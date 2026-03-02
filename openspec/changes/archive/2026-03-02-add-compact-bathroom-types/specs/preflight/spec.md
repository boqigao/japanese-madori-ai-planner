## ADDED Requirements

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
