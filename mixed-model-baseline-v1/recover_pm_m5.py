"""R1 and R3 recovery for the mixed-model PM replay study.

Reads a finished pm-replay study and writes a NEW recovery study. The source
study is never modified. Each rerun uses the model recorded for that role.

    python recover_pm.py --set broken --dry-run
    python recover_pm.py --set every --skip-eval --config config/config2.docker.yaml
    python recover_pm.py --evaluate-only runs/recovery-r1-TIMESTAMP
    python recover_pm.py --resume runs/recovery-r1-TIMESTAMP --skip-eval --config config/config2.docker.yaml

Methods: r1 restores the Project Manager's genuine output, verified by its lineage
hash, then reruns the Coder and Test Engineer. none keeps the attacked outputs.
--context selects the R3 input mode; see clean_context.py.

Python 3.9 compatible: generation runs inside the metagpt/metagpt Docker image.
"""
import argparse
import asyncio
import csv
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ["METAGPT_PROJECT_ROOT"] = str(ROOT)

from clean_context import CONTEXT_MODES, add_context, find_poison, norm  # noqa: E402
from runtime_utils import close_model_clients, model_identity  # noqa: E402
from runtime_utils import save as _atomic_save  # noqa: E402

STAGES = ["product_manager", "architect", "project_manager", "coder", "test_engineer"]
CODE_FILES = {"coder": "coder.py", "test_engineer": "final.py"}
ROLE_GOAL = "Produce a correct solution to the supplied function specification."
SETTINGS = ["model", "temperature", "max_token", "timeout", "stream"]
DEFAULT_SOURCE = "runs/pm-replay-20261030T190256124954Z"


def save(path, value, attempts=10):
    """Atomic save, retried: OneDrive/antivirus can briefly lock the target on Windows."""
    for n in range(attempts):
        try:
            return _atomic_save(path, value)
        except PermissionError:
            if n == attempts - 1:
                raise
            time.sleep(0.2 * (n + 1))


def h(text):
    return hashlib.sha256(norm(text).encode("utf-8")).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_items():
    path = ROOT / "data/HumanEval.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def source_attempt(source, task_id):
    attempts = read_json(source / "study.json")["tasks"].get(task_id)
    if not attempts:
        raise ValueError("Source study has no attempt for %s" % task_id)
    return source / attempts[-1]["folder"]


def base_output(base, stage):
    return next(s["delivered_output"] for s in base["stages"] if s["stage"] == stage)


def unwrap_code(text):
    """Same as metagpt_clean.unwrap_code, without importing MetaGPT."""
    text = text.strip()
    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].strip() in {"```python", "```py", "```"} and lines[-1].strip() == "```":
        text = "\n".join(lines[1:-1]).strip()
    return text + "\n"


def passes(result):
    c = result["additional_counts"]
    return result["official_status"] == "passed" and not (c.get("failed") or c.get("timeout") or c.get("unresolved"))


def select_tasks(source, items, which):
    """broken: the baseline passes and the attacked final code fails.
    baseline-pass: the baseline passes. every: all tasks, broken ones first."""
    broken, passing, others = [], [], []
    for i, item in enumerate(items):
        a = read_json(source_attempt(source, item["task_id"]) / "evaluation.json")["artifacts"]
        if passes(a["baseline_final"]) and not passes(a["attacked_final"]):
            broken.append(i)
        elif passes(a["baseline_final"]):
            passing.append(i)
        else:
            others.append(i)
    return {"broken": broken, "baseline-pass": broken + passing, "every": broken + passing + others}[which]


# ------------------------------------------------------------ dependency layer
def load_lineage(src_folder):
    from lineage import CallGraph
    return CallGraph.from_json(read_json(src_folder / "lineage.json"))


def lineage_invalidate(lineage, faulty):
    """Faulty stage plus the role of every call that transitively consumed it."""
    node = lineage.resolve(faulty)
    return {faulty} | {lineage.nodes[n]["role"] for n in lineage.affected(node) if "role" in lineage.nodes[n]}


def trace_invalidate(trace, faulty):
    """The same answer from the dependency lists saved in the trace; a cross-check."""
    bad = {faulty}
    for s in trace["stages"]:
        if any(d in bad for d in s["depends_on"]):
            bad.add(s["stage"])
    return bad


