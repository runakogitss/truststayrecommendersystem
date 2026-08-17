"""Configuration loading.

Portability rule
----------------
Nothing in this package may depend on a path outside the extracted package
directory.  ``package_root()`` is derived from this file's own location, so a
freshly extracted copy in any directory resolves its own data and configs.
Relative paths in a YAML file are resolved from that YAML file's directory,
never from the current working directory and never from the machine on which
the package was built.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def package_root() -> Path:
    """Root of the extracted package (the directory containing ``src/``)."""
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SamplePaths:
    """Locations of the self-contained frozen research sample."""

    sample_dir: Path
    reviews_path: Path
    features_path: Path
    embeddings_path: Path
    mapping_path: Path
    sample_definition_path: Path
    hash_manifest_path: Path
    source_provenance_path: Path

    def as_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in self.__dict__.items()}

    def missing(self) -> list[str]:
        return [
            name
            for name, value in self.__dict__.items()
            if name != "sample_dir" and not Path(value).is_file()
        ]


@dataclass(frozen=True)
class PipelineConfig:
    """Deterministic evidence-preparation settings.

    These are frozen scientific settings. Changing ``semantic_grouping_method``,
    ``semantic_similarity_threshold`` or ``representatives_per_cluster`` is a methodology
    change and requires researcher approval plus a new frozen version record.
    """

    dataset_namespace: str = "HOTELREC"
    semantic_grouping_method: str = "complete_linkage"
    semantic_similarity_threshold: float = 0.80
    random_seed: int = 20260725
    representatives_per_cluster: int = 3
    require_minilm_verified: bool = True
    allowed_absa_methods: tuple[str, ...] = ("deberta_absa", "distilled_proxy", "none")
    forbidden_dataset_names: tuple[str, ...] = ("booking", "ott", "maide", "synthetic", "attack")
    temporal_windows: dict[str, int] = field(
        default_factory=lambda: {"last_90_days": 90, "last_180_days": 180, "last_365_days": 365}
    )


def load_yaml(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open() as handle:
        value = yaml.safe_load(handle) or {}
    if not isinstance(value, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return value


def _resolve(base: Path, value: str) -> Path:
    candidate = Path(str(value)).expanduser()
    return candidate if candidate.is_absolute() else (base / candidate).resolve()


def load_sample_paths(sample_dir: Path | str | None = None) -> SamplePaths:
    """Resolve the bundled frozen-sample layout.

    Defaults to ``<package root>/data/frozen_research_sample``.
    """
    base = Path(sample_dir).expanduser().resolve() if sample_dir else (package_root() / "data" / "frozen_research_sample").resolve()
    return SamplePaths(
        sample_dir=base,
        reviews_path=base / "reviews.parquet",
        features_path=base / "features.parquet",
        embeddings_path=base / "embeddings.npz",
        mapping_path=base / "review_hotel_mapping.parquet",
        sample_definition_path=base / "sample_definition.json",
        hash_manifest_path=base / "SHA256_MANIFEST.csv",
        source_provenance_path=base / "SOURCE_PROVENANCE.json",
    )


def load_config(path: Path | None = None, temporal_path: Path | None = None) -> PipelineConfig:
    path = Path(path) if path else package_root() / "configs" / "evidence_pipeline.yaml"
    temporal_path = Path(temporal_path) if temporal_path else package_root() / "configs" / "temporal_windows.yaml"
    raw = load_yaml(path)
    temporal = load_yaml(temporal_path)
    windows = {str(k): int(v) for k, v in temporal.get("windows", {}).items()}
    if not windows:
        raise ValueError(f"No temporal windows defined in {temporal_path}")
    forbidden = raw.get("forbidden_dataset_names", raw.get("forbidden_tokens", ["booking", "ott", "maide", "synthetic", "attack"]))
    return PipelineConfig(
        dataset_namespace=str(raw.get("dataset_namespace", "HOTELREC")),
        semantic_grouping_method=str(raw.get("semantic_grouping_method", "complete_linkage")),
        semantic_similarity_threshold=float(raw.get("semantic_similarity_threshold", 0.80)),
        random_seed=int(raw.get("random_seed", 20260725)),
        representatives_per_cluster=int(raw.get("representatives_per_cluster", 3)),
        require_minilm_verified=bool(raw.get("require_minilm_verified", True)),
        allowed_absa_methods=tuple(raw.get("allowed_absa_methods", ["deberta_absa", "distilled_proxy", "none"])),
        forbidden_dataset_names=tuple(forbidden),
        temporal_windows=windows,
    )


@dataclass(frozen=True)
class UpstreamPaths:
    """Locations of the researcher's external locked artefacts.

    Only ``scripts/export_frozen_sample.py`` uses these.  They are never
    required for the examiner rerun.
    """

    locked_input_path: Path
    feature_index_path: Path
    minilm_npz_path: Path
    verification_dir: Path | None = None

    def as_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in self.__dict__.items() if value is not None}


def load_upstream_paths(path: Path) -> UpstreamPaths:
    path = Path(path).expanduser().resolve()
    raw = load_yaml(path)
    required = ["locked_input_path", "feature_index_path", "minilm_npz_path"]
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"Missing upstream path keys in {path}: {missing}")
    verification = raw.get("verification_dir")
    return UpstreamPaths(
        locked_input_path=_resolve(path.parent, raw["locked_input_path"]),
        feature_index_path=_resolve(path.parent, raw["feature_index_path"]),
        minilm_npz_path=_resolve(path.parent, raw["minilm_npz_path"]),
        verification_dir=_resolve(path.parent, verification) if verification else None,
    )
