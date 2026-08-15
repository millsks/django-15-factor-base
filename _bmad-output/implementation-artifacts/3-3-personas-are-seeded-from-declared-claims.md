# Story 3.3: Personas are seeded from declared claims

Status: ready-for-dev

## Story

As a developer working on a generated component,
I want named local identities declared as configuration and materialized by a task,
so that I can exercise real authorization differences without an identity realm.

## Acceptance Criteria

**Traceability:** FR-19 · AD-27 · SC-4

1. **Given** persona declarations
   **When** they are read
   **Then** each declares its groups, its profile fields, and the identity-key claim the mapper resolves by
   **And** at least two personas exist with different group memberships, one of which carries the designated staff group

2. **Given** the seeding task
   **When** it runs locally
   **Then** it materializes the declared personas as local accounts
   **And** it obtains the designated groups by calling the provisioning mechanism from Story 2.3 rather than creating groups of its own

3. **Given** a persona whose declared groups change
   **When** it re-authenticates
   **Then** the corresponding membership change occurs, including removal

4. **Given** the seeding task
   **When** it is invoked in a deployed environment
   **Then** it raises the same `ImproperlyConfigured` as the refusal contract
   **And** it never creates a local account there

5. **Given** a persona signs in twice
   **When** it is resolved
   **Then** it is the same user both times

## Tasks / Subtasks

