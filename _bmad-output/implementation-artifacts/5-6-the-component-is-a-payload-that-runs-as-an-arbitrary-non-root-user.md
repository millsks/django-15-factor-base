# Story 5.6: The component is a payload that runs as an arbitrary non-root user

Status: ready-for-dev

## Story

As an operator,
I want a component to start from environment variables alone under a platform-assigned UID,
so that it fits the image pipeline rather than acquiring an opt-out from it.

## Acceptance Criteria

**Traceability:** FR-38, FR-39 · AD-15 · NFR-3 · SC-3

1. **Given** a built image
   **When** it is inspected
   **Then** no configuration file is present
   **And** the component starts from environment variables alone

2. **Given** an arbitrary non-root UID and a read-only root filesystem
   **When** the component starts
   **Then** startup succeeds
   **And** the component declares no writable path beyond a temporary directory

3. **Given** the zero-writable-path claim
   **When** it is verified
   **Then** it is asserted rather than assumed: static files are collected at build and served by the application, user media is a non-goal, logs go to the event stream, and sessions are database-backed

4. **Given** materialized components
   **When** they are produced
   **Then** they ship no Dockerfile
   **And** the buildpack and golden-base path is the default

5. **Given** this repository
   **When** the harness needs to verify the payload properties
   **Then** it ships a Dockerfile classified as `machinery`, which does not exist today

## Tasks / Subtasks

