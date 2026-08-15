# Story 4.2: Five unconditional refusals evaluate at settings import

Status: ready-for-dev

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

- [ ] Task 1 — Condition 1: the sqlite backend is reached, over *every* configured database (AC: #1)
  - [ ] Move the existing check at `src/config/settings/production.py:26-28` into `src/config/startup/stage_one.py` as `_refuse_sqlite(databases: dict[str, dict[str, object]]) -> None`, iterating **every** alias in `DATABASES`, not only `"default"` (AD-9). The message names the offending alias.
  - [ ] Leave `production.py:26-28` in place as-is. AC #1 states it is the mechanism, and it must keep firing before line 29 (`DATABASES["default"]["CONN_MAX_AGE"] = …`) which assumes a real backend. Stage 1 then re-evaluates the same condition over all aliases as the last statement of the module; the two are consistent by construction because both raise on the same predicate.
  - [ ] Predicate: `str(config.get("ENGINE", "")).endswith("sqlite3")`. This is a settings-value inspection, not a route or callable, so string comparison is correct here — AD-26's "predicates resolve objects, never strings" governs the URLconf conditions in Story 4.3, not settings scalars.
  - [ ] Where a contributed database's alias appears (AD-9, Epic 9), it is iterated identically; no alias is exempt.

- [ ] Task 2 — Condition 2: a local credential path is live in settings — four distinct forbidden states (AC: #2)
  - [ ] `_refuse_local_credential_paths(module: ModuleType) -> None` in `src/config/startup/stage_one.py`. Each of the four states raises its own `ImproperlyConfigured` with its own message; do not collapse them into one aggregated error, because FR-16 requires each to be testable separately.
  - [ ] State 2a — `ModelBackend`: refuse when any entry of `AUTHENTICATION_BACKENDS` resolves to `django.contrib.auth.backends.ModelBackend` or a subclass of it. Resolve each dotted path with `django.utils.module_loading.import_string` and test with `issubclass`, not `in` on the string list — a subclass re-exported under another name is the evasion this closes.
  - [ ] State 2b — `ACCOUNT_LOGIN_METHODS`: refuse when the value is a non-empty collection. `base.py:340` sets `{"username"}` today.
  - [ ] State 2c — `DJANGO_ADMIN_FORCE_ALLAUTH`: refuse when the value is anything other than `True`. Absent counts as not true and refuses. `base.py:271` defaults it `False` today.
  - [ ] State 2d — the static-token surface: refuse when `"rest_framework.authtoken"` is in `INSTALLED_APPS`, **or** when any entry of `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` resolves to `rest_framework.authentication.TokenAuthentication` or a subclass. Resolve with `import_string` + `issubclass`, same reasoning as 2a. One condition, one raise, but the test suite covers both halves.
  - [ ] Read each name off the module object passed to `run_stage_one` using `getattr(module, name, <sentinel>)`, never from `django.conf.settings` — settings are not populated while the module is still executing.

- [ ] Task 3 — Condition 3: `OTEL_SDK_DISABLED` (AC: #3)
  - [ ] `_refuse_otel_disabled() -> None`. Read `OTEL_SDK_DISABLED` from `os.environ` — it is an OpenTelemetry SDK environment variable, not a Django setting, and `src/config/observability/telemetry.py` does not mirror it into settings.
  - [ ] Refuse when the value, lower-cased and stripped, is `"true"`. That is the SDK's own truthiness rule; do not invent a wider one that would refuse on `"0"`.
  - [ ] Message states the reasoning: a deployed component setting it has silently opted out of an immovable guarantee (FR-13).

- [ ] Task 4 — Condition 4: the JWKS trust anchor is not derived from the configured IdP issuer (AC: #4)
  - [ ] `_refuse_untrusted_jwks_anchor(module: ModuleType) -> None`. Read the configured OIDC issuer and the configured JWKS location from the settings names Epic 2 Story 2.7 established. **Do not invent names and do not create a second declaration site (AD-1)** — import the constants from `src/config/authorization/` if that module exposes them, otherwise `getattr` the settings names it sets. If Story 2.7 has not landed, define the two names here and record in the Completion Notes that Story 2.7 must consume them rather than declare its own.
  - [ ] Predicate: parse both values with `urllib.parse.urlsplit` and refuse unless the JWKS URL's `scheme` is `https` **and** its `netloc` equals the issuer's `netloc` **and** its `path` begins with the issuer's `path`. Refuse when either value is absent or empty.
  - [ ] This is the condition that catches a component pointed at a locally generated development key by environment variable **with no key file present at all** — so it must not look at the filesystem. Do not add an existence check on any key path.
  - [ ] No network call: never fetch the issuer's discovery document to confirm the JWKS URL (NFR-1, and FR-23's no-network-at-boot property).

- [ ] Task 5 — Condition 5 (stage-1 half): the claims contract is unconfigured (AC: #5)
  - [ ] `_refuse_unconfigured_claims_contract(module: ModuleType) -> None`. Refuse when any of the four claims-contract values is absent or empty: the identity-key claim name, the group-claim name, the staff-conferring group, the superuser-conferring group.
  - [ ] Same single-declaration rule as Task 4: read the names Epic 2 Story 2.2 established. Story 2.2's AC says "no conventional claim name is defaulted in its place" — so the settings reads must have **no default**; an absent variable must produce an absent value that this condition then refuses, not a fallback of `"sub"`, `"groups"` or `"realm_access.roles"`.
  - [ ] This is the stage-1 half of condition 5 in the refusal table. Its stage-2 half — a designated group absent from the database (AD-27) — belongs to Story 4.3 and must not be implemented here: stage 1 may issue no query at all (NFR-1).

- [ ] Task 6 — Wire the five conditions into `run_stage_one` (AC: all)
  - [ ] `run_stage_one` returns immediately when `is_deployed()` is `False`, then calls the escape-route condition from Story 4.1 followed by the five conditions above, in a fixed declared order. AD-26 requires "one location, one owner, and a fixed order"; record the order as a module-level tuple so a test can assert it.
  - [ ] Every failure raises `django.core.exceptions.ImproperlyConfigured`. No `warnings.warn`, no `structlog` log-and-continue, no `except … : pass` (CG-3).
  - [ ] Messages carry the setting or environment variable name and the value that was rejected — never a secret value. `SECRET_KEY`, tokens and passwords are never read by any of these conditions and must not appear in any message (NFR-7).

- [ ] Task 7 — Tests (AC: all)
  - [ ] `tests/unit/config/startup/test_stage_one_conditions.py` — one test per forbidden state: sqlite (default alias), sqlite (a second configured alias), `ModelBackend`, non-empty `ACCOUNT_LOGIN_METHODS`, `DJANGO_ADMIN_FORCE_ALLAUTH` not true, `authtoken` installed, `TokenAuthentication` in DRF defaults, `OTEL_SDK_DISABLED=true`, JWKS anchor mismatch, each of the four missing claims-contract values.
  - [ ] Each test builds a `types.SimpleNamespace` or a `types.ModuleType` carrying only the names the condition reads, sets `COMPONENT_RUNTIME` absent via `monkeypatch.delenv`, calls `run_stage_one(module)` and asserts `pytest.raises(ImproperlyConfigured)`.
  - [ ] Add the positive case: a fully valid deployed namespace passes `run_stage_one` without raising. Without it, a condition that raises unconditionally would pass every refusal test.
  - [ ] Add a subclass-evasion test for 2a and 2d: a locally defined subclass of `ModelBackend` and of `TokenAuthentication`, referenced by its own dotted path, still refuses.
  - [ ] `tests/unit/test_settings.py` already covers `production.py`'s sqlite refusal; extend rather than duplicate it, following its `_evict_settings_modules` fixture (`tests/unit/test_settings.py:24-30`).

## Dev Notes

### Architecture Constraints

- **AD-26:** the refusal contract is one module, `src/config/startup/`, with one location, one owner and a fixed order. Stage 1 is the last statement of every settings module, "which places it after the AD-8 composition step by construction and is why AD-9's iteration over every configured database is reachable."
- **AD-9 (binding rule):** "The stage-2 unapplied-migrations refusal and the sqlite refusal both iterate every configured database — which is only possible because stage 1 runs *after* composition (AD-26)." This is why Task 1 iterates aliases rather than reading `DATABASES["default"]`.
  **Prevents:** "six enforcement points each being answered differently by six epics."
- **AD-1:** every declaration has exactly one site. The claims-contract setting names and the OIDC issuer / JWKS location setting names are Epic 2's declarations; this story consumes them and must not re-declare them.
- **AD-23:** "The trust anchor is derived from the configured OIDC issuer; a JWKS location not derived from it is refused at startup." Condition 4 is that refusal.
- **CG-3:** "Do not soften a refusal into a warning. A refusal that logs and continues makes deployment smoother and puts local credentials into production."
- **NFR-1:** "The nine checks are settings and URL-configuration inspection with no network call and no query beyond the migration state." **Stage 1 issues zero queries.**
- **NFR-7:** secrets never live in source and never appear in a refusal message.
- **AD-24 forbids** conditional imports and `try/except ImportError` inside these conditions. Every import in `src/config/startup/stage_one.py` is unconditional and top-level; the two feature-scoped conditions of Story 4.4 are delimited by paired line comments instead.

### The settled refusal count

Reproduced from `_bmad-output/planning-artifacts/epics.md:308-326`. **Nine conditions — seven unconditional, two conditional — across fourteen distinct forbidden states**, each tested separately under FR-16.

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

One structural note worth recording: `src/config/settings/base.py:296-335` is the Celery block. AD-24 cites it as `:296-313`; line 296 is indeed the `# Celery` banner, but the block now runs to `:335` (`CELERY_WORKER_HIJACK_ROOT_LOGGER = False`). The citation's start is correct and its end has drifted by twenty-two lines. This story does not touch that block — Story 4.4 and Epic 7 do — but the drift is recorded so the region markers are placed against the current extent rather than the cited one.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.2]
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — lines 308-326
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

### Debug Log References

### Completion Notes List

### File List
