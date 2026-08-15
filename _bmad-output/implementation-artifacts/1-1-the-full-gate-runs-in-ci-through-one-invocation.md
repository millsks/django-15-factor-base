---
baseline_commit: b704abe3a57db26b5682a7d324fbce2a4d21ed6e
---

# Story 1.1: The full gate runs in CI through one invocation

Status: review

## Story

As a platform engineer,
I want the complete quality gate to run in CI through a single invocation,
so that "this component passed its gate" is a statement the pipeline makes rather than a developer's laptop.

## Acceptance Criteria

**Traceability:** AD-18 · supports FR-32, NFR-4

1. **Given** `pixi run ci` has never run in CI
   **When** a pull request or a push to `main` runs
   **Then** exactly one workflow invokes `pixi run ci`
   **And** it runs pre-commit, build, check, lint and cov in that order

2. **Given** template coverage measurement currently lives in the SonarCloud workflow
   **When** the consolidation lands
   **Then** template coverage is measured inside `pixi run ci`
   **And** the SonarCloud workflow no longer owns it

3. **Given** `build` runs on a fortnightly cron today
   **When** the consolidation lands
   **Then** `build` runs as part of the gate on every change
   **And** no cron invokes it

4. **Given** gunicorn has no win-64 build
   **When** the workflows are reorganized
   **Then** the reference application keeps its three-OS matrix
   **And** any six-combination job is declared Linux-only

5. **Given** a developer runs `pixi run ci` locally
   **When** CI runs the same task
   **Then** both execute an identical sequence
   **And** no step exists only in CI or only locally

## Tasks / Subtasks

