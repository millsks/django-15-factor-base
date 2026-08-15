# Story 8.7: Output reconciliation proves the accelerator's machinery never reaches a component

Status: ready-for-dev

## Story

As a lead developer,
I want every path in a materialized tree to have a legal reason to be there,
so that the accelerator's own tooling and planning artifacts cannot travel into the component I ordered.

## Acceptance Criteria

**Traceability:** FR-37, FR-28 · AD-2 · NFR-8 · SC-2

1. **Given** each materialized tree
   **When** output reconciliation runs
   **Then** every path is either a copied path with a travelling disposition or a declared generated artifact
   **And** nothing else is permitted

2. **Given** the accelerator's machinery
   **When** output is produced
   **Then** `_bmad/`, `_bmad-output/`, `.agents/`, `.bmad-loop/`, `.claude/`, the materializer, the carrier and the fixture set are all absent

3. **Given** `.github/` and `docs/`
   **When** they are dispositioned
   **Then** they split rather than travelling wholesale: only the component's own pipeline travels, and only documentation describing how to work on any component travels

4. **Given** directory-level granularity
   **When** it is considered
   **Then** it is insufficient and is not used, because `src/config/`, `tests/`, `pixi.toml` and `pixi.lock` each contain both core and feature-owned content

5. **Given** `src/config/celery_app.py`
   **When** a combination without background task processing is materialized
   **Then** it is absent

6. **Given** the dependency manifest
   **When** the twelve combinations are compared
   **Then** it differs in eleven of the twelve

7. **Given** `COVERAGE_CORE`
   **When** a combination is materialized
   **Then** the setting travels with it

## Tasks / Subtasks

