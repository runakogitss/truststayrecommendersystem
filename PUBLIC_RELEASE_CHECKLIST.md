# TrustStay public release checklist

Status date: 21 August 2026

This checklist defines the public GitHub release. Review-bearing research data,
participant records and live study-backend configuration belong only in a
separately controlled examiner package.

## Dissertation evidence crosswalk

| Required evidence | Public repository location | Status |
|---|---|---|
| Repository overview and execution boundary | `README.md`, `METHODOLOGY_BOUNDARIES.md` | PASS |
| Data origin and public/private boundary | `DATA_PROVENANCE.md`, `data/frozen_research_sample/` | PASS |
| Final grouping decision | `METHODOLOGY_CHANGE_RECORD_2026-08-12.md`, `METHOD_SELECTION_VALIDATION.md` | PASS |
| Frozen evidence configuration | `configs/evidence_pipeline.yaml`, `configs/temporal_windows.yaml` | PASS |
| Evidence schemas | `schemas/` | PASS |
| Layer 1 implementation | `src/truststay_evidence/`, `scripts/` | PASS |
| Completed Layer 1 summary | `outputs/frozen_research_run/validation/run_summary.json` | PASS |
| Completed full-ABSA validation | `outputs/frozen_research_run_full_absa/FULL_ABSA_VALIDATION.md` | PASS WITH WARNINGS |
| Full-ABSA provenance and cluster invariant | `outputs/frozen_research_run_full_absa/ABSA_INFERENCE_PROVENANCE.json`, `cluster_invariance_check.json` | PASS |
| Layer 2 rubric, prompts, schemas and display mapping | `layer2/methodology/` | PASS |
| Layer 2 implementation and dry-run plan | `layer2/implementation/` | PASS |
| Layer 2 production and cross-layer audits | `layer2/audit/` | PASS WITH DISCLOSED PROVENANCE LIMITATION |
| Safe accepted/rejected metadata examples | `layer2/examples/` | PASS |
| Public Layer 2 checksum register | `layer2/SHA256SUMS.txt` | PASS — regenerated and verified |
| Automated test suite | `tests/` | PASS — 48/48 on 21 August 2026 |
| Clean synthetic end-to-end rerun | `scripts/make_smoke_fixture.py` → `scripts/run_handover.py` | PASS — 6 hotels, 240 reviews, 6 full and 6 compact dossiers |

## Recorded production outcomes

- Layer 1 evidence run: 480 hotels, 100,111 reviews, 480 full dossiers and 480
  compact dossiers; status `PASS`.
- Full DeBERTa ABSA refresh: 100,111/100,111 successful inference rows, 0
  technical failures, 480 full and 480 compact refreshed dossiers; verdict
  `PASS WITH WARNINGS`.
- Frozen cluster invariant: 100,111/100,111 matching memberships, 480 hotels
  and 83,686 semantic groups.
- Layer 2: 480 hotels attempted, 439 technically accepted and 41 rejected by
  the implemented validation controls.

## Public exclusions

The GitHub release must not contain:

- raw or paraphrased review-bearing dossiers;
- the frozen Parquet/NPZ research sample;
- participant-level survey exports or qualitative response data;
- full Layer 2 per-hotel production outputs;
- the live v4.8 experiment HTML while it contains study-backend configuration;
- `.env` files, credentials, access tokens, session data or model-provider logs;
- personal absolute filesystem paths;
- virtual environments, caches, `.git` internals or generated ZIP files.

## Historical records

Earlier `NOT RUN` records are retained only under
`archive/historical_development/`. They describe the pre-production stage and
are not current status records. The authoritative completed records are under
`outputs/frozen_research_run/` and
`outputs/frozen_research_run_full_absa/`.

## Final release gates

- [x] Required dissertation technical files present.
- [x] Completed-run wording corrected.
- [x] Historical pre-run material clearly archived.
- [x] Public/private data boundary documented.
- [x] Personal absolute paths scrubbed from live public records.
- [x] Full tests pass: 48/48.
- [x] Regenerate and verify the Layer 2 SHA-256 manifest after final edits.
- [ ] Generate the release-level SHA-256 manifest from the approved commit.
- [ ] Inspect the final Git diff and commit only confirmed release files.
- [ ] Choose a repository license. No license should be invented without the
      author's decision.
- [ ] Tag the approved commit and build the public ZIP from that exact tag.
