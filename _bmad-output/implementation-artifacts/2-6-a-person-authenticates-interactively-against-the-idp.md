---
baseline_revision: 79a2679
review_loop_iteration: 0
status: done
warnings: []
---

# Story 2.6: A person authenticates interactively against the IdP

Status: done

## Story

As a lead developer,
I want browser sign-in to redirect to the IdP and establish a session through the shared mapper,
so that the admin and the server-rendered UI have exactly one credential authority.

## Acceptance Criteria

**Traceability:** FR-4, FR-7 · AD-31 · SC-6

1. **Given** an unauthenticated request to an authenticated page
   **When** it is served
   **Then** it redirects to the IdP
   **And** never to a local login form

2. **Given** the OIDC provider
   **When** it is wired
   **Then** it is `allauth.socialaccount.providers.openid_connect` from the installed distribution
   **And** no additional OIDC framework is added
   **And** `requests` is declared directly in the dependency manifest rather than relied on transitively

3. **Given** a successful callback
   **When** the session is established
   **Then** allauth's `SocialAccountAdapter` invokes the mapper
   **And** contains no mapping logic of its own

4. **Given** provider configuration
   **When** the component starts
   **Then** it is read from `SOCIALACCOUNT_PROVIDERS` populated from the environment
   **And** never from database-resident `SocialApp` rows

5. **Given** the `Site` domain
   **When** it is configured
   **Then** it is environment-driven
   **And** the data migration at `src/django_service/contrib/sites/migrations/0003_set_site_domain_and_name.py` is retired rather than parameterized

6. **Given** `/admin/` login
   **When** `DJANGO_ADMIN_FORCE_ALLAUTH` defaults to true
   **Then** it is served by the IdP redirect through the existing `secure_admin_login` wrapper in `users/admin.py`
   **And** never by Django's own credential form

## Tasks / Subtasks

