---
title: "Product Brief: django-15-factor-base"
status: draft
created: 2026-08-08
updated: 2026-08-14
---

# Product Brief: django-15-factor-base

## Executive Summary

`django-15-factor-base` is an accelerator template for generating Django application components inside an enterprise platform. A lead developer selects the features a component needs from a dropdown, and the generator emits a working service that already satisfies 15-factor principles: the twelve factors plus API-first, telemetry, and authentication/authorization. A CI pipeline containerizes that component and deploys it to a platform such as OpenShift.

The product is not the Django code, which anyone could write in an afternoon. The product is the **set of decisions already made and proven**: which packages, resolved from which channel, wired in which order, with which traps already hit and documented. A generated component emits correlated structured logs, exports OpenTelemetry traces, authenticates against the corporate IdP, and passes a 90% coverage gate on the day it is created — without its author knowing why any of that was hard. It also runs on the developer's machine the moment it is generated, with no database, broker, cache, or identity provider installed alongside it.

## The Problem

Starting a new Django component today means forking an existing service and inheriting whatever was true the day it was forked. Three costs follow, and they compound.

**Decisions are re-litigated or silently lost.** Each new component must rediscover — or ship without — whether the OpenTelemetry ASGI instrumentor is optional (it is not; without it, ASGI requests produce no spans at all), whether template coverage measures anything (not unless the tracer core is forced), and which packages exist on the approved channel.

**Cross-cutting concerns become optional in practice.** Observability, authentication, and configuration are precisely what a team under delivery pressure defers. When they are a component's starting state, deferring them is no longer possible.

**Dead scaffolding accumulates invisibly.** An audit of this repository found five packages with zero references in the source tree and two template overrides no reachable page could render. Every fork inherits that debt and adds to it.

Underneath all three: nothing makes a new component *provably* meet the platform's standard rather than merely claim to.

## The Solution

A curated Django base and a feature model that a generator consumes.

The lead developer picks capabilities — background task processing, object storage, a server-rendered UI, caching — and receives a component containing exactly those. Unselected features are **absent**, not present-and-disabled: no dependency in the manifest, no entry in `INSTALLED_APPS`, no orphaned template, no skipped test.

The product moves through two lifecycle phases:

1. **Reference application (now).** A working Django application whose full gate — tests, coverage including templates, strict type checking, lint, build — passes on every change, with every feature present and exercised.
2. **Template (later).** Once scaffolding, configuration, and default features are settled, the same repository becomes the FreeMarker template the accelerator consumes.

That transition is a one-way boundary and the most consequential fact in this brief: **the gate that makes phase 1 trustworthy cannot run against phase 2 source.** Once FreeMarker directives are interleaved into Python, TOML, and templates, the files stop being valid inputs to `mypy`, `pytest`, or `ruff`. Verification must move from the template to what the template generates.

## What Makes This Different

This section is deliberately unflattering, because inflated claims here would mislead the architecture work downstream. The project began as `cookiecutter-django` and was restructured; all of it is technically reproducible, and there is no moat in the code. The genuine differentiators:

- **Decisions live where they are enforced.** The dependency manifest carries the reasoning for its own non-obvious lines — why one package comes from PyPI when every other comes from conda-forge, why a coverage core is pinned. Rationale cannot drift from configuration when it lives inside the configuration.
- **A single audited supply chain.** Every dependency resolves from conda-forge, with one documented exception.
- **Observability is structural.** Correlated logs and distributed traces are core; no feature selection removes them.
- **The gate detects, it does not decorate.** Removing a feature during this audit orphaned two template overrides that no import graph, linter, or dependency analyzer would flag. Only the coverage gate caught them, by reporting 0%. That property is what will keep feature extraction honest as the model grows.
- **The component runs before anything else does.** No compose file, no services, no IdP realm — where the project this was forked from expects a developer to bring an environment up first. What a developer exercises locally is not a mock of the deployed behaviour; it is the deployed behaviour, minus the network hops.

## Who This Serves

**The lead developer** is the primary user, at one moment: standing up a component and choosing its capabilities. Success is that their first commit after generation is business logic.

