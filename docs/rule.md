# Rule Reference (spec.yaml)

This document summarizes the rules that are actually enforced in code today: DSL parsing, solver constraints, validator checks, and practical spec-writing guidance.

## 1. DSL Input Hard Rules

- Units must be `mm`.
- Grid is fixed to `minor=455`, `major=910`.
- `site.envelope` supports rectangle only; `width/depth` must be multiples of `455`.
- `size_constraints.min_width` and stair `width/placement(x,y)` must be multiples of `455`.
- Supported stair types: `straight`, `L_landing`.
- `shape.allow` must be a non-empty list.
- Only `ldk` and `hall` can use `L2` in the current stage.
- `L2` is effective only when `shape.allow` is `["L2"]`; if `rect` is also present, current logic falls back to a single rectangle.

## 2. Solver Hard Constraints

- Every space must have positive size and stay inside the envelope.
- Per-floor `NoOverlap2D`: no overlap between any spaces/stair components.
- Per-floor `100% coverage`: `sum(space areas + stair areas) == envelope area`.
- Every pair in `topology.adjacency` must physically touch (shared edge with positive length).
- `entry` must touch an exterior boundary.
- `entry` has a hard area cap of `2.5 jo` (about 4.15 m2, grid-discretized).
- Fixed wet-module sizes:
  - `toilet/wc = 910x1820`
  - `washroom = 1820x1820`
  - `bath = 1820x1820`
- `bath` must be adjacent to at least one `washroom` (hard constraint).
- Wet cluster constraints: wet spaces must form a connected cluster and at least one wet space must touch a hall.
- `wc/toilet` and `ldk` are forced non-adjacent (at least one cell gap).
- Hall width cap: short side `<= 1820`.
- Component count cap (hardcoded): `ldk <= 2`, `hall <= 4`.
- Stair constraints:
  - Shared stair projection across floors (same stair `id`).
  - Floors in `connects` must contain the referenced hall, and hall must touch the required stair portal edge.
  - Stair portal edge cannot lie on exterior boundary.

## 3. Solver Soft Objectives

- Minimize area target deviation (shortfall/overshoot).
- Prefer major-grid alignment for major rooms (`ldk/bedroom/master_bedroom`).
- Penalize extreme aspect ratios.
- Penalize floor compactness spans.
- Penalize hall area to avoid hallway domination.

## 4. Validator Errors and Warnings

### Errors (invalid solution)
- Missing/unexpected spaces, empty geometry, non-positive dimensions.
- Any coordinate/size not aligned to 455 grid.
- Out-of-envelope, overlaps, or non-100% coverage.
- Missing ground-floor `entry`, or any `entry` not touching exterior.
- Any primary space unreachable from `entry` (non-wet spaces + stair).
- Direct `wc/toilet` to `ldk` adjacency.
- Stair cross-floor projection mismatch, portal mismatch, non-unique portal segment, or portal width < 1 minor cell.
- `bath` exists without `washroom`, or `bath` not adjacent to any `washroom`.

### Warnings (valid but should be reviewed)
- Area overshoot beyond limits (typically >1.3x target; hall >1.5x).
- `entry` short side < 1365.
- Bedroom short side < 2730.
- Secondary bedroom area > master bedroom area.
- Stair comfort checks: riser outside 140-230, tread < 210, landing < 910, or floor-height closure delta > 2mm.

## 5. spec.yaml Authoring Tips

- For F1, start with: `entry + hall + ldk + toilet + washroom + bath + stair`.
- Explicitly include `bath-washroom` adjacency, for example `[wash1, bath1]`.
- Keep hall flexible with `L2` and `rect_components_max: 3~4`.
- Set explicit bedroom `min_width` (`1820` or `2275`) to avoid narrow rooms.
- Keep `entry.target_tatami` in `1.5~2.5`; values above `2.5` will be clamped by hard constraints.
- If infeasible, relax room targets / bedroom minimum widths / F2 adjacency density first, before changing wet/stair core rules.
