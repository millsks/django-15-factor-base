---
status: done
baseline_revision: 64e845a
review_loop_iteration: 0
final_revision: dd80843
followup_review_recommended: true
---

# Story 5.1: The component declares itself in component.toml

Status: done

## Story

As a platform engineer,
I want a component-owned declaration that always travels,
so that a rule a component must obey at runtime does not live in a file the component does not have.

## Acceptance Criteria

**Traceability:** AD-28 · supports FR-40 · SC-3

1. **Given** `component.toml`
   **When** it is created
   **Then** it carries what the component states about itself: the adopted-application list, the selected-feature list, per-database requiredness, per-database release-stage migration steps, and the process-model constraints
   **And** the selected-feature list is the only declaration of the combination's features present at settings import in both the reference application and a materialized component

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

- [x] Task 1 — Author `component.toml` at the repository root (AC: #1, #2)
  - [x] Create `component.toml` with the top-level concerns and nothing else: `[component]`, `adopted_apps`, `selected_features`, `[[databases]]`, `[[processes]]`, `[[admin_processes]]`. Rationale comments live beside the values they constrain (spine Consistency Conventions).
  - [x] `[component] name = "django-15-factor-base"`. Do **not** duplicate anything `pyproject.toml` or `pixi.toml` already owns beyond the name; the name is an AD-25 parameter site owned by Epic 7 — leave the literal value and do not introduce a placeholder token.
  - [x] `adopted_apps = []` at top level — an empty list, present and valid, consumed by AD-8's composition step in Epic 9.
  - [x] `selected_features = ["celery", "redis", "storage"]` at top level — the selected-feature list (AD-28). The reference application is the all-features combination, so all three are listed here; a materialized component carries the subset it selected. The three selectable features are exactly `celery`, `redis` and `storage` — the server-rendered interface is immovable core and is **not** a feature (AD-29, revision 3), so `ui` must never appear in this list.
  - [x] Beside it, record why it lives here rather than in `accelerator.toml`: it is the only declaration of the combination's features present at settings import in **both** trees. `accelerator.toml` is `machinery` and does not travel; `.accelerator.json` cannot serve either, because AD-17 gives the reference application no stamp, so a mechanism reading it would work in materialized components and fail in the tree that has to gate it. AD-8's refusal of a contribution naming an unselected feature reads this list, and Epic 9 is the consumer — do not implement that refusal here.
  - [x] One `[[databases]]` entry for the `default` alias: `alias = "default"`, `required = true`, `migrate = ["migrate --database default --noinput"]` (the release-stage step list, one entry per invocation the deployment repository runs before new pods serve).
  - [x] `[[processes]]` entries for `web` (always), `worker` and `beat` (Celery only). Each entry: `name`, `task`, and its constraints. `beat` carries `replicas = 1` and `replacement = "stop-before-start"`. `web` and `worker` carry `replacement = "rolling"` and no fixed replica count. Story 5.2 owns the constraint values and the two-way gate test; this story owns the file, the schema and the loader.
  - [x] Wrap the `worker` and `beat` `[[processes]]` entries in paired AD-24 line-comment markers `# feature:celery` / `# /feature:celery`. AD-24 and AD-28 both name `component.toml` as a region-bearing `core` path for exactly this reason; the markers are what keep AD-14's two-way gate test passing in the four non-Celery combinations.
  - [x] Write `selected_features` as a **multi-line array with one feature per line**, each line wrapped in its own `# feature:<name>` / `# /feature:<name>` marker pair, so the per-combination value is produced by the one mechanism AD-24 permits rather than by a value rewrite this story would have to invent — see Project Structure Notes.
  - [x] One `[[admin_processes]]` entry for the pruning process (Story 5.7): `name = "prune"`, `task = "prune"`, `schedule = "deployment-repository"`. Admin processes are **not** in the process group and must never set `COMPONENT_PROCESS` (AD-13).

- [x] Task 2 — Build the declaration loader at `src/config/component/` (AC: #1, #4)
  - [x] `src/config/component/__init__.py` re-exporting `load_component_declaration` and the dataclasses.
  - [x] `src/config/component/loader.py`: parse with stdlib `tomllib` (Python 3.14 — no new dependency, and the supply-chain convention forbids adding one for this).
  - [x] Resolve the file independently of Django settings — `Path(__file__).resolve(strict=True).parents[3] / "component.toml"` — because Epic 9 has settings importing this module and a settings import would be circular. Expose `load_component_declaration(path: Path | None = None)` so tests pass a path rather than monkeypatching a constant.
  - [x] Return frozen dataclasses with full type hints: `ComponentDeclaration(name, adopted_apps: tuple[str, ...], selected_features: frozenset[str], databases: tuple[DatabaseDeclaration, ...], processes: tuple[ProcessDeclaration, ...], admin_processes: tuple[AdminProcessDeclaration, ...])`; `DatabaseDeclaration(alias, required, migrate: tuple[str, ...])`; `ProcessDeclaration(name, task, replicas: int | None, replacement)`; `AdminProcessDeclaration(name, task, schedule)`. `selected_features` is a set because every consumer asks membership; order carries no meaning there, unlike `adopted_apps` whose order AD-8 makes load-bearing.
  - [x] Reject an unknown feature name in `selected_features` with `ImproperlyConfigured` against the closed set `{"celery", "redis", "storage"}`, and reject `celery` without `redis` — the broker constraint (FR-26) makes `celery ∧ ¬redis` one of the two invalid combinations of the eight declared. The materializer refuses the pairing at generation (Epic 8, Story 8.5); this is the same rule asserted where the component reads its own declaration, not a second authority for it.
  - [x] Cache with `functools.cache` on the no-argument path so readiness (Story 5.3) does not re-read the file per probe.
  - [x] Missing file, unparseable TOML, or an unknown top-level key raises `ImproperlyConfigured` with a message naming the file and the offending key. Never a bare `except:`, never `except X: pass`.
  - [x] Absent `adopted_apps` and absent `[[admin_processes]]` both default to empty — no `None`, no sentinel, no caller-side special case (AC #4). Absent `selected_features` also defaults to empty: the *Minimal* preset selects no feature and that is a valid combination, not a missing declaration.

- [x] Task 3 — Record the placement rule where a future author will read it (AC: #3)
  - [x] Add a header comment block at the top of `component.toml` stating AD-28's split verbatim in its own terms: a rule the component must obey at runtime or deploy time belongs here; a rule only the materializer needs belongs in `accelerator.toml`.
  - [x] Add a `## The two declarations` section to `docs/deployment.md` if Story 5.5 has already created it; otherwise create `docs/deployment.md` with that section and register it in `mkdocs.yml` `nav` (see Source Tree — `mkdocs build --strict` fails on an unregistered page).

- [x] Task 4 — Tests (AC: #1, #2, #3, #4)
  - [x] `tests/unit/test_component_declaration.py`: `component.toml` exists at the repository root and parses; every `[[databases]]` entry has `alias`, `required` and a non-empty `migrate` list; `[[processes]]` names exactly `web`, `worker`, `beat`; the `beat` entry declares `replicas == 1` and `replacement == "stop-before-start"`; `adopted_apps` is present and is a list; `selected_features` is present and equals `{"celery", "redis", "storage"}` in the reference application.
  - [x] Assert `selected_features` is a subset of the closed set `{"celery", "redis", "storage"}` and that `"ui"` is not in it — the interface mechanism is immovable core (AD-29, revision 3), and a `ui` entry here is the mechanical form of that regression.
  - [x] Loader tests over `tmp_path`-written TOML: a declaration omitting `adopted_apps` loads with an empty tuple and no error (AC #4); a declaration omitting `selected_features` loads as the empty set (*Minimal*) and no error; an unknown feature name raises `ImproperlyConfigured`; `celery` without `redis` raises `ImproperlyConfigured` (FR-26); an unknown top-level key raises `ImproperlyConfigured`; a missing file raises `ImproperlyConfigured`; the returned dataclasses are frozen.
  - [x] Assert no key in `component.toml` duplicates an `accelerator.toml` concern (AC #3): assert the parsed top-level key set is a subset of the closed set `{"component", "adopted_apps", "selected_features", "databases", "processes", "admin_processes"}` — this is the mechanical form of the placement rule and is what fails when someone puts a disposition or a parameter here. `selected_features` is the one entry that looks like an `accelerator.toml` concern and is not: the carrier declares what each feature *is*, this file declares which ones *this component has*.

## Dev Notes

### Architecture Constraints

- **AD-28** — *Rule:* "`component.toml` is `core` and always travels. It carries what a component states about *itself*: the adopted-app list, per-database requiredness, per-database release-stage migration steps, the process-model constraints, and **the selected-feature list** — which AD-8's settings-import refusal reads, and which nothing else in a materialized component can supply. Because the process-model constraints describe process types that exist in only two of six combinations, `component.toml` is itself a region-bearing `core` path under AD-24; without markers inside it, AD-14's two-way gate test fails in the four non-Celery combinations by declaring processes with no matching task. `accelerator.toml` carries what the *accelerator* knows about all components: feature surfaces, dispositions, parameters, presets, the closed contributable surface, and the pinned verification subset. A rule a component must obey at runtime belongs in `component.toml`; a rule only the materializer needs belongs in `accelerator.toml`." *Prevents:* "a materialized component being unable to adopt a reusable app, declare an extra migration step, or state a database's requiredness, because every one of those rules lived in a file the component does not have."
- **AD-1** — `accelerator.toml` "is `machinery` and never travels. Anything a *component* must know about itself at runtime or deploy time belongs in `component.toml` instead (AD-28)." **Do not** add a disposition, a parameter site, a preset or a feature surface to `component.toml`. `accelerator.toml` does not exist yet; it is Epic 7's Story 7.1.
- **AD-2** — Four exhaustive input dispositions: `core` (always travels), `feature:<name>`, `tenant`, `machinery`; **unlisted defaults to `machinery`**. `component.toml` must therefore be listed explicitly as `core` when `accelerator.toml` is authored in Epic 7 — until then its disposition is stated in this story and in the file's own header comment. Failing to list it later would silently make it `machinery` and it would stop travelling, which is exactly what AD-28 prevents.
- **AD-9** — "Release-stage migration becomes one step per database, and `component.toml` declares them so the deployment repository does not have to guess… Readiness treats a contributed database as required unless `component.toml` declares it optional." The `required` field is what Story 5.3's readiness endpoint reads; default it to `true` when absent.
- **AD-8** — "Adoption is explicit — a `pixi.toml` line and a `component.toml` entry. Nothing self-registers; entry-point discovery is forbidden." The `adopted_apps` list is the `component.toml` half. Do **not** implement discovery, scanning, or `INSTALLED_APPS` inference here; Epic 9 consumes the list.
  Also: "A contribution naming a feature the combination did not select is refused at settings import… **The selected-feature list is read from `component.toml` (AD-28)** — the only declaration present at settings import in both the reference application and a materialized component. `accelerator.toml` cannot serve: it is `machinery` and does not travel. `.accelerator.json` cannot serve either: AD-17 states the reference application carries no stamp, so a mechanism reading it would work in materialized components and fail in the tree that has to gate it." This story provides the list and the loader; **Epic 9 implements the refusal that reads it.** That refusal is why the loader must resolve `component.toml` without importing Django settings (Task 2) — it runs *at* settings import.
- **AD-14** — Replica counts and replacement strategy live in `component.toml`. This story creates the fields; Story 5.2 owns their values and the two-way gate test.
- **AD-24** — A `core` path carries feature-owned regions "delimited by paired line comments in the file's own comment syntax, `feature:<name>` / `/feature:<name>`". **No other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`.** TOML's comment syntax is `#`.
- **Consistency Conventions** — "Hand-authored declarations are TOML and visible… Machine-written records are JSON and hidden. Format signals authorship." `component.toml` is hand-authored TOML. "Rationale lives beside the configuration it constrains, in the same file."
- **Consistency Conventions** — "Cross-cutting concerns with several independent consumers and no natural owner live under `src/config/<concern>/`, as `observability/` already does and `authorization/` and `startup/` will." The loader has three independent consumers (readiness, the gate tests, Epic 9's settings composition) and no natural owner, hence `src/config/component/`.
- **Project standards** — Pixi is the only runner: `pixi run test`, `pixi run typecheck`, `pixi run ci`. Never `pip`, `uv`, bare `python`/`pytest`. Python 3.14 only. PEP 8, line length 120, full type hints on public signatures, Google-style docstrings. `X | Y`, `list[X]`, `dict[K, V]` — never `Union`/`List`/`Dict`. Never `print()`; never stdlib `logging` — `structlog` only.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `component.toml` | **NEW** | Does not exist. The component's statement about itself: `[component]`, `adopted_apps`, `selected_features` (one feature per line, each in its own AD-24 marker pair), `[[databases]]`, `[[processes]]` (with AD-24 `celery` markers around `worker`/`beat`), `[[admin_processes]]`. |
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
- **`component.toml` is a region-bearing `core` path, and the spine says so.** This is no longer a gap this story flags: AD-24 lists `component.toml` among the region-bearing paths known at the time of writing, and AD-28 gives the reason — the process-model constraints describe process types that exist in only **two of six** combinations, so without markers AD-14's two-way gate test (Story 5.2) fails in the **four** non-Celery combinations by declaring processes with no matching task. Note that AD-24's set of region-bearing paths is **open** and carrier-declared as an open `[[regions]]` array; it encodes no count, and neither should any test written here. Place the markers now; the `accelerator.toml` declaration follows in Epic 7, the same author-now/declare-in-Epic-7 pattern epics.md records for the coverage omit list, the local sign-in constants and the FR-14 markers.
- **Open question to raise, not to settle here:** `selected_features` is not removed per combination, it takes a *different value* per combination — which is neither a disposition nor a declared AD-25 parameter. The one-feature-per-line form with per-line markers keeps it inside AD-24's permitted mechanism and needs no new machinery, and this story specifies that form. If Epic 7 or Epic 8 finds a materializer-side value rewrite preferable, that is their call to make against AD-24's "no other sub-file removal mechanism is permitted" — record the outcome here rather than letting the two files diverge.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-28]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-8]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-9]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-14]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29] — the interface mechanism is core, so the selectable features are exactly `celery`, `redis`, `storage`.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Revision 3 — the interface mechanism becomes core] — three features, six valid combinations.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Structural Seed]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.1]
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 5] — "`component.toml` is created here and is what makes Epic 9's adopted-app list and per-database migration steps possible at all."
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-40]
- Repository state: `mkdocs.yml` `nav`; `pixi.toml:145-150` `[activation.env]`; `pyproject.toml:160-173` coverage configuration; `tests/integration/conftest.py:12-19`.

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (bmad-dev-auto, implementation subagent)

