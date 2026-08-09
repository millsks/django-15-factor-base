---
title: "Product Brief: django-15-factor-base"
status: draft
created: 2026-08-08
updated: 2026-08-09
---

# Product Brief: django-15-factor-base

## Executive Summary

`django-15-factor-base` is an accelerator template for generating Django application components inside an enterprise platform. A lead developer selects the features a component needs from a dropdown, and the generator emits a working service that already satisfies 15-factor principles: the twelve factors plus API-first, telemetry, and authentication/authorization. A CI pipeline containerizes that component and deploys it to a platform such as OpenShift.

The product is not the Django code, which anyone could write in an afternoon. The product is the **set of decisions already made and proven**: which packages, resolved from which channel, wired in which order, with which traps already hit and documented. A generated component emits correlated structured logs, exports OpenTelemetry traces, authenticates against the corporate IdP, and passes a 90% coverage gate on the day it is created — without its author knowing why any of that was hard.

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

**Constraint:** background task processing requires a broker, so selecting it without Redis is invalid and the generator must refuse it rather than emit a component that cannot start. That constraint eliminates one of four task/cache pairings, so four toggles yield **12 valid combinations, not 16**.

Immovability is a **capability** contract, not a package list. "Every component emits traces" is fixed; the instrumentation packages flex, because the Celery, Redis, and Postgres instrumentors exist only when those features do.

## Success Criteria

The promise is that the *generated* component works. A green gate on this repository proves one configuration, so the criteria are stated against generator output:

1. **Every valid combination builds and passes.** All 12 are generated and put through the full gate — tests, ≥90% coverage, strict type checking, lint, build — and all 12 pass.
2. **Excluded features leave nothing behind.** No orphaned dependency, template, settings fragment, or test in any generated combination.
3. **A generated component is deployable unmodified** — containerized by the CI pipeline and started on the target platform with no source edits.

## Scope

### In scope

- The Django base: the immovable core and the four selectable features
- Grouping code, dependencies, settings, templates, and tests so a feature can be excluded cleanly
- Rewiring authentication to the IdP exclusively, removing all three local credential paths
- The feature model, its constraint, and the presets
- Verification of generated combinations
- The interface a component presents to the deployment pipeline: environment-variable configuration, a health signal, OTLP export settings

### Out of scope

- **Deployment configuration.** It lives in a separate repository outside the control of the team that owns this product. The contract to it is in scope; its contents are not.
- **The FreeMarker generator engine.** This product supplies the template it consumes.
- **IdP configuration.** Realms, clients, and group definitions are administered elsewhere.
- **Multi-factor authentication.** Enforced at the IdP, never in the component.
- **User media handling.** Avatars resolve from IdP profile metadata as remote URLs.

## Risks and Accepted Trade-offs

**No break-glass account (accepted).** With every credential path delegated to the IdP, an outage locks everyone out of Django admin, including its administrators — accepted in exchange for a single auditable authentication path.

**Phase 2 blinds the gate.** Verification against generated output must exist *before* the repository becomes a template, or the central quality claim goes dark exactly when the product starts being used.

**Orphan detection depends on coverage.** The 0%-coverage signal that catches incomplete feature removal must survive into generated-output verification, or extraction defects ship silently.

**Authorization must re-sync on every login.** Group claims mapped only at account creation mean revoked IdP access never propagates. The mapping must run on every authentication and be shared by the interactive and programmatic paths.

**Channel availability constrains features.** Every feature needs its dependencies on conda-forge or it forces a supply-chain exception. Object storage was the first test and the rule held — `django-storages` and `boto3` are both available, as are the `pyjwt` and `cryptography` packages the authentication rewire needs. Every future feature must be checked the same way before it is committed to.

## Vision

The accelerator becomes the only way a Django component starts inside the platform, and the fastest — so compliance is a side effect of convenience rather than a review gate. Further out, the base stops being a starting point and becomes a living one: a Django release, a new mandatory factor, or a changed auth posture is absorbed once here and propagated, instead of being negotiated with every team that ever forked a repo.
