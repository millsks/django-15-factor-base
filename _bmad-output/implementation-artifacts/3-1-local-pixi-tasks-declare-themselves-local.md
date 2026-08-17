---
baseline_revision: abb084f
review_loop_iteration: 0
status: done
warnings: []
---

# Story 3.1: Local pixi tasks declare themselves local

Status: done

## Story

As a developer working on a generated component,
I want locality declared by the pixi environment I run in rather than by a file in the source tree,
so that a freshly cloned component runs with one command and the declaration is inert in deployment.

## Acceptance Criteria

**Traceability:** AD-13 · supports FR-12 · SC-5

1. **Given** the `dev` pixi environment
   **When** locality is declared
   **Then** `[feature.dev.activation.env]` sets `COMPONENT_RUNTIME = "local"`
   **And** no pixi task declares `COMPONENT_RUNTIME` in its own `env`
   **And** the declaration is committed, so a freshly cloned component runs with one command

2. **Given** a deployed component — a container running its server process directly, or the release stage invoking `pixi run migrate` in the `default` environment
   **When** locality is read
   **Then** `COMPONENT_RUNTIME` is absent and the component reads *deployed*
   **And** the deployment platform's own configuration (an OpenShift configmap or equivalent) remains in sole control of the variable, because nothing in `default` overrides it

3. **Given** the `default` environment's activation env reaches production because the golden base runs pixi
   **When** the configuration is inspected
   **Then** no `COMPONENT_*` variable appears in the `default` environment's resolved activation env, platform-scoped tables included
   **And** no `COMPONENT_PROCESS` appears in *any* activation env, feature-scoped included
   **And** no production-bound environment includes the `dev` feature
   **And** a test asserts all three over the `pixi.toml`

4. **Given** the locality declaration
   **When** it is absent or unrecognized
   **Then** the component treats itself as deployed
   **And** local development is the exception that must declare itself

## Tasks / Subtasks

