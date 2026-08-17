# Full DeBERTa ABSA Refresh Validation

**Execution state:** `NOT RUN`

This is the implementation-time preflight record. The full 100,111-review inference was intentionally not executed. The runner will replace the report in `outputs/frozen_research_run_full_absa/FULL_ABSA_VALIDATION.md` after the professor's full CUDA run.

Corrected adapter smoke result: `PASS WITH WARNINGS` on 8 reviews, with 8 successful inferences, 36 extracted aspect terms, 0 technical failures, and 0 frozen-cluster membership changes. The smoke contained 0 zero-aspect reviews naturally; this is not treated as a failure.

The aspect extractor is `yangheng/deberta-v3-base-end2end-absa`; `yangheng/deberta-v3-base-absa-v1.1` is used only for the documented low-extraction-score sentiment refinement. The hotel lexicon is not an extraction gate.

Expected full-run checks:

- expected rows: `100,111`;
- expected hotels: `480`;
- expected frozen semantic groups: `83,686`;
- expected membership changes: `0`;
- no MiniLM embedding regeneration;
- no clustering invocation;
- no proxy fallback; and
- explicit checkpointed results for every review ID, including failures.

Use `FULL_ABSA_RERUN_README.md` for the Windows smoke-test, full-run, resume, and validation commands.
