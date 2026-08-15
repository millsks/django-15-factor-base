# Story 5.1: The component declares itself in component.toml

Status: ready-for-dev

## Story

As a platform engineer,
I want a component-owned declaration that always travels,
so that a rule a component must obey at runtime does not live in a file the component does not have.

## Acceptance Criteria

**Traceability:** AD-28 · supports FR-40 · SC-3

1. **Given** `component.toml`
   **When** it is created
   **Then** it carries what the component states about itself: the adopted-application list, per-database requiredness, per-database release-stage migration steps, and the process-model constraints

2. **Given** the disposition system
   **When** `component.toml` is classified
   **Then** it is `core` and always travels

3. **Given** the split between the two declarations
   **When** a rule is placed
   **Then** a rule the component must obey at runtime or deploy time goes in `component.toml`
   **And** a rule only the materializer needs goes in `accelerator.toml`

4. **Given** a component with no adopted applications
   **When** it starts
   **Then** an empty adopted-application list is valid and requires no special case

## Tasks / Subtasks

- [ ] Task 1 — Author `component.toml` at the repository root (AC: #1, #2)
  - [ ] Create `component.toml` with the four top-level concerns and nothing else: `[component]`, `adopted_apps`, `[[databases]]`, `[[processes]]`, `[[admin_processes]]`. Rationale comments live beside the values they constrain (spine Consistency Conventions).
  - [ ] `[component] name = "django-15-factor-base"`. Do **not** duplicate anything `pyproject.toml` or `pixi.toml` already owns beyond the name; the name is an AD-25 parameter site owned by Epic 7 — leave the literal value and do not introduce a placeholder token.
  - [ ] `adopted_apps = []` at top level — an empty list, present and valid, consumed by AD-8's composition step in Epic 9.
  - [ ] One `[[databases]]` entry for the `default` alias: `alias = "default"`, `required = true`, `migrate = ["migrate --database default --noinput"]` (the release-stage step list, one entry per invocation the deployment repository runs before new pods serve).
  - [ ] `[[processes]]` entries for `web` (always), `worker` and `beat` (Celery only). Each entry: `name`, `task`, and its constraints. `beat` carries `replicas = 1` and `replacement = "stop-before-start"`. `web` and `worker` carry `replacement = "rolling"` and no fixed replica count. Story 5.2 owns the constraint values and the two-way gate test; this story owns the file, the schema and the loader.
  - [ ] Wrap the `worker` and `beat` `[[processes]]` entries in paired AD-24 line-comment markers `# feature:celery` / `# /feature:celery` — see Project Structure Notes; this makes `component.toml` a region-bearing `core` path.
  - [ ] One `[[admin_processes]]` entry for the pruning process (Story 5.7): `name = "prune"`, `task = "prune"`, `schedule = "deployment-repository"`. Admin processes are **not** in the process group and must never set `COMPONENT_PROCESS` (AD-13).

- [ ] Task 2 — Build the declaration loader at `src/config/component/` (AC: #1, #4)
  - [ ] `src/config/component/__init__.py` re-exporting `load_component_declaration` and the dataclasses.
  - [ ] `src/config/component/loader.py`: parse with stdlib `tomllib` (Python 3.14 — no new dependency, and the supply-chain convention forbids adding one for this).
  - [ ] Resolve the file independently of Django settings — `Path(__file__).resolve(strict=True).parents[3] / "component.toml"` — because Epic 9 has settings importing this module and a settings import would be circular. Expose `load_component_declaration(path: Path | None = None)` so tests pass a path rather than monkeypatching a constant.
  - [ ] Return frozen dataclasses with full type hints: `ComponentDeclaration(name, adopted_apps: tuple[str, ...], databases: tuple[DatabaseDeclaration, ...], processes: tuple[ProcessDeclaration, ...], admin_processes: tuple[AdminProcessDeclaration, ...])`; `DatabaseDeclaration(alias, required, migrate: tuple[str, ...])`; `ProcessDeclaration(name, task, replicas: int | None, replacement)`; `AdminProcessDeclaration(name, task, schedule)`.
  - [ ] Cache with `functools.cache` on the no-argument path so readiness (Story 5.3) does not re-read the file per probe.
  - [ ] Missing file, unparseable TOML, or an unknown top-level key raises `ImproperlyConfigured` with a message naming the file and the offending key. Never a bare `except:`, never `except X: pass`.
  - [ ] Absent `adopted_apps` and absent `[[admin_processes]]` both default to empty — no `None`, no sentinel, no caller-side special case (AC #4).

- [ ] Task 3 — Record the placement rule where a future author will read it (AC: #3)
  - [ ] Add a header comment block at the top of `component.toml` stating AD-28's split verbatim in its own terms: a rule the component must obey at runtime or deploy time belongs here; a rule only the materializer needs belongs in `accelerator.toml`.
  - [ ] Add a `## The two declarations` section to `docs/deployment.md` if Story 5.5 has already created it; otherwise create `docs/deployment.md` with that section and register it in `mkdocs.yml` `nav` (see Source Tree — `mkdocs build --strict` fails on an unregistered page).

- [ ] Task 4 — Tests (AC: #1, #2, #3, #4)
  - [ ] `tests/unit/test_component_declaration.py`: `component.toml` exists at the repository root and parses; every `[[databases]]` entry has `alias`, `required` and a non-empty `migrate` list; `[[processes]]` names exactly `web`, `worker`, `beat`; the `beat` entry declares `replicas == 1` and `replacement == "stop-before-start"`; `adopted_apps` is present and is a list.
  - [ ] Loader tests over `tmp_path`-written TOML: a declaration omitting `adopted_apps` loads with an empty tuple and no error (AC #4); an unknown top-level key raises `ImproperlyConfigured`; a missing file raises `ImproperlyConfigured`; the returned dataclasses are frozen.
  - [ ] Assert no key in `component.toml` duplicates an `accelerator.toml` concern (AC #3): assert the parsed top-level key set is a subset of the closed set `{"component", "adopted_apps", "databases", "processes", "admin_processes"}` — this is the mechanical form of the placement rule and is what fails when someone puts a disposition or a parameter here.

## Dev Notes

### Architecture Constraints

- **AD-28** — *Rule:* "`component.toml` is `core` and always travels. It carries what a component states about *itself*: the adopted-app list, per-database requiredness, per-database release-stage migration steps, and the process-model constraints. `accelerator.toml` carries what the *accelerator* knows about all components: feature surfaces, dispositions, parameters, presets, the closed contributable surface, and the pinned verification subset. A rule a component must obey at runtime belongs in `component.toml`; a rule only the materializer needs belongs in `accelerator.toml`." *Prevents:* "a materialized component being unable to adopt a reusable app, declare an extra migration step, or state a database's requiredness, because every one of those rules lived in a file the component does not have."
- **AD-1** — `accelerator.toml` "is `machinery` and never travels. Anything a *component* must know about itself at runtime or deploy time belongs in `component.toml` instead (AD-28)." **Do not** add a disposition, a parameter site, a preset or a feature surface to `component.toml`. `accelerator.toml` does not exist yet; it is Epic 7's Story 7.1.
- **AD-2** — Four exhaustive input dispositions: `core` (always travels), `feature:<name>`, `tenant`, `machinery`; **unlisted defaults to `machinery`**. `component.toml` must therefore be listed explicitly as `core` when `accelerator.toml` is authored in Epic 7 — until then its disposition is stated in this story and in the file's own header comment. Failing to list it later would silently make it `machinery` and it would stop travelling, which is exactly what AD-28 prevents.
- **AD-9** — "Release-stage migration becomes one step per database, and `component.toml` declares them so the deployment repository does not have to guess… Readiness treats a contributed database as required unless `component.toml` declares it optional." The `required` field is what Story 5.3's readiness endpoint reads; default it to `true` when absent.
- **AD-8** — "Adoption is explicit — a `pixi.toml` line and a `component.toml` entry. Nothing self-registers; entry-point discovery is forbidden." The `adopted_apps` list is the `component.toml` half. Do **not** implement discovery, scanning, or `INSTALLED_APPS` inference here; Epic 9 consumes the list.
- **AD-14** — Replica counts and replacement strategy live in `component.toml`. This story creates the fields; Story 5.2 owns their values and the two-way gate test.
- **AD-24** — A `core` path carries feature-owned regions "delimited by paired line comments in the file's own comment syntax, `feature:<name>` / `/feature:<name>`". **No other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`.** TOML's comment syntax is `#`.
- **Consistency Conventions** — "Hand-authored declarations are TOML and visible… Machine-written records are JSON and hidden. Format signals authorship." `component.toml` is hand-authored TOML. "Rationale lives beside the configuration it constrains, in the same file."
- **Consistency Conventions** — "Cross-cutting concerns with several independent consumers and no natural owner live under `src/config/<concern>/`, as `observability/` already does and `authorization/` and `startup/` will." The loader has three independent consumers (readiness, the gate tests, Epic 9's settings composition) and no natural owner, hence `src/config/component/`.
- **Project standards** — Pixi is the only runner: `pixi run test`, `pixi run typecheck`, `pixi run ci`. Never `pip`, `uv`, bare `python`/`pytest`. Python 3.14 only. PEP 8, line length 120, full type hints on public signatures, Google-style docstrings. `X | Y`, `list[X]`, `dict[K, V]` — never `Union`/`List`/`Dict`. Never `print()`; never stdlib `logging` — `structlog` only.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `component.toml` | **NEW** | Does not exist. The component's statement about itself: `[component]`, `adopted_apps`, `[[databases]]`, `[[processes]]` (with AD-24 `celery` markers around `worker`/`beat`), `[[admin_processes]]`. |
| `src/config/component/__init__.py` | **NEW** | Public surface: `load_component_declaration` and the dataclasses. |
| `src/config/component/loader.py` | **NEW** | `tomllib` parse, frozen dataclasses, `functools.cache`, `ImproperlyConfigured` on every malformed input. |
| `docs/deployment.md` | **NEW** (or UPDATE if Story 5.5 landed first) | Adds `## The two declarations`. `docs/` today holds only `index.md`, `development.md`, `observability.md`. |
| `mkdocs.yml` | UPDATE | `nav` today lists exactly Home/Development/Observability. `pixi run docs` is `mkdocs build --strict`, which **fails on a page absent from `nav`** — add `- Deployment: deployment.md`. |
| `tests/unit/test_component_declaration.py` | **NEW** | Schema and loader assertions. |

Verified absent today: `component.toml`, `accelerator.toml`, `src/config/component/`, `src/config/startup/`, `src/config/authorization/`, `src/django_apps/`, `tools/materializer/`, `Dockerfile`.

### Testing Requirements

- Unit tests only for this story — the loader does no I/O beyond reading one file that ships with the tree, and schema assertions are static. No `@pytest.mark.integration` test is warranted; do not add one for form's sake.
- `tests/integration/conftest.py:12-19` auto-marks everything collected under `tests/integration/` as `integration`, so the marker is applied by collection rather than by hand; state the marker explicitly anyway on any integration test you add, per project standard.
- Test disposition (spine Consistency Conventions): these tests cover a `core` path, so they are `core` and are never pruned.
- AD-20 coverage floor: **ninety percent including templates, everywhere**, `COVERAGE_CORE=ctrace` in force (`pixi.toml:145-150`). `pixi run test-cov` carries `--cov-fail-under=90`. The loader's error branches must be covered — every `ImproperlyConfigured` path needs a test.
- Do **not** add `src/config/component/` to `[tool.coverage.run] omit` (`pyproject.toml:162-169`). AD-20 makes that list a closed, carrier-declared surface; growing it is the exact narrowing AD-20 exists to prevent.
- Run `pixi run test` in the inner loop; the story is done when `pixi run ci` (`test-cov`, `lint`, `typecheck`, `build`) exits 0.

#### Project Structure Notes

- The Structural Seed places `component.toml` at the repository root beside `accelerator.toml` and `pixi.toml`, annotated "core — the component's statement about itself (AD-28)". This story lands the first of those three.
- `src/config/component/` is a new `src/config/<concern>/` sibling of the existing `observability/`. The Structural Seed enumerates `settings/`, `observability/`, `authorization/`, `startup/` under `src/config/` and does not name `component/`; the seed is a seed, not a closed list, and the Consistency Conventions rule for cross-cutting concerns is the governing text. Recorded here as a deliberate variance.
- **Variance to report:** AD-24 names three region-bearing `core` paths (`src/config/settings/base.py`, `src/config/observability/telemetry.py`, `pixi.toml`). Because `worker` and `beat` are Celery-only process types and `component.toml` is `core` and always travels, `component.toml` must carry `feature:celery` regions too, or the two-way process-model gate test (AD-14, Story 5.2) fails in the eight non-Celery combinations by declaring processes with no task. `component.toml` is therefore a **fourth** region-bearing `core` path and must be declared as such in `accelerator.toml` in Epic 7. Place the markers now; the declaration follows the same author-now/declare-in-Epic-7 pattern epics.md records for the coverage omit list, the local sign-in constants and the FR-14 markers.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-28]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-8]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-9]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-14]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Structural Seed]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.1]
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 5] — "`component.toml` is created here and is what makes Epic 9's adopted-app list and per-database migration steps possible at all."
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-40]
- Repository state: `mkdocs.yml` `nav`; `pixi.toml:145-150` `[activation.env]`; `pyproject.toml:160-173` coverage configuration; `tests/integration/conftest.py:12-19`.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
