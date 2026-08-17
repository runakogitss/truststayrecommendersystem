"""A freshly extracted copy must resolve its own paths, with no machine-specific state."""
from __future__ import annotations

import re
from pathlib import Path

from truststay_evidence.config import load_config, load_sample_paths, package_root

ROOT = Path(__file__).resolve().parents[1]


def test_default_paths_resolve_inside_the_package():
    paths = load_sample_paths()
    assert paths.sample_dir == (package_root() / "data" / "frozen_research_sample").resolve()
    assert package_root() == ROOT


def test_configs_load_without_arguments():
    config = load_config()
    assert config.semantic_similarity_threshold == 0.80
    assert config.semantic_grouping_method == "complete_linkage"
    assert config.temporal_windows


def test_no_machine_specific_absolute_paths_in_shipped_files():
    # Assembled from parts so this detector does not match its own source.
    parts = ["/" + "Volumes/", "/" + "Users/[A-Za-z0-9._-]+/", "C:" + chr(92) * 2 + "Users"]
    pattern = re.compile("|".join(parts), re.IGNORECASE)
    for directory in ("src", "scripts", "configs", "tests", "schemas"):
        for path in (ROOT / directory).rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".yaml", ".yml", ".json", ".toml"}:
                continue
            if path.name == Path(__file__).name:
                continue
            hits = pattern.findall(path.read_text(errors="ignore"))
            assert not hits, f"{path.relative_to(ROOT)} contains a machine-specific path: {hits[:3]}"


def test_archive_is_isolated_from_the_execution_path():
    """No shipped module may import or reference archived development code."""
    pattern = re.compile(
        r"^\s*(?:from|import)\s+archive\b|archive/historical_development|phase1b_claims",
        re.MULTILINE,
    )
    for directory in ("src", "scripts"):
        for path in (ROOT / directory).rglob("*.py"):
            hits = pattern.findall(path.read_text())
            assert not hits, f"{path.name} references archived development code: {hits[:3]}"
