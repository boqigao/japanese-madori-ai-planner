## Why

Current outputs still rely on `straight` stairs in benchmark cases, which wastes floor area and conflicts with common Japanese detached-house practice where `L_landing` or U-turn stairs are preferred. This gap now blocks layout quality improvements because stair geometry and circulation realism are under-modeled.

## What Changes

- Add a new stair type `U_turn` in the DSL/model layer and support it through the full pipeline.
- Define deterministic `U_turn` stair geometry components (flights + landing) on the 455mm grid, including portal semantics across floors.
- Extend solver stair footprint generation and stair-to-hall connection constraints to handle `U_turn` without breaking existing `straight`/`L_landing` behavior.
- Extend stair validation rules to verify projection alignment and portal connectivity for `U_turn`.
- Extend renderer stair visualization to draw `U_turn` components, treads, and void/opening correctly in SVG/PNG.
- Update benchmark example specs to replace `straight` stairs with `L_landing` or `U_turn` where appropriate, then regenerate outputs.

## Non-goals

- No change to non-stair room packing rules, adjacency semantics, or hall topology policy.
- No new daylight/sun simulation features.
- No change to wall structural proxy model beyond what current stair footprint geometry already implies.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `dsl`: Extend accepted stair `type` values to include `U_turn` in spec parsing/validation.
- `solver`: Extend stair footprint, portal mapping, and stair connectivity constraints to solve plans with `U_turn` stairs.
- `renderer`: Add `U_turn` stair drawing behavior so generated SVG/PNG reflects the new stair geometry.
- `validator`: Extend stair validation checks for `U_turn` portal/connection correctness.

## Impact

- Affected modules: `plan_engine/dsl.py`, `plan_engine/constants.py`, `plan_engine/models.py`, `plan_engine/stair_logic.py`, `plan_engine/solver/rect_var.py`, `plan_engine/solver/workflow.py`, `plan_engine/validator/stair.py`, `plan_engine/renderer/stair.py` (and potentially `renderer/core.py` glue).
- Affected pipeline stages: DSL parsing, solver, validator, renderer.
- Affected tests: solver/validator/renderer stair-focused test suites plus updated benchmark fixtures under `examples/`.
