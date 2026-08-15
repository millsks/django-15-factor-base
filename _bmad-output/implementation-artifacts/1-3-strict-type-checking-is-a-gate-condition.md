# Story 1.3: Strict type checking is a gate condition

Status: ready-for-dev

## Story

As a platform engineer,
I want mypy to run in strict mode as a gate condition,
so that the strictness three planning documents already assert becomes true of the repository.

## Acceptance Criteria

**Traceability:** NFR-4 · AD-18

1. **Given** `[tool.mypy]` sets `check_untyped_defs` today
   **When** this story lands
   **Then** it sets `strict = true`
   **And** `python_version` continues to track the supported floor

2. **Given** strict mode surfaces existing errors
   **When** they are resolved
   **Then** each is fixed at its source
   **And** none is silenced by `ignore_errors` or a module-wide `# type: ignore`

3. **Given** both the pre-commit hook and `pixi run check` run mypy
   **When** each runs
   **Then** both use the strict configuration
   **And** they agree on the result

4. **Given** a change introducing a type error
   **When** the gate runs
   **Then** it fails rather than warning

## Tasks / Subtasks

- [ ] Task 1 — Flip the mypy configuration to strict (AC: #1)
  - [ ] In `pyproject.toml` `[tool.mypy]` (`:181-191`), replace `check_untyped_defs = true` at `:183` with `strict = true`.
  - [ ] Leave `python_version = "3.14"` at `:182` unchanged. This project is **Python 3.14 only** — a deliberate single-version CI, pinned by `requires-python = "==3.14.*"` at `pyproject.toml:15` and `python = "3.14.*"` at `pixi.toml:15`. 3.14 *is* the supported floor here, so AC #1's second clause is satisfied by not touching it. Do not propose a 3.12/3.13/3.14 matrix.
  - [ ] `strict = true` subsumes `warn_unused_ignores`, `warn_redundant_casts` and `warn_unused_configs` (`:184-186`). Leave them declared — they are explicit and harmless — or remove them with a comment recording that `strict` implies them. Do not remove `ignore_missing_imports = true` at `:184` without first confirming every third-party stub resolves; `strict` does not turn it off, and removing it is a separate decision.
  - [ ] Keep `plugins = ["mypy_django_plugin.main", "mypy_drf_plugin.main"]` (`:188-191`) and `[tool.django-stubs] django_settings_module = "config.settings.test"` (`:198-199`).
  - [ ] Record the reasoning beside the change, per the spine's Rationale convention: strict is a gate condition under NFR-4 and AD-18, not an advisory.

- [ ] Task 2 — Fix every newly surfaced error at its source (AC: #2)
  - [ ] Run `pixi run typecheck` (`mypy src/`, `pixi.toml:193`) and enumerate the errors before changing any code. Expected classes under `strict` that `check_untyped_defs` did not catch: missing return annotations (`disallow_untyped_defs`), missing parameter annotations (`disallow_incomplete_defs`), untyped decorators (`disallow_untyped_decorators`), implicit `Optional`, `Any` returns from typed functions (`warn_return_any`), and calls into untyped third-party code (`disallow_untyped_calls`).
  - [ ] Highest-density expected sites: `src/config/observability/telemetry.py`, `src/config/observability/logging.py`, `src/config/settings/base.py`, `src/config/celery_app.py`, `src/config/api_router.py`, `src/django_service/users/adapters.py`, `src/django_service/users/views.py`, `src/django_service/users/forms.py`, `src/django_service/users/api/views.py`, `src/django_service/users/api/serializers.py`, `src/django_service/users/tasks.py`, `src/django_service/users/context_processors.py`.
  - [ ] Annotate with Python 3.10+ syntax only: `X | Y`, `list[X]`, `dict[K, V]`. Never `Union`, `Optional`, `List`, `Dict`. Public signatures get full type hints and Google-style docstrings.
  - [ ] **Forbidden:** adding `ignore_errors` to any `[[tool.mypy.overrides]]` block; adding a file-level `# mypy: ignore-errors`; adding a module-wide `# type: ignore` at the top of a file; adding `disable_error_code` to relax a rule globally.
  - [ ] A narrowly scoped, single-line `# type: ignore[<specific-code>]` with an adjacent comment naming the upstream reason is permitted where a third-party stub is genuinely wrong — the existing `TEMPLATES[0]["OPTIONS"]["debug"] = True  # type: ignore[index]` in `src/config/settings/test.py` is the shape. Never a bare `# type: ignore` without a code; `warn_unused_ignores` will also flag it if it becomes unnecessary.
  - [ ] `mypy src/` does not cover `manage.py` or `tests/`. Do not widen the target in this story — widening it is a larger change with its own failure surface, and `pixi.toml:193` and `.pre-commit-config.yaml`'s mypy hook must stay identical.

- [ ] Task 3 — Decide the migrations override deliberately (AC: #2)
  - [ ] `pyproject.toml:193-196` already carries `[[tool.mypy.overrides]] module = "*.migrations.*"` with `ignore_errors = true`. This predates the story and is not an error `strict` surfaced. It is consistent with `[tool.ruff] extend-exclude = ["*/migrations/*.py", ...]` at `:44` and with `.pre-commit-config.yaml`'s `exclude:` of `src/django_service/contrib/sites/migrations/`.
  - [ ] Keep it, and add a comment stating why it is not the `ignore_errors` AC #2 forbids: it silences generated Django migration files, which no rule in this product asks anyone to type, and it was not introduced to make strict mode pass. Do not extend its module pattern to any hand-written module.

- [ ] Task 4 — Prove the hook and the task agree (AC: #3)
  - [ ] `.pre-commit-config.yaml`'s `mypy` hook runs `pixi run -e dev -- mypy src/` with `language: system` and `pass_filenames: false`. `pixi.toml:193` runs `mypy src/`. Both resolve the same `pyproject.toml` `[tool.mypy]` block and the same conda-forge `mypy >=2.3,<3` from `[feature.dev.dependencies]`, so agreement is structural rather than coincidental.
  - [ ] Preserve that property: do not add a config flag to either invocation, and do not give the hook `additional_dependencies`. The `.pre-commit-config.yaml` header already states the intent — "the tools come from the pixi `dev` feature ... so pre-commit and `pixi run lint` / `check` can never disagree on versions." A test asserts it in Task 5.

- [ ] Task 5 — Tests (AC: #1, #3, #4)
  - [ ] New `tests/unit/test_typing_policy.py`. Parse `pyproject.toml` with `tomllib`: assert `[tool.mypy].strict is True`; assert `check_untyped_defs` is absent or `True` (never `False`); assert `python_version == "3.14"`; assert no `[[tool.mypy.overrides]]` entry other than the `*.migrations.*` one sets `ignore_errors`.
  - [ ] In the same file, parse `.pre-commit-config.yaml` and `pixi.toml`: assert the `mypy` hook's `entry` and the `typecheck` task's `cmd` name the same target (`src/`) and that neither passes a `--config-file`, `--strict` or `--no-strict` flag that could make them diverge.
  - [ ] Grep `src/` for forbidden silencers: assert no file contains `# mypy: ignore-errors`, and that every `# type: ignore` occurrence carries a bracketed error code.
  - [ ] AC #4 is proven by the gate itself: `pixi run ci` chains `typecheck` (Story 1.1) and mypy exits non-zero on error. Add no test that shells out to mypy — that would be a second invocation and violates AC #3's single-configuration property.

## Dev Notes

### Architecture Constraints

- **NFR-4:** "Strict typing and lint are gate conditions, not advisories."
- **AD-18 — One gate, one invocation, Linux for the matrix.** "Type checking is strict — `[tool.mypy]` sets `check_untyped_defs` today, not `strict`, and three documents already assert otherwise." Confirmed against the repository on 2026-08-15: `pyproject.toml:183` reads `check_untyped_defs = true`.
- **AD-18 Prevents:** "the orphan detector being disabled by a change nobody understood as security-relevant." The same logic applies to strictness: a relaxation that lands as one line in a config table is exactly the change this story exists to make impossible to do quietly. That is why Task 5 asserts the configuration rather than trusting it.
- **Consistency Conventions — Rationale:** "Reasoning lives beside the configuration it constrains, in the same file."
- **Project standard:** full type hints on all public signatures; Google-style docstrings on all public functions and classes; PEP 8 at line length 120; `X | Y`, `list[X]`, `dict[K, V]` — never `Union`/`List`/`Dict`.

### Source Tree — files to touch

| Path | NEW or UPDATE | What changes |
| --- | --- | --- |
| `pyproject.toml` | UPDATE | `[tool.mypy]` at `:181-191`: `check_untyped_defs = true` (`:183`) → `strict = true`. `python_version = "3.14"` (`:182`) unchanged. `plugins` (`:188-191`), `[[tool.mypy.overrides]]` for migrations (`:193-196`) and `[tool.django-stubs]` (`:198-199`) preserved. |
| `src/config/observability/telemetry.py` | UPDATE | Annotate to satisfy strict. Preserve behaviour exactly — AD-24 names `:134-137` as a future feature-owned region (the per-instrumentor calls); do not restructure that block, only annotate around it. |
| `src/config/observability/logging.py` | UPDATE | Annotate. `build_logging_config(debug, log_level, log_format)` is called from `src/config/settings/test.py` and the other settings modules; its signature is load-bearing. |
| `src/config/settings/base.py` | UPDATE | Annotate where strict demands it. AD-24 names `:296-313` as the future Celery feature-owned region; do not restructure it. |
| `src/config/celery_app.py`, `src/config/api_router.py` | UPDATE | Annotate. |
| `src/django_service/users/*.py`, `src/django_service/users/api/*.py` | UPDATE | Annotate. `src/django_service/users/models.py` defines the `User` model that Epic 2 Story 2.1 extends with `idp_subject` — leave its field set unchanged here. |
| `tests/unit/test_typing_policy.py` | NEW | Asserts the strict configuration and hook/task agreement. |

**Do not touch:** `src/config/websocket.py` and the scope dispatcher in `src/config/asgi.py` — Story 1.4 deletes them. If strict mode reports errors there, coordinate with Story 1.4 rather than annotating code that is about to be removed. `src/django_service/contrib/sites/migrations/` is excluded by the migrations override, ruff's `extend-exclude`, and pre-commit's `exclude:`.

### Testing Requirements

- Test file: `tests/unit/test_typing_policy.py`. Configuration parsing only — no I/O beyond reading repository files, no network, no database, no marker.
- Resolve paths from `Path(__file__).resolve().parents[2]`, matching `tests/unit/test_dependency_policy.py:11`.
- Annotations added under Task 2 change no behaviour, so no new behavioural test is required for them — but any signature that changes shape (a parameter made keyword-only, a return type narrowed from `Any`) does need a test asserting the new contract.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` in force (AD-20); `--cov-fail-under=90` at `pixi.toml:196`.
- Test disposition (spine §Consistency Conventions): `tests/` mirrors `src/` and carries the disposition of what it covers; this file covers the gate configuration and will be dispositioned in Epic 7.
- Done means `pixi run ci` exits 0 — including `typecheck` under `strict`.

#### Project Structure Notes

No structural change. `src/config/authorization/` and `src/config/startup/` from the Structural Seed do not exist yet (Epics 2 and 4). Every module they add will be written under `strict` from the start, which is the ordering reason this story precedes them.

Variance from the global project standard: the global standard sets `[tool.mypy] python_version = "3.12"` as the matrix floor. This project deliberately supports Python 3.14 only, so `3.14` is correct here and must not be lowered.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.3]
- [Source: _bmad-output/planning-artifacts/epics.md:115] — NFR-4.
- [Source: _bmad-output/planning-artifacts/epics.md:235] — "`[tool.mypy]` sets `check_untyped_defs` while three documents assert `strict`."
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-18]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24] — `base.py:296-313` and `telemetry.py:134-137` are future feature-owned regions.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Stack] — Python 3.14.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
