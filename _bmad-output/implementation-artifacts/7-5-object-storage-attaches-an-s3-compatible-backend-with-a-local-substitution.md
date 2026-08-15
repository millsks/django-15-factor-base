# Story 7.5: Object storage attaches an S3-compatible backend with a local substitution

Status: ready-for-dev

## Story

As a lead developer,
I want object storage as a selectable feature that works deployed and locally,
so that the three combinations that select it have both a real backing service and a local story.

## Acceptance Criteria

**Traceability:** FR-25, FR-28, FR-18 (fifth substitution) · risk R-1

1. **Given** the evidence from Story 1.8
   **When** the feature is built
   **Then** it uses `django-storages` and `boto3` from the approved channel on that evidence
   **And** the feature is greenfield: no storage configuration or application code exists today

2. **Given** a deployed component
   **When** storage is configured
   **Then** it is configured through Django's storages configuration from environment variables alone
   **And** no bucket, endpoint or credential is baked into the image

3. **Given** a developer with no object store running
   **When** the component runs locally
   **Then** a filesystem-backed storage backend is configured
   **And** the storage API is preserved at every call site

4. **Given** the local substitution
   **When** its limits are documented
   **Then** they state that it does not exercise bucket policy, presigned URLs, eventual consistency, multipart upload, or the network failure modes of a remote object store

5. **Given** user media
   **When** scope is assigned
   **Then** it is out of scope, because avatars resolve from IdP profile metadata as remote URLs

6. **Given** a combination that did not select the feature
   **When** it is inspected
   **Then** no storage configuration, dependency or call site remains

## Tasks / Subtasks

- [ ] Task 0 — Read Story 1.8's recorded result before writing any code (AC: #1)
  - [ ] Story 1.8 records the R-1 spike result *"where the dependency is declared"* — that is, beside the `django-storages` line in `pixi.toml`. Read it. This story's dependency declaration is determined by that result and by nothing else.
  - [ ] **Outcome A — the spike passed.** Declare `django-storages` and `boto3` in `pixi.toml [dependencies]` from conda-forge, with the spike evidence recorded as the comment beside them (FR-50: fitness, not just availability). Proceed with Tasks 1–7 as written.
  - [ ] **Outcome B — the spike failed.** Do not improvise. R-1's escalation is ordered and the order is binding: push the conda-forge feedstock as was done for `django-celery-beat`, under a **time-boxed** `[pypi-dependencies]` exception whose exit condition is that build landing, recorded beside the entry. Adding a third-party entry to `[pypi-dependencies]` breaks Story 1.7's assertion that the block contains only the editable self-install — that test must be extended to permit exactly one exception carrying a reason and an exit condition, not deleted or loosened generally. A component-owned backend against `django.core.files.storage.Storage` is the **last resort**, not the convenient answer; a permanent supply-chain exception is not on the list at all. Adding any runtime dependency requires the user's confirmation.
  - [ ] **Outcome C — Story 1.8 has not run.** Stop and surface it. FR-50's rule is that fitness is proven before a feature is committed to; this story is the commitment.

- [ ] Task 1 — Declare the storage feature's surface in the carrier (AC: #1, #6)
  - [ ] Complete `[features.storage]` in `accelerator.toml`: `packages = ["django-storages", "boto3"]` — the *dependency* surface — plus the regions this story creates and its own tests. **The feature owns no source package and no path root.** AD-33 is retired: there is no `src/features/`, no `django_storage` package and no third import root, so storage's code-shaped surface is entirely `feature:storage` regions inside `core` settings modules. Every new region gets a `[[regions]]` entry; the only new *files* are this story's tests and its documentation page.
  - [ ] Record the R-1 outcome and its evidence pointer in the carrier beside the feature, so the supply-chain state travels with the feature declaration rather than living only in a commit message.
  - [ ] `boto3` is already in `pixi.lock` transitively via `django-anymail`. The spine's Supply chain convention is explicit: *"Transitive availability is not declaration: a package the code imports directly is declared directly, even when something else already pulls it in."* Declare `boto3` directly if the feature's code imports it directly; if only `django-storages` imports it, declare only `django-storages` and record that reasoning.

