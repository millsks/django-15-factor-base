"""Tests for the structlog pipeline configuration."""

from __future__ import annotations

import structlog
from opentelemetry.sdk.trace import TracerProvider

from config.observability.logging import CONSOLE
from config.observability.logging import JSON
from config.observability.logging import add_otel_context
from config.observability.logging import build_logging_config
from config.observability.logging import resolve_log_format
from config.observability.logging import shared_processors

# Hex widths mandated by the OpenTelemetry spec.
TRACE_ID_HEX_LEN = 32
SPAN_ID_HEX_LEN = 16
SENTINEL_USER_ID = 7


class TestAddOtelContext:
    def test_no_keys_added_without_an_active_span(self):
        event_dict = add_otel_context(None, "info", {"event": "hello"})
        assert "trace_id" not in event_dict
        assert "span_id" not in event_dict

    def test_ids_added_inside_a_span(self):
        """The correlation between a log line and its trace."""
        tracer = TracerProvider().get_tracer(__name__)
        with tracer.start_as_current_span("unit-test"):
            event_dict = add_otel_context(None, "info", {"event": "hello"})

        assert len(event_dict["trace_id"]) == TRACE_ID_HEX_LEN
        assert len(event_dict["span_id"]) == SPAN_ID_HEX_LEN
        # Hex, zero-padded -- the format tracing backends expect.
        int(event_dict["trace_id"], 16)
        int(event_dict["span_id"], 16)

    def test_existing_keys_are_preserved(self):
        event = {"event": "hello", "user_id": SENTINEL_USER_ID}
        event_dict = add_otel_context(None, "info", event)
        assert event_dict["event"] == "hello"
        assert event_dict["user_id"] == SENTINEL_USER_ID


class TestResolveLogFormat:
    def test_console_under_debug(self):
        assert resolve_log_format(debug=True) == CONSOLE

    def test_json_when_not_debug(self):
        assert resolve_log_format(debug=False) == JSON

    def test_explicit_choice_wins_over_debug(self):
        assert resolve_log_format(debug=True, log_format=JSON) == JSON
        assert resolve_log_format(debug=False, log_format=CONSOLE) == CONSOLE

    def test_unknown_value_falls_back_rather_than_raising(self):
        """A typo in the environment must not stop the app from starting."""
        assert resolve_log_format(debug=False, log_format="yaml") == JSON
        assert resolve_log_format(debug=False, log_format="") == JSON


class TestSharedProcessors:
    def test_otel_context_is_in_the_shared_chain(self):
        """It must be shared so third-party records get trace ids too."""
        assert add_otel_context in shared_processors()

    def test_contextvars_are_merged_first(self):
        """django-structlog binds request_id via contextvars."""
        assert shared_processors()[0] is structlog.contextvars.merge_contextvars


class TestBuildLoggingConfig:
    def test_formatter_applies_shared_chain_to_foreign_records(self):
        config = build_logging_config(debug=False)
        formatter = config["formatters"]["structured"]
        assert formatter["()"] is structlog.stdlib.ProcessorFormatter
        assert add_otel_context in formatter["foreign_pre_chain"]

    def test_level_is_honoured_and_upper_cased(self):
        config = build_logging_config(debug=False, log_level="debug")
        assert config["root"]["level"] == "DEBUG"

    def test_default_level(self):
        assert build_logging_config(debug=False)["root"]["level"] == "INFO"

    def test_extra_handlers_are_merged_but_kept_off_the_root_logger(self):
        """Production adds mail_admins; it must not fire for every record."""
        config = build_logging_config(
            debug=False,
            extra_handlers={"mail_admins": {"class": "logging.NullHandler"}},
        )
        assert "mail_admins" in config["handlers"]
        assert config["root"]["handlers"] == ["console"]

    def test_extra_loggers_are_merged(self):
        config = build_logging_config(
            debug=False,
            extra_loggers={"django.request": {"level": "ERROR"}},
        )
        assert config["loggers"]["django.request"]["level"] == "ERROR"

    def test_console_handler_uses_the_structured_formatter(self):
        config = build_logging_config(debug=True)
        assert config["handlers"]["console"]["formatter"] == "structured"
