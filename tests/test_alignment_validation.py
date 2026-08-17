"""The reviews / features / embeddings alignment triple must fail loudly."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from conftest import make_embeddings, make_frame
from truststay_evidence.config import PipelineConfig, load_sample_paths
from truststay_evidence.frozen_sample import write_embeddings, write_hash_manifest, write_sample_definition
from truststay_evidence.validation import ValidationFailure, validate_frozen_sample

FEATURE_KEEP = [
    "source_dataset", "hotel_id", "review_id", "review_date", "rating", "review_text", "text_sha256",
    "input_row_position", "minilm_embedding_row", "minilm_verified", "absa_aspect", "absa_sentiment",
    "absa_confidence", "absa_method", "absa_reusable_status", "duplicate_group_id",
]


def _write_sample(directory, n=12, drop_last_embedding=False, shuffle_embeddings=False, corrupt_text_hash=False):
    directory.mkdir(parents=True, exist_ok=True)
    frame = make_frame(n)
    features = frame[FEATURE_KEEP].copy()
    features["cluster_id"] = ""
    if corrupt_text_hash:
        features.loc[0, "text_sha256"] = "0" * 64
    reviews = pd.DataFrame(
        {
            "review_id": frame["review_id"],
            "hotel_id": frame["hotel_id"],
            "review_date": frame["review_date"],
            "rating_normalized_5": frame["rating"],
            "text": frame["review_text"],
        }
    )
    vectors = make_embeddings(n)
    ids = frame["review_id"].tolist()
    if drop_last_embedding:
        vectors, ids = vectors[:-1], ids[:-1]
    if shuffle_embeddings:
        ids = ids[::-1]
    reviews.to_parquet(directory / "reviews.parquet", index=False)
    features.to_parquet(directory / "features.parquet", index=False)
    write_embeddings(directory / "embeddings.npz", vectors, ids, "sentence_transformers")
    pd.DataFrame(
        {
            "sample_row_position": np.arange(n, dtype=np.int64),
            "review_id": frame["review_id"].astype(str),
            "hotel_id": frame["hotel_id"].astype(str),
            "source_input_row_position": frame["input_row_position"].to_numpy(dtype=np.int64),
            "source_minilm_embedding_row": frame["minilm_embedding_row"].to_numpy(dtype=np.int64),
        }
    ).to_parquet(directory / "review_hotel_mapping.parquet", index=False)
    write_sample_definition(
        directory / "sample_definition.json",
        {
            "schema_version": "2.0.0", "sampling_unit": "hotel_id", "method": "test",
            "seed": 1, "target_reviews": n, "selected_hotel_count": 1,
            "selected_review_count": n, "does_not_truncate_hotels": True,
            "hotel_ids": sorted(frame["hotel_id"].unique().tolist()),
        },
    )
    (directory / "SOURCE_PROVENANCE.json").write_text('{"upstream_sources": {}}\n')
    write_hash_manifest(directory, ["reviews.parquet", "features.parquet", "embeddings.npz", "review_hotel_mapping.parquet", "sample_definition.json", "SOURCE_PROVENANCE.json"])
    return load_sample_paths(directory)


def test_aligned_sample_passes(tmp_path):
    paths = _write_sample(tmp_path / "sample")
    report = validate_frozen_sample(paths, PipelineConfig())
    assert report["status"] == "PASS"
    assert report["row_counts"]["reviews"] == report["row_counts"]["features"] == report["row_counts"]["embeddings"] == 12


def test_missing_embedding_row_fails(tmp_path):
    paths = _write_sample(tmp_path / "sample", drop_last_embedding=True)
    with pytest.raises(ValidationFailure, match="Row-count mismatch"):
        validate_frozen_sample(paths, PipelineConfig())


def test_reordered_embeddings_fail(tmp_path):
    paths = _write_sample(tmp_path / "sample", shuffle_embeddings=True)
    with pytest.raises(ValidationFailure, match="order"):
        validate_frozen_sample(paths, PipelineConfig())


def test_text_hash_tampering_fails(tmp_path):
    paths = _write_sample(tmp_path / "sample", corrupt_text_hash=True)
    with pytest.raises(ValidationFailure, match="text_sha256"):
        validate_frozen_sample(paths, PipelineConfig())


def test_file_tampering_breaks_hash_manifest(tmp_path):
    paths = _write_sample(tmp_path / "sample")
    (paths.sample_dir / "SOURCE_PROVENANCE.json").write_text('{"upstream_sources": {"tampered": true}}\n')
    with pytest.raises(ValueError, match="hash verification FAILED"):
        validate_frozen_sample(paths, PipelineConfig())


def test_missing_sample_reports_actionable_error(tmp_path):
    paths = load_sample_paths(tmp_path / "absent")
    with pytest.raises(ValidationFailure, match="export_frozen_sample"):
        validate_frozen_sample(paths, PipelineConfig())
