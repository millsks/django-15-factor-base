---
title: "Edge-Case Review: django-15-factor-base PRD"
status: draft
created: 2026-08-14
reviewer: edge-case hunter (exhaustive path enumeration)
---

# Edge-Case Review — PRD + Addendum

## Verdict

The document is unusually disciplined about the paths it names, and most of the branches it *does* enumerate are genuinely closed — the broker constraint, the two conditional refusals, revocation-on-reauthentication, lazy JWKS, the liveness/readiness asymmetry, and the orphan detector all survive enumeration. What it does not survive is the second-order crossings: paths that exist only where two of its own mechanisms meet. Twenty-three unresolved branches are reported below. Four are critical, and each of the four is a case where one requirement's correct behaviour makes another requirement's correct behaviour impossible: the environment declaration of FR-12 must be committed to satisfy UJ-2 and must not be committed to satisfy FR-12; the unapplied-migration refusal of FR-13 blocks the very `migrate` process FR-40 requires; FR-8 mandates one mapper but never one identity key, so the two flows can resolve the same human to two Django users; and FR-36 lists `pixi.toml`/`pixi.lock` as *kept verbatim* while FR-2 and FR-27 require their contents to differ in every one of the twelve combinations. A fifth structural gap is quieter but wide: **object storage is a selectable feature with no local substitution, no refusal, and no functional requirement of its own** — it appears in the feature model and then never again.

---

## Structure 1 — The Combination Space (all 16 enumerated)

Notation: **T** = background task processing, **R** = Redis cache, **U** = server-rendered UI, **S** = object storage.

| # | T | R | U | S | Valid | Requirements that are not well-defined for it |
|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 0 | 0 | valid | FR-28 (template coverage with no project templates) — F-1.4 |
| 2 | 0 | 0 | 0 | 1 | valid | F-1.1 (object storage), F-1.4 |
| 3 | 0 | 0 | 1 | 0 | valid | — |
| 4 | 0 | 0 | 1 | 1 | valid | F-1.1 |
| 5 | 0 | 1 | 0 | 0 | valid | F-1.3 (no `REDIS_URL` in deployment), F-1.4 |
| 6 | 0 | 1 | 0 | 1 | valid | F-1.1, F-1.3, F-1.4 |
| 7 | 0 | 1 | 1 | 0 | valid | F-1.3 |
| 8 | 0 | 1 | 1 | 1 | valid | F-1.1, F-1.3 |
| 9 | 1 | 0 | 0 | 0 | **invalid** — broker constraint | refused at selection (FR-25, FR-33) ✓ |
| 10 | 1 | 0 | 0 | 1 | **invalid** | refused ✓ |
| 11 | 1 | 0 | 1 | 0 | **invalid** | refused ✓ |
| 12 | 1 | 0 | 1 | 1 | **invalid** | refused ✓ |
| 13 | 1 | 1 | 0 | 0 | valid | F-1.3 (no broker URL), F-1.4, F-4.1 (beat) |
| 14 | 1 | 1 | 0 | 1 | valid | F-1.1, F-1.3, F-1.4, F-4.1 |
| 15 | 1 | 1 | 1 | 0 | valid | F-1.3, F-4.1 |
| 16 | 1 | 1 | 1 | 1 | valid | F-1.1, F-1.3, F-4.1; also the "reference application" combination — F-5.4 |

Counts that follow from the table and are used below: **T is present in 4 of 12 valid combinations, absent in 8. R is present in 8, absent in 4. Each of U and S is present in 6.**

### F-1.1 — Object storage has no local substitution and no deployed refusal — **HIGH**

**Path.** Any combination with S=1 (combos 2, 4, 6, 8, 14, 16), run under the local development contract; and the same combinations deployed with no bucket configured.

**Why unhandled.** §4.4 states "Each deployed dependency has a local substitution designed as such," and the Glossary fixes the set at exactly four: sqlite, in-memory cache, eager task execution, local personas. Object storage is a deployed backing service (§12, factor 4 names it explicitly) and it has none. FR-18's consequence list enumerates what need not be running locally — "no database, cache, broker, or identity provider" — and omits object storage entirely. This leaves three mutually exclusive readings and the PRD picks none: (a) S=1 combinations require a real object store to run locally, which contradicts FR-18 and SC-4 ("*every* valid combination"); (b) a fifth substitution exists — local filesystem storage — which CG-4 forbids outright; (c) object storage is selected but never exercised, which contradicts §6.1 ("all present and exercised") and would make it invisible to the FR-28 coverage gate. Compounding this, no refusal condition in FR-13 or FR-14 covers a *deployed* S=1 component that has fallen back to filesystem storage — a state that violates NFR-3 (statelessness) and FR-38 (read-only root filesystem) and is precisely the class of local-convenience-reaching-deployment the contract exists to catch. Object storage receives no functional requirement of its own anywhere in §4.

**Cite.** §4.4 description; Glossary "Substitution"; FR-18; FR-13; FR-14; CG-4; SC-4.

**Fix.** Add an FR under §4.4 naming the object-storage local substitution and its bounded status (recommended: the storage backend is the *same* API pointed at a local path, declared as the fifth substitution with CG-4 amended to "the five substitutions are closed" — or explicitly state that S=1 combinations run locally with storage calls unexercised and say what the smoke check asserts). Add a conditional refusal to FR-14: *where object storage is selected, a non-remote storage backend → refusal*, which restores the one-substitution-one-refusal invariant §4.4 and CG-4 both rely on.

