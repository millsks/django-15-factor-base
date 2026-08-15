# Story 4.3: Three unconditional refusals evaluate at serving-process startup

Status: ready-for-dev

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

- [ ] Task 1 — Build the URLconf walker that yields view callables, not strings (AC: #1, #2)
  - [ ] Add `_iter_view_callables(urlconf: str | None = None) -> Iterator[tuple[str, Callable[..., object]]]` to `src/config/startup/stage_two.py`. Resolve the root URLconf with `django.urls.get_resolver(urlconf)` and recurse: for each entry in `resolver.url_patterns`, recurse into `URLResolver` (`include(...)`) and yield `pattern.callback` for each `URLPattern`.
  - [ ] Unwrap decorated views before comparison: follow `functools.wraps`-set `__wrapped__` chains with `inspect.unwrap`, and unwrap `django.views.generic.View.as_view()` products via their `view_class` attribute. A decorator applied to `obtain_auth_token` must not hide it.
  - [ ] Yield the callable object itself. **Never** yield or compare `pattern.name`, `pattern.pattern`, `str(pattern)`, or any dotted path derived from them.
  - [ ] Guard against a cyclic or self-referential include with a `seen` set keyed on `id(resolver)`, so the walk terminates.

- [ ] Task 2 — Condition 6, state a: a route whose view callable is `obtain_auth_token` (AC: #1, #2, #3)
  - [ ] `_refuse_credential_minting_route() -> None`. Import `rest_framework.authtoken.views.obtain_auth_token` at module top level (unconditional import — AD-24 forbids `try/except ImportError`) and refuse when any unwrapped view callable **is** that object, or is an instance/subclass product of `rest_framework.authtoken.views.ObtainAuthToken`.
  - [ ] Compare by object identity (`is`) and by `type` / `issubclass` on the view class. Do not compare `callable.__name__ == "obtain_auth_token"` and do not compare `callable.__module__` string literals — a re-export under another name is the evasion this closes.
  - [ ] `src/config/urls.py:39` routes `obtain_auth_token` today: `path("api/auth-token/", obtain_auth_token, name="obtain_auth_token")`, imported at `:11`. Epic 2 Story 2.8 removes it. This condition is what makes the removal permanent.
  - [ ] AC #3's test constructs a URLconf module that routes `obtain_auth_token` while the settings namespace is otherwise valid, and asserts the refusal — settings-correct, URLconf-wrong.

- [ ] Task 3 — Condition 6, state b: a route whose view callable belongs to the local sign-in module (AC: #1, #2)
  - [ ] `_refuse_local_sign_in_route() -> None`. Import the local sign-in module object created by Epic 3 Story 3.4 — a plain top-level `import`, producing a module object.
  - [ ] Predicate: for each unwrapped view callable, resolve its defining module with `inspect.getmodule(callable)` and refuse when that module object **is** the imported local sign-in module, or is a submodule of it (compare the imported module's `__name__` obtained *from the imported object*, never a hardcoded literal, and test `defining.__name__ == mod.__name__ or defining.__name__.startswith(mod.__name__ + ".")`).
  - [ ] **The evasion this blocks, stated explicitly (AD-21):** a route named `local_persona_login` mounted under `/accounts/` would satisfy AD-21 by name and pass an allowlist that already permits `/accounts/` for allauth. Any implementation that matches the route name or the path prefix is wrong and must be rejected in review.
  - [ ] **Shipping is not mounting (AD-21).** The local sign-in *module* is `core` and ships in every component; Story 3.4 mounts its *route* only where locality is local. So in a correctly configured deployed component this condition finds nothing to refuse — it is the backstop for a route reachable anyway, through a URLconf edit, a misconfiguration, or a locality that failed open. Do not read the condition as evidence the route is mounted everywhere, and do not "fix" Story 3.4 by mounting it unconditionally: that would make every deployed component refuse to start.
  - [ ] Story 3.4 declares the local sign-in route's URL name and path prefix as fixed constants in exactly one place, and Epic 7 moves that declaration into `accelerator.toml`. Those constants are **not** the predicate — they exist for the route's own construction and for the FR-17 allowlist (Story 4.6). This condition uses the module object only.
  - [ ] If Story 3.4 has not landed, implement against a `LOCAL_SIGN_IN_MODULE` constant in `src/config/startup/stage_two.py` holding the dotted path, imported once with `importlib.import_module` at module scope into a module object, and record in the Completion Notes that Story 3.4 must place its views in that module rather than declare a second location.

- [ ] Task 4 — Condition 7: unapplied migrations on a serving process, over every configured database (AC: #4, #6)
  - [ ] `_refuse_unapplied_migrations() -> None`. Gate on `is_serving_process()` — this is the **only** condition in the contract that is serving-process-only. Management commands must be exempt, because `manage.py migrate` is the one action that clears the condition and forbidding it deadlocks the FR-41 release stage.
  - [ ] For each alias in `django.conf.settings.DATABASES`, build a `django.db.migrations.executor.MigrationExecutor(connections[alias])` and refuse when `executor.migration_plan(executor.loader.graph.leaf_nodes())` is non-empty. Name the alias and the pending migrations in the message.
  - [ ] This is the one permitted query in the whole contract. NFR-1: "no query beyond migration state." Do not add a connectivity retry, a timeout wrapper, or a readiness-style poll.
  - [ ] Iterate every alias, including a contributed database's (AD-9). Do not special-case `"default"`.
  - [ ] FR-41 traceability: this condition is the *implementation* of the unapplied-migrations refusal. **Epic 5 owns the release-stage contract and the no-entrypoint-migrates property** — do not add or modify any entrypoint, task or container command here.

- [ ] Task 5 — Condition 5, stage-2 half: a designated group is absent from the database (AC: #5)
  - [ ] `_refuse_missing_designated_groups() -> None`. Gate on `is_serving_process()` alongside condition 7, since it too requires a live database.
  - [ ] Read the designated staff group name and superuser group name from the claims contract Epic 2 Story 2.2 declared — the same names Story 4.2's stage-1 half validates as configured. Refuse when either has no matching `django.contrib.auth.models.Group` row.
  - [ ] Use one query: `Group.objects.filter(name__in=[staff_group, superuser_group]).values_list("name", flat=True)`, and refuse naming exactly which of the two is missing.
  - [ ] AD-27's reasoning, which the message must reflect: "a misconfiguration must not present as a permissions bug." AD-12 already establishes that a claim naming a nonexistent `Group` is ignored and logged, never created — safe **only because** AD-27 guarantees the designated groups exist. This condition is that guarantee's enforcement.
  - [ ] The groups themselves are provisioned by a data migration inside `django_service`, seeded from the claims contract (Epic 2 Story 2.3). Do not create groups here; a refusal never repairs.

- [ ] Task 6 — Wire the conditions into `run_stage_two` in a fixed order (AC: all)
  - [ ] `run_stage_two()` returns immediately when `is_deployed()` is `False`. Then: the two URLconf conditions run for **any** deployed process; the two database conditions run only when `is_serving_process()` is `True`.
  - [ ] Record the order as a module-level tuple so a test can assert it (AD-26: one location, one owner, a fixed order).
  - [ ] Set the `_STAGE_TWO_RAN` sentinel from Story 4.1 as the final statement, after all conditions pass.
  - [ ] Every failure raises `ImproperlyConfigured`. No warning, no log-and-continue, no bare `except` (CG-3).

- [ ] Task 7 — Tests (AC: all)
  - [ ] `tests/unit/config/startup/test_stage_two_urlconf.py` — the two forbidden route states, plus the two evasion tests below.
  - [ ] **Evasion test A:** a URLconf routing the local sign-in view under `path("accounts/local-sign-in/", view, name="local_persona_login")` still refuses. Asserts the predicate is not prefix-matching.
  - [ ] **Evasion test B:** a URLconf routing `obtain_auth_token` re-exported under a different module attribute name and a different route name still refuses. Asserts the predicate is not name-matching.
  - [ ] **Negative test:** a URLconf containing only allauth and admin routes passes. Without it a predicate that refuses everything would pass every refusal test.
  - [ ] `tests/integration/config/startup/test_stage_two_database_conditions.py` — `@pytest.mark.integration`. The unapplied-migrations refusal against a second configured alias; the exemption when `COMPONENT_PROCESS` is absent; the missing-designated-group refusal; the pass case with both groups present.
  - [ ] AC #6: one test asserting that with two aliases configured and the *second* holding the fault, both the stage-1 sqlite condition (Story 4.2) and this story's migrations condition refuse. Proves neither reads `DATABASES["default"]` alone.
  - [ ] Each stage-2 condition needs at least one test exercising it through a served request path, not only through `manage.py` — Story 4.5 owns that audit; satisfy it here by reusing the ASGI-driven fixture Story 4.1 created at `tests/integration/config/startup/test_stage_two_fires.py`.

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

### Debug Log References

### Completion Notes List

### File List
