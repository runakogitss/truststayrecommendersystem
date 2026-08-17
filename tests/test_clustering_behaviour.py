"""Tests for the frozen final semantic grouping method."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from truststay_evidence.cluster_builder import build_hotel_clusters
from truststay_evidence.semantic_retrieval import deterministic_semantic_clusters


def test_every_review_is_assigned_to_exactly_one_cluster(frame, embeddings, config):
    clusters = build_hotel_clusters(frame, embeddings, config.semantic_similarity_threshold, config.semantic_grouping_method)
    assert len(clusters) == len(frame)
    assert clusters["review_id"].is_unique
    assert clusters["semantic_cluster_id"].notna().all()
    assert set(clusters["cluster_method"]) == {"complete_linkage"}


def test_complete_linkage_prevents_transitive_chaining():
    # A~B and B~C can each exceed a neighbour threshold while A~C does not.
    # Complete linkage must not put all three in one group.
    a = np.array([1.0, 0.0], dtype=np.float32)
    c = np.array([0.0, 1.0], dtype=np.float32)
    b = ((a + c) / np.linalg.norm(a + c)).astype(np.float32)
    vectors = np.vstack([a, b, c])
    frame = pd.DataFrame({
        "hotel_id": ["H"] * 3,
        "review_id": ["r1", "r2", "r3"],
        "review_date": ["2018-01-01", "2018-02-01", "2018-03-01"],
    })
    threshold = float(np.dot(a, b)) - 0.01
    assert float(np.dot(a, c)) < threshold
    result = deterministic_semantic_clusters(frame, vectors, threshold, "complete_linkage")
    assert result["semantic_cluster_id"].nunique() == 2


def test_every_complete_linkage_cluster_respects_pairwise_threshold(frame, embeddings, config):
    result = build_hotel_clusters(frame, embeddings, config.semantic_similarity_threshold, config.semantic_grouping_method)
    lookup = frame.reset_index(drop=True).copy()
    lookup["_row"] = range(len(lookup))
    merged = lookup.merge(result[["review_id", "semantic_cluster_id"]], on="review_id", validate="one_to_one")
    for _, group in merged.groupby("semantic_cluster_id"):
        rows = group["_row"].to_numpy()
        if len(rows) <= 1:
            continue
        sim = cosine_similarity(embeddings[rows])
        mask = ~np.eye(len(rows), dtype=bool)
        assert float(sim[mask].min()) + 1e-6 >= config.semantic_similarity_threshold


def test_zero_norm_embedding_fails_loudly():
    frame = pd.DataFrame({"hotel_id": ["H"], "review_id": ["r1"], "review_date": ["2018-01-01"]})
    with np.testing.assert_raises(ValueError):
        deterministic_semantic_clusters(frame, np.zeros((1, 4), dtype=np.float32), 0.80, "complete_linkage")
