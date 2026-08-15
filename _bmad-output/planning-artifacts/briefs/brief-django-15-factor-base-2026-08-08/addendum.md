---
title: "Addendum: django-15-factor-base Product Brief"
status: draft
created: 2026-08-09
updated: 2026-08-14
---

# Addendum

Depth captured during brief discovery that belongs to downstream documents — PRD, architecture, solution design — rather than to a two-page brief. Nothing here is decided beyond what the brief states; this is the supporting detail behind those decisions.

**Reading convention.** Present tense describes what is true in the repository today. `must` and `will` describe what the work has to deliver and is not yet built.

## 1. Authentication rewire — findings and target design

### 1.1 Credential paths that currently bypass the IdP

Three defaults survived the fork from `cookiecutter-django`. All three are verified in the source, not inferred.

The defect is not that these paths exist — §1.6 keeps every one of them available for local development. It is that they are **enabled by default and unguarded**, so a deployed component bypasses the IdP unless someone remembers to configure it not to. The remediation inverts that: available where they are configured on, refused at startup where they are not permitted.

| # | Location | Current state | Effect |
|---|---|---|---|
| 1 | `src/config/settings/base.py:274`, implemented at `src/django_service/users/admin.py:11` | `DJANGO_ADMIN_FORCE_ALLAUTH` defaults to `False` | `/admin/` serves Django's own username+password form via `ModelBackend`; the IdP is never involved |
| 2 | `src/config/settings/base.py` — `REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES`, plus `rest_framework.authtoken` in `INSTALLED_APPS` | `TokenAuthentication` enabled | Static, locally issued API tokens with no issuer, expiry, or claims |
| 3 | `src/config/settings/base.py:343` | `ACCOUNT_LOGIN_METHODS = {"username"}` | Local username/password login enabled in allauth |

Mitigating detail for #1: the remediation is already written. `users/admin.py` wraps `admin.site.login` with allauth's `secure_admin_login` — it is gated behind a flag that is off by default. Forcing admin through the IdP is a default flip, not new code.

### 1.2 Two authentication flows

These are distinct mechanisms and must not be conflated in design.

| Flow | Consumer | Mechanism | Dependency cost |
|---|---|---|---|
| Interactive | Django admin, server-rendered UI | Authorization Code + PKCE, redirect to IdP, session cookie | **None.** `allauth.socialaccount.providers.openid_connect` is present in the installed allauth distribution |
| Programmatic | DRF API clients, service-to-service | `Authorization: Bearer <JWT>`, validated against the IdP's JWKS endpoint | **New.** No JWT/JOSE library is currently installed |

DRF's `TokenAuthentication` cannot be adapted. It is hardwired to the `rest_framework.authtoken` `Token` model and resolves a random opaque key against the local database; it has no concept of issuer, signature, expiry, or claims. It must be replaced, and `rest_framework.authtoken` removed from `INSTALLED_APPS`.

### 1.3 Selected approach for the programmatic flow

The selected approach is PyJWT and `cryptography` behind a `rest_framework.authentication.BaseAuthentication` subclass that will fetch and cache the IdP JWKS, verify signature, `iss`, `aud`, and `exp`, and map claims onto a user.

Rejected alternatives:

- **`mozilla-django-oidc`** — ships a usable DRF authentication class, but also brings its own interactive OIDC stack, duplicating what allauth already does. Two OIDC frameworks in one component is a maintenance and correctness liability.
- **`djangorestframework-simplejwt`** — designed to *issue* local JWTs. Usable as an external verifier but works against its grain when the IdP is the sole issuer.
- **`django-oauth-toolkit`** — an authorization server. Substantial overkill when the IdP is external.
- **`allauth.headless`** — available in the installed distribution, but issues allauth's own session tokens rather than validating IdP-issued ones.

Channel check (resolved): both are on conda-forge — `pyjwt` 2.13.0 and `cryptography` 50.0.0. Note the rename from the PyPI name `PyJWT` to the conda package `pyjwt`.

### 1.4 Claims-to-authorization mapping

