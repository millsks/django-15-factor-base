---
baseline_commit: ef5f99a26b6c37e26f11507211623b051afc06ed
baseline_revision: ef5f99a26b6c37e26f11507211623b051afc06ed
final_revision: 8e200e4
review_loop_iteration: 0
followup_review_recommended: true
status: done
---

# Story 1.4: No network surface exists beneath Django's routing

Status: done

## Story

As a platform engineer,
I want the scope-dispatching ASGI wrapper deleted so `asgi.py` exposes Django's application directly,
so that no credential or network surface exists where the route allowlist cannot see it.

## Acceptance Criteria

**Traceability:** AD-16 · supports FR-17, FR-47 · SC-5

1. **Given** `src/config/websocket.py` and the scope-dispatching wrapper exist
   **When** this story lands
   **Then** both are deleted
   **And** `asgi.py` exposes Django's ASGI application directly

2. **Given** the wrapper carries a `[tool.coverage.run] omit` entry
   **When** the wrapper is deleted
   **Then** that omit entry is deleted in the same change

3. **Given** the wrapper is gone
   **When** the suite runs
   **Then** requests resolve through Django's URL resolver
   **And** the ASGI instrumentor still produces spans

4. **Given** a protocol handled below the URL resolver is proposed later
   **When** it is designed
   **Then** it carries its own authentication story and its own carrier entry
   **And** the documentation that travels with a component states this

## Tasks / Subtasks

