"""Access to the bundled MiniLM embedding archive.

The embeddings are *reused* verified artefacts.  Nothing in this module runs a
sentence-transformer, and nothing here may be described as regenerating
embeddings from raw text.
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def npz_member_shape(path: Path, member_name: str = "emb.npy") -> tuple[int, ...]:
    """Read an uncompressed ``.npy`` member header without materialising it."""
    with zipfile.ZipFile(path) as archive:
        if member_name not in archive.namelist():
            raise ValueError(f"{path} has no member {member_name}")
        with archive.open(member_name) as stream:
            version = np.lib.format.read_magic(stream)
            if version == (1, 0):
                header = np.lib.format.read_array_header_1_0(stream)
            else:
                header = np.lib.format.read_array_header_2_0(stream)
    return tuple(int(x) for x in header[0])


@dataclass
class EmbeddingAccess:
    path: Path
    review_ids: list[str]
    embeddings: np.ndarray
    method: str

    def rows(self, embedding_rows) -> np.ndarray:
        return self.embeddings[np.asarray(embedding_rows, dtype=np.int64)]


def open_embeddings(
    path: Path,
    expected_review_ids: list[str],
    cache_dir: Path | None = None,
) -> EmbeddingAccess:
    """Open the archive, optionally through a read-only memory-mapped cache.

    ``.npz`` archives are not memory-mappable.  When ``cache_dir`` is given the
    ``emb.npy`` member is extracted once and reopened with ``mmap_mode='r'``.
    The source archive is never modified; values and row order are unchanged.
    """
    path = Path(path)
    with np.load(path, allow_pickle=False) as archive:
        review_ids = archive["review_id"].astype(str).tolist()
        method_value = archive["method"]
        method = str(method_value.item() if getattr(method_value, "ndim", 0) == 0 else method_value)
        if cache_dir is None:
            embeddings = np.asarray(archive["emb"])
        else:
            embeddings = None

    if cache_dir is not None:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached = cache_dir / f"{path.name}.emb.npy"
        if not cached.exists() or cached.stat().st_size == 0:
            temporary = cached.with_suffix(cached.suffix + ".partial")
            with zipfile.ZipFile(path) as archive, archive.open("emb.npy") as source, temporary.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            temporary.replace(cached)
        embeddings = np.load(cached, mmap_mode="r", allow_pickle=False)
        header_shape = npz_member_shape(path, "emb.npy")
        if tuple(embeddings.shape) != tuple(header_shape):
            raise ValueError(f"Embedding cache shape {embeddings.shape} differs from archive header {header_shape}")

    expected = [str(v) for v in expected_review_ids]
    if review_ids != expected:
        raise ValueError(
            "Embedding review_id sequence does not match the supplied feature order. "
            "The frozen sample is not aligned; do not proceed."
        )
    if method != "sentence_transformers":
        raise ValueError(f"Unexpected embedding method: {method}")
    return EmbeddingAccess(path, review_ids, embeddings, method)
