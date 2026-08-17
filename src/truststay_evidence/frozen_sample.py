"""Read/write access to the self-contained frozen research sample.

The frozen sample is a directory containing exactly the rows required for one
reproducibly defined research run:

    reviews.parquet       raw review records for the selected hotels
    features.parquet      aligned review-level features / ABSA evidence
    embeddings.npz        aligned MiniLM vectors (emb, review_id, method)
    review_hotel_mapping.parquet  stable review-to-hotel row mapping
    sample_definition.json  deterministic hotel selection + its own hash
    SHA256_MANIFEST.csv   hashes of every file above
    SOURCE_PROVENANCE.json  hashes/identity of the upstream locked artefacts

Row re-basing (engineering, not methodology)
--------------------------------------------
The upstream artefacts index embeddings by absolute row position in a
500,000-row corpus.  A self-contained sample cannot carry those rows, so the
export step re-bases ``input_row_position`` and ``minilm_embedding_row`` to
``0..N-1`` within the exported sample and preserves the originals as
``source_input_row_position`` and ``source_minilm_embedding_row``.

Embedding *values*, review identities and row ordering are unchanged.  This is
a change of index origin only and is asserted by ``tests/test_rebasing.py``.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "source_dataset",
    "hotel_id",
    "review_id",
    "review_date",
    "rating",
    "review_text",
    "text_sha256",
    "input_row_position",
    "minilm_embedding_row",
    "minilm_verified",
    "absa_aspect",
    "absa_sentiment",
    "absa_confidence",
    "absa_method",
    "absa_reusable_status",
    "duplicate_group_id",
    "cluster_id",
]

OPTIONAL_FEATURE_COLUMNS = ["exact_reuse", "source_input_row_position", "source_minilm_embedding_row"]

REVIEW_COLUMNS = ["review_id", "hotel_id", "review_date", "rating_normalized_5", "text"]

MAPPING_COLUMNS = [
    "sample_row_position",
    "review_id",
    "hotel_id",
    "source_input_row_position",
    "source_minilm_embedding_row",
]


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_hash_manifest(sample_dir: Path, filenames: list[str]) -> Path:
    sample_dir = Path(sample_dir)
    target = sample_dir / "SHA256_MANIFEST.csv"
    rows = []
    for name in sorted(filenames):
        path = sample_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"Cannot hash missing sample file: {path}")
        rows.append({"path": name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size})
    with target.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "size_bytes"])
        writer.writeheader()
        writer.writerows(rows)
    return target


def read_hash_manifest(path: Path) -> dict[str, str]:
    with Path(path).open(newline="") as handle:
        return {row["path"]: row["sha256"] for row in csv.DictReader(handle)}


def verify_hash_manifest(sample_dir: Path, manifest_path: Path) -> dict:
    """Verify every file recorded in the manifest. Raises on any mismatch."""
    expected = read_hash_manifest(manifest_path)
    if not expected:
        raise ValueError(f"Hash manifest is empty: {manifest_path}")
    checked, mismatches, missing = {}, {}, []
    for name, digest in sorted(expected.items()):
        path = Path(sample_dir) / name
        if not path.is_file():
            missing.append(name)
            continue
        actual = sha256_file(path)
        checked[name] = actual
        if actual != digest:
            mismatches[name] = {"expected": digest, "actual": actual}
    if missing or mismatches:
        raise ValueError(
            "Frozen-sample hash verification FAILED. "
            f"missing={missing} mismatched={sorted(mismatches)}"
        )
    return {"files_checked": len(checked), "hashes": checked, "status": "PASS"}


def load_reviews(path: Path) -> pd.DataFrame:
    import pyarrow.parquet as pq
    frame = pq.read_table(path).to_pandas()
    for column in ("review_id", "hotel_id"):
        if column in frame.columns:
            frame[column] = frame[column].astype(str)
    return frame


def load_mapping(path: Path) -> pd.DataFrame:
    import pyarrow.parquet as pq
    frame = pq.read_table(path).to_pandas()
    for column in ("review_id", "hotel_id"):
        if column in frame.columns:
            frame[column] = frame[column].astype(str)
    return frame


def load_features(path: Path, hotel_ids: list[str] | None = None) -> pd.DataFrame:
    import pyarrow.parquet as pq
    filters = [("hotel_id", "in", [str(v) for v in hotel_ids])] if hotel_ids else None
    frame = pq.read_table(path, filters=filters).to_pandas()
    for column in ("review_id", "hotel_id"):
        if column in frame.columns:
            frame[column] = frame[column].astype(str)
    # Canonical dossier aliases; the source columns are never overwritten.
    if "minilm_embedding_row" in frame.columns and "embedding_row" not in frame.columns:
        frame["embedding_row"] = frame["minilm_embedding_row"]
    if "minilm_verified" in frame.columns and "embedding_verified" not in frame.columns:
        frame["embedding_verified"] = frame["minilm_verified"]
    if "cluster_id" in frame.columns and "semantic_cluster_id" not in frame.columns:
        frame["semantic_cluster_id"] = frame["cluster_id"]
    return frame


def load_embeddings(path: Path) -> tuple[np.ndarray, list[str], str]:
    with np.load(path, allow_pickle=False) as archive:
        for member in ("emb", "review_id", "method"):
            if member not in archive.files:
                raise ValueError(f"Embedding archive {path} lacks required member '{member}'")
        embeddings = np.asarray(archive["emb"])
        review_ids = archive["review_id"].astype(str).tolist()
        method_value = archive["method"]
        method = str(method_value.item() if getattr(method_value, "ndim", 0) == 0 else method_value)
    return embeddings, review_ids, method


def write_embeddings(path: Path, embeddings: np.ndarray, review_ids: list[str], method: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        emb=np.asarray(embeddings, dtype=np.float32),
        review_id=np.array([str(v) for v in review_ids], dtype=object).astype("U"),
        method=np.array(method),
    )
    return path


def load_sample_definition(path: Path) -> dict:
    payload = json.loads(Path(path).read_text())
    if payload.get("sampling_unit") != "hotel_id" or not payload.get("does_not_truncate_hotels"):
        raise ValueError(f"Unsupported or unsafe sample definition: {path}")
    hotel_ids = [str(v) for v in payload.get("hotel_ids", [])]
    if not hotel_ids or len(hotel_ids) != len(set(hotel_ids)):
        raise ValueError("Sample definition must contain a non-empty unique hotel_ids list")
    recorded = payload.get("sample_definition_sha256")
    unsigned = {k: v for k, v in payload.items() if k != "sample_definition_sha256"}
    expected = sha256_text(json.dumps(unsigned, indent=2, sort_keys=True) + "\n")
    if recorded != expected:
        raise ValueError(
            f"Sample definition hash does not match its contents: recorded={recorded} expected={expected}"
        )
    return payload


def write_sample_definition(path: Path, payload: dict) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: v for k, v in payload.items() if k != "sample_definition_sha256"}
    canonical = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    signed = dict(payload)
    signed["sample_definition_sha256"] = sha256_text(canonical)
    path.write_text(json.dumps(signed, indent=2, sort_keys=True) + "\n")
    return signed
