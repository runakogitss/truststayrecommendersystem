#!/usr/bin/env python3
"""Generate a SYNTHETIC smoke fixture with the same shape as a frozen sample.

    python scripts/make_smoke_fixture.py --output data/smoke_fixture_sample

PURPOSE
-------
To let anyone verify that the package installs, validates, runs, produces
dossiers and passes its tests on a clean machine WITHOUT access to the
researcher's licensed review corpus.

THIS IS NOT RESEARCH DATA. The text, ratings, dates and embedding vectors are
generated from a fixed seed. Nothing produced from this fixture may be cited,
reported, or presented as a TrustStay result. The fixture is written to a
separate directory and never to ``data/frozen_research_sample``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from truststay_evidence.config import load_config, load_sample_paths, package_root  # noqa: E402
from truststay_evidence.frozen_sample import sha256_text, write_embeddings, write_hash_manifest  # noqa: E402
from truststay_evidence.sample import build_sample_definition  # noqa: E402
from truststay_evidence.validation import validate_frozen_sample  # noqa: E402

WARNING = """SYNTHETIC SMOKE FIXTURE - NOT RESEARCH DATA

Every review text, rating, date and embedding vector in this directory was
generated deterministically by scripts/make_smoke_fixture.py. It exists only to
prove that the Layer 1 code installs and executes on a clean machine.

