"""Layer 1 must be deterministic and order-independent."""
from __future__ import annotations

import json

import numpy as np

from conftest import make_embeddings, make_frame
from truststay_evidence.cluster_builder import build_hotel_clusters
from truststay_evidence.config import PipelineConfig
from truststay_evidence.dossier_builder import build_full_dossier


def _dossier(frame, embeddings, config):
    clusters = build_hotel_clusters(frame, embeddings, config.semantic_similarity_threshold, config.semantic_grouping_method)
    return build_full_dossier(frame, clusters, embeddings, config, {"test": True})


def test_repeated_build_is_identical(frame, embeddings, config):
    first = json.dumps(_dossier(frame.copy(), embeddings, config), sort_keys=True)
    second = json.dumps(_dossier(frame.copy(), embeddings, config), sort_keys=True)
    assert first == second


def test_input_row_order_does_not_change_output(frame, embeddings, config):
    baseline = _dossier(frame.copy(), embeddings, config)
    shuffled = frame.sample(frac=1.0, random_state=99).reset_index(drop=True)
    reordered = _dossier(shuffled, embeddings, config)
    assert json.dumps(baseline, sort_keys=True) == json.dumps(reordered, sort_keys=True)


def test_no_rng_is_used_by_clustering(frame, embeddings, config):
    np.random.seed(1)
    first = build_hotel_clusters(frame, embeddings, config.semantic_similarity_threshold, config.semantic_grouping_method)
    np.random.seed(999)
    second = build_hotel_clusters(frame, embeddings, config.semantic_similarity_threshold, config.semantic_grouping_method)
    assert first.equals(second)
