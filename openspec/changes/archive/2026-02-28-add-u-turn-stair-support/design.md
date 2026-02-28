## Context

The current stair system supports only `straight` and `L_landing`. Professional review for benchmark outputs indicates `straight` stairs are unrealistic for target Japanese detached-house plans and often waste envelope area that should be used by major rooms. The change is cross-module: DSL parsing, stair footprint generation in solver, portal/connectivity validation, and stair rendering in SVG/PNG.

Constraints that shape the implementation:
- All geometric dimensions remain 455mm-grid aligned (`value % 455 == 0`).
- Solver uses cell units (1 cell = 455mm), then converts back to mm in `PlanSolution`.
- Module boundaries stay strict: solver computes geometry, validator checks solved output, renderer is read-only.

## Goals / Non-Goals

**Goals:**
- Add `U_turn` as a valid stair type in DSL/model/constants.
- Define deterministic `U_turn` stair footprint and portal semantics compatible with existing `stair_portal_for_floor` flow.
- Add solver constraints so `U_turn` stairs participate in no-overlap, buildable-mask bounds, and hall connection rules.
- Render `U_turn` stairs with readable flights/landing/treads/opening in SVG/PNG.
- Validate `U_turn` projection alignment and portal connectivity consistency on multi-floor plans.
- Update benchmark specs to replace `straight` with `L_landing` or `U_turn` and regenerate outputs.

**Non-Goals:**
- Rework global topology optimization strategy for non-stair rooms.
- Add new stair ergonomics optimization beyond current riser/tread preference model.
- Add 3D simulation, construction-detail output, or code-compliance calculations.

## Decisions

### 1) Add `U_turn` as a third canonical stair type
- Decision: extend `STAIR_TYPES`, `StairSpec.type`, and DSL validation to include `U_turn`.
- Rationale: keeps stair typing explicit and backward-compatible.
- Alternative: encode U-turn via generic component DSL.
- Rejected: higher schema complexity and harder validation for MVP.

### 2) Represent `U_turn` footprint as 3 fixed components
- Decision: model as `flight_a + landing + flight_b` with deterministic offsets in cell units, similar to `L_landing` componentized approach.
- Rationale: reuses existing `RectVar` composition and no-overlap mechanics.
- Alternative: a single composite bounding rect.
- Rejected: loses component-level portal and tread visualization semantics.

### 3) Keep portal mapping deterministic per floor rank
- Decision: extend `stair_portal_for_floor` to define valid portal component/edge for `U_turn`, preserving “one valid access edge per floor” behavior.
- Rationale: avoids ambiguous circulation and matches existing validator logic.
- Alternative: dynamic portal selection from topology.
- Rejected: increases model branching and weakens explainability.

### 4) Solver constraints remain hard for stair-hall connection
- Decision: keep stair-to-hall portal edge constraints hard for `U_turn` just like existing types.
- Rationale: avoids non-reachable stairs and hidden infeasible outputs.
- Alternative: soft stair-hall penalties.
- Rejected: would allow logically broken plans.

### 5) Renderer draws U-turn by component semantics
- Decision: add `U_turn` branch in stair renderer to draw tread lines along both flights with landing/void/guardrail behavior consistent with existing styles.
- Rationale: minimal UI delta and preserves visual language.
- Alternative: generic stair hatch without directional treads.
- Rejected: poor readability for review/debug.

## Risks / Trade-offs

- [Risk] Additional stair branch increases solver complexity and solve time on dense plans.
  - Mitigation: keep footprint deterministic and reuse existing no-overlap/connectivity primitives.
- [Risk] Incorrect portal-edge mapping could reintroduce unreachable-floor issues.
  - Mitigation: add dedicated unit tests for `U_turn` floor-rank portal semantics and validator checks.
- [Risk] Benchmark spec migration may create new infeasible cases.
  - Mitigation: migrate gradually per case, regenerate outputs, and record exceptions.

## Migration Plan

1. Extend DSL/constants/models to accept and serialize `U_turn` stair type.
2. Implement `U_turn` footprint generation in solver stair geometry (`rect_var`) and portal mapping (`stair_logic`).
3. Extend solver workflow constraints and solution builder handling for `U_turn`.
4. Extend validator stair checks and renderer stair drawing logic.
5. Add/adjust tests for parser, solver, validator, renderer stair behavior.
6. Update benchmark specs (`examples/*/spec.yaml`) from `straight` to `L_landing` or `U_turn` and regenerate `plan_output`.
7. Rollback path: keep specs on `L_landing`, disable `U_turn` parsing branch, and retain existing stair types only.

## Open Questions

- Should `U_turn` be preferred over `L_landing` by default in future objective tuning, or remain spec-driven only?
- For narrow envelopes, do we allow mirrored `U_turn` variants now or in a follow-up change?
- Should top-floor `open to below` visualization be mandatory for all `U_turn` variants, or only when non-portal flight area exists?
