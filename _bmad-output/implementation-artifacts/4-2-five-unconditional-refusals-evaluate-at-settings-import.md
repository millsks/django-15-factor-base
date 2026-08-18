---
status: done
baseline_revision: 9bcbb281f1c68780d55995bbca8113ed6e40d70a
context: []
warnings: []
---

# Story 4.2: Five unconditional refusals evaluate at settings import

Status: done

## Story

As a platform engineer,
I want every forbidden state readable from settings alone refused at settings import,
so that a deployed component with local convenience configured never reaches a serving state.

## Acceptance Criteria

**Traceability:** FR-13 (stage 1) · AD-26 · CG-3 · SC-5

1. **Given** the sqlite backend is reached in a deployed component
   **When** settings are imported
   **Then** `ImproperlyConfigured` is raised
   **And** the existing check at `production.py:26-28` is the mechanism

2. **Given** a local credential path live in settings
   **When** settings are imported
   **Then** `ImproperlyConfigured` is raised for each of four states: `ModelBackend` present in `AUTHENTICATION_BACKENDS`; a non-empty `ACCOUNT_LOGIN_METHODS`; `DJANGO_ADMIN_FORCE_ALLAUTH` not true; and `rest_framework.authtoken` installed or `TokenAuthentication` in the DRF defaults

3. **Given** `OTEL_SDK_DISABLED` is true in a deployed component
   **When** settings are imported
   **Then** `ImproperlyConfigured` is raised, because the component has silently opted out of an immovable guarantee

4. **Given** a JWKS location not derived from the configured IdP issuer
   **When** settings are imported
   **Then** `ImproperlyConfigured` is raised
   **And** this catches a component anchored to a key generated onto a developer's laptop, with no key file present at all

5. **Given** no identity-key claim, no group-claim name, or no designated staff group
   **When** settings are imported
   **Then** `ImproperlyConfigured` is raised
   **And** no conventional claim name is defaulted in its place

## Tasks / Subtasks