- [ ] Task 1 — Author the machinery `Dockerfile` (AC: #1, #2, #5)
  - [ ] Create `Dockerfile` at the repository root. **It does not exist today** — verified 2026-08-15.
  - [ ] Header comment, first lines of the file: this Dockerfile is `machinery` under AD-2 and **never travels**; materialized components ship no Dockerfile (AD-15); it exists so the harness can verify FR-38/FR-39 payload properties; AD-32 governs the GitHub-template fork that inherits it.
  - [ ] Base image: pin a Debian-based image that provides pixi ≥ 0.70.2 **by digest**, not by tag. Do not invent or guess a tag — resolve the digest at implementation time and record it in the Dev Agent Record. `pixi.toml` `[workspace] requires-pixi = ">=0.70.2"` is the floor.
  - [ ] Build stage: `COPY pixi.toml pixi.lock pyproject.toml ./` then the source tree, then `pixi install --locked -e default`. `--locked` is NFR-5's determinism requirement — a solve at build time is a different component from the one the gate tested.
  - [ ] Run `pixi run collectstatic` at **build** time so `staticfiles/` is baked into the image (AC #3). `staticfiles/` is gitignored (`.gitignore:232`), so it exists only as a build product. `whitenoise.middleware.WhiteNoiseMiddleware` is already in `MIDDLEWARE` (`src/config/settings/base.py:167`) and `production.py:83-85` sets `whitenoise.storage.CompressedManifestStaticFilesStorage` — the application serves them; no sidecar, no volume.
  - [ ] `CMD ["pixi", "run", "web"]`. **No `ENTRYPOINT` or `CMD` that migrates** — Story 5.5's assertion covers this file and must pass on the day it lands.
  - [ ] `COPY` no `.env`, no settings file, no `component.toml` override, no secret. FR-38: configuration is exclusively environmental. `component.toml` is source that travels, not configuration — copying the source tree includes it and that is correct; a *configuration* file is what must be absent.

- [ ] Task 2 — Make an arbitrary non-root UID work (AC: #2)
  - [ ] `USER` a numeric non-root UID (e.g. `1001`), and additionally make the image tolerate a UID the platform assigns at run time and the image has never seen: `chgrp -R 0 /app && chmod -R g=u /app` so group 0 has the owner's permissions, which is how an arbitrary-UID platform grants access.
  - [ ] `ENV HOME=/tmp` — an arbitrary UID has no entry in `/etc/passwd` and therefore no home directory; tools that write to `$HOME` under a read-only root filesystem fail otherwise.
  - [ ] Point every pixi/rattler cache at the temporary directory (`PIXI_CACHE_DIR`, `RATTLER_CACHE_DIR` under `/tmp`) and run with `--frozen` semantics at run time so `pixi run web` performs no solve and writes nothing under `/app`. **Verify this under `--read-only`** rather than assuming it; if `pixi run` still needs a writable path inside `/app`, record exactly which path in the Dev Agent Record and mount it as a `tmpfs` in the harness — do not make `/app` writable.
  - [ ] Declare no `VOLUME` other than, at most, `/tmp`. Do not add a volume for media, logs, or static files.

- [ ] Task 3 — Add `.dockerignore` (AC: #1)
  - [ ] **NEW** `.dockerignore` excluding everything that would either bloat the image or smuggle local state into it: `.git/`, `.pixi/`, `dist/`, `site/`, `db.sqlite3`, `.coverage`, `coverage.xml`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `_bmad/`, `_bmad-output/`, `staticfiles/`, `.env`, `.envs/`. Every one of these exists in the working tree today except `.env`/`.envs/`, which are gitignored and must never enter an image.
  - [ ] `db.sqlite3` in particular: a 320 KB local sqlite database sits at the repository root today. Shipping it would put a writable local credential store into the payload.

- [ ] Task 4 — Assert the zero-writable-path claim rather than assuming it (AC: #2, #3)
  - [ ] `tests/unit/test_payload_properties.py`, static assertions over `Dockerfile` and settings:
    - no `COPY` line names `.env`, `*.cfg`, `*.ini`, or a settings file outside `src/`;
    - a `USER` instruction exists and its value is not `root` or `0`;
    - `HOME` is set to a path under `/tmp`;
    - no `VOLUME` outside `/tmp`;
    - no `RUN`/`CMD`/`ENTRYPOINT` instruction invokes `migrate` (shared with Story 5.5's assertion — import it, do not duplicate it);
    - `LOGGING` declares no file-based handler in any settings module: `build_logging_config` (`src/config/observability/logging.py`) must yield handlers writing to the event stream only, and `production.py:125-151` adds `mail_admins`, which is not a file handler. Assert on the resolved `LOGGING["handlers"]` classes, not on a string.
  - [ ] Assert `SESSION_ENGINE` resolves to the database-backed engine (AC #3's sessions clause) by importing the assertion Story 5.7 writes rather than restating it.
  - [ ] **User media:** `MEDIA_ROOT` is `str(APPS_DIR / "media")` (`src/config/settings/base.py:198`) and `src/config/urls.py:28` serves it via `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` — a declared writable path inside the source tree, which contradicts AC #2. Assert here that the component writes nothing to `MEDIA_ROOT` at run time (no `default` storage backend writes there in a serving path; `tests/conftest.py:13-15` already redirects `MEDIA_ROOT` to a tmpdir for tests) and record the residue. **Removing the `MEDIA_*` surface belongs to Epic 7's object-storage story under FR-25, which states user media is out of scope** — do not remove it here, and do not leave the contradiction unrecorded.

- [ ] Task 5 — Verify the payload properties by actually running the image (AC: #1, #2)
  - [ ] `tests/integration/test_image_payload.py` (`@pytest.mark.integration`), guarded by `pytest.mark.skipif(shutil.which("docker") is None, reason="...")` — the gate runs on Linux where Docker is available, so the guard is a developer-machine accommodation and not a silent pass. This is a capability guard, not a `@pytest.mark.skip`/`xfail`.
  - [ ] Build the image, then run it with `--user 12345:0 --read-only --tmpfs /tmp` and **only** environment variables for configuration (`DJANGO_SETTINGS_MODULE`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_ADMIN_URL`, `DATABASE_URL`). Assert the process starts and `readyz` returns 200 once the database answers, and `livez` returns 200 immediately.
  - [ ] Assert the container wrote nothing outside `/tmp`: `docker diff` on the stopped container must report no changed or added path under `/app`.
  - [ ] Assert no configuration file is present in the image: no `.env` at any level, and `find / -name ".env"` inside the image returns nothing.
  - [ ] The test must leave state as it found it: remove the container and the built image in a fixture teardown.

- [ ] Task 6 — Document the payload contract (AC: #3, #4)
  - [ ] `docs/deployment.md` `## The component is a payload`: materialized components ship **no Dockerfile**; the buildpack and golden-base path is the default; a component that genuinely needs its own build is a deliberate departure. State the four zero-writable-path legs explicitly — static collected at build and served by the application, user media a non-goal, logs to the event stream, sessions database-backed.
  - [ ] State that this repository's `Dockerfile` is `machinery`, exists for harness verification, and that the GitHub-template fork inherits it as a named governed exception (AD-32).
  - [ ] State the SC-3 boundary plainly: this story delivers the component-side half; nothing here starts a component on the target platform, and the deployment configuration lives in a separate repository and is an explicit non-goal.
  - [ ] Ensure `docs/deployment.md` is in `mkdocs.yml` `nav`; `pixi run docs` is `mkdocs build --strict`.

## Dev Notes

### Architecture Constraints

- **AD-15** — *Rule:* "Materialized components ship no Dockerfile; the buildpack and golden-base path is the default, and a component that genuinely needs its own build is a deliberate departure. FR-38 and FR-39 are properties of the application — starts from environment variables alone, under an arbitrary non-root UID, writing nothing outside a temporary directory. **This repository will ship a Dockerfile as `machinery` — none exists today — so the harness can verify those properties.** AD-32 governs the one component shape that inherits it." *Prevents:* "every component acquiring an opt-out from the platform image pipeline, which would turn a base-image CVE bump into N pull requests."
- **AD-2** — Unlisted paths default to `machinery`, so a `Dockerfile` absent from `accelerator.toml` is already non-travelling. It must nonetheless be **listed explicitly as `machinery`** when Epic 7 authors `accelerator.toml`, because AD-2's input reconciliation fails a path claimed by no disposition. Record that obligation in the Dockerfile's header comment.
- **AD-32** — "'Use this template' produces a **fork of the base**, not a generated component… It carries `accelerator.toml`, the materializer and the machinery Dockerfile, so it can adopt reusable apps and can opt out of the image pipeline where a materialized component cannot… These are accepted, not mitigated." Also **R-4**.
- **AD-14** — The deployment repository invokes `pixi run <process>`; the image's `CMD` must therefore be `pixi run web`, not a bare gunicorn invocation, or the image and the process model declare two different things.
- **NFR-3** — "Statelessness — nothing shared through local disk or process memory across replicas; sessions database-backed in every combination."
- **NFR-5** — Determinism: "the same selections and lock file produce the same component." Hence `pixi install --locked` and a digest-pinned base image.
- **Consistency Conventions** — "Supply chain: conda-forge only; `[pypi-dependencies]` carries the editable self-install and nothing else." The image installs through pixi from `pixi.lock`; it must not `pip install`, `apt-get install` a Python package, or add a system package. FR-49: "dependencies lock-pinned with no system packages."
- **Consistency Conventions** — "Logging: structured, JSON to stdout… **No files, no rotation.**" That is AC #3's logs leg, already true; the assertion pins it.
- **Project standards** — Pixi is the only runner, inside the image as well as outside. Python 3.14 only. Never `print()`; `structlog` only. Never a bare `except:`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `Dockerfile` | **NEW** | Does not exist. `machinery`; digest-pinned pixi base; `pixi install --locked`; `collectstatic` at build; numeric non-root `USER` with group-0 permissions; `HOME=/tmp`; caches under `/tmp`; `CMD ["pixi","run","web"]`; no migrate, no configuration file, no volume beyond `/tmp`. |
| `.dockerignore` | **NEW** | Excludes `.git/`, `.pixi/`, `dist/`, `site/`, `db.sqlite3`, `.coverage`, `coverage.xml`, tool caches, `_bmad/`, `_bmad-output/`, `staticfiles/`, `.env`, `.envs/`. |
| `tests/unit/test_payload_properties.py` | **NEW** | Static assertions over the Dockerfile and the resolved settings. |
| `tests/integration/test_image_payload.py` | **NEW** | Builds and runs the image under `--user 12345:0 --read-only --tmpfs /tmp`; asserts boot, probes, and an empty `docker diff`. |
| `docs/deployment.md` | UPDATE (NEW if earlier Epic 5 stories have not landed) | Adds `## The component is a payload`. |
| `mkdocs.yml` | UPDATE | Register `deployment.md` in `nav`. |
| `tests/unit/test_release_stage.py` | UPDATE (created by Story 5.5) | Its Dockerfile branch stops being skipped once this file exists — confirm it passes. |
| `pixi.toml` | read only | `[workspace] requires-pixi = ">=0.70.2"`; `gunicorn`/`uvicorn-worker` are `[target.linux-64.dependencies]` (`:85-87`) and `[target.osx-arm64.dependencies]` (`:89-91`) — the image is linux-64, so `web` resolves. |
| `src/config/settings/production.py` | read only | `:79-86` `STORAGES` — whitenoise for staticfiles, `FileSystemStorage` as `default`. The `default` backend is Epic 7's object-storage story (FR-25, risk R-1); do not change it here. |
| `src/config/settings/base.py` | read only | `:167` whitenoise middleware; `:184-193` `STATIC_ROOT`/`STATIC_URL`/`STATICFILES_DIRS`; `:198-200` `MEDIA_ROOT`/`MEDIA_URL` — the recorded residue. |

### Testing Requirements

- Unit: `tests/unit/test_payload_properties.py` — text parsing of `Dockerfile` plus assertions over already-resolved Django settings. No Docker, no network, milliseconds. Assert on parsed instruction lines, not on a substring of the whole file.
- Integration: `tests/integration/test_image_payload.py` — `@pytest.mark.integration`; `tests/integration/conftest.py:12-19` also auto-marks the directory. Docker-guarded via `skipif(shutil.which("docker") is None)`; the CI runner is Linux, so the gate exercises it. Must leave state as found — remove container and image in teardown.
- Disposition (spine Consistency Conventions): `Dockerfile` is `machinery` and never travels, so **its tests are `machinery` too** and do not run inside a materialized combination's gate. Note this in the test module docstring — it is the one place in Epic 5 where the test's disposition is not `core`.
- AD-20 floor: 90% including templates, `COVERAGE_CORE=ctrace` in force. These tests add no production Python, so the floor is unaffected; do not add anything to `[tool.coverage.run] omit` (`pyproject.toml:162-169`) — AD-20 makes that list closed.
- Inner loop `pixi run test`, then `pixi run test-integration` (this story crosses a resource boundary), then `pixi run ci`.

#### Project Structure Notes

- The Structural Seed lists `Dockerfile` at the repository root annotated "machinery — payload verification only; does not exist yet (AD-15)". This story lands it, and the seed's "does not exist yet" is confirmed accurate as of 2026-08-15.
- **Dependency:** Story 5.2 (the `web` task the image's `CMD` invokes), Story 5.3 (the probes the integration test asserts), Story 5.7 (the `SESSION_ENGINE` assertion AC #3 reuses). Story 5.5's Dockerfile assertion becomes live here.
- **Recorded contradiction, not this story's fix:** `MEDIA_ROOT` under `src/django_service/media` and the `static()` media route at `src/config/urls.py:28` are a declared writable path inside the payload. FR-25 states user media is out of scope and Epic 7 owns the storage feature; this story asserts nothing writes there and records the residue for Epic 7.
- **Not in scope:** the buildpack, the golden base image itself, the CI job that builds and pushes, and the platform manifests. epics.md records SC-3 as an external exit criterion: "Story 5.6 delivers the component-side half — environmental configuration, arbitrary UID, read-only root filesystem, the machinery Dockerfile — but nothing here starts a component on the platform."
- **R-4** is inherited, not created here: the GitHub-template path ships from `main` HEAD carrying this Dockerfile. AD-32 states the consequences; nothing in this story prevents them, and nothing should try.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-15]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-14]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-32]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Structural Seed]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-1, R-4.
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.6]
- [Source: _bmad-output/planning-artifacts/epics.md#External exit criteria] — SC-3, and what Story 5.6 does and does not deliver.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-38]
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-39]
- Repository state: `Dockerfile` absent; `.gitignore:232` (`staticfiles/`), `:152` (`.env`), `:225-228` (`.envs/`); `src/config/settings/base.py:167, 184-200`; `src/config/settings/production.py:79-86, 125-151`; `src/config/urls.py:28`; `tests/conftest.py:13-15`; `pixi.toml:85-92`.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
