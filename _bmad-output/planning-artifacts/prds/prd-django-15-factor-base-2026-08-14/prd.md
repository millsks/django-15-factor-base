---
title: "PRD: django-15-factor-base"
status: final
created: 2026-08-14
updated: 2026-08-16
---

# PRD: django-15-factor-base

## 0. Document Purpose

This PRD specifies phase 1 of `django-15-factor-base`: the reference application and the verification harness that must exist before the repository becomes a FreeMarker template. It is written for the architect who will sequence this work, the developers who will implement it, and the platform group who will hold it to the platform's standard. It builds on `_bmad-output/planning-artifacts/briefs/brief-django-15-factor-base-2026-08-08/` — the product brief and its addendum — and does not duplicate them: the brief carries the case for the product, the addendum carries mechanism, findings, and rejected alternatives, and reasoning the addendum already worked through stays there.

Structure: a Glossary that the rest of the document uses verbatim, features grouped with functional requirements nested and numbered globally as FR-1 through FR-56, cross-cutting non-functional requirements in their own section, and a Factor Coverage section that holds the product to the fifteen factors its name commits it to. Each feature group carries a priority. Assumptions are tagged inline as `[ASSUMPTION]` and indexed in §14.

**Tense discipline, inherited from the addendum:** present tense describes what is true in the repository today. *Must* and *will* describe what this PRD requires and what is not yet built.

**Amendment — 2026-08-16: the server-rendered interface is no longer a feature.** Phase-1 story creation measured what a `feature:ui` disposition could actually remove and found it did not justify a feature axis. The Django admin is immovable core (FR-1) and requires the template loader, `base.html`, the error templates, static files and whitenoise, so the rendering stack was already present in every combination; the removable remainder was about 16 KB of templates, 8 KB of static assets and 100 lines of Python, and **no dependency at all**, since `templates/allauth/elements/field.html` and `fields.html` use `crispy` to render the FR-4 interactive sign-in flow.

Four features become three — background task processing, Redis cache, object storage — and **twelve valid combinations become six**. FR-3 is rewritten, FR-24 and FR-26 restate the counts, FR-27's presets are renamed (*API-only* and *Full web app* no longer name distinguishable selections), and the Glossary's definitions of *Feature*, *Combination* and *Valid combination* are amended. Every derived count in this document was recomputed: the six valid combinations are `¬celery` × {¬redis, redis} × {¬storage, storage}, plus `celery ∧ redis` × {¬storage, storage}. Rationale and the measurement are recorded in `../../architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md` §"Revision 3".

## 1. Vision

A lead developer inside the enterprise platform opens the enterprise developer portal, orders a Django component, selects the capabilities it needs, and receives a repository that already works. It emits correlated structured logs and OpenTelemetry traces. It authenticates against the corporate identity provider and nothing else. It passes a full quality gate — tests, ninety percent coverage including templates, strict type checking, lint, build — on the day it is created. A CI pipeline containerizes it and a deployment repository puts it on the platform. The first commit its author writes is business logic.

The product is not the Django code. Anyone could write that. The product is **the set of decisions already made and proven** — which packages, resolved from which channel, wired in which order, with which traps already hit and recorded next to the configuration they constrain. A lead developer receives all of it without needing to know why any of it was hard.

**It is worth being unflattering about this, because inflated claims here would mislead the architecture work downstream.** The project began as `cookiecutter-django` and was restructured. All of it is technically reproducible and there is no moat in the code. What is genuinely different is narrower and duller: the decisions live where they are enforced, so rationale cannot drift from configuration; the supply chain is audited to a single channel; observability is structural rather than optional; the gate *detects* rather than decorates, which is how two orphaned template overrides were found when no import graph, linter, or dependency analyzer would have flagged them; and the component runs before anything else does. That last one is the departure from what this was forked from, which expects a developer to bring an environment up first.

Stating the inheritance matters for a second reason. This PRD asserts that four credential paths bypass the IdP and that three local substitutions already held before anyone wrote them down. Those are not defects someone introduced — they are what arrived with the fork, which is precisely why they were never decided and never documented.

The measure of success is that the accelerator becomes the fastest way to start a Django component inside the platform, so that **compliance is a side effect of convenience rather than a review gate**. A standard that is slower than the fork it replaces does not get adopted; it gets routed around.

Phase 1 is where those decisions become real and provable. It delivers the reference application with every capability present and exercised, the authentication rewire that makes the identity provider the only credential path in a deployed component, the startup refusals that keep local convenience out of deployment, and the harness that proves all six valid combinations build, pass, and run. That harness is the load-bearing part: the quality gate that makes phase 1 trustworthy cannot run against FreeMarker-interleaved source, so verification has to move to what the template renders — and it has to move **before** the transition, or the central quality claim goes dark exactly when the product starts being used.

## 2. Target User

### 2.1 Jobs To Be Done

**The lead developer** (primary, at one moment — ordering a component):

- Start a new Django component without inheriting whatever was true the day someone forked an existing service.
- Get observability, authentication, and configuration as a starting state rather than as work that delivery pressure will defer.
- Know that the component is deployable before writing a line of it — not believe it, know it, because its own pipeline said so.
- Choose capabilities without having to reason about which packages, settings fragments, and instrumentation each one drags in.

**The developer working on a generated component** (day-to-day):

- Change a line of business logic without standing up a database, a cache, a broker, and an identity realm first.
- Exercise the real authorization behaviour locally, including the difference between a staff persona and a read-only one.
- Trust that what runs locally is the deployed behaviour minus the network hops, and know precisely where that stops being true.

**The platform and architecture group:**

- Keep every Django component in the estate consistent, current, and auditable without policing teams individually.
- Make conformance to the platform standard *provable* rather than merely claimed.
- Answer "which components predate this change" with an actual list.

**Operators:**

- Follow one request across services built by teams that never coordinated, because every component emits the same correlated telemetry.
- Probe, drain, and restart any component the same way regardless of which capabilities it selected.

### 2.2 Non-Users (v1)

- **Teams outside the enterprise platform.** The IdP, the enterprise developer portal, the approved package channel, and the target platform are all assumed present. Nothing here is designed for public or general-purpose use.
- **Non-Django services.** The accelerator produces Django components; other runtimes are a different product.
- **Developers of components already generated.** Propagating an accelerator change into existing components is named in §5 as a non-goal — the provenance stamp makes those components enumerable, and that is all this product provides.
- **Anyone administering the identity provider.** Realms, clients, and group definitions are configured elsewhere; a component only declares what it reads.

### 2.3 Key User Journeys

Downscaled deliberately: the ordering surface is the enterprise developer portal (out of scope) and the primary product surface is a repository, so these three journeys anchor the *why* behind the requirements rather than feed UX work. Beats that phase 1 cannot yet deliver end to end are marked, because a journey that quietly assumes the template would misrepresent this PRD's scope.

- **UJ-1. Dana orders a component and her first commit is business logic.**
  Dana leads a team that has been asked to stand up a document-processing service. She opens the enterprise developer portal, names the component, and picks its capabilities: background task processing, Redis cache, object storage, no server-rendered UI. The portal refuses nothing she asked for — the combination is valid. A new repository appears. Its pipeline has already run: the container is built, the gate is green, and the component has been deployed to the platform's development environment. She clones it, runs it on her laptop with nothing else installed, signs in as a staff persona, and sees the admin. Her first commit adds a model. **Climax:** the pipeline that goes green on that commit is the same pipeline that was already green before she wrote it. **Resolution:** she never opened a decision about logging format, tracing, or authentication. **Edge case:** had she selected background task processing without Redis, generation would have refused with the reason — no broker — rather than emitting a component that cannot start. *(Phase 1 delivers everything this journey depends on except portal-driven generation itself; the materializer of §4.6 produces the same repository content from the same selections.)*

- **UJ-2. Marco changes a line on a plane.**
  Marco picks up a ticket on a component generated three months ago. He has no VPN, no database running, no identity realm reachable. He clones, runs one command, and the component serves. He signs in as the seeded persona that carries the staff group and reaches the admin; he switches to the read-only persona and watches the same page refuse him — the authorization difference is real, produced by the same mapper the deployed component uses, from synthetic claims instead of an ID token. He mints a development token with another command and calls the API; the Bearer authentication class verifies its signature, issuer, audience, and expiry for real, against a local keypair. **Climax:** he runs the full suite and it passes. **Resolution:** he pushes; CI runs the same suite against PostgreSQL and catches what sqlite let through, which is the trade this product made knowingly. **Edge case:** if he sets `OTEL_TRACES_EXPORTER=console` he sees his spans on stdout — otherwise they are created, correlated into his logs, and discarded at the processor rather than flooding stderr against an unreachable collector.

- **UJ-3. Priya proves the estate, not one component.**
  Priya is on the platform group. A Django security release lands and the base is updated. Before the change is allowed to ship, the harness materializes all six valid combinations, runs each one's full gate against PostgreSQL, and runs a smoke check that boots each one with nothing installed and signs a persona in. **Climax:** five pass and one fails — the combination with no cache and no background task processing, where a settings fragment was left behind by the update. Nobody would have found it by review. **Resolution:** it is fixed before it reaches a single component, rather than being discovered by the first lead developer to order that combination.

## 3. Glossary

Downstream workflows and readers must use these terms exactly. Functional requirements, journeys, and criteria use them verbatim; introducing a synonym anywhere in this PRD is a discipline violation.

