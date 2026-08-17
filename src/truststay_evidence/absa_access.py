from __future__ import annotations

import pandas as pd


REAL_METHOD = "deberta_absa"
PROXY_METHOD = "distilled_proxy"
NO_RESULT_METHOD = "none"


def absa_status(method: str) -> str:
    return {REAL_METHOD: "REAL_MODEL_REUSABLE", PROXY_METHOD: "PROXY_SEPARATE_ONLY", NO_RESULT_METHOD: "NO_RESULT"}.get(str(method), "UNKNOWN")


def summarize_absa(frame: pd.DataFrame) -> dict:
    counts = frame["absa_method"].astype(str).value_counts().to_dict()
    total = len(frame)
    return {
        "method_counts": counts,
        "method_shares": {key: value / total if total else 0.0 for key, value in counts.items()},
        "real_model_review_count": int(counts.get(REAL_METHOD, 0)),
        "proxy_review_count": int(counts.get(PROXY_METHOD, 0)),
        "no_result_review_count": int(counts.get(NO_RESULT_METHOD, 0)),
    }
