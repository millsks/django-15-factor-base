# Story 8.9: Verification is reduced on pull request, full on merge, and any bound is reported

Status: ready-for-dev

## Story

As a platform engineer,
I want a pinned reduced set on pull requests and the full set on merge, with exclusions reported,
so that CI cost is bounded without a truncated set reading as full coverage.

## Acceptance Criteria

**Traceability:** FR-35 · AD-19 · CG-2 · SC-1

1. **Given** a pull request
   **When** the harness runs
   **Then** it runs an all-pairs subset
   **And** reports which combinations it did not cover

2. **Given** a merge to `main`
   **When** the harness runs
   **Then** it runs all twelve plus the smoke-check level

3. **Given** several distinct sets satisfy the all-pairs predicate
   **When** the subset is chosen
   **Then** it is pinned as data in the carrier
   **And** a gate test asserts that the pinned set actually satisfies the predicate

4. **Given** any run using a reduced set
   **When** it reports
   **Then** it states the reduction and the combinations not covered
   **And** no reduction is ever silent

5. **Given** the policy beyond twelve combinations
   **When** it is documented
   **Then** it states exhaustive verification while the space stays small, and all-pairs coverage plus unconditional verification of every preset past roughly thirty-two valid combinations

## Tasks / Subtasks

- [ ] Task 1: Pin the subset as carrier data (AC: #3)
  - [ ] Add `[verification] pr_subset = [...]` to `accelerator.toml` listing combination identifiers (the `combination.identifier` format from Story 8.2: sorted selected feature names joined with `-`, or `none`).
  - [ ] Choose the set by running the predicate check, not by intuition, and record beside it the comment that several distinct sets satisfy the predicate and this one is pinned so the exclusion report is stable run to run.
  - [ ] Do not compute the subset at run time. AD-19's stated failure mode is "an exclusion report that says something different every run and is therefore reported but not reviewable."

- [ ] Task 2: Implement the all-pairs predicate (AC: #1, #3)
  - [ ] `tools/harness/allpairs.py` (NEW) — `uncovered_pairs(subset, valid_combinations) -> tuple[Pair, ...]`. A `Pair` is `(feature_a, value_a, feature_b, value_b)` for `a < b` alphabetically.
  - [ ] The predicate holds when every pair of feature-value assignments that occurs in *at least one* valid combination also occurs in at least one subset member. Six feature pairs × four value assignments is twenty-four candidate pairs; `(celery=True, redis=False)` is infeasible under the broker constraint and must be excluded from the required set by deriving the candidates from `enumerate_valid()` rather than from the raw product.
  - [ ] `satisfies_all_pairs(subset, valid) -> bool` is `uncovered_pairs(...) == ()`.
  - [ ] Every subset member must itself be a valid combination; a pinned identifier that is not one of the twelve raises `CarrierError`.

- [ ] Task 3: Report the bound (AC: #1, #4)
  - [ ] `tools/harness/report.py` (NEW) — `reduction_report(subset, valid) -> Report` carrying the reduction level, the subset identifiers, and the sorted identifiers of the combinations **not** covered.
  - [ ] The harness emits the report through `structlog` at the start and end of every reduced run, and writes it as `verification-bound.json` with sorted keys, uploaded as a CI artifact alongside the coverage report from Story 8.8.
  - [ ] A full run also emits a report, stating a reduction of none and an empty uncovered list — so "no reduction is ever silent" is true by construction rather than by remembering to log it.
  - [ ] The report is a first-class output, not a log side effect: a run that produced no report fails.

- [ ] Task 4: Wire the two levels into CI (AC: #1, #2)
  - [ ] `tools/harness/run.py` (created by Story 8.8) gains a `--level` argument with exactly two values: `pr` and `merge`. `pr` runs the pinned subset's gates; `merge` runs all twelve gates **plus** the smoke-check level (Story 8.10).
  - [ ] `.github/workflows/combinations.yml` (created by Story 8.8) selects the level from the trigger: `pull_request` → `pr`, `push` to `main` → `merge`. Do not add a third level and do not make the level a manually settable input that could silently reduce a merge run.
  - [ ] The matrix legs for a `pr` run are the pinned subset's identifiers, read from the carrier at workflow-generation time or expanded by a small setup job that emits the matrix as JSON — either way the identifiers come from `accelerator.toml`, never from a list duplicated into the workflow file.

- [ ] Task 5: Document the policy (AC: #5)
  - [ ] Add an accelerator-facing documentation section stating: exhaustive verification while the space stays small; past roughly thirty-two valid combinations, all-pairs coverage plus unconditional verification of every preset. Name the three presets (*API-only*, *Full web app*, *Worker-enabled*) declared in Story 7.6.
  - [ ] State AD-19's soundness precondition in the same place: this is sound only because generation happens from a released, tagged version and never from `main` HEAD, and AD-32's GitHub-template path is the named, governed exception that does not hold it.
  - [ ] This documentation is accelerator-facing and does **not** travel (NFR-8, Story 8.7's `docs/` split).

- [ ] Task 6: Tests (AC: #1, #3, #4, #5)
  - [ ] `tests/unit/harness/test_allpairs.py` — the pinned set from the real `accelerator.toml` satisfies the predicate; a deliberately deficient set does not and `uncovered_pairs` names the missing pair; every pinned identifier is one of the twelve; the infeasible `(celery=True, redis=False)` pair is never required.
  - [ ] `tests/unit/harness/test_report.py` — a reduced run's report lists exactly the twelve minus the subset; a full run's report lists none and states a reduction of none; a run that produces no report fails.
  - [ ] `tests/unit/harness/test_levels.py` — `merge` runs twelve and includes the smoke-check level; `pr` runs exactly the pinned subset; no level runs fewer than the pinned subset.

## Dev Notes

### Architecture Constraints

- **AD-19** (binding): "A pull request runs an all-pairs subset and reports which combinations it did not cover; merge to `main` runs all twelve plus the smoke-check level. Several distinct sets satisfy the all-pairs predicate, so the subset is **pinned as data in `accelerator.toml`**, with a gate test asserting the pinned set actually satisfies the predicate. This is sound only because generation happens from a released, tagged version and never from `main` HEAD; the exception is AD-32." *Prevents:* "a silently truncated verification set reading as full coverage; an exclusion report that says something different every run and is therefore reported but not reviewable."
- **CG-2** (binding constraint, counterbalances SC-1): "Do not shrink the verification set to keep CI cheap. A template change costing twelve materialize-and-gate runs is the price of SC-1 meaning what it says. Any reduction must be reported (FR-35), never silent."
- **FR-35** (binding): "Any bound on verification coverage is reported explicitly, with the combinations not covered."
- **AD-1** (binding): "the pinned all-pairs subset" is one of the things declared in `accelerator.toml` "and nowhere else". Duplicating the identifiers into the workflow file is a second declaration site and is forbidden.
- **AD-32**: the GitHub-template path "copies the default branch, so AD-19's soundness precondition — generation only from a released tag — does **not** hold for it... These are accepted, not mitigated." Document it; do not attempt to fix it here.
- **NFR-8**: accelerator-facing docs do not travel.
- Never `print()`; `structlog`, JSON to stdout. Never bare `except:`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tools/harness/allpairs.py` | NEW | The predicate and the uncovered-pair report. |
| `tools/harness/report.py` | NEW | `reduction_report()` and `verification-bound.json`. |
| `tools/harness/run.py` | UPDATE | Created by Story 8.8 as a twelve-combination runner. This story adds `--level pr|merge` and makes report emission mandatory. Preserve the run-all-then-fail behaviour and the per-combination structured result records. |
| `.github/workflows/combinations.yml` | UPDATE | Created by Story 8.8, Linux-only with a PostgreSQL service. This story adds trigger-driven level selection and a carrier-derived matrix. Preserve `runs-on: ubuntu-latest`, `fail-fast: false`, the postgres service and the aggregating job. |
| `accelerator.toml` | UPDATE | Adds `[verification] pr_subset` with its rationale comment. `[verification] coverage_bringup` already exists from Story 8.8; keep both in one table. |
| `docs/` (accelerator-facing page) | UPDATE | Adds the beyond-twelve verification policy and the AD-19 soundness precondition. Use whichever page Story 8.7's split assigned as `machinery`; `docs/` today holds `index.md`, `development.md`, `observability.md`. |
| `tests/unit/harness/test_allpairs.py` | NEW | |
| `tests/unit/harness/test_report.py` | NEW | |
| `tests/unit/harness/test_levels.py` | NEW | |

#### Project Structure Notes

All new code is `machinery` under `tools/harness/`, beside the runner Story 8.8 created. Nothing here travels into a component: a materialized component verifies itself, it does not verify the combination space.

`tests/unit/harness/` exists after Story 8.8; if this story lands first, create it with an `__init__.py`.

### Testing Requirements

- All three test files are unit tests: pure combinatorics over `enumerate_valid()` and TOML parsing. No I/O, milliseconds.
- `test_allpairs.py` runs against the **real** `accelerator.toml`, not a fixture — AC #3 requires a gate test asserting the *pinned* set satisfies the predicate, so a synthetic set would not discharge it. Follow the precedent of `tests/unit/test_dependency_policy.py`, which asserts a policy over the real declaration file.
- The deficient-set case must also be covered, so a predicate that returns `True` unconditionally fails the suite.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` (AD-20).
- Disposition: all three test files and both new modules are `machinery`.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-19]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-32]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.9]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.6] — the three presets
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md:880] — CG-2
- [Source: _bmad-output/planning-artifacts/epics.md] — FR-35

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
