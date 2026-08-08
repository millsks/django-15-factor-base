"""Logging and telemetry wiring.

`configure_observability` is the single call each process entrypoint makes --
`manage.py`, `wsgi.py`, `asgi.py` and the Celery app. structlog itself is
configured from the settings module instead, because `LOGGING` has to be built
while settings are being read.
"""

from __future__ import annotations

from config.observability.logging import add_otel_context
from config.observability.logging import build_logging_config
from config.observability.logging import configure_structlog
from config.observability.logging import resolve_log_format
from config.observability.telemetry import configure_telemetry

__all__ = [
    "add_otel_context",
    "build_logging_config",
    "configure_observability",
    "configure_structlog",
    "configure_telemetry",
    "resolve_log_format",
]


def configure_observability(service_version: str | None = None) -> bool:
    """Configure telemetry for the current process.

    Args:
        service_version: Version to report on the OpenTelemetry resource.

    Returns:
        True when telemetry was configured by this call, False when skipped.

    """
    return configure_telemetry(service_version)
