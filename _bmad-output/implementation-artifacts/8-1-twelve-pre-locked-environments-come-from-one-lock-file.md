# Story 8.1: Twelve pre-locked environments come from one lock file

Status: ready-for-dev

## Story

As a platform engineer,
I want the four features declared as pixi features in one environments matrix sharing a single solve group,
so that twelve combinations are not twelve independent dependency solves testing two different Djangos.

## Acceptance Criteria

**Traceability:** AD-3 · supports FR-32 · NFR-5 · SC-1

1. **Given** the four selectable features
   **When** they are declared in `pixi.toml`
   **Then** each is a pixi feature
   **And** an `[environments]` matrix yields twelve pre-locked environments from one `pixi.lock`

2. **Given** all twelve environments
   **When** they are declared
   **Then** they share one `solve-group`

3. **Given** `django-celery-beat`'s `django <6.1` cap
   **When** the solve group is absent
   **Then** the four Celery combinations resolve a different Django from the other eight
   **And** a test asserts that all twelve resolve the same Django version

4. **Given** combination *n*'s gate
   **When** it runs
   **Then** it runs its materialized source under environment *n*
   **And** never in an environment fat enough to hide an import it should not have

## Tasks / Subtasks

- [ ] Task 1: Move feature-owned runtime packages out of `[dependencies]` into `[feature.<name>.dependencies]` in `pixi.toml` (AC: #1)
  - [ ] Create `[feature.celery.dependencies]` and move `celery` (`pixi.toml:17`), `django-celery-beat` (`:35`), `django-timezone-field` (`:37`), `python-crontab` (`:38`), `cron-descriptor` (`:39`), `opentelemetry-instrumentation-celery` (`:67`). Carry the existing comment block at `:22-34` with `django-celery-beat` — the rationale must stay beside the configuration it constrains.
  - [ ] Create `[feature.redis.dependencies]` and move `django-redis` (`:43`), `redis-py` (`:48`), `hiredis` (`:46`), `opentelemetry-instrumentation-redis` (`:69`).
  - [ ] Create `[feature.ui.dependencies]` and move `crispy-bootstrap5` (`:18`), `django-crispy-forms` (`:41`) with its conda-forge cap comment.
  - [ ] Create `[feature.storage.dependencies]` holding `django-storages` and `boto3` at the versions Story 7.5 landed. If Story 7.5 has not landed, declare the table empty with a comment naming Story 7.5 — do not invent versions and do not web-search them; the spine's Stack table (`django-storages` 1.14.6 / `boto3` 1.43.65) is the authority.
  - [ ] Leave `opentelemetry-instrumentation-django`, `-asgi` and `-psycopg`, the API, SDK and OTLP exporter in `[dependencies]` — Story 7.2 requires them present in all twelve.

- [ ] Task 2: Declare the twelve-environment matrix (AC: #1, #2)
  - [ ] Extend `[environments]` (`pixi.toml:141-143`) with twelve entries, each `features = [...]` naming the dev feature plus its selected feature subset, and each carrying `solve-group = "default"` — the same group `default` and `dev` already use.
  - [ ] Name each environment `combo-<id>` where `<id>` is the selected feature names sorted alphabetically and joined with `-`, or `none` when nothing is selected. The twelve: `combo-none`, `combo-redis`, `combo-storage`, `combo-ui`, `combo-redis-storage`, `combo-redis-ui`, `combo-storage-ui`, `combo-redis-storage-ui`, `combo-celery-redis`, `combo-celery-redis-storage`, `combo-celery-redis-ui`, `combo-celery-redis-storage-ui`.
  - [ ] Write the rationale comment above the matrix stating why the shared solve-group exists, in the file's existing comment style.
  - [ ] Regenerate `pixi.lock` with `pixi install` and commit it. Do not hand-edit the lock.

- [ ] Task 3: Assert the solve group holds (AC: #2, #3)
  - [ ] Add `tests/unit/test_environment_matrix.py` parsing `pixi.toml` with `tomllib` and asserting: exactly twelve `combo-*` environments exist; the twelve names equal the enumerated set; every one declares `solve-group = "default"`.
  - [ ] Add to the same file an assertion that no `combo-*` environment names `celery` without also naming `redis` (the broker constraint, declared in Story 7.6).
  - [ ] Add `tests/integration/test_environment_resolution.py` (marked `@pytest.mark.integration`) that parses `pixi.lock` and asserts every `combo-*` environment resolves the identical `django` version string, and identical versions for every package the environments have in common.

- [ ] Task 4: Assert environments are not fat (AC: #4)
  - [ ] In `tests/integration/test_environment_resolution.py`, assert `celery` and `django-celery-beat` appear in the four `combo-celery-*` environments and in no other; `django-redis`, `redis-py`, `hiredis` in exactly the eight `redis`-selecting environments; `opentelemetry-instrumentation-celery` and `-redis` in exactly their feature's environments.
  - [ ] Assert `opentelemetry-instrumentation-django`, `-asgi`, `-psycopg`, `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`, `django`, `psycopg` and `djangorestframework` appear in all twelve.

- [ ] Task 5: Record the starting state and run the gate (AC: #1, #2)
  - [ ] Note in the commit body the pre-change state: `[environments]` had only `default` and `dev`, both `solve-group = "default"` (`pixi.toml:141-143`).
  - [ ] `pixi run ci` must exit 0.

## Dev Notes

### Architecture Constraints

- **AD-3** (binding): "The four selectable features are declared as pixi features with an `[environments]` matrix, so one `pixi.lock` yields twelve pre-locked environments; combination *n*'s gate runs its materialized source under environment *n*. **All twelve environments share one `solve-group`**, without which `django-celery-beat`'s `django <6.1` cap makes the four Celery combinations resolve a different Django from the other eight and SC-1 stops meaning what it says." *Prevents:* "twelve independent dependency solves; a combination passing its gate in an environment fat enough to hide an import it should not have; twelve combinations silently testing two different Django versions."
- **What "environment *n*"** means for the gate: the reference workspace's pre-locked environment supplies the packages; the materialized tree supplies the source. Story 8.8 wires that; this story only has to make the twelve environments exist and be pre-locked from one lock.
- **AD-24**: `pixi.toml` is one of the three declared region-bearing `core` paths. This story adds feature dependency tables; Story 8.3 prunes them by declared marker. Do **not** introduce any other sub-file removal mechanism — not conditional imports, not settings-module inheritance, not `try/except ImportError`.
- **AD-13**: **No `COMPONENT_*` variable may appear in `[activation.env]`.** This story adds no environment variables; do not move `COVERAGE_CORE` (`pixi.toml:145-150`) — AD-20 requires it to travel with every combination and `[activation.env]` is how it does.
- **Supply chain** (Consistency Conventions): conda-forge only. `[pypi-dependencies]` carries the editable self-install and nothing else. A package the code imports directly is declared directly even when something else pulls it in transitively — so `django-timezone-field`, `python-crontab` and `cron-descriptor` stay explicitly declared when they move into the celery feature.
- **Broker constraint** (FR-26, declared in Story 7.6): background task processing requires the Redis cache. Twelve valid combinations, not sixteen. Enforcement in the materializer is Story 8.5; here it only shapes which twelve environments exist.
- Do **not** propose a 3.12/3.13 Python matrix. This project is Python 3.14 only (`pixi.toml:15`).

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `pixi.toml` | UPDATE | Today: `[dependencies]` (`:14-81`) holds every runtime package including celery, redis and crispy; `[environments]` (`:141-143`) declares only `default = { solve-group = "default" }` and `dev = { features = ["dev"], solve-group = "default" }`. This story moves the four features' packages into `[feature.<name>.dependencies]` and adds twelve `combo-*` environments, all `solve-group = "default"`. Preserve: the `[workspace]` block, `[target.linux-64.dependencies]` / `[target.osx-arm64.dependencies]` gunicorn+uvicorn-worker scoping (`:85-91`), `[pypi-dependencies]` / `[pypi-options]` (`:98-104`), `[activation.env] COVERAGE_CORE` (`:145-150`), every task table and every rationale comment. |
| `pixi.lock` | UPDATE | Regenerated by `pixi install` after the matrix lands. Never hand-edited. |
| `tests/unit/test_environment_matrix.py` | NEW | Parses `pixi.toml`; asserts the twelve environment names, the shared solve-group, and the broker constraint over the matrix. |
| `tests/integration/test_environment_resolution.py` | NEW | Parses `pixi.lock`; asserts one Django across all twelve and per-feature package containment. |

`accelerator.toml` and `tools/materializer/` do not exist yet in this repository; this story does not create them.

#### Project Structure Notes

The Structural Seed lists `pixi.toml` as carrying the "feature matrix, environments+solve-group, process tasks (AD-3, AD-13, AD-14)". This story delivers the first two of those three. No new directory is introduced. `tests/unit/` and `tests/integration/` already exist and already carry `conftest.py`.

Variance from the seed: the seed shows `src/config/authorization/`, `src/config/startup/`, `src/django_apps/`, `accelerator.toml`, `component.toml`, `Dockerfile` and `tools/materializer/` — none exist today. Earlier epics create them; nothing here depends on them.

### Testing Requirements

- `tests/unit/test_environment_matrix.py` — pure `tomllib` parsing of `pixi.toml`, no I/O beyond reading the file, milliseconds. Follows the precedent of `tests/unit/test_dependency_policy.py`, which already asserts a repository-level policy by parsing declaration files.
- `tests/integration/test_environment_resolution.py` — every test carries `@pytest.mark.integration`. It reads `pixi.lock`, which is a real resource, and leaves it untouched.
- The coverage floor is 90% including templates, one global constant, `COVERAGE_CORE=ctrace` in force (AD-20). `pixi run test-cov` already carries `--cov-fail-under=90` (`pixi.toml:196`).
- Disposition (Consistency Conventions, Test location): both new test files cover the accelerator's own environment matrix, so they carry the disposition of what they cover. Record them as `machinery` in `accelerator.toml` when Story 7.1's carrier exists; they do not travel into a component.
- Assertions the ACs demand, stated exactly: twelve `combo-*` environments; all twelve `solve-group = "default"`; one identical `django` version across all twelve in `pixi.lock`; no `celery`-selecting environment lacking `redis`; feature packages confined to their feature's environments.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-3]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-20]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Stack] — Django 6.0, `django-celery-beat` caps `<6.1`; pixi ≥ 0.70.2, "the `[environments]` matrix is the AD-3 mechanism"
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.1]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.2] — instrumentation package placement across the twelve
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.6] — the broker constraint and the count of twelve
- [Source: pixi.toml:14-81] — current `[dependencies]`
- [Source: pixi.toml:141-143] — current `[environments]`: only `default` and `dev`, both `solve-group = "default"`
- [Source: pixi.toml:22-34] — the `django-celery-beat` recipe comment already records the `django <6.1` cap

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
