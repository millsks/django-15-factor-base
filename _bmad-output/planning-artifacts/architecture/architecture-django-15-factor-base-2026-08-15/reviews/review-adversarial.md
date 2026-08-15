---
title: "Adversarial Review: ARCHITECTURE-SPINE.md (django-15-factor-base)"
target: "_bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md"
lens: "Divergence attack — construct pairs of phase-1 units that obey every AD and still build incompatibly"
created: 2026-08-15
status: draft
---

# Adversarial Review — Architecture Spine

**Method.** I took the spine as a contract and tried to break it from one level down: for each pair of phase-1 epics (or two developers on two stories) I asked whether both could obey **every** AD to the letter and still produce trees, schemas, or behaviours that cannot be merged. Every finding below carries a buildable counterexample naming the two units, the AD they both obey, and the exact divergence. Vague concerns are omitted deliberately.

**Verdict.** The spine is strong on the two things it was written to fix — the mapper's frequency/identity split and the locality/process declaration — and those ADs (AD-10, AD-11, AD-12, AD-13) are the best work in it. But it has **five critical divergence holes**, and four of them share one root cause: *the spine fixes what is declared and where it lives, and repeatedly does not fix the granularity, the ordering, or the schema of the declaration*. Two competent epics reading the same AD land in incompatible worlds. I found twenty findings; five are critical, six high.

The single most damaging is **X-2**: as written, every deployed component grants nobody any authorization and nobody can reach the admin, and the local smoke check passes anyway.

---

## Findings

### X-1 — No disposition can express feature-owned content inside a core file, yet AD-3 requires exactly that. **Severity: Critical.**

**Units.** Epic A: *Feature model and the carrier* (AD-1, AD-2). Epic B: *Celery feature extraction* (AD-3).

**The AD both obey.**

> AD-2: "Four dispositions, exhaustive and mutually exclusive — `core` (always travels), `feature:<name>` (travels only where selected), `tenant` ..., `machinery` (never travels)."
>
> AD-3: "Feature configuration is therefore **subtractive** — present in `base.py` and pruned."

**The divergence.** `src/config/settings/base.py` carries the Celery block (`CELERY_TIMEZONE`, `CELERY_BROKER_URL`, `CELERY_BROKER_USE_SSL`, `CELERY_RESULT_BACKEND`, `CELERY_REDIS_BACKEND_USE_SSL`, `CELERY_RESULT_EXTENDED`, `CELERY_RESULT_BACKEND_ALWAYS_RETRY` at `src/config/settings/base.py:296-313`) and `django_celery_beat` in the installed-app lists. `src/config/observability/telemetry.py:134-137` unconditionally calls `DjangoInstrumentor().instrument()`, `CeleryInstrumentor().instrument()`, `PsycopgInstrumentor().instrument()`, `RedisInstrumentor().instrument()`. Both files carry immovable-core content, so under AD-2 both must be `core` — AD-2 permits exactly one disposition per path and nothing finer.

