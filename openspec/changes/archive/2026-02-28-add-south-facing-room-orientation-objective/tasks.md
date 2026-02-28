## 1. Orientation Model Foundation

- [x] 1.1 Add north/south edge resolution helpers (from `site.north`) in `plan_engine/solver/workflow.py` with clear docstrings and unit-testable behavior.
- [x] 1.2 Add orientation preference weight tables for major rooms and service rooms in `plan_engine/solver/space_specs.py`.

## 2. Solver Objective Integration

- [x] 2.1 In `plan_engine/solver/workflow.py`, build per-space soft penalty booleans for missing south-touch on `ldk`/`bedroom`/`master_bedroom` using inferred south edge.
- [x] 2.2 In `plan_engine/solver/workflow.py`, build per-space soft penalty booleans for missing north-touch on `washroom`/`bath`/`toilet`/`wc`/`storage` using inferred north edge.
- [x] 2.3 Extend `build_objective` in `plan_engine/solver/workflow.py` to include weighted orientation penalties while preserving existing hard constraints and objective terms.

## 3. Validator Diagnostics

- [x] 3.1 Add orientation preference livability checks in `plan_engine/validator/livability.py` that emit warnings (not errors) for unmet south/north preferences.
- [x] 3.2 Add concise per-floor/per-room orientation diagnostics to report output via `plan_engine/validator/livability.py`.

## 4. Tests and Example Coverage

- [x] 4.1 Add/extend solver tests in `tests/solver/` to validate `site.north` mapping and orientation objective preference outcomes.
- [x] 4.2 Add/extend validator tests in `tests/validator/` to validate orientation warning/diagnostic behavior.
- [x] 4.3 Add/update fixture specs under `resources/specs/` for north-direction variants (`top/right/bottom/left`) and regenerate impacted `examples/*/plan_output` outputs for review.

## 5. Verification

- [x] 5.1 Run targeted tests for touched modules (`tests/solver`, `tests/validator`) and fix regressions.
- [x] 5.2 Run `make verify` and `make test` to confirm end-to-end stability and coverage threshold compliance.
