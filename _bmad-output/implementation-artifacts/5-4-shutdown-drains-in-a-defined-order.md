# Story 5.4: Shutdown drains in a defined order

Status: ready-for-dev

## Story

As an operator,
I want termination to stop traffic before it finishes in-flight work,
so that a deploy does not drop requests that arrived during the drain.

## Acceptance Criteria

**Traceability:** FR-43 · AD-22 · SC-3

1. **Given** a web process receives `SIGTERM`
   **When** shutdown begins
   **Then** readiness flips before the drain begins
   **And** the process then stops accepting connections, finishes in-flight requests, and exits

2. **Given** a worker process receives `SIGTERM`
   **When** shutdown begins
   **Then** it finishes its current task and declines new ones

3. **Given** the grace period
   **When** ownership is assigned
   **Then** the component owns the ordering
   **And** the grace period value is a deployment-repository setting

## Tasks / Subtasks

- [ ] Task 1 — Install the `SIGTERM` handler that flips readiness first (AC: #1)
  - [ ] `src/config/health/drain.py` (new module in the concern Story 5.3 created): `install_sigterm_handler() -> None`.
  - [ ] It captures the currently installed `SIGTERM` handler with `signal.getsignal(signal.SIGTERM)`, installs its own, and on receipt: calls `config.health.state.begin_drain()`, emits one `structlog` event (`event="drain.begin"`, carrying `COMPONENT_PROCESS`), then **delegates to the captured handler** so gunicorn's and Celery's own shutdown proceeds unchanged.
  - [ ] Handle both delegation cases explicitly: a callable previous handler is called with `(signum, frame)`; `signal.SIG_DFL` is re-installed and the signal re-raised so default termination still happens; `signal.SIG_IGN` is left alone. Never swallow the signal.
  - [ ] Make it idempotent — calling it twice must not chain two handlers and must not lose the original. Guard with a module-level `_installed` flag.
  - [ ] Do **not** replace, wrap or reimplement gunicorn's or Celery's shutdown. This story adds ordering, not a shutdown mechanism. The word in AD-22 is *before*: the flip precedes the drain; the drain itself is the server's.
  - [ ] `signal.signal` may only be called from the main thread. Catch `ValueError` from a non-main-thread call, log a warning naming the process, and return without raising — a management command run in a thread must not fail to start. Never `except: pass`.

- [ ] Task 2 — Call it from the serving entrypoints (AC: #1, #2)
  - [ ] In `src/config/asgi.py`, call `install_sigterm_handler()` immediately after `django_application = get_asgi_application()` (currently `:30`) — the same position and rationale as the existing `configure_observability()` call at `:25-27`, which is the file's precedent for process-level setup.
  - [ ] Register the same handler for the Celery worker via `celery.signals.worker_ready` (or `worker_process_init` for a prefork pool) in `src/config/celery_app.py`, so a `worker` process also emits the drain event. The readiness flag has no consumer in a worker, but the log event and the single ordering path do.
  - [ ] Do not call it from `manage.py`, from settings, or from `AppConfig.ready()`: it must be installed by serving processes only, and `AppConfig.ready()` runs for every management command.

- [ ] Task 3 — Verify and pin the web drain sequence (AC: #1)
  - [ ] Confirm the readiness view's first check is `is_draining()` (Story 5.3, Task 3) so a probe arriving after the flip and before the socket closes gets 503 rather than 200.
  - [ ] Confirm the `web` task from Story 5.2 sets no flag that turns gunicorn's graceful shutdown into an abrupt one. `pixi.toml`'s `web` command must not carry `--graceful-timeout 0` or `-k sync`.
  - [ ] Record in a comment beside the `web` task that the grace period is injected by the deployment repository through gunicorn's `GUNICORN_CMD_ARGS`, and that the component sets no value (AC #3).

- [ ] Task 4 — Verify and pin the worker drain semantics (AC: #2)
  - [ ] Celery's default response to one `SIGTERM` is a warm shutdown: the worker stops consuming new messages and finishes the tasks it holds. This story's obligation is to keep that true and assert it, not to reimplement it.
  - [ ] Assert in the process-model test that the `worker` command from Story 5.2 contains no flag that changes it (`--pool=solo` in particular), and record in `docs/deployment.md` that a second `SIGTERM` is a cold shutdown and is the deployment repository's choice, not the component's.
  - [ ] Do not set `CELERY_WORKER_...` shutdown-related settings in `src/config/settings/base.py`. The Celery block there (`:296-335`) is a feature-owned region under AD-24 and adding shutdown policy to it would put deployment-repository policy inside the component.

- [ ] Task 5 — Document ownership of the ordering and of the grace period (AC: #3)
  - [ ] `docs/deployment.md` `## Shutdown`: on `SIGTERM` the component flips readiness, then stops accepting connections, finishes in-flight requests and exits; a worker finishes its current task and declines new ones. State plainly: **the component owns the ordering; the grace period value is the deployment repository's setting.** Name the two knobs the deployment repository owns — the platform's termination grace period and gunicorn's `GUNICORN_CMD_ARGS`.
  - [ ] State the interaction the operator needs: the platform must keep probing readiness during the drain (a probe interval longer than the grace period defeats the flip), and the load balancer removes the replica on the first 503.
  - [ ] Ensure `docs/deployment.md` is in `mkdocs.yml` `nav`; `pixi run docs` is `mkdocs build --strict`.

- [ ] Task 6 — Tests (AC: #1, #2, #3)
  - [ ] `tests/unit/test_drain.py`: installing the handler captures the previous one; delivering `SIGTERM` to the installed handler sets `is_draining()` **before** the previous handler runs — assert the ordering with a spy that records `is_draining()` at call time, not merely that both happened; a second `install_sigterm_handler()` is a no-op; `SIG_DFL` and `SIG_IGN` previous handlers are each handled without raising; a `ValueError` from a non-main thread is logged and swallowed rather than propagated.
  - [ ] Restore the real handler in an autouse fixture — `signal.signal` is process-global and a leaked handler breaks unrelated tests. Reset `config.health.state` flags in the same fixture.
  - [ ] `tests/integration/test_drain.py` (`@pytest.mark.integration`): with a healthy database, readiness returns 200; after invoking the handler, readiness returns 503 while the database is still healthy — the mechanical form of AC #1's "readiness flips before the drain begins".
  - [ ] Extend `tests/unit/test_process_model.py` (Story 5.2) with the `worker`-command assertion from Task 4 rather than creating a second parser.

## Dev Notes

### Architecture Constraints

- **AD-22** — *Rule:* "On `SIGTERM` readiness flips *before* the drain begins, then the process stops accepting connections, finishes in-flight requests and exits; a worker finishes its current task and declines new ones. **The component owns the ordering; the grace period is the deployment repository's.**" *Prevents:* "a drain that finishes in-flight work while traffic is still arriving."
- **AD-14** — The deployment repository invokes `pixi run <process>`; replica counts and replacement strategy live in `component.toml`. The grace period is neither — it is a platform setting and appears in neither file. Do not add a `grace_period` key to `component.toml`.
- **AD-24** — `src/config/settings/base.py` and `pixi.toml` carry feature-owned regions delimited by paired `feature:<name>` / `/feature:<name>` line comments. **No other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`.** The Celery `worker_ready` registration in `src/config/celery_app.py` is unconditional code in a `core` file: `src/config/celery_app.py` already exists and travels; do not guard the import of `celery.signals` with `try/except ImportError`. If `celery_app.py` itself becomes feature-owned in Epic 7, the registration travels with it.
- **AD-16** — "`asgi.py` exposes Django's ASGI application directly." Story 5.2/Epic 1 delete the websocket wrapper; the handler installation is a plain function call in `asgi.py`, not an ASGI middleware layer.
- **NFR-3** — Statelessness: nothing shared through local disk or process memory across replicas. The drain flag is one process's observation of its own signal, never shared.
- **Consistency Conventions** — "Runtime errors… Nothing is swallowed silently." Every branch that declines to act logs. "Logging: structured, JSON to stdout, carrying `request_id`, `trace_id`, `span_id`" — a signal handler has no request context, so the drain event carries the process type instead.
- **Project standards** — Pixi is the only runner. Python 3.14 only. Full type hints, Google docstrings, line length 120. Never `print()`; never stdlib `logging` — `structlog` only. Never a bare `except:`; never `except X: pass` — log or re-raise.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/health/drain.py` | **NEW** | `install_sigterm_handler()`: flip readiness, log, delegate. Idempotent; safe off the main thread. |
| `src/config/health/state.py` | UPDATE (created by Story 5.3) | No change expected — `begin_drain()` / `is_draining()` already exist. If Story 5.3 has not landed, land it first rather than duplicating the flag here. |
| `src/config/health/__init__.py` | UPDATE | Re-export `install_sigterm_handler`. |
| `src/config/asgi.py` | UPDATE | Today: module docstring `:1-9`; a `sys.path` insert at `:17-20` (**removed by Epic 1 / AD-7 — do not re-add or depend on it**); `DJANGO_SETTINGS_MODULE` default `:23`; `configure_observability()` `:25-27`; `django_application = get_asgi_application()` `:30`; a websocket import `:33` and a scope-dispatching `application` wrapper `:36-43` (**deleted by Epic 1 / AD-16 together with `src/config/websocket.py` and its coverage `omit` entry**). **Change:** call `install_sigterm_handler()` after the application is built. **Preserve:** the observability call and its ordering. Reconcile with whatever Epic 1 left the file as; do not restore the wrapper. |
| `src/config/celery_app.py` | UPDATE | Register the handler on a Celery worker-startup signal. Read the file first; preserve the existing app construction and autodiscovery. |
| `pixi.toml` | UPDATE | Comment beside the `web` task recording that the grace period is the deployment repository's, injected via `GUNICORN_CMD_ARGS`. No command change. |
| `docs/deployment.md` | UPDATE | Adds `## Shutdown`. |
| `mkdocs.yml` | UPDATE | Register `deployment.md` in `nav` if not already. |
| `tests/unit/test_drain.py` | **NEW** | Handler ordering, idempotence, delegation cases, thread safety. |
| `tests/integration/test_drain.py` | **NEW** | Readiness 200 → handler → readiness 503 with a healthy database. |
| `tests/unit/test_process_model.py` | UPDATE (created by Story 5.2) | Add the `worker`-command shutdown-flag assertion. |

**Line-range drift note:** `src/config/asgi.py:17-20` and `:33-43` are cited above as they stand today (2026-08-15). Epic 1 removes both under AD-7 and AD-16. Confirm the file's current shape before editing and record the actual insertion point in the Dev Agent Record.

### Testing Requirements

- Unit: `tests/unit/test_drain.py` — no database, no network, no subprocess. Signal handlers are installed and invoked directly as functions; do **not** send a real `SIGTERM` to the test process.
- Integration: `tests/integration/test_drain.py` — `@pytest.mark.integration`; `tests/integration/conftest.py:12-19` auto-marks the directory as well. Must leave state as found: restore the signal handler and reset the health flags in an autouse fixture, or a later test inherits a draining process and sees 503 for no reason.
- Disposition (spine Consistency Conventions): `src/config/health/` is `core`, so these tests are `core` and run in every combination's gate. The worker half of AC #2 is exercised only where Celery is selected; keep the Celery-specific assertion in the process-model test where it derives its expectations from `component.toml` rather than hardcoding.
- AD-20 floor: 90% including templates, `COVERAGE_CORE=ctrace` in force. Every branch of the delegation logic (`callable`, `SIG_DFL`, `SIG_IGN`, `ValueError`) needs a test — this is a four-branch module and the floor will find it. Do not add it to `[tool.coverage.run] omit` (`pyproject.toml:162-169`); AD-20 makes that list closed.
- Inner loop `pixi run test` and `pixi run test-integration`; done when `pixi run ci` exits 0.

#### Project Structure Notes

- The drain logic belongs to `src/config/health/` rather than a new concern: readiness and drain are one state machine, and splitting them would put the flip and the flag in two modules that can disagree — the same failure AD-26 names for the refusal contract.
- **Dependency:** Story 5.3 must have landed (`state.py`, the readiness view's drain-first ordering). Story 5.2 should have landed (the `web` and `worker` tasks Task 3 and Task 4 assert over). Neither is optional; do not stub them.
- **Not in scope:** the grace-period value, the platform's `terminationGracePeriodSeconds`, the probe interval, and the load-balancer deregistration behaviour. All are the deployment repository's, and epics.md records SC-3 as an external exit criterion that no story in this repository closes.
- No new dependency: `signal` and `structlog` are already available; `structlog` is declared in `pixi.toml` `[dependencies]`.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-22]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-14]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-16]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-7]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.4]
- [Source: _bmad-output/planning-artifacts/epics.md#External exit criteria] — SC-3's deployment half is outside this repository.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-43]
- Repository state: `src/config/asgi.py:17-43`; `src/config/celery_app.py`; `src/config/settings/base.py:296-335` (Celery block); `pixi.toml:172-182`; `tests/integration/conftest.py:12-19`.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
