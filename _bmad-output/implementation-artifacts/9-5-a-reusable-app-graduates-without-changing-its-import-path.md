# Story 9.5: A reusable app graduates without changing its import path

Status: ready-for-dev

## Story

As a developer of a reusable app,
I want my application importable by the same name in the tenant space and once installed from the channel,
so that graduating it breaks nothing in the components that adopt it.

## Acceptance Criteria

**Traceability:** FR-53 · AD-6, AD-8

1. **Given** the same application
   **When** it lives in the tenant space and when it is installed from the approved channel
   **Then** it is importable by the same name in both residencies

2. **Given** graduation
   **When** it occurs
   **Then** it requires no change to the installed-application list, imports, or migration references of any component that adopts it

3. **Given** adoption
   **When** it occurs
   **Then** it is explicit: a `pixi.toml` line and a `component.toml` entry

4. **Given** installation
   **When** a package is installed
   **Then** nothing self-registers
   **And** entry-point discovery is forbidden, because an in-repo application has no distribution metadata and the two residencies would diverge

5. **Given** a reusable application
   **When** a component may depend on it
   **Then** it must have reached the approved channel first

## Tasks / Subtasks

- [ ] Task 1 — Define the two residencies precisely (AC: #1, #2)
  - [ ] Residency A (tenant): the application is a directory `src/django_apps/<name>/` with no parent `__init__.py`; the `sources` remapping in `[tool.hatch.build.targets.wheel]` (Stories 1.6, 9.2) puts `src/django_apps` on the import root, so it imports as `<name>`.
  - [ ] Residency B (channel): the application is a conda-forge package declared in `pixi.toml [dependencies]`, installing a top-level package `<name>` into site-packages. Same import name, different residency.
  - [ ] Write this down in `docs/` as the graduation procedure: move the directory out of `src/django_apps/`, publish it to the channel, replace nothing else. In particular, `INSTALLED_APPS` keeps the entry `"<name>"`, imports keep `from <name>… `, and migration references keep `("<name>", "0001_initial")`.

- [ ] Task 2 — Make adoption explicit and mechanical (AC: #3)
  - [ ] Adoption of a channel-resident application is exactly two edits: a line in `pixi.toml [dependencies]` (conda-forge, version-pinned) and an entry in `component.toml`'s adopted-application list. Nothing else.
  - [ ] Adoption of a tenant-resident application is one edit: the `component.toml` entry. The `pixi.toml` line is what the channel residency needs and nothing more — record that asymmetry beside the adopted-application list in `component.toml`.
  - [ ] The `component.toml` entry is what the composition step (Story 9.4) iterates, and its position in the list is the append order. Do not add the application to `INSTALLED_APPS` by hand — the contribution does it.

- [ ] Task 3 — Forbid self-registration structurally (AC: #4)
  - [ ] New `tests/unit/test_no_self_registration.py`. AST-scan every `*.py` under `src/config/` and `src/django_service/` and assert none of them references `importlib.metadata.entry_points`, `importlib.metadata.distributions`, `pkg_resources`, or `pkgutil.iter_modules` over an installed-package path.
  - [ ] Assert the composition step's only discovery mechanism is `importlib.import_module` on a name read from `component.toml` — resolve the call node in `src/config/settings/composition.py` and assert the module-name argument is not a literal.
  - [ ] Assert that no `AppConfig.ready()` in `src/django_service/` mutates settings, `INSTALLED_APPS`, or `DATABASE_ROUTERS`; a self-registering app would be the same defect wearing a different hat.
  - [ ] Record the reason in the test docstring: an in-repo application has no distribution metadata, so an entry-point mechanism would work in one residency and not the other — which is exactly the divergence AD-8 refuses.

- [ ] Task 4 — Enforce the channel-before-dependency rule (AC: #5)
  - [ ] Extend `tests/unit/test_dependency_policy.py` (existing, 45+ lines, already parses `pixi.toml` via a module-scoped `manifest` fixture): for every adopted application in `component.toml` that is **not** a directory under the carrier's tenant root, assert it appears in `pixi.toml [dependencies]` and does **not** appear in `[pypi-dependencies]`.
  - [ ] Reuse that file's existing `OWN_PACKAGE` exemption; a graduated reusable app is never an exemption, it is a conda-forge dependency like any other.
  - [ ] Message on failure must state the rule in the spine's own words: "A reusable app must reach the channel before a component may depend on it."

- [ ] Task 5 — Prove residency-independence with one test body run twice (AC: #1, #2)
  - [ ] New `tests/integration/test_graduation.py`, all tests marked `@pytest.mark.integration`.
  - [ ] Build one minimal application source tree in `tmp_path` — `apps.py` (`class BillingConfig(AppConfig): name = "billing"`), `models.py` with one model, `migrations/0001_initial.py`, `contribution.py` per Story 9.4.
  - [ ] Materialize it into two residencies from that one source: (A) `tmp_path/tenant/django_apps/billing/` with `tmp_path/tenant/django_apps` prepended to `sys.path`; (B) `tmp_path/site/billing/` with `tmp_path/site` prepended, standing in for site-packages.
  - [ ] Parameterize a single test body over both residencies asserting: `importlib.import_module("billing").__name__ == "billing"`; `AppConfig.create("billing").label == "billing"`; the migration module resolves as `billing.migrations`; the contribution module resolves as `billing.contribution`.
  - [ ] Assert the two residencies produce identical values for all four — a test that runs twice and compares is what makes AC #2 an assertion rather than a hope.
  - [ ] Restore `sys.modules`, `sys.path` and the Django app registry in teardown.

- [ ] Task 6 — Document the graduation procedure (AC: #2, #3)
  - [ ] Add `docs/extension-model.md` (or the section of the existing docs tree that Epic 8's NFR-8 rule assigns to component-facing documentation) covering: where a reusable application lives, the two adoption edits, what graduation changes (residency) and what it never changes (import path, `INSTALLED_APPS`, migration references), and that nothing self-registers.
  - [ ] NFR-8: documentation travels with what it describes. This page describes a component-facing capability, so it travels with the component; give it the disposition that makes that true in `accelerator.toml`.

- [ ] Task 7 — Tests and gate (AC: all)
  - [ ] `pixi run test`, `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-6 (binding):** "`src/django_apps/` contains no `__init__.py`. An app at `src/django_apps/billing/` is imported and installed as `billing`, unqualified. **Graduating it to a channel package changes its residency and never its import path.**" *Prevents:* "an app's import path changing at the moment it becomes reusable, breaking every consuming component's `INSTALLED_APPS`, imports and migration references."
- **AD-8 (binding):** "Adoption is explicit — a `pixi.toml` line and a `component.toml` entry. Nothing self-registers; entry-point discovery is forbidden because an in-repo app has no distribution metadata and the two residency modes would diverge."
- **AD-7:** the `sources` remapping is "a directory-level construct, so adding an app needs no per-app edit and AD-6's graduation promise holds." Graduation must not require a build-configuration edit either.
- **Spine Consistency Conventions — Supply chain:** "conda-forge only; `[pypi-dependencies]` carries the editable self-install and nothing else. … **A reusable app must reach the channel before a component may depend on it.**"
- **Spine Consistency Conventions — Test location:** "A tenant app's tests live **inside the app**, because they must graduate with it." The graduation tests in this story test the *mechanism*, live in `tests/`, and are `core`.
- **NFR-8:** documentation travels with what it describes.

**Must not do:**
- Do not implement discovery through entry points, `pkg_resources`, a settings scan, or an `AppConfig.ready()` side effect.
- Do not make the import name depend on residency, on a settings value, or on a per-app build entry.
- Do not add a reusable application to `[pypi-dependencies]` — that is a supply-chain exception and `tests/unit/test_dependency_policy.py` fails until one is deliberately recorded with an exit condition.
- Do not ship a demo application in `src/django_apps/`; tenant paths are never pruned and would travel into every component.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tests/unit/test_dependency_policy.py` | UPDATE | Exists today. Opens with `"""Tests for the supply-chain policy declared in pixi.toml."""`, defines `PIXI_MANIFEST = Path(__file__).resolve().parents[2] / "pixi.toml"`, `OWN_PACKAGE = "django-15-factor-base"`, a module-scoped `manifest` fixture, `test_manifest_is_present`, and `test_no_third_party_package_index_dependencies` asserting `set(manifest["pypi-dependencies"]) == {OWN_PACKAGE}`. **Preserve all of it**; add the adopted-application channel check as new test functions and a `component.toml` fixture beside the existing one. |
| `tests/unit/test_no_self_registration.py` | NEW | The AST scan of Task 3. |
| `tests/integration/test_graduation.py` | NEW | The two-residency parameterized test of Task 5. |
| `component.toml` | UPDATE | **Does not exist today** (Story 5.1). Add the asymmetry note beside the adopted-application list. |
| `pixi.toml` | UPDATE | `[dependencies]` (line 14 onward) is where a graduated application's channel line goes. No entry is added by this story — the reference application adopts nothing; the test must be correct over an empty adopted list. |
| `docs/extension-model.md` | NEW | The graduation procedure. `docs/` exists at the repository root. |
| `accelerator.toml` | UPDATE | **Does not exist today** (Story 7.1). Give the new documentation page a travelling disposition per NFR-8. |

Verified today: `pixi.toml` `[pypi-dependencies]` (line 98) contains only `django-15-factor-base = { path = ".", editable = true }`, with a comment stating that a third-party package appearing there is a supply-chain exception that `tests/unit/test_dependency_policy.py` fails on. `docs/` exists. `component.toml`, `accelerator.toml` and `src/django_apps/` do not.

### Testing Requirements

- Unit: `tests/unit/test_no_self_registration.py` and the additions to `tests/unit/test_dependency_policy.py` — TOML and AST parsing only, no marker.
- Integration: `tests/integration/test_graduation.py` — every test carries `@pytest.mark.integration`; uses `tmp_path` and `monkeypatch.syspath_prepend`; must restore `sys.path`, `sys.modules` and the Django app registry so the suite stays order-independent.
- Assertions the ACs demand:
  - identical import name, app label, migration module and contribution module across both residencies (AC #1, #2);
  - the adoption surface is exactly a `pixi.toml` line plus a `component.toml` entry (AC #3);
  - no entry-point or metadata-scanning call exists in `src/` (AC #4);
  - every non-tenant adopted application is a conda-forge dependency and never a package-index one (AC #5).
- Both the empty-adopted-list case (the reference application today) and the populated case must be covered; the empty case is where an over-eager loop silently passes.
- Disposition: covers `core` composition and machinery surface; lives under `tests/`, never pruned.
- AD-20 floor: ninety percent including templates, `COVERAGE_CORE=ctrace` in force. `pixi run ci` must exit 0.

#### Project Structure Notes

The Structural Seed places `src/django_apps/` as "tenant — path root, no `__init__.py` (AD-6)"; this story adds no source there and instead proves the residency property from outside.

Variance today: Stories 1.6 and 9.2 own the `sources` remapping that makes residency A work; Story 5.1 owns `component.toml`; Story 9.4 owns the contribution module this story's fixture ships. All three must land first. The reference application adopts no applications, which is a valid state (Story 5.1: "an empty adopted-application list is valid and requires no special case") and is the state every test here must also handle.

Python 3.14 only; conda-forge only; `pixi run` for everything.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.5]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-6]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-8]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-7]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — supply chain; test location
- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.2] — the tenant path root
- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.4] — the contribution module the fixture application ships
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.1] — an empty adopted-application list is valid
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.7] — the package-index policy this story's check extends

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
