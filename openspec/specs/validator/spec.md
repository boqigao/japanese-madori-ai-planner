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

### Requirement: Orientation Preference Diagnostics
The validator MUST evaluate orientation preference outcomes using solved geometry and `site.north` mapping to inferred north/south envelope edges. The validator MUST emit warnings and diagnostics (not hard errors) when major-room south preference or service-room north preference is not realized.

#### Scenario: Major room misses south preference
- **GIVEN** `site.north=top` and solved `ldk`/`bedroom` geometries that do not touch the bottom envelope edge
- **WHEN** validator livability checks run
- **THEN** validator emits orientation warning(s) identifying floor and room IDs missing south preference

#### Scenario: Service room misses north preference
- **GIVEN** `site.north=right` and solved `washroom`/`bath`/`storage` geometries that do not touch the left envelope edge
- **WHEN** validator livability checks run
- **THEN** validator emits orientation warning(s) identifying floor and room IDs missing north preference

#### Scenario: Fully realized orientation preferences
- **GIVEN** solved geometry where all targeted major rooms touch inferred south and all targeted service rooms touch inferred north
- **WHEN** validator livability checks run
- **THEN** no orientation-preference warning is emitted and diagnostics report successful orientation realization
