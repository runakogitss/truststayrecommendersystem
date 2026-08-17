from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering


def deterministic_semantic_clusters(
    frame: pd.DataFrame,
    embeddings: np.ndarray,
    threshold: float,
    method: str = "complete_linkage",
) -> pd.DataFrame:
    """Deterministically group reviews by hotel-level semantic similarity.

    The frozen final method is complete-linkage agglomerative clustering with
    cosine distance. With ``distance_threshold = 1 - threshold``, a merge is
    permitted only when the maximum cross-cluster cosine distance is below the
    threshold. This prevents the transitive chaining observed in the earlier
    DBSCAN(min_samples=1) development specification.
    """
    if len(frame) != len(embeddings):
        raise ValueError("Frame and embedding row counts differ")
    if frame.empty:
        return pd.DataFrame(columns=["review_id", "semantic_cluster_id", "cluster_similarity_threshold", "cluster_method"])
    if method != "complete_linkage":
        raise ValueError(f"Unsupported semantic grouping method: {method}")

    order = np.lexsort(
        (
            frame["review_id"].astype(str).to_numpy(),
            pd.to_datetime(frame["review_date"]).astype("int64").to_numpy(),
        )
    )
    ordered = frame.iloc[order].reset_index(drop=True)
    vectors = embeddings[order].astype(np.float32, copy=False)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if np.any(norms <= 1e-12):
        raise ValueError("Zero-norm embedding encountered; cosine clustering is undefined")
    vectors = vectors / norms

    if len(vectors) == 1:
        labels = np.array([0], dtype=int)
    else:
        model = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1.0 - float(threshold),
            metric="cosine",
            linkage="complete",
            compute_full_tree=True,
        )
        labels = model.fit_predict(vectors)

    temp = pd.DataFrame({"review_id": ordered["review_id"].astype(str), "label": labels})
    label_order = temp.groupby("label", sort=False)["review_id"].min().sort_values().index.tolist()
    relabel = {
        old: f"{str(ordered['hotel_id'].iloc[0])}:cluster_{i + 1:05d}"
        for i, old in enumerate(label_order)
    }
    temp["semantic_cluster_id"] = temp["label"].map(relabel)
    return temp[["review_id", "semantic_cluster_id"]].assign(
        cluster_similarity_threshold=float(threshold),
        cluster_method=method,
    )
