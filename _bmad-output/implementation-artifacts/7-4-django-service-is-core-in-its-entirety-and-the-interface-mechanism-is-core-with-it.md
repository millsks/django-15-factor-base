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

**AD-29 — `django_service`'s guaranteed surface is the intersection across all combinations.** Binding rule: *"No `feature:*` disposition may be applied to any path inside `src/django_service/`; it is `core` in its entirety, and a gate test asserts that. Surface that genuinely belongs to the server-rendered UI feature — user-facing page templates, form styling, user-facing views and forms — moves out of `django_service` into a feature-owned location before that feature is extracted. Error templates and `base.html` stay, because the admin and the error handlers need them in every combination. `accelerator.toml` enumerates the guaranteed surface explicitly; anything inside `django_service` not enumerated is internal and may change without a version bump."*

**Prevents:** *"a reusable app importing a module present in six combinations and absent from six, with a combination-invariant version constant that cannot express the difference; and a wholesale `feature:ui` disposition on `templates/` removing `base.html`, which the 403/404/500 pages extend, in the six combinations where FR-3 explicitly requires template rendering to work."* The second half is the trap this story exists to avoid: `feature:ui` on `src/django_service/templates/**` is the obvious move and it is wrong.

**AD-24 — regions, and nothing else.** The `core` paths this story touches (`src/config/urls.py`, `src/config/settings/base.py`) carry UI surface that must be removable. It is removed by paired `# feature:ui` / `# /feature:ui` line comments declared in `accelerator.toml` — **not** by conditional imports, **not** by settings-module inheritance, **not** by `try/except ImportError`, and not by an `{% if %}` on a setting inside a template.

**AD-5 — `django_service` is public API.** *"Moving a module within the guaranteed surface (AD-29), changing `AUTH_USER_MODEL`, or renaming a guaranteed setting is a breaking change. `django_service.__api_version__` is a single integer, bumped by hand on any breaking change and on the removal of any guaranteed surface."* Moving `users/views.py` and `users/urls.py` out of the package is exactly such a removal. If either is enumerated in `[guaranteed_surface]`, the version bumps. `__api_version__` does not exist yet — record the obligation rather than inventing the constant.

**AD-4 — dependency direction.** The UI feature's code may import `django_service`; `django_service` may never import the UI feature; a feature's code may never import another feature's. After the move, verify no `core` module imports the UI feature's package.

**AD-30 — what the smoke check will assert.** *"a persona completes an interactive sign-in and reaches a rendered admin index ... and one rendered 404."* Every combination. If `base.html` still reverses `users:detail` after this story, six combinations fail that check in Epic 8. Fix it here.

**FR-3.** *"The Django admin is orthogonal to the server-rendered UI feature; omitting the UI feature removes only the end-user surface."*

**Project standards.** Pixi is the only runner. Python 3.14 only. conda-forge only. PEP 8 / 120 / full type hints / Google docstrings. Never `print()`, never stdlib `logging`, never bare `except:`, never `except X: pass`. Deleting any file needs the user's confirmation.

### Source Tree — files to touch

**Decisions required — no source document answers these; make them, record them in `accelerator.toml`, and do not leave them implicit.**

1. **Where is "a feature-owned location"?** The Structural Seed names `src/config/`, `src/django_service/`, `src/django_apps/`, `tools/materializer/` and `tests/` — and no home for a feature's own code. Constraints the answer must satisfy: not inside `src/django_service/` (AD-29); not inside `src/django_apps/`, which is `tenant` and therefore *never judged and never pruned* (AD-2, AD-6) — a feature that lands there cannot be removed at all; importable under the AD-7 hatch `sources` remapping of `src/`; disposable as `feature:ui` in its entirety. A new top-level package under `src/` (for example `src/webui/`, installed as `webui`) satisfies all four. Whatever is chosen, the other three features will need the same shape.
2. **What happens to the allauth template overrides?** `templates/account/base_manage_password.html`, `templates/allauth/elements/{alert,badge,button,field,fields}.html` and `templates/allauth/layouts/{entrance,manage}.html` are crispy/Bootstrap-styled overrides of allauth's own templates. They are "form styling", which AD-29 lists as UI-owned — but interactive IdP sign-in is `core` (FR-4, FR-7, and AD-30's smoke check renders a sign-in in every combination), so allauth pages must render in all twelve. Two coherent answers: keep the overrides `core` (allauth surface, not end-user page surface), or delete the overrides and let allauth's built-in templates render, moving only the styling. Do not split them across dispositions.