- [x] Task 1 — Declare the three undeclared dependencies in `pixi.toml` (AC: #2)
  - [x] Add to `[dependencies]`, conda-forge, with rationale comments beside them (the spine's Rationale convention): `requests = ">=2.34,<3"`, `pyjwt = ">=2.13,<3"`, `cryptography = ">=50.0,<51"`.
  - [x] The reason, recorded in the comment: the conda-forge `django-allauth 65.19.1` recipe declares only `asgiref`, `django`, `python` — it encodes **none** of upstream's `socialaccount` extra (`oauthlib`, `requests`, `pyjwt[crypto]`). `allauth/socialaccount/providers/openid_connect/provider.py` imports `requests` at module top, and ID-token verification goes through `allauth/socialaccount/internal/jwtkit.py`, which needs `pyjwt` and `cryptography`. `requests` is in `pixi.lock` today at 2.34.2 **only transitively**, supplied by `opentelemetry-exporter-otlp-proto-http` — so changing the OTLP exporter would break authentication with an `ImportError` at provider import.
  - [x] This satisfies the spine's supply-chain convention directly: "Transitive availability is not declaration: a package the code imports directly is declared directly, even when something else already pulls it in."
  - [x] `pyjwt` and `cryptography` are declared here rather than in Story 2.7 because allauth needs them the moment this story lands. Story 2.7 adds no new dependency.
  - [x] Do **not** add anything to `[pypi-dependencies]`. It carries the editable self-install and nothing else; `tests/unit/test_dependency_policy.py` fails otherwise. Run `pixi install` and commit the updated `pixi.lock`.

- [x] Task 2 — Install and configure the OIDC provider in `src/config/settings/base.py` (AC: #1, #2, #4)
  - [x] Add `"allauth.socialaccount.providers.openid_connect"` to `THIRD_PARTY_APPS`, immediately after the existing `"allauth.socialaccount"` entry (currently base.py:109).
  - [x] Build `SOCIALACCOUNT_PROVIDERS` from the environment in the `# django-allauth` block. Required keys for `openid_connect`, verified against allauth 65.19.1: `provider_id`, `name`, `client_id`, `secret`, and `settings["server_url"]` — a missing `server_url` is a hard `KeyError`, not a graceful degradation.
  - [x] Set `oauth_pkce_enabled: True`. FR-4 specifies "Authorization Code with **PKCE**"; without this key allauth does not use PKCE.
  - [x] Environment variables, `COMPONENT_`-prefixed per the spine's convention: `COMPONENT_OIDC_ISSUER` (becomes `server_url`), `COMPONENT_OIDC_CLIENT_ID`, `COMPONENT_OIDC_CLIENT_SECRET`, `COMPONENT_OIDC_PROVIDER_ID` (default `"oidc"`), `COMPONENT_OIDC_PROVIDER_NAME`. Read them with `default=""` — **do not raise at settings import**; the unconfigured-IdP refusal is Epic 4's stage 1.
  - [x] `COMPONENT_OIDC_ISSUER` is also the trust anchor Story 2.7 derives the JWKS location from (AD-23). One variable, one meaning — do not introduce a second issuer setting.
  - [x] Set `SOCIALACCOUNT_EMAIL_AUTHENTICATION = False` explicitly (it is the default; making it explicit is what stops a later edit turning email into a resolution key, which AD-11 forbids).
  - [x] Do **not** create `SocialApp` rows, a fixture that creates them, or an admin instruction to create them. Configuring the same provider in both settings and the database raises `MultipleObjectsReturned` at login.
  - [x] Keep `django.contrib.sites` in `INSTALLED_APPS` and `SITE_ID = 1` as they are: allauth's `list_apps()` still queries `socialaccount_socialapp` through `SocialApp.objects.on_site(request)` on every lookup — **no row is needed, but the table must exist**, so the migration is not optional.

- [x] Task 3 — Move the social adapter into the authorization package and hook the mapper (AC: #3)
  - [x] Create `src/config/authorization/adapters.py` with `class OIDCSocialAccountAdapter(DefaultSocialAccountAdapter)`.
  - [x] Override `pre_social_login(self, request, sociallogin)`: read `sociallogin.account.extra_data` as the claims mapping, call `resolve_user(claims)` then `sync_for_interactive(user, claims)` from `config.authorization.mapper`, then `sociallogin.connect(request, user)` so allauth attaches its `SocialAccount` bookkeeping to the user the mapper chose. Translate `ClaimsRejected` into `allauth.core.exceptions.ImmediateHttpResponse` carrying a 403/redirect — the interactive flow has no 401 to return; the Bearer flow (Story 2.7) is where 401 applies.
  - [x] `pre_social_login` is the correct hook and `populate_user` is not: `populate_user` runs **only when allauth instantiates a new user**, so mapping placed there runs once and never again. `pre_social_login` runs on every social login. This is Story 2.5 AC #5's rule ("mapping must not live in `populate_user()`") landing in code.
  - [x] Keep `is_open_for_signup` behaviour by carrying the existing implementation across unchanged.
  - [x] The adapter contains **no mapping logic of its own** (AC #3): it extracts claims, calls the mapper, connects the login. Any group, staff or username decision inside the adapter is a defect.
  - [x] Delete `class SocialAccountAdapter` from `src/django_service/users/adapters.py`, including its `populate_user`. Leave `class AccountAdapter` in place — it backs `ACCOUNT_ADAPTER`, is about signup policy, and is untouched by this story.
  - [x] Repoint `SOCIALACCOUNT_ADAPTER` in `src/config/settings/base.py` (currently line 350) to `"config.authorization.adapters.OIDCSocialAccountAdapter"`.
  - [x] Moving the class out of `django_service` is legal: AD-29 says "anything inside `django_service` not enumerated is internal and may change without a version bump", and `accelerator.toml` — where the guaranteed surface is enumerated — does not exist yet. It is also required by AD-4, since `django_service` may not import `config.authorization`.

- [x] Task 4 — Retire the `Site` data migration and make the domain environment-driven (AC: #5)
  - [x] `src/django_service/contrib/sites/migrations/0003_set_site_domain_and_name.py` currently hardcodes `"millsks.github.io"` / `"Django 15-Factor Application Accelerator"` into the database through `RunPython`, with a PostgreSQL sequence resync helper. Replace its `operations` with `[migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop)]` and replace the module docstring with one stating that AD-31 retires this migration and why.
  - [x] **Keep the file and its migration node.** Do not delete it: `0004_alter_options_ordering_domain.py` depends on it, and databases that already applied it carry the row in `django_migrations`. Retiring the *operations* is what "retired rather than parameterized" means here; deleting the node breaks every existing history.
  - [x] Add `SITE_DOMAIN = env.str("COMPONENT_SITE_DOMAIN", default="localhost")` and `SITE_NAME = env.str("COMPONENT_SITE_NAME", default="localhost")` to `src/config/settings/base.py` near `SITE_ID`.
  - [x] Do **not** add startup code that writes the `Site` row. NFR-1 requires the startup checks to make "no network call and no query beyond migration state", and AD-22 forbids any process performing writes at boot. The settings values are the environment-driven source of truth; the `Site` table exists only because allauth's `on_site` lookup needs it to exist.
  - [x] Do **not** add `sonar`-style parameterization or an `accelerator.toml` `[parameters]` entry for the domain. AD-25 owns parameterization and it is Epic 7's; AD-31 explicitly says this migration is *retired*, not parameterized.

- [x] Task 5 — Force the admin through allauth by default (AC: #1, #6)
  - [x] Flip the default in `src/config/settings/base.py:271`: `DJANGO_ADMIN_FORCE_ALLAUTH = env.bool("DJANGO_ADMIN_FORCE_ALLAUTH", default=True)`. It reads `default=False` today, which contradicts FR-7's "`DJANGO_ADMIN_FORCE_ALLAUTH` defaults true."
  - [x] Do **not** modify `src/django_service/users/admin.py:11-15`. AC #6 says "through the **existing** `secure_admin_login` wrapper" — the mechanism is already correct; only the default was wrong.
  - [x] Set `LOGIN_URL` so an unauthenticated request to a `LoginRequiredMixin` view lands on the provider redirect rather than allauth's local form. `LOGIN_URL` is `"account_login"` today (base.py:142); point it at the `openid_connect` provider login route for the configured `provider_id`. Use `django.urls.reverse_lazy` — a module-level `reverse()` in settings runs before the URLconf is loaded.
  - [x] Do **not** delete allauth's local account URLs, forms or templates in this story. FR-6 and the refusal that makes a local credential path fatal are Story 2.8's and Epic 4's respectively; deleting them here would take a change belonging to two other stories.

- [x] Task 6 — Tests (AC: #1 through #6)
  - [x] Update `tests/unit/users/test_adapters.py` (exists): it imports `SocialAccountAdapter` from `django_service.users.adapters` and has five tests over `populate_user` and `is_open_for_signup`. Move the social-adapter cases to a new `tests/unit/authorization/test_adapters.py` against `OIDCSocialAccountAdapter`, drop the `populate_user` name-derivation cases (that behaviour leaves with the class), and leave the two `AccountAdapter` cases where they are.
  - [x] `tests/unit/test_settings.py` (exists) — add cases asserting `"allauth.socialaccount.providers.openid_connect"` is in `INSTALLED_APPS`, that `SOCIALACCOUNT_PROVIDERS["openid_connect"]["APPS"][0]["settings"]["server_url"]` tracks `COMPONENT_OIDC_ISSUER`, that `oauth_pkce_enabled` is True, and that `DJANGO_ADMIN_FORCE_ALLAUTH` is True with the variable unset. The file's `_evict_settings_modules` fixture already re-imports `config.settings.base` fresh under a monkeypatched environment — use it.
  - [x] `tests/unit/authorization/test_adapters.py` (new) — assert `pre_social_login` calls the mapper (patch `resolve_user`/`sync_for_interactive` and assert the call), and assert the adapter module's source contains no `Group`, `is_staff` or `is_superuser` reference (AC #3's "contains no mapping logic of its own").
  - [x] `tests/integration/users/test_admin.py` (exists) — its `_force_allauth` fixture sets `settings.DJANGO_ADMIN_FORCE_ALLAUTH = True` and reloads the admin module. With the default flipped, confirm the `admin_client` tests still pass; the pytest-django `admin_client` fixture logs in via session, not the login form, so they should. Fix any that assumed the local form.
  - [x] `tests/integration/test_site_migration.py` (new, `@pytest.mark.django_db`) — assert no `Site` row carries the retired hardcoded domain after a full migrate, and that `settings.SITE_DOMAIN` tracks `COMPONENT_SITE_DOMAIN`.
  - [x] AC #1 needs a rendered assertion: unauthenticated `client.get(reverse("users:detail", kwargs={"username": ...}))` returns a redirect whose target is the provider login route, not `/accounts/login/`.
  - [x] Run `pixi run test`, `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-31 (binding rule):** "allauth's OIDC provider is configured from `SOCIALACCOUNT_PROVIDERS` populated from the environment, never from database-resident `SocialApp` rows, which a component forbidden to migrate itself could never create. The `Site` domain is likewise environment-driven; the existing data migration at `src/django_service/contrib/sites/migrations/0003_set_site_domain_and_name.py` is **retired rather than parameterized**." *Prevents:* "session behaviour varying by feature toggle; and **every deployed component redirecting to whatever callback domain a data migration baked in**."
  - The migration exists and is exactly as described — verified. It writes `"millsks.github.io"` at line 45.
  - AD-31 also mandates `SESSION_ENGINE` set explicitly to the database-backed engine in `base.py`. That is **Epic 5 Story 5.7's** work, not this story's; `SESSION_ENGINE` is unset in `base.py` today and this story leaves it that way.
- **AD-11 (binding rule):** "The allauth adapter resolves through the mapper too; `SocialAccount` is bookkeeping, not authority." Read `SocialAccount` if you need `extra_data`; never resolve a user from it.
- **AD-4 (dependency direction):** "`config` may import `django_service` … `django_service` may never import a tenant app." The adapter must call the mapper, and the mapper lives in `config` — which is why the adapter moves to `config/authorization/` rather than the mapper being imported into `django_service`.
- **AD-23 (relevant half):** "The trust anchor is derived from the configured OIDC issuer." `COMPONENT_OIDC_ISSUER` set here is that anchor; Story 2.7 derives from it. Do not introduce a second issuer variable.
- **AD-24 (what you must not do):** "No other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`." Never guard the OIDC provider app or `SOCIALACCOUNT_PROVIDERS` behind an availability check.
- **AD-29:** `src/django_service/` is `core` in its entirety. Moving `SocialAccountAdapter` **out** of it is permitted (internal surface, unenumerated); applying a `feature:*` marker to anything left inside it is not.
- **Spine, Supply chain convention:** "conda-forge only; `[pypi-dependencies]` carries the editable self-install and nothing else. **Transitive availability is not declaration**: a package the code imports directly is declared directly, even when something else already pulls it in."
- **FR-7:** "The Django admin is forced through the IdP; `DJANGO_ADMIN_FORCE_ALLAUTH` defaults true."
- **NFR-1 / FR-23:** startup makes no network call. allauth's OIDC discovery happens at **request** time, reading `jwks_uri` from the discovery document then — not at import or boot. Do not add a discovery fetch to settings, an `AppConfig.ready()`, or a system check.

### Repository drift found while writing this story

Two facts to hold while implementing:

1. **`DJANGO_ADMIN_FORCE_ALLAUTH` defaults to `False` today** (`src/config/settings/base.py:271`), against FR-7's "defaults true". Task 5 fixes it. This is a real divergence between the epic text and the repository, not a misreading.
2. **`requests` is undeclared** and reaches the environment only through `opentelemetry-exporter-otlp-proto-http`; `pyjwt` and `cryptography` are absent from `pixi.lock` entirely. Task 1 fixes all three.

### A behaviour allauth has that this design deliberately does not use

In the browser code flow allauth sets `verify_signature = not self.did_fetch_access_token`, which is `True` on that path — so **allauth deliberately skips JWKS signature verification** for the interactive flow (OIDC Core §3.1.3.7 clause 6: the token arrived over a TLS-protected back channel). `iss`, `aud` and `exp` are still enforced. This is correct and expected; do not "fix" it by forcing signature verification on the interactive path. Full JWKS-by-`kid` verification belongs to the Bearer path, which is Story 2.7.

### SC-6 cannot be closed here

SC-6 requires a real IdP identity. It is an **external exit criterion no story closes** — owner: the platform group, after Epic 2. This story's ACs are all satisfiable against a mocked provider.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
|---|---|---|
| `pixi.toml` | UPDATE | Today: `[dependencies]` holds conda-forge runtime packages with rationale comments; `[pypi-dependencies]` holds only the editable self-install. Adds three packages with comments. **Preserve:** the `django-celery-beat` comment block and the `[pypi-options] no-build-isolation` entry. |
| `pixi.lock` | UPDATE | Regenerated by `pixi install`. Commit it. |
| `src/config/settings/base.py` | UPDATE | Today: `THIRD_PARTY_APPS` at 104–116 (`allauth`, `allauth.account`, `allauth.socialaccount` at 107–109); `SITE_ID = 1` at 45; `LOGIN_URL = "account_login"` at 142; `DJANGO_ADMIN_FORCE_ALLAUTH` at 271; the `# django-allauth` block at 336–352 with `SOCIALACCOUNT_ADAPTER` at 350. **Preserve:** the `# PASSWORDS` rationale block (144–159), `MIGRATION_MODULES` (128), and the `# django-rest-framework` block — Story 2.8 owns that one. |
| `src/config/authorization/adapters.py` | NEW | `OIDCSocialAccountAdapter` with `pre_social_login`. |
| `src/django_service/users/adapters.py` | UPDATE | Today: `AccountAdapter` (16–18) and `SocialAccountAdapter` (21–48) with `is_open_for_signup` and `populate_user`. This story removes the second class and its now-unused `SocialLogin`/`User` TYPE_CHECKING imports. **Preserve:** `AccountAdapter` verbatim. |
| `src/django_service/contrib/sites/migrations/0003_set_site_domain_and_name.py` | UPDATE | Today: 66 lines — `_update_or_create_site_with_sequence`, `update_site_forward` writing `"millsks.github.io"`, `update_site_backward`, and `Migration` depending on `0002_alter_domain_unique`. Operations become no-ops; the node and its `dependencies` stay. **Preserve:** the class name, the `dependencies` list, and the file path — `0004_alter_options_ordering_domain.py` depends on this node. |
| `tests/unit/users/test_adapters.py` | UPDATE | Exists, 77 lines, two test classes. Loses `TestSocialAccountAdapter`. |
| `tests/unit/authorization/test_adapters.py` | NEW | The relocated and re-scoped social-adapter tests. |
| `tests/unit/test_settings.py` | UPDATE | Exists. Adds provider-configuration and admin-default cases. |
| `tests/integration/users/test_admin.py` | UPDATE | Exists; its `_force_allauth` fixture and `test_allauth_login` may need adjusting once the default is True. |
| `tests/integration/test_site_migration.py` | NEW | The retired-migration assertion. |

### Testing Requirements

- Test tree mirrors `src/`: `src/config/authorization/adapters.py` → `tests/unit/authorization/test_adapters.py`. Settings behaviour stays in `tests/unit/test_settings.py`, which already owns that concern.
- `tests/integration/conftest.py` auto-applies `pytest.mark.integration` under `tests/integration/`; DB access still needs `@pytest.mark.django_db`.
- Never make a real network call in a test. Mock allauth's provider at the adapter seam or construct `SocialLogin` objects directly — `tests/unit/users/test_adapters.py` already demonstrates constructing `SocialLogin(user=User())` against an unsaved user with no database.
- Assertions the ACs demand: the redirect target for an unauthenticated request (AC #1); `INSTALLED_APPS` membership and the three declared packages present in `pixi.toml` (AC #2 — `tests/unit/test_dependency_policy.py` already parses `pixi.toml`, so extend that pattern rather than inventing a new parser); the adapter calls the mapper and holds no mapping logic (AC #3); provider config comes from settings and no `SocialApp` row is created (AC #4); the retired migration writes nothing (AC #5); the admin default is True and the wrapper is the existing one (AC #6).
- Coverage floor 90% including templates (AD-20), gate via `pixi run test-cov` inside `pixi run ci`. Add nothing to `[tool.coverage.run] omit`. Note that deleting `SocialAccountAdapter.populate_user` removes covered lines — net coverage should rise, not fall.
- `pixi run build` runs inside `pixi run ci` and will catch an import error introduced by the adapter move.

#### Project Structure Notes

`src/config/authorization/` now holds the mapper (2.4, 2.5) and the interactive adapter, matching the spine's Capability map: "Authentication & authorization (§4.2) | `src/config/authorization/`, DRF auth class, allauth adapter".

One recorded variance from the repository as it stands: `src/django_service/contrib/sites/` exists only to host the `sites` migrations via `MIGRATION_MODULES = {"sites": "django_service.contrib.sites.migrations"}` (base.py:128). After this story the directory still exists and still hosts four migration nodes, one of which is now a deliberate no-op. That is intended — a retired node must remain a node.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-31]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-11]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-4]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — supply chain, environment variables, rationale
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/reviews/review-tech-verification.md:47-66] — H-2: the conda-forge allauth recipe omits the socialaccount extra; `requests` survives only on an OpenTelemetry transitive edge
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/reviews/review-tech-verification.md:209-219] — L-3: settings-driven `APPS` confirmed DB-free; required keys; `list_apps()` still queries the table; `MultipleObjectsReturned` on settings+DB collision; `pre_social_login` is the correct hook
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/reviews/review-tech-verification.md:223-235] — L-4: allauth skips JWKS verification in the code flow
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.6]
- [Source: _bmad-output/planning-artifacts/epics.md:32,35] — FR-4, FR-7
- [Source: src/config/settings/base.py:45,104-116,142,271,336-352] — SITE_ID, THIRD_PARTY_APPS, LOGIN_URL, the admin flag, the allauth block
- [Source: src/django_service/contrib/sites/migrations/0003_set_site_domain_and_name.py] — the migration to retire, 66 lines, hardcoded domain at line 45
- [Source: src/django_service/users/admin.py:11-15] — the existing `secure_admin_login` wrapper

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Claude Code). Implementation by the orchestrated `bmad-dev-auto` session; wrap-up, gate and inline review by the session driving the loop after that session was killed (see the Review Triage Log).

