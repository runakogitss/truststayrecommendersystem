# Changelog

## 1.0.0-phase-1b — 2026-07-25

- Froze Phase 1A at commit `7a80d358371590d0005681cda7d6d2652d2a95c`.
- Created branch `phase-1b-claim-compression` for claim-level evidence compression.

## 1.1.0-phase-1b — 2026-07-25

- Added deterministic regex claim segmentation, 384-dimensional claim-level MiniLM embeddings, neutral claim clustering, rare-case retrieval, representative selection, fixed-cutoff temporal summaries, coverage mapping, and full/compact Phase 1B dossiers for 337 HotelRec smoke reviews.
- Added repeated-build determinism evidence, manual-audit queues, Phase 1A/1B comparison, completion and limitations reports, and Phase 1B SHA-256 manifest tooling.

## 1.2.0-phase-1a-chat-packages — 2026-07-25

- Verified and inserted the researcher-supplied final academic rubric with SHA-256 `b000c9632c9dfcb4c7e831062985e83e6e9911eb1351c019635e1396802bf485`.
- Regenerated and validated the master and three single-hotel Phase 1A chat smoke-test ZIPs; status is `READY_FOR_LLM_SMOKE_TEST`.

## 0.1.0 — 2026-07-25

- Created the dissertation repository and provenance boundary.
- Added deterministic configuration and source-path examples.
- Added verified-source validation and MiniLM access interfaces.
- Added rubric-neutral evidence schemas and methodology documentation.

## 0.6.0 — 2026-07-25

- Implemented verified loaders and immutable MiniLM row access.
- Implemented deterministic within-hotel semantic clustering and neutral representatives.
- Implemented factual temporal summaries and visible duplicate/near-duplicate indicators.
- Implemented full and compact HotelRec evidence dossiers.
- Added smoke validation for three exact HotelRec hotels and 11 passing tests.

## 0.2.0 — planned

- Verified loaders and source validation results.

## 0.3.0 — planned

- Deterministic within-hotel semantic clustering.

## 0.4.0 — planned

- Factual temporal summaries.

## 0.5.0 — planned

- Full and compact dossier generation.

## 0.6.0 — planned

- Development validation and reproducibility evidence.
# 1.0.0-handover — 2026-08-12

- Added `TECHNICAL_AUDIT.md`, `HANDOVER_RUNBOOK.md`, `FINAL_STATUS.md`, and
  `METHODOLOGY_DECISIONS_REQUIRED.md`.
- Replaced machine-specific example paths with portable, config-relative paths.
- Added deterministic complete-hotel sampling for the approximately 100K
  handover scope; the executed definition is 480 hotels / 100,111 reviews.
- Generalised locked-input validation so it checks actual dimensions while
  preserving strict ID/order/hash/method checks.
- Added disk-backed memory-mapped MiniLM access for handover runs and Parquet
  predicate filtering for selected hotels.
- Replaced the minimal submission manifest with JSON, CSV, and Markdown output.
- Added source-input validation, Fairmont reference tests, Fairmont regression,
  output validation, and portability-focused tests.
- Preserved the existing Phase 1B material as historical/optional; it is not
  part of the final Layer 1 handover execution path.
