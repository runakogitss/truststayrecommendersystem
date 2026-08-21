# Changelog

## 2.1.0 final-submission clarification — 21 August 2026

- Recorded the completed 480-hotel/100,111-review Layer 1 run instead of the
  superseded pre-run status.
- Recorded the completed full DeBERTa ABSA refresh: 100,111/100,111 successful
  inference rows, 0 technical failures, 480 full dossiers and 480 compact
  dossiers, with the frozen cluster invariant preserved.
- Recorded the Layer 2 production outcome: 439 technically accepted hotels and
  41 validator rejections.
- Removed the obsolete pre-run GPU patch bundle from the live release, retained
  its validation state as a clearly labelled historical preflight record, and
  kept a current optional-rerun guide at the repository root.
- Clarified the public-code/private-data boundary and scrubbed personal local
  path strings from public audit metadata.
- Revalidated the public repository: 48/48 tests passed on 21 August 2026.

## 2.0.0-frozen-research-run

Restructured as a self-contained, examiner-rerunnable Layer 1 handover.

### Self-containment
- Added `data/frozen_research_sample/`: reviews, features, embeddings, sample
  definition, hashes and upstream provenance for the frozen run. The examiner no
  longer needs the external locked corpus or any absolute path.
- Added `scripts/export_frozen_sample.py` (researcher-only) to cut that bundle
  from the external artefacts, with export-time self-validation.
- Added `scripts/run_handover.py`: one command, four stages, fails loudly.

### Engineering fixes (no methodology change)
- **Clean-run output-directory failures.** All writers now create their
  directories. The previous `verify_environment.py` crashed on a clean copy
  because `outputs/development/` did not exist; that script is retired.
- **Scripts returning success on failure.** Every script now exits non-zero with
  a printed reason. Per-hotel build failures are recorded and fail the run.
- **Machine-specific absolute paths.** Removed. Paths resolve from the package
  root or from the config file's own directory. Enforced by
  `tests/test_portability.py`.
- **Path-dependent hash verification.** Removed the requirement that a stored
  artefact path string-equal the operator's configured path, which made the
  package unrunnable outside the original directory layout. Integrity is now
  established by SHA-256 against a manifest that travels with the data.
- **Substring dataset-name matching.** Replaced with whole-token matching
  (`ott` no longer matches `scott`).
- **Misleading validation filenames.** Fairmont-specific development outputs are
  isolated under `archive/`; run outputs are written under
  `outputs/frozen_research_run/validation/` with explicit names.
- **Dependencies.** Pinned and complete; the suite now runs from
  `requirements.txt` alone with no undeclared plugin.
- **Manifest generation.** Rewritten to emit JSON, CSV and Markdown covering
  environment, configuration, input hashes, execution record and output hashes.
- **Compaction.** Rewritten from O(clusters x reviews) to O(n) and proven
  output-identical by `tests/test_compaction_equivalence.py`.
- **`_jsonable`.** No longer raises on array-valued cells.
- **Hotel filenames.** Sanitised and disambiguated by hash suffix.
- **`.gitignore`.** No longer excludes validation reports, which are evidence.

### Validation
- New alignment triple check: reviews / features / embeddings must agree on
  count, identity and order, with no truncation and no out-of-scope data.
- New text-hash chain check: `text_sha256` must match `review_text`.
- New ABSA label/status consistency check.
- Row counts and embedding dimensions are inferred, not hardcoded.

### Diagnostics (report-only)
- Added `src/truststay_evidence/diagnostics.py` and
  `scripts/cluster_diagnostics.py`: cluster-size distribution, large-cluster
  chaining detection, representative traceability, minority-evidence retention
  and compaction ratio.

### Tests
- 43 tests, including an end-to-end run over a synthetic fixture and a
  byte-identical rerun check. Previous suite: 25, of which 6 covered code that
  was not in the execution path.

### Isolation
- Phase 1B claim compression, Phase 1A chat-package builders, the Fairmont
  reference package and historical reports moved to
  `archive/historical_development/`. Nothing in `src/` or `scripts/` references
  them; enforced by test.

### Explicitly not changed
- Similarity threshold, `min_samples`, cluster unit, representative-selection
  rule, compaction selection, temporal windows, ABSA labelling. See
  `METHODOLOGY_DECISIONS_REQUIRED.md` and `LIMITATIONS.md`.

## 2.1.0 — 12 August 2026 — final semantic grouping decision

- Replaced live `DBSCAN(min_samples=1)` semantic grouping with deterministic
  hotel-level complete-linkage agglomerative clustering using cosine distance.
- Frozen semantic similarity threshold changed from 0.85 (development DBSCAN)
  to 0.80 (final complete-linkage method).
- Added explicit method provenance to dossiers/manifests.
- Added minimum pairwise similarity diagnostics for generated semantic groups.
- Replaced chaining-preservation tests with tests that reject transitive chaining
  and assert the complete-linkage threshold bound.
- MiniLM embeddings, ABSA artefacts, frozen sample, temporal logic and Layer 1
  boundary are unchanged.
