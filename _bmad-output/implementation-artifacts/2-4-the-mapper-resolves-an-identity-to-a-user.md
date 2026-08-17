---
baseline_revision: 3edb9fb
review_loop_iteration: 0
followup_review_recommended: true
status: done
final_revision: f81ca7f
warnings: []
---

# Story 2.4: The mapper resolves an identity to a user

Status: done

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

- [x] Task 1 — Declare the mapper's failure type at `src/config/authorization/exceptions.py` (AC: #1)
  - [x] `class ClaimsRejected(Exception)` with a `reason: str` attribute. This is the mapper's one refusal signal; callers translate it to HTTP status.
  - [x] The mapper must never import `rest_framework` or raise `AuthenticationFailed` directly. The DRF Bearer class (Story 2.7) and the allauth adapter (Story 2.6) each translate `ClaimsRejected` into their own protocol's 401. Keeping DRF out of the mapper is what lets the same mapper serve the interactive flow, the Bearer flow and Epic 3's local sign-in route.

- [x] Task 2 — Implement `resolve_user` in `src/config/authorization/mapper.py` (AC: #1, #2, #3, #5)
  - [x] Signature: `def resolve_user(claims: Mapping[str, Any]) -> User`. Full type hints; Google-style docstring stating the AD-10 frequency contract ("runs on every authentication, including every Bearer request; one indexed read").
  - [x] Read the identity key with `read_identity_key(claims, settings.CLAIMS_CONTRACT.identity_key_claim)` from Story 2.2. A missing or empty identity key raises `ClaimsRejected("identity key claim absent")`.
  - [x] The lookup is **exactly one query**: `User.objects.filter(idp_subject=subject).first()`. Not `get()` inside `try/except User.DoesNotExist` (same query count, worse control flow), not `get_or_create` (two queries plus a write attempt on the hot read path), and not a `select_related` or `prefetch_related` of groups — sync loads groups, resolve does not.
  - [x] On a hit, return the user immediately. Do **not** write attributes on the resolve path; attribute reconciliation belongs to Task 3 and runs only when something actually changed.
  - [x] On a miss, create the user inside `transaction.atomic()` with `idp_subject=subject`, an unusable password (`user.set_unusable_password()`), and attributes derived per Task 3. A deployed component authenticates nobody locally, so no user the mapper creates may ever carry a usable password.

- [x] Task 3 — Implement attribute population and the username-collision rule (AC: #1, #3, #4)
  - [x] `def _attributes_from_claims(claims) -> dict[str, str]` pulling `username`, `email`, `name` from the standard OIDC claim names (`preferred_username`, `email`, `name`), falling back to the identity key when `preferred_username` is absent.
  - [x] `email` is written unconditionally and is **never** part of any lookup. `AbstractUser.email` is not unique in this model, so two identities with the same email produce two rows with no constraint conflict — that is AC #3 satisfied structurally rather than by a code branch. Do not add a uniqueness constraint on `email`.
  - [x] `username` is written only when the desired value is free. Before writing, check `User.objects.filter(username=desired).exclude(pk=user.pk).exists()`. If it exists, **do not write it**: emit `structlog` event `authorization.username_collision` at warning with `idp_subject`, `desired_username` and `held_by_idp_subject`, and leave the user's current username in place. That is AC #4's "refused and logged … keeps its existing username and authenticates normally" and AD-12's "Prevents … an `IntegrityError` mid-authentication."
  - [x] For a **first sighting** whose desired username is already taken, the user still has to be created with *some* username, and it must be deterministic and collision-free. Derive it from the identity key — e.g. a stable, truncated, sanitized rendering of `idp_subject` — and log the same collision event. Never append a random suffix or a counter: a non-deterministic username makes AC #2's "resolves to the same user in both orders" test flaky and makes the collision unreproducible in support.
  - [x] Save with `user.save(update_fields=[...])` listing only the fields that actually changed, and skip the save entirely when nothing changed. Resolve on a Bearer request must not write.

- [x] Task 4 — Prove the single-read property, do not merely assert it in prose (AC: #5)
  - [x] Write the resolve path so that the hit case issues exactly one `SELECT`. Verify it with `django.test.utils.CaptureQueriesContext` or pytest-django's `django_assert_num_queries` fixture.
  - [x] AD-10's stated purpose is preventing "`auth_user_groups` write amplification on every API call". A resolve that touches `user.groups` — even to read — defeats it. Do not.

- [x] Task 5 — Tests (AC: #1, #2, #3, #4, #5)
  - [x] `tests/unit/authorization/test_mapper_resolve.py` (new) — claim-extraction and username-derivation behaviour that needs no database: `ClaimsRejected` on an absent identity claim; deterministic derived username for the same `idp_subject` across repeated calls.
  - [x] `tests/integration/authorization/__init__.py` and `tests/integration/authorization/test_mapper_resolve.py` (new, `@pytest.mark.django_db`):
    - AC #1 — an identity whose `email` and `preferred_username` both match an existing user, but whose `idp_subject` differs, resolves to a **new** user, not the existing one.
    - AC #2 — call `resolve_user` twice with the same `idp_subject` and different attribute claims, in both orders (interactive-shaped claims first then Bearer-shaped, and the reverse), asserting the same `pk` both times. The AC says "a test asserts this in both orders" — write both directions explicitly, not one parameterized case that only covers one.
    - AC #3 — two identities with identical `email` claims and distinct `idp_subject`s produce two distinct users.
    - AC #4 — seed user A with `username="ada"` and `idp_subject="A"`; resolve claims with `idp_subject="B"` and `preferred_username="ada"`; assert B is created, B's username is not `"ada"`, A's username is still `"ada"`, both authenticate, and the collision event was emitted.
    - AC #5 — `django_assert_num_queries(1)` around a resolve of an existing identity.
  - [x] Capture structlog events with `structlog.testing.capture_logs()` to assert the collision event rather than asserting on captured stdout.
  - [x] Run `pixi run test`, `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-10 (binding rule — the resolve half only):** "**Resolve** takes claims and returns the user by the identity key. It runs on every authentication, including every Bearer request, and is a single indexed read." *Prevents:* "the only two outcomes of conflating them — `auth_user_groups` write amplification on every API call, or stale authorization."
  - **Do not implement sync in this story.** Group diffing, `is_staff`/`is_superuser`, the epoch record, the `jti` rule and the transaction are all Story 2.5. AD-10 exists precisely because the two get conflated; a `resolve_user` that also syncs is the failure this AD is written to prevent. Keep them separate functions in the same module.
- **AD-11 (binding rule):** "**Identity key** is `User.idp_subject`: unique, indexed, nullable, populated from the claim the claims contract designates, and the sole store. The allauth adapter resolves through the mapper too; `SocialAccount` is bookkeeping, not authority. **Attribute** is `username`, `email`, `name` — populated from claims, displayed, used in URLs, **never resolved by**." *Prevents:* "account takeover through a mutable or collidable claim; the same person resolving to two users depending on which flow saw them first."
  - "Never resolved by" is absolute. No `User.objects.get(email=...)` fallback, no "look up by username if `idp_subject` is null" convenience, no `SocialAccount.objects.get(uid=...)` read. The nullable `idp_subject` on pre-existing rows (Story 2.1 AC #3) means those rows are simply not resolvable until they authenticate — which is the intended behaviour, not a gap to patch.
- **AD-12 (binding rule):** "A `username` collision between two distinct `idp_subject`s is refused and logged; the second identity keeps its existing username and authenticates normally." *Prevents:* "a misconfiguration presenting as a permissions bug; IdP group taxonomy silently becoming Django taxonomy; an `IntegrityError` mid-authentication."
- **FR-8:** "One shared mapper at `src/config/authorization/` owns all authorization decisions, resolving users by one designated identity-key claim." One mapper. The DRF class, the allauth adapter and the local sign-in route are all *callers*; none may contain resolution logic of its own — Stories 2.6 and 2.7 each carry an explicit AC to that effect.
- **AD-4:** `config` may import `django_service`, so `config.authorization.mapper` importing `django_service.users.models.User` is legal and expected. Prefer `django.contrib.auth.get_user_model()` at call time over a module-level import of the concrete class, so the mapper does not pin `AUTH_USER_MODEL`.
- **AD-24 (what you must not do):** no conditional imports, no `try/except ImportError`, no settings-module inheritance. The mapper is `core` and present in all six combinations.
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
- [Source: _bmad-output/planning-artifacts/epics.md:330-339] — SC-6 is external
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/reviews/review-tech-verification.md:219] — allauth's `pre_social_login` (+ `sociallogin.connect`) is the correct hook for resolve-by-`idp_subject`; `populate_user` only decorates a new instance
- [Source: src/config/settings/base.py:175] — `django_structlog.middlewares.RequestMiddleware`, placed after `AuthenticationMiddleware`
- [Source: tests/factories.py] — `UserFactory`, `django_get_or_create = ["username"]`, no `idp_subject`

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m]

### Debug Log References

`pixi run test` (346 passed) -> `pixi run test-integration` (95 passed, 6 skipped)
-> `pixi run ci` (exit 0; 447 passed, total coverage 93.89%, both new modules at
100%). The gate's sqlite run was repeated against the local PostgreSQL 17
(`DATABASE_URL=postgres://.../app_test`, `--create-db`): 441 passed, 6 skipped,
no divergence. Two ruff findings were fixed on the way (PLR2004 magic values in
the count assertions, S105 on a test-local claim value named `secret_ish`); no
error signature repeated.

### Completion Notes List

- Resolution is by `idp_subject` alone. The hit path is
  `User.objects.filter(idp_subject=subject).first()` and returns immediately --
  no attribute write, no group touch -- which is what
  `test_resolving_an_existing_identity_is_a_single_query` and
  `test_the_single_read_holds_when_the_attribute_claims_have_changed` assert with
  `django_assert_num_queries(1)`.
- Sync is **not** implemented here (AD-10). `mapper.py` holds `resolve_user` and
  its private helpers only; `sync_authorization` / `sync_once_per_epoch` are
  Story 2.5's and land in this same module.
- The mapper imports no `rest_framework` and raises only `ClaimsRejected`.
- Username collisions are refused and logged at warning
  (`authorization.username_collision`, carrying `idp_subject`,
  `desired_username`, `held_by_idp_subject`), never raised as `IntegrityError`.
  The replacement name is `idp-<sha256(subject)[:32]>` -- deterministic, no
  random suffix and no counter.
- Two deliberate deviations from the task text, both narrowing rather than
  widening what the story asks for. (1) `_attributes_from_claims` takes the
  already-read `subject` as a second parameter so the identity-key fallback does
  not re-read the claim. (2) The collision check is
  `filter(username=desired).exclude(pk=user.pk).values("idp_subject").first()`
  rather than `.exists()`: it is the same single query, and `.exists()` cannot
  produce the `held_by_idp_subject` the same bullet requires in the event.
- SC-6 is untouched and uncloseable here: every assertion runs against synthetic
  claim dictionaries, which does not prove a real IdP identity authenticating
  through both flows.

### File List

- `src/config/authorization/exceptions.py` (new)
- `src/config/authorization/mapper.py` (new)
- `tests/unit/authorization/test_mapper_resolve.py` (new)
- `tests/integration/authorization/__init__.py` (new)
- `tests/integration/authorization/test_mapper_resolve.py` (new)

### Review Patches (adversarial review, five findings triaged `patch`)

Applied to `src/config/authorization/mapper.py` and both test modules. Every
patch carries a test that was verified to fail against the pre-patch mapper.

- **P1 — every claim-derived value is bounded and valid.** A claim-supplied
  `preferred_username` now goes through the same renderer the identity-key
  fallback always used (`_sanitized_username`), and `email` and `name` are
  truncated to their fields. An identity key longer than `idp_subject` is a
  refusal (`ClaimsRejected`), not a `DataError` mid-authentication -- refused
  rather than truncated, because a truncated key is a different identity. Every
  bound is read from the user model's own field (`_field_max_length`, `None` for
  an unbounded field) rather than from a hardcoded 150, which had pinned
  `AUTH_USER_MODEL` that `get_user_model()`-at-call-time exists to leave open.
  `USERNAME_MAX_LENGTH` is therefore gone; the tests read the field instead of
  the constant, so drift between the two is detectable.
- **P2 — no `IntegrityError` escapes the create path.** `_available_username`
  now checks a deterministic *list* of candidates -- the asked-for name, the
  digest form, the identity key's own rendering -- in one query, so the derived
  name is no longer returned unchecked (and the forgeable derived namespace can
  no longer deny an identity its first sighting). Out of candidates is
  `ClaimsRejected` with a logged event, never an overwrite, never a random
  suffix or counter, never an `IntegrityError`. The insert is wrapped in an
  inner `transaction.atomic()` savepoint (`ATOMIC_REQUESTS` is on, so a broken
  outer transaction could not serve the recovery read): a unique violation is
  resolved by re-reading `idp_subject` -- a concurrent first sighting of the
  same identity returns *that* user, which is AC #2 holding under a race -- and
  a username violation becomes `ClaimsRejected`.
- **P3 — `authorization.user_created` is observed.** Two integration tests: a
  first sighting emits exactly one, carrying `idp_subject`; a hit emits none.
  Deleting the log call now fails the suite (verified).
- **P4 — integer identity keys are exercised through the mapper.** The one
  non-string subject type `read_identity_key` supports now resolves end to end,
  including through `_username_from_identity_key`'s `subject.encode()`.
- **P5 — `resolve_user`'s `Raises:` section** names all three refusal reasons,
  which is the contract Stories 2.6 and 2.7 translate into their 401.

Gate after the patches: `pixi run ci` exit 0, 468 passed, total coverage 94.14%,
`mapper.py` at 100%. Because P1 and P2 are about failures SQLite cannot see, the
suite was also run against local PostgreSQL 17
(`DATABASE_URL=postgres://.../app_test --create-db`): 462 passed, 6 skipped, no
divergence. Against the *pre-patch* mapper the same PostgreSQL run produced
`DataError: value too long for type character varying(150)`,
`character varying(255)`, and
`IntegrityError: duplicate key value violates unique constraint "users_user_username_key"`
-- the failures the gate's SQLite silently absorbed. AC #5's three
`django_assert_num_queries(1)` tests still pass: nothing was added to the hit
path, and the candidate check is still one query on the create path.

## Spec Change Log

### 2026-08-16 — Task 2 / Task 3 contradiction, resolved in favour of the ACs

No section was amended; the contradiction is recorded here rather than edited
away, because the acceptance criteria already settle it and rewriting the task
list after the fact would hide that a reader had to settle anything.

Task 2 says "on a hit, return the user immediately. Do **not** write attributes
on the resolve path." Task 3's last bullet says "Save with
`user.save(update_fields=[...])` listing only the fields that actually changed,
and skip the save entirely when nothing changed." Read together they describe
two different functions: one that never writes on a hit, and one that reconciles
an existing user's attributes when the claims have changed.

AC #5 decides it. "Resolution runs on every authentication including every
Bearer request … it is a single indexed read" is not satisfiable by any
implementation that reads the row, compares three attributes and conditionally
writes — the comparison is free but the `UPDATE` is not, and AD-10's stated
purpose is preventing write amplification on exactly that path. So attribute
population and the collision rule run on the **create** path only, and Task 3's
`update_fields` bullet has no reachable call site in this story.

That bullet is not dead weight for Story 2.5: sync already has a write path and
a transaction, and reconciling attributes there costs nothing extra. The helper
was written to work for a saved user as well as an unsaved one specifically so
2.5 can call it unchanged. Story 2.5 should pick up attribute reconciliation.

## Review Triage Log

### 2026-08-16 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 6: (high 2, medium 1, low 3)
- defer: 1: (high 0, medium 1, low 0)
- reject: 16: (high 0, medium 0, low 16)
- addressed_findings:
  - `[high]` `[patch]` Every claim-derived value reached the database unbounded and unsanitized. A reviewer stored a 200-character `preferred_username` and a 306-character `email` against a live database, and `preferred_username="ada/lovelace"` was written verbatim — after which `get_absolute_url()` raised `NoReverseMatch` for `users:detail` and `UnicodeUsernameValidator` rejected the stored name. The gate could not see any of it: `pixi run ci` runs on SQLite, which ignores varchar limits. Fixed by routing a claim-supplied username through the same sanitize-and-truncate the identity-key fallback always had, bounding `email`/`name` to their columns, refusing an over-long identity key with `ClaimsRejected` rather than letting it become a `DataError`, and replacing the hardcoded `USERNAME_MAX_LENGTH = 150` with lengths read from the model's own `_meta` — the module calls `get_user_model()` at call time precisely so it does not pin `AUTH_USER_MODEL`, and a literal 150 pinned it back. Tests assert against the field length, never against the constant the production code used.
  - `[high]` `[patch]` The create path could raise `IntegrityError` mid-authentication — the one outcome AD-12 and the module docstring both promise never happens. `_available_username` returned `_derived_username(subject)` without checking it was free; a reviewer reproduced the crash by seeding a row holding the derived name. Because the derivation is a pure function of the subject, the namespace is also forgeable: one identity could squat the name another identity's first sighting would derive and deny it authentication. Separately, `filter().first()`-then-insert races itself on a concurrent first sighting of one subject, against a `unique` `idp_subject`. Fixed with a deterministic candidate list resolved in one query, `ClaimsRejected` (logged) when every candidate is taken, and an inner `transaction.atomic()` savepoint whose unique-violation recovery re-reads by `idp_subject` — so a lost race returns the winner's user, which is AC #2 holding under concurrency. No random suffix, no counter; determinism is what AC #2's both-orders assertion rests on.
  - `[medium]` `[patch]` `authorization.user_created` was emitted and observed by nothing — `grep` matched only the mapper, and every collision assertion filtered for `authorization.username_collision`, so deleting the creation log left the suite green. The spine requires every authorization change to emit an event and a new principal existing is one. Now asserted on both sides: exactly one event on a first sighting, none on a hit.
  - `[low]` `[patch]` Integer identity keys crossed the module boundary unexercised. `read_identity_key` deliberately stringifies non-boolean integers ("numeric subjects … occur"), but the mapper's suite parametrized `None`, `""`, `"   "` and `True` and never an int. Added, end to end and through `_username_from_identity_key`'s `subject.encode()`.
  - `[low]` `[patch]` `resolve_user`'s `Raises:` documented one refusal reason while the function grew three. Stories 2.6 and 2.7 translate this exception into their protocol's 401, so the docstring is the contract they will be written against.
  - `[low]` `[patch]` The Task 2 / Task 3 contradiction over attribute reconciliation was resolved silently by the implementation and absent from its declared deviations. Recorded in the Spec Change Log above rather than left implicit; no code change — AC #5 forbids the alternative.

Deferred: `is_active` is not consulted anywhere in resolution, and the mapper
states no contract for it. Filed against Story 2.7, which must not be written
before the placement is decided.

Rejected as noise: fifteen findings, all low. The recurring shapes were style
preferences the repository does not hold (a `NamedTuple` for a three-key dict,
`get_user_model()` called more than once), critiques of code the spec mandates
verbatim (`transaction.atomic()` on the create, `exclude(pk=user.pk)`), and
observations that are true but owned elsewhere (`django_assert_num_queries`
proves "one query" and not "one *indexed* query" — the index is Story 2.1's
`unique=True`, tested there).

## Auto Run Result

Status: done

### What was implemented

The resolve half of the mapper (AD-10), and only that half. `resolve_user`
takes claims and returns the user the identity key designates: one indexed read
on `User.idp_subject`, no writes, no group access, no `rest_framework` import.
A miss creates the user with an unusable password and attributes derived from
the standard OIDC claims, under AD-12's collision rule. Sync — group diffing,
`is_staff`/`is_superuser`, the epoch record — is deliberately absent and is
Story 2.5's; AD-10 exists because the two get conflated.

### Files changed

| Path | Change |
|---|---|
| `src/config/authorization/exceptions.py` | NEW — `ClaimsRejected`, the mapper's one protocol-free refusal signal |
| `src/config/authorization/mapper.py` | NEW — `resolve_user`, attribute population, the deterministic username-collision rule, field-length bounds and unique-violation recovery |
| `tests/unit/authorization/test_mapper_resolve.py` | NEW — claim extraction, username derivation and bounding, no database |
| `tests/integration/authorization/__init__.py` | NEW — test package marker |
| `tests/integration/authorization/test_mapper_resolve.py` | NEW — database-backed resolution, all five ACs |

`src/config/authorization/__init__.py` was left as the docstring-only package
marker the Source Tree table requires.

### Review findings

Six patched (two high, one medium, three low), one deferred, sixteen rejected.
Full detail in the triage log above.

### Verification

- `pixi run ci` — exit 0. 468 passed, total coverage 94.14% against a 90% floor;
  `mapper.py` and `exceptions.py` at 100%. Nothing added to
  `[tool.coverage.run] omit`.
- PostgreSQL 17, whole suite with `--create-db` — 462 passed, 6 skipped, no
  divergence from the SQLite run. Run because two of the patched defects were
  `DataError`/`IntegrityError` failures SQLite cannot express; against the
  pre-patch mapper this same run reproduced all three.
- AC #5's three `django_assert_num_queries(1)` tests pass after the patches. The
  hit path gained only an in-memory `_meta` length check.

### Residual risks

- **SC-6 is not closed and cannot be closed here.** Every assertion runs against
  synthetic claim dictionaries. Proving a real IdP identity authenticates
  through both flows is an external exit criterion owned by the platform group,
  after Epic 2.
- **`is_active` is unconsulted** — see the deferred entry. The interactive flow
  is covered by `ModelBackend.user_can_authenticate`; the Bearer path will not
  be until Story 2.7 decides where the check belongs.
- **Concurrent first sighting is handled but not tested under real concurrency.**
  The `IntegrityError` recovery is exercised by forcing the conflict
  deterministically rather than with threads, so the recovery logic is verified
  and the race window itself is not.
