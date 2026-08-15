# Story 4.1: The refusal contract has one home and two evaluation stages

Status: ready-for-dev

## Story

As a platform engineer,
I want both refusal stages in one module, evaluated independently of which settings module loaded,
so that the guard cannot be skipped by the very failure it exists to catch.

## Acceptance Criteria

**Traceability:** FR-12 · AD-13, AD-26 · NFR-1 · SC-5

1. **Given** the refusal contract
   **When** it is located
   **Then** it is one module at `src/config/startup/` containing both stages and the FR-17 allowlist
   **And** it is not split across the deployed settings module

2. **Given** stage 1
   **When** a settings module is imported
   **Then** stage 1 is invoked as the last statement of that settings module
   **And** every settings module invokes it, so none can skip it by not being loaded

3. **Given** stage 2
   **When** a serving process starts
   **Then** it is invoked by the `AppConfig.ready()` of one named immovable-core application inside `django_service`
   **And** it fires under gunicorn and uvicorn as well as under management commands
   **And** a test asserts it fires through a served request path, not only through `manage.py`

4. **Given** `INSTALLED_APPS` ordering
   **When** the gate runs
   **Then** a test asserts that no adopted application precedes the stage-2 owner

5. **Given** the decision *am I deployed?*
   **When** it is made
   **Then** it is read from the environment and never inferred from which settings module loaded
   **And** absent or unrecognized means deployed

6. **Given** a deployed environment with its settings module pointed at the local module
   **When** the component starts
   **Then** it refuses
   **And** a test constructs exactly that state and asserts the refusal

7. **Given** the nine checks
   **When** they run
   **Then** they perform no network call and no query beyond migration state
   **And** their cost is irrelevant to startup time

## Tasks / Subtasks

