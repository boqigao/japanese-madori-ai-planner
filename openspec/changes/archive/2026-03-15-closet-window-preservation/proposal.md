## Why

When a bedroom only touches the building envelope on one side, the current closet placement algorithm (`_pick_closet_wall`) may place the CL strip on that exterior wall — blocking all window segments and leaving the bedroom with zero natural light. This happens because the algorithm prioritizes short-side walls and avoids blocking doors, but does not check whether the chosen wall is the room's only exterior wall.

Confirmed case: Bedroom 4 on F2 of a 6370×12740mm lot — CL placed on the left (short) exterior wall, which was the only exterior wall. The bedroom ended up windowless.

## What Changes

- When placing a CL on a short-side wall would block all exterior window segments for the parent room, fall back to placing the CL on a **long-side interior wall** instead
- The CL covers only a **partial segment** of the long wall (sized to match the target area), not the full wall
- The bedroom's usable area becomes L-shaped, but the exterior wall is preserved for windows
- No changes to the solver — this is purely a post-solve closet placement improvement in `solution_builder.py`

## Non-goals

- No solver constraint changes (bedroom exterior touch is already enforced)
- No renderer changes (window placement already handles blocked segments correctly)
- No changes to closet placement when the short-side wall is interior (current behavior is correct in that case)

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `closet-semantics`: Closet wall selection gains a window-preservation fallback — when short-side placement would block all windows, CL is placed on a partial long-side interior wall instead

## Impact

- **Affected code**: `plan_engine/solver/solution_builder.py` — `_pick_closet_wall()`, `_place_closet_on_wall()`, `_fit_closet_strip()`
- **Affected module**: solver (post-solve solution building only; no constraint changes)
- **No breaking changes**: Closets that currently have valid window-preserving placement are unaffected; only edge cases where all windows would be blocked are rerouted
