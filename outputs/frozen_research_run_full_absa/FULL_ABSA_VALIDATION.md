# Full DeBERTa ABSA Refresh Validation

**Verdict:** `PASS WITH WARNINGS`
**Generated UTC:** `2026-08-14T00:53:28.457979+00:00`

## Coverage and alignment

- Expected rows: `100111`
- Rows attempted: `100111`
- Successful inference rows: `100111` (100.0000%)
- Reviews with one or more extracted aspects: `98341`
- Reviews with zero extracted aspects: `1770`
- Technical inference failures: `0`
- Extracted aspect terms: `418946`
- Sentiment labels populated: `418946`
- Aspect extraction scores populated: `418946`
- Sentiment-model scores populated: `300075`
- Duplicate review IDs: `0`
- Missing review IDs: `0`

## Frozen cluster invariant

- Review IDs compared: `100111`
- Matching memberships: `100111`
- Mismatching memberships: `0`
- Missing IDs: `0`
- Extra IDs: `0`
- Original hotel count: `480`
- Refreshed hotel count: `480`
- Original group count: `83686`
- Refreshed group count: `83686`
- Cluster invariant: `PASS`

## Dossiers and failures

- Full dossiers generated: `480`
- Compact dossiers generated: `480`
- Dossier failures: `0`

### Validation failures

- None

## Interpretation boundary

Rows with inference_status starting with success are labelled `deberta_absa`; failed rows remain `none`/`NO_RESULT`. Successful zero-aspect inference is not a technical failure. No `distilled_proxy` value is copied into the refreshed result. MiniLM embeddings, frozen semantic group IDs, and the complete-linkage threshold are reused unchanged.
