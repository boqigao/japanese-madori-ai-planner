# Validator Specification

## Purpose
Defines the post-solve validation checks that verify the structural correctness of a generated floor plan. The validator runs only on solved output and produces a `ValidationReport`.

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

### Requirement: Entry Reachability
The system MUST verify that the entry space is reachable from the exterior using BFS traversal.

#### Scenario: Reachable entry
- GIVEN a solution with an entry (genkan) space adjacent to the building edge
- WHEN the validator performs BFS from the entry
- THEN all connected spaces are reachable

### Requirement: Stair Projection Alignment
The system MUST verify that stair positions align across floors.

#### Scenario: Aligned stairs
- GIVEN a 2-floor solution with a stair at position (x=1820, y=910) on both floors
- WHEN the validator checks stair alignment
- THEN the stair projection check passes

### Requirement: WC-LDK Non-Adjacency
The system MUST verify that the WC (toilet) is not directly adjacent to the LDK.

#### Scenario: Separated WC and LDK
- GIVEN a solution where WC and LDK have at least a 1-cell gap
- WHEN the validator checks non-adjacency
- THEN the check passes
