# Deferred Work

Items deferred from code reviews and other workflows: real, but not actionable
at the time they were raised. Each entry records why.

## Deferred from: code review of 1-1-the-full-gate-runs-in-ci-through-one-invocation (2026-08-16)

- **`sonar-project.properties` comment names a nonexistent task `pixi run cov`** (real task: `test-cov`) [sonar-project.properties:20]. Pre-existing, not touched by the reviewed diff — though it sits directly in the coverage.xml pipeline that diff modifies at both ends (producer in `ci.yml`, consumer in `sonarqube.yml`). Worth fixing opportunistically next time either file is touched.
- **Tests never exercise `pixi`'s runtime fail-fast `depends-on` behavior**, only the static manifest [tests/unit/test_gate_contract.py]. Out of Story 1.1's stated unit-test scope ("no I/O beyond reading repository files, no network, no database"); the sequential/fail-fast/exit-code-propagation behavior was verified manually in a scratch workspace and recorded in the story's Debug Log References. If pixi's `depends-on` scheduling semantics ever change, nothing here would catch the regression — would need an integration-level check that intentionally fails an early gate step and asserts a later one never ran.
- **`_invokes()` is a string-matcher fragile to `pixi run -e dev <task>`, chained (`&&`), or piped invocations** [tests/unit/test_gate_contract.py:74]. No current workflow invokes tasks this way, so zero present impact. Hardening backlog if invocation styles diversify.
- **Contract-test blind spots with no current instances** [tests/unit/test_gate_contract.py]: reusable `uses:` workflow calls (job-level references to another local workflow file), target-scoped pixi tasks (`[target.<platform>.tasks]`), duplicate top-level YAML keys (PyYAML silently keeps the last occurrence), and artifact-retention-expiry error-message clarity (a re-run past `retention-days: 7` produces a generic "not found" indistinguishable from "never produced"). None apply to the current five workflow files or task table. Hardening backlog.
