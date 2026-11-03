# Self-contained mixed-model baseline

This directory runs the **clean baseline only**. It has no injector, no corrupted
PM messages, and no replay of old model outputs. After the new baseline is
reviewed, new PM corruptions will be prepared from these new PM outputs.

The folder can be moved anywhere. It does not import code or load files from
`manual-pm-v1`, another repository folder, or a parent folder. You still need the
existing Python 3.11 MetaGPT environment, Ollama service/models, and Docker.

## Model assignments and unchanged settings

| Role | Model |
|---|---|
| Product Manager | qwen2.5:7b |
| Architect | qwen2.5:7b |
| Project Manager | qwen2.5:7b |
| Coder | qwen2.5-coder:7b |
| Test Engineer / reviewer | qwen2.5:7b |

`config/config2.yaml` is the single active configuration file: local Ollama,
temperature 0, max_token 2048, timeout 600, stream false, and the role model map.
The `llm` section also bootstraps MetaGPT imports. The runner makes a separate
config copy per role using `role_models`. An old `config/model_roles.yaml` left
from an earlier package is unused by this version.

The five role prompts and Coder/reviewer behavior remain unchanged. Only the
planned model assignments differ from the older all-Coder-model baseline.

## Local contents

```text
mixed-model-baseline-v1/
├── config/config2.yaml           # Shared settings + per-role model map
├── data/HumanEval.jsonl          # All 164 tasks and evaluator-only references
├── tests/HumanEval_N.json        # 164 files, 504 additional named cases
├── run_baseline.py              # Five-agent clean generation + Docker grading
├── metagpt_clean.py              # Existing role definitions and Action
├── lineage.py                   # Khushi's original implementation, unchanged
├── role_lineage.py              # Per-role model-configuration source adapter
├── runtime_utils.py             # Existing save, model identity, cleanup helpers
├── check_suites.py              # Existing grader; dataset path now local
├── evaluate_humaneval.py         # Existing restricted Docker primitive
├── export_baseline.py            # ZIP export for subsequent PM curation
├── test_baseline.py              # Regression checks without real model calls
├── PROVENANCE.json               # Source and material-copy fingerprints
├── README.md
├── runs/                        # Created when you run a study
└── exports/                     # Created by the export command
```

Historical run folders and the old baseline outputs are not copied into this
package. No model weights, virtual environment or installed MetaGPT source is
bundled. Existing reference tests are evaluator data, not instructions to agents.

## Khushi's tracking stays intact

`lineage.py` is a byte-for-byte copy of Khushi's merged implementation. The new
runner retains her `CallRecorder`, explicit routing checks, per-call IDs, SHA-256
content verification and call-graph export. `role_lineage.py` adds separate
sources such as `model_config:coder`, preventing deliberate role model choices
from appearing as accidental configuration mismatches.

The actual provider request is checked against registered role settings and
instructions. Its routed task/previous-agent text is checked against the
produced content. A clean baseline inserts no deliberate message mismatch.
`verified` means unchanged transmission, not semantically correct reasoning.
Undeclared/weak/ambiguous matches should be inspected as evidence, not
immediately treated as code errors.

Use the live-recorded `lineage.json` for per-role settings. The original
retrospective `lineage.py from-trace` utility does not verify the new per-role
model map. The original code is preserved rather than silently extended.

## Update an existing baseline folder

Extract the contents into the existing `meta-gpt2/mixed-model-baseline-v1`
directory, replacing the code/config files supplied by this package. The archive
contains no `runs/` or `exports/`, so file-by-file extraction preserves those
folders. Avoid Finder's whole-folder replacement if you need to retain old runs.

This update changes code and paths, so old pilot checkpoints will not resume
with the new fingerprint. Start a new study. Do not alter historical checkpoint
hashes to bypass compatibility checks. Do not replace code during an active run.

## Use your existing environment

```bash
conda activate "$HOME/Desktop/UC San Diego/Courses/UCSD CSE 291/adhoc/To-Err-Is-to-LLM/.venv-metagpt"
cd "$HOME/Desktop/UC San Diego/Courses/UCSD CSE 291/adhoc/To-Err-Is-to-LLM/meta-gpt2/mixed-model-baseline-v1"
python --version
ollama list
open -a Docker
```

Wait for Engine running, then:

```bash
docker info
docker image inspect python:3.11-slim
```

If absent, use `docker pull python:3.11-slim`. Both exact model tags must be
installed. Use the existing working environment; no reinstall or real OpenAI
API key is needed. The configured key `ollama` is a local dummy key.

Two 7B models can require memory swaps on a 16 GB Mac; the five calls stay
sequential. Model/provider errors remain distinct from generated-code errors.

## Check the new local setup

```bash
python -m unittest -v test_baseline.py
python lineage.py demo
```

The regression tests check local dataset/test completeness, five role model
assignments, unchanged clean deliveries, real recorder wrapping around simulated
providers, failure checkpoints, reports, resume and ZIP export. They do not
measure real Ollama accuracy or execute candidate code. The lineage demo includes
intentional simulated mismatches; it is not your baseline result.

