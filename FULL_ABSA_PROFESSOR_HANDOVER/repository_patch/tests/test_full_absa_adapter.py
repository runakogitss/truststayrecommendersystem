"""Focused tests for the official end-to-end ABSA refresh boundary."""

from pathlib import Path

import pandas as pd

from truststay_evidence.full_absa_adapter import (
    AspectSpec,
    _extract_entities,
    load_aspect_specs,
    result_row,
)


def test_raw_aspect_extraction_preserves_offsets_and_optional_category():
    specs = load_aspect_specs(Path("configs/full_absa_aspects.yaml"))
    text = "The mattress was comfortable but the staff were slow."
    entities = [
        {"entity_group": "ASP-Positive", "word": "mattress", "start": 4, "end": 12, "score": 0.91},
        {"entity_group": "ASP-Negative", "word": "staff", "start": 37, "end": 42, "score": 0.88},
    ]
    aspects = _extract_entities(text, entities, specs)
    assert [item["raw_aspect"] for item in aspects] == ["mattress", "staff"]
    assert [item["start"] for item in aspects] == [4, 37]
    assert aspects[0]["canonical_aspect"] == "bed"
    assert aspects[1]["sentiment"] == "negative"


def test_multiple_aspects_are_structured_not_collapsed():
    row = result_row(
        "review-1",
        [
            {
                "raw_aspect": "room",
                "canonical_aspect": "room",
                "start": 0,
                "end": 4,
                "extractor_label": "ASP-Positive",
                "aspect_extraction_score": 0.9,
                "sentiment": "positive",
                "sentiment_source": "end2end_extractor_label",
                "sentiment_score": None,
                "sentiment_scores": None,
            },
            {
                "raw_aspect": "staff",
                "canonical_aspect": "staff",
                "start": 10,
                "end": 15,
                "extractor_label": "ASP-Negative",
                "aspect_extraction_score": 0.7,
                "sentiment": "negative",
                "sentiment_source": "sentiment_model_text_pair_refinement",
                "sentiment_score": 0.8,
                "sentiment_scores": {"Positive": 0.1, "Negative": 0.8, "Neutral": 0.1},
            },
        ],
    )
    assert row["inference_status"] == "success_with_aspects"
    assert row["extracted_aspect_count"] == 2
    assert row["aspect_score_count"] == 2
    assert row["sentiment_score_count"] == 1
    assert '"raw_aspect":"room"' in row["absa_aspect_predictions_json"]
    assert '"raw_aspect":"staff"' in row["absa_aspect_predictions_json"]


def test_zero_aspect_is_success_not_failure():
    row = result_row("review-2", [])
    assert row["inference_status"] == "success_no_aspects"
    assert row["absa_method"] == "deberta_absa"
    assert row["extracted_aspect_count"] == 0


def test_runner_has_no_embedding_or_clustering_invocation():
    source = Path("scripts/run_full_absa_refresh.py").read_text(encoding="utf-8")
    assert "build_hotel_clusters" not in source
    assert "cluster_builder" not in source
    assert "sentence_transformers" not in source
    assert "adapter_infer_batch" in source


def test_refreshed_features_never_fallback_to_proxy():
    import runpy

    runner = runpy.run_path("scripts/run_full_absa_refresh.py", run_name="full_absa_test_module")
    features = pd.DataFrame(
        {
            "review_id": ["r1"],
            "hotel_id": ["h1"],
            "absa_method": ["distilled_proxy"],
            "absa_reusable_status": ["PROXY_SEPARATE_ONLY"],
            "absa_aspect": [""],
            "absa_sentiment": [""],
            "absa_confidence": [None],
        }
    )
    predictions = pd.DataFrame(
        [
            {
                "review_id": "r1",
                "absa_method": "none",
                "absa_aspect": "",
                "absa_sentiment": "",
                "absa_confidence": None,
                "inference_status": "failed_model",
                "error_message": "test",
                "absa_aspect_predictions_json": "[]",
                "absa_canonical_aspect": "",
                "extracted_aspect_count": 0,
                "aspect_score_count": 0,
                "sentiment_score_count": 0,
            }
        ]
    )
    clusters = pd.DataFrame({"review_id": ["r1"], "hotel_id": ["h1"], "semantic_cluster_id": ["h1:c1"]})
    refreshed = runner["create_refreshed_features"](features, predictions, clusters)
    assert refreshed.loc[0, "absa_method"] == "none"
    assert refreshed.loc[0, "absa_reusable_status"] == "NO_RESULT"
    assert refreshed.loc[0, "source_absa_method"] == "distilled_proxy"
