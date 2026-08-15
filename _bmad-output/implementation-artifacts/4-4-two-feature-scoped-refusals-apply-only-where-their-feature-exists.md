# Story 4.4: Two feature-scoped refusals apply only where their feature exists

Status: ready-for-dev

## Story

As a lead developer,
I want the cache and task refusals scoped to the features that make them meaningful,
so that four valid combinations are not rejected for legitimately having no cache.

## Acceptance Criteria

**Traceability:** FR-14 · AD-24 · SC-5

1. **Given** the Redis cache feature is selected
   **When** an in-process cache backend is configured in a deployed component
   **Then** `ImproperlyConfigured` is raised

2. **Given** background task processing is selected
   **When** eager task execution is enabled in a deployed component
   **Then** `ImproperlyConfigured` is raised

3. **Given** a combination in which the corresponding feature is absent
   **When** the component starts
   **Then** neither condition is evaluated
   **And** startup proceeds

4. **Given** these two refusals are feature-conditional
   **When** they are written
   **Then** they are delimited as feature-owned regions by paired `feature:<name>` / `/feature:<name>` line comments
   **And** they are not unconditional code guarded by a runtime flag

## Tasks / Subtasks

- [ ] Task 1 — Condition 8: an in-process cache backend where Redis is selected (AC: #1)
  - [ ] Add `_refuse_in_process_cache(module: ModuleType) -> None` to `src/config/startup/stage_one.py`, **inside** the `feature:redis` region delimited in Task 3.
  - [ ] Read `CACHES` off the settings module object passed to `run_stage_one` (never `django.conf.settings` — not populated mid-import).
  - [ ] Refuse when any alias's `BACKEND` resolves to `django.core.cache.backends.locmem.LocMemCache`, `django.core.cache.backends.dummy.DummyCache`, or a subclass of either. Resolve each dotted path with `django.utils.module_loading.import_string` and test with `issubclass` — a subclass re-exported under another name is the evasion this closes, consistent with AD-26's object-resolution rule.
  - [ ] Message names the offending cache alias and states that the Redis feature is selected, so the reader knows which half of the pair is wrong.
  - [ ] `src/config/settings/local.py:21-26` configures `LocMemCache`; `src/config/settings/production.py:33-44` configures `django_redis.cache.RedisCache`. The refusal exists because production settings hardcode Redis, so a component that did **not** select Redis legitimately falls back to the in-process cache in production — an unconditional refusal there would reject four valid combinations.

- [ ] Task 2 — Condition 9: eager task execution where background task processing is selected (AC: #2)
  - [ ] Add `_refuse_eager_tasks(module: ModuleType) -> None` to `src/config/startup/stage_one.py`, **inside** the `feature:celery` region.
  - [ ] Refuse when `CELERY_TASK_ALWAYS_EAGER` is truthy. Read it off the settings module object; absent means not eager and does not refuse.
  - [ ] `src/config/settings/local.py:78-80` sets `CELERY_TASK_ALWAYS_EAGER = True` and `CELERY_TASK_EAGER_PROPAGATES = True`. Refuse on `CELERY_TASK_ALWAYS_EAGER` only — `EAGER_PROPAGATES` is inert without it and refusing on it would produce a second forbidden state the settled count does not have.
  - [ ] Message names the setting and states that background task processing is selected.

- [ ] Task 3 — Delimit both conditions as feature-owned regions (AC: #3, #4)
  - [ ] In `src/config/startup/stage_one.py`, wrap condition 8's function definition **and** its call site in the fixed-order tuple with Python line comments:
    `# feature:redis` … `# /feature:redis`
  - [ ] Wrap condition 9's function definition and its call site with:
    `# feature:celery` … `# /feature:celery`
  - [ ] Every marker pair must be balanced and use the file's own comment syntax (`#` for Python). An unbalanced pair fails reconciliation (AD-24).
  - [ ] The feature names must match the pixi feature names the `[environments]` matrix will use. `pixi.toml` today has only `default` and `dev` environments (`:141-143`), both `solve-group = "default"`; the four-feature matrix is Epic 8. Use `redis` and `celery` and record the choice in the Completion Notes so Epic 7's carrier entry matches.
  - [ ] **Forbidden implementations, explicitly:** do not guard either condition with a settings flag, an environment variable, a `if "django_redis" in INSTALLED_APPS` test, a conditional import, `try/except ImportError`, or a separate settings module. AD-24 permits no sub-file removal mechanism other than the declared markers. AC #4 states the rule directly: "they are not unconditional code guarded by a runtime flag."
  - [ ] Because the region is removed by the materializer, AC #3 is satisfied *by absence*: in a combination without the feature, the function and its call site are not in the file at all. Do not write a runtime "is the feature selected?" branch to satisfy AC #3.

- [ ] Task 4 — Record the region declarations for Epic 7 (AC: #4)
  - [ ] `accelerator.toml` does not exist yet — Epic 7 authors it (AD-1). Record the two regions in a module-level docstring or a comment block at the top of `src/config/startup/stage_one.py`: path, feature name, and what the region contains. Epic 7 moves the declaration into `accelerator.toml` "without changing any assertion's meaning" (epics.md:225).
  - [ ] Do not create `accelerator.toml` here, and do not create a substitute declaration file. One declaration site, authored where the epic says (AD-1).
  - [ ] Add a test asserting the markers are present, paired and balanced in `src/config/startup/stage_one.py` — a small local stand-in for the two-way reconciliation Epic 7 delivers, so the markers cannot be silently dropped in the interval.

- [ ] Task 5 — Wire both conditions into the fixed order (AC: #1, #2)
  - [ ] Append condition 8 and condition 9 to the stage-1 fixed-order tuple established by Story 4.2, each call site inside its own marker pair.
  - [ ] Both are deployed-only: `run_stage_one` already returns early when `is_deployed()` is `False`, so no extra locality test is needed inside either condition.
  - [ ] Both raise `django.core.exceptions.ImproperlyConfigured`. No warning, no log-and-continue (CG-3).

- [ ] Task 6 — Tests (AC: all)
  - [ ] `tests/unit/config/startup/test_feature_scoped_refusals.py`.
  - [ ] AC #1: a deployed settings namespace with `CACHES["default"]["BACKEND"] = "django.core.cache.backends.locmem.LocMemCache"` raises `ImproperlyConfigured`. A second case for `DummyCache`. A third for a locally defined `LocMemCache` subclass referenced by its own dotted path.
  - [ ] AC #2: a deployed settings namespace with `CELERY_TASK_ALWAYS_EAGER = True` raises `ImproperlyConfigured`.
  - [ ] Negative cases: `django_redis.cache.RedisCache` passes; `CELERY_TASK_ALWAYS_EAGER` absent or `False` passes.
  - [ ] AC #3: the marker-balance test from Task 4 is what stands in for "not evaluated in a combination without the feature" until the materializer exists. Add an explicit note in the test module docstring that the runtime half of AC #3 is proven per combination by Epic 8's gate, and is a **traceability marker here, not an acceptance condition for this story** — no materialized combination exists to run against yet.
  - [ ] AC #4: assert the four markers exist, are paired, and that no `if` statement gating either condition on a feature flag appears in `src/config/startup/stage_one.py` — a source scan for the two function names confirming each is enclosed by its markers.

## Dev Notes

### Architecture Constraints

- **AD-24 (binding rule, verbatim in part):** "A region is delimited by paired line comments in the file's own comment syntax, `feature:<name>` / `/feature:<name>`, and every region is declared in `accelerator.toml` with its path and feature. Reconciliation extends to regions in both directions: a marker naming an undeclared feature fails; a declared region whose markers are absent from the named file fails; an unbalanced marker pair fails. **No other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`.**"
  **Prevents:** "two builders splitting on markers versus file-extraction and producing incompatible trees; a missed region leaving `CeleryInstrumentor().instrument()` in eight combinations whose environment no longer contains the instrumentor — an `ImportError` at boot that path-level reconciliation cannot see."
- **Spine, Consistency Conventions → Feature-conditional code:** "The two feature-scoped refusals (FR-14) are feature-owned regions declared under AD-24, not unconditional code guarded by a flag." This is the rule stated at its narrowest and it is exactly this story.
- **AD-3:** materialization is subtractive — "the materializer copies the reference application and removes what the carrier says the combination did not select, at path granularity (AD-2) and region granularity (AD-24)." AC #3 is satisfied by the region being absent from the materialized file, not by a runtime branch.
- **AD-26:** the refusal contract is one module with one location, one owner and a fixed order. These two conditions live in `src/config/startup/stage_one.py` alongside the seven unconditional ones — not in a separate feature module.
- **AD-13:** both conditions are deployed-only; locality fails closed.
- **CG-3:** a refusal never degrades to a warning.
- **NFR-1:** no network call, no query. Both conditions read settings values only.
- **AD-1:** `accelerator.toml` is the single declarative catalogue and is authored in Epic 7. This story writes the markers and records their declaration locally; it does not create the carrier.

### The settled refusal count

From `_bmad-output/planning-artifacts/epics.md:308-326`. **Nine conditions — seven unconditional, two conditional — across fourteen distinct forbidden states**, each tested separately under FR-16.

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

This story owns conditions 8 and 9 — **two of the fourteen forbidden states**, and the only two that are conditional. They exist because production settings hardcode the Redis cache backend, so a component that did not select Redis legitimately falls back to Django's in-process cache in production; an unconditional refusal there would reject four of the twelve valid combinations. The same reasoning applies to eager task execution, which is meaningless in a component with no background task processing.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/startup/stage_one.py` | UPDATE | Holds `run_stage_one`, the escape-route condition (Story 4.1) and the five unconditional conditions (Story 4.2). **Change:** add two condition functions, each inside its own `feature:<name>` marker pair, plus their marker-wrapped call sites in the fixed-order tuple, plus the region-declaration comment block for Epic 7. **Preserve:** the `is_deployed()` early return, the existing fixed order, and the unconditional conditions' position outside every marker pair. |
| `tests/unit/config/startup/test_feature_scoped_refusals.py` | NEW | Both conditions, their negatives, the subclass-evasion case, and the marker-balance assertion. |

**Verified against the repository (2026-08-15):**

- `src/config/settings/local.py:21-26` — `CACHES["default"]["BACKEND"] = "django.core.cache.backends.locmem.LocMemCache"`.
- `src/config/settings/local.py:78-80` — `CELERY_TASK_ALWAYS_EAGER = True` and `CELERY_TASK_EAGER_PROPAGATES = True`.
- `src/config/settings/production.py:33-44` — `CACHES["default"]["BACKEND"] = "django_redis.cache.RedisCache"`, hardcoded with no feature branch. This is the fact that makes condition 8 conditional rather than unconditional.
- `pixi.toml:141-143` — `[environments]` contains only `default` and `dev`, both `solve-group = "default"`. **The twelve-combination matrix does not exist yet** (Epic 8), so no materialized combination can currently exercise AC #3's runtime half.
- `src/config/settings/base.py:296-335` — the Celery block. AD-24 cites it as `:296-313`; line 296 is the `# Celery` banner and the citation's start is correct, but the block now extends to `:335`. Recorded drift; this story does not place markers there — Epic 7 does.

**Does not exist yet and is not created here:** `accelerator.toml` (Epic 7, AD-1), the four pixi features and the `[environments]` matrix (Epic 8, AD-3), `tools/materializer/` (Epic 8).

### Testing Requirements

- `tests/unit/config/startup/test_feature_scoped_refusals.py`, mirroring `src/config/startup/`. Unit tests only — both conditions read settings values and touch nothing external.
- Per the spine's Test-location convention, a feature's tests carry the feature's disposition and are pruned with it. These two conditions' tests are therefore `feature:redis` and `feature:celery` respectively; keep them in **separate test functions or separate marker-delimited regions within the file** so Epic 7 can dispose of them accurately. Note in the module docstring which functions belong to which feature.
- Specific assertions the ACs demand: `ImproperlyConfigured` for `LocMemCache`, for `DummyCache`, for a `LocMemCache` subclass, and for `CELERY_TASK_ALWAYS_EAGER = True`; no raise for `RedisCache` and for eager absent/false; four balanced markers present in the source file.
- AD-20: ninety percent including templates, `COVERAGE_CORE=ctrace` in force (`pixi.toml:145-151`). Do not add `src/config/startup/` to `[tool.coverage.run] omit` (`pyproject.toml:160-168`).
- `pixi run test` in the inner loop; `pixi run ci` (`pixi.toml:206`) is the done condition.

#### Project Structure Notes

Aligned with the Structural Seed — `src/config/startup/` is the single home. The one variance worth stating: AD-24 names three known region-bearing paths — `src/config/settings/base.py`, `src/config/observability/telemetry.py` and `pixi.toml`. This story introduces a **fourth** region-bearing path, `src/config/startup/stage_one.py`, which the spine does not enumerate. That is expected rather than a contradiction: AD-24's list is "three `core` paths carry feature-owned regions **and are the reason this exists**", not a closed set, and epics.md:225 explicitly names "the FR-14 feature-region markers (Epic 4)" as one of three declarations authored in an earlier epic and moved into `accelerator.toml` in Epic 7. Epic 7's carrier must declare four region-bearing paths, not three.

The runtime half of AC #3 — "in a combination in which the corresponding feature is absent, neither condition is evaluated and startup proceeds" — is provable only against a materialized combination, which Epic 8 produces. It is a **traceability marker, not an acceptance condition for this story**; what this story delivers is the mechanism (markers) that makes it true by construction.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.4]
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — lines 308-326
- [Source: _bmad-output/planning-artifacts/epics.md#Cross-epic threads] — line 225: the FR-14 region markers are authored here and move into `accelerator.toml` in Epic 7
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-3]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-14]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#CG-3]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
