#!/usr/bin/env python3
"""Independently verify the frozen-sample SHA-256 manifest. Exits non-zero on mismatch."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from truststay_evidence.config import load_sample_paths
from truststay_evidence.frozen_sample import verify_hash_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-dir", type=Path, default=None)
    args = parser.parse_args()
    paths = load_sample_paths(args.sample_dir)
    if not paths.hash_manifest_path.is_file():
        print(f"FAILED: no hash manifest at {paths.hash_manifest_path}", file=sys.stderr)
        return 2
    try:
        result = verify_hash_manifest(paths.sample_dir, paths.hash_manifest_path)
    except Exception as error:
        print(f"HASH VERIFICATION FAILED\n\n{error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    print(f"\nPASS. {result['files_checked']} file(s) verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
