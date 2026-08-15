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

- [ ] Task 1 — Confirm the gap before changing anything (AC: #1, #2)
  - [ ] Read `src/config/settings/production.py:31-44`. `CACHES["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True` is set at `:41` with the comment "Mimicking memcache behavior". Nothing sets `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS`, anywhere in the repository.
  - [ ] Read the installed `django_redis.cache.omit_exception` decorator: it catches `ConnectionInterrupted`, and when `self._ignore_exceptions` is true it calls `self.logger.exception("Exception ignored")` **only if** `self._log_ignored_exceptions` is true; otherwise it returns the fallback value and logs nothing. `self.logger` is `None` unless that flag is set. Both flags and the logger name are read from settings in `RedisCache.__init__` — `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS` (default `False`) and `DJANGO_REDIS_LOGGER` (default the module name).
  - [ ] Conclusion to carry into the change: AC #1 already holds; **AC #2 does not**. Today a Redis outage is swallowed silently, which contradicts the project's own standard forbidding `except X: pass` and the spine's Runtime errors convention.

- [ ] Task 2 — Turn the swallowed failure into a logged event (AC: #1, #2)
  - [ ] In `src/config/settings/production.py`, immediately beside the `CACHES` block at `:33-44`, add `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True` and `DJANGO_REDIS_LOGGER = "django_service.cache"`.
  - [ ] **Keep `IGNORE_EXCEPTIONS: True`.** AC #1 requires the exception to continue being ignored; removing it would turn a cache outage into an outage, which is the opposite of what this story asks for. State that in the comment beside the new settings, with the reasoning, per the spine's Rationale convention ("Reasoning lives beside the configuration it constrains, in the same file").
  - [ ] Choose `django_service.cache` as the logger name deliberately: `build_logging_config` (`src/config/observability/logging.py:171-176`) already declares a `django_service` logger at the configured level, and `django_service.cache` inherits from it, so the event is levelled with the rest of the component's own output rather than with a third-party default. `logger.exception(...)` emits at `ERROR`, above the `INFO` root level set at `logging.py:194`.
  - [ ] Place the two new settings **adjacent to the `CACHES` block**, contiguously, so they fall inside the `feature:redis` region AD-24 already declares over `production.py:31-44`. That declared range is the block as it stands today; adding two settings extends it, so record the block's new extent in Completion Notes for Epic 7. Do not scatter them, and do not open a second region.

- [ ] Task 3 — Verify the correlation comes for free, and prove it (AC: #2)
  - [ ] `django-redis` logs through the standard library, not structlog. That is fine and is the intended path: `build_logging_config` routes every stdlib record through `structlog.stdlib.ProcessorFormatter` with `foreign_pre_chain=shared_processors()` (`src/config/observability/logging.py:183-189`), and `shared_processors()` (`:57-71`) contains `structlog.contextvars.merge_contextvars` — which supplies `request_id` bound by `django_structlog.middlewares.RequestMiddleware` (`src/config/settings/base.py:175`) — and `add_otel_context` (`:29-54`) — which supplies `trace_id` and `span_id` from the active span. The comment at `logging.py:185-188` already records this design.
  - [ ] Do **not** add a custom cache wrapper, a subclass of `RedisCache`, or a monkeypatch to emit the log line. The correlation works through the configured pipeline; introducing a wrapper adds a `core`/feature boundary problem for Epic 7 and a second place the behaviour can drift.
  - [ ] Add `tests/integration/test_cache_degradation.py` proving all of it end to end (Task 4).

- [ ] Task 4 — Test the degraded path against a cache that cannot connect (AC: #1, #2)
  - [ ] Use `django.test.override_settings` to install, for the test only: a `CACHES["default"]` of `django_redis.cache.RedisCache` pointed at a closed loopback port (for example `redis://127.0.0.1:1/0`) with `OPTIONS = {"CLIENT_CLASS": "django_redis.client.DefaultClient", "IGNORE_EXCEPTIONS": True}`, plus `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True` and `DJANGO_REDIS_LOGGER = "django_service.cache"`.
  - [ ] Override `CACHES` **in the same `override_settings` call** as the two flags. Django clears its cache handlers on a `CACHES` `setting_changed` signal but not on the two `DJANGO_REDIS_*` ones, and both flags are read in `RedisCache.__init__` — so without the `CACHES` override in the same call the cache object is never rebuilt and the flags have no effect. This is the single most likely way this test silently passes for the wrong reason.
  - [ ] Assert AC #1: `django.core.cache.cache.get("anything")` returns `None` and raises nothing.
  - [ ] Assert AC #2: with `caplog.at_level(logging.ERROR, logger="django_service.cache")`, exactly one record is captured; formatting it through the configured `structured` formatter yields an event carrying `request_id`, `trace_id` and `span_id`. Perform the cache call **inside a request** (drive `client.get(reverse("account_login"))` — a `core` route in every combination, since AD-29 deletes `home` and `about` — against a view or middleware that touches the cache, or bind the contextvars the middleware binds) with the `otel_tracing`/`spans` fixtures from `tests/integration/conftest.py` active so a span is genuinely recording — `add_otel_context` (`logging.py:50-53`) adds nothing when no span is recording, so without an active span the `trace_id` assertion would fail for a reason unrelated to this story.
  - [ ] Assert the negative that names the story: with `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS` **unset**, the same operation still returns `None` and captures **zero** records — this is the regression the two new settings prevent, and it is worth pinning so a later settings tidy-up cannot silently restore silence.
  - [ ] Do not require a running Redis. A closed port is what produces `ConnectionInterrupted`; that is the entire mechanism under test.

- [ ] Task 5 — Pin the production settings (AC: #1, #2)
  - [ ] Add unit assertions in `tests/unit/test_settings.py` over the production settings module: `CACHES["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] is True`, `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS is True`, and `DJANGO_REDIS_LOGGER == "django_service.cache"`. All three together are the requirement; any one alone is not.

- [ ] Task 6 — Document it (AC: #2)
  - [ ] Add a short subsection to `docs/observability.md` stating that a Redis outage degrades rather than stops the component, that every ignored failure is logged at `ERROR` on `django_service.cache` correlated with `request_id`/`trace_id`, and that nothing is swallowed silently. Cross-reference the project standard forbidding `except X: pass`.

- [ ] Task 7 — Run the gate (AC: #1, #2)
  - [ ] `pixi run test`, then `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

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
| `tests/unit/test_settings.py` | UPDATE | Adds the three production-settings assertions. |
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

### Debug Log References

### Completion Notes List

### File List
