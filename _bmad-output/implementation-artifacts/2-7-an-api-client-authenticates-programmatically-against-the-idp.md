# Story 2.7: An API client authenticates programmatically against the IdP

Status: ready-for-dev

## Story

As a developer working on a generated component,
I want Bearer JWTs verified against the IdP's JWKS with rotation handled,
so that API authentication is real verification rather than a local lookup.

## Acceptance Criteria

**Traceability:** FR-5 · AD-10, AD-23 · SC-6

1. **Given** an `Authorization: Bearer <JWT>` header
   **When** it is presented
   **Then** a `rest_framework.authentication.BaseAuthentication` subclass using PyJWT and `cryptography` verifies signature, `iss`, `aud` and `exp`
   **And** a token failing any one of them is rejected with 401

2. **Given** a successful validation
   **When** authorization is decided
   **Then** the authentication class invokes the mapper
   **And** contains no mapping logic of its own

3. **Given** JWKS material
   **When** it is first needed
   **Then** it is fetched lazily on the first Bearer request that needs it
   **And** never at import or at boot

4. **Given** keys cached by `kid`
   **When** a token presents an uncached `kid`
   **Then** exactly one refetch is triggered, rate-limited so it cannot be driven by an attacker
   **And** a key rotation is survived without a restart

5. **Given** `PyJWKClient.cache_keys` defaults to `False`, its unknown-`kid` refetch has no rate limiting, and its LRU has no TTL
   **When** this policy is implemented
   **Then** it is component code wrapping PyJWT
   **And** the tests for caching, refetch and rate limiting belong to that code

6. **Given** a cache lifetime
   **When** it is configured
   **Then** it exists only as a backstop for key removal

7. **Given** a token that verifies against an identity whose user is deactivated
   **When** authentication is decided
   **Then** `resolve_user` refuses it with `ClaimsRejected`
   **And** the Bearer path answers 401
   **And** the interactive path answers 403 through the adapter's existing refusal response

## Tasks / Subtasks

