# Story 9.2: The tenant space is a path root that is never judged

Status: ready-for-dev

## Story

As a lead developer,
I want one declared location for the applications my team owns,
so that my own code is neither pruned nor reported as an orphan.

## Acceptance Criteria

**Traceability:** FR-52 · AD-6, AD-7

1. **Given** `src/django_apps/`
   **When** it is created
   **Then** it contains no `__init__.py`
   **And** an application at `src/django_apps/billing/` is imported and installed as `billing`, unqualified

2. **Given** the tenant disposition
   **When** the materializer runs
   **Then** it neither prunes nor reports the tenant space
   **And** a path there is never an orphan and never excluded as unclaimed

3. **Given** the single import-root declaration site from Story 1.6
   **When** the second root is added
   **Then** it is added at that same site through the `sources` remapping
   **And** no second declaration site is created

4. **Given** a component with applications of its own
   **When** it runs its gate
   **Then** it passes the same gate as one without

5. **Given** the tenant-space location
   **When** it is declared
   **Then** it is named in the carrier

## Tasks / Subtasks

- [ ] Task 1 — Create the tenant path root (AC: #1)
  - [ ] Create the directory `src/django_apps/` with **no `__init__.py`**. It is a path root, not a package.
  - [ ] Add `src/django_apps/.gitkeep` (empty) so an otherwise-empty root is tracked by git, and a short `src/django_apps/README.md` stating: apps here are imported unqualified; there is no `__init__.py` and adding one is a defect; a tenant app's tests live inside the app so they graduate with it.
  - [ ] Do not add an example or demo app to the tree. Tenant paths travel into every component (AD-2: `tenant` is never pruned), so a demo `billing/` would ship to every component forever.

- [ ] Task 2 — Add the second import root at the single declaration site (AC: #3)
  - [ ] Edit `[tool.hatch.build.targets.wheel]` in `pyproject.toml` (currently lines 126–127) so the `sources` remapping Story 1.6 introduced lists both roots: `src` and `src/django_apps`. One table, two entries — no new site.
  - [ ] Update the comment above the table (currently `# src/ is the import root; config and django_service are both top-level packages.`) to state both roots and that the construct is directory-level, so adding an app needs no per-app edit — which is what makes AD-6's graduation promise hold.
  - [ ] Do not add `--app-dir`, a `sys.path` insert, a `pythonpath` entry, a `.pth` file, or a `conftest.py` path hack anywhere. `uvicorn --app-dir` accepts one directory and is never a declaration mechanism (AD-7).

- [ ] Task 3 — Declare the tenant space in the carrier (AC: #2, #5)
  - [ ] In `accelerator.toml` (Story 7.1), name the tenant-space location — a single key such as `tenant_root = "src/django_apps"` beside the disposition table — and give `src/django_apps/` the `tenant` disposition covering the whole subtree.
  - [ ] Record the rationale in place: `tenant` answers "never judged, never pruned"; a path there is never an orphan and never excluded as unclaimed.

- [ ] Task 4 — Make the reconciliation and orphan checks honour `tenant` (AC: #2)
  - [ ] In the input-reconciliation check (Story 7.1) and the orphan detectors (Story 7.8), skip everything beneath the declared `tenant_root`: it neither fails as "claimed by no disposition" nor is reported as residue. Read the root from the carrier — never hardcode the string in the checker.
  - [ ] In the materializer's path-pruning pass (Story 8.2), treat `tenant` as travelling and never prunable, and exclude it from output-reconciliation orphan reporting (Story 8.7).
  - [ ] These are edits to modules Epics 7 and 8 create; if a hook does not exist yet, add the branch where the disposition is dispatched, not as a special case at the call site.

- [ ] Task 5 — Gate test: the root is a root, not a package (AC: #1, #3, #5)
  - [ ] New `tests/unit/test_tenant_space.py`.
  - [ ] Assert `src/django_apps/` exists and that `src/django_apps/__init__.py` does **not** exist.
  - [ ] Assert `accelerator.toml` names the tenant root and that its value is the directory that exists on disk.
  - [ ] Assert `pyproject.toml`'s `[tool.hatch.build.targets.wheel]` `sources` contains both `src` and `src/django_apps`, and that no other file in the repository declares an import root: no `sys.path` mutation in `manage.py`, `src/config/asgi.py`, `src/config/wsgi.py`; no `[tool.pytest.ini_options] pythonpath`; no `--app-dir` in any `pixi.toml` task string. Parse the files, do not grep the whole tree.

- [ ] Task 6 — Test: an app under the root imports and installs unqualified (AC: #1, #4)
  - [ ] In `tests/integration/test_tenant_app_residency.py` (marked `@pytest.mark.integration`), build a minimal Django app under `tmp_path/django_apps/billing/` — `apps.py` with `class BillingConfig(AppConfig): name = "billing"`, `models.py`, `migrations/__init__.py` — mirroring what the `sources` remapping does at install time by prepending `tmp_path/django_apps` to `sys.path` via `monkeypatch.syspath_prepend`.
  - [ ] Assert `importlib.import_module("billing")` succeeds and that the import name is `billing`, not `django_apps.billing`.
  - [ ] Assert the app installs unqualified: `django.apps.apps.populate` over a list containing `"billing"` in an isolated registry, or `AppConfig.create("billing")` resolving `BillingConfig` with `label == "billing"` and migration module `billing.migrations`.
  - [ ] Restore `sys.modules` and the app registry in teardown — an integration test must leave state as it found it.

- [ ] Task 7 — Test: the gate is identical with and without tenant apps (AC: #4)
  - [ ] Assert the gate's disposition and orphan checks return the same result for a tree with a tenant app present and one without, by running the reconciliation function twice over a `tmp_path` copy that differs only by the presence of `django_apps/billing/`.
  - [ ] `pixi run test`, `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-6 (binding):** "`src/django_apps/` contains no `__init__.py`. An app at `src/django_apps/billing/` is imported and installed as `billing`, unqualified. Graduating it to a channel package changes its residency and never its import path." *Prevents:* "an app's import path changing at the moment it becomes reusable, breaking every consuming component's `INSTALLED_APPS`, imports and migration references."
- **AD-7 (binding):** "There are five import-root declaration sites in this repository and after this AD there is one. … Retained: `[tool.hatch.build.targets.wheel]`, which declares both roots via a `sources` remapping of `src/` and `src/django_apps/` — a directory-level construct, so adding an app needs no per-app edit and AD-6's graduation promise holds. `uvicorn --app-dir` accepts one directory and is therefore never a declaration mechanism." *Prevents:* "a second source root working under `pytest` and failing under `gunicorn`."
- **AD-2 (binding):** `tenant` is "never judged, never pruned". Unlisted paths default to `machinery`, so the tenant root must be declared or every app beneath it would be treated as accelerator machinery and silently dropped.
- **AD-1:** the tenant-space location is declared in `accelerator.toml` and nowhere else.
- **Spine Consistency Conventions:** "A tenant app's tests live **inside the app**, because they must graduate with it." Do not create `tests/unit/django_apps/`.

**Must not do:**
- Do not add `src/django_apps/__init__.py`. It would make apps import as `django_apps.billing` and break AD-6's graduation promise irreversibly for every consuming component.
- Do not create a second import-root declaration site of any kind (AD-1, AD-7).
- Do not ship an example tenant app in the reference application.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/django_apps/` | NEW | The tenant path root. No `__init__.py`. |
| `src/django_apps/.gitkeep` | NEW | Empty; keeps the root tracked. |
| `src/django_apps/README.md` | NEW | States the unqualified-import rule and the tests-live-inside-the-app convention. |
| `pyproject.toml` | UPDATE | Lines 126–127 today read `[tool.hatch.build.targets.wheel]` / `packages = [ "src/config", "src/django_service" ]`, with the comment `# src/ is the import root; config and django_service are both top-level packages.` at line 125. **Story 1.6 converts `packages` to a `sources` remapping**; this story adds `src/django_apps` to that same `sources` value. If Story 1.6 has not landed, do it there, not here — do not add a parallel key. |
| `accelerator.toml` | UPDATE | **Does not exist today** (Story 7.1). Add the tenant-root key and the `tenant` disposition for `src/django_apps/`. |
| Reconciliation / orphan / materializer modules | UPDATE | Created by Stories 7.1, 7.8, 8.2, 8.7. Add the `tenant` skip, driven by the carrier value. |
| `tests/unit/test_tenant_space.py` | NEW | Static assertions of Task 5. |
| `tests/integration/test_tenant_app_residency.py` | NEW | Import/installation behaviour of Tasks 6–7. |

Verified against the repo today: `src/django_apps/` does **not** exist; `src/` contains only `config/` and `django_service/`. `pyproject.toml:126-127` holds `packages = [ "src/config", "src/django_service" ]` — the range still holds. `pyproject.toml:149` still carries `pythonpath = [ "src", "." ]`, and `pixi.toml`'s `serve` task still carries `--app-dir src`; both are Story 1.6's removals, not this story's.

### Testing Requirements

- `tests/unit/test_tenant_space.py` — no I/O beyond reading two TOML files; unit.
- `tests/integration/test_tenant_app_residency.py` — every test carries `@pytest.mark.integration`; uses `tmp_path` and `monkeypatch.syspath_prepend`; restores `sys.modules` and the Django app registry so the suite is order-independent.
- Assertions: no `__init__.py` at the root; carrier names the root; both roots at one site; no other site declares a root; `import billing` resolves unqualified; `billing.migrations` is the migration module; gate result identical with and without a tenant app.
- Disposition: these tests cover the carrier and the build configuration, both `core`/`machinery` surface of the accelerator; they live under `tests/` and are never pruned by a feature.
- AD-20 floor: ninety percent including templates, `COVERAGE_CORE=ctrace` in force. `pixi run ci` must exit 0.

#### Project Structure Notes

The Structural Seed shows `src/django_apps/    # tenant — path root, no __init__.py (AD-6)` as a sibling of `config/` and `django_service/`. This story creates exactly that.

Variance today: neither `accelerator.toml` nor the disposition machinery exists, so Tasks 3–4 are edits to files Epic 7 and Epic 8 create. `src/config/settings/base.py:16-17` already carries the comment "src/ itself is the import root and is deliberately not a package", which is consistent with adding a second non-package root beside it; `APPS_DIR` at `base.py:18` points at `src/django_service` and must not be repurposed to point at the tenant root.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-6]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-7]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Structural Seed]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — tenant app tests live inside the app
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.6] — the five sites collapse to one; this story adds the second root without adding a second site
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.8] — the orphan detectors this story must teach about `tenant`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