**The platform and architecture group** needs every component consistent, current, and auditable without policing teams individually. **Operators** need every component to emit the same correlated telemetry, so a request can be followed across services built by teams that never coordinated.

## The Feature Model

**Immovable core** — present in every component, not selectable:

PostgreSQL · django-allauth with OpenID Connect · Django REST Framework with drf-spectacular · Django admin · CORS · structlog · OpenTelemetry · environment-based configuration · static file serving · uvicorn/gunicorn

The three factors beyond the twelve — API-first, telemetry, authentication/authorization — are why that core is immovable.

**Selectable features:**

| Feature | What it adds |
|---|---|
| Background task processing | Celery, scheduled tasks, and their tracing instrumentation |
| Redis cache | Cache backend and its tracing instrumentation |
| Server-rendered UI | Form styling, page templates, and user-facing views |
| Object storage | Document and blob storage against an S3-compatible backend |

**Constraint:** background task processing requires a broker, so selecting it without Redis is invalid and the generator must refuse it rather than emit a component that cannot start. That constraint eliminates one of four task/cache pairings, so four toggles yield **12 valid combinations, not 16**. It constrains *deployed* environments only — locally, every combination runs with no broker at all.

**Presets** — *API-only*, *Full web app*, *Worker-enabled* — are named starting points that pre-select a set of toggles and stay fully editable. They constrain nothing; every valid combination is reachable without them.

Immovability is a **capability** contract, not a package list. "Every component emits traces" is fixed; the instrumentation packages flex, because the Celery, Redis, and Postgres instrumentors exist only when those features do.

## The Local Development Contract

The immovable core describes what a *deployed* component depends on. Requiring a developer to run all of it — PostgreSQL, Redis, a broker, an identity provider — to change a line of business logic would make the accelerator slower than the fork it replaces.

So a generated component runs on a developer's machine with **no external service running**. Each deployed dependency has a local substitute — designed as such, not a convenience that happens to work:

| Deployed | Local | What the substitute preserves |
|---|---|---|
| PostgreSQL | sqlite | The ORM, migrations, and the full test suite |
| Redis cache | in-memory cache | The cache API and every call site |
| Celery and its broker | eager, in-process execution | Task code paths, invoked synchronously |
| Corporate IdP | local users and admins, with synthetic claims | The claims-to-groups mapper, unchanged |

**Observability is the exception that needs no substitute.** Nothing about it is stubbed, swapped, or disabled locally — only the final export step is absent, so spans are discarded when they end instead of being exported. That makes it immovable in a stronger sense than the rest of the core: it is the one capability a developer cannot accidentally work without.

Two properties keep this from becoming a second, weaker product. **Local credentials are refused at boot in a deployed component** — not defaulted off but refused, because a wrong default is precisely the inherited failure this work set out to close. And **the local identity path is not a shim**: synthetic claims drive the same mapper, and the local token is validated by the same Bearer authentication class. Only the signer's identity is local. The addendum carries both mechanisms.

## Success Criteria

The promise is that the *generated* component works. A green gate on this repository proves one configuration, so the criteria are stated against generator output:

1. **Every valid combination builds and passes.** All 12 are generated and put through the full gate — tests, ≥90% coverage, strict type checking, lint, build — against **PostgreSQL** rather than the local sqlite substitute, and all 12 pass.
2. **Excluded features leave nothing behind.** No orphaned dependency, template, settings fragment, or test in any generated combination.
3. **A generated component is deployable unmodified** — containerized by the CI pipeline and started on the target platform with no source edits.
4. **A generated component runs locally with nothing else installed.** Every valid combination starts, serves, and authenticates a developer on a machine with no database, cache, broker, or identity provider running.

## Scope

### In scope

- The Django base: the immovable core and the four selectable features
- Grouping code, dependencies, settings, templates, and tests so a feature can be excluded cleanly
- Rewiring authentication so that a deployed component authenticates exclusively against the IdP, and refuses to start if a local credential path is enabled
- The local development contract: the four substitutions, the synthetic-claims path, and the locally signed development token
- The feature model, its constraint, and the presets
- Verification of generated combinations, against PostgreSQL and locally on sqlite
- The interface a component presents to the deployment pipeline: environment-variable configuration, a health signal, OTLP export settings