### Debug Log References

- `pixi run ci` — exit 0. 559 passed, coverage 94.81% (floor 90). `src/config/authorization/adapters.py` at 100%.
- PostgreSQL 17.8 run (per project memory `validate-model-changes-against-postgres`): `DATABASE_URL=postgres://…@localhost:5432/app_test pixi run test-cov --create-db` — exit 0, 559 passed, same coverage. Needed because this story retires a migration whose forward pass carried a PostgreSQL sequence-resync helper (`django_site_id_seq`), and only a real migrate proves the retired node still applies cleanly in a history that already ran the original. `tests/integration/test_postgres_schema.py` asserts `connection.vendor` against the `DATABASE_URL` scheme, so the run is self-proving rather than a silent sqlite fallback.
- First gate attempt failed twice, both times on defects the killed session left mid-edit:
  1. `ruff check .` — `F401 structlog imported but unused` in `tests/integration/test_site_migration.py`. Pre-commit's own `ruff check` passed on the same tree: the file was untracked, and pre-commit only sees tracked/staged paths. `pixi run lint` is what catches an untracked new file, which is the reason the gate runs both.
  2. `pixi run test-cov` — three of Story 2.5's tests failed (`test_the_group_refusal_names_the_claim_it_looked_for`, `test_the_missing_jti_refusal_is_reported`, `test_an_expiry_the_platform_cannot_represent_is_reported`), each asserting `len(events) == 1` against `0`. See the first completion note.

