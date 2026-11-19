"""Incident ageing bucket tests (exact boundaries, no randomness)."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from analysis.ageing import age_bucket, ageing_summary, open_incidents_with_age

NOW = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)


def test_bucket_boundaries():
    assert age_bucket(0.0) == "0-24h"
    assert age_bucket(23.9) == "0-24h"
    assert age_bucket(24.0) == "24-72h"
    assert age_bucket(71.9) == "24-72h"
    assert age_bucket(72.0) == "72h-7d"
    assert age_bucket(167.9) == "72h-7d"
    assert age_bucket(168.0) == "7d+"
    assert age_bucket(500.0) == "7d+"


def test_negative_age_rejected():
    with pytest.raises(ValueError):
        age_bucket(-1.0)


def _incidents():
    # Opened at known offsets from NOW.
    opened = [
        NOW - pd.Timedelta(hours=5),     # 0-24h
        NOW - pd.Timedelta(hours=30),    # 24-72h
        NOW - pd.Timedelta(hours=100),   # 72h-7d
        NOW - pd.Timedelta(hours=200),   # 7d+
        NOW - pd.Timedelta(hours=2),     # 0-24h, but Resolved -> excluded
    ]
    return pd.DataFrame(
        {
            "incident_id": ["INC-1", "INC-2", "INC-3", "INC-4", "INC-5"],
            "cluster": ["c1"] * 5,
            "service": ["compute"] * 5,
            "severity": ["Sev2"] * 5,
            "title": ["t"] * 5,
            "status": ["Active", "Investigating", "Active", "Active", "Resolved"],
            "opened_at": pd.to_datetime(opened, utc=True),
            "acknowledged_at": pd.to_datetime(opened, utc=True),
            "mitigated_at": [None, None, None, None, NOW],
            "resolved_at": [None, None, None, None, NOW],
            "tta_minutes": [10.0] * 5,
            "ttm_minutes": [None, None, None, None, 100.0],
        }
    )


def test_ageing_summary_counts():
    out = ageing_summary(_incidents(), as_of=NOW)
    counts = dict(zip(out["age_bucket"], out["open_incidents"]))
    assert counts == {"0-24h": 1, "24-72h": 1, "72h-7d": 1, "7d+": 1}
    # Buckets always present, in order.
    assert list(out["age_bucket"]) == ["0-24h", "24-72h", "72h-7d", "7d+"]


def test_ageing_summary_no_open_incidents():
    df = _incidents()
    df["status"] = "Resolved"
    out = ageing_summary(df, as_of=NOW)
    assert out["open_incidents"].sum() == 0
    assert list(out["age_bucket"]) == ["0-24h", "24-72h", "72h-7d", "7d+"]


def test_open_incidents_with_age_sorted_oldest_first():
    out = open_incidents_with_age(_incidents(), as_of=NOW)
    assert len(out) == 4
    assert out.iloc[0]["incident_id"] == "INC-4"  # 200h old
    assert out.iloc[0]["age_hours"] == pytest.approx(200.0)
    assert out.iloc[0]["age_bucket"] == "7d+"
    assert out.iloc[-1]["incident_id"] == "INC-1"  # 5h old
