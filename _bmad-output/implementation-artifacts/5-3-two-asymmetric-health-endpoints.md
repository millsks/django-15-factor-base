# Story 5.3: Two asymmetric health endpoints

Status: ready-for-dev

## Story

As an operator,
I want liveness and readiness to mean deliberately different things,
so that a brief database outage degrades a component instead of crash-looping the estate.

## Acceptance Criteria

**Traceability:** FR-42 · AD-22 · NFR-2 · SC-3

1. **Given** the liveness endpoint
   **When** it is probed
   **Then** it checks nothing external
   **And** the process either responds or it does not

2. **Given** the readiness endpoint
   **When** it is probed
   **Then** it checks that every required database answers
   **And** returns non-200 when one does not

3. **Given** a process that has booted but has not yet contacted its database
   **When** readiness is probed
   **Then** it returns non-200 until the first successful contact

4. **Given** a rolling deploy in which an older replica runs against a newer schema
   **When** readiness is probed
   **Then** it does not re-check migrations
   **And** the older replica is not reported unready for a schema difference backwards-compatible migrations exist to permit

5. **Given** no health route exists today
   **When** this story lands
   **Then** both endpoints are built rather than adapted

## Tasks / Subtasks

- [ ] Task 1 — Create the health concern module (AC: #1, #2, #3, #5)
  - [ ] `src/config/health/__init__.py` — re-export `liveness`, `readiness`, and the drain-state accessors Story 5.4 will set.
  - [ ] `src/config/health/state.py` — module-level process state with two flags and no external dependency: `_first_contact_made: bool` (starts `False`) and `_draining: bool` (starts `False`, written by Story 5.4). Expose `mark_first_contact()`, `first_contact_made()`, `begin_drain()`, `is_draining()`. Keep it a plain module, not a Django app, and not a cache entry — the cache is Django's in-process backend in eight of twelve combinations and this state is per-process by design.
  - [ ] `src/config/health/views.py` — two function-based views with full type hints and Google docstrings. Do **not** use DRF: `REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]` is `IsAuthenticated` (`src/config/settings/base.py:362`) and a probe carries no credential.

- [ ] Task 2 — Implement liveness (AC: #1)
  - [ ] `liveness(request: HttpRequest) -> HttpResponse` returns `HttpResponse(status=200)` with a short plain-text body. It reads no setting that performs I/O, opens no database connection, touches no cache, resolves no `request.user`, and makes no network call.
  - [ ] Decorate with `@never_cache` and `@require_GET` (add `HEAD` — probes commonly send `GET`; `require_GET` already permits `HEAD`).
  - [ ] **Middleware hazard to verify, not assume:** `django_structlog.middlewares.RequestMiddleware` (`src/config/settings/base.py:175`) binds `user_id`, which resolves `request.user` and can load the session — a database query on the liveness path, which would break NFR-2. Verify with the `django_assert_num_queries(0)` assertion in Task 5 and, if it fails, exclude the health URLs from that binding by the mechanism django-structlog provides rather than by removing the middleware.
  - [ ] Never let liveness raise: it either answers 200 or the process is not answering. Do not add a `try/except` that converts an error into a 500 — there is nothing to catch, and a bare `except:` is forbidden.

- [ ] Task 3 — Implement readiness (AC: #2, #3, #4)
  - [ ] `readiness(request: HttpRequest) -> JsonResponse`. Order of evaluation, exactly: (1) if `is_draining()` return 503 immediately (Story 5.4 depends on this ordering); (2) for each required database alias, open a cursor and execute `SELECT 1`; (3) on total success call `mark_first_contact()` and return 200.
  - [ ] Required aliases come from `component.toml` via `src/config/component/loader.py` (Story 5.1): a database is required unless the declaration says `required = false` (AD-9). Iterate `django.db.connections` for aliases present in `settings.DATABASES`, and refuse to silently skip an alias that `settings.DATABASES` has and `component.toml` does not declare — treat it as required and log a warning naming the alias.
  - [ ] Before the first success, `first_contact_made()` is `False` and readiness must return non-200 even if the check itself has not yet been attempted — the flag is what AC #3 asserts, not the query result.
  - [ ] Catch `django.db.utils.OperationalError` and `django.db.utils.DatabaseError` specifically per alias — never a bare `except:`, never `except X: pass` — and emit a `structlog` event carrying the alias and the exception class before returning 503. Body: `{"status": "unready", "databases": {"<alias>": "ok" | "error"}}`; on success `{"status": "ready", ...}`.
  - [ ] **Readiness never re-checks migrations** (AC #4). Do not import or call `MigrationExecutor`, `migrate --check`, `showmigrations`, or anything that reads `django_migrations`. Record the reason in the module docstring: during a rolling deploy an older replica may legitimately run against a newer schema.
  - [ ] Status code for unready is `503`; do not use 500 (an error) or 200-with-a-body (unreadable by a probe).

- [ ] Task 4 — Route the two endpoints (AC: #5)
  - [ ] `src/config/health/urls.py` exposing `urlpatterns = [path("livez", liveness, name="liveness"), path("readyz", readiness, name="readiness")]`.
  - [ ] In `src/config/urls.py`, add `path("", include("config.health.urls"))` **before** the existing `path("", TemplateView...)` home route at `:14` so probe paths resolve first. Preserve every existing entry, including the `DEBUG`-gated blocks at `:30-32` and `:48-75`.
  - [ ] Do not place the health routes behind `ADMIN_URL`, `api/`, or `accounts/`. They must be resolvable with no authentication and must not appear in the DRF schema — they are not DRF views, so `drf-spectacular` will not pick them up; confirm with the existing `tests/integration/users/test_api_openapi.py` if the schema snapshot changes.
  - [ ] **Host header note for the deployment repository, not an AC:** platform probes often send the pod IP as `Host`. `ALLOWED_HOSTS` is environment-driven (`src/config/settings/production.py:21`); record in `docs/deployment.md` that the probe must send a `Host` header the component allows, or the deployment repository must include the pod IP range. Do not weaken `ALLOWED_HOSTS` in the component to work around it.

- [ ] Task 5 — Tests (AC: #1, #2, #3, #4, #5)
  - [ ] `tests/unit/test_health_views.py`: liveness returns 200 with `RequestFactory`; liveness performs **zero queries** — assert with pytest-django's `django_assert_num_queries(0)` (this is the mechanical form of AC #1 and of NFR-2); readiness returns 503 while `first_contact_made()` is `False`; readiness returns 503 while `is_draining()` is `True` even with a healthy database; the readiness view's module imports nothing from `django.db.migrations`.
  - [ ] Reset the module state between tests with an autouse fixture — the flags are process-global and a leaked `True` makes a later test pass for the wrong reason.
  - [ ] `tests/integration/test_health.py` (`@pytest.mark.integration`): readiness returns 200 against the real test database and the body reports every required alias `ok`; readiness returns 503 when a required connection raises `OperationalError` (patch the connection's `cursor`); after an unapplied migration is introduced readiness still returns 200 — the explicit AC #4 assertion that migrations are never re-checked.
  - [ ] Assert both routes resolve by name (`reverse("liveness")`, `reverse("readiness")`) and are reachable unauthenticated with the anonymous test client.

- [ ] Task 6 — Document the probe contract (AC: #1, #2, #4)
  - [ ] `docs/deployment.md` `## Health endpoints`: what each path means, that liveness must be wired to the liveness probe and readiness to the readiness probe and never the reverse, that readiness is non-200 from process start until first successful database contact, and that readiness deliberately does not re-check migrations.
  - [ ] Ensure `docs/deployment.md` is registered in `mkdocs.yml` `nav`; `pixi run docs` is `mkdocs build --strict`.

## Dev Notes

### Architecture Constraints

- **AD-22** — *Rule:* "Liveness checks nothing external — the process answers or it does not. Readiness checks that every required database answers (AD-9), returns non-200 from process start until first successful contact, and never re-checks migrations, because during a rolling deploy an older replica may legitimately run against a newer schema." *Prevents:* "a liveness probe that turns a brief database outage into an estate-wide crash loop."
- **NFR-2** — "Liveness touches nothing external — **a system-wide invariant any future health work must preserve.**" This is not a property of one view; anything added to the liveness path later inherits it.
- **AD-9** — "Readiness treats a contributed database as required unless `component.toml` declares it optional." The requiredness field is read, never inferred from the alias name.
- **AD-10** — The epoch record lives in a database table "not in `django.core.cache`: eight of twelve combinations have no Redis, so the cache is Django's in-process backend". The same reasoning forbids storing readiness state in the cache; it is per-process module state.
- **NFR-1** — "the checks make no network call and no query beyond migration state" — that constrains the *refusal* stages, not readiness. Readiness's `SELECT 1` is a deliberate, separate contract; do not conflate the two mechanisms or move readiness into `src/config/startup/`.
- **NFR-3** — Statelessness: "nothing shared through local disk or process memory across replicas." The readiness flags are per-process observations of that process's own history, not shared state, and must never be written to disk or shared.
- **AD-16** — "`asgi.py` exposes Django's ASGI application directly… Any future protocol handled below Django's URL resolver is a designed feature with its own authentication story and its own entry in the carrier, never an inherited handler." The health endpoints are Django URL routes and nothing else — do not implement them as ASGI middleware, which would put a network surface beneath the router that the FR-17 allowlist cannot see.
- **AD-26** — Predicates resolve objects, never strings. Applied here: the readiness check resolves connection objects and iterates declared aliases; it never string-matches an engine name or a URL.
- **Consistency Conventions** — "Cross-cutting concerns with several independent consumers and no natural owner live under `src/config/<concern>/`." Health has three consumers: the URLconf, Story 5.4's signal handler, and Epic 8's smoke check. "Runtime errors… Nothing is swallowed silently." "Logging: structured, JSON to stdout, carrying `request_id`, `trace_id`, `span_id`."
- **Project standards** — Pixi is the only runner. Python 3.14 only. Full type hints on public signatures, Google-style docstrings, line length 120. `X | Y`, `list[X]`, `dict[K, V]`. Never `print()`; never stdlib `logging` — `structlog` only.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/health/__init__.py` | **NEW** | Public surface of the concern. |
| `src/config/health/state.py` | **NEW** | Per-process `first_contact` and `draining` flags with accessor functions. Story 5.4 writes `begin_drain()`. |
| `src/config/health/views.py` | **NEW** | `liveness` (nothing external) and `readiness` (every required database, never migrations). |
| `src/config/health/urls.py` | **NEW** | `livez` and `readyz` routes. |
| `src/config/urls.py` | UPDATE | Today: `urlpatterns` at `:13-29` (home `:14`, about `:15-19`, admin `:21`, users `:23`, allauth `:24`, media `static()` `:28`), a `DEBUG` staticfiles block `:30-32`, an API block `:35-46` including `obtain_auth_token` at `:39`, and a `DEBUG` error-page block `:48-75`. **Change:** insert the health include ahead of the home route. **Preserve:** everything else, including `obtain_auth_token` — its removal is FR-6/Epic 2's work, not this story's. |
| `src/config/component/loader.py` | read only | Story 5.1's loader; readiness reads per-database requiredness from it. |
| `docs/deployment.md` | UPDATE (NEW if 5.1/5.2 have not landed) | Adds `## Health endpoints`. |
| `mkdocs.yml` | UPDATE | Register `deployment.md` in `nav`. |
| `tests/unit/test_health_views.py` | **NEW** | Liveness zero-query assertion, readiness state machine. |
| `tests/integration/test_health.py` | **NEW** | Readiness against the real database; the migrations-not-re-checked assertion. |

**Confirmed by search:** no health, readiness or liveness route, view, or test exists anywhere in `src/` or `tests/` today. AC #5's "built rather than adapted" is literal — there is nothing to adapt. (Stale bytecode for a removed `tests/integration/test_zz_probe.py` exists in `__pycache__`; the source file is gone and must not be resurrected.)

### Testing Requirements

- Unit: `tests/unit/test_health_views.py` — `RequestFactory`, no database except where the fixture demands it, milliseconds. The `django_assert_num_queries(0)` assertion on liveness is the load-bearing one; do not replace it with an inspection of the view body.
- Integration: `tests/integration/test_health.py` — marked `@pytest.mark.integration`. `tests/integration/conftest.py:12-19` also auto-marks everything under that directory; state the marker explicitly regardless. Tests must leave state as found — reset the module flags in an autouse fixture in both files.
- Test disposition (spine Consistency Conventions): health is `core`, so these tests are `core` and are never pruned; they run inside every combination's gate.
- AD-20: coverage floor is ninety percent **including templates**, everywhere, with `COVERAGE_CORE=ctrace` in force (`pixi.toml:145-150`). Do not add `src/config/health/` to `[tool.coverage.run] omit` (`pyproject.toml:162-169`) — that list is a closed, carrier-declared surface under AD-20 and growing it is the narrowing the rule exists to prevent. Every 503 branch needs a test.
- Inner loop `pixi run test`; boundary-crossing changes also `pixi run test-integration`. Done when `pixi run ci` exits 0.

#### Project Structure Notes

- `src/config/health/` is a new `src/config/<concern>/` sibling of `observability/`. The Structural Seed lists `settings/`, `observability/`, `authorization/`, `startup/` and does not name `health/`; the seed is not a closed list and the Consistency Conventions rule for cross-cutting concerns governs. Recorded as a deliberate variance, the same one Story 5.1 records for `src/config/component/`.
- **Dependency:** Story 5.1 must have landed — readiness reads per-database requiredness from `component.toml`. If it has not, do not inline a hardcoded alias list; land 5.1 first.
- **Consumed by Story 5.4:** `begin_drain()` and the drain-first ordering in `readiness` exist here so that Story 5.4 adds only a signal handler. Do not defer the `_draining` flag to 5.4.
- **Consumed by Epic 8:** AD-30's smoke check asserts "readiness returns 200" per combination with no external service running — which in the local substitution set means sqlite answers. Nothing here needs to know that.
- AD-9's contributed-database chain is a *future* consumer: readiness must iterate every configured alias rather than assuming `default`, so that Epic 9 adds a database without editing this view.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-22]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-9]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-10]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-16]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-30]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.3]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-42]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#NFR-2]
- Repository state: `src/config/urls.py:13-29, 35-46`; `src/config/settings/base.py:57-78` (DATABASES), `:164-179` (MIDDLEWARE), `:357-364` (REST_FRAMEWORK); `src/config/settings/production.py:21` (ALLOWED_HOSTS); `tests/integration/conftest.py:12-19`.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
