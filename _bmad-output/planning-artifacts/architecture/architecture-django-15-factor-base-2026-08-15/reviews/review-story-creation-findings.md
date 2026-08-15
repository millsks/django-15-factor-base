---
name: 'review-story-creation-findings'
type: architecture-review
subject: 'ARCHITECTURE-SPINE.md — django-15-factor-base'
method: 'Nine independent per-epic readings of the spine against the reference application, performed during phase-1 story creation'
created: '2026-08-15'
status: open
---

# Spine Corrections — findings from phase-1 story creation

## How these were found

Creating the 68 phase-1 story files required nine independent readings of `ARCHITECTURE-SPINE.md`
against the actual tree, one per epic, each opening the files its epic cites and confirming every
line range, setting name and claimed absence. The findings below are what did not survive contact
with the repository.

Every code citation in this document was re-verified directly against the working tree at commit
`2bd0123` before being recorded. Findings are grouped by what the reader must do about them:
**defects** are wrong code, **errors** are places the spine describes the tree incorrectly,
**contradictions** are places the spine disagrees with itself, and **gaps** are obligations the
spine creates without supplying a mechanism.

Severity is about consequence if shipped unaddressed, not about effort to fix.

---

## A. Live defects in the reference application

These are wrong today, independent of any phase-1 work. Each already has an owning story.

### A-1 — Cache failures are swallowed silently — HIGH

**Owner:** Story 6.5

`src/config/settings/production.py:41` sets `"IGNORE_EXCEPTIONS": True`, and
`DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS` is set nowhere in the tree. django-redis's `omit_exception`
logs only when that flag is true; otherwise its `self.logger` is `None` and the exception vanishes
without trace.

