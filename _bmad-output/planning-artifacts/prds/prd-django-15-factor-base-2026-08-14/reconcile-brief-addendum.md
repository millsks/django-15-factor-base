---
title: "Reconciliation: brief addendum → PRD"
status: draft
created: 2026-08-14
updated: 2026-08-14
---

# Reconciliation — brief addendum against the PRD and its addendum

**Source:** `_bmad-output/planning-artifacts/briefs/brief-django-15-factor-base-2026-08-08/addendum.md` (409 lines, 8 sections)
**Targets:** `prds/prd-django-15-factor-base-2026-08-14/prd.md` (FR-1..FR-49, SC-1..SC-5, CG-1..CG-4, NFR-1..NFR-8) and its addendum.

## Overall assessment

Coverage is high and in several places the PRD is stronger than its source: the refusal contract grew from six to eight conditions with a stated reason, FR-12 relocates the evaluation out of the settings module the source left it inside, FR-17 inverts the denylist, and FR-23 adds a no-network-at-boot property the source never named. Every one of the source's eight sections has PRD representation, and the strip/parameterize/keep table, the twelve-combination arithmetic, the process model, the two health endpoints, the four substitutions, the OTel package split, and the factor-coverage statuses all transcribe faithfully. The material findings are not omissions of reasoning — the PRD is correctly thin there by design — but three classes of defect: (a) the source's **granularity** for the disposition table (§4.2.2) is directory-level and the PRD's own FR-2/FR-24/FR-27 require sub-file variance from exactly those "Kept" entries, which makes FR-36 self-contradicting for `pixi.toml`, `pixi.lock`, `src/config/`, `tests/`, and `.github/`; (b) several source findings that were **verdicts about the current repository** — the dead-dependency audit (§3), the retained `AUTH_PASSWORD_VALIDATORS` and `test.py` MD5 hasher (§1.5), the local-account password surface (§1.6) — reach no FR at all, so nothing in the PRD either requires or protects them; and (c) two things the source explicitly **assigned to the gate** — end-to-end OTLP export (§6.1.1) and orphan detection for non-template residue (§3.1) — appear in the PRD only as a risk or a narrower FR, with no requirement that the gate actually do them. Two cross-reference numbers in the PRD are also wrong. Nothing found contradicts a settled decision in substance; the contradictions are all granularity or citation.

---

## 1. FR-36's disposition table is directory-level, and FR-2/FR-24/FR-27 require sub-file variance from four of its "Kept" entries

**Source (§4.2.2):** the disposition table lists as **Kept — the component itself**: "`src/config/`, `tests/`, `manage.py`, `pixi.toml`, `pixi.lock`, `.github/`, `.pre-commit-config.yaml`, `.gitignore`, `.gitattributes`, `docs/development.md`, `docs/observability.md`." Section §2 simultaneously declares the non-package surface of background task processing to be "`config/celery_app.py`, `config/__init__.py`, `users/tasks.py`, `observability/telemetry.py`, all three settings modules, three test modules", and the package surface to be `celery`, `django-celery-beat`, `django-timezone-field`, `python-crontab`, `cron-descriptor`, `opentelemetry-instrumentation-celery`.

**PRD:** FR-36 transcribes the Kept list verbatim. But FR-2 requires the dependency manifest of a materialized combination to contain "the instrumentation packages that combination's capabilities require, and no others"; FR-27 requires that no combination contain "a dependency, template, static asset, settings fragment, or test belonging to a feature it did not select"; FR-24 requires each feature to declare its non-package surface. `pixi.toml` and `pixi.lock` therefore cannot be kept verbatim — they must differ per combination and the lock must be re-resolved. `src/config/` cannot be kept wholesale — `src/config/celery_app.py` exists in this repository today and must be absent from 8 of 12 combinations, `src/config/__init__.py` and all three settings modules must be edited, and `src/config/observability/telemetry.py` must lose its Celery and Redis instrumentors. `tests/` cannot be kept wholesale — FR-27 requires the three Celery test modules to be absent, not skipped.

**Severity: critical.** This is the requirement a materializer implementer reads first, and read literally it produces twelve identical components.

**Suggested fix:** split FR-36 into two orthogonal dispositions and say so explicitly. (i) *Provenance disposition* — accelerator machinery vs component content, which is what the source's table actually is. (ii) *Combination disposition* — per-feature inclusion, which is FR-24/FR-27's job. Add a consequence to FR-36: "`Kept` means the path belongs to the component rather than to the accelerator; it does not mean the path is copied byte-for-byte. Paths that are Kept and also appear in a feature's declared surface (FR-24) are materialized per combination. `pixi.toml` and `pixi.lock` are Kept-and-varying by construction; the lock is re-resolved per combination." Then add a consequence to FR-29 asserting that materializing two different combinations produces different `pixi.toml` content.

