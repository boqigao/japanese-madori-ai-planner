## MODIFIED Requirements

### Requirement: Entry Reachability
The system MUST verify reachability from entry using realized topology edges (declared adjacency that is physically touching in solved geometry). `toilet/wc` spaces MUST be reachable from entry, and paths that require bedroom transit to reach a toilet MUST be reported as errors.

#### Scenario: Reachable graph with toilet access
- **GIVEN** a solution where topology edges are physically realized and each toilet is connected to circulation
- **WHEN** the validator performs BFS from the entry
- **THEN** all required spaces including `toilet/wc` are reachable

#### Scenario: Toilet unreachable from entry
- **GIVEN** a solution where `toilet1` has no realized topology path from entry
- **WHEN** the validator performs BFS
- **THEN** a validation error is reported for unreachable `toilet1`

#### Scenario: Toilet reachable only via bedroom pass-through
- **GIVEN** a solution where every entry-to-toilet path uses another bedroom as an intermediate transit node
- **WHEN** the validator evaluates route quality
- **THEN** a validation error is reported indicating bedroom pass-through toilet circulation

### Requirement: WC-LDK Non-Adjacency
The system MUST verify that the WC (toilet) is not directly adjacent to the LDK by shared-edge contact on the 455mm grid.

#### Scenario: Separated WC and LDK
- **GIVEN** a solution where WC and LDK have at least a 1-cell (455mm) gap
- **WHEN** the validator checks non-adjacency
- **THEN** the check passes

## ADDED Requirements

### Requirement: Toilet Topology Realization
The system MUST verify that each `toilet/wc` has at least one declared topology edge to a circulation node (`hall`, `entry`, or `stair`) and that at least one such edge is physically realized in solved geometry.

#### Scenario: Toilet topology edge is declared and realized
- **GIVEN** topology includes a toilet-circulation edge and corresponding rectangles share a positive-length edge
- **WHEN** the validator checks toilet topology realization
- **THEN** the toilet topology realization check passes

#### Scenario: Toilet topology edge missing
- **GIVEN** a floor with `toilet1` and no topology edge from toilet to `hall`, `entry`, or `stair`
- **WHEN** the validator checks toilet topology realization
- **THEN** a validation error is reported that toilet circulation topology is missing