- [ ] Task 2 — Build the deployed configuration (AC: #2)
  - [ ] Add the storage backend configuration as a `feature:storage` region in `src/config/settings/base.py`, delimited by paired `# feature:storage` / `# /feature:storage` line comments and declared in `accelerator.toml` (AD-24). No conditional import, no settings-module inheritance, no `try/except ImportError`.
  - [ ] Configure through Django's `STORAGES` setting — the `"default"` entry pointing at `storages.backends.s3.S3Storage`, with `OPTIONS` read from the environment via the existing `environ.Env()` instance (`base.py:19`). Django 6.0 uses `STORAGES`; do not use the removed `DEFAULT_FILE_STORAGE` / `STATICFILES_STORAGE` settings.
  - [ ] Every value — bucket name, endpoint URL, region, access key, secret key, addressing style — comes from an environment variable with no default that could work by accident. A missing required variable in a deployed component is `ImproperlyConfigured` at settings import, consistent with NFR-1 and the spine's Configuration-errors convention. Nothing is baked into the image (FR-38, AD-15).
  - [ ] Never commit credentials. `env()` with no default is the correct shape for a secret (NFR-7).
  - [ ] Interaction with what is already there: `src/config/settings/production.py:79-86` **already defines `STORAGES`** — `"default"` as `django.core.files.storage.FileSystemStorage` and `"staticfiles"` as `whitenoise.storage.CompressedManifestStaticFilesStorage`. Do not add a second, competing definition. Restructure so the `"staticfiles"` entry stays `core` (whitenoise static serving is immovable core, AC #6 of Story 7.4) and only the `"default"` entry is feature-owned. Record the restructure in the carrier.

- [ ] Task 3 — Build the local substitution (AC: #3) — this is FR-18's fifth substitution
  - [ ] FR-18 names five substitutions: sqlite, in-process cache, eager tasks, **filesystem-backed object storage**, local personas. Epic 3 delivered the other four and deliberately did not own this one, because the storage feature does not exist until now (`epics.md:223`). This story completes FR-18.
  - [ ] Under `COMPONENT_RUNTIME=local` (AD-13), the `"default"` storage entry resolves to `django.core.files.storage.FileSystemStorage` rooted at a gitignored local path. Follow whatever mechanism Epic 3 established for the other four substitutions — read `src/config/settings/local.py` and the locality helper Epic 3 built and reuse it. Do not invent a second locality mechanism.
  - [ ] Locality fails closed: absent or unrecognized `COMPONENT_RUNTIME` means deployed (AD-13). A component that fails to set it gets the S3 backend and its missing-variable refusal, not a silent filesystem fallback.
  - [ ] The storage API is preserved at every call site (AC #3): application code uses `django.core.files.storage.storages["default"]` or the `Storage` API and never imports `S3Storage` or `boto3` directly. Add a gate test asserting no module outside the feature's own configuration imports `storages.*` or `boto3`.
  - [ ] Add the local storage root to `.gitignore` if Epic 3's pattern does not already cover it (NFR-7: the development keypair precedent).

- [ ] Task 4 — Document the substitution's limits (AC: #4)
  - [ ] Add the limits to `docs/development.md` (exists) or a sibling under `docs/`, stating in the document's own words that the filesystem substitution does **not** exercise: bucket policy, presigned URLs, eventual consistency, multipart upload, or the network failure modes of a remote object store.
  - [ ] Frame it as R-5's instance for storage — *"local development proves less than running suggests"* — not as a caveat. This is component-facing documentation and travels with the component (NFR-8); disposition it `feature:storage` so it is pruned in the three combinations that do not select the feature.
  - [ ] Record the FR-25 / AC #5 scope statement in the same place: user media is out of scope because avatars resolve from IdP profile metadata as remote URLs.

- [ ] Task 5 — Keep user media out of scope (AC: #5)
  - [ ] Do not add avatar upload, user media models, media upload views, or `ImageField`/`FileField` on `User`.
  - [ ] `src/config/settings/base.py:195-200` sets `MEDIA_ROOT = str(APPS_DIR / "media")` and `MEDIA_URL = "/media/"`, and `src/config/urls.py` serves media via `*static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)`. `src/config/settings/test.py:43` overrides `MEDIA_URL`. Decide whether the existing media plumbing stays `core`, becomes `feature:storage`, or is removed as unused, and record the reason. It is pre-existing scaffolding, not this feature's surface — do not silently repurpose it as the object-storage story.

- [ ] Task 6 — Ensure clean removal (AC: #6)
  - [ ] Every artifact this story creates is either a `feature:storage` path or a declared `feature:storage` region. Nothing is left present-and-disabled.
  - [ ] Run the Story 7.1 input reconciler, the Story 7.2 region reconciler and the Story 7.3 parameter reconciler after the change; all three must report zero failures.
  - [ ] Assert that with the feature's paths and regions removed, no `core` module references `storages`, `boto3`, or any storage environment variable. This is the reference-application-scale version of AC #6; the materialized-tree version is Epic 8's Story 8.7.

- [ ] Task 7 — Tests (AC: all)
  - [ ] `tests/unit/storage/test_settings.py` (NEW): the deployed configuration resolves `S3Storage` with `OPTIONS` from the environment; a missing required variable raises `ImproperlyConfigured`; no credential appears in any default.
  - [ ] `tests/integration/storage/test_local_substitution.py` (NEW), `@pytest.mark.integration`: with `COMPONENT_RUNTIME=local` and nothing running, a save/open/exists/delete round-trip through the `Storage` API succeeds against `tmp_path`; the test leaves no files behind.
  - [ ] `tests/integration/storage/test_no_direct_backend_imports.py` (NEW), `@pytest.mark.integration`: AST-level assertion that no module outside the feature's configuration imports `storages` or `boto3`.
  - [ ] Both test packages are disposition `feature:storage` and are pruned with the feature (spine test-location convention). Mirror `src/` in their location — the settings modules they cover live under `src/config/`, so `tests/{unit,integration}/storage/` beside the existing `tests/unit/` and `tests/integration/` trees is the right shape. There is no feature-owned source directory to mirror; AD-33 is retired.
  - [ ] Do **not** write tests that require a real S3 endpoint. The deployed path is asserted at the configuration level here; end-to-end object-store behaviour has no environment in phase 1 and pretending otherwise is the SC-3/SC-6 mistake at smaller scale.
  - [ ] `pixi run ci` exits 0, coverage ≥90% including templates.

## Dev Notes

### Architecture Constraints

**R-1 — the named residual risk this story carries.** From the spine, verbatim on the escalation order: *"`django-storages` fitness is unproven, and object storage cannot be deferred. Present on the channel, which is FR-50's test, but released 2025-04-02 with no declared Django 6.0 or Python 3.14 support and nothing newer available; Django 6.0 support exists only on unreleased upstream master. Object storage appears in three of six combinations, does not exist yet, and is expected to be selected by most components — so dropping it is not an available answer and the risk must be carried rather than avoided. The escalation is ordered: spike `1.14.6` against the locked Django and Python first, since it is a thin wrapper over a `boto3` already in the lock and Django's `Storage` API has been stable; if that fails, push the conda-forge feedstock as was done for `django-celery-beat`, with a **time-boxed** package-index exception whose exit condition is that build landing; a component-owned S3 backend against `django.core.files.storage.Storage` is the last resort, because a platform product owning its own storage backend is a permanent maintenance and security cost. A permanent supply-chain exception is not on the list."*

**Stack, authoritative — do not web-search for versions.** `django-storages` 1.14.6 / `boto3` 1.43.65. Note beside them in the spine's Stack table: *"`boto3` already locked via `django-anymail`. `django-storages` released 2025-04-02, declares no Django 6.0 or py3.14 — see residual risk R-1."* Python 3.14, Django 6.0.

**AD-24 — regions, and nothing else.** Storage configuration inside `core` settings modules is removed by paired `# feature:storage` / `# /feature:storage` markers declared in `accelerator.toml`. **Forbidden:** conditional imports, settings-module inheritance, `try/except ImportError`. A `try: import storages / except ImportError: pass` in `base.py` is precisely the mechanism this AD names and refuses.

**AD-2 — disposition.** Every new file is `feature:storage`; it travels only where the feature is selected. `src/config/settings/base.py` and `production.py` stay `core` and carry regions.

**AD-13 — locality.** `COMPONENT_RUNTIME=local` is set in the `env` of each local pixi task; it fails closed — absent or unrecognized means deployed. No `COMPONENT_*` variable may appear in `[activation.env]`, asserted by a gate test over the materialized `pixi.toml`.

**AD-29 — nothing inside `src/django_service/`.** No storage code, configuration, template or static asset goes into the base package; it is `core` in its entirety.

**AD-4 — a feature's code may never import another feature's.** Storage configuration imports Django and nothing belonging to `celery` or `redis`. With no feature packages left (AD-33 retired) the rule is thin here, but the `feature:storage` regions must not read `REDIS_URL` or any Celery setting.

**Revision 3 — what this means for storage.** Object storage is now one of **three** selectable features rather than four, and it is the only one with anything code-shaped left. Even that is settings: a `STORAGES` block in `core` settings modules, delimited by `feature:storage` markers. There is no `src/features/`, no `django_storage` package and no third import root — AD-33 is retired with no occupants precisely because celery, redis and storage own dependency entries and AD-24 regions and nothing more.

**FR-38 / AD-15.** Configuration is exclusively environmental; no configuration file in the image; the component starts from environment variables alone.

**Supply chain (spine Consistency Conventions).** conda-forge only; `[pypi-dependencies]` carries the editable self-install and nothing else; transitive availability is not declaration. Adding a runtime dependency requires the user's confirmation.

**Project standards.** Pixi is the only runner — `pixi add` for dependencies, never `pip install`. Python 3.14 only. PEP 8 / 120 / full type hints / Google docstrings. Never `print()`, never stdlib `logging` — `structlog` only. Never bare `except:`, never `except X: pass`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `pixi.toml` | UPDATE | Add `django-storages` and `boto3` to `[dependencies]` (Outcome A) with the R-1 evidence recorded beside them, inside a `feature:storage` region (Story 7.2 established the pattern for the celery and redis dependency lines; note that the crispy packages are `core` and carry no marker, since form styling is immovable core). **Today:** `[dependencies]` `:14-80` contains neither package. `[pypi-dependencies]` `:98-99` contains only `django-15-factor-base = { path = ".", editable = true }` — zero supply-chain exceptions, and Story 1.7 asserts it. `[environments]` `:141-143` has only `default` and `dev`; the six-combination matrix is Epic 8's. **Preserve:** every existing rationale comment, `[activation.env] COVERAGE_CORE = "ctrace"` (`:145-150`), and the platform-scoped gunicorn/uvicorn-worker blocks. |
| `src/config/settings/base.py` | UPDATE | Add the `feature:storage` `STORAGES` region. **Preserve:** the `env = environ.Env()` instance (`:19`), `MEDIA_ROOT`/`MEDIA_URL` (`:195-200`) pending the Task 5 decision, and the markers Story 7.2 placed. Nothing may be appended after the final block — Epic 4 makes the stage-1 refusal call the last statement of every settings module. |
| `src/config/settings/production.py` | UPDATE | **Today:** `STORAGES` at `:79-86` with `"default"` = `FileSystemStorage` and `"staticfiles"` = `whitenoise.storage.CompressedManifestStaticFilesStorage`. **Changes:** restructure so `"staticfiles"` stays `core` and `"default"` becomes the feature-owned entry. **Preserve:** the sqlite refusal at `:26-28` (FR-13 condition 1, the one refusal already built), the security settings, `CACHES` at `:31-44` (a `feature:redis` region under Story 7.2), the anymail block and the structlog `LOGGING` composition. |
| `src/config/settings/local.py` | UPDATE | Add the filesystem substitution consistent with Epic 3's locality mechanism. **Today:** `CACHES` LocMemCache (`:18-26`), the `DJANGO_DEBUG_APPS` gate (`:50-74`), Celery eager settings (`:75-80`). Epic 3 restructures this module; read its current state before editing. |
| *(no feature source directory)* | — | Revision 2 expected a `feature:storage` package here, inherited from a decision Story 7.4 was to make. **That row is retired.** AD-33 has no occupants, so storage's entire code-shaped surface is the `feature:storage` regions in the three settings modules above, plus its dependency entries in `pixi.toml` and its own tests. Do not create `src/features/`, `src/storage/` or a `django_storage` package. |
| `docs/` | NEW or UPDATE | The AC #4 limits and the AC #5 scope statement. `docs/` today holds `index.md`, `development.md`, `observability.md`; `mkdocs.yml:33-36` lists all three in `nav`. A new page must be added to `nav` or `pixi run docs` (`mkdocs build --strict`) fails. |
| `.gitignore` | UPDATE | The local storage root, if Epic 3's pattern does not already cover it. |
| `accelerator.toml` | UPDATE | `[features.storage]` completion, new `[[regions]]`, the R-1 record. Preserve Stories 7.1–7.4 content. |
| `tests/unit/storage/test_settings.py` | NEW | Deployed configuration assertions. |
| `tests/integration/storage/test_local_substitution.py` | NEW | Round-trip through the `Storage` API, `@pytest.mark.integration`. |
| `tests/integration/storage/test_no_direct_backend_imports.py` | NEW | AST-level call-site assertion, `@pytest.mark.integration`. |

**Greenfield status, verified 2026-08-15.** AC #1's claim that *"no storage configuration or application code exists today"* is **almost** accurate and the exception matters: `src/config/settings/production.py:79-86` already defines a `STORAGES` dict. It configures Django's stock `FileSystemStorage` as `"default"` and whitenoise's manifest storage as `"staticfiles"` — so no *object* storage exists, which is what the AC means, but the setting name this feature must own is already taken by a `core` module. Treat this as a restructure of an existing setting, not as an addition to an empty file. `django-storages` and `boto3` are absent from `pixi.toml [dependencies]`; no `storages` or `boto3` import exists anywhere under `src/`.

### Testing Requirements

- Unit: `tests/unit/storage/test_settings.py` — isolated, milliseconds, environment manipulated via `monkeypatch`, no I/O.
- Integration: `tests/integration/storage/`, every test `@pytest.mark.integration`, `tmp_path` for the filesystem, state left exactly as found.
- No test may require a running object store or reach the network. FR-33's smoke check runs with nothing running and FR-23 forbids network at boot; a test that needs S3 cannot run in the gate.
- Test disposition `feature:storage` — pruned with the feature (spine Consistency Conventions, Test location). Their absence in the three non-selecting combinations is correct and is not a coverage gap.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` in force (AD-20).

#### Project Structure Notes

- **No new source structure.** Revision 2 had this story inherit a "feature-owned location" from Story 7.4; AD-33 is retired and no such location exists. Storage adds no package, no import root and no directory under `src/` — its surface is regions inside `src/config/settings/{base,production,local}.py`, dependency lines in `pixi.toml`, one documentation page and two test packages. If a task seems to need a feature source directory, the design is wrong, not the constraint.
- FR-18's fifth substitution landing here rather than in Epic 3 is deliberate and recorded at `epics.md:223`. Epic 3's four substitutions and their locality helper already exist; reuse them.
- FR-26's broker constraint does not involve storage. Object storage is independently selectable and appears in three of the six combinations (Story 7.6).
- If Outcome B applies, the `[pypi-dependencies]` exception changes the project's "zero supply-chain exceptions" state, which Story 1.7's test asserts and the project README and dependency-policy test both reflect. Extend the test to admit exactly one time-boxed, reasoned exception rather than loosening it.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-1, the ordered escalation
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Stack] — django-storages 1.14.6 / boto3 1.43.65; Django 6.0; Python 3.14
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-24]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-15]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-29]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions] — Supply chain: transitive availability is not declaration
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.5]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.8] — the spike whose evidence this story consumes
- [Source: _bmad-output/planning-artifacts/epics.md#Cross-epic threads] — line 223: FR-18's fifth substitution is delivered here, not in Epic 3
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-25]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-18]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-50]
- Repository, verified 2026-08-15: `src/config/settings/production.py:79-86,26-28,31-44`; `src/config/settings/base.py:19,195-200`; `src/config/settings/local.py:18-26,75-80`; `src/config/settings/test.py:43`; `src/config/urls.py` media static line; `pixi.toml:14-80,98-99,141-143`; `mkdocs.yml:33-36`; `docs/` contains `index.md`, `development.md`, `observability.md`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
