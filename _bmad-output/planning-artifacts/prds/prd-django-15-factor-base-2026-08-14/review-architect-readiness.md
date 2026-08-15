---
title: "Architect Readiness Review: django-15-factor-base PRD"
status: draft
created: 2026-08-14
reviewer: Senior Software Architect (next in chain)
scope: Can architecture begin from this PRD?
---

# Architect Readiness Review

**Documents reviewed in full:** PRD and PRD addendum (`prd-django-15-factor-base-2026-08-14/`), product brief and brief addendum (`brief-django-15-factor-base-2026-08-08/`).
**Repository spot-checked:** `src/config/`, `src/django_service/`, `tests/`, `pixi.toml`, `pyproject.toml`, `.github/`.

---

## Verdict

**Qualified no.** I could begin architecture tomorrow on roughly two-thirds of this PRD — the authentication flows, the local development contract, observability, the health and drain interface, and the feature-to-surface decomposition are specified well enough to design against, and the brief's addendum supplies genuine mechanism detail where the PRD deliberately does not repeat it. This is a well-above-average PRD: the tense discipline works, the glossary is enforced, the counter-criteria (CG-1 to CG-4) are the most useful thing in the document, and §4.3's insistence that *where* the refusal is evaluated is itself a requirement is exactly the kind of thinking that prevents a bad architecture.

But three things stop me from producing a design anyone could build from, and all three sit on the critical path:

1. **§4.6 specifies the materializer's properties and never its mechanism.** It is the single largest new build in phase 1 and the least specified thing in the document. The one question that decides its shape — Open Question 2, whether its declarations are single-authored with the FreeMarker template — is assigned to architecture, but architecture cannot answer it without the FreeMarker generator's input contract, which appears nowhere in the document set and belongs to a team named as out of scope (§5). I would be designing the spine of phase 1 against an unknown consumer.

2. **The refusal contract contains a mechanism contradiction and a deployment deadlock** (Findings C-1 and C-2). FR-12 mandates evaluation at settings-module import; FR-15 mandates that the same evaluation resolve the URL configuration. Django cannot do both. And FR-13's unapplied-migrations refusal, evaluated where FR-12 puts it, makes `manage.py migrate` — the release-stage step FR-40 requires — refuse to run. Both fixes change what "refusal" means, so neither is mine to make unilaterally.

3. **The mapper's interface, its user-identity key, and its invocation frequency are unspecified** (Finding C-3). §4.2 is emphatic that the mapper is the only thing permitted to decide what a user may do, then never says what it takes, what it keys a user on, or whether it runs on every Bearer request. Two architects will build materially different — and differently secure — systems from FR-8 and FR-9 as written.

Everything else in this review is recoverable inside architecture. Those three are not.

**One structural observation up front.** The PRD's specification depth tracks how contested a decision was during discovery, not how consequential it is to build. The refusal contract was argued about and is deep on *rationale* while thin on *mechanism*. The materializer was invented late (PRD addendum §1) and is thin on both. The result is a document that reads as more complete than it is: FR-29 through FR-36 are eight numbered requirements that between them do not describe a single mechanism.

---

## 1. What cannot I start?

Places where I would stop and ask the product owner (or a named external party) before designing.

### B-1 — The enterprise developer portal's order surface is undefined. **Severity: high.**
**Cites:** FR-30, §10 (Integration and Dependencies).

FR-30 requires that "the fixture set covers every parameterized value" and that "a parameter added to the order surface without a corresponding fixture causes materialization to fail rather than emit a default." That is a contract against a schema that is never stated. The entire document set names four order inputs: component name, the four feature selections, the component package name (FR-36), and the code-quality project key (FR-36). Whether the portal also supplies the IdP issuer URL, the OIDC client ID, the audience, the team or owner, the repository visibility, the deployment target, or the code-quality organization is unknown — and several of those are needed by FR-5 and FR-10 regardless.

**What would unblock me:** the portal's order-form field list, or a written commitment that the order surface is exactly {component name, package name, project key, four feature booleans} and that any addition is a change request. Without one of those, FR-30's fail-on-missing-fixture rule cannot be implemented, because there is nothing to compare the fixture set against.

### B-2 — The FreeMarker generator's input contract is unknown, and Open Question 2 depends on it. **Severity: high.**
**Cites:** §13 Open Question 2, PRD addendum §1, §5 (non-goal: "the FreeMarker generator engine ... is someone else's").

The PRD assigns Open Question 2 to architecture and says it "should be settled before [the materializer] is built, not after." I agree, and I cannot settle it. Whether the feature-to-surface declarations and the strip/parameterize/keep disposition can be single-authored and consumed by both mechanisms depends entirely on what the FreeMarker generator can read: a YAML manifest, a directory convention, `.ftl` control files, or nothing at all. If the generator can only consume FreeMarker directives interleaved in source, then no phase-1 declaration format survives and the materializer is throwaway scaffolding whose cost should be weighed against a much cheaper alternative. If the generator can read a sidecar manifest, phase-1 work carries forward almost entirely and I should over-invest in the declaration format now.

These are opposite designs. The PRD addendum §1 states the stakes correctly and then leaves the deciding input outside the document.

**What would unblock me:** the FreeMarker generator's documented input contract, or a named owner I can ask, or a product decision to treat the materializer as explicitly disposable so I can optimize it for cheapness instead of longevity.

### B-3 — Is the container image in scope for phase 1? **Severity: high.**
**Cites:** SC-3, FR-37, FR-38, §6.1, §12 factors 3/5/7.

SC-3 requires that "a component is deployable unmodified — containerized by CI and started on the target platform." FR-37 requires "no configuration file is present in the built image." FR-38 requires startup "under an arbitrary non-root UID with a read-only root filesystem." Every one of those is a statement about an image. **There is no Dockerfile in this repository and no workflow that builds a container** (verified: no `Dockerfile*` at root; `grep -rn "docker\|container" .github/workflows/` returns nothing). §6.1's in-scope list names "the deployment interface: environmental configuration, arbitrary UID, declared process model..." and never names an image build.

So either (a) phase 1 builds a Dockerfile and a container-build workflow, which is unlisted work with real weight, or (b) the platform supplies the build (s2i, buildpacks, a shared base image), in which case FR-37 and FR-38 are constraints on *someone else's* build and the component's obligation is different and much smaller. I cannot design the deployment interface without knowing which.

**What would unblock me:** a statement of who owns image construction, and if it is us, its addition to §6.1 as scoped work.

### B-4 — The deployment repository's consumption format for FR-39 and FR-35 is a bilateral contract. **Severity: high.**
**Cites:** FR-39, FR-35, §10.