- [x] Task 1 — Condition 1: the sqlite backend is reached, over *every* configured database (AC: #1)
  - [x] Move the existing check at `src/config/settings/production.py:26-28` into `src/config/startup/stage_one.py` as `_refuse_sqlite(databases: dict[str, dict[str, object]]) -> None`, iterating **every** alias in `DATABASES`, not only `"default"` (AD-9). The message names the offending alias.
  - [x] Leave `production.py:26-28` in place as-is. AC #1 states it is the mechanism, and it must keep firing before line 29 (`DATABASES["default"]["CONN_MAX_AGE"] = …`) which assumes a real backend. Stage 1 then re-evaluates the same condition over all aliases as the last statement of the module; the two are consistent by construction because both raise on the same predicate.
  - [x] Predicate: `str(config.get("ENGINE", "")).endswith("sqlite3")`. This is a settings-value inspection, not a route or callable, so string comparison is correct here — AD-26's "predicates resolve objects, never strings" governs the URLconf conditions in Story 4.3, not settings scalars.
  - [x] Where a contributed database's alias appears (AD-9, Epic 9), it is iterated identically; no alias is exempt.

- [x] Task 2 — Condition 2: a local credential path is live in settings — four distinct forbidden states (AC: #2)
  - [x] `_refuse_local_credential_paths(module: ModuleType) -> None` in `src/config/startup/stage_one.py`. Each of the four states raises its own `ImproperlyConfigured` with its own message; do not collapse them into one aggregated error, because FR-16 requires each to be testable separately.
  - [x] State 2a — `ModelBackend`: refuse when any entry of `AUTHENTICATION_BACKENDS` resolves to `django.contrib.auth.backends.ModelBackend` or a subclass of it. Resolve each dotted path with `django.utils.module_loading.import_string` and test with `issubclass`, not `in` on the string list — a subclass re-exported under another name is the evasion this closes.
  - [x] State 2b — `ACCOUNT_LOGIN_METHODS`: refuse when the value is a non-empty collection. `base.py:340` sets `{"username"}` today.
  - [x] State 2c — `DJANGO_ADMIN_FORCE_ALLAUTH`: refuse when the value is anything other than `True`. Absent counts as not true and refuses. `base.py:271` defaults it `False` today.
  - [x] State 2d — the static-token surface: refuse when `"rest_framework.authtoken"` is in `INSTALLED_APPS`, **or** when any entry of `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` resolves to `rest_framework.authentication.TokenAuthentication` or a subclass. Resolve with `import_string` + `issubclass`, same reasoning as 2a. One condition, one raise, but the test suite covers both halves.
  - [x] Read each name off the module object passed to `run_stage_one` using `getattr(module, name, <sentinel>)`, never from `django.conf.settings` — settings are not populated while the module is still executing.

- [x] Task 3 — Condition 3: `OTEL_SDK_DISABLED` (AC: #3)
  - [x] `_refuse_otel_disabled() -> None`. Read `OTEL_SDK_DISABLED` from `os.environ` — it is an OpenTelemetry SDK environment variable, not a Django setting, and `src/config/observability/telemetry.py` does not mirror it into settings.
  - [x] Refuse when the value, lower-cased and stripped, is `"true"`. That is the SDK's own truthiness rule; do not invent a wider one that would refuse on `"0"`.
  - [x] Message states the reasoning: a deployed component setting it has silently opted out of an immovable guarantee (FR-13).

- [x] Task 4 — Condition 4: the JWKS trust anchor is not derived from the configured IdP issuer (AC: #4)
  - [x] `_refuse_untrusted_jwks_anchor(module: ModuleType) -> None`. Read the configured OIDC issuer and the configured JWKS location from the settings names Epic 2 Story 2.7 established. **Do not invent names and do not create a second declaration site (AD-1)** — import the constants from `src/config/authorization/` if that module exposes them, otherwise `getattr` the settings names it sets. If Story 2.7 has not landed, define the two names here and record in the Completion Notes that Story 2.7 must consume them rather than declare its own.
  - [x] Predicate: parse both values with `urllib.parse.urlsplit` and refuse unless the JWKS URL's `scheme` is `https` **and** its `netloc` equals the issuer's `netloc` **and** its `path` begins with the issuer's `path`. Refuse when either value is absent or empty.
  - [x] This is the condition that catches a component pointed at a locally generated development key by environment variable **with no key file present at all** — so it must not look at the filesystem. Do not add an existence check on any key path.
  - [x] No network call: never fetch the issuer's discovery document to confirm the JWKS URL (NFR-1, and FR-23's no-network-at-boot property).

- [x] Task 5 — Condition 5 (stage-1 half): the claims contract is unconfigured (AC: #5)
  - [x] `_refuse_unconfigured_claims_contract(module: ModuleType) -> None`. Refuse when any of the four claims-contract values is absent or empty: the identity-key claim name, the group-claim name, the staff-conferring group, the superuser-conferring group.
  - [x] Same single-declaration rule as Task 4: read the names Epic 2 Story 2.2 established. Story 2.2's AC says "no conventional claim name is defaulted in its place" — so the settings reads must have **no default**; an absent variable must produce an absent value that this condition then refuses, not a fallback of `"sub"`, `"groups"` or `"realm_access.roles"`.
  - [x] This is the stage-1 half of condition 5 in the refusal table. Its stage-2 half — a designated group absent from the database (AD-27) — belongs to Story 4.3 and must not be implemented here: stage 1 may issue no query at all (NFR-1).

- [x] Task 6 — Wire the five conditions into `run_stage_one` (AC: all)
  - [x] `run_stage_one` returns immediately when `is_deployed()` is `False`, then calls the escape-route condition from Story 4.1 followed by the five conditions above, in a fixed declared order. AD-26 requires "one location, one owner, and a fixed order"; record the order as a module-level tuple so a test can assert it.
  - [x] Every failure raises `django.core.exceptions.ImproperlyConfigured`. No `warnings.warn`, no `structlog` log-and-continue, no `except … : pass` (CG-3).
  - [x] Messages carry the setting or environment variable name and the value that was rejected — never a secret value. `SECRET_KEY`, tokens and passwords are never read by any of these conditions and must not appear in any message (NFR-7).

- [x] Task 7 — Tests (AC: all)
  - [x] `tests/unit/config/startup/test_stage_one_conditions.py` — one test per forbidden state: sqlite (default alias), sqlite (a second configured alias), `ModelBackend`, non-empty `ACCOUNT_LOGIN_METHODS`, `DJANGO_ADMIN_FORCE_ALLAUTH` not true, `authtoken` installed, `TokenAuthentication` in DRF defaults, `OTEL_SDK_DISABLED=true`, JWKS anchor mismatch, each of the four missing claims-contract values.
  - [x] Each test builds a `types.SimpleNamespace` or a `types.ModuleType` carrying only the names the condition reads, sets `COMPONENT_RUNTIME` absent via `monkeypatch.delenv`, calls `run_stage_one(module)` and asserts `pytest.raises(ImproperlyConfigured)`.
  - [x] Add the positive case: a fully valid deployed namespace passes `run_stage_one` without raising. Without it, a condition that raises unconditionally would pass every refusal test.
  - [x] Add a subclass-evasion test for 2a and 2d: a locally defined subclass of `ModelBackend` and of `TokenAuthentication`, referenced by its own dotted path, still refuses.
  - [x] `tests/unit/test_settings.py` already covers `production.py`'s sqlite refusal; extend rather than duplicate it, following its `_evict_settings_modules` fixture (`tests/unit/test_settings.py:24-30`).

## Dev Notes

### Architecture Constraints

- **AD-26:** the refusal contract is one module, `src/config/startup/`, with one location, one owner and a fixed order. Stage 1 is the last statement of every **leaf** settings module — `local.py`, `production.py`, `test.py` — "which places it after the AD-8 composition step by construction and is why AD-9's iteration over every configured database is reachable." **`base.py` must not call it**; Story 4.1 places the calls and the paired gate test. This matters directly here: `base.py` configures four of the five states this story refuses, so a stage-1 call there would fire before the leaf composes and refuse in every combination.
- **AD-9 (binding rule):** "The stage-2 unapplied-migrations refusal and the sqlite refusal both iterate every configured database — which is only possible because stage 1 runs *after* composition (AD-26)." This is why Task 1 iterates aliases rather than reading `DATABASES["default"]`.
  **Prevents:** "six enforcement points each being answered differently by six epics."
- **AD-1:** every declaration has exactly one site. The claims-contract setting names and the OIDC issuer / JWKS location setting names are Epic 2's declarations; this story consumes them and must not re-declare them.
- **AD-23:** "The trust anchor is derived from the configured OIDC issuer; a JWKS location not derived from it is refused at startup. **That check is syntactic and can be nothing else.**" Condition 4 is that refusal, and its scope is exactly that: a string-derivation rule over the configured issuer. "Derived from" is not "confirmed against" — verifying the JWKS location against the issuer's published discovery document would require fetching it, which is the boot-time network call FR-23 forbids. An issuer whose real `jwks_uri` does not match the derivation surfaces on the **first Bearer request, not at boot** (recorded as L-4). Do not widen this condition to close that gap.
- **CG-3:** "Do not soften a refusal into a warning. A refusal that logs and continues makes deployment smoother and puts local credentials into production."
- **NFR-1:** "The nine checks are settings and URL-configuration inspection with no network call and no query beyond the migration state." **Stage 1 issues zero queries.**
- **NFR-7:** secrets never live in source and never appear in a refusal message.
- **AD-24 forbids** conditional imports and `try/except ImportError` inside these conditions. Every import in `src/config/startup/stage_one.py` is unconditional and top-level; the two feature-scoped conditions of Story 4.4 are delimited by paired line comments instead.

### The settled refusal count

Reproduced from `_bmad-output/planning-artifacts/epics.md:310-328`. **Nine conditions — seven unconditional, two conditional — across fourteen distinct forbidden states**, each tested separately under FR-16.

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

This story owns conditions 1, 2, 3, 4 and the stage-1 half of 5 — **eight of the fourteen forbidden states**. Conditions 6, 7 and the stage-2 half of 5 are Story 4.3. Conditions 8 and 9 are Story 4.4. The arithmetic is settled: FR-13's prose says "seven conditions" and lists eight bullets, and AD-27 adds a state absent from every bullet; the table above is the resolution and is authoritative for this epic.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/startup/stage_one.py` | UPDATE | Created as a skeleton by Story 4.1 with `run_stage_one` and the FR-12 escape-route condition. **Change:** add the five condition functions and the fixed-order tuple. **Preserve:** the escape-route condition and the `is_deployed()` early return. |
| `src/config/settings/production.py` | UPDATE (no functional change) | `:26-28` is confirmed present today and is exactly the sqlite refusal; leave it untouched. It fires before `:29` (`DATABASES["default"]["CONN_MAX_AGE"] = env.int(...)`), which is why it cannot simply be deleted in favour of the stage-1 copy. |
| `tests/unit/config/startup/test_stage_one_conditions.py` | NEW | One test per forbidden state, plus the positive case and the two subclass-evasion cases. |
| `tests/unit/test_settings.py` | UPDATE | Today: fresh-import tests for `base`/`local`/`production`, including the `production.py` sqlite refusal, with the `_evict_settings_modules` autouse fixture at `:24-30` and a `no_database_env` fixture at `:33-37`. **Change:** extend with the deployed-namespace cases this story adds. **Preserve:** the eviction fixture semantics — without it `from .base import *` reuses an already-imported `config.settings.base` and module-level env reads are not re-evaluated. |

**Verified against the repository (2026-08-15):**

- `src/config/settings/production.py:26-28` — the sqlite refusal, present and matching the epic's citation exactly.
- `src/config/settings/base.py:133-136` — `AUTHENTICATION_BACKENDS` contains `django.contrib.auth.backends.ModelBackend`. **Forbidden state 2a is live today.**
- `src/config/settings/base.py:340` — `ACCOUNT_LOGIN_METHODS = {"username"}`. **State 2b is live today.**
- `src/config/settings/base.py:271` — `DJANGO_ADMIN_FORCE_ALLAUTH = env.bool("DJANGO_ADMIN_FORCE_ALLAUTH", default=False)`. **State 2c is live today** (FR-7 requires the default to become true; that is Epic 2's change, not this story's).
- `src/config/settings/base.py:112` — `"rest_framework.authtoken"` in `THIRD_PARTY_APPS`; `:357-364` — `TokenAuthentication` in `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`. **State 2d is live today, both halves.**

**Sequencing consequence.** Epic 2 Story 2.8 ("The static-token credential surface is removed entirely") and Story 2.6 (FR-7, `DJANGO_ADMIN_FORCE_ALLAUTH` defaults true) remove states 2a–2d from `base.py`. If this story is implemented before those land, `pixi run ci` will fail the moment the stage-1 call is reached under a deployed configuration. That is the correct behaviour, not a bug in this story — but the dev agent must not "fix" it by softening a condition, exempting `base.py`, or gating a condition behind a flag. If Epic 2 has not landed, complete this story's conditions and tests, and record the blocked gate in the Completion Notes.

**Does not exist yet:** `src/config/authorization/` (Epic 2) — the source of the claims-contract and JWKS setting names.

### Testing Requirements

- `tests/unit/config/startup/test_stage_one_conditions.py`, mirroring `src/config/startup/`. Unit tests only — stage 1 touches no database, no filesystem and no network, so nothing here needs `@pytest.mark.integration`.
- Fourteen forbidden states exist in total; this story's suite must cover eight of them, each as its own test function with its own assertion on `ImproperlyConfigured`. Story 4.5 audits that the full fourteen are covered.
- Assert on the exception *type* and on a distinguishing substring of its message (the setting or variable name), so two conditions cannot pass each other's test.
- Add a no-network assertion for condition 4: patch `socket.socket` to raise and confirm `run_stage_one` completes.
- Add a zero-query assertion for the whole of stage 1 using `django.test.utils.CaptureQueriesContext`.
- AD-20: ninety percent including templates, `COVERAGE_CORE=ctrace` (`pixi.toml:145-151`). Do not add `src/config/startup/` to `[tool.coverage.run] omit` (`pyproject.toml:160-168`) — that list is a closed carrier-declared surface.
- `pixi run test` for the inner loop; `pixi run ci` is the done condition.

#### Project Structure Notes

Consistent with the Structural Seed: `src/config/settings/` is annotated "base + local + production + test; composition, then stage 1 last (AD-8, AD-26)", and `src/config/startup/` is "both refusal stages + the FR-17 allowlist (AD-26)". No variance.

One structural note worth recording: `src/config/settings/base.py:296-335` is the Celery block — `:296` is the `# Celery` header and `:335` is `CELERY_WORKER_HIJACK_ROOT_LOGGER`, the block's last line. AD-24 now cites that extent correctly; an earlier revision cited `:296-313`, which would have left `CELERY_BEAT_SCHEDULER` behind in every combination with no `django_celery_beat`. This story does not touch that block — Story 4.4 and Epic 7 do — but the corrected extent is recorded so the region markers are placed against it.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.2]
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — lines 310-328
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-9]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-23]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-13]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#CG-3]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.2] — the claims contract read from the environment, with no default
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.8] — removal of the static-token credential surface

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m]

