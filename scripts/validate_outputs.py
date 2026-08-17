#!/usr/bin/env python3
"""Validate generated Layer 1 dossiers. Exits non-zero on failure."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from truststay_evidence.config import package_root
from truststay_evidence.pipeline import validate_outputs
from truststay_evidence.provenance import write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    output_root = args.output_dir or (package_root() / "outputs" / "frozen_research_run")
    try:
        report = validate_outputs(output_root)
    except Exception as error:
        print(f"DOSSIER VALIDATION FAILED\n\n{type(error).__name__}: {error}", file=sys.stderr)
        return 2
    target = args.report or (output_root / "validation" / "dossier_validation.json")
    write_json(target, report)
    print(json.dumps({k: v for k, v in report.items() if k != "dossiers"}, indent=2, sort_keys=True))
    print(f"\nPASS. Report written to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
