## ADDED Requirements

### Requirement: Distinct Closet Taxonomy
The system MUST support three distinct storage semantics: `storage` (independent room), `closet` (built-in zone inside a parent room), and `wic` (walk-in closet zone associated with a parent room).

#### Scenario: Closet is modeled as parent-room built-in zone
- **GIVEN** a floor spec containing `bedroom1` with `closet` requirement
- **WHEN** the plan is parsed and solved
- **THEN** the resulting closet geometry is associated to `bedroom1` and is not treated as an independent room in topology

#### Scenario: WIC remains enterable and associated
- **GIVEN** a floor spec containing `master` and `wic_master`
- **WHEN** the plan is parsed and solved
- **THEN** `wic_master` is associated with `master` and has a valid access edge while keeping 455mm-grid alignment

### Requirement: Closet/WIC Access Semantics
The system MUST preserve circulation semantics so closet/WIC access is explicit and does not imply illegal bedroom-to-bedroom traversal.

#### Scenario: WIC access must be explicit in topology
- **GIVEN** a `wic` zone attached to `bedroom2`
- **WHEN** topology and validation run
- **THEN** the plan includes at least one explicit access edge for the `wic` and reports an error when missing

#### Scenario: Bedroom privacy remains intact
- **GIVEN** two adjacent bedrooms each with closet zones
- **WHEN** door-symbol and topology checks run
- **THEN** no implicit bedroom-to-bedroom access is introduced only because closet zones are adjacent