### Debug Log References

None. `pixi run ci` passed on the first full run; no triage report was generated.

### Completion Notes List

**All five conditions landed on the roster delivered by Story 4.1.** `_STAGE_ONE`
in `src/config/startup/stage_one.py` is now six entries — FR-12's escape route
followed by conditions 1 to 5 of the refusal table, in the table's own order.
Nothing was added as a direct call inside `run_stage_one`, so the dispatch keeps
one shape and `tests/unit/startup/test_stage_dispatch.py`'s calling convention
holds unchanged.

**Deviation 1 — condition signatures.** Task 1 and Task 3 write
`_refuse_sqlite(databases: dict[...])` and `_refuse_otel_disabled()`. The
delivered roster is `tuple[Callable[[ModuleType], None], ...]` and
`test_stage_dispatch.py::test_stage_one_passes_the_settings_module_to_every_condition`
pins that convention. Every condition therefore takes the settings module:
`_refuse_sqlite(settings_module: ModuleType)`, and
`_refuse_otel_disabled(_settings_module: ModuleType)` with the leading underscore
that says the parameter is unread and keeps ruff `ARG001` satisfied.

**Deviation 2 — `OTEL_SDK_DISABLED` is not read inside `src/config/startup/`.**
Task 3 says to read it from `os.environ` in `stage_one.py`. That is impossible
as written: `tests/unit/startup/test_module_shape.py::test_no_module_in_the_package_reads_the_environment_itself`
asserts by AST scan that no module in the package imports `os` at all, and that
gate was delivered by Story 4.1. `src/config/observability/telemetry.py` already
owned the read, so its `_is_disabled()` was renamed to a public
`otel_sdk_is_disabled()` with its behaviour unchanged byte for byte, its one
internal caller updated, and its docstring restated to say it is now also the
reader stage-1 condition 3 consumes. The variable name itself is now a module
constant, `OTEL_SDK_DISABLED_ENV_VAR`, so the refusal message and the read cannot
spell it differently.

