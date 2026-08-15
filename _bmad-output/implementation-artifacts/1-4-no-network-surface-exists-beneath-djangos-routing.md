# Story 1.4: No network surface exists beneath Django's routing

Status: ready-for-dev

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

- [ ] Task 1 — Delete the websocket module (AC: #1)
  - [ ] Delete `src/config/websocket.py` in its entirety. It is 13 lines defining one coroutine, `websocket_application(scope, receive, send)`, that accepts every connection unauthenticated and answers `ping` with `pong!`. No other module imports it except `src/config/asgi.py:33`.
  - [ ] Confirm before deleting: `grep -rn "websocket" src/ tests/ pixi.toml pyproject.toml docs/` returns only `src/config/websocket.py`, `src/config/asgi.py:32-33,39-40`, and `pyproject.toml:168`. Anything else found must be handled in this change too.

- [ ] Task 2 — Reduce `src/config/asgi.py` to Django's application (AC: #1, #3)
  - [ ] Delete the scope dispatcher at `src/config/asgi.py:36-43` — the `async def application(scope, receive, send)` that branches on `scope["type"]` and raises `NotImplementedError` for anything that is neither `http` nor `websocket`.
  - [ ] Delete the import at `:32-33` (`from config.websocket import websocket_application` and its "Import websocket application here" comment).
  - [ ] Rename `django_application` at `:30` to `application`, so the module-level ASGI callable is `application = get_asgi_application()`. **The name `application` must be preserved** — `pixi.toml:179` (`serve`) and `pixi.toml:186` (`serve-reload`) both invoke `uvicorn config.asgi:application`, and `config/settings/base.py` names the ASGI application through the same path. Do not rename it to `django_application`.
  - [ ] Preserve the ordering that already exists: `os.environ.setdefault("DJANGO_SETTINGS_MODULE", ...)` (`:23`), then `configure_observability()` (`:25-27`), then `get_asgi_application()`. `configure_observability` must run before the application is constructed or the Django/ASGI instrumentors do not attach.
  - [ ] Preserve the `# noqa: E402` markers on the post-setdefault imports; they are load-bearing, not cosmetic.
  - [ ] Do **not** remove the `sys.path` insert at `:17-20` in this story — that is Story 1.6 (AD-7). If both stories land in the same branch, Story 1.6 owns that hunk.

- [ ] Task 3 — Delete the coverage omit entry in the same change (AC: #2)
  - [ ] Remove `"src/config/websocket.py",` from `pyproject.toml` `[tool.coverage.run] omit` — it is line `:168`, the last entry in the list.
  - [ ] **Keep** `"src/config/wsgi.py"` (`:166`) and `"src/config/asgi.py"` (`:167`) and their shared comment "deployment entrypoints: no logic, exercised by the WSGI/ASGI server rather than by the test suite". Those two entries are legitimate under AD-20 and Story 1.5 declares them; only the websocket entry goes.
  - [ ] AD-16 states the module, the wrapper and the omit entry "are all deleted together". Deleting the module in one commit and the omit entry in another does not satisfy this AC.

- [ ] Task 4 — State the forward rule in travelling documentation (AC: #4)
  - [ ] Add a short section to `docs/observability.md` or `docs/development.md` (whichever the dev agent judges the better home; state the choice in Completion Notes) recording AD-16's rule: any future protocol handled below Django's URL resolver is a designed feature with its own authentication story and its own entry in the carrier, never an inherited handler.
  - [ ] AC #4's "documentation that travels with a component" is NFR-8's rule. `docs/` is not yet dispositioned — `accelerator.toml` does not exist until Epic 7. Write the section now; its `core`-vs-`machinery` disposition is Epic 7 Story 7.1's decision. Note this in Completion Notes so the disposition author finds it.

- [ ] Task 5 — Tests (AC: #1, #2, #3)
  - [ ] New `tests/unit/test_asgi_surface.py`: import `config.asgi` and assert `application` is the object returned by `django.core.asgi.get_asgi_application()` — specifically, that it is an instance of `django.core.handlers.asgi.ASGIHandler`, not a plain coroutine function. Assert `config.asgi` has no attribute named `websocket_application` and no attribute named `django_application`.
  - [ ] In the same file, assert `importlib.util.find_spec("config.websocket") is None` — the module is gone, not merely unreferenced.
  - [ ] In the same file, parse `pyproject.toml` with `tomllib` and assert no entry in `[tool.coverage.run].omit` mentions `websocket`.
  - [ ] New `tests/integration/test_asgi_request_path.py`, every test marked `@pytest.mark.integration`: drive a request through the ASGI application (Django's `AsyncClient` or a direct `application(scope, receive, send)` call with an `http` scope) and assert it resolves through the URL resolver — a known route returns its status and an unknown path returns 404 from Django's handler rather than `NotImplementedError`.
  - [ ] In the same file, assert the ASGI instrumentor still produces a span for that request. Use an in-memory span exporter (`opentelemetry.sdk.trace.export.in_memory_span_exporter.InMemorySpanExporter`) and assert at least one span was recorded. `opentelemetry-instrumentation-asgi` is declared at `pixi.toml:66` and its rationale comment at `:62-65` explains that without it `_is_asgi_supported` is False and ASGI requests silently produce no span — that comment is precisely the regression this test guards.
  - [ ] Existing tests that must keep passing unchanged: `tests/unit/test_observability_init.py`, `tests/unit/test_telemetry.py`, `tests/integration/test_request_logging.py`.

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

### Debug Log References

### Completion Notes List

### File List
