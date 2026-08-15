---
stepsCompleted: [1, 2, 3]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md
  - _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md
  - _bmad-output/specs/spec-django-15-factor-base/SPEC.md
  - _bmad-output/specs/spec-django-15-factor-base/capability-map.md
---

# django-15-factor-base - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for django-15-factor-base, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

Scope is phase 1: the reference application, the authentication rewire, the refusal contract, the local development contract, the feature model, the verification harness, the deployment interface, observability hardening, supply-chain policy, and the extension model. Phase 2 (FreeMarker template conversion) is out of scope.

Identifiers are used verbatim from their source documents: `FR-n` / `NFR-n` / `SC-n` / `CG-n` from the PRD, `AD-n` and `R-n` from the architecture spine, `CAP-n` from the spec kernel. Glossary terms from PRD §3 are used exactly and never paraphrased.

## Requirements Inventory

### Functional Requirements

**§4.1 The Immovable Core** — *Phase-1 must-have*

- **FR-1:** Every valid combination provides the immovable core, and no feature selection removes any part of it.
- **FR-2:** The immovable set is defined by capability, not by package — a materialized combination's dependency manifest carries exactly the instrumentation packages its capabilities require and no others.
- **FR-3:** The Django admin is orthogonal to the server-rendered UI feature; omitting the UI feature removes only the end-user surface.

**§4.2 Authentication and Authorization** — *Phase-1 must-have; none of it is implemented*

- **FR-4:** Interactive authentication against the IdP — Authorization Code with PKCE via `allauth.socialaccount.providers.openid_connect`, establishing a session and invoking the mapper.
- **FR-5:** Programmatic authentication against the IdP — a DRF `BaseAuthentication` subclass validating `Authorization: Bearer <JWT>` against JWKS, verifying signature, `iss`, `aud` and `exp`, with lazy retrieval and `kid`-keyed caching.
- **FR-6:** The static-token credential surface is removed entirely — no `TokenAuthentication`, no `rest_framework.authtoken`, no `obtain_auth_token` route.
- **FR-7:** The Django admin is forced through the IdP; `DJANGO_ADMIN_FORCE_ALLAUTH` defaults true.
- **FR-8:** One shared mapper at `src/config/authorization/` owns all authorization decisions, resolving users by one designated identity-key claim.
- **FR-9:** Authorization re-syncs on every authentication including revocation — adds asserted groups, removes unasserted ones, sets staff, emits a structured log line; resolve and re-sync run at different frequencies.
- **FR-10:** The claims contract is configuration — group-claim name and staff-conferring group read from the environment.
- **FR-11:** Superuser creation is retired as the deployed bootstrap path; staff and superuser are group-driven and the designated groups are provisioned by the component.

**§4.3 The Refusal Contract** — *Phase-1 must-have; one of nine conditions built*

- **FR-12:** The refusal contract is evaluated at two defined points — settings import (stage 1) and serving-process startup (stage 2) — independently of which settings module loaded, with locality read from the environment and failing closed.
- **FR-13:** Seven unconditional refusals: sqlite reached; a local credential path live in settings; a credential-minting route reachable; the local sign-in route reachable; `OTEL_SDK_DISABLED` true; the JWKS trust anchor not derived from the configured IdP; unapplied migrations on a serving process; the claims contract unconfigured. *(Counted as seven conditions across those states; the URL-resolved pair are stage 2.)*
- **FR-14:** Two conditional refusals scoped to their feature — in-process cache where Redis is selected, eager task execution where background task processing is selected.
- **FR-15:** The refusal inspects the resolved URL configuration, not settings alone.
- **FR-16:** Refusals are tested as refusals — each condition has a test that configures the forbidden state and asserts `ImproperlyConfigured`.
- **FR-17:** An allowlist test catches credential paths added later, over `AUTHENTICATION_BACKENDS`, the DRF default authentication classes, and the component's own authentication route prefixes.

**§4.4 The Local Development Contract** — *Phase-1 must-have*

- **FR-18:** A component runs locally with nothing installed — five substitutions: sqlite, in-process cache, eager tasks, filesystem-backed object storage, local personas.
- **FR-19:** Personas are seeded from declared claims by a development task that refuses to run in a deployed environment; local sign-in constructs synthetic claims and passes them to the mapper.
- **FR-20:** The local programmatic flow validates for real — a development task mints a JWT signed by a locally generated, gitignored keypair that the real Bearer authentication class verifies.
- **FR-21:** Observability is not substituted locally — same code, only the terminal export step absent; spans discarded at the processor.
- **FR-22:** The broker constraint is a statement about deployment only; all six combinations run locally with no broker.
- **FR-23:** Nothing on the local start path reaches the network at boot — OIDC discovery and JWKS retrieval are lazy.

**§4.5 The Feature Model and Clean Extraction** — *Phase-1 must-have*

- **FR-24:** Three selectable features declared in one carrier with a single declared location and format, which is the only place a feature's extent is defined.
- **FR-25:** Object storage attaches an S3-compatible backend configured from environment variables alone (`django-storages`, `boto3`); user media is out of scope.
- **FR-26:** The broker constraint is enforced at selection — six valid combinations, not eight.
- **FR-27:** Presets pre-select without constraining; every valid combination is reachable without a preset.
- **FR-28:** Excluded features leave nothing behind — no dependency, template, static asset, settings fragment, or test, and nothing present-but-skipped.
- **FR-29:** The orphan-detection property survives into the harness — template-inclusive coverage with `COVERAGE_CORE` pinned to the C trace core, plus carrier reconciliation for static assets and settings fragments.

**§4.6 The Verification Model** — *Phase-1 must-have*

- **FR-30:** The materializer produces any valid combination deterministically, self-contained and gateable, from single-authored declarations, excluding itself and the carrier from its output.
- **FR-31:** The materializer carries a fixture set covering every parameterized value; a parameter without a fixture fails materialization rather than defaulting.
- **FR-32:** Every valid combination passes the full gate against PostgreSQL — no partial pass; CI must declare a PostgreSQL service, which no workflow does today.
- **FR-33:** Every valid combination passes a local smoke check — boots, readiness 200, persona authenticates, with no external service running.
- **FR-34:** The materializer refuses invalid combinations, naming the broker constraint.
- **FR-35:** Any bound on verification coverage is reported explicitly, with the combinations not covered.
- **FR-36:** Materialized output carries the provenance stamp — accelerator version and order values, in a stable enumerable location.
- **FR-37:** The accelerator's own machinery does not reach a component — a per-path disposition rule defaulting to excluded, with parameterization, `.github/` and `docs/` splits, and `src/django_service/` explicitly not parameterized.

**§4.7 The Deployment Interface** — *Phase-1 must-have, except FR-44's scheduling half which is Next*

- **FR-38:** Configuration is exclusively environmental; no configuration file in the image.
- **FR-39:** The component runs as an arbitrary non-root user with a read-only root filesystem and no writable path beyond a temporary directory.
- **FR-40:** The process model is declared per combination — `web` always, `worker`/`beat` only where background task processing is selected, `beat` exactly one replica with a stop-before-start replacement strategy.
- **FR-41:** Migrations are a release-stage step, enforced by refusal; no entrypoint migrates.
- **FR-42:** Two asymmetric health endpoints — liveness touches nothing external, readiness checks the database, never re-checks migrations, and is non-200 until first successful contact.
- **FR-43:** Shutdown drains in a defined order — readiness flips before the drain begins.
- **FR-44:** Sessions are database-backed with the engine set explicitly in every combination; pruning is a scheduled admin process. *(Explicit engine: phase-1. Scheduling: Next.)*
- **FR-45:** Trace export is environmental and drops rather than retries, with the export path exercised end to end in the gate against a collector stub.

**§4.8 Observability** — *Phase-1 must-have; largely satisfied today*

- **FR-46:** Correlated structured logging — JSON to stdout carrying `request_id`, `trace_id`, `span_id`, propagating into task execution where selected.
- **FR-47:** ASGI request tracing — the ASGI instrumentor active in all six combinations.
- **FR-48:** Degradation is visible — swallowed cache failures emit correlated log events.

**§4.9 Supply Chain and Dependency Policy** — *Phase-1 must-have*

- **FR-49:** Single audited channel with recorded exceptions — zero exceptions; a test asserts no third-party package resolves from the package index; dependencies lock-pinned with no system packages.
- **FR-50:** Channel availability *and fitness against the pinned runtime* are checked before a feature is committed to.

**§4.10 The Extension Model** — *Phase-1 must-have; none of it exists*

- **FR-51:** The base package is a stable import surface with a declared guaranteed surface present in all six combinations; changes to it are breaking and versioned.
- **FR-52:** A component extends through a declared tenant space the accelerator neither supplies nor judges, never pruned and never reported as an orphan.
- **FR-53:** A reusable app graduates without changing its import path; adoption is explicit and nothing self-registers.
- **FR-54:** A reusable app adds configuration and never changes it — additive on a closed declared surface, appending to ordered configuration in adoption order, refused at startup when it names an unselected feature.
- **FR-55:** A contributed backing service inherits the local development contract — substitutions, refusals, migration steps and readiness all extend to it.
- **FR-56:** Base compatibility is declared and checked at adoption, from a declaration both residencies can read, failing the gate rather than production.

### NonFunctional Requirements

- **NFR-1:** Startup fails fast and cheaply — misconfiguration surfaces at boot as `ImproperlyConfigured`, never as scattered runtime errors; the checks make no network call and no query beyond migration state.
- **NFR-2:** Liveness touches nothing external — a system-wide invariant any future health work must preserve.
- **NFR-3:** Statelessness — nothing shared through local disk or process memory across replicas; sessions database-backed in every combination.
- **NFR-4:** Strict typing and lint are gate conditions, not advisories.
- **NFR-5:** Determinism — materialization and dependency resolution are reproducible; the same selections and lock file produce the same component.
- **NFR-6:** Telemetry overhead is measured, not assumed — measured once against the reference application, recorded with the observability documentation, re-measured only when the instrumentation set changes.
- **NFR-7:** Secrets never live in source; the development keypair is generated on demand into a gitignored path.
- **NFR-8:** Documentation travels with what it describes — component-facing docs materialize with the component, accelerator-facing docs do not.

### Additional Requirements

Extracted from `ARCHITECTURE-SPINE.md`. These constrain *how* stories are built and several of them dictate sequencing.

**Starter template: none, and this matters for Epic 1 Story 1.** The architecture specifies no greenfield starter or scaffold. The reference application already exists in this repository (originally `cookiecutter-django`, since restructured), so phase 1 is a brownfield rewire and extraction, not a project bootstrap. Epic 1 Story 1 is therefore the declarative catalogue (`accelerator.toml`) and its reconciliation, not a scaffold step.

**Declaration and disposition**