- The natural hook for the interactive flow is `SocialAccountAdapter` in `src/django_service/users/adapters.py`, which already overrides `populate_user()`.
- **`populate_user()` alone is insufficient.** It runs at account population, not on every authentication. Group mapping placed there means IdP-side revocation never reaches the component and permissions persist indefinitely. Sync must occur on every login.
- Both the interactive and programmatic flows must share one claims-to-groups mapper. Divergence produces a component whose API and admin disagree about a user's authorization.
- A designated IdP group must drive `is_staff` for admin access. `createsuperuser` will cease to be a usable bootstrap path — the first administrator signs in via the IdP and is promoted by group claim.

### 1.5 Consequences already applied

`PASSWORD_HASHERS` and `argon2-cffi` were removed from `base.py`: no deployed component issues or verifies a password, so it has no reason to prefer a hasher and Django's defaults stand. Note this removed the *dependency*, not local password authentication — that is the rewire described above, which remains outstanding. `AUTH_PASSWORD_VALIDATORS` was deliberately retained, and §1.6 gives it a permanent reason to stay: local accounts have passwords.

`src/config/settings/test.py:31` still overrides `PASSWORD_HASHERS` to `MD5PasswordHasher` for suite speed. That was a residual artifact when the target was IdP-only everywhere; under §1.6 it is correct and stays.

### 1.6 Local development posture

Deployed components authenticate exclusively against the IdP. Local development requires local users and local admins, because a developer must be able to work without a reachable IdP realm. This reverses the earlier position that no local authentication of any kind would exist; it does not soften the deployed posture.

**Enforcement is a startup refusal, not a default.** `src/config/settings/production.py:26-28` already establishes the pattern for the database — it raises `ImproperlyConfigured` when the sqlite fallback is reached rather than quietly preferring PostgreSQL. Local authentication must be guarded the same way: production settings inspect the credential surface and refuse to start when any local path is live.

The check must cover every path in the §1.1 table, since each is a separate mechanism:

| Path | What production must refuse |
|---|---|
| Local login backend | `ModelBackend` present in `AUTHENTICATION_BACKENDS` |
| allauth local login | a non-empty `ACCOUNT_LOGIN_METHODS` |
| Admin bypass | `DJANGO_ADMIN_FORCE_ALLAUTH` not true |
| Static API tokens | `rest_framework.authtoken` installed, or `TokenAuthentication` in the DRF defaults |

Two failure modes escape the refusal on its own, and therefore need explicit tests: a component deployed with `DJANGO_SETTINGS_MODULE` pointing at the local settings module never reaches the production checks at all; and a credential path added later is unguarded until someone extends the check. Tests must assert that production settings *refuse*, not merely that they start.

**Simulating claims locally.** Local sign-in constructs a synthetic claims payload — the developer's groups, email, and whatever else the mapper consumes — and passes it to the same claims-to-groups mapper the OIDC path uses. Nothing about the mapper is aware of which path produced the claims. This makes open item 2 (where the shared mapper lives) load-bearing rather than a tidiness concern: the local path is a third consumer of it.

What that exercises: the mapping itself, `is_staff` promotion by designated group, and re-sync on every login, including revocation when a developer's synthetic groups change. What it does not exercise: JWKS retrieval, signature verification, and issuer, audience, and expiry validation.

**The programmatic flow locally.** A development-only task mints a JWT signed by a local keypair, and local settings point the JWKS location at that key. The component then validates the token through the real `BaseAuthentication` subclass described in §1.3 — signature, `iss`, `aud`, and `exp` all genuinely checked. Only the identity of the signer is local; no verification step is stubbed or skipped. The local keypair is a development artifact and must never be present in, or reachable from, a deployed component.

Rejected for the programmatic flow:

- **`SessionAuthentication` locally** — trivial to add, but it leaves the Bearer authentication class unexercised until CI, on a component whose immovable core is API-first.
- **A local IdP container (Keycloak, dex)** — the highest fidelity available, and rejected for consistency: it reintroduces exactly the per-machine service dependency that the sqlite and in-memory-cache substitutions exist to remove. It remains the right answer for deliberate work on the authentication layer itself, as an optional path rather than a requirement.

## 2. Feature-to-surface matrix

The cost of excluding a feature is not measured in packages. Removing background task processing touches ten files spanning settings, application code, observability wiring, and tests.

