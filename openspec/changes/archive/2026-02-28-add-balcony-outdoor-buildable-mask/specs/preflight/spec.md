## MODIFIED Requirements

### Requirement: Area Budget Validation
The system MUST verify area budgets per floor using indoor buildable area as the fill target. Indoor minimum/maximum area feasibility MUST be evaluated against buildable area, and outdoor spaces MUST be excluded from indoor fill math.

#### Scenario: Indoor minimum exceeds buildable area
- **GIVEN** a floor where the sum of indoor spaces' minimum areas exceeds the buildable indoor area
- **WHEN** preflight runs
- **THEN** a preflight error is reported with overshoot in cells and sqm

#### Scenario: Indoor maximum cannot fill buildable area
- **GIVEN** a floor where the sum of indoor spaces' maximum areas is less than the buildable indoor area
- **WHEN** preflight runs
- **THEN** a preflight error is reported with gap in cells and sqm and a suggestion to revise indoor targets

### Requirement: Topology Reachability
The system MUST verify topology reachability per floor from entry via topology edges and stair connectors for indoor spaces. Outdoor spaces (`balcony`/`veranda`) MUST have at least one indoor access topology edge and MUST NOT be treated as required transit nodes for indoor reachability.

#### Scenario: Disconnected indoor topology graph
- **GIVEN** a floor where some indoor spaces are not connected to the entry via any path of topology edges
- **WHEN** preflight runs
- **THEN** a preflight warning is reported listing unreachable indoor spaces

#### Scenario: Outdoor space missing indoor access edge
- **GIVEN** a floor with `balcony1` and topology edges that do not connect `balcony1` to any indoor space
- **WHEN** preflight runs
- **THEN** a preflight error is reported that outdoor access topology is missing

#### Scenario: Outdoor space does not participate in indoor transit
- **GIVEN** a floor where all indoor spaces are entry-reachable without traversing `balcony1`
- **WHEN** preflight runs
- **THEN** topology reachability check passes for indoor transit semantics

## ADDED Requirements

### Requirement: Buildable Mask Consistency Check
The system MUST validate that each floor buildable mask is non-empty, lies within envelope bounds, is grid-aligned to 455mm, and has non-overlapping positive-area components.

#### Scenario: Buildable mask component outside envelope
- **GIVEN** a buildable mask rectangle whose boundary exceeds envelope width or depth
- **WHEN** preflight runs
- **THEN** a preflight error is reported identifying out-of-envelope coordinates

#### Scenario: Overlapping buildable mask components
- **GIVEN** two buildable mask rectangles with positive overlap area
- **WHEN** preflight runs
- **THEN** a preflight error is reported for overlapping buildable components
