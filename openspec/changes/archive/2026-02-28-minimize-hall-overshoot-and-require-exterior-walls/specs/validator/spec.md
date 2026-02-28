## ADDED Requirements

### Requirement: Major Room Exterior Adjacency
The system MUST verify that every `bedroom`, `master_bedroom`, and `ldk` touches at least one exterior boundary edge in solved geometry. Violation MUST be treated as a validation error.

#### Scenario: Major room touches exterior boundary
- **GIVEN** a solved plan where `master` shares a positive-length edge with the envelope boundary
- **WHEN** validator geometry checks run
- **THEN** `master` passes the major-room exterior adjacency rule

#### Scenario: Major room is interior-only
- **GIVEN** a solved plan where `bedroom3` is surrounded by interior spaces and has no exterior-touch edge
- **WHEN** validator geometry checks run
- **THEN** validator reports an error for missing exterior adjacency on `bedroom3`

#### Scenario: Multi-rect LDK satisfies with one exterior component
- **GIVEN** an `ldk` represented by multiple rectangles in a valid solved floor
- **WHEN** validator geometry checks run
- **THEN** the `ldk` requirement passes if any component touches the exterior boundary