### Out of scope

- **Deployment configuration.** It lives in a separate repository outside the control of the team that owns this product. The contract to it is in scope; its contents are not.
- **The FreeMarker generator engine.** This product supplies the template it consumes.
- **IdP configuration.** Realms, clients, and group definitions are administered elsewhere.
- **Multi-factor authentication.** Enforced at the IdP, never in the component.
- **User media handling.** Avatars resolve from IdP profile metadata as remote URLs.

## Risks and Accepted Trade-offs

**No break-glass account in a deployed component (accepted).** Every credential path in a deployed environment is delegated to the IdP, so an outage locks everyone out of Django admin, including its administrators — accepted in exchange for a single auditable authentication path. The local users that make development possible are not a mitigation: they exist only where that refusal does not apply.

**One check carries the whole guarantee.** The separation between a development component and a deployed one rests entirely on the startup refusal. A credential path it fails to inspect, or a settings module that never reaches it, puts local credentials in a deployed environment — and that vulnerability would be one this product created deliberately rather than inherited. That check needs tests asserting refusal happens, not only that startup succeeds.

**Dev/prod parity is deliberately traded (accepted).** The tenth factor exists to discourage exactly what the local development contract does: varying backing services between development and deployment, with sqlite against PostgreSQL as its stock example. A product named for fifteen factors should say so rather than let a reader discover it. The trade buys a component that runs the moment it is generated, and it is bounded — the gate runs against PostgreSQL, the authentication and authorization code paths are shared rather than mocked, and observability is not substituted at all. Parity is given up at the edges the gate can re-establish, and nowhere else.

**Local development proves less than running the component suggests.** sqlite accepts schemas and queries that PostgreSQL rejects; eager Celery never exercises delivery, retries, or serialization; synthetic claims never exercise JWKS retrieval or key rotation. The gate covers all three, so this is a slower feedback loop rather than an unverified product — but a component running locally is not evidence it will run deployed.

**Phase 2 blinds the gate.** Verification against generated output must exist *before* the repository becomes a template, or the central quality claim goes dark exactly when the product starts being used.

**Orphan detection depends on coverage.** The 0%-coverage signal that catches incomplete feature removal must survive into generated-output verification, or extraction defects ship silently.

**Authorization must re-sync on every login.** Group claims mapped only at account creation mean revoked IdP access never propagates. The mapping must run on every authentication and be shared by the interactive path, the programmatic path, and the local synthetic-claims path — which is what makes the requirement exercisable without an IdP present.

**Channel availability constrains features.** Every feature needs its dependencies on conda-forge or it forces a supply-chain exception. Object storage was the first test and the rule held — `django-storages` and `boto3` are both available, as are the `pyjwt` and `cryptography` packages the authentication rewire needs. Every future feature must be checked the same way before it is committed to.

## What Is Not Yet Decided

This brief records the decisions made, not a finished design — but the gaps left in it are now few and specific. An audit against the fifteen factors found four unaccounted for; all four are settled in the addendum's deployment interface, along with the health signal, the local persona and signing-key provisioning, the full refusal list, and how local runnability is verified.

Three questions remain genuinely open, and they cluster:

- **How generated output is verified** once this repository becomes a template — the largest piece of downstream work, and the one the central quality claim depends on
- **How the component's own name is parameterized**, which is the same problem seen from the template's side
- **Where the shared claims-to-groups mapper lives**, so all three authentication paths consume one implementation. The requirement is settled; only its placement is not

The first two are the template transition. The third is module layout. Both are architecture work, which is where this brief hands off.

## Vision

The accelerator becomes the only way a Django component starts inside the platform, and the fastest — so compliance is a side effect of convenience rather than a review gate. Further out, the base stops being a starting point and becomes a living one: a Django release, a new mandatory factor, or a changed auth posture is absorbed once here and propagated, instead of being negotiated with every team that ever forked a repo.
