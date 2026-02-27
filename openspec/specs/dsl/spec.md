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
The system MUST parse site envelope dimensions (width, depth) and orientation (north direction).

#### Scenario: Rectangular envelope
- GIVEN a spec with envelope type "rect", width 9100, depth 7280, north "top"
- WHEN the DSL parser processes the site section
- THEN a `SiteSpec` with `EnvelopeSpec` is created with the correct values

### Requirement: Space Definitions
The system MUST parse per-floor space definitions including area constraints, shape allowances, and adjacency requirements.

#### Scenario: Space with area target
- GIVEN a space defined with min_tatami=4.5 and target_tatami=6.0
- WHEN the DSL parser processes the space
- THEN `AreaConstraint` is created with the specified tatami values

#### Scenario: L-shaped room allowance
- GIVEN a space (e.g., LDK or hall) with shape allow=["rect", "L2"]
- WHEN the DSL parser processes the space
- THEN `ShapeSpec` permits both rectangular and L-shaped layouts

### Requirement: Stair Specification
The system MUST parse stair definitions including type, dimensions, connects map, and placement constraints.

#### Scenario: Stair with connects map
- GIVEN a stair with type "straight", connects mapping floor_id to hall_id
- WHEN the DSL parser processes the stair
- THEN a `StairSpec` is created with width, floor_height, riser_pref, tread_pref, connects, and placement fields

### Requirement: Topology Definition
The system MUST parse adjacency relationships between spaces on each floor.

#### Scenario: Adjacency edges
- GIVEN a topology section with edges [["hall_1f", "ldk"], ["hall_1f", "entry"]]
- WHEN the DSL parser processes the topology
- THEN adjacency constraints are created for the specified space pairs
