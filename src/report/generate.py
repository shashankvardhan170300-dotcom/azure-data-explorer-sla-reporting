"""SLA report generator: Markdown + HTML reports with matplotlib charts.

All figures are computed from SYNTHETIC sample telemetry (see
``src/telemetry/synth.py``). The reports are labelled as such.
"""

from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from analysis import (
    ageing_summary,
    compliance_by_cluster,
    compliance_by_severity,
    correlation_summary,
    daily_tta_ttm,
    tta_ttm_stats,
)
from analysis.correlation import correlate_incidents
from analysis.sla import add_sla_flags

plt.rcParams.update({"figure.figsize": (9, 4.5), "axes.titlesize": 12, "axes.labelsize": 10})


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=130)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _chart_compliance(by_cluster: pd.DataFrame) -> str:
    fig, ax = plt.subplots()
    ax.barh(by_cluster["cluster"], by_cluster["compliance_pct"], color="#2e7d32")
    ax.set_xlim(0, 100)
    ax.set_xlabel("SLA compliance (%)")
    ax.set_title("SLA compliance by cluster")
    for i, v in enumerate(by_cluster["compliance_pct"]):
        ax.text(min(v + 1, 96), i, f"{v:.1f}%", va="center")
    ax.invert_yaxis()
    return _fig_to_base64(fig)


def _chart_ageing(ageing: pd.DataFrame) -> str:
    fig, ax = plt.subplots()
    colors = ["#66bb6a", "#ffa726", "#fb8c00", "#e53935"]
    ax.bar(ageing["age_bucket"], ageing["open_incidents"], color=colors)
    ax.set_ylabel("Open incidents")
    ax.set_title("Open incidents by age bucket")
    for i, v in enumerate(ageing["open_incidents"]):
        ax.text(i, v + 0.3, str(int(v)), ha="center")
    return _fig_to_base64(fig)


def _chart_trend(daily: pd.DataFrame) -> str:
    fig, ax = plt.subplots()
    ax.plot(daily["date"], daily["tta_mean"], marker="o", label="Mean TTA (min)")
    ax.plot(daily["date"], daily["ttm_mean"], marker="s", label="Mean TTM (min)")
    ax.set_ylabel("Minutes")
    ax.set_title("Daily mean TTA / TTM trend")
    ax.legend()
    fig.autofmt_xdate(rotation=30)
    return _fig_to_base64(fig)


