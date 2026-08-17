from __future__ import annotations

import numpy as np
import pandas as pd


def select_representatives(cluster_frame: pd.DataFrame, embeddings: np.ndarray, max_count: int = 3) -> list[str]:
    if cluster_frame.empty:
        return []
    rows = cluster_frame.sort_values(["review_date", "review_id"], kind="mergesort").copy()
    embedding_column = "embedding_row" if "embedding_row" in rows.columns else "minilm_embedding_row"
    vector = embeddings[rows[embedding_column].astype(int).to_numpy()].astype(np.float32)
    vector /= np.maximum(np.linalg.norm(vector, axis=1, keepdims=True), 1e-12)
    centroid = vector.mean(axis=0)
    distance = 1.0 - vector @ (centroid / max(np.linalg.norm(centroid), 1e-12))
    rows["_distance"] = distance
    rows["_completeness"] = rows["review_text"].fillna("").astype(str).str.len()
    rows["_real_first"] = (rows["absa_method"].astype(str) != "deberta_absa").astype(int)
    selected = []
    for _, candidate in rows.sort_values(["_distance", "_real_first", "_completeness", "review_id"], kind="mergesort").iterrows():
        if candidate.review_id not in selected:
            selected.append(str(candidate.review_id))
        if len(selected) >= max_count:
            break
    return selected
