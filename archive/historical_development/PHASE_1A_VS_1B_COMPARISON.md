# Phase 1A versus Phase 1B comparison

Phase 1A remains frozen at commit `7a80d358371590d0005681c2da7d6d2652d2a95c`. Phase 1B is on branch `phase-1b-claim-compression` and uses the same three existing HotelRec smoke hotels: 337 reviews in total.

| Hotel | Reviews | Phase 1A whole-review clusters | Phase 1B claims | Phase 1B claim clusters | Singleton rate | Compact estimate | Rare cases |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bassenthwaite Lakeside Lodges | 217 | 188 | 1,666 | 511 | 59.8826% | 19,980 tokens | 74 |
| Westhaven Luxury Lodge | 52 | 50 | 475 | 213 | 62.4413% | 8,394 tokens | 23 |
| Hotel Vaishnavi | 68 | 67 | 565 | 229 | 61.1354% | 17,817 tokens | 83 |

## What changed

Phase 1A grouped whole reviews. Phase 1B preserves the original review and adds deterministic claim segmentation, claim-level MiniLM embeddings, within-hotel issue grouping, claim coverage mapping, rare-case retrieval, and a new representative-selection table. The Phase 1B full dossier contains 2,706 claims and 953 claim clusters across the three hotels.

The compact dossier is materially smaller than the full evidence while keeping a documented inline display sample. Bassenthwaite is represented by 94 inline claims including 74 rare cases; Westhaven by 43 including 23 rare cases; and Hotel Vaishnavi by 102 including 83 rare cases. The coverage fields explicitly record omitted inline claims and clusters. Full dossiers and membership files remain the source of complete verification.

## Traceability and ABSA

Every claim retains a short stable claim ID, full review ID, source row position, source text hash, claim text hash, source offsets, embedding row, cluster ID, and ABSA method label. Real DeBERTa coverage is 13.3641% for Bassenthwaite, 96.1538% for Westhaven, and 69.1176% for Hotel Vaishnavi. Proxy and missing rows remain separately labelled and are not presented as real model inference.

## Determinism and interpretation

Segmentation and clustering validation passed. Two complete offline Phase 1B builds produced identical SHA-256 inventories for 38 generated and validation files. The grouping threshold, rare-case rules, and display caps are provisional engineering settings. This comparison does not establish semantic correctness, severity, credibility, hotel quality, or a recommendation.

The machine-readable comparison is `outputs/validation/phase_1b/phase_1a_vs_1b_comparison.csv`; the manual semantic audit queue is `outputs/validation/phase_1b/semantic_coherence_manual_audit.csv`.
