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
   **Then** it runs all six plus the smoke-check level

3. **Given** several distinct sets satisfy the all-pairs predicate
   **When** the subset is chosen
   **Then** it is pinned as data in the carrier
   **And** a gate test asserts that the pinned set actually satisfies the predicate

4. **Given** any run using a reduced set
   **When** it reports
   **Then** it states the reduction and the combinations not covered
   **And** no reduction is ever silent

5. **Given** the policy beyond six combinations
   **When** it is documented
   **Then** it states exhaustive verification while the space stays small, and all-pairs coverage plus unconditional verification of every preset past roughly thirty-two valid combinations

## Tasks / Subtasks

- [ ] Task 1: Pin the subset as carrier data (AC: #3)
  - [ ] Add `[verification] pr_subset = [...]` to `accelerator.toml` listing combination identifiers (the `combination.identifier` format from Story 8.2: sorted selected feature names joined with `-`, or `none`).
  - [ ] Choose the set by running the predicate check, not by intuition, and record beside it the comment that several distinct sets satisfy the predicate and this one is pinned so the exclusion report is stable run to run.
  - [ ] **Compute the minimum before pinning, and record the number in the comment.** Over the six-combination space the smallest set satisfying the predicate is **five**, and four of its members are forced: `(c,s)=(1,1)` occurs only in `combo-celery-redis-storage`, `(c,s)=(1,0)` only in `combo-celery-redis`, `(r,s)=(0,1)` only in `combo-storage`, and `(r,s)=(0,0)` only in `combo-none`; the fifth is either `combo-redis` or `combo-redis-storage`, which is the whole of the "several distinct sets" AD-19 anticipates. The reduction is therefore **one gate run in six**. See the Dev Notes assessment before pinning — pinning all six is a legal value of `pr_subset` that satisfies the predicate trivially and reports a reduction of none.
  - [ ] Do not compute the subset at run time. AD-19's stated failure mode is "an exclusion report that says something different every run and is therefore reported but not reviewable."

- [ ] Task 2: Implement the all-pairs predicate (AC: #1, #3)
  - [ ] `tools/harness/allpairs.py` (NEW) — `uncovered_pairs(subset, valid_combinations) -> tuple[Pair, ...]`. A `Pair` is `(feature_a, value_a, feature_b, value_b)` for `a < b` alphabetically.
  - [ ] The predicate holds when every pair of feature-value assignments that occurs in *at least one* valid combination also occurs in at least one subset member. **Three** feature pairs — `(celery, redis)`, `(celery, storage)`, `(redis, storage)` — × four value assignments is **twelve** candidate pairs; `(celery=True, redis=False)` is infeasible under the broker constraint, leaving **eleven** required pairs. Derive the candidates from `enumerate_valid()` rather than from the raw product, so the infeasible pair is excluded by construction rather than by a hardcoded exception.
  - [ ] `satisfies_all_pairs(subset, valid) -> bool` is `uncovered_pairs(...) == ()`.
  - [ ] Every subset member must itself be a valid combination; a pinned identifier that is not one of the six raises `CarrierError`.
  - [ ] The predicate must stay correct as the space grows — derive feature names from the `Combination` fields, never from a literal list of three, so a fourth feature does not silently reduce the required-pair set.

- [ ] Task 3: Report the bound (AC: #1, #4)
  - [ ] `tools/harness/report.py` (NEW) — `reduction_report(subset, valid) -> Report` carrying the reduction level, the subset identifiers, and the sorted identifiers of the combinations **not** covered.
  - [ ] The harness emits the report through `structlog` at the start and end of every reduced run, and writes it as `verification-bound.json` with sorted keys, uploaded as a CI artifact alongside the coverage report from Story 8.8.
  - [ ] A full run also emits a report, stating a reduction of none and an empty uncovered list — so "no reduction is ever silent" is true by construction rather than by remembering to log it.
  - [ ] The report is a first-class output, not a log side effect: a run that produced no report fails.

- [ ] Task 4: Wire the two levels into CI (AC: #1, #2)
  - [ ] `tools/harness/run.py` (created by Story 8.8) gains a `--level` argument with exactly two values: `pr` and `merge`. `pr` runs the pinned subset's gates; `merge` runs all six gates **plus** the smoke-check level (Story 8.10).
  - [ ] `.github/workflows/combinations.yml` (created by Story 8.8) selects the level from the trigger: `pull_request` → `pr`, `push` to `main` → `merge`. Do not add a third level and do not make the level a manually settable input that could silently reduce a merge run.
  - [ ] The matrix legs for a `pr` run are the pinned subset's identifiers, read from the carrier at workflow-generation time or expanded by a small setup job that emits the matrix as JSON — either way the identifiers come from `accelerator.toml`, never from a list duplicated into the workflow file.

- [ ] Task 5: Document the policy (AC: #5)
  - [ ] Add an accelerator-facing documentation section stating: exhaustive verification while the space stays small; past roughly thirty-two valid combinations, all-pairs coverage plus unconditional verification of every preset. Name the three presets — ***Minimal*, *Cached*, *Worker-enabled*** — declared in Story 7.6. (*API-only* and *Full web app* were renamed in revision 3: with the interface mechanism core, they no longer name distinguishable selections.)
  - [ ] State the current position of the space against that switch: **six** valid combinations, well under the roughly thirty-two at which all-pairs starts to pay, and an all-pairs subset that omits exactly one of the six. Record the arithmetic so a later reader can see why the reduction is small rather than assuming it was not measured.
  - [ ] State AD-19's soundness precondition in the same place: this is sound only because generation happens from a released, tagged version and never from `main` HEAD, and AD-32's GitHub-template path is the named, governed exception that does not hold it.
  - [ ] This documentation is accelerator-facing and does **not** travel (NFR-8, Story 8.7's `docs/` split).

- [ ] Task 6: Tests (AC: #1, #3, #4, #5)
  - [ ] `tests/unit/harness/test_allpairs.py` — the pinned set from the real `accelerator.toml` satisfies the predicate; a deliberately deficient set does not and `uncovered_pairs` names the missing pair; every pinned identifier is one of the six; the infeasible `(celery=True, redis=False)` pair is never required; the required-pair set has exactly eleven members over the current space.
  - [ ] `tests/unit/harness/test_report.py` — a reduced run's report lists exactly the six minus the subset; a full run's report lists none and states a reduction of none; a run that produces no report fails.
  - [ ] `tests/unit/harness/test_levels.py` — `merge` runs six and includes the smoke-check level; `pr` runs exactly the pinned subset; no level runs fewer than the pinned subset.

## Dev Notes

### Architecture Constraints

- **Does all-pairs still earn its keep at six?** Measured, not assumed. Eleven feasible pairs, three per combination, and four members forced by pairs that occur in exactly one valid combination each: the minimum satisfying set is **five of six**. All-pairs on a pull request therefore saves **one gate run in six** — about seventeen percent of the matrix — in exchange for a pinned carrier list, a predicate implementation, a gate test asserting the predicate, and an exclusion report that will always name a single combination. **At this size exhaustive is simply correct**, and FR-35 agrees: it puts the switch to all-pairs at roughly thirty-two valid combinations, and the spine files all-pairs-as-permanent-policy under Deferred, using it "only as a per-PR trigger." AD-19 is binding and its mechanism is built here in full — but `pr_subset` may legally be pinned to **all six**, which satisfies the predicate trivially, reports a reduction of none, and leaves `pr` and `merge` differing only by the smoke-check level. Build the machinery; pin all six unless CI cost measurement says otherwise, and record the measurement beside the pin. Reducing from six to five is a decision that should be made on numbers, not inherited from a twelve-combination space that no longer exists.
- **AD-19** (binding): "A pull request runs an all-pairs subset and reports which combinations it did not cover; merge to `main` runs all six plus the smoke-check level. Several distinct sets satisfy the all-pairs predicate, so the subset is **pinned as data in `accelerator.toml`**, with a gate test asserting the pinned set actually satisfies the predicate. This is sound only because generation happens from a released, tagged version and never from `main` HEAD; the exception is AD-32." *Prevents:* "a silently truncated verification set reading as full coverage; an exclusion report that says something different every run and is therefore reported but not reviewable."
- **CG-2** (binding constraint, counterbalances SC-1): "Do not shrink the verification set to keep CI cheap. A template change costing six materialize-and-gate runs is the price of SC-1 meaning what it says. Any reduction must be reported (FR-35), never silent." Revision 3 already halved that price; CG-2 reads more strongly against a further reduction, not less.
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
| `tools/harness/run.py` | UPDATE | Created by Story 8.8 as a six-combination runner. This story adds `--level pr|merge` and makes report emission mandatory. Preserve the run-all-then-fail behaviour and the per-combination structured result records. |
| `.github/workflows/combinations.yml` | UPDATE | Created by Story 8.8, Linux-only with a PostgreSQL service. This story adds trigger-driven level selection and a carrier-derived matrix. Preserve `runs-on: ubuntu-latest`, `fail-fast: false`, the postgres service and the aggregating job. |
| `accelerator.toml` | UPDATE | Adds `[verification] pr_subset` with its rationale comment. `[verification] coverage_bringup` already exists from Story 8.8; keep both in one table. |
| `docs/` (accelerator-facing page) | UPDATE | Adds the beyond-six verification policy, the measured cost of the reduction, and the AD-19 soundness precondition. Use whichever page Story 8.7's split assigned as `machinery`; `docs/` today holds `index.md`, `development.md`, `observability.md`. |
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
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md:888] — CG-2, verified after the revision-3 PRD amendment
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Deferred] — "All-pairs as the permanent policy. FR-35 puts the switch at roughly thirty-two combinations; AD-19 uses it only as a per-PR trigger."
- [Source: _bmad-output/planning-artifacts/epics.md] — FR-35

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