FR-39 requires that "each combination declares which process types it runs and their commands." FR-35 requires that the provenance stamp's "location and format are stable enough that an external process could enumerate components by version." Both have a named external consumer — the deployment repository, which §5 places "outside this team's control." A declaration format chosen unilaterally is a format the consumer may not read.

I can invent a Procfile, a `[tool.component.processes]` block in `pyproject.toml`, or a `component.yaml`, and all three are defensible. Choosing wrong means the deployment repository hand-maintains what the component was supposed to declare, which is the exact failure FR-39 exists to prevent ("rather than letting the deployment repository guess").

**What would unblock me:** either an agreed format from the deployment-repository owners, or an explicit product decision that we publish a format and they adapt.

### B-5 — What confers Django *permissions*, as opposed to staff status? **Severity: high.**
**Cites:** FR-8, FR-9, FR-11, UJ-1, UJ-2.

FR-9 says the mapper "adds the group memberships the claims assert ... sets staff status from the designated group." FR-11 says "staff status is set exclusively by the mapper from the designated group" and retires `createsuperuser`. In Django, `is_staff` grants entry to `/admin/` and nothing else — a staff user with no permissions sees an empty admin index. UJ-1 and UJ-2 both climax on someone "reaching the admin" and seeing something. Nothing in the PRD says where the `Permission` rows attached to those Groups come from, nor whether anyone ever becomes `is_superuser`.

Three plausible answers, materially different: (i) a designated group also confers `is_superuser`; (ii) Django `Group` objects are seeded with permissions by a data migration and claims only bind users to them; (iii) permissions are managed by hand in the admin, which is impossible for the *first* administrator since `createsuperuser` is retired — a genuine bootstrap deadlock.

Related and unanswered: if a claim asserts a group that does not exist as a Django `Group`, does the mapper create it or ignore it? That single choice decides whether IdP group taxonomy silently becomes Django group taxonomy.

**What would unblock me:** a decision on whether superuser exists in a deployed component and where group permissions originate.

### B-6 — The local sign-in entry point is undesigned, and it is a new credential path. **Severity: high.**
**Cites:** FR-19, FR-13, FR-17, §4.4.

