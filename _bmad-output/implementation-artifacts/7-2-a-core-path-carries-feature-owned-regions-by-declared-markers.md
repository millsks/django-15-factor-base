# Story 7.2: A core path carries feature-owned regions by declared markers

Status: ready-for-dev

## Story

As a lead developer,
I want sub-file feature surface removed by declared markers and nothing else,
so that a missed region cannot leave an instrumentor call in a combination whose environment no longer contains it.

## Acceptance Criteria

**Traceability:** FR-2, FR-28 · AD-24 · SC-2

1. **Given** a feature-owned region inside a `core` path
   **When** it is delimited
   **Then** it uses paired `feature:<name>` / `/feature:<name>` line comments in the file's own comment syntax
   **And** every region is declared in the carrier with its path and its feature

2. **Given** the region-bearing paths known at declaration time, as an open set
   **When** they are declared
   **Then** they are declared as an open `[[regions]]` array and include `src/config/settings/base.py` (the Celery block at `:296-335`, `REDIS_URL`/`REDIS_SSL` at `:293-294`, and the feature entries in the installed-app lists), `src/config/settings/production.py` (the `CACHES` block at `:31-44` and its import at `:12`), `src/config/settings/local.py` (`:75-80`), `src/config/observability/telemetry.py` (the celery call at `:135` and the redis call at `:137`, each with its import at `:21` and `:24` — **not** `:134-137` as one region, since `:134` and `:136` are core), `src/config/startup/stage_one.py`, `pixi.toml` and `component.toml`
   **And** the reconciler encodes no fixed count of region-bearing paths

3. **Given** region reconciliation
   **When** the gate runs
   **Then** a marker naming an undeclared feature fails, a declared region whose markers are absent from the named file fails, and an unbalanced marker pair fails

4. **Given** any other sub-file removal mechanism
   **When** it is proposed
   **Then** it is forbidden — not conditional imports, not settings-module inheritance, not `try/except ImportError`

5. **Given** the instrumentation packages
   **When** a combination is materialized
   **Then** `opentelemetry-instrumentation-celery` is present in exactly the combinations that selected background task processing, `opentelemetry-instrumentation-redis` in exactly those that selected the Redis cache
   **And** the API, SDK, OTLP exporter, Django, ASGI and psycopg instrumentation packages are present in all six

## Tasks / Subtasks