- `accelerator.toml` at the repository root is the single declarative catalogue and never travels (AD-1). `component.toml` is `core` and always travels, carrying what a component states about itself (AD-28). Two files, not one.
- Four exhaustive, mutually exclusive input dispositions — `core`, `feature:<name>`, `tenant`, `machinery` — with unlisted defaulting to `machinery`; two-way input reconciliation against the reference application and output reconciliation against each materialized tree (AD-2).
- A `core` path carries feature-owned regions delimited by paired `feature:<name>` / `/feature:<name>` line comments, declared in the carrier, reconciled in both directions. No other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError` (AD-24). Three known region-bearing paths: `src/config/settings/base.py`, `src/config/observability/telemetry.py`, `pixi.toml`.
- Parameterization is an orthogonal axis to disposition, declared as `[parameters]` with fixture values and exact substitution sites, reconciled both ways (AD-25). **Ordering constraint:** building the materializer before parameterization exists re-cuts every carrier entry, fixture and gate output.

**Materialization and environments**

- Materialization is subtractive: copy the reference application and remove what was not selected, at path and region granularity (AD-3). The reference application stays a real, runnable, gateable Django application throughout.
- The three features are pixi features with an `[environments]` matrix; one `pixi.lock` yields six pre-locked environments. **All six share one `solve-group`** — without it `django-celery-beat`'s `django <6.1` cap makes the two Celery combinations resolve a different Django (AD-3).
- Determinism is asserted by a gate test that materializes one combination twice and requires byte-identical trees (AD-3, NFR-5).
- The provenance stamp is `.accelerator.json` at materialized-output root: version, source ref, order values, sorted keys, **no timestamp**, a declared generated artifact. The reference application carries no stamp (AD-17).

**Layering and imports**

- Three territories with a fixed dependency direction: tenant apps may import `django_service`; `django_service` may never import a tenant app; `config` reaches tenant apps only through settings composition; a feature's code may never import another feature's (AD-4).
- `django_service` is public API with `__api_version__` as a single hand-bumped integer; the guaranteed surface is enumerated in the carrier (AD-5). No `feature:*` disposition may apply to any path inside `src/django_service/` — it is `core` in its entirety, asserted by a gate test (AD-29). UI-owned surface must move out of `django_service` before the UI feature is extracted; `base.html` and error templates stay.
- `src/django_apps/` is a path root with no `__init__.py`; an app there is imported unqualified (AD-6).
- No feature owns a package. The server-rendered interface is immovable core (revision 3), and background task processing, Redis and object storage own settings blocks, dependency entries and instrumentor calls — all feature-owned *regions* of `core` paths under AD-24. `src/features/` was proposed in revision 2 and retired unused (AD-33).
- The guaranteed surface is the contract for tenant apps as well as for graduation. With the interface mechanism core, a reusable app with its own templates, forms and views relies on it freely — it extends `base.html`, uses the form styling, and **contributes its own navigation entries** through the navigation registry, an ordered append-only key on the closed contributable surface. An app requiring a remaining feature names it in its contribution module, and AD-8's refusal rejects it at settings import wherever that feature is unselected (AD-29, AD-8).
- Import roots collapse from **six** declaration sites to one: `[tool.hatch.build.targets.wheel]` with a `sources` remapping declaring `src/` and `src/django_apps/`. Removed — `sys.path` inserts in `manage.py:23-25`, `asgi.py:18-20` and `wsgi.py`; pytest `pythonpath`; `--app-dir src` in **both** the `serve` (`pixi.toml:179`) and `serve-reload` (`:186`) tasks. The retained site is *converted* to the `sources` shape, which it does not have today (AD-7).

**Authentication and authorization**

- The mapper is two operations at different frequencies: **resolve** on every authentication (single indexed read), **sync** once per credential epoch inside one transaction. The epoch record lives in a `django_service`-owned database table, not `django.core.cache`, because two of six combinations have no Redis. **A token with no `jti` is rejected with 401** (AD-10).
- One identity key, three separated roles: credential (IdP's), identity key (`User.idp_subject` — unique, indexed, nullable, sole store), attribute (`username`/`email`/`name`, never resolved by). `USERNAME_FIELD` remains `username`; `SocialAccount` is bookkeeping, not authority (AD-11).
- Fixed mapper edge behaviours: a token lacking the group claim is 401, never zero-groups; a claim naming a nonexistent `Group` is ignored and logged, never created; `is_staff`/`is_superuser` each set from their own group and cleared; a `username` collision between distinct `idp_subject`s is refused and logged and the second identity authenticates normally (AD-12).
- Designated `Group` rows and their `Permission` rows are provisioned by a data migration inside `django_service` seeded from the claims contract; the persona seeding task **calls that same mechanism** rather than reimplementing it; a designated group missing at startup is a stage-2 refusal (AD-27).
- JWKS rotation is component code wrapping PyJWT, not PyJWT's own client — `PyJWKClient.cache_keys` defaults `False`, its unknown-`kid` refetch has no rate limiting, its LRU has no TTL (AD-23).
- allauth's OIDC provider is configured from `SOCIALACCOUNT_PROVIDERS` populated from the environment, never database-resident `SocialApp` rows; the `Site` domain is environment-driven and the existing data migration `src/django_service/contrib/sites/migrations/0003_set_site_domain_and_name.py` is retired rather than parameterized (AD-31).

**Refusals, locality and process model**

- The refusal contract is one module, `src/config/startup/`, containing both stages and the FR-17 allowlist. **Stage 1 is the last statement of every settings module**, which places it after composition and is why iteration over every configured database is reachable. **Stage 2** is owned by the `AppConfig.ready()` of one named immovable-core app in `django_service`, with a gate test asserting no adopted app precedes it in `INSTALLED_APPS`. **Predicates resolve objects, never strings** (AD-26).
- The FR-17 allowlist and the AD-8 permitted-contribution surface are **one declaration**, not two lists maintained apart (AD-8, AD-26).
- `COMPONENT_RUNTIME=local` is set in the `env` of each local pixi task; `web`/`worker`/`beat` set no runtime and set `COMPONENT_PROCESS`. **No `COMPONENT_*` variable may appear in `[activation.env]`**, asserted by a gate test over the materialized `pixi.toml`. Locality fails closed; process type fails open (AD-13).
- The local sign-in path is a URL route and no other mechanism, with its name and prefix fixed constants in the carrier; the stage-2 predicate refuses any route whose **view callable belongs to the local sign-in module** (AD-21).
- `asgi.py` exposes Django's ASGI application directly; `src/config/websocket.py`, the scope-dispatching wrapper, and its `[tool.coverage.run] omit` entry are deleted together (AD-16).
- The process model is pixi tasks enumerable by `pixi task list`; `worker` and `beat` are feature-owned regions of `pixi.toml`; replica counts and replacement strategy live in `component.toml`; the gate test is **two-way** (AD-14).
- A contributed database is a chain, not a setting: router, per-database migration step in `component.toml`, refusals iterating every configured database, automatic local substitution, readiness required-unless-declared-optional (AD-9).
- Materialized components ship no Dockerfile; this repository will ship one as `machinery` — none exists today — so the harness can verify FR-38/FR-39 payload properties (AD-15).

**Gate and verification**

- A single workflow invokes `pixi run ci`, **which has never run in CI** — though a wrongly-shaped `ci` task already exists at `pixi.toml:206`. The coverage *run invocation* moves out of the SonarCloud workflow; the template-coverage *configuration* is already correct in `pyproject.toml` and does not move. `build` comes off its fortnightly cron, which lives inside `release.yml` along with three other gate steps run inline. The six-combination harness is Linux-only (`gunicorn` has no win-64 build); the three-OS matrix stays on the reference application, and since GitHub Actions `services:` containers are Linux-only, the PostgreSQL gate is a separate ubuntu-only job. `[tool.mypy]` sets `check_untyped_defs` today, not `strict`, and three documents already assert otherwise (AD-18).
- Verification is reduced on PR (a pinned all-pairs subset declared as data in the carrier, with a gate test asserting the pinned set satisfies the predicate) and full on merge to `main` (AD-19). Sound only because generation happens from a released tag, excepting AD-32.
- The coverage floor is one global constant — ninety percent including templates, everywhere, with `COVERAGE_CORE=ctrace` in force and the omit/exclude list a **closed carrier-declared surface** asserted equal to the declared one. **Time-boxed bring-up mode:** materialized-combination gates run with the floor advisory until the materializer has reported all six numbers once; the exit condition is that report (AD-20).
- The smoke check asserts, per combination, with nothing running: boot, readiness 200, persona interactive sign-in reaching a **rendered admin index**, one Bearer request through the real authentication class, and one **rendered 404**. Separately, a `core`-disposed immovable-core assertion suite runs inside every combination's gate and is never pruned — it is what defends SC-7, and nothing else does (AD-30).
- Test location convention: accelerator and base tests live under `tests/` mirroring `src/` and carry the disposition of what they cover; a tenant app's tests live **inside the app** so they graduate with it.

**Stack (verified against conda-forge and `pixi.lock` on 2026-08-15)**

Python 3.14 · Django 6.0 · django-allauth 65.19.1 (`requests` must be declared directly) · DRF 3.18.0 / drf-spectacular 0.30 · PyJWT 2.13 / cryptography 50.0 (new) · django-storages 1.14.6 / boto3 1.43.65 · Celery 5.6 / django-celery-beat 2.9 · django-redis 7.0 / redis-py 8.1 · psycopg 3.3 · structlog 26.1 / django-structlog 10.1 · OpenTelemetry 1.44 (traces only) · gunicorn 26.0 + uvicorn-worker 0.4 · whitenoise 6.12 · pixi ≥ 0.70.2.

**Named residual risks carried into the work**

- **R-1** `django-storages` fitness unproven against Django 6.0 / Python 3.14; object storage is in three of six combinations and cannot be dropped. Escalation is ordered: spike → conda-forge feedstock push with a time-boxed package-index exception → component-owned backend as last resort.
- **R-2** Bearer revocation latency is the token's lifetime.
- **R-3** A serving process started outside `pixi run web` does not fire the migrations refusal.
- **R-4** The GitHub-template path ships from `main` HEAD carrying machinery (AD-32).
- **R-5** Local development proves less than running suggests.

**Open items with no owner** — FR-45's OTLP export end-to-end test and its collector stub design; NFR-6's telemetry-overhead measurement and its milestone; the enterprise developer portal's order-surface field list (until it exists, the fixture set covers the AD-25 parameters and the four feature booleans).

**Spike, not a decision** — dropping `uvicorn-worker` for gunicorn 26's native ASGI worker.

### UX Design Requirements

**Not applicable.** No UX design contract exists in `{planning_artifacts}` — no `ux-designs/ux-*/DESIGN.md` + `EXPERIENCE.md` spine pair, no legacy `*ux*.md`, no sharded `*ux*/index.md`.

This is consistent with the product rather than a gap. The primary product surface is a repository, not an interface: the ordering surface is the enterprise developer portal (PRD §5 non-goal, §10 integration), and the only rendered surfaces a component owns are the Django admin, framework error pages, and the optional server-rendered UI feature — none of which this phase designs. PRD §2.3 states the journeys are deliberately downscaled to anchor requirements rather than feed UX work.

The visual-surface requirements that do exist are carried as functional requirements and are covered above: FR-3 (the interface mechanism is immovable core; error-page and admin template rendering must work in every combination), AD-29 (`base.html`, the error templates, form styling and the profile views are all `core`, and `base.html` carries no hardcoded navigation), and AD-30 (the smoke check asserts a rendered admin index and a rendered 404).

### FR Coverage Map

All 56 FRs are mapped. No gaps, no duplicates.

| FRs | Epic | Coverage |
|---|---|---|
| FR-1, FR-2, FR-3 | 7 | Immovable core stated as what extraction may not remove; verified by Epic 8's AD-30 assertion suite |
| FR-4 – FR-11 | 2 | Interactive and programmatic flows, the shared mapper, the claims contract, group-driven bootstrap |
| FR-12 – FR-17 | 4 | Two evaluation stages, seven unconditional and two conditional refusals, URLconf inspection, the allowlist |
| FR-18 – FR-23 | 3 | Five substitutions, seeded personas, development keypair, unsubstituted observability, no network at boot |
| FR-24 – FR-29 | 7 | The carrier, object storage, the broker constraint, presets, clean extraction, orphan detection |
| FR-30 – FR-37 | 8 | Materializer, fixture set, PostgreSQL gate, smoke check, invalid-combination refusal, reported bounds, provenance stamp, disposition rule |
| FR-38 – FR-44 | 5 | Environmental configuration, arbitrary UID, process model, release-stage migration, health endpoints, drain ordering, session engine |
| FR-45 – FR-48 | 6 | OTLP export path, correlated logging, ASGI tracing, visible degradation |
| FR-49, FR-50 | 1 | Single audited channel, fitness proven before a feature is committed to |
| FR-51 – FR-56 | 9 | Stable import surface, tenant space, graduation, additive contribution, contributed backing services, compatibility check |

**Cross-epic threads.** Implemented in one epic and consumed in another; deliberately not double-counted above.

- FR-41's unapplied-migrations refusal is *implemented* as a stage-2 condition in Epic 4; Epic 5 owns the release-stage contract and the no-entrypoint-migrates property.
- FR-32's PostgreSQL service and the single `pixi run ci` invocation begin in Epic 1 against the reference application; Epic 8 extends both to six combinations.
- FR-17's allowlist and AD-8's contributable surface are **one declaration** — authored in Epic 4, extended in Epic 9, never forked into two lists.
- FR-29's orphan signal is declared in Epic 7 and exercised per combination in Epic 8, where the deliberate-orphan test lives because it needs a materialized combination to run against.
- FR-18's fifth substitution — filesystem-backed object storage — is delivered in Epic 7's object-storage story rather than Epic 3, because the storage feature is greenfield and does not exist until then. Its other four substitutions are Epic 3.
- FR-26's broker constraint is *declared* in Epic 7 and *enforced* by the materializer in Epic 8 as FR-34.
- Three declarations are authored in a single module in an earlier epic and moved into `accelerator.toml` in Epic 7 without changing any assertion's meaning: the coverage omit list (Epic 1), the local sign-in route's name and prefix constants (Epic 3), and the FR-14 feature-region markers (Epic 4).

**NFR coverage.** NFR-1 → Epic 4. NFR-2, NFR-3 → Epic 5. NFR-4 → Epic 1. NFR-5 → Epics 1, 8. NFR-6 → Epic 6. NFR-7 → Epics 1, 3. NFR-8 → Epic 8.

## Epic List

Nine epics. The split follows the architecture's own ordering constraints — AD-25 (parameterization before the materializer), AD-29 (UI surface leaves `django_service` before the UI feature is extracted), and R-1 (the object-storage supply-chain escalation is a long pole that must start early) — rather than PRD section numbering.

### Epic 1: A gate that detects, and a supply chain that is proven

The platform group gets a quality gate that runs, is strict, and cannot be narrowed — and the object-storage supply-chain risk is either cleared or escalated before anything depends on it. `pixi run ci` has never run in CI, `[tool.mypy]` sets `check_untyped_defs` while three documents assert `strict`, and the coverage `omit` list is open. Every later epic lands against this gate, so it goes first. Carries the R-1 spike as an early long-pole story, on FR-50's own rule that fitness is proven before a feature is committed to. Also collapses the six import-root declaration sites to one (AD-7) and deletes the sub-router network surface with its coverage `omit` entry (AD-16), both preconditions for Epic 4's allowlist to be complete rather than merely present.

**FRs covered:** FR-49, FR-50. *(NFR-4, NFR-5, NFR-7; AD-7, AD-16, AD-18, AD-20)*

### Epic 2: One way in — IdP authentication through a single mapper

A person signs into the admin by redirect to the corporate IdP; an API client presents a Bearer JWT that is verified for real; and both resolve authorization in exactly one place, keyed on one stable claim. The largest unbuilt block in the product, none of which exists today. Includes the JWKS rotation policy this product builds rather than inherits from PyJWT (AD-23), the `jti`-keyed epoch record in a `django_service`-owned table rather than the cache (AD-10), and the data migration that provisions the designated groups so the bootstrap cannot deadlock (AD-27).

**FRs covered:** FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11. *(SC-6; AD-10, AD-11, AD-12, AD-23, AD-27, AD-31)*

### Epic 3: Clone and run — a component that works with nothing installed

A developer clones a component with no network and it serves. They sign in as a staff persona, switch to a read-only one and watch the same page refuse them, mint a development token and call the API — with no database, cache, broker, object store, or identity provider running. Five substitutions, personas seeded through the same group provisioning Epic 2 built, and a locally signed JWT the real Bearer authentication class verifies. Establishes the `COMPONENT_RUNTIME=local` declaration in each local pixi task's `env` (AD-13) that Epic 4 then enforces against.

**FRs covered:** FR-18, FR-19, FR-20, FR-21, FR-22, FR-23. *(SC-4, CG-4; AD-9, AD-13, AD-21, AD-27, AD-30)*

### Epic 4: Local convenience cannot reach deployment — the refusal contract

The platform group can state, and prove, that no deployed component authenticates outside the IdP — because every forbidden configuration refuses at startup, and a credential path added next year fails the build rather than shipping. The product's highest-consequence surface, and the reason Epics 2 and 3 precede it: the conditions it enforces are about paths those epics create. One module at `src/config/startup/`, two stages, and predicates that resolve objects rather than match strings.

**FRs covered:** FR-12, FR-13, FR-14, FR-15, FR-16, FR-17. *(SC-5, CG-3, NFR-1; AD-9, AD-13, AD-21, AD-26, AD-27)*

### Epic 5: Deployable unmodified — the contract to the deployment repository

A component can be handed to a deployment repository nobody on this team owns, and it declares everything that repository needs: which processes it runs, what its probes mean, how it drains, and that migration is a release-stage step it will never perform itself. Creates `component.toml` (AD-28) — the file that makes Epic 9's adopted-app list and per-database migration steps possible at all — and ships the machinery Dockerfile that lets the harness verify the payload properties of FR-38 and FR-39.

**FRs covered:** FR-38, FR-39, FR-40, FR-41, FR-42, FR-43, FR-44. *(SC-3, NFR-2, NFR-3; AD-14, AD-15, AD-22, AD-28)*

### Epic 6: Telemetry that leaves the component, and degradation that is visible

An operator follows one request across services built by teams that never coordinated — and a cache outage shows up as log events rather than as silence. Largely satisfied today, so this epic is about what must not regress plus the one path verified nowhere: the OTLP export branch that runs only when an endpoint is configured, which local development never does. Owns two of the three ownerless open items — FR-45's collector stub design and NFR-6's telemetry-overhead measurement.

**FRs covered:** FR-45, FR-46, FR-47, FR-48. *(SC-7, NFR-6)*

### Epic 7: Three features that can actually be removed

A lead developer's selections mean something: an unselected feature is absent — no dependency, no template, no settings fragment, no skipped test — and the residue that no import graph, linter, or dependency analyzer can see is caught. Declares `accelerator.toml` (AD-1), the four dispositions and their two-way reconciliation (AD-2), the feature-owned region markers (AD-24), and parameterization as an orthogonal axis (AD-25, which must land before Epic 8). Confirms `django_service` is `core` in its entirety with nothing to relocate — the interface mechanism is immovable core (AD-29, revision 3) — deletes the `home`/`about` demonstration pages, replaces `base.html`'s hardcoded navigation with the contributed registry, and builds object storage greenfield on whatever Epic 1's R-1 spike concluded.

**FRs covered:** FR-1, FR-2, FR-3, FR-24, FR-25, FR-26, FR-27, FR-28, FR-29. *(SC-2, CG-1; AD-1, AD-2, AD-24, AD-25, AD-29)*

### Epic 8: Six combinations, proven

A platform engineer updates the base for a Django security release, and the harness reports which of the six combinations broke — before a single lead developer orders it. The load-bearing epic and the reason phase 1 does not end at the reference application: materializer, fixture set, six pre-locked pixi environments sharing one solve-group, the provenance stamp, the smoke check that renders an admin index and a 404, and the unprunable immovable-core suite that is the only thing defending SC-7.

**FRs covered:** FR-30, FR-31, FR-32, FR-33, FR-34, FR-35, FR-36, FR-37. *(SC-1, CG-2, NFR-5, NFR-8; AD-3, AD-17, AD-19, AD-20, AD-30)*

### Epic 9: Build on the base — the extension model

A team's own applications live alongside the base rather than inside it, and an application that proves useful twice graduates to the approved channel without changing its import path or anyone's `INSTALLED_APPS`. Last because it depends on the base having a declared surface, the tenant space having a disposition, and the refusals existing to iterate over what an adopted app contributes. No rework is created by this ordering: Epic 4 places stage 1 as the last statement of every settings module, which is precisely what makes the composition step land before it.

**FRs covered:** FR-51, FR-52, FR-53, FR-54, FR-55, FR-56. *(AD-4, AD-5, AD-6, AD-8, AD-9, AD-28, AD-29)*

### Epic dependency flow

Each epic stands alone and none requires a later one to function.

```text
Epic 1 ──► Epic 2 ──► Epic 3 ──► Epic 4 ──► Epic 5 ──┐
   │                                                  ├──► Epic 7 ──► Epic 8 ──► Epic 9
   └────────────────────────► Epic 6 ─────────────────┘
