## ADDED Requirements

### Requirement: Closet/WIC Geometry Constraints
The solver MUST place closet/WIC geometry with deterministic parent-association rules while preserving 455mm cell alignment and full-floor coverage constraints.

#### Scenario: Closet geometry stays within parent room envelope
- **GIVEN** a bedroom with a requested built-in closet zone
- **WHEN** CP-SAT variables are solved
- **THEN** closet geometry is placed as a parent-associated zone and each coordinate/dimension maps to integer 455mm cells

#### Scenario: WIC geometry is solved with parent association
- **GIVEN** `master` with associated `wic_master`
- **WHEN** solver builds and optimizes constraints
- **THEN** `wic_master` is placed with parent-association constraints and does not collapse into generic storage behavior

### Requirement: WIC Access and Privacy Constraints
The solver MUST enforce explicit access semantics for walk-in closets and MUST NOT require bedroom-to-bedroom transit as an artifact of closet placement.

#### Scenario: WIC access path exists
- **GIVEN** a solved floor with `wic_bedroom2`
- **WHEN** adjacency constraints are evaluated
- **THEN** the `wic` has at least one realized access edge to its allowed source room(s)

#### Scenario: Closet placement avoids forced bedroom pass-through
- **GIVEN** two bedrooms and one hall on a floor
- **WHEN** solver selects final topology realization
- **THEN** closet/WIC placement does not create a model where one bedroom is reachable only through another bedroom
