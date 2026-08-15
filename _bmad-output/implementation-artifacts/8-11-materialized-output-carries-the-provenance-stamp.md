# Story 8.11: Materialized output carries the provenance stamp

Status: ready-for-dev

## Story

As a platform engineer,
I want every materialized combination to record what produced it,
so that "which components predate this change" has an answer.

## Acceptance Criteria

**Traceability:** FR-36 · AD-17 · NFR-5

1. **Given** materialized output
   **When** it is produced
   **Then** `.accelerator.json` is written at its root carrying the accelerator version, the source ref and the full order values

2. **Given** the stamp
   **When** it is serialized
   **Then** keys are sorted
   **And** it carries no timestamp, because that would break determinism and git already records when

3. **Given** output reconciliation
   **When** the stamp is classified
   **Then** it is a declared generated artifact
   **And** it is never hand-edited

4. **Given** the reference application
   **When** it is inspected
   **Then** it carries no stamp

5. **Given** an external process
   **When** it enumerates components by version
   **Then** the stamp's location and format are stable enough to permit it

## Tasks / Subtasks

- [ ] Task 1: Define the stamp (AC: #1, #2, #5)
  - [ ] `tools/materializer/stamp.py` (NEW) — `build_stamp(order, accelerator_version, source_ref) -> dict[str, object]` and `write_stamp(output_root, stamp) -> None`.
  - [ ] Exactly three top-level keys, and the schema is the contract an external enumerator reads: `accelerator_version` (string), `source_ref` (string), `order` (object). `order` carries the **full** order values — the three feature booleans (`celery`, `redis`, `storage`) and every parameter value resolved by Story 8.6, not a subset and not just the selected features. There is no `ui` boolean; the interface mechanism is `core` (AD-29, revision 3).
  - [ ] Serialize with `json.dumps(stamp, sort_keys=True, indent=2)` plus a trailing newline. Sorted keys at every level, not only the top.
  - [ ] `accelerator_version` comes from the released, tagged version the generation ran from (AD-19's soundness precondition); `source_ref` is the git ref of that release. Derive both from the repository at materialization time; if neither can be resolved, raise `MaterializerError` rather than writing a placeholder — a misleading provenance record is the failure AD-17 names.

- [ ] Task 2: Forbid a timestamp (AC: #2)
  - [ ] No `datetime`, `time`, `os.stat` mtime or any other clock value may reach the stamp or any other materializer output.
  - [ ] `tests/unit/materializer/test_stamp.py` asserts the stamp's key set is exactly the three names and that no value parses as a date or a timestamp.
  - [ ] Two `build_stamp` calls with the same inputs, seconds apart, produce byte-identical JSON. This is a direct consequence of Story 8.4's determinism assertion and must not be left implicit.

- [ ] Task 3: Write the stamp during materialization (AC: #1)
  - [ ] Call `write_stamp()` as the **last** step of `materialize()` in `tools/materializer/materialize.py`, after path pruning, region pruning and parameter substitution. Writing it earlier would let a later pass read or overwrite it.
  - [ ] The stamp is written to `<output_root>/.accelerator.json` — at the root of materialized output, nowhere else, one per tree.

- [ ] Task 4: Classify it as a generated artifact (AC: #3)
  - [ ] Add `.accelerator.json` to `accelerator.toml`'s `[generated]` table (created by Story 8.7). It is currently the only entry.
  - [ ] Story 8.7's `reconcile_output()` already permits declared generated artifacts. Assert here that removing `.accelerator.json` from `[generated]` makes reconciliation report it as a violation — that is what proves the stamp's legality comes from the declaration rather than from a special case in the reconciler.
  - [ ] Add a `"_comment"`-free design note in the accelerator-facing documentation stating the stamp is machine-written and never hand-edited. Do not embed the warning in the JSON itself — a fourth key would break AC #1's schema and AC #5's stability.

- [ ] Task 5: Keep the reference application unstamped (AC: #4)
  - [ ] Add `.accelerator.json` to `.gitignore` so a stray stamp written into the working tree cannot be committed. The repository root has a `.gitignore` today.
  - [ ] `tests/unit/test_reference_application_is_unstamped.py` (NEW) — assert no `.accelerator.json` exists at the repository root. This is also the honest signal AD-32 describes: the GitHub-template fork "arrives unstamped".

- [ ] Task 6: Tests (AC: #1, #2, #3, #4, #5)
  - [ ] `tests/unit/materializer/test_stamp.py` — the three-key schema; sorted keys at every level; no timestamp; byte-identical output across repeated calls; the full order round-trips including every parameter and all three booleans; an unresolvable version or ref raises rather than defaulting.
  - [ ] `tests/integration/materializer/test_stamp_in_output.py` (`@pytest.mark.integration`, `tmp_path`) — materialize all six and assert each output root carries exactly one `.accelerator.json`; that the six stamps' `order` objects are pairwise distinct; that reconciliation passes with the stamp declared and fails with it undeclared; and that `json.load` on each stamp yields the combination the tree was materialized for.
  - [ ] Extend `tests/integration/materializer/test_determinism.py` (Story 8.4) coverage implicitly — the stamp is inside the tree the digest covers, so a nondeterministic stamp fails that test too. Do not weaken the digest to exclude it.

## Dev Notes

### Architecture Constraints

- **AD-17** (binding, in full): "The materializer writes `.accelerator.json` at the root of materialized output: accelerator version, source ref, and the full order values, serialized with sorted keys. **No timestamp** — it would break determinism, and git already records when. It is a declared generated artifact under AD-2's output reconciliation, never hand-edited. The reference application carries no stamp." *Prevents:* "a non-deterministic materialization; a misleading provenance record in a repository that was forked rather than generated."
- **Consistency Conventions, Declaration files**: "Hand-authored declarations are TOML and visible: `accelerator.toml`, `component.toml`, `pixi.toml`, `pyproject.toml`. Machine-written records are JSON and hidden: `.accelerator.json`. **Format signals authorship.**" The stamp is JSON and dot-prefixed for that reason; do not make it TOML and do not un-hide it.
- **AD-2**: "every path is either a copied path with a travelling disposition or a declared generated artifact, and nothing else." The stamp has no disposition — it is not copied. Its legality comes only from `[generated]`.
- **AD-28**: what a component states about *itself* belongs in `component.toml`. The stamp states what *produced* the component and is therefore not `component.toml` content. Do not merge them.
- **AD-32**: the GitHub-template fork "arrives unstamped (AD-17), which is the honest signal" that it copied `main` HEAD and carries machinery. Keeping the reference application unstamped is what makes that signal meaningful.
- **NFR-5**: determinism. The stamp sits inside the tree Story 8.4's digest covers, so any nondeterminism in it fails that gate test.
- **Deferred, for context, not for implementation**: "Propagating an accelerator change into existing components. PRD non-goal. `.accelerator.json` carries what a future tool would need." AC #5 is about the format being stable enough to permit that tool, not about building it.
- Never `print()`. Never a placeholder version string. Never bare `except:`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tools/materializer/stamp.py` | NEW | `build_stamp()` and `write_stamp()`. |
| `tools/materializer/materialize.py` | UPDATE | Created by Story 8.2 and extended by 8.3, 8.4, 8.5 and 8.6. This story appends `write_stamp()` as the final step. Preserve `validate()` as the first statement, the path and region pruning, sorted traversal, and parameter substitution ordering. |
| `tools/materializer/errors.py` | UPDATE | Created by Story 8.2. No new type is required if `MaterializerError` covers the unresolvable-version case; add one only if the CLI needs to distinguish it. |
| `accelerator.toml` | UPDATE | Adds `.accelerator.json` to `[generated]` (table created by Story 8.7). |
| `.gitignore` | UPDATE | Exists at the repository root. Add `.accelerator.json` so a stray stamp cannot be committed into the reference application. |
| `docs/` (accelerator-facing page) | UPDATE | Records that the stamp is machine-written and never hand-edited, and documents its three-key schema for the external enumerator of AC #5. Accelerator-facing, so it does not travel (NFR-8). |
| `tests/unit/materializer/test_stamp.py` | NEW | |
| `tests/unit/test_reference_application_is_unstamped.py` | NEW | |
| `tests/integration/materializer/test_stamp_in_output.py` | NEW | |

#### Project Structure Notes

The Structural Seed's second diagram shows `M["materializer"] --> STAMP[".accelerator.json"]` alongside the materialized-trees node and `M --> COMP`, confirming the stamp is a materializer output distinct from `component.toml`. (That node is still labelled `T12` in the spine's diagram, a leftover from the twelve-combination model; the count is six under revision 3 and the edge is what this story depends on, not the label.) No new directory is introduced; `tools/materializer/` is `machinery` and everything here lives inside it or in the carrier.

### Testing Requirements

- `tests/unit/materializer/test_stamp.py` — isolated, no filesystem beyond `tmp_path` for the write helper, milliseconds.
- `tests/unit/test_reference_application_is_unstamped.py` — a whole-repository policy test in the style of `tests/unit/test_dependency_policy.py`; it reads the repository root and asserts an absence.
- `tests/integration/materializer/test_stamp_in_output.py` — `@pytest.mark.integration`, `tmp_path`, leaves state as found.
- Specific assertions the ACs demand: exactly three top-level keys; sorted keys at every level; no timestamp anywhere; byte-identical across repeated builds; the full order present including all three booleans and every parameter; exactly one stamp per output root; six pairwise-distinct `order` objects; reconciliation passes only because the stamp is declared; no stamp in the reference application.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` (AD-20).
- Disposition: `tools/materializer/stamp.py` and all three test files are `machinery`. `.accelerator.json` itself is a declared generated artifact, which is a third category — neither copied nor `machinery`.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-17]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-28]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-32]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — "Format signals authorship"
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Structural Seed] — the materializer-to-stamp edge
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Deferred] — the stamp "carries what a future tool would need"
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.11]
- [Source: _bmad-output/planning-artifacts/epics.md] — FR-36, NFR-5

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