**Deviation 3 — condition 3 refuses on `1` and `yes` as well as `true`.** Task 3
says to match only `"true"` and not to invent a wider rule. Reusing the delivered
reader widens it, deliberately: `telemetry.py` is what decides whether tracing is
installed, and it treats `true`, `1` and `yes` alike. A refusal matching only
`"true"` would leave `OTEL_SDK_DISABLED=1` disabling tracing in a deployed
component with nothing refusing it — a hole exactly the size of the guarantee.
`0` and `false` still do not refuse, which is what the narrower rule was
protecting. Recorded in the condition's own docstring and covered both ways in
the tests.

**Deviation 4 — states 2a and 2d compare dotted paths rather than resolving them
with `import_string` + `issubclass`.** This is the largest deviation in the
story and it has two independent causes, either of which alone would be
decisive.

*It cannot be evaluated at settings-import time.* Stage 1 runs inside
`apps.populate(settings.INSTALLED_APPS)`, before the app registry is ready.
`django.contrib.auth.backends` imports `django.contrib.auth.models`, and defining
a model class with an unready registry raises `AppRegistryNotReady`. Verified
directly against this environment: `import_string("django.contrib.auth.backends.ModelBackend")`,
`import_string("allauth.account.auth_backends.AuthenticationBackend")` and
`import_string("config.authorization.authentication.OIDCBearerAuthentication")`
all raise `AppRegistryNotReady` with no app registry, while
`rest_framework.authentication.TokenAuthentication` and `SessionAuthentication`
resolve. A resolving condition would pass this repository's unit suite —
pytest-django completes `django.setup()` during collection, so the registry *is*
ready there — and then abort a real deployed boot with `AppRegistryNotReady`
rather than the `ImproperlyConfigured` CG-3 requires. That is the worst possible
shape for a defect: green in CI, wrong in production.

