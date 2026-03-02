## 1. Door Segment Computation Utility

- [x] 1.1 Add `compute_door_segments()` function to `plan_engine/solver/solution_builder.py`. Takes `solved_spaces: dict[str, SpaceGeometry]`, `floor_topology: list[tuple[str, str]]` and returns `dict[frozenset[str], tuple[tuple[int,int], tuple[int,int]]]`. Uses `Rect.shared_edge_segment()` and `should_draw_interior_door()` to find the longest shared edge for each door-eligible topology pair.
- [x] 1.2 Add unit tests for `compute_door_segments()` in `tests/solver/test_closet_placement.py` covering: hall-bedroom door found, bedroom-bedroom no door, L-shaped hall picks longest segment.
- [x] 1.3 Run `uv run pytest -x -q` to verify no breakage.

## 2. Short-Wall-Span CL Placement

- [x] 2.1 Add `_pick_closet_wall()` function to `solution_builder.py`. Takes `host: Rect`, `building_rect: Rect`, `door_segments: dict[frozenset[str], segment]`, `host_id: str`, `floor_topology` and returns the chosen wall name (`top`/`bottom`/`left`/`right`). Logic: identify short/long axes, pick among the two long-axis-end walls, prefer interior over exterior, use door segment position as tiebreaker.
- [x] 2.2 Add `_place_closet_on_wall()` function to `solution_builder.py`. Takes `host: Rect`, `wall_name: str`, `depth_mm: int`, `short_side: int` and returns `Rect`. CL rect always spans the full short side. Handles all four wall directions.
- [x] 2.3 Rewrite `_fit_closet_strip()` to use `_pick_closet_wall()` + `_place_closet_on_wall()`. Add overshoot cap: if `short_side × depth > 2 × target_area`, reduce depth to `ceil(target_area / short_side)` grid-aligned (min 1 cell). Remove parameters for old wall-classification path. Keep `_fit_closet_strip_legacy()` as fallback for edge cases where the new approach returns None.
- [x] 2.4 Update `_build_embedded_closet_geometries()` to call `compute_door_segments()` once per floor, then pass the result into `_fit_closet_strip()`.
- [x] 2.5 Add unit tests for `_pick_closet_wall()` and `_place_closet_on_wall()` in `tests/solver/test_closet_placement.py` covering: horizontal room picks left/right, vertical room picks top/bottom, prefers interior over exterior, near-square room fallback, overshoot depth reduction.

## 3. CL Blocked Exterior Segments

- [x] 3.1 Add `blocked_exterior_segments` field to `EmbeddedClosetGeometry` in `plan_engine/models/solution.py` — a list of segment tuples `list[tuple[tuple[int,int], tuple[int,int]]]` (default empty). Update `to_dict()` to include it.
- [x] 3.2 In `_build_embedded_closet_geometries()`, after placing each CL, compute which exterior wall segments (edges coinciding with building boundary) are occupied by the CL rect. Store them in `blocked_exterior_segments`.
- [x] 3.3 Add a helper `_closet_blocked_exterior_segments(closet_rect: Rect, building_rect: Rect) -> list[segment]` in `solution_builder.py` that returns exterior segments covered by the closet.
- [x] 3.4 Add unit tests for `_closet_blocked_exterior_segments()` in `tests/solver/test_closet_placement.py`: CL on interior wall returns empty, CL on exterior wall returns the matching edge segment, CL in corner covers two edges.

## 4. Renderer — Windows Avoid CL

- [x] 4.1 In `plan_engine/renderer/core.py`, after computing `blocked_segments` from entry door, iterate over `floor.embedded_closets` and add each closet's `blocked_exterior_segments` to the blocked set before calling `_draw_windows()`.
- [x] 4.2 Add a renderer-level test in `tests/render/test_renderer_closet_semantics.py` verifying that when a CL has `blocked_exterior_segments`, those segments are excluded from windows.

## 5. Renderer — Door Position Avoids CL

- [x] 5.1 In `plan_engine/renderer/openings.py` `draw_interior_doors()`, after computing the shared segment for a door, check if any `EmbeddedClosetGeometry` rect overlaps that segment's wall. If so, trim the door segment to exclude the CL-overlapping portion. Use the trimmed segment for door symbol placement.
- [x] 5.2 Add helper `_trim_segment_for_closet(segment, closet_rects) -> segment` in `openings.py` that returns the portion of the segment not overlapped by any closet rect.
- [x] 5.3 Add unit tests for door-CL avoidance in `tests/render/test_renderer_closet_semantics.py`: door segment trimmed when CL overlaps, door segment unchanged when no CL overlap.

## 6. Remove Old Wall-Priority Functions

- [x] 6.1 Remove `_select_closet_wall()`, `_span_wall()`, `_wall_span_length()`, `_partial_span_on_wall()` from `solution_builder.py`. Remove `_classify_walls()` and `_neighbor_touching_walls()` if no longer referenced.
- [x] 6.2 Remove or update corresponding tests in `tests/solver/test_closet_wall_classification.py` — delete tests for removed functions, keep/adapt tests for any retained functions.
- [x] 6.3 Run `uv run ruff check plan_engine/` to verify no lint errors from dead imports.

## 7. Verification

- [x] 7.1 Run `uv run pytest -x -q` to verify all existing and new tests pass.
- [x] 7.2 Run `uv run ruff check plan_engine/` to verify no lint errors.
- [x] 7.3 Regenerate all examples in `./examples/` and visually verify: (a) CL spans full short side in every bedroom, (b) bedrooms remain rectangular after CL, (c) no windows on CL-occupied exterior edges, (d) doors are not blocked by CL.
- [x] 7.4 Run `make verify` for end-to-end validation.
