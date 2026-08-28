---
status: done
baseline_revision: bbe1e0b
review_loop_iteration: 0
---

# Story 4.6: The authentication surface matches an allowlist exactly

Status: done

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

- [x] Task 1 — Author the single declaration in `src/config/startup/allowlist.py` (AC: #1, #4)
  - [x] `src/config/startup/allowlist.py` is created as an empty skeleton by Story 4.1. Fill it with **one** module-level declaration object covering both FR-17's allowlist and AD-8's permitted-contribution surface. One frozen dataclass or one module of frozen constants — not two parallel structures in one file, which is the same fork with a shorter distance.
  - [x] `ALLOWED_AUTHENTICATION_BACKENDS: frozenset[str]` — the exact set of dotted paths permitted in `AUTHENTICATION_BACKENDS`. After Epic 2, that is allauth's authentication backend and nothing else; `django.contrib.auth.backends.ModelBackend` is forbidden by Story 4.2's condition 2a and must **not** appear here.
  - [x] `ALLOWED_DRF_AUTHENTICATION_CLASSES: frozenset[str]` — the exact set permitted in `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`. After Epic 2, that is `SessionAuthentication` and the Bearer authentication class Story 2.7 builds; `rest_framework.authentication.TokenAuthentication` must **not** appear here.
  - [x] `AUTHENTICATION_ROUTE_PREFIXES: tuple[str, ...]` — the route prefixes the component itself owns for authentication, admin login and token issuance. This is the **scoping** declaration of AC #2, not a predicate: it says which routes the allowlist has authority over, and business routes outside it are out of scope.
  - [x] `ALLOWED_AUTHENTICATION_ROUTE_VIEWS` — for each in-scope prefix, the set of view callables permitted there, declared as importable references resolved to objects at test time (see Task 3).
  - [x] `CONTRIBUTABLE_KEYS: frozenset[str]` — AD-8's closed permitted-key surface, **by explicit key, never by namespace**: additional `DATABASES` entries and their routers, `INSTALLED_APPS` entries, an app's own namespaced settings, named non-global DRF and Celery keys, and **the `django_service` navigation registry** — an ordered sequence contributed to append-only in adopted-app-list order, exactly like `INSTALLED_APPS`.
  - [x] The navigation registry is on the surface for a stated reason, and the reason belongs in the declaration as a comment: it is the one contributable key rendered on every page, and it is permitted where `MIDDLEWARE` and `AUTHENTICATION_BACKENDS` are refused because **it confers presentation and never authorization** — labels are auto-escaped and no entry carries raw HTML. An entry is **data, never markup**: a label, a URL *name*, and an optional permission the renderer filters on (AD-8).
  - [x] `FORBIDDEN_CONTRIBUTABLE_KEYS: frozenset[str]` — the global-default keys refused whether or not the base already sets them: `DEFAULT_AUTHENTICATION_CLASSES`, `DEFAULT_PERMISSION_CLASSES`, `MIDDLEWARE`, `AUTHENTICATION_BACKENDS`.
  - [x] Add a module docstring stating, in one paragraph, that these are **one declaration**: adding a credential path and adopting an app are checked by one mechanism rather than two that can disagree; that `src/config/startup/` is the **authoritative** location and `accelerator.toml` gains a **mirror** of it in Epic 7 with a gate test asserting the two are equal; and that Epic 9 extends it, never forks it.
  - [x] Add a structural test asserting `ALLOWED_AUTHENTICATION_BACKENDS ∪ ALLOWED_DRF_AUTHENTICATION_CLASSES` is disjoint from `FORBIDDEN_CONTRIBUTABLE_KEYS`'s corresponding entries — the mechanical proof that the two halves cannot drift into contradiction.

- [x] Task 2 — The settings-side allowlist test (AC: #1, #3)
  - [x] `tests/unit/config/startup/test_authentication_allowlist.py`.
  - [x] Assert `set(settings.AUTHENTICATION_BACKENDS) == ALLOWED_AUTHENTICATION_BACKENDS` — **exact equality, not a subset test**. An entry present but not listed fails; an entry listed but absent also fails, which is what makes the allowlist a statement about the surface rather than a floor.
  - [x] Assert `set(settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]) == ALLOWED_DRF_AUTHENTICATION_CLASSES` on the same terms.
  - [x] The failure message must name the unexpected entry and state the AC #3 remedy in words: adding a credential path requires editing `src/config/startup/allowlist.py` in the same change, and that edit is the moment a human decides whether the path belongs.
  - [x] Add the AC #3 test itself: monkeypatch an extra backend into the settings namespace and assert the allowlist test fails. Without it, "the allowlist must be edited in the same change" is a claim rather than a mechanism.

- [x] Task 3 — The route-side allowlist test, resolving objects (AC: #1, #2)
  - [x] Reuse `_iter_view_callables` from `src/config/startup/stage_two.py` (Story 4.3) — one walker, not two. It yields unwrapped view callables from the resolved URLconf.
  - [x] Scope: consider only routes whose resolved path falls under one of `AUTHENTICATION_ROUTE_PREFIXES`. Business routes a developer adds are out of scope (AC #2) — an allowlist covering every route "would break the build on the first feature anyone wrote, and would be deleted within a week."
  - [x] Within scope, assert each route's **view callable** is in `ALLOWED_AUTHENTICATION_ROUTE_VIEWS` for that prefix. Compare resolved objects by identity or by `issubclass` on the view class, never by route name or dotted-path string.
  - [x] **The prefix scoping is not the predicate, and the distinction is the whole point.** `src/config/urls.py:24` mounts `allauth.urls` under `accounts/`, so `/accounts/` is necessarily an in-scope prefix. AD-21 states the consequence: "a route named `local_persona_login` mounted under `/accounts/` would otherwise satisfy this AD and pass an allowlist that already permits `/accounts/` for allauth." The prefix decides *whether the allowlist looks*; the view callable decides *whether it passes*. Any implementation that allowlists a prefix and stops looking is wrong.
  - [x] Cross-check with Story 4.3: a route whose callable belongs to the local sign-in module is refused by stage 2 in a deployed component **and** is absent from `ALLOWED_AUTHENTICATION_ROUTE_VIEWS`. Two independent mechanisms, one declaration; do not make one call the other.
  - [x] Add the evasion test: a route named `local_persona_login` mounted at `accounts/local-sign-in/` whose callable belongs to the local sign-in module fails the allowlist test. Add its mirror: a route named something innocuous mounted at `api/token/` whose callable is `obtain_auth_token` also fails.

- [x] Task 4 — Record the AD-8 half without building Epic 9's mechanism (AC: #4)
  - [x] Declare `CONTRIBUTABLE_KEYS` and `FORBIDDEN_CONTRIBUTABLE_KEYS` in the same file. Epic 9 Story 9.4 builds the composition step that enforces them; this story authors the declaration only.
  - [x] Add a test asserting `CONTRIBUTABLE_KEYS` and `FORBIDDEN_CONTRIBUTABLE_KEYS` are disjoint, and that no entry of `CONTRIBUTABLE_KEYS` is a namespace prefix rather than an explicit key — AD-8 requires "by explicit key, never by namespace."
  - [x] Do **not** implement the contribution-merge behaviour, the `component.toml` adopted-app list, or the `ImproperlyConfigured` on touching an existing key. Those are Epic 9. Enforcing them here would mean building against a `component.toml` that does not exist.
  - [x] Mark the enforcement half in Dev Notes as a **traceability marker, not an acceptance condition for this story**.
  - [x] The navigation registry's own stage-2 validation — every registered URL name must resolve in the URLconf, refused as `ImproperlyConfigured` at the stage that has a resolved URLconf (AD-8, AD-26) — is likewise Epic 9's enforcement, not this story's. Declare the key here; do not implement the check, and do not add it to the stage-2 fixed order. It is **not** a tenth refusal condition (see Dev Notes).

- [x] Task 5 — Tests (AC: all)
  - [x] `tests/unit/config/startup/test_authentication_allowlist.py` — Tasks 2 and 3, plus both evasion tests, plus the AC #3 mechanism test.
  - [x] `tests/unit/config/startup/test_allowlist_declaration.py` — Task 1's structural assertions and Task 4's disjointness and explicit-key assertions.
  - [x] Add a scope test: a business route added outside every `AUTHENTICATION_ROUTE_PREFIXES` entry does **not** fail the allowlist test. Without it the scoping is untested and the first feature anyone writes breaks the build.
  - [x] Add a one-declaration test: assert `src/config/startup/allowlist.py` is the only module under `src/` defining any of these names, by importing and comparing object identity across `src/config/` — a mechanical stand-in for AD-1 until Epic 7's two-way reconciliation exists.

## Dev Notes

### Architecture Constraints

- **AD-26 (binding clause):** "The FR-17 allowlist and AD-8's permitted-contribution surface are the same declaration, so adding a credential path and adopting an app are checked by one mechanism rather than two that can disagree." Also: "The refusal contract is one module, `src/config/startup/`, containing both stages **and the FR-17 allowlist**." And the clause that fixes where the declaration actually lives: "**`src/config/startup/` holds the authoritative copy and `accelerator.toml` mirrors it**, with a gate test asserting equality — the AD-20 precedent for a closed carrier-declared surface. This resolves against AD-1's 'and nowhere else': the carrier is `machinery` and never travels, while the AD-8 composition step runs at settings import inside a materialized component that does not have it, so the carrier cannot be the runtime authority for a rule that must execute there. One declaration, one authoritative location, one reconciliation."
  **Prevents:** "an allowlist maintained apart from the conditions it backstops."
- **AD-8 (binding rule):** "The contributable surface is closed and enumerated **by explicit key, never by namespace**: additional `DATABASES` entries and their routers, `INSTALLED_APPS` entries, the app's own namespaced settings, and named non-global DRF and Celery keys. **Its authoritative location is `src/config/startup/`, mirrored into `accelerator.toml` and reconciled by a gate test (AD-26)** — the composition step runs inside a materialized component, which does not carry the carrier. No global-default key is contributable — `DEFAULT_AUTHENTICATION_CLASSES`, `DEFAULT_PERMISSION_CLASSES`, `MIDDLEWARE`, `AUTHENTICATION_BACKENDS` are refused whether or not the base already sets them, because 'introducing a new key is permitted' would otherwise hand an adopted app authorization over every API request. The permitted-key list and the FR-17 allowlist are **one declaration**, not two lists maintained apart."
  Also, added in revision 3 and part of the same surface: "**Navigation is a contributed ordered sequence, and it is on the surface.** `django_service` owns a navigation registry, contributed to exactly like `INSTALLED_APPS` — append only, in adopted-app-list order. An entry is **data, never markup**: a label, a URL *name*, and an optional permission the renderer filters on. This is the one contributable key rendered on every page, so it is permitted where `MIDDLEWARE` and `AUTHENTICATION_BACKENDS` are refused for a reason that holds here: it confers presentation and never authorization, labels are auto-escaped, and no entry carries raw HTML. Every registered URL name must resolve in the URLconf, refused as `ImproperlyConfigured` at stage 2 — the stage that has a resolved URLconf (AD-26)."
  **Prevents:** "adopting an app being a hand edit repeated in every component; an installed package acquiring visibility of, or authority over, every request."
- **AD-21 (the evasion this story must block):** "a route named `local_persona_login` mounted under `/accounts/` would otherwise satisfy this AD and pass an allowlist that already permits `/accounts/` for allauth."
- **AD-16:** "No network surface exists beneath Django's routing … Any future protocol handled below Django's URL resolver is a designed feature with its own authentication story and its own entry in the carrier, never an inherited handler."
  **Prevents:** "a credential or network surface that the route allowlist cannot see because it is not a route." Epic 1 Story 1.4 deletes `src/config/websocket.py`, the scope-dispatching wrapper and its `[tool.coverage.run] omit` entry together — that deletion is a **precondition for this allowlist to be complete rather than merely present**, and it is Epic 1's work, not this story's.
- **AD-1:** every declaration has exactly one site. `accelerator.toml` is authored in Epic 7 and gains a **mirror** of this declaration then, with a gate test asserting the two are equal — the module here stays authoritative and is not emptied. AD-26 states why: the composition step this surface governs runs at settings import inside a materialized component, which does not carry the carrier, so the carrier cannot be the runtime authority.
- **FR-17's own reasoning:** "the nine refusal conditions are a denylist … and a denylist cannot by construction catch a path invented next year. This FR inverts that, which is the difference between FR-16 being a guarantee and being a habit."
- **CG-3:** an allowlist violation fails the test; it never warns.
- **AD-24 forbids** conditional imports and `try/except ImportError` in the declaration module. Every reference resolves unconditionally.

### The cross-epic thread this story sits on

`epics.md:223`: "FR-17's allowlist and AD-8's contributable surface are **one declaration** — authored in Epic 4, extended in Epic 9, never forked into two lists." Authored here, and **this module stays the authoritative copy**. Epic 7 adds a mirror in `accelerator.toml` and the gate test that asserts the two are equal (AD-26); it does not relocate the declaration, because the carrier is `machinery`, never travels, and the AD-8 composition step has to execute inside a materialized component that does not have it. Extended in Epic 9 when adopted apps exist. **At no point does a second list appear** — a mirror reconciled by a gate test is not a second list, which is exactly the AD-20 precedent AD-26 cites.

**The two names this story must consume but cannot verify.** `ALLOWED_DRF_AUTHENTICATION_CLASSES` needs the Bearer authentication class Story 2.7 builds, and `ALLOWED_AUTHENTICATION_ROUTE_VIEWS` needs the local sign-in module Story 3.4 creates — neither exists when this story is written. AD-26's authoritative-location rule is what resolves this: because `src/config/startup/` is the runtime authority rather than a copy of the carrier, the declaration here is the single site those stories import from, and a name that does not yet resolve is a landing dependency rather than a fork. Record any such name in the Completion Notes so the owning story consumes it instead of declaring its own.

The nine refusal conditions this allowlist backstops are the settled fourteen forbidden states of `epics.md:310-328` — seven unconditional conditions and two conditional, implemented in Stories 4.2, 4.3 and 4.4. The allowlist's job is the inverse: the conditions refuse known-bad states; the allowlist fails the build on any authentication surface not explicitly approved.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/startup/allowlist.py` | UPDATE | Created as an empty skeleton by Story 4.1 so AC #1 of that story ("one module containing both stages and the FR-17 allowlist") holds. **Change:** author the single declaration — the two authentication allowlists, the route-prefix scope, the permitted route views, and AD-8's contributable and forbidden key sets. **Preserve:** the module's position inside `src/config/startup/`; it must not move to `src/config/authorization/`, become a settings entry, or be reduced to a reader of `accelerator.toml` — this module is the authoritative copy and the carrier mirrors it (AD-26). |
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

- `tests/unit/config/startup/`, mirroring `src/config/startup/`, per the spine's Test-location convention. All `core` — the allowlist travels in all six combinations.
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

Three forward references, all **traceability markers rather than acceptance conditions for this story**: Epic 9's composition step that enforces `CONTRIBUTABLE_KEYS` (this story declares, Epic 9 enforces); Epic 7's `accelerator.toml` mirror of the declaration plus the gate test asserting equality (same content in a second, non-authoritative place); and the navigation registry's stage-2 validation, below. None blocks this story: the allowlist test is completable and meaningful against the reference application alone.

**The navigation registry's stage-2 refusal is Epic 9's, not this story's — and it is not a tenth condition.** AD-8 requires that every URL name registered in the navigation registry resolve in the URLconf, refused as `ImproperlyConfigured` at stage 2, the stage that has a resolved URLconf. Two things follow, and they point in different directions. The *declaration* half is this story's: the registry is a key on the closed contributable surface, so it is named in `CONTRIBUTABLE_KEYS` here (Task 1) alongside the reason it is permitted where `MIDDLEWARE` is refused. The *enforcement* half is not: it validates the content of a contribution, which only exists once the composition step and the `component.toml` adopted-app list exist, and both are Epic 9's — the same boundary Task 4 already draws for the rest of `CONTRIBUTABLE_KEYS`. Its shape is Story 9.6's, an adoption-time gate on what a contribution declared, rather than Stories 4.2–4.4's, a forbidden state of the component's own configuration. So it does **not** enter the settled table of nine conditions and fourteen forbidden states, and Story 4.5's audit must still assert exactly fourteen. What it does inherit from this epic is the mechanism: it executes in `src/config/startup/stage_two.py` and Epic 9 appends it to the fixed-order tuple Story 4.3 establishes, which is the shortest available proof that AD-26's "one location, one owner" holds for a refusal an entirely different epic contributes.

One dependency worth stating plainly: this story's settings-side assertions cannot pass until Epic 2 removes `ModelBackend` and `TokenAuthentication` from `base.py`. That is correct sequencing, not a defect — Epic 4 follows Epics 2 and 3 precisely because "the conditions it enforces are about paths those epics create." If Epic 2 has not landed, author the declaration and the tests, and record the failing gate in the Completion Notes rather than widening the allowlist to accommodate the current tree. Widening it would make the allowlist a description of what exists instead of a statement of what is approved, which is the failure FR-17 exists to prevent.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.6]
- [Source: _bmad-output/planning-artifacts/epics.md#Cross-epic threads] — line 223: one declaration, authored in Epic 4, extended in Epic 9, never forked
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — lines 310-328
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

claude-opus-5[1m]

### Debug Log References

- `pixi run ci` — exit 0. 1269 passed, total coverage 96.83% (floor 90).
- `DATABASE_URL=postgres://gateuser:…@localhost:55432/gatedb pixi run test-cov` —
  exit 0. 1269 passed, total coverage 96.83%. Identical on PostgreSQL 17 and on
  the sqlite default.
- The blocking probe, before any change: `config.settings.production` imported
  under a deployed runtime with every documented variable supplied raised
  `ImproperlyConfigured: AUTHENTICATION_BACKENDS contains
  django.contrib.auth.backends.ModelBackend in a deployed component`. After the
  base correction the same probe imports cleanly.
- Negative controls, each applied and reverted:
  - the allowlist emptied of its only backend fails
    `test_the_authentication_backends_match_the_allowlist_exactly` **and**
    `test_a_missing_approved_entry_fails_too`, so both directions of the equality
    are live;
  - `GOVERNED_SETTING_KEYS` pointed at a key AD-8 does not refuse fails
    `test_every_governed_key_is_refused_to_contributors` alone, which is the join
    between the two halves doing exactly its one job;
  - the admin scope widened back to the bare mount fails eight cases, including
    `test_the_deployed_configuration_passes` — the real URLconf, with
    `django_celery_beat.admin` and `django.contrib.auth.admin` registered, is what
    proves the narrowing is necessary rather than tidy;
  - `ModelBackend` put back into `base.py` fails four, among them
    `test_a_deployed_production_import_is_accepted_when_every_requirement_is_met`,
    which is the case whose absence let the escape through in the first place.

### Completion Notes List

**An Epic 2 escape blocked this story, and was fixed inside it.** `base.py` still
declared `django.contrib.auth.backends.ModelBackend` in `AUTHENTICATION_BACKENDS`
and `ACCOUNT_LOGIN_METHODS = {"username"}` — stage 1's forbidden states 2a and 2b.
`production.py` overrides neither, so **no deployed component could import its
settings at all**: every real deployment refused at condition 2. The removal was
recorded as Epic 2 Story 2.6/2.8's, in a docstring at `tests/unit/test_settings.py`
that also predicted the transition — "when it lands, this assertion will fail, and
the fix is to move it forward rather than to delete it … after both, the import
reaches condition 4 and refuses on `OIDC_ISSUER` being unset". Epic 2 closed
without doing it. Both states moved into `local.py` and `test.py`, where the
locality that justifies them is, and the prediction held exactly: the chain now
stops at the trust anchor, which is a genuine deployment requirement.

This was raised with the user before the change, priced at three settings files
and two test expectations, and confirmed. Widening the allowlist to accommodate
the tree was the alternative and was refused, for the story's own reason: it would
have made the allowlist a description of what exists rather than a statement of
what is approved.

**The case whose absence let it through, added.** Every stage-1 condition had a
test that configured its forbidden state and asserted the refusal, and a real
deployed import was asserted to refuse — but nothing asserted that any environment
exists in which it does *not*. So a base carrying two forbidden states read, to
every green run, as the contract working.
`test_a_deployed_production_import_is_accepted_when_every_requirement_is_met` now
asserts the nine conditions are **jointly** satisfiable by a real settings module,
which is a different claim from each being individually satisfiable by a hand-built
namespace, and is the one that catches this class of escape.

**Spec-vs-tree drift reconciled.** The story writes every test path as
`tests/unit/config/startup/…`; no `config/` level exists — Stories 4.1–4.5 put the
suite at `tests/unit/startup/`. Every path was mapped accordingly and no `config/`
directory was created. Line references were stale too: `AUTHENTICATION_BACKENDS` is
at `base.py:203`, not `:203-206` as a four-line block after the correction, and
`ACCOUNT_LOGIN_METHODS` was at `:430`, not `:431`.

**The declaration keeps Story 4.1's names and changes their type, deliberately.**
The skeleton declared `ALLOWED_AUTHENTICATION_BACKENDS` and
`ALLOWED_API_AUTHENTICATION_CLASSES` as tuples of resolved objects, arguing that a
string comparison passes against a name that no longer resolves. The argument is
right; the location was wrong. `stage_one.py` hit the same wall from the other
side — resolving an authentication backend during settings composition raises
`AppRegistryNotReady` — and AD-26 says AD-8's composition step imports this module
at exactly that moment. So the declaration holds `frozenset[str]` (which is also
what this story's Task 1 specifies) and the *test* resolves every path and fails on
one that does not, which keeps the guarantee without making the module
unimportable where it has to be imported. `test_module_shape.py` now asserts
structurally that the allowlist imports no `django`, `allauth` or `rest_framework`
at all, so the property is enforced rather than intended.

The story's `ALLOWED_DRF_AUTHENTICATION_CLASSES` and `AUTHENTICATION_ROUTE_PREFIXES`
are the skeleton's `ALLOWED_API_AUTHENTICATION_CLASSES` and
`ALLOWED_AUTHENTICATION_ROUTE_PREFIXES`; the landed names won, since three modules
and a test already referenced them.

**`ALLOWED_AUTHENTICATION_ROUTE_VIEWS` is a set of packages, not an enumeration of
views.** Enumerating allauth's and the admin's view callables would be a list that
changed with every dependency upgrade. The permitted set is the *defining package*
of the view callable, matched exactly or as a dotted prefix — which is the
predicate `stage_two._refuse_local_sign_in_route` already resolves views by, so the
allowlist and the denylist recognize a view the same way without either calling the
other. AD-21's evasion fails on it: `config.local_dev.views` is not under `allauth`,
whatever the route is named or where it is mounted.

**The admin mount as a whole is not a scope, and that is the story's own rule
applied one prefix down.** A first attempt scoped the bare `ADMIN_URL` and the real
URLconf immediately refused fifteen routes belonging to `django_celery_beat.admin`,
`django.contrib.auth.admin` and the contenttypes shortcut. A scope over the whole
mount would need a permitted-package list that grew with `INSTALLED_APPS` and would
break on the first adopted app — AC #2's "deleted within a week", displaced. What is
in scope is admin **login** and the admin **password-change** form: two fixed routes
beneath a parameterized mount, which is what AC #2 actually names. `ADMIN_URL` is
read through `AuthenticationRouteScope.resolve_prefix`, never hardcoded, and
`test_the_admin_mount_as_a_whole_is_not_a_scope` exists so a later widening has to
delete a case that says why.

**Two prefixes are reserved rather than populated.** `_local/` and
`api/auth-token/` are in scope with *nothing* permitted, so anything mounted there
fails — where an undeclared prefix would simply not be looked at. That is what makes
the local sign-in mount and the retired token address enumerable by this allowlist
rather than only by stage 2. `config.local_dev.constants.LOCAL_SIGNIN_PATH_PREFIX`
is imported and asserted by object identity, not respelled: that module's docstring
names the FR-17 allowlist as one of the two consumers it exists for.

**The story's mirror evasion is mounted at `api/auth-token/`, and the `api/token/`
case became an assertion about the boundary.** Task 3 asks for a token view "mounted
at `api/token/`" to fail the allowlist. It cannot and should not: `api/` is the
business prefix, and putting it in scope is the failure AC #2's second clause
forbids. So the mirror is mounted at the address the surface actually occupied, and
the out-of-scope case is asserted honestly instead —
`test_the_business_route_the_allowlist_ignores_is_still_refused_by_stage_two` mounts
a forbidden view outside every scope, shows the allowlist ignores it, and shows
stage 2 refuses it by defining module wherever it sits. Two independent mechanisms;
neither calls the other; the gap between them is covered by a case rather than by an
assumption.

**`local.py` and `test.py` could have become the hole the allowlist cannot see.**
The allowlist states the *deployed* surface, and the local leaves now add a
credential path on top of it. `TestTheLocalAdditionsAreClosedByACondition`
reconciles the two: it asserts the suite really is running with the addition
installed (without which the reconciliation could pass over an empty set), that the
addition is absent from the allowlist, and that stage 1 refuses that exact entry —
read from the same mapping, so a leaf that changed which backend it added fails here
rather than leaving the case refusing a backend nobody installs.

**One `raise` in the package is deliberately not `ImproperlyConfigured`.**
`AuthenticationRouteScope.__post_init__` raises `ValueError` on a record declaring
both a prefix and a setting, or neither. It cannot raise the refusal type: the
module imports no Django, by requirement. And it is not a configuration state — it
is a malformed literal, reachable only by editing this repository. Story 4.5's Test D
scans every raise in the package, so the exception is recorded in a frozen
`OTHER_RAISE_ALLOWANCE` beside the existing `BROAD_EXCEPT_ALLOWANCE`, in the same
shape: a second one fails while the recorded one does not.

**Forward markers, not acceptance conditions for this story.** Epic 9 Story 9.4
builds the composition step that enforces `CONTRIBUTABLE_KEYS`; Epic 7 adds the
`accelerator.toml` mirror and the gate test asserting equality; the navigation
registry's stage-2 URL-name validation is Epic 9's and is **not** a tenth refusal
condition — Story 4.5's audit still asserts twelve unconditional states plus two
feature-owned ones, unchanged by this story.

**Residual risks.** (1) The route-side check walks `config/urls.py`'s deployed
branch through `tests.conftest.deployed_component_urlconf`; a credential route
reachable by a mechanism that is not a Django route is invisible to it, which is
AD-16's concern and is why Story 1.4's deletion of the sub-router was a
precondition — that deletion has landed, and `src/config/websocket.py` is gone.
(2) `stage_two._walk` keys its `seen` set on resolver identity, so mounting the
same URLconf twice in one throwaway configuration silently walks it once; the
admin-login evasion case mounts a single allauth *view* rather than a second
`include("allauth.urls")` for that reason, and says so. (3) `CONTRIBUTABLE_KEYS`
names the Celery and navigation keys this base can foresee; Epic 9 is where the
list meets a real adopted app, and it is expected to grow there by decision rather
than by discovery.

### File List

- `src/config/startup/allowlist.py` — UPDATE. The declaration, replacing Story 4.1's skeleton.
- `src/config/settings/base.py` — UPDATE. `ModelBackend` and `ACCOUNT_LOGIN_METHODS` removed from the deployed surface.
- `src/config/settings/local.py` — UPDATE. Both re-declared as locality-scoped affordances.
- `src/config/settings/test.py` — UPDATE. The same, so persona sign-in's session backend is declared.
- `tests/unit/startup/test_authentication_allowlist.py` — NEW. The behavioural half.
- `tests/unit/startup/test_allowlist_declaration.py` — NEW. The structural half.
- `tests/unit/startup/test_module_shape.py` — UPDATE. The allowlist is populated, and imports no Django.
- `tests/unit/startup/test_no_softening.py` — UPDATE. `OTHER_RAISE_ALLOWANCE`.
- `tests/unit/test_settings.py` — UPDATE. The refusal moved forward to condition 4; the deployed positive control added.
- `tests/unit/test_local_dev_urls.py` — UPDATE. `EXPECTED_BACKENDS` is the composed local surface.