*`issubclass` is also the wrong predicate.* `allauth.account.auth_backends.AuthenticationBackend`
**is** a `ModelBackend` subclass — asserted mechanically in
`test_the_backend_a_deployed_component_keeps_is_accepted_though_it_subclasses_model_backend`
rather than claimed in a comment. It is also the one backend a deployed
component must keep, because every IdP sign-in goes through it. A rule refusing
`ModelBackend` subclasses refuses the correct configuration, so identity is the
only rule that separates the forbidden entry from the required one.

The consequence is stated rather than left to be discovered, in the module, in
the condition docstring and in the test: a `ModelBackend` or `TokenAuthentication`
subclass re-exported under another dotted path is **not** refused by condition 2.
Closing that evasion is FR-17's allowlist, Story 4.6, which AD-26 already
specifies as holding **objects, not dotted strings** and which for that reason
has to run where objects can be resolved. Story 4.6 should treat this as a
requirement it inherits rather than an option.

**Deviation 5 — test module location.** The spec says
`tests/unit/config/startup/test_stage_one_conditions.py`. The repository's
convention drops the `config` segment: startup tests live in
`tests/unit/startup/` and authorization tests in `tests/unit/authorization/`. The
module was written at `tests/unit/startup/test_stage_one_conditions.py`.