- [ ] Task 1 — Build the key store at `src/config/authorization/jwks.py` (AC: #3, #4, #5, #6)
  - [ ] `class JWKSKeyStore` holding a process-local `dict[str, PyJWK]` keyed by `kid`, a `_fetched_at: float`, and a `_last_fetch_attempt: float`. Construct it once at module scope as `KEY_STORE = JWKSKeyStore()`; **construct only — never fetch in the constructor** (AC #3).
  - [ ] `def get_signing_key(self, kid: str) -> PyJWK` — the one entry point. Cache hit and not TTL-expired → return. Miss or expired → attempt a refetch subject to the rate limit; then look up again; still missing → raise `JWKSKeyUnavailable`.
  - [ ] Rate limit: refuse to fetch if `monotonic() - self._last_fetch_attempt < min_refetch_seconds`. Set `_last_fetch_attempt` **before** the request, so a failing IdP does not turn into a fetch loop. Read the window from `COMPONENT_JWKS_MIN_REFETCH_SECONDS` (default 60). AC #4's "rate-limited so it cannot be driven by an attacker" is the whole point: the Bearer path is unauthenticated at this moment, so a caller sending random `kid`s must not be able to produce one outbound fetch per request.
  - [ ] TTL: `COMPONENT_JWKS_TTL_SECONDS` (default 3600). Its **only** job is to notice a key that was removed at the IdP — that is AC #6's "exists only as a backstop for key removal". Do not shorten it in an attempt to catch rotation faster; rotation is handled by the uncached-`kid` refetch, not by the TTL.
  - [ ] Write the cache **only on a successful fetch**, replacing the dict wholesale. A transient IdP outage must not evict a good cached JWKS.
  - [ ] Parse the fetched document with `jwt.PyJWKSet.from_dict(...)` and index by each key's `key_id`. Use `requests` for the HTTP call (declared in Story 2.6). Set an explicit connect/read timeout — an IdP that never answers must not hold a worker.
  - [ ] Use a `threading.Lock` around fetch-and-swap so concurrent requests in a threaded worker produce one fetch, not N.
  - [ ] `def reset(self) -> None` for tests to clear state between cases. It exists for tests and is documented as such; no production path calls it.

- [ ] Task 2 — Derive the trust anchor, do not accept one (AC: #4, and AD-23's trust-anchor rule)
  - [ ] `def jwks_url_derives_from_issuer(issuer: str, jwks_url: str) -> bool` — true only when scheme, host and port match the issuer exactly and the JWKS path is under the issuer's path. Compare parsed `urllib.parse.urlsplit` components, never substrings.
  - [ ] Read `COMPONENT_OIDC_JWKS_URL`, defaulting to the conventional derivation from `COMPONENT_OIDC_ISSUER`. `COMPONENT_OIDC_ISSUER` is set in Story 2.6 and is the single trust anchor — do not introduce a second issuer variable.
  - [ ] Reject non-`http(s)` schemes outright. PyJWT's own client now does this to block `jku`-header-driven local file reads; the wrapper must not be weaker than the thing it replaces.
  - [ ] The **startup refusal** for a JWKS location not derived from the issuer is Epic 4's (FR-13, condition 4 of the refusal table) — this story exports the predicate, Epic 4 wires the `ImproperlyConfigured`. Note honestly, in the function's docstring, what the check can and cannot be: it is **syntactic and can be nothing else** — a string-derivation rule over the configured issuer, not a check against the discovery document, because verifying against discovery would require the boot-time network fetch FR-23 forbids. State the consequence too: an issuer whose real `jwks_uri` does not match the derivation **surfaces on the first Bearer request, not at boot** (AD-23, L-4). "Derived from" is not "confirmed against", and a reader who takes the startup refusal as proof of a working JWKS location has misread it.

- [ ] Task 3 — Build the DRF authentication class at `src/config/authorization/authentication.py` (AC: #1, #2)
  - [ ] `class OIDCBearerAuthentication(BaseAuthentication)` with `def authenticate(self, request) -> tuple[User, Mapping[str, Any]] | None`.
  - [ ] Return `None` — not a raise — when the `Authorization` header is absent or its scheme is not `Bearer`. Returning `None` lets DRF fall through to `SessionAuthentication`; raising here would break every session-authenticated request.
  - [ ] Read `kid` from `jwt.get_unverified_header(token)`, fetch the key from `KEY_STORE`, then `jwt.decode(token, key=key.key, algorithms=ALLOWED_ALGORITHMS, issuer=..., audience=..., options={"require": ["exp", "iss", "aud"]})`.
  - [ ] `ALLOWED_ALGORITHMS` is an explicit allowlist read from `COMPONENT_OIDC_ALGORITHMS` (default `["RS256"]`). **Never** take the algorithm from the token's own header — that is the `alg=none` / algorithm-confusion family of attacks.
  - [ ] Translate every failure to `rest_framework.exceptions.AuthenticationFailed`: `ExpiredSignatureError`, `InvalidIssuerError`, `InvalidAudienceError`, `InvalidSignatureError`, `DecodeError`, `JWKSKeyUnavailable`, and `ClaimsRejected` from the mapper. Catch each by its specific type — never a bare `except:`, never `except X: pass`.
  - [ ] Implement `def authenticate_header(self, request) -> str: return "Bearer"`. **Without this DRF returns 403, not 401**, and every AC in this story that says "rejected with 401" fails.
  - [ ] On success call `resolve_user(claims)` then `sync_once_per_epoch(user, claims)` from `config.authorization.mapper`, and return `(user, claims)`. The class contains **no mapping logic of its own** (AC #2) — no group reading, no `is_staff`, no username handling.
  - [ ] The no-`jti` 401 (Story 2.5 AC #4) arrives here as `ClaimsRejected` from `sync_once_per_epoch` and is translated like any other. Do not duplicate the `jti` check in this class; the rule has one home, in the mapper.
  - [ ] Emit one `structlog` event per rejection at warning with the reason and the `kid`, never the token. Never log the raw `Authorization` header.

- [ ] Task 4 — Wire the class into DRF (AC: #1)
  - [ ] In `src/config/settings/base.py`, add `"config.authorization.authentication.OIDCBearerAuthentication"` to `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` (currently lines 357–364).
  - [ ] Order it **before** `SessionAuthentication` so a request carrying both a session cookie and a Bearer header is decided by the Bearer credential.
  - [ ] Leave `"rest_framework.authentication.TokenAuthentication"` in place in this story. Its removal is Story 2.8's, and the readiness assessment records the ordering as load-bearing: "2.6 and 2.7 precede 2.8 so the replacement credential paths exist before the old ones are deleted."
  - [ ] Add no new package to `pixi.toml`. `pyjwt`, `cryptography` and `requests` were declared in Story 2.6 Task 1 — confirm all three are present in `[dependencies]` and in `pixi.lock` before writing code against them.

- [ ] Task 5 — Refuse a deactivated user inside the mapper (AC: #7)
  - [ ] In `src/config/authorization/mapper.py`, make `resolve_user` raise `ClaimsRejected` when the resolved user's `is_active` is False. Check the **resolved** row, after the lookup — the row is already loaded at that point, so this costs no additional query. A user created on a miss is active by construction and is unaffected.
  - [ ] Reuse `ClaimsRejected` with its **own reason string** naming deactivation. Do not add an exception type: `exceptions.py` is written for one, Story 2.5 set the precedent by carrying its third refusal the same way, and AD-12 requires it. A shared reason would be actively wrong here — a deactivated user's claims are perfectly valid, and reporting "claims rejected" for what is an operator action sends whoever reads the log to the wrong system.
  - [ ] Reword `resolve_user`'s docstring at `mapper.py:191-193`. "Resolution is by the identity key alone" is about which claim *identifies* the user — email and username are still never consulted — so it is restated, not reversed: resolution is by the identity key alone, **and a resolved row must also be active to be returned**. The deferred-work entry this closes asks specifically for the contract to be visible rather than inherited.
  - [ ] Do **not** also check `is_active` in `OIDCBearerAuthentication` or in the allauth adapter. One home, as with the `jti` rule — a check written in each caller is a check one caller can be written without.
  - [ ] Note the behaviour change to Story 2.6, which is intended and must be tested rather than absorbed: a deactivated user currently receives allauth's own inactive handling, because `perform_login` gates them after `pre_social_login` returns. After this task they are refused earlier, by the mapper, and receive the adapter's 403. That accidental gate is what AC #7's interactive case replaces with a real one.

- [ ] Task 6 — Tests (AC: #1 through #7)
  - [ ] `tests/unit/authorization/test_jwks.py` (new) — the AC #5 tests that "belong to that code":
    - a first `get_signing_key` triggers exactly one fetch (assert against a stubbed fetch callable, not a real HTTP mock);
    - a second call for the same `kid` triggers none;
    - an uncached `kid` triggers exactly **one** refetch (AC #4);
    - a second uncached `kid` inside the rate-limit window triggers **zero** further fetches and raises;
    - a fetch failure leaves the previously cached keys intact;
    - TTL expiry triggers a refetch and only then (AC #6);
    - rotation: a fetch returning a new `kid` makes a token signed by the new key verify with no restart (AC #4).
  - [ ] Use `monkeypatch` on a monotonic-clock seam rather than `time.sleep` — a rate-limit test that sleeps 60 seconds is not a unit test.
  - [ ] `tests/unit/authorization/test_jwks_trust_anchor.py` or cases in the same file — `jwks_url_derives_from_issuer` accepts a matching origin and path prefix, and rejects: a different host, a lookalike host (`idp.example.com.evil.test`), a different port, a different scheme, and a `file://` URL.
  - [ ] `tests/integration/authorization/test_bearer_authentication.py` (new, `@pytest.mark.django_db`) — generate an RSA keypair in-test with `cryptography`, sign tokens with PyJWT, stub the key store's fetch to return the matching JWK set, and drive real requests through the DRF API client against an existing route (`reverse("api:user-me")` is available today):
    - a valid token authenticates and resolves the mapped user (AC #1, #2);
    - each of a bad signature, wrong `iss`, wrong `aud`, and an expired `exp` returns **401** — four separate cases, one per clause of AC #1;
    - a token with `alg` set to something outside the allowlist returns 401;
    - a token with no `jti` returns 401 (the Story 2.5 rule, observed through this surface);
    - no `Authorization` header falls through to session authentication rather than 401ing.
  - [ ] AC #3 — assert nothing fetches at import: import `config.authorization.jwks` and `config.authorization.authentication` with the fetch seam patched to raise, and assert no raise occurs. Then assert the first authenticated request does fetch.
  - [ ] AC #7, three cases across the existing files, because the point of deciding this in the mapper is that one rule serves every surface:
    - `tests/unit/authorization/test_mapper.py` — `resolve_user` raises `ClaimsRejected` for a deactivated user, and the reason names deactivation rather than reusing another refusal's string;
    - `tests/integration/authorization/test_bearer_authentication.py` — a token that verifies cleanly against a deactivated user's identity returns **401**, not 200. Without the mapper check this is the case that authenticates a deactivated principal on every API request, so it is the one that must fail if the check is ever removed;
    - `tests/integration/authorization/test_adapters.py` — the interactive login of a deactivated user returns the adapter's **403**. This is a new assertion over Story 2.6's shipped behaviour, and it is deliberate: today the path is gated only because allauth's `perform_login` happens to check `is_active`, and nothing pins that.
  - [ ] Run `pixi run test`, `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-23 (binding rule):** "JWKS is fetched lazily on the first Bearer request that needs it, never at import or boot. Keys are cached by `kid`. A token presenting an uncached `kid` triggers one refetch, rate-limited so an attacker cannot drive fetches. TTL is a backstop for key removal only. The trust anchor is derived from the configured OIDC issuer; a JWKS location not derived from it is refused at startup. **That check is syntactic and can be nothing else.** Verifying a JWKS location against the issuer's published discovery document requires fetching it, which is the boot-time network call FR-23 forbids — so startup can only apply a string-derivation rule over the configured issuer. An issuer whose real `jwks_uri` does not match the derivation surfaces on the first Bearer request, not at boot. Recorded as L-4 in the tech-verification review; 'derived from' must not be read as 'confirmed against'. **PyJWT does not provide this.** `PyJWKClient.cache_keys` defaults to `False`, its unknown-`kid` refetch has no rate limiting or backoff, and its LRU has no TTL. This policy is component code wrapping PyJWT, and the tests belong to it." *Prevents:* "a cache TTL that must be tuned against an IdP policy nobody has published; a boot that reaches the network; and **the assumption that the library already does this**."
- **Why `PyJWKClient` is not used — verified against PyJWT source, so state it in the module docstring rather than re-deriving it:**
  1. `PyJWKClient.__init__` defaults `cache_keys=False`; the per-`kid` LRU is opt-in, and the default cache is the whole JWK Set response at `lifespan=300`.
  2. `get_signing_key` refetches unconditionally on an unmatched `kid` — "no rate limiting, no backoff, no circuit breaker. A caller sending tokens bearing random `kid` values produces one outbound JWKS fetch per request." On an unauthenticated path that is an amplification vector against the IdP's JWKS endpoint.
  3. The Tier-2 LRU has **no time-based expiration** — entries evict only when the cache exceeds `max_cached_keys` (default 16); `lifespan` does not apply to it. A key rotated *in place* (same `kid`, new material) is served stale indefinitely, which is exactly what a TTL is supposed to backstop. This is why the wrapper's TTL is real and PyJWT's is not.
  - Two PyJWT behaviours the design keeps and should be matched: the constructor rejects non-`http(s)` URIs (blocking `jku`-driven local file reads), and the fetch writes the cache only on success.
  - PyJWT needs no extra library for the network — it uses stdlib `urllib.request`. `cryptography` is required for RS256/ES256.
  - allauth already ships a JWKS-by-`kid` implementation (`allauth/socialaccount/internal/jwtkit.py`). **AD-23 is choosing to build this rather than being forced to** — the choice buys the rate limiting neither library provides. Do not "simplify" by delegating to either.
- **AD-10 (relevant half):** "**Resolve** … runs on every authentication, including every Bearer request, and is a single indexed read … Sync … runs once per credential epoch: … once per Bearer token at first sighting of its `jti`. **A token with no `jti` is rejected with 401.**" The authentication class calls `resolve_user` then `sync_once_per_epoch` and nothing else. It does not decide when to sync — the mapper does.
- **FR-5:** "a DRF `BaseAuthentication` subclass validating `Authorization: Bearer <JWT>` against JWKS, verifying signature, `iss`, `aud` and `exp`, with lazy retrieval and `kid`-keyed caching."
- **FR-23:** "Nothing on the local start path reaches the network at boot — OIDC discovery and JWKS retrieval are lazy." A module-level fetch, an `AppConfig.ready()` warm-up, or a Django system check that touches the network all violate this and would break Epic 3's clone-and-run contract.
- **AD-24 (what you must not do):** no conditional imports, no `try/except ImportError`, no settings-module inheritance. `pyjwt` and `cryptography` are unconditional `core` dependencies in all six combinations.
- **Spine, Consistency Conventions → Runtime errors:** "Authentication failure is 401." Never bare `except:`; never `except X: pass`.
- **Spine, Consistency Conventions → Logging:** structured JSON to stdout with `request_id`/`trace_id`/`span_id`. `structlog` only. Never `print()`, never stdlib `logging`, never the token.

### Where a deactivated user is refused — decided 2026-08-17, not open

Story 2.4's review deferred this and recorded that **this story must not be written before it is decided**. It is decided: the refusal lives inside `resolve_user`, raised as `ClaimsRejected`, and every caller inherits it. Task 5 implements it. Do not re-open the question mid-story; if the implementation turns out to conflict with something here, that is an escalation, not a judgement call.

The reasoning, so it is not re-derived:

- **The hot-path objection was the main argument against mapper placement, and it does not survive contact with the code.** `resolve_user` has already loaded the row by the time the check happens, so reading `user.is_active` costs zero additional queries even on the Bearer path that runs it per request. The concern was real in the abstract and empty in this specific case.
- **FR-8's "protocol-free" constrains HTTP, not access decisions.** The mapper already refuses claims and already decides access in `sync_authorization`. `ClaimsRejected` is the vehicle each caller already translates — 403 on the interactive path, 401 here — so this adds a reason to an existing mechanism rather than bending the design.
- **Per-caller placement fails by omission, and the omission has already happened once.** Story 2.6 shipped with no explicit check, safe only because allauth's `perform_login` gates inactive users after `pre_social_login` returns. No test pins that, and nothing would notice it being lost. Three copies of a security check needing all three to be right is the weaker position.

What this does *not* license: `is_active` does not become a general authorization input the mapper consults for anything else, and no second local-state check joins it without its own decision. The rule is one line — a resolved row must be active — and its whole purpose is that the three entry points cannot disagree about it.

### Why this cache is process-local and the epoch record is not

AD-10 forces the credential-epoch record into a database table because "two of six combinations have no Redis" and a per-process cache would make "first sighting" mean first-sighting-per-worker-per-restart — a **correctness** failure.

The JWKS cache has the opposite shape and the reasoning does not transfer: it caches **public** key material, and a per-worker duplicate costs one extra outbound fetch, not a wrong authorization decision. Keep it in process memory. Do **not** move it into `django.core.cache` "for consistency with the epoch record", and do not put it in the database.

### R-2 applies to this surface

**R-2 — Bearer revocation latency is the token's lifetime.** "AD-10 syncs once per `jti`, so a group revoked at the IdP is honoured until the token expires." Nothing in this story shortens that window, and nothing should try: shorter TTLs on the key cache have no effect on it (they govern key material, not authorization), and a per-request re-sync reintroduces the write amplification AD-10 exists to prevent. Record R-2 in the authentication class's module docstring.

### SC-6 cannot be closed here

SC-6 requires a real IdP identity authenticating through both flows. It is an **external exit criterion no story closes** — owner: the platform group, after Epic 2. Every AC here passes against a locally generated keypair and a stubbed JWKS document; that is deliberate and is not proof of SC-6.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
|---|---|---|
| `src/config/authorization/jwks.py` | NEW | `JWKSKeyStore`, `KEY_STORE`, `jwks_url_derives_from_issuer`, `JWKSKeyUnavailable`. |
| `src/config/authorization/authentication.py` | NEW | `OIDCBearerAuthentication`. |
| `src/config/authorization/exceptions.py` | UPDATE | Created by Story 2.4 with `ClaimsRejected`. Add `JWKSKeyUnavailable` here rather than in `jwks.py` if it needs to be caught outside — one exceptions module for the package. |
| `src/config/settings/base.py` | UPDATE | Today: `REST_FRAMEWORK` at 357–364 with `SessionAuthentication` and `TokenAuthentication` in `DEFAULT_AUTHENTICATION_CLASSES`, `IsAuthenticated` default permission, `drf_spectacular.openapi.AutoSchema` schema class. Adds the Bearer class first in the tuple and the `COMPONENT_JWKS_*` / `COMPONENT_OIDC_ALGORITHMS` reads. **Preserve:** `DEFAULT_PERMISSION_CLASSES`, `DEFAULT_SCHEMA_CLASS`, `CORS_URLS_REGEX` and the annotated `SPECTACULAR_SETTINGS: dict[str, Any]` with its explanatory comment. |
| `src/config/authorization/mapper.py` | UPDATE | Created by Story 2.4, extended by 2.5. Task 5 adds the `is_active` refusal to `resolve_user` with its own `ClaimsRejected` reason, and restates the docstring at 191–193. **Preserve:** everything else — `sync_authorization`, `sync_for_interactive`, `sync_once_per_epoch`, the epoch-race handling, and the identity-key resolution itself, none of which this story touches. |
| `tests/unit/authorization/test_jwks.py` | NEW | The cache/refetch/rate-limit/TTL suite AC #5 requires. |
| `tests/integration/authorization/test_bearer_authentication.py` | NEW | Real tokens, real DRF request cycle, four separate 401 cases, plus AC #7's deactivated-user 401. |
| `tests/unit/authorization/test_mapper.py` | UPDATE | Exists from Story 2.4. Adds the AC #7 refusal case and its reason string. |
| `tests/integration/authorization/test_adapters.py` | UPDATE | Exists from Story 2.6. Adds AC #7's interactive 403, replacing an accidental gate with a pinned one. |

`pixi.toml` needs **no change** in this story: `pyjwt`, `cryptography` and `requests` were declared in Story 2.6.

### Testing Requirements

- Test tree mirrors `src/`: `jwks.py` → `tests/unit/authorization/test_jwks.py`; `authentication.py` → `tests/integration/authorization/test_bearer_authentication.py` (it needs the database, because the mapper resolves a user).
- `tests/integration/conftest.py` auto-applies `pytest.mark.integration` under `tests/integration/`; DB access still needs `@pytest.mark.django_db`.
- **AC #5 explicitly assigns the caching, refetch and rate-limiting tests to this code.** They are not optional and they are not integration tests — they are unit tests over the store with a stubbed fetch seam. Design `JWKSKeyStore` to take its fetch callable as a constructor argument so the seam exists without patching module internals.
- Generate the RSA keypair in-test with `cryptography.hazmat.primitives.asymmetric.rsa`. Never commit a key. NFR-7: "Secrets never live in source." A 2048-bit generation per test module (session-scoped fixture) keeps the suite fast enough.
- No test may make a real outbound request. If a test would, the fetch seam was not used.
- Integration tests leave state as found — default `django_db` rollback. Call `KEY_STORE.reset()` in a fixture so cache state does not leak between tests; a leaking module-level cache is the most likely source of order-dependent failures here.
- Coverage floor 90% including templates (AD-20), gate via `pixi run test-cov` inside `pixi run ci`. Add nothing to `[tool.coverage.run] omit` — in particular, do not omit `jwks.py` on the grounds that it "does network I/O". The seam is what makes it coverable.

#### Project Structure Notes

Matches the spine's Capability map: "Authentication & authorization (§4.2) | `src/config/authorization/`, DRF auth class, allauth adapter". After this story `src/config/authorization/` holds `__init__.py`, `claims.py`, `exceptions.py`, `mapper.py`, `adapters.py`, `jwks.py`, `authentication.py` — the whole §4.2 surface in one place, which is what FR-8's "one shared mapper at `src/config/authorization/`" requires.

Epic 3 Story 3.5 will mint a locally signed JWT that **this exact class** verifies (FR-20). Keep the fetch seam and the algorithm allowlist configurable enough for a locally generated keypair to be a legitimate configuration, without adding a development-only branch — AD-24 forbids the conditional and CG-4 forbids substituting what could run for real.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-23]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-10]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-2
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/reviews/review-tech-verification.md:70-104] — H-3: the three verified corrections to PyJWT's behaviour, and the two behaviours worth matching
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/reviews/review-tech-verification.md:223-240] — L-4: allauth ships its own JWKS-by-`kid`; the startup trust-anchor check can only be string derivation
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.7]
- [Source: _bmad-output/planning-artifacts/epics.md:33,57] — FR-5, FR-23
- [Source: _bmad-output/planning-artifacts/epics.md:314-326] — the refusal table; condition 4 (JWKS trust anchor) is Epic 4's
- [Source: _bmad-output/planning-artifacts/implementation-readiness-report-2026-08-15.md:404] — "2.6 and 2.7 precede 2.8 so the replacement credential paths exist before the old ones are deleted"
- [Source: src/config/settings/base.py:357-364] — the current `REST_FRAMEWORK` block
- [Source: src/config/api_router.py:9-13] — `api:user-me` and the other routes available to drive Bearer requests against
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Deferred from: review of 2-4-the-mapper-resolves-an-identity-to-a-user] — the `is_active` entry this story closes, with the decision recorded on it and the two rejected alternatives
- [Source: src/config/authorization/mapper.py:183-203] — `resolve_user` and the docstring Task 5 restates
- [Source: src/config/authorization/exceptions.py:22-37] — `ClaimsRejected` and the `reason` field the new refusal uses
- [Source: src/config/authorization/adapters.py:155-165] — Story 2.6's `pre_social_login`, which inherits the refusal and turns it into the 403 AC #7 asserts

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
