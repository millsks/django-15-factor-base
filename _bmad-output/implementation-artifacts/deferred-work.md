# Deferred Work

Items deferred from code reviews and other workflows: real, but not actionable
at the time they were raised. Each entry records why.

## Deferred from: code review of 1-1-the-full-gate-runs-in-ci-through-one-invocation (2026-08-16)

- **`sonar-project.properties` comment names a nonexistent task `pixi run cov`** (real task: `test-cov`) [sonar-project.properties:20]. Pre-existing, not touched by the reviewed diff — though it sits directly in the coverage.xml pipeline that diff modifies at both ends (producer in `ci.yml`, consumer in `sonarqube.yml`). Worth fixing opportunistically next time either file is touched.
- **Tests never exercise `pixi`'s runtime fail-fast `depends-on` behavior**, only the static manifest [tests/unit/test_gate_contract.py]. Out of Story 1.1's stated unit-test scope ("no I/O beyond reading repository files, no network, no database"); the sequential/fail-fast/exit-code-propagation behavior was verified manually in a scratch workspace and recorded in the story's Debug Log References. If pixi's `depends-on` scheduling semantics ever change, nothing here would catch the regression — would need an integration-level check that intentionally fails an early gate step and asserts a later one never ran.
- **`_invokes()` is a string-matcher fragile to `pixi run -e dev <task>`, chained (`&&`), or piped invocations** [tests/unit/test_gate_contract.py:74]. No current workflow invokes tasks this way, so zero present impact. Hardening backlog if invocation styles diversify.
- **Contract-test blind spots with no current instances** [tests/unit/test_gate_contract.py]: reusable `uses:` workflow calls (job-level references to another local workflow file), target-scoped pixi tasks (`[target.<platform>.tasks]`), duplicate top-level YAML keys (PyYAML silently keeps the last occurrence), and artifact-retention-expiry error-message clarity (a re-run past `retention-days: 7` produces a generic "not found" indistinguishable from "never produced"). None apply to the current five workflow files or task table. Hardening backlog.

## Deferred from: code review of 1-2-the-gate-runs-against-postgresql (2026-08-15)

- source_spec: `1-2-the-gate-runs-against-postgresql.md`
  summary: Nothing type-checks `tests/` — mypy is scoped to `src/` in both the `typecheck` task and the pre-commit hook, so annotation errors in the suite are invisible to the gate.
  evidence: `pixi.toml:197` defines `typecheck = "mypy src/"`, and `.pre-commit-config.yaml`'s mypy hook also runs `mypy src/` with `pass_filenames: false`, so no configuration reaches the tests directory. This review found a missing return annotation on a fixture in the new `tests/unit/test_database_selection.py` that no gate step would ever have reported (patched here by hand). Pre-existing and project-wide rather than caused by this story; widening the scope would surface an unknown backlog across the whole existing suite, which is its own piece of work.

- source_spec: `1-2-the-gate-runs-against-postgresql.md`
  summary: Importing `config.settings.base` calls the process-global `configure_structlog()`, so every settings-reload test silently reconfigures logging for whatever runs after it.
  evidence: `src/config/settings/base.py` calls `configure_structlog()` at import time. `tests/unit/test_settings.py` established the evict-and-reimport pattern and this story's `test_database_selection.py` extends it, so the module is now re-imported roughly a dozen times per run — each time re-applying a non-test logging configuration ahead of `test_observability_logging.py` and `test_request_logging.py`. No ordering failure is observed today, and the tests pass in any order currently produced, but the coupling is real and invisible. The fix belongs with the observability work rather than with a database story.

- source_spec: `1-2-the-gate-runs-against-postgresql.md`
  summary: `ATOMIC_REQUESTS` is applied to the `default` alias only, so AD-9's forecast second database would be served non-atomically without anything in the source noticing.
  evidence: `src/config/settings/base.py:80` sets `DATABASES["default"]["ATOMIC_REQUESTS"] = True` against one hardcoded key, while AD-9 states that Epic 9's refusals "iterate every configured database" — the architecture already expects more than one alias. This story's `test_every_branch_sets_atomic_requests` asserts the setting across *every* configured alias and names the offenders, so the day a second database is added the suite reports which one is missing it; but the assertion is currently vacuous beyond `default`, and the fix is a one-line loop in `base.py`. Not made here: the story's own Task 4 forbids touching `base.py`, and Dev Notes state "do not add a second database in this story". Belongs with the Epic 9 work that introduces the second alias.

### DW-1: Follow-up review still recommended for 1-2-the-gate-runs-against-postgresql after the damping cap was spent
origin: review-budget-followup
source_spec: `1-2-the-gate-runs-against-postgresql.md`
location: n/a
severity: low
reason: The follow-up-review damping cap (limits.max_followup_reviews = 1) was spent with the story finalized (status: done, verify green) while the review pass still recommended an independent follow-up. The work was committed by bmad-loop run 20260815-155824-9f6b; this entry preserves the lingering recommendation for a deliberate later review.
status: open
