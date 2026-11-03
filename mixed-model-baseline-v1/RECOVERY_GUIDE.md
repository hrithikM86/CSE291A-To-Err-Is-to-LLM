# Recovery guide: mixed models

How to run recovery on the mixed-model study, in which every role uses
`qwen2.5:7b` except the Coder, which uses `qwen2.5-coder:7b`.

**Use R1.** It is the recovery method in the pipeline. R3 is a separate test,
described at the end.

## How R1 works

The fault edits the Project Manager's checklist on its way to the Coder.
Recovery starts from the saved 164-task study
`runs/pm-replay-20261030T190256124954Z`, which is in the repository.

```text
Product Manager -> Architect -> Project Manager -> Coder -> Test Engineer
     kept             kept       restored clean     rerun       rerun
```

1. Lineage finds the stage whose delivered output differs from what it produced,
   and every later stage that used it.
2. The clean checklist is restored from the baseline. Its hash must match the
   Project Manager's recorded output, or recovery stops.
3. The Coder and Test Engineer rerun: 2 model calls instead of 5.
4. The recovered code is tested in Docker. Agents never see the tests.

## One-time setup

You need Docker Desktop, Ollama and Python 3.10 or later. Then run:

```powershell
ollama pull qwen2.5:7b
ollama pull qwen2.5-coder:7b
docker pull metagpt/metagpt@sha256:65e94d386a8aba2a7d9cb99e171d0897f9fccc2f3b1e4c61307fc1a2807b098b
docker tag metagpt/metagpt@sha256:65e94d386a8aba2a7d9cb99e171d0897f9fccc2f3b1e4c61307fc1a2807b098b metagpt/metagpt:latest
docker pull python:3.11-slim
```

This pins MetaGPT 0.8.1, the version the study used. `ollama list` should show
IDs `845dbda0ea48` for `qwen2.5:7b` and `dae161e27b0e` for `qwen2.5-coder:7b`.
Other model versions run, but their outputs will differ from the saved results.

## Each new PowerShell window

Start Docker Desktop and Ollama, then:

```powershell
cd "<repo>\meta-gpt2\mixed-model-baseline-v1"
function Docker-Py { docker run --rm -v "${PWD}:/work" -w /work --add-host=host.docker.internal:host-gateway metagpt/metagpt:latest python @args }
function Latest($p) { (Get-ChildItem runs -Directory -Filter $p | Sort-Object CreationTime | Select-Object -Last 1).FullName }
function Score($p) { Import-Csv "$(Latest $p)/summary.csv" | Group-Object baseline_final_pass, attacked_final_pass, recovered_final_pass | Select-Object Name, Count }
function Progress { Get-ChildItem runs -Directory -Filter "recovery-r1-*" | ForEach-Object { $j = Get-Content "$($_.FullName)/study.json" -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json; if ($j) { "{0}: {1} of {2}" -f $_.Name, @($j.tasks.PSObject.Properties | Where-Object { $_.Value.status -eq "completed" }).Count, @($j.indices).Count } } }
```

## Run R1

Try one task first; it takes about 5 minutes:

```powershell
Docker-Py recover_pm.py --tasks 14 --method r1 --oracle-source lineage --skip-eval --config config/config2.docker.yaml
python recover_pm.py --evaluate-only (Latest "recovery-r1-2*")
Score "recovery-r1-2*"
```

Expected: the task prints `completed` with `'llm_calls': 2`, and `Score` shows
`True, False, True` with count 1.

Then run all 164 tasks. This took 7.3 hours on a CPU-only laptop, so keep it
plugged in and stop it from sleeping.

```powershell
Docker-Py recover_pm.py --set every --method r1 --oracle-source lineage --skip-eval --config config/config2.docker.yaml
python recover_pm.py --evaluate-only (Latest "recovery-r1-2*")
Score "recovery-r1-2*"
```