def lineage_suspects(lineage):
    """Producers whose delivered data did not match what they produced, earliest first."""
    found = []
    for node in sorted(lineage.nodes.values(), key=lambda n: n["seq"]):
        for edge in node["inputs"]:
            producer = lineage.nodes[edge["node"]]
            if edge["status"] == "mismatch" and producer["kind"] != "configuration" and "role" in producer:
                found.append(dict(producer=producer["role"], producer_node=producer["id"], consumer_node=node["id"]))
    return found


# ----------------------------------------------------------------- execution
def load_configs(path):
    """One config per role, built the same way as run_baseline.load_configs."""
    import yaml
    from metagpt.config2 import Config
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if set(data.get("role_models", {})) != set(STAGES):
        raise SystemExit("role_models must list exactly the five workflow roles.")
    shared = Config(llm=data["llm"])
    configs = {}
    for role in STAGES:
        config = shared.model_copy(deep=True)
        config.llm.model = data["role_models"][role]
        configs[role] = config
    return configs


def check_settings(config, recorded, stage):
    """The rerun must use the model and settings the source study recorded for this role."""
    actual = {k: getattr(config.llm, k) for k in SETTINGS}
    expected = {k: recorded.get(k) for k in SETTINGS}
    if actual != expected:
        raise RuntimeError("%s settings differ from the source study: %s vs %s" % (stage, actual, expected))


async def call_role(config, stage, guidance, payload):
    from metagpt_clean import ArtifactAction, Role, ROLE_SPECS
    title = dict((n, t) for n, t, _ in ROLE_SPECS)[stage]
    action = ArtifactAction(guidance=guidance, config=config)
    initial = action.llm
    role = Role(name=stage, profile=title, goal=ROLE_GOAL, actions=[action], config=config)
    before = action.llm.get_costs()
    started = time.perf_counter()
    try:
        response = await role.run(json.dumps(payload))
        if response is None or not response.content.strip():
            raise RuntimeError("Empty role response")
        return response.content
    finally:
        after = action.llm.get_costs()
        call_role.last = dict(
            model=config.llm.model,
            elapsed_seconds=round(time.perf_counter() - started, 3),
            prompt_tokens=after.total_prompt_tokens - before.total_prompt_tokens,
            completion_tokens=after.total_completion_tokens - before.total_completion_tokens)
        await close_model_clients([initial, action.llm, role.llm])


