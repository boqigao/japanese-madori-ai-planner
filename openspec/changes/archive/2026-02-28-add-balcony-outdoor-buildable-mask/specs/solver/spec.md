## MODIFIED Requirements

### Requirement: Space Placement
The system MUST create `RectVar` decision variables for each space and place indoor spaces within the floor indoor buildable mask. Outdoor spaces (`balcony`/`veranda`) MUST be placed within floor envelope bounds and MAY occupy regions outside indoor buildable mask.

#### Scenario: Indoor placement constrained by buildable mask
- **GIVEN** a floor with buildable mask narrower than the full envelope
- **WHEN** the solver runs
- **THEN** every indoor space rectangle is placed fully inside buildable mask cells

#### Scenario: Multi-floor plan with shared stair
- **GIVEN** a spec with 2 floors and a stair element
- **WHEN** the solver runs
- **THEN** the stair occupies the same (x, y) position on both floors

### Requirement: 100% Envelope Coverage
The system MUST enforce that the total area of indoor spaces on a floor equals the floor buildable indoor area.

#### Scenario: Full indoor buildable coverage
- **GIVEN** a floor with buildable indoor area of 46,137,000 mm2
- **WHEN** the solver completes
- **THEN** the sum of all indoor space areas on that floor equals 46,137,000 mm2

#### Scenario: Envelope area larger than buildable target
- **GIVEN** a floor with envelope area greater than buildable indoor area
- **WHEN** the solver completes
- **THEN** indoor coverage is satisfied against buildable area instead of full envelope area

### Requirement: Adjacency Constraints
The system MUST enforce adjacency between spaces specified as adjacent in the DSL, including required indoor-to-outdoor access edges.

#### Scenario: Required indoor adjacency
- **GIVEN** spaces A and B with an adjacency requirement
- **WHEN** the solver completes
- **THEN** A and B share an edge with positive overlap length

#### Scenario: Required indoor-to-balcony adjacency
- **GIVEN** topology declares adjacency between `bedroom_2f` and `balcony_2f`
- **WHEN** the solver completes
- **THEN** indoor and outdoor spaces realize a shared edge suitable for an opening
