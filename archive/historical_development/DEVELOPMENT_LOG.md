# Development log

## 2026-07-25 15:40 — Phase 1A freeze and Phase 1B branch

### Objective
Freeze the audited Phase 1A foundation before beginning claim-level evidence compression.

### Files inspected
Current Git state, Phase 1A full and compact smoke dossiers, Phase 1A audit package, and existing test suite.

### Changes made
Created branch `phase-1b-claim-compression` and added `PHASE_1A_FREEZE_RECORD.md`.

### Validation performed
Confirmed clean Phase 1A state at commit `7a80d358371590d0005681c2da7d6d2652d2a95c`; reran existing tests with 11 passing; recorded hashes for all six Phase 1A dossiers.

### Result
Phase 1A is frozen for comparison. No Phase 1A dossier or verified source file was modified.

### Known limitations
Phase 1A whole-review clustering is retained for comparison only; Phase 1B will test claim-level grouping on the 337-review smoke scope.

### Next permitted step
Implement deterministic sentence/claim segmentation without LLM inference.

## 2026-07-25 — Repository creation and provenance setup

### Objective
Create the dissertation evidence-preparation repository around the verified HotelRec V3.4.1 outputs.

### Files inspected
The attached task specification and the prior verification package. Source paths and hashes are recorded in `DATA_PROVENANCE.md`.

### Changes made
Created the repository structure, package skeleton, configuration examples, schemas, documentation, and provenance-aware validation interfaces.

### Validation performed
Confirmed the workspace did not already contain this repository. Confirmed installed Python and package versions before implementation.

### Result
Repository scaffolding is present. No original TrustStay file was modified and no model inference was run.

### Known limitations
The academic rubric and final LLM layer are intentionally unspecified.

### Next permitted step
Run environment verification and strict verified-input checks, then build a 2–3 hotel smoke sample.

## 2026-07-25 15:18 — Verified loaders, deterministic dossiers, and smoke validation

### Objective
Implement the rubric-neutral evidence-preparation layer and execute the required initial validation.

### Files inspected
Verified input, reusable feature index, verification manifest, and verified MiniLM NPZ. No Booking.com, OTT, MAiDE, or synthetic attack-pool data was opened.

### Changes made
Added source validation, immutable MiniLM access, method-aware ABSA handling, deterministic within-hotel semantic clustering, duplicate visibility, factual temporal summaries, representative selection, full/compact dossier generation, hotel-ID mapping, schemas, tests, and submission-manifest tooling.

### Validation performed
Verified 500,000 rows, 2,346 hotels, exact MiniLM shape `(500000, 384)`, exact review-ID order, and ABSA counts of 103,021 real DeBERTa, 396,239 proxy, and 740 no-result rows. Built and validated smoke dossiers for three exact HotelRec hotel IDs: 217, 52, and 68 review records respectively. Dossier validation passed. Pytest passed 11 tests.

### Result
The evidence-preparation repository is operational for smoke-scale dossier generation. Full and compact dossiers are generated from the same full source dossier; proxy ABSA remains separate.

### Known limitations
The semantic similarity threshold is provisional pending academic validation. No final rubric, score, band, severity, credibility judgment, recommendation, or LLM layer exists.

### Next permitted step
Review the smoke dossiers and, once the academic rubric is frozen, independently specify and audit any later LLM evaluation layer.

## 2026-07-25 15:25 — Git and submission provenance

### Objective
Record the repository state for reproducibility.

### Files inspected
Repository source, configuration, documentation, schemas, tests, smoke-validation evidence, and submission manifest.

### Changes made
Initialized Git and committed the repository as `1879ebe2314af03bfc56bdc4823e31f49ad0045f`.

### Validation performed
The working tree was clean immediately after the initial commit. Environment and submission-manifest records are regenerated after the commit.

### Result
The repository has a local reproducibility anchor without any external push or network action.

### Known limitations
The commit does not vendor the external HotelRec source data or MiniLM embeddings.

### Next permitted step
Keep later rubric and LLM-layer work in separate, explicitly reviewed changes.

## 2026-07-25 15:32 — Evidence-summary completeness refinement

### Objective
Close remaining rubric-neutral evidence fields required by the preparation specification.

### Files inspected
Smoke dossier outputs and the package test suite.

### Changes made
Added factual ABSA polarity counts by period, aspect counts by year, date-gap summaries, cluster internal similarity summaries, exact-reuse counts, and dynamic smoke-hotel selection. Added exact-ID development-hotel mapping review counts.

### Validation performed
Recompiled the package, ran 11 tests, regenerated three smoke dossiers, and reran dossier validation for all three hotels.

### Result
All tests passed and all three smoke dossier sets validated successfully.

### Known limitations
These are descriptive summaries only. They do not imply trend direction, severity, safety, credibility, or recommendation.

