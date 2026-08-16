# Story 1.9: Django runs on the LTS release

Status: ready-for-dev

## Story

As a platform engineer,
I want Django pinned to the 5.2 LTS series rather than the 6.0 feature release,
so that components generated from this accelerator sit on a base with a support window measured in years rather than months.

## Acceptance Criteria

**Traceability:** supports SC-1 · revises the stack line at `epics.md:180` and the version table in `ARCHITECTURE-SPINE.md`

1. **Given** `pixi.toml` declares `django = ">=6.0,<7"`
   **When** this story lands
   **Then** it declares the 5.2 LTS series instead
   **And** `pixi.lock` resolves a `5.2.x` Django

2. **Given** `django-stubs` is version-locked to Django's minor series and strict mypy is a gate condition (Story 1.3)
   **When** Django moves to 5.2
   **Then** `django-stubs` moves to its matching `5.2` series in the same change
   **And** `pixi run ci` exits 0 with `typecheck` reporting no issues

3. **Given** every other Django-dependent package declares a range
   **When** the lock is regenerated
   **Then** no package resolves outside its declared Django range
   **And** the suite passes against a real PostgreSQL as Story 1.2 requires

4. **Given** two planning documents name Django 6.0 as the stack version
   **When** the pin changes
   **Then** `epics.md` and `ARCHITECTURE-SPINE.md` are amended in the same change
   **And** the reason for choosing LTS is recorded where the version is named

5. **Given** a future change could raise Django past the LTS series without anyone noticing
   **When** the suite runs
   **Then** a test fails if the declared Django leaves the LTS series
   **And** a test fails if the `django-stubs` minor stops matching the declared Django minor

## Tasks / Subtasks

