# Story 6.2: ASGI requests produce spans

Status: ready-for-dev

## Story

As an operator,
I want ASGI requests instrumented in every combination,
so that request traces are not silently absent from components served the only way they are served.

## Acceptance Criteria

**Traceability:** FR-47 · SC-7

1. **Given** the ASGI instrumentor
   **When** any of the twelve combinations is inspected
   **Then** it is present and active
   **And** without it ASGI requests would produce no spans at all

2. **Given** a request served over ASGI
   **When** the suite runs
   **Then** a test asserts that spans are produced for it

## Tasks / Subtasks

- [ ] Task 1 — Establish what "the ASGI instrumentor" is in this codebase before writing anything (AC: #1)
  - [ ] Read `src/config/observability/telemetry.py:134-137`. There is **no** `ASGIInstrumentor().instrument()` call and none is to be added. `opentelemetry-instrumentation-asgi` is an *optional import of the Django instrumentor*: when the package is absent, `opentelemetry.instrumentation.django.middleware.otel_middleware._is_asgi_supported` is `False` and the middleware returns early for ASGI requests — no span, and no warning. `DjangoInstrumentor` plus that package is the ASGI instrumentor here.
  - [ ] Read the existing guard at `tests/unit/test_observability_init.py:17-32` (`TestAsgiInstrumentationIsAvailable.test_asgi_support_is_enabled`) and the rationale at `pixi.toml:62-66` and `docs/observability.md:90-104`. This half of AC #1 is already built; the story's job is to close the "present in **all twelve** combinations" half and the AC #2 span assertion, which nothing covers today.

- [ ] Task 2 — Assert the package is core, not feature-scoped, so it is present in all twelve combinations (AC: #1)
  - [ ] Add a test to `tests/unit/test_dependency_policy.py` that parses `pixi.toml` and asserts `opentelemetry-instrumentation-asgi` appears in the top-level `[dependencies]` table and in **no** `[feature.*.dependencies]` table. `[dependencies]` is unconditional, so it survives every feature selection — that is what makes "all twelve" true rather than assumed.
  - [ ] Assert the same for `opentelemetry-instrumentation-django`, `opentelemetry-api`, `opentelemetry-sdk` and `opentelemetry-exporter-otlp-proto-http` (`pixi.toml:58-61,66`) — the immovable-core instrumentation set must not become feature-scoped by a later edit.
  - [ ] Do **not** assert on `opentelemetry-instrumentation-celery` or `opentelemetry-instrumentation-redis` in this test: those two are the ones AD-24 expects to become feature-owned regions of `pixi.toml`. Add an inline comment saying so, or a future edit will read the omission as an oversight.

- [ ] Task 3 — Prove spans are actually produced for a request served over ASGI (AC: #2)
  - [ ] Add `tests/integration/test_asgi_tracing.py`. Use the `otel_tracing` session fixture and the function-scoped `spans` fixture added to `tests/integration/conftest.py` by Story 6.1 (session-scoped `TracerProvider` + `SimpleSpanProcessor(InMemorySpanExporter())` + `DjangoInstrumentor().instrument()` / `.uninstrument()`). If Story 6.1 has not landed, create those fixtures here instead and note the ownership swap in Completion Notes.
  - [ ] Drive the request through Django's ASGI handler, not the WSGI test client: `django.test.AsyncClient` uses `AsyncClientHandler`, which subclasses `django.core.handlers.asgi.ASGIHandler`. Call it from a synchronous test with `asgiref.sync.async_to_sync(AsyncClient().get)(reverse("home"))` — `asgiref` is a Django dependency and `pytest-asyncio` is not installed, so do not introduce an async test style the environment cannot run.
  - [ ] Assert: at least one span was exported for that request; its `kind` is `SpanKind.SERVER`; its `attributes` include `http.method`/`http.request.method` = `GET`; and the span's `trace_id` is a valid (non-zero) trace id. Choose the attribute key by reading what the installed instrumentor emits rather than guessing — the semantic-convention key changed across OpenTelemetry versions and the stack is pinned at 1.44 with instrumentation `>=0.65b0`.
  - [ ] Add a second assertion that the *same* request produces a log line whose `trace_id` matches the exported span's, so AC #2 and Story 6.1's AC #2 cannot drift apart. Reuse the `_events()` helper pattern from `tests/integration/test_request_logging.py:33-48`.
  - [ ] Mark the module `pytestmark = pytest.mark.django_db` as a safety net: `reverse("home")` renders `pages/home.html` through `base.html` and the `allauth_settings` context processor, which should not query, but session and auth middleware make a DB-free guarantee fragile.

- [ ] Task 4 — Record the negative in the assertion, not only in prose (AC: #1)
  - [ ] Strengthen `tests/unit/test_observability_init.py` so the failure message states the consequence: `_is_asgi_supported is False` means the Django instrumentor's middleware returns early for ASGI requests and produces **no span and no warning**, and both `pixi run serve` (`pixi.toml:179`) and the production `gunicorn` + `uvicorn-worker` pairing are exactly that path. Assert with an explicit message rather than a bare `assert _is_asgi_supported is True`.

- [ ] Task 5 — Keep the documentation and the assertion in agreement (AC: #1)
  - [ ] Update the `docs/observability.md` warning block at `:95-104` to name the new `tests/unit/test_dependency_policy.py` assertion alongside the existing `tests/unit/test_observability_init.py` one, so the doc states both guards.

- [ ] Task 6 — Run the gate (AC: #1, #2)
  - [ ] `pixi run test`, then `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-24** — "A `core` path carries feature-owned regions by declared markers, and by no other mechanism." The **Prevents** clause is directly about this file: "a missed region leaving `CeleryInstrumentor().instrument()` in eight combinations whose environment no longer contains the instrumentor — an `ImportError` at boot that path-level reconciliation cannot see." The per-instrumentor calls at `src/config/observability/telemetry.py:134-137` are one of the three declared region-bearing paths. **This story must not reorder, reformat, merge or wrap those four lines.** Epic 7 declares the markers around them; anything that changes their shape re-cuts that declaration. Forbidden throughout: conditional imports, settings-module inheritance, `try/except ImportError`.
- **AD-16** — "`asgi.py` exposes Django's ASGI application directly. `src/config/websocket.py`, the scope-dispatching wrapper, and its `[tool.coverage.run] omit` entry are all deleted together." That deletion is Epic 1's, not this story's. `src/config/asgi.py:33-43` still wraps `django_application` in a scope dispatcher today. Do **not** delete or restructure it here — but do not route the AC #2 test through `config.asgi.application` either, because that wrapper is on its way out and the test would have to be rewritten. Test against Django's own ASGI handler via `django.test.AsyncClient`.
- **AD-7** — import roots collapse to one declaration site; `src/config/asgi.py:18-20`'s `sys.path` insert is one of the five sites Epic 1 removes. Not this story's to touch.
- **Consistency Conventions → Supply chain** — "conda-forge only; `[pypi-dependencies]` carries the editable self-install and nothing else. Transitive availability is not declaration: a package the code imports directly is declared directly, even when something else already pulls it in." `opentelemetry-instrumentation-asgi` is the inverse case worth stating: it is never imported by project code at all, yet must be declared, because its mere presence flips a flag inside a dependency. The declaration comment at `pixi.toml:62-65` already records this — preserve it.
- **Consistency Conventions → Test location** — the tests written here cover immovable-core behaviour (FR-47 is in the SC-7 set) and therefore carry the `core` disposition; they must never be pruned by any feature and must not import feature-owned modules at module level.
- **AD-30** — a `core`-disposed immovable-core assertion suite runs inside every combination's gate and is never pruned: "AD-20's coverage signal defends SC-2; this suite is what defends SC-7, and nothing else does." The span assertion written here is a member of that suite. Its per-combination execution is Epic 8's mechanism — a traceability marker, not an acceptance condition for this story.
- **AD-20** — 90% coverage including templates, `COVERAGE_CORE=ctrace` in force.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/observability/telemetry.py` | **No change** | Today: `configure_telemetry` (`:104-140`) builds the provider, conditionally attaches an exporter, then instruments Django, Celery, psycopg and redis at `:134-137`. **Verified: AD-24's cited `:134-137` range still holds exactly** — line 134 is `DjangoInstrumentor().instrument()` and line 137 is `RedisInstrumentor().instrument()`. Listed here so the dev agent confirms rather than edits: no ASGI instrumentor call is added. |
| `pixi.toml` | UPDATE (docs comment only, optional) | Today: `opentelemetry-instrumentation-asgi = ">=0.65b0"` at `:66`, in the unconditional `[dependencies]` table, with the rationale comment at `:62-65`. **Preserve both.** No version change. |
| `tests/unit/test_dependency_policy.py` | UPDATE | Today: asserts the supply-chain policy over `pixi.toml` (no third-party package in `[pypi-dependencies]` beyond the editable self-install). Adds the core-instrumentation-set placement assertions. |
| `tests/unit/test_observability_init.py` | UPDATE | Today: 74 lines. `TestAsgiInstrumentationIsAvailable` (`:17-32`) already asserts `_is_asgi_supported is True`; `TestReadDotEnv` (`:35-74`) covers `.env` precedence. Adds the explicit failure message. **Preserve** the `TestReadDotEnv` cases — they cover the "`OTEL_*` must be read before Django loads settings" property. |
| `tests/integration/conftest.py` | UPDATE (only if Story 6.1 has not landed) | Adds the session-scoped `otel_tracing` and function-scoped `spans` fixtures. **Preserve** the `pytest_collection_modifyitems` auto-marking hook at `:11-18`. |
| `tests/integration/test_asgi_tracing.py` | NEW | The AC #2 assertion: a request driven through `ASGIHandler` produces a `SERVER` span, and its trace id matches the log line's. |
| `docs/observability.md` | UPDATE | Today: 180 lines; the `!!! warning "opentelemetry-instrumentation-asgi is not optional here"` block at `:95-104` names only `tests/unit/test_observability_init.py`. Adds the second guard. **Preserve** the "What is instrumented" list at `:90-94` and the "Configuration is read before Django starts" section at `:106-117`. |

### Testing Requirements

- `tests/unit/test_dependency_policy.py`, `tests/unit/test_observability_init.py` — unit: no I/O beyond reading `pixi.toml` from the repository tree, which is the established pattern in that module.
- `tests/integration/test_asgi_tracing.py` — the `@pytest.mark.integration` marker is applied automatically by `tests/integration/conftest.py:11-18`; do not add it by hand.
- Specific assertions the ACs demand:
  - `opentelemetry-instrumentation-asgi` present in `[dependencies]`, absent from every `[feature.*.dependencies]`;
  - `_is_asgi_supported is True`, with a failure message naming the silent-no-span consequence;
  - at least one span exported for a request driven through `django.test.AsyncClient`, `kind == SpanKind.SERVER`, HTTP-method attribute present, trace id non-zero;
  - the span's trace id equals the `trace_id` on the request's `django_structlog` log event.
- Teardown: `DjangoInstrumentor().uninstrument()` must run, and `trace.set_tracer_provider` must be called at most once per process (a second call is warned about and ignored) — hence the session-scoped provider fixture. Each integration test leaves state as it found it.
- AD-20 coverage floor 90% including templates via `pixi run test-cov`; `COVERAGE_CORE=ctrace` comes from `pixi.toml:150`.

#### Project Structure Notes

The Structural Seed puts observability at `src/config/observability/` and this story adds no module there. One variance worth recording: the seed's `pixi.toml` line describes "feature matrix, environments+solve-group, process tasks (AD-3, AD-13, AD-14)", but `pixi.toml:141-143` today declares only `default` and `dev`, both `solve-group = "default"`. The twelve-combination matrix does not exist yet (Epic 8), so the "all twelve combinations" half of AC #1 is discharged here by proving the dependency is **unconditional** rather than by enumerating twelve environments. State that framing in the test's docstring so a later reader does not mistake it for a weaker claim than the AC.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.2] — story statement and both acceptance-criteria blocks.
- [Source: _bmad-output/planning-artifacts/epics.md#FR-47] — "ASGI request tracing — the ASGI instrumentor active in all twelve combinations."
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24] — region mechanism, the three region-bearing paths, the `telemetry.py:134-137` citation, and the `ImportError`-at-boot Prevents clause.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-16] — `asgi.py` exposes Django's ASGI application directly; `websocket.py` is deleted with its coverage omit entry.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-30] — the unprunable `core` immovable-core suite is what defends SC-7.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — Supply chain and Test location rows.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#SC-7] — "produces spans for ASGI requests."
- [Source: src/config/observability/telemetry.py:104-140] — `configure_telemetry` and the four instrumentor calls at `:134-137`.
- [Source: pixi.toml:58-69] — the OpenTelemetry dependency block and the `_is_asgi_supported` rationale comment at `:62-65`.
- [Source: tests/unit/test_observability_init.py:17-32] — the existing `_is_asgi_supported` guard.
- [Source: docs/observability.md:90-104] — "What is instrumented" and the ASGI warning block.
- [Source: src/config/asgi.py:33-43] — the scope-dispatching wrapper AD-16 removes in Epic 1.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
