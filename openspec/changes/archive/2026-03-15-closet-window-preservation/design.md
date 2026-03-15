## Context

The post-solve closet placement in `solution_builder.py` works in three steps:
1. `_pick_closet_wall()` selects a wall using scoring: `(blocks_door, is_exterior)` — from short-side candidates only
2. `_place_closet_on_wall()` creates the CL rect spanning the **full short side** on the chosen wall
3. `_closet_blocked_exterior_segments()` records which exterior segments are blocked

The problem: when a bedroom has only one exterior wall and that wall is a short-side candidate, the CL covers the entire exterior wall (because CL spans the full short side). The renderer then finds no unblocked exterior segments ≥1365mm → no windows.

Example — Bedroom 4 (w=4550, h=3640):
- Short-side candidates: left, right (since w > h)
- Left (x=0) is exterior, right (x=4550) has the hall door
- Score: left=(0,1) beats right=(1,0) → CL goes on left
- CL rect: 910×3640mm covers the entire left exterior wall → 0 windows

## Goals / Non-Goals

**Goals:**
- Ensure bedrooms always retain at least one exterior wall segment for windows after closet placement
- When short-side placement would kill all windows, fall back to partial long-side interior wall
- Keep the door-avoidance priority intact

**Non-Goals:**
- No solver changes
- No renderer changes
- No changes to rooms that already have valid window placement

## Decisions

### 1. Detection: "would this placement kill all windows?"

After `_pick_closet_wall()` selects the best short-side candidate, check:
1. Would the CL occupy all exterior segments of the parent room?
2. Specifically: does the parent room have any OTHER exterior wall besides the one being covered?

If yes (other exterior walls exist) → proceed normally.
If no (CL would block the ONLY exterior wall) → trigger fallback.

Implementation: add `_would_block_all_windows(host, wall_name, building_rect) -> bool` helper that checks whether the parent room has exterior segments on walls OTHER than `wall_name`.

### 2. Fallback: partial long-side interior wall

When fallback triggers:
1. Expand candidates to include long-side walls (`top`/`bottom` when `w > h`, or `left`/`right` when `h > w`)
2. Filter to interior-only long-side walls (exclude exterior long sides)
3. Among interior long-side candidates, prefer walls that don't block doors (same `_cl_blocks_door` check)
4. Place CL on the selected long wall with **partial span**: `span = ceil(target_area / depth)` instead of `short_side`
5. Anchor the CL at the corner of the long wall (e.g., top-left corner for "top" wall)

### 3. Modified `_place_closet_on_wall()` signature

Add an optional `span_mm` parameter (defaults to `short_side` for backward compatibility):
```python
def _place_closet_on_wall(host, wall_name, depth_mm, span_mm) -> Rect:
```

When placing on a long wall, `span_mm` = `ceil(target_area / depth_mm)` rounded to grid.

### 4. Scoring with three dimensions

Updated scoring for the combined candidate list (short + fallback long):

```python
def wall_score(wall_name):
    kills_windows = 1 if _would_block_all_windows(host, wall_name, building_rect) else 0
    blocks_door = _cl_blocks_door(wall_name)
    is_ext = 1 if is_exterior[wall_name] else 0
    return (kills_windows, blocks_door, is_ext)
```

Priority order: preserve windows > avoid door blocking > prefer interior walls.

This means:
- Interior short-side wall with no door conflict → best (0,0,0)
- Exterior short-side wall that doesn't kill all windows → ok (0,0,1)
- Interior long-side wall (fallback) → (0,0,0) or (0,1,0)
- Short-side wall that kills all windows → worst (1,*,*)

**Alternative considered:** Always try short side first, only fall back on detection. Chosen instead to unify scoring so the logic is a single sort, not a two-phase if/else.

## Risks / Trade-offs

- [L-shaped usable area may look unusual in rendering] → The CL zone is already rendered as a hatched overlay; the bedroom rect itself stays rectangular. Visual impact is minimal.
- [Partial long-side CL may conflict with a door on the long wall] → The `_cl_blocks_door` check handles this; if all long-side interior walls block doors, the algorithm falls back to the least-bad option (short side that kills windows is still better than no placement at all).
