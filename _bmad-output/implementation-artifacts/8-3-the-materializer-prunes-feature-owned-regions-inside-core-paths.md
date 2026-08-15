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

2. **Given** the carrier's open `[[regions]]` array of region-bearing paths
   **When** a combination without background task processing is materialized
   **Then** the Celery block in `src/config/settings/base.py`, the Celery instrumentor call in `src/config/observability/telemetry.py`, and the `worker` and `beat` tasks in `pixi.toml` are all absent
   **And** the reconciler encodes no count of region-bearing paths

3. **Given** a materialized combination
   **When** it boots
   **Then** no instrumentor is invoked whose package that combination's environment does not contain

4. **Given** any other sub-file removal mechanism
   **When** the implementation is reviewed
   **Then** none is used — not conditional imports, not settings-module inheritance, not `try/except ImportError`

## Tasks / Subtasks

- [ ] Task 1: Implement the region parser (AC: #1)
  - [ ] `tools/materializer/regions.py` — `parse_regions(text: str, comment_prefix: str) -> tuple[Region, ...]`. A `Region` records the feature name, the marker line indices and the enclosed line span.
  - [ ] Markers are paired line comments in the file's own comment syntax: `feature:<name>` opens, `/feature:<name>` closes. Both `.py` and `.toml` use `#`, which covers every path known to be region-bearing today; take the comment prefix from the carrier's region declaration rather than inferring it from the extension, so a path in another comment syntax needs no code change.
  - [ ] Iterate the carrier's `[[regions]]` array. **The set of region-bearing paths is open** (AD-24): the parser and the reconciler must accept any number of entries and must not encode a count, a fixed key set, or a hardcoded path list. A reconciler that asserts "three paths" is the failure AD-24 names.
  - [ ] `prune_regions(text, combination, declared_regions) -> str` removes the marker lines **and** everything between them for every region whose feature is not selected, and removes nothing for a selected feature — including the marker lines, which stay in the reference application but must not appear in materialized output for a selected feature either. Removing the markers with the region is AC #1; removing markers when the feature *is* selected keeps materialized output free of accelerator syntax.
  - [ ] Raise `CarrierError` on an unbalanced pair, a close with no open, nesting, or a marker naming a feature the carrier does not declare.

- [ ] Task 2: Wire region pruning into the materializer (AC: #1, #2)
  - [ ] In `tools/materializer/materialize.py`, after a path is determined to travel (Story 8.2), apply `prune_regions` to any path the carrier declares as region-bearing. Read with `encoding="utf-8"`, write with `encoding="utf-8"` and `newline="\n"`.
  - [ ] Preserve the file's trailing newline exactly. Region removal must not collapse or introduce blank lines beyond the removed span — Story 8.4 requires byte-identical repeat output and Story 8.7 compares trees.

- [ ] Task 3: Place the markers in the declared region-bearing paths (AC: #2)
  - [ ] `src/config/settings/base.py` — wrap the Celery settings block with `feature:celery` markers. The block begins at the `# Celery` header (`:296`) and runs through `CELERY_WORKER_HIJACK_ROOT_LOGGER = False` (`:335`) — verified: `:336` is the `# django-allauth` header. An earlier revision cited `:296-313`, which is the start of the block, not its end; wrapping that range would leave `CELERY_BEAT_SCHEDULER` behind in the four combinations with no `django_celery_beat`. Also wrap the feature entries inside `DJANGO_APPS`/`THIRD_PARTY_APPS`/`LOCAL_APPS` (`:93-123`) and the `REDIS_URL`/`REDIS_SSL` lines (`:293-294`, `feature:redis`) with their owning feature's markers. Verified: the only feature-owned installed-app entry today is `"django_celery_beat"` at `:110`; `"crispy_forms"` (`:105`) and `"crispy_bootstrap5"` (`:106`) are **core** under AD-29 and are not wrapped.
  - [ ] `src/config/settings/production.py` — wrap the `CACHES` block (`:31-44`, `feature:redis`) **and its `from .base import REDIS_URL` at `:12`** with the same feature's markers. `CACHES` is not defined in `base.py` at all; the deployed Redis cache exists only here, so missing this region leaves a `django_redis` backend in the two combinations with no Redis.
  - [ ] `src/config/settings/local.py` — wrap `CELERY_TASK_ALWAYS_EAGER` / `CELERY_TASK_EAGER_PROPAGATES` (`:75-80`, including the `# Celery` header at `:75-76`) with `feature:celery` markers.
  - [ ] `src/config/observability/telemetry.py` — **two single-line regions, each paired with its import.** Wrap `CeleryInstrumentor().instrument()` (`:135`) with `feature:celery` markers and its import `from opentelemetry.instrumentation.celery import CeleryInstrumentor` (`:21`) with the same; wrap `RedisInstrumentor().instrument()` (`:137`) with `feature:redis` markers and its import at `:24` with the same. `DjangoInstrumentor` (`:134`, import `:22`) and `PsycopgInstrumentor` (`:136`, import `:23`) are **core** and are never wrapped. Marking `:134-137` as one region strips Django and psycopg instrumentation from every combination and violates FR-47 while appearing to follow AD-24; pruning a call without its import merely relocates the `ImportError` from `:135` to `:21`.
  - [ ] `src/config/startup/stage_one.py` — wrap the two FR-14 conditional refusals with their owning feature's markers (`feature:celery`, `feature:redis`). Story 4.4 authors those refusals; if it has not landed, record the omission rather than inventing them.
  - [ ] `pixi.toml` — wrap the `[feature.celery.dependencies]`, `[feature.redis.dependencies]` and `[feature.storage.dependencies]` tables added by Story 8.1, and the `worker` and `beat` process tasks that Story 5.2 added, each with its owning feature's markers. There is no `[feature.ui.dependencies]` table — the interface mechanism is `core` (AD-29, revision 3) and the crispy packages stay in `[dependencies]`.
  - [ ] `component.toml` — wrap the `worker`/`beat` replica and replacement constraints (AD-14, AD-28) with `feature:celery` markers. Without them AD-14's two-way gate test fails in the four non-Celery combinations by declaring processes with no matching task.
  - [ ] **`src/config/urls.py` is not region-bearing.** Its interface routes are `core` (`users:detail`, `users:redirect`) or deleted (`home`, `about` — demonstration content, AD-29). Do not add markers there.
  - [ ] Every region added here must have a matching entry in `accelerator.toml`'s `[[regions]]` array (path + feature), authored under Story 7.2. Adding a marker without the declaration fails region reconciliation, and a declared region whose markers are absent fails it in the other direction.

- [ ] Task 4: Prove the boot property (AC: #3)
  - [ ] `tests/integration/materializer/test_region_pruning.py` (`@pytest.mark.integration`, `tmp_path`) — materialize each of the six and, for every combination, assert the pruned `telemetry.py` contains an instrumentor call only for instrumentation packages present in that combination's environment.
  - [ ] Assert for the four non-Celery combinations that `CeleryInstrumentor` appears nowhere in the materialized tree — neither the call nor its import — and for the two non-Redis combinations that `RedisInstrumentor` appears nowhere.
  - [ ] Assert `DjangoInstrumentor` and `PsycopgInstrumentor`, and both their imports, survive in **all six**. This is the assertion that catches the `:134-137`-as-one-region mistake.
  - [ ] Assert `src/config/settings/base.py` in a non-Celery combination contains no `CELERY_` prefixed name (including `CELERY_BEAT_SCHEDULER`, the name the `:296-313` range left behind) and no `django_celery_beat` installed-app entry; that `src/config/settings/production.py` in a non-Redis combination defines no `CACHES` and imports no `REDIS_URL`; that `src/config/settings/local.py` in a non-Celery combination defines no `CELERY_TASK_ALWAYS_EAGER`; and that `pixi.toml` in a non-Celery combination declares neither a `worker` nor a `beat` task.
  - [ ] Assert the reconciler accepts a carrier whose `[[regions]]` array has an entry added or removed, without a code change — the open-set property, tested by driving `prune_regions` from a synthetic carrier in the unit tests rather than by editing the real one.

- [ ] Task 5: Prove no other mechanism is used (AC: #4)
  - [ ] `tests/unit/test_no_conditional_feature_imports.py` — parse `src/config/settings/base.py`, `src/config/observability/telemetry.py` and every module under `src/config/` with `ast`, and assert no `ImportError`/`ModuleNotFoundError` handler exists and no `import` statement sits inside an `if`/`try` body. Fail with the offending file and line.
  - [ ] Assert `src/config/settings/` contains no settings module inheriting from another for the purpose of adding or removing a feature — the only inheritance permitted is the existing `local`/`production`/`test` split from `base`.
  - [ ] Assert no marker text (`feature:` / `/feature:`) survives in any materialized tree.

- [ ] Task 6: Unit tests for the parser (AC: #1)
  - [ ] `tests/unit/materializer/test_regions.py` — balanced pair removed with markers; selected feature keeps content and loses markers; unbalanced pair, orphan close, nesting and undeclared feature each raise `CarrierError`; trailing newline preserved; CRLF is not produced.

## Dev Notes

### Architecture Constraints

- **AD-24** (binding): "A region is delimited by paired line comments in the file's own comment syntax, `feature:<name>` / `/feature:<name>`, and every region is declared in `accelerator.toml` with its path and feature. Reconciliation extends to regions in both directions: a marker naming an undeclared feature fails; a declared region whose markers are absent from the named file fails; an unbalanced marker pair fails. **No other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`.**" *Prevents:* "a missed region leaving `CeleryInstrumentor().instrument()` in the combinations whose environment no longer contains the instrumentor — an `ImportError` at boot that path-level reconciliation cannot see; and a region declared against a stale line range or a fixed path count, which delivers the same failure while appearing to comply."
- **AD-24: the set of region-bearing paths is open.** "The carrier declares it as an open `[[regions]]` array — never as a fixed set of keys. An earlier revision of this AD named three paths and was wrong; **the reconciler must not encode a count.**" The paths known at the time of writing, all verified against the tree: `src/config/settings/base.py` (Celery block `:296-335`; `REDIS_URL`/`REDIS_SSL` `:293-294`; the `django_celery_beat` installed-app entry at `:110`); `src/config/settings/production.py:31-44` plus its `from .base import REDIS_URL` at `:12`; `src/config/settings/local.py:75-80`; `src/config/observability/telemetry.py` (`:135` + import `:21`, `:137` + import `:24`); `src/config/startup/stage_one.py`; `pixi.toml`; `component.toml`. **`src/config/urls.py` is not among them** — its interface routes are core or deleted. Treat this list as today's contents of an open array, not as the array's definition.
- **Line-range corrections, both load-bearing.** `base.py`'s Celery block runs `:296-335`, not `:296-313`: `:296` is the `# Celery` header, `:335` is `CELERY_WORKER_HIJACK_ROOT_LOGGER`, and `:336` opens the `# django-allauth` block. `telemetry.py:134-137` is **not one region** — it is two single-line regions (`:135` celery, `:137` redis) plus their imports (`:21` celery, `:24` redis); `:134` `DjangoInstrumentor` and `:136` `PsycopgInstrumentor` are `core`, as are their imports at `:22` and `:23`.
- **AD-3**: pruning is subtractive at "path granularity (AD-2) and region granularity (AD-24)". Region pruning removes lines; it never rewrites, reorders or reformats them.
- **AD-1**: region declarations live in `accelerator.toml` and nowhere else. The materializer must not carry a hardcoded list of region-bearing files, and must not carry their count either.
- **AD-2**: every region-bearing path listed above is a `core` path — it always travels. Its feature content leaves by region, never by path.
- **AD-29 / revision 3**: no `feature:*` disposition inside `src/django_service/`. That is a *path* rule; it does not forbid region markers there, but no region is declared there today and none should be added by this story. Revision 3 also removes the `ui` feature entirely: `base.html`, `_navbar.html` and the navigation registry, the error templates, form styling, static-file serving and the profile views are `core`, so no template or static asset is region-bearing and no `feature:ui` marker exists anywhere. **AD-33 is retired** — there is no `src/features/`.
- **FR-2** (immovable set is by capability, not package): a materialized combination's dependency manifest carries exactly the instrumentation packages its capabilities require — which is why the `pixi.toml` feature tables are regions.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tools/materializer/regions.py` | NEW | Region parser and pruner. |
| `tools/materializer/materialize.py` | UPDATE | Created by Story 8.2 as a copy-then-remove driver at path granularity. This story adds the region pass for carrier-declared region-bearing paths. Preserve the path-level behaviour and the "never mutate `source_root`" property. |
| `src/config/settings/base.py` | UPDATE | Today 381 lines: `DJANGO_APPS`/`THIRD_PARTY_APPS`/`LOCAL_APPS` at `:93-123` (`django_celery_beat` at `:110` is the only feature entry), `REDIS_URL`/`REDIS_SSL` at `:293-294`, the Celery block `:296-335`, `REST_FRAMEWORK` at `:357`. This story adds paired marker comments around feature-owned spans. It changes no setting's value and moves no setting. |
| `src/config/settings/production.py` | UPDATE | Markers around the `CACHES` block (`:31-44`) and its `from .base import REDIS_URL` (`:12`), both `feature:redis`. `CACHES` exists nowhere else. |
| `src/config/settings/local.py` | UPDATE | Markers around `CELERY_TASK_ALWAYS_EAGER` / `CELERY_TASK_EAGER_PROPAGATES` (`:75-80`, `feature:celery`). |
| `src/config/observability/telemetry.py` | UPDATE | Today 146 lines; the four instrumentor calls at `:134-137` inside the configure function, followed by the `_configured = True` guard and `reset_telemetry_for_testing()` at `:143`. This story adds **two single-line regions** — `:135` (`feature:celery`) and `:137` (`feature:redis`) — each paired with its import at `:21` and `:24`. `:134`, `:136` and their imports at `:22`, `:23` stay core and unmarked. Preserve the idempotence guard and the test helper. |
| `src/config/startup/stage_one.py` | UPDATE | Markers around the two FR-14 feature-scoped refusals (Story 4.4). If that story has not landed, record the omission. |
| `pixi.toml` | UPDATE | Adds markers around the three `[feature.*.dependencies]` tables (Story 8.1 — celery, redis, storage; there is no `ui` table) and the `worker`/`beat` tasks (Story 5.2). Preserve `[activation.env] COVERAGE_CORE` (`:145-150`) unmarked — AD-20 requires it in all six. |
| `component.toml` | UPDATE | Markers around the `worker`/`beat` replica and replacement constraints (`feature:celery`, AD-14/AD-28). |
| `accelerator.toml` | UPDATE | An entry in the open `[[regions]]` array (path + feature) for every marker pair added here. No count, no fixed key set. |
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
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Corrections — revision 2] — corrections 1, 2 and 3
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.2] — the marker syntax and the carrier's `[[regions]]` array, authored there
- [Source: src/config/observability/telemetry.py:134-137] — verified: `DjangoInstrumentor` 134, `CeleryInstrumentor` 135, `PsycopgInstrumentor` 136, `RedisInstrumentor` 137
- [Source: src/config/observability/telemetry.py:21-24] — verified: celery import 21, django 22, psycopg 23, redis 24
- [Source: src/config/settings/base.py:296-335] — the Celery block, verified: `# Celery` at 296, `CELERY_WORKER_HIJACK_ROOT_LOGGER` at 335, `# django-allauth` at 336
- [Source: src/config/settings/base.py:93-123] — the installed-app lists; `django_celery_beat` at 110, `crispy_forms`/`crispy_bootstrap5` at 105-106 are core
- [Source: src/config/settings/production.py:12,31-44] — verified: `from .base import REDIS_URL` at 12, `CACHES` 31-44
- [Source: src/config/settings/local.py:75-80] — verified: `# Celery` at 75, `CELERY_TASK_EAGER_PROPAGATES` at 80

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