- [ ] Task 1: Create the local development package (AC: #1)
  - [ ] Create `src/config/local_dev/__init__.py` (NEW) with a module docstring stating that this package is the whole of the local development contract's code surface, that it is `core` and ships in every component (FR-19), and that it is guarded by the refusal contract rather than stripped from materialized output.
  - [ ] This package is also the module whose view callable Epic 4's stage-2 predicate resolves against (AD-21, AD-26). Do not scatter local-development code into other packages; a second home defeats the predicate.

- [ ] Task 2: Declare the personas as configuration (AC: #1, #5)
  - [ ] Create `src/config/local_dev/personas.py` (NEW).
  - [ ] Define a frozen dataclass `Persona` with fields: `key: str` (the slug used on the sign-in URL and in the task's output), `subject: str` (the identity-key **value** the mapper resolves by), `username: str`, `email: str`, `name: str`, `groups: tuple[str, ...]`.
  - [ ] Define two sentinels, `DESIGNATED_STAFF` and `DESIGNATED_SUPERUSER`, as module constants. A persona lists a sentinel in `groups` where it should carry whichever group the claims contract designates, so no persona hardcodes a group name.
  - [ ] Declare `PERSONAS: tuple[Persona, ...]` with at least two entries and genuinely different memberships: one staff persona whose `groups` contains `DESIGNATED_STAFF`, and one read-only persona whose `groups` contains neither sentinel. Give each a distinct `subject`, `username` and `email`.
  - [ ] Implement `get_persona(key: str) -> Persona` raising `KeyError` (or a narrow module exception) for an unknown key, and `persona_keys() -> tuple[str, ...]`.
  - [ ] Implement `resolve_groups(persona: Persona) -> tuple[str, ...]`: substitutes `DESIGNATED_STAFF` for `settings.CLAIMS_CONTRACT.staff_group` and `DESIGNATED_SUPERUSER` for `settings.CLAIMS_CONTRACT.superuser_group` (Story 2.2's `ClaimsContract` frozen dataclass, exposed as `CLAIMS_CONTRACT` in `src/config/settings/base.py`). Read them through `django.conf.settings`, never from a literal.
  - [ ] Implement `build_claims(persona: Persona) -> dict[str, Any]`: returns a synthetic claims payload keyed by the **configured** claim names — `settings.CLAIMS_CONTRACT.identity_key_claim` and `settings.CLAIMS_CONTRACT.group_claim` — carrying `persona.subject`, `resolve_groups(persona)`, and the profile fields under the standard OIDC names `preferred_username`, `email` and `name` (which is what Story 2.4's `_attributes_from_claims` reads).
  - [ ] Both claim names may be **dotted paths**: Story 2.2's `read_group_claim` / `read_identity_key` resolve a dotted path through nested mappings so `realm_access.roles` is expressible. `build_claims` must therefore *write* a nested payload for a dotted name — a flat key literally named `"realm_access.roles"` will not be found by the reader. Write a small `_set_dotted(payload, path, value)` helper and test it against all three taxonomies (`groups`, `roles`, `realm_access.roles`).
  - [ ] `build_claims` does **not** add `jti`, `iss`, `aud` or `exp`. Those are registered claims of the programmatic flow and are added by Story 3.5's token minting; an interactive persona sign-in is itself the epoch and has no `jti` (Story 2.5's `sync_for_interactive`).
  - [ ] This function is the sole constructor of synthetic claims; Stories 3.4 and 3.5 both call it. Do not build a second payload in either.

- [ ] Task 3: Author the seeding operation (AC: #2, #4)
  - [ ] Create `src/config/local_dev/seeding.py` (NEW) exposing `seed_personas() -> list[str]`, returning the persona keys it materialized.
  - [ ] **First statement:** refuse when not local. `from config.locality import is_local` (Story 3.1); when `is_local()` is `False`, raise `django.core.exceptions.ImproperlyConfigured` with a message naming `COMPONENT_RUNTIME` and stating that persona seeding never creates a local account in a deployed environment. Nothing after this line may execute; do not warn, do not no-op, do not gate on `DEBUG`.
  - [ ] **Second statement:** obtain the designated groups by calling `provision_designated_groups()` from `src/django_service/users/provisioning.py` — the one callable Story 2.3 authored, and the same one its data migration `0003_provision_designated_groups.py` invokes. Call it with no argument so it uses the live app registry (its signature is `provision_designated_groups(apps: StateApps | Apps | None = None) -> ProvisionResult`). **Do not** call `Group.objects.get_or_create`, `Group.objects.create`, or a fixture load anywhere in this module — Story 2.3 ships a test asserting those calls appear in `src/` only inside `provisioning.py`, and this module is the one most likely to break it.
  - [ ] Materialize each persona: for each entry in `PERSONAS`, build its claims with `build_claims`, then call `resolve_user(claims)` followed by `sync_for_interactive(user, claims)` from `src/config/authorization/mapper.py` (Stories 2.4 and 2.5). Use `sync_for_interactive`, **not** `sync_once_per_epoch` — seeding has no `jti` and is not a Bearer epoch. The mapper is what creates or updates the user and applies group membership, staff and superuser status; this module holds no mapping logic of its own.
  - [ ] Idempotent: running it twice materializes the same users, resolved by the identity key, with no duplicates.
  - [ ] Emit one structured `structlog` event per persona recording the key, the resolved user id and the resulting group set. Never `print`; never stdlib `logging`.

- [ ] Task 4: Author the runnable entry point and the pixi task (AC: #2, #4)
  - [ ] Create `src/config/local_dev/seed.py` (NEW) as a `python -m` entry point: `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")`, `django.setup()`, then call `seed_personas()` and log the result. Guard the call with `if __name__ == "__main__":`.
  - [ ] Add to `pixi.toml` `[tasks]`: `seed-personas = { cmd = "python -m config.local_dev.seed", env = { COMPONENT_RUNTIME = "local" }, default-environment = "default", description = "Seed the local development personas" }`. It belongs in `[tasks]`, not `[feature.dev.tasks]`, because it ships in every component and must run from the runtime environment.
  - [ ] Add `seed-personas` to the `LOCAL_TASKS` data set in `tests/unit/test_locality_declaration.py` (authored by Story 3.1) so the two-way locality assertion covers it.
  - [ ] Do **not** implement seeding as a Django management command. A management command must live inside an installed app; the only installed app package is `django_service`, and `django_service` importing `config.local_dev` inverts AD-4's dependency direction. The `python -m` entry point keeps the arrow pointing `config → django_service`.

- [ ] Task 5: Document the personas (AC: #1, #2, #4)
  - [ ] In `docs/development.md`, add a `## Local personas` section: the declared personas and their memberships, `pixi run seed-personas`, the statement that seeding calls the component's own group provisioning rather than creating groups, and the statement that it refuses in a deployed environment.
  - [ ] Carry R-5 honestly: synthetic claims never exercise JWKS retrieval or rotation, and the PRD's own words — the local personas "are not a mitigation" for the absence of a real IdP.

- [ ] Task 6: Tests (AC: #1, #2, #3, #4, #5)
  - [ ] Create `tests/unit/test_local_dev_personas.py` (NEW): assert `PERSONAS` has at least two entries; assert their `groups` differ; assert exactly one carries `DESIGNATED_STAFF`; assert every persona declares a non-empty `subject`, `username`, `email`; assert `build_claims` keys the identity value under the **configured** identity-key claim name and the groups under the **configured** group-claim name (override `settings.CLAIMS_CONTRACT` and assert the payload keys move accordingly); assert a dotted `group_claim` of `realm_access.roles` produces a **nested** payload that Story 2.2's `read_group_claim` reads back, and do the same round-trip for `groups` and `roles`; assert `build_claims` adds no `jti`, `iss`, `aud` or `exp`.
  - [ ] Create `tests/unit/test_local_dev_seeding_refusal.py` (NEW): with `COMPONENT_RUNTIME` unset, and again set to `"production"`, `"dev"` and `""`, assert `seed_personas()` raises `ImproperlyConfigured`. Assert with a patched provisioning callable and a patched mapper that **neither is called** on the refusal path — the refusal must fire before any database work.
  - [ ] Create `tests/integration/test_local_dev_seeding.py` (NEW), every test `@pytest.mark.integration`:
    - [ ] `test_seeding_materializes_declared_personas`: with `COMPONENT_RUNTIME=local`, run `seed_personas()` and assert each persona exists as a user whose identity key equals its declared `subject` and whose group set equals `resolve_groups(persona)`.
    - [ ] `test_seeding_calls_the_shared_group_provisioning`: patch or spy the Story 2.3 provisioning callable and assert it is invoked; separately assert `seeding.py` contains no direct `Group` creation by asserting that with provisioning patched to a no-op the designated groups are absent and seeding surfaces that rather than creating them.
    - [ ] `test_seeding_is_idempotent`: run twice; assert the same user ids and no duplicate accounts.
    - [ ] `test_declared_group_change_is_applied_on_re_authentication`: seed, then mutate the persona's declared groups (a locally constructed `Persona` copy is fine), re-run the claims through the mapper, and assert the added membership appears **and the dropped membership is removed**.
    - [ ] `test_a_persona_resolves_to_the_same_user_twice`: run the claims through the mapper twice and assert one user, same primary key.
  - [ ] Every integration test leaves state as found — use the `db` fixture so the transaction rolls back.

## Dev Notes

### Architecture Constraints

**AD-27 — Authorization data has an owner.** Binding rule, in the AD's own words:

> Django `Group` rows named by the claims contract, and the `Permission` rows attached to them, are provisioned by a data migration inside `django_service`, seeded from the claims contract, so they exist before the first authentication. **The local persona seeding task calls that same mechanism rather than reimplementing it — a task that creates groups itself is what makes the deadlock invisible to the harness.** A designated staff or superuser group absent from the database at startup is a stage-2 refusal condition, on AD-12's own reasoning: a misconfiguration must not present as a permissions bug.

*Prevents:* "the bootstrap deadlock in which every deployed component grants nobody any authorization and nobody can reach the admin, while all twelve local smoke checks pass."

This is load-bearing and it is the single easiest rule in this story to break by accident. A seeding task that calls `Group.objects.get_or_create(name=...)` will pass every one of this story's happy-path tests and every one of the twelve local smoke checks, while every deployed component is unreachable by anyone. The groups must come from the mechanism Story 2.3 built — the same callable its data migration invokes — and from nowhere else.

**AD-11 — One identity key, three separated roles.** A persona's `subject` is the identity key and populates `User.idp_subject` (unique, indexed, nullable, sole store). `username`, `email` and `name` are attributes: populated from claims, displayed, used in URLs, **never resolved by**. `USERNAME_FIELD` remains `username`. AC #5 is a direct consequence — resolution is by identity key, so a persona is the same user across sign-ins whatever its username does.

**AD-12 — The mapper's edge behaviours are fixed.** A claim asserting a group with no matching Django `Group` "is ignored and logged, never created — which is safe only because AD-27 guarantees the designated groups exist." That safety is exactly what a seeding task creating its own groups would destroy. Also: `is_staff` and `is_superuser` are each set from their own designated group and cleared when the claims stop asserting it — which is why AC #3's removal half must be tested, not assumed.

**AD-10 — The mapper is two operations at different frequencies.** Seeding must drive **resolve then sync**, not a bespoke user-creation path, and the payload must carry a `jti` because "a token with no `jti` is rejected with 401."

**AD-4 — Dependency direction.** `config` may import `django_service`; `django_service` may **never** import a tenant app, and nothing in `django_service` may reach back into `config.local_dev`. This is why seeding is a `python -m` entry point rather than a management command (Task 4).

**AD-13 — Locality fails closed.** The refusal in Task 3 reads locality through `config.locality.is_local()` (Story 3.1) and through no other mechanism. Absent or unrecognized means deployed, so an operator who runs the seeding module in production gets `ImproperlyConfigured`, not an account.

**FR-19's own words on why this ships rather than being stripped:** "shipping this path and guarding it was chosen over stripping it from materialized output, because a stripped path cannot be tested by the component's own gate. The cost is that the product now creates a credential path of its own — which is why it is enumerated in the refusal contract rather than trusted to stay unused."

**Never:** `print()`; stdlib `logging`; bare `except:`; `except X: pass`; `Union`/`List`/`Dict`; a second synthetic-claims constructor; a `DEBUG`-based locality test.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/local_dev/__init__.py` | NEW | Package docstring; the declared home of the local development contract's code. |
| `src/config/local_dev/personas.py` | NEW | `Persona` dataclass, `DESIGNATED_STAFF` / `DESIGNATED_SUPERUSER` sentinels, `PERSONAS`, `get_persona`, `persona_keys`, `resolve_groups`, `build_claims`. |
| `src/config/local_dev/seeding.py` | NEW | `seed_personas()` — refuse-if-deployed, call the shared group provisioning, drive the mapper per persona. |
| `src/config/local_dev/seed.py` | NEW | `python -m config.local_dev.seed` entry point. |
| `pixi.toml` | UPDATE | Add the `seed-personas` task with `env = { COMPONENT_RUNTIME = "local" }`. |
| `tests/unit/test_locality_declaration.py` | UPDATE | Add `seed-personas` to `LOCAL_TASKS` (file authored by Story 3.1). |
| `docs/development.md` | UPDATE | New `## Local personas` section. |
| `tests/unit/test_local_dev_personas.py` | NEW | Declaration-shape and claims-construction assertions. |
| `tests/unit/test_local_dev_seeding_refusal.py` | NEW | The deployed-environment refusal, asserted before any database work. |
| `tests/integration/test_local_dev_seeding.py` | NEW | Materialization, shared provisioning, idempotence, membership change including removal, same-user-twice. |

**Dependencies on earlier stories — the concrete names, verified against those stories' own files.** Confirm each exists before starting; if a name moved, follow the implementation, not this table:

| From | Surface |
| --- | --- |
| Story 3.1 | `config.locality.is_local()` |
| Story 2.1 | `User.idp_subject` — unique, indexed, nullable |
| Story 2.2 | `src/config/authorization/claims.py`: `ClaimsContract(identity_key_claim, group_claim, staff_group, superuser_group)`, `load_claims_contract`, `read_group_claim`, `read_identity_key`; exposed as `settings.CLAIMS_CONTRACT` from `src/config/settings/base.py`, with explicit fixture values set in `src/config/settings/test.py` |
| Story 2.3 | `src/django_service/users/provisioning.py`: `provision_designated_groups(apps=None) -> ProvisionResult`, `DESIGNATED_GROUP_PERMISSIONS` |
| Story 2.4 | `src/config/authorization/mapper.py`: `resolve_user(claims) -> User`, `_attributes_from_claims` (reads `preferred_username`, `email`, `name`) |
| Story 2.5 | Same module: `sync_authorization`, `sync_once_per_epoch`, `sync_for_interactive`, `SyncOutcome(added, removed, ignored, is_staff, is_superuser)` |

`src/config/authorization/` and `src/config/local_dev/` do **not** exist in the repository today; `src/config/` currently holds `settings/`, `observability/`, `api_router.py`, `asgi.py`, `celery_app.py`, `urls.py`, `websocket.py`, `wsgi.py`.

**`src/django_service/users/models.py` today (verified).** `User(AbstractUser)` with `name = CharField(...)`, `first_name = None`, `last_name = None`, and `get_absolute_url()` reversing `users:detail` by `username`. `idp_subject` is added by Story 2.1; do not add it here.

**`pixi.toml` today.** `[tasks]` holds `manage`, `migrate`, `collectstatic`, `createsuperuser`, `serve`; `[feature.dev.tasks]` holds the development and harness tasks. Every task carries an explicit `default-environment` and a `description` — match that shape.

### Testing Requirements

- Unit tests (`tests/unit/`) must not touch the database, the network or the filesystem — `tests/unit/conftest.py` states the rule. The persona-declaration tests operate on the dataclasses and on `django.conf.settings` overrides; the refusal test patches the provisioning callable and the mapper and asserts neither was reached.
- Every test in `tests/integration/test_local_dev_seeding.py` carries `@pytest.mark.integration` and uses the `db` fixture so its transaction rolls back. `tests/conftest.py` supplies `user` (`:18-20`) and an autouse `_media_storage` fixture (`:13-15`).
- The refusal assertion is `pytest.raises(ImproperlyConfigured)` — the spine's Consistency Conventions state that every forbidden or missing configuration raises `ImproperlyConfigured` and that "a refusal never degrades to a warning (CG-3)."
- AC #3's removal half must be asserted explicitly. A test that only adds a group passes while revocation silently never happens.
- Coverage floor: ninety percent including templates (AD-20), `COVERAGE_CORE=ctrace`, `--cov-fail-under=90`. `pixi run ci` must exit 0.
- Test disposition: `core` — these cover surface that ships in every combination, under `tests/` mirroring `src/`.
- Run with `pixi run test` / `pixi run test-integration`; never bare `pytest`.

#### Project Structure Notes

`src/config/local_dev/` is a new package under the composition root. It is justified by the spine's Consistency Conventions — "cross-cutting concerns with several independent consumers and no natural owner live under `src/config/<concern>/`, as `observability/` already does and `authorization/` and `startup/` will" — and is required by AD-21, which needs a single identifiable module whose view callable the stage-2 predicate can resolve. It is a variance from the Structural Seed's literal listing (which names only `settings/`, `observability/`, `authorization/`, `startup/`), not from its rule.

Its disposition is `core`: FR-19 states the path ships in every component and is guarded rather than stripped. When Epic 7 authors `accelerator.toml`, `src/config/local_dev/` is declared `core`, and no `feature:*` disposition applies to it.

**Cross-epic marker, not an acceptance condition for this story:** the credential path this package introduces is refused at startup in a deployed component by Epic 4's stage-2 condition. Epic 4 imports this package to resolve the forbidden view callable; keep the package name and its public surface stable.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-27]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-10] · [#AD-11] · [#AD-12] · [#AD-4] · [#AD-13] · [#AD-21]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — `src/config/<concern>/`; `ImproperlyConfigured` for every forbidden configuration; structured JSON logging; test location.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-19] — declarations, the task, the refusal, and why the path ships rather than being stripped.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md:928] — the local personas "are not a mitigation."
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.3] · [#Story 2.3] · [#Story 2.5]
- [Source: _bmad-output/planning-artifacts/epics.md:334] — SC-6 is not closed by personas; it needs a real IdP.
- [Source: src/django_service/users/models.py] · [Source: tests/conftest.py:13-20] · [Source: tests/unit/conftest.py] · [Source: pixi.toml]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
