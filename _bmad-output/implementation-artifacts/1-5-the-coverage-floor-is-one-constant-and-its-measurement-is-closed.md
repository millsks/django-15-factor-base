# Story 1.5: The coverage floor is one constant and its measurement is closed

Status: ready-for-dev

## Story

As a platform engineer,
I want a single global coverage floor with an asserted, closed measurement surface,
so that the only residue detector this product has cannot be disabled by a one-line change nobody reads as security-relevant.

## Acceptance Criteria

**Traceability:** AD-20 · supports FR-29 · CG-1

1. **Given** Python 3.12 and later default to a core without the dynamic file tracer
   **When** a gate run executes
   **Then** `COVERAGE_CORE=ctrace` is in force
   **And** a test asserts it during the run rather than trusting it to be inherited

2. **Given** a template rendered by a test
   **When** coverage reports
   **Then** it reports non-zero
   **And** template measurement is thereby proven real rather than silently reporting zero

3. **Given** an omit or exclude list exists
   **When** the gate runs
   **Then** the effective list equals a declared list held in exactly one place
   **And** a test asserts that equality in both directions

4. **Given** the floor is ninety percent including templates
   **When** any gate runs
   **Then** the floor is ninety percent
   **And** it is never lowered, never made per-directory, and never cleared by a pragma on unreached code

## Tasks / Subtasks

