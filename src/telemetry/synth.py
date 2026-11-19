"""Synthetic cluster telemetry generator.

All data produced here is SYNTHETIC sample data for demonstration purposes.
It is not real Microsoft telemetry, not real production data, and not
proprietary code. It exists so the analysis and reporting code in this
portfolio project can be run end-to-end without access to a real
Azure Data Explorer cluster.

The generator models the *shape* of the telemetry Shashank worked with as a
Data Engineer at Microsoft (Aug 2020 - Jan 2023): cluster incidents with
time-to-acknowledge (TTA) and time-to-mitigate (TTM), plus deployment,
configuration, and task-execution events on the same clusters, so
root-cause correlation (alert -> change event) can be demonstrated.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import pandas as pd

CLUSTERS = ["cluster-eastus-01", "cluster-eastus-02", "cluster-westus-01", "cluster-central-01"]
SERVICES = ["compute", "storage", "networking", "control-plane", "monitoring"]

SEVERITIES = ["Sev1", "Sev2", "Sev3", "Sev4"]

# SLA targets (acknowledge / mitigate) per severity, in minutes.
# These are illustrative targets for the demo, not any real customer's SLA.
SLA_TARGETS_MINUTES = {
    "Sev1": {"tta": 15, "ttm": 240},
    "Sev2": {"tta": 30, "ttm": 480},
    "Sev3": {"tta": 120, "ttm": 1440},
    "Sev4": {"tta": 480, "ttm": 4320},
}

# Typical TTA/TTM (minutes) used to sample realistic synthetic incidents.
_TYPICAL_TTA = {"Sev1": 12, "Sev2": 25, "Sev3": 90, "Sev4": 300}
_TYPICAL_TTM = {"Sev1": 180, "Sev2": 360, "Sev3": 900, "Sev4": 2400}

_TITLES = {
    "Sev1": [
        "Cluster node pool unreachable",
        "Control plane API latency above threshold",
        "Storage write failures on cluster",
    ],
    "Sev2": [
        "Elevated task failure rate",
        "Deployment rollout stalled",
        "Node disk pressure warnings",
    ],
    "Sev3": [
        "Intermittent monitoring gaps",
        "Config drift detected on nodes",
        "Slow query performance in telemetry pipeline",
    ],
    "Sev4": [
        "Dashboard refresh delay",
        "Log ingestion lag below threshold",
        "Minor certificate expiry warning",
    ],
}

_EVENT_DESCRIPTIONS = {
    "deployment": ["Rolling deployment of service build", "Canary deployment started", "Hotfix deployment"],
    "config": ["Configuration change pushed", "Feature flag toggled", "Scaling policy updated"],
    "task": ["Scheduled maintenance task", "Cluster health check task", "Backup task completed"],
}


def generate_incidents(
    n: int = 120,
    days: int = 30,
    end: datetime | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate ``n`` synthetic incidents over the last ``days`` days.

    Returns a DataFrame with columns: incident_id, cluster, service,
    severity, title, status, opened_at, acknowledged_at, mitigated_at,
    resolved_at, tta_minutes, ttm_minutes.

    A fraction of incidents are left open (no mitigated/resolved time) so
    incident-ageing analysis has something to work with.
    """
    rng = random.Random(seed)
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    rows = []
    for i in range(n):
        severity = rng.choices(SEVERITIES, weights=[0.08, 0.22, 0.40, 0.30])[0]
        opened = start + timedelta(seconds=rng.random() * (end - start).total_seconds())
        tta = max(1.0, rng.gauss(_TYPICAL_TTA[severity], _TYPICAL_TTA[severity] * 0.5))
        ttm = max(tta + 5.0, rng.gauss(_TYPICAL_TTM[severity], _TYPICAL_TTM[severity] * 0.4))
        acknowledged = opened + timedelta(minutes=tta)
        mitigated = opened + timedelta(minutes=ttm)
        # ~12% of incidents are still open at generation time.
        is_open = rng.random() < 0.12
        if is_open:
            status = rng.choice(["Active", "Investigating"])
            resolved = None
            mitigated_at = None
            ttm_value = None
        else:
            status = "Resolved"
            resolved = mitigated + timedelta(minutes=max(5.0, rng.gauss(60, 30)))
            mitigated_at = mitigated
            ttm_value = round(ttm, 1)

        rows.append(
            {
                "incident_id": f"INC-{i + 1:04d}",
                "cluster": rng.choice(CLUSTERS),
                "service": rng.choice(SERVICES),
                "severity": severity,
                "title": rng.choice(_TITLES[severity]),
                "status": status,
                "opened_at": opened,
                "acknowledged_at": acknowledged,
                "mitigated_at": mitigated_at,
                "resolved_at": resolved,
                "tta_minutes": round(tta, 1),
                "ttm_minutes": ttm_value,
            }
        )

    df = pd.DataFrame(rows).sort_values("opened_at").reset_index(drop=True)
    for col in ("opened_at", "acknowledged_at", "mitigated_at", "resolved_at"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


def generate_events(
    n: int = 200,
    days: int = 30,
    end: datetime | None = None,
    seed: int = 7,
) -> pd.DataFrame:
    """Generate ``n`` synthetic cluster change events.

    Columns: event_id, cluster, service, event_type (deployment / config /
    task), event_time, description.
    """
    rng = random.Random(seed)
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    rows = []
    for i in range(n):
        event_type = rng.choices(
            ["deployment", "config", "task"], weights=[0.35, 0.35, 0.30]
        )[0]
        event_time = start + timedelta(seconds=rng.random() * (end - start).total_seconds())
        rows.append(
            {
                "event_id": f"EVT-{i + 1:04d}",
                "cluster": rng.choice(CLUSTERS),
                "service": rng.choice(SERVICES),
                "event_type": event_type,
                "event_time": event_time,
                "description": rng.choice(_EVENT_DESCRIPTIONS[event_type]),
            }
        )

    df = pd.DataFrame(rows).sort_values("event_time").reset_index(drop=True)
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True)
    return df


def generate_telemetry(
    n_incidents: int = 120,
    n_events: int = 200,
    days: int = 30,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate a matching pair of synthetic incidents + change events."""
    end = datetime.now(timezone.utc)
    incidents = generate_incidents(n_incidents, days, end=end, seed=seed)
    events = generate_events(n_events, days, end=end, seed=seed + 1)
    return incidents, events
