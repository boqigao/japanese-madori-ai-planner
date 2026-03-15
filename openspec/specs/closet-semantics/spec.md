# Closet Semantics Specification

## Purpose
Defines the rules for embedded closet placement within parent rooms (bedrooms). Closets are placed as strips spanning the full short side of the parent room, with wall selection based on CL-rect overlap simulation and building boundary detection.

## Requirements

### Requirement: Full-Wall-Span Closet Placement

The system MUST place an embedded closet as a strip spanning the full short side of the parent room, cut from one end of the long axis. Given a parent room rect with width `W` and height `H`:

- Short side `S = min(W, H)`, Long side `L = max(W, H)`.
- CL length = `S` (spans the entire short side).
- CL depth `d` is determined from the closet spec's depth or default 910mm (2 cells), 455mm-grid-aligned.
- CL is placed at one end of the long axis: the resulting CL rect has dimensions `d × S` (if room is horizontal, W > H) or `S × d` (if room is vertical, H > W).
- Remaining bedroom rect is `(L - d) × S`, always rectangular.

Wall selection among the two long-axis-end candidates uses CL-rect overlap simulation. For each candidate wall, the system computes the CL rect that would result from placement on that wall (`_place_closet_on_wall`) and checks whether it physically overlaps any door segment involving the host room — including doors on perpendicular walls near the CL strip corner. Scoring per candidate: `(blocks_any_door, is_exterior)`.

1. Avoid walls where the simulated CL rect would overlap any door segment. This covers doors on the candidate wall itself AND doors on perpendicular walls whose segment falls within the CL strip zone.
2. Among non-blocking candidates, prefer interior walls (not on building boundary) to preserve exterior walls for windows.

If `S × d > 2 × target_area`, reduce depth to `d' = ceil(target_area / S)` rounded up to the next 455mm multiple. Minimum depth is 455mm (1 cell).

#### Scenario: Horizontal bedroom — CL on interior end

- **GIVEN** a bedroom rect (0, 3185, 5460, 2275) mm with building boundary (0, 0, 9100, 5460)
- **AND** short side = 2275mm (left/right walls), long side = 5460mm (top/bottom direction)
- **AND** left wall (x=0) is on building boundary (exterior), right wall (x2=5460) is interior
- **AND** CL depth = 910mm
- **WHEN** closet placement runs
- **THEN** CL rect = (4550, 3185, 910, 2275) — at the right (interior) end, spanning full short side 2275mm
- **AND** remaining bedroom = (0, 3185, 4550, 2275) — rectangular

#### Scenario: Vertical bedroom — CL on interior end

- **GIVEN** a bedroom rect (6370, 0, 2730, 5460) mm with building boundary (0, 0, 9100, 5460)
- **AND** short side = 2730mm (top/bottom walls), long side = 5460mm (left/right direction)
- **AND** top wall (y=0) is on building boundary (exterior), bottom wall (y2=5460) is on boundary (exterior)
- **AND** left wall (x=6370) is interior (hall adjacent)
- **AND** CL depth = 910mm
- **WHEN** closet placement runs
- **THEN** CL is placed at top or bottom end (both exterior, pick based on door position)
- **AND** CL rect spans full short side: width = 2730mm, depth = 910mm
- **AND** remaining bedroom is rectangular: 2730 × 4550mm

#### Scenario: Overshoot cap reduces depth

- **GIVEN** a bedroom rect (0, 0, 1820, 5460) mm
- **AND** short side = 1820mm, CL target area = 1,620,000 mm2 (1 tatami)
- **AND** default depth 910mm gives area 1820 × 910 = 1,656,200 mm2 which is ≤ 2 × target
- **WHEN** closet placement runs
- **THEN** CL depth = 910mm, CL rect = 1820 × 910mm (full short side span)

#### Scenario: Near-square room

- **GIVEN** a bedroom rect (0, 0, 2730, 2730) mm (perfect square)
- **WHEN** closet placement runs
- **THEN** CL is placed on whichever wall is interior (not on building boundary), spanning the full 2730mm

### Requirement: Closet Must Not Block Doorways

The system MUST use computed door segments to ensure CL does not physically overlap a door. Because the CL strip spans the full short side, its edges align with the host room boundary — this means the CL can block doors not only on the candidate wall but also on perpendicular walls near the CL strip corner. Wall selection MUST simulate the CL rect and reject candidates that would overlap any door segment. As a secondary defense, the renderer MUST trim door segments to exclude CL-overlapping portions.

#### Scenario: CL and door on the same wall — door slides away

- **GIVEN** a bedroom with CL placed at the right end (interior wall)
- **AND** the right wall has a door segment from hall adjacency at the upper portion
- **WHEN** renderer draws the door
- **THEN** the door is positioned on the shared segment portion that does not overlap with the CL rect

