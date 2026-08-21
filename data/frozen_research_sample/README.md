# Frozen research sample — private handover layout

The review-bearing files described below belong to the separate
private/self-contained professor handover package. They are intentionally not
committed to the public GitHub repository. This public directory retains only
metadata documentation and `SOURCE_PROVENANCE.json`.

This directory holds the complete, self-contained data for the frozen Layer 1
research run. It is produced once by the researcher with:

    python scripts/export_frozen_sample.py --upstream configs/upstream_paths.local.yaml \
        --target-reviews 100000 --seed 20260812

Expected contents:

    reviews.parquet         raw review records
    features.parquet        aligned review-level features / ABSA evidence
    embeddings.npz          aligned MiniLM vectors
    review_hotel_mapping.parquet  stable review ID / hotel ID mapping in sample order
    sample_definition.json  deterministic hotel selection (hash-signed)
    SOURCE_PROVENANCE.json  upstream artefact identity and hashes
    SHA256_MANIFEST.csv     hashes of all of the above

If these files are absent, `scripts/run_handover.py` stops immediately with an
explanatory message rather than producing partial output.
