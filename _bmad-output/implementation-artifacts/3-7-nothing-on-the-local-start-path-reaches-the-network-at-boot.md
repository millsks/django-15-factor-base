---
baseline_revision: edd2cf1
review_loop_iteration: 0
status: done
followup_review_recommended: true
warnings: [oversized]
---

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

- [x] Task 1: Build the no-network guard as a shared fixture (AC: #1, #2, #3)
  - [x] Add a `no_network` fixture to `tests/conftest.py` (UPDATE) so both `tests/unit/` and `tests/integration/` can use it. Append it; preserve the autouse `_media_storage` (`:13-15`) and `user` (`:18-20`) fixtures and the `tests.factories` import.
  - [x] Implement it by monkeypatching the lowest common chokepoints: `socket.socket.connect`, `socket.socket.connect_ex` and `socket.create_connection`, each raising a narrow, named exception (define `class NetworkAccessAttempted(RuntimeError)` in the same module) whose message includes the attempted address. Do not patch `requests`, `urllib` or `httpx` individually — a guard at the library level misses whichever library the code actually used.
  - [x] Restore explicitly, not with `monkeypatch`. `connect` and `connect_ex` are inherited from `_socket.socket`, so `monkeypatch.setattr(socket.socket, "connect", ...)` records the *inherited* implementation and undoes by binding it as an own attribute of the subclass — not the state it found. Capture `socket.socket.__dict__.get(name, _ABSENT)` and `delattr` on teardown when it was absent, inside a `try`/`finally`.
  - [x] Never autouse. `tests/integration/test_import_resolution.py:139,282` opens real sockets to find a free port and to wait for a served process; a global block would break those and would mask a real dependency rather than assert one. Loopback is blocked along with everything else — the Django test client opens no socket, and sqlite opens no socket, so nothing under test needs an exemption.

- [x] Task 2: Assert the whole boot completes with the socket blocked (AC: #1)
  - [x] Create `tests/unit/test_no_network_at_boot.py` (NEW).
  - [x] `test_settings_import_performs_no_network_call`: under `no_network`, evict `config.settings.base`/`local` from `sys.modules` and re-import them. Mirror the eviction idiom at `tests/unit/test_settings.py:51-58` — an autouse fixture that pops the four settings names before *and* after each case. Assert no `NetworkAccessAttempted` and a positive post-condition: the re-imported module exposes `DATABASES` and `OIDC_ISSUER`.
  - [x] `test_boot_performs_no_network_call` — the boot probe, and the assertion this story exists for. Run a fresh interpreter with `sys.executable -c`, using the environment idiom at `tests/integration/test_import_resolution.py:102-124` (drop `PYTHONPATH` and `DJANGO_SETTINGS_MODULE`, set `PYTHONSAFEPATH=1`), and inside the child: install the same three-chokepoint socket guard, then do what `manage.py` does — `configure_observability()` (`manage.py:29,38`), then `django.setup()` under `config.settings.local`. The child prints one JSON object; the parent asserts `returncode == 0` with `result.stderr` as the message and reads the post-conditions out of it. `subprocess.run` needs `# noqa: S603`, an explicit `timeout=`, and `check=False`.
  - [x] The subprocess is not an evasion of `tests/unit/conftest.py`'s "no database, no network, no filesystem" — it is the only place the property is literally true. pytest-django completes `django.setup()` at session start, so an in-process call is a no-op, and `configure_observability()` is guarded by `telemetry.py`'s `_configured` flag which `src/config/__init__.py:3` → `celery_app.py:13` has already set at collection. Say so in the test's docstring.
  - [x] Do **not** write `test_entrypoint_observability_configuration_performs_no_network_call` as an in-process call to `configure_observability()`. The `_configured` guard makes it execute nothing, which is exactly the negative test that passes without reaching the code under test. Clearing the guard with `reset_telemetry_for_testing()` is forbidden by Story 3.6 — it would let a later `configure_telemetry()` re-instrument Django, Celery, psycopg and redis for the rest of the session. The boot probe covers it honestly instead.
  - [x] `test_django_setup_performs_no_oidc_discovery`: in-process, under `no_network`, re-run the one piece of boot-time allauth work — `allauth.socialaccount.apps.SocialAccountConfig.ready()` is `checks` plus `providers.registry.load()`, and `load()` is guarded by `registry.loaded`. Set `registry.loaded = False` in a `try`/`finally` that restores `True`, call `registry.load()`, and assert it completes and that `registry.get_class("openid_connect")` is not `None`. `provider_map` is only added to, so re-loading is safe. This is the AD-31 property made observable: the provider is *configured* from `SOCIALACCOUNT_PROVIDERS` (`base.py:483-502`) and its discovery document is fetched by the request-time `openid_config` property in allauth's views, never at configuration time. Also assert `SOCIALACCOUNT_PROVIDERS["openid_connect"]["APPS"][0]["settings"]["server_url"]` is `settings.OIDC_ISSUER` — one env read, no fetch.
  - [x] If any of these fail, the fix is to make the offending call lazy — never to narrow the guard, and never to mark the test `skip` or `xfail` (`tests/unit/test_suite_policy.py:46,50` bans both mechanically).

- [x] Task 3: Assert JWKS retrieval is not triggered by boot (AC: #2)
  - [x] In the boot probe's child, after `django.setup()`, report `config.authorization.jwks.KEY_STORE`'s state: that `_keys` is empty, that `_fetched_at` is still `-inf`, and that `_fetch` is still the module default `fetch_jwks_document`. Assert all three in the parent. There is no public accessor — `__all__` (`jwks.py:88-95`) exposes the store and the seam, not the cache — so the reads carry `# noqa: SLF001`, which is the same reach `tests/integration/authorization/test_bearer_authentication.py:105-110` already takes.
  - [x] Assert it in the child rather than in-process. `KEY_STORE` is a module-level singleton (`jwks.py:782`) shared by the whole session, so an in-process "holds no keys" assertion is a statement about test ordering, not about boot.
  - [x] Do **not** write `test_jwks_is_retrieved_on_the_first_bearer_request_that_needs_it`. It already exists, in exactly the required shape, at `tests/integration/authorization/test_bearer_authentication.py:499-516` — `jwks_fetch.calls == 0` before any Bearer request, `== 1` after the first, and still `== 1` after a second request carrying the same `kid`, with `tests/jwt_keys.py:213 StubFetch` counting. Story 2.7 owns it; AC #2's second clause is traced to it, not re-implemented. Two tests of one property, as Story 3.6's change log recorded, is worse than one.
  - [x] Do **not** implement the retrieval, the `kid` cache or the rate limiter here — they are Story 2.7's `JWKSKeyStore` (`jwks.py:530-782`), built as component code wrapping PyJWT (AD-23). Note that `tests/unit/authorization/test_jwks.py:150-175` already asserts the two *module bodies* reach no network; this story's contribution is the whole process — settings import, `configure_observability()` and `django.setup()` together, under a blocked socket, which no test in Epic 2 performs.

- [x] Task 4: Assert seeding and keypair generation stay local (AC: #3)
  - [x] `test_keypair_generation_performs_no_network_call`: under `no_network`, relocate the key directory with `monkeypatch.setattr(keys, "DEV_KEY_DIR", tmp_path / ".local-dev-keys")` — `DEV_KEY_DIR` is a module constant (`config/local_dev/keys.py:84`), not an env var and not a setting, and the `key_dir` fixture at `tests/unit/test_local_dev_keys.py:42-46` is the idiom to copy. Call `ensure_keypair()` and assert the positive post-condition: the private key and `jwks.json` exist under `tmp_path` and the returned `kid` is non-empty. RSA key generation is computation; if this fails, something is fetching entropy or a key over a socket and must be changed.
  - [x] `ensure_keypair()` refuses unless `is_local()` (`keys.py:162-163`). The `dev` pixi environment already exports `COMPONENT_RUNTIME=local`, so no `setenv` is needed — but set it explicitly anyway so the case does not depend on an ambient variable.
  - [x] `test_persona_seeding_performs_no_network_call`: in `tests/integration/test_local_dev_seeding.py` (UPDATE — the file Story 3.3 created, 325 lines; extend it rather than adding a second seeding test module). Under `no_network`, with the existing autouse `_local` (`:73-76`) and `_contract` (`:79-87`) fixtures and `db: None`, run `seed_personas()` and assert it returns every declared persona key and that the users exist. Do not add `@pytest.mark.integration` by hand: `tests/integration/conftest.py:12` applies it to every item under the directory, and the module already sets `pytestmark` at `:56`.
  - [x] Neither test may reach a package index. Nothing in the runtime path invokes `pixi`, `pip` or a build; if a test does, that is the defect.

- [x] Task 5: State the scope boundary (AC: #4)
  - [x] In `docs/development.md`, add a `### Nothing on the start path reaches the network` subsection to `## Running with no external services` (`:401-462`). That section documents *substitution* today and says nothing about boot; the claim currently lives only in code comments (`base.py:472-475`, `jwks.py:777-781`). State: nothing on the local start path reaches the network at boot — OIDC discovery and JWKS retrieval are lazy and happen on first use — **and** the claim begins once the environment exists, because environment installation downloads packages by definition.
  - [x] Name the one deliberate opt-in that breaks it, rather than leaving the claim absolute: `OTEL_TRACES_EXPORTER=otlp` set by hand with no endpoint attaches a batch processor to an exporter defaulting to `http://localhost:4318` at `configure_observability()` time (`telemetry.py:107-109,160`). It is already documented at `docs/development.md:427-429`; cross-reference it so the two statements cannot drift apart.
  - [x] Say the same thing in the module docstring of `tests/unit/test_no_network_at_boot.py`, so a reader of the test knows what it does and does not claim. FR-23's own "Out of Scope" line is the wording to follow.

- [x] Task 6: Keep the boot path free of eager work (AC: #1, #2, #3)
  - [x] Audit the boot path for anything that would need the network or would do expensive work at import: `manage.py`, `src/config/__init__.py`, `src/config/asgi.py`, `src/config/wsgi.py`, `src/config/celery_app.py`, `src/config/settings/*.py`, `src/config/observability/__init__.py`, `src/django_service/users/apps.py`. The audit is a read, not an edit: the tree is clean today and Task 2's probe is what keeps it that way.
  - [x] `src/django_service/users/apps.py:9-12` has an empty `ready()` today, and it is the only `def ready` in `src/`. When Epic 4 gives an immovable-core `AppConfig.ready()` the stage-2 refusals (AD-26), those checks must make no network call and no query beyond migration state (NFR-1). Record that constraint in a comment now so the later story inherits it. Do not designate `UsersConfig` as that app — AD-26's owner is declared in `accelerator.toml` and chosen in Epic 4.
  - [x] Do **not** call `ensure_keypair()`, `seed_personas()`, JWKS retrieval or OIDC discovery from any of these modules. Note that `src/config/__init__.py:3` imports `config.celery_app`, so *any* `import config.*` — a bare settings import included — runs `configure_observability()`; anything added to that call is on the boot path whether or not it looks like it.

## Dev Notes

### Architecture Constraints

**FR-23 — Nothing on the local start path reaches the network at boot.** "OIDC discovery and JWKS retrieval occur lazily on first use, never at import or at boot, so a component starts with no route to the IdP." Testable consequences, verbatim:

> - A unit test asserts that importing the settings and completing Django setup performs no OIDC discovery request.
> - A unit test asserts that JWKS retrieval is not triggered by boot, only by the first Bearer request that needs it (FR-5).
> - Persona seeding and development keypair generation are local operations: keypair generation is computation, seeding is a database write, and neither reaches a registry, the IdP, or a package index.

And its **Out of Scope**: "Environment installation, which downloads packages by definition. The claim begins once the environment exists."

**AD-23 — JWKS rotation is solved by key ID, and we build it.** Binding rule: "JWKS is fetched lazily on the first Bearer request that needs it, never at import or boot. Keys are cached by `kid`. A token presenting an uncached `kid` triggers one refetch, rate-limited so an attacker cannot drive fetches. TTL is a backstop for key removal only." *Prevents:* "a cache TTL that must be tuned against an IdP policy nobody has published; **a boot that reaches the network**; and the assumption that the library already does this."

This story owns the "boot that reaches the network" half as an assertion. Story 2.7 owns the retrieval, the `kid` cache and the rate limiter. Do not build a second retrieval path here, and do not weaken the rate limiter to make a test simpler.

**The trust-anchor check is syntactic, and this story is why.** AD-23: "Verifying a JWKS location against the issuer's published discovery document requires fetching it, which is the boot-time network call FR-23 forbids — so startup can only apply a string-derivation rule over the configured issuer. An issuer whose real `jwks_uri` does not match the derivation surfaces on the first Bearer request, not at boot." "Derived from" is not "confirmed against". If an assertion in this story fails because something fetches a discovery document at boot, the fix is to make that fetch lazy — never to accept the fetch and narrow the guard.

**AD-31 — Identity-provider configuration is settings-resident.** "allauth's OIDC provider is configured from `SOCIALACCOUNT_PROVIDERS` populated from the environment, never from database-resident `SocialApp` rows, which a component forbidden to migrate itself could never create." Configuration-from-environment is what makes AC #1 achievable: a provider whose configuration lives in the database would need a query at boot, and a provider that resolved its endpoints by discovery would need a request.

**NFR-1 — Startup fails fast and cheaply.** "Misconfiguration surfaces at boot as `ImproperlyConfigured`, never as scattered runtime errors; the checks make no network call and no query beyond migration state." The refusal contract Epic 4 adds to the boot path inherits this story's property; Task 6's comment is what carries it forward.

**AD-13.** Locality is read from the environment — an environment read, not a network call. Nothing in the locality determination may reach a metadata service, a discovery endpoint, or a platform API.

**R-5.** Asserting that boot is silent proves the component starts offline. It does not prove the IdP integration works; synthetic claims never exercise JWKS retrieval or rotation, and SC-6 stays unproven until a real IdP exists to test against.

**Never:** narrow the socket guard to make a failing assertion pass; patch a specific HTTP library instead of the socket layer; mark any of these tests `skip` or `xfail` without a linked open issue; call seeding, keypair generation, discovery or JWKS retrieval from an import-time path.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `tests/conftest.py` | UPDATE | Add `NetworkAccessAttempted` and the `no_network` fixture (socket-layer guard, not autouse). |
| `tests/unit/test_no_network_at_boot.py` | NEW | The subprocess boot probe (settings import, `configure_observability()`, `django.setup()`, `KEY_STORE` still empty), the in-process settings re-import, the allauth provider-registry load, and keypair generation — all under a blocked socket. |
| `tests/integration/test_local_dev_seeding.py` | UPDATE | Add the seeding-under-`no_network` test to the file Story 3.3 created (325 lines today). |
| `src/django_service/users/apps.py` | UPDATE | Comment in `ready()` recording the no-network / no-query-beyond-migration-state constraint the Epic 4 stage-2 checks inherit. |
| `docs/development.md` | UPDATE | A new `### Nothing on the start path reaches the network` subsection: the lazy-at-boot statement, the environment-installation scope boundary, and the `OTEL_TRACES_EXPORTER=otlp` exception. |

**`tests/conftest.py` today (verified, 20 lines).** Imports `UserFactory` from `tests.factories`; declares an autouse `_media_storage` fixture (`:13-15`) that repoints `settings.MEDIA_ROOT` at `tmpdir`, and a `user` fixture (`:18-20`) depending on `db`. Preserve both; append the new fixture rather than restructuring the file.

**`tests/unit/conftest.py` today (verified).** Docstring only: "Unit tests must not touch the database, the network or the filesystem; add fixtures here only if they hold to that." This story's guard is the enforcement of the network half; put it in `tests/conftest.py` because the integration seeding test needs it too.

**`manage.py` today (re-verified at `edd2cf1`, 44 lines).** Sets `DJANGO_SETTINGS_MODULE` default to `config.settings.local` at `:10`, imports `execute_from_command_line` behind an explanatory `ImportError` re-raise at `:12-19`, imports `configure_observability` behind a second one at `:28-36`, calls it at `:38`, then `execute_from_command_line(sys.argv)` at `:40`. **There is no `sys.path` insert.** AD-7 landed in Epic 1: the comment at `:24-27` records its removal, and the one import-root declaration is now `pyproject.toml [tool.hatch.build.targets.wheel]` (`:170-176`). The 2026-08-15 draft's instruction not to remove the insert, and its note about `[tool.pytest.ini_options] pythonpath` at `:149` being what makes `tests.factories` importable, are both about a tree that no longer exists — there is no `pythonpath` key, and `tests/` resolves as a real package (`tests/__init__.py`) under `--import-mode=importlib` (`pyproject.toml:193`). See Spec Change Log entries 1 and 2.

**`src/config/celery_app.py` today (re-verified, 52 lines).** Sets the settings-module default at `:11`, calls `configure_observability()` at `:13` **at module import**, constructs the `Celery` app at `:15`, adds `DjangoStructLogInitStep` at `:19`, configures from Django settings with the `CELERY_` namespace by *string* at `:25` (lazy — settings are not loaded there), and autodiscovers tasks at `:52` (also lazy — a callback keyed off `INSTALLED_APPS`). Nothing here opens a socket: `Celery(...)` construction does not connect, and the broker is reached on first publish or consume. And `src/config/__init__.py:3` imports this module, so **any** `import config.*` — a bare settings import included — runs `configure_observability()`. That is why the boot probe is a fresh interpreter and not an in-process call: by the time a test runs, the `_configured` guard is already set.

**`src/config/settings/base.py` today (re-verified).** `build_logging_config(...)` runs at `:372` and `configure_structlog()` at `:378` — both local computation. `REDIS_URL` is read at `:384` but no connection is opened. `env.read_env(...)` at `:26` is a **file** read, gated on `DJANGO_READ_DOT_ENV_FILE`. `reverse_lazy("openid_connect_login", ...)` at `:221` is lazy, so no URLconf is loaded at settings import. The `SOCIALACCOUNT_PROVIDERS` block at `:483-502` sets `server_url` to the raw `COMPONENT_OIDC_ISSUER` read at `:481`; the `/.well-known/openid-configuration` suffix and the fetch belong to allauth's request-time `openid_config` property, and the comment at `:472-475` already states that nothing here, in an `AppConfig.ready()`, or in a system check may fetch it. `OIDC_JWKS_URL` at `:516` is likewise a string; the only `requests.get` in `src/` is `jwks.py:439`, inside a function.

**`src/django_service/users/apps.py` today (re-verified, 13 lines).** `UsersConfig` with `name = "django_service.users"`, `verbose_name`, and a `ready()` at `:9-12` whose body is a docstring only. It is the only `def ready` in the whole `src/` tree.

**Dependencies on earlier stories — concrete names.** `config.authorization.jwks.KEY_STORE` / `JWKSKeyStore` and its patchable fetch seam (Story 2.7); `config.local_dev.keys.ensure_keypair()` and `DEV_KEY_DIR` (Story 3.5); `config.local_dev.seeding.seed_personas()` (Story 3.3); `config.locality` (Story 3.1); `settings.CLAIMS_CONTRACT` (Story 2.2). Sequence this story last within the epic, since four of its six assertions are about surfaces those stories create.

### Testing Requirements

- `tests/unit/test_no_network_at_boot.py` is a unit module: no database, no real network (by construction), filesystem only via `tmp_path`. The boot assertion **does** need a subprocess, and it is the point of the module rather than a fallback — pytest-django completes `django.setup()` at session start and the telemetry `_configured` guard is already set at collection, so both are no-ops in process. Invoke it with `sys.executable` from inside the already-active pixi environment; never shell out to `pip`, `uv` or a bare `python`. `subprocess.run` carries `# noqa: S603` (ruff's `S` group is selected), an explicit `timeout=`, `check=False` and a returncode assertion whose message is `result.stderr` — the shape at `tests/integration/test_import_resolution.py:378-388`.
- The seeding assertion is an integration test, uses `db`, and leaves state as found. It needs no hand-written `@pytest.mark.integration`: `tests/integration/conftest.py:12` applies the marker to every item under the directory and `tests/integration/test_local_dev_seeding.py:56` already sets `pytestmark`.
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
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md:197] — "Retrieval is lazy: JWKS is fetched on the first Bearer request that needs it, never at import or at boot. A component must boot with no route to the IdP."
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-23] · [#AD-31] · [#AD-26] · [#AD-13] · [#AD-7]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-5.
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.7] · [#Story 2.7] · [#Story 3.3] · [#Story 3.5]
- [Source: tests/conftest.py:13-20] · [Source: tests/unit/conftest.py] · [Source: tests/unit/test_settings.py:1-30]
- [Source: manage.py:10,24-40] · [Source: src/config/__init__.py:3] · [Source: src/config/celery_app.py:11-13,52] · [Source: src/config/settings/base.py:372-384,472-502] · [Source: src/django_service/users/apps.py:9-12]
- [Source: src/config/authorization/jwks.py:88-95,373,530-573,782] · [Source: tests/integration/authorization/test_bearer_authentication.py:499-516] · [Source: tests/jwt_keys.py:213] · [Source: tests/unit/authorization/test_jwks.py:143-175]
- [Source: src/config/local_dev/keys.py:84,146-196] · [Source: tests/unit/test_local_dev_keys.py:42-46] · [Source: src/config/local_dev/seeding.py:64-109] · [Source: tests/integration/test_local_dev_seeding.py:56,73-87]
- [Source: src/config/observability/telemetry.py:107-109,153,160] · [Source: docs/development.md:401-462] · [Source: tests/unit/test_suite_policy.py:46,50] · [Source: tests/integration/test_import_resolution.py:102-124,139,282,378-388]

## Spec Change Log

Reconciliation pass against the tree at `edd2cf1`, before any code was written. The Dev Notes were
authored 2026-08-15; Epic 1's import-root work and Stories 2.7, 3.1-3.6 have landed since, and ten
claims did not survive re-reading. Each is corrected in place above.

1. **`manage.py` no longer inserts `src/` on `sys.path`, and the Dev Notes' warning not to remove it
   describes a tree that no longer exists.** The file is 44 lines, not 37. AD-7 landed in Epic 1: the
   one import-root declaration is `pyproject.toml [tool.hatch.build.targets.wheel]` (`:170-176`), and
   `manage.py:24-27` now carries a comment saying the insert is gone. The `# noqa: E402` that went with
   it is gone too (`asgi.py:18-23`). `configure_observability()` is at `manage.py:38`, its guarded
   import at `:29-36`.

2. **There is no `pythonpath` key in `[tool.pytest.ini_options]`.** The Dev Notes' note about
   `pyproject.toml:149` being what makes `tests.factories` importable from `tests/conftest.py`, and
   the warning that Epic 1 would later break it, are both stale — Epic 1 already removed it
   (`pyproject.toml:139` records the removal). `tests/` is a real package (`tests/__init__.py`,
   `tests/unit/__init__.py`, `tests/integration/__init__.py` all exist) and `--import-mode=importlib`
   (`:193`) is what resolves it. Nothing in this story needs to pre-empt or preserve anything there.

3. **Every other line number in the Dev Notes was stale.** `src/config/celery_app.py` is 52 lines and
   calls `configure_observability()` at `:13`, not `:12`; `autodiscover_tasks()` is `:52`, not `:37`.
   In `src/config/settings/base.py`, `configure_structlog()` is `:378` not `:287`, `build_logging_config`
   `:372` not `:282-286`, the `REDIS_URL` read `:384` not `:293`, and the Celery block `:388-425` not
   `:296-335`. `src/django_service/users/apps.py` is 13 lines with `ready()` at `:9-12`.

4. **`test_entrypoint_observability_configuration_performs_no_network_call` cannot be written the way
   Task 2 asked, and would have passed without executing anything.** `configure_telemetry` is guarded
   by a `_configured` flag (`telemetry.py:153`), and `src/config/__init__.py:3` → `celery_app.py:13`
   sets it at collection time — so any in-process `configure_observability()` in a test returns
   `False` having done nothing. Clearing the guard with `reset_telemetry_for_testing()` is closed by
   Story 3.6's change-log entry 10: it would let a later `configure_telemetry()` instrument Django,
   Celery, psycopg and redis a second time for the rest of the session. The call is asserted inside the
   subprocess boot probe instead, where it genuinely runs for the first time. This is the exact failure
   mode the story's own Testing Requirements name — a negative test that never reaches the code under
   test — and it was in the task list.

5. **AC #2's second clause is already implemented and must not be implemented again.**
   `tests/integration/authorization/test_bearer_authentication.py:499-516`
   (`test_the_first_bearer_request_is_what_fetches_the_jwks`) asserts `jwks_fetch.calls == 0` before any
   Bearer request, `== 1` after the first, and still `== 1` after a second request with the same `kid` —
   the zero/one/one shape Task 3 specified, including the half that distinguishes lazy retrieval from
   per-request retrieval. Story 2.7 owns it. Task 3 now traces to it rather than adding a duplicate,
   for the reason Story 3.6's change-log entry 6 gave: two tests of one property, one of which is the
   weaker, is worse than one.

6. **The "fetch seam" is a constructor default, not an attribute the store owns by name.**
   `fetch_jwks_document` (`jwks.py:373`) is a module-level function passed as
   `JWKSKeyStore.__init__`'s `fetch` default (`:543-548`) and stored at `:564`. Tests reach it as
   `KEY_STORE._fetch` with `# noqa: SLF001` (`tests/integration/authorization/test_bearer_authentication.py:105-110`,
   `tests/integration/test_credential_surface.py:96`) or by constructing a store with an injected
   `tests/jwt_keys.py:213 StubFetch`. There is no public accessor for the `kid` cache either, so the
   boot assertion reads `_keys`, `_fetched_at` and `_fetch` behind the same marker.

7. **"`KEY_STORE` holds no keys after boot" is not assertable in-process.** `KEY_STORE` is a
   module-level singleton (`jwks.py:782`) shared by the whole session, and the integration suite fills
   and resets it. An in-process assertion would be a statement about test ordering. It moves into the
   subprocess boot probe, which is the only context in which "after boot" is literally true.

8. **`monkeypatch` does not restore `socket.socket.connect` to the state it found.** Task 1 said it
   does. `connect` and `connect_ex` are inherited from `_socket.socket`, so `monkeypatch.setattr`
   records the inherited implementation and undoes by binding it as an *own* attribute on the
   subclass. The fixture saves `socket.socket.__dict__.get(name)` and `delattr`s on teardown when the
   name was absent.

9. **The socket guard must not be autouse for a concrete reason, not only a general one.**
   `tests/integration/test_import_resolution.py:139,282` opens real `AF_INET` sockets to find a free
   port and to wait for a served process to accept connections. `tests/conftest.py` is still the right
   home — the integration seeding test needs the fixture — but an autouse guard there would fail those
   four subprocess cases outright.

10. **`docs/development.md` has nowhere for Task 5 to append to.** The Dev Notes assumed the
    no-network claim was already stated in `## Running with no external services`; it is not stated
    anywhere in the file. That section (`:401-462`) documents the four substitutions and observability's
    non-substitution only. Task 5 adds a subsection rather than a sentence — and names the one
    deliberate opt-in that makes boot reach the network, `OTEL_TRACES_EXPORTER=otlp` with no endpoint
    (`telemetry.py:107-109,160`), already documented at `:427-429`. An absolute claim two paragraphs
    above its own documented exception is a claim that gets discovered rather than read.

Two corrections of smaller weight, applied without a numbered entry: `@pytest.mark.integration` on the
new seeding case is redundant — `tests/integration/conftest.py:12` applies it to every item under the
directory and the module already sets `pytestmark` (`:56`) — and the story's "test disposition: `core`"
needs no artifact, since no `test_*.py` in the tree carries a disposition marker and `accelerator.toml`
does not exist until Epic 7.

## Review Triage Log

### 2026-08-18 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 17: (high 0, medium 8, low 9)
- defer: 2
- reject: 10
- addressed_findings:
  - `[medium]` `[patch]` `NetworkAccessAttempted` derived from `RuntimeError` was swallowable: any boot-time call wrapped in `except Exception` would absorb the refusal, boot would complete, and every negative assertion in the module would pass while boot had genuinely reached the network. Re-derived from `BaseException`, in the fixture and in the child probe. This supersedes the spec's literal `class NetworkAccessAttempted(RuntimeError)`; the spec's intent — narrow, named, and it must fail the test — is served rather than contradicted, so it was patched rather than looped back.
  - `[medium]` `[patch]` A hostname lookup is a network round trip that reaches no `socket.socket`, so `socket.getaddrinfo` and `socket.gethostbyname` were added to the guard alongside the three chokepoints the spec named. The remaining blind spots — connectionless UDP, and I/O inside a C extension such as libpq — are now stated in the fixture docstring and in `docs/development.md` instead of being left implicit.
  - `[medium]` `[patch]` The guard installed its replacements before the `try`, so a failure part-way through installation would have left the socket layer patched process-wide with no teardown. Extracted `_network_guard()` as a context manager that installs inside the `try` and records each replacement only once it has been made; `no_network` is now a thin wrapper. `test_the_guard_restores_the_socket_layer_exactly` asserts the restore is exact, including that a name absent from `socket.socket.__dict__` before is absent after — the property Spec Change Log entry 8 exists for, previously asserted nowhere.
  - `[medium]` `[patch]` The boot probe booted an *unconfigured* issuer and its guard rail was unfalsifiable: `_boot_probe_env()` set no `COMPONENT_OIDC_ISSUER`, and `config/settings/local.py` unconditionally fills the empty value with a `.invalid` fallback, so `assert report["oidc_issuer"] != ""` was true no matter what. The child now boots with `COMPONENT_OIDC_ISSUER` set to the probe issuer and reports the provider block's `server_url` as well, both asserted equal to it — which is the assertion that actually says "a configured component performed no discovery".
  - `[medium]` `[patch]` The probe's verdict was a function of the developer's shell. `OTEL_SDK_DISABLED=1` installs no provider and would have failed `tracer_provider_installed` with the message "configure_observability() installed no tracer provider", precisely the wrong diagnosis; `OTEL_TRACES_EXPORTER=otlp` takes the documented opt-in this module says breaks the property. Those four variables are now scrubbed from the child environment, and the docstring says why the documented exception is excluded rather than inherited.
  - `[medium]` `[patch]` A refusal raised on a background thread never reached the child's exit code, so a boot-time connection from a worker thread would have passed green. The child now installs a `threading.excepthook` that collects `NetworkAccessAttempted`, reports them, and the parent asserts the list is empty.
  - `[medium]` `[patch]` `test_seeding_performs_no_network_call`'s docstring claimed the fixture ordering meant "a PostgreSQL run is asserting that seeding opens no socket". libpq does its I/O in C and never touches Python's `socket` module, so the guard cannot observe a database connection at all. The docstring now states what the test proves — seeding reaches no identity provider, registry or package index — and names the C-extension limit; a `connection.connection is not None` assertion pins the fixture ordering the prose relies on.
  - `[medium]` `[patch]` `docs/development.md`'s headline claim read as absolute while silently excluding the database — a PostgreSQL connection over TCP is a network call by any ordinary reading, and the integration test is deliberately ordered so the connection opens before the guard arms. Rescoped to the claim the bullets support: no call to the identity provider, a registry, or a package index.
  - `[medium]` `[patch]` `src/django_service/users/apps.py` gained a fourteen-line, three-paragraph comment whose final paragraph litigated Epic 4 / AD-26 ownership — content that belongs in the architecture record and would rot the moment Epic 4 lands, and a violation of this project's no-multi-paragraph-comment-blocks rule. Cut to four lines carrying only the constraint a future editor of that method needs.
  - `[low]` `[patch]` The module docstring argued the subprocess exists because an in-process `configure_observability()` "executes nothing at all" — but the child hits the same wall, since importing `config.observability` imports the `config` package, whose `__init__` imports `celery_app`, which calls it at import. What genuinely runs under the guard is that import. The docstring now says so and the assertion message no longer names a call that did nothing.
  - `[low]` `[patch]` `_guard_is_armed()` called `socket.create_connection` with no timeout, so on a host that filters rather than refuses port 9 it would block for the OS TCP connect timeout, twice per call and twice per run, inside a 180-second budget. Explicit short timeout added, `OSError` now returns `False` (a connection *refusal* means the guard was absent, not that it worked), and the success path closes the socket so an unexpected listener cannot leak a descriptor.
  - `[low]` `[patch]` A child that hung surfaced as a raw `subprocess.TimeoutExpired`. It now fails explicitly, naming the hung boot and including the captured output.
  - `[low]` `[patch]` Four assertions constrained nothing — `DATABASES["default"]["ENGINE"] != ""` twice, `installed_app_count > 0`, and `keypair.kid != ""` — which matters more than usual in a module whose stated central risk is a negative assertion over code that never ran. Replaced with post-conditions that prove the operation reached its end: the OIDC provider app present in the child's `INSTALLED_APPS`, the written `jwks.json`'s key id equal to the returned `kid`, and the dev-JWKS `file://` derivation near the end of `local.py`.
  - `[low]` `[patch]` `ensure_keypair()` has two branches and only generation was under the guard. A second call in the same test puts the load-an-existing-PEM branch under it too, asserted by the same `kid` coming back.
  - `[low]` `[patch]` `docs/development.md` presented keypair generation and seeding as "the two local operations a fresh clone performs" — a fresh clone also runs `migrate`. Rephrased so the two are the ones the section is about rather than all of them.
  - `[low]` `[patch]` Both the docs and the module docstring placed the `OTEL_TRACES_EXPORTER=otlp` exception's network call "at `configure_observability()` time". What happens then is the *attachment* of the batch processor; the outbound connection is made by the exporter's background thread shortly after boot. Corrected in both places.
  - `[low]` `[patch]` The guard's blind spots were stated only in test code. One sentence added where the claim is made in `docs/development.md`.

Deferred: Story 2.7's two "reaches no network" tests still guard `requests.get` rather than the socket layer; and the deployed start paths (`wsgi.py`, `asgi.py`, `config.settings.production`) have no boot probe. Both are recorded in `deferred-work.md`.

Rejected, with reasons: the boot probe living as a string literal rather than a linted file (the trade is reasoned in place, and a typo there fails loudly as a non-zero exit rather than silently); the objection that the trust-anchor check could compare against a lazily-fetched discovery document (an argument with AD-23, not a defect in this change); a unit test spawning a subprocess and writing to `tmp_path` (the spec sanctioned it, and `tests/unit/test_local_dev_keys.py` already writes keypairs there); a partially-loaded allauth provider registry if `load()` raised (the map is only added to and was already full); `env.read_env()` re-running on a settings re-import (pre-existing, and `tests/unit/test_settings.py` has always done it); a module holding a bound `create_connection` reference escaping the guard (its internal `sock.connect` is guarded); UDP `sendto`/`sendmsg` chokepoints (nothing in this stack sends UDP; the limit is documented instead); a production-settings boot probe inside this story (the story's title scopes it to the local start path — deferred rather than dropped); the new seeding test duplicating an existing test's post-condition (deliberate — a negative assertion needs its own positive one); and a second seeding pass under the guard (`test_seeding_is_idempotent` already covers the update branch).

## Auto Run Result

Status: done

### Summary

FR-23 made enforceable. The property held by accident before this story — no module on the start
path opens a socket — was asserted nowhere, and lived only in comments in `base.py` and `jwks.py`.
It is now a socket-layer guard shared by both suites and a boot probe that runs the real start path
in a fresh interpreter with every connect and every resolver call refused, then reports back what
boot left behind. The two Epic 2 tests that touched this property asserted module *bodies* under a
`requests.get` stub; nothing had ever booted the component under a blocked socket.

### Files changed

| Path | Change |
| --- | --- |
| `tests/conftest.py` | `NetworkAccessAttempted(BaseException)`, the `_network_guard()` context manager over five chokepoints (`socket.socket.connect`, `connect_ex`, `socket.create_connection`, `getaddrinfo`, `gethostbyname`) with an exact hand-written restore, and the non-autouse `no_network` fixture over it |
| `tests/unit/test_no_network_at_boot.py` | NEW — six tests: the guard refuses and names the address; the guard restores the socket layer exactly; settings import under the guard on both the configured-issuer and fresh-clone branches; the subprocess boot probe; the allauth provider-registry load; keypair generation and reuse |
| `tests/integration/test_local_dev_seeding.py` | One test: seeding under the guard, with the database connection pinned open before it arms |
| `src/django_service/users/apps.py` | The constraint an `AppConfig.ready()` inherits from FR-23 and NFR-1, recorded where the next editor of that method will read it |
| `docs/development.md` | `### Nothing on the start path reaches the network` — the lazy-discovery and lazy-JWKS statement, why the trust-anchor check is syntactic, the environment-installation scope boundary, the `OTEL_TRACES_EXPORTER=otlp` exception, and the guard's blind spots |
| `_bmad-output/implementation-artifacts/deferred-work.md` | Two new open entries |

### Review findings

17 patches applied (8 medium, 9 low), 2 deferred, 10 rejected. No intent gap and no spec defect: the
Spec Change Log had already corrected ten claims against the tree before any code was written, and
every review finding was a code- or doc-level fix inside the reconciled spec. The one patch that
deviates from the spec's literal text — `BaseException` in place of the prescribed `RuntimeError` —
serves the spec's stated intent rather than contradicting it, so it was patched rather than looped
back, and is recorded as such in the triage log.

### Verification

- `pixi run ci` exits 0. 929 passed, total coverage 96.39% against the 90% floor. Run twice
  independently of the implementation subagent, before and after the review patches.
- **The probe was seen to fail before it was believed.** Appending a module-level
  `socket.create_connection(("127.0.0.1", 9), timeout=1)` to `src/config/settings/local.py` failed
  both `test_boot_performs_no_network_call` (child exit 1, `NetworkAccessAttempted: a network
  connection to ('127.0.0.1', 9) was attempted during boot`, traceback naming `local.py:201`) and
  `test_settings_import_performs_no_network_call`. Appending
  `socket.getaddrinfo("example.invalid", 443)` failed the same two, which is what proves the resolver
  chokepoints added in review are live rather than decorative. Priming `KEY_STORE` at import failed
  the probe on `boot left keys in the store, so something fetched a JWK Set`. Each file was restored
  and the gate re-run to exit 0 after every mutation.
- The child reports whether its own guard was still armed on both sides of the boot it performed, and
  `test_the_guard_refuses_a_connection_rather_than_making_one` does the same job for the in-process
  fixture, so a green report cannot mean an uninstalled guard.
- The gate ran against sqlite, which is correct here: this story changes no model, no migration and
  no externally-supplied persisted value. The integration suite was additionally run against a real
  PostgreSQL 17 instance, because the seeding test blocks the socket layer around a database write
  and the fixture ordering it depends on is only meaningful against a TCP-backed database.

### Residual risks

- **The guard is a Python-socket guard, and libpq is not Python.** psycopg's I/O happens inside a C
  extension that never touches `socket`, so `test_seeding_performs_no_network_call` cannot observe a
  database connection — which is the honest reading of what it proves, and is now what its docstring
  and `docs/development.md` say. Any future dependency that does its networking in C is equally
  invisible.
- **Only the local start path is asserted.** `wsgi.py`, `asgi.py` and `config.settings.production`
  boot through the same `configure_observability()` call and are covered by NFR-1, but no probe boots
  them. Recorded in `deferred-work.md`; the probe generalises by parametrising its settings module.
- **The boot probe is a string literal**, so ruff, mypy and coverage all pass over it without
  looking. A mistake there surfaces as a non-zero child exit with a stderr traceback rather than
  silently, which is the right direction, but it is unverified code either way.
- **`KEY_STORE`'s state is read through three private attributes and one `repr(-inf)` comparison.**
  A rename in `jwks.py` turns the headline assertion into an `AttributeError` inside a subprocess; a
  change of the sentinel turns it into "boot recorded a fetch", a message that would send a reader
  hunting for a network call that never happened.
- **`docs/development.md` now carries the no-network claim in prose next to the code that enforces
  it.** Nothing reconciles the two: the enforcement paragraph names
  `tests/unit/test_no_network_at_boot.py` and the five chokepoints by hand, and a change to either
  leaves the other stale.

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (implementation and review-patch subagents: general-purpose, same model; three
review hunters run in parallel at the same model capability).

### Debug Log References

None. No harness loop was entered — `pixi run ci` passed on its first full invocation both after the
inner loop and after the review patches.

### Completion Notes List

**AC #2's second clause was traced, not re-implemented.** `test_the_first_bearer_request_is_what_
fetches_the_jwks` already exists at `tests/integration/authorization/test_bearer_authentication.py`
in exactly the shape the 2026-08-15 draft asked for — zero fetches before any Bearer request, one
after the first, still one after a second request carrying the same `kid`. Story 2.7 owns it. See
Spec Change Log entry 5.

**The observability assertion the draft asked for could not have failed.** `configure_telemetry` is
guarded by a `_configured` flag that `config/__init__.py` → `celery_app.py` sets at collection time,
so an in-process `configure_observability()` in a test executes nothing, and clearing the guard is
closed by Story 3.6. It is asserted inside the boot probe instead, where the import chain runs it for
the first time. See Spec Change Log entry 4.

**The probe reports positive post-conditions on purpose.** Every assertion in this story is negative,
and a negative assertion over code that never ran passes trivially — which the story's own Testing
Requirements name as the failure mode to guard against. So the child reports that its guard was armed
on both sides of the boot, that the app registry is ready, that the tracer provider was installed,
that the OIDC provider app is in `INSTALLED_APPS`, and that the configured issuer round-tripped into
the provider block, alongside the `KEY_STORE` state.

**Two branches were put under the guard that the task list did not ask for.** `ensure_keypair()`'s
load-an-existing-PEM path, and `config/settings/local.py`'s dev-JWKS `file://` derivation — the
latter only reachable with `COMPONENT_OIDC_ISSUER` unset, which is the fresh-clone case and was
previously unexercised under any guard.

**`monkeypatch` was deliberately not used for the socket layer.** `connect` and `connect_ex` are
inherited from `_socket.socket`, so `monkeypatch.setattr` would record the inherited implementation
and undo by binding it as an own attribute of the subclass. The guard saves
`socket.socket.__dict__.get(name)` and `delattr`s when the name was absent, and
`test_the_guard_restores_the_socket_layer_exactly` asserts that. See Spec Change Log entry 8.

**Out of scope, untouched as instructed:** Story 2.7's `JWKSKeyStore`, its `kid` cache and its rate
limiter; the deployed start paths (`wsgi.py`, `asgi.py`, `config.settings.production`); Epic 4's
stage-2 refusal contract, which `users/apps.py`'s comment points forward to without designating
`UsersConfig` as AD-26's owner; and `site/`, untracked mkdocs output.

### File List

| Path | Change |
| --- | --- |
| `tests/conftest.py` | UPDATE — `NetworkAccessAttempted(BaseException)`, `_network_guard()` over five socket chokepoints with an exact hand-written restore, and the non-autouse `no_network` fixture |
| `tests/unit/test_no_network_at_boot.py` | NEW — six tests covering the guard itself, its restore, settings import on two branches, the subprocess boot probe, the allauth provider-registry load, and keypair generation and reuse |
| `tests/integration/test_local_dev_seeding.py` | UPDATE — `test_seeding_performs_no_network_call`, with the database connection pinned open before the guard arms |
| `src/django_service/users/apps.py` | UPDATE — the FR-23 / NFR-1 constraint an `AppConfig.ready()` inherits, recorded in the empty `ready()` |
| `docs/development.md` | UPDATE — `### Nothing on the start path reaches the network`, with the scope boundary, the OTLP exception and the guard's blind spots |
| `_bmad-output/implementation-artifacts/deferred-work.md` | UPDATE — two new open entries |