---

## 2. `.github/` is "Kept", but the twelve-combination harness and the accelerator's own release/quality workflows live there

**Source (§4.2.3):** "the gate ships inside the generated component rather than living beside the template… the thing that proves a component is sound is the component's own pipeline." And, separately, "the template's own CI generates every valid combination and runs each generated repository's gate against it." Two different pipelines, both under `.github/`. §4.2.2 lists `.github/` as Kept and `sonar-project.properties` as Parameterized.

**PRD:** FR-36 keeps `.github/` wholesale; FR-31 requires "CI declares a PostgreSQL service and sets the database URL for gate runs" without saying which of the two CIs. The repository today holds `ci.yml`, `sonarqube.yml`, `release.yml`, `labeler.yml`, `stale.yml` — `release.yml` releases the *accelerator*, and the twelve-combination harness this PRD adds will be a sixth. Under FR-36 as written, every generated component ships the accelerator's release workflow and the twelve-combination harness that has no template to run against.

**Severity: high.**

**Suggested fix:** add a consequence to FR-36: "`.github/workflows/` splits like `docs/`. Workflows that verify one component travel with it; workflows that verify the accelerator — the twelve-combination harness, accelerator release, and any accelerator-scoped quality reporting — do not. A workflow added to this repository without a declared disposition fails materialization." Then split FR-31's first consequence into the two levels: the component gate workflow declares a PostgreSQL service *and* the harness declares one for its own per-combination gate runs.

---

## 3. The materializer's own code has no declared disposition

**Source (§4.2.2):** the Strip list is "`_bmad/`, `_bmad-output/`, `.agents/`, `.bmad-loop/`, `.claude/`" — written before the materializer existed as a concept (it is introduced in the PRD addendum §1, not in the source).

**PRD:** FR-36 copies the strip list unchanged. FR-29 puts the materializer "in this repository". Nothing states that the materializer, its feature-to-surface declarations, and its fixture set (FR-30) are stripped from materialized output.

**Severity: high.** A component that ships the materializer ships the ability to re-materialize itself into a different combination, and the fixture set carries test values for the order surface.

**Suggested fix:** add the materializer's source path, the feature-to-surface declarations, and the fixture set to FR-36's Strip list, with the note that PRD Open Question 2 (single-authoring across phases) does not change this — an artifact can be single-authored in the accelerator and still stripped from output.

---

## 4. The source assigns end-to-end OTLP export to the gate; no FR makes the gate do it

**Source (§6.1.1):** "no test drives `BatchSpanProcessor(OTLPSpanExporter())` end to end. **Per §4.3 this belongs to the gate.**" The source is explicit that `tests/unit/test_telemetry.py` "covers exporter *selection* comprehensively" and that the export path — "protobuf serialization, HTTP transport, batch behavior, retry and timeout" — is not covered.

**PRD:** §11 names it as a risk and gives the mitigation as "it belongs to the gate, and FR-44 keeps the local default at discard-at-the-processor". But FR-44's consequences only assert selection behaviour (export enabled when the endpoint is set; no processor attached when it is not) — the same thing already covered. FR-31 lists nothing about OTLP. So the source *routed* this to the gate and the PRD *cited* the routing without creating the requirement, which leaves the risk with a mitigation that does not exist.

**Severity: high.** It is the only immovable capability whose delivery path is unverified anywhere.

**Suggested fix:** add a consequence to FR-44: "At least one gate-level test drives a span through `BatchSpanProcessor` and the OTLP exporter against a collector endpoint stood up for the test, asserting the span is serialized and transmitted. Exporter *selection* coverage does not satisfy this." Alternatively make it an explicit consequence of FR-31. Either way, §11's mitigation should then cite the FR rather than a routing decision.

---

## 5. Orphan detection covers templates only; the source names static assets and settings fragments as the same class

**Source (§3.1):** "**This is the generalizable finding.** No import graph, linter, or dependency analyzer flags an orphaned template override. Only the coverage gate did, by reporting 0%. Every future feature extraction will produce the same class of residue **across templates, static assets, and settings fragments**."

