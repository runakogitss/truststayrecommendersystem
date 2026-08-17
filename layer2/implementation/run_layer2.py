#!/usr/bin/env python3
"""
TrustStay 100K Layer 2 runner
OpenCode Go + GPT-5.6 Luna

Pipeline
--------
full_dossiers.zip
  -> per-hotel chronological chunks
  -> Layer 2A evidence ledgers (no band / no numeric score)
  -> Layer 2B final rubric adjudication (A-H + band position)
  -> local validation against original review IDs
  -> deterministic display mapping added AFTER LLM inference

The runner is resume-safe. It never sends the numeric display mapping to the LLM.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import dataclasses
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx
import jsonschema

try:
    import tiktoken
except Exception:
    tiktoken = None


VERSION = "1.0.0"
BAND_LABELS = {
    "A": "Exceptional evidence pattern",
    "B": "Strong evidence pattern",
    "C": "Generally positive with meaningful limitations",
    "D": "Mixed or conditional evidence",
    "E": "Weak, high-variance or reliability-concern evidence",
    "F": "Recurring serious concern",
    "G": "Persistent severe concern",
    "H": "Critical failure pattern",
}


@dataclasses.dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    requests: int = 0

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cached_input_tokens += other.cached_input_tokens
        self.requests += other.requests

    def to_dict(self) -> dict[str, int]:
        return dataclasses.asdict(self)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_slug(hotel_id: str) -> str:
    prefix = re.sub(r"[^A-Za-z0-9._-]+", "_", hotel_id)[:90].rstrip("_")
    digest = hashlib.sha256(hotel_id.encode()).hexdigest()[:12]
    return f"{prefix}__{digest}"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def append_jsonl(path: Path, obj: Any, lock: threading.Lock) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    with lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def get_encoder():
    if tiktoken is None:
        return None
    try:
        return tiktoken.get_encoding("o200k_base")
    except Exception:
        return None


ENCODER = get_encoder()


def estimate_tokens(text: str) -> int:
    if ENCODER is not None:
        return len(ENCODER.encode(text))
    # conservative-ish fallback for English-heavy JSON
    return max(1, int(len(text) / 3.6))


def compact_review(r: dict[str, Any]) -> dict[str, Any]:
    # Keep source text + identifiers first. Derived fields are only supporting metadata.
    return {
        "review_id": r.get("review_id"),
        "review_date": r.get("review_date"),
        "rating": r.get("rating"),
        "review_text": r.get("review_text"),
        "duplicate_group_id": r.get("duplicate_group_id"),
        "semantic_cluster_id": r.get("semantic_cluster_id"),
        "absa_aspect": r.get("absa_aspect"),
        "absa_sentiment": r.get("absa_sentiment"),
        "absa_confidence": r.get("absa_confidence"),
        "absa_method": r.get("absa_method"),
        "absa_reusable_status": r.get("absa_reusable_status"),
    }


def build_chunks(
    reviews: list[dict[str, Any]],
    hotel_id: str,
    token_budget: int,
) -> list[dict[str, Any]]:
    # Chronological chunking makes the final cross-period synthesis auditable.
    ordered = sorted(
        reviews,
        key=lambda r: (str(r.get("review_date") or ""), str(r.get("review_id") or "")),
    )
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_tokens = 0

    # Reserve space for wrapper/prompt overhead.
    effective_budget = max(20000, token_budget - 8000)

    for raw in ordered:
        r = compact_review(raw)
        serialized = json.dumps(r, ensure_ascii=False, separators=(",", ":"))
        n = estimate_tokens(serialized) + 4

        if current and current_tokens + n > effective_budget:
            chunks.append(current)
            current = []
            current_tokens = 0

        current.append(r)
        current_tokens += n

    if current:
        chunks.append(current)

    result = []
    for i, rows in enumerate(chunks, start=1):
        dates = [str(r.get("review_date") or "") for r in rows]
        result.append({
            "hotel_id": hotel_id,
            "chunk_id": f"{i:03d}_of_{len(chunks):03d}",
            "chunk_date_range": {"start": min(dates), "end": max(dates)},
            "review_count": len(rows),
            "reviews": rows,
        })
    return result


def extract_response_text(payload: dict[str, Any]) -> str:
    # Raw Responses API does not expose the SDK's convenience `output_text` helper.
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]

    texts: list[str] = []
    for item in payload.get("output", []) or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []) or []:
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                texts.append(content["text"])
            elif content.get("type") == "refusal":
                raise RuntimeError(f"Model refusal: {content.get('refusal') or content}")
    if not texts:
        raise RuntimeError("Responses API returned no output_text.")
    return "\n".join(texts)


def parse_usage(payload: dict[str, Any]) -> Usage:
    u = payload.get("usage") or {}
    details = u.get("input_tokens_details") or {}
    return Usage(
        input_tokens=int(u.get("input_tokens") or 0),
        output_tokens=int(u.get("output_tokens") or 0),
        cached_input_tokens=int(details.get("cached_tokens") or 0),
        requests=1,
    )


class OpenCodeGoClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        reasoning_effort: str,
        timeout_seconds: int,
        max_retries: int,
        store: bool,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.max_retries = max_retries
        self.store = store
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self.client.close()

    def structured_response(
        self,
        *,
        instructions: str,
        user_payload: dict[str, Any],
        schema: dict[str, Any],
        schema_name: str,
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, Any], Usage]:
        request_body = {
            "model": self.model,
            "instructions": instructions,
            "input": json.dumps(user_payload, ensure_ascii=False, separators=(",", ":")),
            "reasoning": {"effort": self.reasoning_effort},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
            "max_output_tokens": max_output_tokens,
            "store": self.store,
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.client.post(f"{self.base_url}/responses", json=request_body)

                if resp.status_code in (408, 409, 429) or resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"Retryable HTTP {resp.status_code}: {resp.text[:1000]}",
                        request=resp.request,
                        response=resp,
                    )

                resp.raise_for_status()
                raw = resp.json()
                text = extract_response_text(raw)
                parsed = json.loads(text)
                jsonschema.validate(parsed, schema)
                return parsed, raw, parse_usage(raw)

            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError,
                    json.JSONDecodeError, jsonschema.ValidationError, RuntimeError) as e:
                last_error = e
                if attempt >= self.max_retries:
                    break
                delay = min(60.0, (2 ** attempt) + random.random())
                time.sleep(delay)

        raise RuntimeError(f"API call failed after retries: {last_error}")


def review_index(dossier: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        r["review_id"]: r
        for r in dossier.get("review_evidence_records", [])
        if r.get("review_id")
    }


def collect_ledger_ids(ledger: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for item in ledger.get("positive_evidence", []):
        ids.extend(item.get("review_ids", []))
    for item in ledger.get("concern_evidence", []):
        ids.extend(item.get("review_ids", []))
    return ids


def collect_assessment_ids(a: dict[str, Any]) -> list[str]:
    ids = list(a.get("material_evidence_ids", []))
    for item in a.get("positive_evidence", []):
        ids.extend(item.get("review_ids", []))
    for item in a.get("concern_evidence", []):
        ids.extend(item.get("review_ids", []))
    return ids


def validate_ids(ids: Iterable[str], valid_ids: set[str], where: str) -> None:
    missing = sorted({x for x in ids if x not in valid_ids})
    if missing:
        raise ValueError(f"{where}: cited review IDs absent from dossier: {missing[:30]}")


def validate_final_semantics(
    a: dict[str, Any],
    dossier: dict[str, Any],
) -> list[str]:
    """Deterministic checks. Returns warnings; raises on hard failures."""
    idx = review_index(dossier)
    valid_ids = set(idx)

    if a["hotel_id"] != dossier["hotel_id"]:
        raise ValueError("Final hotel_id does not match source dossier.")

    expected_count = dossier["hotel_metadata"]["review_count"]
    if a["evidence_review_count"] != expected_count:
        raise ValueError(
            f"evidence_review_count mismatch: output={a['evidence_review_count']} source={expected_count}"
        )

    validate_ids(collect_assessment_ids(a), valid_ids, "final assessment")

    expected_label = BAND_LABELS[a["band"]]
    if a["band_label"] != expected_label:
        raise ValueError(
            f"Band label mismatch: band {a['band']} requires {expected_label!r}."
        )

    warnings: list[str] = []

    # Rubric hard boundary: recurrence above C0 needs multiple distinct IDs.
    if a["recurrence_level"] in {"C1", "C2", "C3"}:
        concern_ids = []
        for item in a.get("concern_evidence", []):
            concern_ids.extend(item.get("review_ids", []))
        if len(set(concern_ids)) < 2:
            raise ValueError(
                f"{a['recurrence_level']} claimed without multiple distinct concern review IDs."
            )

    if a["band"] in {"F", "G", "H"} and a["recurrence_level"] not in {"C2", "C3"}:
        raise ValueError(
            f"Band {a['band']} requires cross-period/persistent recurrence, but recurrence_level={a['recurrence_level']}."
        )

    # C2/C3 must span distinct periods. The rubric does not define a fixed time
    # interval, so we do not invent one. We hard-check distinct dates and warn
    # if all evidence is concentrated in the same calendar month.
    if a["recurrence_level"] in {"C2", "C3"}:
        concern_ids = []
        for item in a.get("concern_evidence", []):
            if item.get("recurrence") in {"C2", "C3"}:
                concern_ids.extend(item.get("review_ids", []))
        dates = [str(idx[rid].get("review_date") or "") for rid in set(concern_ids)]
        dates = [d for d in dates if d]
        if len(set(dates)) < 2:
            raise ValueError(
                f"{a['recurrence_level']} claimed without evidence on distinct review dates."
            )
        months = {d[:7] for d in dates if len(d) >= 7}
        if len(months) < 2:
            warnings.append(
                "C2/C3 evidence IDs span distinct dates but remain within one calendar month; manually verify the rubric's 'distinct periods' requirement."
            )

    # P3 cannot materially support hotel-level conclusion.
    if a["property_relevance_status"] == "P3":
        warnings.append(
            "Hotel-level property relevance is P3. Output should be manually reviewed before use."
        )

    return warnings


def compact_hotel_context(dossier: dict[str, Any], ledgers: list[dict[str, Any]]) -> dict[str, Any]:
    hm = dossier["hotel_metadata"]
    return {
        "hotel_id": dossier["hotel_id"],
        "schema_version": dossier.get("schema_version"),
        "dataset_namespace": dossier.get("dataset_namespace"),
        "hotel_metadata": {
            "review_count": hm.get("review_count"),
            "minimum_review_date": hm.get("minimum_review_date"),
            "maximum_review_date": hm.get("maximum_review_date"),
            "raw_mean_rating": hm.get("raw_mean_rating"),
            "rating_distribution": hm.get("rating_distribution"),
            "duplicate_summary": hm.get("duplicate_summary"),
            "absa": hm.get("absa"),
        },
        "temporal_summaries": dossier.get("temporal_summaries"),
        "warnings": dossier.get("warnings"),
        "methodology_notes": dossier.get("methodology_notes"),
        "evidence_ledgers": ledgers,
    }


def estimate_go_cost(usage: Usage) -> float:
    """
    Conservative short-context Go estimate using current documented rates:
    uncached input $0.20/M, cached read $0.02/M, output $1.20/M.
    Chunking is designed to keep individual requests under the 272K long-context threshold.
    """
    uncached = max(0, usage.input_tokens - usage.cached_input_tokens)
    return (
        uncached / 1_000_000 * 0.20
        + usage.cached_input_tokens / 1_000_000 * 0.02
        + usage.output_tokens / 1_000_000 * 1.20
    )


def load_dossier_names(zip_path: Path) -> list[str]:
    with zipfile.ZipFile(zip_path, "r") as z:
        return sorted(n for n in z.namelist() if n.endswith(".json"))


def read_dossier(zip_path: Path, name: str) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path, "r") as z:
        return json.loads(z.read(name))


def preflight_dossier(dossier: dict[str, Any]) -> None:
    required_top = {
        "hotel_id", "hotel_metadata", "review_evidence_records",
        "schema_version", "temporal_summaries", "warnings"
    }
    missing = required_top - set(dossier)
    if missing:
        raise ValueError(f"Missing dossier keys: {sorted(missing)}")

    recs = dossier["review_evidence_records"]
    if dossier["hotel_metadata"]["review_count"] != len(recs):
        raise ValueError("Declared review count does not match embedded review records.")

    seen = set()
    for r in recs:
        rid = r.get("review_id")
        if not rid:
            raise ValueError("Review missing review_id.")
        if rid in seen:
            raise ValueError(f"Duplicate review_id inside dossier: {rid}")
        seen.add(rid)
        if r.get("hotel_id") != dossier["hotel_id"]:
            raise ValueError(f"Review {rid} hotel_id mismatch.")
        txt = r.get("review_text") or ""
        actual = hashlib.sha256(txt.encode("utf-8")).hexdigest()
        if actual != r.get("text_sha256"):
            raise ValueError(f"Review {rid} text SHA-256 mismatch.")


def process_hotel(
    *,
    zip_path: Path,
    dossier_name: str,
    output_dir: Path,
    cfg: dict[str, Any],
    rubric: str,
    chunk_prompt: str,
    final_prompt: str,
    chunk_schema: dict[str, Any],
    final_schema: dict[str, Any],
    mapping: dict[str, Any],
    api_key: str,
    force: bool,
) -> dict[str, Any]:
    dossier = read_dossier(zip_path, dossier_name)
    preflight_dossier(dossier)

    hotel_id = dossier["hotel_id"]
    slug = safe_slug(hotel_id)
    hotel_dir = output_dir / "hotels" / slug
    ledger_dir = hotel_dir / "ledgers"
    final_path = hotel_dir / "assessment.json"
    meta_path = hotel_dir / "run_metadata.json"

    if final_path.exists() and not force:
        existing = load_json(final_path)
        return {
            "status": "skipped_existing",
            "hotel_id": hotel_id,
            "assessment": existing,
            "usage": Usage().to_dict(),
        }

    client = OpenCodeGoClient(
        api_key=api_key,
        base_url=cfg["base_url"],
        model=cfg["model"],
        reasoning_effort=cfg["reasoning_effort"],
        timeout_seconds=cfg["request_timeout_seconds"],
        max_retries=cfg["max_retries"],
        store=cfg["store"],
    )

    total_usage = Usage()
    try:
        chunks = build_chunks(
            dossier["review_evidence_records"],
            hotel_id,
            cfg["chunk_input_token_budget"],
        )
        ledgers: list[dict[str, Any]] = []
        ledger_api_meta: list[dict[str, Any]] = []

        for chunk in chunks:
            chunk_id = chunk["chunk_id"]
            ledger_path = ledger_dir / f"{chunk_id}.json"
            ledger_meta_path = ledger_dir / f"{chunk_id}.api.json"

            if ledger_path.exists() and not force:
                ledger = load_json(ledger_path)
                jsonschema.validate(ledger, chunk_schema)
                validate_ids(
                    collect_ledger_ids(ledger),
                    set(review_index(dossier)),
                    f"ledger {chunk_id}",
                )
                ledgers.append(ledger)
                continue

            instructions = rubric + "\n\n" + chunk_prompt
            ledger, raw, usage = client.structured_response(
                instructions=instructions,
                user_payload=chunk,
                schema=chunk_schema,
                schema_name="truststay_chunk_evidence_ledger",
                max_output_tokens=cfg["chunk_max_output_tokens"],
            )
            total_usage.add(usage)

            if ledger["hotel_id"] != hotel_id:
                raise ValueError(f"Ledger {chunk_id} hotel_id mismatch.")
            if ledger["chunk_id"] != chunk_id:
                raise ValueError(f"Ledger chunk_id mismatch: expected {chunk_id}, got {ledger['chunk_id']}.")
            if ledger["review_count"] != chunk["review_count"]:
                raise ValueError(f"Ledger {chunk_id} review_count mismatch.")

            validate_ids(
                collect_ledger_ids(ledger),
                {r["review_id"] for r in chunk["reviews"]},
                f"ledger {chunk_id}",
            )

            dump_json(ledger_path, ledger)
            api_meta = {
                "response_id": raw.get("id"),
                "model": raw.get("model"),
                "created_at": raw.get("created_at"),
                "usage": usage.to_dict(),
                "request_hash": sha256_text(json.dumps(chunk, ensure_ascii=False, sort_keys=True)),
            }
            dump_json(ledger_meta_path, api_meta)
            ledger_api_meta.append(api_meta)
            ledgers.append(ledger)

        hotel_context = compact_hotel_context(dossier, ledgers)
        final_instructions = rubric + "\n\n" + final_prompt
        assessment, raw, usage = client.structured_response(
            instructions=final_instructions,
            user_payload=hotel_context,
            schema=final_schema,
            schema_name="truststay_hotel_assessment",
            max_output_tokens=cfg["final_max_output_tokens"],
        )
        total_usage.add(usage)

        validation_warnings = validate_final_semantics(assessment, dossier)

        # Numeric mapping is applied HERE, after inference and validation.
        # It was never included in the model prompt.
        map_payload = mapping["mapping"]
        display_anchor = map_payload[assessment["band"]][assessment["band_position"]]
        assessment["display_anchor"] = display_anchor
        assessment["display_mapping_version"] = mapping["version"]
        assessment["display_mapping_warning"] = mapping["warning"]
        assessment["validation_warnings"] = validation_warnings

        dump_json(final_path, assessment)
        dump_json(meta_path, {
            "runner_version": VERSION,
            "hotel_id": hotel_id,
            "source_dossier_name": dossier_name,
            "model": cfg["model"],
            "provider": cfg["provider"],
            "base_url": cfg["base_url"],
            "reasoning_effort": cfg["reasoning_effort"],
            "chunk_count": len(chunks),
            "usage": total_usage.to_dict(),
            "estimated_go_cost_usd": round(estimate_go_cost(total_usage), 6),
            "final_response_id": raw.get("id"),
            "final_response_model": raw.get("model"),
            "rubric_sha256": sha256_text(rubric),
            "final_prompt_sha256": sha256_text(final_prompt),
            "chunk_prompt_sha256": sha256_text(chunk_prompt),
            "completed_at": now_iso(),
        })

        return {
            "status": "completed",
            "hotel_id": hotel_id,
            "assessment": assessment,
            "usage": total_usage.to_dict(),
            "estimated_go_cost_usd": estimate_go_cost(total_usage),
            "chunk_count": len(chunks),
        }

    finally:
        client.close()


def dry_run_plan(zip_path: Path, names: list[str], cfg: dict[str, Any]) -> dict[str, Any]:
    total_reviews = 0
    total_chunks = 0
    max_chunks = 0
    max_reviews = 0
    hotel_rows = []

    with zipfile.ZipFile(zip_path, "r") as z:
        for name in names:
            d = json.loads(z.read(name))
            preflight_dossier(d)
            chunks = build_chunks(
                d["review_evidence_records"],
                d["hotel_id"],
                cfg["chunk_input_token_budget"],
            )
            rc = len(d["review_evidence_records"])
            total_reviews += rc
            total_chunks += len(chunks)
            max_chunks = max(max_chunks, len(chunks))
            max_reviews = max(max_reviews, rc)
            hotel_rows.append({
                "hotel_id": d["hotel_id"],
                "reviews": rc,
                "chunks": len(chunks),
            })

    return {
        "hotels": len(names),
        "reviews": total_reviews,
        "layer2a_chunk_calls": total_chunks,
        "layer2b_final_calls": len(names),
        "total_expected_api_calls": total_chunks + len(names),
        "max_chunks_for_one_hotel": max_chunks,
        "max_reviews_for_one_hotel": max_reviews,
        "chunk_input_token_budget": cfg["chunk_input_token_budget"],
        "note": (
            "Call count is exact for the current chunking plan. Cost is not estimated here because "
            "actual output size and cache hits materially affect OpenCode Go usage."
        ),
        "hotels_plan": hotel_rows,
    }


def rebuild_master_assessments(output_dir: Path) -> int:
    """Rebuild the canonical JSONL from per-hotel assessment files.

    Per-hotel files are the source of truth. Rebuilding avoids duplicate or missing
    rows when a run is resumed after interruption.
    """
    rows = []
    for p in (output_dir / "hotels").glob("*/assessment.json"):
        try:
            rows.append(load_json(p))
        except Exception:
            continue
    rows.sort(key=lambda x: x.get("hotel_id", ""))
    target = output_dir / "assessments.jsonl"
    temp = target.with_suffix(".jsonl.tmp")
    with temp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    temp.replace(target)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path, help="Path to full_dossiers.zip")
    parser.add_argument("--output", default=Path("layer2_outputs"), type=Path)
    parser.add_argument("--config", default=Path("config.example.json"), type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Validate and plan calls without API requests")
    parser.add_argument("--max-hotels", type=int, default=None, help="Run only first N hotels")
    parser.add_argument("--hotel-id", default=None, help="Run one exact hotel_id")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Overwrite completed hotel outputs")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    cfg_path = args.config if args.config.is_absolute() else base / args.config
    cfg = load_json(cfg_path)
    if args.workers is not None:
        cfg["workers"] = args.workers

    rubric_path = base / "TrustStay_Layer2_Runtime_Rubric_v1_4_20260816.md"
    mapping_path = base / "TrustStay_Display_Mapping_v1_0_20260816.json"
    chunk_prompt_path = base / "prompts" / "chunk_extraction.md"
    final_prompt_path = base / "prompts" / "hotel_adjudication.md"
    chunk_schema_path = base / "schemas" / "chunk_ledger.schema.json"
    final_schema_path = base / "schemas" / "hotel_assessment.schema.json"

    rubric = rubric_path.read_text(encoding="utf-8")
    mapping = load_json(mapping_path)
    chunk_prompt = chunk_prompt_path.read_text(encoding="utf-8")
    final_prompt = final_prompt_path.read_text(encoding="utf-8")
    chunk_schema = load_json(chunk_schema_path)
    final_schema = load_json(final_schema_path)

    zip_path = args.input.resolve()
    if not zip_path.exists():
        raise SystemExit(f"Input not found: {zip_path}")

    names = load_dossier_names(zip_path)
    if args.hotel_id:
        matches = []
        with zipfile.ZipFile(zip_path, "r") as z:
            for name in names:
                d = json.loads(z.read(name))
                if d.get("hotel_id") == args.hotel_id:
                    matches.append(name)
        if not matches:
            raise SystemExit(f"hotel_id not found: {args.hotel_id}")
        names = matches

    if args.max_hotels is not None:
        names = names[:args.max_hotels]

    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        plan = dry_run_plan(zip_path, names, cfg)
        plan["input_zip"] = str(zip_path)
        plan["input_zip_sha256"] = sha256_file(zip_path)
        plan["rubric_sha256"] = sha256_file(rubric_path)
        plan["runner_version"] = VERSION
        plan_path = output_dir / "dry_run_plan.json"
        dump_json(plan_path, plan)
        print(json.dumps({k: v for k, v in plan.items() if k != "hotels_plan"}, indent=2))
        print(f"\nSaved: {plan_path}")
        return 0

    api_key = os.environ.get("OPENCODE_GO_API_KEY")
    if not api_key:
        raise SystemExit(
            "OPENCODE_GO_API_KEY is not set. Export your OpenCode Go API key before running."
        )

    run_started = now_iso()
    run_manifest = {
        "runner_version": VERSION,
        "started_at": run_started,
        "input_zip": str(zip_path),
        "input_zip_sha256": sha256_file(zip_path),
        "hotel_count_requested": len(names),
        "provider": cfg["provider"],
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "reasoning_effort": cfg["reasoning_effort"],
        "rubric_file": rubric_path.name,
        "rubric_sha256": sha256_file(rubric_path),
        "display_mapping_file": mapping_path.name,
        "display_mapping_sha256": sha256_file(mapping_path),
        "numeric_mapping_sent_to_model": False,
        "config": cfg,
    }
    dump_json(output_dir / "run_manifest.json", run_manifest)

    results_path = output_dir / "assessments.jsonl"
    failures_path = output_dir / "failures.jsonl"
    log_lock = threading.Lock()

    total_usage = Usage()
    total_cost = 0.0
    completed = 0
    failed = 0
    skipped = 0

    worker_count = max(1, int(cfg.get("workers", 1)))
    print(f"Running {len(names)} hotels with {worker_count} worker(s) using {cfg['model']}.")

    def task(name: str) -> dict[str, Any]:
        try:
            return process_hotel(
                zip_path=zip_path,
                dossier_name=name,
                output_dir=output_dir,
                cfg=cfg,
                rubric=rubric,
                chunk_prompt=chunk_prompt,
                final_prompt=final_prompt,
                chunk_schema=chunk_schema,
                final_schema=final_schema,
                mapping=mapping,
                api_key=api_key,
                force=args.force,
            )
        except Exception as e:
            return {
                "status": "failed",
                "dossier_name": name,
                "error_type": type(e).__name__,
                "error": str(e),
                "failed_at": now_iso(),
            }

    with futures.ThreadPoolExecutor(max_workers=worker_count) as pool:
        future_map = {pool.submit(task, n): n for n in names}
        for fut in futures.as_completed(future_map):
            result = fut.result()
            status = result["status"]
            if status == "completed":
                completed += 1
                u = Usage(**result["usage"])
                total_usage.add(u)
                total_cost += float(result.get("estimated_go_cost_usd") or 0)
                print(
                    f"[{completed + failed + skipped}/{len(names)}] "
                    f"OK {result['hotel_id']} -> "
                    f"{result['assessment']['band']}-{result['assessment']['band_position']} "
                    f"({result['assessment']['display_anchor']})"
                )
            elif status == "skipped_existing":
                skipped += 1
                print(
                    f"[{completed + failed + skipped}/{len(names)}] "
                    f"SKIP {result['hotel_id']}"
                )
            else:
                failed += 1
                append_jsonl(failures_path, result, log_lock)
                print(
                    f"[{completed + failed + skipped}/{len(names)}] "
                    f"FAIL {result.get('dossier_name')}: {result.get('error')}",
                    file=sys.stderr,
                )

            run_manifest.update({
                "updated_at": now_iso(),
                "completed": completed,
                "failed": failed,
                "skipped_existing": skipped,
                "usage_current_process": total_usage.to_dict(),
                "estimated_go_cost_usd_current_process": round(total_cost, 6),
            })
            dump_json(output_dir / "run_manifest.json", run_manifest)

    total_assessment_files = rebuild_master_assessments(output_dir)
    run_manifest["total_assessment_files"] = total_assessment_files
    run_manifest["completed_at"] = now_iso()
    dump_json(output_dir / "run_manifest.json", run_manifest)

    print("\nDone.")
    print(f"Completed: {completed}")
    print(f"Skipped existing: {skipped}")
    print(f"Failed: {failed}")
    print(f"Usage this process: {total_usage.to_dict()}")
    print(f"Estimated Go cost this process: ${total_cost:.4f}")
    print(f"Outputs: {output_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
