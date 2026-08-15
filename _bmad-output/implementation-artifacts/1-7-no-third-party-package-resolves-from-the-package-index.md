# Story 1.7: No third-party package resolves from the package index

Status: ready-for-dev

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

- [ ] Task 1 — Confirm what already exists before writing anything (AC: #1, #2)
  - [ ] `tests/unit/test_dependency_policy.py` already exists and already covers AC #1 and AC #2. Read it first. It defines `PIXI_MANIFEST = Path(__file__).resolve().parents[2] / "pixi.toml"` and `OWN_PACKAGE = "django-15-factor-base"`, and carries four tests: `test_manifest_is_present`, `test_no_third_party_package_index_dependencies` (asserts `set(manifest["pypi-dependencies"]) == {OWN_PACKAGE}`), `test_own_package_is_an_editable_path_install` (asserts the value is `{"path": ".", "editable": True}`), and `test_celery_beat_resolves_from_conda_forge` (asserts `"django-celery-beat" in manifest["dependencies"]`).
  - [ ] Do **not** rewrite or relocate these tests. Extend the same file. Preserve the existing docstrings — they carry the `django-celery-beat` history (the `importlib-metadata<5.0` cap transcribed without its environment marker, colliding with `opentelemetry-api`) that `pixi.toml:22-34` also records.
  - [ ] Verify the current state holds: `pixi.toml:98-99` declares exactly one `[pypi-dependencies]` entry, `django-15-factor-base = { path = ".", editable = true }`; `pixi.toml:35` declares `django-celery-beat = ">=2.9,<3"` under `[dependencies]`. Both confirmed 2026-08-15. **The project carries zero supply-chain exceptions today.**

- [ ] Task 2 — Assert the rationale requirement for non-obvious declarations (AC: #3)
  - [ ] Define, in the test module, the set of declarations that require a recorded reason. It must at minimum contain every dependency whose version specifier is `"*"` — today `uvicorn-standard` (`pixi.toml:74`), `git-cliff` (`:118`) and `watchdog` (`:130`) — plus every dependency the project imports directly but which is not obviously ours: `django-timezone-field`, `python-crontab`, `cron-descriptor` (`:37-39`, declared because `django-celery-beat` needs them), `hiredis` (`:46`), `opentelemetry-instrumentation-asgi` (`:66`), `hatchling` and `hatch-vcs` (`:79-80`), `libpq` (`:16`).
  - [ ] Assert programmatically that each such name is immediately preceded in `pixi.toml` by at least one `#` comment line. Read `pixi.toml` as text (not just via `tomllib`, which discards comments), locate the declaration line, and walk backwards over contiguous `#` lines.
  - [ ] Assert the exit-condition rule where one applies: any comment block that contains the word `exception` must also contain an exit condition. Express this as a checkable predicate (e.g. the block must contain `exit condition`). Today no block matches, because there are no exceptions — the test protects the future state.
  - [ ] Where a required rationale is missing, **write it** rather than removing the name from the required set. Reasoning lives beside the configuration it constrains (spine §Consistency Conventions).

- [ ] Task 3 — Assert lock-pinning and the absence of system-package reliance (AC: #4)
  - [ ] Assert `pixi.lock` exists at the repository root and parses. It is large; parse it with `yaml.safe_load` only if memory permits, otherwise stream it — the dev agent chooses, but the assertion must be over parsed structure, not a substring grep.
  - [ ] Assert every package resolved into the `default` and `dev` environments comes from `conda-forge` or is the one `pypi` entry for `django-15-factor-base`. A resolved package from any other channel, or a second `pypi` entry, fails.
  - [ ] Assert every conda dependency in `pixi.toml [dependencies]`, `[target.*.dependencies]` and `[feature.dev.dependencies]` appears in the lock with a concrete resolved version — nothing left to solve at install time.
  - [ ] Assert `pixi.toml [workspace] channels == ["conda-forge"]` (`:3`) — a second channel is a supply-chain change and must fail the gate.
  - [ ] "Nothing relies on a system package" is asserted structurally: the C-library dependencies the application needs are declared as conda packages rather than assumed present. `libpq = ">=18.4,<19"` at `pixi.toml:16` is the concrete instance — assert it is declared, and assert its rationale comment exists per Task 2. Do not attempt to introspect the host OS; that would be a machine-dependent assertion and would not hold in CI across the three-OS matrix.
  - [ ] If `yaml` is not importable in the `dev` environment, add `pyyaml` to `[feature.dev.dependencies]` from conda-forge. Never to `[pypi-dependencies]` — that is the very block AC #1 closes.

- [ ] Task 4 — Record the policy where a contributor will meet it (AC: #1, #3)
  - [ ] `pixi.toml:93-97` already carries the policy comment above `[pypi-dependencies]`: "The application itself, and nothing else. ... A third-party package appearing here is a supply-chain exception and needs the reasoning and an exit condition recorded beside it -- `tests/unit/test_dependency_policy.py` fails until that happens." Verify it still names the test file correctly after this story's edits; update it if the test file gains a second module.
  - [ ] Add a short "Supply chain" section to `docs/development.md`: conda-forge is the single channel; `[pypi-dependencies]` carries the editable self-install and nothing else; a directly-imported package is declared directly even when something else already pulls it in transitively; a reusable app must reach the channel before a component may depend on it; channel presence alone is not fitness (Story 1.8 / FR-50).

- [ ] Task 5 — Tests (AC: #1, #2, #3, #4)
  - [ ] Extend `tests/unit/test_dependency_policy.py` with: `test_channels_are_conda_forge_only`; `test_non_obvious_declarations_carry_rationale`; `test_declared_exceptions_carry_an_exit_condition`; `test_lock_file_resolves_every_declared_dependency`; `test_lock_file_has_no_non_conda_forge_source`; `test_libpq_is_declared_rather_than_assumed`.
  - [ ] Each test asserts one property and its failure message names the offending package, so a future contributor sees what to fix without reading the test.
  - [ ] Keep the module-scoped `manifest` fixture pattern already in the file; add a parallel module-scoped fixture for the parsed lock so it is read once.
  - [ ] No marker — this is manifest and lock parsing, unit-scope, milliseconds. Reading `pixi.lock` from disk is repository-file reading, not I/O against a resource.

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

### Debug Log References

### Completion Notes List

### File List
