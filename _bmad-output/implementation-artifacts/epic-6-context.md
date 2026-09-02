# Epic 6 Context: Telemetry that leaves the component, and degradation that is visible

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

An operator must be able to follow one request across services built by teams that never coordinated, and must see a degrading cache as log events rather than as silence. Observability is the one capability a developer cannot accidentally work without, because it is not substituted locally at all — the same code runs, only the terminal export step is absent. Most of this is already satisfied in the reference application, so the epic is largely about stating what must not regress and locking it behind tests, plus adding the one path that is verified nowhere: the OTLP export branch, which runs only when a collector endpoint is configured and local development never configures one. The epic also owns two of the three ownerless open items in the plan — the collector-stub design for the export test, and the telemetry-overhead measurement — each of which must have an owner named as part of the story that carries it.

## Stories

- Story 6.1: Correlated structured logging holds in every combination
- Story 6.2: ASGI requests produce spans
- Story 6.3: Trace export is environmental and drops rather than retries
- Story 6.4: The OTLP export path is exercised end to end
- Story 6.5: Swallowed cache failures become log events
- Story 6.6: Telemetry overhead is measured once and recorded

## Requirements & Constraints

- **Logging is a JSON event stream to stdout.** The component never manages log files or rotation. Log lines emitted during a request carry the request correlation ID, trace ID and span ID, and this holds in all six combinations.
- **Correlation propagates into task execution** wherever background task processing is selected — and the task-side correlation wiring exists only where that feature is selected, never unconditionally.
- **Every authorization change emits a structured event** correlated with the request and trace identifiers.
- **ASGI requests produce spans in every combination.** The ASGI instrumentor is present and active in all six; without it, requests served the only way they are served produce no spans at all. A test must assert spans are actually produced for a request served over ASGI.
- **Export is environmental and drops rather than retries.** Export attaches only when the OTLP endpoint or its traces-specific variant is set. With neither set, no span processor is attached and spans end without export — no batch processor may be attached to an exporter pointed at an unreachable default endpoint.
- **The export branch itself must be exercised.** At least one test drives a batch span processor against an OTLP exporter end to end — serialization, transport and batch behaviour — against a collector stub, and that test runs inside every combination's gate. Comprehensive coverage of exporter *selection* does not satisfy this.
- **Cache failures are swallowed and logged.** Exceptions continue to be ignored so a cache outage degrades the component rather than stopping it; every swallowed failure emits a log event correlated with the request and trace identifiers. Nothing is swallowed silently.
- **Instrumentation is always on** and is never conditionally disabled to gain performance. Its overhead is measured once against the reference application with export disabled, recorded alongside the observability documentation, and re-measured only when the instrumentation set changes — never otherwise.
- **The success criterion this epic serves** is that the immovable core functions in every combination: each materialized combination emits correlated structured logs carrying request and trace identifiers and produces spans for ASGI requests. Nothing here may be narrowed to a subset of combinations.

## Technical Decisions

- **Observability is a cross-cutting concern under the composition root** — it has several independent consumers and no natural owner, so it lives in the configuration package's observability module rather than in any application.
- **Traces only.** Metrics and the OTLP logs signal are explicitly deferred; do not add either as part of this epic.
- **Conditional instrumentors are feature-owned regions, not runtime flags.** The Celery and Redis instrumentor calls in the telemetry module are feature-owned and pruned with their features; the Django and psycopg instrumentor calls beside them are immovable core and must survive in every combination. A region covering an instrumentor call must also cover its import — pruning the call alone relocates the import error rather than fixing it. Declare regions with the paired line-comment marker mechanism the feature-model epic specifies; no other sub-file removal mechanism is permitted (no conditional imports, no settings-module inheritance, no `try/except ImportError`).
- **Two live defects in the reference application belong to this epic and are deliberately unfixed until their stories land:** cache failures are currently swallowed silently, and the OTLP exporter currently attaches to an unconfigured default endpoint. Fix each with the test its story specifies rather than as a drive-by.
- **A refusal already guards the disable switch.** A deployed component that disables the telemetry SDK is refused at settings import by the refusal contract — this epic does not re-implement that, and must not offer any alternative way to turn instrumentation off.
- **Combination arithmetic matters when scoping "every combination".** Three valid cache/background-task pairings times two object-storage states gives six; the Redis cache is present in four of the six and background task processing in only two. Anything asserted "in every combination" must not depend on a feature present in a subset.
- **Standard project conventions apply:** configuration reads component-prefixed environment variables, never a `DJANGO_ENV` or bare `ENV`; dependencies resolve from the approved channel only; the coverage floor including templates is unchanged; tests carry the disposition of what they cover, so a feature's telemetry tests are pruned with that feature while core telemetry tests are not.
- **Both open items require a named owner as an acceptance condition.** The collector stub's shape is a decision to be made and recorded inside its story; the overhead measurement needs both an owner and a milestone. Neither has an architectural decision behind it, so do not assume one exists.

## Cross-Story Dependencies

- **Within the epic:** the environmental-export behaviour (6.3) defines when a processor and exporter are attached at all, and the end-to-end export test (6.4) exercises that same branch — 6.3 lands first. The correlation identifiers established by 6.1 are what the cache-failure log events (6.5) must carry.
- **On earlier epics:** the gate and its combination matrix come from the first epic; 6.1's assertion that authorization changes emit correlated events depends on the mapper built in the authentication epic. Beyond those, this epic may run in parallel with the local-development, refusal-contract and deployment-interface epics.
- **On later epics:** the feature-owned region markers used for the conditional instrumentors are formalized by the feature-extraction epic — declare them in the shape that epic specifies rather than inventing a local mechanism. The unprunable immovable-core assertion suite that runs inside every combination's gate is built by the materializer epic; the per-combination guarantees stated here are what that suite is defending, so write them so they can be lifted into it.
