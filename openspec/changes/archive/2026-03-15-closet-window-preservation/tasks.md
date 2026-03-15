# Tasks: closet-window-preservation

## Implementation

- [x] Add `_would_block_all_windows(host: Rect, wall_name: str, building_rect: Rect) -> bool` helper in `solution_builder.py` — returns True when the parent room has no exterior wall OTHER than the one named by `wall_name`
- [x] Update `_pick_closet_wall()` to expand candidates to include long-side walls when all short-side candidates would block all windows; update scoring to `(kills_all_windows, blocks_door, is_exterior)`
- [x] Update `_place_closet_on_wall()` to accept an optional `span_mm` parameter (defaults to `short_side` for backward compatibility); when provided, use `span_mm` instead of `short_side` for the CL strip length
- [x] Update `_fit_closet_strip()` to calculate `span_mm = ceil(target_area / depth_mm)` rounded to grid when the selected wall is a long-side fallback, and pass it to `_place_closet_on_wall()`

## Tests

- [x] Add unit test for `_would_block_all_windows()`: room with one exterior wall → True; room with two exterior walls → False
- [x] Add unit test for `_pick_closet_wall()` fallback: bedroom with single exterior short-side wall → selects long-side interior wall
- [x] Add unit test for partial-span placement: verify CL rect dimensions match `ceil(target_area / depth)` on long wall, not full wall length
- [x] Add regression test: run solver on 6370×12740 spec, verify Bedroom 4 has a window (exterior segment not fully blocked by CL)
