# Story 2.2: The claims contract is read from the environment

Status: ready-for-dev

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

- [ ] Task 1 — Create the authorization package (AC: #1)
  - [ ] Create `src/config/authorization/__init__.py` with a module docstring naming AD-10/AD-11/AD-12 as its charter. The directory does not exist today; this story creates it.
  - [ ] Do not add anything else to `__init__.py`. It is a package marker, not a re-export surface; later stories add `claims.py`, `mapper.py`, `jwks.py`, `authentication.py`, `adapters.py` beside it.

- [ ] Task 2 — Declare the contract as a frozen dataclass in `src/config/authorization/claims.py` (AC: #1, #2, #3)
  - [ ] `@dataclass(frozen=True, slots=True) class ClaimsContract` with four `str` fields: `identity_key_claim`, `group_claim`, `staff_group`, `superuser_group`. Google-style docstring on the class stating that each is a *name*, never a value.
  - [ ] Add `is_configured: bool` as a property returning `all(...)` over the four fields being non-empty. **Do not raise here.** AC #3 says the refusal is Epic 4's; a raise at import would fire during `pixi run test` and during every management command before Epic 4 has a locality signal to gate it with.
  - [ ] Add `def load_claims_contract(env: environ.Env) -> ClaimsContract` reading exactly four variables with `default=""`:
    `COMPONENT_IDENTITY_CLAIM`, `COMPONENT_GROUP_CLAIM`, `COMPONENT_STAFF_GROUP`, `COMPONENT_SUPERUSER_GROUP`.
    **No fallback value of any kind** — not `"sub"`, not `"groups"`, not `"roles"`. The empty string means unconfigured and is what Epic 4 refuses on.
  - [ ] Add `def read_group_claim(claims: Mapping[str, Any], path: str) -> list[str] | None` resolving a **dotted path** through nested mappings, returning `None` when any segment is missing and a `list[str]` otherwise. This is what makes `realm_access.roles` expressible (AC #2). Return `None` — not `[]` — for absent, because AD-12 makes the absent case a 401 and the empty case must never be silently equivalent to it.
  - [ ] Add `def read_identity_key(claims: Mapping[str, Any], path: str) -> str | None` using the same dotted-path walk, so a nested identity claim needs no second mechanism.

- [ ] Task 3 — Wire the contract into settings (AC: #1)
  - [ ] In `src/config/settings/base.py`, in the `# AUTHENTICATION` block (currently lines 130–142), add `from config.authorization.claims import load_claims_contract` at the top import group and `CLAIMS_CONTRACT = load_claims_contract(env)`.
  - [ ] Place the import beside the existing `from config.observability.logging import ...` imports (base.py:11-12) — importing a `config` sibling from settings is already the established pattern in this file.
  - [ ] Add the four variable names, with no values, to `.envs`/`.env.example` if such a file exists in the repository; if none exists, document them in `docs/` instead (Story 2.3 creates `docs/authentication.md` — if that file already exists when you get here, add them there rather than creating a second home).
  - [ ] Set explicit test values in `src/config/settings/test.py` so the suite runs against a *configured* contract independent of the developer's shell: `CLAIMS_CONTRACT = ClaimsContract(identity_key_claim="sub", group_claim="groups", staff_group="platform-staff", superuser_group="platform-superuser")`. State in a comment that these are test fixtures, not defaults.

- [ ] Task 4 — Keep the existing settings tests passing (AC: #3)
  - [ ] `tests/unit/test_settings.py` re-imports `config.settings.base` under a monkeypatched environment with the module evicted from `sys.modules` first. Confirm that importing `base` with none of the four variables set still succeeds and yields `CLAIMS_CONTRACT.is_configured is False`. If it raises, Task 2's no-raise rule was not followed.
  - [ ] Add that assertion as a new test in `tests/unit/test_settings.py` rather than a new file — it is a settings-module behaviour and belongs with the others.

- [ ] Task 5 — Tests (AC: #1, #2, #3)
  - [ ] `tests/unit/authorization/__init__.py` (new package) and `tests/unit/authorization/test_claims.py` (new).
  - [ ] Parameterize `read_group_claim` over the three taxonomies AC #2 names: `("groups", {"groups": ["a"]})`, `("roles", {"roles": ["a"]})`, `("realm_access.roles", {"realm_access": {"roles": ["a"]}})` — each must yield `["a"]` with no code change, only a different `group_claim` value.
  - [ ] Assert `read_group_claim` returns `None` for a missing path and for a missing intermediate segment, and `[]` (not `None`) for a present-but-empty list — the distinction Story 2.5's 401 rule rests on.
  - [ ] Assert `load_claims_contract` on an empty environment yields four empty strings and `is_configured is False`, and that no field ever equals `"sub"`, `"groups"` or `"roles"` unless the environment said so.
  - [ ] Run `pixi run test`, then `pixi run ci`.

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
- [Source: _bmad-output/planning-artifacts/epics.md:299] — the forward-reference convention
- [Source: _bmad-output/planning-artifacts/epics.md:314-326] — the refusal-count table; condition 5 is "The claims contract is unusable", owned by Epic 4
- [Source: src/config/settings/base.py:19,130-159] — `env`, the AUTHENTICATION block, the PASSWORDS rationale comment
- [Source: tests/unit/test_settings.py:22-29] — the `sys.modules` eviction fixture that makes fresh settings imports possible

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
