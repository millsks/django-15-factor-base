# Story 8.3: The materializer prunes feature-owned regions inside core paths

Status: ready-for-dev

## Story

As a platform engineer,
I want sub-file feature surface removed by its declared markers,
so that a combination does not boot into an `ImportError` from an instrumentor call its environment no longer contains.

## Acceptance Criteria

**Traceability:** FR-30, FR-28, FR-2 · AD-3, AD-24

1. **Given** a `core` path carrying feature-owned regions
   **When** a combination that did not select that feature is materialized
   **Then** the region between the paired `feature:<name>` / `/feature:<name>` markers is removed
   **And** the markers are removed with it

2. **Given** the three declared region-bearing paths
   **When** a combination without background task processing is materialized
   **Then** the Celery block in `src/config/settings/base.py`, the Celery instrumentor call in `src/config/observability/telemetry.py`, and the `worker` and `beat` tasks in `pixi.toml` are all absent

3. **Given** a materialized combination
   **When** it boots
   **Then** no instrumentor is invoked whose package that combination's environment does not contain

4. **Given** any other sub-file removal mechanism
   **When** the implementation is reviewed
   **Then** none is used — not conditional imports, not settings-module inheritance, not `try/except ImportError`

## Tasks / Subtasks

- [ ] Task 1: Implement the region parser (AC: #1)
  - [ ] `tools/materializer/regions.py` — `parse_regions(text: str, comment_prefix: str) -> tuple[Region, ...]`. A `Region` records the feature name, the marker line indices and the enclosed line span.
  - [ ] Markers are paired line comments in the file's own comment syntax: `feature:<name>` opens, `/feature:<name>` closes. Both `.py` and `.toml` use `#`, which covers all three declared region-bearing paths; take the comment prefix from the carrier's region declaration rather than inferring it from the extension.
  - [ ] `prune_regions(text, combination, declared_regions) -> str` removes the marker lines **and** everything between them for every region whose feature is not selected, and removes nothing for a selected feature — including the marker lines, which stay in the reference application but must not appear in materialized output for a selected feature either. Removing the markers with the region is AC #1; removing markers when the feature *is* selected keeps materialized output free of accelerator syntax.
  - [ ] Raise `CarrierError` on an unbalanced pair, a close with no open, nesting, or a marker naming a feature the carrier does not declare.

- [ ] Task 2: Wire region pruning into the materializer (AC: #1, #2)
  - [ ] In `tools/materializer/materialize.py`, after a path is determined to travel (Story 8.2), apply `prune_regions` to any path the carrier declares as region-bearing. Read with `encoding="utf-8"`, write with `encoding="utf-8"` and `newline="\n"`.
  - [ ] Preserve the file's trailing newline exactly. Region removal must not collapse or introduce blank lines beyond the removed span — Story 8.4 requires byte-identical repeat output and Story 8.7 compares trees.

- [ ] Task 3: Place the markers in the three declared region-bearing paths (AC: #2)
  - [ ] `src/config/settings/base.py` — wrap the Celery settings block. The block begins at the `# Celery` header (`:296`) and runs through `CELERY_WORKER_HIJACK_ROOT_LOGGER = False` (`:335`); AD-24 and Story 7.2 cite `:296-313`, which is the start of the block, not its end. Verify the current extent before wrapping and record the corrected range. Also wrap the feature entries inside `DJANGO_APPS`/`THIRD_PARTY_APPS`/`LOCAL_APPS` (`:93-123`) and the `REDIS_URL`/`REDIS_SSL` lines (`:293-294`) with their owning feature's markers.
  - [ ] `src/config/observability/telemetry.py` — wrap `CeleryInstrumentor().instrument()` (`:135`) with `feature:celery` markers and `RedisInstrumentor().instrument()` (`:137`) with `feature:redis` markers. Their imports at the top of the module must be wrapped by the same feature's markers, or the pruned module raises `NameError`/`ImportError` at import. `DjangoInstrumentor` (`:134`) and `PsycopgInstrumentor` (`:136`) are core and are never wrapped.
  - [ ] `pixi.toml` — wrap the `[feature.celery.dependencies]`, `[feature.redis.dependencies]`, `[feature.ui.dependencies]` and `[feature.storage.dependencies]` tables added by Story 8.1, and the `worker` and `beat` process tasks that Story 5.2 added, each with its owning feature's markers.
  - [ ] Every region added here must have a matching declaration in `accelerator.toml` (path + feature), authored under Story 7.2. Adding a marker without the declaration fails region reconciliation.

- [ ] Task 4: Prove the boot property (AC: #3)
  - [ ] `tests/integration/materializer/test_region_pruning.py` (`@pytest.mark.integration`, `tmp_path`) — materialize each of the twelve and, for every combination, assert the pruned `telemetry.py` contains an instrumentor call only for instrumentation packages present in that combination's environment.
  - [ ] Assert for the eight non-Celery combinations that `CeleryInstrumentor` appears nowhere in the materialized tree, and for the four non-Redis combinations that `RedisInstrumentor` appears nowhere.
  - [ ] Assert `src/config/settings/base.py` in a non-Celery combination contains no `CELERY_` prefixed name, and `pixi.toml` in a non-Celery combination declares neither a `worker` nor a `beat` task.

- [ ] Task 5: Prove no other mechanism is used (AC: #4)
  - [ ] `tests/unit/test_no_conditional_feature_imports.py` — parse `src/config/settings/base.py`, `src/config/observability/telemetry.py` and every module under `src/config/` with `ast`, and assert no `ImportError`/`ModuleNotFoundError` handler exists and no `import` statement sits inside an `if`/`try` body. Fail with the offending file and line.
  - [ ] Assert `src/config/settings/` contains no settings module inheriting from another for the purpose of adding or removing a feature — the only inheritance permitted is the existing `local`/`production`/`test` split from `base`.
  - [ ] Assert no marker text (`feature:` / `/feature:`) survives in any materialized tree.

- [ ] Task 6: Unit tests for the parser (AC: #1)
  - [ ] `tests/unit/materializer/test_regions.py` — balanced pair removed with markers; selected feature keeps content and loses markers; unbalanced pair, orphan close, nesting and undeclared feature each raise `CarrierError`; trailing newline preserved; CRLF is not produced.

## Dev Notes

### Architecture Constraints

- **AD-24** (binding): "A region is delimited by paired line comments in the file's own comment syntax, `feature:<name>` / `/feature:<name>`, and every region is declared in `accelerator.toml` with its path and feature. Reconciliation extends to regions in both directions: a marker naming an undeclared feature fails; a declared region whose markers are absent from the named file fails; an unbalanced marker pair fails. **No other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`.**" *Prevents:* "a missed region leaving `CeleryInstrumentor().instrument()` in eight combinations whose environment no longer contains the instrumentor — an `ImportError` at boot that path-level reconciliation cannot see."
- **AD-24 names the three region-bearing paths**: `src/config/settings/base.py` (the Celery block at `:296-313`, feature entries in the installed-app lists), `src/config/observability/telemetry.py` (the per-instrumentor calls at `:134-137`), and `pixi.toml`. **Line-range drift:** `:134-137` in `telemetry.py` is exact today — `DjangoInstrumentor` 134, `CeleryInstrumentor` 135, `PsycopgInstrumentor` 136, `RedisInstrumentor` 137. `:296-313` in `base.py` is the *start* of the Celery block only; the block currently runs 296–335. Wrap the whole block, not the cited range.
- **AD-3**: pruning is subtractive at "path granularity (AD-2) and region granularity (AD-24)". Region pruning removes lines; it never rewrites, reorders or reformats them.
- **AD-1**: region declarations live in `accelerator.toml` and nowhere else. The materializer must not carry a hardcoded list of region-bearing files.
- **AD-2**: `src/config/settings/base.py`, `src/config/observability/telemetry.py` and `pixi.toml` are `core` paths — they always travel. Their feature content leaves by region, never by path.
- **AD-29**: no `feature:*` disposition inside `src/django_service/`. That is a *path* rule; it does not forbid region markers there, but no region is declared there today and none should be added by this story.
- **FR-2** (immovable set is by capability, not package): a materialized combination's dependency manifest carries exactly the instrumentation packages its capabilities require — which is why the `pixi.toml` feature tables are regions.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tools/materializer/regions.py` | NEW | Region parser and pruner. |
| `tools/materializer/materialize.py` | UPDATE | Created by Story 8.2 as a copy-then-remove driver at path granularity. This story adds the region pass for carrier-declared region-bearing paths. Preserve the path-level behaviour and the "never mutate `source_root`" property. |
| `src/config/settings/base.py` | UPDATE | Today 381 lines: `DJANGO_APPS`/`THIRD_PARTY_APPS`/`LOCAL_APPS` at `:93-123`, `REDIS_URL`/`REDIS_SSL` at `:293-294`, the Celery block `:296-335`, `REST_FRAMEWORK` at `:357`. This story adds paired marker comments around feature-owned spans. It changes no setting's value and moves no setting. |
| `src/config/observability/telemetry.py` | UPDATE | Today 146 lines; the four instrumentor calls at `:134-137` inside the configure function, followed by the `_configured = True` guard and `reset_telemetry_for_testing()` at `:143`. This story adds markers around the Celery and Redis instrumentor calls and their imports. Preserve the idempotence guard and the test helper. |
| `pixi.toml` | UPDATE | Adds markers around the four `[feature.*.dependencies]` tables (Story 8.1) and the `worker`/`beat` tasks (Story 5.2). Preserve `[activation.env] COVERAGE_CORE` (`:145-150`) unmarked — AD-20 requires it in all twelve. |
| `accelerator.toml` | UPDATE | Region declarations (path + feature) for every marker pair added here. |
| `tests/unit/materializer/test_regions.py` | NEW | |
| `tests/unit/test_no_conditional_feature_imports.py` | NEW | |
| `tests/integration/materializer/test_region_pruning.py` | NEW | |

#### Project Structure Notes

Consistent with the Structural Seed: `src/config/settings/` and `src/config/observability/` already exist and are the seed's `core` composition root. No new source directory. `tests/unit/test_no_conditional_feature_imports.py` sits at the top of `tests/unit/` because it is a whole-tree policy test, matching the placement of the existing `tests/unit/test_dependency_policy.py` and `tests/unit/test_settings.py`.

The `worker` and `beat` tasks do not exist in `pixi.toml` today; Story 5.2 (AD-14) adds them. If they have not landed, mark only the feature dependency tables and record the omission — do not invent the tasks.

### Testing Requirements

- `tests/unit/materializer/test_regions.py` and `tests/unit/test_no_conditional_feature_imports.py` are isolated, `ast`- and string-level only, milliseconds.
- `tests/integration/materializer/test_region_pruning.py` carries `@pytest.mark.integration` and materializes into `tmp_path`.
- Existing coverage of `telemetry.py` lives in `tests/unit/test_telemetry.py`; `base.py` in `tests/unit/test_settings.py`. Update those if a marker comment changes a line the tests assert on by number — prefer assertions on names, not line numbers.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` (AD-20).
- Disposition: `tests/unit/materializer/` and `tests/integration/materializer/` are `machinery`. `tests/unit/test_no_conditional_feature_imports.py` asserts a property of the component's own source and is `core` — it must travel and run inside every combination's gate.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-3]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.3]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.2] — the marker syntax and the three region-bearing paths, authored there
- [Source: src/config/observability/telemetry.py:134-137] — the four instrumentor calls, cited range verified exact
- [Source: src/config/settings/base.py:296-335] — the Celery block; the spine's `:296-313` is its start, not its end
- [Source: src/config/settings/base.py:93-123] — the installed-app lists

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
