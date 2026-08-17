# TrustStay Layer 2 public file manifest

This manifest describes the intentionally public, non-data-bearing package. No private production file was moved or modified.

## Included

### Methodology

- Frozen runtime rubric
- Frozen Layer 2A and Layer 2B prompts
- Layer 2A chunk-ledger schema
- Layer 2B hotel-assessment schema
- Deterministic display mapping

### Implementation

- Original deterministic/API runner
- Codex-native adapter
- Configuration example
- Verified dry-run plan
- Requirements and implementation README

### Audit

- Production audit record
- Production JSON and Markdown summaries
- Run manifest containing statuses and metadata only
- Layer 1-to-Layer 2 provenance audit

### Examples

- Accepted-hotel manifest metadata
- Rejected-hotel manifest metadata
- Rejected-hotel validator metadata containing the invalid review-ID reference, but no review text

## Explicitly excluded

- `.env` files and credentials
- API keys, access tokens, session information, and Codex/ChatGPT authentication material
- `full_dossiers/` and all raw review datasets
- Verbatim guest-review text or review-bearing corpora
- `.codex_tmp/`
- Complete Codex logs
- Per-hotel production output directories
- ZIP files containing review-bearing data
- Raw accepted/rejected model outputs that could contain evidence text

## Scan note

The implementation README and original runner contain the literal configuration variable name `OPENCODE_GO_API_KEY` because they document the original runner interface. No key value, bearer token, session value, or secret material is present.
