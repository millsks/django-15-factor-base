---
baseline_revision: 90cb6c2
final_revision: f2986fa
review_loop_iteration: 0
followup_review_recommended: true
status: done
---

# Story 1.8: Object-storage fitness is proven before the feature is committed to

Status: done

## Story

As a lead developer,
I want `django-storages` proven against the pinned Django and Python before object storage is built,
so that a feature three of six combinations will select is not committed to on the strength of a package that cannot run.

## Acceptance Criteria

**Traceability:** FR-50 · risk R-1

1. **Given** `django-storages` 1.14.6 declares support for neither Django 6.0 nor Python 3.14
   **When** the spike runs
   **Then** it exercises the package against the locked Django and Python through the storage API call sites the feature will use
   **And** the result is recorded where the dependency is declared

2. **Given** the spike passes
   **When** Epic 7 builds object storage
   **Then** it proceeds on the channel build
   **And** the evidence is attached at the point of declaration

3. **Given** the spike fails
   **When** escalation begins
   **Then** the conda-forge feedstock is pushed as was done for `django-celery-beat`, under a time-boxed package-index exception whose exit condition is that build landing
   **And** a component-owned storage backend remains the last resort rather than a permanent supply-chain exception

4. **Given** FR-50's rule
   **When** any future feature is proposed
   **Then** both channel availability and fitness against the pinned runtime are confirmed before commitment
   **And** presence alone is explicitly insufficient

## Tasks / Subtasks

