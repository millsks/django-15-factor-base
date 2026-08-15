# Story 7.8: The orphan detectors exist for all three residue categories

Status: ready-for-dev

## Story

As a platform engineer,
I want every residue category to have a detector,
so that a category with no detector is not a category that ships.

## Acceptance Criteria

**Traceability:** FR-29 · AD-20 · CG-1 · SC-2

1. **Given** coverage measurement
   **When** a combination's gate runs
   **Then** it includes templates
   **And** `COVERAGE_CORE` is pinned to the C trace core so template measurement is real rather than a silent zero

2. **Given** the declared omit list authored in Story 1.5
   **When** this story lands
   **Then** it moves into `accelerator.toml` as a closed, carrier-declared surface
   **And** the two-way assertion that the effective list equals the declared one is unchanged in meaning

3. **Given** static assets and settings fragments
   **When** residue is detected
   **Then** it is detected by checking materialized output against the carrier
   **And** any path present that no selected feature claims is a defect

4. **Given** an orphaned template override
   **When** it is introduced deliberately
   **Then** the combination's gate fails on the zero-percent coverage signal
   **And** the test that proves this runs in Epic 8, where a materialized combination exists to run it against

## Tasks / Subtasks

- [ ] Task 1 — Name the three residue categories and their detectors explicitly (AC: #1, #3, #4)
  - [ ] The story's title is the requirement: *a category with no detector is not a category that ships*. Record the three categories and their detectors in `accelerator.toml` beside the declarations that implement them, so the mapping is auditable rather than implied:
    - **Templates and unreached code** → template-inclusive coverage with `COVERAGE_CORE=ctrace` and a 90% floor. An orphaned template reports zero percent and the floor fails. (Tasks 2, 4.)
    - **Static assets and settings fragments** → carrier reconciliation of materialized output. Coverage cannot see a `.css` file or a settings block that nothing imports; only "present but claimed by no selected feature" catches it. (Task 5.)
    - **Dependencies** → the package split declared per feature (Story 7.2) reconciled against the materialized `pixi.toml` and the resolved environment. A package present in a combination that no selected feature claims is residue. (Task 5.)
  - [ ] Assert the mapping is total: every category named has a detector named, and every detector named has a gate assertion or a declared Epic 8 owner. A category with a detector "planned" is a category with no detector.

- [ ] Task 2 — Move the coverage omit/exclude declaration into the carrier (AC: #2)
  - [ ] Story 1.5 authored the declared omit list and the two-way assertion that the effective list equals the declared one, in a single module. This story moves that declaration into `accelerator.toml` as `[coverage]` — **without changing any assertion's meaning** (`epics.md:225`).
  - [ ] Read the Story 1.5 declaration module before moving anything, and diff the moved list against it. If the lists differ, the move is wrong; the move is a relocation, not a re-authoring.
  - [ ] Declare in `[coverage]`: `floor = 90`, `core = "ctrace"`, `omit = [...]`, `exclude = [...]`, and `include = [...]`. The `omit` and `exclude` surface is closed: the gate asserts the effective list equals the declared one, in both directions, so an entry added to `pyproject.toml` without the carrier fails and a carrier entry with no effect fails.
  - [ ] `[tool.coverage.run] omit` in `pyproject.toml` today (`:162-169`) is `*/migrations/*`, `*/tests/*`, `**/*.egg-info/**`, `src/config/wsgi.py`, `src/config/asgi.py`, `src/config/websocket.py`. `src/config/websocket.py` is deleted with its omit entry by AD-16 in Story 1.4 — if that story has landed the entry is already gone and must not reappear in the carrier; if it has not, carry it and record the pending removal. `include` is `[ "src/**" ]` (`:161`); Story 7.1 flagged that this excludes `tools/**` from measurement and required an explicit decision — carry whatever decision was recorded there into `[coverage].include`.
  - [ ] Update the Story 1.5 assertion to read the declared list from the carrier instead of from its own module. Its meaning is unchanged: effective equals declared, two-way. Do not weaken it to one direction, and do not add an escape hatch for "entries the carrier does not know about yet".
  - [ ] AD-1 forbids a second declaration site. After this task, `accelerator.toml` is the only place the omit list is authored; `pyproject.toml` carries the effective configuration and the gate proves the two agree.

- [ ] Task 3 — Move the other two Epic-earlier declarations into the carrier (supports AC: #2's pattern)
  - [ ] `epics.md:225` names three declarations that move into `accelerator.toml` in Epic 7 without changing any assertion's meaning. The coverage omit list is one (Task 2). The other two are the **local sign-in route's name and prefix constants** (Story 3.4, AD-21) and the **FR-14 feature-region markers** (Story 4.4, AD-24).
  - [ ] Local sign-in constants: AD-21 states *"Its URL name and path prefix are fixed constants declared in `accelerator.toml`."* Move them from wherever Story 3.4 put them into `accelerator.toml`. **Do not change the stage-2 predicate.** AD-21 and AD-26 require it to refuse any route whose **view callable belongs to the local sign-in module** — never a name or prefix match — *"because a route named `local_persona_login` mounted under `/accounts/` would otherwise satisfy this AD and pass an allowlist that already permits `/accounts/` for allauth."* The constants are declaration; the predicate stays object-resolving.
  - [ ] FR-14 feature-region markers: Story 4.4's two feature-scoped refusals (in-process cache where Redis is selected; eager task execution where background task processing is selected) are delimited as `feature:redis` and `feature:celery` regions. Add their `[[regions]]` entries to the carrier if Story 4.4 did not already, and confirm the Story 7.2 region reconciler passes over them.
  - [ ] For each of the three moves, record in the carrier that it is a relocation of an earlier-authored declaration and name the story that authored it. Nothing about any assertion's meaning changes.

- [ ] Task 4 — Prove template measurement is real (AC: #1)
  - [ ] `COVERAGE_CORE = "ctrace"` is set at `pixi.toml:145-150` in `[activation.env]`, with the reasoning already recorded there: Python 3.12+ defaults to the `sysmon` core, which does not support the dynamic file tracer `django_coverage_plugin` needs, so templates are discovered but never traced and report a silent zero. Story 1.5 asserted it is in force during a gate run; extend that assertion to read the expected value from `[coverage].core` in the carrier rather than from a literal.
  - [ ] `COVERAGE_CORE` is not a `COMPONENT_*` variable, so AD-13's prohibition on `[activation.env]` does not apply to it. Do not move it out on that basis.
  - [ ] Template measurement also requires `TEMPLATES[0]["OPTIONS"]["debug"] = True`, set at `src/config/settings/test.py:43`, the `django_coverage_plugin` entry in `[tool.coverage.run] plugins` (`pyproject.toml:173`), and `template_extensions = "html"` (`pyproject.toml:178`). All three are preconditions for the zero-percent orphan signal; add an assertion that all three are in force, so a future change to any one of them fails the gate instead of blinding the detector.
  - [ ] The floor is 90% including templates, everywhere, never lowered, never per-directory, never cleared by a pragma on unreached code (AD-20, CG-1).

- [ ] Task 5 — Declare the residue detector for static assets and settings fragments (AC: #3)
  - [ ] The detector is carrier reconciliation of **materialized output**: any path present in a materialized tree that no selected feature claims is a defect. Materialized trees do not exist until Epic 8, so what lands here is the declaration and the reusable check.
  - [ ] Add `tools/materializer/residue.py` (NEW) with `detect_residue(carrier: Carrier, tree_root: Path, selection: frozenset[str]) -> list[str]`: for every path in the tree, resolve its disposition; report it if it is `core` (fine), `tenant` (fine), `feature:<name>` where `<name>` is in `selection` (fine), a declared generated artifact (fine — `.accelerator.json`, AD-17), and a defect otherwise.
  - [ ] Test it in this story against a **synthetic tree** built under `tmp_path` — a hand-assembled directory with a known planted orphan `.css` file and a known planted settings fragment. That proves the detector works without needing a materializer. The against-real-output run is Story 8.7's.
  - [ ] Do not implement the pruning half. This story detects; Epic 8 materializes and Story 8.7 runs the detector on real output.

- [ ] Task 6 — Record the deliberate-orphan test as an Epic 8 obligation (AC: #4)
  - [ ] AC #4's own final clause says it: *"the test that proves this runs in Epic 8, where a materialized combination exists to run it against."* This is a **traceability marker, not an acceptance condition for this story** — `epics.md:299` names Story 7.8's deliberate-orphan test as one of three such forward references, and `epics.md:222` states that FR-29's orphan signal is declared in Epic 7 and exercised per combination in Epic 8.
  - [ ] Record the obligation in `accelerator.toml` beside `[coverage]`: a deliberate-orphan test introduces an orphaned template override into a materialized combination and requires the gate to fail on the zero-percent coverage signal. Name it as owed by Epic 8 so it cannot be lost between the two epics.
  - [ ] Do not write a deliberate-orphan test against the reference application. The reference application is the all-features tree; an orphan planted there is covered by nothing and simply fails the floor, which proves the floor works but not that extraction leaves detectable residue.
  - [ ] Record AD-20's **time-boxed bring-up mode** beside the floor: *"Until the materializer has reported all six numbers once, materialized-combination gates run with the floor advisory and the numbers published as an artifact. The exit condition is that report; after it, the floor is hard everywhere."* The floor is hard on the reference application from the moment the gate consolidates — `test-cov` already carries `--cov-fail-under=90` (`pixi.toml:196`). Bring-up mode applies only to materialized combinations, and only until that one report exists.

- [ ] Task 7 — Tests (AC: all)
  - [ ] `tests/unit/materializer/test_residue.py` (NEW): `detect_residue` against synthetic `tmp_path` trees — clean tree reports nothing; planted orphan `.css` reports; planted orphan settings fragment reports; a `tenant` path never reports; `.accelerator.json` never reports.
  - [ ] `tests/integration/materializer/test_coverage_declaration.py` (NEW), `@pytest.mark.integration`: the effective `[tool.coverage.run]` omit/exclude/include lists equal `[coverage]` in the carrier, in both directions; `[coverage].floor` equals the `--cov-fail-under` value in `pixi.toml`'s `test-cov` task; the three template-measurement preconditions are in force.
  - [ ] `tests/integration/materializer/test_declaration_moves.py` (NEW), `@pytest.mark.integration`: the local sign-in name and prefix constants resolve from the carrier and match what the Story 3.4 route registers; the FR-14 regions reconcile.
  - [ ] Update Story 1.5's `COVERAGE_CORE` assertion to source its expected value from the carrier.
  - [ ] `pixi run ci` exits 0, coverage ≥90% including templates.

## Dev Notes

### Architecture Constraints

**AD-20 — the coverage floor is a single global constant, and what it measures is closed.** Binding rule: *"Ninety percent, including templates, everywhere. `COVERAGE_CORE=ctrace` travels with every combination and a test asserts it is in force during a gate run. Never a lower floor, a pragma, or a narrowed measurement. **The coverage `omit`/`exclude` list is a closed, carrier-declared surface** subject to two-way reconciliation, and the gate asserts the effective omit list equals the declared one — otherwise an epic clears its floor with one line and the only residue detector the product has goes blind."* Prevents: *"a per-combination floor becoming the place a structurally sparse combination hides; and the narrowing that is already precedented in this tree — `[tool.coverage.run] omit` — being used to clear the floor while every stated rule still passes."*

**CG-1 — do not reach the coverage threshold by narrowing what is measured.** *"Coverage includes templates precisely because that is the only signal that catches an orphan. Excluding files, adding coverage pragmas to unreached code, or dropping template measurement makes SC-1 pass and destroys SC-2."* If this story's work makes coverage fall, the answer is tests, never an omit entry.

**AD-1 — one declaration site.** After Task 2 the omit list is authored in `accelerator.toml` only. Same for the local sign-in constants after Task 3. The relocation must not leave the old site as a second authority.

**AD-21 / AD-26 — the local sign-in predicate resolves objects, never strings.** Moving the name and prefix constants into the carrier does not make them the predicate. *"The stage-2 predicate refuses any route whose view callable belongs to the local sign-in module (AD-26), never a name or prefix match."* Do not "simplify" the predicate to compare against the newly carrier-resident constants.

**AD-24 — the FR-14 refusals are declared regions.** Not unconditional code guarded by a flag (spine Consistency Conventions, "Feature-conditional code").

**AD-17 — generated artifacts have legal existence.** `.accelerator.json` is a declared generated artifact under AD-2's output reconciliation; the residue detector must not report it. No timestamp, sorted keys, and the reference application carries no stamp.

**AD-2 — output reconciliation.** *"Output, against each materialized tree: every path is either a copied path with a travelling disposition or a declared generated artifact, and nothing else."* That is Story 8.7's assertion; this story builds the function it calls.

**FR-29.** *"The orphan-detection property survives into the harness — template-inclusive coverage with `COVERAGE_CORE` pinned to the C trace core, plus carrier reconciliation for static assets and settings fragments."*

**Project standards.** Pixi is the only runner. Python 3.14 only. conda-forge only. PEP 8 / 120 / full type hints / Google docstrings. Never `print()`, never stdlib `logging`, never bare `except:`, never `except X: pass`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `accelerator.toml` | UPDATE | Add `[coverage]` (floor, core, omit, exclude, include), the local sign-in `[local_signin]` name/prefix constants, the FR-14 `[[regions]]` entries if absent, the three-category residue-detector mapping, and the Epic 8 deliberate-orphan obligation. Preserve everything Stories 7.1–7.7 declared. |
| `pyproject.toml` | UPDATE | Only if the effective configuration must change to match the declaration. **Today:** `[tool.coverage.run] include = [ "src/**" ]` (`:161`), `omit` (`:162-169`) = `*/migrations/*`, `*/tests/*`, `**/*.egg-info/**`, `src/config/wsgi.py`, `src/config/asgi.py`, `src/config/websocket.py`; `plugins = [ "django_coverage_plugin" ]` (`:173`); `[tool.coverage.django_coverage_plugin] template_extensions = "html"` (`:178`). **Preserve:** the plugin and `template_extensions` settings — they are template-measurement preconditions, and removing either blinds the detector. |
| the Story 1.5 declaration module | UPDATE | Read it before moving. Its declared list becomes the carrier's; its assertion now sources from the carrier. Meaning unchanged, both directions preserved. Its path is whatever Story 1.5 chose; find it rather than assuming. |
| the Story 3.4 local sign-in constants module | UPDATE | Same treatment. The route registration and the stage-2 predicate are untouched. |
| `tools/materializer/residue.py` | NEW | `detect_residue`, tested against synthetic trees. |
| `tools/materializer/carrier.py` | UPDATE | Add `Carrier.coverage()` and `Carrier.local_signin()`. Preserve all prior accessors. |
| `tests/unit/materializer/test_residue.py` | NEW | Synthetic-tree detector tests. |
| `tests/integration/materializer/test_coverage_declaration.py` | NEW | Two-way effective-equals-declared assertions, `@pytest.mark.integration`. |
| `tests/integration/materializer/test_declaration_moves.py` | NEW | The two relocations, `@pytest.mark.integration`. |

**Repository state, verified 2026-08-15.** `pixi.toml:145-150` sets `COVERAGE_CORE = "ctrace"` in `[activation.env]` with the sysmon/ctrace reasoning recorded inline. `pixi.toml:196` `test-cov` carries `--cov-fail-under=90`. `pixi.toml:206` `ci = { depends-on = ["test-cov", "lint", "typecheck", "build"] }` — note that AD-18 consolidates the gate into a single CI workflow invoking `pixi run ci`, which has never run in CI; that is Story 1.1's work, not this story's. `sonar-project.properties:23-24` carries `sonar.python.coverage.reportPaths=coverage.xml` and a `sonar.coverage.exclusions` list that includes `src/config/websocket.py` — AD-18 moves template coverage out of the SonarCloud workflow (Story 1.1); do not duplicate that here, but do check that the Sonar exclusion list has not become a second, unreconciled narrowing surface.

### Testing Requirements

- Unit: `tests/unit/materializer/test_residue.py` — isolated, milliseconds, synthetic trees under `tmp_path` only, no dependence on a materializer.
- Integration: `tests/integration/materializer/test_coverage_declaration.py` and `test_declaration_moves.py`, every test `@pytest.mark.integration`, read-only against the repository.
- The two-way coverage assertion must be genuinely two-directional. A one-direction check (declared ⊆ effective) passes while someone adds an omit line to `pyproject.toml`, which is precisely the one-line narrowing AD-20 exists to catch.
- Assert the floor value in the carrier equals the `--cov-fail-under` argument in `pixi.toml`'s `test-cov` task. Two numbers that can drift are two declarations.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` in force (AD-20). This story is where that becomes self-describing.
- Test disposition: these cover `machinery` and carry `machinery`. The **immovable-core assertion suite** is `core` and is Story 7.7's declaration plus Epic 8's implementation — do not confuse the two.

#### Project Structure Notes

- This story ends Epic 7's declaration work. After it, `accelerator.toml` is complete for Epic 8: features, dispositions, regions, parameters, presets, constraints, coverage, tenant root, guaranteed surface, immovable core, local sign-in constants, contributable surface, and the (still empty) pinned verification subset.
- **Ordering:** run this after Stories 7.1–7.7 and after Stories 1.5, 3.4 and 4.4, whose declarations it relocates. If any of those three has not landed, the corresponding move is deferred and must be recorded as owed rather than skipped silently.
- **Variance:** AD-19's pinned all-pairs subset is declared in `accelerator.toml` but cannot be populated until the six combinations exist. It stays an empty declared slot with a gate test asserting the pinned set satisfies the all-pairs predicate — vacuously true while empty, meaningful the moment Epic 8 fills it.
- The residue detector's static-asset and settings-fragment categories cannot be exercised against real output in this epic. That is stated honestly here rather than approximated with a reference-application test that would prove something different — the same discipline `epics.md`'s "External exit criteria" applies to SC-3 and SC-6.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-17]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-18]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-19]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-21]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.8]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.5] — the omit-list declaration and its two-way assertion
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.4] — the local sign-in name and prefix constants
- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.4] — the FR-14 feature-region markers
- [Source: _bmad-output/planning-artifacts/epics.md#Cross-epic threads] — line 222: declared in Epic 7, exercised per combination in Epic 8; line 225: the three relocations
- [Source: _bmad-output/planning-artifacts/epics.md#Reading the acceptance criteria] — line 299: Story 7.8's deliberate-orphan test is a traceability marker
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#CG-1]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#SC-2]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-29]
- Repository, verified 2026-08-15: `pixi.toml:145-150,196,206`; `pyproject.toml:161,162-169,173,178`; `src/config/settings/test.py:43`; `sonar-project.properties:23-24`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
