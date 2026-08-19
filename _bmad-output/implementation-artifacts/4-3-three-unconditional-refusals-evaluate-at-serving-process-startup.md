---
status: done
baseline_revision: d31042865a730918c38e535a069d457e7df1b653
context: []
warnings: []
---

# Story 4.3: Three unconditional refusals evaluate at serving-process startup

Status: done

## Story

As a platform engineer,
I want the conditions that need the application registry refused when a serving process starts,
so that a reachable credential route or an unrecognized schema stops the process rather than serving traffic.

## Acceptance Criteria

**Traceability:** FR-13 (stage 2), FR-15, FR-41 · AD-9, AD-21, AD-26, AD-27 · SC-5

1. **Given** a reachable forbidden credential route
   **When** stage 2 resolves the URL configuration
   **Then** `ImproperlyConfigured` is raised for each of two states: a route whose view callable is `obtain_auth_token`, and a route whose view callable belongs to the local sign-in module

2. **Given** the predicates
   **When** they evaluate a route
   **Then** they resolve the view callable
   **And** they never match on a route name or a path prefix, so a route named `local_persona_login` mounted under `/accounts/` cannot evade them

3. **Given** a component whose settings are correct but whose URL configuration still routes `obtain_auth_token`
   **When** it starts
   **Then** it refuses
   **And** a test constructs exactly that state

4. **Given** unapplied migrations on any configured database
   **When** a serving process starts
   **Then** `ImproperlyConfigured` is raised
   **And** management commands are exempt, so `manage.py migrate` — the one action that clears the condition — is not forbidden by it

5. **Given** a designated staff or superuser group absent from the database
   **When** a serving process starts
   **Then** `ImproperlyConfigured` is raised
   **And** the misconfiguration surfaces as a configuration error rather than as a mysterious permissions problem

6. **Given** stage 1 runs as the last statement of every leaf settings module
   **When** stage 1 and stage 2 iterate databases
   **Then** both iterate every configured database

## Tasks / Subtasks

