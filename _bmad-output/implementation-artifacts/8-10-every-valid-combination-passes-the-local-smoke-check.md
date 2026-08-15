# Story 8.10: Every valid combination passes the local smoke check

Status: ready-for-dev

## Story

As a lead developer,
I want every combination proven to boot and authenticate with nothing installed,
so that the local-runnability claim covers the combination I actually ordered.

## Acceptance Criteria

**Traceability:** FR-33, FR-1, FR-3 · AD-30 · SC-4, SC-7

1. **Given** each of the six combinations
   **When** the smoke check runs with no database, cache, broker, object store or identity provider available
   **Then** the process boots, readiness returns 200, a persona completes an interactive sign-in and reaches a rendered admin index, one Bearer request passes through the real authentication class, and one rendered 404 is produced

2. **Given** a combination in which the Django admin is unreachable
   **When** the smoke check runs
   **Then** it fails

3. **Given** the database backend and the authentication mode
   **When** the combination space is counted
   **Then** neither is treated as a feature toggle
   **And** the space stays at six

4. **Given** the immovable-core assertion suite
   **When** any combination's gate runs
   **Then** it runs inside that gate
   **And** it is never pruned by any feature, because it is what defends the claim that the core still works after an excision

## Tasks / Subtasks

- [ ] Task 1: Build the smoke-check driver (AC: #1)
  - [ ] `tools/harness/smoke.py` (NEW, `machinery`) — for one materialized combination, start the component under its `combo-<id>` environment with `COMPONENT_RUNTIME=local` set (AD-13 puts it in each local pixi task's `env`), wait for the process to accept connections, run the five assertions, then terminate and report.
  - [ ] The five assertions, in order and all required: (a) the process boots; (b) `GET` readiness returns 200; (c) a persona completes an interactive sign-in and the admin index renders; (d) one `Authorization: Bearer <JWT>` request passes through the real authentication class; (e) one request to an unrouted path produces a rendered 404.
  - [ ] Nothing external runs: no PostgreSQL, no Redis, no broker, no object store, no identity provider. The five substitutions from Epic 3 plus Story 7.5's filesystem storage are what make this possible; the smoke check must not start any service, and must fail if it detects one being required.
  - [ ] Fail with the assertion that failed and the combination identifier. Never `print()`; report through `structlog`.

- [ ] Task 2: Make "rendered" mean rendered (AC: #1, #2)
  - [ ] The admin-index assertion must check for content the rendered template produces — the admin index's app-list markup — not merely a 200 status. A 200 with an empty body passes a status check and is exactly the excision damage AD-30 exists to catch.
  - [ ] The 404 assertion must run with `DEBUG = False` so Django uses the project's `404.html` handler rather than the debug traceback page, and must check for content from that template. `src/django_service/templates/` holds the error templates and `base.html`, which AD-29 keeps in every combination — revision 3 makes the whole rendering stack `core`, so this is unconditional rather than dependent on any selection.
  - [ ] The rendered pages must contain the navigation bar `base.html` includes from `_navbar.html`, and `_navbar.html` renders the **navigation registry** (AD-8), not literal links. Assert the bar rendered; do not assert a specific link, since the registry is empty until an app contributes to it. `home` and `about` no longer exist — do not assert on them and do not request `/` expecting a landing page.
  - [ ] Assert the response for the 404 is status 404 **and** carries the rendered template's content.

- [ ] Task 3: Drive the real authentication paths (AC: #1)
  - [ ] Interactive sign-in goes through the local persona sign-in **URL route** and no other mechanism (AD-21) — not a development authentication backend, not a management command that writes a session, not a query-parameter shim. Its URL name and prefix are fixed constants declared in `accelerator.toml`.
  - [ ] The Bearer request uses a JWT minted by the Epic 3 development task from the locally generated, gitignored keypair, and is verified by the **real** DRF `BaseAuthentication` subclass from Epic 2 — not a stub, not a patched class, not `force_authenticate`.
  - [ ] The persona must reach the admin as a staff user, which means the designated `Group` rows exist — provisioned by the `django_service` data migration (AD-27) that the persona seeding task calls rather than reimplements. If the smoke check has to create a group itself, the bootstrap deadlock AD-27 prevents has become invisible again; do not do it.

- [ ] Task 4: Build the immovable-core assertion suite (AC: #4)
  - [ ] `tests/integration/immovable_core/` (NEW package, disposition `core`) — the suite that travels with every combination and runs inside every combination's gate. Add `__init__.py`.
  - [ ] `test_admin_renders.py` — the admin index renders for a staff user in every combination.
  - [ ] `test_api_schema.py` — DRF serves an API described by its drf-spectacular generated schema.
  - [ ] `test_error_pages_render.py` — 403, 404 and 500 templates render and still extend `base.html` (AD-29).
  - [ ] `test_navigation_registry.py` — `base.html` includes `_navbar.html`, `_navbar.html` renders the registry rather than literal links, an entry's label is auto-escaped, an entry carrying a permission is filtered for a user without it, and a registered URL name that does not resolve is refused as `ImproperlyConfigured` at stage 2 (AD-8, AD-26). This is `core` in every combination because the registry is.
  - [ ] `test_user_profile_views.py` — the user detail and redirect views render, `users:detail` and `users:redirect` resolve, and `User.get_absolute_url()` (`src/django_service/users/models.py:19-26`) and `LOGIN_REDIRECT_URL` (`src/config/settings/base.py:140`) reverse them. Revision 3 makes these `core` routes present everywhere; revision 2's instruction to relocate them is superseded and must not be applied.
  - [ ] `test_correlated_logging.py` — a request emits structured JSON to stdout carrying `request_id`, `trace_id` and `span_id`.
  - [ ] `test_asgi_spans.py` — an ASGI request produces a span; the ASGI instrumentor is active in all six. Assert the Django and psycopg instrumentors are active too — they are `core` (`telemetry.py:134`, `:136`) and their absence is the precise damage a mis-marked `:134-137` region would cause.
  - [ ] `test_immovable_dependencies.py` — the immovable capabilities named in Story 7.4 are present: PostgreSQL declared as the deployed database, DRF with drf-spectacular, the Django admin, CORS handling, structlog, OpenTelemetry, environment-based configuration, static file serving, and a uvicorn/gunicorn process.
  - [ ] Every test in this package carries `@pytest.mark.integration`.

- [ ] Task 5: Make the suite unprunable (AC: #4)
  - [ ] Declare `tests/integration/immovable_core/` as `core` in `accelerator.toml`. It is the named exception to the rule that a feature's tests carry the feature's disposition.
  - [ ] `tests/unit/test_immovable_core_suite_is_core.py` (NEW) — assert no path under `tests/integration/immovable_core/` carries any `feature:*` disposition, and assert the suite is present in all six materialized trees. This is the assertion that keeps the suite unprunable; without it the declaration is a convention.
  - [ ] Assert the suite contains no import of any feature's code — a feature import would make it fail in the combinations that removed the feature, and someone would then prune it.

- [ ] Task 6: Wire both into the harness (AC: #1, #2, #4)
  - [ ] `tools/harness/run.py` (Story 8.8) runs the smoke check for every combination at the `merge` level (Story 8.9), after that combination's gate passes.
  - [ ] The immovable-core suite runs as part of each combination's `pixi run ci` — it is inside the materialized tree's `tests/`, so it runs there automatically. Assert it actually ran by checking the per-combination test report names it, rather than assuming collection found it.
  - [ ] `tests/unit/harness/test_combination_space.py` (NEW) — assert the combination space is six; assert the database backend, the authentication mode and the server-rendered interface are not features in `accelerator.toml` and appear in no combination identifier. `ui` in particular must be absent: revision 3 retired it, and a stray `feature:ui` entry would silently reinflate the space.

## Dev Notes

### Architecture Constraints

- **AD-30** (binding, and this is the story that carries it): "The smoke check asserts, for every combination, with no external service running: the process boots; readiness returns 200; a persona completes an interactive sign-in and reaches a **rendered admin index**; one Bearer request passes through the real authentication class; and one **rendered 404**. FR-1's consequence that an unreachable admin fails the smoke check is thereby true rather than assumed. Separately, a `core`-disposed immovable-core assertion suite runs inside every combination's gate and is never pruned by any feature. AD-20's coverage signal defends SC-2; **this suite is what defends SC-7, and nothing else does**."
- **The blindness AD-30 fixes**, stated because it is the reason the suite is not optional: "the harness detecting residue and being structurally blind to excision damage — a feature extraction that removes too much passes every existing check, because the removed thing's tests left with it, coverage measures only what remains, and the smoke check never renders the page that broke." Every design decision in this story follows from that sentence: the suite must be `core` so it does not leave with the feature; it must render rather than status-check; it must not import feature code.
- **Test location convention** (Consistency Conventions): "a feature's tests are `feature:<name>` and are pruned with it, **except the immovable-core assertion suite (AD-30), which is `core`**."
- **AD-21** (binding): "Local persona sign-in is exposed as a URL route and by no other mechanism — not a development authentication backend, not a management command that writes a session, not a query-parameter shim. Its URL name and path prefix are fixed constants declared in `accelerator.toml`."
- **AD-27** (binding): the designated `Group` and `Permission` rows are provisioned by a data migration inside `django_service`; "The local persona seeding task **calls that same mechanism** rather than reimplementing it — a task that creates groups itself is what makes the deadlock invisible to the harness."
- **AD-29** (binding, revision 3): "**The user-interface mechanism is part of that core, not a selectable feature.** `base.html`, `_navbar.html` and the navigation registry, the 403/404/500 templates, the form-styling configuration, static-file serving and the user profile views are all `core` and present in every combination." **FR-3 was rewritten**: it previously made the Django admin orthogonal to a *server-rendered UI feature*; that feature no longer exists. Nothing in this story may be conditioned on a UI selection, and no combination lacks a rendering stack. `home` and `about` are **deleted** as demonstration content, along with their `TemplateView`s in `src/config/urls.py` and `templates/pages/`.
- **AD-13** (binding): `COMPONENT_RUNTIME=local` is set in the `env` of each local pixi task, never in `[activation.env]`.
- **AD-3**: each combination's smoke check runs under its own pre-locked `combo-<id>` environment (Story 8.1), "never in an environment fat enough to hide an import it should not have".
- **SC-4** requires every valid combination to start, serve and authenticate a persona on a machine with nothing running. **SC-7** requires each of the six to serve an API described by its generated schema, render the admin, emit correlated structured logs, and produce spans for ASGI requests — which is exactly the immovable-core suite's content.
- **AD-8, the navigation registry**: an ordered contributed sequence, append-only in adopted-app-list order, whose entries are "data, never markup" — a label, a URL *name*, an optional permission the renderer filters on. Labels are auto-escaped and no entry carries raw HTML, which is why it is permitted where `MIDDLEWARE` and `AUTHENTICATION_BACKENDS` are refused. **Every registered URL name must resolve in the URLconf, refused as `ImproperlyConfigured` at stage 2** — the stage that has a resolved URLconf.
- Never a stub authentication class. Never `force_authenticate`. Never a 200-only assertion where the AC says "rendered".

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tools/harness/smoke.py` | NEW | The five-assertion smoke driver, `machinery`. |
| `tools/harness/run.py` | UPDATE | Created by Story 8.8, extended by 8.9 with `--level`. This story runs the smoke check at the `merge` level after each combination's gate. Preserve the run-all-then-fail behaviour, the level selection and the mandatory report. |
| `tests/integration/immovable_core/__init__.py` | NEW | `core`. |
| `tests/integration/immovable_core/test_admin_renders.py` | NEW | `core`. |
| `tests/integration/immovable_core/test_api_schema.py` | NEW | `core`. |
| `tests/integration/immovable_core/test_error_pages_render.py` | NEW | `core`. |
| `tests/integration/immovable_core/test_navigation_registry.py` | NEW | `core`. The registry is `core` in every combination (AD-8, AD-29). |
| `tests/integration/immovable_core/test_user_profile_views.py` | NEW | `core`. `users:detail` and `users:redirect` are core routes; `User.get_absolute_url()` (`src/django_service/users/models.py:19-26`) and `LOGIN_REDIRECT_URL` (`src/config/settings/base.py:140`) stand unchanged — both verified. |
| `tests/integration/immovable_core/test_correlated_logging.py` | NEW | `core`. Existing coverage of this behaviour lives in `tests/integration/test_request_logging.py`; move or mirror, do not duplicate an assertion that then drifts. |
| `tests/integration/immovable_core/test_asgi_spans.py` | NEW | `core`. Existing telemetry coverage lives in `tests/unit/test_telemetry.py` and `tests/unit/test_observability_init.py`. |
| `tests/integration/immovable_core/test_immovable_dependencies.py` | NEW | `core`. |
| `tests/unit/test_immovable_core_suite_is_core.py` | NEW | Asserts the suite carries no `feature:*` disposition and is present in all six. `machinery`. |
| `tests/unit/harness/test_combination_space.py` | NEW | Asserts the space is six and that the database backend, the authentication mode and the interface mechanism are not features. `machinery`. |
| `accelerator.toml` | UPDATE | Declares `tests/integration/immovable_core/` as `core`. |
| `tests/integration/test_template_rendering.py` | UPDATE | Exists today. Review against the new `test_error_pages_render.py` so the two do not assert the same thing differently; the immovable-core copy is the one that must travel. |

#### Project Structure Notes

`tests/integration/immovable_core/` is a NEW `core`-disposed test package. It sits under `tests/integration/`, consistent with the convention that accelerator and base tests live under `tests/` mirroring `src/` and carry the disposition of what they cover — here, the immovable core, which is `core`.

`tools/harness/` is `machinery` and was created by Story 8.8. `tests/unit/harness/` likewise.

The local sign-in route (Epic 3 Story 3.4), the persona seeding task (3.3), the development keypair and JWT minting task (3.5), the readiness endpoint (Epic 5 Story 5.3), the real Bearer authentication class (Epic 2 Story 2.7) and the group-provisioning data migration (Epic 2 Story 2.3) are all preconditions. None exists today — `src/config/authorization/` and `src/config/startup/` are not in the tree. This story is blocked on all of them.

### Testing Requirements

- Every immovable-core test carries `@pytest.mark.integration`, uses real resources under the local substitutions, and leaves state as found.
- The immovable-core suite must import nothing from any feature. Assert that mechanically in `tests/unit/test_immovable_core_suite_is_core.py` by parsing the suite's imports with `ast`, so a future addition cannot quietly couple it to Celery or Redis.
- The smoke check is not a pytest suite — it is a harness step that starts the real process. Its own logic is unit-tested in `tests/unit/harness/`; its execution is a `merge`-level harness step.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` in force (AD-20). Materialized-combination gates run the floor advisory until the Story 8.8 bring-up report exists.
- The 404 assertion requires `DEBUG = False`; make that explicit in the smoke check's settings selection rather than relying on the ambient settings module.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-30]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-21]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-27]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — test location and the immovable-core exception
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.10]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.4] — the immovable capability list
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-8] — the navigation registry and the stage-2 URL-name resolution
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md:154-164] — FR-3 as rewritten: the interface mechanism is immovable core; `home`/`about` removed
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md:873] — SC-4, verified after the revision-3 PRD amendment
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md:879] — SC-7, "each of the six materialized combinations"
- [Source: tests/integration/test_template_rendering.py] — exists today
- [Source: tests/integration/test_request_logging.py] — exists today

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
