# Mixed-model baseline, PM injection and recovery

This folder contains the project scripts, HumanEval dataset, 504 additional checks,
PM interventions, baseline and attacked outputs, Mac recovery runs and HTML reports.
The earlier baseline-only guide is retained as `README_BASELINE_ORIGINAL.md`.

## Important code

| Script | Purpose |
| --- | --- |
| `run_baseline.py` | Run all five original agents, record metrics/lineage and grade Coder and reviewed code in Docker. |
| `metagpt_clean.py` | MetaGPT roles/actions and shared prompts for the five-agent workflow. |
| `run_pm_replay.py` | Reuse baseline upstream messages, deliver curated corrupted PM instructions and rerun Coder/Tester. |
| `lineage.py`, `role_lineage.py` | Record call dependencies, role configurations and message delivery hashes. |
| `check_suites.py`, `evaluate_humaneval.py` | Docker-isolated official and additional checks. |
| `clean_context.py` | Construct drop, stale, retract and both history variants. |
| `recover_pm.py`, `recover_pm_m5.py` | Restore the original PM and rerun downstream roles; the latter uses Mac-specific output names. |
| `run_recovery_m5_night.py` | Sequential, logged execution of the four recovery variants with resume support. |
| `generate_final_project_report.py` | Build baseline/injection/recovery HTML, CSV and JSON comparisons from saved evidence. |
| `runtime_utils.py` | Model identity, JSON saving and client cleanup helpers. |
| `export_baseline.py` | Export baseline evidence for intervention preparation. |
| `experiment/experiment-1/` | Separate all-Qwen Coder/Tester comparison. |

## Important data and evidence

- `config/`: Ollama/MetaGPT settings and model assignments.
- `data/HumanEval.jsonl`: 164 official task specifications and tests.
- `tests/HumanEval_*.json`: existing additional per-task checks, not pytest modules.
- `pm-message-injections-v1/`: original and corrupted PM messages, payloads and intervention provenance.
- `runs/baseline-20261030T082523974587Z/`: original baseline, with all five roles.
- `runs/pm-replay-20261030T190256124954Z/`: PM injection replay.
- `runs/recovery_m5_*/`: the four Mac recovery studies; `recovery_m5_logs/` stores console logs.
- Older `runs/recovery-*` artifacts, if present, belong to earlier recovery experiments.
- Per-task `trace.json`: inputs, outputs, stage execution and metrics.
- `lineage.json`: original call graph and producer/received hashes; a mismatch detects changed delivery, not mathematical correctness.
- `evaluation.json`: Docker grading for code artifacts and individual checks.
- `study.json`: selection, configuration, checkpoint status and task folders.
- `summary.csv`, `calls.csv` and report files: summaries where the corresponding runner produced them.
- `exports/`, `logs/`: preserved source exports and execution logs.

## Environment

Use Python 3.11. The recorded package versions are in
`requirements-recorded.txt`. That file records key direct dependencies; it is not
an independently validated full dependency lock. MetaGPT's historical dependency
resolver can require constraints on modern package indexes. Reuse the working
Conda environment for the original Mac setup. If exported from that environment,
`environment-lock.txt` captures its complete pip package list.

Ollama, both model weights, Docker Desktop and the Python environment are external
runtime dependencies, not included in this source repository.

## Commands (run from this folder)

Read saved results without model calls or Docker:

```bash
python generate_final_project_report.py
open runs/final_project_comparison.html  # macOS
```

Start a new baseline pilot (requires the configured environment and services):

```bash
python run_baseline.py --start 0 --limit 1
```

Validate source mappings for a new PM replay without model calls:

```bash
python run_pm_replay.py --baseline runs/baseline-20261030T082523974587Z \
  --injections pm-message-injections-v1 --start 0 --limit 164 --validate-only
```

Recovery methods and arguments are documented in `RECOVERY_GUIDE.md`.
Do not start the overnight launcher just to view results: it can resume work and
perform model calls or Docker checks if saved work is incomplete.

## Independence and portability

Core Python helpers, data, tests and PM messages are inside this folder. The
experiment subfolder's parent traversal stays inside this folder. Run commands
from this folder so relative `runs/...` references resolve correctly.

Historical replay `study.json` files contain absolute paths to the original Mac
for source baseline, injection package and configuration. These remain unchanged
for provenance. Viewing saved reports and generating the final comparison uses
local files; resuming an old replay checkpoint at a different location is not
fully portable. Start a new study with explicit local paths, or adapt a separate
checkpoint copy with provenance documented. Do not rewrite historical traces,
code or hashes to hide relocation.

The recovery evaluator records code hashes and check names but not test-content
hashes, and it does not record a fresh recovery call graph. Report evidence limits
remain visible. Baseline is a comparison condition, not a correctness oracle.
