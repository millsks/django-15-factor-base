# Story 1.2: The gate runs against PostgreSQL

Status: ready-for-dev

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

- [ ] Task 1 — Declare the PostgreSQL service on the gate job (AC: #1)
  - [ ] In `.github/workflows/ci.yml`, add a `services:` block to the `gate` job created by Story 1.1. Use `postgres:18` to match the `libpq = ">=18.4,<19"` pin at `pixi.toml:16`. Declare `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB`, `ports: ["5432:5432"]`, and health options `--health-cmd pg_isready --health-interval 10s --health-timeout 5s --health-retries 5`.
  - [ ] Set `DATABASE_URL` on the gate job's `env:` (job level, not step level, so every step of `pixi run ci` sees it). `src/config/settings/base.py:57-58` reads `DATABASE_URL` first and hands it to `env.db(...)`, so the URL is the whole mechanism — no settings change is needed to select PostgreSQL. Format: `postgres://<user>:<password>@localhost:5432/<db>`.
  - [ ] The service block runs only on Linux runners. Keep it on the ubuntu-only `gate` job; do not attach it to the three-OS compatibility matrix job, which continues on the sqlite substitution.
  - [ ] Add a comment beside the service block stating why it exists: FR-32 requires the gate to run against the database the immovable core names, and no workflow declared one before this story.

- [ ] Task 2 — Verify PostgreSQL selection actually takes effect in the test settings (AC: #1, #3)
  - [ ] `pyproject.toml:143` pins `--ds=config.settings.test`. `src/config/settings/test.py` does `from .base import *` and overrides no database setting, so `DATABASE_URL` reaches it unchanged. Confirm this by running the suite locally with `DATABASE_URL` pointed at a PostgreSQL instance before touching anything else.
  - [ ] `pyproject.toml:144` sets `--reuse-db`. Against a service container that is recreated per run, `--reuse-db` is harmless but hides schema drift on repeat local runs. Leave it in place; note in `docs/development.md` that a local PostgreSQL run may need `--create-db` after a migration change.
  - [ ] `src/config/settings/base.py:80` sets `DATABASES["default"]["ATOMIC_REQUESTS"] = True` unconditionally. This is a PostgreSQL-meaningful setting that sqlite tolerates; expect transaction-scoped failures to surface here first.

- [ ] Task 3 — Fix every sqlite-permissive failure at its source (AC: #2, #3)
  - [ ] Run the full suite against PostgreSQL and triage each failure. The expected classes are: unordered `QuerySet` results (sqlite frequently returns insertion order, PostgreSQL does not — fix by adding an explicit `order_by` in the code or by asserting against a set); `max_length`/type-strictness rejections; `CharField` values exceeding declared length; `null` vs empty-string handling; and case-sensitivity differences in `filter(...)` lookups.
  - [ ] Every fix goes in the source that caused it — `src/django_service/users/models.py`, `src/django_service/users/api/views.py`, `src/django_service/users/forms.py`, or the migration that declared the column — not in the test.
  - [ ] Forbidden: `@pytest.mark.skip`, `@pytest.mark.xfail`, `pytest.skip(...)`, `@pytest.mark.django_db(databases=...)` narrowing, or a conditional that branches on the engine inside a test. AC #2 states none is skipped or marked `xfail`.
  - [ ] If a failure is a genuine model or migration defect, fix it with a new migration under `src/django_service/users/migrations/` or `src/django_service/contrib/sites/migrations/`. Do not edit an applied migration in place.

- [ ] Task 4 — Preserve the sqlite substitution for local development (AC: #4)
  - [ ] Do not change the `else` branch at `src/config/settings/base.py:71-78`, which falls back to `django.db.backends.sqlite3` at `BASE_DIR / "db.sqlite3"` when neither `DATABASE_URL` nor `POSTGRES_DB` is set.
  - [ ] Do not change the production refusal at `src/config/settings/production.py:26-28`, which raises `ImproperlyConfigured` when the resolved engine ends with `sqlite3`. That refusal is Epic 4's condition #1 and is already built; this story must leave it exactly as found.
  - [ ] Record the parity gap in `docs/development.md`: local runs use sqlite, the gate uses PostgreSQL, and the divergence is R-5 — a knowingly traded gap, not a defect. State that a failure reproducible only in CI is expected behaviour of this trade and is fixed at its source rather than by narrowing the gate.

- [ ] Task 5 — Tests (AC: #1, #3, #4)
  - [ ] Extend `tests/unit/test_gate_contract.py` (created in Story 1.1): assert the gate job declares a `services` entry whose `image` begins `postgres:`, and that the job-level `env` sets `DATABASE_URL`.
  - [ ] New `tests/unit/test_database_selection.py`: assert the three-branch selection in `src/config/settings/base.py` behaves as declared — with `DATABASE_URL` set the engine is not sqlite; with only `POSTGRES_DB` set the engine is `django.db.backends.postgresql`; with neither set the engine is `django.db.backends.sqlite3`. Exercise this by reloading the settings module under `monkeypatch.setenv`/`delenv`, not by asserting on the already-imported `settings` object.
  - [ ] New `tests/integration/test_postgres_schema.py`, every test marked `@pytest.mark.integration`: assert the migrated schema is reachable and that a write violating a declared `max_length` or `unique` constraint raises rather than truncating. Skip-free — the file runs against whatever database `DATABASE_URL` names, which in the gate is PostgreSQL and locally is sqlite.
  - [ ] Every integration test must leave the database as it found it; rely on `pytest-django`'s transactional `db` fixture rather than committing rows.

## Dev Notes

### Architecture Constraints

- **FR-32:** "Every valid combination passes the full gate against PostgreSQL — no partial pass; CI must declare a PostgreSQL service, which no workflow does today." This story delivers the reference-application half only. Epic 8 Story 8.8 extends it to twelve combinations.
- **AD-18** binds FR-32 and places the PostgreSQL service in the single-invocation gate. The twelve-combination harness is Linux-only; the three-OS matrix stays on the reference application "where it claims something different" — that is, cross-platform importability, not database fidelity.
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

No new directory is created. The Structural Seed's `src/config/settings/` already exists with `base`, `local`, `production`, `test`. `accelerator.toml`, `component.toml` and `tools/materializer/` — which Epic 8's twelve-combination PostgreSQL gate will need — do not exist yet and are out of scope.

Variance: the seed shows stage-1 refusals as "the last statement of every settings module" (AD-26). `src/config/settings/production.py` currently carries an inline ad-hoc sqlite refusal at `:26-28` instead. That is Epic 4's consolidation, not this story's — leave it where it is.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.2]
- [Source: _bmad-output/planning-artifacts/epics.md:98] — FR-32 text.
- [Source: _bmad-output/planning-artifacts/epics.md:220] — Epic 1 begins the PostgreSQL service; Epic 8 extends it.
- [Source: _bmad-output/planning-artifacts/epics.md:316] — refusal condition #1 is "built: `production.py:26-28`".
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-18]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-9]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-5.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
