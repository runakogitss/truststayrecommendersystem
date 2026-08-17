#!/usr/bin/env python3
"""Report semantic-grouping and representative-selection behaviour.

Reports only. Changes no clustering parameter and no selection rule.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from truststay_evidence.config import load_config, package_root
from truststay_evidence.diagnostics import aggregate_diagnostics, hotel_diagnostics
from truststay_evidence.provenance import write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()
    root = args.output_dir or (package_root() / "outputs" / "frozen_research_run")
    config = load_config()
    full_dir, compact_dir = root / "full_dossiers", root / "compact_dossiers"
    files = sorted(full_dir.glob("hotel_*_full.json"))
    if not files:
        print(f"FAILED: no dossiers in {full_dir}", file=sys.stderr)
        return 2
    per_hotel = []
    for path in files:
        dossier = json.loads(path.read_text(encoding="utf-8"))
        compact = compact_dir / path.name.replace("_full.json", "_compact.json")
        per_hotel.append(hotel_diagnostics(dossier, path, compact, config.semantic_similarity_threshold))
    summary = aggregate_diagnostics(per_hotel, config.semantic_similarity_threshold)
    write_json(root / "diagnostics" / "per_hotel_diagnostics.json", {"hotels": per_hotel})
    write_json(root / "diagnostics" / "cluster_diagnostics_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    biggest = sorted((c for d in per_hotel for c in d["large_clusters"]), key=lambda c: -c["unique_review_count"])[: args.top]
    if biggest:
        print("\nLargest clusters inspected:")
        for cluster in biggest:
            print(json.dumps(cluster, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
