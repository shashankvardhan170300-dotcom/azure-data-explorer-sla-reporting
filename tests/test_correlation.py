"""Root-cause correlation tests (exact window logic, no randomness)."""

import pandas as pd
import pytest

from analysis.correlation import correlate_incidents, correlation_summary

OPENED = pd.Timestamp("2026-01-10 12:00:00", tz="UTC")


def _incidents():
    return pd.DataFrame(
        {
            "incident_id": ["INC-1", "INC-2", "INC-3", "INC-4"],
            "cluster": ["c1", "c1", "c2", "c1"],
            "service": ["compute"] * 4,
            "severity": ["Sev2"] * 4,
            "title": ["t"] * 4,
            "status": ["Resolved"] * 4,
            "opened_at": [OPENED] * 4,
            "acknowledged_at": [OPENED] * 4,
            "mitigated_at": [OPENED] * 4,
            "resolved_at": [OPENED] * 4,
            "tta_minutes": [10.0] * 4,
            "ttm_minutes": [100.0] * 4,
        }
    )


def _events():
    return pd.DataFrame(
        {
            "event_id": ["EVT-1", "EVT-2", "EVT-3", "EVT-4", "EVT-5"],
            "cluster": ["c1", "c1", "c1", "c2", "c1"],
            "service": ["compute"] * 5,
            "event_type": ["deployment", "config", "task", "deployment", "deployment"],
            # EVT-1: 30 min before INC-1 (c1) -> candidate
            # EVT-2: 10 min before INC-1 (c1) -> nearest candidate for INC-1
            # EVT-3: 61 min before -> outside the 60-min window
            # EVT-4: 20 min before INC-3 (c2) -> candidate for INC-3
            # EVT-5: 5 min AFTER opened -> never a candidate
            "event_time": [
                OPENED - pd.Timedelta(minutes=30),
                OPENED - pd.Timedelta(minutes=10),
                OPENED - pd.Timedelta(minutes=61),
                OPENED - pd.Timedelta(minutes=20),
                OPENED + pd.Timedelta(minutes=5),
            ],
            "description": ["d"] * 5,
        }
    )


def test_nearest_prior_event_wins():
    out = correlate_incidents(_incidents(), _events(), lookback_minutes=60)
    row = out[out["incident_id"] == "INC-1"].iloc[0]
    assert row["has_candidate"] == True
    assert row["candidate_event_id"] == "EVT-2"  # 10 min before beats 30 min before
    assert row["candidate_event_type"] == "config"
    assert row["minutes_before_incident"] == pytest.approx(10.0)


def test_event_outside_window_ignored():
    out = correlate_incidents(_incidents(), _events(), lookback_minutes=60)
    # INC-2 is on c1 too, same opened_at as INC-1, so it shares the candidates.
    row = out[out["incident_id"] == "INC-2"].iloc[0]
    assert row["candidate_event_id"] == "EVT-2"
    # EVT-3 (61 min before) must never be chosen.
    assert out["candidate_event_id"].tolist().count("EVT-3") == 0


def test_event_after_incident_never_candidate():
    out = correlate_incidents(_incidents(), _events(), lookback_minutes=60)
    assert "EVT-5" not in out["candidate_event_id"].tolist()


def test_different_cluster_not_matched():
    out = correlate_incidents(_incidents(), _events(), lookback_minutes=60)
    row = out[out["incident_id"] == "INC-3"].iloc[0]
    assert row["candidate_event_id"] == "EVT-4"  # c2 event, not the c1 ones
    assert row["candidate_event_type"] == "deployment"


def test_no_candidate_when_nothing_in_window():
    incidents = _incidents().iloc[[3]].copy()  # INC-4 on c1
    events = _events().iloc[[2, 4]].copy()  # only the 61-min-before and after events
    out = correlate_incidents(incidents, events, lookback_minutes=60)
    row = out.iloc[0]
    assert row["has_candidate"] == False
    assert row["candidate_event_id"] is None  # noqa
    assert row["minutes_before_incident"] is None


def test_correlation_summary():
    out = correlate_incidents(_incidents(), _events(), lookback_minutes=60)
    summary = correlation_summary(out)
    by_type = dict(zip(summary["candidate_event_type"], summary["incidents"]))
    # INC-1, INC-2 -> config (EVT-2); INC-3 -> deployment (EVT-4); INC-4 -> config
    assert by_type == {"config": 3, "deployment": 1}
    # Shares are over all 4 incidents.
    config_row = summary[summary["candidate_event_type"] == "config"].iloc[0]
    assert config_row["share_pct"] == pytest.approx(75.0)


def test_empty_events():
    out = correlate_incidents(_incidents(), pd.DataFrame(columns=["event_id", "cluster", "event_type", "event_time"]))
    assert out["has_candidate"].sum() == 0
