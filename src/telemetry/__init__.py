"""Synthetic telemetry generation for the SLA reporting demo."""

from .synth import SLA_TARGETS_MINUTES, generate_events, generate_incidents, generate_telemetry

__all__ = ["SLA_TARGETS_MINUTES", "generate_events", "generate_incidents", "generate_telemetry"]
