from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

import pandas as pd


def _rating_distribution(series: pd.Series) -> dict[str, int]:
    return {str(key): int(value) for key, value in series.value_counts(dropna=False).sort_index().items()}


def _period_summary(frame: pd.DataFrame, period: str) -> list[dict]:
    dates = pd.to_datetime(frame["review_date"], errors="coerce")
    key = dates.dt.to_period("Y").astype(str) if period == "year" else dates.dt.to_period("Q").astype(str)
    result = []
    for value, group in frame.assign(_period=key).groupby("_period", sort=True):
        polarity = {"positive": 0, "negative": 0, "neutral": 0}
        for sentiment in group["absa_sentiment"].fillna("").astype(str):
            for token in sentiment.split(";"):
                if ":" not in token:
                    continue
                try:
                    score = float(token.rsplit(":", 1)[1])
                except ValueError:
                    continue
                polarity["positive" if score > 0 else "negative" if score < 0 else "neutral"] += 1
        result.append({"period": str(value), "review_count": len(group), "mean_rating": float(group["rating"].mean()), "rating_distribution": _rating_distribution(group["rating"]), "absa_polarity_counts": polarity})
    return result


def build_temporal_summaries(frame: pd.DataFrame, windows: dict[str, int]) -> dict:
    dates = pd.to_datetime(frame["review_date"], errors="coerce")
    latest = dates.max()
    summaries = {"by_year": _period_summary(frame, "year"), "by_quarter": _period_summary(frame, "quarter")}
    if pd.notna(latest):
        summaries["configured_windows"] = {
            name: {"days": days, "review_count": int((dates >= latest - timedelta(days=days)).sum()), "historical_review_count": int((dates < latest - timedelta(days=days)).sum()), "anchor_date": latest.date().isoformat()}
            for name, days in windows.items()
        }
    else:
        summaries["configured_windows"] = {}
    summaries["coverage"] = {
        "minimum_date": dates.min().date().isoformat() if dates.notna().any() else None,
        "maximum_date": latest.date().isoformat() if pd.notna(latest) else None,
        "active_year_count": int(dates.dt.year.nunique()),
        "active_quarter_count": int(dates.dt.to_period("Q").nunique()),
        "review_count": len(frame),
        "date_gap_days": [int(days) for days in dates.sort_values().diff().dt.days.dropna().tolist() if days > 0],
    }
    aspect_counts = defaultdict(lambda: {"count": 0, "first_date": None, "latest_date": None, "active_years": set()})
    for _, row in frame.iterrows():
        aspects = str(row.get("absa_aspect", "") or "").split(";")
        aspects = [aspect for aspect in aspects if aspect]
        date = pd.to_datetime(row["review_date"], errors="coerce")
        for aspect in aspects:
            value = aspect_counts[aspect]
            value["count"] += 1
            if pd.notna(date):
                value["first_date"] = min(value["first_date"], date.date().isoformat()) if value["first_date"] else date.date().isoformat()
                value["latest_date"] = max(value["latest_date"], date.date().isoformat()) if value["latest_date"] else date.date().isoformat()
                value["active_years"].add(int(date.year))
    summaries["aspects"] = {key: {**value, "active_years": sorted(value["active_years"]), "active_period_count": len(value["active_years"])} for key, value in sorted(aspect_counts.items())}
    aspect_by_year = {}
    for year in sorted(dates.dt.year.dropna().unique()):
        counts = {aspect: 0 for aspect in summaries["aspects"]}
        for _, row in frame.iterrows():
            row_date = pd.to_datetime(row["review_date"], errors="coerce")
            if pd.notna(row_date) and int(row_date.year) == int(year):
                for aspect in str(row.get("absa_aspect", "") or "").split(";"):
                    if aspect in counts:
                        counts[aspect] += 1
        aspect_by_year[str(int(year))] = counts
    summaries["aspect_counts_by_year"] = aspect_by_year
    return summaries
