---
id: SPEC-django-15-factor-base
companions:
  - capability-map.md
  - ../../planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md
  - ../../planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/addendum.md
  - ../../planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability only — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# django-15-factor-base — Phase 1

## Why

An **opportunity to capture** with a **mandate** attached. A lead developer inside the enterprise platform should be able to order a Django component from the enterprise developer portal and have their first commit be business logic — the component already emits correlated logs and traces, already authenticates against the corporate identity provider and nothing else, and already passed a full quality gate on the day it was created. The product is not the Django code; it is the set of decisions already made and proven, living where they are enforced so rationale cannot drift from configuration.

Phase 1 is where those decisions become real and provable. It delivers the reference application with every capability present and exercised, the authentication rewire that makes the IdP the only credential path in a deployed component, the startup refusals that keep local convenience out of deployment, and the harness that proves all six valid combinations build, pass, and run. The harness is the load-bearing part: the quality gate cannot run against FreeMarker-interleaved source, so verification has to move to what the template renders — and it has to move **before** the phase-2 transition, or the central quality claim goes dark exactly when the product starts being used.

The measure is that the accelerator becomes the fastest way to start a Django component inside the platform, so compliance is a side effect of convenience rather than a review gate. A standard slower than the fork it replaces does not get adopted; it gets routed around.

## Capabilities

- **CAP-1 — Immovable core**
  - **intent:** Every valid combination provides the same fixed capability set — PostgreSQL, allauth with OIDC, DRF with drf-spectacular, the Django admin, CORS, structlog, OpenTelemetry, environment-based configuration, static file serving, and a uvicorn/gunicorn process — defined by capability rather than by package list, so instrumentation flexes with the capabilities that exist while the guarantee does not.
  - **success:** All six materialized combinations serve an API described by their generated schema, render the admin, emit correlated structured logs, and produce spans for ASGI requests; the dependency manifest of each carries exactly the instrumentation packages its capabilities require and no others. *(SC-7)*

- **CAP-2 — IdP-only authentication through one shared mapper**
  - **intent:** A person authenticates interactively by redirect to the IdP and an API client authenticates programmatically by Bearer JWT, and both resolve authorization through a single mapper keyed on one stable identity claim, which re-syncs group membership, staff, and superuser status on every credential epoch including removals.
  - **success:** A real IdP identity authenticates through both flows and resolves to the same user in either order; memberships the claims assert are added, memberships they no longer assert are removed, staff and superuser are set from their designated groups, and the admin and the API agree on the authorization state of the same identity. *(SC-6)*

- **CAP-3 — The refusal contract**
  - **intent:** A deployed component refuses to start on any of nine forbidden configurations, evaluated at two defined points independently of which settings module loaded, and backed by an allowlist so a credential path added later fails the build rather than shipping.
  - **success:** Each of the nine conditions has a test that configures the forbidden state and asserts `ImproperlyConfigured`; the authentication surface matches its allowlist exactly; and a deployed environment loading the local settings module refuses. *(SC-5)*

- **CAP-4 — Local development with nothing installed**
  - **intent:** A developer clones a component and runs it on a machine with no database, cache, broker, object store, or identity provider, exercising real authorization behaviour through seeded personas and a locally signed development token, with observability deliberately unsubstituted.
  - **success:** Every valid combination starts, serves, returns 200 from readiness, and authenticates a persona into a rendered admin index with no external service running; a locally minted JWT is verified for signature, `iss`, `aud`, and `exp` by the real Bearer authentication class. *(SC-4)*

- **CAP-5 — Feature model and clean extraction**
  - **intent:** A lead developer selects any subset of three features — background task processing, Redis cache, object storage — whose entire surface is declared in one carrier, and an unselected feature is absent rather than present-and-disabled.
  - **success:** No materialized combination contains a dependency, template, static asset, settings fragment, or test belonging to a feature it did not select, and an orphaned template override introduced deliberately fails that combination's gate. *(SC-2)*

