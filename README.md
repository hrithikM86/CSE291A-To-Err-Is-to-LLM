# CSE291A: To-Err-Is-to-LLM

Error propagation and recovery in a five-agent MetaGPT pipeline:
**Product Manager → Architect → Project Manager → Coder → Test Engineer**.

This submission contains only `mixed-model-baseline-v1/` and repository documentation.
All saved runs, logs, tests, messages, lineage, metrics and reports are included.
The original research repository is https://github.com/hrithikM86/To-Err-Is-to-LLM.

## Start here

- `mixed-model-baseline-v1/runs/final_project_comparison.html`: final comparison, if generated locally before export. Download/open the HTML in a browser; GitHub does not render arbitrary HTML reports as a live dashboard.
- `mixed-model-baseline-v1/README.md`: scripts, run commands and portability limitations.
- `mixed-model-baseline-v1/SUBMISSION_FILES.json`: source-to-copy SHA-256 manifest.

The Coder uses `qwen2.5-coder:7b`; the other four agents use `qwen2.5:7b`.
The Test Engineer returns reviewed code; an independent Docker evaluator runs tests.

## Main findings from the saved Mac runs

Final outputs passing official and every additional check:
- Baseline: 130/164; PM injection: 114/164.
- Recovery removing faulty history: 130/164; 27/27 injection-broken tasks recovered.
- Recovery retaining faulty history: 113/164; 7/27 recovered.
- Recovery with withdrawal markers: 128/164; 27/27 recovered.
- Recovery removing history plus a retraction notice: 126/164; 25/27 recovered.

These counts concern the saved experiment, not a guarantee of future rerun results.
Model generation completion and test correctness are separate measures.