- [ ] Task 1 — Assert `COVERAGE_CORE=ctrace` is in force during the run (AC: #1)
  - [ ] `COVERAGE_CORE = "ctrace"` is already declared at `pixi.toml:150` in `[activation.env]`, with a comment at `:146-149` explaining that `django_coverage_plugin` is a dynamic file tracer needing `sys.settrace`, and that Python 3.12+ defaults to the `sysmon` core, under which templates "get discovered but never traced, and silently report 0%". Do not remove or relocate that declaration.
  - [ ] The AC demands assertion *during the run*, not inspection of the manifest. Write a test that interrogates the live coverage session, not `os.environ` alone: obtain the active session with `coverage.Coverage.current()`, and assert the tracer core in use is the C trace core (`coverage.env` / the collector's core name, whichever the installed `coverage >=7.15,<8` exposes — the dev agent must determine the exact accessor empirically rather than guessing an attribute name).
  - [ ] Also assert `os.environ["COVERAGE_CORE"] == "ctrace"` as a second, weaker check. Both together satisfy "rather than trusting it to be inherited"; the environment check alone does not.
  - [ ] If `coverage.Coverage.current()` returns `None` — the suite invoked without `--cov` — the test must be conditional on a coverage session existing, expressed with `pytest.skip` **only** for the no-coverage case and with a comment naming the reason. Never `@pytest.mark.skip` and never `xfail`.

- [ ] Task 2 — Prove template measurement is real (AC: #2)
  - [ ] `[tool.coverage.run] plugins = ["django_coverage_plugin"]` at `pyproject.toml:173` and `[tool.coverage.django_coverage_plugin] template_extensions = "html"` at `:175-178` are already configured, as is `TEMPLATES[0]["OPTIONS"]["debug"] = True` in `src/config/settings/test.py`. All three are prerequisites; verify each still holds and do not change them.
  - [ ] Write a test that renders a known template through the real request/response cycle and then asserts, from the live coverage data, that the template file has recorded executed lines. `tests/integration/test_template_rendering.py` already drives the test client through `src/django_service/templates/`; use one of its routes as the rendered surface. Choose a route that **survives revision 3** — `reverse("users:detail", kwargs={"username": ...})` → `users/user_detail.html`, or a rendered 404 → `404.html`. Do **not** use `reverse("home")` or `reverse("about")`: AD-29 deletes the `home` and `about` demonstration pages and their `TemplateView`s, so a coverage assertion anchored on them would have to be rewritten in Epic 7. `templates/users/`, the error templates and `base.html` are `core` and present in every combination.
  - [ ] The assertion is on coverage data, not on the HTTP response: obtain the measured file list from the active `Coverage` object and assert that at least one `.html` path under `src/django_service/templates/` appears with a non-empty executed-line set. A test that only checks the page returns 200 does not satisfy AC #2 — that is what `test_template_rendering.py` already does and it would pass under `sysmon` with zero template coverage.

- [ ] Task 3 — Declare the omit list in exactly one place and reconcile it both ways (AC: #3)
  - [ ] The single declaration site for this story is `pyproject.toml` `[tool.coverage.run] omit` (`:162-169`). Add a comment above it stating it is the **closed, declared** surface under AD-20, that adding an entry is a deliberate act, and that `tests/unit/test_coverage_policy.py` fails until the declaration and the effective configuration agree.
  - [ ] The effective list after Story 1.4 lands is: `*/migrations/*`, `*/tests/*`, `**/*.egg-info/**`, `src/config/wsgi.py`, `src/config/asgi.py`. Story 1.4 removes `src/config/websocket.py` from it. If Story 1.4 has not landed, this story must not declare the websocket entry as legitimate — coordinate the ordering.
  - [ ] Write the reconciliation as two directions in the test: every entry parsed from `pyproject.toml` appears in the effective `Coverage` configuration's `run_omit`, **and** every entry in the effective configuration appears in the parsed declaration. Set equality in one assertion is acceptable only if the failure message names the offending entries in both directions.
  - [ ] Also reconcile the exclude side: assert `[tool.coverage.report] exclude_lines` / `exclude_also` is either absent from `pyproject.toml` (it is today) or equal to the declared list. An empty declared exclude surface is still a declared surface — assert the absence explicitly so adding one later fails the gate rather than passing silently.
  - [ ] `[tool.coverage.run] include = [ "src/**" ]` at `:161` bounds measurement to `src/`. Treat it as part of the closed surface: assert its exact value, so narrowing it (the other way to blind the detector) also fails.
  - [ ] **Record, do not silently resolve, the spine's open item on this line.** `include = ["src/**"]` also means `tools/materializer/` and `tools/harness/` — both now in the Structural Seed, both `machinery`, neither existing yet — are unmeasured by default. The spine names this as needing "a decision, not a default", because adding measurable code outside the measured set is the silent narrowing CG-1 forbids. This story does not take that decision; it makes the value asserted, so widening `include` when those directories arrive is a deliberate change to a declared surface rather than an unnoticed one. State this in the comment above the declaration and in the test module docstring.

- [ ] Task 4 — Make the floor a single constant (AC: #4)
  - [ ] The floor lives once today, as `--cov-fail-under=90` inside the `test-cov` task at `pixi.toml:196`. Keep it there — it is the single site — and add a comment beside it recording AD-20: ninety percent including templates, everywhere, never lowered, never per-directory.
  - [ ] Assert the constant in the test: parse `pixi.toml` and assert `test-cov`'s `cmd` contains `--cov-fail-under=90` exactly, with no second `--cov-fail-under` anywhere in the manifest.
  - [ ] Assert there is no competing declaration: `[tool.coverage.report] fail_under` must be absent from `pyproject.toml`. If it is ever added it becomes a second site, which is exactly what AC #4's "one constant" forbids.
  - [ ] Assert no per-directory narrowing: no `[tool.coverage.paths]` remapping and no per-package `fail_under`.
  - [ ] Guard the pragma route: grep `src/` and assert no line carries `# pragma: no cover`. AC #4 forbids clearing the floor "by a pragma on unreached code". If a genuine need arises later, it must be added as a declared entry in the closed exclude surface, not as a scattered comment.

- [ ] Task 5 — Tests (AC: #1, #2, #3, #4)
  - [ ] New `tests/unit/test_coverage_policy.py`: the manifest-level assertions from Tasks 3 and 4 (declared omit list, `include`, absent `exclude`, absent `fail_under`, the single `--cov-fail-under=90`, no `# pragma: no cover` in `src/`). No I/O beyond reading repository files; no marker.
  - [ ] New `tests/integration/test_coverage_measurement.py`, every test marked `@pytest.mark.integration`: the live-session assertions from Tasks 1 and 2 (`ctrace` in force during the run; a rendered template reports non-zero executed lines; the effective `Coverage` configuration's omit list equals the declared one). These need a running coverage session and a rendered response, so they are integration, not unit.
  - [ ] Both files resolve repository paths from `Path(__file__).resolve().parents[2]`, matching `tests/unit/test_dependency_policy.py:11`.

## Dev Notes

### Architecture Constraints

- **AD-20 — The coverage floor is a single global constant, and what it measures is closed.** Rule, verbatim: "Ninety percent, including templates, everywhere. `COVERAGE_CORE=ctrace` travels with every combination and a test asserts it is in force during a gate run. Never a lower floor, a pragma, or a narrowed measurement. **The coverage `omit`/`exclude` list is a closed, carrier-declared surface** subject to two-way reconciliation, and the gate asserts the effective omit list equals the declared one — otherwise an epic clears its floor with one line and the only residue detector the product has goes blind."
- **AD-20 Prevents:** "a per-combination floor becoming the place a structurally sparse combination hides; and the narrowing that is already precedented in this tree — `[tool.coverage.run] omit` — being used to clear the floor while every stated rule still passes." The precedent AD-20 names is the very list this story closes.
- **AD-20 — bring-up mode, time-boxed:** "`test-cov` already carries `--cov-fail-under=90`, so the floor is hard the moment the gate consolidates. Until the materializer has reported all six numbers once, materialized-combination gates run with the floor advisory and the numbers published as an artifact. The exit condition is that report." **Bring-up mode applies only to materialized-combination gates, which do not exist until Epic 8.** For the reference application the floor is hard now. Do not implement an advisory mode in this story.
- **FR-29:** "The orphan-detection property survives into the harness — template-inclusive coverage with `COVERAGE_CORE` pinned to the C trace core, plus carrier reconciliation for static assets and settings fragments." The carrier half is Epic 7; the coverage half is this story.
- **CG-1** is the constraint this defends; template coverage is the only residue detector for content no import graph, linter or dependency analyzer can see.

### Forward context — this declaration moves

`epics.md:227` and `epics.md:347`: **the coverage omit list authored here moves into `accelerator.toml` in Epic 7 "without changing any assertion's meaning."** Write the declaration and its two-way reconciliation so the *source of the declared list* is a single, easily relocated read — one function that returns the declared list, called by every assertion — rather than a `tomllib` call inlined into each test. Epic 7 then changes only where that function reads from. Note this intent in a comment at the declaration site and in the test module docstring.

### Source Tree — files to touch

| Path | NEW or UPDATE | What changes |
| --- | --- | --- |
| `pyproject.toml` | UPDATE | `[tool.coverage.run]` at `:160-173`: `include = ["src/**"]` (`:161`), `omit` (`:162-169`), `plugins = ["django_coverage_plugin"]` (`:173`) and the comment at `:170-172` explaining the `TEMPLATES ... debug = True` and `COVERAGE_CORE=ctrace` prerequisites. `[tool.coverage.django_coverage_plugin] template_extensions = "html"` at `:175-178`. This story adds the closed-surface comment above `omit`; it changes no value. Story 1.4 removes the `websocket.py` entry. |
| `pixi.toml` | UPDATE | `[activation.env] COVERAGE_CORE = "ctrace"` at `:145-150` — unchanged, comment preserved. `test-cov` at `:196` carries `--cov-fail-under=90` — unchanged, gains the AD-20 rationale comment. |
| `src/config/settings/test.py` | UNCHANGED — verify only | Sets `TEMPLATES[0]["OPTIONS"]["debug"] = True`, without which the template plugin measures nothing. Confirm; change nothing. |
| `tests/unit/test_coverage_policy.py` | NEW | Manifest-level closed-surface and single-floor assertions. |
| `tests/integration/test_coverage_measurement.py` | NEW | Live-session assertions: `ctrace` in force, template lines non-zero, effective omit equals declared. |
| `tests/integration/test_template_rendering.py` | UNCHANGED — reference only | Already drives the test client through project templates; reuse a route from it as the rendered surface. Do not modify it. |

**Verified today (2026-08-15):** `COVERAGE_CORE = "ctrace"` is at `pixi.toml:150` in `[activation.env]`. `--cov-fail-under=90` appears exactly once, at `pixi.toml:196`. `[tool.coverage.report]` does not exist in `pyproject.toml`; there is no `fail_under` and no `exclude_lines`. `coverage >=7.15,<8` and `django_coverage_plugin >=3.2,<4` are in `[feature.dev.dependencies]` at `pixi.toml:109-110`.

### Testing Requirements

- `tests/unit/test_coverage_policy.py`: pure file parsing, milliseconds, no marker.
- `tests/integration/test_coverage_measurement.py`: `@pytest.mark.integration` on every test (marker declared at `pyproject.toml:155-157`). Reads live coverage state and renders a template through the test client; must leave no state behind.
- Specific assertions the ACs demand: the C trace core is the collector in use during the run; `os.environ["COVERAGE_CORE"] == "ctrace"`; at least one `src/django_service/templates/**/*.html` file has non-empty executed lines; declared omit ⊇ effective omit and effective omit ⊇ declared omit; `include == ["src/**"]`; exactly one `--cov-fail-under=90`; no `fail_under` in `pyproject.toml`; no `# pragma: no cover` in `src/`.
- Coverage floor is 90% including templates (AD-20) and this story is what makes that claim checkable. The new tests count toward the floor themselves.
- Test disposition (spine §Consistency Conventions): both files cover the gate's measurement surface; disposition is assigned in Epic 7.

#### Project Structure Notes

No structural change. The Structural Seed's `accelerator.toml` — the eventual home of this declaration — does not exist yet (Epic 7 Story 7.1). Keeping the declaration in `pyproject.toml` today is the correct interim state under AD-1's rule that the carrier is the single catalogue *once it exists*; the move is explicitly planned and must not change any assertion's meaning.

The Structural Seed is **a shape, not an inventory** (AD-2): the two `machinery` directories it now draws — `tools/materializer/` and `tools/harness/`, the six-combination verification runner — are outside the `include = ["src/**"]` measurement bound and outside anything this story measures. That is the spine's open item, recorded above in Task 3 and not decided here.

Variance: AD-20 speaks of "carrier-declared". Until the carrier exists, "held in exactly one place" is satisfied by `pyproject.toml [tool.coverage.run]`. Record that reading in the test module docstring so Epic 7's author does not read the interim site as a second declaration.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.5]
- [Source: _bmad-output/planning-artifacts/epics.md:227] — three declarations move into `accelerator.toml` in Epic 7 without changing meaning.
- [Source: _bmad-output/planning-artifacts/epics.md:347] — Story 1.5's omit list is one of them.
- [Source: _bmad-output/planning-artifacts/epics.md:66] — FR-29.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-30] — coverage defends SC-2; the immovable-core suite defends SC-7.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
