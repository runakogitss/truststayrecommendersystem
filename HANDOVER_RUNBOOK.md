# TrustStay Layer 1 — examiner runbook

This assumes you can run Python. It assumes nothing about TrustStay.

Everything you need is inside this folder. You do **not** need any external
dataset, API key, password, token, `.env` file, database, network connection or
access to the researcher's machine.

---

## 1. What Layer 1 does

Layer 1 turns a fixed set of hotel reviews into **evidence dossiers**: structured,
hash-verified JSON files that record what the reviews say, when they were
written, how they group together semantically, and which specific reviews
support each group.

```
defined review sample
  → raw review records
  → aligned precomputed review-level features / ABSA evidence
  → aligned MiniLM embeddings
  → provenance and input validation
  → semantic evidence grouping
  → duplicate / distinct-review indicators
  → temporal and count-based evidence
  → representative evidence selection
  → full evidence dossier
  → compact evidence dossier
  → validation and reproducibility records
```

**Layer 1 ends at the evidence dossier.** It deliberately produces no LLM
interpretation, no severity judgement, no recurrence judgement, no hotel-quality
judgement, no TrustStay score, no A–H band, no booking recommendation, no
interface output and no experimental result. Those belong to later layers of the
dissertation and are not part of this package. `tests/test_layer1_boundary.py`
enforces this in code.

---

## 2. What is included

| Path | Contents |
|---|---|
| `src/truststay_evidence/` | the Layer 1 implementation |
| `scripts/` | the commands in this runbook |
| `configs/` | frozen scientific settings and temporal windows |
| `schemas/` | JSON schemas for review records and dossiers |
| `tests/` | the automated test suite |
| `data/frozen_research_sample/` | the complete frozen research sample (reviews, features, embeddings, review↔hotel mapping, sample definition, hashes) |
| `outputs/frozen_research_run/` | where your rerun writes its results |
| `archive/historical_development/` | earlier development material, retained for provenance only — **not used by anything in this runbook** |

---

## 3. What is precomputed, and why that matters

Two model steps were performed **upstream by the researcher** and are **not**
re-executed by this rerun:

* aspect-based sentiment analysis (recorded upstream as `yangheng/deberta-v3-base-absa-v1.1`);
* sentence embeddings (recorded upstream as `sentence-transformers/all-MiniLM-L6-v2`).

Their outputs are supplied in `data/frozen_research_sample/` as verified
artefacts. Stated plainly:

> **Model inference was performed upstream. The frozen handover reruns the
> deterministic evidence-consolidation pipeline using verified precomputed
> research artefacts. It does not regenerate DeBERTa ABSA or MiniLM embeddings
> from raw review text.**

This package does not claim otherwise anywhere, and does not contain a validated
raw-text-to-ABSA adapter. What *is* fully reproducible here is every
deterministic step from the supplied artefacts to the final dossiers: identical
inputs give byte-identical dossiers on any machine.

Each review carries an explicit ABSA provenance label — `deberta_absa` (real
model output), `distilled_proxy` (a separate proxy) or `none` (no result). These
are never merged and proxy rows are never presented as direct DeBERTa inference.
Validation rejects the sample if any row's label and status disagree.

---

## 4. Create the environment

Python 3.11 or newer.

```bash
cd TrustStay_Layer1_Reproducible_Evidence_Engine
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## 5. Validate the supplied research sample

```bash
python scripts/validate_sample.py
```

This verifies SHA-256 hashes for every supplied file, checks the sample
definition against its own recorded hash, and confirms the three row sets are
exactly aligned: identical review identities, identical ordering, no missing or
duplicate IDs, no missing hotel IDs, no silent truncation, and no out-of-scope
data. It exits non-zero and prints the reason if anything fails.

---

## 6. Run Layer 1

```bash
python scripts/run_handover.py
```

One command runs all four stages and stops at the first failure:

1. validate the frozen sample;
2. build full and compact dossiers;
3. validate the generated dossiers;
4. write the submission manifest.

Expect it to print `ALL STEPS PASSED`. If it does not, it exits non-zero and
prints what failed — nothing is hidden or downgraded to a warning.

To try one hotel first:

```bash
python scripts/run_handover.py --hotel-limit 1
```

To exercise the package without touching the research data at all, generate a
clearly-labelled synthetic fixture and run against that:

```bash
python scripts/make_smoke_fixture.py --output /tmp/ts_fixture
python scripts/run_handover.py --sample-dir /tmp/ts_fixture --output-dir /tmp/ts_out
```

---

## 7. Where outputs appear

```
outputs/frozen_research_run/
├── full_dossiers/        one hotel_<id>_full.json per hotel — the audit record
├── compact_dossiers/     one hotel_<id>_compact.json per hotel — the projection
├── validation/           frozen_sample_validation, dossier_validation,
│                         execution_record, run_summary
├── diagnostics/          cluster and representative-selection reports
└── manifests/            SUBMISSION_MANIFEST.json / .csv / .md
```

`outputs/frozen_research_run/.embedding_cache/` is a derived working file. It can
be deleted after the run.

---

## 8. Validate the outputs

```bash
python scripts/validate_outputs.py
```

Confirms every dossier matches its schema, that review IDs are unique, that
cluster membership covers every review exactly once, that each representative
resolves to a real source review inside its own cluster, that each full dossier
has a matching compact dossier, and that no downstream judgement field has
leaked into Layer 1 output.

Optional, and worth a look:

```bash
python scripts/cluster_diagnostics.py
```

Reports the cluster-size distribution, the largest clusters, whether those
clusters obey the complete-linkage threshold, the cluster-size distribution, representative traceability, and how much the compact projection compresses. It reports; it changes nothing.

---

## 9. Run the tests

```bash
python -m pytest -q
```

The suite covers input alignment, ABSA label separation, determinism, clustering
behaviour, representative traceability, compaction equivalence, the Layer 1
boundary, portability, temporal anchoring, sampling, and a full end-to-end run
over the synthetic fixture.

---

## 10. Verify hashes

```bash
python scripts/verify_hashes.py
```

Recomputes SHA-256 for every supplied research-sample file and compares against
`data/frozen_research_sample/SHA256_MANIFEST.csv`. Any mismatch fails.

Output hashes are recorded in
`outputs/frozen_research_run/manifests/SUBMISSION_MANIFEST.json`, alongside the
environment, package versions, configuration and runtime.

---

## 11. What results to expect

Read the exact expected counts from `FINAL_STATUS.md` under **Expected results**
and from the supplied `data/frozen_research_sample/sample_definition.json`. The
run is designed so those numbers are checked automatically rather than trusted:
`run_handover.py` fails if the dossiers do not cover exactly the declared number
of reviews.

Two properties are worth confirming yourself:

* **Determinism.** Run it twice into different output directories. The dossiers
  are byte-identical apart from the recorded timestamp and environment block.
* **Hotel completeness.** No hotel's review history is ever truncated, so the
  realised review count exceeds the sampling target. That is the intended
  design, not a rounding error.

---

## 12. If something fails

Every script exits non-zero with a printed reason. The usual causes:

| Symptom | Cause |
|---|---|
| `Frozen research sample is incomplete` | `data/frozen_research_sample/` was not shipped or was not fully extracted |
| `hash verification FAILED` | a supplied file was modified or truncated in transit |
| `Row-count mismatch` | the three row sets disagree; the sample must not be used |
| `does not match review_text` | review text and its recorded hash disagree |
| `ModuleNotFoundError` | the virtual environment is not activated, or step 4 was skipped |

Please do not work around a validation failure. It means the evidence is not the
evidence it claims to be, and any dossier built from it would be untrustworthy.
