# Structural Specification

## Purpose
Defines the structural analysis module that extracts wall segments from solved geometry and computes proxy structural diagnostics. The structural module (`plan_engine/structural/walls.py`) operates on solved `PlanSolution` data and produces `StructureReport` with bearing-wall metrics, vertical continuity analysis, and balance ratios. Results are consumed by the validator (warn-only) and optionally by the renderer (structural wall overlay).
## Requirements
### Requirement: Wall Extraction
The system MUST extract merged wall segments from solved indoor geometry and stair geometry. Outdoor-only boundaries MUST NOT be treated as interior room partitions for structural diagnostics.

#### Scenario: Indoor boundary extraction
- **GIVEN** a solved floor with indoor rooms and a balcony zone
- **WHEN** `extract_solution_walls` is called
- **THEN** boundaries between indoor spaces and boundaries between indoor occupied cells and exterior produce structural wall candidates

#### Scenario: Outdoor-only boundary exclusion
- **GIVEN** two adjacent outdoor cells within a balcony/veranda region
- **WHEN** walls are extracted
- **THEN** no structural partition wall is created between those outdoor cells

### Requirement: Wall Classification
The system MUST classify each wall segment by role: `load_bearing` (exterior walls), `candidate_bearing` (interior walls aligned to major grid), or `partition` (other interior walls).

#### Scenario: Exterior wall role
- GIVEN a wall segment on the building boundary
- WHEN the segment is classified
- THEN it is assigned role `load_bearing`

#### Scenario: Major-grid interior wall
- GIVEN an interior wall segment aligned to the 910mm major grid
- WHEN the segment is classified
- THEN it is assigned role `candidate_bearing`

#### Scenario: Non-aligned interior wall
- GIVEN an interior wall segment not aligned to the 910mm major grid
- WHEN the segment is classified
- THEN it is assigned role `partition`

### Requirement: Floor Structure Metrics
The system MUST compute per-floor structural metrics from indoor/bearing wall segments only, excluding outdoor-only perimeter effects that would inflate bearing-length proxies.

#### Scenario: Outdoor strip does not inflate bearing length
- **GIVEN** a floor with a wide balcony strip on one side
- **WHEN** floor metrics are computed
- **THEN** bearing-length metrics are based on indoor structural boundary extraction and are not artificially increased by outdoor-only geometry

### Requirement: Vertical Continuity Analysis
The system MUST compute continuity metrics between adjacent floors, measuring how much upper-floor bearing wall length is directly supported by lower-floor bearing walls.

#### Scenario: High continuity
- GIVEN an upper floor with 10000mm of vertical bearing walls and a lower floor where 9000mm of that length is directly below bearing walls
- WHEN continuity metrics are computed
- THEN the direct_below_ratio is 0.90

#### Scenario: Low continuity warning
- GIVEN a direct_below_ratio below the target threshold (default 0.50)
- WHEN the structure report is built
- THEN a warning is added about insufficient vertical wall continuity

### Requirement: Vertical Transfer Requirements
The system MUST identify upper-floor bearing wall segments that are not supported by any lower-floor bearing wall and report them as vertical transfer requirements.

#### Scenario: Unsupported segment
- GIVEN an upper-floor bearing wall segment with no corresponding lower-floor bearing wall beneath it
- WHEN the structure report is built
- THEN a `VerticalTransferRequirement` is created with the segment details and unsupported length

### Requirement: Wall Balance Warning
The system MUST warn when the wall balance ratio falls below the target threshold (default 0.50).

#### Scenario: Unbalanced walls
- GIVEN a floor with predominantly vertical bearing walls and very few horizontal ones
- WHEN the structure report is built
- THEN a warning is added about poor wall balance ratio

### Requirement: Structure Report Output
The system MUST produce a `StructureReport` containing floor metrics, continuity metrics, vertical transfer requirements, and collected warnings.

#### Scenario: Complete report
- GIVEN a 2-floor plan with extracted walls
- WHEN `build_structure_report` is called
- THEN a `StructureReport` is returned with metrics for each floor, continuity between F1/F2, transfer requirements, and any warnings

