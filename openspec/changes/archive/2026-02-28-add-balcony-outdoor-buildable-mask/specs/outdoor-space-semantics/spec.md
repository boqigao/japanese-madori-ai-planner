## ADDED Requirements

### Requirement: Outdoor Space Classification
The system MUST classify spaces of type `balcony` and `veranda` as outdoor spaces, distinct from indoor circulation/room spaces.

#### Scenario: Balcony is parsed as outdoor
- **GIVEN** a floor with a space `balcony_2f` of type `balcony`
- **WHEN** the plan is parsed and solved
- **THEN** `balcony_2f` is tagged as `outdoor` in solution and report outputs

#### Scenario: Indoor room is not reclassified
- **GIVEN** a floor with a space `bedroom_2f` of type `bedroom`
- **WHEN** the plan is parsed and solved
- **THEN** `bedroom_2f` remains tagged as `indoor`

### Requirement: Outdoor Access Semantics
The system MUST enforce that every outdoor space has at least one realized access edge from an indoor circulation-capable space, and outdoor spaces MUST NOT be required as transit nodes for indoor reachability.

#### Scenario: Valid indoor-to-balcony access
- **GIVEN** a balcony adjacent to an indoor room with a declared topology edge
- **WHEN** solve and validation complete
- **THEN** the balcony is accepted as accessible from indoor circulation

#### Scenario: Balcony without indoor access is invalid
- **GIVEN** a balcony that has no realized shared-edge contact to any indoor space
- **WHEN** validation runs
- **THEN** validation reports an outdoor access error

### Requirement: Outdoor Area Accounting
The system MUST report indoor and outdoor area totals separately per floor and for the whole plan.

#### Scenario: Area summary includes outdoor subtotal
- **GIVEN** a floor with indoor rooms and one balcony
- **WHEN** report and rendering summaries are generated
- **THEN** the output includes separate indoor area and outdoor area values in sqm and tsubo
