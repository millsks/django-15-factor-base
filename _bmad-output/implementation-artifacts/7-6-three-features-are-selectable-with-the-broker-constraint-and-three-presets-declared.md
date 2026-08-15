# Story 7.6: Three features are selectable, with the broker constraint and three presets declared

Status: ready-for-dev

## Story

As a lead developer,
I want to select any subset of the three features, with invalid pairings named and presets that do not constrain,
so that the selection surface accepts every legitimate request.

## Acceptance Criteria

**Traceability:** FR-24, FR-26, FR-27

1. **Given** the three features
   **When** they are declared
   **Then** background task processing, Redis cache and object storage are each independently selectable
   **And** each is selected or absent, never present-and-disabled

2. **Given** the broker constraint
   **When** the combination space is enumerated
   **Then** it is six valid combinations, not eight
   **And** background task processing without the Redis cache is the excluded pairing

3. **Given** the three presets
   **When** they are declared
   **Then** *Minimal*, *Cached* and *Worker-enabled* set a starting selection and remain fully editable

4. **Given** a selection such as *Minimal plus background task processing plus object storage*
   **When** it is requested
   **Then** it is accepted
   **And** presets do not act as a menu of permitted shapes

5. **Given** every valid combination
   **When** it is requested
   **Then** it is reachable without using a preset

## Tasks / Subtasks