- [x] Task 1 — Build the URLconf walker that yields view callables, not strings (AC: #1, #2)
  - [x] Add `_iter_view_callables(urlconf: str | None = None) -> Iterator[tuple[str, Callable[..., object]]]` to `src/config/startup/stage_two.py`. Resolve the root URLconf with `django.urls.get_resolver(urlconf)` and recurse: for each entry in `resolver.url_patterns`, recurse into `URLResolver` (`include(...)`) and yield `pattern.callback` for each `URLPattern`.
  - [x] Unwrap decorated views before comparison: follow `functools.wraps`-set `__wrapped__` chains with `inspect.unwrap`, and unwrap `django.views.generic.View.as_view()` products via their `view_class` attribute. A decorator applied to `obtain_auth_token` must not hide it.
  - [x] Yield the callable object itself. **Never** yield or compare `pattern.name`, `pattern.pattern`, `str(pattern)`, or any dotted path derived from them.
  - [x] Guard against a cyclic or self-referential include with a `seen` set keyed on `id(resolver)`, so the walk terminates.

- [x] Task 2 — Condition 6, state a: a route whose view callable is `obtain_auth_token` (AC: #1, #2, #3)
  - [x] `_refuse_credential_minting_route() -> None`. Import `rest_framework.authtoken.views.obtain_auth_token` at module top level (unconditional import — AD-24 forbids `try/except ImportError`) and refuse when any unwrapped view callable **is** that object, or is an instance/subclass product of `rest_framework.authtoken.views.ObtainAuthToken`.
  - [x] Compare by object identity (`is`) and by `type` / `issubclass` on the view class. Do not compare `callable.__name__ == "obtain_auth_token"` and do not compare `callable.__module__` string literals — a re-export under another name is the evasion this closes.
  - [x] `src/config/urls.py:39` routes `obtain_auth_token` today: `path("api/auth-token/", obtain_auth_token, name="obtain_auth_token")`, imported at `:11`. Epic 2 Story 2.8 removes it. This condition is what makes the removal permanent.
  - [x] AC #3's test constructs a URLconf module that routes `obtain_auth_token` while the settings namespace is otherwise valid, and asserts the refusal — settings-correct, URLconf-wrong.

- [x] Task 3 — Condition 6, state b: a route whose view callable belongs to the local sign-in module (AC: #1, #2)
  - [x] `_refuse_local_sign_in_route() -> None`. Import the local sign-in module object created by Epic 3 Story 3.4 — a plain top-level `import`, producing a module object.
  - [x] Predicate: for each unwrapped view callable, resolve its defining module with `inspect.getmodule(callable)` and refuse when that module object **is** the imported local sign-in module, or is a submodule of it (compare the imported module's `__name__` obtained *from the imported object*, never a hardcoded literal, and test `defining.__name__ == mod.__name__ or defining.__name__.startswith(mod.__name__ + ".")`).
  - [x] **The evasion this blocks, stated explicitly (AD-21):** a route named `local_persona_login` mounted under `/accounts/` would satisfy AD-21 by name and pass an allowlist that already permits `/accounts/` for allauth. Any implementation that matches the route name or the path prefix is wrong and must be rejected in review.
  - [x] **Shipping is not mounting (AD-21).** The local sign-in *module* is `core` and ships in every component; Story 3.4 mounts its *route* only where locality is local. So in a correctly configured deployed component this condition finds nothing to refuse — it is the backstop for a route reachable anyway, through a URLconf edit, a misconfiguration, or a locality that failed open. Do not read the condition as evidence the route is mounted everywhere, and do not "fix" Story 3.4 by mounting it unconditionally: that would make every deployed component refuse to start.
  - [x] Story 3.4 declares the local sign-in route's URL name and path prefix as fixed constants in exactly one place, and Epic 7 moves that declaration into `accelerator.toml`. Those constants are **not** the predicate — they exist for the route's own construction and for the FR-17 allowlist (Story 4.6). This condition uses the module object only.
  - [x] If Story 3.4 has not landed, implement against a `LOCAL_SIGN_IN_MODULE` constant in `src/config/startup/stage_two.py` holding the dotted path, imported once with `importlib.import_module` at module scope into a module object, and record in the Completion Notes that Story 3.4 must place its views in that module rather than declare a second location.

- [x] Task 4 — Condition 7: unapplied migrations on a serving process, over every configured database (AC: #4, #6)
  - [x] `_refuse_unapplied_migrations() -> None`. Gate on `is_serving_process()` — this is the **only** condition in the contract that is serving-process-only. Management commands must be exempt, because `manage.py migrate` is the one action that clears the condition and forbidding it deadlocks the FR-41 release stage.
  - [x] For each alias in `django.conf.settings.DATABASES`, build a `django.db.migrations.executor.MigrationExecutor(connections[alias])` and refuse when `executor.migration_plan(executor.loader.graph.leaf_nodes())` is non-empty. Name the alias and the pending migrations in the message.
  - [x] This is the one permitted query in the whole contract. NFR-1: "no query beyond migration state." Do not add a connectivity retry, a timeout wrapper, or a readiness-style poll.
  - [x] Iterate every alias, including a contributed database's (AD-9). Do not special-case `"default"`.
  - [x] FR-41 traceability: this condition is the *implementation* of the unapplied-migrations refusal. **Epic 5 owns the release-stage contract and the no-entrypoint-migrates property** — do not add or modify any entrypoint, task or container command here.

- [x] Task 5 — Condition 5, stage-2 half: a designated group is absent from the database (AC: #5)
  - [x] `_refuse_missing_designated_groups() -> None`. Gate on `is_serving_process()` alongside condition 7, since it too requires a live database.
  - [x] Read the designated staff group name and superuser group name from the claims contract Epic 2 Story 2.2 declared — the same names Story 4.2's stage-1 half validates as configured. Refuse when either has no matching `django.contrib.auth.models.Group` row.
  - [x] Use one query: `Group.objects.filter(name__in=[staff_group, superuser_group]).values_list("name", flat=True)`, and refuse naming exactly which of the two is missing.
  - [x] AD-27's reasoning, which the message must reflect: "a misconfiguration must not present as a permissions bug." AD-12 already establishes that a claim naming a nonexistent `Group` is ignored and logged, never created — safe **only because** AD-27 guarantees the designated groups exist. This condition is that guarantee's enforcement.
  - [x] The groups themselves are provisioned by a data migration inside `django_service`, seeded from the claims contract (Epic 2 Story 2.3). Do not create groups here; a refusal never repairs.

- [x] Task 6 — Wire the conditions into `run_stage_two` in a fixed order (AC: all)
  - [x] `run_stage_two()` returns immediately when `is_deployed()` is `False`. Then: the two URLconf conditions run for **any** deployed process; the two database conditions run only when `is_serving_process()` is `True`.
  - [x] Record the order as a module-level tuple so a test can assert it (AD-26: one location, one owner, a fixed order).
  - [x] Set the `_STAGE_TWO_RAN` sentinel from Story 4.1 as the final statement, after all conditions pass.
  - [x] Every failure raises `ImproperlyConfigured`. No warning, no log-and-continue, no bare `except` (CG-3).

- [x] Task 7 — Tests (AC: all)
  - [x] `tests/unit/config/startup/test_stage_two_urlconf.py` — the two forbidden route states, plus the two evasion tests below.
  - [x] **Evasion test A:** a URLconf routing the local sign-in view under `path("accounts/local-sign-in/", view, name="local_persona_login")` still refuses. Asserts the predicate is not prefix-matching.
  - [x] **Evasion test B:** a URLconf routing `obtain_auth_token` re-exported under a different module attribute name and a different route name still refuses. Asserts the predicate is not name-matching.
  - [x] **Negative test:** a URLconf containing only allauth and admin routes passes. Without it a predicate that refuses everything would pass every refusal test.
  - [x] `tests/integration/config/startup/test_stage_two_database_conditions.py` — `@pytest.mark.integration`. The unapplied-migrations refusal against a second configured alias; the exemption when `COMPONENT_PROCESS` is absent; the missing-designated-group refusal; the pass case with both groups present.
  - [x] AC #6: one test asserting that with two aliases configured and the *second* holding the fault, both the stage-1 sqlite condition (Story 4.2) and this story's migrations condition refuse. Proves neither reads `DATABASES["default"]` alone.
  - [x] Each stage-2 condition needs at least one test exercising it through a served request path, not only through `manage.py` — Story 4.5 owns that audit; satisfy it here by reusing the ASGI-driven fixture Story 4.1 created at `tests/integration/config/startup/test_stage_two_fires.py`.

## Dev Notes

### Architecture Constraints

- **AD-26 (the load-bearing clause, verbatim):** "**Predicates resolve objects, never strings.** The credential-path and local-sign-in conditions resolve the URLconf and refuse any route whose view callable belongs to the forbidden module — `obtain_auth_token`'s and the local sign-in module's — so renaming a route or remounting it under another prefix cannot evade them."
- **AD-21 (binding rule):** "Local persona sign-in is exposed as a URL route and by no other mechanism … The stage-2 predicate refuses any route whose **view callable belongs to the local sign-in module** (AD-26), never a name or prefix match, because a route named `local_persona_login` mounted under `/accounts/` would otherwise satisfy this AD and pass an allowlist that already permits `/accounts/` for allauth. **The module ships in every component; the route is mounted only where locality is local.** The distinction is the whole rule: a route mounted unconditionally would make every deployed component refuse to start, since the stage-2 condition refuses the local sign-in route's reachability. Shipping is not mounting, and the refusal is the backstop for a route that is reachable anyway — through a URLconf edit, a misconfiguration, or a locality that failed open — not the expected path."
  **Prevents:** "the product's own credential path taking a shape the refusal contract cannot see; and — the subtler half — a route that satisfies this AD by name and still evades the refusal because the predicate matched a string."
- **AD-9 (binding rule):** "The stage-2 unapplied-migrations refusal and the sqlite refusal both iterate every configured database — which is only possible because stage 1 runs *after* composition (AD-26)."
- **AD-27 (binding rule):** "Django `Group` rows named by the claims contract, and the `Permission` rows attached to them, are provisioned by a data migration inside `django_service`, seeded from the claims contract, so they exist before the first authentication … A designated staff or superuser group absent from the database at startup is a stage-2 refusal condition, on AD-12's own reasoning: a misconfiguration must not present as a permissions bug."
  **Prevents:** "the bootstrap deadlock in which every deployed component grants nobody any authorization and nobody can reach the admin, while every local smoke check passes."
- **AD-13:** "Process type fails open: absent means not a serving process, because failing it closed would produce exactly that deadlock." Do not infer serving-process status from `sys.argv`, the process name, or the presence of an ASGI server in `sys.modules`.
- **AD-22:** "No entrypoint, task or container command runs migrations; migration is a release-stage step … and the stage-2 refusal enforces that a serving process never starts against an unrecognized schema." This story implements the refusal only.
- **AD-24 forbids** `try/except ImportError` and conditional imports. `obtain_auth_token` and the local sign-in module are imported unconditionally at module top level.
- **CG-3:** a refusal never degrades to a warning.
- **NFR-1:** no network call, no query beyond migration state — plus the single designated-group existence read AD-27 requires.
- **R-3 (carry, do not fix):** "A serving process started outside `pixi run web` does not fire the migrations refusal. The price of AD-13's fail-open process type, taken because failing it closed deadlocks the release stage." The refusal is only as reachable as `COMPONENT_PROCESS` being set by the `web`/`worker`/`beat` pixi tasks (Epic 5). Accept this; do not compensate.

### The settled refusal count

From `_bmad-output/planning-artifacts/epics.md:310-328`. **Nine conditions — seven unconditional, two conditional — across fourteen distinct forbidden states**, each tested separately under FR-16.

| # | Condition | Stage | Forbidden states |
|---|---|---|---|
| 1 | The sqlite backend is reached | 1 | 1 *(built: `production.py:26-28`)* |
| 2 | A local credential path is live in settings | 1 | 4 |
| 3 | `OTEL_SDK_DISABLED` is true | 1 | 1 |
| 4 | The JWKS trust anchor is not derived from the configured IdP | 1 | 1 |
| 5 | The claims contract is unusable | 1 and 2 | 2 — unconfigured (stage 1); a designated group absent from the database (stage 2, AD-27) |
| 6 | A forbidden credential route is reachable in the resolved URLconf | 2 | 2 — `obtain_auth_token`; the local sign-in route |
| 7 | Unapplied migrations exist on a serving process | 2 | 1 |
| 8 | *(conditional — Redis selected)* An in-process cache backend is configured | 1 | 1 |
| 9 | *(conditional — background tasks selected)* Eager task execution is enabled | 1 | 1 |

This story owns conditions 6 and 7 and the stage-2 half of 5 — **four of the fourteen forbidden states**. Conditions 5 and 6 are the two groupings in the table; both follow the precedent FR-16 already sets for the four settings-side credential paths, and each state is tested separately.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/startup/stage_two.py` | UPDATE | Created as a skeleton by Story 4.1 with `run_stage_two`, `STAGE_TWO_OWNER_APP_LABEL` and the `_STAGE_TWO_RAN` sentinel. **Change:** add `_iter_view_callables` and the four condition functions, plus the fixed-order tuple. **Preserve:** the `is_deployed()` early return and the sentinel's position as the final statement. |
| `src/django_service/users/apps.py` | UPDATE (no change if 4.1 landed) | `UsersConfig.ready()` already calls `run_stage_two()` after Story 4.1. Confirm only. Today the body at `:9-12` is a docstring and nothing else. |
| `src/config/urls.py` | READ ONLY | Today: `home`, `about`, admin at `settings.ADMIN_URL`, `users/` include, `accounts/` → `allauth.urls` (`:24`), media static, the API block at `:35-46` including `path("api/auth-token/", obtain_auth_token, name="obtain_auth_token")` at `:39` and its import at `:11`, and the `DEBUG`-gated error-page and debug-toolbar routes at `:48-75`. **This story does not edit it** — Epic 2 Story 2.8 removes the token route, and Epic 7 Story 7.4 deletes the `home` and `about` `TemplateView`s as demonstration content (revision 3). Note that `src/config/urls.py` is **not** a region-bearing path under AD-24: its interface routes are `core` or deleted, never feature-owned. This story makes the token route's return a build failure. |
| `tests/unit/config/startup/test_stage_two_urlconf.py` | NEW | Route-condition tests including both evasion tests and the negative case. |
| `tests/integration/config/startup/test_stage_two_database_conditions.py` | NEW | Migrations and designated-group conditions, `@pytest.mark.integration`. |

**Verified:** `src/config/urls.py:11` imports `obtain_auth_token` and `:39` routes it. `src/config/urls.py:24` mounts `allauth.urls` under `accounts/` — which is exactly why AD-21's stated evasion is live and not hypothetical: a prefix-matching predicate that allowlists `/accounts/` for allauth would let a local sign-in route mounted there through.

**Does not exist yet:** the local sign-in module (Epic 3 Story 3.4), `src/config/authorization/` (Epic 2), `accelerator.toml` (Epic 7), `component.toml` (Epic 5). The `web`/`worker`/`beat` pixi tasks that set `COMPONENT_PROCESS` are Epic 5 (`pixi.toml` today has `manage`, `migrate`, `collectstatic`, `createsuperuser`, `serve` at `:172-179` and no process-model tasks).

### Testing Requirements

- Unit tests for the URLconf conditions: build throwaway URLconf modules with `types.ModuleType` carrying a `urlpatterns` list, and pass their dotted name to `_iter_view_callables` via `django.test.override_settings(ROOT_URLCONF=...)` or the `urlconf` argument. No database, no network — these stay in `tests/unit/`.
- Integration tests for the two database conditions, each carrying `@pytest.mark.integration`, using real connections. Each must leave state as found: create `Group` rows inside a transaction that rolls back (`django_db` with the default transactional rollback), never `TransactionTestCase` semantics that persist.
- Assertions the ACs demand, named explicitly:
  - `ImproperlyConfigured` for a route whose callable **is** `obtain_auth_token`, including when re-exported under another name and mounted at another prefix.
  - `ImproperlyConfigured` for a route whose callable's defining module is the local sign-in module, including when named `local_persona_login` and mounted under `/accounts/`.
  - No refusal for an allauth-and-admin-only URLconf.
  - `ImproperlyConfigured` with unapplied migrations on a **non-default** alias.
  - No refusal from the migrations condition when `COMPONENT_PROCESS` is absent, even with migrations pending.
  - `ImproperlyConfigured` when the staff group is absent; separately when the superuser group is absent.
- AD-20: ninety percent including templates, `COVERAGE_CORE=ctrace` in force. Do not extend `[tool.coverage.run] omit` at `pyproject.toml:160-168`.
- Test-location convention (spine, Consistency Conventions): tests mirror `src/` and carry the disposition of what they cover — all `core` here.
- `pixi run test` and `pixi run test-integration` in the inner loop; `pixi run ci` is the done condition.

#### Project Structure Notes

Aligned with the Structural Seed. One observation on scope: the smoke check's "rendered 404" and "rendered admin index" assertions (AD-30) run in Epic 8, and the local sign-in route is asserted reachable *locally* by Epic 3 Story 3.4 — both are **traceability markers, not acceptance conditions for this story**. Likewise Story 3.4's own criterion "when Epic 4 lands, it is refused at startup in a deployed component" is closed by Task 3 here.

One forward reference on the stage-2 fixed-order tuple, recorded so it is not mistaken for scope here. AD-8's navigation registry adds its own stage-2 refusal — every registered URL name must resolve in the URLconf, or `ImproperlyConfigured`, at the stage that has a resolved URLconf. It executes in `src/config/startup/stage_two.py` and Epic 9 appends it to this tuple when the composition step exists. It is **not** a tenth refusal condition and does not change the settled count of nine conditions and fourteen forbidden states: it validates a *contributed setting*, in the shape of Story 9.6's adoption-time gate conditions, rather than a forbidden state of the component's own configuration. Story 4.6 records the declaration half.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.3]
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — lines 310-328
- [Source: _bmad-output/planning-artifacts/epics.md#Cross-epic threads] — line 221: FR-41's refusal is implemented here; Epic 5 owns the release-stage contract
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-21]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-9]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-27]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-22]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-3
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-13]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-15]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.4] — the local sign-in module this condition resolves against

## Dev Agent Record

### Agent Model Used

claude-opus-5

### Debug Log References

- **`AppRegistryNotReady` on a module-scope `rest_framework.authtoken.views` import.** Verified before writing a line of the condition, because Task 2 asks for the import at module top level and that is not survivable here. `config.startup.stage_two` is imported twice before the application registry is populated -- once while a leaf settings module is still executing, through `config.startup.run_stage_one`, and once during app loading through `django_service/users/apps.py`. `rest_framework.authtoken.views` imports `rest_framework.authtoken.models`, which defines a model class, and defining one with an unready registry raises `django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet.` The same import after `django.setup()` succeeds and yields `obtain_auth_token`. Resolved by deferring the import into the condition body; see the Completion Notes for why that is not AD-24's conditional import. Six other candidate module-scope imports were probed the same way and all six are safe before `django.setup()`: `django.conf.settings`, `django.db.connections`, `django.db.migrations.executor`, `django.urls`, `django.urls.resolvers` and `config.local_dev`. `django.contrib.auth.models.Group` is the only other one that is not.
- **`inspect.unwrap(obtain_auth_token) is not obtain_auth_token`.** The failure Task 1 as written would have shipped, and it is silent: DRF's `APIView.as_view()` returns `csrf_exempt(view)`, `csrf_exempt` uses `functools.wraps`, so the object the URLconf holds carries `__wrapped__` and `inspect.unwrap` terminates at `View.as_view.<locals>.view` -- a closure in `django.views.generic.base`. An implementation that unwrapped to the terminal before comparing would have failed the identity comparison against `obtain_auth_token` on the one route the condition exists for, and would have resolved the defining module of *every* class-based view to `django.views.generic.base`. Resolved by walking every link of the chain and yielding all of them, plus each link's `view_class`, rather than collapsing to the terminal.
- **Two landed tests refused once the URLconf conditions existed.** `tests/unit/startup/test_no_network_no_queries.py` and `tests/integration/startup/test_no_queries.py` both call `run_stage_two()` with the locality declaration deleted. The whole suite runs in the `dev` pixi environment, which declares `COMPONENT_RUNTIME=local`, so `config/urls.py` had already mounted the local persona sign-in route when it was imported -- and stage 2 correctly refused it the moment those tests declared the run deployed. The refusal was right and the test state was wrong: a deployed locality asserted over a URL configuration built under a local one. Resolved by overriding `ROOT_URLCONF` in both, to a configuration a deployed component would actually serve.
- **`override_settings(DATABASES=...)` does not reach `django.db.connections`.** `settings.DATABASES` named both aliases while `connections["reporting"]` still raised `ConnectionDoesNotExist`; no `setting_changed` receiver refreshes the handler's `cached_property`. The integration file reconfigures the handler through its own public `configure_settings` and restores the mapping it held before.
- **`DatabaseOperationForbidden` on the second alias under the `django_db` marker.** The marker wraps a case in a `TestCase`, which forbids every alias it was not told about -- and `reporting` cannot be declared in `databases=[...]`, because it does not exist until the test body configures it. Resolved by taking the `django_db_blocker` fixture instead for the two cases that open their own connections, which lifts pytest-django's global guard and adds no `TestCase` semantics.
- **The ASGI probe inherited the autouse fixture's environment and never booted.** It failed with `AttributeError: module 'django.conf.global_settings' has no attribute 'ROOT_URLCONF'` raised while serving -- a misleading surface for the real cause. The file's autouse fixture deletes `COMPONENT_RUNTIME` and sets `COMPONENT_PROCESS` in `os.environ`, a child process inherits both, and `config/asgi.py` selects `config.settings.local`, which stage 1's FR-12 escape route refuses outright on a deployed run. The child was aborting during `django.setup()` and leaving `django.conf.settings` half-configured. Resolved by restoring `COMPONENT_RUNTIME=local` in the child's environment: it boots the way a developer's server boots and declares itself deployed and serving *after* it has served, which is the state the conditions are meant to be evaluated in.
- **The probe wrote into the repository's own `db.sqlite3`.** Its first version overrode `DATABASES` and then migrated, but the served request had already materialized the default connection wrapper, and replacing the handler's mapping does not reconfigure a wrapper that already exists -- so `migrate` and `provision_designated_groups` went to the local settings module's database file rather than to the scratch directory. Two `Group` rows (`probe-staff`, `probe-superuser`) and their permission links were written into a developer artifact and were deleted again by hand. Resolved by dropping and rebuilding the default wrapper inside the override, and the parent now asserts the database the probe actually migrated lives under its own `tmp_path`, so a recurrence fails the test rather than showing up in someone's local database.

### Completion Notes List

**The two deferred imports, and why AD-24 does not reach them.** Task 2 requires `obtain_auth_token` imported "at module top level (unconditional import -- AD-24 forbids `try/except ImportError`)". The prohibition is honoured; its placement is not, and it could not be: a module-scope import of `rest_framework.authtoken.views` -- or of `django.contrib.auth.models`, which the designated-group condition needs -- aborts every boot of this component with `AppRegistryNotReady`, because `config.startup.stage_two` is imported while a settings module is still executing and again during app loading. What AD-24 forbids is a *conditional* import and a `try`/`except ImportError`, both of which are feature-removal mechanisms: an import that may or may not happen, whose absence silently changes behaviour. These two always execute, exactly once, on every code path, with no guard of any kind around them; they are placed past a lifecycle boundary rather than behind a condition. Inside the condition bodies the registry is ready, because stage 2 runs from `AppConfig.ready()`. Both carry `# noqa: PLC0415` -- ruff's `PL` group is selected, and `import-outside-top-level` is a real rule here rather than a hypothetical one -- and the reason is written in the module docstring and again in each condition's docstring rather than only at the `noqa`.

**The sentinel stays where Story 4.1 put it, and Task 6's wording is what gives way.** Task 6 asks for `_STAGE_TWO_RAN` set "as the final statement, after all conditions pass". The landed 4.1 code sets it first, before the locality check, and its module docstring gives the reason in its own words: every developer and CI path runs local, so a record written after the `is_deployed()` early return would never be observed and `tests/integration/startup/test_stage_two_fires.py` would assert nothing. `tests/unit/startup/test_stage_dispatch.py` asserts the position directly. Moving it would break a landed acceptance criterion to satisfy a sentence in a later story's task list, so the landed behaviour is kept. Read literally the two are not even compatible: a sentinel written only after every condition passes says "this component is correctly configured", which is not what a boot-fired record is for.

**Test locations follow the tree, not the Source Tree table.** The table names `tests/unit/config/startup/` and `tests/integration/config/startup/`. Neither exists; the convention already in the repository is `tests/unit/startup/` and `tests/integration/startup/`, which is where Stories 4.1 and 4.2 put `test_stage_dispatch.py`, `test_stage_one_conditions.py`, `test_module_shape.py`, `test_stage_two_fires.py` and `test_no_queries.py`. The two new files join them there. Splitting the startup suite across two directory shapes would have been the worse of the two inconsistencies.

**The string in `_iter_view_callables`'s yielded tuple is the route, and nothing reads it.** Task 1 says never to yield `pattern.name`, `pattern.pattern` or `str(pattern)`, and the signature it specifies is `Iterator[tuple[str, Callable[..., object]]]` -- so the tuple has a string half that has to be something. It is the route's location, accumulated from the patterns above it, and it exists for one purpose: a refusal message that says *where* the forbidden route is mounted. An operator handed "a credential route is reachable" has been told nothing they can act on. No predicate reads it, and the module docstring and the function docstring both say so. The prohibition Task 1 is making is about predicates, and it holds absolutely.

**The walk yields more than one object per route, deliberately.** Three layers, and none subsumes the others: the callback as the URLconf holds it (the only thing `obtain_auth_token`'s identity comparison can match, since DRF built that object once at import time), every link of the `functools.wraps` chain beneath it (a decorator would otherwise hide a forbidden view), and each layer's `view_class` (which is what recognizes a *freshly built* `as_view()` product -- a different object every call, invisible to identity -- and what gives the defining-module predicate a class whose `__module__` is the view's own rather than `django.views.generic.base`). Task 1 asks for `inspect.unwrap`; collapsing to what it returns would have silently broken the identity comparison on the one route condition 6 exists for. See the Debug Log.

**The migrations condition iterates `settings.DATABASES` and never `"default"` alone, and the test proves it the only way that can be proved.** Both AC #6 halves place the fault on a *second* alias while `default` is healthy, because a fault on `default` cannot distinguish an implementation that iterates from one that reads `DATABASES["default"]` and stops. Stage 1's half is driven through `run_stage_one` with a two-alias namespace whose second alias is sqlite; stage 2's is driven against a real, never-migrated second connection. They are one test, because the claim is about the pair agreeing.

**Two landed test modules were amended, and their docstrings say why.** `tests/unit/startup/test_no_network_no_queries.py` and `tests/integration/startup/test_no_queries.py` both predicted this story would have to widen their query count. It did not: the number stays zero, because both new database conditions gate on `is_serving_process()` and no test process declares `COMPONENT_PROCESS` (AD-13 -- absent means *not* a serving process). Recording *why* zero is still right matters as much as changing it would have: a reader who finds the old prose would reasonably conclude the assertion went stale. What did have to change in both is the URL configuration they run stage 2 against -- see the Debug Log.

**`subprocess_env` in `test_stage_two_fires.py` was made public rather than copied.** Story 4.1 wrote it as `_subprocess_env`, and this story's own ASGI probe needs the identical environment: two spellings of "the way a server resolves this component" would drift, and the second one would stop proving anything about the first. The rename is the whole of the change to that file.

**Two shared test builders were added to `tests/conftest.py`, beside `valid_deployed_settings_namespace` and for its stated reason.** `temporary_root_urlconf` installs a throwaway URL configuration as a real module under `override_settings(ROOT_URLCONF=...)`, and `deployed_url_patterns` builds the admin-and-allauth configuration that is both the negative case and the baseline four other modules need. Three files across the unit and integration suites use them, two of which are landed modules this story amended; a `tests/unit/` home would have had to be copied.

**Not done, and deliberately.** `src/config/urls.py` is untouched -- the token route it once carried is Story 2.8's removal, and this condition is what makes the removal permanent. `src/django_service/users/apps.py` is untouched; Story 4.1 already calls `run_stage_two()` from `UsersConfig.ready()` and that was confirmed rather than changed. No entrypoint, pixi task or container command was added or modified: AD-22 and FR-41's release-stage contract are Epic 5's, and this story implements only the refusal. The local sign-in route is still mounted only where `config.locality.is_local()` answers true, which is Story 3.4's design and not a defect -- mounting it unconditionally would make every deployed component refuse to start. No code path here creates a `Group`.

**Gate result:** `pixi run ci` exits 0 -- pre-commit, build, mypy strict over `src/`, ruff over the tree, and the full suite at 96.79% coverage against a floor of 90%.

### File List

**New -- source**

*(none: Story 4.1 created `src/config/startup/stage_two.py` as the frame this story fills)*

**New -- tests**

| Path | Why |
|---|---|
| `tests/unit/startup/test_stage_two_urlconf.py` | Condition 6's two forbidden states, both AD-21/AD-26 evasion cases, the negative case, the roster order, and the walk's own properties -- cycle termination, `include()` descent, and an unresolvable defining module. |
| `tests/integration/startup/test_stage_two_database_conditions.py` | Condition 7 and the stage-2 half of condition 5 against real connections, the `COMPONENT_PROCESS` exemption, AC #6 across both stages, and the ASGI probe that drives every stage-2 condition from a process that has served a request. |

**Modified -- source**

| Path | Why |
|---|---|
| `src/config/startup/stage_two.py` | The story: `_iter_view_callables` and its `_walk`/`_view_candidates` helpers, the four condition functions, and the fixed-order `_STAGE_TWO` roster. The `is_deployed()` early return and the sentinel's position are preserved exactly as Story 4.1 left them. |

**Modified -- tests**

| Path | Why |
|---|---|
| `tests/conftest.py` | Added `temporary_root_urlconf` and `deployed_url_patterns`, the two builders the new tests and the two amended landed modules share. |
| `tests/unit/startup/test_no_network_no_queries.py` | Runs stage 2 against a deployed-shaped URL configuration rather than the local one this process holds, and records why the query count is still zero after this story. |
| `tests/integration/startup/test_no_queries.py` | The same two amendments, for the same two reasons, against a real connection. |
| `tests/integration/startup/test_stage_two_fires.py` | `_subprocess_env` renamed to `subprocess_env` so this story's probe reuses Story 4.1's environment rather than writing a second one. |
