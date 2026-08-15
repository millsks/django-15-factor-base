---
stepsCompleted: [1, 2, 3, 4, 5, 6]
status: READY
findings: 11
findingsFixed: 4
criticalIssues: 0
frCoverage: 56/56
nfrCoverage: 8/8
documentsAssessed:
  - _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md
  - _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/specs/spec-django-15-factor-base/SPEC.md
  - _bmad-output/specs/spec-django-15-factor-base/capability-map.md
uxDocument: none
duplicatesFound: none
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-15
**Project:** django-15-factor-base

## Step 1 — Document Discovery

### PRD Files Found

**Whole Documents:**

- `prds/prd-django-15-factor-base-2026-08-14/prd.md` (107,724 bytes, modified 2026-08-14) — status `final`, FR-1..FR-56, NFR-1..NFR-8, SC-1..SC-7, CG-1..CG-4

**Sharded Documents:** none.

**Supporting files in the same folder** (not the PRD itself, not assessed as the PRD): `addendum.md`, `reconcile-brief.md`, `reconcile-brief-addendum.md`, `review-architect-readiness.md`, `review-edge-cases.md`, `review-rubric.md`, `.memlog.md`.

### Architecture Files Found

**Whole Documents:**

- `architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md` (47,555 bytes, modified 2026-08-15) — status `final`, AD-1..AD-32, binds FR-1..FR-56 / NFR-1..NFR-8 / SC-1..SC-7 / CG-1..CG-4

**Sharded Documents:** none.

**Supporting files in the same folder** (not assessed as the architecture): `reviews/review-adversarial.md`, `reviews/review-tech-verification.md`, `walkthrough.html`, `.memlog.md`.

### Epics & Stories Files Found

**Whole Documents:**

- `epics.md` (120,815 bytes, modified 2026-08-15) — 9 epics, 66 stories, `stepsCompleted: [1, 2, 3]`

**Sharded Documents:** none.

### UX Design Files Found

**Whole Documents:** none.
**Sharded Documents:** none.

No `ux-designs/ux-*/DESIGN.md` + `EXPERIENCE.md` spine pair, no legacy `*ux*.md`, no sharded `*ux*/index.md`.

### Documents Outside the Search Patterns

The spec kernel is at `_bmad-output/specs/`, which the `{planning_artifacts}` patterns do not reach. It was an input to the epics and stories and declares itself the canonical contract, so it is included in this assessment:

- `specs/spec-django-15-factor-base/SPEC.md` — CAP-1..CAP-10, constraints, non-goals, assumptions, open questions
- `specs/spec-django-15-factor-base/capability-map.md` — the CAP → FR / NFR / SC / CG / AD crosswalk

### Issues Found

**Duplicates:** none. Each document type resolves to exactly one whole document with no sharded counterpart.

**Missing documents:** UX design specification absent. Assessed as **not applicable rather than a gap** — the primary product surface is a repository, the ordering surface is the enterprise developer portal (a stated non-goal), and the only rendered surfaces a component owns are the Django admin, framework error pages, and the optional server-rendered UI feature. PRD §2.3 states the user journeys are deliberately downscaled to anchor requirements rather than feed UX work. The visual-surface obligations that exist are carried as FR-3, AD-29 and AD-30 and are covered by epic stories 7.4 and 8.8.

## Step 2 — PRD Analysis

`prd.md` read in full (976 lines). The PRD numbers its requirements globally as FR-1..FR-56 across ten feature groups, each group carrying a priority, with cross-cutting non-functional requirements in their own section. Every FR states a normative requirement followed by a list of testable consequences; the requirement statement is extracted below.

### Functional Requirements

**§4.1 The Immovable Core** — *Phase-1 must-have*

- **FR-1:** Every valid combination provides the immovable core, and no feature selection removes any part of it.
- **FR-2:** The dependency manifest of a materialized combination contains the instrumentation packages that combination's capabilities require, and no others.
- **FR-3:** Selecting or omitting the server-rendered UI feature does not affect the presence or function of the Django admin.

**§4.2 Authentication and Authorization** — *Phase-1 must-have; none implemented*

- **FR-4:** A person can authenticate to the Django admin and the server-rendered UI by redirect to the IdP using Authorization Code with PKCE, receiving a session cookie.
- **FR-5:** An API client can authenticate by presenting `Authorization: Bearer <JWT>`, which the component validates against the IdP's JWKS endpoint.
- **FR-6:** A deployed component contains no path that issues or accepts a locally minted API token.
- **FR-7:** In a deployed component, `/admin/` login is served by the IdP redirect and never by Django's own credential form.
- **FR-8:** Every authentication, by any flow, resolves authorization through a single mapper located at `src/config/authorization/`.
- **FR-9:** On every authentication the mapper resolves or creates the user, adds the group memberships the claims assert, removes the memberships the claims no longer assert, sets staff status from the designated group, and emits a structured log line recording what changed.
- **FR-10:** Which claim carries group membership, and which group confers staff status, are read from the environment rather than hardcoded.
- **FR-11:** In a deployed component, the first administrator is established by IdP group claim rather than by `createsuperuser`.

**§4.3 The Refusal Contract** — *Phase-1 must-have; one condition built*

- **FR-12:** Conditions readable from settings alone are evaluated at settings import, by shared code every settings module imports; conditions requiring the application registry are evaluated at serving-process startup; the decision *am I deployed?* is read from the environment, never inferred from which module was loaded.
- **FR-13:** A deployed component refuses to start when any of seven unconditional conditions holds, regardless of which features it selected.
- **FR-14:** A deployed component refuses to start on two further conditions, each scoped to the feature that makes it meaningful.
- **FR-15:** The credential-path refusal resolves the URL configuration and fails on a reachable token-minting route.
- **FR-16:** The suite asserts that deployed settings *refuse*, not merely that they start.
- **FR-17:** The suite asserts that the component's authentication surface matches an approved set exactly, so a path introduced after this PRD fails the build until someone adds it deliberately.

**§4.4 The Local Development Contract** — *Phase-1 must-have*

