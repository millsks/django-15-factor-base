# Capability Map

The crosswalk from this spec's stable capability IDs to the requirement, criterion, and architectural-decision identifiers in the adopted companions. Neither the PRD nor the architecture spine keys anything on `CAP-N`; this file is the only place that binding exists, and downstream work traces through it.

Column sources: `FR` / `NFR` / `SC` / `CG` from `prd.md`; `AD` and *Lives in* from `ARCHITECTURE-SPINE.md`.

| Capability | PRD § | FR | NFR | Criteria | AD | Lives in |
|---|---|---|---|---|---|---|
| CAP-1 Immovable core | 4.1 | FR-1..FR-3 | — | SC-7 | AD-2, AD-3, AD-5, AD-29, AD-30 | `src/config/`, `src/django_service/` |
| CAP-2 IdP-only auth + mapper | 4.2 | FR-4..FR-11 | — | SC-6 | AD-10, AD-11, AD-12, AD-23, AD-27, AD-31 | `src/config/authorization/`, DRF auth class, allauth adapter |
| CAP-3 Refusal contract | 4.3 | FR-12..FR-17 | NFR-1 | SC-5, CG-3 | AD-9, AD-13, AD-16, AD-21, AD-26, AD-27 | `src/config/startup/` |
| CAP-4 Local development | 4.4 | FR-18..FR-23 | — | SC-4, CG-4 | AD-9, AD-13, AD-21, AD-27, AD-30 | `pixi.toml` task `env`, settings `local` |
| CAP-5 Feature model | 4.5 | FR-24..FR-29 | NFR-5 | SC-2, CG-1 | AD-1, AD-2, AD-24, AD-25, AD-29 | `accelerator.toml` |
| CAP-6 Materializer + verification | 4.6 | FR-30..FR-37 | NFR-4, NFR-5, NFR-8 | SC-1, CG-1, CG-2 | AD-3, AD-17, AD-18, AD-19, AD-20, AD-30 | `tools/materializer/`, CI |
| CAP-7 Deployment interface | 4.7 | FR-38..FR-45 | NFR-2, NFR-3 | SC-3 | AD-14, AD-15, AD-17, AD-22, AD-28, AD-32 | `pixi.toml` tasks, `component.toml` |
| CAP-8 Observability | 4.8 | FR-46..FR-48 | NFR-6 | SC-7 | *(conventions only)* | `src/config/observability/` |
| CAP-9 Supply chain | 4.9 | FR-49..FR-50 | NFR-7 | — | *(conventions only)* | `pixi.toml` |
| CAP-10 Extension model | 4.10 | FR-51..FR-56 | — | — | AD-4, AD-5, AD-6, AD-7, AD-8, AD-9, AD-28, AD-29 | `src/django_apps/` |

## Coverage gaps in the map

- **CAP-8 and CAP-9 have no governing AD.** The spine covers both through its Consistency Conventions table and residual risk R-1 rather than through a numbered invariant. Two spine open items sit here with no owner: the FR-45 OTLP export end-to-end test and the NFR-6 telemetry-overhead measurement.
- **CAP-9 and CAP-10 have no success criterion in the PRD's SC set.** SC-1 through SC-7 do not validate FR-49..FR-56. The success statements for those two capabilities in `SPEC.md` are derived from their FRs' own testable consequences, not from an SC.
- **AD-32 (the GitHub-template consumer) is a governed exception, not a capability.** It is mapped to CAP-7 because it varies the deployment interface, but it is deliberately outside every guarantee this contract makes.

## Residual risks, by capability

| Risk | Capability | Status |
|---|---|---|
| R-1 `django-storages` fitness unproven against Django 6.0 / Python 3.14 | CAP-5, CAP-9 | Carried; escalation ordered (spike → feedstock push with time-boxed exception → component-owned backend) |
| R-2 Bearer revocation latency is the token's lifetime | CAP-2 | Accepted; narrows FR-9 and SC-6 |
| R-3 A serving process started outside `pixi run web` does not fire the migrations refusal | CAP-3, CAP-7 | Accepted; the price of fail-open process type |
| R-4 The GitHub-template path ships from `main` HEAD with machinery attached | CAP-7 | Accepted under AD-32 |
| R-5 Local development proves less than running suggests | CAP-4 | Accepted; the gate is the counterweight |

## Staleness in the adopted companions

### Resolved 2026-08-15 (`bmad-architecture` update run)

Both items below were surfaced by this spec run and corrected in `ARCHITECTURE-SPINE.md` by its owning skill. No AD, invariant, convention, stack entry, residual risk, open item, or deferred entry was touched; `lint_spine.py` returned zero findings after the edit.

1. **The spine's "Divergences From the PRD" section (D-1..D-5) was stale** and is now recorded as reconciled. The PRD was amended by commit `b8a3fd9` ("docs: reconcile the PRD with the phase-1 architecture spine") on 2026-08-15, six minutes after the spine's own commit `35282c8`. Each divergence was checked against current PRD text and the PRD already agreed:

   | Divergence | Current PRD text |
   |---|---|
   | D-1 `src/django_service/` parameterized | FR-37 states it is a **constant**, "not parameterized, and this is load-bearing" |
   | D-2 declarations cross-checkable with the template | FR-30 states the copy is one-way and "what this does not buy is an ongoing cross-check" |
   | D-3 FR-9 "on every authentication" | FR-9 states resolve and re-sync run at different frequencies, re-sync once per credential epoch. Consequence R-2 still stands |
   | D-4 interactive flow "costs no new dependency" | §4.2 says no new *framework*, and names `requests` as the package cost |
   | D-5 PRD unaware of reusable apps / tenant space / template consumer | §4.10 (FR-51..FR-56), the template-repository non-goal in §5, and the code-host entry in §10 all exist |

2. **The spine's `binds:` range read `FR-1..FR-50`** while the PRD runs to FR-56. Corrected to `FR-1..FR-56`; the spine already governed FR-51..FR-56 in substance via AD-4 through AD-9, AD-28 and AD-29, so only the declared range was wrong. Its map row "Reusable apps (new; not in the PRD)" is now "Reusable apps / extension model (§4.10)".

### Open

- **`prd.md` frontmatter carries `updated: 2026-08-16`** — a day later than its own commit (`b8a3fd9`, 2026-08-15) and a day in the future relative to the date of this spec run. The PRD is `bmad-prd`'s artifact; neither `bmad-spec` nor `bmad-architecture` edits it. Needs a `bmad-prd` run.
