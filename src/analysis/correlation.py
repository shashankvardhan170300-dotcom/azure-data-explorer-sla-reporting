"""Root-cause correlation: join incidents to nearby change events.

The analysis Shashank ran at Microsoft correlated alerts with deployment,
configuration, and task-execution events on the same cluster. This module
reproduces that pattern: for each incident, find change events on the same
cluster that occurred within a lookback window *before* the incident opened,
and rank them by proximity (closest event first) as the most likely
root-cause candidates.
"""

from __future__ import annotations

import pandas as pd

DEFAULT_LOOKBACK_MINUTES = 60


def correlate_incidents(
    incidents: pd.DataFrame,
    events: pd.DataFrame,
    lookback_minutes: int = DEFAULT_LOOKBACK_MINUTES,
) -> pd.DataFrame:
    """Attach the nearest prior change event to each incident.

    Returns a copy of ``incidents`` with columns:
      - ``candidate_event_id`` / ``candidate_event_type`` / ``candidate_event_time``:
        the closest same-cluster event in the lookback window, or None
      - ``minutes_before_incident``: how long before the incident the event happened
      - ``has_candidate``: True when a candidate event was found

    Only events on the SAME cluster and in the window
    ``[opened_at - lookback, opened_at)`` are considered. An event at or
    after the incident opened is never a candidate.
    """
    df = incidents.copy()
    df["candidate_event_id"] = None
    df["candidate_event_type"] = None
    df["candidate_event_time"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    df["minutes_before_incident"] = None
    df["has_candidate"] = False

    if events.empty or df.empty:
        return df

    events = events.copy()
    events["event_time"] = pd.to_datetime(events["event_time"], utc=True)
    df["opened_at"] = pd.to_datetime(df["opened_at"], utc=True)

    for idx, row in df.iterrows():
        window_start = row["opened_at"] - pd.Timedelta(minutes=lookback_minutes)
        candidates = events[
            (events["cluster"] == row["cluster"])
            & (events["event_time"] >= window_start)
            & (events["event_time"] < row["opened_at"])
        ]
        if candidates.empty:
            continue
        nearest = candidates.sort_values("event_time", ascending=False).iloc[0]
        gap = (row["opened_at"] - nearest["event_time"]).total_seconds() / 60.0
        df.at[idx, "candidate_event_id"] = nearest["event_id"]
        df.at[idx, "candidate_event_type"] = nearest["event_type"]
        df.at[idx, "candidate_event_time"] = nearest["event_time"]
        df.at[idx, "minutes_before_incident"] = round(float(gap), 1)
        df.at[idx, "has_candidate"] = True

    return df


def correlation_summary(correlated: pd.DataFrame) -> pd.DataFrame:
    """Share of incidents with a candidate change event, by event type."""
    total = len(correlated)
    if total == 0:
        return pd.DataFrame(columns=["candidate_event_type", "incidents", "share_pct"])
    with_candidate = correlated[correlated["has_candidate"]]
    summary = (
        with_candidate.groupby("candidate_event_type")
        .size()
        .rename("incidents")
        .reset_index()
        .sort_values("incidents", ascending=False)
    )
    summary["share_pct"] = (summary["incidents"] / total * 100).round(1)
    return summary.reset_index(drop=True)
