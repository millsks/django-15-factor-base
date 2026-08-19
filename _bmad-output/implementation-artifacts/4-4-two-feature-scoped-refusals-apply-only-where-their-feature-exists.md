---
status: done
baseline_revision: 02df6a712ea3cead8f3a7785df6b19880478fd0f
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: []
---

# Story 4.4: Two feature-scoped refusals apply only where their feature exists

Status: done

## Story

As a lead developer,
I want the cache and task refusals scoped to the features that make them meaningful,
so that the two valid combinations with no Redis are not rejected for legitimately having no cache.

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

- [x] Task 1 — Condition 8: an in-process cache backend where Redis is selected (AC: #1)
  - [x] Add `_refuse_in_process_cache(settings_module: ModuleType) -> None` *(the draft spelled the parameter `module`; Reconciliation 3 — the landed convention in this file is `settings_module`)* to `src/config/startup/stage_one.py`, **inside** the `feature:redis` region delimited in Task 3.
  - [x] Read `CACHES` off the settings module object passed to `run_stage_one` (never `django.conf.settings` — not populated mid-import).
  - [x] Refuse when any alias's `BACKEND` resolves to `django.core.cache.backends.locmem.LocMemCache`, `django.core.cache.backends.dummy.DummyCache`, or a subclass of either. Resolve each dotted path with `django.utils.module_loading.import_string` and test with `issubclass` — a subclass re-exported under another name is the evasion this closes, consistent with AD-26's object-resolution rule.
  - [x] Message names the offending cache alias and states that the Redis feature is selected, so the reader knows which half of the pair is wrong.
  - [x] `src/config/settings/local.py:38-43` configures `LocMemCache`; `src/config/settings/production.py:35-46` configures `django_redis.cache.RedisCache`. The refusal exists because production settings hardcode Redis, so a component that did **not** select Redis legitimately falls back to the in-process cache in production — an unconditional refusal there would reject the two valid combinations that have no Redis.

- [x] Task 2 — Condition 9: eager task execution where background task processing is selected (AC: #2)
  - [x] Add `_refuse_eager_tasks(settings_module: ModuleType) -> None` *(parameter renamed per Reconciliation 3)* to `src/config/startup/stage_one.py`, **inside** the `feature:celery` region.
  - [x] Refuse when `CELERY_TASK_ALWAYS_EAGER` is truthy. Read it off the settings module object; absent means not eager and does not refuse.
  - [x] `src/config/settings/local.py:103` and `:110` set `CELERY_TASK_ALWAYS_EAGER = True` and `CELERY_TASK_EAGER_PROPAGATES = True` (not contiguous). Refuse on `CELERY_TASK_ALWAYS_EAGER` only — `EAGER_PROPAGATES` is inert without it and refusing on it would produce a second forbidden state the settled count does not have.
  - [x] Message names the setting and states that background task processing is selected.

- [x] Task 3 — Delimit both conditions as feature-owned regions (AC: #3, #4)
  - [x] In `src/config/startup/stage_one.py`, wrap condition 8's function definition **and** its call site in the fixed-order tuple with Python line comments:
    `# feature:redis` … `# /feature:redis`
  - [x] Wrap condition 9's function definition and its call site with:
    `# feature:celery` … `# /feature:celery`
  - [x] Every marker pair must be balanced and use the file's own comment syntax (`#` for Python). An unbalanced pair fails reconciliation (AD-24).
  - [x] The feature names must match the pixi feature names the `[environments]` matrix will use. `pixi.toml:379-382` today has `default`, `dev` and `spike-storage` environments, all `solve-group = "default"`; the three-feature matrix — `celery`, `redis`, `storage` — is Epic 8. Use `redis` and `celery` and record the choice in the Completion Notes so Epic 7's carrier entry matches.
  - [x] **Forbidden implementations, explicitly:** do not guard either condition with a settings flag, an environment variable, a `if "django_redis" in INSTALLED_APPS` test, a conditional import, `try/except ImportError`, or a separate settings module. AD-24 permits no sub-file removal mechanism other than the declared markers. AC #4 states the rule directly: "they are not unconditional code guarded by a runtime flag."
  - [x] Because the region is removed by the materializer, AC #3 is satisfied *by absence*: in a combination without the feature, the function and its call site are not in the file at all. Do not write a runtime "is the feature selected?" branch to satisfy AC #3.

- [x] Task 4 — Record the region declarations for Epic 7 (AC: #4)
  - [x] `accelerator.toml` does not exist yet — Epic 7 authors it (AD-1). Record the two regions in a module-level docstring or a comment block at the top of `src/config/startup/stage_one.py`: path, feature name, and what the region contains. Epic 7 moves the declaration into `accelerator.toml` "without changing any assertion's meaning" (epics.md:227).
  - [x] Do not create `accelerator.toml` here, and do not create a substitute declaration file. One declaration site, authored where the epic says (AD-1).
  - [x] Add a test asserting the markers are present, paired and balanced in `src/config/startup/stage_one.py` — a small local stand-in for the two-way reconciliation Epic 7 delivers, so the markers cannot be silently dropped in the interval.

- [x] Task 5 — Wire both conditions into the fixed order (AC: #1, #2)
  - [x] Append condition 8 and condition 9 to the stage-1 fixed-order tuple established by Story 4.2, each call site inside its own marker pair.
  - [x] Both are deployed-only: `run_stage_one` already returns early when `is_deployed()` is `False`, so no extra locality test is needed inside either condition.
  - [x] Both raise `django.core.exceptions.ImproperlyConfigured`. No warning, no log-and-continue (CG-3).

- [x] Task 6 — Tests (AC: all)
  - [x] `tests/unit/startup/test_feature_scoped_refusals.py` *(the draft said `tests/unit/config/startup/`, which does not exist — Reconciliation 2)*.
  - [x] AC #1: a deployed settings namespace with `CACHES["default"]["BACKEND"] = "django.core.cache.backends.locmem.LocMemCache"` raises `ImproperlyConfigured`. A second case for `DummyCache`. A third for a locally defined `LocMemCache` subclass referenced by its own dotted path.
  - [x] AC #2: a deployed settings namespace with `CELERY_TASK_ALWAYS_EAGER = True` raises `ImproperlyConfigured`.
  - [x] Negative cases: `django_redis.cache.RedisCache` passes; `CELERY_TASK_ALWAYS_EAGER` absent or `False` passes.
  - [x] AC #3: the marker-balance test from Task 4 is what stands in for "not evaluated in a combination without the feature" until the materializer exists. Add an explicit note in the test module docstring that the runtime half of AC #3 is proven per combination by Epic 8's gate, and is a **traceability marker here, not an acceptance condition for this story** — no materialized combination exists to run against yet.
  - [x] AC #4: assert the four markers exist, are paired, and that no `if` statement gating either condition on a feature flag appears in `src/config/startup/stage_one.py` — a source scan for the two function names confirming each is enclosed by its markers.

## Dev Notes

### Architecture Constraints

- **AD-24 (binding rule, verbatim in part):** "A region is delimited by paired line comments in the file's own comment syntax, `feature:<name>` / `/feature:<name>`, and every region is declared in `accelerator.toml` with its path and feature. Reconciliation extends to regions in both directions: a marker naming an undeclared feature fails; a declared region whose markers are absent from the named file fails; an unbalanced marker pair fails. **No other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`.**"
  **Prevents:** "two builders splitting on markers versus file-extraction and producing incompatible trees; a missed region leaving `CeleryInstrumentor().instrument()` in the four combinations whose environment no longer contains the instrumentor — an `ImportError` at boot that path-level reconciliation cannot see; and a region declared against a stale line range or a fixed path count, which delivers the same failure while appearing to comply."
- **Spine, Consistency Conventions → Feature-conditional code:** "The two feature-scoped refusals (FR-14) are feature-owned regions declared under AD-24, not unconditional code guarded by a flag." This is the rule stated at its narrowest and it is exactly this story.
- **AD-3:** materialization is subtractive — "the materializer copies the reference application and removes what the carrier says the combination did not select, at path granularity (AD-2) and region granularity (AD-24)." AC #3 is satisfied by the region being absent from the materialized file, not by a runtime branch.
- **AD-26:** the refusal contract is one module with one location, one owner and a fixed order. These two conditions live in `src/config/startup/stage_one.py` alongside the seven unconditional ones — not in a separate feature module.
- **AD-13:** both conditions are deployed-only; locality fails closed.
- **CG-3:** a refusal never degrades to a warning.
- **NFR-1:** no network call, no query. Both conditions read settings values only.
- **AD-1:** `accelerator.toml` is the single declarative catalogue and is authored in Epic 7. This story writes the markers and records their declaration locally; it does not create the carrier.

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

This story owns conditions 8 and 9 — **two of the fourteen forbidden states**, and the only two that are conditional. They exist because production settings hardcode the Redis cache backend, so a component that did not select Redis legitimately falls back to Django's in-process cache in production; an unconditional refusal there would reject two of the six valid combinations. The same reasoning applies to eager task execution, which is meaningless in a component with no background task processing.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/startup/stage_one.py` | UPDATE | Holds `run_stage_one`, the escape-route condition (Story 4.1) and the five unconditional conditions (Story 4.2). **Change:** add two condition functions, each inside its own `feature:<name>` marker pair, plus their marker-wrapped call sites in the fixed-order tuple, plus the region-declaration comment block for Epic 7. **Preserve:** the `is_deployed()` early return, the existing fixed order, and the unconditional conditions' position outside every marker pair. |
| `tests/unit/startup/test_feature_scoped_refusals.py` | NEW | Both conditions, their negatives, the subclass-evasion case, and the marker-balance assertion. **`tests/unit/startup/`, not `tests/unit/config/startup/`** — the latter does not exist and never has; Stories 4.1-4.3 put the whole startup suite in the former. |
| `tests/unit/startup/test_stage_one_conditions.py` | UPDATE | `EXPECTED_EVALUATION_ORDER` (`:61-68`) pins the roster by name and order, so appending two conditions makes it fail. The two new names go in — each inside its own marker pair, because a core assertion naming a function the materializer removed with its feature would fail in the four combinations that do not select it. |
| `pyproject.toml` | UPDATE | `lint.task-tags` gains `"feature"`. Ruff's `ERA` group is selected with no per-file ignores, and `ERA001` reads `# feature:redis` as commented-out code (`# /feature:redis` escapes it — the leading slash). See Reconciliation. |

**Verified against the repository (2026-08-15) — every line number below was re-checked on 2026-08-18 and corrected; see Reconciliation:**

- `src/config/settings/local.py:38-43` — `CACHES["default"]["BACKEND"] = "django.core.cache.backends.locmem.LocMemCache"` (the story's original `:21-26` was stale).
- `src/config/settings/local.py:103` and `:110` — `CELERY_TASK_ALWAYS_EAGER = True` and `CELERY_TASK_EAGER_PROPAGATES = True`. They are **not** contiguous; `:104-109` is a comment block. The original `:78-80` was stale.
- `src/config/settings/test.py:44-49`, `:60`, `:62` — the same `LocMemCache` and the same two eager flags. Not in the original story, and it matters: `test.py` is a leaf settings module, so it calls `run_stage_one`, and it would refuse on both new conditions were the suite ever to run deployed. It does not (AD-13 keeps the whole test surface local), and that is the only reason it is safe.
- `src/config/settings/base.py` declares **no** `CACHES` and neither eager flag. Absence is therefore a real state both conditions must accept, not a hypothetical.
- `src/config/settings/production.py:35-46` — `CACHES["default"]["BACKEND"] = "django_redis.cache.RedisCache"`, hardcoded with no feature branch (original `:33-44` was stale). This is the fact that makes condition 8 conditional rather than unconditional.
- `pixi.toml:379-382` — `[environments]` contains `default`, `dev` and `spike-storage` (Story 1.8's R-1 spike, not the storage *feature*). **The six pre-locked environments do not exist yet** (Epic 8), so no materialized combination can currently exercise AC #3's runtime half. No pixi feature named `celery`, `redis` or `storage` exists.
- `django-redis >=7.0,<8` is an unscoped `[dependencies]` entry (`pixi.toml:96`), so `django_redis.cache.RedisCache` resolves in the `dev` environment and the negative case needs no import guard — which `tests/unit/test_suite_policy.py` forbids anyway (`pytest.importorskip` is a banned call).
- `src/config/settings/base.py:296-335` — the Celery block: `:296` is the `# Celery` header and `:335` is `CELERY_WORKER_HIJACK_ROOT_LOGGER`, the block's last line. AD-24 now cites that extent; an earlier revision cited `:296-313`, which would have stranded `CELERY_BEAT_SCHEDULER` in every combination with no `django_celery_beat`. This story does not place markers there — Epic 7 does.

**Does not exist yet and is not created here:** `accelerator.toml` (Epic 7, AD-1), the three pixi features and the six-environment `[environments]` matrix (Epic 8, AD-3), `tools/materializer/` (Epic 8).

### Testing Requirements

- `tests/unit/startup/test_feature_scoped_refusals.py`, beside the rest of the startup suite (Reconciliation 2). Unit tests only — both conditions read settings values and touch nothing external.
- Per the spine's Test-location convention, a feature's tests carry the feature's disposition and are pruned with it. These two conditions' tests are therefore `feature:redis` and `feature:celery` respectively; keep them in **separate test functions or separate marker-delimited regions within the file** so Epic 7 can dispose of them accurately. Note in the module docstring which functions belong to which feature.
- Specific assertions the ACs demand: `ImproperlyConfigured` for `LocMemCache`, for `DummyCache`, for a `LocMemCache` subclass, and for `CELERY_TASK_ALWAYS_EAGER = True`; no raise for `RedisCache` and for eager absent/false; four balanced markers present in the source file.
- AD-20: ninety percent including templates, `COVERAGE_CORE=ctrace` in force (`pixi.toml:145-151`). Do not add `src/config/startup/` to `[tool.coverage.run] omit` (`pyproject.toml:160-168`).
- `pixi run test` in the inner loop; `pixi run ci` (`pixi.toml:206`) is the done condition.

#### Project Structure Notes

Aligned with the Structural Seed — `src/config/startup/` is the single home. No variance remains here: **AD-24 now names `src/config/startup/stage_one.py` itself as a region-bearing path**, carrying "the two FR-14 conditional refusals" under `feature:celery` and `feature:redis` — which is exactly what this story writes. The regions this story creates are therefore anticipated by the spine rather than an addition to it.

The related correction matters more than the enumeration: **the set of region-bearing paths is open, and the carrier declares it as an open `[[regions]]` array — never as a fixed set of keys, and the reconciler must not encode a count.** An earlier revision of AD-24 named three paths and was wrong. So do not write, in a comment, a test, or the Task 4 declaration block, any assertion of the form "there are N region-bearing paths"; declare this file's two regions and nothing about the size of the set. epics.md:227 names "the FR-14 feature-region markers (Epic 4)" as one of the declarations authored in an earlier epic and moved into `accelerator.toml` in Epic 7, which is how these two regions reach the carrier.

The runtime half of AC #3 — "in a combination in which the corresponding feature is absent, neither condition is evaluated and startup proceeds" — is provable only against a materialized combination, which Epic 8 produces. It is a **traceability marker, not an acceptance condition for this story**; what this story delivers is the mechanism (markers) that makes it true by construction.

### Reconciliation against the tree (2026-08-18)

The story was authored 2026-08-15, before Stories 4.1-4.3 landed. Five claims were re-verified and four
required a decision the draft does not make. Each is resolved here so that implementation has no open
question.

1. **`ERA001` rejects the opening markers, and `task-tags` is the fix.** Ruff's `ERA` group is selected
   (`pyproject.toml:74`) with no `per-file-ignores`. Probed directly: `# feature:redis` and
   `# feature:celery` are both reported as `ERA001 Found commented-out code`; the closing
   `# /feature:redis` and `# /feature:celery` are not, because the leading slash stops ruff parsing the
   comment as code. `pixi run ci` therefore fails on an unmodified AD-24 marker.
   **Resolved by adding `"feature"` to `lint.task-tags` in `pyproject.toml`** — verified to suppress
   both, with the marker text left *exactly* as AD-24 spells it. The alternative, appending
   `# noqa: ERA001` to each opening marker, was rejected: it changes the marker's own line text, and
   Story 8.3's stripper has to match that line. A declared task tag says `feature:` is a recognized
   annotation rather than dead code, which is what it is. Cost: any comment beginning `feature` is
   exempt from `ERA001` tree-wide. `FIX`/`TD` are not selected, so nothing else is affected.

2. **Test location is `tests/unit/startup/`.** The Source Tree table said `tests/unit/config/startup/`.
   That directory does not exist. Story 4.3 recorded the same correction for its own two files. Follows
   the tree.

3. **The private-function signature convention is `settings_module`, not `module`.** Tasks 1 and 2
   spell the parameter `module`. Every one of the six landed conditions in `stage_one.py` takes
   `settings_module: ModuleType`, and `_refuse_otel_disabled` spells it `_settings_module` precisely
   because it does not read it. The landed convention wins; the semantics the task specifies are
   unchanged.

4. **Conditions are driven through `run_stage_one`, never called directly.**
   `tests/unit/startup/test_stage_one_conditions.py:9-12` states the rule and the reason: a condition
   called by hand passes whether or not it was ever wired into the roster. The new test file follows it.
   The one licensed private access is the roster read, which already carries `# noqa: SLF001`.

5. **Absence of `CACHES` and of `CELERY_TASK_ALWAYS_EAGER` must not refuse.**
   `tests/conftest.py:108-143`'s `valid_deployed_settings_namespace` sets neither, and it is the
   baseline for `test_stage_one_conditions.py`, `test_stage_one_escape_route.py`,
   `test_no_network_no_queries.py` and `tests/integration/startup/test_no_queries.py`. A condition that
   refused on absence would break all four. This agrees with Task 2's own rule ("absent means not eager
   and does not refuse") and extends it to `CACHES`. **The shared factory is deliberately not
   extended** — adding feature-scoped keys to a core conftest would put a `feature:` region in the
   fixture every core test depends on.

6. **An unimportable cache backend is not condition 8's refusal.** Resolving a dotted `BACKEND` with
   `import_string` can raise `ImportError`. Condition 8 skips that alias rather than converting the
   error into a refusal: its message describes *an in-process backend where Redis is selected*, which is
   not what an unimportable path is, and refusing would add a fifteenth forbidden state to a count the
   architecture settled at fourteen. Django owns that defect and raises `InvalidCacheBackendError` —
   itself an `ImproperlyConfigured` — at first cache access. The skip is asserted by a test rather than
   left implicit.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.4]
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — lines 310-328
- [Source: _bmad-output/planning-artifacts/epics.md#Cross-epic threads] — line 227: the FR-14 region markers are authored here and move into `accelerator.toml` in Epic 7
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-3]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-14]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#CG-3]

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m]

### Debug Log References

- Ruff `ERA001` on the opening markers: reproduced, then cleared by
  `lint.task-tags = [ "TODO", "FIXME", "XXX", "feature" ]` in `pyproject.toml`.
  All four values are spelled because setting the key replaces ruff's default
  rather than extending it.
- Probed and rejected: a marker pair around the three new imports. Ruff's isort
  (`I001`) merges a comment-separated import run back into the sorted block and
  carries the markers with whichever import they attach to, so the pair does not
  survive `ruff check --fix`. Recorded in `stage_one.py`'s module docstring
  instead — see Completion Notes.

### Completion Notes List

- **Feature names, for Epic 7's carrier entry: `redis` and `celery`.** Three
  paths carry regions: `src/config/startup/stage_one.py`,
  `tests/unit/startup/test_stage_one_conditions.py` and
  `tests/unit/startup/test_feature_scoped_refusals.py`. The two test paths are
  there because the spine's Test-location convention gives a feature's tests the
  feature's disposition: an assertion naming a function the materializer removed
  fails in every combination that did not select it. Verified rather than
  reasoned — with all four regions stripped, the three files still parse and
  `ruff format --check` reports no reformatting needed, in each of the three
  strip combinations.
- **Each feature owns two marker pairs in that file, not one.** A region is a
  contiguous run of lines, and a condition's definition and its `_STAGE_ONE`
  roster entry are not adjacent. Four pairs, eight marker lines, four distinct
  marker texts. A roster entry left outside its pair would survive into a
  combination whose definition the materializer removed — a `NameError` at
  settings import.
- **Region declaration site:** `stage_one.py`'s module docstring, per Task 4.
  `accelerator.toml` was not created and no substitute declaration file was
  written (AD-1). The declaration records path, feature and contents for each
  region, and asserts nothing about how many region-bearing paths the tree has.
- **Not covered by the declarations, recorded rather than hidden:** the three
  Django-core imports condition 8 resolves through (`DummyCache`, `LocMemCache`,
  `import_string`) sit unmarked in the sorted import block. They are Django's
  own, so they resolve in every combination and removing a region leaves an
  unused import rather than an `ImportError`. Pruning it is the materializer's
  general orphan problem (Epic 8), which AD-24's own `CeleryInstrumentor`
  example already places there.
- **Two guards the story did not specify, both required by CG-3.** A `BACKEND`
  that resolves to something which is not a class is skipped, because
  `issubclass` raises `TypeError` on it and a condition must raise only
  `ImproperlyConfigured`. An alias whose value is not a mapping, or whose
  `BACKEND` is not a string, is likewise skipped — Django's `CacheHandler`
  already refuses those at first access, and refusing them here would put this
  condition's message on a defect it does not describe.
- `EXPECTED_EVALUATION_ORDER` in `tests/unit/startup/test_stage_one_conditions.py`
  gained the two names, each inside its own marker pair, so the core assertion
  shrinks in step with the roster in a combination that selected neither feature.
- **The `import_string` guard catches `Exception`, not `ImportError`, and that
  is the one correctness fix the review produced.** `import_string` executes
  third-party module code, so a `BACKEND` whose module raises at import
  propagates out of a settings import. `AppRegistryNotReady` and a plain
  `RuntimeError` were both reproduced escaping the original narrow guard, which
  breaks the single promise this module makes: `ImproperlyConfigured` and
  nothing else leaves a condition (CG-3). `BaseException` is deliberately not
  caught, so `KeyboardInterrupt`, `SystemExit` and the suite's own network guard
  still pass through untouched. The skip-rather-than-refuse decision is
  unchanged and is the generalisation of Reconciliation 6.
- **The declaration block is now reconciled against the markers in both
  directions**, which is what Task 4's "small local stand-in" asked for. The
  test parses the declared `path`/`feature` pairs out of `stage_one.__doc__` and
  checks that every marker names a declared feature and that every declared
  feature still present in the tree has markers in the file it names. Before the
  review the assertion compared against a hardcoded dict, so the declaration
  block could rot without anything failing.
- **`lint.task-tags` is now pinned by a test.** The key replaces ruff's default
  rather than extending it, so an edit dropping `TODO`/`FIXME`/`XXX` — or
  dropping `ERA` from `select`, which would make the `feature` tag pointless —
  changes lint behaviour tree-wide with the gate still green.
- Gate: `pixi run ci` exits 0. Total coverage 96.78%;
  `src/config/startup/stage_one.py` at 100%; 1105 tests pass, 151 of them in
  `tests/unit/startup/`.

### File List

- `src/config/startup/stage_one.py` — UPDATE: conditions 8 and 9, their two
  marker pairs each, their `_STAGE_ONE` entries, the region declarations and the
  refreshed module docstring.
- `tests/unit/startup/test_feature_scoped_refusals.py` — NEW: both conditions,
  their negatives, the subclass-evasion case, the unimportable-backend decision,
  and the marker balance/pairing/enclosure assertions.
- `tests/unit/startup/test_stage_one_conditions.py` — UPDATE: the roster
  expectation and the stale module docstring.
- `pyproject.toml` — UPDATE: `lint.task-tags` gains `"feature"` (with the three
  ruff defaults respelled).
- `tests/unit/startup/test_no_network_no_queries.py` — UPDATE: the namespace now
  declares a Redis `CACHES` alias, so stage 1's one third-party-import line runs
  inside the `no_network` and no-cursor guards. Without it NFR-1 was asserted
  over a code path the new condition never reached.
- `tests/conftest.py` — UPDATE: docstring only. It named three consumers of
  `valid_deployed_settings_namespace`; there are seven, and the count is replaced
  by the property rather than re-counted.

## Review Triage Log

### 2026-08-18 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 16: (high 1, medium 7, low 8)
- defer: 2: (high 0, medium 2, low 0)
- reject: 5: (high 0, medium 1, low 4)
- addressed_findings:
  - `[high]` `[patch]` `_refuse_in_process_cache` guarded only `ImportError` around `import_string`, which executes third-party module code — `AppRegistryNotReady` and `RuntimeError` were both reproduced escaping a settings import, breaking CG-3's "`ImproperlyConfigured` and nothing else". Guard widened to `Exception` (never `BaseException`), skip semantics unchanged, and a test drives a dotted path whose resolution raises.
  - `[medium]` `[patch]` `test_the_markers_name_only_features_this_file_declares` asserted set *equality* against a hardcoded two-feature roster, so it would fail on a correctly materialized single-feature tree. Changed to a subset relation; the class docstring's false "holds with one feature, both, or none" claim made true.
  - `[medium]` `[patch]` The new test file's feature-scoped content carried no markers — only prose. Verified: 7 tests fail on a stripped tree, and the `LocMemCache` subclass was unconditional. Redis-owned and celery-owned content wrapped in marker pairs and added to the declaration block.
  - `[medium]` `[patch]` Markers sat two blank lines from the code they wrapped, so a stripped file failed `ruff format --check` on leftover blank runs. Moved flush; re-verified across all three strip combinations.
  - `[medium]` `[patch]` `test_the_redis_cache_backend_is_accepted` was not a control — dropping `django-redis` would make `import_string` raise, the alias skip, and the test pass green. Now asserts the path resolves to a class first.
  - `[medium]` `[patch]` Marker scanning covered `stage_one.py` alone while two test files also carry markers. Balance, nesting, interleaving and naming assertions parametrized over all three marker-bearing paths.
  - `[medium]` `[patch]` The Task-4 declaration block was never read by any test — it compared against a hardcoded dict — so a declaration could rot or lose a region silently. The test now parses `stage_one.__doc__` and reconciles declarations against markers in both directions.
  - `[medium]` `[patch]` `tests/unit/startup/test_no_network_no_queries.py` drove a namespace with no `CACHES`, so stage 1's only third-party-import line never ran inside the `no_network` and no-cursor guards. A Redis alias added there; the shared factory deliberately left alone.
  - `[low]` `[patch]` `_refuse_in_process_cache`'s docstring said "Three inputs are skipped"; there are five. Count corrected and the untested non-dict `CACHES` input given a case.
  - `[low]` `[patch]` Truthiness of `CELERY_TASK_ALWAYS_EAGER` was documented at length and asserted nowhere; a case now pins a truthy non-`True` value (`"false"`, the shape an env-driven settings module produces).
  - `[low]` `[patch]` `_refuse_eager_tasks`'s message said "Leave it unset" while `False` is an accepted state a test asserts. Reworded to match the contract.
  - `[low]` `[patch]` The balance test keyed depth per feature, so cross-feature interleaving passed — the arrangement in which a line-based stripper orphans the other feature's closing marker. Interleaving now asserted.
  - `[low]` `[patch]` `test_no_region_is_gated_by_a_module_level_branch` walked only `tree.body`, missing a gate inside a module-level `try`/`with`/`for`/`match`. Now walks module scope without descending into function, class or lambda bodies.
  - `[low]` `[patch]` `_sole_line_matching` interpolated a function name into a regex unescaped; `re.escape` applied. `test_the_roster_itself_carries_no_conditional_entry` used a bare `next(...)` that would die with `StopIteration` instead of reporting; given a default and a message.
  - `[low]` `[patch]` Stale counts in prose: `tests/conftest.py` said "Three modules" (seven consumers), the new file said "four other modules", and `test_stage_one_conditions.py` routed the reader to half the stage-2 surface. Counts replaced by properties; redirect completed.
  - `[low]` `[patch]` Nothing pinned `[tool.ruff]`, though the key added here *replaces* ruff's default `task-tags` and the markers depend on `ERA` staying selected. A `tomllib`-based test now pins both.

**Deferred (2 · both medium)** — recorded in `deferred-work.md`: the `F401` orphan imports a stripped region leaves behind, and whether `FileBasedCache`/`DatabaseCache` belong in condition 8's forbidden set.

**Rejected (5)** — eager execution set on the Celery app rather than settings (checked: `config/celery_app.py:26` takes its whole configuration from `django.conf:settings`, so settings is the only source); widening `isinstance(caches, dict)` to `Mapping` (Django's settings contract requires a dict, and the import would become another orphan); the duplicated `namespace`/`_refusal` helpers (five lines, and the two modules' autouse needs differ); "no test asserts the fourteen-state total" (Story 4.5 owns that audit by name); and the objection that AC #3's runtime half is tracked only in a test docstring (the story authorises exactly that, and Epic 8's gate is where it becomes provable).

## Auto Run Result

Status: done

**What was implemented.** Conditions 8 and 9 of the refusal contract — the only two of the fourteen forbidden states that are feature-scoped. An in-process cache backend where the Redis feature is selected, and eager task execution where background task processing is selected. Both evaluate at settings import, both are deployed-only through `run_stage_one`'s existing early return, both raise `ImproperlyConfigured` and nothing else. Neither is guarded by a runtime flag: they are delimited as AD-24 feature-owned regions by paired `# feature:<name>` / `# /feature:<name>` line comments, so a combination that did not select the feature does not contain the condition at all. This is the first code in the repository to carry those markers.

**Files changed**

| Path | Change |
|---|---|
| `src/config/startup/stage_one.py` | Conditions 8 and 9, two marker pairs each (definition and roster entry are not adjacent), their `_STAGE_ONE` entries, and the region-declaration block that stands in for `accelerator.toml` until Epic 7. |
| `tests/unit/startup/test_feature_scoped_refusals.py` | NEW. Both conditions, their negatives, the subclass evasion, all five skip paths, and the AST-based marker balance/pairing/interleaving/enclosure/declaration-reconciliation suite. |
| `tests/unit/startup/test_stage_one_conditions.py` | `EXPECTED_EVALUATION_ORDER` gains both names, each inside its own marker pair; stale docstring counts corrected. |
| `tests/unit/startup/test_no_network_no_queries.py` | Namespace declares a Redis `CACHES` alias so NFR-1 is asserted over the code path condition 8 actually takes. |
| `tests/conftest.py` | Docstring only — a stale consumer count replaced by the property. |
| `pyproject.toml` | `lint.task-tags` gains `"feature"`, without which `ERA001` reads every opening marker as commented-out code and the gate fails. |

**Review findings:** 16 patches applied, 2 deferred, 5 rejected. Breakdown and reasoning in the triage log above.

**Verification performed**

- `pixi run ci` exits 0 — pre-commit, build, mypy strict over `src/`, ruff over the tree, full suite at **96.78%** against a floor of 90. Run independently of the implementation agents, twice: once after implementation and once after the review patches. 1105 tests pass; `src/config/startup/stage_one.py` is at 100%.
- **Materialization rehearsed rather than assumed.** All four regions were stripped from the three marker-bearing files in three combinations — redis removed, celery removed, both removed. Every stripped copy parses and `ruff format --check` reports no reformatting needed. This is what moved the markers flush against their code and relocated the feature-neutral test class to the end of its file.
- **Ruff `ERA001` reproduced and cleared empirically**, and the `task-tags` remedy probed before it was chosen over `# noqa` per marker (which would change the marker text Story 8.3's stripper has to match).
- The `import_string` escape was reproduced twice, by two independent reviewers, before the guard was widened; the fix was mutation-checked by reverting it and confirming the new test is what fails.

**Residual risks**

1. **Stripping a region leaves `F401` unused imports** — three in `stage_one.py`, four in the new test file. `ruff check` fails on them, so a materialized combination does not pass its own gate until Epic 8 prunes orphan imports. It cannot be closed here: a marker pair inside the sorted import block does not survive ruff's isort, which was probed. Deferred and recorded.
2. **AC #3's runtime half is unproven** and cannot be proven in this story — "in a combination without the feature, neither condition is evaluated" needs a materialized combination, and `tools/materializer/` and the six-environment matrix are Epic 8. The mechanism is asserted instead; the story itself scopes this as a traceability marker.
3. **The declaration block is prose in a docstring.** It is reconciled against the markers in both directions by test, but a parser over prose is more fragile than the `accelerator.toml` array Epic 7 replaces it with. It is anchored on the structured `path`/`feature` prefix only, not on the surrounding wording.
4. **`FileBasedCache` and `DatabaseCache` pass condition 8.** Both fail the way the refusal message describes. Whether they belong in the forbidden set is a change to an architecturally settled count, not this story's call — deferred to whoever owns the refusal table.
