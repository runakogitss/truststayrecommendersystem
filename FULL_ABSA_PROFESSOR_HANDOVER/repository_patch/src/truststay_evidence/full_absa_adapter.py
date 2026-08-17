"""Official-model end-to-end adapter for the targeted ABSA refresh.

The model author's documented workflow uses:

* ``yangheng/deberta-v3-base-end2end-absa`` as a token-classification model
  whose labels jointly encode aspect spans and sentiment; and
* ``yangheng/deberta-v3-base-absa-v1.1`` as an optional text-pair sentiment
  refinement when the end-to-end extractor score is below 0.8.

The fixed hotel lexicon is never used to decide whether inference runs. It is
only an optional post-extraction canonical-category mapper.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ASPECT_MODEL_ID = "yangheng/deberta-v3-base-end2end-absa"
SENTIMENT_MODEL_ID = "yangheng/deberta-v3-base-absa-v1.1"
FALLBACK_CONFIDENCE_THRESHOLD = 0.8
PREDICTION_COLUMNS = [
    "review_id",
    "absa_method",
    "absa_aspect",
    "absa_sentiment",
    "absa_confidence",
    "inference_status",
    "error_message",
    "absa_aspect_predictions_json",
    "absa_canonical_aspect",
    "extracted_aspect_count",
    "aspect_score_count",
    "sentiment_score_count",
]


@dataclass(frozen=True)
class AspectSpec:
    canonical: str
    aliases: tuple[str, ...]


@dataclass
class EndToEndRuntime:
    aspect_extractor: Any
    sentiment_tokenizer: Any
    sentiment_model: Any
    torch: Any
    device: Any
    sentiment_id2label: dict[int, str]
    aspect_revision: str | None
    sentiment_revision: str | None
    aspect_tokenizer_revision: str | None
    sentiment_tokenizer_revision: str | None


def load_aspect_specs(path: Path) -> list[AspectSpec]:
    import yaml

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    specs = []
    for item in raw.get("aspects", []):
        if not isinstance(item, dict) or not item.get("canonical") or not item.get("aliases"):
            raise ValueError(f"Invalid aspect entry in {path}: {item!r}")
        canonical = str(item["canonical"]).strip()
        aliases = tuple(dict.fromkeys([canonical, *[str(v).strip() for v in item["aliases"] if str(v).strip()]]))
        specs.append(AspectSpec(canonical, aliases))
    if not specs:
        raise ValueError(f"No optional canonical aspect categories found in {path}")
    return specs


def canonical_category(raw_aspect: str, specs: list[AspectSpec]) -> str | None:
    """Map an already extracted raw term to an optional category.

    This function is deliberately downstream of model extraction. No review
    is rejected when it has no matching category.
    """
    value = str(raw_aspect or "").strip()
    for spec in specs:
        for alias in spec.aliases:
            if re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", value, flags=re.IGNORECASE):
                return spec.canonical
    return None


def _resolved_revision(model: Any, tokenizer: Any) -> str | None:
    for value in (
        getattr(getattr(model, "config", None), "_commit_hash", None),
        getattr(tokenizer, "init_kwargs", {}).get("_commit_hash"),
    ):
        if value:
            return str(value)
    return None


def _id2label(model: Any) -> dict[int, str]:
    return {int(key): str(value) for key, value in dict(model.config.id2label).items()}


def load_runtime(
    device_name: str,
    aspect_revision: str,
    sentiment_revision: str,
    max_length: int = 512,
    local_files_only: bool = False,
) -> EndToEndRuntime:
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoModelForTokenClassification, AutoTokenizer, pipeline
    except ImportError as error:
        raise RuntimeError(
            "Full ABSA dependencies are missing. Install requirements_full_absa.txt before loading the official models."
        ) from error

    if device_name == "auto":
        device_name = "cuda" if torch.cuda.is_available() else "cpu"
    if device_name == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--device cuda was requested but torch.cuda.is_available() is false; refusing CPU fallback")
    device = torch.device(device_name)
    pipeline_device = 0 if device.type == "cuda" else -1

    aspect_tokenizer = AutoTokenizer.from_pretrained(
        ASPECT_MODEL_ID, revision=aspect_revision, use_fast=True, local_files_only=local_files_only
    )
    # The pipeline uses tokenizer.model_max_length internally. Some tokenizer
    # configs expose a very large sentinel instead of the model's practical
    # 512-token limit, so make the documented truncation explicit.
    aspect_tokenizer.model_max_length = int(max_length)
    aspect_model = AutoModelForTokenClassification.from_pretrained(
        ASPECT_MODEL_ID, revision=aspect_revision, local_files_only=local_files_only
    )
    aspect_extractor = pipeline(
        "token-classification",
        model=aspect_model,
        tokenizer=aspect_tokenizer,
        aggregation_strategy="simple",
        device=pipeline_device,
    )

    sentiment_tokenizer = AutoTokenizer.from_pretrained(
        SENTIMENT_MODEL_ID, revision=sentiment_revision, use_fast=True, local_files_only=local_files_only
    )
    sentiment_model = AutoModelForSequenceClassification.from_pretrained(
        SENTIMENT_MODEL_ID, revision=sentiment_revision, local_files_only=local_files_only
    )
    sentiment_model.to(device)
    sentiment_model.eval()
    labels = _id2label(sentiment_model)
    if not {"positive", "negative", "neutral"}.issubset({value.lower() for value in labels.values()}):
        raise RuntimeError(f"Sentiment model labels are not Positive/Negative/Neutral: {labels}")

    return EndToEndRuntime(
        aspect_extractor=aspect_extractor,
        sentiment_tokenizer=sentiment_tokenizer,
        sentiment_model=sentiment_model,
        torch=torch,
        device=device,
        sentiment_id2label=labels,
        aspect_revision=_resolved_revision(aspect_model, aspect_tokenizer),
        sentiment_revision=_resolved_revision(sentiment_model, sentiment_tokenizer),
        aspect_tokenizer_revision=_resolved_revision(aspect_model, aspect_tokenizer),
        sentiment_tokenizer_revision=_resolved_revision(sentiment_model, sentiment_tokenizer),
    )


def model_environment(runtime: EndToEndRuntime) -> dict[str, Any]:
    torch = runtime.torch
    cuda_available = bool(torch.cuda.is_available())
    return {
        "device": str(runtime.device),
        "cuda_version": getattr(torch.version, "cuda", None),
        "gpu_name": torch.cuda.get_device_name(0) if cuda_available else None,
        "gpu_vram_bytes": int(torch.cuda.get_device_properties(0).total_memory) if cuda_available else None,
        "torch_version": getattr(torch, "__version__", None),
    }


def _clean_aspect(value: str) -> str:
    return re.sub(r'^[\s\.,;:!?\(\)\[\]\{\}"\']+|[\s\.,;:!?\(\)\[\]\{\}"\']+$', "", value or "").strip()


def _locate_span(text: str, phrase: str) -> tuple[int, int] | None:
    if not phrase:
        return None
    for flags in (0, re.IGNORECASE):
        match = re.search(re.escape(phrase), text, flags=flags)
        if match:
            return int(match.start()), int(match.end())
    return None


def _sentiment_from_label(label: str) -> str | None:
    lower = str(label or "").lower()
    for candidate in ("positive", "negative", "neutral"):
        if candidate in lower:
            return candidate
    return None


def _extract_entities(text: str, entities: list[dict[str, Any]], specs: list[AspectSpec]) -> list[dict[str, Any]]:
    aspects = []
    seen = set()
    for entity in entities or []:
        label = str(entity.get("entity_group") or entity.get("entity") or "")
        sentiment = _sentiment_from_label(label)
        if "asp" not in label.lower() or sentiment is None:
            continue
        raw_aspect = _clean_aspect(str(entity.get("word") or ""))
        if not raw_aspect:
            continue
        start, end = entity.get("start"), entity.get("end")
        if start is None or end is None:
            located = _locate_span(text, raw_aspect)
            if located is None:
                continue
            start, end = located
        key = (raw_aspect.casefold(), int(start), int(end))
        if key in seen:
            continue
        seen.add(key)
        aspects.append(
            {
                "raw_aspect": raw_aspect,
                "canonical_aspect": canonical_category(raw_aspect, specs),
                "start": int(start),
                "end": int(end),
                "extractor_label": label,
                "aspect_extraction_score": float(entity.get("score", 0.0)),
                "sentiment": sentiment,
                "sentiment_source": "end2end_extractor_label",
                "sentiment_score": None,
                "sentiment_scores": None,
            }
        )
    return aspects


def _decode_sentiment(runtime: EndToEndRuntime, logits: Any) -> tuple[str, float, dict[str, float]]:
    probabilities = runtime.torch.softmax(logits, dim=-1)[0].detach().cpu().numpy()
    scores = {runtime.sentiment_id2label[index]: float(probabilities[index]) for index in range(len(probabilities))}
    best_index = int(np.argmax(probabilities))
    label = _sentiment_from_label(runtime.sentiment_id2label[best_index])
    if label is None:
        raise RuntimeError(f"Unsupported sentiment label: {runtime.sentiment_id2label[best_index]}")
    return label, float(probabilities[best_index]), scores


def _classify_sentiment_batch(runtime: EndToEndRuntime, pairs: list[tuple[str, str]], max_length: int) -> list[dict[str, Any]]:
    texts = [pair[0] for pair in pairs]
    aspects = [pair[1] for pair in pairs]
    encoded = runtime.sentiment_tokenizer(
        texts,
        aspects,
        padding=True,
        truncation="only_first",
        max_length=max_length,
        return_tensors="pt",
    )
    encoded = {key: value.to(runtime.device) for key, value in encoded.items()}
    with runtime.torch.inference_mode():
        outputs = runtime.sentiment_model(**encoded)
    logits = getattr(outputs, "logits", None)
    if logits is None or len(logits) != len(pairs):
        raise RuntimeError("Sentiment model did not return one logits row per text/aspect pair")
    results = []
    for index in range(len(pairs)):
        label, score, scores = _decode_sentiment(runtime, logits[index : index + 1])
        results.append({"sentiment": label, "sentiment_score": score, "sentiment_scores": scores})
    return results


def _refine_low_confidence(
    runtime: EndToEndRuntime,
    text: str,
    aspects: list[dict[str, Any]],
    max_length: int,
    batch_size: int,
) -> None:
    candidates = [aspect for aspect in aspects if float(aspect["aspect_extraction_score"]) < FALLBACK_CONFIDENCE_THRESHOLD]
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start : start + batch_size]
        pairs = [(text, str(aspect["raw_aspect"])) for aspect in batch]
        try:
            results = _classify_sentiment_batch(runtime, pairs, max_length)
        except Exception as batch_error:
            results = []
            for pair in pairs:
                try:
                    results.extend(_classify_sentiment_batch(runtime, [pair], max_length))
                except Exception as error:
                    results.append({"sentiment_error": f"{type(error).__name__}: {error}; batch_error={batch_error}"})
        for aspect, result in zip(batch, results):
            if "sentiment_error" in result:
                aspect["sentiment_error"] = result["sentiment_error"]
            else:
                aspect.update(result)
                aspect["sentiment_source"] = "sentiment_model_text_pair_refinement"


def infer_batch(
    frame: pd.DataFrame,
    runtime: EndToEndRuntime,
    specs: list[AspectSpec],
    batch_size: int,
    max_length: int,
) -> pd.DataFrame:
    """Run official end-to-end extraction for every row in ``frame``."""
    rows: list[dict[str, Any]] = []
    records = frame[["review_id", "review_text"]].to_dict(orient="records")
    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        valid = []
        row_entities: dict[str, list[dict[str, Any]]] = {}
        for record in batch:
            review_id = str(record["review_id"])
            text = record.get("review_text")
            if not str(text or "").strip():
                rows.append(failure_row(review_id, "missing/invalid review_text", "failed_missing_text"))
            else:
                valid.append((review_id, str(text)))
        if valid:
            try:
                outputs = runtime.aspect_extractor(
                    [text for _, text in valid],
                    batch_size=batch_size,
                )
                for (review_id, text), entities in zip(valid, outputs):
                    row_entities[review_id] = _extract_entities(text, entities, specs)
            except Exception as batch_error:
                for review_id, text in valid:
                    try:
                        entities = runtime.aspect_extractor(text)
                        row_entities[review_id] = _extract_entities(text, entities, specs)
                    except Exception as error:
                        rows.append(failure_row(review_id, f"{type(error).__name__}: {error}; batch_error={batch_error}", "failed_model"))
        for review_id, text in valid:
            if review_id not in row_entities:
                continue
            aspects = row_entities[review_id]
            _refine_low_confidence(runtime, text, aspects, max_length, batch_size)
            rows.append(result_row(review_id, aspects))
        print(f"  inference batch {min(start + batch_size, len(records))}/{len(records)} reviews", flush=True)
    return pd.DataFrame(rows, columns=PREDICTION_COLUMNS)


def failure_row(review_id: str, reason: str, status: str) -> dict[str, Any]:
    return {
        "review_id": str(review_id),
        "absa_method": "none",
        "absa_aspect": "",
        "absa_sentiment": "",
        "absa_confidence": np.nan,
        "inference_status": status,
        "error_message": reason,
        "absa_aspect_predictions_json": "[]",
        "absa_canonical_aspect": "",
        "extracted_aspect_count": 0,
        "aspect_score_count": 0,
        "sentiment_score_count": 0,
    }


def result_row(review_id: str, aspects: list[dict[str, Any]]) -> dict[str, Any]:
    raw = [str(aspect["raw_aspect"]) for aspect in aspects]
    sentiments = [f"{aspect['raw_aspect']}:{aspect['sentiment']}" for aspect in aspects]
    canonical = [str(aspect["canonical_aspect"]) for aspect in aspects if aspect.get("canonical_aspect")]
    aspect_score_count = sum(aspect.get("aspect_extraction_score") is not None for aspect in aspects)
    sentiment_score_count = sum(aspect.get("sentiment_score") is not None for aspect in aspects)
    return {
        "review_id": str(review_id),
        "absa_method": "deberta_absa",
        "absa_aspect": ";".join(raw),
        "absa_sentiment": ";".join(sentiments),
        "absa_confidence": np.nan,
        "inference_status": "success_with_aspects" if aspects else "success_no_aspects",
        "error_message": "",
        "absa_aspect_predictions_json": json.dumps(aspects, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        "absa_canonical_aspect": ";".join(canonical),
        "extracted_aspect_count": len(aspects),
        "aspect_score_count": int(aspect_score_count),
        "sentiment_score_count": int(sentiment_score_count),
    }


def runtime_provenance(runtime: EndToEndRuntime) -> dict[str, Any]:
    env = model_environment(runtime)
    aspect_max_length = getattr(getattr(runtime.aspect_extractor, "tokenizer", None), "model_max_length", None)
    return {
        **env,
        "aspect_extraction_max_sequence_length": aspect_max_length,
        "aspect_extraction_model_id": ASPECT_MODEL_ID,
        "aspect_extraction_resolved_revision": runtime.aspect_revision,
        "sentiment_model_id": SENTIMENT_MODEL_ID,
        "sentiment_model_resolved_revision": runtime.sentiment_revision,
        "aspect_tokenizer_id": ASPECT_MODEL_ID,
        "aspect_tokenizer_resolved_revision": runtime.aspect_tokenizer_revision,
        "sentiment_tokenizer_id": SENTIMENT_MODEL_ID,
        "sentiment_tokenizer_resolved_revision": runtime.sentiment_tokenizer_revision,
        "architecture": "official end2end token classification for aspect+sentiment, with official low-extraction-score text-pair sentiment refinement",
        "aspect_extraction_score_definition": "token-classification pipeline entity score returned by the end-to-end extractor",
        "sentiment_score_definition": "softmax top-label probability from the separate sentiment classifier, only when low-score refinement ran successfully; not calibrated truth probability",
        "combined_confidence_created": False,
        "model_assumptions": [
            "The end-to-end token-classification model extracts raw aspect spans and joint sentiment labels.",
            "The separate sentiment model is called only for extracted aspects below the official 0.8 score threshold.",
            "The optional hotel lexicon maps raw extracted terms to canonical categories and never gates inference.",
        ],
    }
