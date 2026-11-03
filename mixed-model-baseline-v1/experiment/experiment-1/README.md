# Experiment 1 — same PM corruptions, Coder and reviewer both qwen2.5:7b

Extract this package inside your existing `mixed-model-baseline-v1/` project. It creates:

```text
mixed-model-baseline-v1/
├── config/, data/, tests/, pm-message-injections-v1/   # Existing, unchanged
├── run_baseline.py, lineage.py, role_lineage.py, ...  # Existing helpers, unchanged
├── runs/baseline-20261030T082523974587Z/               # Existing source records
└── experiment/
    └── experiment-1/
        ├── run_experiment_1.py
        ├── WHAT_WE_ARE_DOING.txt
        ├── README.md
        └── runs/all-qwen-pm-TIMESTAMP/               # Created when you run
```

The first three agents originally used qwen2.5:7b and are reused. Only the Coder model changes from qwen2.5-coder:7b to qwen2.5:7b; the Test Engineer remains qwen2.5:7b. The original specification, role prompts, sampling settings, token limits, model digest for qwen2.5:7b, Docker image, and existing tests are checked against the source study. The exact same corrupted PM message package is used. No corruption files are regenerated or edited. The original YAML is not modified; the Coder-model override exists only in this runner's memory.

## Run from this experiment folder

Keep the existing `.venv-metagpt` environment active. From `mixed-model-baseline-v1/`:

```bash
cd experiment/experiment-1
```

Check all 164 source mappings without model calls or Docker:

```bash
python run_experiment_1.py --start 0 --limit 164 --validate-only
```

With Ollama and Docker running, test one task:

```bash
caffeinate -i python run_experiment_1.py --start 0 --limit 1
```

Inspect the printed results folder. After checking the pilot, start a separate full study:

```bash
caffeinate -i python run_experiment_1.py --start 0 --limit 164
```

Two new role calls per task: 328 planned calls for 164 tasks before retries. Completed execution does not mean every code artifact passed tests.

If interrupted, ensure the original process has stopped, reactivate the same environment and services, then use:

```bash
caffeinate -i python run_experiment_1.py --resume-full
```

This resumes the unique unfinished full 164-task study in this experiment's own `runs/`. It refuses ambiguity. Completed tasks are skipped; incomplete or unresolved tasks receive new attempt folders. Inputs, code and settings must remain unchanged across resume. For a pilot or a specifically chosen study, use `--resume` with its exact printed study folder.

## Results

- `overview.md`: all-Qwen attacked raw/final pass counts and recorded new token/time totals.
- `summary.csv`: task ID, execution, PM delivery mismatch, and raw/final official and additional test results.
- `calls.csv`: new Coder and Test Engineer calls across attempts, tokens and latency.
- `results.csv`, `checks.csv`: detailed artifact/check outcomes.
- `lineage_edges.csv`, `lineage_summary.csv`: transmission/configuration evidence.
- `totals.json`, `study.json`: totals, frozen inputs/environment and resume state.
- `console.log`, `metagpt.log`: study-level logs, also saved per task.
- `task-NNN/attempt-N/`: unchanged upstream outputs, original/corrupted PM, inputs, `coder_after_pm_injection.py`, `final.py`, `review.diff`, trace, lineage, and evaluation.

Historical source trace, lineage, evaluations and code copies are retained for audit. Files named `historical_mixed_baseline_coder.py` and `historical_mixed_baseline_final.py` came from the previous mixed-model run. They are not a newly run all-Qwen baseline and are not included in this study's outcome totals. Only the two new attacked artifacts are graded here.

The lineage preserves the original PM producer hash and checks the corrupted delivery against it, so PM → Coder should show `mismatch`. New Coder and Test Engineer model-config edges point to the explicit `model_config:experiment_1_all_qwen` node. This makes the planned model change visible without incorrectly flagging it as an unexpected config mismatch. Khushi's lineage.py remains unchanged.

The old `generate_final_comparison.py` was built for mixed-model baseline-versus-injection studies. This experiment has its own schema and summaries; a later comparison should pair its results with the previous corrupted study by task ID and confirm identical PM hashes. Do not interpret the historical mixed-model baseline as an all-Qwen control.

## Verification

Read-only validation passed against all 164 exported source tasks. Offline simulations checked the two all-Qwen routes, unchanged PM delivery bytes, the intended mismatch edge, verified new model-config edges, two new calls per task, attacked-only evaluations, cost reporting, and completed-task resume skipping. The actual Ollama/Docker experiment is run locally by you.