Do not cite, report, or present anything derived from this directory. The real
frozen research sample lives in data/frozen_research_sample.
"""

ASPECTS = ["room", "staff", "food", "location", "cleanliness", "value", "noise", "facilities"]
THEMES = [
    "The room was comfortable and the bed was well made.",
    "Staff at reception were helpful throughout the stay.",
    "Breakfast selection was reasonable but repetitive.",
    "Location is convenient for the central district.",
    "There was persistent noise from the corridor at night.",
    "The bathroom had a slow drain that was not fixed.",
    "Check-in took far longer than expected on arrival.",
    "Air conditioning in the room did not work properly.",
]


def build(output: Path, hotels: int, reviews_per_hotel: int, dim: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    start = date(2012, 1, 1)
    for hotel_index in range(hotels):
        hotel_id = f"SmokeHotel_{hotel_index + 1:03d}"
        # A deliberate mix: some near-identical texts so grouping has something to do.
        for review_index in range(reviews_per_hotel):
            theme = THEMES[review_index % len(THEMES)]
            suffix = "" if review_index % 5 else f" Visit number {review_index // 5}."
            rows.append(
                {
                    "hotel_id": hotel_id,
                    "review_id": f"smoke_{hotel_index + 1:03d}_{review_index + 1:05d}",
                    "review_date": (start + timedelta(days=int(rng.integers(0, 2500)))).isoformat(),
                    "rating": float(int(rng.integers(1, 6))),
                    "review_text": theme + suffix,
                }
            )
    frame = pd.DataFrame(rows).sort_values(["hotel_id", "review_date", "review_id"], kind="mergesort").reset_index(drop=True)
    n = len(frame)

    # Deterministic embeddings: one base direction per theme plus small noise, so
    # the clustering step sees genuinely related and genuinely unrelated evidence.
    bases = rng.normal(size=(len(THEMES), dim)).astype(np.float32)
    bases /= np.linalg.norm(bases, axis=1, keepdims=True)
    theme_index = np.array([THEMES.index(t.split(" Visit number")[0]) for t in frame["review_text"]])
    embeddings = bases[theme_index] + rng.normal(scale=0.02, size=(n, dim)).astype(np.float32)
    embeddings = (embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)).astype(np.float32)

    methods = np.where(rng.random(n) < 0.05, "deberta_absa", "distilled_proxy")
    status = {"deberta_absa": "REAL_MODEL_REUSABLE", "distilled_proxy": "PROXY_SEPARATE_ONLY", "none": "NO_RESULT"}
    aspects, sentiments = [], []
    for method in methods:
        if method == "deberta_absa":
            picked = rng.choice(ASPECTS, size=int(rng.integers(1, 3)), replace=False)
            aspects.append(";".join(sorted(picked)))
            sentiments.append(";".join(f"{a}:{round(float(rng.uniform(-1, 1)), 3)}" for a in sorted(picked)))
        else:
            aspects.append("")
            sentiments.append("")

    features = pd.DataFrame(
        {
            "source_dataset": "HOTELREC",
            "hotel_id": frame["hotel_id"],
            "review_id": frame["review_id"],
            "review_date": frame["review_date"],
            "rating": frame["rating"],
            "review_text": frame["review_text"],
            "text_sha256": frame["review_text"].map(sha256_text),
            "input_row_position": np.arange(n, dtype=np.int64),
            "minilm_embedding_row": np.arange(n, dtype=np.int64),
            "minilm_verified": True,
            "absa_aspect": aspects,
            "absa_sentiment": sentiments,
            "absa_confidence": pd.Series([pd.NA] * n, dtype="object"),
            "absa_method": methods,
            "absa_reusable_status": [status[m] for m in methods],
            "duplicate_group_id": "",
            "cluster_id": "",
            "exact_reuse": False,
            "source_input_row_position": np.arange(n, dtype=np.int64),
            "source_minilm_embedding_row": np.arange(n, dtype=np.int64),
        }
    )
    reviews = pd.DataFrame(
        {
            "review_id": frame["review_id"],
            "hotel_id": frame["hotel_id"],
            "review_date": frame["review_date"],
            "rating_normalized_5": frame["rating"],
            "text": frame["review_text"],
            "platform": "smoke_fixture",
        }
    )

    reviews.to_parquet(output / "reviews.parquet", index=False)
    features.to_parquet(output / "features.parquet", index=False)
    write_embeddings(output / "embeddings.npz", embeddings, frame["review_id"].tolist(), "sentence_transformers")
    pd.DataFrame(
        {
            "sample_row_position": np.arange(n, dtype=np.int64),
            "review_id": frame["review_id"].astype(str),
            "hotel_id": frame["hotel_id"].astype(str),
            "source_input_row_position": np.arange(n, dtype=np.int64),
            "source_minilm_embedding_row": np.arange(n, dtype=np.int64),
        }
    ).to_parquet(output / "review_hotel_mapping.parquet", index=False)

    counts = features.groupby("hotel_id", sort=True).size()
    build_sample_definition(
        counts,
        output / "sample_definition.json",
        target_reviews=n,
        seed=seed,
        source_description="SYNTHETIC SMOKE FIXTURE - not research data",
    )
    (output / "SOURCE_PROVENANCE.json").write_text(
        json.dumps(
            {
                "generated_utc": "fixture",
                "note": "SYNTHETIC SMOKE FIXTURE. No upstream research artefact was used.",
                "upstream_sources": {"locked_input_sha256": "n/a-synthetic-fixture"},
                "models_recorded_upstream": {"verified_by_this_package": False},
                "row_rebasing": {"applied": True, "embedding_values_changed": False, "row_order_changed": False},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    (output / "THIS_IS_NOT_RESEARCH_DATA.txt").write_text(WARNING)
    write_hash_manifest(
        output,
        [
            "reviews.parquet",
            "features.parquet",
            "embeddings.npz",
            "review_hotel_mapping.parquet",
            "sample_definition.json",
            "SOURCE_PROVENANCE.json",
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=package_root() / "data" / "smoke_fixture_sample")
    parser.add_argument("--hotels", type=int, default=6)
    parser.add_argument("--reviews-per-hotel", type=int, default=40)
    parser.add_argument("--dim", type=int, default=384)
    parser.add_argument("--seed", type=int, default=20260812)
    args = parser.parse_args()

    output = args.output.resolve()
    if output.name == "frozen_research_sample":
        print("REFUSED: will not write synthetic data into the frozen research sample directory.", file=sys.stderr)
        return 2
    build(output, args.hotels, args.reviews_per_hotel, args.dim, args.seed)
    report = validate_frozen_sample(load_sample_paths(output), load_config(), verify_hashes=True)
    print(json.dumps(report["row_counts"], indent=2))
    print(f"\nSynthetic smoke fixture written to {output} (NOT research data).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
