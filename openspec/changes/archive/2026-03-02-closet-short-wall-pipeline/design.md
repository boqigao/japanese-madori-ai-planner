## Context

Embedded closets are placed as a post-solve heuristic in `solution_builder.py`. The previous approach (`smart-closet-placement`) classified walls as free/door/exterior and picked the "best" wall. This still produces three defects:

1. **CL blocks doors**: The algorithm knows a wall has a door but doesn't know the exact segment position. It may place CL covering the door location.
2. **CL blocks windows**: Renderer places windows on all eligible exterior edges without knowing CL occupies some of them.
3. **CL makes bedrooms L-shaped**: CL may span a long wall or partial span on any wall, leaving the bedroom non-rectangular.

Real Japanese closets follow a clear pattern: CL is a full-width strip across the short side of the bedroom, cut from one end of the long axis. The bedroom remains rectangular. Doors are placed on the remaining wall portions, and windows are only placed on exterior segments not occupied by CL.

Current pipeline order: Solver → CL placement → Renderer (doors, windows, CL drawing).
The renderer computes door segments independently and places windows without CL awareness.

## Goals / Non-Goals

**Goals:**
- CL always spans the full short side of its parent room, keeping the bedroom rectangular
- CL placement knows exact door segment positions to avoid conflicts
- Windows are never placed on exterior walls occupied by CL
- Door position on a shared wall adapts to avoid CL (door slides to the far end from CL)

**Non-Goals:**
- No CP-SAT solver changes (room orientation is handled post-solve)
- No changes to walk-in closet (WIC) handling
- No changes to closet area allocation in solver constraints
- No changes to preflight warnings

## Decisions

### D1: Short-Wall-Span Rule

**Decision**: CL always spans the full short side `S = min(W, H)` of the parent room. CL depth `d` is cut from one end of the long axis `L = max(W, H)`. Remaining bedroom is `(L - d) × S`, always rectangular.

**Why not keep wall-priority (free > door > exterior)?** The wall-priority approach can select a long wall or a wall that creates an L-shape. The short-wall rule is geometrically deterministic and matches real floor plan conventions.

**Wall selection within short-wall candidates**: For a horizontal room (W > H), candidates are `left` and `right`. For a vertical room (H > W), candidates are `top` and `bottom`. Among the two candidates, prefer the one that is interior (not on building boundary) to keep windows on the exterior end. If both candidates are exterior, pick the one farther from the primary door.

### D2: Door Segment Computation Extracted to Shared Utility

**Decision**: Create `compute_door_segments()` in `plan_engine/solver/solution_builder.py` (not in renderer, not in constants). This function takes solved spaces, topology, and building rect, and returns a mapping of `(space_a_id, space_b_id) → segment`. It reuses `Rect.shared_edge_segment()` from `models/geometry.py` and `should_draw_interior_door()` from `constants.py`.

**Why in solution_builder?** The solver module already has access to solved spaces and topology. Putting it in constants would add geometry dependencies to a pure-constants module. Putting it in renderer would break the rule that solver must not import renderer. The renderer can import from solver's solution_builder (it's a utility, not a constraint-building function).

**Alternative considered**: A new `plan_engine/geometry_utils.py` shared module. Rejected as over-engineering for a single function — solution_builder is the natural home since it already does post-solve geometry work.

### D3: Pipeline Order — CL Before Windows

**Decision**: The information flow becomes:

```
Solver (room rects)
  → compute_door_segments()
  → _fit_closet_strip() using door segments + building rect
  → EmbeddedClosetGeometry now includes blocked_exterior_segments
  → Renderer: doors (unchanged), then windows (blocked_segments includes CL exterior)
```

CL placement happens in `solution_builder.py` (unchanged location). The new output includes which exterior segments are blocked by CL. The renderer's `draw_windows()` already accepts `blocked_segments` — we just need to pass CL's blocked segments into it.

**Model change**: Add `blocked_exterior_segments` field to `EmbeddedClosetGeometry` (list of segment tuples). The renderer reads these and adds them to the window blocked set.

### D4: Door Position Adjustment

**Decision**: When CL is placed on a wall that has a door segment, the renderer should place the door at the end of the shared segment that is farthest from CL. This is a renderer-side adjustment, not a solution_builder change.

**Why renderer-side?** Door rendering is already in the renderer. The renderer knows both the shared segment and the CL rect. It can offset the door symbol to the non-CL end of the segment. Solution_builder doesn't need to know how doors are drawn.

**Mechanism**: In `draw_interior_doors()`, after computing the shared segment, check if any CL rect of either space overlaps that segment's wall. If so, shift the door symbol to the non-overlapping portion.

### D5: Remove Previous Wall-Priority Functions

**Decision**: Remove `_select_closet_wall()`, `_span_wall()`, `_wall_span_length()`, `_partial_span_on_wall()`, `_fit_closet_strip_legacy()` from solution_builder. The new `_fit_closet_strip()` implements the short-wall rule directly. `_classify_walls()` and `_neighbor_touching_walls()` are kept for potential future use but may be removed if unused after refactor.

### D6: Handling Near-Square Rooms

**Decision**: When `W == H` (perfect square) or `|W - H| <= minor_grid` (nearly square), treat as having no strong short/long axis. In this case, prefer the wall that is interior (not on building boundary) among all four candidates. This degrades gracefully to a "best available wall" selection for edge cases.

## Risks / Trade-offs

**[Risk] CL area exceeds target when spanning full short wall**: Full short wall span at depth `d` gives area `S × d`. If this is much larger than the target CL area, the closet is oversized. → **Mitigation**: If `S × d > 2 × target_area`, reduce depth to `d' = ceil(target_area / S)` grid-aligned. If minimum depth (1 cell) still overshoots, accept it — a slightly larger closet is better than breaking the rectangular bedroom guarantee.

**[Risk] Renderer imports from solution_builder for door segment utility**: This creates a new import path renderer → solver. → **Mitigation**: The function is a pure geometry utility with no solver state dependency. If this coupling becomes a concern, extract to a shared module later.

**[Risk] CL on exterior wall removes window from that wall**: Bedrooms may lose a window wall. → **Mitigation**: This is by design (closets don't have windows). The algorithm prefers interior walls for CL. Exterior-wall CL only happens when both long-axis ends are exterior (corner rooms), and even then the other walls retain windows. The preflight warning remains active for edge cases.
