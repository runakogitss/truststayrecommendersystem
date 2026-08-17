# TrustStay 100K Layer 2 — GPT-5.6 Luna via OpenCode Go

This package adds the LLM assessment layer to `full_dossiers.zip`.

## What it does

```text
480 frozen Layer-1 hotel dossiers
        ↓
Layer 2A: chronological evidence-ledger extraction
        ↓
Layer 2B: frozen rubric hotel adjudication
        ↓
A-H band + upper/middle/lower + evidence IDs
        ↓
local validation against the original dossier
        ↓
deterministic display translation
```

**Fairmont Dallas is excluded.**

The numeric 5-point mapping is never sent to the model. It is applied locally only after the qualitative assessment passes validation.

## Why two LLM stages?

Some full dossiers are too large for a comfortable one-shot assessment. The runner therefore applies the same scalable process to every hotel:

1. Every review is read by GPT-5.6 Luna in chronological chunks.
2. Each chunk becomes a traceable evidence ledger containing exact review IDs.
3. A final call applies the frozen TrustStay rubric across all ledgers.
4. The final output is checked against the original dossier.

Layer 2A is explicitly forbidden from assigning a band or numeric score.

## OpenCode Go configuration

The runner defaults to:

- provider: OpenCode Go
- model: `gpt-5.6-luna`
- base URL: `https://opencode.ai/zen/go/v1`
- endpoint: `/responses`
- reasoning effort: `medium`
- `store: false`

## Install

```bash
cd TrustStay_Layer2_GPT56_Luna_100K
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Add your API key

macOS/Linux:

```bash
export OPENCODE_GO_API_KEY="YOUR_KEY"
```

PowerShell:

```powershell
$env:OPENCODE_GO_API_KEY="YOUR_KEY"
```

Do not put the real key in source control.

## 1. Run a no-cost preflight first

```bash
python run_layer2.py \
  --input /path/to/full_dossiers.zip \
  --output ./layer2_outputs \
  --dry-run
```

This reads and validates all dossiers and calculates the exact API call plan without calling the model.

## 2. Pilot on 5 hotels

```bash
python run_layer2.py \
  --input /path/to/full_dossiers.zip \
  --output ./layer2_outputs \
  --max-hotels 5
```

Inspect those five results before running all 480.

## 3. Run the 480-hotel corpus

```bash
python run_layer2.py \
  --input /path/to/full_dossiers.zip \
  --output ./layer2_outputs \
  --workers 2
```

The default is intentionally conservative. You can raise `--workers` if the provider tolerates it.

## Resume behavior

Just run the same command again.

Completed hotel assessments and completed chunk ledgers are reused. Failed hotels are isolated in `failures.jsonl`.

Use `--force` only when you intentionally want to regenerate existing outputs.

## Output structure

```text
layer2_outputs/
├── run_manifest.json
├── assessments.jsonl
├── failures.jsonl                 # only if failures occur
└── hotels/
    └── <hotel_slug>/
        ├── assessment.json
        ├── run_metadata.json
        └── ledgers/
            ├── 001_of_001.json
            └── 001_of_001.api.json
```

`assessment.json` is the validated final output. It contains the qualitative Layer-2 fields plus:

- `display_anchor`
- `display_mapping_version`
- `display_mapping_warning`
- `validation_warnings`

Those fields are added by local code, not by the LLM.

## Audit protections

The runner checks:

- source dossier structure;
- declared vs embedded review counts;
- duplicate review IDs within each hotel;
- hotel-ID consistency;
- every review-text SHA-256;
- chunk-ledger cited review IDs;
- final cited review IDs;
- band-to-label consistency;
- recurrence requires multiple distinct concern review IDs;
- C2/C3 requires evidence on distinct dates.

The rubric says C2 requires distinct *periods* but does not freeze a numerical time-gap definition. The runner therefore does **not invent one**. It hard-checks distinct dates and raises a manual-review warning if cited C2/C3 evidence remains within one calendar month.

## Important research note

This is a hierarchical LLM implementation of Layer 2. It should be documented as such in the technical appendix:

- Layer 2A performs evidence compression/extraction from all source review text.
- Layer 2B performs the actual rubric-based hotel assessment.
- The participant-facing 5-point value is a deterministic post-inference translation.

Do not describe the 5-point anchor as an LLM-generated hotel-quality score.

## Recommended run order

1. `--dry-run` on all 480.
2. run `--max-hotels 5`;
3. manually inspect evidence IDs against source reviews;
4. run another stratified 10–20 hotel QA set if desired;
5. freeze code + rubric + schemas by hash;
6. run all 480;
7. archive `run_manifest.json`, outputs, rubric, schemas, and source ZIP hash together.

## Verified against the supplied 100K corpus

A local no-API dry run on `full_dossiers.zip` completed successfully on 16 August 2026:

- 480 hotel dossiers
- 100,111 reviews
- 549 Layer 2A chunk calls
- 480 Layer 2B final calls
- 1,029 total planned API calls
- maximum 9 chunks for one hotel

These counts are specific to the supplied corpus and the default 180,000-token chunk budget.