FR-19 requires that "local sign-in constructs a synthetic claims payload and passes it to the mapper," and FR-32/SC-4 require a persona to sign in during the smoke check. Nothing says what the *entry point* is: a development-only login view, a development-only authentication backend, a management command that writes a session, or a query-parameter impersonation shim. These have very different security surfaces, and this path is materialized into **every** component (it is part of the local contract, and `src/config/` is on FR-36's keep list).

This matters more than a design-detail question because of Finding C-4 below: FR-13's refusal list does not mention it.

**What would unblock me:** a product decision on the shape of local sign-in, or acceptance that architecture chooses it *and* that FR-13's condition list is reopened to cover it.

### B-7 — When does the twelve-combination gate run? **Severity: medium.**
**Cites:** FR-31, CG-2, §9 (Cost).

FR-31 says all twelve are gated; it never says on what trigger. The brief says "on every template change." Today CI runs on every push and PR to `main`/`develop` across three operating systems. Twelve combinations × a full gate is a large multiple of the current cost, and CG-2 forbids me from reducing the set to manage it. The lever I have left is the *trigger* (every PR vs. merge queue vs. nightly), and that is a product and platform decision with a real correctness consequence: a nightly gate means a broken combination can be merged.

**What would unblock me:** a trigger policy, and confirmation that the twelve-combination gate runs on Linux only (running it on the existing three-OS matrix would be 36 gate runs, and `gunicorn` is already declared POSIX-only in `pixi.toml:69-78`, so the Windows leg cannot exercise the declared process model anyway).

### B-8 — FR-36's disposition list does not partition the repository, and its own keep rule leaks accelerator machinery. **Severity: medium (but trivially fixable, and it must be fixed before the materializer is designed).**
**Cites:** FR-36.

FR-36 gives three lists (Stripped / Parameterized / Kept). Their union does not cover the tracked tree, and the PRD does not state a default disposition for an unlisted path. A deterministic materializer (NFR-5) cannot be built on a partial partition.

Verified gaps in the tracked tree:
- `docs/index.md` — tracked, in none of the three lists (only `docs/development.md` and `docs/observability.md` are named).
- `.github/` is listed **Kept in its entirety**, which ships the accelerator's own machinery into every component — directly contradicting FR-36's own headline. Tracked under `.github/`: fourteen BMad agent definitions in `.github/agents/`, `.github/copilot/settings.json`, `.github/CODEOWNERS`, `.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md`, and workflows `release.yml`, `stale.yml`, `labeler.yml`, `sonarqube.yml`. At minimum `.github/agents/` and `.github/copilot/` belong on the strip list and `sonarqube.yml` on the parameterize list.

**What would unblock me:** a default disposition for unlisted paths (I would argue for *strip*, so an unlisted addition fails safe rather than leaking), and `.github/` broken down to file granularity.

---

## 2. What would I get wrong? (Expensive ambiguities)

Places where two competent architects produce materially different designs.

### A-1 — The materializer's mechanism. **Severity: critical.**
**Cites:** FR-29, FR-24, NFR-5.

FR-29 states properties (self-contained, deterministic, all-features output equivalent to the reference application) and no mechanism. At least three architectures satisfy every stated consequence:

- **Subtractive with in-source markers.** Copy the tree; strip regions delimited by comment markers (`# feature:celery ... # /feature:celery`) and delete declared files. Keeps the reference application runnable and gateable as itself. Costs: markers are noise in source, and marker-stripping inside `pixi.toml` / `settings/base.py` is fragile.
- **Subtractive with an external manifest.** A YAML/TOML manifest declares each feature's file list, settings fragments, dependency names, and test modules; the materializer executes it. Keeps source clean; the manifest drifts from source silently, which is the very orphan class §4.5 exists to catch.
- **Composition of fragments.** Settings and dependencies are assembled from per-feature parts rather than subtracted from a whole. The cleanest output; it means the "reference application" is itself a materialized artifact, which changes what this repository *is* and how its own gate works.

These are not stylistic variants. They differ in whether the reference application remains a real Django application, in what the FreeMarker template can later reuse (B-2), in how orphan detection is preserved (FR-28), and in cost by a factor of several.

Note also that FR-29's third consequence — "materialized output for the all-features-selected combination is equivalent to the reference application" — pulls hard toward subtractive, and **"equivalent" is undefined**. Byte-identical is a strong, cheap, checkable property and would settle much of this. Functionally equivalent is nearly uncheckable.

**What would unblock me:** a decision on subtractive vs. compositional, and a definition of "equivalent" in FR-29.

### A-2 — Does the mapper run on every Bearer request? **Severity: critical.**
**Cites:** FR-9, FR-5, FR-8.

FR-9: "On every authentication the mapper resolves or creates the user, adds ... removes ... sets staff status ... and emits a structured log line recording what changed." For the interactive flow, "every authentication" is once per login — cheap and obviously right. For the programmatic flow, DRF authenticates **every single request**. Read literally, FR-9 mandates a user lookup, a group-membership diff, up to two M2M writes, a staff-status write, and a log line on every API call.

Architect A implements it literally: correct per the text, and a service-to-service caller at moderate volume produces sustained write traffic and row contention on `auth_user_groups` for a single identity, plus a log line per request. Architect B caches the mapping keyed by token `jti`/`exp` and re-syncs at most once per token lifetime: performant, and it silently reintroduces exactly the revocation latency FR-9 exists to eliminate — the property §9 calls out as security-critical.

Both are defensible readings. They are different products.

**What would unblock me:** an explicit statement of mapper invocation policy for the programmatic flow, and if caching is permitted, the accepted staleness window (which is Open Question 1 wearing a different hat — and Open Question 1 is scoped only to *sessions*, so it does not cover this).

### A-3 — What key identifies the user? **Severity: critical (security).**
**Cites:** FR-9 ("resolves or creates the user"), FR-8.

The single most consequential field in the mapper is never named. If the mapper resolves users by `email`, and the IdP issues tokens with an unverified or mutable email claim, then two identities can collide and one can take over the other's account and its groups. If it resolves by `sub`, that cannot happen, but `sub` is opaque and the existing `users.User` model and `SocialAccountAdapter.populate_user()` are almost certainly email-oriented today. If it resolves by `preferred_username`, the value is mutable at most issuers.

This is precisely the class of decision this product exists to make once and encode. It is absent.

**What would unblock me:** name the identity claim, and state the behaviour when it is missing from a token.

### A-4 — `ModelBackend` refusal: string match or subclass check? **Severity: high (security).**
**Cites:** FR-13 ("`ModelBackend` present in `AUTHENTICATION_BACKENDS`").

Verified in `src/config/settings/base.py:133-136`:

```
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
```

`allauth.account.auth_backends.AuthenticationBackend` **is a subclass of `ModelBackend`**, and it must remain present for allauth to work. So:

- Architect A writes an exact-string check for `"django.contrib.auth.backends.ModelBackend"`. It passes with allauth present — correct today, and blind to any future backend that subclasses `ModelBackend` under another name, which is the whole point of §4.3.
- Architect B writes `issubclass(import_string(b), ModelBackend)`. It refuses the *required* allauth backend and no deployed component can ever start.

The correct design is a third thing (an allowlist of permitted backend paths, which is what FR-17 already asks for) — but FR-13 as written points at the two wrong answers and FR-17 is a separate requirement in a separate list. **The refusal condition and the allowlist should be one mechanism, not two**, and the PRD keeps them apart.

**What would unblock me:** restate FR-13's credential-path condition as "`AUTHENTICATION_BACKENDS` differs from the approved allowlist" and merge it with FR-17.

### A-5 — How allauth's OIDC provider and the Site are configured. **Severity: high.**
**Cites:** FR-4, FR-37, §12 factor 3.

FR-4 requires `allauth.socialaccount.providers.openid_connect` and FR-37 requires that a component "starts from environment variables alone" with no configuration file in the image. allauth offers two provider-configuration paths: a settings-resident `SOCIALACCOUNT_PROVIDERS[...]["APPS"]` list (env-drivable, satisfies FR-37) or database-resident `SocialApp` rows (does not — a freshly deployed component would not authenticate until someone inserted a row, and FR-40 forbids the component from migrating itself).

Verified current state: `SOCIALACCOUNT_PROVIDERS` does not appear in `base.py` at all — none of this is configured today, so the choice is entirely open. But `base.py:45,97,128` show `SITE_ID = 1`, `django.contrib.sites` installed, and `MIGRATION_MODULES = {"sites": "django_service.contrib.sites.migrations"}` — meaning the Site domain, which allauth uses to build callback URLs, **is already database-resident configuration seeded by a data migration**. That is a live tension with FR-37 and with §12's "factor 3: Config — Satisfied", and it will differ per deployed environment.

**What would unblock me:** a decision that provider configuration is settings-and-environment only, plus a decision on how the Site domain becomes environment-driven (or an explicit acceptance that it is a release-stage data step).

### A-6 — Is the 90% coverage floor per-combination or aggregate? **Severity: high.**
**Cites:** FR-31, SC-1, CG-1, FR-28.

FR-31 puts each of twelve combinations through "coverage at or above ninety percent including templates." Per-combination is the only reading consistent with "a failure in any one combination fails the run," and it is also the reading nobody has tested. Coverage arithmetic is not stable under subtraction: removing the server-rendered UI removes user-facing views *and* their tests, and removes templates from the denominator — the resulting percentage can move in either direction. It is entirely possible that some combination lands at 88% for reasons that are structural rather than defective, and CG-1 forbids the obvious remedies (excluding files, pragmas, dropping template measurement).

This is a real risk to SC-1 that nobody has measured, and the answer changes the design: if the floor is fragile, the materializer must emit per-combination coverage configuration, which is another surface each feature must declare.

**What would unblock me:** a measurement of actual coverage for two or three of the sparser combinations before the floor is committed to as a hard gate, or a stated policy for a combination that misses the floor structurally.

### A-7 — Where the "am I deployed?" declaration lives and what it is called. **Severity: medium.**
**Cites:** FR-12.

FR-12 is admirably clear that the declaration is read from the environment and **fails closed** (absent or unrecognized ⇒ deployed). It does not name the variable, its accepted values, or how the *test suite* declares itself. That last one is not cosmetic: `pixi run test-cov` runs `pytest tests/` against a test settings module in an environment that has declared nothing, so under FR-12's fail-closed rule the entire suite would treat itself as deployed and refuse to start. Every developer's first run of the suite after FR-12 lands will fail unless the fixture story is designed alongside it.

**What would unblock me:** nothing from the PO — this is mine — but it needs to be designed *with* FR-12 rather than after, and it is a place where a careless design breaks every test at once.

### A-8 — What "the JWKS trust anchor is not the configured IdP" actually compares. **Severity: high.**
**Cites:** FR-13 (fifth condition), FR-20.

The PRD calls this out as the subtlest of the eight and then spends one sentence on the check itself. The condition is circular as written: the JWKS location *is* configuration, so "not the configured IdP" needs a second, independent source of truth about what the IdP is. Candidate designs:

- Refuse if the JWKS URL scheme is `file://` or its host is loopback/private — a denylist, and §4.3's own argument against denylists applies.
- Require the JWKS URL to be *derived* from the OIDC issuer rather than independently configurable, and refuse if an override is set. Structurally strongest; removes a knob the local contract (FR-20) needs.
- Require the JWKS host to match the issuer host. Cheap, and defeated by a local issuer claim.

Option 2 conflicts with FR-20, which requires local settings to "point the JWKS location at that key." Reconciling those two is a genuine design problem and the PRD does not acknowledge it exists.

**What would unblock me:** nothing external — but this needs to be recognized as a designed mechanism rather than a one-line condition, and FR-13/FR-20 need to be read against each other before either is built.

---

## 3. Is depth proportionate to risk in §4.3, §4.2, and §4.6?

Short answer: **§4.3 no (deep on rationale, thin and in two places wrong on mechanism), §4.2 no (thin exactly where the security lives), §4.6 emphatically no.**

### §4.3 — The Refusal Contract

The reasoning is the best in the document. FR-12's insight that a guard behind the door it is guarding cannot fire is correct and non-obvious. FR-17's inversion from denylist to allowlist is the right instinct. FR-15's observation that a settings-only check cannot see a URL is verified true (`src/config/urls.py:11,39` route `obtain_auth_token` at `/api/auth-token/` independent of any setting).

But the mechanism does not survive contact with Django.

#### C-1 — FR-12 and FR-15 cannot both be satisfied by one mechanism. **Severity: critical.**

FR-12: "The conditions are evaluated by shared code that **every settings module imports**."
FR-15: the credential-path refusal "**resolves the URL configuration** and fails on a reachable token-minting route."

At settings-module import time the Django app registry is not populated. Resolving the URLconf imports `config/urls.py`, which imports views, which import models — raising `AppRegistryNotReady`. FR-15 cannot execute where FR-12 places it.

Worse, the natural alternatives each reintroduce the hole FR-12 exists to close:
- **`AppConfig.ready()`** — requires the checking code to live in an installed app, so a settings module that omits that app from `INSTALLED_APPS` skips the contract. Same failure mode, new door.
- **`django.core.checks` system checks** — only run for `manage.py` commands and `runserver`, and are skippable with `--skip-checks`. A deployed component served by `gunicorn config.asgi:application` **never runs system checks at all**, which makes this the worst option available and the most likely one to be chosen, because it looks idiomatic.
- **An explicit call in `config/asgi.py`** — runs on the real deployed boot path, but is one file the entrypoint could bypass, and does not cover `worker`/`beat`/one-off admin processes (FR-39, FR-43).

So the contract must be split across at least two evaluation points with different reachability guarantees, and the PRD asserts a single one that cannot work. This is the highest-consequence surface in the product (§11: "One check carries the whole guarantee") specified with a mechanism that does not exist.

**What would unblock me:** acceptance that FR-12 becomes "evaluated at every process entry point, by code no settings module can decline to load," with the entry points enumerated (`asgi.py`, `wsgi.py`, `manage.py`, the Celery app) and the split between import-time and post-`django.setup()` conditions made explicit.

#### C-2 — The unapplied-migrations refusal deadlocks the release stage. **Severity: critical.**

FR-13: "Unapplied migrations exist → refusal."
FR-40: "Documentation states that the deployment pipeline runs migration before new pods begin serving," and "no entrypoint runs migrations."

If the refusal is evaluated at settings import (FR-12) or at `AppConfig.ready()`, then `manage.py migrate` — which does both — refuses to start, and the component can never be migrated. The condition forbids the only action that clears it. The same applies to `manage.py clearsessions` (FR-43) and `collectstatic` during a release.

The PRD gives no carve-out. Architect A notices and scopes the migration condition to serving processes only; architect B does not and ships a component that cannot be deployed a second time. This one will be found in about ninety seconds of real use, but it will be found *after* the refusal contract is built and tested, because FR-16's tests assert refusal in the forbidden state and would all pass.

**What would unblock me:** a decision on which conditions apply to which process types, which in turn requires FR-39's process model to exist before the refusal contract is designed (see Finding S-3).

Related and worth noting: NFR-1 concedes "no query beyond the migration state," which means startup now requires a reachable database. Combined with FR-41's own rationale — a liveness probe that touches the database converts a brief outage into a crash loop — a database blip during a rolling deploy will now fail every *new* pod at boot. That is arguably correct (an unmigrated component should not serve), but it is a deliberate availability trade the PRD does not name.

#### C-3 — The eight conditions do not cover the credential path this PRD creates. **Severity: critical.**

FR-13's credential-path condition enumerates exactly the four inherited bypasses from the brief's addendum §1.1: `ModelBackend`, `ACCOUNT_LOGIN_METHODS`, `DJANGO_ADMIN_FORCE_ALLAUTH`, `authtoken`/`TokenAuthentication`, plus the `obtain_auth_token` route.

FR-19 introduces a **fifth** local credential path — synthetic-claims persona sign-in — which is new code this PRD requires, ships in `src/config/` (FR-36 keep list) into every component, and by construction bypasses the IdP entirely. It appears in none of the eight conditions.

Whether FR-17's allowlist catches it depends on the shape chosen in B-6: an authentication backend or a URL route would be caught; a management command or a middleware shim would not. The PRD's own §4.3 principle — "each separate mechanism gets its own check" — demands an explicit ninth condition, and the PRD's own §4.3 note is a warning about exactly this failure (a mechanism named in one section and missing from the settled list in another).

**What would unblock me:** an explicit refusal condition for the local sign-in path, written once its shape is decided.

#### C-4 — Depth verdict for §4.3
Eight conditions, four supporting FRs, a strong rationale — and a mechanism that cannot execute (C-1), a deadlock (C-2), a missing condition for the product's own new bypass (C-3), a circular check (A-8), and a refusal predicate that points at two wrong implementations (A-4). **Depth is disproportionate: the FR count and the quality of the prose create an appearance of settledness that the mechanism does not have.** This section needs another pass before it is built, and it is the section where being wrong is most expensive.

### §4.2 — The shared authorization mapper

FR-8 settles placement (`src/config/authorization/`) with a good argument, and names all three callers. FR-9 specifies the five steps and — correctly and importantly — insists on removal and on per-authentication re-sync. The rejected-alternatives work in the brief's addendum §1.3 is thorough.

What is missing is everything about the mapper as a *component*:

- **Its interface.** Raw claims `dict`, or a normalized value object? Who performs the dotted-path lookup that FR-10 requires (`realm_access.roles` is nested; `groups` is not)? Does it return a `User`, or mutate and return `None`? Is it one function or a small package with a resolver, a differ, and a logger? FR-8 names a *directory* and never a signature — and it is the one thing three independent callers must agree on.
- **Its identity key** — Finding A-3, critical, security-relevant.
- **Its invocation frequency** — Finding A-2, critical.
- **Its group-not-found behaviour** — create or ignore (B-5).
- **Its missing-claim behaviour.** FR-10 refuses at *startup* if the claims contract is unconfigured. It says nothing about a *token* that lacks the configured claim at runtime. Reject with 401? Authenticate with zero groups? The second is fail-closed for authorization but grants authentication, which for an API is a meaningfully different posture.
- **Concurrency.** Two simultaneous Bearer requests for the same identity both diffing and rewriting `auth_user_groups` is a straightforward race. Whether the mapper runs in a transaction, and whether it is idempotent, is unstated. Under A-2's literal reading this is not a rare interleaving, it is the steady state.
- **Failure mode.** If the mapper raises mid-sync, is the user left half-mapped? A partially applied group diff that removed memberships before adding them is a privilege *loss*; the reverse ordering is a privilege *retention*. The ordering in FR-9 (add, then remove) happens to be the safer one, but nothing says it is deliberate.

**Depth verdict: disproportionate.** §4.2 is deep on *which library* and *where the file goes* — the questions that were contested — and thin on the contract that three callers must share, which is where divergence actually happens. §9 states that "divergence between the interactive and programmatic flows is the default outcome of independent implementation." Correct — and an unspecified interface is how independent implementation happens even when everyone agrees there is one mapper.

### §4.6 — The combination materializer

**Depth verdict: severely disproportionate — the least specified and largest new build in phase 1.**

FR-29 through FR-36 are eight requirements that between them describe: what the output must satisfy (self-contained, deterministic, equivalent at the all-on combination), what it must carry (fixtures, provenance stamp), what it must refuse, what it must strip, and how failures are reported. They do not describe **how a combination is produced**. A-1 sets out three architectures that satisfy every listed consequence and cost wildly different amounts.

Additional specifics that are absent and needed:

- **Where output goes and how it is gated.** A materialized combination must run its own gate (`pixi run ci`), which means resolving a pixi environment per combination. Twelve pixi solves, or twelve `pixi install` runs, is a large and unbudgeted cost, and `pixi.lock` is on FR-36's *keep* list — but a lock file for the all-features dependency set is wrong for a combination that dropped Celery and Redis. **FR-36 keeping `pixi.lock` unmodified contradicts FR-2 and FR-27**, which require the manifest to contain no package from an unselected feature. Either the materializer re-locks (slow, and breaks NFR-5's determinism claim unless pinned), or the lock is regenerated per combination and committed as a fixture, or FR-36's disposition for `pixi.lock` is wrong. None of the three is chosen.
- **How the twelve smoke checks work.** FR-32 requires each combination to boot, return 200 from readiness, and authenticate a persona. That is twelve application boots with database creation, migrations, persona seeding, and a keypair generation — sequenced somehow, in some harness, reported somehow. No requirement describes the runner.
- **FR-34's reporting mechanism.** "A run using a reduced set reports the reduction and the combinations not covered" — reports where, to whom, in what artifact? This is the mechanism that makes CG-2 enforceable rather than aspirational, and it is one sentence.
- **The provenance stamp's format** — B-4.

