## ADDED Requirements

### Requirement: Wall Classification for Closet Placement

The system MUST classify each wall (top, bottom, left, right) of a parent room into one of: `free` (interior, no door), `exterior` (coincides with building footprint boundary), `door` (shared segment with a topology-adjacent space that receives an interior door), or `both` (exterior and door). Classification MUST use the same door-eligibility rules as the renderer.

#### Scenario: Interior wall with no door-eligible neighbor

- **GIVEN** a bedroom rect at (1820, 910, 3640, 2275) mm and building boundary at (0, 0, 9100, 5460) mm
- **AND** the bedroom's bottom wall (y2=3185) does not coincide with building boundary (y2=5460)
- **AND** no topology-adjacent space with a door-eligible type shares a segment on the bottom wall
- **WHEN** wall classification runs
- **THEN** the bottom wall is classified as `free`

#### Scenario: Exterior wall detection

- **GIVEN** a bedroom rect whose right edge x2 equals the building footprint right edge x2
- **WHEN** wall classification runs
- **THEN** the right wall is classified as `exterior` (or `both` if also a door wall)

#### Scenario: Door wall detection

- **GIVEN** a bedroom with topology adjacency to a hall, and the hall's solved rect shares a positive-length collinear edge on the bedroom's left wall
- **WHEN** wall classification runs
- **THEN** the left wall is classified as `door`

### Requirement: Full-Wall-Span Closet Placement

The system MUST prefer placing an embedded closet as a strip spanning the full length of the chosen wall at the configured depth. The wall selection MUST follow this priority: (1) `free` walls, shorter wall first; (2) `free` walls, longer wall; (3) partial span on non-free walls avoiding conflicts. The closet rect MUST remain 455mm-grid-aligned.

#### Scenario: Closet placed on shortest free wall

- **GIVEN** a bedroom (4550 x 2275 mm) with `free` classification on top wall (4550mm long) and right wall (2275mm long)
- **AND** closet depth is 910mm (2 cells)
- **WHEN** closet placement runs
- **THEN** closet is placed spanning the full right wall: rect (3640, 910, 910, 2275) mm

#### Scenario: Closet placed spanning full wall at requested depth

- **GIVEN** a bedroom (3640 x 2730 mm) with bottom wall classified as `free`
- **AND** closet spec has `depth_mm: 910`
- **WHEN** closet placement runs
- **THEN** closet rect spans full bottom wall width: (x=bedroom.x, y=bedroom.y2-910, w=3640, h=910) mm

#### Scenario: No free wall available falls back to partial span

- **GIVEN** a bedroom where all four walls are classified as `exterior` or `door`
- **WHEN** closet placement runs
- **THEN** closet is placed as a partial strip on the least-conflicting wall, using the area-based sizing logic

#### Scenario: Overshoot cap triggers partial span

- **GIVEN** a bedroom (4550 x 1820 mm) with one `free` wall (the 4550mm long bottom wall)
- **AND** closet target is 1.0 tatami (~1.66 sqm) and depth is 910mm
- **AND** full-span area (4550 x 910 = 4.14 sqm) exceeds 2x target area
- **WHEN** closet placement runs
- **THEN** closet uses partial span on the free wall, sized to approximate target area: rect width = ceil(target_area / depth) grid-aligned

### Requirement: Closet Must Not Overlap Exterior Walls

The system MUST NOT place an embedded closet on a wall classified as `exterior` when at least one `free` or `door` wall is available. This prevents closets from blocking window placement on exterior walls.

#### Scenario: Exterior wall avoided when free wall exists

- **GIVEN** a master bedroom with top wall `exterior` and bottom wall `free`
- **WHEN** closet placement runs
- **THEN** closet is placed on the bottom wall, not the top wall

#### Scenario: Exterior wall used only as last resort

- **GIVEN** a corner bedroom where top and right walls are `exterior`, left wall is `door`, and bottom wall is `door`
- **WHEN** closet placement runs
- **THEN** closet is placed on either the left or bottom `door` wall (not on an `exterior` wall)

### Requirement: Closet Must Not Block Doorways

The system MUST NOT place an embedded closet on a wall classified as `door` when at least one `free` wall is available. When a `door` wall must be used (no `free` walls), the closet MUST be sized and positioned to leave the door segment unobstructed.

#### Scenario: Door wall avoided when free wall exists

- **GIVEN** a bedroom with left wall shared with hall (`door`) and bottom wall interior (`free`)
- **WHEN** closet placement runs
- **THEN** closet is placed on the bottom wall, not the left wall

### Requirement: Shared Door-Eligibility Logic

The door-eligibility function used by closet wall classification MUST be identical to the function used by the renderer for interior door placement. Both MUST import from a single shared location.

#### Scenario: Consistent door prediction

- **GIVEN** two spaces (bedroom, hall) that are topology-adjacent with a shared wall segment
- **WHEN** both the closet wall classifier and the renderer evaluate whether a door should be placed
- **THEN** both produce the same boolean result
