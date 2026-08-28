---
status: done
baseline_revision: ad3a4aa
review_loop_iteration: 0
warnings: []
---

# Story 5.2: The process model is declared as pixi tasks with its constraints as data

Status: done

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
   **When** any of the six combinations is inspected
   **Then** it is present in all six, served by gunicorn with the uvicorn worker class

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

- [x] Task 1 — Add the `web` process task to `pixi.toml` (AC: #1, #2, #4)
  - [x] In `[tasks]` (`pixi.toml:456`), after the existing `serve` task (`:463`) and before `seed-personas` (`:476`), add:
        `web = { cmd = "gunicorn config.asgi:application -k uvicorn_worker.UvicornWorker --bind 0.0.0.0:8000", default-environment = "default", env = { COMPONENT_PROCESS = "web" }, description = "Serving process: gunicorn + uvicorn worker (deployed)" }`
  - [x] `default-environment` is not optional: `tests/unit/test_gate_contract.py::test_every_task_with_a_command_pins_its_environment` fails any task with a `cmd` that omits it.
  - [x] Set **no** `COMPONENT_RUNTIME` on `web` — absence means *deployed* (AD-13). Do not add it "for clarity"; setting it inverts the fail-closed property, and `tests/unit/test_locality_declaration.py::test_no_task_declares_component_runtime` already fails the gate on any task that does.
  - [x] Do **not** encode a grace period or a port in the command. AD-22 gives the grace-period value to the deployment repository; gunicorn's own `GUNICORN_CMD_ARGS` environment variable is the injection point for that and for `--bind`, and needs no component-side flag. Record that in the rationale comment beside the task.
  - [x] Add a comment beside `web` recording that `gunicorn` and `uvicorn-worker` are declared only under `[target.linux-64.dependencies]` (`pixi.toml:147`) and `[target.osx-arm64.dependencies]` (`:151`) — gunicorn has no conda-forge win-64 build, which is also AD-18's reason the six-combination harness is Linux-only. `serve` (uvicorn directly) remains the cross-platform local task and is **not** a process type.

- [x] Task 2 — Add `worker` and `beat` as feature-owned regions of `pixi.toml` (AC: #1, #2, #5)
  - [x] Immediately after `web`, add the paired AD-24 markers in TOML comment syntax: `# feature:celery` … `# /feature:celery`, flush against the lines they delimit (Story 4.4 established that a marker separated by a blank line does not survive `ruff format` in Python files; the same flush-marker convention is used here for consistency across region-bearing paths).
  - [x] Inside the region:
        `worker = { cmd = "celery -A config.celery_app worker -l INFO", default-environment = "default", env = { COMPONENT_PROCESS = "worker" }, description = "Serving process: Celery worker (deployed)" }`
        `beat = { cmd = "celery -A config.celery_app beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler", default-environment = "default", env = { COMPONENT_PROCESS = "beat" }, description = "Serving process: Celery beat, exactly one replica (deployed)" }`
  - [x] `config.celery_app` is the existing app module at `src/config/celery_app.py` (`app = Celery("django_service")` at `:15`); `CELERY_BEAT_SCHEDULER` is already set to the database scheduler at `src/config/settings/base.py:436` — the explicit `--scheduler` flag is belt-and-braces and must agree with it.
  - [x] Add no flag that alters shutdown semantics (no `--pool=solo`, no `-Ofair` change to signal handling): Story 5.4 depends on Celery's default warm shutdown.
  - [x] Region markers are placed now and **declared** in `accelerator.toml` in Epic 7 (AD-24 reconciliation). Note that in the comment so the Epic 7 author finds it. `pixi.toml` carries no `# feature:` region today, so this is the first one in the manifest.

- [x] Task 3 — Verify the `[[processes]]` constraints in `component.toml` (AC: #7)
  - [x] **Already landed in Story 5.1** (`component.toml:144-168`): `web` → `task = "web"`, `replacement = "rolling"`, no replica count; `worker` → `task = "worker"`, `replacement = "rolling"`, no replica count; `beat` → `task = "beat"`, `replicas = 1`, `replacement = "stop-before-start"`, with both reasons recorded beside it, and the `worker`/`beat` pair inside the `# feature:celery` markers.
  - [x] Do not re-author them. Verify each value against AC #7 and leave the file's process-model header comment truthful: it currently says the entries "name tasks `pixi.toml` does not yet define" (`component.toml:138-140`), which stops being true in this story. Rewrite that sentence to state the rule and name this story as the one that closed it.

- [x] Task 4 — Define the process group structurally and write the two-way gate test (AC: #6)
  - [x] Define the **process group** as exactly the set of `pixi.toml` tasks whose `env` table contains a `COMPONENT_PROCESS` key. This is derived from the parsed TOML, not from a name, a prefix or a comment — a string-matched group is the failure mode AD-26 names for predicates and the same reasoning applies here.
  - [x] `tests/unit/test_process_model.py` — parse `pixi.toml` with `tomllib`, walking `[tasks]`, every `[feature.<name>.tasks]` table and the platform-scoped variants of both (there are four task tables today: `[tasks]:456`, `[feature.dev.tasks]:492`, `[feature.gate.tasks]:548`, `[feature.spike-storage.tasks]:566`), and parse `component.toml` through `src/config/component/loader.py`.
  - [x] Mirror the walking idiom in `tests/unit/test_locality_declaration.py` (`_task_tables`, `_tasks`, `_task_env` at `:181`, `:208`, `:230`) rather than inventing a second shape; key results by location string so a task name declared in two tables cannot shadow its twin.
  - [x] Forward direction: every `[[processes]]` entry names a task that exists and whose `env["COMPONENT_PROCESS"]` equals the entry's `name`.
  - [x] Reverse direction: every task in the process group is named by a `[[processes]]` entry. A task that declares `COMPONENT_PROCESS` and is not declared fails.
  - [x] Assert no process task sets `COMPONENT_RUNTIME` (AC #2).
  - [x] Assert `web` is in the process group in every parse — it is unconditional (AC #4) — and that its command invokes `gunicorn` with `-k uvicorn_worker.UvicornWorker`.
  - [x] Assert every declared process name is a member of `config.locality.SERVING_PROCESSES`, imported rather than re-spelled (AD-1 single declaration site). A **subset** rather than an equality: a non-Celery combination declares `web` alone while the locality module still recognizes three.
  - [x] Assert no `[[admin_processes]]` task sets `COMPONENT_PROCESS`: an admin process that declared itself a serving process would fire the migrations refusal and deadlock the release stage — the same failure AD-13 attributes to `[activation.env]`. Do **not** assert that an admin process's task exists: `component.toml` declares `prune` (`:181-184`) and no `prune` task exists until the session-pruning story lands.
  - [x] Assert the AD-24 marker region positionally, as `tests/unit/test_component_declaration.py` does for `component.toml`: the `# feature:celery` region inside `[tasks]` holds the `worker` and `beat` task lines, holds neither `web` nor any non-process task, and closes before the next table header.

- [x] Task 5 — Reconcile with the existing AD-13 assertions and close the cross-region gap (AC: #2, #3, #5)
  - [x] **Do not re-assert the activation-env prohibition.** `tests/unit/test_locality_declaration.py` already owns it: `test_component_process_absent_from_every_activation_env` (`:340`) is absolute across all four activation-table shapes including platform-scoped ones, and `test_default_environment_activation_env_declares_no_component_variable` (`:305`) covers `COMPONENT_*` for every activation table a non-developer environment resolves. This story's original instruction — the blanket "no `COMPONENT_*` in `[activation.env]`" — is **superseded**: AD-13 was amended 2026-08-17 (spine `d40b684`) so locality is declared once in `[feature.dev.activation.env]`, which legitimately holds `COMPONENT_RUNTIME = "local"`. Writing the blanket form here would fail the gate against the manifest it is asserting.
  - [x] Two assertions in that module are vacuous today and go live with this story: `test_only_serving_process_tasks_declare_a_process_type` (`:412`) and `test_serving_process_tasks_declare_no_runtime` (`:464`). Do not duplicate or rename them; the new module's docstring names them as the neighbouring half of the same contract.
  - [x] Record in the new module's docstring why `COMPONENT_PROCESS` in an activation env would be fatal: the golden base runs pixi, so activation env reaches production, and `COMPONENT_PROCESS` placed there would make every management command declare itself a serving process — `pixi run migrate` included, a release-stage step, which then refuses on the unapplied-migrations condition and deadlocks the release.
  - [x] Epic 8 extends both the activation-env and the two-way assertions over each **materialized** `pixi.toml`; here they run against the reference application. Note that in the docstring.
  - [x] **Close the cross-region consistency gap** the ledger leaves unowned (`deferred-work.md:271-274`): assert that `celery` in `component.toml`'s `selected_features`, the `worker`/`beat` `[[processes]]` entries, and the `# feature:celery` region of `pixi.toml` `[tasks]` are all present or all absent together. Declare the process-to-feature mapping (`{"worker", "beat"} ⟹ celery`) once, in this module, as a module-level constant with the reasoning beside it — this story owns the process names, which is the half that was missing when the entry was written. A half-stripped region then fails here rather than loading clean.

- [x] Task 6 — Document the process contract and correct the two stale claims about `serve` (AC: #1, #3)
  - [x] In `docs/deployment.md` add `## Process model` after `## The two declarations`: the deployment repository invokes `pixi run web` / `pixi run worker` / `pixi run beat`, enumerates them with `pixi task list`, and reads replica counts and replacement strategy from `component.toml`. State that there is **no Procfile** and none will be added.
  - [x] State the fail direction pair explicitly: locality fails closed (absent or unrecognized `COMPONENT_RUNTIME` means deployed); process type fails open (absent `COMPONENT_PROCESS` means not a serving process), because failing it closed would deadlock the release stage on the migrations refusal (AC #3).
  - [x] State that the deployment platform must set `DJANGO_SETTINGS_MODULE`, and what happens when it does not: `config/asgi.py` falls back to `config.settings.local`, and stage-1 condition 1 (`_refuse_the_local_settings_module`) refuses a deployed process that loaded it. The fallback therefore fails closed at settings import and no entrypoint change is made in this story.
  - [x] **Correct `serve`'s description** in `pixi.toml:463`. "production-like ASGI" is not true and has not been since the locality contract landed: bare `pixi run serve` resolves in `default`, reads *deployed*, imports `config.settings.local` through the `asgi.py` fallback and is refused by that same condition. The task is the cross-platform **local** ASGI server, invoked as `pixi run -e dev serve`, and its description and rationale comment must say so. This closes the open ledger entry at `deferred-work.md:48-50`, which assigns the choice to this story.
  - [x] **Correct `docs/development.md:54-55`**, which lists `serve` among the operational commands "a deployment runs". A deployment runs `web`; `serve` is a developer's. Remove `serve` from that list and point at the new `## Process model` section. Leave the `migrate`/`collectstatic` half of the same sentence to Story 5.5, which owns the release stage (`deferred-work.md:211-214` stays open for that half).
  - [x] `docs/deployment.md` is already in `mkdocs.yml` `nav` (Story 5.1) and `tests/unit/test_component_declaration.py` asserts it. Verify with `pixi run docs` (`mkdocs build --strict`), which is not itself in the gate (`deferred-work.md:281-284`).

## Dev Notes

### Architecture Constraints

- **AD-14** — *Rule:* "`web`, `worker` and `beat` are pixi tasks; the deployment repository invokes `pixi run <process>` and enumerates them with `pixi task list`. `worker` and `beat` are feature-owned regions of `pixi.toml` under AD-24 — pruning them is sub-file removal by declared marker, not something that happens for free. Replica counts and replacement strategy — `beat` is exactly one replica and must be stopped before its replacement starts — live in `component.toml`. The gate test is **two-way**: every process type the declaration names has a matching task, *and* every task in the materialized `pixi.toml` process group is named by the declaration." *Prevents:* "inventing a Procfile the deployment repository may not read; a `worker` task surviving into a component with no Celery and the deployment repository trying to run it."
- **AD-13 (as amended 2026-08-17, spine `d40b684`)** — Locality is declared **once**, in `[feature.dev.activation.env]`, and **no task declares `COMPONENT_RUNTIME`**; a task `env` overrides the caller's, so a task-level declaration could not be corrected by the deployment platform. `web`, `worker` and `beat` set no runtime and inherit *deployed*; each sets `COMPONENT_PROCESS` in its own task `env`. **No `COMPONENT_PROCESS` may appear in any activation env** — the golden base runs pixi, so activation env reaches production, and it would make every management command declare itself a serving process and deadlock the release stage on the migrations refusal. Locality fails closed: absent or unrecognized means deployed. Process type fails open: absent means not a serving process. *Prevents:* "the declaration travelling into the deployed image and inverting the fail-closed property… `sys.argv` sniffing." **Do not sniff `sys.argv`.**
- **AD-24** — Regions are "delimited by paired line comments in the file's own comment syntax, `feature:<name>` / `/feature:<name>`, and every region is declared in `accelerator.toml` with its path and feature… **No other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`.**" `pixi.toml` is one of the region-bearing paths AD-24 lists, and this story places its first region. **The set is open** and the carrier declares it as an open `[[regions]]` array — "the reconciler must not encode a count," and neither may any test written here.
- **AD-28** — Process-model constraints are `component.toml` content, not `accelerator.toml` content. AD-28 also makes `component.toml` itself region-bearing for exactly this story's reason: "the process-model constraints describe process types that exist in only two of six combinations… without markers inside it, AD-14's two-way gate test fails in the four non-Celery combinations by declaring processes with no matching task."
- **AD-18** — "The six-combination harness is Linux-only, `gunicorn` having no win-64 build; the three-OS matrix stays on the reference application."
- **AD-15** — Materialized components ship no Dockerfile; `pixi run <process>` against the golden base is the invocation path, which is why the process model is pixi tasks rather than container commands.
- **AD-26** — Predicates resolve objects, never strings. Applied here: the process group is the set of tasks structurally declaring `COMPONENT_PROCESS`, not the set of tasks whose name happens to be `web`/`worker`/`beat`.
- **AD-1** — One declaration site per fact. `src/config/locality.py` already declares `PROCESS_ENV_VAR = "COMPONENT_PROCESS"` (`:74`) and `SERVING_PROCESSES = frozenset({"web", "worker", "beat"})` (`:81`). The new test imports both rather than re-spelling the literals.
- **Consistency Conventions** — Environment variables are `COMPONENT_`-prefixed for component-level runtime facts and never `DJANGO_ENV` or a bare `ENV`. "Rationale lives beside the configuration it constrains, in the same file, as `pixi.toml` already does."
- **Project standards** — Pixi is the only runner. Python 3.14 only. Full type hints, Google docstrings, line length 120. `structlog` only, never `print()` or stdlib `logging`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `pixi.toml` | UPDATE | `[tasks]` (`:456-487`) holds `manage`, `migrate`, `collectstatic`, `createsuperuser`, `serve`, `seed-personas`, `mint-token`; `[feature.dev.tasks]` (`:492`), `[feature.gate.tasks]` (`:548`) and `[feature.spike-storage.tasks]` (`:566`) hold the rest. **No `web`, `worker` or `beat` task exists, and no `# feature:` region exists in the manifest at all.** Add `web` unconditionally and `worker`/`beat` inside `# feature:celery` markers, each with `env = { COMPONENT_PROCESS = ... }` and `default-environment = "default"`. Correct `serve`'s description. **Preserve:** every existing task, `default-environment` on each, the `[target.*.dependencies]` gunicorn/uvicorn-worker split at `:147-153`, `[activation.env]` at `:384-407` (`COVERAGE_CORE = "ctrace"` — AD-20 depends on it) and `[feature.dev.activation.env]` at `:435-440`. |
| `component.toml` | UPDATE (created by Story 5.1) | Values already correct (`:144-168`). Only the process-model header comment (`:130-142`) changes, where it states the tasks do not yet exist. |
| `src/config/celery_app.py` | read only | Existing Celery app module the `worker`/`beat` commands target. Do not modify. |
| `src/config/locality.py` | read only | `PROCESS_ENV_VAR` and `SERVING_PROCESSES` are imported by the new test. Do not modify. |
| `docs/deployment.md` | UPDATE | Adds `## Process model` (the file has `## The two declarations` and `## Reading the declaration` today). |
| `docs/development.md` | UPDATE | One sentence at `:54-55` stops listing `serve` as something a deployment runs. |
| `mkdocs.yml` | no change | `nav` already lists `deployment.md`. |
| `tests/unit/test_process_model.py` | **NEW** | The two-way gate test, the `COMPONENT_RUNTIME`-absent assertion, the marker-region assertion and the cross-region feature-consistency check. |

Line anchors re-verified against the working tree at `ad3a4aa` on 2026-08-28.

### Testing Requirements

- `tests/unit/test_process_model.py` — unit, no database, no network. `tomllib` parse of two files on disk plus one import from `config.locality`; milliseconds.
- No integration test is warranted: actually launching gunicorn belongs to Epic 8's smoke check (AD-30), which asserts boot and readiness 200 per combination.
- Disposition: the module covers `core` paths (`pixi.toml`, `component.toml`) and is `core` — never pruned. Write the assertions so they pass in a combination where the `celery` region has been removed: derive the expected process set from `component.toml` rather than hardcoding three names, then assert `web` is always among them.
- House idiom for manifest tests (`test_gate_contract.py`, `test_coverage_policy.py`, `test_locality_declaration.py`): `REPO_ROOT = Path(__file__).resolve().parents[2]`, a module-scoped `manifest` fixture doing `tomllib.load`, values under test hoisted to module-level constants with their reasoning beside them, declarative sentence test names, `assert not offenders, f"…"` with a message naming the offenders and the AD, and a non-vacuity guard (`test_the_scanners_see_the_manifest_they_claim_to`).
- AD-20 floor: 90% including templates, `COVERAGE_CORE=ctrace` in force. Do not extend `[tool.coverage.run] omit`.
- `pixi run test` in the inner loop; done when `pixi run ci` exits 0.

#### Project Structure Notes

- The Structural Seed annotates `pixi.toml` as "feature matrix, environments+solve-group, process tasks (AD-3, AD-13, AD-14)". This story lands the process-task third of that.
- **Known and assessed overlap** (epics.md#Known file overlap): `pixi.toml` is touched by Epic 1 (supply chain), Epic 3 (locality `env`), Epic 5 (process tasks), Epic 7 (feature-owned regions) and Epic 8 (the `[environments]` matrix). These are distinct blocks; keep this story's edits inside the `[tasks]` table and do not reflow neighbouring blocks.
- **Variance:** the six-combination `[environments]` matrix does not exist yet — `pixi.toml:379-382` declares `default`, `dev` and `spike-storage`. The six pre-locked environments are Epic 8's Story 8.1. AC #4's "any of the six combinations" and AC #5's "a combination without background task processing" are therefore asserted here **structurally** — `web` outside any region, `worker`/`beat` inside the `celery` region — and asserted **per combination** in Epic 8. Do not attempt to build the matrix here.
- **Variance:** `accelerator.toml` does not exist, so the AD-24 region declaration cannot be written yet. Markers are placed now, declared in Epic 7. This mirrors the pattern epics.md records for three other declarations authored early and moved into `accelerator.toml` in Epic 7. Note that the spine's AD-24 region table already under-records `component.toml`'s regions (`deferred-work.md:291-294`); this story adds `pixi.toml`'s first, so the same omission risk applies.
- **Forward reference, not an acceptance condition:** AC #3's mention of the migrations refusal describes why process type fails open. The refusal itself is Epic 4's stage-2 condition, and Story 5.5 owns the release-stage contract. Nothing in this story implements a refusal.

#### Spec Reconciliation (2026-08-28, against `ad3a4aa`)

The story was authored 2026-08-15. Six claims were re-verified and corrected before implementation:

1. **Every `pixi.toml` line anchor was stale** — the manifest has roughly tripled in length. `[tasks]` is `:456` not `:172`, `serve` is `:463` not `:179`, `[activation.env]` is `:384` not `:145`, `[feature.dev.activation.env]` is `:435` not `:152`, and the `[target.*.dependencies]` split is `:147`/`:151` not `:85`/`:89`. All corrected above.
2. **Task 5's activation-env instruction was superseded.** AD-13's per-task form was amended on 2026-08-17; the blanket "no `COMPONENT_*` in `[activation.env]`" contradicts the permitted `[feature.dev.activation.env] COMPONENT_RUNTIME = "local"` and would fail against the current manifest. `deferred-work.md:221-224` predicted this against this exact story. The `COMPONENT_PROCESS` half is unaffected, still absolute, and already asserted in `tests/unit/test_locality_declaration.py`. Task 5 is rewritten to reconcile rather than duplicate, and the ledger entry's 5.2 half is discharged.
3. **Task 3 is already done.** Story 5.1 authored the `[[processes]]` values, the `beat` rationale and the `# feature:celery` region in `component.toml`. The task is reduced to verification plus the one header sentence that stops being true here.
4. **The manifest gained three task tables and two tasks** since the story was written (`seed-personas`, `mint-token`, `[feature.gate.tasks]`, `[feature.spike-storage.tasks]`). The process-group walk must cover every task table, not just `[tasks]` and `[feature.dev.tasks]`.
5. **`deferred-work.md:48-50` assigns this story the `serve`-versus-`asgi.py` decision.** Resolved without changing an entrypoint: stage-1 condition 1 (`src/config/startup/stage_one.py:180`) already refuses a deployed process that loaded `config.settings.local`, so the `asgi.py` fallback fails closed at settings import. What is actually wrong is `serve`'s description, which claims production parity a task resolving in `default` cannot have. Task 6 corrects it and the neighbouring stale sentence in `docs/development.md`. Changing `asgi.py`'s default to `config.settings.production` was considered and rejected: `manage.py:10` carries the same local fallback, so the symmetry would be half a fix, and it would break `pixi run -e dev serve` for a property the refusal already guarantees.
6. **`deferred-work.md:271-274` has no owner and half of it is this story's.** The cross-region consistency between `selected_features`, `[[processes]]` and the `pixi.toml` region is added to Task 5, since the missing piece the entry names — authority over the process names — arrives here.

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
- Repository state at `ad3a4aa`: `pixi.toml:147-153, 379-382, 384-440, 456-487, 492, 548, 566`; `component.toml:130-184`; `src/config/locality.py:74, 81`; `src/config/celery_app.py:15`; `src/config/settings/base.py:436`; `src/config/startup/stage_one.py:180`; `tests/unit/test_locality_declaration.py:181-275, 305, 340, 388, 412, 464`.

## Dev Agent Record

### Agent Model Used

`claude-opus-5[1m]` (Opus 5, 1M context), running as the bmad-dev-auto implementation subagent.

### Debug Log References

`pixi run ci` — **pass, exit 0**, run twice (the second run confirms idempotence: pre-commit
auto-fixed nothing and the tree was unchanged after it).

- pre-commit over all files: pass, no file modified
- `build`, `typecheck` (mypy over 65 source files), `lint` (ruff over 177 files): pass
- `test-cov`: **1356 passed**, 101 warnings, 16.6s. **Total coverage 97.03%** (floor 90%,
  `COVERAGE_CORE=ctrace` in force, templates included). `pixi run test` (unit only): 1077 passed,
  10 of them new in `tests/unit/test_process_model.py`.
- `pixi run docs` (`mkdocs build --strict`): pass, no warning. Not part of the gate
  (`deferred-work.md` records that).
- `pixi task list`: enumerates `beat`, `web` and `worker` alongside the existing tasks, each with
  its description. No process was actually started.

Two deliberate mutation probes were run against a scratch copy of each manifest and reverted:

1. `COMPONENT_PROCESS = "beat"` → `"beeat"` in `pixi.toml`: both directions of the gate failed, as
   designed (`test_every_declared_process_names_a_task_that_declares_it` and
   `test_every_task_in_the_process_group_is_named_by_the_declaration`).
2. `"celery"` removed from `component.toml`'s `selected_features` and nothing else:
   `test_the_celery_feature_its_processes_and_its_task_region_are_present_or_absent_together`
   failed and named the five signals still present against the one now absent. The cross-region
   check is not vacuous.

### Completion Notes List

**Decisions the spec did not dictate**

- **`web`'s command is pinned by fragments, not by string equality.** `WEB_SERVER` and
  `WEB_WORKER_CLASS` are asserted as substrings; `--bind 0.0.0.0:8000` is deliberately *not*
  asserted. AD-22 gives the grace period to the deployment repository and `GUNICORN_CMD_ARGS` is
  the injection point for `--bind` and worker counts too, so pinning the bind value here would
  make a deployment-repository concern a gate failure. The reasoning is recorded beside the
  constants.
- **The cross-region check is one signal set, not a three-way boolean.** Task 5 asks that the
  feature, the processes and the region be "all present or all absent together". Implemented as
  five independent signals (the feature line, each of the two `[[processes]]` entries, each of the
  two tasks, plus the marker region) partitioned into present/absent, so a strip that took `worker`
  and left `beat` fails just as loudly as one that took the feature line alone. The
  `{"worker", "beat"} ⟹ celery` mapping is the module-level `CELERY_PROCESSES` constant with the
  reasoning beside it, as Task 5 requires.
- **The marker-region assertion reads task names with a regex** (`TASK_ASSIGNMENT`), because a
  region is a span of lines and `tomllib` preserves neither comments nor line order. Every
  assertion about a task's *content* still goes through the parsed TOML; the regex is confined to
  answering "which task names sit between these two marker lines".
- **The reverse direction also checks the routing, not just the name.** A task declaring
  `COMPONENT_PROCESS = "worker"` while `component.toml` routes `worker` to some other task passes a
  naive membership check; it is reported here. The spec asked only for membership.
- **`docs/deployment.md` gained a table of replica counts and replacement strategies** and two
  sub-headings (`### The two variables, and which way each one fails`,
  `### The deployment platform must set DJANGO_SETTINGS_MODULE`). The spec named the content of the
  section but not its shape.

**Where the literal instruction was adapted**

- **Task 1 says to place `web` "after `serve` and before `seed-personas`".** Done, but with the new
  `# ---- Serving processes (AD-14) ----` comment block between `serve` and `web`, so the process
  tasks read as a group rather than as three lines wedged into the Django operational commands.
  `seed-personas` and its comment block are untouched and still follow.
- **Task 6 says to correct `docs/development.md:54-55`.** Two further sentences in the same file
  carried the identical retired claim — the task table's `| pixi run serve | Production-like ASGI
  server |` and the `## Serving the application` paragraph's "closer to production". Both were
  corrected in the same pass; leaving them would have left the file contradicting the `pixi.toml`
  description this story rewrote. Flagged rather than silent: it is more than the one sentence the
  spec names, in the file the spec names. The neighbouring `migrate`/`collectstatic` half of the
  same sentence was left for Story 5.5, as instructed.
- **`docs/deployment.md`'s closing two paragraphs were rewritten**, not only extended. They stated
  that `component.toml` "today name[s] tasks `pixi.toml` does not yet define" and that Story 5.2
  "will" add them — false the moment this story landed, the same staleness Task 3 catches in
  `component.toml`'s own header. The Source Tree table says the page "adds `## Process model`";
  correcting the stale sentences in it is the same obligation applied to the same file.

**Touched outside the Source Tree table**

- **`_bmad-output/implementation-artifacts/deferred-work.md`** — three entries discharged in place,
  in the `update (date):` / `status: resolved (date)` shape the ledger already uses. The Spec
  Reconciliation section states that this story closes each of them but the file is not in the
  table:
  - the `serve`-versus-`asgi.py` entry (Reconciliation item 5) — marked resolved, recording that the
    description was corrected and the entrypoint default deliberately left alone;
  - the stale-AD-13-instructions entry (item 2) — its 5.2 half marked discharged; the entry stays
    `open` as the record for any other spec written against the pre-amendment AD-13;
  - the cross-region-consistency entry (item 6) — marked `status: resolved (2026-08-28)`.
  - The `pixi run docs`-not-in-the-gate entry is left open: Task 6 cites it as context, not as
    something to close, and adding `docs` to the `ci` chain is a gate-cost decision.

**Found and deliberately not fixed**

- **`docs/development.md:89`** still lists `serve` among "the operational commands in `[tasks]` …
  run them as `pixi run -e dev migrate` when you want them to behave locally". That sentence is
  *true* of `serve` and is now the correct advice for it, so it was left as written — but it is the
  same list Story 5.5 will revisit for `migrate`/`collectstatic`, and a reader could take the
  grouping as implying `serve` is operational. Worth a second look when 5.5 rewrites the paragraph.
- **No `prune` task exists** for the `[[admin_processes]]` entry `component.toml` declares. This is
  Task 4's explicit instruction (do not assert that an admin process's task exists) and is a
  forward reference to the session-pruning story, not a defect. The new module asserts only the
  prohibition — no admin task may declare `COMPONENT_PROCESS` — which is vacuous today for exactly
  that reason, and the docstring says so.
- **`pixi.toml`'s `celery` region is placed but not declared.** `accelerator.toml` does not exist,
  so AD-24's `[[regions]]` entry for it cannot be written. A comment beside the markers names Epic 7
  as the author and states the path/feature pair it needs, because an undeclared region is one the
  materializer never strips. This is the recorded variance, not an omission.
- **The orphan-import cost of stripping this region is nil**, unlike the Python regions Story 4.4
  added — a TOML region leaves no import behind. The open `F401` ledger entry from 4.4 is unaffected
  either way.


**Added by the orchestrating session after the implementation subagent returned**

- **The region's explanatory comment was moved inside the markers.** It sat above
  `# feature:celery`, so a non-Celery combination would have kept prose about `--scheduler`,
  `config.celery_app` and the Epic 7 declaration for tasks it does not have — the orphan-residue
  category AD-24 names, arriving through the very file that declares the regions. Everything the
  region needs explaining is now below the opening marker and is deleted with it. `pixi.toml`
  records why the comment sits there rather than above.
- **`test_the_celery_process_tasks_sit_inside_a_marker_pair` raised in a stripped combination.**
  Found by rehearsing the strip rather than by reading: removing both `# feature:celery` regions
  from `pixi.toml` and `component.toml` made `_celery_region_bounds` raise `ValueError` on the
  absent marker, so the module failed in the four combinations it is `core` in order to serve —
  directly against the spec's Testing Requirements ("write the assertions so they pass in a
  combination where the `celery` region has been removed"). `_celery_region_bounds` now returns
  `None` for an absent region and the case asserts the complement instead: no Celery process task
  survived the strip. Re-rehearsed after the fix — all 10 cases pass in the stripped tree, and the
  tree was restored from a byte-for-byte backup.
- **The same rehearsal surfaced six failures in `tests/unit/test_component_declaration.py`**, which
  is Story 5.1's and is pinned to the reference combination. Not fixed here: it is that story's
  file, and deciding which of the six become combination-aware needs Epic 8's materialized-fixture
  set. Recorded as a new `deferred-work.md` entry against this story, with the reproduction and the
  six case names.

### File List

| Path | NEW/UPDATE |
|---|---|
| `pixi.toml` | UPDATE |
| `component.toml` | UPDATE |
| `tests/unit/test_process_model.py` | **NEW** |
| `docs/deployment.md` | UPDATE |
| `docs/development.md` | UPDATE |
| `_bmad-output/implementation-artifacts/deferred-work.md` | UPDATE (outside the Source Tree table — see Completion Notes) |
