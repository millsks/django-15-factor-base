---
baseline_revision: 32f0d5f
review_loop_iteration: 0
followup_review_recommended: true
status: done
---

# Story 1.7: No third-party package resolves from the package index

Status: done

## Story

As a platform engineer,
I want a test asserting the package-index block carries only the editable self-install,
so that a future supply-chain exception must be added deliberately rather than accumulating.

## Acceptance Criteria

**Traceability:** FR-49 · NFR-5, NFR-7

1. **Given** the `[pypi-dependencies]` block
   **When** the test runs
   **Then** its only entry is the component's own editable path install
   **And** any third-party entry fails the gate

2. **Given** the zero-exception state confirmed 2026-08-14
   **When** `django-celery-beat` is inspected
   **Then** it resolves from conda-forge
   **And** it is absent from the package-index block

3. **Given** a dependency line whose presence is not obvious
   **When** it is declared
   **Then** its reasoning is recorded beside it in `pixi.toml`
   **And** an exit condition is recorded where one applies

4. **Given** dependencies are lock-pinned
   **When** the environment is solved
   **Then** nothing relies on a system package

## Tasks / Subtasks

- [x] Task 1 — Confirm what already exists before writing anything (AC: #1, #2)
  - [x] `tests/unit/test_dependency_policy.py` already exists and already covers AC #1 and AC #2. Read it first. It defines `PIXI_MANIFEST = Path(__file__).resolve().parents[2] / "pixi.toml"` and `OWN_PACKAGE = "django-15-factor-base"`, and carries four tests: `test_manifest_is_present`, `test_no_third_party_package_index_dependencies` (asserts `set(manifest["pypi-dependencies"]) == {OWN_PACKAGE}`), `test_own_package_is_an_editable_path_install` (asserts the value is `{"path": ".", "editable": True}`), and `test_celery_beat_resolves_from_conda_forge` (asserts `"django-celery-beat" in manifest["dependencies"]`).
  - [x] Do **not** rewrite or relocate these tests. Extend the same file. Preserve the existing docstrings — they carry the `django-celery-beat` history (the `importlib-metadata<5.0` cap transcribed without its environment marker, colliding with `opentelemetry-api`) that `pixi.toml:22-34` also records.
  - [x] Verify the current state holds: `pixi.toml:98-99` declares exactly one `[pypi-dependencies]` entry, `django-15-factor-base = { path = ".", editable = true }`; `pixi.toml:35` declares `django-celery-beat = ">=2.9,<3"` under `[dependencies]`. Both confirmed 2026-08-15. **The project carries zero supply-chain exceptions today.**

- [x] Task 2 — Assert the rationale requirement for non-obvious declarations (AC: #3)
  - [x] Define, in the test module, the set of declarations that require a recorded reason. It must at minimum contain every dependency whose version specifier is `"*"` — today `uvicorn-standard` (`pixi.toml:74`), `git-cliff` (`:118`) and `watchdog` (`:130`) — plus every dependency the project imports directly but which is not obviously ours: `django-timezone-field`, `python-crontab`, `cron-descriptor` (`:37-39`, declared because `django-celery-beat` needs them), `hiredis` (`:46`), `opentelemetry-instrumentation-asgi` (`:66`), `hatchling` and `hatch-vcs` (`:79-80`), `libpq` (`:16`).
  - [x] Assert programmatically that each such name is immediately preceded in `pixi.toml` by at least one `#` comment line. Read `pixi.toml` as text (not just via `tomllib`, which discards comments), locate the declaration line, and walk backwards over contiguous `#` lines.
  - [x] Assert the exit-condition rule where one applies: any comment block that contains the word `exception` must also contain an exit condition. Express this as a checkable predicate (e.g. the block must contain `exit condition`). Today no block matches, because there are no exceptions — the test protects the future state.
  - [x] Where a required rationale is missing, **write it** rather than removing the name from the required set. Reasoning lives beside the configuration it constrains (spine §Consistency Conventions).

- [x] Task 3 — Assert lock-pinning and the absence of system-package reliance (AC: #4)
  - [x] Assert `pixi.lock` exists at the repository root and parses. It is large; parse it with `yaml.safe_load` only if memory permits, otherwise stream it — the dev agent chooses, but the assertion must be over parsed structure, not a substring grep.
  - [x] Assert every package resolved into the `default` and `dev` environments comes from `conda-forge` or is the one `pypi` entry for `django-15-factor-base`. A resolved package from any other channel, or a second `pypi` entry, fails.
  - [x] Assert every conda dependency in `pixi.toml [dependencies]`, `[target.*.dependencies]` and `[feature.dev.dependencies]` appears in the lock with a concrete resolved version — nothing left to solve at install time.
  - [x] Assert `pixi.toml [workspace] channels == ["conda-forge"]` (`:3`) — a second channel is a supply-chain change and must fail the gate.
  - [x] "Nothing relies on a system package" is asserted structurally: the C-library dependencies the application needs are declared as conda packages rather than assumed present. `libpq = ">=18.4,<19"` at `pixi.toml:16` is the concrete instance — assert it is declared, and assert its rationale comment exists per Task 2. Do not attempt to introspect the host OS; that would be a machine-dependent assertion and would not hold in CI across the three-OS matrix.
  - [x] If `yaml` is not importable in the `dev` environment, add `pyyaml` to `[feature.dev.dependencies]` from conda-forge. Never to `[pypi-dependencies]` — that is the very block AC #1 closes.

- [x] Task 4 — Record the policy where a contributor will meet it (AC: #1, #3)
  - [x] `pixi.toml:93-97` already carries the policy comment above `[pypi-dependencies]`: "The application itself, and nothing else. ... A third-party package appearing here is a supply-chain exception and needs the reasoning and an exit condition recorded beside it -- `tests/unit/test_dependency_policy.py` fails until that happens." Verify it still names the test file correctly after this story's edits; update it if the test file gains a second module.
  - [x] Add a short "Supply chain" section to `docs/development.md`: conda-forge is the single channel; `[pypi-dependencies]` carries the editable self-install and nothing else; a directly-imported package is declared directly even when something else already pulls it in transitively; a reusable app must reach the channel before a component may depend on it; channel presence alone is not fitness (Story 1.8 / FR-50).

- [x] Task 5 — Tests (AC: #1, #2, #3, #4)
  - [x] Extend `tests/unit/test_dependency_policy.py` with: `test_channels_are_conda_forge_only`; `test_non_obvious_declarations_carry_rationale`; `test_declared_exceptions_carry_an_exit_condition`; `test_lock_file_resolves_every_declared_dependency`; `test_lock_file_has_no_non_conda_forge_source`; `test_libpq_is_declared_rather_than_assumed`.
  - [x] Each test asserts one property and its failure message names the offending package, so a future contributor sees what to fix without reading the test.
  - [x] Keep the module-scoped `manifest` fixture pattern already in the file; add a parallel module-scoped fixture for the parsed lock so it is read once.
  - [x] No marker — this is manifest and lock parsing, unit-scope, milliseconds. Reading `pixi.lock` from disk is repository-file reading, not I/O against a resource.

## Dev Notes

### Architecture Constraints

- **FR-49:** "Single audited channel with recorded exceptions — zero exceptions; a test asserts no third-party package resolves from the package index; dependencies lock-pinned with no system packages."
- **Spine §Consistency Conventions — Supply chain:** "conda-forge only; `[pypi-dependencies]` carries the editable self-install and nothing else. Transitive availability is not declaration: a package the code imports directly is declared directly, even when something else already pulls it in. A reusable app must reach the channel before a component may depend on it."
- **Spine §Consistency Conventions — Rationale:** "Reasoning lives beside the configuration it constrains, in the same file, as `pixi.toml` already does." AC #3 is this convention made checkable.
- **NFR-5 — Determinism:** "materialization and dependency resolution are reproducible; the same selections and lock file produce the same component." AC #4's lock-pinning assertion is the dependency-resolution half.
- **NFR-7 — Secrets never live in source.** Not exercised by this story's implementation; it is carried in the story's requirements line because the supply-chain surface is where an unaudited package would introduce one. Add no secret-scanning here — Epic 3 Story 3.5 owns the gitignored development keypair.
- **Stack table (spine §Stack), authoritative — do not web-search versions:** django-allauth 65.19.1 with `requests` declared directly (divergence D-4: the channel recipe declares only `asgiref`/`django`, but the OIDC provider imports `requests`, so it must be declared directly under the transitive-availability rule). `requests` is **not** declared in `pixi.toml` today. Epic 2 adds it when the OIDC provider is wired. **Do not add it in this story** — it would declare a dependency for code that does not exist yet. Record the pending obligation in Completion Notes so Epic 2's author sees it.
- **AD-3:** "All six environments share one `solve-group`, without which `django-celery-beat`'s `django <6.1` cap makes the two Celery combinations resolve a different Django from the other four and SC-1 stops meaning what it says." Today `[environments]` at `pixi.toml:141-143` has only `default` and `dev`, both `solve-group = "default"`. The six-environment matrix is Epic 8 Story 8.1. Write the lock assertions so they hold over whatever environments exist rather than hard-coding the two.
- **Forbidden:** adding any third-party entry to `[pypi-dependencies]`; adding a second channel to `[workspace] channels`; using `pip`, `uv`, `uvx` or bare `python`/`pytest` anywhere. Pixi is the only runner: `pixi run python`, `pixi run test`, `pixi run ci`.

### Source Tree — files to touch

| Path | NEW or UPDATE | What changes |
| --- | --- | --- |
| `tests/unit/test_dependency_policy.py` | UPDATE | 66 lines today. Already asserts AC #1 and AC #2 in full (`test_no_third_party_package_index_dependencies`, `test_own_package_is_an_editable_path_install`, `test_celery_beat_resolves_from_conda_forge`). This story adds the AC #3 rationale assertions and the AC #4 lock-pinning assertions. Preserve every existing test and docstring. |
| `pixi.toml` | UPDATE (only where a rationale is missing) | `[workspace] channels = ["conda-forge"]` (`:3`); `[dependencies]` (`:14-80`); `[target.linux-64.dependencies]` / `[target.osx-arm64.dependencies]` (`:85-91`); `[pypi-dependencies]` with its policy comment (`:93-99`); `[pypi-options] no-build-isolation` (`:103-104`); `[feature.dev.dependencies]` (`:106-132`). Add rationale comments where Task 2's required set finds none. Change no version specifier. |
| `pixi.lock` | UNCHANGED — read only | Lock-file format v7 (the `setup-pixi` comment at `.github/workflows/ci.yml:25-27` records that v0.67.2 caps at v6). Never hand-edit; regenerate only via `pixi` if a dependency genuinely changes. |
| `docs/development.md` | UPDATE | Adds the "Supply chain" section. |

**Verified today (2026-08-15):** `[pypi-dependencies]` contains exactly one key. `django-celery-beat` is in `[dependencies]`. `channels = ["conda-forge"]`. The project carries **zero** supply-chain exceptions — consistent with `epics.md:98`'s "zero exceptions" and the "zero-exception state confirmed 2026-08-14" in AC #2.

### Testing Requirements

- Test file: `tests/unit/test_dependency_policy.py` — extended, not replaced. Unit scope: parses `pixi.toml` and `pixi.lock` from disk, no network, no database, no marker.
- Paths resolve from `Path(__file__).resolve().parents[2]`, the pattern already at `:11`.
- Assertions the ACs demand, each its own test function: `[pypi-dependencies]` has exactly the one editable self-install key (existing); its value is `{"path": ".", "editable": True}` (existing); `django-celery-beat` is under `[dependencies]` and absent from `[pypi-dependencies]` (existing, extend with the absence half); channels are conda-forge only; every non-obvious declaration carries a preceding comment; any comment naming an exception also names an exit condition; every declared dependency resolves in `pixi.lock`; no lock entry resolves from a channel other than conda-forge except the one pypi self-install; `libpq` is declared.
- Coverage floor 90% including templates (AD-20); `--cov-fail-under=90` at `pixi.toml:196`.
- Test disposition (spine §Consistency Conventions): this file covers the supply-chain policy, which is `machinery`-adjacent but applies to every component's `pixi.toml`; its disposition is assigned in Epic 7 Story 7.1. Note the question in Completion Notes rather than deciding it here.

#### Project Structure Notes

No structural change. `pixi.toml` is one of the four hand-authored TOML declarations the spine names ("Declaration files | Hand-authored declarations are TOML and visible: `accelerator.toml`, `component.toml`, `pixi.toml`, `pyproject.toml`"); two of those four do not exist yet.

Variance from the Structural Seed: `pixi.toml` is annotated as carrying "feature matrix, environments+solve-group, process tasks (AD-3, AD-13, AD-14)". Today it carries neither the feature matrix (Epic 8), the `COMPONENT_RUNTIME=local` task env (Epic 3), nor the `web`/`worker`/`beat` process tasks (Epic 5). Only the supply-chain blocks this story touches exist. `epics.md:307` records that `pixi.toml` is deliberately shared across five epics as distinct blocks with distinct owners — stay inside the supply-chain blocks.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.7]
- [Source: _bmad-output/planning-artifacts/epics.md:98] — FR-49.
- [Source: _bmad-output/planning-artifacts/epics.md:307] — assessed `pixi.toml` overlap across Epics 1, 3, 5, 7, 8.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — supply chain, rationale, declaration files.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-3] — the shared solve-group.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Stack] — divergence D-4, `requests` must be declared directly (Epic 2).
- [Source: _bmad-output/planning-artifacts/epics.md:116] — NFR-5.

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Claude Opus 5, 1M context)

### Debug Log References

- `pixi run test` — 201 passed (10 in `tests/unit/test_dependency_policy.py`).
- `pixi run format` / `pixi run lint` / `pixi run typecheck` — clean. One ruff
  finding fixed en route: `PERF401` on the lock-resolution loop.
- `pixi run ci` — **exit 0**. `test-cov`: 273 passed, total coverage **92.46%**
  (floor 90).
- `pixi.lock` parse cost: **16 ms** with `yaml.CSafeLoader`, 113 ms with the
  pure-Python `SafeLoader`. The module-scoped `lock` fixture parses once, so the
  cost is paid once for the whole file. Nothing is hidden here.

### Completion Notes List

- **The spec's line references were stale and its `libpq` value was wrong.**
  Story 1.2 pinned `libpq = ">=17,<18"` to match the `postgres:17` gate server;
  the spec quotes `>=18.4,<19`. Every reference in Tasks 1-4 was re-verified
  against the current `pixi.toml` rather than trusted. No version specifier was
  changed by this story.
- **The rationale rule (Task 2) had to be defined more precisely than the spec
  states it.** "Walk backwards over contiguous `#` lines" fails for
  `python-crontab` and `cron-descriptor` (a run of three declarations headed by
  one comment block) and for `watchdog` (trailing comment, no preceding block).
  The implemented rule, documented on `_rationale` in the test module: a
  declaration is explained if it has a trailing `#` comment, **or** if walking
  backwards — stepping over *bare* declarations, ones with no comment of their
  own — reaches a `#` comment block before hitting a blank line, a `[table]`
  header, or a declaration that carries its own trailing comment. The last of
  those is what keeps it strict: an uncommented dependency appended to the end
  of a table is not credited with a neighbour's reason. Verified by simulation
  against three insertion points.
- **Two rationale comments were written into `pixi.toml` rather than dropping
  the names from the required set**, as Task 2 directs: `hiredis` (the C parser
  redis-py selects automatically when importable, declared directly instead of
  arriving transitively behind `django-redis`) and `git-cliff` (CHANGELOG
  generation for the `changelog` task, which `release.yml` also runs; unpinned
  because it is a standalone Rust binary with no Python API this project
  imports, and its configuration surface is `[tool.git-cliff]` in
  `pyproject.toml`).
- **The exit-condition rule is scoped to declaration-attached comments.** A
  comment block is checked when it is a rationale for a declaration, not when it
  is table-level prose. Without that scoping the header at `pixi.toml:9-13`
  ("there are no exceptions") would be a false positive. The test carries a
  non-vacuity guard — it fails if the parser finds no rationale at all — so it
  cannot pass because the parser broke. Today no declaration matches, which is
  the zero-exception state AC #2 records.
- **No conda name-mapping problem exists.** Every declared name (`redis-py`,
  `django_coverage_plugin`, `python-build`, `factory_boy`, `uvicorn-standard`)
  matches its lock filename stem exactly, so the lock assertion resolves all 66
  declarations across both environments and all three platforms with nothing
  skipped. `_conda_package` raises rather than skipping if a filename ever fails
  to split.
- **The lock assertions iterate whatever environments the lock declares** and
  derive each environment's features from `[environments]`, so the
  six-environment matrix of Epic 8 Story 8.1 is covered without editing this
  module (AD-3).
- **Pending obligation for Epic 2 — `requests` (divergence D-4).**
  django-allauth's OIDC provider imports `requests`, and the conda-forge recipe
  declares only `asgiref`/`django`, so under the transitive-availability rule it
  must be declared directly in `[dependencies]`. It is **not** declared today and
  was deliberately not added here — that would declare a dependency for code
  that does not exist yet. Epic 2 declares it when the provider is wired. Note
  that `test_non_obvious_declarations_carry_rationale` will not force a comment
  on it automatically (it is version-pinned, not `"*"`), so whoever adds it
  should also add it to `RATIONALE_REQUIRED` in
  `tests/unit/test_dependency_policy.py`.
- **Test disposition question, noted rather than decided** (spine §Consistency
  Conventions): `tests/unit/test_dependency_policy.py` covers the supply-chain
  policy, which is `machinery`-adjacent but applies to every component's
  `pixi.toml`. Its disposition is assigned in Epic 7 Story 7.1. This story does
  not decide it.
- **Two stale documentation claims were corrected as part of Task 4**, because
  both asserted a supply-chain exception this story's tests now prove does not
  exist. `docs/development.md:65-68` said "`pixi.lock` holds exactly two PyPI
  entries ... and `django-celery-beat`"; the lock holds exactly one.
  `docs/observability.md` §"Note on dependencies" said `django-celery-beat`
  comes from PyPI, and its own closing sentence instructed that the note be
  deleted once the move landed — which it has. The heading was kept and the body
  rewritten, so the anchor stays valid for any external link.
- **`pyyaml` was already declared** at `pixi.toml:137` under
  `[feature.dev.dependencies]`; Task 3's conditional authorisation to add it was
  not needed.
- The `[pypi-dependencies]` policy comment still names
  `tests/unit/test_dependency_policy.py` correctly — this story added no second
  test module, so Task 4's first subtask needed no edit.

### File List

- `tests/unit/test_dependency_policy.py` — UPDATE. Extended from 4 tests to 10;
  every existing test and docstring preserved. Adds the `manifest_lines` and
  `lock` module-scoped fixtures, the manifest text-scanning helpers, and
  `test_channels_are_conda_forge_only`,
  `test_non_obvious_declarations_carry_rationale`,
  `test_declared_exceptions_carry_an_exit_condition`,
  `test_lock_file_resolves_every_declared_dependency`,
  `test_lock_file_has_no_non_conda_forge_source`,
  `test_libpq_is_declared_rather_than_assumed`.
  `test_celery_beat_resolves_from_conda_forge` gained AC #2's absence half.
- `pixi.toml` — UPDATE. Two rationale comments added (`hiredis`, `git-cliff`).
  No version specifier, table, channel or environment changed.
- `docs/development.md` — UPDATE. New "## Supply chain" section; the stale
  two-PyPI-entries paragraph in "Environment" corrected.
- `docs/observability.md` — UPDATE. §"Note on dependencies" rewritten; it
  described a supply-chain exception that no longer exists.
- `pixi.lock` — read only, unchanged.

## Review Triage Log

### 2026-08-16 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 13: (high 2, medium 4, low 7)
- defer: 2: (high 0, medium 1, low 1)
- reject: 6: (high 0, medium 0, low 6)
- addressed_findings:
  - `[high]` `[patch]` `_rationale` walked backwards over uncommented
    declarations, so 22 of the manifest's 67 declarations were credited with a
    comment written about a different package, and a new dependency inserted
    anywhere inside such a run passed AC #3 having recorded no reason at all.
    All three hunters found it independently and executed it. Since both
    dependency tables are alphabetically ordered, a new name normally lands in
    the credited middle, so the guard was defeated by the ordinary case. Rewrote
    the walk to strict adjacency — a trailing comment, or a block on the lines
    immediately above — rebuilt the docstring around it, and gave `python-crontab`
    its own trailing rationale, the one required name the strict rule left
    unexplained. Borrowing measured after the fix: 0.
  - `[high]` `[patch]` The module pinned registry hosts —
    `CONDA_FORGE_URL = "https://conda.anaconda.org/conda-forge/"` and
    `PERMITTED_INDEXES = {"https://pypi.org/simple"}` — at three assertion sites.
    This accelerator is used where those are fronted by a private mirror, which
    preserves neither the host nor `conda-forge` as a path segment of its own
    (`.../api/conda/conda-forge-remote/`), so the gate would have failed on a
    supply chain that was exactly as declared. Replaced with `_is_conda_forge`,
    matching the channel name by containment, and dropped the index-URL rule
    entirely in favour of the host-agnostic invariant already asserted: nothing
    but the editable self-install resolves from an index at all.
  - `[medium]` `[patch]` The `try: from yaml import CSafeLoader` /
    `except ImportError` fallback is an assignment error under the project's
    strict mypy; it escaped only because `typecheck` and the pre-commit hook are
    both scoped to `src/`. Replaced with a `getattr` bound to `Any`.
  - `[medium]` `[patch]` The lock test asserted a package was *present*, never
    that its version satisfied the declared specifier. Widening `libpq` to
    `>=18,<19` against a lock holding 17.11 — the exact edit the comment beside
    it invites — passed. Added `_satisfies`/`_version_key`, a conda-flavoured
    comparator that raises on an unrecognised constraint rather than skipping it.
  - `[medium]` `[patch]` The new `hiredis` rationale claimed it would otherwise
    "arrive transitively behind django-redis". The lock shows `django-redis`
    depends on django/python/redis-py/typing_extensions and `redis-py` on
    async-timeout/python — neither pulls `hiredis`, so undeclared it would not
    arrive at all. Corrected the comment.
  - `[medium]` `[patch]` The exit-condition rule fired only when the rationale
    contained the literal word "exception", so a carve-out worded "Temporary: no
    conda-forge build yet" escaped it. Keyed the rule on location as well — any
    third-party key under a `[pypi-dependencies]` table is an exception by
    definition, which is what the policy comment above that table already says.
  - `[low]` `[patch]` `_offending_sources` re-parsed an offending URL for a
    package name inside its own failure message; a foreign channel need not use
    conda's `name-version-build` filename, so `_conda_package` raised
    `ValueError` in place of the assertion. Reports the URL instead.
  - `[low]` `[patch]` The table form `foo = { version = "*" }` is legal pixi and
    evaded both the unpinned auto-enrolment and the `libpq != "*"` guard. Every
    rule now reads specifiers through `_version_spec`.
  - `[low]` `[patch]` Task 3's "assert `pixi.lock` exists and parses" was ticked
    but unimplemented — a missing lock surfaced as a raw fixture error in several
    tests at once. Added `test_lock_is_present`.
  - `[low]` `[patch]` `test_channels_are_conda_forge_only` read only
    `[workspace] channels`; a per-feature `channels` list and a per-dependency
    `channel =` key are two more ways a second source arrives. Both now checked.
  - `[low]` `[patch]` Three vacuity holes in the lock test: a platform declared
    in `[workspace] platforms` but absent from the lock was skipped silently, an
    environment resolving zero packages passed, and an environment naming an
    undefined feature dropped that feature's whole dependency set. All three now
    fail loudly.
  - `[low]` `[patch]` `docs/development.md` claimed verification "for every
    environment and platform" and that "nothing here relies on a package the host
    happens to provide" when only `libpq` was asserted. Narrowed both claims to
    what the tests actually do, and made the adjacency rule explicit where the
    rationale policy is stated.
  - `[low]` `[patch]` The helpers carrying these rules had no direct tests and
    are not measured by `--cov=src`, which is why the `_rationale` defect shipped.
    Added `test_rationale_does_not_borrow_a_neighbours_comment`,
    `test_channel_is_identified_by_name_not_by_host` and
    `test_satisfies_compares_versions_rather_than_strings`.

Not this story's problem: two findings deferred (CI never runs pixi with
`--locked`/`--frozen`, so a stale committed lock is invisible to the gate; the
`docs` task is not in the `ci` chain, so the new cross-document anchor is
unchecked). Six rejected as noise, the notable ones being the "duplicate" AC #2
absence assertion (deliberate, and the spec asked for it), and a claimed
`django-celery-beat` build mismatch in `docs/observability.md` (the doc says the
cap was removed *since* build `pyhcf101f3_1`, which the lock resolving `_2` does
not contradict).

