# Story 3.6: Observability is not substituted locally

Status: ready-for-dev

## Story

As a developer working on a generated component,
I want the same observability code running locally that runs deployed,
so that telemetry is the one capability I cannot accidentally work without.

## Acceptance Criteria

**Traceability:** FR-21 · CG-4

1. **Given** no OTLP endpoint is configured
   **When** the component runs locally
   **Then** the tracer provider is still installed, all instrumentors still instrument, and spans are still created and ended
   **And** `trace_id` and `span_id` still reach every log line
   **And** spans are discarded at the processor

2. **Given** `OTEL_TRACES_EXPORTER=console`
   **When** the component runs
   **Then** spans are written to stdout
   **And** nothing else about the behaviour changes

3. **Given** an unreachable endpoint
   **When** the local configuration is inspected
   **Then** no batch processor is attached to an exporter pointed at it
   **And** no retry cycle floods stderr through a test run

## Tasks / Subtasks

- [ ] Task 1: Establish that there is no local substitution to remove (AC: #1)
  - [ ] Read `src/config/observability/telemetry.py` end to end. Its module docstring already states the property this story is making enforceable: "Tracing is always wired in; only *export* is conditional." `configure_telemetry` (`:104-140`) installs a `TracerProvider`, attaches a processor only when an exporter is resolved, sets the global tracer provider, and then instruments Django, Celery, psycopg and redis unconditionally at `:134-137`.
  - [ ] Confirm no settings module, no pixi task and no entry point disables telemetry locally: `src/config/settings/{base,local,test,production}.py` set no `OTEL_*` variable; `[activation.env]` in `pixi.toml` sets only `COVERAGE_CORE`. Record the confirmation in the story's Completion Notes.
  - [ ] Do **not** add a local opt-out, an `if DEBUG` guard around instrumentation, or a `OTEL_SDK_DISABLED` default. `OTEL_SDK_DISABLED` being true is an unconditional stage-1 refusal condition in a deployed component (FR-13), and defaulting it anywhere is what would make that refusal fire on every component.

- [ ] Task 2: Make the discard-at-the-processor property explicit (AC: #1, #3)
  - [ ] `resolve_traces_exporter()` (`:87-101`) returns `NONE` when `OTEL_TRACES_EXPORTER` is unset and no endpoint is configured, and `configure_telemetry` then attaches no span processor at all. Add a comment at the branch recording that "no processor attached" is how spans are discarded: they are created, they end, and their `SpanContext` is live for the duration — which is what keeps `trace_id` on the log line — and nothing exports them.
  - [ ] Add a small public predicate to `telemetry.py`, `def has_span_processor(provider: TracerProvider) -> bool`, or expose the resolved exporter from `configure_telemetry`'s return path, so a test can assert "no batch processor is attached" over the object rather than by re-deriving the environment logic. Asserting the same `os.environ` reads twice proves nothing.

- [ ] Task 3: Stop reading `DJANGO_ENV` for the deployment-environment resource attribute (AC: #2)
  - [ ] `build_resource()` (`:68-84`) sets `"deployment.environment": os.environ.get("DJANGO_ENV", "local")`. This violates the spine's Consistency Conventions, which state that component-level runtime facts are `COMPONENT_`-prefixed and "Never `DJANGO_ENV` or a bare `ENV` — the platform is likely to set a generic `ENV=dev` for a development *deployment*, and a deployed dev environment is still deployed." It also defaults to reporting `local` from a deployed component that never sets the variable, which is the fail-open inversion AD-13 exists to prevent.
  - [ ] Replace the read with `config.locality.is_local()` (Story 3.1): `"deployment.environment": "local" if is_local() else "deployed"`. `config.observability` importing `config.locality` keeps the composition root's internal direction intact and adds no new dependency.
  - [ ] Update `tests/unit/test_telemetry.py`'s `OTEL_VARS` tuple (`:23-30`), which currently includes `"DJANGO_ENV"`, and any assertion that depends on it.
  - [ ] Scope note: this is the AD-13 environment-variable convention, not an Epic 6 observability change. Do not extend the edit into exporter behaviour, span attributes, or the instrumentor set — those are Epic 6's (FR-45, NFR-6).

- [ ] Task 4: Tests for the unsubstituted local path (AC: #1, #2, #3)
  - [ ] Extend `tests/unit/test_telemetry.py` (UPDATE), reusing its `_clean_otel_env` fixture (`:33-40`, which unsets every `OTEL_*` variable and calls `reset_telemetry_for_testing()` before and after) and its `no_side_effects` fixture (`:43+`, which patches the four instrumentor classes and the global provider).
    - [ ] `test_provider_is_installed_with_no_endpoint_configured`: with nothing set, assert `configure_telemetry()` returns `True` and a `TracerProvider` was set.
    - [ ] `test_all_instrumentors_instrument_with_no_endpoint_configured`: assert all four of Django, Celery, psycopg and redis were instrumented. Instrumentation must not be conditional on export — AD-24's worked failure is a missed region "leaving `CeleryInstrumentor().instrument()` in eight combinations whose environment no longer contains the instrumentor", and the mirror-image mistake is skipping instrumentation because nothing is being exported.
    - [ ] `test_no_processor_is_attached_when_nothing_is_configured`: assert via Task 2's predicate that the provider carries no span processor.
    - [ ] `test_unreachable_endpoint_is_not_a_configuration_this_code_produces`: with `OTEL_TRACES_EXPORTER` unset and no endpoint, assert `resolve_traces_exporter()` is `NONE` — i.e. the code never attaches a `BatchSpanProcessor` to an `OTLPSpanExporter` with no endpoint to point it at.
    - [ ] `test_console_exporter_attaches_a_simple_processor`: with `OTEL_TRACES_EXPORTER=console`, assert a `SimpleSpanProcessor` over a `ConsoleSpanExporter` is attached and that the instrumentor set and the resource are byte-for-byte the same as in the unset case — "nothing else about the behaviour changes."
    - [ ] `test_deployment_environment_follows_locality`: with `COMPONENT_RUNTIME=local` assert `local`; with it unset assert `deployed`; assert `DJANGO_ENV` no longer influences the resource.
  - [ ] Create `tests/integration/test_local_trace_correlation.py` (NEW), `@pytest.mark.integration` on every test: with no OTLP endpoint configured, issue a request through the Django test client against an existing view and assert that a span was created and ended and that the emitted log records carry both `trace_id` and `span_id`. Capture structlog output with `structlog.testing.capture_logs` or a `LogCapture` processor; assert over the captured event dictionaries, not over stdout text.
    - [ ] `src/config/observability/logging.py:29-54` (`add_otel_context`) is what puts `trace_id` and `span_id` into the event dict when a span is active, and it is included by `shared_processors()` (`:57`). Assert the behaviour, not the processor's presence in a list.
  - [ ] `test_no_retry_output_during_a_run`: assert that a full local run emits no OTLP exporter retry/connection-error records — assert over captured log records for the OpenTelemetry exporter logger rather than by scraping stderr.

- [ ] Task 5: Document the non-substitution (AC: #1, #2)
  - [ ] `docs/development.md`'s `## Running with no external services` section already states "Observability is the exception: it is not substituted at all." Extend it with the three testable consequences: the provider and instrumentors are installed with no endpoint configured, spans are discarded at the processor, and `OTEL_TRACES_EXPORTER=console` prints them to stdout without changing anything else.
  - [ ] `docs/observability.md` already carries a `### Why export is conditional` subsection (`:51`). Reconcile the two so they say the same thing, and cross-link rather than duplicating.

## Dev Notes

### Architecture Constraints

**FR-21 — Observability is not substituted locally.** "Local development runs the same observability code the deployed component runs; only the terminal export step is absent." Testable consequences, verbatim:

> - With no OTLP endpoint configured, the tracer provider is still installed, all instrumentors still instrument, spans are still created and ended, and `trace_id` and `span_id` still reach every log line. Spans are discarded at the processor.
> - `OTEL_TRACES_EXPORTER=console` sends spans to stdout without other behavioural change.
> - No configuration attaches a batch processor to an exporter pointed at an unreachable endpoint — that retries every cycle and floods stderr through every test run.

**CG-4 — Do not substitute a capability that could run locally as deployed.** "A substitution is warranted only where the deployed dependency genuinely cannot be present on a developer's machine without becoming the service dependency this contract exists to remove. Each one widens the parity gap the product already trades knowingly, and each must be guarded by a refusal. The count is not the constraint — the principle is." Telemetry is the capability that fails this test: nothing about running the SDK locally requires a collector, so nothing is substituted. This story's job is to make that structural rather than incidental.

**Consistency Conventions — environment variables.** "`COMPONENT_`-prefixed for component-level runtime facts, and never in `[activation.env]` (AD-13). Never `DJANGO_ENV` or a bare `ENV` — the platform is likely to set a generic `ENV=dev` for a development *deployment*, and a deployed dev environment is still deployed." Task 3 exists because `telemetry.py` currently violates this.

**Consistency Conventions — logging.** "Structured, JSON to stdout, carrying `request_id`, `trace_id`, `span_id`. Every authorization change emits an event. No files, no rotation." Never `print()`, never stdlib `logging` — `structlog` only.

**AD-24 — no conditional imports, no `try/except ImportError`.** `telemetry.py` is one of the three known region-bearing `core` paths, cited at `:134-137` for the per-instrumentor calls. This story adds no markers and removes no instrumentor. If an instrumentor import needs to become conditional for a combination that lacks the package, that is a declared feature-owned region in Epic 7 — never a `try/except ImportError` here.

**FR-13 — `OTEL_SDK_DISABLED` true is an unconditional stage-1 refusal.** `_is_disabled()` (`:40-52`) reads it. Do not set it anywhere, do not default it, and do not add a local convenience that sets it to quiet the suite.

**Scope boundary.** Epic 6 owns FR-45 (the OTLP export path end to end against a collector stub — an ownerless open item in the spine), NFR-6 (telemetry-overhead measurement) and FR-48 (visible cache degradation). This story owns only the local non-substitution property. Do not build a collector stub here.

**R-5.** Local telemetry proves the instrumentation is installed and the correlation works. It proves nothing about the export path, which local development never exercises — that gap is precisely why FR-45 exists.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/observability/telemetry.py` | UPDATE | Comment the discard-at-the-processor branch; add `has_span_processor` (or an equivalent inspectable return) for Task 2; replace the `DJANGO_ENV` read in `build_resource` with `config.locality.is_local()`. |
| `tests/unit/test_telemetry.py` | UPDATE | Add the six assertions in Task 4; drop `DJANGO_ENV` from `OTEL_VARS` and add `COMPONENT_RUNTIME`. |
| `tests/integration/test_local_trace_correlation.py` | NEW | End-to-end `trace_id` / `span_id` on log lines with no endpoint configured; no retry output. |
| `docs/development.md` | UPDATE | Extend the observability paragraph in `## Running with no external services`. |
| `docs/observability.md` | UPDATE | Reconcile `### Why export is conditional` with the above; cross-link. |

**`src/config/observability/telemetry.py` today (verified, 146 lines).** Module docstring states the always-wired/conditionally-exported property and names the flood-stderr failure it avoids. `DEFAULT_SERVICE_NAME = "django-15-factor-base"` at `:31`; `OTLP` / `CONSOLE` / `NONE` constants at `:33-35`; module-level `_configured` guard at `:37`. `_is_disabled()` `:40-52` reads `OTEL_SDK_DISABLED` against `{"true","1","yes"}`. `_has_otlp_endpoint()` `:55-65` checks `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`. `build_resource()` `:68-84` — **the `DJANGO_ENV` read is at `:80`**. `resolve_traces_exporter()` `:87-101`. `configure_telemetry()` `:104-140`: returns `False` when already configured or disabled; builds the provider; attaches `BatchSpanProcessor(OTLPSpanExporter())` for `otlp`, `SimpleSpanProcessor(ConsoleSpanExporter())` for `console`, **nothing for `none`**; sets the global provider; then instruments Django, Celery, psycopg, redis at `:134-137`. `reset_telemetry_for_testing()` `:143-146`. **Preserve:** the idempotence guard, the four instrumentor calls as a contiguous block, and `reset_telemetry_for_testing` (the existing test fixture depends on it).

**`src/config/observability/logging.py` today (verified).** `add_otel_context` at `:29-54` writes `trace_id` (32 hex) and `span_id` (16 hex) into the event dict when a span context is present; `shared_processors()` at `:57`; `configure_structlog()` at `:74`; `resolve_log_format()` at `:95`; `build_logging_config()` at `:138`. `src/config/settings/base.py:282-287` builds `LOGGING` and calls `configure_structlog()` at settings-import time.

**`tests/unit/test_telemetry.py` today (verified).** Module docstring explains why instrumentors and the global provider are patched out. `OTEL_VARS` at `:23-30` lists the six variables the `_clean_otel_env` autouse fixture (`:33-40`) unsets, including `DJANGO_ENV`. `no_side_effects` (`:43+`) patches `DjangoInstrumentor`, `CeleryInstrumentor`, `PsycopgInstrumentor` and `RedisInstrumentor` on the module.

**`src/config/observability/__init__.py` today (verified).** `configure_observability()` at `:62-73` calls `read_dot_env()` then `configure_telemetry()`; it is the single call each entry point makes (`manage.py:29-31`, `src/config/celery_app.py:12`, and the WSGI/ASGI entry points).

### Testing Requirements

- Unit tests extend `tests/unit/test_telemetry.py` and must keep using its `no_side_effects` fixture where instrumentation is asserted — instrumenting Django, Celery, psycopg and redis for real would apply for the whole session and leak into every later test.
- `tests/integration/test_local_trace_correlation.py` carries `@pytest.mark.integration` on every test and leaves state as found: call `reset_telemetry_for_testing()` in teardown and restore any tracer provider it installed.
- Assert over captured structlog event dictionaries, never over raw stdout text. `src/config/settings/test.py:15` already configures console rendering at `WARNING` for the suite; scraping that output is brittle.
- The "no retry cycle" assertion must be an assertion, not an observation — capture the OpenTelemetry exporter logger's records and assert emptiness.
- Coverage floor: ninety percent including templates (AD-20), `COVERAGE_CORE=ctrace` in force (set in `[activation.env]`, which `tests/unit/test_locality_declaration.py` from Story 3.1 must continue to allow — `COVERAGE_CORE` is not a `COMPONENT_*` variable and is unaffected by that assertion).
- Test disposition: `core`.
- Run with `pixi run test` / `pixi run test-integration`; `pixi run ci` must exit 0.

#### Project Structure Notes

Aligned with the Structural Seed: `src/config/observability/` is the "existing cross-cutting home" and this story stays inside it. The one new import — `config.observability.telemetry` importing `config.locality` — is within the composition root and creates no cross-territory edge; AD-4 constrains `config` → `django_service` → tenant, and this is neither.

`src/config/websocket.py` is still present in the tree and still carries a `[tool.coverage.run] omit` entry at `pyproject.toml:168`. AD-16 requires the module, the scope-dispatching wrapper and the omit entry to be deleted together — that is **Epic 1's** work, not this story's. Do not touch it here.

### References

- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-21] — the three testable consequences.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#CG-4]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — environment variables; logging; feature-conditional code.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13] · [#AD-24] · [#AD-16] · [#AD-20]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Open Items] — FR-45's collector stub is ownerless and is Epic 6's, not this story's.
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.6] · [Source: _bmad-output/planning-artifacts/epics.md#Epic 6]
- [Source: src/config/observability/telemetry.py:1-146] · [Source: src/config/observability/logging.py:29-57] · [Source: src/config/observability/__init__.py:62-73]
- [Source: tests/unit/test_telemetry.py:1-50] · [Source: docs/observability.md:51] · [Source: docs/development.md#Running with no external services] · [Source: pyproject.toml:160-178]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
