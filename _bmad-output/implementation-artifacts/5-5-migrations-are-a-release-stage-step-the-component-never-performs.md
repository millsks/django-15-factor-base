---
status: done
baseline_revision: b608936
review_loop_iteration: 0
warnings: []
followup_review_recommended: true
final_revision: 8038775
---

# Story 5.5: Migrations are a release-stage step the component never performs

Status: done

## Story

As a platform engineer,
I want no entrypoint to migrate and the component to refuse an unrecognized schema,
so that migration cannot race across replicas and a serving process never runs against a schema it does not know.

## Acceptance Criteria

**Traceability:** FR-41 · AD-22 · SC-3 · risk R-3

1. **Given** every entrypoint, task and container command
   **When** they are inspected
   **Then** none runs migrations
   **And** a test asserts this over the materialized process tasks

2. **Given** unapplied migrations
   **When** a serving process starts
   **Then** the stage-2 refusal from Story 4.3 raises `ImproperlyConfigured`

3. **Given** the deployment pipeline
   **When** the contract is documented
   **Then** the documentation states that migration runs before new pods begin serving
   **And** that it runs once per database as `component.toml` declares

4. **Given** a serving process started outside `pixi run web`
   **When** the migrations refusal is considered
   **Then** it does not fire
   **And** this is the accepted price of a fail-open process type

## Tasks / Subtasks