## Auto Run Result

Status: done

### Implemented change

`tests/unit/test_dependency_policy.py` grows from four tests to seventeen, turning
the supply-chain policy from a convention recorded in comments into a gate
condition. AC #1 and AC #2 were already asserted; this story adds AC #3 (every
non-obvious declaration records why it is there, and anything declared an
exception records what retires it) and AC #4 (every declared dependency resolves
in `pixi.lock` to a concrete version satisfying its declared range, on every
declared environment and platform, from the audited channel alone). The policy is
written down where a contributor meets it, in a new "Supply chain" section of
`docs/development.md`.

The project's zero-exception state is confirmed rather than assumed:
`[pypi-dependencies]` carries only `django-15-factor-base = { path = ".",
editable = true }`, `django-celery-beat` resolves from conda-forge, and
`channels = ["conda-forge"]`. No version specifier changed and `pixi.lock` was
not touched.

### Files changed

- `tests/unit/test_dependency_policy.py` — 4 tests to 17. Every original test and
  docstring preserved. Adds `manifest_lines` and `lock` module-scoped fixtures,
  the manifest text-scanning helpers, a conda version comparator, and the AC #3
  and AC #4 assertions.
- `pixi.toml` — rationale comments for `hiredis`, `git-cliff` and
  `python-crontab`; the `django-celery-beat` dependency-group header reworded. No
  specifier, table, channel or environment changed.