```

Epic 6 may run in parallel with Epics 3–5; its one dependency beyond Epic 1 is Story 6.1's assertion that authorization changes emit correlated events, which needs Epic 2's mapper. Epic 7 requires every feature to exist before it can be declared and extracted.

**Reading the acceptance criteria.** A small number of criteria reference a later epic — Story 2.2's refusal, Story 3.4's guarded route, Story 7.8's deliberate-orphan test. These are traceability markers recording where the obligation completes, not acceptance conditions for the story that carries them. No story is blocked on a later one: each is completable and testable on its own, and the forward-referenced behaviour is a separate story's acceptance criterion in the epic that owns it.

### Known file overlap, assessed

Two overlaps were reviewed and judged incidental rather than same-component-end-to-end, so no consolidation was made.

- **`pixi.toml`** is touched by Epic 1 (supply chain), Epic 3 (locality `env`), Epic 5 (process tasks), Epic 7 (feature-owned regions) and Epic 8 (the `[environments]` matrix). These are distinct blocks with distinct owners, and AD-24 makes the feature-owned ones explicitly delimited.
- **`accelerator.toml`** is authored in Epic 7 and read in Epic 8. That is a producer/consumer boundary and it is exactly where AD-25's ordering constraint sits; merging the two epics would hide the constraint the architecture states explicitly.

### Resolved during story creation: the refusal count

The source is arithmetically inconsistent. PRD §4.3 and FR-16 both state **nine** conditions (seven unconditional, two conditional); FR-13 says "seven conditions" and then lists **eight** bullets; and AD-27 adds a stage-2 refusal — a designated group absent from the database — that appears in no FR-13 bullet at all, which under a strict per-bullet reading would make ten.

**Decision: nine conditions, seven unconditional and two conditional,** reached by applying FR-16's own rule that one condition may cover several distinct forbidden states:

| # | Condition | Stage | Forbidden states |
|---|---|---|---|
| 1 | The sqlite backend is reached | 1 | 1 *(built: `production.py:26-28`)* |
| 2 | A local credential path is live in settings | 1 | 4 |
| 3 | `OTEL_SDK_DISABLED` is true | 1 | 1 |
| 4 | The JWKS trust anchor is not derived from the configured IdP | 1 | 1 |
| 5 | The claims contract is unusable | 1 and 2 | 2 — unconfigured (stage 1); a designated group absent from the database (stage 2, AD-27) |
| 6 | A forbidden credential route is reachable in the resolved URLconf | 2 | 2 — `obtain_auth_token`; the local sign-in route |
| 7 | Unapplied migrations exist on a serving process | 2 | 1 |
| 8 | *(conditional — Redis selected)* An in-process cache backend is configured | 1 | 1 |
| 9 | *(conditional — background tasks selected)* Eager task execution is enabled | 1 | 1 |

Fourteen distinct forbidden states, each tested separately under FR-16. Conditions 5 and 6 are the two groupings; both follow the precedent FR-16 already sets for the four settings-side credential paths. If the PRD is next revised, FR-13's bullet list and AD-27's condition should be reconciled to this table.

### External exit criteria — the two success criteria no story can close

Every FR is discharged by a story, but two of the seven success criteria require an environment this repository does not contain and no epic creates. They are recorded here so that completing all nine epics is not mistaken for proving all seven criteria.

| Criterion | What it requires | Why no story closes it | Owner | When |
|---|---|---|---|---|
| **SC-6** — The IdP authentication path works | A *real* IdP identity authenticating through both flows, with the mapper producing correct authorization state in both and resolving to the same user in either order | A local identity-provider container is an explicit PRD non-goal, and the local personas of Epic 3 are synthetic claims that the PRD states are "not a mitigation." Epic 2 can pass every story's acceptance criteria against unit tests with mocked JWKS and claims while SC-6 remains unproven | Platform group — a realm, client and group definitions to test against | After Epic 2 |
| **SC-3** — A component is deployable unmodified | A component containerized by CI and started on the target platform with no source edits, with its process model, health endpoints and drain behaviour intact | Deployment configuration lives in a separate repository outside this team's control and is an explicit non-goal. Story 5.6 delivers the component-side half — environmental configuration, arbitrary UID, read-only root filesystem, the machinery Dockerfile — but nothing here starts a component on the platform | Deployment repository | After Epic 5 |

**Both are integration milestones, not stories.** Neither belongs inside an epic, because neither is this repository's work to do. What phase 1 delivers is everything required for them to be attempted, and the honest statement of completion is: **five of seven success criteria are proven in-repo by the harness; SC-3 and SC-6 are proven against external environments once those are available.**

Stating this is not pessimism about the plan — it is the same discipline CG-2 applies to verification coverage. A silently narrowed claim reads as full coverage and is worse than a bounded one.

## Epic 1: A gate that detects, and a supply chain that is proven

The platform group gets a quality gate that runs, is strict, and cannot be narrowed — and the object-storage supply-chain risk is cleared or escalated before anything depends on it. Every later epic lands against this gate, so it goes first.

Two declarations authored here move later without changing meaning: Story 1.5's declared omit list moves into `accelerator.toml` in Epic 7, and Story 1.6's single import-root site gains the `src/django_apps/` root in Epic 9 without gaining a second site.

### Story 1.1: The full gate runs in CI through one invocation

As a platform engineer,
I want the complete quality gate to run in CI through a single invocation,
So that "this component passed its gate" is a statement the pipeline makes rather than a developer's laptop.

**Requirements:** AD-18 · supports FR-32, NFR-4

**Acceptance Criteria:**

**Given** `pixi run ci` has never run in CI
**When** a pull request or a push to `main` runs
**Then** exactly one workflow invokes `pixi run ci`
**And** it runs pre-commit, build, check, lint and cov in that order

**Given** template coverage measurement currently lives in the SonarCloud workflow
**When** the consolidation lands
**Then** template coverage is measured inside `pixi run ci`
**And** the SonarCloud workflow no longer owns it

**Given** `build` runs on a fortnightly cron today
**When** the consolidation lands
**Then** `build` runs as part of the gate on every change
**And** no cron invokes it

**Given** gunicorn has no win-64 build
**When** the workflows are reorganized
**Then** the reference application keeps its three-OS matrix
**And** any six-combination job is declared Linux-only

**Given** a developer runs `pixi run ci` locally
**When** CI runs the same task
**Then** both execute an identical sequence
**And** no step exists only in CI or only locally

### Story 1.2: The gate runs against PostgreSQL

As a platform engineer,
I want CI to run the suite against PostgreSQL rather than the sqlite substitution,
So that the database named in the immovable core is actually verified before anything is built on it.

**Requirements:** FR-32 (reference application) · AD-18 · SC-1

**Acceptance Criteria:**

**Given** no workflow declares a database service today
**When** the gate job runs
**Then** CI declares a PostgreSQL service
**And** sets the database URL for the gate run

**Given** the suite has only ever run against sqlite
**When** it first runs against PostgreSQL
**Then** every failure arising from sqlite-permissive behaviour is fixed at its source
**And** none is skipped or marked `xfail`

**Given** a schema PostgreSQL rejects and sqlite accepts
**When** the gate runs
**Then** the gate fails

**Given** local development uses the sqlite substitution
**When** a developer runs the suite with no database running
**Then** it still runs on sqlite
**And** the divergence remains the knowingly traded parity gap rather than a defect

### Story 1.3: Strict type checking is a gate condition

As a platform engineer,
I want mypy to run in strict mode as a gate condition,
So that the strictness three planning documents already assert becomes true of the repository.

**Requirements:** NFR-4 · AD-18

**Acceptance Criteria:**

**Given** `[tool.mypy]` sets `check_untyped_defs` today
**When** this story lands
**Then** it sets `strict = true`
**And** `python_version` continues to track the supported floor

**Given** strict mode surfaces existing errors
**When** they are resolved
**Then** each is fixed at its source
**And** none is silenced by `ignore_errors` or a module-wide `# type: ignore`

**Given** both the pre-commit hook and `pixi run check` run mypy
**When** each runs
**Then** both use the strict configuration
**And** they agree on the result

**Given** a change introducing a type error
**When** the gate runs
**Then** it fails rather than warning

### Story 1.4: No network surface exists beneath Django's routing

As a platform engineer,
I want the scope-dispatching ASGI wrapper deleted so `asgi.py` exposes Django's application directly,
So that no credential or network surface exists where the route allowlist cannot see it.

**Requirements:** AD-16 · supports FR-17, FR-47 · SC-5

**Acceptance Criteria:**

**Given** `src/config/websocket.py` and the scope-dispatching wrapper exist
**When** this story lands
**Then** both are deleted
**And** `asgi.py` exposes Django's ASGI application directly

**Given** the wrapper carries a `[tool.coverage.run] omit` entry
**When** the wrapper is deleted
**Then** that omit entry is deleted in the same change

**Given** the wrapper is gone
**When** the suite runs
**Then** requests resolve through Django's URL resolver
**And** the ASGI instrumentor still produces spans

**Given** a protocol handled below the URL resolver is proposed later
**When** it is designed
**Then** it carries its own authentication story and its own carrier entry
**And** the documentation that travels with a component states this

### Story 1.5: The coverage floor is one constant and its measurement is closed

As a platform engineer,
I want a single global coverage floor with an asserted, closed measurement surface,
So that the only residue detector this product has cannot be disabled by a one-line change nobody reads as security-relevant.

**Requirements:** AD-20 · supports FR-29 · CG-1

