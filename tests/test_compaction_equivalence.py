"""The O(n) compaction must be byte-identical to the original nested-scan form."""
from __future__ import annotations

import json

from truststay_evidence.cluster_builder import build_hotel_clusters
from truststay_evidence.dossier_builder import build_full_dossier, compact_from_full


def _legacy_compact(full: dict, max_reviews_per_cluster: int = 3) -> dict:
    """Verbatim behaviour of the previous implementation, kept as an oracle."""
    representatives = {
        review["review_id"]: review
        for cluster in full["semantic_clusters"]
        for review in full["review_evidence_records"]
        if review["review_id"] in cluster["representative_review_ids"]
    }
    compact_clusters = []
    for cluster in full["semantic_clusters"]:
        compact_clusters.append(
            {
                **cluster,
                "representative_reviews": [
                    representatives[rid]
                    for rid in cluster["representative_review_ids"][:max_reviews_per_cluster]
                    if rid in representatives
                ],
            }
        )
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


def test_optimised_compaction_matches_legacy_output(frame, embeddings, config):
    clusters = build_hotel_clusters(frame, embeddings, config.semantic_similarity_threshold, config.semantic_grouping_method)
    full = build_full_dossier(frame, clusters, embeddings, config, {})
    new = json.dumps(compact_from_full(full, 3), sort_keys=True, ensure_ascii=False)
    old = json.dumps(_legacy_compact(full, 3), sort_keys=True, ensure_ascii=False)
    assert new == old


def test_compact_keeps_group_metadata_for_unselected_evidence(frame, embeddings, config):
    """Compaction drops non-representative TEXT but never hides that it existed."""
    clusters = build_hotel_clusters(frame, embeddings, config.semantic_similarity_threshold, config.semantic_grouping_method)
    full = build_full_dossier(frame, clusters, embeddings, config, {})
    compact = compact_from_full(full, 3)
    assert len(compact["semantic_clusters"]) == len(full["semantic_clusters"])
    for original, projected in zip(full["semantic_clusters"], compact["semantic_clusters"]):
        assert projected["unique_review_count"] == original["unique_review_count"]
        assert projected["rating_distribution"] == original["rating_distribution"]
        assert projected["independence_claim"] == "not_established"
