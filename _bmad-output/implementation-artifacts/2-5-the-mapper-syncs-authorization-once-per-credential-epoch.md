# Story 2.5: The mapper syncs authorization once per credential epoch

Status: ready-for-dev

## Story

As a platform engineer,
I want group membership, staff and superuser status re-synced from claims on every credential epoch including removals,
so that a revocation at the IdP reaches the component rather than persisting until someone notices.

## Acceptance Criteria

**Traceability:** FR-9, FR-11 · AD-10, AD-12 · SC-6 · risk R-2

1. **Given** an authentication
   **When** sync runs
   **Then** it adds the memberships the claims assert, removes the memberships they no longer assert, sets `is_staff` and `is_superuser` each from its own designated group, and emits a structured log line recording what changed
   **And** all of it runs inside one transaction

2. **Given** sync frequency
   **When** an interactive login occurs
   **Then** sync runs
   **And** when a Bearer credential is seen, sync runs once at first sighting of its `jti` and not on subsequent requests carrying the same `jti`

3. **Given** eight of twelve combinations have no Redis
   **When** the epoch record is stored
   **Then** it lives in a `django_service`-owned database table
   **And** never in `django.core.cache`

4. **Given** a Bearer token with no `jti`
   **When** it is presented
   **Then** it is rejected with 401

5. **Given** mapping must not live in `populate_user()`
   **When** an identity authenticates a second and subsequent time
   **Then** a test asserts mapping still occurs

6. **Given** an identity whose claims drop the designated staff group
   **When** it next authenticates
   **Then** it loses staff status
   **And** can no longer reach the admin

7. **Given** a token lacking the configured group claim
   **When** it is presented
   **Then** it is rejected with 401
   **And** never authenticated with zero groups

8. **Given** a claim asserting a group with no matching Django `Group`
   **When** sync runs
   **Then** the claim is ignored and logged
   **And** no group is created

## Tasks / Subtasks

