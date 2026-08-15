# Story 2.4: The mapper resolves an identity to a user

Status: ready-for-dev

## Story

As a platform engineer,
I want one mapper that resolves any set of claims to a user by the identity key alone,
so that the same person is the same user across flows, and two people whose emails collide are not.

## Acceptance Criteria

**Traceability:** FR-8 · AD-10, AD-11, AD-12 · SC-6

1. **Given** the mapper at `src/config/authorization/`
   **When** any caller presents claims
   **Then** the user is resolved or created by the identity-key claim alone
   **And** never by email address or username

2. **Given** an identity first seen through one flow and later through the other
   **When** it authenticates the second time
   **Then** it resolves to the same user
   **And** a test asserts this in both orders

3. **Given** two distinct identities whose email claims collide
   **When** each authenticates
   **Then** they resolve to two distinct users

4. **Given** a `username` collision between two distinct identity keys
   **When** the second identity authenticates
   **Then** the collision is refused and logged
   **And** the second identity keeps its existing username and authenticates normally

5. **Given** resolution runs on every authentication including every Bearer request
   **When** it runs
   **Then** it is a single indexed read

## Tasks / Subtasks

- [ ] Task 1 — Declare the mapper's failure type at `src/config/authorization/exceptions.py` (AC: #1)
  - [ ] `class ClaimsRejected(Exception)` with a `reason: str` attribute. This is the mapper's one refusal signal; callers translate it to HTTP status.
  - [ ] The mapper must never import `rest_framework` or raise `AuthenticationFailed` directly. The DRF Bearer class (Story 2.7) and the allauth adapter (Story 2.6) each translate `ClaimsRejected` into their own protocol's 401. Keeping DRF out of the mapper is what lets the same mapper serve the interactive flow, the Bearer flow and Epic 3's local sign-in route.

