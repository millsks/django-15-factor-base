# Story 8.4: Materialization is deterministic and equivalent to the reference application

Status: ready-for-dev

## Story

As a platform engineer,
I want byte-identical output from identical selections,
so that a materialized combination is a reproducible artifact rather than a fresh result each run.

## Acceptance Criteria

**Traceability:** FR-30 · AD-3 · NFR-5

1. **Given** the same selections
   **When** materialization runs twice
   **Then** the two trees are byte-identical
   **And** a gate test asserts it

2. **Given** the all-features-selected combination
   **When** it is materialized
   **Then** its output is equivalent to the reference application

3. **Given** any source of nondeterminism — iteration order, timestamps, or filesystem ordering
   **When** output is written
   **Then** none reaches the tree

## Tasks / Subtasks

- [ ] Task 1: Remove every ordering-derived nondeterminism from the materializer (AC: #3)
  - [ ] In `tools/materializer/materialize.py`, walk the source tree in `sorted()` order at every directory level; never iterate a `set` or `dict` whose insertion order derives from a filesystem walk.
  - [ ] In `tools/materializer/carrier.py`, hold dispositions in a mapping whose iteration is sorted before use; return `tuple` rather than `list` from any function whose result feeds output.
  - [ ] In `tools/materializer/combination.py`, `enumerate_valid()` returns the twelve in a fixed, sorted-by-identifier order and never derives it from `frozenset` iteration.
  - [ ] Write every text file with `encoding="utf-8"` and `newline="\n"`; copy binary paths byte-for-byte.

- [ ] Task 2: Remove every time- and environment-derived nondeterminism (AC: #3)
  - [ ] No timestamp is written into any file the materializer produces. `.accelerator.json` is explicitly timestamp-free (AD-17, Story 8.11).
  - [ ] Do not preserve source mtimes into output metadata comparisons; the byte-identity assertion compares file **content** and the set of relative paths, not stat metadata, because mtimes cannot be made equal across two runs without lying about them.
  - [ ] No absolute path, hostname, user name, environment variable value, or `os.urandom`-derived value may appear in output.
  - [ ] `PYTHONHASHSEED` must not be relied on. If any code path sorts by hash, replace it with an explicit key.

- [ ] Task 3: Implement the tree comparison helper (AC: #1, #2)
  - [ ] `tools/materializer/compare.py` — `tree_digest(root: Path) -> str` computing a SHA-256 over the sorted sequence of `(relative_posix_path, sha256(content))` pairs. Directories contribute only through the paths beneath them; empty directories are recorded explicitly so an added or dropped empty directory is visible.
  - [ ] `diff_trees(a: Path, b: Path) -> tuple[str, ...]` returning a sorted, human-readable list of differing paths, so a failing assertion names what differed rather than reporting two hashes.

- [ ] Task 4: Define and assert equivalence to the reference application (AC: #2)
  - [ ] "Equivalent" is: for the all-features-selected combination, the set of paths in the output equals the set of reference-application paths that travel (`core`, `tenant`, and every `feature:*` path — all four features are selected), plus the declared generated artifacts, and the content of every such path is identical to the reference application's **except** for the feature-marker comment lines removed by Story 8.3 and the parameter substitutions applied by Story 8.6.
  - [ ] Implement `assert_equivalent_to_reference()` in the test, not in the materializer — this is a gate assertion, not a production code path.
  - [ ] State the exclusions explicitly in the assertion's failure message: markers removed, parameters substituted, `.accelerator.json` added, `machinery` paths absent.

- [ ] Task 5: The determinism gate test (AC: #1)
  - [ ] `tests/integration/materializer/test_determinism.py` (`@pytest.mark.integration`, `tmp_path`) — materialize one combination twice into two separate `tmp_path` subdirectories and assert `tree_digest(a) == tree_digest(b)`, reporting `diff_trees` on failure.
  - [ ] Repeat for all twelve, not one — the AC names one combination as the minimum; running twelve costs the same walk and catches a feature-specific ordering bug.
  - [ ] Add a second run under a different working directory and a different `tmp_path` prefix, to catch an absolute path leaking into output.
  - [ ] This test runs in `pixi run ci`; it is a gate test, not an optional check.

- [ ] Task 6: Unit tests (AC: #3)
  - [ ] `tests/unit/materializer/test_compare.py` — `tree_digest` is stable across two constructions of the same tree; differs when one byte differs; differs when an empty directory is added; `diff_trees` names the differing path.
  - [ ] `tests/unit/materializer/test_combination.py` (extend) — `enumerate_valid()` returns the same tuple across repeated calls and across processes with different hash seeds.

## Dev Notes

### Architecture Constraints

- **AD-3** (binding): "Determinism is asserted: a gate test materializes one combination twice and requires byte-identical trees."
- **NFR-5** (binding): "Determinism — materialization and dependency resolution are reproducible; the same selections and lock file produce the same component." The dependency-resolution half is Story 8.1's shared solve-group; this story owns the materialization half.
- **AD-17** (binding, and the reason a timestamp is forbidden): the provenance stamp carries "**No timestamp** — it would break determinism, and git already records when." Nothing else the materializer writes may carry one either.
- **AD-3, subtractive**: equivalence to the reference application for the all-features combination is a consequence of materialization being copy-then-remove. If the all-features output differs from the reference application by anything other than markers, parameters, generated artifacts and `machinery` paths, the materializer is transforming rather than subtracting and the implementation is wrong.
- **AD-2**: the only paths legally present in output are copied paths with a travelling disposition and declared generated artifacts. Story 8.7 asserts that as its own reconciliation; this story's equivalence check must not silently permit anything AD-2 forbids.
- Never `print()` a diff — return it and let the assertion message carry it. Never stdlib `logging`; `structlog` only.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tools/materializer/compare.py` | NEW | `tree_digest` and `diff_trees`. |
| `tools/materializer/materialize.py` | UPDATE | Created by Story 8.2, extended by Story 8.3. This story enforces sorted traversal, fixed newline and encoding, and no timestamp. Preserve the path-level and region-level pruning already implemented. |
| `tools/materializer/carrier.py` | UPDATE | Created by Story 8.2. Sorted iteration; tuple returns. Preserve `Disposition`'s four members and the `machinery` default. |
| `tools/materializer/combination.py` | UPDATE | Created by Story 8.2. Fix the enumeration order explicitly. Preserve the twelve-member result and the identifier format. |
| `tests/unit/materializer/test_compare.py` | NEW | |
| `tests/unit/materializer/test_combination.py` | UPDATE | Add the stable-ordering assertions. |
| `tests/integration/materializer/test_determinism.py` | NEW | The AD-3 gate test. |

#### Project Structure Notes

No structural change. All work sits inside `tools/materializer/` (machinery, per the Structural Seed) and its mirror under `tests/`. The determinism test is `machinery`-disposed and does not travel into a component.

### Testing Requirements

- `tests/integration/materializer/test_determinism.py` is the named gate test for AD-3 and must run in `pixi run ci`. It carries `@pytest.mark.integration`, uses `tmp_path` exclusively, and leaves nothing behind.
- Comparison is content-based: relative POSIX paths plus SHA-256 of bytes. Do **not** assert on `st_mtime`, `st_ino`, ownership or permissions beyond the executable bit, and if the executable bit is asserted, assert it explicitly rather than through a mode comparison.
- Unit tests must be hash-seed independent. If the test runner is invoked with `PYTHONHASHSEED=random`, `enumerate_valid()` must still return the same tuple.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` in force (AD-20). `tools/**` is inside `[tool.coverage.run] include` after Story 8.2.
- Assertions the ACs demand: two runs byte-identical for every combination; all-features output equivalent to the reference application under the four stated exclusions; no timestamp, absolute path, hostname or unsorted-iteration artifact in any output tree.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-3]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-17]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.4]
- [Source: _bmad-output/planning-artifacts/epics.md] — NFR-5, "Determinism — materialization and dependency resolution are reproducible"

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