### Debug Log References

`pixi run ci` green: 1318 passed, total coverage 96.97% (floor 90%). `src/config/component/loader.py` at 100%.

### Completion Notes List

- `component.toml` orders the two bare top-level keys (`adopted_apps`, `selected_features`) **above** `[component]`. TOML folds a bare key written after a table header into that table, so the spec's listed order could not be taken literally without changing what the keys mean. The key set is unchanged.
- `functools.cache` is applied to a private `_load_default()` rather than to `load_component_declaration` itself. Decorating the public function would also cache explicit paths and serve stale bytes for a re-written `tmp_path` file. The spec's requirement — "cache on the no-argument path" — holds exactly: `load_component_declaration() is load_component_declaration()`, and an explicit path is never served from the cache. Both are asserted.
- One validation surface beyond the five refusals the spec enumerates: a single `_typed()` helper (one raise site, one message shape) refuses a wrongly-typed field, so a malformed declaration raises `ImproperlyConfigured` rather than letting a raw `KeyError`/`TypeError` escape. Covered by a parametrized test over 14 field/type pairs.
- `_typed` uses a PEP 695 type parameter (`def _typed[T](...)`); ruff's `UP047` fails the gate on the `TypeVar` form.
- `mkdocs.yml` `nav` was Home / Technology Stack / Development / Observability / Authentication — two entries more than the spec's Source Tree table recorded. `- Deployment: deployment.md` appended.
- **Flagged, not fixed:** `component.toml` is absent from `[tool.hatch.build.targets.sdist] include` (`pyproject.toml:196`), and `[tool.hatch.build.targets.wheel] only-include = ["src"]` means a non-editable install has nothing at `parents[3]/component.toml`. The gate is green because the project runs from the tree under an editable install, and AD-28's "always travels" is about materialization rather than Python packaging. Packaging the declaration is Story 5.6's call (the component is a payload), so it is recorded here rather than expanding this story's Source Tree into `pyproject.toml`.
- The spec's open question is left open as instructed: `selected_features` takes a different *value* per combination rather than being removed, and the one-feature-per-line marked form is the AD-24-permitted mechanism implemented here. If Epic 7 or 8 prefers a materializer-side value rewrite, the outcome belongs in this story file.

