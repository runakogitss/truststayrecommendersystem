# Data provenance

## Evidence chain

```text
upstream locked HotelRec input          (researcher's machine, not shipped)
  → verified reusable feature index      (researcher's machine, not shipped)
  → verified MiniLM NPZ                  (researcher's machine, not shipped)
  → method-labelled ABSA outputs
        ↓  scripts/export_frozen_sample.py   [researcher, run once]
  → data/frozen_research_sample/         (SHIPPED — self-contained)
        ↓  scripts/run_handover.py            [examiner]
  → rubric-neutral evidence preparation
  → full and compact hotel evidence dossiers
```

## What is shipped

`data/frozen_research_sample/` contains exactly the rows required for the frozen
research run and nothing else:

| File | Contents |
|---|---|
| `reviews.parquet` | raw review records: review ID, hotel ID, date, normalised 1–5 rating, verbatim text |
| `features.parquet` | aligned review-level features and ABSA evidence, with method labels |
| `embeddings.npz` | aligned MiniLM vectors (`emb`, `review_id`, `method`) |
| `review_hotel_mapping.parquet` | stable review ID / hotel ID mapping in sample row order, including original locked-source row positions |
| `sample_definition.json` | the deterministic hotel selection, seed, and its own SHA-256 |
| `SHA256_MANIFEST.csv` | SHA-256 hashes for every file above |
| `SOURCE_PROVENANCE.json` | identity and SHA-256 of the upstream artefacts this was cut from |

The upstream locked corpus is **not** shipped and is **not** required. The chain
back to it is preserved by hash in `SOURCE_PROVENANCE.json`, so the sample's
origin remains checkable without redistributing the corpus.

## Upstream model inference

Performed by the researcher, before this package, and **not** re-executed here:

| Step | Recorded upstream identifier |
|---|---|
| Sentence embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Aspect-based sentiment | `yangheng/deberta-v3-base-absa-v1.1` |

These identifiers are recorded from the research record. **This package does not
verify them and does not re-run them.** A validated raw-text-to-ABSA adapter is
not present and is documented as an external dependency rather than invented.

## ABSA method labels

Every review carries one of three labels, which are never merged:

| Label | Status | Meaning |
|---|---|---|
| `deberta_absa` | `REAL_MODEL_REUSABLE` | genuine DeBERTa ABSA output |
| `distilled_proxy` | `PROXY_SEPARATE_ONLY` | a separate proxy — **not** DeBERTa inference |
| `none` | `NO_RESULT` or historical source literal `UNKNOWN` | no ABSA result for this review; the source literal is preserved |

Validation rejects the sample if any row's label and status disagree. Aspect and
sentiment fields are typically populated only for `deberta_absa` rows; the
realised coverage for this sample is recorded in
`outputs/frozen_research_run/validation/frozen_sample_validation.json` under
`absa`, and must be read from there rather than assumed.

## Row re-basing

The upstream artefacts index embeddings by absolute position in the full corpus.
A self-contained sample cannot carry those rows, so the export re-bases
`input_row_position` and `minilm_embedding_row` to `0..N-1` and preserves the
originals as `source_input_row_position` and `source_minilm_embedding_row`.

Embedding **values**, review **identities** and row **order** are unchanged. This
is a change of index origin only, recorded in `SOURCE_PROVENANCE.json` under
`row_rebasing` and asserted by the test suite.

## Dataset scope

Only HotelRec-namespace data is in scope. Booking.com, OTT, MAiDE and synthetic
attack-pool data are excluded, and validation fails if an out-of-scope dataset
name appears. Matching is on whole tokens, never bare substrings, so ordinary
paths and identifiers do not produce false positives.
