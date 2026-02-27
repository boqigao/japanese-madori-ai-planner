## MODIFIED Requirements

### Requirement: Topology Reachability
The system MUST verify topology reachability per floor from entry via topology edges and stair connectors. Generic disconnected spaces SHALL produce warnings, and bedroom spaces (`bedroom`, `master_bedroom`) that are reachable only through other bedrooms MUST produce preflight errors.

#### Scenario: Disconnected topology graph
- **GIVEN** a floor where some spaces are not connected to the entry via any path of topology edges
- **WHEN** preflight runs
- **THEN** a preflight warning is reported listing unreachable spaces

#### Scenario: Bedroom reachable only through another bedroom
- **GIVEN** a floor where a bedroom path from entry requires another bedroom as an intermediate node
- **WHEN** preflight runs
- **THEN** a preflight error is reported listing the blocked bedroom and bedroom-transit path evidence

#### Scenario: Bedroom reachable through non-bedroom circulation
- **GIVEN** a floor where each bedroom is reachable from entry through hall/entry/stair-connected circulation without bedroom transit
- **WHEN** preflight runs
- **THEN** the bedroom reachability check passes with no pass-through error