- **Accelerator** — the whole product: the Django base, the feature model, and the verification harness, consumed by the enterprise developer portal to produce components.
- **Reference application** — this repository in phase 1: a working Django application with every selectable feature present and exercised, whose own gate proves one configuration. Not a component.
- **Template** — this repository in phase 2, once FreeMarker directives are interleaved into its source. Out of scope for this PRD; named only where a phase-1 requirement exists to serve it.
- **Component** — a Django application produced by the accelerator, living in its own repository, owned by the team that ordered it.
- **Immovable core** — the set of capabilities present in every component regardless of selection. A **capability** contract, never a package list.
- **Feature** — one of the three selectable capabilities: background task processing, Redis cache, object storage. Selected or absent; never present-and-disabled. *(Amended: the server-rendered interface was a fourth feature and is now immovable core — see FR-3.)*
- **Combination** — one assignment of on/off to all three features. Eight exist.
- **Valid combination** — a combination that satisfies the broker constraint. Six exist.
- **Preset** — a named starting point (*Minimal*, *Cached*, *Worker-enabled*) that pre-selects features and remains fully editable. Constrains nothing.
- **Materializer** — the phase-1 mechanism, living in this repository, that produces the source of any valid combination from the reference application so the harness can gate it. Replaced by the template in phase 2; the verification it feeds is not.
- **Gate** — the full quality sequence: tests, coverage at or above ninety percent including templates, strict type checking, lint, and build. Run against PostgreSQL.
- **Smoke check** — the local-runnability verification for one combination: the component boots, readiness returns 200, and a persona signs in, with no external service running.
- **Harness** — the materializer and the two verification levels together.
- **Refusal** — a startup failure raised as `ImproperlyConfigured` when a deployed component is configured in a way this product forbids. Distinct from a default: a refusal cannot be reached accidentally. Nine exist, evaluated at one of two points (§4.3).
- **Carrier** — the single machine-readable artifact declaring every feature's surface, constraints, and presets. The only place a feature's extent is defined; read by the materializer, the disposition rule, and the orphan checks.
- **Identity key** — the claim by which the mapper resolves a user. Stable, designated in the claims contract, and never an email address or username.
- **IdP** — the identity provider: the OpenID Connect issuer a deployed component authenticates against. Never used to abbreviate anything else.
- **Enterprise developer portal** — where a lead developer places the order that drives generation. Always written out; never abbreviated.
- **Interactive flow** — browser authentication: Authorization Code with PKCE, redirect to the IdP, session cookie. Serves the Django admin and the server-rendered UI.
- **Programmatic flow** — API authentication: `Authorization: Bearer <JWT>`, validated against the IdP's JWKS endpoint. Serves API clients and service-to-service calls.
- **Mapper** — the single shared claims-to-authorization function. Turns claims about an identity into authorization state in Django, resolving the user by the identity key. The only thing in a component permitted to decide what a user may do or who they are. Three callers: the interactive flow, the programmatic flow, and the local path.
- **Claims contract** — the environment configuration declaring the identity key, which claim carries group membership, and which groups confer staff and superuser access.
- **Persona** — a named local identity declared as configuration with its groups and profile fields, materialized as a local account by a development task. Exists only where the refusals do not apply.
- **Substitution** — a local stand-in for a deployed backing service, designed as such. Five exist: sqlite, in-memory cache, eager task execution, filesystem-backed object storage, and local personas.
- **Orphan** — a file, dependency, settings fragment, or test left behind by feature removal that no import graph, linter, or dependency analyzer flags. Detected only by the coverage gate reporting zero.
- **Provenance stamp** — the record inside a component of the accelerator version and the order values that produced it.
- **Deployment repository** — the separate repository, outside this team's control, that runs a component on the platform. This PRD specifies the contract to it, never its contents.
- **Base package** — the component's platform-provided application package. Its name is identical in every component and is never parameterized, because reusable apps import from it.
- **Reusable app** — a Django application built *on* the base rather than inside it. It lives in the tenant space while it is being developed and, once it has proven itself, is published to the approved channel and adopted by other components as an ordinary dependency.
- **Tenant space** — the declared location in a component where the applications that component owns live. The accelerator neither provides nor judges its contents.
- **Contribution** — the configuration a reusable app adds to the component that adopts it. Additive only: an app may introduce configuration and may never change configuration that already exists.
- **Template repository** — this repository consumed directly by the code host's create-from-template facility, producing a fork of the base rather than a generated component.

## 4. Features

Each subsection is a coherent feature group carrying a priority. **Phase-1 must-have** means the requirement is in scope for this PRD's delivery. **Next** means the requirement is specified here because a phase-1 decision depends on it, but building it belongs to the template work that follows.

### 4.1 The Immovable Core

**Priority: Phase-1 must-have.**

**Description:** Every component contains a fixed set of capabilities that no selection can remove: PostgreSQL, django-allauth with OpenID Connect, Django REST Framework with drf-spectacular, the Django admin, CORS, structlog, OpenTelemetry, environment-based configuration, static file serving, and a uvicorn/gunicorn process. The three factors beyond the fifteen — API-first, telemetry, and authentication/authorization — are why this core is immovable rather than merely default. Realizes UJ-1, UJ-3.

The core is a capability contract, not a package list. "Every component emits traces" is fixed; the instrumentation packages that deliver it flex, because the Celery, Redis, and Postgres instrumentors exist only where those capabilities do. An architecture that hardcodes the immovable core as a fixed package list will ship dependencies that four of the six valid combinations cannot use.

**Functional Requirements:**

#### FR-1: Immovable capability set

Every valid combination provides the immovable core, and no feature selection removes any part of it. Realizes UJ-1.

**Consequences (testable):**
- Each of the six valid combinations declares PostgreSQL as its deployed database, DRF with drf-spectacular, the Django admin, CORS handling, structlog, OpenTelemetry, environment-based configuration, static file serving, and a uvicorn/gunicorn process.
- No feature toggle in the feature model can be set to a value that removes any of the above.
- A combination in which the Django admin is unreachable fails the smoke check.

#### FR-2: The immovable set is defined by capability, not by package

The dependency manifest of a materialized combination contains the instrumentation packages that combination's capabilities require, and no others. Realizes UJ-3.

**Consequences (testable):**
- `opentelemetry-api`, `-sdk`, `-exporter-otlp-proto-http`, `-instrumentation-django`, `-instrumentation-asgi`, and `-instrumentation-psycopg` are present in all six combinations.
- `opentelemetry-instrumentation-celery` is present in exactly the combinations that selected background task processing, and absent from the others.
- `opentelemetry-instrumentation-redis` is present in exactly the combinations that selected the Redis cache, and absent from the others.
- `django-structlog` is present in all six; its Celery correlation-ID propagation is wired only where background task processing is selected.

#### FR-3: The interface mechanism is immovable core

The rendering stack — template loading, `base.html`, the navigation bar and its contribution registry, the error templates, form styling, static-file serving and the user profile views — is present in every component and is not selectable. Realizes UJ-1.

**Amended.** This requirement previously made the Django admin orthogonal to a *server-rendered UI feature*. That feature no longer exists. The admin is immovable core (FR-1) and requires the template loader, `base.html`, the error templates, static files and whitenoise, so the rendering stack was already present in every combination. Measured against the reference application, what the feature could actually remove was roughly 16 KB of templates, 8 KB of static assets and 100 lines of Python — and no dependency at all, since `templates/allauth/elements/field.html` and `fields.html` use `crispy` to render the FR-4 interactive sign-in flow. Carrying a feature axis and six extra valid combinations to remove that much was not a sound trade.

**Consequences (testable):**
- In every combination the admin renders, static files serve, the messages framework is available, and template rendering works.
- `base.html` and the 403/404/500 templates render in every combination, and the smoke check asserts a rendered admin index and a rendered 404.
- `base.html` contains no hardcoded navigation links; the navigation bar renders the contributed registry, so an adopted app can appear in it (FR-54).
- The `home` and `about` demonstration pages are removed rather than made core: nothing in the product requires them, and a component that wants a landing page owns one.

---

### 4.2 Authentication and Authorization

**Priority: Phase-1 must-have.** This is the largest unbuilt block in the product and none of it is implemented.

**Description:** A deployed component authenticates exclusively against the IdP, through two distinct flows that must not be conflated. The interactive flow serves the Django admin and the server-rendered UI over Authorization Code with PKCE, and costs no new *framework* — the OpenID Connect provider ships in the installed allauth distribution. It does cost a package: the provider imports `requests` directly, and the approved channel's allauth recipe does not declare it, because upstream places it in a `socialaccount` extra the recipe drops. `requests` reaches the environment today only transitively, through the telemetry exporter (FR-49). The programmatic flow serves API clients over `Authorization: Bearer <JWT>` validated against the IdP's JWKS endpoint, and requires new dependencies: PyJWT and `cryptography`, both confirmed on the approved channel. Realizes UJ-1, UJ-2.

Four credential paths currently bypass the IdP, all verified in the source. The defect is not that they exist — §4.4 keeps every one of them available locally — but that they are **enabled by default and unguarded**, so a deployed component bypasses the IdP unless someone remembers to configure it not to. The remediation inverts that: available where configured on, refused at startup where not permitted.

DRF's `TokenAuthentication` cannot be adapted to this. It is hardwired to the `rest_framework.authtoken` model and resolves an opaque key against the local database; it has no concept of issuer, signature, expiry, or claims. Alternatives considered and rejected — `mozilla-django-oidc`, `djangorestframework-simplejwt`, `django-oauth-toolkit`, `allauth.headless` — are recorded in the brief's addendum §1.3 with their reasoning.

**Functional Requirements:**

#### FR-4: Interactive authentication against the IdP

A person can authenticate to the Django admin and the rendered interface by redirect to the IdP using Authorization Code with PKCE, receiving a session cookie. Realizes UJ-1, UJ-2.

**Consequences (testable):**
- Reaching an authenticated page unauthenticated redirects to the IdP, not to a local login form.
- The flow uses `allauth.socialaccount.providers.openid_connect` from the installed distribution; no additional OIDC framework is added.
- A successful callback establishes a session and invokes the mapper (FR-8).

#### FR-5: Programmatic authentication against the IdP

An API client can authenticate by presenting `Authorization: Bearer <JWT>`, which the component validates against the IdP's JWKS endpoint. Realizes UJ-1, UJ-2.

**Consequences (testable):**
- Validation is performed by a `rest_framework.authentication.BaseAuthentication` subclass using PyJWT and `cryptography`.
- Signature, `iss`, `aud`, and `exp` are each verified; a token failing any one is rejected with 401.
- JWKS material is fetched from the IdP and cached by key identifier. A credential presenting an identifier the component does not hold triggers exactly one refetch, rate-limited, so a key rotation is survived without a restart and without knowing the identity provider's rotation schedule. A cache lifetime remains only as a backstop for key *removal*, where any reasonable value serves.
- **Retrieval is lazy**: JWKS is fetched on the first Bearer request that needs it, never at import or at boot. A component must boot with no route to the IdP (FR-18).
- A successful validation invokes the mapper (FR-8).

#### FR-6: The static-token credential surface is removed entirely

A deployed component contains no path that issues or accepts a locally minted API token. Realizes UJ-1.

**Consequences (testable):**
- `TokenAuthentication` is absent from `REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES`.
- `rest_framework.authtoken` is absent from `INSTALLED_APPS`.
- The `obtain_auth_token` route is deleted from the URL configuration; a request to `/api/auth-token/` returns 404.
- A test asserts the route's absence from the resolved URL configuration, not merely the setting's absence — removing the authentication class disables token *acceptance* and leaves the route still issuing them.

#### FR-7: The Django admin is forced through the IdP

In a deployed component, `/admin/` login is served by the IdP redirect and never by Django's own credential form. Realizes UJ-1.

**Consequences (testable):**
- `DJANGO_ADMIN_FORCE_ALLAUTH` defaults to true; the existing `secure_admin_login` wrapper in `users/admin.py` is the mechanism and requires no new code.
- A deployed component with the flag false refuses to start (FR-13).

#### FR-8: One shared mapper owns all authorization decisions

