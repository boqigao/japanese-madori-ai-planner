## ADDED Requirements

### Requirement: Closet Wall Feasibility Warning

The system MUST emit a warning during preflight if a room with an embedded closet has a topology configuration where all non-exterior adjacency edges require doors. This is a heuristic check based on topology (before room positions are known) that flags potentially problematic configurations.

#### Scenario: Room with sufficient free-wall potential

- **GIVEN** floor F2 has `bedroom2` with an embedded closet
- **AND** `bedroom2` has 2 topology adjacency edges (to `hall` and `bedroom3`)
- **AND** `bedroom3` adjacency does not produce a door (bedroom-to-bedroom)
- **WHEN** preflight runs
- **THEN** no closet wall feasibility warning is emitted for `bedroom2`

#### Scenario: Room with all door-eligible neighbors

- **GIVEN** floor F2 has `bedroom2` with an embedded closet
- **AND** `bedroom2` has 3 topology adjacency edges all to door-eligible types (hall, ldk, washroom)
- **AND** `bedroom2` type is in `WINDOW_SPACE_TYPES` (eligible for exterior windows)
- **WHEN** preflight runs
- **THEN** preflight emits a warning: closet placement on `bedroom2` may conflict with doors/windows
