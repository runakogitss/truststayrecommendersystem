from __future__ import annotations

import pandas as pd


def review_records(frame: pd.DataFrame, cluster_map: pd.DataFrame) -> list[dict]:
    merged = frame.merge(cluster_map[["review_id", "semantic_cluster_id"]], on="review_id", how="left", validate="one_to_one")
    records = []
    for row in merged.to_dict(orient="records"):
        record = {key: row.get(key) for key in [
            "source_dataset", "hotel_id", "review_id", "review_date", "rating", "review_text", "text_sha256",
            "input_row_position", "minilm_embedding_row", "minilm_verified", "absa_aspect", "absa_sentiment",
            "absa_confidence", "absa_method", "absa_reusable_status", "duplicate_group_id", "semantic_cluster_id",
        ]}
        record["embedding_row"] = record.pop("minilm_embedding_row")
        record["embedding_verified"] = record.pop("minilm_verified")
        records.append(record)
    return records
