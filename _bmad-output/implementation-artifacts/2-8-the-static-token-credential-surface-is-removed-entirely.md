# Story 2.8: The static-token credential surface is removed entirely

Status: ready-for-dev

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

- [ ] Task 1 — Confirm the replacement exists before deleting anything (AC: #3)
  - [ ] Verify `config.authorization.authentication.OIDCBearerAuthentication` exists and is present in `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` (Story 2.7 Task 4). If it is not, stop — this story must not land first. The readiness assessment records the ordering as load-bearing: "2.6 and 2.7 precede 2.8 so the replacement credential paths exist before the old ones are deleted."
  - [ ] Verify `tests/integration/authorization/test_bearer_authentication.py` passes. That suite is the evidence for AC #3's "no functionality is lost."

- [ ] Task 2 — Remove the route from `src/config/urls.py` (AC: #2)
  - [ ] Delete the import `from rest_framework.authtoken.views import obtain_auth_token` (line 11).
  - [ ] Delete the `path("api/auth-token/", obtain_auth_token, name="obtain_auth_token")` entry and its `# DRF auth token` comment (lines 38–39).
  - [ ] Leave the rest of the API block exactly as it is: `path("api/", include("config.api_router"))`, `api/schema/`, `api/docs/`.
  - [ ] Do **not** replace the route with a 410, a redirect, or a deprecation shim. A credential-minting route that still resolves is still a route the URLconf-resolving refusal must see. Delete it.

- [ ] Task 3 — Remove the settings surface in `src/config/settings/base.py` (AC: #1)
  - [ ] Delete `"rest_framework.authtoken"` from `THIRD_PARTY_APPS` (line 112).
  - [ ] Delete `"rest_framework.authentication.TokenAuthentication"` from `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` (line 360). The tuple is left holding `OIDCBearerAuthentication` and `SessionAuthentication`.
  - [ ] Leave `SessionAuthentication` in place — it is the interactive flow's API surface and Story 2.6 made that flow IdP-owned. It is not a static-token path and FR-6 does not name it.
  - [ ] Do **not** touch `DEFAULT_PERMISSION_CLASSES` or `DEFAULT_SCHEMA_CLASS`.

- [ ] Task 4 — Record the residue you are deliberately not cleaning up (AC: #1)
  - [ ] Removing `rest_framework.authtoken` from `INSTALLED_APPS` leaves the `authtoken_token` and `authtoken_tokenproxy` tables, and the app's rows in `django_migrations`, in any database that already migrated. Django does not error on this and no migration is written here.
  - [ ] Write **no** migration to drop those tables. Migration is a release-stage step the deployment repository performs (AD-22, FR-41); a destructive drop authored in this repository would run against every environment on the next release with no operator decision.
  - [ ] Record the residue in `docs/authentication.md` (created in Story 2.3) under a short "Retired surfaces" heading: what was removed, what remains in existing databases, and that dropping it is an operator decision.
  - [ ] Search for and remove any leftover reference: at the time of writing, `authtoken` / `obtain_auth_token` / `TokenAuthentication` appear in exactly four places — `src/config/urls.py:11`, `src/config/urls.py:39`, `src/config/settings/base.py:112`, `src/config/settings/base.py:360`. No test, doc or fixture references them. Re-run the search after your edits and confirm zero hits under `src/`, `tests/` and `docs/`.

- [ ] Task 5 — Tests (AC: #1, #2, #3)
  - [ ] `tests/unit/test_credential_surface.py` (new):
    - `reverse("obtain_auth_token")` raises `django.urls.NoReverseMatch`;
    - `resolve("/api/auth-token/")` raises `django.urls.Resolver404`;
    - `"rest_framework.authtoken" not in settings.INSTALLED_APPS`;
    - no entry in `settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` ends with `"TokenAuthentication"`.
  - [ ] AC #2 demands the assertion be made against the **resolved** URL configuration, not the setting. `resolve()` and `reverse()` both operate on the loaded URLconf, which is what makes them the right tools; an assertion that merely greps `urls.py` does not satisfy the AC. `tests/unit/users/test_api_urls.py` already uses exactly this `reverse`/`resolve` pair and is the pattern to follow.
  - [ ] `tests/integration/test_credential_surface.py` (new, `@pytest.mark.django_db`) — a live `client.get("/api/auth-token/")` and `client.post("/api/auth-token/", ...)` both return 404.
  - [ ] AC #3 — assert an API call that would previously have used a static token now succeeds through the Bearer flow: reuse the token-minting fixtures from `tests/integration/authorization/test_bearer_authentication.py` against `reverse("api:user-me")`.
  - [ ] Run `pixi run test`, `pixi run test-integration`, then `pixi run ci`.

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

### Debug Log References

### Completion Notes List

### File List
