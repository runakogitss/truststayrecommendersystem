from __future__ import annotations

import pandas as pd

from .semantic_retrieval import deterministic_semantic_clusters


def build_hotel_clusters(
    frame: pd.DataFrame,
    embeddings,
    threshold: float,
    method: str = "complete_linkage",
) -> pd.DataFrame:
    parts = []
    embedding_column = "embedding_row" if "embedding_row" in frame.columns else "minilm_embedding_row"
    for hotel_id, group in frame.groupby("hotel_id", sort=True):
        rows = group.sort_values(["review_date", "review_id"], kind="mergesort")
        local_embeddings = embeddings[rows[embedding_column].astype(int).to_numpy()]
        result = deterministic_semantic_clusters(rows, local_embeddings, threshold, method)
        parts.append(result)
    return (
        pd.concat(parts, ignore_index=True)
        if parts
        else pd.DataFrame(columns=["review_id", "semantic_cluster_id", "cluster_similarity_threshold", "cluster_method"])
    )
