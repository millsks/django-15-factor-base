# Story 9.4: A reusable app contributes configuration additively on a closed surface

Status: ready-for-dev

## Story

As a lead developer,
I want an adopted application to add configuration and never change it,
so that installing a package cannot give it authority over every request.

## Acceptance Criteria

**Traceability:** FR-54 · AD-8, AD-26

1. **Given** an adopted application
   **When** it ships a contribution
   **Then** it ships a declared contribution module
   **And** the composition step merges contributions from the `component.toml` adopted-application list

2. **Given** a contribution introducing a new key
   **When** composition runs
   **Then** it succeeds

3. **Given** a contribution touching a key the component already defines
   **When** composition runs
   **Then** it raises `ImproperlyConfigured` at startup

4. **Given** a contribution to an ordered sequence such as `INSTALLED_APPS` or `DATABASE_ROUTERS`
   **When** composition runs
   **Then** it appends in adopted-application-list order
   **And** no application can place itself ahead of the base or of another application

5. **Given** the contributable surface
   **When** it is declared
   **Then** it is closed and enumerated in the carrier by explicit key, never by namespace
   **And** it comprises additional `DATABASES` entries and their routers, `INSTALLED_APPS` entries, the application's own namespaced settings, and named non-global DRF and Celery keys

6. **Given** a global-default key
   **When** contribution is attempted
   **Then** `DEFAULT_AUTHENTICATION_CLASSES`, `DEFAULT_PERMISSION_CLASSES`, `MIDDLEWARE` and `AUTHENTICATION_BACKENDS` are each refused
   **And** the refusal holds whether or not the base already sets them

7. **Given** the permitted-key list and the Story 4.6 allowlist
   **When** they are declared
   **Then** they are one declaration

8. **Given** a contribution naming a feature the combination did not select
   **When** settings are imported
   **Then** it is refused
   **And** an application cannot contribute `CELERY_BEAT_SCHEDULE` into a component with no Celery and have its scheduled work silently never run

## Tasks / Subtasks

