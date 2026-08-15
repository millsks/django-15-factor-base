# Story 4.6: The authentication surface matches an allowlist exactly

Status: ready-for-dev

## Story

As a platform engineer,
I want the component's authentication surface asserted against an approved list,
so that a credential path invented after this PRD fails the build until someone adds it deliberately.

## Acceptance Criteria

**Traceability:** FR-17 · AD-8, AD-26 · SC-5

1. **Given** `AUTHENTICATION_BACKENDS` and the DRF default authentication classes
   **When** the allowlist test runs
   **Then** each matches the approved allowlist exactly
   **And** an entry present but not listed fails the test

2. **Given** resolved URL routes
   **When** they are checked
   **Then** only the route prefixes the component itself owns for authentication, admin login and token issuance are in scope
   **And** business routes a developer adds are out of its scope

3. **Given** a developer adding a credential path
   **When** the change is made
   **Then** the allowlist must be edited in the same change
   **And** that edit is the moment a human decides whether the path belongs

4. **Given** the allowlist and the contributable-configuration surface Epic 9 will need
   **When** they are declared
   **Then** they are one declaration
   **And** never two lists maintained apart

## Tasks / Subtasks

- [ ] Task 1 — Author the single declaration in `src/config/startup/allowlist.py` (AC: #1, #4)
  - [ ] `src/config/startup/allowlist.py` is created as an empty skeleton by Story 4.1. Fill it with **one** module-level declaration object covering both FR-17's allowlist and AD-8's permitted-contribution surface. One frozen dataclass or one module of frozen constants — not two parallel structures in one file, which is the same fork with a shorter distance.
  - [ ] `ALLOWED_AUTHENTICATION_BACKENDS: frozenset[str]` — the exact set of dotted paths permitted in `AUTHENTICATION_BACKENDS`. After Epic 2, that is allauth's authentication backend and nothing else; `django.contrib.auth.backends.ModelBackend` is forbidden by Story 4.2's condition 2a and must **not** appear here.
  - [ ] `ALLOWED_DRF_AUTHENTICATION_CLASSES: frozenset[str]` — the exact set permitted in `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`. After Epic 2, that is `SessionAuthentication` and the Bearer authentication class Story 2.7 builds; `rest_framework.authentication.TokenAuthentication` must **not** appear here.
  - [ ] `AUTHENTICATION_ROUTE_PREFIXES: tuple[str, ...]` — the route prefixes the component itself owns for authentication, admin login and token issuance. This is the **scoping** declaration of AC #2, not a predicate: it says which routes the allowlist has authority over, and business routes outside it are out of scope.
  - [ ] `ALLOWED_AUTHENTICATION_ROUTE_VIEWS` — for each in-scope prefix, the set of view callables permitted there, declared as importable references resolved to objects at test time (see Task 3).
  - [ ] `CONTRIBUTABLE_KEYS: frozenset[str]` — AD-8's closed permitted-key surface, **by explicit key, never by namespace**: additional `DATABASES` entries and their routers, `INSTALLED_APPS` entries, an app's own namespaced settings, and named non-global DRF and Celery keys.
  - [ ] `FORBIDDEN_CONTRIBUTABLE_KEYS: frozenset[str]` — the global-default keys refused whether or not the base already sets them: `DEFAULT_AUTHENTICATION_CLASSES`, `DEFAULT_PERMISSION_CLASSES`, `MIDDLEWARE`, `AUTHENTICATION_BACKENDS`.
  - [ ] Add a module docstring stating, in one paragraph, that these are **one declaration**: adding a credential path and adopting an app are checked by one mechanism rather than two that can disagree, and this file moves into `accelerator.toml` in Epic 7 and is extended (never forked) in Epic 9.
  - [ ] Add a structural test asserting `ALLOWED_AUTHENTICATION_BACKENDS ∪ ALLOWED_DRF_AUTHENTICATION_CLASSES` is disjoint from `FORBIDDEN_CONTRIBUTABLE_KEYS`'s corresponding entries — the mechanical proof that the two halves cannot drift into contradiction.

- [ ] Task 2 — The settings-side allowlist test (AC: #1, #3)
  - [ ] `tests/unit/config/startup/test_authentication_allowlist.py`.
  - [ ] Assert `set(settings.AUTHENTICATION_BACKENDS) == ALLOWED_AUTHENTICATION_BACKENDS` — **exact equality, not a subset test**. An entry present but not listed fails; an entry listed but absent also fails, which is what makes the allowlist a statement about the surface rather than a floor.
  - [ ] Assert `set(settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]) == ALLOWED_DRF_AUTHENTICATION_CLASSES` on the same terms.
  - [ ] The failure message must name the unexpected entry and state the AC #3 remedy in words: adding a credential path requires editing `src/config/startup/allowlist.py` in the same change, and that edit is the moment a human decides whether the path belongs.
  - [ ] Add the AC #3 test itself: monkeypatch an extra backend into the settings namespace and assert the allowlist test fails. Without it, "the allowlist must be edited in the same change" is a claim rather than a mechanism.

- [ ] Task 3 — The route-side allowlist test, resolving objects (AC: #1, #2)
  - [ ] Reuse `_iter_view_callables` from `src/config/startup/stage_two.py` (Story 4.3) — one walker, not two. It yields unwrapped view callables from the resolved URLconf.
  - [ ] Scope: consider only routes whose resolved path falls under one of `AUTHENTICATION_ROUTE_PREFIXES`. Business routes a developer adds are out of scope (AC #2) — an allowlist covering every route "would break the build on the first feature anyone wrote, and would be deleted within a week."
  - [ ] Within scope, assert each route's **view callable** is in `ALLOWED_AUTHENTICATION_ROUTE_VIEWS` for that prefix. Compare resolved objects by identity or by `issubclass` on the view class, never by route name or dotted-path string.
  - [ ] **The prefix scoping is not the predicate, and the distinction is the whole point.** `src/config/urls.py:24` mounts `allauth.urls` under `accounts/`, so `/accounts/` is necessarily an in-scope prefix. AD-21 states the consequence: "a route named `local_persona_login` mounted under `/accounts/` would otherwise satisfy this AD and pass an allowlist that already permits `/accounts/` for allauth." The prefix decides *whether the allowlist looks*; the view callable decides *whether it passes*. Any implementation that allowlists a prefix and stops looking is wrong.
  - [ ] Cross-check with Story 4.3: a route whose callable belongs to the local sign-in module is refused by stage 2 in a deployed component **and** is absent from `ALLOWED_AUTHENTICATION_ROUTE_VIEWS`. Two independent mechanisms, one declaration; do not make one call the other.
  - [ ] Add the evasion test: a route named `local_persona_login` mounted at `accounts/local-sign-in/` whose callable belongs to the local sign-in module fails the allowlist test. Add its mirror: a route named something innocuous mounted at `api/token/` whose callable is `obtain_auth_token` also fails.

- [ ] Task 4 — Record the AD-8 half without building Epic 9's mechanism (AC: #4)
  - [ ] Declare `CONTRIBUTABLE_KEYS` and `FORBIDDEN_CONTRIBUTABLE_KEYS` in the same file. Epic 9 Story 9.4 builds the composition step that enforces them; this story authors the declaration only.
  - [ ] Add a test asserting `CONTRIBUTABLE_KEYS` and `FORBIDDEN_CONTRIBUTABLE_KEYS` are disjoint, and that no entry of `CONTRIBUTABLE_KEYS` is a namespace prefix rather than an explicit key — AD-8 requires "by explicit key, never by namespace."
  - [ ] Do **not** implement the contribution-merge behaviour, the `component.toml` adopted-app list, or the `ImproperlyConfigured` on touching an existing key. Those are Epic 9. Enforcing them here would mean building against a `component.toml` that does not exist.
  - [ ] Mark the enforcement half in Dev Notes as a **traceability marker, not an acceptance condition for this story**.

- [ ] Task 5 — Tests (AC: all)
  - [ ] `tests/unit/config/startup/test_authentication_allowlist.py` — Tasks 2 and 3, plus both evasion tests, plus the AC #3 mechanism test.
  - [ ] `tests/unit/config/startup/test_allowlist_declaration.py` — Task 1's structural assertions and Task 4's disjointness and explicit-key assertions.
  - [ ] Add a scope test: a business route added outside every `AUTHENTICATION_ROUTE_PREFIXES` entry does **not** fail the allowlist test. Without it the scoping is untested and the first feature anyone writes breaks the build.
  - [ ] Add a one-declaration test: assert `src/config/startup/allowlist.py` is the only module under `src/` defining any of these names, by importing and comparing object identity across `src/config/` — a mechanical stand-in for AD-1 until Epic 7's two-way reconciliation exists.

## Dev Notes

### Architecture Constraints

- **AD-26 (binding clause):** "The FR-17 allowlist and AD-8's permitted-contribution surface are the same declaration, so adding a credential path and adopting an app are checked by one mechanism rather than two that can disagree." Also: "The refusal contract is one module, `src/config/startup/`, containing both stages **and the FR-17 allowlist**."
  **Prevents:** "an allowlist maintained apart from the conditions it backstops."
- **AD-8 (binding rule):** "The contributable surface is closed and enumerated in `accelerator.toml`, **by explicit key, never by namespace**: additional `DATABASES` entries and their routers, `INSTALLED_APPS` entries, the app's own namespaced settings, and named non-global DRF and Celery keys. No global-default key is contributable — `DEFAULT_AUTHENTICATION_CLASSES`, `DEFAULT_PERMISSION_CLASSES`, `MIDDLEWARE`, `AUTHENTICATION_BACKENDS` are refused whether or not the base already sets them, because 'introducing a new key is permitted' would otherwise hand an adopted app authorization over every API request. The permitted-key list and the FR-17 allowlist are **one declaration**, not two lists maintained apart."
  **Prevents:** "adopting an app being a hand edit repeated in every component; an installed package acquiring visibility of, or authority over, every request."
- **AD-21 (the evasion this story must block):** "a route named `local_persona_login` mounted under `/accounts/` would otherwise satisfy this AD and pass an allowlist that already permits `/accounts/` for allauth."
- **AD-16:** "No network surface exists beneath Django's routing … Any future protocol handled below Django's URL resolver is a designed feature with its own authentication story and its own entry in the carrier, never an inherited handler."
  **Prevents:** "a credential or network surface that the route allowlist cannot see because it is not a route." Epic 1 Story 1.4 deletes `src/config/websocket.py`, the scope-dispatching wrapper and its `[tool.coverage.run] omit` entry together — that deletion is a **precondition for this allowlist to be complete rather than merely present**, and it is Epic 1's work, not this story's.
- **AD-1:** every declaration has exactly one site. `accelerator.toml` is authored in Epic 7 and this declaration moves there then, "without changing any assertion's meaning."
- **FR-17's own reasoning:** "the nine refusal conditions are a denylist … and a denylist cannot by construction catch a path invented next year. This FR inverts that, which is the difference between FR-16 being a guarantee and being a habit."
- **CG-3:** an allowlist violation fails the test; it never warns.
- **AD-24 forbids** conditional imports and `try/except ImportError` in the declaration module. Every reference resolves unconditionally.

### The cross-epic thread this story sits on

`epics.md:221`: "FR-17's allowlist and AD-8's contributable surface are **one declaration** — authored in Epic 4, extended in Epic 9, never forked into two lists." Authored here. Moved into `accelerator.toml` in Epic 7 (epics.md:225 names three such declarations; this one arrives via AD-1 and AD-8's own text, which already places the contributable surface in `accelerator.toml`). Extended in Epic 9 when adopted apps exist. **At no point does a second list appear.**

The nine refusal conditions this allowlist backstops are the settled fourteen forbidden states of `epics.md:308-326` — seven unconditional conditions and two conditional, implemented in Stories 4.2, 4.3 and 4.4. The allowlist's job is the inverse: the conditions refuse known-bad states; the allowlist fails the build on any authentication surface not explicitly approved.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/startup/allowlist.py` | UPDATE | Created as an empty skeleton by Story 4.1 so AC #1 of that story ("one module containing both stages and the FR-17 allowlist") holds. **Change:** author the single declaration — the two authentication allowlists, the route-prefix scope, the permitted route views, and AD-8's contributable and forbidden key sets. **Preserve:** the module's position inside `src/config/startup/`; it must not move to `src/config/authorization/` or become a settings entry. |
| `src/config/startup/stage_two.py` | READ ONLY (import) | Story 4.3's `_iter_view_callables` is reused by the route-side test. Do not copy it into the test module; one walker. |
| `tests/unit/config/startup/test_authentication_allowlist.py` | NEW | Settings-side exact-equality assertions, route-side object-resolved assertions, both evasion tests, the scope test, the AC #3 mechanism test. |
| `tests/unit/config/startup/test_allowlist_declaration.py` | NEW | One-declaration and disjointness structural assertions. |

**Verified against the repository (2026-08-15):**

- `src/config/settings/base.py:133-136` — `AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend", "allauth.account.auth_backends.AuthenticationBackend"]`. `ModelBackend` is present today and must be gone before this test passes; Epic 2 removes it.
- `src/config/settings/base.py:357-364` — `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = ("rest_framework.authentication.SessionAuthentication", "rest_framework.authentication.TokenAuthentication")`. `TokenAuthentication` is present today; Epic 2 Story 2.8 removes it and Story 2.7 adds the Bearer class.
- `src/config/urls.py:24` — `path("accounts/", include("allauth.urls"))`. This is the prefix AD-21's evasion exploits.
- `src/config/urls.py:21` — `path(settings.ADMIN_URL, admin.site.urls)`, with `ADMIN_URL = "admin/"` at `base.py:264` and `env("DJANGO_ADMIN_URL")` at `production.py:107`. The admin-login prefix is therefore **parameterized by environment**; the route-prefix scope must read `settings.ADMIN_URL` rather than hardcode `admin/`.
- `src/config/urls.py:11,39` — `obtain_auth_token` imported and routed at `api/auth-token/`. Present today; Epic 2 Story 2.8 removes it.
- `src/config/websocket.py` — **still present**. AD-16 and Epic 1 Story 1.4 delete it together with its `[tool.coverage.run] omit` entry (`pyproject.toml:168`). Until that lands, a network surface exists beneath Django's routing that this allowlist cannot see. Record it in the Completion Notes if Epic 1 has not landed; do not delete it here — that is Story 1.4's acceptance criterion, and its coverage omit entry must be removed in the same change.

**Does not exist yet and is not created here:** `accelerator.toml` (Epic 7), `component.toml` (Epic 5 — the adopted-app list AD-8's composition step reads), `src/config/authorization/` (Epic 2 — the Bearer authentication class named in `ALLOWED_DRF_AUTHENTICATION_CLASSES`), the local sign-in module (Epic 3).

### Testing Requirements

- `tests/unit/config/startup/`, mirroring `src/config/startup/`, per the spine's Test-location convention. All `core` — the allowlist travels in all twelve combinations.
- Unit tests only: the allowlist reads settings and the resolved URLconf, and touches no database, network or filesystem. No `@pytest.mark.integration` here.
- Specific assertions the ACs demand:
  - **Exact set equality** on `AUTHENTICATION_BACKENDS` and on the DRF default authentication classes — not `issubset`, not `all(x in allowed)`.
  - An unlisted entry monkeypatched in fails the test (AC #1, AC #3).
  - An in-scope route whose view callable is not in the permitted set fails, including when its route name and prefix are innocuous (AC #2 with AD-21's evasion).
  - A business route outside every declared prefix does not fail (AC #2's second clause).
  - `CONTRIBUTABLE_KEYS` and `FORBIDDEN_CONTRIBUTABLE_KEYS` are disjoint and contain no namespace prefixes (AC #4, AD-8).
- These tests run against `config.settings.test` (`pyproject.toml:143`, `--ds=config.settings.test`), which inherits `base.py`. That is the right target: the allowlist is a statement about the base's surface in every combination, not about the deployed module alone.
- AD-20: ninety percent including templates, `COVERAGE_CORE=ctrace` in force (`pixi.toml:145-151`). Do not add `src/config/startup/` to `[tool.coverage.run] omit` (`pyproject.toml:160-168`) — that list is a closed carrier-declared surface and narrowing it blinds the only residue detector the product has.
- `pixi run test` in the inner loop; `pixi run ci` (`pixi.toml:206`) is the done condition.

#### Project Structure Notes

Aligned with the Structural Seed, which annotates `src/config/startup/` as "both refusal stages + the FR-17 allowlist (AD-26)". The declaration lives with the conditions it backstops, which is AD-26's explicit reason for putting it there.

Two forward references, both **traceability markers rather than acceptance conditions for this story**: Epic 9's composition step that enforces `CONTRIBUTABLE_KEYS` (this story declares, Epic 9 enforces), and Epic 7's move of the declaration into `accelerator.toml` (same content, new residency). Neither blocks this story: the allowlist test is completable and meaningful against the reference application alone.

One dependency worth stating plainly: this story's settings-side assertions cannot pass until Epic 2 removes `ModelBackend` and `TokenAuthentication` from `base.py`. That is correct sequencing, not a defect — Epic 4 follows Epics 2 and 3 precisely because "the conditions it enforces are about paths those epics create." If Epic 2 has not landed, author the declaration and the tests, and record the failing gate in the Completion Notes rather than widening the allowlist to accommodate the current tree. Widening it would make the allowlist a description of what exists instead of a statement of what is approved, which is the failure FR-17 exists to prevent.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.6]
- [Source: _bmad-output/planning-artifacts/epics.md#Cross-epic threads] — line 221: one declaration, authored in Epic 4, extended in Epic 9, never forked
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — lines 308-326
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-8]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-21]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-16]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-17]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#SC-5]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.4] — the sub-router network surface whose deletion this allowlist depends on
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.8] — removal of the static-token credential surface

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
