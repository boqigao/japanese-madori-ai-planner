## 1. Preflight Feasibility Guard

- [x] 1.1 Add a major-room exterior-touch feasibility check in `plan_engine/preflight.py` for floors containing `bedroom`, `master_bedroom`, or `ldk`.
- [x] 1.2 Emit actionable preflight diagnostics/suggestions when buildable mask has no envelope-contact opportunity for required major rooms.

## 2. Solver Objective and Hard Constraints

- [x] 2.1 Increase hall overshoot objective weight in `plan_engine/solver/space_specs.py` to minimize oversized hall outcomes.
- [x] 2.2 In `plan_engine/solver/workflow.py`, enforce a hard exterior-touch constraint for each `bedroom`, `master_bedroom`, and `ldk` entity.
- [x] 2.3 Ensure the exterior-touch rule handles multi-rectangle entities correctly (pass if any component touches exterior) without breaking existing 455mm grid constraints.

## 3. Validator Enforcement

- [x] 3.1 Add validator hard checks in `plan_engine/validator/geometry.py` to reject solved plans where `bedroom`/`master_bedroom`/`ldk` lacks exterior boundary contact.
- [x] 3.2 Add clear per-floor/per-room error messages for exterior-touch violations in `ValidationReport` output.

## 4. Regression and Fixture Updates

- [x] 4.1 Add/extend tests in `tests/preflight/`, `tests/solver/`, and `tests/validator/` to cover feasible and infeasible exterior-touch scenarios.
- [x] 4.2 Add/update YAML fixtures under `resources/specs/` for interior-only major-room failure and exterior-touch success cases.
- [x] 4.3 Regenerate and review impacted benchmark outputs under `examples/` to confirm hall area reduction and no interior-only bedroom/LDK placement.

## 5. End-to-End Verification

- [x] 5.1 Run targeted tests for touched modules (`preflight`, `solver`, `validator`) and fix regressions.
- [x] 5.2 Run `make verify` and `make test` to confirm end-to-end stability and coverage requirements.
