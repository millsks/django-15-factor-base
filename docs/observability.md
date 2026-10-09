# Observability

Logging and tracing are permanent parts of this template, not an optional
add-on. Every process — web, ASGI, Celery worker, management command — emits
structured logs through **structlog** and creates **OpenTelemetry** spans.

## What a log line looks like

```json
{
  "event": "request_started",
  "request": "GET /",
  "request_id": "779e9522-1615-4425-baa1-a6f8ac9f1495",
  "user_id": null,
  "ip": "127.0.0.1",
  "level": "info",
  "logger": "django_structlog.middlewares.request",
  "timestamp": "2026-08-08T21:37:00.576800Z",
  "trace_id": "3293968340d1e265f91e2e43e120bba8",
  "span_id": "eb80a5eaf6eba477"
}
```

Three identifiers do the work:

- **`request_id`** ties every line from one request together, and follows the
  request into any Celery task it enqueues.
- **`trace_id`** opens the corresponding trace in your tracing backend.
- **`user_id`** is populated because `RequestMiddleware` is ordered *after*
  `AuthenticationMiddleware`.

Django, allauth and Celery log through the standard library, not structlog.
They are routed through `structlog.stdlib.ProcessorFormatter` with the same
`foreign_pre_chain`, so their output is structured and carries the same
timestamp, level and trace context. There is no second log format to parse.

## Configuration

All standard OpenTelemetry variables apply. The ones that matter most:

| Variable | Default | Effect |
| --- | --- | --- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | Where spans are sent. Unset means spans are created but not exported. |
| `OTEL_TRACES_EXPORTER` | `otlp` when an endpoint is set, else `none` | `otlp`, `console` or `none`. `otlp` requires an endpoint: set without one, it resolves to `none` and logs a warning. |
| `OTEL_SERVICE_NAME` | `django-15-factor-base` | `service.name` on the resource. |
| `OTEL_SDK_DISABLED` | `false` | Turns tracing off entirely, per the OTel spec. |
| `COMPONENT_RUNTIME` | unset — the `dev` pixi environment sets `local`, so every `pixi run` path is local | Reported as `deployment.environment`, which takes exactly two values: `local` when this variable is `local` (after stripping and lowercasing), and `deployed` otherwise. This attribute previously mirrored `DJANGO_ENV` and could carry a tier name such as `staging`; a dashboard or alert keyed on those values needs updating. |
| `DJANGO_LOG_LEVEL` | `INFO` | Root log level. |
| `DJANGO_LOG_FORMAT` | `console` under DEBUG, else `json` | `json` or `console`. |

### Why export is conditional

A `BatchSpanProcessor` whose collector is unreachable retries on every export
cycle and floods stderr — in every test run and every `runserver`. So the OTLP
processor is attached **only** when an endpoint is configured:

| Condition | SDK + instrumentation | Span export | `trace_id` in logs |
| --- | --- | --- | --- |
| Endpoint set | on | OTLP | yes |
| Endpoint unset | on | dropped | yes |
| `OTEL_TRACES_EXPORTER=console` | on | stdout | yes |
| `OTEL_TRACES_EXPORTER=otlp`, endpoint unset | on | dropped, with a warning | yes |
| `OTEL_SDK_DISABLED=true` | off | none | no |

Instrumentation is installed either way, which is why `trace_id` appears in the
sample above even with no collector running.

**Instrumentation is unconditional, not merely "not skipped".** The Django,
Celery, psycopg and redis instrumentors are installed on every run, in every
environment, with no `if DEBUG`, no locality check and no endpoint check in
front of them — `configure_telemetry` attaches a span processor conditionally
and then instruments unconditionally. Nothing about the export decision reaches
the instrumentors, so a local run exercises the same instrumentation code a
deployed one does. Spans are created and ended locally exactly as they are
deployed; with no processor attached they are simply discarded when they end,
and their `SpanContext` is live for the whole span, which is what keeps
`trace_id` and `span_id` on every log line a span is active for. The one
condition that turns instrumentation off is `OTEL_SDK_DISABLED`, and nothing in
this repository sets or defaults it.