**Acceptance Criteria:**

**Given** Python 3.12 and later default to a core without the dynamic file tracer
**When** a gate run executes
**Then** `COVERAGE_CORE=ctrace` is in force
**And** a test asserts it during the run rather than trusting it to be inherited

**Given** a template rendered by a test
**When** coverage reports
**Then** it reports non-zero
**And** template measurement is thereby proven real rather than silently reporting zero

**Given** an omit or exclude list exists
**When** the gate runs
**Then** the effective list equals a declared list held in exactly one place
**And** a test asserts that equality in both directions

**Given** the floor is ninety percent including templates
**When** any gate runs
**Then** the floor is ninety percent
**And** it is never lowered, never made per-directory, and never cleared by a pragma on unreached code

### Story 1.6: Import roots are declared in exactly one place

As a developer working on a generated component,
I want one import-root declaration,
So that a source root cannot work under pytest and fail under gunicorn.

**Requirements:** AD-7 · supports AD-6

**Acceptance Criteria:**

**Given** six declaration sites exist today
**When** this story lands
**Then** the `sys.path` inserts at `manage.py:23-25`, `asgi.py:18-20` and in `wsgi.py` are removed
**And** the pytest `pythonpath` setting and `--app-dir src` in **both** the `serve` and `serve-reload` tasks are removed

**Given** the pytest `pythonpath` is `["src", "."]` and the `"."` entry is what makes `tests.factories` importable under `--import-mode=importlib`
**When** the setting is removed
**Then** `tests.factories` still resolves from `tests/conftest.py`
**And** how it resolves is recorded rather than left to coincidence

**Given** one site is retained
**When** the root is declared
**Then** it is `[tool.hatch.build.targets.wheel]` declaring it through a `sources` remapping
**And** the site is *converted* to that shape, since it reads `packages = ["src/config", "src/django_service"]` today
**And** the declaration is directory-level, needing no per-app edit

**Given** the removals
**When** the suite runs under pytest and the application is served under gunicorn and under uvicorn
**Then** imports resolve identically in all three

**Given** `uvicorn --app-dir` accepts a single directory
**When** roots are declared
**Then** it is never used as a declaration mechanism

### Story 1.7: No third-party package resolves from the package index

As a platform engineer,
I want a test asserting the package-index block carries only the editable self-install,
So that a future supply-chain exception must be added deliberately rather than accumulating.

**Requirements:** FR-49 · NFR-5, NFR-7

**Acceptance Criteria:**

**Given** the `[pypi-dependencies]` block
**When** the test runs
**Then** its only entry is the component's own editable path install
**And** any third-party entry fails the gate

**Given** the zero-exception state confirmed 2026-08-14
**When** `django-celery-beat` is inspected
**Then** it resolves from conda-forge
**And** it is absent from the package-index block

**Given** a dependency line whose presence is not obvious
**When** it is declared
**Then** its reasoning is recorded beside it in `pixi.toml`
**And** an exit condition is recorded where one applies

**Given** dependencies are lock-pinned
**When** the environment is solved
**Then** nothing relies on a system package

### Story 1.8: Object-storage fitness is proven before the feature is committed to

As a lead developer,
I want `django-storages` proven against the pinned Django and Python before object storage is built,
So that a feature three of six combinations will select is not committed to on the strength of a package that cannot run.

**Requirements:** FR-50 · risk R-1

**Acceptance Criteria:**

**Given** `django-storages` 1.14.6 declares support for neither Django 6.0 nor Python 3.14
**When** the spike runs
**Then** it exercises the package against the locked Django and Python through the storage API call sites the feature will use
**And** the result is recorded where the dependency is declared

**Given** the spike passes
**When** Epic 7 builds object storage
**Then** it proceeds on the channel build
**And** the evidence is attached at the point of declaration

**Given** the spike fails
**When** escalation begins
**Then** the conda-forge feedstock is pushed as was done for `django-celery-beat`, under a time-boxed package-index exception whose exit condition is that build landing
**And** a component-owned storage backend remains the last resort rather than a permanent supply-chain exception

**Given** FR-50's rule
**When** any future feature is proposed
**Then** both channel availability and fitness against the pinned runtime are confirmed before commitment
**And** presence alone is explicitly insufficient

## Epic 2: One way in — IdP authentication through a single mapper

A person signs into the admin by redirect to the corporate IdP; an API client presents a Bearer JWT that is verified for real; and both resolve authorization in exactly one place, keyed on one stable claim. The largest unbuilt block in the product, none of which exists today.

The refusals that guard these paths are Epic 4; this epic builds the paths and removes the four that bypass the IdP.

### Story 2.1: The user model carries the identity key

As a platform engineer,
I want a stable, indexed identity-key field on the user model,
So that an identity resolves to the same user no matter which flow saw them first.

**Requirements:** AD-11 · supports FR-8

**Acceptance Criteria:**

**Given** the user model today
**When** this story lands
**Then** `User.idp_subject` exists as a unique, indexed, nullable field
**And** it is the sole store of the identity key

**Given** `USERNAME_FIELD`
**When** the field is added
**Then** it remains `username`
**And** `username`, `email` and `name` remain attributes that are displayed and used in URLs but never resolved by

**Given** the migration adding the field
**When** it runs against an existing database
**Then** it applies without data loss
**And** existing rows carry a null identity key until their next authentication

### Story 2.2: The claims contract is read from the environment

As a platform engineer,
I want the identity-key claim, the group claim, and the staff and superuser groups read from configuration,
So that a component can be pointed at any IdP's claim taxonomy without a code change.

**Requirements:** FR-10 · AD-12

**Acceptance Criteria:**

**Given** the claims contract
**When** it is configured
**Then** the identity-key claim name, the group-claim name, the staff-conferring group and the superuser-conferring group are each read from the environment

**Given** differing IdP taxonomies
**When** the group-claim name is set
**Then** `groups`, `roles` and `realm_access.roles` are each expressible without a code change

**Given** no claims contract is configured
**When** a deployed component starts
**Then** it will refuse to start once Epic 4 lands
**And** no conventional claim name is defaulted in its place

### Story 2.3: The designated groups exist before the first authentication

As a lead developer,
I want the designated groups and their permissions provisioned by the component,
So that the first administrator can be established by claim rather than deadlocking on an admin nobody can reach.

**Requirements:** FR-11 · AD-27 · SC-6

**Acceptance Criteria:**

**Given** the claims contract names a staff group and a superuser group
**When** the component migrates
**Then** a data migration inside `django_service` creates those `Group` rows and attaches their `Permission` rows
**And** it is seeded from the claims contract rather than from hardcoded names

**Given** the migration has already run
**When** it runs again
**Then** it is idempotent and creates no duplicates

**Given** any other path that needs those groups
**When** it runs
**Then** it calls this same provisioning mechanism
**And** no path creates groups of its own

**Given** the deployed bootstrap path
**When** it is documented
**Then** the documentation states that the first administrator is established by IdP group claim
**And** that `createsuperuser` remains available only where the refusals do not apply

### Story 2.4: The mapper resolves an identity to a user

As a platform engineer,
I want one mapper that resolves any set of claims to a user by the identity key alone,
So that the same person is the same user across flows, and two people whose emails collide are not.

**Requirements:** FR-8 · AD-10, AD-11, AD-12 · SC-6

**Acceptance Criteria:**

**Given** the mapper at `src/config/authorization/`
**When** any caller presents claims
**Then** the user is resolved or created by the identity-key claim alone
**And** never by email address or username

**Given** an identity first seen through one flow and later through the other
**When** it authenticates the second time
**Then** it resolves to the same user
**And** a test asserts this in both orders

**Given** two distinct identities whose email claims collide
**When** each authenticates
**Then** they resolve to two distinct users

**Given** a `username` collision between two distinct identity keys
**When** the second identity authenticates
**Then** the collision is refused and logged
**And** the second identity keeps its existing username and authenticates normally

**Given** resolution runs on every authentication including every Bearer request
**When** it runs
**Then** it is a single indexed read

### Story 2.5: The mapper syncs authorization once per credential epoch

As a platform engineer,
I want group membership, staff and superuser status re-synced from claims on every credential epoch including removals,
So that a revocation at the IdP reaches the component rather than persisting until someone notices.

**Requirements:** FR-9, FR-11 · AD-10, AD-12 · SC-6 · risk R-2

**Acceptance Criteria:**

**Given** an authentication
**When** sync runs
**Then** it adds the memberships the claims assert, removes the memberships they no longer assert, sets `is_staff` and `is_superuser` each from its own designated group, and emits a structured log line recording what changed
**And** all of it runs inside one transaction

**Given** sync frequency
**When** an interactive login occurs
**Then** sync runs
**And** when a Bearer credential is seen, sync runs once at first sighting of its `jti` and not on subsequent requests carrying the same `jti`

**Given** two of six combinations have no Redis
**When** the epoch record is stored
**Then** it lives in a `django_service`-owned database table
**And** never in `django.core.cache`

**Given** a Bearer token with no `jti`
**When** it is presented
**Then** it is rejected with 401

**Given** mapping must not live in `populate_user()`
**When** an identity authenticates a second and subsequent time
**Then** a test asserts mapping still occurs

**Given** an identity whose claims drop the designated staff group
**When** it next authenticates
**Then** it loses staff status
**And** can no longer reach the admin

**Given** a token lacking the configured group claim
**When** it is presented
**Then** it is rejected with 401
**And** never authenticated with zero groups

**Given** a claim asserting a group with no matching Django `Group`
**When** sync runs
**Then** the claim is ignored and logged
**And** no group is created

### Story 2.6: A person authenticates interactively against the IdP

As a lead developer,
I want browser sign-in to redirect to the IdP and establish a session through the shared mapper,
So that the admin and the server-rendered UI have exactly one credential authority.

**Requirements:** FR-4, FR-7 · AD-31 · SC-6

**Acceptance Criteria:**

**Given** an unauthenticated request to an authenticated page
**When** it is served
**Then** it redirects to the IdP
**And** never to a local login form

**Given** the OIDC provider
**When** it is wired
**Then** it is `allauth.socialaccount.providers.openid_connect` from the installed distribution
**And** no additional OIDC framework is added
**And** `requests` is declared directly in the dependency manifest rather than relied on transitively

**Given** a successful callback
**When** the session is established
**Then** allauth's `SocialAccountAdapter` invokes the mapper
**And** contains no mapping logic of its own

**Given** provider configuration
**When** the component starts
**Then** it is read from `SOCIALACCOUNT_PROVIDERS` populated from the environment
**And** never from database-resident `SocialApp` rows

**Given** the `Site` domain
**When** it is configured
**Then** it is environment-driven
**And** the data migration at `src/django_service/contrib/sites/migrations/0003_set_site_domain_and_name.py` is retired rather than parameterized

**Given** `/admin/` login
**When** `DJANGO_ADMIN_FORCE_ALLAUTH` defaults to true
**Then** it is served by the IdP redirect through the existing `secure_admin_login` wrapper in `users/admin.py`
**And** never by Django's own credential form

### Story 2.7: An API client authenticates programmatically against the IdP

As a developer working on a generated component,
I want Bearer JWTs verified against the IdP's JWKS with rotation handled,
So that API authentication is real verification rather than a local lookup.

**Requirements:** FR-5 · AD-10, AD-23 · SC-6

**Acceptance Criteria:**

**Given** an `Authorization: Bearer <JWT>` header
**When** it is presented
**Then** a `rest_framework.authentication.BaseAuthentication` subclass using PyJWT and `cryptography` verifies signature, `iss`, `aud` and `exp`
**And** a token failing any one of them is rejected with 401

**Given** a successful validation
**When** authorization is decided
**Then** the authentication class invokes the mapper
**And** contains no mapping logic of its own

**Given** JWKS material
**When** it is first needed
**Then** it is fetched lazily on the first Bearer request that needs it
**And** never at import or at boot

**Given** keys cached by `kid`
**When** a token presents an uncached `kid`
**Then** exactly one refetch is triggered, rate-limited so it cannot be driven by an attacker
**And** a key rotation is survived without a restart

**Given** `PyJWKClient.cache_keys` defaults to `False`, its unknown-`kid` refetch has no rate limiting, and its LRU has no TTL
**When** this policy is implemented
**Then** it is component code wrapping PyJWT
**And** the tests for caching, refetch and rate limiting belong to that code

**Given** a cache lifetime
**When** it is configured
**Then** it exists only as a backstop for key removal

### Story 2.8: The static-token credential surface is removed entirely

As a platform engineer,
I want every locally minted API token path deleted,
So that a deployed component has no credential path the IdP does not own.

**Requirements:** FR-6 · SC-5

**Acceptance Criteria:**

**Given** `REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES`
**When** this story lands
**Then** `TokenAuthentication` is absent
**And** `rest_framework.authtoken` is absent from `INSTALLED_APPS`

**Given** the URL configuration
**When** the route is removed
**Then** a request to `/api/auth-token/` returns 404
**And** a test asserts the route's absence from the *resolved* URL configuration rather than merely the setting's absence

**Given** the programmatic flow from Story 2.7 is in place
**When** an API client authenticates
**Then** it uses the Bearer flow
**And** no functionality is lost by the removal

## Epic 3: Clone and run — a component that works with nothing installed

A developer clones a component with no network and it serves. They sign in as a staff persona, switch to a read-only one and watch the same page refuse them, mint a development token and call the API — with no database, cache, broker, object store, or identity provider running.

Four of the five substitutions land here. The fifth — filesystem-backed object storage — is delivered in Epic 7 alongside the storage feature itself, which does not exist until then. The locality declaration established here is what Epic 4 enforces against, and the local sign-in route's constants move into the carrier in Epic 7.

### Story 3.1: Local pixi tasks declare themselves local

As a developer working on a generated component,
I want locality declared by the task I run rather than by a file in the source tree,
So that a freshly cloned component runs with one command and the declaration is inert in deployment.

