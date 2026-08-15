# Story 3.1: Local pixi tasks declare themselves local

Status: ready-for-dev

## Story

As a developer working on a generated component,
I want locality declared by the task I run rather than by a file in the source tree,
so that a freshly cloned component runs with one command and the declaration is inert in deployment.

## Acceptance Criteria

**Traceability:** AD-13 · supports FR-12 · SC-5

1. **Given** each local pixi task
   **When** it is declared
   **Then** it sets `COMPONENT_RUNTIME=local` in its own `env`
   **And** the declaration is committed, so a freshly cloned component runs with one command

2. **Given** a container runs its server process directly and never invokes a local task
   **When** a component is deployed
   **Then** the local declaration is inert

3. **Given** `[activation.env]` reaches production because the golden base runs pixi
   **When** the configuration is inspected
   **Then** no `COMPONENT_*` variable appears in `[activation.env]`
   **And** a test asserts this over the `pixi.toml`

4. **Given** the locality declaration
   **When** it is absent or unrecognized
   **Then** the component treats itself as deployed
   **And** local development is the exception that must declare itself

## Tasks / Subtasks

- [ ] Task 1: Author the locality reader at `src/config/locality.py` (AC: #4)
  - [ ] Create `src/config/locality.py` (NEW) with module-level constants `RUNTIME_ENV_VAR = "COMPONENT_RUNTIME"`, `PROCESS_ENV_VAR = "COMPONENT_PROCESS"`, `LOCAL = "local"`, and `SERVING_PROCESSES: frozenset[str] = frozenset({"web", "worker", "beat"})`. These four names are the single declaration site for the `COMPONENT_*` contract; nothing else in the tree may re-spell them as string literals.
  - [ ] Implement `is_local() -> bool`: returns `True` only when `os.environ.get(RUNTIME_ENV_VAR, "").strip().lower() == LOCAL`. Any other value — absent, empty, `"Local "` after strip/lower is still local, but `"dev"`, `"1"`, `"true"` — is **not** local. **Fails closed.**
  - [ ] Implement `is_deployed() -> bool` as `not is_local()`. Deployed is the default and requires no declaration.
  - [ ] Implement `component_process() -> str | None`: returns the `COMPONENT_PROCESS` value when it is a member of `SERVING_PROCESSES`, else `None`. Implement `is_serving_process() -> bool` as `component_process() is not None`. **Fails open** — absent means not a serving process.
  - [ ] Read the environment inside the functions, never at import time, so a test's `monkeypatch.setenv` is observed without module reloading.
  - [ ] Full type hints, Google-style docstrings, no `print`, no stdlib `logging`.

- [ ] Task 2: Declare `COMPONENT_RUNTIME=local` in the `env` of every local pixi task (AC: #1, #2)
  - [ ] In `pixi.toml` `[tasks]`, add `env = { COMPONENT_RUNTIME = "local" }` to: `manage`, `migrate`, `collectstatic`, `createsuperuser`, `serve`.
  - [ ] In `pixi.toml` `[feature.dev.tasks]`, add the same `env` to: `runserver`, `serve-reload`, `makemigrations`, `test`, `test-integration`, `test-cov`.
  - [ ] Do **not** add it to `ci`. `ci` is a `depends-on` aggregator; pixi does not propagate a task's `env` to the tasks it depends on, so the declaration must sit on each leaf task that loads Django.
  - [ ] Leave the pure-tooling tasks (`bootstrap`, `format`, `lint`, `typecheck`, `ruff-report`, `build`, `docs`, `docs-serve`, `changelog`, `precommit`) without the variable — they never import `config.settings`.
  - [ ] Add a short rationale comment above the `[tasks]` block, in the file's existing commenting style, stating that locality is declared per task because activation env travels into production.

- [ ] Task 3: Keep every `COMPONENT_*` variable out of activation env (AC: #3)
  - [ ] Confirm `[activation.env]` in `pixi.toml` still contains only `COVERAGE_CORE = "ctrace"` and `[feature.dev.activation.env]` only `DJANGO_DEBUG_APPS = "True"`. Both hold today; this story's job is to make that state enforced rather than incidental.
  - [ ] Add a comment inside `[activation.env]` recording the prohibition and its consequence.

- [ ] Task 4: Author the gate test over the materialized manifest (AC: #1, #3)
  - [ ] Create `tests/unit/test_locality_declaration.py` (NEW), following the `tomllib` manifest-parsing pattern already established in `tests/unit/test_dependency_policy.py:11-23` (module-scoped `manifest` fixture, `Path(__file__).resolve().parents[2] / "pixi.toml"`).
  - [ ] Declare the expected local-task set as data in the test module (`LOCAL_TASKS: frozenset[str]`), matching Task 2's list.
  - [ ] `test_no_component_variable_in_activation_env`: assert no key starting with `COMPONENT_` appears in `[activation.env]` or in any `[feature.<name>.activation.env]` table.
  - [ ] `test_every_local_task_declares_local_runtime`: for each name in `LOCAL_TASKS`, assert the task exists in `[tasks]` or `[feature.dev.tasks]` and that its `env["COMPONENT_RUNTIME"] == "local"`.
  - [ ] `test_no_task_declares_an_unrecognized_runtime`: iterate every task in every task table; where a task sets `COMPONENT_RUNTIME` at all, assert the value is exactly `"local"`. This is the two-way half — it catches a task that declares a typo'd locality and silently becomes deployed.
  - [ ] `test_serving_process_tasks_declare_no_runtime`: for any task named `web`, `worker` or `beat` that exists, assert it sets no `COMPONENT_RUNTIME`. These tasks arrive in Epic 5; write the assertion so it passes vacuously until then.

- [ ] Task 5: Unit-test the locality reader (AC: #4)
  - [ ] Create `tests/unit/test_locality.py` (NEW). Use `monkeypatch.setenv` / `monkeypatch.delenv(..., raising=False)`; no reload machinery is needed because Task 1 reads at call time.
  - [ ] Assert: `COMPONENT_RUNTIME` absent → `is_local()` is `False` and `is_deployed()` is `True`; `COMPONENT_RUNTIME=""` → deployed; `COMPONENT_RUNTIME="production"` → deployed; `COMPONENT_RUNTIME="dev"` → deployed; `COMPONENT_RUNTIME="local"` → local; `COMPONENT_RUNTIME="LOCAL"` → local.
  - [ ] Assert: `COMPONENT_PROCESS` absent → `component_process()` is `None` and `is_serving_process()` is `False`; `COMPONENT_PROCESS="web"` → `"web"` and `True`; `COMPONENT_PROCESS="shell"` → `None` and `False`.

- [ ] Task 6: Document the declaration (AC: #1, #2, #4)
  - [ ] In `docs/development.md`, under the existing `## Environment` section, add a short subsection stating: locality is declared by the pixi task, `COMPONENT_RUNTIME=local` lives in each local task's own `env`, a deployed container runs its server process directly and therefore never sets it, and absent or unrecognized means deployed.

## Dev Notes

### Architecture Constraints

**AD-13 — Locality and process type are declared per pixi task.** Binding rule, in the AD's own words:

> `COMPONENT_RUNTIME=local` is set in the `env` of each local pixi task. `web`, `worker` and `beat` set no runtime and inherit *deployed*; each sets `COMPONENT_PROCESS`. **No `COMPONENT_*` variable may appear in `[activation.env]`**, and a gate test asserts it over the materialized `pixi.toml` — the golden base runs pixi, so activation env reaches production, and `COMPONENT_PROCESS` placed there would make every management command declare itself a serving process and deadlock the release stage on the migrations refusal.
> Locality fails closed: absent or unrecognized means deployed. Process type fails open: absent means not a serving process, because failing it closed would produce exactly that deadlock.

*Prevents:* "the declaration travelling into the deployed image and inverting the fail-closed property; the entire test suite refusing to start on the day the refusal contract lands; `sys.argv` sniffing."

Consequences the dev agent must not trade away:

- **Never** put `COMPONENT_RUNTIME` or `COMPONENT_PROCESS` in `[activation.env]`, `[feature.dev.activation.env]`, `.env`, `pyproject.toml`, a settings module, or a committed dotfile. Activation env is evaluated by the golden base in production; a `COMPONENT_RUNTIME=local` that reaches production inverts the fail-closed property and disarms every refusal in Epic 4. A `COMPONENT_PROCESS` there makes `pixi run migrate` — a release-stage step — declare itself a serving process and refuse on the unapplied-migrations condition, deadlocking the release.
- **Never** infer locality from `sys.argv`, `DEBUG`, the settings module name, `DJANGO_ENV`, or a bare `ENV`. The spine's Consistency Conventions state it directly: `COMPONENT_`-prefixed variables carry component-level runtime facts, and "Never `DJANGO_ENV` or a bare `ENV` — the platform is likely to set a generic `ENV=dev` for a development *deployment*, and a deployed dev environment is still deployed."
- The asymmetry is deliberate and must be preserved exactly: **locality fails closed** (absent or unrecognized ⇒ deployed, so local development is the exception that declares itself) while **process type fails open** (absent ⇒ not a serving process). Do not "tidy" them into the same default.
- Accepted consequence, recorded so it is not treated as a bug: **R-5's sibling R-3** — "A serving process started outside `pixi run web` does not fire the migrations refusal. The price of AD-13's fail-open process type, taken because failing it closed deadlocks the release stage."

**AD-1 / single declaration site.** `src/config/locality.py` is the only place the `COMPONENT_RUNTIME` and `COMPONENT_PROCESS` names and their accepted values are spelled. Epic 4's `src/config/startup/` imports this module rather than re-reading `os.environ`; Epic 5's `web`/`worker`/`beat` tasks are the producers of `COMPONENT_PROCESS`. Do not create a second reader.

**Pixi capability.** Per-task `env` is confirmed available at the pinned floor: the spine's Stack table records `pixi ≥ 0.70.2` with "Per-task `env` confirmed available", and `pixi.toml` sets `requires-pixi = ">=0.70.2"`.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/locality.py` | NEW | The single locality/process-type reader: `RUNTIME_ENV_VAR`, `PROCESS_ENV_VAR`, `LOCAL`, `SERVING_PROCESSES`, `is_local()`, `is_deployed()`, `component_process()`, `is_serving_process()`. |
| `pixi.toml` | UPDATE | Add `env = { COMPONENT_RUNTIME = "local" }` to the eleven Django-invoking tasks named in Task 2; add rationale comments. |
| `tests/unit/test_locality_declaration.py` | NEW | Manifest assertions over `pixi.toml` (AC #1, #3). |
| `tests/unit/test_locality.py` | NEW | Behavioural assertions over the reader (AC #4). |
| `docs/development.md` | UPDATE | New subsection under `## Environment` describing the declaration. |

**`pixi.toml` today.** `[workspace]` pins `requires-pixi = ">=0.70.2"`. `[environments]` declares only `default` and `dev`, both `solve-group = "default"` — the twelve-combination matrix (AD-3) does not exist yet and is Epic 8's. `[activation.env]` contains exactly one key, `COVERAGE_CORE = "ctrace"`, with a comment explaining the `sysmon`/`ctrace` template-tracing reason; `[feature.dev.activation.env]` contains exactly one key, `DJANGO_DEBUG_APPS = "True"`. **No task currently declares an `env` table, and no `COMPONENT_*` variable exists anywhere in the repository** (verified by grep over `src/`, `tests/`, `pixi.toml`, `pyproject.toml`, `docs/`). Preserve: every task's existing `default-environment` and `description` — `pixi task list` is the process-model surface AD-14 depends on, and `description` is what it prints. Preserve the comment blocks; the spine's Consistency Conventions require rationale to live beside the configuration it constrains.

**`docs/development.md` today.** Sections are `## Environment` (with `### Debug apps`), `## Running with no external services`, `## Database`, `## Tasks`, `## Logging and tracing`, `## Tests`, `## Serving the application`, `## Coverage`, `## Pre-commit`. The `## Tasks` table enumerates the current tasks — it does not show `env`, and does not need to.

### Testing Requirements

- Both new test files are **unit** tests under `tests/unit/`: no database, no network, no filesystem beyond reading the committed `pixi.toml`. Do not mark them `@pytest.mark.integration`.
- `tests/unit/test_locality_declaration.py` parses `pixi.toml` with `tomllib` and asserts over the parsed structure — never with a regex or a substring search over the raw text. A `COMPONENT_RUNTIME` mentioned in a comment must not satisfy or break the assertion.
- The gate test must be two-way (Task 4): every declared local task carries the variable, **and** no task carries a value other than `"local"`. A one-way test passes on the day someone writes `COMPONENT_RUNTIME = "Local"` into a task and silently makes that task deployed.
- Coverage floor is the AD-20 global constant: **ninety percent including templates**, `COVERAGE_CORE=ctrace` in force, enforced by `pixi run test-cov` (`--cov-fail-under=90`). `pixi run ci` must exit 0.
- Test disposition (spine Consistency Conventions): these tests cover `core` surface, so they live under `tests/` mirroring `src/` and carry the `core` disposition when Epic 7 declares dispositions.
- Run with `pixi run test`; never bare `pytest`.

#### Project Structure Notes

The Structural Seed lists `src/config/{settings,observability,authorization,startup}/` as the composition root's contents. `src/config/locality.py` is a **module, not a package**, and is a deliberate addition: the spine's Consistency Conventions reserve `src/config/<concern>/` for "cross-cutting concerns with several independent consumers and no natural owner", and locality is a two-function environment read with no internal structure to justify a package. Its consumers are Epic 3 (this epic's URL gating and seeding refusal), Epic 4 (`src/config/startup/`) and Epic 5 (the process tasks). Recorded here as a variance from the seed's literal contents, not from its rule.

**Known duplication, deliberate.** Epic 5 Story 5.2 also asserts the `[activation.env]` prohibition, in `tests/unit/test_process_model.py`, alongside its two-way process-model test. That is the same AD-13 clause asserted twice in two files. Leave this story's assertion where it is: it must exist before Epic 5 lands, and the two tests are cheap. If a later story consolidates them, `tests/unit/test_locality_declaration.py` is the home — it owns the locality half of AD-13, and `test_process_model.py` owns the process half.

Existing repository state relevant to placement: `src/config/` today contains `settings/`, `observability/`, `api_router.py`, `asgi.py`, `celery_app.py`, `urls.py`, `websocket.py`, `wsgi.py`. `src/config/authorization/` and `src/config/startup/` do not exist yet (Epics 2 and 4).

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-14] — `web`/`worker`/`beat` as pixi tasks; the producers of `COMPONENT_PROCESS`, delivered in Epic 5.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — `COMPONENT_`-prefixed environment variables; never `DJANGO_ENV` or bare `ENV`; rationale beside configuration; test location.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20] — the ninety-percent floor, templates included, `COVERAGE_CORE=ctrace`.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-3, the accepted price of the fail-open process type.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Stack] — pixi ≥ 0.70.2, per-task `env` confirmed.
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.1]
- [Source: _bmad-output/planning-artifacts/epics.md#Known file overlap, assessed] — `pixi.toml` is touched by Epics 1, 3, 5, 7 and 8 in distinct blocks; this story owns only the locality `env`.
- [Source: pixi.toml] — `[activation.env]`, `[feature.dev.activation.env]`, `[tasks]`, `[feature.dev.tasks]`, `requires-pixi`.
- [Source: tests/unit/test_dependency_policy.py:1-23] — the `tomllib` manifest-fixture pattern to follow.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