Every authentication, by any flow, resolves authorization through a single mapper located at `src/config/authorization/`. Realizes UJ-2, UJ-3.

**Consequences (testable):**
- All three callers — allauth's `SocialAccountAdapter`, the DRF `BaseAuthentication` subclass, and the local path of §4.4 — import the mapper; none contains its own mapping logic.
- The mapper is not behind any feature toggle and is present in all six valid combinations.
- A test asserts that the admin and the API agree on the authorization state of the same identity presented through different flows.
- **One claim is the identity key.** The claims contract designates a stable subject identifier, and the mapper resolves the user by that claim alone — never by email address or username, which are mutable at the IdP and collidable between identities.
- An identity first seen through the programmatic flow and later through the interactive flow resolves to the same user. A test asserts this in both orders.
- Two distinct identities whose email claims collide resolve to two distinct users.

**Notes:** one mapper without one identity key leaves the divergence FR-8 exists to prevent reachable by another route — a Bearer-first identity creates a user with no linked social account, and the same person's later interactive login either creates a second user or collides with the first, depending on how account resolution happens to be written. Placement beside `src/config/observability/` is settled: that is already this repository's home for a cross-cutting concern with several independent consumers and no natural owner among them, and placing the mapper in the users app would make the DRF authentication class import from a package the server-rendered UI feature also edits.

#### FR-9: Authorization re-syncs on every authentication, including revocation

On every authentication the mapper resolves or creates the user, adds the group memberships the claims assert, **removes the memberships the claims no longer assert**, sets staff status from the designated group, and emits a structured log line recording what changed. Realizes UJ-2, UJ-3.

**Consequences (testable):**
- Mapping does not live in `populate_user()`, which runs once at account population; a test asserts mapping occurs on a second and subsequent authentication.
- An identity whose claims drop a group loses the corresponding Django group membership on its next authentication.
- An identity whose claims drop the designated staff group loses staff status on its next authentication and can no longer reach the admin.
- Each authorization change produces a structured log event correlated with `request_id` and `trace_id`.
- **Resolution and re-sync run at different frequencies, and the difference is a requirement.** Resolving an identity to a user runs on every authentication, including every request of the programmatic flow. Re-syncing group membership runs once per credential epoch: every interactive authentication, and once per bearer credential rather than once per request. Read without this distinction, the requirement mandates a membership diff and up to two writes on every API call for a single identity, which no component can sustain.

**Out of Scope:**
- Propagating a revocation to an already-established session before its next authentication. `[ASSUMPTION: session lifetime is short enough that per-login re-sync is the accepted revocation latency; architecture confirms against the platform's session policy.]`
- Propagating a revocation to an already-issued bearer credential before it expires. This is not a design choice that could have gone the other way: the claims are carried *in* the credential, so a component honours them until it expires no matter how often it re-syncs. Re-syncing per request would rewrite the same rows without shortening that window by a second. The lever is credential lifetime, and it belongs to the identity provider.

#### FR-10: The claims contract is configuration

Which claim carries group membership, and which group confers staff status, are read from the environment rather than hardcoded. Realizes UJ-3.

**Consequences (testable):**
- The group-claim name is environment-configurable; `groups`, `roles`, and `realm_access.roles` are all expressible without code change.
- The group that confers staff status is environment-configurable.
- A component started without the claims contract configured refuses to start (FR-13).

#### FR-11: Superuser creation is retired as the deployed bootstrap path

In a deployed component, the first administrator is established by IdP group claim rather than by `createsuperuser`. Realizes UJ-1.

**Consequences (testable):**
- Staff status is set exclusively by the mapper from the designated group.
- Superuser status is likewise group-driven, from a second designated group in the claims contract, and is cleared when the claims stop asserting it. Without this, an administrator promoted by claim reaches an admin with no permissions in it, and any pre-existing superuser stays permanently outside IdP control.
- Documentation states the bootstrap path; `createsuperuser` remains available only where the refusals do not apply.
- **The groups themselves exist before the first authentication.** The designated groups, and the permissions attached to them, are provisioned by the component rather than assumed to be present — and the local persona path uses that same provisioning rather than creating groups of its own. Without this the product deadlocks in a way no local check can see: claims assert a group that does not exist, FR-9 ignores it, staff status is never granted, and the only place a human could create the group is the admin they cannot reach.
- A designated group absent from a deployed component refuses at startup (FR-13), on the same reasoning that refuses an unconfigured claims contract.

---

### 4.3 The Refusal Contract

**Priority: Phase-1 must-have.** One condition is built; eight are not, and the mechanism that evaluates all nine is not built either.

**Description:** The separation between a component in local development and a deployed component rests entirely on startup refusals, which makes this the product's highest-consequence surface (§11). The pattern already exists for the database, which raises `ImproperlyConfigured` when the sqlite fallback is reached rather than quietly preferring PostgreSQL. Every other substitution gets the same treatment. Realizes UJ-3.

**Nine conditions: seven unconditional, two scoped to a feature.** The two conditional ones exist because production settings hardcode the Redis cache backend, so a component that did not select Redis legitimately falls back to Django's in-process cache in production — the honest consequence of not selecting a cache. An unconditional refusal there would reject four valid combinations. The same reasoning applies to eager task execution, which is meaningless in a component with no background task processing.

Three of the unconditional conditions are not credential paths and must not be filed as such. The JWKS trust anchor catches a component doing everything correctly and trusting the wrong signer: the Bearer authentication class runs, the signature verifies, and `iss`, `aud`, and `exp` are all checked — the component is simply anchored to a key generated onto a developer's laptop. The claims contract catches a component that authenticates correctly and then cannot decide what anyone is allowed to do. Unapplied migrations catch a component serving against a schema it does not recognize. None of the three is a bypass, so no check that asks "is a bypass enabled" will see any of them.

Where and when the contract is evaluated are both requirements, and two constraints pull against each other. The logic must not live inside the deployed settings module, because the failure mode it most needs to catch — a component pointed at the local settings module — is precisely the case where that module never loads; a guard placed behind the door it is guarding cannot fire. But several conditions need the resolved URL configuration, which does not exist at settings-import time: Django raises `AppRegistryNotReady`. Django's own system-check framework is not the escape, because it does not run under `gunicorn config.asgi:application`, which is the only path that matters in deployment. FR-12 resolves this with two evaluation points, assigning each condition to the earliest point that can evaluate it.

**Functional Requirements:**

#### FR-12: The refusal contract is evaluated at two defined points, independently of which settings module loaded

Conditions readable from settings alone are evaluated at settings import, by shared code every settings module imports. Conditions requiring the application registry are evaluated at serving-process startup. The decision *am I deployed?* is read from the environment, never inferred from which module was loaded. Realizes UJ-3.

**Consequences (testable):**
- **Stage 1 — settings import.** Shared code, imported by every settings module, evaluates every condition that reads only settings. No settings module can skip it by not being loaded.
- **Stage 2 — serving-process startup.** An `AppConfig.ready()` belonging to a first-party application inside the immovable core evaluates the conditions that need the application registry. It fires under gunicorn and uvicorn as well as under management commands, which is what Django's system-check framework does not do.
- The environment declaration fails closed: absent or unrecognized, the component treats itself as deployed and applies every unconditional condition. Local development is the exception and must declare itself; deployment is the default.
- The local declaration is carried by the local development task's environment, not by a file in the source tree. It is committed, so a freshly cloned component runs with one command; and it is inert in deployment, because a container runs its server process directly and never invokes that task.
- A component started with its settings module pointed at the local module, in an environment that has not declared itself local, refuses to start. A test constructs exactly that state and asserts refusal.
- A test asserts stage 2 fires under a served request path, not only under `manage.py`.

**Notes:** this replaces the weaker mechanism the source material implied — an assertion inside the deployed settings module that the loaded module is the deployed one — which inherits the hole it is meant to close. Relocating removes the failure mode rather than detecting it.

#### FR-13: Unconditional refusals

A deployed component refuses to start when any of seven conditions holds, regardless of which features it selected. Each is annotated with the evaluation stage of FR-12 that can reach it. Realizes UJ-3.

**Consequences (testable):**
- *(Stage 1)* The sqlite backend is reached → refusal. *(Built: `production.py:26-28`.)*
- *(Stage 1)* A local credential path is live in settings → refusal. This covers `ModelBackend` present in `AUTHENTICATION_BACKENDS`; a non-empty `ACCOUNT_LOGIN_METHODS`; `DJANGO_ADMIN_FORCE_ALLAUTH` not true; and `rest_framework.authtoken` installed or `TokenAuthentication` in the DRF defaults.
- *(Stage 2)* A credential-minting route is reachable in the resolved URL configuration → refusal. This covers `obtain_auth_token` (FR-15).
- *(Stage 2)* The local sign-in route is reachable in the resolved URL configuration → refusal. The synthetic-claims sign-in path of FR-19 is a credential path this product itself introduces, and it ships in every component (FR-19).
- *(Stage 1)* `OTEL_SDK_DISABLED` is true → refusal, because a deployed component that sets it has silently opted out of an immovable guarantee.
- *(Stage 1)* The JWKS trust anchor is not the configured IdP → refusal. The trust anchor is compared against the configured IdP issuer: a JWKS location that is not derived from that issuer is refused, which is what catches a component pointed at a locally generated development key. Unconditional, because the programmatic flow is immovable core and therefore present in all six valid combinations.
- *(Stage 2)* Unapplied migrations exist → refusal, for serving processes only, so that a process which serves traffic never runs against a schema it does not recognize. Evaluating it for every process would deadlock the release stage of FR-41, because `manage.py migrate` is the one action that clears the condition and would be forbidden by it.
- *(Stage 1)* The claims contract is unconfigured → refusal. No identity-key claim, no group-claim name, or no designated staff group means the component cannot decide who someone is or what they may do, and will not boot. Defaulting to conventional claim names was rejected: it fails closed, since nobody gets elevated, but presents as a mysterious permissions problem rather than a configuration error — expensive to diagnose once, and expensive per component across an estate.

**Out of Scope:**
- Detecting the development keypair *file* inside a built image. That is a packaging concern handled by the disposition rule (FR-37) and the gitignore rule (FR-20), and it is the narrower problem: the trust-anchor condition above catches a component pointed at a local JWKS location by environment variable, with no key file present at all.

#### FR-14: Conditional refusals

A deployed component refuses to start on two further conditions, each scoped to the feature that makes it meaningful. Realizes UJ-3.

**Consequences (testable):**
- Where the Redis cache feature is selected: an in-process cache backend is configured → refusal.
- Where background task processing is selected: eager task execution is enabled → refusal.
- In combinations where the corresponding feature is absent, neither condition is evaluated and startup proceeds.

#### FR-15: The refusal inspects the URL configuration, not settings alone