The PRD addendum §1 is candid that the materializer was invented during PRD discovery to close a gap in the brief. That is good product work. The consequence is that the newest and largest mechanism in phase 1 received the least specification, and §4.6 is the section I would most need rewritten before designing.

---

## 4. Is the current-state picture accurate?

I spot-checked the highest-consequence claims. **Most are accurate — the PRD is unusually honest about what is unbuilt — but four are wrong, and one of them undercuts the product's headline claim.**

### Verified accurate

| Claim | Cite | Result |
|---|---|---|
| sqlite refusal exists at `production.py:26-28` | FR-13, §4.3 | **Correct**, exactly those lines: `if DATABASES["default"]["ENGINE"].endswith("sqlite3"): raise ImproperlyConfigured` |
| Four credential paths live and unguarded | §4.2 | **Correct.** `base.py:133-136` (`ModelBackend`), `base.py:340` (`ACCOUNT_LOGIN_METHODS = {"username"}`), `base.py:271` (`DJANGO_ADMIN_FORCE_ALLAUTH` default `False`), `base.py:112` (`rest_framework.authtoken`), `base.py:358-360` (`TokenAuthentication`), `urls.py:11,39` (`obtain_auth_token` at `/api/auth-token/`). Brief addendum line numbers have drifted by 2-3 lines; immaterial. |
| `secure_admin_login` wrapper already written, flag-gated | FR-7 | **Correct**, `src/django_service/users/admin.py:11` |
| No health route exists | FR-41 | **Correct.** No `health`/`readiness`/`liveness` match in `urls.py` or `api_router.py` |
| No workflow declares PostgreSQL | FR-31, §10 | **Correct.** `grep -rn "services:\|postgres\|DATABASE_URL" .github/workflows/` returns nothing |
| `src/config/observability/` exists as the cross-cutting home | FR-8 notes | **Correct**, and `src/config/authorization/` does not exist |
| Component package is `src/django_service/` | FR-36 | **Correct** |
| `sonar-project.properties` hardcodes the project key | FR-36 | **Correct** |
| `SESSION_ENGINE` not set explicitly | §12 factor 6 | **Correct** — absent from `base.py` |
| Template coverage machinery is real | FR-28, CG-1 | **Correct.** `pyproject.toml:173` `plugins = ["django_coverage_plugin"]`, `pyproject.toml:175-178` restricts to `html`, `pixi.toml:141` `COVERAGE_CORE = "ctrace"` |
| PyJWT and cryptography are new dependencies | §4.2 | **Correct** — neither appears in `pixi.toml` |
| `django-celery-beat` still under `[pypi-dependencies]` | PRD addendum §4 | **Correct**, `pixi.toml:90`, with the now-historical rationale at lines 84-89 |
| Only one refusal is tested as a refusal | FR-16 | **Correct.** `tests/unit/test_settings.py` has `test_production_refuses_sqlite` and no other refusal test |

