---
baseline_revision: f9c4a13
review_loop_iteration: 0
status: done
warnings: []
---

# Story 2.5: The mapper syncs authorization once per credential epoch

Status: done

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

3. **Given** two of six combinations have no Redis
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

- [x] Task 1 — Add the epoch table to `django_service` (AC: #3)
  - [x] Add `class CredentialEpoch(models.Model)` to `src/django_service/users/models.py` with: `jti = CharField(max_length=255, unique=True)`, `user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name="credential_epochs")`, `first_seen_at = DateTimeField(auto_now_add=True)`, `expires_at = DateTimeField(null=True, blank=True, db_index=True)`.
  - [x] `unique=True` on `jti` supplies the index; do not also set `db_index=True`. `expires_at` needs its own index because the pruning process (AD-31) scans on it.
  - [x] Populate `expires_at` from the token's `exp` claim when present. It exists so AD-31's declared admin process can prune the table alongside sessions; without it the table grows without bound.
  - [x] Generate `src/django_service/users/migrations/0004_credentialepoch.py` with `pixi run makemigrations users`. Confirm it contains exactly one `CreateModel`.
  - [x] Do **not** bump any API version constant. AD-10 says the epoch table "is internal surface (AD-29), so adding it is not an API version bump." `django_service.__api_version__` does not exist in this repository yet in any case — it arrives in Epic 9 Story 9.1.

- [x] Task 2 — Implement `sync_authorization` in `src/config/authorization/mapper.py` (AC: #1, #6, #7, #8)
  - [x] Signature: `def sync_authorization(user: User, claims: Mapping[str, Any]) -> SyncOutcome`. Add `@dataclass(frozen=True, slots=True) class SyncOutcome` carrying `added: tuple[str, ...]`, `removed: tuple[str, ...]`, `ignored: tuple[str, ...]`, `is_staff: bool`, `is_superuser: bool`.
  - [x] Read the asserted groups with `read_group_claim(claims, settings.CLAIMS_CONTRACT.group_claim)` (Story 2.2). **`None` — the claim is absent — raises `ClaimsRejected("group claim absent")`.** An empty list is a legitimate assertion of "no groups" and proceeds. AC #7 and AD-12 turn on exactly this distinction; collapsing `None` and `[]` fails the AC silently.
  - [x] Wrap the whole body in `with transaction.atomic():` (AC #1). AD-10: "Sync runs inside one transaction, which makes FR-9's add-then-remove ordering a detail rather than a security property." Because of that, ordering is free — but do not take it as licence to leave a window open outside the transaction.
  - [x] Resolve asserted names to `Group` rows in **one** query: `Group.objects.filter(name__in=asserted)`. Names in `asserted` that came back with no row are the **ignored** set: emit `structlog` warning `authorization.unknown_group_claim` with the name and the `idp_subject`, and move on. **Never `Group.objects.create`** — AD-12 says ignored and logged, never created, and AD-27 makes that safe by guaranteeing the designated rows already exist (Story 2.3). Group creation in this repository has exactly one call site, `src/django_service/users/provisioning.py`.
  - [x] Diff against current membership and apply with `user.groups.add(*to_add)` / `user.groups.remove(*to_remove)`. Do not use `user.groups.set(...)` — it hides which rows moved, and AC #1 requires the log line to record what changed.
  - [x] Set `user.is_staff = settings.CLAIMS_CONTRACT.staff_group in asserted_resolved_names` and `user.is_superuser = settings.CLAIMS_CONTRACT.superuser_group in asserted_resolved_names` — each from **its own** designated group, each **cleared** when unasserted (AD-12, AC #6). Save with `update_fields=["is_staff", "is_superuser"]`.
  - [x] Emit exactly one `structlog` event `authorization.synced` at info carrying `idp_subject`, `groups_added`, `groups_removed`, `groups_ignored`, `is_staff`, `is_superuser`. One line per sync, recording what changed (AC #1).

- [x] Task 3 — Implement the epoch gate `sync_once_per_epoch` (AC: #2, #3, #4)
  - [x] Signature: `def sync_once_per_epoch(user: User, claims: Mapping[str, Any]) -> SyncOutcome | None`. Returns `None` when the epoch was already recorded and sync was therefore skipped.
  - [x] Read `jti` from the claims. **Falsy or absent `jti` raises `ClaimsRejected("token carries no jti")`.** AD-10: "**A token with no `jti` is rejected with 401.** Without this rule, one builder syncs every request and one never syncs again, delivering both of the outcomes this AD claims to prevent." The rule lives here, in the mapper; Story 2.7's DRF class translates `ClaimsRejected` into the 401 (AC #4).
  - [x] Inside `transaction.atomic()`: `CredentialEpoch.objects.get_or_create(jti=jti, defaults={"user": user, "expires_at": ...})`. If `created` is False, return `None` without syncing (AC #2's "not on subsequent requests carrying the same `jti`"). If True, call `sync_authorization` and return its outcome.
  - [x] Two workers can race the same first sighting. Catch `django.db.IntegrityError` **specifically** (never a bare `except:`, never `except X: pass`) around the create, treat it as already-seen, log `authorization.epoch_race` at debug, and return `None`. The unique constraint on `jti` is what makes this safe.
  - [x] Do **not** touch `django.core.cache` anywhere in this module. AD-10: the epoch record lives in the database "not in `django.core.cache`: two of six combinations have no Redis, so in those the cache is Django's in-process backend and 'first sighting' would degrade to first-sighting-per-worker-per-restart." A cache read "as an optimization in front of the table" reintroduces exactly that failure and is forbidden.
  - [x] Add `def sync_for_interactive(user, claims) -> SyncOutcome` that calls `sync_authorization` **unconditionally** — an interactive login is itself the epoch, has no `jti`, and must never be routed through the epoch gate (AC #2's first clause).

- [x] Task 4 — Keep mapping out of `populate_user()` (AC: #5)
  - [x] `src/django_service/users/adapters.py` currently defines `SocialAccountAdapter.populate_user`, which allauth calls **only when instantiating a new user**. Any mapping placed there runs once and never again — which is the failure mode AC #5 exists to catch.
  - [x] Add no mapping call to `populate_user` in this story. Story 2.6 moves the social adapter to `src/config/authorization/adapters.py` and hooks `pre_social_login`, which allauth calls on **every** social login.
  - [x] AC #5's test belongs here regardless of where the hook lands: assert that a second and subsequent authentication of the same identity still produces a `SyncOutcome`. Write it against the mapper's own entry points so it holds independently of which adapter hook Story 2.6 chooses.

- [x] Task 5 — Tests (AC: #1 through #8)
  - [x] `tests/unit/authorization/test_mapper_sync.py` (new) — `ClaimsRejected` on absent group claim (AC #7) and on absent/empty `jti` (AC #4); these need no database if you drive the claim-reading helpers directly.
  - [x] `tests/integration/authorization/test_mapper_sync.py` (new, `@pytest.mark.django_db`):
    - AC #1 — a user in groups `{A, B}` given claims asserting `{B, C}` ends in `{B, C}`; the emitted event records `added=("C",)`, `removed=("A",)`. Assert the transaction with `django_assert_num_queries` bounded and, better, by asserting that a `sync_authorization` that raises part-way leaves membership unchanged (force the raise by patching the `is_staff` save to raise, then assert no group rows moved).
    - AC #2 — first call with `jti="j1"` returns a `SyncOutcome`; second call with the same `jti` returns `None` and performs no membership write; a call with `jti="j2"` syncs again. Separately, `sync_for_interactive` syncs on every call.
    - AC #3 — assert `CredentialEpoch.objects.filter(jti=...).exists()` after first sighting, and add a source-text assertion that `django.core.cache` is not imported anywhere under `src/config/authorization/`.
    - AC #4 — claims with no `jti` key, and claims with `jti=""`, both raise `ClaimsRejected`.
    - AC #5 — authenticate the same identity three times through `sync_for_interactive` with changing group claims and assert the membership tracks the claims each time.
    - AC #6 — a user in the staff group, then claims that no longer assert it: `user.is_staff is False` afterwards, and a request to the admin index as that user does not return 200. Use the Django test client against `reverse("admin:index")`.
    - AC #7 — claims with the group claim key absent raise `ClaimsRejected`; claims with the key present and `[]` do **not** raise and result in zero groups. Both cases in the same test file, adjacent, so the distinction is legible.
    - AC #8 — claims asserting `"no-such-group"` leave `Group.objects.count()` unchanged, produce an `authorization.unknown_group_claim` event, and still sync the groups that do exist.
  - [x] Use `structlog.testing.capture_logs()` for every event assertion.
  - [x] Run `pixi run test`, `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-10 (binding rule — the sync half):** "**Sync** diffs asserted groups against stored ones, adds, removes, sets staff and superuser, and emits the structured log line. It runs once per credential epoch: every interactive login, and once per Bearer token at first sighting of its `jti`. Sync runs inside one transaction … **The epoch record lives in the database**, in a `django_service`-owned table, not in `django.core.cache`: two of six combinations have no Redis, so in those the cache is Django's in-process backend and 'first sighting' would degrade to first-sighting-per-worker-per-restart. The table is pruned by a declared admin process alongside sessions (AD-31). It is internal surface (AD-29), so adding it is not an API version bump. **A token with no `jti` is rejected with 401.**" *Prevents:* "the only two outcomes of conflating them — `auth_user_groups` write amplification on every API call, or stale authorization."
  - **Do not implement resolve in this story.** `resolve_user` is Story 2.4's and already exists in the same module. Sync takes a `User` it is handed; it never looks one up.
- **AD-12 (binding rule, all four edges):** "A token lacking the configured group claim is rejected with 401, never authenticated with zero groups. A claim asserting a group with no matching Django `Group` is ignored and logged, never created — which is safe only because AD-27 guarantees the designated groups exist. `is_staff` and `is_superuser` are each set from their own designated group and cleared when the claims stop asserting it. A `username` collision between two distinct `idp_subject`s is refused and logged; the second identity keeps its existing username and authenticates normally." *Prevents:* "a misconfiguration presenting as a permissions bug; IdP group taxonomy silently becoming Django taxonomy; an `IntegrityError` mid-authentication." (The fourth edge is Story 2.4's; the first three are this story's.)
- **AD-31:** "Expired sessions and expired mapper epoch records (AD-10) are pruned by one declared admin process, not a background task, because Celery exists in only two of six combinations." That process is Epic 5's (Story 5.7 owns the session engine; the pruning process is declared in `component.toml`). **This story does not build the pruner** — it builds the `expires_at` column the pruner will need. Do not add a Celery task, a `cron` entry, or a management command that prunes.
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
- [Source: _bmad-output/planning-artifacts/epics.md:330-339] — SC-6 is external
- [Source: _bmad-output/planning-artifacts/implementation-readiness-report-2026-08-15.md:387,514] — sizing reviewed, left intact deliberately
- [Source: src/django_service/users/adapters.py:29-48] — the existing `populate_user`, which AC #5 forbids as a mapping site
- [Source: src/django_service/users/admin.py:11-15] — `secure_admin_login` wrapping, relevant to AC #6's admin assertion

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Claude Code, `bmad-dev-auto`)

### Debug Log References

- `pixi run ci` — exit 0. 513 passed, 6 skipped. Coverage 94.59% (floor 90). `src/config/authorization/mapper.py` and `src/django_service/users/models.py` both at 100%.
- PostgreSQL 17 run (per project memory `validate-model-changes-against-postgres`): `DATABASE_URL=postgres://…:55432/gatedb pixi run test-cov --create-db` — 513 passed, same coverage. The gate's sqlite substitution does not enforce `varchar` widths; this story both adds a table and persists an externally-supplied value (`jti`), so it needed the real run.
- Pre-fix probe on the same PostgreSQL: `CredentialEpoch.objects.create(jti="j" * 300, …)` raises `django.db.utils.DataError: value too long for type character varying(255)`. That is what `_reject_an_unstorable_jti` exists to prevent; the probe was throwaway and is not in the tree.

### Completion Notes List

- **One deviation, recorded.** The spec names two refusals for `sync_once_per_epoch`; the implementation raises a third, `jti longer than the epoch field`, from `_reject_an_unstorable_jti`. It is the exact mirror of Story 2.4's `_reject_an_unstorable_identity_key` and exists for the same reason: `jti` is attacker-influenced input written into a `varchar(255)`, sqlite stores an over-long one silently and PostgreSQL answers with a `DataError` in the middle of an authentication — verified above. Truncating instead would be worse than the error it avoids: two distinct credentials sharing a prefix would share one epoch, so the second would never sync, which is the stale-authorization half of exactly what AD-10 prevents. No new exception *type* was added — `ClaimsRejected` carries it in `reason`, as AD-12 and `exceptions.py` require.
- `jti` and `exp` are read as flat, non-configurable claim names (`JTI_CLAIM`, `EXPIRY_CLAIM`), not through `CLAIMS_CONTRACT`. The contract designates the four claims *authorization is decided from*; both of these are RFC 7519 registered claims, and an epoch is not an authorization decision but a frequency. `jti` is read through the module's existing `_read_text`, so a non-string `jti` is refused rather than coerced.
- The `authorization.synced` event is emitted as the last statement *inside* the `transaction.atomic()` block, following the task's "wrap the whole body" literally. `ATOMIC_REQUESTS` is on, so an outer rollback can discard the change regardless of where the emit sits; nothing is gained by moving it out.
- `added` is ordered as the claims asserted it; `removed` is sorted, because the held set arrives in the database's order and an unsorted tuple would make the event — and any assertion against it — depend on an order nobody declared.
- `is_staff` / `is_superuser` are read against the **resolved** group names, not the asserted ones, so a designated group that does not exist confers nothing. No defensive `get_or_create` for the designated groups was added: AD-27 makes their absence Epic 4's stage-2 startup refusal. `tests/integration/authorization/test_mapper_sync.py::test_a_designated_group_that_does_not_exist_confers_nothing` pins that.
- `django.core.cache` is banned by an AST import scan over `src/config/authorization/`, not by a text search — the module docstrings quote AD-10's rule, which names the module in prose, and a grep reports the prohibition as a violation of itself.
- AC #5's test is written against `sync_for_interactive` rather than against any adapter hook, so it holds whichever hook Story 2.6 lands on. `populate_user` in `src/django_service/users/adapters.py` is unchanged.
- Out of scope and deliberately absent, as the spec requires: no pruner, no Celery task, no management command, no cache, no re-sync timer, no change to `resolve_user`, no API version constant.
- Task names in this repository are `format` / `lint` / `typecheck` / `test` / `test-integration` / `test-cov` / `ci`, not `fmt` / `check` / `cov`.

### File List

| Path | NEW / UPDATE | What changed |
|---|---|---|
| `src/django_service/users/models.py` | UPDATE | Adds `CredentialEpoch` (`jti` unique, `user` FK cascade, `first_seen_at`, indexed nullable `expires_at`, `__str__`). `User` untouched. |
| `src/django_service/users/migrations/0004_credentialepoch.py` | NEW | Generated by `pixi run makemigrations users`. Exactly one `CreateModel`, depending on `0003_provision_designated_groups`. |
| `src/config/authorization/mapper.py` | UPDATE | Adds `SyncOutcome`, `sync_authorization`, `sync_for_interactive`, `sync_once_per_epoch`, `_reject_an_unstorable_jti`, `_expires_at`, the `JTI_CLAIM`/`EXPIRY_CLAIM` constants and the two new refusal reasons. Records R-2 in the module docstring. `resolve_user` and its helpers are unchanged. |
| `tests/unit/authorization/test_mapper_sync.py` | NEW | Claim-shape refusals (absent group claim, unusable `jti`, over-long `jti`), `exp` reading, `SyncOutcome`. No database. |
| `tests/integration/authorization/test_mapper_sync.py` | NEW | The eight behavioural assertions, plus the epoch-race and no-cache-import checks. |

`src/config/authorization/exceptions.py` was **not** modified: `ClaimsRejected` is reused for all three refusals, as the spec requires.

## Review Triage Log

### 2026-08-17 — Inline review pass (non-standard)

The orchestrated run was killed during step-04, so the three hunter sessions
never ran -- the second story in this epic to die at that same phase. Reviewed
inline instead, by the session driving the loop. Recorded as weaker evidence
than a normal pass for one reason, per CG-2: the hunters read a diff blind and
this reviewer had the story's full context.

- intent_gap: 0
- bad_spec: 0
- patch: 0
- defer: 0
- reject: 0
- addressed_findings:
  - none

What was checked, and why each came back clean rather than unexamined:

- **The first-sighting race.** Two concurrent requests carrying one new `jti`
  both see "not seen". The implementation opens an outer `atomic()`, wraps
  `get_or_create` in an inner savepoint, catches `IntegrityError`, and re-reads
  before deciding: a lost race returns `None` (already synced by the winner),
  a genuine failure logs and re-raises. `test_a_lost_race_for_the_first_sighting_is_treated_as_already_seen`
  and `test_an_insert_failure_that_is_not_the_race_is_reported_and_raised` pin
  both halves.
- **Revocation lag.** Gating on first sighting means a group revoked at the IdP
  is honoured until the token expires. Documented at `mapper.py:15` as a
  deliberate trade with the alternatives named, not left implicit.
- **Unbounded epoch growth.** Rows accumulate; `expires_at` carries its own
  index precisely so AD-31's declared admin process can scan it. Forward work,
  already planned rather than missing.
- **Model/migration drift on `jti`.** Already closed by the story itself, which
  added a schema assertion mirroring `users_user.name` and using `display_size`
  -- the correction that came out of Story 1.2's third review round.
