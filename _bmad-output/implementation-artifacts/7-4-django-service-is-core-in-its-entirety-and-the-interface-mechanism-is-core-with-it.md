# Story 7.4: django_service is core in its entirety and the interface mechanism is core with it

Status: ready-for-dev

## Story

As a lead developer,
I want no feature-scoped disposition anywhere inside the base package,
so that a reusable app cannot import a module that exists in some combinations and not in others.

## Acceptance Criteria

**Traceability:** FR-1, FR-3 · AD-29 · SC-7 · readiness warning W-1

1. **Given** that no source document enumerates which templates, static assets, views and forms constitute the interface mechanism
   **When** this story begins
   **Then** that surface is enumerated by audit of the existing tree and recorded in the carrier as `core`
   **And** the enumeration distinguishes the `home`/`about` demonstration pages, which are deleted, from `base.html`, `_navbar.html`, the error templates, form styling, static-file serving and the user profile views, which stay

2. **Given** any path inside `src/django_service/`
   **When** its disposition is assigned
   **Then** it is `core`
   **And** a gate test asserts that no `feature:*` disposition applies to any path inside it

3. **Given** surface an earlier revision assigned to a server-rendered UI feature
   **When** its disposition is decided
   **Then** nothing moves out of `django_service` — the interface mechanism is immovable core (revision 3), so `base.html`, the error templates, form styling, static-file serving and the user profile views all stay
   **And** the `home` and `about` demonstration pages are deleted rather than made core, including their `TemplateView`s in `src/config/urls.py` and `templates/pages/`
   **And** `base.html` carries no hardcoded navigation, its bar rendering the contributed navigation registry instead of literal links
   **And** `User.get_absolute_url()` and `LOGIN_REDIRECT_URL` stand unchanged, since `users:detail` and `users:redirect` are now core routes

4. **Given** `base.html` and the error templates
   **When** any combination is materialized
   **Then** they remain
   **And** the 403, 404 and 500 pages that extend `base.html` still render

5. **Given** any of the six combinations
   **When** it runs
   **Then** the admin renders, static files serve, the messages framework is available, and template rendering works
   **And** the navigation bar, the form styling and the user profile views are present too, because the interface mechanism is core rather than selectable

6. **Given** the immovable core
   **When** any of the six combinations is inspected
   **Then** it declares PostgreSQL as its deployed database, DRF with drf-spectacular, the Django admin, CORS handling, structlog, OpenTelemetry, environment-based configuration, static file serving and a uvicorn/gunicorn process
   **And** no feature toggle can be set to a value that removes any of them

## Tasks / Subtasks