### F-1.2 — FR-43's combination arithmetic is inverted — **LOW**

**Path.** The justification for session pruning being an admin process.

**Why unhandled.** FR-43 states "background task processing exists in only eight of the twelve combinations, and a component whose session table grew without bound in the other four." The table above shows the opposite: T=1 in **4** of 12, T=0 in **8**. The requirement's conclusion is unaffected (it is in fact *better* supported), but downstream epics that derive per-process work estimates from stated counts will be wrong by a factor of two. §4.1's description has a related imprecision — "will ship dependencies that four of the twelve valid combinations cannot use" is true of the Redis instrumentor but the Celery instrumentor is unusable in eight.

**Cite.** FR-43 consequence 2; §4.1 description ¶2.

**Fix.** FR-43: "background task processing exists in only four of the twelve combinations, and a component whose session table grew without bound in the other eight." §4.1: "dependencies that four or eight of the twelve valid combinations cannot use, depending on the instrumentor."

### F-1.3 — A deployed component with a feature selected but its backing service unconfigured is reachable and unforbidden — **MEDIUM**

**Path.** Combos 5–8, 13–16 deployed with no `REDIS_URL`; combos 13–16 deployed with no broker URL; combos with S=1 and no bucket.

**Why unhandled.** The refusal contract catches the *substitution being active* (in-process cache, eager execution) but not the *service being absent*. A T=1 component deployed with eager execution correctly disabled and no broker URL configured passes all eight conditions, boots, serves, and silently accepts tasks that are never dispatched. This is the same failure shape FR-25 refuses at selection time — "a component that cannot start" — arriving instead as a component that starts and does nothing. §4.3's framing ("a component that did not select Redis legitimately falls back") covers the R=0 case but says nothing about R=1 with no endpoint.

**Cite.** FR-14; §4.3 description ¶2; FR-25.

**Fix.** Extend FR-14 with a third and fourth conditional pair: *where a feature that attaches a backing service by environment variable is selected, an unset endpoint for that service → refusal*. Stated generically it covers Redis, broker, and object storage in one clause and keeps the one-refusal-per-substitution symmetry.

### F-1.4 — The orphan detector's premise is undefined in combinations with no project templates — **MEDIUM**

**Path.** Combos 1, 2, 5, 6, 13, 14 (U=0), which after FR-3's removal of "form styling, page templates, and user-facing views" may contain zero project-owned templates.

**Why unhandled.** FR-28 requires "Coverage measurement includes templates in every combination's gate run" and asserts that a deliberately introduced orphaned template fails that combination's gate. In a combination whose project template set is empty, template coverage is either vacuously 100% or the measurement errors on an empty set — and the PRD does not say which, nor whether the FR-28 fault-injection test is expected to run in all twelve combinations or only where templates exist. UJ-3's climax is specifically the no-cache-no-UI combination failing on a leftover fragment, so this is the exact combination the journey leans on.

**Cite.** FR-28; FR-3; UJ-3.

**Fix.** State in FR-28 whether the template-coverage assertion is per-combination-unconditional or conditional on a non-empty template set, and specify that the fault-injection test runs in at least one U=0 combination.

---

## Structure 2 — The Refusal Contract (8 conditions × 12 combinations)

Cross-product result: the six unconditional conditions are meaningful in all twelve — none is vacuous. The two conditional ones are correctly scoped in *direction* (see F-2.6 for a reachability problem with one of them). The findings are about the mechanism's own edges.

### F-2.1 — The local declaration must be committed to satisfy UJ-2 and must not be committed to satisfy FR-12 — **CRITICAL**