- [ ] Task 2 — Implement `resolve_user` in `src/config/authorization/mapper.py` (AC: #1, #2, #3, #5)
  - [ ] Signature: `def resolve_user(claims: Mapping[str, Any]) -> User`. Full type hints; Google-style docstring stating the AD-10 frequency contract ("runs on every authentication, including every Bearer request; one indexed read").
  - [ ] Read the identity key with `read_identity_key(claims, settings.CLAIMS_CONTRACT.identity_key_claim)` from Story 2.2. A missing or empty identity key raises `ClaimsRejected("identity key claim absent")`.
  - [ ] The lookup is **exactly one query**: `User.objects.filter(idp_subject=subject).first()`. Not `get()` inside `try/except User.DoesNotExist` (same query count, worse control flow), not `get_or_create` (two queries plus a write attempt on the hot read path), and not a `select_related` or `prefetch_related` of groups — sync loads groups, resolve does not.
  - [ ] On a hit, return the user immediately. Do **not** write attributes on the resolve path; attribute reconciliation belongs to Task 3 and runs only when something actually changed.
  - [ ] On a miss, create the user inside `transaction.atomic()` with `idp_subject=subject`, an unusable password (`user.set_unusable_password()`), and attributes derived per Task 3. A deployed component authenticates nobody locally, so no user the mapper creates may ever carry a usable password.

- [ ] Task 3 — Implement attribute population and the username-collision rule (AC: #1, #3, #4)
  - [ ] `def _attributes_from_claims(claims) -> dict[str, str]` pulling `username`, `email`, `name` from the standard OIDC claim names (`preferred_username`, `email`, `name`), falling back to the identity key when `preferred_username` is absent.
  - [ ] `email` is written unconditionally and is **never** part of any lookup. `AbstractUser.email` is not unique in this model, so two identities with the same email produce two rows with no constraint conflict — that is AC #3 satisfied structurally rather than by a code branch. Do not add a uniqueness constraint on `email`.
  - [ ] `username` is written only when the desired value is free. Before writing, check `User.objects.filter(username=desired).exclude(pk=user.pk).exists()`. If it exists, **do not write it**: emit `structlog` event `authorization.username_collision` at warning with `idp_subject`, `desired_username` and `held_by_idp_subject`, and leave the user's current username in place. That is AC #4's "refused and logged … keeps its existing username and authenticates normally" and AD-12's "Prevents … an `IntegrityError` mid-authentication."
  - [ ] For a **first sighting** whose desired username is already taken, the user still has to be created with *some* username, and it must be deterministic and collision-free. Derive it from the identity key — e.g. a stable, truncated, sanitized rendering of `idp_subject` — and log the same collision event. Never append a random suffix or a counter: a non-deterministic username makes AC #2's "resolves to the same user in both orders" test flaky and makes the collision unreproducible in support.
  - [ ] Save with `user.save(update_fields=[...])` listing only the fields that actually changed, and skip the save entirely when nothing changed. Resolve on a Bearer request must not write.

- [ ] Task 4 — Prove the single-read property, do not merely assert it in prose (AC: #5)
  - [ ] Write the resolve path so that the hit case issues exactly one `SELECT`. Verify it with `django.test.utils.CaptureQueriesContext` or pytest-django's `django_assert_num_queries` fixture.
  - [ ] AD-10's stated purpose is preventing "`auth_user_groups` write amplification on every API call". A resolve that touches `user.groups` — even to read — defeats it. Do not.

- [ ] Task 5 — Tests (AC: #1, #2, #3, #4, #5)
  - [ ] `tests/unit/authorization/test_mapper_resolve.py` (new) — claim-extraction and username-derivation behaviour that needs no database: `ClaimsRejected` on an absent identity claim; deterministic derived username for the same `idp_subject` across repeated calls.
  - [ ] `tests/integration/authorization/__init__.py` and `tests/integration/authorization/test_mapper_resolve.py` (new, `@pytest.mark.django_db`):
    - AC #1 — an identity whose `email` and `preferred_username` both match an existing user, but whose `idp_subject` differs, resolves to a **new** user, not the existing one.
    - AC #2 — call `resolve_user` twice with the same `idp_subject` and different attribute claims, in both orders (interactive-shaped claims first then Bearer-shaped, and the reverse), asserting the same `pk` both times. The AC says "a test asserts this in both orders" — write both directions explicitly, not one parameterized case that only covers one.
    - AC #3 — two identities with identical `email` claims and distinct `idp_subject`s produce two distinct users.
    - AC #4 — seed user A with `username="ada"` and `idp_subject="A"`; resolve claims with `idp_subject="B"` and `preferred_username="ada"`; assert B is created, B's username is not `"ada"`, A's username is still `"ada"`, both authenticate, and the collision event was emitted.
    - AC #5 — `django_assert_num_queries(1)` around a resolve of an existing identity.
  - [ ] Capture structlog events with `structlog.testing.capture_logs()` to assert the collision event rather than asserting on captured stdout.
  - [ ] Run `pixi run test`, `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-10 (binding rule — the resolve half only):** "**Resolve** takes claims and returns the user by the identity key. It runs on every authentication, including every Bearer request, and is a single indexed read." *Prevents:* "the only two outcomes of conflating them — `auth_user_groups` write amplification on every API call, or stale authorization."
  - **Do not implement sync in this story.** Group diffing, `is_staff`/`is_superuser`, the epoch record, the `jti` rule and the transaction are all Story 2.5. AD-10 exists precisely because the two get conflated; a `resolve_user` that also syncs is the failure this AD is written to prevent. Keep them separate functions in the same module.
- **AD-11 (binding rule):** "**Identity key** is `User.idp_subject`: unique, indexed, nullable, populated from the claim the claims contract designates, and the sole store. The allauth adapter resolves through the mapper too; `SocialAccount` is bookkeeping, not authority. **Attribute** is `username`, `email`, `name` — populated from claims, displayed, used in URLs, **never resolved by**." *Prevents:* "account takeover through a mutable or collidable claim; the same person resolving to two users depending on which flow saw them first."
  - "Never resolved by" is absolute. No `User.objects.get(email=...)` fallback, no "look up by username if `idp_subject` is null" convenience, no `SocialAccount.objects.get(uid=...)` read. The nullable `idp_subject` on pre-existing rows (Story 2.1 AC #3) means those rows are simply not resolvable until they authenticate — which is the intended behaviour, not a gap to patch.
- **AD-12 (binding rule):** "A `username` collision between two distinct `idp_subject`s is refused and logged; the second identity keeps its existing username and authenticates normally." *Prevents:* "a misconfiguration presenting as a permissions bug; IdP group taxonomy silently becoming Django taxonomy; an `IntegrityError` mid-authentication."
- **FR-8:** "One shared mapper at `src/config/authorization/` owns all authorization decisions, resolving users by one designated identity-key claim." One mapper. The DRF class, the allauth adapter and the local sign-in route are all *callers*; none may contain resolution logic of its own — Stories 2.6 and 2.7 each carry an explicit AC to that effect.
- **AD-4:** `config` may import `django_service`, so `config.authorization.mapper` importing `django_service.users.models.User` is legal and expected. Prefer `django.contrib.auth.get_user_model()` at call time over a module-level import of the concrete class, so the mapper does not pin `AUTH_USER_MODEL`.
- **AD-24 (what you must not do):** no conditional imports, no `try/except ImportError`, no settings-module inheritance. The mapper is `core` and present in all twelve combinations.
- **Spine, Consistency Conventions → Logging:** structured JSON to stdout carrying `request_id`, `trace_id`, `span_id`; **every authorization change emits an event**. Use `structlog.get_logger(__name__)`. Never `print()`. Never stdlib `logging`. `django-structlog`'s `RequestMiddleware` (already in `MIDDLEWARE` at `src/config/settings/base.py:175`) binds `request_id` for the life of a request, so the mapper's events inherit correlation without doing anything.
- **Spine, Consistency Conventions → Runtime errors:** "Nothing is swallowed silently." Never a bare `except:`; never `except X: pass`. The collision case is logged and handled, not swallowed.

### SC-6 cannot be closed here

The `**Requirements:**` line names SC-6. SC-6 requires a real IdP identity authenticating through both flows and is an **external exit criterion no story closes** — owner: the platform group, after Epic 2. Every AC in this story is satisfiable against synthetic claim dictionaries, and passing them does not prove SC-6. Do not report otherwise.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
|---|---|---|
| `src/config/authorization/mapper.py` | NEW | `resolve_user`, `_attributes_from_claims`, the collision rule. Story 2.5 adds `sync_authorization` and `sync_once_per_epoch` to this same module. |
| `src/config/authorization/exceptions.py` | NEW | `ClaimsRejected`. |
| `src/config/authorization/__init__.py` | UPDATE | Created in Story 2.2 as a docstring-only package marker. Leave it that way — do not add re-exports. |
| `tests/unit/authorization/test_mapper_resolve.py` | NEW | `tests/unit/authorization/__init__.py` is created by Story 2.2; confirm it exists. |
| `tests/integration/authorization/__init__.py` | NEW | Test package marker. |
| `tests/integration/authorization/test_mapper_resolve.py` | NEW | Database-backed resolution behaviour. |

Depends on, and must not re-create: `User.idp_subject` (Story 2.1), `ClaimsContract` / `read_identity_key` / `read_group_claim` (Story 2.2).

### Testing Requirements

- Test tree mirrors `src/` (spine, Consistency Conventions → Test location): `src/config/authorization/mapper.py` → `tests/unit/authorization/test_mapper_resolve.py` + `tests/integration/authorization/test_mapper_resolve.py`. Naming the file `..._resolve` leaves `..._sync` free for Story 2.5 and keeps AD-10's two operations visibly separate in the test tree too.
- `tests/integration/conftest.py` auto-applies `pytest.mark.integration` under `tests/integration/`. Database access still needs `@pytest.mark.django_db`.
- Integration tests leave state as found: the default `django_db` transaction rollback satisfies this. Avoid `transaction=True`.
- Override the claims contract per test through pytest-django's `settings` fixture (`settings.CLAIMS_CONTRACT = ClaimsContract(...)`) rather than through the environment — the contract is already materialized into settings by the time a test runs.
- Query-count assertion for AC #5: `django_assert_num_queries(1)` (pytest-django fixture). This is the only mechanical proof of AD-10's single-indexed-read property; a comment is not.
- `tests/factories.py`'s `UserFactory` sets `username`, `email`, `name` and a password, and uses `django_get_or_create = ["username"]`. It does **not** set `idp_subject`, which makes it exactly the right tool for seeding the "pre-existing user with a colliding username" fixture in AC #4.
- Coverage floor 90% including templates (AD-20), gate via `pixi run test-cov` inside `pixi run ci`. Add nothing to `[tool.coverage.run] omit`.

#### Project Structure Notes

`src/config/authorization/` is the spine's Structural Seed entry "the mapper (AD-10, AD-11, AD-12)". This story fills it. `src/config/startup/` remains absent and is Epic 4's.

Repository task names: `pixi run format` / `lint` / `typecheck` / `test` / `test-integration` / `test-cov` / `ci`. Pixi is the only runner. Python 3.14 only. Use `X | Y`, `list[X]`, `dict[K, V]`, `Mapping[str, Any]` — never `Union`/`List`/`Dict`.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-10]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-11]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-12]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-4]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.4]
- [Source: _bmad-output/planning-artifacts/epics.md:36] — FR-8
- [Source: _bmad-output/planning-artifacts/epics.md:328-337] — SC-6 is external
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/reviews/review-tech-verification.md:219] — allauth's `pre_social_login` (+ `sociallogin.connect`) is the correct hook for resolve-by-`idp_subject`; `populate_user` only decorates a new instance
- [Source: src/config/settings/base.py:175] — `django_structlog.middlewares.RequestMiddleware`, placed after `AuthenticationMiddleware`
- [Source: tests/factories.py] — `UserFactory`, `django_get_or_create = ["username"]`, no `idp_subject`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
