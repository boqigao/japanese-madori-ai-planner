## ADDED Requirements

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