The credential-path refusal resolves the URL configuration and fails on a reachable token-minting route. Realizes UJ-3.

**Consequences (testable):**
- A component whose settings are correct but whose URL configuration still routes `obtain_auth_token` refuses to start.
- A test constructs exactly that state and asserts refusal.

#### FR-16: Refusals are tested as refusals

The suite asserts that deployed settings *refuse*, not merely that they start. Realizes UJ-3.

**Consequences (testable):**
- Each of the nine conditions has at least one test that configures the forbidden state and asserts `ImproperlyConfigured` is raised. Where a condition covers several distinct forbidden states — the settings-side credential paths are four — each state is tested separately.
- The settings-module escape route is covered by FR-12's test: deployed environment, local settings module, refusal asserted.
- Each stage-2 condition has a test that exercises it through a served request path, not only through `manage.py`.

#### FR-17: An allowlist test catches credential paths added later

The suite asserts that the component's authentication surface matches an approved set exactly, so a path introduced after this PRD fails the build until someone adds it deliberately. Realizes UJ-3.

**Consequences (testable):**
- `AUTHENTICATION_BACKENDS` and the DRF default authentication classes each match an approved allowlist exactly; an entry present but not listed fails the test.
- Resolved URL routes are checked against the allowlist only within the component's authentication surface — the route prefixes the component itself owns for authentication, admin login, and token issuance. Business routes a developer adds are out of its scope; an allowlist covering every route would break the build on the first feature anyone wrote, and would be deleted within a week.
- Adding a credential path requires editing the allowlist in the same change, which is the moment a human decides whether it belongs.

**Notes:** the nine refusal conditions are a denylist — refuse these known-bad states — and a denylist cannot by construction catch a path invented next year. This FR inverts that, which is the difference between FR-16 being a guarantee and being a habit.

**Notes on the list length:** the refusal contract is nine conditions, not the six the brief's addendum §6.3 records. Three were missing there. The development keypair was named in §1.6 as something the refusal must catch but absent from the §6.3 table — a gap between two sections both marked settled. The claims contract was never enumerated. And the local sign-in route is a credential path this product creates in §1.6 and then guards nowhere, the same omission as the keypair one layer further in. Each is resolved here as an explicit condition, on the addendum's own principle that every separate mechanism gets its own check; the addendum should be reconciled to nine when it is next touched.

That three of nine conditions were missing from a list its own source called settled is the argument for FR-17. A denylist maintained by review will always be one omission behind.

---

### 4.4 The Local Development Contract

**Priority: Phase-1 must-have.**

**Description:** The immovable core describes what a *deployed* component depends on. Requiring a developer to run all of it to change a line of business logic would make the accelerator slower than the fork it replaces, so a component runs on a developer's machine with no external service running. Each deployed dependency has a local substitution designed as such, not a convenience that happens to work. Stating the three inherited ones as a contract changes their status from defaults that happen to survive feature extraction into properties every combination is verified to have. Realizes UJ-2.

**There are five substitutions, not four.** Object storage was originally counted out of the set, which left the six combinations that select it with no local story at all — they could not satisfy the criterion that every valid combination runs with nothing installed. A filesystem-backed storage backend is the same shape as the other four: it preserves the storage API at every call site and exercises the same code paths, differing only in where bytes land.

The local identity path is not a shim. Synthetic claims drive the same mapper, and the local token is validated by the same Bearer authentication class. Only the signer's identity is local.

**Functional Requirements:**

#### FR-18: A component runs locally with nothing installed

Every valid combination starts, serves, and authenticates a persona on a machine with no database, cache, broker, or identity provider running. Realizes UJ-2.

**Consequences (testable):**
- sqlite is selected when neither `DATABASE_URL` nor `POSTGRES_DB` is set, preserving the ORM, migrations, and the full suite.
- An in-process cache backend is configured locally, preserving the cache API at every call site.
- Task execution is eager and propagating locally, preserving task bodies invoked synchronously.
- Where object storage is selected, a filesystem-backed storage backend is configured locally, preserving the storage API at every call site. What it does not exercise: bucket policy, presigned URLs, eventual consistency, multipart upload, and the network failure modes of a remote object store.
- The local personas of FR-19 stand in for the IdP, preserving the mapper, staff and superuser promotion, and per-authentication re-sync.
- The smoke check of FR-34 passes for all six valid combinations.

#### FR-19: Personas are seeded from declared claims

Local identities are declared as configuration — named personas with their groups and profile fields — and a development task materializes them as local accounts. Realizes UJ-2.

**Consequences (testable):**
- At least two personas with different group memberships exist, one of which carries the designated staff group.
- Each persona declares the identity-key claim FR-8 resolves users by, so a persona is the same user across sign-ins.
- Local sign-in constructs a synthetic claims payload and passes it to the mapper of FR-8; the mapper is unaware which path produced the claims.
- Changing a persona's declared groups and re-authenticating produces the corresponding membership change, including removal.
- The seeding task refuses to run in a deployed environment, raising the same `ImproperlyConfigured` as the refusal contract. It ships in every component because a developer who clones one needs it; it must never create a local account in a deployed environment.
- The sign-in route it depends on is refused at startup in a deployed component (FR-13, stage 2).

**Notes:** shipping this path and guarding it was chosen over stripping it from materialized output, because a stripped path cannot be tested by the component's own gate. The cost is that the product now creates a credential path of its own — which is why it is enumerated in the refusal contract rather than trusted to stay unused.

#### FR-20: The local programmatic flow validates for real

A development task mints a JWT signed by a locally generated keypair, and local settings point the JWKS location at that key, so the real Bearer authentication class verifies it. Realizes UJ-2.

**Consequences (testable):**
- Signature, `iss`, `aud`, and `exp` are all genuinely verified; no verification step is stubbed or skipped.
- The keypair is generated on demand by a development task into a gitignored path and is never committed.
- A tampered or expired locally signed token is rejected.

**Notes:** the never-commit rule carries more weight here than in an ordinary repository. A keypair committed to a template ships inside every component generated from it, so one published private key would be shared by every service the accelerator ever produces.

#### FR-21: Observability is not substituted locally

Local development runs the same observability code the deployed component runs; only the terminal export step is absent. Realizes UJ-2.

**Consequences (testable):**
- With no OTLP endpoint configured, the tracer provider is still installed, all instrumentors still instrument, spans are still created and ended, and `trace_id` and `span_id` still reach every log line. Spans are discarded at the processor.
- `OTEL_TRACES_EXPORTER=console` sends spans to stdout without other behavioural change.
- No configuration attaches a batch processor to an exporter pointed at an unreachable endpoint — that retries every cycle and floods stderr through every test run.

#### FR-22: The broker constraint is a statement about deployment only

Locally, all six valid combinations run with no broker. Realizes UJ-2.

**Consequences (testable):**
- Combinations that selected background task processing execute tasks eagerly with no broker present locally.
- Documentation states the constraint's scope explicitly, so it does not read as absolute.

#### FR-23: Nothing on the local start path reaches the network at boot

OIDC discovery and JWKS retrieval occur lazily on first use, never at import or at boot, so a component starts with no route to the IdP. Realizes UJ-2.

**Consequences (testable):**
- A unit test asserts that importing the settings and completing Django setup performs no OIDC discovery request.
- A unit test asserts that JWKS retrieval is not triggered by boot, only by the first Bearer request that needs it (FR-5).
- Persona seeding and development keypair generation are local operations: keypair generation is computation, seeding is a database write, and neither reaches a registry, the IdP, or a package index.

**Out of Scope:**
- Environment installation, which downloads packages by definition. The claim begins once the environment exists.
- A general no-network guarantee across the whole local session. Catching a template's CDN reference, or a network call added by future work, would need a network-denied smoke check; that was considered and set aside as disproportionate. This FR covers the two violators this PRD's own work introduces.

**Notes:** this is a requirement rather than an assumption because the failure is invisible to everyone who has network access. A developer on the corporate network reaches the IdP, so eager discovery works for them and for CI; the only person who finds out is a developer with no route, who then cannot work and has no idea why.

---

### 4.5 The Feature Model and Clean Extraction

**Priority: Phase-1 must-have.**

**Description:** Four selectable features, each with a package surface and a substantially larger non-package surface, all declared in one carrier. Removing background task processing touches ten files spanning settings, application code, observability wiring, and tests — which is why "the cost of excluding a feature" cannot be measured in packages. Unselected features are absent, not present-and-disabled: no dependency in the manifest, no entry in the installed-app list, no orphaned template, no skipped test. Realizes UJ-1, UJ-3.

The hardest part is what is left behind. Removing MFA during the audit orphaned two template overrides that no import graph, linter, or dependency analyzer would flag; only the coverage gate caught them, by reporting zero percent. Every future feature extraction will produce the same class of residue across templates, static assets, and settings fragments, so that detection property has to survive into the harness.

**Functional Requirements:**

#### FR-24: Three selectable features, declared in one carrier

A lead developer can select any subset of background task processing, Redis cache, and object storage. Every feature's surface is declared in a single machine-readable artifact with a named location, which is the only place a feature's extent is defined. Realizes UJ-1.

**Consequences (testable):**
- The carrier declares, per feature: its package surface, its non-package surface (settings fragments, application modules, observability wiring, templates, static assets, tests), its constraints, and the presets that pre-select it.
- The carrier has a single declared location and format, in the same way the mapper has one at `src/config/authorization/`. Nothing infers a feature's extent from naming conventions or directory layout.
- Selecting a feature produces every element of its declared surface; omitting it produces none.
- FR-28, FR-29, FR-30 and FR-37 all read the same carrier. A feature described in one of them and not the carrier is a defect the materializer surfaces rather than a discrepancy that persists.

**Notes:** without a named carrier, five requirements in this PRD depend on a declaration that has no file, no format, and no owner — while the mapper, a smaller thing, is pinned to an exact package. The carrier is what makes clean extraction specifiable rather than aspirational, and FR-30 requires it to be authored once and shared with the eventual template.

#### FR-25: Object storage attaches an S3-compatible backend

Where selected, a component stores documents and blobs against an S3-compatible object store configured by environment variable. Realizes UJ-1.

**Consequences (testable):**
- The storage backend is configured through Django's storages configuration from environment variables alone; no bucket, endpoint, or credential is baked into the image.
- The packages are `django-storages` and `boto3`, both present on the approved channel. `boto3` already resolves into the environment as a transitive dependency of the mail package; `django-storages` does not, and no storage configuration or application code exists — this feature is greenfield, not a rewire.
- `[ASSUMPTION: the channel's `django-storages` build works against the pinned Django and Python. Its released version predates both and declares support for neither; support exists only on unreleased upstream. Compatibility is proven before the feature is committed to, and if it fails the answer is to correct the channel recipe under FR-49's exception discipline, never to drop the feature — most components will select it.]`
- User media is out of scope: avatars resolve from IdP profile metadata as remote URLs, so no media pipeline exists to build.
- Where the feature is absent, no storage configuration, dependency, or call site remains (FR-28).

