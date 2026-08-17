# Epic 3 Context: Clone and run — a component that works with nothing installed

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

A developer clones a generated component onto a machine with nothing installed and it serves: they sign in as a staff persona, switch to a read-only persona and watch the same page refuse them, mint a development token and call the API — with no database, cache, broker, object store, or identity provider running. This epic delivers four of the five local substitutions (sqlite, in-process cache, eager tasks, local personas; filesystem-backed object storage arrives with the storage feature in Epic 7), the persona seeding that reuses Epic 2's group provisioning, and a locally signed JWT the real Bearer authentication class genuinely verifies. It also establishes the locality declaration that Epic 4's refusal contract enforces against. It matters because the alternative — standing up four backing services before changing a line of business logic — is the friction the product exists to remove, and because parity with deployed behaviour is what keeps local convenience honest.

## Stories

- Story 3.1: Local pixi tasks declare themselves local
- Story 3.2: The database, cache and task substitutions hold locally
- Story 3.3: Personas are seeded from declared claims
- Story 3.4: Local sign-in is a URL route that drives the real mapper
- Story 3.5: The local programmatic flow validates for real
- Story 3.6: Observability is not substituted locally
- Story 3.7: Nothing on the local start path reaches the network at boot

## Requirements & Constraints

- A component must run locally with nothing installed. With no `DATABASE_URL`/`POSTGRES_DB`, sqlite is selected and the ORM, migrations and full suite are preserved; with no cache service, an in-process backend is configured and every cache call site keeps working; with no broker, task execution is eager, synchronous and propagating. Every valid combination — including the ones that select background task processing — runs locally with no broker. The broker constraint is a statement about deployment only, and the documentation must say so.
- Local identities are declared as configuration and materialized by a development task. Each persona declares its groups, its profile fields, and the identity-key claim the mapper resolves by. At least two personas exist with different group memberships, one carrying the designated staff group. Re-authenticating a persona whose declared groups changed produces the corresponding membership change, including removal; signing in twice resolves to the same user.
- The seeding task refuses to run in a deployed environment, raising the same `ImproperlyConfigured` the refusal contract uses, and never creates a local account there.
- Local sign-in constructs a synthetic claims payload and passes it to the same mapper the IdP flows use; the mapper must be unaware which path produced the claims. A staff persona and a read-only persona reaching the same admin page must diverge because of the mapper, never because of a local-only branch.
- The local programmatic flow must validate for real: a development task mints a JWT signed by a locally generated keypair, local settings point the JWKS location at that key, and the real Bearer authentication class verifies signature, `iss`, `aud` and `exp` with nothing stubbed or skipped. Tampered and expired tokens are rejected.
- Secrets never live in source. The development keypair is generated on demand into a gitignored path and is never committed — a key committed to a template ships inside every component generated from it.
- Observability is not substituted. With no OTLP endpoint, the tracer provider still installs, instrumentors still instrument, spans are still created and ended, `trace_id`/`span_id` still reach every log line, and spans are discarded at the processor. `OTEL_TRACES_EXPORTER=console` writes spans to stdout and changes nothing else. No batch processor may be attached to an exporter pointed at an unreachable endpoint, so no retry cycle floods stderr through a test run.
- Nothing on the local start path reaches the network at boot: settings import and Django setup perform no OIDC discovery, and JWKS retrieval is triggered only by the first Bearer request that needs it. Persona seeding is a database write and keypair generation is computation; neither reaches a registry, the IdP, or a package index. The claim is scoped to begin once the environment exists — environment installation downloads packages by definition.
- Substitution is permitted only where the deployed dependency genuinely cannot be present on a developer's machine; each substitution widens the parity gap and each must be guarded by a refusal. Local development is knowingly a weaker proof than running it suggests.

## Technical Decisions

- **Locality is declared by the development environment, not by a file in the source tree and not per task.** `COMPONENT_RUNTIME = "local"` is declared exactly once, in the dev feature's activation env; every developer path runs in that environment and inherits it. The default environment declares nothing and therefore reads *deployed* — which is what the golden base runs and what the release stage invokes for migration and static-file collection. Serving-process tasks set no runtime and each sets `COMPONENT_PROCESS` in its own task env. No `COMPONENT_*` variable may appear in the default environment's resolved activation env, `COMPONENT_PROCESS` may not appear in any activation env, and no production-bound environment may include the dev feature; a gate test asserts all three over the materialized `pixi.toml`. Locality fails closed (absent or unrecognized means deployed); process type fails open. Note that the epics file still describes the earlier per-task-`env` form of this rule — the environment-scoped form above is the resolved decision, taken because a task's `env` overrides the caller's and would leave the deployment platform unable to opt out.
- **Local sign-in is a URL route and no other mechanism** — not a development authentication backend, not a management command that writes a session, not a query-parameter shim. Its URL name and path prefix are fixed constants held in exactly one place. The module ships in every component but the route is mounted only where locality is local; a route mounted unconditionally would make every deployed component refuse to start. The stage-2 refusal that guards it resolves the *view callable's* owning module, never a name or prefix match.
- **Persona seeding calls the existing group-provisioning mechanism** rather than creating groups of its own. Designated groups and their permissions are provisioned by a data migration inside the base service package, seeded from the claims contract; a seeding task that creates groups itself is what makes the deployment bootstrap deadlock invisible to the harness.
- Local substitution for any contributed database is applied automatically by the base, so the run-with-nothing-installed property stays true by construction rather than per-app.
- Sessions are database-backed with the engine set explicitly in every combination; the local path must not vary this.
- Tests for the base and accelerator live under `tests/` mirroring `src/` and carry the disposition of what they cover.

## Cross-Story Dependencies

- Story 3.3 depends on the designated-group provisioning mechanism delivered in Epic 2; it must call it, not reimplement it. Stories 3.3 and 3.4 both depend on the shared mapper from Epic 2, and 3.5 depends on Epic 2's real Bearer authentication class and its lazy JWKS retrieval.
- Story 3.4 depends on Story 3.3's personas existing, and Story 3.5's minted token exercises the same identity/claims contract.
- Story 3.7's no-network-at-boot property constrains Stories 3.3, 3.4 and 3.5 — seeding and keypair generation must stay local computation and database writes.
- Story 3.1's locality declaration is what Epic 4 enforces against; the seeding task's deployed-environment refusal and the local sign-in route's stage-2 refusal are owned by Epic 4, not by this epic. Forward references to Epic 4 in these stories are traceability markers, not acceptance conditions here.
- Story 3.4's URL name and path-prefix constants move into the declarative carrier in Epic 7 without changing meaning, so hold them in a single module now.
- The fifth substitution (filesystem-backed object storage) is Epic 7's, delivered with the storage feature; do not attempt it here.
- Story 3.6 must not regress what Epic 6 later verifies end to end; this epic owns only the no-endpoint-configured local behaviour.
- `pixi.toml` is touched by several epics in distinct blocks; this epic owns only the locality declaration.
