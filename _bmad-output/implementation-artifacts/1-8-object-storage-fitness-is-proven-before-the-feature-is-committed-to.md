# Story 1.8: Object-storage fitness is proven before the feature is committed to

Status: ready-for-dev

## Story

As a lead developer,
I want `django-storages` proven against the pinned Django and Python before object storage is built,
so that a feature six of twelve combinations will select is not committed to on the strength of a package that cannot run.

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

- [ ] Task 1 — Stage the spike dependency without committing the feature (AC: #1)
  - [ ] Add `django-storages = ">=1.14.6,<2"` to a **new, dedicated pixi feature** — `[feature.spike-storage.dependencies]` in `pixi.toml` — and add a matching `[environments]` entry `spike-storage = { features = ["dev", "spike-storage"], solve-group = "default" }`. The shared `solve-group = "default"` is mandatory (AD-3): without it the spike would resolve a different Django from the one it is meant to test.
  - [ ] **Do not add `django-storages` to `[dependencies]` in this story.** The whole point of FR-50 is that fitness is proven *before* the feature is committed to; putting it in the runtime dependency set is the commitment. Epic 7 Story 7.5 moves it there if and only if this spike passes.
  - [ ] Do not add `boto3` explicitly. `django-storages` is the direct importer, not this project's code, so the transitive-availability rule (spine §Consistency Conventions, Supply chain) does not require a direct declaration for it here. The spine's Stack table records `boto3 1.43.65` as already locked via `django-anymail`. If the solve reports it missing, declare it inside `[feature.spike-storage.dependencies]` alongside `django-storages`, never in `[pypi-dependencies]`.
  - [ ] Record the reasoning and the exit condition beside the new block, per the spine's Rationale convention and Story 1.7's AC #3: this feature exists to run R-1's spike, and its exit condition is the spike's recorded verdict.
  - [ ] Add a `spike-storage` pixi task: `pytest tests/spikes/test_django_storages_fitness.py -m spike` with `default-environment = "spike-storage"` and a `description` naming R-1.

- [ ] Task 2 — Exercise the call sites the feature will actually use (AC: #1)
  - [ ] FR-25 defines the surface: "Object storage attaches an S3-compatible backend configured from environment variables alone (`django-storages`, `boto3`); user media is out of scope." The spike therefore exercises the **default file storage backend**, configured through Django 6.0's `STORAGES` setting, from environment variables only.
  - [ ] Mandatory, no-network leg — all of these must run against the locked Django 6.0 and Python 3.14 and must pass without any S3-compatible server:
    - Import the backend module and instantiate the S3 storage class. Confirm the class path against the installed `django-storages 1.14.6` rather than assuming — 1.14.x ships both a legacy `storages.backends.s3boto3.S3Boto3Storage` and a `storages.backends.s3.S3Storage`; record which one exists and which the feature will name.
    - Configure it through `settings.STORAGES["default"]` with `BACKEND` and an `OPTIONS` dict sourced from environment variables (endpoint URL, region, bucket, access key, secret key), and assert Django resolves it via `django.core.files.storage.storages["default"]` and `default_storage`.
    - Assert the instance satisfies the `django.core.files.storage.Storage` contract for every method the feature calls: `save`, `open`, `exists`, `delete`, `url`, `size`, `listdir`, `get_available_name`. Assert each is present and that its signature is compatible with what Django 6.0's `Storage` base declares — this is the class of breakage a package predating Django 6.0 is most likely to exhibit.
    - Assert no `DeprecationWarning` or `RemovedInDjango*Warning` is raised on import or instantiation, with `warnings.catch_warnings(record=True)`. A removed-API warning here is the early signal of a Django 6.1 break.
    - Assert `django.core.checks.run_checks()` reports no error with the storage backend configured — the Django system check framework is where a settings-shape incompatibility surfaces.
    - Assert the backend reads its configuration from environment variables alone, with no configuration file (FR-38).
  - [ ] Optional round-trip leg, and **its absence must be reported, not hidden**: a `save` → `exists` → `open` → `size` → `url` → `delete` cycle against an S3-compatible endpoint. Gate it on an `AWS_S3_ENDPOINT_URL`-style environment variable being set; when unset, the test reports the bound explicitly rather than passing silently.
  - [ ] **State the bound in the recorded verdict.** CG-2's discipline applies: "A silently narrowed claim reads as full coverage and is worse than a bounded one" (`epics.md:339`). If only the no-network leg ran, the verdict says so and names what remains unproven.

- [ ] Task 3 — Record the verdict where the dependency is declared (AC: #1, #2)
  - [ ] AC #1's "recorded where the dependency is declared" means a comment block in `pixi.toml` beside the `django-storages` declaration. Write it there: the versions tested (django-storages 1.14.6, Django 6.0, Python 3.14 — from the spine's Stack table), the call sites exercised, the verdict, the date, and the bound (which legs did not run).
  - [ ] Also add an "Object storage fitness (R-1)" section to `docs/development.md` carrying the same verdict and the full escalation ladder, so a reader who never opens `pixi.toml` finds it.
  - [ ] The verdict must be one of exactly three: **proven** (all mandatory legs pass), **proven with a stated bound** (mandatory legs pass, round-trip unrun), or **failed** (any mandatory leg fails). Do not record a fourth, softer outcome.

- [ ] Task 4 — Author the ordered escalation, whatever the verdict (AC: #2, #3, #4)
  - [ ] Write the escalation ladder into `docs/development.md` verbatim in its ordering, whether or not it is triggered. R-1 states it: **spike** `1.14.6` against the locked Django and Python first, since it is a thin wrapper over a `boto3` already in the lock and Django's `Storage` API has been stable → if that fails, **push the conda-forge feedstock** as was done for `django-celery-beat`, with a **time-boxed** package-index exception whose exit condition is that build landing → **a component-owned S3 backend** against `django.core.files.storage.Storage` as the **last resort**, "because a platform product owning its own storage backend is a permanent maintenance and security cost." R-1 closes: "A permanent supply-chain exception is not on the list."
  - [ ] If and only if the verdict is **failed**: open the conda-forge feedstock issue/PR, record its URL beside the declaration, and add the time-boxed `[pypi-dependencies]` exception with its exit condition stated in a comment. Story 1.7's tests are written to require exactly that — an exception entry whose comment block names an exit condition. Do not add the exception pre-emptively on a passing verdict.
  - [ ] The `django-celery-beat` precedent is documented in this repository at `pixi.toml:22-34` and in `tests/unit/test_dependency_policy.py:55-65`. Follow its shape: what was wrong upstream, what build fixed it, and what the solver now enforces on its own.

- [ ] Task 5 — Make FR-50's general rule checkable (AC: #4)
  - [ ] Record FR-50 as a standing rule in the same `docs/development.md` supply-chain section Story 1.7 creates: before any feature is committed to, confirm **both** channel availability **and** fitness against the pinned runtime. "Presence alone is explicitly insufficient."
  - [ ] Name the failure mode concretely so a future reader recognizes it: `django-storages` is present on conda-forge — which is FR-50's availability test — and was released 2025-04-02 declaring support for neither Django 6.0 nor Python 3.14. Availability passed; fitness was unknown. That gap is what R-1 is.
  - [ ] This half of AC #4 is a documented rule, not an automated assertion — there is no mechanical test for "a future feature was proposed." Say so explicitly in the docs rather than writing a test that only appears to enforce it.

- [ ] Task 6 — Tests (AC: #1, #2, #3, #4)
  - [ ] New `tests/spikes/__init__.py` and `tests/spikes/test_django_storages_fitness.py`. Register a `spike` marker in `pyproject.toml [tool.pytest.ini_options] markers` alongside the existing `integration` marker at `:155-157`.
  - [ ] **Keep the spike out of `pixi run ci`.** `pyproject.toml:150` sets `testpaths = ["tests"]`, which would collect `tests/spikes/`; the `test-cov` task at `pixi.toml:196` runs `pytest tests/`. The spike needs the `spike-storage` environment, which the `dev` environment is not, so it would fail collection in the gate. Add `-m "not spike"` to the `test-cov` task's `cmd`, or place the spike outside `testpaths` — the dev agent chooses and records the choice. The gate must stay green and the spike must stay runnable via `pixi run spike-storage`.
  - [ ] The no-network leg is unit-scope in cost but crosses a package boundary; mark it `@pytest.mark.spike` only. The round-trip leg is `@pytest.mark.spike` **and** `@pytest.mark.integration`, and is conditional on the endpoint variable — express the condition with `pytest.skip` inside the test, carrying a comment that names the bound. Never `@pytest.mark.skip` and never `xfail`.
  - [ ] Extend `tests/unit/test_dependency_policy.py`: assert `django-storages` is **absent** from `[dependencies]` and from `[pypi-dependencies]` while the verdict is unrecorded, and that the `spike-storage` environment declares `solve-group = "default"`. Once the verdict is recorded, update the assertion to match the verdict's outcome and state which one it encodes.
  - [ ] Every temporary object the round-trip leg creates must be deleted in teardown; the integration leg must leave the bucket as it found it.

## Dev Notes

### Architecture Constraints

- **FR-50:** "Channel availability *and fitness against the pinned runtime* are checked before a feature is committed to."
- **R-1 — `django-storages` fitness is unproven, and object storage cannot be deferred.** Verbatim: "Present on the channel, which is FR-50's test, but released 2025-04-02 with no declared Django 6.0 or Python 3.14 support and nothing newer available; Django 6.0 support exists only on unreleased upstream master. Object storage appears in six of twelve combinations, does not exist yet, and is expected to be selected by most components — so dropping it is not an available answer and the risk must be carried rather than avoided. The escalation is ordered: spike `1.14.6` against the locked Django and Python first, since it is a thin wrapper over a `boto3` already in the lock and Django's `Storage` API has been stable; if that fails, push the conda-forge feedstock as was done for `django-celery-beat`, with a **time-boxed** package-index exception whose exit condition is that build landing; a component-owned S3 backend against `django.core.files.storage.Storage` is the last resort, because a platform product owning its own storage backend is a permanent maintenance and security cost. A permanent supply-chain exception is not on the list."
- **Why this is Epic 1 and not Epic 7.** `epics.md:235`: Epic 1 "carries the R-1 spike as an early long-pole story, on FR-50's own rule that fitness is proven before a feature is committed to." `epics.md:271`: Epic 7 "builds object storage greenfield on whatever Epic 1's R-1 spike concluded." **This story's output is Epic 7 Story 7.5's input.** Write the verdict so that story can act on it without re-deriving anything.
- **AD-3:** the four selectable features are pixi features with an `[environments]` matrix, and **all twelve environments share one `solve-group`**. The spike environment must join `solve-group = "default"` for the same reason: otherwise it tests a different Django than the product ships.
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

Variance: the spike environment is a fifth pixi environment shape that the AD-3 twelve-combination matrix does not anticipate. It is temporary — Epic 8 Story 8.1 builds the real matrix, and by then this spike has served its purpose. Record in Completion Notes whether `[feature.spike-storage]` should be removed at that point or folded into the `storage` feature Epic 7 declares.

### Forward context — this story's output is consumed downstream

Epic 7 Story 7.5 ("Object storage attaches an S3-compatible backend with a local substitution") builds on this verdict. AC #2's "the evidence is attached at the point of declaration" is what makes that possible: Story 7.5 moves `django-storages` from the spike feature into the `storage` pixi feature and carries the comment block with it. FR-18's fifth substitution — filesystem-backed object storage — is also Epic 7's, not Epic 3's (`epics.md:223`). **These are traceability markers, not acceptance conditions for this story.**

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.8]
- [Source: _bmad-output/planning-artifacts/epics.md:99] — FR-50.
- [Source: _bmad-output/planning-artifacts/epics.md:182] — R-1 restated in the epic preamble with the ordered escalation.
- [Source: _bmad-output/planning-artifacts/epics.md:235] — Epic 1 carries the R-1 spike as an early long-pole story.
- [Source: _bmad-output/planning-artifacts/epics.md:271] — Epic 7 "builds object storage greenfield on whatever Epic 1's R-1 spike concluded."
- [Source: _bmad-output/planning-artifacts/epics.md:223] — FR-18's fifth substitution is delivered in Epic 7, not Epic 3.
- [Source: _bmad-output/planning-artifacts/epics.md:339] — CG-2's discipline: a silently narrowed claim is worse than a bounded one.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-1 in full.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Stack] — django-storages 1.14.6 / boto3 1.43.65, Django 6.0, Python 3.14.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-3] — the shared solve-group.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — supply chain, rationale.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
