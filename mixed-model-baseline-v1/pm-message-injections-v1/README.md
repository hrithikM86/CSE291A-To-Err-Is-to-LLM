# PM message injections for the mixed-model baseline

This package supplies **164 task-specific PM message substitutions** for the completed study `baseline-20261030T082523974587Z`. It contains no experiment runner, new tests, or newly generated downstream code. No Ollama/MetaGPT inference or generated-code execution was performed while preparing it.

## Files

- `tasks/task-NNN/project_manager_original.txt`: byte-for-byte original PM output.
- `tasks/task-NNN/project_manager_corrupted.txt`: the replacement PM message to deliver to the Coder.
- `tasks/task-NNN/product_manager.txt` and `architect.txt`: unchanged upstream output copies, for linking the replay to the original run.
- `tasks/task-NNN/coder_payload.json`: an optional ready-to-read JSON payload matching the original `coder_input.json["payload"]` format. Its keys are `original_specification`, `previous_stage`, and `previous_artifact`. Only `previous_artifact` differs from the saved baseline payload.
- `tasks/task-NNN/project_manager.diff`: standard before/after diff of the PM text.
- `manifest.json`: task IDs, source attempts and paths, message hashes, source lineage/trace hashes, unchanged test-file hashes, intended edits, and static coverage notes. This is analysis metadata, NOT an agent prompt.
- `INDEX.csv`: one row per task for locating original, corrupted, and payload files.
- `CHANGES.md`: full task-by-task explanation, baseline observations, coverage limits, and diffs.
- `CHANGES.html`: offline expandable diff viewer. Original removed lines are **green** and replacement lines are **red**; this intentionally differs from conventional diff colors. The full analysis is in `CHANGES.md`.
- `VALIDATION.json`: archive-integrity and source-handoff checks. These checks validate data preparation, not program correctness or successful error propagation.

## Local replay handoff

Extract the ZIP into its own folder next to your existing baseline project. Keep the original baseline study and export unchanged.

For each manifest entry:

1. Locate its original baseline attempt using `source_folder`. That path is relative to the export root; for your live baseline study remove the leading `tasks/` (for example, `task-000/attempt-1`). Do not assume all tasks used attempt 1.
2. Reuse the original specification, Product Manager, and Architect records without calling those agents again. Preserve the original PM generation record as well.
3. Deliver the contents of `project_manager_corrupted.txt` as the Coder's `previous_artifact`, or load the supplied `coder_payload.json`. Reuse the original Coder system messages and model settings from the saved `coder_input.json`. The supplied JSON is a payload, not a full provider request or complete runner configuration.
4. Run the Coder locally with `qwen2.5-coder:7b`. Pass its newly generated code to the Test Engineer with the unchanged original specification and the original `qwen2.5:7b` settings and system messages.
5. Save the new records in a new study folder. Preserve the reused upstream lineage and distinguish the PM's original output from its substituted delivered output. Record the intervention and both message hashes; do not silently overwrite the original PM lineage evidence or claim the baseline PM model generated the replacement.
6. Evaluate raw attacked Coder code and reviewed final code against the **same existing** official HumanEval suite and additional test files that graded the baseline. Use Docker through the existing local evaluation code. The manifest records the dataset/test hashes for matching. No tests are bundled or changed here.

The recorded chain is reused Product Manager → reused Architect → substituted PM message → new Coder → new Test Engineer. The original Coder payload directly supplies only the specification and preceding PM artifact: do not append the older agents' full outputs to that payload, since that would change the experiment's input context.

Do not send the manifest, analysis report, diff, expected answers, or original/corrupted pair together to an agent. Only the replacement PM text belongs in `previous_artifact`. Keep the source specification and system prompts unchanged even when they conflict with the PM message: whether the Coder rejects the instruction is part of the observation.

## What these messages establish

These are assistant-authored, specification- and test-aware semantic interventions, not a claim to reproduce the paper's automated injector. Each task has its own required behavior. Related PM clauses and embedded examples were edited or omitted where they conflicted; the before/after diffs document every byte-level message change. Some unrelated original PM defects are retained, and some broader replacement clauses can resolve an existing ambiguity or defect. The task-specific baseline notes flag known interactions. Do not interpret the messages as clean single-line mutations or assume all subsequent failures were caused by them.

Static reasoning identifies one potentially exposing existing additional check for 147 tasks. For 17 tasks the supplied additional checks do not isolate the intended fault; these gaps are listed explicitly in the manifest and report. The official suite may expose faults missed by those cases, but its exposure has not been evaluated here. There are no measured injection-success, adoption, correction, or persistence rates yet.

The baseline is the comparison condition, not guaranteed-correct ground truth. Use the specification and existing test oracle for correctness. Separate pre-existing failures from newly introduced failures and distinguish reviewer corrections from changes that merely pass the available tests.

## Validation performed

- All 2,970 files indexed by the uploaded export's manifest matched their SHA-256 hashes.
- All 164 selected source attempts are marked completed; their five saved role outputs match their trace messages and original handoffs.
- The source graphs contain 820 model-call nodes across the selected latest attempts and 3,116 verified dependency/configuration edges. Verified means matching transmitted content, not correct reasoning.
- Original PM, Product Manager, and Architect copies are byte-identical to their sources.
- Every replacement differs from its original, retains the source message's function declaration wording where present, and maps to the same task and authoritative specification.
- Every prepared Coder payload changes only `previous_artifact`.
- Existing dataset and 164 test files (504 additional cases) were read and hashed; none was modified or regenerated.

The original study reports 824 model calls across all saved attempts. This is compatible with 820 calls in the latest exported attempts; preparation does not rewrite historical metrics or treat older interrupted work as new calls.
