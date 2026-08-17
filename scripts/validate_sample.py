#!/usr/bin/env python3
"""Validate the bundled frozen research sample only. Exits non-zero on failure."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from truststay_evidence.config import load_config, load_sample_paths, package_root
from truststay_evidence.provenance import write_json
from truststay_evidence.validation import ValidationFailure, validate_frozen_sample


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-dir", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--skip-hash-verification", action="store_true")
    args = parser.parse_args()
    paths = load_sample_paths(args.sample_dir)
    config = load_config()
    try:
        report = validate_frozen_sample(paths, config, verify_hashes=not args.skip_hash_verification)
    except ValidationFailure as error:
        print(f"VALIDATION FAILED\n\n{error}", file=sys.stderr)
        return 2
    target = args.report or (package_root() / "outputs" / "frozen_research_run" / "validation" / "frozen_sample_validation.json")
    write_json(target, report)
    print(json.dumps({k: v for k, v in report.items() if k != "hash_verification"}, indent=2, sort_keys=True))
    print(f"\nPASS. Report written to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
