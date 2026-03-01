## 1. Extract Shared Door-Eligibility Logic

- [x] 1.1 Move `_should_draw_interior_door()` logic from `plan_engine/renderer/helpers.py` to `plan_engine/constants.py` as a public function `should_draw_interior_door(left_type, right_type) -> bool`. Keep the private `_should_draw_interior_door` in `renderer/helpers.py` as a thin wrapper that delegates to the new public function for backward compatibility.
- [x] 1.2 Update `plan_engine/renderer/helpers.py` to delegate `_should_draw_interior_door()` to `constants.should_draw_interior_door()`.
- [x] 1.3 Run `uv run pytest -x -q` to verify no breakage.

## 2. Wall Classification

- [x] 2.1 Add `_classify_walls()` function to `plan_engine/solver/solution_builder.py`. Takes `host: Rect`, `building_rect: Rect`, `host_id: str`, `host_type: str`, `floor_topology: list[tuple[str, str]]`, `solved_spaces: dict[str, SpaceGeometry]` and returns `dict[str, str]` mapping `{top, bottom, left, right}` → `{free, exterior, door, both}`.
- [x] 2.2 Implement exterior detection: a wall is `exterior` if its edge coincides with the building footprint boundary.
- [x] 2.3 Implement door-wall detection: a wall is `door` if any topology-adjacent space with `should_draw_interior_door(host_type, neighbor_type) == True` has a rect sharing a positive-length collinear edge on that wall.
- [x] 2.4 Add helper `_neighbor_touches_wall()` that checks if any rect of a neighbor space shares a collinear segment with a specific wall of the host room.
- [x] 2.5 Add unit tests for `_classify_walls()` in `tests/solver/test_closet_wall_classification.py` covering: free wall, exterior wall, door wall, combined both, and corner room with mixed walls.

## 3. Full-Wall-Span Placement

- [x] 3.1 Add `_span_wall()` function to `solution_builder.py` that places a closet spanning the full length of a named wall (`top`/`bottom`/`left`/`right`) at a given depth in mm. Returns `Rect` or `None` if depth exceeds room dimension.
- [x] 3.2 Add `_select_closet_wall()` function that takes classified walls, host rect, depth candidates, minor grid, and target area, and returns the best `(wall_name, Rect)` following the priority: (1) free walls shorter-first at full span, (2) free walls longer, (3) partial span on non-free walls, (4) legacy fallback. Apply 2x overshoot cap: if full-span area > 2x target, use partial span instead.
- [x] 3.3 Refactor `_fit_closet_strip()` to call `_classify_walls()` and `_select_closet_wall()`. Add new parameters: `building_rect`, `floor_topology`, `solved_spaces`, `host_id`, `host_type`. Preserve the existing signature as a fallback path when classification data is unavailable.
- [x] 3.4 Update `_build_embedded_closet_geometries()` to compute `building_rect` from solved spaces and pass `building_rect`, `floor.topology`, `solved_spaces`, `host_id`, and `host_type` through to `_fit_closet_strip()`.
- [x] 3.5 Update `_build_embedded_closet_geometries()` call site in `build_solution()` to pass `floor.topology.adjacency` (as list of tuples) and the floor spec needed for topology access.
- [x] 3.6 Add unit tests for `_span_wall()` and `_select_closet_wall()` in `tests/solver/test_closet_wall_classification.py` covering: full-span on free wall, overshoot cap triggers partial, fallback when no free wall.

## 4. Preflight Closet Feasibility Warning

- [x] 4.1 Add `_warn_closet_wall_feasibility()` function in `plan_engine/preflight/closets.py`. For each room with an embedded closet whose type is in `WINDOW_SPACE_TYPES`, count topology-adjacent spaces that would produce doors (`should_draw_interior_door`). If all adjacency edges produce doors, emit a warning.
- [x] 4.2 Integrate `_warn_closet_wall_feasibility()` into the preflight pipeline (call from `run_preflight()` in `plan_engine/preflight/core.py`).
- [x] 4.3 Add a unit test for the warning in `tests/test_preflight.py` covering: normal case (no warning), and edge case (all neighbors are door-eligible → warning emitted).

## 5. Verification and Examples

- [x] 5.1 Run `uv run pytest -x -q` to verify all existing and new tests pass.
- [x] 5.2 Run `uv run ruff check plan_engine/` to verify no lint errors introduced.
- [x] 5.3 Regenerate all examples in `./examples/` and visually verify closet positions are improved (closets on interior non-door walls, no window/door blocking).
- [x] 5.4 Run `make verify` for end-to-end validation.
