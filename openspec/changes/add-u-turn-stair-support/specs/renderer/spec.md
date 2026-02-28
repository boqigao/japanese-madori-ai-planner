## MODIFIED Requirements

### Requirement: Stair Visualization
The system MUST draw stair components with tread step lines, void hatching, guardrails, and connection openings for supported stair types (`straight`, `L_landing`, `U_turn`).

#### Scenario: Straight stair
- **GIVEN** a straight stair with calculated treads
- **WHEN** the renderer draws the stair
- **THEN** component outlines, evenly spaced tread lines, and guardrails are drawn

#### Scenario: L-landing stair
- **GIVEN** an L-landing stair with two flights and a landing
- **WHEN** the renderer draws the stair
- **THEN** both flights with tread lines, the landing, and connection openings are drawn

#### Scenario: U-turn stair
- **GIVEN** a U-turn stair with two opposite-direction flights and a landing
- **WHEN** the renderer draws the stair
- **THEN** both flights are rendered with directional tread lines, the landing is rendered as a component, and guardrail/opening indicators follow solved portal semantics

#### Scenario: Void floor (upper floor stair)
- **GIVEN** an upper floor with a stair void
- **WHEN** the renderer draws the void
- **THEN** cross-hatching and guardrail lines indicate the opening
