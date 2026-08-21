# TrustStay — Reproducible Review-Evidence System

Version `2.1.0-complete-linkage-080`

TrustStay is a research system for turning hotel-review text into structured,
traceable evidence and then applying a bounded qualitative assessment workflow.
It was developed for the MSc dissertation *TrustStay: Design and Evaluation of
a Signal-Explicit Review-Evidence Intermediary for Hotel Booking Decisions*.

This public repository contains the implementation, frozen configurations,
schemas, prompts, methodology records, validation summaries, tests and
non-sensitive audit evidence for both technical layers. It intentionally does
not publish raw guest-review text, participant-level data, credentials or full
per-hotel production outputs.

> **Research boundary:** TrustStay organizes and interprets reported guest
> evidence. It does not establish whether a review claim is true, determine
> reviewer independence, detect fake reviews, estimate objective hotel quality
> or provide current booking advice.

## Status at a glance

| Component | Recorded result |
|---|---|
| Frozen research scope | 480 hotels and 100,111 reviews |
| Layer 1 evidence run | 480 full dossiers and 480 compact dossiers; 0 dossier failures |
| Full DeBERTa ABSA refresh | 100,111/100,111 successful rows; 0 technical inference failures |
| Extracted aspect terms | 418,946 |
| Frozen semantic groups | 83,686 |
| Cluster-invariance check | 100,111/100,111 review memberships matched |
| Layer 2 workload | 549 Layer 2A assessments + 480 Layer 2B assessments = 1,029 logical assessments |
| Layer 2 production outcome | 439 technically accepted hotels; 41 validator rejections |
| Public-repository tests | 48/48 passed on 21 August 2026 |
| Synthetic end-to-end check | Passed: 6 hotels, 240 reviews, 6 full and 6 compact dossiers |

The detailed evidence behind these figures is linked in
[`FINAL_STATUS.md`](FINAL_STATUS.md) and
[`PUBLIC_RELEASE_CHECKLIST.md`](PUBLIC_RELEASE_CHECKLIST.md).

## Start here

- **New to TrustStay?** Read “What problem TrustStay addresses” and “System
  architecture” below.
- **Want to run the public code?** Follow “Route A — Public synthetic
  end-to-end run.”
- **Reviewing the research record?** Start with
  [`FINAL_STATUS.md`](FINAL_STATUS.md),
  [`DATA_PROVENANCE.md`](DATA_PROVENANCE.md) and the
  [`public release checklist`](PUBLIC_RELEASE_CHECKLIST.md).
- **Inspecting Layer 2?** Open [`layer2/README.md`](layer2/README.md), then read
  the frozen rubric, prompts, schemas and audit records.
- **Holding authorized private data?** Use
  [`HANDOVER_RUNBOOK.md`](HANDOVER_RUNBOOK.md) for the controlled Layer 1 rerun.

## What problem TrustStay addresses

Hotel guests make booking decisions before experiencing many dimensions of
service quality. Reviews reduce that information gap, but ratings and generic
summaries can compress away details that matter to a decision, including:

- what aspect of the hotel a review discusses;
- how specific the supporting evidence is;
- how serious the reported consequence may be;
- whether similar reports are recent or distributed across time;
- how much distinct evidence is available; and
- which source reviews support an assessment.

TrustStay treats review text as evidence to be organized and traced, rather
than as material to be collapsed immediately into one opaque score. Its
architecture deliberately separates reproducible evidence construction from
qualitative model interpretation.

## System architecture

```text
Frozen review corpus
        │
        ▼
Layer 1: deterministic evidence engine
  validate identity, ordering and hashes
  retain aspect-level ABSA information
  group semantically similar reviews within each hotel
  calculate counts, dates, temporal windows and provenance
  select traceable representative evidence
        │
        ▼
Hotel evidence dossiers
        │
        ▼
Layer 2A: bounded LLM evidence ledgers
  process chronological chunks
  retain exact cited review IDs
  do not assign a band or numerical display value
        │
        ▼
Deterministic ledger validation
        │
        ▼
Layer 2B: frozen-rubric hotel adjudication
  assess the hotel-level evidence pattern
  return structured qualitative fields and cited evidence IDs
        │
        ▼
Final schema, provenance and semantic validation
        │
        ▼
Deterministic display mapping
```

Layer 1 and the validators use code for operations with exact answers. The LLM
is reserved for rubric-bound qualitative interpretation. The final production
display mapping is applied only after the qualitative output passes validation.

## Layer 1 — Evidence Engine

Layer 1 converts review-level material into full and compact hotel evidence
dossiers. It remains rubric-neutral: it does not assign a severity judgement,
TrustStay band, numerical display anchor or recommendation.

### 1. Input validation and provenance

