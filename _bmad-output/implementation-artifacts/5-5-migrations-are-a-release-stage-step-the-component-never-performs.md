# Story 5.5: Migrations are a release-stage step the component never performs

Status: ready-for-dev

## Story

As a platform engineer,
I want no entrypoint to migrate and the component to refuse an unrecognized schema,
so that migration cannot race across replicas and a serving process never runs against a schema it does not know.

## Acceptance Criteria

**Traceability:** FR-41 · AD-22 · SC-3 · risk R-3

1. **Given** every entrypoint, task and container command
   **When** they are inspected
   **Then** none runs migrations
   **And** a test asserts this over the materialized process tasks

2. **Given** unapplied migrations
   **When** a serving process starts
   **Then** the stage-2 refusal from Story 4.3 raises `ImproperlyConfigured`

3. **Given** the deployment pipeline
   **When** the contract is documented
   **Then** the documentation states that migration runs before new pods begin serving
   **And** that it runs once per database as `component.toml` declares

4. **Given** a serving process started outside `pixi run web`
   **When** the migrations refusal is considered
   **Then** it does not fire
   **And** this is the accepted price of a fail-open process type

## Tasks / Subtasks

- [ ] Task 1 — Assert no entrypoint or task migrates (AC: #1)
  - [ ] `tests/unit/test_release_stage.py` — parse `pixi.toml` with `tomllib`, merging `[tasks]` and every `[feature.<name>.tasks]` table.
  - [ ] Derive the process group structurally, exactly as Story 5.2 does: the tasks whose `env` contains `COMPONENT_PROCESS`. Import that helper from `tests/unit/test_process_model.py` or factor it into a shared test helper — do not write a second, divergent parser.
  - [ ] For every process task assert: the command contains no `migrate`, `migrate --check`, `makemigrations` or `manage.py migrate` invocation, and its `depends-on` list (transitively resolved) reaches no task that does. The transitive check matters — `depends-on = ["migrate"]` is the shape this test exists to catch.
  - [ ] Assert the same over `src/config/asgi.py` and `src/config/wsgi.py`: neither imports `django.core.management` nor calls `call_command`.
  - [ ] Assert the same over the `Dockerfile` once Story 5.6 lands it: no `RUN`, `ENTRYPOINT` or `CMD` line contains a migrate invocation. Write the assertion to be skipped with an explicit reason when the file is absent, and record in Story 5.6's task list that the file must satisfy it. Do not weaken the assertion to a substring search over the whole file — check the instruction lines.
  - [ ] Assert `migrate` (`pixi.toml:174`) and `collectstatic` (`:175`) themselves set **no** `COMPONENT_PROCESS`: they are release-stage and build-stage steps, not serving processes, and a `COMPONENT_PROCESS` on them would make the migrations refusal fire against the very command that clears it — the deadlock AD-13 names.

- [ ] Task 2 — Wire the release-stage steps to `component.toml` (AC: #1, #3)
  - [ ] Confirm every `[[databases]]` entry in `component.toml` carries a non-empty `migrate` step list (Story 5.1) and that the `default` entry's step targets the `default` alias explicitly (`migrate --database default --noinput`).
  - [ ] Add a test asserting each declared step is a Django management invocation and names a `--database` alias that exists in the same declaration — so a contributed database (AD-9, Epic 9) cannot be added without its step.
  - [ ] Do not add a task that runs all the steps in sequence. The deployment repository runs them; a component-side "migrate-all" task is one `depends-on` away from becoming an entrypoint.

- [ ] Task 3 — Assert the stage-2 refusal fires for a serving process (AC: #2)
  - [ ] The refusal itself is Epic 4's Story 4.3 (condition 7 of the nine-condition table: "Unapplied migrations exist on a serving process", stage 2). Epic 4 precedes Epic 5 in the dependency flow, so this is a **dependency, not a forward reference**: reuse it, do not reimplement it, and do not add a second migration check anywhere.
  - [ ] `tests/integration/test_release_stage.py` (`@pytest.mark.integration`): with `COMPONENT_PROCESS` set and `COMPONENT_RUNTIME` unset, and with an unapplied migration present, the stage-2 hook raises `ImproperlyConfigured`. If Story 4.3's module exposes a callable, invoke it directly; if it runs from `AppConfig.ready()`, trigger it the way Epic 4's own tests do.
  - [ ] Assert the converse in the same module: with `COMPONENT_PROCESS` **absent**, the same unapplied-migration state raises nothing (AC #4). This is R-3 as a test rather than a paragraph.
  - [ ] Do **not** move, duplicate, or relax the refusal. AD-26: the refusal contract is one module, `src/config/startup/`, with one owner.

- [ ] Task 4 — Document the release-stage contract (AC: #3, #4)
  - [ ] `docs/deployment.md` `## Migrations are a release-stage step`: migration runs **before** new pods begin serving; it runs once per database, exactly as `component.toml`'s `[[databases]] migrate` lists declare; no entrypoint, task or container command migrates, and none will be added.
  - [ ] State the ordering the deployment repository must implement: apply migrations → start new replicas → old replicas drain. Cross-reference AD-22's readiness rule — readiness never re-checks migrations, so an older replica running against a newer schema stays ready, which is what makes backwards-compatible migrations viable.
  - [ ] State risk **R-3** honestly under its own subheading: a serving process started outside `pixi run web` does not fire the migrations refusal, because process type fails open; failing it closed would deadlock the release stage. This is the accepted price, recorded, not mitigated.
  - [ ] Ensure `docs/deployment.md` is in `mkdocs.yml` `nav`; `pixi run docs` is `mkdocs build --strict`.

- [ ] Task 5 — Tests and gate (AC: #1, #2, #4)
  - [ ] `tests/unit/test_release_stage.py` as above — static assertions over `pixi.toml`, `component.toml`, `src/config/asgi.py`, `src/config/wsgi.py`, and the `Dockerfile` when present.
  - [ ] `tests/integration/test_release_stage.py` as above — the refusal fires for a serving process and does not fire without one.
  - [ ] Run `pixi run test`, then `pixi run ci`; the story is done when `pixi run ci` exits 0.

## Dev Notes

### Architecture Constraints

- **AD-22** — *Rule:* "**No entrypoint, task or container command runs migrations**; migration is a release-stage step the deployment repository performs before new pods serve, one per database as `component.toml` declares, and the stage-2 refusal enforces that a serving process never starts against an unrecognized schema." *Prevents:* "an entrypoint that migrates and races across replicas."
- **AD-13** — "Process type fails open: absent means not a serving process, because failing it closed would produce exactly that deadlock" — the release stage runs `pixi run migrate`, which is not a serving process and must not be treated as one. **Do not sniff `sys.argv`** to detect a serving process.
- **AD-9** — "Release-stage migration becomes one step per database, and `component.toml` declares them so the deployment repository does not have to guess. The stage-2 unapplied-migrations refusal and the sqlite refusal both iterate every configured database — which is only possible because stage 1 runs *after* composition (AD-26)."
- **AD-26** — "The refusal contract is one module, `src/config/startup/`, containing both stages and the FR-17 allowlist. **Stage 2** is owned by the `AppConfig.ready()` of one named immovable-core app in `django_service`, declared in `accelerator.toml`; no adopted app may precede it in `INSTALLED_APPS`, and a gate test asserts that ordering." This story asserts the refusal's behaviour; it does not own, move or extend it.
- **AD-28** — Per-database release-stage migration steps are `component.toml` content. A step list belongs there and nowhere else.
- **R-3** — "A serving process started outside `pixi run web` does not fire the migrations refusal. The price of AD-13's fail-open process type, taken because failing it closed deadlocks the release stage." Accepted, not mitigated. Do not attempt a mitigation in this story.
- **The nine-condition refusal table** (epics.md#Resolved during story creation): condition 7 is "Unapplied migrations exist on a serving process", stage 2, one forbidden state, tested separately under FR-16. That test lives in Epic 4. This story's integration test asserts the *contract from the deployment side* and must not be counted as, or written to replace, FR-16's condition test.
- **Project standards** — Pixi is the only runner: `pixi run migrate` is how the release stage invokes it; never bare `python manage.py`. Python 3.14 only. Full type hints, Google docstrings, line length 120. Never `print()`; `structlog` only. Never a bare `except:`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tests/unit/test_release_stage.py` | **NEW** | No process task, entrypoint or Dockerfile instruction migrates; `migrate`/`collectstatic` declare no `COMPONENT_PROCESS`; every declared database has a migration step. |
| `tests/integration/test_release_stage.py` | **NEW** | The stage-2 refusal fires with `COMPONENT_PROCESS` set and does not fire without it. |
| `docs/deployment.md` | UPDATE (NEW if earlier Epic 5 stories have not landed) | Adds `## Migrations are a release-stage step` including the R-3 subsection. |
| `mkdocs.yml` | UPDATE | Register `deployment.md` in `nav`. |
| `component.toml` | read/verify | Created by Story 5.1; confirm the `[[databases]] migrate` lists. No new keys. |
| `pixi.toml` | read/verify | `migrate` at `:174` is `python manage.py migrate` in the `default` environment with no `env` table — correct as-is. `collectstatic` at `:175` likewise. **Do not** add `COMPONENT_PROCESS` to either. |
| `src/config/asgi.py`, `src/config/wsgi.py` | read/verify | Neither imports `django.core.management` today. The assertion pins that. |
| `Dockerfile` | read/verify (created by Story 5.6) | Assertion skipped with an explicit reason while absent. |
| `src/config/startup/` | read only | Epic 4's refusal module. **Do not modify.** |

**Verified absent today:** `component.toml`, `Dockerfile`, `src/config/startup/`. `src/config/settings/production.py:26-28` holds the only refusal that exists today (sqlite in production); it is Epic 4's to generalise, not this story's.

### Testing Requirements

- Unit: `tests/unit/test_release_stage.py` — `tomllib` and text parsing of files on disk; no database, no network, milliseconds. Share the process-group helper with `tests/unit/test_process_model.py` (Story 5.2) rather than duplicating it: two parsers that can disagree is precisely the failure mode AD-26 names for the refusal contract, and the same reasoning applies to its tests.
- Integration: `tests/integration/test_release_stage.py` — `@pytest.mark.integration`; `tests/integration/conftest.py:12-19` also auto-marks the directory. The test manipulates `COMPONENT_PROCESS` and migration state, both process-global — use `monkeypatch` and restore migration state in a fixture so the suite leaves the database as it found it.
- Disposition (spine Consistency Conventions): both modules cover `core` paths and are `core`; they run inside every combination's gate and are never pruned. Derive expectations from `component.toml` so they hold in a combination where the `celery` region removed `worker` and `beat`.
- AD-20 floor: 90% including templates, `COVERAGE_CORE=ctrace` in force. These are assertion suites over configuration rather than new production code, so they add little coverage denominator — but do not use that as a reason to skip the `docs` update, which `pixi run docs` gates separately.
- AC #1's "over the materialized process tasks": here the assertions run against the reference application's `pixi.toml`. Epic 8 runs the same suite inside each materialized combination. Write the test so it reads whatever `pixi.toml` is at the repository root, with no path assumption beyond that.

#### Project Structure Notes

- Nothing new is added to `src/`. This story is a contract and its enforcement, not a feature: the behaviour it names is the *absence* of a behaviour, and the artefact is the test that keeps it absent.
- **Dependencies:** Story 5.1 (`component.toml` and the `[[databases]] migrate` lists), Story 5.2 (the process tasks and the process-group helper), and Epic 4 Story 4.3 (the stage-2 refusal). Epic 4 precedes Epic 5 in epics.md's dependency flow, so all three are available.
- **Consumed by Story 5.6:** the Dockerfile assertion. 5.6's Dockerfile must satisfy it on the day it lands; the skip-when-absent branch is a sequencing accommodation, not a permanent exemption.
- **Cross-epic thread** (epics.md): "FR-41's unapplied-migrations refusal is *implemented* as a stage-2 condition in Epic 4; **Epic 5 owns the release-stage contract and the no-entrypoint-migrates property.**" Keep the split exactly there.
- SC-3 is an external exit criterion: nothing in this repository starts a component on the target platform, and the deployment configuration that runs these steps lives in a separate repository and is an explicit non-goal. This story delivers the component-side declaration and its enforcement; it does not close SC-3.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-22]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-9]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-28]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-3.
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.5]
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — condition 7.
- [Source: _bmad-output/planning-artifacts/epics.md#Cross-epic threads]
- [Source: _bmad-output/planning-artifacts/epics.md#External exit criteria] — SC-3.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-41]
- Repository state: `pixi.toml:172-182`; `src/config/asgi.py`; `src/config/wsgi.py`; `src/config/settings/production.py:26-28`; `tests/integration/conftest.py:12-19`.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