### File List

- `component.toml` — NEW
- `src/config/component/__init__.py` — NEW
- `src/config/component/loader.py` — NEW
- `docs/deployment.md` — NEW
- `tests/unit/test_component_declaration.py` — NEW
- `mkdocs.yml` — UPDATE (`nav`)

## Review Triage Log

### 2026-08-28 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 16: (high 0, medium 9, low 7)
- defer: 5: (high 0, medium 4, low 1)
- reject: 6: (high 0, medium 1, low 5)
- addressed_findings:
  - `[medium]` `[patch]` `replicas = true` was accepted because `bool` subclasses `int`, so a boolean reached the deployment repository as the replica count 1 — the one value AD-14 says must never be wrong. Added a `_replicas` helper refusing `bool` before the `int` check; `[[databases]] required` still validates as `bool`.
  - `[medium]` `[patch]` `replacement` accepted any string, so `"recreate"` or `"Rolling"` loaded clean against a field the whole double-enqueue safety argument rests on. Closed the set as `REPLACEMENT_STRATEGIES = {"rolling", "stop-before-start"}`. `[[admin_processes]] schedule` deliberately left open — one known value is a value, not a set.
  - `[medium]` `[patch]` AD-28's placement rule was enforced against the top-level key set only: `[component] version`, `[[databases]] disposition` and `[[processes]] preset` all loaded clean, which is exactly what the file's own header and `docs/deployment.md` claim is refused. Added a closed key set per table and generalised the refusal into `_refuse_unknown_keys`.
  - `[medium]` `[patch]` No identity or sanity constraints: two `[[databases]]` sharing an alias (readiness probes one database twice, the deployment repository runs one migration twice), two `[[processes]]` sharing a name with contradictory replacement strategies, empty-string identities, and `replicas` at zero or negative all loaded clean. Added duplicate refusals for all three record kinds, a blank-identity refusal, and `replicas >= 1`.
  - `[low]` `[patch]` Non-UTF-8 bytes made `tomllib.load` raise `UnicodeDecodeError`, escaping the module's stated "one exception to catch" contract. Caught and re-raised as `ImproperlyConfigured`.
  - `[low]` `[patch]` The `strict=True` rationale was untrue — it claimed to relocate an error message, but `__file__` for an importing module always resolves, and where strict resolution can fail it raises `FileNotFoundError` at import time. Rewritten to state what it actually does (symlink resolution, so `parents[3]` walks from the real location) and what it does not protect against (`parents[3]` landing on a wrong-but-existing directory).
  - `[low]` `[patch]` A missing required key was reported as `must be declared as str, found None`, reading as though the author wrote a null that TOML cannot express. The message now distinguishes an absent key from a wrongly-typed one, from the same single raise site.
  - `[low]` `[patch]` `component.toml`'s process-model comment asserted in the indicative that every process "declares `COMPONENT_PROCESS` through its own pixi task", when no `web`, `worker`, `beat` or `prune` task exists in `pixi.toml` — they arrive with Story 5.2. Reworded to state the rule and name the gap. Same correction in `docs/deployment.md`.
  - `[medium]` `[patch]` `docs/deployment.md` published the `parents[3]` resolution mechanism unconditionally, though the wheel (`only-include = ["src"]`) and the sdist both omit `component.toml`. The page now qualifies it to the source tree and editable install and names Story 5.6 as the owner of packaging; the packaging gap itself is deferred.
  - `[medium]` `[patch]` `test_an_explicit_path_is_not_served_from_the_cache` proved nothing — it compared results from two different files, which can never be the same object under any caching scheme, so it passed even with `@cache` on the public function, the exact staleness bug it claimed to exclude. Replaced with a write / load / rewrite-the-same-path / reload assertion.
  - `[medium]` `[patch]` The closed-set tests compared the committed file against constants imported from the loader, so adding `"presets"` to `TOP_LEVEL_KEYS` or `"graphql"` to `SELECTABLE_FEATURES` passed the entire suite — the sets were closed against the file and open to a developer. Both are now pinned against literals written in the test.
  - `[medium]` `[patch]` The AD-24 marker test guarded the celery region's lower bound only: moving the closing marker past `[[admin_processes]]` still passed, and stripping the region would then silently delete the prune admin process from every non-Celery combination. The test now asserts the region holds exactly the `worker` and `beat` entries and closes before `[[admin_processes]]`, and the brittle `'"web"' not in region` string check (which passed only because a comment spells it in backticks) is replaced with a positional assertion.
  - `[low]` `[patch]` The header test asserted three substrings a header could keep while losing the entire placement rule; it now asserts both halves of the split.
  - `[low]` `[patch]` The mkdocs nav test raised `TypeError: unhashable type: 'list'` on a nested nav section and `AttributeError` on a bare-string entry. `_nav_targets` now handles all three shapes, with a case per shape.
  - `[medium]` `[patch]` Nothing observed the invariant the loader's whole design rests on — that `config.component` imports no `django.conf`. Every test runs under `--ds=config.settings.test`, where `BASE_DIR` is the same repository root, so a rewrite to `settings.BASE_DIR` passed all 48 cases and would deadlock Epic 9's settings composition. Added an AST-based import test following the `tests/unit/startup/test_module_shape.py` idiom.
  - `[low]` `[patch]` `test_a_wrongly_typed_field_is_refused` claimed to cover "each declared field" but never mutated `[[admin_processes]] task` — its replacement string matched the `[[processes]]` entry first, and 100% line coverage hid the hole. Added that case plus 19 cases covering every refusal introduced above.

