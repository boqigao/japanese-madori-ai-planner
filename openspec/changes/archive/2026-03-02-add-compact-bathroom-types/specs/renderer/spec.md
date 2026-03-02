## ADDED Requirements

### Requirement: Washstand Fixture Drawing

The renderer MUST draw a sink fixture inside `washstand` rooms. The sink MUST be a simple basin symbol (rectangular or oval) centered in the room, without a washing machine symbol. The sink dimensions MUST scale proportionally to the room dimensions (similar to existing washroom sink scaling but without the laundry area).

#### Scenario: Washstand fixture is drawn

- **GIVEN** a solved floor with space type `washstand` and rect {x, y, w=910, h=910}
- **WHEN** the renderer iterates fixture drawing in `fixtures.py`
- **THEN** a sink symbol is drawn within the washstand bounds at approximately centered position

### Requirement: Shower Fixture Drawing

The renderer MUST draw a shower head fixture inside `shower` rooms. The fixture MUST consist of a shower head symbol (circle with spray lines or similar indicator). The fixture MUST NOT include a bathtub rectangle (visually distinct from `bath` type).

#### Scenario: Shower fixture is drawn

- **GIVEN** a solved floor with space type `shower` and rect {x, y, w=910, h=1365}
- **WHEN** the renderer iterates fixture drawing in `fixtures.py`
- **THEN** a shower head symbol is drawn within the shower bounds, and no bathtub rectangle is present
