## MODIFIED Requirements

### Requirement: Window Symbols

The system MUST draw window symbols on exterior edges of eligible room types. Exterior segments occupied by embedded closets or entry doors MUST be subtracted from candidate segments before window placement. When a blocked segment partially overlaps a candidate exterior segment, the candidate MUST be split into unblocked sub-segments. Window count and position are determined independently on each sub-segment using the standard thresholds (≥3600mm → 2 windows, ≥1365mm → 1 window, <1365mm → skip).

#### Scenario: Partial exterior blockage — subtraction reduces window count

- **GIVEN** a bedroom rect (5460, 0, 3640, 3185) with exterior north wall segment (5460, 0) → (9100, 0), length 3640mm
- **AND** CL rect (8190, 0, 910, 3185) blocks the north edge sub-segment (8190, 0) → (9100, 0)
- **WHEN** the renderer subtracts blocked segments from the candidate
- **THEN** the remaining sub-segment is (5460, 0) → (8190, 0), length 2730mm
- **AND** 1 window is drawn (centered, since 2730mm < 3600mm threshold)
- **AND** no window appears in the blocked (8190, 0) → (9100, 0) range

#### Scenario: Full exterior blockage — no window

- **GIVEN** a bedroom rect (6370, 0, 2730, 5460) with CL rect (6370, 0, 2730, 910) blocking the entire north edge (6370, 0) → (9100, 0)
- **WHEN** the renderer subtracts blocked segments from the north wall candidate (6370, 0) → (9100, 0)
- **THEN** subtraction produces an empty list (blocked segment equals candidate)
- **AND** no window is drawn on the north edge

#### Scenario: No blockage — unchanged

- **GIVEN** a bedroom with exterior south wall and no CL or entry door on that wall
- **WHEN** the renderer processes window candidates
- **THEN** the full south wall segment is retained and windows are placed normally

#### Scenario: Multiple blocked segments on one wall

- **GIVEN** an exterior wall segment (0, 0) → (9100, 0), length 9100mm
- **AND** two blocked sub-segments: (0, 0) → (910, 0) and (8190, 0) → (9100, 0)
- **WHEN** the renderer subtracts both blocked segments
- **THEN** the remaining sub-segment is (910, 0) → (8190, 0), length 7280mm
- **AND** 2 windows are drawn on the remaining sub-segment

#### Scenario: Blocked segment leaves remainder too short for window

- **GIVEN** an exterior wall segment (0, 0) → (2730, 0), length 2730mm
- **AND** CL blocks (0, 0) → (1820, 0)
- **WHEN** the renderer subtracts the blocked segment
- **THEN** the remaining sub-segment is (1820, 0) → (2730, 0), length 910mm
- **AND** no window is drawn (910mm < 1365mm minimum)