### Wrong or misleading

#### D-1 — §12 factor 4 claims object storage attaches by environment variable, "Satisfied". **It does not exist at all.** **Severity: high.**

`grep -rn "STORAGES\|django-storages\|storages\|boto3" src/ pixi.toml` returns exactly one hit: `src/config/settings/production.py:79`, a `STORAGES` block that is Django's built-in static/default file storage configuration, not an S3 backend. There is no `django-storages`, no `boto3`, no S3 configuration, no object-storage application code.

The brief's addendum §3 says this plainly ("Object storage libraries: none present. Genuinely greenfield"). The PRD's factor table contradicts its own source. **Consequence beyond the table:** the Glossary defines the reference application as one "with every selectable feature present and exercised," and §6.1 puts that in scope — so one of the four features is entirely unbuilt, and building it is unlisted work that the materializer depends on (Finding S-1).

#### D-2 — "The gate" is not a single thing in CI, and one of its four steps runs twice a month. **Severity: medium.**

The Glossary defines *Gate* as "tests, coverage at or above ninety percent including templates, strict type checking, lint, and build," and FR-31 requires each of twelve combinations to pass it. §10 flags exactly one gap — the missing PostgreSQL service. The picture is more fragmented than that.

`pixi.toml:197` defines `ci = { depends-on = ["test-cov", "lint", "typecheck", "build"] }` — the gate exists as a single invocable task. **No workflow calls it.** Instead it is split three ways:

