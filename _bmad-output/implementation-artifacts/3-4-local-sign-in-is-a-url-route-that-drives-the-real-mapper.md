---
baseline_revision: b37e438
final_revision: 1622332
review_loop_iteration: 0
status: done
followup_review_recommended: true
warnings: []
---

# Story 3.4: Local sign-in is a URL route that drives the real mapper

Status: done

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

- [x] Task 1: Fix the route's name and prefix as constants in exactly one place (AC: #2)
  - [x] Create `src/config/local_dev/constants.py` (NEW) with `LOCAL_SIGNIN_URL_NAME: str = "local_persona_signin"` and `LOCAL_SIGNIN_PATH_PREFIX: str = "_local/"`.
  - [x] Do **not** mount the prefix under `accounts/`. AD-21 uses that exact case as its worked failure: "a route named `local_persona_login` mounted under `/accounts/` would otherwise satisfy this AD and pass an allowlist that already permits `/accounts/` for allauth."
  - [x] Every other module — `src/config/local_dev/urls.py`, `src/config/urls.py`, templates, tests — imports these two names. No string literal `"_local/"` or `"local_persona_signin"` may appear anywhere else in `src/`.
  - [x] Add a comment recording that these constants move into `accelerator.toml` in Epic 7 without changing their meaning, so the move is a relocation of the declaration rather than a redefinition.