This contradicts three separate statements of the same rule: FR-48 ("degradation is visible —
swallowed cache failures emit correlated log events"), the spine's own Runtime-errors convention
("Cache failure is swallowed *and* logged … Nothing is swallowed silently"), and the project
standard forbidding `except SomeError: pass`.

**Consequence:** a Redis outage in a deployed component presents as silence. FR-48 currently reads
as satisfied because the setting that would satisfy it is *half* present.

**Correction:** set `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS` alongside `IGNORE_EXCEPTIONS`, and assert
the pairing rather than either flag alone.

### A-2 — The OTLP exporter attaches to a default endpoint that was never configured — HIGH

**Owner:** Story 6.3

`resolve_traces_exporter` in `src/config/observability/telemetry.py` reads:

```python
configured = os.environ.get("OTEL_TRACES_EXPORTER", "").strip().lower()
if configured in {CONSOLE, NONE, OTLP}:
    return configured
return OTLP if _has_otlp_endpoint() else NONE
```

An explicit `OTEL_TRACES_EXPORTER=otlp` returns `otlp` **before** the endpoint check runs, so a
`BatchSpanProcessor(OTLPSpanExporter())` is attached pointing at the SDK default
`http://localhost:4318` with nothing listening. The module's own docstring names this as the
behaviour the design prevents — "against nothing on every export cycle" — and
`tests/unit/test_telemetry.py:81-88` currently pins the defective behaviour.

**Correction:** require an endpoint before honouring an explicit `otlp`, and re-point the test.

**Related boundary, not a defect:** "unreachable endpoint" cannot be determined at startup at all
without a network call, which NFR-1 forbids. "No endpoint configured" is the only startup-observable
proxy, and FR-45's acceptance criteria should say so rather than implying reachability is checked.

### A-3 — `telemetry.py` reads `DJANGO_ENV`, which the spine forbids by name — MEDIUM

**Owner:** Story 3.6

`src/config/observability/telemetry.py:80`:

```python
"deployment.environment": os.environ.get("DJANGO_ENV", "local"),
```

The spine's Consistency Conventions table states: "Never `DJANGO_ENV` or a bare `ENV` — the platform
is likely to set a generic `ENV=dev` for a development *deployment*, and a deployed dev environment
is still deployed."

Worse than the naming: the default fails **open** toward `"local"`. A deployed component whose
platform does not set `DJANGO_ENV` reports its telemetry as local — the inverse of AD-13's
fail-closed locality rule, in the one subsystem whose whole purpose is telling you where something
ran.

**Correction:** derive from the AD-13 locality reader, defaulting to deployed.

---

## B. Errors — the spine describes the tree incorrectly

### B-1 — AD-24's Celery region range is short by 22 lines — HIGH

**Confirmed independently by six of nine readings.**

AD-24 cites "the Celery block at `:296-313`" in `src/config/settings/base.py`. Verified against the
tree:

| Line | Content |
|---|---|
| 296 | `# Celery` — block header, **citation start is correct** |
| 313 | `CELERY_RESULT_BACKEND_ALWAYS_RETRY` — **mid-block** |
| 335 | `CELERY_WORKER_HIJACK_ROOT_LOGGER = False` — **actual last line** |
| 336 | blank |
| 337 | `# django-allauth` — next block |

**Consequence if shipped:** a marker pair placed at the literal cited range leaves `:314-335`
outside the region — including `CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"`
— in the eight combinations whose environment contains no `django_celery_beat`. That is exactly the
boot-time `ImportError` class AD-24's Prevents clause exists to stop, reintroduced by the AD's own
citation.

**Correction:** `:296-335`.

### B-2 — AD-24's `telemetry.py` region is not one region — HIGH

The citation `src/config/observability/telemetry.py:134-137` is exact as a *line range* — those four
lines are the instrumentor calls. But the framing as a single feature-owned region is wrong:

| Line | Call | Disposition |
|---|---|---|
| 134 | `DjangoInstrumentor().instrument()` | **core** |
| 135 | Celery instrumentor | `feature:celery` |
| 136 | `PsycopgInstrumentor().instrument()` | **core** |
| 137 | Redis instrumentor | `feature:redis` |

Marking `:134-137` as one region strips Django and psycopg instrumentation from **every**
combination — a direct FR-47 violation (the ASGI instrumentor active in all twelve) delivered by
following the spine literally.

**Additionally:** the corresponding imports at `:21` and `:24` are named in no source document.
Pruning a call without its import moves the `ImportError` from line 135 to line 21. The region
declaration must cover both sites.

**Correction:** two single-line regions plus their import lines, not one four-line region.

### B-3 — "Three known region-bearing paths" is at least six — HIGH

AD-24 states three: `src/config/settings/base.py`, `src/config/observability/telemetry.py`,
`pixi.toml`. The readings found these additional ones, three of them in files that exist today:

| Path | Region | Feature | Found by |
|---|---|---|---|
| `src/config/settings/base.py:293-294` | `REDIS_URL` / `REDIS_SSL` | `feature:redis` | Epic 7 |
| `src/config/settings/production.py:31-44` | the `CACHES` block + its `from .base import REDIS_URL` at `:12` | `feature:redis` | Epics 6, 7 |
| `src/config/settings/local.py:75-80` | `CELERY_TASK_ALWAYS_EAGER` / `CELERY_TASK_EAGER_PROPAGATES` | `feature:celery` | Epic 7 |
| `src/config/urls.py` | `home`/`about` `TemplateView`s, the `users/` include | `feature:ui` | Epic 7 |
| `src/config/startup/stage_one.py` | the two FR-14 conditional refusals | celery, redis | Epic 4 |
| `component.toml` | `worker`/`beat` replica and replacement constraints | `feature:celery` | Epic 5 |

Note `CACHES` is **not defined in `base.py` at all** — the deployed Redis cache exists only in
`production.py`. Any treatment assuming the Redis surface lives in `base.py` is incomplete.

`component.toml` is the structurally interesting one: AD-28 makes it `core` (always travels) while
AD-14 puts process constraints in it for process types that exist in only four of twelve
combinations. Without markers inside it, AD-14's two-way gate test fails in the eight non-Celery
combinations by declaring processes with no matching task.

**Correction:** state the count as open, and require the reconciler be built over an open
`[[regions]]` array in `accelerator.toml` rather than three fixed keys. Story 7.2 already instructs
this; the spine should not contradict it.

### B-4 — AD-7 undercounts the import-root declaration sites and misstates one line range — MEDIUM

AD-7 says "there are five import-root declaration sites in this repository and after this AD there
is one." Verified:

- `manage.py:24-26` → actually **`:23-25`** (comment at `:22`). Off by one.
- `asgi.py:18-20` → **holds exactly**.
- `wsgi.py` (no range cited) → `src/config/wsgi.py:24-26`.
- **A sixth site AD-7 does not name:** `pixi.toml:186`, the `serve-reload` task
  (`uvicorn config.asgi:application --app-dir src --reload --reload-dir src`). AD-7 names only the
  `serve` task at `:179`.
- **The retained site does not have the required shape.** `pyproject.toml:126-127` reads
  `packages = ["src/config", "src/django_service"]` — a per-package enumeration, not the `sources`
  remapping AD-7 requires. AD-7 reads as though the survivor is already correct; it must itself be
  converted, and that conversion is what makes AD-6's graduation promise hold.

**Correction:** six sites, `manage.py:23-25`, and an explicit statement that the retained site is
converted rather than merely kept.

### B-5 — AD-7's removal of the pytest `pythonpath` takes a non-source-root entry with it — MEDIUM

**Independently found by Epics 1 and 9.**

`pyproject.toml:149` reads `pythonpath = ["src", "."]`. The `"."` entry is not a source root — it is
what makes `tests.factories` importable from `tests/conftest.py` under `--import-mode=importlib`.
The `sources` remapping AD-7 retains covers `src/`, not the repository root.

**Correction:** AD-7 should say how `tests.factories` resolves after the removal, or the removal is
not safely executable as written.

### B-6 — AD-18 misattributes where template coverage and the build cron live — LOW

Two claims in AD-18 do not match the tree:

- **"Template coverage moves out of the SonarCloud workflow."** The template-coverage
  *configuration* is already in `pyproject.toml` (`django_coverage_plugin`, `template_extensions`)
  and `pixi.toml [activation.env] COVERAGE_CORE=ctrace`. What `sonarqube.yml:36` owns is the
  coverage *run invocation*.
- **"`build` off its fortnightly cron."** The cron lives inside `release.yml`
  (`cron: "0 0 7,21 * *"` at `:5`, `pixi run build` at `:213-215`) — and that same workflow also
  runs `lint`, `typecheck` and `test-cov` inline at `:173-181`. Four gate steps live there, not one.

**Also:** a `ci` task already exists at `pixi.toml:206` as
`depends-on = ["test-cov", "lint", "typecheck", "build"]` — no pre-commit step, and roughly the
reverse of the required fast-fail ordering. AD-18's "has never run in CI" is accurate; a reader
should not infer "does not exist."

**Correction:** name `release.yml` and `pyproject.toml` as the actual sites, and characterise `ci`
as existing-but-wrong-shaped.

---

## C. Contradictions — the spine disagrees with itself

### C-1 — AD-29's `base.html` guarantee is not satisfiable, and AD-30 depends on it — CRITICAL

**Owner:** Story 7.4

AD-29 states that `base.html` and the error templates stay in `django_service` "because the admin
and the error handlers need them in every combination." Verified, `src/django_service/templates/base.html`
reverses UI-feature routes:

| Line | Reversal | Owner |
|---|---|---|
| 71, 75 | `{% url 'home' %}` | `feature:ui` |
| 78 | `{% url 'about' %}` | `feature:ui` |
| 83 | `{% url 'users:detail' %}` | `feature:ui` |

With the UI feature absent, every page extending `base.html` raises `NoReverseMatch` — including the
403/404/500 pages AD-29 explicitly requires to keep working. **AD-30's smoke check asserts a rendered
404 in all twelve combinations**, so this is not a latent problem: it fails the harness in the six
combinations without the UI feature, in the check specifically designed to catch excision damage.

The same defect appears twice more:
- `src/django_service/users/models.py:24-31` — `User.get_absolute_url()` reverses `users:detail`,
  and the admin calls it.
- `src/config/settings/base.py:140` — `LOGIN_REDIRECT_URL = "users:redirect"`.

**Correction:** AD-29 must state that the navbar is decoupled from `base.html` (or that those
reversals become conditional on the feature) before the UI feature is extractable. As written, AD-29
and AD-30 cannot both hold.

### C-2 — The contributable surface has two mutually exclusive authoritative homes — HIGH

**Owner:** Story 9.4

- **AD-26:** the refusal contract is one module, `src/config/startup/`, "containing both stages and
  the FR-17 allowlist," and the FR-17 allowlist and AD-8's permitted-contribution surface "are the
  same declaration."
- **AD-1 / AD-8:** the closed contributable surface is declared in `accelerator.toml` "and nowhere
  else."

Both cannot be the single authoritative site. `accelerator.toml` is `machinery` and **never
travels**, while the AD-8 composition step runs at settings import inside a materialized component
that does not have that file. The rule as written cannot execute where it must execute.

**Resolution adopted in Story 9.4**, on the AD-20 precedent: the runtime constant in
`src/config/startup/` is authoritative, `accelerator.toml` mirrors it, and a gate test asserts
equality. Nothing is forked — but the spine should state which file wins rather than leaving two
ADs asserting exclusivity over the same declaration.

### C-3 — AD-26's "last statement of every settings module" cannot be literal — HIGH

**Owner:** Story 4.1

AD-26 places stage 1 as "the last statement of every settings module," and the whole point is that
this lands *after* the AD-8 composition step, which is what makes AD-9's iteration over every
configured database reachable.

But `base.py` is imported via `from .base import *` and itself configures four forbidden states. A
stage-1 call at the end of `base.py` fires **before** the leaf module composes — destroying the
after-composition property the rule exists to guarantee.

**Resolution adopted in Story 4.1:** leaf modules only (`local.py`, `production.py`, `test.py`),
with a gate test asserting each leaf's last statement *and* a paired test asserting `base.py` does
not call it.

**Correction:** AD-26 should say "every leaf settings module" and name the `base.py` prohibition
explicitly, since the literal reading is both plausible and wrong.

### C-4 — AD-21 and FR-13, read literally, refuse every deployed component — MEDIUM

**Owner:** Story 3.4

AD-21: the local sign-in route "ships in every component and is refused wherever the component is
deployed." FR-13: "the local sign-in route reachable" is a refusal condition.

Read together and literally, every deployed component refuses to start, because the route ships in
every component.

**Resolution adopted in Story 3.4:** the code ships everywhere, the route is *mounted* only when
`COMPONENT_RUNTIME=local`, and the refusal is the backstop for a route that is reachable anyway.
This is almost certainly the intent, but the spine does not say "mounted" anywhere and the
distinction is the whole rule.

**Correction:** distinguish shipping from mounting in AD-21's text.

### C-5 — AD-23's "refused at startup" is stronger than FR-23 permits — MEDIUM

**Owner:** Story 2.7

AD-23: "a JWKS location not derived from [the configured OIDC issuer] is refused at startup."
FR-23 / AD-23 itself: nothing on the start path reaches the network; JWKS is fetched lazily, never
at import or boot.

Verifying a JWKS location against the issuer's discovery document requires fetching that document.
At startup the check can therefore only be a **string-derivation rule** over the configured issuer —
which is weaker than "derived from" implies, and cannot detect an issuer whose published JWKS URI
does not match the derivation.

Story 2.7 exports the predicate and states the limit honestly rather than overclaiming. The
tech-verification review already recorded this as L-4.

**Correction:** AD-23 should state the check is syntactic, and that a mismatch between derivation
and the real discovery document surfaces on first Bearer request rather than at boot.

---

## D. Gaps — obligations with no mechanism

### D-1 — No feature-owned location exists for the UI surface AD-29 requires to move — HIGH

**Owner:** Story 7.4 (recorded as a constrained decision)

AD-29 requires user-facing templates, form styling, views and forms to move "out of `django_service`
into a feature-owned location before that feature is extracted." No source document names that
location, and the Structural Seed has no home for a feature's code at all.

`src/django_apps/` cannot be it: `tenant` means never judged and never pruned, so a feature landing
there could never be removed — the exact opposite of the requirement.

**Correction:** the Structural Seed needs a feature-code root. Story 7.4 recommends a new top-level
package under `src/` and has Stories 7.5 and 7.7 inherit the decision rather than re-deciding it,
but this is a spine-level choice being made in a story file for want of one.

### D-2 — Nothing tells a settings-import-time check which features the combination selected — HIGH

**Owner:** Story 9.4

AD-8 requires that "a contribution naming a feature the combination did not select is refused at
settings import." No document says how settings import learns the selection:

- `accelerator.toml` is `machinery` and does not travel.
- `.accelerator.json` is explicitly absent from the reference application (AD-17), so the mechanism
  would work in materialized components and fail in the tree that must gate it.

Story 9.4 adds `component.toml [features] selected` under AD-28's rule — which **extends** what
AD-28 and Story 5.1 enumerate (adopted apps, per-database requiredness, migration steps,
process-model constraints).

**Correction:** add the selected-feature list to AD-28's stated contents.

### D-3 — The Structural Seed is a shape, not an inventory, but AD-2 needs an inventory — MEDIUM

**Owner:** Story 8.7

AD-2's input reconciliation fails on "a path claimed by no disposition." Unlisted defaults to
`machinery`, so silence is survivable at runtime — but reconciliation still requires every path to
be enumerated. The Structural Seed is silent on paths that exist today: `.github/`, `docs/`,
`mkdocs.yml`, `sonar-project.properties`, `manage.py`, `CHANGELOG.md`, `LICENSE`, `README.md`,
`_bmad/`, `_bmad-output/`, `.agents/`, `.bmad-loop/`, `.claude/`.

**Correction:** either the seed grows an inventory, or AD-2 states that the carrier's disposition
list is the inventory and the seed is illustrative.

### D-4 — AD-25 under-enumerates the parameterization sites — MEDIUM

**Owner:** Story 7.3

`sonar-project.properties:6` is confirmed exactly as cited. But AC 2's second reconciliation
direction — "a site matching no declared parameter fails" — fails on sites carrying the identical
defect that are not in the parameter list:

- `sonar-project.properties:7` `sonar.organization=millsks`, `:10` `sonar.projectName`
- `src/config/settings/base.py:266` `ADMINS`; `:374-375` spectacular title/description
- `src/config/settings/production.py:21` `ALLOWED_HOSTS` default `["millsks.github.io"]`;
  `:96-99`, `:104-107`, `:151-153`
- `src/config/observability/telemetry.py:31` `DEFAULT_SERVICE_NAME = "django-15-factor-base"`

**Correction:** extend `[parameters]`, or the two-way reconciliation AD-25 promises cannot pass on
first run.

### D-5 — The verification harness has no declared home — LOW

**Owner:** Stories 8.8–8.10

`tools/` does not exist at all, not just `tools/materializer/`. Stories 8.8–8.10 need a verification
runner distinct from the materializer; the Structural Seed names no location. Placed at
`tools/harness/` (`machinery`) with the variance flagged.

### D-6 — Two ownerless open items remain ownerless — LOW

The spine's own Open Items list carries FR-45's collector-stub design and NFR-6's telemetry-overhead
measurement, both needing an owner. Stories 6.4 and 6.6 decline to invent one: 6.4 proposes a
concrete stub design (in-process loopback `ThreadingHTTPServer` on `POST /v1/traces`,
protobuf-decoded, with `max_export_batch_size` below N to exercise batching) but frames it as a
proposal requiring ratification, since no AD exists.

### D-7 — Coverage measurement excludes the code phase 1 adds — LOW

**Owner:** Stories 7.1, 7.8

`pyproject.toml:161` sets `[tool.coverage.run] include = ["src/**"]`. The `tools/materializer/` and
`tools/harness/` code Epics 7 and 8 introduce is therefore unmeasured by default. Adding measurable
code outside the measured set without deciding is precisely the silent narrowing CG-1 forbids and
AD-20 names as the defect already precedented in this tree.

---

## E. Cross-story collisions

These are not spine errors — they are places where two stories, each correct alone, interact. They
are recorded because implementing either in isolation produces a broken tree.

| # | Collision | Resolution |
|---|---|---|
| E-1 | NFR-6's uninstrumented baseline naturally uses `OTEL_SDK_DISABLED=true` — which is stage-1 refusal condition 3. A benchmark built on it works today and breaks the moment Epic 4 ships. | Story 6.6 obtains the baseline by not calling `configure_observability()`. |
| E-2 | Story 2.7 asserts `jwks_url_derives_from_issuer` **rejects** `file://`; FR-20 requires local settings to point JWKS at a locally generated key. | Story 3.5: the rejection is the deployed trust-anchor guard and stays; `JWKSKeyStore`'s fetch seam gains a local `file://` reader. Both hold. |
| E-3 | The four `COMPONENT_*` claims variables collide with AD-13's absolute prohibition on any `COMPONENT_*` variable in `[activation.env]` — a gate test Epic 8 runs over the materialized `pixi.toml`. | Story 2.2 flags it; Epic 3 sets them per-task. |
| E-4 | Implementing Epic 4 before Epic 2 makes `pixi run ci` fail **by design** — all four stage-1 credential-path states and one stage-2 route state are live today (`base.py:133-136`, `:271`, `:340`, `:112`, `:357-364`; `urls.py:11`, `:39`). | Each affected Epic 4 story carries an explicit instruction not to soften a condition or widen the allowlist to accommodate the current tree. |
| E-5 | The mapper cannot be reached from `django_service` without inverting AD-4. | Story 2.3's provisioning callable reads the claims contract off `django.conf.settings`; Story 2.6 moves `SocialAccountAdapter` into `src/config/authorization/adapters.py`. |
| E-6 | Story 5.2 and Story 3.1 both assert the `[activation.env]` prohibition. | Both left in place; Story 3.1 names the consolidation home. |
| E-7 | GitHub Actions `services:` containers are Linux-only, so Story 1.2's PostgreSQL gate cannot run on the three-OS matrix AD-18 preserves. | Ubuntu-only `gate` job plus a retained three-OS `pixi run test` compatibility job, split commented in-workflow. |

---

## F. Confirmed correct

Recorded so they are not re-investigated.

- `production.py:26-28` — the sqlite refusal is built exactly as AD-26 and the epics claim. It reads
  `DATABASES["default"]` only, so AD-9's every-configured-database iteration is a genuine addition.
- `telemetry.py:134-137` — the line range is exact (see B-2 for the framing problem).
- `asgi.py:18-20` — AD-7's citation holds exactly.
- `[activation.env]` is already clean: it holds only `COVERAGE_CORE = "ctrace"`, and no `COMPONENT_*`
  variable exists anywhere in the tree. Story 3.1's AC #3 enforces an existing state rather than
  repairing one.
- `COVERAGE_CORE` at `pixi.toml:145-150` travels correctly as `core` content of a `core` path;
  AD-13's `[activation.env]` prohibition applies only to `COMPONENT_*`.
- `pixi.toml:141-143` — only `default` and `dev` environments, both `solve-group = "default"`, as
  Epic 8 assumes.
- `src/config/websocket.py`, the scope dispatcher at `src/config/asgi.py:36-43`, and the omit entry
  at `pyproject.toml:168` all exist and are deletable together per AD-16. Note the module-level
  callable is currently `application` (the dispatcher), with Django's at `django_application`, and
  `pixi.toml:179`/`:186` invoke `config.asgi:application` — the name must survive on the survivor.
- `src/django_service/contrib/sites/migrations/0003_set_site_domain_and_name.py` exists and hardcodes
  `"millsks.github.io"` at `:45`, as AD-31 states.
- `tests/unit/test_dependency_policy.py` already satisfies two of Story 1.7's four acceptance
  criteria; that story is scoped to the remainder.
- `pyproject.toml:183` sets `check_untyped_defs = true`, not `strict`, as AD-18 states.

---

## G. Smaller items worth folding into the next spine revision

- **AD-29 has two pre-existing violations.** `src/django_service/users/tasks.py:1` imports
  `from celery import shared_task` — `feature:celery` code inside the package AD-29 declares `core`
  in its entirety. Its own docstring calls it "a pointless Celery task to demonstrate usage" and
  nothing in `src/` calls it. (The `base.html` violation is C-1.)
- **`MEDIA_ROOT` declares a writable path inside the payload.** `base.py:198`
  `MEDIA_ROOT = str(APPS_DIR / "media")`, served at `src/config/urls.py:28`. FR-39 requires no
  writable path beyond a temporary directory and FR-25 puts user media out of scope. Story 5.6
  asserts nothing is written there; removing the surface belongs to Epic 7's storage story.
- **NFR-2 has an unnamed concrete threat.** `django_structlog.middlewares.RequestMiddleware`
  (`base.py:175`) binds `user_id`, resolving `request.user` and potentially issuing a session query.
  On the liveness path that breaks "liveness touches nothing external." Story 5.3 makes it a
  `django_assert_num_queries(0)` assertion rather than an assumption.
- **`DJANGO_ADMIN_FORCE_ALLAUTH` defaults to `False`** (`base.py:271`), against FR-7's "defaults
  true." Story 2.6 flips it.
- **`requests`, `pyjwt` and `cryptography` are all undeclared.** `requests` reaches `pixi.lock` only
  transitively via `opentelemetry-exporter-otlp-proto-http`; the other two are absent from the lock
  entirely. Divergence D-4 names only `requests`; allauth's ID-token verification needs all three.
- **"Retired rather than parameterized" cannot mean deleting the migration.**
  `0004_alter_options_ordering_domain.py` depends on the `0003` node and applied databases carry it
  in `django_migrations`. Story 2.6 retires the operations to no-ops and keeps the node.
- **`ADMIN_URL` is environment-parameterized** (`base.py:264` default `admin/`; `production.py:107`
  from `DJANGO_ADMIN_URL`), so FR-17's route-prefix scope must read `settings.ADMIN_URL` rather than
  hardcode a prefix.
- **Story 7.5's "greenfield" claim is imprecise.** `production.py:79-86` already defines `STORAGES`
  (`"default"` = `FileSystemStorage`, `"staticfiles"` = whitenoise). No *object* storage exists, but
  the setting name the feature must own is already held by a `core` module and the `"staticfiles"`
  half is immovable core — a restructure, not an addition.
- **"The fixture set" is not a third artifact.** Story 8.2's AC #3 excludes "the materializer, the
  carrier and the fixture set" as three things, but AD-25 places fixture values inside
  `accelerator.toml [parameters]` — excluding the carrier discharges the fixture set. If a separate
  fixture file is ever created it must be declared `machinery`.
- **AD-14's "process group" is undefined** and pixi has no native task grouping. Story 5.2 defines
  it structurally as the set of tasks whose `env` declares `COMPONENT_PROCESS`, so the two-way test
  derives from parsed TOML rather than name matching — consistent with AD-26's objects-not-strings
  rule, and it correctly places the `prune` admin process outside the group.
- **Story 9.3's acceptance criteria omit AD-4's fourth clause** ("a feature's code may never import
  another feature's"). Carried as a task under AC #4.
- **Story 9.6's compatibility check is a gate condition, not a refusal** — easy to "complete" by
  wiring it into stage 1, which would make a tenth refusal condition and contradict the epics'
  resolved count of nine. Same for 9.7, which widens the domain of conditions 1 and 7 rather than
  adding new ones.
- **Task-name drift.** This repository's tasks are `format` / `typecheck` / `test-cov` / `ci`, not
  the `fmt` / `check` / `cov` names the global standard uses. Renaming would break
  `.pre-commit-config.yaml`, `release.yml` and `sonarqube.yml`. Stories cite the real names and treat
  AD-18's sequence as naming steps, not identifiers.
- **`mkdocs build --strict` is a real gate on the documentation criteria.** Six Epic 5 stories write
  `docs/deployment.md`; it must be added to `mkdocs.yml` `nav` or `pixi run docs` fails. Every story
  that writes to it carries the nav step.

---

## Suggested disposition

| Priority | Items | Why first |
|---|---|---|
| Before Epic 7 starts | B-1, B-2, B-3, C-1, D-1 | All five are wrong-as-written in ways that make Epic 7 unbuildable or produce a tree that fails Epic 8's harness. C-1 and D-1 are blocking. |
| Before Epic 4 starts | C-3, C-2 | Both change where code goes, not just what it says. |
| Independently, any time | A-1, A-2, A-3 | Live defects; each has an owning story and none blocks another. |
| Next spine revision | B-4, B-5, B-6, C-4, C-5, D-2..D-7, §G | Correctness of the document rather than of the work. |

Two further notes for whoever revises the spine. First, epics.md:310-326 already resolved the
refusal-count inconsistency to **nine conditions across fourteen forbidden states**; FR-13's bullet
list and AD-27's condition should be reconciled to that table rather than re-derived. Second, the
Divergences section states "no open divergence remains" — that was true when written, and this
document is the honest successor to it rather than a contradiction of it.
