# Story 2.1: The user model carries the identity key

Status: ready-for-dev

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

- [ ] Task 1 — Add the field to `src/django_service/users/models.py` (AC: #1, #2)
  - [ ] Add `idp_subject = CharField(_("IdP subject"), max_length=255, unique=True, null=True, blank=True, default=None)` to `class User(AbstractUser)`, immediately after the existing `name` field.
  - [ ] Do **not** add `db_index=True`. `unique=True` already creates the index: Django's schema editor emits an explicit index only for `field.db_index and not field.unique`, so setting both produces one index and one redundant declaration. The "indexed" half of AC #1 is satisfied by `unique=True`.
  - [ ] Do **not** set `USERNAME_FIELD`, do not touch `REQUIRED_FIELDS`, and do not add a `UserManager` override. `USERNAME_FIELD` is inherited from `AbstractUser` as `"username"` and must stay that way (AD-11).
  - [ ] Leave `get_absolute_url()` resolving on `self.username` — `username` remains the URL attribute (AC #2).

- [ ] Task 2 — Generate and hand-check the schema migration (AC: #3)
  - [ ] Run `pixi run makemigrations users` and confirm the generated file is `src/django_service/users/migrations/0002_user_idp_subject.py` with a single `migrations.AddField`.
  - [ ] Confirm the operation carries `null=True` and `default=None` and therefore needs no `RunPython` backfill and asks no interactive default question.
  - [ ] Confirm no other operation was swept in — the file must contain exactly the one `AddField`. If `makemigrations` produced extra operations, revert and re-run; unrelated drift belongs in its own migration.
  - [ ] Apply and roll back once locally: `pixi run migrate` then `pixi run manage migrate users 0001` to prove the migration is reversible.

- [ ] Task 3 — Surface the field where it is safe to surface it (AC: #1, #2)
  - [ ] Add `idp_subject` to `UserAdmin.fieldsets` in `src/django_service/users/admin.py` under the `None` group, as a read-only entry via `readonly_fields = ["idp_subject"]`. It is an identity key, not an editable attribute; an operator editing it in the admin is account takeover.
  - [ ] Do **not** add it to `list_display`, `search_fields`, `UserAdminChangeForm` or `UserAdminCreationForm` in `src/django_service/users/forms.py`.
  - [ ] Do **not** add it to `UserSerializer` in `src/django_service/users/api/serializers.py`. The API exposes attributes; the identity key is not an attribute (AD-11).

- [ ] Task 4 — Tests (AC: #1, #2, #3)
  - [ ] Add `tests/unit/users/test_models.py` (new) asserting `User._meta.get_field("idp_subject")` has `unique is True`, `null is True`, `max_length == 255`, and that `User.USERNAME_FIELD == "username"`. These are field-introspection assertions and need no database.
  - [ ] Add cases to `tests/integration/users/test_models.py` (exists) asserting: a user created without `idp_subject` persists with `idp_subject is None`; two users may both hold `idp_subject=None` without violating the unique constraint; two users with the *same* non-null `idp_subject` raise `IntegrityError`.
  - [ ] Update `tests/factories.py` only if a test needs it — `UserFactory` must continue to produce users with `idp_subject` unset by default, so existing tests keep exercising the null case.
  - [ ] Run `pixi run test`, then `pixi run ci`.

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

### Debug Log References

### Completion Notes List

### File List
