---
baseline_revision: 2555897
review_loop_iteration: 0
status: done
warnings: [oversized]
---

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

> **Reconciled against the tree at `2555897` before implementation.** Every dependency named below
> was re-read from the current files rather than taken from this story's 2026-08-15 Dev Notes.
> Nine claims did not survive that reading; each correction is recorded in the **Spec Change Log**
> at the end of this file and applied in place below.

- [x] Task 0: Confirm the signing dependencies are declared (AC: #1) — **already satisfied, verify only**
  - [x] `pixi.toml` `[dependencies]` **does** carry `pyjwt = ">=2.13,<3"` (`pixi.toml:67`) and
        `cryptography = ">=50.0,<51"` (`pixi.toml:72`), both with rationale comments, both declared by
        Story 2.7. `[pypi-dependencies]` holds only the editable self-install. Nothing to add.
  - [x] `tests/unit/test_dependency_policy.py::test_the_allauth_socialaccount_extra_is_declared_rather_than_inherited`
        already asserts, for each of `requests`, `pyjwt` and `cryptography`, that the package is in
        `[dependencies]` with a rationale. This story adds no dependency and must not touch either table.
  - [x] `cryptography` is imported by `src/` for the first time in this story (today only `tests/jwt_keys.py`
        imports it). That is a new *direct* import of an already-declared package, which the supply-chain
        convention permits without a manifest change.

- [x] Task 1: Generate the keypair on demand into a gitignored path (AC: #1, #4)
  - [x] Create `src/config/local_dev/keys.py` (NEW).
  - [x] Declare the location as a module constant, `DEV_KEY_DIR: Final[Path] = BASE_DIR / ".local-dev-keys"`,
        with `BASE_DIR = Path(__file__).resolve().parents[3]` — the idiom at
        `src/config/observability/__init__.py:31-32`, and the same four-levels-up root
        `src/config/settings/base.py:16-20` reaches by a `.parent` chain. One declaration site; nothing
        else spells the directory name.
  - [x] Implement `ensure_keypair() -> DevKeypair`, where `DevKeypair` is a frozen slotted dataclass
        carrying `kid: str`, `private_key_path: Path` and `jwks_path: Path`:
    - [x] Refuse when `config.locality.is_local()` is `False`, as the **first statement**, raising
          `ImproperlyConfigured` with a module-level message constant — the `seeding.py:82-83` idiom
          (operator-invoked code refuses with `ImproperlyConfigured`; only request-reachable code uses
          `Http404`).
    - [x] Create the directory with mode `0o700` if absent.
    - [x] If the private key file is absent, generate RSA-2048 with `cryptography`
          (`public_exponent=65537`, `key_size=2048`) and write unencrypted PKCS#8 PEM at mode `0o600`.
    - [x] Derive a stable `kid` from the public key: the base64url (unpadded) of the SHA-256 RFC 7638
          JWK thumbprint. Deterministic from the key, so a reload yields the same `kid`.
    - [x] Write a JWKS document holding exactly that one public key to `jwks.json`, rendered with
          `jwt.algorithms.RSAAlgorithm.to_jwk` plus `kid`, `alg: "RS256"` and `use: "sig"` — the same
          shape `tests/jwt_keys.py:SigningKey.public_jwk` produces, because that is the shape
          `jwt.PyJWKSet.from_dict` in `jwks.py:_index_by_kid` consumes.
    - [x] If the key already exists, load it and return. Generation is on demand and idempotent, never
          on import.
  - [x] Expose `load_private_key(keypair: DevKeypair)` (or return the key object on `DevKeypair`) so
        `tokens.py` signs with the same material without re-reading the PEM by path in a second place.
  - [x] Never generate at import time and never from a settings module. `ensure_keypair()` is called by
        the minting entry point and by tests, and by nothing that runs at boot (FR-23).
  - [x] Add `.local-dev-keys/` to `.gitignore` (UPDATE), in the project-specific tail block before the
        `# pixi environments` block, as its own commented block matching the
        `# Collected static files (STATIC_ROOT)` style. The comment states the reason: a key committed to
        a template ships inside every component generated from it, so one published private key would be
        shared by every service the accelerator ever produces.
  - [x] Do **not** add the key to any packaging manifest.

- [x] Task 2: Point the local JWKS location at the generated key (AC: #1, #2)
  - [x] The names are Django **settings**, declared once in `src/config/settings/base.py:481-556`, and the
        `COMPONENT_*` spellings are the environment variables behind them. `jwks.py` and
        `authentication.py` read `settings.OIDC_JWKS_URL`, `settings.OIDC_ISSUER`, `settings.OIDC_AUDIENCE`,
        `settings.OIDC_ALGORITHMS`, `settings.OIDC_LEEWAY_SECONDS`, `settings.JWKS_TTL_SECONDS` and
        `settings.JWKS_MIN_REFETCH_SECONDS`. Use those names. Introduce no second location variable and no
        second store — the store is `JWKSKeyStore` with the module-level instance `KEY_STORE`
        (`src/config/authorization/jwks.py:407, 659`).
  - [x] Extend the fetch seam. It is the **module-level function** `fetch_jwks_document() -> Mapping[str, Any]`
        (`jwks.py:332`), taken as `JWKSKeyStore.__init__`'s `fetch` default — not a method. Today it refuses
        any scheme outside `_PERMITTED_SCHEMES` (`{"http", "https"}`). Add a `file` branch that reads the
        document from disk, bounded by the existing `_MAX_DOCUMENT_BYTES`, and parses it through the same
        `json.loads` / "must be a JSON object" path the HTTP branch uses, so both feed the identical
        `kid`-keyed cache.
  - [x] **Gate the `file` branch on `config.locality.is_local()`**, refusing with `JWKSKeyUnavailable` and a
        distinct message where locality is not local. AD-23's stage-1 trust-anchor refusal is Epic 4's and
        **is not implemented yet** — every Epic 4 story is `ready-for-dev`, and `jwks_url_derives_from_issuer`
        has no consumer in `src/` today. Without this gate, shipping the `file` branch would leave a deployed
        component reading its trust anchor off local disk with nothing at all refusing it. The gate is that
        refusal's obligation met by the module that owns the read, not a substitute for it.
  - [x] Reject a `file://` URL carrying a host other than empty or `localhost`; resolve the path with
        `urllib.request.url2pathname` over the split path so a Windows drive letter survives (`win-64` is a
        declared platform).
  - [x] Change **nothing** about signature, `iss`, `aud`, `exp` or `alg` verification, and leave the rate
        limiter and TTL behaviour intact.
  - [x] Do **not** relax `jwks_url_derives_from_issuer` — it already answers `False` for a `file://` location
        and `tests/unit/authorization/test_jwks.py:515-516` freezes that. It stays untouched.
  - [x] Set the local values in `src/config/settings/local.py` only — never in `base.py`, `test.py` or
        `production.py` — appended after the existing `# Your stuff...` banner as its own commented block:
    - [x] `OIDC_JWKS_URL` → `(DEV_KEY_DIR / "jwks.json").as_uri()`, importing `DEV_KEY_DIR` from
          `config.local_dev.keys`. `as_uri()` rather than string concatenation so the URL is well-formed on
          every declared platform. Importing the module is not generating a key: `keys.py` reads no settings
          and generates nothing at import.
    - [x] `OIDC_ISSUER` and `OIDC_AUDIENCE` → local development values, **only where the environment left
          them unset**, following the `CLAIMS_CONTRACT` idiom already in `local.py:103-131`. This is not
          optional decoration: `base.py` defaults both to `""`, and PyJWT's `_validate_aud` raises
          `MissingRequiredClaimError("aud")` on a token whose `aud` is the empty string (`if "aud" not in
          payload or not payload["aud"]`) — so with the audience unset, every locally minted token is
          rejected and AC #2 cannot hold on a fresh clone. Verified against PyJWT 2.13.0 in this
          environment.
    - [x] Do not touch `SOCIALACCOUNT_PROVIDERS`. It is built in `base.py` from the `OIDC_ISSUER` value read
          there; re-binding the name in `local.py` does not and must not reach back into it.
  - [x] Reading a local file is not a network call and does not violate FR-23: retrieval stays lazy, triggered
        by the first Bearer request whose `kid` is uncached.

- [x] Task 3: Mint the token (AC: #1, #2, #3)
  - [x] Create `src/config/local_dev/tokens.py` (NEW) exposing
        `mint_token(persona_key: str, *, lifetime_seconds: int = 900, jti: str | None = None) -> str`.
  - [x] Refuse when not local, first statement, `ImproperlyConfigured` — the same way `seeding.py` does.
  - [x] Build the payload from `build_claims(get_persona(persona_key))`
        (`src/config/local_dev/personas.py:164, 211` — the sole synthetic-claims constructor) and add the
        registered claims:
    - [x] `iss` from `settings.OIDC_ISSUER` and `aud` from `settings.OIDC_AUDIENCE` — read from the same
          settings the authentication class reads (`authentication.py:375, 389`), never from a literal.
    - [x] `exp` from `lifetime_seconds`, plus `iat`.
    - [x] `jti`, defaulting to a fresh `uuid4` hex. Required not by the authentication class — which checks
          only `_REQUIRED_CLAIMS = ["exp", "iss", "aud"]` (`authentication.py:92`) — but by
          `mapper.sync_once_per_epoch`, which raises `ClaimsRejected("token carries no jti")`;
          `_authorized` converts that to the same 401 (AD-10's rejection, at a location this story's Dev
          Notes originally misattributed to the authentication class).
    - [x] `build_claims` already emits the identity-key claim and the **group claim**; do not drop either.
          The mapper refuses `identity key claim absent` and `group claim absent` alike.
  - [x] Sign with PyJWT using `RS256`, the private key from `ensure_keypair()`, and a `kid` header matching
        the JWKS entry. `RS256` is the sole member of `_DEFAULT_ALGORITHMS` behind `settings.OIDC_ALGORITHMS`
        (`authentication.py:85, 353`); do not widen it, and never let the token's own header choose the
        algorithm. There is no `ALLOWED_ALGORITHMS` name in the tree.
  - [x] Do **not** add a verification bypass, a `verify_signature=False` path, a settings flag that relaxes
        audience checking, or a test-only authentication class.
  - [x] Create `src/config/local_dev/mint.py` (NEW) as the `python -m config.local_dev.mint <persona-key>`
        entry point, modelled line for line on `src/config/local_dev/seed.py`: module-level
        `logger: structlog.stdlib.BoundLogger = structlog.get_logger("config.local_dev.mint")` with the
        **explicit dotted name** (`__name__` is `"__main__"` under `python -m`);
        `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")`; `django.setup()`; the
        deferred in-function import of `config.local_dev.tokens`; `sys.argv` parsing for the persona key;
        `ensure_keypair()` then `mint_token()`; emit the token as a structured `structlog` event — never
        `print`; `if __name__ == "__main__": main()`.
  - [x] Refusals propagate as tracebacks, as `seed.py` does. No `argparse`, no `SystemExit` handling.
  - [x] Add to `pixi.toml` `[tasks]` (the default-environment table, immediately after `seed-personas` at
        `pixi.toml:476`):
        `mint-token = { cmd = "python -m config.local_dev.mint", default-environment = "default", description = "Mint a development JWT for a local persona" }`.
  - [x] **Declare no `env` on it.** `tests/unit/test_locality_declaration.py::test_no_task_declares_component_runtime`
        fails on any task whose own `env` names `COMPONENT_RUNTIME`, at any value. The invocation is
        `pixi run -e dev mint-token <persona-key>`; the bare form resolves in `default` and reads *deployed*,
        which is what makes the refusal the guard.
  - [x] Nothing to register in `tests/unit/test_locality_declaration.py` — there is no `LOCAL_TASKS` data set
        in that file (verified).

- [x] Task 4: Document the flow and the never-commit rule (AC: #1, #4)
  - [x] Extend `docs/development.md`'s `## Local personas` section with a `### Minting a development token`
        subsection: `pixi run -e dev mint-token <persona>` (the `-e dev` is required), the `file://` JWKS
        location, the local issuer and audience defaults, and the statement that the token is verified by the
        real Bearer authentication class with nothing stubbed.
  - [x] State the never-commit rule and its reason (NFR-7), and state R-5 plainly: synthetic claims never
        exercise JWKS retrieval over the network or key rotation at the IdP.
  - [x] `pixi run -e dev docs` runs mkdocs `--strict`; a broken anchor fails the gate.

- [x] Task 5: Tests (AC: #1, #2, #3, #4)
  - [x] Create `tests/unit/test_local_dev_keys.py` (NEW). `tests/unit/test_observability_init.py` is the
        precedent for a unit test that writes under `tmp_path` while touching no database and no network;
        follow it, monkeypatching `keys.DEV_KEY_DIR`. Assert: `ensure_keypair()` raises `ImproperlyConfigured`
        when `COMPONENT_RUNTIME` is deleted or unrecognized; the private key and `jwks.json` are absent before
        and present after a first call; a second call returns the same `kid` and does not rewrite the key
        file; the private key file mode is `0o600` and the directory `0o700`; the JWKS document holds exactly
        one key whose `kid` matches and whose `kty`/`alg`/`use` are `RSA`/`RS256`/`sig`. Keep RSA generation
        to as few calls as the assertions genuinely need — 2048-bit generation is the slowest thing in the
        unit suite.
  - [x] Create `tests/unit/test_gitignore_covers_dev_keys.py` (NEW): read `.gitignore` and assert
        `.local-dev-keys/` is present; assert `git ls-files` tracks nothing under that name. This is NFR-7's
        only automatic guard. Reading a repository manifest in a unit test is established here
        (`test_dependency_policy.py`, `test_locality_declaration.py`).
  - [x] Extend `tests/unit/authorization/test_jwks.py` (UPDATE). `test_the_default_fetch_refuses_a_scheme_outside_http`
        at `:753` currently proves the refusal with `file:///etc/passwd` **and runs in the `dev` environment,
        where locality is local** — so it changes meaning under Task 2 and must be updated, not deleted.
        Split it into: a scheme genuinely outside the permitted set is still refused with the unchanged
        message `"JWKS location uses a scheme that is not http or https"`; a `file://` location is refused
        with the new local-only message when `COMPONENT_RUNTIME` is deleted; a `file://` location with a
        foreign host is refused; and a `file://` location is read where locality is local.
  - [x] Create `tests/integration/test_local_dev_bearer_flow.py` (NEW). Every test carries the integration
        marker (`tests/integration/conftest.py` applies it automatically) and `pytest.mark.django_db`. Model
        it on `tests/integration/authorization/test_bearer_authentication.py`, with one deliberate
        difference: **the fetch seam is not stubbed**. The real `fetch_jwks_document` reads the real
        `file://` location, because that path is what AC #1 and #2 are about. Reset `KEY_STORE` on both
        sides of every test — it is module-level state and the 60-second refetch window otherwise leaks
        between tests. Cases:
    - [x] `test_minted_token_authenticates_through_the_real_class`: generate a keypair into `tmp_path`, point
          `settings.OIDC_JWKS_URL` at its `jwks.json`, mint a token for the staff persona, present it as
          `Authorization: Bearer <jwt>` to `api:user-me`, assert 200 and that the authenticated user resolves
          to the persona's `idp_subject`.
    - [x] `test_tampered_signature_is_rejected`: corrupt the signature segment; assert 401.
    - [x] `test_tampered_payload_is_rejected`: re-encode the payload with an added group claim, keeping the
          original signature; assert 401.
    - [x] `test_expired_token_is_rejected`: mint with a negative lifetime; assert 401.
    - [x] `test_wrong_issuer_is_rejected` and `test_wrong_audience_is_rejected`: assert 401 for each. These
          are AC #2's "no verification step is stubbed or skipped" — without them, a class decoding with
          `options={"verify_aud": False}` passes every other case here.
    - [x] `test_unknown_kid_is_rejected`: sign with a second, unpublished keypair (`tests/jwt_keys.generate`)
          under a `kid` the local JWKS does not carry; assert 401.
    - [x] `test_token_without_jti_is_rejected`: assert 401 (AD-10, raised by the mapper).
  - [x] Reuse `tests/jwt_keys.py` (`generate`, `jwks_document`, `SigningKey.sign`) for the impostor and
        unknown-`kid` material rather than writing a second helper.
  - [x] Assertions are over the real authentication class's behaviour. Do not patch the class, do not patch
        PyJWT's `decode`, do not patch `KEY_STORE._fetch` in this file, and do not mark any of these `xfail`.

## Dev Notes

### Architecture Constraints

**FR-20 — The local programmatic flow validates for real.** "A development task mints a JWT signed by a locally generated keypair, and local settings point the JWKS location at that key, so the real Bearer authentication class verifies it." Testable consequences: "Signature, `iss`, `aud`, and `exp` are all genuinely verified; no verification step is stubbed or skipped. The keypair is generated on demand by a development task into a gitignored path and is never committed. A tampered or expired locally signed token is rejected."

**FR-20's own note on why the never-commit rule is stronger here than elsewhere:** "the never-commit rule carries more weight here than in an ordinary repository. A keypair committed to a template ships inside every component generated from it, so one published private key would be shared by every service the accelerator ever produces."

**NFR-7 — Secrets never live in source.** "No credential, key, or token is committed; the development keypair is generated on demand into a gitignored path."

**AD-23 — JWKS rotation is solved by key ID, and we build it.** Binding rule: "JWKS is fetched lazily on the first Bearer request that needs it, never at import or boot. Keys are cached by `kid`. A token presenting an uncached `kid` triggers one refetch, rate-limited so an attacker cannot drive fetches. TTL is a backstop for key removal only. The trust anchor is derived from the configured OIDC issuer; a JWKS location not derived from it is refused at startup." And: "**That check is syntactic and can be nothing else.** Verifying a JWKS location against the issuer's published discovery document requires fetching it, which is the boot-time network call FR-23 forbids — so startup can only apply a string-derivation rule over the configured issuer. An issuer whose real `jwks_uri` does not match the derivation surfaces on the first Bearer request, not at boot." And: "**PyJWT does not provide this.** `PyJWKClient.cache_keys` defaults to `False`, its unknown-`kid` refetch has no rate limiting or backoff, and its LRU has no TTL. This policy is component code wrapping PyJWT, and the tests belong to it."

Two consequences for this story. First, because retrieval is component code, adding a `file://` scheme is a change to the component's own retrieval and is legitimate — it is not a bypass. Second, the local JWKS location is *deliberately* not derived from an issuer, which is exactly the state the deployed trust-anchor refusal forbids; it is permitted locally because locality is local, and Epic 4's stage-1 condition is what keeps it from reaching a deployed component. Never soften that refusal to accommodate this story. Third, because that refusal is **syntactic** — a string-derivation rule over the configured issuer, not a confirmation against a fetched discovery document — a `file://` location is caught by it reliably: no `file://` string derives from an `https://` issuer. What the syntactic check cannot catch is an issuer whose real `jwks_uri` differs from the derivation, and that surfaces on the first Bearer request rather than at boot. Do not add a discovery fetch to close that gap; it would be the boot-time network call FR-23 forbids.

**AD-10 — a token with no `jti` is rejected with 401.** The minted token carries one; the negative test
asserts the rejection. The check is **not** in the authentication class — its `_REQUIRED_CLAIMS` are
`exp`, `iss`, `aud` only. `mapper.sync_once_per_epoch` raises `ClaimsRejected("token carries no jti")`
and `OIDCBearerAuthentication._authorized` converts it to the same 401. The observable behaviour the
test asserts is unchanged; the location is not where this story's Dev Notes originally put it.

**AD-13 — locality fails closed.** Keypair generation and minting both refuse when `config.locality.is_local()` is `False`, before touching the filesystem.

**FR-23 — nothing on the local start path reaches the network at boot.** Keypair generation is computation, not a fetch. Do not call `ensure_keypair()` from a settings module, an `AppConfig.ready()`, or any import-time path — Story 3.7 asserts the boot path is silent, and an import-time keypair generation would also make every `pixi run manage` invocation do RSA key generation.

**Never:** commit a key; write the key outside `DEV_KEY_DIR`; add a `verify_signature=False` path; add a settings flag that relaxes `aud` or `iss` checking; introduce a second authentication class for local use; add either signing package to `[pypi-dependencies]`; use `print()` or stdlib `logging`.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/local_dev/keys.py` | NEW | `DEV_KEY_DIR`, `DevKeypair`, `ensure_keypair()` — on-demand RSA generation, PEM at `0o600`, single-key JWKS document, thumbprint `kid`. |
| `src/config/local_dev/tokens.py` | NEW | `mint_token()` — RS256 over `build_claims` plus `iss`/`aud`/`exp`/`iat`/`jti`, `kid` header. |
| `src/config/local_dev/mint.py` | NEW | `python -m config.local_dev.mint <persona-key>` entry point. |
| `src/config/authorization/jwks.py` | UPDATE | A locality-gated `file` branch in `fetch_jwks_document()`, feeding the same parse and the same `kid`-keyed cache. Verification, TTL and rate limiting untouched. |
| `src/config/settings/local.py` | UPDATE | `OIDC_JWKS_URL` at `file://` + `DEV_KEY_DIR / "jwks.json"`; local `OIDC_ISSUER` and `OIDC_AUDIENCE` defaults, filled only where unset. |
| `pixi.toml` | UPDATE | Add the `mint-token` task with **no** `env`; invoked as `pixi run -e dev mint-token`. `[dependencies]` already carries `pyjwt` and `cryptography` — do not touch it. |
| `.gitignore` | UPDATE | Add `.local-dev-keys/` with the reason. |
| `tests/unit/test_locality_declaration.py` | UNCHANGED | Nothing to register; `LOCAL_TASKS` does not exist in the delivered file (verified). |
| `docs/development.md` | UPDATE | `### Minting a development token` under `## Local personas`. |
| `tests/unit/test_local_dev_keys.py` | NEW | Refusal, on-demand generation, idempotence, file modes, JWKS shape. |
| `tests/unit/test_gitignore_covers_dev_keys.py` | NEW | `.gitignore` carries `.local-dev-keys/`; nothing under it is tracked. |
| `tests/unit/authorization/test_jwks.py` | UPDATE | The scheme-refusal case splits: unpermitted scheme, `file://` while deployed, `file://` with a foreign host, `file://` while local. |
| `tests/integration/test_local_dev_bearer_flow.py` | NEW | The real authentication class against minted, tampered, expired, wrong-`iss`, wrong-`aud`, unknown-`kid` and `jti`-less tokens, over the real `file://` retrieval. |

**`.gitignore` today (verified).** Already ignores `.env`, `.envrc`, `.venv`, `db.sqlite3`, `staticfiles/`, `.pixi/*` (with `!.pixi/config.toml`), `ruff-report.json`, and the `.envs/.local/*` / `.envs/.production/*` files. It does **not** mention any key directory. Add the entry; do not reorganize the file.

**`src/config/settings/local.py` today (verified, 82 lines).** `SECRET_KEY` with a committed development default at `:11-14`, `ALLOWED_HOSTS`, the `LocMemCache` block at `:21-26`, the console email backend, the whitenoise `runserver_nostatic` prepend at `:39`, the `DEBUG_APPS` gate at `:51-74`, and the Celery eager settings at `:78-80`. Preserve all of it; append the JWKS-location setting in its own commented block.

**`src/config/observability/__init__.py:32`** shows the established root-derivation idiom: `BASE_DIR = Path(__file__).resolve().parents[3]`. `src/config/settings/base.py:15` uses `Path(__file__).resolve(strict=True).parent.parent.parent.parent` for the same root. Use one of these, not a new one.

**Dependencies on earlier stories — re-verified against the current files at `2555897`, not against the stories that introduced them.**

`src/config/authorization/` **exists**; Epic 2 built it. This story's original Dev Notes claimed it did not.

- `src/config/authorization/jwks.py`: `JWKSKeyStore` (`:407`), the module-level `KEY_STORE` (`:659`),
  `configured_jwks_url()` (`:193`), `conventional_jwks_url()` (`:174`), `fetch_jwks_document()` (`:332`, the
  fetch seam — a module-level function, not a method), `jwks_url_derives_from_issuer()` (`:208`),
  `_PERMITTED_SCHEMES` (`:92`), `_MAX_DOCUMENT_BYTES` (`:130`), `JWKSKeyStore.reset()` (`:496`), and the
  `_index_by_kid` path (`:595`) that feeds `jwt.PyJWKSet.from_dict` and silently drops any JWK with no `kid`.
- `src/config/authorization/authentication.py`: `OIDCBearerAuthentication` (`:147`), registered first in
  `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`. It decodes with
  `algorithms=list(_algorithms())`, `issuer=_issuer()`, `audience=_audience()`, `leeway=_leeway()` and
  `options={"require": _REQUIRED_CLAIMS}` where `_REQUIRED_CLAIMS = ["exp", "iss", "aud"]` (`:92`). The
  `kid` is read from the unverified header and must be a non-blank string (`:199`). Every refusal becomes
  `AuthenticationFailed`, rendered **401** because `authenticate_header` answers `"Bearer"`. There is **no**
  `ALLOWED_ALGORITHMS` name — the reader is `_algorithms()` (`:353`) over `settings.OIDC_ALGORITHMS`, with
  `_DEFAULT_ALGORITHMS = ("RS256",)` (`:85`).
- `src/config/authorization/mapper.py`: `resolve_user` (`:188`) and `sync_once_per_epoch` (`:819`), which is
  where the `jti` requirement actually lives — `ClaimsRejected("token carries no jti")`, converted to 401 by
  `_authorized`. Refusal reasons a minted token can trip include `identity key claim absent`,
  `group claim absent` and `resolved user is deactivated`.
- `src/config/authorization/exceptions.py`: `ClaimsRejected(reason)`, `JWKSKeyUnavailable(reason)`.
- `src/config/settings/base.py:481-556`: `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_JWKS_URL`, `OIDC_AUDIENCE`
  (defaults to `OIDC_CLIENT_ID`), `OIDC_ALGORITHMS`, `OIDC_LEEWAY_SECONDS`, `JWKS_TTL_SECONDS`,
  `JWKS_MIN_REFETCH_SECONDS` — the Django-setting names the two modules read. The `COMPONENT_*` spellings are
  the environment variables behind them and appear nowhere in `jwks.py` or `authentication.py`.
- `src/config/local_dev/personas.py`: `get_persona()` (`:164`), `build_claims()` (`:211`), `Persona` (`:90`),
  `UnknownPersonaError` (`:79`), and the two declared personas `staff` and `reader` (`:132-149`).
  `build_claims` emits `preferred_username`, `email`, `name`, the contract's identity-key claim and the
  contract's group claim — deliberately no `iss`, `aud`, `exp` or `jti`.
- `src/config/locality.py`: `is_local()` (`:84`), reading `COMPONENT_RUNTIME` at call time and failing closed.
- `tests/jwt_keys.py`: `generate()`, `jwks_document()`, `SigningKey.public_jwk()` / `.sign()`, `StubFetch`,
  `FakeClock`. It already exists and is the model for the JWK rendering `keys.py` must produce.

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
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md:312] — detecting the key file inside a built image is out of scope here; the trust-anchor refusal is the broader guard.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-23] · [#AD-10] · [#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Stack] — PyJWT 2.13, cryptography 50.0, both new.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — supply chain: a directly imported package is declared directly.
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.5] · [#Story 2.7]
- [Source: pixi.toml] — `[dependencies]` carries no `pyjwt` and no `cryptography` today; `[pypi-dependencies]` holds only the editable self-install.
- [Source: tests/unit/test_dependency_policy.py:31-46] — the assertion that fails if a signing package is added to `[pypi-dependencies]`.
- [Source: .gitignore] · [Source: src/config/settings/local.py] · [Source: src/config/observability/__init__.py:32] · [Source: src/config/api_router.py] · [Source: tests/integration/users/test_api_views.py]

## Spec Change Log

Reconciliation pass against the tree at `2555897`, before any code was written. Nine claims in the
2026-08-15 Dev Notes did not survive re-reading; each was corrected in place above.

1. **Task 0 was already satisfied.** `pixi.toml:67,72` carry `pyjwt = ">=2.13,<3"` and
   `cryptography = ">=50.0,<51"` in `[dependencies]`, with rationale comments, declared by Story 2.7.
   `tests/unit/test_dependency_policy.py` already asserts exactly that for both. Task 0 is now a
   verification step, not a change.
2. **`src/config/authorization/` was said not to exist.** It does. Every name in the dependency list was
   re-read from the current files with line numbers.
3. **`COMPONENT_OIDC_JWKS_URL` and friends are environment variables, not the names the code reads.** The
   two modules read Django settings — `OIDC_JWKS_URL`, `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_ALGORITHMS`,
   `JWKS_TTL_SECONDS`, `JWKS_MIN_REFETCH_SECONDS` — declared once in `base.py:481-556`.
4. **`ALLOWED_ALGORITHMS` does not exist.** The reader is `_algorithms()` (`authentication.py:353`) over
   `settings.OIDC_ALGORITHMS`, defaulting to `("RS256",)`.
5. **The fetch seam is a module-level function, not a method on `JWKSKeyStore`.** `fetch_jwks_document()`
   at `jwks.py:332`, passed as the store's `fetch` constructor default. "Extend `JWKSKeyStore`'s fetch seam"
   now names the right object.
6. **The `file` branch needs a locality gate of its own.** The spec rested the deployed guard entirely on
   Epic 4's stage-1 trust-anchor refusal. Every Epic 4 story is still `ready-for-dev`, and
   `jwks_url_derives_from_issuer` has no consumer in `src/` today, so that guard does not exist yet.
   Gating on `config.locality.is_local()` inside the branch is the same refusal met by the module that owns
   the read. `jwks_url_derives_from_issuer` is left untouched and still answers `False` for `file://`.
7. **Local settings must default `OIDC_ISSUER` and `OIDC_AUDIENCE` too, not only the JWKS location.**
   `base.py` defaults both to `""`, and PyJWT 2.13.0's `_validate_aud` refuses a token whose `aud` is the
   empty string with `MissingRequiredClaimError("aud")` (`if "aud" not in payload or not payload["aud"]`).
   With the audience unset, every locally minted token is rejected and AC #1's "mints a token" produces
   something the real class can never accept. Verified by reading PyJWT's source in this environment.
8. **The `jti` requirement is enforced by the mapper, not the authentication class.** Same 401, different
   module. AC #3's `jti` case is unaffected; the Dev Notes' attribution was wrong.
9. **`tests/unit/authorization/test_jwks.py:753` changes meaning and must be updated.**
   `test_the_default_fetch_refuses_a_scheme_outside_http` proves the refusal with `file:///etc/passwd`, and
   the whole suite runs in the `dev` environment where locality is local. Left as-is it would assert the
   opposite of Task 2. It is split into four cases rather than deleted.

Two further corrections of smaller weight, applied without a numbered entry: `tests/jwt_keys.py` already
provides the JWK rendering and signing helpers this story would otherwise duplicate, and
`tests/unit/test_observability_init.py` is the precedent that settles the unit-versus-integration question
for `tmp_path` filesystem writes the original Task 5 left open.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