def build_reports(
    incidents: pd.DataFrame,
    events: pd.DataFrame,
    out_dir: str | Path,
    lookback_minutes: int = 60,
) -> dict:
    """Compute all analyses, write Markdown + HTML reports, return paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    flagged = add_sla_flags(incidents)
    closed = flagged[flagged["sla_compliant"].notna()]
    overall = (
        round(100.0 * int(closed["sla_compliant"].sum()) / len(closed), 1) if len(closed) else 0.0
    )
    by_cluster = compliance_by_cluster(incidents)
    by_severity = compliance_by_severity(incidents)
    stats = tta_ttm_stats(incidents)
    ageing = ageing_summary(incidents)
    daily = daily_tta_ttm(incidents)
    correlated = correlate_incidents(incidents, events, lookback_minutes=lookback_minutes)
    corr_summary = correlation_summary(correlated)
    n_with_candidate = int(correlated["has_candidate"].sum())

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def md_table(df: pd.DataFrame) -> str:
        if df.empty:
            return "_No data._\n"
        header = "| " + " | ".join(df.columns) + " |\n"
        sep = "| " + " | ".join("---" for _ in df.columns) + " |\n"
        body = "".join("| " + " | ".join(str(v) for v in row) + " |\n" for row in df.values)
        return header + sep + body

    md = []
    md.append("# Cluster SLA Report (Synthetic Demo Data)\n")
    md.append(
        "> **Synthetic sample data.** This report is generated from SYNTHETIC telemetry "
        "created for demonstration. It is not real production data.\n"
    )
    md.append(f"_Generated: {generated_at} | Incidents: {len(incidents)} | "
              f"Closed: {len(closed)} | Open: {len(incidents) - len(closed)} | "
              f"Change events: {len(events)}_\n")
    md.append(f"## Overall SLA compliance: **{overall}%** (closed incidents)\n")
    md.append("## SLA compliance by cluster\n")
    md.append(md_table(by_cluster))
    md.append("## SLA compliance by severity\n")
    md.append(md_table(by_severity))
    md.append("## TTA / TTM statistics by cluster (minutes)\n")
    md.append(md_table(stats))
    md.append("## Open incidents by age bucket\n")
    md.append(md_table(ageing))
    md.append("## Root-cause correlation (change events within "
              f"{lookback_minutes} min before the incident, same cluster)\n")
    md.append(f"{n_with_candidate} of {len(incidents)} incidents "
              f"({round(100 * n_with_candidate / max(len(incidents), 1), 1)}%) "
              "have a candidate change event.\n")
    md.append(md_table(corr_summary))
    md.append("## Charts\n")
    md.append("![SLA compliance by cluster](sla_compliance_by_cluster.png)\n")
    md.append("![Open incidents by age bucket](incident_ageing.png)\n")
    md.append("![Daily mean TTA / TTM trend](tta_ttm_trend.png)\n")

    md_path = out_dir / "sla_report.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    # Save chart PNGs alongside the Markdown report.
    charts = {
        "sla_compliance_by_cluster.png": _chart_compliance(by_cluster),
        "incident_ageing.png": _chart_ageing(ageing),
        "tta_ttm_trend.png": _chart_trend(daily),
    }
    for name, b64 in charts.items():
        (out_dir / name).write_bytes(base64.b64decode(b64))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Cluster SLA Report (Synthetic Demo Data)</title>
<style>
body {{ font-family: sans-serif; max-width: 900px; margin: 2em auto; padding: 0 1em; color: #222; }}
h1, h2 {{ color: #0d47a1; }}
table {{ border-collapse: collapse; margin: 1em 0; }}
th, td {{ border: 1px solid #bbb; padding: 6px 10px; text-align: left; }}
th {{ background: #e3f2fd; }}
.notice {{ background: #fff8e1; border: 1px solid #ffe082; padding: 0.8em; }}
img {{ max-width: 100%; }}
</style></head>
<body>
<h1>Cluster SLA Report (Synthetic Demo Data)</h1>
<p class="notice"><strong>Synthetic sample data.</strong> This report is generated from
SYNTHETIC telemetry created for demonstration. It is not real production data.</p>
<p><em>Generated: {generated_at} | Incidents: {len(incidents)} | Closed: {len(closed)} |
Open: {len(incidents) - len(closed)} | Change events: {len(events)}</em></p>
<h2>Overall SLA compliance: {overall}% (closed incidents)</h2>
<h2>SLA compliance by cluster</h2>
{by_cluster.to_html(index=False)}
<h2>SLA compliance by severity</h2>
{by_severity.to_html(index=False)}
<h2>TTA / TTM statistics by cluster (minutes)</h2>
{stats.to_html(index=False)}
<h2>Open incidents by age bucket</h2>
{ageing.to_html(index=False)}
<h2>Root-cause correlation ({lookback_minutes} min lookback)</h2>
<p>{n_with_candidate} of {len(incidents)} incidents have a candidate change event.</p>
{corr_summary.to_html(index=False)}
<h2>Charts</h2>
<img src="data:image/png;base64,{charts['sla_compliance_by_cluster.png']}" alt="SLA compliance by cluster">
<img src="data:image/png;base64,{charts['incident_ageing.png']}" alt="Open incidents by age bucket">
<img src="data:image/png;base64,{charts['tta_ttm_trend.png']}" alt="Daily mean TTA / TTM trend">
</body>
</html>
"""
    html_path = out_dir / "sla_report.html"
    html_path.write_text(html, encoding="utf-8")

    return {
        "markdown": str(md_path),
        "html": str(html_path),
        "charts": [str(out_dir / name) for name in charts],
        "overall_compliance_pct": overall,
        "incidents": len(incidents),
        "open_incidents": len(incidents) - len(closed),
        "incidents_with_candidate_event": n_with_candidate,
    }