#### FR-26: The broker constraint is enforced at selection

Background task processing without the Redis cache is refused at generation rather than emitted as a component that cannot start. Realizes UJ-1.

**Consequences (testable):**
- The combination space is six valid combinations, not eight.
- The materializer refuses the invalid pairing with a stated reason (FR-35).

#### FR-27: Presets pre-select without constraining

The three presets — *Minimal*, *Cached*, *Worker-enabled* — set a starting selection and remain fully editable. Realizes UJ-1. *(Renamed: with the interface mechanism core, "API-only" and "Full web app" no longer name distinguishable selections.)*

**Consequences (testable):**
- Every valid combination is reachable without using a preset.
- A selection such as *Minimal plus background task processing plus object storage* is accepted; presets do not act as a menu of permitted shapes.

#### FR-28: Excluded features leave nothing behind

No materialized combination contains a dependency, template, static asset, settings fragment, or test belonging to a feature it did not select. Realizes UJ-3.

**Consequences (testable):**
- For each of the six valid combinations, the dependency manifest contains no package from an unselected feature's package surface.
- No template or static asset unreachable from any view in the combination is present.
- No test module for an unselected feature is present — and no test is present-but-skipped in its place.

#### FR-29: The orphan-detection property survives into the harness

The coverage signal that catches incomplete feature removal is preserved in per-combination verification, across every residue category that signal can reach. Realizes UJ-3.

**Consequences (testable):**
- Coverage measurement includes templates in every combination's gate run.
- The coverage tracer core is pinned so template measurement is real: `COVERAGE_CORE` is set to the C trace core in every combination's environment. Python 3.12 and later default to a core without the dynamic file tracer templates require, so templates are discovered, never traced, and silently report zero — indistinguishable from a genuine orphan, which makes the signal SC-2 and CG-1 both rest on unreadable. A test asserts the setting is in force during a gate run rather than trusting it to be inherited.
- An orphaned template override introduced deliberately into a combination causes that combination's gate to fail.
- Static assets and settings fragments are covered too. The source audit named three residue categories — templates, static assets, and settings fragments — and coverage detects only the first. The other two are detected by checking materialized output against the FR-24 carrier: any path present that no selected feature claims is a defect.

**Notes:** the template orphans are the famous case because they were found the hard way, but they are one third of the class. A residue category with no detector is a category that ships.

---

### 4.6 The Verification Model

**Priority: Phase-1 must-have.** This is the harness, and the reason phase 1 does not end at the reference application.

**Description:** Two models are kept deliberately separate. **Selection** is individual features with declared constraints, freely combinable, with the generator refusing invalid combinations at the source. **Verification** is a set of combinations CI proves green — test fixtures, never a restriction on what may be selected. Presenting the presets as menu items was rejected because it would refuse legitimate requests. Realizes UJ-3.

Verification also has two levels, and only the second is a claim this product makes. A component's own pipeline answers "is *this* component sound." It does not answer "are all six combinations sound" — and left there, the first lead developer to order an untried combination is the one who discovers the defect.

In phase 2 the second level is the template's CI rendering all six. Phase 1 cannot do that, because there is no template. So phase 1 builds a materializer: a mechanism in this repository that produces the source of any valid combination from the reference application, so the six-combination claim is provable *before* the transition rather than after it. When FreeMarker arrives it replaces the materializer; the verification it feeds is unchanged. The ordering is not a convenience but a requirement of the brief's risk register (§1, §11).

**Functional Requirements:**

#### FR-30: The materializer produces any valid combination

A developer or CI job can materialize the complete source of any of the six valid combinations from the reference application. Realizes UJ-3.

**Consequences (testable):**
- Materializing a combination produces a self-contained source tree that its own gate can run against.
- The same selections produce the same output; materialization is deterministic.
- Materialized output for the all-features-selected combination is equivalent to the reference application.
- The declarations the materializer reads are authored once. The FR-24 carrier, the FR-31 fixture set, and the FR-37 disposition rule are single-authored artifacts, and the phase-2 template is derived from them rather than restating them. **What this does not buy is an ongoing cross-check.** The template is produced by copying this repository into a separate source tree and interleaving directives there, so from that moment the two drift and neither validates the other. The materializer's cost is bounded by single-authoring; its durability rests on the reference application and the template-repository consumer (§10) outliving the transition, not on the template consuming the carrier.
- The materializer excludes itself, the carrier, and the fixture set from its own output (FR-37).

**Notes:** this PRD does not choose the materializer's implementation. Several architectures satisfy every consequence above at materially different cost, and picking among them is architecture's work; what the PRD fixes is the shape of the inputs it reads, which makes the choice bounded rather than open-ended.

#### FR-31: The materializer carries a fixture set

Materialization supplies test values for every parameter the enterprise developer portal would supply. Realizes UJ-3.

**Consequences (testable):**
- The fixture set covers every parameterized value, including the component package name and the code-quality project key.
- A parameter added to the order surface without a corresponding fixture causes materialization to fail rather than emit a default.

#### FR-32: Every valid combination passes the full gate against PostgreSQL

All six valid combinations are materialized and put through tests, coverage at or above ninety percent including templates, strict type checking, lint, and build, against PostgreSQL. Realizes UJ-3.

**Consequences (testable):**
- CI declares a PostgreSQL service and sets the database URL for gate runs. No workflow does this today, so the suite has only ever run against the sqlite fallback and PostgreSQL — immovable core — has never been verified.
- A failure in any one combination fails the run; there is no partial pass.

#### FR-33: Every valid combination passes a local smoke check

All six valid combinations boot, return 200 from readiness, and authenticate a persona with no external service running. Realizes UJ-2, UJ-3.

**Consequences (testable):**
- The smoke check runs with no database, cache, broker, or identity provider available.
- Neither the database backend nor the authentication mode is treated as a feature toggle; they are properties of the environment a combination runs in, so the combination space stays at six.

#### FR-34: The materializer refuses invalid combinations

A request to materialize background task processing without the Redis cache fails with the reason. Realizes UJ-1.

**Consequences (testable):**
- The invalid pairing is refused before any source is produced.
- The refusal names the broker constraint rather than failing generically.

#### FR-35: Any bound on verification coverage is reported explicitly

If the verification set is ever narrower than the full valid combination space, the run states what was excluded. Realizes UJ-3.

**Consequences (testable):**
- The policy is exhaustive verification while the space stays small; past roughly thirty-two valid combinations it becomes all-pairs coverage plus unconditional verification of every preset.
- A run using a reduced set reports the reduction and the combinations not covered. A silently truncated verification set reads as full coverage and is worse than no claim.

#### FR-36: Materialized output carries the provenance stamp

Every materialized combination records the accelerator version and the order values that produced it. Realizes UJ-3.

**Consequences (testable):**
- The stamp is present in materialized output and populated with the materializer's version and selections in phase 1.
- The stamp's location and format are stable enough that an external process could enumerate components by version.

**Notes:** the stamp costs one templated value and buys the only question worth asking after an accelerator change — *which components predate it?* Without it that question has no answer, because a generated repository is otherwise indistinguishable from any other Django service. Acting on that answer is a non-goal (§5).

#### FR-37: The accelerator's own machinery does not reach a component

Materialized output excludes the accelerator's tooling and planning artifacts, and parameterizes what is correct for this repository but wrong for any other. Realizes UJ-1.

**Consequences (testable):**
- The disposition is a rule evaluated per path, not a list of directories. A path is included only if the carrier shows it claimed by the immovable core or by a feature the combination selected; it is parameterized if the carrier declares it parameterized; it is excluded otherwise.
- Unlisted paths default to excluded, so a file no declaration claims does not silently travel into every component. This is FR-17's lesson applied to materialization: a rule maintained as an enumeration is always one omission behind.
- Directory-level granularity is insufficient and must not be used. `src/config/`, `tests/`, `pixi.toml` and `pixi.lock` each contain both core and feature-owned content — `src/config/celery_app.py` exists today and must be absent from the four combinations without background task processing, and the dependency manifest differs in five of the six. A rule that keeps those paths wholesale produces six identical components and makes FR-2's entire testable surface unreachable.
- **Excluded, as accelerator machinery:** `_bmad/`, `_bmad-output/`, `.agents/`, `.bmad-loop/`, `.claude/`, and the materializer, the FR-24 carrier and the FR-31 fixture set themselves.
- **Parameterized:** `sonar-project.properties`, `README.md`, `CHANGELOG.md`, `LICENSE`, `pyproject.toml`, and `mkdocs.yml`. The component name is one parameter with several sites, not one file.
- **Not parameterized, and this is load-bearing:** the component package path `src/django_service/` is a **constant** in every component. Reusable apps (§4.10) import from it by that name, so renaming it per component would break every reusable app in every component that renamed it differently. It is the stable import surface, not a placeholder.
- **Split, not kept wholesale:** `.github/` contains both the component's own pipeline and the accelerator's six-combination harness, release, and code-quality workflows; only the component's own pipeline travels. `docs/` splits the same way and already has a stated rule: what describes how to work on any component travels with it; what describes the accelerator does not.
- A materialized combination does not report code quality into the accelerator's own project — the hardcoded project key at `sonar-project.properties:6` is parameterized. Shipped unparameterized, nothing fails and the metrics merge silently.
- The `COVERAGE_CORE` setting of FR-29 travels with every combination, since the orphan signal is worthless without it.

**Notes:** the source addendum's strip/parameterize/keep table describes *this repository* — which of its directories belong to the accelerator and which to a component. That is a different question from which paths belong in a *particular combination*, and importing it unchanged produced a requirement that contradicted three others.

---

### 4.7 The Deployment Interface

**Priority: Phase-1 must-have**, except FR-44 which is **Next**.

**Description:** Deployment configuration lives in a separate repository outside this team's control. This PRD specifies the contract the component presents to it and never its contents. The process model varies by combination, so the component declares it rather than letting the deployment repository guess. Realizes UJ-1, UJ-3.

**Functional Requirements:**

#### FR-38: Configuration is exclusively environmental

A deployed component reads all configuration from environment variables, with no configuration file baked into the image. Realizes UJ-1.

**Consequences (testable):**
- No configuration file is present in the built image.
- The component starts from environment variables alone.

#### FR-39: The component runs as an arbitrary non-root user

A deployed component starts under a UID assigned by the platform and writes to no fixed path. Realizes UJ-1.

