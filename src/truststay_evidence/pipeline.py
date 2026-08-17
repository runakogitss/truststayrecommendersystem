"""Layer 1 execution over the self-contained frozen research sample.

Layer 1 ends at the evidence dossier. Nothing in this module produces an LLM
call, a severity or recurrence judgement, a hotel-quality estimate, a TrustStay
score, an A-H band, a recommendation or any interface output.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd

from .cluster_builder import build_hotel_clusters
from .config import PipelineConfig, SamplePaths, package_root
from .diagnostics import aggregate_diagnostics, hotel_diagnostics
from .dossier_builder import build_full_dossier, write_dossier_pair
from .embedding_access import open_embeddings
from .frozen_sample import load_features, load_sample_definition
from .provenance import environment_record, write_json


def _peak_rss_mb() -> float:
    """Return the process peak resident set size in MB on supported platforms."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.WinDLL("kernel32", use_last_error=True).GetCurrentProcess()
        get_process_memory_info = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
        get_process_memory_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), wintypes.DWORD]
        get_process_memory_info.restype = wintypes.BOOL
        if get_process_memory_info(process, ctypes.byref(counters), counters.cb):
            return round(counters.PeakWorkingSetSize / 1024 / 1024, 2)
        raise OSError("GetProcessMemoryInfo failed")

    import resource

    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports kilobytes, macOS reports bytes.
    return round(usage / 1024 / 1024, 2) if usage > 10**7 else round(usage / 1024, 2)


def _directory_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file())


def run_layer1(
    paths: SamplePaths,
    config: PipelineConfig,
    output_root: Path,
    validation_report: dict,
    hotel_limit: int | None = None,
    progress_every: int = 25,
) -> dict:
    output_root = Path(output_root)
    full_dir = output_root / "full_dossiers"
    compact_dir = output_root / "compact_dossiers"
    diag_dir = output_root / "diagnostics"
    for directory in (full_dir, compact_dir, diag_dir, output_root / "validation", output_root / "manifests"):
        directory.mkdir(parents=True, exist_ok=True)

    definition = load_sample_definition(paths.sample_definition_path)
    hotel_ids = sorted(str(v) for v in definition["hotel_ids"])
    if hotel_limit:
        hotel_ids = hotel_ids[:hotel_limit]

    source_provenance = json.loads(Path(paths.source_provenance_path).read_text())

    started = time.time()
    features_all = load_features(paths.features_path)
    embeddings = open_embeddings(
        paths.embeddings_path,
        features_all["review_id"].astype(str).tolist(),
        cache_dir=output_root / ".embedding_cache",
    )
    load_seconds = time.time() - started

    provenance = {
        "layer": "Layer 1 - evidence preparation",
        "source_mode": "precomputed_verified_artifacts",
        "inference_rerun": {
            "absa": False,
            "embeddings": False,
            "note": (
                "DeBERTa ABSA and MiniLM inference were performed upstream by the researcher. "
                "This run reruns the deterministic evidence-consolidation pipeline using the "
                "verified precomputed research artefacts supplied in data/frozen_research_sample."
            ),
        },
        "frozen_sample": {
            "sample_definition_sha256": definition.get("sample_definition_sha256"),
            "seed": definition.get("seed"),
            "selected_hotel_count": definition.get("selected_hotel_count"),
            "selected_review_count": definition.get("selected_review_count"),
        },
        "upstream_sources": source_provenance.get("upstream_sources", {}),
        "sample_hash_verification": validation_report.get("hash_verification", {}).get("status", "unknown"),
        "config": {
            "dataset_namespace": config.dataset_namespace,
            "semantic_grouping_method": config.semantic_grouping_method,
            "semantic_similarity_threshold": config.semantic_similarity_threshold,
            "representatives_per_cluster": config.representatives_per_cluster,
            "temporal_windows": config.temporal_windows,
        },
        "environment": environment_record(package_root()),
    }

    per_hotel_diagnostics: list[dict] = []
    hotel_records: list[dict] = []
    failures: list[dict] = []
    build_started = time.time()

    for index, hotel_id in enumerate(hotel_ids, start=1):
        try:
            subset = features_all[features_all["hotel_id"].astype(str) == hotel_id].copy()
            if subset.empty:
                raise ValueError("hotel present in the sample definition has no feature rows")
            cluster_map = build_hotel_clusters(
                subset, embeddings.embeddings, config.semantic_similarity_threshold, config.semantic_grouping_method
            )
            dossier = build_full_dossier(subset, cluster_map, embeddings.embeddings, config, provenance)
            full_path, compact_path = write_dossier_pair(
                dossier, full_dir, compact_dir, hotel_id, config.representatives_per_cluster
            )
            diagnostics = hotel_diagnostics(dossier, full_path, compact_path, config.semantic_similarity_threshold)
            per_hotel_diagnostics.append(diagnostics)
            hotel_records.append(
                {
                    "hotel_id": hotel_id,
                    "review_count": int(dossier["hotel_metadata"]["review_count"]),
                    "cluster_count": len(dossier["semantic_clusters"]),
                    "full_dossier": str(full_path.relative_to(output_root)),
                    "compact_dossier": str(compact_path.relative_to(output_root)),
                    "status": "PASS",
                }
            )
        except Exception as error:  # fail loudly, per hotel, and keep going
            failures.append({"hotel_id": hotel_id, "error": f"{type(error).__name__}: {error}"})
            print(f"  !! FAILED hotel {hotel_id}: {type(error).__name__}: {error}", flush=True)
        if progress_every and index % progress_every == 0:
            print(f"  ... {index}/{len(hotel_ids)} hotels processed", flush=True)

    build_seconds = time.time() - build_started

    write_json(diag_dir / "per_hotel_diagnostics.json", {"hotels": per_hotel_diagnostics})
    aggregate = aggregate_diagnostics(per_hotel_diagnostics, config.semantic_similarity_threshold)
    write_json(diag_dir / "cluster_diagnostics_summary.json", aggregate)

    execution = {
        "status": "PASS" if not failures else "FAIL",
        "requested_hotels": len(hotel_ids),
        "hotels_processed": len(hotel_records),
        "hotels_failed": len(failures),
        "failures": failures,
        "input_review_rows": int(validation_report["row_counts"]["reviews"]),
        "input_feature_rows": int(validation_report["row_counts"]["features"]),
        "input_embedding_rows": int(validation_report["row_counts"]["embeddings"]),
        "reviews_in_processed_hotels": sum(r["review_count"] for r in hotel_records),
        "full_dossiers_written": len(list(full_dir.glob("hotel_*_full.json"))),
        "compact_dossiers_written": len(list(compact_dir.glob("hotel_*_compact.json"))),
        "runtime_seconds": {
            "input_load": round(load_seconds, 3),
            "dossier_build": round(build_seconds, 3),
            "total": round(load_seconds + build_seconds, 3),
        },
        "peak_rss_mb": _peak_rss_mb(),
        "output_bytes": {
            "full_dossiers": _directory_bytes(full_dir),
            "compact_dossiers": _directory_bytes(compact_dir),
        },
        "embedding_cache_note": "outputs/.embedding_cache is a derived artefact and may be deleted after the run",
        "cluster_diagnostics_summary": aggregate,
        "hotels": hotel_records,
        "provenance": provenance,
    }
    write_json(output_root / "validation" / "execution_record.json", execution)
    return execution


