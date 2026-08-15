---
baseline_commit: 1e9e022e139baef6ff78f9590dea0bbaa1af79c8
final_revision: ab5d768
review_loop_iteration: 0
followup_review_recommended: true
status: done
---

# Story 1.2: The gate runs against PostgreSQL

Status: done

## Story

As a platform engineer,
I want CI to run the suite against PostgreSQL rather than the sqlite substitution,
so that the database named in the immovable core is actually verified before anything is built on it.

## Acceptance Criteria

**Traceability:** FR-32 (reference application) · AD-18 · SC-1

1. **Given** no workflow declares a database service today
   **When** the gate job runs
   **Then** CI declares a PostgreSQL service
   **And** sets the database URL for the gate run

2. **Given** the suite has only ever run against sqlite
   **When** it first runs against PostgreSQL
   **Then** every failure arising from sqlite-permissive behaviour is fixed at its source
   **And** none is skipped or marked `xfail`

3. **Given** a schema PostgreSQL rejects and sqlite accepts
   **When** the gate runs
   **Then** the gate fails

4. **Given** local development uses the sqlite substitution
   **When** a developer runs the suite with no database running
   **Then** it still runs on sqlite
   **And** the divergence remains the knowingly traded parity gap rather than a defect

## Tasks / Subtasks

