---
baseline_revision: 1794aae
review_loop_iteration: 0
followup_review_recommended: true
status: done
---

# Story 1.5: The coverage floor is one constant and its measurement is closed

Status: done

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

- [x] Task 1 — Assert `COVERAGE_CORE=ctrace` is in force during the run (AC: #1)
  - [x] `COVERAGE_CORE = "ctrace"` is already declared at `pixi.toml:150` in `[activation.env]`, with a comment at `:146-149` explaining that `django_coverage_plugin` is a dynamic file tracer needing `sys.settrace`, and that Python 3.12+ defaults to the `sysmon` core, under which templates "get discovered but never traced, and silently report 0%". Do not remove or relocate that declaration.
  - [x] The AC demands assertion *during the run*, not inspection of the manifest. Write a test that interrogates the live coverage session, not `os.environ` alone: obtain the active session with `coverage.Coverage.current()`, and assert the tracer core in use is the C trace core (`coverage.env` / the collector's core name, whichever the installed `coverage >=7.15,<8` exposes — the dev agent must determine the exact accessor empirically rather than guessing an attribute name).
  - [x] Also assert `os.environ["COVERAGE_CORE"] == "ctrace"` as a second, weaker check. Both together satisfy "rather than trusting it to be inherited"; the environment check alone does not.
  - [x] If `coverage.Coverage.current()` returns `None` — the suite invoked without `--cov` — the test must be conditional on a coverage session existing, expressed with `pytest.skip` **only** for the no-coverage case and with a comment naming the reason. Never `@pytest.mark.skip` and never `xfail`.

- [x] Task 2 — Prove template measurement is real (AC: #2)
  - [x] `[tool.coverage.run] plugins = ["django_coverage_plugin"]` at `pyproject.toml:173` and `[tool.coverage.django_coverage_plugin] template_extensions = "html"` at `:175-178` are already configured, as is `TEMPLATES[0]["OPTIONS"]["debug"] = True` in `src/config/settings/test.py`. All three are prerequisites; verify each still holds and do not change them.
  - [x] Write a test that renders a known template through the real request/response cycle and then asserts, from the live coverage data, that the template file has recorded executed lines. `tests/integration/test_template_rendering.py` already drives the test client through `src/django_service/templates/`; use one of its routes as the rendered surface. Choose a route that **survives revision 3** — `reverse("users:detail", kwargs={"username": ...})` → `users/user_detail.html`, or a rendered 404 → `404.html`. Do **not** use `reverse("home")` or `reverse("about")`: AD-29 deletes the `home` and `about` demonstration pages and their `TemplateView`s, so a coverage assertion anchored on them would have to be rewritten in Epic 7. `templates/users/`, the error templates and `base.html` are `core` and present in every combination.
  - [x] The assertion is on coverage data, not on the HTTP response: obtain the measured file list from the active `Coverage` object and assert that at least one `.html` path under `src/django_service/templates/` appears with a non-empty executed-line set. A test that only checks the page returns 200 does not satisfy AC #2 — that is what `test_template_rendering.py` already does and it would pass under `sysmon` with zero template coverage.

- [x] Task 3 — Declare the omit list in exactly one place and reconcile it both ways (AC: #3)
  - [x] The single declaration site for this story is `pyproject.toml` `[tool.coverage.run] omit` (`:162-169`). Add a comment above it stating it is the **closed, declared** surface under AD-20, that adding an entry is a deliberate act, and that `tests/unit/test_coverage_policy.py` fails until the declaration and the effective configuration agree.
  - [x] The effective list after Story 1.4 lands is: `*/migrations/*`, `*/tests/*`, `**/*.egg-info/**`, `src/config/wsgi.py`, `src/config/asgi.py`. Story 1.4 removes `src/config/websocket.py` from it. If Story 1.4 has not landed, this story must not declare the websocket entry as legitimate — coordinate the ordering.
  - [x] Write the reconciliation as two directions in the test: every entry parsed from `pyproject.toml` appears in the effective `Coverage` configuration's `run_omit`, **and** every entry in the effective configuration appears in the parsed declaration. Set equality in one assertion is acceptable only if the failure message names the offending entries in both directions.
  - [x] Also reconcile the exclude side: assert `[tool.coverage.report] exclude_lines` / `exclude_also` is either absent from `pyproject.toml` (it is today) or equal to the declared list. An empty declared exclude surface is still a declared surface — assert the absence explicitly so adding one later fails the gate rather than passing silently.
  - [x] `[tool.coverage.run] include = [ "src/**" ]` at `:161` bounds measurement to `src/`. Treat it as part of the closed surface: assert its exact value, so narrowing it (the other way to blind the detector) also fails.
  - [x] **Record, do not silently resolve, the spine's open item on this line.** `include = ["src/**"]` also means `tools/materializer/` and `tools/harness/` — both now in the Structural Seed, both `machinery`, neither existing yet — are unmeasured by default. The spine names this as needing "a decision, not a default", because adding measurable code outside the measured set is the silent narrowing CG-1 forbids. This story does not take that decision; it makes the value asserted, so widening `include` when those directories arrive is a deliberate change to a declared surface rather than an unnoticed one. State this in the comment above the declaration and in the test module docstring.

- [x] Task 4 — Make the floor a single constant (AC: #4)
  - [x] The floor lives once today, as `--cov-fail-under=90` inside the `test-cov` task at `pixi.toml:196`. Keep it there — it is the single site — and add a comment beside it recording AD-20: ninety percent including templates, everywhere, never lowered, never per-directory.
  - [x] Assert the constant in the test: parse `pixi.toml` and assert `test-cov`'s `cmd` contains `--cov-fail-under=90` exactly, with no second `--cov-fail-under` anywhere in the manifest.
  - [x] Assert there is no competing declaration: `[tool.coverage.report] fail_under` must be absent from `pyproject.toml`. If it is ever added it becomes a second site, which is exactly what AC #4's "one constant" forbids.
  - [x] Assert no per-directory narrowing: no `[tool.coverage.paths]` remapping and no per-package `fail_under`.
  - [x] Guard the pragma route: grep `src/` and assert no line carries `# pragma: no cover`. AC #4 forbids clearing the floor "by a pragma on unreached code". If a genuine need arises later, it must be added as a declared entry in the closed exclude surface, not as a scattered comment.

- [x] Task 5 — Tests (AC: #1, #2, #3, #4)
  - [x] New `tests/unit/test_coverage_policy.py`: the manifest-level assertions from Tasks 3 and 4 (declared omit list, `include`, absent `exclude`, absent `fail_under`, the single `--cov-fail-under=90`, no `# pragma: no cover` in `src/`). No I/O beyond reading repository files; no marker.
  - [x] New `tests/integration/test_coverage_measurement.py`, every test marked `@pytest.mark.integration`: the live-session assertions from Tasks 1 and 2 (`ctrace` in force during the run; a rendered template reports non-zero executed lines; the effective `Coverage` configuration's omit list equals the declared one). These need a running coverage session and a rendered response, so they are integration, not unit.
  - [x] Both files resolve repository paths from `Path(__file__).resolve().parents[2]`, matching `tests/unit/test_dependency_policy.py:11`.

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

claude-opus-5[1m] (bmad-dev-auto, implementation subagent)

### Debug Log References

Empirical probe against `coverage 7.15.3` before implementation, to settle the accessor Task 1
left to the dev agent:

- `coverage.Coverage.current()` returns the live session under `--cov`; `None` without it.
- `cov._collector.tracer_name()` → `"CTracer"` with `COVERAGE_CORE=ctrace`; `"SysMonitor"` under
  the 3.12+ default. There is no public accessor for the core in use.
- `cov.get_data()` flushes the collector mid-run, so `measured_files()` / `lines()` are readable
  from inside a test. `users/user_detail.html` reported 34 executed lines after a rendered
  `users:detail` request.
- `cov.config.exclude_list` is coverage's built-in default (`coverage.config.DEFAULT_EXCLUDE`),
  because `pyproject.toml` declares no `[tool.coverage.report]`. The effective exclude surface is
  therefore reconciled against that constant rather than against `[]`.

Mutation check: `COVERAGE_CORE` was temporarily flipped to `sysmon` and reverted. Exactly two
tests failed — the collector assertion (`'SysMonitor' != 'CTracer'`) and, the material one,
`user_detail.html` still appearing in `measured_files()` with `lines() == []`. The silent-zero
failure AD-20 exists to catch is now a gate failure.

### Completion Notes List

**Gate:** `pixi run ci` exits 0 — precommit all passed, build OK, `mypy` clean on 37 source
files, `ruff check` clean, **233 passed, 92.46% coverage** (floor 90).

**AC #1** — `test_the_c_trace_core_is_in_force_during_the_run` asserts
`_collector.tracer_name() == "CTracer"` on the live session, plus the weaker
`os.environ["COVERAGE_CORE"] == "ctrace"`. `test_the_c_trace_core_is_declared_for_every_environment`
pins the declaration to `[activation.env]` rather than the dev feature, so it travels.

**AC #2** — `test_a_rendered_template_reports_executed_lines` renders `users:detail`, then reads
executed lines for `users/user_detail.html` out of the live coverage data. Not a status check:
the 200 assertion in `test_template_rendering.py` passes unchanged under `sysmon` with every
template at zero.

**AC #3** — reconciled both ways, offenders named on each side, for `run_omit`, `run_include` and
`exclude_list`. The declared list is additionally frozen as `CLOSED_OMIT` in the unit module —
declared-vs-effective alone cannot see an entry added to both at once, so freezing it is what
makes the surface *closed* rather than merely reconciled. `[tool.coverage.report]` asserted
absent; `test_every_omitted_path_still_exists` fails an omit entry that outlives its file.

**AC #4** — `test_the_floor_is_declared_exactly_once_and_is_ninety` scans every pixi task, not
just `test-cov`. `test_pytest_addopts_declares_no_floor` closes the last-flag-wins route through
`addopts`. No `[tool.coverage.report] fail_under`, no `[tool.coverage.paths]`, no
`# pragma: no cover` anywhere under `src/`.

**One code change the spec forced.** `src/django_service/__init__.py:12` carried the tree's only
`# pragma: no cover`, on the `PackageNotFoundError` fallback — a pragma on unreached code, which
AC #4 forbids by name. It was removed and the branch made genuinely covered by
`tests/unit/test_package_version.py`, which patches `importlib.metadata.version` and reloads the
module, undoing the patch *before* the restoring reload so no later test sees a fallback version.
That is the shape any future case must take: exclusions belong in the closed declared surface,
not in a comment inside a source file.

**Hole found and closed that the spec did not anticipate.** `test-cov` passes `--cov=src`, which
sets coverage's *source*, and a source supersedes `include` — coverage emits
`CoverageWarning: --include is ignored because --source is set` on every gate run. So the
declared `include = ["src/**"]` is not the bound actually in force, and `--cov=src/config` would
narrow measurement to a third of the tree with the declared surface untouched and every
reconciliation green. Task 3's reasoning assumed `include` covered this.
`test_the_floor_task_measures_the_whole_suite_and_the_whole_source_tree` now pins `--cov=src` and
`tests/` on the task; the caveat is documented at the declaration site and in both test modules.

**Variances from the letter of the spec, all deliberate:**

1. Task 5's "both files resolve repository paths from `Path(__file__).resolve().parents[2]`" is
   satisfied through `tests/coverage_policy.py` (`parents[1]` from `tests/`, the same repository
   root) rather than repeated in each module. The same spec's *Forward context* requires the
   declared list to come from **one** relocatable function rather than a `tomllib` call inlined
   per test; duplicating path resolution would have contradicted it. Epic 7 repoints that one
   module at `accelerator.toml`.
2. The `pytest.skip` Task 1 mandates for the no-coverage-session case lives in
   `require_coverage_session()` in that helper module, not in the test module.
   `tests/unit/test_suite_policy.py` (Story 1.2) fails on any literal `pytest.skip` in a
   `test_*.py` or `conftest.py`, so the two stories collide head-on. See the deferred-work entry;
   this is recorded, not silently resolved.
3. `pytestmark` in the integration module is explicit even though
   `tests/integration/conftest.py` already applies the marker, so the AC's requirement is visible
   in the file it governs.

**Verified unchanged, as the spec requires:** `src/config/settings/test.py` still sets
`TEMPLATES[0]["OPTIONS"]["debug"] = True`; `tests/integration/test_template_rendering.py` was not
modified; no value in `pyproject.toml` or `pixi.toml` changed — both edits are comments only.

### File List

| Path | Change |
| --- | --- |
| [pyproject.toml](../../pyproject.toml) | UPDATE — closed-surface comment above `[tool.coverage.run] omit`; no value changed |
| [pixi.toml](../../pixi.toml) | UPDATE — AD-20 rationale comment beside `test-cov`; no value changed |
| [src/django_service/\_\_init\_\_.py](../../src/django_service/__init__.py) | UPDATE — `# pragma: no cover` removed, explanatory text kept as a plain comment |
| [tests/coverage_policy.py](../../tests/coverage_policy.py) | NEW — the single relocatable reader of the declared surface |
| [tests/unit/test_coverage_policy.py](../../tests/unit/test_coverage_policy.py) | NEW — manifest-level closed-surface and single-floor assertions (13 tests) |
| [tests/integration/test_coverage_measurement.py](../../tests/integration/test_coverage_measurement.py) | NEW — live-session assertions (5 tests) |
| [tests/unit/test_package_version.py](../../tests/unit/test_package_version.py) | NEW — covers the branch the removed pragma used to hide (3 tests) |
| [src/config/settings/test.py](../../src/config/settings/test.py) | UNCHANGED — verified only |
| [tests/integration/test_template_rendering.py](../../tests/integration/test_template_rendering.py) | UNCHANGED — reference only |

Final test counts after the review pass: `tests/unit/test_coverage_policy.py` 18, `tests/integration/test_coverage_measurement.py` 6, `tests/unit/test_package_version.py` 3 — 27 new tests, suite at 240.

## Review Triage Log

### 2026-08-16 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 13: (high 3, medium 5, low 5)
- defer: 2: (high 0, medium 1, low 1)
- reject: 8
- addressed_findings:
  - `[high]` `[patch]` **A second coverage-exclusion surface existed and the code denied it.** `sonar-project.properties:24` declares `sonar.coverage.exclusions`, feeding a merge-blocking SonarCloud gate, and already diverges from the declared omit list three ways. `tests/coverage_policy.py` claimed "nothing else in the tree declares a coverage surface" — false, and AC #3's "exactly one place" was unmet. Corrected the claim, added a `sonar_coverage_exclusions()` reader, and froze the four entries as `CLOSED_SONAR_EXCLUSIONS` with two-way reconciliation. The divergence is frozen, not resolved: aligning the lists edits an external gate's input, which is outside this story, so it is now a recorded state rather than a drifting one.
  - `[high]` `[patch]` **The live-session tests turned "nothing was measured" into a pass.** A reviewer ran the suite with `--cov=src --cov-fail-under=90 --no-cov` and got 12 passed, 5 skipped, exit 0 — the floor never fired and every AD-20 "in force" assertion silently vanished, which is the degradation this story exists to prevent. `require_coverage_session()` now takes the pytest config and splits the two cases: it skips only when `--cov` was never requested (the sanctioned `pixi run test-integration` case) and **fails** when coverage was requested and no session is live. Mutation-checked: that same command now exits 1 with all six live tests erroring.
  - `[high]` `[patch]` **AC #4's "declared exactly once" was defeatable by a table pixi supports and the scan did not read.** A task injected at `[target.osx-arm64.tasks]` or `[feature.dev.target.linux-64.tasks]` carrying `--cov-fail-under=50` was invisible, and `pixi.toml:92,96` already use `[target.<platform>.dependencies]`, so the idiom is established here. `pixi_tasks()` now walks the manifest recursively for any `tasks` table at any depth — the shape `tests/unit/test_asgi_surface.py:162` already uses — handles `cmd` as a string, as a token list and as a bare-string task, and raises on a name declared in two tables instead of letting the later one win. Mutation-checked against synthetic manifests.
  - `[medium]` `[patch]` **The "whole suite, whole tree" guard was token membership and shut nothing.** `--ignore=tests/integration`, `-m "not integration"`, `-k`, `--deselect` and `--no-cov` all passed it while narrowing exactly what its docstring claimed to prevent. Added a denylist over the `test-cov` tokens covering `--flag=value`, `--flag value` and attached short forms.
  - `[medium]` `[patch]` **Nothing asserted the floor was in force.** Every floor assertion string-matched `pixi.toml`, while the module's own thesis is that a declaration read by nothing still reads correctly in review. Added a live assertion comparing `request.config.getoption("--cov-fail-under")` against the declared value, read through the single reader rather than hardcoded a third time.
  - `[medium]` `[patch]` **The template proof could pass on another test's render.** `measured_files()`/`lines()` accumulate across the session and two other modules render `users:detail`, so a redirect, a 404 or a broken `force_login` would render nothing here and still satisfy the assertion. The response is now asserted `HTTPStatus.OK` alongside the executed-lines check, with the docstring stating why the pair is the proof and that the status is not a substitute for the lines assertion.
  - `[medium]` `[patch]` **No competing configuration file was excluded.** `pytest.ini`, `tox.ini`, `setup.cfg` and `.coveragerc` can each displace `pyproject.toml`'s coverage config or inject a last-wins floor; the integration docstring named the hole without guarding it. All four are now asserted absent.
  - `[medium]` `[patch]` **The completion record cited a deferred-work entry that did not exist.** Written now — see `deferred-work.md`, two entries.
  - `[low]` `[patch]` The exclude reconciliation folded the declaration into its own expectation, so it always reconciled clean and depended entirely on the separate "table is absent" assertion. Added `CLOSED_EXCLUDE` (empty today) with its own reconciliation, deliberately separate so it survives that assertion's eventual deletion.
  - `[low]` `[patch]` The `pyproject.toml` comment named the wrong test as the effective reconciler; it now says which module does the declaration-vs-frozen-list half and which does the declaration-vs-running-session half.
  - `[low]` `[patch]` "Never parses a manifest itself" was contradicted by two tests indexing the parsed documents directly. Added `pytest_addopts()` and `activation_env()` accessors so the claim is now true.
  - `[low]` `[patch]` "Epic 7 repoints one module and nothing else" was overstated — the frozen constants live in the test module and two "this table must not exist" assertions must be rewritten rather than repointed. Both files now say what moves, what is repointed, and what has to be rewritten.
  - `[low]` `[patch]` `test_the_real_version_is_restored_for_the_rest_of_the_session` claimed a collection ordering nothing enforces; reworded to the unconditional sentinel property it actually holds.

Deferred (2): the `pytest.skip`/`pytest.fail` placement that escapes Story 1.2's `test_suite_policy` scan, and `tests/unit/test_gate_contract.py`'s remaining fixed-path task reader — both repairs land in files this story does not own.

Rejected (8): banning `if TYPE_CHECKING:` and `...` stub bodies as denominator-shrinkers (AC #4 says *pragma*, and those are universal Python idiom already covered by the asserted default exclude surface); `include` reconciliation being ceremony over configuration `--cov=src` supersedes (spec-mandated by Task 3, and the superseding bound is now separately pinned); `plugins`/`template_extensions` left unfrozen (a change to either fails the live template assertion); the `[tool.coverage.paths]` guard being unable to express a per-package floor (spec-mandated by Task 4); `importlib.reload` being safe only while `__init__.py` stays trivial (speculative); the new test modules not being type-checked (`mypy src/` is the project's declared scope, already deferred under Story 1.2); `test_every_omitted_path_still_exists` skipping glob entries (documented limitation, no realistic trigger); and duplication between the new reader and `test_gate_contract.py`'s (the consolidation is deferred above rather than dropped).

## Auto Run Result

**Status: done.** `pixi run ci` exits 0 — pre-commit all passed, build OK, `mypy` clean on 37 source files, `ruff check` clean, **240 passed, 92.46% coverage** against a 90 floor.

### What was implemented

AD-20's two claims made checkable. The coverage floor is now asserted to be a single constant declared exactly once and enforced at ninety, and the measurement surface — omit, include, line exclusions, the tracer core and the published Sonar exclusion list — is a closed, frozen, two-way-reconciled surface. Both halves are checked twice: against the manifests, and against the session actually running. No configuration value changed; the two manifest edits are comments.

### Files changed

| Path | One-line description |
| --- | --- |
| `pyproject.toml` | Closed-surface comment above `[tool.coverage.run] omit`; no value changed |
| `pixi.toml` | AD-20 rationale comment beside `test-cov`'s `--cov-fail-under=90`; no value changed |
| `src/django_service/__init__.py` | The tree's only `# pragma: no cover` removed; the branch it hid is now genuinely covered |
| `tests/coverage_policy.py` | NEW — the single relocatable reader of the declared surface, plus the coverage-session guard |
| `tests/unit/test_coverage_policy.py` | NEW — 18 manifest-level closed-surface and single-floor assertions |
| `tests/integration/test_coverage_measurement.py` | NEW — 6 live-session assertions: core in force, template lines non-zero, floor in force, surfaces reconciled |
| `tests/unit/test_package_version.py` | NEW — 3 tests covering the branch the removed pragma used to hide |
| `_bmad-output/implementation-artifacts/deferred-work.md` | Two deferred entries from this review pass |

### Review findings breakdown

13 patches applied, 2 items deferred, 8 rejected. No intent gaps and no spec defects: every finding was implementation-level and fixable in place, so no loopback was triggered and `review_loop_iteration` stayed at 0.

### Verification performed

- `pixi run ci` → exit 0, twice: once after implementation (233 passed, 92.46%) and once after the review patches (240 passed, 92.46%).
- **Mutation checks, not just green runs.** `COVERAGE_CORE=sysmon` → exactly two failures, including `user_detail.html` still appearing in `measured_files()` with `lines() == []`, which is the silent-zero AD-20 exists to catch. `--no-cov` on the gate command → exit 1 with all six live tests erroring (was exit 0 with five silent skips). Second floors injected at `[target.osx-arm64.tasks]` and `[feature.dev.target.linux-64.tasks]` → both named by the exactly-once test. `--ignore`/`-m`/`--no-cov` added to the real `test-cov` command → all three named. Every mutation reverted; `git diff` on both manifests shows comments only.
- Coverage API behaviour confirmed empirically against the pinned `coverage 7.15.3` / `pytest-cov 7.1.0` rather than assumed — the tracer accessor, mid-run `get_data()` flushing, `DEFAULT_EXCLUDE`, and the three `--cov` / `--no-cov` / no-flag option states.

### Residual risks

- **The Sonar exclusion list is frozen while disagreeing with the declared omit list.** Three divergences are recorded rather than resolved. Both surfaces are now closed, so neither drifts further, but the published coverage view and the gate's floor still measure slightly different trees until someone reconciles them deliberately.
- **`tests/coverage_policy.py` holds a `pytest.skip` and a `pytest.fail` outside Story 1.2's scan.** Narrowed as far as it can be without editing that guard, and deferred rather than dropped.
- **`--cov=src` supersedes `include = ["src/**"]`,** so coverage prints a `--include is ignored` warning on every gate run. The bound in force is now separately pinned, but the dead-configuration warning stays until Epic 7 moves the declaration.
- **`tools/materializer/` and `tools/harness/` remain outside measurement.** Recorded at the declaration site and in the test docstrings as a decision this story deliberately did not take.
