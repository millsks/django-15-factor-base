# Epic 6 Context: Telemetry that leaves the component, and degradation that is visible

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

An operator must be able to follow one request across services built by teams that never coordinated, and must see a degrading cache as log events rather than as silence. Observability is the one capability a developer cannot accidentally work without, because it is never substituted locally: the same code runs, and only the terminal export step is absent. Most of this already holds in the reference application, so the epic mainly states what must not regress and locks it behind tests. It also adds the one path nothing verifies today, the OTLP export branch, which runs only when a collector endpoint is configured, and local development never configures one. The epic owns two open items, both now decided: the export end-to-end test, with a named owner and stub design, and the telemetry-overhead measurement, with a named owner and milestone.

## Stories

- Story 6.1: Correlated structured logging holds in every combination
- Story 6.2: ASGI requests produce spans
- Story 6.3: Trace export is environmental and drops rather than retries
- Story 6.4: The OTLP export path is exercised end to end
- Story 6.5: Swallowed cache failures become log events
- Story 6.6: Telemetry overhead is measured once and recorded

## Requirements & Constraints

- **Logging is a JSON event stream to stdout.** The component never manages log files or rotation. Every log line emitted during a request carries `request_id`, `trace_id` and `span_id`, in all six combinations.
- **Correlation propagates into task execution** wherever background task processing is selected. The task-side correlation wiring exists only where that feature is selected, never unconditionally.
- **Every authorization change emits a structured event** correlated with `request_id` and `trace_id`.
- **ASGI requests produce spans in every combination.** The ASGI instrumentor is present and active in all six. Without it, requests served the only way they are served produce no spans at all. A test must assert that a request served over ASGI actually produces spans.
- **Export is environmental and drops rather than retries.** Export is attached only when the OTLP endpoint or its traces-specific variant is set. With neither set, no span processor is attached and spans end without export, discarded at the processor rather than failing at the socket. No batch processor may be attached to an exporter pointed at an unreachable default endpoint. Setting the console exporter explicitly still shows spans on stdout locally.
- **The export branch itself must be exercised.** At least one test drives a batch span processor against an OTLP exporter end to end, covering serialization, transport and batch behaviour, against a collector stub. That test runs inside every combination's gate. Thorough coverage of exporter *selection* does not satisfy this.
- **Cache failures are swallowed and logged.** Exceptions are still ignored, so a cache outage degrades the component rather than stopping it. Every swallowed failure emits a log event correlated with `request_id` and `trace_id`. Nothing is swallowed silently.
- **Instrumentation is always on.** It is never conditionally disabled to gain performance. Its overhead, with export disabled, is measured once against the reference application and recorded alongside the observability documentation. It is re-measured only when the instrumentation set changes.
- **Success criterion served:** the immovable core works in every combination. Each materialized combination emits correlated structured logs and produces ASGI spans. Nothing here may be narrowed to a subset of combinations.

## Technical Decisions

- **Observability is a cross-cutting concern under the composition root.** It has several independent consumers and no natural owner, so it lives in the configuration package's `observability/` module, not in any application.
- **Traces only.** OpenTelemetry API/SDK 1.44, with structlog and django-structlog for logging. Metrics and the OTLP logs signal are deferred; do not add either.
- **Collector stub design for the export test (decided, owner: platform engineering).** The stub is a standard-library `http.server` loopback server that receives the real `opentelemetry-exporter-otlp-proto-http` POST at `/v1/traces`. There is no container and no new dependency. Story 6.4 delivers it. Because the stub needs no external service, the test can run in every combination's gate.
- **Overhead measurement ownership (decided, owner: platform engineering; milestone: before the v0.2.0 release).** Story 6.6 delivers it. Only the owner and milestone are decided. No architectural decision covers the method, so do not assume one exists.
- **Conditional instrumentors are feature-owned regions, not runtime flags.** In the telemetry module, the Celery and Redis instrumentor calls are feature-owned and pruned with their features. The Django and psycopg calls beside them are immovable core and must survive in every combination. Mark these as separate single-line regions, never as one range: a single range would strip core instrumentation everywhere. A region covering a call must also cover its import, because pruning the call alone only moves the import error. Use only the paired line-comment marker mechanism. Conditional imports, settings-module inheritance and `try/except ImportError` are forbidden.
- **Known defects land with their story's tests, never as drive-by fixes.** Silently swallowed cache failures belong to 6.5. The OTLP exporter attaching to an unconfigured default endpoint belongs to 6.3. The telemetry module reading the forbidden `DJANGO_ENV` belongs to Story 3.6, not to this epic.
- **The disable switch is already guarded.** If a deployed component disables the telemetry SDK, the refusal contract refuses it at settings import. Do not re-implement that check or offer any other way to turn instrumentation off.
- **Combination arithmetic.** The six valid combinations are no-Celery × {no Redis, Redis} × {no storage, storage}, plus Celery-with-Redis × {no storage, storage}. Redis is present in four of the six and Celery in two. Nothing asserted "in every combination" may depend on a feature that is present in only some of them.
- **Conventions:** configuration reads `COMPONENT_`-prefixed environment variables, never `DJANGO_ENV` or a bare `ENV`. Dependencies come from conda-forge only, and any package imported directly is declared directly. Tests carry the disposition of what they cover, so a feature's telemetry tests are pruned with that feature and core telemetry tests are not.

## Cross-Story Dependencies

- **Within the epic:** 6.3 decides when a processor and exporter are attached at all, and 6.4 exercises that same branch, so 6.3 lands first. The correlation identifiers established by 6.1 are what 6.5's cache-failure log events must carry.
- **On earlier epics:** the gate and its combination matrix come from Epic 1. 6.1's assertion about authorization-change events depends on the mapper built in Epic 2. The SDK-disable refusal comes from Epic 4.
- **On later epics:** the feature-extraction epic (Epic 7) formalizes the feature-owned region markers. Declare regions in the shape it specifies. The materializer epic (Epic 8) builds the unprunable immovable-core assertion suite that runs in every combination's gate. Write the per-combination guarantees here so they can be lifted into that suite.
