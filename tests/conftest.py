from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from truststay_evidence.config import PipelineConfig  # noqa: E402
from truststay_evidence.frozen_sample import sha256_text  # noqa: E402


@pytest.fixture
def config() -> PipelineConfig:
    return PipelineConfig()


def make_frame(n: int = 12, hotel_id: str = "HOTEL_X", seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    texts = [f"Review text number {i} about the room and the staff." for i in range(n)]
    methods = ["deberta_absa" if i % 4 == 0 else "distilled_proxy" for i in range(n)]
    status = {"deberta_absa": "REAL_MODEL_REUSABLE", "distilled_proxy": "PROXY_SEPARATE_ONLY"}
    return pd.DataFrame(
        {
            "source_dataset": "HOTELREC",
            "hotel_id": hotel_id,
            "review_id": [f"r{i:04d}" for i in range(n)],
            "review_date": pd.date_range("2015-01-01", periods=n, freq="60D").astype(str),
            "rating": [float(1 + (i % 5)) for i in range(n)],
            "review_text": texts,
            "text_sha256": [sha256_text(t) for t in texts],
            "input_row_position": np.arange(n),
            "minilm_embedding_row": np.arange(n),
            "embedding_row": np.arange(n),
            "minilm_verified": True,
            "embedding_verified": True,
            "absa_aspect": ["room;staff" if m == "deberta_absa" else "" for m in methods],
            "absa_sentiment": ["room:0.5;staff:-0.4" if m == "deberta_absa" else "" for m in methods],
            "absa_confidence": [None] * n,
            "absa_method": methods,
            "absa_reusable_status": [status[m] for m in methods],
            "duplicate_group_id": "",
            "exact_reuse": False,
        }
    )


def make_embeddings(n: int = 12, dim: int = 16, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = rng.normal(size=(3, dim))
    vectors = base[np.arange(n) % 3] + rng.normal(scale=0.02, size=(n, dim))
    return (vectors / np.linalg.norm(vectors, axis=1, keepdims=True)).astype(np.float32)


@pytest.fixture
def frame() -> pd.DataFrame:
    return make_frame()


@pytest.fixture
def embeddings() -> np.ndarray:
    return make_embeddings()
