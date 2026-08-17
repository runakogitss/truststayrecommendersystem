# Final status — professor handover build

Package version: `2.1.0-complete-linkage-080`  
Frozen sample: **480 hotels / 100,111 reviews**

| Component | Status | Note |
|---|---|---|
| Frozen sample files | PASS | Bundled in `data/frozen_research_sample/` |
| Review / feature / embedding counts | PASS | 100,111 / 100,111 / 100,111 |
| Embedding shape | PASS | 100,111 × 384 float32 |
| Supplied sample hashes | PASS | Existing validation report verifies all six bundled research-sample files |
| ABSA label separation | PASS | direct / proxy / none preserved |
| Semantic grouping implementation | PASS | Final method is complete-linkage cosine at 0.80 |
| Chaining prevention unit test | PASS | Synthetic A~B~C chain is not collapsed into one cluster |
| Threshold compliance unit test | PASS | Cluster members obey the configured complete-linkage bound in synthetic tests |
| Representative traceability | PASS | Unit-tested |
| Layer 1 boundary | PASS | No downstream judgement output |
| Core methodology-related tests in this build environment | PASS | 20/20 targeted tests passed |
| Full pytest suite in this build environment | NOT FULLY EXECUTED | This sandbox cannot install `pyarrow`; 32 tests passed and parquet-dependent tests were blocked by the missing runtime dependency. `pyarrow==21.0.0` is pinned in `requirements.txt`. |
| Full 100,111-review dossier rerun after the methodology change | TO BE RUN BY PROFESSOR | `python scripts/run_handover.py` |

## Expected professor rerun

After installing `requirements.txt`, the runbook should:

1. validate the bundled 480-hotel / 100,111-review sample;
2. run Layer 1 with complete-linkage cosine clustering at 0.80;
3. write one full and one compact dossier for every successfully processed hotel;
4. validate dossier structure and review coverage;
5. generate submission manifests and diagnostics.

A validation failure should be treated as a failure, not bypassed.
