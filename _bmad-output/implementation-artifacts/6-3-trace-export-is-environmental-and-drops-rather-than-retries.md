# Story 6.3: Trace export is environmental and drops rather than retries

Status: ready-for-dev

## Story

As a developer working on a generated component,
I want export attached only when a collector is configured,
so that local development does not retry against an unreachable endpoint through every test run.

## Acceptance Criteria

**Traceability:** FR-45 · CG-4

1. **Given** the OTLP endpoint or its traces-specific variant is set
   **When** the component starts
   **Then** export is enabled

2. **Given** neither is set
   **When** the component starts
   **Then** no span processor is attached
   **And** spans end without export

3. **Given** an unreachable endpoint
   **When** the configuration is inspected
   **Then** no batch processor is attached to an exporter pointed at it

## Tasks / Subtasks

- [ ] Task 1 — Read the implementation before changing anything; this is a regression-lock story with one hardening (AC: #1, #2, #3)
  - [ ] Read `src/config/observability/telemetry.py:1-13` (the module docstring states the rule), `:55-65` (`_has_otlp_endpoint`), `:87-101` (`resolve_traces_exporter`) and `:104-140` (`configure_telemetry`). AC #1 and AC #2 are implemented today and covered by `tests/unit/test_telemetry.py:62-79` and `:146-159`.
  - [ ] Read `docs/observability.md:51-66` ("Why export is conditional"). Keep the source, the tests and the documentation in agreement at the end of this story.

- [ ] Task 2 — Close the AC #3 gap: an explicit `OTEL_TRACES_EXPORTER=otlp` with no endpoint (AC: #3)
  - [ ] Reproduce the gap first. `resolve_traces_exporter` (`telemetry.py:98-101`) honours an explicit `OTEL_TRACES_EXPORTER` value before consulting `_has_otlp_endpoint()`. Set `OTEL_TRACES_EXPORTER=otlp` with **neither** `OTEL_EXPORTER_OTLP_ENDPOINT` nor `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` set: `configure_telemetry` attaches `BatchSpanProcessor(OTLPSpanExporter())`, and the SDK's default endpoint is `http://localhost:4318` — the exact retry-flood the module docstring at `:7-12` says this design prevents. `tests/unit/test_telemetry.py:81-88` (`test_explicit_choice_is_honoured`) currently pins that behaviour.
  - [ ] Change `resolve_traces_exporter` so an explicit `otlp` with no configured endpoint resolves to `NONE`. `console` and `none` remain honoured unconditionally — neither reaches the network. Keep the function's return contract (`otlp` | `console` | `none`) and its Google-style docstring; update the docstring to state the new rule.
  - [ ] Emit one structlog warning when the downgrade happens, naming both environment variables, so the operator who set `OTEL_TRACES_EXPORTER=otlp` learns why nothing is exporting. Use `structlog.get_logger(__name__)`; never stdlib `logging`, never `print()`. Note that `configure_telemetry` runs at entrypoint import *before* Django loads settings and therefore before `configure_structlog()` runs (`src/config/settings/base.py:287`) — structlog's default configuration handles this correctly, but do not assume the JSON renderer is installed at that moment.
  - [ ] Do not add a reachability probe. NFR-1 requires the startup checks to make "no network call and no query beyond migration state", so "unreachable" is not determinable at startup. The only startup-observable proxy for AC #3 is *no endpoint configured*, and that is what the implementation asserts. Record this reading in the test docstring.

- [ ] Task 3 — Extend the exporter-selection unit tests to cover every branch (AC: #1, #2, #3)
  - [ ] Update `tests/unit/test_telemetry.py:81-88` to reflect the new rule, and add: explicit `otlp` **with** `OTEL_EXPORTER_OTLP_ENDPOINT` set → returns `OTLP`; explicit `otlp` **with** `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` set only → returns `OTLP`; explicit `otlp` with neither → returns `NONE` and emits the warning.
  - [ ] Add an assertion that with an endpoint configured, `configure_telemetry` attaches exactly one processor and it is a `BatchSpanProcessor` — AC #1's "export is enabled" is currently proven only at the `resolve_traces_exporter` level, not at the `configure_telemetry` level. Follow the `add_span_processor`-monkeypatch pattern already used at `tests/unit/test_telemetry.py:131-159`.
  - [ ] Add an assertion that with no endpoint configured, a span started against the configured provider ends without raising and without any exporter having been constructed — AC #2's "spans end without export" half, which nothing asserts today.
  - [ ] Keep the `_clean_otel_env` autouse fixture (`tests/unit/test_telemetry.py:33-40`) as the isolation mechanism; add any new variable name to `OTEL_VARS` (`:23-30`) rather than deleting it ad hoc inside a test.

- [ ] Task 4 — Lock the "batch processor only ever wraps an OTLP exporter, and only when configured" shape (AC: #3)
  - [ ] Add a test that inspects the processors attached by `configure_telemetry` across all three exporter values and asserts: `otlp` → `BatchSpanProcessor`; `console` → `SimpleSpanProcessor` wrapping `ConsoleSpanExporter`; `none` → no processor. `ConsoleSpanExporter` under `SimpleSpanProcessor` writes to stdout and never retries, which is why it is not gated on an endpoint.
  - [ ] Assert that `_is_disabled()` short-circuits before any provider or processor is built (`telemetry.py:119-120`) — `OTEL_SDK_DISABLED` returning `False` from `configure_telemetry` is the SDK's standard kill switch, and it is separately a stage-1 refusal condition in Epic 4 (refusal-count table, condition 3). That coupling is a traceability marker here, not an acceptance condition for this story.

- [ ] Task 5 — Keep the documentation truthful (AC: #1, #2, #3)
  - [ ] Update `docs/observability.md:51-66` to state the new explicit-`otlp`-without-endpoint downgrade and the warning it logs. Update the configuration table at `:37-50` if it lists `OTEL_TRACES_EXPORTER` semantics.

- [ ] Task 6 — Run the gate (AC: #1, #2, #3)
  - [ ] `pixi run test`, then `pixi run ci`. The whole of this story is unit-testable; no integration test is required (Story 6.4 owns the end-to-end path).

## Dev Notes

### Architecture Constraints

- **FR-45** — "Trace export is environmental and drops rather than retries, with the export path exercised end to end in the gate against a collector stub." This story owns the *environmental and drops rather than retries* half. The *exercised end to end* half is Story 6.4.
- **CG-4** — "Do not substitute a capability that could run locally as deployed. A substitution is warranted only where the deployed dependency genuinely cannot be present on a developer's machine… Each one widens the parity gap the product already trades knowingly, and each must be guarded by a refusal." Read together with **FR-21**: "Observability is not substituted locally — same code, only the terminal export step absent; spans discarded at the processor." The instrumentation is identical in local and deployed; only the terminal export differs. Do **not** introduce a local-only telemetry code path, a `DEBUG` branch, or a settings-module override to achieve AC #2 — the absence of an endpoint is the entire mechanism.
- **NFR-1** — "Startup fails fast and cheaply… the checks make no network call and no query beyond migration state." This is why AC #3 cannot be discharged by probing reachability.
- **AD-24** — `src/config/observability/telemetry.py` is a `core` path carrying feature-owned regions, and the set of such paths is **open and carrier-declared**, not a fixed count. **`:134-137` is not one region.** Verified line by line: `:134` `DjangoInstrumentor().instrument()` and `:136` `PsycopgInstrumentor().instrument()` are **`core`**, present in all six combinations; only `:135` `CeleryInstrumentor().instrument()` and `:137` `RedisInstrumentor().instrument()` are feature-owned, as two single-line regions, and each carries its import with it — `:21` for Celery and `:24` for Redis — because pruning a call without its import only moves the `ImportError` from line 135 to line 21. This story edits `resolve_traces_exporter` (`:87-101`) and possibly the exporter branch (`:124-128`), both **above** all of that. Leave `:21-24` and `:134-137` one import and one call per line: do not merge, wrap, reorder or insert between them, because Epic 7 declares four separate marker pairs there and any shape change re-cuts them. AD-24 also forbids conditional imports, settings-module inheritance and `try/except ImportError` as sub-file mechanisms anywhere in this file.
- **AD-18 / NFR-4** — strict typing and lint are gate conditions, not advisories. Full type hints on public signatures; `X | Y`, `list[X]`, `dict[K, V]`.
- **Consistency Conventions → Configuration errors** — every forbidden or missing configuration raises `ImproperlyConfigured` at one of the two refusal stages, and a refusal never degrades to a warning. Note the distinction: an explicit `OTEL_TRACES_EXPORTER=otlp` with no endpoint is **not** a forbidden configuration and must **not** raise. It is a misconfiguration the component degrades through, which is why the response is a logged warning and a downgrade to `none`. `OTEL_SDK_DISABLED=true` is the forbidden one, and it is Epic 4's refusal, not this story's.
- **Deferred (spine)** — "Metrics and the OTLP logs signal. Additive to the existing traces-only setup." OpenTelemetry is traces only at 1.44. Do not add a metrics provider, a metrics exporter, or an OTLP logs handler.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/observability/telemetry.py` | UPDATE | Today: `_is_disabled` (`:40-52`) reads `OTEL_SDK_DISABLED`; `_has_otlp_endpoint` (`:55-65`) returns true when either `OTEL_EXPORTER_OTLP_ENDPOINT` or `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` is set; `resolve_traces_exporter` (`:87-101`) honours an explicit `OTEL_TRACES_EXPORTER` and otherwise returns `OTLP` when an endpoint exists and `NONE` when it does not; `configure_telemetry` (`:104-140`) is idempotent via the module-level `_configured` flag (`:37`, `:118-120`, `:139`), attaches `BatchSpanProcessor(OTLPSpanExporter())` for `otlp` (`:126`) or `SimpleSpanProcessor(ConsoleSpanExporter())` for `console` (`:128`), then instruments at `:134-137`. **This story changes only `resolve_traces_exporter`** — an explicit `otlp` with no endpoint downgrades to `NONE` and logs a warning. **Preserve:** the idempotence guard and `reset_telemetry_for_testing` (`:143-146`, used by the test fixture); the `configure_telemetry` return contract (`True` configured / `False` skipped); the module docstring's stated rule, updated in place rather than removed; the imports at `:21` and `:24` and lines `:134-137` byte-for-byte, one import and one call per line. |
| `tests/unit/test_telemetry.py` | UPDATE | Today: 159 lines. `_clean_otel_env` autouse fixture (`:33-40`) and `no_side_effects` fixture (`:43-58`) that stubs the four instrumentors and `trace.set_tracer_provider`. `TestResolveTracesExporter` (`:62-93`), `TestBuildResource` (`:95-109`), `TestConfigureTelemetry` (`:112-159`). Updates `test_explicit_choice_is_honoured` (`:81-88`) and adds the branch, processor-type and span-ends-without-export cases. **Preserve:** both fixtures and the existing coverage of `build_resource` and idempotence. |
| `docs/observability.md` | UPDATE | Today: 180 lines; "Configuration" at `:37-50`, "Why export is conditional" at `:51-66`. Adds the explicit-`otlp`-without-endpoint rule. **Preserve:** "What is instrumented" (`:90-104`) and "Configuration is read before Django starts" (`:106-117`). |

### Testing Requirements

- All work here is `tests/unit/test_telemetry.py` — unit tests only: no I/O, no network, no database, milliseconds each. That is itself part of the point: if a test in this module ever needs a network, the design has regressed.
- Assertions the ACs demand:
  - endpoint set (either variable) → `resolve_traces_exporter()` returns `OTLP`, and `configure_telemetry` attaches exactly one processor, of type `BatchSpanProcessor`;
  - neither variable set → returns `NONE`, `configure_telemetry` attaches zero processors, and a span started and ended against the provider raises nothing and constructs no exporter;
  - explicit `OTEL_TRACES_EXPORTER=otlp` with neither variable set → returns `NONE` and logs one warning naming both variables;
  - `console` → one `SimpleSpanProcessor` wrapping `ConsoleSpanExporter`;
  - `OTEL_SDK_DISABLED=true` → `configure_telemetry()` returns `False` and builds no provider.
- To assert on the emitted warning, use `structlog.testing.capture_logs` — this module logs through structlog directly rather than through the stdlib bridge, so the objection recorded at `tests/integration/test_request_logging.py:1-11` (that `capture_logs` drops `merge_contextvars` and therefore `request_id`) does not apply here.
- AD-20 coverage floor: 90% including templates, enforced by `pixi run test-cov` (`--cov-fail-under=90`), `COVERAGE_CORE=ctrace` from `pixi.toml:150`.
- Test disposition (Consistency Conventions → Test location): these cover immovable-core behaviour and are `core`; they must never be pruned by a feature.

#### Project Structure Notes

`src/config/observability/` is the Structural Seed's "existing cross-cutting home" and this story stays entirely inside it plus its mirrored test module — no layout variance. One thing to be aware of but not act on: `src/config/startup/` does not exist yet, so the `OTEL_SDK_DISABLED` **refusal** (Epic 4, refusal-count table condition 3) has no home. Today `_is_disabled()` makes the kill switch a silent skip; Epic 4 turns the same state into an `ImproperlyConfigured` in deployed runtime. Do not pre-empt that here — adding a raise now would break every local test run, which is precisely the failure mode AD-13 was written to avoid.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.3] — story statement and all three acceptance-criteria blocks.
- [Source: _bmad-output/planning-artifacts/epics.md#FR-45] — "Trace export is environmental and drops rather than retries, with the export path exercised end to end in the gate against a collector stub."
- [Source: _bmad-output/planning-artifacts/epics.md#FR-21] — "Observability is not substituted locally — same code, only the terminal export step absent; spans discarded at the processor."
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — `OTEL_SDK_DISABLED` is stage-1 refusal condition 3, owned by Epic 4.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#CG-4] — "Do not substitute a capability that could run locally as deployed."
- [Source: _bmad-output/planning-artifacts/epics.md#NFR-1] — the startup checks make no network call.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24] — the `telemetry.py:135`/`:137`-plus-imports-`:21`/`:24` region citation, with `:134` and `:136` `core`, and the forbidden alternative mechanisms.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — Configuration errors row; a refusal never degrades to a warning.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Deferred] — "Metrics and the OTLP logs signal" are deferred; traces only.
- [Source: src/config/observability/telemetry.py:1-13,40-65,87-140] — the docstring rule, the two predicates, exporter resolution and `configure_telemetry`.
- [Source: tests/unit/test_telemetry.py:23-58,62-93,112-159] — the fixtures and the existing selection coverage.
- [Source: docs/observability.md:37-66] — "Configuration" and "Why export is conditional".

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
