---
title: "Addendum: django-15-factor-base PRD"
status: final
created: 2026-08-14
updated: 2026-08-14
---

# Addendum

Depth generated during PRD discovery that belongs to architecture rather than to the PRD. It is deliberately thin: the brief's own addendum at `_bmad-output/planning-artifacts/briefs/brief-django-15-factor-base-2026-08-08/addendum.md` already carries the mechanism, findings, and rejected alternatives for authentication, the feature-to-surface matrix, the dependency audit, the deployment interface, and the local development interface. Nothing there is repeated here. Sections follow the order of the PRD sections they attach to.

## 1. The refusal evaluation model — why two stages (PRD §4.3)

The first draft placed the whole refusal contract at settings import, on the reasoning that a guard inside the deployed settings module cannot fire when that module is the thing being bypassed. That reasoning is right and the placement was wrong, because some conditions cannot be evaluated there at all.

What forced the split: resolving the URL configuration requires the application registry, which is not populated at settings-import time — Django raises `AppRegistryNotReady`. The token-minting route condition, the local sign-in route condition, and the FR-17 allowlist all need the resolved URL configuration. So a single evaluation point at settings import cannot express three of the nine conditions.

Rejected alternatives:

- **Django's system-check framework.** The natural home for exactly this kind of validation, and it does not run under `gunicorn config.asgi:application`. A refusal that fires under `manage.py` and not under the server is a refusal that never fires where it matters.
- **A single point late enough to resolve the URL configuration.** Reachable only after the settings module has already been chosen and loaded, which reopens the hole FR-12 exists to close.
- **An assertion inside the deployed settings module** that the loaded module is the deployed one — the mechanism the source material implied. It inherits the hole it is meant to detect.

The migration condition is scoped, not relocated. Evaluated for every process, the unapplied-migration refusal forbids `manage.py migrate` — the single action that clears it — and deadlocks the release stage. Scoping it to serving processes is not a workaround: the refusal exists so that a process serving traffic never runs against a schema it does not recognize, and a migration process is not serving traffic. The narrower rule is the more accurate one.

The local declaration must be present on a fresh clone, or UJ-2's "clone, one command, it serves" fails; and it must not reach an image, or it disables every unconditional refusal in every deployed component. A committed dotfile satisfies the first and fails the second unless the image build is exactly right, which makes a security property depend on a build detail. Carrying it in the local development task's environment satisfies both structurally: it is committed, and a container never invokes that task. The residual risk is an image built to invoke the development task as its entrypoint, which the declared process model of FR-40 already forbids.

## 2. Object storage as the fifth substitution (PRD §4.4)

The brief and its addendum both fix the substitution set at four. That was consistent until object storage became a selectable feature, at which point the six combinations selecting it had no local behaviour defined at all — they could not satisfy the criterion that every valid combination runs with nothing installed, and no requirement said what they should do instead.

Three options were available: declare object storage unavailable locally and accept that SC-4 covers only six of twelve combinations; require a local S3-compatible container, which reintroduces the per-machine service dependency the whole contract exists to remove; or substitute a filesystem-backed storage backend.

The third is the same shape as the other four — it preserves the storage API at every call site and differs only in where bytes land — so it was taken, and the counter-criterion that forbade a fifth substitution was rewritten to state a principle instead of defending a number. The principle it now states would have permitted this substitution and still forbids the ones it was written to prevent.

What this substitution does not exercise, listed in FR-18, is wider than the gaps in the other four. Of the five this is the leakiest, and the gate is the only thing that covers the difference.

## 3. The materializer — why phase 1 gained a mechanism the brief did not name (PRD §4.6)

The brief scopes phase 1 as "the reference application" and defines the verification harness in §4.2.3 as *the template's CI renders all 12 combinations and runs each generated repository's own gate*. Those two statements are in tension: the harness as defined requires the FreeMarker template, which phase 1 does not have. Left unresolved, phase 1 delivers a reference application whose twelve-combination claim is first exercised by the template work — the failure the brief's risk register names.

Three resolutions were considered.

