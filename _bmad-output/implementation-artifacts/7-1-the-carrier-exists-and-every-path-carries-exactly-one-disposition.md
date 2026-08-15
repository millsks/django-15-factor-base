# Story 7.1: The carrier exists and every path carries exactly one disposition

Status: ready-for-dev

## Story

As a lead developer,
I want one declarative catalogue that is the only place a feature's extent is defined,
so that nothing infers what a feature owns from naming or directory layout.

## Acceptance Criteria

**Traceability:** FR-24 · AD-1, AD-2 · NFR-5 · SC-2

1. **Given** `accelerator.toml`
   **When** it is created
   **Then** it lives at the repository root
   **And** it is classified `machinery` and never travels

2. **Given** a feature
   **When** its extent is declared
   **Then** the carrier declares its package surface, its non-package surface — settings fragments, application modules, observability wiring, templates, static assets, tests — its constraints, and the presets that pre-select it
   **And** nothing infers any of that from a naming convention

3. **Given** the four input dispositions
   **When** a path is classified
   **Then** it is exactly one of `core`, `feature:<name>`, `tenant` or `machinery`
   **And** the four are exhaustive and mutually exclusive

4. **Given** a path with no declaration
   **When** it is classified
   **Then** it defaults to `machinery`
   **And** so a file no declaration claims cannot silently travel into every component

5. **Given** input reconciliation against the reference application
   **When** the gate runs
   **Then** a path claimed by no disposition fails
   **And** a claim naming a path that does not exist fails

6. **Given** the disposition question
   **When** it is answered
   **Then** it answers only whether a path travels
   **And** what is substituted inside it is the separate parameter axis

## Tasks / Subtasks