- [x] Task 1 — Delete the websocket module (AC: #1)
  - [x] Delete `src/config/websocket.py` in its entirety. It is 13 lines defining one coroutine, `websocket_application(scope, receive, send)`, that accepts every connection unauthenticated and answers `ping` with `pong!`. No other module imports it except `src/config/asgi.py:33`.
  - [x] Confirm before deleting: `grep -rn "websocket" src/ tests/ pixi.toml pyproject.toml docs/` returns only `src/config/websocket.py`, `src/config/asgi.py:32-33,39-40`, and `pyproject.toml:168`. Anything else found must be handled in this change too.

- [x] Task 2 — Reduce `src/config/asgi.py` to Django's application (AC: #1, #3)
  - [x] Delete the scope dispatcher at `src/config/asgi.py:36-43` — the `async def application(scope, receive, send)` that branches on `scope["type"]` and raises `NotImplementedError` for anything that is neither `http` nor `websocket`.
  - [x] Delete the import at `:32-33` (`from config.websocket import websocket_application` and its "Import websocket application here" comment).
  - [x] Rename `django_application` at `:30` to `application`, so the module-level ASGI callable is `application = get_asgi_application()`. **The name `application` must be preserved** — `pixi.toml:190` (`serve`) and `pixi.toml:197` (`serve-reload`) both invoke `uvicorn config.asgi:application`. Do not rename it to `django_application`. *(Corrected in the follow-up review pass: the original text also cited `config/settings/base.py` as naming the ASGI application. It does not — `base.py:89` declares `WSGI_APPLICATION` and there is no `ASGI_APPLICATION` setting anywhere in the tree. The two pixi tasks are the whole constraint, and they are now pinned by `TestTheServedApplicationIsThisModule`.)*
  - [x] Preserve the ordering that already exists: `os.environ.setdefault("DJANGO_SETTINGS_MODULE", ...)` (`:23`), then `configure_observability()` (`:25-27`), then `get_asgi_application()`. `configure_observability` must run before the application is constructed or the Django/ASGI instrumentors do not attach.
  - [x] Preserve the `# noqa: E402` markers on the post-setdefault imports; they are load-bearing, not cosmetic.
  - [x] Do **not** remove the `sys.path` insert at `:17-20` in this story — that is Story 1.6 (AD-7). If both stories land in the same branch, Story 1.6 owns that hunk.

- [x] Task 3 — Delete the coverage omit entry in the same change (AC: #2)
  - [x] Remove `"src/config/websocket.py",` from `pyproject.toml` `[tool.coverage.run] omit` — it is line `:168`, the last entry in the list.
  - [x] **Keep** `"src/config/wsgi.py"` (`:166`) and `"src/config/asgi.py"` (`:167`) and their shared comment "deployment entrypoints: no logic, exercised by the WSGI/ASGI server rather than by the test suite". Those two entries are legitimate under AD-20 and Story 1.5 declares them; only the websocket entry goes.
  - [x] AD-16 states the module, the wrapper and the omit entry "are all deleted together". Deleting the module in one commit and the omit entry in another does not satisfy this AC.

- [x] Task 4 — State the forward rule in travelling documentation (AC: #4)
  - [x] Add a short section to `docs/observability.md` or `docs/development.md` (whichever the dev agent judges the better home; state the choice in Completion Notes) recording AD-16's rule: any future protocol handled below Django's URL resolver is a designed feature with its own authentication story and its own entry in the carrier, never an inherited handler.
  - [x] AC #4's "documentation that travels with a component" is NFR-8's rule. `docs/` is not yet dispositioned — `accelerator.toml` does not exist until Epic 7. Write the section now; its `core`-vs-`machinery` disposition is Epic 7 Story 7.1's decision. Note this in Completion Notes so the disposition author finds it.

- [x] Task 5 — Tests (AC: #1, #2, #3)
  - [x] New `tests/unit/test_asgi_surface.py`: import `config.asgi` and assert `application` is the object returned by `django.core.asgi.get_asgi_application()` — specifically, that it is an instance of `django.core.handlers.asgi.ASGIHandler`, not a plain coroutine function. Assert `config.asgi` has no attribute named `websocket_application` and no attribute named `django_application`.
  - [x] In the same file, assert `importlib.util.find_spec("config.websocket") is None` — the module is gone, not merely unreferenced.
  - [x] In the same file, parse `pyproject.toml` with `tomllib` and assert no entry in `[tool.coverage.run].omit` mentions `websocket`.
  - [x] New `tests/integration/test_asgi_request_path.py`, every test marked `@pytest.mark.integration`: drive a request through the ASGI application (Django's `AsyncClient` or a direct `application(scope, receive, send)` call with an `http` scope) and assert it resolves through the URL resolver — a known route returns its status and an unknown path returns 404 from Django's handler rather than `NotImplementedError`.
  - [x] In the same file, assert the ASGI instrumentor still produces a span for that request. Use an in-memory span exporter (`opentelemetry.sdk.trace.export.in_memory_span_exporter.InMemorySpanExporter`) and assert at least one span was recorded. `opentelemetry-instrumentation-asgi` is declared at `pixi.toml:66` and its rationale comment at `:62-65` explains that without it `_is_asgi_supported` is False and ASGI requests silently produce no span — that comment is precisely the regression this test guards.
  - [x] Existing tests that must keep passing unchanged: `tests/unit/test_observability_init.py`, `tests/unit/test_telemetry.py`, `tests/integration/test_request_logging.py`.

## Dev Notes

### Architecture Constraints

- **AD-16 — No network surface exists beneath Django's routing.** Rule, verbatim: "`asgi.py` exposes Django's ASGI application directly. `src/config/websocket.py`, the scope-dispatching wrapper, and its `[tool.coverage.run] omit` entry are all deleted together. Any future protocol handled below Django's URL resolver is a designed feature with its own authentication story and its own entry in the carrier, never an inherited handler." **Prevents:** "a credential or network surface that the route allowlist cannot see because it is not a route."
- **Why this is Epic 1 and not Epic 4.** `epics.md:237`: deleting the sub-router network surface with its coverage omit entry is a "precondition for Epic 4's allowlist to be complete rather than merely present." FR-17's allowlist inspects the resolved URLconf (FR-15); a handler that is not a route is invisible to it. The current `websocket_application` accepts every connection with no authentication whatsoever.
- **AD-26 — Predicates resolve objects, never strings.** The forward reason the surface must be a route: the stage-2 predicates resolve the URLconf and refuse routes by view callable. Nothing beneath the resolver can be reached by that mechanism.
- **AD-20** — the coverage `omit` list is "a closed, carrier-declared surface" and the precedent it names for narrowing is `[tool.coverage.run] omit` in this very tree. Story 1.5 closes that list; this story removes the one entry that would otherwise be declared and then be wrong.
- **FR-47:** "ASGI request tracing — the ASGI instrumentor active in all six combinations." AC #3's span assertion is what keeps this true across the deletion.

### Source Tree — files to touch

| Path | NEW or UPDATE | What changes |
| --- | --- | --- |
| `src/config/websocket.py` | DELETE | 13 lines. Defines `websocket_application(scope, receive, send)`: an unauthenticated accept-everything loop answering `ping` with `pong!`. Sole importer is `src/config/asgi.py:33`. Nothing preserved. |
| `src/config/asgi.py` | UPDATE | Today (44 lines): module docstring; `import os, sys`, `from pathlib import Path`; `from django.core.asgi import get_asgi_application`; `sys.path` insert at `:17-20`; `DJANGO_SETTINGS_MODULE` setdefault at `:23`; `configure_observability()` at `:25-27`; `django_application = get_asgi_application()` at `:30`; websocket import at `:32-33`; scope dispatcher at `:36-43`. **Delete** `:32-33` and `:36-43`; **rename** `django_application` → `application`. **Preserve** the settings setdefault, the observability call and their ordering, and the `# noqa: E402` markers. The `sys.path` block at `:17-20` belongs to Story 1.6. |
| `pyproject.toml` | UPDATE | `[tool.coverage.run] omit` at `:162-169`. Remove only `"src/config/websocket.py"` (`:168`). Keep `*/migrations/*`, `*/tests/*`, `**/*.egg-info/**`, `src/config/wsgi.py`, `src/config/asgi.py` and the comment at `:166-167`. |
| `sonar-project.properties` | UPDATE | **Found during the first review pass, not in the original plan.** `sonar.coverage.exclusions` is a second carrier of the same exemption AC #2 deletes; Task 1's grep was not scoped to reach it. Remove `src/config/websocket.py` from that list too. |
| `src/config/urls.py` | UPDATE | **Found during the first review pass.** A comment in the `settings.DEBUG` static-serving block described the block as being "for local web socket development" — residue the Task 1 grep missed because it is spelled as two words. |
| `docs/observability.md` or `docs/development.md` | UPDATE | Records AD-16's forward rule for sub-resolver protocols. |
| `tests/unit/test_asgi_surface.py` | NEW | Asserts the ASGI callable's identity, the module's absence, and the omit list. |
| `tests/integration/test_asgi_request_path.py` | NEW | Asserts URL-resolver routing and span production, `@pytest.mark.integration`. |

**Verified today (2026-08-15):** `src/config/websocket.py` exists (13 lines). The scope dispatcher exists at `src/config/asgi.py:36-43`. The omit entry exists at `pyproject.toml:168`. All three of AD-16's named deletions hold as written.

### Testing Requirements

- `tests/unit/test_asgi_surface.py`: no I/O beyond reading `pyproject.toml` and importing `config.asgi`; no marker.
- `tests/integration/test_asgi_request_path.py`: `@pytest.mark.integration` on every test; the marker is declared at `pyproject.toml:155-157`. Must leave no state behind — use `pytest-django`'s transactional fixtures and reset the tracer provider/exporter in teardown.
- Naming mirrors `src/config/asgi.py`, per the spine's test-location convention.
- Coverage: deleting `websocket.py` and its omit entry means the ASGI module's remaining lines are still omitted via `src/config/asgi.py` at `pyproject.toml:167`. The 90% floor including templates stands (AD-20); `--cov-fail-under=90` at `pixi.toml:196`.
- Test disposition (spine §Consistency Conventions): these cover `core` paths and will be dispositioned `core` in Epic 7.

#### Project Structure Notes

After this story `src/config/` contains `__init__.py`, `api_router.py`, `asgi.py`, `celery_app.py`, `urls.py`, `wsgi.py`, `observability/`, `settings/` — one module closer to the Structural Seed, which lists no `websocket.py`. The seed's `authorization/` and `startup/` subpackages arrive in Epics 2 and 4.

Variance worth recording: `src/config/wsgi.py` retains its own `sys.path` insert and `configure_observability()` call and is unaffected by this story. Both entrypoints keep their coverage omit entries, which Story 1.5 will declare as the closed list.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.4]
- [Source: _bmad-output/planning-artifacts/epics.md:237] — deletion is a precondition for Epic 4's allowlist.
- [Source: _bmad-output/planning-artifacts/epics.md:165] — AD-16 restated in the epic preamble.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-16]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/epics.md:93] — FR-47.

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m]

### Debug Log References

`pixi run ci` — exit 0. precommit, build, typecheck, lint, test-cov all pass;
198 tests, coverage 92.31% (floor 90%). (183 at implementation; 190 after the
first review pass added the non-HTTP refusal, span-name and exclusion-residue
tests; 194 after the second; 198 after the third added the pixi-target pin, the
observability-ordering assertion, the forward-rule assertion and the prose
coverage-carrier check.)

### Completion Notes List

- **Task 1.** `src/config/websocket.py` deleted. The confirmation grep found one
  reference the story did not list: `docs/development.md` named `websocket.py`
  among the omitted deployment entrypoints in the Coverage section. Handled in
  this change, per the task's "anything else found must be handled" clause.
- **Task 2.** `src/config/asgi.py` is now 30 lines: docstring, imports, the
  `sys.path` insert (untouched — Story 1.6 owns it), the settings setdefault,
  `configure_observability()`, then `application = get_asgi_application()`. The
  scope dispatcher and the websocket import are gone. The callable is named
  `application`, as `pixi run serve` / `serve-reload` require. Both `# noqa:
  E402` markers on the post-setdefault import are preserved.
- **Task 3.** `"src/config/websocket.py"` removed from `[tool.coverage.run]
  omit` in the same change. `src/config/wsgi.py`, `src/config/asgi.py` and their
  shared comment are untouched; Story 1.5 still declares them.
- **Task 4 — documentation home: `docs/development.md`.** Chosen over
  `docs/observability.md` for three reasons. The rule is about *what the
  accelerator serves and how it is authenticated*, not about instrumentation —
  `observability.md` is end-to-end about logs, traces and the OTEL_* contract,
  and the rule would be the only non-observability topic in it. `development.md`
  already carries the adjacent material: "Serving the application" describes
  `config.asgi:application` under uvicorn and gunicorn, and the new section sits
  directly beneath it. And `development.md` is where the stale `websocket.py`
  reference lived, so both halves of the documentation change stay in one file.
  The section is `## Protocols below the URL resolver`.
- **Task 5.** `tests/unit/test_asgi_surface.py` (no marker; reads only
  checked-in repository configuration) and
  `tests/integration/test_asgi_request_path.py` (all marked `integration`).
  Counts as of the second review pass: **18 unit and 9 integration, 27 in
  total** — 7 and 5 at implementation, then 14 and 9 after the first pass. The
  integration tests call
  `config.asgi.application(scope, receive, send)` directly with a raw `http`
  scope rather than going through Django's test client, so they exercise the
  object uvicorn actually invokes.
- **Note for Epic 7 Story 7.1 (disposition).** The new section in
  `docs/development.md` is `## Protocols below the URL resolver`, between
  `## Serving the application` and `## Coverage`. It states AD-16's forward
  rule and is the artefact AC #4 is satisfied by, so it is `core` content
  regardless of how the rest of `docs/development.md` is dispositioned. If that
  file is split, this section must travel with whatever carries `asgi.py`.
  `src/config/asgi.py` also carries a one-line comment pointing at it; a rename
  of the section or the file breaks that pointer.
- **Telemetry state, worth knowing.** Importing `config.asgi` runs
  `configure_observability()` for real at collection time, which installs the
  Django/Celery/psycopg/redis instrumentors process-wide for the rest of the
  suite. That is required in the integration module — the span assertion cannot
  be made against stubbed instrumentors. The review pass removed the same import
  from the *unit* module for this reason: see the triage log below. The
  `recorded_spans` fixture attaches an `InMemorySpanExporter` to the live
  provider and restores the provider's processor list in teardown, so no
  processor is left behind for later tests.
- **Second coverage-exclusion carrier (review pass).** `sonar.coverage.exclusions`
  in `sonar-project.properties` is a second carrier of the same exemption AD-16
  deletes, and Task 1's grep was not scoped to reach it. It is now cleaned and
  asserted alongside `[tool.coverage.run] omit`, including a residue test that
  fails when either carrier names a path that no longer exists. Story 1.5, which
  closes the omit list, should treat both carriers as the closed surface.

### File List

- `src/config/websocket.py` — DELETED
- `src/config/asgi.py` — MODIFIED
- `src/config/urls.py` — MODIFIED (review pass)
- `pyproject.toml` — MODIFIED
- `sonar-project.properties` — MODIFIED (review pass)
- `docs/development.md` — MODIFIED
- `tests/unit/test_asgi_surface.py` — NEW
- `tests/integration/test_asgi_request_path.py` — NEW
- `_bmad-output/implementation-artifacts/6-2-asgi-requests-produce-spans.md` —
  MODIFIED (second follow-up review pass). Not a file this story sets out to
  touch, but this change made one of its Dev Notes false in a way that would
  have steered FR-47's own story away from the deployed callable. Corrected
  there rather than left for 6.2 to discover.

## Review Triage Log

### 2026-08-15 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 9: (high 1, medium 6, low 2)
- defer: 1: (high 0, medium 1, low 0)
- reject: 8: (high 0, medium 0, low 8)
- addressed_findings:
  - `[high]` `[patch]` `tests/unit/test_asgi_surface.py` imported `config.asgi` at
    module scope, which runs `configure_observability()` for real: it instruments
    Django, Celery, psycopg and redis process-wide and, when
    `OTEL_EXPORTER_OTLP_ENDPOINT` is set, attaches a `BatchSpanProcessor` whose
    exporter reaches the network — inside `pixi run test`, which `pixi.toml`
    advertises as unit tests with no I/O, and against the invariant
    `tests/unit/test_telemetry.py` states in its own docstring. Rewritten to
    assert the ASGI surface statically with `ast` over `src/config/asgi.py`
    (exactly one module-level `application`, assigned from an unwrapped
    `get_asgi_application()` call; no function named `application`; no name bound
    other than `SRC_DIR` and `application`; no websocket import). The runtime
    identity assertion moved to the integration module, which imports
    `config.asgi` legitimately. This deviates from Task 5's letter, which put the
    `isinstance` check in the unit file; the spec's intent is preserved and the
    project's unit/integration rule decided the placement.
  - `[medium]` `[patch]` `sonar-project.properties:24` still listed
    `src/config/websocket.py` in `sonar.coverage.exclusions` — a second carrier of
    the exemption AD-16 deletes "together" with the module, missed because Task 1's
    grep covered `src/ tests/ pixi.toml pyproject.toml docs/` only. Entry removed;
    `TestCoverageExclusionsAreClosed` now asserts both carriers and adds
    `test_every_excluded_source_path_still_exists`, which fails on any exclusion
    naming a deleted file — the shape that let this one survive.
  - `[medium]` `[patch]` The new `docs/development.md` section claimed
    "everything the server answers is a route", which is false:
    `whitenoise.middleware.WhiteNoiseMiddleware` (`base.py:167`) serves collected
    static assets from `__call__` without calling `get_response`, so those
    responses never reach the resolver. Left unqualified this becomes the artefact
    Epic 4 Story 4.6 quotes for "the URLconf is a complete description of the
    network surface". The section now names the exception, says why it is
    accepted, and requires any completeness claim to address it explicitly.
  - `[medium]` `[patch]` `test_the_span_describes_the_resolved_request` asserted
    `http.method == "GET"`, a value copied verbatim from the scope the test itself
    builds — it could not fail for the reason its docstring gave, and could not
    detect a bypassed resolver. Replaced with an assertion on the span *name*
    (`"GET home"`), which is resolution-derived: verified that a resolved route
    yields `GET home` and `/no-such-page/` yields `GET`. A paired test asserts the
    unresolved path produces a span without the route name. This also removes the
    `OTEL_SEMCONV_STABILITY_OPT_IN` attribute-rename fragility.
  - `[medium]` `[patch]` No test drove a non-HTTP scope, so AC #1's behavioural
    claim rested entirely on the type of a module attribute — a re-added handler
    accepting unauthenticated websocket connections would have passed the whole
    suite. Added `TestNonHttpScopesAreRefused`: websocket and lifespan scopes must
    raise Django's `ValueError("… can only handle ASGI/HTTP connections …")`.
  - `[medium]` `[patch]` `isinstance(application, ASGIHandler)` accepts
    `ASGIStaticFilesHandler` (confirmed: it subclasses `ASGIHandler`), which serves
    everything under `STATIC_URL` from inside itself without consulting the
    URLconf — precisely AD-16's prohibited shape, passing every assertion the story
    added. Tightened to `type(...) is ASGIHandler` in the integration module.
  - `[medium]` `[patch]` The integration `receive` awaits an `asyncio.Event` nobody
    sets, so a regression that made the handler await `receive` twice would hang
    rather than fail; there is no `pytest-timeout` in the project, so CI would stall
    to its job limit. The drive is now wrapped in `asyncio.timeout(10)`.
  - `[medium]` `[patch]` With `OTEL_SDK_DISABLED=true` — the documented kill switch
    `telemetry._is_disabled` honours — the span fixture errored with a message
    accusing `config.asgi` of not installing a provider. The reviewers proposed
    skipping; `tests/unit/test_suite_policy.py`, built by Story 1.2, forbids
    `pytest.skip` in integration tests, and it caught the attempt. Failing is
    correct here (FR-47 requires the instrumentor active in every combination), so
    only the message was fixed: it now names the missing provider and appends
    "OTEL_SDK_DISABLED is set" when that is the cause.
  - `[low]` `[patch]` `src/config/urls.py:31` still read "for local web socket
    development" — residue the Task 1 grep could not find because it is spelled as
    two words. Reworded.
  - `[low]` `[patch]` The doc section said "`asgi.py` stays exactly one line" (the
    file is 33) and pointed at "the carrier" without naming it. Both corrected;
    the carrier is now identified as `accelerator.toml`.

**Deferred (1).** WhiteNoise's static surface is invisible to Epic 4's route
allowlist. Pre-existing, and the decision — allowlist coverage for
middleware-level file serving, or an explicit out-of-scope declaration — is
Story 4.6's. Recorded in `deferred-work.md`.

**Rejected (8).** The substantive ones: the redundant `pytest.mark.integration`
in `pytestmark` (the conftest adds it, but Task 5 required it explicitly);
`assert not hasattr(config.asgi, "django_application")` as an over-tight name pin
(Task 5 required it verbatim); `FileNotFoundError` when the suite is run from an
unpacked sdist (the gate never does, and `tests/unit/test_gate_contract.py`
already sets the precedent of reading repository config from a unit test);
`test_the_deployment_entrypoints_are_still_omitted` encoding Story 1.5's
decisions and Story 7.8's eventual move of the omit list (speculative, and the
assertion is correct today); `test_a_second_known_route_is_served` being weak
(the new span-name test now carries the discriminating power); `body_events.pop()`
popping from the tail (changed to `pop(0)` while editing, but a one-element list
made it a non-issue); adding `--ws none` / `--lifespan off` to the `serve` tasks
(the process model is Story 5.2's, and Django's `ValueError` is already the
correct refusal — now tested); and the observation that both test files were
untracked mid-review (this workflow commits at the end).

