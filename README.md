# CSE291A: To-Err-Is-to-LLM

### Error propagation and recovery in multi-agent LLM systems

A five-agent coding study that measures how a faulty Project Manager message affects downstream code, whether review corrects it, and how restoring the message and handling faulty history changes recovery.

**164 HumanEval tasks · 504 additional test cases · Five MetaGPT agents · Four recovery configurations**

[Full experiment report](mixed-model-baseline-v1/runs/final_project_comparison.html) · [Experiment code](mixed-model-baseline-v1/) · [Recovery guide](mixed-model-baseline-v1/RECOVERY_GUIDE.md) · [Original research repository](https://github.com/hrithikM86/To-Err-Is-to-LLM)

## Overview

```text
Product Manager → Architect → Project Manager → Coder → Test Engineer
                                                    ↓            ↓
                                             Docker evaluation of both code artifacts
```

The **Coder** uses `qwen2.5-coder:7b`. The other four agents use `qwen2.5:7b`, served locally through Ollama. The **Test Engineer** reviews code and returns a final implementation; it is separate from the Docker evaluator that executes the official and additional tests.

All experiments reported in the final comparison were run on a **Mac M5**. Earlier collaborator recovery artifacts are also preserved for provenance; the final report selects the new `recovery_m5_*` Mac runs rather than those older results.

### Experimental conditions

1. **Original baseline:** run all five agents and evaluate the Coder and reviewed final code.
2. **PM injection:** reuse the original Product Manager and Architect outputs, replace the Project Manager's output with a curated, task-specific faulty implementation plan, then rerun the Coder and Test Engineer.
3. **Recovery:** use lineage to identify the changed PM handoff, restore the original baseline PM message, and rerun the two downstream agents under one of four history configurations.

The intervention changes an intermediate **message**, not the model weights. Corrupted instructions are designed to produce semantic mistakes in runnable code; they do not guarantee adoption or test failure. Existing official and additional tests are reused across conditions.

| Recovery name | Argument | What happens to old faulty history |
| --- | --- | --- |
| Remove faulty history | `drop` | Omit the faulty history. |
| Keep faulty history | `stale` | Retain the old faulty history despite restoring the PM message. |
| Withdrawal markers | `retract` | Replace faulty history entries with withdrawal markers. |
| Remove history + notice | `both` | Omit faulty history and add a retraction notice. |

All four are configurations of `--method r1`; they are not four separate `--method` arguments. The `none` method reuses the attacked outputs without recovery.

## Repository layout

```text
CSE291A-To-Err-Is-to-LLM/
├── README.md
└── mixed-model-baseline-v1/
    ├── config/                       # Model assignments and MetaGPT/Ollama settings
    ├── data/                         # HumanEval specifications and official tests
    ├── tests/                        # 504 additional checks across 164 task files
    ├── pm-message-injections-v1/      # Original/corrupted PM messages and provenance
    ├── experiment/experiment-1/       # Separate all-Qwen downstream-model comparison
    ├── runs/                         # Baseline, injection, recovery and report evidence
    │   ├── baseline-20261030T082523974587Z/
    │   ├── pm-replay-20261030T190256124954Z/
    │   ├── recovery_m5_*/            # Four Mac recovery studies and their console logs
    │   └── final_project_comparison.html
    ├── logs/                         # Execution logs
    ├── exports/                      # Baseline exports for intervention preparation
    ├── metagpt/                      # Local MetaGPT-generated support assets
    ├── environment-lock.txt          # Packages exported from the working environment
    ├── requirements-recorded.txt     # Key recorded package versions
    └── *.py                          # Experiment runners and analysis utilities
```

The small local `metagpt/` directory is not a replacement for the installed MetaGPT Python package. Model weights, Docker and the Python environment are external dependencies.

### Important code

| File | What it does |
| --- | --- |
| [`run_baseline.py`](mixed-model-baseline-v1/run_baseline.py) | Runs the five-agent baseline and saves messages, metrics, lineage and Docker test results. |
| [`metagpt_clean.py`](mixed-model-baseline-v1/metagpt_clean.py) | Defines the MetaGPT roles, actions and shared instructions used by the pipeline. |
| [`run_pm_replay.py`](mixed-model-baseline-v1/run_pm_replay.py) | Delivers the curated faulty PM message and reruns the Coder and Test Engineer against the saved baseline. |
| [`lineage.py`](mixed-model-baseline-v1/lineage.py) | Records call dependencies and compares produced-message hashes with the content downstream agents received. |
| [`role_lineage.py`](mixed-model-baseline-v1/role_lineage.py) | Associates each role with its model configuration in the dependency graph. |
| [`check_suites.py`](mixed-model-baseline-v1/check_suites.py) | Runs the official and additional checks using the Docker evaluation utilities. |
| [`evaluate_humaneval.py`](mixed-model-baseline-v1/evaluate_humaneval.py) | Provides Docker-isolated evaluation of generated Python code. |
| [`recover_pm_m5.py`](mixed-model-baseline-v1/recover_pm_m5.py) | Restores the baseline PM message and regenerates affected downstream outputs into new Mac recovery runs. |
| [`clean_context.py`](mixed-model-baseline-v1/clean_context.py) | Builds the four history-handling variants used during recovery. |
| [`run_recovery_m5_night.py`](mixed-model-baseline-v1/run_recovery_m5_night.py) | Schedules the four recovery configurations sequentially, retaining logs and resuming incomplete work. |
| [`generate_final_project_report.py`](mixed-model-baseline-v1/generate_final_project_report.py) | Builds the combined baseline, injection and recovery HTML, CSV and JSON reports from saved evidence. |
| [`experiment/experiment-1/run_experiment_1.py`](mixed-model-baseline-v1/experiment/experiment-1/run_experiment_1.py) | Compares the corrupted-PM condition with general Qwen replacing Qwen-Coder in the Coder role. |

## Run the project

### 1. Clone and enter the experiment folder

```bash
git clone https://github.com/hrithikM86/CSE291A-To-Err-Is-to-LLM.git
cd CSE291A-To-Err-Is-to-LLM/mixed-model-baseline-v1
```

Use **Python 3.11**. The recorded main dependencies are MetaGPT `0.8.1`, OpenAI Python SDK `1.39.0`, Pydantic `2.9.2` and PyYAML `6.0.1`. The OpenAI SDK communicates with Ollama's local compatible endpoint; these experiments do not require a paid OpenAI API key.

If the original working Conda environment is available, activate it. For a fresh compatible environment:

```bash
conda create -n cse291a python=3.11 -y
conda activate cse291a
python -m pip install -r environment-lock.txt
python -m pip check
```

The lock file records the original environment, not a tested cross-platform installer. MetaGPT's older dependencies can require platform-specific resolution on newer package indexes. Keep the original environment when reproducing the Mac setup; `requirements-recorded.txt` is only a short record of direct package versions.

### 2. Start Ollama and Docker

Install Ollama and Docker Desktop first. On macOS:

```bash
open -a Ollama
open -a Docker
ollama pull qwen2.5:7b
ollama pull qwen2.5-coder:7b
curl --fail http://localhost:11434/api/tags
docker info
docker pull python:3.11-slim
```

Wait until Docker's engine is running. Role assignments and generation settings are in [`config/config2.yaml`](mixed-model-baseline-v1/config/config2.yaml): temperature `0`, maximum output `2048` tokens, timeout `600` seconds. Saved model digests identify the original weights; the same tag or temperature alone does not guarantee identical future generations.

### 3. Inspect the saved results without rerunning anything

```bash
python generate_final_project_report.py
open runs/final_project_comparison.html
```

This reads existing evidence and writes matching `.html`, `.csv` and `.json` files. It does not call models or run Docker. Download/open the HTML locally: GitHub's normal file viewer does not display it as an interactive dashboard.

### 4. Run a new baseline

Start with one task, then run all tasks after checking the pilot:

```bash
python run_baseline.py --start 0 --limit 1
caffeinate -i python run_baseline.py --start 0 --limit 164
```

Each command creates a separate timestamped study in `runs/`. Resume an interrupted baseline using its actual folder name:

```bash
python run_baseline.py --resume runs/<your-baseline-folder>
```

`caffeinate` is optional and macOS-specific; it prevents idle sleep while the command runs.

### 5. Replay the saved PM injections

Validate the curated messages against their **original paired baseline** first:

```bash
python run_pm_replay.py \
  --baseline runs/baseline-20261030T082523974587Z \
  --injections pm-message-injections-v1 \
  --start 0 --limit 164 --validate-only
```

Run the replay by removing `--validate-only`. It creates a new timestamped study and makes two new model calls per task. The saved intervention package is tied to its source baseline by hashes; do not silently pair it with a newly generated baseline. Use `--resume <study-folder>` to resume a compatible replay checkpoint.

### 6. Run recovery

A one-task recovery against the saved injection study:

```bash
python recover_pm_m5.py \
  --source runs/pm-replay-20261030T190256124954Z \
  --tasks 14 --method r1 --context drop --oracle-source lineage
```

For all 164 tasks, replace `--tasks 14` with `--set every`. Choose `stale`, `retract` or `both` to change history handling. These commands generate downstream code and evaluate it in Docker unless `--skip-eval` is supplied.

For the four-mode overnight schedule:

```bash
caffeinate -i python -u run_recovery_m5_night.py
```

The launcher selects existing full `recovery_m5_*` studies and reuses completed work. Running it on this submission may therefore skip already finished modes rather than create fresh studies. Use explicit recovery commands when a new independent run is required. Individual recovery runs support `--resume <study-folder>`; saved console output is under `runs/recovery_m5_logs/`.

## Read the evidence

| Saved file | Meaning |
| --- | --- |
| `study.json` | Task selection, configuration, task folders and progress/checkpoint state. |
| `trace.json` | Per-agent inputs, outputs, execution decisions and reported time/token measurements. |
| `lineage.json` | Recorded dependencies, producer/received hashes and delivery mismatch evidence. |
| `coder.py` / `coder_after_pm_injection.py` | Raw code before Test Engineer review, depending on the study. |
| `final.py` | Reviewed code returned by the Test Engineer. |
| `evaluation.json` | Official-suite status and individual additional-check outcomes for evaluated code artifacts. |
| `summary.csv`, `calls.csv`, logs | Run summaries and call-level records where produced by that runner. |
| `final_project_comparison.html` | Searchable comparisons, per-task checks, code changes, lineage and cost accounting. |

**Important interpretation:** a lineage mismatch means the received message differs from the recorded producer output; it does not independently establish a semantic bug. A completed model call does not mean the code passed tests. The baseline is a comparison condition, not an infallible correctness oracle.

Some historical replay checkpoints retain absolute paths from the original Mac. They are preserved for provenance. Reports work from the copied folder; resuming an old checkpoint at a different location can require adapting a separate checkpoint copy. Do not rewrite original evidence or hashes simply to make relocated paths look unchanged.

Recovery evaluations record code hashes and check names but not test-content hashes, and the recovery runner does not create a fresh recovery call graph. Missing or failed-call usage cannot be reconstructed from summaries alone.

## Results

The following results come from the supplied [`final_project_comparison.html`](mixed-model-baseline-v1/runs/final_project_comparison.html), using the four new Mac M5 recovery studies. Every condition covers **164 tasks** and **504 additional checks** per output.

- **Coder:** raw implementation before review.
- **Tester:** reviewed final implementation, not the Docker test runner.
- **All checks:** a task passes its official suite and every additional check.
- **Recovered:** previously baseline-passing tasks that failed after PM injection and pass all checks after recovery; **27 tasks** meet this eligibility criterion.

| Condition | Output | Official passed / 164 | All checks passed / 164 | Additional checks passed / 504 | Recovered / 27 |
| --- | --- | ---: | ---: | ---: | ---: |
| Original baseline | Coder | 128/164 | 124/164 | 458/504 | — |
| Original baseline | Tester | 133/164 | 130/164 | 466/504 | — |
| PM injection | Coder | 54/164 | 47/164 | 325/504 | — |
| PM injection | Tester | 118/164 | 114/164 | 437/504 | — |
| Recovery: remove faulty history | Coder | 128/164 | 124/164 | 458/504 | — |
| Recovery: remove faulty history | Tester | 133/164 | 130/164 | 466/504 | 27/27 |
| Recovery: keep faulty history | Coder | 80/164 | 75/164 | 379/504 | — |
| Recovery: keep faulty history | Tester | 119/164 | 113/164 | 443/504 | 7/27 |
| Recovery: withdrawal markers | Coder | 128/164 | 124/164 | 462/504 | — |
| Recovery: withdrawal markers | Tester | 131/164 | 128/164 | 464/504 | 27/27 |
| Recovery: remove history + notice | Coder | 127/164 | 123/164 | 457/504 | — |
| Recovery: remove history + notice | Tester | 129/164 | 126/164 | 459/504 | 25/27 |

All reported evaluations completed with **zero timeouts and zero unresolved checks**.

### Recorded model time and token usage

Times below are **summed model-call durations**, not full elapsed experiment time; Docker grading time is excluded. Baseline first-three and last-two rows partition the five-agent baseline total. Injection and recovery rows contain only the two newly executed downstream roles; the reused upstream cost is not charged again. Values cover the selected paired baseline attempts and recorded replay/recovery calls, not unrecorded failed requests or all historical baseline retries.

| Work measured | Model seconds | Total tokens |
| --- | ---: | ---: |
| Baseline: all five agents | 9,438.955 | 559,651 |
| Baseline: first three agents | 6,465.156 | 321,682 |
| Baseline: Coder + Tester | 2,973.799 | 237,969 |
| PM injection: Coder + Tester | 2,772.467 | 207,001 |
| Recovery, remove history: Coder + Tester | 4,877.032 | 237,969 |
| Recovery, keep history: Coder + Tester | 3,030.245 | 369,984 |
| Recovery, withdrawal markers: Coder + Tester | 2,925.129 | 264,125 |
| Recovery, remove history + notice: Coder + Tester | 3,163.275 | 257,831 |

### Findings

- **Upstream faults propagated strongly:** PM injection reduced raw Coder all-check passes from **124 to 47**.
- **Review corrected many errors:** under PM injection, reviewed final code passed all checks on **114 tasks**, compared with **47** for raw Coder code.
- **Removing faulty history was most effective in this run:** it recovered **27/27** eligible tasks and matched baseline totals at **130/164** final all-check passes.
- **Restoring the PM alone was insufficient when faulty history remained:** the stale-history condition recovered only **7/27** eligible tasks.
- **Withdrawal markers recovered 27/27 eligible tasks**, but overall final all-check passes remained **128/164**, indicating failures outside that eligible subset.
- **Adding a retraction notice did not improve on simple removal:** that condition recovered **25/27** eligible tasks and passed all checks on **126/164** final outputs.

These are observations from the recorded models, tasks, prompts and execution conditions. Passing the available tests does not prove correctness on every input, and a single run does not establish statistical significance or a universal ranking of recovery strategies.

## Acknowledgments

The fault-injection and defense study is inspired by [MAS-Resilience](https://github.com/CUHK-ARISE/MAS-Resilience) and uses [MetaGPT](https://github.com/FoundationAgents/MetaGPT), [Ollama](https://ollama.com/), [HumanEval](https://github.com/openai/human-eval) and Docker. This repository is an independent course-project adaptation, not an exact reproduction of the paper. Collaborator contributions to dependency tracking and recovery are preserved in the project code and original repository history.
