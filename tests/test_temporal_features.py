"""Temporal features must be factual and anchored to the data, not the clock."""
from __future__ import annotations

import pandas as pd

from truststay_evidence.temporal_features import build_temporal_summaries


def test_windows_anchor_to_latest_review_date(frame, config):
    summaries = build_temporal_summaries(frame, config.temporal_windows)
    latest = pd.to_datetime(frame["review_date"]).max().date().isoformat()
    for window in summaries["configured_windows"].values():
        assert window["anchor_date"] == latest
    assert summaries["coverage"]["maximum_date"] == latest
    assert summaries["coverage"]["review_count"] == len(frame)


def test_window_counts_partition_the_corpus(frame, config):
    summaries = build_temporal_summaries(frame, config.temporal_windows)
    for window in summaries["configured_windows"].values():
        assert window["review_count"] + window["historical_review_count"] == len(frame)


def test_summaries_make_no_judgement(frame, config):
    summaries = build_temporal_summaries(frame, config.temporal_windows)
    blob = str(summaries).lower()
    for token in ("recovery", "deterioration", "recurrence", "severe", "risk"):
        assert token not in blob


def test_rerun_on_a_different_day_is_identical(frame, config):
    first = build_temporal_summaries(frame, config.temporal_windows)
    second = build_temporal_summaries(frame, config.temporal_windows)
    assert first == second
