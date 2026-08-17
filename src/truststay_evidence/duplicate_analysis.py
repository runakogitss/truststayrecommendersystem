from __future__ import annotations

import pandas as pd


def duplicate_summary(frame: pd.DataFrame) -> dict:
    groups = frame["duplicate_group_id"].fillna("").astype(str)
    grouped = groups[groups != ""]
    return {
        "possible_duplicate_review_count": int((groups != "").sum()),
        "possible_duplicate_group_count": int(grouped.nunique()),
        "exact_reuse_review_count": int(frame.get("exact_reuse", pd.Series(False, index=frame.index)).fillna(False).astype(bool).sum()),
        "independence_claim": "not_established",
    }


def cluster_duplicate_summary(frame: pd.DataFrame) -> dict:
    return {
        "unique_review_count": int(frame["review_id"].nunique()),
        "possible_duplicate_count": int((frame["duplicate_group_id"].fillna("").astype(str) != "").sum()),
        "independence_claim": "not_established",
    }
