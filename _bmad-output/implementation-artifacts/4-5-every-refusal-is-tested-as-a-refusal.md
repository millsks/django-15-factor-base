---
status: done
baseline_revision: 30eaa16b05bb4c9150e44a3a04d2cd815fadc29f
review_loop_iteration: 0
---

# Story 4.5: Every refusal is tested as a refusal

Status: done

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

- [x] Task 1 — Declare the fourteen forbidden states as data (AC: #1)
  - [x] Add `tests/unit/config/startup/forbidden_states.py` holding a single module-level tuple `FORBIDDEN_STATES` of frozen dataclass records, one per state: a stable `state_id`, its condition number (1–9), its stage (1 or 2), and a one-line description. Fourteen entries, matching the table in Dev Notes exactly.
  - [x] This is a **test-support declaration, not a second copy of the contract**. It names states, not predicates. The predicates live once in `src/config/startup/` (AD-26, AD-1).
  - [x] Mark each entry with whether it is conditional (`feature:redis` for state 8, `feature:celery` for state 9), so Epic 7 can dispose of the two conditional entries with their features.

- [x] Task 2 — The coverage audit test (AC: #1)
  - [x] Add `tests/unit/config/startup/test_refusal_coverage_audit.py` with one test that collects every test function in `tests/unit/config/startup/` and `tests/integration/config/startup/` and asserts that every `state_id` in `FORBIDDEN_STATES` is claimed by at least one of them.
  - [x] Claiming mechanism: a `@pytest.mark.forbidden_state("<state_id>")` marker applied to each refusal test. Register the marker in `[tool.pytest.ini_options] markers` in `pyproject.toml:155-157`, alongside the existing `integration` marker.
  - [x] The audit fails in both directions: an unclaimed state fails, and a marker naming a `state_id` not in `FORBIDDEN_STATES` fails. A one-way check lets a renamed state go dark.
  - [x] Collect markers by walking the test modules with `pytest`'s own collection (an `pytest.Item`-level hook or a session-scoped fixture recording `item.iter_markers("forbidden_state")`), not by parsing source text.
  - [x] Assert the count is exactly fourteen, so adding a tenth condition without updating the declaration fails rather than passing quietly.

- [x] Task 3 — Apply the marker across the existing refusal tests (AC: #1)
  - [x] Mark the eight stage-1 states in `tests/unit/config/startup/test_stage_one_conditions.py` (Story 4.2): sqlite; `ModelBackend`; non-empty `ACCOUNT_LOGIN_METHODS`; `DJANGO_ADMIN_FORCE_ALLAUTH` not true; the static-token surface; `OTEL_SDK_DISABLED`; the JWKS anchor; the unconfigured claims contract.
  - [x] Mark the four stage-2 states across `tests/unit/config/startup/test_stage_two_urlconf.py` and `tests/integration/config/startup/test_stage_two_database_conditions.py` (Story 4.3): `obtain_auth_token` route; local sign-in route; unapplied migrations; designated group absent.
  - [x] Mark the two conditional states in `tests/unit/config/startup/test_feature_scoped_refusals.py` (Story 4.4): in-process cache; eager tasks.
  - [x] Where a condition covers several states — condition 2 (four states), condition 5 (two states), condition 6 (two states) — each state must be its own test function with its own marker. Do not parameterize four states onto one function in a way that leaves a single marker covering all of them; if `pytest.mark.parametrize` is used, apply the `forbidden_state` marker per parameter set with `pytest.param(..., marks=...)`.

- [x] Task 4 — The settings-module escape route (AC: #2)
  - [x] Story 4.1 implements the condition and its first test. This story asserts it is present, marked, and constructed correctly: `monkeypatch.delenv("COMPONENT_RUNTIME", raising=False)`, fresh import of `config.settings.local`, `pytest.raises(ImproperlyConfigured)`.
  - [x] The test must import the settings module for real rather than calling `run_stage_one` with a hand-built namespace — the point of FR-12's escape route is that the *module load path* refuses, and a synthesized namespace does not exercise it.
  - [x] Use the eviction fixture pattern at `tests/unit/test_settings.py:24-30`, extended to evict `config.settings.local` and `config.settings.base` together; without evicting `base`, the `from .base import *` reuses an already-imported copy and the module-level environment reads are not re-evaluated.
  - [x] Give this test its own `state_id` entry outside the fourteen (it is FR-12's test, not a refusal condition) and assert its presence separately, so it cannot be traded off against the fourteen.

- [x] Task 5 — Each stage-2 condition through a served request path (AC: #3)
  - [x] Add `tests/integration/config/startup/test_stage_two_served_path.py`, `@pytest.mark.integration`, driving requests through `config.asgi:application` with an ASGI transport rather than through `manage.py`.
  - [x] One test per stage-2 condition — four in total: the `obtain_auth_token` route, the local sign-in route, unapplied migrations, and the absent designated group. Each configures the forbidden state, starts the application through the served path, and asserts `ImproperlyConfigured`.
  - [x] Add the paired control: one test that invokes `django.core.management.call_command("check")` and asserts the same condition fires there too, so "it fires under management commands as well" is proven rather than assumed — except for the migrations condition, which is deliberately exempt for management commands (AD-13 fail-open, FR-13 stage 2). Assert that exemption explicitly.
  - [x] `src/config/asgi.py` is in the coverage `omit` list at `pyproject.toml:166`; these tests assert behaviour reached *through* it and do not require changing that list.

- [x] Task 6 — CG-3: no refusal is softened (AC: #4)
  - [x] Add `tests/unit/config/startup/test_no_softening.py`.
  - [x] Test A: run each condition against its forbidden state with `pytest.warns(None)` semantics — assert the call raises `ImproperlyConfigured` **and** that `warnings.catch_warnings(record=True)` captured nothing. A condition that warns and raises is still wrong shape; a condition that warns and returns is the failure CG-3 names.
  - [x] Test B: capture `structlog` output with `structlog.testing.capture_logs()` around each forbidden state and assert that no log event is emitted *in place of* the raise. Logging alongside a raise is permitted; logging instead of it is not.
  - [x] Test C: a source-level scan of `src/config/startup/*.py` asserting the module contains no `warnings.warn(`, no bare `except:`, and no `except <Exception>: pass` — the project standard forbids all three, and here they are also the exact shape CG-3 prohibits.
  - [x] Test D: assert every condition's failure path raises `django.core.exceptions.ImproperlyConfigured` specifically, not a bare `Exception`, `ValueError` or `RuntimeError` — the Consistency Conventions table fixes the type: "Every forbidden or missing configuration raises `ImproperlyConfigured` at one of the two refusal stages."

- [x] Task 7 — Positive controls (AC: #1)
  - [x] For each of the nine conditions add, or confirm from the owning story, one test where the condition's input is *valid* and no exception is raised. Without positive controls a predicate hardcoded to raise passes all fourteen refusal tests.
  - [x] Add one end-to-end positive: a fully valid deployed settings namespace and a clean URLconf pass `run_stage_one` and `run_stage_two` together without raising.

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

Reproduced from `_bmad-output/planning-artifacts/epics.md:310-328`. **Nine conditions — seven unconditional, two conditional — across fourteen distinct forbidden states**, each tested separately under FR-16. This table is the contents of `FORBIDDEN_STATES`.

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

The AD-30 immovable-core assertion suite that runs inside every combination's gate is Epic 8's, and Epic 8 extends this epic's assertions to all six combinations. That is a **traceability marker, not an acceptance condition for this story**.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.5]
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — lines 310-328
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-16]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#CG-3]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#SC-5]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m]

### Debug Log References

- `pixi run ci` — exit 0. 1214 passed, total coverage 96.78% (floor 90).
- `DATABASE_URL=postgres://…/app_test pixi run test-cov` — exit 0. 1214 passed,
  total coverage 96.78%. The suite behaves identically on PostgreSQL 17 and on
  the sqlite default.
- Negative-control run of the audit: removing one `forbidden_state` marker fails
  `test_every_forbidden_state_is_claimed_by_a_refusal_test[sqlite-backend]`;
  misspelling one additionally fails
  `test_no_claim_names_a_state_the_declaration_does_not_have`. Both directions
  verified, then reverted.
- Negative controls for the review-pass assertions, each applied and reverted:
  a marker on a body that asserts nothing fails
  `test_every_claiming_test_asserts_a_refusal`; the same marker under
  `@pytest.mark.skip` additionally fails
  `test_no_claim_is_carried_by_a_test_that_never_runs`; an
  `except (builtins.Exception, OSError):` added to `stage_two.py` fails
  `test_the_broad_handlers_are_the_recorded_ones_and_no_more`, which the previous
  dotted-name reader did not see; and a
  `warnings.warn(..., stacklevel=2)` beside condition 1's raise fails
  `test_the_forbidden_state_raises_and_warns_about_nothing[sqlite-backend]`,
  which the previous filename filter did not see.

### Completion Notes List

**Spec-vs-tree drift reconciled.** The story writes every test path as
`tests/unit/config/startup/...` and `tests/integration/config/startup/...`. No
`config/` level exists: Stories 4.1-4.4 put the suite at `tests/unit/startup/`
and `tests/integration/startup/`. Every path in the Source Tree table was mapped
accordingly, and no `config/` directory was created. Line references were stale
too -- the pytest `markers` list is at `pyproject.toml:229`ff, not `:155-157`,
and `[tool.coverage.run]` is at `:240`ff, not `:160-168`. Nothing was added to
the coverage `omit` list.

**The count is expressed as twelve plus two, not as a literal fourteen.** AD-24
requires states 8 and 9 to leave with their features. A bare
`len(FORBIDDEN_STATES) == 14` would fail a materialized combination that dropped
one, so the audit asserts twelve unconditional states (a literal, feature-neutral)
plus one marker-delimited entry per feature, and the sum itself is asserted --
`UNCONDITIONAL_STATE_COUNT` plus the states the features own equals
`len(FORBIDDEN_STATES)`. Fourteen is the sum in this tree and shrinks with the
tree. The conditional expectation is keyed feature → **set** of state ids rather
than feature → one id, so a feature growing a second state fails rather than
overwriting its first. Three files gained AD-24 region markers --
`forbidden_states.py`, `test_refusal_coverage_audit.py`, `test_no_softening.py`
-- and each is declared in `stage_one.py`'s docstring bullet list and added to
`MARKER_BEARING_PATHS` in `test_feature_scoped_refusals.py`, so the existing
balance, interleave, naming and two-way reconciliation assertions now cover them.
`test_no_softening.py` carries two `feature:redis` pairs: one for condition 8's
CG-3 builder, and one for the `stage_one.py` entry in `BROAD_EXCEPT_ALLOWANCE` --
the `except Exception` that entry records sits inside `stage_one.py`'s own
`feature:redis` region, so an allowance outside a region would have failed a
correctly materialized tree that no longer had the handler.

**FR-16 is per condition, so the audit asserts the distribution and not only the
count.** Twelve unconditional states fixed by a literal says nothing about which
conditions they belong to: condition 3's state could be deleted and a second
added under condition 1 with every count green.
`test_every_numbered_condition_owns_at_least_one_state` asserts the partition --
the unconditional states cover exactly conditions 1 to 7, and each feature's
states cover exactly that feature's condition -- which holds unchanged on a
materialized combination, because conditions 8 and 9 leave with their features.

**Claims are collected by a child `pytest --collect-only`, not by the running
session.** `pixi run test` collects `tests/unit/` alone and `pixi run
test-integration` collects `tests/integration/` alone, so an audit reading its own
session's collection would report the other half's states as unclaimed and would
pass or fail on how the suite was invoked. `tests/conftest.py` gained a
`pytest_collection_modifyitems` hook that reads `item.iter_markers` and writes a
JSON report when `FORBIDDEN_STATE_CLAIM_REPORT` names a path; the audit sets that
variable on a child collecting the whole of `tests/` (about one second). The hook
is `@pytest.hookimpl(trylast=True)` so that markers another hook applies are in
the report its docstring promises to carry, and it creates the report path's
parent directory before writing -- a variable naming a path in a directory that
does not exist would otherwise raise out of collection and take the whole session
with it.

**A marker is a claim only if the test it marks runs and asserts a refusal.** Two
gaps closed in review. The collector records claims carried by a test with
`skip`, `skipif` or `xfail` separately from live claims, and
`test_no_claim_is_carried_by_a_test_that_never_runs` fails on any of them, so a
never-executed test no longer satisfies the audit. And
`test_every_claiming_test_asserts_a_refusal` resolves each claiming node id back
to its function and requires the body to contain a `pytest.raises` on the refusal
type, a call to the owning module's `_refusal` helper, or an assertion naming a
refusal -- the third clause being what the served-path cases take, where the raise
happened in a child process. The residue is recorded below.

**The audit child runs on `subprocess_env()`, like every other probe.** It built
its own environment from `dict(os.environ)` and popped `PYTEST_ADDOPTS` alone,
which meant it inherited `DATABASE_URL`, `DJANGO_SETTINGS_MODULE` and the
`POSTGRES_*` set that the shared helper drops for reasons its docstring records,
and pytest-cov's `COV_CORE_*` subprocess activation -- so every audit run wrote a
`.coverage.<host>.<pid>` file into the repository root that nothing combined. The
helper moved from `tests/integration/startup/conftest.py` to `tests/conftest.py`
(a unit module may not import an integration package's conftest) and gained the
`COV_CORE_*` drop, which every boot probe now inherits too.

**Task 4 -- the escape route was already delivered and correctly constructed.**
`tests/unit/startup/test_stage_one_escape_route.py` (Story 4.1) deletes
`COMPONENT_RUNTIME`, evicts `config.settings.local` *and* `config.settings.base`
through an autouse fixture, imports the module for real and asserts
`ImproperlyConfigured`. It was marked, not duplicated; nothing was added to
`tests/unit/test_settings.py`.

**Task 5 -- the served-path probe moved rather than being written twice.** Story
4.3 had already built an ASGI probe driving all four stage-2 conditions from a
process that had served a request, as one test at the end of
`test_stage_two_database_conditions.py`. FR-16 wants one case per condition, so
the probe source and its assertions moved to
`tests/integration/startup/test_stage_two_served_path.py` and were split into four
marked cases plus the positive control and the AD-13 exemption. Every assertion is
preserved; the old module carries a pointer paragraph. One was not, and was
restored in review: the "left the tree as it found it" case compared the migrated
database against `tmp_path_factory.getbasetemp()` -- the session temporary root
that every test's files live under -- where the original compared it against the
probe's own scratch directory. The fixture now records that directory in the
report and the case compares against it.

**Task 5 -- the management-command control needed a real settings module on disk.**
`call_command("check")` in the running process cannot re-fire stage 2: `ready()`
already ran during collection. A synthesized in-memory settings module does not
work either, because `config/__init__.py` imports `config.celery_app`, whose
`os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")` runs on
the first import of anything under `config` and configures `django.conf.settings`
from the local module first -- an early attempt did exactly that and silently ran
the migrations condition against the repository's own database. The control now
generates `probe_settings.py` and `probe_urlconf.py` into `tmp_path`, runs
`execute_from_command_line(["manage.py", "check"])` in a fresh interpreter with
that directory as its working directory, and reports the refusal. The refusal
arrives out of `django.setup()`, which every management command performs.

**AD-13's exemption is wider than the story states, and is asserted as it is --
for both conditions.** Both database-backed stage-2 conditions gate on
`is_serving_process()`, not just the migrations one, so a management command with
no `COMPONENT_PROCESS` declaration is exempt from both. As first written the
control asserted the exemption and its paired half for the migrations condition
alone, while these notes claimed both; review added condition 5's pair. Reaching
condition 5's stage-2 half from a management command takes a database that is
*migrated* -- condition 7 evaluates first and would refuse a never-migrated one
before condition 5 was consulted -- and `django.setup()` is idempotent, so a
second command in the same child never re-enters `ready()`. So a module-scoped
fixture runs `manage.py migrate` in a child of its own with no process type
declared (which is AD-13's exemption doing exactly the job it exists for), and
the two cases then run `manage.py check` against that database under a claims
contract designating two groups the migration did not provision.

**The management-command probe's settings module drops the dev tooling, and that
is not tidying.** `config/settings/local.py` installs django-debug-toolbar under
`DJANGO_DEBUG_APPS`, and its `AppConfig.ready()` hides its own migrations from
`migrate` unless the database store is configured -- while anything reading
migration state from inside an *earlier* `AppConfig.ready()`, which is where stage
2 runs, still sees them. A child that kept it reported
`debug_toolbar.0001_initial` pending on a database that had just been fully
migrated, which is a state no `manage.py migrate` can clear. A deployed component
does not install it either, so the generated module filters it and
`django_extensions` out of `INSTALLED_APPS` and drops the toolbar middleware.

**Task 6 Test C distinguishes swallowing from a documented skip.** Story 4.4's
`except Exception` around `import_string` in `_refuse_in_process_cache` continues
to the next cache alias under a comment recording why; it does not `pass`. The
scan is AST-based and bans the *no-op body* (`pass`, `...`), the bare `except:`,
and any `warnings` import or `warn` call, then freezes the count of broad handlers
at `{"stage_one.py": 1}` so a second one fails while the recorded one does not.

**Task 6 Test B is guarded against the structlog capture going blind, and Test A
against its filter going blind.** A fixture emits one event through
`capture_logs()` and requires it to arrive before any case asserts silence; the
integration half carries the same control, and it is an **autouse fixture** there
now rather than a case defined after the one it protects -- as a case it ran
second by definition order alone, so `-x`, `-k` or any reordering left the silence
assertion passing vacuously. Test A gained the mirror control it did not have:
`warning_filter_is_live` raises a warning attributed to `stage_one.py`'s own
`__file__` and requires it to be recorded, so an editable-install redirect or a
symlinked path cannot silently make every "warned about nothing" assertion
vacuous. `pytest.warns(None)` is not used -- modern pytest raises on it.

Test A no longer decides what belongs to the contract by filename alone.
`warnings.warn(..., stacklevel=2)` is ruff's preferred spelling and attributes the
record to the *caller*, which for these builders is the test module itself, so a
filename filter missed the likeliest spelling of the failure CG-3 names. The
recorder now also consults the live frame stack: whatever `stacklevel` claims, a
warning issued from inside a condition has that condition's frame on the stack.
A third-party `DeprecationWarning` still cannot fail the case.

**Every case asserts what the refusal said, not only that one arrived.** Tests A,
B and D drove a builder and asserted the type; stage 1 evaluates a roster in
order and every condition raises the same class, so a builder that stopped
constructing its state -- or a condition deleted outright -- would have kept all
three green under the label of the state no longer being checked. Each entry in
the refusal table now carries one distinguishing substring of its own message and
every case asserts it, which is what every other module in this package already
did. The integration half does the same.

**Task 6 covers twelve states in the unit module and two in the integration one.**
Unapplied migrations and an absent designated group need a live connection, so
their CG-3 assertions live in `test_stage_two_served_path.py`. The split is
reconciled by an equality: every declared state is either in the unit module's
builder table or in `DELEGATED_TO_THE_INTEGRATION_SUITE`, never both and never
neither. That equality was one-way as first written -- it compared two lists and
said nothing about whether the module a state was delegated *to* covered it, and
the migrations state had no case there while three docstrings claimed it did. The
delegated set moved to `forbidden_states.py`, where both modules can read it, and
the integration class now parametrizes its cases straight off it, so a delegated
state with no builder fails on that side. The migrations case constructs its state
the way the group case does: a row deleted inside `django_db`'s transaction --
here the `django_migrations` record for an applied leaf, found rather than named
-- which the rollback restores.

**Task 7 -- one positive control was missing and was added.** Condition 5's
stage-1 half had no case handing it a valid contract; it now has
`test_a_contract_carrying_all_four_names_is_accepted`. The other eight were
confirmed present from their owning stories:
conditions 1 (`test_a_second_alias_on_a_real_backend_is_accepted`), 2
(`test_the_backend_a_deployed_component_keeps_is_accepted_though_it_subclasses_model_backend`),
3 (`test_an_enabled_sdk_is_accepted`), 4
(`test_an_explicit_location_under_the_issuer_is_accepted`), 5-stage-2
(`test_both_designated_groups_present_is_accepted`), 6
(`test_an_allauth_and_admin_url_configuration_is_accepted`), 7 (the served-path
probe's `everything_satisfied`), 8 (`test_the_redis_cache_backend_is_accepted`)
and 9 (`test_eager_execution_switched_off_is_accepted`). The end-to-end positive
is `test_both_stages_accept_a_fully_valid_component_together`.

**Residual risks.** (1) The audit reads a child collection of `tests/`; a marker
placed in a file the suite does not collect is invisible to it, as it is to
pytest. (2) The management-command probe clears `PYTHONSAFEPATH` for its own
child so the generated settings module resolves from that child's working
directory; `config` and `django_service` still resolve only through the editable
install, and no Python file in the repository declares an import root. (3) An
early, since-fixed revision of that probe ran the migrations condition against the
local settings module's own database and may have created the gitignored
`db.sqlite3` in the repository root; the committed tests never touch it.

(4) **The management-command probe exercises stage 2 only.** Its generated
settings module composes `config.settings.local` under a declared local runtime
and then drops the declaration, so stage 1 ran while the run was still local and
evaluated nothing -- and the namespace would not survive stage 1 if it did,
because the throwaway database these children need is sqlite and condition 1
refuses sqlite outright. Building the child on a genuinely deployed-shaped
namespace would mean a real PostgreSQL for every run of that file, which
`pixi run ci` does not have. The limitation is *measured* rather than left as
prose: the child reports what stage 1 would have said about its own namespace and
`test_the_probe_never_has_stage_one_evaluated_over_it` asserts that it is a
refusal naming the sqlite backend. So the clean control run in that class is
evidence about stage 2 and about nothing else, and the day the probe could be
built deployed-shaped, that case is what fails.

(5) **A claim still cannot be proved to configure the state it names.**
`test_every_claiming_test_asserts_a_refusal` establishes that a claiming test
asserts *a* refusal; nothing static can establish that the state it configures is
the state its marker names, and the third of its three clauses -- an assertion
mentioning a refusal, which is the shape the served-path cases take because their
raise happened in a child process -- is satisfied by any such assertion. What is
closed is the marker on a test that asserts no refusal at all, and the marker on a
test that never runs. What is open is the marker on the wrong refusal test, which
the per-state message assertions in the owning modules make unlikely rather than
impossible.

### File List

- `pyproject.toml` (UPDATE) -- registered the `forbidden_state` marker.
- `src/config/startup/stage_one.py` (UPDATE) -- six AD-24 region-declaration
  bullets for the three new marker-bearing files this story added
  (`forbidden_states.py` is a declaration module rather than a test module; the
  other two are test modules). No behaviour change.
- `tests/conftest.py` (UPDATE) -- `FORBIDDEN_STATE_MARKER`,
  `FORBIDDEN_STATE_REPORT_ENV_VAR`, the report's two keys, `DISABLING_MARKERS`,
  the `trylast` `pytest_collection_modifyitems` claim collector, and
  `subprocess_env` with `SUBPROCESS_ENV_DROPPED` (moved here from
  `tests/integration/startup/conftest.py`).
- `tests/integration/startup/conftest.py` (UPDATE) -- keeps `REPO_ROOT` and
  `BOOT_PROBE_TIMEOUT_SECONDS`; `subprocess_env` moved to the shared home.
- `tests/integration/startup/test_stage_two_fires.py` (UPDATE) -- imports
  `subprocess_env` from its new home.
- `tests/unit/startup/forbidden_states.py` (NEW) -- `FORBIDDEN_STATES` (fourteen
  records), `ESCAPE_ROUTE_STATE` and `DELEGATED_TO_THE_INTEGRATION_SUITE`.
- `tests/unit/startup/test_refusal_coverage_audit.py` (NEW) -- the two-way audit,
  the declaration's count and distribution, and the claim-quality checks.
- `tests/unit/startup/test_no_softening.py` (NEW) -- CG-3 tests A, B, C and D.
- `tests/integration/startup/test_stage_two_served_path.py` (NEW) -- the four
  stage-2 conditions on the served path, the management-command control for both
  URLconf conditions and both database-backed ones, AD-13's exemption and its
  paired half for each, CG-3 for the two database states, and the end-to-end
  positive.
- `tests/unit/startup/test_stage_one_conditions.py` (UPDATE) -- eight markers and
  condition 5's missing positive control.
- `tests/unit/startup/test_stage_two_urlconf.py` (UPDATE) -- two markers.
- `tests/unit/startup/test_feature_scoped_refusals.py` (UPDATE) -- two markers,
  three paths added to `MARKER_BEARING_PATHS`.
- `tests/unit/startup/test_stage_one_escape_route.py` (UPDATE) -- one marker.
- `tests/integration/startup/test_stage_two_database_conditions.py` (UPDATE) --
  three markers; the served-path probe moved out, with a pointer left behind.