**Deviation 6 — Task 5's setting names come from Epic 2, which has landed.** The
spec's "Does not exist yet: `src/config/authorization/`" is stale.
`CLAIMS_CONTRACT`, `CLAIMS_ENVIRONMENT_VARIABLES`, `ClaimsContract.is_configured`,
`OIDC_ISSUER`, `OIDC_JWKS_URL` and `jwks_url_derives_from_issuer` all exist and
are consumed rather than re-declared (AD-1). Nothing new was declared here.

**Deviation 7 — Task 4's predicate was not re-derived.** Task 4 spells out a
`urlsplit` rule. `config.authorization.jwks.jwks_url_derives_from_issuer` is
already exactly that rule, already never raises, and its own docstring names
Epic 4 as its consumer. It is imported. What did have to change is the
explicit-or-conventional fallback: `configured_jwks_url()` reads
`django.conf.settings`, which is unpopulated while a settings module is
executing, so the fallback was extracted into a pure `resolve_jwks_url(explicit,
issuer)` that `configured_jwks_url()` now delegates to and that stage 1 calls
with values read off the module. One declaration of the fallback rule, two
readers.

**Deviation 8 — `_bmad-output/implementation-artifacts/deferred-work.md`'s
distinctness question is answered NO.** The Story 2.2 review asked whether
`COMPONENT_STAFF_GROUP == COMPONENT_SUPERUSER_GROUP` belongs in refusal condition
5. It does not, for three reasons. AC #5 scopes condition 5 to values that are
*absent*, and a contract whose two group names are equal has four present values.
The refusal-count table is authoritative for this epic at fourteen forbidden
states, and Story 4.5 audits exactly that number — a fifteenth added quietly here
would break that audit rather than extend it. And `is_configured` is the
predicate the spec pins condition 5 to; widening it, or introducing a second
`is_usable` beside it, is a change to the contract Epic 4 is written against and
belongs to whoever owns that decision. `deferred-work.md` was not edited.

**Forbidden states 2a and 2b are live in `base.py` today, and this story did not
soften anything to accommodate them.** `base.py:203-206` still lists
`django.contrib.auth.backends.ModelBackend` in `AUTHENTICATION_BACKENDS`, and
`base.py:431` still sets `ACCOUNT_LOGIN_METHODS = {"username"}`. Epic 2's Story
2.6/2.8 own removing them. States 2c and 2d are already resolved:
`base.py:362` defaults `DJANGO_ADMIN_FORCE_ALLAUTH` true, and neither half of the
static-token surface remains. The gate stays green because pixi's `dev` feature
sets `COMPONENT_RUNTIME=local` (`pixi.toml:435-436`), so `run_stage_one` returns
at the `is_deployed()` check for the whole suite. A deployed boot against
`base.py` as it stands would refuse on 2a, which is the correct behaviour and not
a defect in this story.

**Two existing fixtures had to be rewritten, and a third case besides.** Both
`tests/unit/startup/test_no_network_no_queries.py` and
`tests/integration/startup/test_no_queries.py` built a bare
`ModuleType(PRODUCTION_SETTINGS_MODULE)` and called `run_stage_one` under
deployed locality; against six conditions a bare namespace refuses on the first
one, before a socket or a cursor could be reached, so both assertions would have
passed over code that never ran.
`tests/unit/startup/test_stage_one_escape_route.py::test_a_deployed_component_importing_a_deployed_settings_module_is_accepted`
had the same shape and was not listed in the brief; it was found and fixed the
same way. The valid namespace is built once, by
`valid_deployed_settings_namespace()` in `tests/conftest.py`, because the unit
suite and the integration suite both need it and a copy in each would drift the
first time Story 4.3 or 4.4 adds a condition. No assertion was weakened anywhere.

**Stage 1 is asserted through a real settings import, not only through synthetic
namespaces.** `tests/unit/startup/test_stage_one_conditions.py` drives every
per-condition case against a namespace built in a fixture, which is the right
shape for saying what each condition refuses and is structurally incapable of
saying that the call site Story 4.1 placed as the last statement of
`production.py` reaches the roster at all, with the values `base.py` and
`production.py` actually composed onto the module. Two cases in
`tests/unit/test_settings.py` close that, reusing its existing
`_evict_settings_modules` and `production_env` fixtures rather than declaring
new ones:

