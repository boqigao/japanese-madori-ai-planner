## Why

Window placement currently uses exact segment matching to exclude blocked areas (entry doors, closets). When a closet occupies only a portion of a room's exterior wall, the full wall segment does not match the shorter blocked segment, so the entire wall receives windows — including the portion behind the closet. This produces physically impossible floor plans where windows overlap with closets.

## What Changes

- Replace exact-match segment blocking in `draw_windows` with segment subtraction: candidate exterior segments are split by removing blocked portions, and only the remaining unblocked sub-segments receive windows.
- Window count and position are recalculated on the shorter sub-segments, so windows naturally shrink or reduce in count when closets consume part of an exterior wall.

## Non-goals

- Changing closet placement logic (closet wall selection is unchanged).
- Changing window sizing rules (34% of wall, 910–1600mm clamped) — only the candidate segments change.
- Addressing closets on interior walls or door–closet interactions (already handled).

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `renderer`: Window placement must subtract blocked segments from candidate exterior segments instead of exact-matching. Window count and position are recomputed on remaining sub-segments.

## Impact

- **Renderer module**: `plan_engine/renderer/openings.py` — `draw_windows` function and a new segment-subtraction helper.
- **Renderer helpers**: `plan_engine/renderer/helpers.py` — possible new utility for segment splitting.
- **Tests**: `tests/render/test_renderer_closet_semantics.py` — new/updated tests for partial blocking.
- No solver, preflight, validator, or structural changes.