| Option | What phase 1 delivers | Why not selected |
|---|---|---|
| Build a materializer *(selected)* | A mechanism in this repository that produces the source of any valid combination from the reference application, feeding the same two verification levels the template will later feed | — |
| Specify the harness, build it later | The reference application plus a PostgreSQL-backed gate; the harness contract written as requirements only | Leaves criterion 1 unproven through the entire riskiest transition. The brief's own risk register forbids this ordering explicitly |
| Component gate only | Reference application plus its own hardened gate; combination verification moved to a separate PRD | Same defect, and it additionally makes the twelve-combination claim nobody's deliverable |

The architectural question the selection opens is how much of the materializer survives into phase 2. Three artifacts are candidates for single-authoring: the strip/parameterize/keep disposition (brief addendum §4.2.2), the fixture set that supplies order values, and the feature-to-surface declarations. If those are authored once and consumed by both the materializer and the FreeMarker template, phase-1 work carries forward almost entirely. If they are authored twice, the materializer is throwaway scaffolding and its cost should be weighed accordingly.

PRD FR-30 requires single-authoring. Left open, the materializer's cost is unbounded and an architect choosing between implementations has no basis for the choice. Requiring shared declarations is a product-level constraint — it says what the phase-2 transition must not cost — rather than an implementation decision, which is why it belongs in the PRD.

A second-order property worth preserving: the materializer and the template answer the same question by different means, so for a given combination the two should produce equivalent source. That is a stronger transition test than either mechanism alone, and it exists only if the materializer is kept alive through the changeover rather than deleted at its start.

## 4. Supply-chain exception — resolution and the verification method (PRD §4.9)

Resolved during this PRD run, 2026-08-14. conda-forge `django-celery-beat` build `2.9.0 pyhcf101f3_1` (uploaded 2026-08-15 UTC) declares `importlib-metadata` with no version cap, replacing `pyhcf101f3_0`'s unconditional `importlib-metadata <5.0`. That cap was the sole reason the dependency resolved from the package index, and it was irreconcilable with `opentelemetry-api`'s `>=6.0` requirement.

The verification method generalizes. Channel *availability* is not the question when the blocker is a version constraint — a package can be present and still unusable. The check is to read the specific build's `depends` list from `api.anaconda.org/package/conda-forge/<name>` and compare builds, since the fix arrives as a build-number bump at an unchanged version. Here `2.9.0` appears twice with different constraint sets, and only the newer build resolves the conflict. Any future channel-availability check under PRD FR-50 should take this shape rather than stopping at "the package exists."

The consequence for the repository is not yet applied. `pixi.toml` still declares the dependency under `[pypi-dependencies]` (line 90) with a rationale comment (lines 86-89) that is now historical, and a related comment at lines 21-23 explaining why its transitive dependencies are declared separately. Moving the dependency and updating both comment blocks is repository work, deliberately not performed during this PRD run.

## 5. Why the PRD states criteria rather than outcome metrics (PRD §7)

Considered and set aside: time from generation to first business-logic commit, share of new Django components started through the accelerator, and rate of components that diverge from the base within a fixed window.

Each is a genuine measure of whether the product is working, and none is measurable from this repository. They depend on enterprise developer portal telemetry and on repository-activity data across the estate — both outside the team's control and outside this PRD's scope.

They are not wrong, only misplaced. If the platform group wants adoption instrumented, that is a developer-portal requirement, and the provenance stamp (PRD FR-36) is the join key that would make estate-wide analysis possible at all.

## 6. Counter-criteria — the reasoning behind each (PRD §7)

The PRD names four things that must not be optimized. The reasoning is worth keeping because each describes a specific, plausible way a green build could mean less than it appears to.

- **Coverage by narrowing measurement.** The ninety-percent threshold and the template inclusion are not independent quality knobs — template coverage *is* the orphan detector. A change that excludes templates to make coverage easier removes the only signal that catches incomplete feature removal, while making the number go up.
- **Verification set shrinkage.** Twelve materialize-and-gate runs per template change is expensive, and the pressure to sample will be real and recurring. FR-35's reporting rule exists because a silently reduced set reads exactly like a full one.
- **Refusal softening.** A refusal that logs and continues is strictly easier to deploy against. It is also the single mechanism separating a local component from a deployed one.
- **Substitution creep.** The reasoning is in §2: the constraint is the principle, not the count.
