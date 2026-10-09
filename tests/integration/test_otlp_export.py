"""FR-45: the OTLP export path, driven end to end against a loopback collector stub.

Why this module exists (AC #1). Exporter *selection* is covered thoroughly by
`tests/unit/test_telemetry.py`; the branch that actually exports was not.
`configure_telemetry` attaches `BatchSpanProcessor(OTLPSpanExporter())` at
`src/config/observability/telemetry.py:206-207`, and only when
`resolve_traces_exporter()` returns `otlp` -- which, short of an explicit
`OTEL_TRACES_EXPORTER`, requires `_has_otlp_endpoint()` (`:84-98`) to see a
non-blank `OTEL_EXPORTER_OTLP_ENDPOINT` or `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`.

Every unit test runs under the autouse `_clean_env` (`tests/unit/test_telemetry.py:68-81`),
which scrubs both variables, and the cases that reach `configure_telemetry` use
`installed_provider` (`:84-94`) and `no_side_effects` (`:97-111`) to keep the
provider and instrumentors out of the process; `constructed_exporters`
(`:134-140`) swaps both exporter classes for stubs. The one test that builds a
real exporter, `test_endpoint_configured_attaches_one_batch_processor_wrapping_otlp`
(`:387-412`), points it at `http://collector:4318`, records no span, checks the
types and shuts down -- so a real `OTLPSpanExporter` is *constructed* but no
test serialized a span or sent a byte. Local development never fills the gap
either: no task, `[activation.env]` or feature environment in `pixi.toml`
sets any `OTEL_*` variable, so every `pixi run` path resolves to `none`.

What this module adds (AC #2): the real exporter, built by its own constructor
so its environment reading is exercised, behind a real `BatchSpanProcessor`,
POSTing over a real loopback socket to `tests/integration/otlp_collector.py`.
The bodies are decoded as `ExportTraceServiceRequest`, which is what proves
serialization rather than merely that bytes arrived.

What it deliberately does not do: call `configure_telemetry` or
`trace.set_tracer_provider`. The former instruments the stack process-wide and
the latter is one-shot per process; Story 6.3 asserts the selection, this
module asserts the path selected. Each test builds and shuts down a local
`TracerProvider`.

The test is unconditional and `core` (AC #3): the API, SDK and HTTP exporter are
unconditional `[dependencies]`, nothing here is skipped, and Epic 8's
per-combination gate runs it without special-casing.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from tests.integration.otlp_collector import PROTOBUF_CONTENT_TYPE
from tests.integration.otlp_collector import TRACES_PATH
from tests.integration.otlp_collector import CapturedRequest
from tests.integration.otlp_collector import OtlpCollectorStub
from tests.integration.otlp_collector import otlp_collector

if TYPE_CHECKING:
    from collections.abc import Iterator


#: Seconds. The exporter's default is 10 s with retries; a stub that misbehaves
#: should fail the test well inside the flush timeout below.
EXPORT_TIMEOUT_SECONDS = "3"

#: A flush that has not completed by now is a failure, never a hang.
FLUSH_TIMEOUT_MILLIS = 10_000

SPAN_NAME = "otlp-export-probe"
ATTRIBUTE_KEY = "probe.kind"
ATTRIBUTE_VALUE = "end-to-end"

#: Smaller than the span count, so one flush must split into several exports.
BATCH_SIZE = 2
BATCHED_SPAN_COUNT = 5


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch) -> Iterator[OtlpCollectorStub]:
    """Serve the collector stub and point the exporter's environment at it.

    Every ambient `OTEL_*` variable is scrubbed first -- integration tests get no
    `_clean_env`, and `OTEL_SDK_DISABLED`, the sampler, span limits, `OTEL_BSP_*`
    and the exporter's own variables can each empty or reshape the export.
    """
    for name in [name for name in os.environ if name.startswith("OTEL_")]:
        monkeypatch.delenv(name)
    # An ambient HTTP(S)_PROXY would otherwise route the loopback POST through a proxy.
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    with otlp_collector() as collector:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", f"{collector.endpoint}{TRACES_PATH}")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_TIMEOUT", EXPORT_TIMEOUT_SECONDS)
        yield collector


def _decode(request: CapturedRequest) -> ExportTraceServiceRequest:
    """Parse a captured body as the protobuf the exporter claims to send."""
    decoded = ExportTraceServiceRequest()
    decoded.ParseFromString(request.body)
    return decoded


def _span_names(decoded: ExportTraceServiceRequest) -> list[str]:
    """Flatten every span name in a decoded export request."""
    return [
        span.name
        for resource_spans in decoded.resource_spans
        for scope_spans in resource_spans.scope_spans
        for span in scope_spans.spans
    ]


def _emit_and_flush(provider: TracerProvider, names: list[str]) -> None:
    """Record one span per name on `provider` and flush it to the exporter."""
    tracer = provider.get_tracer(__name__)
    for name in names:
        with tracer.start_as_current_span(name) as span:
            span.set_attribute(ATTRIBUTE_KEY, ATTRIBUTE_VALUE)
    assert provider.force_flush(timeout_millis=FLUSH_TIMEOUT_MILLIS) is True


def _assert_single_probe_export(stub: OtlpCollectorStub) -> CapturedRequest:
    """Assert one protobuf POST arrived carrying exactly the probe span."""
    assert len(stub.requests) == 1, stub.requests
    request = stub.requests[0]
    assert request.path == TRACES_PATH
    assert request.headers.get("content-type") == PROTOBUF_CONTENT_TYPE

    decoded = _decode(request)
    assert len(decoded.resource_spans) == 1
    scope_spans = decoded.resource_spans[0].scope_spans
    assert len(scope_spans) == 1
    spans = scope_spans[0].spans
    assert [span.name for span in spans] == [SPAN_NAME]
    attributes = {attribute.key: attribute.value.string_value for attribute in spans[0].attributes}
    assert attributes == {ATTRIBUTE_KEY: ATTRIBUTE_VALUE}
    return request


def test_a_span_is_serialized_and_sent_to_the_collector(stub: OtlpCollectorStub) -> None:
    """Serialization and transport: one span, one protobuf POST, decodable."""
    provider = TracerProvider()
    try:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        _emit_and_flush(provider, [SPAN_NAME])
        request = _assert_single_probe_export(stub)
        assert "content-encoding" not in request.headers
    finally:
        provider.shutdown()


def test_a_gzip_compressed_export_arrives_and_decodes(
    stub: OtlpCollectorStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The compression variable is honoured and the compressed body still decodes."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_COMPRESSION", "gzip")
    provider = TracerProvider()
    try:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        _emit_and_flush(provider, [SPAN_NAME])
        request = _assert_single_probe_export(stub)
        assert request.headers.get("content-encoding") == "gzip"
    finally:
        provider.shutdown()


def test_spans_beyond_the_batch_size_arrive_across_several_requests_without_loss(
    stub: OtlpCollectorStub,
) -> None:
    """Batch behaviour: five spans over a batch size of two need several POSTs, none lost or repeated."""
    names = [f"batched-span-{index}" for index in range(BATCHED_SPAN_COUNT)]
    provider = TracerProvider()
    try:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(), max_export_batch_size=BATCH_SIZE))
        _emit_and_flush(provider, names)

        assert len(stub.requests) > 1, stub.requests
        assert all(request.path == TRACES_PATH for request in stub.requests)
        assert all(request.headers.get("content-type") == PROTOBUF_CONTENT_TYPE for request in stub.requests)
        received = [name for request in stub.requests for name in _span_names(_decode(request))]
        assert sorted(received) == sorted(names)
        assert all(len(_span_names(_decode(request))) <= BATCH_SIZE for request in stub.requests)
    finally:
        provider.shutdown()
