---
status: done
baseline_revision: 4100868
review_loop_iteration: 0
final_revision: 5be15d9
followup_review_recommended: true
warnings: [oversized]
---

# Story 6.2: ASGI requests produce spans

Status: ready-for-dev

## Story

As an operator,
I want ASGI requests instrumented in every combination,
so that request traces are not silently absent from components served the only way they are served.

## Acceptance Criteria

**Traceability:** FR-47 · SC-7

1. **Given** the ASGI instrumentor
   **When** any of the six combinations is inspected
   **Then** it is present and active
   **And** without it ASGI requests would produce no spans at all

2. **Given** a request served over ASGI
   **When** the suite runs
   **Then** a test asserts that spans are produced for it

## Tasks / Subtasks

<!-- Reconciled against the tree at 4100868 before implementation. Every line
     number the frozen spec cited had moved, the fixture names it predicted are
     not the names Story 6.1 shipped, and part of AC #2 turned out to be already
     covered by Story 1.4. The reconciliation is recorded in Completion Notes;
     the Acceptance Criteria above are untouched. -->

- [x] Task 1 — Establish what "the ASGI instrumentor" is here, and what is already covered, before writing anything (AC: #1, #2)
  - [x] Read `src/config/observability/telemetry.py` around the four instrumentor calls. There is **no** `ASGIInstrumentor().instrument()` call and none is to be added. `opentelemetry-instrumentation-asgi` is an *optional import of the Django instrumentor*: without it `opentelemetry.instrumentation.django.middleware.otel_middleware._is_asgi_supported` is `False` and `_DjangoMiddleware` returns early for ASGI requests (verified at `otel_middleware.py:178` and `:324` in the installed package) — no span, and no warning. `DjangoInstrumentor` plus that package is the ASGI instrumentor here.
  - [x] Read the existing guard at `tests/unit/test_observability_init.py:17-32` (`TestAsgiInstrumentationIsAvailable.test_asgi_support_is_enabled`), the rationale at `pixi.toml:124-127` and the warning block at `docs/observability.md:115-123`. **Corrected reference:** the frozen spec cited `pixi.toml:62-66` and `docs/observability.md:90-104`; both files have grown since it was written.
  - [x] **Corrected scope for AC #2.** The frozen spec says the span assertion "nothing covers today". That is no longer true: Story 1.4 shipped `tests/integration/test_asgi_request_path.py::TestAsgiRequestsAreStillTraced`, which drives `config.asgi.application` with a raw `http` scope and asserts a `SpanKind.SERVER` span plus the resolved-route span name. What it does **not** assert, and what this story adds, is (a) the HTTP-method attribute, (b) a non-zero trace id, and (c) that the *same* ASGI request's log line carries that span's trace id. `tests/integration/test_log_correlation.py` asserts (c) only over the **WSGI** test client, so the ASGI path — the only path a component is served on — is where the two halves can still drift apart unobserved.

- [x] Task 2 — Assert the instrumentation set is core, not feature-scoped, so it is present in all six combinations (AC: #1)
  - [x] Add tests to `tests/unit/test_dependency_policy.py` asserting `opentelemetry-instrumentation-asgi` appears in the top-level `[dependencies]` table (`pixi.toml:128`) and in **no** `[feature.*.dependencies]` table. `[dependencies]` is unconditional, so it survives every feature selection — that is what makes "all six" true rather than assumed. State that framing in the docstring so a later reader does not read it as a weaker claim than the AC.
  - [x] Assert the same for `opentelemetry-instrumentation-django`, `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http` and `opentelemetry-instrumentation-psycopg` (`pixi.toml:120-123,128,130`) — the immovable-core instrumentation set must not become feature-scoped by a later edit. `psycopg` is included because `telemetry.py`'s `PsycopgInstrumentor().instrument()` is `core` beside `DjangoInstrumentor().instrument()`.
  - [x] Do **not** assert on `opentelemetry-instrumentation-celery` or `opentelemetry-instrumentation-redis`: those two are the ones AD-24 expects to become feature-owned regions of `pixi.toml`, matching the single-line regions in `telemetry.py` and their imports. Add an inline comment saying so, or a future edit will read the omission as an oversight.
  - [x] **Reuse the module's own machinery rather than adding a parallel reader.** `_feature_dependencies(manifest)` (`tests/unit/test_dependency_policy.py:480`) already returns feature -> platform -> package and synthesizes a `"default"` feature from `[dependencies]` plus `[target.*.dependencies]`; `_declarations(lines)` (`:276`) already yields every declaration with its owning table. Cover `[target.<platform>.dependencies]` too — `pixi.toml:147,151` prove that idiom is live in this manifest, and a fixed-path reader would miss a package moved there. The module has **no test classes**: every test is a module-level function with a prose-sentence name, a rationale docstring opening with the requirement id, and a long f-string message on every assert. Match that.

- [x] Task 3 — Prove spans are produced for a request served over ASGI, and that the log line agrees (AC: #2)
  - [x] Add `tests/integration/test_asgi_tracing.py`. Use the function-scoped `recorded_spans` fixture in `tests/integration/conftest.py:47` — **corrected name**: the frozen spec predicted `otel_tracing` + `spans`; Story 6.1 shipped one fixture called `recorded_spans` that attaches an `InMemorySpanExporter` to the live process-wide provider and restores the processor list on teardown. It has landed; do not create fixtures for it and do not call `trace.set_tracer_provider`.
  - [x] **Drive `config.asgi.application` with a raw `http` scope, not `django.test.AsyncClient`.** The frozen spec's Task 3 says `AsyncClient`; its own Dev Notes (AD-16) then invert that instruction and explain why — `AsyncClient` uses `AsyncClientHandler`, a subclass the test client builds, whereas `config.asgi.application` is the exact object uvicorn loads. The Dev Notes' correction wins, and `tests/integration/test_asgi_request_path.py` already establishes the shape.
  - [x] Do not write a third byte-identical copy of the async driver. Add a `drive_asgi` fixture to `tests/integration/conftest.py` yielding a callable that builds the scope, drives `config.asgi.application` and returns the sent messages — a fixture, because a conftest cannot be imported from a test module, and because the deferred-work ledger already records duplicated integration helpers as belonging there. Leave `tests/integration/test_asgi_request_path.py` alone: it is Story 1.4's file and rewriting it is not this story's change. Keep the local `_span_absence_hint()` copy in the new module, matching the convention `conftest.py` records for predicates used inside assertion messages.
  - [x] Assert, for one request: at least one exported span has `kind == SpanKind.SERVER`; that span's `attributes` carry `GET` under `http.method` **or** `http.request.method`; and its `context.trace_id` is non-zero. **Verified against the installed stack:** with no `OTEL_SEMCONV_STABILITY_OPT_IN` set the mode is `_StabilityMode.DEFAULT`, so `_set_http_method` writes the old key `http.method` (`opentelemetry/instrumentation/_semconv.py:361-364`); accept either key and name both plus that environment variable in the failure message, so an opt-in flip reads as a convention change rather than a missing span.
  - [x] Add a second case asserting the *same* request produces a log line whose `trace_id` equals the exported `SERVER` span's, so AC #2 and Story 6.1's AC #2 cannot drift apart on the ASGI path. Reuse the `_events(caplog, name)` helper shape from `tests/integration/test_log_correlation.py:97`, read `record.msg` through `caplog` and **never** through `structlog.testing.capture_logs` — that helper drops `merge_contextvars` and `add_otel_context`, so every identifier under test vanishes by construction.
  - [x] Use `account_login`, not `home`. Story 7.4 deletes the `home` and `about` routes as demonstration content (AD-29) — `src/config/urls.py:26-30` already carries that comment — while `account_login`, registered by `include("allauth.urls")` at `src/config/urls.py:46`, is `core` in all six combinations because FR-4's interactive flow is immovable core.
  - [x] Mark the module `pytestmark = [pytest.mark.integration, pytest.mark.django_db]`, matching the two sibling modules. The `integration` marker is auto-applied by `tests/integration/conftest.py:22-29`; the sibling modules still declare it explicitly, so follow them rather than the frozen spec's "do not add it by hand".

- [x] Task 4 — Record the negative in the assertion, not only in prose (AC: #1)
  - [x] `tests/unit/test_observability_init.py:31` is a bare `assert _is_asgi_supported is True`. Give it an explicit message stating the consequence: `False` means the Django instrumentor's middleware returns early for ASGI requests and produces **no span and no warning**, and both `pixi run serve` (`pixi.toml:498`) and the production `gunicorn` + `uvicorn-worker` pairing (`pixi.toml:147,151`) are exactly that path. **Preserve** the four `TestReadDotEnv` cases — they cover the "`OTEL_*` must be read before Django loads settings" property.

- [x] Task 5 — Keep the documentation and the assertions in agreement (AC: #1)
  - [x] `docs/observability.md:122-123` names only `tests/unit/test_observability_init.py`. Name the new `tests/unit/test_dependency_policy.py` assertion beside it, and say what each of the two guards actually defends: one that the flag is true in *this* environment, the other that the dependency is unconditional and therefore present in *every* combination. **Preserve** the "What is instrumented" list at `:111-113` and the "Configuration is read before Django starts" section at `:125` onward.

- [x] Task 6 — Run the gate (AC: #1, #2)
  - [x] `pixi run test`, then `pixi run test-integration`, then `pixi run ci` (exit 0 required; `ci` chains precommit -> build -> typecheck -> lint -> test-cov at the 90% floor).

## Dev Notes

### Architecture Constraints

- **AD-24** — "A `core` path carries feature-owned regions by declared markers, and by no other mechanism." The **Prevents** clause is directly about this file: "a missed region leaving `CeleryInstrumentor().instrument()` in eight combinations whose environment no longer contains the instrumentor — an `ImportError` at boot that path-level reconciliation cannot see" (the spine's clause still says *eight* from the twelve-combination model; under revision 3 it is the **four** combinations without Celery). `src/config/observability/telemetry.py` is one of an **open, carrier-declared set** of region-bearing paths — the reconciler encodes no count.
  **`:134-137` is not one region, and this story must not treat it as one.** `:134` `DjangoInstrumentor().instrument()` and `:136` `PsycopgInstrumentor().instrument()` are **`core`** — present in all six combinations, and `:134` is precisely the call this story's ASGI spans depend on. Only `:135` `CeleryInstrumentor().instrument()` and `:137` `RedisInstrumentor().instrument()` are feature-owned, as **two single-line regions**, and each region must also cover its import — `:21 from opentelemetry.instrumentation.celery import CeleryInstrumentor` and `:24 from opentelemetry.instrumentation.redis import RedisInstrumentor` — because pruning a call without its import moves the `ImportError` from line 135 to line 21 rather than fixing it.
  Practical consequence for this story, which changes none of it: leave `:21-24` and `:134-137` one import and one call per line, and do not merge, wrap, reorder or interleave them. Four separate marker pairs land there in Epic 7, not one. Forbidden throughout: conditional imports, settings-module inheritance, `try/except ImportError`.
- **AD-16** — "`asgi.py` exposes Django's ASGI application directly. `src/config/websocket.py`, the scope-dispatching wrapper, and its `[tool.coverage.run] omit` entry are all deleted together." That deletion is Epic 1's, not this story's, **and Story 1.4 has since landed it**: `src/config/asgi.py` now binds one name, `application = get_asgi_application()`, with no wrapper in front of it. The earlier instruction here — do not route the AC #2 test through `config.asgi.application`, because the wrapper is on its way out — is obsolete and was inverted by that deletion. `config.asgi.application` is now Django's own `ASGIHandler` and is the object uvicorn loads, so it is the *better* target for a span assertion than `django.test.AsyncClient`, whose `AsyncClientHandler` is a subclass built by the test client rather than the deployed callable. `tests/integration/test_asgi_request_path.py`, written by Story 1.4, already drives raw `http` scopes against it and asserts a `SpanKind.SERVER` span; reuse that shape rather than re-deriving it, and do not restructure `asgi.py` here.
- **AD-7** — import roots collapse to one declaration site; `src/config/asgi.py:18-20`'s `sys.path` insert is one of the **six** sites Epic 1 removes. Not this story's to touch.
- **Consistency Conventions → Supply chain** — "conda-forge only; `[pypi-dependencies]` carries the editable self-install and nothing else. Transitive availability is not declaration: a package the code imports directly is declared directly, even when something else already pulls it in." `opentelemetry-instrumentation-asgi` is the inverse case worth stating: it is never imported by project code at all, yet must be declared, because its mere presence flips a flag inside a dependency. The declaration comment at `pixi.toml:62-65` already records this — preserve it.
- **Consistency Conventions → Test location** — the tests written here cover immovable-core behaviour (FR-47 is in the SC-7 set) and therefore carry the `core` disposition; they must never be pruned by any feature and must not import feature-owned modules at module level.
- **AD-30** — a `core`-disposed immovable-core assertion suite runs inside every combination's gate and is never pruned: "AD-20's coverage signal defends SC-2; this suite is what defends SC-7, and nothing else does." The span assertion written here is a member of that suite. Its per-combination execution is Epic 8's mechanism — a traceability marker, not an acceptance condition for this story.
- **AD-20** — 90% coverage including templates, `COVERAGE_CORE=ctrace` in force.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/observability/telemetry.py` | **No change** | Today: `configure_telemetry` (`:104-140`) builds the provider, conditionally attaches an exporter, then instruments Django, Celery, psycopg and redis at `:134-137`. **Verified line by line:** `:134` `DjangoInstrumentor().instrument()` (**`core`**), `:135` `CeleryInstrumentor().instrument()` (`feature:celery`, with its import at `:21`), `:136` `PsycopgInstrumentor().instrument()` (**`core`**), `:137` `RedisInstrumentor().instrument()` (`feature:redis`, with its import at `:24`). AD-24's earlier `:134-137`-as-one-region framing was corrected precisely because it would strip `:134` — the Django instrumentor this story's ASGI spans come from — out of every combination. Listed here so the dev agent confirms rather than edits: no ASGI instrumentor call is added. |
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

The Structural Seed puts observability at `src/config/observability/` and this story adds no module there. One variance worth recording: the seed's `pixi.toml` line describes "feature matrix, environments+solve-group, process tasks (AD-3, AD-13, AD-14)", but `pixi.toml:141-143` today declares only `default` and `dev`, both `solve-group = "default"`. The six pre-locked environments do not exist yet (Epic 8), so the "all six combinations" half of AC #1 is discharged here by proving the dependency is **unconditional** rather than by enumerating six environments. State that framing in the test's docstring so a later reader does not mistake it for a weaker claim than the AC.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.2] — story statement and both acceptance-criteria blocks.
- [Source: _bmad-output/planning-artifacts/epics.md#FR-47] — "ASGI request tracing — the ASGI instrumentor active in all six combinations."
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24] — region mechanism, the open set of region-bearing paths, the `telemetry.py:135`/`:137`-plus-imports-`:21`/`:24` citation with `:134` and `:136` `core`, and the `ImportError`-at-boot Prevents clause.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-16] — `asgi.py` exposes Django's ASGI application directly; `websocket.py` is deleted with its coverage omit entry.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-30] — the unprunable `core` immovable-core suite is what defends SC-7.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — Supply chain and Test location rows.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#SC-7] — "produces spans for ASGI requests."
- [Source: src/config/observability/telemetry.py:104-140] — `configure_telemetry` and the four instrumentor calls at `:134-137`.
- [Source: pixi.toml:58-69] — the OpenTelemetry dependency block and the `_is_asgi_supported` rationale comment at `:62-65`.
- [Source: tests/unit/test_observability_init.py:17-32] — the existing `_is_asgi_supported` guard.
- [Source: docs/observability.md:90-104] — "What is instrumented" and the ASGI warning block.
- [Source: src/config/asgi.py] — the scope-dispatching wrapper AD-16 removes; deleted by Story 1.4, so the file now binds `application = get_asgi_application()` and nothing else.

## Review Triage Log

### 2026-09-02 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 11: (high 2, medium 5, low 4)
- defer: 5: (high 0, medium 4, low 1)
- reject: 11: (high 0, medium 3, low 8)
- addressed_findings:
  - `[high]` `[patch]` **The log-correlation test was order-dependent and failed in isolation.** `drive_asgi` deferred `import config.asgi` into the driver; that import runs `django.setup()`, whose `configure_logging(dictConfig)` *replaces* the root logger's handlers — including the `LogCaptureHandler` pytest installs for `caplog`. The wipe therefore landed inside the `caplog.at_level` window of whichever test drove first. Verified: `pytest tests/integration/test_asgi_tracing.py::TestTheAsgiRequestsLogLineNamesTheSameTrace` alone **failed** ("emitted no `request_started` event") while the module passed. Fixed by hoisting the import to conftest module scope — which the deferring rationale's own premise did not survive, since `tests/integration/test_asgi_request_path.py` already imports it at module scope in the same directory. Re-verified: the class now passes alone.
  - `[high]` `[patch]` **All three tests discarded the driver's return value, so a broken route was indistinguishable from a served one.** A 404 or 500 still produces a `SERVER` span carrying `http.method` and a non-zero trace id, and django-structlog emits `request_started` before resolution either way — so a renamed `account_login` would have left the module green while proving nothing. Added `_assert_served()`, asserting exactly one `http.response.start` carrying 200, the shape both sibling modules already use. Verified by mutation: repointing the three tests at `/no-such-page/` now fails all three; before the patch it failed none.
  - `[medium]` `[patch]` `spans[0]` was indexed without asserting there is exactly one `SERVER` span, though the module's own helper docstring concedes the exporter is attached to the *process-wide* provider. Added `_the_server_span()`, which asserts the count and names every exported span on failure.
  - `[medium]` `[patch]` `spans[0].context.trace_id` would raise a bare `AttributeError` rather than fail with the authored message: `ReadableSpan.context` is `SpanContext | None`, and mypy is scoped to `src/` so nothing in the gate types it. A null-ish span context is precisely this module's subject. Added `_trace_id_of()`.
  - `[medium]` `[patch]` The ASGI `request_started` line was checked for `trace_id` alone. django-structlog binds the identifiers through `sync_to_async(self.prepare)` on the async path and directly on the sync one, so `tests/integration/test_log_correlation.py`'s WSGI assertion of the three-identifier conjunction cannot speak for ASGI — the only path a component is served on. Added the `CORRELATION_KEYS` check, reusing that module's frozenset shape.
  - `[medium]` `[patch]` Both new dependency tests passed vacuously on an emptied `CORE_INSTRUMENTATION`, and one assertion message actively invited the edit ("take it out of that set"). Added the non-empty guard `tests/unit/test_suite_policy.py` already applies to its own exemption table. Verified by mutation: emptying the frozenset now fails the gate.
  - `[medium]` `[patch]` `misplaced` was computed from a name-keyed `{declaration.name: declaration}` mapping, which keeps only the last occurrence — so a package declared in *both* `[dependencies]` and a conditional table survived on file order alone, and a conditional duplicate written above `[dependencies]` would never have been examined. Now walks every declaration, with the reason recorded in the docstring.
  - `[low]` `[patch]` The `CORE_INSTRUMENTATION` comment claimed `configure_telemetry` "attaches the OTLP exporter … unconditionally"; `telemetry.py` attaches a `BatchSpanProcessor` only when the resolved exporter is `otlp` (Story 6.3's behaviour). Corrected, and the real reason the exporter package is core — `OTLPSpanExporter` is imported at that module's top level, so it is needed to import `configure_telemetry` at all — written in its place.
  - `[low]` `[patch]` The docs paragraph opened "Two guards keep this from regressing" and then named three.
  - `[low]` `[patch]` `TRACE_ID_HEX_LEN` was declared and then bypassed twelve lines later by a hardcoded `'032x'`.
  - `[low]` `[patch]` The module docstring said the span-existence assertion "is not repeated here" while all three tests opened with one. Reworded to say why it is repeated: reading a span's contents requires having one, and a bare `IndexError` is a worse failure than a sentence naming the environment cause.

## Dev Agent Record

### Agent Model Used

`claude-opus-5[1m]` via `bmad-dev-auto`.

### Debug Log References

- `pixi run -e dev python -m pytest tests/integration/test_asgi_tracing.py tests/unit/test_dependency_policy.py tests/unit/test_observability_init.py -q` — 47 passed.
- `pixi run ci` — exit 0. **1551 passed, total coverage 97.04%** (floor 90).
- Two mutation probes, both reverted:
  - `METHOD_ATTRIBUTES` replaced with a bogus key, to read the real span's attribute set out of the failure rather than trust a reading of the installed source.
  - `opentelemetry-instrumentation-asgi` moved from `[dependencies]` into `[feature.dev.dependencies]` in `pixi.toml`. **Both** new dependency tests failed, naming the offending table; `pixi.toml` was restored with `git checkout --` and re-verified clean.
- No PostgreSQL run. This project's rule is that schema changes and tests persisting externally-supplied values need a real PG17 run before the sqlite gate is trusted; this story adds neither. The one route it drives is an anonymous `GET` of `account_login`, which writes nothing.
- **Corrected after the PR's CI gate failed on PostgreSQL 17.** The skip reasoning above was wrong: the route writes nothing, but driving `config.asgi.application` inside a `django_db` test fires `request_started` -> `close_old_connections`, which closes the non-autocommit test connection, so `account_login`'s first query 500s. sqlite hid it because Django never closes an in-memory database. `drive_asgi` now detaches that handler for the drive, as `django.test.Client` does. Reproduced on PG17 (3 failed), fixed (1551 passed, 97.04%). Any test that drives the ASGI callable into a view that queries needs a PG run.

### Completion Notes List

1. **The frozen spec was reconciled against the tree before implementation, and the reconciliation is the substantive part of this story.** Three of its claims had gone stale:
   - **Every line number had moved.** `pixi.toml:58-66` is now `:118-131` (the `-asgi` rationale comment is at `:124-127`); `docs/observability.md:90-104` is now `:111-123` and the file is 193 lines, not 180.
   - **The fixture names were predictions, not the names Story 6.1 shipped.** The spec expected a session-scoped `otel_tracing` plus a function-scoped `spans`. What landed is one fixture, `recorded_spans`, which attaches an `InMemorySpanExporter` to the *live* process-wide provider and restores the processor list on teardown — because `set_tracer_provider` refuses to override and the provider is installed at `config` package import. Nothing here calls `set_tracer_provider` or builds a provider.
   - **AC #2 was not uncovered.** The spec says the span assertion is something "nothing covers today". Story 1.4 had already shipped `tests/integration/test_asgi_request_path.py::TestAsgiRequestsAreStillTraced`, which drives `config.asgi.application` with a raw scope and asserts a `SpanKind.SERVER` span and the resolved-route span name. The real remaining gap was narrower and is what this story built: the span's **content** (method attribute, non-zero trace id) and the **log-to-span agreement on the ASGI path**. `tests/integration/test_log_correlation.py` asserts that agreement only over the WSGI test client, so the two halves could drift apart on the only path a component is actually served on while every existing assertion stayed green.

2. **The spec contradicted itself about how to drive the request, and the Dev Notes won.** Task 3 said `django.test.AsyncClient`; the Dev Notes' AD-16 paragraph then explicitly inverted that instruction, because Story 1.4's deletion of the scope-dispatching wrapper made `config.asgi.application` Django's own `ASGIHandler` — the exact object uvicorn loads — while `AsyncClient` builds an `AsyncClientHandler` subclass of its own. The Dev Notes are the later correction, so the raw-scope driver is what was written.

3. **`drive_asgi` is a fixture in `tests/integration/conftest.py`, not a copied helper.** Writing the module standalone would have made a *third* byte-identical copy of the async scope driver; the deferred-work ledger already records duplicated integration helpers as belonging in the conftest, and Story 6.1 hoisted `recorded_spans` there for the same reason. `tests/integration/test_asgi_request_path.py` was deliberately **not** rewritten to use it — that file is Story 1.4's and changing it is not this story's change, so its own copy of the driver stands. `_span_absence_hint()` *is* duplicated into the new module, matching the convention `conftest.py` records for predicates used inside assertion messages.
   One deviation from the spec's wording: `drive_asgi` `return`s the closure rather than `yield`ing it. There is no teardown, so a generator fixture would have been a bare `yield` with nothing after it.

4. **The HTTP-method attribute key was determined empirically, not from the source reading.** The spec directs choosing the key by reading what the installed instrumentor emits. Reading `opentelemetry/instrumentation/_semconv.py:361-364` says `_StabilityMode.DEFAULT` writes the old `http.method`; the probe confirmed it. The `SERVER` span is named `GET accounts/login/` and carries `http.flavor, http.host, http.method, http.route, http.scheme, http.server_name, http.status_code, http.target, http.url, net.host.port, net.peer.ip, net.peer.port` — **`http.method`**, with `http.request.method` absent. The assertion still accepts either spelling and names both plus `OTEL_SEMCONV_STABILITY_OPT_IN` in the failure, so setting that variable reads as a convention change rather than as a vanished span.

5. **`opentelemetry-instrumentation-psycopg` was added to the asserted core set beyond the five the spec listed.** `PsycopgInstrumentor().instrument()` sits at `core` in `telemetry.py` beside `DjangoInstrumentor().instrument()`, so leaving its package out of `CORE_INSTRUMENTATION` would have left one of the two unconditional instrumentor calls unguarded. `-celery` and `-redis` are deliberately excluded, with the reason written into the constant block: AD-24 expects exactly those two to become feature-owned regions, so asserting them would fail the gate on the day Epic 7 does what the spine says.

6. **"All six combinations" is discharged structurally, and the tests say so in their docstrings.** The six pre-locked environments do not exist yet — `pixi.toml` declares `default` and `dev`, and Epic 8 adds the matrix — so a test enumerating six environments would assert over something the manifest does not have. `[dependencies]` is the table pixi applies to every environment it can build, so a package declared there is present in all six by construction and in whatever the matrix becomes afterwards. The second test covers `[target.<platform>.dependencies]` as well as `[feature.*]`, because that idiom is live in this manifest (`gunicorn` and `uvicorn-worker` are declared that way) and a fixed-path reader would miss a package moved there.

7. **No production source was changed.** `src/config/observability/telemetry.py`, `src/config/asgi.py` and every `pixi.toml` dependency declaration are byte-identical to `4100868`, as the spec's Source Tree table directs. This story is assertions and documentation only.

### File List

**Modified**

- `tests/unit/test_dependency_policy.py` — `CORE_INSTRUMENTATION` and the placement constants, plus the two AC #1 tests.
- `tests/integration/conftest.py` — `_http_scope()`, `_drive_scope()` and the `drive_asgi` fixture. `pytest_collection_modifyitems`, `_sdk_is_disabled` and `recorded_spans` untouched.
- `tests/unit/test_observability_init.py` — the `_is_asgi_supported` assertion gained a message naming the silent-no-span consequence and both uvicorn paths. The four `TestReadDotEnv` cases untouched.
- `docs/observability.md` — the ASGI warning block now names all three guards and what each defends.

**Added**

- `tests/integration/test_asgi_tracing.py` — `core`. AC #2's method-attribute, non-zero-trace-id and log-to-span agreement assertions, over `account_login`, driven through `config.asgi.application`.

**Deliberately unchanged**

- `src/config/observability/telemetry.py`, `src/config/asgi.py`, `pixi.toml`, `tests/integration/test_asgi_request_path.py`.

## Auto Run Result

Status: `done`

### Summary of implemented change

FR-47 / SC-7. AC #1's "present in all six combinations" half is now asserted structurally: the
immovable-core OpenTelemetry set is proven to sit in `pixi.toml`'s unconditional `[dependencies]`
table and in no `[feature.*]` or `[target.*]` table, which is what makes "all six" true rather than
assumed while Epic 8's six environments do not yet exist. AC #1's "active" half gained an explicit
failure message naming the consequence it guards — `_is_asgi_supported is False` means the Django
instrumentor's middleware returns early for every ASGI request and produces no span **and no
warning**. AC #2's span assertion, which Story 1.4 had already partly built, was completed with what
it lacked: the HTTP-method attribute, a non-zero trace id, the three SC-7 identifiers on the log
line, and the agreement between that line's `trace_id` and the span's — all driven through
`config.asgi.application`, the object uvicorn loads, on the `account_login` route. No production
source changed.

### Files changed

- `tests/unit/test_dependency_policy.py` — `CORE_INSTRUMENTATION` and two AC #1 placement tests; `-celery` and `-redis` deliberately excluded, with AD-24 as the recorded reason.
- `tests/integration/conftest.py` — `_http_scope()`, `_drive_scope()` and the `drive_asgi` fixture; `config.asgi` imported at module scope so `django.setup()`'s logging reconfiguration cannot land inside a `caplog` window.
- `tests/integration/test_asgi_tracing.py` — **new**, `core`. AC #2's method-attribute, trace-id and log-agreement assertions.
- `tests/unit/test_observability_init.py` — the `_is_asgi_supported` assertion gained its consequence message.
- `docs/observability.md` — the ASGI warning block names all three guards and what each defends.
- `_bmad-output/implementation-artifacts/deferred-work.md` — five entries.

### Review findings breakdown

Three reviewers (adversarial, edge-case, verification-gap) ran in parallel against the diff.
**11 patches applied** (2 high, 5 medium, 4 low) — the two high ones were assertions that could not
fail: an order-dependent `caplog` wipe, and three tests that discarded the driver's response and so
passed on a 404. **5 deferred**, **11 rejected**. No intent gaps, no spec repairs, no loopbacks
(`review_loop_iteration` 0).

### Verification performed

- `pixi run ci` — **exit 0. 1551 passed, total coverage 97.04%** (floor 90). Pre-commit, build,
  typecheck (74 source files, no issues) and lint all clean.
- Four mutation probes, each reverted and re-verified:
  - `opentelemetry-instrumentation-asgi` moved into `[feature.dev.dependencies]` → both new dependency tests failed, naming the table.
  - `CORE_INSTRUMENTATION` emptied → the placement test failed on the new non-empty guard.
  - the three tracing tests repointed at `/no-such-page/` → all three failed on the new status assertion; before the patch, none did.
  - `METHOD_ATTRIBUTES` replaced with a bogus key → read the real span's attribute set out of the failure, confirming **`http.method`** (old semconv, `_StabilityMode.DEFAULT`) with `http.request.method` absent.
- `TestTheAsgiRequestsLogLineNamesTheSameTrace` run in isolation — failed before the import hoist, passes after.
- No PostgreSQL run: this project requires one for schema changes and for tests persisting externally-supplied values. This story adds neither; the single route it drives is an anonymous `GET`.
- **Corrected after the PR's CI gate failed on PostgreSQL 17.** The skip reasoning above was wrong: the route writes nothing, but driving `config.asgi.application` inside a `django_db` test fires `request_started` -> `close_old_connections`, which closes the non-autocommit test connection, so `account_login`'s first query 500s. sqlite hid it because Django never closes an in-memory database. `drive_asgi` now detaches that handler for the drive, as `django.test.Client` does. Reproduced on PG17 (3 failed), fixed (1551 passed, 97.04%). Any test that drives the ASGI callable into a view that queries needs a PG run.

### Residual risks

- The `>=0.65b0` instrumentation pins are open-ended and nothing asserts the Django and ASGI instrumentors resolve to the same series. Once Epic 8 solves six environments independently they can drift per-combination — deferred, because the right cap on a beta-versioned line is a judgment call.
- `CORE_INSTRUMENTATION` is reconciled against no source, so a fifth unconditional instrumentor added to `telemetry.py` would go unguarded. Deferred until Epic 7's region markers make an audit able to tell `core` calls from feature-owned ones.
- `tests/integration/conftest.py` now carries a second copy of the ASGI scope driver that `test_asgi_request_path.py` structurally cannot adopt; deferred, since widening it means rewriting a file this story had no mandate over.
- `docs/observability.md` is pinned by no test, so the guard claims added to it can rot.

### Follow-up review recommendation

`true`. Two high-severity findings were assertions that could not fail, and the pass changed the
shape of all three new tests plus both dependency tests. The result is green and mutation-probed,
but the volume and consequence of the review-driven changes are enough that an independent pass over
them is worth its cost.
