# Solver Specification

## Purpose
Defines CP-SAT layout solving behavior for room placement, stair integration, topology realization, and objective optimization on the 455mm grid.

## Requirements
### Requirement: Space Placement
The system MUST create `RectVar` decision variables for each space and place indoor spaces within the floor indoor buildable mask. Outdoor spaces (`balcony`/`veranda`) MUST be placed within floor envelope bounds and MAY occupy regions outside indoor buildable mask. In addition, each `bedroom`, `master_bedroom`, and `ldk` MUST realize at least one shared edge segment with the floor exterior boundary.

#### Scenario: Indoor placement constrained by buildable mask
- **GIVEN** a floor with buildable mask narrower than the full envelope
- **WHEN** the solver runs
- **THEN** every indoor space rectangle is placed fully inside buildable mask cells

#### Scenario: Bedroom requires exterior-touch
- **GIVEN** a floor with `bedroom2` defined and all dimensions aligned to the 455mm grid
- **WHEN** the solver completes
- **THEN** `bedroom2` has at least one exterior-touch edge with positive length in mm

#### Scenario: LDK requires exterior-touch
- **GIVEN** a floor with `ldk` that may use one or more rectangles
- **WHEN** the solver completes
- **THEN** at least one `ldk` component touches the envelope boundary with positive overlap length

### Requirement: Bedroom Aspect Ratio Constraint

The solver MUST enforce a hard aspect ratio constraint on `bedroom` and `master_bedroom` spaces such that the ratio of longer side to shorter side does not exceed 9:5 (1.80). Expressed as linear inequalities on cell-unit variables: `5 * w ≤ 9 * h` AND `5 * h ≤ 9 * w`.

#### Scenario: Square bedroom is accepted

- **GIVEN** a bedroom with width 8 cells (3640mm) and height 8 cells (3640mm)
- **WHEN** the solver evaluates the aspect ratio constraint
- **THEN** the constraint is satisfied (ratio 1:1.00, within 1:1.80 limit)

#### Scenario: Standard 6-tatami bedroom is accepted

- **GIVEN** a bedroom with width 6 cells (2730mm) and height 8 cells (3640mm)
- **WHEN** the solver evaluates the aspect ratio constraint
- **THEN** the constraint is satisfied (ratio 1:1.33, within 1:1.80 limit)

#### Scenario: Compact bedroom at boundary is accepted

- **GIVEN** a bedroom with width 5 cells (2275mm) and height 9 cells (4095mm)
- **WHEN** the solver evaluates the aspect ratio constraint
- **THEN** the constraint is satisfied (ratio 1:1.80, at the 1:1.80 limit)

#### Scenario: Elongated bedroom is rejected

- **GIVEN** a bedroom with width 5 cells (2275mm) and height 12 cells (5460mm)
- **WHEN** the solver evaluates the aspect ratio constraint
- **THEN** the constraint is violated (ratio 1:2.40, exceeds 1:1.80 limit) and this configuration is excluded from the solution space

### Requirement: Soft Objective Minimization
The system MUST minimize a combined objective covering area targets, alignment, compactness, and orientation preference. Hall area overshoot above target MUST receive strong penalty so circulation expansion is disfavored. In addition, orientation preference terms MUST use `site.north` to infer north/south envelope edges, then prefer `ldk`/`bedroom`/`master_bedroom` touching the inferred south edge and prefer `washroom`/`bath`/`toilet`/`wc`/`storage` touching the inferred north edge.

#### Scenario: Hall overshoot is strongly penalized
- **GIVEN** a feasible floor where hall can expand while keeping all hard constraints satisfied
- **WHEN** the solver optimizes objective terms
- **THEN** hall area above target incurs high overshoot cost and the selected plan favors smaller hall area in grid cells

#### Scenario: South preference for major rooms
- **GIVEN** `site.north=top` and a feasible floor containing `ldk` and `bedroom2`
- **WHEN** solver objective penalties are evaluated
- **THEN** plans where `ldk`/`bedroom2` touch the bottom envelope edge (south) receive lower orientation penalty than plans without south touch

#### Scenario: North preference for service rooms
- **GIVEN** `site.north=top` and a feasible floor containing `wash1`, `bath1`, and `storage1`
- **WHEN** solver objective penalties are evaluated
- **THEN** plans where those rooms touch the top envelope edge (north) receive lower orientation penalty than plans without north touch

#### Scenario: Orientation remains soft under tight topology
- **GIVEN** a constrained floor where adjacency and 455mm-grid-aligned packing make full orientation preference impossible
- **WHEN** the solver optimizes
- **THEN** the solver MAY accept unmet orientation preference by paying configured soft penalty while still satisfying all hard constraints

### Requirement: U-turn Stair Footprint Modeling
The solver MUST model `U_turn` stairs as deterministic 455mm-grid-aligned rectangular components in cell units and include them in normal packing constraints.

#### Scenario: U-turn footprint components are generated
- **GIVEN** a `U_turn` stair spec with width and riser/tread preferences in mm
- **WHEN** stair footprint variables are created
- **THEN** the solver creates component rectangles (two flights and one landing) whose coordinates and dimensions are aligned to 455mm cells

#### Scenario: U-turn footprint participates in no-overlap
- **GIVEN** a floor with indoor rooms and one `U_turn` stair
- **WHEN** floor packing constraints are built
- **THEN** all `U_turn` component intervals are included in `NoOverlap2D` and cannot overlap room rectangles

### Requirement: U-turn Stair Connection Constraints
The solver MUST enforce hall connectivity for `U_turn` stairs through a deterministic portal component and edge per floor rank.

#### Scenario: Stair portal touches connected hall
- **GIVEN** a `U_turn` stair connects map `{"F1": "hall1", "F2": "hall2"}`
- **WHEN** stair connection constraints are applied
- **THEN** each floor's mapped portal edge has positive shared boundary with its connected hall rectangles

#### Scenario: Missing connected hall is rejected
- **GIVEN** a `U_turn` stair connect entry pointing to a missing hall id
- **WHEN** solver constraints are assembled
- **THEN** the solver setup fails with a descriptive missing hall reference error

### Requirement: Shower-Washstand Adjacency Constraint

The solver MUST enforce that each `shower` space touches at least one `washstand` space on the same floor, using the same touching-constraint mechanism as the existing `bath`↔`washroom` adjacency. This constraint MUST be added in `add_bath_wash_adjacency_constraints` (or an analogous function) alongside the existing bath-washroom logic.

#### Scenario: Single shower touches single washstand

- **GIVEN** a floor with one `shower` (id=`shower2`) and one `washstand` (id=`wash2`)
- **WHEN** the solver builds adjacency constraints
- **THEN** a `touching_constraint` is created between `shower2` and `wash2` and enforced via `AddBoolOr`

#### Scenario: Floor with shower but no washstand raises error

- **GIVEN** a floor defining `shower` spaces but no `washstand` spaces
- **WHEN** the solver assembles wet adjacency constraints
- **THEN** a `ValueError` is raised with message indicating shower requires washstand on the same floor
