# Story 3.7: Nothing on the local start path reaches the network at boot

Status: ready-for-dev

## Story

As a developer working on a generated component,
I want boot to make no network call,
so that a component starts with no route to the IdP rather than failing in a way only an offline developer ever sees.

## Acceptance Criteria

**Traceability:** FR-23 · AD-23

1. **Given** settings import and Django setup
   **When** a unit test completes them
   **Then** no OIDC discovery request is performed

2. **Given** boot
   **When** a unit test completes it
   **Then** JWKS retrieval is not triggered
   **And** it is triggered only by the first Bearer request that needs it

3. **Given** persona seeding and development keypair generation
   **When** each runs
   **Then** keypair generation is computation and seeding is a database write
   **And** neither reaches a registry, the IdP, or a package index

4. **Given** environment installation downloads packages by definition
   **When** this requirement is scoped
   **Then** the claim begins once the environment exists

## Tasks / Subtasks

- [ ] Task 1: Build the no-network guard as a shared fixture (AC: #1, #2, #3)
  - [ ] Add a `no_network` fixture to `tests/conftest.py` (UPDATE) so both `tests/unit/` and `tests/integration/` can use it.
  - [ ] Implement it by monkeypatching the lowest common chokepoints: `socket.socket.connect`, `socket.socket.connect_ex` and `socket.create_connection`, each raising a narrow, named exception (define `class NetworkAccessAttempted(RuntimeError)` in the same module) whose message includes the attempted address. Do not patch `requests`, `urllib` or `httpx` individually — a guard at the library level misses whichever library the code actually used.
  - [ ] Leave loopback alone only if a test genuinely needs it (the Django test client does not open sockets); prefer blocking everything and letting a failure name the caller.
  - [ ] The fixture must restore the originals on teardown; `monkeypatch` does this for you. Never leave it autouse — a globally blocked socket would mask a real dependency rather than assert one.

- [ ] Task 2: Assert settings import and Django setup make no request (AC: #1)
  - [ ] Create `tests/unit/test_no_network_at_boot.py` (NEW).
  - [ ] `test_settings_import_performs_no_network_call`: under `no_network`, evict `config.settings.base`/`local` from `sys.modules` (the eviction idiom is documented in `tests/unit/test_settings.py:1-30`) and re-import them. Assert no `NetworkAccessAttempted` is raised.
  - [ ] `test_django_setup_performs_no_oidc_discovery`: under `no_network`, run a full `django.setup()` in a subprocess or with a fresh app registry and assert it completes. The specific thing being asserted is that allauth's OpenID Connect provider does **not** fetch the issuer's discovery document at configuration time: AD-31 requires the provider to be configured "from `SOCIALACCOUNT_PROVIDERS` populated from the environment, never database-resident `SocialApp` rows", and reading configuration is not fetching it.
  - [ ] `test_entrypoint_observability_configuration_performs_no_network_call`: under `no_network` with no `OTEL_EXPORTER_OTLP_ENDPOINT` set, call `config.observability.configure_observability()` and assert it completes. This is the call `manage.py:29-31` and `src/config/celery_app.py:12` make on every invocation.
  - [ ] If any of these fail, the fix is to make the offending call lazy — never to narrow the guard, and never to mark the test `xfail`.

- [ ] Task 3: Assert JWKS retrieval is lazy and is triggered by the first Bearer request (AC: #2)
  - [ ] In the same test module, `test_jwks_is_not_retrieved_at_boot`: under `no_network`, complete boot and assert Story 2.7's module-level `KEY_STORE` in `src/config/authorization/jwks.py` holds no keys and that its fetch seam was not called. Story 2.7 already builds a patchable fetch seam for exactly this purpose — use it rather than adding one.
  - [ ] `test_jwks_is_retrieved_on_the_first_bearer_request_that_needs_it`: with the fetch seam spied (not the socket blocked), assert it is called zero times after boot and exactly once after the first Bearer request whose `kid` is uncached, and zero further times for a second request carrying the same `kid`. The second half is what distinguishes lazy retrieval from per-request retrieval.
  - [ ] Do **not** implement the retrieval, the `kid` cache or the rate limiter here — they are Story 2.7's `JWKSKeyStore`, built as component code wrapping PyJWT (AD-23). This story asserts the timing property they must have. Story 2.7 carries its own import-time assertion; this story's contribution is the *boot* assertion — a full `django.setup()` under a blocked socket, which no test in Epic 2 performs.

- [ ] Task 4: Assert seeding and keypair generation stay local (AC: #3)
  - [ ] `test_keypair_generation_performs_no_network_call`: under `no_network` and with `DEV_KEY_DIR` pointed at `tmp_path`, call `ensure_keypair()` (Story 3.5) and assert it completes. RSA key generation is computation; if this test fails, something is fetching entropy or a key over a socket and must be changed.
  - [ ] `test_persona_seeding_performs_no_network_call`: `@pytest.mark.integration`, in `tests/integration/test_local_dev_seeding.py` (the file Story 3.3 creates — extend it rather than adding a second seeding test module). Under `no_network` and with `COMPONENT_RUNTIME=local`, run `seed_personas()` and assert it completes. Seeding is a database write against the substituted sqlite backend and reaches nothing else.
  - [ ] Neither test may reach a package index. Nothing in the runtime path invokes `pixi`, `pip` or a build; if a test does, that is the defect.

- [ ] Task 5: State the scope boundary (AC: #4)
  - [ ] In `docs/development.md`, in the `## Running with no external services` section, add an explicit sentence: nothing on the local start path reaches the network at boot — OIDC discovery and JWKS retrieval are lazy and happen on first use — **and** the claim begins once the environment exists, because environment installation downloads packages by definition.
  - [ ] Say the same thing in the module docstring of `tests/unit/test_no_network_at_boot.py`, so a reader of the test knows what it does and does not claim. FR-23's own "Out of Scope" line is the wording to follow.

- [ ] Task 6: Keep the boot path free of eager work (AC: #1, #2, #3)
  - [ ] Audit the boot path for anything that would need the network or would do expensive work at import: `manage.py`, `src/config/asgi.py`, `src/config/wsgi.py`, `src/config/celery_app.py`, `src/config/settings/*.py`, `src/config/observability/__init__.py`, `src/django_service/users/apps.py`.
  - [ ] `src/django_service/users/apps.py:9-12` has an empty `ready()` today. When Epic 4 gives an immovable-core `AppConfig.ready()` the stage-2 refusals (AD-26), those checks must make no network call and no query beyond migration state (NFR-1). Record that constraint in a comment now so the later story inherits it.
  - [ ] Do **not** call `ensure_keypair()`, `seed_personas()`, JWKS retrieval or OIDC discovery from any of these modules.

## Dev Notes

### Architecture Constraints

**FR-23 — Nothing on the local start path reaches the network at boot.** "OIDC discovery and JWKS retrieval occur lazily on first use, never at import or at boot, so a component starts with no route to the IdP." Testable consequences, verbatim:

> - A unit test asserts that importing the settings and completing Django setup performs no OIDC discovery request.
> - A unit test asserts that JWKS retrieval is not triggered by boot, only by the first Bearer request that needs it (FR-5).
> - Persona seeding and development keypair generation are local operations: keypair generation is computation, seeding is a database write, and neither reaches a registry, the IdP, or a package index.

And its **Out of Scope**: "Environment installation, which downloads packages by definition. The claim begins once the environment exists."

**AD-23 — JWKS rotation is solved by key ID, and we build it.** Binding rule: "JWKS is fetched lazily on the first Bearer request that needs it, never at import or boot. Keys are cached by `kid`. A token presenting an uncached `kid` triggers one refetch, rate-limited so an attacker cannot drive fetches. TTL is a backstop for key removal only." *Prevents:* "a cache TTL that must be tuned against an IdP policy nobody has published; **a boot that reaches the network**; and the assumption that the library already does this."

This story owns the "boot that reaches the network" half as an assertion. Story 2.7 owns the retrieval, the `kid` cache and the rate limiter. Do not build a second retrieval path here, and do not weaken the rate limiter to make a test simpler.

**AD-31 — Identity-provider configuration is settings-resident.** "allauth's OIDC provider is configured from `SOCIALACCOUNT_PROVIDERS` populated from the environment, never from database-resident `SocialApp` rows, which a component forbidden to migrate itself could never create." Configuration-from-environment is what makes AC #1 achievable: a provider whose configuration lives in the database would need a query at boot, and a provider that resolved its endpoints by discovery would need a request.

**NFR-1 — Startup fails fast and cheaply.** "Misconfiguration surfaces at boot as `ImproperlyConfigured`, never as scattered runtime errors; the checks make no network call and no query beyond migration state." The refusal contract Epic 4 adds to the boot path inherits this story's property; Task 6's comment is what carries it forward.

**AD-13.** Locality is read from the environment — an environment read, not a network call. Nothing in the locality determination may reach a metadata service, a discovery endpoint, or a platform API.

**R-5.** Asserting that boot is silent proves the component starts offline. It does not prove the IdP integration works; synthetic claims never exercise JWKS retrieval or rotation, and SC-6 stays unproven until a real IdP exists to test against.

**Never:** narrow the socket guard to make a failing assertion pass; patch a specific HTTP library instead of the socket layer; mark any of these tests `skip` or `xfail` without a linked open issue; call seeding, keypair generation, discovery or JWKS retrieval from an import-time path.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `tests/conftest.py` | UPDATE | Add `NetworkAccessAttempted` and the `no_network` fixture (socket-layer guard, not autouse). |
| `tests/unit/test_no_network_at_boot.py` | NEW | Settings import, `django.setup()`, `configure_observability()`, JWKS laziness, keypair generation — all under `no_network`. |
| `tests/integration/test_local_dev_seeding.py` | UPDATE | Add the seeding-under-`no_network` test to the file Story 3.3 creates. |
| `src/django_service/users/apps.py` | UPDATE | Comment in `ready()` recording the no-network / no-query-beyond-migration-state constraint the Epic 4 stage-2 checks inherit. |
| `docs/development.md` | UPDATE | The lazy-at-boot statement and the environment-installation scope boundary. |

**`tests/conftest.py` today (verified, 20 lines).** Imports `UserFactory` from `tests.factories`; declares an autouse `_media_storage` fixture (`:13-15`) that repoints `settings.MEDIA_ROOT` at `tmpdir`, and a `user` fixture (`:18-20`) depending on `db`. Preserve both; append the new fixture rather than restructuring the file.

**`tests/unit/conftest.py` today (verified).** Docstring only: "Unit tests must not touch the database, the network or the filesystem; add fixtures here only if they hold to that." This story's guard is the enforcement of the network half; put it in `tests/conftest.py` because the integration seeding test needs it too.

**`manage.py` today (verified, 37 lines).** Sets `DJANGO_SETTINGS_MODULE` default to `config.settings.local` at `:11`, inserts `src/` on `sys.path` at `:22-25`, then imports and calls `configure_observability()` at `:29-31` before `execute_from_command_line`. **Do not remove the `sys.path` insert here** — collapsing the five import-root declaration sites to one is AD-7 and Epic 1's work, and doing it in this story would break the boot path this story is asserting about.

**`src/config/celery_app.py` today (verified, 37 lines).** Sets the settings-module default at `:10`, calls `configure_observability()` at `:12` **at module import**, constructs the `Celery` app, adds `DjangoStructLogInitStep`, configures from Django settings with the `CELERY_` namespace, and autodiscovers tasks at `:37`. The import-time `configure_observability()` call is exactly why Task 2's third assertion matters.

**`src/config/settings/base.py` today.** `configure_structlog()` runs at settings-import time (`:287`) and `LOGGING` is built at `:282-286` — both local computation. `REDIS_URL` is read at `:293` but no connection is opened. The Celery block at `:296-335` sets `CELERY_BROKER_URL` without connecting.

**`src/django_service/users/apps.py` today (verified, 12 lines).** `UsersConfig` with `name = "django_service.users"`, `verbose_name`, and a `ready()` whose body is a docstring only.

**Dependencies on earlier stories — concrete names.** `config.authorization.jwks.KEY_STORE` / `JWKSKeyStore` and its patchable fetch seam (Story 2.7); `config.local_dev.keys.ensure_keypair()` and `DEV_KEY_DIR` (Story 3.5); `config.local_dev.seeding.seed_personas()` (Story 3.3); `config.locality` (Story 3.1); `settings.CLAIMS_CONTRACT` (Story 2.2). Sequence this story last within the epic, since four of its six assertions are about surfaces those stories create.

### Testing Requirements

- `tests/unit/test_no_network_at_boot.py` is a unit module: no database, no real network (by construction), filesystem only via `tmp_path`. The `django.setup()` assertion may need a subprocess to get a clean app registry — if so, invoke it with `sys.executable` from inside the already-active pixi environment; never shell out to `pip`, `uv` or a bare `python`.
- The seeding assertion is an integration test and carries `@pytest.mark.integration`, uses `db`, and leaves state as found.
- Every assertion here is a *negative* assertion, which is the failure mode to guard against: a negative test that never executes the code under test passes trivially. Each test must assert that the operation **completed** (a positive post-condition — settings module imported, `django.setup()` returned, personas materialized, keypair written) in addition to no `NetworkAccessAttempted` being raised.
- Coverage floor: ninety percent including templates (AD-20), `COVERAGE_CORE=ctrace`, `--cov-fail-under=90`. `pixi run ci` must exit 0.
- Test disposition: `core`, under `tests/` mirroring `src/`.
- Run with `pixi run test` / `pixi run test-integration`; never bare `pytest`.

#### Project Structure Notes

This story adds no source module. Its one source-tree edit is a forward-looking comment in `src/django_service/users/apps.py`; note that `UsersConfig` is *not* necessarily the immovable-core app AD-26 designates as stage 2's owner — that app is "declared in `accelerator.toml`" and chosen in Epic 4, and a gate test there asserts no adopted app precedes it in `INSTALLED_APPS`. Do not designate it here.

Aligned with the spine's test-location convention: accelerator and base tests live under `tests/` mirroring `src/` and carry the disposition of what they cover. These cover `core` boot-path surface.

### References

- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-23] — the three consequences and the out-of-scope line.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#NFR-1]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md:189] — "Retrieval is lazy: JWKS is fetched on the first Bearer request that needs it, never at import or at boot. A component must boot with no route to the IdP."
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-23] · [#AD-31] · [#AD-26] · [#AD-13] · [#AD-7]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-5.
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.7] · [#Story 2.7] · [#Story 3.3] · [#Story 3.5]
- [Source: tests/conftest.py:13-20] · [Source: tests/unit/conftest.py] · [Source: tests/unit/test_settings.py:1-30]
- [Source: manage.py:11,22-31] · [Source: src/config/celery_app.py:10-12,37] · [Source: src/config/settings/base.py:282-296] · [Source: src/django_service/users/apps.py:9-12]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
