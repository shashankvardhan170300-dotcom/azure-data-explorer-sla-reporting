"""Analysis package: SLA compliance, incident ageing, root-cause correlation."""

from .ageing import ageing_summary, age_bucket, open_incidents_with_age
from .correlation import correlate_incidents, correlation_summary
from .sla import add_sla_flags, compliance_by_cluster, compliance_by_severity, daily_tta_ttm, tta_ttm_stats

__all__ = [
    "add_sla_flags",
    "ageing_summary",
    "age_bucket",
    "compliance_by_cluster",
    "compliance_by_severity",
    "correlate_incidents",
    "correlation_summary",
    "daily_tta_ttm",
    "open_incidents_with_age",
    "tta_ttm_stats",
]
