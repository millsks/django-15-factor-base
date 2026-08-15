# Review — Technology Verification Lens

**Target:** `ARCHITECTURE-SPINE.md` (architecture-django-15-factor-base-2026-08-15)
**Lens:** Was every committed decision web-researched or reality-checked, or asserted from training data?
**Date:** 2026-08-15
**Method:** conda-forge API (`api.anaconda.org`), PyPI JSON API, upstream source at HEAD and at release tags, current vendor documentation, and direct reads of `pixi.toml`, `pixi.lock`, `pyproject.toml`, `src/`, `.github/workflows/`.

---

## Verdict

The spine is **substantially better researched than most**. Every package it names exists on conda-forge, and several of its sharper claims (gunicorn has no win-64 build; `pixi run ci` has never run in CI; `build` is on a fortnightly cron; Django 6.0 rather than 6.1) turn out to be exactly right and non-obvious. The load-bearing pixi capability — per-task `env` — is real and behaves as AD-13 requires.

But three technology decisions are stated as settled when the live evidence says otherwise, one dependency is materially under-specified, and a handful of Stack-table facts contradict the repository's own lockfile. The pattern in the misses is consistent: **the spine verified that a package exists, not that the current release of it fits the stated use.**

---

## Findings

Severity: **HIGH** = wrong or will break; **MEDIUM** = unverified, materially risky, or contradicts the repo; **LOW** = imprecision, or a verified-good item recorded for the file.

---

### H-1 (HIGH) — `django-storages 1.14` has no released Django 6.0 or Python 3.14 support

**Claim:** Stack table, row `django-storages / boto3 | 1.14 / 1.43`. Also the closing sentence: "PyJWT, cryptography, django-storages and boto3 are new to this repository and were confirmed present on conda-forge on 2026-08-15."

**What I verified:**

| Source | Result |
| --- | --- |
| conda-forge `/package/conda-forge/django-storages` | latest = **1.14.6**, noarch |
| PyPI `django-storages` | latest = **1.14.6**, uploaded **2025-04-02** (16 months old) |
| PyPI classifiers for 1.14.6 | `Framework :: Django :: 3.2, 4.1, 4.2, 5.0, 5.1` — **no 5.2, no 6.0**. `Python :: 3.10, 3.11, 3.12` — **no 3.13, no 3.14** |
| GitHub tags | latest tag is `1.14.6`; nothing newer |
| GitHub `master` `pyproject.toml` | declares `Framework :: Django :: 6.0` and `Python :: 3.14`, added by commit `#1545` on **2026-08-02** — **unreleased** |
| GitHub commit log | `Add support for Django 5.2 (#1520)` landed 2025-06-17 — also after 1.14.6, also unreleased |

**The truth:** the released django-storages that the `storage` feature would install predates Django 5.2 support, let alone Django 6.0, and predates Python 3.13. Django 6.0.8 is what this project locks. The fix exists upstream but has not shipped, and conda-forge cannot ship what upstream has not tagged. "Confirmed present on conda-forge" is true and beside the point — presence was checked, fitness was not.

**Consequence:** the `storage` feature is one of four selectable features and therefore appears in six of the twelve gated combinations. If 1.14.6 breaks on Django 6.0, half the matrix fails and there is no newer conda-forge build to reach for.

**What the spine should do:** either (a) empirically verify `django-storages 1.14.6` against Django 6.0.8 / Python 3.14 before committing the row, (b) record the `storage` feature as blocked on a django-storages release and say so in Deferred, or (c) declare it the project's first supply-chain exception with an exit condition, the way `pixi.toml` already does for `django-celery-beat`.

---

### H-2 (HIGH) — the conda-forge `django-allauth` package does not carry the `socialaccount` dependency set

**Claim:** Stack table, row `django-allauth (incl. socialaccount.providers.openid_connect) | 65.19`. The parenthetical asserts the OIDC provider is covered by that one package.

**What I verified:**