- [ ] Task 1 — Add the epoch table to `django_service` (AC: #3)
  - [ ] Add `class CredentialEpoch(models.Model)` to `src/django_service/users/models.py` with: `jti = CharField(max_length=255, unique=True)`, `user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name="credential_epochs")`, `first_seen_at = DateTimeField(auto_now_add=True)`, `expires_at = DateTimeField(null=True, blank=True, db_index=True)`.
  - [ ] `unique=True` on `jti` supplies the index; do not also set `db_index=True`. `expires_at` needs its own index because the pruning process (AD-31) scans on it.
  - [ ] Populate `expires_at` from the token's `exp` claim when present. It exists so AD-31's declared admin process can prune the table alongside sessions; without it the table grows without bound.
  - [ ] Generate `src/django_service/users/migrations/0004_credentialepoch.py` with `pixi run makemigrations users`. Confirm it contains exactly one `CreateModel`.
  - [ ] Do **not** bump any API version constant. AD-10 says the epoch table "is internal surface (AD-29), so adding it is not an API version bump." `django_service.__api_version__` does not exist in this repository yet in any case — it arrives in Epic 9 Story 9.1.

- [ ] Task 2 — Implement `sync_authorization` in `src/config/authorization/mapper.py` (AC: #1, #6, #7, #8)
  - [ ] Signature: `def sync_authorization(user: User, claims: Mapping[str, Any]) -> SyncOutcome`. Add `@dataclass(frozen=True, slots=True) class SyncOutcome` carrying `added: tuple[str, ...]`, `removed: tuple[str, ...]`, `ignored: tuple[str, ...]`, `is_staff: bool`, `is_superuser: bool`.
  - [ ] Read the asserted groups with `read_group_claim(claims, settings.CLAIMS_CONTRACT.group_claim)` (Story 2.2). **`None` — the claim is absent — raises `ClaimsRejected("group claim absent")`.** An empty list is a legitimate assertion of "no groups" and proceeds. AC #7 and AD-12 turn on exactly this distinction; collapsing `None` and `[]` fails the AC silently.
  - [ ] Wrap the whole body in `with transaction.atomic():` (AC #1). AD-10: "Sync runs inside one transaction, which makes FR-9's add-then-remove ordering a detail rather than a security property." Because of that, ordering is free — but do not take it as licence to leave a window open outside the transaction.
  - [ ] Resolve asserted names to `Group` rows in **one** query: `Group.objects.filter(name__in=asserted)`. Names in `asserted` that came back with no row are the **ignored** set: emit `structlog` warning `authorization.unknown_group_claim` with the name and the `idp_subject`, and move on. **Never `Group.objects.create`** — AD-12 says ignored and logged, never created, and AD-27 makes that safe by guaranteeing the designated rows already exist (Story 2.3). Group creation in this repository has exactly one call site, `src/django_service/users/provisioning.py`.
  - [ ] Diff against current membership and apply with `user.groups.add(*to_add)` / `user.groups.remove(*to_remove)`. Do not use `user.groups.set(...)` — it hides which rows moved, and AC #1 requires the log line to record what changed.
  - [ ] Set `user.is_staff = settings.CLAIMS_CONTRACT.staff_group in asserted_resolved_names` and `user.is_superuser = settings.CLAIMS_CONTRACT.superuser_group in asserted_resolved_names` — each from **its own** designated group, each **cleared** when unasserted (AD-12, AC #6). Save with `update_fields=["is_staff", "is_superuser"]`.
  - [ ] Emit exactly one `structlog` event `authorization.synced` at info carrying `idp_subject`, `groups_added`, `groups_removed`, `groups_ignored`, `is_staff`, `is_superuser`. One line per sync, recording what changed (AC #1).

- [ ] Task 3 — Implement the epoch gate `sync_once_per_epoch` (AC: #2, #3, #4)
  - [ ] Signature: `def sync_once_per_epoch(user: User, claims: Mapping[str, Any]) -> SyncOutcome | None`. Returns `None` when the epoch was already recorded and sync was therefore skipped.
  - [ ] Read `jti` from the claims. **Falsy or absent `jti` raises `ClaimsRejected("token carries no jti")`.** AD-10: "**A token with no `jti` is rejected with 401.** Without this rule, one builder syncs every request and one never syncs again, delivering both of the outcomes this AD claims to prevent." The rule lives here, in the mapper; Story 2.7's DRF class translates `ClaimsRejected` into the 401 (AC #4).
  - [ ] Inside `transaction.atomic()`: `CredentialEpoch.objects.get_or_create(jti=jti, defaults={"user": user, "expires_at": ...})`. If `created` is False, return `None` without syncing (AC #2's "not on subsequent requests carrying the same `jti`"). If True, call `sync_authorization` and return its outcome.
  - [ ] Two workers can race the same first sighting. Catch `django.db.IntegrityError` **specifically** (never a bare `except:`, never `except X: pass`) around the create, treat it as already-seen, log `authorization.epoch_race` at debug, and return `None`. The unique constraint on `jti` is what makes this safe.
  - [ ] Do **not** touch `django.core.cache` anywhere in this module. AD-10: the epoch record lives in the database "not in `django.core.cache`: eight of twelve combinations have no Redis, so the cache is Django's in-process backend and 'first sighting' would degrade to first-sighting-per-worker-per-restart." A cache read "as an optimization in front of the table" reintroduces exactly that failure and is forbidden.
  - [ ] Add `def sync_for_interactive(user, claims) -> SyncOutcome` that calls `sync_authorization` **unconditionally** — an interactive login is itself the epoch, has no `jti`, and must never be routed through the epoch gate (AC #2's first clause).

- [ ] Task 4 — Keep mapping out of `populate_user()` (AC: #5)
  - [ ] `src/django_service/users/adapters.py` currently defines `SocialAccountAdapter.populate_user`, which allauth calls **only when instantiating a new user**. Any mapping placed there runs once and never again — which is the failure mode AC #5 exists to catch.
  - [ ] Add no mapping call to `populate_user` in this story. Story 2.6 moves the social adapter to `src/config/authorization/adapters.py` and hooks `pre_social_login`, which allauth calls on **every** social login.
  - [ ] AC #5's test belongs here regardless of where the hook lands: assert that a second and subsequent authentication of the same identity still produces a `SyncOutcome`. Write it against the mapper's own entry points so it holds independently of which adapter hook Story 2.6 chooses.

- [ ] Task 5 — Tests (AC: #1 through #8)
  - [ ] `tests/unit/authorization/test_mapper_sync.py` (new) — `ClaimsRejected` on absent group claim (AC #7) and on absent/empty `jti` (AC #4); these need no database if you drive the claim-reading helpers directly.
  - [ ] `tests/integration/authorization/test_mapper_sync.py` (new, `@pytest.mark.django_db`):
    - AC #1 — a user in groups `{A, B}` given claims asserting `{B, C}` ends in `{B, C}`; the emitted event records `added=("C",)`, `removed=("A",)`. Assert the transaction with `django_assert_num_queries` bounded and, better, by asserting that a `sync_authorization` that raises part-way leaves membership unchanged (force the raise by patching the `is_staff` save to raise, then assert no group rows moved).
    - AC #2 — first call with `jti="j1"` returns a `SyncOutcome`; second call with the same `jti` returns `None` and performs no membership write; a call with `jti="j2"` syncs again. Separately, `sync_for_interactive` syncs on every call.
    - AC #3 — assert `CredentialEpoch.objects.filter(jti=...).exists()` after first sighting, and add a source-text assertion that `django.core.cache` is not imported anywhere under `src/config/authorization/`.
    - AC #4 — claims with no `jti` key, and claims with `jti=""`, both raise `ClaimsRejected`.
    - AC #5 — authenticate the same identity three times through `sync_for_interactive` with changing group claims and assert the membership tracks the claims each time.
    - AC #6 — a user in the staff group, then claims that no longer assert it: `user.is_staff is False` afterwards, and a request to the admin index as that user does not return 200. Use the Django test client against `reverse("admin:index")`.
    - AC #7 — claims with the group claim key absent raise `ClaimsRejected`; claims with the key present and `[]` do **not** raise and result in zero groups. Both cases in the same test file, adjacent, so the distinction is legible.
    - AC #8 — claims asserting `"no-such-group"` leave `Group.objects.count()` unchanged, produce an `authorization.unknown_group_claim` event, and still sync the groups that do exist.
  - [ ] Use `structlog.testing.capture_logs()` for every event assertion.
  - [ ] Run `pixi run test`, `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-10 (binding rule — the sync half):** "**Sync** diffs asserted groups against stored ones, adds, removes, sets staff and superuser, and emits the structured log line. It runs once per credential epoch: every interactive login, and once per Bearer token at first sighting of its `jti`. Sync runs inside one transaction … **The epoch record lives in the database**, in a `django_service`-owned table, not in `django.core.cache`: eight of twelve combinations have no Redis, so the cache is Django's in-process backend and 'first sighting' would degrade to first-sighting-per-worker-per-restart. The table is pruned by a declared admin process alongside sessions (AD-31). It is internal surface (AD-29), so adding it is not an API version bump. **A token with no `jti` is rejected with 401.**" *Prevents:* "the only two outcomes of conflating them — `auth_user_groups` write amplification on every API call, or stale authorization."
  - **Do not implement resolve in this story.** `resolve_user` is Story 2.4's and already exists in the same module. Sync takes a `User` it is handed; it never looks one up.
- **AD-12 (binding rule, all four edges):** "A token lacking the configured group claim is rejected with 401, never authenticated with zero groups. A claim asserting a group with no matching Django `Group` is ignored and logged, never created — which is safe only because AD-27 guarantees the designated groups exist. `is_staff` and `is_superuser` are each set from their own designated group and cleared when the claims stop asserting it. A `username` collision between two distinct `idp_subject`s is refused and logged; the second identity keeps its existing username and authenticates normally." *Prevents:* "a misconfiguration presenting as a permissions bug; IdP group taxonomy silently becoming Django taxonomy; an `IntegrityError` mid-authentication." (The fourth edge is Story 2.4's; the first three are this story's.)
- **AD-31:** "Expired sessions and expired mapper epoch records (AD-10) are pruned by one declared admin process, not a background task, because Celery exists in only four of twelve combinations." That process is Epic 5's (Story 5.7 owns the session engine; the pruning process is declared in `component.toml`). **This story does not build the pruner** — it builds the `expires_at` column the pruner will need. Do not add a Celery task, a `cron` entry, or a management command that prunes.
- **AD-27:** "A designated staff or superuser group absent from the database at startup is a stage-2 refusal condition." That refusal is **Epic 4's**. This story's ignore-and-log behaviour (AC #8) is safe only because Story 2.3 provisions the designated rows; do not add a defensive `get_or_create` for the designated groups here.
- **AD-29:** `src/django_service/` is `core` in its entirety; the epoch model lives there and carries no `feature:*` marker.
- **AD-24 (what you must not do):** no conditional imports, no `try/except ImportError`, no settings-module inheritance. In particular, do not write `try: from django_redis import ... except ImportError:` to pick a storage backend for the epoch record. There is one storage: the table.
- **Spine, Consistency Conventions → Logging:** "Every authorization change emits an event." Sync is the authorization change. One `authorization.synced` event per sync, plus per-name `authorization.unknown_group_claim` warnings. `structlog` only — never `print()`, never stdlib `logging`.
- **Spine, Consistency Conventions → Runtime errors:** "Authentication failure is 401 … Nothing is swallowed silently." Never a bare `except:`; never `except X: pass`. The `IntegrityError` race is caught by its specific type, logged, and handled.
- **FR-9:** "Authorization re-syncs on every authentication including revocation — adds asserted groups, removes unasserted ones, sets staff, emits a structured log line; **resolve and re-sync run at different frequencies**." The spine's divergence D-3 records that the PRD was amended to say so explicitly: "resolution and re-sync run at different frequencies and … the difference is a requirement."

### R-2 — the risk this story carries and does not remove

**R-2 — Bearer revocation latency is the token's lifetime.** "AD-10 syncs once per `jti`, so a group revoked at the IdP is honoured until the token expires. Unavoidable for bearer credentials, but it narrows FR-9 and SC-6 and is not the same question as PRD Open Question 1, which covers sessions only."

Implications for implementation, stated so nobody tries to fix it in code:

- Do **not** add a shorter re-sync interval, a "re-sync every N minutes" timer, or a revocation-check callback to the IdP. Each of those reintroduces the write amplification AD-10 exists to prevent, and none of them closes the window — the token remains valid regardless.
- Do **not** delete the epoch row early to force a re-sync. The row's purpose is idempotence, not freshness.
- Record R-2 in the module docstring of `mapper.py` so the next reader does not mistake it for an oversight. Token lifetime is the IdP's policy lever, not this component's.

### SC-6 cannot be closed here

SC-6 requires a real IdP identity authenticating through both flows with correct authorization state in both. It is an **external exit criterion no story closes** — owner: the platform group, after Epic 2. Every AC here is satisfiable against synthetic claim dictionaries and mocked JWKS. Passing them does not prove SC-6.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
|---|---|---|
| `src/django_service/users/models.py` | UPDATE | Today: `User(AbstractUser)` with `name`, nulled `first_name`/`last_name`, `get_absolute_url()`, plus `idp_subject` from Story 2.1. Adds `CredentialEpoch`. **Preserve:** everything already there, including the `# type: ignore[assignment]` comments. |
| `src/django_service/users/migrations/0004_credentialepoch.py` | NEW | One `CreateModel`. Confirm `0003_provision_designated_groups.py` (Story 2.3) exists before numbering. |
| `src/config/authorization/mapper.py` | UPDATE | Created by Story 2.4 holding `resolve_user` and the attribute/collision helpers. Adds `sync_authorization`, `sync_once_per_epoch`, `sync_for_interactive`, `SyncOutcome`. **Preserve:** `resolve_user`'s single-query property — do not add a `select_related("groups")` for sync's benefit. |
| `src/config/authorization/exceptions.py` | UPDATE | Created by Story 2.4 holding `ClaimsRejected`. Reuse it; do not add a second exception type per condition — the `reason` attribute carries the distinction. |
| `tests/unit/authorization/test_mapper_sync.py` | NEW | Claim-shape rejections. |
| `tests/integration/authorization/test_mapper_sync.py` | NEW | The eight behavioural assertions. |

### Testing Requirements

- Test tree mirrors `src/`. Keeping sync's tests in `..._sync.py` beside Story 2.4's `..._resolve.py` keeps AD-10's two operations separated in the test tree, which is the point of the AD.
- `tests/integration/conftest.py` auto-applies `pytest.mark.integration` under `tests/integration/`; database access still needs `@pytest.mark.django_db`.
- Integration tests must leave state as found — default `django_db` rollback satisfies this; avoid `transaction=True`. The one place you may be tempted is the `IntegrityError` race test; simulate it by creating the row directly rather than by spawning concurrency.
- Override `settings.CLAIMS_CONTRACT` per test through pytest-django's `settings` fixture. Seed the designated `Group` rows in the test by calling `provision_designated_groups()` from Story 2.3 — **not** by creating groups in the test, which would violate AC #3 of Story 2.3 in spirit and hide a real defect.
- AC #6's "can no longer reach the admin" needs a rendered check: `client.force_login(user)` then `client.get(reverse("admin:index"))`, asserting a non-200. Note that `src/django_service/users/admin.py:11-15` wraps `admin.site.login` with `secure_admin_login` when `DJANGO_ADMIN_FORCE_ALLAUTH` is set, so the redirect target differs by setting — assert "not 200", not a specific target.
- Coverage floor 90% including templates (AD-20). `*/migrations/*` is already omitted, so the new migration costs nothing; the model and mapper code do not qualify for omission and must be covered. Add nothing to `[tool.coverage.run] omit`.

#### Project Structure Notes

Two territories, deliberately: the epoch **table** is `django_service`-owned (AD-10 names the owner explicitly), and the sync **logic** is `config/authorization`-owned. `config` may import `django_service` (AD-4), so `mapper.py` importing `CredentialEpoch` is legal. The reverse — `django_service` importing the mapper — is not, and nothing in this story needs it.

The readiness assessment flagged this story as the largest in Epic 2 ("eight acceptance criteria spanning the sync algorithm, the epoch record and table, the `jti` rejection rule, and four edge behaviours") and it was **reviewed again and left intact**: "each is large but implements a single mechanism, and splitting would fragment it." Implement it as one mechanism; do not split it into two stories' worth of half-wired code.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-10]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-12]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-27]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-31]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-2
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Divergences From the PRD] — D-3, resolve and re-sync at different frequencies
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.5]
- [Source: _bmad-output/planning-artifacts/epics.md:37-39] — FR-9, FR-11
- [Source: _bmad-output/planning-artifacts/epics.md:328-337] — SC-6 is external
- [Source: _bmad-output/planning-artifacts/implementation-readiness-report-2026-08-15.md:387,514] — sizing reviewed, left intact deliberately
- [Source: src/django_service/users/adapters.py:29-48] — the existing `populate_user`, which AC #5 forbids as a mapping site
- [Source: src/django_service/users/admin.py:11-15] — `secure_admin_login` wrapping, relevant to AC #6's admin assertion

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