**Path.** A fresh clone, no environment set, `<one command>` (UJ-2) → FR-12 fails closed → treated as deployed → sqlite reached → refusal. The component does not start. Conversely: the declaration is committed to the repository so the clone works → it is materialized into every component (FR-36 keeps the repository's configuration) → it is present in the built image → every deployed component declares itself local → **all six unconditional refusals are disabled in production.**

**Why unhandled.** FR-12 is explicit that "Local development is the case that must declare itself," and equally explicit that absent means deployed. It never says *where the local declaration lives*. Every available home is wrong in one of the two directions: an uncommitted `.env` breaks UJ-2's "clones, runs one command, and the component serves" and FR-18's "nothing installed"; a committed default file, a pixi task environment block, or a settings-module constant all travel into the component and then into the image unless something excludes them, and FR-36's strip list does not name any such artifact. This is structurally identical to the development-keypair hazard FR-20's note calls out — one wrong file in a template is shared by every component the accelerator ever produces — but for the keypair the PRD supplies the mechanism (generated on demand, gitignored, in the strip list) and for the declaration it supplies none.

**Cite.** FR-12 consequence 2; FR-18; UJ-2; FR-36; NFR-7.

**Fix.** Add a consequence to FR-12: the local declaration is set by the development task runner (pixi task environment) and never by a file that can be committed or copied into an image; and add an explicit consequence that the built image is asserted, by test, not to carry the local declaration by any route. Add the artifact to FR-36's strip list.

### F-2.2 — The unapplied-migration refusal blocks the migration process itself — **CRITICAL**

**Path.** Release stage. `manage.py migrate` runs against a database with unapplied migrations — which is the only state in which it is ever run.

**Why unhandled.** FR-12 requires the contract to be "evaluated by shared code that every settings module imports" and states "No settings module can skip the contract by not being loaded." FR-13 makes "unapplied migrations exist → refusal" unconditional. `manage.py migrate` loads a settings module. Therefore the migration command evaluates the contract, finds unapplied migrations by construction, raises `ImproperlyConfigured`, and exits — the release-stage step FR-40 requires can never succeed in a deployed environment. The same reasoning applies to any one-off admin process run before migration completes, and to FR-43's session-pruning process if it is ever scheduled against a pending schema. Nowhere does the PRD carve management commands out of the contract, and doing so casually would reopen the FR-12 hole (a component could be started via a management command to evade the checks).

**Cite.** FR-12 consequence 1; FR-13 consequence 3; FR-40; FR-43.

**Fix.** State the evaluation *point*, not just its location: the contract is evaluated at server startup (the WSGI/ASGI application factory and the process entrypoints named in FR-39), not at settings import. Then add a consequence to FR-13: the migration condition is evaluated only on serving process types; `migrate` and other release-stage one-off processes are exempt from that single condition and from no other. Add a test that a management command runs against a pending schema and that a `web` process does not.

### F-2.3 — The startup migration query turns a database outage into a boot crash loop, contradicting FR-41's own argument — **HIGH**

**Path.** Deployed component, database briefly unreachable, a replica restarts (or the platform scales up) during the outage.

**Why unhandled.** NFR-1 concedes that the eight checks include "a query… [for] the migration state." When the database is unreachable that query does not return a clean "unapplied migrations exist" — it raises a connection error or hangs for the driver's connect timeout. The PRD never says what the component does in that case: refuse (`ImproperlyConfigured`), retry, or propagate the driver error. Any of the three produces exactly the pathology FR-41 spends a paragraph forbidding for liveness — "a brief database outage [becomes] a crash loop… they restart into the same unreachable database" — except at startup, where readiness cannot rescue it because the process never binds. A slow-but-reachable database creates the second half of the same problem: startup exceeds the liveness threshold and the platform kills a healthy process, and the health contract (FR-41) names only two endpoints, with no startup probe.

**Cite.** NFR-1; FR-13 consequence 3; FR-41 consequences 1–2.

**Fix.** Add a consequence to FR-13: an *unreachable* database at startup is distinguished from *unapplied migrations* — the former is a bounded retry with a stated ceiling, then exit non-zero, and never an `ImproperlyConfigured`. Add a third health endpoint (startup) to FR-41, or state that liveness returns 200 as soon as the process binds and before the contract completes, and say which.

### F-2.4 — One gate run must satisfy two contradictory values of the deployed/local declaration — **HIGH**

**Path.** `pixi run cov` in a materialized combination: FR-16 requires tests that configure the forbidden state and assert refusal (requires *deployed*); FR-19 and FR-20 require persona seeding and a locally minted token to work (requires *local*); FR-31 requires the whole run against PostgreSQL.

**Why unhandled.** FR-12 states the declaration is "read from the environment," which for a Django process normally means read once at settings import. If it is read once, the two halves of the suite cannot both run in one process, and the PRD's gate is a single sequence. If it is re-read per evaluation so tests can override it, then FR-12's guarantee weakens — an in-process mechanism that can flip the declaration is a mechanism a future code path can flip too, which is the hole FR-12 exists to close. The PRD never resolves the tension, and it is on the critical path for SC-1 and SC-5 both being provable by the same run.

**Cite.** FR-12; FR-16; FR-19; FR-20; FR-31; SC-1; SC-5.

**Fix.** State that refusal tests execute the contract as a pure function over an explicit configuration mapping (constructed state in, `ImproperlyConfigured` out) rather than by mutating process environment, and that the ambient declaration is read exactly once per process. That makes FR-16 satisfiable without weakening FR-12.

### F-2.5 — The JWKS trust-anchor condition has no decision procedure, and may be unreachable as written — **HIGH**

**Path.** Any deployed component; the condition "The JWKS trust anchor is not the configured IdP → refusal."

**Why unhandled.** The PRD never says how the check decides. The obvious implementation — fetch the issuer's discovery document and compare its `jwks_uri` to the configured one — is forbidden by NFR-1 ("no network call") and by FR-5/FR-23 (nothing reaches the IdP at boot). That leaves a lexical comparison of two environment values, which the PRD does not state and which has its own boundary cases: is a JWKS URL on the issuer's host but a different path an anchor mismatch? Is `file://` or a filesystem path the only forbidden form? §4.3 says the condition catches "a component… anchored to a key that was generated onto a developer's laptop," and FR-13's out-of-scope note says it catches "a component pointed at a local JWKS location by environment variable, with no key file present at all" — both descriptions of intent, neither a rule. Worse, there is a **forbidden-but-unreachable** reading: if the component derives its JWKS location from the issuer rather than accepting a separate variable (the normal OIDC design, and what FR-5's "the IdP's JWKS endpoint" implies), then no configuration can make the anchor differ from the issuer, the condition can never fire, and FR-16's mandatory test for it cannot construct the forbidden state.

**Cite.** FR-13 consequence 5 and its Out of Scope; NFR-1; FR-5; FR-23; FR-16.

**Fix.** State that the JWKS location is an independent configuration value (so the mismatch state exists) and give the rule: refusal when the configured JWKS location's scheme is not `https`, or its origin does not match the configured issuer's origin. Both are lexical and satisfy NFR-1.

### F-2.6 — The in-process-cache conditional refusal is forbidden but arguably unreachable — **MEDIUM**

**Path.** Combos 5–8, 13–16 (R=1), deployed, cache backend in-process.

