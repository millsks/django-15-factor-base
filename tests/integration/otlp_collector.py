"""A loopback OTLP/HTTP collector stub for exercising the real trace exporter.

Shape decided in Story 6.4 and recorded in `docs/observability.md` under "OTLP
export verification": a standard-library `ThreadingHTTPServer` on
`127.0.0.1:0`, served on a daemon thread, that accepts `POST /v1/traces`,
gunzips a gzip-encoded body, records what arrived and answers `200` with an
empty `ExportTraceServiceResponse`. A handler failure is recorded and re-raised
on context exit, so it fails the test instead of surfacing as "nothing
arrived". No container, no dependency beyond what the pinned
`opentelemetry-exporter-otlp-proto-http` already brings.

This is a helper, not a test module: `python_files` collects only `test_*.py`
and `tests.py`, and coverage omits `*/tests/*`.
"""

from __future__ import annotations

import gzip
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from dataclasses import field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse

if TYPE_CHECKING:
    from collections.abc import Iterator

TRACES_PATH = "/v1/traces"
PROTOBUF_CONTENT_TYPE = "application/x-protobuf"

#: Per-connection socket timeout, in seconds. A client that stalls mid-request
#: fails the handler rather than holding a thread open past the test.
SOCKET_TIMEOUT_SECONDS = 5.0

#: How long context exit waits for the serving thread before declaring a leak.
JOIN_TIMEOUT_SECONDS = 5.0

#: How often `serve_forever` checks for shutdown; bounds how long exit blocks.
POLL_INTERVAL_SECONDS = 0.05


@dataclass(frozen=True)
class CapturedRequest:
    """One request the stub accepted, with its body already decompressed.

    Header names are lower-cased, so lookups do not depend on the client's casing.
    """

    path: str
    headers: dict[str, str]
    body: bytes


@dataclass
class OtlpCollectorStub:
    """What the context manager yields: where to send, and what arrived."""

    endpoint: str
    requests: list[CapturedRequest] = field(default_factory=list)


class _CollectorServer(ThreadingHTTPServer):
    """A loopback server that carries the list its handlers append to."""

    def __init__(self) -> None:
        """Bind to an ephemeral port on loopback only, never all interfaces."""
        super().__init__(("127.0.0.1", 0), _CollectorHandler)
        self.captured: list[CapturedRequest] = []
        self.errors: list[Exception] = []
        self.lock = threading.Lock()


class _CollectorHandler(BaseHTTPRequestHandler):
    """Accept OTLP/HTTP trace exports; answer anything else with 404."""

    timeout = SOCKET_TIMEOUT_SECONDS

    def do_POST(self) -> None:
        """Record a `/v1/traces` export and acknowledge it with an empty response."""
        if self.path != TRACES_PATH:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        server = cast("_CollectorServer", self.server)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            if self.headers.get("Content-Encoding", "").strip().lower() == "gzip":
                body = gzip.decompress(body)
        except (ValueError, OSError, EOFError) as error:
            with server.lock:
                server.errors.append(error)
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        headers = {name.lower(): value for name, value in self.headers.items()}
        with server.lock:
            server.captured.append(CapturedRequest(path=self.path, headers=headers, body=body))

        payload = ExportTraceServiceResponse().SerializeToString()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", PROTOBUF_CONTENT_TYPE)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - signature fixed by the base class
        """Discard request logging, which would otherwise write to stderr."""


@contextmanager
def otlp_collector() -> Iterator[OtlpCollectorStub]:
    """Serve the stub for the duration of the block, then stop and join it.

    Yields:
        The stub, whose `endpoint` is the `http://127.0.0.1:<port>` base URL and
        whose `requests` fills as exports arrive.

    Raises:
        RuntimeError: If a handler failed while reading a request, or the
            serving thread is still alive after shutdown.

    """
    server = _CollectorServer()
    host, port = server.server_address[:2]
    stub = OtlpCollectorStub(endpoint=f"http://{host!s}:{port}", requests=server.captured)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": POLL_INTERVAL_SECONDS},
        name="otlp-collector-stub",
        daemon=True,
    )
    thread.start()
    try:
        yield stub
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=JOIN_TIMEOUT_SECONDS)
        if server.errors:
            msg = "OTLP collector stub failed to read a request"
            raise RuntimeError(msg) from server.errors[0]
        if thread.is_alive():
            msg = "OTLP collector stub thread did not stop"
            raise RuntimeError(msg)