The controlled research input contains aligned review records, precomputed
features, review-to-hotel mappings and 384-dimensional MiniLM embeddings. Before
execution, Layer 1 checks:

- equal row counts across reviews, features, mappings and embeddings;
- identical review IDs and identical ordering;
- unique review IDs and contiguous rebased indices;
- review-text SHA-256 values;
- dataset-scope restrictions;
- sample-definition integrity; and
- the supplied file-hash manifest.

The completed validation records 480 hotels and 100,111 aligned rows across all
four input structures. See [`DATA_PROVENANCE.md`](DATA_PROVENANCE.md).

### 2. Aspect-based sentiment information

Whole-review sentiment can flatten mixed experiences. A statement such as
“helpful staff but a noisy room” contains different evaluations of different
hotel aspects. The full production refresh therefore used:

- `yangheng/deberta-v3-base-end2end-absa` for end-to-end aspect extraction and
  joint aspect sentiment; and
- `yangheng/deberta-v3-base-absa-v1.1` for the documented low-extraction-score
  sentiment-refinement path.

The completed refresh processed all 100,111 reviews, retained 1,770 valid
zero-aspect results, recorded zero technical inference failures and did not use
proxy fallback. Model identities, resolved revisions and execution metadata are
preserved in
[`ABSA_INFERENCE_PROVENANCE.json`](outputs/frozen_research_run_full_absa/ABSA_INFERENCE_PROVENANCE.json).

### 3. Semantic grouping

Each review is represented by a precomputed
`sentence-transformers/all-MiniLM-L6-v2` embedding. Reviews are grouped only
within their hotel using cosine distance and complete-linkage agglomerative
clustering at a frozen 0.80 similarity threshold.

```text
MiniLM embedding
    → cosine distance
    → hotel-level complete linkage
    → maximum within-cluster distance 0.20
    → equivalent minimum pairwise similarity 0.80
```

Complete linkage was selected to limit transitive chaining. In the development
comparison, the earlier `DBSCAN(min_samples=1)` configuration produced a largest
cluster of 706 reviews. The final complete-linkage 0.80 method reduced the
largest cluster to 19 while retaining more usable grouping than the stricter
0.85 and 0.90 candidates. The frozen decision is documented in
[`METHODOLOGY_CHANGE_RECORD_2026-08-12.md`](METHODOLOGY_CHANGE_RECORD_2026-08-12.md)
and [`METHOD_SELECTION_VALIDATION.md`](METHOD_SELECTION_VALIDATION.md).

Semantic grouping organizes similar language. It is not evidence that reports
are true, independent or mutually corroborating.

### 4. Deterministic evidence features

After the model-derived representations are frozen, Layer 1 calculates the
parts of the evidence base with reproducible answers:

- hotel and review identity;
- semantic-group membership;
- group and review counts;
- duplicate and distinct-review indicators;
- review dates;
- 90-, 180- and 365-day summaries anchored to each hotel's latest review;
- aspect and sentiment distributions;
- source provenance and hashes; and
- representative evidence selection.

Representative reviews are selected deterministically by centroid proximity,
then by `_real_first`, review-text length and `review_id`, all ascending. Text
length is only a tie-break; if it is reached, the shorter text wins.

### 5. Layer 1 outputs

Layer 1 writes two schema-validated dossier forms per hotel:

- **Full dossier:** retains every review and the complete structured evidence
  record used for downstream processing.
- **Compact dossier:** retains selected representative text and aggregate
  evidence fields for lower-context inspection. It is a projection, not the
  complete evidential record.

The public repository contains safe aggregate validation records but excludes
the review-bearing dossier files themselves.

## Layer 2 — Bounded qualitative assessment

Layer 2 applies a frozen, two-stage LLM workflow to the Layer 1 full dossiers.
Its methodology, implementation and safe audit evidence are under
[`layer2/`](layer2/).

### Layer 2A: chronological evidence ledgers

Large hotel dossiers are divided into chronological chunks. The same extraction
prompt converts each chunk into a structured evidence ledger containing exact
review IDs. Layer 2A organizes evidence but is forbidden from assigning the
final A–H band or numerical display value.

### Layer 2B: hotel-level adjudication

Layer 2B receives the validated ledgers and applies the frozen runtime rubric to
the hotel-level evidence pattern. The output is constrained by a JSON schema and
includes qualitative assessment fields, confidence, temporal status and cited
review identifiers.

### Deterministic validation and display mapping

The control harness checks, among other things:

- source-dossier structure and declared review counts;
- hotel and chunk identity;
- duplicate and missing review IDs;
- cited review IDs against the source dossier;
- output schemas;
- band-to-label consistency;
- recurrence claims against multiple distinct concern review IDs; and
- date evidence for higher recurrence categories.

Only an accepted qualitative assessment reaches the deterministic production
display mapping. The numerical mapping is never sent to the LLM.

