## ADDED Requirements

### Requirement: Washstand Room Type

The system MUST support a `washstand` room type representing a compact wash area with sink only (no washing machine space). The washstand MUST have a fixed module size of 910×910mm (2×2 cells on the 455mm grid). The washstand MUST be classified as a wet space and a wet-core space, participating in wet-cluster grouping and hall adjacency constraints.

#### Scenario: Washstand appears in wet module sizes

- **GIVEN** the constant `WET_MODULE_SIZES_MM`
- **WHEN** the type `washstand` is looked up
- **THEN** the returned size is `(910, 910)` in mm

#### Scenario: Washstand is a wet space type

- **GIVEN** the constant `WET_SPACE_TYPES`
- **WHEN** checked for membership
- **THEN** `washstand` is a member of both `WET_SPACE_TYPES` and `WET_CORE_SPACE_TYPES`

#### Scenario: Washstand participates in wet cluster

- **GIVEN** a floor with spaces `washstand`, `shower`, and `hall`
- **WHEN** the solver builds wet cluster constraints
- **THEN** `washstand` and `shower` MUST form a connected cluster adjacent to `hall`

### Requirement: Shower Room Type

The system MUST support a `shower` room type representing a shower-only room without bathtub. The shower MUST have a fixed module size of 910×1365mm (2×3 cells on the 455mm grid). The shower MUST be classified as a wet space and a wet-core space, participating in wet-cluster grouping and hall adjacency constraints.

#### Scenario: Shower appears in wet module sizes

- **GIVEN** the constant `WET_MODULE_SIZES_MM`
- **WHEN** the type `shower` is looked up
- **THEN** the returned size is `(910, 1365)` in mm

#### Scenario: Shower is a wet space type

- **GIVEN** the constant `WET_SPACE_TYPES`
- **WHEN** checked for membership
- **THEN** `shower` is a member of both `WET_SPACE_TYPES` and `WET_CORE_SPACE_TYPES`

### Requirement: Shower-Washstand Adjacency

The solver MUST enforce that each `shower` space touches at least one `washstand` space on the same floor. This is analogous to the existing `bath`↔`washroom` adjacency constraint. A floor that defines a `shower` without any `washstand` MUST raise a `ValueError` at solve time.

#### Scenario: Shower must touch washstand

- **GIVEN** a floor with one `shower` and one `washstand`
- **WHEN** the solver applies wet adjacency constraints
- **THEN** the `shower` rectangle MUST share a positive-length edge with the `washstand` rectangle

#### Scenario: Shower without washstand is rejected

- **GIVEN** a floor with one `shower` but no `washstand`
- **WHEN** the solver assembles constraints
- **THEN** a `ValueError` is raised indicating shower requires washstand

### Requirement: Shower Door Suppression

The system MUST suppress door placement on `shower`↔non-`washstand` edges. A door MUST only be placed between `shower` and `washstand` (parallel to existing `bath`↔`washroom` door logic).

#### Scenario: Door placed between shower and washstand

- **GIVEN** a solved floor where `shower` and `washstand` share an edge
- **WHEN** door placement is evaluated
- **THEN** a door is placed on the shared edge

#### Scenario: No door between shower and hall

- **GIVEN** a solved floor where `shower` and `hall` share an edge
- **WHEN** door placement is evaluated
- **THEN** no door is placed on the shared edge

### Requirement: Washstand Renderer Fixture

The renderer MUST draw a sink symbol inside `washstand` rooms. The sink MUST be a single basin without washing machine symbol (visually distinct from full-size `washroom`).

#### Scenario: Washstand displays sink fixture

- **GIVEN** a solved floor with a `washstand` room at position (x, y) with dimensions 910×910mm
- **WHEN** the renderer draws fixtures
- **THEN** a sink symbol is drawn centered within the washstand bounds

### Requirement: Shower Renderer Fixture

The renderer MUST draw a shower head symbol inside `shower` rooms. The symbol MUST NOT include a bathtub (visually distinct from full-size `bath`).

#### Scenario: Shower displays shower head fixture

- **GIVEN** a solved floor with a `shower` room at position (x, y) with dimensions 910×1365mm
- **WHEN** the renderer draws fixtures
- **THEN** a shower head symbol is drawn within the shower bounds, without a bathtub rectangle