- [ ] Task 1 — Fix the contribution-module contract (AC: #1)
  - [ ] Document and implement one shape: an adopted application `billing` ships `billing/contribution.py` exposing module-level constants:
    - `CONTRIBUTION: dict[str, object]` — the settings keys it adds;
    - `SEQUENCE_CONTRIBUTION: dict[str, tuple[str, ...]]` — entries to append to ordered sequences, keyed by sequence name (`INSTALLED_APPS`, `DATABASE_ROUTERS`);
    - `REQUIRES_FEATURES: tuple[str, ...]` — feature names the contribution needs, empty tuple if none;
    - `MIN_BASE_API_VERSION: int` / `MAX_BASE_API_VERSION: int` — consumed by Story 9.6, declared here.
  - [ ] The module name is a fixed constant (`contribution`) declared once in `src/config/startup/`, never configurable per app. Discovery is `importlib.import_module(f"{app}.contribution")` over the `component.toml` list — never an entry point, never a scan of `INSTALLED_APPS`, never a package-metadata lookup (AD-8).
  - [ ] An adopted application whose contribution module is missing is an `ImproperlyConfigured`, not a skip. `try/except ImportError` is forbidden (AD-24) and a silently skipped contribution is the failure mode this whole AD exists to prevent.

- [ ] Task 2 — Extend the single permitted-key declaration (AC: #5, #6, #7)
  - [ ] Story 4.6 authored the FR-17 allowlist inside `src/config/startup/` (AD-26: "one module … containing both stages and the FR-17 allowlist"). Extend **that same declaration** with the contributable surface. Do not create a second list, in `accelerator.toml` or anywhere else.
  - [ ] Structure it as one module-level mapping, e.g. `src/config/startup/surface.py`, carrying: `AUTHENTICATION_ALLOWLIST` (Story 4.6's content, unchanged), `CONTRIBUTABLE_KEYS: frozenset[str]`, `CONTRIBUTABLE_SEQUENCES: frozenset[str]`, `REFUSED_GLOBAL_KEYS: frozenset[str]`, and `KEY_FEATURE_OWNER: dict[str, str]` mapping a contributable key to the feature that owns it.
  - [ ] `CONTRIBUTABLE_KEYS` is enumerated **by explicit key**: additional `DATABASES` aliases and their routers, `INSTALLED_APPS` entries, the application's own namespaced settings (prefix `<APP>_` declared per adopted app in `component.toml`, still checked key by key), and the named non-global DRF and Celery keys. Never a namespace, prefix-glob, or regex over key names.
  - [ ] `REFUSED_GLOBAL_KEYS` contains at least `DEFAULT_AUTHENTICATION_CLASSES`, `DEFAULT_PERMISSION_CLASSES`, `MIDDLEWARE`, `AUTHENTICATION_BACKENDS`. The refusal is unconditional — checked before the already-defined check, so it fires whether or not the base sets the key.
  - [ ] **Carrier mirror, not a second list:** `accelerator.toml` (AD-1, AD-8) enumerates the same surface for reconciliation, and a gate test asserts the carrier's enumeration equals the runtime constant exactly — the pattern AD-20 already uses for the coverage `omit` list. The runtime constant is authoritative because `accelerator.toml` never travels and the composition step runs at settings import inside a materialized component that does not have it. Record this reasoning in a comment at both sites.

- [ ] Task 3 — Build the composition step (AC: #1, #2, #3, #4)
  - [ ] New `src/config/settings/composition.py` exposing `apply_contributions(namespace: dict[str, object]) -> None`.
  - [ ] Read the adopted-application list from `component.toml` (Story 5.1) preserving file order — that order *is* the append order.
  - [ ] For each application, in list order: import its contribution module; run the refusal checks below; then apply. Applying means (a) setting each new key in `namespace`, (b) appending each sequence entry to the end of the existing sequence in `namespace`.
  - [ ] Refusal checks, each raising `django.core.exceptions.ImproperlyConfigured` with a message naming the application, the key, and the rule violated:
    - key in `REFUSED_GLOBAL_KEYS` → refuse (AC #6);
    - key not in `CONTRIBUTABLE_KEYS` / sequence not in `CONTRIBUTABLE_SEQUENCES` → refuse (AC #5);
    - key already present in `namespace` → refuse (AC #3);
    - key introduced by an earlier adopted application in this same run → refuse; two applications colliding is the same violation as colliding with the base;
    - any name in `REQUIRES_FEATURES`, or the owning feature of any contributed key per `KEY_FEATURE_OWNER`, not in the component's selected features → refuse (AC #8).
  - [ ] Appending is append-only: build `namespace[seq] = list(namespace[seq]) + list(entries)`. Never insert, sort, reorder, or accept an index/priority field from the contribution. No application can place itself ahead of the base or another application because the API offers no way to express it.
  - [ ] `DATABASE_ROUTERS` may not exist in the namespace yet; treat a missing contributable sequence as an empty list and create it, which is "introducing a new key" and is permitted.

- [ ] Task 4 — Read the component's selected features (AC: #8)
  - [ ] No source document names a mechanism a settings-import-time check can use to learn which features the combination selected: `accelerator.toml` never travels, and `.accelerator.json` is absent from the reference application (AD-17). Resolve it in `component.toml`, which is `core`, always travels, and by AD-28 carries "what a component states about *itself*".
  - [ ] Add a `[features] selected = ["celery", "redis", "ui", "storage"]` array to `component.toml`. The reference application lists all four; the materializer (Epic 8) writes the combination's actual four booleans into each materialized tree.
  - [ ] Add a gate test asserting the reference application's list equals the four feature names declared in `accelerator.toml`, so the two cannot drift.
  - [ ] Do not infer feature presence from `INSTALLED_APPS` membership, from a module being importable, or from `try/except ImportError` (AD-24). Read the declaration.

- [ ] Task 5 — Invoke composition in the settings modules, before stage 1 (AC: #1, #3, #8)
  - [ ] Call `apply_contributions(globals())` as the **penultimate** statement of each settings module that is a `DJANGO_SETTINGS_MODULE` entry point — `src/config/settings/local.py`, `production.py`, `test.py` — immediately before the stage-1 call Story 4.1 placed as the final statement.
  - [ ] Do **not** invoke it in `base.py`. `base.py` is star-imported by the three leaves, so composing there would let a leaf module silently override a contributed key after the collision check had already passed.
  - [ ] Guard against double application with a private sentinel key in the namespace, so a settings module that is loaded twice, or a leaf that inherits a composed namespace, composes once and only once.
  - [ ] Add a gate test asserting every settings module in `src/config/settings/` that sets `ROOT_URLCONF` ends with exactly these two statements in this order — parsed from the AST, not matched as text. This ordering is what makes AD-9's iteration over every configured database reachable at stage 1.

- [ ] Task 6 — Test fixtures: contribution modules that behave (AC: all)
  - [ ] Add fixture applications under `tests/fixtures/tenant_apps/` — a compliant one (`good_app`), one contributing an already-defined key, one contributing `DEFAULT_AUTHENTICATION_CLASSES`, one contributing an unlisted key, one contributing `CELERY_BEAT_SCHEDULE` with `REQUIRES_FEATURES = ("celery",)`, and two compliant ones used to prove append order.
  - [ ] These fixtures cover `core` composition machinery, so they carry the `core` disposition and live under `tests/` — they are **not** tenant applications and must not go in `src/django_apps/` (spine Consistency Conventions: a tenant app's tests live inside the app; these are the base's tests).

- [ ] Task 7 — Tests (AC: all)
  - [ ] `tests/unit/test_composition.py`: new key succeeds (AC #2); already-defined key raises `ImproperlyConfigured` (AC #3); each of the four global-default keys raises, asserted twice — once with the key present in the namespace and once with it absent (AC #6); an unlisted key raises (AC #5); `INSTALLED_APPS` and `DATABASE_ROUTERS` append in `component.toml` order, asserted with two fixture applications in both orders (AC #4); a contribution naming an unselected feature raises at settings import (AC #8); a missing contribution module raises.
  - [ ] `tests/unit/test_contributable_surface.py`: the carrier enumeration equals the runtime constant (AC #7); the allowlist and the contributable surface are one module-level declaration, asserted by identity of the object, not by comparing two copies (AC #7); no entry in `CONTRIBUTABLE_KEYS` is a namespace, prefix pattern or wildcard (AC #5); the four global keys are in `REFUSED_GLOBAL_KEYS` (AC #6).
  - [ ] `tests/integration/test_composition_startup.py` (`@pytest.mark.integration`): load a settings module with an adopted fixture application configured and assert the composed `INSTALLED_APPS` and `DATABASES` reach Django intact, and that stage 1 ran after composition.
  - [ ] `pixi run test`, `pixi run test-integration`, `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-8 (binding, verbatim on the load-bearing clauses):** "An app ships a declared contribution module. The composition step (AD-26) merges contributions from the `component.toml` adopted-app list. Introducing a new key is permitted; touching an existing key raises `ImproperlyConfigured`. Contributions to an **ordered sequence** — `INSTALLED_APPS`, `DATABASE_ROUTERS` — append only, in adopted-app-list order. The contributable surface is closed and enumerated in `accelerator.toml`, **by explicit key, never by namespace** … No global-default key is contributable — `DEFAULT_AUTHENTICATION_CLASSES`, `DEFAULT_PERMISSION_CLASSES`, `MIDDLEWARE`, `AUTHENTICATION_BACKENDS` are refused whether or not the base already sets them, because 'introducing a new key is permitted' would otherwise hand an adopted app authorization over every API request. The permitted-key list and the FR-17 allowlist are **one declaration**, not two lists maintained apart. A contribution naming a feature the combination did not select is refused at settings import … Adoption is explicit — a `pixi.toml` line and a `component.toml` entry. Nothing self-registers; entry-point discovery is forbidden." *Prevents:* "adopting an app being a hand edit repeated in every component; an installed package acquiring visibility of, or authority over, every request."
- **AD-26 (binding):** "**Stage 1** is invoked as the **last statement of every settings module**, which places it after the AD-8 composition step by construction and is why AD-9's iteration over every configured database is reachable. … The FR-17 allowlist and AD-8's permitted-contribution surface are the same declaration, so adding a credential path and adopting an app are checked by one mechanism rather than two that can disagree." *Prevents:* "stage 1 running before composition and never seeing a contributed database; an allowlist maintained apart from the conditions it backstops."
- **AD-3:** "Feature configuration is **subtractive**; reusable-app configuration is **compositional**; the two are not interchangeable." Do not implement a contribution as a feature-owned region or vice versa.
- **AD-28:** the adopted-application list lives in `component.toml`, which is `core` and always travels; `accelerator.toml` carries what only the materializer needs.
- **AD-24:** no conditional imports, no settings-module inheritance, no `try/except ImportError` as a removal or degradation mechanism.
- **Spine Consistency Conventions:** "Every forbidden or missing configuration raises `ImproperlyConfigured` at one of the two refusal stages. A refusal never degrades to a warning (CG-3)."

**Must not do:**
- Do not use `importlib.metadata.entry_points`, `pkg_resources`, or any auto-discovery. An in-repo application has no distribution metadata and the two residency modes would diverge (AD-8, Story 9.5).
- Do not accept a priority, weight, or index field from a contribution. Ordering is the `component.toml` list order and nothing else.
- Do not permit a namespace, prefix, or `fnmatch` pattern in `CONTRIBUTABLE_KEYS`.
- Do not log-and-continue on any refusal. Raise.
- Do not add a second declaration of the permitted keys (AD-1, AD-26).

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/settings/composition.py` | NEW | `apply_contributions(namespace)`, the contribution-module loader, and the five refusal checks. |
| `src/config/startup/surface.py` | UPDATE | **Does not exist today**; `src/config/startup/` is created by Story 4.1 and the FR-17 allowlist by Story 4.6. Extend that same declaration with `CONTRIBUTABLE_KEYS`, `CONTRIBUTABLE_SEQUENCES`, `REFUSED_GLOBAL_KEYS`, `KEY_FEATURE_OWNER`. |
| `src/config/settings/local.py` | UPDATE | 82 lines today; imports `from .base import *` and overrides `DEBUG`, `CACHES`, email and debug-toolbar settings. Add `apply_contributions(globals())` as the penultimate statement, before Story 4.1's stage-1 call. |
| `src/config/settings/production.py` | UPDATE | 160 lines today; `from .base import *` at line 7, the sqlite refusal at lines 26–28 (range verified), Redis `CACHES`, security and logging settings. Same two-statement tail. |
| `src/config/settings/test.py` | UPDATE | 46 lines today. Same two-statement tail. |
| `src/config/settings/base.py` | UPDATE | 381 lines. **No composition call here.** `INSTALLED_APPS` is assembled at line 123 from `DJANGO_APPS` + `THIRD_PARTY_APPS` + `LOCAL_APPS`; `DATABASES` at 55–80; `REST_FRAMEWORK` at ~357–366; `AUTHENTICATION_BACKENDS` at 132–136; `AUTH_USER_MODEL` at 138. Composition appends to the assembled `INSTALLED_APPS`, so no change is needed here unless `DATABASE_ROUTERS` should be declared as an empty list for clarity — permitted, and it must then still accept appends. |
| `component.toml` | UPDATE | **Does not exist today** (Story 5.1). Adds `[features] selected` (Task 4); already carries the adopted-application list. |
| `accelerator.toml` | UPDATE | **Does not exist today** (Story 7.1). Add the mirrored contributable-surface enumeration for two-way reconciliation. |
| `tests/fixtures/tenant_apps/**` | NEW | Seven fixture applications with contribution modules. |
| `tests/unit/test_composition.py` | NEW | Composition behaviour and every refusal. |
| `tests/unit/test_contributable_surface.py` | NEW | One-declaration and closed-enumeration assertions. |
| `tests/integration/test_composition_startup.py` | NEW | Settings-import-time behaviour end to end. |

Verified today: `src/config/settings/` contains `__init__.py`, `base.py`, `local.py`, `production.py`, `test.py`. There is no `composition.py`, no `startup/`, no `component.toml`, no `accelerator.toml`, and no `DATABASE_ROUTERS` anywhere in the tree. `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` currently includes `TokenAuthentication` (Story 2.8 removes it) — the refusal in AC #6 is about the key, not its value, and holds regardless.

### Testing Requirements

- Unit: `tests/unit/test_composition.py`, `tests/unit/test_contributable_surface.py` — no I/O beyond `tmp_path` and TOML reads.
- Integration: `tests/integration/test_composition_startup.py`, every test marked `@pytest.mark.integration`; it loads settings and touches the app registry, so it must restore `sys.modules` and the registry in teardown.
- Fixtures: `tests/fixtures/tenant_apps/` reached via `monkeypatch.syspath_prepend` so the fixture applications import unqualified, exactly as a tenant application does under the Story 9.2 `sources` remapping.
- Every refusal path needs its own test asserting `ImproperlyConfigured` and asserting the message names the application and the key — a refusal whose message does not identify the offender costs an afternoon in a component nobody here maintains.
- Disposition: this suite covers `core` composition machinery, so it is `core` and is never pruned by any feature.
- AD-20 floor: ninety percent including templates, `COVERAGE_CORE=ctrace` in force, global constant, never narrowed. `pixi run ci` must exit 0.
- Runner: `pixi run test`, `pixi run test-integration`, `pixi run cov`, `pixi run ci`.

#### Project Structure Notes

The Structural Seed annotates `src/config/settings/` as "base + local + production + test; composition, then stage 1 last (AD-8, AD-26)". This story is that annotation made real.

Two variances worth stating plainly:

1. **Where the single declaration lives.** AD-26 places the FR-17 allowlist in `src/config/startup/`; AD-1 and AD-8 place the closed contributable surface in `accelerator.toml`. Both cannot be the single authoritative site, because `accelerator.toml` is `machinery` and never travels while the composition step runs at settings import inside a materialized component. This story resolves it the way AD-20 resolves the coverage `omit` list: the runtime constant in `src/config/startup/` is authoritative, the carrier mirrors it, and a gate test asserts equality. Nothing is forked — there is one authored value and one reconciliation.
2. **How selected features are known at settings import.** No AD names a mechanism. `component.toml [features] selected` is added here under AD-28's rule that a fact a component must obey at runtime lives in `component.toml`.

Python 3.14; `dict[str, object]`, `frozenset[str]`, `tuple[str, ...]`; full type hints on `apply_contributions`; Google-style docstrings; no `print()`; `structlog` if anything is logged, though a refusal raises rather than logs.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.4]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-8]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-28]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-3]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20] — the omit-list precedent for a runtime constant reconciled against the carrier
- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.6] — the FR-17 allowlist this story extends
- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.1] — stage 1 as the last statement of every settings module
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.1] — `component.toml` and the adopted-application list
- [Source: _bmad-output/planning-artifacts/epics.md] lines 221 — "FR-17's allowlist and AD-8's contributable surface are **one declaration** — authored in Epic 4, extended in Epic 9, never forked into two lists"

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
