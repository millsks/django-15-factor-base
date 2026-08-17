---
baseline_revision: a1548d0
final_revision: d0cd417
review_loop_iteration: 0
status: done
followup_review_recommended: true
warnings: []
---

# Story 2.7: An API client authenticates programmatically against the IdP

Status: done

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

- [x] Task 1 — Build the key store at `src/config/authorization/jwks.py` (AC: #3, #4, #5, #6)
  - [x] `class JWKSKeyStore` holding a process-local `dict[str, PyJWK]` keyed by `kid`, a `_fetched_at: float`, and a `_last_fetch_attempt: float`. Construct it once at module scope as `KEY_STORE = JWKSKeyStore()`; **construct only — never fetch in the constructor** (AC #3).
  - [x] `def get_signing_key(self, kid: str) -> PyJWK` — the one entry point. Cache hit and not TTL-expired → return. Miss or expired → attempt a refetch subject to the rate limit; then look up again; still missing → raise `JWKSKeyUnavailable`.
  - [x] Rate limit: refuse to fetch if `monotonic() - self._last_fetch_attempt < min_refetch_seconds`. Set `_last_fetch_attempt` **before** the request, so a failing IdP does not turn into a fetch loop. Read the window from `COMPONENT_JWKS_MIN_REFETCH_SECONDS` (default 60). AC #4's "rate-limited so it cannot be driven by an attacker" is the whole point: the Bearer path is unauthenticated at this moment, so a caller sending random `kid`s must not be able to produce one outbound fetch per request.
  - [x] TTL: `COMPONENT_JWKS_TTL_SECONDS` (default 3600). Its **only** job is to notice a key that was removed at the IdP — that is AC #6's "exists only as a backstop for key removal". Do not shorten it in an attempt to catch rotation faster; rotation is handled by the uncached-`kid` refetch, not by the TTL.
  - [x] Write the cache **only on a successful fetch**, replacing the dict wholesale. A transient IdP outage must not evict a good cached JWKS.
  - [x] Parse the fetched document with `jwt.PyJWKSet.from_dict(...)` and index by each key's `key_id`. Use `requests` for the HTTP call (declared in Story 2.6). Set an explicit connect/read timeout — an IdP that never answers must not hold a worker.
  - [x] Use a `threading.Lock` around fetch-and-swap so concurrent requests in a threaded worker produce one fetch, not N.
  - [x] `def reset(self) -> None` for tests to clear state between cases. It exists for tests and is documented as such; no production path calls it.

- [x] Task 2 — Derive the trust anchor, do not accept one (AC: #4, and AD-23's trust-anchor rule)
  - [x] `def jwks_url_derives_from_issuer(issuer: str, jwks_url: str) -> bool` — true only when scheme, host and port match the issuer exactly and the JWKS path is under the issuer's path. Compare parsed `urllib.parse.urlsplit` components, never substrings.
  - [x] Read `COMPONENT_OIDC_JWKS_URL`, defaulting to the conventional derivation from `COMPONENT_OIDC_ISSUER`. `COMPONENT_OIDC_ISSUER` is set in Story 2.6 and is the single trust anchor — do not introduce a second issuer variable.
  - [x] Reject non-`http(s)` schemes outright. PyJWT's own client now does this to block `jku`-header-driven local file reads; the wrapper must not be weaker than the thing it replaces.
  - [x] The **startup refusal** for a JWKS location not derived from the issuer is Epic 4's (FR-13, condition 4 of the refusal table) — this story exports the predicate, Epic 4 wires the `ImproperlyConfigured`. Note honestly, in the function's docstring, what the check can and cannot be: it is **syntactic and can be nothing else** — a string-derivation rule over the configured issuer, not a check against the discovery document, because verifying against discovery would require the boot-time network fetch FR-23 forbids. State the consequence too: an issuer whose real `jwks_uri` does not match the derivation **surfaces on the first Bearer request, not at boot** (AD-23, L-4). "Derived from" is not "confirmed against", and a reader who takes the startup refusal as proof of a working JWKS location has misread it.

- [x] Task 3 — Build the DRF authentication class at `src/config/authorization/authentication.py` (AC: #1, #2)
  - [x] `class OIDCBearerAuthentication(BaseAuthentication)` with `def authenticate(self, request) -> tuple[User, Mapping[str, Any]] | None`.
  - [x] Return `None` — not a raise — when the `Authorization` header is absent or its scheme is not `Bearer`. Returning `None` lets DRF fall through to `SessionAuthentication`; raising here would break every session-authenticated request.
  - [x] Read `kid` from `jwt.get_unverified_header(token)`, fetch the key from `KEY_STORE`, then `jwt.decode(token, key=key.key, algorithms=ALLOWED_ALGORITHMS, issuer=..., audience=..., options={"require": ["exp", "iss", "aud"]})`.
  - [x] `ALLOWED_ALGORITHMS` is an explicit allowlist read from `COMPONENT_OIDC_ALGORITHMS` (default `["RS256"]`). **Never** take the algorithm from the token's own header — that is the `alg=none` / algorithm-confusion family of attacks.
  - [x] Translate every failure to `rest_framework.exceptions.AuthenticationFailed`: `ExpiredSignatureError`, `InvalidIssuerError`, `InvalidAudienceError`, `InvalidSignatureError`, `DecodeError`, `JWKSKeyUnavailable`, and `ClaimsRejected` from the mapper. Catch each by its specific type — never a bare `except:`, never `except X: pass`.
  - [x] Implement `def authenticate_header(self, request) -> str: return "Bearer"`. **Without this DRF returns 403, not 401**, and every AC in this story that says "rejected with 401" fails.
  - [x] On success call `resolve_user(claims)` then `sync_once_per_epoch(user, claims)` from `config.authorization.mapper`, and return `(user, claims)`. The class contains **no mapping logic of its own** (AC #2) — no group reading, no `is_staff`, no username handling.
  - [x] The no-`jti` 401 (Story 2.5 AC #4) arrives here as `ClaimsRejected` from `sync_once_per_epoch` and is translated like any other. Do not duplicate the `jti` check in this class; the rule has one home, in the mapper.
  - [x] Emit one `structlog` event per rejection at warning with the reason and the `kid`, never the token. Never log the raw `Authorization` header.

- [x] Task 4 — Wire the class into DRF (AC: #1)
  - [x] In `src/config/settings/base.py`, add `"config.authorization.authentication.OIDCBearerAuthentication"` to `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` (currently lines 357–364).
  - [x] Order it **before** `SessionAuthentication` so a request carrying both a session cookie and a Bearer header is decided by the Bearer credential.
  - [x] Leave `"rest_framework.authentication.TokenAuthentication"` in place in this story. Its removal is Story 2.8's, and the readiness assessment records the ordering as load-bearing: "2.6 and 2.7 precede 2.8 so the replacement credential paths exist before the old ones are deleted."
  - [x] Add no new package to `pixi.toml`. `pyjwt`, `cryptography` and `requests` were declared in Story 2.6 Task 1 — confirm all three are present in `[dependencies]` and in `pixi.lock` before writing code against them.

- [x] Task 5 — Refuse a deactivated user inside the mapper (AC: #7)
  - [x] In `src/config/authorization/mapper.py`, make `resolve_user` raise `ClaimsRejected` when the resolved user's `is_active` is False. Check the **resolved** row, after the lookup — the row is already loaded at that point, so this costs no additional query. A user created on a miss is active by construction and is unaffected.
  - [x] Reuse `ClaimsRejected` with its **own reason string** naming deactivation. Do not add an exception type: `exceptions.py` is written for one, Story 2.5 set the precedent by carrying its third refusal the same way, and AD-12 requires it. A shared reason would be actively wrong here — a deactivated user's claims are perfectly valid, and reporting "claims rejected" for what is an operator action sends whoever reads the log to the wrong system.
  - [x] Reword `resolve_user`'s docstring at `mapper.py:191-193`. "Resolution is by the identity key alone" is about which claim *identifies* the user — email and username are still never consulted — so it is restated, not reversed: resolution is by the identity key alone, **and a resolved row must also be active to be returned**. The deferred-work entry this closes asks specifically for the contract to be visible rather than inherited.
  - [x] Do **not** also check `is_active` in `OIDCBearerAuthentication` or in the allauth adapter. One home, as with the `jti` rule — a check written in each caller is a check one caller can be written without.
  - [x] Note the behaviour change to Story 2.6, which is intended and must be tested rather than absorbed: a deactivated user currently receives allauth's own inactive handling, because `perform_login` gates them after `pre_social_login` returns. After this task they are refused earlier, by the mapper, and receive the adapter's 403. That accidental gate is what AC #7's interactive case replaces with a real one.

- [x] Task 6 — Tests (AC: #1 through #7)
  - [x] `tests/unit/authorization/test_jwks.py` (new) — the AC #5 tests that "belong to that code":
    - a first `get_signing_key` triggers exactly one fetch (assert against a stubbed fetch callable, not a real HTTP mock);
    - a second call for the same `kid` triggers none;
    - an uncached `kid` triggers exactly **one** refetch (AC #4);
    - a second uncached `kid` inside the rate-limit window triggers **zero** further fetches and raises;
    - a fetch failure leaves the previously cached keys intact;
    - TTL expiry triggers a refetch and only then (AC #6);
    - rotation: a fetch returning a new `kid` makes a token signed by the new key verify with no restart (AC #4).
  - [x] Use `monkeypatch` on a monotonic-clock seam rather than `time.sleep` — a rate-limit test that sleeps 60 seconds is not a unit test.
  - [x] `tests/unit/authorization/test_jwks_trust_anchor.py` or cases in the same file — `jwks_url_derives_from_issuer` accepts a matching origin and path prefix, and rejects: a different host, a lookalike host (`idp.example.com.evil.test`), a different port, a different scheme, and a `file://` URL.
  - [x] `tests/integration/authorization/test_bearer_authentication.py` (new, `@pytest.mark.django_db`) — generate an RSA keypair in-test with `cryptography`, sign tokens with PyJWT, stub the key store's fetch to return the matching JWK set, and drive real requests through the DRF API client against an existing route (`reverse("api:user-me")` is available today):
    - a valid token authenticates and resolves the mapped user (AC #1, #2);
    - each of a bad signature, wrong `iss`, wrong `aud`, and an expired `exp` returns **401** — four separate cases, one per clause of AC #1;
    - a token with `alg` set to something outside the allowlist returns 401;
    - a token with no `jti` returns 401 (the Story 2.5 rule, observed through this surface);
    - no `Authorization` header falls through to session authentication rather than 401ing.
  - [x] AC #3 — assert nothing fetches at import: import `config.authorization.jwks` and `config.authorization.authentication` with the fetch seam patched to raise, and assert no raise occurs. Then assert the first authenticated request does fetch.
  - [x] AC #7, three cases across the existing files, because the point of deciding this in the mapper is that one rule serves every surface:
    - `tests/unit/authorization/test_mapper.py` — `resolve_user` raises `ClaimsRejected` for a deactivated user, and the reason names deactivation rather than reusing another refusal's string;
    - `tests/integration/authorization/test_bearer_authentication.py` — a token that verifies cleanly against a deactivated user's identity returns **401**, not 200. Without the mapper check this is the case that authenticates a deactivated principal on every API request, so it is the one that must fail if the check is ever removed;
    - `tests/integration/authorization/test_adapters.py` — the interactive login of a deactivated user returns the adapter's **403**. This is a new assertion over Story 2.6's shipped behaviour, and it is deliberate: today the path is gated only because allauth's `perform_login` happens to check `is_active`, and nothing pins that.
  - [x] Run `pixi run test`, `pixi run test-integration`, then `pixi run ci`.

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

claude-opus-5[1m] (Claude Code), driven as a single implementation session against the frozen spec.

### Debug Log References

- `pixi run ci` — **exit 0**. 643 passed, total coverage 95.60% (floor 90). `src/config/authorization/jwks.py` and `src/config/authorization/authentication.py` both at **100%**.
- PostgreSQL 17 run (project memory `validate-model-changes-against-postgres`): `DATABASE_URL=postgres://…@localhost:5432/app_test pixi run test-cov --create-db` — exit 0, 643 passed, same coverage. `tests/integration/test_postgres_schema.py` asserts `connection.vendor` against the `DATABASE_URL` scheme, so the run is self-proving rather than a silent sqlite fallback. No migration and no schema change in this story; the run is here because the Bearer path writes claim-derived attributes and `CredentialEpoch` rows on a surface that had never been exercised end to end.
- Three gate iterations, each on a distinct signature:
  1. `ruff check .` — `RUF100` (an unused `S105` on `_SCHEME`), `RUF022` (`__all__` unsorted) and two `EM101`/`TRY003` pairs on literal exception messages in `fetch_jwks_document`. Fixed by hoisting the three refusal strings to module constants, matching what `mapper.py` already does at every `raise`.
  2. `pixi run test` — `test_an_issuer_with_no_host_anchors_nothing` failed. `_origin` returned `None` for a hostless URL and `None == None` made `https:///a` derive from `https:///`, anchoring the trust decision on nothing. A real defect the test caught before the gate did; fixed in `jwks_url_derives_from_issuer`.
  3. `pixi run test-integration` — `tests/integration/users/test_api_openapi.py::test_api_docs_not_accessible_by_anonymous_users` failed, 401 against an expected 403. Intended: see the first completion note.
- `PLR2004` on the fetch-count assertions was fixed by naming `AFTER_ONE_REFETCH` rather than by an ignore.

### Completion Notes List

- **`authenticate_header` changes the anonymous response across the whole API, and that is the point.** DRF renders a permission failure as 403 unless *some* authenticator offers a `WWW-Authenticate` challenge; before this story none did, so an unauthenticated request to any DRF route answered 403. Task 3 requires the method — without it every "rejected with 401" in this story is a 403 — so installing the class first necessarily moves the anonymous answer to 401 everywhere. It moves *onto* the spine's rule ("authentication failure is 401") rather than away from it. One existing test asserted the old behaviour and was updated with the reasoning written into it: `tests/integration/users/test_api_openapi.py`. That file is not in the Source Tree table, and the change is recorded here rather than absorbed silently.
- **`COMPONENT_OIDC_AUDIENCE` is a variable the spec does not name, added deliberately.** AC #1 requires `aud` verification and the spec's Task 3 passes `audience=…` without saying where it comes from. It defaults to `COMPONENT_OIDC_CLIENT_ID`, which is what an IdP issuing tokens for this component's own client puts in `aud`, so a single-client deployment configures nothing extra; a deployment whose IdP names a separate resource server (Keycloak's usual shape) sets the variable. It is never defaulted to "any": `aud` is in the `require` list, so an unconfigured audience refuses every token rather than accepting all of them. This does **not** touch AD-23's "no second issuer variable" rule — `COMPONENT_OIDC_ISSUER` is read once into `OIDC_ISSUER` and both the allauth provider block and the Bearer path consume that one name, which `test_there_is_one_issuer_variable_and_both_consumers_read_it` pins.
- **`InvalidTokenError` closes the catch tuple, and it is not a bare `except`.** The spec names five PyJWT exceptions; two more are reachable and required by its own test list — `InvalidAlgorithmError` (the algorithm-allowlist case) and `MissingRequiredClaimError` (the `require` option). All seven plus `InvalidTokenError`, PyJWT's own root for a *verdict about the token*, are named in `_TOKEN_REFUSED`. The root is included so a PyJWT release adding a subclass still lands on a 401 instead of escaping as a 500; every arrival is logged with its concrete class name, so nothing is swallowed. `PyJWTError` — which also covers key-handling faults — is deliberately **not** caught.
- **The rate limit is stamped before the request and the fetch happens under the lock.** Both are load-bearing and both have their own test. Stamping after the request would let a slow-failing IdP be retried once per request; releasing the lock around the fetch would let N concurrent workers produce N fetches, which is the stampede the lock exists to prevent. Holding it is why `_FETCH_TIMEOUT` is explicit rather than left to `requests`' default of none.
- **A refetch the rate limit refused still serves a stale cached key.** `get_signing_key` re-reads the cache without the TTL gate after a refresh attempt. The alternative — refusing every request while an IdP is unreachable — converts a degraded dependency into a total outage, and the TTL is a backstop for key *removal*, not a validity bound on key material. `test_a_failed_fetch_leaves_the_cached_keys_intact` pins it.
- **The trust-anchor predicate compares parsed components and rejects a hostless origin.** The lookalike case (`idp.example.com.evil.test`) is what decides the design: a substring rule would hand an attacker the right to publish this component's signing keys. Default ports are normalised so `https://idp.example.com` and `…:443` are one origin, and the path rule matches at segment boundaries so `/realms/main-evil` is not under `/realms/main`. Its docstring states honestly what the check can and cannot be, and Epic 4 still owns the `ImproperlyConfigured`.
- **No test in this repository opens a socket.** `JWKSKeyStore` takes both its fetch callable and its clock as constructor arguments. The integration suite reaches the module-level `KEY_STORE` through `monkeypatch` on that same seam and calls `reset()` on both sides of every case, so the process-wide cache cannot leak between tests. The four cases that exercise the *real* `fetch_jwks_document` replace `requests.get`.
- **AC #3's import assertion loads both modules fresh under a throwaway name rather than reloading them.** `importlib.reload` would rebind the process's real `KEY_STORE` and leave every later test holding a different object than the authentication class does — an order-dependent failure introduced by the test that exists to prevent one.
- **AC #7's mapper case is split across three files, not the two the spec names.** `tests/unit/authorization/test_mapper.py` does not exist; the mapper's unit tests are `test_mapper_resolve.py` and `test_mapper_sync.py`, and the unit half opens no database. So the refusal is pinned in `tests/unit/authorization/test_mapper_resolve.py` by calling `_reject_a_deactivated_user` directly — the same shape `test_an_identity_key_exactly_the_field_length_is_storable` already uses for the pre-query refusals — and in `tests/integration/authorization/test_mapper_resolve.py` through `resolve_user` against a real row. The Bearer 401 and the interactive 403 land where the spec puts them.
- **The `is_active` check has exactly one home.** Neither `OIDCBearerAuthentication` nor the allauth adapter tests or reads `is_active`; both inherit the refusal through `ClaimsRejected`. The interactive 403 that Story 2.6 got by accident — allauth's `perform_login` gating after `pre_social_login` returns — is now pinned by `test_a_deactivated_person_is_refused_by_the_mapper_rather_than_by_allauth`, with a reactivation control beside it.
- **Spec-vs-tree drift, recorded rather than silently accommodated:** the Source Tree says `REST_FRAMEWORK` is at `src/config/settings/base.py:357-364`; it is at 451-458 in the tree at baseline `a1548d0` (Story 2.6 inserted the provider block above it). The block's contents matched the description exactly and everything the table says to preserve was preserved.
- **SC-6 is not closed and cannot be.** Every case here passes against a locally generated keypair and a stubbed JWKS document. It requires a real IdP identity through both flows and is an external exit criterion owned by the platform group after Epic 2; the integration module's docstring says so.
- **R-2 is recorded in `authentication.py`'s module docstring** and nothing in this story tries to shorten the window. `pixi.toml` and `pixi.lock` are untouched: `pyjwt` 2.13.0, `cryptography` and `requests` 2.34.2 were all confirmed present in `[dependencies]` and in the lock before any code was written against them.
- Task names in this repository are `format` / `lint` / `typecheck` / `test` / `test-integration` / `test-cov` / `ci` — not `fmt` / `check` / `cov`.

### File List

| Path | NEW / UPDATE | What changed |
|---|---|---|
| `src/config/authorization/jwks.py` | NEW | `JWKSKeyStore` (lazy, `kid`-keyed, TTL, rate-limited refetch, `threading.Lock`, `reset`), `KEY_STORE`, `fetch_jwks_document`, `jwks_url_derives_from_issuer`, `conventional_jwks_url`, `configured_jwks_url`. Module docstring carries the three verified `PyJWKClient` findings and the process-local-cache reasoning. |
| `src/config/authorization/authentication.py` | NEW | `OIDCBearerAuthentication` — `authenticate`, `authenticate_header`, and the three private steps. Module docstring carries R-2 and the `authenticate_header` warning. |
| `src/config/authorization/exceptions.py` | UPDATE | Adds `JWKSKeyUnavailable` with its own `reason`, and restates the module docstring around two refusal types rather than one. `ClaimsRejected` untouched. |
| `src/config/authorization/mapper.py` | UPDATE | `_reject_a_deactivated_user` and the `_USER_DEACTIVATED` reason; `resolve_user` calls it on the hit path; the docstring at 191-193 restated and its refusal list grown from three to four. Nothing else changed. |
| `src/config/settings/base.py` | UPDATE | `OIDC_ISSUER` and `OIDC_CLIENT_ID` hoisted to named reads the provider block now consumes; adds `OIDC_JWKS_URL`, `OIDC_AUDIENCE`, `OIDC_ALGORITHMS`, `JWKS_TTL_SECONDS`, `JWKS_MIN_REFETCH_SECONDS`; `OIDCBearerAuthentication` first in `DEFAULT_AUTHENTICATION_CLASSES`, ahead of `SessionAuthentication`, with `TokenAuthentication` left in place. `DEFAULT_PERMISSION_CLASSES`, `DEFAULT_SCHEMA_CLASS`, `CORS_URLS_REGEX` and the annotated `SPECTACULAR_SETTINGS` preserved. |
| `tests/jwt_keys.py` | NEW | In-test RSA generation (`SigningKey`, `generate`, `jwks_document`, `sign_with_a_symmetric_key`) and the two seams the suites share (`StubFetch`, `FakeClock`). No committed key material (NFR-7). |
| `tests/unit/authorization/test_jwks.py` | NEW | 39 cases: the AC #5 cache/refetch/rate-limit/TTL suite, the rotation case, the AC #3 no-fetch-at-construction and no-fetch-at-import probes, the trust-anchor table, and the default fetch with `requests.get` replaced. |
| `tests/integration/authorization/test_bearer_authentication.py` | NEW | 25 cases through the real DRF request cycle against `api:user-me`: the valid token, four separate 401s for AC #1's four clauses, the required-claim omissions, the algorithm allowlist, an unpublished `kid`, no `kid`, malformed headers, the `WWW-Authenticate` challenge, the missing-`jti` 401, AC #7's deactivated-user 401 with its active control, AC #3's first-request fetch, and the two fall-through cases. Plus AC #2's source-level "no mapping logic" assertion. |
| `tests/unit/authorization/test_mapper_resolve.py` | UPDATE | AC #7 without a database: the refusal, the control, and that the reason is shared with no other refusal. |
| `tests/integration/authorization/test_mapper_resolve.py` | UPDATE | AC #7 against a real row: the refusal through `resolve_user`, its reason, its reported event, the active control, and that a user created on a miss is active by construction. |
| `tests/integration/authorization/test_adapters.py` | UPDATE | AC #7's interactive 403, replacing allauth's accidental gate with a pinned one, plus a reactivation control. |
| `tests/unit/test_settings.py` | UPDATE | The Bearer wiring and its configuration: class ordering, `TokenAuthentication` still installed, the rest of the `REST_FRAMEWORK` block preserved, the declared defaults, the single issuer variable, the audience fallback and override, and the environment-driven windows. `no_oidc_env` grows the five new variables. |
| `tests/integration/users/test_api_openapi.py` | UPDATE | **Not in the Source Tree table.** The anonymous refusal is now 401 with a `Bearer` challenge rather than 403 — see the first completion note. |

## Review Triage Log

### 2026-08-17 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 9: (high 1, medium 5, low 3)
- defer: 5: (high 0, medium 3, low 2)
- reject: 16: (high 0, medium 0, low 16)
- addressed_findings:
  - `[high]` `[patch]` **A key/algorithm mismatch escaped as an unauthenticated 500, not a 401.** `_TOKEN_REFUSED` closed over `InvalidTokenError`, but PyJWT's key-preparation failures sit outside that subtree — verified against the installed PyJWT 2.13: an ES256-signed token checked against an RSA key with `algorithms=["RS256","ES256"]` raises a bare `TypeError`, and the older path raises `InvalidKeyError`. The suite's own settings test blesses `RS256,ES256` as a supported configuration, so an anonymous caller could pick `alg` and `kid` to force a traceback with no `bearer_rejected` event. Added `_KEY_UNUSABLE` / `_DECODE_REFUSED` around `jwt.decode` and corrected the docstring claim that `InvalidTokenError` "closes the set". Pinned by `test_a_token_signed_with_the_other_permitted_family_is_refused_not_crashed`.
  - `[medium]` `[patch]` **A JWK Set whose keys carry no `kid` silently wiped a good cache.** `PyJWKSet.from_dict` accepts such a document (verified: one key parses, `key_id is None`), `_index_by_kid` drops it, and `_refresh` swapped the resulting `{}` in as a success — the exact failure the "written only on success" comment claims to prevent, and the one case the existing malformed-document test misses because `{"keys": []}` raises instead. An empty index is now a failed fetch that leaves the cache intact. Pinned by `test_a_document_whose_keys_carry_no_kid_leaves_the_cached_keys_intact`.
  - `[medium]` `[patch]` **`jwks_url_derives_from_issuer` raised `ValueError` instead of returning a bool.** `urlsplit(...).port` raises on a non-integer or out-of-range port (verified), so the predicate Epic 4 will build a startup `ImproperlyConfigured` on would crash on a typo rather than refuse. Guarded the parse and both port reads; also added a dot-segment check, since `urlsplit` does not normalize and `/realms/main/../../other` passed `_path_is_under` against `/realms/main`. Pinned by `test_an_unparseable_or_escaping_location_is_refused_rather_than_raised` and `test_an_unparseable_issuer_anchors_nothing_either`.
  - `[medium]` `[patch]` **The new credential was invisible in the published API contract.** Verified by generating the schema: three `could not resolve authenticator` warnings and a `securitySchemes` holding only `cookieAuth` and `tokenAuth`. A story whose subject is programmatic API authentication shipped a document that does not describe it. Added `OIDCBearerScheme(OpenApiAuthenticationExtension)` beside the class it targets. Pinned by `test_the_bearer_credential_is_described_in_the_published_contract` and `test_generating_the_schema_resolves_every_authenticator`.
  - `[medium]` `[patch]` **The refusal reason blamed the wrong system.** `_refresh` returned "a fetch was attempted", not "a fetch succeeded", so an unreachable IdP, a non-2xx answer and an unconfigured location were all reported as `no signing key published for the presented kid` — sending an operator to inspect the IdP's key set for a connectivity problem, and contradicting both `JWKSKeyUnavailable`'s own docstring and the argument this same change makes for `_USER_DEACTIVATED` in the mapper. Replaced the bool with a three-state `_Refresh` outcome and gave the failed fetch its own reason; `fetch_jwks_document` now raises `JWKSKeyUnavailable` rather than `requests.RequestException` for a payload-shape problem, which was making the same event indistinguishable from a connection error. Pinned by three cases asserting the three reasons differ.
  - `[medium]` `[patch]` **Log fields and the outbound fetch were attacker-steerable.** Four sub-fixes: the token's `kid` was written unbounded into every refusal event and is now truncated at 64 characters; `requests.get` followed redirects by default, so a 30x could move the signing-key fetch to a host the origin pinning never validated, and now passes `allow_redirects=False`; nothing bounded the response body, and it is now streamed to a 1 MiB cap with an over-size response treated as a failed fetch; and `_refresh` caught bare `ValueError`, wide enough to report a programming error as an IdP problem, now narrowed with `_index_by_kid` translating the three non-total `PyJWKSet.from_dict` failures instead. Each pinned by its own case.
  - `[low]` `[patch]` **Input-shape guards.** `_kid` validated `kid.strip()` but returned the unstripped value, so a padded `kid` never matched the cache and provoked a refetch every window; `_algorithms()` turned a bare-string setting into `('R','S','2','5','6')` and refused every token; `_audience()` treated a whitespace-only value as configured. All three fixed, with six cases in the new `tests/unit/authorization/test_authentication.py`.
  - `[low]` `[patch]` **Zero and negative configuration windows.** `COMPONENT_JWKS_MIN_REFETCH_SECONDS=0` disabled the rate limit outright — re-arming the amplification the module exists to prevent — and a negative TTL made every request take the lock. Both are now clamped to floors in `base.py` with the reasoning in the comment; the declared defaults are unchanged. Pinned by two parametrized cases in `test_settings.py`.
  - `[low]` `[patch]` **No lever for clock skew.** `jwt.decode` ran with zero tolerance, so a few seconds of IdP drift produced intermittent 401s with no operator remedy short of a code change. Added `COMPONENT_OIDC_LEEWAY_SECONDS` passed as `leeway`, **defaulting to 0.0** so the shipped verification posture is exactly as specified — this adds the lever without changing the policy. Pinned by `test_the_shipped_clock_skew_tolerance_is_zero` and the admitted/refused integration pair.

Deferred (five entries written to the ledger): the ID-token-as-access-token consequence of defaulting `aud` to the client id; the store lock held across a fetch with no total-duration bound; `PyJWKSet.from_dict`'s three non-total failure modes reachable by any future direct caller; the substring-scan technique behind AC #2's structural assertion; and the Story 2.6 structlog save/restore gap, which this story enlarged rather than caused.

Rejected as noise, with the reason each came back rather than being left unexamined:

- **The trust-anchor predicate has no production call site.** Correct, and it is the spec's own assignment: Task 2 exports the predicate and Epic 4 (FR-13, condition 4) wires the `ImproperlyConfigured`. Shipping the fetch before the guard is the ordering the epics chose, not a defect this story introduced.
- **`reset()` is test-only machinery in `src/`.** Spec-mandated verbatim by Task 1, and the integration suite's cache leakage is the failure it prevents.
- **Five new environment variables ship undocumented.** True, and true of `COMPONENT_OIDC_ISSUER` and every other `COMPONENT_*` variable Stories 2.2 and 2.6 added — the repository has no `.env.example` and no operator-facing variable reference at all. That is a project-level gap for the documentation work to close once, not this story's to solve five variables at a time.
- **The 403→401 flip reaches every DRF route, including the session CSRF-failure path.** Real and intended: the spine's "authentication failure is 401" is the rule, `authenticate_header` is what makes it true, and the change is pinned twice with `WWW-Authenticate` assertions. Recorded as a residual risk rather than dropped.
- **Defaults are duplicated between `base.py` and the modules' `getattr` fallbacks.** The fallbacks are what let the unit suites construct a store without a settings fixture; the values are asserted against `base.py` in `test_settings.py`, so drift fails a test.
- **A lowercase `bearer` scheme is never tested.** The comparison is already case-insensitive per RFC 7235; the gap is one missing assertion over correct behaviour, not a defect.
- Also rejected: the integration fixture's `KEY_STORE._fetch` monkeypatch (the module-level singleton has no other supported seam, and the `noqa` is honest); duplicate integration setups and the oracle test comparing two same-path refusals (real test-quality nits, no behaviour behind them); tokens without `kid` being refused (argued and correct, and the matching key-side drop is the same rule); duplicate `kid` last-wins; log volume from the rate-limited event (one line per refused lookup, which is the operator's only signal that a spray is in progress); a `DatabaseError` from the mapper (Story 2.5 already owns the epoch-race handling); and `resolve_user`'s refusal-count wording.

## Auto Run Result

Status: done

### What was implemented

Bearer JWTs are now verified for real. `OIDCBearerAuthentication` reads the `Authorization: Bearer` credential, resolves its `kid` against a component-owned JWKS key store, verifies signature, `iss`, `aud` and `exp` against an explicit algorithm allowlist, and hands the verified claims to the mapper — `resolve_user` then `sync_once_per_epoch`, and nothing else. Every refusal is a 401 with a `WWW-Authenticate: Bearer` challenge and one structured warning event carrying the reason and the `kid`, never the token.

The key store is this story's substance rather than a wrapper around a library that already does it. Keys are cached by `kid` in process memory, fetched lazily on the first Bearer request that needs one and never at import or boot, refetched exactly once when an uncached `kid` arrives, and rate-limited so an unauthenticated caller spraying `kid` values cannot drive one outbound fetch per request. The TTL is a backstop for key removal only. A failed fetch leaves good keys in place; a successful one replaces them wholesale.

The third strand closes a decision Story 2.4 deferred and Story 2.6 shipped without: a deactivated user is refused inside `resolve_user`, once, and all three callers inherit it — 401 on the Bearer path, 403 on the interactive one, where allauth's accidental gate is now a pinned rule.

### Files changed

| Path | What changed |
|---|---|
| `src/config/authorization/jwks.py` | NEW. `JWKSKeyStore` (lazy, `kid`-keyed, TTL, three-state rate-limited refetch, lock, `reset`), `KEY_STORE`, `fetch_jwks_document` (no redirects, bounded body), `jwks_url_derives_from_issuer` and the URL helpers. |
| `src/config/authorization/authentication.py` | NEW. `OIDCBearerAuthentication` and the `OIDCBearerScheme` OpenAPI extension. Module docstring carries R-2 and the `authenticate_header` warning. |
| `src/config/authorization/exceptions.py` | Adds `JWKSKeyUnavailable` with its own `reason`; `ClaimsRejected` untouched. |
| `src/config/authorization/mapper.py` | `resolve_user` refuses a deactivated row with its own `ClaimsRejected` reason; docstring restated. Nothing else. |
| `src/config/settings/base.py` | `OIDC_ISSUER`/`OIDC_CLIENT_ID` hoisted to one read each; adds the JWKS and Bearer settings with clamped windows; Bearer class first in `DEFAULT_AUTHENTICATION_CLASSES`, `TokenAuthentication` left for Story 2.8. |
| `tests/jwt_keys.py` | NEW. In-test RSA and EC key generation, JWKS document building, and the fetch/clock seams both suites share. No committed key material. |
| `tests/unit/authorization/test_jwks.py` | NEW. The AC #5 cache/refetch/rate-limit/TTL suite, rotation, the no-fetch-at-import probes, the trust-anchor table, and the real fetch with `requests.get` replaced. |
| `tests/unit/authorization/test_authentication.py` | NEW. The header, `kid`, algorithm and audience shape guards, without a database. |
| `tests/integration/authorization/test_bearer_authentication.py` | NEW. The real DRF request cycle: the valid token, AC #1's four separate 401s, the allowlist, the missing-`jti` 401, AC #7's deactivated-user 401, AC #3's first-request fetch, and the fall-through cases. |
| `tests/unit/authorization/test_mapper_resolve.py`, `tests/integration/authorization/test_mapper_resolve.py`, `tests/integration/authorization/test_adapters.py` | AC #7 at all three surfaces, each with its control. |
| `tests/unit/test_settings.py` | The Bearer wiring, the declared defaults, the single issuer variable, and the clamped windows. |
| `tests/integration/users/test_api_openapi.py` | The anonymous refusal is now 401 with a `Bearer` challenge; the published contract carries `bearerAuth`. |

### Review findings

Three reviewers ran in parallel over the full diff. 9 patches applied (1 high, 5 medium, 3 low), 5 items deferred to the ledger, 16 rejected. No intent gap and no spec-level defect: every finding was a localized gap in code the spec already prescribed correctly, so no loopback was triggered.

### Verification

- `pixi run ci` — **exit 0**. 684 passed, coverage **95.78%** against a 90% floor; `jwks.py` and `authentication.py` both 100%. Run independently after patching, not only reported by the implementation agent.
- PostgreSQL 17 run performed during implementation (`pgvector/pgvector:0.8.1-pg17`), 643 passed at that point, with `test_postgres_schema.py` confirming the run was genuinely PG rather than a silent sqlite fallback. This story adds no migration.
- The four load-bearing review claims were reproduced directly against the installed PyJWT 2.13 and drf-spectacular before being accepted: the `TypeError` escape, the `kid`-less JWK Set parsing cleanly, `urlsplit(...).port` raising, and `securitySchemes` omitting the Bearer scheme.
- Each of the nine patches was verified by reverting the source change and confirming the named test fails.
- No test in the repository opens a socket; the fetch seam is a constructor argument and the four cases exercising the real fetch replace `requests.get`.

### Residual risks

- **SC-6 is not closed and cannot be closed here.** Every case passes against a locally generated keypair and a stubbed JWKS document. A real IdP identity through both flows is an external exit criterion owned by the platform group after Epic 2.
- **R-2 stands unchanged.** Bearer revocation latency is the token's lifetime; nothing here shortens it and nothing should. Recorded in the authentication module's docstring.
- **The JWKS trust anchor is checked syntactically or not at all.** The predicate ships; the startup refusal that consumes it is Epic 4's. Until then a `COMPONENT_OIDC_JWKS_URL` naming a host the issuer does not control will be fetched from and trusted. "Derived from" is not "confirmed against" — confirming against discovery would need the boot-time fetch FR-23 forbids.
- **Anonymous DRF requests now answer 401 rather than 403 across every route**, including the session CSRF-failure path. This is the spine's rule taking effect rather than a regression, but it is an observable API change for any existing client that branched on 403.
- The five ledger entries above, of which the ID-token-as-access-token question is the one worth a decision before Epic 3 Story 3.5 mints tokens against this same class.

### Follow-up review

Recommended: **true**. The pass applied nine patches, one high-severity, across exception handling, cache invalidation, redirect and body policy, a new OpenAPI extension and four new settings — security-relevant surface area and enough breadth that an independent look at the patched state is worth its cost.
