# Story 7.7: Every feature's surface is complete and independently removable

Status: ready-for-dev

## Story

As a lead developer,
I want each feature's code, dependencies, settings, templates and tests grouped so the feature can be excluded cleanly,
so that removing a feature is a declared operation rather than an archaeology exercise.

## Acceptance Criteria

**Traceability:** FR-28 · AD-2 · SC-2

1. **Given** any path in the reference application
   **When** input reconciliation runs
   **Then** every path is claimed by exactly one disposition
   **And** removing background task processing is a declared set of paths and regions rather than a manual trace through ten files

2. **Given** a feature's tests
   **When** their disposition is assigned
   **Then** they carry the disposition of what they cover, so a feature's tests are `feature:<name>` and are pruned with it

3. **Given** the immovable-core assertion suite
   **When** its disposition is assigned
   **Then** it is `core` and is never pruned by any feature

4. **Given** a tenant application's tests
   **When** their location is decided
   **Then** they live inside the application, because they must graduate with it

5. **Given** a feature's code
   **When** its imports are inspected
   **Then** it never imports another feature's code

## Tasks / Subtasks

- [ ] Task 1 — Close the disposition sweep: every tracked path claimed exactly once (AC: #1)
  - [ ] Story 7.1 built the reconciler and declared the bulk of the tree, deliberately leaving UI and storage surface claimed as `core` until Stories 7.4 and 7.5 moved and created it. Those stories have landed. Sweep the whole tracked set again and correct every entry that is now wrong.
  - [ ] Re-run `reconcile_input` over the real carrier and `git ls-files`. Zero failures is the exit condition, not the starting assumption.
  - [ ] Strengthen the reconciler from "resolves to a disposition" to **"resolves to exactly one disposition"**: detect and fail on a path matched by two claims of different dispositions, and on a path matched by two claims of the same disposition where one is a glob and the other is a literal (ambiguity is a maintenance hazard even when the answer agrees today).
  - [ ] Add an `explain` capability — `Carrier.explain(path) -> str` naming the claim that produced a path's disposition. AC #1's second clause is about a human being able to answer "what does removing celery delete?" without tracing ten files; the reconciler must be able to answer the inverse per path.

- [ ] Task 2 — Make each feature's removal a single declared query (AC: #1)
  - [ ] Add `Carrier.surface_of(feature: str) -> FeatureSurface` returning, in one structure: the feature's paths, its regions (path + feature), its packages, and its tests. This is what turns AC #1's second clause into a mechanism.
  - [ ] Worked case the AC names — **background task processing**. Its declared surface, as it stands after Stories 7.2, 7.4 and 7.5, is: packages `celery`, `django-celery-beat`, `django-timezone-field`, `python-crontab`, `cron-descriptor`, `opentelemetry-instrumentation-celery`; regions in `pixi.toml` (those dependency lines, plus the `worker` and `beat` tasks once Story 5.2 adds them), `src/config/settings/base.py` (the Celery block `:296-335` and the `django_celery_beat` installed-app entry `:110`), `src/config/settings/local.py` (the eager-execution settings and Story 4.4's feature-scoped refusal), `src/config/observability/telemetry.py` (the `CeleryInstrumentor` import `:21` and call `:135`); paths `src/config/celery_app.py` and the celery tests. **`src/django_service/users/tasks.py` is not on that list**: Story 7.4 deletes it rather than relocating it (AD-29 — `feature:celery` code inside a package that is `core` in its entirety), and `tests/integration/users/test_tasks.py` goes with it. A deleted path carries no disposition; if either still exists when this story runs, that is Story 7.4 unfinished, not a surface to declare here. Verify each against the tree; add anything the sweep finds that this list omits.
  - [ ] **`src/config/celery_app.py` exists and is not yet dispositioned as a feature path.** It is a top-level module in the composition root; it is `feature:celery` in its entirety. `tests/unit/test_celery_app.py` covers it and carries the same disposition. Check what imports it — `src/config/__init__.py` is the conventional place — and make any such import a declared `feature:celery` region rather than a conditional import (AD-24).
  - [ ] Repeat the same completeness pass for `redis` and `storage` — **the three features are `celery`, `redis`, `storage` and there is no `ui`** (AD-29, revision 3) — and record each feature's full surface in the carrier so a reader can answer the removal question from the declaration alone. Two of the three have an empty `paths` list, since AD-33 is retired and no feature owns a package: `redis` is regions and dependency entries, `storage` is regions, dependency entries and its own tests.

- [ ] Task 3 — Disposition every test by what it covers (AC: #2, #3, #4)
  - [ ] Apply the spine's convention: *"Accelerator and base tests live under `tests/`, mirroring `src/`, and carry the disposition of what they cover — a feature's tests are `feature:<name>` and are pruned with it, except the immovable-core assertion suite (AD-30), which is `core`. A tenant app's tests live inside the app, because they must graduate with it."*
  - [ ] Walk the existing suite and assign: `tests/conftest.py`, `tests/__init__.py`, `tests/factories.py`, `tests/unit/conftest.py`, `tests/integration/conftest.py` — `core` (shared fixtures reachable in every combination; if any fixture is feature-specific, move it into the feature's own conftest rather than dispositioning a shared file to a feature). `tests/unit/test_celery_app.py` — `feature:celery`. `tests/unit/test_telemetry.py` — `core`, but audit it: it must not assert on `CeleryInstrumentor` or `RedisInstrumentor` unconditionally, or it fails in the **four** combinations with no Celery and the **two** with no Redis respectively; split the feature-specific assertions into `feature:<name>` test modules. `tests/unit/test_settings.py` — same audit for Celery and Redis settings assertions. `tests/unit/test_dependency_policy.py`, `test_observability_init.py`, `test_observability_logging.py` — `core`. `tests/integration/test_request_logging.py`, `test_template_rendering.py` — `core`. `tests/unit/users/*`, `tests/integration/users/*` — all `core`, because `django_service` is `core` in its entirety and nothing moves out of it (AD-29, revision 3). The one module that is not `core` is not re-dispositioned either: Story 7.4 **deletes** `tests/integration/users/test_tasks.py` along with the `tasks.py` it covers, so if it is still present, resolve that before dispositioning it.
  - [ ] AC #3: declare the **immovable-core assertion suite** as `core` in the carrier. AD-30 makes it the only thing defending SC-7. The suite itself is written in Epic 8 (it must run inside every combination's gate); this story declares its location and its `core` disposition so it cannot later be created under a feature-scoped path by accident. Reserve the path — for example `tests/immovable_core/` — and add a gate test asserting no `feature:*` disposition claims anything under it.
  - [ ] AC #4: declare the tenant-test convention in the carrier — a tenant app's tests live inside the app under `src/django_apps/<app>/`, not under `tests/`. `src/django_apps/` does not exist yet (Epic 9 creates it); the declaration is the deliverable here, and the `tenant` disposition already means never judged and never pruned (AD-2).
  - [ ] Add a gate test asserting no test module under `tests/` resolves to `tenant`, and no path under the declared tenant root resolves to anything but `tenant`.

- [ ] Task 4 — Enforce cross-feature import isolation (AC: #5)
  - [ ] AD-4: *"A feature's code may never import another feature's."* Build an AST-based import check: for every path dispositioned `feature:<name>`, parse it and resolve each import to a disposition via the carrier; fail on any import resolving to `feature:<other>`.
  - [ ] Assert the rest of AD-4's direction rules in the same check, since they share the machinery and Epic 9 will otherwise duplicate it: a tenant app may import `django_service`; `django_service` may never import a tenant app; `config` may import `django_service` and reaches tenant apps only through settings composition, never by direct import.
  - [ ] Resolve module names to paths using the carrier and the declared import roots, not by string prefix matching — the same discipline AD-26 applies to refusal predicates. A check that matches `"celery" in import_line` would flag `opentelemetry.instrumentation.celery` inside the celery feature's own file and miss a re-exported symbol.
  - [ ] Known case to get right: `src/config/observability/telemetry.py` is `core` and imports both `CeleryInstrumentor` and `RedisInstrumentor` inside declared `feature:*` regions. The check must resolve an import's disposition to the **region** it sits in, not to the file's disposition, or every region-bearing `core` file reads as a violation.

- [ ] Task 5 — Nothing present-but-skipped (AC: #1, #2)
  - [ ] FR-28: an excluded feature leaves *"no dependency, template, static asset, settings fragment, or test, and nothing present-but-skipped."*
  - [ ] Add a gate test asserting no test in the suite is marked `@pytest.mark.skip`, `@pytest.mark.skipif` or `@pytest.mark.xfail` on the basis of a feature's absence. A feature's tests leave with the feature; they are never present and skipped.
  - [ ] Add a gate test asserting no `pytest.importorskip` on a feature package, and no module-level `try/except ImportError` in the test tree used to tolerate an absent feature.
  - [ ] These are the test-side mirror of AD-24's forbidden mechanisms. Skipping is how a builder who cannot remove a test makes the suite pass, and it is exactly the residue SC-2 denies.

- [ ] Task 6 — Tests (AC: all)
  - [ ] `tests/unit/materializer/test_surface_of.py` (NEW): `surface_of` returns paths, regions, packages and tests for each feature; `explain` names the claim behind a path's disposition.
  - [ ] `tests/integration/materializer/test_exactly_one_disposition.py` (NEW), `@pytest.mark.integration`: every tracked path resolves to exactly one disposition; ambiguous claims fail; the whole-tree sweep reports zero failures.
  - [ ] `tests/integration/materializer/test_test_dispositions.py` (NEW), `@pytest.mark.integration`: every test module's disposition matches the disposition of what it covers; nothing under the immovable-core suite path is `feature:*`; nothing under `tests/` is `tenant`.
  - [ ] `tests/integration/materializer/test_import_isolation.py` (NEW), `@pytest.mark.integration`: the AD-4 direction rules, region-aware.
  - [ ] `tests/integration/materializer/test_no_present_but_skipped.py` (NEW), `@pytest.mark.integration`: the Task 5 assertions.
  - [ ] `pixi run ci` exits 0, coverage ≥90% including templates.

## Dev Notes

### Architecture Constraints

**AD-2 — every path carries exactly one disposition.** *"Four input dispositions, exhaustive and mutually exclusive — `core` (always travels), `feature:<name>` (travels only where selected), `tenant` (never judged, never pruned), `machinery` (never travels). Unlisted defaults to `machinery`."* Prevents: *"an unlisted path silently travelling into every component; a developer's own app being deleted or reported as an orphan; a generated artifact having no legal existence."* Input reconciliation is against the reference application; output reconciliation against each materialized tree is Story 8.7's.

**AD-4 — dependency direction across the three territories.** *"A tenant app may import `django_service`. `django_service` may never import a tenant app. `config` may import `django_service` and reaches tenant apps only through the settings composition step, never by direct import. A feature's code may never import another feature's."* Prevents: *"a base that depends on what is built on it; feature surfaces that cannot be independently removed."* AC #5 is the last clause; assert all four.

**AD-24 — regions, not mechanisms.** No conditional imports, no settings-module inheritance, no `try/except ImportError`. This story's Task 5 extends the same prohibition to the test tree: no skip, no `xfail`, no `importorskip` standing in for removal.

**AD-30 — the immovable-core assertion suite.** *"Separately, a `core`-disposed immovable-core assertion suite runs inside every combination's gate and is never pruned by any feature. AD-20's coverage signal defends SC-2; this suite is what defends SC-7, and nothing else does."* Prevents: *"the harness detecting residue and being structurally blind to excision damage — a feature extraction that removes too much passes every existing check, because the removed thing's tests left with it, coverage measures only what remains, and the smoke check never renders the page that broke."* This story declares the suite's location and disposition; Epic 8 writes it.

**AD-6 — `src/django_apps/` is a path root, not a package.** No `__init__.py`. An app at `src/django_apps/billing/` is imported and installed as `billing`, unqualified. Its tests live inside it so graduation changes residency and never the import path.

**AD-20 / CG-1 — do not answer a coverage drop with an omit entry.** A feature's tests leaving with the feature is correct; a `core` module losing coverage because its only test left is a defect in the disposition assignment, and it is fixed by moving the test or writing a `core` one — never by narrowing measurement.

**Spine Consistency Conventions, Test location** (quoted in full in Task 3) is the binding rule for AC #2, #3 and #4.

**Project standards.** Pixi is the only runner. Python 3.14 only. conda-forge only. PEP 8 / 120 / full type hints / Google docstrings. Never `print()`, never stdlib `logging`, never bare `except:`, never `except X: pass`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `accelerator.toml` | UPDATE | Complete the `[dispositions]` sweep; per-feature surface completion; the immovable-core suite path and its `core` disposition; the tenant-test convention. Preserve everything Stories 7.1–7.6 declared. |
| `tools/materializer/carrier.py` | UPDATE | Add `Carrier.surface_of()` and `Carrier.explain()`. Preserve all prior accessors. |
| `tools/materializer/reconcile.py` | UPDATE | Strengthen to exactly-one-disposition with ambiguity detection. Preserve the two input directions Story 7.1 built. |
| `tools/materializer/imports.py` | NEW | AST-based, region-aware AD-4 direction checker. |
| `src/config/celery_app.py` | UPDATE (disposition only) | **Today:** exists at the composition-root level; covered by `tests/unit/test_celery_app.py`. **Changes:** no code change; it gains a `feature:celery` disposition. If anything in `core` imports it, that import becomes a declared `feature:celery` region. |
| `tests/unit/test_telemetry.py` | UPDATE | **Today:** covers `src/config/observability/telemetry.py` including, potentially, the Celery and Redis instrumentor calls. **Changes:** split any Celery- or Redis-specific assertion into `feature:<name>` test modules so the `core` remainder passes in all six combinations. **Preserve:** the exporter-resolution, resource-building and idempotence-guard assertions, which are `core`. |
| `tests/unit/test_settings.py` | UPDATE | Same audit for Celery and Redis settings assertions. |
| `tests/unit/test_celery_app.py` | UPDATE (disposition only) | Becomes `feature:celery`. |
| `tests/{conftest,factories,__init__}.py`, `tests/unit/conftest.py`, `tests/integration/conftest.py` | UPDATE if needed | `core`. If a fixture is feature-specific, move it into a feature conftest rather than dispositioning a shared file to a feature. |
| `tests/unit/materializer/test_surface_of.py` | NEW | |
| `tests/integration/materializer/test_exactly_one_disposition.py` | NEW | `@pytest.mark.integration` |
| `tests/integration/materializer/test_test_dispositions.py` | NEW | `@pytest.mark.integration` |
| `tests/integration/materializer/test_import_isolation.py` | NEW | `@pytest.mark.integration` |
| `tests/integration/materializer/test_no_present_but_skipped.py` | NEW | `@pytest.mark.integration` |

**Test tree as it stands, verified 2026-08-15.** `tests/`: `__init__.py`, `conftest.py`, `factories.py`. `tests/unit/`: `__init__.py`, `conftest.py`, `test_celery_app.py`, `test_dependency_policy.py`, `test_observability_init.py`, `test_observability_logging.py`, `test_settings.py`, `test_telemetry.py`, and `users/{__init__,test_adapters,test_api_urls,test_urls}.py`. `tests/integration/`: `__init__.py`, `conftest.py`, `test_request_logging.py`, `test_template_rendering.py`, and `users/{__init__,test_admin,test_api_openapi,test_api_views,test_forms,test_models,test_tasks,test_views}.py`. Stale `__pycache__` entries exist for `tests/integration/test_zz_probe.py` and `test_zz_asgi.py`, whose source files are gone — they are untracked build artifacts, not paths needing a disposition, and confirm why the input set must be `git ls-files` rather than a directory walk.

**`src/config/` as it stands:** `__init__.py`, `api_router.py`, `asgi.py`, `celery_app.py`, `urls.py`, `websocket.py`, `wsgi.py`, plus `settings/` and `observability/`. `websocket.py` is deleted by AD-16 in Story 1.4 together with its `[tool.coverage.run] omit` entry (`pyproject.toml:168`) and the `sonar.coverage.exclusions` reference (`sonar-project.properties:24`); if that story has not landed, do not delete it here and do not disposition it as though it were gone. `src/config/authorization/` and `src/config/startup/` do not exist yet (Epics 2 and 4).

### Testing Requirements

- Unit: `tests/unit/materializer/test_surface_of.py` — isolated, milliseconds.
- Integration: the four new `tests/integration/materializer/` modules, every test `@pytest.mark.integration`, read-only against the repository, state left as found.
- The import-isolation check must be region-aware and resolution-based, not string-based. Write the `telemetry.py` case as an explicit test: `core` file, `feature:celery` region containing a `feature:celery` import — not a violation.
- Existing tests that must keep passing: the entire suite. Any test whose disposition changes keeps its assertions unchanged; only its location or its module split changes.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` in force (AD-20).

#### Project Structure Notes

- This story is the completeness pass over Stories 7.1–7.6, so it should be run last within the declaration group and re-run after Story 7.8 if 7.8 moves any declaration.
- **Variance:** `src/config/celery_app.py` is feature-owned code sitting in the composition root, which the Structural Seed describes as `core` — "Settings, URL configuration, observability, authorization, startup refusals, entrypoints. Assembles; owns no domain." A `feature:celery` path inside `src/config/` is legitimate under AD-2 (unlike inside `src/django_service/`, which AD-29 forbids), but it is worth recording explicitly so a later reader does not mistake it for a mis-disposition.
- **Variance:** the Seed does not name a location for the immovable-core assertion suite. Reserve one here so Epic 8 inherits it rather than choosing.
- `tests/` mirrors `src/` today for `users/` only. The new `tests/unit/materializer/` and `tests/integration/materializer/` mirror `tools/materializer/`, which extends the convention consistently — record it.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-4]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-6]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-16]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26] — predicates resolve objects, never strings; the same discipline applies to the import checker
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-30]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — Test location
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.7]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.7] — output reconciliation; traceability marker, not an acceptance condition here
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-28]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#SC-2]
- Repository, verified 2026-08-15: full `tests/` and `src/config/` listings; `src/config/settings/base.py:110,296-335`; `src/config/observability/telemetry.py:21,135`; `pyproject.toml:168`; `sonar-project.properties:24`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