The production run attempted 480 hotels. It technically accepted 439 and
rejected 41 outputs that failed evidence-identifier provenance controls.
“Accepted” means the output passed the implemented technical controls. It does
not mean the hotel assessment was independently fact-checked, independently
human-validated or guaranteed free of every possible model error.

## Reproducibility routes

There are three different reproducibility routes. Choose the one that matches
your access level and objective.

### Route A — Public synthetic end-to-end run

Anyone can verify installation, alignment checks, clustering, dossier
generation, validation and manifest creation with the deterministic synthetic
fixture. The fixture contains no research reviews and must not be reported as a
TrustStay research result.

Requirements:

- Python 3.11 or newer;
- enough local space for the pinned Python dependencies and generated fixture;
  and
- no API key.

```bash
git clone https://github.com/runakogitss/truststayrecommendersystem.git
cd truststayrecommendersystem

python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python scripts/make_smoke_fixture.py --output /tmp/truststay_smoke_sample
python scripts/run_handover.py \
  --sample-dir /tmp/truststay_smoke_sample \
  --output-dir /tmp/truststay_smoke_output

python -m pytest -q
```

The expected final messages are `RESULT ALL STEPS PASSED` and a passing pytest
summary. On 21 August 2026, the repository produced 48/48 passing tests and the
synthetic run produced six full plus six compact dossiers from 240 reviews.

Windows users can replace the `/tmp/...` locations with folders under
`$env:TEMP`.

### Route B — Controlled deterministic Layer 1 rerun

The public clone is code- and documentation-complete but intentionally not
data-complete. An authorized researcher or examiner with the separate private
handover package can place the frozen files under
`data/frozen_research_sample/` and run:

```bash
python scripts/run_handover.py
```

The run validates the supplied sample, constructs the Layer 1 dossiers,
validates them and writes submission manifests. It requires no API key and does
not rerun DeBERTa or MiniLM inference; it reuses the supplied verified upstream
artifacts.

See [`HANDOVER_RUNBOOK.md`](HANDOVER_RUNBOOK.md) for the controlled-data route.

### Route C — Optional full ABSA GPU refresh

The production full-ABSA run has already been completed. Authorized researchers
with the private sample and a compatible CUDA environment can independently
repeat it using:

```bash
python scripts/run_full_absa_refresh.py --smoke-test --device cuda --batch-size 4
python scripts/run_full_absa_refresh.py --device cuda
python scripts/run_full_absa_refresh.py --validate-only
```

See [`FULL_ABSA_RERUN_README.md`](FULL_ABSA_RERUN_README.md) for model,
dependency, checkpointing and validation details. A new run may download model
weights and is not required for the public synthetic check.

### Optional Layer 2 dry run and model execution

The Layer 2 runner operates on a controlled ZIP of full Layer 1 dossiers. A
no-cost dry run validates the dossier collection and calculates the logical call
plan without calling an external model:

```bash
cd layer2/implementation
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python run_layer2.py \
  --input /path/to/full_dossiers.zip \
  --output ./layer2_outputs \
  --dry-run
```

Actual Layer 2 inference requires a compatible configured provider and an API
key supplied only through the environment. Never place a real key in the
repository. See
[`layer2/implementation/README.md`](layer2/implementation/README.md) for the
frozen production configuration, pilot workflow, resume behavior and validation
scope.

## Repository map

| Path | Purpose |
|---|---|
| [`src/truststay_evidence/`](src/truststay_evidence/) | Layer 1 evidence-engine modules |
| [`scripts/`](scripts/) | Sample validation, handover execution, ABSA refresh and diagnostics |
| [`configs/`](configs/) | Frozen grouping, temporal-window and ABSA category settings |
| [`schemas/`](schemas/) | Review-record and hotel-dossier JSON schemas |
| [`tests/`](tests/) | Unit, negative, determinism, portability and end-to-end tests |
| [`outputs/frozen_research_run/`](outputs/frozen_research_run/) | Safe aggregate Layer 1 validation and manifest evidence |
| [`outputs/frozen_research_run_full_absa/`](outputs/frozen_research_run_full_absa/) | Completed full-ABSA validation, provenance and cluster-invariance records |
| [`layer2/methodology/`](layer2/methodology/) | Frozen rubric, prompts, schemas and display mapping |
| [`layer2/implementation/`](layer2/implementation/) | Layer 2 runner, adapter, example configuration and dry-run plan |
| [`layer2/audit/`](layer2/audit/) | Safe production summaries, run manifest and cross-layer audit |
| [`layer2/examples/`](layer2/examples/) | Review-free accepted/rejected trace metadata |
| [`archive/historical_development/`](archive/historical_development/) | Superseded development records, clearly separated from the live pipeline |

