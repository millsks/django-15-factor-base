---
baseline_revision: ce04aae
review_loop_iteration: 0
status: done
warnings: []
---

# Story 3.2: The database, cache and task substitutions hold locally

Status: done

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

- [x] Task 1: Make the database substitution a named, reusable selection rather than an inline `if` chain (AC: #1)
  - [x] In `src/config/settings/base.py`, the selection currently sits inline at lines 72-93 (re-verified 2026-08-17; the spec's original citation of 53-82 predates Epic 2's claims-contract additions): `DATABASE_URL` → `env.db(...)`; else `POSTGRES_DB` → an explicit PostgreSQL dict; else the sqlite fallback at `str(BASE_DIR / "db.sqlite3")`. Keep that precedence order exactly.
  - [x] Extract the sqlite branch into a module-level helper `def _sqlite_alias(base_dir: Path, alias: str = "default") -> dict[str, Any]` in `base.py`, returning `{"ENGINE": "django.db.backends.sqlite3", "NAME": str(base_dir / f"db.{alias}.sqlite3" if alias != "default" else base_dir / "db.sqlite3")}`. The `alias` parameter is what lets AD-9's contributed-database substitution extend this in Epic 9 without a second mechanism.
  - [x] Add `def apply_local_database_substitution(databases: dict[str, Any], base_dir: Path) -> None` in `base.py`: for every alias in `databases` whose configuration is missing or empty, install `_sqlite_alias(base_dir, alias)`. Call it after the existing selection so the `default` alias keeps its current behaviour and any alias a future contributed database adds is substituted by the same code path.
  - [x] Preserve `DATABASES["default"]["ATOMIC_REQUESTS"] = True` (`base.py:95`) and `DEFAULT_AUTO_FIELD` (`base.py:97`) exactly as they are.
  - [x] Do **not** move the substitution into `local.py`. It must hold for any settings module that loads with no database configured, because FR-12 makes the refusal contract evaluate "independently of which settings module loaded" and `production.py:26-28` is the guard that makes the sqlite fallback safe.

- [x] Task 2: Confirm and pin the in-process cache substitution (AC: #2)
  - [x] `src/config/settings/local.py:21-26` already sets `CACHES["default"]` to `django.core.cache.backends.locmem.LocMemCache`. Keep the backend; add a comment recording that this is one of FR-18's five substitutions and that the cache API is preserved at every call site — no call site may branch on which backend is active.
  - [x] Add the same `CACHES` block to `src/config/settings/test.py` explicitly rather than inheriting it from `base.py`'s absence of a `CACHES` key. Relying on Django's implicit default makes the substitution invisible to the assertion in Task 5 and to a reader.
  - [x] Do **not** add a `CACHES` key to `base.py` — `production.py:33-44` sets the Redis backend and `base.py` must not pre-empt it.

- [x] Task 3: Confirm and pin the eager task substitution (AC: #3, #4)
  - [x] `src/config/settings/local.py:78-80` already sets `CELERY_TASK_ALWAYS_EAGER = True` and `CELERY_TASK_EAGER_PROPAGATES = True`. Keep both. Eager alone swallows exceptions into the result object; propagating is what makes a failing task body fail the caller.
  - [x] Add the same two settings to `src/config/settings/test.py`, for the same visibility reason as Task 2.
  - [x] Add a comment recording that this holds in **all six** combinations locally, including the two that select background task processing, and that it is a conditional refusal (FR-14) only in a deployed component where background task processing was selected.

- [x] Task 4: Document the three substitutions and the scope of the broker constraint (AC: #1, #2, #3, #4)
  - [x] `docs/development.md` already carries a `## Running with no external services` section at `:398-420`: heading, intro paragraph (`:400-403`), a three-row table (`:405-409` — PostgreSQL → sqlite, Redis cache → `LocMemCache`, Celery and its broker → eager in-process), an observability-exception paragraph (`:411-414`, which this spec originally overlooked and which must survive — it is Story 3.6's territory), and a trade-off paragraph (`:416-420`). Extend rather than rewrite it.
  - [x] Add an explicit sentence: the broker constraint is a statement about **deployment** only — every valid combination runs locally with no broker, including the combinations that selected background task processing — so the constraint does not read as absolute.
  - [x] Extend the trade-off paragraph with R-5 in its own terms: sqlite accepts schemas PostgreSQL rejects; eager execution never exercises delivery or retries; local success is not evidence that a change works deployed.
  - [x] Note that filesystem-backed object storage is the fifth substitution and arrives with the storage feature in Epic 7; do not claim it here.

- [x] Task 5: Tests (AC: #1, #2, #3, #4)
  - [x] **Placement, re-verified 2026-08-17.** `tests/unit/test_database_selection.py` (NEW since this spec was written) already owns the three-branch selection contract in depth: `test_database_url_selects_the_named_backend`, `test_postgres_variables_select_postgresql`, `test_no_database_environment_falls_back_to_sqlite`, `test_database_url_wins_over_the_postgres_variables`, the two empty-value fallbacks, the partial-PostgreSQL refusal, and a parametrized `ATOMIC_REQUESTS` check. The three sqlite/precedence tests this task originally enumerated are therefore **already delivered** — do not author duplicates in `test_settings.py`. The database half of this task adds only the alias-substitution tests, and they go in `test_database_selection.py`, which owns that contract and already has the eviction and clean-environment fixtures (`:54-83`).
  - [x] `tests/unit/test_database_selection.py` (UPDATE): `test_local_substitution_fills_an_unconfigured_extra_alias` — call `apply_local_database_substitution` directly with a dict carrying an empty second alias and assert it receives a sqlite configuration whose `NAME` is distinct from the `default` alias's. This is the AD-9 hook; it is unit-testable without a contributed database existing. Add alongside it: a test that a **configured** alias is left untouched (the substitution must not shadow a real database), and a test that the `default` alias's existing behaviour is unchanged by the new call site.
  - [x] `tests/unit/test_settings.py` (UPDATE). It carries the `_evict_settings_modules` fixture (`:42-49`) that pops `config.settings.base`/`local`/`production` from `sys.modules`, and a `no_database_env` fixture (`:52-55`) that deletes `DATABASE_URL` and `POSTGRES_DB`. Reuse both — do not author a second eviction mechanism.
  - [x] `test_local_configures_an_in_process_cache`: import `config.settings.local` fresh and assert the `default` cache backend is `django.core.cache.backends.locmem.LocMemCache`.
  - [x] `test_local_executes_tasks_eagerly_and_propagates`: assert both `CELERY_TASK_ALWAYS_EAGER` and `CELERY_TASK_EAGER_PROPAGATES` are `True`. Propagation is asserted as well as eagerness — eager alone swallows the exception into the result object.
  - [x] Assert the same three substitutions in `config.settings.test`, so Tasks 2 and 3 are pinned rather than merely written. Without this the explicit blocks added to `test.py` are unasserted prose.
  - [x] Add `tests/integration/test_local_substitutions.py` (NEW): the ORM works against the substituted database (create and read a `User` via the existing `user` fixture in `tests/conftest.py:18-20`), `django.core.cache.cache.set`/`get` round-trips through the in-process backend, and a task executes its body synchronously and propagates a raised exception to the caller. Leave no state behind — use the `db` fixture's transaction rollback.
  - [x] **Marker mechanism, re-verified 2026-08-17.** `tests/integration/conftest.py:12-19` applies `pytest.mark.integration` to every item collected under `tests/integration/`, so a per-test marker is redundant. Declare a file-level `pytestmark` anyway, matching `test_postgres_schema.py:36` — it is what a reader sees first, and it keeps the file correct if it is ever moved.
  - [x] **No existing task raises.** `src/django_service/users/tasks.py` holds exactly one task, `get_users_count() -> int`, whose body is `User.objects.count()` and which has no exception path. Use it for the synchronous-body assertion, and register a **test-local** failing task with `@shared_task` inside the integration module for the propagation assertion. Do **not** add a raising task to `src/` — production code must not grow a failure fixture.

## Dev Notes

### Architecture Constraints

**FR-18 — five substitutions, four of them here.** "Every valid combination starts, serves, and authenticates a persona on a machine with no database, cache, broker, or identity provider running." Its testable consequences that belong to this story: sqlite selected when neither `DATABASE_URL` nor `POSTGRES_DB` is set, preserving the ORM, migrations and the full suite; an in-process cache backend configured locally, preserving the cache API at every call site; task execution eager and propagating locally, preserving task bodies invoked synchronously.

**The fifth substitution is not this story.** Filesystem-backed object storage is delivered in Epic 7's object-storage story, "because the storage feature is greenfield and does not exist until then. Its other four substitutions are Epic 3." Do not add a `STORAGES` local override, do not touch `django-storages`, and do not claim the fifth substitution in the documentation. The fourth substitution in Epic 3's set is the local personas, which are Stories 3.3 and 3.4 — not this story either.

**FR-22 — the broker constraint is a statement about deployment only.** "Locally, all six valid combinations run with no broker." Testable consequences: combinations that selected background task processing execute tasks eagerly with no broker present locally, and "documentation states the constraint's scope explicitly, so it does not read as absolute."

**AD-9 — A contributed database is a chain, not a setting.** Binding rule: "The stage-2 unapplied-migrations refusal and the sqlite refusal both iterate every configured database — which is only possible because stage 1 runs *after* composition (AD-26). **Local substitution is applied automatically by the base, so FR-18 stays true by construction.**" Task 1's `apply_local_database_substitution` is that automatic application. Writing it as a single hardcoded `default` branch is what forces Epic 9 to invent a second mechanism — *Prevents:* "six enforcement points each being answered differently by six epics."

**AD-24 — no sub-file removal by any mechanism other than declared markers.** The Celery block in `src/config/settings/base.py` is one of the region-bearing `core` paths AD-24 knows about — the set is **open**, declared as an open `[[regions]]` array, and no count may be encoded anywhere. When touching that file: **never** introduce a conditional import, a settings-module inheritance trick, or `try/except ImportError` to make Celery configuration optional. The markers are declared in Epic 7; this story adds no markers and removes no code.

**CG-4 — Do not substitute a capability that could run locally as deployed.** Each substitution "widens the parity gap the product already trades knowingly, and each must be guarded by a refusal." The three guards already exist or are scheduled: the sqlite refusal (built today at `src/config/settings/production.py:26-28`, generalized to all aliases in Epic 4), the in-process-cache conditional refusal and the eager-execution conditional refusal (FR-14, Epic 4). Do not add a fourth substitution here.

**R-5 — Local development proves less than running suggests.** Carried verbatim into the documentation: "sqlite accepts schemas PostgreSQL rejects, eager execution never exercises delivery or retries, synthetic claims never exercise JWKS retrieval or rotation." The existing paragraph in `docs/development.md` already says something close to this; strengthen it, do not soften it.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/settings/base.py` | UPDATE | Extract `_sqlite_alias` and add `apply_local_database_substitution`; call it after the existing `DATABASE_URL` / `POSTGRES_DB` / sqlite selection. |
| `src/config/settings/local.py` | UPDATE | Comment the `CACHES` and Celery-eager blocks as declared FR-18 substitutions. No behavioural change. |
| `src/config/settings/test.py` | UPDATE | Add the explicit `CACHES` in-process block and the two Celery eager settings so the substitutions are visible rather than inherited. |
| `docs/development.md` | UPDATE | Extend `## Running with no external services` with the FR-22 scope statement, the R-5 trade-offs, and the note that the fifth substitution arrives in Epic 7. |
| `tests/unit/test_database_selection.py` | UPDATE | The alias-substitution assertions — this file, not `test_settings.py`, owns the database-selection contract. |
| `tests/unit/test_settings.py` | UPDATE | The cache and eager-task substitution assertions, reusing the existing fixtures. |
| `tests/integration/test_local_substitutions.py` | NEW | ORM / cache / eager-task round-trips against the substituted backends, under the `integration` marker. |

> **Line-number reconciliation, 2026-08-17.** This spec was written 2026-08-15; Epic 1 stories 1.6–1.9 and the whole of Epic 2 have landed since, and every citation below was re-verified against the tree at `ce04aae`. The substance of each claim held; only positions moved. The corrected positions are what appear below — the superseded ones are not preserved, because a stale line number in a spec is a trap, not a record.

**`src/config/settings/base.py` today (verified at `ce04aae`).** 545 lines. Database selection at `:72-93`: `if os.getenv("DATABASE_URL")` → `env.db("DATABASE_URL")`; `elif os.getenv("POSTGRES_DB")` → explicit PostgreSQL dict with `POSTGRES_USER`/`POSTGRES_PASSWORD` and defaulted `POSTGRES_HOST="postgres"`, `POSTGRES_PORT="5432"`; `else` → sqlite at `BASE_DIR / "db.sqlite3"` with a comment naming `production.py` as the guard. Then `DATABASES["default"]["ATOMIC_REQUESTS"] = True` at `:95` and `DEFAULT_AUTO_FIELD` at `:97`. `BASE_DIR` is defined at `:17`, `env = environ.Env()` at `:21`, `env.read_env(...)` at `:26`. `import os` `:4`, `from pathlib import Path` `:6`, `from typing import Any` `:7` — all three imports the new helpers need are already present. The Celery block runs `:337-376`, which is what AD-24 cites: `:337` is the `# Celery` header, `:376` is `CELERY_WORKER_HIJACK_ROOT_LOGGER` (the block's last line) and `:377` is the `# django-allauth` header; see Project Structure Notes. **Must be preserved:** the settings-module import of `build_logging_config` / `configure_structlog` at `:13-14` and the `configure_structlog()` call at `:328`; the `load_claims_contract` import at `:12`; `MIGRATION_MODULES` at `:148`; the `INSTALLED_APPS` composition at `:143`. There is no `CACHES` key anywhere in the file, and no module outside `src/config/settings/` reads `DATABASES`, `CACHES` or `CELERY_TASK_ALWAYS_EAGER`.

**`src/config/settings/local.py` today (verified at `ce04aae`).** 82 lines. `CACHES` with `LocMemCache` at `:21-26`. `# Celery` header at `:75`; `CELERY_TASK_ALWAYS_EAGER = True` at `:78`, `CELERY_TASK_EAGER_PROPAGATES = True` at `:80`. **Must be preserved:** the `DEBUG_APPS` gate at `:51-74`, which keeps `debug_toolbar` and `django_extensions` out of the runtime environment where those packages are absent — it is the reason `pixi run serve` works from the `default` environment.

**`src/config/settings/test.py` today (verified at `ce04aae`).** 60 lines. Sets `LOGGING` to console/WARNING (`:16`), `SECRET_KEY` (`:21-24`), `TEST_RUNNER` (`:26`), `PASSWORD_HASHERS` (`:31`), locmem email (`:36`), an `# AUTHENTICATION` block setting `CLAIMS_CONTRACT` from Epic 2 (`:38-49`), `TEMPLATES[0]["OPTIONS"]["debug"] = True` (`:53` — required by `django_coverage_plugin` for template coverage; do not remove it), and `MEDIA_URL` (`:58`). It sets no `CACHES` and no Celery settings today.

**`src/config/settings/production.py` today (verified).** The sqlite refusal is at `:26-28` — `if DATABASES["default"]["ENGINE"].endswith("sqlite3"): raise ImproperlyConfigured(...)`. It inspects only the `default` alias. Generalizing it to iterate every configured database is **Epic 4's** work (FR-13, AD-9); do not move it here, and do not change its behaviour in this story.

### Testing Requirements

- Unit assertions are split by contract ownership: database-alias substitution in `tests/unit/test_database_selection.py`, cache and eager-task substitution in `tests/unit/test_settings.py`. Integration round-trips go in `tests/integration/test_local_substitutions.py` under the `integration` marker, which `tests/integration/conftest.py:12-19` applies to every item collected in that directory; declare a file-level `pytestmark` for visibility regardless.
- `tests/unit/test_settings.py` documents its own reload contract in its module docstring: each test imports a settings module fresh so module-level environment reads are re-evaluated, and `config.settings.base` is evicted alongside the target because the `from .base import *` would otherwise reuse the already-imported copy. Follow that contract; do not introduce a competing fixture.
- Unit tests must not touch the database — `tests/unit/conftest.py` states the rule. The `apply_local_database_substitution` test operates on a plain dict, not on a connection.
- Integration tests must leave state as found: use the `db` fixture (transaction rollback) and the `user` fixture from `tests/conftest.py`.
- Coverage floor: ninety percent including templates (AD-20), `COVERAGE_CORE=ctrace` in force, `--cov-fail-under=90` via `pixi run test-cov`. `pixi run ci` must exit 0.
- Test disposition: these tests cover `core` settings surface, so they live under `tests/` mirroring `src/` and carry the `core` disposition.
- Run with `pixi run test` and `pixi run test-integration`; never bare `pytest`.

#### Project Structure Notes

Aligned with the Structural Seed: `src/config/settings/` is where "base + local + production + test; composition, then stage 1 last (AD-8, AD-26)" lives, and this story touches only that directory plus tests and docs.

**The region's extent, verified.** AD-24 cites the Celery feature-owned region in `src/config/settings/base.py` as a contiguous block, and the file agrees: at `ce04aae` it begins at `:337` (`# Celery`) and ends at `:376` (`CELERY_WORKER_HIJACK_ROOT_LOGGER = False`), with `:377` already the `# django-allauth` header. (The spine's `:296-335` citation is the same block before Epic 2 shifted it; the block, not the numbers, is what AD-24 is about.) An earlier revision cited a shorter range, stopping at `CELERY_RESULT_BACKEND_ALWAYS_RETRY`, which would have left eight further `CELERY_*` settings — including `CELERY_BEAT_SCHEDULER` — in every combination with no `django_celery_beat`. That is corrected in the spine; do not reintroduce the narrower range. This story does not add or move markers (that is Epic 7), but it must not narrow the block either: keep every `CELERY_*` setting contiguous inside that one block so the eventual marker pair can wrap it whole.

### References

- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-18] — the five substitutions and their testable consequences.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-22] — the broker constraint's scope and the documentation consequence.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#CG-4] — every substitution must be guarded by a refusal.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-9] — local substitution applied automatically by the base.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24] — no conditional imports, no settings-module inheritance, no `try/except ImportError`; the `:296-335` region citation and the open `[[regions]]` array.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-5.
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.2]
- [Source: _bmad-output/planning-artifacts/epics.md:225] — FR-18's fifth substitution is Epic 7's, not this story's.
- [Source: src/config/settings/base.py:72-97] · [Source: src/config/settings/local.py:21-26,78-80] · [Source: src/config/settings/production.py:26-28,33-44] · [Source: src/config/settings/test.py:53]
- [Source: tests/unit/test_settings.py:42-55] — the eviction and `no_database_env` fixtures.
- [Source: tests/unit/test_database_selection.py:54-83] — the eviction and clean-environment fixtures that the alias tests reuse; the file that owns the three-branch contract.
- [Source: tests/integration/conftest.py:12-19] — the directory-level `integration` marker.
- [Source: src/django_service/users/tasks.py] — `get_users_count()`, the one existing task; nothing in `src/` raises.
- [Source: docs/development.md:398-420] — the existing substitution section to extend.

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — bmad-dev-auto, 2026-08-17.

### Debug Log References

Planned against the tree at `ce04aae`. Every "today (verified)" citation in Dev Notes was
re-checked before implementation and corrected in place — the spec was written 2026-08-15 and
Epic 1's stories 1.6–1.9 plus the whole of Epic 2 had shifted `base.py` from 383 to 545 lines
and `test.py` from 46 to 60. The substance of every claim held; only positions moved.

Inner loop: `pixi run test` (556 passed) → `pixi run test-integration` (188 passed, 6 skipped)
→ `pixi run format` → `pixi run lint` → `pixi run typecheck` (49 files, clean).

**Final gate: `pixi run ci` exit 0 — 750 passed, 65 warnings, coverage 95.85% (floor 90%).**
Re-run a second time to confirm: still exit 0 with no pre-commit auto-fix churn.
`src/config/settings/base.py`, `local.py` and `test.py` are each at 100% statement coverage.

The implementation run was interrupted once by a host-level API error (the machine slept) after
Tasks 1–4 and part of Task 5 had landed on disk. It was resumed from the on-disk state rather
than restarted; nothing was re-derived from memory.

### Completion Notes List

All five tasks and every subtask are complete. Nothing was traded away and no acceptance
criterion is partially met.

**What was built.** `src/config/settings/base.py` gains `_sqlite_alias` and
`apply_local_database_substitution`, with the substitution called unconditionally after the
three-branch selection — where it is a no-op today and is the declared AD-9 hook Epic 9's
contributed database extends. `local.py` changes by comment only. `test.py` gains an explicit
`CACHES` LocMemCache block and both Celery eager settings. `docs/development.md` gains the
FR-22 deployment-scope paragraph, the Epic 7 fifth-substitution note, and a strengthened R-5
trade-off paragraph. Six new unit tests and four new integration round-trips.

**Two spec-vs-tree gaps found during planning and closed in the spec before implementing.**

1. *Three of Task 5's unit tests were already delivered.* `tests/unit/test_database_selection.py`
   did not exist when this spec was written and now owns the three-branch contract in depth,
   including `test_no_database_environment_falls_back_to_sqlite` and
   `test_database_url_wins_over_the_postgres_variables`. Writing the enumerated
   `test_sqlite_is_selected_when_no_database_is_configured` and its two precedence siblings into
   `test_settings.py` would have been three duplicates of tests that already pass. The
   alias-substitution tests went into `test_database_selection.py` instead, which owns that
   contract and already had the eviction and clean-environment fixtures.
2. *No task in `src/` raises.* Task 5 required proving that a failing task body propagates to
   the caller, but `get_users_count` — the only task the application ships — has no exception
   path. A raising task was registered in the integration module with `@shared_task` rather than
   added to `src/`; a failure fixture in production code would ship inside every generated
   component.

**Variances, recorded rather than silent.**

1. *`_sqlite_alias`'s `NAME` expression was rewritten for legibility.* The spec's form
   (`str(base_dir / f"..." if alias != "default" else base_dir / "...")`) depends on `/` binding
   tighter than the conditional, which reads as a precedence puzzle. Same output; the condition
   is stated the positive way against a named local.
2. *`apply_local_database_substitution` iterates `list(databases)`.* Mutating values during
   iteration is legal, but the snapshot is unconditionally safe against a later edit that adds a
   key.
3. *`_evict_settings_modules` in `test_settings.py` was extended, not duplicated.* Task 5's
   `config.settings.test` assertion needed that module evicted too, and the existing fixture
   popped only `base`/`local`/`production`. The spec forbade a competing fixture; it did not
   anticipate the existing one being one entry short.
4. *Synchronicity is proven by an uncommitted row, not by a type check alone.*
   `get_users_count.delay()` is asserted to return a count that includes the `user` fixture's
   row, which exists only inside the test's un-rolled-back transaction. A worker in another
   process could not see it. The `EagerResult` type is asserted as well.
5. *The failing task raises a module-local `LocalSubstitutionTaskError`.* `pytest.raises` on a
   bare `RuntimeError` would also be satisfied by the task machinery failing for an unrelated
   reason, which is the opposite of what the test claims.
6. *The docs trade-off paragraph gained a cross-reference* to the existing
   `### The parity gap between local runs and the gate` section, and names Epic 7 explicitly for
   the fifth substitution — `docs/development.md` already uses epic vocabulary elsewhere.

**Out of scope, but real — flagged rather than patched.**

1. **`.gitignore` covers `db.sqlite3` and `db.sqlite3-journal` only.** The alias-aware filename
   this story introduces means the first contributed database (Epic 9) writes
   `db.<alias>.sqlite3` into the repository root, un-ignored, and a developer will commit a
   database file. Epic 9 needs `db.*.sqlite3` and its journal added. The pattern is a footgun
   the moment that epic lands.
2. **The single-alias production refusal is now the only thing holding the door.**
   `production.py:26-28` inspects `DATABASES["default"]` only, and `base.py` now substitutes
   *every* unconfigured alias. Today `default` is the only alias, so the ordering
   (select → substitute → refuse) is correct. The window opens the moment Epic 9 adds an alias:
   a production import would substitute sqlite into it and the refusal would not see it. That
   generalization is already Epic 4's declared work (FR-13, AD-9) — this records that Epic 9
   landing first would open the gap, whichever order they arrive in.
3. **`apply_local_database_substitution` is star-exported.** `from .base import *` puts it into
   the `local`/`production`/`test` namespaces. That is what makes it reachable from a future
   contributed-database chain, and Django ignores non-uppercase names, so it configures nothing
   by being there — but `production.py` does carry a callable that would install sqlite if
   anything ever called it. Item 2 is what closes that door.
4. **`tests/integration/users/test_tasks.py:14` is now dead.** It sets
   `CELERY_TASK_ALWAYS_EAGER` via the `settings` fixture, which `config.settings.test` now
   declares. Harmless, but a reader will take it as evidence that the setting is *not* declared.
   Left alone as out of scope.

### File List

| Path | NEW / UPDATE |
| --- | --- |
| `tests/integration/test_local_substitutions.py` | NEW |
| `src/config/settings/base.py` | UPDATE |
| `src/config/settings/local.py` | UPDATE |
| `src/config/settings/test.py` | UPDATE |
| `docs/development.md` | UPDATE |
| `tests/unit/test_database_selection.py` | UPDATE |
| `tests/unit/test_settings.py` | UPDATE |
| `_bmad-output/implementation-artifacts/epic-3-context.md` | NEW (compiled planning context) |
| `_bmad-output/implementation-artifacts/3-2-the-database-cache-and-task-substitutions-hold-locally.md` | UPDATE (this record) |
