## ADDED Requirements

### Requirement: DSL Accepts Washstand and Shower Types

The YAML DSL parser MUST accept `washstand` and `shower` as valid values for the `type` field of space definitions. These types MUST be parsed identically to other wet types (no special fields required beyond standard space fields: id, type, size_constraints, area).

#### Scenario: Spec with washstand type is parsed

- **GIVEN** a spec.yaml containing a space with `type: washstand`
- **WHEN** the DSL parser processes the spec
- **THEN** the space is parsed successfully with type `washstand`

#### Scenario: Spec with shower type is parsed

- **GIVEN** a spec.yaml containing a space with `type: shower`
- **WHEN** the DSL parser processes the spec
- **THEN** the space is parsed successfully with type `shower`