- **FR-18:** Every valid combination starts, serves, and authenticates a persona on a machine with no database, cache, broker, or identity provider running.
- **FR-19:** Local identities are declared as configuration — named personas with their groups and profile fields — and a development task materializes them as local accounts.
- **FR-20:** A development task mints a JWT signed by a locally generated keypair, and local settings point the JWKS location at that key, so the real Bearer authentication class verifies it.
- **FR-21:** Local development runs the same observability code the deployed component runs; only the terminal export step is absent.
- **FR-22:** Locally, all twelve valid combinations run with no broker.
- **FR-23:** OIDC discovery and JWKS retrieval occur lazily on first use, never at import or at boot, so a component starts with no route to the IdP.

**§4.5 The Feature Model and Clean Extraction** — *Phase-1 must-have*

- **FR-24:** A lead developer can select any subset of background task processing, Redis cache, server-rendered UI, and object storage; every feature's surface is declared in a single machine-readable artifact with a named location.
- **FR-25:** Where selected, a component stores documents and blobs against an S3-compatible object store configured by environment variable.
- **FR-26:** Background task processing without the Redis cache is refused at generation rather than emitted as a component that cannot start.
- **FR-27:** The three presets — *API-only*, *Full web app*, *Worker-enabled* — set a starting selection and remain fully editable.
- **FR-28:** No materialized combination contains a dependency, template, static asset, settings fragment, or test belonging to a feature it did not select.
- **FR-29:** The coverage signal that catches incomplete feature removal is preserved in per-combination verification, across every residue category that signal can reach.

**§4.6 The Verification Model** — *Phase-1 must-have*

- **FR-30:** A developer or CI job can materialize the complete source of any of the twelve valid combinations from the reference application.
- **FR-31:** Materialization supplies test values for every parameter the enterprise developer portal would supply.
- **FR-32:** All twelve valid combinations are materialized and put through tests, coverage at or above ninety percent including templates, strict type checking, lint, and build, against PostgreSQL.
- **FR-33:** All twelve valid combinations boot, return 200 from readiness, and authenticate a persona with no external service running.
- **FR-34:** A request to materialize background task processing without the Redis cache fails with the reason.
- **FR-35:** If the verification set is ever narrower than the full valid combination space, the run states what was excluded.
- **FR-36:** Every materialized combination records the accelerator version and the order values that produced it.
- **FR-37:** Materialized output excludes the accelerator's tooling and planning artifacts, and parameterizes what is correct for this repository but wrong for any other.

**§4.7 The Deployment Interface** — *Phase-1 must-have, except FR-44's scheduling half which is Next*

- **FR-38:** A deployed component reads all configuration from environment variables, with no configuration file baked into the image.
- **FR-39:** A deployed component starts under a UID assigned by the platform and writes to no fixed path.
- **FR-40:** Each combination declares which process types it runs and their commands.
- **FR-41:** A component never migrates itself at startup, and refuses to start against a schema it does not recognize.
- **FR-42:** A component exposes a liveness endpoint and a readiness endpoint with deliberately different semantics.
- **FR-43:** On `SIGTERM` a web process reports unready, stops accepting connections, finishes in-flight requests, and exits; a worker finishes its current task and declines new ones.
- **FR-44:** Expired session rows are pruned by a one-off management process the platform schedules; sessions are database-backed in every combination with the engine set explicitly.
- **FR-45:** OTLP export is controlled by environment; with no collector configured, spans are discarded rather than retried.

**§4.8 Observability** — *Phase-1 must-have; largely satisfied today*

- **FR-46:** Every component writes a JSON event stream to stdout in which log lines carry the request correlation ID, trace ID, and span ID.
- **FR-47:** Requests served over ASGI produce spans.
- **FR-48:** Where the Redis cache feature is selected, swallowed cache failures become log events.

**§4.9 Supply Chain and Dependency Policy** — *Phase-1 must-have*

- **FR-49:** Every dependency in every combination resolves from the approved channel, and any exception is recorded at the point of declaration with its reason and its exit condition.
- **FR-50:** A new selectable feature is not accepted until its dependencies are confirmed present on the approved channel *and* confirmed to work against the pinned runtime.

**§4.10 The Extension Model** — *Phase-1 must-have; none exists*

- **FR-51:** The component's base package presents a declared surface that reusable apps may depend on, and changes to it are treated as breaking.
- **FR-52:** A component has one declared location for the applications it owns, and the accelerator neither supplies nor judges their contents.
- **FR-53:** An application developed inside a component keeps its import path when it is published to the channel and adopted elsewhere.
- **FR-54:** An adopted application may introduce configuration a component did not have, and may not alter configuration that already exists.
- **FR-55:** Where an adopted application brings its own backing service, the substitutions of §4.4 extend to it without the application having to arrange it.
- **FR-56:** A reusable app states which versions of the base it supports, and adopting it into an incompatible component fails the gate rather than failing in production.

**Total FRs: 56.** Contiguous FR-1..FR-56 with no gaps and no duplicates.

### Non-Functional Requirements

- **NFR-1 — Startup fails fast, and cheaply.** Any misconfiguration in the refusal contract surfaces at boot as `ImproperlyConfigured`, never as scattered runtime errors. The nine checks are settings and URL-configuration inspection with no network call and no query beyond the migration state.
- **NFR-2 — Liveness touches nothing external.** A system-wide invariant any future health work must preserve.
- **NFR-3 — Statelessness.** Components share nothing through local disk or process memory across replicas; sessions are database-backed in every combination.
- **NFR-4 — Strict typing and lint are gate conditions, not advisories.** No combination passes with type or lint errors.
- **NFR-5 — Determinism.** Materialization and dependency resolution are reproducible: the same selections and the same lock file produce the same component.
- **NFR-6 — Telemetry overhead is measured, not assumed.** Measured once against the reference application, recorded alongside the observability documentation, re-measured only when the instrumentation set changes.
- **NFR-7 — Secrets never live in source.** No credential, key, or token is committed; the development keypair is generated on demand into a gitignored path.
- **NFR-8 — Documentation travels with what it describes.** Component-facing documentation is materialized with the component; accelerator-facing documentation is not.