- [x] Task 1 — Rebuild the `ci` task in `pixi.toml` to the AD-18 sequence (AC: #1, #5)
  - [x] Replace `pixi.toml:206` `ci = { depends-on = ["test-cov", "lint", "typecheck", "build"], ... }` with a chain whose order is pre-commit → build → check → lint → cov. `depends-on` does not guarantee ordering across independent tasks; express the order by chaining each task's own `depends-on` (e.g. `build` depends-on `precommit`, `typecheck` depends-on `build`, `lint` depends-on `typecheck`, `test-cov` depends-on `lint`, `ci` depends-on `test-cov`) **or** by declaring `ci` as an explicit ordered `cmd` sequence. Whichever is chosen, `pixi run ci` must execute all five and stop at the first failure.
  - [x] The existing task names are `precommit`, `build`, `typecheck`, `lint`, `test-cov` (`pixi.toml:190-206`). Do **not** rename them in this story; the AC names the *steps*, not the task identifiers.
  - [x] Keep every task's `default-environment = "dev"`; `ci` currently has none — give it `default-environment = "dev"` so `pixi run ci` never prompts.
  - [x] Update the `ci` task `description` to name the five steps in their executed order.

- [x] Task 2 — Collapse `.github/workflows/ci.yml` onto the single invocation (AC: #1, #4, #5)
  - [x] `.github/workflows/ci.yml` today has two jobs: `test` (three-OS matrix, runs `pixi run test`) and `lint` (ubuntu, runs `pixi run lint` then `pixi run typecheck`). Neither invokes `pixi run ci`.
  - [x] Declare a `gate` job on `ubuntu-latest` whose only project step is `run: pixi run ci`. Story 1.2 attaches the PostgreSQL `services:` block and `DATABASE_URL` to **this** job — leave the job shaped so that addition is a pure insertion.
  - [x] Retain a three-OS compatibility matrix job (`ubuntu-latest`, `windows-latest`, `macos-latest`) on the reference application per AC #4. Because GitHub Actions `services:` containers run only on Linux runners, that matrix job runs `pixi run test` (sqlite substitution), not `pixi run ci`. Record this split in a comment in `ci.yml` so the next reader does not read it as a narrowed gate.
  - [x] Keep `prefix-dev/setup-pixi@v0.9.5` with `pixi-version: v0.70.2`, `environments: dev`, `cache: true` — the existing pins carry a comment explaining the lock-file-format v7 requirement; preserve it.
  - [x] Add a comment in `ci.yml` stating that any future six-combination job is Linux-only because `gunicorn` has no win-64 build (`pixi.toml:82-91` scopes `gunicorn`/`uvicorn-worker` to `linux-64` and `osx-arm64` only).

- [x] Task 3 — Remove the gate steps that live outside the single invocation (AC: #2, #3, #5)
  - [x] `.github/workflows/sonarqube.yml:35-36` runs `pixi run test-cov` solely to produce `coverage.xml` for the scanner. Template coverage is configured in `pyproject.toml` (`[tool.coverage.run] plugins = ["django_coverage_plugin"]`, `[tool.coverage.django_coverage_plugin] template_extensions = "html"`) and enabled by `COVERAGE_CORE=ctrace` in `pixi.toml [activation.env]` — so it is already measured by `pixi run ci`. Make the SonarCloud workflow consume the gate's artifact rather than re-run coverage: remove the `pixi run test-cov` step and obtain `coverage.xml` from the gate job (upload/download artifact, or `workflow_run`). The SonarCloud workflow must no longer own a coverage run.
  - [x] `.github/workflows/release.yml:173-181` runs `pixi run lint`, `pixi run typecheck` and `pixi run test-cov` inline, and `:213-215` runs `pixi run build`, on the `cron: "0 0 7,21 * *"` schedule at `release.yml:5`. Replace those four steps with a single `pixi run ci` step, or remove them entirely and make the release job depend on the gate having passed. Either way, no cron may be the thing that first invokes `build`.
  - [x] Do **not** delete `release.yml`'s cron — it schedules the *release*, which is out of scope. Only the gate steps inside it move.

- [x] Task 4 — Record the gate contract where a reader will find it (AC: #1, #5)
  - [x] Add a "The gate" section to `docs/development.md` naming `pixi run ci` as the single entry point, listing the five steps in order, and stating that CI runs exactly this task and nothing else.

- [x] Task 5 — Tests (AC: #1, #2, #3, #4, #5)
  - [x] New `tests/unit/test_gate_contract.py`. Parse `pixi.toml` with `tomllib` and assert the `ci` task reaches all five steps and that the executed order is pre-commit → build → check → lint → cov.
  - [x] In the same file, parse every file under `.github/workflows/` with `yaml.safe_load` and assert: exactly one workflow contains a step whose `run` invokes `pixi run ci`; no workflow triggered by `schedule` contains a step invoking `pixi run build`; no workflow other than the gate invokes `pixi run test-cov`, `pixi run lint` or `pixi run typecheck`.
  - [x] Assert the reference-application matrix job still declares all three of `ubuntu-latest`, `windows-latest`, `macos-latest`.
  - [x] `PyYAML` is not declared in `pixi.toml` today. `check-yaml` comes from `pre-commit-hooks`, which is a different package. If `yaml` is not importable in the `dev` environment, add `pyyaml` to `[feature.dev.dependencies]` from conda-forge — never to `[pypi-dependencies]` (Story 1.7 asserts that block holds only the editable self-install).

## Dev Notes

### Architecture Constraints

- **AD-18 — One gate, one invocation, Linux for the matrix.** "A single workflow invokes `pixi run ci`, which has never run in CI. A `ci` task **already exists** at `pixi.toml:206` … so this AD reshapes an existing task rather than creating one. The coverage *run invocation* moves out of the SonarCloud workflow (`sonarqube.yml:36`); the template-coverage *configuration* is already correct in `pyproject.toml` … and does not move. `build` comes off its fortnightly cron, which lives inside `release.yml` … that workflow also runs `lint`, `typecheck` and `test-cov` inline at `:173-181`, so four gate steps leave it, not one. The six-combination harness is Linux-only, `gunicorn` having no win-64 build; the three-OS matrix stays on the reference application, where it claims something different. **GitHub Actions `services:` containers are Linux-only**, so FR-32's PostgreSQL gate cannot run on that three-OS matrix: the gate job is ubuntu-only and a separate three-OS job runs `pixi run test` for platform compatibility." **Prevents:** "the orphan detector being disabled by a change nobody understood as security-relevant; thirty-six gate runs that cannot exercise the process model."
- **AD-20 — bring-up mode.** "`test-cov` already carries `--cov-fail-under=90`, so the floor is hard the moment the gate consolidates." Consolidating the gate makes the 90% floor binding on this repository immediately. Do not weaken `--cov-fail-under=90` to make the gate pass; the bring-up advisory mode of AD-20 applies only to *materialized-combination* gates, which do not exist yet.
- **AD-19** pins verification reduction to PR/merge. This story does **not** implement the reduced/full split — that is Epic 8 Story 8.9. Keep the workflow shape simple enough that the split is an addition rather than a rewrite.
- **Consistency Conventions — Rationale:** "Reasoning lives beside the configuration it constrains, in the same file, as `pixi.toml` already does." Every comment this story removes from `ci.yml` or `pixi.toml` must be re-placed, not dropped.

### Source Tree — files to touch

| Path | NEW or UPDATE | What changes |
| --- | --- | --- |
| `pixi.toml` | UPDATE | Today `ci` at `:206` is `depends-on = ["test-cov", "lint", "typecheck", "build"]` with no ordering guarantee, no pre-commit step, and no `default-environment`. Rebuild it as the ordered five-step chain. Preserve every existing task definition and comment block (`:158-205`). |
| `.github/workflows/ci.yml` | UPDATE | Today: `test` job, three-OS matrix, runs `pixi run test`; `lint` job, ubuntu, runs `pixi run lint` + `pixi run typecheck`. Becomes: a `gate` job on ubuntu running only `pixi run ci`, plus a retained three-OS compatibility matrix running `pixi run test`. Preserve the `setup-pixi` pins and their comments (`:22-29`). |
| `.github/workflows/sonarqube.yml` | UPDATE | Today runs `pixi install -e dev` (`:31`), `pixi run test-cov` (`:36`), `pixi run ruff-report` (`:39`), then the scan. Remove the coverage run; consume the gate's `coverage.xml`. Preserve the scanner steps, `SONAR_TOKEN` handling and the `sonar-project.properties` pointer comment at `:33-34`. |
| `.github/workflows/release.yml` | UPDATE | Today runs `pixi run lint` + `pixi run typecheck` (`:173-177`), `pixi run test-cov` (`:179-181`) and `pixi run build` (`:213-215`) on the `cron: "0 0 7,21 * *"` schedule (`:4-5`). Remove the gate steps; keep the release mechanics, the tag/changelog logic and the cron itself. |
| `docs/development.md` | UPDATE | Add a "The gate" section. |
| `tests/unit/test_gate_contract.py` | NEW | Asserts the `ci` task's five ordered steps and the workflow-level properties above. |

**Not a scaffold step.** `epics.md:125` states there is no starter template: "the reference application already exists in this repository (originally `cookiecutter-django`, since restructured), so phase 1 is a brownfield rewire and extraction, not a project bootstrap." Everything this story touches already exists.

**Verified CI state today (2026-08-15).** `.github/workflows/` contains `ci.yml`, `labeler.yml`, `release.yml`, `sonarqube.yml`, `stale.yml`. No workflow invokes `pixi run ci`. No workflow declares a database service. `pixi run precommit` exists as a task but is invoked by no workflow.

### Testing Requirements

- Test file: `tests/unit/test_gate_contract.py`. Pure manifest/YAML parsing — no I/O beyond reading repository files, no network, no database. It belongs in `tests/unit/`, not `tests/integration/`; no `@pytest.mark.integration` marker.
- Resolve paths from `Path(__file__).resolve().parents[2]`, matching the existing pattern at `tests/unit/test_dependency_policy.py:11`.
- Assertions the ACs demand, each its own test function:
  - `pixi run ci` reaches `precommit`, `build`, `typecheck`, `lint`, `test-cov`.
  - The order of execution is pre-commit → build → check → lint → cov.
  - Exactly one workflow file contains a `run` step invoking `pixi run ci`.
  - No `schedule`-triggered workflow invokes `pixi run build`.
  - The three-OS matrix job still names all three runners.
- Coverage floor is 90% including templates (AD-20), enforced by `--cov-fail-under=90` in the `test-cov` task at `pixi.toml:196`. New test code counts toward it.
- Test disposition convention (spine §Consistency Conventions): accelerator and base tests live under `tests/` mirroring `src/` and carry the disposition of what they cover. This file covers the gate itself, which is `machinery`; it will be dispositioned in Epic 7.

#### Project Structure Notes

The Structural Seed places the gate under "Verification model (§4.6) | `tools/materializer/`, CI". `tools/materializer/` does not exist yet and is Epic 8's. This story touches only the CI half. `accelerator.toml`, `component.toml` and `Dockerfile` from the Structural Seed also do not exist yet and are out of scope here.

Task-name variance: the repository uses `format`/`typecheck`/`test-cov` where the global standard names `fmt`/`check`/`cov`. The AC names the steps, not the task identifiers, so no rename is required and none should be introduced in this story — a rename would break `.pre-commit-config.yaml`, `release.yml` and `sonarqube.yml` in the same change.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.1]
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 1] — "Every later epic lands against this gate, so it goes first."
- [Source: _bmad-output/planning-artifacts/epics.md:125] — no starter template; brownfield rewire.
- [Source: _bmad-output/planning-artifacts/epics.md:222] — "FR-32's PostgreSQL service and the single `pixi run ci` invocation begin in Epic 1 against the reference application; Epic 8 extends both to six combinations."
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-18]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-19]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`

### Debug Log References

- `pixi run ci` — exits 0. Executed order confirmed from the task banners:
  `precommit` → `build` → `typecheck` → `lint` → `test-cov`, every step resolving
  to the `dev` environment with no prompt.
- `pixi run test-cov` — 116 passed (107 before this story, +9 new), coverage
  92.31% against the 90% floor.
- Baseline verification before any edit: all five steps already passed
  individually, so consolidation could not be masking a pre-existing failure.

### Completion Notes List

**Two deviations from the task text, both forced by the tooling.**

1. **`ci` cannot carry `default-environment`.** Task 1 says to give it one. pixi
   0.70.2 rejects that key on a task that declares only `depends-on`:
   `Unexpected keys, expected only 'cmd', 'depends-on', 'description', 'args'`.
   What actually makes the gate non-interactive is that all five steps it
   depends on pin `dev`, so `test_every_gate_step_pins_its_environment` asserts
   that property instead of the unavailable mechanism.

2. **Ordering is expressed as an ordered `depends-on` list, not a chain.** Task 1
   offered chaining each task's own `depends-on` as one option; that was
   rejected because it would make `pixi run lint` drag `typecheck`, `build` and
   `precommit` behind it. Verified empirically in a scratch workspace that pixi
   runs a `depends-on` list sequentially in declaration order, halts at the
   first failure, and propagates a non-zero exit code — so the list order is the
   executed order and no chain is needed.

**A capability was removed, deliberately.** `release.yml` ran `pixi run build`
*after* creating the release tag, which confirmed hatch-vcs resolved that tag to
the intended version. AC #3 forbids a cron invoking `build`, so it is gone. The
gate builds every commit on `main`, but always before the tag exists, so it
proves the package builds and does **not** prove the tag resolves. Nothing
checks that now. A replacement would be a step asserting the resolved version
without invoking a gate step. Recorded in a comment at the removal site.

**SonarCloud needed a trigger change, not just a step removal.** Removing its
coverage run leaves it needing `coverage.xml` from the gate, and cross-workflow
artifacts are only reachable through `workflow_run` — a same-run
`download-artifact` would have failed on every run and, with `continue-on-error`,
reported zero coverage rather than failing. That is the silent-failure shape the
project standards forbid, so `sonarqube.yml` now triggers on `workflow_run`
after CI completes, guards on `conclusion == 'success'`, checks out
`workflow_run.head_sha`, and downloads with no `continue-on-error`.
**Unverified locally:** GitHub Actions cannot run here, so the first real run
should confirm the artifact resolves and that Sonar's pull-request decoration
still works under `workflow_run` — PR context is weaker under that trigger than
under `pull_request`.

**`pyyaml` declared, not newly installed.** It already reached the `dev`
environment transitively. The spine's supply-chain convention requires a
directly-imported package to be declared directly, and the new test imports it,
so it is now explicit in `[feature.dev.dependencies]` from conda-forge. Task 5
pre-authorized this.

**Project lint is stricter than the global standard.** `pyproject.toml` sets no
`line-length`, so ruff uses 88, and `E501` is not in its ignore list — the gate
caught twelve violations in the new test file on its first run, which is the
gate doing its job on the change that created it.

### File List

| Path | Change |
| --- | --- |
| `pixi.toml` | `ci` rebuilt as the ordered five-step gate; `pyyaml` declared in `[feature.dev.dependencies]` |
| `.github/workflows/ci.yml` | `test`/`lint` jobs replaced by a `gate` job invoking `pixi run ci` and a three-OS `compatibility` job; gate uploads `coverage.xml` |
| `.github/workflows/sonarqube.yml` | Coverage run removed; triggers on `workflow_run` after CI and consumes the gate's artifact |
| `.github/workflows/release.yml` | Four gate steps removed (`lint`, `typecheck`, `test-cov`, `build`); cron and release mechanics kept |
| `docs/development.md` | New "The gate" section; task table entry updated |
| `tests/unit/test_gate_contract.py` | NEW — 9 tests asserting the gate contract against `pixi.toml` and the workflows |

## Change Log

| Date | Change |
| --- | --- |
| 2026-08-16 | Consolidated the quality gate onto a single `pixi run ci` invocation (Story 1.1). Gate steps removed from `release.yml` and `sonarqube.yml`; SonarCloud moved to `workflow_run`. |
