# Validator Specification

## Purpose
Defines the post-solve validation checks that verify the structural correctness of a generated floor plan. The validator runs only on solved output and produces a `ValidationReport`. Implementation is split across `core.py` (orchestrator), `geometry.py` (spatial checks), `connectivity.py` (graph traversal), `stair.py` (stair alignment), `livability.py` (quality metrics), and `structural.py` (bearing-wall diagnostics).

## Requirements

### Requirement: Space Presence Check
The system MUST verify that all spaces defined in the spec are present in the solution.

#### Scenario: All spaces present
- GIVEN a spec with 5 spaces and a solution with 5 spaces
- WHEN the validator runs
- THEN the space presence check passes

#### Scenario: Missing space
- GIVEN a spec with 5 spaces but a solution with only 4
- WHEN the validator runs
- THEN a validation error is reported for the missing space

### Requirement: Grid Alignment Check
The system MUST verify that all coordinates and dimensions satisfy `value % 455 == 0`.

#### Scenario: Aligned solution
- GIVEN a solution where all values are multiples of 455
- WHEN the validator checks grid alignment
- THEN the check passes

#### Scenario: Misaligned value
- GIVEN a solution with a space at x=500 (not divisible by 455)
- WHEN the validator checks grid alignment
- THEN a grid alignment error is reported

### Requirement: No-Overlap Check
The system MUST verify that no two spaces on the same floor overlap.

#### Scenario: Non-overlapping spaces
- GIVEN a solution with properly separated spaces
- WHEN the validator checks for overlaps
- THEN the no-overlap check passes

### Requirement: 100% Envelope Coverage
The system MUST verify that the total space area equals the envelope area for each floor.

#### Scenario: Full coverage
- GIVEN a solution where space areas sum to the envelope area
- WHEN the validator checks coverage
- THEN the coverage check passes

#### Scenario: Incomplete coverage
- GIVEN a solution where space areas sum to less than the envelope area
- WHEN the validator checks coverage
- THEN a coverage gap error is reported

### Requirement: Entry Exterior Adjacency
The system MUST verify that the entry (genkan) space touches the building boundary.

#### Scenario: Entry on boundary
- GIVEN a solution with an entry space adjacent to the exterior edge
- WHEN the validator checks entry exterior adjacency
- THEN the check passes

### Requirement: Entry Reachability
The system MUST verify that all spaces are reachable from the entry using BFS traversal over adjacency edges.

#### Scenario: Reachable graph
- GIVEN a solution where all spaces are connected via adjacency
- WHEN the validator performs BFS from the entry
- THEN all spaces are reachable

#### Scenario: Isolated space
- GIVEN a solution with a space not connected to any neighbor
- WHEN the validator performs BFS
- THEN the isolated space is reported as unreachable

### Requirement: Stair Projection Alignment
The system MUST verify that stair positions align across floors.

#### Scenario: Aligned stairs
- GIVEN a 2-floor solution with a stair at position (x=1820, y=910) on both floors
- WHEN the validator checks stair alignment
- THEN the stair projection check passes

### Requirement: Stair Portal Positioning
The system MUST verify that stair portals are positioned on interior edges (not on exterior walls) and connect to the configured hall.

#### Scenario: Interior portal
- GIVEN a stair portal edge adjacent to a hall and not on the building boundary
- WHEN the validator checks portal positioning
- THEN the check passes

### Requirement: WC-LDK Non-Adjacency
The system MUST verify that the WC (toilet) is not directly adjacent to the LDK.

#### Scenario: Separated WC and LDK
- GIVEN a solution where WC and LDK have at least a 1-cell gap
- WHEN the validator checks non-adjacency
- THEN the check passes

### Requirement: Livability Checks
The system MUST produce quality warnings for dimensional concerns without failing validation.

#### Scenario: Entry too narrow
- GIVEN a solution where the entry width is below 1365mm
- WHEN the livability checker runs
- THEN a warning is reported about narrow entry

#### Scenario: Small bedroom
- GIVEN a solution where a bedroom is under 6.0 tatami
- WHEN the livability checker runs
- THEN a warning is reported about undersized bedroom

#### Scenario: Hall circulation quality
- GIVEN a solution where hall area per connected room is below threshold
- WHEN the livability checker runs
- THEN a warning about insufficient circulation is reported

### Requirement: Structural Diagnostics
The system MUST produce structural proxy diagnostics as informational findings (warn-only, never invalidates).

#### Scenario: Bearing-wall analysis
- GIVEN a solved plan with extracted wall segments
- WHEN the structural validator runs
- THEN bearing length, wall balance ratio, and vertical continuity metrics are appended to the report

#### Scenario: Vertical transfer warnings
- GIVEN an upper floor with bearing walls that are not supported by lower floor walls
- WHEN the structural validator runs
- THEN vertical transfer requirements are reported as warnings
