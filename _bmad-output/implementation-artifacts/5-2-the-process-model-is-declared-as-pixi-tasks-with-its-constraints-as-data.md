# Story 5.2: The process model is declared as pixi tasks with its constraints as data

Status: ready-for-dev

## Story

As an operator,
I want to enumerate a component's process types and their constraints without reading its source,
so that any component can be run the same way regardless of which features it selected.

## Acceptance Criteria

**Traceability:** FR-40 · AD-13, AD-14 · SC-3

1. **Given** the process types
   **When** they are declared
   **Then** `web`, `worker` and `beat` are pixi tasks invoked as `pixi run <process>`
   **And** they are enumerable with `pixi task list`

2. **Given** each process task
   **When** it runs
   **Then** it sets `COMPONENT_PROCESS`
   **And** sets no runtime, inheriting *deployed*

3. **Given** process type is absent
   **When** locality and process type are evaluated
   **Then** locality fails closed and process type fails open
   **And** a process type failing closed would deadlock the release stage on the migrations refusal

4. **Given** `web`
   **When** any of the twelve combinations is inspected
   **Then** it is present in all twelve, served by gunicorn with the uvicorn worker class

5. **Given** `worker` and `beat`
   **When** a combination without background task processing is inspected
   **Then** they are absent
   **And** they are removed as feature-owned regions of `pixi.toml` rather than surviving into a component the deployment repository would then try to run

6. **Given** the declaration and the tasks
   **When** the gate test runs
   **Then** it checks both directions: every process type the declaration names has a matching task, and every task in the process group is named by the declaration

7. **Given** `beat`
   **When** its constraints are declared in `component.toml`
   **Then** they state exactly one replica, because its schedule lives in PostgreSQL
   **And** they state that it must be replaced by stopping the old process before starting the new one, because a default rolling update would produce the two-replica window the replica count forbids

## Tasks / Subtasks

