# Epic 4 Context: Local convenience cannot reach deployment — the refusal contract

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

The platform group can state, and prove, that no deployed component authenticates outside the identity provider — because every forbidden configuration refuses at startup with `ImproperlyConfigured`, and a credential path someone adds next year fails the build rather than shipping. This is the product's highest-consequence surface: the entire separation between a component in local development and a deployed one rests on these startup refusals, and it comes after Epics 2 and 3 because the paths it forbids are the ones those epics create. The epic delivers one refusal module with two evaluation stages, nine conditions covering fourteen distinct forbidden states, predicates that resolve objects rather than match strings, a test per forbidden state, and an allowlist over the authentication surface that inverts the denylist so a path invented later cannot slip through review.

## Stories

- Story 4.1: The refusal contract has one home and two evaluation stages
- Story 4.2: Five unconditional refusals evaluate at settings import
- Story 4.3: Three unconditional refusals evaluate at serving-process startup
- Story 4.4: Two feature-scoped refusals apply only where their feature exists
- Story 4.5: Every refusal is tested as a refusal
- Story 4.6: The authentication surface matches an allowlist exactly

## Requirements & Constraints

**The canonical count is nine conditions — seven unconditional, two feature-scoped — over fourteen distinct forbidden states.** The source documents are arithmetically inconsistent (one says seven then lists eight; an architecture decision adds a tenth that appears in no list). The reconciled table below is authoritative for this epic; one condition may cover several states, each tested separately.

| # | Condition | Stage | States |
|---|---|---|---|
| 1 | The sqlite backend is reached | 1 | 1 *(already built in the deployed settings module)* |
| 2 | A local credential path is live in settings | 1 | 4 — `ModelBackend` in the authentication backends; a non-empty account login-methods setting; admin-force-allauth not true; the static-token app installed or its DRF authentication class in the defaults |
| 3 | Telemetry is disabled by environment variable | 1 | 1 |
| 4 | The JWKS trust anchor is not derived from the configured IdP issuer | 1 | 1 |
| 5 | The claims contract is unusable | 1 and 2 | 2 — unconfigured identity-key claim, group-claim name or designated staff group (stage 1); a designated group absent from the database (stage 2) |
| 6 | A forbidden credential route is reachable in the resolved URLconf | 2 | 2 — the token-minting route; the local sign-in route |
| 7 | Unapplied migrations on a serving process | 2 | 1 |
| 8 | *(only where the Redis cache feature is selected)* an in-process cache backend is configured | 1 | 1 |
| 9 | *(only where background task processing is selected)* eager task execution is enabled | 1 | 1 |

- Three of the unconditional conditions are **not** credential bypasses and must not be filed as such — the trust anchor (a component that verifies signatures correctly against the wrong signer), the claims contract (a component that authenticates correctly and cannot decide what anyone may do), and unapplied migrations (a component serving against a schema it does not recognize). No check phrased as "is a bypass enabled" sees any of them.
- The unapplied-migrations condition applies to serving processes only. Evaluating it for every process deadlocks the release stage, because running migrations is the one action that clears it.
- Refusals raise; none is softened into a warning that logs and continues. A refusal that logs and continues is exactly how local credentials reach production.
- Startup must fail fast and cheaply: the checks make no network call and no query beyond migration state, so their cost is irrelevant to startup time.
- The allowlist covers `AUTHENTICATION_BACKENDS`, the DRF default authentication classes, and only the route prefixes the component itself owns for authentication, admin login and token issuance. Business routes a developer adds are out of scope — an allowlist over every route breaks on the first feature written and gets deleted within a week. Adding a credential path must require editing the allowlist in the same change; that edit is the human decision point.
- Success is measured as: every one of the nine conditions has a test that configures the forbidden state and asserts refusal, and the authentication surface matches its allowlist exactly.

## Technical Decisions

- **One module, `src/config/startup/`, holds both stages and the allowlist.** Not split across the deployed settings module — the failure mode it most needs to catch is a component pointed at the local settings module, and a guard placed behind the door it guards cannot fire.
- **Stage 1 is the last statement of every *leaf* settings module** (`local.py`, `production.py`, `test.py`). `base.py` must not call it: `base.py` is star-imported and itself configures four forbidden states, so a call there fires before the leaf composes and destroys the after-composition property the rule exists to guarantee. A gate test asserts both halves — each leaf ends with the call, and `base.py` contains none. Being after composition is what makes iteration over every configured database reachable, for both the migrations and sqlite conditions.
- **Stage 2 is owned by the `AppConfig.ready()` of one named immovable-core app** inside the base service package, because Django's own system-check framework does not run under a gunicorn/uvicorn serving process — the only path that matters in deployment. No adopted app may precede that app in `INSTALLED_APPS`; a gate test asserts the ordering.
- **Predicates resolve objects, never strings.** The forbidden-route conditions resolve the URLconf and refuse any route whose view callable belongs to the forbidden module, so renaming a route or remounting it under another prefix cannot evade them — a route named for a local persona login mounted under the allauth prefix must still be caught.
- **Locality is read from the environment and fails closed** — absent or unrecognized means deployed — and is never inferred from which settings module loaded. Note that the epics file still describes the earlier per-task form of this declaration; the resolved decision, already delivered in Epic 3, places it once in the dev environment's activation env. Consume the delivered locality reader; do not write a second one.
- **The two feature-scoped refusals are delimited as feature-owned regions** by paired `feature:<name>` / `/feature:<name>` line comments — the only permitted sub-file removal mechanism. They must not be written as unconditional code guarded by a runtime flag.
- **The allowlist and the contributable-configuration surface are one declaration**, authored here in `src/config/startup/` as the authoritative copy and extended (never forked) by the extension-model epic. The declarative carrier mirrors it with a gate test asserting equality; the carrier cannot be the runtime authority, because it never travels into a materialized component while this rule must execute there.

## Cross-Story Dependencies

- The whole epic depends on Epics 2 and 3: the claims contract and designated-group provisioning, the JWKS trust anchor and Bearer path, the static-token surface removal, the locality declaration, and the local sign-in module whose view callable stage 2 resolves.
- Story 4.1 establishes the module, the two stages and the locality read that Stories 4.2–4.4 register conditions into; 4.5 tests all fourteen states and 4.6 adds the allowlist, so both follow the conditions they cover.
- The unapplied-migrations refusal is implemented here but the release-stage, no-entrypoint-migrates contract belongs to the deployment-interface epic. The seeding task's deployed-environment refusal and the local sign-in route's guard are this epic's obligations, referenced forward from Epic 3.
- The feature-region markers written here are declared in the carrier in the feature-model epic, and the allowlist declaration is extended by the extension-model epic. Author both in one place now so those moves change no assertion's meaning.
- Known residual risk to carry, not solve: a serving process started outside the declared process task does not fire the migrations refusal — the accepted price of process type failing open.