**Total NFRs: 8.** Deliberately behavioural rather than numeric — PRD §6.2 places concrete figures (probe timings, startup budget, termination grace, resource limits, JWKS cache TTL) out of MVP scope for architecture to pin against the real platform.

### Additional Requirements

**Success criteria (SC-1..SC-7)** — binary and machine-checked, deliberately not adoption metrics, because those depend on portal telemetry outside this product's control. SC-1 every valid combination builds and passes; SC-2 excluded features leave nothing behind; SC-3 a component is deployable unmodified; SC-4 a component runs locally with nothing else installed; SC-5 no deployed component authenticates outside the IdP; SC-6 the IdP authentication path works; SC-7 the immovable core functions in every combination.

**Anti-gaming criteria (CG-1..CG-4)** — each forbids a way a primary criterion could be made to pass while the product got worse: do not narrow what coverage measures; do not shrink the verification set; do not soften a refusal into a warning; do not substitute a capability that could run locally as deployed.

**Constraints and guardrails (§9)** — the IdP is the only credential authority in a deployed component; authorization is decided in exactly one place; revocation must reach the component; no network surface exists beneath URL routing; an adopted application cannot acquire authority over requests it does not own; one audited channel with zero current exceptions; no feature is committed to before its dependencies are confirmed.

**Integration dependencies (§10)** — enterprise developer portal, identity provider, deployment repository, approved package channel, code-quality platform, CI provider, code host as a template repository, and reusable applications.

**Risks (§11)** — one check carries the whole guarantee; no break-glass account (accepted); dev/prod parity deliberately traded; local development proves less than running suggests; phase 2 blinds the gate until the harness exists; orphan detection depends on coverage; the OTLP export path is never exercised locally; channel availability constrains the feature model.

**Live assumptions (§14)** — four remain: `django-storages` fitness against the pinned Django and Python; session lifetime as the accepted revocation latency; the platform's termination grace period; the existence of a platform startup-time budget. Five earlier assumptions were resolved into requirements, and two more were closed by architecture.