| Path | NEW/UPDATE/MOVE | What changes |
|---|---|---|
| `accelerator.toml` | UPDATE | `[features.ui]` enumeration, the stays list, `[guaranteed_surface]`, `[immovable_core]`, new `[[regions]]` for `src/config/urls.py` and `base.py:140`. Preserve Stories 7.1–7.3 content. |
| `src/django_service/templates/base.html` | UPDATE | **Today:** full page chrome — CDN Bootstrap CSS/JS, favicon, a navbar reversing `home`, `about` and `users:detail`, an `ACCOUNT_ALLOW_REGISTRATION` conditional around the sign-up link, the messages loop, and the `css`/`javascript`/`body`/`main`/`content`/`modal`/`inline_javascript` block skeleton. **Changes:** navbar and CDN styling move to a UI-feature template overriding an empty block. **Preserve:** the block names (the error templates and any future template extend them), the favicon link, `{% load static i18n %}`, and the messages loop. |
| `src/django_service/templates/{403,403_csrf,404,500}.html` | keep | Unchanged. They use only `{% block title %}` and `{% block content %}`. Verified. |
| `src/django_service/templates/pages/{home,about}.html` | MOVE | To the UI feature location. Referenced by `src/config/urls.py` `TemplateView`s. |
| `src/django_service/templates/users/{user_detail,user_form}.html` | MOVE | `user_form.html` loads `crispy_forms_tags`; both extend `base.html`. |
| `src/django_service/templates/account/`, `templates/allauth/` | decide | See "Decisions required" #2. |
| `src/django_service/users/views.py` | MOVE | 52 lines; `UserDetailView`, `UserUpdateView`, `UserRedirectView`, all end-user pages behind `LoginRequiredMixin`. |
| `src/django_service/users/urls.py` | MOVE | 12 lines; `app_name = "users"`, three routes. |
| `src/django_service/users/forms.py` | UPDATE + split | 40 lines. `UserAdminChangeForm` / `UserAdminCreationForm` are imported by `admin.py` → stay `core`. `UserSignupForm` / `UserSocialSignupForm` are named in `base.py:348,352` → decide with #2. |
| `src/django_service/users/context_processors.py` | MOVE | 8 lines; exists only for the navbar's registration link. Registered at `base.py:224`. |
| `src/django_service/users/tasks.py` | MOVE or delete | Imports `celery`. `feature:celery` code inside `django_service`, which AD-29 forbids. Deletion requires user confirmation. |
| `src/django_service/users/models.py` | UPDATE | **Today:** `User(AbstractUser)` with `name`, `first_name`/`last_name` nulled, and `get_absolute_url()` reversing `users:detail` (`:24-31`). **Changes:** the `get_absolute_url` route reference only. **Preserve:** the model fields and `AUTH_USER_MODEL` identity — Epic 2 adds `idp_subject` here; do not pre-empt it. |
| `src/django_service/users/{admin,adapters,apps}.py`, `api/`, `migrations/`, `contrib/sites/` | keep | `core`. `admin.py` imports the two admin forms and applies `secure_admin_login` under `DJANGO_ADMIN_FORCE_ALLAUTH`. |
| `src/django_service/static/css/project.css`, `static/js/project.js` | MOVE | Referenced only from `base.html`'s UI blocks. |
| `src/django_service/static/images/favicons/favicon.ico` | keep | `base.html` head, every combination. |
| `src/config/urls.py` | UPDATE | **Today:** `home` and `about` `TemplateView`s, the admin mount, `users/` include, `accounts/` allauth include, media static, the API router, `obtain_auth_token` (Epic 2 removes it), spectacular schema/docs, and DEBUG-only error-page and debug-toolbar routes. **Changes:** `feature:ui` markers around the `home`, `about` and `users/` entries. **Preserve:** the admin mount, the allauth include, the API block and the DEBUG error-page routes. |
| `src/config/settings/base.py` | UPDATE | `feature:ui` region around `LOGIN_REDIRECT_URL` (`:140`) with a `core` default; `feature:ui` region around the `django_service.users.context_processors.allauth_settings` entry (`:224`); the UI app label joins the `feature:ui` installed-app region at `:105-106`. Preserve everything else; Story 7.2 already placed markers in this file. |
| `tests/integration/test_template_rendering.py` | UPDATE | Exists. Extend with UI-absent rendering assertions. |
| `tests/integration/users/{test_views,test_forms,test_tasks}.py`, `tests/unit/users/test_urls.py` | MOVE | Follow the code they cover; disposition `feature:ui` (or `feature:celery` for `test_tasks.py`). |
| `tests/integration/materializer/test_django_service_is_core.py` | NEW | The AD-29 gate test. |

