# floor-buildable-mask Specification

## Purpose
TBD - created by archiving change add-balcony-outdoor-buildable-mask. Update Purpose after archive.
## Requirements
### Requirement: Floor Buildable Mask Definition
The system MUST allow each floor to define an indoor buildable mask as one or more grid-aligned axis-aligned rectangles in millimeters.

#### Scenario: Valid multi-rectangle buildable mask
- **GIVEN** floor `F2` defines two buildable rectangles with all coordinates and sizes divisible by 455mm
- **WHEN** the DSL and preflight checks run
- **THEN** the buildable mask is accepted and converted to cell-unit regions

#### Scenario: Misaligned buildable mask rectangle
- **GIVEN** a buildable rectangle with width not divisible by 455mm
- **WHEN** the DSL and preflight checks run
- **THEN** a grid-alignment error is reported

### Requirement: Buildable Mask Defaults
The system MUST preserve backward compatibility by defaulting floor buildable mask to the full floor envelope when no buildable mask is declared.

#### Scenario: Legacy spec without buildable field
- **GIVEN** a spec that does not define floor buildable masks
- **WHEN** the parser builds `PlanSpec`
- **THEN** each floor uses full-envelope buildable area by default

### Requirement: Indoor Coverage Target Uses Buildable Mask
The system MUST apply strict indoor 100% utilization to buildable mask area rather than the full envelope area.

#### Scenario: Indoor spaces fill buildable area exactly
- **GIVEN** a floor with envelope area larger than declared buildable area
- **WHEN** solver and validator run
- **THEN** indoor space area equals buildable area, not full envelope area

