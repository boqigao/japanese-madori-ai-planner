## ADDED Requirements

### Requirement: U-turn Stair Validation
The validator MUST validate `U_turn` stair projection alignment and portal connectivity consistency across floors.

#### Scenario: U-turn projection aligned across floors
- **GIVEN** a two-floor solved plan with `U_turn` stairs
- **WHEN** stair validation runs
- **THEN** the validator confirms stair projection and component bounding boxes are aligned in mm across floors

#### Scenario: U-turn portal mismatch is an error
- **GIVEN** a solved plan where `U_turn` stair portal edge/component does not match expected floor-rank mapping
- **WHEN** stair validation runs
- **THEN** validator emits an error describing the portal mismatch

#### Scenario: U-turn hall connection missing is an error
- **GIVEN** a solved plan where the mapped `U_turn` portal does not share a positive-length edge with the declared hall
- **WHEN** stair validation runs
- **THEN** validator emits an error for missing stair-hall portal connectivity
