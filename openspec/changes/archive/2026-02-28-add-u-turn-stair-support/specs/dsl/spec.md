## MODIFIED Requirements

### Requirement: Stair Specification
The system MUST parse stair definitions including type, dimensions, connects map, and placement constraints. The accepted stair `type` values MUST include `straight`, `L_landing`, and `U_turn`.

#### Scenario: Stair with connects map
- **GIVEN** a stair with type `straight` and a `connects` mapping from floor_id to hall_id
- **WHEN** the DSL parser processes the stair
- **THEN** a `StairSpec` is created with width (mm), floor_height (mm), riser_pref (mm), tread_pref (mm), connects, and placement fields

#### Scenario: U-turn stair is accepted
- **GIVEN** a stair with type `U_turn`, dimensions aligned to 455mm grid, and valid connects mapping
- **WHEN** the DSL parser processes the stair
- **THEN** parsing succeeds and the resulting `StairSpec.type` is `U_turn`

#### Scenario: Unsupported stair type is rejected
- **GIVEN** a stair with type `spiral`
- **WHEN** the DSL parser processes the stair
- **THEN** validation fails with an unsupported stair type error
