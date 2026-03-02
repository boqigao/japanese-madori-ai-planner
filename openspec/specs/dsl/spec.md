# DSL Specification

## Purpose
Defines how YAML DSL input files are parsed and validated into a `PlanSpec` model. The DSL module is the entry point for all plan specifications and ensures structural correctness before the solver receives input.
## Requirements
### Requirement: YAML Parsing
The system MUST parse a YAML specification file into a `PlanSpec` dataclass.

#### Scenario: Valid spec file
- GIVEN a well-formed YAML file with site, floors, and spaces
- WHEN the DSL parser loads the file
- THEN a `PlanSpec` object is returned with all fields populated

#### Scenario: Missing required fields
- GIVEN a YAML file missing a required field (e.g., `site` or `floors`)
- WHEN the DSL parser loads the file
- THEN a descriptive error is raised indicating the missing field

### Requirement: Grid Alignment Validation
The system MUST validate that all dimensional values in the spec align to the 455mm minor grid.

#### Scenario: Aligned dimensions
- GIVEN a spec with envelope width=9100mm and depth=7280mm
- WHEN the DSL parser validates grid alignment
- THEN validation passes (both values % 455 == 0)

#### Scenario: Misaligned dimensions
- GIVEN a spec with envelope width=9000mm (not divisible by 455)
- WHEN the DSL parser validates grid alignment
- THEN a grid alignment error is raised

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

### Requirement: Stair Specification
The system MUST parse stair definitions including type, dimensions, connects map, and placement constraints. The accepted stair `type` values MUST include `straight`, `L_landing`, and `U_turn`.

#### Scenario: Stair with connects map
- **GIVEN** a stair with type `straight` and a `connects` mapping from floor_id to hall_id
- **WHEN** the DSL parser processes the stair
- **THEN** a `StairSpec` is created with width (mm), floor_height (mm), riser_pref (mm), tread_pref (mm), connects, and placement fields

#### Scenario: U-turn stair is accepted
- **GIVEN** a stair with type `U_turn`, dimensions aligned to 455mm grid, and valid connects mapping
- **WHEN** the DSL parser processes the stair
- **THEN** parsing succeeds and the resulting `StairSpec.type` is `U_turn`

#### Scenario: Unsupported stair type is rejected
- **GIVEN** a stair with type `spiral`
- **WHEN** the DSL parser processes the stair
- **THEN** validation fails with an unsupported stair type error

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

### Requirement: DSL Accepts Washstand and Shower Types

The YAML DSL parser MUST accept `washstand` and `shower` as valid values for the `type` field of space definitions. These types MUST be parsed identically to other wet types (no special fields required beyond standard space fields: id, type, size_constraints, area).

#### Scenario: Spec with washstand type is parsed

- **GIVEN** a spec.yaml containing a space with `type: washstand`
- **WHEN** the DSL parser processes the spec
- **THEN** the space is parsed successfully with type `washstand`

#### Scenario: Spec with shower type is parsed

- **GIVEN** a spec.yaml containing a space with `type: shower`
- **WHEN** the DSL parser processes the spec
- **THEN** the space is parsed successfully with type `shower`

