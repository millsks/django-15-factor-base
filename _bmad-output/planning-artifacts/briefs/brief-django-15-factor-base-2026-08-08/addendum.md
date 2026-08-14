---
title: "Addendum: django-15-factor-base Product Brief"
status: draft
created: 2026-08-09
updated: 2026-08-09
---

# Addendum

Depth captured during brief discovery that belongs to downstream documents — PRD, architecture, solution design — rather than to a two-page brief. Nothing here is decided beyond what the brief states; this is the supporting detail behind those decisions.

**Reading convention.** Present tense describes what is true in the repository today. `must` and `will` describe what the work has to deliver and is not yet built.

## 1. Authentication rewire — findings and target design

### 1.1 Credential paths that currently bypass the IdP

Three defaults survived the fork from `cookiecutter-django` and each contradicts the IdP-only posture. All three are verified in the source, not inferred.

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

`PASSWORD_HASHERS` and `argon2-cffi` were removed: with no locally issued or verified password, the component has no reason to prefer a hasher and Django's defaults stand. Note this removed the *dependency*, not local password authentication — that is the rewire described above, which remains outstanding. `AUTH_PASSWORD_VALIDATORS` was deliberately retained while any residual password path exists.

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

### 4.3 Policy

Exhaustive verification of all 12 while the space stays small. Past roughly 32 valid combinations, replace with all-pairs coverage plus unconditional verification of every preset. All-pairs holds six to eight features at roughly six to ten builds rather than 64 to 256.

Any bound on coverage must be reported explicitly. A silently truncated verification set reads as full coverage and is worse than no claim.

## 5. Deployment interface

Deployment configuration lives in a separate repository outside the control of the team that owns this product. The contract the generated component must present:

- Configuration exclusively via environment variables, with no configuration file baked into the image
- No reliance on a fixed UID or writable arbitrary paths — the target platform assigns arbitrary non-root UIDs
- A health signal the platform can probe
- OTLP export controlled by environment; traces are dropped rather than retried when no collector is configured
- PostgreSQL required in every deployed environment; the sqlite fallback is a local-development convenience and production settings already raise if it is reached

Open item: whether the sqlite fallback survives into generated components or is confined to the reference application.

## 6. Open items carried forward

1. The phase-2 verification harness — how generated output is built and gated once the repository becomes a FreeMarker template
2. Whether the sqlite development fallback survives generation
3. Where the shared claims-to-groups mapper lives so both authentication flows consume one implementation
4. The health-signal contract expected by the deployment repository

Resolved during discovery: conda-forge availability for `django-storages`, `boto3`, `pyjwt`, and `cryptography` — all four confirmed present.