Setting `OTEL_TRACES_EXPORTER=otlp` explicitly does not get around this. With
neither `OTEL_EXPORTER_OTLP_ENDPOINT` nor `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`
set, the explicit choice resolves to `none` rather than letting the exporter
fall back to the SDK's default `http://localhost:4318`, and one warning is
logged, `telemetry.otlp_exporter_without_endpoint`, naming all three variables
so the operator who set it learns why nothing is exporting. It is a warning and
not a refusal: the component degrades through the misconfiguration rather than
failing to start. `console` and `none` are honoured as set, since neither
reaches the network. Whether a configured endpoint is actually *reachable* is
not checked — startup makes no network call — so "an endpoint is configured" is
the whole rule.

## Seeing it work

Spans to your terminal, no collector required:

```sh
OTEL_TRACES_EXPORTER=console pixi run runserver
curl localhost:8000/
```

JSON logs in development, which normally default to console rendering:

```sh
DJANGO_LOG_FORMAT=json pixi run runserver
```

Against a collector:

```sh
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=my-service
pixi run serve
```

## What is instrumented

`DjangoInstrumentor`, `CeleryInstrumentor`, `PsycopgInstrumentor` and
`RedisInstrumentor` — so a trace spans the request, the queries it ran, the
cache calls it made and any task it queued.

!!! warning "`opentelemetry-instrumentation-asgi` is not optional here"

    It is an *optional* import of the Django instrumentor, but this project
    needs it. Without it `_is_asgi_supported` is `False` and the middleware
    returns early for ASGI requests — **no span, and no warning**. Since
    `pixi run serve` and the production uvicorn worker are both ASGI, dropping
    the package would silently disable tracing in production while leaving
    `runserver` working.

    Three guards keep this from regressing, and they defend different things.
    `tests/unit/test_observability_init.py` asserts `_is_asgi_supported` is true
    — that the package is importable in *this* environment, whichever one the
    suite happens to be running in. `tests/unit/test_dependency_policy.py`
    asserts it is declared in `pixi.toml`'s unconditional `[dependencies]` table
    and in no `[feature.*]` or `[target.*]` table — that it is present in *every*
    combination rather than in the one that was tested. Neither implies the
    other: a package could be importable in `dev` and absent from a combination
    nobody ran the suite in, and a correct declaration could still fail to
    install.

    The third, `tests/integration/test_asgi_tracing.py`, asserts the behaviour
    the other two exist to protect: a request driven through `config.asgi.application` produces a
    `SERVER` span carrying the HTTP method and a real trace id, and the same
    request's log line names that trace.

## Configuration is read before Django starts

`configure_observability()` runs at entrypoint import — before Django loads its
settings. That is deliberate: the Django instrumentor inserts its middleware
into `MIDDLEWARE`, which has no effect once the middleware chain is built.

The consequence is that `OTEL_*` variables must be in the environment before
settings are read. `configure_observability()` therefore loads `.env` itself
when `DJANGO_READ_DOT_ENV_FILE` is set, rather than waiting for the settings
module to do it — otherwise `OTEL_*` entries in `.env` would be parsed too late
and appear to be ignored. Real environment variables still take precedence.

## Writing logs

Use structlog, never the standard library, and pass data as keyword arguments
rather than interpolating it into the message:

```python
import structlog

logger = structlog.get_logger(__name__)

logger.info("order_placed", order_id=order.pk, total=order.total)
```

`request_id`, `user_id` and `trace_id` are added for you.

## Layout

```
src/config/observability/
  __init__.py     configure_observability() -- called by each process entrypoint
  logging.py      processor chains and the LOGGING dictConfig factory
  telemetry.py    tracer provider, exporter selection, instrumentors
```

`configure_observability()` is called from `manage.py`, `wsgi.py`, `asgi.py`
and `celery_app.py`, and is idempotent. It is deliberately not called from an
`AppConfig.ready()` hook: that runs after Django has built its handler stack,
and can fire more than once.

structlog itself is configured from `config/settings/base.py`, because
`LOGGING` has to be built while settings are being read.

## OTLP export verification

**Owner:** Platform engineering. **Decided:** 2026-10-09 (Story 6.4, FR-45).

Because nothing local configures an endpoint, the branch in
`configure_telemetry` that attaches `BatchSpanProcessor(OTLPSpanExporter())` is
the one path no ordinary run reaches. `tests/integration/test_otlp_export.py`
builds the same processor and exporter pair that branch builds -- independently
of `configure_telemetry` -- and drives it against a collector stub in
`tests/integration/otlp_collector.py`.