## Auto Run Result

Status: done

### Summary

`component.toml` now exists at the repository root as the component's own statement about itself (AD-28), and `src/config/component/` reads it without importing Django settings — the property Epic 9 needs, since AD-8's contribution refusal runs *at* settings import. The file carries the adopted-application list, the selected-feature list, per-database requiredness and release-stage migration steps, and the process-model constraints, with AD-24 line-comment marker pairs around the two Celery-only process entries and around each `selected_features` line. The loader returns frozen dataclasses, caches only the no-argument path, and refuses every malformed declaration with `ImproperlyConfigured`.

### Files changed

- `component.toml` — NEW. The declaration, plus the AD-28 placement rule and the AD-24 region rationale as a header block. Bare top-level keys precede `[component]` because TOML would otherwise fold them into it.
- `src/config/component/loader.py` — NEW. `tomllib` parse, frozen `slots=True` dataclasses, `functools.cache` on a private `_load_default()`, closed key sets at the top level and per table, closed feature and replacement-strategy sets, duplicate-identity and blank-identity refusals, the FR-26 broker constraint.
- `src/config/component/__init__.py` — NEW. Public surface: `load_component_declaration`, the four records, the closed sets.
- `docs/deployment.md` — NEW. `## The two declarations`, the resolution mechanism with its packaging limitation stated, and the AD-24 region explanation.
- `tests/unit/test_component_declaration.py` — NEW. Schema assertions against the committed file, marker-region assertions, an AST import guard, and loader tests over `tmp_path` covering every refusal branch.
- `mkdocs.yml` — UPDATE. `- Deployment: deployment.md` added to `nav`.

