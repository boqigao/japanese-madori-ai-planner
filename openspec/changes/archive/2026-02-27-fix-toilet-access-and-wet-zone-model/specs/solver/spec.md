## MODIFIED Requirements

### Requirement: Wet Module Clustering
The system MUST treat wet clustering as two distinct constraints: (1) `bath` MUST be adjacent to at least one `washroom`; (2) all wet spaces on a floor MUST maintain hall-level accessibility. `toilet/wc` MUST NOT be forced to form a single connected component with `washroom/bath` beyond declared topology and hall-access constraints.

#### Scenario: Bath-washroom coupling required
- **GIVEN** a floor containing `bath1` and `wash1`
- **WHEN** the solver completes
- **THEN** `bath1` and at least one washroom share a positive-length edge on the 455mm grid

#### Scenario: Toilet independent from bath-washroom cluster
- **GIVEN** a floor containing `toilet1`, `wash1`, and `bath1`
- **WHEN** the solver completes
- **THEN** `toilet1` is not required by wet-cluster logic to touch `wash1` or `bath1`

#### Scenario: Wet accessibility through hall is preserved
- **GIVEN** wet spaces on a floor with at least one hall
- **WHEN** the solver completes
- **THEN** at least one wet-space-to-hall touching relation is realized

## ADDED Requirements

### Requirement: Toilet Circulation Adjacency Enforcement
The system MUST enforce that each `toilet/wc` realizes at least one circulation adjacency edge declared in topology to `hall`, `entry`, or `stair`, using shared-edge touching in cell space (1 cell = 455mm).

#### Scenario: Declared toilet-hall required edge is realized
- **GIVEN** topology includes `[toilet1, hall1, required]`
- **WHEN** the solver completes
- **THEN** `toilet1` and `hall1` share a positive-length edge

#### Scenario: Missing declared circulation edge makes model infeasible
- **GIVEN** a floor with `toilet1` but no topology edge from toilet to `hall`, `entry`, or `stair`
- **WHEN** toilet circulation adjacency enforcement is applied
- **THEN** the solver reports infeasible or preflight rejects before solve