### 2026-08-15 — Review pass (follow-up)

- intent_gap: 0
- bad_spec: 0
- patch: 9: (high 2, medium 4, low 3)
- defer: 1: (high 0, medium 1, low 0)
- reject: 7: (high 0, medium 2, low 5)
- addressed_findings:
  - `[high]` `[patch]` `docs/development.md`'s "One known exception, and it is
    not a protocol handler" was false, and it is the sentence Story 4.6 was told
    to quote. Two more middleware answer without reaching the resolver, both
    verified against the installed sources: `SecurityMiddleware` returns an SSL
    redirect from `process_request` (`SECURE_SSL_REDIRECT` is on in
    `production.py:51`), and `CorsMiddleware.__call__` returns
    `check_preflight(request)` for CORS preflight `OPTIONS` — a policy-bearing
    response, not an inert file. The section now frames the middleware chain
    itself as the standing exception, names all three, and says the list must be
    re-checked whenever `MIDDLEWARE` changes.
  - `[high]` `[patch]` The previous pass rewrote `tests/unit/test_asgi_surface.py`
    to parse rather than import, on the stated grounds that importing
    `config.asgi` would run `configure_observability()` inside `pixi run test`.
    That premise is wrong: `src/config/__init__.py` imports `config.celery_app`,
    which calls `configure_observability()` at module scope, so pytest-django
    loading `config.settings.test` has already installed the instrumentors
    before collection — and the file's own
    `importlib.util.find_spec("config.websocket")` imports the same parent
    package. The docstring now states the real reason for reading the source
    (only a static read can see a binding the test settings' branch does not
    take) and says plainly that it buys nothing on side effects. The same
    inaccuracy in the integration fixture's docstring ("installed once, at
    `config.asgi` import") is corrected to name the `config` package.
  - `[medium]` `[patch]` All three structural assertions iterated
    `_asgi_module().body`, so a dispatcher reintroduced as
    `if settings.DEBUG: application = Wrapper(...)` was invisible to every one
    of them — and `src/config/urls.py:31` shows that `settings.DEBUG` gate is a
    shape this package already uses. They now use `ast.walk`, and
    `test_application_is_assigned_from_get_asgi_application` additionally
    asserts the single assignment it finds is in `module.body`, i.e. bound
    unconditionally.
  - `[medium]` `[patch]` `test_application_is_assigned_from_get_asgi_application`
    matched the *name* `get_asgi_application`, so
    `from config.shim import wrap as get_asgi_application` would have satisfied
    it. Added `test_get_asgi_application_is_djangos_own`, asserting the symbol
    is imported from `django.core.asgi` and nowhere else.
  - `[medium]` `[patch]` `test_a_span_is_recorded_for_an_asgi_request` asserted
    only that some span existed. `configure_observability()` installs the
    psycopg, redis and Celery instrumentors process-wide, so a database span
    satisfied it while the request span — the only thing FR-47 is about — could
    be missing. Now asserts `SpanKind.SERVER` is among the recorded kinds.
  - `[medium]` `[patch]` `test_an_unresolved_path_produces_a_span_without_a_route_name`
    asserted only `"GET home" not in names`, which any span set lacking that one
    name satisfies. Now asserts the positive value (`"GET"`), keeping the
    negative as a second line.
  - `[low]` `[patch]` `test_no_other_name_is_bound_to_an_asgi_callable` pinned
    the exact roster `{"SRC_DIR", "application"}`, which Story 1.6 breaks when it
    removes the `sys.path` insert — failing with a message about a name count
    rather than about AD-16. Replaced with
    `test_application_is_the_only_name_that_looks_like_an_asgi_callable`, which
    names the invariant by shape and survives that deletion.
  - `[low]` `[patch]` `_sonar_coverage_exclusions()` returned the first matching
    key; Sonar uses the last, so a duplicated declaration would let the test
    report a cleaned list while the shipping one still named the deleted module.
    It now collects every declaration and fails on more than one.
  - `[low]` `[patch]` The replacement comment at `src/config/urls.py:31` was
    still inaccurate — the block is gated on `settings.DEBUG`, not on which
    server is running, and its usual consumer is `runserver`, which is not ASGI.
    Reworded. Also added the two review-pass files (`sonar-project.properties`,
    `src/config/urls.py`) to the Source Tree table, which recorded them only in
    the File List.
  - `[medium]` `[patch]` AC #4's artifact — the `docs/` section — was observed by
    nothing, though `src/config/asgi.py` points at it by name and Epic 4 is told
    to consult it. Added `TestTheForwardRuleIsDocumented`: the heading exists,
    `asgi.py` still names it, and the section names each short-circuiting
    middleware.

