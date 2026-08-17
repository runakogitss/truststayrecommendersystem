#!/usr/bin/env python3
"""Targeted full-sample DeBERTa ABSA refresh with frozen clustering.

This entrypoint deliberately does not import or call the clustering builder.
It reads the professor-validated cluster membership from the original full
dossiers, performs only the requested ABSA refresh, then rebuilds dossiers
against that fixed review-to-cluster mapping.

Examples (Windows):
    python scripts/run_full_absa_refresh.py --smoke-test
    python scripts/run_full_absa_refresh.py
    python scripts/run_full_absa_refresh.py --resume
    python scripts/run_full_absa_refresh.py --validate-only
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from truststay_evidence.config import load_config, load_sample_paths, package_root  # noqa: E402
from truststay_evidence.dossier_builder import build_full_dossier, write_dossier_pair  # noqa: E402
from truststay_evidence.embedding_access import open_embeddings  # noqa: E402
from truststay_evidence.frozen_sample import (  # noqa: E402
    load_features,
    load_reviews,
    read_hash_manifest,
    sha256_file,
)
from truststay_evidence.full_absa_adapter import (  # noqa: E402
    ASPECT_MODEL_ID,
    SENTIMENT_MODEL_ID,
    EndToEndRuntime,
    PREDICTION_COLUMNS,
    infer_batch as adapter_infer_batch,
    load_aspect_specs,
    load_runtime,
    model_environment,
    runtime_provenance,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, path)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def frozen_sample_digest(sample_dir: Path, manifest_path: Path) -> tuple[str, dict[str, str]]:
    expected = read_hash_manifest(manifest_path)
    actual = {name: sha256_file(Path(sample_dir) / name) for name in sorted(expected)}
    if actual != expected:
        raise ValueError("Frozen sample hash manifest does not match the supplied input files")
    canonical = json.dumps(actual, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(canonical), actual


def load_frozen_cluster_map(original_output: Path, expected_ids: list[str]) -> pd.DataFrame:
    """Read, but never recompute, the validated review-to-cluster mapping."""
    records: list[dict[str, str]] = []
    source_dir = Path(original_output) / "full_dossiers"
    files = sorted(source_dir.glob("hotel_*_full.json"))
    if not files:
        raise FileNotFoundError(f"No frozen full dossiers found at {source_dir}")
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        for record in data.get("review_evidence_records", []):
            records.append(
                {
                    "review_id": str(record["review_id"]),
                    "hotel_id": str(record["hotel_id"]),
                    "semantic_cluster_id": str(record["semantic_cluster_id"]),
                }
            )
    mapping = pd.DataFrame(records)
    if mapping.empty:
        raise ValueError("Frozen dossiers contained no review-to-cluster records")
    if mapping["review_id"].duplicated().any():
        raise ValueError("Frozen dossiers contain duplicate review IDs")
    expected = set(map(str, expected_ids))
    actual = set(mapping["review_id"])
    if actual != expected:
        raise ValueError(
            f"Frozen cluster map IDs differ from the frozen sample: missing={len(expected - actual)}, extra={len(actual - expected)}"
        )
    return mapping.sort_values("review_id", kind="mergesort").reset_index(drop=True)


def _unused_legacy_load_model(model_id: str, revision: str, device_name: str, local_files_only: bool) -> Any:
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as error:
        raise RuntimeError(
            "Full ABSA dependencies are missing. Install requirements_full_absa.txt before loading the model."
        ) from error

    if device_name == "auto":
        device_name = "cuda" if torch.cuda.is_available() else "cpu"
    if device_name == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--device cuda was requested but torch.cuda.is_available() is false")
    device = torch.device(device_name)
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, use_fast=True, local_files_only=local_files_only)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_id, revision=revision, local_files_only=local_files_only
    )
    model.to(device)
    model.eval()
    id2label = {int(key): str(value) for key, value in dict(model.config.id2label).items()}
    labels = {value.lower() for value in id2label.values()}
    if not {"positive", "negative", "neutral"}.issubset(labels):
        raise RuntimeError(
            f"Model id2label does not expose Positive/Negative/Neutral labels: {id2label}. "
            "Refusing to guess the output adapter."
        )
    return (tokenizer, model, torch, device, id2label)


def model_environment(runtime: ModelRuntime) -> dict[str, Any]:
    torch = runtime.torch
    cuda_available = bool(torch.cuda.is_available())
    gpu_name = torch.cuda.get_device_name(0) if cuda_available else None
    vram = None
    if cuda_available:
        vram = int(torch.cuda.get_device_properties(0).total_memory)
    return {
        "device": str(runtime.device),
        "cuda_version": getattr(torch.version, "cuda", None),
        "gpu_name": gpu_name,
        "gpu_vram_bytes": vram,
        "torch_version": getattr(torch, "__version__", None),
    }


def _unused_legacy_resolved_revision(runtime: Any, tokenizer: Any, requested: str) -> str | None:
    for value in (
        getattr(runtime.model.config, "_commit_hash", None),
        getattr(tokenizer, "init_kwargs", {}).get("_commit_hash"),
    ):
        if value:
            return str(value)
    return None


def decode_prediction(runtime: ModelRuntime, logits: Any, aspect: str) -> dict[str, Any]:
    probabilities = runtime.torch.softmax(logits, dim=-1)[0].detach().cpu().numpy()
    index = int(np.argmax(probabilities))
    raw_label = runtime.id2label.get(index, str(index))
    label = raw_label.strip().lower()
    if "positive" in label:
        sentiment, sign = "positive", 1.0
    elif "negative" in label:
        sentiment, sign = "negative", -1.0
    elif "neutral" in label:
        sentiment, sign = "neutral", 0.0
    else:
        raise RuntimeError(f"Unsupported model output label {raw_label!r}; refusing to guess")
    probability = float(probabilities[index])
    return {
        "aspect": aspect,
        "sentiment": sentiment,
        "raw_label": raw_label,
        "label_index": index,
        "probability": probability,
        "signed_score": sign * probability,
    }


def predict_pair_batch(runtime: ModelRuntime, pairs: list[tuple[str, str]], max_length: int) -> list[dict[str, Any]]:
    texts = [pair[0] for pair in pairs]
    aspects = [pair[1] for pair in pairs]
    encoded = runtime.tokenizer(
        texts,
        aspects,
        padding=True,
        truncation="only_first",
        max_length=max_length,
        return_tensors="pt",
    )
    encoded = {key: value.to(runtime.device) for key, value in encoded.items()}
    with runtime.torch.inference_mode():
        outputs = runtime.model(**encoded)
    logits = getattr(outputs, "logits", None)
    if logits is None or len(logits) != len(pairs):
        raise RuntimeError("DeBERTa output did not contain one logits row per text/aspect pair")
    return [decode_prediction(runtime, logits[index : index + 1], aspect) for index, (_, aspect) in enumerate(pairs)]


def _unused_legacy_failure_row(review_id: str, reason: str, candidate_count: int = 0) -> dict[str, Any]:
    return {
        "review_id": str(review_id),
        "absa_method": NO_RESULT_METHOD,
        "absa_aspect": "",
        "absa_sentiment": "",
        "absa_confidence": np.nan,
        "inference_status": "failed",
        "error_message": reason,
        "absa_pairs_json": "[]",
        "aspect_candidate_count": int(candidate_count),
        "successful_aspect_count": 0,
    }


def _unused_legacy_success_row(review_id: str, pairs: list[dict[str, Any]], candidate_count: int) -> dict[str, Any]:
    aspects = [str(pair["aspect"]) for pair in pairs]
    sentiment = ";".join(f"{pair['aspect']}:{float(pair['signed_score']):.12g}" for pair in pairs)
    confidence = float(np.mean([float(pair["probability"]) for pair in pairs]))
    return {
        "review_id": str(review_id),
        "absa_method": DIRECT_METHOD,
        "absa_aspect": ";".join(aspects),
        "absa_sentiment": sentiment,
        "absa_confidence": confidence,
        "inference_status": "success",
        "error_message": "",
        "absa_pairs_json": json.dumps(pairs, sort_keys=True, separators=(",", ":")),
        "aspect_candidate_count": int(candidate_count),
        "successful_aspect_count": len(pairs),
    }


def _unused_legacy_infer_batch(
    frame: pd.DataFrame,
    specs: list[Any],
    runtime: Any,
    batch_size: int,
    max_length: int,
) -> pd.DataFrame:
    raise RuntimeError("The legacy text-pair-only adapter is disabled; use truststay_evidence.full_absa_adapter.infer_batch")


def checkpoint_parts(checkpoint_dir: Path) -> list[Path]:
    return sorted(Path(checkpoint_dir).glob("checkpoint_batch_*.parquet"))


def load_checkpoint_results(checkpoint_dir: Path) -> pd.DataFrame:
    parts = checkpoint_parts(checkpoint_dir)
    if not parts:
        return pd.DataFrame(columns=PREDICTION_COLUMNS)
    frames = []
    for part in parts:
        frame = pd.read_parquet(part)
        missing = set(PREDICTION_COLUMNS) - set(frame.columns)
        if missing:
            raise ValueError(f"Checkpoint {part} lacks columns {sorted(missing)}")
        frames.append(frame[PREDICTION_COLUMNS].copy())
    combined = pd.concat(frames, ignore_index=True)
    combined["review_id"] = combined["review_id"].astype(str)
    if combined["review_id"].duplicated().any():
        combined = combined.drop_duplicates("review_id", keep="last")
    return combined


def write_checkpoint(frame: pd.DataFrame, checkpoint_dir: Path, batch_number: int) -> Path:
    target = Path(checkpoint_dir) / f"checkpoint_batch_{batch_number:06d}.parquet"
    atomic_parquet(frame[PREDICTION_COLUMNS], target)
    return target


def run_inference_with_checkpoints(
    frame: pd.DataFrame,
    specs: list[Any],
    runtime: EndToEndRuntime,
    checkpoint_dir: Path,
    batch_size: int,
    max_length: int,
    resume: bool,
    recompute_successful: bool,
) -> pd.DataFrame:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    existing = load_checkpoint_results(checkpoint_dir) if resume or checkpoint_parts(checkpoint_dir) else pd.DataFrame(columns=PREDICTION_COLUMNS)
    successful_ids = set(
        existing.loc[existing["inference_status"].astype(str).str.startswith("success"), "review_id"].astype(str)
    )
    if not recompute_successful:
        work = frame[~frame["review_id"].astype(str).isin(successful_ids)].copy()
    else:
        work = frame.copy()
    next_number = max([int(p.stem.split("_")[-1]) for p in checkpoint_parts(checkpoint_dir)] or [0]) + 1
    for start in range(0, len(work), batch_size):
        result = adapter_infer_batch(work.iloc[start : start + batch_size], runtime, specs, batch_size, max_length)
        write_checkpoint(result, checkpoint_dir, next_number)
        next_number += 1
        if existing.empty:
            existing = result.copy()
        else:
            existing = pd.concat([existing, result], ignore_index=True).drop_duplicates("review_id", keep="last")
    selected_ids = set(frame["review_id"].astype(str))
    result = existing[existing["review_id"].astype(str).isin(selected_ids)].copy()
    if set(result["review_id"].astype(str)) != selected_ids:
        missing = selected_ids - set(result["review_id"].astype(str))
        raise RuntimeError(f"Inference ended with missing checkpoint results for {len(missing)} reviews")
    return frame[["review_id"]].merge(result, on="review_id", how="left", validate="one_to_one")[PREDICTION_COLUMNS]


def create_refreshed_features(features: pd.DataFrame, predictions: pd.DataFrame, cluster_map: pd.DataFrame) -> pd.DataFrame:
    frame = features.copy()
    frame["review_id"] = frame["review_id"].astype(str)
    if frame["review_id"].duplicated().any():
        raise ValueError("Frozen features contain duplicate review IDs")
    for column in (
        "absa_method",
        "absa_reusable_status",
        "absa_aspect",
        "absa_sentiment",
        "absa_confidence",
    ):
        frame[f"source_{column}"] = frame[column]
    frame = frame.drop(
        columns=["absa_method", "absa_reusable_status", "absa_aspect", "absa_sentiment", "absa_confidence"],
        errors="ignore",
    )
    frame = frame.drop(columns=["semantic_cluster_id"], errors="ignore")
    frame = frame.merge(predictions, on="review_id", how="left", validate="one_to_one")
    frame = frame.merge(cluster_map[["review_id", "semantic_cluster_id"]], on="review_id", how="left", validate="one_to_one")
    if frame["inference_status"].isna().any() or frame["semantic_cluster_id"].isna().any():
        raise ValueError("Refreshed feature table has missing inference results or frozen cluster assignments")
    successful = frame["inference_status"].astype(str).str.startswith("success")
    frame["absa_reusable_status"] = np.where(successful, "REAL_MODEL_REUSABLE", "NO_RESULT")
    frame["absa_method"] = np.where(successful, "deberta_absa", "none")
    return frame


def validate_dossiers(output_root: Path, expected_ids: set[str]) -> dict[str, Any]:
    """Validate dossier structure without importing or calling clustering code."""
    full_dir = Path(output_root) / "full_dossiers"
    compact_dir = Path(output_root) / "compact_dossiers"
    full_files = sorted(full_dir.glob("hotel_*_full.json"))
    compact_files = sorted(compact_dir.glob("hotel_*_compact.json"))
    failures: list[str] = []
    seen: set[str] = set()
    for path in full_files:
        try:
            dossier = json.loads(path.read_text(encoding="utf-8"))
            records = dossier["review_evidence_records"]
            record_ids = [str(record["review_id"]) for record in records]
            if len(record_ids) != len(set(record_ids)):
                failures.append(f"duplicate review IDs in {path.name}")
            seen.update(record_ids)
            assigned = set()
            record_to_cluster = {str(record["review_id"]): str(record["semantic_cluster_id"]) for record in records}
            for cluster in dossier["semantic_clusters"]:
                cluster_id = str(cluster["semantic_cluster_id"])
                member_count = int(cluster["unique_review_count"])
                reps = [str(value) for value in cluster["representative_review_ids"]]
                if member_count != sum(1 for value in record_to_cluster.values() if value == cluster_id):
                    failures.append(f"cluster member count mismatch in {path.name}:{cluster_id}")
                assigned.update(value for value, value_cluster in record_to_cluster.items() if value_cluster == cluster_id)
                if any(record_to_cluster.get(rep) != cluster_id for rep in reps):
                    failures.append(f"representative cluster mismatch in {path.name}:{cluster_id}")
            if assigned != set(record_ids):
                failures.append(f"cluster coverage mismatch in {path.name}")
            compact = compact_dir / path.name.replace("_full.json", "_compact.json")
            if not compact.is_file():
                failures.append(f"missing compact dossier for {path.name}")
        except Exception as error:
            failures.append(f"{path.name}: {type(error).__name__}: {error}")
    if seen != expected_ids:
        failures.append(f"dossier review coverage differs: missing={len(expected_ids - seen)}, extra={len(seen - expected_ids)}")
    return {
        "full_dossier_count": len(full_files),
        "compact_dossier_count": len(compact_files),
        "review_ids_in_dossiers": len(seen),
        "failures": failures,
    }


def compare_cluster_memberships(original: pd.DataFrame, refreshed: pd.DataFrame) -> dict[str, Any]:
    left = original[["review_id", "hotel_id", "semantic_cluster_id"]].copy()
    right = refreshed[["review_id", "hotel_id", "semantic_cluster_id"]].copy()
    left["review_id"] = left["review_id"].astype(str)
    right["review_id"] = right["review_id"].astype(str)
    left_ids, right_ids = set(left.review_id), set(right.review_id)
    joined = left.merge(right, on="review_id", how="inner", suffixes=("_original", "_refreshed"))
    mismatch = joined[joined.semantic_cluster_id_original != joined.semantic_cluster_id_refreshed]
    report = {
        "total_review_ids_compared": int(len(joined)),
        "matching_memberships": int(len(joined) - len(mismatch)),
        "mismatching_memberships": int(len(mismatch)),
        "missing_ids": sorted(left_ids - right_ids),
        "extra_ids": sorted(right_ids - left_ids),
        "original_hotel_count": int(left.hotel_id.nunique()),
        "refreshed_hotel_count": int(right.hotel_id.nunique()),
        "original_group_count": int(left.semantic_cluster_id.nunique()),
        "refreshed_group_count": int(right.semantic_cluster_id.nunique()),
        "mismatching_review_id_examples": mismatch.review_id.astype(str).tolist()[:20],
        "status": "PASS" if len(mismatch) == 0 and left_ids == right_ids else "FAIL",
    }
    return report


def refresh_dossiers(
    frame: pd.DataFrame,
    cluster_map: pd.DataFrame,
    embeddings: np.ndarray,
    config: Any,
    provenance: dict,
    output_root: Path,
) -> dict[str, Any]:
    full_dir = Path(output_root) / "full_dossiers"
    compact_dir = Path(output_root) / "compact_dossiers"
    full_dir.mkdir(parents=True, exist_ok=True)
    compact_dir.mkdir(parents=True, exist_ok=True)
    failures = []
    for hotel_id, hotel_frame in frame.groupby(frame["hotel_id"].astype(str), sort=True):
        try:
            hotel_clusters = cluster_map[cluster_map["hotel_id"].astype(str) == str(hotel_id)].copy()
            dossier = build_full_dossier(hotel_frame.copy(), hotel_clusters, embeddings, config, provenance)
            dossier["methodology_notes"]["absa_reused_without_inference"] = False
            dossier["methodology_notes"]["absa_refreshed_with_direct_model"] = True
            dossier["methodology_notes"]["cluster_membership_reused_without_reclustering"] = True
            dossier["warnings"] = [
                "ABSA rows are official end-to-end DeBERTa results where inference_status starts with success; failed rows remain no-result and are never proxy-filled.",
                "Raw aspect terms come from the official end-to-end token-classification model; the hotel lexicon is only an optional canonical-category mapper.",
                "Aspect extraction scores and sentiment-model scores are preserved separately in absa_aspect_predictions_json; no combined confidence is created.",
                "MiniLM embeddings and frozen complete-linkage cluster memberships were reused without recomputation.",
                *[warning for warning in dossier.get("warnings", []) if "Proxy ABSA" not in warning and "confidence is unavailable" not in warning and "absa_reused_without_inference" not in warning],
            ]
            write_dossier_pair(dossier, full_dir, compact_dir, str(hotel_id), config.representatives_per_cluster)
        except Exception as error:
            failures.append({"hotel_id": str(hotel_id), "error": f"{type(error).__name__}: {error}"})
    return {
        "full_dossier_count": len(list(full_dir.glob("hotel_*_full.json"))),
        "compact_dossier_count": len(list(compact_dir.glob("hotel_*_compact.json"))),
        "failures": failures,
    }


def explode_aspect_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    """Create a normalized child table without losing the row-level result."""
    rows = []
    for record in predictions.to_dict(orient="records"):
        try:
            aspects = json.loads(record.get("absa_aspect_predictions_json") or "[]")
        except json.JSONDecodeError:
            aspects = []
        for aspect in aspects:
            rows.append(
                {
                    "review_id": str(record["review_id"]),
                    "raw_aspect": aspect.get("raw_aspect", ""),
                    "canonical_aspect": aspect.get("canonical_aspect"),
                    "start": aspect.get("start"),
                    "end": aspect.get("end"),
                    "extractor_label": aspect.get("extractor_label", ""),
                    "aspect_extraction_score": aspect.get("aspect_extraction_score"),
                    "sentiment": aspect.get("sentiment"),
                    "sentiment_source": aspect.get("sentiment_source"),
                    "sentiment_score": aspect.get("sentiment_score"),
                    "sentiment_scores_json": json.dumps(aspect.get("sentiment_scores"), sort_keys=True)
                    if aspect.get("sentiment_scores") is not None
                    else None,
                    "sentiment_error": aspect.get("sentiment_error", ""),
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "review_id",
            "raw_aspect",
            "canonical_aspect",
            "start",
            "end",
            "extractor_label",
            "aspect_extraction_score",
            "sentiment",
            "sentiment_source",
            "sentiment_score",
            "sentiment_scores_json",
            "sentiment_error",
        ],
    )


def output_manifest(output_root: Path) -> Path:
    target = Path(output_root) / "SHA256_MANIFEST.csv"
    rows = []
    for path in sorted(Path(output_root).rglob("*")):
        relative_parts = path.relative_to(output_root).parts
        if not path.is_file() or path == target or ".embedding_cache" in relative_parts or "smoke_test" in relative_parts:
            continue
        rows.append({"path": str(path.relative_to(output_root)).replace("\\", "/"), "sha256": sha256_file(path), "size_bytes": path.stat().st_size})
    temporary = target.with_name(target.name + ".partial")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "size_bytes"])
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, target)
    return target


def validation_markdown(report: dict[str, Any]) -> str:
    failures = report.get("validation_failures", [])
    lines = [
        "# Full DeBERTa ABSA Refresh Validation",
        "",
        f"**Verdict:** `{report['final_verdict']}`",
        f"**Generated UTC:** `{report['generated_utc']}`",
        "",
        "## Coverage and alignment",
        "",
        f"- Expected rows: `{report['expected_rows']}`",
        f"- Rows attempted: `{report['rows_attempted']}`",
        f"- Successful inference rows: `{report['successful_inference_rows']}` ({report['inference_coverage_percent']:.4f}%)",
        f"- Reviews with one or more extracted aspects: `{report['reviews_with_aspects']}`",
        f"- Reviews with zero extracted aspects: `{report['reviews_with_zero_aspects']}`",
        f"- Technical inference failures: `{report['technical_failures']}`",
        f"- Extracted aspect terms: `{report['extracted_aspect_terms']}`",
        f"- Sentiment labels populated: `{report['sentiment_labels_populated']}`",
        f"- Aspect extraction scores populated: `{report['aspect_scores_populated']}`",
        f"- Sentiment-model scores populated: `{report['sentiment_scores_populated']}`",
        f"- Duplicate review IDs: `{report['duplicate_review_ids']}`",
        f"- Missing review IDs: `{report['missing_review_ids']}`",
        "",
        "## Frozen cluster invariant",
        "",
        f"- Review IDs compared: `{report['cluster_invariance']['total_review_ids_compared']}`",
        f"- Matching memberships: `{report['cluster_invariance']['matching_memberships']}`",
        f"- Mismatching memberships: `{report['cluster_invariance']['mismatching_memberships']}`",
        f"- Missing IDs: `{len(report['cluster_invariance']['missing_ids'])}`",
        f"- Extra IDs: `{len(report['cluster_invariance']['extra_ids'])}`",
        f"- Original hotel count: `{report['cluster_invariance']['original_hotel_count']}`",
        f"- Refreshed hotel count: `{report['cluster_invariance']['refreshed_hotel_count']}`",
        f"- Original group count: `{report['cluster_invariance']['original_group_count']}`",
        f"- Refreshed group count: `{report['cluster_invariance']['refreshed_group_count']}`",
        f"- Cluster invariant: `{report['cluster_invariance']['status']}`",
        "",
        "## Dossiers and failures",
        "",
        f"- Full dossiers generated: `{report['dossiers_generated']['full_dossier_count']}`",
        f"- Compact dossiers generated: `{report['dossiers_generated']['compact_dossier_count']}`",
        f"- Dossier failures: `{len(report['dossiers_generated']['failures'])}`",
        "",
        "### Validation failures",
        "",
    ]
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "Rows with inference_status starting with success are labelled `deberta_absa`; failed rows remain `none`/`NO_RESULT`. Successful zero-aspect inference is not a technical failure. No `distilled_proxy` value is copied into the refreshed result. MiniLM embeddings, frozen semantic group IDs, and the complete-linkage threshold are reused unchanged.",
            "",
        ]
    )
    return "\n".join(lines)


def build_validation_report(
    output_root: Path,
    expected_ids: list[str],
    predictions: pd.DataFrame,
    refreshed: pd.DataFrame,
    original_clusters: pd.DataFrame,
    dossier_report: dict[str, Any],
    smoke_test: bool,
) -> dict[str, Any]:
    expected = set(map(str, expected_ids))
    ids = predictions["review_id"].astype(str)
    duplicate_count = int(ids.duplicated().sum())
    actual = set(ids)
    statuses = predictions["inference_status"].astype(str)
    successful = statuses.str.startswith("success")
    with_aspects = statuses.eq("success_with_aspects")
    zero_aspects = statuses.eq("success_no_aspects")
    failed = statuses.str.startswith("failed")
    cluster_report = compare_cluster_memberships(original_clusters[original_clusters.review_id.isin(expected)], refreshed)
    failures = []
    if duplicate_count:
        failures.append(f"prediction table contains {duplicate_count} duplicate review IDs")
    if actual != expected:
        failures.append(f"prediction IDs differ from expected IDs: missing={len(expected - actual)}, extra={len(actual - expected)}")
    if cluster_report["status"] != "PASS":
        failures.append("cluster-membership invariant FAILED")
    failures.extend(f"dossier failure: {item}" for item in dossier_report.get("failures", []))
    if not smoke_test and len(predictions) != len(expected):
        failures.append("full run did not produce one result row per frozen review")
    if predictions["absa_method"].astype(str).eq("distilled_proxy").any():
        failures.append("refreshed predictions contain forbidden distilled_proxy labels")
    direct_count = int(successful.sum())
    extracted_terms = int(predictions.loc[successful, "extracted_aspect_count"].fillna(0).sum())
    aspect_score_count = int(predictions.loc[successful, "aspect_score_count"].fillna(0).sum())
    sentiment_score_count = int(predictions.loc[successful, "sentiment_score_count"].fillna(0).sum())
    sentiment_labels = int(predictions.loc[successful, "extracted_aspect_count"].fillna(0).sum())
    if failures:
        verdict = "FAIL"
    elif smoke_test or int(failed.sum()) or int(zero_aspects.sum()):
        verdict = "PASS WITH WARNINGS"
    else:
        verdict = "PASS"
    return {
        "generated_utc": utc_now(),
        "smoke_test": bool(smoke_test),
        "expected_rows": len(expected),
        "rows_attempted": len(predictions),
        "successful_inference_rows": direct_count,
        "inference_coverage_percent": 100.0 * direct_count / len(expected) if expected else 0.0,
        "reviews_with_aspects": int(with_aspects.sum()),
        "reviews_with_zero_aspects": int(zero_aspects.sum()),
        "technical_failures": int(failed.sum()),
        "extracted_aspect_terms": extracted_terms,
        "sentiment_labels_populated": sentiment_labels,
        "aspect_scores_populated": aspect_score_count,
        "sentiment_scores_populated": sentiment_score_count,
        "duplicate_review_ids": duplicate_count,
        "missing_review_ids": len(expected - actual),
        "cluster_invariance": cluster_report,
        "dossiers_generated": dossier_report,
        "validation_failures": failures,
        "final_verdict": verdict,
        "output_directory": str(output_root),
    }


def make_provenance(
    runner_path: Path,
    sample_dir: Path,
    sample_hash: str,
    input_hashes: dict[str, str],
    runtime: EndToEndRuntime,
    args: argparse.Namespace,
    started: str,
    ended: str,
    duration: float,
    attempted: int,
    successful: int,
    failed: int,
    cluster_mapping_hash: str,
) -> dict[str, Any]:
    try:
        import transformers
        transformers_version = transformers.__version__
    except ImportError:
        transformers_version = None
    try:
        import sentencepiece
        sentencepiece_version = sentencepiece.__version__
    except ImportError:
        sentencepiece_version = None
    env = model_environment(runtime)
    model_info = runtime_provenance(runtime)
    return {
        **model_info,
        "python_version": platform.python_version(),
        "pytorch_version": env.get("torch_version"),
        "transformers_version": transformers_version,
        "sentencepiece_version": sentencepiece_version,
        "batch_size": args.batch_size,
        "maximum_sequence_length": args.max_length,
        "truncation_strategy": "token-classification pipeline truncation=True; text-pair refinement truncates only the review text",
        "random_seed": args.seed,
        "start_timestamp_utc": started,
        "end_timestamp_utc": ended,
        "total_inference_runtime_seconds": round(duration, 3),
        "rows_attempted": attempted,
        "rows_successful": successful,
        "rows_failed": failed,
        "runner_code_sha256": sha256_file(runner_path),
        "input_frozen_sample_hash": sample_hash,
        "input_frozen_sample_files": input_hashes,
        "optional_canonical_category_config": str(args.aspect_config),
        "original_cluster_mapping_sha256": cluster_mapping_hash,
        "cluster_membership_source": str(Path(args.original_output_dir) / "full_dossiers"),
        "minilm_recomputed": False,
        "embeddings_recomputed": False,
        "clustering_recomputed": False,
        "proxy_fallback_used": False,
        "model_assumptions": model_info["model_assumptions"] if "model_assumptions" in model_info else [
            "The end-to-end token-classification model extracts raw aspect spans and joint sentiment labels.",
            "The separate sentiment model is called only for extracted aspects below the official 0.8 score threshold.",
            "The optional hotel lexicon maps raw extracted terms to canonical categories and never gates inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    root = package_root()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample-dir", type=Path, default=root / "data" / "frozen_research_sample")
    parser.add_argument("--original-output-dir", type=Path, default=root / "outputs" / "frozen_research_run")
    parser.add_argument("--output-dir", type=Path, default=root / "outputs" / "frozen_research_run_full_absa")
    parser.add_argument("--aspect-config", type=Path, default=root / "configs" / "full_absa_aspects.yaml")
    parser.add_argument("--aspect-revision", default="main")
    parser.add_argument("--sentiment-revision", default="main")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--batch-size", type=int, default=4, help="Safe default; reduce to 2 or 1 after a CUDA OOM")
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--seed", type=int, default=20260813)
    parser.add_argument("--limit", type=int, default=None, help="Deterministic first-N review limit; intended for smoke tests")
    parser.add_argument("--smoke-test", action="store_true", help="Run a small isolated test under output_dir/smoke_test")
    parser.add_argument("--resume", action="store_true", help="Load checkpoint parts and skip already successful review IDs")
    parser.add_argument("--recompute-successful", action="store_true", help="Explicitly allow recomputation of successful checkpoint rows")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true", help="Validate an already completed output without model loading")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = package_root()
    args.sample_dir = Path(args.sample_dir).expanduser().resolve()
    args.original_output_dir = Path(args.original_output_dir).expanduser().resolve()
    args.output_dir = Path(args.output_dir).expanduser().resolve()
    args.aspect_config = Path(args.aspect_config).expanduser().resolve()
    if args.smoke_test and args.output_dir == (root / "outputs" / "frozen_research_run_full_absa").resolve():
        args.output_dir = args.output_dir / "smoke_test"
    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be positive")
    if args.limit is not None and not args.smoke_test:
        raise SystemExit("--limit is reserved for --smoke-test so a partial result cannot be mistaken for the full run")
    if args.smoke_test and args.limit is None:
        args.limit = 100
    if args.batch_size <= 0 or args.max_length <= 0:
        raise SystemExit("--batch-size and --max-length must be positive")
    if not args.smoke_test and not args.validate_only and args.device != "cuda":
        raise SystemExit("The dissertation-grade full run requires --device cuda and will not silently fall back to CPU.")

    paths = load_sample_paths(args.sample_dir)
    config = load_config()
    started_timestamp = utc_now()
    start_clock = time.time()
    input_hash, input_hashes = frozen_sample_digest(paths.sample_dir, paths.hash_manifest_path)
    features = load_features(paths.features_path)
    reviews = load_reviews(paths.reviews_path)
    if features["review_id"].astype(str).tolist() != reviews["review_id"].astype(str).tolist():
        raise SystemExit("Frozen features and reviews are not aligned by review_id")
    expected_all_ids = features["review_id"].astype(str).tolist()
    original_clusters = load_frozen_cluster_map(args.original_output_dir, expected_all_ids)
    selected = features.copy()
    if args.limit is not None:
        selected = selected.iloc[: args.limit].copy()
    selected_ids = selected["review_id"].astype(str).tolist()
    cluster_subset = original_clusters[original_clusters["review_id"].isin(set(selected_ids))].copy()
    specs = load_aspect_specs(args.aspect_config)
    output_root = args.output_dir
    output_root.mkdir(parents=True, exist_ok=True)

    if args.validate_only:
        predictions_path = output_root / "full_absa_predictions.parquet"
        features_path = output_root / "features_full_absa.parquet"
        if not predictions_path.is_file() or not features_path.is_file():
            raise SystemExit("--validate-only requires full_absa_predictions.parquet and features_full_absa.parquet")
        predictions = pd.read_parquet(predictions_path)
        refreshed = pd.read_parquet(features_path)
        atomic_parquet(explode_aspect_predictions(predictions), output_root / "full_absa_aspect_predictions.parquet")
        dossier_report = {
            "full_dossier_count": len(list((output_root / "full_dossiers").glob("hotel_*_full.json"))),
            "compact_dossier_count": len(list((output_root / "compact_dossiers").glob("hotel_*_compact.json"))),
            "failures": [],
        }
        dossier_report["validation"] = validate_dossiers(output_root, set(selected_ids))
        dossier_report["failures"].extend(dossier_report["validation"].get("failures", []))
        report = build_validation_report(output_root, selected_ids, predictions, refreshed, cluster_subset, dossier_report, bool(args.smoke_test or args.limit))
        atomic_json(output_root / "cluster_invariance_check.json", report["cluster_invariance"])
        (output_root / "FULL_ABSA_VALIDATION.md").write_text(validation_markdown(report), encoding="utf-8")
        output_manifest(output_root)
        print(json.dumps(report, indent=2))
        return 0 if report["final_verdict"] != "FAIL" else 5

    checkpoint_dir = output_root / "checkpoints"
    parts_exist = checkpoint_parts(checkpoint_dir)
    if parts_exist and not args.resume and not args.recompute_successful:
        raise SystemExit("Checkpoint files already exist. Re-run with --resume or --recompute-successful explicitly.")

    runtime = load_runtime(
        args.device,
        args.aspect_revision,
        args.sentiment_revision,
        max_length=args.max_length,
        local_files_only=args.local_files_only,
    )
    runtime.torch.manual_seed(args.seed)
    predictions = run_inference_with_checkpoints(
        selected,
        specs,
        runtime,
        checkpoint_dir,
        args.batch_size,
        args.max_length,
        args.resume,
        args.recompute_successful,
    )
    successful_count = int(predictions["inference_status"].astype(str).str.startswith("success").sum())
    failed_count = int(len(predictions) - successful_count)
    refreshed = create_refreshed_features(selected, predictions, cluster_subset)
    atomic_parquet(predictions, output_root / "full_absa_predictions.parquet")
    atomic_parquet(
        predictions[~predictions["inference_status"].astype(str).str.startswith("success")].copy(),
        output_root / "full_absa_failures.parquet",
    )
    atomic_parquet(explode_aspect_predictions(predictions), output_root / "full_absa_aspect_predictions.parquet")
    atomic_parquet(refreshed, output_root / "features_full_absa.parquet")

    # The embeddings are opened for dossier representative selection only; no
    # embedding model or clustering function is called here.
    embeddings = open_embeddings(paths.embeddings_path, expected_all_ids, cache_dir=output_root / ".embedding_cache")
    mapping_payload = original_clusters.sort_values(["review_id", "semantic_cluster_id"], kind="mergesort").to_dict(orient="records")
    cluster_mapping_hash = sha256_bytes(json.dumps(mapping_payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    provenance = make_provenance(
        Path(__file__).resolve(),
        paths.sample_dir,
        input_hash,
        input_hashes,
        runtime,
        args,
        started_timestamp,
        utc_now(),
        time.time() - start_clock,
        len(predictions),
        successful_count,
        failed_count,
        cluster_mapping_hash,
    )
    dossier_report = refresh_dossiers(refreshed, cluster_subset, embeddings.embeddings, config, provenance, output_root)
    dossier_validation = validate_dossiers(output_root, set(selected_ids))
    dossier_report["validation"] = dossier_validation
    dossier_report["failures"].extend(dossier_validation.get("failures", []))
    cluster_report = compare_cluster_memberships(cluster_subset, refreshed)
    atomic_json(output_root / "cluster_invariance_check.json", cluster_report)
    report = build_validation_report(output_root, selected_ids, predictions, refreshed, cluster_subset, dossier_report, bool(args.smoke_test or args.limit))
    report["cluster_invariance"] = cluster_report
    provenance.update(
        {
            "review_count": report["expected_rows"],
            "successful_inference_rows": report["successful_inference_rows"],
            "reviews_with_aspects": report["reviews_with_aspects"],
            "reviews_with_zero_aspects": report["reviews_with_zero_aspects"],
            "extracted_aspect_terms": report["extracted_aspect_terms"],
            "technical_failures": report["technical_failures"],
        }
    )
    atomic_json(output_root / "ABSA_INFERENCE_PROVENANCE.json", {**provenance, "validation_summary": report})
    (output_root / "FULL_ABSA_VALIDATION.md").write_text(validation_markdown(report), encoding="utf-8")
    output_manifest(output_root)
    print(json.dumps(report, indent=2))
    return 0 if report["final_verdict"] != "FAIL" else 5


if __name__ == "__main__":
    raise SystemExit(main())
