"""Incident ageing analysis.

Ageing measures how long currently-open incidents have been open, bucketed
into the bands used on the SLA dashboard: 0-24h, 24-72h, 72h-7d, 7d+.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

AGEING_BUCKETS = ["0-24h", "24-72h", "72h-7d", "7d+"]
_BUCKET_EDGES_HOURS = [0, 24, 72, 168, float("inf")]


def age_bucket(age_hours: float) -> str:
    """Map an age in hours to its ageing bucket.

    Boundaries are inclusive on the lower edge: exactly 24h -> "24-72h",
    exactly 72h -> "72h-7d", exactly 168h (7d) -> "7d+".
    """
    if age_hours < 0:
        raise ValueError("age_hours must not be negative")
    for label, low, high in zip(
        AGEING_BUCKETS, _BUCKET_EDGES_HOURS[:-1], _BUCKET_EDGES_HOURS[1:]
    ):
        if low <= age_hours < high:
            return label
    return AGEING_BUCKETS[-1]


def ageing_summary(
    incidents: pd.DataFrame,
    as_of: datetime | None = None,
) -> pd.DataFrame:
    """Ageing distribution of currently-open incidents.

    Returns one row per bucket with the open-incident count, ordered
    youngest to oldest. ``as_of`` defaults to now (UTC).
    """
    as_of = as_of or datetime.now(timezone.utc)
    open_inc = incidents[incidents["status"] != "Resolved"].copy()
    counts = {bucket: 0 for bucket in AGEING_BUCKETS}
    if not open_inc.empty:
        ages = (pd.to_datetime(as_of, utc=True) - pd.to_datetime(open_inc["opened_at"], utc=True)).dt.total_seconds() / 3600.0
        for age in ages:
            counts[age_bucket(float(age))] += 1
    return pd.DataFrame(
        {"age_bucket": AGEING_BUCKETS, "open_incidents": [counts[b] for b in AGEING_BUCKETS]}
    )


def open_incidents_with_age(
    incidents: pd.DataFrame,
    as_of: datetime | None = None,
) -> pd.DataFrame:
    """Open incidents with their current age (hours) and bucket attached."""
    as_of = as_of or datetime.now(timezone.utc)
    open_inc = incidents[incidents["status"] != "Resolved"].copy()
    if open_inc.empty:
        open_inc["age_hours"] = pd.Series(dtype=float)
        open_inc["age_bucket"] = pd.Series(dtype=str)
        return open_inc
    open_inc["age_hours"] = (
        (pd.to_datetime(as_of, utc=True) - pd.to_datetime(open_inc["opened_at"], utc=True)).dt.total_seconds()
        / 3600.0
    ).round(1)
    open_inc["age_bucket"] = open_inc["age_hours"].map(age_bucket)
    return open_inc.sort_values("age_hours", ascending=False).reset_index(drop=True)