- [x] Task 1 — Assert no entrypoint or task migrates (AC: #1)
  - [x] `tests/unit/test_release_stage.py` — parse `pixi.toml` with `tomllib`, merging `[tasks]` and every `[feature.<name>.tasks]` table.
  - [x] Derive the process group structurally, exactly as Story 5.2 does: the tasks whose `env` contains `COMPONENT_PROCESS`. Import that helper from `tests/unit/test_process_model.py` or factor it into a shared test helper — do not write a second, divergent parser.
  - [x] For every process task assert: the command contains no `migrate`, `migrate --check`, `makemigrations` or `manage.py migrate` invocation, and its `depends-on` list (transitively resolved) reaches no task that does. The transitive check matters — `depends-on = ["migrate"]` is the shape this test exists to catch.
  - [x] Assert the same over `src/config/asgi.py` and `src/config/wsgi.py`: neither imports `django.core.management` nor calls `call_command`.
  - [x] Assert the same over the `Dockerfile` once Story 5.6 lands it: no `RUN`, `ENTRYPOINT` or `CMD` line contains a migrate invocation. Write the assertion to be skipped with an explicit reason when the file is absent, and record in Story 5.6's task list that the file must satisfy it. Do not weaken the assertion to a substring search over the whole file — check the instruction lines.
  - [x] Assert `migrate` (`pixi.toml:174`) and `collectstatic` (`:175`) themselves set **no** `COMPONENT_PROCESS`: they are release-stage and build-stage steps, not serving processes, and a `COMPONENT_PROCESS` on them would make the migrations refusal fire against the very command that clears it — the deadlock AD-13 names.

- [x] Task 2 — Wire the release-stage steps to `component.toml` (AC: #1, #3)
  - [x] Confirm every `[[databases]]` entry in `component.toml` carries a non-empty `migrate` step list (Story 5.1) and that the `default` entry's step targets the `default` alias explicitly (`migrate --database default --noinput`).
  - [x] Add a test asserting each declared step is a Django management invocation and names a `--database` alias that exists in the same declaration — so a contributed database (AD-9, Epic 9) cannot be added without its step.
  - [x] Do not add a task that runs all the steps in sequence. The deployment repository runs them; a component-side "migrate-all" task is one `depends-on` away from becoming an entrypoint.

- [x] Task 3 — Assert the stage-2 refusal fires for a serving process (AC: #2)
  - [x] The refusal itself is Epic 4's Story 4.3 (condition 7 of the nine-condition table: "Unapplied migrations exist on a serving process", stage 2). Epic 4 precedes Epic 5 in the dependency flow, so this is a **dependency, not a forward reference**: reuse it, do not reimplement it, and do not add a second migration check anywhere.
  - [x] `tests/integration/test_release_stage.py` (`@pytest.mark.integration`): with `COMPONENT_PROCESS` set and `COMPONENT_RUNTIME` unset, and with an unapplied migration present, the stage-2 hook raises `ImproperlyConfigured`. If Story 4.3's module exposes a callable, invoke it directly; if it runs from `AppConfig.ready()`, trigger it the way Epic 4's own tests do.
  - [x] Assert the converse in the same module: with `COMPONENT_PROCESS` **absent**, the same unapplied-migration state raises nothing (AC #4). This is R-3 as a test rather than a paragraph.
  - [x] Do **not** move, duplicate, or relax the refusal. AD-26: the refusal contract is one module, `src/config/startup/`, with one owner.

- [x] Task 4 — Document the release-stage contract (AC: #3, #4)
  - [x] `docs/deployment.md` `## Migrations are a release-stage step`: migration runs **before** new pods begin serving; it runs once per database, exactly as `component.toml`'s `[[databases]] migrate` lists declare; no entrypoint, task or container command migrates, and none will be added.
  - [x] State the ordering the deployment repository must implement: apply migrations → start new replicas → old replicas drain. Cross-reference AD-22's readiness rule — readiness never re-checks migrations, so an older replica running against a newer schema stays ready, which is what makes backwards-compatible migrations viable.
  - [x] State risk **R-3** honestly under its own subheading: a serving process started outside `pixi run web` does not fire the migrations refusal, because process type fails open; failing it closed would deadlock the release stage. This is the accepted price, recorded, not mitigated.
  - [x] Ensure `docs/deployment.md` is in `mkdocs.yml` `nav`; `pixi run docs` is `mkdocs build --strict`.

- [x] Task 5 — Tests and gate (AC: #1, #2, #4)
  - [x] `tests/unit/test_release_stage.py` as above — static assertions over `pixi.toml`, `component.toml`, `src/config/asgi.py`, `src/config/wsgi.py`, and the `Dockerfile` when present.
  - [x] `tests/integration/test_release_stage.py` as above — the refusal fires for a serving process and does not fire without one.
  - [x] Run `pixi run test`, then `pixi run ci`; the story is done when `pixi run ci` exits 0.

## Dev Notes

### Architecture Constraints

- **AD-22** — *Rule:* "**No entrypoint, task or container command runs migrations**; migration is a release-stage step the deployment repository performs before new pods serve, one per database as `component.toml` declares, and the stage-2 refusal enforces that a serving process never starts against an unrecognized schema." *Prevents:* "an entrypoint that migrates and races across replicas."
- **AD-13** — "Process type fails open: absent means not a serving process, because failing it closed would produce exactly that deadlock" — the release stage runs `pixi run migrate`, which is not a serving process and must not be treated as one. **Do not sniff `sys.argv`** to detect a serving process.
- **AD-9** — "Release-stage migration becomes one step per database, and `component.toml` declares them so the deployment repository does not have to guess. The stage-2 unapplied-migrations refusal and the sqlite refusal both iterate every configured database — which is only possible because stage 1 runs *after* composition (AD-26)."
- **AD-26** — "The refusal contract is one module, `src/config/startup/`, containing both stages and the FR-17 allowlist. **Stage 2** is owned by the `AppConfig.ready()` of one named immovable-core app in `django_service`, declared in `accelerator.toml`; no adopted app may precede it in `INSTALLED_APPS`, and a gate test asserts that ordering." This story asserts the refusal's behaviour; it does not own, move or extend it.
- **AD-28** — Per-database release-stage migration steps are `component.toml` content. A step list belongs there and nowhere else.
- **R-3** — "A serving process started outside `pixi run web` does not fire the migrations refusal. The price of AD-13's fail-open process type, taken because failing it closed deadlocks the release stage." Accepted, not mitigated. Do not attempt a mitigation in this story.
- **The nine-condition refusal table** (epics.md#Resolved during story creation): condition 7 is "Unapplied migrations exist on a serving process", stage 2, one forbidden state, tested separately under FR-16. That test lives in Epic 4. This story's integration test asserts the *contract from the deployment side* and must not be counted as, or written to replace, FR-16's condition test.
- **Project standards** — Pixi is the only runner: `pixi run migrate` is how the release stage invokes it; never bare `python manage.py`. Python 3.14 only. Full type hints, Google docstrings, line length 120. Never `print()`; `structlog` only. Never a bare `except:`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tests/unit/test_release_stage.py` | **NEW** | No process task, entrypoint or Dockerfile instruction migrates; `migrate`/`collectstatic` declare no `COMPONENT_PROCESS`; every declared database has a migration step. |
| `tests/integration/test_release_stage.py` | **NEW** | The stage-2 refusal fires with `COMPONENT_PROCESS` set and does not fire without it. |
| `docs/deployment.md` | UPDATE (NEW if earlier Epic 5 stories have not landed) | Adds `## Migrations are a release-stage step` including the R-3 subsection. |
| `mkdocs.yml` | UPDATE | Register `deployment.md` in `nav`. |
| `component.toml` | read/verify | Created by Story 5.1; confirm the `[[databases]] migrate` lists. No new keys. |
| `pixi.toml` | read/verify | `migrate` at `:174` is `python manage.py migrate` in the `default` environment with no `env` table — correct as-is. `collectstatic` at `:175` likewise. **Do not** add `COMPONENT_PROCESS` to either. |
| `src/config/asgi.py`, `src/config/wsgi.py` | read/verify | Neither imports `django.core.management` today. The assertion pins that. |
| `Dockerfile` | read/verify (created by Story 5.6) | Assertion skipped with an explicit reason while absent. |
| `src/config/startup/` | read only | Epic 4's refusal module. **Do not modify.** |

**Verified absent today:** `component.toml`, `Dockerfile`, `src/config/startup/`. `src/config/settings/production.py:26-28` holds the only refusal that exists today (sqlite in production); it is Epic 4's to generalise, not this story's.

### Testing Requirements

- Unit: `tests/unit/test_release_stage.py` — `tomllib` and text parsing of files on disk; no database, no network, milliseconds. Share the process-group helper with `tests/unit/test_process_model.py` (Story 5.2) rather than duplicating it: two parsers that can disagree is precisely the failure mode AD-26 names for the refusal contract, and the same reasoning applies to its tests.
- Integration: `tests/integration/test_release_stage.py` — `@pytest.mark.integration`; `tests/integration/conftest.py:12-19` also auto-marks the directory. The test manipulates `COMPONENT_PROCESS` and migration state, both process-global — use `monkeypatch` and restore migration state in a fixture so the suite leaves the database as it found it.
- Disposition (spine Consistency Conventions): both modules cover `core` paths and are `core`; they run inside every combination's gate and are never pruned. Derive expectations from `component.toml` so they hold in a combination where the `celery` region removed `worker` and `beat`.
- AD-20 floor: 90% including templates, `COVERAGE_CORE=ctrace` in force. These are assertion suites over configuration rather than new production code, so they add little coverage denominator — but do not use that as a reason to skip the `docs` update, which `pixi run docs` gates separately.
- AC #1's "over the materialized process tasks": here the assertions run against the reference application's `pixi.toml`. Epic 8 runs the same suite inside each materialized combination. Write the test so it reads whatever `pixi.toml` is at the repository root, with no path assumption beyond that.

#### Project Structure Notes

- Nothing new is added to `src/`. This story is a contract and its enforcement, not a feature: the behaviour it names is the *absence* of a behaviour, and the artefact is the test that keeps it absent.
- **Dependencies:** Story 5.1 (`component.toml` and the `[[databases]] migrate` lists), Story 5.2 (the process tasks and the process-group helper), and Epic 4 Story 4.3 (the stage-2 refusal). Epic 4 precedes Epic 5 in epics.md's dependency flow, so all three are available.
- **Consumed by Story 5.6:** the Dockerfile assertion. 5.6's Dockerfile must satisfy it on the day it lands; the skip-when-absent branch is a sequencing accommodation, not a permanent exemption.
- **Cross-epic thread** (epics.md): "FR-41's unapplied-migrations refusal is *implemented* as a stage-2 condition in Epic 4; **Epic 5 owns the release-stage contract and the no-entrypoint-migrates property.**" Keep the split exactly there.
- SC-3 is an external exit criterion: nothing in this repository starts a component on the target platform, and the deployment configuration that runs these steps lives in a separate repository and is an explicit non-goal. This story delivers the component-side declaration and its enforcement; it does not close SC-3.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-22]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-13]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-9]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-26]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-28]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Named Residual Risks] — R-3.
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.5]
- [Source: _bmad-output/planning-artifacts/epics.md#Resolved during story creation: the refusal count] — condition 7.
- [Source: _bmad-output/planning-artifacts/epics.md#Cross-epic threads]
- [Source: _bmad-output/planning-artifacts/epics.md#External exit criteria] — SC-3.
- [Source: _bmad-output/planning-artifacts/prds/prd-django-15-factor-base-2026-08-14/prd.md#FR-41]
- Repository state: `pixi.toml:172-182`; `src/config/asgi.py`; `src/config/wsgi.py`; `src/config/settings/production.py:26-28`; `tests/integration/conftest.py:12-19`.

## Dev Agent Record

### Agent Model Used

`claude-opus-5[1m]` (Claude Opus 5, 1M context), via Claude Code.

### Debug Log References

Inner loop, in order, all from the repository root:

- `pixi run -e dev python -m pytest tests/unit/test_process_model.py -q` — 11 passed, after the manifest reader moved to `tests/pixi_manifest.py`. Run first and on its own, because that move touches Story 5.2's gate and nothing else in this story is worth debugging while it is broken.
- `pixi run -e dev python -m pytest tests/unit/test_release_stage.py tests/unit/test_suite_policy.py -q` — 104 passed, 1 skipped (the Dockerfile case).
- `pixi run -e dev python -m pytest tests/integration/startup/test_stage_two_database_conditions.py -q` — 7 passed, confirming Epic 4's FR-16 cases are unchanged in behaviour after `never_migrated_database_alias` moved to `tests/conftest.py`.
- `pixi run -e dev python -m pytest tests/integration/test_release_stage.py -q` — 6 passed.
- `pixi run fmt` — no files rewritten. `pixi run lint` — all checks passed.
- `pixi run test` — 1150 passed, 1 skipped. `pixi run test-integration` — 290 passed, 6 skipped.
- `pixi run docs` — built, `--strict`, no warnings from this page. `deployment.md` was already registered in `mkdocs.yml` `nav`; no edit was needed there.
- `pixi run ci` — exit 0.

No failure loop was entered: nothing in this story failed the gate on a first run.

### Completion Notes List

**The shared process-group helper (Task 1, and the one refactor this story took on).** `tests/unit/test_process_model.py` held the pixi-manifest walk and, inside it, the structural definition of the process group. Story 5.5 needs exactly that group to assert that no member of it migrates, and the spec forbids a second parser. The walk moved to a new **`tests/pixi_manifest.py`** — a helper module, not a collected one (`python_files` matches `test_*.py` and `tests.py`, so nothing there is collected), placed at `tests/` for the reason `tests/conftest.py` already records: a collected test module is not a helper library, and importing one from another ties two files' collection together. `test_process_model.py` now imports from it and its assertions are unchanged; the AD-24 region helpers stayed behind, because a region is a span of lines and only that file reads text.

`task_dependencies()` is new in the shared module: pixi permits `depends-on` entries as a bare string *or* as a table carrying `task` alongside `args`, and a walk that read only the first form would be blind to a dependency written in the second.

**What was deliberately not folded in.** `tests/unit/test_locality_declaration.py` carries its own `_task_tables`/`_task_env`. It asserts the *other* half of AD-13's task-`env` contract and its walk also covers `[activation.env]` tables that have nothing to do with tasks, so folding it in is a refactor of Story 4.4's work rather than of this story's. That decision is recorded in `tests/pixi_manifest.py`'s docstring rather than left implicit.

**The transitive `depends-on` check is the point of Task 1.** `web` running gunicorn is obviously not a migration and nobody would write one into that command. `depends-on = ["migrate"]` on the same task is one line, it reads as a convenience, it makes a developer's `pixi run web` work against a fresh database, and it produces N replicas migrating concurrently on every rolling deploy. So `_reachable()` walks the whole dependency closure from each process task, yields the task's own command first, and terminates on cycles.

**Migration detection is a word match, not a substring search.** `MIGRATION_INVOCATION` excludes `[\w.-]` on both sides, so `--no-migrate` and a dotted module path are not matches, and the module's own prose is not an offence. Two guards keep it honest: `test_the_detector_recognizes_the_manifests_own_migration_tasks` asserts the detector still matches `migrate` and `makemigrations` as the manifest declares them (a tightened look-around would otherwise make every case pass by finding nothing) and asserts it does *not* match the real `web` command.

**Task 2's second half found nothing to fix but is not vacuous.** `tests/unit/test_component_declaration.py:305` already asserts each `[[databases]]` entry carries a non-empty `migrate` list, so that was verified rather than re-asserted. The new case reads the step's *content*: the command is checked against `django.core.management.get_commands()` — the registry `manage.py` itself dispatches through, so a typo or a command from an unselected app fails in the gate — and `--database` must name the alias of the entry declaring it. Without the alias clause, a contributed database (AD-9, Epic 9) could be added with a step that silently re-migrates `default`.

**No `migrate-all` task, asserted rather than left to review.** `test_the_only_tasks_that_migrate_are_the_two_the_manifest_is_supposed_to_have` pins the set to exactly `migrate` and `makemigrations`, in both directions. Nothing was added (an aggregate is one `depends-on` away from being an entrypoint) and nothing was removed (the release stage invokes `pixi run migrate`, so deleting it would make every scan here pass by having nothing left to find).

**The Dockerfile skip needed a recorded exemption, and that is a real repository rule.** `tests/unit/test_suite_policy.py` bans `pytest.skip`, `skipif` and `xfail` outright — Story 1.2's ban — with a per-occurrence exemption table. The spec requires the Dockerfile assertion to skip with an explicit reason while the file is absent, so `"unit/test_release_stage.py": {"pytest.skip(...)": 1}` was added to `RECORDED_EXEMPTIONS` with the reasoning beside it. This is a sequencing accommodation, not a dodged gate failure: there is no state being permitted, only a file Story 5.6 has not written. The exemption is spent per occurrence, so a second skip in that module fails the gate. Story 5.6's task list now carries the obligation, names the exact test, tells the author to confirm it reports **passed** rather than **skipped** after the first `Dockerfile` commit, and warns that removing the exemption entry while leaving the branch fails `test_every_recorded_exemption_still_describes_the_file` from the other side.

**The Dockerfile assertion joins continuations before it looks.** `_instruction_lines()` folds `\`-continued lines into one instruction, so `RUN pixi run collectstatic \` / `&& pixi run migrate` is one `RUN` whose arguments contain a migrate — where a per-line reader would see a second line beginning `&&` and classify it as no instruction at all. Only `RUN`, `ENTRYPOINT` and `CMD` are checked; the rest describe the image.

**`never_migrated_database_alias` moved to `tests/conftest.py` (a second shared-home move, and why it was worth it).** Epic 4's `_second_configured_database` carried a documented *silent* failure mode: `override_settings(DATABASES=...)` alone leaves `django.db.connections` bound to the old mapping, so the extra alias exists in settings and raises `ConnectionDoesNotExist` on access — a state in which the subject cannot be exercised and which presents as a passing test rather than as an error. Copying that dance into this story's integration module is precisely the kind of duplication a second copy eventually gets wrong. It is now one parameterized context manager in `tests/conftest.py`, it refuses `default` outright, and Epic 4's four call sites were rewired to it with no behavioural change (7 passed, unchanged). The refusal module itself was **not** touched.

**The integration module asserts the deployment side and is not a replacement for FR-16's condition test.** Epic 4's `tests/integration/startup/test_stage_two_database_conditions.py` owns condition 7 and keeps its `@pytest.mark.forbidden_state("unapplied-migrations")` claim; nothing here carries that marker, so the FR-16 coverage audit is unaffected. What this module adds is the deployment repository's question, parameterized over **every process type `component.toml` declares** rather than over `web` alone — a `worker` consuming against an unrecognized schema is the same defect arriving through a queue — plus an assertion that the refusal message actually tells the operator migration is a *release-stage* step, because an operator given only "the alias is wrong" adds a migrate to an entrypoint.

Deriving the parameter list from `[[processes]]` is also what makes the module hold in a combination where the `celery` region removed `worker` and `beat`: it collects `web` alone there and asserts the same contract.

**R-3 is one test case, not two, and that is deliberate.** The mechanism that exempts `pixi run migrate` cannot distinguish it from a gunicorn started by hand outside the declared tasks — it is the same absent `COMPONENT_PROCESS` in both. So the case that proves the release stage is not deadlocked *is* the case that demonstrates R-3, and the docstring says so rather than implying a mitigation exists. `test_the_refusal_is_the_only_thing_standing_between_the_two_cases` runs both halves over one configuration of the unmigrated state, so the difference is attributable to the variable rather than to two set-ups that might have differed.

**Nothing was added to `src/`.** This story is a contract and its enforcement; the behaviour it names is the absence of a behaviour. The coverage denominator is unchanged and the AD-20 floor is unaffected.

**`mkdocs.yml` needed no change** — `Deployment: deployment.md` was already in `nav` from Story 5.1. Task 4's last subtask was verified rather than performed, and `pixi run docs` (`mkdocs build --strict`) confirms it.

**SC-3 remains open, as the story says it must.** Nothing here starts a component on the target platform; the deployment configuration that runs these steps lives in a separate repository and is an explicit non-goal. This delivers the component-side declaration and its enforcement only.

**Nothing in the spec went unsatisfied.**

#### Review pass — 17 patches applied

An adversarial review of the implementation returned seventeen verified findings.
All seventeen were applied. They fall into four groups.

**The walk was never exercised (the highest-value one).** No task in this
repository's process group declares `depends-on` at all, so the transitive walk —
the mechanism this module exists for — ran over a closure of exactly one task per
process, and stubbing `task_dependencies()` to return `()` left the whole module
green. The module already guards against vacuous green for the *detector* twice
and had no such guard for the *walk*.
`test_the_transitive_walk_finds_a_migration_reached_through_a_dependency` is that
guard: four synthetic in-memory manifests — `migrate` reached directly, reached
at depth two, reached at depth two through a `{task, args}` entry whose named
task does not migrate and whose `args` do, and a chain of the same depth that
reaches nothing. Both mutations were run to confirm the control bites: returning
`()` fails three of the four cases, and discarding `args` alone fails the third.

**The readers had four holes, each a way a real migration escapes a real scan.**
`task_command()` returned `""` for pixi's list form, so `cmd = ["python",
"manage.py", "migrate"]` on a serving task passed every migration scan silently;
it now joins the list. `task_dependencies()` read a table entry's `task` and
discarded its `args`, so `depends-on = [{ task = "manage", args = ["migrate"] }]`
on `web` passed the transitive assertion — `manage`'s own command is `python
manage.py` and contains no migrate — so it now returns (name, args) pairs and
`_reachable()` appends the args to the command it scans, keying its cycle guard
on the pair. `feature_scopes()` seeded the root scope under `default` and then
iterated `manifest["feature"]`, so a literal `[feature.default]` table would have
replaced it and dropped every unscoped task from every walk in the suite; that
now raises rather than resolving. And `ENTRYPOINT_MODULES` covered `asgi.py` and
`wsgi.py` only, missing the other two modules a process loads at boot —
`workers.py` (gunicorn's `-k config.workers.DrainingUvicornWorker`) and
`celery_app.py` (`worker` and `beat`'s `-A config.celery_app`). Both are now
scanned. `celery_app.py` is `feature:celery`, so its presence is required *from
the declaration* rather than unconditionally, the same derivation
`tests/unit/test_process_model.py` uses for `worker` and `beat`.

**The Dockerfile parser had four defects and zero execution.** An instruction
whose last line ended in an unterminated `\` was dropped entirely (`pending` was
never flushed after the loop). The comment skip was gated on `not pending`, so a
`#` line *inside* a continuation was folded into the arguments — meaning a
Dockerfile comment reading "migrate is a release-stage step" would have been
reported as a migrating instruction, the exact false positive this file elsewhere
AST-parses Python to avoid. BuildKit heredocs (`RUN <<EOF` … `EOF`) parsed each
body line as its own instruction, so `pixi run migrate` inside one was classified
under a head of `PIXI` and never scanned. And `ONBUILD RUN pixi run migrate` and
`HEALTHCHECK CMD pixi run migrate --check` both execute and both escaped — the
`ONBUILD` prefix is now stripped and the wrapped instruction classified as what
it is, and `HEALTHCHECK` joined `EXECUTING_INSTRUCTIONS`. Since `Dockerfile` does
not exist yet, none of that was verified by anything:
`test_the_dockerfile_parser_reads_each_form_an_instruction_can_take` is seven
cases over synthetic Dockerfile text that run **now**, asserting both the parse
and the classification.

**The declared steps were under-specified, and one crash path was unhandled.**
`migrate = ["shell --database default"]` satisfied both of the original checks —
a real management command, and `--database` naming the entry's own alias — so the
release-stage contract's central declaration could be filled with a
non-migration. A step must now *be* a migration command (through this module's
own detector, so there is one definition of "migrates" rather than two that can
drift) and must carry `--noinput` (either spelling): a release stage has no TTY,
and a step that prompts hangs the rollout before a single new pod starts.
`shlex.split()` raising `ValueError` on an unbalanced quote surfaced as a
traceback rather than as the offender list the case spends a paragraph designing;
it is caught and reported as an offender. And `_targeted_alias()` returned the
*first* `--database`, while Django honours the last — a step naming two aliases
passed here and migrated the other one — so `_targeted_aliases()` returns all of
them and the step must name exactly one.

**Three things outside this module that the review found and this pass fixed.**
`tests/unit/test_suite_policy.py`'s scan globbed `test_*.py`, `spike_*.py` and
`conftest.py`, which this story's own new helper `tests/pixi_manifest.py` matches
none of — the ban had acquired precisely the door its docstring argues at length
it must not have, one that opens by naming a file something else. The scan now
reads every `.py` under `tests/`. That brought `tests/coverage_policy.py`'s
`pytest.skip` into view, which is a legitimate guard (coverage never requested)
and is now *recorded* in `RECORDED_EXEMPTIONS` with its reasoning instead of
sitting beyond the scan; that module's docstring no longer cites the glob as the
reason for its placement. `tests/conftest.py`'s `never_migrated_database_alias`
mutated `connections.settings` and materialized the connection *before* its
`try`, so a raise from `connections[alias]` leaked the replaced handler into
every later test in the session, and its `finally` closed the connection before
restoring, so a close failure skipped the restore — the same silent failure mode
the fixture's own docstring warns a second copy would get wrong. Both are inside
a `try` now, with the restore in an inner `finally` that runs whatever the
teardown does. And `NEVER_MIGRATED_ENGINE`'s docstring justified the constant
with "an in-memory database is gone the moment its connection closes", which is
false at the call site this story added
(`test_stage_two_database_conditions.py:193` passes `NAME =
"/srv/reporting.sqlite3"`); the constant is now documented as the engine alone
and the `:memory:` reasoning moved to the context manager that supplies it.

**And three in the prose.** `docs/deployment.md` claimed "no entrypoint, no pixi
task, no container command migrates" — disprovable in ten seconds against
`pixi.toml:458`, and by a test in this very story that *requires* that task to
exist. It now says no entrypoint, no *serving-process* task and no container
command, and explains why the `migrate` task is not a counter-example. The doc
documents the release-stage invocation as `pixi run manage <step>` while
`test_the_only_tasks_that_migrate_are_the_two_the_manifest_is_supposed_to_have`
justified the task with "the release stage invokes `pixi run migrate`" — a
different command, carrying neither `--database` nor `--noinput`. The docstring
now states the true justification: `migrate` is the local invocation and the task
AD-13's deadlock argument is written about. The `### Accepted risk R-3`
subsection named `web`, `worker` and `beat` unconditionally in a page that
qualifies every other Celery mention; it is now qualified the same way. Finally,
nothing pinned the new section at all — deleting or renaming it failed no test
while two module docstrings promise a reader they will find R-3 under its own
subheading — so
`test_the_deployment_page_still_carries_the_release_stage_contract_and_the_accepted_risk`
pins both headings by literal, following
`tests/unit/test_component_declaration.py`'s precedent.

**Gate after the review pass.** `pixi run format`, `pixi run lint`, `pixi run
typecheck`, `pixi run test` (1180 passed, 1 skipped — 30 new cases), `pixi run
test-integration` (290 passed, 6 skipped, unchanged), `pixi run docs`, and `pixi
run ci` — exit 0.

### File List

**New**

- `tests/unit/test_release_stage.py` — the static half: no serving process migrates directly or transitively; the positive control that proves the transitive walk over four synthetic manifests; `migrate`/`collectstatic` declare no `COMPONENT_PROCESS`; the four boot-time entrypoints reach for no management command; the Dockerfile instruction scan (skipped while the file is absent) and the seven synthetic cases that exercise its parser today; every declared migration step is a migration command naming its own alias exactly once and carrying `--noinput`; the set of migrating tasks is exactly two; the deployment page still carries both headings.
- `tests/integration/test_release_stage.py` — the deployment-side half: every declared process type refuses a schema the release stage never migrated, and the release-stage step itself is not refused (AC #4 / R-3).
- `tests/pixi_manifest.py` — the shared pixi-manifest reader, including the structural definition of the process group and the new `task_dependencies()`, which returns each `depends-on` entry's `args` alongside its name. `task_command()` reads pixi's list form as well as its string form, and `feature_scopes()` refuses a literal `[feature.default]` table rather than letting it replace the root scope.

**Updated**

- `docs/deployment.md` — new `## Migrations are a release-stage step` section: the ordering the deployment repository must implement, one step per database as `component.toml` declares, the start-time refusal and how it fits the readiness rule, and `### Accepted risk R-3: the refusal only fires for a declared process` stated as accepted and unmitigated with the deadlock that closing it would produce. The review pass corrected the headline claim (no *serving-process* task migrates; the `migrate` task exists and is not a counter-example) and qualified R-3's process list with "where `celery` is selected", as the rest of the page does.
- `tests/unit/test_process_model.py` — the manifest reader moved out to `tests/pixi_manifest.py` and is imported from there; assertions unchanged.
- `tests/unit/test_suite_policy.py` — `RECORDED_EXEMPTIONS` gains the one `pytest.skip` in `unit/test_release_stage.py`, with its reasoning. The review pass widened `_test_modules()` from three collection-name globs to every `.py` under `tests/`, so an evasion written into an imported helper is scanned like one written into a test, and recorded `coverage_policy.py`'s existing guard in the table.
- `tests/coverage_policy.py` — docstring only: its `pytest.skip` is now inside the scan and recorded, so the paragraph citing the old glob as the reason for its placement no longer says that.
- `tests/conftest.py` — `never_migrated_database_alias()` and `NEVER_MIGRATED_ENGINE`, promoted from Epic 4's private helper. The review pass moved every global mutation inside the `try` and the restore into an inner `finally`, so neither a raise from `connections[alias]` nor a failing `close()` can leak the replaced handler into the rest of the session; `NEVER_MIGRATED_ENGINE`'s docstring no longer claims an in-memory database at a call site that names a path.
- `tests/integration/startup/test_stage_two_database_conditions.py` — rewired to the shared helper; no behavioural change.
- `_bmad-output/implementation-artifacts/5-6-the-component-is-a-payload-that-runs-as-an-arbitrary-non-root-user.md` — Task 1 and Task 4 record the Dockerfile's obligation to satisfy this story's assertion, by test name.

**Read / verified, not modified**

- `component.toml` — the `[[databases]] migrate` list already targets `default` explicitly. No new keys.
- `pixi.toml` — `migrate` and `collectstatic` declare no `env` at all. Unchanged, and the new tests are what keep it so.
- `mkdocs.yml` — `deployment.md` already in `nav`.
- `src/config/asgi.py`, `src/config/wsgi.py` — neither imports `django.core.management`. The assertion pins that.
- `src/config/startup/` — Epic 4's refusal module. Untouched.
- `Dockerfile` — still absent; Story 5.6's.

## Review Triage Log

### 2026-08-28 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 17: (high 1, medium 8, low 8)
- defer: 0
- reject: 8
- addressed_findings:
  - `[high]` `[patch]` The transitive `depends-on` walk — the mechanism the module exists for — was never exercised: no task in the process group declares `depends-on`, so `task_dependencies` returned `()` for every task `_reachable` visited and stubbing it left the module green. Added `test_the_transitive_walk_finds_a_migration_reached_through_a_dependency`, a positive control over synthetic manifests covering both `depends-on` spellings at depth one and two plus a negative control. Mutation-verified: neutering `task_dependencies` fails 3 of its 4 cases.
  - `[medium]` `[patch]` `task_command` returned `""` for pixi's list form (`cmd = [...]`), so a serving task written that way escaped every migration scan. The list form is now joined.
  - `[medium]` `[patch]` `task_dependencies` discarded a table-form entry's `args`, so `depends-on = [{ task = "manage", args = ["migrate"] }]` on `web` passed the transitive assertion. It now returns `(name, args)` pairs and `_reachable` scans the full effective invocation.
  - `[medium]` `[patch]` `ENTRYPOINT_MODULES` covered only `asgi.py` and `wsgi.py`, missing `celery_app.py` (`worker`, `beat`) and `workers.py` (gunicorn `-k`) — a `call_command("migrate")` in either runs at every replica boot. Both added, `celery_app.py`'s presence derived from `selected_features` so the case holds in the four non-Celery combinations.
  - `[medium]` `[patch]` The Dockerfile parser — Story 5.6's gate, with zero execution today — dropped an instruction ending in an unterminated `\`, folded comment lines inside a continuation into the arguments (a false positive on prose about the prohibition), misparsed BuildKit heredoc bodies as separate instructions, and scanned neither `ONBUILD` nor `HEALTHCHECK`. All four fixed, and `test_the_dockerfile_parser_reads_each_form_an_instruction_can_take` now exercises the parser today rather than when 5.6 lands.
  - `[medium]` `[patch]` A declared `[[databases]] migrate` step was only required to be *some* management command naming its alias, so `migrate = ["shell --database default"]` passed. The step must now be a migration command.
  - `[medium]` `[patch]` `never_migrated_database_alias` replaced `connections.settings` and materialized the connection *before* its `try`, and closed the connection *before* the restore inside `finally`; either raise leaked mutated global connection state into the rest of the session. Every mutation is now inside the `try` with the restore in an inner `finally`.
  - `[medium]` `[patch]` `docs/deployment.md`'s headline claim "no entrypoint, no pixi task, no container command migrates" was disprovable in ten seconds — `pixi.toml` declares a `migrate` task and this story's own test requires it to exist. Reworded to the true rule (no *serving-process* task) with the reason the `migrate` task is not a counter-example.
  - `[medium]` `[patch]` The doc and the test docstring documented two different release-stage invocations (`pixi run manage migrate --database default --noinput` vs `pixi run migrate`). Reconciled on the `pixi run manage <step>` form the declared steps are shaped for.
  - `[low]` `[patch]` Declared steps were not required to carry `--noinput`; a release stage has no TTY and a prompting step hangs the rollout before any pod starts. Asserted.
  - `[low]` `[patch]` `shlex.split` raised `ValueError` on an unbalanced quote in `component.toml`, surfacing a malformed declaration as a traceback rather than as the offender list. Caught and reported as an offender.
  - `[low]` `[patch]` `_targeted_alias` returned the first `--database` while Django honours the last. Every occurrence is now collected and exactly one, matching the entry's alias, is required.
  - `[low]` `[patch]` `tests/pixi_manifest.py` matched none of `_test_modules()`'s three globs, so gate evasions added to the new shared helper were outside the scan the ban depends on. The walk is now every `*.py` under `tests/`, which also pulled `tests/coverage_policy.py`'s existing skip into `RECORDED_EXEMPTIONS` with its reasoning.
  - `[low]` `[patch]` `feature_scopes` let a literal `[feature.default]` table overwrite the root scope, silently removing every unscoped task from every walk. It now fails loudly.
  - `[low]` `[patch]` `NEVER_MIGRATED_ENGINE`'s docstring justified itself with "an in-memory database ... leaves no artifact", untrue at the call site passing `NAME = "/srv/reporting.sqlite3"`. The constant is documented as the engine alone; the `:memory:` reasoning moved to the context manager.
  - `[low]` `[patch]` Nothing pinned the new `## Migrations are a release-stage step` section, while two module docstrings asserted the R-3 price was recorded there. Both headings pinned by literal, following `tests/unit/test_component_declaration.py`'s precedent.
  - `[low]` `[patch]` The R-3 subsection named `worker` and `beat` unconditionally in a document that qualifies every other Celery mention. Qualified the same way.

Rejected: the `depends_on` underscore spelling (pixi refuses unexpected keys, so such a manifest does not load); `SERVING_PROCESSES` drift against `component.toml` (already asserted at `tests/unit/test_process_model.py:360`); overlap between the new integration module and Epic 4's condition tests (the split is what the spec mandates, and the differential case is not a duplicate); `RELEASE_STAGE_INSTRUCTION`'s coupling to the refusal's wording (deliberate, and its failure message says so); `DECLARED_PROCESSES` import-time evaluation and the `[0]` index (guarded by its own case); the inline `("migrate", "makemigrations")` literal in the detector guard (independence from the constant it guards is the point); `_targeted_alias`'s placement and double call, and two offenders for one defect (cosmetic); a dynamic `importlib` reach for the management package in an entrypoint (speculative).

## Auto Run Result

Status: done

### Summary

Story 5.5 delivers AD-22's release-stage contract as enforcement rather than prose. Nothing was added to `src/`: the behaviour the story names is the *absence* of a behaviour, so the artefact is the set of assertions that keeps it absent, plus the deployment-side documentation of what the component will not do for you.

The static half asserts that no serving process migrates — directly or through a transitively resolved `depends-on` — that `migrate` and `collectstatic` declare no `COMPONENT_PROCESS` (a `COMPONENT_PROCESS` on `migrate` is AD-13's deadlock, the refusal firing against the one command that clears it), that no boot-time entrypoint module reaches `django.core.management`, and that every `[[databases]] migrate` step in `component.toml` is a real, non-interactive migration naming its own alias. The Dockerfile assertion is written and exercised against synthetic input today; against the file itself it skips with an explicit reason until Story 5.6 lands it, and 5.6's task list now carries that obligation by test name.

The behavioural half asserts the contract from the deployment side: with `COMPONENT_PROCESS` set to each process type `component.toml` declares, an unmigrated alias refuses with `ImproperlyConfigured`; with it absent, the identical state raises nothing. That second case is AC #4 and R-3 in one — the mechanism that exempts `pixi run migrate` cannot distinguish it from a hand-rolled gunicorn, and a third case runs the same state twice over one configuration so the difference is attributable to the variable rather than to the set-up. Epic 4's stage-2 refusal was reused, not moved, duplicated or relaxed.

### Files changed

| File | Change |
|---|---|
| [tests/unit/test_release_stage.py](../../tests/unit/test_release_stage.py) | NEW — the static contract: process tasks, entrypoint modules, Dockerfile instructions, declared migration steps, and the positive controls that keep each detector honest. |
| [tests/integration/test_release_stage.py](../../tests/integration/test_release_stage.py) | NEW — the refusal fires for every declared process type and does not fire without one, parametrized from `component.toml`. |
| [tests/pixi_manifest.py](../../tests/pixi_manifest.py) | NEW — the shared pixi-manifest reader, extracted from `test_process_model.py` so two files cannot disagree about what a process is. |
| [tests/unit/test_process_model.py](../../tests/unit/test_process_model.py) | Reader extracted; assertions unchanged. |
| [tests/conftest.py](../../tests/conftest.py) | Epic 4's private second-database helper promoted to a shared `never_migrated_database_alias`, with its teardown made exception-safe. |
| [tests/integration/startup/test_stage_two_database_conditions.py](../../tests/integration/startup/test_stage_two_database_conditions.py) | Rewired to the shared helper; no behavioural change. |
| [tests/unit/test_suite_policy.py](../../tests/unit/test_suite_policy.py) | Evasion scan widened to every `*.py` under `tests/`; two exemptions recorded. |
| [tests/coverage_policy.py](../../tests/coverage_policy.py) | Docstring corrected — it cited the old glob as the reason for its placement. |
| [docs/deployment.md](../../docs/deployment.md) | NEW section `## Migrations are a release-stage step`, with the three-step ordering, one-step-per-database, how the refusal meshes with the readiness rule, and R-3 recorded as accepted and unmitigated. |
| [5-6-the-component-is-a-payload-that-runs-as-an-arbitrary-non-root-user.md](5-6-the-component-is-a-payload-that-runs-as-an-arbitrary-non-root-user.md) | Task list carries the Dockerfile obligation this story's assertion imposes. |

### Review findings

17 patches applied, 0 deferred, 8 rejected, 0 spec loopbacks. See the triage log above.

### Verification

- `pixi run ci` — exit 0, run twice by the orchestrator independently of the implementation agent. Pre-commit (ruff check, ruff format, mypy) all passed; `pixi run build` succeeded; `mypy src/` clean over 71 files; ruff clean; **1476 passed, 1 skipped**, coverage **96.99%** against a 90% floor.
- `pixi run docs` — `mkdocs build --strict`, no warnings; `deployment.md` was already registered in `mkdocs.yml` `nav`, so no change was needed there.
- The one skip is the Dockerfile case, which retires itself when Story 5.6 lands the file.
- **Mutation-verified rather than asserted:** neutering `task_dependencies` to return `()` fails 3 of the transitive walk's 4 cases. Before the review pass the same mutation left the module byte-identically green, which is the failure this story would otherwise have shipped.

### Residual risks

- **R-3 is unmitigated by design.** A serving process started outside `pixi run web` does not fire the migrations refusal. Recorded in `docs/deployment.md` under its own subheading; closing it would deadlock the release stage against `pixi run migrate`.
- **The Dockerfile assertion has not met a real Dockerfile.** Its parser is now exercised against synthetic input covering continuations, heredocs, `ONBUILD` and `HEALTHCHECK`, but Story 5.6 is where it first runs against the artefact it exists for.
- **SC-3 is not closed and cannot be here.** The deployment repository that implements the ordering this story documents lives elsewhere and is an explicit non-goal; this story delivers the component-side declaration and its enforcement.
- **The gate ran against sqlite.** No model or schema change is involved — these are assertion suites over configuration — so the PostgreSQL-only failure modes are not in play.
