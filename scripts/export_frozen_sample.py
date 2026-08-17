#!/usr/bin/env python3
"""RESEARCHER-ONLY: build the self-contained frozen research sample.

The examiner never runs this. It is run once, by the researcher, on the machine
that holds the external locked artefacts, and it writes
``data/frozen_research_sample/`` so that the handover ZIP no longer depends on
those artefacts or on any absolute path.

    python scripts/export_frozen_sample.py \
        --upstream configs/upstream_paths.local.yaml \
        --target-reviews 100000 --seed 20260812

What it does
------------
1. Reads the locked input, the reusable feature index and the MiniLM NPZ.
2. Selects complete hotel histories deterministically (hotels are never
   truncated, so the realised count exceeds the target).
3. Extracts exactly the selected rows from all three sources.
4. Re-bases ``input_row_position`` / ``minilm_embedding_row`` to 0..N-1 and
   preserves the originals as ``source_*`` columns. Embedding VALUES and row
   ORDER are unchanged; only the index origin moves.
5. Writes reviews / features / embeddings / sample definition / hashes /
   upstream provenance, then verifies the exported bundle end to end.

It does NOT run DeBERTa or MiniLM inference and never relabels proxy ABSA rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from truststay_evidence.config import load_config, load_sample_paths, load_upstream_paths, package_root  # noqa: E402
from truststay_evidence.frozen_sample import (  # noqa: E402
    FEATURE_COLUMNS,
    MAPPING_COLUMNS,
    REVIEW_COLUMNS,
    sha256_file,
    write_embeddings,
    write_hash_manifest,
)
from truststay_evidence.sample import build_sample_definition  # noqa: E402
from truststay_evidence.validation import validate_frozen_sample  # noqa: E402

STATUS_BY_METHOD = {
    "deberta_absa": "REAL_MODEL_REUSABLE",
    "distilled_proxy": "PROXY_SEPARATE_ONLY",
    "none": "NO_RESULT",
}


def _first_present(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    for name in candidates:
        if name in frame.columns:
            return name
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--upstream", type=Path, required=True, help="YAML with locked_input_path, feature_index_path, minilm_npz_path")
    parser.add_argument("--target-reviews", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=20260812)
    parser.add_argument("--sample-dir", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    upstream = load_upstream_paths(args.upstream)
    config = load_config(args.config)
    paths = load_sample_paths(args.sample_dir)
    paths.sample_dir.mkdir(parents=True, exist_ok=True)

    for label, path in [
        ("locked_input_path", upstream.locked_input_path),
        ("feature_index_path", upstream.feature_index_path),
        ("minilm_npz_path", upstream.minilm_npz_path),
    ]:
        if not Path(path).is_file():
            print(f"FAILED: {label} does not exist: {path}", file=sys.stderr)
            return 2

    print("Hashing upstream locked artefacts (this can take a few minutes)...", flush=True)
    upstream_hashes = {
        "locked_input_sha256": sha256_file(upstream.locked_input_path),
        "feature_index_sha256": sha256_file(upstream.feature_index_path),
        "minilm_npz_sha256": sha256_file(upstream.minilm_npz_path),
    }
    for key, value in upstream_hashes.items():
        print(f"  {key}: {value}")

    # ---------------------------------------------------------------- select
    print("\nReading feature index...", flush=True)
    index = pq.read_table(upstream.feature_index_path).to_pandas()
    index["hotel_id"] = index["hotel_id"].astype(str)
    index["review_id"] = index["review_id"].astype(str)
    counts = index.groupby("hotel_id", sort=True).size()
    print(f"  {len(index)} rows across {len(counts)} hotels")

    definition = build_sample_definition(
        counts,
        paths.sample_definition_path,
        args.target_reviews,
        args.seed,
        source_description=f"feature index sha256={upstream_hashes['feature_index_sha256']}",
    )
    hotel_ids = [str(v) for v in definition["hotel_ids"]]
    print(f"\nSample definition: {definition['selected_hotel_count']} hotels / {definition['selected_review_count']} reviews")
    print(f"  seed {definition['seed']}, definition sha256 {definition['sample_definition_sha256']}")

    # -------------------------------------------------------------- features
    selected = index[index["hotel_id"].isin(set(hotel_ids))].copy()
    selected = selected.sort_values("input_row_position", kind="mergesort").reset_index(drop=True)
    if len(selected) != int(definition["selected_review_count"]):
        print(
            f"FAILED: extracted {len(selected)} feature rows but the definition declares "
            f"{definition['selected_review_count']}.",
            file=sys.stderr,
        )
        return 3

    source_positions = selected["input_row_position"].to_numpy(dtype=np.int64)
    source_embedding_rows = selected["minilm_embedding_row"].to_numpy(dtype=np.int64)
    selected["source_input_row_position"] = source_positions
    selected["source_minilm_embedding_row"] = source_embedding_rows
    selected["input_row_position"] = np.arange(len(selected), dtype=np.int64)
    selected["minilm_embedding_row"] = np.arange(len(selected), dtype=np.int64)

    if "absa_confidence" not in selected.columns:
        selected["absa_confidence"] = pd.Series([pd.NA] * len(selected), dtype="object")
    if "absa_reusable_status" not in selected.columns:
        selected["absa_reusable_status"] = selected["absa_method"].astype(str).map(STATUS_BY_METHOD)
    if "duplicate_group_id" not in selected.columns:
        selected["duplicate_group_id"] = ""
    if "source_dataset" not in selected.columns:
        selected["source_dataset"] = config.dataset_namespace

    keep = FEATURE_COLUMNS + [c for c in ("exact_reuse", "source_input_row_position", "source_minilm_embedding_row") if c in selected.columns]
    missing = [c for c in FEATURE_COLUMNS if c not in selected.columns]
    if missing:
        print(f"FAILED: feature index lacks required columns {missing}", file=sys.stderr)
        return 3
    features = selected[keep].copy()
    features.to_parquet(paths.features_path, index=False)
    print(f"\nWrote {paths.features_path.name}: {len(features)} rows")

    # --------------------------------------------------------------- reviews
    print("Reading locked input review records...", flush=True)
    raw = pq.read_table(upstream.locked_input_path).to_pandas()
    raw["review_id"] = raw["review_id"].astype(str)
    rating_column = _first_present(raw, ["rating_normalized_5", "rating"])
    text_column = _first_present(raw, ["text", "review_text"])
    date_column = _first_present(raw, ["review_date", "date"])
    hotel_column = _first_present(raw, ["hotel_id"])
    if not all([rating_column, text_column, date_column, hotel_column]):
        print("FAILED: locked input does not expose review_id/hotel_id/date/rating/text columns", file=sys.stderr)
        return 3

    raw[hotel_column] = raw[hotel_column].astype(str)
    if not raw["review_id"].is_unique:
        print("FAILED: locked input contains duplicate review IDs", file=sys.stderr)
        return 3
    source_counts = raw.groupby(hotel_column, sort=True).size()
    selected_counts = selected.groupby("hotel_id", sort=True).size()
    count_mismatches = {
        hotel_id: {
            "feature_index": int(selected_counts[hotel_id]),
            "locked_input": int(source_counts.get(hotel_id, 0)),
        }
        for hotel_id in hotel_ids
        if int(source_counts.get(hotel_id, 0)) != int(selected_counts[hotel_id])
    }
    if count_mismatches:
        print(
            "FAILED: selected hotel histories are not complete in the locked input: "
            + json.dumps(count_mismatches, sort_keys=True),
            file=sys.stderr,
        )
        return 3

    raw = raw.set_index("review_id")
    order = features["review_id"].astype(str).tolist()
    unknown = [rid for rid in order[:] if rid not in raw.index][:5]
    if unknown:
        print(f"FAILED: review IDs present in the feature index are absent from the locked input, e.g. {unknown}", file=sys.stderr)
        return 3
    subset = raw.loc[order]
    reviews = pd.DataFrame(
        {
            "review_id": order,
            "hotel_id": subset[hotel_column].astype(str).to_numpy(),
            "review_date": subset[date_column].to_numpy(),
            "rating_normalized_5": pd.to_numeric(subset[rating_column], errors="coerce").to_numpy(),
            "text": subset[text_column].astype(str).to_numpy(),
        }
    )
    for extra in ("author_id_or_name", "title", "platform"):
        if extra in subset.columns:
            reviews[extra] = subset[extra].to_numpy()
    missing_review_cols = [c for c in REVIEW_COLUMNS if c not in reviews.columns]
    if missing_review_cols:
        print(f"FAILED: could not assemble required review columns {missing_review_cols}", file=sys.stderr)
        return 3
    reviews.to_parquet(paths.reviews_path, index=False)
    print(f"Wrote {paths.reviews_path.name}: {len(reviews)} rows")

    # -------------------------------------------------------------- mapping
    mapping = pd.DataFrame(
        {
            "sample_row_position": np.arange(len(features), dtype=np.int64),
            "review_id": features["review_id"].astype(str).to_numpy(),
            "hotel_id": features["hotel_id"].astype(str).to_numpy(),
            "source_input_row_position": features["source_input_row_position"].to_numpy(dtype=np.int64),
            "source_minilm_embedding_row": features["source_minilm_embedding_row"].to_numpy(dtype=np.int64),
        }
    )[MAPPING_COLUMNS]
    mapping.to_parquet(paths.mapping_path, index=False)
    print(f"Wrote {paths.mapping_path.name}: {len(mapping)} rows")

    # ------------------------------------------------------------ embeddings
    print("Extracting aligned MiniLM rows...", flush=True)
    with np.load(upstream.minilm_npz_path, allow_pickle=False) as archive:
        all_ids = archive["review_id"].astype(str)
        method_value = archive["method"]
        method = str(method_value.item() if getattr(method_value, "ndim", 0) == 0 else method_value)
        emb = archive["emb"]
        taken = np.asarray(emb[source_embedding_rows], dtype=np.float32)
    taken_ids = all_ids[source_embedding_rows].tolist()
    if taken_ids != order:
        print("FAILED: MiniLM row extraction does not align with the selected review order.", file=sys.stderr)
        return 3
    write_embeddings(paths.embeddings_path, taken, order, method)
    print(f"Wrote {paths.embeddings_path.name}: shape {taken.shape}, method {method}")

    # ------------------------------------------------------------ provenance
    provenance = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "note": (
            "This frozen sample was extracted from the researcher's external locked artefacts. "
            "DeBERTa ABSA and MiniLM inference were performed upstream; this package reuses those "
            "verified precomputed outputs and does not regenerate them."
        ),
        "upstream_sources": {
            "locked_input_filename": Path(upstream.locked_input_path).name,
            "feature_index_filename": Path(upstream.feature_index_path).name,
            "minilm_npz_filename": Path(upstream.minilm_npz_path).name,
            **upstream_hashes,
            "upstream_row_count": int(len(index)),
            "upstream_hotel_count": int(len(counts)),
        },
        "models_recorded_upstream": {
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "absa_model": "yangheng/deberta-v3-base-absa-v1.1",
            "verified_by_this_package": False,
            "note": "Model identifiers are recorded from the research record; this package does not re-run or verify them.",
        },
        "row_rebasing": {
            "applied": True,
            "description": "input_row_position and minilm_embedding_row re-based to 0..N-1 within the frozen sample",
            "originals_preserved_as": ["source_input_row_position", "source_minilm_embedding_row"],
            "embedding_values_changed": False,
            "row_order_changed": False,
        },
        "sample_definition_sha256": definition["sample_definition_sha256"],
        "frozen_sample": {
            "selected_hotel_count": int(definition["selected_hotel_count"]),
            "selected_review_count": int(definition["selected_review_count"]),
            "mapping_filename": paths.mapping_path.name,
        },
        "hotel_completeness": {
            "checked_against_locked_input": True,
            "selected_hotel_count_checked": int(len(hotel_ids)),
            "mismatched_hotel_count": int(len(count_mismatches)),
            "all_selected_reviews_present_in_locked_input": not bool(count_mismatches),
        },
    }
    paths.source_provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")

    write_hash_manifest(
        paths.sample_dir,
        [
            "reviews.parquet",
            "features.parquet",
            "embeddings.npz",
            "review_hotel_mapping.parquet",
            "sample_definition.json",
            "SOURCE_PROVENANCE.json",
        ],
    )
    print(f"Wrote {paths.hash_manifest_path.name}")

    # ------------------------------------------------------------- self-test
    print("\nValidating the exported bundle...", flush=True)
    report = validate_frozen_sample(paths, config, verify_hashes=True)
    print(json.dumps(report["row_counts"], indent=2))
    print(json.dumps(report["absa"]["method_counts"], indent=2))
    print("\nEXPORT PASS. data/frozen_research_sample is now self-contained.")
    print("Next: python scripts/run_handover.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
