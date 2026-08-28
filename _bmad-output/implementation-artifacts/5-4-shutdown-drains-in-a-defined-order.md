---
status: done
baseline_revision: 408dc9b
review_loop_iteration: 0
warnings: []
---

# Story 5.4: Shutdown drains in a defined order

Status: done

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

- [x] Task 1 — Install the `SIGTERM` handler that flips readiness first (AC: #1)
  - [x] `src/config/health/drain.py` (new module in the concern Story 5.3 created): `install_sigterm_handler() -> None`.
  - [x] It captures the currently installed `SIGTERM` handler with `signal.getsignal(signal.SIGTERM)`, installs its own, and on receipt: calls `config.health.state.begin_drain()`, emits one `structlog` event (`event="drain.begin"`, carrying `COMPONENT_PROCESS`), then **delegates to the captured handler** so gunicorn's and Celery's own shutdown proceeds unchanged.
  - [x] Handle both delegation cases explicitly: a callable previous handler is called with `(signum, frame)`; `signal.SIG_DFL` is re-installed and the signal re-raised so default termination still happens; `signal.SIG_IGN` is left alone. Never swallow the signal.
  - [x] Make it idempotent — calling it twice must not chain two handlers and must not lose the original. Guard with a module-level `_installed` flag.
  - [x] Export `reset_sigterm_handler_for_testing() -> None` beside it, mirroring `config.health.state.reset_health_state_for_testing()` (`state.py:106`) and its stated rationale. **This is not optional bookkeeping.** `tests/integration/test_asgi_request_path.py:45` imports `config.asgi` at module scope, `tests/integration/` collects before `tests/unit/` under `pytest tests/` (the `test-cov` task), so by the time `tests/unit/test_drain.py` runs the handler is already installed and `_installed` is already `True` — every idempotence and delegation case would assert against a no-op. The helper restores the captured previous handler and clears `_installed`.
  - [x] Do **not** replace, wrap or reimplement gunicorn's or Celery's shutdown. This story adds ordering, not a shutdown mechanism. The word in AD-22 is *before*: the flip precedes the drain; the drain itself is the server's.
  - [x] `signal.signal` may only be called from the main thread. Catch `ValueError` from a non-main-thread call, log a warning naming the process, and return without raising — a management command run in a thread must not fail to start. Never `except: pass`.

- [x] Task 2 — Call it from the serving entrypoints (AC: #1, #2)
  - [x] In `src/config/asgi.py`, call `install_sigterm_handler()` immediately after the application is bound. **Verified current shape (2026-08-28):** the file is 32 lines; Epic 1 has already removed the `sys.path` insert and the websocket wrapper, so the binding is `application = get_asgi_application()` at `:32` — not `django_application` at `:30`. `configure_observability()` is at `:26`, and it is the file's precedent for process-level setup.
  - [x] `src/config/asgi.py` is in `[tool.coverage.run] omit` (`pyproject.toml:297`) and that list is closed by `tests/unit/test_coverage_policy.py`, so **nothing measures this call site**. Assert it structurally instead, the way `tests/unit/test_asgi_surface.py:test_observability_is_configured_before_the_application_is_built` already asserts the observability call: parse `asgi.py` with `ast` and assert exactly one module-level `install_sigterm_handler()` call, positioned after the `application` assignment. Put that case in `tests/unit/test_drain.py` (it belongs to this story's contract), not in `test_asgi_surface.py`, whose subject is AD-16's surface.
  - [x] Do not add `src/config/health/drain.py` to the omit list. `test_asgi_surface.py:test_the_deployment_entrypoints_are_still_omitted` and `test_coverage_policy.py` both freeze that list; AD-20 makes it closed.
  - [x] Register the same handler for the Celery worker via `celery.signals.worker_ready` in `src/config/celery_app.py`, so a `worker` process also emits the drain event. The readiness flag has no consumer in a worker, but the log event and the single ordering path do. `worker_ready` and not `worker_process_init`: Celery installs its own `SIGTERM` handler in the **main** worker process (`install_platform_tweaks`, before the consumer starts), which is the process the platform signals; `worker_process_init` fires in prefork children, whose handlers are reset and which never receive the platform's `SIGTERM` directly.
  - [x] Follow the file's existing signal-registration shape verbatim: `src/config/celery_app.py:32` already carries `@setup_logging.connect  # type: ignore[untyped-decorator]` with a three-line comment (`:28-31`) explaining that celery ships no `py.typed`. A second `.connect` decorator needs the same marker or `mypy --strict` fails; do not repeat the explanation, point at it.
  - [x] Extend `tests/unit/test_celery_app.py` (which already imports `app` and `config_loggers`) with a case that the new receiver is connected to `worker_ready` and calls `install_sigterm_handler`. Importing `config.celery_app` only *connects* the receiver — it installs no handler — so this case is safe to run in-process.
  - [x] Do not call it from `manage.py`, from settings, or from `AppConfig.ready()`: it must be installed by serving processes only, and `AppConfig.ready()` runs for every management command.

- [x] Task 3 — Verify and pin the web drain sequence (AC: #1)
  - [ ] Confirm the readiness view's first check is `is_draining()` (Story 5.3, Task 3) so a probe arriving after the flip and before the socket closes gets 503 rather than 200.
  - [ ] Confirm the `web` task from Story 5.2 sets no flag that turns gunicorn's graceful shutdown into an abrupt one. `pixi.toml:503`'s `web` command must not carry `--graceful-timeout 0` or `-k sync`. **Verified today:** it carries `-k uvicorn_worker.UvicornWorker` and no timeout, and `tests/unit/test_process_model.py:90` already pins the worker class as `WEB_WORKER_CLASS`.
  - [ ] **Already satisfied by Story 5.2 — verify, do not duplicate.** `pixi.toml:499-502` already records beside the `web` task that AD-22 gives the grace-period value to the deployment repository and that `GUNICORN_CMD_ARGS` is gunicorn's injection point for it; `docs/deployment.md:121-124` says the same in prose. Confirm both still read that way and leave them alone. AC #3's remaining unwritten half is the `## Shutdown` section in Task 5.

- [x] Task 4 — Verify and pin the worker drain semantics (AC: #2)
  - [x] Celery's default response to one `SIGTERM` is a warm shutdown: the worker stops consuming new messages and finishes the tasks it holds. This story's obligation is to keep that true and assert it, not to reimplement it.
  - [x] Assert in the process-model test that the `worker` command from Story 5.2 contains no flag that changes it (`--pool=solo` in particular), and record in `docs/deployment.md` that a second `SIGTERM` is a cold shutdown and is the deployment repository's choice, not the component's.
  - [x] Reuse `tests/unit/test_process_model.py`'s existing machinery rather than writing a second parser: the module-scoped `manifest()` fixture (`:113`), `_tasks_named()` (`:272`) and `_task_command()` (`:232`). Append the case at EOF (after `:626`). **Do not add a pixi task inside the `# feature:celery` region** — `test_the_celery_process_tasks_sit_inside_a_marker_pair` (`:527`) asserts the region's task assignments are exactly `["worker", "beat"]`.
  - [x] Do not set `CELERY_WORKER_...` shutdown-related settings in `src/config/settings/base.py`. **Drift, verified today:** the Celery block is at `:414-453`, not `:296-335`, and it carries **no** `# feature:` markers — no settings module does yet; Epic 7 formalizes them, and `pixi.toml:516/529`, `component.toml:91-99` and `src/config/startup/stage_one.py:833/964` are where the marker convention lives today. The prohibition is unchanged and is the point: shutdown policy is the deployment repository's, so it belongs in neither the settings block nor the region that block will become.

- [x] Task 5 — Document ownership of the ordering and of the grace period (AC: #3)
  - [x] `docs/deployment.md` `## Shutdown`: on `SIGTERM` the component flips readiness, then stops accepting connections, finishes in-flight requests and exits; a worker finishes its current task and declines new ones. State plainly: **the component owns the ordering; the grace period value is the deployment repository's setting.** Name the two knobs the deployment repository owns — the platform's termination grace period and gunicorn's `GUNICORN_CMD_ARGS`.
  - [x] State the interaction the operator needs: the platform must keep probing readiness during the drain (a probe interval longer than the grace period defeats the flip), and the load balancer removes the replica on the first 503.
  - [x] **Already satisfied — verify only.** `mkdocs.yml:39` already registers `Deployment: deployment.md`. `pixi run docs` is `mkdocs build --strict`.
  - [x] Placement: `docs/deployment.md` is 280 lines with top-level sections `## The two declarations` (`:6`), `## Process model` (`:55`), `## Reading the declaration` (`:140`), `## Health endpoints` (`:179`). There is no `## Shutdown`. Append the new section after `:280`; the file currently ends inside the Health-endpoints subsections, and shutdown reads naturally after them since it is what happens to readiness next.

- [x] Task 6 — Tests (AC: #1, #2, #3)
  - [x] `tests/unit/test_drain.py`: installing the handler captures the previous one; delivering `SIGTERM` to the installed handler sets `is_draining()` **before** the previous handler runs — assert the ordering with a spy that records `is_draining()` at call time, not merely that both happened; a second `install_sigterm_handler()` is a no-op; `SIG_DFL` and `SIG_IGN` previous handlers are each handled without raising; a `ValueError` from a non-main thread is logged and swallowed rather than propagated.
  - [x] Restore the real handler in an autouse fixture — `signal.signal` is process-global and a leaked handler breaks unrelated tests. The fixture calls `reset_sigterm_handler_for_testing()` and `config.health.state.reset_health_state_for_testing()` before **and** after every case, matching `tests/unit/test_health_views.py:96-101`. Before-and-after, not just after: `tests/integration/test_asgi_request_path.py` has already installed the handler by collection time.
  - [x] Include the structural case from Task 2: `asgi.py` makes exactly one module-level `install_sigterm_handler()` call, after the `application` assignment.
  - [x] Assert the log event with the project's existing capture fixture rather than a new one — `tests/unit/test_health_views.py:209` has `captured_events`. Beware [[structlog-config-leaks-across-tests]]: use `structlog.testing.capture_logs()`, do not re-import settings in this module.
  - [x] `tests/integration/test_drain.py` (`@pytest.mark.integration`): with a healthy database, readiness returns 200; after invoking the handler, readiness returns 503 while the database is still healthy — the mechanical form of AC #1's "readiness flips before the drain begins".
  - [x] Extend `tests/unit/test_process_model.py` (Story 5.2) with the `worker`-command assertion from Task 4 rather than creating a second parser.

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
| `src/config/health/drain.py` | **NEW** | `install_sigterm_handler()`: flip readiness, log, delegate. Idempotent; safe off the main thread. Plus `reset_sigterm_handler_for_testing()`. |
| `src/config/health/state.py` | — | **No change.** `begin_drain()` (`:85`) and `is_draining()` (`:96`) exist and are final. |
| `src/config/health/__init__.py` | UPDATE | Re-export `install_sigterm_handler` and `reset_sigterm_handler_for_testing`, appending to the existing sorted `__all__` (`:33-41`). |
| `src/config/asgi.py` | UPDATE | Today: module docstring `:1-9`; a `sys.path` insert at `:17-20` (**removed by Epic 1 / AD-7 — do not re-add or depend on it**); `DJANGO_SETTINGS_MODULE` default `:23`; `configure_observability()` `:25-27`; `django_application = get_asgi_application()` `:30`; a websocket import `:33` and a scope-dispatching `application` wrapper `:36-43` (**deleted by Epic 1 / AD-16 together with `src/config/websocket.py` and its coverage `omit` entry**). **Change:** call `install_sigterm_handler()` after the application is built. **Preserve:** the observability call and its ordering. Reconcile with whatever Epic 1 left the file as; do not restore the wrapper. |
| `src/config/celery_app.py` | UPDATE | Register the handler on a Celery worker-startup signal. Read the file first; preserve the existing app construction and autodiscovery. |
| `pixi.toml` | — | **No change.** Story 5.2 already wrote that comment (`:499-502`). Verify only. |
| `docs/deployment.md` | UPDATE | Adds `## Shutdown`. |
| `mkdocs.yml` | — | **No change.** `deployment.md` is already in `nav` (`:39`). |
| `tests/unit/test_drain.py` | **NEW** | Handler ordering, idempotence, delegation cases, thread safety. |
| `tests/integration/test_drain.py` | **NEW** | Readiness 200 → handler → readiness 503 with a healthy database. |
| `tests/unit/test_process_model.py` | UPDATE (created by Story 5.2) | Append the `worker`-command shutdown-flag assertion at EOF (after `:626`), reusing `manifest`/`_tasks_named`/`_task_command`. |
| `tests/unit/test_celery_app.py` | UPDATE | Assert the new `worker_ready` receiver is connected and calls the installer. |

**Line-range drift note — resolved at `408dc9b`.** Epic 1 has already removed both the `sys.path` insert and the websocket wrapper. `src/config/asgi.py` is now 32 lines: docstring `:1-9`, `import os` `:11`, `from django.core.asgi import get_asgi_application` `:13`, the `DJANGO_SETTINGS_MODULE` default `:16`, an explanatory comment `:18-23`, `from config.observability import configure_observability` `:24`, `configure_observability()` `:26`, a comment `:28-31`, and `application = get_asgi_application()` `:32`. **Insertion point: after `:32`.** Do not restore the wrapper and do not re-add the `sys.path` insert.

### Testing Requirements

- Unit: `tests/unit/test_drain.py` — no database, no network, no subprocess. Signal handlers are installed and invoked directly as functions; do **not** send a real `SIGTERM` to the test process.
- Integration: `tests/integration/test_drain.py` — `@pytest.mark.integration`; `tests/integration/conftest.py:12-19` auto-marks the directory as well. Must leave state as found: restore the signal handler and reset the health flags in an autouse fixture, or a later test inherits a draining process and sees 503 for no reason.
- Disposition (spine Consistency Conventions): `src/config/health/` is `core`, so these tests are `core` and run in every combination's gate. The worker half of AC #2 is exercised only where Celery is selected; keep the Celery-specific assertion in the process-model test where it derives its expectations from `component.toml` rather than hardcoding.
- AD-20 floor: 90% including templates, `COVERAGE_CORE=ctrace` in force. Every branch of the delegation logic (`callable`, `SIG_DFL`, `SIG_IGN`, `ValueError`) needs a test — this is a four-branch module and the floor will find it. Do not add it to `[tool.coverage.run] omit` (**now `pyproject.toml:292-298`**); AD-20 makes that list closed and `tests/unit/test_coverage_policy.py` freezes it as `CLOSED_OMIT`.
- Inner loop `pixi run test` and `pixi run test-integration`; done when `pixi run ci` exits 0. The coverage task is named **`test-cov`**, not `cov` (`pixi.toml:579`); `ci` is `precommit → build → typecheck → lint → test-cov` (`pixi.toml:615-621`).

#### Project Structure Notes

- The drain logic belongs to `src/config/health/` rather than a new concern: readiness and drain are one state machine, and splitting them would put the flip and the flag in two modules that can disagree — the same failure AD-26 names for the refusal contract.
- **Dependency: both prerequisites have landed — verified at `408dc9b`.** Story 5.3 gave `src/config/health/{state,views,urls,__init__}.py`; `begin_drain()` is `state.py:85`, `is_draining()` is `state.py:96`, both are re-exported from `config.health`, and `readiness` evaluates `is_draining()` first. Story 5.2 gave the `web` (`pixi.toml:503`), `worker` (`:527`) and `beat` (`:528`) tasks and `tests/unit/test_process_model.py`. Nothing here needs stubbing.
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

### Spec Change Log

Reconciled against the tree at `408dc9b` (2026-08-28). The story was authored 2026-08-15; what
changed since, and what it changes here:

| Claim as written | Actual today | Effect on the work |
|---|---|---|
| `asgi.py` binds `django_application` at `:30`, with a `sys.path` insert and a websocket wrapper still present | 32 lines, both removed by Epic 1; the binding is `application = get_asgi_application()` at `:32` | Insertion point moves to after `:32`; the reconcile-with-Epic-1 instruction is discharged, not pending |
| Task 3: write the grace-period comment beside the `web` task | Story 5.2 already wrote it (`pixi.toml:499-502`), and `docs/deployment.md:121-124` restates it | Verify, do not duplicate |
| Task 5: register `deployment.md` in `mkdocs.yml` `nav` | Already registered (`:39`) | Verify only |
| `settings/base.py` Celery block at `:296-335`, a feature-owned region under AD-24 | Block is at `:414-453` and carries **no** `feature:` markers; no settings module does yet | Prohibition unchanged; the AD-24 framing is forward-looking, not a description of today |
| `[tool.coverage.run] omit` at `pyproject.toml:162-169` | `:292-298`, and frozen as `CLOSED_OMIT` in `tests/unit/test_coverage_policy.py` | Same prohibition, one more carrier to not touch |
| Celery signal is `worker_ready` "or `worker_process_init` for a prefork pool" | — | Resolved to `worker_ready`: the prefork children never receive the platform's `SIGTERM` directly |
| Coverage task is `pixi run cov` (project standard) | This repo's task is `test-cov` (`pixi.toml:579`) | Command name only |

Frontmatter carries `warnings: [oversized]`: the file is ~4.2k tokens against the workflow's
900-1600 target. That target belongs to `spec-template.md`, the greenfield path this project does
not use — these stories are bulk-authored with architecture tracing that is the reason they are
implementable. The flag is recorded rather than acted on.

**Two hazards the spec did not name, now written into the tasks.**

*The `_installed` guard is pre-tripped by collection order.* `tests/integration/test_asgi_request_path.py`
imports `config.asgi` at module scope; `tests/integration/` collects before `tests/unit/` under
`pytest tests/`, which is what `test-cov` runs. Without a `reset_sigterm_handler_for_testing()` helper
every idempotence and delegation case in `tests/unit/test_drain.py` would assert against an
already-installed handler and pass for the wrong reason under `pixi run test` while failing — or worse,
silently degrading — under `pixi run ci`. `src/config/health/state.py:106` already establishes the
helper shape and the reason for it.

*The `asgi.py` call site is unmeasured.* `src/config/asgi.py` is in the closed `omit` list, so no
coverage signal exists for the one line that makes any of this run in production. `test_asgi_surface.py`
already solved the same problem for `configure_observability()` by asserting the call's presence and
position in the AST; this story does the same for `install_sigterm_handler()`, in
`tests/unit/test_drain.py`.

## Dev Agent Record

### Agent Model Used

`claude-opus-5[1m]`, via `bmad-dev-auto`.

### Debug Log References

- `pixi run ci` — **exit 0**. 1415 passed, total coverage 97.20% (floor 90). `src/config/health/drain.py`: 41 statements, 0 missed.
- `pixi run test` — 1125 passed. Run separately from `test-cov` to prove the collection-order hazard is handled.
- Handler-displacement reproduction (below) — run under `pixi run -e dev python`.

### Completion Notes List

**AC #1 is not satisfied in the `web` process, and the gate cannot see it.** Everything the spec
asked for was built and every test passes, but the mechanism the spec chose is defeated by the
server Story 5.2 pinned. This was found by reading `uvicorn`'s source during verification, then
reproduced:

```python
import signal
import config.asgi                      # what gunicorn's load_wsgi() does
from uvicorn import Config, Server
from config.health.state import is_draining

signal.getsignal(signal.SIGTERM)        # -> <function _handle_sigterm>   (ours, as designed)

server = Server(Config("config.asgi:application"))
with server.capture_signals():          # what uvicorn does when it starts serving
    signal.getsignal(signal.SIGTERM)    # -> <bound method Server.handle_exit>   (ours is gone)
    signal.raise_signal(signal.SIGTERM) # the platform's SIGTERM, during serving
    is_draining()                       # -> False        <-- AC #1 fails here
    server.should_exit                  # -> True         <-- the drain has begun
```

The sequence inside a gunicorn worker is fixed and there is no seam in it:

1. `Worker.init_process()` → `init_signals()` — `uvicorn_worker/_workers.py:96-101` resets `SIGTERM` to `SIG_DFL`.
2. `Worker.load_wsgi()` — `gunicorn/workers/base.py:136` imports `config.asgi`, which installs our handler. Correct, and too early.
3. `Worker.run()` → `Server.serve()` → `capture_signals()` — `uvicorn/server.py:330` does
   `signal.signal(sig, self.handle_exit)` for `HANDLED_SIGNALS`, which includes `SIGTERM`
   (`uvicorn/server.py:36-39`). **Unconditional**, main-thread only, no configuration flag.

There is one `SIGTERM` slot and the last writer wins, so the drain flip must be installed *after*
step 3. `capture_signals`' `finally` block restores our handler and re-raises the signal
(`uvicorn/server.py:334-339`), so `drain.begin` does fire — **after** the drain has completed, which
is the exact inversion of AD-22's word *before*. The process still exits correctly; readiness is
simply never 503 while the socket is still open, so the load balancer keeps routing to a replica
that is closing. That is the failure AD-22 names: "a drain that finishes in-flight work while
traffic is still arriving."

**AC #2 does hold, and for a reason worth recording.** Celery installs its `SIGTERM` handler in
`install_platform_tweaks` (`celery/apps/worker.py:145`, → `:270`) and sends `worker_ready` afterwards
(`:181`). Nothing re-installs after that, so the receiver registered in `config/celery_app.py` puts
the flip genuinely in front of Celery's warm shutdown and it stays there. The asymmetry between the
two entrypoints is the whole finding: `worker_ready` is a post-signal-setup hook and module import is
not.

**AC #3 holds.** Ownership is documented (`docs/deployment.md` `## Shutdown`), the component sets no
grace period, and `pixi.toml:499-502` already recorded the `GUNICORN_CMD_ARGS` injection point.

**Why this was not caught by the tests the spec asked for.** Every case the spec named invokes the
handler as a plain function, which asserts that the *handler* orders correctly and never that the
handler is *in the slot* when the signal arrives. `src/config/asgi.py` is coverage-omitted, so the
call site has only the AST assertion this story added — and an AST assertion cannot see a third party
overwriting the slot 200ms later. A test that would have caught it has to run a real server and
signal it.

### Candidate resolutions, with what each one costs

None of these is inside this story's frozen boundary, which is why the run stops here rather than
picking one.

| # | Resolution | Cost |
|---|---|---|
| A | Component-owned worker class (e.g. `config.health.worker.DrainingUvicornWorker`) that installs the flip after `capture_signals` has run | Changes `pixi.toml`'s `web` command, which Story 5.2 froze, and `tests/unit/test_process_model.py:90` (`WEB_WORKER_CLASS`) pins the current `-k uvicorn_worker.UvicornWorker`. Needs a seam inside the running loop; the obvious ones are timing-dependent. |
| B | Re-assert the slot from the readiness view — the handler checks `signal.getsignal(SIGTERM)` and re-installs in front if displaced | Tidy in principle (readiness is the only consumer of the flag and is probed continuously), but `signal.signal` is main-thread-only and Django runs the current **sync** `readiness` view in a threadpool executor. Requires making Story 5.3's readiness view async. |
| C | Accept that the flip is the platform's job and drop AC #1's component half | Contradicts AD-22 ("the component owns the ordering") and would have to be taken at the architecture level, not here. |

Recommendation: **A**, scoped as an amendment that reopens Story 5.2's `web` command, with the
end-to-end test the spec never asked for — start the real `web` command, `SIGTERM` it, and assert
`/readyz` answers 503 while the socket is still accepting.

### File List

Implemented and left **uncommitted** in the working tree (gate green at each step):

| Path | Change |
|---|---|
| `src/config/health/drain.py` | NEW — `install_sigterm_handler()`, `_handle_sigterm()`, `_delegate()`, `reset_sigterm_handler_for_testing()`; four displaced-handler shapes (callable, `SIG_DFL`, `SIG_IGN`, `None` from a C handler) |
| `src/config/health/__init__.py` | Re-exports both new names |
| `src/config/asgi.py` | Import `:24`; `install_sigterm_handler()` `:45`, after `application = get_asgi_application()` `:33` |
| `src/config/celery_app.py` | `worker_ready` receiver `install_drain_handler` `:61-86` |
| `docs/deployment.md` | `## Shutdown` appended (280 → 338 lines) |
| `tests/unit/test_drain.py` | NEW — 15 cases incl. the ordering spy and the `asgi.py` AST position case |
| `tests/integration/test_drain.py` | NEW — 3 cases, readiness 200 → handler → 503 |
| `tests/unit/test_process_model.py` | `test_the_worker_command_carries_no_shutdown_altering_flag` appended |
| `tests/unit/test_celery_app.py` | Two cases for the `worker_ready` receiver |

Deviations from the spec, all deliberate and all recorded in the code:
`signal.signal`'s return value instead of a preceding `getsignal`; the Celery receiver imports the
installer function-locally (matching `config_loggers`, and because `config/__init__.py` imports
`config.celery_app`, so a module-level import would pull the health concern into every `config`
import); and a fourth displaced-handler shape (`None`, a handler installed from C) shares the
declined-delegation branch rather than falling through unhandled.

## Auto Run Result

Status: **resolved** (was **blocked**)

The dev session escalated rather than deciding alone, correctly. Its finding, verbatim: AC #1
("readiness flips before the drain begins") was not satisfied in the `web` process, because
`uvicorn.Server.capture_signals()` replaces the `SIGTERM` handler unconditionally when it starts
serving, after `config.asgi` has been imported, so the drain flip never ran while the process was
draining. AC #2 and AC #3 were satisfied. Every resolution crossed a boundary another story froze —
`pixi.toml`'s `web` command (Story 5.2) or the sync readiness view (Story 5.3).

### What the mechanism actually is

Confirmed independently, and it is two overwrites rather than one:

1. `uvicorn_worker/_workers.py` — the gunicorn worker's `init_signals()` resets every handled signal
   to `SIG_DFL` when the worker is forked.
2. The worker then loads the application, which imports `config.asgi` and installs the drain handler.
   At that moment it is live, which is why the existing tests pass.
3. `uvicorn/server.py` — `Server.serve()` opens `with self.capture_signals():`, whose body is
   `{sig: signal.signal(sig, self.handle_exit) for sig in HANDLED_SIGNALS}`. It replaces the handler
   unconditionally and keeps the displaced one only to restore on the way out.

`config/health/drain.py` delegates to the handler it displaced; nothing can delegate to a handler
that displaced *it* afterwards. So the fix had to be at the layer that installs last.

### Resolution — decided by the user, implemented inline

The component owns its worker class. `src/config/workers.py` adds `DrainingServer`, whose
`handle_exit` calls `begin_drain()` and then `super().handle_exit(...)` unchanged, and
`DrainingUvicornWorker`, which runs it. `pixi.toml`'s `web` now names
`-k config.workers.DrainingUvicornWorker`, and Story 5.2's `WEB_WORKER_CLASS` constant was updated
with it so a revert to the stock worker is a gate failure rather than a silent regression.

The flip is `begin_drain()` — the same function the signal handler calls — so `web` and `worker`
reach the same state through one definition of what draining means.

**The coupling this accepts, and what pins it.** `uvicorn_worker` builds `Server(config=self.config)`
inside `_serve` from a module-level name, with no overridable attribute, so `_serve` is overridden
with a copy of its four upstream statements. `tests/unit/test_workers.py` pins that:
`test_upstream_still_builds_its_server_inside_serve` fails if the seam appears (an invitation to
delete the override), and `test_the_override_matches_the_upstream_statement_for_statement` compares
the two bodies as parsed statements, so an upstream fix that this copy would otherwise drop fails
the gate.

### The blind spot that let this through, closed

Stories 5.3's and 5.4's drain tests invoke the `SIGTERM` handler as a plain function — they call what
`signal.getsignal` returns, or the module function directly. That is exactly why `web` could be
broken while all of them passed: in a real `web` process the handler they exercise is the one uvicorn
threw away. `TestTheHandlerUvicornActuallyInstalls` drives uvicorn's own installation instead and
asks what is registered afterwards, then calls it. Those cases fail if the fix is reverted, and would
have failed before it.

**A uvicorn behaviour found while writing them, asserted rather than worked around silently.**
`capture_signals` re-raises every captured signal as it exits, *after* restoring the displaced
handler. Under pytest that handler is the default disposition, so the first version of the case
delivered a real `SIGTERM` to the runner and killed the session mid-file — five dots and a silent
exit. `_absorbing_sigterm` holds it harmless, and
`test_uvicorn_reraises_what_it_captured_on_the_way_out` asserts the behaviour, because it is also how
a `web` process actually terminates once graceful shutdown finishes.

### What was not changed

Story 5.3's readiness view is untouched — it was the other candidate boundary and it did not need to
move. `config/health/drain.py` is untouched: it remains correct and is the handler that runs in
`worker` and `beat`.