- [ ] Task 1 — Create `accelerator.toml` at the repository root with the full top-level table skeleton (AC: #1, #2)
  - [ ] Create `accelerator.toml` (NEW, repository root). Top-level tables, in this order: `[accelerator]` (version, a short `description`), `[features.<name>]` (one per feature), `[dispositions]`, `[regions]` (Story 7.2 populates), `[parameters]` (Story 7.3 populates), `[presets.<name>]` (Story 7.6 populates), `[tenant]`, `[verification]`, `[coverage]` (Story 7.8 populates), `[contributable]`.
  - [ ] Use the three canonical feature names from the AD-4 dependency graph: `celery` (background task processing), `redis` (Redis cache), `storage` (object storage). These strings are the `<name>` in `feature:<name>` dispositions, in the AD-24 markers, and in the pixi `[feature.<name>]` tables Epic 8 builds. Do not invent alternative spellings. There is no `ui` feature — the interface mechanism is immovable core (AD-29, revision 3, FR-3), so no `feature:ui` name may be created here or anywhere.
  - [ ] Under `[tenant]`, declare `root = "src/django_apps/"` — the tenant-space location, per AD-1's enumerated contents. The directory does not exist in the tree yet (Epic 9 creates it); declare the location regardless, and see Task 4's `allow_missing` handling.
  - [ ] Under `[verification]`, declare `pinned_subset = []` with a comment recording that AD-19's pinned all-pairs subset is populated when the six-combination matrix exists (Epic 8). An empty list is a declared-but-unpopulated slot, not an omission.
  - [ ] Under `[contributable]`, declare the AD-8 closed contributable surface **by explicit key, never by namespace**. Record in a comment that this list and the FR-17 allowlist are ONE declaration (AD-8, AD-26) authored in Epic 4 and extended in Epic 9 — this story creates the slot and moves nothing that Epic 4 has not yet authored. Record too that **`src/config/startup/` holds the authoritative copy and `accelerator.toml` mirrors it**, with a gate test asserting equality (AD-26): the carrier is `machinery` and never travels, while the composition step runs at settings import inside a materialized component that does not have it, so the carrier cannot be the runtime authority. The surface includes the **navigation registry** (AD-8) — an ordered sequence contributed to exactly like `INSTALLED_APPS`, append-only in adopted-app-list order, whose entries are data (label, URL name, optional permission) and never markup.
  - [ ] Put reasoning beside the configuration it constrains, as `pixi.toml` already does (spine Consistency Conventions, "Rationale").

- [ ] Task 2 — Declare each feature's package and non-package surface (AC: #2)
  - [ ] For each of the three features write `[features.<name>]` with: `title` (the PRD's prose name), `packages` (the conda-forge package names the feature adds), `paths` (its owned path list — may be empty at this story; Stories 7.5 and 7.7 fill them), `constraints` (Story 7.6 populates `celery.requires = ["redis"]`), and `presets` back-reference handled in `[presets]`.
  - [ ] `features.celery.packages` = the Celery block already in `pixi.toml`: `celery`, `django-celery-beat`, `django-timezone-field`, `python-crontab`, `cron-descriptor`, `opentelemetry-instrumentation-celery`.
  - [ ] `features.redis.packages` = `django-redis`, `redis-py`, `hiredis`, `opentelemetry-instrumentation-redis`.
  - [ ] `features.storage.packages` = `django-storages`, `boto3` — neither is in `pixi.toml` today; Story 7.5 adds them. Declare them here and let Story 7.5's landing satisfy the declaration.
  - [ ] `django-crispy-forms` and `crispy-bootstrap5` are **`core`**, not a feature's packages. `templates/allauth/elements/field.html` and `fields.html` use `crispy` to render the FR-4 interactive sign-in flow, which is immovable core, so the form-styling packages are present in every combination (AD-29, revision 3). Do not declare them under any feature.
  - [ ] Enumerate the non-package surface categories explicitly as separate keys so nothing is inferred: `settings_fragments`, `app_modules`, `observability`, `templates`, `static`, `tests`. An empty list is a legitimate declaration; an absent key is not. Under the revision-3 model no feature owns a package or a path root (AD-33 is retired) — `celery`, `redis` and `storage` own dependency entries and AD-24 regions of `core` paths, plus their own tests, so several of these lists are legitimately empty.

- [ ] Task 3 — Declare a disposition for every tracked path in the reference application (AC: #3, #4, #6)
  - [ ] Enumerate the input set as **git-tracked paths** (`git ls-files`), not the working tree. The working tree carries `.pixi/`, `__pycache__/`, `db.sqlite3`, `coverage.xml`, `dist/` and `site/`, none of which is source and none of which should need a declaration.
  - [ ] `core`: `manage.py`, `src/config/**`, `src/django_service/**` (AD-29 — its entirety, no exceptions), `component.toml` (AD-28; created in Epic 5), `README.md`, `LICENSE`, `CHANGELOG.md`, `.gitignore`, `.gitattributes`, `.pre-commit-config.yaml`, `mkdocs.yml`, `docs/**`, `pyproject.toml`, `pixi.toml`, `pixi.lock`, `sonar-project.properties`, and the `tests/` paths covering `core` surface.
  - [ ] `machinery`: `accelerator.toml` itself (AC #1), `tools/materializer/**` and `tools/harness/**` — the Structural Seed names both, the materializer being the projection of the carrier (Epic 8) and `tools/harness/` the six-combination verification runner — `Dockerfile` (AD-15, Epic 5), `_bmad/**`, `_bmad-output/**`, `.agents/**`, `.claude/**`, `.bmad-loop/**`, `.github/agents/**`, `.github/copilot/**`. Record explicitly that `machinery` is the default for *behaviour* but **not for enumeration** (AD-2, correction 14): input reconciliation still requires every path present in the tree to be claimed, so these entries are load-bearing rather than documentary.
  - [ ] The Structural Seed is a **shape, not an inventory**. Paths it does not draw still need explicit entries — at minimum `.github/`, `docs/`, `mkdocs.yml`, `sonar-project.properties`, `manage.py`, `CHANGELOG.md`, `LICENSE`, `README.md`, `_bmad/`, `_bmad-output/`, `.agents/`, `.bmad-loop/` and `.claude/`, all of which exist today.
  - [ ] Split `.github/` and `docs/` per FR-37: workflows that gate the *component* travel as `core`; workflows that gate the *accelerator's own machinery* (SonarCloud for this repository, the six-combination matrix, release automation) are `machinery`. Decide each of `.github/workflows/{ci,labeler,release,sonarqube,stale}.yml` individually and record the reason inline. Same for `docs/`: component-facing documentation travels (NFR-8), accelerator-facing does not.
  - [ ] `tenant`: `src/django_apps/**`.
  - [ ] `feature:<name>`: leave empty at this story where a later story owns the enumeration (7.5 for `storage`, 7.7 for the full sweep). Every path must still be claimed by *something* for AC #5 to pass — until 7.5/7.7 land, storage surface is claimed as `core` and 7.5/7.7 re-disposition it. State that transition in a comment so the intermediate state is not mistaken for the final one. The interface surface is **not** in that transitional set: `base.html`, `_navbar.html`, the error templates, form styling, static-file serving and the user profile views are permanently `core` (AD-29), and the `home`/`about` demonstration pages are deleted by Story 7.4 rather than re-dispositioned.
  - [ ] Add a comment at the head of `[dispositions]` stating AD-2 verbatim on scope: disposition answers only *does this path travel*; substitution inside a path is the orthogonal AD-25 parameter axis (AC #6).

- [ ] Task 4 — Build the carrier loader and the two-way input reconciler (AC: #3, #4, #5)
  - [ ] Create `tools/materializer/__init__.py` and `tools/materializer/carrier.py` (NEW). `carrier.py` parses `accelerator.toml` with `tomllib` (stdlib, Python 3.14) and returns typed structures. Full type hints on public signatures; Google-style docstrings; `X | Y` / `list[X]` / `dict[K, V]` only.
  - [ ] Public surface: `load_carrier(path: Path) -> Carrier`; `Carrier.disposition_for(path: str) -> Disposition`; `Carrier.declared_paths() -> list[str]`; `Carrier.features() -> dict[str, Feature]`. Model `Disposition` as a frozen dataclass or `StrEnum`-plus-payload that makes `core` / `feature:<name>` / `tenant` / `machinery` **exhaustive and mutually exclusive by construction** (AC #3) — a path resolving to two dispositions must be a load-time error, not a test-time one.
  - [ ] `disposition_for` returns `machinery` for any path no rule claims (AC #4). Implement the default in the loader, once, so no caller can forget it.
  - [ ] Create `tools/materializer/reconcile.py` (NEW) with `reconcile_input(carrier: Carrier, tracked: list[str]) -> list[str]` returning failure messages. Two directions: (a) every tracked path is **claimed by a declaration** — the `machinery` default settles behaviour, not enumeration (AD-2, correction 14), so an unlisted path is a reconciliation failure even though `disposition_for` would answer `machinery` for it; the check also rejects a path resolving *ambiguously* and a `core`/`feature`/`tenant` glob so broad it silently swallows a path a later story must claim individually; (b) every declared path or glob matches at least one tracked path (AC #5, second clause). Honour `allow_missing = true` on the small set of forward-declared entries (`component.toml`, `Dockerfile`, `src/django_apps/`, `tools/**`) and require a reason string beside each.
  - [ ] Never `print()`. Reconciliation failures are returned as data and asserted in the gate test; any logging goes through `structlog`.

- [ ] Task 5 — Wire reconciliation into the gate (AC: #5)
  - [ ] Add `tests/unit/materializer/__init__.py` and `tests/unit/materializer/test_carrier.py` (NEW): loader unit tests over inline TOML fixtures — exhaustiveness, mutual exclusion, `machinery` default, ambiguous-claim rejection.
  - [ ] Add `tests/integration/materializer/__init__.py` and `tests/integration/materializer/test_input_reconciliation.py` (NEW), every test marked `@pytest.mark.integration`: run `reconcile_input` against the real `accelerator.toml` and the real `git ls-files` output and assert zero failures. This is the gate test AC #5 names.
  - [ ] Add negative tests: a temp carrier claiming `src/does/not/exist.py` fails; a temp tracked set carrying a path that only an over-broad glob would claim is reported.
  - [ ] Do not modify `[tool.coverage.run] omit` to hide `tools/`. See Project Structure Notes — the `include = [ "src/**" ]` decision is deliberate and must be made explicitly, not by omission.

- [ ] Task 6 — Tests and gate (AC: all)
  - [ ] `pixi run test` for the unit layer, `pixi run test-integration` for the reconciler, then `pixi run ci` must exit 0.
  - [ ] Every new module carries tests in the same commit. Coverage floor is 90% including templates (AD-20).

## Dev Notes

### Architecture Constraints

**AD-1 — `accelerator.toml` is the single declarative catalogue.** Binding rule: *"Every feature's package surface, non-package surface, constraints and presets; every path's disposition; every parameter and its sites; the tenant-space location; the pinned all-pairs subset; and the closed contributable surface are declared in `accelerator.toml` at the repository root, and nowhere else. It is `machinery` and never travels."* Prevents: *"five PRD requirements depending on a declaration with no file, no format and no owner; a feature's extent being inferred from directory layout."*

- **Forbidden:** a second declaration site. If a fact belongs in the list above, it goes in `accelerator.toml` and is read from there. Do not mirror it into `pyproject.toml`, a Python constants module, or a second TOML file.
- Anything a *component* must know about itself at runtime or deploy time belongs in `component.toml` instead (AD-28). `component.toml` does not exist yet — Epic 5 creates it. Do not create it here, and do not put adopted-app lists, per-database requiredness, or process-model replica counts into `accelerator.toml`.

**AD-2 — Every path carries exactly one disposition.** Binding rule: *"Four input dispositions, exhaustive and mutually exclusive — `core` (always travels), `feature:<name>` (travels only where selected), `tenant` (never judged, never pruned), `machinery` (never travels). Unlisted defaults to `machinery`. Disposition answers only does this path travel; what is substituted inside it is the orthogonal parameter axis (AD-25), and feature-owned regions inside a `core` path are AD-24."* And: *"Two reconciliation checks, both in the gate. **Input**, against the reference application: a path claimed by no disposition fails; a claim naming a path that does not exist fails. Unlisted defaulting to `machinery` settles *behaviour*, not *enumeration* — input reconciliation still requires every path present in the tree to be claimed, so the carrier's disposition list is the inventory."*

- Prevents: *"an unlisted path silently travelling into every component; a developer's own app being deleted or reported as an orphan; a generated artifact having no legal existence."*
- **Output** reconciliation (against each materialized tree) is Story 8.7's, not this story's. Build only the input half here.

**AD-29 — no `feature:*` inside `src/django_service/`.** Every path under `src/django_service/` is `core`. Story 7.4 adds the gate test that asserts it; this story must not create a `feature:*` claim there in the meantime.

**AD-3 — the reference application stays real.** *"The reference application remains a real, runnable, gateable Django application throughout."* Creating the carrier changes no application behaviour. If `pixi run ci` behaves differently after this story for any reason other than the new reconciliation test, something is wrong.

**Consistency Conventions.** Hand-authored declarations are TOML and visible; machine-written records are JSON and hidden. `accelerator.toml` is hand-authored TOML. Test location: accelerator and base tests live under `tests/` mirroring `src/` and carry the disposition of what they cover.

**Project standards.** Pixi is the only runner — `pixi run python`, `pixi run test`, `pixi run ci`; never `pip`, `uv`, or bare `python`/`pytest`. Python 3.14 only. conda-forge only; `[pypi-dependencies]` carries the editable self-install and nothing else. PEP 8, line length 120, full type hints on public signatures, Google-style docstrings. Never `print()`; never stdlib `logging` — `structlog` only. Never bare `except:`; never `except X: pass`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `accelerator.toml` | NEW | The catalogue. Does not exist today. Repository root, sibling to `pixi.toml`. |
| `tools/materializer/__init__.py` | NEW | `tools/` does not exist today. Package init. |
| `tools/materializer/carrier.py` | NEW | `tomllib` loader, typed carrier model, `machinery` default, ambiguity rejection. |
| `tools/materializer/reconcile.py` | NEW | Two-way input reconciliation, returns failure messages as data. |
| `tests/unit/materializer/__init__.py` | NEW | Test package init (`tests/unit/users/__init__.py` is the existing precedent). |
| `tests/unit/materializer/test_carrier.py` | NEW | Loader unit tests over inline TOML. |
| `tests/integration/materializer/__init__.py` | NEW | Test package init. |
| `tests/integration/materializer/test_input_reconciliation.py` | NEW | The AD-2 input-reconciliation gate test. `@pytest.mark.integration`. |
| `pyproject.toml` | UPDATE | Today `[tool.coverage.run] include = [ "src/**" ]` (`:161`) excludes `tools/` from measurement, and `[tool.ruff] lint.isort.known-first-party = [ "config", "django_service", "tests" ]` (`:113`) does not know `tools`. Decide and record both; see Project Structure Notes. Preserve everything else — this file also carries the ruff rule set, the hatch build config AD-7 rewrites in Story 1.6, pytest config, coverage config and the git-cliff config. |

**Verified against the tree, 2026-08-15:** the tracked root files are exactly `.gitattributes`, `.gitignore`, `.pre-commit-config.yaml`, `CHANGELOG.md`, `LICENSE`, `README.md`, `manage.py`, `mkdocs.yml`, `pixi.lock`, `pixi.toml`, `pyproject.toml`, `sonar-project.properties`. `db.sqlite3`, `coverage.xml`, `dist/` and `site/` exist in the working tree but are untracked.

**Does not exist yet** and must not be assumed: `accelerator.toml`, `component.toml`, `Dockerfile`, `tools/`, `src/django_apps/`, `src/config/authorization/`, `src/config/startup/`.

### Testing Requirements

- Unit: `tests/unit/materializer/test_carrier.py`. Isolated, milliseconds, no filesystem beyond `tmp_path`. Assert: (a) each of the four disposition forms parses; (b) a path claimed twice raises at load time; (c) an unlisted path resolves to `machinery`; (d) `core`, `tenant` and `feature:<name>` never coincide for one path.
- Integration: `tests/integration/materializer/test_input_reconciliation.py`, every test `@pytest.mark.integration`. Assert: `reconcile_input` over the real carrier and the real tracked-path set returns an empty failure list. Assert both negative directions against `tmp_path` fixtures. Each test must leave resources as it found them — read-only against the repository, writes only under `tmp_path`.
- Coverage floor is 90% including templates, `COVERAGE_CORE=ctrace` in force (AD-20); the floor is enforced by `pixi run test-cov` (`pixi.toml:196`, `--cov-fail-under=90`).
- Test disposition convention (spine Consistency Conventions): accelerator and base tests live under `tests/` mirroring `src/` and carry the disposition of what they cover. `tests/unit/materializer/` and `tests/integration/materializer/` cover `machinery`, so they are `machinery` — declare them so in `[dispositions]` in this story.

#### Project Structure Notes

- The Structural Seed places `accelerator.toml` and `component.toml` at the root and `tools/materializer/` and `tools/harness/` beside `src/` and `tests/`. This story creates `accelerator.toml` and `tools/materializer/`; `component.toml` is Epic 5's and `tools/harness/` — the six-combination verification runner, distinct from the materializer — is Epic 8's. The Seed is a shape and not an inventory: everything it does not draw still needs an explicit disposition entry (AD-2).
- **Variance to resolve, and record the decision inline:** `[tool.coverage.run] include = [ "src/**" ]` (`pyproject.toml:161`) means nothing under `tools/` is coverage-measured. AD-20 makes the omit/exclude surface closed and carrier-declared, and Story 7.8 moves that declaration into `accelerator.toml`. Adding measurable code outside `src/**` without deciding this is exactly the silent narrowing CG-1 forbids. Recommended: extend `include` to `[ "src/**", "tools/**" ]` so materializer code is measured, and record the change beside the Story 1.5 declaration so 7.8's move carries it. If the dev agent decides otherwise, the reason must be written into `accelerator.toml`'s `[coverage]` comment, not left implicit.
- `lint.isort.known-first-party` at `pyproject.toml:113` lists `config`, `django_service`, `tests`. Adding `tools` keeps import ordering stable across the new package.
- `tools/` is not on the import path (`[tool.pytest.ini_options] pythonpath = [ "src", "." ]`, `pyproject.toml:149`). `"."` makes `tools.materializer` importable from tests today. Note that Story 1.6 (AD-7) removes the pytest `pythonpath` setting entirely in favour of the hatch `sources` remapping — if Story 1.6 has already landed, confirm `tools.materializer` still imports under pytest and fix at the retained declaration site, never by re-adding a second one.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-3]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-8]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-19]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-28]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Structural Seed]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.1]
- [Source: _bmad-output/planning-artifacts/epics.md#Requirements Inventory] — FR-24, FR-37; the "Starter template: none" note establishing this is a brownfield declaration step, not a scaffold
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#SC-2]
- Repository, verified 2026-08-15: `pyproject.toml:113,149,161`; `pixi.toml:196`; tracked root file set via `git ls-files`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
