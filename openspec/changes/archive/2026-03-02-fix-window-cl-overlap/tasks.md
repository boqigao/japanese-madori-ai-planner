## 1. Segment Subtraction Helper

- [x] 1.1 Add `_subtract_segments(segment, blocked_segments)` to `plan_engine/renderer/helpers.py`. Takes one candidate segment and the full set of blocked segments. Returns a list of remaining sub-segments after removing all overlapping blocked portions. Handles: full overlap (empty result), partial overlap at one end (one shorter segment), overlap in the middle (two sub-segments), no overlap (original segment unchanged). Only considers blocked segments on the same axis line (same x for vertical, same y for horizontal).
- [x] 1.2 Add unit tests for `_subtract_segments()` in `tests/render/test_renderer_closet_semantics.py`: no overlap returns original, partial overlap at end, full overlap returns empty, two blocked portions leave middle, blocked segment shorter than candidate, blocked segment extends beyond candidate.

## 2. Integrate Subtraction into `draw_windows`

- [x] 2.1 In `plan_engine/renderer/openings.py` `draw_windows()`, replace the exact-match `if key in blocked_segments: continue` check with a subtraction loop: for each unique candidate segment, call `_subtract_segments(segment, blocked_segments)`, then iterate over the resulting sub-segments for length check and window placement.
- [x] 2.2 Add integration tests in `tests/render/test_renderer_closet_semantics.py`: CL partially blocks exterior wall → window count reduced, CL fully blocks wall → no window, no CL → windows unchanged.

## 3. Verification

- [x] 3.1 Run `uv run pytest -x -q` to verify all tests pass.
- [x] 3.2 Run `uv run ruff check plan_engine/` to verify no lint errors.
- [x] 3.3 Regenerate all examples in `./examples/` and visually verify: no window symbols overlap with CL areas, window count is reduced on walls with partial CL blockage.
- [x] 3.4 Run `make verify` for end-to-end validation.