- [ ] Task 1 — Define the marker syntax and the `[regions]` declaration shape (AC: #1, #3)
  - [ ] In `accelerator.toml`, populate `[[regions]]` as an **open array of tables — never a fixed set of keys, and never a hardcoded count**. Each entry: `path` (repo-relative), `feature` (one of `celery`, `redis`, `storage`), and a short `reason`. Add nothing else — the marker pair in the file is the extent; the carrier does not duplicate line numbers, which would drift on every edit.
  - [ ] Marker form: an open line `feature:<name>` and a close line `/feature:<name>`, each written as a **line comment in the file's own comment syntax**. Python: `# feature:celery` / `# /feature:celery`. TOML: `# feature:celery` / `# /feature:celery`. Django templates, if a region ever lands in one: `{# feature:celery #}` / `{# /feature:celery #}` — no template carries one today, because the interface mechanism is `core` in its entirety (AD-29).
  - [ ] The marker text must be recognizable by an exact regex anchored to the comment token, so a marker inside a string literal or a docstring is not a marker. Write the regex once in the parser (Task 3) and nowhere else.
  - [ ] Markers are removed along with the region they delimit when a combination prunes it (Story 8.3's acceptance). Nothing in this story removes anything — this story marks and reconciles only.

- [ ] Task 2 — Mark the region-bearing paths (AC: #1, #2, #5)
  - [ ] `src/config/settings/base.py` — wrap the Celery settings block at **`:296-335`**. The block begins at the `# Celery` header on `:296` and ends at `CELERY_WORKER_HIJACK_ROOT_LOGGER = False` on `:335`, immediately before the `# django-allauth` header on `:336`. Open marker above `:296`, close marker after `:335`. An earlier revision cited `:296-313`; that range was corrected in AD-24 because it left `CELERY_BEAT_SCHEDULER` in every combination with no `django_celery_beat`. Record the extent in the carrier `reason` field.
  - [ ] `src/config/settings/base.py` — wrap `REDIS_URL` / `REDIS_SSL` at `:293-294` as `feature:redis`. These are read by the Celery block (`CELERY_BROKER_URL`, `:302`) and by `production.py`'s `CACHES` (`:36`), and both consumers exist only where `redis` is selected — `celery` requires `redis` (FR-26), so `redis` is present whenever either is.
  - [ ] `src/config/settings/base.py` — wrap the feature entries in the installed-app lists individually: `"django_celery_beat"` at `:110` as `feature:celery`. One marker pair per contiguous run, not one pair around `THIRD_PARTY_APPS`. **`"crispy_forms"` (`:105`) and `"crispy_bootstrap5"` (`:106`) are `core` and carry no marker** — form styling is part of the immovable interface mechanism (AD-29, revision 3), and `templates/allauth/elements/field.html` and `fields.html` need `crispy` to render the FR-4 sign-in flow in every combination.
  - [ ] `src/config/observability/telemetry.py` — only two of the four instrumentor calls are feature-owned: `:134` `DjangoInstrumentor()` and `:136` `PsycopgInstrumentor()` are `core` (present in all six), `:135` `CeleryInstrumentor()` is `feature:celery`, `:137` `RedisInstrumentor()` is `feature:redis`. That is **two separate single-line regions**, not one region spanning `:134-137`. Mark each individually; marking the range as one region strips Django and psycopg instrumentation from every combination and violates FR-47 while appearing to comply.
  - [ ] `src/config/observability/telemetry.py` — the matching imports must be marked too, or pruning the call leaves the import and the `ImportError` this AD exists to prevent moves from line 135 to line 21. `from opentelemetry.instrumentation.celery import CeleryInstrumentor` at `:21` is `feature:celery`; `from opentelemetry.instrumentation.redis import RedisInstrumentor` at `:24` is `feature:redis`. `DjangoInstrumentor` (`:22`) and `PsycopgInstrumentor` (`:23`) stay.
  - [ ] `src/config/settings/production.py` — wrap the `CACHES` block at `:31-44` and its `from .base import REDIS_URL` at `:12` as `feature:redis`. `CACHES` is **not defined in `base.py` at all**; the deployed Redis cache exists only here, so missing this leaves four combinations configuring a cache backend their environment does not contain.
  - [ ] `src/config/settings/local.py` — wrap `CELERY_TASK_ALWAYS_EAGER` / `CELERY_TASK_EAGER_PROPAGATES` at `:75-80` as `feature:celery`. Epic 3 rewrites this module and Story 4.4 makes the eager-execution refusal a further declared region; if `local.py` still carries the block unmarked when this story runs, mark it here.
  - [ ] `src/config/startup/stage_one.py` — the two FR-14 conditional refusals are `feature:celery` and `feature:redis` regions. **The module does not exist yet** (Epic 4, Story 4.4). Record the forward reference in the carrier `reason`; if Story 4.4 has already landed, mark them here.
  - [ ] `component.toml` — the `worker`/`beat` replica and replacement constraints (AD-14) are a `feature:celery` region, which is why `component.toml` is itself a region-bearing `core` path: it declares process types that exist in only two of six combinations, and without markers AD-14's two-way gate test fails in the other four. **The file does not exist yet** (Epic 5, Story 5.1). Record the forward reference; mark it if Story 5.1 has landed. `feature:celery`: `celery` (`:17`), the `django-celery-beat` entry and its explanatory comment block plus its three explicit dependencies (`:22-39`), `opentelemetry-instrumentation-celery` (`:67`). `feature:redis`: `django-redis` (`:43`), `hiredis` (`:46`), `redis-py` (`:48`), `opentelemetry-instrumentation-redis` (`:69`). Keep each entry's rationale comment inside its region — the rationale travels or is pruned with what it explains.
  - [ ] `pixi.toml` — `crispy-bootstrap5` (`:18`) and `django-crispy-forms` (`:41`) are **`core` and carry no marker**. Form styling is immovable core, so no dependency leaves with the interface mechanism — that measurement is what retired the fourth feature (AD-29, revision 3).
  - [ ] `pixi.toml` — leave `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`, `opentelemetry-instrumentation-django`, `opentelemetry-instrumentation-asgi` and `opentelemetry-instrumentation-psycopg` (`:58-61`, `:66`, `:68`) unmarked and therefore `core` — present in all six (AC #5, second clause).
  - [ ] `pixi.toml` — the `worker` and `beat` tasks are `feature:celery` regions under AD-14. **They do not exist yet** (Epic 5, Story 5.2 creates them). Do not invent them. Record the forward reference in the carrier `reason` and let Story 5.2 add the markers when it adds the tasks; if Story 5.2 has already landed, mark them here.

- [ ] Task 3 — Build the region parser and the two-way region reconciler (AC: #3)
  - [ ] Create `tools/materializer/regions.py` (NEW). Public surface: `parse_regions(text: str, comment_syntax: CommentSyntax) -> list[Region]` returning `(feature, start_line, end_line)` triples; `reconcile_regions(carrier: Carrier, repo_root: Path) -> list[str]` returning failure messages.
  - [ ] Failure one: a marker in any file naming a feature not declared in `[features]`.
  - [ ] Failure two: a `[[regions]]` entry whose named file contains no matching marker pair.
  - [ ] Failure three: an unbalanced pair — an open with no close, a close with no open, a nested or interleaved pair for the same feature.
  - [ ] Also fail on a marker present in a file that carries no `[[regions]]` declaration at all — otherwise a marker added to an undeclared file passes reconciliation because nothing declares that file.
  - [ ] Reuse the `Carrier` loader from Story 7.1 (`tools/materializer/carrier.py`); extend it to expose `Carrier.regions()`. Do not open `accelerator.toml` a second time from `regions.py`.
  - [ ] Never `print()`; failures are returned as data. Type hints on every public signature; Google-style docstrings.

- [ ] Task 4 — Assert the instrumentation-package split as a carrier property (AC: #5)
  - [ ] AC #5's *"when a combination is materialized"* is discharged in Epic 8 against real materialized output. What lands here is the declaration that makes it derivable: `features.celery.packages` contains `opentelemetry-instrumentation-celery`, `features.redis.packages` contains `opentelemetry-instrumentation-redis`, and neither appears in any `core` region of `pixi.toml`.
  - [ ] Add a test asserting the carrier and `pixi.toml` agree: every package named in a `[features.<name>].packages` list appears inside a `feature:<name>` region of `pixi.toml`, and no package inside a `feature:<name>` region is absent from that feature's `packages` list. Two-way, like every other reconciliation in this epic.
  - [ ] Add a test asserting the six always-present OpenTelemetry packages sit outside every region in `pixi.toml`.

- [ ] Task 5 — Tests (AC: #1, #3, #4, #5)
  - [ ] `tests/unit/materializer/test_regions.py` (NEW): parser unit tests over inline strings — balanced pair, unbalanced open, unbalanced close, nested pair, marker inside a string literal (must not match), marker in `#`-comment and `{# #}`-comment syntax.
  - [ ] `tests/integration/materializer/test_region_reconciliation.py` (NEW), `@pytest.mark.integration`: `reconcile_regions` over the real carrier and the real tree returns zero failures; three negative cases against `tmp_path` copies covering the three declared failure modes.
  - [ ] `tests/integration/materializer/test_instrumentation_split.py` (NEW), `@pytest.mark.integration`: the Task 4 assertions.
  - [ ] Add a **forbidden-mechanism test** for AC #4: assert `src/config/observability/telemetry.py` and `src/config/settings/*.py` contain no `try:`/`except ImportError` block and no conditional import of an instrumentor, and that no settings module inherits from another purely to drop a feature. Grep-level structural assertion over the parsed AST, not over raw text.
  - [ ] `pixi run ci` exits 0.

## Dev Notes

### Architecture Constraints

**AD-24 — A `core` path carries feature-owned regions by declared markers, and by no other mechanism.** Binding rule, in the AD's own words: *"A region is delimited by paired line comments in the file's own comment syntax, `feature:<name>` / `/feature:<name>`, and every region is declared in `accelerator.toml` with its path and feature. Reconciliation extends to regions in both directions: a marker naming an undeclared feature fails; a declared region whose markers are absent from the named file fails; an unbalanced marker pair fails. **No other sub-file removal mechanism is permitted — not conditional imports, not settings-module inheritance, not `try/except ImportError`.** **The set of region-bearing paths is open, and the carrier declares it as an open `[[regions]]` array — never as a fixed set of keys.** An earlier revision of this AD named three paths and was wrong; the reconciler must not encode a count."*

**Prevents (state this to yourself before choosing any shortcut):** *"two builders splitting on markers versus file-extraction and producing incompatible trees; a missed region leaving `CeleryInstrumentor().instrument()` in [the] combinations whose environment no longer contains the instrumentor — an `ImportError` at boot that path-level reconciliation cannot see; and a region declared against a stale line range or a fixed path count, which delivers the same failure while appearing to comply."* Four of six combinations do not select background task processing. Path-level reconciliation (AD-2) sees `telemetry.py` as one `core` path and reports nothing. The marker is the only thing standing between those four combinations and a boot failure.

**Explicitly forbidden in this story:**
- `try: from opentelemetry.instrumentation.celery import CeleryInstrumentor / except ImportError: CeleryInstrumentor = None`
- `if "celery" in INSTALLED_APPS:` or any runtime flag guarding an instrumentor call
- a `settings/celery.py` that `base.py` conditionally imports, or a settings module that exists only in some combinations and is inherited from
- extracting the Celery block into a separate file and disposing that file `feature:celery` — that is path-level removal used where AD-24 requires region-level, and it produces the incompatible-tree outcome the Prevents clause names first

**AD-2 — disposition scope.** *"Disposition answers only does this path travel; ... feature-owned regions inside a `core` path are AD-24."* `src/config/settings/base.py`, `src/config/observability/telemetry.py` and `pixi.toml` remain `core` and always travel. The regions inside them are the sub-file axis.

**AD-3 — the reference application stays real.** Markers are comments. After this story `pixi run ci` must behave identically, because every marker is inert to Python and to TOML. If a marker changes behaviour, it is in the wrong place.

**AD-14 — `worker` and `beat` are feature-owned regions of `pixi.toml`.** *"Pruning them is sub-file removal by declared marker, not something that happens for free."* The tasks do not exist yet; do not create them here.

**AD-29 — no `feature:*` inside `src/django_service/`.** No marker in this story goes inside `src/django_service/`; it is `core` in its entirety, and that now includes the whole interface mechanism — `base.html`, `_navbar.html` and the navigation registry, the error templates, form styling, static-file serving and the user profile views. Nothing moves out of the package (revision 3); Story 7.4 asserts the rule with a gate test, deletes the `home`/`about` demonstration pages, and replaces `base.html`'s hardcoded links with the registry.

**Project standards.** Pixi is the only runner. Python 3.14 only. conda-forge only. PEP 8 / 120 / full type hints / Google docstrings. Never `print()`, never stdlib `logging`, never bare `except:`, never `except X: pass`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `accelerator.toml` | UPDATE | Story 7.1 created it with an empty `[regions]` slot. Populate `[[regions]]` with one entry per declared region. Preserve `[dispositions]`, `[features]`, `[tenant]`, `[verification]`, `[contributable]` untouched. |
| `src/config/settings/base.py` | UPDATE | **Today:** the single composed settings module — `BASE_DIR`/`APPS_DIR` (`:15-18`), `DATABASES` with a sqlite fallback (`:57-80`), `DJANGO_APPS`/`THIRD_PARTY_APPS`/`LOCAL_APPS` (`:93-123`), structlog wiring (`:281-291`), `REDIS_URL`/`REDIS_SSL` (`:293-294`), the Celery block (`:296-335`), allauth (`:336-352`), DRF (`:357-364`), spectacular (`:373-379`). **This story adds:** three marker pairs — `feature:celery` around `:110`, `feature:redis` around `:293-294`, `feature:celery` around `:296-335`. `crispy_forms` (`:105`) and `crispy_bootstrap5` (`:106`) stay unmarked and `core`. **Preserve:** every setting value, every existing comment, the `# ruff: noqa: ERA001, E501` header at `:1`, and the module's ordering — Epic 4 will append the stage-1 refusal call as the last statement, so do not add anything after the final block. |
| `src/config/observability/telemetry.py` | UPDATE | **Today:** builds a `TracerProvider`, resolves the exporter (`resolve_traces_exporter`, `:87-101`), attaches OTLP or console processors (`:125-128`), then instruments four libraries at `:134-137`. **This story adds:** `feature:celery` markers around the import at `:21` and the call at `:135`; `feature:redis` markers around the import at `:24` and the call at `:137`. **Preserve:** the module docstring's reasoning about conditional export (`:1-13`), the `_configured` idempotence guard, `reset_telemetry_for_testing`, and the `DjangoInstrumentor`/`PsycopgInstrumentor` calls, which are `core`. |
| `pixi.toml` | UPDATE | **Today:** `[workspace]` (`:1-7`), `[dependencies]` (`:14-80`) with per-package rationale comments, platform-scoped gunicorn/uvicorn-worker (`:85-91`), `[pypi-dependencies]` carrying only the editable self-install (`:98-99`), `[pypi-options] no-build-isolation` (`:103-104`), `[feature.dev.dependencies]` (`:106-132`), `[environments]` with only `default` and `dev` sharing `solve-group = "default"` (`:141-143`), `[activation.env] COVERAGE_CORE = "ctrace"` (`:145-150`), and the task tables (`:172-207`). **This story adds:** marker pairs around the celery and redis dependency lines listed in Task 2. **Preserve:** the six-combination `[environments]` matrix is Epic 8's work — do not add `[feature.<name>]` tables or new environments here. Do not touch `[activation.env]`; AD-13 forbids `COMPONENT_*` there and this story adds no variables. |
| `tools/materializer/regions.py` | NEW | Marker parser and two-way region reconciler. |
| `tools/materializer/carrier.py` | UPDATE | Add `Carrier.regions()`. Preserve the Story 7.1 loader contract, especially the `machinery` default and the ambiguity rejection. |
| `tests/unit/materializer/test_regions.py` | NEW | Parser unit tests. |
| `tests/integration/materializer/test_region_reconciliation.py` | NEW | AD-24 two-way gate test, `@pytest.mark.integration`. |
| `tests/integration/materializer/test_instrumentation_split.py` | NEW | AC #5 carrier/`pixi.toml` package-split assertions, `@pytest.mark.integration`. |

**Line-range verification, 2026-08-15 — read both Python files, results below.**

- `src/config/observability/telemetry.py` — `:134` `DjangoInstrumentor().instrument()`, `:135` `CeleryInstrumentor().instrument()`, `:136` `PsycopgInstrumentor().instrument()`, `:137` `RedisInstrumentor().instrument()`. **This is not one four-line region.** Two of the four calls are `core`; the feature-owned regions are the single lines `:135` and `:137`, plus their imports at `:21` and `:24`. A region covering a call must also cover its import — pruning the call alone moves the `ImportError` from line 135 to line 21, which is the failure this AD exists to prevent, relocated rather than fixed.
- `src/config/settings/base.py:296-335` — `:296` is the `# Celery` header and `:298` the first setting. The block runs through `CELERY_RESULT_BACKEND_ALWAYS_RETRY` (`:313`), `CELERY_RESULT_BACKEND_MAX_RETRIES` (`:315`), `CELERY_ACCEPT_CONTENT` (`:317`), the serializers (`:319`, `:321`), the time limits (`:324`, `:327`), `CELERY_BEAT_SCHEDULER` (`:329`), `CELERY_WORKER_SEND_TASK_EVENTS` (`:331`), `CELERY_TASK_SEND_SENT_EVENT` (`:333`) and `CELERY_WORKER_HIJACK_ROOT_LOGGER` (`:335`). The `# django-allauth` header follows at `:336`. Closing at `:313`, as an earlier revision did, would leave twenty-two Celery settings in four combinations — harmless as dead configuration, fatal as an orphan the coverage signal cannot see and as a `CELERY_BEAT_SCHEDULER` referencing `django_celery_beat`, a package those combinations do not have.
- `src/config/settings/base.py:293-294` — `REDIS_URL` and `REDIS_SSL`. `feature:redis`. Consumed by the Celery block (`:302`, `:304`, `:306`, `:308`) and by `production.py` (`:12`, `:36`).
- `src/config/settings/production.py:31-44` — the `CACHES` block configuring `django_redis.cache.RedisCache`, and its `from .base import REDIS_URL` at `:12`. `CACHES` is not defined in `base.py` at all; the deployed Redis cache lives only here, and the in-process substitute only in `local.py:18-26`.
- `src/config/settings/local.py:75-80` — `CELERY_TASK_ALWAYS_EAGER` / `CELERY_TASK_EAGER_PROPAGATES`, `feature:celery`. Epic 3 rewrites this module and Story 4.4 makes the eager-execution refusal a further declared region.

**`src/config/urls.py` is not a region-bearing path.** An earlier revision expected `feature:ui` markers around its `home`, `about` and `users/` routes. Under revision 3 the `users/` include is `core` and the `home`/`about` `TemplateView`s are **deleted** by Story 7.4, so nothing in this file is feature-owned and no marker belongs in it.

**The set is open by construction, not by exception.** Epic 3 restructures the local substitutions, Epic 4 adds the FR-14 feature-scoped refusals in `src/config/startup/stage_one.py`, and Epic 5 creates `component.toml` with the AD-14 process constraints — each a further region-bearing path. Model `[[regions]]` as an open array of tables and never hard-code a filename list or a count in the reconciler.

### Testing Requirements

- Unit: `tests/unit/materializer/test_regions.py`. Isolated, milliseconds. Assert the three declared failure modes are detected at parser level and that a marker-shaped string inside a Python string literal or docstring does not match.
- Integration: `tests/integration/materializer/test_region_reconciliation.py` and `test_instrumentation_split.py`, every test `@pytest.mark.integration`. Read-only against the repository; negative cases operate on `tmp_path` copies and leave state as found.
- The AC #4 forbidden-mechanism test belongs in `tests/integration/materializer/test_region_reconciliation.py` or its own module; assert over parsed ASTs (`ast.parse` on the settings and telemetry modules) so a comment mentioning `ImportError` does not trip it.
- Existing tests that must keep passing unchanged: `tests/unit/test_telemetry.py`, `tests/unit/test_settings.py`, `tests/unit/test_celery_app.py`, `tests/unit/test_observability_init.py`. Markers are comments; if any of these change behaviour, a marker is misplaced.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` in force (AD-20).
- Test disposition: these tests cover `machinery` (the reconciler) and therefore carry `machinery`. The FR-14 refusal tests Epic 4 writes will carry `feature:<name>` and be pruned with their feature — that is Story 7.7's sweep, not this one's.

#### Project Structure Notes

- No file moves and no new source packages under `src/`. This story adds comments to existing `core` paths — `base.py`, `telemetry.py`, `pixi.toml`, `production.py`, `local.py` — and one new machinery module. There is no `src/features/` and no feature package: AD-33 is retired, and a feature owns regions of `core` paths and dependency entries and nothing else.
- The set of region-bearing paths is **open**. Two more arrive with Epic 4 (`src/config/startup/stage_one.py`) and Epic 5 (`component.toml`), and the AD's own list is explicitly "the paths known at the time of writing". Model `[[regions]]` as an open array of tables, never as a fixed set of keys, and never hard-code filenames or a count in the reconciler.
- `pixi.toml` is touched by Epics 1, 3, 5, 7 and 8 (epics.md "Known file overlap, assessed"). The overlap is judged incidental because the blocks are distinct and AD-24 makes the feature-owned ones explicitly delimited. Keep every marker pair tight around its own lines so a later epic editing an adjacent block does not land inside a region.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-3]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-14]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — "Feature-conditional code": the FR-14 refusals are feature-owned regions, not flag-guarded code
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.2]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.3] — the pruning half of this contract; traceability marker, not an acceptance condition here
- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.4] — the two FR-14 refusals become further declared regions
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-2] — the immovable set is defined by capability, not by package
- Repository, verified 2026-08-15: `src/config/settings/base.py:110,293-294,296-335` (and `:105-106` crispy, confirmed `core`); `src/config/observability/telemetry.py:21,24,134-137`; `src/config/settings/production.py:12,31-44`; `src/config/settings/local.py:18-26,75-80`; `pixi.toml:17,22-39,43,46,48,58-61,66-69` (and `:18`, `:41` crispy, confirmed `core`)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