**Open questions (§13)** — two: the accepted revocation latency (owner: platform group) and the number of writable paths a component needs (closed by architecture from the component's side, per §14 item 3).

### PRD Completeness Assessment

**Complete and unusually rigorous for this stage.** Every FR carries testable consequences rather than prose intent, which is why the epics could be written with concrete acceptance criteria rather than restatements. Requirements are contiguous, the glossary is enforced verbatim throughout, priorities are stated per feature group, and assumptions are tagged inline and indexed. Non-goals are explicit and argued rather than listed.

Three defects found, none blocking:

1. **FR-13's internal arithmetic is inconsistent.** The requirement statement says "seven conditions" and then lists eight bullets, against a stated total of nine in §4.3 and FR-16. Separately, AD-27 in the architecture declares a stage-2 refusal — a designated group absent from the database — that appears in no FR-13 bullet, which under a strict per-bullet reading would make ten. Resolved during epic creation to a nine-condition, fourteen-forbidden-state table now recorded in `epics.md`. **The PRD itself is still wrong and should be reconciled to that table on its next revision.**
2. **`prd.md` frontmatter reads `updated: 2026-08-16`** — one day after its own commit (`b8a3fd9`, 2026-08-15) and one day in the future relative to today. Already recorded as an open question in the spec kernel. Cosmetic; no content depends on it.
3. **Three requirements carry no owner** — FR-45's OTLP export end-to-end test and its collector stub design, NFR-6's telemetry-overhead measurement and its milestone, and FR-31's dependency on a portal order-surface field list that does not yet exist. The architecture spine records all three as Open Items. Each now has a story whose acceptance criteria include naming an owner.

## Step 3 — Epic Coverage Validation

`epics.md` read completely (2,300 lines): 9 epics, 66 stories, an FR Coverage Map, an NFR coverage line, a cross-epic threads section, and a resolved-refusal-count table. Coverage was verified two ways — mechanically, that every identifier appears; and substantively, that the mapped story's acceptance criteria actually discharge the requirement rather than merely naming it.

### Coverage Matrix

Requirement text is abbreviated here; full text is in Step 2 above.

| FR | PRD Requirement | Epic Coverage | Status |
|---|---|---|---|
| FR-1 | Immovable core present in every combination | Epic 7 / 7.4, Epic 8 / 8.10 | ✓ Covered |
| FR-2 | Instrumentation by capability, not package list | Epic 7 / 7.2, Epic 8 / 8.7 | ✓ Covered |
| FR-3 | Admin orthogonal to the UI feature | Epic 7 / 7.4 | ✓ Covered |
| FR-4 | Interactive authentication against the IdP | Epic 2 / 2.6 | ✓ Covered |
| FR-5 | Programmatic authentication against the IdP | Epic 2 / 2.7 | ✓ Covered |
| FR-6 | Static-token credential surface removed | Epic 2 / 2.8 | ✓ Covered |
| FR-7 | Admin forced through the IdP | Epic 2 / 2.6 | ✓ Covered |
| FR-8 | One shared mapper owns authorization | Epic 2 / 2.4 | ✓ Covered |
| FR-9 | Re-sync on every authentication, including revocation | Epic 2 / 2.5 | ✓ Covered |
| FR-10 | Claims contract is configuration | Epic 2 / 2.2 | ✓ Covered |
| FR-11 | Superuser creation retired as deployed bootstrap | Epic 2 / 2.3, 2.5 | ✓ Covered |
| FR-12 | Two evaluation points, independent of settings module | Epic 4 / 4.1 | ✓ Covered |
| FR-13 | Seven unconditional refusals | Epic 4 / 4.2, 4.3 | ✓ Covered |
| FR-14 | Two conditional refusals | Epic 4 / 4.4 | ✓ Covered |
| FR-15 | Refusal inspects the URL configuration | Epic 4 / 4.3 | ✓ Covered |
| FR-16 | Refusals tested as refusals | Epic 4 / 4.5 | ✓ Covered |
| FR-17 | Allowlist catches later credential paths | Epic 4 / 4.6 | ✓ Covered |
| FR-18 | Runs locally with nothing installed | Epic 3 / 3.2, 3.3; Epic 7 / 7.5; Epic 8 / 8.10 | ✓ Covered (split) |
| FR-19 | Personas seeded from declared claims | Epic 3 / 3.3, 3.4 | ✓ Covered |
| FR-20 | Local programmatic flow validates for real | Epic 3 / 3.5 | ✓ Covered |
| FR-21 | Observability not substituted locally | Epic 3 / 3.6 | ✓ Covered |
| FR-22 | Broker constraint is about deployment only | Epic 3 / 3.2 | ✓ Covered |
| FR-23 | No network on the local start path at boot | Epic 3 / 3.7 | ✓ Covered |
| FR-24 | Four features declared in one carrier | Epic 7 / 7.1, 7.3, 7.6 | ✓ Covered |
| FR-25 | Object storage attaches an S3-compatible backend | Epic 7 / 7.5 | ✓ Covered |
| FR-26 | Broker constraint enforced at selection | Epic 7 / 7.6; Epic 8 / 8.5 | ✓ Covered (split) |
| FR-27 | Presets pre-select without constraining | Epic 7 / 7.6 | ✓ Covered |
| FR-28 | Excluded features leave nothing behind | Epic 7 / 7.5, 7.7; Epic 8 / 8.7 | ✓ Covered (split) |
| FR-29 | Orphan detection survives into the harness | Epic 7 / 7.8; Epic 8 / 8.8 | ✓ Covered (split) |
| FR-30 | Materializer produces any valid combination | Epic 8 / 8.2, 8.3, 8.4 | ✓ Covered |
| FR-31 | Materializer carries a fixture set | Epic 8 / 8.6 | ✓ Covered |
| FR-32 | Every combination passes the gate against PostgreSQL | Epic 1 / 1.2; Epic 8 / 8.8 | ✓ Covered (split) |
| FR-33 | Every combination passes a local smoke check | Epic 8 / 8.10 | ✓ Covered |
| FR-34 | Materializer refuses invalid combinations | Epic 8 / 8.5 | ✓ Covered |
| FR-35 | Any bound on verification is reported | Epic 8 / 8.9 | ✓ Covered |
| FR-36 | Materialized output carries the provenance stamp | Epic 8 / 8.11 | ✓ Covered |
| FR-37 | Accelerator machinery does not reach a component | Epic 7 / 7.3; Epic 8 / 8.7 | ✓ Covered (split) |
| FR-38 | Configuration is exclusively environmental | Epic 5 / 5.6 | ✓ Covered |
| FR-39 | Runs as an arbitrary non-root user | Epic 5 / 5.6 | ✓ Covered |
| FR-40 | Process model declared per combination | Epic 5 / 5.1, 5.2 | ✓ Covered |
| FR-41 | Migrations are a release-stage step | Epic 4 / 4.3; Epic 5 / 5.5 | ✓ Covered (split) |
| FR-42 | Two asymmetric health endpoints | Epic 5 / 5.3 | ✓ Covered |
| FR-43 | Shutdown drains in a defined order | Epic 5 / 5.4 | ✓ Covered |
| FR-44 | Session engine explicit; pruning as admin process | Epic 5 / 5.7 | ✓ Covered |
| FR-45 | Trace export environmental; export path gated | Epic 6 / 6.3, 6.4 | ✓ Covered |
| FR-46 | Correlated structured logging | Epic 6 / 6.1 | ✓ Covered |
| FR-47 | ASGI request tracing | Epic 1 / 1.4; Epic 6 / 6.2 | ✓ Covered |
| FR-48 | Degradation is visible | Epic 6 / 6.5 | ✓ Covered |
| FR-49 | Single audited channel with recorded exceptions | Epic 1 / 1.7 | ✓ Covered |
| FR-50 | Channel availability and fitness checked first | Epic 1 / 1.8 | ✓ Covered |
| FR-51 | Base package is a stable import surface | Epic 9 / 9.1 | ✓ Covered |
| FR-52 | Component extends through a declared tenant space | Epic 9 / 9.2 | ✓ Covered |
| FR-53 | Reusable app graduates without changing import path | Epic 9 / 9.5 | ✓ Covered |
| FR-54 | Reusable app adds configuration and never changes it | Epic 9 / 9.4 | ✓ Covered |
| FR-55 | Contributed backing service inherits the local contract | Epic 9 / 9.7 | ✓ Covered |
| FR-56 | Base compatibility declared and checked at adoption | Epic 9 / 9.6 | ✓ Covered |

**NFR coverage:** NFR-1 → 4.1 · NFR-2 → 5.3 · NFR-3 → 5.6, 5.7 · NFR-4 → 1.3 · NFR-5 → 1.7, 8.2 · NFR-6 → 6.6 · NFR-7 → 1.7, 3.5 · NFR-8 → 1.4, 8.5. All eight covered.

### Missing Requirements

**None.** No FR from the PRD is absent from the epics, and no requirement appears in the epics that does not exist in the PRD. Seven FRs are deliberately split across two epics; each split is recorded in the epics document's cross-epic threads section with its reason, and in every case one epic declares or implements while the other verifies against materialized output.

### Coverage Statistics

- Total PRD FRs: **56**
- FRs covered in epics: **56**
- Coverage percentage: **100%**
- Total PRD NFRs: **8**
- NFRs covered in epics: **8** (100%)
- Stories: **68** across 9 epics (66 at assessment time; Story 8.2 split into three during remediation)
- FRs covered by a single story: 40 · by two or more stories within one epic: 9 · split across epics: 7

### Traceability Finding — stories do not cite requirement identifiers inline

Coverage is complete, but the *instrument* of traceability is the FR Coverage Map, not the stories. Only five FR identifiers appear anywhere inside the nine epic bodies; the remaining stories express their requirement behaviourally and rely on the map for linkage.

**Impact:** a developer picking up Story 5.3 sees correct, testable acceptance criteria but no path back to FR-42, NFR-2 or AD-22 without opening the map and reading upward. The linkage also becomes fragile under edit — splitting or renumbering a story does not update the map, and nothing detects the divergence.

**Recommendation:** add one reference line per story naming the FRs, NFRs and ADs it discharges. Sixty-six lines, mechanical, and it makes each story self-contained for `bmad-create-story`, which builds per-story context files in phase 4 and would otherwise have to re-derive the linkage. Recorded here as a finding for decision rather than applied unilaterally, since it is a small deviation from the epics template's story structure.

## Step 4 — UX Alignment Assessment

### UX Document Status

**Not Found.** No `ux-designs/ux-*/DESIGN.md` + `EXPERIENCE.md` spine pair, no legacy `*ux*.md`, no sharded `*ux*/index.md`.

### Is a user interface implied?

Checked rather than assumed. Both source documents do assert UI surface:

| Term | PRD | Spine |
|---|---|---|
| "server-rendered UI" | 11 | 1 |
| "static asset" | 7 | — |
| "template override" | 3 | — |
| `base.html` / error templates | — | 3 |
| form styling / page template / user-facing | 3 | 3 |
| messages framework, rendered admin, rendered 404 | 2 | 2 |

So a UI surface exists in three forms: the Django admin (immovable, framework-provided), framework error pages (403/404/500 extending `base.html`), and the optional **server-rendered UI feature**, one of the four selectable features.

**Assessment: UX documentation is not required for phase 1, and its absence is not a gap.** The reasoning is specific rather than a blanket "no UI":

- No *new* end-user experience is designed here. The UI surface is inherited from the fork this repository began as, and phase 1's work on it is **removal mechanics** — making the feature cleanly excisable — not design.
- The product surface a user actually receives is a repository. The ordering surface where a lead developer makes choices is the enterprise developer portal, an explicit non-goal (§5) owned by another team.
- PRD §2.3 states the user journeys were deliberately downscaled to anchor requirements rather than feed UX work, and names the beats phase 1 cannot deliver end to end.
- User media is an explicit non-goal; avatars resolve from IdP profile metadata as remote URLs, so no media or upload experience exists to design.

### Alignment Issues

**None between UX and PRD or UX and Architecture**, there being no UX document to misalign. The UI-adjacent requirements that exist are internally consistent across the three documents: FR-3 (admin orthogonal to the UI feature) is governed by AD-29 (no `feature:*` disposition inside `django_service`; `base.html` and error templates stay) and verified by AD-30 (the smoke check asserts a rendered admin index and a rendered 404). Epic stories 7.4 and 8.8 carry both.

### Warnings

**W-1 — The server-rendered UI feature's surface is not enumerated in any source document.** This is where the absent UX artifact actually bites, and it bites as a *declaration* gap rather than a design gap.

AD-29 requires that "surface that genuinely belongs to the server-rendered UI feature — user-facing page templates, form styling, user-facing views and forms — moves out of `django_service` into a feature-owned location before that feature is extracted," and FR-24 requires the carrier to be the only place a feature's extent is defined. But **neither the PRD nor the spine names which templates, views, forms or static assets constitute that surface.** The category is described; its members are not listed anywhere.

- *Impact:* Story 7.4 requires the relocation and Story 7.1 requires the declaration, but whoever picks them up must first derive the inventory by auditing the existing tree. Get it wrong in the permissive direction and `base.html` or an error template leaves `django_service`, breaking template rendering in the six combinations where FR-3 explicitly requires it to work. Get it wrong in the restrictive direction and UI surface stays behind as residue in six combinations — precisely the orphan class that cost this project two template overrides before.
- *Severity:* Medium. It is discoverable work with a detector behind it — AD-2's input reconciliation fails on any path no disposition claims, and AD-20's coverage signal catches an orphaned template — so a wrong answer fails the gate rather than shipping. But it is unestimated work sitting inside two stories that read as though the inventory already exists.
- *Recommendation:* Add an explicit first acceptance criterion to Story 7.4 requiring the UI feature's surface to be enumerated by audit and recorded in the carrier before any file moves. No UX design work is needed — this is an inventory of what is already in the tree.

**W-2 — No accessibility, responsive or browser-support requirement exists anywhere.** A direct consequence of having no UX document: nothing in the PRD, the spine or the spec asserts a contrast standard, a keyboard-navigation requirement, an ARIA pattern, a breakpoint, or a supported-browser set — for the admin, the error pages, or the server-rendered UI feature.

- *Impact:* Low for phase 1 as scoped. The admin's accessibility is Django's, the error pages are minimal, and the UI feature ships whatever it inherited. No component-facing promise is being made that this absence would break.
- *Severity:* Low, but worth naming rather than leaving silent. The moment a team builds an end-user surface on this base — which the extension model of §4.10 exists to enable — the base will have handed them no standard to inherit, and each component will answer the question differently. That is the same estate-consistency failure the product exists to prevent, one layer up.
- *Recommendation:* Not a phase-1 blocker. Worth an entry on the phase-2 or platform-standards backlog rather than a story here.

## Step 5 — Epic Quality Review

Reviewed against the create-epics-and-stories standards: user value, epic independence, story sizing, acceptance-criteria quality, dependency direction, and entity-creation timing. **No critical violations. Three major issues and three minor concerns.**

### Best Practices Compliance Checklist

| Epic | User value | Independent | Sized | No fwd deps | Entities when needed | Clear ACs | FR traceability |
|---|---|---|---|---|---|---|---|
| 1 — Gate and supply chain | ⚠ platform-group only | ✓ | ✓ | ✓ | n/a | ✓ | ⚠ map only |
| 2 — IdP authentication | ✓ | ✓ | ⚠ 2.5 | ✓ | ✓ | ✓ | ⚠ map only |
| 3 — Clone and run | ✓ | ✓ | ✓ | ✓ | n/a | ✓ | ⚠ map only |
| 4 — Refusal contract | ✓ | ✓ | ⚠ 4.2 | ✓ | n/a | ✓ | ⚠ map only |
| 5 — Deployment interface | ✓ | ✓ | ✓ | ✓ | n/a | ✓ | ⚠ map only |
| 6 — Observability | ✓ | ✓ | ✓ | ✓ | n/a | ✓ | ⚠ map only |
| 7 — Feature model | ✓ | ✓ | ✓ | ✓ | n/a | ✓ | ⚠ map only |
| 8 — Twelve combinations | ✓ | ✓ | ⚠ 8.2 | ✓ | n/a | ✓ | ⚠ map only |
| 9 — Extension model | ✓ | ✓ | ⚠ 9.4 | ✓ | n/a | ✓ | ⚠ map only |

### 🔴 Critical Violations

**None.** No epic is a pure technical milestone with no stated user, no epic requires a later epic to function, and no story depends on a later story.

### 🟠 Major Issues

**M-1 — Two success criteria have no verification path inside phase 1.**

Every FR is covered, but coverage of requirements is not the same as coverage of criteria, and two of the seven cannot be closed by anything in this plan:

- **SC-6 ("The IdP authentication path works")** requires *a real IdP identity* to authenticate through both flows and produce correct authorization state. No story stands up an identity provider or tests against one. A local IdP container is an explicit PRD non-goal, and the local personas of Epic 3 are synthetic claims by design — the PRD is explicit that they are "not a mitigation." So Epic 2 can be fully implemented, fully unit-tested, and pass every story's acceptance criteria while SC-6 remains unproven. This is the criterion covering the largest unbuilt block in the product.
- **SC-3 ("A component is deployable unmodified")** requires a component to be *containerized by CI and started on the target platform*. Story 5.6 delivers the component-side half — environmental configuration, arbitrary UID, read-only filesystem, the machinery Dockerfile — but deployment configuration is a separate repository and an explicit non-goal, so nothing here starts a component on the platform.

*Impact:* "Phase 1 complete" will not mean "all seven success criteria proven." Five will be machine-verified by the harness; two will rest on work outside this repository. Left unstated, that gap gets discovered at the moment someone claims the phase is done.

*Recommendation:* Not new stories inside these epics — neither gap is this repository's to close. Record both explicitly as **exit criteria requiring an external environment**, name their owners (platform group for the IdP realm, deployment repository for the platform start), and schedule them as an integration milestone after Epic 5 and Epic 2 land. The alternative — quietly treating five-of-seven as done — is exactly the kind of silent narrowing CG-2 forbids elsewhere in this product.

**M-2 — Story-level requirement traceability is absent.** Carried forward from Step 3. Only five FR identifiers appear inside the nine epic bodies; every other story relies on the FR Coverage Map for linkage. The compliance checklist above marks this per-epic because it fails for all nine. *Recommendation:* one reference line per story naming the FRs, NFRs and ADs it discharges — 66 mechanical additions that make each story self-contained for `bmad-create-story`.

**M-3 — Four stories carry sizing risk, one seriously.**

- **Story 8.2 (the materializer)** is the single largest engineering item in the plan: subtractive copy, path-level pruning, region-level pruning, self-exclusion, equivalence with the reference application, and a byte-identical determinism assertion. It is unlikely to fit one dev session. *Recommendation:* split into (a) copy plus path-granularity pruning, (b) region-granularity pruning, (c) determinism and equivalence assertions. Each is independently completable in that order.
- **Story 1.3 (strict mypy)** has genuinely unknown fallout — the tree currently sets `check_untyped_defs`, and nobody has measured the distance to `strict`. It sits on the critical path for every later epic. *Recommendation:* measure the error count before committing the story to a sprint; split by module if it is large.
- **Story 2.5 (mapper sync)** carries eight acceptance criteria spanning the sync algorithm, the epoch record and table, the `jti` rejection rule, and four edge behaviours. *Recommendation:* consider splitting the epoch-record mechanism from the sync algorithm.
- **Story 4.2 (five stage-1 conditions, eight forbidden states)** and **Story 9.4 (the closed contribution surface)** are large but cohesive; splitting either would fragment a single mechanism. Flagged for awareness rather than action.

### 🟡 Minor Concerns

**m-1 — Epic 1 delivers value to the platform group only, and is the closest thing here to a technical epic.** Its stories are CI consolidation, a database service, type-checking strictness, a deletion, a coverage floor, an import-root cleanup, a dependency assertion and a spike. By the letter of the standard — "Infrastructure Setup — not user-facing" — this is a violation.

Accepted deliberately, for a reason specific to this product: the platform and architecture group is a named user in PRD §2.1 whose job to be done is *"make conformance to the platform standard provable rather than merely claimed,"* and in this product the quality gate is not scaffolding that supports the deliverable — it substantially **is** the deliverable. Every one of SC-1 through SC-7 is a statement about what the gate proves, and CG-1 and CG-2 exist solely to stop the gate being weakened. An epic that makes the gate real is user value here in a way it would not be in an ordinary application. Recorded rather than remediated.

**m-2 — Four stories create a declaration artifact rather than a user capability:** 2.1 (the identity-key field), 5.1 (`component.toml`), 7.1 (`accelerator.toml`) and 7.3 (the parameter declarations). Each is justified — the architecture requires each to have exactly one declared home, and each is consumed by the very next stories — and none is a bulk upfront-setup story of the kind the standard forbids. Story 2.1 is the thinnest; it stays separate because backfilling a nullable unique field against existing databases is a discrete migration risk worth its own review.

**m-3 — Roughly six acceptance criteria are policy or rationale statements rather than verifiable conditions.** Examples: Story 1.4's final criterion about future sub-router protocols; Story 1.2's and 3.2's closing criteria that the sqlite divergence "remains the knowingly traded parity gap rather than a defect"; Story 5.5's criterion recording that a process started outside `pixi run web` does not fire the migrations refusal; Story 7.3's closing criterion about the consequence the story prevents. These carry real design intent that would otherwise be lost, but a developer cannot check them off. *Recommendation:* leave them in place and treat them as constraints on the implementation rather than as acceptance gates — or move them into the epic goal paragraphs if the sprint tooling requires every criterion to be checkable.

### Dependency Analysis

**Epic independence — pass.** The flow is monotonic: 1 → 2 → 3 → 4 → 5, with 6 requiring 1 and 2, 7 requiring 2–6, 8 requiring 7, and 9 requiring 4, 5 and 7. No epic requires a later one. Each was tested individually: Epic 3 works without the refusals; Epic 5 works without the harness; Epic 7's input reconciliation runs against the reference application and does not need the materializer.

**Within-epic dependencies — pass.** All nine epics reviewed story by story. Every story builds only on earlier ones. Four orderings are load-bearing: 2.6 and 2.7 precede 2.8 so the replacement credential paths exist before the old ones are deleted; 4.1 precedes 4.2–4.4 so both stages exist before conditions are added; 5.1 precedes 5.2, 5.3 and 5.5, all of which read `component.toml`; 8.1 and 8.2 precede the rest of Epic 8.

**Forward references — inspected, not violations.** Five acceptance criteria mention a later epic (in Stories 2.2, 3.4, 7.8 and two handoffs). Each was checked: none blocks its story. They record where an obligation completes, and the epics document states this convention explicitly.

**Entity creation timing — pass.** Three schema changes, each in the first story that needs it: `User.idp_subject` in 2.1 (consumed by 2.4), the designated `Group` and `Permission` rows by data migration in 2.3 (consumed by 2.5 and 3.3), and the mapper epoch table in 2.5 (consumed by its own logic). No story creates schema for a later story's benefit, and no epic creates tables in bulk.

### Special Implementation Checks

**Starter template — correctly absent.** The architecture specifies none. This is a brownfield rewire of an existing reference application, so Epic 1 Story 1 is gate consolidation rather than a scaffold step.

**Brownfield indicators — present.** Integration points are named and specified (IdP, deployment repository, enterprise developer portal, approved channel, code-quality platform, CI provider). Migration and compatibility stories exist: 2.1 (schema migration against existing databases), 2.3 (data migration for authorization groups), 2.6 (retiring the existing `Site` data migration), 2.8 (removing the inherited credential surface), 9.6 (base compatibility check). The plan reads as brownfield throughout, which matches the repository.

## Summary and Recommendations

### Overall Readiness Status

**READY** — with eleven findings, none of them blocking.

Implementation can begin on Epic 1 immediately. There are no critical violations, no requirement gaps, no duplicate or missing documents, no forward dependencies, and no circular epic dependencies. The four planning artifacts are mutually consistent: every FR the PRD states is discharged by a story, every architectural decision the spine makes is reflected in the story that implements it, and the spec kernel's capability map reconciles cleanly against both.

This is a stronger position than most projects reach at this gate, and the reason is upstream: the PRD writes testable consequences rather than intent, and the spine names exact files and line numbers. The findings below are refinements and honest scope boundaries, not repairs.

### Critical Issues Requiring Immediate Action

**None.** Nothing must be fixed before implementation starts.

The finding closest to critical is **M-1**, and it is a scope-honesty problem rather than a defect: two of the seven success criteria cannot be closed by any work in this repository. It requires a decision, not a fix, and that decision can be made while Epic 1 is underway.

### Findings by Severity

| # | Finding | Severity | Blocks | Disposition |
|---|---|---|---|---|
| M-1 | SC-6 and SC-3 have no verification path inside phase 1 | Major | Declaring phase 1 complete | **Recorded** in `epics.md` as external exit criteria |
| M-2 | Stories do not cite FR/NFR/AD identifiers inline | Major | Nothing; degrades phase-4 story context | **Fixed** — 68 reference lines added |
| M-3 | Story 8.2 likely exceeds one dev session; 1.3, 2.5, 9.4 carry sizing risk | Major | Nothing; affects sprint sizing | **Fixed** — 8.2 split into three; 1.3 measured |
| W-1 | The server-rendered UI feature's surface is described but never enumerated | Medium | Stories 7.1 and 7.4 | **Fixed** — enumeration criterion added to 7.4 |
| P-1 | FR-13's arithmetic is internally inconsistent, and AD-27 adds an unlisted condition | Medium | Nothing; resolved in `epics.md` | Open — needs a `bmad-prd` run |
| P-3 | FR-45, NFR-6 and FR-31's field list have no owner | Medium | Stories 6.4, 6.6, 8.6 | Open — needs your decision |
| m-1 | Epic 1 delivers platform-group value only; closest to a technical epic | Minor | Nothing; accepted with reasoning | Accepted |
| m-2 | Four stories create a declaration artifact rather than a user capability | Minor | Nothing | Accepted |
| m-3 | Roughly six acceptance criteria are policy statements, not verifiable conditions | Minor | Nothing | Accepted |
| W-2 | No accessibility, responsive or browser-support requirement exists anywhere | Minor | Nothing in phase 1 | Deferred to platform standards |
| P-2 | `prd.md` frontmatter reads `updated: 2026-08-16`, a day in the future | Cosmetic | Nothing | Open — needs a `bmad-prd` run |

### Recommended Next Steps

**Before sprint planning** — both consume the stories directly, so doing them first avoids rework:

1. ~~**Add a requirement reference line to each of the 66 stories** (M-2)~~ — **done**, see Remediation Applied, naming the FRs, NFRs and ADs it discharges. Mechanical, and it makes each story self-contained for `bmad-create-story`, which builds per-story context in phase 4.
2. ~~**Add an enumeration criterion to Story 7.4** (W-1)~~ — **done**, see Remediation Applied requiring the server-rendered UI feature's surface to be inventoried by audit and recorded in the carrier before any file moves. No UX design work — this is a list of what is already in the tree.

**Before committing Epic 1 to a sprint:**

3. ~~**Measure the distance to `strict` mypy** (M-3).~~ — **done**: 22 errors in 12 files, no split needed. Story 1.3 sits on the critical path for every later epic and its size is currently unknown. One command answers it.
4. ~~**Split Story 8.2** into copy-plus-path-pruning, region-pruning, and determinism-and-equivalence assertions.~~ — **done**: now Stories 8.2, 8.3 and 8.4. It is the largest engineering item in the plan and the least likely to fit one session.

**As a decision, not a task:**

5. ~~**Record SC-6 and SC-3 as external exit criteria** (M-1)~~ — **done** in `epics.md`; owners still need naming. with named owners — platform group for an IdP realm to test against, deployment repository for a platform start — and schedule them as an integration milestone after Epics 2 and 5 land. State plainly that phase-1 completion proves five of seven criteria in-repo. The alternative is discovering the gap at the moment someone claims the phase is done, which is the silent narrowing CG-2 forbids elsewhere in this product.
6. **Name owners for the three ownerless requirements** (P-3) — FR-45's collector stub, NFR-6's measurement, FR-31's portal field list. Each already has a story whose acceptance criteria require an owner; assigning them earlier removes a stall from three sprints.

**Housekeeping, whenever the documents are next touched:**

7. **Reconcile FR-13 to the nine-condition, fourteen-state table** now recorded in `epics.md`, and add AD-27's designated-group condition to the PRD's enumeration (P-1). Requires a `bmad-prd` run.
8. **Correct `prd.md`'s frontmatter date** (P-2). Same run.

### Final Note

This assessment identified **eleven issues across three categories** — three PRD defects, two UX warnings, and six epic-quality findings — with **zero critical issues and zero requirement gaps**. All 56 functional requirements and all 8 non-functional requirements trace to at least one story with testable acceptance criteria.

Address items 1 and 2 before sprint planning, decide item 5 while Epic 1 is in flight, and treat the rest as backlog. Or proceed as-is: nothing in this list prevents a developer from starting Story 1.1 today.

---

## Remediation Applied — 2026-08-15

Four of the eleven findings were actioned immediately after the assessment. `epics.md` now holds **9 epics and 68 stories**; the coverage matrix above reflects the renumbering.

### M-2 — Story-level traceability, fixed

A **`**Requirements:**` line** was added to all 68 stories, immediately below the user story and above the acceptance criteria, naming the FRs, NFRs, ADs, SCs, CGs and named risks each story discharges. Format example, from Story 5.3:

> **Requirements:** FR-42 · AD-22 · NFR-2 · SC-3

Every story now carries one; 68 lines for 68 stories, verified programmatically. Stories that support a requirement without discharging it are marked as such (`AD-18 · supports FR-32, NFR-4`) so the map's primary assignment stays unambiguous.

### M-3 — Sizing, fixed and measured

**Story 8.2 split into three**, changing Epic 8 from 9 stories to 11 and total stories from 66 to 68:

| New | Title | Was |
|---|---|---|
| 8.2 | The materializer copies the reference application and prunes by path | 8.2 (part) |
| 8.3 | The materializer prunes feature-owned regions inside core paths | 8.2 (part) |
| 8.4 | Materialization is deterministic and equivalent to the reference application | 8.2 (part) |
| 8.5 – 8.11 | *(unchanged content)* | 8.3 – 8.9 |

Each is independently completable in order, and the middle one now carries AD-24's failure mode explicitly — a missed region leaving an instrumentor call in a combination whose environment no longer contains the package.

**Story 1.3 measured rather than estimated.** Current `[tool.mypy]` (`check_untyped_defs`) reports **no issues in 38 source files**. Under `--strict` the same tree reports **22 errors in 12 files**:

| Error class | Count | Notes |
|---|---|---|
| `type-arg` — missing type arguments on Django generics | 8 | `UserChangeForm`, `DetailView`, `UpdateView`, `QuerySet`, `UserAdmin`, `GenericViewSet`, `SuccessMessageMixin` |
| `no-untyped-def` — missing annotations | 6 | `tasks.py`, `context_processors.py`, `apps.py`, `celery_app.py`, and two in `api/views.py` |
| `misc` — subclassing `Any` from allauth | 4 | `DefaultAccountAdapter`, `DefaultSocialAccountAdapter`, `SignupForm`, `SocialSignupForm` |
| `no-untyped-call` / `no-any-return` | 4 | includes `CeleryInstrumentor` and `adapters.py:48` |

**Conclusion: Story 1.3 does not need splitting.** Twenty-two errors across twelve files is comfortably one session. Two useful details fell out of the measurement: **three of the 22 disappear when Story 1.4 runs first** (`websocket.py:1`, `asgi.py:36`, `asgi.py:40` all belong to the wrapper 1.4 deletes), so sequencing 1.4 ahead of 1.3 is now the recommended order within Epic 1; and the four allauth `misc` errors are third-party-stub problems rather than repository defects, so they will need either a targeted `# type: ignore[misc]` with a comment or a stub package — the only place in Story 1.3 where "fix at the source" may not be available.

Stories 2.5, 9.4 and 4.2 were reviewed again and left intact: each is large but implements a single mechanism, and splitting would fragment it.

### W-1 — UI surface enumeration, fixed

Story 7.4 gained a first acceptance criterion requiring the server-rendered UI feature's surface to be enumerated by audit and recorded in the carrier **before any file moves**, and requiring the enumeration to distinguish user-facing surface from `base.html` and the error templates, which stay. The unestimated work is now visible inside the story that depends on it.

### M-1 — External exit criteria, recorded

`epics.md` gained a section stating that SC-3 and SC-6 cannot be closed by any story, with what each requires, why no epic closes it, its owner and its milestone. The honest completion statement is written into the document: **five of seven success criteria are proven in-repo by the harness; SC-3 and SC-6 are proven against external environments once those exist.**

### Not actioned

- **P-1 and P-2** require a `bmad-prd` run — `prd.md` is that skill's artifact and is not edited here. The nine-condition, fourteen-state table `epics.md` carries is what implementation should follow in the meantime.
- **P-3** needs owners named, which is a decision rather than an edit. Stories 6.4, 6.6 and 8.6 each carry "name an owner" as an acceptance criterion, so the requirement is not lost.

### Post-remediation statistics

- Epics: **9** · Stories: **68** · Requirement reference lines: **68** · Unreplaced placeholders: **0**
- FR coverage: **56/56** · NFR coverage: **8/8**
- Findings fixed: **4** · Accepted: **3** · Deferred: **1** · Open pending a `bmad-prd` run or your decision: **3**

---

**Assessed:** 2026-08-15
**Assessor:** Implementation Readiness workflow (`bmad-check-implementation-readiness`)
**Documents assessed:** `prd.md` (final), `ARCHITECTURE-SPINE.md` (final), `epics.md` (9 epics, 68 stories), `SPEC.md` and `capability-map.md` (spec kernel)
**UX design contract:** none — assessed as not applicable, see Step 4
