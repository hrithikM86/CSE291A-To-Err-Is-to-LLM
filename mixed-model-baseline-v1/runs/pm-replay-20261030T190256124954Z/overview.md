# PM message replay

Study status: completed
Completed comparison tasks: 164 / 164

| Artifact | Official passes on completed tasks | Additional cases passed |
|---|---:|---:|
| baseline_coder | 128 / 164 | 458 / 504 |
| baseline_final | 133 / 164 | 466 / 504 |
| attacked_coder | 54 / 164 | 325 / 504 |
| attacked_final | 118 / 164 | 437 / 504 |

New raw-Coder official failures: 82 / 128 eligible baseline passes.
Final official regressions: 25 / 133 eligible baseline passes.
Official test recoveries after a new raw-Coder failure: 62.
New raw-Coder official failures persisting through review: 20.

New recorded model calls, all attempts: 328
New reported tokens, all attempts: 207001
New recorded model-call seconds, all attempts: 2772.467

Baseline evaluation is reused after hash and environment checks; upstream generations are not charged again.
Calls without reported token counters and interrupted requests may consume unreported computation.
Official test outcomes do not establish full correctness or adoption of a specific fault.

- comparison.csv: per-task baseline versus attacked raw Coder and final outcomes.
- comparison_checks.csv: individual baseline-to-attacked test transitions.
- calls.csv: new role calls across all attempts, tokens and latency.
- lineage_edges.csv: recorded transmissions, including the substituted PM mismatch.
- task-NNN/attempt-N/: full messages, code, diffs, trace, lineage and evaluation.
