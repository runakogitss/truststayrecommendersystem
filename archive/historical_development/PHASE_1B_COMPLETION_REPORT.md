# Phase 1B completion report

## Decision

`PHASE_1B_PASS`

Phase 1B passed the deterministic implementation, data-boundary, alignment, coverage, compact-size, test, and repeated-build checks for the three existing HotelRec smoke hotels. The result is evidence preparation only; it does not authorize an LLM layer or academic judgment.

## Reproducibility anchor

- Repository: `<source repository at the time of the historical freeze>`
- Branch: `phase-1b-claim-compression`
- Phase 1B implementation commit: `9cc502b`
- Phase 1A frozen commit: `7a80d358371590d0005681c2da7d6d2652d2a95c`
- Phase 1B claim segmentation: `regex_claim_v1`
- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Embedding shape: `(2706, 384)`
- Seed: `20260725`
- Temporal cutoff: `2019-05-13`

## Scope and counts

Only the three existing Phase 1A smoke hotels were processed: 337 verified HotelRec reviews, segmented into 2,706 claims and 953 claim clusters. The full dossier counts are Bassenthwaite 1,666 claims/511 clusters, Westhaven 475/213, and Hotel Vaishnavi 565/229.

Compact estimates are Bassenthwaite 19,980 tokens and 100,746 bytes, Westhaven 8,394 tokens and 42,145 bytes, and Hotel Vaishnavi 17,817 tokens and 89,360 bytes. These estimates use the documented characters-divided-by-four method.

Rare-case register counts are Bassenthwaite 74, Westhaven 23, and Hotel Vaishnavi 83. The compact display is capped and its omissions are explicit; all claims remain in the full dossier and coverage mapping.

## Validation evidence

- `scripts/validate_phase_1b.py`: PASS; claim embedding alignment, source coverage, segmentation repeatability, clustering repeatability, full-to-compact containment, compact size, manual segmentation coverage, and 30 multi-cluster plus 30 singleton audit samples.
- `python3 -m pytest -q`: 16 passed, 32 non-failing deprecation warnings.
- Repeated complete offline build: PASS; SHA-256 inventories matched for all 38 generated/validation files.
- Manual semantic audit: queue generated with 30 multi-claim clusters, 30 singleton clusters, rare cases, and contradictory rating/sentiment clusters. Human fields remain blank.
- No LLM rubric call was made.

## Reusable outputs

Use the Phase 1B claim embedding output, cluster membership and summaries, full/compact dossiers, temporal summaries, representative selections, coverage mapping, and method-labelled ABSA fields for the three smoke hotels. The Phase 1B NPZ is a new claim-level artifact and must not be confused with the frozen Phase 1A review-level MiniLM NPZ. Real DeBERTa, proxy, and no-result ABSA rows remain separate.

## Boundaries and next action

No Booking.com, OTT, MAiDE, synthetic attack-pool, or other out-of-scope data were processed. No source data or Phase 1A dossier was modified. Before any later LLM-layer work, manually review and complete the audit queue and separately freeze the academic rubric.
