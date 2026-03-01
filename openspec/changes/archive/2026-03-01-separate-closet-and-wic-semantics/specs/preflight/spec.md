## ADDED Requirements

### Requirement: Closet/WIC Consistency Preflight
Preflight MUST fail fast when closet/WIC declarations are impossible or contradictory before solver execution.

#### Scenario: Invalid WIC parent assignment
- **GIVEN** a `wic` declaration assigned to a non-bedroom parent where bedroom-only rule is active
- **WHEN** preflight runs
- **THEN** preflight emits an error and solver execution is skipped

#### Scenario: Missing closet host room
- **GIVEN** a floor with closet declaration but no matching host room
- **WHEN** preflight runs
- **THEN** preflight reports a consistency error for that floor

### Requirement: Access Feasibility Preflight
Preflight MUST detect impossible closet/WIC access declarations based on floor topology declarations.

#### Scenario: WIC declared without any candidate access connection
- **GIVEN** a floor where a `wic` is declared but no topology edge can reach it
- **WHEN** preflight evaluates access declarations
- **THEN** preflight fails with a missing-access diagnostic
