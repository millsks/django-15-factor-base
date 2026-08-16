---
baseline_revision: f624273
final_revision: 9f1d427
review_loop_iteration: 0
followup_review_recommended: true
status: done
warnings: []
---

# Story 2.2: The claims contract is read from the environment

Status: done

## Story

As a platform engineer,
I want the identity-key claim, the group claim, and the staff and superuser groups read from configuration,
so that a component can be pointed at any IdP's claim taxonomy without a code change.

## Acceptance Criteria

**Traceability:** FR-10 · AD-12

1. **Given** the claims contract
   **When** it is configured
   **Then** the identity-key claim name, the group-claim name, the staff-conferring group and the superuser-conferring group are each read from the environment

2. **Given** differing IdP taxonomies
   **When** the group-claim name is set
   **Then** `groups`, `roles` and `realm_access.roles` are each expressible without a code change

3. **Given** no claims contract is configured
   **When** a deployed component starts
   **Then** it will refuse to start once Epic 4 lands
   **And** no conventional claim name is defaulted in its place

## Tasks / Subtasks

- [x] Task 1 — Create the authorization package (AC: #1)
  - [x] Create `src/config/authorization/__init__.py` with a module docstring naming AD-10/AD-11/AD-12 as its charter. The directory does not exist today; this story creates it.
  - [x] Do not add anything else to `__init__.py`. It is a package marker, not a re-export surface; later stories add `claims.py`, `mapper.py`, `jwks.py`, `authentication.py`, `adapters.py` beside it.

- [x] Task 2 — Declare the contract as a frozen dataclass in `src/config/authorization/claims.py` (AC: #1, #2, #3)
  - [x] `@dataclass(frozen=True, slots=True) class ClaimsContract` with four `str` fields: `identity_key_claim`, `group_claim`, `staff_group`, `superuser_group`. Google-style docstring on the class stating that each is a *name*, never a value.
  - [x] Add `is_configured: bool` as a property returning `all(...)` over the four fields being non-empty. **Do not raise here.** AC #3 says the refusal is Epic 4's; a raise at import would fire during `pixi run test` and during every management command before Epic 4 has a locality signal to gate it with.
  - [x] Add `def load_claims_contract(env: environ.Env) -> ClaimsContract` reading exactly four variables with `default=""`:
    `COMPONENT_IDENTITY_CLAIM`, `COMPONENT_GROUP_CLAIM`, `COMPONENT_STAFF_GROUP`, `COMPONENT_SUPERUSER_GROUP`.
    **No fallback value of any kind** — not `"sub"`, not `"groups"`, not `"roles"`. The empty string means unconfigured and is what Epic 4 refuses on.
  - [x] Add `def read_group_claim(claims: Mapping[str, Any], path: str) -> list[str] | None` resolving a **dotted path** through nested mappings, returning `None` when any segment is missing and a `list[str]` otherwise. This is what makes `realm_access.roles` expressible (AC #2). Return `None` — not `[]` — for absent, because AD-12 makes the absent case a 401 and the empty case must never be silently equivalent to it.
  - [x] Add `def read_identity_key(claims: Mapping[str, Any], path: str) -> str | None` using the same dotted-path walk, so a nested identity claim needs no second mechanism.

- [x] Task 3 — Wire the contract into settings (AC: #1)
  - [x] In `src/config/settings/base.py`, in the `# AUTHENTICATION` block (currently lines 130–142), add `from config.authorization.claims import load_claims_contract` at the top import group and `CLAIMS_CONTRACT = load_claims_contract(env)`.
  - [x] Place the import beside the existing `from config.observability.logging import ...` imports (base.py:11-12) — importing a `config` sibling from settings is already the established pattern in this file.
  - [x] Add the four variable names, with no values, to `.envs`/`.env.example` if such a file exists in the repository; if none exists, document them in `docs/` instead (Story 2.3 creates `docs/authentication.md` — if that file already exists when you get here, add them there rather than creating a second home).
  - [x] Set explicit test values in `src/config/settings/test.py` so the suite runs against a *configured* contract independent of the developer's shell: `CLAIMS_CONTRACT = ClaimsContract(identity_key_claim="sub", group_claim="groups", staff_group="platform-staff", superuser_group="platform-superuser")`. State in a comment that these are test fixtures, not defaults.

- [x] Task 4 — Keep the existing settings tests passing (AC: #3)
  - [x] `tests/unit/test_settings.py` re-imports `config.settings.base` under a monkeypatched environment with the module evicted from `sys.modules` first. Confirm that importing `base` with none of the four variables set still succeeds and yields `CLAIMS_CONTRACT.is_configured is False`. If it raises, Task 2's no-raise rule was not followed.
  - [x] Add that assertion as a new test in `tests/unit/test_settings.py` rather than a new file — it is a settings-module behaviour and belongs with the others.

- [x] Task 5 — Tests (AC: #1, #2, #3)
  - [x] `tests/unit/authorization/__init__.py` (new package) and `tests/unit/authorization/test_claims.py` (new).
  - [x] Parameterize `read_group_claim` over the three taxonomies AC #2 names: `("groups", {"groups": ["a"]})`, `("roles", {"roles": ["a"]})`, `("realm_access.roles", {"realm_access": {"roles": ["a"]}})` — each must yield `["a"]` with no code change, only a different `group_claim` value.
  - [x] Assert `read_group_claim` returns `None` for a missing path and for a missing intermediate segment, and `[]` (not `None`) for a present-but-empty list — the distinction Story 2.5's 401 rule rests on.
  - [x] Assert `load_claims_contract` on an empty environment yields four empty strings and `is_configured is False`, and that no field ever equals `"sub"`, `"groups"` or `"roles"` unless the environment said so.
  - [x] Run `pixi run test`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **FR-10 (binding rule):** "The claims contract is configuration — group-claim name and staff-conferring group read from the environment." Story 2.2 widens that to all four names, because AD-12 requires `is_superuser` to have "its own designated group" and AD-11 requires the identity key to come from "the claim the claims contract designates."
- **AD-12 (binding rule):** "A token lacking the configured group claim is rejected with 401, never authenticated with zero groups. A claim asserting a group with no matching Django `Group` is ignored and logged, never created … `is_staff` and `is_superuser` are each set from their own designated group and cleared when the claims stop asserting it." *Prevents:* "a misconfiguration presenting as a permissions bug; IdP group taxonomy silently becoming Django taxonomy; an `IntegrityError` mid-authentication."
  - This story does **not** implement those behaviours — Story 2.5 does. What this story owes AD-12 is the *distinction* between "claim absent" and "claim present and empty", which is why `read_group_claim` returns `None` versus `[]`. Collapsing them here makes AD-12 unimplementable downstream.
- **AD-13 (a constraint you must respect):** "**No `COMPONENT_*` variable may appear in `[activation.env]`**, and a gate test asserts it over the materialized `pixi.toml`." The four variables this story introduces carry the `COMPONENT_` prefix, so they are covered by that prohibition. Local values are set per-task in `pixi.toml` task `env` tables in Epic 3, never in `[activation.env]`. Do not put them in `[activation.env]` "just for local convenience" — Epic 8's gate test will fail on it.
- **Spine, Consistency Conventions → Environment variables:** "`COMPONENT_`-prefixed for component-level runtime facts … Never `DJANGO_ENV` or a bare `ENV`." The claims contract is a component-level runtime fact, hence the prefix. The existing `DJANGO_`-prefixed variables in `base.py` configure Django itself and are not the precedent to follow here.
- **Spine, Consistency Conventions → Package naming:** "Cross-cutting concerns with several independent consumers and no natural owner live under `src/config/<concern>/`, as `observability/` already does and `authorization/` and `startup/` will." This story creates `authorization/`. It has three independent consumers — the DRF Bearer class, the allauth adapter, and Epic 3's local sign-in route — which is exactly the condition the convention names.
- **FR-38 / AD-15:** "Configuration is exclusively environmental; no configuration file in the image." The contract is read from `environ.Env`, never from a TOML/YAML/JSON file shipped in the tree.
- **AD-24 (what you must not do):** no conditional imports, no `try/except ImportError`, no settings-module inheritance as a removal mechanism. `claims.py` is `core` and unconditional.
- **AD-4 (dependency direction):** `config` may import `django_service`; `django_service` may **never** import `config`. `claims.py` must import nothing from `django_service` and nothing from `django.contrib.auth` — it deals in names, not models. Story 2.3's provisioning code inside `django_service` reads the contract from `django.conf.settings`, never by importing `config.authorization.claims`.

### The forward reference in AC #3 — traceability marker, not an acceptance condition

AC #3's "it will refuse to start once Epic 4 lands" **records where the obligation completes; it is not this story's acceptance condition.** The epics document states this convention explicitly: "A small number of criteria reference a later epic — Story 2.2's refusal, Story 3.4's guarded route, Story 7.8's deliberate-orphan test. These are traceability markers recording where the obligation completes, not acceptance conditions for the story that carries them."

Concretely: **do not write an `ImproperlyConfigured` raise in this story.** The refusal is condition 5 in the epics' refusal table — "The claims contract is unusable", stage 1 and stage 2 — and it is authored in Epic 4 Story 4.2 inside `src/config/startup/`. What this story delivers, and what Epic 4 consumes, is `ClaimsContract.is_configured`. The half of AC #3 that **is** binding here is the second clause: "no conventional claim name is defaulted in its place."

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
|---|---|---|
| `src/config/authorization/__init__.py` | NEW | Package marker with a docstring. Directory does not exist today — verified. |
| `src/config/authorization/claims.py` | NEW | `ClaimsContract`, `load_claims_contract`, `read_group_claim`, `read_identity_key`. |
| `src/config/settings/base.py` | UPDATE | Today: `env = environ.Env()` at line 19; `# AUTHENTICATION` block at lines 130–142 holding `AUTHENTICATION_BACKENDS`, `AUTH_USER_MODEL`, `LOGIN_REDIRECT_URL`, `LOGIN_URL`. This story adds one import and one `CLAIMS_CONTRACT = load_claims_contract(env)` assignment in that block. **Preserve:** the whole `# PASSWORDS` comment block below it (lines 144–159), which already explains why `PASSWORD_HASHERS` is unset because authentication is delegated to an OIDC provider — that comment is the rationale-beside-configuration convention working, and it is about to become true rather than aspirational. |
| `src/config/settings/test.py` | UPDATE | Today: a short module setting `LOGGING`, `SECRET_KEY`, `TEST_RUNNER`, `PASSWORD_HASHERS`, `EMAIL_BACKEND`, `TEMPLATES[0]["OPTIONS"]["debug"] = True`, `MEDIA_URL`. Add an explicit `CLAIMS_CONTRACT` fixture value. **Preserve:** the `TEMPLATES[0]["OPTIONS"]["debug"] = True` line — AD-20's template coverage depends on it. |
| `tests/unit/authorization/__init__.py` | NEW | Test package marker; `tests/unit/users/__init__.py` is the precedent. |
| `tests/unit/authorization/test_claims.py` | NEW | Taxonomy parameterization and the no-default assertions. |
| `tests/unit/test_settings.py` | UPDATE | Exists. Add the "base imports cleanly with an unconfigured contract" case. |

### Testing Requirements

- Everything in this story is pure functions over mappings and an `environ.Env`. It is **unit-test territory only** — `tests/unit/authorization/test_claims.py`. No integration test is warranted: no I/O, no database, no network.
- `tests/integration/conftest.py` auto-marks anything under `tests/integration/` with `pytest.mark.integration`; nothing in this story belongs there.
- Use `pytest.MonkeyPatch` / `environ.Env` constructed in-test to drive `load_claims_contract`. Do not mutate `os.environ` without `monkeypatch`, and do not read the real environment in a test.
- Assertions the ACs demand: the three taxonomy forms of AC #2 resolve identically; the four names are each independently settable (AC #1); no field acquires a value the environment did not supply (AC #3).
- Coverage floor 90% including templates (AD-20), gate via `pixi run test-cov` inside `pixi run ci`. Add nothing to `[tool.coverage.run] omit`.
- Never `print()`. Never stdlib `logging`. If this module logs at all, it is `structlog` — but it should not need to: it parses, it does not decide.

#### Project Structure Notes

`src/config/authorization/` is named in the spine's Structural Seed as "the mapper (AD-10, AD-11, AD-12)" and confirmed absent from the repository today. Creating it here rather than in Story 2.4 is deliberate: 2.4 and 2.5 both consume the contract, and the readiness assessment records Epic 2's within-epic ordering as load-bearing.

`src/config/startup/` — the other seed directory — is **not** created by this story and must not be. It is Epic 4 Story 4.1's, and AD-26 requires it to have "one location, one owner."

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-12]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-4]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Structural Seed]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.2]
- [Source: _bmad-output/planning-artifacts/epics.md:301] — the forward-reference convention
- [Source: _bmad-output/planning-artifacts/epics.md:314-326] — the refusal-count table; condition 5 is "The claims contract is unusable", owned by Epic 4
- [Source: src/config/settings/base.py:19,130-159] — `env`, the AUTHENTICATION block, the PASSWORDS rationale comment
- [Source: tests/unit/test_settings.py:22-29] — the `sys.modules` eviction fixture that makes fresh settings imports possible

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m]

### Debug Log References

`pixi run ci` — exit 0. pre-commit (10 hooks) passed, build passed, `mypy src/`
found no issues in 40 source files, `ruff check .` clean, full suite 360 passed
with total coverage 92.89% against the 90% floor.

One iteration was needed: ruff TC002 required `import environ` to move into a
`TYPE_CHECKING` block in `claims.py`, since it is used only in the
`load_claims_contract` annotation. `src/config/observability/logging.py` is the
precedent for that block, and it carries no coverage pragma, so neither does
this one.

### Completion Notes List

- `ClaimsContract.is_configured` is a plain boolean property. No raise is
  authored anywhere in this story; the refusal is Epic 4 Story 4.2's, and it
  consumes this property.
- No conventional claim name is defaulted. All four reads use `default=""`.
- `read_group_claim` returns `None` for absent and `[]` for present-and-empty,
  which is the distinction AD-12 rests on. A scalar reads as a single group, and
  the malformed rule applies to the members as well as to the container: an
  object, null, boolean or blank member denies the whole claim rather than being
  coerced into a nonsense group name.
- `read_identity_key` shares the same dotted walk and the same one-value reader,
  so the two functions cannot disagree about what counts as a name.
- A claim name is tried as a literal key before it is split on dots, so an Auth0
  or Azure AD namespaced URI claim is expressible without a code change.
- Every environment value is stripped, so a whitespace-only variable reads as
  unset rather than as a truthy name that resolves nothing.
- `CLAIMS_ENVIRONMENT_VARIABLES` declares the four names once; a test pins the
  table in `docs/authentication.md` against it, since that page is the only
  operator-facing home for them.
- `src/config/startup/` was deliberately not created (Epic 4 Story 4.1 owns it).
- No `COMPONENT_*` variable was added to `[activation.env]` (AD-13).
- The four variable names are documented in `docs/authentication.md`, created
  here because no `.env`, `.env.example` or `.envs` exists in the repository.
  Story 2.3 extends that page rather than creating a second home.

### File List

| Path | NEW / UPDATE |
|---|---|
| `src/config/authorization/__init__.py` | NEW |
| `src/config/authorization/claims.py` | NEW |
| `src/config/settings/base.py` | UPDATE |
| `src/config/settings/test.py` | UPDATE |
| `tests/unit/authorization/__init__.py` | NEW |
| `tests/unit/authorization/test_claims.py` | NEW |
| `tests/unit/test_settings.py` | UPDATE |
| `docs/authentication.md` | NEW |
| `mkdocs.yml` | UPDATE |

## Review Triage Log

### 2026-08-16 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 10: (high 0, medium 5, low 5)
- defer: 3: (high 0, medium 1, low 2)
- reject: 4: (high 0, medium 0, low 4)
- addressed_findings:
  - `[medium]` `[patch]` A namespaced claim name containing literal dots (`https://example.com/roles`, an Azure AD schema URI) was split into segments and never resolved, making two of the taxonomies a component is most likely to meet unreachable by configuration — every token a 401 while the contract reported itself configured. `_resolve` now tries the whole path as a literal key before splitting; two parameterized tests plus a tie-break test pin it.
  - `[medium]` `[patch]` `environ.Env.str` does not strip, so a whitespace-only value (a ConfigMap block scalar, a trailing space in a `.env` line) was truthy: `is_configured` reported True and nothing resolved. `load_claims_contract` now strips every value; `test_a_blank_variable_reads_as_unset` covers four blank forms and `test_surrounding_whitespace_is_stripped_from_a_real_name` covers the ordinary case.
  - `[medium]` `[patch]` `read_group_claim` applied its "malformed denies" rule to the container only and stringified arbitrary members, so `[{"name": "admins"}]` became a group named `{'name': 'admins'}` — not None, so not a 401, and matching no Django group, so an authenticated caller where a refusal was owed. The rule now applies per member via a shared `_read_name`; ten parameterized cases pin it.
  - `[medium]` `[patch]` `{"groups": ""}` yielded `[""]`, a group literally named empty string, asymmetric with `read_identity_key`'s rejection of the same value. Blank scalars and blank members now deny.
  - `[medium]` `[patch]` No test proved a configured environment ever reached `settings.CLAIMS_CONTRACT`: replacing `base.py`'s read with a hardcoded empty contract passed the whole suite, so the one line connecting four variables to a running component was unprotected. Added `test_base_reads_a_configured_contract_from_the_environment` alongside the existing unconfigured case.
  - `[low]` `[patch]` Nothing read `django.conf.settings.CLAIMS_CONTRACT`, so `config/settings/test.py`'s fixture override could be deleted or drift back to the developer's shell with the gate still green. Added `test_the_active_settings_carry_a_configured_contract`.
  - `[low]` `[patch]` `docs/authentication.md` is the only operator-facing home for the four names (no `.env.example` exists) and was reconciled against nothing — a rename in `claims.py` would leave the published docs instructing operators to set a variable nothing reads. Added `CLAIMS_ENVIRONMENT_VARIABLES` as the single declaration and two tests closing the loop docs ↔ constant ↔ loader.
  - `[low]` `[patch]` `docs/authentication.md` stated "Local values are set per task in `pixi.toml`" in the present indicative, but no pixi task sets any `COMPONENT_` variable — a reader who went looking and found nothing could conclude `[activation.env]` was intended, the one thing AD-13 forbids. Reworded to state the present state explicitly and the Epic 3 destination conditionally.
  - `[low]` `[patch]` `read_group_claim` rejected a scalar numeric group while `read_identity_key` accepted a numeric subject, so one IdP emitting `42` as a scalar 401'd and the same value in a one-element list resolved. Both readers now share `_read_name`; `test_a_scalar_numeric_group_claim_reads_the_same_as_a_numeric_member` pins the agreement.
  - `[low]` `[patch]` A whitespace-only identity claim (`{"sub": "   "}`) was accepted as a stable identity key and would have been persisted as `idp_subject`. Now stripped and denied; added to the unusable-identity-key parameterization.

## Auto Run Result

Status: done

### Implemented change

The four names a component needs to read an IdP's claims — the identity-key claim, the group claim, and the
staff- and superuser-conferring groups — are now read from `COMPONENT_`-prefixed environment variables into a
frozen `ClaimsContract` exposed as the `CLAIMS_CONTRACT` setting, with two pure readers that resolve a claim by
name over decoded token claims. Nothing is defaulted and nothing raises: an unset variable stays empty, and
`is_configured` is the predicate Epic 4's startup refusal will consume.

### Files changed

- `src/config/authorization/__init__.py` (NEW) — package marker for the mapper's home (AD-10/AD-11/AD-12); no re-exports.
- `src/config/authorization/claims.py` (NEW) — `ClaimsContract`, `load_claims_contract`, `read_group_claim`, `read_identity_key`, `CLAIMS_ENVIRONMENT_VARIABLES`, and the private `_resolve`/`_read_name` pair. Imports nothing from `django_service` or `django.contrib.auth` (AD-4); deals in names, not models.
- `src/config/settings/base.py` — one import beside the observability siblings and `CLAIMS_CONTRACT = load_claims_contract(env)` at the end of the `# AUTHENTICATION` block, with the rationale recorded beside it. The `# PASSWORDS` comment block is untouched.
- `src/config/settings/test.py` — an explicit `CLAIMS_CONTRACT` fixture so the suite runs against a configured contract independent of the developer's shell, commented as fixtures rather than defaults. `TEMPLATES[0]["OPTIONS"]["debug"] = True` preserved.
- `tests/unit/authorization/__init__.py` (NEW) — test package marker.
- `tests/unit/authorization/test_claims.py` (NEW) — the three AC #2 taxonomies, namespaced-URI claim names, the absent/empty/malformed partition, the no-default assertions, the blank-variable rules, and the docs ↔ constant ↔ loader reconciliation.
- `tests/unit/test_settings.py` — the unconfigured-import case and the configured-environment case at the settings boundary, both with the four variables owned by `monkeypatch`.
- `docs/authentication.md` (NEW) — the operator-facing home for the four variable names, with no values.
- `mkdocs.yml` — nav entry for the new page.

### Review findings breakdown

Three reviewers ran in parallel (adversarial, edge-case, verification-gap) over `git diff f624273`. Seventeen distinct
findings after deduplication. **Ten patched** — five medium, five low — all in the diff's own surface: three widened
what the readers accept or refuse (literal-dot claim names, per-member malformed denial, blank values), two closed the
scalar/list and group/identity asymmetries, and five closed verification gaps (the settings wiring, the test-settings
override, the docs-to-code name reconciliation, the docs wording, the whitespace identity key). **Three deferred** to
`deferred-work.md` — `staff_group == superuser_group` accepted by `is_configured` (the spec pins that predicate to
non-emptiness and Epic 4 owns the refusal), malformed-versus-absent collapsing into one `None` for Story 2.5's
diagnostics, and `mkdocs build --strict` being absent from the gate. **Four rejected** — the AD-13 `[activation.env]`
guard (already a task in Story 3.1, and pre-empting it duplicates the owner), creating `docs/authentication.md` early
(a decision the spec authorizes), namespacing integer identity keys to keep numeric and string keyspaces disjoint
(would corrupt the stored subject for an exotic case), and cutting the `__init__.py` forward file list (the spec's
Task 1 dictates that docstring).

No intent gaps and no spec deviations: the spec was specific enough that every finding was a widening of unspecified
input handling or a missing observer, not a contradiction.

### Verification

- `pixi run ci` → **exit 0**. pre-commit all hooks pass, build OK, `mypy src/` strict **no issues in 40 source files**, `ruff check .` clean, **384 passed**, total coverage **92.97%** against the 90% floor.
- `src/config/authorization/claims.py` — 50 statements, **100%** covered. `src/config/settings/base.py` and `test.py` both remain at 100%.
- One CI iteration was lost to the pre-commit auto-fix trap (ruff fixed one lint and reformatted one file); re-staged and re-ran clean.
- `pixi run docs` → `mkdocs build --strict` builds, confirming the new nav entry and page resolve. Run by hand because the gate does not include it (deferred).
- Mutation check on the settings wiring: before the new test, replacing `base.py`'s `load_claims_contract(env)` with a hardcoded empty contract passed the entire suite. It now fails `test_base_reads_a_configured_contract_from_the_environment`.

### Residual risks

- **No startup refusal exists yet.** A deployed component with an unconfigured contract boots silently. That is AC #3's forward reference working as designed, but until Epic 4 Story 4.2 lands, `is_configured` has no consumer and nothing fails on a missing contract in production.
- **`is_configured` is shape, not semantics.** It now rejects blank values, but it still cannot know that a claim name resolves against any real token or that the staff/superuser group names correspond to Django `Group` rows. The `staff_group == superuser_group` escalation path is deferred, not closed.
- **Malformed and absent share one signal.** The safe direction for authorization, but it costs Story 2.5 the ability to log "claim present but not a list of names" — the message that turns a 401 into a fixable misconfiguration. Deferred.
- **AD-13 is live and unguarded.** These are the repository's first four `COMPONENT_` variables and nothing yet asserts they stay out of `[activation.env]`. Story 3.1 carries that test; until it lands the prohibition is documentation only.
- **`docs/authentication.md` was created two stories early.** Story 2.3 must extend it rather than create it, or the page will be clobbered and the doc-to-code name test will start failing for the wrong reason.
- **Nothing writes or reads these names at runtime yet.** Every guarantee here is about parsing; the resolution semantics AD-11 and AD-12 care about arrive with the mapper in Stories 2.4 and 2.5.