**Why unhandled.** §4.3 says "production settings hardcode the Redis cache backend" — and if that is literally true for an R=1 combination, no deployment configuration can produce an in-process backend, so FR-14's first condition never fires and its FR-16 test can only reach the state by patching a hardcoded value, i.e. by simulating a materializer bug rather than an operator error. The same paragraph then says a non-Redis component "legitimately falls back to Django's in-process cache in production," which is only consistent if the cache backend is a *feature-materialized* fragment rather than a hardcode. Both statements are in one sentence and only one can be true per combination.

**Cite.** §4.3 description ¶2; FR-14 consequence 1; FR-16.

**Fix.** Rewrite §4.3 ¶2 to say the Redis backend is supplied by the Redis feature's settings fragment and is absent where the feature is not selected, and restate FR-14's first condition against what an operator can actually vary (an unset or non-Redis cache URL in an R=1 component), which also merges cleanly with F-1.3.

### F-2.7 — "Eight conditions" is a count of clauses, not of forbidden states, and FR-16 counts the clauses — **MEDIUM**

**Path.** FR-13's second condition is a composite of five distinct states: `ModelBackend` present, non-empty `ACCOUNT_LOGIN_METHODS`, `DJANGO_ADMIN_FORCE_ALLAUTH` not true, `authtoken`/`TokenAuthentication` present, `obtain_auth_token` route reachable.

**Why unhandled.** FR-16 requires "Each of the eight conditions has at least one test that configures the forbidden state and asserts `ImproperlyConfigured`." Read literally, one test of one of the five sub-states satisfies it, and four credential paths go untested while SC-5 reports full coverage. The document's own §4.3 discipline — "each separate mechanism gets its own check" — argues for twelve, and §11's risk statement rests on the completeness of exactly this enumeration.

**Cite.** FR-16 consequence 1; FR-13 consequence 2; §4.3 Notes on the list length; SC-5.

**Fix.** Restate FR-16 as "each of the twelve forbidden states enumerated across FR-13 and FR-14," and keep "eight conditions" as the contract's clause count with the sub-state count made explicit.

### F-2.8 — Development-mode settings are reachable in a deployed component and outside every list — **MEDIUM**

**Path.** Deployed component with `DEBUG` true, or a wildcard host allowlist, or permissive CORS (CORS is immovable core per FR-1 and is constrained by no requirement anywhere).

**Why unhandled.** All eight conditions concern credential paths, telemetry, schema, and the claims contract. `DEBUG=True` in a deployed component publishes a traceback page that renders settings and environment — a credential *disclosure* rather than a credential *path*, so §4.3's own framing ("no check that asks 'is a bypass enabled' will see either one") applies to it too, and it is not among the two exceptions the section names. FR-17's allowlist is scoped to `AUTHENTICATION_BACKENDS`, DRF default authentication classes, and resolved URL routes, so it does not catch this either.

**Cite.** FR-13; FR-17; FR-1 (CORS as immovable core); §4.3 description ¶3.

**Fix.** Either add a ninth unconditional condition (development-mode settings active in a deployed component: `DEBUG`, wildcard hosts, unrestricted CORS) or state explicitly in §4.3 that these are handled outside the contract and by what.

---

## Structure 3 — Two Flows, One Mapper (§4.2)

### F-3.1 — One mapper is mandated; one identity key is not — **CRITICAL**

**Path.** A person authenticates first through the programmatic flow (Bearer JWT, no allauth involvement), then through the interactive flow (allauth OIDC callback) — or the reverse.

**Why unhandled.** FR-8 requires all three callers to import one mapper, and FR-9 says the mapper "resolves or creates the user." It never states *what the user is resolved on* — `sub`, `email`, or `preferred_username` — nor how the two flows relate to allauth's own account model. The interactive flow creates a `SocialAccount` keyed on provider + `uid` and a `User` linked to it; the DRF authentication class has no allauth machinery at all, so a Bearer-first identity produces a bare `User` with no `SocialAccount`. When the same human later signs in interactively, allauth either creates a *second* `User` for the same person or fails on a unique-email collision, and the two Django users can hold different authorization state — the precise divergence FR-8 exists to prevent, arriving through account resolution rather than through mapping logic. FR-8's own test ("the admin and the API agree on the authorization state of the same identity presented through different flows") presumes the two flows have already agreed on which row is "the same identity," which is the unstated part.

**Cite.** FR-8; FR-9 ("resolves or creates the user"); FR-4 consequence 3; FR-5 consequence 5; §9 Security.

**Fix.** Add a consequence to FR-8: identity is resolved on the issuer-scoped `sub` claim in all three callers; the mapper owns account resolution and creation, and the allauth adapter delegates to it rather than resolving independently. Add a test that a Bearer-first identity followed by an interactive login yields exactly one `User`.

### F-3.2 — One claims contract cannot serve two token types that carry claims differently — **HIGH**

**Path.** IdP issues an ID token (interactive) carrying `groups` and an access token (programmatic) carrying `realm_access.roles` — the default shape on at least one common IdP, and the reason FR-10 lists both.

**Why unhandled.** FR-10 makes "the group-claim name" a single environment value. FR-13 refuses to start if it is unconfigured. Nothing accommodates the two flows reading claims from different locations, which is the normal case rather than the exotic one. With one setting, whichever flow's tokens do not match it delivers *no groups* — and by FR-9's revocation rule that is not an error but an instruction to **remove every group and staff status**. The user's authorization then flips on every alternation between browser and API: elevated after an interactive login, stripped after the next API call, restored after the next page load. Every individual requirement behaves as specified.

