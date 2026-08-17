# TrustStay Cross-Layer Provenance Audit

Audit date: 2026-08-17. This was a read-only comparison. No Layer 1 or Layer 2 job was run, no model was invoked, and no existing research file was modified.

## Conclusion

`NOT ESTABLISHED FROM AVAILABLE ARTIFACTS`

Layer 2 source dossiers do not exactly correspond to either preserved Layer 1 set.

The Layer 2 dossiers have the same 480 hotel IDs and the same raw review content as Candidate A, but all 480 files are materially different because ABSA annotations and derived dossier metadata differ. The expected full Candidate B directory is not present. Its preserved validation file says the full ABSA refresh was **NOT RUN**, with only smoke-test directories available.

This is Result D from the requested classification. The exact historical Layer 1 run that produced the Layer 2 dossier version cannot be established from the preserved candidate directories.

## Counts

| Source | Hotels | Exact matches to Layer 2 | Non-identical same-hotel files | Missing |
| --- | ---: | ---: | ---: | ---: |
| Layer 2 input | 480 | — | — | — |
| Candidate A: original Layer 1 | 480 | 0 | 480 | 0 |
| Candidate B: full-ABSA refreshed | 0 preserved full dossiers | 0 | 0 | 480 |

Candidate B's zero counts reflect that the expected full directory does not exist, not that the Layer 2 files were proven different from a complete Candidate B set. The preserved file `outputs/frozen_research_run_full_absa/FULL_ABSA_VALIDATION.md` states `Execution state: NOT RUN`.

## Review-count reconciliation

- Layer 2 source dossiers: 100,111 review evidence records
- Candidate A original Layer 1 dossiers: 100,111 review evidence records
- Candidate B preserved full set: unavailable; smoke-test artifacts only

For all 480 Layer 2/Candidate A hotel pairs, the review count, review-ID set, review-ID order, review-text order, and `text_sha256` order are identical.

## Representative hashes

The three non-required examples were selected with deterministic random seed `20260817`. No guest review text is included.

| Hotel | Layer 2 SHA-256 | Layer 1 Original SHA-256 | Layer 1 Full-ABSA SHA-256 | Match |
| --- | --- | --- | --- | --- |
| Kinosaki Onsen Nishimuraya Honkan | `6f9ed66671536385420e6ed242599b85366ffc0a6c54ab8be37a611d9755fb54` | `ab9431be24ae1f515ffd753cae074b4463c9c52517b5730daf068433a1f2be19` | unavailable | Non-identical to A |
| Gopeng Rainforest Resort | `e57e63bf85a20f2af0acf74ac277bf529f5b7bdf7f885d9794b6b44276866554` | `236a22f15ccbf7e49b65d8cbfedcd3d513a5ee0d007bd0caf9f5d4a072bf93ea` | unavailable | Non-identical to A |
| Comfort Suites, Sioux Falls | `1eee56c8f3bd22278ace6d6003c0f34215708303b3187ea4f3de101abd10a8be` | `8c8ada8a43d751d49d6bc2bf81cc208163eb7d2f37567dd5ab7b12b691afe2a1` | unavailable | Non-identical to A |
| Quality Inn O'Fallon | `c09b06dfb9cac2bd9a60bc8289e076f7389aa1ab379b5c50df719b7cb0c6bda6` | `425de4030c53994ef4ee312c4d3acb10f0096b78c764ffb11ef7d6c259c19ba5` | unavailable | Non-identical to A |
| Long Ji One Hotel | `8461f9f7e677916536cd98d4a4f0d6989a201b90aad60d8d52ecca5d27d751af` | `8f196972c3839c93645c0e5db55760a9ac9286af53ca4bc874bc2e333dac6b59` | unavailable | Non-identical to A |

## Content-level discrepancies

The differences are not serialization-only:

- Canonicalized JSON equality: 0 of 480
- All 480 differ in `hotel_metadata`, `methodology_notes`, `provenance`, `review_evidence_records`, `semantic_clusters`, `temporal_summaries`, and `warnings`
- Review-record differences include 98,732 `absa_sentiment` values, 98,618 `absa_aspect` values, and 78,924 each for `absa_method` and `absa_reusable_status`
- The raw review text and review identifiers remain identical in order across all 480 pairs

Therefore the Layer 2 dossier set is a materially different derived-data version, not a whitespace or ordering variant of Candidate A.

## Evidence created

- [layer1_to_layer2_provenance_audit.json](</Users/ritchierunako/Downloads/layer 2 run /TrustStay_Layer2_GPT56_Luna_100K/layer1_to_layer2_provenance_audit.json>)
- [layer1_to_layer2_provenance_audit.md](</Users/ritchierunako/Downloads/layer 2 run /TrustStay_Layer2_GPT56_Luna_100K/layer1_to_layer2_provenance_audit.md>)

## Safety confirmation

- No model was invoked.
- No Layer 1 or Layer 2 job was rerun.
- No source file was modified.
- No failed hotel was repaired.