### Next permitted step
Freeze and separately audit the future academic rubric and LLM layer when specified.

## 2026-07-25 — Phase 1B claim compression implementation

### Objective
Extend the frozen Phase 1A evidence foundation with deterministic claim-level compression for the same three HotelRec smoke hotels.

### Changes made
Added `regex_claim_v1` segmentation, new claim-level `all-MiniLM-L6-v2` embeddings, average-linkage cosine issue grouping, neutral rare-case retrieval, deterministic representatives, fixed-cutoff temporal summaries, ABSA coverage, full/compact dossiers, membership files, and coverage mappings. The Phase 1B embedding artifact is new and is not a reuse of the Phase 1A review-level NPZ.

### Validation performed
Processed 337 reviews into 2,706 claims and 953 clusters. Compact estimates are 19,980, 8,394, and 17,817 tokens for Bassenthwaite, Westhaven, and Hotel Vaishnavi. The validation script passed, the full test suite passed with 16 tests, and the manual audit queue was generated with 30 multi-claim and 30 singleton samples plus rare and contradictory-pattern samples.

### Result
Phase 1B passed the implementation and evidence-preparation checks. Two complete offline builds produced identical SHA-256 inventories for 38 generated/validation files.

The implementation was committed as `9cc502b` on `phase-1b-claim-compression`; the final manifest refresh is recorded in the subsequent commit.

### Known limitations
Claim rules, clustering threshold, rare-case lexical rules, and compact display caps are provisional engineering settings. Human semantic-audit fields remain blank and no LLM rubric was called.

### Next permitted step
Manually review the Phase 1B audit queue and separately freeze any academic rubric before considering a future LLM layer.

## 2026-07-25 — Phase 1A full-evidence chat packages

### Objective
Freeze the official Phase 1A full-evidence reference and prepare direct-upload smoke-test packages for the same three HotelRec dossiers.

### Changes made
Created the `phase-1a-full-evidence-reference-v1.0` tag at commit `7a80d358371590d0005681c2da7d6d2652d2a95c`. Created exact source-review JSON/Markdown/CSV/Parquet representations, shared smoke-test instructions, strict output schema, run-record and comparison templates, provenance and claim-boundary documents, per-hotel manifests, the master manifest, and four ZIP packages.

### Validation performed
Verified 217, 52, and 68 reviews respectively; all review IDs and text hashes match the frozen Phase 1A dossiers. JSON, CSV, and Parquet files parse; ZIPs extract; internal manifests match; no Phase 1B files, complete 500K data, forbidden datasets, expected answers, or previous judgments are included. No LLM was called.

### Result
Evidence packaging is structurally complete but blocked pending the researcher-supplied final rubric `TrustStay_V35_LLM_Assessment_Rubric_V1_1_Academically_Grounded_20260725.md`. No older rubric was substituted. Package hashes and the blocker status are recorded in `PHASE_1A_CHAT_PACKAGE_COMPLETION_REPORT.md`.

### Known limitations
The consumer-chat smoke test cannot responsibly begin without the exact final rubric. Hidden model updates, memory, browsing, context limits, and chat settings may affect repeatability after the blocker is resolved.

### Next permitted step
Supply the exact final rubric, replace the blocker notice, regenerate manifests and ZIPs, and require a clean package validation PASS before running one fresh ChatGPT and one fresh Claude test per hotel.

## 2026-07-25 — Final rubric inserted and Phase 1A packages released

### Objective
Replace the temporary rubric blocker with the exact researcher-supplied final academic rubric and finalise the blind ChatGPT/Claude smoke-test packages.

### Changes made
Verified the researcher-supplied rubric at 40,680 bytes with SHA-256 `b000c9632c9dfcb4c7e831062985e83e6e9911eb1351c019635e1396802bf485`; copied it byte-for-byte into the historical package and regenerated all package manifests and ZIPs. The Phase 1A JSON schema was unchanged.

### Validation performed
The complete package validator passed with zero failed checks. Hotel review counts remain 217, 52, and 68; all review IDs, text hashes, JSON/CSV/Parquet files, ZIP contents, and internal manifests matched. Phase 1B, forbidden datasets, previous judgments, expected answers, complete source arrays, credentials, caches, and Git history remain excluded.

### Result
Status changed to `READY_FOR_LLM_SMOKE_TEST`. Master and all three single-hotel ZIP hashes are recorded in `PHASE_1A_CHAT_PACKAGE_COMPLETION_REPORT.md`.

### Known limitations
No LLM was called. Consumer-chat hidden model updates, memory, browsing, context limits, and settings may reduce exact reproducibility.

### Next permitted step
Run one blind ChatGPT and one blind Claude consumer-chat smoke test for each hotel using the corresponding single-hotel ZIP.
