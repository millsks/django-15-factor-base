---
status: done
baseline_revision: ec47bc5
review_loop_iteration: 0
warnings: [oversized]
---

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

- [x] Task 1 — Lock the JSON-to-stdout, no-files, no-rotation property with tests (AC: #1)
  - [x] In `tests/unit/test_observability_logging.py`, add a class asserting over `build_logging_config(debug=False)`: `handlers` has exactly one key, `console`; its `class` is `"logging.StreamHandler"`; `root["handlers"] == ["console"]`.
  - [x] Add a reusable in-module assertion over any built config: no handler `class` value contains `File`, `Rotating`, `Watched` or `SysLog`, and no handler dict carries a `filename` key. Apply it to `build_logging_config(debug=False)`.
  - [x] Apply the same assertion to `build_logging_config(debug=False, log_format="json", extra_handlers={"mail_admins": {"level": "ERROR", "filters": ["require_debug_false"], "class": "django.utils.log.AdminEmailHandler"}})` — the shape `src/config/settings/production.py:131-137` passes. Assert the extra handler merged in *and* still stayed off the root logger (`root["handlers"] == ["console"]`), so the deployed configuration is covered by the same no-file property.
  - [x] Add a test that `_renderer("json")` returns a list whose **last** element is an instance of `structlog.processors.JSONRenderer`, and that `resolve_log_format(debug=False)` (no explicit format) returns `"json"`. Together these are "JSON event stream" as an asserted fact.
  - [x] Add a test in `tests/unit/test_settings.py` that the **production settings module's own** `LOGGING` carries no file handler and no `filename` key, driven through the existing `production_env` fixture (`tests/unit/test_settings.py:112`) and `importlib.import_module(PRODUCTION)`. The literal-dict test above cannot catch production adding a file handler later; this one can.

- [x] Task 2 — Hoist the span-capture fixture, then assert all three identifiers on one line (AC: #2)
  - [x] **The tree already has this fixture, twice.** `tests/integration/test_asgi_request_path.py:190-229` and `tests/integration/test_local_trace_correlation.py:121-147` define `recorded_spans` fixtures with identical bodies (only the docstrings and the assertion message's FR number differ). Hoist one copy into `tests/integration/conftest.py` under the same name — `recorded_spans` is the name the tree uses; do not invent a new one — and delete both local copies. Write the hoisted assertion message so it names neither FR (it now serves three modules).
  - [x] The fixture's assertion calls `_sdk_is_disabled()`, so `tests/integration/conftest.py` needs its own copy of that helper. A test module cannot import from a conftest, so the two existing modules keep theirs: `test_local_trace_correlation.py` still calls `_sdk_is_disabled` directly at `:132` and `:250`, and both modules still call `_span_absence_hint()` in assertion messages. Delete only the fixture from each module — leave both helpers in place.
  - [x] **Do not follow the original spec's `otel_tracing` fixture design.** It called `trace.set_tracer_provider(provider)` and `DjangoInstrumentor().instrument()`. Both are wrong here: `config/__init__.py` imports `config.celery_app`, which calls `configure_observability()` at module scope, so an SDK `TracerProvider` and all four instrumentors are **already live** before any test runs, and `trace.set_tracer_provider` refuses to override (it warns and ignores). Instrumenting Django a second time would mutate `settings.MIDDLEWARE` for the rest of the session. The `recorded_spans` pattern — attach a `SimpleSpanProcessor(InMemorySpanExporter())` to the live provider, restore `_span_processors` in `finally` — is the correct and already-proven mechanism.
  - [x] Add `tests/integration/test_log_correlation.py` (NEW). Module docstring must state what this module adds over `tests/integration/test_local_trace_correlation.py`: that module covers FR-21 (observability is not substituted locally) and asserts `trace_id`/`span_id` only; this one covers FR-46 / SC-7 and asserts **`request_id`, `trace_id` and `span_id` together on one log line**, which nothing asserts today.
  - [x] The core assertion: drive `client.get(reverse("account_login"))` with `caplog.at_level(logging.INFO, logger="django_structlog")`, take the `request_started` event dicts, and assert **one** dict carries all three keys; `len(trace_id) == 32`, `len(span_id) == 16`, `int(trace_id, 16) != 0`, `int(span_id, 16) != 0`, and `request_id` is a non-empty string. Reuse the `_events(caplog, name)` helper shape from `tests/integration/test_local_trace_correlation.py:107-118` (reads `record.msg` dicts).
  - [x] Add the agreement assertion: with `recorded_spans` active, the log line's `trace_id` is among `{format(span.context.trace_id, "032x") for span in recorded_spans.get_finished_spans()}`.
  - [x] Drive `account_login`, not `home`. AD-29 deletes `home` and `about` as demonstration content along with their `TemplateView`s — `src/config/urls.py:28-30` already carries a comment saying Story 7.4 removes them. `account_login` is registered by `path("accounts/", include("allauth.urls"))` at `src/config/urls.py:46` and is `core` in every combination because FR-4's interactive flow is immovable core. It is already reversed by `tests/integration/users/test_views.py:116`. `home` still exists today (`src/config/urls.py:36`) — the point is not that it is gone, but that this story must not add a new dependency on a route that is being deleted.
  - [x] Do not use `structlog.testing.capture_logs` — it installs its own processor chain, dropping both `merge_contextvars` (so `request_id` vanishes) and `add_otel_context` (so `trace_id`/`span_id` vanish). `tests/integration/test_local_trace_correlation.py:20-24` records this; keep the `caplog` approach.

- [x] Task 3 — Position the Celery correlation switch so it can become a `feature:celery` region (AC: #3)
  - [x] Move `DJANGO_STRUCTLOG_CELERY_ENABLED = True` **and its two preceding comment lines** from `src/config/settings/base.py:430-432` to immediately after the `# Celery` banner and its rule line at `src/config/settings/base.py:437-438`, keeping the value and the comment text unchanged. It must be contiguous with the rest of the Celery-owned settings so Epic 7 can enclose the whole block in one `feature:celery` / `/feature:celery` marker pair.
  - [x] `REDIS_URL` / `REDIS_SSL` (`:434-435`) stay exactly where they are — they are a separate region, and `CELERY_BROKER_URL` at `:443` reads `REDIS_URL`, so they must continue to precede the block.
  - [x] Do **not** add the marker comments, an `if` guard, a conditional import, a `try/except ImportError`, or a settings-module override to achieve feature scoping — AD-24 forbids every one of those. This story only makes the block contiguous; Epic 7 declares the region.
  - [x] Add a unit test in `tests/unit/test_settings.py` that reads `src/config/settings/base.py` as text (this module reads settings only via `importlib` today — a textual read is new here, so use `Path(config.settings.base.__file__).read_text()` or the repo-relative path, and say in the docstring why the assertion is textual: the property is *position within a block*, which the imported module cannot show) and asserts that the `DJANGO_STRUCTLOG_CELERY_ENABLED` assignment line index is greater than the `# Celery` banner line index, that every assignment line strictly between them is `CELERY_`-prefixed (today: none), and that it precedes the next section banner (`# django-allauth`). A later edit that moves it back above `REDIS_URL` then fails.

- [x] Task 4 — Assert the Celery-side correlation wiring reaches task execution (AC: #3)
  - [x] Extend `tests/unit/test_celery_app.py` with a test that `DjangoStructLogInitStep` is in `config.celery_app.app.steps["worker"]` (wired at `src/config/celery_app.py:20`). That step is what connects `task_prerun`, which binds the published metadata into the task's log context.
  - [x] Add a test that the **publish side is actually connected**, which is the observable consequence of `DJANGO_STRUCTLOG_CELERY_ENABLED = True`: `django_structlog.apps.DjangoStructLogConfig.ready()` calls `CeleryReceiver().connect_signals()`, which connects `receiver_before_task_publish` to `celery.signals.before_task_publish` and `receiver_after_task_publish` to `after_task_publish`. Assert by resolving `before_task_publish.receivers` (dereference weakrefs the way `tests/unit/test_celery_app.py:19-36` already does for `worker_ready`) and finding a bound method of `django_structlog.celery.receivers.CeleryReceiver`. Assert the *consequence*, never the settings value — the settings value is already covered by Task 3's position test.
  - [x] Add `tests/integration/test_celery_log_correlation.py` (NEW) for the end-to-end half. It **must be its own module**: it imports `celery` and `django_structlog.celery` at module level, which are feature-owned, so a core module importing them could not survive pruning in the four combinations without Celery. AD-29 puts a feature's tests under that feature's disposition; Epic 7 marks this whole file `feature:celery`.
  - [x] In that module: define the task in the module itself with `@shared_task`. Do **not** enqueue `src/django_service/users/tasks.py:get_users_count` — AD-29 deletes that module rather than relocating it, and a test built on it would be removed with it.
  - [x] Drive the publish from inside a real request so `request_id` is bound by `django_structlog.middlewares.RequestMiddleware`: mount a test-local view that enqueues the task using `temporary_root_urlconf` (`tests/conftest.py:332`), then `client.get()` it. Enqueuing from the test body directly would prove nothing — the middleware's contextvars are cleared once the response is returned.
  - [x] **`CELERY_TASK_ALWAYS_EAGER` cannot carry this assertion and the original spec's instruction to use it is wrong.** Under eager execution `apply_async` short-circuits to `apply()`, so `before_task_publish` never fires and `__django_structlog__` is never written into the headers; and `task_prerun`'s receiver is connected only by the worker bootstep, which no test process runs. The task body would then execute in the *same* contextvar context as the request and log the request's `request_id` incidentally — the test would pass identically with `DJANGO_STRUCTLOG_CELERY_ENABLED = False` and assert nothing. The whole suite already runs eager by default (`src/config/settings/test.py:89,91` plus `--ds=config.settings.test`), so this trap is live.
  - [x] Assert the propagation vehicle instead, in two halves that use the **real** receivers: (a) publish — with `app.conf.task_always_eager` off and `app.conf.broker_url` pointed at kombu's in-process `memory://` transport for the duration of the test (restore both in a `finally`), enqueue from the view and capture the published headers via a probe connected to `before_task_publish`; assert `headers["__django_structlog__"]["request_id"]` equals the `request_id` on the request's own `request_started` log line. (b) execute — feed those captured headers through the real `django_structlog.celery.receivers.CeleryReceiver().receiver_task_prerun(...)` with a task request object carrying `__django_structlog__`, emit a log line from inside that bound context, and assert it carries the same `request_id`. Together these are "correlation propagates into task execution" without a live broker or worker.
  - [x] If `memory://` publishing proves unworkable in this environment, fall back to asserting (a) by invoking the connected `receiver_before_task_publish` directly with a `headers` dict from inside the request, and record the substitution in Completion Notes. Do not silently weaken the assertion to the eager-mode version rejected above.

- [x] Task 5 — Assert the mapper's authorization-change event is correlated (AC: #4)
  - [x] **No longer blocked — Epic 2 has landed.** The original spec said `src/config/authorization/` does not exist. It does: the mapper is `src/config/authorization/mapper.py`, and `sync_authorization` (`:678`) already emits `logger.info("authorization.synced", ...)` at `:783-791` with keys `idp_subject`, `groups_added`, `groups_removed`, `groups_ignored`, `is_staff`, `is_superuser`. Logger name is `config.authorization.mapper`.
  - [x] The gap is precisely that **no test anywhere asserts `request_id` or `trace_id` on `authorization.synced`**. The existing coverage (`tests/integration/authorization/test_mapper_sync.py:180`) asserts the payload keys through `structlog.testing.capture_logs`, which by construction cannot see either identifier.
  - [x] Add the assertion to `tests/integration/test_log_correlation.py`: POST `reverse("local_persona_signin", kwargs={"persona_key": "staff"})` with `recorded_spans` active and `caplog.at_level(logging.INFO, logger="config.authorization.mapper")`. `src/config/local_dev/views.py:173-175` runs the real `resolve_user` then `sync_for_interactive` inside the request, so `authorization.synced` is emitted with the request's contextvars bound. Assert the event carries `request_id` and a 32-hex non-zero `trace_id` **alongside** its group-change payload, and that `groups_added` is non-empty so the event is a real authorization change rather than a no-op sync.
  - [x] Mirror the preconditions from `tests/integration/test_local_dev_signin.py`: the `_local` fixture (`:92`, `COMPONENT_RUNTIME=local`), `_contract` (`:97`), and `_groups` (`:106`, calls `django_service.users.provisioning.provision_designated_groups()` — the only sanctioned `Group` creator). The local sign-in route is mounted only when `config.locality.is_local()` (`src/config/urls.py:104-106`), which the test settings already satisfy. No network: claims are synthesized by `config.local_dev.personas.build_claims`, there is no JWKS fetch.
  - [x] `groups_added` compares as a **tuple**, not a list.

- [x] Task 6 — Run the gate (AC: #1, #2, #3, #4)
  - [x] `pixi run test`, then `pixi run test-integration`, then `pixi run ci`. Never bare `pytest`/`python`; never `pip`/`uv`.
  - [x] The coverage task is `pixi run test-cov`, not `pixi run cov` — `ci` chains `precommit → build → typecheck → lint → test-cov` (`pixi.toml:637-643`).

## Dev Notes

### Architecture Constraints

- **Consistency Conventions → Logging** — "Structured, JSON to stdout, carrying `request_id`, `trace_id`, `span_id`. Every authorization change emits an event. No files, no rotation." This is the whole of AC #1, #2 and #4 stated as an invariant; there is no AD, so the convention table is the binding text.
- **AD-24** — "A `core` path carries feature-owned regions by declared markers, and by no other mechanism." The set of region-bearing paths is open and the carrier declares it as an open `[[regions]]` array. This story touches one of them, `src/config/settings/base.py`, and only to make the Celery block contiguous. **Forbidden:** "No other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`." **Prevents:** a missed region leaving `CeleryInstrumentor().instrument()` in the **four** combinations whose environment no longer contains the instrumentor — an `ImportError` at boot that path-level reconciliation cannot see. (The spine's Prevents clause still says *eight*, from the retired twelve-combination model.)
- **AD-29 / Consistency Conventions → Test location** — tests live under `tests/` mirroring `src/` and carry the disposition of what they cover; a feature's tests are `feature:<name>` and are pruned with it, except the immovable-core assertion suite (AD-30), which is `core`. Consequence for this story: `tests/integration/test_log_correlation.py` is `core` and must import nothing feature-owned at module level; `tests/integration/test_celery_log_correlation.py` is `feature:celery` and is pruned with Celery. Do not use `pytest.importorskip` to merge them — it is banned outright by `tests/unit/test_suite_policy.py:55` and would leave the test present-but-skipped, violating FR-28.
- **AD-20** — the coverage floor is ninety percent including templates, everywhere, with `COVERAGE_CORE=ctrace` in force (`pixi.toml:407`). `pixi run test-cov` carries `--cov-fail-under=90`.
- **Project standard** — never `print()`; never stdlib `logging` in project code (test modules reading `caplog` may import `logging` for the level constant, as `tests/integration/test_local_trace_correlation.py:29` already does). `structlog` only, JSON to stdout.

### Suite policy constraints that bind the new tests

- `tests/unit/test_suite_policy.py` scans **every** `.py` under `tests/`. Banned outright: `@pytest.mark.skip/skipif/xfail` (`:51`), `pytest.skip` / `pytest.xfail` / `pytest.importorskip` (`:55`), `pytest.mark.django_db(databases=...)` (`:63`), and branching on a `vendor` attribute (`:59`). A missing tracer provider must therefore **fail** with a diagnostic message, never skip — the `_span_absence_hint()` pattern exists for exactly this.
- `RECORDED_EXEMPTIONS` (`tests/unit/test_suite_policy.py:132-138`) is keyed by path *and exact count* and fails in both directions. Nothing here should need an entry; if one does, the design is wrong.
- No policy test holds a roster or count of test modules, so adding two modules needs no registration.
- Ruff runs over `tests/` with **no** `per-file-ignores` (there is no such table in `pyproject.toml`). Consequences: `SLF` is selected, so `provider._active_span_processor._span_processors` needs `# noqa: SLF001` — copy the existing annotations verbatim; `PLC0415` for in-function imports; `PLR2004` for magic numbers; `INP` means a new test *directory* would need `__init__.py` (neither new module needs a new directory); `I` with `force-single-line` means one import per line. `D` (pydocstyle) is **not** selected, so test docstrings are conventional here, not enforced. Never write a bare `# noqa` (PGH004) or an unused one (RUF100).
- `mypy` runs against `src/` only (`pixi run typecheck`), so the new test modules are not type-checked — but `src/config/settings/base.py` is, and Task 3's move must keep it clean.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/settings/base.py` | UPDATE | The only source change in the story. `DJANGO_STRUCTLOG_CELERY_ENABLED = True` sits at `:432` with its two comment lines at `:430-431`, separated from the Celery block by `REDIS_URL`/`REDIS_SSL` at `:434-435`. Move all three lines to immediately after the `# Celery` banner (`:437`) and its rule line (`:438`). **Preserve:** `LOGGING = build_logging_config(...)` at `:422-426` and `configure_structlog()` at `:428` — the ordering is load-bearing (structlog must be configured while settings are being read); and `MIDDLEWARE` where `django_structlog.middlewares.RequestMiddleware` sits at `:276`, deliberately after `AuthenticationMiddleware` so `request.user` is resolvable as `user_id`. |
| `src/config/observability/logging.py` | UNCHANGED (tests only) | `add_otel_context` (`:29-54`) injects `trace_id`/`span_id` from the active span; `shared_processors()` (`:57-71`) is used both as the structlog chain (via `configure_structlog`, `:74-92`) and as the stdlib `foreign_pre_chain` (`:188`), which is what makes Django/allauth/Celery records carry the same context; `_renderer` (`:114-135`) ends the JSON chain in `JSONRenderer()`; `build_logging_config` (`:138-196`) emits exactly one `logging.StreamHandler` named `console` and merges `extra_handlers` at `:169` without adding them to the root logger. This story asserts those properties rather than changing them. **Preserve:** `merge_contextvars` as the first shared processor (`:66`) — `request_id` is a contextvar bound by django-structlog and disappears without it. |
| `src/config/celery_app.py` | UNCHANGED (tests only) | Calls `configure_observability()` at `:14` before `Celery(...)`, and registers `DjangoStructLogInitStep` at `:20` with the comment recording that it carries `request_id` from the enqueueing request into the task's log context. This story asserts it. |
| `tests/integration/conftest.py` | UPDATE | 19 lines today, holding only the `pytest_collection_modifyitems` auto-marking hook at `:12-19`. Gains the hoisted `recorded_spans` fixture and its `_sdk_is_disabled` helper. **Preserve:** the auto-marking hook — it is why individual integration tests carry no explicit `@pytest.mark.integration`. |
| `tests/integration/test_asgi_request_path.py` | UPDATE | Delete the local `recorded_spans` fixture at `:190-229`; keep `_sdk_is_disabled` and `_span_absence_hint`, both still used in assertion messages. |
| `tests/integration/test_local_trace_correlation.py` | UPDATE | Delete the local `recorded_spans` fixture at `:121-147`; keep `_sdk_is_disabled` (still called at `:132`, `:250`) and `_span_absence_hint`. |
| `tests/integration/test_log_correlation.py` | NEW · `core` | AC #2's three-identifier assertion and trace-id agreement, driven through `account_login`; AC #4's mapper correlation, driven through the local sign-in route. Imports nothing feature-owned. |
| `tests/integration/test_celery_log_correlation.py` | NEW · `feature:celery` | AC #3's request→task propagation. Imports `celery` and `django_structlog.celery` at module level, which is why it is separate. |
| `tests/unit/test_observability_logging.py` | UPDATE | 105 lines today. Adds the AC #1 no-file/no-rotation assertions and the JSON-renderer assertion. |
| `tests/unit/test_settings.py` | UPDATE | 905 lines, all flat functions, no classes; reads settings only via `importlib` today. Adds the textual position assertion for `DJANGO_STRUCTLOG_CELERY_ENABLED` and the production-`LOGGING` no-file-handler assertion. |
| `tests/unit/test_celery_app.py` | UPDATE | 81 lines. Adds the `DjangoStructLogInitStep` registration assertion and the `before_task_publish` connection assertion. `_connected_receivers()` at `:19-36` already dereferences weakrefs for `worker_ready`; generalize or copy that shape. |

### Line-range reconciliation (verified at `ec47bc5`, 2026-08-29)

The story was authored 2026-08-15; six epics have landed since. Every line number below was re-read from the tree. The **corrected** value is what this spec uses.

| Claim as written | Corrected |
| --- | --- |
| `base.py:289-291` — `DJANGO_STRUCTLOG_CELERY_ENABLED` | `:430-432` (comments `:430-431`, assignment `:432`) |
| `base.py:293-294` — `REDIS_URL`/`REDIS_SSL` | `:434-435` |
| `base.py:296` — `# Celery` banner | `:437` |
| `base.py:296-335` — Celery block extent | `:437-476` (`CELERY_WORKER_HIJACK_ROOT_LOGGER` at `:476`; `# django-allauth` at `:477`) |
| `base.py:281-285` — `LOGGING` | `:422-426`; `configure_structlog()` at `:428` |
| `base.py:164-179` / `:175` — `MIDDLEWARE` / `RequestMiddleware` | `RequestMiddleware` at `:276` |
| `celery_app.py:12` / `:19` | `configure_observability()` at `:14`; `DjangoStructLogInitStep` at `:20` |
| `production.py:31-44` — extra handlers | `:127-150`; the `extra_handlers` dict is `:131-137`; `LOGGING["filters"]` bolted on at `:151-153` |
| `conftest.py` 21 lines, hook `:11-18` | 19 lines, hook `:12-19` |
| `test_request_logging.py:33-48` — `_events()` | `:33-44` |
| `telemetry.py:135`/`:137` — instrumentor regions | `:205-208` (Django `:205`, Celery `:206`, psycopg `:207`, redis `:208`); imports at `:21` (Celery) and `:24` (redis) |
| `pyproject.toml:168` — coverage `omit` | `:292-298` |
| `pixi run cov` | `pixi run test-cov` (`pixi.toml:601`); there is no `cov` task |

Substantive corrections beyond line drift:

1. **Task 5 is not blocked.** Epic 2 is complete (`sprint-status.yaml`, stories 2-1…2-8 all `done`). `src/config/authorization/mapper.py` exists and already emits `authorization.synced`. The deferral instruction in the original Task 5 is void; the task is in scope for this story.
2. **`src/config/websocket.py` does not exist** and is not in the coverage `omit` list. The original Project Structure note's instruction "must not touch it" is moot. `src/config/startup/` also now exists (Epic 4), so only the seed variance for `websocket.py` was real and it is resolved.
3. **The span-capture fixture already exists twice** under the name `recorded_spans`. The original Task 2's `otel_tracing` + `spans` design would install a second tracer provider and re-instrument Django; it is replaced by hoisting the existing fixture. See Task 2.
4. **`CELERY_TASK_ALWAYS_EAGER` cannot carry AC #3.** See Task 4 for the mechanism and the replacement.
5. **`home` still exists** (`src/config/urls.py:36`), with a comment at `:28-30` recording that Story 7.4 deletes it. The instruction to drive `account_login` stands, for the forward-looking reason, not because `home` is already gone.
6. **The Celery block's boundary after the move.** `DJANGO_STRUCTLOG_CELERY_ENABLED` plus its two comment lines land at `:439-441`; the block then runs `:437-476` unchanged in extent (three lines removed above it, three added inside it). State the verified post-change extent in Completion Notes so Epic 7 declares the region against the range as it stands after this story.

### Testing Requirements

- `tests/unit/test_observability_logging.py`, `tests/unit/test_settings.py`, `tests/unit/test_celery_app.py` — no I/O, no database, no network, milliseconds each. The textual `base.py` read in `test_settings.py` is a filesystem read of a source file in the repo, which the unit tier already does elsewhere for policy assertions; keep it to one `read_text()`.
- `tests/integration/test_log_correlation.py`, `tests/integration/test_celery_log_correlation.py`, and the conftest fixture — the `@pytest.mark.integration` marker is applied **automatically** by `tests/integration/conftest.py:12-19`; do not add it by hand. Tests touching the ORM need `pytest.mark.django_db` (the file-level `pytestmark = [pytest.mark.integration, pytest.mark.django_db]` at `tests/integration/test_local_trace_correlation.py:52` is the convention here).
- Assertions the ACs demand, stated concretely:
  - one built `LOGGING` dict, exactly one handler, class `logging.StreamHandler`, no `filename` key anywhere, no handler class name containing `File`, `Rotating`, `Watched` or `SysLog` — asserted for both the default build and the production-shaped one;
  - `_renderer("json")[-1]` is a `JSONRenderer`; `resolve_log_format(debug=False)` is `"json"`;
  - one request-scoped `django_structlog` event dict containing all three of `request_id`, `trace_id`, `span_id`, with `len(trace_id) == 32`, `len(span_id) == 16`, both non-zero, and `request_id` non-empty;
  - the log line's `trace_id` is among the hex-formatted trace ids of the spans the in-memory exporter captured for that request;
  - `DjangoStructLogInitStep` is in `config.celery_app.app.steps["worker"]`, and a `CeleryReceiver` method is connected to `before_task_publish`;
  - the headers published for a task enqueued inside a request carry `__django_structlog__["request_id"]` equal to that request's `request_id`, and a log line emitted from inside the context those headers restore carries the same `request_id`;
  - `authorization.synced`, emitted by the real mapper inside a request, carries `request_id` and a valid `trace_id` alongside a non-empty `groups_added`.
- Every fixture restores what it found: `recorded_spans` puts `_span_processors` back and shuts its processor down; the Celery test restores `app.conf.task_always_eager` and `app.conf.broker_url`; `temporary_root_urlconf` restores the URLconf. `reset_telemetry_for_testing()` must **not** be called — clearing the process-wide guard would let a later `configure_telemetry()` instrument Django, Celery, psycopg and redis a second time for the rest of the session.
- AD-20 coverage floor: 90% including templates, enforced by `pixi run test-cov` with `COVERAGE_CORE=ctrace`.

#### Project Structure Notes

The Structural Seed places observability at `src/config/observability/` as the existing cross-cutting home; this story adds nothing new to the layout and stays inside it. The two seed variances the original spec flagged are resolved: `src/config/authorization/` (Epic 2) and `src/config/startup/` (Epic 4) both exist now. `src/config/websocket.py` is already gone.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.1] — story statement and the four acceptance-criteria blocks.
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6] — "Largely satisfied today, so this epic is mostly about what must not regress, plus the one path that is verified nowhere."
- [Source: _bmad-output/planning-artifacts/epics.md#FR-46] — "Correlated structured logging — JSON to stdout carrying `request_id`, `trace_id`, `span_id`, propagating into task execution where selected."
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — the Logging row and the Test location row.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24] — feature-owned regions by declared markers and by no other mechanism.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20] — the single global coverage floor.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#SC-7] — "emits correlated structured logs carrying request and trace identifiers, and produces spans for ASGI requests."
- [Source: _bmad-output/implementation-artifacts/epic-6-context.md] — epic goal, the six-story list, and the four-of-six / two-of-six combination arithmetic.
- [Source: src/config/observability/logging.py:29-71,114-135,138-196] — `add_otel_context`, `shared_processors`, `_renderer`, `build_logging_config`.
- [Source: src/config/settings/base.py:422-441] — `LOGGING`, `configure_structlog()`, `DJANGO_STRUCTLOG_CELERY_ENABLED`, `REDIS_URL`, the Celery banner.
- [Source: src/config/celery_app.py:14,20] — `configure_observability()` and `DjangoStructLogInitStep`.
- [Source: src/config/authorization/mapper.py:678,783-791] — `sync_authorization` and the `authorization.synced` event.
- [Source: src/config/local_dev/views.py:136,173-175] — `persona_signin` drives the real mapper inside a request.
- [Source: tests/integration/test_local_trace_correlation.py:1-25,107-147] — the `caplog` rationale and the `recorded_spans` fixture being hoisted.
- [Source: tests/integration/test_asgi_request_path.py:190-229] — the duplicate `recorded_spans` fixture.
- [Source: tests/unit/test_suite_policy.py:51-63,132-138] — the banned forms and the recorded exemptions.
- [Source: .pixi/envs/dev/.../django_structlog/apps.py, celery/receivers.py:211-224] — `connect_signals` connects only the publish side; `connect_worker_signals` connects `task_prerun`.

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m]

### Debug Log References

- `pixi run lint` / `pixi run typecheck` / `pixi run test` / `pixi run test-integration` / `pixi run ci`.
- Ad-hoc single-module runs via `pixi run -e dev python -m pytest <path> -q`.
- Two throwaway probes under the session scratchpad (not in the tree) established how celery's
  configuration is actually reachable from a test; see the first completion note.

### Completion Notes List

1. **Task 4 used `memory://` as specified — the documented fallback was not needed — but the
   *mechanism* for turning eager off had to change.** `app.conf.task_always_eager = False` and
   `app.conf.update(task_always_eager=False)` both look like they take and change nothing: celery's
   `Settings` is a `ConfigurationView` opened with `prefix="CELERY"`, so `__getitem__` resolves
   `task_always_eager` by trying `CELERY_TASK_ALWAYS_EAGER` *first*, and that spelling is answered by
   the Django settings map before `changes` is ever consulted. What does work is Django's own
   settings: `app.config_from_object("django.conf:settings", namespace="CELERY")` leaves the
   application's configuration a live view over `django.conf.settings`, so pytest-django's `settings`
   fixture is both the way in and the way back out. Verified: `task_always_eager` reads `False` and
   `broker_url` reads `memory://` inside the override, and both revert after it. Publishing over
   kombu's in-process transport then works, `before_task_publish` fires, and
   `headers["__django_structlog__"]["request_id"]` equals the enqueueing request's own
   `request_started` `request_id`.
2. `@shared_task(ignore_result=True)` on the probe task keeps `apply_async` away from the Redis
   result backend, which nothing in the run stands up.
3. `assert_writes_no_files` is public in `tests/unit/test_observability_logging.py` and imported by
   `tests/unit/test_settings.py`, so "what counts as a file handler" has one definition rather than
   two that can drift. The spec asked for a reusable in-module assertion; this is that assertion,
   named so the second call site can reach it.
4. Hoisting `recorded_spans` into `tests/integration/conftest.py` left three imports unused in
   `tests/integration/test_asgi_request_path.py` (`trace`, `TracerProvider`, `SimpleSpanProcessor`)
   and one in `tests/integration/test_local_trace_correlation.py` (`SimpleSpanProcessor`); they were
   removed. `InMemorySpanExporter` survives in both modules as an annotation only, so ruff's `TC`
   rules require it under `TYPE_CHECKING` — it moved there. `_sdk_is_disabled` and
   `_span_absence_hint` stayed in both modules as the spec directs.
5. `reset_telemetry_for_testing()` was not called anywhere, `trace.set_tracer_provider` was not
   called anywhere, and nothing was added to `RECORDED_EXEMPTIONS`.
6. **Verified post-change extent of the Celery block in `src/config/settings/base.py`: lines
   433–475.** `# Celery` banner at `:433`, its rule line at `:434`, the two moved comment lines at
   `:435-436`, `DJANGO_STRUCTLOG_CELERY_ENABLED = True` at `:437`, and
   `CELERY_WORKER_HIJACK_ROOT_LOGGER = False` at `:475`; `# django-allauth` begins at `:476`.
   `REDIS_URL`/`REDIS_SSL` now sit at `:430-431`, still ahead of the block that reads them. The move
   removed one net line above the banner, so the spec's predicted `:439-441` landing is `:435-437`
   in the tree as it stands. Epic 7 should declare the region against `433–475`.
7. Environment note, not a code issue: `tests/integration/test_image_payload.py` builds the payload
   image, and on this machine the first build stalled for ~20 minutes on a hung
   `docker-credential-desktop get` process. Killing that process let the build proceed. It is
   unrelated to this story's changes.

### File List

**Modified**

- `src/config/settings/base.py` — the only source change: `DJANGO_STRUCTLOG_CELERY_ENABLED` and its
  two comment lines moved inside the Celery block.
- `tests/integration/conftest.py` — gained the hoisted `recorded_spans` fixture and `_sdk_is_disabled`.
- `tests/integration/test_asgi_request_path.py` — local `recorded_spans` deleted; imports adjusted.
- `tests/integration/test_local_trace_correlation.py` — local `recorded_spans` deleted; imports adjusted.
- `tests/unit/test_observability_logging.py` — AC #1 no-file/no-rotation and JSON-renderer assertions.
- `tests/unit/test_settings.py` — production `LOGGING` no-file assertion; textual position assertion
  for `DJANGO_STRUCTLOG_CELERY_ENABLED`.
- `tests/unit/test_celery_app.py` — `DjangoStructLogInitStep` registration and `before_task_publish`
  connection assertions; `_connected_receivers` generalized to take a signal.

**Added**

- `tests/integration/test_log_correlation.py` — `core`. AC #2's three-identifier assertion and
  trace-id agreement through `account_login`; AC #4's mapper correlation through the local persona
  sign-in.
- `tests/integration/test_celery_log_correlation.py` — `feature:celery`. AC #3's request-to-task
  propagation, in the two halves the spec specifies.


## Dev Agent Record

### Agent Model Used

`claude-opus-5[1m]` via `bmad-dev-auto`, bmad-loop run `20260829-102544-6e44`.

### Debug Log References

- `pixi run ci` — exit 0. 1545 passed, total coverage 97.04% (floor 90).
- `DATABASE_URL=postgres://…@localhost:55432/gatedb pixi run test-cov` — exit 0,
  identical. Run because the correlation tests drive the real mapper, which writes
  `Group` membership inside a request.

**The session was stopped mid-flight and the story was finished inline.** The run
recorded `0 done, 0 deferred, 0 escalated` and paused for manual rollback, with the
implementation, three new modules and the reconciled task list all sitting
uncommitted and no task box ticked. The suggested `reset --hard` would have
discarded a complete story, so it was not taken; per this project's recovery note a
killed dev session is finished inline rather than re-driven. The only thing missing
from the gate was the formatter pass the session never reached — one file, which
`pre-commit` reformatted on the first run.

Each task was verified against the tree rather than ticked on trust:

| Task | Evidence |
|---|---|
| 1 | `test_the_default_build_writes_no_files`, `test_the_production_shaped_build_writes_no_files`, `test_the_default_build_has_exactly_one_console_stream_handler` and `test_the_json_chain_ends_in_the_json_renderer` in `tests/unit/test_observability_logging.py`. |
| 2 | `recorded_spans` hoisted to `tests/integration/conftest.py:48`; `test_a_request_event_carries_all_three` and `test_the_logged_trace_id_is_one_the_exporter_recorded`. |
| 3 | `DJANGO_STRUCTLOG_CELERY_ENABLED` **moved** out of the general logging block and into the `# Celery` block in `base.py`, which is what lets it become part of that file's `feature:celery` region rather than stranding a Celery-only switch in `core`. |
| 4 | Three cases in `tests/integration/test_celery_log_correlation.py`, including `test_the_override_actually_disables_eager_execution` — the control that stops the other two passing against a task that never really ran asynchronously. |
| 5 | `test_authorization_synced_carries_the_requests_identifiers`. |
| 6 | The gate, above. |

### Completion Notes List

**The spec's Task 5 was stale and the session reconciled it correctly.** As written
the task said "Blocked on Epic 2. `src/config/authorization/` does not exist in the
repository today", and the Dev Notes repeated it. Epic 2 landed long ago. The
session checked the tree rather than the prose, found `sync_authorization` in
`src/config/authorization/mapper.py` already emitting `authorization.synced`, and
rewrote the task around the real gap — which was never the mapper's absence but
that **no test anywhere asserted `request_id` or `trace_id` on that event**. The
existing coverage at `tests/integration/authorization/test_mapper_sync.py` asserts
the payload keys through `structlog.testing.capture_logs`, which by construction
cannot see either identifier. AC #4 is met rather than deferred.

**The Dev Notes' claim that `src/config/websocket.py` "still exists" is also
stale** — Story 1.4 deleted it with its coverage `omit` entry. Nothing in this
story touched it either way, so the staleness is recorded here rather than fixed
in the frozen spec.

**Task 3 is a move, not an addition.** `DJANGO_STRUCTLOG_CELERY_ENABLED` sat above
`REDIS_URL`, outside the Celery block, where an AD-24 `feature:celery` region could
not enclose it without also taking settings that are `core`. It now sits inside the
Celery block with its explanatory comment, so Epic 7 can mark the region without
moving code at declaration time.
