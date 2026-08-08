"""Tests for the OpenTelemetry setup.

The exporter-selection logic is tested directly because it is what keeps a
missing collector from flooding stderr with retries. `configure_telemetry` is
tested with the instrumentors and the global provider patched out -- calling
them for real would instrument Django, Celery, psycopg and redis for the whole
test session.
"""

from __future__ import annotations

import pytest

from config.observability import telemetry
from config.observability.telemetry import CONSOLE
from config.observability.telemetry import NONE
from config.observability.telemetry import OTLP
from config.observability.telemetry import build_resource
from config.observability.telemetry import configure_telemetry
from config.observability.telemetry import reset_telemetry_for_testing
from config.observability.telemetry import resolve_traces_exporter

OTEL_VARS = (
    "OTEL_SDK_DISABLED",
    "OTEL_TRACES_EXPORTER",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_SERVICE_NAME",
    "DJANGO_ENV",
)


@pytest.fixture(autouse=True)
def _clean_otel_env(monkeypatch: pytest.MonkeyPatch):
    """Start every test from an unconfigured, unset state."""
    for name in OTEL_VARS:
        monkeypatch.delenv(name, raising=False)
    reset_telemetry_for_testing()
    yield
    reset_telemetry_for_testing()


@pytest.fixture
def no_side_effects(monkeypatch: pytest.MonkeyPatch):
    """Patch out instrumentation and the global provider."""
    installed: list[str] = []
    for name in ("Django", "Celery", "Psycopg", "Redis"):
        monkeypatch.setattr(
            telemetry,
            f"{name}Instrumentor",
            lambda name=name: type(
                "Stub",
                (),
                {"instrument": lambda self: installed.append(name)},
            )(),
        )
    monkeypatch.setattr(telemetry.trace, "set_tracer_provider", lambda provider: None)
    return installed


class TestResolveTracesExporter:
    def test_none_when_no_endpoint_is_configured(self):
        """The default path: no collector, so nothing is exported."""
        assert resolve_traces_exporter() == NONE

    def test_otlp_when_endpoint_is_configured(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
        assert resolve_traces_exporter() == OTLP

    def test_otlp_when_only_the_traces_endpoint_is_configured(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            "http://collector:4318/v1/traces",
        )
        assert resolve_traces_exporter() == OTLP

    @pytest.mark.parametrize("value", [CONSOLE, NONE, OTLP])
    def test_explicit_choice_is_honoured(
        self,
        monkeypatch: pytest.MonkeyPatch,
        value: str,
    ):
        monkeypatch.setenv("OTEL_TRACES_EXPORTER", value.upper())
        assert resolve_traces_exporter() == value

    def test_unknown_value_falls_back(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("OTEL_TRACES_EXPORTER", "carrier-pigeon")
        assert resolve_traces_exporter() == NONE


class TestBuildResource:
    def test_default_service_name(self):
        attributes = build_resource().attributes
        assert attributes["service.name"] == telemetry.DEFAULT_SERVICE_NAME
        assert attributes["deployment.environment"] == "local"

    def test_environment_overrides(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("OTEL_SERVICE_NAME", "checkout")
        monkeypatch.setenv("DJANGO_ENV", "production")
        attributes = build_resource("1.2.3").attributes
        assert attributes["service.name"] == "checkout"
        assert attributes["deployment.environment"] == "production"
        assert attributes["service.version"] == "1.2.3"

    def test_version_is_omitted_when_unknown(self):
        assert "service.version" not in build_resource().attributes


class TestConfigureTelemetry:
    def test_disabled_by_the_standard_kill_switch(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
        assert configure_telemetry() is False

    def test_is_idempotent(self, no_side_effects: list[str]):
        """Every process entrypoint calls it; repeat calls must be no-ops."""
        assert configure_telemetry() is True
        assert configure_telemetry() is False
        assert sorted(no_side_effects) == ["Celery", "Django", "Psycopg", "Redis"]

    def test_instruments_even_without_an_exporter(self, no_side_effects: list[str]):
        """Spans still get created, so trace ids still reach the logs."""
        assert configure_telemetry() is True
        assert "Django" in no_side_effects

    def test_console_exporter_registers_a_processor(
        self,
        monkeypatch: pytest.MonkeyPatch,
        no_side_effects: list[str],
    ):
        monkeypatch.setenv("OTEL_TRACES_EXPORTER", CONSOLE)
        added: list[object] = []
        monkeypatch.setattr(
            telemetry.TracerProvider,
            "add_span_processor",
            lambda self, processor: added.append(processor),
        )
        assert configure_telemetry() is True
        assert len(added) == 1

    def test_no_processor_without_an_endpoint(
        self,
        monkeypatch: pytest.MonkeyPatch,
        no_side_effects: list[str],
    ):
        """The whole point: no collector means no retrying exporter."""
        added: list[object] = []
        monkeypatch.setattr(
            telemetry.TracerProvider,
            "add_span_processor",
            lambda self, processor: added.append(processor),
        )
        assert configure_telemetry() is True
        assert added == []
