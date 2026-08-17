# Phase 1A full-evidence freeze record

- Repository: `<source repository at the time of the historical freeze>`
- Frozen commit: `7a80d358371590d0005681c2da7d6d2652d2a95c`
- Frozen commit branch: `main`
- Current packaging branch: `phase-1b-claim-compression`
- Record time (UTC): `2026-07-25T12:31:08.763669+00:00`
- Operating system: `macOS-26.5.2-arm64-arm-64bit`
- Python: `3.12.7 (v3.12.7:0b05ead877f, Sep 30 2024, 23:18:00) [Clang 13.0.0 (clang-1300.0.29.30)]`
- Phase 1A tests: `11 passed, 22 warnings`
- Phase 1A determinism: recorded frozen dossier hashes; no regeneration performed
- Number of hotels: 3
- Source-review count: 337 total
- Final rubric status: `FOUND`; no older rubric substituted

## Frozen Phase 1A dossiers

| Label | Hotel ID | Reviews | SHA-256 |
|---|---|---:|---|
| `hotel_01` | `Hotel_Review-g1006863-d3676814-Reviews-Bassenthwaite_Lakeside_Lodges-Bassenthwaite_Keswick_Lake_District_Cumbria_England.html` | 217 | `9d2934d1b55632ba1f907a3b6ef9ff06a4801f50e4277a715fe1a0305797ed84` |
| `hotel_02` | `Hotel_Review-g1007668-d2478211-Reviews-Westhaven_Luxury_Lodge-Collingwood_Golden_Bay_Nelson_Tasman_Region_South_Island.html` | 52 | `561450e09707db594fd148578fe2faaa2931fe1fdd4f6360f885ac057d0e66f6` |
| `hotel_03` | `Hotel_Review-g1010180-d3533746-Reviews-Hotel_Vaishnavi-Solapur_Solapur_District_Maharashtra.html` | 68 | `28bf9460e0f838e7314cf4ba51d87beb348bbc1010da149313e10f02fda9e01f` |

## Frozen components

- Phase 1A full JSON dossiers and review-level evidence records.
- Verified HotelRec source-review identity, review IDs, text, dates, ratings, provenance, cluster membership, representatives, temporal summaries, and ABSA method labels.
- Phase 1A source-review hash and row-position traceability.

## Explicit exclusions

- Phase 1B compressed dossiers and claim-level outputs are excluded.
- Complete 500K parquet and complete MiniLM NPZ are excluded.
- Booking.com, OTT, MAiDE, synthetic attack-pool, unrelated hotels, previous model judgments, expected answers, scores, bands, conclusions, and adjudications are excluded.
- Final rubric is not included because the researcher-supplied file was not found; no older rubric was substituted.
