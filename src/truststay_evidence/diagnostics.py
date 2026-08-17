"""Diagnostics for the frozen final semantic grouping and evidence compaction.

The final semantic method is hotel-level complete-linkage agglomerative
clustering over cosine distance. Diagnostics verify that produced groups obey
that threshold and report cluster size, representative traceability and compact
projection behaviour. They do not change the method.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def cluster_size_distribution(dossier: dict) -> dict:
    sizes = [int(c["unique_review_count"]) for c in dossier["semantic_clusters"]]
    counter = Counter(sizes)
    total = sum(sizes)
    return {
        "cluster_count": len(sizes),
        "review_count": total,
        "singleton_cluster_count": counter.get(1, 0),
        "singleton_share_of_clusters": (counter.get(1, 0) / len(sizes)) if sizes else 0.0,
        "singleton_share_of_reviews": (counter.get(1, 0) / total) if total else 0.0,
        "largest_cluster_size": max(sizes) if sizes else 0,
        "size_histogram": {str(k): int(v) for k, v in sorted(counter.items())},
    }


def large_cluster_report(dossier: dict, threshold: float, min_size: int = 10, top_n: int = 10) -> list[dict]:
    rows = []
    for cluster in dossier["semantic_clusters"]:
        size = int(cluster["unique_review_count"])
        if size < min_size:
            continue
        sim = cluster["internal_similarity_summary"]
        minimum_pairwise = float(sim.get("minimum_pairwise_similarity", 1.0))
        rows.append({
            "semantic_cluster_id": cluster["semantic_cluster_id"],
            "unique_review_count": size,
            "mean_to_centroid": round(float(sim["mean_to_centroid"]), 6),
            "minimum_to_centroid": round(float(sim["minimum_to_centroid"]), 6),
            "minimum_pairwise_similarity": round(minimum_pairwise, 6),
            "meets_complete_linkage_threshold": bool(minimum_pairwise + 1e-6 >= threshold),
            "threshold_margin": round(minimum_pairwise - threshold, 6),
            "earliest_date": cluster["earliest_date"][:10],
            "latest_date": cluster["latest_date"][:10],
            "rating_distribution": cluster["rating_distribution"],
            "representative_review_ids": cluster["representative_review_ids"],
        })
    rows.sort(key=lambda r: -r["unique_review_count"])
    return rows[:top_n]


def representative_traceability(dossier: dict) -> dict:
    record_ids = {str(r["review_id"]) for r in dossier["review_evidence_records"]}
    cluster_of = {str(r["review_id"]): r["semantic_cluster_id"] for r in dossier["review_evidence_records"]}
    unresolved, misassigned, total = [], [], 0
    for cluster in dossier["semantic_clusters"]:
        for rid in cluster["representative_review_ids"]:
            total += 1
            if rid not in record_ids:
                unresolved.append(rid)
            elif cluster_of[rid] != cluster["semantic_cluster_id"]:
                misassigned.append(rid)
    return {
        "representative_count": total,
        "unresolved_representative_ids": unresolved[:20],
        "misassigned_representative_ids": misassigned[:20],
        "all_traceable_to_source_review_ids": not unresolved and not misassigned,
    }


def representative_selection_behaviour(dossier: dict, low_rating_max: float = 2.0) -> dict:
    ratings = {str(r["review_id"]): r.get("rating") for r in dossier["review_evidence_records"]}
    total_low = sum(1 for v in ratings.values() if v is not None and float(v) <= low_rating_max)
    represented_low = 0
    multi_member_clusters = 0
    low_lost_in_multi = 0
    for cluster in dossier["semantic_clusters"]:
        reps = set(cluster["representative_review_ids"])
        represented_low += sum(1 for rid in reps if ratings.get(rid) is not None and float(ratings[rid]) <= low_rating_max)
        if int(cluster["unique_review_count"]) > len(reps):
            multi_member_clusters += 1
            low_in_cluster = sum(int(v) for k, v in cluster["rating_distribution"].items() if float(k) <= low_rating_max)
            low_in_reps = sum(1 for rid in reps if ratings.get(rid) is not None and float(ratings[rid]) <= low_rating_max)
            low_lost_in_multi += max(0, low_in_cluster - low_in_reps)
    return {
        "low_rating_threshold": low_rating_max,
        "low_rated_reviews_in_full_dossier": total_low,
        "low_rated_reviews_selected_as_representatives": represented_low,
        "clusters_where_compaction_drops_members": multi_member_clusters,
        "low_rated_reviews_not_carried_into_compact": low_lost_in_multi,
        "note": "Full dossiers retain every review; compact dossiers carry representative text plus cluster-level distributions.",
    }


def compaction_report(full_path: Path, compact_path: Path) -> dict:
    full_bytes = Path(full_path).stat().st_size
    compact_bytes = Path(compact_path).stat().st_size
    compact = json.loads(Path(compact_path).read_text(encoding="utf-8"))
    embedded = sum(len(c.get("representative_reviews", [])) for c in compact["semantic_clusters"])
    text_chars = sum(len(r.get("review_text") or "") for c in compact["semantic_clusters"] for r in c.get("representative_reviews", []))
    return {
        "full_bytes": full_bytes,
        "compact_bytes": compact_bytes,
        "compact_share_of_full": round(compact_bytes / full_bytes, 6) if full_bytes else None,
        "embedded_representative_reviews": embedded,
        "embedded_review_text_characters": text_chars,
        "approx_tokens_of_review_text": text_chars // 4,
    }


def hotel_diagnostics(dossier: dict, full_path: Path, compact_path: Path, threshold: float) -> dict:
    return {
        "hotel_id": dossier["hotel_id"],
        "cluster_size_distribution": cluster_size_distribution(dossier),
        "large_clusters": large_cluster_report(dossier, threshold),
        "representative_traceability": representative_traceability(dossier),
        "representative_selection_behaviour": representative_selection_behaviour(dossier),
        "compaction": compaction_report(full_path, compact_path),
    }


def aggregate_diagnostics(per_hotel: list[dict], threshold: float) -> dict:
    if not per_hotel:
        return {"hotels": 0}
    clusters = sum(d["cluster_size_distribution"]["cluster_count"] for d in per_hotel)
    reviews = sum(d["cluster_size_distribution"]["review_count"] for d in per_hotel)
    singletons = sum(d["cluster_size_distribution"]["singleton_cluster_count"] for d in per_hotel)
    inspected = [c for d in per_hotel for c in d["large_clusters"]]
    violations = [c for c in inspected if not c["meets_complete_linkage_threshold"]]
    traceable = all(d["representative_traceability"]["all_traceable_to_source_review_ids"] for d in per_hotel)
    ratios = [d["compaction"]["compact_share_of_full"] for d in per_hotel if d["compaction"]["compact_share_of_full"]]
    low_total = sum(d["representative_selection_behaviour"]["low_rated_reviews_in_full_dossier"] for d in per_hotel)
    low_lost = sum(d["representative_selection_behaviour"]["low_rated_reviews_not_carried_into_compact"] for d in per_hotel)
    return {
        "hotels": len(per_hotel),
        "grouping_method": "complete_linkage_cosine",
        "configured_similarity_threshold": threshold,
        "total_clusters": clusters,
        "total_reviews": reviews,
        "singleton_clusters": singletons,
        "singleton_share_of_reviews": round(singletons / reviews, 6) if reviews else None,
        "mean_reviews_per_cluster": round(reviews / clusters, 6) if clusters else None,
        "largest_cluster_size": max((d["cluster_size_distribution"]["largest_cluster_size"] for d in per_hotel), default=0),
        "large_clusters_inspected": len(inspected),
        "large_cluster_threshold_violations": len(violations),
        "all_representatives_traceable": traceable,
        "mean_compact_share_of_full": round(sum(ratios) / len(ratios), 6) if ratios else None,
        "low_rated_reviews_total": low_total,
        "low_rated_reviews_not_carried_into_compact": low_lost,
        "interpretation_boundary": "Semantic grouping is topical organisation, not truth, recurrence, independence, deception, severity or hotel quality.",
    }
