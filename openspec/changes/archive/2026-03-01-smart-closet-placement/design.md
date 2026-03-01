## Context

Embedded closets (type `closet`) are placed deterministically after the CP-SAT solver completes. The current algorithm in `solution_builder.py:_fit_closet_strip()` tries exactly two fixed positions — a horizontal strip anchored at the parent room's top-left corner, and a vertical strip anchored at the top-right corner — selecting whichever has the smallest area overshoot. This produces closets that frequently overlap exterior walls (blocking windows) and door walls (blocking circulation access), and never span a full wall as standard Japanese house closets do.

The renderer draws doors and windows after closets are placed, but has no awareness of closet positions, creating visual and functional conflicts in the output.

### Current pipeline

```
Solver (room rects) → solution_builder (closet placed, no context)
                    → Renderer (doors/windows placed, ignoring closets)
```

### Target pipeline

```
Solver (room rects) → solution_builder (wall-classified closet placement)
                    → Renderer (doors/windows, no conflicts)
```

## Goals / Non-Goals

**Goals:**

- Closets are placed on interior non-door walls, avoiding window and door conflicts
- Closets prefer to span the full length of the chosen wall at the configured depth
- The wall classification logic reuses the same door-prediction rules as the renderer
- A preflight warning catches rooms where no eligible closet wall may exist

**Non-Goals:**

- No changes to the CP-SAT solver model — closet placement remains post-solve
- No WIC (walk-in closet) changes — WICs are solver-level touching-constrained spaces
- No multi-rect (L2) room closet improvements
- No renderer changes — renderer draws closets wherever they are placed
- No DSL changes — closet specification format is unchanged

## Decisions

### D1: Wall classification at solution_builder time

**Decision**: Add a `_classify_walls()` function in `solution_builder.py` that, given a parent room rect, building footprint rect, floor topology, and solved spaces, returns a dict mapping each wall (`top`/`bottom`/`left`/`right`) to a classification: `free`, `exterior`, `door`, or `both`.

**Rationale**: At solution_builder time all the information needed to predict doors and windows is available: room positions are finalized, topology is known, and the building bounding rect is computable. This avoids any coupling to the renderer while producing identical predictions.

**Alternatives considered**:
- *Classify at render time and feed back*: Violates architecture boundary (renderer must not alter geometry).
- *Classify at solver time*: Information isn't finalized until after solving; adds unnecessary CP-SAT complexity.

### D2: Door prediction via shared utility

**Decision**: Extract the door-eligibility logic (currently `_should_draw_interior_door()` in `renderer/helpers.py`) into `plan_engine/constants.py` as `should_draw_interior_door()` (public, no underscore prefix). Both the renderer and solution_builder import from constants.

**Rationale**: The renderer and solution_builder need identical door prediction to stay in sync. A single source of truth in `constants.py` prevents drift. The function is pure (two string args → bool) with no renderer dependencies.

**Alternatives considered**:
- *Duplicate the logic in solution_builder*: Drift risk when door rules change.
- *Import from renderer into solver*: Violates architecture boundary (solver must not import renderer).

### D3: Full-wall-span as primary strategy

**Decision**: For each eligible wall (classified as `free`), place the closet spanning the wall's full length at the first viable depth from the depth candidate list. If multiple free walls exist, prefer the shorter wall (produces a more proportional closet area relative to target). Fall back to partial-span on the best available wall only if no free wall can fit the target area.

**Rationale**: Reference Japanese plans show closets spanning one full wall of the bedroom. Full-span is simpler to implement, produces cleaner visual results, and naturally avoids partial-coverage awkwardness.

**Wall preference order**:
1. `free` walls, shorter wall first (closet area closer to target)
2. `free` walls, longer wall (oversized but still valid)
3. `door` wall with partial span avoiding the shared segment (degraded)
4. `exterior` wall (last resort, window conflict accepted)
5. Legacy top-left/right-edge fallback (should never reach here)

### D4: Building rect computation

**Decision**: Compute `building_rect` as the bounding box of all solved indoor space rects on the floor, matching how the renderer computes it in `_bounding_rect(_floor_rects(floor))`.

**Rationale**: Exterior walls (where windows go) are defined as room walls coinciding with the building footprint boundary. The building rect must match the renderer's computation exactly.

### D5: Neighbor-on-wall detection

**Decision**: A neighbor "touches wall W" of the host room if any of the neighbor's rects share a collinear edge segment of positive length with the host room's wall W. For example, if the host's left wall is `x=host.x, y∈[host.y, host.y2]`, a neighbor touches it if any neighbor rect has `x2 == host.x` with overlapping y-range.

**Rationale**: This mirrors the renderer's `_shared_segment()` logic for placing doors. Positive-length overlap is required (point-only contacts don't get doors).

### D6: Preflight closet wall feasibility

**Decision**: Add a warning (not error) in `preflight/closets.py` that checks: for each room with an embedded closet, does the room type appear in `WINDOW_SPACE_TYPES` (eligible for windows)? If so, does the room have ≤ 1 non-exterior wall in the topology? If the room has 3+ topology-adjacent spaces all requiring doors, plus all remaining walls being exterior, emit a warning that closet placement may conflict with openings.

**Rationale**: This is a heuristic feasibility check at preflight time (before solving, before room positions are known). It cannot be exact because positions aren't known yet, but it can catch obviously problematic configurations (e.g., a room with 4 topology neighbors all needing doors).

## Risks / Trade-offs

**[Risk] Full-wall-span produces oversized closets** → Mitigation: Prefer the shorter free wall first, which naturally brings closet area closer to the target. If overshoot exceeds 2x the target area, fall back to partial span.

**[Risk] Door prediction diverges from renderer** → Mitigation: D2 extracts to a single shared function. A unit test asserts that solution_builder and renderer produce identical door predictions for a standard test case.

**[Risk] Building rect computation edge cases with buildable mask** → Mitigation: Use the same bounding-rect logic as the renderer. Buildable masks only restrict where rooms CAN be placed; once placed, the building rect is the bounding box of actual placements.

**[Risk] Visual regression in all examples** → Mitigation: Expected and desired. All 10 examples will be regenerated and visually inspected. The new placements should be visibly more realistic.