**Requirements:** AD-13 · supports FR-12 · SC-5

**Acceptance Criteria:**

**Given** each local pixi task
**When** it is declared
**Then** it sets `COMPONENT_RUNTIME=local` in its own `env`
**And** the declaration is committed, so a freshly cloned component runs with one command

**Given** a container runs its server process directly and never invokes a local task
**When** a component is deployed
**Then** the local declaration is inert

**Given** `[activation.env]` reaches production because the golden base runs pixi
**When** the configuration is inspected
**Then** no `COMPONENT_*` variable appears in `[activation.env]`
**And** a test asserts this over the `pixi.toml`

**Given** the locality declaration
**When** it is absent or unrecognized
**Then** the component treats itself as deployed
**And** local development is the exception that must declare itself

### Story 3.2: The database, cache and task substitutions hold locally

As a developer working on a generated component,
I want the component to run with no database, cache or broker,
So that changing a line of business logic does not require standing up four services first.

**Requirements:** FR-18, FR-22 · AD-9 · SC-4

**Acceptance Criteria:**

**Given** neither `DATABASE_URL` nor `POSTGRES_DB` is set
**When** the component starts
**Then** sqlite is selected
**And** the ORM, migrations and the full suite are preserved

**Given** no cache service is running
**When** the component starts
**Then** an in-process cache backend is configured
**And** the cache API is preserved at every call site

**Given** no broker is running
**When** a task is invoked
**Then** execution is eager and propagating
**And** task bodies are invoked synchronously

**Given** every valid combination
**When** it runs locally
**Then** it runs with no broker, including the combinations that selected background task processing
**And** the documentation states that the broker constraint is a statement about deployment only, so it does not read as absolute

### Story 3.3: Personas are seeded from declared claims

As a developer working on a generated component,
I want named local identities declared as configuration and materialized by a task,
So that I can exercise real authorization differences without an identity realm.

**Requirements:** FR-19 · AD-27 · SC-4

**Acceptance Criteria:**

**Given** persona declarations
**When** they are read
**Then** each declares its groups, its profile fields, and the identity-key claim the mapper resolves by
**And** at least two personas exist with different group memberships, one of which carries the designated staff group

**Given** the seeding task
**When** it runs locally
**Then** it materializes the declared personas as local accounts
**And** it obtains the designated groups by calling the provisioning mechanism from Story 2.3 rather than creating groups of its own

**Given** a persona whose declared groups change
**When** it re-authenticates
**Then** the corresponding membership change occurs, including removal

**Given** the seeding task
**When** it is invoked in a deployed environment
**Then** it raises the same `ImproperlyConfigured` as the refusal contract
**And** it never creates a local account there

**Given** a persona signs in twice
**When** it is resolved
**Then** it is the same user both times

### Story 3.4: Local sign-in is a URL route that drives the real mapper

As a developer working on a generated component,
I want local sign-in to construct synthetic claims and hand them to the same mapper the IdP flows use,
So that the authorization behaviour I see locally is the deployed behaviour minus the network hops.

**Requirements:** FR-19 · AD-21 · SC-4, SC-5

**Acceptance Criteria:**

**Given** local persona sign-in
**When** it is exposed
**Then** it is a URL route and no other mechanism
**And** it is not a development authentication backend, a management command that writes a session, or a query-parameter shim

**Given** the route
**When** it is declared
**Then** its URL name and path prefix are fixed constants held in exactly one place
**And** that declaration moves into `accelerator.toml` in Epic 7 without changing its meaning

**Given** a sign-in
**When** it completes
**Then** it constructs a synthetic claims payload and passes it to the mapper
**And** the mapper is unaware which path produced the claims

**Given** a staff persona and a read-only persona
**When** each reaches the same admin page
**Then** the staff persona is admitted and the read-only persona is refused
**And** the difference is produced by the mapper rather than by any local-only branch

**Given** this route is a credential path the product itself introduces
**When** Epic 4 lands
**Then** it is refused at startup in a deployed component

### Story 3.5: The local programmatic flow validates for real

As a developer working on a generated component,
I want a locally minted token that the real Bearer authentication class genuinely verifies,
So that API authorization is exercised locally rather than stubbed.

**Requirements:** FR-20 · NFR-7 · SC-4

**Acceptance Criteria:**

**Given** a development task
**When** it mints a token
**Then** the token is a JWT signed by a locally generated keypair
**And** local settings point the JWKS location at that key

**Given** the minted token
**When** it is presented
**Then** the real Bearer authentication class verifies signature, `iss`, `aud` and `exp`
**And** no verification step is stubbed or skipped

**Given** a tampered or expired locally signed token
**When** it is presented
**Then** it is rejected

**Given** the keypair
**When** it is created
**Then** it is generated on demand into a gitignored path
**And** it is never committed, because a key committed to a template would ship inside every component generated from it

### Story 3.6: Observability is not substituted locally

As a developer working on a generated component,
I want the same observability code running locally that runs deployed,
So that telemetry is the one capability I cannot accidentally work without.

**Requirements:** FR-21 · CG-4

**Acceptance Criteria:**

**Given** no OTLP endpoint is configured
**When** the component runs locally
**Then** the tracer provider is still installed, all instrumentors still instrument, and spans are still created and ended
**And** `trace_id` and `span_id` still reach every log line
**And** spans are discarded at the processor

**Given** `OTEL_TRACES_EXPORTER=console`
**When** the component runs
**Then** spans are written to stdout
**And** nothing else about the behaviour changes

**Given** an unreachable endpoint
**When** the local configuration is inspected
**Then** no batch processor is attached to an exporter pointed at it
**And** no retry cycle floods stderr through a test run

### Story 3.7: Nothing on the local start path reaches the network at boot

As a developer working on a generated component,
I want boot to make no network call,
So that a component starts with no route to the IdP rather than failing in a way only an offline developer ever sees.

**Requirements:** FR-23 · AD-23

**Acceptance Criteria:**

**Given** settings import and Django setup
**When** a unit test completes them
**Then** no OIDC discovery request is performed

**Given** boot
**When** a unit test completes it
**Then** JWKS retrieval is not triggered
**And** it is triggered only by the first Bearer request that needs it

**Given** persona seeding and development keypair generation
**When** each runs
**Then** keypair generation is computation and seeding is a database write
**And** neither reaches a registry, the IdP, or a package index

**Given** environment installation downloads packages by definition
**When** this requirement is scoped
**Then** the claim begins once the environment exists

## Epic 4: Local convenience cannot reach deployment — the refusal contract

The platform group can state, and prove, that no deployed component authenticates outside the IdP — because every forbidden configuration refuses at startup, and a credential path added next year fails the build rather than shipping.

This is the product's highest-consequence surface and the reason Epics 2 and 3 precede it: the conditions it enforces are about paths those epics create. Nine conditions and fourteen forbidden states, per the table above. The FR-14 region markers written here are declared in the carrier in Epic 7.

### Story 4.1: The refusal contract has one home and two evaluation stages

As a platform engineer,
I want both refusal stages in one module, evaluated independently of which settings module loaded,
So that the guard cannot be skipped by the very failure it exists to catch.

**Requirements:** FR-12 · AD-13, AD-26 · NFR-1 · SC-5

**Acceptance Criteria:**

**Given** the refusal contract
**When** it is located
**Then** it is one module at `src/config/startup/` containing both stages and the FR-17 allowlist
**And** it is not split across the deployed settings module

**Given** stage 1
**When** a leaf settings module is imported
**Then** stage 1 is invoked as the last statement of that leaf module — `local.py`, `production.py`, `test.py`
**And** every leaf module invokes it, so none can skip it by not being loaded
**And** `base.py` does not invoke it, since it is imported via `from .base import *` and a call there would fire before the leaf composes, destroying the after-composition property the rule exists to guarantee
**And** a paired gate test asserts both halves

**Given** stage 2
**When** a serving process starts
**Then** it is invoked by the `AppConfig.ready()` of one named immovable-core application inside `django_service`
**And** it fires under gunicorn and uvicorn as well as under management commands
**And** a test asserts it fires through a served request path, not only through `manage.py`

**Given** `INSTALLED_APPS` ordering
**When** the gate runs
**Then** a test asserts that no adopted application precedes the stage-2 owner

**Given** the decision *am I deployed?*
**When** it is made
**Then** it is read from the environment and never inferred from which settings module loaded
**And** absent or unrecognized means deployed

**Given** a deployed environment with its settings module pointed at the local module
**When** the component starts
**Then** it refuses
**And** a test constructs exactly that state and asserts the refusal

**Given** the nine checks
**When** they run
**Then** they perform no network call and no query beyond migration state
**And** their cost is irrelevant to startup time

### Story 4.2: Five unconditional refusals evaluate at settings import

As a platform engineer,
I want every forbidden state readable from settings alone refused at settings import,
So that a deployed component with local convenience configured never reaches a serving state.

**Requirements:** FR-13 (stage 1) · AD-26 · CG-3 · SC-5

**Acceptance Criteria:**

**Given** the sqlite backend is reached in a deployed component
**When** settings are imported
**Then** `ImproperlyConfigured` is raised
**And** the existing check at `production.py:26-28` is the mechanism

**Given** a local credential path live in settings
**When** settings are imported
**Then** `ImproperlyConfigured` is raised for each of four states: `ModelBackend` present in `AUTHENTICATION_BACKENDS`; a non-empty `ACCOUNT_LOGIN_METHODS`; `DJANGO_ADMIN_FORCE_ALLAUTH` not true; and `rest_framework.authtoken` installed or `TokenAuthentication` in the DRF defaults

**Given** `OTEL_SDK_DISABLED` is true in a deployed component
**When** settings are imported
**Then** `ImproperlyConfigured` is raised, because the component has silently opted out of an immovable guarantee

**Given** a JWKS location not derived from the configured IdP issuer
**When** settings are imported
**Then** `ImproperlyConfigured` is raised
**And** this catches a component anchored to a key generated onto a developer's laptop, with no key file present at all

**Given** no identity-key claim, no group-claim name, or no designated staff group
**When** settings are imported
**Then** `ImproperlyConfigured` is raised
**And** no conventional claim name is defaulted in its place

### Story 4.3: Three unconditional refusals evaluate at serving-process startup

As a platform engineer,
I want the conditions that need the application registry refused when a serving process starts,
So that a reachable credential route or an unrecognized schema stops the process rather than serving traffic.

**Requirements:** FR-13 (stage 2), FR-15, FR-41 · AD-9, AD-21, AD-26, AD-27 · SC-5

**Acceptance Criteria:**

**Given** a reachable forbidden credential route
**When** stage 2 resolves the URL configuration
**Then** `ImproperlyConfigured` is raised for each of two states: a route whose view callable is `obtain_auth_token`, and a route whose view callable belongs to the local sign-in module

**Given** the predicates
**When** they evaluate a route
**Then** they resolve the view callable
**And** they never match on a route name or a path prefix, so a route named `local_persona_login` mounted under `/accounts/` cannot evade them

**Given** a component whose settings are correct but whose URL configuration still routes `obtain_auth_token`
**When** it starts
**Then** it refuses
**And** a test constructs exactly that state

**Given** unapplied migrations on any configured database
**When** a serving process starts
**Then** `ImproperlyConfigured` is raised
**And** management commands are exempt, so `manage.py migrate` — the one action that clears the condition — is not forbidden by it

**Given** a designated staff or superuser group absent from the database
**When** a serving process starts
**Then** `ImproperlyConfigured` is raised
**And** the misconfiguration surfaces as a configuration error rather than as a mysterious permissions problem

**Given** stage 1 runs as the last statement of every leaf settings module
**When** stage 1 and stage 2 iterate databases
**Then** both iterate every configured database

### Story 4.4: Two feature-scoped refusals apply only where their feature exists

As a lead developer,
I want the cache and task refusals scoped to the features that make them meaningful,
So that the two valid combinations with no Redis are not rejected for legitimately having no cache.

**Requirements:** FR-14 · AD-24 · SC-5

**Acceptance Criteria:**

**Given** the Redis cache feature is selected
**When** an in-process cache backend is configured in a deployed component
**Then** `ImproperlyConfigured` is raised

**Given** background task processing is selected
**When** eager task execution is enabled in a deployed component
**Then** `ImproperlyConfigured` is raised

**Given** a combination in which the corresponding feature is absent
**When** the component starts
**Then** neither condition is evaluated
**And** startup proceeds

**Given** these two refusals are feature-conditional
**When** they are written
**Then** they are delimited as feature-owned regions by paired `feature:<name>` / `/feature:<name>` line comments
**And** they are not unconditional code guarded by a runtime flag

### Story 4.5: Every refusal is tested as a refusal

As a platform engineer,
I want each forbidden state to have a test that configures it and asserts the raise,
So that the suite proves the deployed settings refuse rather than merely proving they start.

**Requirements:** FR-16 · CG-3 · SC-5

**Acceptance Criteria:**

**Given** the fourteen distinct forbidden states across nine conditions
**When** the suite runs
**Then** each has at least one test that configures that state and asserts `ImproperlyConfigured`
**And** a condition covering several states has each state tested separately

**Given** the settings-module escape route
**When** it is tested
**Then** the test configures a deployed environment with the local settings module loaded and asserts refusal

**Given** each stage-2 condition
**When** it is tested
**Then** at least one test exercises it through a served request path
**And** not only through `manage.py`

**Given** any refusal
**When** it fires
**Then** it raises rather than logging and continuing
**And** no refusal is softened into a warning

### Story 4.6: The authentication surface matches an allowlist exactly

As a platform engineer,
I want the component's authentication surface asserted against an approved list,
So that a credential path invented after this PRD fails the build until someone adds it deliberately.

**Requirements:** FR-17 · AD-8, AD-26 · SC-5

**Acceptance Criteria:**