**PRD:** the Glossary defines *Orphan* to include "a file, dependency, settings fragment, or test", and FR-27 asserts absence of all of them. But FR-28 — the requirement that *preserves the detection property* — has only two consequences, both template-and-coverage: "Coverage measurement includes templates in every combination's gate run" and "An orphaned template override introduced deliberately into a combination causes that combination's gate to fail." CG-1 likewise defends only template coverage. Coverage does not measure static assets or settings fragments, so FR-27's assertion for those two categories has no detecting mechanism — exactly the condition the source says is undetectable by any linter or dependency analyzer. SC-2 then claims all five categories.

**Severity: high.** SC-2 is a primary success criterion, and for two of its five categories nothing checks it.

**Suggested fix:** extend FR-28 with a consequence naming the mechanism for the other categories, e.g. "Each feature's declared surface (FR-24) is asserted against materialized output in both directions: every declared path present when selected, every declared path absent when not. For static assets and settings fragments, where coverage gives no signal, this reachability assertion is the detector." Add a deliberate-orphan test for a static asset and for a settings fragment alongside the template one.

---

## 6. The dependency audit's verdicts reach no requirement, and nothing prevents the same accumulation recurring

**Source (§3):** a table of verdicts against source references — `python-slugify` (0 references, "Dead"), `django-model-utils` (0, "Dead"), `pillow` (0, "Dead… **withdrawn** once object storage was scoped to documents and blobs and avatars were confirmed to resolve from IdP metadata as remote URLs"), `fido2` and `qrcode` ("Cut. MFA is enforced at the IdP"), `argon2-cffi` ("Cut with that block"). Plus: "**Object storage libraries: none present.** Genuinely greenfield, not a dead dependency."

**PRD:** §4.9 covers channel policy (FR-48) and pre-commitment availability checks (FR-49). §5 non-goals record MFA-at-the-IdP and avatars-as-remote-URLs, which is where the *rationale* belongs. But no FR requires the audited packages to be gone, and no FR establishes the standing property — that a dependency with zero source references is a defect. FR-27 only catches packages belonging to an *unselected feature*, not packages belonging to no feature at all, which is precisely what all five audited entries were.

**Severity: medium.** The removals may already be applied, but the PRD is the document that would keep them applied.

**Suggested fix:** add a consequence to FR-48: "No combination's dependency manifest declares a package with zero references in that combination's source and tests. A gate step asserts this, so a dependency added for work that was later cut fails the build rather than accumulating." Optionally note in §4.9 that the audit removals are the baseline this asserts against.

---

## 7. FR-19 declares personas but never specifies how a persona signs in

**Source (§1.6):** "Local development requires local users and local admins, because a developer must be able to work without a reachable IdP realm." §1.5: "`AUTH_PASSWORD_VALIDATORS` was **deliberately retained**, and §1.6 gives it a permanent reason to stay: **local accounts have passwords**." The §1.6 table then names the local paths that must exist locally and be refused when deployed: `ModelBackend` in `AUTHENTICATION_BACKENDS`, a non-empty `ACCOUNT_LOGIN_METHODS`, `DJANGO_ADMIN_FORCE_ALLAUTH` false.

**PRD:** FR-19's consequences cover declaration, seeding, group differences, and that "Local sign-in constructs a synthetic claims payload and passes it to the mapper" — but never say what the developer types, or that the local settings module keeps `ModelBackend` and a non-empty `ACCOUNT_LOGIN_METHODS` for exactly that purpose. FR-13 says those states are refused when deployed; nothing says they are *required* locally. A reader implementing FR-6, FR-7, FR-13, and FR-17 in sequence has every incentive to delete them outright, at which point FR-18 and FR-32 (persona signs in with nothing installed) become unimplementable.

**Severity: medium-high.** The requirement most at risk of being optimized away by the requirements next to it.

**Suggested fix:** add consequences to FR-19: "Local settings retain `ModelBackend` and a non-empty `ACCOUNT_LOGIN_METHODS` so a persona can sign in without a reachable IdP; these are the same states FR-13 refuses when deployed, which is the point. Personas carry passwords, so `AUTH_PASSWORD_VALIDATORS` remains configured." Add a matching note that the `test.py` override of `PASSWORD_HASHERS` to a fast hasher is correct and stays (source §1.5: "under §1.6 it is correct and stays"), so no cleanup pass removes it as residue of the IdP-only target.

---

## 8. The remediation "inverts the default"; the PRD requires the refusal but not the flipped default for two of the four paths