- [ ] Task 1 — Audit and record the interface surface in the carrier as `core` (AC: #1, #2)
  - [ ] This discharges readiness warning W-1: the interface surface is described in the sources but never enumerated. It is an inventory of what is already in the tree, not a design exercise. No UX contract exists and none is to be invented (`epics.md:192-198`).
  - [ ] The enumeration is now a **`core` enumeration, not a feature's**. There is no `[features.ui]` and no `feature:ui` name — the interface mechanism is immovable core (AD-29, revision 3; FR-3), and AD-33 is retired, so there is no `src/features/`, no feature package and no third import root. Record the surface under `[dispositions]` as `core` and reference it from `[immovable_core]` (Task 6).
  - [ ] Record, item by item and with the reason each stays: `base.html`, the new `_navbar.html` and the navigation registry, `403.html`, `403_csrf.html`, `404.html`, `500.html`, the `account/` and `allauth/` template overrides, `templates/users/{user_detail,user_form}.html`, `users/{views,urls,forms,context_processors}.py`, `static/css/project.css`, `static/js/project.js`, `static/images/favicons/favicon.ico`. The audit results are pre-run in Source Tree below; verify each against the tree rather than trusting the table.
  - [ ] Record separately the **deleted** list — `templates/pages/home.html`, `templates/pages/about.html` and their two `TemplateView` routes in `src/config/urls.py` — with the reason: demonstration content, nothing in the product needs it, and a component that wants a landing page owns one. A deleted path is not a disposition; it must not appear in `[dispositions]` after Task 3, and input reconciliation would fail on a claim naming a path that no longer exists.
  - [ ] Record the one **decision this story must make and cannot inherit** (Source Tree, "Decision required"): what the navigation brand link points at once `home` is gone.

- [ ] Task 2 — Assert `django_service` is `core` in its entirety (AC: #2)
  - [ ] This is the story's spine and the reason its premise changed: with the interface mechanism core, **nothing moves out of `src/django_service/`**. The package's disposition is uniform and the story's job is to assert it, not to reshape it.
  - [ ] Confirm every tracked path under `src/django_service/` is claimed `core` in `accelerator.toml` — `users/{models,views,urls,forms,admin,adapters,apps,context_processors}.py`, `migrations/`, `api/`, `contrib/sites/`, the whole of `templates/` after Task 3's deletions, the whole of `static/`, and `__init__.py`.
  - [ ] The one genuine violation in the tree is **`src/django_service/users/tasks.py`**: it imports `from celery import shared_task`, which is `feature:celery` code inside the package this AD declares `core` in its entirety. Its own docstring calls it "a pointless Celery task to demonstrate usage" and nothing under `src/` calls it. AD-29 resolves it explicitly: it is **deleted rather than relocated**. Deleting a file requires the user's confirmation. Take `tests/integration/users/test_tasks.py` with it.
  - [ ] Do not create a `feature:*` claim, a marker, or a region anywhere under `src/django_service/` — Task 5's gate test refuses both the path-level and the sub-file route.

- [ ] Task 3 — Delete the `home` and `about` demonstration pages (AC: #1, #3)
  - [ ] Delete `src/django_service/templates/pages/home.html` and `pages/about.html`, and the now-empty `templates/pages/` directory. Deleting files requires the user's confirmation.
  - [ ] Delete their routes in `src/config/urls.py`: `path("", TemplateView.as_view(template_name="pages/home.html"), name="home")` at `:14` and the `about/` route at `:15-19`. Remove the now-unused `from django.views.generic import TemplateView` import at `:8` — no other route in the file uses it.
  - [ ] **`src/config/urls.py` gains no markers and becomes no region-bearing path.** Its UI routes are either core or deleted: the `users/` include at `:23` is now a `core` route, and `home`/`about` are gone. An earlier revision expected `feature:ui` regions here; that is wrong under revision 3 and Story 7.2's `[[regions]]` list does not name this file.
  - [ ] **`User.get_absolute_url()` (`src/django_service/users/models.py:19-26`) and `LOGIN_REDIRECT_URL` (`src/config/settings/base.py:140`) stand unchanged.** Both reverse `users:detail` / `users:redirect`, which are now `core` routes present in every combination. An earlier revision required them to be relocated or region-marked; do neither. Leave both files byte-identical in this respect.
  - [ ] Retarget the tests that reverse the deleted routes rather than deleting them: `tests/integration/test_request_logging.py` calls `reverse("home")` at `:64`, `:76`, `:89`, `:101`, `:113`, `:135` and `reverse("about")` at `:90`; `tests/integration/test_template_rendering.py` has `test_home` (`:30-32`) and `test_about` (`:34-36`). The logging tests need any resolvable `core` route that renders — the admin index or a profile route — and their assertions about `request_id`/`trace_id` correlation must survive the change untouched. The two template-rendering tests cover pages that no longer exist; replace them with equivalents over `core` templates rather than dropping the coverage.
  - [ ] Do not use conditional imports, settings-module inheritance or `try/except ImportError` anywhere in this task. AD-24 forbids all three, and a URLconf that conditionally includes a module is exactly the mechanism it names.

- [ ] Task 4 — Replace `base.html`'s hardcoded navigation with the registry (AC: #3, #4, #5)
  - [ ] `src/django_service/templates/base.html` hardcodes four reversals inside its navbar: `{% url 'home' %}` on the brand link at **`:71`**, `{% url 'home' %}` again at **`:75`**, `{% url 'about' %}` at **`:78`** and `{% url 'users:detail' request.user.username %}` at **`:83`**. Two of those routes are being deleted by Task 3. Replace the whole `<nav>` block (`:60-104`) with `{% include "_navbar.html" %}`.
  - [ ] Create `src/django_service/templates/_navbar.html` (NEW, `core`). It renders the **navigation registry** rather than literal links: it iterates the registry, filters each entry by its optional permission against `request.user`, reverses each entry's URL *name*, and escapes each label. No entry carries raw HTML and no link in this template is hardcoded.
  - [ ] Create the registry itself in `django_service` — AD-8: *"`django_service` owns a navigation registry, contributed to exactly like `INSTALLED_APPS` — append only, in adopted-app-list order. An entry is data, never markup: a label, a URL name, and an optional permission the renderer filters on."* It is permitted on the closed contributable surface where `MIDDLEWARE` and `AUTHENTICATION_BACKENDS` are refused, for a reason that must hold in the implementation: **it confers presentation and never authorization**, labels are auto-escaped, and no entry carries raw HTML.
  - [ ] Seed the registry with the base's own entries, which are what the navbar renders today minus the deleted pages: the authenticated profile link (`users:detail`), sign-out (`account_logout`), sign-in (`account_login`), and sign-up (`account_signup`) gated on `ACCOUNT_ALLOW_REGISTRATION`. `src/django_service/users/context_processors.py` (`allauth_settings`, registered at `base.py:224`) supplies that flag and **stays `core`** — it is registered unconditionally in every combination.
  - [ ] **Every registered URL name must resolve in the URLconf, refused as `ImproperlyConfigured` at stage 2** — the stage that has a resolved URLconf (AD-8, AD-26). An app that contributes a link to a route it forgot to mount fails at startup rather than rendering a 500 on whatever page carries the navigation bar. `src/config/startup/` does not exist until Epic 4; if Story 4.3 has not landed, record the refusal as owed and name the story that owes it rather than implementing a second refusal site.
  - [ ] The **contribution and merge** half of the registry — an adopted app appending its own entries through its contribution module — is AD-8's composition step and belongs to Epic 9, Story 9.4. What lands here is the registry, its renderer, and the base's own entries. Traceability marker, not an acceptance condition for this story.
  - [ ] Keep `403.html`, `403_csrf.html`, `404.html`, `500.html` unchanged; they extend `base.html` and use only `{% block title %}` / `{% block content %}`. After this task a 404 renders with no `NoReverseMatch`, which is what AD-30's smoke check asserts in every combination.
  - [ ] Do **not** guard the navbar with `{% if %}` on a setting, and do not introduce a feature flag anywhere in this task. There is no `ui` feature to switch on, and a present-but-disabled shape is what FR-28 and Story 7.6 forbid.
  - [ ] `base.html`'s Bootstrap CSS and JS load from `cdnjs.cloudflare.com` and stay `core` with the rest of the form styling. Record the external-fetch observation for the local smoke check (FR-33 runs with no external service): it is a rendering concern for a page fetched from a browser, not a boot-time network reach, and FR-23's no-network-at-boot rule is unaffected. Do not silently vendor or remove it under this story.

- [ ] Task 5 — The AD-29 gate test (AC: #2)
  - [ ] Add `tests/integration/materializer/test_django_service_is_core.py` (NEW), `@pytest.mark.integration`: load the carrier and assert **no** `[dispositions]` entry, glob or region under `src/django_service/` resolves to a `feature:*` disposition. Assert over resolved dispositions, not over the literal declaration text, so a glob like `src/**/templates/pages/*` cannot slip through.
  - [ ] Assert the complement too: every tracked path under `src/django_service/` resolves to exactly `core`. `machinery` and `tenant` are also violations there.
  - [ ] Extend the carrier's `[[regions]]` reconciliation to reject a region whose `path` is under `src/django_service/` — AD-29 bars feature dispositions at path level, and a marker there would reintroduce combination-varying surface inside the guaranteed package by the sub-file route.

- [ ] Task 6 — Enumerate the guaranteed surface and the immovable core in the carrier (AC: #6)
  - [ ] AD-29: *"`accelerator.toml` enumerates the guaranteed surface explicitly; anything inside `django_service` not enumerated is internal and may change without a version bump."* Add `[guaranteed_surface]` listing the modules and names reusable apps may import — at minimum `django_service.users.models.User` (`AUTH_USER_MODEL`) and `django_service.__api_version__`. `__api_version__` does not exist yet (AD-5, Epic 9); declare the slot and record the forward reference.
  - [ ] Add `[immovable_core]` enumerating AC #6's nine items so the assertion has a single declared source: PostgreSQL as the deployed database, DRF with drf-spectacular, the Django admin, CORS handling, structlog, OpenTelemetry, environment-based configuration, static file serving, and a uvicorn/gunicorn process. Add the **interface mechanism** as a tenth (FR-3, amended): template loading, `base.html`, `_navbar.html` and the navigation registry, the error templates, form styling, static-file serving and the user profile views.
  - [ ] Add a gate test asserting no `[features.*]` list claims any package or path backing an `[immovable_core]` item — that is what makes "no feature toggle can be set to a value that removes any of them" checkable rather than asserted.
  - [ ] The runtime half of AC #6 — the `core`-disposed immovable-core assertion suite that runs inside every combination's gate and is never pruned (AD-30) — belongs to Epic 8. **Traceability marker, not an acceptance condition for this story.** What lands here is the declaration it will assert against.

- [ ] Task 7 — Tests (AC: #3, #4, #5, and regression cover for the deletions)
  - [ ] `tests/integration/test_template_rendering.py` (UPDATE, exists today): replace `test_home` (`:30-32`) and `test_about` (`:34-36`), whose pages no longer exist, with assertions over `core` templates. Assert the 403, 404 and 500 pages render end to end with no `NoReverseMatch` now that `base.html` reverses nothing itself.
  - [ ] Add an assertion that `_navbar.html` renders from the registry: an entry whose permission the user lacks is filtered out, a label containing markup is escaped, and a registry with no entries renders an empty bar rather than raising.
  - [ ] Add an assertion that the admin index renders for a staff user and that `django.contrib.messages` round-trips through `base.html`'s message loop (AC #5), mirroring the AD-30 smoke check at reference-application scale. Assert `{% static %}` resolves.
  - [ ] `tests/integration/test_request_logging.py` (UPDATE): retarget its seven `reverse("home")` / `reverse("about")` calls (`:64`, `:76`, `:89`, `:90`, `:101`, `:113`, `:135`) at a `core` route. Its assertions about `request_id` and `trace_id` correlation are unchanged in meaning — do not weaken them to make the retarget easier.
  - [ ] **No test moves and none is re-dispositioned to a feature.** `tests/integration/users/{test_views,test_forms,test_admin,test_models,test_api_views,test_api_openapi}.py` and `tests/unit/users/{test_urls,test_api_urls,test_adapters}.py` all cover `core` surface and all stay `core` where they are. Only `tests/integration/users/test_tasks.py` leaves, with the `tasks.py` it covers.
  - [ ] `pixi run ci` exits 0, with coverage ≥90% including templates. Deleting `pages/home.html` and `pages/about.html` removes measured templates along with the tests that covered them, which is the correct shape; answer any residual shortfall with tests, never with an omit entry (CG-1).

## Dev Notes

### Architecture Constraints

**AD-29 — `django_service`'s guaranteed surface is the intersection across all combinations.** Binding rule: *"No `feature:*` disposition may be applied to any path inside `src/django_service/`; it is `core` in its entirety, and a gate test asserts that. `accelerator.toml` enumerates the guaranteed surface explicitly; anything inside `django_service` not enumerated is internal and may change without a version bump. **The user-interface mechanism is part of that core, not a selectable feature** (revision 3). `base.html`, `_navbar.html` and the navigation registry, the 403/404/500 templates, the form-styling configuration, static-file serving and the user profile views are all `core` and present in every combination. ... The `home` and `about` pages are **deleted** rather than made core ... `User.get_absolute_url()` (`src/django_service/users/models.py:19-26`) and `LOGIN_REDIRECT_URL` (`src/config/settings/base.py:140`) reverse `users:detail` and `users:redirect`, which are now `core` routes present everywhere, so both stand unchanged. **`base.html` still carries no hardcoded navigation.** Its navigation bar is `{% include "_navbar.html" %}`, and `_navbar.html` renders the navigation registry (AD-8) rather than literal links. ... The four reversals at `base.html:71`, `:75`, `:78` and `:83` are replaced by that mechanism. **`src/django_service/users/tasks.py` violates this rule today** ... it is deleted rather than relocated."*

**Prevents:** *"a reusable app importing a module present in some combinations and absent from others, with a combination-invariant version constant that cannot express the difference."*

**Why the premise moved, in case a reader meets an older revision of this story.** Revision 2 had a `feature:ui` disposition and required the user-facing surface to move out of `django_service` into a feature root (AD-33). Revision 3 removes the problem instead. The Django admin is immovable core (FR-1) and needs the template loader, `base.html`, the error templates, static files and whitenoise, so that stack was already present in every combination. Measured against this tree, `feature:ui` could have removed about **16 KB of templates, 8 KB of static assets and roughly 100 lines of Python — and no dependency at all**, because `templates/allauth/elements/field.html` and `fields.html` use `crispy` to render the FR-4 interactive sign-in flow. Carrying a feature axis, a feature root and six extra combinations to remove that much was not a trade worth making. **AD-33 is retired**: there is no `src/features/`, no `django_ui` or `django_storage` package, and no third import root. Anything in an older note that says otherwise is wrong.

**AD-8 — the navigation registry.** *"`django_service` owns a navigation registry, contributed to exactly like `INSTALLED_APPS` — append only, in adopted-app-list order. An entry is data, never markup: a label, a URL name, and an optional permission the renderer filters on. This is the one contributable key rendered on every page, so it is permitted where `MIDDLEWARE` and `AUTHENTICATION_BACKENDS` are refused for a reason that holds here: it confers presentation and never authorization, labels are auto-escaped, and no entry carries raw HTML. Every registered URL name must resolve in the URLconf, refused as `ImproperlyConfigured` at stage 2 — the stage that has a resolved URLconf (AD-26). An app that contributes a link to a route it forgot to mount fails at startup rather than rendering a 500 on whatever page carries the navigation bar."* The registry survives revision 3 on its own merit: it is what makes navigation extensible by adopted apps at all, and it removes `NoReverseMatch` structurally — an entry that was never registered is never reversed.

**AD-24 — regions, and nothing else.** This story adds **no** regions. `src/config/urls.py` is not a region-bearing path: its `users/` include is `core` and its `home`/`about` routes are deleted. `src/config/settings/base.py:140` gets no marker either. Where any later story does need sub-file removal, it uses paired `feature:<name>` / `/feature:<name>` line comments declared in `accelerator.toml` — **not** conditional imports, **not** settings-module inheritance, **not** `try/except ImportError`, and not an `{% if %}` on a setting inside a template.

**AD-5 — `django_service` is public API.** *"Moving a module within the guaranteed surface (AD-29), changing `AUTH_USER_MODEL`, or renaming a guaranteed setting is a breaking change. `django_service.__api_version__` is a single integer, bumped by hand on any breaking change and on the removal of any guaranteed surface."* Nothing moves in this story, so no relocation triggers a bump. Deleting `users/tasks.py` does: check whether it is enumerated in `[guaranteed_surface]` before removing it. `__api_version__` does not exist yet (Epic 9) — record the obligation rather than inventing the constant.

**AD-4 — dependency direction.** `django_service` may never import a tenant app, and a feature's code may never import another feature's. With no feature packages left, the live check here is that nothing under `src/django_service/` imports a feature's code — which is exactly what `users/tasks.py` does today, and why it goes.

**AD-30 — what the smoke check will assert.** *"a persona completes an interactive sign-in and reaches a rendered admin index ... and one rendered 404."* Every combination. `base.html` currently reverses `home` and `about`, and Task 3 deletes both routes — if the navbar is not replaced in the same change, **every** page extending `base.html` raises `NoReverseMatch`, including that 404. The two halves of this story are not separable.

**FR-3, amended.** *"The rendering stack — template loading, `base.html`, the navigation bar and its contribution registry, the error templates, form styling, static-file serving and the user profile views — is present in every component and is not selectable."* Its testable consequences include: `base.html` contains no hardcoded navigation links; the navigation bar renders the contributed registry, so an adopted app can appear in it (FR-54); and the `home` and `about` demonstration pages are removed rather than made core.

**Project standards.** Pixi is the only runner. Python 3.14 only. conda-forge only. PEP 8 / 120 / full type hints / Google docstrings. Never `print()`, never stdlib `logging`, never bare `except:`, never `except X: pass`. Deleting any file needs the user's confirmation.

### Source Tree — files to touch

**Decision required — one, and no source document answers it. Make it, record it in `accelerator.toml`, and do not leave it implicit.**

1. **What does the navigation brand link point at once `home` is gone?** `base.html:71` reverses `{% url 'home' %}` on the `navbar-brand` anchor, and Task 3 deletes that route. The brand link is not a registry entry — the registry is the *list* of navigation items, and the brand is the bar's own identity. Coherent answers: point it at `/` and accept that the base ships no route there (a component that wants a landing page mounts one); point it at the authenticated landing target, which is what `LOGIN_REDIRECT_URL` already names (`users:redirect`, `base.py:140`); or render the brand as plain text with no anchor at all. Whichever is chosen, it must reverse a route that resolves in **every** combination, because a `NoReverseMatch` here breaks the 404 page that AD-30's smoke check renders.

**Not a decision any more.** Revision 2 asked where "a feature-owned location" is, and what happens to the allauth template overrides. Both questions dissolve. There is no feature-owned location — AD-33 is retired and no feature has a code surface. And `templates/account/base_manage_password.html`, `templates/allauth/elements/{alert,badge,button,field,fields}.html` and `templates/allauth/layouts/{entrance,manage}.html` are simply `core`: they are crispy/Bootstrap overrides that render the FR-4 interactive sign-in flow, which AD-30's smoke check exercises in every combination.

| Path | NEW/UPDATE/DELETE | What changes |
|---|---|---|
| `accelerator.toml` | UPDATE | Claim every path under `src/django_service/` as `core`; add `[guaranteed_surface]` and `[immovable_core]` (Task 6), and record the deleted-path list as deletions rather than dispositions. **No `[features.ui]`, no `feature:ui` name, no `src/features/` root, and no new `[[regions]]` from this story.** Preserve Stories 7.1–7.3 content. |
| `src/django_service/templates/base.html` | UPDATE | **Today:** full page chrome — CDN Bootstrap CSS/JS, favicon, a `<nav>` block at `:60-104` reversing `home` (`:71` brand, `:75`), `about` (`:78`) and `users:detail` (`:83`), an `ACCOUNT_ALLOW_REGISTRATION` conditional around the sign-up link (`:90-95`), the messages loop, and the `css`/`javascript`/`body`/`main`/`content`/`modal`/`inline_javascript` block skeleton. **Changes:** the whole `<nav>` block at `:60-104` becomes `{% include "_navbar.html" %}`, and no `{% url %}` for a navigation target remains in this file. **Preserve:** the block names (the error templates extend them), the favicon link, `{% load static i18n %}`, the messages loop, and the CDN Bootstrap links — all `core`. |
| `src/django_service/templates/_navbar.html` | NEW | `core`. Renders the navigation registry: iterate entries, filter by each entry's optional permission against `request.user`, reverse each entry's URL *name*, auto-escape each label. No hardcoded link, no raw HTML, and no `{% if %}` on a feature setting. An empty registry renders an empty bar rather than raising. |
| The registry module in `src/django_service/` | NEW | `core`. Holds the ordered, append-only registry and the base's own seed entries (`users:detail`, `account_logout`, `account_login`, and `account_signup` gated on `ACCOUNT_ALLOW_REGISTRATION`), plus whatever exposes it to the template — a context processor or a template tag, registered unconditionally. Its exact module path is this story's to choose inside `django_service`; AD-8 fixes the shape, not the filename. |
| `src/django_service/templates/{403,403_csrf,404,500}.html` | keep | Unchanged, `core`. They use only `{% block title %}` and `{% block content %}`. Verified. |
| `src/django_service/templates/pages/{home,about}.html` | DELETE | Demonstration content. The now-empty `templates/pages/` goes with them. Deleting files requires the user's confirmation. |
| `src/django_service/templates/users/{user_detail,user_form}.html` | keep | `core`. `user_form.html` loads `crispy_forms_tags`; both extend `base.html`. The user profile views are core (FR-3, amended), so their templates are too. |
| `src/django_service/templates/account/`, `templates/allauth/` | keep | `core`. Form styling for the FR-4 sign-in flow, rendered in every combination. |
| `src/django_service/users/views.py` | keep | `core`, unchanged. 52 lines; `UserDetailView`, `UserUpdateView`, `UserRedirectView` behind `LoginRequiredMixin`. Revision 2 moved these out; revision 3 does not. |
| `src/django_service/users/urls.py` | keep | `core`, unchanged. 12 lines; `app_name = "users"`, three routes. `users:detail` and `users:redirect` are core routes. |
| `src/django_service/users/forms.py` | keep | `core`, unchanged and unsplit. `UserAdminChangeForm` / `UserAdminCreationForm` are imported by `admin.py`; `UserSignupForm` / `UserSocialSignupForm` are named at `base.py:348,352`. All four are core. |
| `src/django_service/users/context_processors.py` | keep | `core`, unchanged. 8 lines; supplies `ACCOUNT_ALLOW_REGISTRATION`, which the registry's sign-up entry is gated on. Registered unconditionally at `base.py:224`. |
| `src/django_service/users/tasks.py` | DELETE | Imports `from celery import shared_task` — `feature:celery` code inside the package AD-29 declares `core` in its entirety. Nothing under `src/` calls it; its docstring calls it a demonstration. Deleted, not relocated. Deleting a file requires the user's confirmation. Take `tests/integration/users/test_tasks.py` with it. |
| `src/django_service/users/models.py` | keep | **Unchanged.** `get_absolute_url()` at `:19-26` reverses `users:detail`, now a `core` route present everywhere. Revision 2 required this to be relocated or region-marked; do neither. Epic 2 adds `idp_subject` here — do not pre-empt it. |
| `src/django_service/users/{admin,adapters,apps}.py`, `api/`, `migrations/`, `contrib/sites/` | keep | `core`. `admin.py` imports the two admin forms and applies `secure_admin_login` under `DJANGO_ADMIN_FORCE_ALLAUTH`. |
| `src/django_service/static/**` | keep | `core`. `css/project.css`, `js/project.js`, `images/favicons/favicon.ico`, `fonts/.gitkeep`. Static-file serving is immovable core. |
| `src/config/urls.py` | UPDATE | **Today:** `home` (`:14`) and `about` (`:15-19`) `TemplateView`s, the admin mount (`:21`), the `users/` include (`:23`), the `accounts/` allauth include (`:24`), media static, the API router, `obtain_auth_token` (Epic 2 removes it), spectacular schema/docs, and DEBUG-only error-page and debug-toolbar routes. **Changes:** delete the `home` and `about` routes and the now-unused `from django.views.generic import TemplateView` import at `:8`. **Preserve:** everything else, the `users/` include included — it is a `core` route. **This file gains no markers and is not region-bearing**; Story 7.2's `[[regions]]` array does not name it. |
| `src/config/settings/base.py` | keep | **Unchanged by this story.** `LOGIN_REDIRECT_URL` (`:140`) stands, the `allauth_settings` context-processor entry (`:224`) stands, and the crispy entries at `:105-106` stay `core`. Revision 2 put three `feature:ui` regions here; revision 3 puts none. Story 7.2 owns the markers this file does carry. |
| `src/config/startup/` | traceability | The stage-2 refusal for an unresolvable registry URL name lands here (AD-8, AD-26). The directory does not exist until Epic 4; if Story 4.3 has not landed, record the refusal as owed and name the owing story rather than opening a second refusal site. |
| `tests/integration/test_template_rendering.py` | UPDATE | Exists. Replace `test_home` (`:30-32`) and `test_about` (`:34-36`) with `core`-template equivalents; add the navbar-registry and admin/messages/`{% static %}` assertions. |
| `tests/integration/test_request_logging.py` | UPDATE | Exists. Retarget six `reverse("home")` calls (`:64`, `:76`, `:89`, `:101`, `:113`, `:135`) and one `reverse("about")` (`:90`) at a `core` route. Assertions unchanged in meaning. |
| `tests/integration/users/{test_views,test_forms,test_admin,test_models,test_api_views,test_api_openapi}.py`, `tests/unit/users/{test_urls,test_api_urls,test_adapters}.py` | keep | All `core`, all stay where they are. Nothing moves and nothing is re-dispositioned. |
| `tests/integration/users/test_tasks.py` | DELETE | Goes with the `tasks.py` it covers. |
| `tests/integration/materializer/test_django_service_is_core.py` | NEW | The AD-29 gate test. |

**Audit results, verified 2026-08-15 by reading the tree.** `src/django_service/templates/` contains exactly 17 files: `403.html`, `403_csrf.html`, `404.html`, `500.html`, `base.html`, `account/base_manage_password.html`, `allauth/elements/{alert,badge,button,field,fields}.html`, `allauth/layouts/{entrance,manage}.html`, `pages/{about,home}.html`, `users/{user_detail,user_form}.html`. Two are deleted here and one is added, leaving 16. `src/django_service/static/` contains `css/project.css`, `js/project.js`, `images/favicons/favicon.ico`, `fonts/.gitkeep` — all `core`.

### Testing Requirements

- Integration: `tests/integration/test_template_rendering.py` (update), `tests/integration/test_request_logging.py` (update) and `tests/integration/materializer/test_django_service_is_core.py` (new), every test `@pytest.mark.integration`. Real template rendering, real URL resolution.
- **There is no UI-absent state to simulate.** The interface mechanism is present in all six combinations, so these assertions run against the reference application as it stands. What varies across combinations is `celery`, `redis` and `storage`, and none of them touches a template. Revision 2 asked for an alternate `ROOT_URLCONF` under `override_settings` to fake the feature's absence; that scaffolding is not needed and must not be written.
- Assert specifically: a 404 renders end to end with no `NoReverseMatch` now that `base.html` reverses nothing itself; a 403 and a 500 render; the admin index renders for a staff user; `django.contrib.messages` is in `INSTALLED_APPS` and a message round-trips through `base.html`'s loop; `{% static %}` resolves.
- Assert the registry's three renderer properties directly: an entry whose permission the user lacks is filtered out, a label containing markup is escaped rather than emitted, and an empty registry renders an empty bar rather than raising.
- Retargeted tests keep their existing assertions; do not weaken `test_request_logging.py`'s `request_id`/`trace_id` correlation checks to make the retarget easier.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` (AD-20). Template coverage is the orphan detector — a template left with no test reports zero and the gate fails. That is correct behaviour; answer it with tests, never with an omit entry (CG-1). Deleting `pages/home.html` and `pages/about.html` removes measured templates along with the tests that covered them, which is the correct shape, and `_navbar.html` arrives with the tests that measure it.
- Test disposition: tests carry the disposition of what they cover (spine Consistency Conventions). Every test named in this story covers `core` surface and is therefore `core` and never pruned. The one exception leaves the tree entirely: `tests/integration/users/test_tasks.py` is deleted with `tasks.py`.

#### Project Structure Notes

- **No variance.** Revision 2 recorded two, and revision 3 dissolves both. There is no new directory for feature-owned code — AD-33 is retired and no feature has a code surface — and `src/config/urls.py` does not become region-bearing, because its `home`/`about` routes are deleted and its `users/` include is `core`. Everything this story adds (`_navbar.html`, the registry module) lands inside `src/django_service/`, which the Structural Seed already names.
- `src/django_service/users/tasks.py` is a pre-existing AD-29 violation in the tree today: `feature:celery` code inside the package AD-29 declares `core` in its entirety. It is not called by anything in `src/`; its only consumer is `tests/integration/users/test_tasks.py`. It is the one path in the package whose disposition cannot be satisfied by claiming it `core`, which is why AD-29 resolves it by deletion.
- The hatch wheel config lists `packages = [ "src/config", "src/django_service" ]` (`pyproject.toml:127`) and **needs no change** — this story creates no new top-level package. Story 1.6 (AD-7) converts that list to a `sources` remapping declaring `src/` and `src/django_apps/`; either shape already covers what lands here.
- Story ordering: Task 5's gate test reads the carrier, so Story 7.1 must have created it. Task 4's stage-2 refusal needs `src/config/startup/`, which is Epic 4's. Neither blocks the rest of the story — record what is owed and proceed.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-5]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-4]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-30]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-6]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-8] — the navigation registry
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Revision 3 — the interface mechanism becomes core] — why this story's premise inverted
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-33] — retired; there is no `src/features/`
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.4]
- [Source: _bmad-output/planning-artifacts/epics.md#UX Design Requirements] — lines 192-198: no UX contract exists and none is to be invented
- [Source: _bmad-output/planning-artifacts/implementation-readiness-report-2026-08-15.md#W-1] — the enumeration criterion this story discharges
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-1]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-3]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#SC-7]
- Repository, verified 2026-08-15: `src/django_service/templates/base.html:60-104,71,75,78,83`; `src/django_service/users/models.py:19-26`; `src/django_service/users/tasks.py`; `src/django_service/users/{views,urls,forms,context_processors,admin}.py`; `src/config/urls.py:8,14,15-19,23`; `src/config/settings/base.py:105-106,140,224,348,352`; `tests/integration/test_request_logging.py:64,76,89,90,101,113,135`; `tests/integration/test_template_rendering.py:30-32,34-36`; `pyproject.toml:127`; full `templates/` (17 files) and `static/` listings

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
