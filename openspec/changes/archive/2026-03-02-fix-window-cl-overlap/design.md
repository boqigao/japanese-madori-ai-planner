## Design Decisions

### D1: Segment Subtraction in `draw_windows`

**Decision**: Replace the exact-match `if key in blocked_segments: continue` check with a segment subtraction step that splits each candidate exterior segment into sub-segments by removing blocked portions.

**Why**: The current code compares full wall segments against the blocked set. A room's exterior wall (e.g., `(5460,0)→(9100,0)`, length 3640mm) never matches a shorter blocked segment from a closet (e.g., `(8190,0)→(9100,0)`, length 910mm). The full wall passes the filter, and windows are drawn across the entire wall — including behind the closet.

**How**: After deduplicating candidate segments, apply a `_subtract_blocked_segments(segment, blocked_segments)` helper that returns a list of remaining sub-segments. Each sub-segment then goes through the existing length check and window count logic independently.

```
Before:
  candidate: (5460, 0) ─────────────────── (9100, 0)   3640mm → 2 windows
  blocked:                    (8190, 0) ── (9100, 0)   ignored (no exact match)

After:
  candidate splits into:
    (5460, 0) ─────── (8190, 0)   2730mm → 1 window (centered)
    (8190, 0) ── (9100, 0)        blocked, removed
```

### D2: Subtraction Helper in `helpers.py`

**Decision**: Add `_subtract_segments(segment, blocked)` → `list[segment]` to `plan_engine/renderer/helpers.py`.

**Why**: Keep segment arithmetic in the helpers module alongside `_exterior_segments`, `_segment_length`, `_segment_key`. The function works on axis-aligned segments only (all our segments are horizontal or vertical).

**Algorithm**: For each blocked segment that overlaps with the candidate on the same axis line, clip the candidate. Collect remaining pieces. The function handles:
- Full overlap → empty result
- Partial overlap at one end → one shorter sub-segment
- Overlap in the middle → two sub-segments (left and right of blocked)
- No overlap → original segment unchanged

### D3: Existing Exact-Match Check Remains for Full-Wall Blocks

**Decision**: The subtraction replaces the exact-match check entirely. We do NOT keep both mechanisms.

**Why**: Segment subtraction is a superset of exact matching. If a blocked segment exactly equals the candidate, subtraction produces an empty list — same as the old `continue` behavior. No need for two code paths.

### D4: Window Count Recalculation on Sub-Segments

**Decision**: The existing window count rules (≥3600mm → 2 windows, ≥1365mm → 1 window, <1365mm → 0) are applied to each sub-segment independently.

**Why**: After subtraction, a 3640mm wall minus a 910mm blocked portion becomes a 2730mm sub-segment. This naturally drops from 2 windows to 1 window. No special logic needed — the existing thresholds handle it.

## Architecture

```
draw_windows()
  │
  ├── for each space in WINDOW_SPACE_TYPES:
  │     ├── _exterior_segments(rect, building_rect)     [existing]
  │     ├── deduplicate                                  [existing]
  │     │
  │     ├── NEW: for each segment:
  │     │     └── _subtract_segments(segment, blocked)   [NEW helper]
  │     │           → list of unblocked sub-segments
  │     │
  │     └── for each sub-segment:                        [existing logic]
  │           ├── length < 1365mm → skip
  │           ├── length ≥ 3600mm → 2 windows
  │           └── else → 1 window
  │
  └── return opening_segments
```

## Files Changed

| File | Change |
|------|--------|
| `plan_engine/renderer/helpers.py` | Add `_subtract_segments()` |
| `plan_engine/renderer/openings.py` | Replace exact-match with subtraction loop in `draw_windows()` |
| `tests/render/test_renderer_closet_semantics.py` | Add tests for partial blocking, subtraction edge cases |
