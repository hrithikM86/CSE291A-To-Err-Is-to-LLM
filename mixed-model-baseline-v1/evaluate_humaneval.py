"""Evaluate saved code in restricted Docker containers, never on the host.

Official HumanEval checks and supplemental boundary checks are reported
separately. No model calls are made and source traces are left unchanged.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def run_check(code, check_body, image, timeout):
    """Run a trusted check around candidate code in a fresh container."""
    token = "CHECK_COMPLETED_" + uuid.uuid4().hex
    name = "humaneval-" + uuid.uuid4().hex
    harness = (
        "import runpy\n"
        "namespace = runpy.run_path('/work/candidate.py')\n"
        + check_body
        + f"\nprint({token!r}, flush=True)\n"
    )
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix=".evaluation-", dir=ROOT) as temporary:
        folder = Path(temporary)
        folder.chmod(0o755)
        for filename, content in (("candidate.py", code), ("check.py", harness)):
            path = folder / filename
            path.write_text(content, encoding="utf-8")
            path.chmod(0o644)

        command = [
            "docker", "run", "--rm", "--pull=never", "--name", name,
            "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "64", "--memory", "256m", "--cpus", "1",
            "--user", "65534:65534",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
            "--mount", f"type=bind,source={folder.resolve()},target=/work,readonly",
            image, "python", "-I", "-B", "/work/check.py",
        ]
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout
            )
            stdout = completed.stdout
            stderr = completed.stderr
            if completed.returncode == 0 and token in stdout.splitlines():
                status = "passed"
            elif completed.returncode in (125, 126, 127):
                status = "infrastructure_error"
            elif completed.returncode == 0:
                status = "incomplete_check"
            else:
                status = "failed"
            return {
                "status": status,
                "returncode": completed.returncode,
                "stdout": stdout.replace(token, "CHECK_COMPLETED"),
                "stderr": stderr,
                "wall_seconds": round(time.perf_counter() - started, 3),
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "wall_seconds": round(time.perf_counter() - started, 3),
            }
        finally:
            # Also stop a container if the Docker client timed out.
            subprocess.run(
                ["docker", "rm", "-f", name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=20,
            )


def supplemental_checks(task_id, entry_point):
    if task_id != "HumanEval/0":
        return []
    cases = [
        ("duplicate_values_zero_threshold", [1.0, 1.0], 0.0, False),
        ("distance_equal_to_threshold", [1.0, 1.5], 0.5, False),
        ("distance_below_threshold", [1.0, 1.25], 0.5, True),
    ]
    return [
        (
            name,
            f"candidate = namespace[{entry_point!r}]\n"
            f"actual = candidate({numbers!r}, {threshold!r})\n"
            f"print('Expected:', {expected!r}, 'Actual:', actual, flush=True)\n"
            f"assert actual == {expected!r}, 'Boundary result mismatch'\n",
        )
        for name, numbers, threshold, expected in cases
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_folder", type=Path)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "HumanEval.jsonl")
    parser.add_argument("--image", default="python:3.11-slim")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("Timeout must be positive.")
    if not shutil.which("docker"):
        raise SystemExit("Docker CLI not found. Install and open Docker Desktop first.")
    subprocess.run(["docker", "info"], check=True, capture_output=True, timeout=30)
    image_info = subprocess.run(
        ["docker", "image", "inspect", args.image],
        check=True, capture_output=True, text=True, timeout=30,
    )
    image_record = json.loads(image_info.stdout)[0]
    # Use the resolved local image ID so it cannot change between checks.
    image_id = image_record["Id"]

    trace = json.loads((args.run_folder / "trace.json").read_text(encoding="utf-8"))
    if trace.get("status") != "completed":
        raise SystemExit("Select a completed five-role run.")
    artifact_files = trace.get("artifact_files", {})
    candidate_filename = artifact_files.get("attacked_coder", "coder.py")
    final_filename = artifact_files.get("reviewed_final", "final.py")
    for filename in (candidate_filename, final_filename):
        if Path(filename).name != filename:
            raise SystemExit("Artifact filenames must be simple filenames.")
    dataset_bytes = args.dataset.read_bytes()
    if sha256(dataset_bytes) != trace["dataset_sha256"]:
        raise SystemExit("Dataset differs from the one used in this run.")
    matches = [
        json.loads(line) for line in dataset_bytes.splitlines()
        if line.strip() and json.loads(line)["task_id"] == trace["task_id"]
    ]
    if len(matches) != 1:
        raise SystemExit("Expected exactly one matching HumanEval task.")
    item = matches[0]
    official_body = item["test"] + f"\ncheck(namespace[{item['entry_point']!r}])\n"
    extra = supplemental_checks(item["task_id"], item["entry_point"])

    report = {
        "task_id": item["task_id"],
        "source_trace": str((args.run_folder / "trace.json").resolve()),
        "dataset_sha256": sha256(dataset_bytes),
        "docker_image": args.image,
        "docker_image_id": image_id,
        "docker_repo_digests": image_record.get("RepoDigests", []),
        "timeout_per_check_seconds": args.timeout,
        "note": "Official suite and supplemental checks are distinct outcomes.",
        "evaluated_coder_file": candidate_filename,
        "evaluated_final_file": final_filename,
        "status": "running",
        "artifacts": {},
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = args.run_folder / f"evaluation-{stamp}.json"

    def save():
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    save()
    for filename in (candidate_filename, final_filename):
        code_bytes = (args.run_folder / filename).read_bytes()
        result = {"code_sha256": sha256(code_bytes), "supplemental": {}}
        report["artifacts"][filename] = result
        code = code_bytes.decode("utf-8")
        print(f"\n{filename}", flush=True)
        result["official_humaneval"] = run_check(code, official_body, image_id, args.timeout)
        print("  Official HumanEval:", result["official_humaneval"]["status"], flush=True)
        save()
        for name, body in extra:
            result["supplemental"][name] = run_check(code, body, image_id, args.timeout)
            print(f"  {name}:", result["supplemental"][name]["status"], flush=True)
            save()
        result["supplemental_all_passed"] = (
            all(check["status"] == "passed" for check in result["supplemental"].values())
            if extra else None
        )
        save()
    report["status"] = "completed"
    save()
    print("\nEvaluation saved:", path)
    print("Evaluation completed does not mean every test passed.")


if __name__ == "__main__":
    main()