**Source (§1.1):** "The defect is not that these paths exist… It is that they are **enabled by default and unguarded**… The remediation inverts that: available where they are configured on, refused at startup where they are not permitted." The four paths are located precisely: `base.py:274` / `users/admin.py:11` (`DJANGO_ADMIN_FORCE_ALLAUTH` defaults `False`), `REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES` plus `rest_framework.authtoken`, `base.py:343` (`ACCOUNT_LOGIN_METHODS = {"username"}`), and `urls.py:11,38` (`obtain_auth_token`).

**PRD:** paths 1, 2 and 4 get default-flipping requirements — FR-7 ("`DJANGO_ADMIN_FORCE_ALLAUTH` defaults to true"), FR-6 (all three token consequences, including the route deletion and the test asserting route absence rather than setting absence). Path 3 gets none: no FR states that the deployed configuration has an empty `ACCOUNT_LOGIN_METHODS` or that `ModelBackend` is absent from the deployed `AUTHENTICATION_BACKENDS`. FR-13 refuses those states and FR-4 implies the outcome ("redirects to the IdP, not to a local login form"), but a refusal with no corresponding default flip means the shipped deployed configuration refuses to start.

**Severity: medium.**

**Suggested fix:** add an FR alongside FR-6 and FR-7 — "FR-6a: local login is off in the deployed configuration" — with consequences: `ACCOUNT_LOGIN_METHODS` is empty and `AUTHENTICATION_BACKENDS` contains only the allauth backend when the environment declares itself deployed; `ModelBackend` and a non-empty `ACCOUNT_LOGIN_METHODS` are configured only in the local path of FR-19. This also gives FR-17's allowlist a stated expected value.

---

## 9. Object storage has a declared surface in the source and no FR anywhere in the PRD

**Source (§2):** object storage's surface is "`django-storages` 1.14.6 + `boto3` 1.43.65, both on conda-forge" and "`STORAGES` configuration"; §3 adds "**Object storage libraries: none present.** Genuinely greenfield". Source §7 factor 4 has object storage attaching by environment variable.

**PRD:** object storage appears as one of the four features in the Glossary, FR-24, FR-25 and the §12 factor-4 row ("PostgreSQL, cache, and object storage attach by environment variable"), but there is no FR describing what selecting it produces. Every other feature has at least one behavioural FR touching it — background tasks via FR-39/FR-45, Redis via FR-14/FR-47, server-rendered UI via FR-3. Object storage is the one feature that is entirely greenfield and the one with no requirement stating its behaviour, so §12 factor 4 asserts something no FR carries.

**Severity: medium.**

**Suggested fix:** add an FR to §4.5: "Where object storage is selected, the storage backend is configured entirely from environment variables — endpoint, bucket, and credentials — with no configuration file and no code change between environments, and the component makes no object-storage call at boot (FR-23)." Point §12 factor 4 at it.

---

## 10. `SESSION_ENGINE` and `clearsessions` — the mechanism names are dropped and the status is asserted in two tenses

**Source (§5.3):** "Sessions are database-backed in every combination (§7, factor 6)… `manage.py clearsessions` must run periodically, as a one-off admin process the platform schedules. It is deliberately *not* a Celery beat task: beat exists in only 8 of the 12 combinations." §7 factor 6 status: "Decided, **`SESSION_ENGINE` not yet set explicitly**".

**PRD:** FR-43 carries the whole reasoning and the 8-of-12 argument, and the priority note correctly splits component-side (must-have) from schedule-side (Next). Two smaller losses: neither `SESSION_ENGINE` nor `clearsessions` is named, so the requirement is "the session engine set explicitly" against an unnamed setting and "a one-off management process" against an unnamed command — both are things the source pinned and a test would need. And §12 factor 6 reads "engine set explicitly; … | Decided, **engine not yet set explicitly**", which restates the source's status correctly but sits oddly next to FR-43's consequence phrased in the present.

**Severity: low-medium.**

**Suggested fix:** name `SESSION_ENGINE = "django.contrib.sessions.backends.db"` and `manage.py clearsessions` in FR-43's consequences. Nothing else changes.

---

## 11. Two wrong FR cross-references

**PRD, internal:** FR-18's fourth consequence reads "The smoke check of **FR-33** passes for all twelve valid combinations" — the smoke check is **FR-32**; FR-33 is the materializer's refusal of invalid combinations. FR-25's second consequence reads "The materializer refuses the invalid pairing with a stated reason (**FR-34**)" — that is **FR-33**; FR-34 is the reported-bound policy. Both look like survivors of an FR renumber.

