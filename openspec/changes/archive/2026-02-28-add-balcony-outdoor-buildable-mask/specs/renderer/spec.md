## MODIFIED Requirements

### Requirement: Space Visualization
The system MUST draw indoor and outdoor spaces with distinct visual semantics. Outdoor spaces (`balcony`/`veranda`) MUST use outdoor styling and remain read-only reflections of solved geometry.

#### Scenario: Balcony styling
- **GIVEN** a floor with `balcony_2f` and indoor rooms
- **WHEN** the renderer draws the floor
- **THEN** balcony is rendered with outdoor-specific fill/hatch style distinct from indoor room colors

### Requirement: Floor Area Summary
The system MUST draw area summaries that separate indoor and outdoor totals per floor and for the whole plan.

#### Scenario: Mixed indoor-outdoor floor summary
- **GIVEN** a floor containing indoor rooms and one balcony
- **WHEN** the renderer draws area summary
- **THEN** the summary displays indoor sqm/tsubo and outdoor sqm/tsubo as separate lines

### Requirement: Door Symbols
The system MUST draw opening symbols on realized shared boundaries for indoor-to-indoor and indoor-to-outdoor access edges where appropriate.

#### Scenario: Indoor-to-balcony opening
- **GIVEN** an indoor room and balcony with realized shared boundary and declared topology edge
- **WHEN** the renderer draws openings
- **THEN** an opening symbol is rendered on the shared indoor-outdoor edge

### Requirement: Legend
The system MUST include legend entries that distinguish indoor room types from outdoor space types.

#### Scenario: Legend with balcony
- **GIVEN** a rendered floor containing a balcony
- **WHEN** legend is generated
- **THEN** legend includes balcony/veranda entry with outdoor style swatch
