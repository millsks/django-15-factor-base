# Story 3.4: Local sign-in is a URL route that drives the real mapper

Status: ready-for-dev

## Story

As a developer working on a generated component,
I want local sign-in to construct synthetic claims and hand them to the same mapper the IdP flows use,
so that the authorization behaviour I see locally is the deployed behaviour minus the network hops.

## Acceptance Criteria

**Traceability:** FR-19 · AD-21 · SC-4, SC-5

1. **Given** local persona sign-in
   **When** it is exposed
   **Then** it is a URL route and no other mechanism
   **And** it is not a development authentication backend, a management command that writes a session, or a query-parameter shim

2. **Given** the route
   **When** it is declared
   **Then** its URL name and path prefix are fixed constants held in exactly one place
   **And** that declaration moves into `accelerator.toml` in Epic 7 without changing its meaning

3. **Given** a sign-in
   **When** it completes
   **Then** it constructs a synthetic claims payload and passes it to the mapper
   **And** the mapper is unaware which path produced the claims

4. **Given** a staff persona and a read-only persona
   **When** each reaches the same admin page
   **Then** the staff persona is admitted and the read-only persona is refused
   **And** the difference is produced by the mapper rather than by any local-only branch

5. **Given** this route is a credential path the product itself introduces
   **When** Epic 4 lands
   **Then** it is refused at startup in a deployed component

## Tasks / Subtasks

- [ ] Task 1: Fix the route's name and prefix as constants in exactly one place (AC: #2)
  - [ ] Create `src/config/local_dev/constants.py` (NEW) with `LOCAL_SIGNIN_URL_NAME: str = "local_persona_signin"` and `LOCAL_SIGNIN_PATH_PREFIX: str = "_local/"`.
  - [ ] Do **not** mount the prefix under `accounts/`. AD-21 uses that exact case as its worked failure: "a route named `local_persona_login` mounted under `/accounts/` would otherwise satisfy this AD and pass an allowlist that already permits `/accounts/` for allauth."
  - [ ] Every other module — `src/config/local_dev/urls.py`, `src/config/urls.py`, templates, tests — imports these two names. No string literal `"_local/"` or `"local_persona_signin"` may appear anywhere else in `src/`.
  - [ ] Add a comment recording that these constants move into `accelerator.toml` in Epic 7 without changing their meaning, so the move is a relocation of the declaration rather than a redefinition.

