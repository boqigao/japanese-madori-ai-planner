## ADDED Requirements

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
