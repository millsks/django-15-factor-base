# Story 6.4: The OTLP export path is exercised end to end

Status: ready-for-dev

## Story

As a platform engineer,
I want the export branch tested against a collector stub inside every combination's gate,
so that the one path carrying telemetry off a component is not the one path nothing verifies.

## Acceptance Criteria

**Traceability:** FR-45 · spine Open Item (no AD, needs an owner)

1. **Given** exporter *selection* is comprehensively covered today
   **When** coverage is examined
   **Then** the branch that actually exports is shown to run only when an endpoint is configured, which local development never does

2. **Given** a collector stub
   **When** at least one test runs
   **Then** it drives a batch span processor against an OTLP exporter end to end
   **And** exercises serialization, transport and batch behaviour

3. **Given** this test
   **When** the gate runs
   **Then** it runs inside every combination's gate

4. **Given** this is an open item with no architectural decision
   **When** the story is picked up
   **Then** an owner is named and the collector stub's shape is decided as part of it

## Tasks / Subtasks

- [ ] Task 1 — Name the owner and record the stub decision before writing the stub (AC: #4)
  - [ ] **This story may not invent an owner.** The spine lists this as an Open Item: "FR-45 — the OTLP export path end-to-end test against a collector stub, inside every combination's gate. No AD; needs an owner and a stub design." Obtain the owner from the human running the work. If none is supplied, stop, record the blocked state in Completion Notes, and escalate — do not name a placeholder, a team-shaped guess, or "the platform group" by inference.
  - [ ] Once named, record the owner and the stub decision in a new `## OTLP export verification` section of `docs/observability.md`, stating: the owner, the stub's shape (below), what the test proves, what it deliberately does not prove, and the date.
  - [ ] Note for the caller: the spine's Open Items entry at `ARCHITECTURE-SPINE.md:501` should be updated to name the owner once decided. Editing a planning artifact is a separate, deliberate act — flag it rather than doing it silently as part of an implementation commit.

- [ ] Task 2 — Show the gap rather than assert it (AC: #1)
  - [ ] Read `src/config/observability/telemetry.py:124-128`. The `BatchSpanProcessor(OTLPSpanExporter())` line at `:126` executes only when `resolve_traces_exporter()` returns `OTLP`, which — absent an explicit `OTEL_TRACES_EXPORTER` — requires `_has_otlp_endpoint()` (`:55-65`) to be true.
  - [ ] Read `tests/unit/test_telemetry.py:62-159`. Selection is covered thoroughly; `tests/unit/test_telemetry.py:43-58`'s `no_side_effects` fixture and the `add_span_processor` monkeypatching at `:131-159` mean **no test ever constructs a real `OTLPSpanExporter` or sends a byte**. No local pixi task sets either endpoint variable (`pixi.toml:172-206`), and neither does `[activation.env]` (`pixi.toml:145-150`) — so local development never configures one.
  - [ ] Write this up as the docstring of the new test module, citing the exact lines. AC #1 is a statement about what the suite proves; the artifact that discharges it is the recorded reasoning, not a passing assertion.

- [ ] Task 3 — Build the collector stub (AC: #2, #4)
  - [ ] Create `tests/integration/otlp_collector.py`. It is a helper module, not a test module: pytest's `python_files` (`pyproject.toml:151-153`) collects only `test_*.py` and `tests.py`, so this name is not collected, and `[tool.coverage.run] omit` (`pyproject.toml:162-169`) already excludes `*/tests/*` from measurement. `tests/integration/__init__.py` exists, so `tests.integration.otlp_collector` is importable (`pythonpath = ["src", "."]`, `pyproject.toml:149`).
  - [ ] **Stub shape — decide and record:** an in-process `http.server.ThreadingHTTPServer` bound to `127.0.0.1:0` (ephemeral port), served on a daemon thread, with a handler that accepts `POST /v1/traces`, reads `Content-Length` bytes, transparently gunzips when `Content-Encoding: gzip`, appends the raw body to a list, and replies `200` with an empty `ExportTraceServiceResponse`. Expose it as a context manager yielding an object carrying `.endpoint` (the `http://127.0.0.1:<port>` base URL) and `.requests` (the captured bodies).
  - [ ] Reasoning to record with the decision: the pinned exporter is `opentelemetry-exporter-otlp-proto-http` (`pixi.toml:60`), which POSTs protobuf to `{endpoint}/v1/traces` over HTTP — so an HTTP stub exercises the real transport with no container, no network beyond loopback, and no dependency the six pre-locked environments do not already have. A gRPC stub would need `opentelemetry-exporter-otlp-proto-grpc`, which is not declared and must not be added. A real `otel/opentelemetry-collector` container would put a service dependency inside a gate whose whole premise (SC-4, CG-4) is that nothing external runs.
  - [ ] Decode the captured body with `opentelemetry.proto.collector.trace.v1.trace_service_pb2.ExportTraceServiceRequest` — the proto package arrives with the pinned exporter, so decoding is what proves *serialization* rather than merely that bytes arrived.
  - [ ] The stub must bind to `127.0.0.1` only, never `0.0.0.0`, and must shut down and join its thread on context exit so the test leaves resources as it found them.

- [ ] Task 4 — Drive the export path end to end (AC: #2)
  - [ ] Create `tests/integration/test_otlp_export.py`. Inside the stub's context: set `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` to `f"{stub.endpoint}/v1/traces"` with `monkeypatch.setenv`, build a `TracerProvider`, attach `BatchSpanProcessor(OTLPSpanExporter())`, start and end one span with a known name and one known attribute, then call `provider.force_flush(timeout_millis=...)`.
  - [ ] Assert **serialization**: the decoded `ExportTraceServiceRequest` contains one resource span whose scope span carries the known span name and attribute.
  - [ ] Assert **transport**: the stub received exactly one `POST` to `/v1/traces`, and its `Content-Type` is `application/x-protobuf`.
  - [ ] Assert **batch behaviour**: emit N spans (N ≥ 2) with a `BatchSpanProcessor` configured with a `max_export_batch_size` smaller than N, and assert the stub received more than one request and that the union of decoded spans across requests equals the N emitted. This is the clause the story exists for — a single-span flush proves the exporter works but proves nothing about batching.
  - [ ] Do **not** call `config.observability.telemetry.configure_telemetry()` in this test. It sets a process-wide tracer provider and instruments Django, Celery, psycopg and redis for the remainder of the session, and `trace.set_tracer_provider` is one-shot per process. Build a local `TracerProvider` and never call `trace.set_tracer_provider`. The test asserts the *export path*; Story 6.3 asserts that `configure_telemetry` selects it.
  - [ ] Give the flush an explicit finite timeout and assert `force_flush` returned `True`, so a stub that never responds fails the test rather than hanging the gate.

- [ ] Task 5 — Make the test a member of the unprunable core suite (AC: #3)
  - [ ] Both new files carry the `core` disposition under the Consistency Conventions test-location rule and must never be pruned by a feature. Neither may import a feature-owned module at module level: the OpenTelemetry API, SDK and the OTLP HTTP exporter are all unconditional `[dependencies]` (`pixi.toml:58-60`), so this holds by construction — assert it in `tests/unit/test_dependency_policy.py` if Story 6.2's placement test has not already.
  - [ ] Do **not** guard the test with `pytest.importorskip` or any conditional skip. FR-28 forbids anything present-but-skipped, and a skipped export test is exactly the "one path nothing verifies" this story exists to close.
  - [ ] **Traceability marker, not an acceptance condition for this story:** "runs inside every combination's gate" completes in Epic 8, which builds the six-combination harness (`tools/harness/`, `machinery`) and the `core`-disposed suite that runs inside each gate (AD-30). Here the obligation is discharged by making the test unconditional and `core`-disposed so Epic 8 has nothing to special-case. Record that split in Completion Notes.

- [ ] Task 6 — Run the gate (AC: #1, #2, #3, #4)
  - [ ] `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **Spine → Open Items** — "FR-45 — the OTLP export path end-to-end test against a collector stub, inside every combination's gate. **No AD; needs an owner and a stub design.**" There is no architectural decision to conform to. The stub design in Task 3 is a *proposal this story must get ratified by the named owner*, not a decision already made. If the owner chooses differently, the ACs still stand and the tasks change.
- **AD-30** — "a `core`-disposed immovable-core assertion suite runs inside every combination's gate and is never pruned by any feature. AD-20's coverage signal defends SC-2; **this suite is what defends SC-7, and nothing else does.**" This test belongs to that suite.
- **Consistency Conventions → Test location** — "Accelerator and base tests live under `tests/`, mirroring `src/`, and carry the disposition of what they cover — a feature's tests are `feature:<name>` and are pruned with it, except the immovable-core assertion suite (AD-30), which is `core`."
- **FR-28** — "Excluded features leave nothing behind — no dependency, template, static asset, settings fragment, or test, and nothing present-but-skipped." No conditional skip on this test.
- **AD-24** — `src/config/observability/telemetry.py` is a region-bearing `core` path, and the set of such paths is **open and carrier-declared**. **`:134-137` is not one region:** `:134` `DjangoInstrumentor` and `:136` `PsycopgInstrumentor` are **`core`**; only `:135` `CeleryInstrumentor` and `:137` `RedisInstrumentor` are feature-owned, each as a single-line region carrying its import at `:21` and `:24` respectively. This story is not expected to modify `telemetry.py` at all. If it does, it must leave `:21-24` and `:134-137` one import and one call per line. Forbidden anywhere in that file: conditional imports, settings-module inheritance, `try/except ImportError`.
- **Consistency Conventions → Supply chain** — "conda-forge only; `[pypi-dependencies]` carries the editable self-install and nothing else." The stub must be built from the standard library plus packages already declared in `pixi.toml`. Do not add `httpx`, `requests-mock`, `responses`, `pytest-httpserver`, `grpcio`, or `opentelemetry-exporter-otlp-proto-grpc`. `tests/unit/test_dependency_policy.py` fails on an undeclared exception.
- **CG-4 / SC-4** — the gate runs with no external service. A collector container is not an option.
- **AD-20** — 90% coverage including templates; `COVERAGE_CORE=ctrace` from `pixi.toml:150`.
- **Deferred (spine)** — metrics and the OTLP logs signal are deferred. Export exactly one signal: traces.
- **Project standards** — never `print()`; never stdlib `logging` in project code. The stub's `BaseHTTPRequestHandler` writes to stderr by default via `log_message` — override it to a no-op rather than letting it print, or the gate output fills with request lines.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `tests/integration/otlp_collector.py` | NEW | The collector stub: a loopback-bound `ThreadingHTTPServer` accepting `POST /v1/traces`, capturing request bodies (gunzipping when needed), exposed as a context manager with `.endpoint` and `.requests`. Not collected by pytest (`python_files` is `test_*.py`/`tests.py`), not measured by coverage (`*/tests/*` omitted). |
| `tests/integration/test_otlp_export.py` | NEW | The end-to-end assertions: serialization (decoded protobuf carries the span), transport (one `POST` to `/v1/traces`, `application/x-protobuf`), and batch behaviour (N spans over a smaller batch size arrive across multiple requests with no loss). Module docstring carries the AC #1 write-up. |
| `docs/observability.md` | UPDATE | Today: 180 lines; "Why export is conditional" at `:51-66`, "Seeing it work" at `:67-89`. Adds an `## OTLP export verification` section naming the owner, the stub shape and the decision date. **Preserve** every existing section. |
| `src/config/observability/telemetry.py` | **No change expected** | Today: `configure_telemetry` (`:104-140`) attaches `BatchSpanProcessor(OTLPSpanExporter())` at `:126` when `resolve_traces_exporter()` returns `OTLP`. Listed so the dev agent reads it and confirms the branch under test, not to edit it. |
| `tests/unit/test_dependency_policy.py` | UPDATE (only if Story 6.2 has not landed) | Asserts `opentelemetry-exporter-otlp-proto-http` is in the unconditional `[dependencies]` table, so the export test can never be pruned by a feature selection. |

### Testing Requirements

- Both new files live under `tests/integration/`; the `@pytest.mark.integration` marker is applied **automatically** by `tests/integration/conftest.py:11-18` — do not add it by hand.
- These are integration tests by the project's own definition: real transport over a real socket, no mocking of the exporter, no mocking of the HTTP layer. Mocking any of it would reproduce exactly the coverage illusion AC #1 describes.
- No database access — do not add `pytest.mark.django_db`. Nothing here touches the ORM or Django settings.
- Isolation: use `monkeypatch.setenv` for the endpoint variables so they are unset on teardown; shut the server down and join the thread on context exit; never call `trace.set_tracer_provider`; call `provider.shutdown()` after the assertions. Each test must leave resources as it found them.
- Determinism: bind to port `0` and read the assigned port from the socket, never a hardcoded port — a fixed port makes the test fail when the gate runs two combinations concurrently.
- Timeouts: every flush and every socket operation gets a finite timeout. A hung gate is worse than a failing one.
- AD-20 coverage floor: 90% including templates via `pixi run test-cov` (`--cov-fail-under=90`).

#### Project Structure Notes

The Structural Seed shows only `tests/` without internal detail, so `tests/integration/otlp_collector.py` as a non-collected helper beside the test that uses it is consistent with the seed and with the existing `tests/factories.py` precedent at the `tests/` root. One relevant variance: the seed lists `tools/materializer/` and `tools/harness/` (the six-combination verification runner) as machinery and neither exists yet — the six-combination gate that AC #3 refers to is Epic 8's, so nothing in this story can execute the test six times. The property this story delivers is that the test is unconditional and `core`, which is what makes Epic 8's "run it in every gate" a no-op rather than a port.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.4] — story statement and all four acceptance-criteria blocks.
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6] — "Owns two of the three ownerless open items — FR-45's collector stub design and NFR-6's telemetry-overhead measurement."
- [Source: _bmad-output/planning-artifacts/epics.md#FR-45] — the export path exercised end to end in the gate against a collector stub.
- [Source: _bmad-output/planning-artifacts/epics.md#FR-28] — nothing present-but-skipped.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Open Items] — "FR-45 — the OTLP export path end-to-end test… No AD; needs an owner and a stub design."
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-30] — the `core`-disposed unprunable suite that defends SC-7.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24] — the `telemetry.py:135`/`:137`-plus-imports-`:21`/`:24` regions, with `:134` and `:136` `core`, and the forbidden mechanisms.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — Test location and Supply chain rows.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Deferred] — traces only; metrics and OTLP logs deferred.
- [Source: src/config/observability/telemetry.py:55-65,104-140] — `_has_otlp_endpoint` and the `BatchSpanProcessor(OTLPSpanExporter())` branch at `:126`.
- [Source: tests/unit/test_telemetry.py:43-58,131-159] — the `no_side_effects` fixture and the `add_span_processor` monkeypatching that keep every existing test off the wire.
- [Source: pixi.toml:58-60,145-150,172-206] — the OTLP exporter dependency; `[activation.env]` carrying only `COVERAGE_CORE`; no task setting an OTLP endpoint.
- [Source: pyproject.toml:149-153,162-169] — `pythonpath`, `python_files`, and the coverage `omit` list excluding `*/tests/*`.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
