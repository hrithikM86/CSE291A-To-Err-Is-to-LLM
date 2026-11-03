# Experiment 1: all-Qwen PM injection

Status: completed
Completed tasks: 164 / 164

The original upstream outputs and exact same corrupted PM messages were reused.
Only Coder and Test Engineer ran anew, both using qwen2.5:7b.
No clean all-Qwen baseline was generated. Historical mixed-model outputs are provenance, not an all-Qwen control.

| Artifact | Official passes / completed tasks | Additional passed / total |
|---|---:|---:|
| attacked_coder | 53 / 164 | 306 / 504 |
| attacked_final | 107 / 164 | 414 / 504 |

New recorded calls, all attempts: 328
New reported tokens, all attempts: 236220
New recorded call seconds, all attempts: 3299.718

See summary.csv, calls.csv, checks.csv, lineage_edges.csv and per-task artifacts.
A delivery mismatch is not proof of fault adoption; test passes are not proof of complete correctness.
Without a clean all-Qwen run, do not attribute every failure to injection.