def validate_outputs(output_root: Path) -> dict:
    """Structural validation of generated dossiers. Raises on failure."""
    from .schemas import assert_dossier_shape, assert_review_record_shape

    output_root = Path(output_root)
    full_dir = output_root / "full_dossiers"
    compact_dir = output_root / "compact_dossiers"
    full_files = sorted(full_dir.glob("hotel_*_full.json"))
    if not full_files:
        raise ValueError(f"No full dossiers found in {full_dir}")

    results = []
    for path in full_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert_dossier_shape(data)
        record_ids, cluster_of = set(), {}
        for record in data["review_evidence_records"]:
            assert_review_record_shape(record)
            review_id = str(record["review_id"])
            if review_id in record_ids:
                raise ValueError(f"Duplicate review_id {review_id} in {path.name}")
            record_ids.add(review_id)
            cluster_of[review_id] = record["semantic_cluster_id"]

        clustered = 0
        for cluster in data["semantic_clusters"]:
            clustered += int(cluster["unique_review_count"])
            for review_id in cluster["representative_review_ids"]:
                if review_id not in record_ids:
                    raise ValueError(f"Representative {review_id} is not a source review in {path.name}")
                if cluster_of[review_id] != cluster["semantic_cluster_id"]:
                    raise ValueError(f"Representative {review_id} assigned to the wrong cluster in {path.name}")
        if clustered != len(record_ids):
            raise ValueError(
                f"Cluster membership ({clustered}) does not cover every review ({len(record_ids)}) in {path.name}"
            )

        compact_path = compact_dir / path.name.replace("_full.json", "_compact.json")
        if not compact_path.is_file():
            raise ValueError(f"Missing compact dossier for {path.name}")
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert_dossier_shape({**compact, "review_evidence_records": []})
        if compact["hotel_id"] != data["hotel_id"]:
            raise ValueError(f"Compact/full hotel_id mismatch for {path.name}")
        if len(compact["semantic_clusters"]) != len(data["semantic_clusters"]):
            raise ValueError(f"Compact/full cluster count mismatch for {path.name}")

        forbidden = {"score", "band", "recommendation", "severity_judgement", "quality_score", "risk_grade"}
        blob = json.dumps(data).lower()
        leaked = sorted(t for t in forbidden if f'"{t}"' in blob)
        if leaked:
            raise ValueError(f"Layer 1 dossier {path.name} contains downstream judgement key(s): {leaked}")

        results.append(
            {
                "hotel_id": data["hotel_id"],
                "review_count": len(record_ids),
                "cluster_count": len(data["semantic_clusters"]),
                "full_dossier": path.name,
                "compact_dossier": compact_path.name,
                "status": "PASS",
            }
        )

    return {
        "status": "PASS",
        "full_dossier_count": len(results),
        "compact_dossier_count": len(sorted(compact_dir.glob("hotel_*_compact.json"))),
        "total_reviews_in_dossiers": sum(r["review_count"] for r in results),
        "total_clusters": sum(r["cluster_count"] for r in results),
        "dossiers": results,
    }
