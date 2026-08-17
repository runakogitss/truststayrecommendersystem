# TrustStay Layer 1 — Reproducible Evidence Engine

Version `2.1.0-complete-linkage-080`

This is the **professor handover package** for TrustStay Layer 1. It contains the
frozen 480-hotel / 100,111-review research sample, aligned precomputed review
features and MiniLM embeddings, the Layer 1 Python code, tests, provenance and
rerun instructions.

## What Layer 1 does

`frozen review sample → validate alignment/hashes → hotel-level semantic grouping
→ duplicate/distinct-review indicators → temporal summaries → representative
evidence → full + compact evidence dossiers`

Final semantic grouping is:

`MiniLM all-MiniLM-L6-v2 → cosine distance → complete-linkage clustering → 0.80 similarity threshold`

Layer 1 ends at the evidence dossier. It does not produce LLM interpretation,
severity/recurrence judgements, hotel quality, TrustStay scores/bands,
recommendations or experiment results.

## Professor start here

Read `HANDOVER_RUNBOOK.md`, then run:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements.txt
python scripts/run_handover.py
```

The package requires no API key and no access to the researcher's original
`/Volumes/...` paths.

## Bundled frozen sample

- hotels: **480**
- reviews: **100,111**
- feature rows: **100,111**
- MiniLM embeddings: **100,111 × 384 float32**
- sample seed: `20260812`
- sample definition SHA-256: `4152e876313fa6ffa4cc1b9096d05a3ff5a531a9e917d63054246b6b0661a318`

See `DATA_PROVENANCE.md` and the manifest inside `data/frozen_research_sample/`.

## Method record

The replacement of the earlier DBSCAN development grouping with complete linkage
is documented in `METHODOLOGY_CHANGE_RECORD_2026-08-12.md`; the comparison summary
is in `METHOD_SELECTION_VALIDATION.md`.