### Review findings

16 patches applied (9 medium, 7 low) — seven loader refusals that were claimed but not enforced, two prose claims that were not true, and seven tests that passed for the wrong reason. 5 items deferred to `deferred-work.md`: the `selected_features`-versus-`[[processes]]` cross-region consistency check that no story currently owns; `component.toml`'s absence from both build targets (Story 5.6); `pixi run docs` being in no CI job; the undischarged obligation recorded in `tests/unit/startup/test_installed_apps_ordering.py`; and the spine's AD-24 region table recording one region for this file where four now exist. 6 findings rejected as noise or as decisions the spec deliberately assigned elsewhere — chiefly requiring at least one `[[databases]]`/`[[processes]]` entry, requiring a non-empty `migrate` list on a required alias, and the `parents[3]` magic depth, which the tests already re-derive independently.

### Verification

- `pixi run ci` exits 0: pre-commit, build, typecheck, lint, and 1345 tests at 97.03% total coverage against a 90% floor. `src/config/component/loader.py` is at 100% with no missed lines.
- `pixi run docs` (`mkdocs build --strict`) is clean, so the new page is registered correctly even though that task is not itself in the gate.
- Reviews ran adversarially, edge-case-first and verification-gap-first in parallel against the full diff since `64e845a`; every reported finding was reproduced against the working tree before triage.
- All four acceptance criteria verified directly: AC #1 by the schema tests and by confirming no competing feature declaration exists at settings import (`grep` over `src/config/settings/` returns nothing); AC #2 by the header's disposition statement and the marker regions; AC #3 by the closed key sets, now enforced at both levels; AC #4 by the empty-`adopted_apps` load test.

### Residual risks

- The four `task` values (`web`, `worker`, `beat`, `prune`) name pixi tasks that do not exist until Story 5.2. The file and the docs page both say so now, but until 5.2's two-way gate test lands, that half of the declaration has no observer.
- A materialized non-Celery combination has never been produced from this file. The marker regions are asserted structurally, not by a strip-and-reparse, which is Epic 8's machinery.
- `selected_features` takes a different value per combination rather than being removed. The one-feature-per-line marked form keeps that inside AD-24's permitted mechanism, but if Epic 7 or 8 prefers a materializer-side value rewrite, the decision must be recorded here rather than left to diverge.