The stub is a standard-library `http.server.ThreadingHTTPServer` bound to
`127.0.0.1` on an ephemeral port and served on a daemon thread. It accepts
`POST /v1/traces`, gunzips the body when `Content-Encoding: gzip`, records the
path, headers and body, and answers `200` with an empty
`ExportTraceServiceResponse`; any other path or method is refused. It is loopback only,
needs no container and adds no dependency: the pinned exporter is
`opentelemetry-exporter-otlp-proto-http`, which already speaks protobuf over
HTTP, and the gate runs with no external service.

What the test proves, using the real exporter built from its own environment
variables behind a real `BatchSpanProcessor`:

- **Serialization** — the captured body decodes as an `ExportTraceServiceRequest`
  carrying the emitted span's name and attribute, with and without gzip.
- **Transport** — exactly one `POST` to `/v1/traces` per flush of a single span,
  with `Content-Type: application/x-protobuf`.
- **Batching** — five spans over a `max_export_batch_size` of two arrive across
  several requests, none lost and none repeated.

What it deliberately does not prove:

- compatibility with a real collector, or with any particular backend;
- the gRPC exporter, which is not a dependency;
- retry and backoff against a failing or unreachable collector;
- TLS or authentication headers;
- that `configure_telemetry` *selects* this path, or constructs the exporter
  it attaches — Story 6.3's tests in `tests/unit/test_telemetry.py` cover
  selection and the processor's types, and this test never calls
  `configure_telemetry` or installs a global tracer provider.

The test is unconditional and `core`: the OpenTelemetry API, SDK and HTTP
exporter are all in `pixi.toml`'s unconditional `[dependencies]`, and nothing
skips it. Running it inside every combination's gate completes in Epic 8, which
builds the six-combination harness; being unconditional is what lets that gate
run it without special-casing.

## Cache degradation is logged

Where the Redis feature is selected (four of the six combinations), the deployed
cache is `django_redis` with `IGNORE_EXCEPTIONS` on, so a Redis outage degrades
the component rather than stopping it: a failed read returns the default and a
failed write is dropped. Ignoring the failure is not the same as hiding it.
`config/settings/production.py` also sets:

```python
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
DJANGO_REDIS_LOGGER = "django_service.cache"
```

so every ignored failure is logged at `ERROR` on `django_service.cache`, with the
traceback. That logger is a child of the configured `django_service` logger, and
the record passes the same `foreign_pre_chain` as every other stdlib record, so
it carries the `request_id`, `trace_id` and `span_id` of the request it happened
in. Nothing is swallowed silently. This is the project standard applied to a
third-party default: never `except X: pass`, log or re-raise. django-redis's
default is exactly that silent `except`, which is why the default is not used.

Two limits. Degradation is prompt only when the failure is: production sets no
socket timeout on the Redis client, so a host that drops packets rather than
refusing the connection blocks each cache call for the operating system's TCP
timeout. And nothing in `src/` performs a cache operation today, so this is in
place for the first code that does, rather than for a caller that exists.

Local and test runs use `LocMemCache`, which cannot lose a connection and has
nothing to swallow, so the two settings are not set there.
`tests/integration/test_cache_degradation.py` drives a request against an
unreachable Redis and asserts both halves: the call returns `None`, and exactly
one correlated `ERROR` line is emitted.

## Adding metrics or OTLP logs later

Both are additive and need no restructuring:

- **Metrics** — add a `MeterProvider` with a `PeriodicExportingMetricReader` in
  `configure_telemetry()`, plus `opentelemetry-exporter-otlp-proto-http`, which
  is already a dependency.
- **OTLP logs** — attach an OTel `LoggingHandler` in `build_logging_config()`
  alongside the console handler. Logs would then go to both stdout and the
  collector.

## Note on dependencies

Every dependency resolves from conda-forge, including `django-celery-beat`. It
used to be the one exception: the recipe dropped the environment marker on
upstream's `importlib-metadata<5.0; python_version < "3.8"` and applied the cap
unconditionally, which collided with `opentelemetry-api`'s
`importlib-metadata>=6.0` and made the two impossible to install together. Build
`2.9.0 pyhcf101f3_1` removed the cap, so the dependency moved into
`[dependencies]` in `pixi.toml` and the project now carries no supply-chain
exceptions at all.

The recipe's remaining constraint is a `django <6.1` cap, which will block a
Django 6.1 upgrade until it is relaxed. See [Supply chain](development.md#supply-chain)
for the policy the whole dependency set is held to.