- [x] Task 1 — Stage the spike dependency without committing the feature (AC: #1)
  - [x] Add `django-storages = ">=1.14.6,<2"` to a **new, dedicated pixi feature** — `[feature.spike-storage.dependencies]` in `pixi.toml` — and add a matching `[environments]` entry `spike-storage = { features = ["dev", "spike-storage"], solve-group = "default" }`. The shared `solve-group = "default"` is mandatory (AD-3): without it the spike would resolve a different Django from the one it is meant to test.
  - [x] **Do not add `django-storages` to `[dependencies]` in this story.** The whole point of FR-50 is that fitness is proven *before* the feature is committed to; putting it in the runtime dependency set is the commitment. Epic 7 Story 7.5 moves it there if and only if this spike passes.
  - [x] Do not add `boto3` explicitly. `django-storages` is the direct importer, not this project's code, so the transitive-availability rule (spine §Consistency Conventions, Supply chain) does not require a direct declaration for it here. The spine's Stack table records `boto3 1.43.65` as already locked via `django-anymail`. If the solve reports it missing, declare it inside `[feature.spike-storage.dependencies]` alongside `django-storages`, never in `[pypi-dependencies]`.
  - [x] Record the reasoning and the exit condition beside the new block, per the spine's Rationale convention and Story 1.7's AC #3: this feature exists to run R-1's spike, and its exit condition is the spike's recorded verdict.
  - [x] Add a `spike-storage` pixi task: `pytest tests/spikes/test_django_storages_fitness.py -m spike` with `default-environment = "spike-storage"` and a `description` naming R-1. **Done, with the module renamed** to `spike_django_storages_fitness.py` — see the Task 6 note below; the name is the mechanism that keeps the gate from collecting it.

- [x] Task 2 — Exercise the call sites the feature will actually use (AC: #1)
  - [x] FR-25 defines the surface: "Object storage attaches an S3-compatible backend configured from environment variables alone (`django-storages`, `boto3`); user media is out of scope." The spike therefore exercises the **default file storage backend**, configured through Django 6.0's `STORAGES` setting, from environment variables only.
  - [x] Mandatory, no-network leg — all of these must run against the locked Django 6.0 and Python 3.14 and must pass without any S3-compatible server:
    - Import the backend module and instantiate the S3 storage class. Confirm the class path against the installed `django-storages 1.14.6` rather than assuming — 1.14.x ships both a legacy `storages.backends.s3boto3.S3Boto3Storage` and a `storages.backends.s3.S3Storage`; record which one exists and which the feature will name.
    - Configure it through `settings.STORAGES["default"]` with `BACKEND` and an `OPTIONS` dict sourced from environment variables (endpoint URL, region, bucket, access key, secret key), and assert Django resolves it via `django.core.files.storage.storages["default"]` and `default_storage`.
    - Assert the instance satisfies the `django.core.files.storage.Storage` contract for every method the feature calls: `save`, `open`, `exists`, `delete`, `url`, `size`, `listdir`, `get_available_name`. Assert each is present and that its signature is compatible with what Django 6.0's `Storage` base declares — this is the class of breakage a package predating Django 6.0 is most likely to exhibit.
    - Assert no `DeprecationWarning` or `RemovedInDjango*Warning` is raised on import or instantiation, with `warnings.catch_warnings(record=True)`. A removed-API warning here is the early signal of a Django 6.1 break.
    - Assert `django.core.checks.run_checks()` reports no error with the storage backend configured — the Django system check framework is where a settings-shape incompatibility surfaces.
    - Assert the backend reads its configuration from environment variables alone, with no configuration file (FR-38).
  - [x] Optional round-trip leg, and **its absence must be reported, not hidden**: a `save` → `exists` → `open` → `size` → `url` → `delete` cycle against an S3-compatible endpoint. Gate it on an `AWS_S3_ENDPOINT_URL`-style environment variable being set; when unset, the test reports the bound explicitly rather than passing silently.
  - [x] **State the bound in the recorded verdict.** CG-2's discipline applies: "A silently narrowed claim reads as full coverage and is worse than a bounded one" (`epics.md:341`). If only the no-network leg ran, the verdict says so and names what remains unproven.

- [x] Task 3 — Record the verdict where the dependency is declared (AC: #1, #2)
  - [x] AC #1's "recorded where the dependency is declared" means a comment block in `pixi.toml` beside the `django-storages` declaration. Write it there: the versions tested (django-storages 1.14.6, Django 6.0, Python 3.14 — from the spine's Stack table), the call sites exercised, the verdict, the date, and the bound (which legs did not run).
  - [x] Also add an "Object storage fitness (R-1)" section to `docs/development.md` carrying the same verdict and the full escalation ladder, so a reader who never opens `pixi.toml` finds it.
  - [x] The verdict must be one of exactly three: **proven** (all mandatory legs pass), **proven with a stated bound** (mandatory legs pass, round-trip unrun), or **failed** (any mandatory leg fails). Do not record a fourth, softer outcome.

- [x] Task 4 — Author the ordered escalation, whatever the verdict (AC: #2, #3, #4)
  - [x] Write the escalation ladder into `docs/development.md` verbatim in its ordering, whether or not it is triggered. R-1 states it: **spike** `1.14.6` against the locked Django and Python first, since it is a thin wrapper over a `boto3` already in the lock and Django's `Storage` API has been stable → if that fails, **push the conda-forge feedstock** as was done for `django-celery-beat`, with a **time-boxed** package-index exception whose exit condition is that build landing → **a component-owned S3 backend** against `django.core.files.storage.Storage` as the **last resort**, "because a platform product owning its own storage backend is a permanent maintenance and security cost." R-1 closes: "A permanent supply-chain exception is not on the list."
  - [x] If and only if the verdict is **failed**: open the conda-forge feedstock issue/PR, record its URL beside the declaration, and add the time-boxed `[pypi-dependencies]` exception with its exit condition stated in a comment. Story 1.7's tests are written to require exactly that — an exception entry whose comment block names an exit condition. Do not add the exception pre-emptively on a passing verdict. **Branch not triggered.** The verdict is *proven with a stated bound*, so no feedstock issue was opened and no `[pypi-dependencies]` entry was added. `test_the_storage_spike_is_staged_rather_than_committed_to` asserts the absence, and its docstring says which verdict it encodes.
  - [x] The `django-celery-beat` precedent is documented in this repository at `pixi.toml:22-34` and in `tests/unit/test_dependency_policy.py:55-65`. Follow its shape: what was wrong upstream, what build fixed it, and what the solver now enforces on its own.

- [x] Task 5 — Make FR-50's general rule checkable (AC: #4)
  - [x] Record FR-50 as a standing rule in the same `docs/development.md` supply-chain section Story 1.7 creates: before any feature is committed to, confirm **both** channel availability **and** fitness against the pinned runtime. "Presence alone is explicitly insufficient."
  - [x] Name the failure mode concretely so a future reader recognizes it: `django-storages` is present on conda-forge — which is FR-50's availability test — and was released 2025-04-02 declaring support for neither Django 6.0 nor Python 3.14. Availability passed; fitness was unknown. That gap is what R-1 is.
  - [x] This half of AC #4 is a documented rule, not an automated assertion — there is no mechanical test for "a future feature was proposed." Say so explicitly in the docs rather than writing a test that only appears to enforce it.

- [x] Task 6 — Tests (AC: #1, #2, #3, #4)
  - [x] New `tests/spikes/__init__.py` and `tests/spikes/test_django_storages_fitness.py`. Register a `spike` marker in `pyproject.toml [tool.pytest.ini_options] markers` alongside the existing `integration` marker at `:155-157`. **Module named `spike_django_storages_fitness.py`**, and the marker registered at `pyproject.toml:210-218` (the spec's `:155-157` was stale).
  - [x] **Keep the spike out of `pixi run ci`.** `pyproject.toml:150` sets `testpaths = ["tests"]`, which would collect `tests/spikes/`; the `test-cov` task at `pixi.toml:196` runs `pytest tests/`. The spike needs the `spike-storage` environment, which the `dev` environment is not, so it would fail collection in the gate. Add `-m "not spike"` to the `test-cov` task's `cmd`, or place the spike outside `testpaths` — the dev agent chooses and records the choice. The gate must stay green and the spike must stay runnable via `pixi run spike-storage`. **Choice: neither, exactly. `-m` is banned** on the floor-carrying task by `tests/unit/test_coverage_policy.py::test_the_floor_task_measures_the_whole_suite_and_the_whole_source_tree` (`NARROWING_FLAGS`), and `testpaths` is irrelevant because `test-cov` names `tests/` on the command line, which overrides it. The spike is kept out by *module name* instead — `spike_*.py` does not match `python_files`. See the Completion Notes.
  - [x] The no-network leg is unit-scope in cost but crosses a package boundary; mark it `@pytest.mark.spike` only. The round-trip leg is `@pytest.mark.spike` **and** `@pytest.mark.integration`, and is conditional on the endpoint variable — express the condition with `pytest.skip` inside the test, carrying a comment that names the bound. Never `@pytest.mark.skip` and never `xfail`.
  - [x] Extend `tests/unit/test_dependency_policy.py`: assert `django-storages` is **absent** from `[dependencies]` and from `[pypi-dependencies]` while the verdict is unrecorded, and that the `spike-storage` environment declares `solve-group = "default"`. Once the verdict is recorded, update the assertion to match the verdict's outcome and state which one it encodes.
  - [x] Every temporary object the round-trip leg creates must be deleted in teardown; the integration leg must leave the bucket as it found it.

## Dev Notes

### Architecture Constraints

- **FR-50:** "Channel availability *and fitness against the pinned runtime* are checked before a feature is committed to."
- **R-1 — `django-storages` fitness is unproven, and object storage cannot be deferred.** Verbatim: "Present on the channel, which is FR-50's test, but released 2025-04-02 with no declared Django 6.0 or Python 3.14 support and nothing newer available; Django 6.0 support exists only on unreleased upstream master. Object storage appears in three of six combinations, does not exist yet, and is expected to be selected by most components — so dropping it is not an available answer and the risk must be carried rather than avoided. The escalation is ordered: spike `1.14.6` against the locked Django and Python first, since it is a thin wrapper over a `boto3` already in the lock and Django's `Storage` API has been stable; if that fails, push the conda-forge feedstock as was done for `django-celery-beat`, with a **time-boxed** package-index exception whose exit condition is that build landing; a component-owned S3 backend against `django.core.files.storage.Storage` is the last resort, because a platform product owning its own storage backend is a permanent maintenance and security cost. A permanent supply-chain exception is not on the list."
- **Why this is Epic 1 and not Epic 7.** `epics.md:237`: Epic 1 "carries the R-1 spike as an early long-pole story, on FR-50's own rule that fitness is proven before a feature is committed to." `epics.md:273`: Epic 7 "builds object storage greenfield on whatever Epic 1's R-1 spike concluded." **This story's output is Epic 7 Story 7.5's input.** Write the verdict so that story can act on it without re-deriving anything.
- **AD-3:** the three selectable features — background task processing, Redis and object storage — are pixi features with an `[environments]` matrix, and **all six environments share one `solve-group`**. The spike environment must join `solve-group = "default"` for the same reason: otherwise it tests a different Django than the product ships.
- **Spine §Consistency Conventions — Supply chain:** conda-forge only; `[pypi-dependencies]` carries the editable self-install and nothing else. Story 1.7's tests enforce this; a spike that quietly adds a pypi entry breaks that story's gate.
- **FR-25:** "Object storage attaches an S3-compatible backend configured from environment variables alone (`django-storages`, `boto3`); **user media is out of scope.**" Do not spike media handling, `ImageField`, thumbnailing or upload views.
- **FR-38:** "Configuration is exclusively environmental; no configuration file in the image." The spike's configuration must come from environment variables only.
- **Stack table (spine §Stack), authoritative — do not web-search versions:** `django-storages / boto3 | 1.14.6 / 1.43.65 | boto3 already locked via django-anymail. django-storages released 2025-04-02, declares no Django 6.0 or py3.14 — see residual risk R-1`. Django 6.0, Python 3.14.
- **Forbidden:** upgrading `django-storages` past 1.14.6 to make the spike pass — nothing newer is available on the channel, which is the premise of R-1; using `pip`/`uv` to fetch a package for the spike; skipping to the component-owned backend without attempting the feedstock push; recording a permanent package-index exception.

### Source Tree — files to touch

| Path | NEW or UPDATE | What changes |
| --- | --- | --- |
| `pixi.toml` | UPDATE | NEW `[feature.spike-storage.dependencies]` with `django-storages` and its rationale/exit-condition comment. NEW `[environments] spike-storage = { features = ["dev", "spike-storage"], solve-group = "default" }` alongside the existing `default` and `dev` at `:141-143`. NEW `spike-storage` task. The `test-cov` task at `:196` gains `-m "not spike"` (or `testpaths` is adjusted). `[dependencies]` (`:14-80`) and `[pypi-dependencies]` (`:98-99`) are **unchanged** unless the verdict is *failed*. |
| `pyproject.toml` | UPDATE | `[tool.pytest.ini_options] markers` at `:155-157` gains `spike: marks the R-1 django-storages fitness spike; runs only in the spike-storage environment`. If the spike is placed outside `testpaths`, `:150` changes too. |
| `tests/spikes/__init__.py` | NEW | Package marker, matching the `__init__.py` convention already used in `tests/`, `tests/unit/`, `tests/integration/`. |
| `tests/spikes/test_django_storages_fitness.py` | NEW | The spike itself: import, instantiation, `STORAGES` resolution, `Storage` API conformance, warnings check, `run_checks`, environment-only configuration; plus the conditional round-trip leg. |
| `tests/unit/test_dependency_policy.py` | UPDATE | Asserts `django-storages` placement matches the recorded verdict and that `spike-storage` shares the solve-group. Extended by Story 1.7 as well — coordinate. |
| `docs/development.md` | UPDATE | "Object storage fitness (R-1)" section: verdict, bound, ordered escalation, and FR-50's standing rule. Extends the "Supply chain" section Story 1.7 adds. |

**Verified today (2026-08-15):** `django-storages` and `boto3` are **not** declared in `pixi.toml`. `[environments]` has only `default` and `dev`, both `solve-group = "default"`. `django-anymail = ">=15.1,<16"` is declared at `pixi.toml:21`. `[tool.pytest.ini_options] markers` declares only `integration`. `tests/spikes/` does not exist. Nothing about object storage exists in `src/`.

### Testing Requirements

- Test files: `tests/spikes/test_django_storages_fitness.py` (new, `@pytest.mark.spike`), `tests/unit/test_dependency_policy.py` (extended, no marker).
- Every test in the round-trip leg carries `@pytest.mark.integration` in addition to `@pytest.mark.spike`, per the project convention that anything touching a real resource is an integration test, and must leave the bucket as it found it.
- Assertions the ACs demand: the S3 backend class imports and instantiates under Django 6.0 / Python 3.14; `storages["default"]` and `default_storage` resolve to it; every named `Storage` method exists with a Django-6.0-compatible signature; no removal/deprecation warning on import or instantiation; `django.core.checks.run_checks()` reports no error; configuration comes from environment variables alone.
- Coverage floor 90% including templates (AD-20), `--cov-fail-under=90` at `pixi.toml:196`. The spike runs outside the gate's coverage measurement; make sure excluding it does not narrow the measured surface — this interacts with Story 1.5's closed omit list, so if an omit entry is needed for `tests/spikes/`, it must be added to that **declared** list, not added silently. `*/tests/*` is already omitted at `pyproject.toml:164`, which likely covers it — verify rather than assume.
- Test disposition (spine §Consistency Conventions): the spike covers a `feature:storage` surface that does not exist yet. It is `machinery` — a spike is accelerator work and never travels to a component. Record that intent for Epic 7 Story 7.1's disposition author.

#### Project Structure Notes

`tests/spikes/` is a new sibling of `tests/unit/` and `tests/integration/`. The Structural Seed shows only `tests/` without subdivision, so this introduces no conflict; the spine's test-location convention ("Accelerator and base tests live under `tests/`, mirroring `src/`, and carry the disposition of what they cover") is satisfied by a `machinery`-dispositioned spike directory.

Variance: the spike environment is an extra pixi environment shape that the AD-3 six-environment matrix does not anticipate. It is temporary — Epic 8 Story 8.1 builds the real matrix, and by then this spike has served its purpose. Record in Completion Notes whether `[feature.spike-storage]` should be removed at that point or folded into the `storage` feature Epic 7 declares.

### Forward context — this story's output is consumed downstream

Epic 7 Story 7.5 ("Object storage attaches an S3-compatible backend with a local substitution") builds on this verdict. AC #2's "the evidence is attached at the point of declaration" is what makes that possible: Story 7.5 moves `django-storages` from the spike feature into the `storage` pixi feature and carries the comment block with it. FR-18's fifth substitution — filesystem-backed object storage — is also Epic 7's, not Epic 3's (`epics.md:225`). **These are traceability markers, not acceptance conditions for this story.**

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.8]
- [Source: _bmad-output/planning-artifacts/epics.md:99] — FR-50.
- [Source: _bmad-output/planning-artifacts/epics.md:184] — R-1 restated in the epic preamble: "object storage is in three of six combinations and cannot be dropped", with the ordered escalation.
- [Source: _bmad-output/planning-artifacts/epics.md:237] — Epic 1 carries the R-1 spike as an early long-pole story.
- [Source: _bmad-output/planning-artifacts/epics.md:273] — Epic 7 "builds object storage greenfield on whatever Epic 1's R-1 spike concluded."
- [Source: _bmad-output/planning-artifacts/epics.md:225] — FR-18's fifth substitution is delivered in Epic 7, not Epic 3.
- [Source: _bmad-output/planning-artifacts/epics.md:341] — CG-2's discipline: a silently narrowed claim is worse than a bounded one.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-1 in full.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Stack] — django-storages 1.14.6 / boto3 1.43.65, Django 6.0, Python 3.14.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-3] — the shared solve-group.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — supply chain, rationale.

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Claude Opus 5, 1M context)

### Debug Log References

- `pixi run spike-storage` — **23 passed, 1 skipped in 0.21 s**. The one skip is
  the round-trip leg; its message is reproduced verbatim under the verdict
  below. Nothing else in the spike is conditional.
- `pixi install -e spike-storage` — solved in 16 s.
  `django-storages-1.14.6-pyhd8ed1ab_0.conda` from conda-forge, in all three
  lock environments. No new `pypi:` entry: `pixi.lock` still holds exactly one,
  the editable self-install.
- Versions read back from the installed distributions in the spike environment,
  not looked up: `django-storages 1.14.6`, `boto3 1.43.65`, `botocore 1.43.65`,
  `Django 6.0.8`, `Python 3.14.6`. All four match the spine's Stack table.
- `pixi run test` — 213 passed (was 205 before this story; +4 in
  `test_dependency_policy.py`, +2 in `test_gate_contract.py`, +2 from
  `test_suite_policy.py`'s widened parametrize).
- `pixi run format` / `pixi run lint` / `pixi run typecheck` — clean. Two ruff
  findings fixed en route, both `RUF100` (unused `# noqa: S105` on the two
  `AWS_SECRET_ACCESS_KEY` dict entries — ruff's hardcoded-password rule does not
  in fact fire on that key).
- `pixi run docs` — builds clean under `--strict`. The new intra-document anchor
  `#object-storage-fitness-r-1` was verified against the generated
  `site/development/index.html` rather than assumed.
- `pixi run ci` — **exit 0**. `test-cov`: 285 passed, total coverage **92.46%**
  against the 90% floor. Unchanged from Story 1.7's 92.46%, as expected: nothing
  under `src/` was touched.
- One failed intermediate run, recorded because the fix is load-bearing:
  `pixi run ci` initially aborted with `the task 'ci' is ambiguous` — see the
  first Completion Note.
- **Every new rule was verified by mutation rather than by inspection.** Ten
  mutations in total, each confirmed to fail a *named* assertion and then
  reverted:
  the verdict comment upgraded from `proven with a stated bound` to `proven`;
  the verdict block hoisted above the table header so `_rationale` cannot reach
  it; `django-storages` added to `[dependencies]`; `solve-group` dropped from
  the spike environment; a `test_leak.py` dropped into `tests/spikes/`;
  `python_files` widened with `spike_*.py`; a second `pytest.skip` added to the
  spike; the recorded parameter-rename set emptied; `VERDICT_VERSIONS` changed
  to claim Django 6.1; and a method the backend does not have added to
  `STORAGE_METHODS`. All bit.
- **The round-trip leg was proved live, not merely skippable.** Re-run with
  `AWS_S3_ENDPOINT_URL=http://127.0.0.1:9`, it stops skipping, reaches the wire
  and fails with `botocore.exceptions.EndpointConnectionError` on `save` — so
  the leg genuinely performs I/O when an endpoint exists, and the skip is the
  only thing standing between it and a real bucket.

### Completion Notes List

- **Verdict: `proven with a stated bound`.** The bound is the round-trip leg. All
  mandatory no-network legs pass against `django-storages 1.14.6` / Django 6.0.8
  / Python 3.14.6 / boto3 1.43.65; the `save` → `exists` → `open` → `size` →
  `url` → `delete` cycle against a live S3-compatible endpoint **did not run**,
  because no endpoint was stood up and the instructions for this run forbade
  standing one up. So the wire protocol against a real bucket is unproven. The
  skip reports it in those words, and so do `pixi.toml` and `docs/development.md`.
  Epic 7 Story 7.5 may proceed on the channel build; it should close the bound
  against a MinIO container as its first act.

- **`pixi run ci` broke, and the fix is a new dependency-free `gate` feature.**
  The `spike-storage` environment layers the `dev` *feature*, so every task in
  `[feature.dev.tasks]` became visible from two environments. Fifteen of them
  survived that, because each pins `default-environment`. `ci` cannot: pixi
  rejects `default-environment` on a task that declares only `depends-on`
  (`Unexpected keys, expected only 'cmd', 'depends-on', 'description', 'args'` —
  verified, not assumed), which is exactly what
  `test_every_gate_step_pins_its_environment`'s docstring already says. `pixi
  run ci` therefore failed with `the task 'ci' is ambiguous` before running a
  single step. `ci` now lives in `[feature.gate.tasks]`, a feature with no
  dependencies whose only member is the `dev` environment, so the gate is
  reachable from exactly one environment again. **This is not spike-specific
  scaffolding.** Epic 8 Story 8.1's six-environment matrix would have hit the
  same wall the moment any of those six carried the dev toolchain; the `gate`
  feature is the general fix and should survive the spike's deletion. Everything
  Story 1.1 asserts about the gate is untouched — `test_gate_contract.py`'s
  `_all_tasks` already walked every feature, and all its assertions still pass.

- **The spike is kept out of the gate by module *name*, not by a pytest flag,
  and neither option the spec offered was usable as written.** `-m "not spike"`
  on `test-cov` is banned: `tests/unit/test_coverage_policy.py` lists `-m` in
  `NARROWING_FLAGS` and fails the floor-carrying task for carrying any of them,
  on Story 1.5's reasoning that a floor over a filtered suite is not a floor.
  And `testpaths` is not the mechanism the spec assumed — `test-cov` runs
  `pytest tests/`, naming the directory on the command line, and pytest ignores
  `testpaths` whenever paths are given. Changing `testpaths` would have changed
  nothing at all. So the spike module is named
  `tests/spikes/spike_django_storages_fitness.py`: `python_files` matches
  `test_*.py` and `tests.py` only, and pytest collects a non-matching file
  solely when it is an *initial* path on the command line — which
  `pixi run spike-storage` makes it and `pytest tests/` never does. The
  directory stays where the spec's Source Tree table puts it. Two new
  assertions in `test_gate_contract.py` hold the mechanism from both sides: no
  module in `tests/spikes/` may match `python_files`, and `python_files` may not
  grow a pattern matching `spike_*.py`.

- **No coverage `omit` entry was needed, verified rather than assumed.**
  `[tool.coverage.run] include = ["src/**"]` and `test-cov`'s `--cov=src` both
  bound measurement to `src/`, so nothing under `tests/` is measured whatever
  `omit` says; `*/tests/*` at `pyproject.toml:267` covers it a second time in
  any case. Story 1.5's closed `CLOSED_OMIT` list is untouched, which was the
  outcome the Testing Requirements section asked for.

- **`tests/unit/test_suite_policy.py` was widened rather than side-stepped.**
  Its scan globs `test_*.py` and `conftest.py`, so a directory named
  `spike_*.py` would have been beyond the reach of Story 1.2's ban on
  `pytest.skip` / `xfail` / vendor-branching — the naming that keeps the gate
  green would also have opened a door that closes by convention. `_test_modules`
  now globs `spike_*.py` too, and the spike's one `pytest.skip` is entered in
  `RECORDED_EXEMPTIONS` with its reasoning, counted at one. A second skip in
  that file fails the gate; deleting this one fails it from the other side.

- **The spec's line references were stale, again, and every one was re-verified.**
  `[environments]` is at `pixi.toml:221-224`, not `:141-143`; `test-cov` is at
  `:286`, not `:196`; `[dependencies]` runs `:14-93`, not `:14-80`;
  `[pypi-dependencies]` is `:111-112`, not `:98-99`. In `pyproject.toml`,
  `testpaths` is `:205` (not `:150`) and `markers` was `:210-212` before this
  story added to it (not `:155-157`). The `django-celery-beat` precedent the spec cites at
  `pixi.toml:22-34` is at `:25-38`, and — as Story 1.7 established — it is a
  *retired* exception living in `[dependencies]`, not a live one. The new
  comment block follows its shape (what was wrong, what fixed it, what the
  solver now enforces) without describing the project as carrying an exception:
  it carries zero, and this story added none.

- **`boto3` was not declared, and did not need to be.** It arrives in the
  spike environment behind `django-storages`' own conda recipe at exactly the
  1.43.65 the Stack table names — the same version `django-anymail` already
  locks, which is what the shared `solve-group` guarantees. The spike imports
  `boto3` only to read its version back for the verdict assertion.

- **A real finding for Epic 7 Story 7.5, discovered by running the spike rather
  than reading the source.** `django-storages` 1.14.6 reads only *two* of the
  five configuration values from the process environment on its own —
  `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, via its internal
  `lookup_env`. `endpoint_url`, `region_name` and `bucket_name` are read from
  **Django settings alone**. So FR-38's "environment variables alone" is not
  something the package delivers by itself: the application has to route those
  three from the environment into `STORAGES["default"]["OPTIONS"]`. The spike
  does exactly that, and `_options_from_environment` is the shape Story 7.5
  needs to reproduce in `config/settings/`.

- **One API divergence, recorded rather than failed on or hidden.** `S3Storage`
  spells Django's `Storage.listdir(self, path)` as `listdir(self, name)`. Every
  positional call binds — and positional is the only kind Django and the feature
  make — but `listdir(path=...)` would raise `TypeError`. Failing the spike on it
  would have overstated a breakage; passing silently would have been the
  narrowed claim CG-2 forbids. So the spike asserts positional compatibility by
  *binding* the minimal and maximal calls Django's base signature permits, and
  separately freezes the set of parameter renames at exactly this one. A second
  rename fails; this one disappearing fails too.

- **`pixi.toml`'s verdict block sits *below* the table header, not above it.**
  Story 1.7's `_rationale` reads adjacency strictly and stops at anything that is
  not a `#` comment — including a `[table]` header. A block written above
  `[feature.spike-storage.dependencies]` would have been invisible to
  `test_the_spike_verdict_is_recorded_beside_the_declaration`, and AC #1's
  "recorded where the dependency is declared" would have been satisfied only to
  the eye. Caught by running the test, not by reading.

- **The verdict vocabulary is closed and the reader is ordered longest-first.**
  "proven with a stated bound" contains "proven", so a naive scan would have
  reported the strongest of the three verdicts for a record saying the opposite —
  silently, on a green suite. `test_the_verdict_reader_does_not_read_a_bound_as_full_coverage`
  pins the ordering; `_recorded_verdict` returns `None` for a fourth, softer
  outcome rather than accepting it.

- **The feedstock push is *not* outstanding.** R-1's escalation step 2 is
  triggered only by a failed verdict, and the verdict is not failed. No
  conda-forge issue or PR was opened, and none is required. The ladder is
  written into `docs/development.md` in R-1's own order regardless, per Task 4.

- **Variance recorded for Epic 8 Story 8.1, as the Project Structure Notes ask.**
  `[feature.spike-storage]` should be **removed**, not folded into Epic 7's
  `storage` feature. Story 7.5 moves the `django-storages` declaration and its
  verdict comment into `storage`; what remains here — the environment, the task
  and `tests/spikes/` — is machinery whose question has been answered, and
  keeping it would leave a seventh environment shape beside AD-3's six. The
  `gate` feature introduced above is the opposite case and should stay.

- **Test disposition, recorded for Epic 7 Story 7.1 rather than decided here:**
  `tests/spikes/` is `machinery` in its entirety. A spike is accelerator work and
  never travels to a component. Stated in the package docstring and in
  `docs/development.md`.

---

#### Review pass — 19 triaged findings applied (2026-08-16)

Three adversarial reviewers ran against the diff since `90cb6c2`. Nineteen
findings were triaged as *patch*; all nineteen were re-verified against the code
before being fixed, and all nineteen were real. **The verdict did not move** —
it is still `proven with a stated bound` — but three recorded claims did, because
they said more than the spike proved. CG-2 governed every one of them: the record
was made accurate rather than the tests inflated to match the record.

- **The verdict's versions are now tied to the gate (H1).** The only check that
  the runtime matches the verdict lived inside the spike, and the spike runs in
  no automated path: `ci.yml` pins `environments: dev`, so `pixi run ci` never
  enters `spike-storage`. Meanwhile `django = ">=6.0,<7"` admits a 6.1 on
  re-solve — and an untracked story file proposing exactly that (a move to the
  5.2 LTS series) is already sitting in `_bmad-output/`. The verdict's `Tested
  against:` line is now *parsed* out of the comment and reconciled, per platform,
  against `pixi.lock` for the `spike-storage` environment, at the verdict's own
  precision: `Django 6.0` is satisfied by a locked `6.0.8` and not by `6.1.0`.
  Dropping a package name from that line fails too, so the reconciliation cannot
  be narrowed by editing the record.
- **The round-trip leg can no longer reach a real bucket by accident (H2).** It
  preferred ambient values (`os.environ.get(v) or FALLBACK[v]`), so a developer
  with an AWS profile exported ran the documented command straight at their own
  bucket — and with `file_overwrite` defaulting to True, `save()` would have
  silently replaced a pre-existing object at the fixed key `spike/r1-round-trip.txt`
  before teardown deleted it. Now: an explicit `SPIKE_STORAGE_ROUND_TRIP` opt-in
  arms the leg *and* is the only thing that lets ambient values in at all;
  `file_overwrite` is False; the key carries a fresh UUID and is asserted free
  before the write; teardown deletes the key it *meant* to write as well as
  whatever `save()` returned, so an object created by a `save()` that then raised
  is still removed; and a `client_config` with a 5 s connect timeout and one
  attempt replaces botocore's 60 s × retry budget, so the documented "point it at
  MinIO" remedy fails in under a second rather than hanging. "Leaves the bucket
  as it found it" is restated precisely in all three places that claimed it.
- **The FR-38 claim was circular, and the corrected fact is now in the record
  (H3).** The old test built the backend as `backend(**_options_from_environment())`
  — all five values as explicit kwargs — and `BaseStorage.__init__` applies
  explicit kwargs *last*, so a value coming from a Django setting, a boto3
  profile or a package default was unreachable by construction. "Moving every
  variable" could only move what the test itself injected. The leg is split in
  two: the moving half is kept and renamed for what it proves, and a new leg
  *withholds* each option in turn. `access_key` and `secret_key` survive the
  withholding (django-storages' `lookup_env`); `endpoint_url`, `region_name` and
  `bucket_name` come back `None` — and a value planted in
  `settings.AWS_STORAGE_BUCKET_NAME` arrives, proving the source is Django
  settings. So FR-38 is the *application's* job. That fact was in the Completion
  Notes and nowhere else; it is now in the verdict block and in
  `docs/development.md`.
- **`run_checks()` is recorded as a weak signal (M1).** Verified empirically:
  with `STORAGES["default"]["BACKEND"] = "nonexistent.module.NoSuchStorage"`,
  `run_checks()` returns `[]`. Django never instantiates a storage backend during
  system checks; the only check reading `STORAGES` is
  `staticfiles.checks.check_storages`, on the `staticfiles` alias. The spec
  mandates the assertion, so it stays — with the docstring, the verdict block and
  the docs all saying what it can and cannot show.
- **"Positional calls — the only kind Django and the feature make" was false, in
  three places (M2).** `django/db/models/fields/files.py:98` calls
  `self.storage.save(name, content, max_length=…)` and
  `django/core/files/storage/base.py:43` calls
  `self.get_available_name(name, max_length=…)`. The *conclusion* survives —
  `listdir` is not one of those call sites — but the stated reason was the part a
  future reader would reuse for the next rename. Corrected in the spike,
  `pixi.toml` and `docs/development.md`, and now asserted rather than described:
  `DJANGO_KEYWORD_CALL_SITES` is checked both against the recorded rename set
  (a collision is a failure, not a record) and against the backend's own
  signatures.
- **The skip gate is no longer a string coupling (M3).** `endpoint.endswith(".invalid")`
  worked only because the fallback constant happened to end that way: adding a
  port to it — the obvious "wire it to MinIO" edit — would have armed the leg
  against an unresolvable host, and a real endpoint at an internal `.invalid`
  name would have been skipped while the bound was reported unclosed. The gate is
  the opt-in; when armed against the fallback endpoint it fails with a message
  saying so rather than reaching the wire.
- **Two of the eight "contract" methods were compared against themselves (M4).**
  `S3Storage.save` and `S3Storage.open` are the *identical function objects* as
  Django 6.0's — django-storages overrides `_save`/`_open`, not the public
  methods — so for 2 of 8 the signature checks bound Django against Django. The
  set is now detected and frozen (`INHERITED_FROM_DJANGO`), the verdict says
  which two prove nothing about the package, and a new leg binds the
  two-argument call Django's base class makes to `_save` and `_open`, where the
  real behaviour lives.
- **boto3 is now genuinely exercised (M5).** It was imported only to read
  `__version__`; `S3Storage.connection` is lazy, so session construction,
  endpoint resolution, the credential chain and the signer were all unexercised
  while `boto3 1.43.65` sat in the verdict's "Tested against" line reading as
  coverage. Verified it runs offline (0.05 s against `.invalid`) rather than
  assumed, then added a mandatory leg that touches it. Mutation-checked: pointing
  the fallback endpoint at `"not a url at all"` fails that leg and no other.
- **The `gate` feature's invariant is asserted (M6).** The Completion Note above
  argues at length that `ci` must be reachable from exactly one environment and
  nothing enforced it — while Epic 8's six-environment matrix is the same change
  six times over. `test_the_gate_task_is_reachable_from_exactly_one_environment`
  now reads `[environments]` and counts. Its sibling
  `test_every_task_with_a_command_pins_its_environment` closes the related hole:
  the documented "every task declares `default-environment`" rule covered 6 of 18
  tasks by assertion, and `changelog` — which `release.yml` invokes — would have
  broken only at release time, with the gate green.
- **`docs/development.md` no longer contradicts the mechanism this story
  introduced (M7).** "You never need `-e` for a task. Every task declares
  `default-environment`" was the belief that produced the ambiguity failure: `ci`
  declares none and *cannot*. The paragraph now names both mechanisms, says which
  applies to `ci`, and points at the rule.
- **"Staged, not committed to" now covers every dependency table (M8).** It
  checked `[dependencies]` and `[pypi-dependencies]` only; adding
  `django-storages` to `[feature.dev.dependencies]` — the environment the whole
  product suite runs in — passed cleanly. The module's own `DEPENDENCY_TABLE`
  regex already knew the per-feature and per-target variants, so the new
  assertion reads every table and requires exactly one declaration site.
- **The two copies of the verdict are reconciled (M9).** Nothing under `tests/`
  read `docs/development.md`. When the bound is closed, `pixi.toml` and
  `test_dependency_policy.py` move together by design and the docs were free to
  keep saying "proven with a stated bound" — to precisely the reader the docs
  copy exists for.
- **The solve-group is checked against what was solved, not only what was
  declared (M10).** `test_lock_file_resolves_every_declared_dependency` checks
  each environment against the declared *range* independently, so `django 6.0.8`
  in `dev` and `6.1.0` in `spike-storage` both passed. Every package resolved in
  more than one environment must now resolve to one version, per platform.
- **The gate-collection guard recurses and finds its own directories (L1).**
  `SPIKE_DIRECTORY.glob("*.py")` did not descend, so `tests/spikes/s3/test_helpers.py`
  would have been collected by the gate while the test written to prevent exactly
  that went on passing. Verified by creating that file.
- **The spike task's target is reconciled with the tree (L2).** A rename that
  updated the `RECORDED_EXEMPTIONS` key but missed the task would have left the
  gate green and `pixi run spike-storage` — the one command the verdict tells
  Story 7.5 to re-run — failing with "file or directory not found".
- **The feature's reasoning and exit condition moved below the table header
  (L3).** `_rationale` stops at a `[table]` header, so the block written *above*
  `[feature.spike-storage.dependencies]` was invisible to every assertion and
  could have been deleted with the suite green — the trap this story's own notes
  describe applying to the verdict and not to the reasoning. Reworded to drop the
  word "exception" (which would have armed `EXCEPTION_WORD` and classified the
  package as a supply-chain carve-out, which it is not), and
  `test_the_spike_verdict_is_recorded_beside_the_declaration` now requires the
  exit condition to be there.
- **The removal plan carries its own cost (L4).** Deleting
  `[feature.spike-storage]` breaks nine assertions across three test modules.
  The list is recorded beside the declaration in `pixi.toml` — where the person
  doing the removal will be looking — and in `docs/development.md`.
- **The deprecation leg can now see boto3 and botocore (L5).** It evicted only
  `storages*` from `sys.modules`; boto3 and botocore stayed imported from the
  module-level import, so their import-time warnings fired once before any
  recorder existed and were checked against silence they got for free — while the
  verdict named boto3 as a version it is a statement about. All three are evicted
  and re-imported inside the recorder, with a guard that fails if the eviction
  list finds nothing.
- **Story 7.5's `ImproperlyConfigured` obligation is recorded where it will be
  read (L6).** `_options_from_environment` raises a bare `KeyError`, and it is
  explicitly nominated as "the shape Story 7.5 has to reproduce" — reproduced
  verbatim, a deployment missing `AWS_STORAGE_BUCKET_NAME` dies at
  settings-import with an opaque `KeyError` instead of Django's
  `ImproperlyConfigured`. Noted in the helper's docstring, in the verdict block
  and in the docs, and the current behaviour is pinned by a test so the
  requirement rests on a fact rather than a reading.

- **Every new assertion was mutation-verified, and one rule could not be.**
  Sixteen mutations, each confirmed to fail a *named* assertion and then
  reverted: the verdict's Django bumped to 6.1; boto3 dropped from the "Tested
  against" line; `django-storages` added to `[feature.dev.dependencies]`; the
  exit condition removed; the docs verdict downgraded to unbounded "proven"; the
  `gate` feature added to a second environment; `changelog` stripped of its
  `default-environment`; the spike task pointed at a renamed module;
  `tests/spikes/s3/test_helpers.py` created; the inherited-method set narrowed to
  `{"save"}`; the `_save` hook arity claimed as three; `("listdir", "path")`
  added to the keyword call sites; `bucket_name` claimed as environment-sourced;
  `os.environ[...]` softened to `.get(..., "")`; the warning-eviction list
  emptied; and the fallback endpoint set to `"not a url at all"` (which failed
  the boto3 client leg and no other, which is what shows that leg reaches
  botocore). The round-trip leg was re-proved live against
  `AWS_S3_ENDPOINT_URL=http://127.0.0.1:9` with the opt-in set — it stops
  skipping, reaches the wire and fails with `EndpointConnectionError` in under a
  second — and re-proved *inert* with the same ambient values and no opt-in,
  where it skips as before.
  **The exception is the two lock-reading rules (H1's reconciliation plumbing and
  M10).** `pixi.lock` cannot be mutated for a test: `pixi run` re-solves and
  rewrites it before the task starts, so an edited lock is restored before pytest
  opens it — confirmed by trying, twice. Both rules were therefore split into
  helpers (`_verdict_drift`, `_cross_environment_divergences`) and exercised
  against a synthetic lock shaped exactly as `_resolved_packages` returns,
  covering agreement, a bumped release line, an absent package and a legitimate
  per-platform difference.

- **Final state.** `pixi run ci` — exit 0, **297 passed**, coverage **92.46%**
  against the 90% floor (unchanged; nothing under `src/` was touched).
  `pixi run spike-storage` — **30 passed, 1 skipped** (was 23 / 1). `pixi run
  test` — **225 passed** (was 213: +10 in `test_dependency_policy.py`, +2 in
  `test_gate_contract.py`). `pixi run docs` builds clean under `--strict`. No
  assertion was weakened or deleted, no dependency was added, and
  `[pypi-dependencies]` still holds exactly one entry.

### File List

- `pixi.toml` — UPDATE. New `[feature.spike-storage.dependencies]` carrying
  `django-storages = ">=1.14.6,<2"` and, immediately above the declaration, the
  R-1 verdict block (versions, call sites, class path, recorded divergence,
  bound, escalation pointer) plus the feature's own reasoning and exit
  condition. New `spike-storage` entry in `[environments]`
  (`features = ["dev", "spike-storage"]`, `solve-group = "default"`). New
  `[feature.spike-storage.tasks] spike-storage`. `ci` moved from
  `[feature.dev.tasks]` into a new dependency-free `[feature.gate.tasks]`, and
  `dev` gained the `gate` feature — unchanged in content, order and description.
  `[dependencies]` and `[pypi-dependencies]` untouched.
- `pyproject.toml` — UPDATE. `[tool.pytest.ini_options] markers` gains `spike`,
  with a comment recording why the gate cannot reach it. Nothing else changed;
  `testpaths` and `python_files` are as they were.
- `tests/spikes/__init__.py` — NEW. Package marker, plus the naming convention
  and the `machinery` disposition.
- `tests/spikes/spike_django_storages_fitness.py` — NEW. The spike: version
  assertion, import and instantiation, `STORAGES["default"]` /
  `default_storage` resolution, per-method presence and positional-signature
  binding against Django 6.0's `Storage`, the frozen parameter-rename set, the
  fresh-import warnings check, `run_checks()`, environment-only configuration
  proved by moving every value, and the conditional round-trip leg with
  teardown. 24 tests.
- `tests/unit/test_dependency_policy.py` — UPDATE. 14 tests to 18. Adds
  `_recorded_verdict` and the R-1 constants, plus
  `test_the_storage_spike_is_staged_rather_than_committed_to`,
  `test_the_spike_environment_shares_the_solve_group`,
  `test_the_spike_verdict_is_recorded_beside_the_declaration` and
  `test_the_verdict_reader_does_not_read_a_bound_as_full_coverage`. No existing
  test or docstring changed.
- `tests/unit/test_gate_contract.py` — UPDATE. Adds
  `test_the_storage_spike_is_not_a_gate_step` and
  `test_the_gate_cannot_collect_the_storage_spike`, and the `fnmatch` /
  `PYPROJECT` reads they need. No existing test changed.
- `tests/unit/test_suite_policy.py` — UPDATE. `_test_modules` now globs
  `spike_*.py`; `RECORDED_EXEMPTIONS` gains the spike's one `pytest.skip`, with
  its reasoning.
- `docs/development.md` — UPDATE. New `### Object storage fitness (R-1)`
  subsection under "Supply chain": verdict, what was proven, the bound, the
  recorded divergence, the ordered escalation ladder, where the verdict lives
  and how to run the spike. The "Channel presence alone is not fitness"
  paragraph is rewritten as FR-50's standing rule with its concrete failure mode
  and an explicit statement that its forward-looking half is a documented
  obligation rather than an automated assertion. "Environment" now describes
  three environments; the Tasks table gains `pixi run spike-storage`; the Tests
  section gains `tests/spikes/`.
- `pixi.lock` — UPDATE, generated. Re-solved by `pixi install -e spike-storage`.
  Adds the `spike-storage` environment and `django-storages 1.14.6` from
  conda-forge on all three platforms. Still exactly one `pypi:` entry.

#### Review pass — files changed (2026-08-16)

No new files, no deletions, and `pixi.lock`, `pyproject.toml` and
`tests/spikes/__init__.py` were not touched.

- `tests/spikes/spike_django_storages_fitness.py` — UPDATE. 24 tests to 31.
  Round-trip leg rebuilt around the `SPIKE_STORAGE_ROUND_TRIP` opt-in, a
  UUID-bearing key, a pre-write existence check, `file_overwrite = False`, a
  short-timeout `client_config` and leak-proof teardown; the fixture ignores
  ambient AWS values unless the opt-in is set. New legs:
  `test_the_methods_the_backend_inherits_unchanged_are_the_recorded_ones`,
  `test_the_internal_hooks_accept_the_call_djangos_base_class_makes` (× 2),
  `test_the_renamed_parameter_is_not_one_django_passes_by_keyword`,
  `test_configuration_reaches_the_backend_from_the_environment_and_from_django_settings`,
  `test_a_missing_variable_is_a_named_failure_rather_than_a_silent_default` and
  `test_the_backend_builds_a_boto3_client_without_touching_the_network`.
  `test_the_backend_is_configured_from_the_environment_alone` renamed to
  `test_moving_every_environment_variable_moves_the_whole_configuration` for what
  it actually proves. The warnings leg now evicts boto3 and botocore as well as
  storages. New constants: `INHERITED_FROM_DJANGO`, `INTERNAL_HOOK_ARITY`,
  `ENVIRONMENT_SOURCED_OPTIONS`, `ROUND_TRIP_OPT_IN`, `ROUND_TRIP_TRUTHY`,
  `WARNING_SENSITIVE_PACKAGES`, `DJANGO_KEYWORD_CALL_SITES`; new helpers
  `_round_trip_is_armed` and `_safety_options`. The `run_checks` docstring and
  the parameter-rename comment record what they do and do not show. One
  `pytest.skip`, unchanged in count.
- `tests/unit/test_dependency_policy.py` — UPDATE. 18 tests to 25. Adds
  `test_the_storage_spike_is_declared_in_no_other_dependency_table`,
  `test_the_recorded_verdict_names_the_versions_the_lock_resolves`,
  `test_every_shared_package_resolves_to_one_version_across_environments`,
  `test_the_docs_copy_of_the_verdict_matches_the_manifest`, and four
  helper-level tests (`_tested_against`, `_is_same_release_line`,
  `_verdict_drift`, `_cross_environment_divergences`, `_docs_section`). New
  helpers of the same names; new constants `DEVELOPMENT_DOCS`,
  `DOCS_VERDICT_HEADING`, `TESTED_AGAINST_PREFIX`, `VERDICT_VERSION_PACKAGES`,
  `TESTED_AGAINST_ENTRY`, and a new `docs` fixture. `BOUND_PHRASES` gains
  `spike_storage_round_trip`. `test_the_spike_verdict_is_recorded_beside_the_declaration`
  gains a fourth property: the staging must record its exit condition. No
  existing assertion was weakened.
- `tests/unit/test_gate_contract.py` — UPDATE. 22 tests to 24. Adds
  `test_the_gate_task_is_reachable_from_exactly_one_environment`,
  `test_every_task_with_a_command_pins_its_environment` and
  `test_the_spike_task_names_a_file_that_exists`;
  `test_the_gate_cannot_collect_the_storage_spike` now recurses and discovers
  spike directories rather than reading one hard-coded path. New helpers
  `_feature_declaring`, `_environments_carrying`, `_spike_directories`; new
  constants `TESTS_ROOT`, `GATE_TASK`.
- `tests/unit/test_suite_policy.py` — UPDATE, comment only. The
  `RECORDED_EXEMPTIONS` note for the spike now describes the opt-in gate and why
  it replaced the endpoint-variable gate. The count is still one.
- `pixi.toml` — UPDATE, comments only; no dependency, task or environment
  changed. The spike feature's reasoning and exit condition moved *below*
  `[feature.spike-storage.dependencies]` so `_rationale` can reach them, reworded
  to avoid the word "exception", and extended with the cost of removing the
  feature. The verdict block records: the gate-side version reconciliation, the
  two inherited methods, the keyword call sites Django actually makes, the
  `run_checks` weak signal, FR-38 as the application's job with Story 7.5's
  `ImproperlyConfigured` obligation, the opt-in bound, and what the live leg does
  to a bucket.
- `docs/development.md` — UPDATE. The "you never need `-e`" paragraph rewritten
  to name both mechanisms and why `ci` uses the second one. The "Object storage
  fitness (R-1)" section gains the same six corrections as the verdict block,
  plus a "Removing it, and what that costs" paragraph.

## Review Triage Log

### 2026-08-16 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 19: (high 3, medium 10, low 6)
- defer: 0
- reject: 1: (high 0, medium 0, low 1)
- addressed_findings:
  - `[high]` `[patch]` The recorded verdict named four versions that nothing in
    `pixi run ci` checked — the only reconciliation lived in the spike, which no
    automated path runs. Django and django-storages both admit a bump on
    re-solve, so the verdict could certify a runtime nobody ran while the gate
    stayed green. Found independently by all three hunters. Added
    `test_the_recorded_verdict_names_the_versions_the_lock_resolves`, which
    parses the `Tested against:` line and reconciles it against
    `_resolved_packages(lock)["spike-storage"]` per platform.
  - `[high]` `[patch]` The round-trip leg could write to, overwrite in, and
    delete from a real production bucket. The fixture preferred ambient AWS
    values, `S3Storage` defaults `file_overwrite = True`, and the key was fixed —
    so a developer with AWS variables already exported would, on the docs' own
    instruction, destroy a pre-existing object at that key. Now armed only by an
    explicit `SPIKE_STORAGE_ROUND_TRIP` opt-in, which is also the only thing that
    lets ambient values in; `file_overwrite = False`, a `uuid4` key asserted free
    before the write, leak-proof teardown, and a 5s connect timeout.
  - `[high]` `[patch]` The FR-38 "configured from the environment alone" leg was
    circular — every option was passed as an explicit kwarg, which shadows every
    other source, so no non-environment source was reachable by construction and
    the leg could not fail. Split into a renamed test for what it really proves
    plus a new one that withholds each option in turn. The real fact —
    django-storages reads only the two credential variables itself, making FR-38
    the application's job — moved from the Completion Notes into the verdict.
  - `[medium]` `[patch]` The `run_checks()` leg is vacuous: Django never
    instantiates a storage backend during system checks, and `run_checks()`
    returns `[]` even for a backend path that does not exist. The assertion is
    spec-mandated so it stays, but it is now recorded as a weak signal rather
    than as evidence of fitness.
  - `[medium]` `[patch]` "Positional calls — the only kind Django and the feature
    make" was false and repeated in three places; Django's file field calls
    `save(..., max_length=...)` and `get_available_name(..., max_length=...)` by
    keyword. The conclusion held but the rationale did not. Corrected and made
    assertable via `DJANGO_KEYWORD_CALL_SITES`.
  - `[medium]` `[patch]` The round-trip skip gate was an undeclared coupling to
    the `.invalid` suffix of a constant 360 lines away, not the "variable is
    unset" condition every docstring claimed. Now gated on identity.
  - `[medium]` `[patch]` `S3Storage.save` and `.open` are the identical function
    objects as Django's — django-storages overrides `_save`/`_open` — so two of
    the eight contract methods were compared against themselves. The inherited
    set is now frozen and the internal hooks are bound.
  - `[medium]` `[patch]` boto3 was named in "Tested against" while no mandatory
    leg constructed a session or client. A leg now touches
    `configured_storage.connection`, verified to stay offline.
  - `[medium]` `[patch]` The `gate` feature's whole reason for existing — `ci`
    reachable from exactly one environment — was unasserted, as was the
    "every task declares `default-environment`" rule for 12 of 18 dev tasks.
    Both now hold.
  - `[medium]` `[patch]` `docs/development.md` still claimed every task declares
    `default-environment`, which `ci` cannot — the exact belief that produced the
    ambiguity failure this story had to fix.
  - `[medium]` `[patch]` The "staged, not committed to" assertion read two tables;
    `django-storages` in `[feature.dev.dependencies]` would have passed it.
  - `[medium]` `[patch]` The docs copy of the verdict was unasserted and could
    drift from the manifest copy — for exactly the reader it exists to serve.
  - `[medium]` `[patch]` `solve-group` was asserted in the manifest only; the
    lock was never checked for cross-environment version identity, so a
    divergence the shared group exists to prevent would have passed.
  - `[low]` `[patch]` The gate-collection guard was non-recursive and scoped to
    one hard-coded directory.
  - `[low]` `[patch]` Nothing checked that the spike task's `cmd` names a file
    that exists.
  - `[low]` `[patch]` The spike feature's reasoning and exit condition sat above
    the table header, where `_rationale` cannot see them — the same trap the
    implementation avoided for the verdict block and fell into here.
  - `[low]` `[patch]` The removal plan omitted its own cost: deleting the spike
    breaks nine assertions across three modules.
  - `[low]` `[patch]` The deprecation-warning leg evicted only `storages*`, so
    boto3/botocore import warnings fired before the recorder existed.
  - `[low]` `[patch]` `_options_from_environment` raises a bare `KeyError` on a
    missing variable and is nominated as the shape Story 7.5 copies; the
    `ImproperlyConfigured` obligation is now recorded and pinned.

## Auto Run Result

Status: done

### Implemented change

R-1's spike is built and its verdict is **proven with a stated bound**.
`django-storages` 1.14.6 imports, instantiates, resolves through
`STORAGES["default"]`, and conforms to Django 6.0's `Storage` contract on Python
3.14 — so Epic 7 Story 7.5 proceeds on the conda-forge build, and no
package-index exception is opened. The bound: the round-trip leg against a live
S3-compatible endpoint did not run, so the wire protocol against a real bucket
is unproven.

The dependency is staged rather than committed to. It lives in a dedicated
`[feature.spike-storage.dependencies]` joined to the shared `solve-group` (AD-3),
not in `[dependencies]`, and `[pypi-dependencies]` still holds exactly one entry.
The verdict — versions, call sites exercised, class path, the recorded `listdir`
divergence, and what is *not* proven — is a comment block beside the declaration,
where AC #1 requires it, mirrored into `docs/development.md` for a reader who
never opens `pixi.toml`. The ordered escalation ladder is written out whether or
not it is triggered, and FR-50's standing rule is recorded with the concrete
`django-storages` failure mode that motivated it, including an explicit statement
that its forward-looking half is a documented obligation with no mechanical test.

Keeping the spike out of `pixi run ci` needed a mechanism the spec did not
anticipate: `-m "not spike"` is banned by Story 1.5's `NARROWING_FLAGS`, and
`testpaths` is irrelevant because `test-cov` names paths on the command line.
Exclusion is by module name — `spike_*.py` does not match `python_files` — held
from both sides by gate-contract assertions.

### Files changed

- `pixi.toml` — UPDATE. New `[feature.spike-storage.dependencies]` with the R-1
  verdict block, the `spike-storage` environment, and the `spike-storage` task.
  `ci` moved into a new dependency-free `[feature.gate.tasks]` — see residual
  risks. No runtime dependency, channel or specifier changed.
- `pyproject.toml` — UPDATE. The `spike` marker registered.
- `tests/spikes/__init__.py` — NEW. Package marker recording the naming
  convention and the `machinery` disposition.
- `tests/spikes/spike_django_storages_fitness.py` — NEW. The spike: 30 passing
  legs plus the conditional round-trip.
- `tests/unit/test_dependency_policy.py` — UPDATE. Staging, solve-group,
  verdict-recorded, verdict-versions-match-the-lock, docs-matches-manifest,
  cross-environment version identity, and no-other-table assertions.
- `tests/unit/test_gate_contract.py` — UPDATE. The spike is not a gate step, the
  gate cannot collect it, the task names a file that exists, `ci` is reachable
  from exactly one environment, and every task with a `cmd` pins its environment.
- `tests/unit/test_suite_policy.py` — UPDATE. `_test_modules` now reaches
  `spike_*.py`, so the spike directory is not beyond the skip ban; the one
  `pytest.skip` is a counted, reasoned exemption.
- `docs/development.md` — UPDATE. New "Object storage fitness (R-1)" section;
  FR-50's standing rule; the three environments and the task table; the
  `default-environment` paragraph corrected.
- `pixi.lock` — UPDATE (generated). Re-solved for the spike environment; still
  exactly one `pypi:` entry, and no package moved in `default` or `dev`.

### Review findings

Three hunters (adversarial, edge-case, verification-gap) ran in parallel against
the diff. 19 patches applied, 0 deferred, 1 rejected. No intent gap and no spec
defect, so no repair loopback ran; `review_loop_iteration` stayed at 0.

The pattern all three converged on is the one this story is itself about: the
record claimed more than the tests proved. Three legs the verdict listed as
evidence could not fail — `run_checks()` never instantiates a backend, the FR-38
leg passed its own values in as kwargs, and two of the eight contract methods
were Django's own functions compared against themselves. Each was fixed by
narrowing the claim and strengthening the test, not by softening either. The
separate consequential find is that nothing in the gate tied the verdict to the
versions it names — and an untracked `1-9-django-runs-on-the-lts-release.md`
proposing Django 5.2 LTS makes that drift the next story, not a hypothetical.

The one finding with real-world consequence beyond the record: the round-trip leg
would arm on ambient AWS credentials and overwrite-then-delete a pre-existing
object at a fixed key. It now requires an explicit opt-in and cannot clobber.

### Verification performed

- `pixi run ci` — **exit 0**. 297 passed, coverage 92.46% against the 90% floor.
  Re-run by the orchestrator after the review pass, not only by the subagents.
- `pixi run spike-storage` — 30 passed, 1 skipped, against Django 6.0.8 and
  Python 3.14.6. The skip is the round-trip leg, its message naming the bound.
- `pixi run test` 225 passed; `format`, `lint`, `typecheck`, `docs --strict` all
  clean.
- 26 mutations across the two passes, each confirmed to fail a named assertion
  and reverted: verdict versions bumped, boto3 dropped from the tested-against
  line, `django-storages` promoted to `[dependencies]` and to
  `[feature.dev.dependencies]`, solve-group dropped, `gate` added to a second
  environment, `changelog` stripped of `default-environment`, the spike task
  pointed at a renamed module, a test module planted in `tests/spikes/s3/`,
  `python_files` widened, the inherited-method set narrowed, the keyword
  call-site set falsified, the exit condition deleted, the docs verdict
  downgraded, and the warning-eviction list emptied.
- The round-trip leg was proved live (reaches botocore and fails in under a
  second with the opt-in set) and proved inert (skips under real ambient AWS
  values without the opt-in). It is not decorative.
- `pixi.lock` was confirmed byte-identical across the review pass, and to carry
  `django-storages` in the `spike-storage` environment only.

### Residual risks

- **`pixi run ci` needed a structural fix that outlives this story.**
  `spike-storage` layers the `dev` *feature*, which made `ci` visible from two
  environments, and pixi rejects `default-environment` on a `depends-on`-only
  task — so `ci` aborted with `the task 'ci' is ambiguous` before running a step.
  `ci` now lives in a dependency-free `[feature.gate.tasks]` belonging to `dev`
  alone, and an assertion holds it there. Epic 8 Story 8.1's six-environment
  matrix hits the same wall; the `gate` feature should survive the spike's
  deletion.
- **The bound is real and unclosed.** Nothing has exercised the S3 wire protocol.
  Story 7.5 should close it against a MinIO endpoint before shipping object
  storage, by setting `SPIKE_STORAGE_ROUND_TRIP` and re-running.
- **A finding for Story 7.5, not for this story.** `django-storages` 1.14.6 reads
  only `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from the process
  environment; `endpoint_url`, `region_name` and `bucket_name` come from Django
  settings alone. FR-38's "environment variables alone" is therefore the
  application's job — `config/settings/` must reproduce
  `_options_from_environment`'s shape, and must raise `ImproperlyConfigured`
  rather than `KeyError` on a missing variable.
- **One recorded API divergence:** `S3Storage.listdir(self, name)` against
  Django's `Storage.listdir(self, path)`. Harmless because `listdir` is not among
  the methods Django calls by keyword — which is now asserted rather than
  assumed — and the rename set is frozen, so a second one fails.
- **The spike is temporary machinery with a removal cost.** Deleting
  `[feature.spike-storage]` breaks nine assertions across three test modules.
  That cost is recorded in `pixi.toml` and `docs/development.md` where whoever
  performs the removal will meet it.
