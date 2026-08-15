# Story 6.1: Correlated structured logging holds in every combination

Status: ready-for-dev

## Story

As an operator,
I want every log line from every component to carry the same correlation identifiers,
so that I can follow one request across services whose teams never coordinated.

## Acceptance Criteria

**Traceability:** FR-46 · SC-7

1. **Given** any component
   **When** it logs
   **Then** it writes a JSON event stream to stdout
   **And** it never manages log files or rotation

2. **Given** a log line emitted during a request
   **When** it is inspected
   **Then** it carries `request_id`, `trace_id` and `span_id`
   **And** this holds in all six combinations

3. **Given** background task processing is selected
   **When** a task executes
   **Then** correlation propagates into task execution
   **And** `django-structlog`'s Celery correlation-ID propagation is wired only where that feature is selected

4. **Given** an authorization change
   **When** the mapper syncs
   **Then** it emits a structured event correlated with `request_id` and `trace_id`

## Tasks / Subtasks

- [ ] Task 1 — Lock the JSON-to-stdout, no-files, no-rotation property with tests (AC: #1)
  - [ ] In `tests/unit/test_observability_logging.py`, add a test that `build_logging_config(debug=False)` produces exactly one handler `console` whose `class` is `"logging.StreamHandler"`, and assert that no handler class in the built config contains `FileHandler`, `RotatingFileHandler`, `TimedRotatingFileHandler`, `WatchedFileHandler` or `SysLogHandler`, and that no handler carries a `filename` key.
  - [ ] Add a test that the `structured` formatter's `processors` for `log_format="json"` end in `structlog.processors.JSONRenderer` (assert on the type of the last element returned by `config.observability.logging._renderer("json")`), and that `debug=False` with no explicit format resolves to `json` via `resolve_log_format`.
  - [ ] Add a test that `build_logging_config(extra_handlers={...})` cannot introduce a file handler without failing this suite — i.e. run the same no-file-handler assertion over `build_logging_config(debug=False, extra_handlers=production_extra_handlers)` using the handler dict that `src/config/settings/production.py` passes.

- [ ] Task 2 — Make `request_id` + `trace_id` + `span_id` on one request-scoped log line an asserted fact, not an inferred one (AC: #2)
  - [ ] Add an `otel_tracing` fixture to `tests/integration/conftest.py`: session-scoped, builds `TracerProvider(resource=build_resource())`, attaches `SimpleSpanProcessor(InMemorySpanExporter())` (`opentelemetry.sdk.trace.export.in_memory_span_exporter`), calls `opentelemetry.trace.set_tracer_provider(provider)` **once** for the session, and calls `DjangoInstrumentor().instrument()` on entry / `.uninstrument()` on exit. `trace.set_tracer_provider` is one-shot per process — a second call logs a warning and is ignored — so this must be session-scoped, not function-scoped.
  - [ ] Add a function-scoped `spans` fixture that clears the in-memory exporter before yielding and returns it, so each test starts from an empty span list.
  - [ ] Add `tests/integration/test_log_correlation.py`: drive `client.get(reverse("account_login"))` with `caplog.at_level(logging.INFO, logger="django_structlog")`, then assert the `django_structlog` `request_started` (or `request_finished`) event dict carries all three of `request_id`, `trace_id`, `span_id`, that `trace_id` is 32 hex characters and `span_id` is 16 hex characters, and that the `trace_id` on the log line equals `format(span.context.trace_id, "032x")` for the span the exporter captured for that request. Reuse the `_events()` helper pattern from `tests/integration/test_request_logging.py:33-48`.
  - [ ] Drive `account_login` rather than `home`. AD-29 (revision 3) **deletes** `home` and `about` as demonstration content along with their `TemplateView`s in `src/config/urls.py`; the allauth sign-in page is `core` in every combination because FR-4's interactive flow is immovable core, and it renders through `base.html` and the crispy form styling, which are also now `core`. The existing `tests/integration/test_request_logging.py` still reverses `home` throughout — repointing that module is Epic 7's excision work, not this story's, but do not add a new dependency on a route that is being deleted.
  - [ ] Do not use `structlog.testing.capture_logs` — it swaps in its own processor chain and drops `merge_contextvars`, so `request_id` would never appear. The existing module docstring at `tests/integration/test_request_logging.py:1-11` records this; keep the same `caplog` approach.

- [ ] Task 3 — Position the Celery correlation switch so it can become a `feature:celery` region (AC: #3)
  - [ ] Move `DJANGO_STRUCTLOG_CELERY_ENABLED = True` and its two comment lines from `src/config/settings/base.py:289-291` to the top of the Celery block that begins at `src/config/settings/base.py:296` (`# Celery`), keeping the value and the comment text unchanged. It must be contiguous with the rest of the Celery-owned settings so Epic 7 can enclose the whole block in one `feature:celery` / `/feature:celery` marker pair.
  - [ ] Do **not** add the marker comments, an `if` guard, a conditional import, a `try/except ImportError`, or a settings-module override to achieve feature scoping — AD-24 forbids every one of those. This story only makes the block contiguous; Epic 7 declares the region.
  - [ ] Add a unit test in `tests/unit/test_settings.py` that reads `src/config/settings/base.py` as text and asserts `DJANGO_STRUCTLOG_CELERY_ENABLED` appears **after** the `# Celery` banner line and before the first non-`CELERY_`-prefixed assignment that follows it, so a later edit cannot silently move it back outside the block.

- [ ] Task 4 — Assert the Celery-side correlation reaches task execution (AC: #3)
  - [ ] Add a test asserting `config.celery_app.app.steps["worker"]` contains `django_structlog.celery.steps.DjangoStructLogInitStep` (wired at `src/config/celery_app.py:19`), extending `tests/unit/test_celery_app.py`.
  - [ ] Add an integration test in `tests/integration/test_log_correlation.py` that, with `CELERY_TASK_ALWAYS_EAGER` on, enqueues a task from inside a request and asserts the task's log records carry the same `request_id` as the request that enqueued them. Define that task **in the test module itself** with `@shared_task`. Do not enqueue `src/django_service/users/tasks.py`: AD-29 records that it violates the `django_service`-is-core-in-its-entirety rule by importing `from celery import shared_task`, that nothing in `src/` calls it, and that it is **deleted** rather than relocated — a test built on it would be removed with it.

- [ ] Task 5 — Assert the mapper's authorization-change event is correlated (AC: #4)
  - [ ] **Blocked on Epic 2.** `src/config/authorization/` does not exist in the repository today. `epics.md:297` names this assertion as Epic 6's one dependency beyond Epic 1. Do not stub, mock or fabricate a mapper to close this task.
  - [ ] Once the mapper exists, add a test in `tests/integration/test_log_correlation.py` that performs one sync through it inside a request with the `otel_tracing` fixture active, and asserts the emitted structured event carries `request_id` and `trace_id` alongside the group-change payload.
  - [ ] If Epic 2 has not landed when this story is picked up, complete Tasks 1–4 and 6, and record the deferral explicitly in Completion Notes naming the blocking epic. Do not mark the story done with this AC silently unmet.

- [ ] Task 6 — Run the gate (AC: #1, #2, #3, #4)
  - [ ] `pixi run test`, then `pixi run test-integration`, then `pixi run ci`. Never bare `pytest`/`python`; never `pip`/`uv`.

## Dev Notes

### Architecture Constraints

- **Consistency Conventions → Logging** — "Structured, JSON to stdout, carrying `request_id`, `trace_id`, `span_id`. Every authorization change emits an event. No files, no rotation." This is the whole of AC #1, #2 and #4 stated as an invariant; there is no AD, so the convention table is the binding text.
- **AD-24** — "A `core` path carries feature-owned regions by declared markers, and by no other mechanism." **The set of region-bearing paths is open** and the carrier declares it as an open `[[regions]]` array; the reconciler encodes no count. The ones known at the time of writing that matter here: `src/config/settings/base.py` (the Celery block at **`:296-335`** — `:296` is the `# Celery` header and `:335` is `CELERY_WORKER_HIJACK_ROOT_LOGGER`, the block's last line; `REDIS_URL`/`REDIS_SSL` at `:293-294`; feature entries in the installed-app lists), `src/config/settings/production.py:31-44` plus its `from .base import REDIS_URL` at `:12`, `src/config/settings/local.py:75-80`, `src/config/observability/telemetry.py` (**`:135` and `:137` as two single-line regions, plus their imports at `:21` and `:24` — `:134` and `:136` are `core`**), `src/config/startup/stage_one.py`, `pixi.toml` and `component.toml`. **Prevents:** "a missed region leaving `CeleryInstrumentor().instrument()` in eight combinations whose environment no longer contains the instrumentor — an `ImportError` at boot that path-level reconciliation cannot see" — the spine's Prevents clause still says *eight* from the twelve-combination model; under revision 3 it is the **four** combinations without Celery. **Forbidden:** "No other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`."
- **AD-29 / Consistency Conventions → Test location** — accelerator and base tests live under `tests/` mirroring `src/` and carry the disposition of what they cover; a feature's tests are `feature:<name>` and are pruned with it, except the immovable-core assertion suite (AD-30), which is `core`. The correlation tests written here cover immovable-core behaviour (FR-46 is in the SC-7 set) and are therefore `core` — they must not import anything feature-owned at module level, or they cannot survive pruning in the four non-Celery combinations. Put the Celery-eager task test in its own module or guard it behind the feature at Epic 7's declaration time; do not use a runtime `pytest.importorskip`, which would make it present-but-skipped and violate FR-28.
- **AD-20** — the coverage floor is ninety percent including templates, everywhere, with `COVERAGE_CORE=ctrace` in force. `pixi run test-cov` already carries `--cov-fail-under=90`.
- **Project standard** — never `print()`; never stdlib `logging` in project code (test modules reading `caplog` may import `logging` for the level constant, as `tests/integration/test_request_logging.py:15` already does). `structlog` only, JSON to stdout.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/settings/base.py` | UPDATE | Today: `DJANGO_STRUCTLOG_CELERY_ENABLED = True` sits at `:291`, separated from the Celery block by `REDIS_URL`/`REDIS_SSL` at `:293-294`. This story moves it into the Celery block that starts at `:296` so one region can own it. **Preserve:** `LOGGING = build_logging_config(...)` at `:281-285` and `configure_structlog()` at `:287` — the call ordering is load-bearing (structlog must be configured while settings are being read), and `MIDDLEWARE` at `:164-179` where `django_structlog.middlewares.RequestMiddleware` sits at `:175` deliberately *after* `AuthenticationMiddleware` so `request.user` is resolvable as `user_id`. |
| `src/config/observability/logging.py` | UPDATE (tests only — no source change expected) | Today: `add_otel_context` (`:29-54`) injects `trace_id`/`span_id` from the active span; `shared_processors()` (`:57-71`) is used both as the structlog chain and as the stdlib `foreign_pre_chain` (`:188`), which is what makes Django/allauth/Celery records carry the same context; `build_logging_config` (`:138-196`) emits exactly one `logging.StreamHandler` named `console`. This story asserts those properties rather than changing them. **Preserve:** `merge_contextvars` as the first shared processor — `request_id` is a contextvar bound by django-structlog and disappears without it. |
| `src/config/celery_app.py` | UPDATE (tests only — no source change expected) | Today: calls `configure_observability()` at `:12` before `Celery(...)`, and registers `DjangoStructLogInitStep` at `:19` with the comment recording that it carries `request_id` from the enqueueing request into the task's log context. This story asserts it. |
| `tests/integration/conftest.py` | UPDATE | Today: 21 lines, only a `pytest_collection_modifyitems` hook that auto-marks everything under `tests/integration/` as `@pytest.mark.integration`. Adds the session-scoped `otel_tracing` fixture and the function-scoped `spans` fixture. **Preserve:** the auto-marking hook — it is why individual integration tests carry no explicit marker. |
| `tests/integration/test_log_correlation.py` | NEW | The AC #2/#3/#4 assertions: three-identifier correlation on a request log line, trace_id agreement between the log line and the captured span, request→task propagation, and (once Epic 2 lands) the mapper's sync event. |
| `tests/unit/test_observability_logging.py` | UPDATE | Today: 105 lines covering `resolve_log_format`, the processor chain and `build_logging_config`. Adds the AC #1 no-file/no-rotation and JSON-renderer assertions. |
| `tests/unit/test_settings.py` | UPDATE | Adds the textual position assertion for `DJANGO_STRUCTLOG_CELERY_ENABLED` inside the Celery block. |
| `tests/unit/test_celery_app.py` | UPDATE | Adds the `DjangoStructLogInitStep` registration assertion. |

**Line-range verification.** AD-24 now cites the `base.py` Celery block as `:296-335`, corrected from the `:296-313` an earlier revision carried. Re-confirmed against the tree: line 296 is the `# Celery` banner and line 335 is `CELERY_WORKER_HIJACK_ROOT_LOGGER = False`, the block's last line — `:313` is `CELERY_RESULT_BACKEND_ALWAYS_RETRY = True`, mid-block. Treat 296–335 as the block's extent when placing the moved setting. Placing `DJANGO_STRUCTLOG_CELERY_ENABLED` at the top of the block shifts every line below it by the number of lines moved; state the new extent in Completion Notes so Epic 7 declares the region against the range as it stands after this story.

### Testing Requirements

- `tests/unit/test_observability_logging.py`, `tests/unit/test_settings.py`, `tests/unit/test_celery_app.py` — no I/O, no database, no network, milliseconds each.
- `tests/integration/test_log_correlation.py` and the new `tests/integration/conftest.py` fixtures — the `@pytest.mark.integration` marker is applied **automatically** by `tests/integration/conftest.py:11-18`; do not add it by hand. Tests touching the ORM need `pytest.mark.django_db` (the file-level `pytestmark = pytest.mark.django_db` pattern at `tests/integration/test_request_logging.py:28` is the convention here).
- Assertions the ACs demand, stated concretely:
  - one built `LOGGING` dict, exactly one handler, class `logging.StreamHandler`, no `filename` key anywhere, no handler class name containing `File`, `Rotating` or `SysLog`;
  - one request-scoped `django_structlog` event dict containing all three of `request_id`, `trace_id`, `span_id`, with `len(trace_id) == 32` and `len(span_id) == 16`;
  - the log line's `trace_id` equals the hex-formatted `trace_id` of the span the in-memory exporter captured for that request;
  - `config.celery_app.app.steps["worker"]` contains `DjangoStructLogInitStep`;
  - a task enqueued from a request logs the same `request_id` as that request.
- The session-scoped tracer provider must be torn down with `DjangoInstrumentor().uninstrument()`; leaving Django instrumented for the whole session mutates `settings.MIDDLEWARE` for every subsequent test. Each integration test must leave resources as it found them.
- AD-20 coverage floor: 90% including templates, enforced by `pixi run test-cov` (`--cov-fail-under=90`) with `COVERAGE_CORE=ctrace` from `pixi.toml:150`.

#### Project Structure Notes

The Structural Seed places observability at `src/config/observability/` as the "existing cross-cutting home" — this story adds nothing new to the layout and stays inside it. Two variances between the seed and the repository today are relevant and are **not** this story's to fix: `src/config/authorization/` (the mapper, Epic 2) and `src/config/startup/` (the refusals, Epic 4) do not exist yet, which is why Task 5 is blocked rather than deferred by choice. `src/config/websocket.py` still exists and is still in the coverage `omit` list at `pyproject.toml:168`; AD-16 deletes it in Epic 1 and this story must not touch it.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.1] — story statement and the four acceptance-criteria blocks.
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6] — "Largely satisfied today, so this epic is mostly about what must not regress, plus the one path that is verified nowhere."
- [Source: _bmad-output/planning-artifacts/epics.md#Epic dependency flow] (`epics.md:297`) — "its one dependency beyond Epic 1 is Story 6.1's assertion that authorization changes emit correlated events, which needs Epic 2's mapper."
- [Source: _bmad-output/planning-artifacts/epics.md#FR-46] — "Correlated structured logging — JSON to stdout carrying `request_id`, `trace_id`, `span_id`, propagating into task execution where selected."
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — the Logging row and the Test location row.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24] — feature-owned regions by declared markers and by no other mechanism; the open, carrier-declared set of region-bearing paths and the `base.py:296-335` citation.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20] — the single global coverage floor.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#SC-7] — "emits correlated structured logs carrying request and trace identifiers, and produces spans for ASGI requests."
- [Source: src/config/observability/logging.py:29-71,138-196] — `add_otel_context`, `shared_processors`, `build_logging_config`.
- [Source: src/config/settings/base.py:281-296] — `LOGGING`, `configure_structlog()`, `DJANGO_STRUCTLOG_CELERY_ENABLED`, the Celery banner.
- [Source: src/config/celery_app.py:12-19] — `configure_observability()` and `DjangoStructLogInitStep`.
- [Source: tests/integration/test_request_logging.py:1-56] — the `caplog` pattern and why `structlog.testing.capture_logs` is not used.
- [Source: tests/integration/conftest.py:11-18] — automatic `@pytest.mark.integration` marking.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
