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

- [ ] Task 1 — Name the owner and the milestone before measuring anything (AC: #3)
  - [ ] **This story may not invent an owner or a milestone.** The spine lists this as an Open Item: "NFR-6 — telemetry overhead measured once and recorded. No AD; needs an owner and a milestone." Obtain both from the human running the work. If either is missing, stop, record the blocked state in Completion Notes, and escalate — do not name a placeholder or infer an owner from the epic's persona.
  - [ ] Record the owner and the milestone in the new `docs/observability.md` section created in Task 4, with the date.
  - [ ] Note for the caller: the spine's Open Items entry at `ARCHITECTURE-SPINE.md:412` should be updated once both are decided. Editing a planning artifact is a separate, deliberate act — flag it rather than folding it into an implementation commit.

- [ ] Task 2 — Decide how the baseline is obtained, and do not use the kill switch (AC: #1)
  - [ ] NFR-6 says "with export disabled". The baseline for *overhead* additionally needs an uninstrumented run. **Do not obtain it by setting `OTEL_SDK_DISABLED=true`.** That state is stage-1 unconditional refusal condition 3 in the refusal-count table, and once Epic 4 lands, a settings import with it set raises `ImproperlyConfigured` — so a benchmark built on the kill switch works today and breaks the moment the refusal contract ships. Record this reasoning in the harness docstring; it is the single most likely wrong turn in this story.
  - [ ] Obtain the uninstrumented baseline by **not calling `configure_observability()`** in the baseline process. `src/config/observability/__init__.py:62-73` is the single entrypoint call, and instrumentation is installed only from `configure_telemetry` (`src/config/observability/telemetry.py:134-137`). A harness that owns its own process start controls this directly, without touching any environment kill switch and without a `DEBUG` branch.
  - [ ] "Export disabled" for the instrumented arm means simply: neither `OTEL_EXPORTER_OTLP_ENDPOINT` nor `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` set, and `OTEL_TRACES_EXPORTER` unset — `resolve_traces_exporter()` (`telemetry.py:87-101`) then returns `NONE` and no span processor is attached (`:124-129`). This isolates instrumentation cost from network cost, which is what NFR-6 asks for.

- [ ] Task 3 — Build the measurement harness (AC: #1)
  - [ ] Create `tools/telemetry_overhead.py`. `tools/` does not exist yet; the Structural Seed places `tools/materializer/` there as `machinery`, so a benchmark harness at `tools/` inherits `machinery` disposition and never travels into a component. Add no `__init__.py` unless the module needs to be imported rather than run.
  - [ ] Shape: run the reference application's request path N times in each arm — instrumented (`configure_observability()` called, no endpoint set) and baseline (`configure_observability()` not called) — through Django's test client against a fixed DB-free route (`reverse("home")`), discard a warm-up window, and report median and p95 wall time per request per arm plus the delta as an absolute figure and a percentage. Report the sample size, the warm-up count, Python and Django versions, and the platform.
  - [ ] Emit the result through `structlog` as a structured event, and/or write a JSON file the operator can paste into the documentation. **Never `print()`**, never stdlib `logging`.
  - [ ] Enumerate the instrumentation set in the report: the four instrumentors installed at `telemetry.py:134-137` (`Django`, `Celery`, `Psycopg`, `Redis`) plus the `opentelemetry-instrumentation-asgi` presence flag (`pixi.toml:66`), and the pinned OpenTelemetry version range from `pixi.toml:58-60`. AC #2's re-measure trigger is defined against exactly this list.
  - [ ] Add a `bench-telemetry` task to `[feature.dev.tasks]` in `pixi.toml` with `default-environment = "dev"` and a `description`, following the existing task style at `pixi.toml:184-206`. It is a development task, not part of `ci` — do **not** add it to the `ci` `depends-on` chain at `pixi.toml:206`. A benchmark inside the gate makes the gate non-deterministic, and NFR-6 says measured **once**, not every run.
  - [ ] Do not add `COMPONENT_RUNTIME` or any other `COMPONENT_*` variable to the task's `env` or to `[activation.env]` — AD-13 forbids `COMPONENT_*` in `[activation.env]` outright, and locality declaration is Epic 3's work.

- [ ] Task 4 — Record the number alongside the observability documentation (AC: #1, #3)
  - [ ] Add an `## Instrumentation overhead` section to `docs/observability.md` carrying: the measured median and p95 delta, the sample size, the date, the machine class, the exact instrumentation set measured, the named owner, the named milestone, how to reproduce it (`pixi run bench-telemetry`), and the explicit statement that instrumentation is always on and is never conditionally disabled to gain performance.
  - [ ] `docs/observability.md` is already in the mkdocs nav (`mkdocs.yml`), so no nav edit is needed. `pixi run docs` builds with `--strict`; broken links fail it.
  - [ ] NFR-8 — "Documentation travels with what it describes." Record in the section which disposition `docs/observability.md` carries. Epic 8 owns the `.github/`/`docs/` disposition split (FR-37); this is a note for that work, not a change here.

- [ ] Task 5 — Make "re-measured only when the instrumentation set changes" enforceable (AC: #2)
  - [ ] Add a test to `tests/unit/test_telemetry.py` that pins the instrumentation set: collect the names of every attribute of `config.observability.telemetry` ending in `Instrumentor` and assert the sorted result equals the frozen list `["CeleryInstrumentor", "DjangoInstrumentor", "PsycopgInstrumentor", "RedisInstrumentor"]`. The failure message must say: the instrumentation set changed, so NFR-6's measurement is stale — re-run `pixi run bench-telemetry` and update the `## Instrumentation overhead` section of `docs/observability.md`.
  - [ ] Prefer this introspective form over adding a declared-set constant to `src/config/observability/telemetry.py`. `telemetry.py:134-137` is AD-24's declared feature-owned region and Epic 7 wraps those four lines in markers; the fewer edits that file takes, the less Epic 7 has to re-cut. If a constant is nonetheless added, place it **above** `configure_telemetry` and leave lines `:134-137` byte-for-byte unchanged and contiguous.
  - [ ] The "and not otherwise" half is a policy statement, not an assertion — record it in the documentation section as the rule, and make sure the test's failure message is the only thing that ever triggers a re-measure.

- [ ] Task 6 — Run the gate (AC: #1, #2, #3)
  - [ ] `pixi run test`, then `pixi run ci`. Run `pixi run bench-telemetry` separately and once; it is not part of `ci`.

## Dev Notes

### Architecture Constraints

- **NFR-6** — "Telemetry overhead is measured, not assumed — measured once against the reference application, recorded with the observability documentation, re-measured only when the instrumentation set changes." No AD covers it. The spine records it as an Open Item needing an owner and a milestone, and this story is where that is answered or escalated.
- **Spine → Open Items** — "NFR-6 — telemetry overhead measured once and recorded. **No AD; needs an owner and a milestone.**"
- **Spine → Capability → Architecture Map** — Observability (§4.8) "Lives in `src/config/observability/`", governed by "Conventions; FR-45 and NFR-6 are open items below." There is no architectural rule to conform to; the conventions table and NFR-6's own words are the whole constraint.
- **AD-24** — `src/config/observability/telemetry.py` is one of three `core` paths carrying feature-owned regions: "the per-instrumentor calls at `:134-137`". **Verified: the range still holds exactly** — `:134` is `DjangoInstrumentor().instrument()`, `:137` is `RedisInstrumentor().instrument()`. Do not reorder, reformat, merge, wrap or insert between those four lines. Forbidden anywhere in that file: conditional imports, settings-module inheritance, `try/except ImportError`.
- **AD-13** — "**No `COMPONENT_*` variable may appear in `[activation.env]`**, and a gate test asserts it over the materialized `pixi.toml`." The new pixi task must not introduce one.
- **AD-18** — "A single workflow invokes `pixi run ci`, which has never run in CI… `build` off its fortnightly cron." The benchmark is not part of `ci` and must not be scheduled on a cron; NFR-6 says measured once.
- **AD-20** — the coverage floor is ninety percent including templates, everywhere, and "Never a lower floor, a pragma, or a narrowed measurement. The coverage `omit`/`exclude` list is a closed, carrier-declared surface." `tools/` is outside `[tool.coverage.run] include = ["src/**"]` (`pyproject.toml:161`), so the harness is not measured and **no new `omit` entry is needed or permitted**. Adding one would touch the surface AD-20 closes.
- **NFR-8** — "Documentation travels with what it describes — component-facing docs materialize with the component, accelerator-facing docs do not."
- **Deferred (spine)** — traces only at OpenTelemetry 1.44; metrics and the OTLP logs signal are deferred. Do not add a metrics exporter to measure this.
- **Project standards** — Pixi is the only runner: `pixi run python tools/telemetry_overhead.py`, never bare `python`, never `uv`. Python 3.14 only. Full type hints, Google-style docstrings, line length 120, `X | Y` / `list[X]` / `dict[K, V]`. Never `print()`; never stdlib `logging`.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `tools/telemetry_overhead.py` | NEW | The two-arm measurement harness. `tools/` does not exist in the repository today; the Structural Seed places `tools/materializer/` there as `machinery`, so this inherits `machinery` disposition and never travels into a component. |
| `pixi.toml` | UPDATE | Today: `[tasks]` at `:172-179` (runtime), `[feature.dev.tasks]` at `:184-206` (development + harness), `ci = { depends-on = ["test-cov", "lint", "typecheck", "build"] }` at `:206`. Adds one `bench-telemetry` task in `[feature.dev.tasks]` with `default-environment = "dev"` and a `description`. **Preserve:** the `ci` `depends-on` list unchanged; `[activation.env]` at `:145-150` carrying only `COVERAGE_CORE = "ctrace"`; `[environments]` at `:141-143`. Do not add a dependency — everything the harness needs (`pytest`/Django test client, `structlog`) is already present. |
| `docs/observability.md` | UPDATE | Today: 180 lines — "What a log line looks like" (`:7`), "Configuration" (`:37`), "Why export is conditional" (`:51`), "Seeing it work" (`:67`), "What is instrumented" (`:90`), "Configuration is read before Django starts" (`:106`), "Writing logs" (`:118`), "Layout" (`:133`), "Adding metrics or OTLP logs later" (`:150`), "Note on dependencies" (`:161`). Adds `## Instrumentation overhead` with the number, method, owner, milestone and re-measure rule. **Preserve** every existing section, particularly the ASGI warning block at `:95-104`. |
| `tests/unit/test_telemetry.py` | UPDATE | Today: 159 lines; fixtures at `:33-58`, selection/resource/configure coverage at `:62-159`. Adds the instrumentation-set pin whose failure message is the re-measure trigger. **Preserve** the `_clean_otel_env` and `no_side_effects` fixtures. |
| `src/config/observability/telemetry.py` | **No change expected** | Today: the four instrumentor calls at `:134-137`, which the pin introspects. Listed so the dev agent reads and confirms rather than edits. If a declared-set constant is added, it goes above `configure_telemetry` and `:134-137` stay byte-for-byte. |
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

This story creates `tools/`, which the Structural Seed anticipates (`tools/materializer/ # machinery — projections of accelerator.toml`) but which does not exist in the repository today. Placing the benchmark at `tools/telemetry_overhead.py` rather than `tools/materializer/` keeps the materializer's namespace clean for Epic 8. Since `accelerator.toml` does not exist yet, the `machinery` disposition is an intent recorded here, not a declared fact — Epic 7 declares it, and AD-2's rule that "unlisted defaults to `machinery`" means the default is already correct even if nothing is written. Record the intended disposition in Completion Notes so Epic 7's carrier entry is unambiguous.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.6] — story statement and all three acceptance-criteria blocks.
- [Source: _bmad-output/planning-artifacts/epics.md#NFR-6] — "Telemetry overhead is measured, not assumed — measured once against the reference application, recorded with the observability documentation, re-measured only when the instrumentation set changes."
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6] — "Owns two of the three ownerless open items — FR-45's collector stub design and NFR-6's telemetry-overhead measurement."
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — `OTEL_SDK_DISABLED` true is stage-1 unconditional refusal condition 3, which is why the baseline may not use the kill switch.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Open Items] — "NFR-6 — telemetry overhead measured once and recorded. No AD; needs an owner and a milestone."
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Capability → Architecture Map] — Observability is governed by conventions; FR-45 and NFR-6 are open items.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24] — the `telemetry.py:134-137` region citation and the forbidden mechanisms.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20] — the closed coverage `omit`/`exclude` surface.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13] — no `COMPONENT_*` in `[activation.env]`.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Structural Seed] — `tools/materializer/` as `machinery`.
- [Source: src/config/observability/telemetry.py:87-101,124-140] — exporter resolution, the processor branch, and the four instrumentor calls.
- [Source: src/config/observability/__init__.py:62-73] — `configure_observability`, the single entrypoint call the baseline arm omits.
- [Source: pixi.toml:58-69,141-150,184-206] — the OpenTelemetry pins, `[environments]`, `[activation.env]`, and the dev task/`ci` block.
- [Source: pyproject.toml:160-169] — `[tool.coverage.run] include = ["src/**"]` and the closed `omit` list.
- [Source: docs/observability.md:1-180] — the existing section structure the new section joins.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
