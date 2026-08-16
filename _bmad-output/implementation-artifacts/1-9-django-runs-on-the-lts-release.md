---
baseline_revision: 7817302
final_revision: 8f8ee32
review_loop_iteration: 0
followup_review_recommended: true
status: done
warnings: []
---

# Story 1.9: Django runs on the LTS release

Status: done

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

- [x] Task 1 — Move the Django pin to the LTS series (AC: #1)
  - [x] `pixi.toml:22` reads `django = ">=6.0,<7"`. Replace it with the 5.2 LTS series — `django = ">=5.2,<5.3"`. Do **not** write `>=5.2,<6`: that admits 5.3+ and future feature releases, which is the thing this story exists to prevent. The LTS series is a minor series, so the cap is the next minor.
  - [x] Add a comment above the pin recording *why*: 5.2 is the LTS with support to April 2028; 6.0 is a feature release inherited from the cookiecutter-django origin (`a96be2d`) and formalised in `45afb1c` without the LTS question ever being asked. Name the next LTS (6.2, April 2027) as the intended successor so the exit condition is written down.
  - [x] **Three packages floor at exactly `>=5.2`** — `django-redis 7.0.0`, `djangorestframework 3.18.0` and `django-debug-toolbar 7.1.1`. 5.2 is therefore the minimum viable Django for this tree; there is no headroom below it. Record this beside the pin so a future "downgrade further" is refused on evidence rather than re-derived.

- [x] Task 2 — Move the type stubs in the same change (AC: #2)
  - [x] `pixi.toml:126` reads `django-stubs = ">=6.0,<7"`. `django-stubs` tracks Django's minor series — the 6.x line is built against Django 6.x — so leaving it would type-check a 5.2 runtime against 6.x stubs. Story 1.3 made `typecheck` a gate condition under `strict`, so this is a correctness change, not a tidy-up. Move it to `>=5.2,<5.3`. conda-forge has `5.2.0`–`5.2.9`.
  - [x] `pixi.toml:128` reads `djangorestframework-stubs = ">=3.17,<4"`. Check what the resolver selects once `django-stubs` moves — `djangorestframework-stubs` depends on `django-stubs` and may need its own adjustment. Determine this from the solve rather than assuming; record the outcome in Completion Notes.
  - [x] Run `pixi install` and confirm the solve succeeds before touching anything else. If it fails, capture the full conflict output in Debug Log References — a resolution failure here is the story's central risk and must be reported, not worked around with a loosened pin.

- [x] Task 3 — Regenerate the lock and verify the tree (AC: #1, #3)
  - [x] Run the project's re-install path so `pixi.lock` is regenerated. Confirm the locked Django is `5.2.x` and the locked `django-stubs` is `5.2.x`.
  - [x] Verify no package resolves outside its declared Django range. The declared ranges as of 2026-08-16, all of which admit 5.2: `django-allauth >=4.2`, `django-anymail >=2.0`, `django-celery-beat >=2.2,<6.1`, `django-cors-headers >=4.2`, `django-crispy-forms >=2.2`, `crispy-bootstrap5 >=4.2`, `django-environ >=1.8`, `django-redis >=5.2,<7.0`, `djangorestframework >=5.2`, `drf-spectacular >=2.2`, `django-structlog >=4.2`, `django-timezone-field >=4.2,<6.2`, `django-storages >=3.2`, `django-debug-toolbar >=5.2`, `django-extensions >=4.2`. Re-read these from the solve rather than trusting this list — it is a snapshot, and the point of the task is to check.
  - [x] **Python stays at 3.14.** Django 5.2.15 carries the `Programming Language :: Python :: 3.14` classifier, so the LTS move does not force a Python downgrade. Do not touch `python = "3.14.*"`.
  - [x] Run the full suite against a real PostgreSQL 17 as Story 1.2 established, not only against the sqlite substitution. Record the command and result.

- [x] Task 4 — Amend the planning documents that name the version (AC: #4)
  - [x] `epics.md:180` — the stack line reads "Python 3.14 · Django 6.0 · ...". Update the Django entry and note the LTS rationale inline.
  - [x] `ARCHITECTURE-SPINE.md` — the version table names Django 6.0; update it and its surrounding prose where the version is load-bearing. Do not rewrite the R-1 risk entry to claim this story resolves it (see Task 5).
  - [x] Do **not** rewrite historical records — Change Logs, Debug Log References, and Review Triage Logs in completed story specs describe what was actually run against Django 6.0 and are evidence, not configuration. Amend forward-looking statements only.

- [x] Task 5 — State plainly what this story does not fix (AC: #4)
  - [x] **R-1 is unchanged.** `django-storages 1.14.6` — still the latest release anywhere as of 2026-08-16, unchanged since 2025-04-02 — declares `Framework :: Django` classifiers of `3.2, 4.1, 4.2, 5.0, 5.1`. It supports neither 5.2 nor 6.0. Its upstream Django 5.2 support landed 2025-06-17 and has never been released. Moving to LTS narrows the gap (one minor behind rather than two majors) but does not close it.
  - [x] Record this in Completion Notes and leave the spine's ordered escalation for R-1 intact: spike first, then a conda-forge feedstock push with a time-boxed package-index exception, then a component-owned backend as last resort.
  - [x] If Story 1.8's spike has already landed, note whether its result was obtained against Django 6.0 and therefore needs re-running against 5.2. Do not re-run it here; record the finding.

- [x] Task 6 — Tests (AC: #5)
  - [x] Extend `tests/unit/test_dependency_policy.py` — the file Stories 1.7 and 1.8 own — rather than creating a new module.
  - [x] Assert the declared Django is the LTS series: read the `django` requirement from `pixi.toml` and fail if its floor leaves `5.2` or its cap admits a later minor. The failure message must say *why* LTS is the policy, not merely that the value changed.
  - [x] Assert stub/runtime alignment: the `django-stubs` minor must equal the declared `django` minor. This is the invariant that silently breaks strict mypy, and nothing currently asserts it.
  - [x] Assert against the **lock** as well as the manifest, as `test_lock_file_has_no_non_conda_forge_source` does: a manifest can be right while the lock is stale.
  - [x] **Host-agnostic, per Story 1.7.** Any assertion touching a channel or index must match on channel identity by containment — `"conda-forge" in url` — never on `conda.anaconda.org`, `pypi.org`, or a path segment. This accelerator runs against private mirrors (JFrog Artifactory), where a repository may be named `conda-forge-remote`.

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

claude-opus-5[1m] (Claude Opus 5, 1M context), via the bmad-loop dev-auto run on 2026-08-16.

### Debug Log References

**The solve failed on the first attempt, exactly where Task 2 said the story's central risk was.** Captured rather than worked around; the resolution was to move a third pin, not to loosen one.

```
$ pixi lock          # after django >=5.2,<5.3 and django-stubs >=5.2,<5.3
  × failed to solve requirements of environment 'default' for platform 'osx-arm64'
  ╰─▶ Cannot solve the request because of: djangorestframework-stubs >=3.17,<4
      cannot be installed because there are no viable options:
      └─ djangorestframework-stubs 3.18.0 would require
         └─ django-stubs >=6.0.9, for which no candidates were found.
      ├─ djangorestframework-stubs 3.17.0 | 3.17.1 would require
      │     └─ django-stubs >=6.0.4 ...
      └─ django-stubs >=5.2,<5.3 cannot be installed because there are no
         viable options: 5.2.9, 5.2.8, 5.2.7, 5.2.6, 5.2.5, 5.2.2, 5.2.1, 5.2.0
         [all] conflict with the versions reported above.
```

Task 2 asked for the `djangorestframework-stubs` outcome to be *determined from the solve*, so it was: the pin was set to `"*"` for one probe run, the solver chose `3.16.9`, and the manifest was then pinned to `>=3.16.9,<3.17` — the wildcard did not survive the probe.

```
$ pixi lock          # probe, djangorestframework-stubs = "*"
Environment: dev
  ~ (conda) django                     6.0.8 pyhd8ed1ab_0   ->  5.2.15 pyhd8ed1ab_0
  ~ (conda) django-stubs               6.0.7 pyhcf101f3_0   ->  5.2.9 pyhcf101f3_0
  ~ (conda) djangorestframework-stubs  3.17.1 pyhcf101f3_0  ->  3.16.9 pyhcf101f3_0
```

**Second failure, and the one Dev Notes predicted would be the interesting one:** `typecheck` under `strict` found four errors that the 6.0 stubs did not report.

```
$ pixi run typecheck
src/django_service/users/forms.py:20: error: Name "admin_forms.UserChangeForm.Meta" is not defined  [name-defined]
src/django_service/users/forms.py:20: error: Class cannot subclass "Meta" (has type "Any")  [misc]
src/django_service/users/forms.py:30: error: Name "admin_forms.UserCreationForm.Meta" is not defined  [name-defined]
src/django_service/users/forms.py:30: error: Class cannot subclass "Meta" (has type "Any")  [misc]
Found 4 errors in 1 file (checked 37 source files)
```

Diagnosed against both stub trees rather than assumed. `django-stubs` 6.0.7 declares `class Meta` inside `UserChangeForm` (`django-stubs/contrib/auth/forms.pyi:87`); the 5.2.9 stub declares `UserChangeForm` with `password` and `__init__` and no nested `Meta`, and its `BaseUserCreationForm` — which `UserCreationForm` inherits from — has none either. Django itself declares both at runtime, so the base classes are real and only the stubs are missing them.

**Third: the R-1 verdict-versus-lock check fired**, which is the guard Story 1.8 built doing its job rather than a defect.

```
$ pixi run test
FAILED tests/unit/test_dependency_policy.py::test_the_recorded_verdict_names_the_versions_the_lock_resolves
E  AssertionError: the lock has moved off the runtime the R-1 verdict is a statement about:
   ['django: verdict says 6.0, lock resolves 5.2.15 on linux-64', ... osx-arm64, ... win-64]
```

### Completion Notes List

**Final pins and what resolved.** `django = ">=5.2,<5.3"` → `5.2.15`; `django-stubs = ">=5.2,<5.3"` → `5.2.9`; `djangorestframework-stubs = ">=3.16.9,<3.17"` → `3.16.9`. `python = "3.14.*"` → `3.14.6`, untouched, and Django 5.2.15 runs on it. The runtime `djangorestframework = ">=3.17,<4"` was **not** touched and still resolves `3.18.0`: the stub line tracks `django-stubs`, not DRF's own version, which is why the two numbers now differ.

**`djangorestframework-stubs` had to move, and this is the finding Task 2 asked for.** It is not a matter of taste: `>=3.17,<4` has no viable option once `django-stubs` is on 5.2, because 3.17.0/3.17.1 require `django-stubs >=6.0.4` and 3.18.0 requires `>=6.0.9`. The 3.16 line is the one built against the 5.2 stubs. All three stub/runtime pins move together at the next LTS.

**Application code needed one change, and it is a genuine finding rather than a tidy-up.** `src/django_service/users/forms.py:20` and `:30` subclass `admin_forms.UserChangeForm.Meta` and `admin_forms.UserCreationForm.Meta`. Both exist at runtime in every Django version in question; the *stubs* differ — 6.0.7 declares `UserChangeForm.Meta`, the 5.2 line declares neither. This is the reverse of what Dev Notes anticipated: no application code depends on Django 6.0 *behaviour*, but two lines depended on the 6.0 *stubs* being more complete. Fixed with narrow `# type: ignore[name-defined,misc]` comments carrying the reasoning, which `warn_unused_ignores` deletes automatically the day the stubs declare the nested classes. Nothing else in `src/` moved.

**No package resolves outside its declared Django range (AC #3), read back from the solve rather than from the story's snapshot.** Every locked package that declares a dependency on `django`, with its recipe's own constraint: `crispy-bootstrap5 >=4.2`, `django-allauth >=4.2`, `django-anymail >=2.0`, `django-celery-beat >=2.2,<6.1`, `django-cors-headers >=4.2`, `django-crispy-forms >=2.2`, `django-debug-toolbar >=5.2`, `django-environ >=1.8`, `django-extensions >=4.2`, `django-ipware` (unconstrained), `django-redis >=5.2,<7.0`, `django-storages >=3.2`, `django-structlog >=4.2`, `django-stubs` (unconstrained), `django-stubs-ext` (unconstrained), `django-timezone-field >=4.2,<6.2`, `django_coverage_plugin` (unconstrained), `djangorestframework >=5.2`, `drf-spectacular >=2.2`, `opentelemetry-instrumentation-django >=2.0`. Every one admits 5.2.15. Two corrections to the story's snapshot, neither material: the locked `django-debug-toolbar` is `7.0.0` rather than the `7.1.1` the task names (its floor is still `>=5.2`), and `django-ipware`, `django-stubs-ext` and `django_coverage_plugin` declare `django` with no constraint at all.

**Worth a second look but not a defect:** `django-stubs 5.2.9` depends on `django-stubs-ext >=5.2.9`, and the solver resolved `django-stubs-ext 6.0.8`. That satisfies the declared constraint and `typecheck` is clean, so it is left as the solver produced it rather than pinned by hand.

**R-1 is unchanged, and this story does not touch it (Task 5).** `django-storages 1.14.6` — still the newest release anywhere, unchanged since 2025-04-02 — declares `Framework :: Django` for 3.2, 4.1, 4.2, 5.0 and 5.1. It supports neither 5.2 nor 6.0; its Django 5.2 support landed upstream 2025-06-17 and has never been released. The LTS move narrows the gap from two majors to one minor and closes nothing. The escalation ladder in the spine (spike → conda-forge feedstock push with a time-boxed package-index exception → component-owned backend) is left exactly as it was, and no rung is retired.

**Story 1.8's spike verdict was obtained against Django 6.0 and does not carry to 5.2. It was not re-run here** (the story says not to) **and it has not been rewritten.** What was recorded instead is that it is out of scope: an `Out of scope: django 5.2` line was added to the verdict block in `pixi.toml` and to its second copy under "Object storage fitness (R-1)" in `docs/development.md`, both saying plainly that R-1 is open again against the LTS runtime and that `pixi run spike-storage` has to be re-run and the verdict re-recorded before Epic 7 Story 7.5 acts on it. Everything above that line is untouched — it is the record of what actually ran on 2026-08-16.

That required widening the gate-side rule rather than deleting it. `test_the_recorded_verdict_names_the_versions_the_lock_resolves` previously asserted "the lock still holds the verdict's runtime", which this change makes false. It now asserts "the lock still holds it, **or** the block names what it no longer covers, at the release line the lock actually resolves" — and it fails from the other direction too, so a disclaimer that has gone stale (spike re-run, `Tested against:` caught up, the line left behind) fails rather than becoming a permanent exemption. `docs/development.md` is reconciled against the manifest on the disclaimer as well as on the verdict, for the reader that copy exists for.

`tests/spikes/spike_django_storages_fitness.py:74` still asserts `VERDICT_VERSIONS` includes `django: "6.0"` and was deliberately left alone: it is the spike's own record of what it ran against, it is collected by nothing in the gate, and it is what makes a re-run against 5.2 fail loudly instead of silently inheriting the old verdict.

**Left for a later, deliberate change — three documents still name Django 6.0 in a forward-looking way, all outside AC #4's two.** `_bmad-output/specs/spec-django-15-factor-base/SPEC.md:70,106` and `capability-map.md:30` state the fitness rule and R-1 against "the pinned Django 6.0"; `_bmad-output/implementation-artifacts/7-5-object-storage-attaches-an-s3-compatible-backend-with-a-local-substitution.md:57,97,153` instructs a future story that the stack is Django 6.0 and that "Django 6.0 uses `STORAGES`" (still true of 5.2 — `STORAGES` has existed since 4.2 — so that instruction is not wrong, only misdated); `8-1-...md:106` cites the spine's old Django row. Story 7.5 in particular will act on a stale version. Not amended here because AC #4 scopes this story to `epics.md` and `ARCHITECTURE-SPINE.md`, and rewriting a not-yet-run story's Dev Notes is a bigger act than it looks.

Historical records were left alone throughout: Change Logs, Debug Log References, Review Triage Logs and Auto Run Results in completed story specs, `epics.md:574` (Story 1.8's own acceptance criterion, which describes what was true when it was written), and the architecture review documents all still say 6.0 because that is what was run.

**Review pass, 2026-08-16 — three of the notes above were superseded by it, and this says which.** The review's findings were applied to this same change rather than deferred, so:

- **`django-stubs-ext` is pinned rather than left as the solver produced it.** The note above records `6.0.8` resolving beside `django-stubs 5.2.9` as "worth a second look but not a defect". The review's point stands: the story's invariant is that the stubs track the runtime series, and `django-stubs` requires only `django-stubs-ext >=5.2.9`, so nothing held the ext package to 5.2. `django-stubs-ext = ">=5.2.9,<5.3"` was added to `[feature.dev.dependencies]`; the solve succeeded (`6.0.8 -> 5.2.9` in `dev` and `spike-storage`) and `pixi run typecheck` stayed clean, so the pin was kept and both the manifest and lock alignment tests now cover both stub packages.
- **The two `Meta` bases are typed rather than ignored.** `# type: ignore[name-defined,misc]` made each base `Any`, which stopped mypy checking the bodies of the two classes whose job is to constrain the admin forms. django-stubs stubs no form's nested `Meta` at all -- it models the options through `ModelFormOptions` -- so there is no upstream base to name; `forms.py` now declares a typed stand-in under `TYPE_CHECKING`, the idiom the file already used for `_UserChangeFormBase`, and inherits Django's real `Meta` at runtime exactly as before. Verified by injection: a wrong `error_messages` now fails `typecheck` where it previously passed.
- **The floor evidence beside the pin named a version this tree does not have.** It read "django-debug-toolbar 7.1.1"; the lock resolves `7.0.0`. Every version and constraint in that block was re-read from `pixi.lock`: `django-redis 7.0.0` declares `django >=5.2,<7.0` (a cap as well as a floor, now stated as such), `djangorestframework 3.18.0` and `django-debug-toolbar 7.0.0` declare `django >=5.2`, and `django-celery-beat 2.9.0` declares `django >=2.2,<6.1`.

The gate-side rules were tightened in the same pass: a disclaimer may no longer be coarser than the verdict it narrows, may not name the package the verdict is *about* (only the runtime it was earned on), and is now read from every occurrence of the label rather than the first; `django-storages` may not leave its staging feature while a disclaimer stands; the docs copy carries a `Tested against:` listing that is reconciled against the manifest's; and the LTS cap is derived from `DJANGO_LTS_SERIES` so that editing the one constant really is the whole move.

**Verification.**

| Command | Result |
| --- | --- |
| `pixi lock` | Solved after the drf-stubs move; `django 6.0.8 → 5.2.15`, `django-stubs 6.0.7 → 5.2.9`, `djangorestframework-stubs 3.17.1 → 3.16.9` in all three environments |
| `pixi install -a` | `default`, `dev`, `spike-storage` all installed |
| `pixi run typecheck` | `Success: no issues found in 37 source files` |
| `pixi run lint` | `All checks passed!` |
| `pixi run test` | `231 passed` (225 before; six added) |
| `pixi run test-integration` | `66 passed, 6 skipped` — the sqlite substitution |
| `DATABASE_URL=postgres://gateuser:gatepass@localhost:55432/gatedb pixi run ci` | **exit 0** — `303 passed`, coverage 92.46% |
| `pixi run ci` (no `DATABASE_URL`) | **exit 0** — `303 passed`, coverage 92.46% |

AC #3's PostgreSQL half was run the way Story 1.2 established it in `.github/workflows/ci.yml`: a real `postgres:17` server (`PostgreSQL 17.11`) in a container with `POSTGRES_USER=gateuser` / `POSTGRES_PASSWORD=gatepass` / `POSTGRES_DB=gatedb`, health-gated on `pg_isready -h localhost`, reached through the job-level `DATABASE_URL` that `config/settings/base.py:57` hands to `env.db()`. Confirmed it was actually used rather than silently falling back to sqlite: `test_gatedb` was present in the server's database list after the run. The container was removed afterwards; nothing was left running.

### File List

- `pixi.toml` — `django` `>=6.0,<7` → `>=5.2,<5.3`; `django-stubs` `>=6.0,<7` → `>=5.2,<5.3`; `djangorestframework-stubs` `>=3.17,<4` → `>=3.16.9,<3.17`; a rationale block beside each recording the LTS policy, the named successor (6.2 LTS, April 2027), the `>=5.2` floor three packages force, and why the stub lines move with the runtime; an `Out of scope: django 5.2` record added to the R-1 verdict block, above nothing and deleting nothing
- `pixi.lock` — regenerated by `pixi lock` / `pixi install -a`, never hand-edited
- `src/django_service/users/forms.py` — a typed stand-in for the nested `Meta` django-stubs does not declare, under `TYPE_CHECKING`, with Django's own `Meta` inherited unchanged at runtime (the review pass replaced the two `# type: ignore[name-defined,misc]` comments this story first shipped)
- `tests/unit/test_dependency_policy.py` — extended, not replaced. Added `test_django_is_declared_as_the_lts_series`, `test_the_type_stubs_track_the_declared_django_series`, `test_the_lock_resolves_the_lts_django_and_its_matching_stubs`, `test_a_disclaimed_verdict_is_accepted_only_while_it_is_still_true`, `test_the_out_of_scope_reader_finds_the_runtime_the_verdict_disclaims` and `test_the_pin_reader_splits_a_range_and_finds_its_series`; `_verdict_drift` became the scope-aware `_verdict_scope_failures`; added `_clauses`, `_series`, `_out_of_scope` and the shared `_named_versions` reader. No assertion names a channel host — the one channel check in the module still matches `"conda-forge"` by containment
- `docs/development.md` — the R-1 verdict's second copy carries the same `Out of scope: django 5.2` record, reconciled against the manifest by the suite; the FR-50 example prose no longer implies the pinned Django is 6.0
- `_bmad-output/planning-artifacts/epics.md` — stack line now reads Django 5.2 LTS with the reason, the cap's shape and the successor; the R-1 bullet records that 1.8's verdict was obtained against 6.0 and does not carry
- `_bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md` — Stack table's Django row rewritten with the LTS rationale and locked version; the `django-storages` row states the 3.2–5.1 classifier set rather than "no Django 6.0"; R-1 gains a dated amendment that changes what the risk is measured against and leaves the escalation ladder untouched

## Review Triage Log

### 2026-08-16 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 12: (high 2, medium 6, low 4)
- defer: 3: (high 0, medium 2, low 1)
- reject: 4: (high 0, medium 1, low 3)
- addressed_findings:
  - `[high]` `[patch]` The R-1 verdict gate could be silenced by writing a comment. Story 1.8's `_verdict_drift` was reshaped into `_verdict_scope_failures`, which accepts an "Out of scope:" disclaimer in place of re-running the spike; all three hunters found it independently. Three weaknesses, each verified by executing the helper: a disclaimer of `django 5` was accepted against a lock at `5.2.15` *and* at `5.9.0` (coarse disclaimers exempted a whole major line); any package could be disclaimed, including `django-storages` and `boto3` — the subjects the verdict is *about*; and only the first `Out of scope:` listing was parsed, so a second was invisible. Fixed by adding `_precision` (a disclaimer must name at least as many components as the verdict names for that package), `DISCLAIMABLE_PACKAGES = {django, python}` (only the runtime the verdict was earned *on* may be disclaimed — excusing the subject leaves a verdict about nothing), and merging every occurrence of the label. Bounding a listing needed `LISTING_END` (dash break *or* sentence end) because `pixi.toml`'s out-of-scope prose quotes the string `"Tested against:"` and a naive merge parsed the following prose as a version. Three tests added.
  - `[high]` `[patch]` A disclaimed verdict was not coupled to the staging rule, so a future story could act on a verdict the manifest itself says no longer applies. `RECORDED_VERDICT` still reads `proven with a stated bound`, Story 7.5's spec instructs it to act on the recorded verdict, and `test_the_storage_spike_is_staged_rather_than_committed_to` held only incidentally — its own docstring authorised 7.5 to rewrite it. Fixed by asserting that while `_out_of_scope(...)` is non-empty, `django-storages` stays declared in `[feature.spike-storage.dependencies]` and nowhere else. `VERDICTS` and `RECORDED_VERDICT` were left alone: they are Story 1.8's record.
  - `[medium]` `[patch]` The lock resolved `django-stubs-ext 6.0.8` beside `django-stubs 5.2.9`, and the new alignment test was scoped to the two packages that already passed rather than to the invariant it advertises. Pinned `django-stubs-ext = ">=5.2.9,<5.3"`; the solve succeeded (`6.0.8` → `5.2.9` in `dev` and `spike-storage`) and `typecheck` stayed clean, so no revert was needed. `STUB_PACKAGES` now drives both the manifest and lock assertions.
  - `[medium]` `[patch]` The two `# type: ignore[name-defined,misc]` comments made both admin `Meta` bases `Any`, so `model`, `fields` and `error_messages` went unchecked in the classes whose job is to constrain the admin forms — a hard error traded for silent non-coverage. django-stubs stubs no form's nested `Meta` at all, so `forms.py` now declares a typed `_AdminFormMeta` under `TYPE_CHECKING` (the idiom already in the file) and inherits Django's real `Meta` at runtime. Both ignores are gone; injecting `error_messages = "nope"` now produces the `[assignment]` error the `Any` base swallowed.
  - `[medium]` `[patch]` The "editing this constant is the whole move" promise was false: `DJANGO_LTS_CLAUSES` hardcoded `<5.3`, so setting `DJANGO_LTS_SERIES = "6.2"` would demand the contradictory range `>=6.2,<5.3`, and a failure message built the cap as `DJANGO_LTS_SERIES[0] + ".3"` — `"1.3"` for a future `"10.2"`. The cap is now derived from the constant everywhere.
  - `[medium]` `[patch]` The permanent floor-evidence block in `pixi.toml` cited `django-debug-toolbar 7.1.1`, a build this tree does not have — the manifest declares `>=7.0,<8` and the lock resolves `7.0.0`. The block exists so a future downgrade is refused on evidence, so every version and constraint in it was re-read from the lock and corrected; `django-redis` is now described as the floor *and* cap it is.
  - `[medium]` `[patch]` The R-1 risk headline in `epics.md` was made less specific by a story whose thesis is that version identity matters — "unproven against **Django 6.0**" had become "against **the pinned Django**". The version is named in the headline again.
  - `[medium]` `[patch]` The docs copy of the verdict was only half-reconciled: it wrote its versions as unlabelled prose, so `_tested_against(section)` returned `{}` and the reconciliation covered the verdict string and the disclaimer but not the versions — the docs' `Django 6.0` could survive a re-run spike with the gate green, misleading exactly the reader that copy exists for. Labelled and reconciled.
  - `[low]` `[patch]` Parser and lookup robustness: `_series` did not strip `~`, whitespace or a trailing `.*`, so legal pins (`~=5.2`, `>= 5.2, <5.3`, `5.2.*`) parsed to nonsense and failed with a misleading message; `manifest["feature"]["dev"]["dependencies"]` was indexed unguarded, raising a bare `KeyError` instead of the test's own diagnostic; and the environment loop had no `if runtime is None: continue`, so a future environment carrying no Django would redden the gate — Epic 8 adds six.
  - `[low]` `[patch]` A docstring asserted a false fact about a sibling file: `_named_versions` claimed `docs/development.md` "writes an em dash because it is prose" when it wrote `--`, leaving the em-dash branch of `DASH_BREAK` unexercised. Made true rather than dropped — the docs listing now ends with a real em dash, exercised by the live reconciliation and an explicit case.
  - `[low]` `[patch]` `docs/development.md` prose defects introduced by the reflow: the FR-50 passage read "neither the pinned Django — … and it declares neither — nor Python 3.14", duplicating its own `neither…nor`; a two-word stub line sat in a file hard-wrapped near 76 columns; and the disclaimer pointed "below" at a record that in this file sits above. All three fixed.
  - `[low]` `[patch]` `ARCHITECTURE-SPINE.md`: the Stack table dateline still claimed verification on 2026-08-15 over rows amended 2026-08-16 (same string in `epics.md`); the Django Note cell had grown to ~900 characters in a table of one-clause cells, a fourth copy of a rationale that already lives in `pixi.toml`; and the row asserted "AD-3's shared solve-group still stands" without re-deriving it, when the `django-celery-beat <6.1` cap that motivated AD-3 no longer binds at `>=5.2,<5.3`. Datelines corrected, cell condensed to point at `pixi.toml`, and the assertion replaced with a plain statement that the cap-driven motivation no longer binds and that this story does not revisit AD-3. The R-1 escalation ladder was not touched.

## Auto Run Result

Status: done

### Implemented change

Django moves from the `6.0` feature release to the `5.2` LTS series, and the
type stubs move with it. `pixi.toml` declares `django = ">=5.2,<5.3"` — the cap
is the next *minor*, because `<6` would re-admit 5.3 and every feature release
after it, which is the thing the story exists to prevent — and `pixi.lock`
resolves `5.2.15`. Python stays at `3.14.*`; Django 5.2.15 carries the 3.14
classifier, so the LTS move forces no downgrade.

The stub move was the story's central risk and it materialised. `django-stubs`
at `>=5.2,<5.3` made `djangorestframework-stubs >=3.17,<4` unsatisfiable —
3.17.0/3.17.1 require `django-stubs >=6.0.4`, 3.18.0 requires `>=6.0.9` — so the
DRF stub pin dropped to `>=3.16.9,<3.17`, determined from the solve rather than
assumed, with the full conflict output recorded. Strict `typecheck` then failed
on two admin forms whose nested `Meta` the 5.2 stub line does not declare: a stub
gap, not a behaviour gap. **No application code depends on Django 6.0 behaviour**
— only on the 6.0 stubs being more complete.

Why the pin is now defensible rather than inherited: `6.0` came from the
cookiecutter-django origin and was never chosen against alternatives. Beside the
pin now sit the support window (April 2028), the named successor (6.2 LTS, April
2027) so the exit is a decision rather than a rediscovery, and the evidence that
`>=5.2` is the floor — three packages require it, so there is no headroom below.

What the story does **not** fix is stated as plainly as what it does.
`django-storages 1.14.6` declares `Framework :: Django` classifiers of
3.2/4.1/4.2/5.0/5.1 — neither 5.2 nor 6.0 — so R-1 narrows from two majors to one
minor and closes nothing. Story 1.8's verdict was earned against Django 6.0; it
was not re-run and not rewritten. Its gate check correctly failed on this change,
and the honest repair was to let the block record what it no longer covers. The
review pass then had to harden that escape hatch — see Residual risks.

### Files changed

- `pixi.toml` — UPDATE. The three pins above, each with its rationale block;
  `django-stubs-ext = ">=5.2.9,<5.3"` added so the stub *runtime* tracks the
  series too; an `Out of scope: django 5.2` record appended to the R-1 verdict
  block, deleting nothing above it. `[pypi-dependencies]` still holds exactly one
  entry and no channel or runtime specifier changed.
- `pixi.lock` — UPDATE (generated). Re-solved, never hand-edited. `django 5.2.15`,
  `django-stubs 5.2.9`, `django-stubs-ext 5.2.9`, `djangorestframework-stubs 3.16.9`.
- `src/django_service/users/forms.py` — UPDATE. A typed `_AdminFormMeta` under
  `TYPE_CHECKING` for the nested `Meta` django-stubs does not declare, with
  Django's own `Meta` inherited unchanged at runtime.
- `tests/unit/test_dependency_policy.py` — UPDATE. The LTS-series, stub-alignment
  and lock assertions AC #5 requires, plus the review pass's hardening of the
  verdict-scope rule. No assertion names a channel host; the one channel check
  still matches `"conda-forge"` by containment, per Story 1.7.
- `docs/development.md` — UPDATE. The verdict's second copy carries the same
  out-of-scope record and now a labelled `Tested against:` listing, so both
  halves are reconciled against the manifest; FR-50 prose corrected.
- `_bmad-output/planning-artifacts/epics.md` — UPDATE. Stack line and R-1 bullet.
- `.../ARCHITECTURE-SPINE.md` — UPDATE. Stack table's Django and `django-storages`
  rows, and a dated R-1 amendment that leaves the escalation ladder intact.
- `_bmad-output/implementation-artifacts/deferred-work.md` — UPDATE. Three entries.

### Review findings

Three hunters (adversarial, edge-case, verification-gap) ran in parallel against
the diff. **12 patches applied, 3 deferred, 4 rejected, 0 intent gaps, 0 spec
defects** — no loopback. All three hunters independently found the same
highest-consequence defect, and it is the one worth reading the triage log for:
the change had reshaped Story 1.8's R-1 gate so that writing a comment
substituted for re-running the spike. The disclaimer could be coarser than the
claim it narrowed (`django 5` was accepted against a lock at `5.9.0`), could name
the subject of the verdict itself, and only its first occurrence was parsed. The
first story to hit that guard had rewritten the guard to accommodate itself. It
is now precision-bounded, restricted to the runtime the verdict was earned *on*,
and coupled to the staging rule, so a disclaimed verdict cannot be built on.

The four rejected findings: that AC #3's PostgreSQL run leaves no re-executable
artifact (Story 1.2 owns that mechanism and CI carries it); that the named 6.2
successor may collide with a `django-celery-beat <6.1` cap (an assertion about an
unreleased future); that `tests/spikes/spike_django_storages_fitness.py:74` still
asserts Django 6.0 (deliberate — a re-run must fail loudly rather than inherit);
and that the FR-50 prose is generally unreconciled (the specific defect was
patched; a general reconciliation is a larger design).

### Verification

| Command | Result |
|---|---|
| `pixi lock` | first attempt **failed** on the DRF-stubs conflict; solved after the pin moved |
| `pixi install -a` | `default`, `dev`, `spike-storage` installed |
| `pixi run typecheck` | Success: no issues found in 37 source files |
| `pixi run lint` | All checks passed |
| `pixi run test` | 234 passed (unit only) |
| `pixi run test-integration` | 66 passed, 6 skipped |
| `DATABASE_URL=postgres://…@localhost:55432/gatedb pixi run ci` | **exit 0** |
| `pixi run ci` (final, after the review pass) | **exit 0** — 306 passed, coverage 92.48% |

AC #3's PostgreSQL leg reproduced Story 1.2's CI shape: a real `postgres:17`
container (server reported 17.11), health-gated on `pg_isready`, reached through
`DATABASE_URL`, which `config/settings/base.py:57` hands to `env.db()`. Confirmed
it was actually used — `test_gatedb` was present in the server's database list
afterwards. Container removed; nothing left running.

The hardened verdict rule was exercised directly rather than trusted: a coarse
`django 5` disclaimer and a `django-storages` disclaimer both now return
failures, while the exact `django 5.2` returns none.

### Residual risks

1. **The disclaimer is still an escape hatch, only a narrower one.** R-1 is now
   open against the shipped runtime with the gate green. That is honest — the
   alternative was a red gate or a re-run spike this story deliberately does not
   perform — but it means the spike's re-run depends on someone choosing to do
   it. What stops it becoming permanent: the disclaimer must name the exact
   release line, so it goes stale on the next bump, and `django-storages` cannot
   leave staging while it stands.
2. **`djangorestframework-stubs 3.16.9` type-checks `djangorestframework 3.18.0`.**
   The misalignment this story closes for Django is reopened one package over,
   forced by the solve with no available fix. Deferred, with the exit condition
   recorded.
3. **Five planning documents still name Django 6.0 forward-looking**, one of them
   instructing a future agent not to verify versions. Outside AC #4's scope;
   deferred, with the 7.5 hazard called out by name.
4. **No deprecation gate.** Moving 6.0 → 5.2 means code can now use APIs 6.0
   already removed, and nothing objects. Deferred.
