# Solver Specification

## Purpose
Defines the constraint-based layout solver that uses Google OR-Tools CP-SAT to generate structurally valid floor plans. The solver creates decision variables for each space, enforces hard constraints, and minimizes a soft objective function.

## Requirements

### Requirement: Space Placement
The system MUST create `RectVar` decision variables for each space and place them within the floor envelope.

#### Scenario: Single-floor plan
- GIVEN a spec with one floor and 5 spaces
- WHEN the solver runs
- THEN each space is assigned x, y, width, height values within the envelope bounds

#### Scenario: Multi-floor plan with shared stair
- GIVEN a spec with 2 floors and a stair element
- WHEN the solver runs
- THEN the stair occupies the same (x, y) position on both floors

### Requirement: No-Overlap Constraint
The system MUST enforce that no two spaces on the same floor overlap.

#### Scenario: Adjacent spaces
- GIVEN two spaces placed on the same floor
- WHEN the solver completes
- THEN the bounding rectangles of the two spaces do not intersect

### Requirement: 100% Envelope Coverage
The system MUST enforce that the total area of all spaces on a floor equals the envelope area.

#### Scenario: Full coverage
- GIVEN a floor with envelope area of 66,430,000 mm²
- WHEN the solver completes
- THEN the sum of all space areas on that floor equals 66,430,000 mm²

### Requirement: Adjacency Constraints
The system MUST enforce adjacency between spaces that are specified as adjacent in the DSL.

#### Scenario: Required adjacency
- GIVEN spaces A and B with an adjacency requirement
- WHEN the solver completes
- THEN A and B share an edge with positive overlap length

### Requirement: Non-Adjacency Constraints
The system MUST enforce separation between spaces that must not be adjacent (e.g., WC and LDK).

#### Scenario: WC-LDK separation
- GIVEN a WC space and an LDK space with a non-adjacency constraint
- WHEN the solver completes
- THEN there is at least a 1-cell (455mm) gap between them

### Requirement: Wet Module Clustering
The system MUST place wet spaces (toilet, washroom, bath) as a connected cluster adjacent to a hall.

#### Scenario: Wet cluster formation
- GIVEN wet spaces (toilet, washroom, bath) on a floor
- WHEN the solver completes
- THEN all wet spaces form a connected group and at least one is adjacent to a hall

### Requirement: Grid Alignment
The system MUST ensure all solver output coordinates and dimensions align to the 455mm minor grid.

#### Scenario: Cell-to-mm conversion
- GIVEN the solver works in cell units (1 cell = 455mm)
- WHEN building the `PlanSolution`
- THEN all mm values satisfy value % 455 == 0

### Requirement: Major Grid Preference
The system SHOULD prefer 910mm major grid alignment for major room types (LDK, bedroom, master_bedroom).

#### Scenario: Major room alignment
- GIVEN a bedroom space
- WHEN the solver optimizes placement
- THEN the solver's soft objective penalizes positions not aligned to the 910mm grid

### Requirement: Soft Objective Minimization
The system SHOULD minimize a combined objective covering area targets, alignment, and compactness.

#### Scenario: Area target optimization
- GIVEN a space with target_tatami=6.0
- WHEN the solver optimizes
- THEN the solver penalizes deviations from the target area in the objective function

### Requirement: Solver Timeout
The system MUST respect the configured solver timeout and return the best solution found within the time limit.

#### Scenario: Timeout reached
- GIVEN a solver timeout of 10 seconds
- WHEN the solver cannot find an optimal solution within 10 seconds
- THEN the best feasible solution found so far is returned
