"""FR-48: a swallowed cache failure is degraded *and* logged, never silent.

`config/settings/production.py` keeps django-redis's `IGNORE_EXCEPTIONS` on, so
a Redis outage degrades the component instead of stopping it (AC #1). Left at
its defaults django-redis then returns the fallback and logs nothing, which is
the `except X: pass` the project standard forbids. The two `DJANGO_REDIS_*`
settings beside the `CACHES` block turn each ignored failure into an `ERROR`
record on `django_service.cache` (AC #2). This module proves both halves against
a cache that cannot connect, plus the negative: without the flag, silence.

This module is `feature:redis`. The behaviour exists only where the Redis cache
is selected, and it imports `django_redis`'s backend by dotted path, so Epic 7
prunes it with the feature in the two combinations that carry no Redis. The
convention it defends -- nothing swallowed silently -- is core; the mechanism is
not. Its unit sibling, `tests/unit/test_cache_degradation_settings.py`, carries
the same disposition.

**Why `CACHES` is overridden in the same call as the flags.** django-redis reads
`DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS` and `DJANGO_REDIS_LOGGER` once, in
`RedisCache.__init__`. Django rebuilds its cache handlers only on a `CACHES`
`setting_changed`, so overriding the two flags alone would leave an
already-built cache object in place and the flags would have no effect -- the
most likely way this module could pass for the wrong reason.

**Why the correlation is read through a formatter attached on emit.** The
record django-redis emits is a plain stdlib record whose message is
`"Exception ignored"`. `request_id`, `trace_id` and `span_id` are added by the
production formatter's `foreign_pre_chain` *at format time*, from the request's
contextvars and the current span. `caplog` formats after the request has
returned, when both are gone, so a handler using the production `structured`
formatter renders each record inside the request and the rendered JSON is what
is asserted. `structlog.testing.capture_logs` is not used: it drops
`merge_contextvars` and `add_otel_context` by construction.

**Why a throwaway URLconf.** Nothing in `src/` performs a cache operation, so no
existing route can carry the request. The request is driven through
`config.asgi.application` itself, so `RequestMiddleware` binds `request_id` and
the ASGI instrumentor opens the span exactly as in production; nothing is bound
by hand. No Redis is required: `127.0.0.1:1` is a closed loopback port, and the
refused connection is what produces django-redis's `ConnectionInterrupted`.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.cache import caches
from django.http import HttpRequest
from django.http import HttpResponse
from django.test import override_settings
from django.urls import path

from config.observability.logging import build_logging_config
from tests.conftest import temporary_root_urlconf

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator

    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

CACHE_LOGGER = "django_service.cache"
PROBE_ROUTE = "cache-probe/"
PROBE_PATH = f"/{PROBE_ROUTE}"
PROBE_KEY = "anything"
PROBE_BODY = b"cache-probe"
RESPONSE_START = "http.response.start"

#: Hex widths mandated by the OpenTelemetry spec.
TRACE_ID_HEX_LEN = 32
SPAN_ID_HEX_LEN = 16

#: A closed loopback port, never a real Redis and never `0.0.0.0`. The one-second
#: socket timeouts keep a firewalled environment, where the connect would hang
#: rather than be refused, from stalling the suite.
UNREACHABLE_CACHES: dict[str, Any] = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:1/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "IGNORE_EXCEPTIONS": True,
            "SOCKET_CONNECT_TIMEOUT": 1,
            "SOCKET_TIMEOUT": 1,
        },
    },
}


@contextmanager
def _unreachable_redis(*, log_ignored: bool) -> Iterator[None]:
    """Install a Redis cache that cannot connect, with or without the logging flags.

    The flags ride the same `override_settings` call as `CACHES`, so the cache
    object is rebuilt and reads them (see the module docstring). Without them,
    `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS` is deleted outright rather than set to
    `False`, so the negative case is django-redis's own default and not a value
    this module chose; `DJANGO_REDIS_LOGGER` is then never read, because
    django-redis builds no logger at all while the flag is off. The cache built under the override is closed on the way
    out; the handler reset on exit discards it.

    Args:
        log_ignored: Whether to install the two settings production carries.

    Yields:
        Control to the block, with the unreachable cache installed.

    """
    flags: dict[str, Any] = (
        {"DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS": True, "DJANGO_REDIS_LOGGER": CACHE_LOGGER} if log_ignored else {}
    )
    with override_settings(CACHES=UNREACHABLE_CACHES, **flags):
        if not log_ignored:
            delattr(settings, "DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS")
            assert not hasattr(settings, "DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS")
        try:
            yield
        finally:
            caches.close_all()


class _RenderingHandler(logging.Handler):
    """Render each record through the production `structured` formatter, on emit."""

    def __init__(self) -> None:
        """Build the JSON formatter exactly as `build_logging_config` declares it."""
        super().__init__(level=logging.DEBUG)
        formatter_config = dict(build_logging_config(debug=False, log_format="json")["formatters"]["structured"])
        factory = formatter_config.pop("()")
        self.setFormatter(factory(**formatter_config))
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Format the record now, while the request's context is still current.

        Args:
            record: The record being emitted.

        """
        self.lines.append(self.format(record))


