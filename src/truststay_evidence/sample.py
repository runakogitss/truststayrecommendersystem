"""Deterministic complete-hotel sampling.

The sampling unit is the hotel.  No hotel's review history is ever truncated,
so the realised review count normally exceeds the target: the final selected
hotel is always included in full.  This is a scientific property of the design,
not a rounding artefact, and must not be "fixed".
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from .frozen_sample import write_sample_definition

METHOD_DESCRIPTION = "sha256(seed + ':' + hotel_id) stable ordering, prefix until target reached, hotels never truncated"


def stable_rank(hotel_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{hotel_id}".encode("utf-8")).hexdigest()


def select_complete_hotels(hotel_review_counts: "pd.Series", target_reviews: int, seed: int) -> tuple[list[str], int]:
    if target_reviews <= 0:
        raise ValueError("target_reviews must be positive")
    ranked = sorted(
        (stable_rank(str(hotel_id), seed), str(hotel_id), int(count))
        for hotel_id, count in hotel_review_counts.items()
    )
    selected: list[str] = []
    review_count = 0
    for _, hotel_id, count in ranked:
        selected.append(hotel_id)
        review_count += count
        if review_count >= target_reviews:
            break
    if review_count < target_reviews:
        raise ValueError(f"Input contains only {review_count} reviews; target is {target_reviews}")
    return selected, review_count


def build_sample_definition(
    hotel_review_counts: "pd.Series",
    output_path: Path,
    target_reviews: int,
    seed: int,
    source_description: str = "",
) -> dict:
    selected, review_count = select_complete_hotels(hotel_review_counts, target_reviews, seed)
    payload = {
        "schema_version": "2.0.0",
        "sampling_unit": "hotel_id",
        "method": METHOD_DESCRIPTION,
        "seed": int(seed),
        "target_reviews": int(target_reviews),
        "selected_hotel_count": len(selected),
        "selected_review_count": int(review_count),
        "does_not_truncate_hotels": True,
        "source_description": source_description,
        "hotel_ids": sorted(selected),
    }
    return write_sample_definition(output_path, payload)
