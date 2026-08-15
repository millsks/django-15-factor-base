---
title: "Input Reconciliation: brief → PRD"
source: "_bmad-output/planning-artifacts/briefs/brief-django-15-factor-base-2026-08-08/brief.md"
targets:
  - "prd.md"
  - "addendum.md"
created: 2026-08-14
---

# Input Reconciliation — brief.md against the PRD and its addendum

## Overall assessment

The PRD preserves the brief's substance with unusual fidelity: every immovable-core item, all four selectable features, the twelve-combination arithmetic and its broker rationale, all four local substitutions, all four success criteria, and every entry in the brief's risk register have a named home in the PRD, and several are stated more sharply than the brief stated them (the refusal contract at eight, the allowlist test, the no-network-at-boot property, the materializer). What the FR structure lost is almost entirely **qualitative**, and it clusters in exactly the two places the brief was most deliberately self-critical: the "What Makes This Different" section, which opens by announcing that it is unflattering and then names the product's origin as a restructured `cookiecutter-django` with "no moat in the code," and the Vision's closing paragraph, which concedes that a generated repository "is a fork by any honest definition — which is the thing this product exists to stop, reappearing one level up." Neither concession survives in any form; the PRD's Vision keeps the confident half of both arguments ("the product is the set of decisions already made and proven") and drops the humility that made the brief credible to a downstream architect. Beyond tone, one genuinely load-bearing mechanism was dropped: the brief twice names the pinned coverage core as the thing that makes template coverage measure anything at all, and neither the PRD nor its addendum mentions it — which leaves the orphan detector (SC-2, FR-28, CG-1) resting on a mechanism no requirement protects. The remaining gaps are small named specifics: the five zero-reference packages from the audit, the S3-compatible object-storage backend, and OpenShift as the named target platform.

---

## 1. The "unflattering" framing of What Makes This Different is entirely absent

**Brief says** (§What Makes This Different):

> "This section is deliberately unflattering, because inflated claims here would mislead the architecture work downstream. The project began as `cookiecutter-django` and was restructured; all of it is technically reproducible, and there is no moat in the code."

**PRD:** nothing. `cookiecutter`, `moat`, and `reproducible` (in this sense) appear nowhere in `prd.md` or `addendum.md`. §1 Vision carries the *positive* half of the same argument — "The product is not the Django code. Anyone could write that. The product is **the set of decisions already made and proven**" — which is the brief's Executive Summary line, not this one. The brief's Executive Summary and its differentiators section were making two different moves; only the flattering one survived.

**Severity: critical.** This is the single largest qualitative loss, and it has a concrete downstream cost the brief itself names: an architect who does not know the repository is a restructured `cookiecutter-django` will not know that its inherited defaults — the four bypassing credential paths of §4.2, the "three of the four [substitutions] already held before this was written, inherited and undocumented" of §4.4 — came from somewhere rather than being chosen. The PRD asserts those facts without their provenance. The brief also warns explicitly that inflated claims here "would mislead the architecture work downstream," and the PRD is precisely that downstream artifact.

**Fix:** add a short subsection to §1 Vision (or a new §1.1, "What this is and is not"), stating in the brief's own register: the repository began as `cookiecutter-django` and was restructured; nothing in it is technically irreproducible and there is no moat in the code; the value is the decision set, the audit trail, and the gate that proves both. Then keep the existing "the product is not the Django code" paragraph as the positive statement it already is. Two or three sentences is enough — the point is that the concession is on the record before an architect reads FR-1.

---

## 2. The Vision's concession that a generated component is itself a fork

**Brief says** (§Vision):

> "That last step is genuinely not solved. Generation produces an independent repository, and a repository someone else now owns and edits is a fork by any honest definition — which is the thing this product exists to stop, reappearing one level up. ... Turning that answer into pull requests is a second product, and naming it here is not the same as having built it."

**PRD:** the *fact* survives in three places — §2.2 Non-Users ("Propagating an accelerator change into existing components is named in §5 as a non-goal"), §5 Non-Goals ("a second product with its own lifecycle"), and §6.2 with a `[NOTE FOR PM]` calling it "emotionally load-bearing." The *argument* does not. Nowhere does the PRD say that a generated component is a fork, or that the product's central problem reappears one level up. §5's framing — "the shape `cruft` and `copier update` take for their own template systems" — is a tooling comparison that reads as a scoping decision, not as an admission.

**Severity: high.** The brief's problem statement opens with "Starting a new Django component today means forking an existing service and inheriting whatever was true the day it was forked," and the PRD's §2.1 JTBD repeats it verbatim. Without the Vision concession, the PRD asserts the problem and never acknowledges that its own solution reinstates it after generation. That is a coherence defect in the document, not only a tone loss.