@contextmanager
def _rendered_cache_lines() -> Iterator[_RenderingHandler]:
    """Attach a rendering handler to the cache logger for the block only.

    Yields:
        The handler, whose `lines` hold every rendered record.

    """
    handler = _RenderingHandler()
    logger = logging.getLogger(CACHE_LOGGER)
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


def _probe_view(request: HttpRequest) -> HttpResponse:
    """Perform one cache read inside a real request.

    Args:
        request: The incoming request.

    Returns:
        A 200 naming whether the read came back empty, so the caller can assert
        the degraded value reached the view rather than an exception.

    """
    value = cache.get(PROBE_KEY)
    return HttpResponse(PROBE_BODY if value is None else b"unexpected")


def _status_and_body(messages: list[dict[str, Any]]) -> tuple[int, bytes]:
    """Extract the status code and body from the ASGI messages sent back.

    Args:
        messages: Every ASGI message the application sent, in order.

    Returns:
        The response status and the concatenated body.

    """
    status = next((message["status"] for message in messages if message["type"] == RESPONSE_START), None)
    assert status is not None, f"no {RESPONSE_START} among {messages}"
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return status, body


def _error_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return the ERROR-or-above records captured on the cache logger.

    Args:
        caplog: The pytest log capture fixture.

    Returns:
        The matching records.

    """
    return [record for record in caplog.records if record.name == CACHE_LOGGER and record.levelno >= logging.ERROR]


class TestACacheOutageDegrades:
    """AC #1: the failure is still ignored."""

    def test_a_read_against_an_unreachable_redis_returns_none(self) -> None:
        """No exception, and the default comes back."""
        with _unreachable_redis(log_ignored=True):
            assert cache.get(PROBE_KEY) is None


@pytest.mark.django_db
class TestTheIgnoredFailureIsLogged:
    """AC #2: the ignored failure is a correlated ERROR record.

    `django_db` because `ATOMIC_REQUESTS` wraps every view in a transaction, so
    even a view that never queries opens a connection.
    """

    def test_one_correlated_error_inside_a_request(
        self,
        caplog: pytest.LogCaptureFixture,
        drive_asgi: Callable[[str], list[dict[str, Any]]],
        recorded_spans: InMemorySpanExporter,
    ) -> None:
        """Driven through the deployed ASGI callable, so nothing is bound by hand."""
        with (
            temporary_root_urlconf(path(PROBE_ROUTE, _probe_view)),
            _unreachable_redis(log_ignored=True),
            _rendered_cache_lines() as rendered,
            caplog.at_level(logging.ERROR, logger=CACHE_LOGGER),
        ):
            status, body = _status_and_body(drive_asgi(PROBE_PATH))

        assert status == HTTPStatus.OK
        assert body == PROBE_BODY, "the view did not see the degraded None"

        records = _error_records(caplog)
        assert len(records) == 1, f"expected one ERROR on {CACHE_LOGGER}, got {[r.getMessage() for r in records]}"
        assert records[0].exc_info is not None, "the ignored exception was logged without its traceback"

        assert len(rendered.lines) == 1, rendered.lines
        event = json.loads(rendered.lines[0])
        assert event["level"] == "error"
        assert event["logger"] == CACHE_LOGGER
        assert event.get("request_id"), f"request_id is absent or empty on the rendered line: {event}"
        assert event.get("exception"), f"the rendered line dropped the traceback: {event}"

        trace_id = event.get("trace_id", "")
        span_id = event.get("span_id", "")
        assert len(trace_id) == TRACE_ID_HEX_LEN, f"malformed trace_id {trace_id!r}"
        assert len(span_id) == SPAN_ID_HEX_LEN, f"malformed span_id {span_id!r}"
        assert int(trace_id, 16) != 0, "trace_id is the invalid all-zero id"
        assert int(span_id, 16) != 0, "span_id is the invalid all-zero id"

        recorded = {
            (format(span.context.trace_id, "032x"), format(span.context.span_id, "016x"))
            for span in recorded_spans.get_finished_spans()
        }
        assert (trace_id, span_id) in recorded, f"the logged ids {(trace_id, span_id)} name no recorded span {recorded}"


class TestWithoutTheFlagTheFailureIsSilent:
    """The regression the production settings close: django-redis's default."""

    def test_the_same_read_logs_nothing(self, caplog: pytest.LogCaptureFixture) -> None:
        """Still degraded, and silent -- which is why production sets the flag."""
        with (
            _unreachable_redis(log_ignored=False),
            _rendered_cache_lines() as rendered,
            caplog.at_level(logging.DEBUG, logger=CACHE_LOGGER),
        ):
            assert cache.get(PROBE_KEY) is None

        assert [record for record in caplog.records if record.name == CACHE_LOGGER] == []
        assert [record for record in caplog.records if record.name.startswith("django_redis")] == []
        assert rendered.lines == []
