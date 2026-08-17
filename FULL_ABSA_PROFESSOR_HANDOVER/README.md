# TrustStay Full ABSA Windows GPU Patch Handover

Package type: **PATCH PACKAGE**. This ZIP contains the final small code/config/documentation patch. It intentionally does not contain the 100,111-review dataset, frozen MiniLM embeddings, existing professor dossiers, or Hugging Face weights.

Extract this folder beside the existing TrustStay repository, then open PowerShell in the repository root and run:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\FULL_ABSA_PROFESSOR_HANDOVER\install_patch.ps1
```

The installer copies the exact packaged patch files into the repository-relative locations shown in `repository_patch\`. It refuses to proceed if the required existing frozen inputs are missing.

Then follow:

```powershell
Get-Content .\FULL_ABSA_RERUN_README.md
python -m pip install -r .\requirements_full_absa.txt
python .\scripts\run_full_absa_refresh.py --smoke-test --device cuda --batch-size 4
```

The full run requires CUDA and must be started explicitly with `--device cuda`. It writes only to `outputs\frozen_research_run_full_absa\` and never overwrites `outputs\frozen_research_run\`.

## Packaged patch contents

```text
repository_patch\FULL_ABSA_RERUN_README.md
repository_patch\FULL_ABSA_VALIDATION.md
repository_patch\requirements_full_absa.txt
repository_patch\configs\full_absa_aspects.yaml
repository_patch\scripts\run_full_absa_refresh.py
repository_patch\src\truststay_evidence\full_absa_adapter.py
repository_patch\tests\test_full_absa_adapter.py
```

## Existing repository dependencies

The installer and runner require these files to already exist in the repository:

```text
data\frozen_research_sample\reviews.parquet
data\frozen_research_sample\features.parquet
data\frozen_research_sample\embeddings.npz
data\frozen_research_sample\review_hotel_mapping.parquet
data\frozen_research_sample\sample_definition.json
data\frozen_research_sample\SHA256_MANIFEST.csv
data\frozen_research_sample\SOURCE_PROVENANCE.json
outputs\frozen_research_run\full_dossiers\*.json
requirements.txt
configs\evidence_pipeline.yaml
configs\temporal_windows.yaml
src\truststay_evidence\config.py
src\truststay_evidence\dossier_builder.py
src\truststay_evidence\embedding_access.py
src\truststay_evidence\frozen_sample.py
src\truststay_evidence\feature_index.py
src\truststay_evidence\representative_selection.py
src\truststay_evidence\temporal_features.py
src\truststay_evidence\duplicate_analysis.py
src\truststay_evidence\absa_access.py
src\truststay_evidence\schemas.py
```

No Mac-specific path is required. Hugging Face model weights are downloaded/cached on the professor's Windows workstation during the first smoke test.