- [ ] Task 1: Declare the generated-artifact surface (AC: #1)
  - [ ] Add a `[generated]` table to `accelerator.toml` enumerating every path the materializer is permitted to create that was not copied. Today that is exactly `.accelerator.json` (AD-17, Story 8.11). The list is closed; an unlisted generated path fails reconciliation.
  - [ ] Extend `tools/materializer/carrier.py` to expose `generated_artifacts: frozenset[str]`.

- [ ] Task 2: Implement output reconciliation (AC: #1, #2, #4, #5)
  - [ ] `tools/materializer/reconcile.py` — `reconcile_output(output_root, source_root, combination, carrier) -> tuple[str, ...]` returning a sorted tuple of violations; empty means clean. A violation is any output path that is neither (a) a path present in the reference application whose disposition travels for this combination, nor (b) a declared generated artifact.
  - [ ] Reconcile in both directions: also report any path that *should* have travelled and is missing. AD-2 names input reconciliation and output reconciliation as two checks; this story owns the output half, and a missing `core` path is an output defect.
  - [ ] Reconciliation operates on the full relative path, never on a directory prefix. Do not implement a directory allowlist.
  - [ ] `reconcile_output` raises nothing; the gate test turns a non-empty violation tuple into a failure naming every violating path.

- [ ] Task 3: Split `.github/` and `docs/` in the carrier (AC: #3)
  - [ ] `.github/workflows/` today holds `ci.yml`, `labeler.yml`, `release.yml`, `sonarqube.yml`, `stale.yml`. Disposition each individually: the component's own pipeline travels (`core`), the accelerator's twelve-combination harness workflow and anything specific to this repository's release or triage automation does not (`machinery`).
  - [ ] `.github/` also holds `agents/`, `copilot/`, `CODEOWNERS`, `ISSUE_TEMPLATE/`, `issue-labeler.yml`, `labeler.yml`, `pull_request_template.md`. Disposition each explicitly; none may rely on the `machinery` default silently — an explicit claim is what makes the split reviewable.
  - [ ] `docs/` today holds `index.md`, `development.md`, `observability.md`. Documentation describing how to work on *any* component travels (`core`); documentation about the accelerator itself — the carrier, the materializer, the twelve-combination harness — does not (`machinery`). Split existing files if a single file mixes both; do not disposition a mixed file as `core`.
  - [ ] `mkdocs.yml` is a parameter site (AD-25) and must remain consistent with whichever `docs/` pages travel; assert that no travelling `mkdocs.yml` nav entry points at a `machinery` page.

- [ ] Task 4: Assert the machinery exclusions (AC: #2)
  - [ ] `_bmad/`, `_bmad-output/`, `.agents/`, `.bmad-loop/`, `.claude/` all exist at the repository root today. Declare each `machinery` in `accelerator.toml` explicitly rather than relying on the default, and assert their absence from every output tree.
  - [ ] Assert `tools/`, `accelerator.toml` and the fixture set are absent. They are absent by disposition (Story 8.2); this story adds the assertion.

- [ ] Task 5: Assert the sub-directory-granularity claims (AC: #4, #5, #6, #7)
  - [ ] `src/config/celery_app.py` (37 lines, exists today) is `feature:celery`. Assert it is absent from the eight non-Celery combinations and present in the four Celery ones. Its existing unit test `tests/unit/test_celery_app.py` is `feature:celery` too and travels with it.
  - [ ] Assert `src/config/` travels partially — `settings/`, `observability/`, `urls.py`, `api_router.py`, `asgi.py`, `wsgi.py` are `core`; `celery_app.py` is `feature:celery` — so a directory-level rule would be wrong for `src/config/`.
  - [ ] Assert `tests/` travels partially: `tests/unit/test_celery_app.py` is `feature:celery`, the immovable-core suite is `core` (Story 8.10), the materializer tests are `machinery`.
  - [ ] Dependency manifest: extract the declared dependency set from each materialized `pixi.toml` and assert all twelve are pairwise distinct — so for any one taken as the baseline, the other eleven differ.
  - [ ] `COVERAGE_CORE`: assert every materialized `pixi.toml` carries `COVERAGE_CORE = "ctrace"` in `[activation.env]` (it sits at `pixi.toml:145-150` today and is unmarked, so it travels as `core` content of a `core` path).

- [ ] Task 6: Wire reconciliation into the gate (AC: #1)
  - [ ] `tests/integration/materializer/test_output_reconciliation.py` (`@pytest.mark.integration`, `tmp_path`) — materialize all twelve and assert `reconcile_output()` returns an empty violation tuple for each, reporting every violation by path on failure.
  - [ ] Add the same call to the twelve-combination harness (Story 8.8) so reconciliation runs per combination in CI, not only in the local suite.
  - [ ] `tests/unit/materializer/test_reconcile.py` — an unlisted output path is a violation; a declared generated artifact is not; a missing `core` path is a violation; a `feature:` path present in a non-selecting combination is a violation.

## Dev Notes

### Architecture Constraints

- **AD-2** (binding): "**Output**, against each materialized tree: every path is either a copied path with a travelling disposition or a declared generated artifact, and nothing else." *Prevents:* "an unlisted path silently travelling into every component; a developer's own app being deleted or reported as an orphan; a generated artifact having no legal existence."
- **AD-2, `tenant`**: `tenant` is "never judged, never pruned". Reconciliation must not report a path under `src/django_apps/` as a violation, and must not require it to be enumerated. This is the "a developer's own app being reported as an orphan" failure the AD names.
- **AD-1** (binding): `accelerator.toml` "is `machinery` and never travels". So is the materializer.
- **FR-37** (binding): "The accelerator's own machinery does not reach a component — a per-path disposition rule defaulting to excluded, with parameterization, `.github/` and `docs/` splits, and `src/django_service/` explicitly not parameterized."
- **NFR-8** (binding): "Documentation travels with what it describes — component-facing docs materialize with the component, accelerator-facing docs do not." This is the rule that decides the `docs/` split; it is not a judgement call.
- **AD-17**: `.accelerator.json` "is a declared generated artifact under AD-2's output reconciliation, never hand-edited." It is the only entry in `[generated]` today.
- **AD-29**: everything inside `src/django_service/` is `core` and travels in all twelve. Reconciliation will report a violation if any path there fails to travel, which is the correct signal.
- **Not a directory allowlist.** AC #4 is a design constraint on the implementation, not only a documented observation: writing `if path.startswith("src/config/")` anywhere in `reconcile.py` violates it.
- Never bare `except:`; never `except X: pass`. Never `print()`; `structlog` only.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tools/materializer/reconcile.py` | NEW | `reconcile_output()`, both directions, path-granular. |
| `tools/materializer/carrier.py` | UPDATE | Created by Story 8.2, extended by 8.5 and 8.6. Adds `generated_artifacts`. Preserve the four-member `Disposition` enum, the `machinery` default, constraints and parameters. |
| `accelerator.toml` | UPDATE | Adds `[generated]`; adds explicit dispositions for `.github/*`, `docs/*`, `_bmad/`, `_bmad-output/`, `.agents/`, `.bmad-loop/`, `.claude/`, `tools/`; confirms `src/config/celery_app.py` as `feature:celery`. |
| `docs/index.md`, `docs/development.md`, `docs/observability.md` | UPDATE | All three exist. Split any page mixing accelerator-facing and component-facing content; `observability.md` describes the component and is expected to travel, `development.md` needs review against NFR-8 because it likely describes both. |
| `mkdocs.yml` | UPDATE | Exists at the repository root and is an AD-25 parameter site. Ensure no travelling nav entry points at a `machinery` page. |
| `.github/workflows/ci.yml` | UPDATE | Today: three-OS matrix `test` job running `pixi run test`, plus a `lint` job running `pixi run lint` and `pixi run typecheck` (55 lines). Epic 1 consolidates it to one `pixi run ci` invocation. This story only assigns its disposition; do not restructure it here. |
| `tests/unit/materializer/test_reconcile.py` | NEW | |
| `tests/integration/materializer/test_output_reconciliation.py` | NEW | |

#### Project Structure Notes

Everything AC #2 names exists at the repository root today: `_bmad/`, `_bmad-output/`, `.agents/`, `.bmad-loop/`, `.claude/`. `tools/` is created by Story 8.2. `accelerator.toml` is created by Story 7.1.

Variance worth recording: the Structural Seed does not enumerate `.github/`, `docs/`, `mkdocs.yml`, `sonar-project.properties`, `manage.py`, `CHANGELOG.md`, `LICENSE` or `README.md`, all of which exist. Every one needs an explicit disposition under AD-2 even though the seed is silent about it — the seed is a shape, not an inventory, and the `machinery` default is a safety net rather than a plan.

### Testing Requirements

- `tests/unit/materializer/test_reconcile.py` — isolated, synthetic trees built in memory or under `tmp_path` with a hand-built `Carrier`; milliseconds.
- `tests/integration/materializer/test_output_reconciliation.py` — `@pytest.mark.integration`, materializes all twelve into `tmp_path`, leaves state as found.
- The failure message must name every violating path. A boolean assertion is insufficient: the point of reconciliation is to say which path has no legal reason to be there.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` (AD-20).
- Disposition: both test files are `machinery`. `tests/unit/test_celery_app.py` (exists today) becomes `feature:celery` and is pruned in the eight non-Celery combinations — that is Story 7.7's declaration, asserted here.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-17]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20] — `COVERAGE_CORE=ctrace` travels with every combination
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.7]
- [Source: _bmad-output/planning-artifacts/epics.md] — FR-37, NFR-8, SC-2
- [Source: pixi.toml:145-150] — `[activation.env] COVERAGE_CORE = "ctrace"`
- [Source: src/config/celery_app.py] — exists, 37 lines
- [Source: .github/workflows/] — `ci.yml`, `labeler.yml`, `release.yml`, `sonarqube.yml`, `stale.yml`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
