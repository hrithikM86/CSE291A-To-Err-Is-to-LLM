import json
import shutil
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
RUNNER = ROOT / "recover_pm_m5.py"
MODES = ["stale", "retract", "both", "drop"]
LOGS = ROOT / "runs/recovery_m5_logs"
LOGS.mkdir(parents=True, exist_ok=True)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def find_run(mode):
    matches = []

    for folder in (ROOT / "runs").glob("recovery_m5_*"):
        path = folder / "study.json"
        if not path.is_file():
            continue

        state = read(path)
        if (
            not state.get("dry_run")
            and state.get("method") == "r1"
            and state.get("context") == mode
            and set(state.get("indices", [])) == set(range(164))
        ):
            matches.append(folder)

    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple full {mode} studies found; refusing to guess."
        )

    return matches[0] if matches else None


def generation_complete(state):
    return all(
        state["tasks"].get(f"HumanEval/{i}", {}).get("status")
        == "completed"
        for i in state["indices"]
    )


def evaluation_complete(folder, entry):
    path = folder / entry["folder"] / "evaluation.json"
    if not path.is_file():
        return False

    artifacts = read(path).get("artifacts", {})
    for name in ("recovered_coder", "recovered_final"):
        result = artifacts.get(name, {})
        checks = result.get("checks", [])

        if (
            result.get("official_status") not in {"passed", "failed"}
            or not checks
            or not all(
                c.get("status") in {"passed", "failed"} for c in checks
            )
        ):
            return False

    return True


def execute(arguments, log):
    command = [sys.executable, "-u", str(RUNNER), *arguments]
    message = "\nCOMMAND: " + repr(command) + "\n"
    print(message, flush=True)
    log.write(message)
    log.flush()

    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    try:
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()

        if process.wait() != 0:
            raise RuntimeError("Recovery command failed; see this mode's log.")

    except KeyboardInterrupt:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait()
        raise


failures = []

for mode in MODES:
    with (LOGS / f"{mode}_full.log").open(
        "a", encoding="utf-8", buffering=1
    ) as log:
        try:
            print(f"\n===== MODE: {mode} =====", flush=True)
            folder = find_run(mode)

            if folder is None:
                execute([
                    "--set", "every",
                    "--method", "r1",
                    "--context", mode,
                    "--oracle-source", "lineage",
                    "--skip-eval",
                ], log)
                folder = find_run(mode)

            else:
                state = read(folder / "study.json")

                if not generation_complete(state):
                    stamp = datetime.now(timezone.utc).strftime(
                        "%Y%m%dT%H%M%S%fZ"
                    )

                    # Preserve partial outputs before the original runner
                    # retries an incomplete task in its existing directory.
                    for entry in state["tasks"].values():
                        if entry.get("status") != "completed":
                            source = folder / entry["folder"]
                            if source.is_dir():
                                target = (
                                    folder / "partial_backups"
                                    / stamp / source.name
                                )
                                shutil.copytree(source, target)

                    execute([
                        "--resume", str(folder),
                        "--skip-eval",
                    ], log)

            if folder is None:
                raise RuntimeError("No recovery study folder was recorded.")

            state = read(folder / "study.json")
            if not generation_complete(state):
                raise RuntimeError(
                    "Some generation tasks failed. Rerun this batch "
                    "later to retry them."
                )

            # Retry missing/unresolved evaluations without new model calls.
            for entry in state["tasks"].values():
                entry["evaluated"] = evaluation_complete(folder, entry)

            (folder / "study.json").write_text(
                json.dumps(state, indent=2), encoding="utf-8"
            )

            if not all(e["evaluated"] for e in state["tasks"].values()):
                execute(["--evaluate-only", str(folder)], log)

            state = read(folder / "study.json")
            if not all(
                evaluation_complete(folder, entry)
                for entry in state["tasks"].values()
            ):
                raise RuntimeError("Some Docker checks remain unresolved.")

            print(f"FINISHED {mode}: {folder}", flush=True)

        except KeyboardInterrupt:
            print("\nStopped. Rerun the same batch command to continue.")
            raise SystemExit(130)

        except Exception as error:
            message = f"\nMODE {mode} NEEDS RETRY: {error}\n"
            print(message, flush=True)
            log.write(message)
            failures.append(mode)

print("\nModes needing retry:", failures or "none")
raise SystemExit(1 if failures else 0)
