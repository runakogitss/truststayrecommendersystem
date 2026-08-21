# Archive — historical development material

**Nothing in this directory is executed by the handover run.** It is retained
for provenance only. `tests/test_portability.py` fails the build if anything in
`src/` or `scripts/` references it.

| Item | What it is | Status |
|---|---|---|
| `phase1b_claims.py`, `build_phase_1b.py`, `validate_phase_1b.py`, `create_phase1b_manifest.py`, `phase_1b_claim_compression.yaml` | Phase 1B claim-level compression experiment | Historical. Not part of review-level Layer 1. |
| `build_phase1a_chat_packages.py`, `validate_phase1a_chat_packages.py` | Builders for manual LLM smoke-test packages | Historical. Belongs to a later layer, not Layer 1. |
| `map_development_hotels.py`, `validate_dossiers.py` | Superseded development utilities | Replaced by `scripts/validate_outputs.py`. |
| `PHASE_1A_*.md`, `PHASE_1B_*.md`, `DEVELOPMENT_LOG.md`, `TECHNICAL_AUDIT.md`, `CHANGELOG.md` | Development records | Historical. |
| `FULL_ABSA_VALIDATION_PREFLIGHT_NOT_RUN.md` | Validation template created before the completed production refresh | Historical pre-run record. Its `NOT RUN` language was true only at that earlier stage; the authoritative completed records are under `outputs/frozen_research_run_full_absa/`. |
| `fairmont_reference_package/` | A review-bearing single-hotel extract from an earlier V3.4.1 pipeline | Excluded from the public repository by `.gitignore`; private historical record only. |

## Warning about `fairmont_reference_package/hotel_layer1_summary.csv`

That privately retained file is a **historical artefact of an earlier, different
pipeline** and is **not included in this public repository**. It contains
downstream fields — `quality_score`,
`score_band`, `risk_grade`, `confidence`, `severe_reviews`, recommendation
eligibility — that the Layer 1 code in this package does not compute, does not
consume, and is forbidden from emitting.

The private copy is retained because it is named in that package's own SHA-256
manifest and removing it would break the private historical hash chain. It must
not be read as a Layer 1 result, and no value in it has been reproduced or
validated by this public package.

Its schema also differs from the current feature schema: it carries a V3.4.1
forensic/credibility feature set and lacks the `review_text`, `absa_aspect` and
`absa_sentiment` columns that Layer 1 requires. It therefore cannot be used as
an input to this pipeline.
