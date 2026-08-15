# Story 9.3: Dependency direction across the three territories is enforced

Status: ready-for-dev

## Story

As a platform engineer,
I want the layering enforced rather than documented,
so that a base that depends on what is built on it is caught by the gate.

## Acceptance Criteria

**Traceability:** AD-4

1. **Given** a tenant application
   **When** its imports are checked
   **Then** it may import `django_service`

2. **Given** `django_service`
   **When** its imports are checked
   **Then** it never imports a tenant application

3. **Given** `config`
   **When** its imports are checked
   **Then** it may import `django_service`
   **And** it reaches tenant applications only through the settings composition step, never by direct import

4. **Given** a violation of any of the above
   **When** the gate runs
   **Then** it fails

## Tasks / Subtasks

- [ ] Task 1 — Build the import-graph reader (AC: #1, #2, #3)
  - [ ] New `tools/layering/__init__.py` and `tools/layering/import_graph.py` (machinery; `tools/` already hosts `tools/materializer/` in the Structural Seed).
  - [ ] `def module_imports(path: Path) -> set[str]` — parse the file with `ast.parse`, walk `ast.Import` and `ast.ImportFrom`, and return the fully-qualified module names. For `ast.ImportFrom` with `level > 0`, resolve the relative import against the file's own package so `from .base import DATABASES` resolves to `config.settings.base` and is not mistaken for a top-level name.
  - [ ] `def territory(module: str, tenant_names: set[str]) -> str` — returns `"config"`, `"base"`, `"tenant"`, or `"external"` from the first dotted segment: `config` → config, `django_service` → base, a name in `tenant_names` → tenant, anything else → external.
  - [ ] Static analysis only. Do not import the modules under test to inspect them — importing `config.settings.production` executes the refusal contract and a settings import is not a layering probe.

- [ ] Task 2 — Determine the tenant-name set from declarations, not from guesswork (AC: #2, #3)
  - [ ] `tenant_names` is the union of: every immediate subdirectory of the carrier's declared tenant root (`src/django_apps/*`, Story 9.2), and every name in `component.toml`'s adopted-application list (Story 5.1). An adopted app that graduated to the channel is still a tenant application for layering purposes — its residency changed, its layer did not.
  - [ ] Never infer tenant names from a naming convention or a prefix. AD-1's rule that nothing is inferred from directory layout applies: the carrier and `component.toml` are the sources.

- [ ] Task 3 — Enforce the base → tenant prohibition (AC: #2, #4)
  - [ ] New `tests/unit/test_layering.py`. For every `*.py` under `src/django_service/`, assert no import resolves to territory `tenant`. Report the offending file, line number and module name in the assertion message — a layering failure must name the import, not just fail.
  - [ ] Include migrations in the scan. A migration that imports a tenant app is the same violation and `[tool.ruff] extend-exclude` hiding migrations from lint does not exempt it here.

- [ ] Task 4 — Enforce the config → tenant prohibition with the composition exception (AC: #3, #4)
  - [ ] For every `*.py` under `src/config/`, assert no import resolves to territory `tenant`. There is **no allowlisted module**: the composition step (`src/config/settings/composition.py`, Story 9.4) reaches tenant applications through `importlib.import_module(name)` on a name read from `component.toml` at runtime, which is not a static import and therefore never appears in the AST scan.
  - [ ] Assert positively that `src/config/settings/composition.py` contains no `ast.Import`/`ast.ImportFrom` node naming a tenant application — so the exception cannot be taken by adding one "just for the settings module".
  - [ ] Assert `src/config/` importing `django_service` is permitted (AC #3, first clause) — encode it as an explicit allowed-edge in the rule table so a future tightening cannot forbid it by accident.

- [ ] Task 5 — Assert the permitted directions, not only the forbidden ones (AC: #1, #3)
  - [ ] Express the rule as a data table in the test module: `ALLOWED_EDGES = {("tenant", "base"), ("config", "base"), ("tenant", "external"), ("base", "external"), ("config", "external"), (t, t) for same-territory}` and derive the failures from it, rather than writing one hand-rolled assertion per prohibition. A new territory then fails closed.
  - [ ] Scan every app under the tenant root (there are none in the reference application; the loop must be correct over an empty set and is exercised by the `tmp_path` fixture below).

- [ ] Task 6 — Enforce the feature-to-feature prohibition (AC: #4)
  - [ ] AD-4's fourth clause — "A feature's code may never import another feature's" — is part of the same rule and is cheap to add here. For every path carrying a `feature:<name>` disposition in `accelerator.toml`, assert no import resolves to a path carrying `feature:<other>`.
  - [ ] Note in the test docstring that the epic's ACs for this story do not enumerate this clause; it is AD-4 completeness and it fails the gate under AC #4 like any other violation.

- [ ] Task 7 — Tests that prove the checker detects, not just that it passes (AC: #4)
  - [ ] In `tests/unit/test_layering.py`, build synthetic trees under `tmp_path`: a `django_service`-shaped module importing `billing`; a `config`-shaped module importing `billing`; a tenant module importing `django_service`. Assert the first two are reported as violations and the third is not.
  - [ ] A checker with no negative test is a checker nobody has seen fail. This subtask is the acceptance evidence for AC #4.
  - [ ] `pixi run test`, then `pixi run ci`.

## Dev Notes

### Architecture Constraints

- **AD-4 (binding, and its `Binds:` field is `all`):** "A tenant app may import `django_service`. `django_service` may never import a tenant app. `config` may import `django_service` and reaches tenant apps only through the settings composition step, never by direct import. A feature's code may never import another feature's." *Prevents:* "a base that depends on what is built on it; feature surfaces that cannot be independently removed."
- **AD-8:** the composition step is how `config` reaches tenant applications — it "merges contributions from the `component.toml` adopted-app list", by name, at runtime. That is why the prohibition on static imports in `config` costs nothing.
- **AD-1:** nothing is inferred from directory layout; the tenant root and the adopted-app list are read from `accelerator.toml` and `component.toml`.
- **AD-24:** no `try/except ImportError`. If the checker cannot resolve a name it fails; it does not degrade to skipping the file.
- **AD-26:** predicates resolve objects, never strings. Here the object is the AST node and the resolved module name — not a substring match over file text. Do not implement this with `grep`, a regex over source, or `str.startswith` on raw lines.

**Must not do:**
- Do not import the modules under test to read their `__dict__`; parse them.
- Do not allowlist any module in `src/config/` for tenant imports. The composition step needs none.
- Do not skip `migrations/` — a migration import is a real edge.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tools/layering/__init__.py` | NEW | Package marker. `tools/` does not exist in the repo today; the Structural Seed places `tools/materializer/` there as `machinery`. |
| `tools/layering/import_graph.py` | NEW | `module_imports()`, `territory()`, and the violation dataclass carrying file, line and module. |
| `tests/unit/test_layering.py` | NEW | The rule table, the four scans, and the synthetic-violation tests. |
| `accelerator.toml` | UPDATE | **Does not exist today** (Story 7.1). Read for the tenant root and the `feature:*` dispositions. Add `tools/layering/` as `machinery` (it would default to `machinery` under AD-2, but declare it so input reconciliation does not report it as unclaimed). |
| `component.toml` | UPDATE | **Does not exist today** (Story 5.1). Read for the adopted-application list. No change to its content in this story. |

Verified today: `src/django_service/` contains `users/`, `contrib/sites/`, `templates/`, `static/`; `src/config/` contains `settings/`, `observability/`, `api_router.py`, `asgi.py`, `celery_app.py`, `urls.py`, `websocket.py`, `wsgi.py`. `src/config/settings/production.py:7-14` uses relative imports (`from .base import *`, `from .base import DATABASES`, …) — the relative-import resolution in Task 1 is required for this file alone to be classified correctly. There are no tenant applications in the tree, so the scan currently passes vacuously; Task 7's synthetic trees are what make the story testable.

### Testing Requirements

- `tests/unit/test_layering.py` — pure AST and TOML parsing; unit, no marker.
- Assertions the ACs demand:
  - no import from `src/django_service/**` resolves to a tenant name (AC #2);
  - no import from `src/config/**` resolves to a tenant name, composition module included (AC #3);
  - `src/config/**` importing `django_service` is allowed (AC #3);
  - a tenant module importing `django_service` is allowed (AC #1);
  - each synthetic violation is reported with file, line and module (AC #4);
  - no `feature:<a>` path imports a `feature:<b>` path (AD-4 clause four).
- Disposition: covers `core` and `machinery` surface; lives under `tests/`, never pruned.
- AD-20 floor: ninety percent including templates. Every branch of `territory()` — including `external` and the relative-import path — needs a test.
- Runner: `pixi run test`, `pixi run ci`. Never bare `pytest`.

#### Project Structure Notes

The Structural Seed's three territories are exactly `src/config/`, `src/django_service/`, `src/django_apps/`. This story adds no application code; it adds a machinery checker and a gate test.

Variance today: `src/django_apps/` (Story 9.2), `accelerator.toml` (Story 7.1), `component.toml` (Story 5.1) and `src/config/settings/composition.py` (Story 9.4) all do not exist. Implement this story after 9.2 and alongside or after 9.4 — the composition-module assertion in Task 4 has nothing to assert until 9.4 lands, and the checker itself is complete without it.

Python 3.14 only; full type hints; `set[str]` / `X | Y` forms; Google-style docstrings; no `print()` and no stdlib `logging` — if the checker needs to report, it returns violations to the caller and the test formats the message.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.3]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-4]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-8]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Structural Seed]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.2] — the tenant root this checker reads
- [Source: _bmad-output/planning-artifacts/epics.md#Story 9.4] — the composition step, the only path from `config` to a tenant app

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
