# Story 1.6: Import roots are declared in exactly one place

Status: ready-for-dev

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

- [ ] Task 1 — Convert the retained site to a `sources` remapping first (AC: #3, #4)
  - [ ] `pyproject.toml:126-127` currently reads `[tool.hatch.build.targets.wheel]` / `packages = [ "src/config", "src/django_service" ]` with the comment at `:125` "src/ is the import root; config and django_service are both top-level packages." `packages` is a per-package enumeration; AD-7 requires a **directory-level** `sources` remapping so that adding an app needs no per-app edit.
  - [ ] Replace it with a `sources`-based declaration that maps `src/` onto the wheel root — hatchling's `[tool.hatch.build.targets.wheel] sources` key. Determine the exact key spelling and value shape against the installed `hatchling >=1.27,<2` (`pixi.toml:79`) rather than guessing; verify with `pixi run build` and by inspecting the produced wheel's top-level entries.
  - [ ] The editable install is what puts the root on `sys.path` at runtime: `pixi.toml:98-99` declares `django-15-factor-base = { path = ".", editable = true }` and `pixi.toml:103-104` sets `no-build-isolation` for it. Hatchling's editable install writes a finder honouring `sources`, which is why the `sys.path` inserts become removable. **Do this task before Task 2** — remove the fallbacks only once the one retained site actually works.
  - [ ] Add `src/django_apps/` to the remapping only if it exists. It does **not** exist today. AD-7 states the retained site "declares both roots via a `sources` remapping of `src/` and `src/django_apps/`", and `epics.md:347` records that Story 1.6's single site "gains the `src/django_apps/` root in Epic 9 without gaining a second site." **Forward context, not this story's acceptance condition:** declare only `src/` now, and add a comment at the declaration recording that Epic 9 adds the second root to this same table.
  - [ ] **Two roots, not three.** The finished remapping declares `src/` and `src/django_apps/` and nothing else. `config` and `django_service` are packages *within* `src/` and must not reappear as their own entries — reinstating them beside `src/` is the per-package enumeration this task exists to remove, and it would make the "no per-app edit" promise false again.
  - [ ] After the change, run `pixi install` (or the project's re-install path) so the editable finder is regenerated. A stale `.pixi` environment will make Task 2 look like it worked when it did not.

- [ ] Task 2 — Remove the six fallback declaration sites (AC: #1, #5)
  - [ ] `manage.py` — remove the comment at `:22` ("src/ is the import root: config, users and contrib are top-level packages.") and the insert at `:23-25` (`src_dir = Path(__file__).parent.resolve() / "src"` / `if str(src_dir) not in sys.path:` / `sys.path.insert(0, str(src_dir))`). Then remove the now-unused `import sys` at `:5` **only if** `sys` is otherwise unused — it is still used by `execute_from_command_line(sys.argv)` at `:33`, so `import sys` stays. Remove `from pathlib import Path` at `:6`, which becomes unused. **AD-7 names `manage.py:23-25` with its comment at `:22`, which is where the insert actually is; an earlier revision of the AD cited `:24-26` and was wrong by one line.**
  - [ ] `src/config/asgi.py` — remove the comment at `:17` and the insert at `:18-20` (`SRC_DIR = Path(__file__).resolve(strict=True).parent.parent` / `if str(SRC_DIR) not in sys.path:` / `sys.path.insert(0, str(SRC_DIR))`). Then remove `import sys` at `:12` and `from pathlib import Path` at `:13`, both of which become unused. **This matches AD-7's cited `asgi.py:18-20` exactly.** Story 1.4 owns the deletion of the scope dispatcher in the same file; if both land together, keep the hunks separate and attribute them.
  - [ ] `src/config/wsgi.py` — remove the comment at `:23` and the insert at `:24-26`, then remove `import sys` at `:18` and `from pathlib import Path` at `:19`, both of which become unused. AD-7 names `wsgi.py` without a line range; the range is `:23-26` including its comment.
  - [ ] `pixi.toml:179` — remove `--app-dir src` from the `serve` task, leaving `uvicorn config.asgi:application`.
  - [ ] `pixi.toml:186` — **the sixth site.** AD-7 names it explicitly; an earlier revision named only `serve`. The `serve-reload` task reads `uvicorn config.asgi:application --app-dir src --reload --reload-dir src`. Remove `--app-dir src` here too; AC #5 says `--app-dir` "is never used as a declaration mechanism", which admits no per-task exception. **Keep `--reload-dir src`** — that is a file-watch target, not an import-root declaration, and removing it would break autoreload.
  - [ ] `pyproject.toml:149` — the pytest setting reads `pythonpath = [ "src", "." ]` with the comment at `:148` `# "src" makes config/ and django_service/ importable; "." makes tests.factories importable.` Remove `"src"`. See Task 3 for the `"."` entry.

- [ ] Task 3 — Resolve the `"."` pythonpath entry deliberately (AC: #1, #2)
  - [ ] AC #1 says "the pytest `pythonpath` setting ... [is] removed", and AD-7 names `pyproject.toml` `[tool.pytest.ini_options] pythonpath` as one of the six sites. AD-7 also states the consequence in its own words: "**Removing the pytest `pythonpath` removes a non-source-root entry with it** ... the removal is not executable until `tests.factories` resolves without it." AC #2 is that condition, and it is an acceptance condition of this story rather than a note. The `"."` entry is not a *source* root — it makes `tests.factories` importable, and `tests/` is a package (`tests/__init__.py` exists). `tests/conftest.py` does `from tests.factories import UserFactory`; `tests/unit/` and `tests/integration/` also carry `__init__.py`. `pyproject.toml:145` sets `--import-mode=importlib`.
  - [ ] **Preferred resolution:** remove the `pythonpath` setting entirely and make the tests package resolve without it — verify whether pytest ≥9 with `--import-mode=importlib` and `tests/__init__.py` present resolves `tests.factories` from rootdir on its own. If it does, delete lines `:148-149` and change nothing else.
  - [ ] **If it does not:** retain `pythonpath = [ "." ]` alone, and replace the comment with one stating explicitly that this entry declares the *tests package root*, not a source root, that `src/` is declared once in `[tool.hatch.build.targets.wheel]`, and that AD-7's rule is therefore satisfied. Record the decision and the evidence in Completion Notes.
  - [ ] Either way, `"src"` must be gone. A test in Task 5 asserts it.

- [ ] Task 4 — Prove the three runtimes agree (AC: #4)
  - [ ] Verify `pixi run test` passes with the fallbacks removed.
  - [ ] Verify `pixi run serve` starts (uvicorn, `config.asgi:application`, no `--app-dir`).
  - [ ] Verify gunicorn with the uvicorn worker starts: `gunicorn config.asgi:application -k uvicorn_worker.UvicornWorker`. `gunicorn >=26.0,<27` and `uvicorn-worker >=0.4,<0.5` are declared only for `linux-64` and `osx-arm64` (`pixi.toml:85-91`); on win-64 this leg is unavailable and that is expected — it is why AD-18 keeps the six-combination harness Linux-only.
  - [ ] Verify `pixi run manage check` (Django's system check) succeeds through `manage.py` with no `sys.path` insert.
  - [ ] Record each verification in Completion Notes. A passing unit suite alone does not satisfy AC #4.

- [ ] Task 5 — Tests (AC: #1, #2, #3, #4, #5)
  - [ ] New `tests/unit/test_import_roots.py`. Read `manage.py`, `src/config/asgi.py` and `src/config/wsgi.py` as text and assert none contains `sys.path.insert` or `sys.path.append`.
  - [ ] Parse `pyproject.toml` with `tomllib`: assert `"src"` is not in `[tool.pytest.ini_options].pythonpath` (and, if Task 3's preferred resolution held, that the key is absent entirely); assert `[tool.hatch.build.targets.wheel]` declares a `sources` remapping and no longer enumerates per-package entries.
  - [ ] Parse `pixi.toml` with `tomllib`: assert no task's `cmd` contains `--app-dir` — this covers both `serve` and `serve-reload` and any task added later.
  - [ ] New `tests/integration/test_import_resolution.py`, every test marked `@pytest.mark.integration`: launch a subprocess for each runtime and assert the import resolves identically. At minimum, `pixi run python -c "import config.asgi, django_service"` and a subprocess that starts uvicorn against `config.asgi:application` and is terminated after a successful bind. Skip the gunicorn leg on platforms where `gunicorn` is not installed by checking `importlib.util.find_spec("gunicorn")` and calling `pytest.skip` with a comment naming `pixi.toml:82-91` as the reason — never `@pytest.mark.skip`.
  - [ ] Every subprocess must be terminated in teardown; the integration tests must leave no listening socket or child process behind.

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

### Debug Log References

### Completion Notes List

### File List
