## ADDED Requirements

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
