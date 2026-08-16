---
baseline_revision: c8b538f
final_revision: 9b9d0d0
review_loop_iteration: 0
followup_review_recommended: true
status: done
---

# Story 1.6: Import roots are declared in exactly one place

Status: done

## Story

As a developer working on a generated component,
I want one import-root declaration,
so that a source root cannot work under pytest and fail under gunicorn.

## Acceptance Criteria

**Traceability:** AD-7 · supports AD-6

1. **Given** six declaration sites exist today
   **When** this story lands
   **Then** the `sys.path` inserts at `manage.py:23-25`, `asgi.py:18-20` and in `wsgi.py` are removed
   **And** the pytest `pythonpath` setting and `--app-dir src` in **both** the `serve` and `serve-reload` tasks are removed

2. **Given** the pytest `pythonpath` is `["src", "."]` and the `"."` entry is what makes `tests.factories` importable under `--import-mode=importlib`
   **When** the setting is removed
   **Then** `tests.factories` still resolves from `tests/conftest.py`
   **And** how it resolves is recorded rather than left to coincidence

3. **Given** one site is retained
   **When** the root is declared
   **Then** it is `[tool.hatch.build.targets.wheel]` declaring it through a `sources` remapping
   **And** the site is *converted* to that shape, since it reads `packages = ["src/config", "src/django_service"]` today
   **And** the declaration is directory-level, needing no per-app edit

4. **Given** the removals
   **When** the suite runs under pytest and the application is served under gunicorn and under uvicorn
   **Then** imports resolve identically in all three

5. **Given** `uvicorn --app-dir` accepts a single directory
   **When** roots are declared
   **Then** it is never used as a declaration mechanism

## Tasks / Subtasks