**Deferred (1).** No test pins `MIDDLEWARE`, so the corrected exception list is
prose that can go stale when a fourth short-circuiting middleware is added.
Pinning the chain is Story 4.6's call, alongside the WhiteNoise entry from the
previous pass. Recorded in `deferred-work.md`.

**Rejected (7).** `--ws none` / `--lifespan off` on the `serve` tasks and the
`uvicorn-standard` dependency (re-raised; still Story 5.2's process model, and
Django's `ValueError` refusal is tested). The redundant `django_db` and
`integration` markers in `pytestmark` (re-raised; Task 5 required the explicit
marker). Driving a `STATIC_URL` path to pin the WhiteNoise exception (needs
`collectstatic`, and the exception is now pinned in prose by a test). Checking
glob-shaped coverage exclusions for existence (`src/config/*.py` resolves to
files that do exist; the check adds no discrimination). The `[tool.coverage.run]`
comment "deployment entrypoints: no logic" now being false for `asgi.py` — real,
but Story 1.5 closes that list and necessarily reads the comment. The
integration run exporting spans to a live collector when
`OTEL_EXPORTER_OTLP_ENDPOINT` is set — pre-existing and the intended behaviour of
`configure_observability`. `accelerator.toml` not existing yet — Task 4 states
this explicitly and Epic 7 creates it.

### 2026-08-15 — Review pass (follow-up, second)

- intent_gap: 0
- bad_spec: 0
- patch: 14: (high 1, medium 8, low 5)
- defer: 2: (high 0, medium 2, low 0)
- reject: 1: (high 0, medium 0, low 1)
- addressed_findings:
  - `[high]` `[patch]` The `docs/development.md` exception list was short a
    fourth entry and named the wrong re-check trigger.
    `django.middleware.common.CommonMiddleware` (`base.py:170`) raises
    `PermissionDenied` on a `DISALLOWED_USER_AGENTS` match and returns a
    redirect when `PREPEND_WWW` is set, both from `process_request` — verified
    against the installed source. Neither setting is set here, which is exactly
    the footing `SecurityMiddleware` was already listed on. That exposed the
    deeper error: the section said the list "has to be re-checked whenever
    `MIDDLEWARE` changes", but for two of the four entries the arming change is
    a *settings* change with `MIDDLEWARE` untouched, so the stated trigger could
    not fire. The section now names four entries, states both triggers, notes
    that `local.py` appends to the list it enumerates (debug_toolbar — checked,
    does not short-circuit), and separates the after-resolution shape
    (`AccountMiddleware` turning the resolver's 404 on `/accounts/` into a login
    redirect) from the before-resolution criterion it uses.
  - `[medium]` `[patch]` The `CorsMiddleware` bullet said the preflight answer
    carries "the configured origin/method/header policy", which reads as
    origin-gated and is not what happens. `check_preflight()` returns a bare
    `HttpResponse` whenever `is_enabled()` and the method is `OPTIONS`;
    `is_enabled()` is `CORS_URLS_REGEX` (`^/api/.*$`) or a signal, with no
    origin involvement, and the origin policy is applied afterwards by *omitting*
    a header from a response that ships either way. So every path under `/api/`
    answers a preflight, route or not. Since this section is what Story 4.6 is
    told to consult, the wrong reading made a policy-free surface look
    policy-bearing. Restated accurately.
  - `[medium]` `[patch]` Nothing pinned the module the servers actually load.
    Every AD-16 assertion is anchored to `src/config/asgi.py` by path or import,
    so retargeting `pixi.toml:190,197` at a sibling module holding a dispatcher
    passed the entire suite. Added
    `TestTheServedApplicationIsThisModule::test_every_server_task_serves_the_asgi_module`,
    which walks every `tasks` table in `pixi.toml` and requires each
    uvicorn/gunicorn command to name `config.asgi:application`. Verified by
    mutation.
  - `[medium]` `[patch]` `TestTheForwardRuleIsDocumented` pinned the heading, the
    pointer from `asgi.py` and the middleware list — but never AC #4's actual
    rule, which is that a sub-resolver protocol carries its own authentication
    story and its own carrier entry. Deleting those three bullets left the class
    green. Added `test_the_section_states_the_forward_rule`.
  - `[medium]` `[patch]` The Coverage section of `docs/development.md` is a third
    carrier of the exclusion list — the one the original `websocket.py` residue
    was found in — and nothing read it: reverting the sentence to name the
    deleted module left the whole suite green. Added
    `test_the_documented_entrypoints_match_the_omit_list`, which parses the
    sentence and compares it against `[tool.coverage.run] omit`.
  - `[medium]` `[patch]` `_sonar_coverage_exclusions()` split on newlines, but
    Sonar reads the file with Java `.properties` semantics, where a trailing
    backslash continues a value. An exclusion written on a continuation line was
    invisible to both the websocket check and the residue check — the exact
    shape the residue check exists to catch. The reader now joins continuations
    first (verified by mutation), and `sonar.exclusions` — a stronger exemption,
    since a path dropped from analysis is dropped from coverage with it — is now
    read alongside `sonar.coverage.exclusions`.
  - `[medium]` `[patch]` `configure_observability()` in `asgi.py`, whose position
    before `get_asgi_application()` Task 2 calls load-bearing for FR-47, was
    observed by nothing: `config/__init__.py` imports `config.celery_app`, which
    calls it at module scope, so deleting the call from `asgi.py` leaves every
    span test green. Added
    `test_observability_is_configured_before_the_application_is_built`, a static
    assertion — the only kind that can see it. Verified by mutation.
  - `[medium]` `[patch]` With `OTEL_TRACES_SAMPLER=always_off` the three span
    tests failed accusing `config.asgi` of producing no span, when the
    instrumentor was active and the sampler was dropping it. `configure_telemetry`
    names no sampler, so the SDK default reads the environment. Same treatment as
    the `OTEL_SDK_DISABLED` message in the first pass: the failure is correct
    (FR-47, and `test_suite_policy.py` forbids skipping), so only the diagnostic
    changed — it now names the sampler when one can suppress sampling. Confirmed
    by running the module under that variable.
  - `[medium]` `[patch]` This change made a Dev Note in
    `6-2-asgi-requests-produce-spans.md:59` false and actively misleading: it
    states in the present tense that `asgi.py:33-43` still wraps
    `django_application`, and instructs Story 6.2 *not* to route its FR-47 span
    test through `config.asgi.application` "because that wrapper is on its way
    out". The deletion inverted that — `config.asgi.application` is now Django's
    own handler and the object uvicorn loads, so it is the better target than
    `AsyncClient`'s subclass. Corrected, along with the same file's
    `asgi.py:33-43` source reference.
  - `[low]` `[patch]` `src/config/urls.py:31` said the DEBUG block serves
    "collected static files". `staticfiles_urlpatterns()` routes to
    `staticfiles.views.serve`, which resolves through `finders.find()` — the
    source directories, never `STATIC_ROOT` — so it contradicted the WhiteNoise
    bullet added in the same change. Third rewrite of this comment; reworded to
    say what the view actually does and why it is not WhiteNoise's surface.
  - `[low]` `[patch]` `test_the_section_exists` was a plain substring check, so
    `### Protocols below the URL resolver` passed while the section's level
    changed and the `"\n## "` bound used to slice it silently ran past its end.
    Now pinned at line start with its level.
  - `[low]` `[patch]` `docs/development.md`'s "`tests/unit/` — no database,
    network, or filesystem access" is contradicted by this story's own unit
    module, which reads four repository files. Reconciled: the rule now permits
    reading checked-in configuration, which several tests assert against.
  - `[low]` `[patch]` Task 2 justified preserving the name `application` partly
    on "`config/settings/base.py` names the ASGI application through the same
    path". It does not — `base.py:89` declares `WSGI_APPLICATION` and no
    `ASGI_APPLICATION` setting exists anywhere. The pixi line numbers were stale
    too (179/186 → 190/197). Corrected in place, with the correction marked; the
    genuine half of the constraint is now the pinned one.
  - `[low]` `[patch]` Completion Notes still claimed 7 and 5 tests and the Debug
    Log still said 190; the real figures are 18 and 9 (27 in the two modules) and
    198 in the suite. Both updated, with the per-pass history kept.

**Deferred (2).** `src/config/wsgi.py`'s inherited docstring recommends
replacing Django's WSGI application with a delegating wrapper — AD-16's shape in
the twin entrypoint, and the one `WSGI_APPLICATION` actually names — with no
test pinning what that module binds. And the two entrypoints disagree on their
default settings module, so `pixi run serve`, advertised as "production-like
ASGI", falls back to `config.settings.local` and DEBUG. Both pre-existing, both
recorded in `deferred-work.md`.

**Rejected (1).** That the artifact under review differs from the one at HEAD
(the `## Auto Run Result` section stripped, `status` back to `in-review`): that
is this workflow's own mechanism for starting a follow-up pass, not a defect.

## Auto Run Result

Status: done

### Summary of implemented change

`src/config/websocket.py` and the scope-dispatching wrapper in
`src/config/asgi.py` are deleted, so `asgi.py` binds one name —
`application = get_asgi_application()` — and every connection the server answers
is decided by Django's URL resolver. The deleted handler accepted every
websocket connection with no authentication at all; because it was not a route,
Epic 4's allowlist (FR-17, which inspects the resolved URLconf) could never have
seen it. AD-16 requires the module, the wrapper and the coverage exemption to go
together, and they do — in `[tool.coverage.run] omit`, in
`sonar.coverage.exclusions`, and in the Coverage prose of `docs/development.md`,
the second and third carriers found in the review passes.

The ordering `asgi.py` already had is preserved exactly: the settings
`setdefault`, then `configure_observability()`, then `get_asgi_application()`.
That order is load-bearing — the instrumentors must attach before the handler is
built, or ASGI requests silently produce no spans (FR-47). The `sys.path` insert
belongs to Story 1.6 and was not touched.

This pass changed no runtime behaviour either. Its through-line was that several
of the story's own claims were being asserted somewhere weaker than where they
could fail. Nothing pinned `pixi.toml` to the module every AD-16 assertion reads,
so the deleted surface could return in a sibling module with the suite green.
Nothing observed `configure_observability()` in `asgi.py`, because the `config`
package already calls it. Nothing read the Coverage sentence that carried the
original residue. And `TestTheForwardRuleIsDocumented` pinned the heading of AC
#4's artifact but not the rule inside it. Each is now asserted where it fails,
and each new guard was verified by mutating the source and watching the specific
test go red.

The one high-severity finding was again in the prose that Story 4.6 is told to
quote: the below-resolver exception list was short a fourth middleware
(`CommonMiddleware`), and the trigger it gave for re-checking itself — "whenever
`MIDDLEWARE` changes" — could not fire for two of the four entries, which are
armed by settings rather than by the list. The `CorsMiddleware` bullet was
separately wrong in the direction that flatters: it described an origin-gated
policy response where the code returns a bare 200 for any `/api/` path, route or
not, before any origin is considered.

### Files changed

| Path | One-line description |
| --- | --- |
| `src/config/websocket.py` | DELETED. 13 lines; one coroutine that accepted every connection unauthenticated and answered `ping` with `pong!`. |
| `src/config/asgi.py` | The scope dispatcher and the websocket import are gone; `django_application` is renamed to `application`, the name `pixi run serve` invokes. The `sys.path` insert (Story 1.6), the settings setdefault, `configure_observability()` and both `# noqa: E402` markers are untouched. |
| `src/config/urls.py` | Comment on the DEBUG-gated static block, rewritten a third time: it now says what `staticfiles.views.serve` actually does (finders, not `STATIC_ROOT`) rather than contradicting the WhiteNoise bullet added in the same change. |
| `pyproject.toml` | `"src/config/websocket.py"` removed from `[tool.coverage.run] omit`; the two deployment-entrypoint entries and their comment kept for Story 1.5. |
| `sonar-project.properties` | The same exemption removed from `sonar.coverage.exclusions`. |
| `docs/development.md` | `## Protocols below the URL resolver` records AD-16's forward rule. This pass corrected the below-resolver middleware list to four entries with both of its re-check triggers, restated what a CORS preflight actually returns, separated the after-resolution shape from the criterion, and made the Coverage sentence say it is a third carrier that a test now checks. |
| `tests/unit/test_asgi_surface.py` | Walks `asgi.py`'s AST for the ASGI surface and the observability ordering, pins `pixi.toml`'s serve targets to that module, asserts the closure of every coverage-exclusion carrier including continuation-line residue, and pins both the heading and the rule of AC #4's documentation. 18 tests. |
| `tests/integration/test_asgi_request_path.py` | Drives raw ASGI scopes against the real callable: routing, non-HTTP refusal, SERVER-span production, and the exact-type check that `ASGIStaticFilesHandler` would otherwise slip past. Span failures now name a suppressing sampler when one is set. 9 tests. |
| `_bmad-output/implementation-artifacts/6-2-asgi-requests-produce-spans.md` | A Dev Note this change made false — telling Story 6.2 not to test through `config.asgi.application` because the wrapper was on its way out — corrected to point at the now-unwrapped callable and the test shape this story wrote. |

### Review findings breakdown

Three reviewers (adversarial, edge-case, verification-gap) ran in parallel
without prior context, each told what the previous passes had already addressed
or rejected. After deduplication and severity assignment: **14 patches applied**
(1 high, 8 medium, 5 low), **2 deferred**, **1 rejected**. Detail is in the
Review Triage Log above. No finding was an intent gap or a spec defect, so no
loopback was triggered and `review_loop_iteration` stays 0.

### Verification performed

- `pixi run ci` — exit code 0. pre-commit (ruff check, ruff format, mypy), build,
  mypy over `src/`, ruff over the tree, and the full suite with coverage all
  pass. **198 tests, coverage 92.31%** against the 90% floor.
- **Every new guard was mutation-tested**, not just run: adding `websocket.py`
  back to the Coverage prose, retargeting `pixi run serve` at
  `config.dispatcher:application`, hiding a websocket exclusion on a
  backslash-continued Sonar line, deleting AC #4's rule bullets, deleting
  `configure_observability()` from `asgi.py`, and dropping a middleware from the
  documented list each made exactly the intended test fail, and each source file
  was restored from a backup and re-verified clean afterwards.
- The sampler diagnostic was confirmed by running the integration module under
  `OTEL_TRACES_SAMPLER=always_off`: the three span tests fail, as they should,
  and now say `OTEL_TRACES_SAMPLER=always_off may be dropping it`.
- The middleware claims were read from the installed sources, not inferred:
  `corsheaders.middleware.CorsMiddleware.check_preflight` /`is_enabled` and
  `django.middleware.common.CommonMiddleware.process_request`. `base.py` was
  grepped to confirm `DISALLOWED_USER_AGENTS`, `PREPEND_WWW` and
  `ASGI_APPLICATION` are all unset.

### Residual risks

- **The exception list is still prose.** Four names are now asserted to appear in
  the section, but nothing pins `MIDDLEWARE` itself, and nothing pins the
  settings that arm two of the four. A fifth short-circuiting middleware, or
  setting `PREPEND_WWW`, still fails no test. Deferred to Story 4.6 alongside the
  WhiteNoise entry.
- **The documentation assertions are substring checks over Markdown.** They catch
  deletion and rename, not a paragraph rewritten to say something false while
  keeping the required phrases — which is precisely the failure this pass and the
  last one both had to fix by hand.
- **FR-47 says "all six combinations"; one is verified.** The span tests run
  under `config.settings.test` only. The fixture's hard failure on a disabled SDK
  or a suppressing sampler is correct, but its scope claim is broader than what
  executes.
- **The `recorded_spans` fixture restores private OpenTelemetry state** by
  reassigning `_active_span_processor._span_processors`. It is guarded by an
  assertion that the attribute exists, so an SDK upgrade fails loudly rather than
  silently leaking a processor — but any processor another fixture added during
  the test would be discarded.
- **`_server_task_commands()` reads `pixi.toml` only.** The production process is
  gunicorn with the uvicorn worker class, and that command lives in deployment
  configuration outside this repository; the new pin covers the two pixi tasks
  and nothing beyond them.