**Given** `AUTHENTICATION_BACKENDS` and the DRF default authentication classes
**When** the allowlist test runs
**Then** each matches the approved allowlist exactly
**And** an entry present but not listed fails the test

**Given** resolved URL routes
**When** they are checked
**Then** only the route prefixes the component itself owns for authentication, admin login and token issuance are in scope
**And** business routes a developer adds are out of its scope

**Given** a developer adding a credential path
**When** the change is made
**Then** the allowlist must be edited in the same change
**And** that edit is the moment a human decides whether the path belongs

**Given** the allowlist and the contributable-configuration surface Epic 9 will need
**When** they are declared
**Then** they are one declaration
**And** never two lists maintained apart

## Epic 5: Deployable unmodified — the contract to the deployment repository

A component can be handed to a deployment repository nobody on this team owns, and it declares everything that repository needs: which processes it runs, what its probes mean, how it drains, and that migration is a release-stage step it will never perform itself.

`component.toml` is created here and is what makes Epic 9's adopted-app list and per-database migration steps possible at all.

### Story 5.1: The component declares itself in component.toml

As a platform engineer,
I want a component-owned declaration that always travels,
So that a rule a component must obey at runtime does not live in a file the component does not have.

**Requirements:** AD-28 · supports FR-40 · SC-3

**Acceptance Criteria:**

**Given** `component.toml`
**When** it is created
**Then** it carries what the component states about itself: the adopted-application list, per-database requiredness, per-database release-stage migration steps, and the process-model constraints

**Given** the disposition system
**When** `component.toml` is classified
**Then** it is `core` and always travels

**Given** the split between the two declarations
**When** a rule is placed
**Then** a rule the component must obey at runtime or deploy time goes in `component.toml`
**And** a rule only the materializer needs goes in `accelerator.toml`

**Given** a component with no adopted applications
**When** it starts
**Then** an empty adopted-application list is valid and requires no special case

### Story 5.2: The process model is declared as pixi tasks with its constraints as data

As an operator,
I want to enumerate a component's process types and their constraints without reading its source,
So that any component can be run the same way regardless of which features it selected.

**Requirements:** FR-40 · AD-13, AD-14 · SC-3

**Acceptance Criteria:**

**Given** the process types
**When** they are declared
**Then** `web`, `worker` and `beat` are pixi tasks invoked as `pixi run <process>`
**And** they are enumerable with `pixi task list`

**Given** each process task
**When** it runs
**Then** it sets `COMPONENT_PROCESS`
**And** sets no runtime, inheriting *deployed*

**Given** process type is absent
**When** locality and process type are evaluated
**Then** locality fails closed and process type fails open
**And** a process type failing closed would deadlock the release stage on the migrations refusal

**Given** `web`
**When** any of the six combinations is inspected
**Then** it is present in all six, served by gunicorn with the uvicorn worker class

**Given** `worker` and `beat`
**When** a combination without background task processing is inspected
**Then** they are absent
**And** they are removed as feature-owned regions of `pixi.toml` rather than surviving into a component the deployment repository would then try to run

**Given** the declaration and the tasks
**When** the gate test runs
**Then** it checks both directions: every process type the declaration names has a matching task, and every task in the process group is named by the declaration

**Given** `beat`
**When** its constraints are declared in `component.toml`
**Then** they state exactly one replica, because its schedule lives in PostgreSQL
**And** they state that it must be replaced by stopping the old process before starting the new one, because a default rolling update would produce the two-replica window the replica count forbids

### Story 5.3: Two asymmetric health endpoints

As an operator,
I want liveness and readiness to mean deliberately different things,
So that a brief database outage degrades a component instead of crash-looping the estate.

**Requirements:** FR-42 · AD-22 · NFR-2 · SC-3

**Acceptance Criteria:**

**Given** the liveness endpoint
**When** it is probed
**Then** it checks nothing external
**And** the process either responds or it does not

**Given** the readiness endpoint
**When** it is probed
**Then** it checks that every required database answers
**And** returns non-200 when one does not

**Given** a process that has booted but has not yet contacted its database
**When** readiness is probed
**Then** it returns non-200 until the first successful contact

**Given** a rolling deploy in which an older replica runs against a newer schema
**When** readiness is probed
**Then** it does not re-check migrations
**And** the older replica is not reported unready for a schema difference backwards-compatible migrations exist to permit

**Given** no health route exists today
**When** this story lands
**Then** both endpoints are built rather than adapted

### Story 5.4: Shutdown drains in a defined order

As an operator,
I want termination to stop traffic before it finishes in-flight work,
So that a deploy does not drop requests that arrived during the drain.

**Requirements:** FR-43 · AD-22 · SC-3

**Acceptance Criteria:**

**Given** a web process receives `SIGTERM`
**When** shutdown begins
**Then** readiness flips before the drain begins
**And** the process then stops accepting connections, finishes in-flight requests, and exits

**Given** a worker process receives `SIGTERM`
**When** shutdown begins
**Then** it finishes its current task and declines new ones

**Given** the grace period
**When** ownership is assigned
**Then** the component owns the ordering
**And** the grace period value is a deployment-repository setting

### Story 5.5: Migrations are a release-stage step the component never performs

As a platform engineer,
I want no entrypoint to migrate and the component to refuse an unrecognized schema,
So that migration cannot race across replicas and a serving process never runs against a schema it does not know.

**Requirements:** FR-41 · AD-22 · SC-3 · risk R-3

**Acceptance Criteria:**

**Given** every entrypoint, task and container command
**When** they are inspected
**Then** none runs migrations
**And** a test asserts this over the materialized process tasks

**Given** unapplied migrations
**When** a serving process starts
**Then** the stage-2 refusal from Story 4.3 raises `ImproperlyConfigured`

**Given** the deployment pipeline
**When** the contract is documented
**Then** the documentation states that migration runs before new pods begin serving
**And** that it runs once per database as `component.toml` declares

**Given** a serving process started outside `pixi run web`
**When** the migrations refusal is considered
**Then** it does not fire
**And** this is the accepted price of a fail-open process type

### Story 5.6: The component is a payload that runs as an arbitrary non-root user

As an operator,
I want a component to start from environment variables alone under a platform-assigned UID,
So that it fits the image pipeline rather than acquiring an opt-out from it.

**Requirements:** FR-38, FR-39 · AD-15 · NFR-3 · SC-3

**Acceptance Criteria:**

**Given** a built image
**When** it is inspected
**Then** no configuration file is present
**And** the component starts from environment variables alone

**Given** an arbitrary non-root UID and a read-only root filesystem
**When** the component starts
**Then** startup succeeds
**And** the component declares no writable path beyond a temporary directory

**Given** the zero-writable-path claim
**When** it is verified
**Then** it is asserted rather than assumed: static files are collected at build and served by the application, user media is a non-goal, logs go to the event stream, and sessions are database-backed

**Given** materialized components
**When** they are produced
**Then** they ship no Dockerfile
**And** the buildpack and golden-base path is the default

**Given** this repository
**When** the harness needs to verify the payload properties
**Then** it ships a Dockerfile classified as `machinery`, which does not exist today

### Story 5.7: Sessions are database-backed with the engine set explicitly

As a platform engineer,
I want the session engine set explicitly in every combination,
So that session behaviour is never a property of an unrelated feature toggle.

**Requirements:** FR-44 · AD-10, AD-31 · NFR-3

**Acceptance Criteria:**

**Given** `SESSION_ENGINE`
**When** settings are composed
**Then** it is set explicitly in `base.py` to the database-backed engine
**And** it is identical in all six combinations

**Given** the Redis cache feature
**When** it is selected
**Then** it may not change `SESSION_ENGINE`

**Given** expired session rows and expired mapper epoch records
**When** pruning is specified
**Then** both are pruned by one declared admin process
**And** deliberately not by a background task, since background task processing exists in only two of six combinations

**Given** the scheduling of that admin process
**When** scope is assigned
**Then** the schedule lives in the deployment repository and is out of scope here
**And** the component-side declaration and documentation are in scope

## Epic 6: Telemetry that leaves the component, and degradation that is visible

An operator follows one request across services built by teams that never coordinated — and a cache outage shows up as log events rather than as silence. Largely satisfied today, so this epic is mostly about what must not regress, plus the one path that is verified nowhere.

This epic owns two of the three ownerless open items: FR-45's collector stub and NFR-6's measurement. Both need an owner named as part of their story.

### Story 6.1: Correlated structured logging holds in every combination

As an operator,
I want every log line from every component to carry the same correlation identifiers,
So that I can follow one request across services whose teams never coordinated.

**Requirements:** FR-46 · SC-7

**Acceptance Criteria:**

**Given** any component
**When** it logs
**Then** it writes a JSON event stream to stdout
**And** it never manages log files or rotation

**Given** a log line emitted during a request
**When** it is inspected
**Then** it carries `request_id`, `trace_id` and `span_id`
**And** this holds in all six combinations

**Given** background task processing is selected
**When** a task executes
**Then** correlation propagates into task execution
**And** `django-structlog`'s Celery correlation-ID propagation is wired only where that feature is selected

**Given** an authorization change
**When** the mapper syncs
**Then** it emits a structured event correlated with `request_id` and `trace_id`

### Story 6.2: ASGI requests produce spans

As an operator,
I want ASGI requests instrumented in every combination,
So that request traces are not silently absent from components served the only way they are served.

**Requirements:** FR-47 · SC-7

**Acceptance Criteria:**

**Given** the ASGI instrumentor
**When** any of the six combinations is inspected
**Then** it is present and active
**And** without it ASGI requests would produce no spans at all

**Given** a request served over ASGI
**When** the suite runs
**Then** a test asserts that spans are produced for it

### Story 6.3: Trace export is environmental and drops rather than retries

As a developer working on a generated component,
I want export attached only when a collector is configured,
So that local development does not retry against an unreachable endpoint through every test run.

**Requirements:** FR-45 · CG-4

**Acceptance Criteria:**

**Given** the OTLP endpoint or its traces-specific variant is set
**When** the component starts
**Then** export is enabled

**Given** neither is set
**When** the component starts
**Then** no span processor is attached
**And** spans end without export

**Given** an unreachable endpoint
**When** the configuration is inspected
**Then** no batch processor is attached to an exporter pointed at it

### Story 6.4: The OTLP export path is exercised end to end

As a platform engineer,
I want the export branch tested against a collector stub inside every combination's gate,
So that the one path carrying telemetry off a component is not the one path nothing verifies.

**Requirements:** FR-45 · spine Open Item (no AD, needs an owner)

**Acceptance Criteria:**

**Given** exporter *selection* is comprehensively covered today
**When** coverage is examined
**Then** the branch that actually exports is shown to run only when an endpoint is configured, which local development never does

**Given** a collector stub
**When** at least one test runs
**Then** it drives a batch span processor against an OTLP exporter end to end
**And** exercises serialization, transport and batch behaviour

**Given** this test
**When** the gate runs
**Then** it runs inside every combination's gate

**Given** this is an open item with no architectural decision
**When** the story is picked up
**Then** an owner is named and the collector stub's shape is decided as part of it

### Story 6.5: Swallowed cache failures become log events

As an operator,
I want a degrading cache to be visible,
So that a component whose telemetry is immovable does not degrade invisibly.

**Requirements:** FR-48 · SC-7

**Acceptance Criteria:**

**Given** the Redis cache feature is selected
**When** a cache operation raises
**Then** the exception continues to be ignored so a cache outage degrades the component rather than stopping it

**Given** the same swallowed failure
**When** it is ignored
**Then** it emits a log event correlated with `request_id` and `trace_id`
**And** nothing is swallowed silently

### Story 6.6: Telemetry overhead is measured once and recorded

As a platform engineer,
I want the cost of always-on instrumentation measured rather than asserted,
So that the claim that it is acceptable rests on a number.

**Requirements:** NFR-6 · spine Open Item (no AD, needs an owner)

**Acceptance Criteria:**

**Given** instrumentation is always on and never conditionally disabled to gain performance
**When** the overhead is established
**Then** it is measured once against the reference application with export disabled
**And** recorded alongside the observability documentation

**Given** the instrumentation set changes
**When** the measurement is reconsidered
**Then** it is re-measured
**And** not otherwise

**Given** this is an open item with no architectural decision
**When** the story is picked up
**Then** an owner and a milestone are named as part of it

## Epic 7: Three features that can actually be removed

A lead developer's selections mean something: an unselected feature is absent — no dependency, no template, no settings fragment, no skipped test — and the residue that no import graph, linter, or dependency analyzer can see is caught.

This epic declares; Epic 8 verifies against materialized output. Story 7.3 must land before Epic 8 begins, because building the materializer before parameterization exists re-cuts every carrier entry, every fixture, and every combination's gate output.

### Story 7.1: The carrier exists and every path carries exactly one disposition

As a lead developer,
I want one declarative catalogue that is the only place a feature's extent is defined,
So that nothing infers what a feature owns from naming or directory layout.

**Requirements:** FR-24 · AD-1, AD-2 · NFR-5 · SC-2

**Acceptance Criteria:**

**Given** `accelerator.toml`
**When** it is created
**Then** it lives at the repository root
**And** it is classified `machinery` and never travels

**Given** a feature
**When** its extent is declared
**Then** the carrier declares its package surface, its non-package surface — settings fragments, application modules, observability wiring, templates, static assets, tests — its constraints, and the presets that pre-select it
**And** nothing infers any of that from a naming convention

**Given** the four input dispositions
**When** a path is classified
**Then** it is exactly one of `core`, `feature:<name>`, `tenant` or `machinery`
**And** the four are exhaustive and mutually exclusive

**Given** a path with no declaration
**When** it is classified
**Then** it defaults to `machinery`
**And** so a file no declaration claims cannot silently travel into every component

**Given** input reconciliation against the reference application
**When** the gate runs
**Then** a path claimed by no disposition fails
**And** a claim naming a path that does not exist fails

