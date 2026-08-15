# Story 8.8: Every valid combination passes the full gate against PostgreSQL

Status: ready-for-dev

## Story

As a platform engineer,
I want all six combinations gated against PostgreSQL,
so that a defect is found before the first lead developer to order that combination finds it.

## Acceptance Criteria

**Traceability:** FR-32, FR-29 · AD-18, AD-20 · CG-1 · SC-1, SC-2

1. **Given** all six valid combinations
   **When** the harness runs
   **Then** each is materialized and put through tests, coverage at or above ninety percent including templates, strict type checking, lint and build, against PostgreSQL

2. **Given** a failure in any one combination
   **When** the run completes
   **Then** the whole run fails
   **And** there is no partial pass

3. **Given** an orphaned template override introduced deliberately into a combination
   **When** that combination's gate runs
   **Then** it fails

4. **Given** the coverage floor before the materializer has reported all six numbers
   **When** materialized-combination gates run
   **Then** the floor is advisory and the numbers are published as an artifact
   **And** the exit condition is that first full report

5. **Given** that report has been produced
   **When** any later gate runs
   **Then** the floor is hard everywhere
   **And** a combination that misses is answered with tests rather than with a lower floor

## Tasks / Subtasks

- [ ] Task 1: Build the six-combination harness runner (AC: #1, #2)
  - [ ] `tools/harness/__init__.py` and `tools/harness/run.py` (NEW, `machinery`) — for each combination from `enumerate_valid()`: materialize into a working directory, run `reconcile_output()` (Story 8.7), then invoke the gate for that materialized tree under the matching pre-locked pixi environment `combo-<id>` (Story 8.1).
  - [ ] The gate per combination is `pixi run ci` — the same single invocation Epic 1 consolidated, not a re-implementation of its steps. `ci` today is `depends-on = ["test-cov", "lint", "typecheck", "build"]` (`pixi.toml:206`).
  - [ ] Run every combination even after one fails, collect all results, then exit non-zero if any failed. AC #2 forbids a partial pass; it does not forbid finishing the run — a run that stops at the first failure hides which other combinations also broke, which is the whole point of the epic's premise.
  - [ ] Emit one structured result record per combination through `structlog` — combination identifier, per-step outcome, coverage percentage, duration. Never `print()`.

- [ ] Task 2: Run against PostgreSQL (AC: #1)
  - [ ] The harness sets `DATABASE_URL` to the PostgreSQL service, not to sqlite, and does not set `COMPONENT_RUNTIME=local` for the gate run — the local substitutions exist for developers, and SC-1 explicitly requires PostgreSQL "rather than the local sqlite substitution".
  - [ ] Epic 1 Story 1.2 introduces the PostgreSQL `services:` block for the reference application. **GitHub Actions `services:` containers are Linux-only** (AD-18), so that gate is an ubuntu-only job and a separate three-OS job runs `pixi run test` for platform compatibility. This story extends the same connection convention to the six-combination workflow; do not invent a second one, and do not attempt to attach a `services:` block to a three-OS matrix.
  - [ ] Assert in the harness that the database backend in force during a materialized gate is `django.db.backends.postgresql`, and fail the combination if it is not — an accidental sqlite fallback would make every combination pass for the wrong reason.

- [ ] Task 3: The six-combination CI workflow (AC: #1, #2)
  - [ ] `.github/workflows/combinations.yml` (NEW) — `runs-on: ubuntu-latest` only, a `strategy.matrix` over the six combination identifiers, `fail-fast: false`, a `postgres` service, `prefix-dev/setup-pixi@v0.9.5` with `pixi-version: v0.70.2` matching the existing `ci.yml` pins, and a final aggregating job that fails if any matrix leg failed.
  - [ ] **Linux only, for two independent reasons.** AD-18: "The six-combination harness is Linux-only, `gunicorn` having no win-64 build; the three-OS matrix stays on the reference application, where it claims something different." And: "GitHub Actions `services:` containers are Linux-only", so the PostgreSQL gate could not run on a three-OS matrix even if gunicorn built there. Do not add `windows-latest` or `macos-latest` to this workflow, and do not remove them from `ci.yml`.
  - [ ] Disposition `.github/workflows/combinations.yml` as `machinery` in `accelerator.toml` — it is the accelerator's harness and must not travel (Story 8.7).

- [ ] Task 4: The deliberate-orphan test (AC: #3)
  - [ ] `tests/integration/harness/test_deliberate_orphan.py` (NEW, `@pytest.mark.integration`) — materialize one combination, introduce an orphaned template override into the materialized tree (a template file no view renders), run that combination's coverage step, and assert it fails on the zero-percent coverage signal.
  - [ ] This is the test Story 7.8's last acceptance criterion defers to Epic 8 because it needs a materialized combination to run against. Assert the failure comes from the template's zero coverage, not from an unrelated error — check that the coverage report lists the orphan template at 0%.
  - [ ] The test must clean up: the orphan lives only in a `tmp_path` materialized tree and is never introduced into the reference application.
  - [ ] Assert `COVERAGE_CORE=ctrace` is in force during the run — without the C trace core the template reports a silent zero indistinguishable from a genuine orphan, and the test would pass for the wrong reason.

- [ ] Task 5: Time-boxed bring-up mode (AC: #4, #5)
  - [ ] Add `[verification]` to `accelerator.toml` with `coverage_bringup = true` and a comment stating the exit condition verbatim: the floor stays advisory on materialized-combination gates until the materializer has reported all six numbers once, published as an artifact.
  - [ ] `tools/harness/coverage_report.py` (NEW) — collect each combination's coverage percentage into `six-combination-coverage.json`, sorted keys, written to the harness working directory and uploaded as a CI artifact by `combinations.yml`. The report is six numbers; the bring-up exit is reached when all six are present, not when a majority are.
  - [ ] While `coverage_bringup = true`, a materialized combination's coverage step runs without `--cov-fail-under` and its number is recorded rather than enforced. The reference application's own gate is **not** in bring-up mode — `test-cov` keeps `--cov-fail-under=90` (`pixi.toml:196`) and the floor is hard there from the start.
  - [ ] `tests/unit/harness/test_bringup_mode.py` — when `coverage_bringup = false`, the harness must pass `--cov-fail-under=90` to every combination and must reject any per-combination override; when `true`, it must still write every number into the report. Assert there is no code path that lowers the floor below the single global constant.
  - [ ] Flipping `coverage_bringup` to `false` is the recorded exit and is a carrier edit plus a commit, not a code change.

- [ ] Task 6: Assert the floor is one constant (AC: #4, #5)
  - [ ] `tests/unit/test_coverage_floor_is_one_constant.py` — assert the value 90 appears as the coverage floor in exactly one declared place and that no per-combination, per-file or per-directory floor exists anywhere in `pixi.toml`, `pyproject.toml`, `accelerator.toml` or the harness.
  - [ ] Assert the effective `[tool.coverage.run] omit` list equals the carrier-declared closed surface (Story 7.8 moved it into `accelerator.toml`; Story 1.5 authored it). Today `omit` is at `pyproject.toml:162-169` and lists `*/migrations/*`, `*/tests/*`, `**/*.egg-info/**`, `src/config/wsgi.py`, `src/config/asgi.py`, `src/config/websocket.py` — the last of which Epic 1 Story 1.4 deletes together with `src/config/websocket.py` itself.
  - [ ] Do **not** move the template-coverage configuration. AD-18 correction 13: `django_coverage_plugin` and `template_extensions` are already correct in `pyproject.toml` and `COVERAGE_CORE=ctrace` is already correct in `pixi.toml [activation.env]`; only the coverage *run invocation* moves out of `sonarqube.yml:36` (`pixi run test-cov`). Likewise `build` comes off the fortnightly cron in **`release.yml`**, which also runs `lint`, `typecheck` and `test-cov` inline — four gate steps leave that workflow, not one. Epic 1 owns those moves; this story must not duplicate or contradict them.

## Dev Notes

### Architecture Constraints

- **AD-18** (binding): "A single workflow invokes `pixi run ci`, which has never run in CI. A `ci` task **already exists** at `pixi.toml:206` as `depends-on = [\"test-cov\", \"lint\", \"typecheck\", \"build\"]` — no pre-commit step and roughly the reverse of the fast-fail ordering, so this AD reshapes an existing task rather than creating one... The six-combination harness is Linux-only, `gunicorn` having no win-64 build; the three-OS matrix stays on the reference application, where it claims something different. Type checking is strict." *Prevents:* "the orphan detector being disabled by a change nobody understood as security-relevant; thirty-six gate runs that cannot exercise the process model."
- **AD-20** (binding): "Ninety percent, including templates, everywhere. `COVERAGE_CORE=ctrace` travels with every combination and a test asserts it is in force during a gate run. Never a lower floor, a pragma, or a narrowed measurement. **The coverage `omit`/`exclude` list is a closed, carrier-declared surface** subject to two-way reconciliation... **Bring-up mode, time-boxed:** ... Until the materializer has reported all six numbers once, materialized-combination gates run with the floor advisory and the numbers published as an artifact. The exit condition is that report; after it, the floor is hard everywhere and a combination that misses is answered with tests." *Prevents:* "a per-combination floor becoming the place a structurally sparse combination hides; and the narrowing that is already precedented in this tree — `[tool.coverage.run] omit` — being used to clear the floor while every stated rule still passes."
- **CG-1** (binding constraint, counterbalances SC-1): "Do not reach the coverage threshold by narrowing what is measured... Excluding files, adding coverage pragmas to unreached code, or dropping template measurement makes SC-1 pass and destroys SC-2." A failing combination is answered with tests. Never with a pragma, an omit entry, or a lower floor.
- **AD-3**: "combination *n*'s gate runs its materialized source under environment *n*" — the pre-locked `combo-<id>` environment from Story 8.1 supplies the packages; the materialized tree supplies the source. Never run a combination under `dev` or `default`.
- **FR-29 / Story 7.8**: the orphan signal is declared in Epic 7 and exercised per combination here; the deliberate-orphan test lives in this epic "because it needs a materialized combination to run against".
- **Cross-epic thread**: "FR-32's PostgreSQL service and the single `pixi run ci` invocation begin in Epic 1 against the reference application; Epic 8 extends both to six combinations." If Epic 1 Stories 1.1 and 1.2 have not landed, this story is blocked on them.
- **SC-1** requires PostgreSQL "rather than the local sqlite substitution". A gate run against sqlite does not discharge this story.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tools/harness/__init__.py` | NEW | Package marker. `tools/harness/` does not exist. |
| `tools/harness/run.py` | NEW | The six-combination runner: materialize, reconcile, gate, aggregate. |
| `tools/harness/coverage_report.py` | NEW | Writes `six-combination-coverage.json` with sorted keys. |
| `.github/workflows/combinations.yml` | NEW | Linux-only six-leg matrix with a PostgreSQL service and an aggregating job. |
| `.github/workflows/ci.yml` | UPDATE | Today 55 lines: a `test` job over `ubuntu/windows/macos` running `pixi run test`, and a `lint` job running `pixi run lint` and `pixi run typecheck`. Epic 1 consolidates it to one `pixi run ci`. This story leaves the three-OS matrix on the reference application and adds nothing to it. Preserve `pixi-version: v0.70.2` and `actions/checkout@v6`. |
| `accelerator.toml` | UPDATE | Adds `[verification] coverage_bringup` with its exit-condition comment; dispositions `combinations.yml` as `machinery`. |
| `pixi.toml` | UPDATE | Add a `combinations` task in `[feature.dev.tasks]` invoking `python -m tools.harness.run`, with `default-environment = "dev"` and a `description`. Preserve `test-cov`'s `--cov-fail-under=90` (`:196`) and the `ci` task's `depends-on` list (`:206`). |
| `tests/unit/harness/test_bringup_mode.py` | NEW | |
| `tests/unit/test_coverage_floor_is_one_constant.py` | NEW | |
| `tests/integration/harness/test_deliberate_orphan.py` | NEW | |
| `pyproject.toml` | UPDATE | `[tool.coverage.run] omit` at `:162-169` is reconciled against the carrier-declared list. `[tool.mypy]` at `:181-191` sets `check_untyped_defs = true`, not `strict` — Epic 1 Story 1.3 makes it strict; this story depends on that having happened and does not change it. |

#### Project Structure Notes

`tools/harness/` is NEW and is `machinery`. The Structural Seed names it explicitly — `tools/harness/  # machinery — six-combination verification runner` — beside `tools/materializer/`. Separating the runner from the materializer keeps AD-3's materialization concern distinct from AD-18/AD-19's verification concern, and both are `machinery` so neither travels.

`tests/unit/harness/` and `tests/integration/harness/` are NEW test packages; add `__init__.py` to each to match `tests/unit/__init__.py` and `tests/integration/__init__.py`.

### Testing Requirements

- `tests/unit/harness/test_bringup_mode.py` and `tests/unit/test_coverage_floor_is_one_constant.py` — isolated declaration-file parsing, milliseconds. `test_coverage_floor_is_one_constant.py` is a whole-repository policy test in the style of `tests/unit/test_dependency_policy.py`.
- `tests/integration/harness/test_deliberate_orphan.py` — `@pytest.mark.integration`, `tmp_path`, must never touch the reference application's `src/django_service/templates/`.
- The full six-leg run belongs in `.github/workflows/combinations.yml`, not in `pixi run ci` — running six materialize-and-gate cycles inside the reference application's own gate would make every local commit unaffordable. The harness's *unit* behaviour is what `pixi run ci` covers.
- Coverage floor 90% including templates, one global constant, `COVERAGE_CORE=ctrace` in force (AD-20).
- Disposition: `tools/harness/`, its tests, and `combinations.yml` are all `machinery`.

**Traceability marker, not an acceptance condition for this story:** Story 7.8's final criterion states that the deliberate-orphan proof "runs in Epic 8". This story is where that obligation completes; Story 7.8 remains completable on its own.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-18]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-3]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.8]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.8] — the orphan detectors and the deferred proof
- [Source: _bmad-output/planning-artifacts/epics.md] — cross-epic thread, epics.md:220 and :222
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md:862] — SC-1, "against PostgreSQL rather than the local sqlite substitution"
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md:879] — CG-1
- [Source: pixi.toml:196] — `test-cov` carries `--cov-fail-under=90` today
- [Source: pixi.toml:206] — `ci = { depends-on = ["test-cov", "lint", "typecheck", "build"] }`
- [Source: pyproject.toml:160-173] — `[tool.coverage.run]` include/omit and the `django_coverage_plugin` entry
- [Source: .github/workflows/ci.yml:10-34] — the three-OS matrix that stays on the reference application

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
