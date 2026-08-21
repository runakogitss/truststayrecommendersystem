# Final status — public repository and private professor handover

Package version: `2.1.0-complete-linkage-080`  
Frozen sample: **480 hotels / 100,111 reviews**

This public GitHub checkout contains the implementation and safe validation
records. The review-bearing frozen sample is part of the separate
private/self-contained professor handover package; it is intentionally not
committed here.

| Component | Status | Note |
|---|---|---|
| Frozen sample files | PRIVATE HANDOVER PACKAGE | Metadata-only documentation is retained in `data/frozen_research_sample/`; review-bearing files are excluded from this public checkout. |
| Review / feature / embedding counts | PASS | 100,111 / 100,111 / 100,111 |
| Embedding shape | PASS | 100,111 × 384 float32 |
| Supplied sample hashes | PASS | Existing validation report verifies all six bundled research-sample files |
| ABSA label separation | PASS | direct / proxy / none preserved |
| Semantic grouping implementation | PASS | Final method is complete-linkage cosine at 0.80 |
| Chaining prevention unit test | PASS | Synthetic A~B~C chain is not collapsed into one cluster |
| Threshold compliance unit test | PASS | Cluster members obey the configured complete-linkage bound in synthetic tests |
| Representative traceability | PASS | Unit-tested |
| Layer 1 boundary | PASS | No downstream judgement output |
| Complete Layer 1 production run | PASS | 480 hotels, 100,111 reviews, 480 full dossiers and 480 compact dossiers; 0 dossier failures |
| Full DeBERTa ABSA refresh | PASS WITH WARNINGS | 100,111/100,111 successful inference rows, 0 technical failures, 480 refreshed full dossiers and 480 refreshed compact dossiers |
| Frozen-cluster invariant after ABSA refresh | PASS | 100,111/100,111 memberships matched; 480 hotels and 83,686 semantic groups preserved |
| Layer 2 production run | COMPLETED | 480 hotels attempted; 439 technically accepted and 41 rejected by evidence-identifier provenance checks |
| Full public-repository test suite — 21 August 2026 | PASS | 48/48 tests passed in Python 3.12.7; warnings were limited to a third-party `pytest_freezegun` deprecation notice |

## Recorded production evidence

The completed Layer 1 run is recorded in
`outputs/frozen_research_run/validation/run_summary.json`. The completed full
ABSA refresh is recorded in
`outputs/frozen_research_run_full_absa/FULL_ABSA_VALIDATION.md` and
`ABSA_INFERENCE_PROVENANCE.json`. Layer 2 completion and rejection counts are
recorded under `layer2/audit/`.

The word `rerun` below describes an optional independent reproduction. It does
not mean the production run is outstanding.

## Optional examiner rerun

After installing `requirements.txt` in the private/self-contained professor
handover package, the runbook can:

1. validate the bundled 480-hotel / 100,111-review sample;
2. run Layer 1 with complete-linkage cosine clustering at 0.80;
3. write one full and one compact dossier for every successfully processed hotel;
4. validate dossier structure and review coverage;
5. generate submission manifests and diagnostics.

A validation failure should be treated as a failure, not bypassed.
