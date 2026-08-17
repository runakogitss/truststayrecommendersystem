#!/usr/bin/env python3
"""Optional audit: compare the development DBSCAN grouping with complete linkage.

This script is NOT part of the normal professor rerun. It exists so the final
method decision can be independently inspected using the same bundled frozen
sample. It changes no files under the normal dossier output directories.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, DBSCAN

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from truststay_evidence.config import load_sample_paths, package_root  # noqa: E402
from truststay_evidence.frozen_sample import load_embeddings  # noqa: E402


def labels_for(vectors: np.ndarray, method: str, threshold: float) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float32)
    vectors = vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
    if len(vectors) <= 1:
        return np.zeros(len(vectors), dtype=int)
    if method == "dbscan":
        return DBSCAN(eps=1-threshold, min_samples=1, metric="cosine", algorithm="brute", n_jobs=1).fit_predict(vectors)
    return AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=1-threshold,
        metric="cosine",
        linkage="complete",
        compute_full_tree=True,
    ).fit_predict(vectors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    paths = load_sample_paths(args.sample_dir)
    frame = pd.read_parquet(paths.features_path, columns=["hotel_id", "review_id", "minilm_embedding_row"])
    embeddings, embedding_ids, _ = load_embeddings(paths.embeddings_path)
    if frame["review_id"].astype(str).tolist() != [str(v) for v in embedding_ids]:
        raise ValueError("feature/embedding review-ID order mismatch")

    specs = [("dbscan", 0.85), ("complete_linkage", 0.80), ("complete_linkage", 0.85), ("complete_linkage", 0.90)]
    results = []
    for method, threshold in specs:
        cluster_sizes = []
        for _, group in frame.groupby("hotel_id", sort=True):
            rows = group["minilm_embedding_row"].astype(int).to_numpy()
            labels = labels_for(embeddings[rows], method, threshold)
            _, counts = np.unique(labels, return_counts=True)
            cluster_sizes.extend(counts.tolist())
        sizes = np.asarray(cluster_sizes, dtype=int)
        singleton_reviews = int((sizes == 1).sum())
        results.append({
            "method": method,
            "similarity_threshold": threshold,
            "cluster_count": int(len(sizes)),
            "singleton_reviews": singleton_reviews,
            "singleton_share_of_reviews": round(singleton_reviews / len(frame), 6),
            "largest_cluster": int(sizes.max()) if len(sizes) else 0,
            "clusters_gt_50": int((sizes > 50).sum()),
            "clusters_gt_100": int((sizes > 100).sum()),
        })
        print(json.dumps(results[-1], sort_keys=True), flush=True)

    payload = {"reviews": int(len(frame)), "hotels": int(frame["hotel_id"].nunique()), "results": results}
    target = args.output or (package_root() / "outputs" / "frozen_research_run" / "diagnostics" / "grouping_method_comparison.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"written: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
