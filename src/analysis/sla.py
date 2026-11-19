"""SLA compliance computation.

An incident is SLA-compliant when BOTH its time-to-acknowledge (TTA) and
its time-to-mitigate (TTM) fall within the target for its severity.
Open incidents (no mitigation time yet) are excluded from compliance
percentages and reported separately by the ageing module.
"""

from __future__ import annotations

import pandas as pd

from telemetry.synth import SLA_TARGETS_MINUTES


def add_sla_flags(
    incidents: pd.DataFrame,
    targets: dict | None = None,
) -> pd.DataFrame:
    """Return a copy of ``incidents`` with SLA flag columns added.

    Added columns:
      - ``tta_target_minutes`` / ``ttm_target_minutes``: targets for the row's severity
      - ``tta_within_sla``: True when tta_minutes <= target (False when missing)
      - ``ttm_within_sla``: True when ttm_minutes <= target (None when not yet mitigated)
      - ``sla_compliant``: True only when both TTA and TTM are within target;
        None when the incident is still open (TTM unknown)
    """
    targets = targets or SLA_TARGETS_MINUTES
    df = incidents.copy()
    df["tta_target_minutes"] = df["severity"].map(lambda s: targets[s]["tta"])
    df["ttm_target_minutes"] = df["severity"].map(lambda s: targets[s]["ttm"])
    df["tta_within_sla"] = df["tta_minutes"] <= df["tta_target_minutes"]
    df["ttm_within_sla"] = df.apply(
        lambda r: (r["ttm_minutes"] <= r["ttm_target_minutes"]) if pd.notna(r["ttm_minutes"]) else None,
        axis=1,
    )
    df["sla_compliant"] = df.apply(
        lambda r: (bool(r["tta_within_sla"]) and bool(r["ttm_within_sla"]))
        if r["ttm_within_sla"] is not None
        else None,
        axis=1,
    )
    return df


def compliance_by_cluster(incidents: pd.DataFrame) -> pd.DataFrame:
    """SLA compliance % per cluster, over closed (mitigated) incidents only."""
    df = add_sla_flags(incidents)
    closed = df[df["sla_compliant"].notna()]
    if closed.empty:
        return pd.DataFrame(columns=["cluster", "incidents", "compliant", "compliance_pct"])
    grouped = (
        closed.groupby("cluster")["sla_compliant"]
        .agg(["count", "sum"])
        .rename(columns={"count": "incidents", "sum": "compliant"})
        .reset_index()
    )
    grouped["compliance_pct"] = (grouped["compliant"] / grouped["incidents"] * 100).round(1)
    return grouped.sort_values("compliance_pct", ascending=False).reset_index(drop=True)


def compliance_by_severity(incidents: pd.DataFrame) -> pd.DataFrame:
    """SLA compliance % per severity, over closed (mitigated) incidents only."""
    df = add_sla_flags(incidents)
    closed = df[df["sla_compliant"].notna()]
    if closed.empty:
        return pd.DataFrame(columns=["severity", "incidents", "compliant", "compliance_pct"])
    grouped = (
        closed.groupby("severity")["sla_compliant"]
        .agg(["count", "sum"])
        .rename(columns={"count": "incidents", "sum": "compliant"})
        .reset_index()
    )
    grouped["compliance_pct"] = (grouped["compliant"] / grouped["incidents"] * 100).round(1)
    severity_order = {"Sev1": 0, "Sev2": 1, "Sev3": 2, "Sev4": 3}
    grouped["__order"] = grouped["severity"].map(severity_order)
    return grouped.sort_values("__order").drop(columns="__order").reset_index(drop=True)


def tta_ttm_stats(incidents: pd.DataFrame) -> pd.DataFrame:
    """Mean / median / p90 of TTA and TTM per cluster (closed incidents)."""
    df = incidents.copy()
    closed = df[df["ttm_minutes"].notna()]
    if closed.empty:
        return pd.DataFrame(
            columns=["cluster", "tta_mean", "tta_median", "tta_p90", "ttm_mean", "ttm_median", "ttm_p90"]
        )
    stats = (
        closed.groupby("cluster")
        .agg(
            tta_mean=("tta_minutes", "mean"),
            tta_median=("tta_minutes", "median"),
            tta_p90=("tta_minutes", lambda s: s.quantile(0.9)),
            ttm_mean=("ttm_minutes", "mean"),
            ttm_median=("ttm_minutes", "median"),
            ttm_p90=("ttm_minutes", lambda s: s.quantile(0.9)),
        )
        .round(1)
        .reset_index()
    )
    return stats


def daily_tta_ttm(incidents: pd.DataFrame) -> pd.DataFrame:
    """Daily mean TTA/TTM trend (closed incidents), for the trend chart."""
    df = incidents.copy()
    closed = df[df["ttm_minutes"].notna()].copy()
    if closed.empty:
        return pd.DataFrame(columns=["date", "tta_mean", "ttm_mean", "incidents"])
    closed["date"] = pd.to_datetime(closed["opened_at"]).dt.date
    daily = (
        closed.groupby("date")
        .agg(tta_mean=("tta_minutes", "mean"), ttm_mean=("ttm_minutes", "mean"), incidents=("incident_id", "count"))
        .round(1)
        .reset_index()
        .sort_values("date")
    )
    return daily