The package was also tested after copying to an isolated directory with no
neighboring experiment folder. Original role/lineage/checker copy hashes and
all test/data hashes were checked against the source material.

## One-task pilot

```bash
caffeinate -i python run_baseline.py --start 0 --limit 1
```

This makes five new calls, with Coder using the coding model. It saves all five
agent messages, then tests both raw Coder source and reviewer final source in
Docker against the official suite and existing additional tests. The reviewer
itself does not execute tests. No test answers or canonical solutions are sent
to agents, and no test feedback changes the generated baseline.

Inspect the output before starting all 164 tasks. This is a new baseline; no
real model generations are included in the download.

## Full clean baseline, after checking the pilot

```bash
caffeinate -i python run_baseline.py --start 0 --limit 164
```

This starts a new study, including task 0, and makes 820 planned model calls
before retries. Freeze code, model settings, model weights and tests for the run.

## Logs and artifacts

```text
runs/baseline-TIMESTAMP/
├── study.json                     # Progress, selected indices, attempts, snapshot
├── totals.json                    # New model-call/token/latency totals
├── results.csv                    # Coder/final official + additional-test results
├── checks.csv                     # Individual outcomes and observed outputs/errors
├── calls.csv                      # Model and metrics for saved stages/all attempts
├── lineage_summary.csv            # Edge status/node counts for latest attempts
├── lineage_edges.csv              # Individual edges, hashes, evidence flags
├── console.log                    # Study stdout/stderr, appended on resume
├── metagpt.log                    # Explicit framework Loguru log sink
└── task-NNN/attempt-N/
    ├── trace.json                 # Complete clean stage records
    ├── lineage.json               # Live call graph
    ├── product_manager_input.json / product_manager.txt
    ├── architect_input.json / architect.txt
    ├── project_manager_input.json / project_manager.txt
    ├── coder_input.json / coder.txt
    ├── test_engineer_input.json / test_engineer.txt
    ├── coder.py                   # Raw Coder source, before review
    ├── final.py                   # Reviewer source
    ├── evaluation.json            # baseline_coder + baseline_final test records
    ├── console.log
    └── metagpt.log
```

The stage `input` is the actual routed user payload. `*_input.json` also stores
intended system messages and role settings. The recorder hashes the actual
observed provider request and checks routed content. Logs are experiment-level
records, not raw HTTP traffic/authentication headers. Import-time warnings may
appear before study capture starts.

Each stage has its own `model_config`; the trace's `role_model_configs` contains
the full role map. The top-level `model_config` is the general-model default, not
Coder's config. `original_output` equals `delivered_output` in this baseline.
`wall_seconds` is newly measured. `evaluation.json` is authoritative for tests.

`calls.csv` records stage tokens/model/time for all saved attempts. Task wall
seconds are in `study.json`; Docker time and code/test hashes are in evaluation
records. Interrupted requests can consume unrecorded computation. Per-stage
request timing is recorded before explicit HTTP-client cleanup.

The official suite has one outcome, while additional tests have separate named
case counts. `completed` does not mean all code was correct. Native baseline
failures must not later be attributed to corruption. A finite test suite does
not guarantee correctness. Timeouts/unresolved executions remain separate.

Generated source is never imported on the host. `metagpt_clean.py` is imported
for its role definitions; its standalone CLI does not apply the mixed-role map.
Likewise, the legacy standalone `evaluate_humaneval.py` CLI does not load the new
additional suite automatically. Use `run_baseline.py`, which calls
`check_suites.evaluate_artifact` with the local tests and trusted helper setup.

## Resume

Wait for the stopped process to exit, then:

```bash
caffeinate -i python run_baseline.py --resume runs/baseline-ACTUAL_TIMESTAMP
```

Completed tasks, including tasks with wrong answers, are skipped. Unfinished or
unresolved tasks get new attempts. Keep code, config, weights, local data/tests
and Docker image unchanged. All relevant local implementation/material files
are fingerprinted, including Khushi's lineage source. Never edit a saved
fingerprint to hide a change. One shared asyncio.Runner and explicit client
closure preserve the earlier asynchronous cleanup fix.

## Inspect dependencies

```bash
python lineage.py show \
  runs/baseline-ACTUAL_TIMESTAMP/task-000/attempt-1/lineage.json \
  --affected project_manager#1
```

Coder and Test Engineer should be downstream of PM.

## Export your NEW baseline for PM curation

```bash
python export_baseline.py runs/baseline-ACTUAL_TIMESTAMP
```

Upload the ZIP printed under `exports/`. It includes the latest attempts with
all original five-agent messages, input records, code, lineage, evaluations,
logs, study tables, dataset, tests and implementation source. Missing/incomplete
attempts are explicitly identified; earlier successes are not silently used.
The safe role configuration is present in the study snapshot, but configuration
credentials are not copied as a raw config file.

Only after reviewing those new PM outputs will we create new corrupted versions
and a separate injected-condition runner. This baseline contains no old corrupt
PM messages or intervention logic.
