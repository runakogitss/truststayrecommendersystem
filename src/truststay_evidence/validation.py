"""Validation of the self-contained frozen research sample.

Every check raises on failure.  Nothing here infers a hotel judgement, a
severity level, a recurrence pattern or a quality estimate; it establishes only
that the supplied evidence is the evidence it claims to be and that the three
row sets are exactly aligned.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .frozen_sample import (
    FEATURE_COLUMNS,
    MAPPING_COLUMNS,
    REVIEW_COLUMNS,
    load_embeddings,
    load_features,
    load_mapping,
    load_reviews,
    load_sample_definition,
    verify_hash_manifest,
)


class ValidationFailure(RuntimeError):
    """Raised when the supplied research sample fails a required check."""


def _fail(message: str) -> None:
    raise ValidationFailure(message)


def _forbidden_name_hits(values: list[str], forbidden: tuple[str, ...]) -> list[str]:
    """Match whole path segments / tokens, never bare substrings.

    Substring matching produced false positives on ordinary paths (``ott``
    matches ``scott``, ``bottom``, ``Ottawa``).  Matching is now performed on
    tokenised segments.
    """
    hits = []
    for value in values:
        tokens = {t for t in str(value).lower().replace("\\", "/").replace("-", "_").replace(".", "_").replace("/", "_").split("_") if t}
        for name in forbidden:
            if name.lower() in tokens:
                hits.append(f"{value} :: {name}")
    return sorted(set(hits))


def validate_frozen_sample(paths, config, verify_hashes: bool = True) -> dict:
    """Full validation of the bundled research sample.

    Returns a JSON-serialisable report.  Raises ``ValidationFailure`` on any
    problem; callers must not treat a raised exception as a warning.
    """
    missing = paths.missing()
    if missing:
        _fail(
            "Frozen research sample is incomplete. Missing: "
            + ", ".join(missing)
            + f"\nExpected under: {paths.sample_dir}"
            + "\nIf you are the researcher, run scripts/export_frozen_sample.py first."
        )

    package_base = Path(__file__).resolve().parents[2]
    try:
        display_sample_dir = str(Path(paths.sample_dir).resolve().relative_to(package_base))
    except ValueError:
        display_sample_dir = Path(paths.sample_dir).name
    report: dict = {"sample_dir": display_sample_dir, "checks": {}}

    # ---- 1. hashes -------------------------------------------------------
    if verify_hashes:
        report["hash_verification"] = verify_hash_manifest(paths.sample_dir, paths.hash_manifest_path)
        report["checks"]["hash_manifest_matches"] = True
    else:
        report["checks"]["hash_manifest_matches"] = "skipped"

    # ---- 2. sample definition -------------------------------------------
    definition = load_sample_definition(paths.sample_definition_path)
    expected_hotels = sorted({str(v) for v in definition["hotel_ids"]})
    declared_review_count = int(definition["selected_review_count"])
    report["sample_definition"] = {
        "seed": definition.get("seed"),
        "target_reviews": definition.get("target_reviews"),
        "declared_hotel_count": len(expected_hotels),
        "declared_review_count": declared_review_count,
        "sample_definition_sha256": definition.get("sample_definition_sha256"),
    }
    report["checks"]["sample_definition_hash_valid"] = True

    # ---- 3. load the three row sets --------------------------------------
    reviews = load_reviews(paths.reviews_path)
    features = load_features(paths.features_path)
    embeddings, embedding_ids, embedding_method = load_embeddings(paths.embeddings_path)
    mapping = load_mapping(paths.mapping_path)

    n_reviews, n_features, n_embeddings, n_mapping = len(reviews), len(features), int(embeddings.shape[0]), len(mapping)
    report["row_counts"] = {
        "reviews": n_reviews,
        "features": n_features,
        "embeddings": n_embeddings,
        "mapping": n_mapping,
        "declared_in_sample_definition": declared_review_count,
    }
    if not (n_reviews == n_features == n_embeddings == n_mapping == declared_review_count):
        _fail(
            "Row-count mismatch across the frozen sample: "
            f"reviews={n_reviews} features={n_features} embeddings={n_embeddings} mapping={n_mapping} "
            f"declared={declared_review_count}. This indicates silent truncation "
            "or an incomplete export."
        )
    report["checks"]["row_counts_agree"] = True

    # ---- 4. required columns ---------------------------------------------
    missing_review_cols = [c for c in REVIEW_COLUMNS if c not in reviews.columns]
    if missing_review_cols:
        _fail(f"reviews.parquet missing required columns: {missing_review_cols}")
    missing_feature_cols = [c for c in FEATURE_COLUMNS if c not in features.columns]
    if missing_feature_cols:
        _fail(f"features.parquet missing required columns: {missing_feature_cols}")
    missing_mapping_cols = [c for c in MAPPING_COLUMNS if c not in mapping.columns]
    if missing_mapping_cols:
        _fail(f"review_hotel_mapping.parquet missing required columns: {missing_mapping_cols}")
    report["checks"]["required_columns_present"] = True

    # ---- 5. identity, uniqueness, ordering --------------------------------
    review_ids = reviews["review_id"].astype(str)
    feature_ids = features["review_id"].astype(str)

    if review_ids.isin({"", "nan", "None", "NaN"}).any():
        _fail("reviews.parquet contains missing review IDs")
    if not review_ids.is_unique:
        duplicated = sorted(review_ids[review_ids.duplicated()].unique())[:10]
        _fail(f"reviews.parquet contains duplicate review IDs, e.g. {duplicated}")
    if not feature_ids.is_unique:
        duplicated = sorted(feature_ids[feature_ids.duplicated()].unique())[:10]
        _fail(f"features.parquet contains duplicate review IDs, e.g. {duplicated}")
    report["checks"]["review_ids_unique"] = True

    if review_ids.tolist() != feature_ids.tolist():
        set_r, set_f = set(review_ids), set(feature_ids)
        only_r, only_f = sorted(set_r - set_f)[:10], sorted(set_f - set_r)[:10]
        if only_r or only_f:
            _fail(
                "Review identity mismatch between reviews.parquet and features.parquet. "
                f"only_in_reviews={only_r} only_in_features={only_f}"
            )
        _fail("reviews.parquet and features.parquet contain the same IDs in a different order")
    report["checks"]["reviews_features_identical_order"] = True

    if [str(v) for v in embedding_ids] != review_ids.tolist():
        set_e = set(str(v) for v in embedding_ids)
        only_e, only_r = sorted(set_e - set(review_ids))[:10], sorted(set(review_ids) - set_e)[:10]
        if only_e or only_r:
            _fail(f"Embedding identity mismatch. only_in_embeddings={only_e} only_in_reviews={only_r}")
        _fail("embeddings.npz review_id order does not match reviews.parquet order")
    report["checks"]["embeddings_identical_order"] = True

    # The explicit mapping is a portable audit index, not a second data source.
    mapping_ids = mapping["review_id"].astype(str)
    mapping_hotels = mapping["hotel_id"].astype(str)
    if mapping_ids.isin({"", "nan", "None", "NaN"}).any() or mapping_hotels.isin({"", "nan", "None", "NaN"}).any():
        _fail("review_hotel_mapping.parquet contains missing review or hotel IDs")
    if not mapping_ids.is_unique:
        _fail("review_hotel_mapping.parquet contains duplicate review IDs")
    if mapping_ids.tolist() != review_ids.tolist():
        _fail("review_hotel_mapping.parquet review_id order does not match reviews.parquet order")
    if mapping_hotels.tolist() != reviews["hotel_id"].astype(str).tolist():
        _fail("review_hotel_mapping.parquet hotel_id order does not match reviews.parquet order")
    if not np.array_equal(mapping["sample_row_position"].to_numpy(dtype=np.int64), np.arange(n_mapping, dtype=np.int64)):
        _fail("review_hotel_mapping.parquet sample_row_position is not contiguous 0..N-1")
    if "source_input_row_position" in features.columns and not np.array_equal(
        mapping["source_input_row_position"].to_numpy(dtype=np.int64),
        features["source_input_row_position"].to_numpy(dtype=np.int64),
    ):
        _fail("review_hotel_mapping.parquet source_input_row_position disagrees with features.parquet")
    if "source_minilm_embedding_row" in features.columns and not np.array_equal(
        mapping["source_minilm_embedding_row"].to_numpy(dtype=np.int64),
        features["source_minilm_embedding_row"].to_numpy(dtype=np.int64),
    ):
        _fail("review_hotel_mapping.parquet source_minilm_embedding_row disagrees with features.parquet")
    report["checks"]["review_hotel_mapping_identical_order"] = True

    # ---- 6. re-based row indices ------------------------------------------
    expected_positions = np.arange(n_features, dtype=np.int64)
    if not np.array_equal(features["input_row_position"].to_numpy(dtype=np.int64), expected_positions):
        _fail("features.input_row_position is not a contiguous 0..N-1 sequence after export re-basing")
    if not np.array_equal(features["minilm_embedding_row"].to_numpy(dtype=np.int64), expected_positions):
        _fail("features.minilm_embedding_row is not a contiguous 0..N-1 sequence after export re-basing")
    report["checks"]["row_indices_rebased_contiguously"] = True

    # ---- 7. hotel coverage -------------------------------------------------
    hotel_ids = sorted(features["hotel_id"].astype(str).unique())
    if features["hotel_id"].astype(str).isin({"", "nan", "None"}).any():
        _fail("features.parquet contains missing hotel IDs")
    if hotel_ids != expected_hotels:
        only_def = sorted(set(expected_hotels) - set(hotel_ids))[:10]
        only_data = sorted(set(hotel_ids) - set(expected_hotels))[:10]
        _fail(
            "Hotel set does not match the sample definition. "
            f"in_definition_only={only_def} in_data_only={only_data}"
        )
    if not reviews["hotel_id"].astype(str).equals(features["hotel_id"].astype(str)):
        _fail("hotel_id disagrees between reviews.parquet and features.parquet on at least one row")
    report["row_counts"]["hotels"] = len(hotel_ids)
    report["checks"]["hotel_set_matches_definition"] = True

    # ---- 8. field-level integrity -----------------------------------------
    text = reviews["text"].fillna("").astype(str)
    if text.str.strip().eq("").any():
        _fail("reviews.parquet contains empty review text")
    feature_text = features["review_text"].fillna("").astype(str)
    if feature_text.str.strip().eq("").any():
        _fail("features.parquet contains empty review_text")

    dates = pd.to_datetime(reviews["review_date"], errors="coerce", format="mixed")
    if dates.isna().any():
        _fail("reviews.parquet contains unparseable review dates")
    feature_dates = pd.to_datetime(features["review_date"], errors="coerce", format="mixed")
    if feature_dates.isna().any():
        _fail("features.parquet contains unparseable review dates")
    if not (dates.dt.date.to_numpy() == feature_dates.dt.date.to_numpy()).all():
        _fail("review_date disagrees between reviews.parquet and features.parquet")

    ratings = pd.to_numeric(reviews["rating_normalized_5"], errors="coerce")
    if ratings.isna().any() or (~ratings.between(1, 5)).any():
        _fail("reviews.parquet contains ratings outside the normalised 1-5 scale")
    feature_ratings = pd.to_numeric(features["rating"], errors="coerce")
    if feature_ratings.isna().any() or (~feature_ratings.between(1, 5)).any():
        _fail("features.parquet contains ratings outside the normalised 1-5 scale")
    if not np.allclose(ratings.to_numpy(float), feature_ratings.to_numpy(float)):
        _fail("rating disagrees between reviews.parquet and features.parquet")
    report["checks"]["review_feature_fields_agree"] = True

    # ---- 9. text hash chain -------------------------------------------------
    from .frozen_sample import sha256_text

    recomputed = feature_text.map(sha256_text)
    stored = features["text_sha256"].astype(str)
    mismatched = int((recomputed != stored).sum())
    if mismatched:
        examples = features.loc[recomputed != stored, "review_id"].astype(str).tolist()[:5]
        _fail(f"text_sha256 does not match review_text for {mismatched} rows, e.g. {examples}")
    report["checks"]["text_hashes_match_text"] = True

    # ---- 10. namespace, ABSA labels, embedding method -----------------------
    namespaces = sorted(features["source_dataset"].astype(str).unique())
    if namespaces != [config.dataset_namespace]:
        _fail(f"Unexpected dataset namespace(s) {namespaces}; expected only {config.dataset_namespace}")

    methods = features["absa_method"].astype(str)
    unknown = sorted(set(methods.unique()) - set(config.allowed_absa_methods))
    if unknown:
        _fail(f"Unknown ABSA method label(s): {unknown}")
    method_counts = {k: int(v) for k, v in methods.value_counts().items()}

    # The locked V3.4.1 feature index uses the historical literal ``UNKNOWN``
    # for rows whose ABSA method is ``none``.  Preserve that source value in
    # the exported feature table; it is a no-result status, not a model label.
    allowed_statuses = {
        "deberta_absa": {"REAL_MODEL_REUSABLE"},
        "distilled_proxy": {"PROXY_SEPARATE_ONLY"},
        "none": {"NO_RESULT", "UNKNOWN"},
    }
    methods = features["absa_method"].astype(str)
    statuses = features["absa_reusable_status"].astype(str)
    bad_status = features[
        [status not in allowed_statuses.get(method, set()) for method, status in zip(methods, statuses)]
    ]
    if len(bad_status):
        _fail(
            "absa_reusable_status is inconsistent with absa_method for "
            f"{len(bad_status)} rows. Proxy rows must never be presented as direct DeBERTa inference."
        )
    report["checks"]["absa_method_labels_consistent"] = True

    if config.require_minilm_verified and not features["minilm_verified"].astype(bool).all():
        _fail("features.parquet contains rows whose MiniLM embedding is not marked verified")
    if embedding_method != "sentence_transformers":
        _fail(f"Unexpected embedding method: {embedding_method}")
    if embeddings.ndim != 2:
        _fail(f"Embedding matrix must be 2-D; got shape {embeddings.shape}")
    if not np.isfinite(np.asarray(embeddings[: min(4096, n_embeddings)], dtype=np.float64)).all():
        _fail("Embedding matrix contains non-finite values in the inspected block")

    hits = _forbidden_name_hits(namespaces + [str(paths.sample_dir.name)], config.forbidden_dataset_names)
    if hits:
        _fail(f"Out-of-scope dataset name detected: {hits}")
    report["checks"]["dataset_scope_clean"] = True

    # ---- 11. summary --------------------------------------------------------
    report["absa"] = {
        "method_counts": method_counts,
        "method_shares": {k: v / n_features for k, v in method_counts.items()},
        "rows_with_non_empty_aspect": int((features["absa_aspect"].fillna("").astype(str).str.strip() != "").sum()),
        "rows_with_non_null_confidence": int(features["absa_confidence"].notna().sum()),
    }
    report["embeddings"] = {
        "shape": [int(embeddings.shape[0]), int(embeddings.shape[1])],
        "dtype": str(np.asarray(embeddings).dtype),
        "method": embedding_method,
    }
    report["coverage"] = {
        "date_min": dates.min().date().isoformat(),
        "date_max": dates.max().date().isoformat(),
        "mean_rating": float(ratings.mean()),
        "exact_duplicate_text_rows": int(feature_text.duplicated(keep=False).sum()),
        "rows_with_duplicate_group_id": int((features["duplicate_group_id"].fillna("").astype(str).str.strip() != "").sum()),
    }
    report["status"] = "PASS"
    return report
