---
baseline_revision: 4589c54
final_revision: 4938476
review_loop_iteration: 0
status: done
followup_review_recommended: true
warnings: []
---

# Story 2.8: The static-token credential surface is removed entirely

Status: done

## Story

As a platform engineer,
I want every locally minted API token path deleted,
so that a deployed component has no credential path the IdP does not own.

## Acceptance Criteria

**Traceability:** FR-6 · SC-5

1. **Given** `REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES`
   **When** this story lands
   **Then** `TokenAuthentication` is absent
   **And** `rest_framework.authtoken` is absent from `INSTALLED_APPS`

2. **Given** the URL configuration
   **When** the route is removed
   **Then** a request to `/api/auth-token/` returns 404
   **And** a test asserts the route's absence from the *resolved* URL configuration rather than merely the setting's absence

3. **Given** the programmatic flow from Story 2.7 is in place
   **When** an API client authenticates
   **Then** it uses the Bearer flow
   **And** no functionality is lost by the removal

## Tasks / Subtasks

- [x] Task 1 — Confirm the replacement exists before deleting anything (AC: #3)
  - [x] Verify `config.authorization.authentication.OIDCBearerAuthentication` exists and is present in `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` (Story 2.7 Task 4). If it is not, stop — this story must not land first. The readiness assessment records the ordering as load-bearing: "2.6 and 2.7 precede 2.8 so the replacement credential paths exist before the old ones are deleted."
  - [x] Verify `tests/integration/authorization/test_bearer_authentication.py` passes. That suite is the evidence for AC #3's "no functionality is lost."

- [x] Task 2 — Remove the route from `src/config/urls.py` (AC: #2)
  - [x] Delete the import `from rest_framework.authtoken.views import obtain_auth_token` (line 11).
  - [x] Delete the `path("api/auth-token/", obtain_auth_token, name="obtain_auth_token")` entry and its `# DRF auth token` comment (lines 38–39).
  - [x] Leave the rest of the API block exactly as it is: `path("api/", include("config.api_router"))`, `api/schema/`, `api/docs/`.
  - [x] Do **not** replace the route with a 410, a redirect, or a deprecation shim. A credential-minting route that still resolves is still a route the URLconf-resolving refusal must see. Delete it.

- [x] Task 3 — Remove the settings surface in `src/config/settings/base.py` (AC: #1)
  - [x] Delete `"rest_framework.authtoken"` from `THIRD_PARTY_APPS` (line 112).
  - [x] Delete `"rest_framework.authentication.TokenAuthentication"` from `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` (line 360). The tuple is left holding `OIDCBearerAuthentication` and `SessionAuthentication`.
  - [x] Leave `SessionAuthentication` in place — it is the interactive flow's API surface and Story 2.6 made that flow IdP-owned. It is not a static-token path and FR-6 does not name it.
  - [x] Do **not** touch `DEFAULT_PERMISSION_CLASSES` or `DEFAULT_SCHEMA_CLASS`.

- [x] Task 4 — Record the residue you are deliberately not cleaning up (AC: #1)
  - [x] Removing `rest_framework.authtoken` from `INSTALLED_APPS` leaves the `authtoken_token` and `authtoken_tokenproxy` tables, and the app's rows in `django_migrations`, in any database that already migrated. Django does not error on this and no migration is written here.
  - [x] Write **no** migration to drop those tables. Migration is a release-stage step the deployment repository performs (AD-22, FR-41); a destructive drop authored in this repository would run against every environment on the next release with no operator decision.
  - [x] Record the residue in `docs/authentication.md` (created in Story 2.3) under a short "Retired surfaces" heading: what was removed, what remains in existing databases, and that dropping it is an operator decision.
  - [x] Search for and remove any leftover reference: at the time of writing, `authtoken` / `obtain_auth_token` / `TokenAuthentication` appear in exactly four places — `src/config/urls.py:11`, `src/config/urls.py:39`, `src/config/settings/base.py:112`, `src/config/settings/base.py:360`. No test, doc or fixture references them. Re-run the search after your edits and confirm zero hits under `src/`, `tests/` and `docs/`.

- [x] Task 5 — Tests (AC: #1, #2, #3)
  - [x] `tests/unit/test_credential_surface.py` (new):
    - `reverse("obtain_auth_token")` raises `django.urls.NoReverseMatch`;
    - `resolve("/api/auth-token/")` raises `django.urls.Resolver404`;
    - `"rest_framework.authtoken" not in settings.INSTALLED_APPS`;
    - no entry in `settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` ends with `"TokenAuthentication"`.
  - [x] AC #2 demands the assertion be made against the **resolved** URL configuration, not the setting. `resolve()` and `reverse()` both operate on the loaded URLconf, which is what makes them the right tools; an assertion that merely greps `urls.py` does not satisfy the AC. `tests/unit/users/test_api_urls.py` already uses exactly this `reverse`/`resolve` pair and is the pattern to follow.
  - [x] `tests/integration/test_credential_surface.py` (new, `@pytest.mark.django_db`) — a live `client.get("/api/auth-token/")` and `client.post("/api/auth-token/", ...)` both return 404.
  - [x] AC #3 — assert an API call that would previously have used a static token now succeeds through the Bearer flow: reuse the token-minting fixtures from `tests/integration/authorization/test_bearer_authentication.py` against `reverse("api:user-me")`.
  - [x] Run `pixi run test`, `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **FR-6 (binding rule):** "The static-token credential surface is removed entirely — no `TokenAuthentication`, no `rest_framework.authtoken`, no `obtain_auth_token` route." Three things, all three named, all three verified present in the repository today.
- **AD-26 (binding rule — and the reason the weak test is not enough):** "**Predicates resolve objects, never strings.** The credential-path and local-sign-in conditions resolve the URLconf and refuse any route whose view callable belongs to the forbidden module — `obtain_auth_token`'s and the local sign-in module's — so renaming a route or remounting it under another prefix cannot evade them." AC #2's "resolved URL configuration rather than merely the setting's absence" is the same discipline expressed at story scope.
- **AD-16:** "`asgi.py` exposes Django's ASGI application directly … Any future protocol handled below Django's URL resolver is a designed feature with its own authentication story." Epic 1 Story 1.4 deletes `src/config/websocket.py` and the scope-dispatching wrapper. That deletion is what makes the URLconf a *complete* description of the network surface — which is what makes this story's route assertion meaningful rather than merely true. Note the dependency; do not re-do that deletion here.
- **AD-24 (what you must not do):** no conditional imports, no `try/except ImportError`, no settings-module inheritance. Do not "remove" the token surface by making it conditional on locality; delete it.
- **CG-3:** "Do not soften a refusal into a warning." The story-scale form: do not soften a removal into a deprecation.

### The forward reference — what this story does and does not close

FR-6's removal is this story's. The **enforcement** that a credential-minting route added next year fails the build is not: that is FR-17's allowlist and condition 6 of the refusal table ("A forbidden credential route is reachable in the resolved URLconf", stage 2, two forbidden states — `obtain_auth_token` and the local sign-in route), authored in **Epic 4 Stories 4.3 and 4.6**.

The distinction matters for scope: this story deletes the route and asserts its absence. It does **not** build a predicate that resolves view callables against a forbidden-module list, and it does not create `src/config/startup/`. AD-26 requires the refusal contract to have "one location, one owner"; adding a partial predicate here would give it two.

SC-5 appears on this story's requirements line for the same reason — it is satisfied jointly by this removal and by Epic 4's refusals, and this story alone does not close it.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
|---|---|---|
| `src/config/urls.py` | UPDATE | Today, 76 lines: home/about `TemplateView`s, `settings.ADMIN_URL` admin mount, `users/` include, `accounts/` allauth include, media static, a `DEBUG`-gated `staticfiles_urlpatterns()`, then the API block (35–46) holding `api/`, `api/auth-token/`, `api/schema/`, `api/docs/`, then `DEBUG`-gated error-page routes and the debug-toolbar mount. Removes one import and one `path`. **Preserve:** everything else, including the `DEBUG`-gated error routes — AD-30's smoke check renders a 404 and Epic 8 depends on those pages existing. |
| `src/config/settings/base.py` | UPDATE | Today: `THIRD_PARTY_APPS` 104–116 with `"rest_framework.authtoken"` at 112; `REST_FRAMEWORK` 357–364 with `TokenAuthentication` at 360. Removes both entries. **Preserve:** `"rest_framework"` itself at 111, `SessionAuthentication`, `DEFAULT_PERMISSION_CLASSES`, `DEFAULT_SCHEMA_CLASS`, `CORS_URLS_REGEX`, `SPECTACULAR_SETTINGS`. |
| `docs/authentication.md` | UPDATE | Created by Story 2.3. Adds the "Retired surfaces" section. |
| `tests/unit/test_credential_surface.py` | NEW | `reverse`/`resolve` and settings assertions. |
| `tests/integration/test_credential_surface.py` | NEW | Live 404 assertions. |

Verified by search before writing: `authtoken`, `obtain_auth_token` and `TokenAuthentication` appear at exactly those four source locations and nowhere in `tests/`, `docs/` or `pyproject.toml`. `rest_framework.authtoken` is **not** declared separately in `pixi.toml` — it ships inside `djangorestframework`, so no dependency changes.

### Testing Requirements

- Test location mirrors `src/`. These tests cover `src/config/urls.py` and `src/config/settings/base.py`, both `core`, so both test files are `core` disposition and are never pruned (spine, Consistency Conventions → Test location).
- `tests/integration/conftest.py` auto-applies `pytest.mark.integration` under `tests/integration/`; DB access still needs `@pytest.mark.django_db`.
- Integration tests leave state as found — default `django_db` rollback.
- The assertions AC #2 specifically demands: `NoReverseMatch` from `reverse("obtain_auth_token")` and `Resolver404` from `resolve("/api/auth-token/")`. Both read the loaded URLconf. A string search of `urls.py` does not satisfy the AC and must not be substituted for it.
- Coverage floor 90% including templates (AD-20), gate via `pixi run test-cov` inside `pixi run ci`. Add nothing to `[tool.coverage.run] omit`.
- `pixi run build` inside `pixi run ci` will catch a dangling import left behind in `urls.py`.
- One likely knock-on: `tests/integration/users/test_api_openapi.py` exercises the drf-spectacular schema. Removing an authentication class changes the generated security schemes. Re-run it and update any snapshot or assertion it holds rather than omitting it.

#### Project Structure Notes

No structural change. This story only subtracts, which is the point: after it, the only credential paths a component has are the two the IdP owns — the interactive flow (Story 2.6) and the Bearer flow (Story 2.7) — plus `SessionAuthentication`, which carries the session those flows establish.

Epic 4's allowlist (FR-17) will assert that surface exactly, "over `AUTHENTICATION_BACKENDS`, the DRF default authentication classes, and the component's own authentication route prefixes." Leaving `TokenAuthentication` in place would make that allowlist either wrong or permissive on its first day.

Note for the Epic-4 author, not for this story: `AUTHENTICATION_BACKENDS` still contains `"django.contrib.auth.backends.ModelBackend"` (`src/config/settings/base.py:133-136`), and allauth's local account URLs are still mounted at `accounts/`. Those are condition 2 of the refusal table ("A local credential path is live in settings", four forbidden states) and are deliberately out of scope here — FR-6 names three things and those are not among them.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-16]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-22]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.8]
- [Source: _bmad-output/planning-artifacts/epics.md:34,48] — FR-6, FR-17
- [Source: _bmad-output/planning-artifacts/epics.md:314-326] — the refusal table; conditions 2 and 6
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md:869] — SC-5
- [Source: _bmad-output/planning-artifacts/implementation-readiness-report-2026-08-15.md:404] — the 2.6/2.7 → 2.8 ordering
- [Source: src/config/urls.py:11,39] — the import and the route
- [Source: src/config/settings/base.py:112,360] — the installed app and the authentication class

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m]

### Debug Log References

`pixi run test` (504 passed) · `pixi run test-integration` (184 passed, 6 skipped) ·
`pixi run ci` exit 0, coverage 95.77%.

### Completion Notes List

- The spec's Task 4 claim that "no test, doc or fixture references them" was
  wrong. Two test references existed and were handled rather than deleted:
  `tests/unit/test_settings.py::test_the_old_token_credential_is_still_installed`
  asserted the class *was* installed (the inverse of AC #1) and is now
  `test_the_static_token_credential_is_gone`; the docstring of
  `tests/integration/authorization/test_bearer_authentication.py::test_a_header_naming_another_scheme_falls_through_too`
  forward-referenced this story and now describes the post-removal behaviour.
  Its assertions are unchanged and still pass -- a `Token ...` header now falls
  through to `SessionAuthentication`.
- Line numbers in the spec had drifted (`base.py` 133 and 525, not 112 and 360).
  A stale comment at `base.py:519-521` saying `TokenAuthentication` "stays for
  now" was removed with the entry it explained.
- `tests/integration/users/test_api_openapi.py` originally asserted only
  `bearerAuth`; the review pass added `assert RETIRED_SCHEME_NAME not in schemes`
  so the published contract — the only surface of this removal a client author
  reads — is pinned rather than narrated.
- No migration drops the residue (Task 4, AD-22, FR-41). It is recorded in
  `docs/authentication.md`, "Retired surfaces". Note the residue is the
  `authtoken_token` table only: `TokenProxy` is a proxy model
  (`rest_framework/authtoken/migrations/0003_tokenproxy.py:19`) and never had a
  table of its own.
- Task 4's "confirm zero hits under `src/`, `tests/` and `docs/`" holds for
  `src/` exactly. It cannot hold for `tests/` or `docs/`: a test that asserts a
  surface is absent must name the surface, and the operator-facing residue note
  must name the table. The permitted mentions are the two credential-surface test
  modules' constants and docstrings, two corrected docstrings in the Bearer and
  OpenAPI suites, and the "Retired surfaces" section.

### File List

- `src/config/urls.py` — removed the `obtain_auth_token` import and the
  `api/auth-token/` route.
- `src/config/settings/base.py` — removed `rest_framework.authtoken` from
  `THIRD_PARTY_APPS` and `TokenAuthentication` from
  `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`, with its stale comment.
- `docs/authentication.md` — new "Retired surfaces" section.
- `tests/unit/test_credential_surface.py` (new) — `reverse`/`resolve` and
  settings assertions.
- `tests/integration/test_credential_surface.py` (new) — live 404s and the
  Bearer-flow replacement call.
- `tests/unit/test_settings.py` — the inverse test replaced.
- `tests/integration/authorization/test_bearer_authentication.py` — docstring.
- `tests/integration/users/test_api_openapi.py` — docstring.

## Review Triage Log

### 2026-08-17 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 13: (high 1, medium 8, low 4)
- defer: 2: (high 0, medium 2, low 0)
- reject: 3: (high 0, medium 0, low 3)
- addressed_findings:
  - `[high]` `[patch]` `docs/authentication.md` told the operator the retained token rows were "inert regardless … because the class that read them is gone", and that "Django does not error" on the residue. Both are false and both feed an operator's decision about live credential material: `TokenAuthentication` ships inside the installed `djangorestframework` and is one settings line from reading those rows again, and the retained `OneToOneField` FK on `authtoken_token.user_id` makes `User.delete()` fail once the app no longer cascades it. Replaced with an explicit two-point operator note.
  - `[medium]` `[patch]` The residue list named `authtoken_tokenproxy` as a table. `TokenProxy` is a proxy model and has no table; an operator following the drop step would have errored on it. Corrected, with the reason stated.
  - `[medium]` `[patch]` The section opened with "A component mints no credential of its own; the only credentials it accepts are the ones the provider issues", which the repository contradicts one heading below — `ModelBackend` is still in `AUTHENTICATION_BACKENDS` and allauth's local login is still mounted at `accounts/`. Scoped the claim to the static-token surface and pointed at the refusal contract as the owner of the rest.
  - `[medium]` `[patch]` `tests/unit/test_credential_surface.py`'s docstring claimed `reverse`/`resolve` catch "a route remounted under another prefix". They do not — `reverse` catches only an unchanged name, `resolve` only the one literal path. Rewrote to state what the assertions buy and to name the resolver-walking predicate (Epic 4) as what they do not.
  - `[medium]` `[patch]` `tests/integration/test_credential_surface.py` repeated the same overclaim ("catches a route reintroduced by middleware or by a URLconf swap"). Rewritten to the real guarantee: a 410, redirect or shim answering at that path fails here even though `resolve` already raised.
  - `[medium]` `[patch]` The app assertion was `RETIRED_APP not in settings.INSTALLED_APPS`, a string membership test that `"rest_framework.authtoken.apps.AuthTokenConfig"` walks straight through. Replaced with `django.apps.apps.is_installed`, which compares `AppConfig.name` and so answers for the app rather than for one spelling of its entry.
  - `[medium]` `[patch]` The static-token predicate matched on the class-name suffix, so a subclass named anything else passed. Replaced with `issubclass(cls, TokenAuthentication)` over the resolved classes — AD-26's "predicates resolve objects, never strings" at this file's scale. This also removed a `rsplit(".", 1)[-1]` that changed no outcome for any input.
  - `[medium]` `[patch]` The DRF defaults were read off `settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`, which raises `KeyError` if the key is dropped entirely — while DRF quietly falls back to its own defaults, including `BasicAuthentication` against local passwords. Now read through `rest_framework.settings.api_settings`, so the fallback is the case that fails rather than the `KeyError`.
  - `[medium]` `[patch]` Absence was asserted only against `base` and the loaded test settings. `production.py:112` and `local.py:39,56,74` both mutate `INSTALLED_APPS`, so a reinstatement in the module that actually ships would have gone green — precisely the locality-conditional removal AD-24 forbids. Added `test_the_static_token_credential_is_gone_from_local_too` and `test_the_static_token_credential_is_gone_from_production`.
  - `[medium]` `[patch]` The new `_idp` fixture copied `_bearer` but dropped its `JWKS_TTL_SECONDS` and `JWKS_MIN_REFETCH_SECONDS` pins, leaving those windows to `base.py`'s `env.float` reads and the test's configuration a function of whoever's shell ran it. Both pinned.
  - `[low]` `[patch]` No assertion covered `tokenAuth` leaving the published OpenAPI contract — the story's own Testing Requirements named that file as a knock-on and the response had been to edit prose. Added `assert RETIRED_SCHEME_NAME not in schemes`.
  - `[low]` `[patch]` `test_the_token_app_is_not_installed`'s docstring said the app's "model and route are unreachable". Uninstalling removes registration, not reachability — the view still imports fine, which Story 4.3 depends on. Corrected.
  - `[low]` `[patch]` The "Retired surfaces" section recorded the database residue for the operator and gave the API client author nothing. Added "What an API client sends instead", including the trade this makes explicit: programmatic access now depends on a reachable, configured provider.
  - Verification of the patches themselves: the strengthened predicates were mutation-tested by reinstating the app and adding a `TokenAuthentication` subclass named `RenamedStaticCredential`. The first attempt used `apps.is_installed("authtoken")` — the app *label* — which is vacuous, since Django compares `AppConfig.name`; the mutation caught it and the constant was corrected to the dotted path. All three settings predicates then failed on the mutant and pass on the tree.

## Auto Run Result

Status: done

### What was implemented

FR-6's removal: the three named static-token surfaces are deleted rather than deprecated — the `rest_framework.authtoken` app, the `TokenAuthentication` default authenticator, and the `obtain_auth_token` route at `/api/auth-token/`. What remains is the two credentials the IdP owns (Story 2.7's Bearer flow, Story 2.6's interactive sign-in) plus the `SessionAuthentication` that carries the session those flows establish.

The enforcement half is explicitly *not* here: no resolver-walking predicate, no `src/config/startup/`. That is Epic 4 Stories 4.3 and 4.6, and the spine requires the refusal contract to have one owner. SC-5 is jointly satisfied and not closed by this story alone.

### Files changed

- `src/config/urls.py` — removed the `obtain_auth_token` import and the `api/auth-token/` route entry; the rest of the API block and the `DEBUG`-gated error routes untouched.
- `src/config/settings/base.py` — removed `"rest_framework.authtoken"` from `THIRD_PARTY_APPS` and `TokenAuthentication` from `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`, with the stale comment that explained why it was still there.
- `docs/authentication.md` — new "Retired surfaces" section: what went, what an API client sends instead, and what an already-migrated database still holds, including the two things an operator needs before choosing when to drop it.
- `tests/unit/test_credential_surface.py` (new) — `reverse`/`resolve` against the loaded URLconf, `apps.is_installed`, an `issubclass` predicate over the resolved DRF authenticators, and an exact-tuple control.
- `tests/integration/test_credential_surface.py` (new) — GET and POST to the retired path are 404; the API call that used to need a static token succeeds through the Bearer flow.
- `tests/unit/test_settings.py` — the inverse test (`…_is_still_installed`) replaced by absence assertions across `base`, `local` and `production`.
- `tests/integration/users/test_api_openapi.py` — asserts `tokenAuth` is gone from the published security schemes.
- `tests/integration/authorization/test_bearer_authentication.py` — one docstring corrected to post-removal reality; assertions unchanged.

### Review findings

13 patches applied (1 high, 8 medium, 4 low), 2 items deferred, 3 rejected, 0 spec-level loopbacks. The high-severity patch and three of the mediums were operator- or client-facing documentation claims that were simply false; five mediums were predicates that asserted less than their docstrings claimed. Rejected as noise: a `claims()` docstring justifying a fresh `jti` in a module that calls it once; the charge that `test_a_header_naming_another_scheme_falls_through_too` is now redundant (an unrecognised scheme and an absent header are different DRF paths); and the charge that the exact-tuple control subsumes the `issubclass` predicate (it does, for regression detection, but the two fail with different diagnostics).

Deferred: no test covers `User.delete()` against a database still holding the residual `authtoken_token` FK; and the `KEY_STORE._fetch` stub seam is now duplicated across two integration modules with no shared owner.

### Verification

- `pixi run ci` → exit 0. 696 passed, coverage 95.77% against a 90% floor. Run twice: once on the implementation subagent's output, once after the review patches.
- The implementation pass additionally ran the suite against real PostgreSQL 17 (`DATABASE_URL=postgres://…:55432/gatedb`), since the new integration test persists a claim-supplied username: 694 passed, same coverage.
- Mutation-tested the strengthened predicates by reinstating the app and adding a renamed `TokenAuthentication` subclass. All three settings assertions failed on the mutant; the mutation exposed and corrected a vacuous `apps.is_installed` argument in the patch itself.
- Post-edit search for `authtoken|obtain_auth_token|TokenAuthentication`: zero hits under `src/`. Remaining hits are the two credential-surface test modules, two corrected docstrings, and the "Retired surfaces" documentation — all naming the surface in order to assert or record its absence.

### Residual risks

- **The removal is asserted, not enforced.** Nothing yet fails the build if a credential-minting route is remounted under another prefix and another name, or if a static-token authenticator is added back under a different name in a settings module beyond the three now covered. That predicate is Epic 4's by design; until it lands, this is discipline rather than enforcement — the same gap `docs/authentication.md` already concedes for `createsuperuser`.
- **The database residue is real and dormant, not gone.** `authtoken_token` still holds usable secrets in any already-migrated deployment, and deleting a user who has a row in it will fail on the retained FK. Documented for the operator; deferred as a test.
- **The local credential surface is untouched and out of scope.** `ModelBackend` remains in `AUTHENTICATION_BACKENDS` and allauth's local account URLs remain mounted at `accounts/` — condition 2 of the refusal table, four forbidden states, for the Epic 4 author.
- The three new `importlib.import_module` calls in `tests/unit/test_settings.py` marginally enlarge the already-deferred structlog save/restore gap in `_evict_settings_modules`. No new failure mode; the durable fix is recorded against Story 2.6.

### Follow-up review

`true` — the review pass changed a security-relevant predicate set (three assertions strengthened from string matching to object resolution), extended coverage to two settings modules that ship, and rewrote operator-facing guidance whose previous version was actively misleading. The volume and consequence of that warrant an independent look.
