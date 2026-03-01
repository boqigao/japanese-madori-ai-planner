## ADDED Requirements

### Requirement: Closet/WIC Visual Semantics
Renderer MUST draw closet and WIC semantics distinctly from standalone storage rooms while keeping solved geometry read-only.

#### Scenario: Closet visual appears as built-in bedroom element
- **GIVEN** a solved bedroom with closet semantic data
- **WHEN** renderer creates `F1.svg` and `F1.png`
- **THEN** closet is shown with closet-specific styling/annotation and not labeled as independent `storage`

#### Scenario: WIC visual appears as enterable closet
- **GIVEN** a solved `wic` zone associated with `master`
- **WHEN** renderer draws labels and legend
- **THEN** legend and labels distinguish `wic` from generic storage

### Requirement: Bedroom-to-Bedroom Door Symbol Filtering
Renderer MUST suppress door symbols for bedroom-to-bedroom boundaries.

#### Scenario: Adjacent bedrooms without explicit edge
- **GIVEN** `bedroom2` and `bedroom3` share a wall but no explicit opening edge
- **WHEN** renderer draws door symbols
- **THEN** no bedroom-to-bedroom door symbol is rendered on that wall

#### Scenario: Non-bedroom explicit edge remains visible
- **GIVEN** a topology explicitly allows an opening between two non-bedroom compatible spaces
- **WHEN** renderer draws symbols
- **THEN** the door symbol remains rendered on the realized shared boundary