- `test_a_deployed_production_import_is_refused_by_stage_one` — a fresh
  `importlib.import_module("config.settings.production")` with `DATABASE_URL`
  set (so `production.py:26-28` cannot fire first and stop the module before its
  last statement) and `COMPONENT_RUNTIME` deleted raises `ImproperlyConfigured`
  from stage 1. **Caveat, and it is written into the test's docstring rather
  than left here:** the condition it currently catches is state 2a, because
  `base.py:203-206` still lists `ModelBackend`. The assertion names
  `AUTHENTICATION_BACKENDS` and the `ModelBackend` path deliberately, so the
  test says *which* condition fired. It will therefore fail when Epic 2 Story
  2.6/2.8 removes that entry, and the docstring states the fix: move the
  assertion forward to state 2b (`ACCOUNT_LOGIN_METHODS` at `base.py:431`, the
  same story), and after that to condition 4's unset `OIDC_ISSUER`, which is a
  real deployment requirement rather than a leftover. A bare
  `pytest.raises(ImproperlyConfigured)` was rejected precisely because it would
  stay green through all of those transitions and read as proof the whole
  contract holds when it only ever proves the first live condition holds.
- `test_a_local_production_import_reaches_stage_one_and_is_accepted` — the same
  fresh import with `COMPONENT_RUNTIME` set to `local` does not raise, because
  every condition is deployed-only. Without it the case above would pass equally
  against a `run_stage_one` that raised unconditionally. Locality is declared
  explicitly rather than inherited from the pixi `dev` feature, so the case
  states the condition it depends on.

No deployed-environment matrix was added there; the per-condition coverage stays
in one place.

**Condition 1 refuses `DATABASES` it can see and nothing wider.** A namespace with
no `DATABASES` at all returns rather than refusing: it never reaches sqlite, and
Django's own `ConnectionHandler` already raises `ImproperlyConfigured` for a
mapping with no `default` alias. Covered by a test that says so, rather than left
as an uncovered branch.

**`production.py:26-28` was left exactly as it is**, per Task 1. It fires before
`:29` sets `CONN_MAX_AGE`, which assumes a real backend, and the stage-1 copy is
the general form over every alias. Both raise on the same predicate, so they are
consistent by construction.

**No new import weight at settings-import time that was not already paid**, with
one exception worth recording: `stage_one.py` now imports
`config.authorization.jwks`, which was previously reached only through DRF's
lazy resolution of the Bearer class. `jwks.py` binds `django.conf.settings` as an
object rather than reading it, constructs `KEY_STORE` without fetching, and
imports no Django model, so it is safe at settings-import time —
`tests/unit/test_no_network_at_boot.py` still passes unchanged, including its
assertion that the key store holds nothing after boot.

### Review pass — patches applied

Three adversarial review passes ran on the diff. Seven findings survived triage
as *patch* and are implemented here; each has a test that fails without it.

1. **An absent `AUTHENTICATION_BACKENDS` defeated state 2a.** The condition read
   `getattr(..., ())`, so a settings module that never declared the name passed —
   and then ran on `django.conf.global_settings.AUTHENTICATION_BACKENDS`, which
   *is* `['django.contrib.auth.backends.ModelBackend']`. Deleting the line is a
   plausible way to "remove `ModelBackend`" from `base.py:203-206`, and it would
   have reinstated the state. Absence now refuses, with a message naming the
   global default as the reason. The test asserts the default against Django
   itself rather than quoting it.
2. **An absent `ACCOUNT_LOGIN_METHODS` defeated state 2b** identically: allauth
   falls back to its own default and resolves `LOGIN_METHODS` to the username
   method, leaving the local form reachable. Absence now refuses.
3. **State 2d was escapable by spelling.** `rest_framework.authtoken.apps.AuthTokenConfig`
   installs the same app and slipped past an equality test on the module path.
   Matching is now the bare path or any dotted path beneath it; the separator in
   the prefix is what keeps a hypothetical `rest_framework.authtoken2` out, and a
   test pins that too.
4. **The sqlite predicate missed the GIS backend while its comment claimed
   otherwise.** `django.contrib.gis.db.backends.spatialite` does not end in
   `sqlite3`. `_SQLITE_ENGINE_SUFFIXES` is now a tuple of both; the predicate was
   fixed rather than the comment, and spatialite is covered on a second alias —
   a GIS alias beside a PostGIS `default` being the shape it plausibly takes.
5. **The "resolves to nothing" refusal named the wrong variable.** That branch is
   reachable only when the explicit location is unset *and* the issuer derives
   none, yet the message told the operator to leave `COMPONENT_OIDC_JWKS_URL`
   unset — which is what they had already done — and never named
   `COMPONENT_OIDC_ISSUER`, the variable actually at fault. Rewritten to name the
   issuer as the cause; the test asserted only `"OIDC_JWKS_URL"` and so locked the
   misdirection in, and now asserts the issuer variable is named and the
   misdirection is absent.
