## ADDED Requirements

### Requirement: Major Room Exterior-Touch Feasibility
The system MUST run a deterministic preflight feasibility check for the exterior-touch hard rule. If a floor contains any `bedroom`, `master_bedroom`, or `ldk`, then the floor buildable mask MUST provide envelope-contact opportunity; otherwise preflight MUST fail before solving.

#### Scenario: Buildable mask has no exterior contact and major room exists
- **GIVEN** floor `F2` has only interior buildable rectangles (no shared edge with envelope boundary)
- **AND** `F2` includes `bedroom2` or `ldk`
- **WHEN** preflight runs
- **THEN** preflight reports an error that major-room exterior-touch is impossible on that floor

#### Scenario: Buildable mask touches envelope and major room exists
- **GIVEN** floor `F2` buildable mask shares boundary segments with the envelope
- **AND** `F2` includes `master_bedroom`
- **WHEN** preflight runs
- **THEN** no exterior-touch feasibility error is produced for that floor

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

### Requirement: Compact Wet Module Fit Validation

The preflight MUST validate that `washstand` (910×910mm) and `shower` (910×1365mm) fixed module dimensions fit within the floor envelope, using the same `_check_wet_cluster_fit` logic as existing wet modules. The compact modules MUST be included in wet-core cluster packing checks when present alongside other wet-core modules.

#### Scenario: Washstand fits in envelope

- **GIVEN** a floor with envelope 9100×6370mm and one `washstand` (910×910mm)
- **WHEN** preflight checks wet module fit
- **THEN** no error is reported for the washstand

#### Scenario: Shower and washstand cluster packing

- **GIVEN** a floor with one `washstand` (910×910mm) and one `shower` (910×1365mm)
- **WHEN** preflight checks wet-core cluster connectivity
- **THEN** the two modules are verified as packable in a connected arrangement

### Requirement: Shower-Washstand Topology Validation

The preflight MUST validate that if a floor defines a `shower`, at least one `washstand` exists on the same floor. The preflight MUST also verify that wet-core circulation topology is satisfied for compact wet modules (at least one compact wet-core module has a topology edge to a circulation node).

#### Scenario: Shower without washstand is flagged

- **GIVEN** a floor with a `shower` but no `washstand`
- **WHEN** preflight validates wet topology
- **THEN** an error is reported indicating shower requires washstand on the same floor
