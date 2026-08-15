# Story 2.3: The designated groups exist before the first authentication

Status: ready-for-dev

## Story

As a lead developer,
I want the designated groups and their permissions provisioned by the component,
so that the first administrator can be established by claim rather than deadlocking on an admin nobody can reach.

## Acceptance Criteria

**Traceability:** FR-11 · AD-27 · SC-6

1. **Given** the claims contract names a staff group and a superuser group
   **When** the component migrates
   **Then** a data migration inside `django_service` creates those `Group` rows and attaches their `Permission` rows
   **And** it is seeded from the claims contract rather than from hardcoded names

2. **Given** the migration has already run
   **When** it runs again
   **Then** it is idempotent and creates no duplicates

3. **Given** any other path that needs those groups
   **When** it runs
   **Then** it calls this same provisioning mechanism
   **And** no path creates groups of its own

4. **Given** the deployed bootstrap path
   **When** it is documented
   **Then** the documentation states that the first administrator is established by IdP group claim
   **And** that `createsuperuser` remains available only where the refusals do not apply

## Tasks / Subtasks

- [ ] Task 1 — Write the single provisioning mechanism at `src/django_service/users/provisioning.py` (AC: #1, #2, #3)
  - [ ] `def provision_designated_groups(apps: StateApps | Apps | None = None) -> ProvisionResult` — the one callable. `apps=None` means "use the live registry" (`django.apps.apps`); a migration passes its historical registry. This dual signature is what lets the migration and Epic 3's persona seeding share one implementation, which AC #3 requires.
  - [ ] Read the four names from `django.conf.settings.CLAIMS_CONTRACT` (Story 2.2). Do **not** import `config.authorization.claims` — AD-4 forbids `django_service` importing `config`. `settings` is the legal seam and the only one.
  - [ ] If `settings.CLAIMS_CONTRACT.is_configured` is False, return an empty `ProvisionResult` and emit one `structlog` warning event `authorization.provisioning_skipped`. **Do not raise** — a migration that raises on an unconfigured contract makes `pixi run migrate` unusable during bring-up, and the refusal for an unconfigured contract is Epic 4's stage 1.
  - [ ] For each of `staff_group` and `superuser_group`: `Group.objects.get_or_create(name=...)`, then `group.permissions.set(...)` from the declared permission set. `get_or_create` + `set` is what makes AC #2's idempotence structural rather than a re-run guard.
  - [ ] Return a small frozen dataclass `ProvisionResult(created: tuple[str, ...], existing: tuple[str, ...], permissions_attached: int)` so callers can log what happened without re-querying.

- [ ] Task 2 — Declare the permission set beside the mechanism (AC: #1)
  - [ ] In the same module, `DESIGNATED_GROUP_PERMISSIONS: dict[str, tuple[str, ...]]` keyed by the **role slot** (`"staff"`, `"superuser"`), never by group name — the names come from the environment and cannot appear in source (AC #1's "seeded from the claims contract rather than from hardcoded names").
  - [ ] `"staff"` maps to the `app_label.codename` strings a staff member needs to reach a useful admin index: `("users.view_user", "users.change_user")`. Keep it minimal and comment why each is there.
  - [ ] `"superuser"` maps to `()`. Django's `ModelBackend.has_perm` short-circuits on `is_superuser`, so attaching permissions to the superuser group is noise that will drift. State that in the comment.
  - [ ] Resolve each string to a `Permission` row by splitting on `.` and querying `Permission.objects.filter(content_type__app_label=..., codename=...)`. A codename that resolves to nothing is **logged and skipped**, never created — the same discipline AD-12 applies to unknown group claims.

- [ ] Task 3 — Handle the permissions-do-not-exist-yet trap in the migration (AC: #1, #2)
  - [ ] `Permission` rows are created by the `post_migrate` signal, **not** by a migration. A data migration that runs during the same `migrate` invocation that creates the models will find `auth_permission` empty for those models and silently attach nothing.
  - [ ] In the migration's forward function, call `django.contrib.auth.management.create_permissions(app_config, apps=apps, verbosity=0)` for the `users` app config **before** calling `provision_designated_groups(apps)`. Guard it by clearing `app_config.models_module = None` after, per Django's own documented workaround for this ordering.
  - [ ] Do this in the migration only. `provision_designated_groups` itself must not call `create_permissions` — on the live path (Epic 3's persona seeding) the permissions already exist, and calling it there would be a write on a read path.

- [ ] Task 4 — Write the data migration at `src/django_service/users/migrations/0003_provision_designated_groups.py` (AC: #1, #2)
  - [ ] `dependencies = [("users", "0002_user_idp_subject"), ("auth", "0012_alter_user_first_name_max_length"), ("contenttypes", "0002_remove_content_type_name")]` — `auth` and `contenttypes` because the forward function touches `Group`, `Permission` and `ContentType`.
  - [ ] `operations = [migrations.RunPython(forward, reverse, elidable=False)]`.
  - [ ] `forward(apps, schema_editor)` calls `create_permissions` (Task 3) then `provision_designated_groups(apps)`.
  - [ ] `reverse(apps, schema_editor)` deletes only the two `Group` rows the contract names, and only if they exist. It must not delete permissions or users.
  - [ ] Import `provision_designated_groups` inside the function body, not at module top — a migration module that imports application code at import time couples the migration graph to whatever that module imports.

- [ ] Task 5 — Document the deployed bootstrap path (AC: #4)
  - [ ] Create `docs/authentication.md`. Sections: *How an identity becomes a user*; *How the first administrator is established*; *The four claims-contract environment variables*; *`createsuperuser` and where it is still available*.
  - [ ] State in the first-administrator section, in these terms: the first administrator is established by **IdP group claim** — an identity whose claims assert the configured superuser-conferring group receives `is_superuser` on its next authentication. No one runs `createsuperuser` against a deployed component.
  - [ ] State that `createsuperuser` remains available **only where the refusals do not apply** — that is, local development. Name the existing `pixi run createsuperuser` task and say it is a local convenience. Mark the refusal itself as Epic 4's work.
  - [ ] Add `- Authentication: authentication.md` to the `nav:` list in `mkdocs.yml`, after `Development`. `pixi run docs` builds with `--strict`, so a page absent from the nav fails the build.

- [ ] Task 6 — Tests (AC: #1, #2, #3)
  - [ ] `tests/unit/users/test_provisioning.py` (new) — assert `DESIGNATED_GROUP_PERMISSIONS` is keyed by role slot and contains no group *names*; assert that a `ProvisionResult` from an unconfigured contract is empty and raises nothing.
  - [ ] `tests/integration/users/test_provisioning.py` (new, `@pytest.mark.django_db`) — call `provision_designated_groups()` twice against a live database and assert `Group.objects.filter(name=...).count() == 1` for each after the second call (AC #2); assert the staff group's permission set matches the declaration; assert a contract naming different group names produces those names and not any hardcoded string (AC #1).
  - [ ] Assert the migration itself is idempotent by running the forward function twice through `django_test_migrations`-style manual invocation, or — simpler and sufficient — by asserting `provision_designated_groups` is the only writer and testing it directly. Do not add a new dependency for this.
  - [ ] Add a test that greps the repository for a second group-creating call site: assert that `Group.objects.create` and `Group.objects.get_or_create` appear in `src/` **only** inside `src/django_service/users/provisioning.py` (AC #3's "no path creates groups of its own"). A source-text assertion is legitimate here because the property is about authorship, not behaviour.
  - [ ] Run `pixi run test`, `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-27 (binding rule):** "Django `Group` rows named by the claims contract, and the `Permission` rows attached to them, are provisioned by a data migration inside `django_service`, seeded from the claims contract, so they exist before the first authentication. The local persona seeding task **calls that same mechanism** rather than reimplementing it — a task that creates groups itself is what makes the deadlock invisible to the harness. A designated staff or superuser group absent from the database at startup is a stage-2 refusal condition, on AD-12's own reasoning: a misconfiguration must not present as a permissions bug." *Prevents:* "the bootstrap deadlock in which every deployed component grants nobody any authorization and nobody can reach the admin, while every local smoke check passes."
  - "Calls that same mechanism" is why Task 1's callable takes an optional `apps` registry. Epic 3 Story 3.3 will call it; Epic 8's smoke check runs behind it. If you implement provisioning inline in the migration file, Story 3.3 has nothing to call and will reimplement it — which is the exact failure AD-27 names.
- **AD-12 (binding rule, the half this story guarantees):** "A claim asserting a group with no matching Django `Group` is ignored and logged, never created — **which is safe only because AD-27 guarantees the designated groups exist.**" Story 2.5's ignore-and-log rule is only defensible because this story runs. Treat that dependency as real.
- **AD-4 (dependency direction):** "A tenant app may import `django_service`. `django_service` may never import a tenant app. `config` may import `django_service`." `django_service` importing `config` would invert the declared direction and create a cycle with `config.settings.base`, which imports `config.authorization.claims`. Read the contract off `django.conf.settings` and nowhere else.
- **AD-29:** `src/django_service/` is `core` in its entirety — no `feature:*` disposition may be applied to any path inside it, asserted by a gate test. Both new files are unconditional core.
- **AD-24 (what you must not do):** no conditional imports, no `try/except ImportError`, no settings-module inheritance to make provisioning appear or disappear.
- **FR-11 (binding rule):** "Superuser creation is retired as the deployed bootstrap path; staff and superuser are group-driven and the designated groups are provisioned by the component." Note the scope: *retired as the deployed bootstrap path*, not deleted. The `createsuperuser` pixi task stays; the documentation states where it is legitimate and Epic 4 refuses the paths that would make it a credential surface.
- **Spine, Consistency Conventions → Logging:** "Structured, JSON to stdout, carrying `request_id`, `trace_id`, `span_id`. **Every authorization change emits an event.**" Provisioning is an authorization change. Emit `authorization.groups_provisioned` with the created/existing names and the permission count. Never `print()`. Never stdlib `logging`. `structlog` only.
- **Spine, Consistency Conventions → Runtime errors:** "Nothing is swallowed silently." Never a bare `except:`, never `except X: pass`. A missing permission codename is logged at warning and skipped — that is handled, not swallowed.

### SC-6 cannot be closed here

This story's `**Requirements:**` line names SC-6, but **SC-6 cannot be closed in this repository.** The epics document is explicit: a local identity-provider container is a PRD non-goal, and "Epic 2 can pass every story's acceptance criteria against unit tests with mocked JWKS and claims while SC-6 remains unproven." Owner: the platform group, with a realm, client and group definitions to test against, after Epic 2. Do not attempt to stand up an IdP to satisfy this line, and do not report SC-6 as proven when the story passes.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
|---|---|---|
| `src/django_service/users/provisioning.py` | NEW | `provision_designated_groups`, `DESIGNATED_GROUP_PERMISSIONS`, `ProvisionResult`. The one and only group-creating call site in the repository. |
| `src/django_service/users/migrations/0003_provision_designated_groups.py` | NEW | `RunPython` forward/reverse. Depends on `0002_user_idp_subject` from Story 2.1 — confirm that file exists before writing this one. |
| `docs/authentication.md` | NEW | `docs/` today contains exactly `index.md`, `development.md`, `observability.md` — verified. |
| `mkdocs.yml` | UPDATE | Today: `nav:` has three entries — `Home: index.md`, `Development: development.md`, `Observability: observability.md`. Add a fourth. **Preserve:** `docs_dir`/`site_dir`, the material theme block and the `markdown_extensions` list. |
| `tests/unit/users/test_provisioning.py` | NEW | Declaration-shape assertions, no DB. |
| `tests/integration/users/test_provisioning.py` | NEW | Idempotence and contract-seeding against a real database. |

### Testing Requirements

- Mirrors `src/` per the spine's test-location convention: `src/django_service/users/provisioning.py` → `tests/unit/users/test_provisioning.py` and `tests/integration/users/test_provisioning.py`. Both are `core` disposition — they cover `django_service`, which is `core` in its entirety (AD-29).
- `tests/integration/conftest.py` auto-applies `pytest.mark.integration` to everything under `tests/integration/`; you still need `@pytest.mark.django_db` for database access.
- Integration tests must leave state as they found it. `@pytest.mark.django_db` wraps each test in a transaction that rolls back, which satisfies this. Do **not** use `django_db(transaction=True)` unless a test genuinely needs committed state — it truncates tables and is slower.
- Assertions the ACs demand:
  - AC #1 — with `CLAIMS_CONTRACT` overridden through the `settings` fixture to arbitrary names, exactly those `Group` rows appear; no group named by any literal in the source appears.
  - AC #2 — two consecutive calls leave exactly one row per group and the same permission set.
  - AC #3 — the source-text assertion that no other module in `src/` calls `Group.objects.create`/`get_or_create`.
- Migrations are omitted from coverage (`*/migrations/*` is already in `[tool.coverage.run] omit`), which is why the logic lives in `provisioning.py` and not in the migration file — putting it in the migration would make it invisible to AD-20's floor. That is a second, independent reason for Task 1's structure.
- Coverage floor 90% including templates (AD-20). Add nothing to the omit list.
- `pixi run docs` (mkdocs `--strict`) must pass after Task 5. It is not part of `pixi run ci`; run it explicitly.

#### Project Structure Notes

Aligned with the Structural Seed: `src/django_service/` is the platform base, `core` in its entirety. No new top-level directory is created.

One variance worth recording: the seed places authorization under `src/config/authorization/`, and the *mechanism* this story builds lives in `src/django_service/` instead. That is AD-27's explicit instruction ("a data migration inside `django_service`") and AD-4's direction rule, not a drift — authorization *data* has a different owner from authorization *decisions*. The decisions stay in `src/config/authorization/` (Stories 2.4, 2.5).

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-27]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-12]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-4]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.3]
- [Source: _bmad-output/planning-artifacts/epics.md:39] — FR-11
- [Source: _bmad-output/planning-artifacts/epics.md:330-339] — SC-6 is an external exit criterion no story closes
- [Source: _bmad-output/planning-artifacts/implementation-readiness-report-2026-08-15.md:408] — "the designated `Group` and `Permission` rows by data migration in 2.3 (consumed by 2.5 and 3.3)"
- [Source: src/django_service/users/migrations/] — contains only `__init__.py` and `0001_initial.py` today
- [Source: mkdocs.yml] — the three-entry `nav:` list
- [Source: pyproject.toml:162-169] — `[tool.coverage.run] omit` already excludes `*/migrations/*`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