- conda-forge `django-allauth 65.19.1` (`pyhd8ed1ab_0`) declares exactly: `['asgiref >=3.8.1', 'django >=4.2', 'python >=3.10']`. Nothing else.
- Upstream PyPI `requires_dist` for 65.19.1 puts the socialaccount dependencies in an **extra**, not in the base package:
  `'oauthlib<4,>=3.3.0; extra == "socialaccount"'`, `'requests<3,>=2.0.0; extra == "socialaccount"'`, `'pyjwt[crypto]<3,>=2.0; extra == "socialaccount"'`.
  allauth's own quickstart prescribes `pip install "django-allauth[socialaccount]"`.
- `allauth/socialaccount/providers/openid_connect/provider.py` imports `requests` at module top; `views.py` uses `get_adapter().get_requests_session()` for discovery, userinfo and JWKS.
- ID-token verification goes through `allauth/socialaccount/internal/jwtkit.py`, which uses `jwt.algorithms` / `algorithm.from_jwk` and `cryptography` (lazily imported since 65.19.0, so it costs nothing at boot but is still required at verification time).
- `requests` is present in `pixi.lock` at 2.34.2 **only transitively** — `pixi.toml` declares no `requests`. It is currently supplied by `opentelemetry-exporter-otlp-proto-http`.
- `pyjwt` and `cryptography` are **absent from `pixi.lock` entirely** (verified by parsing the lock).

**The truth:** the conda-forge recipe encodes no extras, so nothing in the solver guarantees the socialaccount surface is installable. The spine correctly adds PyJWT and cryptography — but frames them purely as AD-23 JWKS machinery, which understates why they are mandatory: without them `allauth.socialaccount` cannot verify an ID token at all. And `requests` — a hard import of the OIDC provider module — is not declared anywhere; today it survives on an OpenTelemetry transitive edge, so dropping or changing the OTLP HTTP exporter would break authentication with an `ImportError` at provider import.

**What the spine should do:** declare `requests`, `pyjwt` and `cryptography` explicitly in `[dependencies]` with the reasoning beside them (the Conventions row on Rationale already requires this), and record that the conda-forge allauth recipe omits upstream's extras — a genuine supply-chain footgun for a conda-forge-only project.

**Related, low, worth noting:** allauth's own Requirements doc page is stale — it still names `requests-oauthlib`, which 65.19.1 neither declares nor uses anywhere. Do not follow that page.

---

### H-3 (HIGH) — AD-23's "rate-limited refetch" does not exist in PyJWT, and its cache claims are wrong in the configuration it implies

**Claim (AD-23):** "Keys are cached by `kid`. A token presenting an uncached `kid` triggers one rate-limited refetch, so rotation survives without a restart. TTL is a backstop for key removal only."

**What I verified** — read `jwt/jwks_client.py` at PyJWT master directly:

```python
def __init__(self, uri, cache_keys: bool = False, max_cached_keys: int = 16,
             cache_jwk_set: bool = True, lifespan: float = 300, ...)
```

```python
def get_signing_key(self, kid: str) -> PyJWK:
    signing_keys = self.get_signing_keys()
    signing_key = self.match_kid(signing_keys, kid)
    if not signing_key:
        # If no matching signing key from the jwk set, refresh the jwk set and try again.
        signing_keys = self.get_signing_keys(refresh=True)
        signing_key = self.match_kid(signing_keys, kid)
        if not signing_key:
            raise PyJWKClientError(f'Unable to find a signing key that matches: "{kid}"')
    return signing_key
```

Three corrections, in order of severity:

1. **There is no rate limiting.** The refetch is unconditional and unthrottled. A caller sending tokens bearing random `kid` values produces **one outbound JWKS fetch per request**, with no backoff and no circuit breaker. AD-23 states rate limiting as a property of the mechanism; it is a property the project must build and does not get from PyJWT. Given AD-23 also binds FR-13 and the Bearer path is unauthenticated at that point, this is an unauthenticated amplification vector against the IdP's JWKS endpoint.

2. **"Keys are cached by `kid`" is off by default.** PyJWT's per-`kid` LRU is Tier 2 and `cache_keys=False` is the default. The default cache is Tier 1 — the whole JWK Set response, `cache_jwk_set=True`, `lifespan=300`.

3. **"TTL is a backstop for key removal only" is false if you enable the kid cache.** The Tier-2 LRU has **no time-based expiration** — entries evict only when the cache exceeds `max_cached_keys` (default 16). `lifespan` does not apply to it. So a key rotated *in place* (same `kid`, new material) is served stale indefinitely, which is exactly the case a TTL is supposed to backstop.

