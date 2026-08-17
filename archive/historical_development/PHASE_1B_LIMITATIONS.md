# Phase 1B limitations and boundaries

Phase 1B is deterministic evidence preparation for the three existing HotelRec smoke hotels. It is not a truth, quality, severity, credibility, safety, recurrence, recovery, deterioration, score, band, recommendation, or LLM-judgment layer.

## Claim segmentation

- Segmentation uses `regex_claim_v1`, with sentence boundaries and guarded splits for contrast and semicolon clauses.
- The rules are engineering heuristics, not a validated linguistic or semantic theory. The retained source offsets and original review text allow manual correction without losing traceability.
- Causal connectives are deliberately kept in one claim to reduce context loss; this can under-segment some reviews.

## Embeddings and grouping

- Phase 1B generated new claim-level MiniLM embeddings for 2,706 claims from 337 reviews. The existing Phase 1A review-level NPZ was not reused for claim rows and was not modified.
- The embedding model is `sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions, CPU inference, fixed seed `20260725`.
- Agglomerative average-linkage cosine clustering uses threshold `0.50`. This is a provisional retrieval grouping, not an academic validation of issue taxonomy.
- Possible duplicates and near-duplicates remain visible; cluster membership is not independent corroboration.

## Compact display

- Full dossiers retain every claim, source review text, source offsets, hashes, cluster membership, and coverage mapping.
- Compact dossiers retain all rare-case claims and a deterministic display sample. Inline major-cluster display is capped at 20 clusters and one representative claim per displayed cluster; inline cluster summaries omit clusters with fewer than five claims. Omitted evidence remains addressable in the full dossier, membership files, and coverage mapping.
- Token estimates use serialized JSON characters divided by four; they are planning estimates, not tokenizer counts.

## ABSA and temporal scope

- ABSA labels retain their source method. Real DeBERTa rows, proxy rows, and no-result rows are not conflated.
- Claim-level ABSA support is review-level evidence copied to claims; it is not new claim-specific model inference.
- Temporal summaries use the fixed cutoff `2019-05-13`; no post-cutoff data are used in window counts. Date precision is preserved.

## Audit boundary

- The manual audit CSV is prepared with blank human fields. It is an audit queue, not an auto-completed semantic-quality judgment.
- No LLM rubric was called. Future work must review the manual audit and freeze any academic rubric separately.