**Cite.** FR-10 consequence 1; FR-9 consequences 2–3; FR-13 consequence 6; FR-8.

**Fix.** Make the claims contract per-flow-capable: one setting with an optional programmatic override, and add a refusal condition that the override, if present, is non-empty. Alternatively state as a hard product constraint that the IdP must be configured to emit the group claim identically in both token types, and put that in §10 as an integration requirement on the identity provider.

### F-3.3 — Missing, empty, or malformed claims: the demote-versus-reject branch is undefined — **HIGH**

**Path.** Four sub-paths: (a) token valid, group claim absent (many IdPs omit empty claims entirely); (b) group claim present but empty; (c) group claim present but the wrong type — a space-delimited string, or a nested path whose parent object is missing; (d) the claims contract is configured with a claim name the IdP does not emit at all.

**Why unhandled.** FR-9 says the mapper "removes the memberships the claims no longer assert." Under that rule (a), (b), (c) and (d) are indistinguishable from a legitimate revocation, so all four demote the user. (d) is the dangerous one: a component that is configured — so FR-13's claims-contract refusal passes — but configured *wrongly* boots cleanly and silently strips staff status from every identity on their next authentication. There is no break-glass account by explicit decision (§5, §11), so the recovery path from that state is a database edit or an IdP change, with the admin unreachable in the meantime. §4.3's argument for making the claims contract a refusal — "it presents as a mysterious permissions problem rather than a configuration error" — describes this exact outcome, and the refusal as specified does not prevent it. (c) is separately undefined: does a malformed claim raise (500), reject the authentication (401), or read as empty (demote)?

**Cite.** FR-9 consequences 2–3; FR-10; FR-13 consequence 6; §5 (no break-glass); §11.

**Fix.** Split the branch in FR-9: a group claim that is *absent* or *of an unexpected type* is a claims error — reject the authentication with 401/403 and log at error, never demote; only a claim that is present and well-formed and does not contain a group causes removal. Add a consequence: an authentication that would remove the designated staff group from the last remaining staff user emits a distinct high-severity log event.

### F-3.4 — The scope of membership removal is unstated, and the widest reading forbids app-level groups — **MEDIUM/HIGH**

**Path.** An operator grants a Django group through the admin (an application role the IdP knows nothing about); the user authenticates again.

**Why unhandled.** FR-9 removes "the memberships the claims no longer assert." Read literally that is every Django group not named in the claims, so locally granted application roles are stripped on next login and cannot persist — a significant constraint on what a generated component can do, stated nowhere. Read narrowly (only groups within an IdP-managed namespace) the PRD supplies no namespace, prefix, or registry to define the boundary. The Glossary's "the only thing in a component permitted to decide what a user may do" suggests the wide reading is intended, in which case it should be a stated product constraint rather than an inference.

**Cite.** FR-9 consequence 2; Glossary "Mapper"; FR-19 consequence 3.

**Fix.** State the rule: the mapper owns the full group set (wide reading) and application-level authorization is expressed through permissions on IdP-derived groups, not through separately assigned groups — or define the managed namespace explicitly. Either way add it to §9 Guardrails, because it constrains every component built on this base.

### F-3.5 — `is_superuser` is never set and never revoked, and FR-11's bootstrap yields an admin with no permissions — **HIGH**

**Path.** First administrator of a freshly deployed component, established by IdP group claim per FR-11.

**Why unhandled.** FR-11 says "Staff status is set exclusively by the mapper from the designated group," and FR-9 says the mapper "sets staff status from the designated group." Neither mentions `is_superuser`, and `is_staff` alone grants entry to the admin index with zero model permissions — so the bootstrap path as written produces an administrator who can log into an empty admin. The PRD never says whether the designated staff group is expected to carry permissions (and if so, who grants them, since `createsuperuser` is retired and group permissions are database state that no requirement seeds), or whether the mapper should also set `is_superuser`. The reverse path is also open: an account that acquired `is_superuser` before deployment — a persona-seeded local account in a database later promoted, or any pre-existing row — keeps it forever, because the mapper's revocation rule covers groups and `is_staff` only. That is a permanent unmanaged elevation inside a product whose whole claim is that the IdP is the only authority.

**Cite.** FR-11 consequences 1–2; FR-9 consequence 1; §9 Security; §12 factor 15.

