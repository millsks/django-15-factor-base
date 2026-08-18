---
baseline_revision: 8ce0121
review_loop_iteration: 0
status: done
followup_review_recommended: false
warnings: [oversized]
---

# Story 4.1: The refusal contract has one home and two evaluation stages

Status: done

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
   **When** a leaf settings module is imported
   **Then** stage 1 is invoked as the last statement of that module
   **And** every leaf settings module — `local.py`, `production.py`, `test.py` — invokes it, so none can skip it by not being loaded
   **And** `base.py` does **not** invoke it, and a paired gate test asserts both halves (AD-26)

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

- [x] Task 1 — Create the single module `src/config/startup/` and its public entry points (AC: #1, #5)
  - [x] Create `src/config/startup/__init__.py` exporting exactly four public names: `run_stage_one`, `run_stage_two`, `is_deployed`, `is_serving_process`. Nothing else is public; every condition predicate is imported through these two entry points.
  - [x] **Do not create `src/config/startup/locality.py`.** Story 3.1 already delivered `src/config/locality.py` as the single declaration site for the `COMPONENT_*` contract, and its spec states the rule directly: "Epic 4's `src/config/startup/` imports this module rather than re-reading `os.environ`. Do not create a second reader." A duplicate reader violates AD-1 and gives the two `COMPONENT_*` names two spellings that can drift apart.
  - [x] Re-export the two names from the delivered module instead: `from config.locality import is_deployed, is_serving_process` in `src/config/startup/__init__.py`. Both already have exactly the required semantics — `is_deployed()` returns `False` only when `COMPONENT_RUNTIME` is `"local"` after strip/lower (fail closed), and `is_serving_process()` returns `True` only for a member of `SERVING_PROCESSES = {"web", "worker", "beat"}` (fail open). `config.locality` also exposes `is_local()`, `component_process()`, `RUNTIME_ENV_VAR`, `PROCESS_ENV_VAR`, `LOCAL` and `SERVING_PROCESSES`; use those constants rather than re-spelling any name as a literal.
  - [x] The import constraint this story cites is already satisfied and must stay satisfied: `config/locality.py` reads `os.environ` directly and imports nothing but `os` and `typing`, so importing it from `src/config/startup/` introduces no settings back-import and no circular import at settings-import time. Verify that remains true rather than assuming it.
  - [x] Create `src/config/startup/stage_one.py`, `src/config/startup/stage_two.py` and `src/config/startup/allowlist.py` as empty-but-typed skeletons that Stories 4.2, 4.3, 4.4 and 4.6 fill. This story delivers the frame, the locality decision, the two invocation points and the ordering gate test; it delivers no condition.

- [x] Task 2 — Define the stage-1 entry point and its calling convention (AC: #1, #2, #7)
  - [x] `run_stage_one(settings_module: ModuleType, /) -> None` in `src/config/startup/stage_one.py`, re-exported from `__init__.py`. It takes the *namespace it is validating* rather than reading `django.conf.settings`, because `django.conf.settings` is not yet populated while a settings module is still executing. The parameter is required and positional-only: every call site passes it, and the originally specified `| None = None, /, **_: object` form would silently swallow a future condition's misrouted keyword rather than failing on it.
  - [x] Concrete convention the condition stories build on: each settings module calls `run_stage_one(sys.modules[__name__])` as its final statement, and `run_stage_one` reads candidate names off that module object with `getattr(module, name, default)`.
  - [x] `run_stage_one` returns immediately when `is_deployed()` is `False`. Every condition is deployed-only.
  - [x] Raise `django.core.exceptions.ImproperlyConfigured` and nothing else. Never `warnings.warn`, never a log-and-continue branch (CG-3).

- [x] Task 3 — Invoke stage 1 as the last statement of every leaf settings module (AC: #2, #6)
  - [x] Append to `src/config/settings/local.py`, `src/config/settings/production.py` and `src/config/settings/test.py`, as the last statement of each file:
    `run_stage_one(sys.modules[__name__])`, with `import sys` and `from config.startup import run_stage_one` at the top of the file.
  - [x] Do **not** add the call to `src/config/settings/base.py`. `base.py` is never named by `DJANGO_SETTINGS_MODULE`; it is a composition fragment consumed by `from .base import *`. A call there would fire *before* the leaf module finishes composing, and `base.py` today sets `ModelBackend`, a non-empty `ACCOUNT_LOGIN_METHODS`, `DJANGO_ADMIN_FORCE_ALLAUTH=False` and `rest_framework.authtoken` — so a stage-1 call in `base.py` would refuse in every combination and destroy the after-composition property AD-26 exists to guarantee.
  - [x] Add a gate test that enumerates `src/config/settings/*.py`, excludes `__init__.py` and `base.py`, and asserts each remaining file's **last top-level AST statement** (`ast.parse(...).body[-1]`) is an `ast.Expr` wrapping a call to the `Name` `run_stage_one`. Parse the AST rather than the last non-blank source line: `production.py` ends with a trailing comment banner and `local.py` may grow one, and a source-line check would either fail on a comment or have to re-implement comment stripping. Mirror the technique already used at `tests/unit/test_asgi_surface.py:300-332`. This is what makes "no settings module can skip it by not being loaded" mechanical rather than reviewed.
  - [x] Add the paired gate test asserting `base.py` does **not** call `run_stage_one`, so the exclusion cannot be reverted silently.

- [x] Task 4 — Define the stage-2 entry point and give it its named owner (AC: #1, #3, #4)
  - [x] `run_stage_two() -> None` in `src/config/startup/stage_two.py`, re-exported from `__init__.py`. It returns immediately when `is_deployed()` is `False`. Conditions that are serving-process-only additionally gate on `is_serving_process()`; Story 4.3 owns which.
  - [x] The named immovable-core owner is `django_service.users`. Call `run_stage_two()` from `UsersConfig.ready()` in `src/django_service/users/apps.py:9-16`, replacing the body that is a docstring plus a comment today. Preserve the substance of that comment — it records that `ready()` runs inside `django.setup()` and is therefore bound by FR-23 and NFR-1 — since `run_stage_two()` is exactly the thing it constrains. Add a module constant `STAGE_TWO_OWNER_APP_LABEL = "users"` in `src/config/startup/stage_two.py` — one declaration site, moved into `accelerator.toml` in Epic 7 (AD-26).
  - [x] Do not create a new app for this. `django_service` is `core` in its entirety (AD-29) and `django_service.users` is already an immovable-core app; a second app is surface with no requirement behind it.
  - [x] Add the AC #4 gate test: resolve `django.apps.apps.get_app_configs()` in `INSTALLED_APPS` order and assert that the index of the app whose `label == STAGE_TWO_OWNER_APP_LABEL` is strictly less than the index of every app named in the `component.toml` adopted-app list. `component.toml` does not exist until Epic 5; until it does, assert the weaker invariant that the stage-2 owner appears in `LOCAL_APPS` (`src/config/settings/base.py:188-191`) and that `LOCAL_APPS` is the last segment of the `INSTALLED_APPS` composition (`:193`), and leave a comment naming Epic 5's `component.toml` as the eventual source of the adopted-app list.

- [x] Task 5 — Prove stage 2 fires through a served request path (AC: #3)
  - [x] **The assertion must run in a subprocess, not in the pytest process.** pytest-django completes `django.setup()` — and therefore `UsersConfig.ready()` — during collection, before any test body runs, so an in-process sentinel read is already `True` no matter what the invocation point does and asserts nothing. This is the same problem `tests/unit/test_no_network_at_boot.py:20-30` records for boot assertions, and the same remedy applies.
  - [x] Add an integration test that runs a boot probe subprocess (`[sys.executable, "-c", _PROBE_SOURCE, report_path]`, `# noqa: S603`) which: leaves `DJANGO_SETTINGS_MODULE` unset so `src/config/asgi.py:16`'s own `setdefault` is what selects the module, imports `config.asgi` — whose `get_asgi_application()` is what triggers `django.setup()` and the `ready()` hook — drives one request through the resulting `application` callable, and writes a JSON report to the given path. The test asserts the report says the stage-2 hook fired **and** that the request produced a response, so a probe that never actually served cannot report success. Follow `tests/integration/test_import_resolution.py:100-122` for the subprocess environment (`_subprocess_env()`: drop `PYTHONPATH` and `DJANGO_SETTINGS_MODULE`, set `PYTHONSAFEPATH=1`) and its JSON-report-to-a-file convention rather than parsing stdout.
  - [x] The sentinel is a module-level record in `src/config/startup/stage_two.py` read through a **public** helper (e.g. `stage_two_has_run() -> bool`), not a bare `_STAGE_TWO_RAN` name read across module boundaries: ruff `SLF001` is selected and flags `stage_two._STAGE_TWO_RAN`, while importing the name directly would bind a copy of the boolean at import time and never observe the later write. Hold the state in a small module-level mutable record rather than rebinding a module global, because ruff `PLW0603` forbids the `global` statement.
  - [x] Set the record at the **start** of `run_stage_two()`, before the `is_deployed()` early return. What AC #3 asserts is that the invocation point fires under a serving process; every developer and CI path runs local, so a sentinel set after the early return would never be observed and the test would assert nothing.
  - [x] Do not assert this by mocking or patching `run_stage_two` — the thing under test is that `ready()` calls it at all.
  - [x] Assert the same for the management-command path by invoking `django.core.management.call_command("check")` in a separate test. This one is genuinely in-process: it asserts the command path completes with the hook in place, and it is the weaker of the two assertions by design.
  - [x] `src/config/asgi.py` and `src/config/wsgi.py` are in the coverage `omit` list (`[tool.coverage.run] omit`, frozen as `CLOSED_OMIT` at `tests/unit/test_coverage_policy.py:88-94`); this test asserts behaviour reached *through* them, so it does not require removing either omit entry — and must not add one.
  - [x] Coverage note: work a subprocess does is not measured by the parent's coverage run, so the stage-2 body still needs the in-process unit tests below to reach the floor. The subprocess proves the *wiring*; the unit tests cover the *code*.

- [x] Task 6 — The settings-module escape route refuses (AC: #5, #6)
  - [x] Implement, in `src/config/startup/stage_one.py`, the FR-12 escape-route condition: when `is_deployed()` is `True` and the settings module passed to `run_stage_one` is `config.settings.local`, raise `ImproperlyConfigured` naming the module. Compare the module object's `__name__` obtained from the passed module — do not read `os.environ["DJANGO_SETTINGS_MODULE"]`, which a process can set to one value and import another.
  - [x] The message must state the resolution: set `COMPONENT_RUNTIME=local` for local work, or point `DJANGO_SETTINGS_MODULE` at `config.settings.production` for a deployed one.
  - [x] Add the AC #6 test: `monkeypatch.delenv("COMPONENT_RUNTIME", raising=False)`, import `config.settings.local` fresh, assert `ImproperlyConfigured`.

- [x] Task 7 — Assert NFR-1's cost property (AC: #7)
  - [x] Add a test that runs `run_stage_one` and `run_stage_two` against a valid deployed configuration under the delivered network guard, asserting no network call is attempted. Reuse `tests/conftest.py`'s `no_network` fixture (`:136`) — the guard is already written, covers `connect`, `connect_ex`, `create_connection`, `getaddrinfo` and `gethostbyname`, and raises a `BaseException` subclass so a stray `except Exception:` cannot swallow it. Do not hand-patch `socket.socket`.
  - [x] Add a test using `django.test.utils.CaptureQueriesContext` asserting **zero** queries from both stages as this story delivers them. The story delivers no condition that reads the database; the migration-state read arrives with Story 4.3 and the designated-group existence read with it, and each will amend this assertion as it lands. Asserting zero now is what makes those two additions visible instead of absorbed.
  - [x] Do not add a wall-clock timing assertion — NFR-1's `[ASSUMPTION]` records that no platform startup-time budget exists, so there is no threshold to assert against.

- [x] Task 8 — Tests (AC: all)
  - [x] Test packages are `tests/unit/startup/` and `tests/integration/startup/`, each with `__init__.py` (ruff `INP` requires it). **Not** `tests/unit/config/startup/`: the delivered mirror convention drops the `config` segment — `tests/unit/authorization/` and `tests/integration/authorization/` mirror `src/config/authorization/`, and `tests/unit/users/` mirrors `src/django_service/users/`. Adding a `config/` level here would make `startup/` the only package in the suite nested differently from the one it mirrors.
  - [x] **Do not write a locality truth-table test.** Story 3.1 delivered `tests/unit/test_locality.py`, whose eleven tests already cover fail-closed locality, fail-open process type, normalization and call-time reads. A second copy under `startup/` would assert the same behaviour of the same functions and would have to be kept in step by hand.
  - [x] `tests/unit/startup/test_module_shape.py` — AC #1 (one module; `__init__.py` exports exactly the four public names), AC #2 (the last-statement gate test and its `base.py` counterpart). Include the re-export identity assertion that replaces the dropped truth-table test: `config.startup.is_deployed is config.locality.is_deployed` and the same for `is_serving_process`. Object identity, not equal behaviour — that is what proves no second reader was written.
  - [x] `tests/unit/startup/test_stage_one_escape_route.py` — AC #6.
  - [x] `tests/unit/startup/test_installed_apps_ordering.py` — AC #4.
  - [x] `tests/integration/startup/test_stage_two_fires.py` — AC #3. `tests/integration/conftest.py:12` applies `@pytest.mark.integration` to everything under `tests/integration/` automatically; do not re-apply it by hand.
  - [x] `tests/unit/startup/test_no_network_no_queries.py` — AC #7.
  - [x] `tests/unit/test_suite_policy.py` forbids `pytest.skip`, `xfail`, `skipif` and `importorskip` in any new test module unless the file is registered in its `RECORDED_EXEMPTIONS` table (`:94`). Write none; nothing in this story needs one.

## Dev Notes

### Architecture Constraints

- **AD-26 (binding rule, verbatim):** "The refusal contract is one module, `src/config/startup/`, containing both stages and the FR-17 allowlist. **Stage 1** is invoked as the **last statement of every leaf settings module** — `local.py`, `production.py`, `test.py` — which places it after the AD-8 composition step by construction and is why AD-9's iteration over every configured database is reachable. **`base.py` must not call it**, and a gate test asserts both halves: each leaf's last statement is the stage-1 call, and `base.py` contains none. The distinction is load-bearing rather than pedantic — `base.py` is imported via `from .base import *` and itself configures four forbidden states, so a call at its end fires *before* the leaf composes and destroys the after-composition property this rule exists to guarantee. 'Every settings module' is the plausible reading and the wrong one. **Stage 2** is owned by the `AppConfig.ready()` of one named immovable-core app in `django_service`, declared in `accelerator.toml`; no adopted app may precede it in `INSTALLED_APPS`, and a gate test asserts that ordering. **Predicates resolve objects, never strings.** … **`src/config/startup/` holds the authoritative copy and `accelerator.toml` mirrors it**, with a gate test asserting equality."
  **Prevents:** "the product's highest-consequence surface being split across two modules by two builders who both satisfy FR-12; stage 1 running before composition and never seeing a contributed database; an allowlist maintained apart from the conditions it backstops."
- **AD-13 (binding rule, as amended 2026-08-17 — spine commit `d40b684`):** "`COMPONENT_RUNTIME = \"local\"` is declared exactly once, in `[feature.dev.activation.env]`. Every developer path runs in the `dev` environment and inherits it; the `default` environment declares nothing and therefore reads *deployed* — which is what the golden base runs and what the release stage invokes (`pixi run migrate`, `pixi run collectstatic`). `web`, `worker` and `beat` set no runtime and inherit *deployed*; each sets `COMPONENT_PROCESS` in its own task `env`. **No `COMPONENT_*` variable may appear in the `default` environment's resolved activation env; `COMPONENT_PROCESS` may not appear in *any* activation env** … **No production-bound environment may include the `dev` feature.** … Locality fails closed: absent or unrecognized means deployed. Process type fails open: absent means not a serving process, because failing it closed would produce exactly that deadlock."
  The superseded per-task version of this rule is what the rest of this story was originally written against; where the two disagree, the amended rule governs. `src/config/locality.py` (Story 3.1) is the delivered reader for both names — this story imports it and creates no second one.
  **Prevents:** "the declaration travelling into the deployed image and inverting the fail-closed property; the entire test suite refusing to start on the day the refusal contract lands; `sys.argv` sniffing." **`sys.argv` sniffing is forbidden.** Do not inspect `sys.argv`, `sys.modules`, or the process name to decide locality or process type.
- **NFR-1:** "the nine checks are settings and URL-configuration inspection with no network call and no query beyond the migration state, so their cost is irrelevant to startup time."
- **CG-3:** "Do not soften a refusal into a warning. A refusal that logs and continues makes deployment smoother and puts local credentials into production."
- **AD-29:** no `feature:*` disposition may apply to any path inside `src/django_service/` — it is `core` in its entirety. The stage-2 owner therefore travels in all six combinations by construction.
- **AD-24 forbids** conditional imports, settings-module inheritance and `try/except ImportError` as sub-file removal mechanisms. `src/config/startup/` must not use any of them for feature scoping; Story 4.4 uses paired `feature:<name>` / `/feature:<name>` line comments instead.
- **AD-1:** every declaration has exactly one site. `STAGE_TWO_OWNER_APP_LABEL` is a single constant here, declared in `accelerator.toml` from Epic 7 (AD-26). The allowlist and AD-8's contributable surface are different: `src/config/startup/` **remains the authoritative location**, and Epic 7 adds a mirror in `accelerator.toml` plus a gate test asserting the two are equal. The carrier is `machinery`, never travels, and therefore cannot be the runtime authority for a rule that executes at settings import inside a materialized component (AD-26, AD-8).
- **R-3 (carry, do not attempt to fix):** "A serving process started outside `pixi run web` does not fire the migrations refusal. The price of AD-13's fail-open process type, taken because failing it closed deadlocks the release stage." Do not add a fallback that infers serving-process status when `COMPONENT_PROCESS` is absent.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/startup/__init__.py` | NEW | Public surface: `run_stage_one`, `run_stage_two`, and `is_deployed` / `is_serving_process` **re-exported from `config.locality`**, not redefined. |
| ~~`src/config/startup/locality.py`~~ | **DO NOT CREATE** | Superseded. `src/config/locality.py` (Story 3.1) is the single reader; `startup/__init__.py` re-exports `is_deployed` and `is_serving_process` from it. A second reader violates AD-1. |
| `src/config/startup/stage_one.py` | NEW | Stage-1 entry point, the FR-12 escape-route condition, `_STAGE_ONE` skeleton for Stories 4.2/4.4. |
| `src/config/startup/stage_two.py` | NEW | Stage-2 entry point, `STAGE_TWO_OWNER_APP_LABEL`, `_STAGE_TWO_RAN` sentinel, skeleton for Story 4.3. |
| `src/config/startup/allowlist.py` | NEW | Empty declaration module; Story 4.6 fills it. Created here so AC #1's "one module containing both stages and the allowlist" is true from the start. This module is the **authoritative** home of the FR-17 allowlist and AD-8's contributable surface — `accelerator.toml` mirrors it in Epic 7, never replaces it (AD-26). |
| `src/config/settings/local.py` | UPDATE | Today: 197 lines. `DEBUG=True`, dev SECRET_KEY, LocMemCache, console email, whitenoise prepended to `INSTALLED_APPS`, the `DEBUG_APPS` block, eager Celery, the local `CLAIMS_CONTRACT` fill, the JWKS-location derivation, and a closing `OIDC_ISSUER` / `OIDC_AUDIENCE` whitespace-stripped fill. **Change:** add the `run_stage_one(sys.modules[__name__])` call as the new last statement. **Preserve:** the `DEBUG_APPS` env gate, the eager-Celery block (Story 4.4 marks it, this story does not) and the closing OIDC fill — the `.strip() or` form is load-bearing and documented in place. |
| `src/config/settings/production.py` | UPDATE | Today: 160 lines. The sqlite refusal at `:25-28` (comment at `:25`, `if DATABASES["default"]["ENGINE"].endswith("sqlite3"):` at `:26`), Redis cache, security headers, anymail, `LOGGING`, `SPECTACULAR_SETTINGS["SERVERS"]`. Ends with a trailing comment banner. **Change:** add the stage-1 call as the last statement, after the banner. **Preserve:** the sqlite refusal verbatim — Story 4.2 designates it as condition 1's mechanism. |
| `src/config/settings/test.py` | UPDATE | Today: 88 lines. Console logging at WARNING, test SECRET_KEY, `TEST_RUNNER`, MD5 hasher, locmem email, a configured `CLAIMS_CONTRACT` fixture, `TEMPLATES[0]["OPTIONS"]["debug"] = True` (required by `django_coverage_plugin`), `MEDIA_URL`, then a trailing comment banner. **Change:** add the stage-1 call as the last statement. **Preserve:** the `TEMPLATES` debug line — removing it silently zeroes template coverage and breaks AD-20 — and the `CLAIMS_CONTRACT` fixture, which is what keeps the suite exercising a configured contract. |
| `src/django_service/users/apps.py` | UPDATE | Today: `UsersConfig(name="django_service.users", verbose_name=_("Users"))` with a `ready()` whose body is a docstring plus a comment recording that `ready()` runs inside `django.setup()` and is bound by FR-23 and NFR-1 (`:9-16`). **Change:** `ready()` calls `run_stage_two()`. **Preserve:** `name` and `verbose_name` — `name` is the `AUTH_USER_MODEL="users.User"` app and changing it breaks migrations — and the substance of that comment, which is now a constraint on the call rather than on an empty body. |

**Line references re-verified against `8ce0121`.** The sqlite refusal is at `production.py:25-28`, not `:26-28`. `LOCAL_APPS` is at `base.py:188-191` and `INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS` at `:193` — not `:118-123`. `users/apps.py`'s `ready()` spans `:9-16`, not `:9-12`. The three settings modules have all grown since this story was written; prefer the AST and structural assertions specified in Tasks 3 and 4 to any assertion keyed on a line number.

**Does not exist yet and is not created here:** `accelerator.toml` (Epic 7) and `component.toml` (Epic 5).

**Already delivered, contrary to this story's original reading:** `src/config/authorization/` (Epic 2 — `claims.py`, `jwks.py`, `mapper.py`, `authentication.py`, `adapters.py`, `exceptions.py`) and `src/config/local_dev/` including the local sign-in route (Epic 3, Story 3.4 — `urls.py`, `views.py`). Both exist and are importable. This story still delivers no condition that inspects either; Stories 4.3 and 4.6 resolve view callables out of `config.local_dev` and can now do so against a real module instead of a placeholder.

### Testing Requirements

- New test packages `tests/unit/startup/` and `tests/integration/startup/`, each with `__init__.py`, mirroring `src/config/startup/` per the spine's Test-location convention: "Accelerator and base tests live under `tests/`, mirroring `src/`, and carry the disposition of what they cover." The delivered form of that convention drops the `config` segment — see Task 8. Everything in this story is `core`.
- `tests/integration/conftest.py:12` applies `@pytest.mark.integration` to every test under `tests/integration/` through `pytest_collection_modifyitems`; integration tests do not carry the marker by hand.
- Follow the fresh-import fixture pattern established at `tests/unit/test_settings.py:51-58` (module-name constants at `:40-43`): evict `config.settings.base` alongside the target module from `sys.modules` before *and* after each test, or the `from .base import *` reuses the already-imported copy and module-level environment reads are not re-evaluated. The eviction list there already covers all four modules including `config.settings.test`. The idiom is deliberately re-declared per test module rather than shared through a conftest — `tests/unit/test_no_network_at_boot.py:389-405` re-declares it too; follow that precedent.
- Locality tests must `monkeypatch.setenv` / `monkeypatch.delenv` rather than mutating `os.environ` directly, so state is left as found.
- The tests run in the `dev` pixi environment, which declares `COMPONENT_RUNTIME = "local"` in `[feature.dev.activation.env]` (`pixi.toml:436`). Every stage-1 and stage-2 call in the suite therefore takes the not-deployed early return unless a test deletes the variable. That is what keeps adding the call to `test.py` from refusing at collection — and it is also why any test of deployed behaviour must `monkeypatch.delenv("COMPONENT_RUNTIME", raising=False)` explicitly rather than assuming a clean environment.
- AD-20 coverage floor: ninety percent including templates, `COVERAGE_CORE=ctrace` in force. The `omit`/`exclude` list is a closed carrier-declared surface, frozen as `CLOSED_OMIT` at `tests/unit/test_coverage_policy.py:88-94` — **do not add `src/config/startup/` to `[tool.coverage.run] omit`** under any circumstance. `tests/unit/test_coverage_policy.py` also forbids `# pragma: no cover` anywhere under `src/`, and `tests/unit/test_typing_policy.py:305` requires every `# type: ignore` to name its error code.
- Ruff rules that will bite this package specifically: `EM`/`TRY003` (no string literal inline in a `raise` — bind the message to a variable first, as `tests/conftest.py:83-85` does), `SLF001` (no cross-module private-attribute reads — see Task 5), `PLW0603` (no `global` statement), `PLC0415` (imports top-level unless `# noqa`'d), `INP` (every test package needs `__init__.py`), `S603` (subprocess calls need `# noqa: S603`), and `isort.force-single-line` (one import per line). `D` is not selected, but the house style is Google-style docstrings on every public function and module; match it.
- Run with `pixi run test`, `pixi run test-integration`, and `pixi run ci` (`pixi.toml:549`, `depends-on = ["precommit", "build", "typecheck", "lint", "test-cov"]`, fast-fail-first in that order). Done means `pixi run ci` exits 0.

#### Project Structure Notes

The spine's Structural Seed places `startup/` under `src/config/` beside `settings/`, `observability/` and `authorization/`, annotated "both refusal stages + the FR-17 allowlist (AD-26)". That directory does not exist in the repository today; this story creates it, matching the Consistency Conventions rule that "cross-cutting concerns with several independent consumers and no natural owner live under `src/config/<concern>/`, as `observability/` already does and `authorization/` and `startup/` will."

**Two upstream dependencies this story assumes, both flagged rather than worked around:**

1. **Locality is already declared, and not on a task.** AD-13 was amended on 2026-08-17 (spine commit `d40b684`) and Story 3.1 has landed: `COMPONENT_RUNTIME = "local"` is declared once in `[feature.dev.activation.env]`, and **no pixi task declares it**. Every developer path — `test`, `test-integration`, `test-cov`, `typecheck`, `precommit` — resolves to the `dev` environment and inherits it, so adding the stage-1 call to `test.py` does **not** make the suite refuse at collection. Do **not** add `env = { COMPONENT_RUNTIME = "local" }` to any task: `tests/unit/test_locality_declaration.py::test_no_task_declares_component_runtime` fails on any task that does. `COMPONENT_RUNTIME` remains forbidden in the `default` environment's `[activation.env]`, and `COMPONENT_PROCESS` in *any* activation env.
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

## Spec Change Log

Reconciliation pass against the tree at `8ce0121`, before any code was written. The Dev Notes were
authored 2026-08-15 and last touched 2026-08-18 for the locality-reader correction; Stories 2.1-2.8
and 3.1-3.7 have landed since the rest of it was written, and nine claims did not survive
re-reading. Each is corrected in place above.

1. **The test packages are `tests/unit/startup/` and `tests/integration/startup/`, not
   `tests/unit/config/startup/`.** The delivered mirror convention drops the `config` segment:
   `tests/unit/authorization/` and `tests/integration/authorization/` mirror
   `src/config/authorization/`, and `tests/unit/users/` mirrors `src/django_service/users/`. Only
   `authorization/` and `users/` are subpackaged at all; every other config-level test sits flat in
   `tests/unit/test_*.py`. A `config/` level here would make `startup/` the one package in the suite
   nested differently from the thing it mirrors.

2. **The locality truth-table test is dropped, not relocated.** Task 8 asked for
   `tests/unit/config/startup/test_locality.py` carrying the fail-closed and fail-open truth tables.
   Story 3.1 already delivered `tests/unit/test_locality.py` with eleven tests covering exactly that:
   undeclared and unrecognized runtimes read deployed, declared ones read local, values are stripped
   and lowercased before matching, both names are read at call time, and the two declarations are
   independent. A second copy would assert the same behaviour of the same two functions and would
   have to be kept in step by hand. Replaced with a re-export **identity** assertion in
   `test_module_shape.py` (`config.startup.is_deployed is config.locality.is_deployed`), which is
   what actually proves no second reader was written — the thing AD-1 is about.

3. **The stage-2 sentinel assertion must run in a subprocess.** Task 5 specified an integration test
   that drives a request through `config.asgi:application` and asserts a `_STAGE_TWO_RAN` sentinel.
   In the pytest process that assertion is vacuous: pytest-django completes `django.setup()` — and
   therefore `UsersConfig.ready()` — during collection, so the sentinel is already `True` before any
   test body runs and would stay `True` if the `ready()` call were deleted.
   `tests/unit/test_no_network_at_boot.py:20-30` records this exact problem for boot assertions and
   solves it with a `-c` boot-probe subprocess writing a JSON report to a file; Task 5 now specifies
   the same shape, and additionally requires the report to prove a response was produced so a probe
   that never served cannot pass.

4. **The sentinel is set at the start of `run_stage_two()`, not at its end, and is read through a
   public helper.** Set at the end it would sit after the `is_deployed()` early return and would
   never fire on any developer or CI path — all of which run local — so the test would assert
   nothing. Read as a bare `stage_two._STAGE_TWO_RAN` it trips ruff `SLF001`, and imported directly
   it binds a copy of the boolean at import time and never observes the write. Held in a rebound
   module global it trips ruff `PLW0603`. The specified form — a small module-level mutable record
   behind a public reader — is the only one that is both lint-clean and observable.

5. **The last-statement gate test parses the AST rather than reading the last source line.** Task 3
   asked for the last non-blank, non-comment source line. `production.py` already ends with a
   trailing comment banner and `test.py` does too, so a source-line check either fails on the comment
   or re-implements comment stripping. `ast.parse(...).body[-1]` is exact, and the technique is
   already in the suite at `tests/unit/test_asgi_surface.py:300-332`.

6. **`run_stage_one` takes a required positional-only module.** The specified
   `(settings_module: ModuleType | None = None, /, **_: object)` has no caller that uses either the
   default or the keyword catch-all, and `**_: object` would silently absorb a future condition's
   misrouted keyword instead of failing on it. Narrowed to `(settings_module: ModuleType, /)`.

7. **Task 7's query assertion is zero queries from both stages, not "the migration-state read and the
   designated-group read".** Neither of those conditions exists until Stories 4.3 and 4.6. Asserting
   zero now means each of those additions has to amend this test visibly rather than being absorbed
   into a pre-widened allowance. The network half reuses the delivered `no_network` fixture
   (`tests/conftest.py:136`) rather than hand-patching `socket.socket`; the delivered guard already
   covers `connect`, `connect_ex`, `create_connection`, `getaddrinfo` and `gethostbyname` and raises
   a `BaseException` subclass so a stray `except Exception:` cannot swallow it.

8. **`src/config/authorization/` and the local sign-in module already exist.** The Dev Notes listed
   both under "Does not exist yet and is not created here". Epic 2 delivered `config/authorization/`
   and Story 3.4 delivered `config/local_dev/urls.py` and `views.py`. Nothing in this story depends
   on either — it delivers no condition — but Stories 4.3 and 4.6 resolve view callables out of
   `config.local_dev` and can now do so against a real module. `accelerator.toml` and
   `component.toml` genuinely do not exist.

9. **Line references throughout the Source Tree table were stale and are corrected.** The sqlite
   refusal is at `production.py:25-28`; `LOCAL_APPS` is at `base.py:188-191` with the `INSTALLED_APPS`
   composition at `:193`; `ready()` spans `users/apps.py:9-16`; the `ci` task is at `pixi.toml:549`
   with `depends-on = ["precommit", "build", "typecheck", "lint", "test-cov"]` — a different set and
   order from the four the Dev Notes named. `local.py` is 197 lines, not 82. The `users/apps.py`
   `ready()` body is a docstring **plus a comment** recording the FR-23/NFR-1 constraint on whatever
   goes there, not a docstring alone; that comment is now a constraint on `run_stage_two()` and is
   preserved rather than replaced.

**KEEP.** Three things in the original Dev Notes are load-bearing and must survive any
re-derivation: the `base.py` exclusion and the reasoning behind it (AD-26's "every settings module"
is the plausible and wrong reading); the instruction to import `config.locality` rather than write a
second reader; and R-3's standing refusal to infer serving-process status when `COMPONENT_PROCESS`
is absent.

## Review Triage Log


## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Claude Opus 5, 1M context), acting as the Story 4.1 implementation agent.

### Debug Log References

- `pixi run ci` -> exit 0. Five steps in order: precommit (10 hooks, all Passed), build,
  typecheck (`Success: no issues found in 63 source files`), lint (`All checks passed!`),
  test-cov (`977 passed`, `Required test coverage of 90% reached. Total coverage: 96.50%`).
- `pixi run test` -> `724 passed`. `pixi run test-integration` -> `247 passed, 6 skipped`
  (the six skips are pre-existing platform skips, unchanged by this story).
- Every new module under `src/config/startup/` reports 100% line coverage in the term-missing
  report: `__init__.py` 6/6, `allowlist.py` 6/6, `stage_one.py` 22/22, `stage_two.py` 16/16.
  `src/django_service/users/apps.py` 8/8.
- **One real failure during the run, and its cause.** The first version of the stage-2 boot probe
  hung for the full 180-second subprocess timeout. Django's `ASGIHandler` races the response
  against a task awaiting `http.disconnect`, so a `receive()` that returns a message every time it
  is called reads as a client that has already gone away. The probe's `receive` now hands over the
  request body once and then blocks on an event that is never set, which is what a real server's
  receive channel does between messages. An `asyncio.wait_for` was added inside the probe so a
  future regression of the same shape fails in 60 seconds with a diagnosable traceback rather than
  in 180 with a `TimeoutExpired` on the parent.
- **Mutation check, run deliberately rather than assumed, and re-run by the orchestrator.** With
  `run_stage_two()` removed from `UsersConfig.ready()` and replaced by `pass`, the ASGI boot-probe
  case fails (`assert False is True` on `report["stage_two_fired_during_setup"]`) and the
  last-statement gate catches the same mutation applied to `production.py`'s stage-1 call. The
  implementation agent's first report said *both* integration cases fail under the `ready()`
  mutation; that is wrong, and the corrected result is one — the management-command case reads the
  sentinel in the pytest process, where collection already wrote it, so it survives the mutation.
  That case is the deliberately weaker half of AC #3 and its own docstring says so; the boot probe
  is the assertion that carries the criterion. The call was restored immediately afterwards.
- **Independent gate re-run by the orchestrator:** `pixi run ci` -> exit 0, `977 passed`,
  `Total coverage: 96.50%`. The new packages run 41 tests in ~1.0s.

### Completion Notes List

- **AC #1.** `src/config/startup/` holds `__init__.py`, `stage_one.py`, `stage_two.py` and
  `allowlist.py`. `__all__` is exactly `run_stage_one`, `run_stage_two`, `is_deployed`,
  `is_serving_process`. No `startup/locality.py` was written: the two predicates are re-exported
  from `config.locality`, and `test_module_shape.py` asserts that by **object identity** plus an
  AST scan proving no module in the package imports `os` at all.
- **AC #2.** `run_stage_one(sys.modules[__name__])` is the last top-level statement of `local.py`,
  `production.py` and `test.py`. `base.py` calls it nowhere. Both halves are gate tests over
  `ast.parse(...).body[-1]`, with the leaf list enumerated from the directory rather than written
  down, and a third case asserting exactly one call per leaf.
- **AC #3.** `UsersConfig.ready()` calls `run_stage_two()`. The served-path proof is a `-c` boot
  probe subprocess that leaves `DJANGO_SETTINGS_MODULE` unset, imports `config.asgi`, reads the
  sentinel at that point, drives one request through the resulting callable and writes a JSON
  report. The parent requires both `stage_two_fired_during_setup is True` **and** a real 404
  response, so a probe that never served cannot pass. The management-command path is asserted
  separately and in-process, as the spec's weaker assertion.
- **AC #4.** `test_installed_apps_ordering.py` reads the live app registry. `component.toml` does
  not exist, so the strong index comparison is not yet possible; the delivered form asserts the
  invariant that makes it hold by construction -- the owner is the first `LOCAL_APPS` entry,
  `LOCAL_APPS` is the last segment of `INSTALLED_APPS`, and nothing at or after the owner comes
  from outside `LOCAL_APPS`. Epic 5's `component.toml` is named in the module docstring as the
  eventual source of the adopted-app roster.
- **AC #5.** Locality is `config.locality.is_deployed()` and nothing else -- read from the
  environment, never inferred from the settings module, and never from `sys.argv`. The escape-route
  condition compares the passed module object's `__name__`, not
  `os.environ["DJANGO_SETTINGS_MODULE"]`. The refusal is parametrized over both spellings of
  deployed (unset **and** unrecognized), so a condition written against a missing variable rather
  than against `is_deployed()` fails.
- **AC #6.** `test_stage_one_escape_route.py` deletes `COMPONENT_RUNTIME`, imports
  `config.settings.local` for real, and asserts `ImproperlyConfigured` with a message naming the
  module and stating both resolutions.
- **AC #7.** Network: the delivered `no_network` fixture, unmodified. Queries: zero, asserted
  twice -- `connection.execute_wrapper` in the unit test (no connection opened, so it stays a unit
  test) and `CaptureQueriesContext` against a live connection in the integration test. No
  wall-clock assertion, per NFR-1's `[ASSUMPTION]`.
- **This story delivers exactly one condition** -- FR-12's escape route, which Task 6 requires and
  which is the frame's own reason to exist. `_STAGE_ONE` and `_STAGE_TWO` are the condition rosters
  Stories 4.2, 4.3 and 4.4 append to; `allowlist.py` is declared and empty for Story 4.6.
- Nothing was added to `[tool.coverage.run] omit`, no `# pragma: no cover` was written, no
  `pytest.skip`/`xfail`/`skipif`/`importorskip` was introduced, and no `# type: ignore` was added.

**Judgment calls a reviewer should know about:**

1. **`CaptureQueriesContext` cannot run as a unit test, so AC #7's query half is asserted in two
   places.** Its `__enter__` calls `connection.ensure_connection()`, which pytest-django blocks
   outside `django_db` -- and `tests/unit/conftest.py` states that unit tests touch no database.
   Rather than mark a unit test `django_db` (which no unit test in this suite does) or drop the
   mechanism the spec names, the unit test uses `connection.execute_wrapper` (installs without
   connecting; proves nothing reached the cursor) and `tests/integration/startup/test_no_queries.py`
   carries the spec's `CaptureQueriesContext` assertion against a real connection. Both must be
   amended when Story 4.3's migration-state read lands.
2. **Two test modules beyond the Task 8 list.** `tests/unit/startup/test_stage_dispatch.py` covers
   the dispatch frame itself -- that each roster is iterated and that both iterations sit *below*
   the `is_deployed()` early return. Without it the stage-2 loop body would never execute (its
   roster is empty in this story) and would show as an uncovered line. It replaces the rosters by
   name through `monkeypatch.setattr(module, "_STAGE_TWO", ...)`, which reads no private attribute
   and so trips no `SLF001`. `tests/integration/startup/test_no_queries.py` is the file from
   point 1.
3. **`__init__.py`'s "exactly four public names" is asserted over `__all__`.** Importing the
   submodules binds `stage_one`, `stage_two` and `allowlist` as attributes of the package, so a
   `dir()`-based count could never be four. `__all__` is the declaration; each of its four entries
   is additionally asserted to resolve to a callable.
4. **`allowlist.py` declares three empty rosters rather than being literally empty**
   (`ALLOWED_AUTHENTICATION_BACKENDS`, `ALLOWED_API_AUTHENTICATION_CLASSES`,
   `ALLOWED_AUTHENTICATION_ROUTE_PREFIXES`), matching FR-17's three surfaces. Story 4.6 fills the
   values; it may rename them, and nothing outside the module reads them yet.
5. **`SETTINGS_MODULE_ENV_VAR = "DJANGO_SETTINGS_MODULE"` is spelled in `stage_one.py`** purely to
   compose the refusal message. The condition never reads it -- that is the point of the condition.

**Residual risk knowingly left:**

- **AC #3's "under gunicorn and uvicorn" is proven transitively, not by starting them.** The probe
  drives `config.asgi:application` directly. Both servers import that same module and call the same
  `get_asgi_application()`, and `tests/integration/test_import_resolution.py` already starts both
  and asserts they resolve it identically. A gunicorn-specific `ready()` failure mode would not be
  caught here.
- **AC #4 is the weaker invariant until Epic 5.** Recorded above and in the module docstring.
- **R-3 stands untouched.** Nothing infers serving-process status when `COMPONENT_PROCESS` is
  absent, and stage 2 gates on nothing but `is_deployed()` in this story.
- **The boot probe inherits `COMPONENT_RUNTIME=local` from the `dev` environment**, so it exercises
  the local path. That is deliberate -- it is why the sentinel is written before the locality check
  -- but it means the probe proves the invocation point fires, not that a deployed serving process
  evaluates a condition. Story 4.3 is where that becomes assertable.

### File List

**New**

- `src/config/startup/__init__.py` -- the package: four public names, two of them re-exported from
  `config.locality`.
- `src/config/startup/stage_one.py` -- `run_stage_one`, the `_STAGE_ONE` roster, and FR-12's
  escape-route condition.
- `src/config/startup/stage_two.py` -- `run_stage_two`, `STAGE_TWO_OWNER_APP_LABEL`, the
  `_STAGE_TWO` roster, and the `stage_two_has_run()` boot sentinel.
- `src/config/startup/allowlist.py` -- the authoritative FR-17 allowlist, declared and empty.
- `tests/unit/startup/__init__.py`
- `tests/unit/startup/test_module_shape.py` -- AC #1, AC #2.
- `tests/unit/startup/test_stage_one_escape_route.py` -- AC #5, AC #6.
- `tests/unit/startup/test_installed_apps_ordering.py` -- AC #4.
- `tests/unit/startup/test_stage_dispatch.py` -- the dispatch frame and the sentinel ordering.
- `tests/unit/startup/test_no_network_no_queries.py` -- AC #7.
- `tests/integration/startup/__init__.py`
- `tests/integration/startup/test_stage_two_fires.py` -- AC #3.
- `tests/integration/startup/test_no_queries.py` -- AC #7's `CaptureQueriesContext` half.

**Modified**

- `src/config/settings/local.py` -- `import sys`, `from config.startup import run_stage_one`, and
  the stage-1 call as the new last statement. Nothing else touched.
- `src/config/settings/production.py` -- the same three additions; the sqlite refusal and the
  trailing banner are untouched.
- `src/config/settings/test.py` -- the same three additions; the `TEMPLATES` debug line and the
  `CLAIMS_CONTRACT` fixture are untouched.
- `src/django_service/users/apps.py` -- `ready()` calls `run_stage_two()`. `name` and
  `verbose_name` are unchanged, and the FR-23/NFR-1 comment is preserved as a constraint on the
  call rather than on an empty body.