- Dev A implements sub-file removal with in-source region markers (`# feature:celery` … `# /feature:celery`) and declares the markers in `accelerator.toml`.
- Dev B refuses to put markers in source (AD-1's paradigm says "nothing infers a feature's extent from naming or directory layout"; markers feel like the same sin), and instead refactors the Celery settings into `src/config/settings/_celery.py` and the Celery/Redis instrumentor calls into `src/config/observability/_celery.py`, making them whole-file `feature:celery` / `feature:redis` surfaces imported by the core file behind a guard.

Both obey AD-1, AD-2, AD-3 and AD-4. The carriers are incompatible, the trees are incompatible, and — worse — under Dev A's world the AD-2 reconciliation check **passes** while a missed marker leaves `CeleryInstrumentor().instrument()` in eight combinations whose pixi environment no longer contains `opentelemetry-instrumentation-celery`. That is an `ImportError` at boot in two thirds of the combination space, and AD-2's Prevents ("an unlisted path silently travelling into every component") does not prevent it because the *path* is claimed and the *region* is not.

**Close it.** A new AD fixing (a) the granularity of a disposition, (b) the single sanctioned mechanism by which a `core` path carries feature-owned regions, with a fixed syntax, and (c) an extension of the two-way reconciliation to regions: every marker names a declared feature, every declared region marker exists in the file it names. Without this the materializer's central mechanism is undefined for the three files that matter most (`settings/base.py`, `observability/telemetry.py`, `pixi.toml`).

---

### X-2 — Django `Group` rows have no owner, AD-12 forbids creating them, and the result is a bootstrap deadlock in every deployed component. **Severity: Critical.**

**Units.** Epic A: *Authentication and the mapper* (AD-10, AD-11, AD-12). Epic B: *Local development contract* (personas, AD-21).

**The AD both obey.**

> AD-12: "A claim asserting a group with no matching Django `Group` is **ignored and logged, never created**."
>
> AD-11 / AD-12: "`is_staff` and `is_superuser` are each set from their own designated group."

**The divergence.** Nothing in the spine says where Django `Group` rows come from, or their `Permission` rows.

- Epic B must make groups exist locally or personas resolve to zero groups and SC-4 fails, so the persona seeding task ships a `Group.objects.get_or_create(...)` derived from the persona declarations. The smoke check passes for all twelve combinations.
- Epic A assumes groups pre-exist, because AD-12 forbids it from creating them.

Deployed: the seeding task is refused (AD-13 locality, FR-19), the mapper may not create groups (AD-12), `createsuperuser` is retired (FR-11) and the component cannot migrate itself (AD-22). The first real IdP sign-in asserts the designated staff group; there is no matching `Group`; AD-12 ignores-and-logs; `is_staff` is never set; the admin is unreachable; and the only place a human could create the group is the admin. **Nobody can ever administer a deployed component.** Both units obeyed every AD, and the harness cannot see it: the smoke check is local, where Epic B seeded the groups.

This is the readiness review's **B-5** (severity: high, "Nothing specifies where Django permissions or superuser come from"), and the spine answers the superuser half (AD-11) while silently dropping the provisioning half.

**Close it.** A new AD naming the owner and mechanism of `Group`/`Permission` provisioning in a deployed component — a data migration inside `django_service` seeded from the claims contract, or a release-stage management command the carrier declares as a process type — and requiring the local persona seeding task to *call* that mechanism rather than reimplement it. State explicitly whether a designated group missing from the database is a refusal condition (I would argue it is: it is exactly "a misconfiguration presenting as a permissions bug," which AD-12's own Prevents forbids).

---

### X-3 — Stage-1 refusals and AD-8's composition step are ordering-incompatible; and no AD fixes the refusal contract's mechanism at all. **Severity: Critical.**

**Units.** Epic A: *Refusal contract* (`src/config/startup/`). Epic B: *Reusable-app extension model* (AD-8, AD-9).

**The AD both obey.**

> AD-8: "`config/settings/base.py` **ends with** a composition step that walks the explicitly adopted app list and merges contributions."
>
> AD-9: "The stage-2 unapplied-migrations refusal and the sqlite refusal **both iterate every configured database**." / "Local substitution is applied automatically by the base."
>
> (FR-12, inherited): stage 1 is "shared code, imported by every settings module."

**The divergence.** Epic A implements stage 1 the way the mechanism demands — a module every settings module imports, evaluated at import. Epic B appends the composition step to the end of `base.py`, as AD-8 mandates. `production.py` then imports `base.py` and overrides afterwards.

Result: an adopted app contributes `DATABASES["billing"]`, and AD-9 applies the local sqlite substitution to it automatically. Stage 1 has already run. The sqlite refusal never sees `billing`. A deployed component serves a contributed database out of a sqlite file. AD-9's Prevents — "six enforcement points each being answered differently by six epics" — does not prevent this, because AD-9 fixes *what* the enforcement points do and nothing fixes *when* they run relative to composition.

**And the larger hole:** the Capability map routes §4.3 (the refusal contract — the product's highest-consequence surface, §11: "One check carries the whole guarantee") to AD-13, AD-9, AD-21, AD-22. **None of those four says where stage 1 lives, where stage 2 lives, which app owns the `AppConfig`, or in what order they run.** AD-13 is only about the locality/process *declaration*. Two developers therefore split: one adds `config.startup` to `INSTALLED_APPS` (making `config` an installed app, which sits awkwardly against AD-4's "assembles; owns no domain"); the other puts `ready()` in `django_service.users.apps.UsersConfig`, coupling the refusal contract to the app the UI feature edits. Both satisfy FR-12 and every AD. The readiness review's **C-1** (critical) is unanswered by the spine. So is FR-17's allowlist, which §11 calls "the difference between FR-16 being a guarantee and being a habit" — it appears in no AD (see also X-8, where it collides with AD-8).

**Close it.** A new AD: the refusal contract is one module at `src/config/startup/`; stage 1 is invoked as the **last statement of every settings module**, after the AD-8 composition step by construction; stage 2 is owned by a named `AppConfig` in a named immovable-core app that AD-8 forbids any adopted app from preceding; and the FR-17 allowlist is part of the same module and the same declaration.

---

### X-4 — `accelerator.toml` is machinery that never travels, and AD-8, AD-9, AD-14 and AD-22 all make it a component-facing declaration. **Severity: Critical.**

**Units.** Epic A: *Deployment interface* (AD-14, AD-22). Epic B: *Reusable apps* (AD-8, AD-9).

**The AD both obey.**

> AD-2: "`machinery` (never travels)." Structural Seed: "`accelerator.toml` # machinery — the catalogue (AD-1)."
>
> AD-1: "declared in `accelerator.toml` at the repository root, **and nowhere else**."
>
> AD-14: "Replica counts and replacement strategy ... live in `accelerator.toml`."
>
> AD-9: "the process-model declaration **varies by adopted apps** as well as by combination" / "Readiness treats a contributed database as required **unless the carrier declares otherwise**."
>
> AD-8: "The contributable surface is closed and **enumerated in `accelerator.toml`**."

**The divergence.** Component X is materialized and therefore has no `accelerator.toml`. Its team then adopts reusable app `billing`, which contributes a database. Three mechanisms now have no home in X:

1. The deployment repository needs a second release-stage migration step for `billing`. AD-14 puts process-model constraints in a file X does not have.
2. Readiness must decide whether `billing` is required. "Unless the carrier declares otherwise" has no carrier in X.
3. The composition step must validate `billing`'s contribution against the closed surface. Dev A hardcodes the closed surface in `config/settings/composition.py`; Dev B reads it from the carrier, per AD-1's "and nowhere else," and X's composition step finds nothing and either crashes or no-ops — silently reopening the surface AD-8 exists to close.

Dev B is the letter-compliant one and is the broken one. Note also that AD-8's "adoption is explicit — a `pixi.toml` line and **an adopted-app list entry**" never says where the adopted-app list lives; AD-1's absolutism points at the carrier, which is precisely the file that does not travel.

**Close it.** Split the declaration: `accelerator.toml` stays machinery (the catalogue: feature surfaces, dispositions, presets, parameters), and a **component-resident, `core`-disposed declaration** carries what the component itself needs at runtime and at deploy time — the adopted-app list, per-database requiredness, and the process-model constraints. Or rule that the closed contributable surface is code in `config/`, not data. Either is fine; the spine currently permits both and they are not merge-compatible.

---

### X-5 — Parameterization has no disposition, no declaration and no owner; FR-37's parameterize list is silently dropped. **Severity: Critical.**

**Units.** Epic A: *Materializer*. Epic B: *Fixture set* (FR-31).

**The AD both obey.**

> AD-2: "Four dispositions, exhaustive and mutually exclusive — `core`, `feature:<name>`, `tenant`, `machinery`."
>
> AD-1 enumerates what the carrier declares: "Every feature's package surface, non-package surface, constraints and presets; the per-path disposition; the tenant-space location; and each process type's deployment constraints." **Parameterization is not in that list, and there is no fifth disposition for it.**

**The divergence.** FR-37 requires "it is parameterized if the carrier declares it parameterized" and names the list: `sonar-project.properties`, `README.md`, `CHANGELOG.md`, `LICENSE`, `pyproject.toml`, `mkdocs.yml`. The user's constraint correctly removed `src/django_service/` from that list (AD-5, memlog); the other six went with it and appear nowhere in the spine.

- Epic A ships `sonar-project.properties` as `core` — it must travel, and `core` is the only disposition that travels unconditionally. The hardcoded project key at `sonar-project.properties:6` travels with it, every generated component reports code quality into the accelerator's own project, **nothing fails and the metrics merge silently** — the exact consequence FR-37 names.
- Epic B builds a fixture set covering "the four feature booleans, the component name and the code-quality project key" (spine, Deferred) with nowhere to apply it, and no field list to fail against, so FR-31's fail-on-missing-fixture rule is unimplementable.

And "the component name" is itself a multi-file substitution with no declared extent: `pixi.toml:4` `[workspace] name`, `pyproject.toml:6` `[project] name`, `pixi.toml:101` `[pypi-dependencies] django-15-factor-base = {...}`, `pixi.toml:106` `[pypi-options] no-build-isolation = ["django-15-factor-base"]`, `sonar-project.properties`, `mkdocs.yml`, `README.md`. Inferring that extent is precisely what the Design Paradigm forbids.

**Sequencing trap.** Build the materializer and the twelve gates first, add parameterization second, and every carrier entry, every fixture, and every combination's gate output is re-cut.

**Close it.** Make parameterization an **orthogonal axis**, not a fifth disposition: a path has a disposition (does it travel) and, independently, a parameter set (what is substituted inside it). Declare `[parameters]` in the carrier — name, fixture value, and the exact path + token sites — and extend the two-way reconciliation to it: a declared parameter with no site fails, a site with no declared parameter fails.

---

### X-6 — AD-14's "prune per combination for free" is false, and the spine never says whether `pixi.toml` / `pixi.lock` travel verbatim. **Severity: High.**

**Units.** Epic A: *Materializer* (AD-3). Epic B: *Deployment interface* (AD-14).

**The AD both obey.**

> AD-14: "`web`, `worker` and `beat` are pixi tasks; the deployment repository invokes `pixi run <process>` and enumerates them with `pixi task list`. **They prune per combination for free.** ... A gate test asserts every process type the carrier declares has a matching task in materialized output."
>
> AD-3: "The four selectable features are declared as pixi features with an `[environments]` matrix, so one `pixi.lock` yields twelve genuinely lean, pre-locked environments."

**The divergence.** `pixi.toml` is a single path carrying, simultaneously: core dependencies, feature dependencies, the environments matrix, the process tasks, the AD-13 locality declarations, and `COVERAGE_CORE`. Under AD-2 it gets one disposition, and it must be `core`.

- Epic A copies it (the only thing AD-2 authorizes for a `core` path). Every materialized component now carries `[feature.celery.dependencies]`, all twelve environments, and `worker`/`beat` tasks. FR-2 ("the dependency manifest of a materialized combination contains ... no others") and FR-40 ("`worker` and `beat` are present in **exactly** the combinations that selected background task processing") are both violated.
- AD-14's gate test **passes** anyway, because it asserts only carrier→task ("every process type the carrier declares has a matching task"), never task→carrier. A `worker` task in a component with no Celery is invisible to it.
- Epic B then reads `pixi task list` in a no-Celery component and finds a `worker` process the deployment repository will try to run.

"For free" is doing all the work here: pruning a task out of `pixi.toml` is sub-file editing of a `core` path, i.e. X-1 again, and no AD authorizes it. Separately unanswered: does a materialized component keep the twelve-environment matrix — and if so, which environment does its own `pixi run ci` use — or a single `default`/`dev` pair, in which case its lock must be regenerated and AD-3's "pre-locked" claim does not survive materialization at all (NFR-5).

**Close it.** Make AD-14's gate assertion two-way. And give `pixi.toml` and `pixi.lock` an explicit materialization contract in an AD; they are the one file pair on which AD-2, AD-3, AD-13, AD-14 and AD-20 all land at once.

---

### X-7 — AD-10's "once per `jti`" depends on shared state that eight of twelve combinations do not have, and on a claim AD-12 never requires. **Severity: High.**

**Units.** Two developers on the mapper: the DRF authentication class story and the sync story.

**The AD both obey.**

> AD-10: "**Sync** ... runs once per credential epoch: every interactive login, and **once per Bearer token at first sighting of its `jti`**."

**Divergence A — where the epoch record lives.**
- Dev A uses `django.core.cache`. In the eight combinations without the Redis feature, that is Django's in-process backend: "first sighting" becomes *first sighting per gunicorn worker per process lifetime*. With N workers, sync runs N times per token and again after every deploy. AD-10's Prevents claims it prevents `auth_user_groups` write amplification; across two thirds of the combination space it divides it by N and nothing more.
- Dev B uses a table in `django_service`. That is a model added to the declared public API (AD-5 — is that a breaking change? unstated), a migration, a write per token, and unbounded row growth with no pruning process declared (FR-44 declares a pruning admin process for *sessions* only).

Both obey AD-10. They differ in write volume, in revocation behaviour across restarts, and in whether the component gains a migration.

**Divergence B — a token with no `jti`.** AD-12 fixes the edge behaviours for the group claim, the unmatched `Group`, staff/superuser, and username collision. It says nothing about a missing `jti`, and not every issuer puts one on access tokens.
- Dev A: no `jti` → sync every request. That is the write-amplification outcome AD-10 exists to prevent, arriving through a gap in AD-12.
- Dev B: no `jti` → resolve only, never sync. Authorization is frozen at first sighting, indefinitely. That is the stale-authorization outcome AD-10 exists to prevent.

AD-10 says "there is no third outcome"; the missing-`jti` gap delivers both.

**Divergence C.** Conventions state "Cache failure is swallowed *and* logged." If the epoch record lives in the cache, a cache outage silently switches the system into Divergence-A or Divergence-B behaviour with no signal beyond a swallowed-failure log line.

**Close it.** AD-10 must name the epoch store, its availability guarantee across all twelve combinations, its behaviour when the store is unavailable, and the behaviour for a token without `jti`. The consistent answer for the last is rejection with 401, matching AD-12's own posture for a token lacking a claim the contract requires.

---

### X-8 — AD-8's closed surface admits DRF entries, which collide head-on with the FR-17 allowlist the refusal epic must build. **Severity: High.**

**Units.** Epic A: *Reusable-app extension model* (AD-8). Epic B: *Refusal contract and allowlist* (FR-17).

**The AD both obey.**

> AD-8: "Introducing a new key is permitted; touching an existing key raises `ImproperlyConfigured` ... The contributable surface is closed and enumerated ...: additional databases and their routers, installed apps, the app's own namespaced settings, **DRF and Celery entries**. Anything else is refused."
>
> AD-8's Prevents: "an installed package acquiring `MIDDLEWARE` and therefore **visibility of every request**."
>
> FR-17: "`AUTHENTICATION_BACKENDS` and the DRF default authentication classes each match an approved allowlist **exactly**; an entry present but not listed fails the test."

**The divergence.**
1. App `billing` contributes `REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]` — a key the base does not set today, so "introducing a new key is permitted" allows it, the composition step accepts it, and an adopted app now decides authorization for **every API request in the component**. That is the whole-request visibility AD-8's Prevents claims to forbid, arriving through the door AD-8 explicitly opened. The rule says `MIDDLEWARE`; the harm is "visibility of every request," and DRF's global defaults deliver it.
2. If the base ever stops setting `DEFAULT_AUTHENTICATION_CLASSES` explicitly, an app may introduce it under AD-8 — and the component's own FR-17 allowlist test then fails at adoption. Epic A's supported behaviour breaks Epic B's gate. Both obeyed their AD.
3. "Celery entries" are permitted unconditionally. An adopted app may contribute `CELERY_BEAT_SCHEDULE` into one of the eight combinations with no Celery. Nothing in AD-8 requires a contribution to name the features it needs, and nothing refuses it — so the app's scheduled work silently never runs.

**Close it.** Replace "DRF and Celery entries" with an explicit, non-global key enumeration; add "a contribution naming a feature the combination did not select is refused at settings import"; and make the FR-17 allowlist and the composition step's permitted-surface the *same declaration*, not two lists maintained apart. (§4.3's own lesson: three of nine refusal conditions were missing from a list its source called settled.)

---

### X-9 — AD-5's compatibility gate cannot run for an in-repo app, by AD-8's own argument. **Severity: High.**

**Units.** Epic A: *Base versioning* (AD-5). Epic B: *Reusable-app residency* (AD-6, AD-8).

**The AD both obey.**

> AD-5: "a reusable app declares the range it supports **in its package metadata** and the adoption gate test asserts compatibility."
>
> AD-8: "entry-point discovery is forbidden because **an in-repo app has no distribution metadata** and the two residency modes would diverge."

**The divergence.** `src/django_apps/billing/` in its development residency — the residency AD-6 exists to make first-class — has no distribution metadata. The adoption gate test either finds nothing and skips (silently, throughout the app's most-edited phase) or fails and blocks development entirely.
- Dev A puts the supported range in the contribution module as a constant, so both residencies work; the gate test reads it there.
- Dev B follows AD-5 literally and the supply-chain convention ("A reusable app must reach the channel before a component may depend on it"), so an app must be published before it can be adopted — which contradicts AD-6's premise that apps "live here in development and graduate to channel packages."

The two residency modes diverge on exactly the axis AD-8 refused entry points to protect. Also unstated: the version constant's format (integer? semver?) and the range syntax, so two apps will express compatibility two ways.

**Close it.** Declare the compatibility range in the contribution module — one place, both residencies — and fix the constant's format and the range grammar in AD-5.

---

### X-10 — `django_service` is declared a stable public API and simultaneously contains feature-owned surface. **Severity: High.**

**Units.** Epic A: *Server-rendered UI feature extraction* (AD-2, AD-3). Epic B: *Reusable apps* (AD-5).

**The AD both obey.**

> AD-5: "The package name `django_service` is a constant ... reusable apps import from it by that name **in every deployment** ... `django_service` exposes an API version constant."
>
> FR-3: the UI feature removes "the end-user surface — form styling, page templates, and user-facing views."

**The divergence.** `src/django_service/templates/`, `src/django_service/users/forms.py` and `users/views.py` are UI surface. AD-2 permits a `feature:ui` disposition on any path, including paths inside `django_service`.

- Epic A declares them `feature:ui`. Six combinations now lack part of the "stable public API" while the API version constant is combination-invariant. A reusable app declaring support for API version 3 imports `django_service.users.forms`, works in six components and `ImportError`s in six. The AD-5 adoption gate test passes in both, because it compares version numbers, not surfaces.
- Epic B reads AD-5 strictly, treats `django_service` as combination-invariant, and requires the UI surface to move out of it into a feature-owned location. Incompatible tree.

A live sub-case: `src/django_service/templates/` contains both UI pages (`pages/home.html`, `users/user_detail.html`) and error pages (`403.html`, `404.html`, `500.html`, `403_csrf.html`) that `extend "base.html"`. Dev A takes `templates/` wholesale as `feature:ui`; the six non-UI combinations lose `base.html` and every error page fails to render — while FR-3 requires that in a UI-absent combination "the admin renders, static files serve, the messages framework is available, and template rendering works."

**Close it.** AD-5 must state that the guaranteed public surface is the **intersection across all twelve combinations**, enumerate it, and forbid `feature:*` dispositions inside `django_service` — or make the version constant combination-aware. And state whether removing a feature bumps it.

---

### X-11 — The smoke check is invoked by two ADs and defined by none; and the verification model detects residue but never excision damage. **Severity: High.**

**Units.** Epic A: *Harness / verification* (AD-18, AD-19, AD-20). Epic B: *Immovable core* (FR-1, FR-3, SC-7).

**The AD both obey.**

> AD-19: "Merge to `main` runs all twelve **plus the smoke-check level**."

Nothing in the spine says what the smoke check asserts. Epic A builds the PRD glossary version: boot, readiness 200, persona signs in. Epic B relies on FR-1's consequence: "a combination in which the Django admin is unreachable **fails the smoke check**" — which the glossary version does not check (the readiness review flags this mismatch in its minor-defects list, and the spine does not resolve it).

**The divergence, and the structural point.** Take X-10's wholesale `templates/ = feature:ui` split. Six combinations ship with broken error pages and no `base.html`. **Nothing in the harness fails:**
- The UI feature's tests were pruned with the UI feature (Consistency Conventions: "a feature's tests are `feature:<name>` and are pruned with it"), so no test renders those templates.
- Coverage measures only what remains, so the floor is met.
- The smoke check boots and signs in a persona and never renders the admin or a 404.

AD-20's coverage signal is asymmetric by construction: it catches a template **left behind** (reports zero) and is structurally blind to a template **wrongly removed**, because the removed thing's tests leave with it. SC-2 is well defended; SC-7 ("the immovable core functions in every combination") is defended by nothing.

**Close it.** An AD defining the smoke check's assertion set (boot; readiness 200; persona interactive sign-in reaching a rendered admin index; one Bearer request through the real authentication class; one rendered 404), plus a `core`-disposed immovable-core assertion suite that is never pruned and runs inside every combination's gate.

---

### X-12 — AD-21 fixes the *shape* of local sign-in but not the *predicate* that refuses it. **Severity: High.**

**Units.** Epic A: *Refusal contract* (stage 2). Epic B: *Local development contract* (AD-21).

**The AD both obey.**

> AD-21: "Local persona sign-in is exposed as a URL route under a path prefix the component owns, and by no other mechanism ... Because it is a route, FR-13's stage-2 refusal reaches it and FR-17's allowlist covers it."

**The divergence.** "Because it is a route" is an argument, not a predicate.
- Epic A implements stage 2 as `try: reverse("dev_signin") ... → refuse`.
- Epic B names the route `local_persona_login` and mounts it under `/accounts/persona/` — a prefix the component owns, satisfying AD-21 — and the FR-17 allowlist already permits the `/accounts/` prefix because allauth lives there.

The refusal never fires. The allowlist never fires. A deployed component ships a live synthetic-claims sign-in route that will mint a session for any declared persona, including a staff one. Both units obeyed AD-21 to the letter, and this is the single worst outcome the product can produce — §11: "a vulnerability this product would have created deliberately rather than inherited."

**Close it.** AD-21 must fix the route's URL name and path prefix as constants, and — the durable half — require the stage-2 predicate to resolve the URLconf and refuse **any route whose view callable belongs to the local sign-in module**, never a string match. The same predicate shape should apply to `obtain_auth_token` (FR-15), which today lives at `src/config/urls.py:11,39`.

---

### X-13 — CG-1 is bound by AD-20 on the floor and the tracer core only; coverage `omit` is an unclaimed narrowing surface. **Severity: Medium-High.**

**Units.** Epic A: *Object storage feature*. Epic B: *Coverage floor* (AD-20).

**The AD both obey.**

> AD-20: "Ninety percent, including templates, everywhere. `COVERAGE_CORE=ctrace` travels with every combination and a test asserts it is in force ... a combination that misses structurally is answered with tests, never with a lower floor, a pragma, or a narrowed measurement."
>
> CG-1: "Excluding files, adding coverage pragmas to unreached code, or dropping template measurement makes SC-1 pass and destroys SC-2."

**The divergence.** AD-20 forbids a lower floor and a pragma *by name*. The narrowing that is already sanctioned and precedented in this repository is `[tool.coverage.run] omit` (`pyproject.toml:162-169`), which today hides `src/config/wsgi.py`, `src/config/asgi.py` and `src/config/websocket.py`. Epic A adds `omit = ["src/config/storage/*"]` to clear the floor in the six combinations that select object storage. Every AD-20 assertion still passes — floor is 90, `ctrace` is in force, no pragma, templates still measured — and an orphaned storage module left behind in the other six is now invisible to the only detector the product has.

Related residue: AD-16 deletes `src/config/websocket.py`, and nothing requires its `omit` entry at `pyproject.toml:168` to go with it. A stale `omit` line is residue that the residue detector is structurally unable to see.

**Close it.** AD-20 must declare the coverage `omit`/`exclude` list a **closed, carrier-declared surface** subject to the two-way reconciliation, and require the gate to assert the effective omit list equals the declared one.

---

### X-14 — AD-13 forbids `[activation.env]` for locality only; the same trap is open for `COMPONENT_PROCESS`, in the fail-open direction. **Severity: Medium.**

**Unit.** Any developer touching `pixi.toml`.

**The AD.**

> AD-13: "`COMPONENT_RUNTIME=local` is set in the `env` of each local pixi task, **never** in `[activation.env]` — the golden base runs pixi, so activation env reaches production ... Each of those three sets `COMPONENT_PROCESS`. ... Process type fails open."

**The divergence.** `[activation.env]` already exists in this repository (`pixi.toml:147-152`, carrying `COVERAGE_CORE`), so it is a live and precedented place to put things. A developer adds `COMPONENT_PROCESS = "web"` there so that a bare `python manage.py runserver` behaves like a serving process. **No AD forbids it** — AD-13's prohibition names `COMPONENT_RUNTIME` only.

Because process type fails *open*, the result is the inverse of harmless: every management command in the deployed image now declares itself a serving process, and `manage.py migrate` refuses on unapplied migrations. That is precisely the release-stage deadlock AD-13's Prevents cites as the reason for failing open in the first place.

**Close it.** Generalize the rule: **no `COMPONENT_*` variable may appear in `[activation.env]`**, asserted by a gate test over the materialized `pixi.toml`.

---

### X-15 — AD-2's reconciliation runs against the reference application, so anything the materializer *writes* has no disposition — including `.accelerator.json`. **Severity: Medium.**

**Units.** Epic A: *Carrier and disposition* (AD-2). Epic B: *Provenance stamp* (AD-17).

**The AD both obey.**

> AD-2: "Unlisted defaults to `machinery`. A two-way reconciliation check runs in the gate **against the reference application**: a path claimed by no disposition fails, and **a claim naming a path that does not exist fails**."
>
> AD-17: "The materializer writes `.accelerator.json` at the root of materialized output ... **The reference application carries no stamp.**"

**The divergence.** `.accelerator.json` cannot be claimed — a claim naming it fails the reconciliation, because the path does not exist in the reference application. Unclaimed means `machinery`, which means never travels, which means the stamp must not exist. AD-17 requires it to exist. Every generated artifact has the same problem: a rewritten `pixi.toml` (X-6), a per-combination lock, a generated `.env.example`.

Dev A special-cases the stamp inside the materializer. Dev B adds an `output-only` claim class, and AD-2's "exhaustive and mutually exclusive" four become five. Neither is wrong under the spine as written.

**Close it.** AD-2 must distinguish *input disposition* (does this repository path travel) from *output provenance* (what may exist in materialized output that did not exist here), and state the second reconciliation the harness actually needs: every path in materialized output is either a copied path with a travelling disposition or a declared generated artifact.

---

### X-16 — AD-19's all-pairs subset is not unique and is not pinned. **Severity: Medium.**

**Unit.** *Gate and CI* epic.

**The AD.**

> AD-19: "A pull request runs an all-pairs subset — every feature both selected and absent, every pair of features in both states — and reports which combinations it did not cover."

**The divergence.** Over four features with the broker constraint, several distinct minimal sets satisfy that predicate. Dev A hardcodes a list of six. Dev B generates one with a greedy covering-array algorithm whose output depends on set iteration order. Both satisfy AD-19 exactly. Under Dev B, a given combination may go months without ever being exercised on any PR, and the CG-2-mandated exclusion report says something different every run — reported, but not reviewable. NFR-5's determinism reaches materialization and does not reach CI's own configuration.

**Close it.** Pin the subset as data in `accelerator.toml`, and add a gate test asserting the pinned set satisfies the all-pairs predicate.

---

### X-17 — AD-20's "report before the floor is a hard gate" has no home, and AD-18 makes it unreachable. **Severity: Medium.**

**Units.** Epic A: *Gate consolidation* (AD-18). Epic B: *Harness* (AD-19, AD-20).

**The AD both obey.**

> AD-20: "**Before the floor is wired as a hard gate**, the materializer reports all twelve coverage numbers."
>
> AD-18: "A **single workflow** invokes `pixi run ci`."

**The divergence.** `pixi run ci` already depends on `test-cov`, and `test-cov` already carries `--cov-fail-under=90` (`pixi.toml:198,208`). The moment Epic A wires the single workflow, the floor is a hard gate. Epic B then runs `pixi run ci` per materialized combination — hard by inheritance, on its very first run. AD-20's reporting phase needs a *second* gate shape (`--cov-fail-under=0` plus a report artifact) that AD-18 forbids as a second invocation and that no AD assigns to an owner or gives an exit condition. The first sparse combination that lands at 88% for structural reasons (readiness review A-6, unmeasured) fails the run, and the only remedies AD-20 permits are tests nobody has budgeted.

**Close it.** Name the reporting phase as a distinct, time-boxed gate mode with an owner and an exit condition, or state explicitly that the floor is advisory for materialized combinations until a named milestone — and say which, because the sequencing is load-bearing.

---

### X-18 — AD-7 covers modules and misses tool configuration, which is where the second import root actually lives. **Severity: Medium.**

**Units.** Epic A: *Import roots* (AD-7). Epic B: *Tenant space* (AD-6).

**The AD both obey.**

> AD-7: "Import roots are declared in the package build configuration alone. No module manipulates `sys.path`; the inserts in `manage.py`, `asgi.py` and `wsgi.py` are removed. `uvicorn --app-dir` accepts one directory and is therefore not a declaration mechanism."

**The divergence.** Two live import-root declarations are neither modules manipulating `sys.path` nor the build configuration, so AD-7 forbids neither: `pyproject.toml:149` `[tool.pytest.ini_options] pythonpath = ["src", "."]`, and `pixi.toml:181` `serve = "uvicorn config.asgi:application --app-dir src"`. Epic A deletes the three inserts and stops. `src/django_apps/billing` then imports as `billing` under `pytest` (pythonpath `src`) and fails under `pixi run web`, because `[tool.hatch.build.targets.wheel] packages` at `pyproject.toml:126-127` lists exactly `src/config` and `src/django_service`. That is AD-7's own stated failure mode — "works under `pytest` and fails under `gunicorn`" — surviving AD-7 intact.

Epic B then needs `src/django_apps/` to be a root without a per-app edit, because AD-6 promises graduation "changes its residency and never its import path." Dev A adds each app to `packages` (the five-place edit reintroduced one line at a time); Dev B uses a `sources` remapping of the whole directory (different wheel layout, different editable behaviour). Both claim AD-7.

**Close it.** AD-7 must enumerate every import-root declaration site in this repository, require the pytest `pythonpath` and `--app-dir` to be removed or derived from the build configuration, and name the single build-configuration construct that makes `src/django_apps/` a root with no per-app edit.

---

### X-19 — Session engine and the database-resident allauth/Site configuration are unowned. **Severity: Medium.**

**(a) Session engine.** FR-44 requires the session engine set explicitly "so session behaviour never varies by toggle"; NFR-3 restates it as statelessness. **No AD mentions `SESSION_ENGINE`.** Epic *Redis feature* naturally sets `cached_db` where Redis is selected (it is the obvious win, and it is in that feature's surface); Epic *Deployment interface* sets `db` in `base.py` for NFR-3. Both are defensible; the first violates FR-44 outright; nothing adjudicates, and the divergence is invisible to the gate because both configurations pass every test.

**(b) The `Site` domain and allauth provider configuration.** `src/config/settings/base.py:45` sets `SITE_ID = 1`; `base.py:128` sets `MIGRATION_MODULES = {"sites": "django_service.contrib.sites.migrations"}`; `src/django_service/contrib/sites/migrations/0003_set_site_domain_and_name.py` writes the domain at migrate time. allauth builds callback URLs from the `Site`. FR-38 requires configuration from environment variables alone and AD-22 forbids the component migrating itself. **No AD covers this**; the readiness review's **A-5** (high) is dropped. Epic *Authentication* configures the OIDC provider via `SOCIALACCOUNT_PROVIDERS` from environment and considers itself done; nobody owns the `Site` domain, so every deployed component redirects to whatever the data migration baked in, in every environment.

**Close it.** An AD stating that all allauth provider and `Site` configuration is settings-and-environment resident, what becomes of the existing sites data migration, and an explicit `SESSION_ENGINE` invariant.

---

### X-20 — The GitHub-template consumer is governed nowhere, and AD-19's soundness argument is false for it. **Severity: Medium.**

**Units.** Epic A: *Deployment interface* (AD-15). Epic B: *Gate and CI* (AD-19).

**The AD both obey.**

> AD-19: "This is only sound because generation happens from a released, tagged version and **never from `main` HEAD**; if that ever changes, the trigger becomes every-PR-all-twelve."
>
> AD-15: "**Materialized components** ship no Dockerfile; the buildpack and golden-base path is the default."

**The divergence.** The decision log records the third consumer plainly: "this repository also becomes a GitHub TEMPLATE REPOSITORY ... 'Use this template' → full tree copy, no engine, no parameterization, all features present" and "GitHub 'Use this template' always copies the default branch, so the user's own path DOES read main HEAD."

A repository created that way is a real Django component and it: ships the Dockerfile (AD-15 restricts only *materialized* components, so this component acquires exactly the image-pipeline opt-out AD-15 exists to prevent); is created from `main` HEAD, so a red `main` ships (AD-19's soundness precondition is false for it); and carries `accelerator.toml` and the materializer, so it **can** adopt reusable apps while a materialized component cannot (X-4). Two blessed component shapes with materially different capabilities and different guarantees, from one architecture.

The spine acknowledges this path exactly once, obliquely, inside AD-17 ("a repository created from the GitHub template arrives unstamped").

**Close it.** An AD for the template path: what it is, what it inherits, whether AD-15 and AD-19 apply to it — or an explicit named residual risk recording that AD-19's soundness condition is violated on that path and the consequence is accepted.

---

## PRD fidelity — contradictions and quiet drops

| # | Issue | Severity |
|---|---|---|
| P-1 | **AD-10 narrows FR-9 and does not declare the divergence.** FR-9: "On **every authentication** the mapper resolves or creates the user, adds ... removes ... sets staff status ... and emits a structured log line." For the programmatic flow every request is an authentication (readiness A-2). AD-10 restricts sync to once per `jti`. The call is defensible — it is the only performant one — but the spine states it as a derivation rather than a change, never names the resulting staleness window, and Deferred lists only the *session* question (PRD Open Question 1), which explicitly does not cover Bearer. SC-6's "memberships they no longer assert removed" is true only after the token expires. | High |
| P-2 | **FR-37's parameterize list is dropped in full** (X-5). The user's constraint correctly removed `src/django_service/` from it; the remaining six items and the parameterization mechanism went with it, and FR-31's fail-on-missing-fixture rule has nothing to compare against as a result. | Critical |
| P-3 | **FR-44's explicit session engine is dropped** (X-19a) — a phase-1 must-have whose entire point is that behaviour must not vary by toggle. | Medium |
| P-4 | **Readiness B-5 (Group/Permission provisioning) is dropped** (X-2); **readiness A-5 (allauth provider config and the DB-resident Site) is dropped** (X-19b); **readiness C-1 (where the refusal contract is evaluated) is unanswered by any AD** (X-3). All three were flagged critical or high by the reviewer the spine cites as a source. | Critical |
| P-5 | **FR-30's "authored once and shared with the eventual template" is now false.** The decision log records FreeMarker as a one-way copy that will drift; Deferred says "nothing in this spine depends on what that generator consumes," which is a true but different claim. The memlog itself flagged this ("offer to update the PRD") and the spine does not carry a PRD-divergence list. | Medium |
| P-6 | **NFR-6 (telemetry overhead measured once and recorded) and FR-45 (an OTLP export end-to-end test against a collector stub) have no AD and no owner.** The capability map's Observability row reads "Conventions; unchanged from PRD," which is accurate for FR-46–FR-48 and not for these two — FR-45 in particular requires a collector stub inside every combination's gate. | Medium |
| P-7 | **CG-4** — AD-9 introduces a sixth substitution class (automatic local substitution for app-contributed databases) with no bound. CG-4 accepts that "the count is not the constraint" but requires each substitution to be justified and guarded. Guarded: yes (AD-9 iterates the sqlite refusal). Justified per instance: no mechanism exists. | Low-Medium |
| P-8 | **CG-1** is bound by AD-20 only against the floor value, pragmas and the tracer core; the `omit` list is the sanctioned narrowing already in the tree and is unbound (X-13). | Medium-High |
| P-9 | **Tone.** The PRD is deliberately unflattering about itself ("there is no moat in the code"; "a repository someone else now owns and edits is a fork by any honest definition"). The spine is uniformly confident and names exactly one residual risk (AD-13's). X-2, X-7, X-12 and X-20 are all live, accepted-or-not risks that belong in a **Named residual risks** block so the next reader does not take the spine at face value the way §5 warns against. | Low |

CG-2 (AD-19) and CG-3 (Consistency Conventions: "A refusal never degrades to a warning") are properly bound. SC-3, SC-5 and SC-6 are well served. SC-2 is well served on the residue axis and blind on the excision axis (X-11).

---

## Summary

| ID | Finding | Severity |
|---|---|---|
| X-1 | No disposition expresses feature-owned regions inside a `core` file; AD-3 requires exactly that | Critical |
| X-2 | Django `Group` rows are unowned; AD-12 forbids creating them → deployed bootstrap deadlock | Critical |
| X-3 | Stage-1 refusals vs AD-8's terminal composition step are ordering-incompatible; no AD fixes the refusal contract's mechanism | Critical |
| X-4 | `accelerator.toml` is non-travelling machinery and simultaneously the component's runtime/deploy declaration | Critical |
| X-5 | Parameterization has no disposition, no declaration, no owner; FR-37's list silently dropped | Critical |
| X-6 | AD-14's "prune for free" is false; `pixi.toml`/`pixi.lock` materialization contract undeclared; gate assertion is one-way | High |
| X-7 | AD-10's per-`jti` epoch needs shared state 8/12 combinations lack, and has no rule for a missing `jti` | High |
| X-8 | AD-8's DRF surface grants every-request authorization power and collides with the FR-17 allowlist | High |
| X-9 | AD-5's compatibility gate cannot run for in-repo apps, by AD-8's own argument | High |
| X-10 | `django_service` is a stable public API that contains feature-owned surface | High |
| X-11 | The smoke check is invoked by two ADs and defined by none; the harness detects residue, never excision damage | High |
| X-12 | AD-21 fixes local sign-in's shape but not the refusal predicate → a live persona route can ship deployed | High |
| X-13 | CG-1 unbound on coverage `omit`, the narrowing already precedented in the tree | Medium-High |
| X-14 | `[activation.env]` prohibition covers `COMPONENT_RUNTIME` only; `COMPONENT_PROCESS` there deadlocks the release stage | Medium |
| X-15 | Reconciliation runs against the reference application, so generated output — including `.accelerator.json` — has no disposition | Medium |
| X-16 | AD-19's all-pairs subset is not unique and not pinned | Medium |
| X-17 | AD-20's pre-hard-gate reporting phase has no home and AD-18 forbids the second invocation it needs | Medium |
| X-18 | AD-7 misses the two real import-root declarations (`pytest pythonpath`, `--app-dir`) | Medium |
| X-19 | `SESSION_ENGINE` and the DB-resident `Site`/allauth configuration are unowned | Medium |
| X-20 | The GitHub-template consumer is ungoverned and falsifies AD-19's soundness argument and AD-15's premise | Medium |

**Recommended new or tightened ADs, in the order I would write them:** disposition granularity and the sub-file mechanism (X-1, X-6); the refusal contract's location, ownership and ordering, folding in FR-17's allowlist (X-3, X-8, X-12); authorization data provisioning (X-2); the carrier split into machinery catalogue vs component-resident declaration (X-4); parameterization as an orthogonal axis (X-5); the smoke check and the immovable-core assertion suite (X-11); the mapper's epoch store (X-7); `django_service`'s guaranteed surface (X-10, X-9).
