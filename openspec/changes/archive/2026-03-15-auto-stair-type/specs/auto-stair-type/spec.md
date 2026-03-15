# Auto Stair Type Selection

## Overview

The spec generator automatically selects the optimal stair type based on lot width when the user does not specify `--stair`.

## Requirements

### R1: Width-based stair type selection

- When `--stair` is not explicitly provided, the generator MUST select stair type based on envelope width:
  - Width ≤ 6370mm (14 cells): `straight`
  - Width 6825–7735mm (15–17 cells): `L_landing`
  - Width ≥ 8190mm (18+ cells): `U_turn`
- The function `select_stair_type(envelope_width_mm: int) -> str` MUST be defined in `profiles.py`

### R2: User override preserved

- When `--stair TYPE` is explicitly provided by the user, the auto-selection MUST NOT apply
- The CLI flag behavior is unchanged

### R3: Stair cell estimate consistency

- Area allocation (`distribute.py`) MUST use the stair cell estimate matching the selected stair type, not the hardcoded default
- `STAIR_CELLS_ESTIMATE` lookup key MUST match the selected type

### R4: Single-floor specs

- For `--floors 1` (hiraya), no stair is emitted, so auto-selection MUST be skipped

### R5: Feasibility report

- The feasibility report printed by the generator SHOULD include the selected stair type so users know what was chosen
