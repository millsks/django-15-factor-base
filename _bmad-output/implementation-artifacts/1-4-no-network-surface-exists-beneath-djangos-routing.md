---
baseline_commit: ef5f99a26b6c37e26f11507211623b051afc06ed
baseline_revision: ef5f99a26b6c37e26f11507211623b051afc06ed
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
  - [x] Rename `django_application` at `:30` to `application`, so the module-level ASGI callable is `application = get_asgi_application()`. **The name `application` must be preserved** — `pixi.toml:179` (`serve`) and `pixi.toml:186` (`serve-reload`) both invoke `uvicorn config.asgi:application`, and `config/settings/base.py` names the ASGI application through the same path. Do not rename it to `django_application`.
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
190 tests, coverage 92.31% (floor 90%). (183 at implementation; 190 after the
review pass added the non-HTTP refusal, span-name and exclusion-residue tests.)

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
- **Task 5.** `tests/unit/test_asgi_surface.py` (7 tests, no marker, no I/O
  beyond reading `pyproject.toml`) and
  `tests/integration/test_asgi_request_path.py` (5 tests, all marked
  `integration`). The integration tests call
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

## Auto Run Result

Status: done

### Summary of implemented change

`src/config/websocket.py` and the scope-dispatching wrapper in
`src/config/asgi.py` are deleted, so `asgi.py` now binds one name —
`application = get_asgi_application()` — and every connection the server answers
is resolved by Django's URL resolver. The deleted handler accepted every
websocket connection with no authentication at all; because it was not a route,
Epic 4's allowlist (FR-17, which inspects the resolved URLconf) could never have
seen it. AD-16 requires the module, the wrapper and the coverage exemption to go
together, and they do — in `[tool.coverage.run] omit` and, found during review,
in `sonar.coverage.exclusions`, a second carrier of the same exemption that the
story's grep was not scoped to reach.

The ordering `asgi.py` already had is preserved exactly: the settings
`setdefault`, then `configure_observability()`, then `get_asgi_application()`.
That order is load-bearing — the instrumentors must attach before the handler is
built, or ASGI requests silently produce no spans (FR-47). The `sys.path` insert
belongs to Story 1.6 and was not touched.

The review pass changed no runtime behaviour. It closed the gap between what the
tests asserted and what they claimed to assert: the story verified the deletion
structurally (a type, some absent attribute names) but never behaviourally, so a
re-added handler accepting unauthenticated websocket connections would have
passed the whole suite, and the one span assertion checked a value the test
itself had written into the scope. It also removed a real side effect the spec
had not anticipated — the unit test imported `config.asgi`, instrumenting the
process and, with an OTLP endpoint configured, opening a network exporter inside
`pixi run test`.

### Files changed

| Path | One-line description |
| --- | --- |
| `src/config/websocket.py` | DELETED. 13 lines; one coroutine that accepted every connection unauthenticated and answered `ping` with `pong!`. |
| `src/config/asgi.py` | The scope dispatcher and the websocket import are gone; `django_application` is renamed to `application`, the name `pixi run serve` invokes. The `sys.path` insert (Story 1.6), the settings setdefault, `configure_observability()` and both `# noqa: E402` markers are untouched. |
| `src/config/urls.py` | Review pass: a comment still described static serving as being "for local web socket development". |
| `pyproject.toml` | `"src/config/websocket.py"` removed from `[tool.coverage.run] omit`; the two deployment-entrypoint entries and their comment kept for Story 1.5. |
| `sonar-project.properties` | Review pass: the same exemption removed from `sonar.coverage.exclusions`, the second carrier AD-16 covers. |
| `docs/development.md` | New `## Protocols below the URL resolver` recording AD-16's forward rule, and the stale `websocket.py` mention in the Coverage section removed. Review pass qualified the completeness claim with WhiteNoise's static surface and named `accelerator.toml` as the carrier. |
| `tests/unit/test_asgi_surface.py` | NEW. Asserts the ASGI surface statically with `ast` — no import, so no instrumentation — plus the absence of the module and the closure of both coverage-exclusion carriers, including a residue test for exclusions naming deleted files. |
| `tests/integration/test_asgi_request_path.py` | NEW. Drives raw ASGI scopes against the real callable: three routing tests, two non-HTTP refusal tests, three span tests, and the exact-type check that `ASGIStaticFilesHandler` would otherwise slip past. |

### Review findings breakdown

Three reviewers (adversarial, edge-case, verification-gap) ran in parallel
without prior context. After deduplication and severity assignment: **9 patches
applied** (1 high, 6 medium, 2 low), **1 deferred**, **8 rejected**. Detail is in
the Review Triage Log above. No finding was an intent gap or a spec defect, so no
implementation loopback was triggered; `review_loop_iteration` stays 0.

The single high-severity finding was that the unit test's module-scope
`import config.asgi` runs `configure_observability()` for real. Verified against
the source: `configure_telemetry` attaches `BatchSpanProcessor(OTLPSpanExporter())`
whenever `OTEL_EXPORTER_OTLP_ENDPOINT` is set, so a developer with tracing
configured locally — the setup `docs/observability.md` documents — would have had
`pixi run test` start an exporter thread and reach the network.

One reviewer proposal was rejected by the repository itself: skipping the span
tests when `OTEL_SDK_DISABLED` is set tripped `tests/unit/test_suite_policy.py`,
the guard Story 1.2 built to stop integration tests dodging the gate. Failing is
the correct behaviour, so only the misleading assertion message was fixed.

### Verification performed

- `pixi run ci` — **exit 0**, run to completion after the review patches. All
  five steps clean: pre-commit, build, `mypy src/` strict, `ruff check .`,
  `pytest tests/` → **190 passed**, coverage **92.31%** against the 90% floor.
- Claims checked directly rather than taken from the reviewers: the Sonar
  exclusion line and the `urls.py` comment were read in place; WhiteNoise's
  middleware position confirmed at `src/config/settings/base.py:167`;
  `issubclass(ASGIStaticFilesHandler, ASGIHandler)` confirmed True in the dev
  environment; span names confirmed empirically as `GET home` for a resolved
  route and `GET` for an unresolved path, which is what makes the new assertion
  meaningful; and `OTEL_SDK_DISABLED=true` confirmed to produce the corrected
  failure message.
- `grep -rn "websocket" src/ tests/ pixi.toml pyproject.toml docs/` now returns
  only the intentional mentions: the new tests and the one sentence in
  `docs/development.md` explaining what the rule prevents.

### Residual risks

- **The static surface is still invisible to the allowlist.** This story closes
  the websocket half of `epics.md:237`'s precondition for Epic 4. WhiteNoise
  serves collected assets below the resolver and is deferred to Story 4.6; the
  documentation now refuses to let that claim be inherited silently.
- **The `recorded_spans` fixture reaches into OpenTelemetry SDK internals.** No
  public detach exists and `set_tracer_provider` refuses to override, so the
  fixture snapshots and restores `_active_span_processor._span_processors` to
  leave no processor behind. It is now guarded — if those internals move under
  the `>=1.44,<2` pin, the failure names the SDK rather than raising an opaque
  `AttributeError`.
- **Integration collection installs telemetry process-wide.** Importing
  `config.asgi` instruments Django, Celery, psycopg and redis for the whole run.
  This is required for the span assertions and the suite is green with it; the
  unit suite no longer participates.
- **`docs/` has no disposition yet.** The new section is `core` content by
  argument, not by declaration, until Epic 7 Story 7.1 writes `accelerator.toml`.
  A note for that author is in the Completion Notes.
