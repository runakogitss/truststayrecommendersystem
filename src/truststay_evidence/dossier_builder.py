"""Full and compact evidence dossier construction.

SCIENTIFIC BEHAVIOUR IS UNCHANGED from the frozen Layer 1 method.  The edits in
this file are engineering only and are asserted to be output-identical by
``tests/test_compaction_equivalence.py``:

  * ``compact_from_full`` was O(clusters x reviews); it is now O(n) and emits
    byte-identical JSON.
  * ``_jsonable`` no longer raises on array-valued cells.
  * Output directories are created before writing.

Known limitations of the compact dossier that are METHODOLOGY, not bugs, and
are therefore NOT changed here (see LIMITATIONS.md, item L4):

  * Representative selection remains centroid-proximity based. Minority or
    outlying evidence can therefore be absent as text from the compact dossier,
    although every review remains in the full dossier and rating distributions
    remain visible at cluster level.

Changing either would alter which evidence a downstream layer sees and requires
researcher approval and a new frozen method version.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .absa_access import summarize_absa
from .duplicate_analysis import cluster_duplicate_summary, duplicate_summary  # noqa: F401
from .feature_index import review_records
from .representative_selection import select_representatives
from .schemas import assert_dossier_shape, assert_review_record_shape
from .temporal_features import build_temporal_summaries

DOSSIER_SCHEMA_VERSION = "0.2.0"


def _jsonable(value):
    if isinstance(value, (list, dict, tuple, set)):
        return value
    if isinstance(value, np.ndarray):
        return value.tolist()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return value
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    return value


def build_full_dossier(frame: pd.DataFrame, cluster_map: pd.DataFrame, embeddings, config, provenance: dict) -> dict:
    frame = frame.sort_values(["review_date", "review_id"], kind="mergesort").reset_index(drop=True)
    # The newly computed semantic cluster map is authoritative for this dossier.
    frame = frame.drop(columns=["semantic_cluster_id"], errors="ignore")

    records = review_records(frame, cluster_map)
    for record in records:
        record.update({key: _jsonable(value) for key, value in record.items()})
        assert_review_record_shape(record)

    merged = frame.merge(cluster_map, on="review_id", how="left", validate="one_to_one")
    if merged["semantic_cluster_id"].isna().any():
        missing = merged.loc[merged["semantic_cluster_id"].isna(), "review_id"].tolist()[:5]
        raise ValueError(f"Reviews were not assigned to a semantic cluster, e.g. {missing}")

    embedding_column = "embedding_row" if "embedding_row" in merged.columns else "minilm_embedding_row"
    clusters = []
    for cluster_id, group in merged.groupby("semantic_cluster_id", sort=True):
        cluster_rows = group.sort_values(["review_date", "review_id"], kind="mergesort")
        reps = select_representatives(cluster_rows, embeddings, config.representatives_per_cluster)
        vectors = np.asarray(embeddings[cluster_rows[embedding_column].astype(int).to_numpy()], dtype=np.float32)
        vectors = vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
        centroid = vectors.mean(axis=0)
        centroid = centroid / max(float(np.linalg.norm(centroid)), 1e-12)
        similarities = vectors @ centroid
        if len(vectors) <= 1:
            minimum_pairwise_similarity = 1.0
        else:
            pairwise = vectors @ vectors.T
            mask = ~np.eye(len(vectors), dtype=bool)
            minimum_pairwise_similarity = float(pairwise[mask].min())
        clusters.append(
            {
                "semantic_cluster_id": str(cluster_id),
                "unique_review_count": int(cluster_rows["review_id"].nunique()),
                "possible_duplicate_count": int((cluster_rows["duplicate_group_id"].fillna("").astype(str) != "").sum()),
                "exact_reuse_review_count": int(
                    cluster_rows.get("exact_reuse", pd.Series(False, index=cluster_rows.index)).fillna(False).astype(bool).sum()
                ),
                "internal_similarity_summary": {
                    "mean_to_centroid": float(similarities.mean()),
                    "minimum_to_centroid": float(similarities.min()),
                    "maximum_to_centroid": float(similarities.max()),
                    "minimum_pairwise_similarity": minimum_pairwise_similarity,
                },
                "earliest_date": str(cluster_rows["review_date"].min()),
                "latest_date": str(cluster_rows["review_date"].max()),
                "rating_distribution": {str(k): int(v) for k, v in cluster_rows["rating"].value_counts().sort_index().items()},
                "absa_method_distribution": cluster_rows["absa_method"].astype(str).value_counts().to_dict(),
                "aspect_distribution": sorted(
                    {a for v in cluster_rows["absa_aspect"].fillna("").astype(str) for a in v.split(";") if a}
                ),
                "representative_review_ids": reps,
                "independence_claim": "not_established",
            }
        )

    metadata = {
        "hotel_id": str(frame["hotel_id"].iloc[0]),
        "review_count": len(frame),
        "minimum_review_date": str(frame["review_date"].min()),
        "maximum_review_date": str(frame["review_date"].max()),
        "raw_mean_rating": float(frame["rating"].mean()),
        "rating_distribution": {str(k): int(v) for k, v in frame["rating"].value_counts().sort_index().items()},
        "absa": summarize_absa(frame),
        "duplicate_summary": duplicate_summary(frame),
        "source_hashes": {
            "frozen_sample_definition_sha256": str(provenance.get("frozen_sample", {}).get("sample_definition_sha256", "")),
            "upstream_locked_input_sha256": str(provenance.get("upstream_sources", {}).get("locked_input_sha256", "")),
        },
    }

    dossier = {
        "schema_version": DOSSIER_SCHEMA_VERSION,
        "dataset_namespace": config.dataset_namespace,
        "hotel_id": str(frame["hotel_id"].iloc[0]),
        "hotel_metadata": metadata,
        "temporal_summaries": build_temporal_summaries(frame, config.temporal_windows),
        "semantic_clusters": clusters,
        "absa_evidence": summarize_absa(frame),
        "review_evidence_records": records,
        "provenance": provenance,
        "methodology_notes": {
            "layer": "Layer 1 - evidence preparation only",
            "rubric_neutral": True,
            "embeddings_reused_without_inference": True,
            "absa_reused_without_inference": True,
            "cluster_method": config.semantic_grouping_method,
            "cluster_threshold": config.semantic_similarity_threshold,
            "representatives_per_cluster": config.representatives_per_cluster,
            "clustering_is_deterministic_no_rng_used": True,
            "independence_not_established": True,
        },
        "warnings": [
            "Proxy ABSA rows are separated from real DeBERTa rows and are never relabelled.",
            "No scoring, severity, credibility, recurrence, band, recommendation or conclusion is produced.",
            "ABSA confidence is unavailable in the verified source and is preserved as null where present.",
            "Semantic similarity is not factual truth; semantic group size is not independent corroboration; duplicate-looking evidence is not deception.",
            "Semantic groups use complete-linkage cosine clustering. At the configured threshold, all members of a non-singleton group must satisfy the complete-linkage distance bound; semantic similarity is still not evidence of factual truth or independent corroboration.",
        ],
    }
    assert_dossier_shape(dossier)
    return dossier


def compact_from_full(full: dict, max_reviews_per_cluster: int = 3) -> dict:
    """Deterministic projection of the full dossier.

    Output is identical to the previous implementation; only the lookup was
    changed from a nested scan to a single pass.
    """
    wanted: set[str] = set()
    for cluster in full["semantic_clusters"]:
        wanted.update(cluster["representative_review_ids"])
    representatives = {
        record["review_id"]: record
        for record in full["review_evidence_records"]
        if record["review_id"] in wanted
    }
    compact_clusters = [
        {
            **cluster,
            "representative_reviews": [
                representatives[rid]
                for rid in cluster["representative_review_ids"][:max_reviews_per_cluster]
                if rid in representatives
            ],
        }
        for cluster in full["semantic_clusters"]
    ]
    return {
        "schema_version": full["schema_version"],
        "dataset_namespace": full["dataset_namespace"],
        "hotel_id": full["hotel_id"],
        "hotel_metadata": full["hotel_metadata"],
        "temporal_summaries": full["temporal_summaries"],
        "semantic_clusters": compact_clusters,
        "absa_evidence": full["absa_evidence"],
        "provenance": full["provenance"],
        "warnings": full["warnings"],
        "methodology_notes": full["methodology_notes"],
    }


def _safe_name(hotel_id: str) -> str:
    """Filesystem-safe, collision-free file stem for a hotel identifier."""
    import hashlib
    import re

    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(hotel_id)).strip("_")[:80]
    digest = hashlib.sha256(str(hotel_id).encode("utf-8")).hexdigest()[:12]
    return f"{cleaned}__{digest}" if cleaned else digest


def write_dossier_pair(
    full: dict,
    full_dir: Path,
    compact_dir: Path,
    hotel_id: str,
    max_reviews_per_cluster: int = 3,
) -> tuple[Path, Path]:
    full_dir, compact_dir = Path(full_dir), Path(compact_dir)
    full_dir.mkdir(parents=True, exist_ok=True)
    compact_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_name(hotel_id)
    full_path = full_dir / f"hotel_{stem}_full.json"
    compact_path = compact_dir / f"hotel_{stem}_compact.json"
    full_path.write_text(json.dumps(full, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    compact_path.write_text(
        json.dumps(compact_from_full(full, max_reviews_per_cluster), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return full_path, compact_path
