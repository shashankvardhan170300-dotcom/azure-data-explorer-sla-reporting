"""SLA compliance math tests.

Uses small hand-built incident frames (no randomness) so the expected
values are exact.
"""

import pandas as pd
import pytest

from analysis.sla import add_sla_flags, compliance_by_cluster, compliance_by_severity, tta_ttm_stats

TARGETS = {
    "Sev1": {"tta": 15, "ttm": 240},
    "Sev2": {"tta": 30, "ttm": 480},
    "Sev3": {"tta": 120, "ttm": 1440},
    "Sev4": {"tta": 480, "ttm": 4320},
}


def _incidents(rows):
    base = {
        "incident_id": [f"INC-{i:03d}" for i in range(len(rows))],
        "cluster": ["c1"] * len(rows),
        "service": ["compute"] * len(rows),
        "status": ["Resolved"] * len(rows),
        "opened_at": pd.to_datetime(["2026-01-01"] * len(rows), utc=True),
        "acknowledged_at": pd.to_datetime(["2026-01-01"] * len(rows), utc=True),
        "mitigated_at": pd.to_datetime(["2026-01-01"] * len(rows), utc=True),
        "resolved_at": pd.to_datetime(["2026-01-01"] * len(rows), utc=True),
    }
    for key in ("severity", "tta_minutes", "ttm_minutes"):
        base[key] = [r[key] for r in rows]
    return pd.DataFrame(base)


def test_compliant_when_both_within_target():
    df = _incidents([{"severity": "Sev1", "tta_minutes": 10.0, "ttm_minutes": 200.0}])
    out = add_sla_flags(df, TARGETS)
    assert out.loc[0, "sla_compliant"] == True
    assert out.loc[0, "tta_within_sla"] == True
    assert out.loc[0, "ttm_within_sla"] == True


def test_breach_on_tta_only():
    df = _incidents([{"severity": "Sev1", "tta_minutes": 16.0, "ttm_minutes": 200.0}])
    out = add_sla_flags(df, TARGETS)
    assert out.loc[0, "sla_compliant"] == False
    assert out.loc[0, "tta_within_sla"] == False
    assert out.loc[0, "ttm_within_sla"] == True


def test_breach_on_ttm_only():
    df = _incidents([{"severity": "Sev2", "tta_minutes": 20.0, "ttm_minutes": 500.0}])
    out = add_sla_flags(df, TARGETS)
    assert out.loc[0, "sla_compliant"] == False
    assert out.loc[0, "ttm_within_sla"] == False


def test_boundary_is_compliant():
    # Exactly at the target counts as within SLA (<=).
    df = _incidents([{"severity": "Sev1", "tta_minutes": 15.0, "ttm_minutes": 240.0}])
    out = add_sla_flags(df, TARGETS)
    assert out.loc[0, "sla_compliant"] == True


def test_open_incident_has_no_compliance_flag():
    df = _incidents([{"severity": "Sev1", "tta_minutes": 10.0, "ttm_minutes": None}])
    df.loc[0, "status"] = "Active"
    df.loc[0, "mitigated_at"] = None
    df.loc[0, "resolved_at"] = None
    out = add_sla_flags(df, TARGETS)
    assert out.loc[0, "sla_compliant"] is None
    assert out.loc[0, "ttm_within_sla"] is None
    assert out.loc[0, "tta_within_sla"] == True


def test_compliance_by_cluster_excludes_open_incidents():
    df = _incidents(
        [
            {"severity": "Sev1", "tta_minutes": 10.0, "ttm_minutes": 100.0},
            {"severity": "Sev1", "tta_minutes": 10.0, "ttm_minutes": 100.0},
            {"severity": "Sev1", "tta_minutes": 10.0, "ttm_minutes": None},
        ]
    )
    df.loc[2, "status"] = "Active"
    out = compliance_by_cluster(df)
    assert len(out) == 1
    assert out.loc[0, "incidents"] == 2
    assert out.loc[0, "compliant"] == 2
    assert out.loc[0, "compliance_pct"] == 100.0


def test_compliance_by_severity_mixed():
    df = _incidents(
        [
            {"severity": "Sev1", "tta_minutes": 10.0, "ttm_minutes": 100.0},
            {"severity": "Sev1", "tta_minutes": 99.0, "ttm_minutes": 100.0},
            {"severity": "Sev3", "tta_minutes": 10.0, "ttm_minutes": 100.0},
        ]
    )
    out = compliance_by_severity(df)
    sev1 = out[out["severity"] == "Sev1"].iloc[0]
    sev3 = out[out["severity"] == "Sev3"].iloc[0]
    assert sev1["incidents"] == 2 and sev1["compliant"] == 1 and sev1["compliance_pct"] == 50.0
    assert sev3["incidents"] == 1 and sev3["compliance_pct"] == 100.0
    # Ordered Sev1 before Sev3.
    assert list(out["severity"]) == ["Sev1", "Sev3"]


def test_tta_ttm_stats():
    df = _incidents(
        [
            {"severity": "Sev2", "tta_minutes": 10.0, "ttm_minutes": 100.0},
            {"severity": "Sev2", "tta_minutes": 30.0, "ttm_minutes": 300.0},
        ]
    )
    out = tta_ttm_stats(df)
    assert out.loc[0, "tta_mean"] == 20.0
    assert out.loc[0, "tta_median"] == 20.0
    assert out.loc[0, "ttm_mean"] == 200.0
    assert out.loc[0, "ttm_p90"] == pytest.approx(280.0)


def test_empty_frame_returns_empty_stats():
    df = _incidents([]).iloc[0:0]
    assert compliance_by_cluster(df).empty
    assert compliance_by_severity(df).empty
    assert tta_ttm_stats(df).empty
