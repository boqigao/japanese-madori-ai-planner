## MODIFIED Requirements

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
