from __future__ import annotations

REVIEW_EVIDENCE_FIELDS = [
    "source_dataset", "hotel_id", "review_id", "review_date", "rating", "review_text",
    "text_sha256", "input_row_position", "embedding_row", "embedding_verified",
    "absa_aspect", "absa_sentiment", "absa_confidence", "absa_method",
    "absa_reusable_status", "duplicate_group_id", "semantic_cluster_id",
]

DOSSIER_TOP_LEVEL_FIELDS = [
    "schema_version", "dataset_namespace", "hotel_id", "hotel_metadata", "temporal_summaries",
    "semantic_clusters", "absa_evidence", "review_evidence_records", "provenance",
    "methodology_notes", "warnings",
]

FORBIDDEN_DOSSIER_TERMS = {
    "score", "band", "recommendation", "safe", "unsafe", "severity", "credibility",
    "deterioration", "recovery", "confidence_judgment",
}


def assert_review_record_shape(record: dict) -> None:
    missing = set(REVIEW_EVIDENCE_FIELDS) - record.keys()
    if missing:
        raise ValueError(f"Review evidence record missing fields: {sorted(missing)}")


def assert_dossier_shape(dossier: dict) -> None:
    missing = set(DOSSIER_TOP_LEVEL_FIELDS) - dossier.keys()
    if missing:
        raise ValueError(f"Dossier missing fields: {sorted(missing)}")