**Consequences (testable):**
- Startup succeeds under an arbitrary non-root UID with a read-only root filesystem. The component declares **no** writable path beyond a temporary directory, and this is asserted rather than assumed: static files are collected at build and served by the application, user media is a non-goal, logs go to the event stream, and sessions are database-backed, so nothing in a running component writes to disk.

#### FR-40: The process model is declared per combination

Each combination declares which process types it runs and their commands. Realizes UJ-1.

**Consequences (testable):**
- `web` is present in all six, served by gunicorn with the uvicorn worker class.
- `worker` and `beat` are present in exactly the combinations that selected background task processing.
- The declaration states that `beat` runs as exactly one replica — its schedule lives in PostgreSQL, which makes the process replaceable but not duplicable; two would produce duplicate dispatches.
- The declaration also states that `beat` must be replaced by stopping the old process before starting the new one. A default rolling update starts the replacement first, producing exactly the two-replica window the previous consequence forbids — so a replica count declared without a replacement strategy states a constraint the deployment repository would violate by default.

#### FR-41: Migrations are a release-stage step, enforced by refusal

A component never migrates itself at startup, and refuses to start against a schema it does not recognize. Realizes UJ-3.

**Consequences (testable):**
- No entrypoint runs migrations; running them there would race across replicas and collapse the boundary between the release and run stages.
- Unapplied migrations raise `ImproperlyConfigured` at the startup of a serving process, with management commands exempt (FR-13, stage 2).
- Documentation states that the deployment pipeline runs migration before new pods begin serving.

#### FR-42: Two asymmetric health endpoints

A component exposes a liveness endpoint and a readiness endpoint with deliberately different semantics. No health route exists today, so all of this is to be built. Realizes UJ-3.

**Consequences (testable):**
- Liveness checks nothing external: the process responds, or it does not. A liveness probe that queries the database converts a brief database outage into a crash loop — every replica fails, the platform kills them all, and they restart into the same unreachable database.
- Readiness checks that the database answers, and returns non-200 when it does not. Readiness failing during a database outage is correct and recoverable.
- Readiness does not re-check migrations. Startup answered that question once and permanently, and during a rolling deploy an older replica may legitimately run against a schema newer than its code — which is what backwards-compatible migrations are for and must not read as unready.
- Readiness returns non-200 from process start until the first successful database contact, so a process that has booted but cannot yet serve is never reported ready.

#### FR-43: Shutdown drains in a defined order

On `SIGTERM` a web process reports unready, stops accepting connections, finishes in-flight requests, and exits; a worker finishes its current task and declines new ones. Realizes UJ-3.

**Consequences (testable):**
- Readiness flips before the drain begins, so traffic stops arriving before in-flight work is finished.
- The component owns the ordering; the grace period is a deployment-repository setting. `[ASSUMPTION: the platform's termination grace period exceeds the longest expected drain; this PRD states the ordering requirement and leaves the value to the deployment repository.]`

#### FR-44: Session pruning is a scheduled admin process

Expired session rows are pruned by a one-off management process the platform schedules. Realizes UJ-3.

**Consequences (testable):**
- Sessions are database-backed in every combination, with the session engine set explicitly rather than left to the framework default, so session behaviour never varies by toggle.
- Pruning is documented as a scheduled admin process, deliberately not as a scheduled background task — background task processing exists in only two of the six combinations, and a component whose session table grew without bound in the other four would make session hygiene a property of an unrelated toggle.

**Notes:** the source addendum §5.3 originally inverted this arithmetic, reading "8 of the 12" and "the other 4"; it has since been corrected to match. Background tasks require the Redis cache, so they are present only in the `on/on` pairing: one of three valid pairings, times two UI states, times two object-storage states — four combinations. The correction strengthens the requirement, since two thirds of the space is affected rather than one third.

**Priority note:** setting the session engine explicitly is phase-1 must-have; scheduling the pruning process is **Next**, because the schedule lives in the deployment repository.

#### FR-45: Trace export is environmental and drops rather than retries

OTLP export is controlled by environment; with no collector configured, spans are discarded rather than retried. Realizes UJ-2.

**Consequences (testable):**
- Export is enabled only when the OTLP endpoint or its traces-specific variant is set.
- With neither set, no span processor is attached and spans end without export.
- The export path itself is exercised in the gate: at least one test drives a batch span processor against an OTLP exporter end to end — serialization, transport, and batch behaviour — against a collector stub. Exporter *selection* is comprehensively covered today, but the branch that actually exports runs only when an endpoint is configured, which local development never does, so without this the one path that carries telemetry off the component is verified nowhere.

---

### 4.8 Observability

**Priority: Phase-1 must-have.** Largely satisfied today; this group states what must not regress and what must be added.

**Description:** Correlated logs and distributed traces are core, and no feature selection removes them. This is the one capability a developer cannot accidentally work without, because it is not substituted locally at all. Realizes UJ-2, UJ-3.

**Functional Requirements:**

#### FR-46: Correlated structured logging

Every component writes a JSON event stream to stdout in which log lines carry the request correlation ID, trace ID, and span ID. Realizes UJ-3.

**Consequences (testable):**
- The component never manages log files or rotation.
- Correlation identifiers are present on log lines emitted during a request in all six combinations.
- Where background task processing is selected, correlation propagates into task execution.

#### FR-47: ASGI request tracing

Requests served over ASGI produce spans. Realizes UJ-3.

**Consequences (testable):**
- The ASGI instrumentor is present and active in all six combinations; without it, ASGI requests produce no spans at all.

#### FR-48: Degradation is visible

Where the Redis cache feature is selected, swallowed cache failures become log events. Realizes UJ-3.

**Consequences (testable):**
- Cache exceptions continue to be ignored so that a cache outage degrades a component rather than stopping it — that is the whole reason a cache is not a database.
- Every swallowed failure emits a log event correlated with the request and trace identifiers. The objection was never that the cache degrades; it was that it degraded invisibly in a component whose telemetry is immovable.

---

### 4.9 Supply Chain and Dependency Policy

**Priority: Phase-1 must-have.**

**Description:** Every dependency resolves from the approved channel. Rationale lives inside the configuration it constrains, so it cannot drift from it. As of 2026-08-14 the product has no supply-chain exceptions — the one that existed cleared upstream — which turns "a single audited supply chain" from a claim with an asterisk into a plain one, and makes the empty package-index block itself worth asserting. Realizes UJ-3.

**Functional Requirements:**

#### FR-49: Single audited channel with recorded exceptions

Every dependency in every combination resolves from the approved channel, and any exception is recorded at the point of declaration with its reason and its exit condition. Realizes UJ-3.

**Consequences (testable):**
- The dependency manifest carries the reasoning for its own non-obvious lines.
- Zero exceptions. The single historical exception — `django-celery-beat` from the package index, because the channel recipe transcribed an upstream version cap without its environment marker, making the cap unconditional and irreconcilable with the OpenTelemetry API's own requirement — is resolved: the corrected build is on the channel with the cap removed, and the dependency moves out of the package-index block. Confirmed 2026-08-14.
- A test asserts that **no third-party package resolves from the package index**. The block is not empty and cannot be: it carries the component's own editable path install, which is how the source tree reaches the environment rather than a supply-chain exception. Anything else appearing there fails the build, so a future exception has to be added deliberately rather than accumulating.
- Dependencies are pinned in a lock file, and no component relies on system packages.

#### FR-50: Channel availability is checked before a feature is committed to

A new selectable feature is not accepted until its dependencies are confirmed present on the approved channel. Realizes UJ-3.

**Consequences (testable):**
- Object storage was the first test of this rule and it half held. The storage and cloud-SDK packages are both available, as are the JWT and cryptography packages the authentication rewire needs — but availability turned out to be the weaker half of the question. The storage package is present and its released version declares support for neither the pinned Django nor the pinned Python (FR-25).
- **Availability is not fitness, and the rule now tests both.** A dependency is confirmed present on the channel *and* confirmed to work against the pinned runtime before a feature is committed to. Checking only presence is how a feature gets committed to on the strength of a package that cannot run.
- A proposed feature whose dependencies are absent from the channel forces an explicit supply-chain exception decision rather than a silent addition.

---

### 4.10 The Extension Model

**Priority: Phase-1 must-have.** None of it exists; the tenant space, the contribution mechanism and the compatibility check are all to be built.

**Description:** A component is not a renamed copy of the base with business logic poured into it. The base keeps its name and its shape, and the work a team actually came to do arrives *alongside* it as Django applications. An application that turns out to be useful twice stops being local: it is published to the approved channel and adopted by other components as an ordinary dependency. Realizes UJ-1, UJ-2.

This is the difference between an accelerator that produces independent forks and a platform whose components share code. It is also what makes the base package name a constant rather than a parameter (FR-37): an application that imports from the base only works if the base is called the same thing everywhere it is adopted.

**Functional Requirements:**

#### FR-51: The base package is a stable import surface

The component's base package presents a declared surface that reusable apps may depend on, and changes to it are treated as breaking. Realizes UJ-1.

**Consequences (testable):**
- The base package name is identical in every component and is never parameterized (FR-37).
- The surface a reusable app may depend on is declared explicitly; anything else inside the base is internal and may change freely.
- The declared surface is present in all six valid combinations. No feature selection may remove part of it, or an app would import successfully in some components and fail in others.
- Moving a module within the declared surface, changing the user model, or renaming a guaranteed setting is a breaking change and is versioned as one.

#### FR-52: A component extends through a declared tenant space

A component has one declared location for the applications it owns, and the accelerator neither supplies nor judges their contents. Realizes UJ-1.

**Consequences (testable):**
- The tenant space has a single declared location, named in the carrier (FR-24).
- The materializer neither prunes nor reports the tenant space: a path there is not an orphan (FR-29) and is never excluded as unclaimed (FR-37).
- A component with applications of its own passes the same gate as one without.

#### FR-53: A reusable app graduates without changing its import path

An application developed inside a component keeps its import path when it is published to the channel and adopted elsewhere. Realizes UJ-1.

**Consequences (testable):**
- The same application is importable by the same name in both residencies — while it lives in the tenant space, and once it is installed from the channel.
- Graduating an application requires no change to the installed-app list, imports, or migration references of any component that adopts it.
- Adoption is explicit: a manifest entry and a declaration in the component. Nothing self-registers on installation.

#### FR-54: A reusable app adds configuration and never changes it

An adopted application may introduce configuration a component did not have, and may not alter configuration that already exists. Realizes UJ-1.

**Consequences (testable):**
- Introducing new configuration succeeds; writing to configuration the component already defines raises `ImproperlyConfigured` at startup.
- Additions to ordered configuration append in adoption order, so composition is deterministic and no application can place itself ahead of the base or of another application.
- The configuration an application may contribute is a closed, declared set. Global defaults that would give an application authority over every request — request middleware, and the framework-wide authentication and permission defaults — are outside it, whether or not the component already sets them.
- An application contributing configuration that depends on a feature the combination did not select is refused at startup rather than silently doing nothing.