- `docs/development.md` — new "## Supply chain" section; the stale
  two-PyPI-entries paragraph in "Environment" corrected.
- `docs/observability.md` — §"Note on dependencies" rewritten. It still described
  `django-celery-beat` as resolving from PyPI, which `pixi.toml` contradicts and
  the new tests prove false.
- `pixi.lock` — read only, unchanged.

### Review findings

Three hunters (adversarial, edge-case, verification-gap) ran in parallel against
the diff. 13 patches applied, 2 items deferred, 6 rejected. No intent gap and no
spec defect, so no repair loopback ran; `review_loop_iteration` stayed at 0. The
full breakdown is in the Review Triage Log above.

The consequential find, reached independently by all three: the rationale rule
credited a declaration with whichever comment happened to head its run, so 22 of
67 declarations were "explained" by a comment about a different package and a new
dependency could land unexplained. AC #3's mechanism did not hold. It does now,
and the regression is pinned by a test.

### Verification performed

- `pixi run ci` — **exit 0**. 277 passed, coverage 92.46% against the 90% floor.
- `pixi run -e dev python -m pytest tests/unit/test_dependency_policy.py` — 17
  passed in 0.13 s. Parsing the 270 KB lock costs ~16 ms via `CSafeLoader`, paid
  once per module.
