# Story 5.7: Sessions are database-backed with the engine set explicitly

Status: ready-for-dev

## Story

As a platform engineer,
I want the session engine set explicitly in every combination,
so that session behaviour is never a property of an unrelated feature toggle.

## Acceptance Criteria

**Traceability:** FR-44 · AD-10, AD-31 · NFR-3

1. **Given** `SESSION_ENGINE`
   **When** settings are composed
   **Then** it is set explicitly in `base.py` to the database-backed engine
   **And** it is identical in all twelve combinations

2. **Given** the Redis cache feature
   **When** it is selected
   **Then** it may not change `SESSION_ENGINE`

3. **Given** expired session rows and expired mapper epoch records
   **When** pruning is specified
   **Then** both are pruned by one declared admin process
   **And** deliberately not by a background task, since background task processing exists in only four of twelve combinations

4. **Given** the scheduling of that admin process
   **When** scope is assigned
   **Then** the schedule lives in the deployment repository and is out of scope here
   **And** the component-side declaration and documentation are in scope

## Tasks / Subtasks

- [ ] Task 1 — Set `SESSION_ENGINE` explicitly in `base.py` (AC: #1, #2)
  - [ ] Add to `src/config/settings/base.py` in the `# SECURITY` block (currently `:242-249`, holding `SESSION_COOKIE_HTTPONLY` at `:245`, `CSRF_COOKIE_HTTPONLY` at `:247`, `X_FRAME_OPTIONS` at `:249`):
        `SESSION_ENGINE = "django.contrib.sessions.backends.db"`
  - [ ] Place it **outside any `feature:<name>` region**. It must be unconditional code in the `core` part of the file. Verify by inspection that no `# feature:` marker encloses the new line.
  - [ ] Beside it, record the rationale in the file (spine convention): explicit because FR-44's point is that session behaviour must not vary by toggle; the Redis feature may not change it; Django's default happens to be the same value, and relying on a default is exactly what this line removes.
  - [ ] Do **not** set `SESSION_ENGINE` in `local.py`, `production.py`, or `test.py`. Do not add a `SESSION_CACHE_ALIAS`. Do not introduce a `cached_db` variant "for performance" — that reintroduces the toggle dependency.
  - [ ] `django.contrib.sessions` is already in `DJANGO_APPS` (`:96`) and `SessionMiddleware` is already in `MIDDLEWARE` (`:168`); no app or middleware change is needed.

- [ ] Task 2 — Add the single pruning admin process (AC: #3)
  - [ ] Create a Django management command in a `django_service`-owned app: `src/django_service/users/management/__init__.py`, `.../commands/__init__.py`, `.../commands/prune_expired_state.py`. (`src/django_service/users/` has no `management/` directory today.) If Epic 2 placed the AD-10 epoch model in a different `django_service` app, put the command in that app instead and record the choice.
  - [ ] The command prunes **both** in one invocation: expired session rows (via `django.contrib.sessions.backends.db.SessionStore.clear_expired()` or the equivalent queryset delete — do not shell out to `clearsessions`) and expired mapper epoch records (AD-10's `jti`-keyed table, delivered by Epic 2).
  - [ ] Emit one `structlog` event per pruned kind with the deleted row count. Never `print()`; the command must not use `self.stdout.write` as its only output channel for machine-readable results.
  - [ ] Support `--dry-run` reporting counts without deleting, and make the command idempotent and safe to run concurrently with serving traffic (delete by expiry predicate, no table lock, no `TRUNCATE`).
  - [ ] Full type hints and a Google-style docstring on `Command.handle`.
  - [ ] **Do not** implement pruning as a Celery task, a `CELERY_BEAT_SCHEDULE` entry, or a `PeriodicTask` row. AC #3's second clause is the requirement, not an implementation preference: Celery exists in only four of twelve combinations.

- [ ] Task 3 — Declare the admin process (AC: #3, #4)
  - [ ] Add a `prune` task to `pixi.toml` `[tasks]`:
        `prune = { cmd = "python manage.py prune_expired_state", default-environment = "default", description = "Admin process: prune expired sessions and mapper epoch records" }`
  - [ ] It must set **no** `COMPONENT_PROCESS` — an admin process is not a serving process, and declaring it one would fire the migrations refusal against it (AD-13's deadlock). Story 5.2's two-way gate test asserts exactly this.
  - [ ] Confirm the matching `[[admin_processes]]` entry in `component.toml` (Story 5.1): `name = "prune"`, `task = "prune"`, `schedule = "deployment-repository"`. Add a test that every `[[admin_processes]]` entry names an existing `pixi.toml` task and that no such task is in the process group.
  - [ ] Do not put a cron expression, an interval, or a schedule value in `component.toml` beyond the marker that the schedule is the deployment repository's (AC #4).

- [ ] Task 4 — Document, and state the phase boundary honestly (AC: #4)
  - [ ] `docs/deployment.md` `## Session and epoch pruning`: sessions are database-backed in every combination with `SESSION_ENGINE` set explicitly in `base.py`; expired session rows and expired mapper epoch records are pruned by one admin process, `pixi run prune`; it is deliberately not a background task because Celery exists in only four of twelve combinations.
  - [ ] State the phase boundary: **FR-44's explicit-engine half is phase 1; its scheduling half is "Next."** The component declares and documents the process; the schedule lives in the deployment repository and is out of scope here.
  - [ ] Record the AD-31 companion facts in the same section so a reader does not look for them elsewhere: session cookie hardening lives in `production.py` (`SESSION_COOKIE_SECURE` `:53`, `SESSION_COOKIE_NAME = "__Secure-sessionid"` `:55`) and is unchanged by this story.
  - [ ] Ensure `docs/deployment.md` is in `mkdocs.yml` `nav`; `pixi run docs` is `mkdocs build --strict`.

- [ ] Task 5 — Tests (AC: #1, #2, #3)
  - [ ] `tests/unit/test_session_settings.py`:
    - `django.conf.settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"`;
    - the literal appears in `src/config/settings/base.py` — a source-level assertion, because AC #1 says *set explicitly in `base.py`*, and a settings-level assertion alone would pass on Django's default;
    - `local.py`, `production.py` and `test.py` contain **no** `SESSION_ENGINE` assignment (AC #2's mechanical form: no settings module other than `base.py` may set it, so no feature's settings fragment can either);
    - the assignment in `base.py` is not enclosed by any `# feature:` / `# /feature:` marker pair — parse the markers rather than eyeballing them, since this is what makes AC #1's "identical in all twelve combinations" true after materialization.
  - [ ] Extend `tests/unit/test_settings.py` if its existing fresh-import fixtures make the multi-module assertions cheaper; that module already evicts and re-imports `config.settings.{base,local,production}` (see its docstring and `_evict_settings_modules` fixture) and is the established pattern here.
  - [ ] `tests/integration/test_prune_command.py` (`@pytest.mark.integration`): create an expired session and an expired epoch record, run the command via `call_command`, assert both are gone and a live session and a live epoch record survive; `--dry-run` deletes nothing and reports the same counts. Leave the database as found.
  - [ ] Add the `[[admin_processes]]` ↔ `pixi.toml` assertions to `tests/unit/test_process_model.py` (Story 5.2) rather than writing a second `pixi.toml` parser.

## Dev Notes

### Architecture Constraints

- **AD-31** — *Rule:* "`SESSION_ENGINE` is set explicitly in `base.py` to the database-backed engine, in every combination — **the Redis feature may not change it, because FR-44's whole point is that session behaviour must not vary by toggle.** Expired sessions and expired mapper epoch records (AD-10) are pruned by one declared admin process, not a background task, because Celery exists in only four of twelve combinations." *Prevents:* "session behaviour varying by feature toggle."
- **AD-10** — "**The epoch record lives in the database**, in a `django_service`-owned table, not in `django.core.cache`: eight of twelve combinations have no Redis… The table is pruned by a declared admin process alongside sessions (AD-31). It is internal surface (AD-29), so adding it is not an API version bump." The epoch model is Epic 2's deliverable; this story prunes it and must not redefine it.
- **NFR-3** — "Statelessness — nothing shared through local disk or process memory across replicas; **sessions database-backed in every combination.**"
- **FR-44 phase note** (epics.md §4.7): "Sessions are database-backed with the engine set explicitly in every combination; pruning is a scheduled admin process. *(Explicit engine: phase-1. **Scheduling: Next.**)*" Say so in the documentation; do not build a scheduler.
- **AD-24** — Feature-owned regions are delimited by paired `feature:<name>` / `/feature:<name>` line comments and **no other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`.** The `SESSION_ENGINE` line must sit outside every region; conversely, the Redis feature's own settings fragment (Epic 7) will be a region in this same file and must not contain a `SESSION_ENGINE` assignment.
- **AD-13** — Process type fails open; an admin process must not declare `COMPONENT_PROCESS`, or it declares itself a serving process and deadlocks on the migrations refusal.
- **AD-14** — The two-way process-model gate test derives the process group structurally; the `prune` task must fall outside it.
- **AD-29** — `src/django_service/` is `core` in its entirety and **no `feature:*` disposition may apply to any path inside it**. The management command therefore travels into all twelve combinations, which is exactly why it must not depend on Celery.
- **Project standards** — Pixi is the only runner: the command is invoked as `pixi run prune`, never bare `python manage.py`. Python 3.14 only. Full type hints, Google docstrings, line length 120. `X | Y`, `list[X]`, `dict[K, V]`. Never `print()`; never stdlib `logging` — `structlog` only. Never a bare `except:`; never `except X: pass`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/settings/base.py` | UPDATE | **`SESSION_ENGINE` is set nowhere in the repository today** — grep for `SESSION` returns only `SESSION_COOKIE_HTTPONLY` at `:245` and `production.py:53,55`. Add the explicit assignment in the `# SECURITY` block at `:242-249`. **Preserve:** `SESSION_COOKIE_HTTPONLY`, `CSRF_COOKIE_HTTPONLY`, `X_FRAME_OPTIONS`; the `django.contrib.sessions` entry at `:96`; `SessionMiddleware` at `:168`; the whole Celery block at `:296-335`. |
| `src/django_service/users/management/__init__.py` | **NEW** | No `management/` directory exists under any `django_service` app today. |
| `src/django_service/users/management/commands/__init__.py` | **NEW** | |
| `src/django_service/users/management/commands/prune_expired_state.py` | **NEW** | Prunes expired sessions and expired AD-10 epoch records in one invocation; `--dry-run`; structured log events with row counts. |
| `pixi.toml` | UPDATE | Add `prune` to `[tasks]` (`:172`) with **no** `env` table. Preserve the existing `manage`/`migrate`/`collectstatic`/`createsuperuser`/`serve` entries at `:173-179`. |
| `component.toml` | verify (created by Story 5.1) | The `[[admin_processes]]` `prune` entry, `schedule = "deployment-repository"`. |
| `docs/deployment.md` | UPDATE (NEW if earlier Epic 5 stories have not landed) | Adds `## Session and epoch pruning`. |
| `mkdocs.yml` | UPDATE | Register `deployment.md` in `nav`. |
| `tests/unit/test_session_settings.py` | **NEW** | Explicit-in-`base.py`, absent-elsewhere, outside-any-region. |
| `tests/unit/test_settings.py` | UPDATE (optional) | Existing module with fresh-import fixtures for `base`/`local`/`production`; reuse rather than duplicate. |
| `tests/integration/test_prune_command.py` | **NEW** | Expired rows deleted, live rows kept, `--dry-run` deletes nothing. |
| `tests/unit/test_process_model.py` | UPDATE (created by Story 5.2) | `[[admin_processes]]` ↔ task assertions; `prune` not in the process group. |

**Line-range check:** the epic cites no ranges for this story. `src/config/settings/base.py` anchors verified 2026-08-15 — DATABASES `:57-78`, `DJANGO_APPS` `:93-103`, `MIDDLEWARE` `:164-179`, MEDIA `:195-200`, SECURITY `:242-249`, Celery `:296-335`.

### Testing Requirements

- Unit: `tests/unit/test_session_settings.py` — settings introspection plus source-text assertions; no database, milliseconds. The source-text assertion is load-bearing: `SESSION_ENGINE`'s Django default is the same value, so a settings-only assertion would pass with the line absent and AC #1 would be unproven.
- Integration: `tests/integration/test_prune_command.py` — `@pytest.mark.integration`; `tests/integration/conftest.py:12-19` also auto-marks the directory. Uses the real database; must leave state as found (create rows inside the test, assert, let the transaction roll back).
- Disposition (spine Consistency Conventions): everything here covers `core` paths — `src/config/settings/base.py` outside any region, and `src/django_service/` which AD-29 makes `core` in its entirety — so these tests are `core` and run in every combination's gate, never pruned.
- AD-20 floor: 90% including templates, `COVERAGE_CORE=ctrace` in force (`pixi.toml:145-150`). The management command's `--dry-run` and delete branches both need coverage. Do not add anything to `[tool.coverage.run] omit` (`pyproject.toml:162-169`) — AD-20 makes that list a closed, carrier-declared surface.
- Inner loop `pixi run test` then `pixi run test-integration`; done when `pixi run ci` exits 0.

#### Project Structure Notes

- **Dependency on Epic 2:** the AD-10 mapper epoch table does not exist yet — `src/config/authorization/` is absent and the model is Epic 2's deliverable. Epic 2 precedes Epic 5 in epics.md's dependency flow, so by the time this story runs the model exists; locate it in whichever `django_service` app Epic 2 placed it in and import it directly. Do **not** create the model here, and do **not** guard its import with `try/except ImportError` (AD-24 forbids that mechanism outright).
- **Dependency on Story 5.1:** the `[[admin_processes]]` entry. **Dependency on Story 5.2:** the process-group definition the `prune` task must fall outside of.
- The Structural Seed does not enumerate a `management/` directory; adding one under an existing `django_service` app is ordinary Django structure and no variance from the seed.
- **Not in scope and must not be built:** a schedule, a cron entry, a `PeriodicTask` row, a Celery beat schedule, or a `CELERY_BEAT_SCHEDULE` key. FR-44's scheduling half is "Next" and the schedule is the deployment repository's.
- **AD-31's other half is not this story's:** allauth's `SOCIALACCOUNT_PROVIDERS` from the environment, and retiring `src/django_service/contrib/sites/migrations/0003_set_site_domain_and_name.py`, belong to Epic 2. That migration still exists today; leave it alone.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-31]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-10]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-14]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.7]
- [Source: _bmad-output/planning-artifacts/epics.md#§4.7 The Deployment Interface] — "Phase-1 must-have, except FR-44's scheduling half which is Next."
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-44]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#NFR-3]
- Repository state: `src/config/settings/base.py:96, 168, 242-249, 296-335`; `src/config/settings/production.py:53, 55`; `pixi.toml:145-150, 172-182`; `tests/unit/test_settings.py:1-30`; `tests/integration/conftest.py:12-19`; no `management/` directory under `src/django_service/`.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