| Feature | Packages | Non-package surface |
|---|---|---|
| Background task processing | `celery`, `django-celery-beat`, `django-timezone-field`, `python-crontab`, `cron-descriptor`, `opentelemetry-instrumentation-celery` | `config/celery_app.py`, `config/__init__.py`, `users/tasks.py`, `observability/telemetry.py`, all three settings modules, three test modules |
| Redis cache | `redis-py`, `hiredis`, `django-redis`, `opentelemetry-instrumentation-redis` | `CACHES` configuration |
| Server-rendered UI | `django-crispy-forms`, `crispy-bootstrap5` | `templates/pages/`, `templates/users/`, allauth template overrides, `users` views / forms / urls |
| Object storage | `django-storages` 1.14.6 + `boto3` 1.43.65, both on conda-forge | `STORAGES` configuration |

### 2.1 Immovable as capability, not as package set

"Observability is immovable" is true of the capability and false of the package list. The OpenTelemetry dependencies split:

- **Always present:** `opentelemetry-api`, `-sdk`, `-exporter-otlp-proto-http`, `-instrumentation-django`, `-instrumentation-asgi`
- **Conditional:** `-instrumentation-celery` (background tasks), `-instrumentation-redis` (cache), `-instrumentation-psycopg` (core, since PostgreSQL is immovable)

`django-structlog` is likewise immovable, but its Celery correlation-ID propagation exists only when Celery does. An architecture that treats the immovable set as a fixed package list will hardcode dependencies that must flex.

### 2.2 Django admin is orthogonal to the UI toggle

Admin is itself a server-rendered UI: retaining it means static file serving, the messages framework, and template rendering remain in every component regardless of the UI toggle. What the UI toggle removes is the *end-user* surface — form styling, page templates, user-facing views — not the rendering machinery. The audiences differ (operators versus end users), which is why both are core rather than coupled.

## 3. Dependency audit — results and reasoning

Conducted against source references across `src/` and `tests/`.

| Package | References | Verdict |
|---|---|---|
| `python-slugify` | 0 | Dead. Django ships `django.utils.text.slugify`; the dependency is redundant |
| `django-model-utils` | 0 | Dead. A conventions library nothing uses |
| `pillow` | 0 | Dead. Initially classified as latent against a future media feature; **withdrawn** once object storage was scoped to documents and blobs and avatars were confirmed to resolve from IdP metadata as remote URLs |
| `fido2`, `qrcode` | via `allauth.mfa` | Cut. MFA is enforced at the IdP |
| `argon2-cffi` | `PASSWORD_HASHERS` only | Cut with that block |

**Object storage libraries: none present.** Genuinely greenfield, not a dead dependency.

### 3.1 The orphan class

Removing `allauth.mfa` left two template overrides unreachable, traced to their only callers inside the installed allauth distribution:

| Override | Only rendered by | Status after MFA removal |
|---|---|---|
| `elements/panel.html` | `mfa/index.html` | Unreachable |
| `elements/table.html` | `mfa/webauthn/authenticator_list.html`, `usersessions/usersession_list.html` | Unreachable — `allauth.usersessions` was never installed |

`account/email.html` was confirmed to use `badge`, `button`, `field`, `fields`, `form`, `h`, and `p` — not `table`. An existing test docstring claiming to cover `table.html` was therefore already inaccurate before the removal, and was corrected.

**This is the generalizable finding.** No import graph, linter, or dependency analyzer flags an orphaned template override. Only the coverage gate did, by reporting 0%. Every future feature extraction will produce the same class of residue across templates, static assets, and settings fragments.

## 4. Verification model

### 4.1 Selection versus verification

Two separate models, deliberately not merged:

- **Selection** — individual features with declared constraints. Freely combinable; the generator refuses invalid combinations at the source.
- **Verification** — a set of combinations CI proves green. Test fixtures, never a restriction on what may be selected.
- **Presets** — named starting points (*API-only*, *Full web app*, *Worker-enabled*) that pre-select features and remain fully editable. A convenience and documentation device with zero constraining effect.

Presenting profiles as menu items was rejected: it would refuse legitimate requests such as *API-only plus background tasks plus object storage*.