**Fix.** Add to FR-9: the mapper sets *and clears* `is_superuser` from a second designated group (or explicitly states that `is_superuser` is never used and that the designated staff group's permissions are seeded by a migration, naming which). Add a consequence: an identity whose claims do not assert the superuser group has `is_superuser` cleared on next authentication.

### F-3.6 — The programmatic flow re-syncs authorization on every request, and its revocation window is not the one FR-9 scoped out — **MEDIUM/HIGH**

**Path.** An API client making sustained requests with a valid Bearer token.

**Why unhandled.** FR-9 applies "on every authentication," and for a stateless Bearer flow every request is an authentication. As specified, every API request performs a user lookup, a group-set diff, membership writes, and a structured log event — a write path and a log line per request, with concurrent requests for the same identity racing on the same membership rows. Nothing states that the mapper is idempotent-and-quiet when nothing changed, or that the programmatic flow may cache the resolved authorization for the token's lifetime. Separately, FR-9's Out of Scope covers only "an already-established session," and its assumption is stated against *session lifetime*. A live Bearer token is not a session: after a group is removed at the IdP, an unexpired token keeps asserting the old claims and the mapper will faithfully **re-grant** the removed group on every request until the token expires. The revocation latency for the programmatic flow is therefore bounded by token TTL, a value the PRD never mentions, and Open Question 1's proposed remedy ("a shorter session lifetime") does not touch it.

**Cite.** FR-9 (all consequences and Out of Scope); Assumption 2; Open Question 1; FR-5.

**Fix.** Add to FR-9: the mapper is a no-op with no log event when the resolved state is unchanged, and the programmatic flow may cache the mapping result for at most the token's remaining lifetime. Extend the Out of Scope and Assumption 2 to name access-token lifetime alongside session lifetime, and add it to Open Question 1's ownership.

### F-3.7 — Unknown groups: create or ignore is undefined — **MEDIUM**

**Path.** Claims assert a group with no corresponding Django `Group` row.

**Why unhandled.** FR-9 says the mapper "adds the group memberships the claims assert" with no statement about non-existent groups. If it creates them, an IdP with a large role set populates the Django group table with rows that any later permission grant attaches to by name; if it ignores them, a permission granted to a locally created group of the same name never applies and presents as a silent authorization failure. FR-19's persona test ("changing a persona's declared groups… produces the corresponding membership change") passes under either reading because personas are seeded locally, so the local contract does not discriminate the branch.

**Cite.** FR-9 consequence 1; FR-19 consequence 3.

**Fix.** State the rule in FR-9 (recommended: create on demand, and log at info on first creation of any group name) and add a test that asserts the chosen behaviour for a claim naming a group that does not exist.

---

## Structure 4 — Lifecycle Ordering (§4.7)

### F-4.1 — The `beat` single-replica constraint has no corresponding deployment-strategy term, and beat has no drain semantics — **HIGH**

**Path.** A rolling deploy of any T=1 combination (13–16).

**Why unhandled.** FR-39 states beat "runs as exactly one replica — its schedule lives in PostgreSQL, which makes the process replaceable but not duplicable; two would produce duplicate dispatches." A rolling update with any surge — the default on the obvious target platform — starts the new beat before terminating the old, producing exactly the two-beat window the requirement forbids. §4.7's stated purpose is "the contract the component presents to [the deployment repository]," and this is a contract term the deployment repository will otherwise get wrong by accepting its own defaults. Replica count alone does not express it. Separately, FR-42 defines drain ordering for `web` and `worker` and says nothing about `beat` — whether it drains, what it does with a dispatch in flight at SIGTERM, or whether a scheduling gap during replacement is acceptable.

**Cite.** FR-39 consequence 3; FR-42; §4.7 description.

**Fix.** Add a consequence to FR-39: the declaration states that `beat` must be replaced with no overlap (surge zero / recreate), and that a scheduling gap of the replacement duration is the accepted trade. Add `beat` to FR-42's ordering with its own sentence.

### F-4.2 — Readiness has two inputs and the PRD defines only one — **MEDIUM**

**Path.** SIGTERM received while the database is healthy; and the window between process bind and first successful database contact.

**Why unhandled.** FR-41 defines readiness as "checks that the database answers, and returns non-200 when it does not." FR-42 requires that on SIGTERM "readiness flips before the drain begins" — which is a second, stateful input the FR-41 definition does not admit. The composition is unstated (readiness must be `not draining AND db_ok`), as is where the drain flag lives and whether a probe that arrives mid-flip can observe 200. The boot window is a related unknown: whether readiness answers at all before the application is fully initialized, or whether the endpoint is simply unreachable until then and the platform's probe failure threshold absorbs it.

**Cite.** FR-41 consequence 2; FR-42 consequence 1; NFR-2.

**Fix.** Restate FR-41's readiness consequence as a conjunction of a drain flag and a database check, and state that the endpoint is served as soon as the process binds — returning non-200 until the first successful database contact rather than not answering.

### F-4.3 — A failed or interrupted release-stage migration has no defined recovery, and FR-13 makes it total — **MEDIUM/HIGH**

**Path.** SIGTERM (or platform timeout, or node eviction) during `manage.py migrate` in the release stage, leaving the migration set partially applied.

**Why unhandled.** FR-40 requires migration before new pods serve, and FR-13 refuses startup on unapplied migrations. Combined, a partially completed migration job means **no new replica can start** until a human intervenes, and old replicas may already be terminating under the deploy. The PRD states the happy ordering and neither the failure ordering nor the recovery path — whether the release stage is retried, whether migrations must be individually re-runnable, or what a deployment does when the migration job exits non-zero. This is the one lifecycle failure where the refusal contract converts a partial failure into a total one.

**Cite.** FR-40; FR-13 consequence 3; §4.7 description.

**Fix.** Add a consequence to FR-40: the migration step is idempotent and safely re-runnable, a failed release stage aborts the deploy with the previous release left serving, and documentation states that the deployment pipeline must not begin replacing replicas until the migration step reports success.

### F-4.4 — SIGTERM before the process is serving is unspecified — **LOW/MEDIUM**

**Path.** SIGTERM arrives while the refusal contract is being evaluated, or after evaluation but before the server binds — routine during a deploy that is rolled back or a scale-down that races a scale-up.

**Why unhandled.** FR-42's ordering begins with "reports unready, stops accepting connections, finishes in-flight requests" — every step presumes a bound, serving process. A process killed at second three of startup has no readiness endpoint to flip and no connections to drain; the requirement is silent on whether it must exit cleanly, and on whether a startup that is still evaluating the contract must remain interruptible (it will not be, if the migration-state query is blocking on an unreachable database — see F-2.3).

**Cite.** FR-42; NFR-1; FR-13.

**Fix.** One consequence in FR-42: a process that receives SIGTERM before it begins serving exits immediately and non-zero without attempting the drain sequence, and no startup check blocks signal handling.

---

## Structure 5 — The Materializer and the Harness (§4.6)

### F-5.1 — `pixi.toml` and `pixi.lock` are listed as kept verbatim while FR-2 and FR-27 require them to differ per combination — **CRITICAL**

**Path.** All twelve materializations.

**Why unhandled.** FR-36's disposition places `pixi.toml` and `pixi.lock` under **Kept** — the same category as `manage.py` and `.gitignore`, meaning copied unchanged. FR-2 requires the Celery instrumentor present in exactly four combinations and the Redis instrumentor in exactly eight; FR-27 requires that "the dependency manifest contains no package from an unselected feature's package surface"; FR-48 requires every dependency lock-pinned. A verbatim `pixi.toml` fails FR-2 and FR-27 in eleven of twelve combinations, and a verbatim `pixi.lock` ships every feature's resolved packages into every component. NFR-5 compounds the ambiguity by stating determinism as "the same selections and the same lock file produce the same component," implying one shared lock file — while per-combination manifests require twelve resolutions, whose relationship to the accelerator's own lock file is undefined. This is the single most mechanically consequential contradiction in the document: FR-2's entire testable surface is unreachable as long as the manifest is in the Kept list.

**Cite.** FR-36 consequence 3; FR-2 (all consequences); FR-27 consequence 1; FR-48; NFR-5.

**Fix.** Move `pixi.toml` to **Parameterized** and give `pixi.lock` its own disposition: regenerated per combination, or a single accelerator lock file from which each combination's manifest selects a subset — and state which, because it decides whether materialization requires a solver. Restate NFR-5's determinism claim against whichever answer is chosen.

### F-5.2 — FR-36's disposition is an enumerated list with no rule for anything not on it — **HIGH**

**Path.** Any file added to the repository after this PRD — a new top-level config, a new `docs/` page, a new tooling directory.

**Why unhandled.** FR-36 gives three closed lists (Stripped, Parameterized, Kept) with no default for a path that matches none, and no test that fails when one appears. A file added later is silently included or silently dropped depending on the implementation, and either error is invisible: an accelerator-internal file shipped into every component, or a component-essential file missing from all twelve. This is precisely the denylist weakness FR-17 was written to eliminate for credential paths — "a denylist cannot by construction catch a path invented next year" — and the same lesson is not applied to the disposition, even though §4.6 and the addendum both name the disposition as one of the three artifacts that must survive into phase 2.

**Cite.** FR-36 consequences 1–3; FR-17 and its Notes; addendum §1 ¶4.

**Fix.** Add a consequence to FR-36: every path in the repository resolves to exactly one disposition, and a path matching none fails materialization with the path named — the FR-17 pattern applied to the file set. A test enumerates the repository against the disposition and fails on any unclassified path.

### F-5.3 — The materializer and `.github/` ship into materialized components — **HIGH**

**Path.** Every materialization.

**Why unhandled.** The materializer lives "in this repository" (Glossary, FR-29) and appears on none of FR-36's three lists — so under F-5.2's missing default it may travel into every component, carrying its own tests into the component's suite and its own code into the component's ninety-percent coverage denominator. `.github/` is explicitly **Kept**, which means a component inherits the accelerator's workflows — including the twelve-combination materialize-and-gate workflow that FR-31 requires, which cannot run in a component that has no materializer and no combination space. Some CI must travel with a component (the component's own pipeline is central to UJ-1's climax), so `.github/` is neither purely kept nor purely stripped, and the PRD treats it as one thing.

**Cite.** FR-36 consequence 3; FR-29; FR-31; UJ-1.

**Fix.** Split `.github/` by workflow: the component pipeline is parameterized and travels; the harness workflow is stripped. Add the materializer and its tests to the Stripped list explicitly.

### F-5.4 — "Equivalent to the reference application" is undefined, and no requirement says which side wins on disagreement — **MEDIUM**

**Path.** Materializing combination 16 (all features) and comparing to the reference application.

**Why unhandled.** FR-29's third consequence asserts equivalence, but FR-36 guarantees the two differ by construction — the package path is renamed from `src/django_service/`, six files are parameterized, five directories are stripped. So "equivalent" needs a defined normalization, and the PRD does not give one, which makes the consequence untestable as written. The addendum §1 goes further and proposes the materializer/template cross-check as "a stronger transition test than either mechanism alone" — that test also needs the equivalence relation this FR leaves open. And in phase 1 the more common disagreement is between the materializer and the reference application after a developer edits the latter; nothing states which is authoritative or that a divergence is a build failure rather than a diff.

**Cite.** FR-29 consequence 3; FR-36; addendum §1 ¶5; NFR-5.

**Fix.** Define the equivalence: materialized output for combination 16, after applying the reference application's own parameter values and excluding the stripped set, is byte-identical to the reference application — and a divergence fails the harness run.

### F-5.5 — Nothing requires materialization into a clean target, so the harness can mask the very orphans it detects — **MEDIUM**

**Path.** Twelve sequential materialize-and-gate runs in a reused CI workspace.

**Why unhandled.** FR-29 requires determinism of *output for the same selections* but never that the destination is empty before materialization begins. A harness that materializes combination 8 over the residue of combination 16 leaves that combination holding a settings fragment or template it did not select — which either fails the gate for a spurious reason or, worse, satisfies an import that should have been removed and turns SC-2 into a false pass. This is the orphan failure mode (§4.5) reproduced one level up, inside the mechanism whose job is to detect it.

**Cite.** FR-29 consequences 1–2; FR-27; FR-28; SC-2; NFR-5.

**Fix.** Add a consequence to FR-29: materialization targets an empty destination and fails if the destination is non-empty; the harness creates a fresh tree per combination.

### F-5.6 — Whether a failing combination stops the run or the run completes is unstated — **MEDIUM**

**Path.** Combination 5 fails its gate; combinations 6 through 16 have not yet run.

**Why unhandled.** FR-31 says "A failure in any one combination fails the run; there is no partial pass" — a statement about the verdict, not about execution. UJ-3's narrative depends on the run-all behaviour ("eleven pass and one fails"), and FR-34's reporting requirement — a run must state what was not covered — arguably applies to combinations skipped by a fail-fast abort, which the PRD does not connect. Under fail-fast, two independently broken combinations take two full CI cycles to discover, each cycle being twelve gate runs.

**Cite.** FR-31 consequence 2; FR-34; UJ-3.

**Fix.** State in FR-31 that all twelve run regardless of individual failures and the run reports every failing combination; the verdict is the conjunction.

### F-5.7 — Fixture-set orphans and two broken FR cross-references — **LOW**

**Path.** (a) A parameter is removed from the order surface while its fixture remains. (b) Traceability by FR number.

**Why unhandled.** FR-30 closes the missing-fixture direction ("a parameter added… without a corresponding fixture causes materialization to fail") and leaves the stale-fixture direction open — the same orphan class FR-27 and FR-28 treat as load-bearing for source, untreated for the fixture set that §4.6 and the addendum both name as a phase-2 carry-forward artifact. Separately, two cross-references resolve to the wrong requirement: FR-25 cites "(FR-34)" for the materializer's refusal, which is FR-33; FR-18 cites "The smoke check of FR-33," which is FR-32. Downstream epics that trace by number will follow both to the wrong place.

**Cite.** FR-30; FR-25 consequence 2; FR-18 consequence 4.

**Fix.** Add the inverse consequence to FR-30 (a fixture with no corresponding parameter fails materialization). Correct both citations.

---

## Paths checked and found handled

Enumerated and *not* reported, so the reader knows the coverage was exhaustive:

**Combination space.** All four invalid combinations (T=1, R=0) are refused at selection with a named reason (FR-25, FR-33) rather than emitted — including the refusal being stated as pre-source ("before any source is produced"). The immovable core is well-defined in all twelve (FR-1). Instrumentor presence is enumerated per feature and matches the table exactly for Redis (8) and Celery (4) (FR-2). The admin's independence from the UI feature is stated and testable in all six U=0 combinations (FR-3). Presets constrain nothing and every combination is reachable without one (FR-26). Object storage's *package* availability is confirmed (FR-49) — only its behaviour is missing.

**Refusal contract.** The relocation of the evaluation out of the deployed settings module closes the guard-behind-its-own-door failure (FR-12) and its specific test case is named. Fail-closed direction on the environment declaration is explicit and correct. Both conditional refusals are scoped to the correct feature and explicitly not evaluated where the feature is absent (FR-14 consequence 3). The URL-configuration inspection closes the settings-correct-route-still-live path (FR-15), and the route-absence-versus-class-absence distinction is called out in FR-6. The denylist weakness is identified and inverted by the allowlist test (FR-17). The development keypair *file* is correctly deferred to packaging rather than duplicated as a ninth condition (FR-13 Out of Scope). The eight-versus-six reconciliation against the brief's addendum is explicit.

**Authentication.** First-versus-subsequent authentication is closed by the explicit rejection of `populate_user()` and a test for the second authentication (FR-9). Group removal and staff-status removal on re-authentication are both stated. Staff-group removal against a *live session* is scoped out with a named assumption and an owner (Assumption 2, Open Question 1). Lazy JWKS retrieval is required at both FR-5 and FR-23 with a boot-time no-network test. Signature, `iss`, `aud`, `exp` are each individually required, locally as well as deployed (FR-5, FR-20). Key rotation is required to be survivable without restart. The local path is genuinely the same mapper and the same authentication class, not a shim (FR-19, FR-20).

**Lifecycle.** Liveness touching nothing external is stated twice with the crash-loop reasoning (FR-41, NFR-2). Readiness not re-checking migrations is stated with the rolling-deploy schema-skew reasoning — the older-replica-newer-schema path is explicitly handled. Migrations never running at entrypoint, with the replica-race reasoning, is closed (FR-40). Web drain ordering (unready → stop accepting → finish in-flight → exit) and worker drain (finish current, decline new) are both ordered, with the grace period correctly assigned to the deployment repository as a named assumption. Session storage is database-backed in all twelve with the engine set explicitly, so it cannot vary by toggle (FR-43, NFR-3).

**Harness.** The missing-fixture direction is closed by failure rather than by defaulting (FR-30). The invalid-combination refusal names the constraint rather than failing generically (FR-33). Silent verification-set truncation is forbidden and must be reported, with the growth policy pre-decided (FR-34, CG-2). The provenance stamp's phase-1 population is specified, and acting on it is correctly a non-goal. The sonar project key is identified as a silent-merge hazard and parameterized (FR-36). Coverage narrowing, refusal softening, and substitution creep are each named as counter-criteria with the specific mechanism they would destroy (CG-1, CG-3, CG-4).