- [ ] Task 1 — Add the `web` process task to `pixi.toml` (AC: #1, #2, #4)
  - [ ] In `[tasks]` (`pixi.toml:172`), beside the existing `serve` task at `:179`, add:
        `web = { cmd = "gunicorn config.asgi:application -k uvicorn_worker.UvicornWorker --bind 0.0.0.0:8000", default-environment = "default", env = { COMPONENT_PROCESS = "web" }, description = "Serving process: gunicorn + uvicorn worker (deployed)" }`
  - [ ] Set **no** `COMPONENT_RUNTIME` on `web` — absence means *deployed* (AD-13). Do not add it "for clarity"; setting it inverts the fail-closed property.
  - [ ] Do **not** encode a grace period in the command. AD-22 gives the grace-period value to the deployment repository; gunicorn's own `GUNICORN_CMD_ARGS` environment variable is the injection point and needs no component-side flag. Record that in the rationale comment beside the task.
  - [ ] Add a comment beside `web` recording that `gunicorn` and `uvicorn-worker` are declared only under `[target.linux-64.dependencies]` (`pixi.toml:85`) and `[target.osx-arm64.dependencies]` (`:89`) — gunicorn has no conda-forge win-64 build, which is also AD-18's reason the twelve-combination harness is Linux-only. `serve` (uvicorn directly) remains the cross-platform local task and is **not** a process type.

- [ ] Task 2 — Add `worker` and `beat` as feature-owned regions of `pixi.toml` (AC: #1, #2, #5)
  - [ ] Immediately after `web`, add the paired AD-24 markers in TOML comment syntax: `# feature:celery` … `# /feature:celery`.
  - [ ] Inside the region:
        `worker = { cmd = "celery -A config.celery_app worker -l INFO", default-environment = "default", env = { COMPONENT_PROCESS = "worker" }, description = "Serving process: Celery worker (deployed)" }`
        `beat = { cmd = "celery -A config.celery_app beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler", default-environment = "default", env = { COMPONENT_PROCESS = "beat" }, description = "Serving process: Celery beat, exactly one replica (deployed)" }`
  - [ ] `config.celery_app` is the existing app module at `src/config/celery_app.py`; `CELERY_BEAT_SCHEDULER` is already set to the database scheduler at `src/config/settings/base.py:329` — the explicit `--scheduler` flag is belt-and-braces and must agree with it.
  - [ ] Add no flag that alters shutdown semantics (no `--pool=solo`, no `-Ofair` change to signal handling): Story 5.4 depends on Celery's default warm shutdown.
  - [ ] Region markers are placed now and **declared** in `accelerator.toml` in Epic 7 (AD-24 reconciliation). Note that in the comment so the Epic 7 author finds it.

- [ ] Task 3 — Fill in the `[[processes]]` constraints in `component.toml` (AC: #7)
  - [ ] `web`: `task = "web"`, `replacement = "rolling"`, no replica count (the deployment repository scales it).
  - [ ] `worker`: `task = "worker"`, `replacement = "rolling"`, no replica count.
  - [ ] `beat`: `task = "beat"`, `replicas = 1`, `replacement = "stop-before-start"`.
  - [ ] Beside `beat`, record the two reasons verbatim in the file: exactly one replica because its schedule lives in PostgreSQL; stop-before-start because a default rolling update would produce the two-replica window the replica count forbids.
  - [ ] Keep the `worker`/`beat` entries inside the `# feature:celery` / `# /feature:celery` markers Story 5.1 placed.

- [ ] Task 4 — Define the process group structurally and write the two-way gate test (AC: #6)
  - [ ] Define the **process group** as exactly the set of `pixi.toml` tasks whose `env` table contains a `COMPONENT_PROCESS` key. This is derived from the parsed TOML, not from a name, a prefix or a comment — a string-matched group is the failure mode AD-26 names for predicates and the same reasoning applies here.
  - [ ] `tests/unit/test_process_model.py` — parse `pixi.toml` with `tomllib`, merging `[tasks]` and every `[feature.<name>.tasks]` table, and parse `component.toml` through `src/config/component/loader.py`.
  - [ ] Forward direction: every `[[processes]]` entry names a task that exists and whose `env["COMPONENT_PROCESS"]` equals the entry's `name`.
  - [ ] Reverse direction: every task in the process group is named by a `[[processes]]` entry. A task that declares `COMPONENT_PROCESS` and is not declared fails.
  - [ ] Assert no process task sets `COMPONENT_RUNTIME` (AC #2).
  - [ ] Assert `web` is in the process group in every parse — it is unconditional (AC #4) — and that its command invokes `gunicorn` with `-k uvicorn_worker.UvicornWorker`.
  - [ ] Assert no `[[admin_processes]]` task sets `COMPONENT_PROCESS`: an admin process that declared itself a serving process would fire the migrations refusal and deadlock the release stage — the same failure AD-13 attributes to `[activation.env]`.

- [ ] Task 5 — Assert the AD-13 activation-env prohibition (AC: #2, #3)
  - [ ] In the same test module, assert that neither `[activation.env]` (`pixi.toml:145`) nor any `[feature.<name>.activation.env]` table (`:152`) contains a key beginning `COMPONENT_`. Today `[activation.env]` holds only `COVERAGE_CORE` and `[feature.dev.activation.env]` only `DJANGO_DEBUG_APPS`; the test is what keeps it that way.
  - [ ] Record in the test docstring why: the golden base runs pixi, so activation env reaches production, and `COMPONENT_PROCESS` placed there would make every management command declare itself a serving process.
  - [ ] Epic 8 extends this same assertion over each **materialized** `pixi.toml`; here it runs against the reference application. Note that in the docstring.

- [ ] Task 6 — Document the process contract (AC: #1, #3)
  - [ ] In `docs/deployment.md` add `## Process model`: the deployment repository invokes `pixi run web` / `pixi run worker` / `pixi run beat`, enumerates them with `pixi task list`, and reads replica counts and replacement strategy from `component.toml`. State that there is **no Procfile** and none will be added.
  - [ ] State the fail direction pair explicitly: locality fails closed (absent or unrecognized `COMPONENT_RUNTIME` means deployed); process type fails open (absent `COMPONENT_PROCESS` means not a serving process), because failing it closed would deadlock the release stage on the migrations refusal (AC #3).
  - [ ] Ensure `docs/deployment.md` is in `mkdocs.yml` `nav` — `pixi run docs` is `mkdocs build --strict`.

## Dev Notes

### Architecture Constraints

- **AD-14** — *Rule:* "`web`, `worker` and `beat` are pixi tasks; the deployment repository invokes `pixi run <process>` and enumerates them with `pixi task list`. `worker` and `beat` are feature-owned regions of `pixi.toml` under AD-24 — pruning them is sub-file removal by declared marker, not something that happens for free. Replica counts and replacement strategy — `beat` is exactly one replica and must be stopped before its replacement starts — live in `component.toml`. The gate test is **two-way**: every process type the declaration names has a matching task, *and* every task in the materialized `pixi.toml` process group is named by the declaration." *Prevents:* "inventing a Procfile the deployment repository may not read; a `worker` task surviving into a component with no Celery and the deployment repository trying to run it."
- **AD-13** — *Rule:* "`COMPONENT_RUNTIME=local` is set in the `env` of each local pixi task. `web`, `worker` and `beat` set no runtime and inherit *deployed*; each sets `COMPONENT_PROCESS`. **No `COMPONENT_*` variable may appear in `[activation.env]`**, and a gate test asserts it over the materialized `pixi.toml` — the golden base runs pixi, so activation env reaches production, and `COMPONENT_PROCESS` placed there would make every management command declare itself a serving process and deadlock the release stage on the migrations refusal. Locality fails closed: absent or unrecognized means deployed. Process type fails open: absent means not a serving process." *Prevents:* "the declaration travelling into the deployed image and inverting the fail-closed property… `sys.argv` sniffing." **Do not sniff `sys.argv`.**
- **AD-24** — Regions are "delimited by paired line comments in the file's own comment syntax, `feature:<name>` / `/feature:<name>`, and every region is declared in `accelerator.toml` with its path and feature… **No other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`.**" `pixi.toml` is one of AD-24's three named region-bearing paths.
- **AD-28** — Process-model constraints are `component.toml` content, not `accelerator.toml` content.
- **AD-18** — "The twelve-combination harness is Linux-only, `gunicorn` having no win-64 build; the three-OS matrix stays on the reference application."
- **AD-15** — Materialized components ship no Dockerfile; `pixi run <process>` against the golden base is the invocation path, which is why the process model is pixi tasks rather than container commands.
- **AD-26** — Predicates resolve objects, never strings. Applied here: the process group is the set of tasks structurally declaring `COMPONENT_PROCESS`, not the set of tasks whose name happens to be `web`/`worker`/`beat`.
- **Consistency Conventions** — Environment variables are `COMPONENT_`-prefixed for component-level runtime facts and never `DJANGO_ENV` or a bare `ENV`. "Rationale lives beside the configuration it constrains, in the same file, as `pixi.toml` already does."
- **Project standards** — Pixi is the only runner. Python 3.14 only. Full type hints, Google docstrings, line length 120. `structlog` only, never `print()` or stdlib `logging`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `pixi.toml` | UPDATE | Today `[tasks]` (`:172-179`) holds `manage`, `migrate`, `collectstatic`, `createsuperuser`, `serve`; `[feature.dev.tasks]` (`:184`) holds the dev and harness tasks. **No `web`, `worker` or `beat` task exists.** Add `web` unconditionally and `worker`/`beat` inside `# feature:celery` markers, each with `env = { COMPONENT_PROCESS = ... }`. **Preserve:** every existing task, `default-environment` on each, the `[target.*.dependencies]` gunicorn/uvicorn-worker split at `:85-92`, and `[activation.env]` at `:145-150` (`COVERAGE_CORE = "ctrace"` — AD-20 depends on it). |
| `component.toml` | UPDATE (created by Story 5.1) | Fill the `[[processes]]` constraint values and their rationale comments. |
| `src/config/celery_app.py` | read only | Existing Celery app module the `worker`/`beat` commands target. Do not modify. |
| `docs/deployment.md` | UPDATE (or NEW if 5.1/5.5 have not landed) | Adds `## Process model`. |
| `mkdocs.yml` | UPDATE | `nav` must list `deployment.md`; `mkdocs build --strict` fails otherwise. |
| `tests/unit/test_process_model.py` | **NEW** | Two-way gate test, the `COMPONENT_RUNTIME`-absent assertion, and the `[activation.env]` prohibition. |

Line-range check: the epic and spine cite no line ranges for this story. `pixi.toml` anchors verified 2026-08-15 — `[dependencies]:14`, `[target.linux-64.dependencies]:85`, `[pypi-dependencies]:98`, `[environments]:141`, `[activation.env]:145`, `[feature.dev.activation.env]:152`, `[tasks]:172`, `serve:179`, `[feature.dev.tasks]:184`, `ci:206`.

### Testing Requirements

- `tests/unit/test_process_model.py` — unit, no database, no network. `tomllib` parse of two files on disk; milliseconds.
- No integration test is warranted: actually launching gunicorn belongs to Epic 8's smoke check (AD-30), which asserts boot and readiness 200 per combination.
- Disposition: the module covers `core` paths (`pixi.toml`, `component.toml`) and is `core` — never pruned. Write the assertions so they pass in a combination where the `celery` region has been removed: derive the expected process set from `component.toml` rather than hardcoding three names, then assert `web` is always among them.
- AD-20 floor: 90% including templates, `COVERAGE_CORE=ctrace` in force. Do not extend `[tool.coverage.run] omit` (`pyproject.toml:162-169`).
- `pixi run test` in the inner loop; done when `pixi run ci` exits 0.

#### Project Structure Notes

- The Structural Seed annotates `pixi.toml` as "feature matrix, environments+solve-group, process tasks (AD-3, AD-13, AD-14)". This story lands the process-task third of that.
- **Known and assessed overlap** (epics.md#Known file overlap): `pixi.toml` is touched by Epic 1 (supply chain), Epic 3 (locality `env`), Epic 5 (process tasks), Epic 7 (feature-owned regions) and Epic 8 (the `[environments]` matrix). These are distinct blocks; keep this story's edits inside the `[tasks]` table and do not reflow neighbouring blocks.
- **Variance:** the `[environments]` matrix does not exist yet — `pixi.toml:141-143` declares only `default` and `dev`, both `solve-group = "default"`. The twelve combinations are Epic 8's Story. AC #4's "any of the twelve combinations" and AC #5's "a combination without background task processing" are therefore asserted here **structurally** — `web` outside any region, `worker`/`beat` inside the `celery` region — and asserted **per combination** in Epic 8. Do not attempt to build the matrix here.
- **Variance:** `accelerator.toml` does not exist, so the AD-24 region declaration cannot be written yet. Markers are placed now, declared in Epic 7. This mirrors the pattern epics.md records for three other declarations authored early and moved into `accelerator.toml` in Epic 7.
- **Forward reference, not an acceptance condition:** AC #3's mention of the migrations refusal describes why process type fails open. The refusal itself is Epic 4's stage-2 condition, and Story 5.5 owns the release-stage contract. Nothing in this story implements a refusal.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-14]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-28]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-18]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-15]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Stack] — gunicorn 26.0 + uvicorn-worker 0.4; "gunicorn 26 ships a native `asgi` worker; dropping `uvicorn-worker` is a spike, not a decision" — keep `-k uvicorn_worker.UvicornWorker`.
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.2]
- [Source: _bmad-output/planning-artifacts/epics.md#Known file overlap, assessed]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-40]
- Repository state: `pixi.toml:85-92, 141-158, 172-182, 184-206`; `src/config/settings/base.py:329`; `src/config/celery_app.py`.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