#### Scenario: CL on wall with no door — no conflict

- **GIVEN** a bedroom with CL placed at the top end
- **AND** the top wall has no topology-adjacent door-eligible neighbor
- **WHEN** closet placement runs
- **THEN** CL is placed without door conflict consideration

#### Scenario: CL would block door on perpendicular wall — avoids that wall

- **GIVEN** a vertical bedroom rect (0, 2730, 2275, 5460) mm with candidates top/bottom
- **AND** the hall door is on the right wall (x=2275) at y=[2730, 3640]
- **AND** CL on "top" would produce rect (0, 2730, 2275, 910) whose right edge (x=2275) overlaps the door segment
- **WHEN** wall selection simulates CL rects for each candidate
- **THEN** "top" is rejected (blocks perpendicular door), "bottom" is chosen instead
- **AND** the door remains unobstructed

### Requirement: Shared Door-Eligibility Logic

The door-eligibility function used by closet wall classification MUST be identical to the function used by the renderer for interior door placement. Both MUST import from a single shared location.

#### Scenario: Consistent door prediction

- **GIVEN** two spaces (bedroom, hall) that are topology-adjacent with a shared wall segment
- **WHEN** both the closet wall classifier and the renderer evaluate whether a door should be placed
- **THEN** both produce the same boolean result

### Requirement: Window-Preserving Closet Fallback

**Modifies**: "Full-Wall-Span Closet Placement"

When placing the CL on a short-side wall would block ALL exterior window segments of the parent room, the system MUST fall back to placing the CL on a **partial long-side interior wall** instead.

#### Detection

The system MUST check whether the selected short-side wall is the parent room's **only exterior wall**. If placing CL there would leave zero unblocked exterior segments >=1365mm, the fallback MUST trigger.

A helper `_would_block_all_windows(host, wall_name, building_rect) -> bool` determines this by checking whether the parent room has any exterior wall on a side OTHER than `wall_name`.

#### Fallback behavior

When fallback triggers:

1. Expand candidates to include long-side walls (perpendicular to the original short-side candidates)
2. Filter to **interior** long-side walls only (exclude exterior long sides)
3. Among interior long-side candidates, prefer walls that don't block doors (same `_cl_blocks_door` scoring)
4. Place CL with **partial span**: `span_mm = ceil(target_area / depth_mm)` rounded up to 455mm grid, NOT the full wall length
5. Anchor the CL at the corner where the long wall meets an interior edge (to keep it away from the exterior window wall)

#### Updated scoring

The combined scoring for all candidates (short + fallback long) becomes:

```
(blocks_door, kills_all_windows, is_exterior)
```

This ensures: avoid door blocking > preserve windows > prefer interior.

#### Modified `_place_closet_on_wall()`

The function gains an optional `span_mm` parameter. When placing on a long wall via fallback, `span_mm` is calculated from the target area rather than using the full short side.

#### Scenario: CL fallback to long-side interior wall

- **GIVEN** Bedroom 4 rect (0, 3640, 4550, 3640) mm with building boundary (0, 0, 6370, 12740)
- **AND** short side = 3640mm, candidates = [left, right]
- **AND** left wall (x=0) is the ONLY exterior wall
- **AND** right wall (x=4550) has a hall door
- **AND** CL target area = 1,620,000 mm2 (1.0 tatami), depth = 910mm
- **WHEN** closet placement detects that left would block all windows
- **THEN** fallback to long-side candidates: [top, bottom]
- **AND** top wall (y=3640) is interior (Bedroom 3 above) -> viable
- **AND** CL span = ceil(1,620,000 / 910) = 1820mm (rounded to grid)
- **AND** CL rect = (0, 3640, 1820, 910) -- partial top wall, anchored at left corner
- **AND** left exterior wall (3640mm) remains fully unblocked -> windows preserved

#### Scenario: Short-side placement is fine — no fallback needed

- **GIVEN** a bedroom with two exterior walls (left and bottom)
- **AND** CL short-side candidate is left (exterior)
- **AND** bottom wall is also exterior -> room has other window segments
- **WHEN** closet placement evaluates the left wall
- **THEN** `_would_block_all_windows` returns False (bottom exterior remains)
- **AND** CL is placed on left wall as before — no fallback needed

#### Scenario: All long-side walls are exterior — edge case

- **GIVEN** a bedroom with only one interior wall (the door side, which is a short side)
- **AND** all other walls are exterior
- **WHEN** fallback triggers because short-side placement kills windows
- **AND** long-side candidates are all exterior
- **THEN** pick the long-side wall with the lowest `(blocks_door, is_exterior)` score
- **AND** CL goes on a partial exterior long wall — some windows are blocked but not all
