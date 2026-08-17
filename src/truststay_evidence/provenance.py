from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .frozen_sample import sha256_file

TRACKED_PACKAGES = ["numpy", "pandas", "pyarrow", "yaml", "sklearn", "pytest"]


def git_commit(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "not_a_git_checkout"


def package_versions() -> dict[str, str]:
    versions = {}
    for name in TRACKED_PACKAGES:
        try:
            module = __import__(name)
            versions[name] = getattr(module, "__version__", "installed")
        except Exception:
            versions[name] = "missing"
    return versions


def environment_record(repository: Path) -> dict:
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.replace("\n", " "),
        "python_executable": sys.executable,
        "machine": platform.machine(),
        "processor": platform.processor(),
        "system": platform.platform(),
        "packages": package_versions(),
        "git_commit": git_commit(repository),
    }


def hash_tree(root: Path, relative_to: Path | None = None, skip_dirs: tuple[str, ...] = ("__pycache__", ".git", ".venv", ".pytest_cache", ".embedding_cache")) -> list[dict]:
    root = Path(root)
    base = Path(relative_to) if relative_to else root
    records = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        try:
            display = str(path.relative_to(base))
        except ValueError:
            display = str(path)
        records.append(
            {
                "path": display,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return records


def write_json(path: Path, payload: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    return path
