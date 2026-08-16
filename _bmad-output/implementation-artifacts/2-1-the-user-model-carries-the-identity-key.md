---
baseline_revision: 58e2890
final_revision: 65da3d4
review_loop_iteration: 0
followup_review_recommended: true
status: done
warnings: []
---

# Story 2.1: The user model carries the identity key

Status: done

## Story

As a platform engineer,
I want a stable, indexed identity-key field on the user model,
so that an identity resolves to the same user no matter which flow saw them first.

## Acceptance Criteria

**Traceability:** AD-11 · supports FR-8

1. **Given** the user model today
   **When** this story lands
   **Then** `User.idp_subject` exists as a unique, indexed, nullable field
   **And** it is the sole store of the identity key

2. **Given** `USERNAME_FIELD`
   **When** the field is added
   **Then** it remains `username`
   **And** `username`, `email` and `name` remain attributes that are displayed and used in URLs but never resolved by

3. **Given** the migration adding the field
   **When** it runs against an existing database
   **Then** it applies without data loss
   **And** existing rows carry a null identity key until their next authentication

## Tasks / Subtasks

- [x] Task 1 — Add the field to `src/django_service/users/models.py` (AC: #1, #2)
  - [x] Add `idp_subject = CharField(_("IdP subject"), max_length=255, unique=True, null=True, blank=True, default=None)` to `class User(AbstractUser)`, immediately after the existing `name` field.
  - [x] Do **not** add `db_index=True`. `unique=True` already creates the index: Django's schema editor emits an explicit index only for `field.db_index and not field.unique`, so setting both produces one index and one redundant declaration. The "indexed" half of AC #1 is satisfied by `unique=True`.
  - [x] Do **not** set `USERNAME_FIELD`, do not touch `REQUIRED_FIELDS`, and do not add a `UserManager` override. `USERNAME_FIELD` is inherited from `AbstractUser` as `"username"` and must stay that way (AD-11).
  - [x] Leave `get_absolute_url()` resolving on `self.username` — `username` remains the URL attribute (AC #2).

- [x] Task 2 — Generate and hand-check the schema migration (AC: #3)
  - [x] Run `pixi run makemigrations users` and confirm the generated file is `src/django_service/users/migrations/0002_user_idp_subject.py` with a single `migrations.AddField`.
  - [x] Confirm the operation carries `null=True` and `default=None` and therefore needs no `RunPython` backfill and asks no interactive default question.
  - [x] Confirm no other operation was swept in — the file must contain exactly the one `AddField`. If `makemigrations` produced extra operations, revert and re-run; unrelated drift belongs in its own migration.
  - [x] Apply and roll back once locally: `pixi run migrate` then `pixi run manage migrate users 0001` to prove the migration is reversible.

- [x] Task 3 — Surface the field where it is safe to surface it (AC: #1, #2)
  - [x] Add `idp_subject` to `UserAdmin.fieldsets` in `src/django_service/users/admin.py` under the `None` group, as a read-only entry via `readonly_fields = ["idp_subject"]`. It is an identity key, not an editable attribute; an operator editing it in the admin is account takeover.
  - [x] Do **not** add it to `list_display`, `search_fields`, `UserAdminChangeForm` or `UserAdminCreationForm` in `src/django_service/users/forms.py`.
  - [x] Do **not** add it to `UserSerializer` in `src/django_service/users/api/serializers.py`. The API exposes attributes; the identity key is not an attribute (AD-11).

- [x] Task 4 — Tests (AC: #1, #2, #3)
  - [x] Add `tests/unit/users/test_models.py` (new) asserting `User._meta.get_field("idp_subject")` has `unique is True`, `null is True`, `max_length == 255`, and that `User.USERNAME_FIELD == "username"`. These are field-introspection assertions and need no database.
  - [x] Add cases to `tests/integration/users/test_models.py` (exists) asserting: a user created without `idp_subject` persists with `idp_subject is None`; two users may both hold `idp_subject=None` without violating the unique constraint; two users with the *same* non-null `idp_subject` raise `IntegrityError`.
  - [x] Update `tests/factories.py` only if a test needs it — `UserFactory` must continue to produce users with `idp_subject` unset by default, so existing tests keep exercising the null case.
  - [x] Run `pixi run test`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-11 (binding rule):** "**Identity key** is `User.idp_subject`: unique, indexed, nullable, populated from the claim the claims contract designates, and the sole store. The allauth adapter resolves through the mapper too; `SocialAccount` is bookkeeping, not authority. **Attribute** is `username`, `email`, `name` — populated from claims, displayed, used in URLs, never resolved by. `USERNAME_FIELD` remains `username`." *Prevents:* "account takeover through a mutable or collidable claim; the same person resolving to two users depending on which flow saw them first."
  - "Sole store" is the load-bearing phrase: no second column, no `SocialAccount.uid` read, no `UserProfile` mirror, no cache of the mapping. Anything that needs the identity key reads this field.
- **AD-5:** `django_service` is public API. Adding a field to the existing `User` model is additive and is **not** a breaking change; `AUTH_USER_MODEL` is unchanged. `django_service.__api_version__` does not exist in this repository yet (it arrives in Epic 9, Story 9.1), so there is nothing to bump.
- **AD-29:** every path inside `src/django_service/` is `core` in its entirety. Do not introduce any `feature:<name>` marker in the files this story touches.
- **AD-24 (what you must not do):** sub-file conditionality is only ever expressed with declared paired `feature:<name>` / `/feature:<name>` line-comment markers. No conditional imports, no `try/except ImportError`, no settings-module inheritance to make a field appear or disappear. This story needs none of those mechanisms; the note is here so none is reached for.
- **Nullability is deliberate and load-bearing.** Both PostgreSQL and SQLite permit multiple `NULL`s under a `UNIQUE` constraint, which is exactly what makes AC #3's "existing rows carry a null identity key until their next authentication" work without a data migration. Do not add a `UniqueConstraint` with a condition, do not add `blank=False`, and do not backfill.
- **Nothing resolves by this field yet.** Story 2.4 builds the mapper that reads it. This story is the schema change and nothing more. Do not add a `get_by_idp_subject` manager method here.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
|---|---|---|
| `src/django_service/users/models.py` | UPDATE | Today: `User(AbstractUser)` with `name = CharField(...)`, `first_name = None`, `last_name = None`, and `get_absolute_url()` reversing `users:detail` on `self.username` (27 lines). This story adds one field. **Preserve:** the `first_name`/`last_name` nulling with its `# type: ignore[assignment]` comments, the class docstring, and `get_absolute_url()` exactly as written. |
| `src/django_service/users/migrations/0002_user_idp_subject.py` | NEW | Single `migrations.AddField`, `dependencies = [("users", "0001_initial")]`. Generated, not hand-written. |
| `src/django_service/users/admin.py` | UPDATE | Today: flips `admin.site.login` through `secure_admin_login` when `settings.DJANGO_ADMIN_FORCE_ALLAUTH` (lines 11–15), then `UserAdmin(auth_admin.UserAdmin)` with `fieldsets`, `list_display`, `search_fields`. This story adds `idp_subject` to the first fieldset and a `readonly_fields` entry. **Preserve:** the `secure_admin_login` block untouched — Story 2.6 depends on it and changes its default separately. |
| `tests/unit/users/test_models.py` | NEW | Field-introspection assertions; no DB. |
| `tests/integration/users/test_models.py` | UPDATE | Exists. Add null-tolerance and uniqueness cases. |

Confirmed present before writing: `src/django_service/users/migrations/` contains only `__init__.py` and `0001_initial.py`, so `0002_` is the correct next number.

### Testing Requirements

- Test tree mirrors `src/` (spine, Consistency Conventions → Test location). `src/django_service/users/models.py` → `tests/unit/users/test_models.py` and `tests/integration/users/test_models.py`.
- `tests/integration/conftest.py` applies `pytest.mark.integration` automatically to every test collected under `tests/integration/`, via `pytest_collection_modifyitems`. You do **not** hand-decorate integration tests in this repository; adding the marker by hand is harmless but redundant.
- Database-touching tests need `@pytest.mark.django_db` (pytest-django), which is separate from the integration marker.
- Assertions the ACs demand, explicitly:
  - AC #1 — `unique is True`, `null is True` on the field; a second row with the same non-null value raises `django.db.utils.IntegrityError`.
  - AC #2 — `User.USERNAME_FIELD == "username"`; `reverse("users:detail", kwargs={"username": ...})` still resolves.
  - AC #3 — a `User` created through `UserFactory` (which sets no `idp_subject`) has `idp_subject is None`, and two such users coexist.
- Coverage floor is **90% including templates**, one global constant, never narrowed (AD-20). The gate task is `pixi run test-cov` (`--cov-fail-under=90`), reached through `pixi run ci`.
- Do not add anything to `[tool.coverage.run] omit` in `pyproject.toml`. AD-20 makes that list a closed declared surface; `*/migrations/*` is already omitted, so the new migration costs no coverage.

#### Project Structure Notes

Aligned with the spine's Structural Seed: `src/django_service/` is the platform base and is `core` in its entirety. This story adds no new directory. `src/config/authorization/` — where the mapper that consumes this field will live — does not exist yet and is **not** created by this story.

Repository task names differ from the generic harness names: this project uses `pixi run format`, `pixi run lint`, `pixi run typecheck`, `pixi run test`, `pixi run test-integration`, `pixi run test-cov`, and `pixi run ci` (which chains `test-cov`, `lint`, `typecheck`, `build`). Pixi is the only runner — never `pip`, `uv`, bare `python` or bare `pytest`.

Python 3.14 only. `[tool.mypy]` currently sets `check_untyped_defs`, not `strict`; Epic 1 Story 1.3 tightens it. Write fully annotated public signatures now so that change does not come back to this file.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-11]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-5]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.1]
- [Source: _bmad-output/planning-artifacts/implementation-readiness-report-2026-08-15.md] — "Story 2.1 is the thinnest; it stays separate because backfilling a nullable unique field against existing databases is a discrete migration risk worth its own review."
- [Source: src/django_service/users/models.py] — current model, 27 lines
- [Source: src/django_service/users/admin.py:11-15] — the `secure_admin_login` block this story must not disturb

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m]

### Debug Log References

- `pixi run makemigrations users` → `0002_user_idp_subject.py`, one `AddField`, no interactive default prompt.
- `pixi run migrate` → applied; `pixi run manage migrate users 0001` → unapplied cleanly; re-applied. Migration is reversible.
- `pixi run ci` → exit 0 (pre-commit, build, typecheck, lint, test-cov). 314 passed, coverage 92.50%.

### Completion Notes List

- `idp_subject` added immediately after `name`; no `db_index=True` (the `unique=True` index is the index), `USERNAME_FIELD`,
  `REQUIRED_FIELDS` and the `UserManager` untouched, `get_absolute_url()` unchanged.
- Admin surfaces the field in the `None` fieldset and pins it in `readonly_fields`; `list_display`, `search_fields`, both
  admin forms and `UserSerializer` were deliberately left alone.
- `UserFactory` unchanged — it still produces users with no identity key, so every pre-existing test keeps exercising the
  null case.
- Two lint accommodations, no config relaxation: `# noqa: SLF001` on the `User._meta` introspection calls and one
  `# noqa: PLR2004` on a count comparison (the repo's existing precedent, `tests/integration/test_request_logging.py:90`).
- The uniqueness-collision test wraps the failing create in `transaction.atomic()` so the broken transaction stays
  contained and the follow-up assertion still has a usable connection.

### File List

- `src/django_service/users/models.py` (UPDATE)
- `src/django_service/users/migrations/0002_user_idp_subject.py` (NEW, generated)
- `src/django_service/users/admin.py` (UPDATE)
- `tests/unit/users/test_models.py` (NEW)
- `tests/unit/users/test_migrations.py` (NEW, review pass)
- `tests/unit/users/test_api_serializers.py` (NEW, review pass)
- `tests/integration/users/test_models.py` (UPDATE)
- `tests/integration/users/test_admin.py` (UPDATE, review pass)

## Review Triage Log

### 2026-08-16 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 10: (high 0, medium 4, low 6)
- defer: 6: (high 0, medium 5, low 1)
- reject: 14: (high 0, medium 1, low 13)
- addressed_findings:
  - `[medium]` `[patch]` The read-only guarantee on `idp_subject` had no test — deleting `readonly_fields` left all 314 tests green while the change form became editable and POST-writable. Added `test_the_change_form_carries_no_editable_identity_key` and `test_the_change_view_ignores_a_posted_identity_key` to `tests/integration/users/test_admin.py`; verified by mutation (both fail with the line removed, the POST leg proving a real write).
  - `[medium]` `[patch]` AC #3's "applies without data loss" rested on a hand-run migrate recorded in prose. Added `tests/unit/users/test_migrations.py` pinning the operation shape — exactly one `AddField`, declared dependencies, `null=True`, `unique=True`, `max_length=255`, default `None` — so a later `RunPython` backfill cannot be added silently.
  - `[medium]` `[patch]` AC #1's "indexed" half was argued in a code comment and never read out of a database. Added `test_the_identity_key_is_unique_in_the_schema_not_only_the_model`, which queries `connection.introspection.get_constraints` for a unique index over the column on whichever backend is configured.
  - `[medium]` `[patch]` Task 3's "do not add it to `UserSerializer`" was satisfied by not typing anything. Added `tests/unit/users/test_api_serializers.py` asserting the API surface is exactly `{username, name, url}`, so a future `fields = "__all__"` cannot publish the identity key with a green suite.
  - `[low]` `[patch]` `test_many_users_may_share_a_null_identity_key` asserted a table-wide `count() == 2`, which any seeded or fixture-created user would break as a phantom uniqueness failure. Scoped to the two `pk`s the test creates (which also retires the `# noqa: PLR2004`).
  - `[low]` `[patch]` Both new integration tests drew usernames from an unseeded `Faker` under `django_get_or_create = ["username"]`; a repeated draw would return the existing row and turn the collision test into a false accusation against the constraint. Usernames are now explicit.
  - `[low]` `[patch]` The collision test's bare `pytest.raises(IntegrityError)` was equally satisfied by a duplicate username. It now asserts the error names `idp_subject`, matching the repo's own precedent at `tests/integration/test_postgres_schema.py:147-149`.
  - `[low]` `[patch]` Nothing asserted the identity key stays out of `list_display` and `search_fields`. Added `test_the_identity_key_is_not_a_lookup_surface`.
  - `[low]` `[patch]` The unit-test docstring for `USERNAME_FIELD` was ungrammatical and self-contradicting about which field is resolved by. Rewritten.
  - `[low]` `[patch]` `pixi run ci` runs `pre-commit run --all-files`, which enumerates `git ls-files` — both new files were untracked, so ruff-format and the hygiene hooks never saw them and the reported green gate was weaker than it read. Files staged and the gate re-run: all hooks pass on the new files.

Deferred entries were appended to `deferred-work.md`. The medium-severity reject is the single-column `UNIQUE` over `sub` with no issuer component: an OIDC subject is unique only within an issuer, so a component pointed at two IdPs could collide two people onto one row. Rejected rather than deferred because AD-11 binds the identity key to exactly this shape and Story 2.2's claims contract is where a composite value would be designated; it is recorded under residual risks below rather than dropped.

## Auto Run Result

Status: done

### Implemented change

`User.idp_subject` — a unique, nullable `CharField(max_length=255)` — is added to the user model as the sole store of the
identity key (AD-11), with the schema migration that carries it and the admin surface that displays it without letting
anyone edit it. `USERNAME_FIELD` remains `username`; nothing resolves by the new field yet, which is Story 2.4's work.

### Files changed

- `src/django_service/users/models.py` — adds `idp_subject` immediately after `name`, with the reasoning for no `db_index=True` and for load-bearing nullability recorded at the declaration.
- `src/django_service/users/migrations/0002_user_idp_subject.py` (NEW) — generated; a single `AddField` carrying `null=True`, so existing rows take a null key and no backfill runs.
- `src/django_service/users/admin.py` — surfaces the field in the first fieldset and pins it in `readonly_fields`; the `secure_admin_login` block and the `TYPE_CHECKING` shim are untouched.
- `tests/unit/users/test_models.py` (NEW) — field introspection: unique, null, `max_length`, no separate index, `USERNAME_FIELD`.
- `tests/unit/users/test_migrations.py` (NEW) — pins the migration's operation shape against a later silent backfill.
- `tests/unit/users/test_api_serializers.py` (NEW) — the identity key is not part of the REST surface.
- `tests/integration/users/test_models.py` — null tolerance, non-null collision, and the unique index read from the backend catalog.
- `tests/integration/users/test_admin.py` — the change form has no editable identity key, a crafted POST does not write one, and the field is not a lookup surface.

### Review findings

Ten patches applied (4 medium, 6 low), all test-level: the review changed no production code. Six items deferred to
`deferred-work.md` — `--reuse-db` hiding new migrations from developer databases, the missing `makemigrations --check`
drift guard, `UserAdminChangeForm` inheriting `fields = "__all__"`, the untested `""`-versus-`NULL` pseudo-key,
the concurrent-first-authentication race Story 2.4 inherits, and the missing over-length boundary test. Fourteen
findings rejected, mostly arguments against decisions the spec makes explicitly (`default=None`, no `db_index`, no
`CheckConstraint`, no searchability, generated-migration formatting).

### Verification

- `pixi run ci` → exit 0 with every file staged so pre-commit saw them: all hooks pass, build OK, `mypy src/` clean on 38 files, `ruff check .` clean, **323 passed**, coverage **92.50%** against the 90% floor.
- `pixi run manage makemigrations --check --dry-run` → "No changes detected": the model and the migrations agree.
- `pixi run manage sqlmigrate users 0002 --backwards` → produces a clean table rebuild; the migration reverses.
- Mutation check: removing `readonly_fields = ["idp_subject"]` fails exactly the two new admin tests and nothing else, confirming they guard the line rather than restate it.
- Migration applied and rolled back against a live database during implementation (`pixi run migrate`, `pixi run manage migrate users 0001`, re-applied).

### Residual risks

- **One column, no issuer.** The `UNIQUE` is over the subject alone. An OIDC `sub` is unique only within an issuer, so a component ever pointed at two IdPs collides two people onto one row — the failure AD-11 exists to prevent, reached from the other side. Story 2.2 designates which claim fills the field and is the place to decide whether that value must be composite.
- **`""` is not `NULL`.** Nothing yet stops an empty string being stored as a pseudo-key that collides on its second write. Deferred, and Story 2.4's mapper must normalize before writing.
- **Nothing writes the field yet.** Every guarantee here is schema-level; the resolution semantics AD-11 actually cares about arrive with the mapper in Story 2.4.
- **AC #2's "never resolved by" is only partly assertable today.** `USERNAME_FIELD` and the URL attribute are pinned; the absence of any resolution path over `email`/`name` cannot be asserted until a resolver exists.
