---
status: done
baseline_revision: 83902fd
review_loop_iteration: 0
warnings: []
---

# Story 5.6: The component is a payload that runs as an arbitrary non-root user

Status: done

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

- [x] Task 1 — Author the machinery `Dockerfile` (AC: #1, #2, #5)
  - [x] Create `Dockerfile` at the repository root. **It does not exist today** — verified 2026-08-15.
  - [x] Header comment, first lines of the file: this Dockerfile is `machinery` under AD-2 and **never travels**; materialized components ship no Dockerfile (AD-15); it exists so the harness can verify FR-38/FR-39 payload properties; AD-32 governs the GitHub-template fork that inherits it.
  - [x] Base image: pin a Debian-based image that provides pixi ≥ 0.70.2 **by digest**, not by tag. Do not invent or guess a tag — resolve the digest at implementation time and record it in the Dev Agent Record. `pixi.toml` `[workspace] requires-pixi = ">=0.70.2"` is the floor.
  - [x] Build stage: `COPY pixi.toml pixi.lock pyproject.toml ./` then the source tree, then `pixi install --locked -e default`. `--locked` is NFR-5's determinism requirement — a solve at build time is a different component from the one the gate tested.
  - [x] Run `pixi run collectstatic` at **build** time so `staticfiles/` is baked into the image (AC #3). `staticfiles/` is gitignored (`.gitignore:232`), so it exists only as a build product. `whitenoise.middleware.WhiteNoiseMiddleware` is already in `MIDDLEWARE` (`src/config/settings/base.py:167`) and `production.py:83-85` sets `whitenoise.storage.CompressedManifestStaticFilesStorage` — the application serves them; no sidecar, no volume.
  - [x] `CMD ["pixi", "run", "web"]`. **No `ENTRYPOINT` or `CMD` that migrates** — Story 5.5's assertion covers this file and must pass on the day it lands.
  - [x] **Obligation recorded by Story 5.5 (landed):** `tests/unit/test_release_stage.py::test_no_dockerfile_instruction_migrates` exists today and `pytest.skip`s with an explicit reason *only while `Dockerfile` is absent*. Creating the file arms it, with no edit to that test. It joins continuation lines first and then fails on any `RUN`, `ENTRYPOINT` or `CMD` whose arguments contain `migrate` or `makemigrations` as a word — including one hidden after a `&&` on the second line of a multi-line `RUN`, and including `pixi run migrate`. So: `collectstatic` at build time is fine, a build-time or start-up migration is not, at any depth of the image (AD-22). Run `pixi run test` immediately after the first `Dockerfile` commit and confirm the case reports **passed** rather than **skipped**; a still-skipped result means the file is not where the assertion looks (repository root).
  - [x] Once the file exists, delete the `"unit/test_release_stage.py"` entry from `RECORDED_EXEMPTIONS` in `tests/unit/test_suite_policy.py` **only if** the `pytest.skip` branch is also removed. Leaving the branch is the intended outcome — the skip is what keeps the module usable in a tree where `Dockerfile` was never created — and `test_every_recorded_exemption_still_describes_the_file` fails from the other side if the entry is dropped while the branch stays. Do not remove the branch merely because it is no longer taken here.
  - [x] `COPY` no `.env`, no settings file, no `component.toml` override, no secret. FR-38: configuration is exclusively environmental. `component.toml` is source that travels, not configuration — copying the source tree includes it and that is correct; a *configuration* file is what must be absent.

- [x] Task 2 — Make an arbitrary non-root UID work (AC: #2)
  - [x] `USER` a numeric non-root UID (e.g. `1001`), and additionally make the image tolerate a UID the platform assigns at run time and the image has never seen: `chgrp -R 0 /app && chmod -R g=u /app` so group 0 has the owner's permissions, which is how an arbitrary-UID platform grants access.
  - [x] `ENV HOME=/tmp` — an arbitrary UID has no entry in `/etc/passwd` and therefore no home directory; tools that write to `$HOME` under a read-only root filesystem fail otherwise.
  - [x] Point every pixi/rattler cache at the temporary directory (`PIXI_CACHE_DIR`, `RATTLER_CACHE_DIR` under `/tmp`) and run with `--frozen` semantics at run time so `pixi run web` performs no solve and writes nothing under `/app`. **Verify this under `--read-only`** rather than assuming it; if `pixi run` still needs a writable path inside `/app`, record exactly which path in the Dev Agent Record and mount it as a `tmpfs` in the harness — do not make `/app` writable.
  - [x] Declare no `VOLUME` other than, at most, `/tmp`. Do not add a volume for media, logs, or static files.

- [x] Task 3 — Add `.dockerignore` (AC: #1)
  - [x] **NEW** `.dockerignore` excluding everything that would either bloat the image or smuggle local state into it: `.git/`, `.pixi/`, `dist/`, `site/`, `db.sqlite3`, `.coverage`, `coverage.xml`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `_bmad/`, `_bmad-output/`, `staticfiles/`, `.env`, `.envs/`. Every one of these exists in the working tree today except `.env`/`.envs/`, which are gitignored and must never enter an image.
  - [x] `db.sqlite3` in particular: a 320 KB local sqlite database sits at the repository root today. Shipping it would put a writable local credential store into the payload.

- [x] Task 4 — Assert the zero-writable-path claim rather than assuming it (AC: #2, #3)
  - [x] `tests/unit/test_payload_properties.py`, static assertions over `Dockerfile` and settings:
    - no `COPY` line names `.env`, `*.cfg`, `*.ini`, or a settings file outside `src/`;
    - a `USER` instruction exists and its value is not `root` or `0`;
    - `HOME` is set to a path under `/tmp`;
    - no `VOLUME` outside `/tmp`;
    - no `RUN`/`CMD`/`ENTRYPOINT` instruction invokes `migrate` — **already owned** by `tests/unit/test_release_stage.py::test_no_dockerfile_instruction_migrates`, which arms itself when this story creates the file. Do **not** restate it here. If this module needs the same continuation-joining instruction parser (`_instruction_lines` in that file), promote it to a shared helper module the way Story 5.5 promoted the pixi-manifest reader to `tests/pixi_manifest.py`, and update both call sites — never copy it;
    - `LOGGING` declares no file-based handler in any settings module: `build_logging_config` (`src/config/observability/logging.py`) must yield handlers writing to the event stream only, and `production.py:125-151` adds `mail_admins`, which is not a file handler. Assert on the resolved `LOGGING["handlers"]` classes, not on a string.
  - [x] Assert `SESSION_ENGINE` resolves to the database-backed engine (AC #3's sessions clause) by importing the assertion Story 5.7 writes rather than restating it.
  - [x] **User media:** `MEDIA_ROOT` is `str(APPS_DIR / "media")` (`src/config/settings/base.py:198`) and `src/config/urls.py:28` serves it via `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` — a declared writable path inside the source tree, which contradicts AC #2. Assert here that the component writes nothing to `MEDIA_ROOT` at run time (no `default` storage backend writes there in a serving path; `tests/conftest.py:13-15` already redirects `MEDIA_ROOT` to a tmpdir for tests) and record the residue. **Removing the `MEDIA_*` surface belongs to Epic 7's object-storage story under FR-25, which states user media is out of scope** — do not remove it here, and do not leave the contradiction unrecorded.

- [x] Task 5 — Verify the payload properties by actually running the image (AC: #1, #2)
  - [x] `tests/integration/test_image_payload.py` (`@pytest.mark.integration`), guarded by `pytest.mark.skipif(shutil.which("docker") is None, reason="...")` — the gate runs on Linux where Docker is available, so the guard is a developer-machine accommodation and not a silent pass. This is a capability guard, not a `@pytest.mark.skip`/`xfail`.
  - [x] Build the image, then run it with `--user 12345:0 --read-only --tmpfs /tmp` and **only** environment variables for configuration (`DJANGO_SETTINGS_MODULE`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_ADMIN_URL`, `DATABASE_URL`). Assert the process starts and `readyz` returns 200 once the database answers, and `livez` returns 200 immediately.
  - [x] Assert the container wrote nothing outside `/tmp`: `docker diff` on the stopped container must report no changed or added path under `/app`.
  - [x] Assert no configuration file is present in the image: no `.env` at any level, and `find / -name ".env"` inside the image returns nothing.
  - [x] The test must leave state as it found it: remove the container and the built image in a fixture teardown.

- [x] Task 6 — Document the payload contract (AC: #3, #4)
  - [x] `docs/deployment.md` `## The component is a payload`: materialized components ship **no Dockerfile**; the buildpack and golden-base path is the default; a component that genuinely needs its own build is a deliberate departure. State the four zero-writable-path legs explicitly — static collected at build and served by the application, user media a non-goal, logs to the event stream, sessions database-backed.
  - [x] State that this repository's `Dockerfile` is `machinery`, exists for harness verification, and that the GitHub-template fork inherits it as a named governed exception (AD-32).
  - [x] State the SC-3 boundary plainly: this story delivers the component-side half; nothing here starts a component on the target platform, and the deployment configuration lives in a separate repository and is an explicit non-goal.
  - [x] Ensure `docs/deployment.md` is in `mkdocs.yml` `nav`; `pixi run docs` is `mkdocs build --strict`.

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
  **Line-range drift:** `:28` is correct against the file today (2026-08-15). Revision 3 deletes the `home` and `about` `TemplateView` routes at `:14-19` as demonstration content (AD-29, Epic 7 Story 7.4), which shifts the media route up by six lines. Locate the `static(settings.MEDIA_URL, ...)` call rather than the line number, and record the actual position in the Dev Agent Record.
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

claude-opus-5[1m] (Claude Opus 5, 1M context), via Claude Code.

### Debug Log References

#### Planning reconciliation (resolved before implementation, 2026-08-28)

- **Base image, resolved by digest.** `ghcr.io/prefix-dev/pixi@sha256:f32bc1b96d4aacb8bc0cc3c4b731eceb3dd3606f48ec56ed8f61b9a737c5db58`
  — the multi-arch index for tag `0.70.2-trixie`. Verified by pulling it: Debian GNU/Linux 13 (trixie), `pixi 0.70.2` at
  `/usr/local/bin/pixi`, `ca-certificates` present, no `curl`, root, no `ENTRYPOINT`/`CMD`/`USER`/`WORKDIR`/`ENV`.
  `0.70.2` is exactly the floor `pixi.toml [workspace] requires-pixi = ">=0.70.2"` names and exactly the version
  installed on the development machine. The linux/amd64 child manifest is `sha256:3c8c1ba00a43eb4564c4d9972ab5857b29e66c4f3f0d24454254e27b622c6885`.
- **`--platform=linux/amd64` is a constraint, not a preference.** `pixi.lock` declares `linux-64`, `osx-arm64` and
  `win-64` and no `linux-aarch64`, so `pixi install --locked` cannot resolve on an arm64 base at all. The `FROM` must
  therefore pin the platform explicitly; on an arm64 developer machine the build runs under emulation and is slow.
  `gunicorn`/`uvicorn-worker` are `[target.linux-64.dependencies]`, so linux-64 is also the only Linux platform where
  the `web` task resolves.
- **Story 5.7 has not landed, so its assertion cannot be imported.** `SESSION_ENGINE` is unset anywhere in `src/`
  (Django's global default is the database backend) and Story 5.7 owns setting it explicitly. Task 4's sessions bullet
  is therefore satisfied by asserting **this story's own claim** — the resolved session engine writes nothing to local
  disk, i.e. it is not the file-backed engine — and by recording that the explicit setting and the equality assertion
  belong to 5.7. Restating 5.7's assertion here, or importing a module that does not exist, are both refused.
- **Line-range drift confirmed and corrected.** `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` is at
  `src/config/urls.py:50`, not `:28` — the probe include Story 5.3 added at the head of `urlpatterns` moved it down.
  The `home` and `about` routes are still present at `:36-41`.
- **Minimal environment to import `config.settings.production` under `is_deployed()`**, from the stage-1 roster
  (`src/config/startup/stage_one.py:1043-1055`): `DJANGO_SETTINGS_MODULE=config.settings.production`,
  `DJANGO_SECRET_KEY`, `DJANGO_ADMIN_URL`, a non-sqlite `DATABASE_URL`, `COMPONENT_OIDC_ISSUER`,
  `COMPONENT_IDENTITY_CLAIM`, `COMPONENT_GROUP_CLAIM`, `COMPONENT_STAFF_GROUP`, `COMPONENT_SUPERUSER_GROUP`; with
  `OTEL_SDK_DISABLED` and `COMPONENT_RUNTIME` unset. `REDIS_URL` has a default and nothing on the boot or probe path
  touches the cache, so Redis is not needed. This set is required at **build** time too, because `collectstatic` must
  run under `config.settings.production` — that is the only settings module that declares `STORAGES` with
  `CompressedManifestStaticFilesStorage`, and the manifest it writes is the artefact being baked. The values are
  supplied inline on the `RUN` line so they do not persist as `ENV`; `tests/unit/test_payload_properties.py` asserts
  that no `ENV` instruction sets any of them.
- **Plain-HTTP probes need two more variables in the harness** (not in the image): `DJANGO_ALLOWED_HOSTS`, because
  `production.py:23` defaults to `["millsks.github.io"]`, and `DJANGO_SECURE_SSL_REDIRECT=False`, because
  `production.py:53` defaults to `True` and `SecurityMiddleware` 301s the probes — there is no `SECURE_REDIRECT_EXEMPT`
  in the repo. Sending `X-Forwarded-Proto: https` is the alternative; the variable is clearer in a test.
- **The integration test must run the release stage itself.** `_refuse_unapplied_migrations`
  (`src/config/startup/stage_two.py:434`) fires for serving processes, so `web` will not boot against an unmigrated
  database. The harness therefore runs `docker run … pixi run migrate` as a separate, non-serving invocation of the
  same image before starting `web` — which is Story 5.5's contract demonstrated, not violated: the *image* still
  declares no migrating instruction.
- **Two container runs, because one cannot prove both things.** `docker diff` on a `--read-only` container is
  trivially empty and proves nothing, so the no-writes claim is asserted against a **writable** run (every changed
  path must be under `/tmp`), and the startup claim is asserted against a **`--read-only --tmpfs /tmp`** run. Both use
  `--user 12345:0`.
- **`pytest.mark.skipif` is a recorded evasion.** `tests/unit/test_suite_policy.py` scans every `*.py` under `tests/`
  and counts `@pytest.mark.skipif` alongside `pytest.skip(...)`, so the Docker capability guard must be added to
  `RECORDED_EXEMPTIONS` in the same change or `test_no_test_dodges_the_postgresql_gate` fails.
- **`.git/` is excluded from the build context, so `hatch-vcs` has no tags to read.** The editable self-install is
  built with `no-build-isolation` against the conda-forge `hatchling`/`hatch-vcs` already in `[dependencies]`, and
  `hatch-vcs` derives `dynamic = ["version"]` from git. The build supplies the version explicitly rather than shipping
  `.git`; the exact mechanism is recorded in the Completion Notes once verified against a real build.

#### Implementation findings (2026-08-28)

Everything below was observed against a real build and real containers, not derived.

- **The build works, and the version mechanism is the `ARG`.** `docker build --platform linux/amd64`
  succeeds; the image is 396 MB. `.dockerignore` excludes `.git/`, so `hatch-vcs` has no tags, and the
  build supplies the version through `ARG COMPONENT_VERSION` exported as `SETUPTOOLS_SCM_PRETEND_VERSION`
  on the `pixi install` line. **Verified both ways**: with the default the installed distribution reports
  `0.0.0` (which is also `[tool.hatch.version] fallback-version`, so the default agrees with what the
  backend would have produced on its own), and with `--build-arg COMPONENT_VERSION=9.8.7` it reports
  `9.8.7`. A pipeline passes the real version; nothing needs `.git` in the context.
- **`pixi run` wants exactly one writable path inside `/app`, and it is not required.** The path is
  `/app/.pixi/task-cache-v0/`, where pixi writes `default-web-<hash>.json`. Under
  `--read-only --tmpfs /tmp` the write simply does not happen and the component boots and serves anyway,
  so it is an optimisation rather than a requirement. `/app` was **not** made writable. The integration
  harness mounts a tmpfs over that one directory in the *writable* run, which is the spec's prescribed
  handling, and `docker diff` then reports nothing under `/app` at all.
- **`docker diff` on the writable run, verbatim, before the tmpfs was added:**
  `C /app`, `C /app/.pixi`, `C /app/.pixi/task-cache-v0`, `A /app/.pixi/task-cache-v0/default-web-…json`,
  `C /tmp`, `A /tmp/.gunicorn`, `A /tmp/.cache`, `A /tmp/.cache/rosetta`. With
  `--tmpfs /app/.pixi/task-cache-v0` it reduces to `C /tmp`, `A /tmp/.cache`, `A /tmp/.cache/rosetta`,
  `A /tmp/.gunicorn` — every changed path inside the temporary directory. (`/tmp/.cache/rosetta` is the
  emulation layer on an arm64 host and will not appear on a linux-amd64 runner; it is under `/tmp` either
  way, so the assertion holds on both.)
- **`PYTHONDONTWRITEBYTECODE=1` is load-bearing, not hygiene.** The editable install resolves `config` and
  `django_service` from `/app/src`, so CPython would write `__pycache__` beside the source on the first
  import of every container — a write under `/app` on a writable run, and a silent failure on a read-only
  one. Without the variable the `docker diff` assertion fails.
- **Start-up under an arbitrary UID on a read-only root filesystem: verified.**
  `docker run --user 12345:0 --read-only --tmpfs /tmp` with configuration supplied only as environment
  variables reaches `livez` 200 and `readyz` 200 roughly two seconds after start, with
  `drain.handler_installed` and gunicorn's `Application startup complete` in the log. Nothing is mounted
  and no configuration file participates.
- **`find / -xdev -name ".env" -o -name ".envs"` inside the image returns nothing.**
- **`collectstatic` at build produced 919 files and `staticfiles/staticfiles.json`,** under
  `config.settings.production` with the roster supplied inline on the `RUN` line. The image carries no
  `ENV` for any of those variables, which `tests/unit/test_payload_properties.py` asserts.
- **The release stage has to run before `web` will boot,** exactly as the reconciliation predicted. The
  harness runs it as a separate non-serving invocation of the same image, one `docker run … pixi run
  manage <step>` per step `component.toml` declares (`migrate --database default --noinput`), which is the
  form `docs/deployment.md` gives a deployment repository.
- **`env.db("DATABASE_URL")` is fine; a shell was not.** An early manual run failed with
  `settings.DATABASES is improperly configured` because zsh does not word-split an unquoted parameter
  expansion, so a whole block of `-e` flags reached `docker run` as one argument. Recorded because the
  symptom pointed convincingly at django-environ and at the image, and at neither.
- **Line-range drift, confirmed against the tree.** `static(settings.MEDIA_URL,
  document_root=settings.MEDIA_ROOT)` is at `src/config/urls.py:50`, inside the `urlpatterns` list opened
  at `:23`. The `home` and `about` routes are still present at `:36-41`.
- **Docker Desktop crashed during the first emulated build** (`rpc error: … EOF`, then a missing socket at
  `~/.docker/run/docker.sock`) and was restarted with `open -a Docker`. A repeat of the same build then
  completed. Recorded as an environment quirk of an arm64 machine emulating amd64, not as anything about
  the Dockerfile.

#### Verification actually run

| Step | Result |
|---|---|
| `pixi run test` immediately after `Dockerfile` first existed | `tests/unit/test_release_stage.py::test_no_dockerfile_instruction_migrates` **PASSED**, not skipped |
| `pixi run test` (unit) | 1198 passed, 4.42 s |
| `pixi run test-integration` | 295 passed, 6 skipped (all six the pre-existing `tests/integration/test_coverage_measurement.py` `--cov` guard); the five `test_image_payload.py` cases ran |
| `pixi run lint` | All checks passed |
| `pixi run typecheck` | Success: no issues found in 71 source files |
| `pixi run ci` | **exit 0** — pre-commit all Passed, build OK, mypy OK, ruff OK, 1499 passed, coverage **96.99 %** (floor 90) |
| `pixi run docs` (`mkdocs build --strict`) | Documentation built, no warnings; `deployment.md` was already at `mkdocs.yml` nav line 39, so no change was needed there — verified rather than assumed |

Note on the task names: this repository spells them `pixi run format`, `pixi run typecheck` and
`pixi run test-cov`, not `fmt`/`check`/`cov`.

### Completion Notes List

- **`Dockerfile` (NEW, root, `machinery`).** Digest-pinned `ghcr.io/prefix-dev/pixi` base with an explicit
  `--platform=linux/amd64` (`pixi.lock` declares no `linux-aarch64`, so `--locked` cannot resolve on any
  other base, and `gunicorn`/`uvicorn-worker` are `[target.linux-64.dependencies]`). Selective `COPY` of
  seven named files plus `src/` — never `COPY . .` — so no configuration file can arrive incidentally.
  `pixi install --locked -e default`, then `collectstatic` at build under `config.settings.production`
  with the stage-1 roster supplied inline, then `chgrp -R 0 /app && chmod -R g=u /app`. `ENV HOME=/tmp`,
  pixi/rattler caches under `/tmp`, `PIXI_FROZEN` + `PIXI_NO_INSTALL` (which together are `--as-is`, so
  run time performs no solve and modifies no environment), `PYTHONDONTWRITEBYTECODE=1`. `USER 1001`,
  `EXPOSE 8000`, no `VOLUME` at all, `CMD ["pixi", "run", "web"]`, nothing that migrates at any depth.
- **`.dockerignore` (NEW).** Everything Task 3 names, plus `.local-dev-keys/` (a generated dev signing
  keypair at the repository root — gitignored, and a private key in an image is a private key in a
  registry), `.DS_Store`, `__pycache__/`, `.agents/`, `.bmad-loop/`, `.claude/`, `.github/` and `tests/`.
  `pixi.toml`, `pixi.lock`, `pyproject.toml`, `manage.py`, `src/`, `component.toml`, `README.md` and
  `LICENSE` all stay — the last three because the editable self-install needs them.
- **`tests/dockerfile.py` (NEW).** The Dockerfile instruction parser, **promoted** from
  `tests/unit/test_release_stage.py` rather than copied, the way Story 5.5 promoted the pixi reader to
  `tests/pixi_manifest.py`. Carries `DOCKERFILE`, `EXECUTING_INSTRUCTIONS`, `ONBUILD_INSTRUCTION`,
  `CONTINUATION`, `COMMENT_PREFIX`, `HEREDOC_OPENER` and `instruction_lines`. Both call sites import it;
  nothing about the parse changed. Its synthetic execution stayed in `test_release_stage.py`, because the
  second half of each of those cases asserts a *migration* count, which is that module's question.
- **`tests/unit/test_payload_properties.py` (NEW), 13 cases.** A vacuity guard on the file itself; no
  `COPY` names a configuration file; a numeric non-root `USER`; `HOME` under `/tmp`; no `VOLUME` outside
  `/tmp`; no `ENV` bakes the build-stage roster; no file-based log handler in any of the four settings
  modules (asserted on the **resolved handler class**, so `FileHandler`'s three stdlib subclasses are
  covered by one `issubclass`, and `production.py`'s `mail_admins` correctly survives); the session store
  is not the file backend; and the two `MEDIA_ROOT` legs. It does **not** restate
  `test_no_dockerfile_instruction_migrates`.
- **`tests/integration/test_image_payload.py` (NEW), 5 cases.** Own network, `postgres:17`, the release
  stage run from `component.toml`'s declared steps, a `--read-only --tmpfs /tmp` run for start-up and the
  probes, and a **writable** run for `docker diff` — because a read-only container's diff is trivially
  empty and proves nothing. Both runs use `--user 12345:0`. Probes go over a runtime-assigned published
  port read back with `docker port` (the pixi base image has no `curl`, and a fixed port would collide).
  Every fixture removes what it created — containers, network, image — in `finally`.
- **`docs/deployment.md`.** New `## The component is a payload` with five subsections: no Dockerfile in a
  materialized component, the four zero-writable-path legs, running under an arbitrary UID, this
  repository's Dockerfile as machinery with the AD-32 template fork as a named governed exception, and the
  SC-3 boundary stated plainly.
- **`tests/unit/test_suite_policy.py`.** Added `"integration/test_image_payload.py": {"@pytest.mark.skipif": 1}`
  to `RECORDED_EXEMPTIONS` with the reasoning block above it in the established style. The
  `unit/test_release_stage.py` entry and its `pytest.skip` branch were **both left in place**, together —
  the branch accommodates the file's *absence*, which is the normal state in a materialized component.
- **`tests/unit/test_release_stage.py`.** Imports the promoted parser; the prose that described the
  Dockerfile as not yet existing was corrected, and the skip message now explains what the branch is for
  rather than when it retires. No assertion changed.
- Nothing was added to `[tool.coverage.run] omit`.

**Departures from the spec, and why.**

1. *Task 2's caches at build time.* The spec asks for the pixi and rattler caches under `/tmp`. Declaring
   that as `ENV` before the install layers would have baked the whole download cache into an image layer,
   so the install runs with the base image's root `HOME` and removes `/root/.cache` in the same `RUN`; the
   `/tmp` cache variables are declared after, where they govern run time. Same property, no bloat.
2. *Task 5's single container run.* Split into two, as the Planning reconciliation directs, because one
   run cannot demonstrate both start-up under `--read-only` and a meaningful `docker diff`.
3. *One extra assertion each side.* `test_no_env_instruction_bakes_the_variables_the_build_supplies_inline`
   (unit) and `test_static_files_are_baked_into_the_image` (integration) are not in the task list. The
   first makes good on a claim the Dockerfile's own comment makes; the second is AC #3's static leg, which
   otherwise had no behavioural assertion anywhere.

**Residual risks and things recorded rather than fixed.**

- **The `MEDIA_ROOT` residue stands.** `MEDIA_ROOT` is still `str(APPS_DIR / "media")`, `MEDIA_URL` is
  still `/media/`, and `src/config/urls.py:50` still calls `static(...)`. Read as a declaration that is a
  writable path inside the payload. It is inert today for two reasons, both now asserted: `static()`
  returns `[]` whenever `DEBUG` is false, so a deployed component mounts no media route; and no model in
  any installed application declares a `FileField`, so `production.py`'s `default` `FileSystemStorage` is
  never handed anything to save. **Epic 7's object-storage story under FR-25 owns removing the surface**,
  and the `default` backend is R-1's. Nothing here changed either.
- **The sessions residue is Story 5.7's.** `SESSION_ENGINE` is set nowhere in `src/`; what resolves is
  Django's global default, which is the database backend. This story asserts only its own claim — the
  resolved store is not the file backend and therefore writes nothing to local disk. Setting the value
  explicitly and asserting the equality remain 5.7's, and are not restated here.
- **`accelerator.toml` does not exist yet, so three new paths carry an unfulfilled AD-2 obligation.**
  `Dockerfile`, `.dockerignore`, `tests/unit/test_payload_properties.py` and
  `tests/integration/test_image_payload.py` are all `machinery` by default and must be **listed
  explicitly** when Epic 7 authors that file, because AD-2's input reconciliation fails a path claimed by
  no disposition. The obligation is recorded in the Dockerfile's header comment, in `.dockerignore`'s, and
  in both test modules' docstrings.
- **R-4 is inherited, not created.** The GitHub-template fork ships from `main` HEAD carrying this
  Dockerfile and can therefore opt out of the image pipeline. AD-32 accepts that; nothing here mitigates
  it, and `docs/deployment.md` now names it.
- **`pixi run` will try to write `/app/.pixi/task-cache-v0` on every start.** On a read-only root
  filesystem the write fails silently and costs nothing but the cache. If a future pixi makes that path
  mandatory, the fix is a tmpfs at that path in the deployment manifest, not a writable `/app`.
- **Build cost.** The integration module builds the image inside the suite. On a linux-amd64 runner this
  is native; on an arm64 developer machine every layer runs under emulation. Timeouts are set generously
  (one hour for the build) for that reason.

**What could not be verified, and why.**

- **A completely cold build inside the harness.** The runs timed above reused BuildKit's layer cache, so
  the 5–15 s figures are warm-cache figures and not what a CI runner will see. A genuinely cold build
  *was* performed twice by hand today — `pixi install --locked` ran for real (18.2 s, reported as `DONE`
  rather than `CACHED`) and again from that layer down for the `--build-arg` check — so the cold path is
  known to work; its duration on the gate's runner is not measured.
- **The gate's own Linux amd64 runner.** Everything here ran on macOS/arm64 with Docker Desktop 29.6.1,
  against an emulated `linux/amd64` image. The one observable difference found is `/tmp/.cache/rosetta` in
  `docker diff`, which is under `/tmp` and therefore passes the same assertion; nothing else is expected
  to differ, but it has not been run there.
- **Behaviour under a platform that assigns a UID for real.** `--user 12345:0` is the closest local
  approximation. Nothing in this repository starts a component on the target platform — that is the SC-3
  boundary this story deliberately does not cross.

### File List

**New**

- `Dockerfile`
- `.dockerignore`
- `tests/dockerfile.py`
- `tests/unit/test_payload_properties.py`
- `tests/integration/test_image_payload.py`

**Modified**

- `tests/unit/test_release_stage.py` — imports the promoted parser; stale "does not exist yet" prose corrected. No assertion changed.
- `tests/unit/test_suite_policy.py` — one `RECORDED_EXEMPTIONS` entry plus its reasoning block.
- `docs/deployment.md` — new `## The component is a payload` section.

**Read only, unchanged**

- `mkdocs.yml` — `deployment.md` already registered in `nav` (line 39); verified, not edited.
- `pyproject.toml` — `[tool.coverage.run] omit` untouched (AD-20).
- `pixi.toml`, `component.toml`, `src/config/settings/*`, `src/config/urls.py`.


## Orchestrating-session addendum — the payload did not actually run read-only

The dev session was stopped before it could commit, and its work was finished
inline rather than re-driven. Finishing it surfaced a defect the session had seen,
misdiagnosed and worked around in the wrong place.

**The defect.** `pixi run <task>` writes
`/app/.pixi/task-cache-v0/<env>-<task>-<hash>.json` when the task completes. The
write happens *after* the task's own exit status is known, so when it fails pixi
exits non-zero with the task's output already printed. That is how
`pixi run manage migrate` applied every migration, provisioned the designated
groups, reported success -- and then failed the release stage with
`Permission denied (os error 13)` under the image's `g=rX` tree. Under
`--read-only` the same write fails with `Read-only file system (os error 30)`.

**What the session concluded, and why it was wrong.** Its module docstring stated
that the cache write is "an optimisation, not a requirement: under `--read-only`
the write fails, pixi carries on and the component boots". Both halves are false:
pixi exits non-zero, and the component's release stage did not complete. The
session then mounted a tmpfs over that one directory in the test fixture, which
made the container cases pass and left the release-stage fixture failing -- the
state the tree was in when the run stopped.

**Why the workaround was in the wrong place even where it worked.** A deployment
platform mounts `/tmp` and knows nothing about pixi's internals. A payload that
needs a second, pixi-specific mount to run read-only does not have the property
this story exists to verify, so a harness that supplies that mount is verifying
something the platform will not reproduce.

**The fix.** The image owns it: `Dockerfile` links
`/app/.pixi/task-cache-v0` to `/tmp`, and the integration runs use a plain
`--read-only --tmpfs /tmp`. No pixi flag or environment variable relocates that
cache -- `PIXI_CACHE_DIR` and `RATTLER_CACHE_DIR` govern the package caches,
`--frozen` and `--no-install` govern solving -- so a symlink is what is available.

The link targets `/tmp` itself rather than a path beneath it, and that is not a
detail: the platform mounts a fresh tmpfs there, so a link to `/tmp/<anything>`
dangles, and `mkdir` on a name occupied by a dangling symlink fails with
`File exists (os error 17)` rather than following it. Both were reproduced against
a built image before the Dockerfile was touched.

**What was removed.** The `--tmpfs /app/.pixi/task-cache-v0` mount, its constant
and the incorrect paragraph describing the write as optional. The
`writable_container` fixture now mounts nothing over any path in `/app`, so
`docker diff` reports the whole of what the container wrote -- which is what makes
the no-writes assertion mean anything.

**What was added.** `test_the_pixi_task_cache_is_kept_out_of_the_application_root`
in `tests/unit/test_payload_properties.py`, because the integration case needs
Docker and this one does not, and because the instruction is the kind a later
reader deletes as inscrutable. Negative control: removing the `RUN` from the
Dockerfile fails it.

**Story 5.5's obligation is discharged.**
`tests/unit/test_release_stage.py::test_no_dockerfile_instruction_migrates`
reports **passed** rather than skipped now that `Dockerfile` exists, confirmed
directly. Its `pytest.skip` branch and the matching `RECORDED_EXEMPTIONS` entry
stay, which is what that story's task list specifies: the branch is what keeps the
module usable in a materialized component where the file is correctly absent.

**Verification.** `pixi run ci` -- exit 0, 1509 passed, coverage 96.99%. The five
`tests/integration/test_image_payload.py` cases pass against a freshly built
image, including the release stage that was failing.
