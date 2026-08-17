# Technical audit

Audit scope: the supplied `TrustStay_Evidence_Pipeline_Dissertation_20260725`
repository, the supplied Fairmont Dallas Layer 1 ZIP, and the final handover
tree in this package.

## What currently works

- The existing unit/Phase 1B suite passed 16 tests before changes.
- The final handover suite passes 25 tests.
- The locked 500K verification passed with 500,000 rows, 2,346 hotels,
  MiniLM shape `(500000, 384)`, and the recorded source hashes.
- The verified ABSA counts are 103,021 `deberta_absa`, 396,239
  `distilled_proxy`, and 740 `none`; labels remain separate.
- Complete-hotel sampling is deterministic: the supplied run selected 480
  hotels and 100,111 reviews for target 100,000 with seed 20260812.
- The Fairmont regression passed all structural checks: 2,550 IDs, source
  joins, text/date/rating hashes, ABSA methods, embedding flags, valid full and
  compact dossiers, temporal coverage, representative traceability, and
  provenance hashes.

## Incomplete or blocked

- The repository does not contain a validated raw-to-ABSA preprocessing adapter.
  It reuses method-labelled verified ABSA outputs in handover mode.
- MiniLM inference is also not rerun from raw text in handover mode; the locked
  `sentence-transformers/all-MiniLM-L6-v2` artifact is reused.
- A full 100K dossier build was not completed in this workspace. The sample
  definition and Fairmont end-to-end build were executed; 100K runtime and
  disk totals remain machine-dependent.
- Layer 2 LLM interpretation, academic scoring, bands, severity and
  recommendations are deliberately outside this package.

## Obsolete, duplicated or historical material

- Phase 1B claim compression files and scripts are retained as historical or
  optional development material. They are not invoked by the final Layer 1
  handover command and are not required for review-level dossiers.
- The original repository contains older generated manifests, macOS metadata
  files, and development outputs. The final tree excludes metadata files and
  regenerates portable root manifests.
- `validate_dossiers.py` remains as a legacy smoke validator; the handover
  path uses `validate_handover_outputs.py` with explicit output arguments.
- The supplied Fairmont directory omitted `source_reviews.csv` even though its
  README and ZIP manifest described it. The source file is present in the
  supplied ZIP and is unpacked into this package.

## Code/documentation inconsistencies found and fixed

- `configs/paths.example.yaml` contained machine-specific `/Volumes/...`
  paths. It now uses paths relative to the config file and documents external
  locked artifacts.
- Input validation hardcoded 500,000 rows and `(500000, 384)`, which blocked
  smaller/derived handover scopes. Validation now infers the row count and
  dimension while still checking index/NPZ alignment; an expected shape can be
  supplied when required.
- The README's `create_submission_manifest.py` reference was not actually
  missing in this snapshot, but the old script only wrote a path-heavy JSON
  list. It has been replaced with JSON, CSV and Markdown submission records.
- Several legacy Phase 1A package scripts used absolute paths. They now require
  operator-supplied output/input arguments and are clearly legacy.
- Feature-index loading filtered only after reading the entire table. Handover
  hotel selection now uses Parquet predicate filtering where possible.
- The old MiniLM loader materialised the complete NPZ embedding matrix. Handover
  mode now creates a read-only memory-mapped cache for `emb.npy`, preserving
  exact rows and values.
- The supplied Fairmont historical summary contains downstream fields such as
  `quality_score`, `score_band`, `risk_grade`, and recommendation eligibility.
  Those fields are retained only as reference evidence and are not consumed by
  final Layer 1 code.

## Scaling risks

- `DBSCAN(metric='cosine', algorithm='brute')` remains the intended method and
  is executed independently per hotel. A hotel with a very large review count
  can still require quadratic pairwise work.
- The 500K input/index is read during full validation; this is appropriate for
  a one-time locked-input check but should not be repeated per hotel.
- Full dossiers contain review text and can be large. Compact dossiers are
  projections for downstream transport, not evidence deletion.
- The one-time NPZ-to-NPY cache requires disk approximately equal to the
  embedding member size. The Fairmont run created an approximately 732 MB cache
  for the supplied 500K/384 archive; it was removed from the packaged outputs.

## Researcher approval points

See `METHODOLOGY_DECISIONS_REQUIRED.md`. In particular, do not change the
semantic threshold, claim the proxy ABSA rows are direct inference, or add
score/severity/band logic to Layer 1 without a new researcher-approved frozen
method record.
