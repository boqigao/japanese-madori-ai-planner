## ADDED Requirements

### Requirement: Closet/WIC Topology Validation
Validator MUST verify closet/WIC parent association and access semantics from solved geometry.

#### Scenario: WIC missing access edge is invalid
- **GIVEN** a solved floor where `wic_master` has no realized shared edge to any allowed access space
- **WHEN** validator connectivity checks run
- **THEN** validator reports an error for missing WIC access connectivity

#### Scenario: Closet parent mismatch is invalid
- **GIVEN** solved closet geometry attributed to `bedroom2` but spatially mapped outside its allowed parent zone
- **WHEN** validator geometry/topology checks run
- **THEN** validator reports a closet-parent mismatch error

### Requirement: Privacy-safe Reachability with Closet Semantics
Validator MUST ensure closet/WIC modeling does not silently reintroduce bedroom pass-through reachability violations.

#### Scenario: Bedroom reachable only through another bedroom
- **GIVEN** a solved floor graph where `bedroom3` can be reached only by passing through `bedroom2`
- **WHEN** validator reachability checks run
- **THEN** validator emits an error even if closet/WIC constraints are otherwise satisfied
