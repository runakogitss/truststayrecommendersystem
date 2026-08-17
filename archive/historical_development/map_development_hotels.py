from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from truststay_evidence.config import load_paths
from truststay_evidence.loaders import list_hotel_ids, load_feature_index


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Map requested development HotelRec IDs without fuzzy matching.")
    parser.add_argument("--hotel-id", action="append", default=[])
    parser.add_argument("--file", type=Path, help="Text or CSV file containing requested hotel IDs")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    requested = list(args.hotel_id)
    if args.file:
        if args.file.suffix.lower() == ".csv":
            with args.file.open(newline="") as handle:
                reader = csv.DictReader(handle)
                key = "hotel_id" if "hotel_id" in (reader.fieldnames or []) else (reader.fieldnames or [None])[0]
                requested.extend(row[key] for row in reader if key and row.get(key))
        else:
            requested.extend(line.strip() for line in args.file.read_text().splitlines() if line.strip())
    feature_index_path = load_paths(root / "configs/paths.example.yaml").feature_index_path
    available_frame = load_feature_index(feature_index_path, columns=["hotel_id"])
    counts = available_frame["hotel_id"].astype(str).value_counts().to_dict()
    available = set(counts)
    rows = []
    for value in dict.fromkeys(str(item) for item in requested):
        matched = value if value in available else ""
        rows.append({"requested_hotel_id": value, "matched_hotel_id": matched, "match_method": "exact_hotel_id" if matched else "unmatched", "matching_review_count": counts.get(matched, 0), "match_confidence": "exact" if matched else "none", "unmatched_status": "" if matched else "UNMATCHED_NO_EXACT_ID"})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["requested_hotel_id", "matched_hotel_id", "match_method", "matching_review_count", "match_confidence", "unmatched_status"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