## Public and restricted artifacts

| Public GitHub repository | Restricted research/examiner package |
|---|---|
| Code and tests | Frozen review-bearing sample |
| Frozen configurations and schemas | Full and compact hotel dossiers |
| Rubric, prompts and display mapping | Complete per-hotel Layer 2 outputs |
| Aggregate validation summaries | Verbatim review-bearing accepted/rejected traces |
| Safe production metadata | Participant-level data and qualitative responses |
| Review-free example traces | Controlled experiment file while live backend configuration is present |
| Checksums and provenance descriptions | Private immutable provenance records containing execution-environment details |

These exclusions protect research participants, guest-review text, credentials
and controlled source material. Their absence from GitHub is an intentional
data-governance boundary, not evidence that the recorded production runs were
not executed.

## What is deterministic, and what is not

### Deterministic after frozen upstream inputs

- identity and alignment checks;
- hash verification;
- complete-linkage cluster construction;
- counts and temporal summaries;
- representative selection;
- dossier schema validation;
- Layer 2 provenance checks; and
- final production display mapping.

### Procedurally reproducible, not guaranteed byte-identical

- DeBERTa inference when model/runtime versions or hardware differ; and
- Layer 2 LLM ledger extraction and qualitative adjudication.

The prompts, schemas, rubric, model configuration and validators make these
stages inspectable and repeatable as procedures, but a future LLM execution need
not reproduce identical wording or identical qualitative output bytes.

## Important interpretation boundaries

1. **No fake-review detector.** TrustStay begins from an accepted review corpus.
   Review-authenticity screening is treated as an upstream platform or dataset
   responsibility and is outside this pipeline.
2. **Reported claims are not verified facts.** Hash and provenance checks show
   where a claim came from; they do not prove that the claim is true.
3. **Similarity is not corroboration.** Semantic groups organize related
   language but do not establish reviewer independence or factual agreement.
4. **Bands are qualitative evidence-pattern categories.** They are not
   calibrated probabilities, objective hotel-quality grades or booking
   recommendations.
5. **Acceptance is technical.** The 439 accepted Layer 2 outputs passed the
   implemented controls; they were not all independently human-adjudicated.
6. **The experiment used a frozen stimulus.** The study hotel's qualitative
   assessment was paired with a pre-fieldwork 3.2/5 research display anchor.
   The later production display mapping should not be read as the historical
   generator of that experimental anchor.
7. **Cross-layer byte identity is limited.** Raw-corpus continuity is strongly
   established across the 480 hotels, but the exact historical full-ABSA Layer
   1 dossier release consumed by Layer 2 is not available for byte-level
   comparison. The public audit therefore records `NOT ESTABLISHED FROM
   AVAILABLE ARTIFACTS` rather than silently repairing the gap.

Read [`METHODOLOGY_BOUNDARIES.md`](METHODOLOGY_BOUNDARIES.md),
[`LIMITATIONS.md`](LIMITATIONS.md) and the
[`Layer 1-to-Layer 2 provenance audit`](layer2/audit/layer1_to_layer2_provenance_audit.md)
before making substantive claims from the system.

## Validation and integrity evidence

Authoritative public records include:

- [`run_summary.json`](outputs/frozen_research_run/validation/run_summary.json):
  completed Layer 1 counts and runtime;
- [`dossier_validation.json`](outputs/frozen_research_run/validation/dossier_validation.json):
  dossier coverage and schema checks;
- [`FULL_ABSA_VALIDATION.md`](outputs/frozen_research_run_full_absa/FULL_ABSA_VALIDATION.md):
  full-ABSA coverage and verdict;
- [`cluster_invariance_check.json`](outputs/frozen_research_run_full_absa/cluster_invariance_check.json):
  frozen-membership comparison;
- [`production_run_summary.json`](layer2/audit/production_run_summary.json):
  Layer 2 workload and outcomes; and
- [`layer2/SHA256SUMS.txt`](layer2/SHA256SUMS.txt): public Layer 2 artifact
  checksums.

To verify the Layer 2 public package from the repository root:

```bash
cd layer2
shasum -a 256 -c SHA256SUMS.txt
```

## Project status

TrustStay is a completed dissertation research artifact and reproducibility
record. It is not a production hotel-ranking service, a live booking product or
a validated replacement for existing platform ratings.

Reproducibility bugs and documentation issues may be reported through GitHub
Issues. Do not attach raw reviews, participant data, API keys or other restricted
material to a public issue.

## Citation and license

When citing the repository, include the repository URL, the exact release tag or
commit and the associated dissertation title. Formal citation metadata can be
added once the final bibliographic details are confirmed.

No open-source license has yet been selected. Until a license file is added,
public visibility does not by itself grant permission to copy, modify or
redistribute the code beyond rights provided by applicable law.
