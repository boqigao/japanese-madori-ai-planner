## Why

47% of bedrooms across the 10 examples have aspect ratios exceeding 1:1.5, with the worst reaching 1:2.5 (essentially a corridor). Architectural review confirms the standard range for Japanese residential bedrooms is 1:1.25 ~ 1:1.5. The current solver hard constraint allows ratios up to 1:2.5 (`2*w ≤ 5*h`), which is far too permissive.

## What Changes

- Tighten the bedroom aspect ratio hard constraint from 1:2.5 to 1:1.80 (`5*w ≤ 9*h` and `5*h ≤ 9*w`) in the solver. This applies to `bedroom` and `master_bedroom` types.
- Regenerate all examples to verify improved proportions and confirm solver feasibility.

## Non-goals

- Changing the minimum short side (2275mm is acceptable for compact houses).
- Modifying the existing soft penalty `|w - h|` (it already pushes toward square; the tight hard constraint will make it more effective).
- Changing aspect ratio constraints for non-bedroom room types (LDK, hall, etc.).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `solver`: Bedroom aspect ratio hard constraint tightened from 1:2.5 to 1:1.80.

## Impact

- **Solver module**: `plan_engine/solver/workflow_spaces.py` — change the linear inequality for bedroom aspect ratio.
- **Examples**: All 10 examples will be regenerated. Room proportions will change; some layouts may shift significantly.
- **Risk**: Tighter constraint may cause solver infeasibility for very compact envelopes. Need to verify all 10 examples still solve.
