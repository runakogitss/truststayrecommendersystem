"""Proxy ABSA output must never be presented as direct DeBERTa inference."""
from __future__ import annotations

import pandas as pd
import pytest

from conftest import make_frame
from truststay_evidence.absa_access import absa_status, summarize_absa
from truststay_evidence.config import PipelineConfig, load_sample_paths
from truststay_evidence.validation import ValidationFailure, validate_frozen_sample
from test_alignment_validation import _write_sample


def test_status_mapping_is_separate():
    assert absa_status("deberta_absa") == "REAL_MODEL_REUSABLE"
    assert absa_status("distilled_proxy") == "PROXY_SEPARATE_ONLY"
    assert absa_status("none") == "NO_RESULT"
    assert absa_status("deberta_absa") != absa_status("distilled_proxy")


def test_summary_keeps_counts_separate():
    summary = summarize_absa(make_frame(12))
    assert summary["real_model_review_count"] == 3
    assert summary["proxy_review_count"] == 9
    assert summary["real_model_review_count"] + summary["proxy_review_count"] == 12


def test_relabelled_proxy_row_is_rejected(tmp_path):
    paths = _write_sample(tmp_path / "sample")
    features = pd.read_parquet(paths.features_path)
    proxy = features.index[features["absa_method"] == "distilled_proxy"][0]
    features.loc[proxy, "absa_reusable_status"] = "REAL_MODEL_REUSABLE"
    features.to_parquet(paths.features_path, index=False)
    with pytest.raises(ValidationFailure, match="never be presented as direct DeBERTa"):
        validate_frozen_sample(paths, PipelineConfig(), verify_hashes=False)
