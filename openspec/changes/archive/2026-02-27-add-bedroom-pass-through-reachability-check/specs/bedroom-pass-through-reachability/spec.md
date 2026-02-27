## ADDED Requirements

### Requirement: Bedroom Reachability Without Bedroom Transit
The preflight system MUST verify that each bedroom-like space (`bedroom`, `master_bedroom`) is reachable from the floor entry using topology traversal where bedroom nodes are terminal targets and MUST NOT be used as intermediate transit nodes.

#### Scenario: Bedrooms reachable via hall on single floor
- **GIVEN** a floor topology where each bedroom has a path from entry through `entry`/`hall`/non-bedroom spaces
- **WHEN** preflight evaluates bedroom reachability
- **THEN** no bedroom-pass-through error is reported

#### Scenario: Bedroom chain requires passing through another bedroom
- **GIVEN** a topology where path to `bedroom_b` from entry is `entry -> hall -> bedroom_a -> bedroom_b`
- **WHEN** preflight evaluates bedroom reachability
- **THEN** preflight reports an error for `bedroom_b` as blocked by bedroom transit

#### Scenario: Multi-floor bedroom reachable through stair and hall
- **GIVEN** a two-floor topology with stair connectivity and a path `entry(F1) -> hall(F1) -> stair -> hall(F2) -> bedroom(F2)`
- **WHEN** preflight evaluates bedroom reachability
- **THEN** preflight accepts the bedroom as reachable without bedroom transit

### Requirement: Bedroom Reachability Diagnostics
The preflight system MUST emit actionable diagnostics for each blocked bedroom, including floor ID, target bedroom ID, and at least one representative topology path fragment demonstrating bedroom transit.

#### Scenario: Deterministic diagnostic content
- **GIVEN** a floor with one blocked bedroom and one valid bedroom
- **WHEN** preflight generates diagnostics
- **THEN** exactly the blocked bedroom is listed with floor-scoped evidence and a remediation hint to connect it to hall/entry/stair-linked circulation
