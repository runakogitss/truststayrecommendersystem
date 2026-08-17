#!/usr/bin/env python3
"""Codex-native TrustStay Layer 2 adapter.

This file deliberately leaves the original OpenCode Go runner untouched.  It
reuses only deterministic loading, chunking, validation, and display-mapping
helpers from ``run_layer2.py`` and replaces the inference transport with one
fresh ``codex exec`` process per qualitative assessment.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

from run_layer2 import (
    BAND_LABELS,
    build_chunks,
    collect_assessment_ids,
    collect_ledger_ids,
    compact_hotel_context,
    dump_json,
    load_json,
    now_iso,
    preflight_dossier,
    safe_slug,
    validate_final_semantics,
    validate_ids,
)


MODEL = "gpt-5.6-luna"
CODEX_MODE = "GPT-5.6 Luna via Codex using ChatGPT-managed authentication"


def read_dossier(path: Path) -> dict[str, Any]:
    dossier = load_json(path)
    preflight_dossier(dossier)
    return dossier


def parse_model_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        # Formatting-only recovery for an otherwise valid JSON response.
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("Codex response was not a JSON object.")
    return value


def run_codex_json(prompt: str, schema_path: Path, output_path: Path) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    cmd = [
        "codex",
        "exec",
        "--model",
        MODEL,
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "-c",
        'model_reasoning_effort="medium"',
        "--output-schema",
        str(schema_path),
        "-o",
        str(output_path),
        "-",
    ]
    completed = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=900,
        check=False,
    )
    log_path = output_path.with_suffix(output_path.suffix + ".codex.log")
    log_path.write_text(completed.stdout or "", encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"codex exec failed with exit code {completed.returncode}; see {log_path.name}"
        )
    if not output_path.exists():
        raise RuntimeError(f"codex exec produced no output file; see {log_path.name}")
    result = parse_model_json(output_path)
    token_match = re.search(r"tokens used\s+([\d,]+)", completed.stdout or "", re.I)
    result["_codex_usage"] = {
        "tokens_used": int(token_match.group(1).replace(",", "")) if token_match else None,
        "input_tokens": None,
        "cached_input_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
    }
    return result


def prompt_for(instructions: str, payload: dict[str, Any]) -> str:
    return (
        instructions
        + "\n\nReturn only the structured JSON object required by the schema."
        + "\n\nINPUT JSON:\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def initial_manifest(
    dossiers: list[Path],
    rubric_path: Path,
    chunk_prompt_path: Path,
    final_prompt_path: Path,
    chunk_schema_path: Path,
    final_schema_path: Path,
    mapping_path: Path,
    chunk_counts: dict[str, int],
    review_counts: dict[str, int],
) -> dict[str, Any]:
    rows = []
    for p in dossiers:
        d = load_json(p)
        hotel_id = d["hotel_id"]
        rows.append(
            {
                "hotel_id": hotel_id,
                "source_dossier": p.name,
                "state": "pending",
                "layer2a_chunks_expected": chunk_counts[hotel_id],
                "layer2a_chunks_complete": 0,
                "layer2b_status": "pending",
                "schema_validation_status": "pending",
                "mapping_status": "pending",
                "final_status": "pending",
                "error": None,
                "reviews": review_counts[hotel_id],
            }
        )
    return {
        "started_at": now_iso(),
        "execution_mode": CODEX_MODE,
        "assessment_model": MODEL,
        "external_llm_api_calls": 0,
        "dossier_ordering": "lexicographic source filename order",
        "dataset": {"hotels": len(dossiers), "reviews": sum(review_counts.values())},
        "workload": {
            "layer2a_assessments": sum(chunk_counts.values()),
            "layer2b_assessments": len(dossiers),
            "total_logical_assessments": sum(chunk_counts.values()) + len(dossiers),
        },
        "frozen_files": {
            "rubric": rubric_path.name,
            "layer2a_prompt": chunk_prompt_path.name,
            "layer2b_prompt": final_prompt_path.name,
            "chunk_schema": chunk_schema_path.name,
            "hotel_schema": final_schema_path.name,
            "display_mapping": mapping_path.name,
        },
        "hotels": rows,
    }


def update_row(manifest: dict[str, Any], hotel_id: str, **updates: Any) -> None:
    for row in manifest["hotels"]:
        if row["hotel_id"] == hotel_id:
            row.update(updates)
            return
    raise KeyError(hotel_id)


def row_for(manifest: dict[str, Any], hotel_id: str) -> dict[str, Any]:
    return next(row for row in manifest["hotels"] if row["hotel_id"] == hotel_id)


def process_hotel(
    dossier_path: Path,
    output_dir: Path,
    rubric: str,
    chunk_prompt: str,
    final_prompt: str,
    chunk_schema: dict[str, Any],
    final_schema: dict[str, Any],
    chunk_schema_path: Path,
    final_schema_path: Path,
    mapping: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path,
    manifest_lock: threading.Lock,
    force: bool,
) -> dict[str, Any]:
    dossier = read_dossier(dossier_path)
    hotel_id = dossier["hotel_id"]
    hotel_dir = output_dir / "hotels" / safe_slug(hotel_id)
    ledger_dir = hotel_dir / "ledgers"
    assessment_path = hotel_dir / "assessment.json"
    metadata_path = hotel_dir / "run_metadata.json"
    codex_tmp = hotel_dir / ".codex_tmp"
    chunks = build_chunks(dossier["review_evidence_records"], hotel_id, 180000)
    valid_ids = set(r["review_id"] for r in dossier["review_evidence_records"])
    usage: list[dict[str, Any]] = []

    def save_manifest(**updates: Any) -> None:
        with manifest_lock:
            update_row(manifest, hotel_id, **updates)
            dump_json(manifest_path, manifest)

    if assessment_path.exists() and not force:
        assessment = load_json(assessment_path)
        base = {k: v for k, v in assessment.items() if not k.startswith("display_") and k != "validation_warnings"}
        jsonschema.validate(base, final_schema)
        validate_final_semantics(base, dossier)
        save_manifest(
            state="complete",
            layer2a_chunks_complete=len(chunks),
            layer2b_status="complete",
            schema_validation_status="valid",
            mapping_status="complete",
            final_status="complete",
            error=None,
        )
        return {"status": "skipped_existing", "hotel_id": hotel_id}

    save_manifest(state="layer2a_in_progress", error=None)
    ledgers: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        chunk_id = chunk["chunk_id"]
        ledger_path = ledger_dir / f"{chunk_id}.json"
        if ledger_path.exists() and not force:
            ledger = load_json(ledger_path)
            jsonschema.validate(ledger, chunk_schema)
            validate_ids(collect_ledger_ids(ledger), set(chunk["reviews"][i]["review_id"] for i in range(len(chunk["reviews"]))), f"ledger {chunk_id}")
        else:
            codex_output = codex_tmp / f"{chunk_id}.json"
            ledger = run_codex_json(
                prompt_for(rubric + "\n\n" + chunk_prompt, chunk),
                chunk_schema_path,
                codex_output,
            )
            usage.append(ledger.pop("_codex_usage", {}))
            jsonschema.validate(ledger, chunk_schema)
            if ledger["hotel_id"] != hotel_id or ledger["chunk_id"] != chunk_id:
                raise ValueError(f"Ledger identity mismatch for {chunk_id}.")
            if ledger["review_count"] != chunk["review_count"]:
                raise ValueError(f"Ledger review_count mismatch for {chunk_id}.")
            validate_ids(collect_ledger_ids(ledger), set(r["review_id"] for r in chunk["reviews"]), f"ledger {chunk_id}")
            dump_json(ledger_path, ledger)
            dump_json(ledger_path.with_suffix(".codex.json"), {"execution_mode": CODEX_MODE, "model": MODEL, "usage": usage[-1]})
        ledgers.append(ledger)
        save_manifest(layer2a_chunks_complete=index)

    save_manifest(state="layer2a_complete", layer2b_status="in_progress")
    hotel_context = compact_hotel_context(dossier, ledgers)
    codex_output = codex_tmp / "assessment.json"
    assessment = run_codex_json(
        prompt_for(rubric + "\n\n" + final_prompt, hotel_context),
        final_schema_path,
        codex_output,
    )
    usage.append(assessment.pop("_codex_usage", {}))
    jsonschema.validate(assessment, final_schema)
    warnings = validate_final_semantics(assessment, dossier)
    save_manifest(layer2b_status="complete", schema_validation_status="valid")

    assessment["display_anchor"] = mapping["mapping"][assessment["band"]][assessment["band_position"]]
    assessment["display_mapping_version"] = mapping["version"]
    assessment["display_mapping_warning"] = mapping["warning"]
    assessment["validation_warnings"] = warnings
    dump_json(assessment_path, assessment)
    dump_json(metadata_path, {
        "execution_mode": CODEX_MODE,
        "model": MODEL,
        "provider": "Codex CLI",
        "external_llm_api_calls": 0,
        "hotel_id": hotel_id,
        "source_dossier": dossier_path.name,
        "chunk_count": len(chunks),
        "usage": usage,
        "validation_warnings": warnings,
        "completed_at": now_iso(),
    })
    save_manifest(mapping_status="complete", final_status="complete", state="complete", error=None)
    return {"status": "completed", "hotel_id": hotel_id, "warnings": warnings}


def write_summaries(output_dir: Path, manifest: dict[str, Any], errors: list[dict[str, Any]]) -> None:
    assessments = []
    for p in sorted((output_dir / "hotels").glob("*/assessment.json")):
        try:
            assessments.append(load_json(p))
        except Exception:
            continue
    def distribution(key: str, values: list[str]) -> dict[str, int]:
        return {v: sum(1 for a in assessments if a.get(key) == v) for v in values}
    bands = distribution("band", list("ABCDEFGH"))
    positions = distribution("band_position", ["upper", "middle", "lower"])
    confidence = distribution("confidence", ["High", "Medium-high", "Medium", "Low-medium", "Low"])
    temporal = distribution("temporal_status", ["improving", "stable_positive", "mixed", "stable_concern", "worsening", "insufficient_recent_evidence"])
    successful = len(assessments)
    attempted = len(manifest["hotels"])
    summary = {
        "dataset": manifest["dataset"],
        "workload": manifest["workload"],
        "completion": {"hotels_attempted": attempted, "hotels_successfully_completed": successful, "hotels_failed": len(errors), "completion_percentage": round(successful / attempted * 100, 2) if attempted else 0},
        "band_distribution": bands,
        "band_position_distribution": positions,
        "confidence_distribution": confidence,
        "temporal_status_distribution": temporal,
        "validation": {"schema_valid_hotels": successful, "warnings": sum(len(a.get("validation_warnings", [])) for a in assessments), "failures": len(errors)},
        "failed_hotels": errors,
        "execution_environment": CODEX_MODE + ".",
        "external_llm_api_calls": 0,
    }
    dump_json(output_dir / "production_run_summary.json", summary)
    lines = [
        "# TrustStay Layer 2 production run summary",
        "",
        "## Dataset",
        f"- Hotels found: {manifest['dataset']['hotels']}",
        f"- Reviews found: {manifest['dataset']['reviews']}",
        "",
        "## Workload",
        f"- Layer 2A assessments: {manifest['workload']['layer2a_assessments']}",
        f"- Layer 2B assessments: {manifest['workload']['layer2b_assessments']}",
        f"- Total logical assessments: {manifest['workload']['total_logical_assessments']}",
        "",
        "## Completion",
        f"- Hotels attempted: {attempted}",
        f"- Hotels successfully completed: {successful}",
        f"- Hotels failed: {len(errors)}",
        f"- Completion percentage: {summary['completion']['completion_percentage']}%",
        "",
        "## Band distribution",
        "| Band | Hotels | Percentage |\n| --- | ---: | ---: |",
    ]
    for band, count in bands.items():
        lines.append(f"| {band} | {count} | {count / successful * 100:.2f}% |" if successful else f"| {band} | 0 | 0.00% |")
    for title, values in [("Band-position", positions), ("Confidence", confidence), ("Temporal-status", temporal)]:
        lines += ["", f"## {title} distribution", ""]
        lines += [f"- {k}: {v}" for k, v in values.items()]
    lines += ["", "## Validation", f"- Schema-valid hotels: {successful}", f"- Warnings: {summary['validation']['warnings']}", f"- Failures: {len(errors)}", "", "## Execution environment", f"- {CODEX_MODE}.", "- External LLM API calls: 0"]
    if errors:
        lines += ["", "## Failed hotels", "", "| Hotel | Stage | Error |", "| --- | --- | --- |"]
        lines += [f"| {e.get('hotel_id', '')} | {e.get('stage', '')} | {e.get('error', '')} |" for e in errors]
    (output_dir / "production_run_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--max-hotels", type=int, default=None)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    base = args.project_dir.resolve()
    output_dir = (args.output or base / "layer2_outputs").resolve()
    source_dir = base / "full_dossiers"
    dossiers = sorted(source_dir.glob("*.json"))
    if args.max_hotels is not None:
        dossiers = dossiers[: args.max_hotels]
    rubric_path = base / "TrustStay_Layer2_Runtime_Rubric_v1_4_20260816.md"
    chunk_prompt_path = base / "prompts/chunk_extraction.md"
    final_prompt_path = base / "prompts/hotel_adjudication.md"
    chunk_schema_path = base / "schemas/chunk_ledger.schema.json"
    final_schema_path = base / "schemas/hotel_assessment.schema.json"
    mapping_path = base / "TrustStay_Display_Mapping_v1_0_20260816.json"
    rubric = rubric_path.read_text(encoding="utf-8")
    chunk_prompt = chunk_prompt_path.read_text(encoding="utf-8")
    final_prompt = final_prompt_path.read_text(encoding="utf-8")
    chunk_schema = load_json(chunk_schema_path)
    final_schema = load_json(final_schema_path)
    mapping = load_json(mapping_path)
    chunk_counts, review_counts = {}, {}
    for p in dossiers:
        d = read_dossier(p)
        chunk_counts[d["hotel_id"]] = len(build_chunks(d["review_evidence_records"], d["hotel_id"], 180000))
        review_counts[d["hotel_id"]] = len(d["review_evidence_records"])
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "run_manifest.json"
    if manifest_path.exists() and not args.force:
        manifest = load_json(manifest_path)
    else:
        manifest = initial_manifest(dossiers, rubric_path, chunk_prompt_path, final_prompt_path, chunk_schema_path, final_schema_path, mapping_path, chunk_counts, review_counts)
        dump_json(manifest_path, manifest)
    lock = threading.Lock()
    errors: list[dict[str, Any]] = []
    errors_lock = threading.Lock()
    def work(p: Path) -> dict[str, Any]:
        try:
            return process_hotel(p, output_dir, rubric, chunk_prompt, final_prompt, chunk_schema, final_schema, chunk_schema_path, final_schema_path, mapping, manifest, manifest_path, lock, args.force)
        except Exception as exc:
            hotel_id = load_json(p).get("hotel_id", p.name)
            error = {"hotel_id": hotel_id, "stage": row_for(manifest, hotel_id).get("state", "unknown"), "error": f"{type(exc).__name__}: {exc}"}
            with errors_lock:
                errors.append(error)
                with lock:
                    update_row(manifest, hotel_id, state="failed", final_status="failed", error=error["error"])
                    dump_json(manifest_path, manifest)
            return {"status": "failed", **error}
    with futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for result in pool.map(work, dossiers):
            print(json.dumps(result, ensure_ascii=False), flush=True)
    rows = []
    for p in sorted((output_dir / "hotels").glob("*/assessment.json")):
        rows.append(load_json(p))
    with (output_dir / "assessments.jsonl").open("w", encoding="utf-8") as f:
        for row in sorted(rows, key=lambda x: x.get("hotel_id", "")):
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest["completed_at"] = now_iso()
    manifest["successful_hotels"] = len(rows)
    manifest["failed_hotels"] = len(errors)
    dump_json(manifest_path, manifest)
    audit = {
        "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "execution_mode": CODEX_MODE,
        "assessment_model": MODEL,
        "external_llm_api_calls": 0,
        "dataset": manifest["dataset"],
        "workload": manifest["workload"],
        "dossier_ordering": manifest["dossier_ordering"],
        "successful_hotels": len(rows),
        "failed_hotels": len(errors),
        "frozen_files": manifest["frozen_files"],
        "orchestration_changes": ["Added codex_luna_adapter.py; frozen methodology files and source dossiers unchanged."],
        "usage_metadata": "Codex CLI token totals are recorded per assessment where exposed; input/cached/output/reasoning breakdowns are null when the CLI does not expose them.",
    }
    dump_json(output_dir / "audit_record.json", audit)
    write_summaries(output_dir, manifest, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
