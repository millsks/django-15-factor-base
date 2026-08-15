# Story 9.7: A contributed backing service inherits the local development contract

Status: ready-for-dev

## Story

As a developer working on a generated component,
I want an adopted application's own database to inherit every guarantee the component's own database has,
so that adopting an application does not cost me the local development contract.

## Acceptance Criteria

**Traceability:** FR-55 · AD-9, AD-22, AD-28

1. **Given** an application contributing a database
   **When** it contributes
   **Then** it must also contribute a router that answers only for its own labels and returns `None` otherwise

2. **Given** a component that adopts an application with its own database
   **When** it runs locally with nothing installed
   **Then** it still starts, serves and authenticates a persona
   **And** the local substitution is applied automatically by the base rather than arranged by the application

3. **Given** a deployed component whose contributed database has fallen back to the local substitution
   **When** it starts
   **Then** it refuses

4. **Given** unapplied migrations on a contributed database
   **When** a serving process starts
   **Then** it refuses exactly as it does on the component's own database

5. **Given** readiness
   **When** it evaluates a contributed backing service
   **Then** it treats it as required unless `component.toml` declares it optional

6. **Given** release-stage migration
   **When** it is declared
   **Then** `component.toml` declares one step per database
   **And** the deployment repository does not have to infer how many there are

## Tasks / Subtasks

