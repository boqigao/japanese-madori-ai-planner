## MODIFIED Requirements

### Requirement: Wall Extraction
The system MUST extract merged wall segments from solved indoor geometry and stair geometry. Outdoor-only boundaries MUST NOT be treated as interior room partitions for structural diagnostics.

#### Scenario: Indoor boundary extraction
- **GIVEN** a solved floor with indoor rooms and a balcony zone
- **WHEN** `extract_solution_walls` is called
- **THEN** boundaries between indoor spaces and boundaries between indoor occupied cells and exterior produce structural wall candidates

#### Scenario: Outdoor-only boundary exclusion
- **GIVEN** two adjacent outdoor cells within a balcony/veranda region
- **WHEN** walls are extracted
- **THEN** no structural partition wall is created between those outdoor cells

### Requirement: Floor Structure Metrics
The system MUST compute per-floor structural metrics from indoor/bearing wall segments only, excluding outdoor-only perimeter effects that would inflate bearing-length proxies.

#### Scenario: Outdoor strip does not inflate bearing length
- **GIVEN** a floor with a wide balcony strip on one side
- **WHEN** floor metrics are computed
- **THEN** bearing-length metrics are based on indoor structural boundary extraction and are not artificially increased by outdoor-only geometry
