# Story 3.2: The database, cache and task substitutions hold locally

Status: ready-for-dev

## Story

As a developer working on a generated component,
I want the component to run with no database, cache or broker,
so that changing a line of business logic does not require standing up four services first.

## Acceptance Criteria

**Traceability:** FR-18, FR-22 · AD-9 · SC-4

1. **Given** neither `DATABASE_URL` nor `POSTGRES_DB` is set
   **When** the component starts
   **Then** sqlite is selected
   **And** the ORM, migrations and the full suite are preserved

2. **Given** no cache service is running
   **When** the component starts
   **Then** an in-process cache backend is configured
   **And** the cache API is preserved at every call site

3. **Given** no broker is running
   **When** a task is invoked
   **Then** execution is eager and propagating
   **And** task bodies are invoked synchronously

4. **Given** every valid combination
   **When** it runs locally
   **Then** it runs with no broker, including the combinations that selected background task processing
   **And** the documentation states that the broker constraint is a statement about deployment only, so it does not read as absolute

## Tasks / Subtasks

- [ ] Task 1: Make the database substitution a named, reusable selection rather than an inline `if` chain (AC: #1)
  - [ ] In `src/config/settings/base.py`, the selection currently sits inline at lines 57-78: `DATABASE_URL` → `env.db(...)`; else `POSTGRES_DB` → an explicit PostgreSQL dict; else the sqlite fallback at `str(BASE_DIR / "db.sqlite3")`. Keep that precedence order exactly.
  - [ ] Extract the sqlite branch into a module-level helper `def _sqlite_alias(base_dir: Path, alias: str = "default") -> dict[str, Any]` in `base.py`, returning `{"ENGINE": "django.db.backends.sqlite3", "NAME": str(base_dir / f"db.{alias}.sqlite3" if alias != "default" else base_dir / "db.sqlite3")}`. The `alias` parameter is what lets AD-9's contributed-database substitution extend this in Epic 9 without a second mechanism.
  - [ ] Add `def apply_local_database_substitution(databases: dict[str, Any], base_dir: Path) -> None` in `base.py`: for every alias in `databases` whose configuration is missing or empty, install `_sqlite_alias(base_dir, alias)`. Call it after the existing selection so the `default` alias keeps its current behaviour and any alias a future contributed database adds is substituted by the same code path.
  - [ ] Preserve `DATABASES["default"]["ATOMIC_REQUESTS"] = True` (`base.py:80`) and `DEFAULT_AUTO_FIELD` (`base.py:82`) exactly as they are.
  - [ ] Do **not** move the substitution into `local.py`. It must hold for any settings module that loads with no database configured, because FR-12 makes the refusal contract evaluate "independently of which settings module loaded" and `production.py:26-28` is the guard that makes the sqlite fallback safe.

- [ ] Task 2: Confirm and pin the in-process cache substitution (AC: #2)
  - [ ] `src/config/settings/local.py:21-26` already sets `CACHES["default"]` to `django.core.cache.backends.locmem.LocMemCache`. Keep the backend; add a comment recording that this is one of FR-18's five substitutions and that the cache API is preserved at every call site — no call site may branch on which backend is active.
  - [ ] Add the same `CACHES` block to `src/config/settings/test.py` explicitly rather than inheriting it from `base.py`'s absence of a `CACHES` key. Relying on Django's implicit default makes the substitution invisible to the assertion in Task 5 and to a reader.
  - [ ] Do **not** add a `CACHES` key to `base.py` — `production.py:33-44` sets the Redis backend and `base.py` must not pre-empt it.

- [ ] Task 3: Confirm and pin the eager task substitution (AC: #3, #4)
  - [ ] `src/config/settings/local.py:78-80` already sets `CELERY_TASK_ALWAYS_EAGER = True` and `CELERY_TASK_EAGER_PROPAGATES = True`. Keep both. Eager alone swallows exceptions into the result object; propagating is what makes a failing task body fail the caller.
  - [ ] Add the same two settings to `src/config/settings/test.py`, for the same visibility reason as Task 2.
  - [ ] Add a comment recording that this holds in **all twelve** combinations locally, including the four that select background task processing, and that it is a conditional refusal (FR-14) only in a deployed component where background task processing was selected.

- [ ] Task 4: Document the three substitutions and the scope of the broker constraint (AC: #1, #2, #3, #4)
  - [ ] `docs/development.md` already carries a `## Running with no external services` section with a three-row table (PostgreSQL → sqlite, Redis cache → `LocMemCache`, Celery and its broker → eager in-process) and an honest paragraph on what each stand-in trades away. Extend rather than rewrite it.
  - [ ] Add an explicit sentence: the broker constraint is a statement about **deployment** only — every valid combination runs locally with no broker, including the combinations that selected background task processing — so the constraint does not read as absolute.
  - [ ] Extend the trade-off paragraph with R-5 in its own terms: sqlite accepts schemas PostgreSQL rejects; eager execution never exercises delivery or retries; local success is not evidence that a change works deployed.
  - [ ] Note that filesystem-backed object storage is the fifth substitution and arrives with the storage feature in Epic 7; do not claim it here.

- [ ] Task 5: Tests (AC: #1, #2, #3, #4)
  - [ ] Extend `tests/unit/test_settings.py` (UPDATE). It already carries the `_evict_settings_modules` fixture (`:23-30`) that pops `config.settings.base`/`local`/`production` from `sys.modules`, and a `no_database_env` fixture (`:33-37`) that deletes `DATABASE_URL` and `POSTGRES_DB`. Reuse both — do not author a second eviction mechanism.
  - [ ] `test_sqlite_is_selected_when_no_database_is_configured`: with `no_database_env`, import `config.settings.base` fresh and assert `DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"`.
  - [ ] `test_database_url_takes_precedence_over_sqlite` and `test_postgres_env_takes_precedence_over_sqlite`: assert the fallback does not shadow an explicitly configured database.
  - [ ] `test_local_substitution_fills_an_unconfigured_extra_alias`: call `apply_local_database_substitution` directly with a dict carrying an empty second alias and assert it receives a sqlite configuration. This is the AD-9 hook; it is unit-testable without a contributed database existing.
  - [ ] `test_local_configures_an_in_process_cache`: import `config.settings.local` fresh and assert the `default` cache backend is `django.core.cache.backends.locmem.LocMemCache`.
  - [ ] `test_local_executes_tasks_eagerly_and_propagates`: assert both `CELERY_TASK_ALWAYS_EAGER` and `CELERY_TASK_EAGER_PROPAGATES` are `True`.
  - [ ] Add `tests/integration/test_local_substitutions.py` (NEW), every test marked `@pytest.mark.integration`: apply a migration-backed assertion that the ORM works against the substituted database (create and read a `User` via the existing `user` fixture in `tests/conftest.py:18-20`), that `django.core.cache.cache.set`/`get` round-trips through the in-process backend, and that calling an existing task from `src/django_service/users/tasks.py` executes its body synchronously and propagates a raised exception to the caller. Leave no state behind — use the `db` fixture's transaction rollback.

## Dev Notes

### Architecture Constraints

**FR-18 — five substitutions, four of them here.** "Every valid combination starts, serves, and authenticates a persona on a machine with no database, cache, broker, or identity provider running." Its testable consequences that belong to this story: sqlite selected when neither `DATABASE_URL` nor `POSTGRES_DB` is set, preserving the ORM, migrations and the full suite; an in-process cache backend configured locally, preserving the cache API at every call site; task execution eager and propagating locally, preserving task bodies invoked synchronously.

**The fifth substitution is not this story.** Filesystem-backed object storage is delivered in Epic 7's object-storage story, "because the storage feature is greenfield and does not exist until then. Its other four substitutions are Epic 3." Do not add a `STORAGES` local override, do not touch `django-storages`, and do not claim the fifth substitution in the documentation. The fourth substitution in Epic 3's set is the local personas, which are Stories 3.3 and 3.4 — not this story either.

**FR-22 — the broker constraint is a statement about deployment only.** "Locally, all twelve valid combinations run with no broker." Testable consequences: combinations that selected background task processing execute tasks eagerly with no broker present locally, and "documentation states the constraint's scope explicitly, so it does not read as absolute."

**AD-9 — A contributed database is a chain, not a setting.** Binding rule: "The stage-2 unapplied-migrations refusal and the sqlite refusal both iterate every configured database — which is only possible because stage 1 runs *after* composition (AD-26). **Local substitution is applied automatically by the base, so FR-18 stays true by construction.**" Task 1's `apply_local_database_substitution` is that automatic application. Writing it as a single hardcoded `default` branch is what forces Epic 9 to invent a second mechanism — *Prevents:* "six enforcement points each being answered differently by six epics."

**AD-24 — no sub-file removal by any mechanism other than declared markers.** The Celery block in `src/config/settings/base.py` is one of the three known region-bearing `core` paths. When touching that file: **never** introduce a conditional import, a settings-module inheritance trick, or `try/except ImportError` to make Celery configuration optional. The markers are declared in Epic 7; this story adds no markers and removes no code.

**CG-4 — Do not substitute a capability that could run locally as deployed.** Each substitution "widens the parity gap the product already trades knowingly, and each must be guarded by a refusal." The three guards already exist or are scheduled: the sqlite refusal (built today at `src/config/settings/production.py:26-28`, generalized to all aliases in Epic 4), the in-process-cache conditional refusal and the eager-execution conditional refusal (FR-14, Epic 4). Do not add a fourth substitution here.

**R-5 — Local development proves less than running suggests.** Carried verbatim into the documentation: "sqlite accepts schemas PostgreSQL rejects, eager execution never exercises delivery or retries, synthetic claims never exercise JWKS retrieval or rotation." The existing paragraph in `docs/development.md` already says something close to this; strengthen it, do not soften it.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/settings/base.py` | UPDATE | Extract `_sqlite_alias` and add `apply_local_database_substitution`; call it after the existing `DATABASE_URL` / `POSTGRES_DB` / sqlite selection. |
| `src/config/settings/local.py` | UPDATE | Comment the `CACHES` and Celery-eager blocks as declared FR-18 substitutions. No behavioural change. |
| `src/config/settings/test.py` | UPDATE | Add the explicit `CACHES` in-process block and the two Celery eager settings so the substitutions are visible rather than inherited. |
| `docs/development.md` | UPDATE | Extend `## Running with no external services` with the FR-22 scope statement, the R-5 trade-offs, and the note that the fifth substitution arrives in Epic 7. |
| `tests/unit/test_settings.py` | UPDATE | Add the five substitution assertions listed in Task 5, reusing the existing fixtures. |
| `tests/integration/test_local_substitutions.py` | NEW | ORM / cache / eager-task round-trips against the substituted backends, all `@pytest.mark.integration`. |

**`src/config/settings/base.py` today (verified).** 383 lines. Database selection at `:53-82`: `if os.getenv("DATABASE_URL")` → `env.db("DATABASE_URL")`; `elif os.getenv("POSTGRES_DB")` → explicit PostgreSQL dict with `POSTGRES_USER`/`POSTGRES_PASSWORD` and defaulted `POSTGRES_HOST="postgres"`, `POSTGRES_PORT="5432"`; `else` → sqlite at `BASE_DIR / "db.sqlite3"` with a comment naming `production.py` as the guard. Then `DATABASES["default"]["ATOMIC_REQUESTS"] = True` and `DEFAULT_AUTO_FIELD`. `BASE_DIR` is defined at `:15`, `env = environ.Env()` at `:19`. The Celery block runs `:296-335` — the spine cites it as `:296-313`, which is where the block *starts* but not where it ends; see Project Structure Notes. **Must be preserved:** the settings-module import of `build_logging_config` / `configure_structlog` at `:11-12` and the `configure_structlog()` call at `:287`; `MIGRATION_MODULES` at `:128`; the `INSTALLED_APPS` composition at `:123`.

**`src/config/settings/local.py` today (verified).** 82 lines. `CACHES` with `LocMemCache` at `:21-26`. `CELERY_TASK_ALWAYS_EAGER = True` at `:78`, `CELERY_TASK_EAGER_PROPAGATES = True` at `:80`. **Must be preserved:** the `DEBUG_APPS` gate at `:51-74`, which keeps `debug_toolbar` and `django_extensions` out of the runtime environment where those packages are absent — it is the reason `pixi run serve` works from the `default` environment.

**`src/config/settings/test.py` today (verified).** 46 lines. Sets `LOGGING` to console/WARNING, `SECRET_KEY`, `TEST_RUNNER`, `PASSWORD_HASHERS`, locmem email, `TEMPLATES[0]["OPTIONS"]["debug"] = True` (`:39` — required by `django_coverage_plugin` for template coverage; do not remove it), and `MEDIA_URL`. It sets no `CACHES` and no Celery settings today.

**`src/config/settings/production.py` today (verified).** The sqlite refusal is at `:26-28` — `if DATABASES["default"]["ENGINE"].endswith("sqlite3"): raise ImproperlyConfigured(...)`. It inspects only the `default` alias. Generalizing it to iterate every configured database is **Epic 4's** work (FR-13, AD-9); do not move it here, and do not change its behaviour in this story.

### Testing Requirements

- Unit assertions go in `tests/unit/test_settings.py`; integration round-trips go in `tests/integration/test_local_substitutions.py` with `@pytest.mark.integration` on **every** test in the file.
- `tests/unit/test_settings.py` documents its own reload contract in its module docstring: each test imports a settings module fresh so module-level environment reads are re-evaluated, and `config.settings.base` is evicted alongside the target because the `from .base import *` would otherwise reuse the already-imported copy. Follow that contract; do not introduce a competing fixture.
- Unit tests must not touch the database — `tests/unit/conftest.py` states the rule. The `apply_local_database_substitution` test operates on a plain dict, not on a connection.
- Integration tests must leave state as found: use the `db` fixture (transaction rollback) and the `user` fixture from `tests/conftest.py`.
- Coverage floor: ninety percent including templates (AD-20), `COVERAGE_CORE=ctrace` in force, `--cov-fail-under=90` via `pixi run test-cov`. `pixi run ci` must exit 0.
- Test disposition: these tests cover `core` settings surface, so they live under `tests/` mirroring `src/` and carry the `core` disposition.
- Run with `pixi run test` and `pixi run test-integration`; never bare `pytest`.

#### Project Structure Notes

Aligned with the Structural Seed: `src/config/settings/` is where "base + local + production + test; composition, then stage 1 last (AD-8, AD-26)" lives, and this story touches only that directory plus tests and docs.

**Recorded drift.** AD-24 cites the Celery feature-owned region in `src/config/settings/base.py` as `:296-313`. In the current file the Celery block begins at `:296` (`# Celery`) and runs to `:336` (`CELERY_WORKER_HIJACK_ROOT_LOGGER = False`) — the cited range stops at `CELERY_RESULT_BACKEND_ALWAYS_RETRY` and excludes eight further `CELERY_*` settings. This story does not add or move markers (that is Epic 7), but it must not narrow the block either: keep every `CELERY_*` setting contiguous inside that one block so the eventual marker pair can wrap it whole.

### References

- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-18] — the five substitutions and their testable consequences.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-22] — the broker constraint's scope and the documentation consequence.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#CG-4] — every substitution must be guarded by a refusal.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-9] — local substitution applied automatically by the base.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24] — no conditional imports, no settings-module inheritance, no `try/except ImportError`; the `:296-313` region citation.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-5.
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.2]
- [Source: _bmad-output/planning-artifacts/epics.md:223] — FR-18's fifth substitution is Epic 7's, not this story's.
- [Source: src/config/settings/base.py:53-82] · [Source: src/config/settings/local.py:21-26,78-80] · [Source: src/config/settings/production.py:26-28] · [Source: src/config/settings/test.py:39]
- [Source: tests/unit/test_settings.py:1-43] — the eviction and `no_database_env` fixtures.
- [Source: docs/development.md#Running with no external services] — the existing substitution table to extend.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
