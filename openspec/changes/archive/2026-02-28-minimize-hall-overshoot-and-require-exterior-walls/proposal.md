## Why

Current outputs still over-allocate circulation area (`hall`) and occasionally place bedroom/LDK blocks fully inside the floor, which creates windowless major rooms and unrealistic plans. Professional review in `local-dev/floor-feedback/v8/professional.md` identifies these as priority quality defects to fix now.

## What Changes

- Increase hall overshoot penalty so hall area growth above target is strongly discouraged during optimization.
- Add a hard solver rule: every `bedroom`, `master_bedroom`, and `ldk` must touch at least one exterior boundary segment.
- Add corresponding validation errors so plans are rejected if any required major room is interior-only.
- Add deterministic preflight checks for clearly impossible specs (for example, no feasible exterior-touch opportunities for required room set).
- Update benchmark examples impacted by this rule so they remain solvable and realistic.

## Non-goals

- No orientation-aware preference optimization in this change (e.g., “south-facing first”).
- No new window-placement engine or daylight simulation.
- No redesign of stair type policy (straight vs L/U stair strategy is out of scope).

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `solver`: strengthen hall-area minimization objective and enforce exterior-touch hard constraints for bedroom/master/LDK.
- `preflight`: add feasibility diagnostics for new exterior-touch requirement.
- `validator`: reject solutions where bedroom/master/LDK does not touch an exterior boundary.

## Impact

- Affected modules: `plan_engine/solver/space_specs.py`, `plan_engine/solver/workflow.py`, `plan_engine/preflight.py`, `plan_engine/validator/geometry.py` (and related tests/spec fixtures).
- Affected pipeline stages: preflight, solver, validator.
- Output impact: fewer oversized hall layouts and no interior-only bedroom/LDK placements in accepted plans.
- Backward compatibility: stricter validity may make some existing specs infeasible until topology/area targets are adjusted.