- `ci.yml` (push/PR to `main`,`develop`, three OSes): `pixi run test` — which is `pytest tests/unit/` only (`pixi.toml:185`) — plus `lint` and `typecheck`.
- `sonarqube.yml` (push to `main` and every PR): `pixi run test-cov` — the full suite with `--cov-fail-under=90` and template coverage. Verified as a hard step with no `continue-on-error` anywhere in `.github/workflows/`.
- `release.yml` (cron, the 7th and 21st of each month, plus manual dispatch): `test-cov` and `build`.

So the 90% floor and the template-coverage orphan detector **are** enforced per change — I initially read this wrong from `ci.yml` alone, and want to be clear that they are enforced. Two things follow that still matter:

1. **`pixi run build` is enforced only on a fortnightly cron.** A change that breaks packaging can sit on `main` for up to two weeks. The Glossary's gate includes build; per-change CI does not.
2. **The harness will be the first consumer of `pixi run ci`, a task no workflow has ever run.** FR-31 needs one invocable gate per materialized combination, and `pixi run ci` is the only thing shaped like one. It should be exercised against the reference application before twelve combinations depend on it.
3. **The orphan detector lives in a workflow named for code-quality reporting.** CG-1 calls template coverage the only signal that catches incomplete feature extraction, and SC-2 rests on it. Its home is a SonarCloud workflow — a plausible target for a well-meaning "SonarCloud is flaky, make it non-blocking" change that would destroy SC-2 without anyone deciding to. Given CG-1's existence, the coverage step belongs in the same workflow as the rest of the gate.

Also note that FR-36 keeps `.github/` wholesale (B-8), so every generated component inherits this three-workflow split, including a SonarCloud workflow — which FR-36 does correctly flag for parameterization of the project key.

#### D-3 — FR-48's testable consequence is unsatisfiable as written. **Severity: medium.**

FR-48 requires "a test or gate step asserts that the package-index dependency block is empty." Verified `pixi.toml:82-90`:

```
[pypi-dependencies]
django-15-factor-base = { path = ".", editable = true }
...
django-celery-beat = ">=2.9,<3"
```

The block **can never be empty**: the project's own editable self-install lives there and must. The assertion FR-48 mandates would fail permanently. The requirement should read "contains no third-party package" or "contains only the editable self-install."

Separately, §12 factor 2 says "resolved from the approved channel with **no exceptions** ... Satisfied," and FR-48 says the exception "**is resolved**." Both are true upstream and false in this repository — `django-celery-beat` is still at `pixi.toml:90`. The PRD addendum §4 is explicit that the repository change was "deliberately not performed during this PRD run," but the factor table does not carry that qualifier. Minor, and worth fixing so the table is not read as ground truth.

#### D-4 — §12 factor 8 "Satisfied, declared" overstates FR-39. **Severity: low-medium.**

Factor 8 cites FR-39 (process model declared per combination, beat as one replica) and marks it Satisfied. FR-39 is a phase-1 must-have that is not built: nothing in the repository declares a process model in any consumable form, and B-4 notes the format is not even chosen. "Declared" is doing a lot of work — it appears to mean "decided in the brief," which is the same status the table gives factors 5 and 9 as "Decided, not implemented." The inconsistency makes the table less trustworthy than it should be. The same reading applies to factor 12 ("Admin processes — Satisfied") when FR-11 and FR-43 are both unbuilt.

### D-5 — An undeclared surface: `src/config/websocket.py`. **Severity: medium.**

`src/config/websocket.py` is a tracked 13-line ping/pong ASGI websocket handler. It appears in **no** planning document — not the brief, not the brief addendum's feature-to-surface matrix (§2), not the PRD's immovable core (FR-1), not any of the four selectable features (FR-24), and not FR-36's disposition lists. Because it lives under `src/config/`, FR-36's keep rule ships it into every generated component.

Either it is part of the immovable core (in which case FR-1 should say so and something should test it — it is untyped, which is also a question under `mypy strict`), or it is dead scaffolding of exactly the kind the brief's audit was meant to eliminate ("five packages with zero references, two unreachable template overrides"). This is a small thing, but it is a live counterexample to the claim that the reference application's surface is fully enumerated — and FR-24 requires every feature to declare its surface completely.

### D-6 — FR-46 asserts the ASGI instrumentor is "present and active"; there is nothing to assert against. **Severity: medium.**

FR-46's testable consequence: "The ASGI instrumentor is present and active in all twelve combinations; without it, ASGI requests produce no spans at all." The brief's problem statement leads with this ("whether the OpenTelemetry ASGI instrumentor is optional — it is not").

Verified current state: `opentelemetry-instrumentation-asgi` is declared at `pixi.toml:53`, locked, and present in all six environment legs — with a comment at `pixi.toml:49-52` explaining that it exists precisely so `DjangoInstrumentor`'s `_is_asgi_supported` returns True. But it is **never imported in source**. `src/config/observability/telemetry.py:134-137` instruments exactly four things — Django, Celery, Psycopg, Redis — and the ASGI instrumentor is consumed *implicitly* by `DjangoInstrumentor`.