- [ ] Task 1 — Create the single module `src/config/startup/` and its public entry points (AC: #1, #5)
  - [ ] Create `src/config/startup/__init__.py` exporting exactly four public names: `run_stage_one`, `run_stage_two`, `is_deployed`, `is_serving_process`. Nothing else is public; every condition predicate is imported through these two entry points.
  - [ ] Create `src/config/startup/locality.py` with `is_deployed() -> bool` reading `COMPONENT_RUNTIME` from `os.environ` and returning `False` **only** when the value is exactly `"local"`; every other value, including absent, empty and unrecognized, returns `True` (AD-13, fail closed).
  - [ ] In the same file add `is_serving_process() -> bool` reading `COMPONENT_PROCESS` and returning `True` only when the value is one of `{"web", "worker", "beat"}`; absent or unrecognized returns `False` (AD-13, fail open).
  - [ ] Read both variables through `os.environ` directly, not through `config.settings.base.env` — `src/config/startup/` must not import any settings module, because stage 1 is called *from* settings and a back-import is a circular import at settings-import time.
  - [ ] Create `src/config/startup/stage_one.py`, `src/config/startup/stage_two.py` and `src/config/startup/allowlist.py` as empty-but-typed skeletons that Stories 4.2, 4.3, 4.4 and 4.6 fill. This story delivers the frame, the locality decision, the two invocation points and the ordering gate test; it delivers no condition.

- [ ] Task 2 — Define the stage-1 entry point and its calling convention (AC: #1, #2, #7)
  - [ ] `run_stage_one(settings_module: ModuleType | None = None, /, **_: object) -> None` in `src/config/startup/stage_one.py`, re-exported from `__init__.py`. It takes the *namespace it is validating* rather than reading `django.conf.settings`, because `django.conf.settings` is not yet populated while a settings module is still executing.
  - [ ] Concrete convention the condition stories build on: each settings module calls `run_stage_one(sys.modules[__name__])` as its final statement, and `run_stage_one` reads candidate names off that module object with `getattr(module, name, default)`.
  - [ ] `run_stage_one` returns immediately when `is_deployed()` is `False`. Every condition is deployed-only.
  - [ ] Raise `django.core.exceptions.ImproperlyConfigured` and nothing else. Never `warnings.warn`, never a log-and-continue branch (CG-3).

- [ ] Task 3 — Invoke stage 1 as the last statement of every leaf settings module (AC: #2, #6)
  - [ ] Append to `src/config/settings/local.py`, `src/config/settings/production.py` and `src/config/settings/test.py`, as the last statement of each file:
    `run_stage_one(sys.modules[__name__])`, with `import sys` and `from config.startup import run_stage_one` at the top of the file.
  - [ ] Do **not** add the call to `src/config/settings/base.py`. `base.py` is never named by `DJANGO_SETTINGS_MODULE`; it is a composition fragment consumed by `from .base import *`. A call there would fire *before* the leaf module finishes composing, and `base.py` today sets `ModelBackend`, a non-empty `ACCOUNT_LOGIN_METHODS`, `DJANGO_ADMIN_FORCE_ALLAUTH=False` and `rest_framework.authtoken` — so a stage-1 call in `base.py` would refuse in every combination and destroy the after-composition property AD-26 exists to guarantee.
  - [ ] Add a gate test that enumerates `src/config/settings/*.py`, excludes `__init__.py` and `base.py`, and asserts each remaining file's last non-blank, non-comment source line is the `run_stage_one(...)` call. This is what makes "no settings module can skip it by not being loaded" mechanical rather than reviewed.
  - [ ] Add the paired gate test asserting `base.py` does **not** call `run_stage_one`, so the exclusion cannot be reverted silently.

- [ ] Task 4 — Define the stage-2 entry point and give it its named owner (AC: #1, #3, #4)
  - [ ] `run_stage_two() -> None` in `src/config/startup/stage_two.py`, re-exported from `__init__.py`. It returns immediately when `is_deployed()` is `False`. Conditions that are serving-process-only additionally gate on `is_serving_process()`; Story 4.3 owns which.
  - [ ] The named immovable-core owner is `django_service.users`. Call `run_stage_two()` from `UsersConfig.ready()` in `src/django_service/users/apps.py:9-12`, replacing the empty docstring-only body. Add a module constant `STAGE_TWO_OWNER_APP_LABEL = "users"` in `src/config/startup/stage_two.py` — one declaration site, moved into `accelerator.toml` in Epic 7 (AD-26).
  - [ ] Do not create a new app for this. `django_service` is `core` in its entirety (AD-29) and `django_service.users` is already an immovable-core app; a second app is surface with no requirement behind it.
  - [ ] Add the AC #4 gate test: resolve `django.apps.apps.get_app_configs()` in `INSTALLED_APPS` order and assert that the index of the app whose `label == STAGE_TWO_OWNER_APP_LABEL` is strictly less than the index of every app named in the `component.toml` adopted-app list. `component.toml` does not exist until Epic 5; until it does, assert the weaker invariant that the stage-2 owner appears in `LOCAL_APPS` and that `LOCAL_APPS` is the last segment of `INSTALLED_APPS` in `src/config/settings/base.py:118-123`, and leave a comment naming Epic 5's `component.toml` as the eventual source of the adopted-app list.

- [ ] Task 5 — Prove stage 2 fires through a served request path (AC: #3)
  - [ ] Add an integration test that drives a request through the ASGI application (`config.asgi:application`) rather than through `manage.py`, and asserts the stage-2 hook ran. Assert on an observable side effect of `ready()` — e.g. a module-level `_STAGE_TWO_RAN` sentinel in `src/config/startup/stage_two.py` set at the end of `run_stage_two()` — not by mocking `run_stage_two` itself.
  - [ ] Assert the same for the management-command path by invoking `django.core.management.call_command("check")` in a separate test.
  - [ ] `src/config/asgi.py` and `src/config/wsgi.py` are in the coverage `omit` list at `pyproject.toml:165-167`; this test asserts behaviour reached *through* them, so it does not require removing either omit entry.

- [ ] Task 6 — The settings-module escape route refuses (AC: #5, #6)
  - [ ] Implement, in `src/config/startup/stage_one.py`, the FR-12 escape-route condition: when `is_deployed()` is `True` and the settings module passed to `run_stage_one` is `config.settings.local`, raise `ImproperlyConfigured` naming the module. Compare the module object's `__name__` obtained from the passed module — do not read `os.environ["DJANGO_SETTINGS_MODULE"]`, which a process can set to one value and import another.
  - [ ] The message must state the resolution: set `COMPONENT_RUNTIME=local` for local work, or point `DJANGO_SETTINGS_MODULE` at `config.settings.production` for a deployed one.
  - [ ] Add the AC #6 test: `monkeypatch.delenv("COMPONENT_RUNTIME", raising=False)`, import `config.settings.local` fresh, assert `ImproperlyConfigured`.

- [ ] Task 7 — Assert NFR-1's cost property (AC: #7)
  - [ ] Add a test that runs `run_stage_one` and `run_stage_two` against a valid deployed configuration with `socket.socket` patched to raise, asserting no network call is attempted.
  - [ ] Add a test using `django.test.utils.CaptureQueriesContext` asserting that the only queries `run_stage_two` issues are the migration-state read and the designated-group existence read (Story 4.3 adds the latter); zero queries from `run_stage_one`.
  - [ ] Do not add a wall-clock timing assertion — NFR-1's `[ASSUMPTION]` records that no platform startup-time budget exists, so there is no threshold to assert against.

- [ ] Task 8 — Tests (AC: all)
  - [ ] `tests/unit/config/startup/test_locality.py` — the fail-closed and fail-open truth tables.
  - [ ] `tests/unit/config/startup/test_module_shape.py` — AC #1 (one module, the four public names), AC #2 (the last-statement gate test and its `base.py` counterpart).
  - [ ] `tests/unit/config/startup/test_stage_one_escape_route.py` — AC #6.
  - [ ] `tests/unit/config/startup/test_installed_apps_ordering.py` — AC #4.
  - [ ] `tests/integration/config/startup/test_stage_two_fires.py` — AC #3, `@pytest.mark.integration`.
  - [ ] `tests/unit/config/startup/test_no_network_no_queries.py` — AC #7.

## Dev Notes

### Architecture Constraints

- **AD-26 (binding rule, verbatim):** "The refusal contract is one module, `src/config/startup/`, containing both stages and the FR-17 allowlist. **Stage 1** is invoked as the **last statement of every settings module**, which places it after the AD-8 composition step by construction and is why AD-9's iteration over every configured database is reachable. **Stage 2** is owned by the `AppConfig.ready()` of one named immovable-core app in `django_service`, declared in `accelerator.toml`; no adopted app may precede it in `INSTALLED_APPS`, and a gate test asserts that ordering. **Predicates resolve objects, never strings.**"
  **Prevents:** "the product's highest-consequence surface being split across two modules by two builders who both satisfy FR-12; stage 1 running before composition and never seeing a contributed database; an allowlist maintained apart from the conditions it backstops."
- **AD-13 (binding rule):** "`COMPONENT_RUNTIME=local` is set in the `env` of each local pixi task. `web`, `worker` and `beat` set no runtime and inherit *deployed*; each sets `COMPONENT_PROCESS`. **No `COMPONENT_*` variable may appear in `[activation.env]`** … Locality fails closed: absent or unrecognized means deployed. Process type fails open: absent means not a serving process, because failing it closed would produce exactly that deadlock."
  **Prevents:** "the declaration travelling into the deployed image and inverting the fail-closed property; the entire test suite refusing to start on the day the refusal contract lands; `sys.argv` sniffing." **`sys.argv` sniffing is forbidden.** Do not inspect `sys.argv`, `sys.modules`, or the process name to decide locality or process type.
- **NFR-1:** "the nine checks are settings and URL-configuration inspection with no network call and no query beyond the migration state, so their cost is irrelevant to startup time."
- **CG-3:** "Do not soften a refusal into a warning. A refusal that logs and continues makes deployment smoother and puts local credentials into production."
- **AD-29:** no `feature:*` disposition may apply to any path inside `src/django_service/` — it is `core` in its entirety. The stage-2 owner therefore travels in all twelve combinations by construction.
- **AD-24 forbids** conditional imports, settings-module inheritance and `try/except ImportError` as sub-file removal mechanisms. `src/config/startup/` must not use any of them for feature scoping; Story 4.4 uses paired `feature:<name>` / `/feature:<name>` line comments instead.
- **AD-1:** every declaration has exactly one site. `STAGE_TWO_OWNER_APP_LABEL` and the allowlist are single constants here, migrating into `accelerator.toml` in Epic 7 without changing meaning.
- **R-3 (carry, do not attempt to fix):** "A serving process started outside `pixi run web` does not fire the migrations refusal. The price of AD-13's fail-open process type, taken because failing it closed deadlocks the release stage." Do not add a fallback that infers serving-process status when `COMPONENT_PROCESS` is absent.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/startup/__init__.py` | NEW | Public surface: `run_stage_one`, `run_stage_two`, `is_deployed`, `is_serving_process`. |
| `src/config/startup/locality.py` | NEW | `COMPONENT_RUNTIME` fail-closed and `COMPONENT_PROCESS` fail-open readers. |
| `src/config/startup/stage_one.py` | NEW | Stage-1 entry point, the FR-12 escape-route condition, `_STAGE_ONE` skeleton for Stories 4.2/4.4. |
| `src/config/startup/stage_two.py` | NEW | Stage-2 entry point, `STAGE_TWO_OWNER_APP_LABEL`, `_STAGE_TWO_RAN` sentinel, skeleton for Story 4.3. |
| `src/config/startup/allowlist.py` | NEW | Empty declaration module; Story 4.6 fills it. Created here so AC #1's "one module containing both stages and the allowlist" is true from the start. |
| `src/config/settings/local.py` | UPDATE | Today: `DEBUG=True`, dev SECRET_KEY, LocMemCache, console email, whitenoise prepended to `INSTALLED_APPS`, the `DEBUG_APPS` block (`:51-74`), eager Celery (`:78-80`). Ends at line 82. **Change:** add the `run_stage_one(sys.modules[__name__])` call as the new last statement. **Preserve:** the `DEBUG_APPS` env gate and the eager-Celery block — Story 4.4 marks the latter, this story does not. |
| `src/config/settings/production.py` | UPDATE | Today: the sqlite refusal at `:26-28` (confirmed present, unchanged), Redis cache, security headers, anymail, `LOGGING`, `SPECTACULAR_SETTINGS["SERVERS"]`. Ends at line 161 (a trailing comment banner). **Change:** add the stage-1 call as the last statement, after the banner. **Preserve:** `:26-28` verbatim — Story 4.2 designates it as condition 1's mechanism. |
| `src/config/settings/test.py` | UPDATE | Today: console logging at WARNING, test SECRET_KEY, `TEST_RUNNER`, MD5 hasher, locmem email, `TEMPLATES[0]["OPTIONS"]["debug"]=True` (required by `django_coverage_plugin`, `pyproject.toml:173`). **Change:** add the stage-1 call as the last statement. **Preserve:** the `TEMPLATES` debug line — removing it silently zeroes template coverage and breaks AD-20. |
| `src/django_service/users/apps.py` | UPDATE | Today: `UsersConfig(name="django_service.users", verbose_name=_("Users"))` with an empty `ready()` carrying only a docstring (`:9-12`). **Change:** `ready()` calls `run_stage_two()`. **Preserve:** `name` and `verbose_name`; `name` is the `AUTH_USER_MODEL="users.User"` app and changing it breaks migrations. |

**Verified line references.** `production.py:26-28` is exactly the sqlite refusal (`if DATABASES["default"]["ENGINE"].endswith("sqlite3"): … raise ImproperlyConfigured(msg)`) — the epic's citation holds. `src/config/settings/base.py:118-123` is `LOCAL_APPS` and the `INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS` composition — holds.

**Does not exist yet and is not created here:** `accelerator.toml` (Epic 7), `component.toml` (Epic 5), `src/config/authorization/` (Epic 2), the local sign-in module (Epic 3, Story 3.4).

### Testing Requirements

- New test packages `tests/unit/config/startup/` and `tests/integration/config/startup/`, each with `__init__.py`, mirroring `src/config/startup/` per the spine's Test-location convention: "Accelerator and base tests live under `tests/`, mirroring `src/`, and carry the disposition of what they cover." Everything in this story is `core`.
- Every integration test carries `@pytest.mark.integration` (declared at `pyproject.toml:155-157`).
- Follow the fresh-import fixture pattern already established at `tests/unit/test_settings.py:24-30`: evict `config.settings.base` alongside the target module from `sys.modules` before and after each test, or the `from .base import *` reuses the already-imported copy and module-level environment reads are not re-evaluated. Extend that eviction list to include `config.settings.test`.
- Locality tests must `monkeypatch.setenv` / `monkeypatch.delenv` rather than mutating `os.environ` directly, so state is left as found.
- AD-20 coverage floor: ninety percent including templates, `COVERAGE_CORE=ctrace` in force (set at `pixi.toml:145-151`). The `omit`/`exclude` list is a closed carrier-declared surface — **do not add `src/config/startup/` to `[tool.coverage.run] omit` in `pyproject.toml:160-168`** under any circumstance.
- Run with `pixi run test`, `pixi run test-integration`, and `pixi run ci` (`pixi.toml:206`, `depends-on = ["test-cov", "lint", "typecheck", "build"]`). Done means `pixi run ci` exits 0.

#### Project Structure Notes

The spine's Structural Seed places `startup/` under `src/config/` beside `settings/`, `observability/` and `authorization/`, annotated "both refusal stages + the FR-17 allowlist (AD-26)". That directory does not exist in the repository today; this story creates it, matching the Consistency Conventions rule that "cross-cutting concerns with several independent consumers and no natural owner live under `src/config/<concern>/`, as `observability/` already does and `authorization/` and `startup/` will."

**Two upstream dependencies this story assumes, both flagged rather than worked around:**

1. **`COMPONENT_RUNTIME=local` is not set anywhere in `pixi.toml` today.** Story 3.1 adds it to each local pixi task's `env` — including `test`, `test-integration` and `test-cov` (`pixi.toml:194-196`). Until it lands, adding the stage-1 call to `test.py` makes the entire suite refuse at collection, which is precisely the failure AD-13's "Prevents" clause names. If Story 3.1 has not landed when this story is implemented, add `env = { COMPONENT_RUNTIME = "local" }` to the three test tasks as part of this story and note it in the Completion Notes; do **not** add `COMPONENT_RUNTIME` to `[activation.env]` (`pixi.toml:145`), which AD-13 forbids outright.
2. **`base.py` currently configures four of the five stage-1 forbidden states.** `AUTHENTICATION_BACKENDS` contains `ModelBackend` (`:133-136`), `ACCOUNT_LOGIN_METHODS = {"username"}` is non-empty (`:340`), `DJANGO_ADMIN_FORCE_ALLAUTH` defaults `False` (`:271`), and `rest_framework.authtoken` plus `TokenAuthentication` are present (`:112`, `:357-364`). Epic 2 Story 2.8 removes that surface. This story delivers no condition, so it does not trip on them; Story 4.2 does, and states the same dependency.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Structural Seed]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-3
- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.1]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.1] — the `COMPONENT_RUNTIME` declaration this story enforces against
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-12]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#NFR-1]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#CG-3]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