- **CAP-6 — Materializer and two-level verification**
  - **intent:** A developer or CI job materializes the complete source of any valid combination deterministically from the reference application, so the six-combination claim is provable before the FreeMarker transition rather than after it.
  - **success:** All six valid combinations are materialized and pass the full gate — tests, coverage at or above ninety percent including templates, strict type checking, lint, build — against PostgreSQL, with no partial pass; materializing one combination twice produces byte-identical trees; and an invalid pairing is refused with the broker constraint named. *(SC-1)*

- **CAP-7 — Deployment interface**
  - **intent:** A component declares to a deployment repository it does not own which process types it runs, what its health endpoints mean, how it drains, and that migration is a release-stage step — and never migrates itself.
  - **success:** A component is containerized by CI and started on the target platform with no source edits, under an arbitrary non-root UID with a read-only root filesystem, with its declared process model, asymmetric liveness and readiness semantics, and drain ordering intact. *(SC-3)*

- **CAP-8 — Observability**
  - **intent:** Every component writes a JSON event stream to stdout carrying request, trace, and span identifiers, produces spans for ASGI requests, and makes swallowed degradation visible — none of which any feature selection can remove.
  - **success:** Correlation identifiers are present on log lines emitted during a request in all six combinations and propagate into task execution where background processing is selected; the ASGI instrumentor is active in all twelve; every swallowed cache failure emits a correlated log event; and the OTLP export path is exercised end to end against a collector stub. *(SC-7)*

- **CAP-9 — Supply chain policy**
  - **intent:** Every dependency in every combination resolves from the approved channel with its reasoning recorded at the point of declaration, and a new feature is not committed to until its dependencies are proven both present on the channel and fit against the pinned runtime.
  - **success:** A test asserts no third-party package resolves from the package index — the block carries the component's own editable path install and nothing else — and dependencies are lock-pinned with no reliance on system packages.

- **CAP-10 — Extension model**
  - **intent:** A component extends through a declared tenant space whose reusable apps contribute configuration additively on a closed surface, keep their import path when they graduate to the channel, and declare which versions of the base they support.
  - **success:** Writing to configuration the component already defines raises `ImproperlyConfigured` at startup and introducing a new key succeeds; the same app is importable by the same name in the tenant space and once installed from the channel; adopting an app outside the base's supported range fails the component's gate; and a component adopting an app with its own database still starts, serves, and authenticates a persona with nothing installed.

## Constraints

- The IdP is the only credential authority in a deployed component. Local credential paths exist only where the refusals do not apply, and a refusal never degrades to a warning.
- Authorization is decided in exactly one place — the mapper at `src/config/authorization/` — and resolution is keyed on one stable identity claim, never an email address or username.
- Deployment is the default and local development is the exception that must declare itself: an absent or unrecognized runtime declaration means deployed. The declaration is carried by the local pixi task environment, never by a file in the source tree and never in `[activation.env]`.
- Every dependency resolves from conda-forge; `[pypi-dependencies]` carries the editable self-install and nothing else. Zero exceptions as of 2026-08-14. A feature is not committed to until its dependencies are proven present **and** fit against the pinned Django 6.0 and Python 3.14.
- `src/django_service/` is a constant, never parameterized, and no feature-scoped disposition may apply to any path inside it — reusable apps import from it by that name in every deployment.
- The coverage floor is ninety percent including templates, globally, with the C trace core in force in every combination and the omit/exclude list a closed carrier-declared surface. Never a lower floor, a pragma, or a narrowed measurement.
- Any bound on the verification set is reported explicitly with the combinations it did not cover. A silently truncated set reads as full coverage.
- A substitution is warranted only where the deployed dependency cannot be present on a developer's machine without becoming the service dependency the local contract exists to remove. The count is not the constraint; the principle is.
- Nothing on the local start path reaches the network at boot: OIDC discovery and JWKS retrieval are lazy, on first use only.
- No network surface exists beneath Django's URL routing. A protocol handled below the resolver is invisible to the authentication allowlist and is never an inherited handler.
- Configuration is exclusively environmental — no configuration file is baked into the image — and a materialized component ships no Dockerfile.
- All six pixi environments share one solve-group. Without it the two Celery combinations resolve a different Django from the other four and the six-combination claim stops meaning what it says.
- Dev/prod parity is deliberately traded. Backing services differ between local and deployed; the trade is bounded by the gate running against PostgreSQL, authorization code paths shared rather than mocked, and observability not substituted at all.
- Concrete non-functional numbers — probe timings, startup budget, termination grace, resource limits, JWKS cache TTL — are outside this contract and are pinned against the real platform.