**Fix:** in §5, extend the propagation non-goal with the brief's sentence: a generated component is an independent repository that someone else owns and edits — a fork by any honest definition, which is the thing this product exists to stop, reappearing one level up. The provenance stamp (FR-35) is the precondition for any answer, and naming the capability is not the same as having built it. The existing `[NOTE FOR PM]` in §6.2 can then reference it rather than gesturing at it.

---

## 3. The pinned coverage core — the mechanism the orphan detector actually depends on — is missing

**Brief says** (§The Problem):

> "Each new component must rediscover — or ship without — whether the OpenTelemetry ASGI instrumentor is optional (it is not; without it, ASGI requests produce no spans at all), **whether template coverage measures anything (not unless the tracer core is forced)**, and which packages exist on the approved channel."

and (§What Makes This Different):

> "The dependency manifest carries the reasoning for its own non-obvious lines — why one package comes from PyPI when every other comes from conda-forge, **why a coverage core is pinned**."

**PRD:** the ASGI instrumentor trap survives intact (FR-46: "without it, ASGI requests produce no spans at all"). The channel question survives as FR-49. The coverage-core trap survives **nowhere** — `coverage core`, `COVERAGE_CORE`, `ctrace`, and `sysmon` appear in neither `prd.md` nor `addendum.md`, nor in the brief's own addendum. FR-28 requires only "Coverage measurement includes templates in every combination's gate run," and CG-1 forbids narrowing what is measured, but neither names the thing that makes template measurement work. The repository itself carries the reasoning at `pixi.toml:137-141`: `django_coverage_plugin` is a dynamic file tracer needing `sys.settrace`, Python 3.12+ defaults coverage to the `sysmon` core, and the result is a silent 0%.

**Severity: high.** The brief's fourth differentiator, SC-2, FR-28, and CG-1 all rest on the zero-percent orphan signal, and that signal exists only because an environment variable is pinned in `pixi.toml`. FR-36 keeps `pixi.toml` in materialized output, so the mechanism travels by accident rather than by requirement — and nothing detects its loss. A regression here does not fail loudly in a way that identifies itself; it produces exactly the reading an orphaned template produces, which means the detector and its own failure are indistinguishable.

**Fix:** add a consequence to FR-28 naming the mechanism and requiring it be verified rather than inherited: the coverage core is pinned to the tracing implementation `django_coverage_plugin` requires, the pin travels with every materialized combination, and a gate step asserts that template files appear in the coverage report with non-zero measurement in a combination known to render templates. That last clause is what distinguishes "the detector found nothing" from "the detector is not running." Also add the pin to FR-48's list of manifest lines that carry their own reasoning — the brief names it there explicitly, alongside the supply-chain exception that has since been resolved.

---

## 4. "Compliance is a side effect of convenience" — the adoption thesis is dropped

**Brief says** (§Vision):

> "The accelerator becomes the only way a Django component starts inside the platform, and the fastest — so compliance is a side effect of convenience rather than a review gate."

**PRD:** absent. `compliance`, `fastest`, and `review gate` appear nowhere. One shard of the argument survives, in §4.4's description: "Requiring a developer to run all of it to change a line of business logic would make the accelerator slower than the fork it replaces" — which is the same reasoning applied to one feature group, stripped of the principle it derives from. §1 Vision describes the mechanics of ordering a component but never states why a lead developer would choose the accelerator over forking.

**Severity: medium-high.** This is not an adoption *metric* — the PRD's decision to state criteria rather than outcome metrics is settled and correct — it is a **design constraint**. "Fastest, therefore chosen" is the reason the local development contract exists at all, the reason presets constrain nothing (FR-26), and the reason the refusal contract is a startup failure rather than a review checklist. An architect optimizing the refusal contract without it will reasonably conclude that a stricter, slower path is always better.

