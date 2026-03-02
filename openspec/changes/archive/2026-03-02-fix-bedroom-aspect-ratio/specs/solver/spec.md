## ADDED Requirements

### Requirement: Bedroom Aspect Ratio Constraint

The solver MUST enforce a hard aspect ratio constraint on `bedroom` and `master_bedroom` spaces such that the ratio of longer side to shorter side does not exceed 9:5 (1.80). Expressed as linear inequalities on cell-unit variables: `5 * w ≤ 9 * h` AND `5 * h ≤ 9 * w`.

#### Scenario: Square bedroom is accepted

- **GIVEN** a bedroom with width 8 cells (3640mm) and height 8 cells (3640mm)
- **WHEN** the solver evaluates the aspect ratio constraint
- **THEN** the constraint is satisfied (ratio 1:1.00, within 1:1.80 limit)

#### Scenario: Standard 6-tatami bedroom is accepted

- **GIVEN** a bedroom with width 6 cells (2730mm) and height 8 cells (3640mm)
- **WHEN** the solver evaluates the aspect ratio constraint
- **THEN** the constraint is satisfied (ratio 1:1.33, within 1:1.80 limit)

#### Scenario: Compact bedroom at boundary is accepted

- **GIVEN** a bedroom with width 5 cells (2275mm) and height 9 cells (4095mm)
- **WHEN** the solver evaluates the aspect ratio constraint
- **THEN** the constraint is satisfied (ratio 1:1.80, at the 1:1.80 limit)

#### Scenario: Elongated bedroom is rejected

- **GIVEN** a bedroom with width 5 cells (2275mm) and height 12 cells (5460mm)
- **WHEN** the solver evaluates the aspect ratio constraint
- **THEN** the constraint is violated (ratio 1:2.40, exceeds 1:1.80 limit) and this configuration is excluded from the solution space