### 4.2 The valid combination space

Four toggles suggest 16 combinations. The broker constraint eliminates one of four Celery/Redis pairings:

| Background tasks | Redis | Valid |
|---|---|---|
| off | off | yes |
| off | on | yes — cache only |
| on | on | yes |
| on | off | no — no broker |

3 valid pairings × UI (2) × Object storage (2) = **12 valid combinations.**

### 4.3 What each combination is verified against

Local development and deployment do not use the same backing services (§6), so a combination that passes on the local substitutes has not been shown to work deployed. Each combination therefore carries two checks, which are not the same check run twice:

| Check | Backing services | Establishes |
|---|---|---|
| Full gate | PostgreSQL | tests, ≥90% coverage, strict typing, lint, build against the real backend |
| Local runnability | none | the component starts, serves, and authenticates a developer with nothing installed |

Neither the database backend nor the authentication mode is a feature toggle. They are properties of the environment a combination runs in, so they do not multiply the combination space — 12 remains 12.

**Current state, and the reason this is stated explicitly.** No workflow in `.github/workflows/` declares a `services:` block or sets `DATABASE_URL`, so the suite has only ever run against the sqlite fallback. PostgreSQL is immovable core and nothing has verified it. The gate must gain a PostgreSQL service before criterion 1 means what it says.

### 4.4 Policy

Exhaustive verification of all 12 while the space stays small. Past roughly 32 valid combinations, replace with all-pairs coverage plus unconditional verification of every preset. All-pairs holds six to eight features at roughly six to ten builds rather than 64 to 256.

Any bound on coverage must be reported explicitly. A silently truncated verification set reads as full coverage and is worse than no claim.

## 5. Deployment interface

Deployment configuration lives in a separate repository outside the control of the team that owns this product. The contract the generated component must present:

- Configuration exclusively via environment variables, with no configuration file baked into the image
- No reliance on a fixed UID or writable arbitrary paths — the target platform assigns arbitrary non-root UIDs
- A health signal the platform can probe
- OTLP export controlled by environment; traces are dropped rather than retried when no collector is configured
- PostgreSQL required in every deployed environment; production settings already raise if the sqlite path is reached

## 6. Local development interface

The counterpart to §5. Where the deployment interface states what a component must present to the platform, this states what it must not demand of a developer: **nothing running alongside it.**

### 6.1 The substitutions

| Deployed | Local | Mechanism | Preserved | Not exercised |
|---|---|---|---|---|
| PostgreSQL | sqlite | `base.py:57-78` selects sqlite when neither `DATABASE_URL` nor `POSTGRES_DB` is set | ORM, migrations, full suite | PostgreSQL-specific DDL and constraint behavior, transaction and isolation semantics, native JSON and array types |
| Redis cache | in-memory cache | `local.py:22-28` sets `LocMemCache` | The cache API at every call site | Eviction, shared state across processes, serialization |
| Celery and broker | eager execution | `local.py` sets `CELERY_TASK_ALWAYS_EAGER` and `CELERY_TASK_EAGER_PROPAGATES` | Task bodies, invoked synchronously in-process | Delivery, retries, scheduling, argument serialization, worker concurrency |
| Corporate IdP | local users and admins | §1.6 — local credential paths, synthetic claims through the shared mapper | Claims-to-groups mapping, `is_staff` promotion, per-login re-sync | JWKS retrieval, signature and issuer validation, key rotation, IdP-side revocation |

### 6.1.1 Observability is not substituted

The four rows above swap an implementation. Observability does not: locally it runs the same code the deployed component runs, and only the terminal export step is absent.

`src/config/observability/telemetry.py` makes **export** conditional and nothing else. `resolve_traces_exporter()` returns `otlp` only when `OTEL_EXPORTER_OTLP_ENDPOINT` or its traces-specific variant is set; with neither present it returns `none` and no span processor is attached. The tracer provider is still installed, all four instrumentors still instrument, spans are still created and ended, and `trace_id` and `span_id` still reach every log line. Spans are discarded at the end of their life rather than never existing.