**Fix:** restore the sentence to §1 Vision as a stated design constraint, and add a line to §9 Constraints and Guardrails under a new "Adoption posture" heading: the accelerator must remain the fastest way to start a Django component, because that is the only enforcement mechanism this product has — nothing here is a review gate, and a requirement that makes generation slower than forking defeats the product regardless of what it guarantees. This also gives CG-4 (don't add substitutions) and §4.4 an explicit parent principle rather than leaving them as isolated judgments.

---

## 5. "The gate detects, it does not decorate" — the phrase and its framing are gone

**Brief says** (§What Makes This Different):

> "**The gate detects, it does not decorate.** Removing a feature during this audit orphaned two template overrides that no import graph, linter, or dependency analyzer would flag. Only the coverage gate caught them, by reporting 0%. That property is what will keep feature extraction honest as the model grows."

**PRD:** the *evidence* survives twice — §4.5's description ("Removing MFA during the audit orphaned two template overrides that no import graph, linter, or dependency analyzer would flag. Only the coverage gate caught them, by reporting zero percent") and the Glossary's definition of **Orphan**. The *claim* the evidence supports does not. "The gate detects, it does not decorate" is the brief's sharpest statement of what distinguishes this gate from the coverage badge on any other repository, and it is the standing rebuttal to every future proposal to loosen the threshold. CG-1 forbids one specific instance of decoration; the principle that would forbid the next one is not stated.

**Severity: medium.**

**Fix:** promote the phrase to §4.5's description as the leading sentence of the paragraph that currently begins "The hardest part is what is left behind," and echo it in CG-1's rationale. The evidence is already in both places; it currently arrives without the conclusion it was collected to support.

---

## 6. The audit's five zero-reference packages are dropped

**Brief says** (§The Problem):

> "**Dead scaffolding accumulates invisibly.** An audit of this repository found **five packages with zero references in the source tree** and two template overrides no reachable page could render. Every fork inherits that debt and adds to it."

**PRD:** the two template overrides survive (§4.5, Glossary). The five packages do not — `five packages` and `zero references` appear nowhere. FR-27's first consequence covers the forward-looking requirement ("the dependency manifest contains no package from an unselected feature's package surface") but the finding that motivated it is gone, and with it the fact that dead *dependencies* — not only dead templates — are a demonstrated failure mode in this specific repository.

**Severity: medium.** The asymmetry matters: the template orphans are cited twice as proof that coverage is the only detector, while the package orphans — which coverage does *not* detect, and which no requirement currently claims to detect either — are unmentioned. FR-27 asserts the property; nothing in the PRD says how a package with zero references would be found in a materialized combination.

**Fix:** add the finding to §4.5's description alongside the template-override evidence, and add a consequence to FR-27 or FR-28 requiring detection of declared-but-unreferenced dependencies in materialized output — or, if that detection is deliberately not in scope, say so explicitly under FR-27's Out of Scope with the reasoning. Either resolution is fine; silently carrying a forward-looking requirement whose motivating evidence and detection mechanism are both absent is not.

---

## 7. The comparison to the parent project — "where the project this was forked from expects a developer to bring an environment up first"

**Brief says** (§What Makes This Different):

> "**The component runs before anything else does.** No compose file, no services, no IdP realm — where the project this was forked from expects a developer to bring an environment up first. What a developer exercises locally is not a mock of the deployed behaviour; it is the deployed behaviour, minus the network hops."

**PRD:** the second sentence survives nearly verbatim in §2.1 ("Trust that what runs locally is the deployed behaviour minus the network hops, and know precisely where that stops being true" — in fact improved by the added clause). The first does not: "no compose file" appears nowhere, and the comparison to the parent project is absent along with the parent project itself (see gap 1). §5's non-goal rejecting a local identity-provider container carries part of the reasoning — "it reintroduces exactly the per-machine service dependency the substitutions exist to remove" — without the observation that this is a deliberate departure from what the source project did.

**Severity: medium.** Chiefly a consequence of gap 1; fixing that one makes this one cheap.

**Fix:** when adding the origin paragraph under gap 1, include the departure: `cookiecutter-django` expects a developer to bring a compose environment up before the application runs, and the local development contract of §4.4 is a deliberate inversion of that. This also strengthens §5's rejection of the local IdP container by giving it a precedent rather than only a principle.

---

## 8. Object storage is no longer described as S3-compatible

**Brief says** (§The Feature Model, feature table):

> "Object storage | Document and blob storage against an **S3-compatible** backend"

**PRD:** `S3` appears nowhere. The Glossary defines **Feature** as including "object storage" with no elaboration; §4.5 never states what backend it targets; FR-49's consequence refers obliquely to "the storage and cloud-SDK packages" without naming `django-storages` and `boto3`, which the brief does name in its risk register.

**Severity: medium.** FR-24 requires each feature to declare "both its package surface and its non-package surface," and this is the one feature whose surface has an external protocol contract. An architect reading only the PRD does not know whether object storage means S3, an OpenShift-native store, or a Django storage abstraction over either — and that determines whether the deployment interface of §4.7 needs an object-storage attachment contract at all.

**Fix:** state the backend in §4.5's description or in the Glossary's **Feature** entry: object storage means document and blob storage against an S3-compatible backend, delivered by `django-storages` and `boto3`. Add the endpoint/credential environment variables to §4.7's contract, since factor 4 in §12 already claims "PostgreSQL, cache, and object storage attach by environment variable" — a claim currently made in the Factor Coverage table with no FR behind it.

---

## 9. The target platform is never named

**Brief says** (§Executive Summary):

> "A CI pipeline containerizes that component and deploys it to a platform such as **OpenShift**."

**PRD:** `OpenShift` appears nowhere; §1 says "a deployment repository puts it on the platform," and the Glossary defines **Deployment repository** without naming what it deploys to.

**Severity: low.** Mostly harmless, with one exception: FR-38 requires startup under "a UID assigned by the platform" and Open Question 3 and Assumption 3 both refer to "the platform's **security context constraints**" — SCC is OpenShift's term for a concept most readers know by another name. The requirement is legible only to someone who already knows the target.

**Fix:** name the platform once, in §10 Integration and Dependencies under a "Target platform" entry, phrased as the brief phrases it ("a platform such as OpenShift") so the PRD does not over-commit. FR-38 and Assumption 3 then read as specific rather than vague.

---

## 10. The parity trade loses its bound

**Brief says** (§Risks, dev/prod parity):

> "The trade buys a component that runs the moment it is generated, and it is bounded — the gate runs against PostgreSQL, the authentication and authorization code paths are shared rather than mocked, and observability is not substituted at all. **Parity is given up at the edges the gate can re-establish, and nowhere else.**"

**PRD** (§11, Dev/prod parity): reproduces the passage almost word for word — including "the gate runs against PostgreSQL, the authorization code paths are shared rather than mocked, and observability is not substituted at all" — and stops before the final sentence.

**Severity: low.** The closing sentence is the rule the three examples are instances of, and it is the criterion CG-4 needs: a proposed fifth substitution is acceptable only if the gate can re-establish parity at that edge. CG-4 currently forbids a fifth substitution categorically, which is a stronger and less reasoned position than the brief's.

**Fix:** restore the sentence to §11 and cite it from CG-4 as the test a hypothetical fifth substitution would have to pass. Note this makes CG-4 slightly *weaker* than currently written, which appears to be the brief's intent — the brief bounds the trade, it does not close it.

---

## 11. The brief's "no decisions remain open" is contradicted without acknowledgement

**Brief says** (§What Is Not Yet Decided):

> "**No decisions remain open.** ... Everything else this brief raised is settled. What remains is not decisions but work."

**PRD:** §13 opens three questions (revocation latency, materializer-to-template relationship, writable path count) and §14 indexes five live assumptions. Every one is well-owned and correctly scoped, and §13's framing — "None blocks architecture from starting; each blocks a specific decision inside it" — is more useful than the brief's flat claim. But the PRD never notes that it is reopening ground the brief declared settled, and Open Question 2 in particular is genuinely new: the materializer did not exist when the brief was written, so the brief could not have closed it. The PRD's own addendum §1 explains the materializer's origin well; §13 does not connect to it.

**Severity: low.** The PRD is right and the brief is stale. The risk is only that a reader holding both documents cannot tell whether the PRD disagreed with the brief or superseded it.

**Fix:** add one sentence to §13's preamble: these three arose during PRD discovery and postdate the brief's "no decisions remain open," two of them because the materializer did not exist when the brief was written. Then reconcile the brief's §What Is Not Yet Decided when it is next touched — the same pass that should update the refusal contract from six conditions to eight (PRD §4.3 already flags this) and should record that the supply-chain exception cleared on 2026-08-14, which the brief still describes as pending.

---

## Verified as carried through — no action needed

Recorded so a later reader does not re-check them:

- All ten immovable-core items, and the "three factors beyond the twelve" rationale for immovability (brief §Feature Model → FR-1, FR-2).
- Capability-not-package-list, including the instrumentor flex (brief → FR-2, Glossary).
- Twelve valid combinations, the broker constraint, and its deployment-only scope (brief → FR-22, FR-25, FR-33, Glossary).
- Presets as non-constraining starting points (brief → FR-26).
- All four substitutions with their preserved properties, and observability as the unsubstituted exception (brief §Local Development Contract → FR-18 through FR-21, §4.8).
- Refusal-not-default, and local credentials refused at boot in a deployed component (brief → Glossary **Refusal**, §4.3).
- The local identity path is not a shim; same mapper, same Bearer class, only the signer is local (brief → §4.4 description, FR-19, FR-20).
- All four success criteria, restated as SC-1 through SC-4 with the PostgreSQL qualifier intact.
- All eight risk-register entries, each with a §11 counterpart; seven with mitigations the brief did not have.
- The ASGI instrumentor trap (brief §The Problem → FR-46).
- Rationale-inside-configuration (brief → §4.9, FR-48).
- Every out-of-scope item, including MFA at the IdP and avatars as remote IdP URLs (brief §Scope → §5).
- The provenance stamp as enumerability-only, with acting on it out of scope (brief §Vision, §What Is Not Yet Decided → FR-35, §5).
- Phase-1/phase-2 boundary, the one-way transition, and the "gate cannot run against FreeMarker-interleaved source" argument (brief §The Solution → §1, §4.6, Glossary).
