## 1. DSL and Domain Model Updates

- [x] 1.1 Update stair type constants and parsing validation in `plan_engine/constants.py` and `plan_engine/dsl.py` to accept `U_turn`.
- [x] 1.2 Update stair-related dataclass typing/serialization and docstrings in `plan_engine/models.py` for `U_turn` compatibility.

## 2. Stair Geometry and Portal Logic

- [x] 2.1 Implement `U_turn` footprint component generation in `plan_engine/solver/rect_var.py` with 455mm-grid-aligned cell geometry.
- [x] 2.2 Extend portal mapping for `U_turn` in `plan_engine/stair_logic.py` so each floor has one deterministic portal component/edge.

## 3. Solver Constraint Integration

- [x] 3.1 Update stair variable creation and shared-anchor handling in `plan_engine/solver/workflow.py` to include `U_turn` components.
- [x] 3.2 Ensure `U_turn` stairs satisfy existing stair-hall portal edge constraints and internal portal-edge constraints in `plan_engine/solver/workflow.py`.
- [x] 3.3 Confirm `plan_engine/solver/solution_builder.py` serializes solved `U_turn` stair geometry correctly.

## 4. Validator and Renderer Support

- [x] 4.1 Extend stair validation checks in `plan_engine/validator/stair.py` for `U_turn` projection/portal consistency and connectivity diagnostics.
- [x] 4.2 Extend stair drawing in `plan_engine/renderer/stair.py` (and glue in `plan_engine/renderer/core.py` if required) to visualize `U_turn` flights, landing, treads, and voids.

## 5. Benchmarks, Tests, and Verification

- [x] 5.1 Add/extend tests in `tests/dsl/`, `tests/solver/`, `tests/validator/`, and `tests/render/` for `U_turn` parsing, solving, validation, and rendering behavior.
- [x] 5.2 Update benchmark specs under `examples/*/spec.yaml` to replace `straight` with `L_landing` or `U_turn` where practical.
- [x] 5.3 Regenerate impacted outputs under `examples/*/plan_output` and confirm no broken stair connectivity/regressions.
- [x] 5.4 Run `make verify` and `make test` and fix any regressions before final review.
