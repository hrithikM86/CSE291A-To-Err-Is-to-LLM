# Experiment Evidence Index

For the project overview, setup, execution instructions, contributors, and findings, see the [main README](../README.md).

This page identifies the saved studies used in the final comparison.

## Final report

Open [final_project_comparison.html](runs/final_project_comparison.html) locally in a browser.

The report contains per-task test outcomes, code comparisons, lineage evidence, token usage, and runtime measurements.

## Studies included in the report

| Condition | Saved study |
| --- | --- |
| Original baseline | [`baseline-20261030T082523974587Z`](runs/baseline-20261030T082523974587Z/) |
| PM injection | [`pm-replay-20261030T190256124954Z`](runs/pm-replay-20261030T190256124954Z/) |
| Recovery: remove faulty history | [`recovery_m5_r1_20261103T141211230438Z`](runs/recovery_m5_r1_20261103T141211230438Z/) |
| Recovery: keep faulty history | [`recovery_m5_r1-stale_20261103T113551282042Z`](runs/recovery_m5_r1-stale_20261103T113551282042Z/) |
| Recovery: withdrawal markers | [`recovery_m5_r1-r3retract_20261103T122809433235Z`](runs/recovery_m5_r1-r3retract_20261103T122809433235Z/) |
| Recovery: remove history + notice | [`recovery_m5_r1-r3both_20261103T131811856893Z`](runs/recovery_m5_r1-r3both_20261103T131811856893Z/) |

Each study covers 164 HumanEval tasks. Recovery console logs are stored in [`runs/recovery_m5_logs/`](runs/recovery_m5_logs/).

## Inspect one task

1. Open the study's `study.json` and locate the task's recorded folder.
2. Read `trace.json` for agent inputs, outputs, and execution metrics.
3. Inspect the saved Coder and `final.py` implementations.
4. Read `evaluation.json` for official and additional test outcomes.
5. Where available, inspect `lineage.json` for dependency and message-delivery evidence.

Baseline and injection studies use attempt subfolders; recovery task folders follow a different layout. Use `study.json` rather than assuming identical paths.

## Supporting material

- [`pm-message-injections-v1/`](pm-message-injections-v1/): original and corrupted PM messages, mappings, and change documentation.
- [`experiment/experiment-1/`](experiment/experiment-1/): separate downstream model comparison, outside the main six-condition report.
- [`RECOVERY_GUIDE.md`](RECOVERY_GUIDE.md): recovery implementation and arguments.
- [`README_BASELINE_ORIGINAL.md`](README_BASELINE_ORIGINAL.md): historical baseline-only documentation.

Older `recovery-*` artifacts are retained for provenance; the final comparison uses the `recovery_m5_*` studies listed above.

## Evidence preservation

Keep saved traces, generated code, evaluations, and hashes unchanged. Write new experiments into separate study folders.

Some historical checkpoints contain original Mac paths. Refer to the main README's portability notes before resuming a relocated checkpoint.