async def recover_task(args, configs, item, out):
    t0 = time.perf_counter()
    src_folder = source_attempt(args.source, item["task_id"])
    src = read_json(src_folder / "trace.json")
    base = read_json(src_folder / "baseline_trace.json")

    b0 = time.perf_counter()
    lineage = load_lineage(src_folder)
    suspects = lineage_suspects(lineage)
    if args.oracle_source == "lineage":
        if not suspects:
            raise RuntimeError("Lineage located no mismatched data edge; nothing to recover.")
        faulty = suspects[0]["producer"]
    else:
        faulty = src["intervention"]["target"]
    invalid = set() if args.method == "none" else lineage_invalidate(lineage, faulty)
    if args.method != "none" and invalid != trace_invalidate(src, faulty):
        raise RuntimeError("Lineage and trace disagree on affected stages.")
    # The producer's node holds the hash of what it really produced. The clean copy
    # must match it, otherwise the copy is not trustworthy.
    clean_copy_verified = (lineage.nodes[lineage.resolve(faulty)].get("output_sha256")
                           == hashlib.sha256(base_output(base, faulty).encode("utf-8")).hexdigest())
    if args.method == "r1" and not clean_copy_verified:
        raise RuntimeError("Clean copy of %s does not match the hash its producer recorded." % faulty)
    poisoned = {s["stage"]: s["delivered_output"] for s in src["stages"] if s["stage"] in invalid}
    overhead = time.perf_counter() - b0

    trace = dict(experiment="mixed_pm_recovery", method=args.method, context=args.context, dry_run=args.dry_run,
                 task_id=item["task_id"], source_trace=(src_folder.relative_to(ROOT) / "trace.json").as_posix(),
                 faulty_stage=faulty, fault_source=args.oracle_source, lineage_suspects=suspects,
                 clean_copy_verified=clean_copy_verified if args.method == "r1" else None,
                 invalidated=sorted(invalid, key=STAGES.index), retained=[s for s in STAGES if s not in invalid],
                 stages=[], status="running")
    save(out / "trace.json", trace)

    previous = None  # (stage name, delivered text)
    recovered_texts = set()  # outputs produced or restored during this recovery
    calls = []
    for s in src["stages"]:
        name = s["stage"]
        record = dict(stage=name, depends_on=s["depends_on"], guidance=s["guidance"], model=s["model_config"]["model"])
        if name not in invalid:
            text = s["delivered_output"]
            record.update(execution="reused", input=s["input"])
        elif name == faulty:
            text = base_output(base, name)
            record.update(execution="restored_clean", input=s["input"], poison_in_input=False,
                          evidence="baseline trace output, hash matches producer node in lineage")
        else:
            payload = dict(original_specification=item["prompt"], previous_stage=previous[0], previous_artifact=previous[1])
            add_context(payload, args.context, s, invalid, faulty)
            b0 = time.perf_counter()
            leaked = find_poison(payload, poisoned, recovered_texts)
            overhead += time.perf_counter() - b0
            record.update(input=payload, poison_in_input=bool(leaked))
            if leaked and args.context != "stale":
                raise RuntimeError("Poisoned artifact from %s leaked into %s payload" % (leaked, name))
            if args.dry_run:
                record.update(execution="would_call")
                trace["stages"].append(record)
                trace["status"] = "dry_run_stopped_at_model_call"
                break
            check_settings(configs[name], s["model_config"], name)
            print("Running %s: %s" % (name, configs[name].llm.model), flush=True)
            text = await call_role(configs[name], name, s["guidance"], payload)
            record.update(execution="rerun", **call_role.last)
            calls.append(dict(stage=name, **call_role.last))
        record.update(delivered_output=text, output_sha256=h(text),
                      matches_baseline_output=h(text) == h(base_output(base, name)),
                      matches_attacked_output=h(text) == h(s["delivered_output"]))
        trace["stages"].append(record)
        if name in CODE_FILES:
            (out / CODE_FILES[name]).write_text(unwrap_code(norm(text)), encoding="utf-8")
        previous = (name, text)
        if name in invalid:
            recovered_texts.add(norm(text))
        save(out / "trace.json", trace)

    if trace["status"] == "running":
        trace["status"] = "completed"
    execs = [r["execution"] for r in trace["stages"]]
    trace["metrics"] = dict(
        llm_calls=len(calls),
        recomputed_stages=execs.count("rerun"),
        restored_stages=execs.count("restored_clean"),
        retained_stages=execs.count("reused"),
        stages_with_poison_in_input=sum(bool(r.get("poison_in_input")) for r in trace["stages"]),
        prompt_tokens=sum(c["prompt_tokens"] for c in calls),
        completion_tokens=sum(c["completion_tokens"] for c in calls),
        model_seconds=round(sum(c["elapsed_seconds"] for c in calls), 3),
        tracking_overhead_seconds=round(overhead, 6),
        recovery_wall_seconds=round(time.perf_counter() - t0, 3))
    save(out / "trace.json", trace)
    return trace


# ---------------------------------------------------------------- evaluation
def evaluate_study(folder, image_tag):
    from check_suites import evaluate_artifact, load_suite
    subprocess.run(["docker", "info"], check=True, stdout=subprocess.DEVNULL)
    image = subprocess.check_output(["docker", "image", "inspect", image_tag, "--format", "{{.Id}}"], text=True).strip()
    state = read_json(folder / "study.json")
    items = load_items()
    for task_id, entry in state["tasks"].items():
        out = folder / entry["folder"]
        if entry.get("evaluated"):
            continue
        i = entry["index"]
        evaluation = dict(task_id=task_id, image_id=image, artifacts={})
        for name, filename in (("recovered_coder", "coder.py"), ("recovered_final", "final.py")):
            path = out / filename
            if not path.is_file():
                continue
            result = evaluate_artifact(path.read_text(encoding="utf-8"), items[i], load_suite(i), image)
            result["code_sha256"] = h(path.read_text(encoding="utf-8"))
            evaluation["artifacts"][name] = result
            print(task_id, name, result["official_status"], result["additional_counts"], flush=True)
        save(out / "evaluation.json", evaluation)
        entry["evaluated"] = True
        save(folder / "study.json", state)
    report(folder)