- [ ] Task 1 — Declare the three features as independently selectable (AC: #1)
  - [ ] Complete `[features.<name>]` for all three in `accelerator.toml`, using the canonical names established in Story 7.1: `celery` (background task processing), `redis` (Redis cache), `storage` (object storage). **There is no `ui` feature.** The interface mechanism is immovable core (AD-29, revision 3; FR-3), so no fourth `[features.*]` table may be created here.
  - [ ] Each feature carries `title` (the PRD's prose name, so the portal has a label), `packages`, the non-package surface keys, `constraints`, and nothing that makes it depend on a preset. Under revision 3 no feature owns a package or a path root — AD-33 is retired — so `packages` is legitimately empty for all three, and their surface is dependency entries plus AD-24 regions of `core` paths plus their own tests.
  - [ ] Assert "selected or absent, never present-and-disabled" as a testable property, not a slogan: no feature may be represented by a boolean *setting* the component reads at runtime. There is no `USE_CELERY`, no `USE_REDIS`, no `settings.FEATURES` dict. A feature's presence is the presence of its paths and regions and nothing else. Add a gate test asserting no settings module defines a feature-toggle-shaped name.
  - [ ] Record in the carrier that the three selections are also the three pixi features Epic 8 turns into an `[environments]` matrix (AD-3), so the names must remain valid pixi feature names.

- [ ] Task 2 — Declare the broker constraint (AC: #2)
  - [ ] Declare it as data, on the feature that carries it: `[features.celery] requires = ["redis"]`. One expression, in the carrier, machine-readable — not prose in a comment and not a hardcoded pair in Python.
  - [ ] Record beside it what the constraint *is*: background task processing needs a broker, the broker is Redis, so background task processing without the Redis cache is not a valid pairing. Eight subsets of three features minus the two in which `celery` is selected and `redis` is not equals **six**.
  - [ ] Add a carrier-derived enumeration helper — `Carrier.valid_combinations() -> list[frozenset[str]]` in `tools/materializer/carrier.py` — that computes the space from `[features]` and `constraints`. Do not hardcode the number six or the six sets anywhere; both must fall out of the declaration, so adding a fourth feature or a second constraint does not require finding six literals.
  - [ ] The **enforcement** of this constraint — the materializer refusing an invalid combination and naming the broker constraint — is FR-34, Story 8.5. It is *declared* here and *enforced* there (`epics.md:224`). **Traceability marker, not an acceptance condition for this story.** What this story owes Epic 8 is a declaration precise enough to refuse from.

- [ ] Task 3 — Declare the three presets (AC: #3, #4, #5)
  - [ ] `[presets.<name>]` for exactly three: `minimal`, `cached`, `worker-enabled`. Each carries a `title` matching the PRD's prose name (*Minimal*, *Cached*, *Worker-enabled*), a `description`, and a `selects` list of feature names. **The names changed in revision 3**: *API-only* and *Full web app* no longer name distinguishable selections, because with the interface mechanism core every combination serves both an API and a rendered interface (FR-27, amended). Do not carry the old names forward in a `title`, a comment or a test.
  - [ ] Suggested starting selections, which fall straight out of the new names: `minimal` selects nothing; `cached` selects `redis`; `worker-enabled` selects `celery` and `redis`. What matters for the ACs is not which subset each names but that each is a **starting point** and nothing else.
  - [ ] A preset must be structurally incapable of constraining. It contributes only an initial `selects` list; it carries no `allows`, no `forbids`, no `locked` flag, and no field the materializer could read as a permission. Add a gate test asserting the `[presets.*]` schema admits only `title`, `description` and `selects`.
  - [ ] Every preset's `selects` list must itself be a valid combination under the Task 2 constraint. A preset that names an invalid pairing is a defect; assert it.

- [ ] Task 4 — Prove presets do not gate the selection space (AC: #4, #5)
  - [ ] Add a gate test asserting: for every one of the six valid combinations produced by `valid_combinations()`, materialization input can be constructed from the feature selections alone, with no preset named. This is AC #5, and it is the assertion that stops a preset from becoming a required field.
  - [ ] Add the AC #4 worked example as a named test case: *Minimal plus background task processing plus object storage* — that is, `{celery, redis, storage}`, since *Minimal* selects nothing and the broker constraint pulls `redis` in with `celery`. Assert it is a member of `valid_combinations()`. Record in the test's docstring that the AC's phrasing describes starting from a preset and editing, which is exactly what the preset must permit.
  - [ ] Add a test asserting that every preset's `selects` list is reachable *without* the preset — i.e. that presets add no combination the raw selection space lacks.

- [ ] Task 5 — Reconcile the feature space against `pixi.toml` (AC: #1, #2)
  - [ ] Two-way, in the manner of every other check in this epic: every feature declared in `accelerator.toml` has a matching `feature:<name>` region in `pixi.toml` (Story 7.2 placed them), and every `feature:<name>` marker in `pixi.toml` names a declared feature.
  - [ ] Assert the three canonical names are exactly `celery`, `redis`, `storage` — no synonyms, no aliases, no display names leaking into the marker text, and **no `ui`**. Story 7.2's markers, Story 7.5's storage feature and Epic 8's pixi `[feature.<name>]` tables all key off these strings. Add the negative assertion too: no `feature:ui` marker exists anywhere in the tree, since Story 7.4 makes the interface mechanism core rather than extracting it.
  - [ ] Do **not** create the `[environments]` matrix here. `pixi.toml:141-143` today declares only `default` and `dev`, both `solve-group = "default"`. Building the six pre-locked environments — and the shared `solve-group` that keeps `django-celery-beat`'s `django <6.1` cap from splitting the Django version across combinations — is Story 8.1.

- [ ] Task 6 — Tests (AC: all)
  - [ ] `tests/unit/materializer/test_combinations.py` (NEW): `valid_combinations()` returns six sets; every set containing `celery` also contains `redis`; the two `celery`-without-`redis` subsets are absent; the count is derived, not asserted against a literal list of six hand-written sets.
  - [ ] `tests/unit/materializer/test_presets.py` (NEW): exactly three presets; each `selects` list is a valid combination; the preset schema admits no constraining field; every preset's selection is reachable without the preset.
  - [ ] `tests/integration/materializer/test_feature_space_reconciliation.py` (NEW), `@pytest.mark.integration`: the two-way `accelerator.toml` ↔ `pixi.toml` feature-name check.
  - [ ] `tests/integration/materializer/test_no_feature_toggle_settings.py` (NEW), `@pytest.mark.integration`: AST-level assertion over `src/config/settings/*.py` that no feature-toggle-shaped setting exists (AC #1's "never present-and-disabled").
  - [ ] `pixi run ci` exits 0.

## Dev Notes

### Architecture Constraints

**FR-26 — the broker constraint.** *"Background task processing without the Redis cache is refused at generation rather than emitted as a component that cannot start. The combination space is six valid combinations, not eight."* Declared here; enforced by the materializer in Epic 8 as FR-34 (`epics.md:224`).

**FR-27 — presets pre-select without constraining, and the three were renamed.** *"The three presets — Minimal, Cached, Worker-enabled — set a starting selection and remain fully editable. Every valid combination is reachable without using a preset. A selection such as Minimal plus background task processing plus object storage is accepted; presets do not act as a menu of permitted shapes."* The rename is a consequence of revision 3, not a cosmetic change: with the interface mechanism core, *API-only* and *Full web app* describe the same materialized shape, so they no longer name distinguishable selections. The failure the requirement prevents is unchanged — a preset list quietly becoming the menu, so a lead developer who wants *Minimal* plus background tasks plus object storage is told to pick one of three shapes.

**FR-24 — one carrier.** *"A lead developer can select any subset of background task processing, Redis cache, and object storage. Every feature's surface is declared in a single machine-readable artifact with a named location, which is the only place a feature's extent is defined."* Three features, not four. AD-1 forbids a second declaration site: the feature names, the constraint and the presets live in `accelerator.toml` and are read from there by everything.

**AD-3 — the features are native pixi features.** *"The selectable features are declared as pixi features with an `[environments]` matrix, so one `pixi.lock` yields six pre-locked environments; combination *n*'s gate runs its materialized source under environment *n*. **All six environments share one `solve-group`**, without which `django-celery-beat`'s `django <6.1` cap makes the two Celery combinations resolve a different Django from the other four and SC-1 stops meaning what it says."* That matrix is Story 8.1's work; this story only fixes the names it will use.

**Revision 3 — why there are three features and not four.** The server-rendered interface stopped being selectable. The Django admin is immovable core (FR-1) and already required the template loader, `base.html`, the error templates, static files and whitenoise in every combination, so `feature:ui` could only have removed about 16 KB of templates, 8 KB of static assets and roughly 100 lines of Python — and **no dependency**, because the crispy-styled allauth templates render the FR-4 sign-in flow everywhere. Halving the combination space was the better trade. **AD-33 is retired** with it: there is no `src/features/`, no `django_ui` or `django_storage` package, and no feature owns a code surface. This story's job is to declare three features, and to make sure a fourth cannot creep back in through a name.

**AD-2 — selected or absent.** `feature:<name>` paths travel *only where selected*. There is no third state. A runtime flag that disables a feature whose code is still present contradicts AD-2, FR-28 and SC-2 simultaneously, and it defeats the coverage-based orphan detector, because present-and-disabled code reports as uncovered rather than as absent.

**AD-24 — sub-file surface.** Where a feature's surface is a fragment of a `core` file, it is a declared region delimited by paired `feature:<name>` / `/feature:<name>` line comments — never a conditional import, never settings-module inheritance, never `try/except ImportError`, and never an `if` on a feature flag.

**FR-22 — the constraint is about deployment only.** *"Locally, all six valid combinations run with no broker."* The constraint governs which combinations exist, not how they run locally. Local development substitutes eager task execution (FR-18) in every combination that selected background task processing.

**Project standards.** Pixi is the only runner. Python 3.14 only. conda-forge only. PEP 8 / 120 / full type hints / Google docstrings. Never `print()`, never stdlib `logging`, never bare `except:`, never `except X: pass`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `accelerator.toml` | UPDATE | Complete `[features.*]`; add `[features.celery] requires = ["redis"]`; add the three `[presets.*]` tables. Preserve `[dispositions]`, `[[regions]]`, `[[parameters]]`, `[guaranteed_surface]`, `[immovable_core]` from Stories 7.1–7.5. |
| `tools/materializer/carrier.py` | UPDATE | Add `Carrier.presets()`, `Carrier.constraints()` and `Carrier.valid_combinations()`. Preserve the Story 7.1 loader contract (`machinery` default, ambiguity rejection) and the accessors Stories 7.2 and 7.3 added. |
| `tests/unit/materializer/test_combinations.py` | NEW | Combination-space unit tests. |
| `tests/unit/materializer/test_presets.py` | NEW | Preset schema and reachability unit tests. |
| `tests/integration/materializer/test_feature_space_reconciliation.py` | NEW | Two-way carrier ↔ `pixi.toml` feature-name check, `@pytest.mark.integration`. |
| `tests/integration/materializer/test_no_feature_toggle_settings.py` | NEW | AST assertion that no feature-toggle setting exists, `@pytest.mark.integration`. |

**No source file under `src/` is edited by this story.** Nothing about the reference application changes; this is declaration plus assertions.

**Repository state, verified 2026-08-15.** `pixi.toml:141-143` declares exactly two environments, `default` and `dev`, both `solve-group = "default"`. There are no `[feature.<name>]` tables for `celery`, `redis` or `storage` — the only pixi feature that exists is `dev` (`[feature.dev.dependencies]` `:106-132`, `[feature.dev.tasks]` `:184-187`, `[feature.dev.activation.env]` `:152-156`). The six-combination matrix does not exist. The `django-celery-beat` comment at `pixi.toml:33-34` already records the `django <6.1` cap that makes AD-3's shared solve-group load-bearing.

**The six combinations, for reference.** With `storage` free (2 states) and the `{celery, redis}` axis restricted to `{}`, `{redis}`, `{celery, redis}` (3 states, the fourth — `{celery}` — excluded), the space is 2 × 3 = 6. Written out: `¬celery` × {¬redis, redis} × {¬storage, storage}, plus `celery ∧ redis` × {¬storage, storage}. The dev agent must not hardcode this; it must fall out of `valid_combinations()`.

### Testing Requirements

- Unit: `tests/unit/materializer/test_combinations.py` and `test_presets.py` — isolated, milliseconds, inline TOML fixtures plus the real carrier where the assertion is about the real declaration.
- Integration: `tests/integration/materializer/test_feature_space_reconciliation.py` and `test_no_feature_toggle_settings.py`, every test `@pytest.mark.integration`, read-only against the repository.
- The combination count must be asserted as a derived property (`len(valid_combinations()) == 6` given the declared features and constraints), plus a structural assertion that no valid combination contains `celery` without `redis`. Do not write a test that compares against six literal frozensets — it would pass while `valid_combinations()` is a hardcoded list, which is the implementation this story forbids.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` in force (AD-20).
- Test disposition: these cover `machinery` and carry `machinery`.

#### Project Structure Notes

- This story adds no source structure. It closes the `[features]` and `[presets]` slots Story 7.1 opened, and it is the last declaration Epic 8's materializer needs from the selection axis.
- The names `celery`, `redis`, `storage` are load-bearing across five places: `[features.<name>]` in `accelerator.toml`, `feature:<name>` dispositions, `feature:<name>` / `/feature:<name>` markers in the region-bearing `core` files Story 7.2 declares, pixi `[feature.<name>]` tables (Epic 8), and the `[environments]` matrix names (Epic 8). Fixing them here, with a two-way reconciliation test, is what stops a rename in Epic 8 from being a silent partial rename.
- The PRD's prose names — background task processing, Redis cache, object storage — are the `title` fields. The portal order surface will show titles and send names; the field list for that surface is an open item owned by the portal team, and until it exists the fixture set covers the AD-25 parameters and the three feature booleans (spine Open Items; Story 8.6).

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-3]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Open Items] — the portal order surface
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.6]
- [Source: _bmad-output/planning-artifacts/epics.md#Cross-epic threads] — line 224: FR-26 declared here, enforced as FR-34 in Epic 8
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.5] — the materializer's refusal; traceability marker, not an acceptance condition here
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.1] — the six pre-locked environments
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Revision 3 — the interface mechanism becomes core] — three features, six combinations, and the preset rename
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-24] — three selectable features
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#Glossary] — *Preset*: *Minimal*, *Cached*, *Worker-enabled*
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-26]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-27]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-22]
- Repository, verified 2026-08-15: `pixi.toml:33-34,106-132,141-143,152-156,184-187`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