**Given** the disposition question
**When** it is answered
**Then** it answers only whether a path travels
**And** what is substituted inside it is the separate parameter axis

### Story 7.2: A core path carries feature-owned regions by declared markers

As a lead developer,
I want sub-file feature surface removed by declared markers and nothing else,
So that a missed region cannot leave an instrumentor call in a combination whose environment no longer contains it.

**Requirements:** FR-2, FR-28 · AD-24 · SC-2

**Acceptance Criteria:**

**Given** a feature-owned region inside a `core` path
**When** it is delimited
**Then** it uses paired `feature:<name>` / `/feature:<name>` line comments in the file's own comment syntax
**And** every region is declared in the carrier with its path and its feature

**Given** the region-bearing paths known at declaration time, as an open set
**When** they are declared
**Then** they are declared as an open `[[regions]]` array and include `src/config/settings/base.py` (the Celery block at `:296-335`, `REDIS_URL`/`REDIS_SSL` at `:293-294`, and the feature entries in the installed-app lists), `src/config/settings/production.py` (the `CACHES` block at `:31-44` and its import at `:12`), `src/config/settings/local.py` (`:75-80`), `src/config/observability/telemetry.py` (the celery call at `:135` and the redis call at `:137`, each with its import at `:21` and `:24` — **not** `:134-137` as one region, since `:134` and `:136` are core), `src/config/urls.py`, `src/config/startup/stage_one.py`, `pixi.toml` and `component.toml`
**And** the reconciler encodes no fixed count of region-bearing paths

**Given** region reconciliation
**When** the gate runs
**Then** a marker naming an undeclared feature fails, a declared region whose markers are absent from the named file fails, and an unbalanced marker pair fails

**Given** any other sub-file removal mechanism
**When** it is proposed
**Then** it is forbidden — not conditional imports, not settings-module inheritance, not `try/except ImportError`

**Given** the instrumentation packages
**When** a combination is materialized
**Then** `opentelemetry-instrumentation-celery` is present in exactly the combinations that selected background task processing, `opentelemetry-instrumentation-redis` in exactly those that selected the Redis cache
**And** the API, SDK, OTLP exporter, Django, ASGI and psycopg instrumentation packages are present in all six

### Story 7.3: Parameterization is declared as an axis orthogonal to disposition

As a platform engineer,
I want every parameter and its exact substitution sites declared,
So that a value correct for this repository and wrong for any other cannot travel unnoticed.

**Requirements:** FR-24 (parameters), FR-37 · AD-25

**Acceptance Criteria:**

**Given** the carrier
**When** parameters are declared
**Then** `[parameters]` names each parameter, its fixture value, and every exact path and token site it substitutes

**Given** parameter reconciliation
**When** the gate runs
**Then** a declared parameter with no site fails
**And** a site matching no declared parameter fails

**Given** the parameter set
**When** it is enumerated
**Then** it is `sonar-project.properties` (project key), `README.md`, `CHANGELOG.md`, `LICENSE`, `pyproject.toml`, `mkdocs.yml`, and the component name

**Given** the component name
**When** it is substituted
**Then** it is one parameter with several sites — `pixi.toml` `[workspace] name`, `pyproject.toml` `[project] name`, the `[pypi-dependencies]` self-install key, and `[pypi-options] no-build-isolation`

**Given** `src/django_service/`
**When** parameterization is considered
**Then** it is not a parameter
**And** it is a constant, because reusable apps import from it by that name in every deployment

**Given** the hardcoded project key at `sonar-project.properties:6`
**When** it is shipped unparameterized
**Then** nothing fails and every component's metrics merge silently into this project
**And** that is precisely the consequence this story prevents

### Story 7.4: django_service is core in its entirety and the interface mechanism is core with it

As a lead developer,
I want no feature-scoped disposition anywhere inside the base package,
So that a reusable app cannot import a module that exists in six combinations and not the other six.

**Requirements:** FR-1, FR-3 · AD-29 · SC-7 · readiness warning W-1

**Acceptance Criteria:**

**Given** that no source document enumerates which templates, static assets, views and forms constitute the server-rendered UI feature
**When** this story begins
**Then** that surface is enumerated by audit of the existing tree and recorded in the carrier before any file moves
**And** the enumeration distinguishes user-facing surface from `base.html` and the error templates, which stay

**Given** any path inside `src/django_service/`
**When** its disposition is assigned
**Then** it is `core`
**And** a gate test asserts that no `feature:*` disposition applies to any path inside it

**Given** surface that genuinely belongs to the server-rendered UI feature
**When** the UI feature is prepared for extraction
**Then** nothing moves out — the interface mechanism is immovable core (revision 3), so `base.html`, the error templates, form styling, static-file serving and the user profile views all stay
**And** the `home` and `about` demonstration pages are deleted rather than made core
**And** `base.html` carries no hardcoded navigation, its bar rendering the contributed navigation registry instead of literal links
**And** `User.get_absolute_url()` and `LOGIN_REDIRECT_URL` stand unchanged, since `users:detail` and `users:redirect` are now core routes

**Given** `base.html` and the error templates
**When** the UI feature is absent
**Then** they remain
**And** the 403, 404 and 500 pages that extend `base.html` still render

**Given** a combination with the server-rendered UI absent
**When** it runs
**Then** the admin renders, static files serve, the messages framework is available, and template rendering works
**And** what the UI feature removed is the end-user surface and nothing else

**Given** the immovable core
**When** any of the six combinations is inspected
**Then** it declares PostgreSQL as its deployed database, DRF with drf-spectacular, the Django admin, CORS handling, structlog, OpenTelemetry, environment-based configuration, static file serving and a uvicorn/gunicorn process
**And** no feature toggle can be set to a value that removes any of them

### Story 7.5: Object storage attaches an S3-compatible backend with a local substitution

As a lead developer,
I want object storage as a selectable feature that works deployed and locally,
So that the six combinations that select it have both a real backing service and a local story.

**Requirements:** FR-25, FR-28, FR-18 (fifth substitution) · risk R-1

**Acceptance Criteria:**

**Given** the evidence from Story 1.8
**When** the feature is built
**Then** it uses `django-storages` and `boto3` from the approved channel on that evidence
**And** the feature is greenfield: no storage configuration or application code exists today

**Given** a deployed component
**When** storage is configured
**Then** it is configured through Django's storages configuration from environment variables alone
**And** no bucket, endpoint or credential is baked into the image

**Given** a developer with no object store running
**When** the component runs locally
**Then** a filesystem-backed storage backend is configured
**And** the storage API is preserved at every call site

**Given** the local substitution
**When** its limits are documented
**Then** they state that it does not exercise bucket policy, presigned URLs, eventual consistency, multipart upload, or the network failure modes of a remote object store

**Given** user media
**When** scope is assigned
**Then** it is out of scope, because avatars resolve from IdP profile metadata as remote URLs

**Given** a combination that did not select the feature
**When** it is inspected
**Then** no storage configuration, dependency or call site remains

### Story 7.6: Three features are selectable, with the broker constraint and three presets declared

As a lead developer,
I want to select any subset of the three features, with invalid pairings named and presets that do not constrain,
So that the selection surface accepts every legitimate request.

**Requirements:** FR-24, FR-26, FR-27

**Acceptance Criteria:**

**Given** the three features
**When** they are declared
**Then** background task processing, Redis cache, server-rendered UI and object storage are each independently selectable
**And** each is selected or absent, never present-and-disabled

**Given** the broker constraint
**When** the combination space is enumerated
**Then** it is six valid combinations, not eight
**And** background task processing without the Redis cache is the excluded pairing

**Given** the three presets
**When** they are declared
**Then** *API-only*, *Full web app* and *Worker-enabled* set a starting selection and remain fully editable

**Given** a selection such as *API-only plus background task processing plus object storage*
**When** it is requested
**Then** it is accepted
**And** presets do not act as a menu of permitted shapes

**Given** every valid combination
**When** it is requested
**Then** it is reachable without using a preset

### Story 7.7: Every feature's surface is complete and independently removable

As a lead developer,
I want each feature's code, dependencies, settings, templates and tests grouped so the feature can be excluded cleanly,
So that removing a feature is a declared operation rather than an archaeology exercise.

**Requirements:** FR-28 · AD-2 · SC-2

**Acceptance Criteria:**

**Given** any path in the reference application
**When** input reconciliation runs
**Then** every path is claimed by exactly one disposition
**And** removing background task processing is a declared set of paths and regions rather than a manual trace through ten files

**Given** a feature's tests
**When** their disposition is assigned
**Then** they carry the disposition of what they cover, so a feature's tests are `feature:<name>` and are pruned with it

**Given** the immovable-core assertion suite
**When** its disposition is assigned
**Then** it is `core` and is never pruned by any feature

**Given** a tenant application's tests
**When** their location is decided
**Then** they live inside the application, because they must graduate with it

**Given** a feature's code
**When** its imports are inspected
**Then** it never imports another feature's code

### Story 7.8: The orphan detectors exist for all three residue categories

As a platform engineer,
I want every residue category to have a detector,
So that a category with no detector is not a category that ships.

**Requirements:** FR-29 · AD-20 · CG-1 · SC-2

**Acceptance Criteria:**

**Given** coverage measurement
**When** a combination's gate runs
**Then** it includes templates
**And** `COVERAGE_CORE` is pinned to the C trace core so template measurement is real rather than a silent zero

**Given** the declared omit list authored in Story 1.5
**When** this story lands
**Then** it moves into `accelerator.toml` as a closed, carrier-declared surface
**And** the two-way assertion that the effective list equals the declared one is unchanged in meaning

**Given** static assets and settings fragments
**When** residue is detected
**Then** it is detected by checking materialized output against the carrier
**And** any path present that no selected feature claims is a defect

**Given** an orphaned template override
**When** it is introduced deliberately
**Then** the combination's gate fails on the zero-percent coverage signal
**And** the test that proves this runs in Epic 8, where a materialized combination exists to run it against

## Epic 8: Six combinations, proven

A platform engineer updates the base for a Django security release, and the harness reports which of the six combinations broke — before a single lead developer orders it. The load-bearing epic, and the reason phase 1 does not end at the reference application.

### Story 8.1: Six pre-locked environments come from one lock file

As a platform engineer,
I want the three features declared as pixi features in one environments matrix sharing a single solve group,
So that six combinations are not six independent dependency solves testing two different Djangos.

**Requirements:** AD-3 · supports FR-32 · NFR-5 · SC-1

**Acceptance Criteria:**

**Given** the four selectable features
**When** they are declared in `pixi.toml`
**Then** each is a pixi feature
**And** an `[environments]` matrix yields six pre-locked environments from one `pixi.lock`

**Given** all six environments
**When** they are declared
**Then** they share one `solve-group`

**Given** `django-celery-beat`'s `django <6.1` cap
**When** the solve group is absent
**Then** the four Celery combinations resolve a different Django from the other eight
**And** a test asserts that all six resolve the same Django version

**Given** combination *n*'s gate
**When** it runs
**Then** it runs its materialized source under environment *n*
**And** never in an environment fat enough to hide an import it should not have

### Story 8.2: The materializer copies the reference application and prunes by path

As a platform engineer,
I want a materializer that produces a combination's source by removing the paths that combination did not select,
So that the six-combination claim becomes provable before the FreeMarker transition rather than after it.

**Requirements:** FR-30 · AD-2, AD-3

**Acceptance Criteria:**

**Given** a valid combination
**When** it is materialized
**Then** the materializer copies the reference application and removes every path the carrier assigns to a feature the combination did not select
**And** the result is a self-contained source tree

**Given** paths dispositioned `core` or `tenant`
**When** any combination is materialized
**Then** they are present in the output

**Given** the materializer, the carrier and the fixture set
**When** output is produced
**Then** all three are excluded from it

**Given** the reference application
**When** materialization has run
**Then** it remains a real, runnable, gateable Django application throughout

### Story 8.3: The materializer prunes feature-owned regions inside core paths

As a platform engineer,
I want sub-file feature surface removed by its declared markers,
So that a combination does not boot into an `ImportError` from an instrumentor call its environment no longer contains.

**Requirements:** FR-30, FR-28, FR-2 · AD-3, AD-24

**Acceptance Criteria:**

**Given** a `core` path carrying feature-owned regions
**When** a combination that did not select that feature is materialized
**Then** the region between the paired `feature:<name>` / `/feature:<name>` markers is removed
**And** the markers are removed with it

**Given** the three declared region-bearing paths
**When** a combination without background task processing is materialized
**Then** the Celery block in `src/config/settings/base.py`, the Celery instrumentor call in `src/config/observability/telemetry.py`, and the `worker` and `beat` tasks in `pixi.toml` are all absent

**Given** a materialized combination
**When** it boots
**Then** no instrumentor is invoked whose package that combination's environment does not contain

**Given** any other sub-file removal mechanism
**When** the implementation is reviewed
**Then** none is used — not conditional imports, not settings-module inheritance, not `try/except ImportError`

### Story 8.4: Materialization is deterministic and equivalent to the reference application

As a platform engineer,
I want byte-identical output from identical selections,
So that a materialized combination is a reproducible artifact rather than a fresh result each run.

**Requirements:** FR-30 · AD-3 · NFR-5

**Acceptance Criteria:**

**Given** the same selections
**When** materialization runs twice
**Then** the two trees are byte-identical
**And** a gate test asserts it

**Given** the all-features-selected combination
**When** it is materialized
**Then** its output is equivalent to the reference application

**Given** any source of nondeterminism — iteration order, timestamps, or filesystem ordering
**When** output is written
**Then** none reaches the tree

### Story 8.5: The materializer refuses invalid combinations

As a lead developer,
I want an invalid pairing refused with its reason,
So that I never receive a component that cannot start.

**Requirements:** FR-34, FR-26

**Acceptance Criteria:**

