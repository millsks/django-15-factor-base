# Story 8.6: The fixture set covers every parameterized value

Status: ready-for-dev

## Story

As a platform engineer,
I want test values for every parameter the enterprise developer portal would supply,
so that a parameter added to the order surface breaks materialization instead of silently defaulting.

## Acceptance Criteria

**Traceability:** FR-31 · AD-25

1. **Given** the fixture set
   **When** it is authored
   **Then** it covers every parameterized value declared in Story 7.3, including the component package name and the code-quality project key
   **And** it covers the four feature booleans

2. **Given** a parameter with no corresponding fixture
   **When** materialization runs
   **Then** it fails
   **And** never emits a default

3. **Given** the portal's order-surface field list does not exist yet
   **When** the fixture set is scoped
   **Then** it covers the declared parameters and the four feature booleans
   **And** the missing field list is recorded as an open item owned by the portal team

## Tasks / Subtasks

- [ ] Task 1: Load the parameter declarations and their fixtures (AC: #1)
  - [ ] `tools/materializer/parameters.py` — `load_parameters(carrier) -> tuple[Parameter, ...]`. `Parameter` is a frozen dataclass carrying `name`, `fixture: str | None`, and `sites: tuple[Site, ...]` where `Site` is `(path, token)`.
  - [ ] Read from `accelerator.toml` `[parameters]`, authored by Story 7.3: `sonar-project.properties` (project key), `README.md`, `CHANGELOG.md`, `LICENSE`, `pyproject.toml`, `mkdocs.yml`, and the component name.
  - [ ] The component name is **one** parameter with four sites — `pixi.toml` `[workspace] name`, `pyproject.toml` `[project] name`, the `[pypi-dependencies]` self-install key, and `[pypi-options] no-build-isolation`. Model it as one `Parameter` with four `Site`s, not four parameters.
  - [ ] `src/django_service/` is **not** a parameter. Assert that no declared parameter's site falls inside `src/django_service/` and fail loudly if one does.

- [ ] Task 2: Add the four feature booleans to the order surface (AC: #1)
  - [ ] Extend the order model in `tools/materializer/order.py` (NEW) — an `Order` frozen dataclass carrying the `Combination` (the four booleans) and a `dict[str, str]` of parameter values. This is what the enterprise developer portal will eventually supply and what the fixture set stands in for.
  - [ ] `fixture_order() -> Order` builds an order from the carrier's fixture values plus one `Combination`, so every gate run materializes from a real `Order` rather than from an ad-hoc argument list.
  - [ ] The four feature booleans get fixtures too: the twelve valid `Combination`s enumerated by Story 8.2 are the fixture values for the boolean half of the order surface. Assert all twelve are reachable through `fixture_order()`.

- [ ] Task 3: Fail on a missing fixture (AC: #2)
  - [ ] `resolve_values(parameters, order) -> dict[str, str]` raises `MissingFixtureError` (new subclass of `MaterializerError`) naming the parameter when a declared parameter has no fixture and the order supplies no value.
  - [ ] There is no default. Do not add a fallback, an empty string, a `getattr(..., default)`, or a `dict.get(name, "")`. FR-31's whole content is that a parameter without a fixture fails materialization rather than defaulting.
  - [ ] Call `resolve_values()` before any file is written, alongside `validate()` from Story 8.5 — a missing fixture must refuse before output exists, on the same reasoning.

- [ ] Task 4: Substitute at the declared sites (AC: #1)
  - [ ] `substitute(text, path, values, parameters) -> str` replaces only at the exact `(path, token)` sites the carrier declares. Never a repository-wide search-and-replace, and never a regex over content the carrier did not name — AD-25 makes the sites exact for exactly that reason.
  - [ ] A declared site whose token is absent from the file raises `CarrierError`; a token found at a path the carrier did not declare is Story 7.3's reconciliation, not this story's, but the materializer must not silently substitute there.
  - [ ] Wire `substitute()` into `tools/materializer/materialize.py` after region pruning (Story 8.3), so parameters apply to the pruned text.

- [ ] Task 5: Record the open item (AC: #3)
  - [ ] Add a comment block in `accelerator.toml` above `[parameters]` stating: the enterprise developer portal's order-surface field list does not exist; until it does, the fixture set covers the AD-25 parameters and the four feature booleans; owner is the portal team. Rationale lives beside the configuration it constrains.
  - [ ] Add the same statement to `docs/` in the accelerator-facing documentation, not the component-facing documentation — accelerator-facing docs do not travel (NFR-8).

- [ ] Task 6: Tests (AC: #1, #2, #3)
  - [ ] `tests/unit/materializer/test_parameters.py` — every parameter named in AD-25 is declared and has a fixture; the component name is one parameter with four sites; no site falls inside `src/django_service/`; a parameter with `fixture = None` and no order value raises `MissingFixtureError` naming it; no code path returns a default.
  - [ ] `tests/unit/materializer/test_order.py` — `fixture_order()` reaches all twelve combinations; the order carries exactly the four booleans plus the declared parameter names and nothing else.
  - [ ] `tests/integration/materializer/test_substitution.py` (`@pytest.mark.integration`, `tmp_path`) — materialize with the fixture order and assert the substituted value appears at every declared site and that the reference application's own value (for example the hardcoded project key at `sonar-project.properties:6`) appears nowhere in the output.

## Dev Notes

### Architecture Constraints

- **AD-25** (binding): "A path has a disposition (AD-2) and, independently, a parameter set. `accelerator.toml` declares `[parameters]`: each parameter's name, its fixture value, and every exact path and token site it substitutes. Reconciliation covers it both ways — a declared parameter with no site fails, a site matching no declared parameter fails." *Prevents:* "`sonar-project.properties`'s hardcoded key travelling as `core` so every component's metrics merge into this project silently — nothing failing, which is the exact consequence FR-37 names; and FR-31's fail-on-missing-fixture rule having nothing to compare against."
- **AD-25 ordering constraint** (binding on this epic): "Building the materializer before parameterization exists re-cuts every carrier entry, every fixture and every combination's gate output, so it does not happen in that order." Story 7.3 must have landed. If it has not, this story is blocked; do not author `[parameters]` here.
- **AD-25 / AD-5**: "`src/django_service/` is **not** a parameter" — it is a constant, "because reusable apps import from it by that name in every deployment". Divergence D-1 records that FR-37 once said otherwise and the PRD has since been corrected. Never parameterize it.
- **FR-31** (binding): "a parameter without a fixture fails materialization rather than defaulting."
- **AD-1**: the fixture values live in `accelerator.toml` `[parameters]`, not in a second file. If a separate fixture file is introduced it must be declared `machinery` — but prefer the carrier, because AD-1 permits one declaration site.
- **NFR-8**: "component-facing docs materialize with the component, accelerator-facing docs do not." The portal open item is accelerator-facing.
- **Open item, verbatim from the spine**: "The enterprise developer portal's order surface. FR-31's fail-on-missing-fixture rule needs a field list. Until one exists the fixture set covers the AD-25 parameters and the four feature booleans. Owner: portal team." Record it; do not attempt to invent the field list.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tools/materializer/parameters.py` | NEW | Parameter model, fixture resolution, exact-site substitution. |
| `tools/materializer/order.py` | NEW | `Order` and `fixture_order()` — the stand-in for the portal's order surface. |
| `tools/materializer/errors.py` | UPDATE | Created by Story 8.2. Add `MissingFixtureError(MaterializerError)`. |
| `tools/materializer/materialize.py` | UPDATE | Add the substitution pass after region pruning; resolve values before any write. Preserve path pruning (8.2), region pruning (8.3), sorted traversal (8.4) and the `validate()` first-statement ordering (8.5). |
| `accelerator.toml` | UPDATE | Story 7.3 authors `[parameters]`. This story adds the portal open-item comment block and, if absent, fixture values for any declared parameter lacking one. |
| `docs/development.md` | UPDATE | Exists today alongside `docs/index.md` and `docs/observability.md`. Add the accelerator-facing note about the missing order-surface field list, or add it to whichever accelerator-facing page Story 8.7's `docs/` split assigns as non-travelling. |
| `tests/unit/materializer/test_parameters.py` | NEW | |
| `tests/unit/materializer/test_order.py` | NEW | |
| `tests/integration/materializer/test_substitution.py` | NEW | |

`sonar-project.properties` exists at the repository root and carries the hardcoded project key AD-25 names; do not edit its value here — Story 7.3 declares it as a parameter site and this story substitutes it in output only.

#### Project Structure Notes

No structural change. `tools/materializer/` is `machinery` per the Structural Seed. The order model deliberately lives in the materializer rather than in `src/`, because the order surface is the accelerator's concern and never travels.

### Testing Requirements

- Unit tests are isolated: build a `Carrier` from an in-test TOML string; do not read the real `accelerator.toml` in a unit test except for the "every AD-25 parameter is declared" assertion, which is a policy check over a declaration file and follows the precedent of `tests/unit/test_dependency_policy.py`.
- Integration tests carry `@pytest.mark.integration` and materialize into `tmp_path`.
- The negative assertion in `test_substitution.py` is load-bearing for AD-25's stated failure mode: assert the reference application's own project key value does **not** appear anywhere in the materialized tree. A test that only asserts the fixture value appears would pass while the original also travelled.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` (AD-20).
- Disposition: all three test files are `machinery`.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-25]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-5]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Open Items] — the portal order-surface item and its owner
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Divergences From the PRD] — D-1, `src/django_service/` is a constant
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.6]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.3] — the parameter set and its sites, declared there
- [Source: _bmad-output/planning-artifacts/epics.md] — FR-31, NFR-8

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
