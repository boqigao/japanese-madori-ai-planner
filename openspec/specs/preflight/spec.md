# Preflight Specification

## Purpose
Defines the deterministic feasibility checks that run before CP-SAT solving. The preflight module detects spec errors that would certainly cause solve failures (area budget violations, unreachable topology, dimension impossibilities) and provides actionable diagnostics and suggestions. It also produces per-floor numeric summaries (`FloorPreflightStats`) reused for solver-failure reports.
## Requirements
### Requirement: Area Budget Validation
The system MUST verify that per-floor minimum area requirements do not exceed the envelope and maximum area can fill the envelope.

#### Scenario: Minimum area exceeds envelope
- GIVEN a floor where the sum of all spaces' minimum areas exceeds the envelope area
- WHEN preflight runs
- THEN a preflight error is reported with the overshoot in cells and sqm

#### Scenario: Maximum area cannot fill envelope
- GIVEN a floor where the sum of all spaces' maximum areas is less than the envelope area
- WHEN preflight runs
- THEN a preflight error is reported with the gap in cells and sqm, plus a suggestion to add storage or increase targets

### Requirement: Envelope Alignment Check
The system MUST verify that envelope dimensions align to the minor grid (455mm).

#### Scenario: Aligned envelope
- GIVEN an envelope with width=9100 and depth=7280
- WHEN preflight checks alignment
- THEN the check passes (both values % 455 == 0)

### Requirement: Room Minimum Width Check
The system MUST verify that each space's minimum width can fit within the envelope dimensions.

#### Scenario: Room too wide
- GIVEN a space with min_width exceeding the envelope's shorter dimension
- WHEN preflight runs
- THEN a preflight error is reported

### Requirement: Wet Cluster Fit Check
The system MUST verify that the wet core composed of `washroom` and `bath` can physically fit within the envelope on the 455mm grid. `toilet/wc` MUST be validated as an independent fixed-size module and MUST NOT be required to be part of the washroom-bath fit bundle.

#### Scenario: Wet core fits
- **GIVEN** wet core modules (`washroom` 1820x1820mm and `bath` 1820x1820mm) and an envelope of 9100x7280mm
- **WHEN** preflight checks wet core fit
- **THEN** the wet core fit check passes

#### Scenario: Wet core cannot fit
- **GIVEN** wet core modules and an envelope whose width or depth cannot host the required 455mm-grid arrangement
- **WHEN** preflight checks wet core fit
- **THEN** a preflight error is reported describing wet core fit impossibility in mm and cells

#### Scenario: Toilet is validated independently from wet core
- **GIVEN** a floor with `toilet` 910x1820mm and no direct toilet-to-washroom adjacency edge
- **WHEN** preflight checks module fit
- **THEN** preflight does not fail for missing toilet-washroom coupling if toilet size itself is placeable on the 455mm grid

### Requirement: Reference Consistency
The system MUST verify that topology edges and stair connects maps reference existing space IDs.

#### Scenario: Dangling reference
- GIVEN a topology edge referencing a space ID not defined on the floor
- WHEN preflight runs
- THEN a preflight error is reported for the dangling reference

### Requirement: Topology Reachability
The system MUST verify topology reachability per floor from entry via topology edges and stair connectors. Generic disconnected spaces SHALL produce warnings, bedroom spaces (`bedroom`, `master_bedroom`) that are reachable only through other bedrooms MUST produce preflight errors, and `toilet/wc` spaces without circulation topology access MUST produce preflight errors.

#### Scenario: Disconnected topology graph
- **GIVEN** a floor where some spaces are not connected to the entry via any path of topology edges
- **WHEN** preflight runs
- **THEN** a preflight warning is reported listing the unreachable spaces

#### Scenario: Bedroom reachable only through another bedroom
- **GIVEN** a floor where a bedroom path from entry requires another bedroom as an intermediate node
- **WHEN** preflight runs
- **THEN** a preflight error is reported listing the blocked bedroom and bedroom-transit path evidence

#### Scenario: Toilet has no circulation topology edge
- **GIVEN** a floor with `toilet1` and topology edges that do not connect `toilet1` to `hall`, `entry`, or `stair`
- **WHEN** preflight runs
- **THEN** a preflight error is reported that toilet circulation topology is missing

#### Scenario: Bedroom reachable through non-bedroom circulation
- **GIVEN** a floor where each bedroom is reachable from entry through hall/entry/stair-connected circulation without bedroom transit
- **WHEN** preflight runs
- **THEN** the bedroom reachability check passes with no pass-through error

### Requirement: Stair Area Accounting
The system MUST compute the stair footprint area per floor and account for it in the area budget.

#### Scenario: Stair with known footprint
- GIVEN a stair spec with width and floor height
- WHEN preflight calculates the area budget
- THEN the stair footprint area is subtracted from the available envelope area

### Requirement: Hall Fanout Warning
The system MUST warn when a hall has an unusually high number of adjacency connections (fanout >= 8).

#### Scenario: High fanout hall
- GIVEN a hall connected to 8 or more spaces via topology edges
- WHEN preflight runs
- THEN a preflight warning is reported that high fanout makes solving harder

### Requirement: Per-Floor Diagnostics
The system MUST produce per-floor diagnostic lines with envelope cells, min/max area, room count, and hall fanout.

#### Scenario: Diagnostic output
- GIVEN a valid spec with 2 floors
- WHEN preflight completes
- THEN diagnostic lines are produced for each floor showing numeric summaries

### Requirement: Solver Failure Report
The system MUST provide a `build_solver_failure_report` function that creates an actionable report when the solver fails, combining preflight warnings, error message, floor stats, and timeout information.

#### Scenario: Solver timeout failure
- GIVEN a solver that timed out after 90 seconds
- WHEN `build_solver_failure_report` is called with floor stats
- THEN the report includes the error message, per-floor area budget summaries, and suggestions to reduce constraints or increase timeout