**Severity: low**, but they are the two references a reader follows to find the harness.

**Suggested fix:** FR-18 → FR-32; FR-25 → FR-33. Worth a sweep of the remaining cross-references at the same time (FR-13's "gitignore rule (FR-20)", FR-5→FR-18, FR-8→§4.4, SC-1's FR list all check out).

---

## 12. Package-name detail the source pinned and the PRD generalizes away

**Source (§1.3):** "Channel check (resolved): both are on conda-forge — `pyjwt` 2.13.0 and `cryptography` 50.0.0. **Note the rename from the PyPI name `PyJWT` to the conda package `pyjwt`.**" §2 similarly pins `django-storages` 1.14.6 and `boto3` 1.43.65.

**PRD:** FR-5 requires "PyJWT and `cryptography`" (the PyPI spelling); FR-49 says "the JWT and cryptography packages the authentication rewire needs". The channel-name rename is the kind of trap the Vision explicitly says the product exists to have already hit — "which packages, resolved from which channel… with which traps already hit and recorded next to the configuration they constrain" — and FR-48 requires "the dependency manifest carries the reasoning for its own non-obvious lines", which is exactly where this belongs.

**Severity: low.** Mechanism legitimately stays in the source addendum, but a requirement citing the wrong package spelling is a small trap of its own.

**Suggested fix:** in FR-5, write the channel name (`pyjwt`) with the PyPI name in parentheses, or drop package spellings from FR-5 entirely and let FR-48/FR-49 own naming. Related: the PRD addendum §4 already records that `pixi.toml:90` still declares `django-celery-beat` under `[pypi-dependencies]` — FR-48's "a test or gate step asserts that the package-index dependency block is empty" will fail until that repository work is done, which is correct and worth stating as the exit condition rather than a surprise.

---

## Verified as correctly carried, no action

For completeness, the following source content was checked and found faithfully represented: §1.1 paths 1/2/4 and the "a refusal that inspects only settings will not see it" argument (FR-6, FR-15); §1.2 the two flows and their dependency costs, and why `TokenAuthentication` cannot be adapted (§4.2 description, FR-4, FR-5); §1.3 rejected alternatives (cited, not duplicated, as intended); §1.4/§1.4.1 the three callers, the five mapper steps including removal, the `src/config/authorization/` placement and both reasons for it, and the claims contract as configuration (FR-8, FR-9, FR-10, FR-11); §1.6 the five-path refusal table, both escape failure modes, seeded personas, the on-demand keypair and the "one published private key shared by every component" argument, and the rejected local IdP container (FR-12, FR-13, FR-16, FR-19, FR-20, NFR-7, §5); §2.1 the always-present/conditional OTel split including `-instrumentation-psycopg` and the `django-structlog` Celery caveat (FR-2); §2.2 admin orthogonality (FR-3); §3.1 the MFA orphan finding as the origin of the orphan concept (Glossary, FR-28); §4.1 selection/verification/presets separation and the rejected menu framing (§4.6, FR-26); §4.2 the 12-of-16 arithmetic (FR-25); §4.2.1 the provenance stamp and its "which components predate it" justification (FR-35); §4.2.2 the full three-way disposition list (FR-36, subject to gaps 1–3); §4.2.3 both verification levels and the fixture-set consequence (FR-29..FR-32, FR-30); §4.3 the two-checks-per-combination model and the "no workflow declares services:" current state (FR-31, FR-32); §4.4 the 32-combination all-pairs policy and the explicit-reporting rule (FR-34, CG-2); §5 all five interface bullets (FR-37, FR-38, FR-41, FR-44, FR-13); §5.1 the process model and beat's single replica (FR-39); §5.2 release-stage migrations, the unmigrated-schema refusal, and drain ordering (FR-40, FR-42); §5.4 both endpoints, the crash-loop argument for liveness, and the rolling-deploy argument against re-checking migrations (FR-41, NFR-2); §6.1 all four substitutions and their "not exercised" columns (FR-18, §11); §6.1.1 discard-at-the-processor and the rejected unreachable-endpoint exporter (FR-21, FR-44); §6.1.2 the provenance of the substitutions (§4.4 description); §6.2 the broker constraint's scope (FR-22); §6.3 the six→eight expansion, the two conditional refusals and their four-combination justification, and `IGNORE_EXCEPTIONS` becoming visible (FR-13, FR-14, FR-47); §7 all fifteen factor statuses (§12); §8 propagation as a named non-goal (§5).