6. **`zip(..., strict=True)` could raise `ValueError` out of a condition contracted
   to raise `ImproperlyConfigured` and nothing else.** `isinstance` admits a
   `ClaimsContract` subclass, and a fifth dataclass field made the pairing strict
   zip raise. The field/variable count is now compared explicitly, **above** the
   `is_configured` early return — placement matters, because a populated
   five-field contract returns early and never reaches the zip while a
   half-configured one does. `strict=True` stays as the belt. Two tests, one for
   each of those two shapes.
7. **Refusal messages could echo a credential (NFR-7).** `_refuse_untrusted_jwks_anchor`
   interpolated the raw issuer and JWKS location; a URL carrying userinfo
   (`https://user:pw@idp…`) or a query-string token would land verbatim in a boot
   failure and from there into deployment logs. A `_redacted()` renderer now keeps
   scheme, host, port and path and drops userinfo, query and fragment. It is
   message rendering only — the predicate is still handed the location as
   configured, so no second derivation rule was introduced.

Folded in alongside 1 and 3, from the edge-case pass: `AUTHENTICATION_BACKENDS`,
`ACCOUNT_LOGIN_METHODS`, `INSTALLED_APPS`, `REST_FRAMEWORK` and its class list
declared as `None` or as a non-iterable escaped as `TypeError`, breaking the same
"only `ImproperlyConfigured`" promise. One shared `_as_roster` guard handles it,
and it closes a second hole in the same move: a **bare string** is iterable, so
`AUTHENTICATION_BACKENDS = "…ModelBackend"` would have been read one character at
a time and matched nothing — a typo presenting as a clean configuration.

Two things worth recording that came out of the patching rather than the review:

- **Absence is now judged against the framework default, not treated uniformly.**
  `AUTHENTICATION_BACKENDS`, `ACCOUNT_LOGIN_METHODS` and `DJANGO_ADMIN_FORCE_ALLAUTH`
  refuse when absent because what they fall back to *is* the forbidden state;
  `INSTALLED_APPS` and DRF's class list read as empty when absent because their
  defaults name nothing forbidden. The asymmetry is deliberate and is stated in
  the condition docstring, with a test pinning both sides — a future reader
  "simplifying" it either way breaks a test that explains itself.
- **`_redacted` suppresses the whole location when the authority will not parse.**
  An out-of-range port makes `SplitResult.port` raise `ValueError`; the renderer
  returns `<unreadable location>` rather than a partial reconstruction. That is
  the fail-safe direction — a location that cannot be parsed cannot be shown to
  be secret-free — and it costs a little diagnostic detail on inputs that are
  already malformed.

`_refuse_local_credential_paths` was split into four named helpers, one per
forbidden state, because the added guards pushed it past ruff's `C901`
complexity ceiling. It remains the single roster entry and the fixed order of
the four is still declared in one place, so the order test is unaffected.

### File List

**Modified — source**

- `src/config/startup/stage_one.py` — the five conditions, the constants they
  compare against, and the fixed-order roster; module docstring extended.
- `src/config/observability/telemetry.py` — `_is_disabled()` renamed to public
  `otel_sdk_is_disabled()`, `OTEL_SDK_DISABLED_ENV_VAR` and `_DISABLED_VALUES`
  extracted, the one internal caller updated.
- `src/config/authorization/jwks.py` — `resolve_jwks_url()` extracted from
  `configured_jwks_url()`, added to `__all__`, module docstring extended.

**New — tests**

- `tests/unit/startup/test_stage_one_conditions.py`

**Modified — tests**

- `tests/conftest.py` — `valid_deployed_settings_namespace()`,
  `DEPLOYED_OIDC_ISSUER`, `DEPLOYED_AUTHENTICATION_BACKEND`.
- `tests/unit/startup/test_no_network_no_queries.py` — fixture rebuilt on the
  shared valid namespace.
- `tests/integration/startup/test_no_queries.py` — same.
- `tests/unit/startup/test_stage_one_escape_route.py` — the deployed-module case
  rebuilt on the shared valid namespace.
- `tests/unit/test_settings.py` — the two end-to-end cases that evaluate stage 1
  through a genuine `config.settings.production` import, deployed and local,
  reusing the module's existing `_evict_settings_modules` and `production_env`
  fixtures.

**Modified — spec**

- `_bmad-output/implementation-artifacts/4-2-five-unconditional-refusals-evaluate-at-settings-import.md`
