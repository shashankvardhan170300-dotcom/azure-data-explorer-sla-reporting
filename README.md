# Azure Data Explorer Analytics & SLA Reporting

A telemetry analytics and SLA-reporting toolkit in Python, built around the
analysis patterns Shashank Narayandas used as a Data Engineer at Microsoft
(Aug 2020 – Jan 2023, Hyderabad): end-to-end root-cause analysis on cluster
telemetry with Azure Data Explorer (KQL) and SQL Server, correlating alerts
with deployment, configuration, and task-execution events, and maintaining
Power BI dashboards that tracked cluster SLA compliance (TTA, TTM, incident
ageing).

## Honesty note

This is a **portfolio reconstruction**, not Microsoft code and not real
production telemetry. All demo telemetry is **SYNTHETIC sample data**
generated locally (see `src/telemetry/synth.py`) so the analysis can run
end-to-end without access to a real cluster. No proprietary code, real
incident data, customer metrics, or internal details are included. The KQL
files are genuine, runnable Kusto Query Language against an ADX cluster —
adjust the table names to your own `Incidents` / `ClusterEvents` tables.

## What it does

- **Synthetic telemetry** (`src/telemetry/synth.py`) — generates incidents
  (severity, cluster, service, TTA/TTM, open vs resolved) and change events
  (deployment / config / task) with a fixed seed for reproducibility.
- **SLA analysis** (`src/analysis/sla.py`) — an incident is compliant when
  both TTA and TTM are within its severity target; compliance % by cluster
  and severity, plus mean / median / p90 TTA-TTM stats and a daily trend.
- **Incident ageing** (`src/analysis/ageing.py`) — open incidents bucketed
  into 0–24h, 24–72h, 72h–7d, 7d+.
- **Root-cause correlation** (`src/analysis/correlation.py`) — for each
  incident, finds the nearest same-cluster change event within a 60-minute
  lookback before the incident opened, as a root-cause candidate.
- **KQL** (`kql/`) — the same four analyses as runnable Kusto queries for a
  real Azure Data Explorer cluster.
- **Reports** (`src/report/generate.py`) — Markdown + self-contained HTML SLA
  reports with matplotlib charts (compliance by cluster, ageing distribution,
  TTA/TTM trend).

## Quick start

```bash
pip install -r requirements.txt
python scripts/run_report.py
```

That generates synthetic telemetry, runs the analysis, and writes the reports
to `output/` (`sla_report.md`, `sla_report.html`, plus chart PNGs).

Options:

```bash
python scripts/run_report.py --incidents 200 --events 300 --days 30 --seed 42 --out output
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests cover SLA math (including boundary and open-incident cases), ageing
bucket boundaries, and correlation window logic (nearest prior event wins,
events outside the window or after the incident are never candidates,
cluster must match).

## SLA targets used in the demo

| Severity | TTA target | TTM target |
|----------|-----------|-----------|
| Sev1 | 15 min | 4 h |
| Sev2 | 30 min | 8 h |
| Sev3 | 2 h | 24 h |
| Sev4 | 8 h | 72 h |

These are illustrative targets for the demo, not any real customer's SLA.

## Project layout

```
src/
  telemetry/synth.py     synthetic incident + change-event generator
  analysis/sla.py        SLA compliance, TTA/TTM stats
  analysis/ageing.py     open-incident ageing buckets
  analysis/correlation.py alert -> change-event correlation
  report/generate.py     Markdown + HTML reports with charts
kql/                     same analyses as runnable KQL
scripts/run_report.py    end-to-end runner
tests/                   pytest suite
```

## License

MIT — see [LICENSE](LICENSE).
