"""Deterministic hotel sampling; hotels are never truncated."""
from __future__ import annotations

import pandas as pd
import pytest

from truststay_evidence.frozen_sample import load_sample_definition
from truststay_evidence.sample import build_sample_definition, select_complete_hotels


def counts():
    return pd.Series({f"H{i:03d}": 10 + (i % 7) for i in range(60)})


def test_selection_is_deterministic():
    first, n1 = select_complete_hotels(counts(), 100, 20260812)
    second, n2 = select_complete_hotels(counts(), 100, 20260812)
    assert first == second and n1 == n2


def test_different_seed_gives_a_different_selection():
    a, _ = select_complete_hotels(counts(), 100, 20260812)
    b, _ = select_complete_hotels(counts(), 100, 1)
    assert a != b


def test_hotels_are_never_truncated():
    series = counts()
    selected, total = select_complete_hotels(series, 100, 20260812)
    assert total == sum(int(series[h]) for h in selected)
    assert total >= 100


def test_definition_is_hash_signed_and_tamper_evident(tmp_path):
    path = tmp_path / "sample_definition.json"
    payload = build_sample_definition(counts(), path, 100, 20260812)
    assert load_sample_definition(path)["sample_definition_sha256"] == payload["sample_definition_sha256"]
    text = path.read_text().replace('"target_reviews": 100', '"target_reviews": 999')
    path.write_text(text)
    with pytest.raises(ValueError, match="hash does not match"):
        load_sample_definition(path)


def test_impossible_target_fails_loudly():
    with pytest.raises(ValueError, match="target"):
        select_complete_hotels(counts(), 10**9, 20260812)
