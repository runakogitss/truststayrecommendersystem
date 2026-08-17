# Semantic grouping method selection — validation summary

This is the decision record for the grouping stage **after MiniLM**. MiniLM was
not retrained or replaced.

The frozen 100,111-review / 480-hotel embedding set was compared hotel-by-hotel
using the earlier development configuration and three complete-linkage
thresholds. The selection criterion was semantic-grouping behaviour, not the
resulting TrustStay score or band.

| Method | Similarity threshold | Singleton share of reviews | Largest cluster |
|---|---:|---:|---:|
| Development DBSCAN (`min_samples=1`) | 0.85 | 86.9% | 706 |
| Complete linkage | **0.80** | **72.8%** | **19** |
| Complete linkage | 0.85 | 90.1% | 12 |
| Complete linkage | 0.90 | 98.5% | 5 |

The development DBSCAN configuration allowed transitive chaining: locally
similar reviews could connect reviews that were not mutually similar. Complete
linkage removes that mechanism. The 0.85 and 0.90 complete-linkage thresholds
were judged too sparse for useful evidence organisation; 0.80 retained a
meaningful amount of grouping while preserving the complete-linkage bound.

The final frozen decision is therefore **hotel-level complete-linkage cosine
clustering at 0.80 similarity**.

Optional reproducibility command:

```bash
python scripts/compare_grouping_methods.py
```

This comparison script is an audit aid; the normal professor rerun uses only the
frozen final method in `configs/evidence_pipeline.yaml`.