**Two PyJWT behaviours that support the design and are worth citing in the spine:** the constructor now rejects non-`http(s)` URIs to block `jku`-header-driven local file reads, and `fetch_data` writes the cache only on success, so a transient IdP outage no longer wipes a good cached JWKS.

**Also verified for AD-23:** PyJWT needs no extra library for this — networking is stdlib `urllib.request`. `cryptography` is required for RS256/ES256 (the `crypto` extra, `cryptography>=3.4.0`), which the spine correctly lists.

---

### M-1 (MEDIUM) — the spine pins `uvicorn-worker`, which gunicorn 26 has made unnecessary

**Claim:** Stack table, row `gunicorn + uvicorn-worker | 26.0 + 0.4`.

**What I verified:**

- `uvicorn_worker.UvicornWorker` **is** the correct current path — confirmed from the uvicorn-worker README (`gunicorn example:app -w 4 -k uvicorn_worker.UvicornWorker`) and the package's `__all__`. `uvicorn.workers.UvicornWorker` has been deprecated since uvicorn 0.30.0 (2024-05-28) and still emits a `DeprecationWarning`. **The spine's path is right.** (Neither path appears anywhere in the repo today — the `serve` task runs bare uvicorn — so there is no contradiction to fix, only a forward decision.)
- **But gunicorn ships a native ASGI worker.** I read `gunicorn/workers/__init__.py` at **tag 26.0.0**, not just master:
  ```python
  SUPPORTED_WORKERS = { ..., "asgi": "gunicorn.workers.gasgi.ASGIWorker" }
  ```
  `gunicorn/workers/gasgi.py` is present at that tag (HTTP 200). Gunicorn's own docs: "Gunicorn includes a native ASGI worker that enables running async Python web frameworks … **without external dependencies like Uvicorn**."
- Meanwhile `uvicorn-worker 0.4.0` was released **2025-09-20** — eleven months before uvicorn 0.52.3 (2026-08-13) and eight before gunicorn 26.0.0 (2026-05-05). It declares `uvicorn>=0.36.0` with **no upper bound**, its PyPI classifiers stop at **Python 3.13** (no 3.14), and `uvicorn_worker/_workers.py` imports the **private** `uvicorn._compat.asyncio_run`. That symbol still exists on uvicorn master, so it works today — but it is a private-API dependency in an unmaintained-looking package, pinned against a Python version it does not claim.

