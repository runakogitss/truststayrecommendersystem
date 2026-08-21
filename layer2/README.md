# TrustStay Layer 2 public reproducibility package

This directory contains the public, non-data-bearing implementation and audit records for the completed TrustStay Layer 2 run.

## Preserved production result

- 480 source hotels
- 100,111 source review records
- 549 Layer 2A logical chunk assessments
- 480 Layer 2B logical hotel assessments
- 439 accepted hotels
- 41 rejected hotels

The public package contains no source dossiers, guest-review text, raw production outputs, Codex logs, `.codex_tmp` files, credentials, or authentication material.

## Public versus private research packages

The private/self-contained professor handover may contain the frozen Layer 1
sample and the source dossiers required for a full rerun. This public Layer 2
package contains only code, frozen methodology, validation summaries, provenance
metadata, checksums, and safe audit records. It is intentionally not a
self-contained review-data distribution.

“Accepted” means that a Layer 2 output passed the implemented technical
acceptance controls. It does not mean the hotel interpretation was independently
fact-checked or human-validated, that every possible LLM error was detected, or
that TrustStay prevents hallucinations.

The raw corpus is traceable across the 480 hotels, but the exact historical
intermediate Layer 1 dossier version consumed by Layer 2 remains
`NOT ESTABLISHED FROM AVAILABLE ARTIFACTS`; the public package does not claim
byte identity to the completed full-ABSA dossier release.

## Contents

- `methodology/`: frozen rubric, prompts, schemas, and deterministic display mapping.
- `implementation/`: runner, Codex adapter, configuration example, dry-run plan, requirements, and implementation README.
- `audit/`: production audit records, summaries, manifest, and cross-layer provenance audit.
- `examples/`: metadata-only accepted/rejected trace records. These do not contain review text.
- `PUBLIC_FILE_MANIFEST.md`: inclusion and exclusion inventory.
- `SHA256SUMS.txt`: checksums for the public files in this directory.

## Execution note

`implementation/run_layer2.py` preserves the original OpenCode Go runner. The completed production execution used `implementation/codex_luna_adapter.py`, which invokes the Codex CLI with ChatGPT-managed authentication. No authentication material is included here.

The public package is documentation and reproducibility evidence only. It is not a replacement for the private source dossiers or production output directory.