- [ ] Task 1 — Move the Django pin to the LTS series (AC: #1)
  - [ ] `pixi.toml:22` reads `django = ">=6.0,<7"`. Replace it with the 5.2 LTS series — `django = ">=5.2,<5.3"`. Do **not** write `>=5.2,<6`: that admits 5.3+ and future feature releases, which is the thing this story exists to prevent. The LTS series is a minor series, so the cap is the next minor.
  - [ ] Add a comment above the pin recording *why*: 5.2 is the LTS with support to April 2028; 6.0 is a feature release inherited from the cookiecutter-django origin (`a96be2d`) and formalised in `45afb1c` without the LTS question ever being asked. Name the next LTS (6.2, April 2027) as the intended successor so the exit condition is written down.
  - [ ] **Three packages floor at exactly `>=5.2`** — `django-redis 7.0.0`, `djangorestframework 3.18.0` and `django-debug-toolbar 7.1.1`. 5.2 is therefore the minimum viable Django for this tree; there is no headroom below it. Record this beside the pin so a future "downgrade further" is refused on evidence rather than re-derived.

- [ ] Task 2 — Move the type stubs in the same change (AC: #2)
  - [ ] `pixi.toml:126` reads `django-stubs = ">=6.0,<7"`. `django-stubs` tracks Django's minor series — the 6.x line is built against Django 6.x — so leaving it would type-check a 5.2 runtime against 6.x stubs. Story 1.3 made `typecheck` a gate condition under `strict`, so this is a correctness change, not a tidy-up. Move it to `>=5.2,<5.3`. conda-forge has `5.2.0`–`5.2.9`.
  - [ ] `pixi.toml:128` reads `djangorestframework-stubs = ">=3.17,<4"`. Check what the resolver selects once `django-stubs` moves — `djangorestframework-stubs` depends on `django-stubs` and may need its own adjustment. Determine this from the solve rather than assuming; record the outcome in Completion Notes.
  - [ ] Run `pixi install` and confirm the solve succeeds before touching anything else. If it fails, capture the full conflict output in Debug Log References — a resolution failure here is the story's central risk and must be reported, not worked around with a loosened pin.

- [ ] Task 3 — Regenerate the lock and verify the tree (AC: #1, #3)
  - [ ] Run the project's re-install path so `pixi.lock` is regenerated. Confirm the locked Django is `5.2.x` and the locked `django-stubs` is `5.2.x`.
  - [ ] Verify no package resolves outside its declared Django range. The declared ranges as of 2026-08-16, all of which admit 5.2: `django-allauth >=4.2`, `django-anymail >=2.0`, `django-celery-beat >=2.2,<6.1`, `django-cors-headers >=4.2`, `django-crispy-forms >=2.2`, `crispy-bootstrap5 >=4.2`, `django-environ >=1.8`, `django-redis >=5.2,<7.0`, `djangorestframework >=5.2`, `drf-spectacular >=2.2`, `django-structlog >=4.2`, `django-timezone-field >=4.2,<6.2`, `django-storages >=3.2`, `django-debug-toolbar >=5.2`, `django-extensions >=4.2`. Re-read these from the solve rather than trusting this list — it is a snapshot, and the point of the task is to check.
  - [ ] **Python stays at 3.14.** Django 5.2.15 carries the `Programming Language :: Python :: 3.14` classifier, so the LTS move does not force a Python downgrade. Do not touch `python = "3.14.*"`.
  - [ ] Run the full suite against a real PostgreSQL 17 as Story 1.2 established, not only against the sqlite substitution. Record the command and result.

- [ ] Task 4 — Amend the planning documents that name the version (AC: #4)
  - [ ] `epics.md:180` — the stack line reads "Python 3.14 · Django 6.0 · ...". Update the Django entry and note the LTS rationale inline.
  - [ ] `ARCHITECTURE-SPINE.md` — the version table names Django 6.0; update it and its surrounding prose where the version is load-bearing. Do not rewrite the R-1 risk entry to claim this story resolves it (see Task 5).
  - [ ] Do **not** rewrite historical records — Change Logs, Debug Log References, and Review Triage Logs in completed story specs describe what was actually run against Django 6.0 and are evidence, not configuration. Amend forward-looking statements only.

- [ ] Task 5 — State plainly what this story does not fix (AC: #4)
  - [ ] **R-1 is unchanged.** `django-storages 1.14.6` — still the latest release anywhere as of 2026-08-16, unchanged since 2025-04-02 — declares `Framework :: Django` classifiers of `3.2, 4.1, 4.2, 5.0, 5.1`. It supports neither 5.2 nor 6.0. Its upstream Django 5.2 support landed 2025-06-17 and has never been released. Moving to LTS narrows the gap (one minor behind rather than two majors) but does not close it.
  - [ ] Record this in Completion Notes and leave the spine's ordered escalation for R-1 intact: spike first, then a conda-forge feedstock push with a time-boxed package-index exception, then a component-owned backend as last resort.
  - [ ] If Story 1.8's spike has already landed, note whether its result was obtained against Django 6.0 and therefore needs re-running against 5.2. Do not re-run it here; record the finding.

- [ ] Task 6 — Tests (AC: #5)
  - [ ] Extend `tests/unit/test_dependency_policy.py` — the file Stories 1.7 and 1.8 own — rather than creating a new module.
  - [ ] Assert the declared Django is the LTS series: read the `django` requirement from `pixi.toml` and fail if its floor leaves `5.2` or its cap admits a later minor. The failure message must say *why* LTS is the policy, not merely that the value changed.
  - [ ] Assert stub/runtime alignment: the `django-stubs` minor must equal the declared `django` minor. This is the invariant that silently breaks strict mypy, and nothing currently asserts it.
  - [ ] Assert against the **lock** as well as the manifest, as `test_lock_file_has_no_non_conda_forge_source` does: a manifest can be right while the lock is stale.
  - [ ] **Host-agnostic, per Story 1.7.** Any assertion touching a channel or index must match on channel identity by containment — `"conda-forge" in url` — never on `conda.anaconda.org`, `pypi.org`, or a path segment. This accelerator runs against private mirrors (JFrog Artifactory), where a repository may be named `conda-forge-remote`.

## Dev Notes

### Architecture Constraints

- **Provenance.** Django 6.0 was not chosen against alternatives. The repository's first commit is `a96be2d feat: initial setup and config of cookiecutter-django`; cookiecutter-django tracks the current feature release, not the LTS. The pin `django = ">=6.0,<7"` was written one commit later in `45afb1c feat: restructure into src layout and adopt pixi toolchain`. No planning document evaluates 5.2 LTS — the question was never posed.
- **What *was* decided** is 6.0 rather than 6.1, because `django-celery-beat` capped Django `<6.1` and allowing 6.1 would have made the `[environments]` matrix resolve two different Djangos. That reasoning is about which *feature* release to take and does not survive contact with the LTS question: 5.2 sits well inside `>=2.2,<6.1`.
- **Support window** is the whole point. Django 6.0 shipped December 2025 as a feature release; 6.1 already exists. Django 5.2 LTS is supported to April 2028. Components generated from this accelerator inherit whatever it pins, so a feature release propagates a short support window into every downstream component.
- **Strict mypy is a gate condition** (Story 1.3, AD-18). That is what makes the `django-stubs` move part of this story rather than a follow-up: mismatched stubs produce wrong type checking that still exits 0.

### Source Tree — files to touch

- `pixi.toml` — `django` pin (`:22`), `django-stubs` (`:126`), possibly `djangorestframework-stubs` (`:128`)
- `pixi.lock` — regenerated, not hand-edited
- `tests/unit/test_dependency_policy.py` — extended (Task 6)
- `_bmad-output/planning-artifacts/epics.md` — stack line at `:180`
- `_bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md` — version table

Do not touch: `python = "3.14.*"`; `src/` (no application code depends on a 6.0-only API — verify this rather than assuming, and report any that does); the R-1 risk entry's escalation ladder.

### Testing Requirements

Done means `pixi run ci` exits 0 — including `typecheck` under `strict`, which is the step most likely to surface a real problem, since the stubs change with the runtime. A green suite against sqlite alone does not satisfy AC #3; the PostgreSQL run Story 1.2 established is required.

If any application code turns out to depend on Django 6.0 behaviour, that is a genuine finding: report it in Completion Notes with the file and line rather than silently rewriting it, because it changes the size of this story.

### References

- [Source: pixi.toml:22] — the Django pin
- [Source: pixi.toml:126,128] — the stub pins
- [Source: epics.md:180] — the stack line naming Django 6.0
- [Source: ARCHITECTURE-SPINE.md] — version table and R-1
- [Source: git a96be2d, 45afb1c] — cookiecutter-django origin and the pin's introduction
- Django 5.2.15 declares `Programming Language :: Python :: 3.14`; Django 6.0.8 declares `python >=3.12`
- django-storages 1.14.6 `Framework :: Django` classifiers: 3.2, 4.1, 4.2, 5.0, 5.1

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
