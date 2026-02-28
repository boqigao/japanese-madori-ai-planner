## MODIFIED Requirements

### Requirement: 100% Envelope Coverage
The system MUST verify that total indoor space area equals buildable indoor area for each floor, and MUST report indoor-vs-outdoor area breakdowns separately.

#### Scenario: Full indoor buildable coverage
- **GIVEN** a solution where indoor space areas sum to buildable indoor area
- **WHEN** the validator checks coverage
- **THEN** the indoor coverage check passes

#### Scenario: Indoor buildable coverage gap
- **GIVEN** a solution where indoor space areas sum to less than buildable indoor area
- **WHEN** the validator checks coverage
- **THEN** a buildable-coverage gap error is reported

### Requirement: Entry Reachability
The system MUST verify reachability from entry for all indoor spaces using realized topology edges. Outdoor spaces MUST be checked by outdoor-access rules and MUST NOT be used as mandatory transit nodes for indoor BFS reachability.

#### Scenario: Reachable indoor graph with outdoor spaces
- **GIVEN** a solution where indoor topology is physically realized and each indoor space is reachable from entry
- **WHEN** the validator performs BFS from the entry
- **THEN** entry reachability passes regardless of whether outdoor spaces are transit-isolated

#### Scenario: Indoor room unreachable from entry
- **GIVEN** a solution where `bedroom3` has no realized topology path from entry through indoor circulation
- **WHEN** the validator performs BFS
- **THEN** a validation error is reported for unreachable indoor room

## ADDED Requirements

### Requirement: Outdoor Access Validation
The system MUST verify that each outdoor space has at least one realized indoor adjacency edge and one corresponding opening candidate on the shared boundary.

#### Scenario: Outdoor access realized
- **GIVEN** a balcony adjacent to `bedroom2` with positive shared-edge overlap
- **WHEN** the validator checks outdoor access
- **THEN** the balcony access check passes

#### Scenario: Outdoor access missing
- **GIVEN** an outdoor space with no realized indoor touching edge
- **WHEN** the validator checks outdoor access
- **THEN** a validation error is reported for missing indoor-to-outdoor access
