# Story 3.5: The local programmatic flow validates for real

Status: ready-for-dev

## Story

As a developer working on a generated component,
I want a locally minted token that the real Bearer authentication class genuinely verifies,
so that API authorization is exercised locally rather than stubbed.

## Acceptance Criteria

**Traceability:** FR-20 · NFR-7 · SC-4

1. **Given** a development task
   **When** it mints a token
   **Then** the token is a JWT signed by a locally generated keypair
   **And** local settings point the JWKS location at that key

2. **Given** the minted token
   **When** it is presented
   **Then** the real Bearer authentication class verifies signature, `iss`, `aud` and `exp`
   **And** no verification step is stubbed or skipped

3. **Given** a tampered or expired locally signed token
   **When** it is presented
   **Then** it is rejected

4. **Given** the keypair
   **When** it is created
   **Then** it is generated on demand into a gitignored path
   **And** it is never committed, because a key committed to a template would ship inside every component generated from it

## Tasks / Subtasks

- [ ] Task 0: Confirm the signing dependencies are declared (AC: #1)
  - [ ] `pixi.toml` `[dependencies]` does **not** carry `pyjwt` or `cryptography` today. The spine's Stack table pins PyJWT 2.13 and cryptography 50.0 and marks both "new". Story 2.7 declares them; if they are still absent when this story runs, add `pyjwt = ">=2.13,<3"` and `cryptography = ">=50.0,<51"` to `[dependencies]` (conda-forge), never to `[pypi-dependencies]`.
  - [ ] Both are imported directly by this story's code, so both are declared directly — the spine's supply-chain convention: "Transitive availability is not declaration: a package the code imports directly is declared directly, even when something else already pulls it in."
  - [ ] `tests/unit/test_dependency_policy.py` asserts `[pypi-dependencies]` holds only the project's own editable install. Adding either package to that table fails the gate, and correctly so.

- [ ] Task 1: Generate the keypair on demand into a gitignored path (AC: #1, #4)
  - [ ] Create `src/config/local_dev/keys.py` (NEW).
  - [ ] Declare the location as a module constant, `DEV_KEY_DIR: Path = BASE_DIR / ".local-dev-keys"`, derived from the repository root the same way `src/config/observability/__init__.py:32` does (`Path(__file__).resolve().parents[3]`). One declaration site; nothing else spells the directory name.
  - [ ] Implement `ensure_keypair() -> DevKeypair` (a frozen dataclass carrying `kid: str`, `private_key_path: Path`, `jwks_path: Path`): refuse when `config.locality.is_local()` is `False` (raise `ImproperlyConfigured`); create `DEV_KEY_DIR` with mode `0o700` if absent; if the private key file is absent, generate an RSA-2048 keypair with `cryptography` and write it as unencrypted PEM with file mode `0o600`; derive a stable `kid` from the public key (for example the base64url of its SHA-256 thumbprint) and write a JWKS document containing exactly that one public key to `jwks.json`. If the key already exists, load it and return — generation is on demand and idempotent, never on import.
  - [ ] Never generate at import time and never from a settings module. `ensure_keypair()` is called by the minting entry point and by tests, and by nothing that runs at boot (FR-23).
  - [ ] Add `.local-dev-keys/` to `.gitignore` (UPDATE), in the "Environments"/secrets area, with a comment: a key committed to a template ships inside every component generated from it, so one published private key would be shared by every service the accelerator ever produces.
  - [ ] Do **not** add the key to `[tool.hatch.build.targets.sdist] include` or to any packaging manifest.

- [ ] Task 2: Point the local JWKS location at the generated key (AC: #1, #2)
  - [ ] Story 2.7 reads the JWKS location from `COMPONENT_OIDC_JWKS_URL`, defaulting to the conventional derivation from `COMPONENT_OIDC_ISSUER`, and holds the key material in `JWKSKeyStore` / the module-level `KEY_STORE` at `src/config/authorization/jwks.py`. Use those names; do not introduce a second location variable or a second store.
  - [ ] Set the local value to `file://` + the absolute path of `DEV_KEY_DIR / "jwks.json"`. Set it in `src/config/settings/local.py` only — never in `base.py`, `test.py` or `production.py`.
  - [ ] The component's JWKS retrieval is component code wrapping PyJWT (AD-23), so it — not PyJWT's `PyJWKClient` — decides which schemes it accepts. Extend `JWKSKeyStore`'s fetch seam in `src/config/authorization/jwks.py` to read a `file://` location from disk and parse it into the same `kid`-keyed cache the HTTP path populates. Change **nothing** about signature, `iss`, `aud`, `exp` or `alg` verification, and leave the rate limiter (`COMPONENT_JWKS_MIN_REFETCH_SECONDS`) and TTL (`COMPONENT_JWKS_TTL_SECONDS`) behaviour intact.
  - [ ] This does not weaken the deployed trust anchor, and the guard is already in place: Story 2.7's `jwks_url_derives_from_issuer` explicitly **rejects** a `file://` URL, and the stage-1 trust-anchor refusal (AD-23, FR-13 condition 4, Epic 4) is what stops a `file://` location from reaching a deployed component. Do not relax that predicate to accommodate this story — the `file://` scheme is reachable locally precisely because the refusal does not apply where locality is local.
  - [ ] Reading a local file is not a network call and does not violate FR-23: retrieval stays lazy, triggered by the first Bearer request whose `kid` is uncached (Story 3.7 asserts this).

- [ ] Task 3: Mint the token (AC: #1, #2, #3)
  - [ ] Create `src/config/local_dev/tokens.py` (NEW) exposing `mint_token(persona_key: str, *, lifetime_seconds: int = 900, jti: str | None = None) -> str`.
  - [ ] Refuse when not local, first statement, the same way Stories 3.3 and 3.4 do.
  - [ ] Build the payload from `build_claims(get_persona(persona_key))` (Story 3.3 — the sole synthetic-claims constructor) and add the registered claims the Bearer class verifies: `iss` from `COMPONENT_OIDC_ISSUER` and `aud` from whatever audience setting Story 2.7's `OIDCBearerAuthentication` verifies against — read both from the same source that class reads, never from a literal — plus `exp` from `lifetime_seconds`, `iat`, and a `jti` (AD-10 rejects a token with no `jti` with 401).
  - [ ] Sign with `PyJWT` using `RS256`, the private key from `ensure_keypair()`, and a `kid` header matching the JWKS entry. `RS256` must be a member of Story 2.7's `ALLOWED_ALGORITHMS` (`COMPONENT_OIDC_ALGORITHMS`, default `["RS256"]`); do not widen that allowlist, and never let the token's own header choose the algorithm. Rotation is what `kid` exists for; a token minted without one cannot be matched to a key.
  - [ ] Do **not** add a verification bypass, a `verify_signature=False` path, a settings flag that relaxes audience checking, or a test-only authentication class. FR-20's whole point is that the real class verifies for real.
  - [ ] Create `src/config/local_dev/mint.py` (NEW) as the `python -m config.local_dev.mint <persona-key>` entry point: `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")`, `django.setup()`, parse the persona key from `sys.argv`, call `ensure_keypair()` then `mint_token()`, and emit the token as a structured `structlog` event — never `print`.
  - [ ] Add to `pixi.toml` `[tasks]`: `mint-token = { cmd = "python -m config.local_dev.mint", env = { COMPONENT_RUNTIME = "local" }, default-environment = "default", description = "Mint a development JWT for a local persona" }`.
  - [ ] Add `mint-token` to the `LOCAL_TASKS` data set in `tests/unit/test_locality_declaration.py` (Story 3.1).

- [ ] Task 4: Document the flow and the never-commit rule (AC: #1, #4)
  - [ ] Extend `docs/development.md`'s `## Local personas` section (Story 3.3) with a subsection on the programmatic flow: `pixi run mint-token <persona>`, the `file://` JWKS location, and the statement that the token is verified by the real Bearer authentication class with nothing stubbed.
  - [ ] State the never-commit rule and its reason (NFR-7), and state R-5 plainly: synthetic claims never exercise JWKS retrieval over the network or key rotation at the IdP.

- [ ] Task 5: Tests (AC: #1, #2, #3, #4)
  - [ ] Create `tests/unit/test_local_dev_keys.py` (NEW): assert `ensure_keypair()` refuses with `ImproperlyConfigured` when `COMPONENT_RUNTIME` is unset or unrecognized; assert the private key file and `jwks.json` are absent before and present after a first call, using `tmp_path` and monkeypatching `DEV_KEY_DIR`; assert a second call returns the same `kid` and does not rewrite the key; assert the private key file mode is `0o600` and the directory `0o700`; assert the JWKS document contains exactly one key whose `kid` matches. (Filesystem writes confined to `tmp_path` keep this test unit-scoped in the sense that matters — no database, no network — but if the project's unit-test rule is read strictly, place it in `tests/integration/` with the marker instead; do not skip it.)
  - [ ] Create `tests/unit/test_gitignore_covers_dev_keys.py` (NEW) or add the assertion to an existing manifest test: read `.gitignore` and assert `.local-dev-keys/` is present. Also assert no file under `DEV_KEY_DIR`'s name is tracked. This is NFR-7's only automatic guard.
  - [ ] Create `tests/integration/test_local_dev_bearer_flow.py` (NEW), every test `@pytest.mark.integration`:
    - [ ] `test_minted_token_authenticates_through_the_real_class`: generate a keypair into `tmp_path`, point the JWKS setting at it, mint a token for the staff persona, present it as `Authorization: Bearer <jwt>` to an existing authenticated API endpoint (`src/django_service/users/api/views.py` is routed through `src/config/api_router.py`), and assert a 200 and that the authenticated user resolves to the persona's identity key.
    - [ ] `test_tampered_signature_is_rejected`: flip a character in the signature segment; assert 401.
    - [ ] `test_tampered_payload_is_rejected`: re-encode the payload with an added group claim, keeping the original signature; assert 401.
    - [ ] `test_expired_token_is_rejected`: mint with a negative lifetime; assert 401.
    - [ ] `test_wrong_issuer_is_rejected` and `test_wrong_audience_is_rejected`: mint with a deliberately wrong `iss` / `aud`; assert 401 for each. These are AC #2's "no verification step is stubbed or skipped" — without them, a class that decodes with `options={"verify_aud": False}` passes every other test here.
    - [ ] `test_unknown_kid_is_rejected`: mint with a second, unrelated keypair; assert 401.
    - [ ] `test_token_without_jti_is_rejected`: assert 401 (AD-10).
  - [ ] Assertions are over the real authentication class's behaviour. Do not patch the class, do not patch PyJWT's `decode`, and do not mark any of these `xfail`.

## Dev Notes

### Architecture Constraints

**FR-20 — The local programmatic flow validates for real.** "A development task mints a JWT signed by a locally generated keypair, and local settings point the JWKS location at that key, so the real Bearer authentication class verifies it." Testable consequences: "Signature, `iss`, `aud`, and `exp` are all genuinely verified; no verification step is stubbed or skipped. The keypair is generated on demand by a development task into a gitignored path and is never committed. A tampered or expired locally signed token is rejected."

**FR-20's own note on why the never-commit rule is stronger here than elsewhere:** "the never-commit rule carries more weight here than in an ordinary repository. A keypair committed to a template ships inside every component generated from it, so one published private key would be shared by every service the accelerator ever produces."

**NFR-7 — Secrets never live in source.** "No credential, key, or token is committed; the development keypair is generated on demand into a gitignored path."

**AD-23 — JWKS rotation is solved by key ID, and we build it.** Binding rule: "JWKS is fetched lazily on the first Bearer request that needs it, never at import or boot. Keys are cached by `kid`. A token presenting an uncached `kid` triggers one refetch, rate-limited so an attacker cannot drive fetches. TTL is a backstop for key removal only. The trust anchor is derived from the configured OIDC issuer; a JWKS location not derived from it is refused at startup." And: "**PyJWT does not provide this.** `PyJWKClient.cache_keys` defaults to `False`, its unknown-`kid` refetch has no rate limiting or backoff, and its LRU has no TTL. This policy is component code wrapping PyJWT, and the tests belong to it."

Two consequences for this story. First, because retrieval is component code, adding a `file://` scheme is a change to the component's own retrieval and is legitimate — it is not a bypass. Second, the local JWKS location is *deliberately* not derived from an issuer, which is exactly the state the deployed trust-anchor refusal forbids; it is permitted locally because locality is local, and Epic 4's stage-1 condition is what keeps it from reaching a deployed component. Never soften that refusal to accommodate this story.

**AD-10 — a token with no `jti` is rejected with 401.** The minted token carries one; the negative test asserts the rejection.

**AD-13 — locality fails closed.** Keypair generation and minting both refuse when `config.locality.is_local()` is `False`, before touching the filesystem.

**FR-23 — nothing on the local start path reaches the network at boot.** Keypair generation is computation, not a fetch. Do not call `ensure_keypair()` from a settings module, an `AppConfig.ready()`, or any import-time path — Story 3.7 asserts the boot path is silent, and an import-time keypair generation would also make every `pixi run manage` invocation do RSA key generation.

**Never:** commit a key; write the key outside `DEV_KEY_DIR`; add a `verify_signature=False` path; add a settings flag that relaxes `aud` or `iss` checking; introduce a second authentication class for local use; add either signing package to `[pypi-dependencies]`; use `print()` or stdlib `logging`.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/local_dev/keys.py` | NEW | `DEV_KEY_DIR`, `DevKeypair`, `ensure_keypair()` — on-demand RSA generation, PEM at `0o600`, single-key JWKS document, stable `kid`. |
| `src/config/local_dev/tokens.py` | NEW | `mint_token()` — RS256 over `build_claims` plus `iss`/`aud`/`exp`/`iat`/`jti`, `kid` header. |
| `src/config/local_dev/mint.py` | NEW | `python -m config.local_dev.mint <persona-key>` entry point. |
| `src/config/settings/local.py` | UPDATE | Point Story 2.7's JWKS-location setting at `file://` + `DEV_KEY_DIR / "jwks.json"`. |
| `pixi.toml` | UPDATE | Add the `mint-token` task with `env = { COMPONENT_RUNTIME = "local" }`; add `pyjwt` and `cryptography` to `[dependencies]` if Story 2.7 has not. |
| `.gitignore` | UPDATE | Add `.local-dev-keys/` with the reason. |
| `tests/unit/test_locality_declaration.py` | UPDATE | Add `mint-token` to `LOCAL_TASKS`. |
| `docs/development.md` | UPDATE | Programmatic-flow subsection under `## Local personas`. |
| `tests/unit/test_local_dev_keys.py` | NEW | Refusal, on-demand generation, idempotence, file modes, JWKS shape. |
| `tests/unit/test_gitignore_covers_dev_keys.py` | NEW | `.gitignore` carries `.local-dev-keys/`. |
| `tests/integration/test_local_dev_bearer_flow.py` | NEW | The real authentication class against minted, tampered, expired, wrong-`iss`, wrong-`aud`, unknown-`kid` and `jti`-less tokens. |

**`.gitignore` today (verified).** Already ignores `.env`, `.envrc`, `.venv`, `db.sqlite3`, `staticfiles/`, `.pixi/*` (with `!.pixi/config.toml`), `ruff-report.json`, and the `.envs/.local/*` / `.envs/.production/*` files. It does **not** mention any key directory. Add the entry; do not reorganize the file.

**`src/config/settings/local.py` today (verified, 82 lines).** `SECRET_KEY` with a committed development default at `:11-14`, `ALLOWED_HOSTS`, the `LocMemCache` block at `:21-26`, the console email backend, the whitenoise `runserver_nostatic` prepend at `:39`, the `DEBUG_APPS` gate at `:51-74`, and the Celery eager settings at `:78-80`. Preserve all of it; append the JWKS-location setting in its own commented block.

**`src/config/observability/__init__.py:32`** shows the established root-derivation idiom: `BASE_DIR = Path(__file__).resolve().parents[3]`. `src/config/settings/base.py:15` uses `Path(__file__).resolve(strict=True).parent.parent.parent.parent` for the same root. Use one of these, not a new one.

**Dependencies on earlier stories — concrete names, verified against those stories' files.** `src/config/authorization/jwks.py`: `JWKSKeyStore`, the module-level `KEY_STORE`, `jwks_url_derives_from_issuer`, `JWKSKeyUnavailable`, and the `COMPONENT_OIDC_JWKS_URL` / `COMPONENT_OIDC_ISSUER` / `COMPONENT_JWKS_TTL_SECONDS` / `COMPONENT_JWKS_MIN_REFETCH_SECONDS` reads (Story 2.7). `src/config/authorization/authentication.py`: `OIDCBearerAuthentication` and `ALLOWED_ALGORITHMS` from `COMPONENT_OIDC_ALGORITHMS` (Story 2.7), registered first in `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`. `src/config/authorization/mapper.py`: `resolve_user`, `sync_once_per_epoch` — the Bearer path uses the epoch gate, which is why the minted token must carry a `jti` (Story 2.5). `config.local_dev.personas.build_claims` / `get_persona` (Story 3.3). `config.locality.is_local()` (Story 3.1). `src/config/authorization/` does not exist in the repository today.

**Existing API surface for the integration test.** `src/config/api_router.py` routes `src/django_service/users/api/views.py`; `src/config/urls.py:37` mounts it at `api/`. `tests/integration/users/test_api_views.py` already exercises those endpoints and is the model to follow for request construction.

### Testing Requirements

- Every test in `tests/integration/test_local_dev_bearer_flow.py` carries `@pytest.mark.integration`, uses the `db` fixture, and leaves state as found. Keys go under `tmp_path`, never under the repository root.
- The six rejection tests (tampered signature, tampered payload, expired, wrong `iss`, wrong `aud`, unknown `kid`) are not optional garnish — they are how AC #2's "no verification step is stubbed or skipped" is proven. A single happy-path test passes against an implementation that verifies nothing.
- Never patch the authentication class, PyJWT's `decode`, or the JWKS cache in these tests. Patching is permitted only in `tests/unit/test_local_dev_keys.py`, and only to relocate `DEV_KEY_DIR` into `tmp_path`.
- No `@pytest.mark.skip` or `@pytest.mark.xfail` without a comment linking an open issue.
- Coverage floor: ninety percent including templates (AD-20), `COVERAGE_CORE=ctrace`, `--cov-fail-under=90`. `pixi run ci` must exit 0.
- Test disposition: `core`, under `tests/` mirroring `src/`.
- Run with `pixi run test` / `pixi run test-integration`; never bare `pytest`, never `pip`, never `uv`.

#### Project Structure Notes

`src/config/local_dev/` is created by Story 3.3; this story adds `keys.py`, `tokens.py` and `mint.py` to it. Disposition `core` — the path ships in every component and is guarded by the refusals rather than stripped, on FR-19's stated reasoning that "a stripped path cannot be tested by the component's own gate."

`.local-dev-keys/` is a generated, ignored artifact at the repository root. It is not a declared generated artifact under AD-2's output reconciliation — that rule governs materialized output, and this directory never exists in a materialized tree because it is created on demand by a local task. When Epic 7 authors `accelerator.toml`, the directory needs no disposition entry; the `.gitignore` line is what keeps it out of the tree.

### References

- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-20] — including the note on why the never-commit rule carries more weight here.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#NFR-7]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md:304] — detecting the key file inside a built image is out of scope here; the trust-anchor refusal is the broader guard.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-23] · [#AD-10] · [#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Stack] — PyJWT 2.13, cryptography 50.0, both new.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — supply chain: a directly imported package is declared directly.
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.5] · [#Story 2.7]
- [Source: pixi.toml] — `[dependencies]` carries no `pyjwt` and no `cryptography` today; `[pypi-dependencies]` holds only the editable self-install.
- [Source: tests/unit/test_dependency_policy.py:31-46] — the assertion that fails if a signing package is added to `[pypi-dependencies]`.
- [Source: .gitignore] · [Source: src/config/settings/local.py] · [Source: src/config/observability/__init__.py:32] · [Source: src/config/api_router.py] · [Source: tests/integration/users/test_api_views.py]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
