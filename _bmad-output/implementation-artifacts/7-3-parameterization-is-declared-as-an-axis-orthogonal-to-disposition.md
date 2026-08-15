# Story 7.3: Parameterization is declared as an axis orthogonal to disposition

Status: ready-for-dev

## Story

As a platform engineer,
I want every parameter and its exact substitution sites declared,
so that a value correct for this repository and wrong for any other cannot travel unnoticed.

## Acceptance Criteria

**Traceability:** FR-24 (parameters), FR-37 · AD-25

1. **Given** the carrier
   **When** parameters are declared
   **Then** `[parameters]` names each parameter, its fixture value, and every exact path and token site it substitutes

2. **Given** parameter reconciliation
   **When** the gate runs
   **Then** a declared parameter with no site fails
   **And** a site matching no declared parameter fails

3. **Given** the parameter set
   **When** it is enumerated
   **Then** it is `sonar-project.properties` (project key), `README.md`, `CHANGELOG.md`, `LICENSE`, `pyproject.toml`, `mkdocs.yml`, and the component name

4. **Given** the component name
   **When** it is substituted
   **Then** it is one parameter with several sites — `pixi.toml` `[workspace] name`, `pyproject.toml` `[project] name`, the `[pypi-dependencies]` self-install key, and `[pypi-options] no-build-isolation`

5. **Given** `src/django_service/`
   **When** parameterization is considered
   **Then** it is not a parameter
   **And** it is a constant, because reusable apps import from it by that name in every deployment

6. **Given** the hardcoded project key at `sonar-project.properties:6`
   **When** it is shipped unparameterized
   **Then** nothing fails and every component's metrics merge silently into this project
   **And** that is precisely the consequence this story prevents

## Tasks / Subtasks

