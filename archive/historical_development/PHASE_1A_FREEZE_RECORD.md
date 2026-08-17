# Phase 1A freeze record

Frozen before Phase 1B claim-level compression work began.

- Freeze date: 2026-07-25
- Phase 1A branch: `main`
- Phase 1A commit: `7a80d358371590d0005681c2da7d6d2652d2a95c`
- Phase 1B branch: `phase-1b-claim-compression`
- Existing tests: `11 passed, 22 warnings`
- Phase 1A source audit package SHA-256: `ac42efffe1f5c94d8bd540c693de7a74222170b90beb9bb4b5f9fea94256f16b`

## Frozen Phase 1A dossier hashes

| Dossier | SHA-256 |
|---|---|
| `outputs/development/hotel_Hotel_Review-g1006863-d3676814-Reviews-Bassenthwaite_Lakeside_Lodges-Bassenthwaite_Keswick_Lake_District_Cumbria_England.html_full.json` | `9d2934d1b55632ba1f907a3b6ef9ff06a4801f50e4277a715fe1a0305797ed84` |
| `outputs/development/hotel_Hotel_Review-g1007668-d3676814-Reviews-Westhaven_Luxury_Lodge-Collingwood_Golden_Bay_Nelson_Tasman_Region_South_Island.html_full.json` | `561450e09707db594fd148578fe2faaa2931fe1fdd4f6360f885ac057d0e66f6` |
| `outputs/development/hotel_Hotel_Review-g1010180-d3533746-Reviews-Hotel_Vaishnavi-Solapur_Solapur_District_Maharashtra.html_full.json` | `28bf9460e0f838e7314cf4ba51d87beb348bbc1010da149313e10f02fda9e01f` |
| `outputs/development/hotel_Hotel_Review-g1006863-d3676814-Reviews-Bassenthwaite_Lakeside_Lodges-Bassenthwaite_Keswick_Lake_District_Cumbria_England.html_compact.json` | `1ebac832530a48871d9b381c192722950ed9892d0c3f33654fef00987fc60893` |
| `outputs/development/hotel_Hotel_Review-g1007668-d2478211-Reviews-Westhaven_Luxury_Lodge-Collingwood_Golden_Bay_Nelson_Tasman_Region_South_Island.html_compact.json` | `7448401720d5f60031c1ae2dc4279c5f372cf881b7fabf00b66540200108788c` |
| `outputs/development/hotel_Hotel_Review-g1010180-d3533746-Reviews-Hotel_Vaishnavi-Solapur_Solapur_District_Maharashtra.html_compact.json` | `6c77944086979294cc43990fe5a44eaa62cc5d1a9fcbbcf2db2cc66f8857211d` |

## Frozen components

- Source provenance and locked-input identity;
- verified source loaders;
- review-ID and input-row mapping;
- MiniLM review-embedding mapping;
- ABSA method separation;
- factual review-level evidence records;
- forbidden-source protections.

## Explicitly not frozen

- Whole-review cluster design;
- representative-selection design;
- compact-dossier structure;
- temporal cutoff convention;
- all new Phase 1B claim segmentation, claim embeddings, issue grouping, and compression logic.

Phase 1B must not rewrite or overwrite the frozen Phase 1A dossier files.