**Audit results, verified 2026-08-15 by reading the tree.** `src/django_service/templates/` contains exactly 21 files: `403.html`, `403_csrf.html`, `404.html`, `500.html`, `base.html`, `account/base_manage_password.html`, `allauth/elements/{alert,badge,button,field,fields}.html`, `allauth/layouts/{entrance,manage}.html`, `pages/{about,home}.html`, `users/{user_detail,user_form}.html`. `src/django_service/static/` contains `css/project.css`, `js/project.js`, `images/favicons/favicon.ico`, `fonts/.gitkeep`.

### Testing Requirements

- Integration: `tests/integration/test_template_rendering.py` (extend) and `tests/integration/materializer/test_django_service_is_core.py` (new), every test `@pytest.mark.integration`. Real template rendering, real URL resolution.
- The UI-absent assertions must simulate absence by configuration (an alternate `ROOT_URLCONF` without the `feature:ui` routes, `override_settings`) rather than by deleting files — the reference application must stay runnable and gateable throughout (AD-3). The file-deletion form of this assertion is Epic 8's, against a real materialized combination.
- Assert specifically: a 404 renders end to end with no `NoReverseMatch`; a 403 and a 500 render; the admin index renders for a staff user; `django.contrib.messages` is in `INSTALLED_APPS` and a message round-trips through `base.html`'s loop; `{% static %}` resolves.
- Moved tests keep their existing assertions; do not weaken them to make the move easier.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` (AD-20). Template coverage is the orphan detector — a template moved without its test reports zero and the gate fails. That is correct behaviour; answer it with tests, never with an omit entry (CG-1).
- Test disposition: tests carry the disposition of what they cover (spine Consistency Conventions). UI tests become `feature:ui` and are pruned with the feature; the admin, model, API and adapter tests stay `core`.

#### Project Structure Notes

- **Variance:** the Structural Seed has no directory for a feature's own code. This story must create one and it becomes the pattern for `celery`, `redis` and `storage`. Record the decision in `accelerator.toml` so Stories 7.5 and 7.7 inherit it rather than re-deciding.
- **Variance:** `src/config/urls.py` becomes a region-bearing `core` path, which AD-24's three-path list does not anticipate. Story 7.2's reconciler must already treat `[[regions]]` as an open array; confirm it does before adding the fourth and fifth paths.
- `src/django_service/users/tasks.py` is a pre-existing AD-29 violation in the tree today: `feature:celery` code inside the package AD-29 declares `core` in its entirety. It is not called by anything in `src/`; its only consumer is `tests/integration/users/test_tasks.py`.
- The hatch wheel config lists `packages = [ "src/config", "src/django_service" ]` (`pyproject.toml:127`). A new top-level package under `src/` needs that list extended — or, if Story 1.6 (AD-7) has landed, the `sources` remapping of `src/` already covers it and no per-package edit is needed, which is the directory-level property AD-7 exists to deliver.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-5]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-4]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-30]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-6]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.4]
- [Source: _bmad-output/planning-artifacts/epics.md#UX Design Requirements] — lines 192-198: no UX contract exists and none is to be invented
- [Source: _bmad-output/planning-artifacts/implementation-readiness-report-2026-08-15.md#W-1] — the enumeration criterion this story discharges
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-1]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-3]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#SC-7]
- Repository, verified 2026-08-15: `src/django_service/templates/base.html`; `src/django_service/users/models.py:24-31`; `src/django_service/users/tasks.py`; `src/django_service/users/{views,urls,forms,context_processors,admin}.py`; `src/config/urls.py`; `src/config/settings/base.py:105-106,140,224,348,352`; `pyproject.toml:127`; full `templates/` and `static/` listings

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