- [x] Task 1 — Convert the retained site to a `sources` remapping first (AC: #3, #4)
  - [x] `pyproject.toml:126-127` currently reads `[tool.hatch.build.targets.wheel]` / `packages = [ "src/config", "src/django_service" ]` with the comment at `:125` "src/ is the import root; config and django_service are both top-level packages." `packages` is a per-package enumeration; AD-7 requires a **directory-level** `sources` remapping so that adding an app needs no per-app edit.
  - [x] Replace it with a `sources`-based declaration that maps `src/` onto the wheel root — hatchling's `[tool.hatch.build.targets.wheel] sources` key. Determine the exact key spelling and value shape against the installed `hatchling >=1.27,<2` (`pixi.toml:79`) rather than guessing; verify with `pixi run build` and by inspecting the produced wheel's top-level entries.
  - [x] The editable install is what puts the root on `sys.path` at runtime: `pixi.toml:98-99` declares `django-15-factor-base = { path = ".", editable = true }` and `pixi.toml:103-104` sets `no-build-isolation` for it. Hatchling's editable install writes a finder honouring `sources`, which is why the `sys.path` inserts become removable. **Do this task before Task 2** — remove the fallbacks only once the one retained site actually works.
  - [x] Add `src/django_apps/` to the remapping only if it exists. It does **not** exist today. AD-7 states the retained site "declares both roots via a `sources` remapping of `src/` and `src/django_apps/`", and `epics.md:347` records that Story 1.6's single site "gains the `src/django_apps/` root in Epic 9 without gaining a second site." **Forward context, not this story's acceptance condition:** declare only `src/` now, and add a comment at the declaration recording that Epic 9 adds the second root to this same table.
  - [x] **Two roots, not three.** The finished remapping declares `src/` and `src/django_apps/` and nothing else. `config` and `django_service` are packages *within* `src/` and must not reappear as their own entries — reinstating them beside `src/` is the per-package enumeration this task exists to remove, and it would make the "no per-app edit" promise false again.
  - [x] After the change, run `pixi install` (or the project's re-install path) so the editable finder is regenerated. A stale `.pixi` environment will make Task 2 look like it worked when it did not.

- [x] Task 2 — Remove the six fallback declaration sites (AC: #1, #5)
  - [x] `manage.py` — remove the comment at `:22` ("src/ is the import root: config, users and contrib are top-level packages.") and the insert at `:23-25` (`src_dir = Path(__file__).parent.resolve() / "src"` / `if str(src_dir) not in sys.path:` / `sys.path.insert(0, str(src_dir))`). Then remove the now-unused `import sys` at `:5` **only if** `sys` is otherwise unused — it is still used by `execute_from_command_line(sys.argv)` at `:33`, so `import sys` stays. Remove `from pathlib import Path` at `:6`, which becomes unused. **AD-7 names `manage.py:23-25` with its comment at `:22`, which is where the insert actually is; an earlier revision of the AD cited `:24-26` and was wrong by one line.**
  - [x] `src/config/asgi.py` — remove the comment at `:17` and the insert at `:18-20` (`SRC_DIR = Path(__file__).resolve(strict=True).parent.parent` / `if str(SRC_DIR) not in sys.path:` / `sys.path.insert(0, str(SRC_DIR))`). Then remove `import sys` at `:12` and `from pathlib import Path` at `:13`, both of which become unused. **This matches AD-7's cited `asgi.py:18-20` exactly.** Story 1.4 owns the deletion of the scope dispatcher in the same file; if both land together, keep the hunks separate and attribute them.
  - [x] `src/config/wsgi.py` — remove the comment at `:23` and the insert at `:24-26`, then remove `import sys` at `:18` and `from pathlib import Path` at `:19`, both of which become unused. AD-7 names `wsgi.py` without a line range; the range is `:23-26` including its comment.
  - [x] `pixi.toml:179` — remove `--app-dir src` from the `serve` task, leaving `uvicorn config.asgi:application`.
  - [x] `pixi.toml:186` — **the sixth site.** AD-7 names it explicitly; an earlier revision named only `serve`. The `serve-reload` task reads `uvicorn config.asgi:application --app-dir src --reload --reload-dir src`. Remove `--app-dir src` here too; AC #5 says `--app-dir` "is never used as a declaration mechanism", which admits no per-task exception. **Keep `--reload-dir src`** — that is a file-watch target, not an import-root declaration, and removing it would break autoreload.
  - [x] `pyproject.toml:149` — the pytest setting reads `pythonpath = [ "src", "." ]` with the comment at `:148` `# "src" makes config/ and django_service/ importable; "." makes tests.factories importable.` Remove `"src"`. See Task 3 for the `"."` entry.

- [x] Task 3 — Resolve the `"."` pythonpath entry deliberately (AC: #1, #2)
  - [x] AC #1 says "the pytest `pythonpath` setting ... [is] removed", and AD-7 names `pyproject.toml` `[tool.pytest.ini_options] pythonpath` as one of the six sites. AD-7 also states the consequence in its own words: "**Removing the pytest `pythonpath` removes a non-source-root entry with it** ... the removal is not executable until `tests.factories` resolves without it." AC #2 is that condition, and it is an acceptance condition of this story rather than a note. The `"."` entry is not a *source* root — it makes `tests.factories` importable, and `tests/` is a package (`tests/__init__.py` exists). `tests/conftest.py` does `from tests.factories import UserFactory`; `tests/unit/` and `tests/integration/` also carry `__init__.py`. `pyproject.toml:145` sets `--import-mode=importlib`.
  - [x] **Preferred resolution:** remove the `pythonpath` setting entirely and make the tests package resolve without it — verify whether pytest ≥9 with `--import-mode=importlib` and `tests/__init__.py` present resolves `tests.factories` from rootdir on its own. If it does, delete lines `:148-149` and change nothing else.
  - [x] **If it does not:** retain `pythonpath = [ "." ]` alone, and replace the comment with one stating explicitly that this entry declares the *tests package root*, not a source root, that `src/` is declared once in `[tool.hatch.build.targets.wheel]`, and that AD-7's rule is therefore satisfied. Record the decision and the evidence in Completion Notes.
  - [x] Either way, `"src"` must be gone. A test in Task 5 asserts it.

- [x] Task 4 — Prove the three runtimes agree (AC: #4)
  - [x] Verify `pixi run test` passes with the fallbacks removed.
  - [x] Verify `pixi run serve` starts (uvicorn, `config.asgi:application`, no `--app-dir`).
  - [x] Verify gunicorn with the uvicorn worker starts: `gunicorn config.asgi:application -k uvicorn_worker.UvicornWorker`. `gunicorn >=26.0,<27` and `uvicorn-worker >=0.4,<0.5` are declared only for `linux-64` and `osx-arm64` (`pixi.toml:85-91`); on win-64 this leg is unavailable and that is expected — it is why AD-18 keeps the six-combination harness Linux-only.
  - [x] Verify `pixi run manage check` (Django's system check) succeeds through `manage.py` with no `sys.path` insert.
  - [x] Record each verification in Completion Notes. A passing unit suite alone does not satisfy AC #4.

- [x] Task 5 — Tests (AC: #1, #2, #3, #4, #5)
  - [x] New `tests/unit/test_import_roots.py`. Read `manage.py`, `src/config/asgi.py` and `src/config/wsgi.py` as text and assert none contains `sys.path.insert` or `sys.path.append`.
  - [x] Parse `pyproject.toml` with `tomllib`: assert `"src"` is not in `[tool.pytest.ini_options].pythonpath` (and, if Task 3's preferred resolution held, that the key is absent entirely); assert `[tool.hatch.build.targets.wheel]` declares a `sources` remapping and no longer enumerates per-package entries.
  - [x] Parse `pixi.toml` with `tomllib`: assert no task's `cmd` contains `--app-dir` — this covers both `serve` and `serve-reload` and any task added later.
  - [x] New `tests/integration/test_import_resolution.py`, every test marked `@pytest.mark.integration`: launch a subprocess for each runtime and assert the import resolves identically. At minimum, `pixi run python -c "import config.asgi, django_service"` and a subprocess that starts uvicorn against `config.asgi:application` and is terminated after a successful bind. Skip the gunicorn leg on platforms where `gunicorn` is not installed by checking `importlib.util.find_spec("gunicorn")` and calling `pytest.skip` with a comment naming `pixi.toml:82-91` as the reason — never `@pytest.mark.skip`.
  - [x] Every subprocess must be terminated in teardown; the integration tests must leave no listening socket or child process behind.

## Dev Notes

### Architecture Constraints

- **AD-7 — Import roots are declared once, and every declaration site is named.** Rule, verbatim: "There are **six** import-root declaration sites in this repository and after this AD there is one. Removed: the `sys.path` insert in `manage.py` at **`:23-25`** (comment at `:22`) — an earlier revision cited `:24-26`; the `sys.path` insert in `asgi.py:18-20`; the `sys.path` insert in `src/config/wsgi.py:24-26`; `pyproject.toml [tool.pytest.ini_options] pythonpath` at `:149`; `--app-dir src` in the `serve` task at `pixi.toml:179`; and `--app-dir src` in the **`serve-reload`** task at `pixi.toml:186` — an earlier revision named only `serve`. Retained: `[tool.hatch.build.targets.wheel]`, which declares both roots via a `sources` remapping of `src/` and `src/django_apps/` (AD-6) — a directory-level construct, so adding an app needs no per-app edit and AD-6's graduation promise holds. **The retained site does not have that shape today**: `pyproject.toml:126-127` reads `packages = ["src/config", "src/django_service"]`, a per-package enumeration. Converting it is part of this AD, not a precondition of it. `uvicorn --app-dir` accepts one directory and is therefore never a declaration mechanism. **Removing the pytest `pythonpath` removes a non-source-root entry with it.** `:149` reads `pythonpath = ["src", "."]`; the `"."` entry is what makes `tests.factories` importable from `tests/conftest.py` under `--import-mode=importlib`, and the `sources` remapping covers `src/`, not the repository root. The removal is not executable until `tests.factories` resolves without it."
- **AD-7 Prevents:** "a second source root working under `pytest` and failing under `gunicorn` — the failure this rule exists to stop, which survives a rule that names only `sys.path`." This is why AC #4 requires all three runtimes verified and why `--app-dir` counts as a declaration site even though it contains no `sys.path` call.
- **AD-6 — `src/django_apps/` is a path root, not a package.** "`src/django_apps/` contains no `__init__.py`. An app at `src/django_apps/billing/` is imported and installed as `billing`, unqualified. Graduating it to a channel package changes its residency and never its import path." The directory-level requirement in AC #3 exists to keep this promise cheap — a per-package `packages = [...]` list would need an edit per app.
- **AD-5:** "The package name `django_service` is a constant, never parameterized." The `sources` remapping must not rename or relocate it.
- **AD-25:** `src/django_service/` is explicitly **not** a parameter. Do not introduce a substitution token in the wheel declaration.
- **Forbidden:** re-adding any removed site "just for local convenience"; adding a `.pth` file, a `conftest.py` `sys.path` manipulation, a `PYTHONPATH` export in `[activation.env]`, or a `setup.cfg`/`tox.ini` path entry. Every one of those is a second declaration site and defeats the AD.

### Forward context — this declaration grows, it does not fork

`epics.md:347`: "Story 1.6's single import-root site gains the `src/django_apps/` root in Epic 9 without gaining a second site." Epic 9 Story 9.2 adds `src/django_apps/` to the same `sources` table. Write the declaration and its comment so that addition is a one-line edit in one place.

### Source Tree — files to touch

| Path | NEW or UPDATE | What changes |
| --- | --- | --- |
| `pyproject.toml` | UPDATE | `[tool.hatch.build.targets.wheel]` at `:126-127`: `packages = [ "src/config", "src/django_service" ]` → a `sources` remapping of `src/`. Comment at `:125` rewritten. `[tool.pytest.ini_options] pythonpath = [ "src", "." ]` at `:149` and its comment at `:148`: `"src"` removed; `"."` per Task 3. Preserve `addopts` (`:142-146`), `minversion`, `testpaths`, `python_files`, `markers` (`:155-157`) and `[tool.hatch.build.targets.sdist]` (`:129-138`) unchanged. |
| `manage.py` | UPDATE | 37 lines. Sets `DJANGO_SETTINGS_MODULE` (`:11`), imports `execute_from_command_line` inside a try/except ImportError (`:13-20`), inserts `src/` on `sys.path` (`:22-25`), calls `configure_observability()` (`:29-31`), then `execute_from_command_line(sys.argv)` (`:33`). **Remove `:22-25` and the `Path` import at `:6`.** Preserve the settings default, the ImportError re-raise (it re-raises `from exc` — do not turn it into a swallow), the observability call and its comment at `:27-28`, and `import sys` (still used at `:33`). |
| `src/config/asgi.py` | UPDATE | Remove `:17-20` and the now-unused `import sys` (`:12`) and `from pathlib import Path` (`:13`). Preserve the settings setdefault (`:23`), `configure_observability()` (`:25-27`) and their ordering. Story 1.4 separately deletes `:32-33` and `:36-43`. |
| `src/config/wsgi.py` | UPDATE | 36 lines. Remove `:23-26` and the now-unused `import sys` (`:18`) and `from pathlib import Path` (`:19`). Preserve the `DJANGO_SETTINGS_MODULE` default of `config.settings.production` at `:27`, `configure_observability()` at `:29-31`, and `application = get_wsgi_application()` at `:36`. |
| `pixi.toml` | UPDATE | `serve` at `:179` and `serve-reload` at `:186` lose `--app-dir src`. `serve-reload` keeps `--reload --reload-dir src`. Every other task, comment and block unchanged. |
| `tests/unit/test_import_roots.py` | NEW | Asserts the removals and the single retained site. |
| `tests/integration/test_import_resolution.py` | NEW | Asserts identical resolution under pytest, uvicorn and gunicorn. |

**Line-number verification against the repository, 2026-08-15:**

| AD-7 cites | Actual location | Status |
| --- | --- | --- |
| `manage.py:23-25` | `manage.py:23-25` (comment at `:22`) | Holds. An earlier revision of AD-7 cited `:24-26`; that was corrected. |
| `asgi.py:18-20` | `src/config/asgi.py:18-20` (comment at `:17`) | Holds exactly. |
| `src/config/wsgi.py:24-26` | `src/config/wsgi.py:24-26` (comment at `:23`) | Holds. |
| `pyproject.toml [tool.pytest.ini_options] pythonpath` at `:149` | `pyproject.toml:149`, value `[ "src", "." ]` | Holds; the `"."` entry is not a source root and its removal is gated by AC #2 — see Task 3. |
| `--app-dir src` in the `serve` task, `pixi.toml:179` | `pixi.toml:179` | Holds. |
| `--app-dir src` in the `serve-reload` task, `pixi.toml:186` | `pixi.toml:186` | Holds. This is the sixth site; an earlier revision of AD-7 named only `serve`. |
| Retained: `[tool.hatch.build.targets.wheel]` `sources` remapping of `src/` and `src/django_apps/` | `pyproject.toml:126-127` uses `packages`, not `sources` | **Does not hold yet** — AD-7 says so itself; converting the retained site is part of this story, not a precondition of it. |

`src/django_apps/` does not exist today.

### Testing Requirements

- `tests/unit/test_import_roots.py`: text and TOML parsing only, milliseconds, no marker. Resolve repository paths from `Path(__file__).resolve().parents[2]`, matching `tests/unit/test_dependency_policy.py:11`.
- `tests/integration/test_import_resolution.py`: `@pytest.mark.integration` on every test (marker declared at `pyproject.toml:155-157`). Real subprocesses, so genuinely integration. Terminate every child in teardown; bind to an ephemeral port; leave no state behind.
- Assertions the ACs demand: no `sys.path` mutation in the three entrypoints; `"src"` absent from pytest `pythonpath`; `--app-dir` absent from every pixi task; the wheel target declares `sources`; `import config.*` and `import django_service` succeed identically under pytest, uvicorn and gunicorn.
- Coverage floor 90% including templates (AD-20); `--cov-fail-under=90` at `pixi.toml:196`. Note that `src/config/asgi.py` and `src/config/wsgi.py` are omitted from measurement (`pyproject.toml:166-167`), so their edits do not move the number — the new tests still count toward it.
- Test disposition (spine §Consistency Conventions): `tests/` mirrors `src/` and carries the disposition of what it covers; both files cover `core` paths and will be dispositioned in Epic 7.
- Done means `pixi run ci` exits 0 **and** the three runtime verifications in Task 4 are recorded.

#### Project Structure Notes

This story is the precondition for the Structural Seed's `src/django_apps/` — "tenant — path root, no `__init__.py` (AD-6)". That directory does not exist yet; Epic 9 creates it and adds it to the same `sources` table this story authors.

Variance: the Structural Seed shows `src/config/`, `src/django_service/` and `src/django_apps/` as siblings under `src/`. The first two exist and match. The wheel declaration today enumerates them individually, which is the variance this story closes.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.6]
- [Source: _bmad-output/planning-artifacts/epics.md:148] — AD-7 restated in the epic preamble with the **six** named sites and the conversion of the retained one.
- [Source: _bmad-output/planning-artifacts/epics.md:347] — the single site gains `src/django_apps/` in Epic 9 without gaining a second site.
- [Source: _bmad-output/planning-artifacts/epics.md:237] — collapsing the import-root declaration sites to one is a precondition for Epic 4's allowlist. *(That line still reads "five"; `epics.md:148` and AD-7 are the corrected count of six.)*
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-7]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-6]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-5]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-18] — gunicorn has no win-64 build.

## Dev Agent Record

### Agent Model Used

claude-opus-5

### Debug Log References

Commands run, in order, on `feature/1-6-import-roots` at baseline `c8b538f` (platform osx-arm64, Python 3.14.6, pytest 9.1.1, hatchling 1.31.0):

| # | Command | Purpose | Result |
| --- | --- | --- | --- |
| 1 | `pixi run build` (after the `sources` conversion) | Task 1 — the retained site builds | Wheel + sdist built |
| 2 | `pixi run -e dev python -c "<zipfile inspect dist/*.whl>"` | Task 1 — wheel top-level entries | `['config', 'django_15_factor_base-…dist-info', 'django_service']` — identical to the `packages` build |
| 3 | `pixi install -e default -e dev` | Task 1 — regenerate the editable finder | `_editable_impl_django_15_factor_base.pth` resolves to `<repo>/src` |
| 4 | `pixi run test` (pythonpath removed) | Task 3 — does `tests.factories` still resolve | 174 passed |
| 5 | `pytest … -o django_find_project=false` from `cwd=/tmp` with `--rootdir` | Task 3 — resolution with the repo root off `sys.path` | 8 passed, `repo_root_on_sys_path=False` |
| 6 | `pixi run manage check` | Task 4 | "System check identified no issues (0 silenced)." |
| 7 | `pixi run serve` | Task 4 | Bound `http://127.0.0.1:8000`, `GET /` → 200 |
| 8 | `pixi run -e default gunicorn config.asgi:application -k uvicorn_worker.UvicornWorker --bind 127.0.0.1:8124` | Task 4 | Bound, worker booted, `GET /` → 200 |
| 9 | `pixi run test` / `format` / `lint` / `typecheck` / `test-integration` | Inner loop | 187 unit passed; 91 files unchanged; ruff clean; mypy clean on 37 files; 64 integration passed, 6 skipped |
| 10 | `pixi run ci` | The gate | **Exit 0.** 257 passed, coverage 92.46% (floor 90%) |

Two failures surfaced mid-loop and were fixed rather than worked around:

- `RUF100` on `src/config/asgi.py` and `src/config/wsgi.py` — removing the `sys.path` insert left `# noqa: E402` unused, because an `os.environ` mutation is the one statement ruff lets precede a module-level import. Suppressions removed and replaced with a comment saying why the import is still below the settings default.
- `tests/unit/test_suite_policy.py::test_no_test_dodges_the_postgresql_gate` — see the exemption note below.

### Completion Notes List

**Task 1 — the retained site.** `[tool.hatch.build.targets.wheel]` now reads `only-include = [ "src" ]` / `sources = [ "src" ]`, replacing `packages = [ "src/config", "src/django_service" ]`. `only-include` is needed because hatchling's default wheel file selection looks for a package named after the project (`django_15_factor_base`), which does not exist here; both keys are directory-level, so adding an app needs no edit. Two roots, not three: `config` and `django_service` appear nowhere in the declaration. `src/django_apps/` was **not** added — it does not exist yet — and the comment at the declaration records that Epic 9 adds it to this same array.

One thing found while writing that comment and recorded rather than fixed here: hatchling normalises `sources` into a dict and sorts it **alphabetically ascending** (`hatchling/builders/config.py`, `sources` property), then `get_distribution_path` returns on the **first** matching prefix (same file, lines 740-749). `"src"` sorts before `"src/django_apps"`, so simply appending the second root would leave apps importable as `django_apps.billing` rather than `billing` — the opposite of AD-6. Epic 9 Story 9.2 has to verify that addition against the built wheel instead of assuming it. Noted in the comment at the declaration site so it is in front of whoever does it.

**Task 2 — the six removed sites.** All six gone: the `sys.path` inserts in `manage.py`, `src/config/asgi.py` and `src/config/wsgi.py` (with the now-unused `from pathlib import Path` in each, and the now-unused `import sys` in the two config modules; `manage.py` keeps `import sys` for `execute_from_command_line(sys.argv)`); `--app-dir src` from both the `serve` and `serve-reload` pixi tasks; and `"src"` from the pytest `pythonpath`. `serve-reload` keeps `--reload-dir src` — a file-watch target, not a declaration — with a comment saying so.

**Task 3 — decision: the preferred resolution held. The `pythonpath` setting is removed entirely; `pythonpath = [ "." ]` was *not* retained.**

Evidence, in the order it was gathered:

1. With `pythonpath` deleted outright, `pixi run test` passed 174/174 — including `tests/conftest.py`'s `from tests.factories import UserFactory` and `tests/unit/test_coverage_policy.py`'s ten `from tests.coverage_policy import …`, all of which fail loudly if the `tests` package does not resolve.
2. That alone did not distinguish resolution from coincidence, because two things were still putting the repository root on `sys.path` under `pixi run test`: pytest-django's `django_find_project` (`pytest_django/plugin.py:228`, on by default, finds `manage.py` and inserts its directory) and the invocation's working directory. So the decisive run removed both — `pytest <abs paths> -c <abs pyproject> --rootdir=<repo> -o django_find_project=false` executed from `cwd=/tmp`. A probe module asserted the conditions and the outcome together: `repo_root_on_sys_path=False`, `tests.__spec__.origin=<repo>/tests/__init__.py`, `tests.__path__=['<repo>/tests']`, `factories_file=<repo>/tests/factories.py`, 8 passed.
3. The mechanism, read off `_pytest/pathlib.py`: under `--import-mode=importlib`, `import_path` resolves `tests/conftest.py` to the canonical module name `tests.conftest` (walking up while `__init__.py` exists — `tests/__init__.py` is present) and hands it to `_import_module_using_spec`, which imports the **parent package first**, by file location, via `importlib.util.spec_from_file_location` and explicitly "without touching `sys.path`". `tests` therefore lands in `sys.modules` with a real `__spec__` and a real `__path__`, and `tests.factories` is found through that `__path__`. `pythonpath` was never what made this work under importlib mode; it was a redundant second route.

So AC #2 is satisfied by removal, not by retention, and no non-source-root entry survives. `test_pytest_declares_no_pythonpath_at_all` pins it and carries the mechanism in its docstring.

**Deviation from the story's Source Tree table: `tests/unit/test_suite_policy.py` was modified.** That module (Story 1.2, AC #2) bans `pytest.skip(...)` outright across the whole suite, which collides head-on with this story's Task 5 requirement to skip the gunicorn leg at runtime via `importlib.util.find_spec`. Its own docstring names the escape hatch — "if one of these ever needs to be legitimate — a genuinely platform-specific test, say — that is a deliberate decision to record in the story that makes it" — so the decision is recorded rather than the ban weakened: a `RECORDED_EXEMPTIONS` table keyed by module **and** by the exact evasion, exempting `pytest.skip(...)` in `integration/test_import_resolution.py` and nothing else, with the win-64 reasoning (`pixi.toml` `[target.*.dependencies]`, AD-18) beside it. A second test, `test_every_recorded_exemption_still_describes_the_file`, fails if the entry ever stops matching, so the exemption cannot outlive the skip it was granted for.

**Task 4 — the three runtimes, verified rather than inferred.** Run against the finished tree, not an intermediate one:

| Verification | Result | Observed |
| --- | --- | --- |
| `pixi run test` | **PASS** | `187 passed in 0.35s` |
| `pixi run serve` (uvicorn, no `--app-dir`) | **PASS** | `INFO: Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)`; `GET /` → HTTP 200; process terminated, no listener left |
| `gunicorn config.asgi:application -k uvicorn_worker.UvicornWorker` | **PASS** | `Listening at: http://127.0.0.1:8124`, `Using worker: uvicorn_worker.UvicornWorker`, `Booting worker with pid: 46314`, `Application startup complete.`; `GET /` → HTTP 200; terminated, no listener left |
| `pixi run manage check` | **PASS** | `System check identified no issues (0 silenced).` |

**Task 5 — tests.** `tests/unit/test_import_roots.py` (10 tests, no marker, text + `tomllib` only) asserts: no `sys.path.insert`/`append` in any of the three entrypoints (parameterized, so a failure names the file); `"src"` absent from the pytest `pythonpath`; the `pythonpath` key absent entirely; the wheel target declares `sources` containing `src`; the wheel target declares no `packages` and no `sources` entry named `config` or `django_service`; no pixi task command in `[tasks]` or any `[feature.*.tasks]` contains `--app-dir`; and both serve tasks still serve `config.asgi:application` with `--reload-dir src` intact.

`tests/integration/test_import_resolution.py` (4 tests, each explicitly `@pytest.mark.integration`) runs the probe `import config.asgi, django_service` in-process, in a bare interpreter subprocess, under uvicorn, and under gunicorn + `uvicorn_worker.UvicornWorker`. Every subprocess runs with `PYTHONSAFEPATH=1` and `PYTHONPATH` cleared, so neither the working directory nor an inherited entry can supply the packages — the editable install generated from the retained `sources` declaration is the only thing left that can, which is what makes these tests an assertion about AC #3 and not just about the servers. Servers bind an OS-assigned free port on 127.0.0.1; `_wait_for_bind` polls the socket and fails with the captured server output if the process exits first, so an `ImportError` reads as an `ImportError` rather than as a timeout; a `contextlib.contextmanager` terminates (then kills) every child in teardown. gunicorn is started with `--no-control-socket` because gunicorn 26 otherwise creates `~/.gunicorn/gunicorn.ctl`, which is state this suite has no business creating. Verified afterwards: no `uvicorn`/`gunicorn` process and no `~/.gunicorn` socket left behind. Whole file runs in ~3s.

**Gate.** `pixi run ci` exits **0**: pre-commit clean, build succeeds, mypy clean over 37 files, ruff clean, `257 passed`, coverage **92.46%** against the 90% floor. `pixi.lock` is unchanged.

---

### Review patch pass — 21 findings applied in place

Three adversarial reviews of the above landed 21 defects, all triaged as *patch*. Nothing was reverted or redesigned. What changed and why:

**The gunicorn leg could not fail (the worst of them).** `_wait_for_bind` asserted only that a TCP connection was accepted. gunicorn's arbiter creates its listening sockets in `Arbiter.start()` **before** forking, and without `--preload` the application is imported in the *worker* — so an unimportable `config.asgi` bound the port and the test passed green. That is precisely the "works under pytest, fails under gunicorn" failure AD-7 exists to stop, sitting inside the test written to prove it does not happen. Demonstrated rather than argued: with the gunicorn command pointed at `config.does_not_exist:application`, the old shape (no `--preload`, bind-only) **passed**; the new shape fails with `Failed: server exited with 1 before binding to <port>: ModuleNotFoundError: No module named 'config.does_not_exist'`. Both server legs now also issue a real HTTP request and assert its status.

The path requested is one no URLconf routes, and the assertion is `404`. A 404 is not a weaker proof here: Django reaches it only after importing `config.urls`, which imports `django_service.users.urls` through `include()`, so a 404 proves both packages resolved *in the server process* while an unresolvable one gives a 500. A routed path answering 200 proves the same thing but runs the view inside the transaction `ATOMIC_REQUESTS` opens, which creates `db.sqlite3` in the repository root under the local settings these servers boot with — state this suite is required to leave behind none of.

**The server subprocesses were running under the wrong settings.** `_subprocess_env` popped only `PYTHONPATH`, so every server inherited the `DJANGO_SETTINGS_MODULE=config.settings.test` pytest-django writes from `--ds`, making each entrypoint's `os.environ.setdefault(..., "config.settings.local")` — the very line the new comment in `asgi.py` is about — a no-op in these tests. It is popped too. The uvicorn test's docstring claimed "`pixi run serve` is this command; the port is the only difference", which was false three ways (settings module, `dev` vs `default` environment, `python -m uvicorn` vs the console script); it now states what the test actually proves.

**The stdout pipe was never drained.** `stdout=PIPE, stderr=STDOUT` with no reader until exit: a server emitting more than one pipe buffer before binding blocks on write forever, and the symptom is the 60s "did not bind" timeout — the exact misdiagnosis `_wait_for_bind` exists to prevent. Output is now drained on a daemon thread into a bounded 400-line buffer (`_ServerProcess`), and both failure messages — early exit and timeout — carry it.

**`_terminate` orphaned gunicorn workers.** `process.kill()` on the arbiter left forked workers alive holding the listening socket. Servers now start with `start_new_session=True` and the escalation path kills the process *group* (`os.killpg(os.getpgid(pid), SIGKILL)`, guarded for platforms without it); the post-kill `wait()` is wrapped in `contextlib.suppress(subprocess.TimeoutExpired)` so it cannot raise out of the `finally` and mask the real outcome.

**Smaller integration-test fixes.** The plain-interpreter probe parsed stdout with `.split()`, which breaks on any repository path containing a space, and `all(...)` over an empty list is True so it passed vacuously if the subprocess printed nothing — now `splitlines()` with the count asserted first. The gunicorn skip checks `uvicorn_worker` as well as `gunicorn`, so a missing worker class reads as a missing dependency rather than as a failed server. The one-line import probe got its own `PROBE_TIMEOUT_SECONDS` instead of borrowing the 60s bind timeout.

**`config.wsgi` was imported by nothing in the entire suite.** Its `sys.path` insert and `# noqa: E402` were removed with only a text-absence assertion behind the edit, and `pyproject.toml` omits it from coverage — so an import-time break there would ship silently while `WSGI_APPLICATION = "config.wsgi.application"` is what `runserver` loads. `test_the_wsgi_entrypoint_imports_and_exposes_an_application` now imports it and asserts `application` is callable.

**Nothing inspected the built artifact.** `test_the_built_wheel_ships_the_source_tree_at_its_root` builds a wheel into `tmp_path` (`--no-isolation`, so it uses the conda-forge hatchling already present) and asserts its top-level entries are exactly the packages under `src/`. This is what would catch `only-include` or `sources` being dropped — neither of which makes the build fail. Cost measured: **0.26 s**, stable across repeated runs; it is cheap enough to ship, and it is the only test in the repository that reads the result of the one retained declaration rather than the declaration itself.

**`_task_commands` did not scan every task, despite its docstring.** It handled `[tasks]` and `[feature.*.tasks]` with a *string* `cmd` only. pixi also accepts `cmd` as an argv array, and tasks live under `[target.<platform>.tasks]` and `[feature.<name>.target.<platform>.tasks]` — `serve = { cmd = ["uvicorn", "config.asgi:application", "--app-dir", "src"] }` sailed straight through. It now walks for every nested `tasks` table (the pattern `tests/unit/test_asgi_surface.py::_server_task_commands` already uses) and joins list-form `cmd`.

**Four of the five mechanisms the story forbids were unguarded.** The Dev Notes ban a `.pth` file, a `conftest.py` `sys.path` manipulation, a `PYTHONPATH` export in `[activation.env]` and a `setup.cfg`/`tox.ini` entry; only `--app-dir` and three hard-coded entrypoints were checked. `src/config/celery_app.py` — a process entrypoint too — was unscanned, and a `PYTHONPATH = "src"` three lines above the tasks the test *did* scan would have passed everything. The frozen `ENTRYPOINTS` triple is replaced by a pruned walk of every `.py` in the repository (excluding `.pixi/`, `.git/`, generated trees and the vendored agent tooling `[tool.ruff] extend-exclude` already disclaims), with a guard asserting the three files AD-7 names are still in the scan. Added: no `PYTHONPATH` in any `activation.env` or task `env` table, no committed `.pth`, no `setup.cfg`/`tox.ini`/`pytest.ini` at the root. Pruning rather than filtering keeps it a unit test — the whole file runs in well under a second.

**The `sys.path` check was textual and overclaimed.** Its docstring said "a rewritten-but-equivalent insert ... still fails here", which was false: `sys.path += [...]`, `sys.path[0:0] = [...]`, `sys.path.extend(...)` and `site.addsitedir(...)` all pass a substring search. It now parses the AST, as its sibling `tests/unit/test_suite_policy.py` does and for the same reason (prose about the prohibition must not itself be an offence), and the docstring states honestly what still escapes it — an alias or an `exec`. Verified by injecting `sys.path += ["/tmp/x"]` into `src/config/celery_app.py`: red, `56: augmented assignment to sys.path`.

**`test_the_serve_tasks_still_serve_the_asgi_application` pinned whole command strings**, so adding `--host 0.0.0.0` would break a test whose stated purpose is that the task "still serves the ASGI application". It now asserts the load-bearing parts: `config.asgi:application` present, `--app-dir` absent, `--reload-dir src` still present on `serve-reload`. Unguarded dict indexing that produced `KeyError` instead of an assertion failure is guarded.

**pytest-django was re-supplying the declaration this story deleted.** `django_find_project` defaults to **true**, and `_add_django_project_to_path` does `sys.path.insert(0, project_dir)` — so under the shipped configuration the repository root was on `sys.path` on every test run: a live seventh declaration site, with AC #2's "recorded rather than left to coincidence" satisfied only inside a throwaway probe. `django_find_project = false` is now declared in `[tool.pytest.ini_options]` with the reasoning beside it, and `test_pytest_django_declares_no_import_root` pins it. **It broke nothing** — 195 unit and 72 integration tests pass with it off, which is the point of the change. Demonstrated: with the plugin's insert forced back on, `sys.path` carries the repository root **twice**; with it off, the pytest-django entry is gone.

**Recorded, not fixed — an eighth site that no patch in this pass covers.** While proving the above, `sys.path` was instrumented under a real run. With `django_find_project` off, the repository root is *still* on `sys.path`, and the traceback names celery: `celery/fixups/django.py:79` does `sys.path.insert(0, os.getcwd())` inside `DjangoFixup.install()`, which runs whenever a `Celery` app is constructed with Django settings present. `src/config/__init__.py` imports `celery_app`, so **every** import of `config` — under pytest, uvicorn, gunicorn and `manage.py` alike — puts the current working directory on `sys.path`. It declares the *invocation directory*, not `src/`, and it is a third-party library's behaviour rather than a line in this repository, so it is neither one of AD-7's six sites nor removable by editing this tree. It is written down here because AD-7's claim is "one declaration site" and this is the one thing left that can still put a directory on the path behind everyone's back. Options for whoever takes it: `app.set_default()`/`DjangoFixup` avoidance, or `CELERY_SKIP_DJANGO_FIXUP` — both are design decisions, not patches.

**The `RECORDED_EXEMPTIONS` table exempted far more than its comment claimed.** The filter compared only the evasion *description* after stripping the line number, so **every** `pytest.skip(...)` in `integration/test_import_resolution.py` was permitted — present and future, for any reason. The next developer adding "skip if no Postgres" to that file would have got it silently, which is the exact failure Story 1.2's ban exists to make loud. The table is now keyed by module, form **and count** (`{"pytest.skip(...)": 1}`), spent per occurrence: a second skip in that file fails the gate. `test_every_recorded_exemption_still_describes_the_file` gained the emptiness guard its sibling parametrize already had, and now asserts the exempted module is one `_test_modules()` actually collects — a rename would otherwise leave the exemption green while the file it licenses goes unscanned. The module docstring and `test_no_test_dodges_the_postgresql_gate`'s docstring, which both described an absolute ban with no mention of the table sitting above them, say so now.

**The comment at the retained site cited third-party line numbers.** `hatchling/builders/config.py:740-749` drifts on any upgrade allowed by `>=1.27,<2`, and this repository has already been bitten by a stale citation (AD-7 itself shipped a wrong `manage.py:24-26`). The Epic 9 warning keeps its substance and now cites the behaviour and the option names instead. The same block acknowledges the `.pth` tension the story left unaddressed: what the retained site *generates* is `.pixi/envs/*/site-packages/_editable_impl_django_15_factor_base.pth` containing `<repo>/src`, and a build artifact regenerated from the one declaration is not the hand-written second declaration the Dev Notes forbid. `only-include = [ "src" ]` is documented as load-bearing and asserted, since dropping it still builds while quietly changing what ships.

**The comment added to `asgi.py` and `wsgi.py` was factually wrong.** It claimed "an `os.environ` mutation is the one statement ruff allows to precede an import". Checked against this project's own ruff (0.16.2): a bare `sys.path.insert(0, "x")` as the only pre-import statement passes E402 **clean**, as do a docstring, a `__future__` import and a conditional block; what actually tripped E402 in the old code was the plain `SRC_DIR = ...` assignment. As written the comment taught a future maintainer something false and implied lint would catch a re-added insert, which it would not. Rewritten to say what is true and to name `tests/unit/test_import_roots.py` as the thing that would catch it.

**`manage.py` lost its self-sufficiency and its error message did not keep up.** The `try/except ImportError` guarded only the Django import and advised about `PYTHONPATH`, while `from config.observability import configure_observability` was unguarded — so without an editable install `python manage.py` failed with a bare `ModuleNotFoundError: config` and no guidance, in a repository whose whole purpose is to be cloned. It is guarded now, naming `pixi install`. The Django `ImportError` re-raise is untouched and still re-raises `from exc`.

**Verified after the pass.** `pixi run test-integration` leaves no `uvicorn` or `gunicorn` process, no listening socket and no `~/.gunicorn` directory (removed and confirmed not recreated — `--no-control-socket` holds). The one process found listening on the machine belongs to an unrelated project (`django-python-generate-sbom`, running since July).

### File List

| Path | NEW or UPDATE |
| --- | --- |
| `pyproject.toml` | UPDATE — `[tool.hatch.build.targets.wheel]` converted to `only-include`/`sources`; `[tool.pytest.ini_options] pythonpath` and its comment removed. *Patch pass:* `django_find_project = false` added with its reasoning; the wheel comment re-cited by behaviour rather than by hatchling line numbers, and extended to acknowledge the generated `.pth` and the load-bearing `only-include` |
| `manage.py` | UPDATE — `sys.path` insert, its comment and `from pathlib import Path` removed. *Patch pass:* the `config.observability` import guarded with a message naming the editable install |
| `src/config/asgi.py` | UPDATE — `sys.path` insert, its comment, `import sys`, `from pathlib import Path` and the now-unused `# noqa: E402` removed. *Patch pass:* the E402 comment rewritten — its claim about what ruff allows was false |
| `src/config/wsgi.py` | UPDATE — same removals as `asgi.py`, and the same comment correction |
| `pixi.toml` | UPDATE — `--app-dir src` removed from the `serve` and `serve-reload` tasks |
| `tests/unit/test_suite_policy.py` | UPDATE — `RECORDED_EXEMPTIONS` table plus `test_every_recorded_exemption_still_describes_the_file`; see the deviation note above. *Patch pass:* the table keyed by count so it exempts one occurrence rather than a form for a whole file; emptiness guard added; both docstrings updated to mention the table |
| `tests/unit/test_import_roots.py` | NEW — *patch pass:* repository-wide AST scan replacing the frozen entrypoint triple, task scan covering array-form `cmd` and `[target.*.tasks]`, plus assertions for `PYTHONPATH`, committed `.pth`, root config files, `only-include` and `django_find_project` |
| `tests/integration/test_import_resolution.py` | NEW — *patch pass:* `--preload` and an asserted HTTP status on both server legs, `DJANGO_SETTINGS_MODULE` cleared, output drained on a thread, process-group kill, and two new tests (`config.wsgi` import, built-wheel contents) |
| `README.md` | UPDATE — *patch pass:* the Layout section said `src/` "is on `sys.path`", the mechanism this story deleted. It now names `[tool.hatch.build.targets.wheel]` as the one declaration site |
| `docs/index.md` | UPDATE — *patch pass:* the same correction in the layout tree and its prose, plus the list of what no longer declares the root |
| `_bmad-output/implementation-artifacts/1-6-import-roots-are-declared-in-exactly-one-place.md` | UPDATE — status, task checkboxes, this record |

## Review Triage Log

### 2026-08-16 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 22: (high 1, medium 12, low 9)
- defer: 1: (high 0, medium 1, low 0)
- reject: 7: (high 0, medium 0, low 7)
- addressed_findings:
  - `[high]` `[patch]` The gunicorn leg could not fail. gunicorn's arbiter binds its listening sockets before forking workers, and without `--preload` the app is imported in the worker — so an unimportable `config.asgi` bound the port and the test passed green, defeating the exact "works under pytest, fails under gunicorn" failure AD-7 exists to stop. Added `--preload` and replaced the bare bind poll with an asserted HTTP status on both server legs. Proven red against `config.does_not_exist:application`.
  - `[medium]` `[patch]` Server subprocesses inherited `DJANGO_SETTINGS_MODULE=config.settings.test` from pytest-django, so `asgi.py`'s `setdefault` — the line the new comment is about — was a no-op in every leg. Cleared it; corrected the docstring's false `pixi run serve` equivalence claim.
  - `[medium]` `[patch]` pytest-django's `django_find_project` re-inserted the repository root on `sys.path` on every test run — a live seventh declaration site AC #2 was blind to. Set `django_find_project = false` and asserted it.
  - `[medium]` `[patch]` `only-include = ["src"]` was load-bearing but unasserted, and nothing in the suite inspected the built artifact. Asserted the key, and added an integration test that builds the wheel and checks its top-level entries.
  - `[medium]` `[patch]` `_task_commands` missed array-form `cmd` and `[target.*.tasks]` tables, so `--app-dir` in list form sailed through the AC #5 check. Now walks every nested `tasks` table.
  - `[medium]` `[patch]` Four of the five mechanisms the story forbids were unguarded and `ENTRYPOINTS` was a frozen triple missing `celery_app.py`. Replaced with a repository-wide AST scan plus assertions for `PYTHONPATH` in activation/task env, committed `.pth` files, and root `setup.cfg`/`tox.ini`/`pytest.ini`.
  - `[medium]` `[patch]` `config.wsgi` was imported by nothing in the suite — its edit stood on a text-absence assertion alone while `WSGI_APPLICATION` points at it. Added a test that imports it and asserts `application` is callable.
  - `[medium]` `[patch]` The server subprocess stdout pipe was never drained (deadlock, misreported as a bind timeout) and failure messages carried no server output. Drained on a daemon thread into a bounded buffer; both failure paths now report it.
  - `[medium]` `[patch]` `_terminate` orphaned gunicorn workers on the kill path, contradicting its own docstring, and a second `wait()` could raise out of `finally`. Process-group kill plus suppression.
  - `[medium]` `[patch]` The E402 comment added to `asgi.py` and `wsgi.py` was factually wrong about what ruff permits before an import, and implied lint would catch a re-added `sys.path` insert — it would not. Rewritten.
  - `[medium]` `[patch]` `RECORDED_EXEMPTIONS` exempted *every* `pytest.skip` in the named file rather than the one occurrence its own comment claimed, silently reopening the ban Story 1.2 exists to enforce. Keyed by count; both docstrings updated to disclose the table.
  - `[medium]` `[patch]` `README.md` and `docs/index.md` still described `src/` as being placed on `sys.path` — the mechanism this story deleted — and named no declaration site. Both corrected.
  - `[low]` `[patch]` The plain-interpreter probe used `.split()` (breaks on repository paths containing a space, in a template meant to be cloned anywhere) and `all()` over a possibly-empty list (vacuous pass). Now `splitlines()` with the count asserted.
  - `[low]` `[patch]` `test_no_entrypoint_mutates_sys_path` was a substring search whose docstring claimed equivalence-detection; `sys.path +=`, slice assignment, `.extend` and `site.addsitedir` all escaped it. Converted to an AST check, with the residual escapes stated honestly.
  - `[low]` `[patch]` The serve-task test pinned whole command strings, so adding `--host` would break a test about `--app-dir`. Asserts the load-bearing parts only.
  - `[low]` `[patch]` The wheel comment cited `hatchling/builders/config.py:740-749` under a `>=1.27,<2` pin — the same stale-line-citation failure AD-7 itself already shipped once. Re-cited by behaviour and option name.
  - `[low]` `[patch]` The generated `_editable_impl_*.pth` was unacknowledged against the story's ban on `.pth` files. One sentence at the declaration site distinguishes a generated artifact of the one declaration from a hand-written second one.
  - `[low]` `[patch]` Unguarded dict indexing (`wheel["sources"]`, `commands["serve"]`) raised `KeyError` instead of failing the assertion.
  - `[low]` `[patch]` The gunicorn skip checked only `gunicorn`, so a missing `uvicorn_worker` would surface as a startup failure. Both specs checked.
  - `[low]` `[patch]` `BIND_TIMEOUT_SECONDS` (60s, sized for a cold Django + OTel server start) was reused as the timeout for a one-line import probe. Separate constant.
  - `[low]` `[patch]` `test_every_recorded_exemption_still_describes_the_file` had no emptiness guard, unlike its protected sibling, and did not verify the exempted module is actually collected. Both added.
  - `[low]` `[patch]` `manage.py` imported `config.observability` unguarded, so without an editable install it now failed with a bare `ModuleNotFoundError: config` and no guidance — in a repository whose purpose is to be cloned. Guarded with a message naming `pixi install`; the Django `ImportError` re-raise left untouched.

**Deferred (1):** hatchling sorts `sources` alphabetically and applies the first matching prefix, so adding `src/django_apps` beside `src` shadows it and would make apps import as `django_apps.billing` rather than `billing` — the opposite of AD-6. Not caused by this story (the directory does not exist), but it invalidates the assumption Epic 9 Story 9.2 will act on. Recorded in the declaration-site comment and in `deferred-work.md`.

**Rejected (7):** redundant `@pytest.mark.integration` decorators (the story requires them explicitly); the `_free_port` bind race (documented, standard); `--no-control-socket` availability (gunicorn is pinned `>=26.0,<27`); mypy resolving `tests.factories` (the gate passes); the `resolve(strict=True)` removal; the pytest-runtime leg being a near no-op; and the observation that the diff excluded the story file itself (excluded deliberately — it is the record, not the code).

## Auto Run Result

Status: `done`

### Implemented change

Six import-root declaration sites collapsed to one. The `sys.path` inserts in `manage.py`, `src/config/asgi.py` and `src/config/wsgi.py`, `--app-dir src` in the `serve` and `serve-reload` pixi tasks, and the pytest `pythonpath` setting are all gone. The retained site — `[tool.hatch.build.targets.wheel]` — was converted from the per-package enumeration `packages = ["src/config", "src/django_service"]` to a directory-level `only-include`/`sources` remapping of `src/`, so adding an app needs no edit there. The review pass additionally removed a seventh site nobody had counted: pytest-django's `django_find_project`, which was re-inserting the repository root on `sys.path` on every test run.

### Files changed

| Path | One-line description |
| --- | --- |
| `pyproject.toml` | Wheel target converted to `only-include`/`sources`; `pythonpath` removed; `django_find_project = false` added |
| `manage.py` | `sys.path` insert removed; the `config.observability` import guarded with editable-install guidance |
| `src/config/asgi.py` | `sys.path` insert, `import sys`, `Path` and the stale `# noqa: E402` removed |
| `src/config/wsgi.py` | Same removals |
| `pixi.toml` | `--app-dir src` removed from `serve` and `serve-reload`; `--reload-dir src` kept (a file-watch target, not a declaration) |
| `tests/unit/test_import_roots.py` | NEW — repository-wide AST scan for `sys.path` mutation, nested pixi task scan, and assertions for every forbidden mechanism |
| `tests/integration/test_import_resolution.py` | NEW — pytest, plain interpreter, uvicorn and gunicorn legs, plus `config.wsgi` import and built-wheel contents |
| `tests/unit/test_suite_policy.py` | Recorded-exemption table for the one platform-conditional skip, keyed by count and self-invalidating |
| `README.md`, `docs/index.md` | Layout sections no longer describe the deleted `sys.path` mechanism |

### Review findings

22 patches applied (1 high, 12 medium, 9 low), 1 deferred, 7 rejected. No intent gaps and no spec defects — every finding was localized hardening of code written in this run, so no loopback was needed. The high-severity one is worth naming: the gunicorn leg of the three-runtime proof could not fail, because gunicorn binds its listening socket before forking the worker that imports the application. The test that existed to catch "works under pytest, fails under gunicorn" passed green on exactly that failure. Fixed with `--preload` plus an asserted HTTP status, and demonstrated red against an unimportable module before being accepted.

### Verification performed

- `pixi run ci` → exit 0. 267 passed, coverage 92.46% against the 90% floor. Run twice, once after the docs correction.
- `pixi run test` → 195 unit tests pass.
- `pixi run serve` → uvicorn binds `127.0.0.1:8000`, `GET /` returns 200, terminates cleanly.
- `gunicorn config.asgi:application -k uvicorn_worker.UvicornWorker` → binds, `GET /` returns 200, terminates cleanly.
- `pixi run manage check` → "System check identified no issues (0 silenced)."
- `pixi run -e dev mkdocs build --strict` → clean.
- After `pixi run test-integration`: no stray `uvicorn`/`gunicorn` process, no listening socket, no `~/.gunicorn` directory.

### Residual risks

- **Epic 9 will hit the deferred `sources` shadowing defect.** Hatchling applies the first matching path prefix, so appending `src/django_apps` beside `src` yields `django_apps.billing` rather than the unqualified `billing` AD-6 promises — silently, with a green build. Recorded at the declaration site and in `deferred-work.md`.
- **Celery's Django fixup still puts the invocation directory on `sys.path`.** `DjangoFixup.install()` does `sys.path.insert(0, os.getcwd())`, and `src/config/__init__.py` imports `celery_app`, so this happens in every runtime. It declares the working directory rather than a source root and is third-party behaviour, so it is neither one of AD-7's six sites nor removable here — but it is the one remaining thing that can put a directory on the path unannounced.
- **The four new server subprocess tests are a new flake surface** on the three-OS integration matrix. They drain output on a thread, kill by process group, and carry a 60s bind budget, but they are the first tests in this suite to spawn servers and bind ports.