So "present" is a dependency-manifest assertion (easy) and "active" has no call site to assert on. A test written naively against FR-46 would assert an import or a package presence and would pass in a combination where ASGI tracing was in fact broken — which is exactly the failure the brief says this requirement exists to prevent. The only honest test is a behavioural one: drive a request through the ASGI application and assert a span was produced.

This is small but worth naming because it is the PRD's own headline example of a decision that must not be silently lost, and its stated consequence does not test the thing it cares about.

---

## 5. Sequencing risk

The PRD priority-ranks feature groups (almost everything is "Phase-1 must-have") and defers epic ordering. Reading the dependencies, there is a clear trap and it is the opposite of what the narrative suggests.

### S-1 — The harness is narratively first and technically last. **Severity: critical.**

§4.6 and §1 both argue, correctly, that the materializer must exist *before* the FreeMarker transition. That is an argument about phase 1 versus phase 2. It is easy to misread as "build the harness first within phase 1," and the two verification levels have very different readiness:

- **The materializer + PostgreSQL gate level (FR-29, FR-31)** genuinely can go early. It needs feature-surface declarations and a complete reference application, and nothing from §4.2 or §4.3.
- **The smoke-check level (FR-32) cannot.** It requires the component to boot (FR-18), **readiness to return 200** (FR-41 — no health route exists today), and **a persona to sign in** (FR-19 → the mapper FR-8 → the claims contract FR-10 → the local sign-in path B-6). So FR-32 transitively depends on nearly all of §4.2, §4.4, and the health endpoints in §4.7.

An epic plan that groups "§4.6 The Verification Model" as one unit and schedules it early will stall halfway through. The two levels must be split across the plan: materializer early, smoke check late.

### S-2 — Object storage is a hidden prerequisite of the materializer. **Severity: high.**

FR-29 materializes combinations "from the reference application." Per D-1, one of the four features does not exist in the reference application. Twelve combinations of a three-feature reference application is not what SC-1 claims, and retrofitting the fourth feature after the materializer is built means re-cutting every surface declaration and re-running every combination. Object storage must be built *before* the materializer, and it is currently invisible in the plan because §12 marks it Satisfied.

### S-3 — The refusal contract cannot be designed before the process model. **Severity: high.**

Per C-2, the refusal conditions must be scoped by process type (a `migrate` job must not refuse on unapplied migrations; a `beat` process arguably should not resolve the URLconf at all). FR-39's process model is in §4.7, which reads as a later, more peripheral group than §4.3. Building §4.3 first produces a monolithic contract that then has to be re-cut per process type — and the tests written under FR-16 will all still pass, so the re-cut will not be prompted by a failure.

Additionally, two of the eight conditions are **feature-conditional** (FR-14). The refusal module therefore has its own feature surface and is itself materialized per combination — so §4.3 also depends on §4.5's surface declarations. §4.3 sits downstream of two groups that look independent of it.

### S-4 — PostgreSQL in CI should be the first commit, not part of the harness epic. **Severity: high.**

The suite has never run against PostgreSQL (verified). Adding it will surface latent failures in existing code — sqlite is permissive about DDL, constraints, transaction semantics, and JSON/array types. If PostgreSQL arrives as part of FR-31 (the twelve-combination gate), those latent failures appear simultaneously across twelve combinations, at the same moment as the materializer's first real run, and will be misattributed to the materializer. Landing PostgreSQL against the single reference application first isolates that cost to one clearly-scoped change.

A related, cheaper prerequisite from D-2: **consolidate the gate behind `pixi run ci` in one workflow before the harness depends on it**. FR-31 assumes a single invocable gate; today the gate is three workflows on three triggers, `build` runs fortnightly, and `pixi run ci` has never executed in CI. The harness should not be the first thing to discover that.

### S-5 — The package rename is a repo-wide refactor disguised as a parameterization bullet. **Severity: medium-high.**

FR-36 lists `src/django_service/` under "Parameterized" as one item among seven. Renaming that package touches settings (`INSTALLED_APPS`, `AUTH_USER_MODEL`, `MIGRATION_MODULES`, template and static directories), `urls.py`, `api_router.py`, every module under `tests/` (13 test modules import it), `pyproject.toml`, coverage configuration, and `sonar-project.properties`. It is a mechanical change that conflicts with every other in-flight branch simultaneously.

It should land early and alone, before the authentication rewire and the refusal contract create long-lived branches in the same files.

### S-6 — FR-17's allowlist must land with FR-6, not after it. **Severity: medium.**

FR-6 removes the static-token surface; FR-17's allowlist is what makes the removal permanent. Sequenced after, there is a window in which the paths can return unnoticed — and §4.3's own argument (the JWKS condition was found by a human reading two sections against each other, "which is not a mechanism") applies exactly here. They are one change.

### S-7 — FR-28's orphan detection can die silently during the harness build. **Severity: medium.**

The template-coverage machinery exists today (`django_coverage_plugin`, `COVERAGE_CORE=ctrace`). It depends on a non-obvious environment variable and on integration tests that exercise template rendering (`tests/integration/test_template_rendering.py`). When the materializer emits twelve combinations, each needs that environment variable set and those tests present, or coverage will report a healthy number with templates silently unmeasured — SC-1 passes, SC-2 is destroyed, and CG-1 is violated without anyone choosing to violate it. This is the highest-value thing to assert explicitly in the harness, and FR-28's consequence ("an orphaned template override introduced deliberately into a combination causes that combination's gate to fail") is the right test. It should be written as a *negative control that runs in CI*, not as a one-time manual verification.

### Suggested ordering implied by the above

1. Consolidate the gate behind one `pixi run ci` invocation in one workflow — D-2.
2. PostgreSQL service in CI against the reference application — S-4.
3. Package rename / parameterization groundwork — S-5.
4. Object storage feature, completing the reference application — S-2.
5. Process model declaration (FR-39) — needed by S-3.
6. Feature-surface declarations (FR-24) — needed by the materializer and by FR-14.
7. Refusal contract (§4.3), scoped by process type — after 5 and 6.
8. Authentication rewire and the mapper (§4.2), with FR-6 and FR-17 in one change.
9. Local development contract (§4.4), including the local sign-in path and its refusal condition.
10. Health endpoints and drain (FR-41, FR-42).
11. Materializer + PostgreSQL twelve-combination gate (FR-29-31, FR-33-36).
12. Smoke-check level (FR-32) — last, because it depends on 8, 9, and 10.

This is offered as evidence of the dependency structure, not as a proposed epic plan.

---

## 6. Minor defects worth fixing in the next pass