- [ ] Task 1 — Require the router with the database (AC: #1)
  - [ ] In `src/config/settings/composition.py` (Story 9.4), add the chain check: a contribution introducing one or more `DATABASES` aliases must also append at least one entry to `DATABASE_ROUTERS`. A contribution that adds a database without a router raises `ImproperlyConfigured` naming the application and the alias.
  - [ ] The reverse is not required — a router with no new database is permitted (an application may route its models to an existing alias).
  - [ ] Add a router contract test helper in `src/config/startup/` — `assert_router_is_scoped(router, owned_labels)` is a *test* helper, so put the helper in `tests/`; the composition step itself checks presence, not behaviour. Behaviour is asserted by Task 5.

- [ ] Task 2 — Apply the local substitution in the base, automatically (AC: #2)
  - [ ] In the composition step, immediately after contributed `DATABASES` aliases are merged, substitute every contributed alias with sqlite when the runtime is local — `COMPONENT_RUNTIME=local`, read through the same locality helper Story 3.1/4.1 established, never re-derived here and never inferred from which settings module loaded.
  - [ ] The substituted entry is `{"ENGINE": "django.db.backends.sqlite3", "NAME": str(BASE_DIR / f"db.{alias}.sqlite3")}`, mirroring the `default` alias fallback at `src/config/settings/base.py:73-78`.
  - [ ] The application contributes its deployed database configuration only. It never writes a local branch, never reads `COMPONENT_RUNTIME`, and never ships a "local" variant — FR-18 stays true by construction because the base does it (AD-9).
  - [ ] Add `db.*.sqlite3` (and `db.*.sqlite3-journal`) to `.gitignore`; it currently lists `db.sqlite3` and `db.sqlite3-journal` at lines 61–62 and would not match a per-alias file.

- [ ] Task 3 — Extend the two refusals to iterate every configured database (AC: #3, #4)
  - [ ] Stage 1's sqlite condition (refusal-table condition 1, built today only for the `default` alias at `src/config/settings/production.py:26-28` and moved into `src/config/startup/` by Story 4.2) must iterate `settings.DATABASES` and refuse on **any** alias whose `ENGINE` resolves to the sqlite backend when the runtime is deployed. Report every offending alias, not the first.
  - [ ] Stage 2's unapplied-migrations condition (Story 4.3) must iterate every configured alias and refuse if any has unapplied migrations, honouring the router: use `MigrationExecutor(connections[alias])` per alias.
  - [ ] Both are reachable only because stage 1 runs as the last statement of every **leaf** settings module — `local.py`, `production.py`, `test.py` — after composition, and because **`base.py` does not call it** (AD-26). A call at the end of `base.py` would fire before the leaf composes and would never see a contributed alias at all. Do not move either check earlier.
  - [ ] These are edits inside `src/config/startup/`, not new conditions. This story widens the domain two existing conditions iterate over, exactly as the epics' refusal table describes; it adds none.
  - [ ] The widening is combination-invariant: neither condition depends on `celery`, `redis` or `storage`, so both iterate identically across **all six** valid combinations, and the tests must not be parameterized by feature selection.

- [ ] Task 4 — Readiness, requiredness, and the release-stage declaration (AC: #5, #6)
  - [ ] Extend the readiness endpoint (Story 5.3) to check every database the component declares required. A contributed alias is **required unless** `component.toml` marks it optional — the default is required, and an absent declaration means required.
  - [ ] **Use Story 5.1's shape; do not introduce a second one.** `component.toml` declares databases as an array of tables — one `[[databases]]` entry per alias carrying `alias`, `required` and `migrate` (the release-stage step list). A contributed alias adds one more `[[databases]]` entry: `alias = "billing"`, `required = false` for the optional case, and a non-empty `migrate` list. There is no `[databases.<alias>]` table and no `[[release.migrate]]` table — Story 5.1 closes the top-level key set to `{component, adopted_apps, selected_features, databases, processes, admin_processes}` and its loader raises `ImproperlyConfigured` on anything else, so a `release` table would fail that story's gate test rather than this one's.
  - [ ] Requiredness reaches this story as `DatabaseDeclaration.required` from `load_component_declaration()`. Story 5.1 makes `migrate` non-empty a schema condition, so "one step per database" is already true for every *declared* alias; what this story adds is the other direction — an alias that reached the composed `DATABASES` through a contribution and has no `[[databases]]` entry at all.
  - [ ] Readiness still never re-checks migrations (AD-22) — during a rolling deploy an older replica may legitimately run against a newer schema. Adding a contributed database does not change that.
  - [ ] Liveness is untouched: it checks nothing external in any configuration (NFR-2, AD-22).
  - [ ] Add a gate test reconciling the `[[databases]]` entries against the composed `DATABASES` in both directions — a composed alias with no entry fails, an entry naming no composed alias fails. Story 5.5's `tests/unit/test_release_stage.py` already asserts every declared entry carries a non-empty `migrate` list; do not restate that assertion, reference it.

- [ ] Task 5 — Router behaviour tests (AC: #1)
  - [ ] Add a fixture application to `tests/fixtures/tenant_apps/` (created in Story 9.4) contributing a `billing` alias and a router class.
  - [ ] Build it as a **whole revision-3 tenant app**, not a settings-only stub: its own model on the `billing` alias, a view, a mounted URL, a template extending `base.html` with a crispy-styled form, and one contributed navigation entry pointing at that route. With the interface mechanism `core` in all six combinations (AD-29), that is what an adopted app now looks like, and it is what makes AC #2's "starts and *serves*" a real assertion rather than a boot check. It declares no feature in `REQUIRES_FEATURES` — relying on `base.html`, the form styling and the navigation registry costs an app nothing, because none of them is feature-owned.
  - [ ] Assert the router returns the alias for `db_for_read`/`db_for_write` on a model whose app label it owns, and `None` for a model it does not own — `None` and not `"default"`, because returning a concrete alias would make one application's router decide routing for every other application's models.
  - [ ] Assert `allow_relation` returns `None` for cross-application pairs and `allow_migrate` returns `None` for labels it does not own.
  - [ ] Assert a contribution adding a `DATABASES` alias with no router raises `ImproperlyConfigured`.

- [ ] Task 6 — Local-contract test with nothing installed (AC: #2)
  - [ ] `tests/integration/test_contributed_database_local.py`, marked `@pytest.mark.integration`. With `COMPONENT_RUNTIME=local`, an adopted fixture application contributing a `billing` database, and no PostgreSQL running: assert the component starts, both aliases resolve to sqlite, migrations apply to both, readiness returns 200, and a persona authenticates through the local sign-in route (Story 3.4).
  - [ ] Then assert the app **serves**: the authenticated persona requests the fixture app's mounted route, the page renders through `base.html`, and the navigation bar carries the app's contributed entry with its label escaped. The local contract is the whole app working locally with nothing installed, not the database alone — and under revision 3 the interface half of that is present in every combination, so this assertion is not parameterized by feature selection either.
  - [ ] Assert the substitution came from the base: the fixture application's contribution contains only the deployed configuration, and the test asserts the contributed dict as declared is not sqlite while the composed setting is.
  - [ ] Use `tmp_path` for the sqlite files and leave no database file behind.

- [ ] Task 7 — Refusal and readiness tests (AC: #3, #4, #5, #6)
  - [ ] `tests/unit/test_contributed_database_refusals.py`: deployed runtime with a contributed alias left on sqlite raises `ImproperlyConfigured` naming that alias (AC #3); a deployed component with unapplied migrations on the contributed alias only — the `default` alias fully migrated — raises at stage 2 (AC #4). The second case is the one a per-alias loop written as `if not migrated(default)` silently passes.
  - [ ] `tests/unit/test_readiness_contributed.py`: a required contributed alias that does not answer produces non-200; the same alias marked `required = false` in its `[[databases]]` entry produces 200; an alias with no requiredness declaration is treated as required (AC #5).
  - [ ] `tests/unit/test_contributed_database_declaration.py`: the two-way reconciliation between `[[databases]]` entries and the composed `DATABASES` (AC #6).
  - [ ] `pixi run test`, `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-9 (binding, verbatim):** "An app contributing a database must also contribute a router that answers only for its own labels and returns `None` otherwise. Release-stage migration becomes one step per database, and `component.toml` declares them so the deployment repository does not have to guess. The stage-2 unapplied-migrations refusal and the sqlite refusal both iterate every configured database — which is only possible because stage 1 runs *after* composition (AD-26). Local substitution is applied automatically by the base, so FR-18 stays true by construction. Readiness treats a contributed database as required unless `component.toml` declares it optional." *Prevents:* "six enforcement points each being answered differently by six epics."
- **AD-22 (binding):** "Readiness checks that every required database answers (AD-9), returns non-200 from process start until first successful contact, and **never re-checks migrations**, because during a rolling deploy an older replica may legitimately run against a newer schema. No entrypoint, task or container command runs migrations; migration is a release-stage step the deployment repository performs before new pods serve, one per database as `component.toml` declares." Liveness "checks nothing external."
- **AD-28 (binding):** `component.toml` "is `core` and always travels. It carries what a component states about *itself*: the adopted-app list, per-database requiredness, per-database release-stage migration steps, the process-model constraints, and **the selected-feature list**." Story 5.1 authors the file and its loader; this story adds one `[[databases]]` entry per contributed alias and reads requiredness back through `load_component_declaration()`.
- **AD-26:** stage 1 is the last statement of every **leaf** settings module — `local.py`, `production.py`, `test.py` — and **`base.py` must not call it**, asserted by a paired gate test. That placement is what puts stage 1 after the AD-8 composition step, and it is the reason per-alias iteration is reachable at all: `base.py` is star-imported by the three leaves, so a call at its end would fire before the leaf composes and would never see a contributed alias. The distinction is load-bearing rather than pedantic, and "every settings module" is the plausible reading and the wrong one.
- **AD-13:** locality is read from the environment and fails closed — absent or unrecognized means deployed. Do not infer local from the settings module, from `DEBUG`, or from `sys.argv`.
- **FR-18 / Story 3.2:** the component runs locally with nothing installed. A contributed database must not break that, and the base — not the application — is what keeps it true.

**Must not do:**
- Do not let a contributed router return `"default"` (or any concrete alias) for models it does not own. `None` is the only correct answer, and it is what lets several routers coexist.
- Do not add a tenth refusal condition. Two existing conditions widen their domain; the resolved count is nine.
- Do not make readiness re-check migrations (AD-22), and do not make liveness touch a database (NFR-2).
- Do not let an application arrange its own local substitution or read `COMPONENT_RUNTIME` in its contribution.
- Do not run migrations from an entrypoint, task, or container command (FR-41, AD-22).

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/settings/composition.py` | UPDATE | Created in Story 9.4. Add the database↔router chain check and the automatic local substitution for contributed aliases. |
| `src/config/startup/` | UPDATE | **Does not exist today** (Story 4.1). Widen the sqlite condition (Story 4.2) and the unapplied-migrations condition (Story 4.3) to iterate every configured alias. |
| `src/config/settings/base.py` | UPDATE | 381 lines. `DATABASES` is built at lines 55–80: `DATABASE_URL` → `POSTGRES_DB` → a sqlite fallback at 73–78 with `NAME = str(BASE_DIR / "db.sqlite3")`, then `DATABASES["default"]["ATOMIC_REQUESTS"] = True` at line 80. **Preserve that chain**; the per-alias substitution mirrors its sqlite branch. Declare `DATABASE_ROUTERS: list[str] = []` here if Story 9.4 did not, so composition appends rather than creates. |
| `src/config/settings/production.py` | UPDATE | 160 lines. Lines 26–28 hold the current single-alias sqlite refusal (`if DATABASES["default"]["ENGINE"].endswith("sqlite3"): raise ImproperlyConfigured(...)`) — range verified. Story 4.2 moves this into `src/config/startup/`; this story is what makes the moved check iterate. If 4.2 has not landed, the widening still belongs in the startup module, not here. |
| Readiness view (Story 5.3) | UPDATE | Does not exist today — Story 5.3 states "no health route exists today … both endpoints are built rather than adapted." Extend it to iterate required aliases. |
| `component.toml` | UPDATE | **Does not exist today** (Story 5.1), which creates it with one `[[databases]]` entry for `default` (`alias`, `required`, `migrate`) and a closed top-level key set. Add one further `[[databases]]` entry per contributed alias. Do **not** add a `release` table or a `[databases.<alias>]` table — both are unknown top-level shapes Story 5.1's loader refuses. |
| `.gitignore` | UPDATE | Lines 61–62 carry `db.sqlite3` and `db.sqlite3-journal`. Add the per-alias glob. |
| `tests/fixtures/tenant_apps/**` | UPDATE | Created in Story 9.4. Add the database-contributing fixture application and its router. |
| `tests/unit/test_contributed_database_refusals.py` | NEW | AC #3, #4. |
| `tests/unit/test_readiness_contributed.py` | NEW | AC #5. |
| `tests/unit/test_contributed_database_declaration.py` | NEW | AC #6 — the two-way reconciliation of `[[databases]]` against the composed `DATABASES`. |
| `tests/integration/test_contributed_database_local.py` | NEW | AC #2. |
| `tests/unit/test_contributed_router.py` | NEW | AC #1. |

Verified today: `src/config/settings/base.py:55-80` matches the description above; `src/config/settings/production.py:26-28` still holds the sqlite refusal; `.gitignore:61-62` holds the two sqlite entries. There is no `DATABASE_ROUTERS` anywhere in the tree, no health route, no `component.toml`, and no `src/config/startup/`.

### Testing Requirements

- Unit: the four `tests/unit/test_*` modules above — settings composition, refusal predicates, readiness logic and TOML reconciliation, all exercisable without a live service.
- Integration: `tests/integration/test_contributed_database_local.py` — `@pytest.mark.integration` on every test; uses `tmp_path` for sqlite files, real migrations, and the local sign-in route; must leave no database file and no registry mutation behind.
- Assertions the ACs demand:
  - a `DATABASES` contribution without a `DATABASE_ROUTERS` contribution raises `ImproperlyConfigured` (AC #1);
  - the router returns `None`, not `"default"`, for labels it does not own (AC #1);
  - the composed local settings are sqlite for every contributed alias while the contribution itself declares no local variant (AC #2);
  - a persona authenticates and readiness returns 200 with nothing installed (AC #2);
  - the fixture app's own page renders through `base.html` and its contributed navigation entry appears, escaped, in the bar (AC #2 — "serves");
  - a deployed runtime with any alias on sqlite refuses, naming the alias (AC #3);
  - unapplied migrations on the contributed alias alone refuse at stage 2 (AC #4);
  - a required contributed alias that does not answer makes readiness non-200; `required = false` does not; an undeclared alias is required (AC #5);
  - `component.toml`'s `[[databases]]` entries and the composed `DATABASES` reconcile in both directions (AC #6).
- Disposition: covers `core` surface (`src/config/`), so the suite is `core` and never pruned.
- AD-20 floor: ninety percent including templates, `COVERAGE_CORE=ctrace` in force. `pixi run ci` must exit 0.

#### Project Structure Notes

The Structural Seed's `src/config/startup/` owns both refusal stages, and `component.toml` is `core` and always travels. This story adds no new module; it widens three existing surfaces (composition, the two refusal conditions, readiness) and adds entries to `component.toml`'s existing `[[databases]]` array — it introduces no new table there and no new top-level key.

Variance today: none of `src/config/startup/`, `component.toml`, the health routes, `src/config/settings/composition.py` or `tests/fixtures/` exists. This story is last in the epic and depends on Stories 3.1/3.2 (locality and substitutions), 4.1–4.3 (the refusal stages), 5.1 (`component.toml`), 5.3 (readiness), 5.5 (release-stage migration) and 9.4 (composition). Sequencing note from the epic: no rework is created by placing this last, because Epic 4 already placed stage 1 as the last statement of every *leaf* settings module — which is what makes composition land before it.

Python 3.14; `dict[str, dict[str, object]]` for the databases mapping; full type hints; Google-style docstrings; no `print()`; `structlog` for any log line, JSON to stdout — a refusal raises `ImproperlyConfigured` and never degrades to a warning.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.7]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-9]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-22]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-28]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — conditions 1 and 7; the count stays nine
- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.3] — stage 1 and stage 2 both iterate every configured database
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.3] — readiness; no health route exists today
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.5] — migration is a release-stage step, one per database as `component.toml` declares
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.2] — the local substitutions this story must not break
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29] — the interface mechanism is `core`; an adopted app extends `base.html`, uses the form styling and contributes navigation entries freely
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.1] — `component.toml`'s `[[databases]]` shape, its closed top-level key set, and the loader this story reads requiredness through
- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.4] — the composition step, the navigation registry contribution, and the fixture applications this story extends

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