- [x] Task 1 — Declare the PostgreSQL service on the gate job (AC: #1)
  - [x] In `.github/workflows/ci.yml`, add a `services:` block to the `gate` job created by Story 1.1. Use `postgres:18` to match the `libpq = ">=18.4,<19"` pin at `pixi.toml:16`. Declare `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB`, `ports: ["5432:5432"]`, and health options `--health-cmd pg_isready --health-interval 10s --health-timeout 5s --health-retries 5`.
  - [x] Set `DATABASE_URL` on the gate job's `env:` (job level, not step level, so every step of `pixi run ci` sees it). `src/config/settings/base.py:57-58` reads `DATABASE_URL` first and hands it to `env.db(...)`, so the URL is the whole mechanism — no settings change is needed to select PostgreSQL. Format: `postgres://<user>:<password>@localhost:5432/<db>`.
  - [x] The service block runs only on Linux runners. Keep it on the ubuntu-only `gate` job; do not attach it to the three-OS compatibility matrix job, which continues on the sqlite substitution.
  - [x] Add a comment beside the service block stating why it exists: FR-32 requires the gate to run against the database the immovable core names, and no workflow declared one before this story.

- [x] Task 2 — Verify PostgreSQL selection actually takes effect in the test settings (AC: #1, #3)
  - [x] `pyproject.toml:143` pins `--ds=config.settings.test`. `src/config/settings/test.py` does `from .base import *` and overrides no database setting, so `DATABASE_URL` reaches it unchanged. Confirm this by running the suite locally with `DATABASE_URL` pointed at a PostgreSQL instance before touching anything else.
  - [x] `pyproject.toml:144` sets `--reuse-db`. Against a service container that is recreated per run, `--reuse-db` is harmless but hides schema drift on repeat local runs. Leave it in place; note in `docs/development.md` that a local PostgreSQL run may need `--create-db` after a migration change.
  - [x] `src/config/settings/base.py:80` sets `DATABASES["default"]["ATOMIC_REQUESTS"] = True` unconditionally. This is a PostgreSQL-meaningful setting that sqlite tolerates; expect transaction-scoped failures to surface here first.

- [x] Task 3 — Fix every sqlite-permissive failure at its source (AC: #2, #3)
  - [x] Run the full suite against PostgreSQL and triage each failure. The expected classes are: unordered `QuerySet` results (sqlite frequently returns insertion order, PostgreSQL does not — fix by adding an explicit `order_by` in the code or by asserting against a set); `max_length`/type-strictness rejections; `CharField` values exceeding declared length; `null` vs empty-string handling; and case-sensitivity differences in `filter(...)` lookups. — **Zero failures surfaced.** See Debug Log References and Completion Notes.
  - [x] Every fix goes in the source that caused it — `src/django_service/users/models.py`, `src/django_service/users/api/views.py`, `src/django_service/users/forms.py`, or the migration that declared the column — not in the test. — vacuous: no fix was required, so none of those files is touched.
  - [x] Forbidden: `@pytest.mark.skip`, `@pytest.mark.xfail`, `pytest.skip(...)`, `@pytest.mark.django_db(databases=...)` narrowing, or a conditional that branches on the engine inside a test. AC #2 states none is skipped or marked `xfail`. — none used anywhere in the suite; verified by grep.
  - [x] If a failure is a genuine model or migration defect, fix it with a new migration under `src/django_service/users/migrations/` or `src/django_service/contrib/sites/migrations/`. Do not edit an applied migration in place. — no migration added or edited.

- [x] Task 4 — Preserve the sqlite substitution for local development (AC: #4)
  - [x] Do not change the `else` branch at `src/config/settings/base.py:71-78`, which falls back to `django.db.backends.sqlite3` at `BASE_DIR / "db.sqlite3"` when neither `DATABASE_URL` nor `POSTGRES_DB` is set. — `src/config/settings/base.py` is byte-for-byte unchanged.
  - [x] Do not change the production refusal at `src/config/settings/production.py:26-28`, which raises `ImproperlyConfigured` when the resolved engine ends with `sqlite3`. That refusal is Epic 4's condition #1 and is already built; this story must leave it exactly as found. — unchanged; still covered by `tests/unit/test_settings.py::test_production_refuses_sqlite`.
  - [x] Record the parity gap in `docs/development.md`: local runs use sqlite, the gate uses PostgreSQL, and the divergence is R-5 — a knowingly traded gap, not a defect. State that a failure reproducible only in CI is expected behaviour of this trade and is fixed at its source rather than by narrowing the gate.

- [x] Task 5 — Tests (AC: #1, #3, #4)
  - [x] Extend `tests/unit/test_gate_contract.py` (created in Story 1.1): assert the gate job declares a `services` entry whose `image` begins `postgres:`, and that the job-level `env` sets `DATABASE_URL`.
  - [x] New `tests/unit/test_database_selection.py`: assert the three-branch selection in `src/config/settings/base.py` behaves as declared — with `DATABASE_URL` set the engine is not sqlite; with only `POSTGRES_DB` set the engine is `django.db.backends.postgresql`; with neither set the engine is `django.db.backends.sqlite3`. Exercise this by reloading the settings module under `monkeypatch.setenv`/`delenv`, not by asserting on the already-imported `settings` object.
  - [x] New `tests/integration/test_postgres_schema.py`, every test marked `@pytest.mark.integration`: assert the migrated schema is reachable and that a write violating a declared `max_length` or `unique` constraint raises rather than truncating. Skip-free — the file runs against whatever database `DATABASE_URL` names, which in the gate is PostgreSQL and locally is sqlite.
  - [x] Every integration test must leave the database as it found it; rely on `pytest-django`'s transactional `db` fixture rather than committing rows.

## Dev Notes

### Architecture Constraints

- **FR-32:** "Every valid combination passes the full gate against PostgreSQL — no partial pass; CI must declare a PostgreSQL service, which no workflow does today." This story delivers the reference-application half only. Epic 8 Story 8.8 extends it to six combinations.
- **AD-18** binds FR-32 and places the PostgreSQL service in the single-invocation gate. The six-combination harness is Linux-only; the three-OS matrix stays on the reference application "where it claims something different" — that is, cross-platform importability, not database fidelity. **GitHub Actions `services:` containers are Linux-only**, so FR-32's PostgreSQL gate cannot run on that three-OS matrix at all: the gate job is ubuntu-only and the separate three-OS job runs `pixi run test` for platform compatibility.
- **AD-9** (forward context, Epic 9): "the stage-2 unapplied-migrations refusal and the sqlite refusal both iterate every configured database." Today `DATABASES` has exactly one key. Do not add a second database in this story; do not write a fix that assumes exactly one either.
- **R-5 — Local development proves less than running suggests.** "sqlite accepts schemas PostgreSQL rejects, eager execution never exercises delivery or retries, synthetic claims never exercise JWKS retrieval or rotation." AC #4's "knowingly traded parity gap" is this risk, stated by name.
- **CG-3 / Consistency Conventions:** "A refusal never degrades to a warning." Applied here as: a gate failure never degrades to a skip.

### Source Tree — files to touch

| Path | NEW or UPDATE | What changes |
| --- | --- | --- |
| `.github/workflows/ci.yml` | UPDATE | Story 1.1 leaves a `gate` job on `ubuntu-latest` running `pixi run ci`. This story adds the `services:` PostgreSQL block and the job-level `DATABASE_URL`. No other job gains a database. |
| `src/config/settings/base.py` | UPDATE (only if a fix requires it) | `:57-78` is the three-branch database selection: `DATABASE_URL` → `POSTGRES_*` → sqlite fallback. `:80` sets `ATOMIC_REQUESTS = True`. Preserve all three branches and the fallback comment at `:72-73`. |
| `src/config/settings/production.py` | UNCHANGED — verify only | `:26-28` raises `ImproperlyConfigured` on a sqlite engine. Confirm it still holds; change nothing. |
| `src/django_service/users/models.py`, `.../api/views.py`, `.../forms.py` | UPDATE (as failures dictate) | Source-level fixes for sqlite-permissive behaviour. Scope is whatever the first PostgreSQL run surfaces. |
| `docs/development.md` | UPDATE | Records the parity gap and the `--reuse-db` note. |
| `tests/unit/test_gate_contract.py` | UPDATE | Adds the service-declaration assertions. Created by Story 1.1. |
| `tests/unit/test_database_selection.py` | NEW | Asserts the three-branch selection. |
| `tests/integration/test_postgres_schema.py` | NEW | Schema-strictness assertions under `@pytest.mark.integration`. |

**Verified today (2026-08-15):** no file under `.github/workflows/` contains a `services:` key. `DATABASE_URL` is read at `src/config/settings/base.py:57`. `psycopg = ">=3.3,<4"` and `libpq = ">=18.4,<19"` are already declared at `pixi.toml:47` and `pixi.toml:16` — no dependency needs adding, and none may be added to `[pypi-dependencies]`.

### Testing Requirements

- `tests/integration/` files carry `@pytest.mark.integration` on every test (declared as a marker at `pyproject.toml:155-157`). `tests/unit/` files carry no marker and perform no I/O.
- `tests/unit/test_database_selection.py` mirrors `src/config/settings/`; `tests/integration/test_postgres_schema.py` mirrors the persistence layer of `src/django_service/`.
- Coverage floor is 90% including templates, `COVERAGE_CORE=ctrace` in force (AD-20). The `test-cov` task at `pixi.toml:196` enforces `--cov-fail-under=90`.
- Test disposition (spine §Consistency Conventions): these tests cover `core` paths and will be dispositioned `core` in Epic 7.
- The gate is `pixi run ci` and it must exit 0 against PostgreSQL. `pixi run test` (unit only) passing is not sufficient evidence for this story.

#### Project Structure Notes

No new directory is created. The Structural Seed's `src/config/settings/` already exists with `base`, `local`, `production`, `test`. `accelerator.toml`, `component.toml` and `tools/materializer/` — which Epic 8's six-combination PostgreSQL gate will need — do not exist yet and are out of scope.

Variance: the seed shows stage-1 refusals as "the last statement of every settings module" (AD-26). `src/config/settings/production.py` currently carries an inline ad-hoc sqlite refusal at `:26-28` instead. That is Epic 4's consolidation, not this story's — leave it where it is.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.2]
- [Source: _bmad-output/planning-artifacts/epics.md:72] — FR-32 text.
- [Source: _bmad-output/planning-artifacts/epics.md:222] — Epic 1 begins the PostgreSQL service; Epic 8 extends it to six combinations.
- [Source: _bmad-output/planning-artifacts/epics.md:318] — refusal condition #1 is "built: `production.py:26-28`".
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-18]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-9]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-5.

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`

### Debug Log References

**A real PostgreSQL 18 was used throughout.** Host port 5432 was already taken
by an unrelated `devinfra-postgres` container, so the throwaway ran on 55432:

```sh
docker run -d --name pg-story-1-2 -e POSTGRES_USER=gateuser \
  -e POSTGRES_PASSWORD=gatepass -e POSTGRES_DB=gatedb -p 55432:5432 postgres:18
# pg_isready: accepting connections after 1s
# server: PostgreSQL 18.4 (Debian 18.4-1.pgdg13+1) on aarch64-unknown-linux-gnu
```

1. **Baseline, before any edit** — `DATABASE_URL=postgres://gateuser:gatepass@localhost:55432/gatedb pixi run test-cov`
   → **118 passed, 92.31% coverage, exit 0.** PostgreSQL surfaced **no failures at
   all.** Confirmed the run was genuinely against PostgreSQL and not a silent
   sqlite fallback: `\l` in the container showed `test_gatedb` created, and `\dt`
   in it showed all 24 migrated tables (`users_user`, `account_emailaddress`,
   `django_celery_beat_*`, `django_site`, …).
2. **Fresh database** — the same URL with `pytest tests/ --create-db` → 118
   passed. Migrations apply cleanly to an empty PostgreSQL from scratch, so the
   clean baseline was not an artefact of `--reuse-db`.
3. **`pixi run ci` against PostgreSQL, first attempt** — failed at step 4
   (`lint`), not on the database: `TC003 Move standard library import
   types.ModuleType into a type-checking block` in the new
   `tests/unit/test_database_selection.py`. Note the pre-commit step *passed*
   the same file — pre-commit `--all-files` enumerates via `git ls-files` and
   the new files were untracked, so `pixi run lint`'s `ruff check .` was the
   only step seeing them. Fixed by moving the import under `if TYPE_CHECKING`;
   the new files were then `git add -N`'d so pre-commit sees them too, matching
   what CI does with a checked-out commit.
4. **`pixi run ci` against PostgreSQL, final** — **exit 0.** All five steps
   passed; **133 passed, 92.31% coverage** (118 before this story, +15 new).
5. **`pixi run ci` with `DATABASE_URL` and `POSTGRES_DB` both unset (AC #4)** —
   **exit 0**, 133 passed, 92.31%. The sqlite substitution is intact.

**Two probes run to prove the divergence is real rather than assumed.** Both
were throwaway and both were removed; neither is part of the change.

- *Data strictness.* A raw over-length write (`name` = 300 chars against
  `max_length=255`) — **sqlite: no exception, stored length 300.**
  **PostgreSQL: `DataError: value too long for type character varying(255)`.**
  This is why `test_a_value_over_the_declared_max_length_is_rejected` asserts
  through `full_clean()`: a database-level assertion would fail on sqlite, and
  making it pass there would have required exactly the engine-conditional AC #2
  forbids.
- *Schema strictness (AC #3 demonstration).* A temporary migration adding
  `CharField(max_length=0)` — **sqlite applied it and built the schema.**
  **PostgreSQL refused at migrate time: `psycopg.errors.InvalidParameterValue:
  length for type varchar must be at least 1`, erroring every test in the
  file.** A schema sqlite accepts and PostgreSQL rejects now fails the gate.

**Cleanup.** `docker rm -f pg-story-1-2`; the probe migration, its bytecode and
the scratch probe test were deleted. No container, volume or stray file remains.

### Completion Notes List

**The headline result: PostgreSQL surfaced zero failures.** Task 3 anticipated
a triage list — unordered `QuerySet` results, `max_length` rejections, `null`
versus empty-string handling, case-sensitivity in `filter(...)`. None of it
appeared. The suite went green against PostgreSQL on the first attempt, before
any edit. So **no file under `src/` is touched by this story at all**:
`models.py`, `api/views.py` and `forms.py` are unchanged, and no migration was
added or edited. A reviewer expecting source-level fixes should read their
absence as "the reference application was already PostgreSQL-clean", not as
"the failures were suppressed" — Task 3's forbidden list (`skip`, `xfail`,
`pytest.skip`, `databases=` narrowing, engine conditionals) appears nowhere in
`tests/`, verified by grep.

Why it came out clean is worth stating, because it is not luck: the only
application model is a thin `AbstractUser` subclass with one `CharField`; the
one custom queryset (`UserViewSet.get_queryset`) filters to a single row by
primary key, so there is no ordering to be unstable; and the suite's assertions
are per-object rather than over ordered collections.

**That makes the new tests the substance of the story, not a formality.** With
no failures to fix, the only durable evidence that the gate is now stricter is
`tests/integration/test_postgres_schema.py`, which asserts the schema is
actually reachable and that `unique` and `NOT NULL` are enforced by the
database rather than by a form. Those two run identically on both backends. The
`max_length` half deliberately does not: it is asserted through model
validation, because sqlite ignores `VARCHAR(n)` entirely (measured — see the
Debug Log). The file's module docstring says so plainly rather than implying a
guarantee sqlite does not give.

**Deliberate scope decision on AC #2.** The AC is written for a suite that
fails on first contact with PostgreSQL. It is satisfied vacuously here, and I
have recorded it as vacuous rather than inventing failures to fix. The
substantive obligation the AC carries — that nothing is skipped or `xfail`ed —
is met and now enforced: the new integration file is skip-free by construction,
and `docs/development.md` states that a CI-only failure is fixed at its source
and never by narrowing the gate.

**One test-contract addition beyond the task text.** Task 5 asks for two
assertions on `test_gate_contract.py`; I added a third,
`test_no_other_job_declares_a_database_service`, which fails if a service is
ever attached to the three-OS `compatibility` job. Task 1 states that
constraint but nothing enforced it, and a service on a matrix job would break
two of its three legs at runtime rather than at review time.

**The `postgres:18` image tag is asserted only by family** (`postgres:`) in the
contract test. `pixi.toml`'s `libpq = ">=18.4,<19"` is what fixes the major
version; pinning it in a second place would give two things to update and one
of them would drift.

**Unverified locally — GitHub Actions cannot run on this machine.** Everything
above tests the *mechanism* (a real PostgreSQL 18 at a `DATABASE_URL`) but not
the *platform*. Specifically unproven until the first real run: that the
`services:` container's health check gates step start as expected; that
`ports: ["5432:5432"]` is reachable at `localhost:5432` from the runner; and
that the job-level `env` is visible to every step of `pixi run ci`. All three
are standard GitHub Actions behaviour and the local run reproduces their effect,
but the first CI run is the confirmation.

**Untouched by design.** `pixi.toml` gains nothing — `psycopg >=3.3,<4` and
`libpq >=18.4,<19` were already declared, so this story adds no dependency and
`[pypi-dependencies]` still holds only the editable self-install. `--reuse-db`
stays in `pyproject.toml` as Task 2 directs; the `--create-db` caveat is now
documented rather than worked around.

### File List

| Path | Change |
| --- | --- |
| `.github/workflows/ci.yml` | `gate` job gains a `postgres:18` `services:` block (health-checked, `ports: ["5432:5432"]`) and a job-level `DATABASE_URL`; the Story 1.1 placeholder comment and two now-stale forward references to Story 1.2 rewritten to the present tense. *(review patch)* the `libpq`-fixes-the-server-version rationale corrected — libpq is the client library and pins nothing server-side; the `compatibility` matrix job gains a `pixi run test-integration` leg so sqlite is still exercised somewhere in CI. |
| `docs/development.md` | New "The parity gap between local runs and the gate" subsection under Database — records R-5 by name, states that a CI-only failure is expected behaviour of the trade and is fixed at source, gives the local `docker run` reproduction, and documents the `--create-db` caveat around `--reuse-db`. "The gate" section updated to say the gate runs against PostgreSQL and why the three-OS job cannot. *(review patch)* reproduction recipe made runnable and pixi-only (concrete URL, `--rm`, host port 55432, `pixi run test-cov --create-db`); the matrix-job description corrected to name its new integration leg. |
| `tests/unit/test_gate_contract.py` | Three new tests: the gate declares a `postgres:`-family service; the gate sets `DATABASE_URL` at job level; no job other than the gate declares any service. *(review patch)* three more — the `DATABASE_URL` *value* must name the declared service, the service must be `pg_isready`-health-gated and publish 5432, and no other job may set `DATABASE_URL`; the no-other-service check narrowed to database services so a future Redis is not blocked. |
| `tests/unit/test_database_selection.py` | NEW — 7 tests over the three-branch selection in `base.py`: `DATABASE_URL` wins and is not sqlite, `POSTGRES_*` selects postgresql, neither falls back to sqlite, `DATABASE_URL` beats `POSTGRES_DB`, and `ATOMIC_REQUESTS` holds on every branch (asserted across all configured aliases, per AD-9). Uses the evict-and-reimport pattern from `tests/unit/test_settings.py`. *(review patch)* two more tests — half-configured `POSTGRES_*` refuses rather than degrading, and an empty `DATABASE_URL` falls back; the fixture now restores the original module and the parent-package attribute; module docstring corrected to stop claiming "no I/O". |
| `tests/integration/test_postgres_schema.py` | NEW — 5 tests, all `@pytest.mark.integration`, skip-free and engine-blind: migrated schema reachable, boundary-length value round-trips whole, over-length value rejected, duplicate `username` rejected by the database, `NULL` in a `NOT NULL` column rejected. Failing writes are wrapped in an inner `transaction.atomic()` so the transactional `db` fixture leaves the database as found. *(review patch)* two more — the live connection must be the backend `DATABASE_URL` names (the only test that can tell a PostgreSQL gate from a sqlite one), and the column's declared width is read out of the schema by introspection; `NAME_MAX_LENGTH` guarded against `None`. |

**Unchanged, verified only:** `src/config/settings/base.py` (all three branches
and the fallback comment intact), `src/config/settings/production.py:26-28`
(the sqlite refusal still raises), `src/django_service/users/models.py`,
`.../api/views.py`, `.../forms.py`, `pixi.toml`, `pyproject.toml`, and every
migration directory.

## Change Log

| Date | Change |
| --- | --- |
| 2026-08-15 | Declared a health-checked `postgres:18` service and a job-level `DATABASE_URL` on the `gate` job, so `pixi run ci` runs against PostgreSQL rather than the sqlite substitution (Story 1.2, FR-32). |
| 2026-08-15 | Ran the full suite against a real PostgreSQL 18.4 before any edit: zero sqlite-permissive failures, so no source or migration change was needed. Recorded as a vacuous AC #2 rather than manufactured. |
| 2026-08-15 | Added `tests/unit/test_database_selection.py` and `tests/integration/test_postgres_schema.py`, and extended `tests/unit/test_gate_contract.py` with the service, `DATABASE_URL` and no-service-on-the-matrix assertions. |
| 2026-08-15 | Recorded the sqlite/PostgreSQL parity gap in `docs/development.md` as risk R-5, with the local reproduction recipe and the `--reuse-db` / `--create-db` caveat. |
| 2026-08-15 | Applied 11 review patches, all in tests, comments and docs — no source or workflow behaviour changed beyond one added sqlite integration leg. The theme all three reviewers converged on: the story's mechanism could be silently reverted with a green suite, because nothing asserted the *value* of `DATABASE_URL` or that the live connection was the backend it names. |
| 2026-08-15 | Follow-up review pass: 11 more patches. The one that mattered — `internal_size` is `None` for `varchar` on PostgreSQL too, so the story's only schema-reading assertion could not fail on any backend; switched to `display_size` and mutation-verified. Also pinned the URL's host and port (a `55432:5432` port edit had passed every check while breaking the gate), scoped the service health check to TCP, and asserted the sqlite integration leg that nothing was holding in place. No source file touched; one real CI behaviour change, the health command. |

## Review Triage Log

### 2026-08-15 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 11: (high 2, medium 7, low 2)
- defer: 2: (high 0, medium 2, low 0)
- reject: 5: (high 0, medium 0, low 5)
- addressed_findings:
  - `[high]` `[patch]` The gate contract asserted only that the `DATABASE_URL` *key* existed, so `DATABASE_URL: ""` or a sqlite URL would revert the whole gate to the substitution with every test still green — `base.py:57` branches on truthiness. Added `test_the_database_url_names_the_declared_postgresql_service`, pinning the URL's scheme and the service's own `POSTGRES_USER`/`PASSWORD`/`DB`. Mutation-verified: emptying the URL now fails the suite.
  - `[high]` `[patch]` Nothing at runtime observed which backend the gate ran on — all five schema tests pass identically on sqlite, so the suite could not distinguish a PostgreSQL gate from a sqlite one. Added `test_the_connection_is_the_backend_database_url_names`, deriving the expected vendor from the declared environment and asserting it unconditionally. Not the engine conditional AC #2 forbids: nothing is skipped or tolerated, and both legs assert.
  - `[medium]` `[patch]` The service's `pg_isready` health check and `5432` port mapping were unasserted; removing either leaves a green suite and an intermittently connection-refused gate. Added `test_the_postgresql_service_is_health_gated_and_reachable`. Both mutations verified to fail.
  - `[medium]` `[patch]` `test_no_other_job_declares_a_database_service` failed on *any* service on *any* job, so a future Redis for Celery would trip a check whose Linux-runner rationale does not cover it. Narrowed to database services, and paired with a new `test_no_other_job_points_itself_at_a_database` for the other half of the same mistake.
  - `[medium]` `[patch]` After the gate moved to PostgreSQL, no CI job opened a sqlite connection at all — the unit tests never touch a database — leaving AC #4 asserted as configuration only. The `compatibility` matrix job now also runs `pixi run test-integration` with no `DATABASE_URL`.
  - `[medium]` `[patch]` `test_a_value_over_the_declared_max_length_is_rejected` asserted through `full_clean()` and never reached the database, and its `pytest.raises` was over-determined — the unsaved user's blank `password` also fails validation, so the raise proved nothing. Assertion message now names the fields, and a new `test_the_column_is_declared_at_the_max_length_the_model_states` reads the width out of the schema via introspection (`internal_size`), which pins it exactly on PostgreSQL and admits `None` on sqlite.
  - `[medium]` `[patch]` `test_database_selection.py`'s docstring claimed "No I/O, no database connection", but importing the settings module resolves `BASE_DIR`, may read a `.env`, and calls the process-global `configure_structlog()`. Docstring corrected to claim only what is true.
  - `[medium]` `[patch]` The evict-and-reimport fixture popped `config.settings.base` without restoring it, leaving the parent package holding a module built under a monkeypatched environment. Fixture now restores both the `sys.modules` entry and the package attribute in a `finally`.
  - `[medium]` `[patch]` `test_postgres_variables_select_postgresql`'s docstring misdescribed the branch — `base.py:59` keys on `POSTGRES_DB` alone, so half-configured credentials raise `ImproperlyConfigured` at import rather than falling back. Docstring corrected and the refusal pinned by a new test; the empty-`DATABASE_URL` fallback is now pinned too.
  - `[low]` `[patch]` The `postgres:`-family assertion and the `ci.yml` comment both claimed the `libpq` pin fixes the server major version. It does not — libpq is the *client* library and an 18 client connects to an older server without complaint. Both rationales corrected to say the tag and the pin are kept aligned by hand.
  - `[low]` `[patch]` The `docs/development.md` reproduction recipe could not be pasted (a literal `DATABASE_URL=...`), invoked `pytest` directly against the project's pixi-only rule, started a container with no `--rm` or removal step, and bound host port 5432 — the port the dev's own debug log records as already taken. Rewritten as a runnable sequence on port 55432 using `pixi run test-cov --create-db`, which was verified to accept the passthrough flag.

### 2026-08-15 — Review pass (follow-up)

- intent_gap: 0
- bad_spec: 0
- patch: 11: (high 1, medium 5, low 5)
- defer: 0
- reject: 16
- addressed_findings:
  - `[high]` `[patch]` `test_the_column_is_declared_at_the_max_length_the_model_states` — the story's one assertion that reads the schema rather than the model — **could not fail on either backend.** It read `internal_size`, which is the *fixed-width* byte size and is `None` for every variable-length type on PostgreSQL as well as sqlite; `assert reported in (None, NAME_MAX_LENGTH)` was therefore unconditionally true, and the docstring's claim that "PostgreSQL reports the `varchar(n)` width as an integer, which pins it exactly" was false. Verified at source (`psycopg/_column.py:83-86` returns `None` when `PQfsize` is negative; `django/db/backends/postgresql/introspection.py:118` passes it straight through) and empirically on a real `postgres:18`. Switched to `display_size`, which both backends report as `255`, and the assertion is now exact and unconditional. Mutation-verified: expecting a wrong width now fails on PostgreSQL *and* on sqlite. A `next()` with no default was also replaced with a sentinel so a renamed column reports a readable failure instead of `StopIteration`.
  - `[medium]` `[patch]` The gate contract pinned the `DATABASE_URL`'s credentials but not its **host or port**, so `ports: ["55432:5432"]` — which satisfies the `endswith(":5432")` check — passed every assertion while leaving the gate connection-refused. The URL is now parsed with `urlsplit` and its host and port are compared against the host side of the service's own port mapping. Parsing also removes two side defects of the previous substring containment: `POSTGRES_DB: user` would have "matched" `gateuser`, and a legitimate `?sslmode=` query parameter would have broken the `endswith` on the database name. Mutation-verified.
  - `[medium]` `[patch]` The service's health check was a bare `pg_isready`, which probes the **local unix socket**. The postgres image's entrypoint runs initdb against a temporary server started with `listen_addresses=''` (confirmed at `docker-entrypoint.sh:297` inside the image), so the bare check reports ready during that window while TCP — the only thing the runner can reach — is still closed. The health gate could therefore green-light a step that then fails connection-refused for reasons unrelated to the change. Now `pg_isready -h localhost -U gateuser -d gatedb`, verified locally to reach `healthy` in ~3s, and asserted by the contract test. Mutation-verified.
  - `[medium]` `[patch]` The `pixi run test-integration` leg added to the `compatibility` job by the previous pass — the only place in CI that opens a sqlite connection at all — had **nothing asserting it**, while its sibling checks guarded loudly against a database appearing where it should not. Deleting it silently reinstated exactly the hole it was added to close. Added `test_some_job_still_exercises_the_sqlite_substitution`. Mutation-verified.
  - `[medium]` `[patch]` `test_the_connection_is_the_backend_database_url_names` derived its expected vendor from `DATABASE_URL` alone, so a developer configured through the `POSTGRES_DB` branch of `base.py:59` — genuinely on PostgreSQL — would have had the test fail them for being correctly configured. Both PostgreSQL-selecting branches are now read.
  - `[medium]` `[patch]` `_postgres_service()` returns `{}` when no service matches, and the caller then indexed `service_env["POSTGRES_USER"]` — so removing the service, retagging the image, or relying on the image's default credentials produced a bare `KeyError` instead of the assertion messages written beside it. The missing keys are now reported by name.
  - `[low]` `[patch]` `test_every_branch_sets_atomic_requests` indexed `config["ATOMIC_REQUESTS"]` while iterating every alias, but `base.py:80` sets it on `default` only — so AD-9's forecast second database would have raised `KeyError` from inside a generator expression rather than reporting which database was missing the setting. Reads with `.get()` and names the offenders.
  - `[low]` `[patch]` Both the `ci.yml` comment and the contract test's docstring justified job-level `env:` with "every step of `pixi run ci` sees it" / "every one of them has to see the same database" — false, since `precommit`, `build`, `typecheck` and `lint` open no database. Job level is still right, for the reason now stated: no step can be reordered or added into a position where the database-touching ones stop seeing it.
  - `[low]` `[patch]` `test_no_other_job_declares_a_database_service` matched only images literally beginning `postgres:`, so `mysql:8`, `mariadb`, an untagged `postgres`, or a registry-qualified `ghcr.io/.../postgres:18` all evaded a check whose Linux-runner rationale covers them identically. Now matched on the image's repository segment across four database families. Its sibling `test_no_other_job_points_itself_at_a_database` inspected only job-level `env`, leaving step-level `env:` as the obvious way in; both are now scanned.
  - `[low]` `[patch]` `POSTGRES_DB=""` is the exact sibling of the empty-`DATABASE_URL` case already pinned — `base.py:59` is a truthiness branch too — and was uncovered. Added `test_an_empty_postgres_db_falls_back_rather_than_half_selecting`.
  - `[low]` `[patch]` The `docs/development.md` reproduction recipe spun forever if the container failed to start (`until docker exec … pg_isready` retries a dead container indefinitely) and left port 55432 held whenever `pixi run ci` failed — which is the only case the recipe exists for, since a trailing `docker stop` does not run under `set -e`. Now a bounded loop with a `trap … EXIT` cleanup, a `docker rm -f` guard against a stale name, and the same TCP-scoped `pg_isready` the gate uses.

## Auto Run Result

Status: done

### Summary of implemented change

CI's `gate` job declares a health-checked `postgres:18` service and sets
`DATABASE_URL` at job level, so all five steps of `pixi run ci` execute against
PostgreSQL rather than the sqlite substitution (FR-32, AD-18). No settings
change is involved — `src/config/settings/base.py:57` already reads
`DATABASE_URL` first, so the URL is the whole mechanism, and that file remains
byte-for-byte unchanged. The suite went green against real PostgreSQL 18.4 on
the first run, so AC #2 is satisfied vacuously: no sqlite-permissive failure
existed to fix, and nothing under `src/` is touched by this story. The sqlite
substitution is preserved for local development and recorded as risk R-5.

This follow-up review pass changed no behaviour except one: the service's health
command now probes TCP rather than the local unix socket. Everything else went
into the tests that hold the story's mechanism in place — the previous pass had
established that the mechanism could be reverted with a green suite, and this
pass found the same class of hole one level deeper, in an assertion that could
not fail at all.

### Files changed

| Path | One-line description |
| --- | --- |
| `.github/workflows/ci.yml` | PostgreSQL service and job-level `DATABASE_URL` on the gate; a sqlite integration leg on the three-OS matrix; health check scoped to TCP (`pg_isready -h localhost -U … -d …`) because the image's init phase answers the bare check over a socket while TCP is still closed. |
| `docs/development.md` | Records the R-5 parity gap, the `--reuse-db`/`--create-db` caveat, and a reproduction recipe that is now bounded, `trap`-cleaned and safe to paste when the gate fails. |
| `tests/unit/test_gate_contract.py` | Nine gate-contract assertions: the service exists, is TCP-health-gated and publishes 5432; the `DATABASE_URL` value is parsed and matched against the service's credentials, host and published port; no other job declares a database service or points itself at one; and some job still exercises sqlite. |
| `tests/unit/test_database_selection.py` | Ten tests over the three-branch selection in `base.py`, including both truthiness edges (`DATABASE_URL=""` and `POSTGRES_DB=""`), the half-configured refusal, branch precedence, and `ATOMIC_REQUESTS` across every configured alias. |
| `tests/integration/test_postgres_schema.py` | Seven skip-free, engine-blind tests: the live connection is the backend the environment names, the migrated schema is reachable, the column's declared width is read out of the schema, and boundary/over-length/duplicate/NULL writes behave as declared. |

**Unchanged, verified only:** everything under `src/`, `pixi.toml`,
`pyproject.toml`, and every migration directory.

### Review findings breakdown

Three reviewers (adversarial, edge-case, verification-gap) ran in parallel
without prior context. After deduplication and severity assignment:

- **11 patches applied** — 1 high, 5 medium, 5 low. Detailed in the Review
  Triage Log above.
- **0 deferred.** Two candidates were already in
  `deferred-work.md` from the previous pass (mypy's `src/`-only scope; the
  process-global `configure_structlog()` re-run on settings re-import), so
  re-recording them would have been noise.
- **16 rejected.** The substantive ones and why: *AC #3 has no permanent test*
  — correct, but unfixable by construction, since a test that ships a schema
  PostgreSQL rejects would fail the gate on every run; it was demonstrated by
  the throwaway probe in the Debug Log instead. *The `postgres:18` tag should
  be digest-pinned, and drift from `libpq` should be tested* — the previous
  pass settled this deliberately, and re-litigating it would give two places
  to update. *The sqlite integration leg is unrequested scope and creates a
  CI-only step* — it is neither: the previous pass added it for AC #4, and
  `pixi run test-integration` is a real task any developer can run. The
  remainder were cosmetic (comment volume, hardcoded line numbers in comments,
  a duplicated constant across the unit/integration boundary).

### Verification performed

A real PostgreSQL 18 was used throughout, on host port 55432 because 5432 is
taken locally by an unrelated container.

1. `pixi run test` — 91 passed.
2. `pixi run test-integration` against PostgreSQL — 51 passed.
3. **`pixi run ci` against PostgreSQL — exit 0**, 142 passed, 92.31% coverage.
   (The first attempt tripped the pre-commit auto-fix trap: `ruff-format` and
   `end-of-file-fixer` modified files, so the run was repeated after re-staging.)
4. **Mutation checks, four of them, each reverted after measuring:**
   - width assertion expecting a wrong value → fails on PostgreSQL **and** on
     sqlite (the point: it previously failed on neither);
   - `ports: ["55432:5432"]` → `test_the_database_url_names_…` fails;
   - health command reverted to bare `pg_isready` → `test_…health_gated…` fails;
   - the sqlite integration leg deleted → `test_some_job_still_exercises_…` fails.
5. **Source-level confirmation of the high finding**, independent of the running
   database: `psycopg/_column.py:83-86` returns `None` from `internal_size`
   whenever `PQfsize` is negative, which it is for every varlena type;
   `django/db/backends/postgresql/introspection.py:118` passes that value
   through unchanged as `FieldInfo.internal_size`.
6. The health-check fix was validated against a real container: `pg_isready -h
   localhost -U gateuser -d gatedb` reaches `healthy` in ~3s, and the image's
   `docker-entrypoint.sh:297` was read to confirm the init server runs with
   `listen_addresses=''`.
7. All probe containers removed; `docker ps -a` shows none remaining.

### Residual risks

- **The platform is still unproven.** Everything above tests the *mechanism*
  against a real PostgreSQL at a `DATABASE_URL`, not GitHub Actions itself.
  Unconfirmed until the first real run: that the service container's health
  check gates step start, that `ports: ["5432:5432"]` is reachable at
  `localhost:5432` from the runner, and that job-level `env` reaches every
  step. The health-command change is the one edit in this pass that alters CI
  runtime behaviour and cannot be verified locally; it was chosen because the
  bare form is measurably racy, and the replacement was confirmed to reach
  `healthy` against the same image.
- **AC #3 has no standing test and cannot have one.** The gate failing on a
  PostgreSQL-rejected schema was demonstrated by a temporary probe migration
  and recorded in the Debug Log; nothing permanent asserts it.
- **The `postgres:18` tag and `libpq = ">=18.4,<19"` are kept aligned by hand.**
  `libpq` is the client library and pins no server version, so no test can
  catch drift between them.
- **`ATOMIC_REQUESTS` is set on `default` only** (`base.py:80`). AD-9 forecasts
  a second database; the test now reports which alias is missing the setting
  rather than raising, but the source behaviour is unchanged and out of scope
  for a database story.
