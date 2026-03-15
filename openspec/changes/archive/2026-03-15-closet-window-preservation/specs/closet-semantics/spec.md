# Closet Semantics — Delta Spec (closet-window-preservation)

## Changed Requirement: Window-Preserving Closet Fallback

**Modifies**: "Full-Wall-Span Closet Placement"

When placing the CL on a short-side wall would block ALL exterior window segments of the parent room, the system MUST fall back to placing the CL on a **partial long-side interior wall** instead.

### Detection

The system MUST check whether the selected short-side wall is the parent room's **only exterior wall**. If placing CL there would leave zero unblocked exterior segments ≥1365mm, the fallback MUST trigger.

A helper `_would_block_all_windows(host, wall_name, building_rect) -> bool` determines this by checking whether the parent room has any exterior wall on a side OTHER than `wall_name`.

### Fallback behavior

When fallback triggers:

1. Expand candidates to include long-side walls (perpendicular to the original short-side candidates)
2. Filter to **interior** long-side walls only (exclude exterior long sides)
3. Among interior long-side candidates, prefer walls that don't block doors (same `_cl_blocks_door` scoring)
4. Place CL with **partial span**: `span_mm = ceil(target_area / depth_mm)` rounded up to 455mm grid, NOT the full wall length
5. Anchor the CL at the corner where the long wall meets an interior edge (to keep it away from the exterior window wall)

### Updated scoring

The combined scoring for all candidates (short + fallback long) becomes:

```
(blocks_door, kills_all_windows, is_exterior)
```

This ensures: avoid door blocking > preserve windows > prefer interior.

### Modified `_place_closet_on_wall()`

The function gains an optional `span_mm` parameter. When placing on a long wall via fallback, `span_mm` is calculated from the target area rather than using the full short side.

### Scenarios

#### Scenario: CL fallback to long-side interior wall (new)

- **GIVEN** Bedroom 4 rect (0, 3640, 4550, 3640) mm with building boundary (0, 0, 6370, 12740)
- **AND** short side = 3640mm, candidates = [left, right]
- **AND** left wall (x=0) is the ONLY exterior wall
- **AND** right wall (x=4550) has a hall door
- **AND** CL target area = 1,620,000 mm2 (1.0 tatami), depth = 910mm
- **WHEN** closet placement detects that left would block all windows
- **THEN** fallback to long-side candidates: [top, bottom]
- **AND** top wall (y=3640) is interior (Bedroom 3 above) → viable
- **AND** CL span = ceil(1,620,000 / 910) = 1820mm (rounded to grid)
- **AND** CL rect = (0, 3640, 1820, 910) — partial top wall, anchored at left corner
- **AND** left exterior wall (3640mm) remains fully unblocked → windows ✓

#### Scenario: Short-side placement is fine (no change)

- **GIVEN** a bedroom with two exterior walls (left and bottom)
- **AND** CL short-side candidate is left (exterior)
- **AND** bottom wall is also exterior → room has other window segments
- **WHEN** closet placement evaluates the left wall
- **THEN** `_would_block_all_windows` returns False (bottom exterior remains)
- **AND** CL is placed on left wall as before — no fallback needed

#### Scenario: All long-side walls are exterior (edge case)

- **GIVEN** a bedroom with only one interior wall (the door side, which is a short side)
- **AND** all other walls are exterior
- **WHEN** fallback triggers because short-side placement kills windows
- **AND** long-side candidates are all exterior
- **THEN** pick the long-side wall with the lowest `(blocks_door, is_exterior)` score
- **AND** CL goes on a partial exterior long wall — some windows are blocked but not all
