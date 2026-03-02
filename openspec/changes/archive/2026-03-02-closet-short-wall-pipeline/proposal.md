## Why

Embedded closets (CL) are placed as a post-solve heuristic that picks a wall based on free/door/exterior classification, but ignores room geometry orientation. This produces three critical defects: (1) CL often blocks doorways because the placement algorithm doesn't know the exact door segment position, (2) CL blocks windows because renderer places windows without knowing where CL is, and (3) CL cuts rooms into L-shapes because it may span a long wall instead of the short wall. In real Japanese floor plans, CL always spans the full short wall at one end of the long axis, keeping the bedroom rectangular and leaving the opposite end for windows.

## What Changes

- **Rewrite CL placement rule**: CL must always span the full short side of the parent room, cutting a strip from one end of the long axis. This guarantees the remaining bedroom is rectangular.
- **Compute door segments before CL placement**: Extract the door segment computation (currently in renderer) into a shared utility so that CL placement knows where each door is located, not just which wall has a door.
- **Pipeline reorder — CL before windows**: CL-occupied exterior wall segments must be passed to the renderer's window stage as blocked segments, so windows are never drawn on walls occupied by CL.
- **Door position awareness for CL**: When the chosen wall has a door, place the door at the far end from CL (or CL at the far end from the door) to avoid conflicts.
- **Remove previous wall-priority logic**: Replace the free > door > exterior wall selection with the new short-wall-first rule. The previous `_select_closet_wall()`, `_span_wall()`, and related functions are superseded.

### Non-goals

- Solver (CP-SAT) changes to influence room orientation are out of scope for this change. The new placement algorithm handles all orientations post-solve.
- Walk-in closets (WIC) are unaffected — they remain independent solver spaces.
- Closet area allocation in the solver is unchanged — the solver already includes CL area in the parent bedroom target.

## Capabilities

### New Capabilities
- `door-segment-computation`: Shared utility to compute door segment positions from solved room rects and topology, usable by both CL placement and renderer.

### Modified Capabilities
- `closet-semantics`: Replace wall-priority placement with short-wall-span rule; add door-segment awareness; previous requirements (wall classification priority, overshoot cap, "no exterior overlap" as absolute rule) are superseded by the new geometric rule.
- `renderer`: Window placement must accept CL-blocked exterior segments and skip them.

## Impact

- **plan_engine/solver/solution_builder.py**: Major rewrite of `_fit_closet_strip()`, `_select_closet_wall()`, `_partial_span_on_wall()`. New short-wall placement logic. Door segment computation integrated.
- **plan_engine/renderer/openings.py**: `draw_windows()` receives additional blocked segments from CL exterior occupation. Door segment computation extracted to shared utility.
- **plan_engine/renderer/helpers.py** or **plan_engine/constants.py**: New shared `compute_door_segments()` utility.
- **plan_engine/models/solution.py**: `FloorSolution` or `EmbeddedClosetGeometry` may need a field for CL-blocked exterior segments.
- **Affected pipeline stages**: solver (solution_builder), renderer (openings).
- **Preflight**: No changes needed — existing `_warn_closet_wall_feasibility()` remains valid as a heuristic.
