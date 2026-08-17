#!/usr/bin/env python3
"""One-command examiner rerun of TrustStay Layer 1.

    python scripts/run_handover.py

Runs, in order: sample validation -> Layer 1 execution -> output validation ->
manifest generation. Any failure stops the run with a non-zero exit status and
a printed reason. Nothing is swallowed.

Layer 1 ends at the evidence dossier. This script never produces an LLM call,
a severity or recurrence judgement, a hotel-quality estimate, a TrustStay
score, an A-H band or a booking recommendation.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from truststay_evidence.config import load_config, load_sample_paths, package_root  # noqa: E402
from truststay_evidence.manifest import create_submission_manifest  # noqa: E402
from truststay_evidence.pipeline import run_layer1, validate_outputs  # noqa: E402
from truststay_evidence.provenance import write_json  # noqa: E402
from truststay_evidence.validation import ValidationFailure, validate_frozen_sample  # noqa: E402

RULE = "=" * 78


def banner(step: str, title: str) -> None:
    print(f"\n{RULE}\n{step}  {title}\n{RULE}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample-dir", type=Path, default=None, help="Defaults to data/frozen_research_sample")
    parser.add_argument("--output-dir", type=Path, default=None, help="Defaults to outputs/frozen_research_run")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--temporal", type=Path, default=None)
    parser.add_argument("--hotel-limit", type=int, default=None, help="Smoke test only: process the first N hotels")
    parser.add_argument("--skip-hash-verification", action="store_true", help="Not recommended; recorded in the report")
    args = parser.parse_args()

    root = package_root()
    paths = load_sample_paths(args.sample_dir)
    config = load_config(args.config, args.temporal)
    output_root = (args.output_dir or (root / "outputs" / "frozen_research_run")).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    print(f"TrustStay Layer 1 - Reproducible Evidence Engine")
    print(f"package root : {root}")
    print(f"sample dir   : {paths.sample_dir}")
    print(f"output dir   : {output_root}")

    # ---------------------------------------------------------------- step 1
    banner("[1/4]", "Validating the frozen research sample")
    try:
        validation = validate_frozen_sample(paths, config, verify_hashes=not args.skip_hash_verification)
    except ValidationFailure as error:
        print(f"\nFAILED: the supplied research sample did not validate.\n\n{error}\n", file=sys.stderr)
        return 2
    except Exception:
        traceback.print_exc()
        print("\nFAILED: unexpected error during sample validation.\n", file=sys.stderr)
        return 2
    write_json(output_root / "validation" / "frozen_sample_validation.json", validation)
    counts = validation["row_counts"]
    print(f"  hotels          : {counts['hotels']}")
    print(f"  reviews         : {counts['reviews']}")
    print(f"  feature rows    : {counts['features']}")
    print(f"  embedding rows  : {counts['embeddings']}")
    print(f"  alignment       : PASS (identical IDs, identical order, no truncation)")
    print(f"  ABSA labels     : {validation['absa']['method_counts']}")
    print("  STEP 1 PASS")

    # ---------------------------------------------------------------- step 2
    banner("[2/4]", "Running Layer 1 (evidence consolidation)")
    print("  Reusing verified precomputed ABSA and MiniLM artefacts.")
    print("  No DeBERTa or MiniLM inference is performed in this rerun.")
    execution = run_layer1(paths, config, output_root, validation, hotel_limit=args.hotel_limit)
    print(f"  hotels processed: {execution['hotels_processed']} (failed: {execution['hotels_failed']})")
    print(f"  full dossiers   : {execution['full_dossiers_written']}")
    print(f"  compact dossiers: {execution['compact_dossiers_written']}")
    print(f"  runtime         : {execution['runtime_seconds']['total']} s")
    print(f"  peak RSS        : {execution['peak_rss_mb']} MB")
    if execution["status"] != "PASS":
        print(f"\nFAILED: {execution['hotels_failed']} hotel(s) did not build.", file=sys.stderr)
        for failure in execution["failures"][:10]:
            print(f"  - {failure['hotel_id']}: {failure['error']}", file=sys.stderr)
        return 3
    print("  STEP 2 PASS")

    # ---------------------------------------------------------------- step 3
    banner("[3/4]", "Validating generated dossiers")
    try:
        output_validation = validate_outputs(output_root)
    except Exception as error:
        print(f"\nFAILED: dossier validation error: {type(error).__name__}: {error}\n", file=sys.stderr)
        return 4
    write_json(output_root / "validation" / "dossier_validation.json", output_validation)
    print(f"  full dossiers validated   : {output_validation['full_dossier_count']}")
    print(f"  compact dossiers validated: {output_validation['compact_dossier_count']}")
    print(f"  reviews covered           : {output_validation['total_reviews_in_dossiers']}")
    print(f"  semantic clusters         : {output_validation['total_clusters']}")

    expected_reviews = int(validation["sample_definition"]["declared_review_count"])
    if args.hotel_limit is None and output_validation["total_reviews_in_dossiers"] != expected_reviews:
        print(
            f"\nFAILED: dossiers cover {output_validation['total_reviews_in_dossiers']} reviews "
            f"but the frozen sample declares {expected_reviews}.\n",
            file=sys.stderr,
        )
        return 5
    print("  STEP 3 PASS")

    # ---------------------------------------------------------------- step 4
    banner("[4/4]", "Writing submission manifest")
    manifest = create_submission_manifest(root, paths, config, output_root, validation, execution, output_validation)
    print(f"  manifest files hashed: {manifest['hashed_file_count']}")
    print(f"  written to           : {output_root / 'manifests'}")
    print("  STEP 4 PASS")

    banner("RESULT", "ALL STEPS PASSED")
    summary = {
        "status": "PASS",
        "hotels": counts["hotels"] if args.hotel_limit is None else execution["hotels_processed"],
        "reviews": output_validation["total_reviews_in_dossiers"],
        "full_dossiers": output_validation["full_dossier_count"],
        "compact_dossiers": output_validation["compact_dossier_count"],
        "runtime_seconds": execution["runtime_seconds"]["total"],
        "hotel_limit_applied": args.hotel_limit,
    }
    write_json(output_root / "validation" / "run_summary.json", summary)
    print(json.dumps(summary, indent=2))
    print(f"\nOutputs: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
