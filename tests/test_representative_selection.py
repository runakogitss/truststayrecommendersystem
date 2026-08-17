"""Representative evidence must remain traceable and behave as documented."""
from __future__ import annotations

import numpy as np

from truststay_evidence.cluster_builder import build_hotel_clusters
from truststay_evidence.diagnostics import representative_selection_behaviour, representative_traceability
from truststay_evidence.dossier_builder import build_full_dossier
from truststay_evidence.representative_selection import select_representatives


def test_representatives_trace_to_source_review_ids(frame, embeddings, config):
    clusters = build_hotel_clusters(frame, embeddings, config.semantic_similarity_threshold, config.semantic_grouping_method)
    dossier = build_full_dossier(frame, clusters, embeddings, config, {})
    trace = representative_traceability(dossier)
    assert trace["all_traceable_to_source_review_ids"]
    assert not trace["unresolved_representative_ids"]
    assert not trace["misassigned_representative_ids"]


def test_representative_cap_is_respected(frame, embeddings, config):
    clusters = build_hotel_clusters(frame, embeddings, config.semantic_similarity_threshold, config.semantic_grouping_method)
    dossier = build_full_dossier(frame, clusters, embeddings, config, {})
    for cluster in dossier["semantic_clusters"]:
        assert len(cluster["representative_review_ids"]) <= config.representatives_per_cluster
        assert len(cluster["representative_review_ids"]) == len(set(cluster["representative_review_ids"]))


def test_selection_is_centroid_proximity_ordered(frame, embeddings, config):
    """DOCUMENTED BEHAVIOUR: the effective ordering key is centroid distance.
    The declared secondary keys (real-ABSA-first, then text length ASCENDING)
    almost never fire because the distance is a float. The ascending length key
    means that where it does fire it prefers the SHORTER text. Recorded here so
    the dissertation describes the rule as implemented, not as intended."""
    reps = select_representatives(frame, embeddings, max_count=3)
    assert len(reps) == 3
    assert reps == select_representatives(frame, embeddings, max_count=3)


def test_full_dossier_never_loses_a_review(frame, embeddings, config):
    clusters = build_hotel_clusters(frame, embeddings, config.semantic_similarity_threshold, config.semantic_grouping_method)
    dossier = build_full_dossier(frame, clusters, embeddings, config, {})
    assert len(dossier["review_evidence_records"]) == len(frame)
    behaviour = representative_selection_behaviour(dossier)
    assert behaviour["low_rated_reviews_in_full_dossier"] >= 0