`--set broken` runs only the 27 tasks the fault broke. Check progress from a
second window with `Progress`. If a run stops, finished tasks are kept; continue
it, then evaluate:

```powershell
Docker-Py recover_pm.py --resume "runs/<run folder>" --skip-eval --config config/config2.docker.yaml
```

## Output

Each run creates `runs/recovery-r1[-mode]-<timestamp>/`:

```text
summary.csv         one row per task; scores stay blank until evaluation ends
study.json          settings and status of every task
task-NNN/           trace.json, coder.py, final.py, evaluation.json
```

The key `summary.csv` columns are `baseline_final_pass`, `attacked_final_pass`,
`recovered_final_pass`, `llm_calls` and `stages_with_poison_in_input`. A program
passes only if the official HumanEval test and every additional check pass.
`Score` output for the full R1 run:

```text
Name                Count
True, False, True      27    broken by the fault, recovered
True, True, True      103    passed throughout
False, True, False     11    baseline fails; attacked code passed
False, False, False    23    fails in all three
```

R1 recovered all 27 broken tasks, with no regressions, using 328 calls. That puts
the study at 130 of 164, the baseline's own score.

## R3: a separate test

R3 controls what the rerun agents can see. It is not part of the main flow,
because roles in this pipeline keep no memory, so R1 already gives them a clean
input. R3 matters in frameworks where agents keep conversation history.

Every R3 run is R1 plus an input mode. R1 restores the clean checklist and reruns
the Coder and Test Engineer; the mode decides what else those two agents see. To
simulate memory, the faulty run's history is copied from the saved traces into
the rerun input, and each mode handles it differently:

| Mode | Added to the rerun input | Recovered, 27 broken tasks |
|---|---|---|
| `stale` | The faulty history unchanged: no R3, the comparison | 9 |
| `drop` | Nothing: the same run as R1 | 27 |
| `retract` | The history with faulty items replaced by a withdrawn marker | 27 |
| `both` | A notice that the earlier checklist was faulty | 26 |

A poison check stops the run if faulty text reaches an input, except in `stale`.
Without R3, 18 of 27 tasks stayed broken. The miss in `both`, task 123, is a new
bug, not the injected rule.

Each mode takes about 1 to 4 hours:

```powershell
foreach ($mode in @("stale","retract","both")) {
  Docker-Py recover_pm.py --set broken --method r1 --context $mode --skip-eval --config config/config2.docker.yaml
}
foreach ($p in @("recovery-r1-stale-2*","recovery-r1-r3retract-2*","recovery-r1-r3both-2*")) {
  python recover_pm.py --evaluate-only (Latest $p)
  Score $p
}
```

## Anagha's saved results

All in `runs/`, run on 2026-11-02 and 03. Each run has a `summary.csv` and a
`-raw.zip` with its traces, code and test results.

| Run | Folder | Tasks | Recovered |
|---|---|---|---|
| R1 alone, the `drop` mode | `recovery-r1-20261102T175724890919Z` | All 164 | 27 of 27 broken, 130 of 164 overall |
| R1 + `stale`: faulty memory left in, no R3 | `recovery-r1-stale-20261103T014352801564Z` | 27 broken | 9 |
| R1 + R3 `retract`: memory kept, faulty items withdrawn | `recovery-r1-r3retract-20261103T032553968424Z` | 27 broken | 27 |
| R1 + R3 `both`: memory removed, retraction notice added | `recovery-r1-r3both-20261103T042633269919Z` | 27 broken | 26 |

There is no R3-only run, because R3 only changes the input of R1's reruns.
Extract a zip outside `runs/` to inspect it.

## Before committing

Docker rewrites generated files. Revert them and delete new logs:

```powershell
git checkout -- metagpt/tools/schemas
git clean -n -- logs
git clean -f -- logs
```

`git clean -n` shows what will be deleted; committed logs are kept. Commit each
run's `summary.csv` and a zip of its folder, not the task folders.
