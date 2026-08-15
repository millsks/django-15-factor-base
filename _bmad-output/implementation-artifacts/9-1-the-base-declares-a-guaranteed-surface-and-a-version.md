# Story 9.1: The base declares a guaranteed surface and a version

Status: ready-for-dev

## Story

As a developer of a reusable app,
I want an explicit, versioned surface I may depend on,
so that a routine tidy-up inside the base does not become an estate-wide break.

## Acceptance Criteria

**Traceability:** FR-51 · AD-5, AD-29

1. **Given** the base package
   **When** its surface is declared
   **Then** the carrier enumerates the guaranteed surface explicitly
   **And** anything inside `django_service` not enumerated is internal and may change without a version bump

2. **Given** the guaranteed surface
   **When** any of the twelve combinations is inspected
   **Then** it is present in all twelve
   **And** no feature selection may remove part of it

3. **Given** `django_service.__api_version__`
   **When** it is declared
   **Then** it is a single integer bumped by hand on any breaking change and on the removal of any guaranteed surface

4. **Given** a breaking change
   **When** it is identified
   **Then** moving a module within the guaranteed surface, changing `AUTH_USER_MODEL`, or renaming a guaranteed setting each qualifies

5. **Given** the base package name
   **When** it is materialized
   **Then** it is `django_service` in every component and is never parameterized

6. **Given** the mapper epoch table from Story 2.5
   **When** its surface is classified
   **Then** it is internal
   **And** adding it is not an API version bump

## Tasks / Subtasks