- **Broken cross-references, both off by one in §4.6.** FR-18's consequence cites "the smoke check of **FR-33**" (FR-33 is the invalid-combination refusal; the smoke check is FR-32). FR-25's consequence cites "the materializer refuses the invalid pairing with a stated reason (**FR-34**)" (FR-34 is the coverage-bound reporting rule; the refusal is FR-33). Both are consistent with an FR being inserted into §4.6 without references being renumbered — worth re-checking every reference in that section.
- **FR-1's third consequence relies on a check the smoke check does not perform.** "A combination in which the Django admin is unreachable fails the smoke check" — but the Glossary and FR-32 define the smoke check as boot + readiness 200 + persona sign-in. Admin reachability must be added to the smoke check definition or the consequence moved.
- **§4.7's group priority contradicts FR-43's own priority note.** The header says "Phase-1 must-have, except FR-43 which is **Next**"; FR-43's note splits it (session engine phase-1, scheduling Next). The note is right; the header should match.
- **FR-34's title and first consequence disagree.** The title is about reporting a bound; the first consequence states the exhaustive-until-32 policy. Two requirements in one FR, and the policy half is what §6.2 and §9 cite.
- **The brief's addendum §6.3 should be reconciled to eight conditions**, as PRD §4.3 already instructs — and to **nine**, if C-3 is accepted.
- **FR-36's `pixi.lock` disposition conflicts with FR-2 and FR-27** — see §3, §4.6 depth. Needs an explicit decision, not a list entry.

---

## 7. Summary of findings by severity

| ID | Finding | Severity | Cite |
|---|---|---|---|
| C-1 | FR-12 and FR-15 cannot both be satisfied by one mechanism; system checks never run under ASGI | Critical | FR-12, FR-15 |
| C-2 | Unapplied-migrations refusal deadlocks `manage.py migrate`, the step FR-40 requires | Critical | FR-13, FR-40 |
| C-3 | The local sign-in path FR-19 creates is absent from the eight refusal conditions | Critical | FR-13, FR-19 |
| A-1 | Materializer mechanism unspecified; three architectures satisfy every stated consequence | Critical | FR-29 |
| A-2 | Whether the mapper runs on every Bearer request is undetermined and changes the product | Critical | FR-9, FR-5 |
| A-3 | The mapper's user-identity claim is never named (account-takeover surface) | Critical | FR-9 |
| B-1 | Developer-portal order surface undefined; FR-30 cannot be implemented against it | High | FR-30 |
| B-2 | FreeMarker input contract unknown; Open Question 2 is unanswerable by architecture alone | High | §13 OQ2 |
| B-3 | No Dockerfile and no container build; is image construction in scope? | High | SC-3, FR-37/38 |
| B-4 | FR-39/FR-35 formats are bilateral contracts with an external consumer | High | FR-39, FR-35 |
| B-5 | Nothing specifies where Django permissions or superuser come from | High | FR-9, FR-11 |
| B-6 | Local sign-in entry point undesigned, and it ships in every component | High | FR-19 |
| A-4 | `ModelBackend` refusal predicate points at two wrong implementations (allauth subclasses it) | High | FR-13 |
| A-5 | allauth provider config and the DB-resident Site domain vs. FR-37's env-only rule | High | FR-4, FR-37 |
| A-6 | 90% floor per-combination is unmeasured and structurally fragile under subtraction | High | FR-31, CG-1 |
| A-8 | The JWKS trust-anchor check is circular as written and conflicts with FR-20 | High | FR-13, FR-20 |
| D-1 | Object storage claimed Satisfied; it does not exist in any form | High | §12 factor 4 |
| D-2 | The gate is three workflows, not one; `build` runs fortnightly; `pixi run ci` never runs in CI | Medium | Glossary, §10, FR-31 |
| D-6 | FR-46's "ASGI instrumentor present **and active**" has no explicit instrumentation call to assert | Medium | FR-46 |
| S-1 | Smoke-check level transitively depends on §4.2/§4.4/§4.7; splitting §4.6 is mandatory | Critical | FR-32 |
| S-2 | Object storage is an invisible prerequisite of the materializer | High | FR-29, D-1 |
| S-3 | Refusal contract depends on the process model and on feature surfaces | High | FR-13, FR-39 |
| S-4 | PostgreSQL must land before the twelve-combination gate to isolate latent failures | High | FR-31 |
| B-7 | Twelve-combination gate trigger policy unstated; 3-OS matrix would make it 36 runs | Medium | FR-31, CG-2 |
| B-8 | FR-36's lists do not partition the tree; `.github/` keep rule leaks 14 BMad agent files | Medium | FR-36 |
| A-7 | FR-12's fail-closed rule will refuse the test suite unless designed together | Medium | FR-12 |
| D-3 | FR-48's "package-index block is empty" is unsatisfiable (editable self-install) | Medium | FR-48 |
| D-5 | `src/config/websocket.py` is an undeclared surface that ships in every component | Medium | FR-1, FR-24, FR-36 |
| S-5 | Package rename is a repo-wide refactor listed as one parameterization bullet | Medium-high | FR-36 |
| S-6 | FR-17's allowlist must land with FR-6, not after | Medium | FR-6, FR-17 |
| S-7 | Template-coverage orphan detection can die silently during the harness build | Medium | FR-28, CG-1 |
| D-4 | §12 factor 8 and 12 marked Satisfied while their FRs are unbuilt | Low-medium | §12 |
| — | Off-by-one FR cross-references in §4.6; FR-1/smoke-check mismatch; §4.7 priority header | Low | §6 above |

---

## 8. What I would need to start, in one list

1. The developer-portal order surface, or a commitment that it is closed (B-1).
2. The FreeMarker generator's input contract, or a decision that the materializer is disposable (B-2).
3. Ownership of the container image (B-3).
4. An agreed declaration format for the process model and provenance stamp (B-4).
5. A decision on superuser and on where group permissions originate (B-5).
6. A decision on the shape of local sign-in, and a ninth refusal condition covering it (B-6, C-3).
7. Acceptance that FR-12 splits across process entry points, and a per-process scoping of the eight conditions (C-1, C-2).
8. The mapper's identity claim, invocation policy, and missing-claim behaviour (A-2, A-3).
9. A corrected §12 factor table, and object storage moved into the build plan (D-1, D-4).
10. Agreement that consolidating the gate behind one `pixi run ci` invocation, and landing PostgreSQL against the reference application, are prerequisite work rather than part of the harness epic (D-2, S-4).

Items 1-4 are product-owner or external-party decisions. Items 5-8 are product decisions with architecture input. Items 9-10 are corrections. With those, I could produce the architecture.
