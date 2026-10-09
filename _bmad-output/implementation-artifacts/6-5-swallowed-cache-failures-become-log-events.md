---
status: done
baseline_revision: 84ae57c
review_loop_iteration: 0
followup_review_recommended: false
final_revision: 7c217cb
warnings: [oversized]
---

# Story 6.5: Swallowed cache failures become log events

Status: ready-for-dev

## Story

As an operator,
I want a degrading cache to be visible,
so that a component whose telemetry is immovable does not degrade invisibly.

## Acceptance Criteria

**Traceability:** FR-48 · SC-7

1. **Given** the Redis cache feature is selected
   **When** a cache operation raises
   **Then** the exception continues to be ignored so a cache outage degrades the component rather than stopping it

2. **Given** the same swallowed failure
   **When** it is ignored
   **Then** it emits a log event correlated with `request_id` and `trace_id`
   **And** nothing is swallowed silently

## Tasks / Subtasks

- [x] Task 1 — Confirm the gap before changing anything (AC: #1, #2)
  - [x] Read `src/config/settings/production.py:31-44`. `CACHES["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True` is set at `:41` with the comment "Mimicking memcache behavior". Nothing sets `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS`, anywhere in the repository.
  - [x] Read the installed `django_redis.cache.omit_exception` decorator: it catches `ConnectionInterrupted`, and when `self._ignore_exceptions` is true it calls `self.logger.exception("Exception ignored")` **only if** `self._log_ignored_exceptions` is true; otherwise it returns the fallback value and logs nothing. `self.logger` is `None` unless that flag is set. Both flags and the logger name are read from settings in `RedisCache.__init__` — `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS` (default `False`) and `DJANGO_REDIS_LOGGER` (default the module name).
  - [x] Conclusion to carry into the change: AC #1 already holds; **AC #2 does not**. Today a Redis outage is swallowed silently, which contradicts the project's own standard forbidding `except X: pass` and the spine's Runtime errors convention.

- [x] Task 2 — Turn the swallowed failure into a logged event (AC: #1, #2)
  - [x] In `src/config/settings/production.py`, immediately beside the `CACHES` block at `:33-44`, add `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True` and `DJANGO_REDIS_LOGGER = "django_service.cache"`.
  - [x] **Keep `IGNORE_EXCEPTIONS: True`.** AC #1 requires the exception to continue being ignored; removing it would turn a cache outage into an outage, which is the opposite of what this story asks for. State that in the comment beside the new settings, with the reasoning, per the spine's Rationale convention ("Reasoning lives beside the configuration it constrains, in the same file").
  - [x] Choose `django_service.cache` as the logger name deliberately: `build_logging_config` (`src/config/observability/logging.py:171-176`) already declares a `django_service` logger at the configured level, and `django_service.cache` inherits from it, so the event is levelled with the rest of the component's own output rather than with a third-party default. `logger.exception(...)` emits at `ERROR`, above the `INFO` root level set at `logging.py:194`.
  - [x] Place the two new settings **adjacent to the `CACHES` block**, contiguously, so they fall inside the `feature:redis` region AD-24 already declares over `production.py:31-44`. That declared range is the block as it stands today; adding two settings extends it, so record the block's new extent in Completion Notes for Epic 7. Do not scatter them, and do not open a second region.

- [x] Task 3 — Verify the correlation comes for free, and prove it (AC: #2)
  - [x] `django-redis` logs through the standard library, not structlog. That is fine and is the intended path: `build_logging_config` routes every stdlib record through `structlog.stdlib.ProcessorFormatter` with `foreign_pre_chain=shared_processors()` (`src/config/observability/logging.py:183-189`), and `shared_processors()` (`:57-71`) contains `structlog.contextvars.merge_contextvars` — which supplies `request_id` bound by `django_structlog.middlewares.RequestMiddleware` (`src/config/settings/base.py:175`) — and `add_otel_context` (`:29-54`) — which supplies `trace_id` and `span_id` from the active span. The comment at `logging.py:185-188` already records this design.
  - [x] Do **not** add a custom cache wrapper, a subclass of `RedisCache`, or a monkeypatch to emit the log line. The correlation works through the configured pipeline; introducing a wrapper adds a `core`/feature boundary problem for Epic 7 and a second place the behaviour can drift.
  - [x] Add `tests/integration/test_cache_degradation.py` proving all of it end to end (Task 4).

- [x] Task 4 — Test the degraded path against a cache that cannot connect (AC: #1, #2)
  - [x] Use `django.test.override_settings` to install, for the test only: a `CACHES["default"]` of `django_redis.cache.RedisCache` pointed at a closed loopback port (for example `redis://127.0.0.1:1/0`) with `OPTIONS = {"CLIENT_CLASS": "django_redis.client.DefaultClient", "IGNORE_EXCEPTIONS": True}`, plus `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True` and `DJANGO_REDIS_LOGGER = "django_service.cache"`.
  - [x] Override `CACHES` **in the same `override_settings` call** as the two flags. Django clears its cache handlers on a `CACHES` `setting_changed` signal but not on the two `DJANGO_REDIS_*` ones, and both flags are read in `RedisCache.__init__` — so without the `CACHES` override in the same call the cache object is never rebuilt and the flags have no effect. This is the single most likely way this test silently passes for the wrong reason.
  - [x] Assert AC #1: `django.core.cache.cache.get("anything")` returns `None` and raises nothing.
  - [x] Assert AC #2: with `caplog.at_level(logging.ERROR, logger="django_service.cache")`, exactly one record is captured; formatting it through the configured `structured` formatter yields an event carrying `request_id`, `trace_id` and `span_id`. Perform the cache call **inside a request** (drive `client.get(reverse("account_login"))` — a `core` route in every combination, since AD-29 deletes `home` and `about` — against a view or middleware that touches the cache, or bind the contextvars the middleware binds) with the `recorded_spans` fixture from `tests/integration/conftest.py` active (drive it through `drive_asgi` against a test-only URLconf; see Reconciliation) so a span is genuinely recording — `add_otel_context` (`logging.py:50-53`) adds nothing when no span is recording, so without an active span the `trace_id` assertion would fail for a reason unrelated to this story.
  - [x] Assert the negative that names the story: with `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS` **unset**, the same operation still returns `None` and captures **zero** records — this is the regression the two new settings prevent, and it is worth pinning so a later settings tidy-up cannot silently restore silence.
  - [x] Do not require a running Redis. A closed port is what produces `ConnectionInterrupted`; that is the entire mechanism under test.

- [x] Task 5 — Pin the production settings (AC: #1, #2)
  - [x] Add unit assertions in `tests/unit/test_cache_degradation_settings.py` (NEW, `feature:redis`; see Reconciliation) over the production settings module: `CACHES["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] is True`, `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS is True`, and `DJANGO_REDIS_LOGGER == "django_service.cache"`. All three together are the requirement; any one alone is not.

- [x] Task 6 — Document it (AC: #2)
  - [x] Add a short subsection to `docs/observability.md` stating that a Redis outage degrades rather than stops the component, that every ignored failure is logged at `ERROR` on `django_service.cache` correlated with `request_id`/`trace_id`, and that nothing is swallowed silently. Cross-reference the project standard forbidding `except X: pass`.

- [x] Task 7 — Run the gate (AC: #1, #2)
  - [x] `pixi run test`, then `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Reconciliation against the tree at `84ae57c` (2026-10-09)

The story was authored 2026-08-15. These corrections **supersede** any conflicting line reference or instruction below.

- `production.py` is 169 lines. `from .base import REDIS_URL` is `:14` (not `:12`); the `CACHES` block is `:33-46` (not `:31-44`), `IGNORE_EXCEPTIONS: True` at `:43`. The security block starts at `:48`. No `feature:redis` markers exist in the file yet (Epic 7 draws them); record the block's new extent in Completion Notes.
- `django_redis` (installed, `.pixi/envs/dev`) matches Task 1 exactly: `omit_exception` logs `self.logger.exception("Exception ignored")` only when `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS`; `self.logger` is built in `__init__` from `DJANGO_REDIS_LOGGER`. `get` routes through `_get`, decorated with `return_value=CONNECTION_INTERRUPTED`, and maps it to `default`. Nothing in `src/`, `tests/`, `docs/`, `pyproject.toml` or `pixi.toml` mentions `DJANGO_REDIS_*`. AC #1 holds; AC #2 does not.
- `logging.py` line references in the story are current (`add_otel_context` `:29-54`, `shared_processors` `:57-71`, `django_service` logger `:174`, `foreign_pre_chain` `:188`, root level `:194`).
- **Fixture name:** there is no `otel_tracing`/`spans` fixture. The span-recording fixture is `recorded_spans` (`tests/integration/conftest.py:73-112`); the ASGI driver is `drive_asgi` (`:175-212`). Auto-marking is `:49-56`.
- **No route touches the cache.** Nothing in `src/` performs a `django.core.cache` operation (the mapper, `users/models.py`, `health/state.py` and `jwks.py` all document *why not*). So the test cannot ride an existing route. It drives a real request through `config.asgi.application` with `drive_asgi` against a test-only URLconf (`ROOT_URLCONF` overridden to the test module, whose one view calls `cache.get`). The `RequestMiddleware` binds `request_id` and the ASGI instrumentor opens the span, exactly as in production; nothing is bound by hand.
- **How the correlation is observed.** A stdlib record's `record.msg` is the plain string `"Exception ignored"`; `request_id`/`trace_id`/`span_id` are added by the formatter's `foreign_pre_chain` **at format time**, from contextvars and the current span. `caplog` formats too late (after the request). So the test attaches, to the `django_service.cache` logger for its duration, a handler using the production `structured` formatter (`build_logging_config(debug=False, log_format="json")["formatters"]["structured"]`) that renders each record on emit, inside the request, and parses the JSON line. `caplog` still counts records.
- **Unit assertions move to a new file.** `tests/unit/test_settings.py` is `core`; the three production values are `feature:redis` and would need region markers inside a core file. They go in `tests/unit/test_cache_degradation_settings.py` (wholly `feature:redis`), reusing `tests.settings_import.evicted_settings_modules` and the same env as `test_production_accepts_a_real_database` (`test_settings.py:489-494`). Task 5's target path is superseded by this.
- `docs/observability.md` is 262 lines (not 180). Add the new section before `## Adding metrics or OTLP logs later` (`:238`); preserve every existing section.
- Coverage task is `test-cov` within `pixi run ci`; ad-hoc pytest needs `pixi run -e dev python -m pytest`.
- Connection to `127.0.0.1:1` may be retried by redis-py's default `Retry`; give the client `SOCKET_CONNECT_TIMEOUT`/`SOCKET_TIMEOUT` of 1 s so a firewalled environment cannot hang the test.

### Architecture Constraints

- **Consistency Conventions → Runtime errors** — "Authentication failure is 401. **Cache failure is swallowed *and* logged, correlated with `request_id` and `trace_id`. Nothing is swallowed silently.**" This is the whole story stated as an invariant; there is no AD, so the convention table is the binding text.
- **Consistency Conventions → Logging** — "Structured, JSON to stdout, carrying `request_id`, `trace_id`, `span_id`… No files, no rotation." The new log event inherits this by routing through the existing `foreign_pre_chain`; do not give it a handler of its own.
- **Consistency Conventions → Rationale** — "Reasoning lives beside the configuration it constrains, in the same file, as `pixi.toml` already does." The two new settings get a comment explaining why `IGNORE_EXCEPTIONS` stays true.
- **Project standard (global)** — never bare `except:`; never `except X: pass` — log or re-raise. `django-redis`'s default is precisely `except X: return fallback` with no log, which is why the default is not acceptable here.
- **AD-24** — the set of region-bearing `core` paths is **open**, declared by the carrier as an open `[[regions]]` array with no count encoded. **`src/config/settings/production.py` is now among them**: `:31-44`, the `CACHES` block, is a declared `feature:redis` region, and so is its `from .base import REDIS_URL` at `:12` — AD-24 records that `CACHES` is not defined in `base.py` at all, so the deployed Redis cache exists only here. That settles the question an earlier revision left open; this story's two new settings belong **inside** that region, which is why they go contiguously beside the block. Also region-bearing and relevant: `base.py:293-294` (`REDIS_URL`/`REDIS_SSL`), `telemetry.py:137` plus its import at `:24` (`:134` and `:136` are `core`; `:134-137` is not one region), and `startup/stage_one.py`. Do **not** achieve feature scoping with a conditional import, a settings-module override, or a `try/except ImportError` — AD-24 forbids all three, everywhere.
- **FR-14** — a conditional refusal scoped to the Redis feature: an in-process cache backend configured where Redis is selected. Owned by Epic 4. Not this story's, and this story must not add a refusal.
- **AD-30** — a `core`-disposed immovable-core assertion suite defends SC-7. FR-48 is in the SC-7 set. Note the tension and resolve it explicitly: the *behaviour* is Redis-feature-scoped (`feature:redis`), so the degradation test carries `feature:redis` disposition under the Consistency Conventions test-location rule and is pruned with the feature in the **two of six** combinations without Redis. The *convention* — nothing swallowed silently — is core. Record which disposition each new test file carries in Completion Notes so Epic 7's carrier entry is unambiguous.
- **AD-20** — 90% coverage including templates; `COVERAGE_CORE=ctrace` from `pixi.toml:150`.
- **Deferred (spine)** — traces only at OpenTelemetry 1.44; do not add a metric for cache failures.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/settings/production.py` | UPDATE | Today: 160 lines. The `CACHES` block at `:31-44` configures `django_redis.cache.RedisCache` at `REDIS_URL` with `CLIENT_CLASS` `django_redis.client.DefaultClient` and `IGNORE_EXCEPTIONS: True` (`:41`), commented "Mimicking memcache behavior" with a link to the django-redis README. This story adds `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True` and `DJANGO_REDIS_LOGGER = "django_service.cache"` adjacent to that block, with the reasoning comment. **Preserve:** `IGNORE_EXCEPTIONS: True`, the `LOCATION` from `REDIS_URL`, the `CLIENT_CLASS`, and the security block that follows at `:46-63`. |
| `src/config/observability/logging.py` | **No change expected** | Today: `shared_processors()` (`:57-71`) supplies `merge_contextvars` and `add_otel_context`; `build_logging_config` (`:138-196`) wires them as the stdlib `foreign_pre_chain` at `:188` and declares a `django_service` logger at `:174`. That is what correlates the django-redis record. Listed so the dev agent confirms rather than adds a logger entry: `django_service.cache` inherits from `django_service` and needs no declaration. If a test shows otherwise, add the child logger — but verify first. |
| `src/config/settings/local.py` | **No change** | Today: `CACHES` at `:21-26` is `django.core.cache.backends.locmem.LocMemCache` — the FR-18 in-process substitution. It cannot raise `ConnectionInterrupted` and has nothing to swallow. Do not add the new settings here. |
| `tests/integration/test_cache_degradation.py` | NEW | The AC #1 and AC #2 end-to-end assertions against a closed loopback port, plus the "unset flag means silence" negative. |
| `tests/unit/test_cache_degradation_settings.py` | NEW | The three production-settings assertions (`feature:redis`; supersedes the `test_settings.py` row). |
| `docs/observability.md` | UPDATE | Today: 180 lines. Adds the cache-degradation subsection. **Preserve** every existing section. |

### Testing Requirements

- `tests/unit/test_settings.py` — unit: reads settings, no I/O.
- `tests/integration/test_cache_degradation.py` — the `@pytest.mark.integration` marker is applied **automatically** by `tests/integration/conftest.py:11-18`; do not add it by hand. Add `pytest.mark.django_db` if the request-driving half touches the ORM.
- Assertions the ACs demand:
  - `cache.get(...)` against an unreachable Redis returns `None` and raises nothing (AC #1);
  - exactly one `ERROR` record on `django_service.cache` for that operation (AC #2);
  - that record, rendered through the configured `structured` formatter, carries `request_id`, `trace_id` and `span_id` (AC #2);
  - with `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS` unset, the same operation logs nothing — the regression this story closes;
  - production settings carry all three values.
- Isolation: everything goes through `override_settings`, so nothing leaks into the rest of the suite. Use a **closed** loopback port, never a real Redis, never `0.0.0.0`. Give the client a short socket timeout if the default makes the test slow — a connection refused on loopback is immediate, but a firewalled port would hang.
- The `otel_tracing`/`spans` fixtures come from `tests/integration/conftest.py` (added by Story 6.1). If Story 6.1 has not landed, create them here and note the ownership swap.
- AD-20 coverage floor: 90% including templates via `pixi run test-cov` (`--cov-fail-under=90`).

#### Project Structure Notes

No layout change; this story stays inside `src/config/settings/` and the mirrored test tree. What to record for Epic 7: the Redis feature's settings extent is split across `src/config/settings/production.py` (the `CACHES` block at `:31-44`, now plus two logging flags, and the `from .base import REDIS_URL` at `:12`) and `src/config/settings/base.py:293-294` (`REDIS_URL`/`REDIS_SSL`, which the Celery block also consumes). AD-24 now declares all of those as region-bearing, so nothing here is unowned — the only thing to carry forward is the `CACHES` block's **new extent** after this story's two settings land, so the carrier's `[[regions]]` entry is declared against the range as it actually stands.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.5] — story statement and both acceptance-criteria blocks.
- [Source: _bmad-output/planning-artifacts/epics.md#FR-48] — "Degradation is visible — swallowed cache failures emit correlated log events."
- [Source: _bmad-output/planning-artifacts/epics.md#FR-14] — the Redis-scoped conditional refusal, owned by Epic 4.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — Runtime errors, Logging, Rationale and Test location rows.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24] — the open, carrier-declared set of region-bearing paths, including `production.py:31-44` plus `:12`, and the forbidden sub-file mechanisms.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-30] — the `core` suite that defends SC-7.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#SC-7] — the immovable core functions in every combination.
- [Source: src/config/settings/production.py:31-44] — the `CACHES` block and `IGNORE_EXCEPTIONS: True` at `:41`.
- [Source: src/config/observability/logging.py:29-71,171-196] — `add_otel_context`, `shared_processors`, the `django_service` logger and the `foreign_pre_chain` wiring.
- [Source: src/config/settings/base.py:175,293-294] — `django_structlog.middlewares.RequestMiddleware` and `REDIS_URL`/`REDIS_SSL`.
- [Source: src/config/settings/local.py:21-26] — the LocMemCache substitution.
- [Source: tests/integration/conftest.py:11-18] — automatic `@pytest.mark.integration` marking.

## Dev Agent Record

### Agent Model Used

Claude Opus 5.5 (claude-opus-5-5)

### Debug Log References

- `pixi run -e dev python -m pytest tests/integration/test_cache_degradation.py` — first run: the request case failed with `RuntimeError: Database access not allowed`. `ATOMIC_REQUESTS` wraps every view in a transaction, so even a view that never queries opens a connection; `pytest.mark.django_db` added to that class only. Then 3 passed.
- Same module, three consecutive runs: 3 passed each (0.26–0.29 s). Module runtime ~0.3 s; the request case's call phase 0.02 s. The refused loopback connection is immediate; redis-py 8.1's default connection `Retry(NoBackoff(), 0)` adds nothing, so no `CONNECTION_POOL_KWARGS` retry tuning was needed. `SOCKET_CONNECT_TIMEOUT`/`SOCKET_TIMEOUT` of 1 s kept as the firewall guard.
- Interference: `test_cache_degradation.py` + `test_log_correlation.py` in both orders (`-p no:randomly`): 6 passed each way.
- `pixi run -e dev python -m pytest tests/unit/test_cache_degradation_settings.py`: 4 passed.
- `pixi run -e dev mypy` over both new test files: clean (one `del settings.X` → `[misc]` fixed with `delattr`). The remaining errors in that run are pre-existing ones in `tests/conftest.py`/`tests/settings_import.py`; the gate's mypy scope is `src/`.
- `pixi run test`: 1256 passed. `pixi run test-integration`: 317 passed, 6 skipped. `pixi run lint`: clean. `pixi run fmt`: no changes. `pixi run docs` (`mkdocs build --strict`): clean.
- `pixi run ci`: exit 0 — 1579 passed, coverage 97.09%.

### Completion Notes List

- Task 1 confirmed against `django_redis` 7.0.0 in `.pixi/envs/dev`: `omit_exception` logs only when `_log_ignored_exceptions`; `self.logger` is built in `__init__` from `DJANGO_REDIS_LOGGER`. AC #1 held, AC #2 did not.
- **Epic 7 — `feature:redis` region in `src/config/settings/production.py`:** the `CACHES` block now spans **`:33-55`** (header comment `:33-34`, `CACHES` dict `:35-46`, rationale comment `:47-53`, `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True` `:54`, `DJANGO_REDIS_LOGGER = "django_service.cache"` `:55`), contiguous, one region. Plus `from .base import REDIS_URL` at **`:14`** (unchanged). The security block now starts at `:57`.
- `IGNORE_EXCEPTIONS: True`, `LOCATION`, `CLIENT_CLASS` and the "Mimicking memcache behavior" comment are preserved; the reasoning for keeping `IGNORE_EXCEPTIONS` and for the logger name sits beside the two new settings.
- `src/config/observability/logging.py` unchanged, as expected: `django_service` is declared, `django_service.cache` inherits its level and propagates to the root `console` handler with the `structured` formatter. Pinned by `test_the_parent_logger_is_declared_so_the_child_inherits_its_level`.
- **Dispositions:** `tests/integration/test_cache_degradation.py` — `feature:redis` (the behaviour exists only where the Redis cache is selected and the module names `django_redis`'s backend; pruned in the two of six combinations without Redis). `tests/unit/test_cache_degradation_settings.py` — `feature:redis` (pins values inside production.py's Redis region; `test_settings.py` is `core`). The *convention* (nothing swallowed silently) remains core per AD-30; the mechanism is feature-scoped. Both docstrings say so.
- The integration test drives a real request through `config.asgi.application` (`drive_asgi`) against a throwaway URLconf built with the existing `tests.conftest.temporary_root_urlconf` helper (rather than overriding `ROOT_URLCONF` to the test module), with `recorded_spans` active. Correlation is read from a handler on `django_service.cache` that renders each record on emit through the production `structured` formatter (`build_logging_config(debug=False, log_format="json")`). Asserts: 200 and the view saw `None`; exactly one ERROR record with `exc_info`; the rendered JSON carries non-empty `request_id`, well-formed non-zero `trace_id`/`span_id`, and the `trace_id` is among the recorded spans.
- `CACHES` and both flags are installed in one `override_settings` call; the negative case overrides `CACHES` and deletes `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS` (asserting it is absent) before the cache is first built, then asserts zero records on `django_service.cache` and on any `django_redis*` logger. The cache built under each override is closed (`caches.close_all()`) before the override exits and Django's handler reset discards it.
- Deviation: the unit module imports production *deployed* (locality variable deleted, stage-1 roster supplied via `tests.settings_import.import_settings`, as `test_payload_properties.py` does) rather than inheriting the dev environment's `COMPONENT_RUNTIME=local` as `test_settings.py:489-494` does. Stricter, and independent of the developer's shell.
- Note: django-redis caches connection pools per URL at class level, so one never-connected pool for `redis://127.0.0.1:1/0` remains in `ConnectionFactory._pools` for the session. It holds no socket and is shared by both cases.
- `docs/observability.md`: new `## Cache degradation is logged` section before `## Adding metrics or OTLP logs later`; every existing section preserved.

### File List

- `src/config/settings/production.py` (UPDATE)
- `tests/integration/test_cache_degradation.py` (NEW)
- `tests/unit/test_cache_degradation_settings.py` (NEW)
- `docs/observability.md` (UPDATE)
- `_bmad-output/implementation-artifacts/6-5-swallowed-cache-failures-become-log-events.md` (UPDATE — tasks ticked, Dev Agent Record)

## Review Triage Log

### 2026-10-09 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 6: (high 0, medium 0, low 6)
- defer: 1: (high 0, medium 1, low 0)
- reject: 13: (high 0, medium 0, low 13)
- addressed_findings:
  - `[low]` `[patch]` The rendered JSON line was not checked for the traceback; it now asserts the `exception` key `dict_tracebacks` adds.
  - `[low]` `[patch]` Only `trace_id` was tied to a recorded span; the `(trace_id, span_id)` pair must now name a recorded span.
  - `[low]` `[patch]` `CACHE_LOGGER.rpartition(".")[0] == PARENT_LOGGER` compared two test constants; removed (the parent relation is asserted against production `LOGGING` in the next test).
  - `[low]` `[patch]` A missing `http.response.start` or missing correlation key raised a bare `StopIteration`/`KeyError`; both now fail with the captured messages/event.
  - `[low]` `[patch]` The negative helper's docstring claimed it ran django-redis's full default while `DJANGO_REDIS_LOGGER` stayed set; it now says the logger setting is never read while the flag is off.
  - `[low]` `[patch]` `docs/observability.md` overclaimed: it now states that degradation is prompt only for a refused connection (no production socket timeout; deferred) and that no `src/` code performs a cache operation today.

## Auto Run Result

Status: `done`

### Summary of implemented change

FR-48. A Redis outage was already swallowed (`IGNORE_EXCEPTIONS: True`) but silently: django-redis logs an ignored `ConnectionInterrupted` only when `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS` is set. Production now sets it, with `DJANGO_REDIS_LOGGER = "django_service.cache"`, contiguous with the `CACHES` block (`feature:redis` region now `production.py:33-55`, plus `:14`). The record is a stdlib `ERROR` with traceback on a child of the configured `django_service` logger, so the existing `foreign_pre_chain` adds `request_id`, `trace_id` and `span_id`. No change to `logging.py`, no wrapper, no new dependency.

### Files changed

- `src/config/settings/production.py` — the two flags plus the reasoning comment.
- `tests/integration/test_cache_degradation.py` (NEW, `feature:redis`) — AC #1 against a closed loopback port; AC #2 through `config.asgi.application` with a test-only URLconf, rendered on emit through the production JSON formatter, ids tied to a recorded span; the flag-unset negative.
- `tests/unit/test_cache_degradation_settings.py` (NEW, `feature:redis`) — pins the three production values and the logger inheritance.
- `docs/observability.md` — new `## Cache degradation is logged` section, including its two limits.
- `_bmad-output/implementation-artifacts/deferred-work.md` — one entry.

### Review findings breakdown

Blind, edge-case and verification-gap reviewers ran in parallel. **6 patches** (all low), **1 deferred** (production sets no Redis socket timeout, so a packet-dropping Redis blocks rather than degrades), **13 rejected**. No intent gaps, no spec repairs; `review_loop_iteration` 0.

### Verification performed

- `pixi run ci` — exit 0 after review patches: **1579 passed, coverage 97.09%**; pre-commit, build, typecheck, lint clean.
- New modules: 7 passed in 0.33 s; repeated and run alongside `test_log_correlation.py` in both orders by the implementer.
- `ruff check`/`format --check` on the new files — clean.
- Ad-hoc `mypy` on test files crashes inside `django-stubs/http/request.pyi:56` (mypy 2.3.0 INTERNAL ERROR), reproduced on the untouched `tests/integration/test_log_correlation.py`; pre-existing and unrelated. The gate's `typecheck` covers `src/` only.
- No PostgreSQL run: no schema change, nothing persisted.

### Residual risks

- Blackholed Redis: no production socket timeout (deferred).
- An operator setting `DJANGO_LOG_LEVEL` above `ERROR` silences these records along with everything else at that level; that is their explicit choice, not a swallow.
- Feature disposition of both new test files is prose only until Epic 7 introduces the carrier.