- [ ] Task 1 — Declare `__api_version__` on the base package (AC: #3, #6)
  - [ ] Add `__api_version__: int = 1` to `src/django_service/__init__.py`, with a Google-style module-docstring paragraph stating the bump rule: hand-bumped on any breaking change and on the removal of any guaranteed surface.
  - [ ] Do **not** derive it from `importlib.metadata`, git tags, or `__version__`. The existing `__version__` / `__version_info__` block stays exactly as it is and is unrelated: `__version__` is the distribution version, `__api_version__` is the contract version, and an in-repo reusable app has no distribution metadata to read (AD-5).
  - [ ] Add a comment beside the constant listing the three breaking changes named by AC #4: moving a module within the guaranteed surface, changing `AUTH_USER_MODEL`, renaming a guaranteed setting.

- [ ] Task 2 — Enumerate the guaranteed surface in the carrier (AC: #1, #2, #4)
  - [ ] Add a `[base_surface]` table to `accelerator.toml` (created by Story 7.1) declaring, by explicit dotted path, every module, class and settings key a reusable app may depend on. Never by namespace or glob — an enumeration by prefix would make "anything not enumerated is internal" unenforceable.
  - [ ] Populate it from the tree as it stands after Epics 2–7: at minimum `django_service.users.models.User`, `django_service.users.apps.UsersConfig`, and the settings keys `AUTH_USER_MODEL`, `MIGRATION_MODULES`. Enumerate concrete names, not directories.
  - [ ] Add a `guaranteed_settings` key inside the same table listing the settings names that count as guaranteed, so AC #4's "renaming a guaranteed setting" is decidable by the test rather than by argument.
  - [ ] Add the rationale beside the declaration in `accelerator.toml` itself (spine Consistency Conventions: reasoning lives beside the configuration it constrains), stating that everything inside `src/django_service/` not listed here is internal.

- [ ] Task 3 — Gate test: the enumerated surface exists and resolves (AC: #1, #2)
  - [ ] New `tests/unit/test_base_surface.py`. Parse `accelerator.toml` with `tomllib` (mirror the fixture style of `tests/unit/test_dependency_policy.py`).
  - [ ] For every dotted path in `[base_surface]`, import the module with `importlib.import_module` and `getattr` the attribute; a name that does not resolve fails the test. This is what makes "moving a module within the guaranteed surface" a detectable breaking change rather than a convention.
  - [ ] Assert every enumerated path lies inside `django_service.` — the guaranteed surface may not name `config` or a tenant app.
  - [ ] Assert each name in `guaranteed_settings` is present in the imported Django settings.

- [ ] Task 4 — Gate test: presence in all twelve combinations is structural (AC: #2, #6)
  - [ ] In the same test module, assert that every path inside `src/django_service/` carries disposition `core` in `accelerator.toml` and that no `feature:*` disposition applies anywhere under it (AD-29). This is the mechanism by which "present in all twelve" is true: a `core` path travels into every combination, so no separate twelve-way check is needed and none should be invented.
  - [ ] Assert the mapper epoch table's model (Story 2.5, `django_service`-owned) is **not** enumerated in `[base_surface]` — it is internal, and adding it is not an API bump.
  - [ ] Note in the test docstring that Story 7.4 owns the AD-29 disposition assertion; this test asserts the same property from the surface side and the two are allowed to overlap.

- [ ] Task 5 — Gate test: the package name is a constant (AC: #5)
  - [ ] Assert `django_service` appears in no `[parameters]` entry of `accelerator.toml`, and that no parameter's substitution sites include a path under `src/django_service/`. AD-25 states `src/django_service/` is not a parameter; divergence D-1 settled this in the PRD.
  - [ ] Assert `__api_version__` is exactly `int` (`type(...) is int`), not a string, tuple, or `bool`.

- [ ] Task 6 — Full test pass (AC: all)
  - [ ] `pixi run test`, then `pixi run ci`. Every new module and branch must be covered to the 90% floor.

## Dev Notes

### Architecture Constraints

- **AD-5 (binding):** "The package name `django_service` is a constant, never parameterized — reusable apps import from it by that name in every deployment. Moving a module within the guaranteed surface (AD-29), changing `AUTH_USER_MODEL`, or renaming a guaranteed setting is a breaking change. `django_service.__api_version__` is a single integer, bumped by hand on any breaking change and on the removal of any guaranteed surface." *Prevents:* "a reusable app silently breaking on a component whose base moved beneath it; a routine tidy-up inside the base becoming an estate-wide break."
- **AD-29 (binding):** "No `feature:*` disposition may be applied to any path inside `src/django_service/`; it is `core` in its entirety, and a gate test asserts that. … `accelerator.toml` enumerates the guaranteed surface explicitly; anything inside `django_service` not enumerated is internal and may change without a version bump." *Prevents:* "a reusable app importing a module present in six combinations and absent from six, with a combination-invariant version constant that cannot express the difference."
- **AD-1:** the guaranteed surface is declared in `accelerator.toml` "and nowhere else." Do not create a second enumeration in `src/`, in docs, or in a test constant — the test reads the carrier.
- **AD-10:** the epoch record "is internal surface (AD-29), so adding it is not an API version bump."
- **AD-25:** "`src/django_service/` is **not** a parameter (AD-5)."

**Must not do:**
- Do not compute `__api_version__` from anything. It is a hand-edited literal. A derived value cannot express "I did not break anything this release."
- Do not use `try/except ImportError` to make an enumerated name optional (AD-24 forbids it as a removal mechanism, and an optional guaranteed name is a contradiction).
- Do not enumerate by namespace or wildcard. AD-8 forbids namespace enumeration for the contributable surface and the same reasoning applies here: a prefix enumerates whatever happens to exist.
- Do not add a second declaration site for the surface (AD-1).

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/django_service/__init__.py` | UPDATE | 18 lines today: a module docstring plus `__version__` read from distribution metadata via `importlib.metadata.version("django-15-factor-base")` with a `PackageNotFoundError` fallback, and a derived `__version_info__`. **Preserve all of it.** Add `__api_version__: int = 1` plus the bump-rule docstring paragraph and comment. |
| `accelerator.toml` | UPDATE | **Does not exist in the repo today**; created by Story 7.1 at the repository root, disposition `machinery`. Add the `[base_surface]` table (enumerated dotted paths, `guaranteed_settings`) and its rationale comment. |
| `tests/unit/test_base_surface.py` | NEW | The four gate assertions of Tasks 3–5. |

Verified: `src/django_service/__init__.py` exists (18 lines). `src/django_service/` contains `users/`, `contrib/sites/`, `templates/`, `static/`. `AUTH_USER_MODEL = "users.User"` is at `src/config/settings/base.py:138`; `MIGRATION_MODULES` at `:128`. There is no `accelerator.toml`, no `[base_surface]` table, and no `__api_version__` anywhere in the tree today.

### Testing Requirements

- Location: `tests/unit/test_base_surface.py`, mirroring `src/django_service/`. Unit only — parsing TOML and importing modules needs no external resource, so no `@pytest.mark.integration` marker here.
- Disposition (spine Consistency Conventions): this suite covers `core` surface, so it is `core` and is never pruned.
- Assertions the ACs demand:
  - every `[base_surface]` entry imports and resolves (AC #1);
  - every entry is under `django_service.` (AC #1);
  - every path under `src/django_service/` is disposed `core`, none `feature:*` (AC #2);
  - `type(django_service.__api_version__) is int` (AC #3);
  - `guaranteed_settings` names all exist in the imported settings (AC #4);
  - no `[parameters]` entry names `django_service` or a path beneath it (AC #5);
  - the epoch model is absent from `[base_surface]` (AC #6).
- AD-20: the coverage floor is ninety percent including templates, global, with `COVERAGE_CORE=ctrace` in force. `pixi run cov` / `pixi run ci` must exit 0.
- Runner: `pixi run test`, `pixi run cov`, `pixi run ci`. Never bare `pytest`, `pip`, or `uv`.

#### Project Structure Notes

The Structural Seed places `src/django_service/` as "core in its entirety — no feature:* dispositions (AD-29)" and `accelerator.toml` at the root as the machinery catalogue. This story adds no directory; it adds one constant and one carrier table.

Variance from the seed as the repo stands today: `accelerator.toml` does not exist (Story 7.1), `src/config/authorization/`, `src/config/startup/` and `src/django_apps/` do not exist, and `src/django_service/` still contains user-facing UI surface that Story 7.4 moves out. This story must be implemented after Story 7.1 and Story 7.4 land, because the enumeration would otherwise name paths that are about to move — which is exactly the breaking change AC #4 defines.

Python 3.14 only; PEP 8 at 120 columns; full type hints on public signatures; `X | Y` / `list[X]` / `dict[K, V]`; no `print()`; `structlog` only if logging is needed (it is not, here).

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-5]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-10]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-25]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Divergences From the PRD] — D-1, `src/django_service/` is a constant, "not parameterized, and this is load-bearing"
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.1] — `accelerator.toml` is created there
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.4] — AD-29 disposition assertion and the UI-surface move
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.5] — the epoch record lives in a `django_service`-owned table

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
