---
status: in-review
baseline_revision: 5c4a1b3
review_loop_iteration: 0
followup_review_recommended: false
warnings: [oversized]
---

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

- [x] Task 1 — Read the implementation before changing anything; this is a regression-lock story with one hardening (AC: #1, #2, #3)
  - [x] Read `src/config/observability/telemetry.py:1-13` (the module docstring states the rule), `:55-65` (`_has_otlp_endpoint`), `:87-101` (`resolve_traces_exporter`) and `:104-140` (`configure_telemetry`). AC #1 and AC #2 are implemented today and covered by `tests/unit/test_telemetry.py:62-79` and `:146-159`.
  - [x] Read `docs/observability.md:51-66` ("Why export is conditional"). Keep the source, the tests and the documentation in agreement at the end of this story.

- [x] Task 2 — Close the AC #3 gap: an explicit `OTEL_TRACES_EXPORTER=otlp` with no endpoint (AC: #3)
  - [x] Reproduce the gap first. `resolve_traces_exporter` (`telemetry.py:98-101`) honours an explicit `OTEL_TRACES_EXPORTER` value before consulting `_has_otlp_endpoint()`. Set `OTEL_TRACES_EXPORTER=otlp` with **neither** `OTEL_EXPORTER_OTLP_ENDPOINT` nor `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` set: `configure_telemetry` attaches `BatchSpanProcessor(OTLPSpanExporter())`, and the SDK's default endpoint is `http://localhost:4318` — the exact retry-flood the module docstring at `:7-12` says this design prevents. `tests/unit/test_telemetry.py:81-88` (`test_explicit_choice_is_honoured`) currently pins that behaviour.
  - [x] Change `resolve_traces_exporter` so an explicit `otlp` with no configured endpoint resolves to `NONE`. `console` and `none` remain honoured unconditionally — neither reaches the network. Keep the function's return contract (`otlp` | `console` | `none`) and its Google-style docstring; update the docstring to state the new rule.
  - [x] Emit one structlog warning when the downgrade happens, naming both environment variables, so the operator who set `OTEL_TRACES_EXPORTER=otlp` learns why nothing is exporting. Use `structlog.get_logger(__name__)`; never stdlib `logging`, never `print()`. Note that `configure_telemetry` runs at entrypoint import *before* Django loads settings and therefore before `configure_structlog()` runs (`src/config/settings/base.py:287`) — structlog's default configuration handles this correctly, but do not assume the JSON renderer is installed at that moment.
  - [x] Do not add a reachability probe. NFR-1 requires the startup checks to make "no network call and no query beyond migration state", so "unreachable" is not determinable at startup. The only startup-observable proxy for AC #3 is *no endpoint configured*, and that is what the implementation asserts. Record this reading in the test docstring.

- [x] Task 3 — Extend the exporter-selection unit tests to cover every branch (AC: #1, #2, #3)
  - [x] Update `tests/unit/test_telemetry.py:81-88` to reflect the new rule, and add: explicit `otlp` **with** `OTEL_EXPORTER_OTLP_ENDPOINT` set → returns `OTLP`; explicit `otlp` **with** `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` set only → returns `OTLP`; explicit `otlp` with neither → returns `NONE` and emits the warning.
  - [x] Add an assertion that with an endpoint configured, `configure_telemetry` attaches exactly one processor and it is a `BatchSpanProcessor` — AC #1's "export is enabled" is currently proven only at the `resolve_traces_exporter` level, not at the `configure_telemetry` level. Follow the `add_span_processor`-monkeypatch pattern already used at `tests/unit/test_telemetry.py:131-159`.
  - [x] Add an assertion that with no endpoint configured, a span started against the configured provider ends without raising and without any exporter having been constructed — AC #2's "spans end without export" half, which nothing asserts today.
  - [x] Keep the `_clean_otel_env` autouse fixture (`tests/unit/test_telemetry.py:33-40`) as the isolation mechanism; add any new variable name to `OTEL_VARS` (`:23-30`) rather than deleting it ad hoc inside a test.

- [x] Task 4 — Lock the "batch processor only ever wraps an OTLP exporter, and only when configured" shape (AC: #3)
  - [x] Add a test that inspects the processors attached by `configure_telemetry` across all three exporter values and asserts: `otlp` → `BatchSpanProcessor`; `console` → `SimpleSpanProcessor` wrapping `ConsoleSpanExporter`; `none` → no processor. `ConsoleSpanExporter` under `SimpleSpanProcessor` writes to stdout and never retries, which is why it is not gated on an endpoint.
  - [x] Assert that `_is_disabled()` short-circuits before any provider or processor is built (`telemetry.py:119-120`) — `OTEL_SDK_DISABLED` returning `False` from `configure_telemetry` is the SDK's standard kill switch, and it is separately a stage-1 refusal condition in Epic 4 (refusal-count table, condition 3). That coupling is a traceability marker here, not an acceptance condition for this story.

- [x] Task 5 — Keep the documentation truthful (AC: #1, #2, #3)
  - [x] Update `docs/observability.md:51-66` to state the new explicit-`otlp`-without-endpoint downgrade and the warning it logs. Update the configuration table at `:37-50` if it lists `OTEL_TRACES_EXPORTER` semantics.

- [x] Task 5b — Retire the "deliberate opt-in" wording Stories 3.6 and 3.7 wrote for the behaviour this story removes (AC: #3)
  - [x] `docs/development.md:431-433` (parenthetical under "Running with no external services") and `:502-510` ("One deliberate opt-in breaks it") — restate: an explicit `otlp` with no endpoint now resolves to `none` and logs `telemetry.otlp_exporter_without_endpoint`; the boot claim no longer has that exception.
  - [x] `docs/observability.md:80-84` — replace the opt-in paragraph with the downgrade rule; `:44` table row states that `otlp` requires an endpoint.
  - [x] `tests/unit/test_no_network_at_boot.py:10-19` and `:323-327` — docstrings only: the exception is gone. Keep scrubbing `OTEL_TRACES_EXPORTER` from the child (hermeticity), but stop calling it the supported way to reach the network.

- [x] Task 6 — Run the gate (AC: #1, #2, #3)
  - [x] `pixi run test`, then `pixi run ci`. The whole of this story is unit-testable; no integration test is required (Story 6.4 owns the end-to-end path).

## Dev Notes

### Reconciliation against the tree at `5c4a1b3` (2026-10-08) — supersedes stale claims below

This story was authored 2026-08-15; Epics 3 and 4 have since landed. Where the text below disagrees with this section, this section wins.

- **Line numbers have moved.** `telemetry.py`: `otel_sdk_is_disabled()` (public, `:54-76`, replaced `_is_disabled`; also read by `config.startup.stage_one` refusal condition 3, which now exists), `_has_otlp_endpoint` `:79-88`, `resolve_traces_exporter` `:117-131`, `has_span_processor` `:134-157` (new helper from Story 3.6), `configure_telemetry` `:160-211`, exporter branch `:180-184`, instrumentor calls `:205-208`, region imports `:21` and `:24`. `reset_telemetry_for_testing` `:214-217`. The AD-24 constraint is unchanged: leave `:21-24` and `:205-208` byte-identical.
- **Test module has moved on.** `tests/unit/test_telemetry.py` is 245 lines. The scrub fixture is `_clean_env` with tuple `SCRUBBED_VARS` (`:28-59`), not `_clean_otel_env`/`OTEL_VARS`. Fixtures `installed_provider` (`:62-72`, captures the provider handed to `set_tracer_provider`) and `no_side_effects` (`:75-89`) exist. Already covered: no endpoint → zero processors (`:198-205`), no `BatchSpanProcessor` with no endpoint (`:207-223`), console → one `SimpleSpanProcessor(ConsoleSpanExporter)` (`:225-245`), kill switch → `False` (`:152-157`). `test_explicit_choice_is_honoured` (`:111-118`) pins the defect. Still missing: endpoint configured → exactly one `BatchSpanProcessor` wrapping `OTLPSpanExporter` at the `configure_telemetry` level; span ends with no exporter constructed; explicit `otlp` downgrade + warning; kill switch builds no provider.
- **The "deliberate opt-in" is the defect, not a decision.** Stories 3.6 and 3.7 documented explicit `OTEL_TRACES_EXPORTER=otlp` without an endpoint as "the deliberate opt-in" because that was the behaviour at the time and those stories did not own it. The epic context names it as a live defect this epic owns ("the OTLP exporter currently attaches to an unconfigured default endpoint … fix each with the test its story specifies"), and AC #3 forbids it. Task 5b retires that wording in `docs/development.md`, `docs/observability.md` and `tests/unit/test_no_network_at_boot.py`.
- **Logger.** Use the module-level convention of `src/config/authorization/*.py`: `logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)`. Event name `telemetry.otlp_exporter_without_endpoint`, with keys naming `OTEL_TRACES_EXPORTER` and both endpoint variables.
- **Docs line numbers.** `docs/observability.md` is 208 lines: Configuration table `:40-49`, "Why export is conditional" `:51-84`. `README.md:41-43` already states the target behaviour and needs no change.

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

## Review Triage Log

### 2026-10-08 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 6: (high 0, medium 1, low 5)
- defer: 2: (high 0, medium 1, low 1)
- reject: 13: (high 0, medium 2, low 11)
- addressed_findings:
  - `[medium]` `[patch]` Nothing asserted the default path stays silent: mutating the downgrade guard to `if True:` left the suite green, so every endpoint-less local boot could have logged a misleading `otlp` warning. `test_none_when_no_endpoint_is_configured` and `test_unknown_value_falls_back` now assert `captured_events == []`.
  - `[low]` `[patch]` `_has_otlp_endpoint` treated a whitespace-only endpoint as configured, selecting OTLP against a URL that points at nothing — AC #3's case by another route. It now strips; `test_a_blank_endpoint_is_not_an_endpoint` covers `""`, `" "` and `"\t"` on both variables.
  - `[low]` `[patch]` The warning carried a prose `message=` key, the only one in `src/config`, duplicating the event name and colliding with any event-renaming processor. Dropped; `endpoint_variables` already names both variables.
  - `[low]` `[patch]` The endpoint-configured test set `/v1/traces` on the *general* variable, which the SDK suffixes itself, and indexed `installed_provider[0]` before asserting a provider exists. Per-variable `ENDPOINT_VALUES` and a length assertion added.
  - `[low]` `[patch]` `tests/unit/test_no_network_at_boot.py` said the scrub keeps the warning off the child's *stderr*; pre-settings structlog writes to stdout. Reworded to "output".
  - `[low]` `[patch]` `docs/development.md` claimed a configured endpoint is "not a local start path", which nothing enforces (a local collector is legitimate). Reworded.

## Dev Agent Record

### Agent Model Used

Claude Opus 5.5 (claude-opus-5-5)

### Debug Log References

- `pixi run test`: 1242 passed. `pixi run ci`: exit 0, 1559 passed, coverage 97.09%.
- After review patches: `pixi run ci` exit 0, **1565 passed, coverage 97.09%**.
- `tests/unit/test_telemetry.py` run in isolation (26 passed) and in the full suite.

### Completion Notes List

- `resolve_traces_exporter`: `console`/`none` honoured unconditionally; an endpoint (either variable) resolves to `otlp`; explicit `otlp` with neither endpoint resolves to `none` and logs one `telemetry.otlp_exporter_without_endpoint` warning (keys `exporter_variable`, `endpoint_variables`, `resolved_exporter`; the prose `message` key was dropped in review). Unknown values keep the endpoint rule. No probe, no raise.
- Module-level `logger` added; `import structlog` sits before `from opentelemetry import trace` (ruff isort), so the AD-24 import and instrumentor lines are byte-identical but shifted down by the added lines.
- The capture tests rebind `telemetry.logger` and prove the capture live with a control event (`captured_events` fixture, after `tests/unit/test_health_views.py`), so `cache_logger_on_first_use` cannot blind them.
- Endpoint-configured test builds the real `BatchSpanProcessor(OTLPSpanExporter())` and shuts the provider down in `finally`; the no-endpoint tests replace both exporter classes with counting stubs.
- Task 4's three-value shape is covered by separate tests (otlp, console, none) rather than one parametrised case.
- The "deliberate opt-in" wording is retired in `docs/development.md`, `docs/observability.md` and `tests/unit/test_no_network_at_boot.py`; `OTEL_TRACES_EXPORTER` is still scrubbed from the boot probe's child.

### File List

- src/config/observability/telemetry.py
- tests/unit/test_telemetry.py
- tests/unit/test_no_network_at_boot.py
- docs/observability.md
- docs/development.md
- _bmad-output/implementation-artifacts/6-3-trace-export-is-environmental-and-drops-rather-than-retries.md

## Auto Run Result

Status: `done`

### Summary of implemented change

FR-45 / CG-4. `resolve_traces_exporter` now applies the endpoint rule to an explicit `OTEL_TRACES_EXPORTER=otlp` as well: with neither `OTEL_EXPORTER_OTLP_ENDPOINT` nor `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` set (blank counts as unset), it resolves to `none` and logs one `telemetry.otlp_exporter_without_endpoint` warning instead of attaching a `BatchSpanProcessor` to the SDK's `localhost:4318` default. `console` and `none` stay unconditional. No reachability probe (NFR-1), no refusal. The "deliberate opt-in" wording Stories 3.6/3.7 wrote for the old behaviour is retired. AD-24 lines (`telemetry.py` region imports and the four instrumentor calls) are byte-identical, shifted by the added import and logger.

### Files changed

- `src/config/observability/telemetry.py` — downgrade-and-warn rule, blank-endpoint handling, module logger, docstrings.
- `tests/unit/test_telemetry.py` — every exporter-selection branch; `configure_telemetry`-level processor shape for otlp/console/none; span ends with no exporter constructed; kill switch builds no provider; silence on the default path.
- `tests/unit/test_no_network_at_boot.py` — docstrings: the explicit-`otlp` exception no longer exists.
- `docs/observability.md`, `docs/development.md` — the downgrade rule replaces the opt-in.
- `_bmad-output/implementation-artifacts/deferred-work.md` — two entries.

### Review findings breakdown

Blind, edge-case and verification-gap reviewers ran in parallel. **6 patches** (1 medium, 5 low), **2 deferred** (pre-settings rendering of the warning; comma-separated `OTEL_TRACES_EXPORTER` lists), **13 rejected**. No intent gaps, no spec repairs, `review_loop_iteration` 0.

### Verification performed

- `pixi run ci` — exit 0, **1565 passed, coverage 97.09%** (floor 90); pre-commit, build, typecheck, lint clean.
- Verification-gap reviewer's mutation (`if configured == OTLP:` → `if True:`) passed the suite before the patch; the new silence assertions close it.
- Reviewer booted `import config.wsgi` with `OTEL_TRACES_EXPORTER=otlp`, no endpoint: the warning appears (console-rendered, stdout) and nothing is exported.
- No PostgreSQL run: unit-only change, no schema, nothing persisted.

### Residual risks

- The warning fires inside `configure_observability()`, before settings run `configure_structlog()`, so it renders through structlog's defaults (console text on stdout), not the configured JSON pipeline. The spec accepted this; deferred.
- `OTEL_TRACES_EXPORTER=otlp,console` (spec-valid list) is treated as unknown — pre-existing; deferred.

### Follow-up review recommendation

`false`. Six localized patches, one medium (an added assertion); no behaviour beyond the blank-endpoint strip changed in review.