- [ ] Task 2: Author the sign-in view (AC: #1, #3, #4)
  - [ ] Create `src/config/local_dev/views.py` (NEW) with two view callables:
    - [ ] `persona_index(request)` — `GET`, lists `persona_keys()` from `src/config/local_dev/personas.py` with a POST form per persona.
    - [ ] `persona_signin(request, persona_key)` — `POST` only (`require_POST`). Resolve the persona with `get_persona`, build its synthetic claims with `build_claims` (Story 3.3 — the sole constructor; do not build a second payload here), then call `resolve_user(claims)` followed by `sync_for_interactive(user, claims)` from `src/config/authorization/mapper.py` (Stories 2.4, 2.5), then establish the session with `django.contrib.auth.login(request, user, backend="django.contrib.auth.backends.ModelBackend")` and redirect.
    - [ ] Use `sync_for_interactive`, **not** `sync_once_per_epoch`. Story 2.5's own rule: "an interactive login is itself the epoch, has no `jti`, and must never be routed through the epoch gate." Routing local sign-in through the epoch gate would make AC #3's group-change behaviour fire once and never again.
  - [ ] `GET` is not a sign-in method here: a credential path reachable by following a link is a drive-by session. The list page is `GET`; the act is `POST`.
  - [ ] The view contains **no** mapping logic: no group assignment, no `is_staff` write, no permission decision. Everything that distinguishes a staff persona from a read-only one happens inside the mapper, driven by the claims. If a reviewer can find a branch in this module that reads a persona's groups and sets anything on the user, the story is not done.
  - [ ] Refuse when not local: the first statement of both views calls `config.locality.is_local()` (Story 3.1) and returns `HttpResponseNotFound` — or raises `ImproperlyConfigured`, matching Story 3.3's seeding refusal — when it is `False`. This is defence in depth behind Task 3's URLconf gate, not a substitute for it.
  - [ ] Log each sign-in as a structured `structlog` event carrying the persona key and the resolved user id. Never `print`.

- [ ] Task 3: Expose it as a URL route and by no other mechanism (AC: #1, #2)
  - [ ] Create `src/config/local_dev/urls.py` (NEW): `app_name`-free module with `urlpatterns = [path("", views.persona_index, name=f"{LOCAL_SIGNIN_URL_NAME}_index"), path("<slug:persona_key>/", views.persona_signin, name=LOCAL_SIGNIN_URL_NAME)]`.
  - [ ] The persona is selected by a **path segment**, never a query parameter. AD-21 names "a query-parameter shim" as a forbidden shape.
  - [ ] In `src/config/urls.py` (UPDATE), append the include **only when locality is local**:
        `if is_local(): urlpatterns += [path(LOCAL_SIGNIN_PATH_PREFIX, include("config.local_dev.urls"))]`.
        Use the string form of `include` so the URLconf module is imported lazily by the resolver.
  - [ ] Gate on `config.locality.is_local()`, never on `settings.DEBUG`. `DEBUG` is not the locality signal (AD-13), and a deployed component with `DEBUG` mistakenly true would then mount a live credential path.
  - [ ] This locality gate is **not** the AD-24 prohibition's subject. AD-24 forbids conditional imports as a *feature-removal* mechanism during materialization; this is a runtime configuration branch inside a `core` path that ships in every combination. Do not attempt to express it as a feature-owned region.
  - [ ] Do **not** add anything to `AUTHENTICATION_BACKENDS`. Passing `backend=` to `django.contrib.auth.login()` names an already-declared backend and adds no new credential path — which matters because FR-17's allowlist is evaluated over `AUTHENTICATION_BACKENDS`, the DRF default authentication classes, and the component's own authentication route prefixes.
  - [ ] Do **not** add a management command, a middleware, a signal receiver, an `authenticate()` backend, or a test-only client shim that establishes a persona session by any other route.

- [ ] Task 4: Templates for the two views (AC: #1, #4)
  - [ ] Add `src/django_service/templates/local_dev/persona_index.html` (NEW), extending the existing `base.html`. Templates live under `src/django_service/templates/`, which `src/config/settings/base.py:211` registers as the `DIRS` entry; `base.html` and the error templates stay in `django_service` in every combination (AD-29).
  - [ ] Keep the template minimal: one POST form per persona listing its key and its declared groups. Template coverage is measured (AD-20), so a template with unreachable branches costs coverage.

- [ ] Task 5: Tests (AC: #1, #2, #3, #4)
  - [ ] Create `tests/unit/test_local_dev_urls.py` (NEW):
    - [ ] With `COMPONENT_RUNTIME=local`, assert `reverse(LOCAL_SIGNIN_URL_NAME, kwargs={"persona_key": ...})` resolves and that the resolved path starts with `/` + `LOCAL_SIGNIN_PATH_PREFIX`.
    - [ ] Assert `resolve()` on that path returns a view callable whose `__module__` is `config.local_dev.views` — the same object-identity property Epic 4's predicate relies on (AD-26: predicates resolve objects, never strings).
    - [ ] Assert the prefix does not begin with `accounts/`.
    - [ ] Assert `AUTHENTICATION_BACKENDS` is unchanged — it contains exactly `django.contrib.auth.backends.ModelBackend` and `allauth.account.auth_backends.AuthenticationBackend` and no local-development entry.
    - [ ] Assert the constants appear in exactly one module: import them from `config.local_dev.constants` and assert `config.local_dev.urls` and `config.urls` reference the imported names (a grep-style assertion over the source text of `src/config/` for the literal strings is acceptable and is the cheapest way to catch a second declaration site).
  - [ ] Create `tests/integration/test_local_dev_signin.py` (NEW), every test `@pytest.mark.integration`:
    - [ ] `test_signin_establishes_a_session_through_the_mapper`: POST to the route as the staff persona; assert the response redirects, the session carries an authenticated user, and the user's identity key equals the persona's declared `subject`.
    - [ ] `test_the_mapper_receives_the_same_claims_shape_as_the_idp_flows`: spy the mapper entry point and assert it is called with the payload `build_claims` produced — no extra local-only argument, no flag telling it the request came from local sign-in.
    - [ ] `test_staff_persona_reaches_the_admin_index_and_read_only_persona_does_not`: sign in as each persona in turn and request the admin index (`reverse("admin:index")`); assert the staff persona receives a rendered 200 and the read-only persona is refused (redirect to login or 403). This is AC #4 and it is the story's centre of gravity.
    - [ ] `test_the_difference_is_produced_by_the_mapper`: assert the read-only persona's user has `is_staff` `False` and lacks the designated staff group, and that the staff persona's `is_staff` was set by the mapper's sync rather than by the view — assert by patching the mapper's sync to a no-op and observing that the staff persona is then *also* refused.
    - [ ] `test_get_does_not_sign_in`: a `GET` to the sign-in path returns 405 and establishes no session.
    - [ ] `test_route_is_absent_when_not_local`: with `COMPONENT_RUNTIME` unset, reload the URLconf (`django.urls.clear_url_caches()` plus `importlib.reload` of `config.urls`, or `override_settings(ROOT_URLCONF=...)`) and assert the path 404s and `reverse` raises `NoReverseMatch`. Restore the URLconf in teardown.

- [ ] Task 6: Document the route (AC: #1, #2)
  - [ ] Extend the `## Local personas` section of `docs/development.md` (added by Story 3.3) with the sign-in route: its prefix, that it is `POST`-only, that it is mounted only when `COMPONENT_RUNTIME=local`, and that it is refused at startup in a deployed component once Epic 4 lands.

## Dev Notes

### Architecture Constraints

**AD-21 — The local sign-in path is a URL route, and the refusal resolves its view.** Binding rule, in the AD's own words:

> Local persona sign-in is exposed as a URL route and by no other mechanism — not a development authentication backend, not a management command that writes a session, not a query-parameter shim. Its URL name and path prefix are fixed constants declared in `accelerator.toml`. The stage-2 predicate refuses any route whose **view callable belongs to the local sign-in module** (AD-26), never a name or prefix match, because a route named `local_persona_login` mounted under `/accounts/` would otherwise satisfy this AD and pass an allowlist that already permits `/accounts/` for allauth. It ships in every component and is refused wherever the component is deployed.

*Prevents:* "the product's own credential path taking a shape the refusal contract cannot see; and — the subtler half — a route that satisfies this AD by name and still evades the refusal because the predicate matched a string."

**Where the constants live in this story.** `accelerator.toml` does not exist yet — it is authored in Epic 7. epics.md records the sequencing explicitly: the local sign-in route's name and prefix constants are among "three declarations … authored in a single module in an earlier epic and moved into `accelerator.toml` in Epic 7 without changing any assertion's meaning." So this story authors them in `src/config/local_dev/constants.py` as the single module, and Epic 7 relocates the declaration. Keep them as plain module-level constants with no computation, so the move is mechanical.

**Why the route is mounted conditionally rather than unconditionally.** AD-21 says the path "ships in every component and is refused wherever the component is deployed", and FR-13 makes "the local sign-in route reachable" a stage-2 refusal condition. Those two statements are consistent only if the *code* ships everywhere while the *route* is mounted only when locality is local — an unconditionally mounted route would make every deployed component refuse to start and nothing would ever deploy. The refusal is the backstop that catches the route being reachable anyway: mounted by a hand edit, by a tenant app's URLconf include, or by a component that sets `COMPONENT_RUNTIME=local` in a deployed environment. Do not remove the locality gate, and do not treat the refusal as making the gate redundant.

**AD-26 — Predicates resolve objects, never strings.** Epic 4's stage-2 predicate resolves the URLconf and refuses any route whose view callable belongs to `config.local_dev`. Two consequences for this story: the view callables must live in that package (not be re-exported from elsewhere, not be a `lambda`, not be wrapped in a decorator that relocates `__module__`), and the package name and view locations must stay stable.

**AD-11 / AD-10 — the mapper owns identity and authorization.** The view resolves by identity key and syncs; it never writes `is_staff`, `is_superuser` or group membership itself. AC #4's "the difference is produced by the mapper rather than by any local-only branch" is the acceptance condition, and Task 5's patched-sync test is what proves it rather than assuming it.

**FR-17 / AD-8 — the allowlist surface.** The allowlist covers `AUTHENTICATION_BACKENDS`, the DRF default authentication classes, and the component's own authentication route prefixes, and it is one declaration shared with AD-8's contributable surface. This story must not widen any of the three: no new backend, no new DRF authentication class, one new route prefix that Epic 4 will enumerate.

**R-5 carried honestly.** Local sign-in exercises the mapper, group sync, staff promotion and the admin's authorization — and exercises nothing about OIDC discovery, the Authorization Code with PKCE exchange, allauth's callback handling, or token verification. The PRD states the personas "are not a mitigation" for the absence of a real IdP; SC-6 remains unproven by anything in this epic.

**Never:** add to `AUTHENTICATION_BACKENDS`; write a session from a management command; select the persona by query parameter; gate on `settings.DEBUG`; put mapping logic in the view; spell the route name or prefix as a literal outside `constants.py`; use `print()` or stdlib `logging`.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/local_dev/constants.py` | NEW | `LOCAL_SIGNIN_URL_NAME`, `LOCAL_SIGNIN_PATH_PREFIX` — the single declaration site until Epic 7 moves it. |
| `src/config/local_dev/views.py` | NEW | `persona_index` (GET) and `persona_signin` (POST): build claims, drive the mapper, establish the session. |
| `src/config/local_dev/urls.py` | NEW | The two routes, persona selected by path segment. |
| `src/config/urls.py` | UPDATE | Locality-gated `include` of `config.local_dev.urls` at `LOCAL_SIGNIN_PATH_PREFIX`. |
| `src/django_service/templates/local_dev/persona_index.html` | NEW | Minimal persona list with one POST form per persona, extending `base.html`. |
| `docs/development.md` | UPDATE | Extend `## Local personas` with the route. |
| `tests/unit/test_local_dev_urls.py` | NEW | Reverse/resolve, module identity, prefix, single declaration site, backends unchanged. |
| `tests/integration/test_local_dev_signin.py` | NEW | Session establishment, mapper claims shape, admin admit/refuse, GET rejection, absence when not local. |

**`src/config/urls.py` today (verified, 75 lines).** `urlpatterns` holds `home`, `about`, `path(settings.ADMIN_URL, admin.site.urls)`, `path("users/", include("django_service.users.urls", namespace="users"))`, `path("accounts/", include("allauth.urls"))`, and `*static(settings.MEDIA_URL, ...)`. A `if settings.DEBUG:` block at `:30-32` appends `staticfiles_urlpatterns()`. The API block at `:35-46` adds `api/`, **`path("api/auth-token/", obtain_auth_token, name="obtain_auth_token")`**, `api/schema/` and `api/docs/`. A second `if settings.DEBUG:` block at `:48-75` adds the 400/403/404/500 preview routes and the debug-toolbar mount.

Two things to preserve and one not to touch: keep the `allauth.urls` include at `accounts/` and the admin mount intact; keep the error-preview routes, which AD-30's smoke check depends on for a rendered 404. **Do not remove `obtain_auth_token`** — that is Story 2.8's work (FR-6), not this story's, and removing it here would leave Story 2.8 with nothing to assert.

**`src/django_service/templates/`** is the registered template directory (`src/config/settings/base.py:211`, `DIRS: [str(APPS_DIR / "templates")]`, with `APPS_DIR = BASE_DIR / "src" / "django_service"` at `:18`) and `APP_DIRS` is `True`. AD-29 requires `base.html` and the error templates to stay in `django_service`; a small `local_dev/` subdirectory there is consistent with that, since this surface is `core` and is not the server-rendered UI feature.

**Dependencies on earlier stories — concrete names, verified against those stories' files.** `config.locality.is_local()` (Story 3.1); `config.local_dev.personas.build_claims` / `get_persona` / `persona_keys` / `resolve_groups` (Story 3.3); `config.authorization.mapper.resolve_user` and `sync_for_interactive` (Stories 2.4, 2.5); `settings.CLAIMS_CONTRACT` (Story 2.2, with fixture values set in `src/config/settings/test.py`); `User.idp_subject` (Story 2.1). `src/config/authorization/` does not exist in the repository today.

**Interaction with Story 2.6.** That story forces the admin through allauth (`DJANGO_ADMIN_FORCE_ALLAUTH` defaulting true, served through the existing `secure_admin_login` wrapper in `src/django_service/users/admin.py`) and makes an unauthenticated request to an authenticated page redirect to the IdP rather than to a local form. AC #4's admin assertions must therefore be written against an **already-established session** — sign in through this story's route first, then request `reverse("admin:index")`. Do not weaken `DJANGO_ADMIN_FORCE_ALLAUTH` in a test settings override to make the admin reachable.

### Testing Requirements

- Unit tests in `tests/unit/test_local_dev_urls.py`: URLconf reverse/resolve and source-level assertions only — no database, no client requests. Integration behaviour goes in `tests/integration/test_local_dev_signin.py` with `@pytest.mark.integration` on every test.
- The object-identity assertion (`view.__module__ == "config.local_dev.views"`) is not decoration: it is the same property Epic 4's predicate uses, and asserting it here catches a refactor that moves the view before Epic 4 discovers it.
- The URLconf-reload test must restore state — `django.urls.clear_url_caches()` after the reload, and re-import `config.urls` in teardown. A leaked URLconf breaks every later test in the session; the integration convention requires leaving resources as found.
- Template coverage counts toward the AD-20 floor: ninety percent **including templates**, `COVERAGE_CORE=ctrace` in force. The new template must be rendered by at least one test.
- Test disposition: `core`, under `tests/` mirroring `src/`.
- Run with `pixi run test` / `pixi run test-integration`; `pixi run ci` must exit 0.

#### Project Structure Notes

`src/config/local_dev/` is created by Story 3.3 and extended here; see that story's Project Structure Notes for the variance rationale against the Structural Seed. Disposition is `core` — FR-19 ships the path in every component and guards it rather than stripping it.

**Traceability marker, not an acceptance condition for this story.** AC #5 — "this route is refused at startup in a deployed component when Epic 4 lands" — records where the obligation completes. epics.md states it directly: "A small number of criteria reference a later epic — Story 2.2's refusal, **Story 3.4's guarded route**, Story 7.8's deliberate-orphan test. These are traceability markers recording where the obligation completes, not acceptance conditions for the story that carries them." Do not implement a stage-2 refusal in this story, do not create `src/config/startup/`, and do not fail this story's gate on the refusal's absence. What this story owes Epic 4 is a stable module name and a view callable it can resolve.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-21]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26] — predicates resolve objects, never strings; the allowlist and the contributable surface are one declaration.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24] — the sub-file removal prohibition, and why a runtime locality branch is not its subject.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29] — `base.html` and error templates stay in `django_service`.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-30] — the smoke check's rendered admin index and rendered 404.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-19] · [#FR-13] · [#FR-17]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.4] · [Source: _bmad-output/planning-artifacts/epics.md:225] — the constants move into `accelerator.toml` in Epic 7 · [Source: _bmad-output/planning-artifacts/epics.md:299] — the traceability-marker rule.
- [Source: src/config/urls.py:13-46] · [Source: src/config/settings/base.py:18,133-136,211]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