| Local condition | SDK and instrumentation | Span export | `trace_id` in logs |
|---|---|---|---|
| No endpoint set (default) | on | discarded | yes |
| `OTEL_TRACES_EXPORTER=console` | on | stdout | yes |
| `OTEL_SDK_DISABLED=true` | off | none | **no** |

The rejected implementation is worth recording, because it is the obvious one: attaching a `BatchSpanProcessor` to an OTLP exporter pointed at an unreachable endpoint. That retries on every export cycle and floods stderr through every test run and every `runserver`. Discarding at the processor is correct; failing at the socket is not.

**Decision: the local default stays discard-at-the-processor, with the console exporter available on demand** (`OTEL_TRACES_EXPORTER=console pixi run runserver`). Making console the dev-environment default was considered and rejected as noise; a file-writing exporter and an opt-in local collector were rejected as new surface for a capability that already works.

**What local development does not exercise:** the OTLP path itself — protobuf serialization, HTTP transport, batch behavior, retry and timeout — since that branch runs only when an endpoint is configured. `tests/unit/test_telemetry.py` covers exporter *selection* comprehensively, but no test drives `BatchSpanProcessor(OTLPSpanExporter())` end to end. Per §4.3 this belongs to the gate. `OTEL_SDK_DISABLED` is the one setting that genuinely turns the capability off, and a deployed component that sets it has silently opted out of an immovable guarantee — a candidate for the §6.3 refusal list.

### 6.1.2 Provenance of the substitutions

Three of the four substitutions already held before this was written, inherited from `cookiecutter-django` and undocumented. Stating them as a contract changes their status: they become properties every generated combination is verified to have (§4.3), rather than defaults that happen to survive feature extraction.

### 6.2 The consequence for the feature constraint

The brief's constraint — background task processing requires a broker, so the generator refuses it without Redis — is a statement about deployed environments. Locally, all 12 combinations run with no broker, because eager execution needs none. Left unstated, the constraint reads as absolute and local development appears to violate it.

### 6.3 What this does not license

The substitutions are for local development only. `production.py` already refuses sqlite; §1.6 extends the same refusal to local credential paths. The in-memory cache and eager Celery are not currently guarded, and a deployed component that silently falls back to either would be a defect of the same class. Whether those two warrant equivalent startup refusals is open.

## 7. Open items carried forward

1. The phase-2 verification harness — how generated output is built and gated once the repository becomes a FreeMarker template
2. Where the shared claims-to-groups mapper lives so all three authentication paths — interactive, programmatic, and local synthetic (§1.6) — consume one implementation
3. The health-signal contract expected by the deployment repository
4. How local personas are defined and seeded: where the synthetic claims live, and whether the first local admin arrives via `createsuperuser` or a seeding task that can express several developers with different group memberships
5. Where the development signing keypair lives, how it is generated, and what keeps it out of a deployed component
6. Whether the in-memory cache, eager Celery, and `OTEL_SDK_DISABLED` warrant startup refusals in production settings, as sqlite and local credentials do (§6.3)
7. Whether local runnability is verified by a smoke check per combination or by the suite itself running twice
8. How the component's own name is parameterized. The tree is `src/django_service/`, and every generated component needs its own package name, module paths, and `service.name` on the telemetry resource. The generator engine is out of scope, but making the name a template parameter is the template's job, not the engine's
9. The single supply-chain exception is pending upstream, not permanent. `django-celery-beat` resolves from PyPI because the conda-forge recipe transcribed upstream's `importlib-metadata<5.0; python_version < "3.8"` without the environment marker, making the cap unconditional and irreconcilable with `opentelemetry-api`'s `>=6.0,<8.8.0`. [conda-forge/django-celery-beat-feedstock#18](https://github.com/conda-forge/django-celery-beat-feedstock/pull/18) removes the cap, and [celery/django-celery-beat#1080](https://github.com/celery/django-celery-beat/pull/1080) removes it upstream — executing a `TODO` upstream had already written against its own requirement. On merge and build, the dependency moves to conda-forge and the exception in the brief disappears

Resolved: conda-forge availability for `django-storages`, `boto3`, `pyjwt`, and `cryptography` — all four confirmed present. Whether the sqlite fallback survives generation — it does, promoted from a convenience to the declared local contract in §6.
