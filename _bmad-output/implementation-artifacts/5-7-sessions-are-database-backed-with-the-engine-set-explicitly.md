---
status: done
baseline_revision: 5f4cd44
review_loop_iteration: 0
warnings: [oversized]
followup_review_recommended: true
final_revision: 13adf37
---

# Story 5.7: Sessions are database-backed with the engine set explicitly

Status: ready-for-review

## Story

As a platform engineer,
I want the session engine set explicitly in every combination,
so that session behaviour is never a property of an unrelated feature toggle.

## Acceptance Criteria

**Traceability:** FR-44 · AD-10, AD-31 · NFR-3

1. **Given** `SESSION_ENGINE`
   **When** settings are composed
   **Then** it is set explicitly in `base.py` to the database-backed engine
   **And** it is identical in all six combinations

2. **Given** the Redis cache feature
   **When** it is selected
   **Then** it may not change `SESSION_ENGINE`

3. **Given** expired session rows and expired mapper epoch records
   **When** pruning is specified
   **Then** both are pruned by one declared admin process
   **And** deliberately not by a background task, since background task processing exists in only two of six combinations, and the session table in the other four would otherwise grow unbounded

4. **Given** the scheduling of that admin process
   **When** scope is assigned
   **Then** the schedule lives in the deployment repository and is out of scope here
   **And** the component-side declaration and documentation are in scope

## Tasks / Subtasks

> **Anchors reconciled against the tree at `5f4cd44` (2026-08-29).** Every line
> number the original draft carried had drifted — the settings file has grown by
> roughly a hundred lines since 2026-08-15 and `pixi.toml` by three hundred.
> The corrected anchors are used below and recorded in *Dev Notes → Line-range
> reconciliation*.

