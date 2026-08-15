# Story 4.5: Every refusal is tested as a refusal

Status: ready-for-dev

## Story

As a platform engineer,
I want each forbidden state to have a test that configures it and asserts the raise,
so that the suite proves the deployed settings refuse rather than merely proving they start.

## Acceptance Criteria

**Traceability:** FR-16 · CG-3 · SC-5

1. **Given** the fourteen distinct forbidden states across nine conditions
   **When** the suite runs
   **Then** each has at least one test that configures that state and asserts `ImproperlyConfigured`
   **And** a condition covering several states has each state tested separately

2. **Given** the settings-module escape route
   **When** it is tested
   **Then** the test configures a deployed environment with the local settings module loaded and asserts refusal

3. **Given** each stage-2 condition
   **When** it is tested
   **Then** at least one test exercises it through a served request path
   **And** not only through `manage.py`

4. **Given** any refusal
   **When** it fires
   **Then** it raises rather than logging and continuing
   **And** no refusal is softened into a warning

## Tasks / Subtasks

- [ ] Task 1 — Declare the fourteen forbidden states as data (AC: #1)
  - [ ] Add `tests/unit/config/startup/forbidden_states.py` holding a single module-level tuple `FORBIDDEN_STATES` of frozen dataclass records, one per state: a stable `state_id`, its condition number (1–9), its stage (1 or 2), and a one-line description. Fourteen entries, matching the table in Dev Notes exactly.
  - [ ] This is a **test-support declaration, not a second copy of the contract**. It names states, not predicates. The predicates live once in `src/config/startup/` (AD-26, AD-1).
  - [ ] Mark each entry with whether it is conditional (`feature:redis` for state 8, `feature:celery` for state 9), so Epic 7 can dispose of the two conditional entries with their features.

- [ ] Task 2 — The coverage audit test (AC: #1)
  - [ ] Add `tests/unit/config/startup/test_refusal_coverage_audit.py` with one test that collects every test function in `tests/unit/config/startup/` and `tests/integration/config/startup/` and asserts that every `state_id` in `FORBIDDEN_STATES` is claimed by at least one of them.
  - [ ] Claiming mechanism: a `@pytest.mark.forbidden_state("<state_id>")` marker applied to each refusal test. Register the marker in `[tool.pytest.ini_options] markers` in `pyproject.toml:155-157`, alongside the existing `integration` marker.
  - [ ] The audit fails in both directions: an unclaimed state fails, and a marker naming a `state_id` not in `FORBIDDEN_STATES` fails. A one-way check lets a renamed state go dark.
  - [ ] Collect markers by walking the test modules with `pytest`'s own collection (an `pytest.Item`-level hook or a session-scoped fixture recording `item.iter_markers("forbidden_state")`), not by parsing source text.
  - [ ] Assert the count is exactly fourteen, so adding a tenth condition without updating the declaration fails rather than passing quietly.

- [ ] Task 3 — Apply the marker across the existing refusal tests (AC: #1)
  - [ ] Mark the eight stage-1 states in `tests/unit/config/startup/test_stage_one_conditions.py` (Story 4.2): sqlite; `ModelBackend`; non-empty `ACCOUNT_LOGIN_METHODS`; `DJANGO_ADMIN_FORCE_ALLAUTH` not true; the static-token surface; `OTEL_SDK_DISABLED`; the JWKS anchor; the unconfigured claims contract.
  - [ ] Mark the four stage-2 states across `tests/unit/config/startup/test_stage_two_urlconf.py` and `tests/integration/config/startup/test_stage_two_database_conditions.py` (Story 4.3): `obtain_auth_token` route; local sign-in route; unapplied migrations; designated group absent.
  - [ ] Mark the two conditional states in `tests/unit/config/startup/test_feature_scoped_refusals.py` (Story 4.4): in-process cache; eager tasks.
  - [ ] Where a condition covers several states — condition 2 (four states), condition 5 (two states), condition 6 (two states) — each state must be its own test function with its own marker. Do not parameterize four states onto one function in a way that leaves a single marker covering all of them; if `pytest.mark.parametrize` is used, apply the `forbidden_state` marker per parameter set with `pytest.param(..., marks=...)`.

- [ ] Task 4 — The settings-module escape route (AC: #2)
  - [ ] Story 4.1 implements the condition and its first test. This story asserts it is present, marked, and constructed correctly: `monkeypatch.delenv("COMPONENT_RUNTIME", raising=False)`, fresh import of `config.settings.local`, `pytest.raises(ImproperlyConfigured)`.
  - [ ] The test must import the settings module for real rather than calling `run_stage_one` with a hand-built namespace — the point of FR-12's escape route is that the *module load path* refuses, and a synthesized namespace does not exercise it.
  - [ ] Use the eviction fixture pattern at `tests/unit/test_settings.py:24-30`, extended to evict `config.settings.local` and `config.settings.base` together; without evicting `base`, the `from .base import *` reuses an already-imported copy and the module-level environment reads are not re-evaluated.
  - [ ] Give this test its own `state_id` entry outside the fourteen (it is FR-12's test, not a refusal condition) and assert its presence separately, so it cannot be traded off against the fourteen.

- [ ] Task 5 — Each stage-2 condition through a served request path (AC: #3)
  - [ ] Add `tests/integration/config/startup/test_stage_two_served_path.py`, `@pytest.mark.integration`, driving requests through `config.asgi:application` with an ASGI transport rather than through `manage.py`.
  - [ ] One test per stage-2 condition — four in total: the `obtain_auth_token` route, the local sign-in route, unapplied migrations, and the absent designated group. Each configures the forbidden state, starts the application through the served path, and asserts `ImproperlyConfigured`.
  - [ ] Add the paired control: one test that invokes `django.core.management.call_command("check")` and asserts the same condition fires there too, so "it fires under management commands as well" is proven rather than assumed — except for the migrations condition, which is deliberately exempt for management commands (AD-13 fail-open, FR-13 stage 2). Assert that exemption explicitly.
  - [ ] `src/config/asgi.py` is in the coverage `omit` list at `pyproject.toml:166`; these tests assert behaviour reached *through* it and do not require changing that list.

- [ ] Task 6 — CG-3: no refusal is softened (AC: #4)
  - [ ] Add `tests/unit/config/startup/test_no_softening.py`.
  - [ ] Test A: run each condition against its forbidden state with `pytest.warns(None)` semantics — assert the call raises `ImproperlyConfigured` **and** that `warnings.catch_warnings(record=True)` captured nothing. A condition that warns and raises is still wrong shape; a condition that warns and returns is the failure CG-3 names.
  - [ ] Test B: capture `structlog` output with `structlog.testing.capture_logs()` around each forbidden state and assert that no log event is emitted *in place of* the raise. Logging alongside a raise is permitted; logging instead of it is not.
  - [ ] Test C: a source-level scan of `src/config/startup/*.py` asserting the module contains no `warnings.warn(`, no bare `except:`, and no `except <Exception>: pass` — the project standard forbids all three, and here they are also the exact shape CG-3 prohibits.
  - [ ] Test D: assert every condition's failure path raises `django.core.exceptions.ImproperlyConfigured` specifically, not a bare `Exception`, `ValueError` or `RuntimeError` — the Consistency Conventions table fixes the type: "Every forbidden or missing configuration raises `ImproperlyConfigured` at one of the two refusal stages."

- [ ] Task 7 — Positive controls (AC: #1)
  - [ ] For each of the nine conditions add, or confirm from the owning story, one test where the condition's input is *valid* and no exception is raised. Without positive controls a predicate hardcoded to raise passes all fourteen refusal tests.
  - [ ] Add one end-to-end positive: a fully valid deployed settings namespace and a clean URLconf pass `run_stage_one` and `run_stage_two` together without raising.

## Dev Notes

### Architecture Constraints

- **FR-16 (binding):** "Each of the nine conditions has at least one test that configures the forbidden state and asserts `ImproperlyConfigured` is raised. Where a condition covers several distinct forbidden states — the settings-side credential paths are four — each state is tested separately."
- **CG-3 (verbatim):** "Do not soften a refusal into a warning. A refusal that logs and continues makes deployment smoother and puts local credentials into production. Counterbalances SC-3 and SC-5."
- **Spine, Consistency Conventions → Configuration errors:** "Every forbidden or missing configuration raises `ImproperlyConfigured` at one of the two refusal stages. A refusal never degrades to a warning (CG-3)."
- **SC-5:** "Each of the nine refusal conditions has a test that configures the forbidden state and asserts refusal, and the authentication surface matches its allowlist exactly." This story delivers the first half; Story 4.6 delivers the second.
- **AD-26:** the contract is one module with one location and one owner. `FORBIDDEN_STATES` is a test-side index of *states*, not a second copy of the predicates — do not let it become a place where a condition's logic is duplicated.
- **AD-1:** one declaration site. `FORBIDDEN_STATES` names states; the predicates are declared once in `src/config/startup/`.
- **AD-13:** the migrations condition is exempt for management commands by design (process type fails open). Assert the exemption; do not treat it as a coverage gap.
- **Project standard:** never `print()`, never stdlib `logging` — `structlog` only. Never bare `except:`, never `except X: pass`.

### The fourteen forbidden states — the settled count

Reproduced from `_bmad-output/planning-artifacts/epics.md:308-326`. **Nine conditions — seven unconditional, two conditional — across fourteen distinct forbidden states**, each tested separately under FR-16. This table is the contents of `FORBIDDEN_STATES`.

| # | Condition | Stage | Forbidden states |
|---|---|---|---|
| 1 | The sqlite backend is reached | 1 | 1 *(built: `production.py:26-28`)* |
| 2 | A local credential path is live in settings | 1 | 4 — `ModelBackend` in `AUTHENTICATION_BACKENDS`; non-empty `ACCOUNT_LOGIN_METHODS`; `DJANGO_ADMIN_FORCE_ALLAUTH` not true; `rest_framework.authtoken` installed or `TokenAuthentication` in the DRF defaults |
| 3 | `OTEL_SDK_DISABLED` is true | 1 | 1 |
| 4 | The JWKS trust anchor is not derived from the configured IdP | 1 | 1 |
| 5 | The claims contract is unusable | 1 and 2 | 2 — unconfigured (stage 1); a designated group absent from the database (stage 2, AD-27) |
| 6 | A forbidden credential route is reachable in the resolved URLconf | 2 | 2 — `obtain_auth_token`; the local sign-in route |
| 7 | Unapplied migrations exist on a serving process | 2 | 1 |
| 8 | *(conditional — Redis selected)* An in-process cache backend is configured | 1 | 1 |
| 9 | *(conditional — background tasks selected)* Eager task execution is enabled | 1 | 1 |

**Why the count is settled and not re-derivable.** The source is arithmetically inconsistent: PRD §4.3 and FR-16 both state nine conditions; FR-13 says "seven conditions" and then lists eight bullets; and AD-27 adds a stage-2 refusal that appears in no FR-13 bullet, which under a strict per-bullet reading would make ten. The decision — nine conditions, seven unconditional and two conditional — applies FR-16's own rule that one condition may cover several distinct forbidden states. Conditions 5 and 6 are the two groupings, both following the precedent FR-16 already sets for the four settings-side credential paths. **Do not re-open the arithmetic; assert against fourteen.**

**Ownership map for the marker sweep:**

| States | Owning story | Test module |
|---|---|---|
| 1, 2a–2d, 3, 4, 5-stage-1 (eight states) | 4.2 | `tests/unit/config/startup/test_stage_one_conditions.py` |
| 6a, 6b (two states) | 4.3 | `tests/unit/config/startup/test_stage_two_urlconf.py` |
| 7, 5-stage-2 (two states) | 4.3 | `tests/integration/config/startup/test_stage_two_database_conditions.py` |
| 8, 9 (two states) | 4.4 | `tests/unit/config/startup/test_feature_scoped_refusals.py` |

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tests/unit/config/startup/forbidden_states.py` | NEW | The fourteen-entry `FORBIDDEN_STATES` declaration plus the FR-12 escape-route entry. |
| `tests/unit/config/startup/test_refusal_coverage_audit.py` | NEW | Two-way audit: every state claimed, every marker recognized, count exactly fourteen. |
| `tests/unit/config/startup/test_no_softening.py` | NEW | CG-3: no warning, no log-and-continue, no `warnings.warn`/bare-except in the source, correct exception type. |
| `tests/integration/config/startup/test_stage_two_served_path.py` | NEW | Four stage-2 conditions through the ASGI served path, plus the management-command control and the migrations exemption. |
| `tests/unit/config/startup/test_stage_one_conditions.py` | UPDATE | Created by Story 4.2. **Change:** add `@pytest.mark.forbidden_state(...)` to eight test functions; add positive controls where missing. **Preserve:** every existing assertion. |
| `tests/unit/config/startup/test_stage_two_urlconf.py` | UPDATE | Created by Story 4.3. **Change:** markers on the two route-state tests. **Preserve:** the two evasion tests and the negative case. |
| `tests/integration/config/startup/test_stage_two_database_conditions.py` | UPDATE | Created by Story 4.3. **Change:** markers on the two database-state tests. **Preserve:** transaction-rollback semantics so state is left as found. |
| `tests/unit/config/startup/test_feature_scoped_refusals.py` | UPDATE | Created by Story 4.4. **Change:** markers on the two conditional-state tests. **Preserve:** the `feature:<name>` disposition notes in the module docstring. |
| `tests/unit/test_settings.py` | UPDATE | Today: fresh-import tests for `base`/`local`/`production` with the `_evict_settings_modules` autouse fixture at `:24-30` and `no_database_env` at `:33-37`. **Change:** confirm the escape-route test lives here or in `tests/unit/config/startup/`, in one place only. **Preserve:** the eviction fixture semantics. |
| `pyproject.toml` | UPDATE | Today: `[tool.pytest.ini_options]` at `:141-157` with `addopts = ["--ds=config.settings.test", "--reuse-db", "--import-mode=importlib"]`, `pythonpath = ["src", "."]`, and one marker (`integration`). **Change:** register the `forbidden_state` marker. **Preserve:** `--ds`, `--reuse-db`, `--import-mode=importlib` and the `pythonpath` entries — the last is removed by Epic 1 Story 1.6 (AD-7), not here. |

**Does not exist yet and is not created here:** `accelerator.toml`, `component.toml`, `tools/materializer/`, `src/config/authorization/`, the local sign-in module.

### Testing Requirements

- Everything in this story is test code. It adds no production surface, so its own coverage contribution is the marker sweep and the audit.
- All four stage-2 served-path tests carry `@pytest.mark.integration` (registered at `pyproject.toml:155-157`) and must leave resources as found — create `Group` rows inside the default rolling-back `django_db` transaction, never persisting.
- Unit tests stay in `tests/unit/` and touch no database, network or filesystem.
- The audit test must be deterministic: collection order must not affect the result, so accumulate claimed `state_id`s into a set before asserting.
- AD-20 coverage floor: ninety percent including templates, `COVERAGE_CORE=ctrace` in force (`pixi.toml:145-151`). Do not add `src/config/startup/` or any part of `tests/config/startup/` to `[tool.coverage.run] omit` (`pyproject.toml:160-168`) — the omit list is a closed carrier-declared surface and a narrowing here would blind the only residue detector the product has.
- Test-location convention (spine, Consistency Conventions): tests mirror `src/` and carry the disposition of what they cover. States 8 and 9's tests are `feature:redis` and `feature:celery`; the other twelve are `core`. Keep them separable.
- `pixi run test` and `pixi run test-integration` in the inner loop; `pixi run ci` (`pixi.toml:206`, `depends-on = ["test-cov", "lint", "typecheck", "build"]`) is the done condition.

#### Project Structure Notes

Aligned with the Structural Seed and the Test-location convention. This story is the epic's closing audit and depends on Stories 4.2, 4.3 and 4.4 having landed — it marks and audits their tests rather than writing the conditions. If any of the three has not landed, implement `FORBIDDEN_STATES`, the audit test and the CG-3 tests, and let the audit fail on the unclaimed states; do not stub the missing conditions or weaken the audit to pass.

The AD-30 immovable-core assertion suite that runs inside every combination's gate is Epic 8's, and Epic 8 extends this epic's assertions to twelve combinations. That is a **traceability marker, not an acceptance condition for this story**.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.5]
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — lines 308-326
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-16]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#CG-3]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#SC-5]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
