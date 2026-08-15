# Story 7.4: django_service is core in its entirety and the UI surface leaves it

Status: ready-for-dev

## Story

As a lead developer,
I want no feature-scoped disposition anywhere inside the base package,
so that a reusable app cannot import a module that exists in six combinations and not the other six.

## Acceptance Criteria

**Traceability:** FR-1, FR-3 · AD-29 · SC-7 · readiness warning W-1

1. **Given** that no source document enumerates which templates, static assets, views and forms constitute the server-rendered UI feature
   **When** this story begins
   **Then** that surface is enumerated by audit of the existing tree and recorded in the carrier before any file moves
   **And** the enumeration distinguishes user-facing surface from `base.html` and the error templates, which stay

2. **Given** any path inside `src/django_service/`
   **When** its disposition is assigned
   **Then** it is `core`
   **And** a gate test asserts that no `feature:*` disposition applies to any path inside it

3. **Given** surface that genuinely belongs to the server-rendered UI feature
   **When** the UI feature is prepared for extraction
   **Then** user-facing page templates, form styling, user-facing views and forms move out of `django_service` into a feature-owned location first

4. **Given** `base.html` and the error templates
   **When** the UI feature is absent
   **Then** they remain
   **And** the 403, 404 and 500 pages that extend `base.html` still render

5. **Given** a combination with the server-rendered UI absent
   **When** it runs
   **Then** the admin renders, static files serve, the messages framework is available, and template rendering works
   **And** what the UI feature removed is the end-user surface and nothing else

6. **Given** the immovable core
   **When** any of the twelve combinations is inspected
   **Then** it declares PostgreSQL as its deployed database, DRF with drf-spectacular, the Django admin, CORS handling, structlog, OpenTelemetry, environment-based configuration, static file serving and a uvicorn/gunicorn process
   **And** no feature toggle can be set to a value that removes any of them

## Tasks / Subtasks

