# Story 8.5: The materializer refuses invalid combinations

Status: ready-for-dev

## Story

As a lead developer,
I want an invalid pairing refused with its reason,
so that I never receive a component that cannot start.

## Acceptance Criteria

**Traceability:** FR-34, FR-26

1. **Given** a request for background task processing without the Redis cache
   **When** materialization is attempted
   **Then** it is refused before any source is produced

2. **Given** the refusal
   **When** it is reported
   **Then** it names the broker constraint
   **And** does not fail generically

## Tasks / Subtasks

- [ ] Task 1: Read the constraint from the carrier (AC: #1, #2)
  - [ ] Extend `tools/materializer/carrier.py` to load the feature constraints Story 7.6 declares in `accelerator.toml` — the constraint's identifier, the feature that requires, the feature that is required, and the human-readable reason text.
  - [ ] The constraint must be data, not code. Do not hardcode `celery requires redis` in `tools/materializer/`; AD-1 permits exactly one declaration site and it is `accelerator.toml`.
  - [ ] The reason text must name the broker constraint explicitly — background task processing needs a broker, the Redis cache feature is what supplies it, so background task processing without the Redis cache has no broker.

- [ ] Task 2: Implement validation (AC: #1)
  - [ ] `tools/materializer/combination.py` — `validate(combination, carrier) -> None`, raising `InvalidCombinationError` with the constraint's reason text when any declared constraint is violated. Return `None` on success; do not return a boolean the caller may ignore.
  - [ ] Call `validate()` as the **first** action of `materialize()` in `tools/materializer/materialize.py`, before the destination directory is created and before any path is read or copied. AC #1's "before any source is produced" is a hard ordering requirement, not a nicety.
  - [ ] `enumerate_valid()` filters through the same `validate()` so the twelve are derived from the declared constraint rather than from a second, parallel rule.

- [ ] Task 3: Report the refusal (AC: #2)
  - [ ] `InvalidCombinationError.__str__` returns a message that names the requested selection, the violated constraint by identifier, and the reason text. Never a bare `ValueError`, never "invalid combination", never a generic message.
  - [ ] `tools/materializer/cli.py` catches `InvalidCombinationError` specifically — never a bare `except:` and never `except Exception` — emits it through the `structlog` logger with the constraint identifier as a bound key, and exits with a non-zero status distinct from the status used for an unexpected failure.
  - [ ] Do not swallow the exception and do not degrade it to a warning. A refusal never degrades to a warning (Consistency Conventions).

- [ ] Task 4: Assert no partial output (AC: #1)
  - [ ] After a refused request, the destination directory must not exist, or must be exactly as it was before the call. Assert both in the test.
  - [ ] If `materialize()` writes into a staging directory and moves it into place, the staging directory must also be absent after a refusal.

- [ ] Task 5: Tests (AC: #1, #2)
  - [ ] `tests/unit/materializer/test_validate.py` — all four invalid combinations (`celery` selected, `redis` unselected, `ui` and `storage` each free) raise `InvalidCombinationError`; all twelve valid combinations do not; the exception message contains the constraint identifier and names the broker constraint; `enumerate_valid()` yields exactly the twelve that pass `validate()`.
  - [ ] `tests/integration/materializer/test_refusal_produces_nothing.py` (`@pytest.mark.integration`, `tmp_path`) — call `materialize()` with each invalid combination into a fresh `tmp_path` destination and assert the destination does not exist afterwards; call the CLI and assert the non-zero exit status and the structured log line carrying the constraint identifier.
  - [ ] Assert the count: sixteen selections in the four-boolean space, four refused, twelve accepted.

## Dev Notes

### Architecture Constraints

- **FR-26** (declared in Epic 7, Story 7.6): "The broker constraint is enforced at selection — twelve valid combinations, not sixteen." **FR-34** (this story): "The materializer refuses invalid combinations, naming the broker constraint." The cross-epic thread is explicit: "FR-26's broker constraint is *declared* in Epic 7 and *enforced* by the materializer in Epic 8 as FR-34."
- **AD-1** (binding): every feature's "constraints and presets" are declared in `accelerator.toml` "and nowhere else". The materializer reads the constraint; it does not restate it. A second declaration site is forbidden.
- **Consistency Conventions, Configuration errors**: "A refusal never degrades to a warning (CG-3)." This applies to the materializer's refusal as much as to the component's startup refusals.
- **Not this story:** the component's own startup refusal contract at `src/config/startup/` (Epic 4, AD-26) is a different mechanism at a different stage. Do not reuse `ImproperlyConfigured` here — the materializer is not Django and raises `InvalidCombinationError` from `tools/materializer/errors.py`.
- Never bare `except:`; never `except X: pass`. Log at an appropriate level or re-raise.
- Never `print()`. The CLI reports through `structlog`, JSON to stdout.
- Full type hints on public signatures; Google-style docstrings; `X | Y` not `Union`.

### Source Tree — files to touch

| Path | NEW/UPDATE | What changes |
|---|---|---|
| `tools/materializer/carrier.py` | UPDATE | Created by Story 8.2 as a disposition loader. This story adds constraint loading. Preserve the four-member `Disposition` enum and the `machinery` default. |
| `tools/materializer/combination.py` | UPDATE | Created by Story 8.2 with `Combination` and `enumerate_valid()`. This story adds `validate()` and routes `enumerate_valid()` through it. Preserve the fixed enumeration order (Story 8.4) and the identifier format. |
| `tools/materializer/materialize.py` | UPDATE | This story makes `validate()` the first statement, before any filesystem effect. Preserve path pruning (8.2) and region pruning (8.3). |
| `tools/materializer/errors.py` | UPDATE | Created by Story 8.2. This story gives `InvalidCombinationError` its `__str__` and the fields it carries. |
| `tools/materializer/cli.py` | UPDATE | Created by Story 8.2. Adds the specific handler and the distinct exit status. |
| `accelerator.toml` | UPDATE | Story 7.6 declares the constraint. If it has not landed, this story is blocked on it — do not declare the constraint here as a stopgap. |
| `tests/unit/materializer/test_validate.py` | NEW | |
| `tests/integration/materializer/test_refusal_produces_nothing.py` | NEW | |

#### Project Structure Notes

No structural change. `tools/materializer/` is `machinery` per the Structural Seed and neither the validator nor its tests travel into a component — which is correct: a materialized component has already passed validation and has nothing to validate.

### Testing Requirements

- `tests/unit/materializer/test_validate.py` — isolated, no filesystem, milliseconds. Parametrize over all sixteen points of the four-boolean space so the twelve/four split is asserted rather than assumed.
- `tests/integration/materializer/test_refusal_produces_nothing.py` — `@pytest.mark.integration`, `tmp_path` for every destination, leaves state as found.
- The refusal message assertion must check for the constraint identifier and for the substantive words of the reason, not for an exact string — but it must be strict enough that a generic message fails. Asserting only `pytest.raises(InvalidCombinationError)` is insufficient for AC #2.
- Coverage floor 90% including templates, `COVERAGE_CORE=ctrace` (AD-20).
- Disposition: both test files are `machinery`.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#AD-1]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-django-15-factor-base-2026-08-15/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.5]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.6] — the broker constraint and the presets, declared there
- [Source: _bmad-output/planning-artifacts/epics.md] — FR-26, FR-34; and the cross-epic thread "declared in Epic 7 and enforced by the materializer in Epic 8 as FR-34"

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
