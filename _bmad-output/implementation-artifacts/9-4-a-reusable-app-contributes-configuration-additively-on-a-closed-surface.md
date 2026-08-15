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

4. **Given** a contribution to an ordered sequence such as `INSTALLED_APPS`, `DATABASE_ROUTERS` or the navigation registry
   **When** composition runs
   **Then** it appends in adopted-application-list order
   **And** no application can place itself ahead of the base or of another application

5. **Given** the contributable surface
   **When** it is declared
   **Then** it is closed and enumerated by explicit key, never by namespace
   **And** it comprises additional `DATABASES` entries and their routers, `INSTALLED_APPS` entries, the navigation registry, the application's own namespaced settings, and named non-global DRF and Celery keys

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

9. **Given** a contributed navigation entry
   **When** it is registered
   **Then** it is data and never markup — a label, a URL *name*, and an optional permission the renderer filters on
   **And** every registered URL name must resolve in the URLconf, refused as `ImproperlyConfigured` at stage 2

## Tasks / Subtasks

- [ ] Task 1 — Fix the contribution-module contract (AC: #1)
  - [ ] Document and implement one shape: an adopted application `billing` ships `billing/contribution.py` exposing module-level constants:
    - `CONTRIBUTION: dict[str, object]` — the settings keys it adds;
    - `SEQUENCE_CONTRIBUTION: dict[str, tuple[str, ...]]` — entries to append to ordered sequences, keyed by sequence name (`INSTALLED_APPS`, `DATABASE_ROUTERS`, and the navigation registry);
    - `REQUIRES_FEATURES: tuple[str, ...]` — feature names the contribution needs, drawn from `celery`, `redis`, `storage`, empty tuple if none. There is no `ui` feature: the interface mechanism is `core` and present in every combination (AD-29, revision 3), so an app that extends `base.html`, uses the form styling or contributes navigation declares nothing;
    - `MIN_BASE_API_VERSION: int` / `MAX_BASE_API_VERSION: int` — consumed by Story 9.6, declared here.
  - [ ] A navigation entry is not a bare string, so widen the sequence type to `dict[str, tuple[object, ...]]` and give the registry its own entry type — a frozen dataclass or `NamedTuple` in `django_service` carrying `label: str`, `url_name: str`, `permission: str | None`. It is part of the guaranteed surface (Story 9.1), because an app's contribution module imports it by name. **Data, never markup:** no entry field accepts HTML, a URL *path*, a callable, or a template fragment, and the renderer auto-escapes the label. Reject a raw `str` entry rather than coercing it.
  - [ ] The module name is a fixed constant (`contribution`) declared once in `src/config/startup/`, never configurable per app. Discovery is `importlib.import_module(f"{app}.contribution")` over the `component.toml` list — never an entry point, never a scan of `INSTALLED_APPS`, never a package-metadata lookup (AD-8).
  - [ ] An adopted application whose contribution module is missing is an `ImproperlyConfigured`, not a skip. `try/except ImportError` is forbidden (AD-24) and a silently skipped contribution is the failure mode this whole AD exists to prevent.

- [ ] Task 2 — Extend the single permitted-key declaration (AC: #5, #6, #7)
  - [ ] Story 4.6 authored the FR-17 allowlist inside `src/config/startup/` (AD-26: "one module … containing both stages and the FR-17 allowlist"). Extend **that same declaration** with the contributable surface. Do not create a second list, in `accelerator.toml` or anywhere else.
  - [ ] **Which location is authoritative is settled, not open** (AD-26 and AD-8, revision-2 correction #9): `src/config/startup/` holds the authoritative contributable surface, `accelerator.toml` mirrors it, and a gate test asserts equality. The carrier never travels and therefore cannot be the runtime authority for a rule that executes at settings import inside a materialized component. Implement that; do not re-decide it.
  - [ ] The file is `src/config/startup/allowlist.py` — the module Story 4.6 authored, not a new one. It already carries `ALLOWED_AUTHENTICATION_BACKENDS`, `ALLOWED_DRF_AUTHENTICATION_CLASSES`, `AUTHENTICATION_ROUTE_PREFIXES`, `ALLOWED_AUTHENTICATION_ROUTE_VIEWS`, `CONTRIBUTABLE_KEYS: frozenset[str]` (navigation registry included) and `FORBIDDEN_CONTRIBUTABLE_KEYS: frozenset[str]`. **Leave all six as they are** and add what only the composition step needs: `CONTRIBUTABLE_SEQUENCES: frozenset[str]` and `KEY_FEATURE_OWNER: dict[str, str]` mapping a contributable key to the feature that owns it. Do not rename Story 4.6's constants, and do not add a second module beside it — a `surface.py` next to `allowlist.py` is the fork AC #7 forbids, only shorter.
  - [ ] `CONTRIBUTABLE_KEYS` is enumerated **by explicit key**: additional `DATABASES` aliases and their routers, `INSTALLED_APPS` entries, the application's own namespaced settings (prefix `<APP>_` declared per adopted app in `component.toml`, still checked key by key), the named non-global DRF and Celery keys, and the navigation registry. Never a namespace, prefix-glob, or regex over key names.
  - [ ] `CONTRIBUTABLE_SEQUENCES` carries **three** names: `INSTALLED_APPS`, `DATABASE_ROUTERS`, and the navigation registry. AD-8 permits the registry where `MIDDLEWARE` and `AUTHENTICATION_BACKENDS` are refused, and the reason is the criterion the code must honour: it confers presentation and never authorization, labels are auto-escaped, and no entry carries raw HTML. Story 4.6 already put that reason in a comment beside the `CONTRIBUTABLE_KEYS` entry; do not restate it, cross-reference it — it is the only member of this list rendered on every page, so the next person to widen the list needs to find the reasoning once.
  - [ ] `FORBIDDEN_CONTRIBUTABLE_KEYS` already contains `DEFAULT_AUTHENTICATION_CLASSES`, `DEFAULT_PERMISSION_CLASSES`, `MIDDLEWARE`, `AUTHENTICATION_BACKENDS` (Story 4.6). This story consumes it. The refusal is unconditional — checked before the already-defined check, so it fires whether or not the base sets the key.
  - [ ] **Carrier mirror, not a second list:** `accelerator.toml` (AD-1, AD-8) enumerates the same surface for reconciliation, and a gate test asserts the carrier's enumeration equals the runtime constant exactly — the pattern AD-20 already uses for the coverage `omit` list. The runtime constant in `src/config/startup/` is authoritative because `accelerator.toml` never travels and the composition step runs at settings import inside a materialized component that does not have it. Record this reasoning in a comment at both sites.

- [ ] Task 3 — Build the composition step (AC: #1, #2, #3, #4)
  - [ ] New `src/config/settings/composition.py` exposing `apply_contributions(namespace: dict[str, object]) -> None`.
  - [ ] Read the adopted-application list by calling `load_component_declaration()` from `src/config/component/` (Story 5.1) and taking `ComponentDeclaration.adopted_apps`, a `tuple[str, ...]` in file order — that order *is* the append order, which is why Story 5.1 keeps it a tuple rather than a set. Do not re-parse `component.toml` here; Story 5.1's loader resolves the file without importing Django settings precisely so this story can call it *at* settings import without circularity.
  - [ ] For each application, in list order: import its contribution module; run the refusal checks below; then apply. Applying means (a) setting each new key in `namespace`, (b) appending each sequence entry to the end of the existing sequence in `namespace`.
  - [ ] Refusal checks, each raising `django.core.exceptions.ImproperlyConfigured` with a message naming the application, the key, and the rule violated:
    - key in `FORBIDDEN_CONTRIBUTABLE_KEYS` → refuse (AC #6);
    - key not in `CONTRIBUTABLE_KEYS` / sequence not in `CONTRIBUTABLE_SEQUENCES` → refuse (AC #5);
    - key already present in `namespace` → refuse (AC #3);
    - key introduced by an earlier adopted application in this same run → refuse; two applications colliding is the same violation as colliding with the base;
    - any name in `REQUIRES_FEATURES`, or the owning feature of any contributed key per `KEY_FEATURE_OWNER`, not in the component's selected features → refuse (AC #8).
  - [ ] Appending is append-only: build `namespace[seq] = list(namespace[seq]) + list(entries)`. Never insert, sort, reorder, or accept an index/priority field from the contribution. No application can place itself ahead of the base or another application because the API offers no way to express it. The navigation registry is an ordered sequence on exactly these terms — append-only, in adopted-app-list order, "exactly like `INSTALLED_APPS`" (AD-8).
  - [ ] `DATABASE_ROUTERS` may not exist in the namespace yet; treat a missing contributable sequence as an empty list and create it, which is "introducing a new key" and is permitted. The navigation registry does exist already — `django_service` owns it and the base's own entries occupy it before any app contributes — so contributions append behind them and the base's navigation can never be displaced.
  - [ ] Reject a navigation entry that is not the declared entry type, and reject one whose `label`, `url_name` or `permission` is not a plain string (or `None` for the permission). URL-name *resolution* is not checked here: at settings import there is no resolved URLconf. That check is stage 2, Task 5a.

- [ ] Task 4 — Read the component's selected features (AC: #8)
  - [ ] **The mechanism is named and settled** (AD-8 and AD-28, revision-2 correction #10): the selected-feature list lives in `component.toml`, "the only declaration present at settings import in both the reference application and a materialized component." `accelerator.toml` cannot serve — it is `machinery` and does not travel. `.accelerator.json` cannot serve either — AD-17 states the reference application carries no stamp, so a mechanism reading it would work in materialized components and fail in the tree that has to gate it. Read `component.toml`; do not invent an alternative.
  - [ ] `component.toml` is created by **Story 5.1**, and AD-28 enumerates the selected-feature list among its contents. This story *reads* that list; it does not introduce the file or the key. If Story 5.1 has not landed, the key belongs there, not here.
  - [ ] **Consume Story 5.1's shape; do not invent a second one.** The key is top-level `selected_features` — not a `[features]` table — and reaches this story as `ComponentDeclaration.selected_features: frozenset[str]` from `load_component_declaration()`. A set is the right type because every consumer here asks membership. Story 5.1's loader already refuses an unknown feature name against the closed set `{"celery", "redis", "storage"}` and refuses `celery` without `redis` (FR-26's broker constraint), so this story does neither: it asks membership of an already-validated set. Re-validating here would create a second authority for a rule AD-28 places in one.
  - [ ] The list carries **three** feature names — `celery`, `redis`, `storage`. There is no `ui`: revision 3 makes the interface mechanism `core`. The reference application selects all three; the materializer (Epic 8) writes each combination's actual selection into its materialized tree, across the six valid combinations. An absent `selected_features` is the empty set — the *Minimal* preset — and is a valid combination rather than a missing declaration, so composition must handle it without special-casing.
  - [ ] Add a gate test asserting the reference application's list equals the three feature names declared in `accelerator.toml`, so the two cannot drift.
  - [ ] Do not infer feature presence from `INSTALLED_APPS` membership, from a module being importable, or from `try/except ImportError` (AD-24). Read the declaration.

- [ ] Task 5 — Invoke composition in the leaf settings modules, before stage 1 (AC: #1, #3, #8)
  - [ ] Call `apply_contributions(globals())` as the **penultimate** statement of each **leaf** settings module — `src/config/settings/local.py`, `production.py`, `test.py` — immediately before the stage-1 call Story 4.1 placed as the final statement.
  - [ ] Do **not** invoke it in `base.py`, and note that AD-26 says the same of the stage-1 call itself: stage 1 is the last statement of every *leaf*, and **`base.py` must not call it**. `base.py` is star-imported by the three leaves, so composing or refusing there fires before the leaf composes — it would let a leaf module silently override a contributed key after the collision check had already passed, and it would destroy the after-composition property AD-9's per-database iteration depends on.
  - [ ] Guard against double application with a private sentinel key in the namespace, so a settings module that is loaded twice, or a leaf that inherits a composed namespace, composes once and only once.
  - [ ] Add a gate test asserting each of the three leaf settings modules ends with exactly these two statements in this order, and that `base.py` contains **neither** call — parsed from the AST, not matched as text. Do **not** select the modules by "sets `ROOT_URLCONF`": `ROOT_URLCONF` is set at `src/config/settings/base.py:87` and nowhere else, so that predicate selects exactly the one module which must not carry either call. Enumerate the three leaves by name. This ordering is what makes AD-9's iteration over every configured database reachable at stage 1, and it is the paired assertion AD-26 requires.

- [ ] Task 5a — Stage 2: every registered navigation URL name resolves (AC: #9)
  - [ ] In `src/config/startup/stage_two.py` (Story 4.3), iterate the composed navigation registry and `django.urls.reverse` — or `get_resolver().reverse_dict` — each entry's URL name. A name that does not resolve raises `ImproperlyConfigured` naming the contributing application, the label and the URL name.
  - [ ] **This refusal is Epic 9's, and Story 4.6 drew the boundary explicitly**: Story 4.6 declares the navigation registry as a key on the closed contributable surface, and Epic 9 enforces the *content* of what is contributed — the same boundary Story 4.6 already draws for the rest of `CONTRIBUTABLE_KEYS`. Append it to the fixed-order tuple Story 4.3 established in that module; do not open a second stage-2 entry point for it, because "one location, one owner, a fixed order" (AD-26) has to hold for a refusal a different epic contributes.
  - [ ] **It is not a tenth refusal condition.** The settled count of **nine conditions across fourteen forbidden states** (`epics.md:310-328`) is unchanged by this story, and Story 4.5's audit must still assert exactly fourteen. This check validates a *contributed setting* — its shape is Story 9.6's adoption-time gate, not a forbidden state of the component's own configuration, which is what Stories 4.2–4.4 enumerate. Record that in the condition's docstring so the next reader does not reconcile the tuple's length against the table and conclude one of them is wrong.
  - [ ] Stage 2 is the correct stage and the only correct stage: it is the one with a resolved URLconf (AD-26). An app that contributes a link to a route it forgot to mount then fails at startup rather than rendering a 500 on whatever page carries the navigation bar.
  - [ ] Resolve objects, not strings (AD-26): reverse the name through Django's resolver; never string-match the URLconf source or the registry's own entries.
  - [ ] This is a refusal, so Story 4.5's rule applies — it is tested as a refusal, with a fixture app contributing an unmounted URL name.

- [ ] Task 6 — Test fixtures: contribution modules that behave (AC: all)
  - [ ] Add fixture applications under `tests/fixtures/tenant_apps/` — a compliant one (`good_app`), one contributing an already-defined key, one contributing `DEFAULT_AUTHENTICATION_CLASSES`, one contributing an unlisted key, one contributing `CELERY_BEAT_SCHEDULE` with `REQUIRES_FEATURES = ("celery",)`, and two compliant ones used to prove append order.
  - [ ] Add three more for the navigation registry: one contributing a well-formed entry against a route it mounts, one contributing an entry whose URL name is not mounted anywhere (the AC #9 stage-2 refusal), and one attempting an entry carrying markup or a raw string instead of the entry type (the settings-import refusal in Task 3). The well-formed one doubles as the AC #4 append-order fixture for the registry.
  - [ ] `good_app` should be a realistic tenant app under revision 3 — its own template extending `base.html`, a crispy-styled form, a view, a mounted URL, and one navigation entry pointing at it. That is what an adopted app now looks like, and a fixture that contributes only settings keys would not exercise the surface the guaranteed contract promises.
  - [ ] These fixtures cover `core` composition machinery, so they carry the `core` disposition and live under `tests/` — they are **not** tenant applications and must not go in `src/django_apps/` (spine Consistency Conventions: a tenant app's tests live inside the app; these are the base's tests).

- [ ] Task 7 — Tests (AC: all)
  - [ ] `tests/unit/test_composition.py`: new key succeeds (AC #2); already-defined key raises `ImproperlyConfigured` (AC #3); each of the four global-default keys raises, asserted twice — once with the key present in the namespace and once with it absent (AC #6); an unlisted key raises (AC #5); `INSTALLED_APPS` and `DATABASE_ROUTERS` append in `component.toml` order, asserted with two fixture applications in both orders (AC #4); a contribution naming an unselected feature raises at settings import (AC #8); a missing contribution module raises.
  - [ ] `tests/unit/test_contributable_surface.py`: the carrier enumeration equals the runtime constant, with `src/config/startup/` authoritative (AC #7); the allowlist and the contributable surface are one module-level declaration, asserted by identity of the object, not by comparing two copies (AC #7); no entry in `CONTRIBUTABLE_KEYS` is a namespace, prefix pattern or wildcard (AC #5); the four global keys are in `FORBIDDEN_CONTRIBUTABLE_KEYS`, and the navigation registry is in both `CONTRIBUTABLE_KEYS` and `CONTRIBUTABLE_SEQUENCES` while `MIDDLEWARE` and `AUTHENTICATION_BACKENDS` are in neither (AC #5, #6). Story 4.6's own `tests/unit/config/startup/test_allowlist_declaration.py` already asserts disjointness and the no-namespace rule for the constants it authored; extend that module rather than restating its assertions here.
  - [ ] `tests/unit/test_composition.py`, navigation cases: a well-formed entry appends behind the base's own entries and behind an earlier app's, in `component.toml` order (AC #4); a raw string, a dict, or an entry with a markup-bearing label is refused at settings import (AC #9); the registry is never reordered or deduplicated.
  - [ ] `tests/integration/test_composition_startup.py` (`@pytest.mark.integration`): load a settings module with an adopted fixture application configured and assert the composed `INSTALLED_APPS` and `DATABASES` reach Django intact, and that stage 1 ran after composition. Add the AC #9 pair: with the well-formed navigation fixture adopted, stage 2 passes and the rendered navigation bar contains the contributed label escaped; with the unmounted-URL fixture adopted, stage 2 raises `ImproperlyConfigured` naming the app and the URL name.
  - [ ] `pixi run test`, `pixi run test-integration`, `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-8 (binding, verbatim on the load-bearing clauses):** "An app ships a declared contribution module. The composition step (AD-26) merges contributions from the `component.toml` adopted-app list. Introducing a new key is permitted; touching an existing key raises `ImproperlyConfigured`. Contributions to an **ordered sequence** — `INSTALLED_APPS`, `DATABASE_ROUTERS` — append only, in adopted-app-list order. The contributable surface is closed and enumerated **by explicit key, never by namespace** … Its authoritative location is `src/config/startup/`, mirrored into `accelerator.toml` and reconciled by a gate test (AD-26) … No global-default key is contributable — `DEFAULT_AUTHENTICATION_CLASSES`, `DEFAULT_PERMISSION_CLASSES`, `MIDDLEWARE`, `AUTHENTICATION_BACKENDS` are refused whether or not the base already sets them, because 'introducing a new key is permitted' would otherwise hand an adopted app authorization over every API request. The permitted-key list and the FR-17 allowlist are **one declaration**, not two lists maintained apart. A contribution naming a feature the combination did not select is refused at settings import … **The selected-feature list is read from `component.toml` (AD-28)** — the only declaration present at settings import in both the reference application and a materialized component. Adoption is explicit — a `pixi.toml` line and a `component.toml` entry. Nothing self-registers; entry-point discovery is forbidden." *Prevents:* "adopting an app being a hand edit repeated in every component; an installed package acquiring visibility of, or authority over, every request."
- **AD-8, the navigation clause (binding, and new in this revision's reading):** "**Navigation is a contributed ordered sequence, and it is on the surface.** `django_service` owns a navigation registry, contributed to exactly like `INSTALLED_APPS` — append only, in adopted-app-list order. An entry is **data, never markup**: a label, a URL *name*, and an optional permission the renderer filters on. This is the one contributable key rendered on every page, so it is permitted where `MIDDLEWARE` and `AUTHENTICATION_BACKENDS` are refused for a reason that holds here: it confers presentation and never authorization, labels are auto-escaped, and no entry carries raw HTML. Every registered URL name must resolve in the URLconf, refused as `ImproperlyConfigured` at stage 2 — the stage that has a resolved URLconf (AD-26). An app that contributes a link to a route it forgot to mount fails at startup rather than rendering a 500 on whatever page carries the navigation bar."
  **This reverses revision 2.** Revision 2 held that an adopted app could not contribute navigation entries; revision 3 holds that it can, and that this is the registry's purpose. With the interface mechanism `core` (AD-29), an adopted app with its own templates, forms and views relies on it freely — it extends `base.html`, uses the crispy form styling, and contributes its own navigation entries. An app that requires a *remaining* feature — `celery`, `redis`, `storage` — names it in `REQUIRES_FEATURES` and AD-8's refusal rejects it at settings import wherever that feature is unselected.
- **AD-26 (binding):** "**Stage 1** is invoked as the **last statement of every leaf settings module** — `local.py`, `production.py`, `test.py` — which places it after the AD-8 composition step by construction and is why AD-9's iteration over every configured database is reachable. **`base.py` must not call it**, and a gate test asserts both halves … The FR-17 allowlist and AD-8's permitted-contribution surface are the same declaration … **`src/config/startup/` holds the authoritative copy and `accelerator.toml` mirrors it**, with a gate test asserting equality." *Prevents:* "stage 1 running before composition and never seeing a contributed database; an allowlist maintained apart from the conditions it backstops." The leaf/`base.py` distinction is load-bearing rather than pedantic: `base.py` is star-imported, so a call at its end fires before the leaf composes.
- **AD-3:** "Feature configuration is **subtractive**; reusable-app configuration is **compositional**; the two are not interchangeable." Do not implement a contribution as a feature-owned region or vice versa.
- **AD-28:** the adopted-application list **and the selected-feature list** both live in `component.toml`, which is `core` and always travels; `accelerator.toml` carries what only the materializer needs. AD-28 enumerates the selected-feature list explicitly — "which AD-8's settings-import refusal reads, and which nothing else in a materialized component can supply." Story 5.1 creates the file, declares both as **top-level keys** (`adopted_apps`, `selected_features`), and builds the loader at `src/config/component/` that returns them as `tuple[str, ...]` and `frozenset[str]`. This story is the settings-import refusal AD-8 names, and Story 5.1 wrote its loader to resolve `component.toml` without importing Django settings for exactly that reason.
- **AD-29 (revision 3):** the interface mechanism is `core` in every combination, so there is no `ui` feature and no `ui` value in `REQUIRES_FEATURES`. Three features remain — `celery`, `redis`, `storage` — across six valid combinations.
- **AD-24:** no conditional imports, no settings-module inheritance, no `try/except ImportError` as a removal or degradation mechanism.
- **Spine Consistency Conventions:** "Every forbidden or missing configuration raises `ImproperlyConfigured` at one of the two refusal stages. A refusal never degrades to a warning (CG-3)."

**Must not do:**
- Do not use `importlib.metadata.entry_points`, `pkg_resources`, or any auto-discovery. An in-repo application has no distribution metadata and the two residency modes would diverge (AD-8, Story 9.5).
- Do not accept a priority, weight, or index field from a contribution. Ordering is the `component.toml` list order and nothing else.
- Do not permit a namespace, prefix, or `fnmatch` pattern in `CONTRIBUTABLE_KEYS`.
- Do not log-and-continue on any refusal. Raise.
- Do not add a second declaration of the permitted keys (AD-1, AD-26).
- Do not let a navigation entry carry markup, a raw URL path, a callable, a template name, or an ordering hint. Label, URL name, optional permission — and nothing else.
- Do not check URL-name resolution at settings import. There is no resolved URLconf there; the check is stage 2 and only stage 2.
- Do not add `ui` to `REQUIRES_FEATURES`, to `component.toml`'s selected-feature list, or to `KEY_FEATURE_OWNER`. It is not a feature.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/settings/composition.py` | NEW | `apply_contributions(namespace)`, the contribution-module loader, and the five refusal checks. |
| `src/config/startup/allowlist.py` | UPDATE | **Does not exist today**; `src/config/startup/` is skeletoned by Story 4.1 and this module authored by Story 4.6, which already declares `CONTRIBUTABLE_KEYS` (navigation registry included) and `FORBIDDEN_CONTRIBUTABLE_KEYS`. **Change:** add `CONTRIBUTABLE_SEQUENCES` and `KEY_FEATURE_OWNER` only. **Preserve:** every constant Story 4.6 authored, under its own name. This is the **authoritative** copy of the contributable surface (AD-26); `accelerator.toml` mirrors it. No second module. |
| `src/config/startup/stage_two.py` | UPDATE | Created by Story 4.1, filled by Story 4.3 with four conditions and the fixed-order tuple. Add the AC #9 refusal — every registered navigation URL name resolves in the URLconf, or `ImproperlyConfigured` — and append it to that tuple. It is not a tenth condition and does not change the nine/fourteen count. |
| `src/config/component/` | READ ONLY (import) | Created by Story 5.1. `load_component_declaration()` supplies `adopted_apps` and `selected_features`; do not re-parse `component.toml`. |
| `src/django_service/` navigation registry | UPDATE | Created by Story 7.4 together with `_navbar.html`. This story adds the contribution path into it and the entry type an app's contribution module imports; it does not create the registry or the template. |
| `src/config/settings/local.py` | UPDATE | 82 lines today; imports `from .base import *` and overrides `DEBUG`, `CACHES`, email and debug-toolbar settings. Add `apply_contributions(globals())` as the penultimate statement, before Story 4.1's stage-1 call. |
| `src/config/settings/production.py` | UPDATE | 160 lines today; `from .base import *` at line 7, the sqlite refusal at lines 26–28 (range verified), Redis `CACHES`, security and logging settings. Same two-statement tail. |
| `src/config/settings/test.py` | UPDATE | 46 lines today. Same two-statement tail. |
| `src/config/settings/base.py` | UPDATE | 381 lines. **No composition call here, and no stage-1 call either** (AD-26). `INSTALLED_APPS` is assembled at line 123 from `DJANGO_APPS` + `THIRD_PARTY_APPS` + `LOCAL_APPS`; `DATABASES` at 55–80; `ROOT_URLCONF` at 87; `AUTHENTICATION_BACKENDS` at 133–136; `AUTH_USER_MODEL` at 138; `REST_FRAMEWORK` at 357–364. Composition appends to the assembled `INSTALLED_APPS`, so no change is needed here unless `DATABASE_ROUTERS` should be declared as an empty list for clarity — permitted, and it must then still accept appends. |
| `component.toml` | READ ONLY | **Does not exist today**; created by **Story 5.1**, which declares top-level `adopted_apps` and top-level `selected_features` (AD-28) — not a `[features]` table. This story reads both through Story 5.1's loader; it introduces neither and adds no key. |
| `accelerator.toml` | UPDATE | **Does not exist today** (Story 7.1). Add the mirrored contributable-surface enumeration for two-way reconciliation. |
| `tests/fixtures/tenant_apps/**` | NEW | Ten fixture applications with contribution modules — the seven configuration cases plus the three navigation cases of Task 6. |
| `tests/unit/test_composition.py` | NEW | Composition behaviour and every refusal. |
| `tests/unit/test_contributable_surface.py` | NEW | One-declaration and closed-enumeration assertions. |
| `tests/integration/test_composition_startup.py` | NEW | Settings-import-time behaviour end to end. |

Verified today: `src/config/settings/` contains `__init__.py`, `base.py`, `local.py`, `production.py`, `test.py`. There is no `composition.py`, no `startup/`, no `component.toml`, no `accelerator.toml`, and no `DATABASE_ROUTERS` anywhere in the tree. `ROOT_URLCONF` appears exactly once, at `base.py:87` — which is why Task 5's gate test enumerates the three leaves by name instead of selecting on it. `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` currently includes `TokenAuthentication` (Story 2.8 removes it) — the refusal in AC #6 is about the key, not its value, and holds regardless. There is no navigation registry and no `_navbar.html` yet; `src/django_service/templates/base.html` exists and still carries hardcoded navigation, which Story 7.4 replaces.

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

Two questions this story used to have to answer are now answered in the spine, and are cited rather than re-decided:

1. **Where the single declaration lives — settled by AD-26 and AD-8.** `src/config/startup/` holds the authoritative contributable surface; `accelerator.toml` mirrors it; a gate test asserts equality, the way AD-20 already does for the coverage `omit` list. The reason is stated there: the carrier is `machinery`, never travels, and cannot be the runtime authority for a rule that executes at settings import inside a materialized component. Nothing is forked — one authored value, one reconciliation.
2. **How selected features are known at settings import — settled by AD-28 and AD-8.** The selected-feature list lives in `component.toml`, the only declaration present at settings import in both the reference application and a materialized component. It is created by Story 5.1, and this story reads it. `accelerator.toml` cannot serve (it does not travel) and `.accelerator.json` cannot serve (AD-17: the reference application carries no stamp).

One genuinely new obligation arrives with revision 3: **the navigation registry is a contributable ordered sequence**, and the check that every registered URL name resolves is a stage-2 refusal (AC #9). It is stage 2 rather than stage 1 for a structural reason, not a convenient one — stage 2 is the stage with a resolved URLconf (AD-26).

Its ownership is settled between the epics rather than open. Story 4.6 declares the registry as a key on the closed contributable surface and stops there; Story 4.3 records the forward reference and leaves the tuple slot; this story enforces the contributed content. That is the same boundary Story 4.6 draws for the rest of `CONTRIBUTABLE_KEYS` — Epic 4 declares, Epic 9 enforces — and it means the mechanism is inherited, not rebuilt: the condition executes in `src/config/startup/stage_two.py` and this story appends it to Story 4.3's fixed-order tuple. It does **not** enter the settled table of nine conditions and fourteen forbidden states, because it validates a contributed setting in the shape of Story 9.6's adoption-time gate rather than a forbidden state of the component's own configuration. Story 4.5's audit still asserts exactly fourteen.

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
- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.1] — stage 1 as the last statement of every *leaf* settings module, and `base.py` calling neither stage
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29] — the interface mechanism is `core`; the guaranteed surface is the contract for tenant apps
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Revision 3 — the interface mechanism becomes core] — three features, six combinations; the navigation registry retained
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.1] — `component.toml`, the adopted-application list, and the selected-feature list
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.4] — the navigation registry and `_navbar.html` this story contributes into
- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.3] — the stage-2 module and the fixed-order tuple the AC #9 refusal joins; its Project Structure Notes record the forward reference and that it is not a tenth condition
- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.5] — the audit that must still assert exactly fourteen forbidden states
- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.1] — the guaranteed surface the navigation entry type belongs to
- [Source: _bmad-output/planning-artifacts/epics.md] lines 221 — "FR-17's allowlist and AD-8's contributable surface are **one declaration** — authored in Epic 4, extended in Epic 9, never forked into two lists"

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
