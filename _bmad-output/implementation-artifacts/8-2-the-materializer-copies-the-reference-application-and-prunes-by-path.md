# Story 8.2: The materializer copies the reference application and prunes by path

Status: ready-for-dev

## Story

As a platform engineer,
I want a materializer that produces a combination's source by removing the paths that combination did not select,
so that the six-combination claim becomes provable before the FreeMarker transition rather than after it.

## Acceptance Criteria

**Traceability:** FR-30 · AD-2, AD-3

1. **Given** a valid combination
   **When** it is materialized
   **Then** the materializer copies the reference application and removes every path the carrier assigns to a feature the combination did not select
   **And** the result is a self-contained source tree

2. **Given** paths dispositioned `core` or `tenant`
   **When** any combination is materialized
   **Then** they are present in the output

3. **Given** the materializer, the carrier and the fixture set
   **When** output is produced
   **Then** all three are excluded from it

4. **Given** the reference application
   **When** materialization has run
   **Then** it remains a real, runnable, gateable Django application throughout

## Tasks / Subtasks

- [ ] Task 1: Create the materializer package skeleton at `tools/materializer/` (AC: #1)
  - [ ] `tools/materializer/__init__.py` — package marker, no logic.
  - [ ] `tools/materializer/errors.py` — `MaterializerError(Exception)` base; `CarrierError`, `InvalidCombinationError`, `ReconciliationError` subclasses. Never raise bare `Exception`; never `except:`; never `except X: pass`.
  - [ ] `tools/materializer/logging.py` — a `get_logger()` returning a `structlog` bound logger configured for JSON to stdout. Never `print()`. Never stdlib `logging`.
  - [ ] Add `tools/` to `[tool.mypy]`'s checked set and to `[tool.ruff] src`; the module must pass strict type checking and lint like `src/`.

- [ ] Task 2: Load and validate the carrier (AC: #1, #2)
  - [ ] `tools/materializer/carrier.py` — `load_carrier(path: Path) -> Carrier` reading `accelerator.toml` with `tomllib`. `Carrier` is a frozen dataclass exposing `dispositions: dict[str, Disposition]`, `features: frozenset[str]`, `regions`, `parameters`, `generated_artifacts`.
  - [ ] `Disposition` is an enum with exactly four members — `CORE`, `FEATURE`, `TENANT`, `MACHINERY` — exhaustive and mutually exclusive, with `FEATURE` carrying the feature name. An unlisted path resolves to `MACHINERY`; implement that as the default in the resolver, not as a carrier entry.
  - [ ] `resolve_disposition(rel_path: str) -> Disposition` applies the most specific declared prefix; a path matched by two equally specific claims raises `CarrierError`.

- [ ] Task 3: Model the combination (AC: #1)
  - [ ] `tools/materializer/combination.py` — frozen `Combination` dataclass with the three booleans `celery`, `redis`, `storage`; `selected: frozenset[str]` property; `identifier` property returning the selected names sorted and joined with `-`, or `none`. There is no `ui` boolean — the interface mechanism is `core` (AD-29, revision 3).
  - [ ] `enumerate_valid() -> tuple[Combination, ...]` returning exactly six, in a fixed sorted order — this order is the harness's canonical order and must not depend on set iteration.
  - [ ] Do not implement refusal here; Story 8.5 owns `validate()` and its message.

- [ ] Task 4: Implement subtractive path pruning (AC: #1, #2, #3)
  - [ ] `tools/materializer/paths.py` — `travels(disposition, combination) -> bool`: `CORE` and `TENANT` always travel; `FEATURE(name)` travels only when `name` is selected; `MACHINERY` never travels.
  - [ ] `materialize(source_root, dest_root, combination, carrier) -> None` in `tools/materializer/materialize.py`: walk the reference application, and for each path copy it when `travels()` is true and skip it otherwise. Copy, then remove — the operation must be expressible as "copy the reference application and remove what was not selected" (AD-3) and must never mutate `source_root`.
  - [ ] Skip `.git/`, `.pixi/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `dist/`, `site/`, `db.sqlite3`, `.coverage`, `coverage.xml` by declaring them `machinery` in the carrier rather than by hardcoding a list in the materializer — AD-1 forbids a second declaration site.
  - [ ] `tools/materializer/cli.py` with a `main(argv)` and a `if __name__ == "__main__"` guard, invoked as `pixi run python -m tools.materializer <combination-id> <dest>`. Add a `materialize` pixi task wrapping it.

- [ ] Task 5: Prove the accelerator's own machinery is excluded (AC: #3)
  - [ ] Assert in tests that `tools/`, `accelerator.toml` and the fixture set are absent from every output tree. They are absent because they are `machinery`, not because of a special case — do not add a special case.
  - [ ] Note: AD-25 places fixture values inside `accelerator.toml` `[parameters]`. If a separate fixture file is created, it must be declared `machinery` in the carrier; either way AC #3 is discharged by disposition alone.

- [ ] Task 6: Tests (AC: #1, #2, #3, #4)
  - [ ] `tests/unit/materializer/test_carrier.py` — disposition resolution, the `machinery` default for unlisted paths, mutual exclusivity, duplicate-claim `CarrierError`.
  - [ ] `tests/unit/materializer/test_combination.py` — exactly six; stable enumeration order; identifier formatting.
  - [ ] `tests/unit/materializer/test_paths.py` — the `travels()` truth table across all four dispositions and both selection states.
  - [ ] `tests/integration/materializer/test_materialize.py` (`@pytest.mark.integration`, `tmp_path`) — materialize each of the six into `tmp_path`; assert every `core` and `tenant` path present in all six; assert each `feature:<name>` path present in exactly the combinations selecting it; assert `tools/`, `accelerator.toml`, `_bmad/`, `_bmad-output/` absent from all six.
  - [ ] `tests/integration/materializer/test_reference_application_unchanged.py` (`@pytest.mark.integration`) — hash the reference tree before and after materializing all six and assert it is unchanged, discharging AC #4.

## Dev Notes

### Architecture Constraints

- **AD-3** (binding): "The materializer copies the reference application and removes what the carrier says the combination did not select, at path granularity (AD-2) and region granularity (AD-24)... The reference application remains a real, runnable, gateable Django application throughout." Materialization is **subtractive**. It does not generate, template, or rewrite structure — anything that is not a copy-then-remove is out of contract, with the single exception of declared generated artifacts (AD-2, AD-17).
- **AD-2** (binding): "Four *input* dispositions, exhaustive and mutually exclusive — `core` (always travels), `feature:<name>` (travels only where selected), `tenant` (never judged, never pruned), `machinery` (never travels). Unlisted defaults to `machinery`." *Prevents:* "an unlisted path silently travelling into every component; a developer's own app being deleted or reported as an orphan; a generated artifact having no legal existence." Disposition answers only *does this path travel*; substitution inside it is the orthogonal parameter axis (AD-25) and sub-file regions are AD-24.
- **AD-1** (binding): every disposition, parameter, constraint and preset is declared in `accelerator.toml` "and nowhere else. It is `machinery` and never travels." **A second declaration site is forbidden** — no ignore list, no feature-to-path mapping and no skip list may live in the materializer's source.
- **AD-2, `tenant`**: `tenant` paths are "never judged, never pruned". `src/django_apps/` has no `__init__.py` (AD-6) — the copier must not create one and must not treat a directory without `__init__.py` as non-source.
- **AD-2, enumeration**: "Unlisted defaulting to `machinery` settles *behaviour*, not *enumeration* — input reconciliation still requires every path present in the tree to be claimed, so the carrier's disposition list is the inventory. The Structural Seed... is a shape and not an inventory." So the `MACHINERY` default in Task 2 is the resolver's behaviour for a path the carrier did not claim, and it is **not** a licence to leave paths unclaimed: `.github/`, `docs/`, `mkdocs.yml`, `sonar-project.properties`, `manage.py`, `CHANGELOG.md`, `LICENSE`, `README.md`, `_bmad/`, `_bmad-output/`, `.agents/`, `.bmad-loop/` and `.claude/` all need explicit entries. Story 7.1 owns authoring them; this story must not rely on the default to cover them.
- **AD-29**: no `feature:*` disposition may apply to any path inside `src/django_service/`. The materializer does not need to special-case this; Story 7.4 asserts it against the carrier. Do not add a second check here. Revision 3 puts the interface mechanism inside that core — `base.html`, `_navbar.html` and the navigation registry, the error templates, the form styling, static-file serving and the user profile views travel in every combination.
- **AD-33 is retired.** There is no `src/features/`, no feature package and no third import root, so there is no feature root for the materializer to prune. The three features own regions of `core` paths (AD-24) and dependency entries; at path granularity a feature's claim is a claim over ordinary `core`-tree paths, never over a package of its own.
- **Region pruning is Story 8.3.** This story stops at path granularity. Do not implement marker handling.
- **Refusal of invalid combinations is Story 8.5.** This story assumes a valid combination.
- **The provenance stamp is Story 8.11.** Do not write `.accelerator.json` here.
- Pixi is the only runner: `pixi run python -m tools.materializer ...`. Never `python`, `uv`, `uvx`, or `pip`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tools/materializer/__init__.py` | NEW | Package marker. `tools/` does not exist today. |
| `tools/materializer/errors.py` | NEW | `MaterializerError` and its three subclasses. |
| `tools/materializer/logging.py` | NEW | `structlog` JSON-to-stdout logger factory. |
| `tools/materializer/carrier.py` | NEW | `accelerator.toml` loader; `Disposition` enum; `resolve_disposition`. |
| `tools/materializer/combination.py` | NEW | `Combination`; `enumerate_valid()` returning six in fixed order. |
| `tools/materializer/paths.py` | NEW | `travels()` truth table. |
| `tools/materializer/materialize.py` | NEW | Copy-then-remove driver. |
| `tools/materializer/cli.py` | NEW | `python -m tools.materializer` entry point. |
| `accelerator.toml` | UPDATE | Authored by Story 7.1. This story adds dispositions for `tools/` (machinery) and for the cache/build directories listed in Task 4. If Story 7.1 has not landed, this story is blocked on it — do not create a substitute carrier. |
| `pixi.toml` | UPDATE | Add a `materialize` task in `[feature.dev.tasks]` with `default-environment = "dev"` and a `description`, matching the existing task style at `:184-206`. |
| `pyproject.toml` | UPDATE | Today `[tool.ruff] src` and the mypy configuration cover `src` and `tests`; extend both to `tools`. `[tool.coverage.run] include = [ "src/**" ]` at `:161` — extend to `tools/**` so the materializer's own coverage counts toward the floor. |
| `tests/unit/materializer/test_carrier.py` | NEW | |
| `tests/unit/materializer/test_combination.py` | NEW | |
| `tests/unit/materializer/test_paths.py` | NEW | |
| `tests/integration/materializer/test_materialize.py` | NEW | |
| `tests/integration/materializer/test_reference_application_unchanged.py` | NEW | |

#### Project Structure Notes

The Structural Seed places the materializer at `tools/materializer/` and marks it "machinery — projections of accelerator.toml (AD-3)". That directory does not exist today; `tools/` itself does not exist. Everything under it is NEW.

Test location convention: accelerator tests live under `tests/` mirroring what they cover and carry the disposition of what they cover. The materializer covers machinery, so `tests/unit/materializer/` and `tests/integration/materializer/` are `machinery` and never travel. Add `__init__.py` to both new test packages to match the existing `tests/unit/__init__.py` and `tests/integration/__init__.py`.

### Testing Requirements

- Unit tests are isolated — carrier parsing from an in-test TOML string, no filesystem walk. Milliseconds.
- Integration tests carry `@pytest.mark.integration` and use `tmp_path` for every output tree. They must leave the repository exactly as found; `test_reference_application_unchanged.py` asserts that directly.
- Coverage floor: 90% including templates, `COVERAGE_CORE=ctrace` in force (AD-20). Extending `[tool.coverage.run] include` to `tools/**` means the materializer must itself be covered to 90%; write the tests as you write the module rather than after.
- Specific assertions the ACs demand: every `core` and `tenant` path in all six outputs; each `feature:<name>` path in exactly its selecting combinations; `tools/`, `accelerator.toml` and the fixture set absent from all six; the reference tree byte-unchanged after six materializations.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-3]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-6]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-33 — Retired in revision 3]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Structural Seed]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.2]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.1] — the carrier and input reconciliation this story consumes
- [Source: pyproject.toml:160-173] — current `[tool.coverage.run]` include/omit
- [Source: pixi.toml:184-206] — existing dev task style

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
