#!/usr/bin/env python3
"""End-to-end SLA report run.

Generates SYNTHETIC cluster telemetry, runs the SLA / ageing / correlation
analysis, and writes Markdown + HTML reports (with charts) to output/.

Usage:
    python scripts/run_report.py
    python scripts/run_report.py --incidents 200 --events 300 --days 30 --seed 42 --out output
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from report import build_reports  # noqa: E402
from telemetry import generate_telemetry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the cluster SLA report (synthetic demo data).")
    parser.add_argument("--incidents", type=int, default=120, help="Number of synthetic incidents to generate.")
    parser.add_argument("--events", type=int, default=200, help="Number of synthetic change events to generate.")
    parser.add_argument("--days", type=int, default=30, help="How many days back the synthetic data spans.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (same seed = same data).")
    parser.add_argument("--lookback", type=int, default=60, help="Root-cause lookback window in minutes.")
    parser.add_argument("--out", type=str, default="output", help="Output directory for the reports.")
    args = parser.parse_args()

    incidents, events = generate_telemetry(
        n_incidents=args.incidents, n_events=args.events, days=args.days, seed=args.seed
    )
    result = build_reports(incidents, events, args.out, lookback_minutes=args.lookback)

    print(f"Incidents generated:        {result['incidents']}")
    print(f"Open incidents:             {result['open_incidents']}")
    print(f"Overall SLA compliance:     {result['overall_compliance_pct']}%")
    print(f"With candidate change event: {result['incidents_with_candidate_event']}")
    print(f"Markdown report:            {result['markdown']}")
    print(f"HTML report:                {result['html']}")
    for chart in result["charts"]:
        print(f"Chart:                      {chart}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
