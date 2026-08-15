# Story 9.6: Base compatibility is declared and checked at adoption

Status: ready-for-dev

## Story

As a lead developer,
I want an incompatible adoption to fail my gate,
so that a base that moved beneath an application is found before production.

## Acceptance Criteria

**Traceability:** FR-56 · AD-5

1. **Given** a reusable application
   **When** it declares its supported base range
   **Then** it declares `MIN <= v <= MAX` integers in its contribution module
   **And** not in package metadata, because an in-repo application has no distribution metadata

2. **Given** the adoption gate test
   **When** it runs
   **Then** it asserts compatibility from that constant
   **And** it runs identically in both residencies

3. **Given** an application adopted outside the supported range
   **When** the component's gate runs
   **Then** it fails

## Tasks / Subtasks

- [ ] Task 1 — Fix the declaration shape in the contribution module (AC: #1)
  - [ ] A contribution module (`<app>/contribution.py`, Story 9.4) declares two module-level integers: `MIN_BASE_API_VERSION: int` and `MAX_BASE_API_VERSION: int`. Both are required; a contribution module missing either is a failure, not a default.
  - [ ] The compatibility predicate is inclusive on both ends: `MIN_BASE_API_VERSION <= django_service.__api_version__ <= MAX_BASE_API_VERSION`.
  - [ ] Both are plain `int` literals. Not a string, not a tuple, not a specifier expression, not read from `importlib.metadata`, not derived from `django_service.__version__`. AD-5 puts them in the contribution module precisely because an in-repo application has no distribution metadata to carry them in.

- [ ] Task 2 — Implement the check beside the composition surface (AC: #2, #3)
  - [ ] Add `check_adoption_compatibility(adopted: Sequence[str]) -> list[str]` to `src/config/startup/` — the module that already owns the FR-17 allowlist and, after Story 9.4, the contributable surface. It returns the list of incompatible applications with a message naming the application, its declared range, and the base's actual `__api_version__`.
  - [ ] It imports each application's contribution module with `importlib.import_module(f"{app}.contribution")` and reads the two constants with `getattr`. A missing constant, a non-`int` value, or `MIN > MAX` is itself an incompatibility, reported with its own message.
  - [ ] The function reads `django_service.__api_version__` directly (Story 9.1). It never consults distribution metadata, `pkg_resources`, or a version specifier parser — that is what makes it behave identically in both residencies (AC #2).
  - [ ] Put it beside the composition surface but do **not** call it from `apply_contributions`. This check is a gate condition, not a refusal: AC #3 says the component's *gate* fails, and the epic's framing is "failing the gate rather than production." Do not add it to stage 1 or stage 2.

- [ ] Task 3 — The adoption gate test (AC: #2, #3)
  - [ ] New `tests/unit/test_adoption_compatibility.py`. Read the adopted-application list from `component.toml` (Story 5.1) and assert `check_adoption_compatibility(...)` returns an empty list; a non-empty return fails the test with the collected messages.
  - [ ] The test must be correct over an empty adopted list — the reference application adopts nothing, and a loop that vacuously passes must be distinguishable from one that is wrong. Cover the empty case explicitly.
  - [ ] This is the test AC #3 names. It runs inside `pixi run ci` for the reference application and inside every materialized combination's gate, unchanged.

- [ ] Task 4 — Prove residency-independence (AC: #2)
  - [ ] New `tests/integration/test_adoption_compatibility_residency.py`, marked `@pytest.mark.integration`. Reuse the two-residency fixture pattern from Story 9.5: one application source materialized into a tenant-style root and a site-packages-style root under `tmp_path`.
  - [ ] Assert `check_adoption_compatibility(["billing"])` returns the same result under both residencies, for a compatible declaration and for an incompatible one.
  - [ ] Assert the check never touches `importlib.metadata`: monkeypatch `importlib.metadata.version` and `importlib.metadata.distributions` to raise, and assert the check still succeeds. An implementation that silently falls back to metadata would pass in one residency and fail in the other, which is the divergence AD-8 refuses.

- [ ] Task 5 — Negative tests: the check detects (AC: #3)
  - [ ] Table-driven cases in `tests/unit/test_adoption_compatibility.py` over fixture contribution modules under `tests/fixtures/tenant_apps/` (created in Story 9.4): base version below `MIN`; above `MAX`; exactly `MIN`; exactly `MAX`; `MIN` missing; `MAX` missing; `MIN` a string; `MIN > MAX`.
  - [ ] The two boundary cases must pass and the rest must fail — an off-by-one on an inclusive range is the most likely defect here and nothing else catches it.
  - [ ] Monkeypatch `django_service.__api_version__` for the range cases rather than editing the constant; assert the original value is restored.

- [ ] Task 6 — Document the declaration and the bump (AC: #1)
  - [ ] Extend `docs/extension-model.md` (Story 9.5) with the compatibility contract: where the two integers live, what an inclusive range means, and that the base bumps `__api_version__` by hand on any breaking change and on the removal of any guaranteed surface (Story 9.1). A reusable application widens `MAX` only after testing against the new base.

- [ ] Task 7 — Tests and gate (AC: all)
  - [ ] `pixi run test`, `pixi run test-integration`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-5 (binding):** "A reusable app declares its supported range as `MIN <= v <= MAX` integers **in its contribution module**, not in package metadata — an in-repo app has no distribution metadata, and AD-8 refuses to let the two residency modes diverge. The adoption gate test asserts compatibility from that constant, so it runs identically in both residencies." Also: "`django_service.__api_version__` is a single integer, bumped by hand on any breaking change and on the removal of any guaranteed surface." *Prevents:* "a reusable app silently breaking on a component whose base moved beneath it."
- **AD-8:** the two residency modes must not diverge; nothing self-registers and entry-point/metadata discovery is forbidden. The same reasoning governs where the version range lives.
- **AD-26:** the refusal contract is one module with two stages. This check is deliberately **not** one of them — the epics' refusal table enumerates the conditions and adoption compatibility is not among them, and it does not become one here. It is a gate condition: the component's *gate* fails, before production, which is what AC #3 asks for. (Separately, revision 3's navigation registry does add a stage-2 refusal — every registered URL name must resolve in the URLconf, Story 9.4 AC #9. That one is a genuine refusal because it can only be evaluated in a running process; this one can be evaluated by a test and therefore is not. Note that the two checks are nonetheless the same *kind* of thing and neither enters the enumerated table: both judge what a contribution declared, in this story's adoption-time shape, rather than a forbidden state of the component's own configuration. So the navigation check joins Story 4.3's fixed-order tuple without becoming a tenth condition, the settled count of nine conditions across fourteen forbidden states is unchanged, and Story 4.5's audit still asserts exactly fourteen.)
- **AD-24:** no `try/except ImportError`. A contribution module that will not import is a failure with a message, not a skip.
- **Spine Consistency Conventions:** a refusal never degrades to a warning; a gate failure never degrades to a printed notice.

**Must not do:**
- Do not read the range from `pyproject.toml`, package metadata, a `Requires-Dist` specifier, or a TOML file inside the application. The contribution module is the location and there is no second one.
- Do not compare against `django_service.__version__` (the distribution version, derived from git tags by hatch-vcs). `__api_version__` is the contract version and the two are unrelated.
- Do not make the check a startup refusal, and do not call it from `apply_contributions`.
- Do not default a missing `MIN`/`MAX` to anything permissive.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `src/config/startup/` | UPDATE | **Does not exist today**; created by Story 4.1. Add `check_adoption_compatibility()` beside the allowlist/contributable-surface declaration. |
| `src/django_service/__init__.py` | UPDATE (read only) | 18 lines today: module docstring, `__version__` from `importlib.metadata.version("django-15-factor-base")` with a `PackageNotFoundError` fallback, and `__version_info__`. Story 9.1 adds `__api_version__: int`. This story reads it and changes nothing here. |
| `component.toml` | UPDATE (read only) | **Does not exist today** (Story 5.1). Supplies the adopted-application list the gate test iterates. |
| `tests/fixtures/tenant_apps/**` | UPDATE | Created in Story 9.4. Add the compatibility-case contribution modules of Task 5. |
| `tests/unit/test_adoption_compatibility.py` | NEW | The adoption gate test and the eight table-driven cases. |
| `tests/integration/test_adoption_compatibility_residency.py` | NEW | The two-residency and no-metadata assertions. |
| `docs/extension-model.md` | UPDATE | Created in Story 9.5. Add the compatibility contract section. |

Verified today: `src/django_service/__init__.py` exists and carries no `__api_version__`; `src/config/startup/`, `component.toml` and `tests/fixtures/` do not exist. `docs/` exists at the repository root.

### Testing Requirements

- Unit: `tests/unit/test_adoption_compatibility.py` — imports fixture modules from `tmp_path`/`tests/fixtures`, no external resource, no marker.
- Integration: `tests/integration/test_adoption_compatibility_residency.py` — `@pytest.mark.integration` on every test; restores `sys.path`, `sys.modules` and any monkeypatched attribute.
- Assertions the ACs demand:
  - the range is read from the contribution module, never from metadata, proven by making metadata access raise (AC #1, #2);
  - both residencies return identical results for the same declaration (AC #2);
  - an out-of-range adoption produces a non-empty result and fails the gate test (AC #3);
  - the inclusive boundaries `v == MIN` and `v == MAX` pass;
  - a missing, non-integer, or inverted range fails with its own message;
  - the empty adopted-application list passes and is covered explicitly.
- Disposition: covers `core` surface (`src/config/startup/`, `src/django_service/`); lives under `tests/` and is never pruned.
- AD-20 floor: ninety percent including templates, `COVERAGE_CORE=ctrace` in force. `pixi run ci` must exit 0.

#### Project Structure Notes

The Structural Seed places the startup module at `src/config/startup/` — "both refusal stages + the FR-17 allowlist (AD-26)". This story adds a gate helper to that module without adding a refusal stage, and the distinction should be stated in the module docstring so a later reader does not "complete" it by wiring the check into stage 1.

Variance today: `src/config/startup/`, `component.toml`, `accelerator.toml`, `src/django_apps/`, `tests/fixtures/` and `docs/extension-model.md` all do not exist. This story is implementable only after Stories 4.1, 5.1, 9.1, 9.4 and 9.5.

Python 3.14; `Sequence[str]` from `collections.abc`; `list[str]` return; full type hints; Google-style docstrings; no `print()`; if the check reports anything at runtime it does so through its return value, not through logging.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.6]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-5]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-8]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — the enumerated conditions; this check is not one of them
- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.1] — `__api_version__`
- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.4] — the contribution module and its fixtures
- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.5] — the two-residency fixture pattern

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
