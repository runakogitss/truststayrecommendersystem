# Handover File Manifest

This ZIP is a patch package. Extract it beside the existing TrustStay repository and run `install_patch.ps1` from the repository root.

| ZIP path | Purpose |
|---|---|
| `FULL_ABSA_PROFESSOR_HANDOVER/README.md` | Package type, install command, external dependency list |
| `FULL_ABSA_PROFESSOR_HANDOVER/install_patch.ps1` | Windows installer that copies the final patch into repo-relative paths |
| `FULL_ABSA_PROFESSOR_HANDOVER/repository_patch/scripts/run_full_absa_refresh.py` | Final checkpointed ABSA runner; loads frozen clusters and never reclusters |
| `FULL_ABSA_PROFESSOR_HANDOVER/repository_patch/src/truststay_evidence/full_absa_adapter.py` | Official end-to-end aspect extractor plus documented sentiment refinement |
| `FULL_ABSA_PROFESSOR_HANDOVER/repository_patch/configs/full_absa_aspects.yaml` | Optional post-extraction canonical-category mapper; never an extraction gate |
| `FULL_ABSA_PROFESSOR_HANDOVER/repository_patch/requirements_full_absa.txt` | Targeted dependencies; CUDA PyTorch is installed separately |
| `FULL_ABSA_PROFESSOR_HANDOVER/repository_patch/FULL_ABSA_RERUN_README.md` | Windows 10/11 PowerShell GPU instructions |
| `FULL_ABSA_PROFESSOR_HANDOVER/repository_patch/FULL_ABSA_VALIDATION.md` | Preflight/full-run validation report template |
| `FULL_ABSA_PROFESSOR_HANDOVER/repository_patch/tests/test_full_absa_adapter.py` | Focused adapter, no-proxy, and no-clustering tests |
