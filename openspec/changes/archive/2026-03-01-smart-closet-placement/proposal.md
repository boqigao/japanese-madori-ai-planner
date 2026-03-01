## Why

Embedded closets are currently placed by a naive post-solve algorithm that only tries two fixed positions (top-left horizontal strip or top-right vertical strip), selecting purely by area overshoot. This produces unrealistic results: closets frequently overlap exterior walls where windows will be drawn, block doorways to circulation spaces, and never span a full wall as real Japanese house closets do.

## What Changes

- **Wall-aware closet placement**: Replace the fixed-position `_fit_closet_strip()` algorithm in `solution_builder.py` with a wall-classification strategy that identifies which of the parent room's four walls are exterior (window zones), which are door walls (shared with topology-adjacent circulation/accessible spaces), and which are free interior walls suitable for closet placement.
- **Full-wall-span strategy**: Prefer spanning an entire eligible wall at the configured depth, matching the standard Japanese closet pattern (CL fills one narrow wall of the room). Fall back to partial-wall placement only when no full-wall option exists.
- **Closet placement context plumbing**: Pass building footprint bounding rect, floor topology, and solved space map into the closet placement function so it has the information needed for wall classification.
- **Preflight closet feasibility check**: Add a warning-level preflight check that flags rooms with closets where all four walls may be exterior or door-occupied, catching infeasible configurations before solving.

### Non-goals

- **Solver-level closet constraints**: Closet placement remains a deterministic post-solve step. Moving closets into the CP-SAT model is deferred to a future change.
- **Walk-in closet (WIC) changes**: WIC placement uses solver-level `touching_constraint` and is not affected by this change.
- **Multi-rect room closets**: Closets in L-shaped rooms (L2 components) continue to use the largest rect component. Improved multi-rect handling is out of scope.
- **Renderer changes**: The renderer already correctly draws closets wherever they are placed. No renderer changes are needed.

## Capabilities

### New Capabilities

_(none — this enhances an existing capability)_

### Modified Capabilities

- `closet-semantics`: Embedded closet placement algorithm changes from fixed-position to wall-aware full-span strategy. Adds wall classification (exterior/door/free) and placement preference ordering.
- `preflight`: Adds a warning-level check for closet wall feasibility on rooms that declare embedded closets.

## Impact

- **`plan_engine/solver/solution_builder.py`**: Primary change target. `_fit_closet_strip()`, `_build_embedded_closet_geometries()` signature changes to accept building rect, topology, and solved spaces.
- **`plan_engine/preflight/core.py` or `plan_engine/preflight/closets.py`**: New closet wall feasibility check.
- **`plan_engine/renderer/helpers.py`**: `_should_draw_interior_door()` may need to be extracted to a shared location so both renderer and solution_builder can use the same door-prediction logic.
- **Generated output**: All examples will produce different closet positions. Visual regression expected but improvements should be verifiable by inspection.
- **Tests**: Existing closet tests in `tests/solver/test_solver_closet_semantics.py` will need updates to reflect new placement positions. New tests for wall classification logic.
