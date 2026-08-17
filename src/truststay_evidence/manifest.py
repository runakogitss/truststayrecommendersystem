"""Submission manifest generation (JSON, CSV and Markdown)."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .frozen_sample import read_hash_manifest
from .provenance import environment_record, hash_tree, write_json


def create_submission_manifest(
    package_root: Path,
    paths,
    config,
    output_root: Path,
    validation: dict,
    execution: dict,
    output_validation: dict,
) -> dict:
    package_root = Path(package_root)
    output_root = Path(output_root)
    manifest_dir = output_root / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    sample_hashes = read_hash_manifest(paths.hash_manifest_path)
    output_files = hash_tree(output_root, relative_to=package_root)
    code_files = [
        record
        for directory in ("src", "scripts", "configs", "schemas", "tests")
        for record in hash_tree(package_root / directory, relative_to=package_root)
    ]
    doc_files = [
        {"path": p.name, "sha256": h["sha256"], "size_bytes": h["size_bytes"]}
        for p in sorted(package_root.glob("*.md"))
        for h in hash_tree(p, relative_to=package_root)
        if h["path"] == p.name
    ]

    payload = {
        "package": "TrustStay_Layer1_Reproducible_Evidence_Engine",
        "layer": "Layer 1 only - evidence preparation, ends at the evidence dossier",
        "version": __version__,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "environment": environment_record(package_root),
        "configuration": {
            "dataset_namespace": config.dataset_namespace,
            "semantic_grouping_method": config.semantic_grouping_method,
            "semantic_similarity_threshold": config.semantic_similarity_threshold,
            "representatives_per_cluster": config.representatives_per_cluster,
            "temporal_windows": config.temporal_windows,
            "allowed_absa_methods": list(config.allowed_absa_methods),
        },
        "frozen_sample": {
            "directory": str(paths.sample_dir.relative_to(package_root)) if paths.sample_dir.is_relative_to(package_root) else str(paths.sample_dir),
            "is_bundled_sample": paths.sample_dir.is_relative_to(package_root),
            "definition": validation["sample_definition"],
            "row_counts": validation["row_counts"],
            "absa": validation["absa"],
            "embeddings": validation["embeddings"],
            "coverage": validation["coverage"],
            "file_hashes": sample_hashes,
        },
        "upstream_sources": execution["provenance"].get("upstream_sources", {}),
        "inference_rerun": execution["provenance"]["inference_rerun"],
        "execution": {k: v for k, v in execution.items() if k not in {"hotels", "provenance", "cluster_diagnostics_summary"}},
        "cluster_diagnostics_summary": execution["cluster_diagnostics_summary"],
        "output_validation": {k: v for k, v in output_validation.items() if k != "dossiers"},
        "files": {"code_and_config": code_files, "documentation": doc_files, "outputs": output_files},
    }
    payload["hashed_file_count"] = len(code_files) + len(doc_files) + len(output_files)

    write_json(manifest_dir / "SUBMISSION_MANIFEST.json", payload)

    with (manifest_dir / "SUBMISSION_MANIFEST.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["category", "path", "sha256", "size_bytes"])
        writer.writeheader()
        for category, records in payload["files"].items():
            for record in records:
                writer.writerow({"category": category, **record})
        for name, digest in sorted(sample_hashes.items()):
            writer.writerow({"category": "frozen_research_sample", "path": name, "sha256": digest, "size_bytes": ""})

    lines = [
        "# Submission manifest",
        "",
        f"- Package: `TrustStay_Layer1_Reproducible_Evidence_Engine`",
        f"- Version: `{__version__}`",
        f"- Generated: `{payload['generated_utc']}`",
        f"- Python: `{payload['environment']['python'].split()[0]}`",
        f"- Git commit: `{payload['environment']['git_commit']}`",
        "",
        "## Frozen research sample",
        "",
        f"- Hotels: `{validation['row_counts']['hotels']}`",
        f"- Reviews: `{validation['row_counts']['reviews']}`",
        f"- Feature rows: `{validation['row_counts']['features']}`",
        f"- Embedding rows: `{validation['row_counts']['embeddings']}`",
        f"- Seed: `{validation['sample_definition']['seed']}`",
        f"- Sample definition SHA-256: `{validation['sample_definition']['sample_definition_sha256']}`",
        "",
        "## Execution",
        "",
        f"- Hotels processed: `{execution['hotels_processed']}` (failed: `{execution['hotels_failed']}`)",
        f"- Full dossiers: `{execution['full_dossiers_written']}`",
        f"- Compact dossiers: `{execution['compact_dossiers_written']}`",
        f"- Runtime (s): `{execution['runtime_seconds']['total']}`",
        f"- Peak RSS (MB): `{execution['peak_rss_mb']}`",
        f"- Output bytes: `{execution['output_bytes']}`",
        "",
        "## Boundary",
        "",
        "Layer 1 ends at the evidence dossier. No LLM interpretation, severity or",
        "recurrence judgement, hotel-quality estimate, TrustStay score, A-H band,",
        "recommendation or interface output is produced by this package.",
        "",
    ]
    (manifest_dir / "SUBMISSION_MANIFEST.md").write_text("\n".join(lines))
    return payload