## Non-goals

- The FreeMarker generator engine. This product supplies what the engine consumes.
- The phase-2 template conversion itself. Requirements here that serve it exist because the harness must precede the transition, not because this contract delivers it.
- Deployment configuration. It lives in a separate repository outside this team's control; the contract to it is in scope, its contents are not.
- IdP configuration. Realms, clients, and group definitions are administered elsewhere; a component declares only what it reads.
- Multi-factor authentication. Enforced at the IdP, never in the component.
- User media handling. Avatars resolve from IdP profile metadata as remote URLs.
- Propagating an accelerator change into components already generated. The provenance stamp makes those components enumerable, which is the precondition and not the solution; a generated repository someone else now owns and edits is a fork by any honest definition, and closing that is a second product.
- A local identity-provider container. It reintroduces the per-machine service dependency the substitutions exist to remove; it remains the right answer for deliberate work on the authentication layer, as an optional path.
- A break-glass account in a deployed component. Every credential path is delegated to the IdP, and an IdP outage locking out the admin is accepted in exchange for a single auditable path.
- Becoming a general-purpose Django starter. The enterprise platform assumptions are load-bearing throughout.
- Carrying the platform's guarantees into a template repository. Consuming this repository through the code host's create-from-template facility produces a fork of the base, not a component, and is outside every guarantee here.
- Scheduling the session-pruning process. The schedule lives in the deployment repository; the component-side requirement is in scope.
- All-pairs verification as the standing policy. Exhaustive verification of six is correct until the space grows past roughly thirty-two.

## Success signal

A lead developer orders a Django component from the enterprise developer portal, clones it, and their first commit is business logic — because the pipeline that goes green on that commit was already green before they wrote it, and they never opened a decision about logging, tracing, or authentication.

Demonstrable in one CI run: all six valid combinations materialize from the reference application, pass the full gate against PostgreSQL, and boot-and-authenticate a persona locally with nothing installed — and a deliberately introduced orphan or forbidden configuration fails its combination rather than passing quietly.

## Assumptions

- The channel's `django-storages` build works against the pinned Django 6.0 and Python 3.14. Its released version predates both and declares support for neither. *Owner:* architecture. Object storage appears in three of six combinations and dropping it is not an available answer, so this is carried as a named risk rather than avoided.
- Session lifetime is short enough that per-authentication re-sync is the accepted revocation latency. *Owner:* platform group.
- The platform's termination grace period exceeds the longest expected drain. *Owner:* deployment repository.
- A platform startup-time budget exists. The substantive requirement — that the nine refusal checks are cheap enough to be irrelevant to startup — does not depend on knowing its value. *Owner:* architecture.

## Open Questions

- What is the accepted revocation latency for an established session? If the window is judged too wide, the answer is a shorter session lifetime, not a change to the mapper. *Owner:* platform group.
- Who owns the OTLP export end-to-end test, and what shape does its collector stub take? No architectural decision covers it.
- Who owns the telemetry-overhead measurement, and against which milestone? No architectural decision covers it.
- What is the enterprise developer portal's order-surface field list? The fail-on-missing-fixture rule needs one; until it exists the fixture set covers only the declared parameters and the four feature booleans. *Owner:* portal team.
- Should `prd.md`'s frontmatter `updated: 2026-08-16` be corrected? It is a day later than its own commit and a day in the future relative to this spec run. Needs a bmad-prd run; neither bmad-spec nor bmad-architecture edits it. *(Successor to the spine-staleness question, which was resolved on 2026-08-15 — see `capability-map.md`.)*
