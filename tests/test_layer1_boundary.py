"""Layer 1 must end at the evidence dossier."""
from __future__ import annotations

import json
from pathlib import Path

from truststay_evidence.cluster_builder import build_hotel_clusters
from truststay_evidence.dossier_builder import build_full_dossier, compact_from_full

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_KEYS = {
    "quality_score", "score_band", "risk_grade", "truststay_score", "band",
    "recommendation", "severity_judgement", "recurrence_judgement", "confidence_judgment",
}


def _keys(node, found=None):
    found = found if found is not None else set()
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(key)
            _keys(value, found)
    elif isinstance(node, list):
        for item in node:
            _keys(item, found)
    return found


def test_dossier_contains_no_downstream_judgement_fields(frame, embeddings, config):
    clusters = build_hotel_clusters(frame, embeddings, config.semantic_similarity_threshold, config.semantic_grouping_method)
    full = build_full_dossier(frame, clusters, embeddings, config, {})
    leaked = _keys(full) & FORBIDDEN_KEYS
    assert not leaked, f"Layer 1 emitted downstream judgement keys: {leaked}"
    leaked_compact = _keys(compact_from_full(full)) & FORBIDDEN_KEYS
    assert not leaked_compact


def test_independence_is_never_asserted(frame, embeddings, config):
    clusters = build_hotel_clusters(frame, embeddings, config.semantic_similarity_threshold, config.semantic_grouping_method)
    full = build_full_dossier(frame, clusters, embeddings, config, {})
    assert full["methodology_notes"]["independence_not_established"] is True
    for cluster in full["semantic_clusters"]:
        assert cluster["independence_claim"] == "not_established"


def test_no_llm_or_network_dependency_in_source():
    banned = ("openai", "anthropic", "requests.post", "http://", "https://api")
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text().lower()
        for token in banned:
            assert token not in text, f"{path.name} references {token}; Layer 1 must not call a model or network"
