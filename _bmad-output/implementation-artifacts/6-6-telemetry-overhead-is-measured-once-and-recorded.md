---
status: done
baseline_revision: 1a2dad5
review_loop_iteration: 0
followup_review_recommended: false
final_revision: 1eea3d8
warnings: [oversized]
---

# Story 6.6: Telemetry overhead is measured once and recorded

Status: ready-for-dev

## Story

As a platform engineer,
I want the cost of always-on instrumentation measured rather than asserted,
so that the claim that it is acceptable rests on a number.

## Acceptance Criteria

**Traceability:** NFR-6 · spine Open Item (no AD, needs an owner)

1. **Given** instrumentation is always on and never conditionally disabled to gain performance
   **When** the overhead is established
   **Then** it is measured once against the reference application with export disabled
   **And** recorded alongside the observability documentation

2. **Given** the instrumentation set changes
   **When** the measurement is reconsidered
   **Then** it is re-measured
   **And** not otherwise

3. **Given** this is an open item with no architectural decision
   **When** the story is picked up
   **Then** an owner and a milestone are named as part of it

## Tasks / Subtasks

- [x] Task 1 — Name the owner and the milestone before measuring anything (AC: #3)
  - [x] **This story may not invent an owner or a milestone.** The spine lists this as an Open Item: "NFR-6 — telemetry overhead measured once and recorded. No AD; needs an owner and a milestone." Obtain both from the human running the work. If either is missing, stop, record the blocked state in Completion Notes, and escalate — do not name a placeholder or infer an owner from the epic's persona.
  - [x] Record the owner and the milestone in the new `docs/observability.md` section created in Task 4, with the date.
  - [x] Note for the caller: the spine's Open Items entry at `ARCHITECTURE-SPINE.md:502` should be updated once both are decided. Editing a planning artifact is a separate, deliberate act — flag it rather than folding it into an implementation commit.

- [x] Task 2 — Decide how the baseline is obtained, and do not use the kill switch (AC: #1)
  - [x] NFR-6 says "with export disabled". The baseline for *overhead* additionally needs an uninstrumented run. **Do not obtain it by setting `OTEL_SDK_DISABLED=true`.** That state is stage-1 unconditional refusal condition 3 in the refusal-count table, and once Epic 4 lands, a settings import with it set raises `ImproperlyConfigured` — so a benchmark built on the kill switch works today and breaks the moment the refusal contract ships. Record this reasoning in the harness docstring; it is the single most likely wrong turn in this story.
  - [x] Obtain the uninstrumented baseline by **uninstrumenting after boot**, not by skipping `configure_observability()`. *Reconciled 2026-10-09:* skipping the call is impossible without editing production code — `src/config/__init__.py` imports `.celery_app`, which calls `configure_observability()` at `src/config/celery_app.py:14`, so any import of the `config` package (settings included) installs instrumentation. The baseline child therefore calls `.uninstrument()` on each of the four instrumentors (`BaseInstrumentor` is a singleton, so a fresh instance is the installed one) **before the first request is served**, and self-checks that all four report `is_instrumented_by_opentelemetry is False` and that the Django OpenTelemetry middleware is absent from `settings.MIDDLEWARE`. Record this reasoning in the harness docstring alongside the kill-switch reasoning. The tracer provider stays installed in both arms (`trace.set_tracer_provider` is set-once); the log processors that read the current span also run in both arms — state both as method limits in the docs section.
  - [x] "Export disabled" for the instrumented arm means simply: neither `OTEL_EXPORTER_OTLP_ENDPOINT` nor `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` set, and `OTEL_TRACES_EXPORTER` unset — `resolve_traces_exporter()` (`telemetry.py:87-101`) then returns `NONE` and no span processor is attached (`:124-129`). This isolates instrumentation cost from network cost, which is what NFR-6 asks for.

- [x] Task 3 — Build the measurement harness (AC: #1)
  - [x] Create `tools/telemetry_overhead.py`. `tools/` does not exist yet; the Structural Seed places `tools/materializer/` and `tools/harness/` (the six-combination verification runner) there as `machinery`, so a benchmark harness at `tools/` inherits `machinery` disposition and never travels into a component. Keep it out of both of those directories — neither namespace is this story's. Add no `__init__.py` unless the module needs to be imported rather than run.
  - [x] Shape: the parent process spawns one child per arm per round (`sys.executable` re-running the same file with `--arm instrumented|baseline` and a temporary JSON output path), alternating arms across rounds to spread order and thermal effects, and pools each arm's samples. Each child sets `DJANGO_SETTINGS_MODULE` (default `config.settings.test`, overridable by `--settings`), calls `django.setup()`, applies its arm (instrumented: assert `resolve_traces_exporter() == NONE` and no span processor via `has_span_processor`; baseline: uninstrument as above), then issues N GETs of one fixed `core` route through Django's test client — `reverse("account_login")`; AD-29 deletes `home` and `about` — asserting HTTP 200, discarding a warm-up window, timing each request with `time.perf_counter_ns`. If that route needs database tables, the harness owns a throwaway database (e.g. a temporary sqlite file it migrates); it never touches a developer's database. The parent's child environment strips `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` and `OTEL_TRACES_EXPORTER`; if `OTEL_SDK_DISABLED` is set at all the harness refuses to run (raise `SystemExit` with a structlog error) rather than reinterpret it. Report median and p95 wall time per request per arm plus the delta as an absolute figure and a percentage; the sample size, warm-up count, rounds, settings module, database vendor, Python and Django versions, OpenTelemetry SDK version, and platform (`platform.platform()`, `platform.machine()`, CPU count). Keep the statistics reduction in pure, importable functions (stdlib + structlog imports only at module top; Django imports inside the child function) so it can be unit-tested.
  - [x] Emit the result through `structlog` as a structured event, and/or write a JSON file the operator can paste into the documentation. **Never `print()`**, never stdlib `logging`.
  - [x] Enumerate the instrumentation set in the report: the four instrumentors installed at `telemetry.py:134-137` (`Django` and `Psycopg` are `core`; `Celery` and `Redis` are feature-owned, so the reference application's set is the superset a materialized component can carry) plus the `opentelemetry-instrumentation-asgi` presence flag (`pixi.toml:66`), and the pinned OpenTelemetry version range from `pixi.toml:58-60`. AC #2's re-measure trigger is defined against exactly this list.
  - [x] Add a `bench-telemetry` task to `[feature.dev.tasks]` in `pixi.toml` with `default-environment = "dev"` and a `description`, following the existing task style at `pixi.toml:184-206`. It is a development task, not part of `ci` — do **not** add it to the `ci` `depends-on` chain at `pixi.toml:206`. A benchmark inside the gate makes the gate non-deterministic, and NFR-6 says measured **once**, not every run.
  - [x] Do not add `COMPONENT_RUNTIME` or any other `COMPONENT_*` variable to the task's `env` or to `[activation.env]` — AD-13 forbids `COMPONENT_*` in `[activation.env]` outright, and locality declaration is Epic 3's work.

- [x] Task 4 — Record the number alongside the observability documentation (AC: #1, #3)
  - [x] Add an `## Instrumentation overhead` section to `docs/observability.md` carrying: the measured median and p95 delta, the sample size, the date, the machine class, the exact instrumentation set measured, the named owner, the named milestone, how to reproduce it (`pixi run bench-telemetry`), and the explicit statement that instrumentation is always on and is never conditionally disabled to gain performance.
  - [x] `docs/observability.md` is already in the mkdocs nav (`mkdocs.yml`), so no nav edit is needed. `pixi run docs` builds with `--strict`; broken links fail it.
  - [x] NFR-8 — "Documentation travels with what it describes." Record in the section which disposition `docs/observability.md` carries. Epic 8 owns the `.github/`/`docs/` disposition split (FR-37); this is a note for that work, not a change here.

- [x] Task 5 — Make "re-measured only when the instrumentation set changes" enforceable (AC: #2)
  - [x] Add a test to `tests/unit/test_telemetry.py` that pins the instrumentation set (shape fixed in *Reconciliation* below): collect the names of every attribute of `config.observability.telemetry` ending in `Instrumentor` and assert the sorted result equals the set the measurement was taken against — in the reference application, `["CeleryInstrumentor", "DjangoInstrumentor", "PsycopgInstrumentor", "RedisInstrumentor"]`. The failure message must say: the instrumentation set changed, so NFR-6's measurement is stale — re-run `pixi run bench-telemetry` and update the `## Instrumentation overhead` section of `docs/observability.md`.
  - [x] Scope the frozen list to what is actually present. Two of the four names are feature-owned: AD-24 declares `telemetry.py:135` (`CeleryInstrumentor`) and `:137` (`RedisInstrumentor`) as single-line regions **carrying their imports at `:21` and `:24`**, so in a materialized component those two names are absent from the module namespace entirely. A flat four-name pin therefore holds only in the two of six combinations that select both Celery and Redis. Assert `DjangoInstrumentor` and `PsycopgInstrumentor` — the `core` calls at `:134` and `:136` — unconditionally, and let the Celery and Redis names be asserted from a region Epic 7 prunes with their features, reading the selected-feature list from `component.toml` (the only declaration present at settings import in both trees) rather than from a hardcoded four. Record the shape chosen in Completion Notes so Epic 7's carrier entry is unambiguous.
  - [x] Prefer this introspective form over adding a declared-set constant to `src/config/observability/telemetry.py`. That file already carries four marker pairs in Epic 7 (`:21`, `:24`, `:135`, `:137`); the fewer edits it takes, the less Epic 7 has to re-cut. If a constant is nonetheless added, place it **above** `configure_telemetry` and leave the imports at `:21-24` and lines `:134-137` byte-for-byte unchanged, one import and one call per line.
  - [x] The "and not otherwise" half is a policy statement, not an assertion — record it in the documentation section as the rule, and make sure the test's failure message is the only thing that ever triggers a re-measure.

- [x] Task 6 — Run the gate (AC: #1, #2, #3)
  - [x] Add `tests/unit/test_telemetry_overhead.py` covering the pure reduction functions (median/p95/delta, too-few-samples error, zero-baseline percentage) and the `OTEL_SDK_DISABLED` refusal / child-environment scrub, loading the module by file path.
  - [x] `pixi run test`, then `pixi run ci`. Run `pixi run bench-telemetry` separately and once; it is not part of `ci`. Record its output in the docs section.

## Dev Notes

### Reconciliation against the tree (2026-10-09)

The story was authored 2026-08-15; these facts supersede conflicting line numbers and claims elsewhere in this file.

- `src/config/observability/telemetry.py` is 242 lines: instrumentor imports `:24-27` (Celery, Django, Psycopg, Redis), `resolve_traces_exporter` `:127-156`, processor branch `:205-209`, instrumentor calls `:230-233` (Django, Celery, Psycopg, Redis). No `# feature:` markers exist in it yet — Epic 7 cuts them. Every "`:21`/`:24`/`:134-137`" reference above means these lines. **No change to this file.**
- `configure_observability()` is called from `manage.py:38`, `src/config/wsgi.py:31`, `src/config/asgi.py:27` and `src/config/celery_app.py:14`; the last runs on any import of `config`. Hence the uninstrument baseline in Task 2.
- `pixi.toml`: OTel pins `:120-123`, `opentelemetry-instrumentation-asgi` `:128`, `[environments]` `:379-382`, `[activation.env]` `:384-407` (only `COVERAGE_CORE`), `[feature.dev.tasks]` `:580-610`. `ci` now lives in `[feature.gate.tasks]` (`:636-643`); leave it unchanged. The dev feature already sets `COMPONENT_RUNTIME="local"` in `[feature.dev.activation.env]` — the new task adds no env.
- `pyproject.toml`: `[tool.coverage.run] include = ["src/**"]` at `:249`, `omit` `:292-298` — untouched. `typecheck` and the pre-commit mypy hook run `mypy src/` only, so also run `pixi run -e dev mypy --strict tools/telemetry_overhead.py` by hand; `ruff check .` covers `tools/`.
- `tests/unit/test_telemetry.py` is 445 lines; its autouse fixture is `_clean_env` (`:68-81`), not `_clean_otel_env`; `no_side_effects` is at `:97-98`. Preserve both.
- `component.toml` carries `selected_features = [...]` (`:90-101`). Read it through `config.component.load_component_declaration().selected_features` (`src/config/component/loader.py:236`) — do not write a second TOML reader.
- `docs/observability.md` now has 13 headings; place `## Instrumentation overhead` after `## Cache degradation is logged` (`:238`) and before `## Adding metrics or OTLP logs later` (`:271`).
- AD-7 (`tests/unit/test_import_roots.py`) forbids `sys.path` manipulation anywhere in the repository; `config` is importable because the package is installed. The unit test for the harness loads it with `importlib.util.spec_from_file_location`, which touches no import root.
- Task 5 shape: expected names = `{"DjangoInstrumentor", "PsycopgInstrumentor"}` plus `"CeleryInstrumentor"` iff `"celery"` is selected and `"RedisInstrumentor"` iff `"redis"` is selected, the feature list read from `component.toml` via the loader. No feature markers in the test; the mapping prunes itself when the materializer prunes `selected_features`.
- The measurement is run once by the dev agent on this machine and the numbers recorded; no AC requires an operator action outside the repository.

### Human-supplied decisions (2026-10-09)

Supplied by the human running the work before implementation, satisfying Task 1's precondition. These are not inferences.

- **Owner:** Platform engineering.
- **Milestone:** Before the v0.2.0 release.
- Record both, with the date, in the `## Instrumentation overhead` section of `docs/observability.md`.
- **Spine update:** already done in its own commit on this branch (`docs(architecture): name the owner and milestone for the NFR-6 open item`). Do not edit `ARCHITECTURE-SPINE.md` again.

### Architecture Constraints

- **NFR-6** — "Telemetry overhead is measured, not assumed — measured once against the reference application, recorded with the observability documentation, re-measured only when the instrumentation set changes." No AD covers it. The spine records it as an Open Item needing an owner and a milestone, and this story is where that is answered or escalated.
- **Spine → Open Items** — "NFR-6 — telemetry overhead measured once and recorded. **No AD; needs an owner and a milestone.**"
- **Spine → Capability → Architecture Map** — Observability (§4.8) "Lives in `src/config/observability/`", governed by "Conventions; FR-45 and NFR-6 are open items below." There is no architectural rule to conform to; the conventions table and NFR-6's own words are the whole constraint.
- **AD-24** — `src/config/observability/telemetry.py` is a `core` path carrying feature-owned regions, drawn from an **open, carrier-declared set**. **`:134-137` is not one region:** `:134` `DjangoInstrumentor().instrument()` and `:136` `PsycopgInstrumentor().instrument()` are **`core`** and present in all six combinations; only `:135` `CeleryInstrumentor().instrument()` and `:137` `RedisInstrumentor().instrument()` are feature-owned, each as a single-line region that also covers its import at `:21` and `:24` — a region covering a call without its import merely relocates the `ImportError`. That is the fact the Task 5 pin has to respect. Do not reorder, reformat, merge, wrap or insert between the imports at `:21-24` or the calls at `:134-137`. Forbidden anywhere in that file: conditional imports, settings-module inheritance, `try/except ImportError`.
- **AD-13** — "**No `COMPONENT_*` variable may appear in `[activation.env]`**, and a gate test asserts it over the materialized `pixi.toml`." The new pixi task must not introduce one.
- **AD-18** — "A single workflow invokes `pixi run ci`, which has never run in CI… `build` off its fortnightly cron." The benchmark is not part of `ci` and must not be scheduled on a cron; NFR-6 says measured once.
- **AD-20** — the coverage floor is ninety percent including templates, everywhere, and "Never a lower floor, a pragma, or a narrowed measurement. The coverage `omit`/`exclude` list is a closed, carrier-declared surface." `tools/` is outside `[tool.coverage.run] include = ["src/**"]` (`pyproject.toml:161`), so the harness is not measured and **no new `omit` entry is needed or permitted**. Adding one would touch the surface AD-20 closes. The spine carries an Open Item on exactly this — that `tools/materializer/` and `tools/harness/` being unmeasured "needs a decision, not a default" — but it is scoped to the phase-1 code Epics 7 and 8 add, not to a benchmark that produces a number for a human to read. Do not pre-empt that decision here, and do not treat the harness's exclusion as settling it.
- **NFR-8** — "Documentation travels with what it describes — component-facing docs materialize with the component, accelerator-facing docs do not."
- **Deferred (spine)** — traces only at OpenTelemetry 1.44; metrics and the OTLP logs signal are deferred. Do not add a metrics exporter to measure this.
- **Project standards** — Pixi is the only runner: `pixi run python tools/telemetry_overhead.py`, never bare `python`, never `uv`. Python 3.14 only. Full type hints, Google-style docstrings, line length 120, `X | Y` / `list[X]` / `dict[K, V]`. Never `print()`; never stdlib `logging`.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `tools/telemetry_overhead.py` | NEW | The two-arm measurement harness. `tools/` does not exist in the repository today; the Structural Seed places `tools/materializer/` and `tools/harness/` there as `machinery`, so this inherits `machinery` disposition and never travels into a component. |
| `pixi.toml` | UPDATE | Today: `[tasks]` at `:172-179` (runtime), `[feature.dev.tasks]` at `:184-206` (development + harness), `ci = { depends-on = ["test-cov", "lint", "typecheck", "build"] }` at `:206` — a task AD-18 records as already existing but wrongly shaped, which Epic 1 reshapes; this story neither fixes nor depends on its shape, it only stays out of it. Adds one `bench-telemetry` task in `[feature.dev.tasks]` with `default-environment = "dev"` and a `description`. **Preserve:** the `ci` `depends-on` list unchanged; `[activation.env]` at `:145-150` carrying only `COVERAGE_CORE = "ctrace"`; `[environments]` at `:141-143`. Do not add a dependency — everything the harness needs (`pytest`/Django test client, `structlog`) is already present. |
| `docs/observability.md` | UPDATE | Today: 180 lines — "What a log line looks like" (`:7`), "Configuration" (`:37`), "Why export is conditional" (`:51`), "Seeing it work" (`:67`), "What is instrumented" (`:90`), "Configuration is read before Django starts" (`:106`), "Writing logs" (`:118`), "Layout" (`:133`), "Adding metrics or OTLP logs later" (`:150`), "Note on dependencies" (`:161`). Adds `## Instrumentation overhead` with the number, method, owner, milestone and re-measure rule. **Preserve** every existing section, particularly the ASGI warning block at `:95-104`. |
| `tests/unit/test_telemetry.py` | UPDATE | Today: 159 lines; fixtures at `:33-58`, selection/resource/configure coverage at `:62-159`. Adds the instrumentation-set pin whose failure message is the re-measure trigger. **Preserve** the `_clean_otel_env` and `no_side_effects` fixtures. |
| `src/config/observability/telemetry.py` | **No change expected** | Today: the four instrumentor calls at `:134-137` and their imports at `:21-24`, which the pin introspects. `:134`/`:136` are `core`; `:135`/`:137` and the imports at `:21`/`:24` are the feature-owned regions. Listed so the dev agent reads and confirms rather than edits. If a declared-set constant is added, it goes above `configure_telemetry` and `:21-24` and `:134-137` stay byte-for-byte. |
| `mkdocs.yml` | **No change** | `docs/observability.md` is already in `nav` as `Observability: observability.md`. |

### Testing Requirements

- `tests/unit/test_telemetry.py` — unit: no I/O, no network, milliseconds. The instrumentation-set pin is pure introspection of the module namespace.
- The measurement harness itself is **not** a test and must not live under `tests/`. It is not run by `pixi run ci`, is not measured by coverage (`[tool.coverage.run] include = ["src/**"]`, `pyproject.toml:161`), and produces a number a human records — a benchmark that gates the build would be non-deterministic and would contradict "measured once".
- Assertions the ACs demand:
  - the instrumentation set equals the frozen four-name list, with a failure message that names the re-measure obligation and points at the documentation section (AC #2);
  - the documentation section exists and carries a number, an owner, a milestone and a date — verified by review, not by an assertion, because a doc-content assertion would be a coverage-shaped proxy for an editorial fact.
- If the harness gains any importable logic worth testing (for example the statistics reduction), add `tests/unit/test_telemetry_overhead.py` mirroring it — but keep the process-spawning half out of the suite.
- AD-20 coverage floor: 90% including templates via `pixi run test-cov` (`--cov-fail-under=90`); `COVERAGE_CORE=ctrace` from `pixi.toml:150`.

#### Project Structure Notes

This story creates `tools/`, which the Structural Seed anticipates (`tools/materializer/` and `tools/harness/`, both `machinery`) but which does not exist in the repository today. Placing the benchmark at `tools/telemetry_overhead.py` rather than inside either of those keeps the materializer's and the verification runner's namespaces clean for Epics 7 and 8. Since `accelerator.toml` does not exist yet, the `machinery` disposition is an intent recorded here, not a declared fact. AD-2's "unlisted defaults to `machinery`" settles **behaviour, not enumeration** — it makes the runtime consequence right, but every path present still needs its own claim in the carrier, and the Structural Seed is a shape rather than an inventory. So this file will need an explicit entry: record the intended disposition in Completion Notes so Epic 7 writes one rather than relying on the default.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.6] — story statement and all three acceptance-criteria blocks.
- [Source: _bmad-output/planning-artifacts/epics.md#NFR-6] — "Telemetry overhead is measured, not assumed — measured once against the reference application, recorded with the observability documentation, re-measured only when the instrumentation set changes."
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6] — "Owns two of the three ownerless open items — FR-45's collector stub design and NFR-6's telemetry-overhead measurement."
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — `OTEL_SDK_DISABLED` true is stage-1 unconditional refusal condition 3, which is why the baseline may not use the kill switch.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Open Items] — "NFR-6 — telemetry overhead measured once and recorded. No AD; needs an owner and a milestone."
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Capability → Architecture Map] — Observability is governed by conventions; FR-45 and NFR-6 are open items.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24] — the `telemetry.py:135`/`:137`-plus-imports-`:21`/`:24` region citation, with `:134` and `:136` `core`, and the forbidden mechanisms.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20] — the closed coverage `omit`/`exclude` surface.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13] — no `COMPONENT_*` in `[activation.env]`.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Structural Seed] — `tools/materializer/` and `tools/harness/` as `machinery`.
- [Source: src/config/observability/telemetry.py:87-101,124-140] — exporter resolution, the processor branch, and the four instrumentor calls.
- [Source: src/config/observability/__init__.py:62-73] — `configure_observability`, the single entrypoint call the baseline arm omits.
- [Source: pixi.toml:58-69,141-150,184-206] — the OpenTelemetry pins, `[environments]`, `[activation.env]`, and the dev task/`ci` block.
- [Source: pyproject.toml:160-169] — `[tool.coverage.run] include = ["src/**"]` and the closed `omit` list.
- [Source: docs/observability.md:1-180] — the existing section structure the new section joins.

## Dev Agent Record

### Agent Model Used

Claude Opus 5.5

### Debug Log References

- `pixi run -e dev mypy --strict tools/telemetry_overhead.py` crashes inside mypy 2.3.0 / django-stubs (`request.pyi:56`, "Must not defer during final iteration") for *any* single file outside `src/` -- reproduced on an unmodified `manage.py`. Checked instead as `pixi run -e dev mypy --strict src/ tools/telemetry_overhead.py`: no issues in 75 files.
- `pixi run ci` exit 0: pre-commit all Passed; typecheck clean; lint clean; `1607 passed`, total coverage 97.09%.

### Completion Notes List

- Owner (Platform engineering) and milestone (before the v0.2.0 release) are the human-supplied decisions of 2026-10-09, recorded with the date in `docs/observability.md` `## Instrumentation overhead`. `ARCHITECTURE-SPINE.md` was not touched (already updated in its own commit).
- **Measured 2026-10-09** (`pixi run bench-telemetry` defaults: 10 rounds x 1,000 measured requests per child after 200 warm-up = 10,000 per arm; `GET /accounts/login/`; `config.settings.test`; sqlite; Apple M4, 10 cores, 24 GB, macOS 26.2 arm64; Python 3.14.6, Django 5.2.15, OTel SDK 1.44.0, instrumentation-django 0.65b0):
  - baseline median 1.946 ms, p95 2.563 ms; instrumented median 2.053 ms, p95 3.428 ms;
  - delta median +0.107 ms (+5.5%), p95 +0.864 ms (+33.7%). An earlier same-day run (pre-refactor harness, same method) gave median +6.0% and p95 +44%; the docs say the p95 is noisy and to read the median.
- Baseline obtained by `.uninstrument()` after `django.setup()` with a self-check (all instrumentors report uninstrumented, OTel middleware gone from `settings.MIDDLEWARE`); never `OTEL_SDK_DISABLED`, which the harness refuses if present with any value. Instrumented arm asserts `resolve_traces_exporter() == "none"`, an SDK provider and `has_span_processor(...) is False`. Each child gets its own migrated temp sqlite via `DATABASE_URL`; `DJANGO_READ_DOT_ENV_FILE` and the three exporter variables are stripped. The developer `db.sqlite3` was verified untouched (mtime 2026-08-18).
- **Task 5 shape (for Epic 7's carrier):** `TestInstrumentationSet` in `tests/unit/test_telemetry.py` -- `CORE_INSTRUMENTORS = {"DjangoInstrumentor", "PsycopgInstrumentor"}` asserted unconditionally, plus `FEATURE_INSTRUMENTORS = {"celery": "CeleryInstrumentor", "redis": "RedisInstrumentor"}` filtered by `load_component_declaration().selected_features`; compared against every `*Instrumentor` name in `config.observability.telemetry`'s namespace. No feature markers in the test and no constant added to `telemetry.py`; the mapping prunes itself when the materializer prunes `selected_features`. The harness reads the instrumentor set by the same introspection, so a pruned component measures what it carries.
- **Intended disposition of `tools/telemetry_overhead.py`: `machinery`.** It produces a number for a human; it must never travel into a component. Epic 7's carrier should declare it explicitly rather than rely on the unlisted-defaults-to-`machinery` rule. `docs/observability.md` is component-facing (NFR-8); the section notes this for Epic 8/FR-37.
- `bench-telemetry` added to `[feature.dev.tasks]` (`default-environment = "dev"`); not in `ci`; no env, no `COMPONENT_*`; no dependency added. `tools/` is outside coverage `include`; no `omit` entry added. No `__init__.py` in `tools/` (file-level `# ruff: noqa: INP001`); no `sys.path` manipulation (AD-7 test passes).

### File List

- `tools/telemetry_overhead.py` (new)
- `tests/unit/test_telemetry_overhead.py` (new)
- `tests/unit/test_telemetry.py` (modified)
- `pixi.toml` (modified)
- `docs/observability.md` (modified)
- `_bmad-output/implementation-artifacts/6-6-telemetry-overhead-is-measured-once-and-recorded.md` (modified -- Dev Agent Record, task checkboxes)
- `_bmad-output/implementation-artifacts/epic-6-context.md` (modified -- recompiled; the spine's NFR-6 owner/milestone edit made the cache stale)

## Spec Change Log

- 2026-10-09 — Planning reconciliation (not a review loopback). Task 2's baseline changed from "do not call `configure_observability()`" to "uninstrument after boot", because `config/__init__.py` → `celery_app` calls it on any import of `config`. Line numbers re-pinned in *Reconciliation against the tree*. Known-bad state avoided: a baseline arm that silently remained instrumented.

## Review Triage Log

### 2026-10-09 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 7 (high 0, medium 2, low 5)
- defer: 0
- reject: 16 (high 0, medium 0, low 16)
- addressed_findings:
  - `[medium]` `[patch]` The instrumentation-set pin read only `telemetry`'s namespace, so an instrumentor (or the ASGI middleware) wired up elsewhere in `src/` would grow the measured set unnoticed — added `test_no_other_module_installs_instrumentation`, an AST scan asserting `telemetry.py` is the only `src/` module importing `opentelemetry.instrumentation`, with the same stale-measurement message.
  - `[medium]` `[patch]` A `--settings` module ignoring `DATABASE_URL` would let the child `migrate` a real database — the child now refuses unless the connection is sqlite at the harness's throwaway path.
  - `[low]` `[patch]` `--child` without `--arm`/`--out`, non-positive `--requests`/`--rounds`, negative `--warmup`, too few samples, or a missing `--json-out` directory failed only after the run — added `validate_arguments`, with tests.
  - `[low]` `[patch]` The kill-switch refusal ran only in the parent — the child now refuses too.
  - `[low]` `[patch]` Only the last round's child self-report was kept — rounds of one arm must now agree on instrumentors, middleware, DB vendor and URL.
  - `[low]` `[patch]` A hung child hung the harness — added a 900 s child timeout.
  - `[low]` `[patch]` Docs claimed every method limit biases the figure low, which is unsupported for the WSGI-vs-ASGI limit — reworded to "Limits of the method".

## Auto Run Result

Status: done

- **Summary:** NFR-6 is measured and recorded. `tools/telemetry_overhead.py` runs an instrumented (export-disabled) arm against an uninstrumented baseline obtained by `.uninstrument()` — never `OTEL_SDK_DISABLED` — in alternating child processes; `pixi run bench-telemetry` (dev task, outside `ci`). Measured 2026-10-09 on an Apple M4: median +0.107 ms (+5.5%), p95 +0.864 ms (+33.7%) over 10,000 requests per arm. Recorded with owner (Platform engineering), milestone (before v0.2.0) and the re-measure rule in `docs/observability.md`; the instrumentation-set pin in `tests/unit/test_telemetry.py` is the only re-measure trigger.
- **Files changed:** `tools/telemetry_overhead.py` (new harness); `tests/unit/test_telemetry_overhead.py` (new, pure-function, refusal and argument tests); `tests/unit/test_telemetry.py` (instrumentation-set pin and single-installer pin); `pixi.toml` (`bench-telemetry` task); `docs/observability.md` (`## Instrumentation overhead`); `epic-6-context.md` (recompiled); this story file.
- **Review:** 7 patches applied, 0 deferred, 16 rejected (speculative names such as `BaseInstrumentor`, untested process-spawning half kept out of the suite by design, sqlite URL quoting, dependency bumps not being a trigger per AC #2, per-round variance reporting, and similar).
- **Verification:** `pixi run ci` exit 0 (1616 passed, coverage 97.09%); `pixi run docs` (strict) built; `pixi run -e dev mypy --strict src/ tools/telemetry_overhead.py` clean (the single-file form crashes inside mypy/django-stubs on unmodified files too); post-review smoke run `pixi run bench-telemetry --rounds 1 --requests 20 --warmup 5` exit 0. The published figures predate the review patches, none of which touches the timed loop.
- **Residual risks:** the p95 delta is noisy (an earlier same-day run gave +44%); the route exercises only the Django span; `tools/` is outside coverage and the `typecheck` task, so the harness can rot until the pin next fires.