**Given** a request for background task processing without the Redis cache
**When** materialization is attempted
**Then** it is refused before any source is produced

**Given** the refusal
**When** it is reported
**Then** it names the broker constraint
**And** does not fail generically

### Story 8.6: The fixture set covers every parameterized value

As a platform engineer,
I want test values for every parameter the enterprise developer portal would supply,
So that a parameter added to the order surface breaks materialization instead of silently defaulting.

**Requirements:** FR-31 · AD-25

**Acceptance Criteria:**

**Given** the fixture set
**When** it is authored
**Then** it covers every parameterized value declared in Story 7.3, including the component package name and the code-quality project key
**And** it covers the four feature booleans

**Given** a parameter with no corresponding fixture
**When** materialization runs
**Then** it fails
**And** never emits a default

**Given** the portal's order-surface field list does not exist yet
**When** the fixture set is scoped
**Then** it covers the declared parameters and the four feature booleans
**And** the missing field list is recorded as an open item owned by the portal team

### Story 8.7: Output reconciliation proves the accelerator's machinery never reaches a component

As a lead developer,
I want every path in a materialized tree to have a legal reason to be there,
So that the accelerator's own tooling and planning artifacts cannot travel into the component I ordered.

**Requirements:** FR-37, FR-28 · AD-2 · NFR-8 · SC-2

**Acceptance Criteria:**

**Given** each materialized tree
**When** output reconciliation runs
**Then** every path is either a copied path with a travelling disposition or a declared generated artifact
**And** nothing else is permitted

**Given** the accelerator's machinery
**When** output is produced
**Then** `_bmad/`, `_bmad-output/`, `.agents/`, `.bmad-loop/`, `.claude/`, the materializer, the carrier and the fixture set are all absent

**Given** `.github/` and `docs/`
**When** they are dispositioned
**Then** they split rather than travelling wholesale: only the component's own pipeline travels, and only documentation describing how to work on any component travels

**Given** directory-level granularity
**When** it is considered
**Then** it is insufficient and is not used, because `src/config/`, `tests/`, `pixi.toml` and `pixi.lock` each contain both core and feature-owned content

**Given** `src/config/celery_app.py`
**When** a combination without background task processing is materialized
**Then** it is absent

**Given** the dependency manifest
**When** the six combinations are compared
**Then** it differs in five of the six

**Given** `COVERAGE_CORE`
**When** a combination is materialized
**Then** the setting travels with it

### Story 8.8: Every valid combination passes the full gate against PostgreSQL

As a platform engineer,
I want all six combinations gated against PostgreSQL,
So that a defect is found before the first lead developer to order that combination finds it.

**Requirements:** FR-32, FR-29 · AD-18, AD-20 · CG-1 · SC-1, SC-2

**Acceptance Criteria:**

**Given** all six valid combinations
**When** the harness runs
**Then** each is materialized and put through tests, coverage at or above ninety percent including templates, strict type checking, lint and build, against PostgreSQL

**Given** a failure in any one combination
**When** the run completes
**Then** the whole run fails
**And** there is no partial pass

**Given** an orphaned template override introduced deliberately into a combination
**When** that combination's gate runs
**Then** it fails

**Given** the coverage floor before the materializer has reported all six numbers
**When** materialized-combination gates run
**Then** the floor is advisory and the numbers are published as an artifact
**And** the exit condition is that first full report

**Given** that report has been produced
**When** any later gate runs
**Then** the floor is hard everywhere
**And** a combination that misses is answered with tests rather than with a lower floor

### Story 8.9: Verification is reduced on pull request, full on merge, and any bound is reported

As a platform engineer,
I want a pinned reduced set on pull requests and the full set on merge, with exclusions reported,
So that CI cost is bounded without a truncated set reading as full coverage.

**Requirements:** FR-35 · AD-19 · CG-2 · SC-1

**Acceptance Criteria:**

**Given** a pull request
**When** the harness runs
**Then** it runs an all-pairs subset
**And** reports which combinations it did not cover

**Given** a merge to `main`
**When** the harness runs
**Then** it runs all six plus the smoke-check level

**Given** several distinct sets satisfy the all-pairs predicate
**When** the subset is chosen
**Then** it is pinned as data in the carrier
**And** a gate test asserts that the pinned set actually satisfies the predicate

**Given** any run using a reduced set
**When** it reports
**Then** it states the reduction and the combinations not covered
**And** no reduction is ever silent

**Given** the policy beyond six combinations
**When** it is documented
**Then** it states exhaustive verification while the space stays small, and all-pairs coverage plus unconditional verification of every preset past roughly thirty-two valid combinations

### Story 8.10: Every valid combination passes the local smoke check

As a lead developer,
I want every combination proven to boot and authenticate with nothing installed,
So that the local-runnability claim covers the combination I actually ordered.

**Requirements:** FR-33, FR-1, FR-3 · AD-30 · SC-4, SC-7

**Acceptance Criteria:**

**Given** each of the six combinations
**When** the smoke check runs with no database, cache, broker, object store or identity provider available
**Then** the process boots, readiness returns 200, a persona completes an interactive sign-in and reaches a rendered admin index, one Bearer request passes through the real authentication class, and one rendered 404 is produced

**Given** a combination in which the Django admin is unreachable
**When** the smoke check runs
**Then** it fails

**Given** the database backend and the authentication mode
**When** the combination space is counted
**Then** neither is treated as a feature toggle
**And** the space stays at six

**Given** the immovable-core assertion suite
**When** any combination's gate runs
**Then** it runs inside that gate
**And** it is never pruned by any feature, because it is what defends the claim that the core still works after an excision

### Story 8.11: Materialized output carries the provenance stamp

As a platform engineer,
I want every materialized combination to record what produced it,
So that "which components predate this change" has an answer.

**Requirements:** FR-36 · AD-17 · NFR-5

**Acceptance Criteria:**

**Given** materialized output
**When** it is produced
**Then** `.accelerator.json` is written at its root carrying the accelerator version, the source ref and the full order values

**Given** the stamp
**When** it is serialized
**Then** keys are sorted
**And** it carries no timestamp, because that would break determinism and git already records when

**Given** output reconciliation
**When** the stamp is classified
**Then** it is a declared generated artifact
**And** it is never hand-edited

**Given** the reference application
**When** it is inspected
**Then** it carries no stamp

**Given** an external process
**When** it enumerates components by version
**Then** the stamp's location and format are stable enough to permit it

## Epic 9: Build on the base — the extension model

A team's own applications live alongside the base rather than inside it, and an application that proves useful twice graduates to the approved channel without changing its import path or anyone's `INSTALLED_APPS`.

Last because it depends on the base having a declared surface, the tenant space having a disposition, and the refusals existing to iterate over what an adopted app contributes. Nothing here forces rework: Epic 4 placed stage 1 as the last statement of every settings module, which is exactly what makes the composition step land before it.

### Story 9.1: The base declares a guaranteed surface and a version

As a developer of a reusable app,
I want an explicit, versioned surface I may depend on,
So that a routine tidy-up inside the base does not become an estate-wide break.

**Requirements:** FR-51 · AD-5, AD-29

**Acceptance Criteria:**

**Given** the base package
**When** its surface is declared
**Then** the carrier enumerates the guaranteed surface explicitly
**And** anything inside `django_service` not enumerated is internal and may change without a version bump

**Given** the guaranteed surface
**When** any of the six combinations is inspected
**Then** it is present in all six
**And** no feature selection may remove part of it

**Given** `django_service.__api_version__`
**When** it is declared
**Then** it is a single integer bumped by hand on any breaking change and on the removal of any guaranteed surface

**Given** a breaking change
**When** it is identified
**Then** moving a module within the guaranteed surface, changing `AUTH_USER_MODEL`, or renaming a guaranteed setting each qualifies

**Given** the base package name
**When** it is materialized
**Then** it is `django_service` in every component and is never parameterized

**Given** the mapper epoch table from Story 2.5
**When** its surface is classified
**Then** it is internal
**And** adding it is not an API version bump

### Story 9.2: The tenant space is a path root that is never judged

As a lead developer,
I want one declared location for the applications my team owns,
So that my own code is neither pruned nor reported as an orphan.

**Requirements:** FR-52 · AD-6, AD-7

**Acceptance Criteria:**

**Given** `src/django_apps/`
**When** it is created
**Then** it contains no `__init__.py`
**And** an application at `src/django_apps/billing/` is imported and installed as `billing`, unqualified

**Given** the tenant disposition
**When** the materializer runs
**Then** it neither prunes nor reports the tenant space
**And** a path there is never an orphan and never excluded as unclaimed

**Given** the single import-root declaration site from Story 1.6
**When** the second root is added
**Then** it is added at that same site through the `sources` remapping
**And** no second declaration site is created

**Given** a component with applications of its own
**When** it runs its gate
**Then** it passes the same gate as one without

**Given** the tenant-space location
**When** it is declared
**Then** it is named in the carrier

### Story 9.3: Dependency direction across the three territories is enforced

As a platform engineer,
I want the layering enforced rather than documented,
So that a base that depends on what is built on it is caught by the gate.

**Requirements:** AD-4

**Acceptance Criteria:**

**Given** a tenant application
**When** its imports are checked
**Then** it may import `django_service`

**Given** `django_service`
**When** its imports are checked
**Then** it never imports a tenant application

**Given** `config`
**When** its imports are checked
**Then** it may import `django_service`
**And** it reaches tenant applications only through the settings composition step, never by direct import

**Given** a violation of any of the above
**When** the gate runs
**Then** it fails

### Story 9.4: A reusable app contributes configuration additively on a closed surface

As a lead developer,
I want an adopted application to add configuration and never change it,
So that installing a package cannot give it authority over every request.

**Requirements:** FR-54 · AD-8, AD-26

**Acceptance Criteria:**

**Given** an adopted application
**When** it ships a contribution
**Then** it ships a declared contribution module
**And** the composition step merges contributions from the `component.toml` adopted-application list

**Given** a contribution introducing a new key
**When** composition runs
**Then** it succeeds

**Given** a contribution touching a key the component already defines
**When** composition runs
**Then** it raises `ImproperlyConfigured` at startup

**Given** a contribution to an ordered sequence such as `INSTALLED_APPS` or `DATABASE_ROUTERS`
**When** composition runs
**Then** it appends in adopted-application-list order
**And** no application can place itself ahead of the base or of another application

**Given** the contributable surface
**When** it is declared
**Then** it is closed and enumerated in the carrier by explicit key, never by namespace
**And** it comprises additional `DATABASES` entries and their routers, `INSTALLED_APPS` entries, the application's own namespaced settings, and named non-global DRF and Celery keys

**Given** a global-default key
**When** contribution is attempted
**Then** `DEFAULT_AUTHENTICATION_CLASSES`, `DEFAULT_PERMISSION_CLASSES`, `MIDDLEWARE` and `AUTHENTICATION_BACKENDS` are each refused
**And** the refusal holds whether or not the base already sets them

**Given** the permitted-key list and the Story 4.6 allowlist
**When** they are declared
**Then** they are one declaration

**Given** a contribution naming a feature the combination did not select
**When** settings are imported
**Then** it is refused
**And** an application cannot contribute `CELERY_BEAT_SCHEDULE` into a component with no Celery and have its scheduled work silently never run

### Story 9.5: A reusable app graduates without changing its import path

As a developer of a reusable app,
I want my application importable by the same name in the tenant space and once installed from the channel,
So that graduating it breaks nothing in the components that adopt it.

**Requirements:** FR-53 · AD-6, AD-8

**Acceptance Criteria:**

**Given** the same application
**When** it lives in the tenant space and when it is installed from the approved channel
**Then** it is importable by the same name in both residencies

**Given** graduation
**When** it occurs
**Then** it requires no change to the installed-application list, imports, or migration references of any component that adopts it

**Given** adoption
**When** it occurs
**Then** it is explicit: a `pixi.toml` line and a `component.toml` entry

**Given** installation
**When** a package is installed
**Then** nothing self-registers
**And** entry-point discovery is forbidden, because an in-repo application has no distribution metadata and the two residencies would diverge

**Given** a reusable application
**When** a component may depend on it
**Then** it must have reached the approved channel first

### Story 9.6: Base compatibility is declared and checked at adoption

As a lead developer,
I want an incompatible adoption to fail my gate,
So that a base that moved beneath an application is found before production.

**Requirements:** FR-56 · AD-5

**Acceptance Criteria:**

**Given** a reusable application
**When** it declares its supported base range
**Then** it declares `MIN <= v <= MAX` integers in its contribution module
**And** not in package metadata, because an in-repo application has no distribution metadata

**Given** the adoption gate test
**When** it runs
**Then** it asserts compatibility from that constant
**And** it runs identically in both residencies

**Given** an application adopted outside the supported range
**When** the component's gate runs
**Then** it fails

### Story 9.7: A contributed backing service inherits the local development contract

As a developer working on a generated component,
I want an adopted application's own database to inherit every guarantee the component's own database has,
So that adopting an application does not cost me the local development contract.

**Requirements:** FR-55 · AD-9, AD-22, AD-28

**Acceptance Criteria:**

**Given** an application contributing a database
**When** it contributes
**Then** it must also contribute a router that answers only for its own labels and returns `None` otherwise

**Given** a component that adopts an application with its own database
**When** it runs locally with nothing installed
**Then** it still starts, serves and authenticates a persona
**And** the local substitution is applied automatically by the base rather than arranged by the application

**Given** a deployed component whose contributed database has fallen back to the local substitution
**When** it starts
**Then** it refuses

**Given** unapplied migrations on a contributed database
**When** a serving process starts
**Then** it refuses exactly as it does on the component's own database

**Given** readiness
**When** it evaluates a contributed backing service
**Then** it treats it as required unless `component.toml` declares it optional

**Given** release-stage migration
**When** it is declared
**Then** `component.toml` declares one step per database
**And** the deployment repository does not have to infer how many there are
