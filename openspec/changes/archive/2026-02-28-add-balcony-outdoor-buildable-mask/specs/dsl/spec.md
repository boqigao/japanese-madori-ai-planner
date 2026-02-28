## MODIFIED Requirements

### Requirement: Envelope Specification
The system MUST parse site envelope dimensions (width, depth) and orientation (north direction), and MUST parse optional per-floor indoor buildable masks as grid-aligned rectangle components.

#### Scenario: Rectangular envelope with buildable mask
- **GIVEN** a spec with envelope type "rect", width 9100, depth 7280, north "top", and floor `F2` buildable rectangles
- **WHEN** the DSL parser processes the site and floors sections
- **THEN** a `SiteSpec` with `EnvelopeSpec` and floor-level buildable mask components is created

#### Scenario: Rectangular envelope without buildable mask
- **GIVEN** a spec with envelope values but no floor buildable field
- **WHEN** the DSL parser processes the spec
- **THEN** parsing succeeds with buildable mask defaulting to full envelope

### Requirement: Space Definitions
The system MUST parse per-floor space definitions including area constraints, shape allowances, adjacency requirements, and indoor/outdoor semantics.

#### Scenario: Indoor space with area target
- **GIVEN** a `bedroom` space defined with min_tatami=4.5 and target_tatami=6.0
- **WHEN** the DSL parser processes the space
- **THEN** the space is parsed as indoor with an `AreaConstraint` carrying the specified tatami values

#### Scenario: Outdoor balcony space
- **GIVEN** a space defined with type `balcony`
- **WHEN** the DSL parser processes the space
- **THEN** the space is parsed as outdoor and flagged for outdoor access validation

#### Scenario: L-shaped room allowance
- **GIVEN** a space (e.g., LDK or hall) with shape allow=["rect", "L2"]
- **WHEN** the DSL parser processes the space
- **THEN** `ShapeSpec` permits both rectangular and L-shaped layouts

### Requirement: Topology Definition
The system MUST parse adjacency relationships between spaces on each floor, including indoor-to-outdoor access edges.

#### Scenario: Indoor adjacency edges
- **GIVEN** a topology section with edges [["hall_1f", "ldk"], ["hall_1f", "entry"]]
- **WHEN** the DSL parser processes the topology
- **THEN** adjacency constraints are created for the specified indoor space pairs

#### Scenario: Indoor-to-outdoor access edge
- **GIVEN** a topology section containing edge ["bedroom_2f", "balcony_2f"]
- **WHEN** the DSL parser processes the topology
- **THEN** an access edge between indoor and outdoor spaces is created for solver/validator checks