**Notes:** the closed set and the authentication allowlist of FR-17 are one declaration. Maintained apart, they disagree — and §4.3 already demonstrated what happens to a list kept in two places.

#### FR-55: A contributed backing service inherits the local development contract

Where an adopted application brings its own backing service, the substitutions of §4.4 extend to it without the application having to arrange it. Realizes UJ-2.

**Consequences (testable):**
- A component that adopts an application with its own database still starts, serves and authenticates a persona with nothing installed (FR-18).
- The refusals that guard the component's own database guard the contributed one identically: a deployed component whose contributed database has fallen back to the local substitution refuses to start (FR-13).
- Unapplied migrations on a contributed database refuse a serving process exactly as they do on the component's own (FR-41).
- Readiness reports a contributed backing service as required unless the component declares otherwise (FR-42).
- The component declares one release-stage migration step per database, so the deployment repository does not have to infer how many there are (FR-40).

#### FR-56: Base compatibility is declared and checked at adoption

A reusable app states which versions of the base it supports, and adopting it into an incompatible component fails the gate rather than failing in production. Realizes UJ-3.

**Consequences (testable):**
- The base exposes its surface version; an application declares the range it supports.
- The declaration lives somewhere both residencies of FR-53 can read, so the check behaves identically for an application in the tenant space and one installed from the channel.
- Adopting an application outside the supported range fails the component's gate.

---

## 5. Non-Goals (Explicit)

- **The FreeMarker generator engine.** This product supplies what the engine consumes; the engine is someone else's.
- **The phase-2 template conversion itself.** Out of scope for this PRD by explicit decision. Requirements here that serve it — the provenance stamp, the strip/parameterize/keep disposition, the fixture set — exist because the harness must precede the transition, not because this PRD delivers it.
- **Deployment configuration.** It lives in a separate repository outside this team's control. The contract to it is in scope; its contents are not.
- **IdP configuration.** Realms, clients, and group definitions are administered elsewhere. A component declares only what it reads.
- **Multi-factor authentication.** Enforced at the IdP, never in the component.
- **User media handling.** Avatars resolve from IdP profile metadata as remote URLs.
- **Propagating an accelerator change into components already generated.** The provenance stamp makes those components enumerable, which is the precondition for any mechanism at all. Turning that into pull requests — the shape `cruft` and `copier update` take for their own template systems — is a second product with its own lifecycle.

  This one deserves stating plainly rather than filing as scope. Generation produces an independent repository, and **a repository someone else now owns and edits is a fork by any honest definition** — which is the thing this product exists to stop, reappearing one level up. Naming the precondition is not the same as having solved it, and a reader who takes the Vision at face value would believe more has been solved than has.
- **A local identity-provider container.** The highest-fidelity local option, rejected because it reintroduces exactly the per-machine service dependency the substitutions exist to remove. It remains the right answer for deliberate work on the authentication layer itself, as an optional path rather than a requirement.
- **A break-glass account in a deployed component.** Every credential path is delegated to the IdP; see §11.
- **Becoming a general-purpose Django starter.** The platform assumptions in §2.2 are load-bearing throughout.
- **Carrying the platform's guarantees into a template repository.** Consuming this repository through the code host's create-from-template facility produces a fork of the base, not a component: it copies the accelerator's own machinery, performs no parameterization, selects no features, and is taken from whatever is on the default branch rather than a released version. It is a legitimate way to start work and it is outside every guarantee this PRD makes. A repository that must carry those guarantees is generated, not templated.

## 6. MVP Scope

### 6.1 In Scope

- The reference application: the immovable core and the three selectable features, all present and exercised (§4.1, §4.5).
- The authentication rewire — interactive and programmatic flows against the IdP, the shared mapper, per-authentication re-sync, and removal of the four bypassing credential paths (§4.2).
- The refusal contract: nine conditions, evaluated at two defined points independently of which settings module loaded, tested as refusals, and backed by an allowlist test over the authentication surface (§4.3).
- The local development contract: five substitutions, seeded personas, the locally signed development token, and unsubstituted observability (§4.4).
- Grouping code, dependencies, settings, templates, and tests so a feature can be excluded cleanly, with orphan detection preserved (§4.5).
- The materializer and the two verification levels: six combinations gated against PostgreSQL and smoke-checked locally (§4.6).
- The deployment interface: environmental configuration, arbitrary UID, declared process model, release-stage migrations, two health endpoints, drain ordering, explicit session engine, environmental trace export (§4.7).
- Observability hardening: correlated logs, ASGI tracing, conditional instrumentors, visible cache degradation (§4.8).
- Supply-chain policy and the channel check for new features (§4.9).
- The extension model: the base's declared import surface, the tenant space, additive contribution, and the compatibility check (§4.10).

### 6.2 Out of Scope for MVP

- **FreeMarker template conversion** — the phase-2 boundary. Deferred to its own PRD; the harness this PRD delivers is its precondition.
- **Scheduling the session-pruning process** — the schedule lives in the deployment repository. The component-side requirement (explicit session engine, documented admin process) is in scope.
- **Concrete non-functional numbers** — probe timings, startup budget, termination grace, resource limits, JWKS cache TTL. Architecture pins these against the real platform; §8 states the behavioural contract without them.
- **Propagation to existing components** — see §5. `[NOTE FOR PM]` This one is emotionally load-bearing: the Vision's second paragraph describes a base that "stops being a starting point and becomes a living one," and without propagation that stays aspirational. Worth revisiting once the accelerator has produced enough components for the gap to bite.
- **Presets beyond the three named** — *Minimal*, *Cached*, *Worker-enabled*. Adding more is cheap and constrains nothing; there is no evidence yet for which.
- **All-pairs verification** — the policy exists (FR-35) but exhaustive verification of six is correct until the space grows past roughly thirty-two.

## 7. Success Criteria

Success here is stated as verifiable criteria, not outcome metrics. Adoption and cycle-time numbers — how many components are ordered, how long until the first business-logic commit — depend on enterprise developer portal telemetry outside this product's control, so stating them here would create targets nobody in this repository can move or measure. The criteria below are binary and machine-checked, and the harness of §4.6 is what checks them.

**Primary**

- **SC-1: Every valid combination builds and passes.** All six are materialized and put through the full gate — tests, coverage at or above ninety percent including templates, strict type checking, lint, build — against PostgreSQL rather than the local sqlite substitution, and all six pass. Validates FR-30, FR-31, FR-32, FR-35.
- **SC-2: Excluded features leave nothing behind.** No orphaned dependency, template, static asset, settings fragment, or test in any materialized combination. Validates FR-24, FR-28, FR-29.
- **SC-3: A component is deployable unmodified.** Containerized by CI and started on the target platform with no source edits, with its declared process model, health endpoints, and drain behaviour intact. Validates FR-38 through FR-45.
- **SC-4: A component runs locally with nothing else installed.** Every valid combination starts, serves, and authenticates a persona on a machine with no database, cache, broker, or identity provider running. Validates FR-18, FR-19, FR-20, FR-33.

**Secondary**

- **SC-5: No deployed component authenticates outside the IdP.** Each of the nine refusal conditions has a test that configures the forbidden state and asserts refusal, and the authentication surface matches its allowlist exactly. Stated as *outside the IdP* rather than *bypasses the IdP* because three of the nine conditions are not bypasses (§4.3). Validates FR-12, FR-13, FR-14, FR-15, FR-16, FR-17.
- **SC-6: The IdP authentication path works.** A real IdP identity authenticates through the interactive flow and through the programmatic flow, and the mapper produces the correct authorization state in both: memberships the claims assert added, memberships they no longer assert removed, staff and superuser status set from their designated groups, and the same identity resolving to the same user across both flows and in either order. Validates FR-4 through FR-11.
- **SC-7: The immovable core functions in every combination.** Each of the six materialized combinations serves an API described by its generated schema, renders the admin, emits correlated structured logs carrying request and trace identifiers, and produces spans for ASGI requests. Validates FR-1, FR-2, FR-3, FR-46, FR-47, FR-48.

**What SC-6 and SC-7 add.** SC-1 through SC-5 verify only negatives and shapes — that combinations build, that nothing is left behind, that nothing authenticates outside the IdP. All five could pass on a component whose IdP integration rejects every real token and whose telemetry emits nothing, because no criterion asked whether the core *works*. These two close that, and between them bring the twenty-five requirements no criterion previously validated into scope.

**Criteria that must not be gamed**

Each names a way a primary criterion could be made to pass while the product got worse, and forbids it.

- **CG-1: Do not reach the coverage threshold by narrowing what is measured.** Coverage includes templates precisely because that is the only signal that catches an orphan. Excluding files, adding coverage pragmas to unreached code, or dropping template measurement makes SC-1 pass and destroys SC-2. Counterbalances SC-1.
- **CG-2: Do not shrink the verification set to keep CI cheap.** A template change costing six materialize-and-gate runs is the price of SC-1 meaning what it says. Any reduction must be reported (FR-35), never silent. Counterbalances SC-1.
- **CG-3: Do not soften a refusal into a warning.** A refusal that logs and continues makes deployment smoother and puts local credentials into production. Counterbalances SC-3 and SC-5.
- **CG-4: Do not substitute a capability that could run locally as deployed.** A substitution is warranted only where the deployed dependency genuinely cannot be present on a developer's machine without becoming the service dependency this contract exists to remove. Each one widens the parity gap the product already trades knowingly, and each must be guarded by a refusal. The count is not the constraint — the principle is; object storage was added as a fifth on that principle (§4.4), not to make SC-4 cheaper to pass. Counterbalances SC-4.

## 8. Cross-Cutting Non-Functional Requirements

- **NFR-1 — Startup fails fast, and cheaply.** Any misconfiguration in the refusal contract surfaces at boot as `ImproperlyConfigured`, never as scattered runtime errors. The nine checks are settings and URL-configuration inspection with no network call and no query beyond the migration state, so their cost is irrelevant to startup time. `[ASSUMPTION: a platform startup-time budget exists; architecture confirms the value. The requirement above does not depend on knowing it.]`
- **NFR-2 — Liveness touches nothing external.** Stated as an NFR as well as FR-42 because it is a system-wide invariant that any future health work must preserve.
- **NFR-3 — Statelessness.** Components share nothing through local disk or process memory across replicas. Sessions are database-backed in every combination.
- **NFR-4 — Strict typing and lint are gate conditions, not advisories.** No combination passes with type or lint errors.
- **NFR-5 — Determinism.** Materialization and dependency resolution are reproducible: the same selections and the same lock file produce the same component.
- **NFR-6 — Telemetry overhead is measured, not assumed.** Instrumentation is always on and never conditionally disabled to gain performance. The overhead of always-on instrumentation with export disabled is measured once against the reference application and recorded alongside the observability documentation, so the claim that it is acceptable rests on a measurement rather than on repetition. Re-measured only when the instrumentation set changes.
- **NFR-7 — Secrets never live in source.** No credential, key, or token is committed; the development keypair is generated on demand into a gitignored path (FR-20).
- **NFR-8 — Documentation travels with what it describes.** Component-facing documentation is materialized with the component; accelerator-facing documentation is not.

