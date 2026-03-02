## Context

The engine models wet rooms (toilet, washroom, bath) as fixed-size modules from `WET_MODULE_SIZES_MM`. Currently only full-size washroom (1820×1820mm) and bath (1820×1820mm) exist. Japanese 2F homes commonly use compact sanitary on upper floors: a standalone washstand (洗面台のみ) and shower-only room (シャワールーム). Major manufacturers (TOTO JSV-0808, LIXIL SPB-0808) offer 800×800mm shower units with 920×920mm installation footprint, aligning well with our 910mm major grid.

The wet-module system currently has three grouping constants:
- `WET_SPACE_TYPES` = {toilet, wc, washroom, bath} — all wet types, used for hall adjacency
- `WET_CORE_SPACE_TYPES` = {washroom, bath} — must form connected cluster
- `TOILET_SPACE_TYPES` = {toilet, wc} — separate circulation constraints

Solver constraints in `workflow_wet.py`:
1. `add_bath_wash_adjacency_constraints`: each bath must touch at least one washroom
2. `add_wet_cluster_constraints`: wet core modules form a connected cluster adjacent to hall
3. `add_toilet_circulation_constraints`: each toilet touches a circulation node
4. `add_wet_core_circulation_constraints`: wet core has at least one circulation edge

Renderer in `fixtures.py` draws: toilet bowl, washroom sink+washing machine, bath tub+shower area.

Door suppression in `openings.py`: bath↔non-washroom edges are suppressed (no door between bath and non-washroom).

## Goals / Non-Goals

**Goals:**
- Add `washstand` (910×910mm) and `shower` (910×1365mm) as new room types
- Integrate seamlessly into existing wet-module pipeline (preflight, solver, renderer, validator)
- Maintain backward compatibility — existing specs with washroom/bath remain unchanged

**Non-Goals:**
- Changing existing washroom/bath behavior or sizes
- Combined washstand+shower units (single module) — users compose them via adjacency
- Spec generator — separate future change
- Structural implications — wet rooms don't affect bearing analysis

## Decisions

### Decision 1: Add washstand and shower to existing wet-core grouping

**Choice**: Add both types to `WET_CORE_SPACE_TYPES` and `WET_SPACE_TYPES`.

**Rationale**: The existing cluster constraint ("all wet core modules on a floor form one connected group adjacent to hall") works identically for compact types. If a floor has only washstand+shower, they cluster together. If a floor has washroom+bath+washstand+shower (unusual but valid), they all cluster — which is architecturally correct since wet plumbing should be grouped.

**Alternative considered**: Separate "compact wet core" grouping with independent cluster constraint. Rejected because it adds complexity (new constants, new constraint functions) for no practical benefit — floors almost never mix full and compact wet modules.

### Decision 2: Fixed module sizes on 455mm grid

**Choice**:
- `washstand`: 910×910mm (2×2 cells) — fits a standard compact washbasin unit
- `shower`: 910×1365mm (2×3 cells) — fits standard 0808 shower unit with door clearance

**Rationale**: LIXIL SPB-0808 installation footprint is 920×920mm. On our 455mm grid, 2×2 cells = 910×910mm is the closest fit. The shower room needs slightly more depth for the door swing, so 2×3 cells (910×1365mm) provides adequate clearance.

**Alternative considered**: 910×910mm for shower (matching the 0808 internal dimensions exactly). Rejected because the installation footprint needs door swing space, and 2×3 cells is more realistic for a usable shower room.

### Decision 3: shower↔washstand adjacency (parallel to bath↔washroom)

**Choice**: Add a constraint requiring each `shower` to touch at least one `washstand` on the same floor, mirroring the existing `bath`↔`washroom` constraint.

**Rationale**: Architecturally, a shower room should be adjacent to a wash area (you wash hands after showering, plumbing is shared). This mirrors the existing bath↔washroom pattern exactly.

**Implementation**: Extend `add_bath_wash_adjacency_constraints` to also handle shower↔washstand pairs. The function already loops over bath→washroom pairs; add a second loop for shower→washstand.

### Decision 4: Door suppression for shower

**Choice**: Suppress doors on shower↔non-washstand edges (parallel to bath↔non-washroom).

**Rationale**: The shower opens into the washstand area, not directly into a hallway or bedroom. Same architectural pattern as bath opening into washroom.

**Implementation**: Extend the `should_place_door` function in `constants.py` to handle `shower` the same way as `bath`.

### Decision 5: Renderer fixtures

**Choice**:
- `washstand`: Draw a single sink symbol (centered, smaller than washroom's sink). No washing machine symbol.
- `shower`: Draw a shower head symbol (circular with spray lines). No bathtub.

**Rationale**: Visual distinction from full-size counterparts. Washstand is smaller and simpler (no laundry). Shower is visually distinct from bath (no tub rectangle).

## Risks / Trade-offs

**[Risk] Compact modules may be too small for solver 100% coverage** → In floors where compact wet saves 2.5 tatami, other rooms must grow to fill the gap. This is generally beneficial (bedrooms get more space), but on very tight envelopes it could cause aspect ratio constraint violations. Mitigation: preflight already checks area feasibility.

**[Risk] Existing specs with "washroom"/"bath" on all floors continue working** → Mitigation: no existing constants or constraints are modified, only extended. All changes are additive.

**[Trade-off] Fixed size for shower (2×3 cells) may feel large for some designs** → The 910×910mm (2×2) option would be tighter but impractical for the door. Users who need 2×2 can manually set area constraints in spec.yaml, but the default module size remains 2×3.