- [ ] Task 1 — Declare `[parameters]` in `accelerator.toml` (AC: #1, #3)
  - [ ] Populate the `[parameters]` slot Story 7.1 created. Model each parameter as `[[parameters]]`: `name` (stable identifier used by the fixture set and the portal order surface), `description`, `fixture` (the test value Story 8.6 consumes), and `sites` — an array of tables, each `{ path = "...", token = "...", occurrences = N }` or `{ path = "...", locator = "..." }` for structured formats.
  - [ ] Declare exactly the seven parameters AC #3 enumerates, no more and no fewer: `project_key`, `readme`, `changelog`, `license`, `pyproject_metadata`, `mkdocs_metadata`, `component_name`.
  - [ ] `fixture` values must be visibly synthetic so a fixture leaking into real output is obvious on sight — not `django-15-factor-base` with one character changed.
  - [ ] Record beside `[parameters]` the AD-25 statement that a path has a disposition **and, independently**, a parameter set. The same path may be `core` and parameterized; disposition never implies substitution and substitution never implies disposition.

- [ ] Task 2 — Declare the component-name parameter's four sites exactly (AC: #4)
  - [ ] `pixi.toml`, `[workspace] name` — the value `django-15-factor-base` at `:4`.
  - [ ] `pyproject.toml`, `[project] name` — the value `django-15-factor-base` at `:6`.
  - [ ] `pixi.toml`, `[pypi-dependencies]` — the **key** `django-15-factor-base` at `:99`. This is a table key, not a value; the substituter must rewrite the key and leave `{ path = ".", editable = true }` intact. Story 1.7 asserts this block contains exactly one entry and that it is the editable self-install; renaming the key must keep that assertion true.
  - [ ] `pixi.toml`, `[pypi-options] no-build-isolation` — the list element `"django-15-factor-base"` at `:104`. This value must stay equal to the `[pypi-dependencies]` key or the no-build-isolation opt-out silently stops applying and the build frontend fetches `hatchling`/`hatch-vcs` from PyPI, which is a supply-chain violation Story 1.7's test does not cover. Add a carrier `reason` recording that coupling.
  - [ ] One parameter, four sites. Do not declare four parameters that happen to share a fixture — AC #4 says *one parameter with several sites*, and Story 8.6's fixture coverage counts parameters.

- [ ] Task 3 — Declare the remaining six parameters' sites, verified against the files (AC: #1, #3, #6)
  - [ ] `project_key` → `sonar-project.properties`, `sonar.projectKey=millsks_django-15-factor-base` at `:6`. **Confirmed at line 6.** Also audit the neighbouring identity lines and decide each explicitly: `sonar.organization=millsks` (`:7`) and `sonar.projectName=django-15-factor-base` (`:10`) carry the same defect AC #6 names — a component shipping them reports into this organization and this project name. Either fold them into `project_key`'s site list or declare them as their own sites and record the decision; do not leave them undeclared, because AC #2's second direction then fails on them.
  - [ ] `readme` → `README.md`. The whole file is the parameter: title `# django-15-factor-base` at `:1`, the one-line description at `:3`, and the quick-start block. Declare it as a whole-file parameter whose fixture is a generated component README, and record that the accelerator's own README is `core` and travels but is substituted wholesale.
  - [ ] `changelog` → `CHANGELOG.md`. Whole file. A generated component starts with an empty changelog; shipping this repository's history into it is the same defect as the Sonar key with a different blast radius.
  - [ ] `license` → `LICENSE`. Whole file, or at minimum the copyright line `Copyright (c) 2026 Kevin Mills` at `:3`. A component inherits the licence its ordering organization chooses, not this one.
  - [ ] `pyproject_metadata` → `pyproject.toml`: `description` (`:9`), `authors` (`:12-14`). `name` is the `component_name` parameter's site, declared in Task 2 — do not double-claim it, and make the reconciler reject a path/token pair claimed by two parameters.
  - [ ] `mkdocs_metadata` → `mkdocs.yml`: `site_name` (`:1`), `site_description` (`:2`), `repo_url` (`:3`).
  - [ ] Audit for sites the epic does not enumerate and record what you find rather than silently substituting or silently shipping. Known: `src/config/settings/base.py` `ADMINS = ['"Kevin Samuel Mills" <millsks@gmail.com>']` (`:266`) and `SPECTACULAR_SETTINGS["TITLE"]`/`["DESCRIPTION"]` (`:374-375`); `src/config/settings/production.py` `ALLOWED_HOSTS` default `["millsks.github.io"]` (`:21`), `DEFAULT_FROM_EMAIL` (`:96-99`), `EMAIL_SUBJECT_PREFIX` (`:104-107`) and `SPECTACULAR_SETTINGS["SERVERS"]` (`:151-153`); `src/config/observability/telemetry.py` `DEFAULT_SERVICE_NAME = "django-15-factor-base"` (`:31`); `pyproject.toml` git-cliff repository URLs in commented postprocessors (`:235`, `:248`). Each is either a new parameter, an environment-driven value that should stop being hardcoded, or a deliberate constant. Decide, declare, and write the reason in the carrier. Leaving any of them undeclared fails AC #2's second direction, which is the point.

- [ ] Task 4 — Assert `src/django_service/` is not a parameter (AC: #5)
  - [ ] Add a gate test asserting no `[[parameters]]` entry names a site whose `path` is under `src/django_service/` and no parameter's `token` equals `django_service`.
  - [ ] Record in the carrier, beside `[parameters]`, that this is AD-5's constant and PRD divergence D-1, closed: FR-37 once listed `src/django_service/` as parameterized and now states it is a constant, "not parameterized, and this is load-bearing."
  - [ ] Do not rename, alias, or template the package anywhere. Reusable apps import from it by that name in every deployment (AD-5, AD-6).

- [ ] Task 5 — Build the parameter reconciler (AC: #2, #5, #6)
  - [ ] Create `tools/materializer/parameters.py` (NEW). Public surface: `reconcile_parameters(carrier: Carrier, repo_root: Path) -> list[str]`.
  - [ ] Direction one — a declared parameter with no site fails: every `[[parameters]]` entry has at least one site, every site's `path` exists, and every site's `token` occurs in that file the declared number of times. A token that has drifted out of the file (renamed setting, edited README heading) fails here rather than producing a silent no-op substitution.
  - [ ] Direction two — a site matching no declared parameter fails: scan the parameterizable file set for the known-leaky literals — the component name `django-15-factor-base`, `millsks`, `millsks.github.io`, `Kevin Mills`, `millsks@gmail.com` — and fail on any occurrence not covered by a declared site. This is what turns AC #6 from a statement into a test. Hold the literal list in `accelerator.toml` beside `[parameters]`, not in the Python module; AD-1 forbids a second declaration site.
  - [ ] Exempt `_bmad/`, `_bmad-output/`, `.agents/`, `.claude/`, `.bmad-loop/` and `pixi.lock` from direction two by disposition, not by hardcoded path list — they are `machinery` and never travel, so a literal there cannot leak. Read the disposition from the Story 7.1 carrier.
  - [ ] Never `print()`; failures are returned as data. Full type hints, Google-style docstrings.

- [ ] Task 6 — Tests (AC: all)
  - [ ] `tests/unit/materializer/test_parameters.py` (NEW): unit tests over inline TOML and `tmp_path` files — a parameter with zero sites fails; a site whose token is absent fails; an occurrence count mismatch fails; a leaked literal in a travelling path fails; the same literal in a `machinery` path does not.
  - [ ] `tests/integration/materializer/test_parameter_reconciliation.py` (NEW), `@pytest.mark.integration`: `reconcile_parameters` over the real carrier and the real tree returns zero failures.
  - [ ] `tests/integration/materializer/test_django_service_not_parameterized.py` (NEW), `@pytest.mark.integration`: the Task 4 assertion.
  - [ ] `tests/integration/materializer/test_component_name_sites.py` (NEW), `@pytest.mark.integration`: the component name is one parameter; its four sites are exactly the ones AC #4 names; the `[pypi-dependencies]` key and the `[pypi-options] no-build-isolation` element are equal in the reference application and would remain equal after substitution.
  - [ ] `pixi run ci` exits 0.

## Dev Notes

### Architecture Constraints

**AD-25 — Parameterization is an orthogonal axis, not a disposition.** Binding rule: *"A path has a disposition (AD-2) and, independently, a parameter set. `accelerator.toml` declares `[parameters]`: each parameter's name, its fixture value, and every exact path and token site it substitutes. Reconciliation covers it both ways — a declared parameter with no site fails, a site matching no declared parameter fails. The parameters are `sonar-project.properties` (project key), `README.md`, `CHANGELOG.md`, `LICENSE`, `pyproject.toml`, `mkdocs.yml`, and the component name — which is a multi-site substitution spanning `pixi.toml` `[workspace] name`, `pyproject.toml` `[project] name`, the `[pypi-dependencies]` self-install key and `[pypi-options] no-build-isolation`. `src/django_service/` is **not** a parameter (AD-5)."*

**Prevents:** *"`sonar-project.properties`'s hardcoded key travelling as `core` so every component's metrics merge into this project silently — nothing failing, which is the exact consequence FR-37 names; and FR-31's fail-on-missing-fixture rule having nothing to compare against."*

**Ordering constraint — this is why the story exists where it does.** AD-25 closes with: *"Building the materializer before parameterization exists re-cuts every carrier entry, every fixture and every combination's gate output, so it does not happen in that order."* The epic states it again at `epics.md:1654`: **Story 7.3 must land before Epic 8 begins.** Do not defer any part of `[parameters]` to Epic 8 "once the materializer can see it". Every parameter and every site is declared here, complete, before the materializer exists.

**AD-1 — one declaration site.** Parameters and their sites are declared in `accelerator.toml` and nowhere else. The leaky-literal list the reconciler scans for, the fixture values, and the site tokens all live in the carrier. A Python constant holding any of them is a second declaration site and is forbidden.

**AD-5 — `django_service` is a constant.** *"The package name `django_service` is a constant, never parameterized — reusable apps import from it by that name in every deployment."* PRD divergence D-1 is closed in the PRD's own words: FR-37 now states it is not parameterized and that this is load-bearing.

**AD-2 — orthogonality in practice.** `pyproject.toml`, `pixi.toml`, `README.md`, `LICENSE`, `CHANGELOG.md`, `mkdocs.yml` and `sonar-project.properties` are all `core` — they travel — *and* they are parameterized. `accelerator.toml` is `machinery` — it never travels — and therefore never carries a site. Do not conflate the two axes in either direction.

**AD-17 / FR-31 — what this feeds.** The provenance stamp records "the full order values"; the fixture set (Story 8.6) must cover "every parameterized value declared in Story 7.3, including the component package name and the code-quality project key." A parameter declared here without a fixture makes materialization fail rather than default — that is FR-31's rule, and it has nothing to compare against unless this story is complete.

**Project standards.** Pixi is the only runner. Python 3.14 only. conda-forge only. PEP 8 / 120 / full type hints / Google docstrings. Never `print()`, never stdlib `logging`, never bare `except:`, never `except X: pass`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `accelerator.toml` | UPDATE | Populate `[[parameters]]` and the leaky-literal list. Preserve `[dispositions]`, `[features]`, `[[regions]]` from Stories 7.1 and 7.2. |
| `tools/materializer/parameters.py` | NEW | Two-way parameter reconciler. |
| `tools/materializer/carrier.py` | UPDATE | Add `Carrier.parameters()` and `Carrier.leaky_literals()`. Preserve the Story 7.1 loader contract and the Story 7.2 `regions()` accessor. |
| `tests/unit/materializer/test_parameters.py` | NEW | Reconciler unit tests. |
| `tests/integration/materializer/test_parameter_reconciliation.py` | NEW | Real-tree gate test, `@pytest.mark.integration`. |
| `tests/integration/materializer/test_django_service_not_parameterized.py` | NEW | AC #5 assertion, `@pytest.mark.integration`. |
| `tests/integration/materializer/test_component_name_sites.py` | NEW | AC #4 assertion, `@pytest.mark.integration`. |

**No source file is edited by this story.** Parameterization is declared, not applied — substitution happens in the materializer (Epic 8). The reference application keeps its own real values, which is why it stays runnable and gateable (AD-3).

**Site verification, 2026-08-15 — every cited location confirmed by reading the file.**

| Site | Confirmed |
|---|---|
| `sonar-project.properties:6` `sonar.projectKey=millsks_django-15-factor-base` | Yes, exactly line 6 as the epic states |
| `sonar-project.properties:7` `sonar.organization=millsks` | Present; not enumerated by the epic — Task 3 requires a decision |
| `sonar-project.properties:10` `sonar.projectName=django-15-factor-base` | Present; not enumerated by the epic — Task 3 requires a decision |
| `pixi.toml:4` `[workspace] name = "django-15-factor-base"` | Yes |
| `pixi.toml:99` `[pypi-dependencies]` key `django-15-factor-base` | Yes, `django-15-factor-base = { path = ".", editable = true }` |
| `pixi.toml:104` `[pypi-options] no-build-isolation = ["django-15-factor-base"]` | Yes |
| `pyproject.toml:6` `[project] name = "django-15-factor-base"` | Yes |
| `pyproject.toml:9,12-14` `description`, `authors` | Yes |
| `mkdocs.yml:1-3` `site_name`, `site_description`, `repo_url` | Yes |
| `README.md:1,3` title and description | Yes |
| `CHANGELOG.md` | Present, git-cliff generated |
| `LICENSE:3` `Copyright (c) 2026 Kevin Mills` | Yes |

**Not-yet-enumerated literals found in the tree** (Task 3's audit, pre-run so the dev agent does not have to rediscover them): `src/config/settings/base.py:266,374,375`; `src/config/settings/production.py:21,96-99,104-107,151-153`; `src/config/observability/telemetry.py:31`; `pyproject.toml:235,248`. `sonar-project.properties:24,31` reference `src/config/websocket.py`, which AD-16 deletes in Story 1.4 — if that story has landed, the reference is already gone; if not, do not fix it here.

### Testing Requirements

- Unit: `tests/unit/materializer/test_parameters.py`. Isolated, milliseconds, `tmp_path` only.
- Integration: the four `tests/integration/materializer/` modules named above, every test `@pytest.mark.integration`, read-only against the repository, writes confined to `tmp_path`, state left as found.
- The assertions AC #2 demands are two-directional and both must be genuinely capable of failing. A reconciler that only checks direction one passes today and lets `sonar.organization` ship. Write the direction-two negative test first.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` in force (AD-20).
- Test disposition: these tests cover `machinery` and carry `machinery`.

#### Project Structure Notes

- The Structural Seed places `accelerator.toml` at the root carrying "surfaces, dispositions, parameters, presets". This story fills the parameters third.
- No variance between the Seed and the repository is introduced here. The one thing to watch: Story 1.6 (AD-7) rewrites `[tool.hatch.build.targets.wheel]` in `pyproject.toml` from `packages = [ "src/config", "src/django_service" ]` (`:127` today) to a `sources` remapping. That block names `django_service` — a constant, not a parameter — so the rewrite must not introduce a component-name site. If Story 1.6 lands after this one, re-run parameter reconciliation and confirm it still passes.
- `pyproject.toml` is both parameterized and a tool-configuration file. The parameter's sites are the `[project]` metadata keys only; the ruff, pytest, coverage, mypy and git-cliff tables are `core` content that travels verbatim.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-25]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-5]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-17]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Divergences From the PRD] — D-1, closed
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.3]
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 7] — line 1654: Story 7.3 must land before Epic 8 begins
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.6] — the fixture set consumes this declaration; traceability marker, not an acceptance condition here
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.7] — `[pypi-dependencies]` carries only the editable self-install
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-37]
- Repository, verified 2026-08-15: `sonar-project.properties:6,7,10`; `pixi.toml:4,99,104`; `pyproject.toml:6,9,12-14,127`; `mkdocs.yml:1-3`; `LICENSE:3`; `README.md:1,3`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