- [x] Task 1: Author the locality reader at `src/config/locality.py` (AC: #4)
  - [x] Create `src/config/locality.py` (NEW) with module-level constants `RUNTIME_ENV_VAR = "COMPONENT_RUNTIME"`, `PROCESS_ENV_VAR = "COMPONENT_PROCESS"`, `LOCAL = "local"`, and `SERVING_PROCESSES: frozenset[str] = frozenset({"web", "worker", "beat"})`. These four names are the single declaration site for the `COMPONENT_*` contract; nothing else in the tree may re-spell them as string literals.
  - [x] Implement `is_local() -> bool`: returns `True` only when `os.environ.get(RUNTIME_ENV_VAR, "").strip().lower() == LOCAL`. Any other value — absent, empty, `"Local "` after strip/lower is still local, but `"dev"`, `"1"`, `"true"` — is **not** local. **Fails closed.**
  - [x] Implement `is_deployed() -> bool` as `not is_local()`. Deployed is the default and requires no declaration.
  - [x] Implement `component_process() -> str | None`: returns the `COMPONENT_PROCESS` value when it is a member of `SERVING_PROCESSES`, else `None`. Implement `is_serving_process() -> bool` as `component_process() is not None`. **Fails open** — absent means not a serving process.
  - [x] Read the environment inside the functions, never at import time, so a test's `monkeypatch.setenv` is observed without module reloading.
  - [x] Full type hints, Google-style docstrings, no `print`, no stdlib `logging`.

- [x] Task 2: Declare `COMPONENT_RUNTIME=local` once, in the `dev` environment (AC: #1, #2)
  - [x] In `pixi.toml`, add `COMPONENT_RUNTIME = "local"` to `[feature.dev.activation.env]`, beside the existing `DJANGO_DEBUG_APPS = "True"`.
  - [x] Add **no** `env` table to any task. Do not put `COMPONENT_RUNTIME` in `[tasks]`, `[feature.dev.tasks]`, or `[activation.env]`. There is exactly one declaration site.
  - [x] The developer paths inherit it because their tasks resolve to the `dev` environment: `runserver`, `serve-reload`, `makemigrations`, `test`, `test-integration`, `test-cov`, `typecheck`, `precommit`, `ruff-report`, `spike-storage`. Note that `typecheck`/`precommit` (mypy's django-stubs plugin, `pyproject.toml:305-308,323`) and `spike-storage` (pytest's `--ds=config.settings.test` in `addopts`) **do** load `config.settings` — the superseded task list wrongly called them pure tooling.
  - [x] The operational commands in `[tasks]` — `manage`, `migrate`, `collectstatic`, `createsuperuser`, `serve` — get **nothing**. A developer invokes them as `pixi run -e dev <task>`; the release stage invokes them bare and correctly reads *deployed*.
  - [x] Do **not** create `dev-`prefixed twins of those tasks, and do **not** define a same-named task in both `[tasks]` and `[feature.dev.tasks]` — pixi rejects that as `the task '<name>' is ambiguous` (verified on 0.70.2, and the same failure `docs/development.md` already records for `ci`).
  - [x] Add a rationale comment above `[feature.dev.activation.env]`, in the file's existing commenting style, recording *why* the declaration lives in the environment rather than on the tasks: a task's `env` overrides the caller's environment, so a task-level `COMPONENT_RUNTIME=local` on `migrate` could not be overridden by the deployment platform's configmap and would make the release stage read *local*.

- [x] Task 3: Keep `COMPONENT_*` out of the `default` environment's activation env (AC: #3)
  - [x] Confirm `[activation.env]` in `pixi.toml` still contains only `COVERAGE_CORE = "ctrace"`. It must remain free of every `COMPONENT_*` key — this is the table the golden base evaluates in production.
  - [x] `COMPONENT_PROCESS` is forbidden in **every** activation env, feature-scoped included: placed there it would make every management command declare itself a serving process and deadlock the release stage on the migrations refusal. Only `COMPONENT_RUNTIME`, and only in `[feature.dev.activation.env]`, is permitted.
  - [x] Add a comment inside `[activation.env]` recording the prohibition and its consequence.

- [x] Task 4: Author the gate test over the materialized manifest (AC: #1, #3)
  - [x] Create `tests/unit/test_locality_declaration.py` (NEW), following the `tomllib` manifest-parsing pattern already established in `tests/unit/test_dependency_policy.py:11-23` (module-scoped `manifest` fixture, `Path(__file__).resolve().parents[2] / "pixi.toml"`).
  - [x] Enumerate activation tables **including platform-scoped ones**: `[activation.env]`, `[target.<platform>.activation.env]`, `[feature.<n>.activation.env]`, and `[feature.<n>.target.<platform>.activation.env]`. Verified on pixi 0.70.2 that platform-scoped activation env is honoured and reaches the process; a helper that scans only the unscoped tables leaves a hole through which `COMPONENT_RUNTIME = "local"` in `[target.linux-64.activation.env]` passes green and ships in the production image.
  - [x] `test_default_environment_activation_env_declares_no_component_variable`: assert no key starting with `COMPONENT_` appears in any activation table that the `default` environment resolves — the unscoped `[activation.env]`, its platform-scoped siblings, and the activation env of every feature the `default` environment includes.
  - [x] `test_component_process_absent_from_every_activation_env`: assert `COMPONENT_PROCESS` appears in **no** activation table anywhere in the manifest, feature-scoped and platform-scoped included. This one is absolute and does not depend on which environment resolves it.
  - [x] `test_dev_feature_declares_local_runtime`: assert `[feature.dev.activation.env]["COMPONENT_RUNTIME"] == "local"` — exactly that value, so a typo'd `"Local "`-style variant that `is_local()` would still accept, or a `"dev"` that it would not, both fail loudly here.
  - [x] `test_no_task_declares_component_runtime`: iterate every task in every task table (`[tasks]`, `[feature.<n>.tasks]`, platform-scoped variants); assert no task sets `COMPONENT_RUNTIME` in its `env` at all. The single declaration site is the environment; a task that re-declares it is the failure this catches, because a task `env` overrides the caller and would take the configmap out of the loop.
  - [x] `test_no_production_bound_environment_includes_the_dev_feature`: for every entry in `[environments]` other than the developer environments, assert its feature list does not contain `dev`. This is what keeps the narrowed prohibition honest once Epic 8's six-environment matrix lands; write it so it passes on today's `default`/`dev` pair.
  - [x] `test_serving_process_tasks_declare_no_runtime`: for any task named `web`, `worker` or `beat` that exists, assert it sets no `COMPONENT_RUNTIME`. These tasks arrive in Epic 5; write the assertion so it passes vacuously until then.

- [x] Task 5: Unit-test the locality reader (AC: #4)
  - [x] Create `tests/unit/test_locality.py` (NEW). Use `monkeypatch.setenv` / `monkeypatch.delenv(..., raising=False)`; no reload machinery is needed because Task 1 reads at call time.
  - [x] Assert: `COMPONENT_RUNTIME` absent → `is_local()` is `False` and `is_deployed()` is `True`; `COMPONENT_RUNTIME=""` → deployed; `COMPONENT_RUNTIME="production"` → deployed; `COMPONENT_RUNTIME="dev"` → deployed; `COMPONENT_RUNTIME="local"` → local; `COMPONENT_RUNTIME="LOCAL"` → local.
  - [x] Assert: `COMPONENT_PROCESS` absent → `component_process()` is `None` and `is_serving_process()` is `False`; `COMPONENT_PROCESS="web"` → `"web"` and `True`; `COMPONENT_PROCESS="shell"` → `None` and `False`.

- [x] Task 6: Document the declaration (AC: #1, #2, #4)
  - [x] In `docs/development.md`, under the existing `## Environment` section, add a short subsection stating: locality is declared by the pixi *environment*, `COMPONENT_RUNTIME=local` lives once in `[feature.dev.activation.env]`, the `default` environment declares nothing and reads *deployed*, and absent or unrecognized means deployed.
  - [x] State the developer consequence plainly, because it is the one behavioural change a reader will trip over: the operational commands in `[tasks]` are run as `pixi run -e dev migrate` (etc.) when you want them to behave locally. Bare `pixi run migrate` is the *deployed* invocation and is what the release stage uses.
  - [x] Update the existing sentence at `docs/development.md:54-56` ("Operational commands … run in `default`, because a deployment runs them too") to note that this partition is now what carries locality, so it is load-bearing rather than incidental.

## Dev Notes

### Architecture Constraints

**AD-13 — Locality is declared by the dev environment; process type per pixi task.** Binding rule, in the AD's own words (amended 2026-08-17; the superseded per-task version is what this story was originally written against):

> `COMPONENT_RUNTIME = "local"` is declared exactly once, in `[feature.dev.activation.env]`. Every developer path runs in the `dev` environment and inherits it; the `default` environment declares nothing and therefore reads *deployed* — which is what the golden base runs and what the release stage invokes (`pixi run migrate`, `pixi run collectstatic`). `web`, `worker` and `beat` set no runtime and inherit *deployed*; each sets `COMPONENT_PROCESS` in its own task `env`.
> **No `COMPONENT_*` variable may appear in the `default` environment's resolved activation env; `COMPONENT_PROCESS` may not appear in *any* activation env**, feature-scoped included, because a `COMPONENT_PROCESS` there would make every management command declare itself a serving process and deadlock the release stage on the migrations refusal. **No production-bound environment may include the `dev` feature.** A gate test asserts all three over the materialized `pixi.toml`.
> Locality fails closed: absent or unrecognized means deployed. Process type fails open: absent means not a serving process, because failing it closed would produce exactly that deadlock.

*Prevents:* "the declaration travelling into the deployed image and inverting the fail-closed property; a release-stage task reading *local* and disarming every stage-1 refusal; the entire test suite refusing to start on the day the refusal contract lands; `sys.argv` sniffing."

**Why the amendment happened, so it is not re-litigated.** The superseded rule put `COMPONENT_RUNTIME=local` on `migrate` and `collectstatic`, which `docs/development.md:54-56` and Story 5.5 both establish are **deployment-invoked** — so the production release stage would have read *local* and skipped all five stage-1 refusals. A task's `env` overrides the caller's environment (probed on 0.70.2), so the deployment platform's configmap could not have corrected it. Declaring nothing in `default` inverts that: the platform keeps sole control of the variable, and absence fails closed to *deployed*.

Consequences the dev agent must not trade away:

- **Never** put `COMPONENT_RUNTIME` in `[activation.env]`, a task `env`, `.env`, `pyproject.toml`, a settings module, or a committed dotfile. `[feature.dev.activation.env]` is the **only** permitted site. Never put `COMPONENT_PROCESS` in any activation env at all — a `COMPONENT_PROCESS` there makes `pixi run migrate`, a release-stage step, declare itself a serving process and refuse on the unapplied-migrations condition, deadlocking the release.
- **Mechanism facts, probed against pixi 0.70.2 on 2026-08-17 — do not re-derive them and do not assume otherwise:** a task's `env` overrides the caller's environment; `${VAR:-default}` is **not** expanded in a task `env` (the literal string is exported, which `is_local()` reads as *deployed*); `$VAR` in a task `env` *is* expanded from the caller; a task with no `env` passes the caller's value through untouched; platform-scoped `[target.<platform>.activation.env]` is honoured and reaches the process; a same-named task in both `[tasks]` and `[feature.dev.tasks]` is rejected with `the task '<name>' is ambiguous`; `env` on a `depends-on`-only task is a parse error; a dependency task keeps its own `env` when reached through `depends-on`.
- **Never** infer locality from `sys.argv`, `DEBUG`, the settings module name, `DJANGO_ENV`, or a bare `ENV`. The spine's Consistency Conventions state it directly: `COMPONENT_`-prefixed variables carry component-level runtime facts, and "Never `DJANGO_ENV` or a bare `ENV` — the platform is likely to set a generic `ENV=dev` for a development *deployment*, and a deployed dev environment is still deployed."
- The asymmetry is deliberate and must be preserved exactly: **locality fails closed** (absent or unrecognized ⇒ deployed, so local development is the exception that declares itself) while **process type fails open** (absent ⇒ not a serving process). Do not "tidy" them into the same default.
- Accepted consequence, recorded so it is not treated as a bug: **R-5's sibling R-3** — "A serving process started outside `pixi run web` does not fire the migrations refusal. The price of AD-13's fail-open process type, taken because failing it closed deadlocks the release stage."

**AD-1 / single declaration site.** `src/config/locality.py` is the only place the `COMPONENT_RUNTIME` and `COMPONENT_PROCESS` names and their accepted values are spelled. Epic 4's `src/config/startup/` imports this module rather than re-reading `os.environ`; Epic 5's `web`/`worker`/`beat` tasks are the producers of `COMPONENT_PROCESS`. Do not create a second reader.

**Pixi capability.** Feature-scoped `[feature.<n>.activation.env]` is confirmed available and correctly scoped at the pinned floor — probed on 0.70.2: a task defined in `[tasks]` and run as `pixi run -e dev <task>` inherits the dev feature's activation env, while the same task run bare in `default` does not see it at all. `pixi.toml` sets `requires-pixi = ">=0.70.2"`. The spine's Stack-table note "Per-task `env` confirmed available" remains true but is no longer the mechanism this AD relies on.

### Source Tree — files to touch

| Path | NEW / UPDATE | What changes |
| --- | --- | --- |
| `src/config/locality.py` | NEW | The single locality/process-type reader: `RUNTIME_ENV_VAR`, `PROCESS_ENV_VAR`, `LOCAL`, `SERVING_PROCESSES`, `is_local()`, `is_deployed()`, `component_process()`, `is_serving_process()`. |
| `pixi.toml` | UPDATE | Add `COMPONENT_RUNTIME = "local"` to `[feature.dev.activation.env]` — one key, one table. No task gains an `env`. Add rationale comments there and in `[activation.env]`. |
| `tests/unit/test_locality_declaration.py` | NEW | Manifest assertions over `pixi.toml` (AC #1, #3). |
| `tests/unit/test_locality.py` | NEW | Behavioural assertions over the reader (AC #4). |
| `docs/development.md` | UPDATE | New subsection under `## Environment` describing the declaration. |

**`pixi.toml` today.** `[workspace]` pins `requires-pixi = ">=0.70.2"`. `[environments]` declares only `default` and `dev`, both `solve-group = "default"` — the six-combination matrix (AD-3) does not exist yet and is Epic 8's. `[activation.env]` contains exactly one key, `COVERAGE_CORE = "ctrace"`, with a comment explaining the `sysmon`/`ctrace` template-tracing reason; `[feature.dev.activation.env]` contains exactly one key, `DJANGO_DEBUG_APPS = "True"`. **No task currently declares an `env` table, and no `COMPONENT_*` variable exists anywhere in the repository** (verified by grep over `src/`, `tests/`, `pixi.toml`, `pyproject.toml`, `docs/`). Preserve: every task's existing `default-environment` and `description` — `pixi task list` is the process-model surface AD-14 depends on, and `description` is what it prints. Preserve the comment blocks; the spine's Consistency Conventions require rationale to live beside the configuration it constrains.

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

**Ripple from the AD-13 amendment — do not fix it here.** Story 5.2 is written against the superseded blanket prohibition ("no `COMPONENT_*` in `[activation.env]`") and its assertion will contradict this story's `[feature.dev.activation.env]` declaration. The `COMPONENT_PROCESS` half of 5.2's assertion is unaffected and still absolute. Story 5.2 has not been driven, so the correction belongs in its spec when it is next touched, not in a cross-story edit from here. Flagged rather than patched.

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

Claude Opus 5 (1M context) — bmad-dev-auto, 2026-08-17.

### Debug Log References

Re-derived against the amended AD-13, from the spec rather than from the stash. `stash@{0}`
was read for reference only and left in place; nothing was applied from it. Its `pixi.toml`
and `docs/development.md` hunks implement the superseded per-task-`env` design and were not
reused at all; `src/config/locality.py` and `tests/unit/test_locality.py` were re-derived and
both changed materially (module docstring re-anchored to the environment declaration, finding
4's normalization pinned, finding 11's over-broad ownership claim narrowed).
`tests/unit/test_locality_declaration.py` was rewritten from scratch — the amended design
inverts what it asserts.

Inner loop: `pixi run test` (549 passed) → `pixi run format` (no changes) → `pixi run lint`
(one SIM300 yoda-condition fix in `tests/unit/test_locality.py:55`) → `pixi run typecheck`
(clean, 49 files).

**Final gate: `pixi run ci` exit 0 — 739 passed, 65 warnings, coverage 95.82% (floor 90%).**
No pre-commit auto-fix occurred at gate time; the gate ran clean on the first attempt.

### Completion Notes List

All six tasks and all 35 subtasks are complete. Nothing was traded away and no acceptance
criterion is partially met.

**What was built.** `src/config/locality.py` is the single reader; `pixi.toml` gains exactly
one key — `COMPONENT_RUNTIME = "local"` in `[feature.dev.activation.env]` — plus rationale
comment blocks above that table and inside `[activation.env]`. No task gained an `env`. Two
new unit test files: 30 behavioural assertions over the reader, 11 gate assertions over the
manifest.

**Variances, recorded rather than silent.**

1. *The spec's `pixi.toml` snapshot is one environment stale.* Dev Notes say "`[environments]`
   declares only `default` and `dev`". It declares three: `default`, `dev`, and
   `spike-storage`, which layers the **`dev` feature** (`pixi.toml:382`) and therefore
   inherits the new declaration. `test_no_production_bound_environment_includes_the_dev_feature`
   is written against a declared `DEVELOPER_ENVIRONMENTS = {"dev", "spike-storage"}` set with a
   guard that every name in it still exists, rather than against a hardcoded `default`. This
   is correct under AD-13 — `spike-storage` is a developer environment and its spike loads
   Django — but it is a fact the spec did not state.
2. *Two tests beyond the seven Task 4 enumerates*, both from patch findings (3 and 9 below),
   plus one non-vacuity guard (`test_the_scanners_see_the_manifest_they_claim_to`) and one
   in-force assertion (finding 5). Eleven tests in the file rather than seven.
3. *`component_process()` keeps `.strip().lower()`* and the normalization is now pinned by
   `test_a_declared_process_is_normalized_before_it_is_matched`. Task 1's wording ("returns the
   `COMPONENT_PROCESS` value when it is a member of `SERVING_PROCESSES`") is literally
   satisfiable without normalization; keeping it preserves symmetry with `is_local()`, and
   finding 4's actual complaint was that it was *unpinned*, not that it was wrong.
4. *Story 5.2's contradiction was flagged, not patched*, exactly as Dev Notes instruct. No
   cross-story edit was made.

**Patch findings 2–11, re-read against the amended Tasks 2–4.** (Finding 1 was already folded
into Task 4 by the spec and is implemented in `_activation_tables`, which walks all four
shapes including `[target.<platform>.activation.env]` and
`[feature.<n>.target.<platform>.activation.env]` — `tests/unit/test_locality_declaration.py:125-150`.)

| # | Sev | Disposition |
| --- | --- | --- |
| 2 | medium | **Applies. Fixed** at `tests/unit/test_locality_declaration.py:208-227`. `_tasks()` now returns a `list[tuple[table, name, definition]]` rather than a name-keyed mapping, so a task declared in two tables cannot overwrite its twin and every definition is asserted where it is declared. The docstring records why. |
| 3 | medium | **Applies, re-aimed. Fixed** at `tests/unit/test_locality_declaration.py:412-433` (`test_only_serving_process_tasks_declare_a_process_type`). The finding's blanket "no `COMPONENT_` in task `env`" is wrong under the amended design — `web`/`worker`/`beat` are the legitimate producers of `COMPONENT_PROCESS` in their own `env` (AD-14). The hole it names is real and unchanged, though: `migrate` declaring `COMPONENT_PROCESS = "web"` is verbatim the release deadlock. The assertion confines the variable to the three serving-process task names and passes vacuously today. |
| 4 | medium | **Applies. Fixed** at `tests/unit/test_locality.py:126-153`. Parametrized over `(" web ", "web")`, `("WORKER", "worker")`, `("\tBeat\n", "beat")`; deleting `.strip().lower()` from `component_process()` now fails three cases instead of none. |
| 5 | medium | **Applies, re-aimed and weakened. Fixed** at `tests/unit/test_locality_declaration.py:504-522` (`test_the_declared_runtime_is_in_force_in_this_process`). The finding's premise ("per-task `env` is a mechanism this repo had never used") is moot — the mechanism is now feature activation env, which the repo already uses for `DJANGO_DEBUG_APPS` and `COVERAGE_CORE`. The *split* it asks for is still worth having: every other assertion in the file reads TOML and proves only what is declared. Follows the repo's own declared-vs-in-force precedent (`test_coverage_policy.py:417` + `test_coverage_measurement.py:109`). Verified green under `pixi run test`, `pixi run test-cov` and the full gate. |
| 6 | medium | **Moot.** The claim it corrects — that `ci` cannot carry the declaration because pixi does not propagate a task `env` through `depends-on` — was prose attached to the per-task design. It appears nowhere in this implementation: no task carries an `env`, so no reasoning about `ci` is needed or written, in `pixi.toml`, in either test file or in `docs/development.md`. Confirmed by grep over the five touched files. |
| 7 | medium | **Applies. Fixed** in three places. `tests/unit/test_locality_declaration.py:363-374` states plainly that the manifest assertion is *stricter than* `is_local()` and why (canonical spelling), instead of the false claim that `"Local"` reads as deployed; `tests/unit/test_locality.py:78-90` makes the same point from the reader's side and keeps `"Local"` in the positive parametrization; `docs/development.md` now says "`LOCAL`, `Local` and `\" local \"` all read as local" rather than "only the exact value `local` counts". |
| 8 | medium | **Moot as written — the amendment inverts it. Addressed in docs anyway.** Under the superseded design `pixi run -e dev -- pytest` and `pixi shell` carried no task `env` and were therefore deployed. They now activate the `dev` feature's env and are *local*, which is the amendment's central benefit. `docs/development.md` states it explicitly in the new subsection ("the ad-hoc routes above — `pixi run -e dev -- <cmd>` and `pixi shell -e dev` — both activate the same env and are local too"), directly below the paragraph that recommends them. |
| 9 | low | **Applies. Fixed** at `tests/unit/test_locality_declaration.py:153-178` and `:486-502` (`test_no_activation_script_offers_an_unchecked_export_route`). A script's contents live outside the manifest and cannot be parsed here, so the assertion is that none is declared — which keeps the env-table scan exhaustive and forces the check to be extended the day one is added, rather than being silently bypassed by an `export COMPONENT_RUNTIME=local`. Passes vacuously today. |
| 10 | low | **Applies. Fixed** at `tests/unit/test_locality_declaration.py:275-284` (`_is_component_variable`, `name.upper().startswith(...)`) and applied at every use site, including the `COMPONENT_PROCESS` and `COMPONENT_RUNTIME` exact-name comparisons, which are also `.upper()`-normalized. Windows is a declared platform and its environment variables are case-insensitive, so a lower-case `component_runtime` would have resolved there while passing a case-sensitive scan. |
| 11 | low | **Applies. Fixed** at `src/config/locality.py:30-40`. The module docstring now claims ownership of two names — `COMPONENT_RUNTIME` and `COMPONENT_PROCESS` — and their accepted values, and explicitly disclaims the wider `COMPONENT_*` convention, which the spine's Consistency Conventions define and a later component-level fact would not necessarily route through this module. |

The **rejected** item (the non-vacuity guard's dependence on `COVERAGE_CORE` staying in
`[activation.env]`) was not acted on. The equivalent guard in this implementation,
`test_the_scanners_see_the_manifest_they_claim_to`, is deliberately of the same shape and for
the same recorded reason.

### File List

| Path | NEW / UPDATE |
| --- | --- |
| `src/config/locality.py` | NEW |
| `tests/unit/test_locality.py` | NEW |
| `tests/unit/test_locality_declaration.py` | NEW |
| `pixi.toml` | UPDATE |
| `docs/development.md` | UPDATE |
| `_bmad-output/implementation-artifacts/3-1-local-pixi-tasks-declare-themselves-local.md` | UPDATE (this record) |

## Review Triage Log

### 2026-08-17 — Review pass

- intent_gap: 1: (high 1, medium 0, low 0)
- bad_spec: 0
- patch: 11: (high 1, medium 7, low 3)
- defer: 3: (medium 3)
- reject: 1
- addressed_findings:
  - none

Per the cascading rule, the intent gap makes the eleven patch findings moot for this pass —
none was applied, because the code they anchor to was reverted. They are recorded verbatim
below so the re-derivation does not have to rediscover them.

> **Resolved 2026-08-17 — read the findings against the amended design, not the original.**
> The intent gap below was resolved by amending AD-13 in `ARCHITECTURE-SPINE.md`: locality is
> now declared once in `[feature.dev.activation.env]` and no task carries `COMPONENT_RUNTIME`.
> That dissolves both directions of the gap — the release stage's bare `pixi run migrate`
> resolves in `default` and reads *deployed*, and the Django-loading tooling tasks
> (`typecheck`, `precommit`, `spike-storage`) inherit *local* from the dev environment with no
> list to maintain. **Findings anchored to per-task `env` no longer apply.** Finding 1
> (platform-scoped activation tables are unscanned) *does* still apply and has been folded into
> Task 4. Re-read the rest against the amended Tasks 2-4 before treating any as actionable.

### The intent gap

**The set of tasks that count as "local" is not derivable from the captured intent, and the
set Task 2 names is wrong in both directions.**

AC #2 rests on the premise that *"a container runs its server process directly and never
invokes a local task."* That premise is false for the task set Task 2 declares, and the
repository says so in its own words.

*Direction one — deployment-invoked tasks are declared local.*

- `docs/development.md:54-56`, pre-existing and untouched by this story: "Operational
  commands — `manage`, `migrate`, `collectstatic`, `createsuperuser`, `serve` — run in
  `default`, **because a deployment runs them too**."
- Story 5.5 (frozen), lines 71 and 77: "the release stage runs `pixi run migrate`"; "Pixi is
  the only runner: `pixi run migrate` is how the release stage invokes it."

So `pixi run migrate` in the production release stage would read `COMPONENT_RUNTIME=local`.
That is precisely the first item in AD-13's own *Prevents* clause — "the declaration
travelling into the deployed image and inverting the fail-closed property." Verified against
pixi 0.70.2: a task's `env` **overrides** the caller's environment, so the release stage
cannot opt out by exporting anything. Epic 4's `run_stage_one` returns immediately when
local, so all five stage-1 refusals plus the FR-12 escape-route refusal would be skipped for
the release-stage migration. Mitigating context, not a rebuttal: `web`/`worker`/`beat` set no
runtime, so the *serving* processes still refuse — the exposure is a schema change applied to
a production database by a component that would refuse to serve.

*Direction two — Django-loading tasks are declared deployed.*

- `typecheck` (`mypy src/`) and `precommit`: `pyproject.toml:306` enables
  `mypy_django_plugin.main` and `pyproject.toml:323` sets
  `django_settings_module = "config.settings.test"`, so mypy imports the settings module on
  every run. Task 2 explicitly excludes both as tasks that "never import `config.settings`".
- `spike-storage` (`pixi.toml:524`): runs pytest, and `pyproject.toml` `addopts` carries
  `--ds=config.settings.test`. Not named anywhere in the story.

Once Epic 4 lands, both would evaluate as deployed and raise `ImproperlyConfigured`, breaking
`pixi run typecheck`, every `git commit` through the mypy hook, and `pixi run spike-storage`.

**Why this is not inferable.** At least three resolutions are defensible and they have
different downstream owners:

1. Keep `migrate`/`collectstatic` local and give the release stage its own non-local entry
   point — changes AD-13's task partition and Epic 5 Story 5.5's frozen invocation.
2. Drop `migrate`/`collectstatic` from the local set — but Story 4.2's five stage-1 refusals
   (sqlite backend, `ModelBackend` present, non-empty `ACCOUNT_LOGIN_METHODS`,
   `DJANGO_ADMIN_FORCE_ALLAUTH` not true, `OTEL_SDK_DISABLED`) all fire on an ordinary
   developer's configuration, so `pixi run migrate` would refuse on every local machine.
   This resolution breaks local development outright.
3. Keep the declaration and record the release-stage exposure as a named residual risk beside
   R-3. Nothing in the spine's Named Residual Risks covers it today.

The story cannot choose among these: the choice is an architecture decision about AD-13's task
partition, and it binds Epic 4 and Epic 5. It also needs a rule — not a hand-maintained list —
for what makes a task local, since the list is already wrong in both directions on the day it
was written.

### Patch findings, deferred to the re-derivation (not applied)

1. `[high]` `_activation_tables` does not scan platform-scoped activation tables. Verified on
   pixi 0.70.2 that `[target.<platform>.activation.env]` and
   `[feature.<n>.target.<platform>.activation.env]` are honoured and reach the process. AC #3's
   own gate test therefore has a hole: `COMPONENT_RUNTIME = "local"` in
   `[target.linux-64.activation.env]` passes green and ships in the production image. The
   sibling `_task_tables` in the same file *does* walk `target` scopes — the omission is
   asymmetric within one module.
2. `[medium]` `_tasks()` keys by task name across all tables, so a name declared twice is
   silently overwritten and the shadowed definition escapes both two-way assertions. Repo
   precedent raises on collision (`tests/coverage_policy.py:253-268`, pinned by
   `tests/unit/test_coverage_policy.py:529`). Assert per table, not per name.
3. `[medium]` No assertion covers `COMPONENT_PROCESS` in task `env`. `migrate` declaring
   `COMPONENT_PROCESS = "web"` passes every test in the file, and that is verbatim the release
   deadlock AD-13 exists to prevent. Reuse the `COMPONENT_` prefix scan already written for
   activation tables.
4. `[medium]` `component_process()`'s `.strip().lower()` is unpinned — every positive case is
   already lowercase and unpadded, every negative case fails without normalization. Deleting
   the call leaves the suite green. Contrast `is_local()`, whose normalization *is* pinned.
5. `[medium]` Nothing executing asserts the per-task `env` actually reaches the process; the
   only tests either parse TOML or delete both variables in an autouse fixture. Per-task `env`
   is a pixi mechanism this repo had never used before this change. The repo already splits
   declared-vs-in-force for `COVERAGE_CORE` (`test_coverage_policy.py:408` +
   `test_coverage_measurement.py:109`).
6. `[medium]` The stated reason `ci` cannot carry the declaration is wrong, and it is repeated
   in four places. Verified on pixi 0.70.2: `env` on a `depends-on`-only task is a **parse
   error**, and a dependency task's own `env` *is* applied when reached through `depends-on`.
   The real reason is the manifest schema, not propagation.
7. `[medium]` `test_no_task_declares_an_unrecognized_runtime`'s docstring claims
   `COMPONENT_RUNTIME = "Local"` "silently becomes deployed" — `is_local()` lowercases, so it
   reads as *local*. Same error in prose at the new `docs/development.md` subsection ("Only the
   exact value `local` counts", false for `LOCAL`, `Local`, `" local "`). The assertion is
   stricter than the contract for a reason that does not exist.
8. `[medium]` The documented ad-hoc routes — `pixi run -e dev -- pytest`, `pixi shell` — carry
   no task `env` and are therefore deployed. The new subsection sits directly below the
   paragraph recommending them and never says so.
9. `[low]` `[activation.scripts]` is not scanned by the prohibition test; a script could export
   `COMPONENT_*` through an unchecked mechanism.
10. `[low]` The `COMPONENT_` prefix match is case-sensitive; Windows environment variables are
    not, so a lowercase `component_runtime` in activation env passes and still resolves.
11. `[low]` `src/config/locality.py`'s "single site where the `COMPONENT_*` names are spelled"
    is broader than what the module owns (two names).

### Rejected

- The non-vacuity guard in `test_no_component_variable_in_activation_env` would fail if
  `COVERAGE_CORE` ever left `[activation.env]`. The guard is deliberate and its message says
  exactly why; a manifest with no activation table at all is a reader failure worth failing on.
