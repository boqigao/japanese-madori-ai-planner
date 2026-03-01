## ADDED Requirements

### Requirement: Closet and WIC Declarations in YAML DSL
The DSL parser MUST accept explicit closet declarations per parent room and explicit `wic` spaces with parent references.

#### Scenario: Closet declaration is parsed
- **GIVEN** a bedroom declaration with closet metadata in YAML
- **WHEN** `dsl.py` parses the floor spec
- **THEN** the resulting `PlanSpec` keeps closet intent as structured data instead of converting it to generic `storage`

#### Scenario: WIC declaration is parsed with parent reference
- **GIVEN** a space type `wic` with `parent_id=master`
- **WHEN** `dsl.py` parses the spec
- **THEN** parsing succeeds and the parent reference is preserved in the model

### Requirement: Closet/WIC Declaration Validation
The DSL parser MUST reject contradictory declarations at parse time.

#### Scenario: Closet declaration references missing parent
- **GIVEN** a closet declaration referencing `bedroom_x` that does not exist on the floor
- **WHEN** DSL validation runs
- **THEN** parsing fails with a descriptive parent-reference error

#### Scenario: Grid-aligned closet dimensions
- **GIVEN** closet dimensions expressed in mm
- **WHEN** grid validation runs
- **THEN** each closet dimension MUST satisfy `value_mm % 455 == 0` or parsing fails