- [ ] Task 1 — Audit and record the UI surface in the carrier **before moving anything** (AC: #1)
  - [ ] This discharges readiness warning W-1: the UI feature's surface is described in the sources but never enumerated. It is an inventory of what is already in the tree, not a design exercise. No UX contract exists and none is to be invented (`epics.md:192-198`).
  - [ ] Add `[features.ui]` detail to `accelerator.toml`: `templates`, `static`, `views`, `forms`, `urls`, `tests` — each an explicit list. An empty list is a declaration; an absent key is not.
  - [ ] Record, in the same block, the **stays** list and the reason each item stays: `base.html`, `403.html`, `403_csrf.html`, `404.html`, `500.html`, `static/images/favicons/favicon.ico`. The audit results are pre-run in Source Tree below; verify each against the tree rather than trusting the table.
  - [ ] Record the two **decisions this story must make and cannot inherit** (Source Tree, "Decisions required"): where the feature-owned location is, and what happens to the allauth template overrides.

- [ ] Task 2 — Break `base.html`'s dependency on UI-only routes so it renders with the UI absent (AC: #4, #5)
  - [ ] `src/django_service/templates/base.html` today reverses three routes that leave with the UI feature: `{% url 'home' %}` (twice), `{% url 'about' %}`, and `{% url 'users:detail' request.user.username %}`. With the UI absent those tags raise `NoReverseMatch` and **every** page extending `base.html` fails — including the 404 that AD-30's smoke check asserts renders. AC #4 is not satisfiable without this change.
  - [ ] Reduce `base.html` to what the admin and the error handlers need in every combination: `{% load static i18n %}`, the `<head>` block, the favicon, the `{% block css %}` / `{% block javascript %}` / `{% block content %}` / `{% block main %}` / `{% block modal %}` / `{% block inline_javascript %}` block skeleton, and the `{% if messages %}` loop (AC #5 requires the messages framework be available).
  - [ ] Move the navbar — every `{% url %}` in it, the brand link, the profile and sign-in/sign-out items, the `ACCOUNT_ALLOW_REGISTRATION` conditional — into a UI-feature template that overrides a `{% block %}` `base.html` leaves empty. Do **not** guard it with `{% if %}` on a setting: that is present-but-disabled, which FR-28 and Story 7.6's AC forbid, and it leaves a template orphan the coverage signal will report as zero.
  - [ ] `base.html` currently loads Bootstrap CSS and JS from `cdnjs.cloudflare.com`. That is form styling and belongs with the UI feature. Moving it also removes an external network dependency from the error pages, which matters for the local smoke check (FR-33: no external service running). Move it into the UI-feature block.
  - [ ] Keep `403.html`, `403_csrf.html`, `404.html`, `500.html` where they are and unchanged in content; they extend `base.html` and use only `{% block title %}` / `{% block content %}`.

- [ ] Task 3 — Sever the `core`→UI route references (AC: #4, #5)
  - [ ] `src/django_service/users/models.py:24-31` — `User.get_absolute_url()` returns `reverse("users:detail", kwargs={"username": self.username})`. `models.py` is `core` (it is `AUTH_USER_MODEL`, AD-5 guaranteed surface); `users:detail` leaves with the UI. In six combinations this method raises `NoReverseMatch` — and Django's admin calls `get_absolute_url` to render the "View on site" link. Resolve it: either remove the method (a breaking change to the guaranteed surface — bump `django_service.__api_version__` per AD-5 if it is enumerated) or make it resolve the route defensively without a `try/except`-shaped feature check. Record the choice and its reason in the carrier.
  - [ ] `src/config/settings/base.py:140` — `LOGIN_REDIRECT_URL = "users:redirect"` names a UI route. `base.py` is `core`. Make this a `feature:ui` region under AD-24 with a `core` default beside it (the admin index or `settings.ADMIN_URL`), so the six UI-absent combinations have a valid redirect target.
  - [ ] `src/config/urls.py` — `core`, and it carries UI routes: `path("", TemplateView...pages/home.html, name="home")`, `path("about/", TemplateView...pages/about.html, name="about")`, and `path("users/", include("django_service.users.urls", namespace="users"))`. Mark each as a `feature:ui` region under AD-24 (paired `# feature:ui` / `# /feature:ui` line comments) and declare the regions in `accelerator.toml`. **This makes `src/config/urls.py` a region-bearing path the AD-24 list does not name** — declare it; Story 7.2's reconciler must already accept more than three.
  - [ ] Do not use conditional imports, settings-module inheritance or `try/except ImportError` anywhere in this task. AD-24 forbids all three, and a URLconf that conditionally includes a module is exactly the mechanism it names.

- [ ] Task 4 — Move the user-facing surface out of `src/django_service/` (AC: #2, #3)
  - [ ] Decide the feature-owned location first (see "Decisions required"), then move — never the other way round.
  - [ ] Move `src/django_service/users/views.py` (`UserDetailView`, `UserUpdateView`, `UserRedirectView` — all three are `LoginRequiredMixin` end-user pages).
  - [ ] Move `src/django_service/users/urls.py` (the `users` namespace: `~redirect/`, `~update/`, `<str:username>/`).
  - [ ] Move `src/django_service/templates/pages/home.html`, `pages/about.html`, `users/user_detail.html`, `users/user_form.html`.
  - [ ] Move `src/django_service/static/css/project.css` and `static/js/project.js` — both are referenced only from `base.html`'s UI blocks. `static/images/favicons/favicon.ico` stays (`base.html` head, every combination). `static/fonts/.gitkeep` is a placeholder; decide and record.
  - [ ] Split `src/django_service/users/forms.py`: `UserAdminChangeForm` and `UserAdminCreationForm` are used by `users/admin.py` and stay `core`; `UserSignupForm` and `UserSocialSignupForm` are allauth signup forms referenced from `base.py:348` and `:352` — decide with the allauth-template decision and keep both halves consistent.
  - [ ] `src/django_service/users/context_processors.py` (`allauth_settings`, exposing `ACCOUNT_ALLOW_REGISTRATION`) exists only for the navbar's registration link. It is registered in `base.py:224`. Move it with the navbar and make the `TEMPLATES` context-processor entry a `feature:ui` region.
  - [ ] **`src/django_service/users/tasks.py` is `feature:celery` code sitting inside `src/django_service/`** — it imports `from celery import shared_task` and defines `get_users_count`, documented in its own docstring as "a pointless Celery task to demonstrate usage". AD-29 forbids a `feature:*` disposition there, so it must leave too, or be deleted. Deleting it is the cleaner answer and needs the user's confirmation before removal; moving it to the celery feature's location is the conservative one. Take `tests/integration/users/test_tasks.py` with it either way.
  - [ ] Everything remaining under `src/django_service/` — `users/models.py`, `apps.py`, `admin.py`, `adapters.py`, `migrations/`, `api/`, `contrib/sites/`, `templates/{base,403,403_csrf,404,500}.html`, `static/images/`, `__init__.py` — is `core` and stays.
  - [ ] Update every import that follows the moved modules. `INSTALLED_APPS` gains the UI feature's app label as a `feature:ui` region in `base.py` (Story 7.2 already marks `crispy_forms` / `crispy_bootstrap5` at `:105-106`; this entry joins that region or gets its own).

- [ ] Task 5 — The AD-29 gate test (AC: #2)
  - [ ] Add `tests/integration/materializer/test_django_service_is_core.py` (NEW), `@pytest.mark.integration`: load the carrier and assert **no** `[dispositions]` entry, glob or region under `src/django_service/` resolves to a `feature:*` disposition. Assert over resolved dispositions, not over the literal declaration text, so a glob like `src/**/templates/pages/*` cannot slip through.
  - [ ] Assert the complement too: every tracked path under `src/django_service/` resolves to exactly `core`. `machinery` and `tenant` are also violations there.
  - [ ] Extend the carrier's `[[regions]]` reconciliation to reject a region whose `path` is under `src/django_service/` — AD-29 bars feature dispositions at path level, and a marker there would reintroduce combination-varying surface inside the guaranteed package by the sub-file route.

- [ ] Task 6 — Enumerate the guaranteed surface and the immovable core in the carrier (AC: #6)
  - [ ] AD-29: *"`accelerator.toml` enumerates the guaranteed surface explicitly; anything inside `django_service` not enumerated is internal and may change without a version bump."* Add `[guaranteed_surface]` listing the modules and names reusable apps may import — at minimum `django_service.users.models.User` (`AUTH_USER_MODEL`) and `django_service.__api_version__`. `__api_version__` does not exist yet (AD-5, Epic 9); declare the slot and record the forward reference.
  - [ ] Add `[immovable_core]` enumerating AC #6's nine items so the assertion has a single declared source: PostgreSQL as the deployed database, DRF with drf-spectacular, the Django admin, CORS handling, structlog, OpenTelemetry, environment-based configuration, static file serving, and a uvicorn/gunicorn process.
  - [ ] Add a gate test asserting no `[features.*]` list claims any package or path backing an `[immovable_core]` item — that is what makes "no feature toggle can be set to a value that removes any of them" checkable rather than asserted.
  - [ ] The runtime half of AC #6 — the `core`-disposed immovable-core assertion suite that runs inside every combination's gate and is never pruned (AD-30) — belongs to Epic 8. **Traceability marker, not an acceptance condition for this story.** What lands here is the declaration it will assert against.

- [ ] Task 7 — Tests (AC: #4, #5, and regression cover for the move)
  - [ ] `tests/integration/test_template_rendering.py` (UPDATE, exists today): extend to assert the 403, 404 and 500 templates render with the UI-feature templates and routes absent. Simulate absence by overriding `ROOT_URLCONF` to a UI-less URLconf, not by deleting files.
  - [ ] Add an assertion that the admin index renders and that `django.contrib.messages` is available with the UI absent (AC #5), mirroring the AD-30 smoke check at reference-application scale.
  - [ ] `tests/integration/users/test_views.py` and `tests/integration/users/test_forms.py` cover the moved views and forms — relocate them to mirror the feature's new source location and disposition them `feature:ui`, per the spine's test-location convention. `tests/unit/users/test_urls.py` covers the moved URLconf; same treatment. `tests/integration/users/test_admin.py`, `test_models.py`, `test_api_views.py`, `test_api_openapi.py` and `tests/unit/users/test_api_urls.py`, `test_adapters.py` cover `core` and stay.
  - [ ] `pixi run ci` exits 0, with coverage ≥90% including templates. Moving templates without moving their tests will show up as a coverage drop, which is the orphan signal working as designed — fix it by moving the tests, never by adding an omit entry (CG-1).

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