- Each patched rule was verified by mutation rather than by inspection: an
  uncommented dependency inserted mid-run, a manifest range widened without
  re-solving, a table-form wildcard, a third-party key added to
  `[pypi-dependencies]`, a per-dependency `channel =`, and a hostile artifact URL
  were each confirmed to fail a named assertion with a message identifying the
  offending package. Comment borrowing measured before and after: 22 to 0.
- `pixi run docs` — builds clean under `--strict`, checked because of the new
  cross-document anchor.
- The `hiredis` rationale was checked against `pixi.lock` rather than accepted:
  neither `django-redis` nor `redis-py` depends on it.

### Residual risks

- **The lock is verified, but not verified to be current.** Nothing passes
  `--locked`/`--frozen`, so `pixi run ci` may re-solve before the assertions read
  the lock. Deferred — the repair belongs to the gate's shape, which Story 1.1
  owns.
- **`RATIONALE_REQUIRED` is hand-maintained** for version-pinned dependencies;
  only `"*"`-pinned ones enrol automatically. Adding a non-obvious dependency with
  a version range and no comment still passes. Recorded in Completion Notes
  against Epic 2's `requests` (divergence D-4), which is the next known instance.
- **`_satisfies` implements a conda-flavoured subset** of version comparison —
  `>=`/`>`/`<=`/`<`/`==`/`!=`, globs and `*`. It raises on anything else rather
  than skipping, so an unsupported form fails loudly instead of silently passing.
- **Channel identity is matched by containment** (`"conda-forge" in url`) so that
  a private mirror naming the repository `conda-forge-remote` passes. A foreign
  channel served from a path that happened to contain the string would too. This
  is the deliberate trade for mirror portability.
- **Test disposition is still open.** This file is `machinery`-adjacent but
  applies to every component's `pixi.toml`; Epic 7 Story 7.1 assigns it. Noted,
  not decided.
