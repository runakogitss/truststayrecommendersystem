# Full DeBERTa ABSA Refresh Validation

> **Historical preflight record.** The `NOT RUN` state below applies only to
> the earlier implementation-time checkpoint represented by this file. The
> subsequent production refresh was completed for all 100,111 reviews. The
> authoritative completed record is
> `outputs/frozen_research_run_full_absa/FULL_ABSA_VALIDATION.md`.

**Execution state:** `NOT RUN`

At this historical checkpoint, the full 100,111-review inference had not yet
been executed. This record is retained only to preserve the development
sequence; it is not the current production status.

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