- [x] Task 2: Author the sign-in view (AC: #1, #3, #4)
  - [x] Create `src/config/local_dev/views.py` (NEW) with two view callables:
    - [x] `persona_index(request)` — `GET`, lists `persona_keys()` from `src/config/local_dev/personas.py` with a POST form per persona.
    - [x] `persona_signin(request, persona_key)` — `POST` only (`require_POST`). Resolve the persona with `get_persona`, build its synthetic claims with `build_claims` (Story 3.3 — the sole constructor; do not build a second payload here), then call `resolve_user(claims)` followed by `sync_for_interactive(user, claims)` from `src/config/authorization/mapper.py` (Stories 2.4, 2.5), then establish the session with `django.contrib.auth.login(request, user, backend="django.contrib.auth.backends.ModelBackend")` and redirect.
    - [x] Use `sync_for_interactive`, **not** `sync_once_per_epoch`. Story 2.5's own rule: "an interactive login is itself the epoch, has no `jti`, and must never be routed through the epoch gate." Routing local sign-in through the epoch gate would make AC #3's group-change behaviour fire once and never again.
  - [x] `GET` is not a sign-in method here: a credential path reachable by following a link is a drive-by session. The list page is `GET`; the act is `POST`.
  - [x] The view contains **no** mapping logic: no group assignment, no `is_staff` write, no permission decision. Everything that distinguishes a staff persona from a read-only one happens inside the mapper, driven by the claims. If a reviewer can find a branch in this module that reads a persona's groups and sets anything on the user, the story is not done.
  - [x] Refuse when not local: the first statement of both views calls `config.locality.is_local()` (Story 3.1) and raises `Http404` when it is `False`. This is defence in depth behind Task 3's URLconf gate, not a substitute for it. **`Http404`, not `ImproperlyConfigured`.** The spec permitted either; a view reached in a deployed component must not answer 500 with a configuration message, because that both announces that the path exists and turns a guarded route into an error-rate signal. Story 3.3's `ImproperlyConfigured` is right for a *task* an operator invoked and wrong for a *route* a stranger requested.
  - [x] Handle `UnknownPersonaError` from `get_persona` by raising `Http404`. It is `LookupError`, **not** `KeyError` — Story 3.3 narrowed it deliberately so that an incidental dictionary miss inside `personas.py` cannot present as a 404 (`src/config/local_dev/personas.py:79`). Do not catch `LookupError` or `KeyError` here.
  - [x] Handle `ClaimsRejected` from `resolve_user` by re-rendering the index with the rejection reason and status 400. `src/config/authorization/exceptions.py` names this story as its consumer — "Epic 3's local sign-in route turns it into a form error" — and the case is reachable today: on a fresh clone nothing configures `COMPONENT_IDENTITY_CLAIM`, so `build_claims` correctly writes no identity key and the mapper answers `ClaimsRejected("identity key claim absent")`. Left uncaught that is a 500 traceback on the first thing a new developer clicks. `ClaimsRejected.reason` never carries a claim *value*, so rendering it leaks nothing.
  - [x] Log each sign-in as a structured `structlog` event carrying the persona key and the resolved user id. Never `print`. Module logger idiom, matching `seeding.py:52`: `logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)`.

- [x] Task 3: Expose it as a URL route and by no other mechanism (AC: #1, #2)
  - [x] Create `src/config/local_dev/urls.py` (NEW): `app_name`-free module with `urlpatterns = [path("", views.persona_index, name=f"{LOCAL_SIGNIN_URL_NAME}_index"), path("<slug:persona_key>/", views.persona_signin, name=LOCAL_SIGNIN_URL_NAME)]`.
  - [x] The persona is selected by a **path segment**, never a query parameter. AD-21 names "a query-parameter shim" as a forbidden shape.
  - [x] In `src/config/urls.py` (UPDATE), append the include **only when locality is local**, through a named module-level function rather than a bare `if` at module scope:
        `def local_signin_urlpatterns() -> list[URLPattern | URLResolver]: return [] if not is_local() else [path(LOCAL_SIGNIN_PATH_PREFIX, include("config.local_dev.urls"))]`, then `urlpatterns += local_signin_urlpatterns()`.
        Use the string form of `include` so the URLconf module is imported lazily by the resolver.
  - [x] **Why a function and not a bare `if`.** The whole suite runs in the `dev` pixi environment, which declares `COMPONENT_RUNTIME=local` in its activation env (`pixi.toml:435-436`), and a URLconf's locality branch is evaluated once at *import* time — before any `monkeypatch.setenv` a test could apply. A bare `if` is therefore assertable only by reloading `config.urls`, which mutates a module every later test resolves through. The function makes both branches directly callable under a monkeypatched environment with nothing reloaded and nothing to restore. This is Story 3.3's lesson 8 — "locality is set explicitly in every test rather than inherited" — applied to a decision that inheritance would otherwise hide.
  - [x] Gate on `config.locality.is_local()`, never on `settings.DEBUG`. `DEBUG` is not the locality signal (AD-13), and a deployed component with `DEBUG` mistakenly true would then mount a live credential path.
  - [x] This locality gate is **not** the AD-24 prohibition's subject. AD-24 forbids conditional imports as a *feature-removal* mechanism during materialization; this is a runtime configuration branch inside a `core` path that ships in every combination. Do not attempt to express it as a feature-owned region.
  - [x] Do **not** add anything to `AUTHENTICATION_BACKENDS`. Passing `backend=` to `django.contrib.auth.login()` names an already-declared backend and adds no new credential path — which matters because FR-17's allowlist is evaluated over `AUTHENTICATION_BACKENDS`, the DRF default authentication classes, and the component's own authentication route prefixes.
  - [x] Do **not** add a management command, a middleware, a signal receiver, an `authenticate()` backend, or a test-only client shim that establishes a persona session by any other route.

- [x] Task 4: Templates for the two views (AC: #1, #4)
  - [x] Add `src/django_service/templates/local_dev/persona_index.html` (NEW), extending the existing `base.html`. Templates live under `src/django_service/templates/`, which `src/config/settings/base.py:211` registers as the `DIRS` entry; `base.html` and the error templates stay in `django_service` in every combination (AD-29).
  - [x] Keep the template minimal: one POST form per persona listing its key and its declared groups. Template coverage is measured (AD-20), so a template with unreachable branches costs coverage.

- [x] Task 5: Tests (AC: #1, #2, #3, #4)
  - [x] Create `tests/unit/test_local_dev_urls.py` (NEW):
    - [x] With `COMPONENT_RUNTIME=local`, assert `reverse(LOCAL_SIGNIN_URL_NAME, kwargs={"persona_key": ...})` resolves and that the resolved path starts with `/` + `LOCAL_SIGNIN_PATH_PREFIX`.
    - [x] Assert `resolve()` on that path returns a view callable whose `__module__` is `config.local_dev.views` — the same object-identity property Epic 4's predicate relies on (AD-26: predicates resolve objects, never strings).
    - [x] Assert the prefix does not begin with `accounts/`.
    - [x] Assert `AUTHENTICATION_BACKENDS` is unchanged — it contains exactly `django.contrib.auth.backends.ModelBackend` and `allauth.account.auth_backends.AuthenticationBackend` and no local-development entry.
    - [x] Assert the constants appear in exactly one module: import them from `config.local_dev.constants` and assert `config.local_dev.urls` and `config.urls` reference the imported names (a grep-style assertion over the source text of `src/config/` for the literal strings is acceptable and is the cheapest way to catch a second declaration site).
  - [x] Create `tests/integration/test_local_dev_signin.py` (NEW), every test `@pytest.mark.integration`:
    - [x] `test_signin_establishes_a_session_through_the_mapper`: POST to the route as the staff persona; assert the response redirects, the session carries an authenticated user, and the user's identity key equals the persona's declared `subject`.
    - [x] `test_the_mapper_receives_the_same_claims_shape_as_the_idp_flows`: spy the mapper entry point and assert it is called with the payload `build_claims` produced — no extra local-only argument, no flag telling it the request came from local sign-in.
    - [x] `test_staff_persona_reaches_the_admin_index_and_read_only_persona_does_not`: sign in as each persona in turn and request the admin index (`reverse("admin:index")`); assert the staff persona receives a rendered 200 and the read-only persona is refused (redirect to login or 403). This is AC #4 and it is the story's centre of gravity.
    - [x] `test_the_difference_is_produced_by_the_mapper`: assert the read-only persona's user has `is_staff` `False` and lacks the designated staff group, and that the staff persona's `is_staff` was set by the mapper's sync rather than by the view — assert by patching the mapper's sync to a no-op and observing that the staff persona is then *also* refused.
    - [x] `test_get_does_not_sign_in`: a `GET` to the sign-in path returns 405 and establishes no session.
    - [x] `test_route_is_absent_when_not_local`: reload the URLconf under a deployed `COMPONENT_RUNTIME` (`monkeypatch.setenv(RUNTIME_ENV_VAR, "production")`, `django.urls.clear_url_caches()`, `importlib.reload(config.urls)`) and assert the path 404s and `reverse` raises `NoReverseMatch`. Restore in a `finally`: undo the environment, reload again, clear the caches, and **assert the route reverses once more before the test ends** — a restoration that is not asserted is a restoration nobody notices failing, and a leaked URLconf breaks every later test in the session.
    - [x] The branch itself is covered without any reload by the unit test on `local_signin_urlpatterns()` (Task 3): empty under a deployed environment, one entry carrying `LOCAL_SIGNIN_PATH_PREFIX` under a local one. Both tests are wanted — the unit one pins the decision, the integration one pins that the decision reaches the resolver.

- [x] Task 6: Document the route (AC: #1, #2)
  - [x] Extend the `## Local personas` section of `docs/development.md` (added by Story 3.3) with the sign-in route: its prefix, that it is `POST`-only, that it is mounted only when `COMPONENT_RUNTIME=local`, and that it is refused at startup in a deployed component once Epic 4 lands.

## Dev Notes

### Architecture Constraints

**AD-21 — The local sign-in path is a URL route, and the refusal resolves its view.** Binding rule, in the AD's own words:

> Local persona sign-in is exposed as a URL route and by no other mechanism — not a development authentication backend, not a management command that writes a session, not a query-parameter shim. Its URL name and path prefix are fixed constants declared in `accelerator.toml`. The stage-2 predicate refuses any route whose **view callable belongs to the local sign-in module** (AD-26), never a name or prefix match, because a route named `local_persona_login` mounted under `/accounts/` would otherwise satisfy this AD and pass an allowlist that already permits `/accounts/` for allauth. **The module ships in every component; the route is mounted only where locality is local.** The distinction is the whole rule: a route mounted unconditionally would make every deployed component refuse to start, since the stage-2 condition refuses the local sign-in route's reachability. Shipping is not mounting, and the refusal is the backstop for a route that is reachable anyway — through a URLconf edit, a misconfiguration, or a locality that failed open — not the expected path.

*Prevents:* "the product's own credential path taking a shape the refusal contract cannot see; and — the subtler half — a route that satisfies this AD by name and still evades the refusal because the predicate matched a string."

**Where the constants live in this story.** `accelerator.toml` does not exist yet — it is authored in Epic 7. epics.md records the sequencing explicitly: the local sign-in route's name and prefix constants are among "three declarations … authored in a single module in an earlier epic and moved into `accelerator.toml` in Epic 7 without changing any assertion's meaning." So this story authors them in `src/config/local_dev/constants.py` as the single module, and Epic 7 relocates the declaration. Keep them as plain module-level constants with no computation, so the move is mechanical.

**Why the route is mounted conditionally rather than unconditionally.** AD-21 states it as the rule itself: "the module ships in every component; the route is mounted only where locality is local", and "shipping is not mounting." FR-13 makes "the local sign-in route reachable" a stage-2 refusal condition, so the *code* ships everywhere while the *route* is mounted only when locality is local — an unconditionally mounted route would make every deployed component refuse to start and nothing would ever deploy. The refusal is the backstop that catches the route being reachable anyway: mounted by a hand edit, by a tenant app's URLconf include, or by a component that sets `COMPONENT_RUNTIME=local` in a deployed environment. Do not remove the locality gate, and do not treat the refusal as making the gate redundant.

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

**`src/config/urls.py` today (re-verified at `b37e438`, 75 lines — the description below replaces this story's original one, which was written before Story 2.8 landed).** `urlpatterns` holds `home`, `about`, `path(settings.ADMIN_URL, admin.site.urls)`, `path("users/", include("django_service.users.urls", namespace="users"))`, `path("accounts/", include("allauth.urls"))`, and `*static(settings.MEDIA_URL, ...)`. A `if settings.DEBUG:` block at `:29-33` appends `staticfiles_urlpatterns()`. The API block at `:36-45` adds `api/`, `api/schema/` and `api/docs/` — **`obtain_auth_token` is already gone**, removed by Story 2.8 (FR-6), and the original instruction to preserve it is void. A second `if settings.DEBUG:` block at `:47-74` adds the 400/403/404/500 preview routes and the debug-toolbar mount.

Two things to preserve and one not to touch: keep the `allauth.urls` include at `accounts/` and the admin mount intact; keep the error-preview routes, which AD-30's smoke check depends on for a rendered 404. **Do not remove the `home` and `about` `TemplateView`s** — under the spine's revision 3 they are deleted as demonstration content, but that deletion is Epic 7's. This story neither depends on them nor removes them: the sign-in redirect must target `LOGIN_REDIRECT_URL` (`users:redirect`, a `core` route in every combination) or an explicitly named route, never `home`.

**`src/django_service/templates/`** is the registered template directory (`src/config/settings/base.py:290-297`, `DIRS: [str(APPS_DIR / "templates")]`, with `APPS_DIR` defined near the top of the file) and `APP_DIRS` is `True`. AD-29 requires `base.html` and the error templates to stay in `django_service`; a small `local_dev/` subdirectory there is consistent with that. Under the spine's revision 3 the interface mechanism is itself `core` — `base.html`, `_navbar.html` and the navigation registry, the error templates, form styling and static-file serving are present in every combination and there is no `feature:ui` — so a `core` template extending `base.html` is safe in all six combinations rather than only in the ones that selected an interface.

**Dependencies on earlier stories — concrete names, re-verified against the tree at `b37e438`, not against those stories' files.** `config.locality.is_local()` and `RUNTIME_ENV_VAR` (`src/config/locality.py:84,68`); `config.local_dev.personas.build_claims` / `get_persona` / `persona_keys` / `resolve_groups` / `UnknownPersonaError` (Story 3.3, `personas.py:211,164,154,186,79`); `config.authorization.mapper.resolve_user` and `sync_for_interactive` (`mapper.py:188,795`, both taking `Mapping[str, Any]`, `sync_for_interactive` returning `SyncOutcome`); `config.authorization.exceptions.ClaimsRejected` with its `.reason` attribute (`exceptions.py:30`); `settings.CLAIMS_CONTRACT` (`base.py:227`, fixture values `sub` / `groups` / `platform-staff` / `platform-superuser` at `test.py:72-77`); `User.idp_subject` (Story 2.1). `src/config/authorization/` **does exist** — the original claim that it does not was written before Epic 2 landed.

**Settings this story reads, re-verified.** `LOGIN_REDIRECT_URL = "users:redirect"` (`base.py:210`) — the sign-in redirect target. `LOGIN_URL` is `reverse_lazy("openid_connect_login", ...)` (`base.py:221`), which is where an admin refusal lands, so AC #4's refused persona is asserted against `str(settings.LOGIN_URL)` rather than against `account_login`. `ADMIN_URL = "admin/"` (`base.py:349`). `AUTHENTICATION_BACKENDS` (`base.py:203-206`) is `ModelBackend` then allauth's, and is asserted **nowhere in `tests/` today** — Task 5's assertion is genuinely new coverage rather than a duplicate.

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
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.4] · [Source: _bmad-output/planning-artifacts/epics.md:227] — the constants move into `accelerator.toml` in Epic 7 · [Source: _bmad-output/planning-artifacts/epics.md:301] — the traceability-marker rule.
- [Source: src/config/urls.py:13-46] · [Source: src/config/settings/base.py:18,133-136,211]

## Auto Run Result

Status: `done`. Blocking condition: none.

**What was implemented.** Local persona sign-in as a URL route and no other mechanism: two views in
`config.local_dev` (a `GET` index, a `POST` act, the persona a path segment), a package URLconf, a
locality-gated mount in the project URLconf, the two constants in their single declaration site, and
a minimal template. The view builds claims with Story 3.3's sole constructor and drives Epic 2's
mapper; it contains no mapping logic, which is what makes AC #4's divergence the mapper's doing
rather than a local branch's.

**Files changed.**

- `src/config/local_dev/constants.py` (NEW) — the URL name and path prefix, declared once.
- `src/config/local_dev/views.py` (NEW) — `persona_index` and `persona_signin`.
- `src/config/local_dev/urls.py` (NEW) — the two routes.
- `src/config/urls.py` — `local_signin_urlpatterns()`, mounted only where locality is local.
- `src/django_service/templates/local_dev/persona_index.html` (NEW) — one POST form per persona.
- `tests/unit/test_local_dev_urls.py` (NEW) — 15 tests on the route's shape and declaration sites.
- `tests/integration/test_local_dev_signin.py` (NEW) — 19 tests on what the route does.
- `docs/development.md` — a `### Signing in as a persona` subsection.
- `deferred-work.md`, `sprint-status.yaml` — two new entries; the story marked done.

**Review findings.** 14 patches applied (8 medium, 6 low), 2 deferred, 9 rejected. No intent gap and
no bad-spec loopback, so `review_loop_iteration` stayed 0. The eight medium patches are itemized in
the triage log below; the four that changed behaviour rather than prose are the guard ordering
(404 to every verb in a deployed component), the `ImproperlyConfigured` rendering, the savepoint
around resolve-and-sync, and the non-vacuous `signed_in_client()`.

**Verification.** `pixi run ci` exit 0 — 854 passed, 96.27% coverage against a floor of 90,
templates included. The same suite re-run against a real PostgreSQL 17 container: 854 passed,
identical coverage. All four new source files and the new template are at 100%. The three
behaviour-changing fixes were verified by restoring the pre-fix view and confirming their tests
fail against it.

**Follow-up review recommended: true.** Not for any single finding, but for the volume and breadth
of the review pass — fourteen fixes across the view, two test files and the documentation, several
of them on the security-adjacent surface (CSRF coverage, the 404-versus-405 disclosure, transaction
rollback on a refused sign-in) and one of them correcting a test that was passing vacuously.

**Residual risks.** Both are recorded in `deferred-work.md`: the 400 response is served at the
`POST`-only URL, so a browser refresh answers 405; and the claim that a deployed component never
imports `config.local_dev.urls` — which three docstrings rest on — cannot be verified in-process and
needs a subprocess test seam. Beyond those, R-5 stands unchanged and is now stated more fully in the
documentation: this route exercises the mapper and nothing about OIDC discovery, PKCE, allauth's
callback handling or token verification, and the session it establishes is not the deployed session.

## Review Triage Log

### 2026-08-17 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 14: (high 0, medium 8, low 6)
- defer: 2: (high 0, medium 0, low 2)
- reject: 9
- addressed_findings:
  - `[medium]` `[patch]` `@require_POST` ran before the locality guard, so a route mounted by hand in a deployed component answered `405` to a `GET` — confirming the path exists, which is the disclosure the `Http404`-over-`ImproperlyConfigured` choice was made to avoid. The decorator is gone and the method check now follows the locality check. `test_a_deployed_run_answers_404_to_every_verb` (parametrized over `get`/`put`/`delete`) is the new pin; it fails against the pre-fix code.
  - `[medium]` `[patch]` CSRF — the only thing refusing a cross-origin auto-submitting `POST` — was asserted nowhere, so `csrf_exempt` could be added tomorrow with the suite green. Added `test_a_cross_site_post_without_a_token_is_refused` using `Client(enforce_csrf_checks=True)`.
  - `[medium]` `[patch]` `signed_in_client()` discarded the sign-in response, so AC #4's *refusal* half was satisfied identically by a client that had never signed in. The helper now asserts `302` and a session key before returning.
  - `[medium]` `[patch]` `ImproperlyConfigured` from `build_claims` (two overlapping configured claim names) escaped as a 500 next to the neighbouring misconfiguration deliberately turned into a 400. Both are now caught together and rendered as the same form error; `test_overlapping_claim_names_render_as_a_form_error` fails against the pre-fix code.
  - `[medium]` `[patch]` Neither `local_dev.persona_signed_in` nor `local_dev.persona_signin_rejected` was asserted anywhere, unlike the sibling seeding story which pins its event's whole shape. Added `test_a_signin_emits_one_structured_event`.
  - `[medium]` `[patch]` `docs/development.md` stated Epic 4's startup refusal and the credential-surface enumeration in the present tense; neither exists. Both rephrased as future work, with the consequence stated plainly: until the refusal lands, a leaked `COMPONENT_RUNTIME=local` serves the route rather than failing closed at boot.
  - `[medium]` `[patch]` The allauth bypass was recorded nowhere. Local sign-in calls `django.contrib.auth.login` directly, so the session carries no `EmailAddress`, no `SocialAccount` and none of allauth's state — the authorization is the deployed authorization, the session is not. Added to the docs as another face of R-5.
  - `[medium]` `[patch]` A refused sign-in committed the account it had already created: `ATOMIC_REQUESTS` is on, and returning a 400 rather than raising leaves the request's transaction to commit. `resolve_user` and `sync_for_interactive` are now one savepoint; `test_a_refused_signin_leaves_no_account_behind` fails against the pre-fix code.
  - `[low]` `[patch]` `SESSION_BACKEND` was tied to `AUTHENTICATION_BACKENDS` only indirectly. Added `test_the_session_backend_is_one_of_the_declared_backends`.
  - `[low]` `[patch]` `SyncOutcome.ignored` went unlogged, so the "designated groups never provisioned, staff persona silently not staff" case left no trace. The sign-in event now carries `groups_ignored`.
  - `[low]` `[patch]` The index render test asserted the action URL but not the form's method, so a degradation to `method="get"` would have stayed green while every button answered 405. Added `test_the_index_form_posts_to_the_signin_path`.
  - `[low]` `[patch]` `test_each_constant_is_spelled_in_exactly_one_module`'s docstring claimed a reach it does not have (`src/`, `.py`/`.html`, substring). Corrected to state its actual boundary, including that `accelerator.toml` — the file Epic 7 relocates these into — is invisible to it.
  - `[low]` `[patch]` `constants.py` claimed the leading underscore meant the prefix "cannot collide" with a tenant app's routes. URL routing reserves no character; reworded as the convention it is.
  - `[low]` `[patch]` Two docstrings referred to `require_POST` and `functools.wraps` preserving `__module__` after the decorator was removed. Corrected.

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — bmad-dev-auto, 2026-08-17.

### Debug Log References

Planned against the tree at `b37e438`. Every dependency was re-read before anything was written
against it rather than taken from this story's own Dev Notes, which were authored on 2026-08-15
and predate Epics 2 and 3 landing. Three claims did not survive that reading and were corrected in
the spec before implementing — see Completion Notes.

Inner loop: `pixi run format` → `lint` → `typecheck` (56 files) → `test` → `test-integration` →
`docs` (`--strict`). Gate: **`pixi run ci` exit 0 — 854 passed, 96.27% coverage (floor 90).**
`constants.py`, `local_dev/urls.py`, `views.py` and `persona_index.html` are each at 100%.

**Also run against PostgreSQL 17, not only the sqlite substitution.** `DATABASE_URL` pointed at a
`postgres:17` container, `pixi run test-cov --create-db`: 854 passed, 96.27%. This story writes
claim-derived values (`idp_subject`, `username`, `email`, `name`) through the mapper on a new code
path, which is the trigger story 2.4 established for a real-PostgreSQL run rather than the
schema-change trigger story 2.1 established.

**The review's behaviour-changing fixes were verified by reverting them.** The pre-fix view was
restored and the suite re-run: `test_a_deployed_run_answers_404_to_every_verb` (all three
parametrizations), `test_overlapping_claim_names_render_as_a_form_error` and
`test_a_refused_signin_leaves_no_account_behind` all fail against it. A regression test that
passes before the fix has proved nothing.

### Completion Notes List

All six tasks and every subtask are complete. No acceptance criterion is partially met. AC #5 is a
traceability marker and was deliberately **not** implemented — epics.md classes it as recording
where the obligation completes, not as an acceptance condition for this story.

**What was built.** `src/config/local_dev/constants.py` (the two constants, the single declaration
site until Epic 7), `views.py` (`persona_index` and `persona_signin`), `urls.py` (two routes, the
persona a path segment), a locality-gated `local_signin_urlpatterns()` in `src/config/urls.py`, and
`src/django_service/templates/local_dev/persona_index.html`. 15 unit tests and 19 integration tests
across two new files. `docs/development.md` gains a `### Signing in as a persona` subsection.

**Three spec-vs-tree gaps found and closed in the spec before implementing.**

1. *The Dev Notes' description of `src/config/urls.py` was stale.* It instructed "do not remove
   `obtain_auth_token` — that is Story 2.8's work" and gave line numbers for a file that no longer
   matches. Story 2.8 has landed and the route is gone. The description was rewritten against the
   tree at `b37e438`.
2. *`src/config/authorization/` was said not to exist.* It does; Epic 2 built it. The dependency
   list was replaced with names and line numbers re-verified against the current files rather than
   against the stories that introduced them.
3. *`ClaimsRejected` was unmentioned.* `src/config/authorization/exceptions.py`'s docstring names
   this story as its consumer — "Epic 3's local sign-in route turns it into a form error" — and the
   case is reachable on a fresh clone, where no configured identity claim means the mapper answers
   `identity key claim absent`. Left uncaught that is a 500 on the first thing a new developer
   clicks. Added to Task 2 with the reasoning.

**Variances, recorded rather than silent.**

1. *The mount decision is a function, not a bare `if` at module scope.* The whole suite runs in the
   `dev` pixi environment, which declares `COMPONENT_RUNTIME=local`, and a URLconf's locality branch
   is evaluated at import time — before any `monkeypatch.setenv`. A bare `if` would be assertable
   only by reloading `config.urls`, which mutates an object every later test resolves through.
   `local_signin_urlpatterns()` makes both branches directly callable with nothing to restore. This
   is Story 3.3's lesson 8 applied to a decision inheritance would otherwise hide.
2. *`Http404`, not `ImproperlyConfigured`, for the non-local refusal.* The spec permitted either.
   A view reached in a deployed component must not answer 500 with a configuration message: that
   announces the path exists and turns a guarded route into an error-rate signal. The seeding
   task's `ImproperlyConfigured` is right for something an operator invoked and wrong for something
   a stranger requested.
3. *No `require_POST`.* A decorator runs before the function body, so the locality guard would
   never be reached on a `GET` and the answer would be `405` — see the triage log's first entry.
4. *The form action is reversed in the view, not in the template.* A `{% url %}` tag needs a
   literal name, which would be a second declaration site inside a file the constants test scans.
5. *`include()` is not lazy in the sense the spec's wording implies.* Django imports the module as
   the mount is built. The property the spec actually wanted still holds — the import happens inside
   `local_signin_urlpatterns()`, so a deployed component never imports `config.local_dev.urls` — but
   nothing verifies that, which is now a deferred-work entry.
6. *The rejection branch catches `ImproperlyConfigured` as well as `ClaimsRejected`.* Task 2 named
   only the latter. Both are the same misconfiguration from the developer's chair.
7. *The refused-claims path rolls itself back.* `ATOMIC_REQUESTS` is on and a returned 400 commits.

**Out of scope, but real — flagged rather than patched.** Both are in `deferred-work.md`: the
400 response is served at the `POST`-only URL, so a browser refresh answers 405; and the
"a deployed component never imports `config.local_dev.urls`" claim, which three docstrings rest on,
is unverifiable in-process and needs the same subprocess test seam an earlier deferred entry
already asks for.

### File List

| Path | NEW / UPDATE |
| --- | --- |
| `src/config/local_dev/constants.py` | NEW |
| `src/config/local_dev/views.py` | NEW |
| `src/config/local_dev/urls.py` | NEW |
| `src/django_service/templates/local_dev/persona_index.html` | NEW |
| `tests/unit/test_local_dev_urls.py` | NEW |
| `tests/integration/test_local_dev_signin.py` | NEW |
| `src/config/urls.py` | UPDATE |
| `docs/development.md` | UPDATE |
| `_bmad-output/implementation-artifacts/deferred-work.md` | UPDATE (two entries) |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | UPDATE |
| `_bmad-output/implementation-artifacts/3-4-local-sign-in-is-a-url-route-that-drives-the-real-mapper.md` | UPDATE (this record) |