**The truth:** the `gunicorn + uvicorn-worker` pairing is an inherited cookiecutter-Django default that the spine carried forward without checking whether gunicorn 26 still needs it. `--worker-class asgi` removes a package, removes a private-API coupling, and removes a py3.14-unclassified dependency. If the pairing is kept deliberately (e.g. for uvicorn's httptools/uvloop path), the spine should say so — that is a decision, and right now it reads as an assumption.

---

### M-2 (MEDIUM) — the Stack table contradicts the repository's own `pixi.lock` in two places

Both verified by parsing `pixi.lock` directly:

| Spine says | `pixi.lock` says | Note |
| --- | --- | --- |
| `djangorestframework / drf-spectacular \| 3.17 / 0.30` | **djangorestframework 3.18.0**, drf-spectacular 0.30.0 | conda-forge latest is also 3.18.0; `pixi.toml` allows `>=3.17,<4`, so 3.18 is what resolves. The `3.17` is a transcription of the constraint floor, not the locked version. |
| "PyJWT, cryptography, django-storages and **boto3** are new to this repository" | **boto3 1.43.65 is already in the lock** | Pulled transitively. Only `pyjwt`, `cryptography` and `django-storages` are genuinely absent — I confirmed all three are missing from the lock. |

Neither is dangerous, but the Stack table is the artifact downstream work will treat as the pin list, and it is describing a repository state that is one grep away from being checked.

---

### M-3 (MEDIUM) — "twelve genuinely lean, pre-locked environments" will not be version-uniform, and the spine does not say whether it should be

**Claim (AD-3):** "The four selectable features are declared as pixi features with an `[environments]` matrix, so one `pixi.lock` yields twelve genuinely lean, pre-locked environments."

**The mechanism is real.** Confirmed from pixi's manifest reference: `[environments]` composes features, `features` unions dependencies/tasks/activation, `platforms` intersects, and subset combination is the documented pattern. No documented cap on environment count exists. Lockfile dedupe is explicit: "a package may now include an additional `environments` field … To avoid duplication the packages `environments` field may contain multiple environments so the lock file is of minimal size."

**The unexamined consequence:** conda-forge `django-celery-beat 2.9.0` declares `django >=2.2,**<6.1**` (verified via the files API — the same cap `pixi.toml` already warns about). The workspace allows `django >=6.0,<7`, and **Django 6.1 is on conda-forge**. So without a shared `solve-group`, a combination that does *not* select the `celery` feature is free to resolve **Django 6.1**, while every celery combination is pinned to **6.0**. Twelve gates would then be running against two different Djangos, and a Django-6.1 regression would surface in six combinations and not the other six — or worse, the reverse.

A shared `solve-group` fixes uniformity without sacrificing leanness (pixi: "the different environments contain different subsets of the solve-group's dependencies set"). The spine simply does not say which it wants. Given AD-3's whole purpose is that "a combination [passes] its gate in an environment [not] fat enough to hide an import it should not have", the version-uniformity question is squarely in scope and currently unanswered.

---

### M-4 (MEDIUM) — the cost of a twelve-environment lock is real, undocumented, and pixi explicitly declines to generate one for you

**What I verified:**

- pixi's multi-environment docs state as a design principle: "**No Automatic Combinatorial**: To ensure the dependency resolution process remains manageable, the solution should avoid a combinatorial explosion of dependency sets. By making the environments user defined and not automatically inferred by testing a matrix of the features." The hand-written twelve-cell matrix is precisely the shape pixi refuses to infer, because of resolution cost.
- **`pixi lock` cannot be scoped to one environment.** Its documented options are `--json`, `--check`, `--dry-run` only. Open request: prefix-dev/pixi#2846, which also records the practical pain — any change to any environment rewrites the whole `pixi.lock`, invalidating Docker-layer caches for every environment. (`pixi install`, by contrast, *is* scoped: default environment only, `--all` for everything.)
- Solves are per-solve-unit and parallelized (`--concurrent-solves`, default = CPU count); platforms multiply solve count (confirmed in pixi's pytorch doc: same environment, two platforms, "solved separately").
- **No documented size or time limits exist** — I searched for them and found none. So this is a cost, not a blocker.

**Concrete scale, measured on this repo:** 2 environments × 3 platforms → 6,372-line / 272 KB `pixi.lock`, of which ~1,135 lines are per-environment references and the rest is the deduplicated `packages:` block. Twelve environments would put the lock in the ~500 KB–1 MB range. pixi's own repository (≈8 environments × 5 platforms) has a 480 KB lock. Manageable — but AD-3 asserts the approach without pricing it, and the every-change-relocks-everything property is worth knowing before the materializer is built on top of it.

---

### M-5 (MEDIUM) — AD-15 says the repository ships a Dockerfile; it does not

**Claim (AD-15), present tense:** "This repository ships a Dockerfile as `machinery` so the harness can verify those properties."

**Verified absent:** no `Dockerfile` at the repository root or anywhere in the tree.

Also absent, though these are correctly framed as forward-looking elsewhere and only the Dockerfile sentence is in the indicative: `accelerator.toml`, `tools/`, `src/django_apps/`, `src/config/startup/`, `src/config/authorization/`. Two spine statements that *are* accurate about the present: `src/config/observability/` exists, and `src/config/websocket.py` plus the scope-dispatching wrapper in `asgi.py` exist and are exactly as AD-16 describes them (so "are deleted" is a correct instruction, not a false claim).

---

### L-1 (LOW) — AD-20's requirement is correct, its failure mode is correctly described, and there is a better mechanism available

I initially suspected coverage.py had fixed this upstream. It has not. Verified:

- coverage.py `[run] core` docs: "`sysmon`: … Only available in Python 3.12+, and **the default in Python 3.14+**. **The sysmon core does not yet support plugins**, dynamic contexts, or some concurrency libraries." `ctrace` "was the default until Python 3.13."
- coverage 7.9.1 CHANGES: "On Python 3.14+, the 'sysmon' core is now the default … **Plugins and dynamic contexts are still not supported with it.**"
- coverage 7.11.1 added an automatic fallback to `ctrace` when settings conflict with sysmon — but `coverage/core.py`'s `reason_no_sysmon` list covers branch coverage, dynamic contexts and greenlet/eventlet/gevent concurrency. **Plugins are not in that list**; instead `supports_plugins = False` is set and `control.py` warns `"Plugin file tracers (…) aren't supported with …"` and then sets `plugin._coverage_enabled = False`.
- Upstream tracking issue coveragepy#1790 ("Support coverage plugins with sys.monitoring") is **still open**. django_coverage_plugin#102 has a 2025-10-16 report of exactly this on Python 3.14.
- `django_coverage_plugin`'s own `tox.ini` still forces it: `py3{12,13,14,15}: COVERAGE_CORE=ctrace`.

**So AD-20 is right and its assertion test is justified.** Two refinements:

1. **The repo's own comment is wrong about the version.** `pixi.toml` says "On Python 3.12+ coverage defaults to the `sysmon` core." It does not — sysmon became the default in **3.14+**; ctrace was the default through 3.13. The conclusion is unaffected (this project is 3.14-only) but the reasoning-beside-configuration convention means the wrong reason will be read as fact.
2. **There is a mechanism that travels by construction.** coverage **7.9.0** (2025-06-11) added a `[run] core` *config* setting; the pinned range is `coverage >=7.15,<8`, so it is available. Putting `core = "ctrace"` in `[tool.coverage.run]` in `pyproject.toml` makes the requirement part of the materialized source tree, rather than something AD-20 has to make "travel with every combination" as an environment variable plus a test that asserts it is in force. This also resolves a live tension: `COVERAGE_CORE` currently lives in `[activation.env]` — the exact table AD-13 forbids for `COMPONENT_RUNTIME` on the grounds that activation env reaches production.

**Maintenance status, confirmed good:** `django_coverage_plugin` 3.2.2 released 2026-04-04; repo moved to the `coveragepy` GitHub org; commits current (2026-08-09: Django 6.1 and Python 3.15 test matrix). Classifiers cover Python 3.14 and Django 6.0. Django 6.1 support is on master but unreleased — irrelevant while `django-celery-beat` caps Django below 6.1.

---

### L-2 (LOW) — AD-13's per-task `env` is real; one behaviour should be recorded in the spine

**Confirmed exactly as AD-13 needs it:**

- Per-task `env` is documented in the manifest reference: `run = { cmd="python run.py $ARGUMENT", env={ ARGUMENT="value" }}`, and in table form `[tasks.hello] env = { HELLO_WORLD = "..." }`. Added in **pixi 0.20.0 (2024-04-19)** — long-stable, no version risk.
- Priority is documented explicitly: **`task.env` > `activation.env` > `activation.scripts` > dependency activation scripts > outside environment variables.**
- Scope is documented: task env is "interpreted by `deno_task_shell` **when the task runs**", whereas activation "operations will be run before the `pixi run` **and `pixi shell`** commands" and `[activation]` belongs to the default feature, so it reaches every environment that does not set `no-default-feature`.

AD-13's premise — that `[activation.env]` leaks where task env does not — **holds precisely**, and `task.env` also wins on conflict. `default-environment` (pixi 0.64.0) and `depends-on` are both confirmed; `requires-pixi = ">=0.70.2"` is a real released version (2026-06-08) and comfortably above the 0.64.0 floor `default-environment` needs. Latest pixi is 0.76.2.

**The behaviour to record:** in current pixi, an outside shell variable **no longer overrides** `task.env`. So `COMPONENT_RUNTIME=deployed pixi run test` will *not* do what a reader expects — the task's `local` wins. Making a task value user-overridable requires expressing it as a task `arg`, not an env var. Given AD-13 already names one residual risk explicitly, this second one deserves the same treatment.

**Reality check:** `pixi.toml` today uses **zero** per-task `env` tables. The mechanism the refusal contract rests on is unexercised in this repository — worth a first, trivial use before Phase 1 builds on it.

---

### L-3 (LOW) — allauth settings-driven OIDC config is confirmed, with three caveats worth carrying

**Confirmed:** `SOCIALACCOUNT_PROVIDERS["openid_connect"]["APPS"] = [...]` is the documented, authoritative, DB-free path. allauth's docs: "You provide the app configuration either in your project `settings.py`, or, by means of setting up `SocialApp` instances via the Django admin … The examples presented in this documentation are all settings based." Source confirms it — `adapter._build_apps_from_settings` builds **unsaved** `SocialApp` objects and its docstring says "Performs no database I/O." Required keys for openid_connect: `provider_id`, `name`, `client_id`, `secret`, `settings["server_url"]` (a hard `KeyError` if absent); optional `fetch_userinfo`, `oauth_pkce_enabled`, `token_auth_method`, `uid_field` (default `"sub"`).

Caveats the spine should absorb, since AD-11 says "`SocialAccount` is bookkeeping, not authority":

1. `list_apps()` still queries `socialaccount_socialapp` via `SocialApp.objects.on_site(request)` on every lookup — no row is needed, but the table must exist, so the migration is not optional.
2. Configuring the same provider **both** in settings and in the DB raises `MultipleObjectsReturned`. A component that ships settings-based config and inherits a stray admin-created row fails at login, not at startup — a candidate for a stage-2 refusal.
3. `django.contrib.sites` is **optional** for the settings path (`SITES_ENABLED = apps.is_installed("django.contrib.sites")`; settings-based apps carry no sites at all). This repo currently sets `SITE_ID = 1`. Not a contradiction, but a 15-factor component could drop it.

**Adapter hooks confirmed present in 65.19.1:** `SOCIALACCOUNT_ADAPTER`, `DefaultSocialAccountAdapter.pre_social_login`, `populate_user`. `pre_social_login` (+ `sociallogin.connect`) is the correct hook for AD-11's resolve-by-`idp_subject`; `populate_user` only decorates a new instance. Also relevant: `SOCIALACCOUNT_EMAIL_AUTHENTICATION` defaults to `False`, which AD-11's identity model wants — leave it off.

---

### L-4 (LOW) — AD-23 scoping vs. how allauth actually handles the ID token

Verified from `openid_connect/views.py` at 65.19.1:

```python
verify_signature = not self.did_fetch_access_token
return jwtkit.verify_and_decode(
    credential=id_token, keys_url=self.openid_config["jwks_uri"],
    issuer=self.openid_config["issuer"], audience=app.client_id,
    lookup_kid=jwtkit.lookup_kid_jwk, verify_signature=verify_signature)
```

In the browser code flow `did_fetch_access_token` is `True`, so **allauth deliberately skips JWKS signature verification** (OIDC Core §3.1.3.7 clause 6 — the token arrived over a TLS-protected back channel). `iss`/`aud`/`exp` are still enforced. Full JWKS-by-`kid` verification happens only on the token-authentication path (`OpenIDConnectProvider.verify_token` → `jwtkit.lookup_kid_jwk`).

AD-23's scope ("fetched lazily on the first Bearer request that needs it") is therefore **correct**. Two things follow that the spine does not say:

1. allauth already ships a JWKS-by-`kid` implementation. AD-23 is *choosing* to reimplement it on PyJWT rather than being forced to. That is defensible — but it should be stated as a choice, with the H-3 rate-limiting gap owned by whoever writes it.
2. "The trust anchor is derived from the configured OIDC issuer; **a JWKS location not derived from it is refused at startup**" cannot be checked against the discovery document at startup without the boot-time network fetch the same rule forbids. allauth reads `jwks_uri` from the discovery document at request time. The startup check can only be a string-derivation rule over the configured issuer — worth saying so, or the requirement reads as stronger than it can be.

---

### L-5 (LOW) — four booleans is sixteen, not twelve

AD-3 and AD-19 commit to **twelve** combinations from **four** selectable features. 2⁴ = 16. AD-1 mentions "constraints and presets" in the carrier, which presumably prune 16 → 12, but the spine never states the constraint that does it, so "twelve" reads as asserted. (AD-19's Deferred entry noting FR-35's switch point at "roughly thirty-two combinations" — 2⁵ — adds to the ambiguity.) Not a technology finding, but the number is load-bearing three ways: it sets the pixi environment count (M-3, M-4), the CI cost (AD-18/19), and the lock size.

---

### L-6 (LOW) — everything else in the Stack table checks out

Verified present on conda-forge at the stated version, with `py314` builds where the package is compiled, and cross-checked against `pixi.lock`:

| Name | conda-forge | In lock | Note |
| --- | --- | --- | --- |
| Python 3.14 | ✓ | 3.14.6 | |
| Django 6.0 | ✓ | 6.0.8 | **6.1 exists** but `django-celery-beat 2.9.0` declares `django <6.1`. The spine's `6.0` is correct **and forced** — a good catch, verified. |
| django-allauth 65.19 | 65.19.1 | 65.19.0 | Classified and CI-tested for Django 6.0, Django 6.1 and Python 3.14 (`noxfile.py` matrix). 65.19.0 "Officially support Django 6.1." |
| drf-spectacular 0.30 | 0.30.0 | 0.30.0 | Classified for Django 6.0, Python 3.14 |
| PyJWT 2.13 | 2.13.0 (noarch) | absent (new) | Python 3.14 classifier |
| cryptography 50.0 | 50.0.0 | absent (new) | py314 builds on linux-64, osx-arm64, win-64 |
| Celery 5.6 | 5.6.3 | 5.6.3 | `billiard 4.2.4` has py314 builds and is already locked at py314 on both platforms |
| django-celery-beat 2.9 | 2.9.0 | 2.9.0 | `pyhcf101f3_2` no longer lists `pytest` under run deps — the cost recorded in `pixi.toml` may already be resolved |
| django-redis 7.0 / redis-py 8.1 | 7.0.0 / 8.1.0 | ✓ / ✓ | django-redis 7.0.0 declares `Django<7.0,>=5.2`, `redis>=4.0.2`, Python 3.14 — the pairing is genuinely supported |
| psycopg 3.3 | 3.3.4 | 3.3.4 | Python 3.14 |
| structlog 26.1 / django-structlog 10.1 | 26.1.0 / 10.1.0 | ✓ / ✓ | |
| OpenTelemetry 1.44 | 1.44.0 | 1.44.0 | |
| gunicorn 26.0 | 26.0.0 | 26.0.0 | Real; released 2026-05-05. py314 builds exist for linux-64 and osx-arm64. |
| uvicorn-worker 0.4 | 0.4.0 (noarch) | 0.4.0 | See M-1 |
| whitenoise 6.12 | 6.12.0 | 6.12.0 | Classified for Django 6.0, Python 3.14 |
| pixi ≥ 0.70.2 | — | installed 0.70.2 | Real release (2026-06-08); latest is 0.76.2 |

---

### L-7 (LOW) — AD-18's non-obvious premises are all true

Every one of these was checkable and every one holds:

- **"the twelve-combination harness is Linux-only, `gunicorn` having no win-64 build."** Verified via the conda-forge files API across *all* gunicorn versions: subdirs are `linux-64`, `linux-aarch64`, `linux-ppc64le`, `osx-64`, `osx-arm64` — **there has never been a win-64 build**. Upstream classifiers list only `POSIX` and `MacOS X`; "Add Windows support" (benoitc/gunicorn#524) has been open since 2013 on the `fcntl` dependency. `pixi.toml` already scopes gunicorn and uvicorn-worker to the two POSIX targets, so the spine matches the repo.
- **"A single workflow invokes `pixi run ci`, which has never run in CI."** True — `ci.yml` runs `pixi run test`, `lint`, `typecheck` as separate steps; no workflow invokes `pixi run ci`.
- **"`build` off its fortnightly cron."** True — `pixi run build` lives in `release.yml`, whose trigger is `cron: "0 0 7,21 * *"`.
- **"Template coverage moves out of the SonarCloud workflow."** True — `sonarqube.yml` is what runs `pixi run test-cov`.
- **"the three-OS matrix stays on the reference application."** True — `ci.yml` already carries `os: [ubuntu-latest, windows-latest, macos-latest]`.

---

## Summary table

| # | Severity | Finding |
| --- | --- | --- |
| H-1 | HIGH | `django-storages 1.14.6` (Apr 2025) declares no Django 6.0 and no Python 3.14; the fix is committed upstream but unreleased, and conda-forge has nothing newer |
| H-2 | HIGH | conda-forge `django-allauth` omits upstream's `socialaccount` extra — `requests`, `pyjwt`, `cryptography` are undeclared; `requests` survives only on a transitive OpenTelemetry edge |
| H-3 | HIGH | AD-23's "rate-limited refetch" does not exist in PyJWT; `cache_keys` is off by default; the per-`kid` LRU has no TTL, contradicting "TTL is a backstop" |
| M-1 | MEDIUM | gunicorn 26.0.0 ships a native `asgi` worker; `uvicorn-worker 0.4.0` is 11 months stale, has no py3.14 classifier, and imports a private uvicorn symbol |
| M-2 | MEDIUM | Stack table says DRF 3.17 (lock has 3.18.0) and calls boto3 "new" (already in the lock at 1.43.65) |
| M-3 | MEDIUM | Without a shared `solve-group`, non-celery combinations resolve Django 6.1 while celery ones are capped at 6.0 — twelve gates, two Djangos |
| M-4 | MEDIUM | `pixi lock` cannot be scoped; every change re-locks all twelve. pixi's docs explicitly decline to generate feature matrices, citing combinatorial cost |
| M-5 | MEDIUM | AD-15 states the repository ships a Dockerfile; it does not exist |
| L-1 | LOW | AD-20 is correct (sysmon still can't do plugins), but `pixi.toml`'s "3.12+" reason is wrong (3.14+), and `[run] core = "ctrace"` in `pyproject.toml` would travel by construction |
| L-2 | LOW | Per-task `env` confirmed real and correctly reasoned; outside env no longer overrides it; the repo uses it nowhere yet |
| L-3 | LOW | Settings-driven allauth `APPS` confirmed DB-free; three caveats (table still queried, settings+DB collision, sites optional) |
| L-4 | LOW | allauth skips JWKS verification in the code flow, so AD-23's scope is right — but the startup JWKS check can only be string derivation, not discovery |
| L-5 | LOW | "Twelve" from four booleans (2⁴ = 16) is stated without the pruning constraint that produces it |
| L-6 | LOW | All remaining Stack rows verified present, current, and py3.14-capable |
| L-7 | LOW | Every non-obvious AD-18 premise verified true, including gunicorn's total absence from win-64 |

---

## Sources

- conda-forge package and files API: `https://api.anaconda.org/package/conda-forge/<name>[/files]`
- PyPI JSON API: `https://pypi.org/pypi/<name>/json`
- pixi manifest reference: https://pixi.prefix.dev/latest/reference/pixi_manifest/ (note: `pixi.sh` now 301s to `pixi.prefix.dev`)
- pixi multi-environment: https://pixi.prefix.dev/latest/workspace/multi_environment/
- pixi environment-variable priority: https://pixi.prefix.dev/latest/reference/environment_variables/
- pixi scoped-lock request: https://github.com/prefix-dev/pixi/issues/2846
- coverage.py config (`[run] core`): https://coverage.readthedocs.io/en/latest/config.html
- coverage.py plugins-with-sysmon tracking issue: https://github.com/nedbat/coveragepy/issues/1790
- django_coverage_plugin (now under the `coveragepy` org): https://github.com/coveragepy/django_coverage_plugin — see `tox.ini` and issue #102
- PyJWT JWKS client source: https://github.com/jpadilla/pyjwt/blob/master/jwt/jwks_client.py
- uvicorn-worker: https://github.com/Kludex/uvicorn-worker
- gunicorn native ASGI worker at tag 26.0.0: `gunicorn/workers/__init__.py`, `gunicorn/workers/gasgi.py`
- gunicorn Windows support issue: https://github.com/benoitc/gunicorn/issues/524
- django-allauth provider configuration: https://docs.allauth.org/en/latest/socialaccount/provider_configuration.html
- django-allauth openid_connect: https://docs.allauth.org/en/latest/socialaccount/providers/openid_connect.html
- django-storages master `pyproject.toml` and commit #1545: https://github.com/jschneier/django-storages