### Completion Notes List

- **A test-isolation regression this story introduced, and the fix.** `config/settings/base.py` calls `configure_structlog()` at module scope, which is a global `structlog.configure(..., cache_logger_on_first_use=True)`. `tests/integration/test_site_migration.py::test_the_site_domain_is_read_from_the_environment` re-imports that module to re-evaluate the `COMPONENT_SITE_*` reads, so it replaced the process-wide structlog configuration and never put it back. On its own that was harmless; combined with `tests/integration/authorization/test_adapters.py` exercising the mapper's module-level logger afterwards, the logger cached a frozen processor chain and `structlog.testing.capture_logs()` in Story 2.5's unit tests captured nothing — three refusal-reporting assertions went **silently blind** rather than erroring. Neither file reproduces it alone, and `tests/integration/` sorts before `tests/unit/`, so only the whole suite in order shows it. Fixed by saving `structlog.get_config()` before the re-import and restoring it in the `finally`, which is what the orphaned `structlog` import in that file was evidently reaching for. The unused-import lint and the failure had one root cause.
- `tests/unit/test_settings.py` reloads the same settings module through `_evict_settings_modules` with the same leak and no restore. It does not bite today only because `tests/unit/test_settings.py` sorts *after* `tests/unit/authorization/`, so nothing capture-based runs downstream of it. Left alone deliberately — the fixture is shared by that whole file and pre-dates this story — and recorded in the deferred-work ledger instead.
- `oauth_pkce_enabled` is placed inside the app entry's `settings` dict, not at the provider level, and that placement was verified against the installed allauth rather than taken from the spec: `providers/oauth2/provider.py:33` reads `self.app.settings.get("oauth_pkce_enabled")` and `pkce_enabled_default = False` at `:19`. Without the key in that exact position FR-4's PKCE requirement is silently unmet, because the fallback is off.
- The adapter reads claims through `claims_from`, which unwraps allauth's two-key `{"userinfo": …, "id_token": …}` envelope rather than reading `extra_data` flat. Flat reading would find no identity claim at all against a real IdP while passing every hand-built `SocialLogin` in the suite — a test-only shape that looks correct. `userinfo` wins a disagreement (allauth's own precedence) and claims carried by only one envelope still survive.
- A refusal answers 403 through an overridable `refusal_response`, not a redirect back to the login route: a permanent refusal answered with a redirect sends the browser round the provider forever. The body says only "Sign-in was refused" — the reason is a log field, because a claim value or a configured claim name rendered into a page leaks the token's contents to whoever triggered the refusal.
- `SocialAccountAdapter.populate_user`'s name derivation was **deleted rather than moved**. The mapper owns every claim-derived attribute (AD-11), so re-homing it would have recreated the second authority this story exists to remove. `AccountAdapter` is untouched.
- The `Site` migration keeps its node and its `dependencies`; only its `operations` became `RunPython.noop` pairs. `0004_alter_options_ordering_domain` depends on it and deployed databases already record it in `django_migrations`, so deleting the file would break every existing history. Nothing writes the `Site` row at startup — `SITE_DOMAIN`/`SITE_NAME` are settings, and NFR-1/AD-22 forbid a boot-time write.
- `django.contrib.sites` and `SITE_ID` stay: allauth calls `SocialApp.objects.on_site(request)` on every provider lookup, so the table must exist even though AD-31 forbids a row ever being the provider's source. No `SocialApp` row, fixture, or instruction to create one exists anywhere in the tree — `test_no_provider_row_is_created_in_the_database` pins that.
- The deferred `is_active` question from Story 2.4's review does not block this story: allauth's `perform_login` refuses an inactive user after `pre_social_login` returns, so the interactive path is gated regardless of the mapper's silence. It remains open and still blocks Story 2.7, whose Bearer path has no such backend in front of it.
- Out of scope and deliberately absent: no `SocialApp` rows, no discovery fetch at startup or in `AppConfig.ready()`, no forced JWKS signature verification on the interactive path (allauth skips it there by OIDC Core §3.1.3.7 clause 6 — that is Story 2.7's Bearer concern), no deletion of allauth's local account routes (Story 2.8 / Epic 4), no `accelerator.toml` parameterization of the domain (Epic 7).
- Task names in this repository are `format` / `lint` / `typecheck` / `test` / `test-integration` / `test-cov` / `ci`, not `fmt` / `check` / `cov`.

### File List

| Path | NEW / UPDATE | What changed |
|---|---|---|
| `pixi.toml` | UPDATE | Declares `requests`, `pyjwt` and `cryptography` in `[dependencies]` with rationale comments — django-allauth's `socialaccount` extra, which the conda-forge recipe encodes none of. `[pypi-dependencies]` untouched. |
| `pixi.lock` | UPDATE | Regenerated by `pixi install`. |
| `src/config/settings/base.py` | UPDATE | Adds `SITE_DOMAIN`/`SITE_NAME`, the `openid_connect` provider app, `OIDC_PROVIDER_ID`, a `reverse_lazy` `LOGIN_URL` pointing at the provider route, `SOCIALACCOUNT_EMAIL_AUTHENTICATION = False` and the environment-built `SOCIALACCOUNT_PROVIDERS`; repoints `SOCIALACCOUNT_ADAPTER`; flips `DJANGO_ADMIN_FORCE_ALLAUTH` to default `True`. |
| `src/config/authorization/adapters.py` | NEW | `OIDCSocialAccountAdapter` (`pre_social_login`, `is_open_for_signup`, `refusal_response`) and `claims_from`. No mapping logic of its own. |
| `src/django_service/users/adapters.py` | UPDATE | `SocialAccountAdapter` and its `populate_user` deleted with their now-unused imports. `AccountAdapter` unchanged. |
| `src/django_service/contrib/sites/migrations/0003_set_site_domain_and_name.py` | UPDATE | Operations retired to a `RunPython.noop` pair; node, class name and `dependencies` preserved. Docstring restated around AD-31. |
| `tests/unit/authorization/test_adapters.py` | NEW | Envelope unwrapping, the mapper call, the 403 refusal, and the AC #3 source assertions (no `Group`/`is_staff`/`is_superuser`, `populate_user` not overridden). |
| `tests/integration/authorization/test_adapters.py` | NEW | The login end to end through the real mapper, including refusals writing nothing and no `SocialApp` row. |
| `tests/integration/test_site_migration.py` | NEW | The retired-migration assertions and the environment-driven domain, with the structlog save/restore described above. |
| `tests/unit/users/test_adapters.py` | UPDATE | Loses `TestSocialAccountAdapter`; the two `AccountAdapter` cases stay. |
| `tests/unit/test_settings.py` | UPDATE | Provider configuration, PKCE, `LOGIN_URL` and the admin default. |
| `tests/unit/test_dependency_policy.py` | UPDATE | Asserts the three packages are declared in `[dependencies]` with a rationale beside each. |
| `tests/integration/users/test_admin.py` | UPDATE | AC #6, plus a case that passes only because of the *default* rather than a fixture. |
| `tests/integration/users/test_views.py` | UPDATE | AC #1, both against the view directly and through the URL resolver. |

## Review Triage Log

### 2026-08-17 — Inline review pass (non-standard)

The orchestrated dev session was killed by a VS Code restart part-way through
its wrap-up: the implementation was complete on disk, but no task was ticked,
the Dev Agent Record was empty, no gate had run and nothing was committed. The
run's own state carried no session result (`sessions: []`), so `bmad-loop
resume` could only have paused for manual recovery or re-driven the story from
scratch. Reviewed and finalized inline instead, by the session driving the loop
— the third story in this epic to die at that phase, after 2.3 and 2.5.

Recorded as weaker evidence than a normal pass, per CG-2: the three hunters read
a diff blind and this reviewer had the story's full context. It is stronger than
2.5's inline pass in one respect — two real defects were found and fixed here,
both by running the gate rather than by reading.

- intent_gap: 0
- bad_spec: 0
- patch: 2
- defer: 1
- reject: 0
- addressed_findings:
  - `F401` on an untracked file, invisible to pre-commit and caught only by
    `pixi run lint`. Fixed, then re-opened deliberately — the import turned out
    to be the unfinished half of the finding below.
  - The structlog re-configuration leak that blinded three of Story 2.5's
    `capture_logs()` assertions. Fixed by save/restore in
    `test_the_site_domain_is_read_from_the_environment`.

What else was checked, and why each came back clean rather than unexamined:

- **PKCE actually being on.** FR-4 names Authorization Code with PKCE, and the
  key's *position* decides whether it is. Verified against the installed
  allauth: `providers/oauth2/provider.py:33` reads
  `self.app.settings.get("oauth_pkce_enabled")` — the app entry's `settings`
  dict, where the implementation put it — and `:19` defaults it False. Placed
  one level up it would have read as configured and been off.
- **The claims envelope.** The unit suite builds `SocialLogin` objects by hand
  with flat `extra_data`, so a flat read would have passed every test and found
  no identity claim against a real IdP. `claims_from` unwraps both envelopes;
  `test_the_claims_are_read_from_the_id_token_when_that_is_where_they_are`
  covers the case the hand-built objects cannot.
- **A refusal loop.** `refusal_response` returns 403 rather than redirecting to
  the login route, so a permanent refusal terminates instead of cycling the
  browser through the provider forever.
- **AC #3's "no mapping logic of its own"** is asserted against the module
  source, not just behaviour, so a later edit that inlines a `Group` lookup into
  the adapter fails rather than passes with the mapper still nominally called.
- **The retired migration on a real history.** A `RunPython.noop` pair that
  still applies cleanly over a database that already ran the original is a
  PostgreSQL question, not a sqlite one — the original carried a
  `django_site_id_seq` resync. The PG 17.8 run in the Debug Log is that check.
- **Deactivated identities.** Story 2.4's open ledger entry warns that
  `resolve_user` returns an inactive user unchanged. The interactive path is
  still gated, because allauth's `perform_login` runs after `pre_social_login`
  and refuses inactive users. The entry stays open and still blocks 2.7.

Deferred (one entry, written to the ledger): the same structlog-restore gap in
`tests/unit/test_settings.py::_evict_settings_modules`, latent today only
because of collection order.