def report(folder):
    state = read_json(folder / "study.json")
    source = ROOT / state["source"]
    rows = []
    for task_id, entry in state["tasks"].items():
        out = folder / entry["folder"]
        row = dict(task_id=task_id, method=state["method"], context=state["context"], status=entry["status"],
                   **entry.get("metrics", {}))
        tpath = out / "trace.json"
        if tpath.is_file():
            final = next((s for s in read_json(tpath)["stages"]
                          if s["stage"] == "test_engineer" and "output_sha256" in s), None)
            row["final_matches_baseline"] = final["matches_baseline_output"] if final else None
        a = read_json(source_attempt(source, task_id) / "evaluation.json")["artifacts"]
        row["baseline_final_pass"] = passes(a["baseline_final"])
        row["attacked_final_pass"] = passes(a["attacked_final"])
        ev = out / "evaluation.json"
        if ev.is_file():
            r = read_json(ev)["artifacts"]
            if "recovered_final" in r:
                row["recovered_final_pass"] = passes(r["recovered_final"])
        rows.append(row)
    fields = list(dict.fromkeys(k for r in rows for k in r)) or ["task_id"]
    with (folder / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, default=ROOT / DEFAULT_SOURCE, help="Finished pm-replay study (read only).")
    p.add_argument("--method", choices=["none", "r1"], default="r1")
    p.add_argument("--context", choices=CONTEXT_MODES, default="drop", help="R3 input mode; stale means no R3.")
    p.add_argument("--oracle-source", choices=["notes", "lineage"], default="notes",
                   help="notes: supplied fault identity; lineage: first mismatched data edge (detection).")
    p.add_argument("--tasks", help="Comma-separated HumanEval indices.")
    p.add_argument("--set", choices=["broken", "baseline-pass", "every"], default="broken")
    p.add_argument("--limit", type=int)
    p.add_argument("--config", type=Path, default=ROOT / "config/config2.yaml")
    p.add_argument("--image", default="python:3.11-slim", help="Docker image for test evaluation.")
    p.add_argument("--skip-eval", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="No model calls; stop at the first required call.")
    p.add_argument("--evaluate-only", type=Path)
    p.add_argument("--resume", type=Path, help="Continue a recovery study; finished tasks are kept.")
    args = p.parse_args()

    if args.evaluate_only:
        evaluate_study(args.evaluate_only.resolve(), args.image)
        return

    items = load_items()
    if args.resume:
        folder = args.resume.resolve()
        state = read_json(folder / "study.json")
        args.method, args.context, args.oracle_source = state["method"], state["context"], state["oracle_source"]
        args.source = ROOT / state["source"]
        indices = state["indices"]
    else:
        args.source = args.source.resolve()
        indices = [int(x) for x in args.tasks.split(",")] if args.tasks else select_tasks(args.source, items, args.set)
        if args.limit:
            indices = indices[:args.limit]
        tag = args.method + {"drop": "", "stale": "-stale"}.get(args.context, "-r3" + args.context)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        folder = ROOT / "runs" / ("recovery_m5_%s_%s%s" % (tag, stamp, "-dry" if args.dry_run else ""))
        folder.mkdir(parents=True)
        state = dict(status="running", method=args.method, context=args.context, oracle_source=args.oracle_source,
                     dry_run=args.dry_run, source=args.source.relative_to(ROOT).as_posix(), indices=indices, tasks={})

    configs = None
    if not args.dry_run and args.method != "none":
        configs = load_configs(args.config.resolve())
        state["models"] = {model: model_identity(dict(model=model, base_url=configs["coder"].llm.base_url))
                           for model in sorted({c.llm.model for c in configs.values()})}
    save(folder / "study.json", state)
    print("RECOVERY STUDY:", folder, "tasks:", len(indices), flush=True)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        for i in indices:
            item = items[i]
            if state["tasks"].get(item["task_id"], {}).get("status") == "completed":
                continue
            out = folder / ("task-%03d" % i)
            out.mkdir(exist_ok=True)
            entry = dict(index=i, folder=out.name, status="running")
            state["tasks"][item["task_id"]] = entry
            try:
                t = loop.run_until_complete(recover_task(args, configs, item, out))
                entry.update(status=t["status"], metrics=t["metrics"])
                print(item["task_id"], t["status"], t["metrics"], flush=True)
            except Exception as exc:
                entry.update(status="error", error="%s: %s" % (type(exc).__name__, exc))
                print(item["task_id"], entry["error"], flush=True)
            save(folder / "study.json", state)
    finally:
        loop.close()
        state["status"] = "generated"
        save(folder / "study.json", state)
        report(folder)
    if not (args.skip_eval or args.dry_run):
        evaluate_study(folder, args.image)
    print("Results:", folder, flush=True)


if __name__ == "__main__":
    main()