## 9. Constraints and Guardrails

**Security**

- The IdP is the only credential authority in a deployed component. Local credential paths exist only where the refusals do not apply.
- Authorization is decided in exactly one place (FR-8). Divergence between the interactive and programmatic flows is the default outcome of independent implementation, not an unlikely one, because the natural place to put mapping is wherever the developer happens to be working.
- Revocation at the IdP must reach the component (FR-9). Mapping only at account creation means revoked access never propagates.
- No network surface exists beneath the component's URL routing. A protocol handled below the router is invisible to the authentication allowlist of FR-17, because it is not a route — so it cannot be reasoned about by any mechanism in §4.3. Any such surface is a designed feature with its own authentication story and its own entry in the carrier, never an inherited one.
- An adopted application cannot acquire authority over requests it does not own (FR-54).

**Supply chain**

- One audited channel, currently with zero exceptions. Any future exception is documented at its point of declaration with its reason and its exit condition — and the previous one cleared upstream, which shows an exit condition is a real expectation rather than a formality.
- No feature is committed to before its dependencies are confirmed available.

**Cost**

- Verification cost scales with the combination space, and that is accepted while the space is small. The policy at roughly thirty-two combinations (FR-35) exists so the cost has a planned answer rather than an improvised one.

## 10. Integration and Dependencies

- **Enterprise developer portal** — supplies the order: component name and feature selections. This product supplies what the portal's generator consumes and the fixture set that mirrors the order surface (FR-31). A parameter added to the order form without a fixture breaks materialization by design.
- **Identity provider** — OpenID Connect issuer for both flows. The component reads the claims contract from configuration and never configures the IdP.
- **Deployment repository** — runs the component. Consumes the declared process model, health endpoints, drain ordering, and the release-stage migration step.
- **Approved package channel** — resolves every dependency, with no exceptions as of 2026-08-14 (FR-49).
- **Code-quality platform** — receives per-component metrics, so the project key must be parameterized (FR-37).
- **CI provider** — runs both verification levels and must supply a PostgreSQL service, which no workflow declares today.
- **Code host, as a template repository** — consumes this repository directly to start a fork of the base (§5). It performs no generation, so nothing in this PRD's contract applies to what it produces.
- **Reusable applications** — resolved from the same approved channel as every other dependency (§4.10). An application must reach the channel before a component may depend on it, which makes publishing one a supply-chain obligation rather than a convenience.

## 11. Risk and Mitigations

- **One check carries the whole guarantee.** The separation between a local component and a deployed one rests entirely on the startup refusal. A credential path it fails to inspect, a trust anchor it fails to validate, or a settings module that never reaches it puts local authentication into a deployed environment — a vulnerability this product would have created deliberately rather than inherited. *Mitigation:* four requirements, each closing a different way the guarantee could fail. FR-12 moves the evaluation out of the settings module it is meant to guard, so it cannot be skipped by not being loaded. FR-15 inspects the URL configuration rather than settings alone. FR-16 asserts refusal rather than successful start. FR-17 replaces the denylist with an allowlist, so a path added later fails the build. *Demonstrated:* three of the nine conditions were missing from a list the source material called settled (§4.3, FR-17).
- **No break-glass account (accepted).** An IdP outage locks everyone out of the admin, including its administrators. Accepted in exchange for a single auditable authentication path. The local personas are not a mitigation; they exist only where the refusals do not apply.
- **Dev/prod parity is deliberately traded (accepted).** Factor 10 exists to discourage exactly what §4.4 does, with sqlite against PostgreSQL as its stock example, and a product named for fifteen factors should say so rather than let a reader discover it. The trade buys a component that runs the moment it is generated, and it is bounded: the gate runs against PostgreSQL, the authorization code paths are shared rather than mocked, and observability is not substituted at all.
- **Local development proves less than running suggests.** sqlite accepts schemas PostgreSQL rejects; eager execution never exercises delivery, retries, or serialization; synthetic claims never exercise JWKS retrieval or key rotation. The gate covers all three, so this is a slower feedback loop rather than an unverified product — but a component running locally is not evidence it will run deployed.
- **Phase 2 blinds the gate until the harness exists.** *Mitigation:* this PRD's ordering. The materializer (§4.6) exists so the six-combination claim is provable before the transition, and the transition must not happen first.
- **Orphan detection depends on coverage.** The zero-percent signal is the only thing that catches incomplete feature removal. *Mitigation:* FR-29 and CG-1.
- **The OTLP export path is never exercised locally.** Protobuf serialization, HTTP transport, batch behaviour, retry and timeout run only when an endpoint is configured. *Mitigation:* FR-45 puts the export path in the gate and keeps the local default at discard-at-the-processor rather than failing at the socket.
- **Channel availability constrains the feature model.** Every future feature must clear FR-50 before it is committed to.

## 12. Factor Coverage

The product's name commits it to fifteen factors, so each is accounted for. *Satisfied* means the mechanism exists in the repository today.

| # | Factor | How it is accounted for | Status |
|---|---|---|---|
| 1 | Codebase | One repository per component, in version control from generation | Satisfied |
| 2 | Dependencies | Declared and lock-pinned, resolved from the approved channel with no exceptions; no system packages (FR-49) | Satisfied. The repository change moving `django-celery-beat` off the package index has landed, and a later build removed the test dependency it was carrying into the runtime environment |
| 3 | Config | Environment-only; no configuration file in the image (FR-38) | Satisfied |
| 4 | Backing services | PostgreSQL, cache, and object storage attach by environment variable. The §4.4 substitutions are the same contract pointed at a different endpoint | Partly — **object storage does not exist**; `django-storages` and `boto3` are absent from the manifest (FR-25) |
| 5 | Build, release, run | CI builds and containerizes; the deployment repository runs. Migrations are a release-stage step guarded by a refusal (FR-41) | Decided, **not implemented** |
| 6 | Processes | Stateless; sessions database-backed in every combination, engine set explicitly; pruning is a scheduled admin process (FR-44) | Decided, **engine not yet set explicitly** |
| 7 | Port binding | The server binds a port directly; no web server injected at runtime | Satisfied |
| 8 | Concurrency | Process model declared per combination; beat as exactly one replica (FR-40) | Satisfied, declared |
| 9 | Disposability | Fail-fast startup across nine refusal conditions, evaluated at two defined points independently of the settings module (FR-12, FR-13, FR-14); shutdown reports unready then drains (FR-43) | Decided, **not implemented** |
| 10 | Dev/prod parity | **Deliberately traded** — §4.4 varies backing services between local and deployed. Reasoning and mitigations in §11 | Traded, knowingly |
| 11 | Logs | JSON event stream to stdout; no files, no rotation (FR-46) | Satisfied |
| 12 | Admin processes | Management commands run as one-off processes; superuser creation retired as the deployed bootstrap (FR-11) | Satisfied |
| 13 | API first | DRF with drf-spectacular, immovable (FR-1) | Satisfied |
| 14 | Telemetry | structlog and OpenTelemetry, immovable, unsubstituted locally (FR-21, FR-46, FR-47) | Satisfied |
| 15 | Authentication and authorization | IdP-only in deployed components, guarded by refusal (§4.2, §4.3) | Designed, **not implemented** |

## 13. Open Questions

Two questions remain, each with an owner and the condition that would let it be answered. Neither blocks architecture from starting; each blocks a specific decision inside it. A third — whether the materializer and the eventual template share their declarations — was closed during review rather than deferred: FR-30 now requires single-authoring, because leaving it open left the materializer's cost unbounded.

1. **What is the accepted revocation latency?** FR-9 re-syncs authorization on every authentication, so an established session retains its authorization until its next one. Whether that window is acceptable depends on the platform's session lifetime policy. *Owner:* platform group. *Revisit when:* the session policy is known — if the window is judged too wide, the answer is a shorter session lifetime rather than a change to the mapper.
2. **How many writable paths does the component actually need?** FR-39 assumes none, or one temporary directory. *Owner:* architecture, against the platform's security context constraints. *Revisit when:* the first containerized deployment is attempted; a wrong assumption surfaces immediately and cheaply.

## 14. Assumptions Index

Every `[ASSUMPTION]` still live in this document, each with an owner and the condition that would resolve it. Five assumptions present in the first draft were resolved during review and are now requirements rather than assumptions: the settings-module detection mechanism (FR-12), the enumerability of the credential surface (FR-17), the claims-contract default (FR-13), the no-network-at-boot property (FR-23), and the telemetry-overhead claim (NFR-6, now measured rather than assumed).

Two more were resolved by architecture and are struck below rather than renumbered. The **JWKS cache TTL and rotation trigger** turned out not to need the identity provider's policy at all: caching keys by key identifier and refetching once on an unrecognized one survives rotation without a restart, which leaves the lifetime a backstop for key *removal* where any sane value works. **Writable paths** were closed from the component's side rather than measured against the platform.

1. **§4.5 / FR-25 — the channel's object-storage build works against the pinned Django and Python.** Its released version predates both and declares support for neither. *Owner:* architecture. *Revisit when:* compatibility is proven, before the feature is committed to. If it fails, the answer is to correct the channel recipe under FR-49's exception discipline — the feature is not droppable.
2. **§4.2 / FR-9 — Session lifetime is short enough that per-authentication re-sync is the accepted revocation latency.** *Owner:* platform group. *Revisit when:* the session policy is known. *(See Open Question 1 — if the window is too wide, the fix is a shorter session lifetime, not a change to the mapper.)*
3. *(Resolved.)* **§4.7 / FR-39 — writable paths.** Architecture closed this from the component's side rather than measuring it against the platform: static files are collected at build and served by the application, media is a non-goal, logs go to the event stream, and sessions are database-backed, so nothing writes to disk. The component asserts zero writable paths beyond a temporary directory and the harness verifies it. Open Question 2 is closed with it.
4. **§4.7 / FR-43 — The platform's termination grace period exceeds the longest expected drain.** The component owns the drain ordering; the value is a deployment-repository setting. *Owner:* deployment repository. *Revisit when:* drain duration is observed under load.
5. **§8 / NFR-1 — A platform startup-time budget exists.** NFR-1's substantive requirement — that the nine refusal checks are cheap enough to be irrelevant to startup — does not depend on knowing the budget. *Owner:* architecture. *Revisit when:* the platform publishes one.
