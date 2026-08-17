# Methodology change record — semantic grouping

Date: 12 August 2026  
Status: **APPROVED FOR FINAL LAYER 1 HANDOVER**

## Scope

This record changes only the grouping method applied **after** the frozen MiniLM
embeddings. MiniLM, ABSA artefacts, the frozen 480-hotel / 100,111-review sample,
temporal features, and the Layer 1 boundary are unchanged.

## Development issue

The earlier development specification used hotel-level
`DBSCAN(metric="cosine", min_samples=1, eps=1-threshold)` at a nominal similarity
threshold of 0.85. With `min_samples=1`, DBSCAN reduces to single-linkage
connectivity, so a chain of locally similar reviews can join reviews that are
not mutually similar. This produced very large heterogeneous groups in the
validation analysis.

## Final decision

The final handover uses:

- embedding model: `sentence-transformers/all-MiniLM-L6-v2` (precomputed upstream)
- grouping unit: one hotel at a time
- distance: cosine
- algorithm: complete-linkage agglomerative clustering
- similarity threshold: **0.80** (`distance_threshold = 0.20`)
- deterministic ordering: review date, then review ID

Complete linkage was selected because it prevents the transitive chaining of the
earlier method. A cluster may only form while the complete-linkage distance bound
is satisfied. The code records the method and threshold in every dossier and
reports minimum pairwise similarity for diagnostic inspection.

## Interpretation boundary

A semantic group is an organisational device. It does not establish that a
reported event is true, severe, recurrent, independently corroborated, deceptive,
or representative of hotel quality.

## Version

Package version: `2.1.0-complete-linkage-080`  
Dossier schema version: `0.2.0`
