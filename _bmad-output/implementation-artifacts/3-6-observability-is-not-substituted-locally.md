---
baseline_revision: 8284984
review_loop_iteration: 0
status: done
followup_review_recommended: true
final_revision: 368b8a2
warnings: [oversized]
---

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

- [x] Task 1: Establish that there is no local substitution to remove (AC: #1)
  - [x] Read `src/config/observability/telemetry.py` end to end. Its module docstring already states the property this story is making enforceable: "Tracing is always wired in; only *export* is conditional." `configure_telemetry` (`:103-146`) installs a `TracerProvider`, attaches a processor only when an exporter is resolved, sets the global tracer provider, and then instruments Django, Celery, psycopg and redis unconditionally at `:140-143`.
  - [x] Confirm no settings module, no pixi task and no entry point disables telemetry locally: `src/config/settings/{base,local,test,production}.py` set no `OTEL_*` variable; `[activation.env]` in `pixi.toml` sets only `COVERAGE_CORE`. Record the confirmation in the story's Completion Notes.
  - [x] Do **not** add a local opt-out, an `if DEBUG` guard around instrumentation, or a `OTEL_SDK_DISABLED` default. `OTEL_SDK_DISABLED` being true is an unconditional stage-1 refusal condition in a deployed component (FR-13), and defaulting it anywhere is what would make that refusal fire on every component.

- [x] Task 2: Make the discard-at-the-processor property explicit (AC: #1, #3)
  - [x] `resolve_traces_exporter()` (`:86-100`) returns `NONE` when `OTEL_TRACES_EXPORTER` is unset and no endpoint is configured, and `configure_telemetry` then attaches no span processor at all. Add a comment at the branch recording that "no processor attached" is how spans are discarded: they are created, they end, and their `SpanContext` is live for the duration — which is what keeps `trace_id` on the log line — and nothing exports them.
  - [x] Add a small public predicate to `telemetry.py`, `def has_span_processor(provider: TracerProvider) -> bool`, so a test can assert "no batch processor is attached" over the object rather than by re-deriving the environment logic. Asserting the same `os.environ` reads twice proves nothing. The alternative the 2026-08-15 draft offered — widening `configure_telemetry`'s return — is rejected: its `bool` return is the contract `configure_observability` (`__init__.py:73`) forwards and six existing tests assert on.
  - [x] The SDK exposes no public accessor for the attached processors, so the predicate reads `provider._active_span_processor` and its `_span_processors` tuple behind a `# noqa: SLF001`. That is the same private reach `tests/integration/test_asgi_request_path.py:196-200` already takes for the same reason; add the same one-line justification comment. Add `has_span_processor` to nothing else — it has no `__all__` to join (`telemetry.py` declares none) and must not be re-exported from `config.observability.__init__`, whose `__all__` (`:21-29`) is the entrypoint surface.
  - [x] `no_side_effects` (`tests/unit/test_telemetry.py:43-58`) currently patches `telemetry.trace.set_tracer_provider` to `lambda provider: None`, which throws the built provider away and leaves the predicate nothing to inspect. Split the capture out: a new `installed_provider` fixture patches `set_tracer_provider` to append to a list and returns it; `no_side_effects` depends on `installed_provider` and still returns the instrumented-name list, so all six existing tests keep their current signatures and assertions.

- [x] Task 3: Stop reading `DJANGO_ENV` for the deployment-environment resource attribute (AC: #2)
  - [x] `build_resource()` (`:67-83`) sets `"deployment.environment": os.environ.get("DJANGO_ENV", "local")` at `:79`. This violates the spine's Consistency Conventions, which state that component-level runtime facts are `COMPONENT_`-prefixed and "Never `DJANGO_ENV` or a bare `ENV` — the platform is likely to set a generic `ENV=dev` for a development *deployment*, and a deployed dev environment is still deployed." It also defaults to reporting `local` from a deployed component that never sets the variable, which is the fail-open inversion AD-13 exists to prevent.
  - [x] Replace the read with `config.locality.is_local()` (Story 3.1): `"deployment.environment": "local" if is_local() else "deployed"`. `config.observability` importing `config.locality` keeps the composition root's internal direction intact and adds no new dependency.
  - [x] Update `tests/unit/test_telemetry.py`'s `OTEL_VARS` tuple (`:23-30`), which currently includes `"DJANGO_ENV"` (`:29`): drop that name and add `"COMPONENT_RUNTIME"`. Rename the tuple `SCRUBBED_VARS` and its autouse fixture `_clean_otel_env` -> `_clean_env`; a tuple called `OTEL_VARS` holding `COMPONENT_RUNTIME` misnames itself, and neither name is referenced outside the module.
  - [x] Two tests depend on it, not one. `test_environment_overrides` (`:100-106`) sets `DJANGO_ENV=production` and asserts `deployment.environment == "production"`; it is replaced by Task 4's `test_deployment_environment_follows_locality`, keeping its `OTEL_SERVICE_NAME` and `service.version` assertions. `test_default_service_name` (`:95-98`) asserts `"local"` and passes today only because the suite runs in the `dev` pixi environment, which exports `COMPONENT_RUNTIME=local` (`pixi.toml:435-436`); once the fixture scrubs that variable the hermetic answer is `"deployed"`, and that is what it must assert.
  - [x] Accept the granularity loss and record it. `DJANGO_ENV` carried a free-text tier name, so `deployment.environment` could read `staging` or `production`; `is_local()` is boolean and collapses every deployed tier to `"deployed"`. That is the AD-13 trade being made deliberately — a fail-open `local` from an undeclared deployment is the defect — but it is a visible change to an exported resource attribute, so `docs/observability.md:47` is rewritten rather than retitled (Task 5).
  - [x] Scope note: this is the AD-13 environment-variable convention, not an Epic 6 observability change. Do not extend the edit into exporter behaviour, span attributes, or the instrumentor set — those are Epic 6's (FR-45, NFR-6) — and do not touch `DEFAULT_SERVICE_NAME` at `:31`, which AD-25 names as a declared parameterization site owned by Epic 7.

- [x] Task 4: Tests for the unsubstituted local path (AC: #1, #2, #3)
  - [x] Extend `tests/unit/test_telemetry.py` (UPDATE), reusing its autouse env-scrubbing fixture (`:33-40`, which unsets the listed variables and calls `reset_telemetry_for_testing()` before and after) and its `no_side_effects` fixture (`:43-58`, which patches the four instrumentor classes and the global provider), as amended by Tasks 2 and 3.
    - [x] `test_provider_is_installed_with_no_endpoint_configured`: with nothing set, assert `configure_telemetry()` returns `True` and a `TracerProvider` was set.
    - [x] `test_all_instrumentors_instrument_with_no_endpoint_configured`: assert all four of Django, Celery, psycopg and redis were instrumented. Instrumentation must not be conditional on export — AD-24's worked failure is a missed region "leaving `CeleryInstrumentor().instrument()` in eight combinations whose environment no longer contains the instrumentor", and the mirror-image mistake is skipping instrumentation because nothing is being exported.
    - [x] `test_no_processor_is_attached_when_nothing_is_configured`: assert via Task 2's predicate, over `installed_provider[0]`, that the provider carries no span processor. This **replaces** `test_no_processor_without_an_endpoint` (`:146-159`) rather than joining it: that test patches `TracerProvider.add_span_processor` and counts calls, which mocks the very attachment the property is about. Keep its docstring — "The whole point: no collector means no retrying exporter."
    - [x] `test_unreachable_endpoint_is_not_a_configuration_this_code_produces`: with `OTEL_TRACES_EXPORTER` unset and no endpoint, assert `resolve_traces_exporter()` is `NONE` — i.e. the code never attaches a `BatchSpanProcessor` to an `OTLPSpanExporter` with no endpoint to point it at.
    - [x] `test_console_exporter_attaches_a_simple_processor`: with `OTEL_TRACES_EXPORTER=console`, assert a `SimpleSpanProcessor` over a `ConsoleSpanExporter` is attached, and that the instrumentor set and the resource are the same as in the unset case — "nothing else about the behaviour changes." This **replaces** `test_console_exporter_registers_a_processor` (`:131-144`) for the same reason as above. Compare resources with `build_resource() == build_resource()` under each setting rather than "byte-for-byte": `Resource` defines `__eq__` over its attributes and schema URL, and `Resource.create` merges SDK-detected attributes that no serialization of ours would reproduce. Do not let this case reach the `otlp` branch — `BatchSpanProcessor` starts an exporter thread, and no unit test here configures an endpoint.
    - [x] `test_deployment_environment_follows_locality`: with `COMPONENT_RUNTIME=local` assert `local`; with it unset assert `deployed`; with `COMPONENT_RUNTIME` unset **and** `DJANGO_ENV=production` set, assert `deployed` — proving the old variable no longer influences the resource. This is the replacement for `test_environment_overrides`.
  - [x] Create `tests/integration/test_local_trace_correlation.py` (NEW), `pytestmark = [pytest.mark.integration, pytest.mark.django_db]`: with no OTLP endpoint configured, issue `client.get(reverse("home"))` (`src/config/urls.py:24`, the established 200 route) and assert that a span was created and ended and that the emitted log records carry both `trace_id` and `span_id`.
    - [x] **Do not use `structlog.testing.capture_logs`.** It installs its own processor chain, which drops `merge_contextvars` *and `add_otel_context` itself* — so `trace_id` and `span_id` could never appear in what it captures, and the test would assert the absence of the property it exists to prove. Use `caplog` and read `record.msg`, which is the structlog event dict because `configure_structlog()` ends the chain in `wrap_for_formatter`. `tests/integration/test_request_logging.py:1-11` records this exact reasoning and `:33-47` gives the `_events(caplog, name)` / `caplog.at_level(logging.INFO, logger="django_structlog")` idiom to reuse.
    - [x] Read the spans from the **live process-wide provider** rather than installing one: `config/__init__.py:3` imports `config.celery_app`, which calls `configure_observability()` at module scope, so the provider and all four instrumentors are already installed by the time any test runs, and `trace.set_tracer_provider` refuses to override. Reuse the `recorded_spans` fixture idiom at `tests/integration/test_asgi_request_path.py:190-228` verbatim in shape: assert the installed provider is an SDK `TracerProvider`, attach a `SimpleSpanProcessor(InMemorySpanExporter())`, yield the exporter, and in `finally` restore the original `_span_processors` tuple, shut the processor down and clear the exporter. `get_finished_spans()` is the created-and-ended assertion in one call.
    - [x] Assert, never skip. `tests/unit/test_suite_policy.py:46,50` bans `pytest.mark.skip/skipif/xfail` and `pytest.skip`/`pytest.xfail`/`pytest.importorskip` in every test module, and this file is not among the counted exemptions (`:94-97`). When the environment could explain a missing span, name it in the assertion message the way `_span_absence_hint()` (`test_asgi_request_path.py:85-98`) does — `OTEL_SDK_DISABLED` and a suppressing `OTEL_TRACES_SAMPLER` are the two causes.
    - [x] `src/config/observability/logging.py:29-54` (`add_otel_context`) is what puts `trace_id` and `span_id` into the event dict when a span is active, and it is included by `shared_processors()` (`:57`). Assert the behaviour, not the processor's presence in a list.
    - [x] `test_no_retry_output_during_a_run`, in the same integration module: assert that a full local run emits no OTLP exporter retry/connection-error records — assert over captured log records rather than by scraping stderr. Capture under `caplog.at_level(logging.WARNING, logger="opentelemetry")`: both emitters propagate to that ancestor — `opentelemetry.exporter.otlp.proto.http.trace_exporter` ("Transient error %s encountered while exporting span batch, retrying in %.2fs.", "Failed to export span batch code: %s, reason: %s") and `opentelemetry.sdk.trace.export` (the `BatchSpanProcessor` side). Assert the filtered record list is empty and include the offending messages in the failure message.

- [x] Task 5: Document the non-substitution (AC: #1, #2)
  - [x] `docs/development.md`'s `## Running with no external services` section already states "Observability is the exception: it is not substituted at all." Extend it with the three testable consequences: the provider and instrumentors are installed with no endpoint configured, spans are discarded at the processor, and `OTEL_TRACES_EXPORTER=console` prints them to stdout without changing anything else.
  - [x] `docs/observability.md` already carries a `### Why export is conditional` subsection (`:51`) whose table (`:57-62`) states all three consequences correctly; `docs/development.md:417` already links to it. Reconcile by making `development.md` state the consequences and keep the link, and by adding to `observability.md` the one thing its table does not say — that instrumentation is installed unconditionally, not merely that export is skipped.
  - [x] `docs/observability.md:47` carries the row `| `DJANGO_ENV` | `local` | Reported as `deployment.environment`. |`. Task 3 makes that false. Replace the row with `COMPONENT_RUNTIME`, give its default as unset, and state the two values `deployment.environment` can now take (`local` / `deployed`) so the granularity change is discoverable by whoever queries on that attribute.
  - [x] `site/` is untracked mkdocs build output and carries a stale copy of the same row; it regenerates on the next build and is not hand-edited.

## Dev Notes

### Architecture Constraints

**FR-21 — Observability is not substituted locally.** "Local development runs the same observability code the deployed component runs; only the terminal export step is absent." Testable consequences, verbatim:

> - With no OTLP endpoint configured, the tracer provider is still installed, all instrumentors still instrument, spans are still created and ended, and `trace_id` and `span_id` still reach every log line. Spans are discarded at the processor.
> - `OTEL_TRACES_EXPORTER=console` sends spans to stdout without other behavioural change.
> - No configuration attaches a batch processor to an exporter pointed at an unreachable endpoint — that retries every cycle and floods stderr through every test run.

**CG-4 — Do not substitute a capability that could run locally as deployed.** "A substitution is warranted only where the deployed dependency genuinely cannot be present on a developer's machine without becoming the service dependency this contract exists to remove. Each one widens the parity gap the product already trades knowingly, and each must be guarded by a refusal. The count is not the constraint — the principle is." Telemetry is the capability that fails this test: nothing about running the SDK locally requires a collector, so nothing is substituted. This story's job is to make that structural rather than incidental.

**Consistency Conventions — environment variables.** "`COMPONENT_`-prefixed for component-level runtime facts, and never in `[activation.env]` (AD-13). Never `DJANGO_ENV` or a bare `ENV` — the platform is likely to set a generic `ENV=dev` for a development *deployment*, and a deployed dev environment is still deployed." Task 3 exists because `telemetry.py` currently violates this.

**Consistency Conventions — logging.** "Structured, JSON to stdout, carrying `request_id`, `trace_id`, `span_id`. Every authorization change emits an event. No files, no rotation." Never `print()`, never stdlib `logging` — `structlog` only.

**AD-24 — no conditional imports, no `try/except ImportError`.** `telemetry.py` is one of the region-bearing `core` paths AD-24 knows about; the set of such paths is **open**, declared as an open `[[regions]]` array, and no count is encoded anywhere. **The regions in this file are not the range `:140-143`.** AD-24 states it explicitly: `:141` (`CeleryInstrumentor().instrument()`) is one single-line `feature:celery` region and `:143` (`RedisInstrumentor().instrument()`) is one single-line `feature:redis` region, **each paired with its import** — `:21` `CeleryInstrumentor` and `:24` `RedisInstrumentor` — while `:140` `DjangoInstrumentor` and `:142` `PsycopgInstrumentor` are `core` and present in every combination. Note that `:141` now carries a trailing `# type: ignore[no-untyped-call]` and that `:131-139` is a comment block explaining it; the marker travels with the line, and the comment block is `core` prose about all four calls. Marking the range as one region strips Django and psycopg instrumentation everywhere, and pruning a call without its import moves the `ImportError` from line 135 to line 21 rather than fixing it. This story adds no markers and removes no instrumentor, but it must not reorder or merge those four calls either: Epic 7's marker pairs are declared against exactly that interleaving. If an instrumentor import needs to become conditional for a combination that lacks the package, that is a declared feature-owned region in Epic 7 — never a `try/except ImportError` here.

**FR-13 — `OTEL_SDK_DISABLED` true is an unconditional stage-1 refusal.** `_is_disabled()` (`:40-52`) reads it. Do not set it anywhere, do not default it, and do not add a local convenience that sets it to quiet the suite.

**Scope boundary.** Epic 6 owns FR-45 (the OTLP export path end to end against a collector stub — an ownerless open item in the spine), NFR-6 (telemetry-overhead measurement) and FR-48 (visible cache degradation). This story owns only the local non-substitution property. Do not build a collector stub here.

**R-5.** Local telemetry proves the instrumentation is installed and the correlation works. It proves nothing about the export path, which local development never exercises — that gap is precisely why FR-45 exists.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/observability/telemetry.py` | UPDATE | Comment the discard-at-the-processor branch; add `has_span_processor` (or an equivalent inspectable return) for Task 2; replace the `DJANGO_ENV` read in `build_resource` with `config.locality.is_local()`. |
| `tests/unit/test_telemetry.py` | UPDATE | Add Task 4's assertions; split an `installed_provider` fixture out of `no_side_effects`; rename `OTEL_VARS` -> `SCRUBBED_VARS`, dropping `DJANGO_ENV` and adding `COMPONENT_RUNTIME`; replace `test_environment_overrides`, `test_console_exporter_registers_a_processor` and `test_no_processor_without_an_endpoint`, and flip `test_default_service_name` to `deployed`. |
| `tests/integration/test_local_trace_correlation.py` | NEW | End-to-end `trace_id` / `span_id` on log lines with no endpoint configured; no retry output. |
| `docs/development.md` | UPDATE | Extend the observability paragraph in `## Running with no external services`. |
| `docs/observability.md` | UPDATE | Replace the `DJANGO_ENV` row at `:47` with `COMPONENT_RUNTIME`; say instrumentation is unconditional in `### Why export is conditional`. |

**`src/config/observability/telemetry.py` today (re-verified at `8284984`, 152 lines — the 2026-08-15 draft measured 146 and every line number below is corrected).** Module docstring `:1-13` states the always-wired/conditionally-exported property and names the flood-stderr failure it avoids. `DEFAULT_SERVICE_NAME = "django-15-factor-base"` at `:31`; `OTLP` / `CONSOLE` / `NONE` constants at `:33-35`; module-level `_configured` guard at `:37`. `_is_disabled()` `:40-52` reads `OTEL_SDK_DISABLED` against `{"true","1","yes"}`. `_has_otlp_endpoint()` `:55-64` checks `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`. `build_resource()` `:67-83` — **the `DJANGO_ENV` read is at `:79`**. `resolve_traces_exporter()` `:86-100`. `configure_telemetry()` `:103-146`: returns `False` when already configured or disabled; builds the provider `:121`; attaches `BatchSpanProcessor(OTLPSpanExporter())` for `otlp` `:125`, `SimpleSpanProcessor(ConsoleSpanExporter())` for `console` `:127`, **nothing for `none`**; sets the global provider `:129`; then instruments Django, Celery, psycopg, redis at `:140-143` behind the comment block `:131-139`. `reset_telemetry_for_testing()` `:149-152`. **Preserve:** the idempotence guard, the four instrumentor calls as a contiguous block in that order with their comment block and `CeleryInstrumentor`'s `# type: ignore[no-untyped-call]`, and `reset_telemetry_for_testing` (the existing test fixture depends on it).

**`src/config/observability/logging.py` today (verified).** `add_otel_context` at `:29-54` writes `trace_id` (32 hex) and `span_id` (16 hex) into the event dict when a span context is present; `shared_processors()` at `:57`; `configure_structlog()` at `:74`; `resolve_log_format()` at `:95`; `build_logging_config()` at `:138`. `src/config/settings/base.py:282-287` builds `LOGGING` and calls `configure_structlog()` at settings-import time.

**`tests/unit/test_telemetry.py` today (re-verified at `8284984`, 159 lines).** Module docstring `:1-8` explains why instrumentors and the global provider are patched out. `OTEL_VARS` at `:23-30` lists the six variables the `_clean_otel_env` autouse fixture (`:33-40`) unsets, including `DJANGO_ENV` at `:29`. `no_side_effects` (`:43-58`) patches `DjangoInstrumentor`, `CeleryInstrumentor`, `PsycopgInstrumentor` and `RedisInstrumentor` on the module and patches `telemetry.trace.set_tracer_provider` to `lambda provider: None` at `:57`. Three test classes: `TestResolveTracesExporter` `:61-91` (five cases, all preserved), `TestBuildResource` `:94-109`, `TestConfigureTelemetry` `:112-159`.

**The suite runs with `COMPONENT_RUNTIME=local` in the ambient environment.** `pixi.toml:435-436` declares it in `[feature.dev.activation.env]` and both `pixi run test` and `pixi run test-integration` resolve the `dev` environment (`pixi.toml:504-505`). No `OTEL_*` variable is set anywhere in `pixi.toml` or any settings module, so "no OTLP endpoint configured" is already the ambient state — AC #1 is the default the suite runs under, not a state a test has to construct.

**The live tracer provider is installed before any test runs.** `src/config/__init__.py:3` imports `config.celery_app`, whose module scope calls `configure_observability()` (`celery_app.py:13`), so importing anything under `config` — which `--ds=config.settings.test` does — installs the provider and all four instrumentors. This is why `tests/integration/test_asgi_request_path.py` can read spans off `trace.get_tracer_provider()` and why the new integration test must attach to that provider rather than build one.

**`src/config/observability/__init__.py` today (verified).** `configure_observability()` at `:62-73` calls `read_dot_env()` then `configure_telemetry()`; it is the single call each entry point makes (`manage.py:29-31`, `src/config/celery_app.py:12`, and the WSGI/ASGI entry points).

### Testing Requirements

- Unit tests extend `tests/unit/test_telemetry.py` and must keep using its `no_side_effects` fixture where instrumentation is asserted — instrumenting Django, Celery, psycopg and redis for real would apply for the whole session and leak into every later test.
- `tests/integration/test_local_trace_correlation.py` carries `pytestmark = [pytest.mark.integration, pytest.mark.django_db]` (`tests/integration/conftest.py` also applies the `integration` marker by directory, but the explicit declaration matches every existing file) and leaves state as found. It installs **no** provider, so it must **not** call `reset_telemetry_for_testing()` — clearing the process-wide guard would let a later `configure_telemetry()` instrument Django, Celery, psycopg and redis a second time for the rest of the session. What it must restore is the live provider's `_span_processors` tuple, in a `finally`, exactly as `tests/integration/test_asgi_request_path.py:190-228` does.
- Assert over captured structlog event dictionaries, never over raw stdout text. `src/config/settings/test.py:16` configures console rendering at `WARNING` for the suite; scraping that output is brittle. Reach those dictionaries through `caplog` (`record.msg`), not `structlog.testing.capture_logs` — see Task 4.
- Do not import `config.settings.base` from either test module. Re-importing it re-runs the process-global `structlog.configure()` and silently blinds later log-capture assertions; `tests/integration/test_site_migration.py:111-118` is the one place that does it, and it saves and restores `structlog.get_config()` around the import for that reason.
- The "no retry cycle" assertion must be an assertion, not an observation — capture the OpenTelemetry exporter logger's records and assert emptiness.
- Coverage floor: ninety percent including templates (AD-20), `COVERAGE_CORE=ctrace` in force (set in `[activation.env]`, which `tests/unit/test_locality_declaration.py` from Story 3.1 must continue to allow — `COVERAGE_CORE` is not a `COMPONENT_*` variable and is unaffected by that assertion).
- Test disposition: `core`.
- Run with `pixi run test` / `pixi run test-integration`; `pixi run ci` must exit 0.
- Neither module may skip. `tests/unit/test_suite_policy.py:46,50` is an AST gate over every test module banning `pytest.mark.skip`/`skipif`/`xfail` and calls to `pytest.skip`/`pytest.xfail`/`pytest.importorskip`; neither new-or-changed file is among its counted exemptions.
- Lint constraints that bite here: `force-single-line` imports, `PLR2004` (name magic numbers, cf. `TRACE_ID_HEX_LEN = 32` / `SPAN_ID_HEX_LEN = 16` at `tests/unit/test_observability_logging.py:16-17`), and `SLF001` (the `_active_span_processor` / `_span_processors` reads need `# noqa: SLF001` with a reason). mypy strict runs over `src/` only, so `has_span_processor` must be fully annotated; the tests follow the existing looser style.

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

## Spec Change Log

Reconciliation pass against the tree at `8284984`, before any code was written. The Dev Notes were
authored 2026-08-15; Stories 3.1-3.5 and Epic 1's ASGI work have landed since, and eleven claims did
not survive re-reading. Each is corrected in place above.

1. **Every line number in the Dev Notes was stale.** `telemetry.py` is 152 lines, not 146: a six-line
   comment block and a `# type: ignore[no-untyped-call]` were added around the instrumentor calls. The
   `DJANGO_ENV` read is at `:79`, not `:80`; the instrumentors are at `:140-143`, not `:134-137`;
   `configure_telemetry` is `:103-146`, `resolve_traces_exporter` `:86-100`, `build_resource` `:67-83`,
   `_has_otlp_endpoint` `:55-64`, `reset_telemetry_for_testing` `:149-152`. The AD-24 paragraph named
   `:135` and `:137` as the two single-line feature regions; those are now `:141` and `:143`, and `:141`
   carries a trailing type-ignore marker that travels with the region.

2. **`structlog.testing.capture_logs` is the wrong tool and Task 4's instruction is reversed.** It
   installs its own processor chain, dropping `merge_contextvars` *and `add_otel_context`* — so
   `trace_id` and `span_id` can never appear in what it captures, and a test written that way would
   assert the absence of the property AC #1 exists to prove. `tests/integration/test_request_logging.py:1-11`
   records the same finding for `request_id` and uses `caplog` with `record.msg`; Story 6.1 (`:46`)
   independently corrects Story 3.6 on this point. The task now says `caplog`.

3. **Task 2's second option is unusable.** "Expose the resolved exporter from `configure_telemetry`'s
   return path" would change a `bool` return that `configure_observability` (`__init__.py:73`) forwards
   and six existing tests assert on. Only the `has_span_processor(provider)` predicate is now prescribed.

4. **The predicate has nothing to inspect under the current fixture.** `no_side_effects`
   (`tests/unit/test_telemetry.py:57`) patches `telemetry.trace.set_tracer_provider` to
   `lambda provider: None`, discarding the provider `configure_telemetry` builds. An `installed_provider`
   fixture is split out to capture it; `no_side_effects` depends on it and keeps its existing return
   type, so no existing test signature changes.

5. **Two existing tests break, not one.** `test_environment_overrides` (`:100-106`) sets
   `DJANGO_ENV=production` and asserts `deployment.environment == "production"` — a hard failure after
   Task 3. `test_default_service_name` (`:95-98`) asserts `"local"` and passes today only because the
   `dev` pixi environment exports `COMPONENT_RUNTIME=local` (`pixi.toml:435-436`); once the fixture
   scrubs that variable the hermetic answer is `"deployed"`.

6. **Three existing tests are replaced, not supplemented.** `test_console_exporter_registers_a_processor`
   (`:131-144`) and `test_no_processor_without_an_endpoint` (`:146-159`) patch
   `TracerProvider.add_span_processor` and count calls, mocking the attachment the property is about.
   Task 4's object-level equivalents supersede them; keeping both would leave two tests of one property,
   one of which mocks the thing under test.

7. **`OTEL_VARS` is renamed.** A tuple called `OTEL_VARS` that holds `COMPONENT_RUNTIME` misnames
   itself. It becomes `SCRUBBED_VARS` and its autouse fixture `_clean_otel_env` becomes `_clean_env`;
   neither name is referenced outside the module.

8. **`deployment.environment` loses granularity and the docs must say so.** `DJANGO_ENV` carried a
   free-text tier name; `is_local()` is boolean and collapses `staging`, `production` and every other
   deployed tier to `"deployed"`. The 2026-08-15 draft treated `docs/observability.md:47` as a
   cross-reference to reconcile; it is a factual table row that becomes false, and it is replaced.

9. **Nothing outside the source tree sets `DJANGO_ENV`.** A full sweep found no `.env` file, Dockerfile,
   GitHub workflow, `pixi.toml` entry or settings module that mentions it; the only setter in the
   repository is `tests/unit/test_telemetry.py:102`. So the deployed default has always been the
   fail-open `"local"` recorded as a known defect at `ARCHITECTURE-SPINE.md:502`. No env-var allowlist
   test enumerates it either — `tests/unit/test_locality_declaration.py` matches by `COMPONENT_` prefix
   and needs no change.

10. **The integration test must not install or reset telemetry.** The Testing Requirements told it to
    call `reset_telemetry_for_testing()` in teardown and restore "any tracer provider it installed".
    `src/config/__init__.py:3` -> `config.celery_app:13` -> `configure_observability()` already installs
    the provider and all four instrumentors at package import, and `trace.set_tracer_provider` refuses
    to override. Clearing the guard in teardown would let a later `configure_telemetry()` re-instrument
    for the rest of the session. The test attaches an `InMemorySpanExporter` to the live provider and
    restores its `_span_processors` tuple instead.

11. **The "no retry output" assertion needed concrete logger names, and skipping is banned.** The
    emitters are `opentelemetry.exporter.otlp.proto.http.trace_exporter` and
    `opentelemetry.sdk.trace.export`; both propagate to `opentelemetry`, so one
    `caplog.at_level(logging.WARNING, logger="opentelemetry")` covers them. And
    `tests/unit/test_suite_policy.py:46,50` bans every skip mechanism in every test module, so a missing
    provider or a suppressing sampler must fail the assertion with a named cause
    (`test_asgi_request_path.py:85-98`), not skip it.

Two corrections of smaller weight, applied without a numbered entry: the story's "test disposition:
`core`" needs no artifact — no `test_*.py` in the tree carries a disposition marker and `accelerator.toml`
does not exist until Epic 7 — and `site/` is untracked mkdocs output whose stale copy of the
`DJANGO_ENV` row regenerates rather than being hand-edited.

## Review Triage Log

### 2026-08-18 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 10: (high 2, medium 4, low 4)
- defer: 1: (high 0, medium 0, low 1)
- reject: 10: (high 0, medium 1, low 9)
- addressed_findings:
  - `[high]` `[patch]` Nothing observed the resource on the *installed* provider, so dropping it entirely (`TracerProvider()` with no `resource=`) passed the whole 920-test suite — the `deployment.environment` attribute this story changed could have stopped reaching any backend silently. `test_provider_is_installed_with_no_endpoint_configured` now asserts `service.name` and `deployment.environment` on `installed_provider[0].resource`. Verified: the mutation now fails two tests.
  - `[high]` `[patch]` `test_no_retry_output_during_a_run` could not fail. `BatchSpanProcessor`'s default schedule delay is five seconds, so a processor wrongly attached to an unreachable endpoint emits its first retry warning long after the `caplog` window closes; attaching one unconditionally left all five integration tests green. Added `test_the_live_provider_carries_no_span_processor`, which asserts the structural property over the process-wide provider through `has_span_processor`. Verified: the mutation now fails that test. The log-based check is kept and its docstring demoted to "secondary".
  - `[medium]` `[patch]` `has_span_processor` raised `AttributeError` on the `ProxyTracerProvider` / no-op provider `trace.get_tracer_provider()` returns before configuration and under `OTEL_SDK_DISABLED`. It now returns `False` for a provider with no processor container, while still failing loudly if the container exists but the SDK's internals moved.
  - `[medium]` `[patch]` `assert build_resource() == unset_resource` in the console test was a tautology — `build_resource` never reads `OTEL_TRACES_EXPORTER`, so no implementation could fail it. Now compares `provider.resource` against the resource captured before the variable was set.
  - `[medium]` `[patch]` `test_unreachable_endpoint_is_not_a_configuration_this_code_produces` sat in `TestConfigureTelemetry` while exercising no line of it, duplicating `TestResolveTracesExporter`'s default case. It now calls `configure_telemetry()` and asserts no `BatchSpanProcessor` is on the built provider.
  - `[medium]` `[patch]` `docs/development.md` claimed "Nothing points a batch processor at a collector that is not there", which is false when `OTEL_TRACES_EXPORTER=otlp` is set explicitly with no endpoint — `resolve_traces_exporter` honours the explicit choice and the SDK falls back to its own default endpoint. Both docs now scope the claim to the default configuration and name the opt-in.
  - `[low]` `[patch]` `SCRUBBED_VARS` omitted `OTEL_RESOURCE_ATTRIBUTES`, which `Resource.create` merges via `OTELResourceDetector` and which could break `test_version_is_omitted_when_unknown` from an ambient shell, and `OTEL_TRACES_SAMPLER`. Both added, with the reason recorded inline.
  - `[low]` `[patch]` The `trace_id` / `span_id` assertions checked length only, which passes on whitespace and on the all-zero id an invalid span context would produce — the regression they exist to catch. They now also assert the ids parse as non-zero hex.
  - `[low]` `[patch]` `docs/observability.md` gave `COMPONENT_RUNTIME`'s default as "unset", which is true only of the `default` pixi environment and never of the reader running `pixi run`. The row now names the `dev` environment's `local`, the strip-and-lowercase matching, and that the attribute previously mirrored `DJANGO_ENV` so tier-keyed dashboards need updating.
  - `[low]` `[patch]` Two doc overclaims corrected: "`trace_id` and `span_id` reach every log line" is now scoped to lines emitted while a span is active, and the console consequence is stated as what the suite actually asserts — that a console exporter is attached — rather than implying an end-to-end stdout test.

Deferred: the `recorded_spans` fixture and the three environment-hint helpers are duplicated verbatim between this story's integration module and `tests/integration/test_asgi_request_path.py`; lifting them into `tests/integration/conftest.py` touches a shared file a second passing module depends on and is worth doing when Epic 6's collector-stub tests want the same fixture.

Rejected as noise: the `_configured` early return described as a second way instrumentation is "turned off" (it prevents double-instrumenting, it does not disable); `_sdk_is_disabled` re-implementing the private `telemetry._is_disabled` (the established precedent does the same, and it is recorded in the deferred entry); the `recorded_spans` restore being unsynchronised and un-flushed (`SimpleSpanProcessor` exports on span end, and the shape is copied from the working precedent by spec instruction); `_span_absence_hint` not enumerating `OTEL_PYTHON_DJANGO_EXCLUDED_URLS` or covering the correlation assertion; the retry-logger filter not covering `urllib3` (the structural assertion now carries AC #3); the console test leaking an unshut `ConsoleSpanExporter` (it holds `sys.stdout` and no thread); duplicated SERVER-span coverage with `test_asgi_request_path.py` (different premise — the no-endpoint local path); and `INSTRUMENTED_NAMES` being a list rather than a tuple (it is compared against `sorted()`, which returns a list).

## Auto Run Result

Status: done

### Summary

FR-21 made structural. Telemetry was already unsubstituted locally by accident of how
`configure_telemetry` was written; this story made that enforceable — a predicate that lets the
"no processor is attached" property be asserted over the built provider instead of by re-reading the
environment, tests that pin the provider, the instrumentor set, the resource and the log correlation
with no endpoint configured, and the AD-13 correction that stops `deployment.environment` being read
from a `DJANGO_ENV` that defaulted to `local` from a deployed component.

### Files changed

| Path | Change |
| --- | --- |
| `src/config/observability/telemetry.py` | `has_span_processor` predicate; `DJANGO_ENV` read replaced with `config.locality.is_local()`; the `none` branch's "absence is the discard" comment |
| `tests/unit/test_telemetry.py` | `SCRUBBED_VARS` replacing `OTEL_VARS`; `installed_provider` fixture split out of `no_side_effects`; six tests added or replaced, all asserting over the built provider |
| `tests/integration/test_local_trace_correlation.py` | NEW — six tests: no exporter resolves; a request produces a finished SERVER span; request events carry non-zero hex `trace_id` / `span_id`; the logged trace id is a recorded span's; the live provider carries no processor; no OpenTelemetry warning records during a run |
| `docs/development.md` | The three testable consequences under `## Running with no external services`, with the explicit-`otlp` opt-in named |
| `docs/observability.md` | `COMPONENT_RUNTIME` replaces the `DJANGO_ENV` config row, with the migration note; instrumentation-is-unconditional paragraph |
| `_bmad-output/implementation-artifacts/deferred-work.md` | One new open entry: the duplicated integration fixture |

### Review findings

10 patches applied (2 high, 4 medium, 4 low), 1 deferred, 10 rejected. No intent gap and no spec
defect: the specification's own Spec Change Log had already corrected the eleven claims that did not
survive re-reading the tree, and every review finding was a code- or doc-level fix inside it.

### Verification

- `pixi run ci` exits 0. 921 passed, total coverage 96.39% against the 90% floor.
- Both high-severity findings were closed against a mutation, not by inspection. Dropping the
  resource from the provider (`TracerProvider()`) failed the whole suite before the patch and now
  fails two tests. Attaching an unconditional `BatchSpanProcessor(OTLPSpanExporter())` left all five
  integration tests green before the patch and now fails
  `test_the_live_provider_carries_no_span_processor`. `telemetry.py` was restored from a backup after
  each and the gate re-run to `CI_EXIT=0`.
- The gate ran against sqlite, which is correct here: no model, migration or persisted
  externally-supplied value is touched.

### Residual risks

- **The OTLP export branch is still untested**, by design. `configure_telemetry`'s `otlp` path is
  never taken by any test, so `BatchSpanProcessor(OTLPSpanExporter())` is unexercised. That is FR-45's
  work in Epic 6 against a collector stub, and R-5 already records that local telemetry proves nothing
  about export.
- **`deployment.environment` granularity is gone and cannot be restored by an operator.**
  `Resource.create` merges the explicit dict last, so `OTEL_RESOURCE_ATTRIBUTES` cannot override it.
  Every deployed tier now reports `deployed`. This is the intended AD-13 trade, recorded in the
  docstring and the docs table, but any dashboard keyed on `staging` or `production` breaks on deploy.
- **`has_span_processor` reads SDK internals.** An OpenTelemetry SDK upgrade that renames
  `_active_span_processor` or `_span_processors` breaks it loudly, in three places (the predicate and
  both integration fixtures). It fails rather than silently reporting "no processor", which is the
  right direction, but it is an upgrade-time cost.
- **The instrumentor block at `telemetry.py:178-181` is load-bearing for Epic 7.** AD-24's marker
  pairs are declared against exactly that interleaving of `core` and feature-owned lines; reordering
  or merging them later strips Django and psycopg instrumentation from every combination.

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (implementation subagent: general-purpose, same model).

### Debug Log References

None. No harness loop was entered — `pixi run ci` passed on its first full invocation after the
inner loop, and was re-run independently to confirm `EXIT=0`.

### Completion Notes List

**Task 1 confirmation — there was no local substitution to remove.** Verified against the tree at
`8284984`: `src/config/settings/base.py`, `local.py`, `test.py` and `production.py` set no `OTEL_*`
variable; `pixi.toml` sets no `OTEL_*` variable in any activation env or task env; the unscoped
`[activation.env]` (`pixi.toml:384`) contains exactly one entry, `COVERAGE_CORE = "ctrace"`. So "no
OTLP endpoint configured" was already the ambient state of every local and every test run, and this
story made that property enforceable rather than incidental. No local opt-out, no `if DEBUG` guard
around instrumentation and no `OTEL_SDK_DISABLED` default were added.

**AD-24 preserved.** The four instrumentor calls at `telemetry.py:178-181` keep their order and
contiguity, `CeleryInstrumentor`'s `# type: ignore[no-untyped-call]` is intact, and the explanatory
comment block travels with them. No markers were added and no instrumentor was removed.

**`has_span_processor` reads SDK internals deliberately.** `provider._active_span_processor.
_span_processors` behind two `# noqa: SLF001` comments — the SDK exposes no public accessor, and
`tests/integration/test_asgi_request_path.py:196-200` already takes the same reach for the same
reason. The implementation uses direct attribute access rather than `getattr(..., ())`: a default
would silently report "no processor attached" if the SDK internals moved, turning an infrastructure
break into a passing assertion of the property under test.

**`deployment.environment` granularity was traded knowingly.** `DJANGO_ENV` carried a free-text tier
name; `config.locality.is_local()` is boolean, so every deployed tier now reports `deployed` rather
than `staging` or `production`. That is the AD-13 fail-closed correction — the old read defaulted to
`local`, so a deployed component that never set the variable reported itself local. Recorded in
`build_resource`'s docstring and in `docs/observability.md`'s configuration table, which now names
`COMPONENT_RUNTIME` and states both values the attribute can take.

**`structlog.testing.capture_logs` was not used, contrary to the 2026-08-15 draft.** It installs its
own processor chain, dropping `merge_contextvars` and `add_otel_context`, so `trace_id` and `span_id`
could never appear in what it captures. The integration test reads `caplog` and `record.msg`,
matching `tests/integration/test_request_logging.py`. See Spec Change Log entry 2.

**The integration test installs nothing and resets nothing.** It attaches an `InMemorySpanExporter`
to the live process-wide provider and restores the original `_span_processors` tuple in a `finally`.
`reset_telemetry_for_testing()` is deliberately not called: clearing the process-wide guard would let
a later `configure_telemetry()` instrument Django, Celery, psycopg and redis a second time for the
rest of the session. See Spec Change Log entry 10.

**Gate.** `pixi run ci` exits 0. 920 passed, total coverage 96.44% against the 90% floor;
`src/config/observability/telemetry.py` is at 100%. `pixi run test` 672 passed, `pixi run
test-integration` 242 passed with 6 pre-existing skips in `test_coverage_measurement.py`. The gate
ran against sqlite, which is correct here: this story changes no model, no migration and no
externally-supplied persisted value.

**Out of scope, untouched as instructed:** `src/config/websocket.py` and its `pyproject.toml` omit
entry (Epic 1, AD-16), `DEFAULT_SERVICE_NAME` (Epic 7, AD-25), the OTLP export path against a
collector stub (Epic 6, FR-45), and `site/` (untracked mkdocs output whose stale `DJANGO_ENV` row
regenerates on the next build).

### File List

| Path | Change |
| --- | --- |
| `src/config/observability/telemetry.py` | UPDATE — `has_span_processor` predicate; `DJANGO_ENV` read replaced with `config.locality.is_local()`; discard-at-the-processor comment on the `none` branch |
| `tests/unit/test_telemetry.py` | UPDATE — `OTEL_VARS` → `SCRUBBED_VARS` (`DJANGO_ENV` out, `COMPONENT_RUNTIME` in), `_clean_otel_env` → `_clean_env`, `installed_provider` fixture split out of `no_side_effects`; three tests replaced, one flipped, five added |
| `tests/integration/test_local_trace_correlation.py` | NEW — five tests: exporter resolves to `NONE`; a request produces a finished SERVER span; request events carry 32-hex `trace_id` and 16-hex `span_id`; the logged trace id is a recorded span's; no OpenTelemetry warning records during a run |
| `docs/development.md` | UPDATE — the three testable consequences under `## Running with no external services` |
| `docs/observability.md` | UPDATE — `DJANGO_ENV` config row replaced with `COMPONENT_RUNTIME`; instrumentation-is-unconditional paragraph under `### Why export is conditional` |