- [x] Task 1 — Set `SESSION_ENGINE` explicitly in `base.py` (AC: #1, #2)
  - [x] Add to `src/config/settings/base.py` in the `# SECURITY` block (`:343-350`, holding
        `SESSION_COOKIE_HTTPONLY` at `:346`, `CSRF_COOKIE_HTTPONLY` at `:348`, `X_FRAME_OPTIONS` at `:350`):
        `SESSION_ENGINE = "django.contrib.sessions.backends.db"`
  - [x] Follow the file's own two comment registers: the Django docs-URL line directly above the assignment
        (the whole `# SECURITY` block's style), **plus** the prose register the file uses wherever a setting
        encodes a project decision (`LOGIN_URL` at `:232-237`, `DJANGO_ADMIN_FORCE_ALLAUTH` at `:382-389`).
        The rationale to record: explicit because FR-44's point is that session behaviour must not vary by
        toggle; the Redis feature may not change it; Django's default happens to be the same value, and
        relying on a default is exactly what this line removes.
  - [x] Place it **outside any `feature:<name>` region**. Verified state of the tree: there are **zero**
        `# feature:` markers in `base.py`, `local.py`, `production.py` or `test.py` today, so the constraint
        is forward-looking rather than a present hazard — Epic 7's `redis` region will be the first marker
        pair in this file and must not enclose this line. Task 5 asserts it mechanically so the constraint
        survives that arrival.
  - [x] Do **not** set `SESSION_ENGINE` in `local.py`, `production.py`, or `test.py`. Do not add a
        `SESSION_CACHE_ALIAS`. Do not introduce a `cached_db` variant "for performance" — that reintroduces
        the toggle dependency.
  - [x] `django.contrib.sessions` is already in `DJANGO_APPS` (`:161`) and `SessionMiddleware` is already in
        `MIDDLEWARE` (`:269`); no app or middleware change is needed.

- [x] Task 2 — Add the single pruning admin process (AC: #3)
  - [x] Create a Django management command: `src/django_service/users/management/__init__.py`,
        `.../commands/__init__.py`, `.../commands/prune_expired_state.py`. **`users` is the right app,
        confirmed:** Epic 2 put the AD-10 record in `src/django_service/users/models.py:48` as
        `CredentialEpoch` (app label `users`, table `users_credentialepoch`). No `management/` directory
        exists anywhere under `src/` today, and this repository has no custom management command yet.
  - [x] The command prunes **both** in one invocation:
    - sessions — `Session.objects.filter(expire_date__lt=timezone.now())`, importing
      `django.contrib.sessions.models.Session` directly. This is the predicate Django's own `clearsessions`
      and `SessionStore.clear_expired()` use. Import the model rather than calling `clear_expired()` because
      the `--dry-run` leg needs a **count** and `clear_expired()` returns none; the direct import is coherent
      precisely because Task 1 makes the database engine explicit. Do not shell out to `clearsessions`.
    - epochs — `CredentialEpoch.objects.filter(expires_at__lt=timezone.now())`. `expires_at`
      (`models.py:86`) is `null=True, db_index=True`, and the index exists specifically for this scan.
      `__lt` excludes NULL in SQL, which is the **required** behaviour and not an accident: `_expires_at()`
      (`src/config/authorization/mapper.py:980-1010`) writes `None` when the token carries no readable `exp`,
      and a null expiry means "not prunable by expiry". Never prune on `first_seen_at`.
  - [x] Emit one `structlog` event per pruned kind with the deleted row count. Module-level idiom, matching
        the repository: `logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)`; event names
        are `snake_case`, dot-namespaced by subsystem, outcome-phrased, first positional arg, everything else
        keyword pairs. **Never log a `jti` value** — the house rule at `mapper.py:945-947` logs `jti_length`
        instead. Never `print()`; `self.stdout.write` must not be the only output channel.
  - [x] Support `--dry-run` reporting counts without deleting, and make the command idempotent and safe to
        run concurrently with serving traffic (delete by expiry predicate, no table lock, no `TRUNCATE`).
        `QuerySet.delete()` returns `(total, per_label)`, which is the count both legs report.
  - [x] Full type hints — `add_arguments(self, parser: CommandParser) -> None`,
        `handle(self, *args: Any, **options: Any) -> None` — and a Google-style docstring on `Command.handle`.
        `mypy --strict` runs with `mypy_django_plugin` and django-stubs 5.2 (`pyproject.toml:310-335`).
  - [x] **Do not** implement pruning as a Celery task, a `CELERY_BEAT_SCHEDULE` entry, or a `PeriodicTask`
        row. AC #3's second clause is the requirement, not an implementation preference: Celery exists in only
        two of six combinations, and in the other four the pruning would simply never run.

- [x] Task 3 — Declare the admin process (AC: #3, #4)
  - [x] Add a `prune` task to `pixi.toml` `[tasks]` (`:456`), directly after `createsuperuser` (`:460`) in
        the "Django (runtime environment)" block:
        `prune = { cmd = "python manage.py prune_expired_state", default-environment = "default", description = "Admin process: prune expired sessions and mapper epoch records" }`
  - [x] It must sit **outside** the `# feature:celery` region (`:516-529`) — that region's bounds are
        positionally asserted by `tests/unit/test_process_model.py::test_the_celery_process_tasks_sit_inside_a_marker_pair`
        (`:398`), and pruning must exist in all six combinations.
  - [x] It must declare **no `env` table at all**: no `COMPONENT_PROCESS` (an admin process is not a serving
        process — AD-13's deadlock; asserted by `test_process_model.py:368` and
        `tests/unit/test_locality_declaration.py:412`), and no `COMPONENT_RUNTIME`
        (`test_locality_declaration.py:388` fails any task that declares one).
  - [x] The `component.toml` `[[admin_processes]]` entry **already exists** (`:184-187`: `name = "prune"`,
        `task = "prune"`, `schedule = "deployment-repository"`), created by Story 5.1. Verify it; do not add
        or restate it.
  - [x] Add the **forward direction** to `tests/unit/test_process_model.py`: every `[[admin_processes]]`
        entry names a task `pixi.toml` actually declares, and no task an admin process names is in the process
        group. Use `tasks_named()` from `tests/pixi_manifest.py`, which the module already imports. Rewrite
        the "Deliberately not asserted" paragraph in
        `test_no_administrative_process_runs_a_task_that_declares_a_process_type`'s docstring (`:390-397`):
        it names *this* story as the one that closes the gap, so leaving it standing would be a false record.
  - [x] Do not put a cron expression, an interval, or a schedule value in `component.toml` beyond the marker
        that the schedule is the deployment repository's (AC #4).

- [x] Task 4 — Document, and state the phase boundary honestly (AC: #4)
  - [x] Add `## Session and epoch pruning` to `docs/deployment.md`, after `## The component is a payload`
        (`:453`). Sessions are database-backed in every combination with `SESSION_ENGINE` set explicitly in
        `base.py`; expired session rows and expired mapper epoch records are pruned by one admin process,
        `pixi run prune`; it is deliberately not a background task because Celery exists in only two of six
        combinations, so in the other four a scheduled task would never run and the session table would grow
        without bound.
  - [x] **Do not rename or remove any existing `##`/`###` heading.** `## The two declarations` (`:6`),
        `## Migrations are a release-stage step` (`:179`) and `### Accepted risk R-3: the refusal only fires
        for a declared process` (`:264`) are pinned by name in `tests/unit/test_component_declaration.py` and
        `tests/unit/test_release_stage.py`. Adding a new heading is safe; renaming a pinned one fails the gate.
  - [x] Match the page's register: second person to the deployment-repository operator, the load-bearing claim
        in bold, then the reason it exists and the failure it prevents, closing by naming the test that
        enforces it mechanically.
  - [x] State the phase boundary: **FR-44's explicit-engine half is phase 1; its scheduling half is "Next."**
        The component declares and documents the process; the schedule lives in the deployment repository and
        is out of scope here.
  - [x] Record the AD-31 companion facts in the same section so a reader does not look for them elsewhere:
        session cookie hardening lives in `production.py` (`SESSION_COOKIE_SECURE` `:55`,
        `SESSION_COOKIE_NAME = "__Secure-sessionid"` `:57`) and is unchanged by this story.
  - [x] `docs/deployment.md` is **already** registered in `mkdocs.yml` `nav` at `:39` — verify, do not edit.
        `pixi run docs` is `mkdocs build --strict`.

- [x] Task 5 — Tests (AC: #1, #2, #3)
  - [x] **Promote the AD-24 marker parser to `tests/feature_regions.py`** and refactor
        `tests/unit/startup/test_feature_scoped_refusals.py` onto it without changing a single assertion.
        It currently holds the only complete implementation — `MARKER` (`:298`), `_Region` (`:331`),
        `_marker_events` (`:359`), `_regions` (`:379`) — and there is no shared helper anywhere; a private
        copy in the new module would be the fourth. This repository's established answer to that is
        promotion, not duplication: `tests/pixi_manifest.py` (Story 5.5) and `tests/dockerfile.py`
        (Story 5.6) were both lifted out of a test module the same way. Leave the substring-matching
        `FEATURE_MARKERS` tuples in `test_component_declaration.py:92` and `test_process_model.py:136`
        alone — they answer a different, positional question about TOML.
  - [x] `tests/unit/test_session_settings.py` (**NEW**, disposition `core`):
    - `django.conf.settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"`;
    - the literal appears in `src/config/settings/base.py` — a source-level assertion, because AC #1 says
      *set explicitly in `base.py`*, and a settings-level assertion alone would pass on Django's default,
      which is the same string;
    - `local.py`, `production.py` and `test.py` contain **no** `SESSION_ENGINE` assignment (AC #2's
      mechanical form: no settings module other than `base.py` may set it, so no feature's settings fragment
      can either);
    - the assignment in `base.py` is enclosed by no region — computed with `tests/feature_regions.regions()`
      over the file's own text, not eyeballed, since this is what makes AC #1's "identical in all six
      combinations" true after materialization;
    - a vacuity guard that the scanner sees the file it claims to (the module's own established pattern:
      `test_process_model.py:219`), because every marker assertion above is trivially true in a file with
      no markers.
    - Where a test needs a freshly imported settings module, go through `tests/settings_import.py`'s
      `evicted_settings_modules()` / `import_settings()`, as `tests/unit/test_settings.py:53-68` and
      `test_payload_properties.py:376-390` do. Re-importing `base.py` without eviction leaves structlog
      reconfigured for every later module in the session.
  - [x] Update `tests/unit/test_payload_properties.py::test_the_session_store_is_the_database_store`
        (`:1115`). Story 5.6 wrote its docstring (`:1118-1129`) to say that `SESSION_ENGINE` is set nowhere in
        `src/`, that what resolves is Django's global default, and that setting it explicitly "is 5.7's task"
        — all three become false with Task 1. Rewrite that prose and tighten the
        `getattr(module, "SESSION_ENGINE", None)` / `global_settings` fallback (`:1144-1146`) into an
        assertion that the setting is present, since this story now guarantees it.
  - [x] `tests/integration/test_prune_command.py` (**NEW**, disposition `core`): use `@pytest.mark.django_db`
        — **not** `transaction=True`, which truncates the tables the group-provisioning migration seeds
        (`tests/integration/authorization/test_mapper_sync.py:9-13` records why). The directory's `conftest.py`
        auto-applies `pytest.mark.integration`, so no explicit marker is needed. Cases: an expired session row
        and an expired epoch record are both deleted by one `call_command` invocation; a live session and a
        live epoch record survive; an epoch with a **null** `expires_at` survives; `--dry-run` deletes nothing
        and reports the same counts; the structlog events carry the counts
        (`structlog.testing.capture_logs()`, the module-local `_events(captured, "event.name")` idiom from
        `tests/integration/authorization/test_mapper_sync.py`). Rows are created inline —
        `Session.objects.create(session_key=..., session_data="", expire_date=...)` and
        `CredentialEpoch.objects.create(jti=..., user=..., expires_at=...)` with the `user` fixture
        (`tests/conftest.py:225`); there is no epoch factory and one is not needed. Leave the database as
        found.
  - [x] Every new test module opens with the house docstring: the property and the AD/FR it comes from, why
        the property is worth asserting and what failure it prevents, the spine disposition, explicit
        "asserted elsewhere" cross-references, and a closing sentence classifying it unit-vs-integration in
        terms of I/O.
  - [x] Coverage: the command's `--dry-run` and delete branches both need exercising (AD-20 floor 90%,
        `include = [ "src/**" ]`). **Nothing** may be added to `[tool.coverage.run] omit` — AD-20 makes that
        list a closed, carrier-declared surface and `tests/unit/test_coverage_policy.py` freezes it.
  - [x] Add no `pytest.mark.skip`/`skipif`/`xfail` and no `pytest.importorskip` anywhere: `test_suite_policy.py`
        fails on any of them unless recorded in `RECORDED_EXEMPTIONS`, and nothing here needs one.

## Dev Notes

### Architecture Constraints

- **AD-31** — *Rule:* "`SESSION_ENGINE` is set explicitly in `base.py` to the database-backed engine, in every combination — **the Redis feature may not change it, because FR-44's whole point is that session behaviour must not vary by toggle.** Expired sessions and expired mapper epoch records (AD-10) are pruned by one declared admin process, not a background task, because Celery exists in only two of six combinations." *Prevents:* "session behaviour varying by feature toggle."
- **AD-10** — "**The epoch record lives in the database**, in a `django_service`-owned table, not in `django.core.cache`: two of six combinations have no Redis… The table is pruned by a declared admin process alongside sessions (AD-31). It is internal surface (AD-29), so adding it is not an API version bump." The epoch model is Epic 2's deliverable; this story prunes it and must not redefine it.
- **NFR-3** — "Statelessness — nothing shared through local disk or process memory across replicas; **sessions database-backed in every combination.**"
- **FR-44 phase note** (epics.md §4.7): "Sessions are database-backed with the engine set explicitly in every combination; pruning is a scheduled admin process. *(Explicit engine: phase-1. **Scheduling: Next.**)*" Say so in the documentation; do not build a scheduler.
- **AD-24** — Feature-owned regions are delimited by paired `feature:<name>` / `/feature:<name>` line comments and **no other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`.** The `SESSION_ENGINE` line must sit outside every region; conversely, the Redis feature's own settings fragment (Epic 7) will be a region in this same file and must not contain a `SESSION_ENGINE` assignment.
- **AD-13** — Process type fails open; an admin process must not declare `COMPONENT_PROCESS`, or it declares itself a serving process and deadlocks on the migrations refusal.
- **AD-14** — The two-way process-model gate test derives the process group structurally; the `prune` task must fall outside it.
- **AD-29** — `src/django_service/` is `core` in its entirety and **no `feature:*` disposition may apply to any path inside it**. The management command therefore travels into all six combinations, which is exactly why it must not depend on Celery. Revision 3 also makes the interface mechanism part of that core; that changes nothing here, since `SESSION_ENGINE` was never interface-owned.
- **Project standards** — Pixi is the only runner: the command is invoked as `pixi run prune`, never bare `python manage.py`. Python 3.14 only. Full type hints, Google docstrings, line length 120. `X | Y`, `list[X]`, `dict[K, V]`. Never `print()`; never stdlib `logging` — `structlog` only. Never a bare `except:`; never `except X: pass`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/settings/base.py` | UPDATE | **`SESSION_ENGINE` is set nowhere in the repository today** — the only `SESSION*` names in `src/` are `SESSION_COOKIE_HTTPONLY` (`base.py:346`), `SESSION_COOKIE_SECURE`/`SESSION_COOKIE_NAME` (`production.py:55,57`) and the unrelated `SESSION_BACKEND` constant in `src/config/local_dev/views.py:101`. Add the explicit assignment in the `# SECURITY` block at `:343-350`. **Preserve:** `SESSION_COOKIE_HTTPONLY`, `CSRF_COOKIE_HTTPONLY`, `X_FRAME_OPTIONS`; `django.contrib.sessions` at `:161`; `SessionMiddleware` at `:269`; the Celery block and `configure_structlog()` at `:405`. |
| `src/django_service/users/management/__init__.py` | **NEW** | No `management/` directory exists anywhere under `src/` today. |
| `src/django_service/users/management/commands/__init__.py` | **NEW** | |
| `src/django_service/users/management/commands/prune_expired_state.py` | **NEW** | Prunes expired sessions and expired `CredentialEpoch` records in one invocation; `--dry-run`; structured log events with row counts. |
| `pixi.toml` | UPDATE | Add `prune` to `[tasks]` (`:456`), after `createsuperuser` (`:460`), with **no** `env` table and outside the `# feature:celery` region (`:516-529`). Preserve `manage`/`migrate`/`collectstatic`/`createsuperuser` (`:457-460`) and `serve` (`:476`). |
| `component.toml` | verify only | `[[admin_processes]]` `prune` already at `:184-187` with `schedule = "deployment-repository"`. Unchanged. |
| `docs/deployment.md` | UPDATE | Adds `## Session and epoch pruning` after `## The component is a payload` (`:453`). No existing heading renamed. |
| `mkdocs.yml` | verify only | `deployment.md` already in `nav` at `:39`. Unchanged. |
| `tests/feature_regions.py` | **NEW** | The AD-24 marker parser, *promoted* from `tests/unit/startup/test_feature_scoped_refusals.py` (`:298`, `:331-402`) rather than copied — the pattern `tests/pixi_manifest.py` and `tests/dockerfile.py` established. |
| `tests/unit/startup/test_feature_scoped_refusals.py` | UPDATE | Imports the promoted parser; its private `MARKER`/`_Region`/`_marker_events`/`_regions` are deleted. **No assertion changes.** |
| `tests/unit/test_session_settings.py` | **NEW** | Explicit-in-`base.py`, absent-elsewhere, outside-any-region, plus a vacuity guard. |
| `tests/unit/test_payload_properties.py` | UPDATE | `test_the_session_store_is_the_database_store` (`:1115`): docstring corrected, `global_settings` fallback (`:1144-1146`) tightened into a presence assertion. |
| `tests/unit/test_process_model.py` | UPDATE | The admin-process forward direction, and the "Deliberately not asserted" paragraph at `:390-397` rewritten. |
| `tests/integration/test_prune_command.py` | **NEW** | Expired rows deleted, live rows and null-expiry rows kept, `--dry-run` deletes nothing, log events carry the counts. |

### Line-range reconciliation (verified at `5f4cd44`, 2026-08-29)

Every anchor the 2026-08-15 draft carried had drifted. Corrected values, used throughout above:

| Claim in the draft | Actual |
|---|---|
| `base.py` `# SECURITY` block `:242-249` | `:343-350` — `SESSION_COOKIE_HTTPONLY` `:346`, `CSRF_COOKIE_HTTPONLY` `:348`, `X_FRAME_OPTIONS` `:350` |
| `django.contrib.sessions` at `base.py:96` | `:161`, inside `DJANGO_APPS` `:158-168` |
| `SessionMiddleware` at `base.py:168` | `:269`, inside `MIDDLEWARE` `:265-280` |
| `production.py:53, 55` | `SESSION_COOKIE_SECURE` `:55`, `SESSION_COOKIE_NAME` `:57` |
| `pixi.toml` `[tasks]` at `:172`, entries `:173-179` | `[tasks]` `:456`, entries `:457-460`, `serve` `:476`, `web` `:503`, `# feature:celery` region `:516-529` |
| `pixi.toml:145-150` for `COVERAGE_CORE` | still set; the coverage floor task is `test-cov` at `:579` |
| `pyproject.toml` omit `:162-169` | `[tool.coverage.run]` `include = [ "src/**" ]` with a five-entry `omit`; unchanged in substance |

**Task names in this repository are `format`, `typecheck` and `test-cov`** — not `fmt`, `check`, `cov`.
`pixi run ci` (`pixi.toml:615`) chains `precommit → build → typecheck → lint → test-cov`, in that order.

**Two claims in the draft were already true and need only verification, not work:** `component.toml`'s
`[[admin_processes]]` `prune` entry exists at `:184-187`, and `docs/deployment.md` is registered in
`mkdocs.yml` `nav` at `:39`.

**Two claims were false in the draft's favour and are now facts:** the AD-10 epoch model *does* exist —
`CredentialEpoch`, `src/django_service/users/models.py:48`, migration `0004_credentialepoch.py` — so the
"Epic 2 has not landed" hedging is retired; and `base.py` contains no `# feature:` markers at all, so the
"outside any region" requirement is a constraint on Epic 7's future `redis` region rather than a present
one to navigate.

**One obligation this story inherits.** Story 5.6 left
`tests/unit/test_payload_properties.py::test_the_session_store_is_the_database_store` (`:1115`) asserting only
that the *resolved* store is the database store, with a docstring that names this story as the owner of the
explicit setting. Task 1 makes that docstring false; Task 5 rewrites it. This is the "sessions residue is
Story 5.7's" line in 5.6's Completion Notes coming due.

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

claude-opus-5[1m] (Claude Opus 5, 1M context), via Claude Code.

### Debug Log References

- **Every "verify only" claim in the task list checked and found true.** `component.toml`
  `[[admin_processes]]` `prune` sits at `:184-187` with `schedule = "deployment-repository"` and was not
  touched. `docs/deployment.md` is at `mkdocs.yml` `nav` line 39 and was not touched. `base.py`,
  `local.py`, `production.py` and `test.py` carry zero `# feature:` markers, so "outside any region" was a
  forward-looking constraint rather than a present hazard -- which is why the test asserting it needed a
  vacuity guard read off a file that *does* carry markers.
- **`_prune` had to become a PEP 695 generic.** The first spelling used a `TypeVar`, and ruff `UP047`
  fails a generic function written that way on Python 3.14. `def _prune[ModelT: Model](...)` is what
  passes both `lint` and `mypy --strict`.
- **`Path` in `test_session_settings.py` is a `TYPE_CHECKING` import.** Every use is in a `Final[Path]`
  annotation -- the values themselves come from `REPO_ROOT / ...` -- so ruff `TC003` moves it. Recorded
  because the module reads as though it uses `Path` at run time and does not.
- **PostgreSQL 17 was brought up for the integration run**, per the project memory note: `docker run -d
  --rm --name pg-local ... -p 55432:5432 postgres:17`, then `DATABASE_URL=postgres://...:55432/gatedb`.
  `test_gatedb` was created in that container, which is the direct evidence the run was not on the sqlite
  substitution. The container was stopped afterwards.
- **`delete()`'s per-label count, not its total.** `QuerySet.delete()` returns `(total, per_label)` and
  the total includes cascaded rows. Neither model is the parent of anything today, so the two agree; the
  per-label lookup is what keeps them agreeing if either ever gains a dependent. Reading the label needs
  `Model._meta.label`, which is `# noqa: SLF001` in the same form and with the same reason
  `config/authorization/mapper.py:966` already carries.

#### Verification actually run

| Command | Literal result |
|---|---|
| `pixi run lint` | All checks passed |
| `pixi run typecheck` | Success: no issues found in 74 source files |
| `pixi run format` | 2 files reformatted, 200 unchanged (the two new test modules) |
| `pixi run test` | 1217 passed, 4.71 s |
| `pixi run test-integration` (`DATABASE_URL` → PostgreSQL 17) | 300 passed, 6 skipped, 74.75 s — the 6 are the pre-existing `test_coverage_measurement.py` `--cov` guard |
| `pixi run docs` (`mkdocs build --strict`) | Documentation built, no warnings |
| `pixi run ci` | **exit 0** — pre-commit all Passed, build OK, mypy OK, ruff OK, **1523 passed**, coverage **97.03 %** (floor 90) |
| `pixi run test-cov` with `DATABASE_URL` → PostgreSQL 17 | 1523 passed, coverage 97.03 % |
| `prune_expired_state.py` coverage | 35 statements, **0 missed, 100 %** — both the `--dry-run` and the delete branch |

### Completion Notes List

- **`src/config/settings/base.py`.** `SESSION_ENGINE = "django.contrib.sessions.backends.db"` added at
  the head of the `# SECURITY` block, above `SESSION_COOKIE_HTTPONLY`. Carries both of the file's comment
  registers, as Task 1 directs: the bare Django docs-URL line, then the prose register the file uses
  wherever a setting encodes a project decision -- that Django's default is the same string is exactly why
  the line is worth writing, that the Redis feature may not change it, that it sits outside every region,
  and that no `cached_db` variant or `SESSION_CACHE_ALIAS` may be added. Nothing else in the block moved;
  `django.contrib.sessions` and `SessionMiddleware` were already present and needed no change.
- **`src/django_service/users/management/{__init__.py,commands/__init__.py}` (NEW).** Empty, which is the
  `django_service` convention (`users/__init__.py` and `users/api/__init__.py` are both empty; only
  `config/` packages carry charter docstrings).
- **`src/django_service/users/management/commands/prune_expired_state.py` (NEW).** Prunes both kinds in
  one invocation: `Session.objects.filter(expire_date__lt=now)` and
  `CredentialEpoch.objects.filter(expires_at__lt=now)`. The session model is imported directly rather than
  `clearsessions` shelled out to, because `--dry-run` needs a count and `clear_expired()` returns none --
  and that import is only coherent because Task 1 made the engine explicit, which the module docstring
  says. `--dry-run` counts and deletes nothing. Two structlog events, one per kind, each carrying its
  count; never a `jti`, never a user identifier. `self.stdout.write` is a second channel, not the only
  one. No Celery anywhere: `src/django_service/` is `core` (AD-29), so this travels into all six
  combinations and must not depend on a feature that exists in two.
- **The event names carry the mode.** `prune.sessions_pruned` / `prune.epochs_pruned` for a real run,
  `prune.sessions_prunable` / `prune.epochs_prunable` for a rehearsal, rather than one name plus a
  `dry_run` field. The name is what an operator's alerting keys on, and a rehearsal emitting `...pruned`
  would be counted as a prune that happened -- a table left growing would look like a table being kept.
  Both spellings still carry `dry_run` in the payload.
- **`pixi.toml`.** `prune` added to `[tasks]` directly after `createsuperuser`, in the "Django (runtime
  environment)" block, well above the `# feature:celery` region. **No `env` table at all** -- no
  `COMPONENT_PROCESS` (AD-13's deadlock) and no `COMPONENT_RUNTIME` (locality is the environment's). The
  comment above it says why the *position* is load-bearing, which position alone does not carry.
- **`tests/feature_regions.py` (NEW).** The AD-24 marker parser, **promoted** from
  `tests/unit/startup/test_feature_scoped_refusals.py` rather than copied -- the pattern
  `tests/pixi_manifest.py` (5.5) and `tests/dockerfile.py` (5.6) established. Carries `MARKER`, `Region`,
  `marker_events` and `regions`, all now public. Its docstring records what it deliberately does *not*
  answer: the substring `FEATURE_MARKERS` tuples in `test_component_declaration.py` and
  `test_process_model.py` stay where they are, because they ask a positional question about TOML lines.
- **`tests/unit/startup/test_feature_scoped_refusals.py`.** Imports the promoted parser; its private
  `MARKER`, `_Region`, `_marker_events` and `_regions` are deleted, and the now-unused `dataclass` import
  with them. **No assertion changed** -- the two functions are imported *under their old private names* on
  purpose, because four cases assign a local `regions` and importing `regions` under its own name would
  shadow it into an `UnboundLocalError`. The import block says so.
- **`tests/unit/test_session_settings.py` (NEW), 5 cases, disposition `core`.** The resolved
  `settings.SESSION_ENGINE`; exactly one assignment in `base.py` and the string it assigns; zero
  assignments in `local.py`, `production.py` and `test.py`; the assignment enclosed by no region,
  computed with `tests/feature_regions.regions()`; and a vacuity guard. Assignments are found by `ast`
  rather than by substring, because this module's own prose and `base.py`'s new comment both contain the
  name and neither is an assignment.
- **The vacuity guard is the load-bearing one.** `base.py` has no markers, so the region case is
  trivially true -- true for a file with no regions, for a parser that found none, and for a parser that
  had stopped working. The guard reads `src/config/startup/stage_one.py` *through the same `regions()`*
  and requires a non-empty result, which is the only thing distinguishing those three states until Epic 7
  places the `redis` region.
- **`tests/unit/test_payload_properties.py`.** `test_the_session_store_is_the_database_store`: the
  docstring's three now-false claims rewritten, and the `global_settings` fallback replaced by an
  assertion that `production.py` composes the setting at all -- falling back would make the case pass on
  Django's default, which is the same string. The module docstring's sessions bullet now points at
  `test_session_settings.py` for the declaration side instead of forward-referencing this story.
- **`tests/unit/test_process_model.py`.** New
  `test_every_declared_admin_process_names_a_task_that_exists` -- the forward direction, written over
  every `[[admin_processes]]` entry rather than over the name `prune`, with its own non-vacuity assert.
  The "Deliberately not asserted: that the task exists" paragraph in
  `test_no_administrative_process_runs_a_task_that_declares_a_process_type` was rewritten; leaving it
  would have been a false record.
- **`tests/integration/test_prune_command.py` (NEW), 5 cases, disposition `core`.** Both kinds pruned by
  one `call_command`; live rows survive; a null-`expires_at` epoch survives; `--dry-run` deletes nothing
  *and reports the numbers the real run then reports*; the events carry the counts and no `jti`.
  `@pytest.mark.django_db` without `transaction=True`. All five rows are seeded in every case, so a
  pruner that emptied both tables cannot pass the first case.
- Nothing was added to `[tool.coverage.run] omit`. No `skip`/`skipif`/`xfail`/`importorskip` anywhere.
- **`docs/deployment.md`.** New `## Session and epoch pruning` after `## The component is a payload`,
  with three subsections. No existing heading renamed or removed. Second person throughout, the
  load-bearing claim in bold, `pixi run prune` and `--dry-run` shown as an operator runs them, the
  not-a-background-task reason stated as the requirement it is, the phase boundary stated plainly
  (explicit engine phase-1, scheduling **Next**), the AD-31 cookie-hardening companion facts recorded so
  a reader does not go looking elsewhere, and a close naming all three enforcing test modules.

**Departures from the spec, and why.**

1. *Four event names rather than two.* Task 2 asks for "one `structlog` event per pruned kind with the
   deleted row count". A `--dry-run` that emitted the same event name as a real prune would poison exactly
   the signal the event exists to provide, so the mode is carried in the name and the count in the
   payload. Still one event per kind per invocation.
2. *No fresh settings import in `test_session_settings.py`.* Task 5 says to go through
   `tests/settings_import.py` "where a test needs a freshly imported settings module". None here does:
   the source assertions read text, and the one resolved-value assertion is deliberately about the
   *materialised* setting, which `django.conf.settings` already holds. Importing four settings modules to
   answer it would reconfigure structlog for the process to learn nothing extra.
3. *The promoted functions are imported under their old private names.* Task 5 says to refactor "without
   changing a single assertion", and four cases assign a local `regions`. Aliasing on import is what keeps
   those bodies byte-identical; renaming the locals would have been the change the task forbids.
4. *One extra assertion in the integration module.* `--dry-run`'s counts are compared against the counts
   the *real* run then reports, not merely asserted non-zero. A rehearsal whose numbers differ from the
   run it rehearses is worse than no rehearsal, and nothing else would have caught it.

**Residual risks and things recorded rather than fixed.**

- **The "outside every region" assertion is currently unfired.** `base.py` carries no `# feature:` markers,
  so `test_the_session_engine_assignment_is_enclosed_by_no_feature_region` is green over a file with
  nothing to enclose it. It arms itself the day **Epic 7** places the `redis` region in that file, with no
  edit -- which is the same shape as Story 5.5's Dockerfile assertion arming on 5.6. The vacuity guard is
  what keeps it honest until then, and it will need revisiting once `base.py` has markers of its own: at
  that point the guard can read `base.py` itself and `MARKER_BEARING_MODULE` can go.
- **`tests/feature_regions.py` carries an unfulfilled AD-2 obligation.** `accelerator.toml` does not exist
  yet, so this new path is `machinery` by default and must be listed explicitly when **Epic 7** authors
  that file -- AD-2's input reconciliation fails a path claimed by no disposition. Same obligation
  `tests/dockerfile.py`, `tests/pixi_manifest.py`, `Dockerfile` and the two 5.6 test modules already
  carry. `tests/unit/test_session_settings.py` and `tests/integration/test_prune_command.py` are `core`
  by AD-29's reasoning (they cover `src/django_service/` and an unregioned part of `base.py`), which the
  modules' own docstrings state.
- **The pixi `prune` task is not asserted to be outside the `# feature:celery` region.**
  `test_the_celery_process_tasks_sit_inside_a_marker_pair` bounds that region positionally and would fail
  if the closing marker moved down over `prune`, so the property is protected in practice -- but it is
  protected as a side effect of a case about `worker` and `beat`, not by an assertion naming the admin
  process. Recorded rather than added, because the natural home for it is Epic 8's per-combination
  materialization gate, where "the `prune` task survives in all six" is directly checkable.
- **`FR-44`'s scheduling half is untouched, deliberately.** No cron expression, no interval, no
  `PeriodicTask` row, no `CELERY_BEAT_SCHEDULE` key. `docs/deployment.md` says so in the operator's own
  terms.
- **AD-31's other half remains Epic 2's.** `SOCIALACCOUNT_PROVIDERS` from the environment and retiring
  `src/django_service/contrib/sites/migrations/0003_set_site_domain_and_name.py` were not touched; that
  migration still exists.

**What could not be verified, and why.**

- **Behaviour of the command as a *scheduled* job on a platform.** Nothing in this repository starts a
  component on the target platform (the SC-3 boundary Epic 5 does not cross), so `pixi run prune` was
  verified as a `call_command` dispatch and as a declared task, not as a Kubernetes CronJob or equivalent.
- **The gate's own Linux amd64 runner.** Everything ran on macOS/arm64. The PostgreSQL 17 leg was run
  against `postgres:17` in Docker, which is the same server image CI uses, so the sqlite/PostgreSQL parity
  risk the project memory records is closed; the runner architecture is not otherwise exercised here.
- **Concurrency with live serving traffic.** The command is *argued* safe beside traffic -- delete by
  expiry predicate over an indexed column, no lock, no `TRUNCATE` -- and the argument is sound, but no
  test runs it against a component serving requests. `transaction=True` would have been needed to try, and
  it truncates the tables the group-provisioning migration seeds.

### File List

**New**

- `src/django_service/users/management/__init__.py`
- `src/django_service/users/management/commands/__init__.py`
- `src/django_service/users/management/commands/prune_expired_state.py`
- `tests/feature_regions.py`
- `tests/unit/test_session_settings.py`
- `tests/integration/test_prune_command.py`

**Modified**

- `src/config/settings/base.py` — explicit `SESSION_ENGINE` in the `# SECURITY` block.
- `pixi.toml` — the `prune` task, with no `env`, outside the `# feature:celery` region.
- `docs/deployment.md` — new `## Session and epoch pruning` section.
- `tests/unit/startup/test_feature_scoped_refusals.py` — imports the promoted parser; four private
  definitions and one import deleted. No assertion changed.
- `tests/unit/test_payload_properties.py` — session case docstring corrected, `global_settings` fallback
  replaced by a presence assertion, module docstring bullet re-pointed.
- `tests/unit/test_process_model.py` — the admin-process forward direction added; the stale "Deliberately
  not asserted" paragraph rewritten.

**Read only, unchanged**

- `component.toml` — `[[admin_processes]]` `prune` already present at `:184-187`; verified, not edited.
- `mkdocs.yml` — `deployment.md` already in `nav` at line 39; verified, not edited.
- `pyproject.toml` — `[tool.coverage.run] omit` untouched (AD-20).
- `src/django_service/users/models.py`, `src/config/authorization/mapper.py`,
  `src/config/settings/{local,production,test}.py`.

## Review Triage Log

### 2026-08-29 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 9: (high 0, medium 8, low 1)
- defer: 2: (high 0, medium 2, low 0)
- reject: 5: (high 0, medium 0, low 5)
- addressed_findings:
  - `[medium]` `[patch]` The redis/LocMem combination count was inverted in every new rationale block — `base.py`, `docs/deployment.md` and `test_session_settings.py` said a cache-backed engine would be per-replica in "the four LocMem combinations". Redis is present in four of six and absent in **two**; the four-of-six claim is true only of celery. Corrected to *two* at the four redis-scoped sites, and the three sites making a generic claim about any region were rewritten to carry no count at all ("removed from every component that did not select that region's feature"). The three celery-scoped "four"s were verified correct and left alone.
  - `[medium]` `[patch]` The epoch cutoff ignored `OIDC_LEEWAY_SECONDS`, so under a non-zero leeway the pruner deleted the epoch row inside the window in which the Bearer path still *accepts* the token — the exact "removed early re-syncs a live credential" outcome the command's own docstring argues against, plus loss of AD-10's jti-held-by-another-identity guard for that window. Added `_epoch_cutoff()` (`now - leeway`, clamped at zero), read off `django.conf.settings` because AD-4 forbids `django_service` importing `config`. Session cutoff deliberately unchanged: `expire_date` derives from no token claim. New case `test_an_epoch_expiring_inside_the_leeway_window_survives`.
  - `[medium]` `[patch]` The steady-state path — every scheduled run after the first — was never executed. `_prune`'s `per_label.get(label, 0)` fallback and the "a second run removes nothing and says so" claim in both the docs and the docstring were unverified; Django returns `(0, {})` for an empty delete, so tightening that `.get` to `per_label[label]` would `KeyError` on every steady-state run with the suite green. Added `test_a_second_run_removes_nothing_and_reports_zero`.
  - `[medium]` `[patch]` Both reported counts were `1`, so a copy-paste (`epochs=sessions`) passed every case. The seed is now asymmetric — two expired sessions against one expired epoch — and the assertions name the exact numbers.
  - `[medium]` `[patch]` The secrecy assertion checked only the three `jti` literals against the captured event stream, while `docs/deployment.md` promises no session key either. Added both expired session keys and the live one to the secrets tuple, and extended the scan to the command's stdout — the second output channel the module itself asserts is non-empty and nothing was checking.
  - `[medium]` `[patch]` The `prune` task's *command string* was pinned by nothing: the new forward-direction case asserted only that a task of that name exists, and the integration test dispatched its own literal. A typo in the pixi `cmd` passed the whole gate and left `pixi run prune` emitting `Unknown command`. Added `test_every_declared_admin_process_runs_a_management_command_django_has` (resolves the cmd, `shlex.split`s it, checks the token against `get_commands()` — `test_release_stage.py`'s technique) and `test_every_declared_admin_process_task_is_declared_in_the_root_task_table` (a task declared only under `[feature.dev.tasks]` is one a deployed component does not have).
  - `[medium]` `[patch]` Two vacuity gaps in `test_session_settings.py`. Its own comment claimed a fourth settings module "should fail this file's vacuity guard" and nothing enumerated the directory, so a future `staging.py` setting a cache engine would ship green — the guard now globs `SETTINGS_DIR` and asserts set equality. And the AD-24 enclosure case passed on a *malformed* pair, because `regions()` is deliberately lenient and `base.py` is absent from `MARKER_BEARING_PATHS`; marker balance is now asserted in this module before the enclosure result is trusted, and the docstring's delegation claim — which named a test that does not read this file — was corrected.
  - `[low]` `[patch]` `_assigned_strings` handled only `ast.Assign` while `_assignment_lines` handled `ast.AnnAssign` too, so a correct `SESSION_ENGINE: str = "..."` would have failed with a message claiming the file sets it to `[]`. Both helpers now agree.
  - `[medium]` `[patch]` Four operator-facing corrections. "Nothing is locked" was false — both legs take row locks for the statement's duration — and is now stated accurately with a `statement_timeout` warning for a first run against a neglected table. The "no silent half-prune" claim was replaced by what actually happens: autocommit, no transaction, the completed leg's deletion stands and has already been reported, non-zero exit, re-run safe because idempotent. The NULL-`expires_at` residue is recorded rather than implied away. And the section now names the environment the job needs and the `Unknown command: 'prune_expired_state'` failure mode that a misconfigured job reports instead of the real cause (reproduced, not inferred).

## Auto Run Result

Status: done

### Summary

`SESSION_ENGINE` is now set explicitly in `src/config/settings/base.py` to the database-backed
engine, outside every AD-24 feature region, and set in no other settings module — so session
behaviour is identical in all six combinations and cannot become a property of the Redis toggle.
Expired session rows and expired AD-10 `CredentialEpoch` records are pruned by one declared admin
process, `pixi run prune`, which is a Django management command rather than a Celery task because
background task processing exists in only two of the six combinations. The component declares the
process and no schedule for it; FR-44's scheduling half stays with the deployment repository.

### Files changed

**New**

- `src/django_service/users/management/{__init__.py,commands/__init__.py}` — the app's first management package.
- `src/django_service/users/management/commands/prune_expired_state.py` — prunes both kinds in one invocation on an expiry predicate, with `--dry-run`, a leeway-aware epoch cutoff, and one structlog event per kind carrying the row count.
- `tests/feature_regions.py` — the AD-24 marker parser, promoted out of `test_feature_scoped_refusals.py` rather than copied.
- `tests/unit/test_session_settings.py` — explicit-in-`base.py`, absent-elsewhere, enclosed-by-no-region, with a directory-enumerating vacuity guard and a marker-balance check.
- `tests/integration/test_prune_command.py` — both legs, both modes, the null-expiry row, the leeway window and the steady state, against PostgreSQL.

**Modified**

- `src/config/settings/base.py` — the explicit `SESSION_ENGINE` assignment and its rationale.
- `pixi.toml` — the `prune` task, no `env` table, outside the `feature:celery` region.
- `docs/deployment.md` — new `## Session and epoch pruning`; no existing heading renamed.
- `tests/unit/startup/test_feature_scoped_refusals.py` — imports the promoted parser; no assertion changed.
- `tests/unit/test_payload_properties.py` — the session-store case's docstring corrected and its `global_settings` fallback tightened into a presence assertion.
- `tests/unit/test_process_model.py` — the admin-process forward direction, in three cases (existence, a real management command, declared in the root task table), and the stale "deliberately not asserted" paragraph rewritten.

**Verified, unchanged:** `component.toml` (`[[admin_processes]] prune` already present), `mkdocs.yml` (nav already registers `deployment.md`), `pyproject.toml` (`[tool.coverage.run] omit` untouched).

### Review findings

9 patches applied (8 medium, 1 low), 2 deferred, 5 rejected. No intent gaps and no spec-level defects, so no loopback was taken. See `## Review Triage Log`.

### Verification performed

| Command | Result |
|---|---|
| `pixi run ci` against PostgreSQL 17 (`postgres:17` container) | **exit 0** — 1527 passed, coverage **97.04 %** (floor 90) |
| `pixi run ci` — pre-patch run, same conditions | exit 0 — 1523 passed, 97.03 % |
| `pixi run docs` (`mkdocs build --strict`) | exit 0, no warnings |
| `prune_expired_state.py` coverage | 40 statements, 0 missed, **100 %** |
| `pixi task list` | `prune` present |
| PostgreSQL genuinely used | `test_gatedb` created inside the container; the gate was not silently on SQLite |

The gate was run against a real PostgreSQL 17 both before and after the review patches. Every
review patch was additionally negative-verified by the patching session — the defect reinjected,
the intended case observed failing, the fix restored.

### Residual risks

- **The enclosure assertion is armed but unfired.** `base.py` carries no `# feature:` markers today, so the outside-every-region case runs over a file with nothing to enclose the line. The marker-balance check and the vacuity guard are what keep it honest until Epic 7 places the `redis` region there, at which point it arms itself with no edit.
- **`tests/feature_regions.py` carries an unfulfilled AD-2 obligation** — `accelerator.toml` does not exist, so this path must be listed explicitly when Epic 7 authors it, alongside `tests/pixi_manifest.py`, `tests/dockerfile.py` and Story 5.6's two modules.
- **Two items deferred rather than fixed** — the unbatched first prune against a neglected table, and the NULL-`expires_at` epoch rows that nothing ever removes. Both are recorded in `deferred-work.md` and both are named honestly in `docs/deployment.md`.
- **FR-44's scheduling half is untouched by design.** No cron, no interval, no `PeriodicTask`, no `CELERY_BEAT_SCHEDULE`.
- **Not verified:** the command running as a scheduled job on the target platform (the SC-3 boundary this repository does not cross), the gate's own Linux amd64 runner, and concurrency against live serving traffic — the safety argument is an expiry predicate over an indexed column with no table lock, which is reasoned rather than load-tested.
