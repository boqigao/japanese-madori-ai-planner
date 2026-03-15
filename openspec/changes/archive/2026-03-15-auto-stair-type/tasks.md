# Tasks: auto-stair-type

## Implementation

- [x] Add `select_stair_type(envelope_width_mm: int) -> str` function in `plan_engine/generator/profiles.py` with width-based thresholds (≤6370→straight, ≤7735→L_landing, else→U_turn)
- [x] Update `plan_engine/generator/emit.py` to call `select_stair_type()` when user has not explicitly specified `--stair`, passing the envelope width from metrics
- [x] Update stair cell estimate lookup in `plan_engine/generator/distribute.py` to use the selected stair type instead of the hardcoded `DEFAULT_STAIR_TYPE`
- [x] Add selected stair type to the feasibility report output in `plan_engine/generator/emit.py`
- [x] Skip auto-selection for single-floor specs (`--floors 1`) in `emit.py`

## Tests

- [x] Add unit test for `select_stair_type()` covering all three thresholds (narrow/medium/wide)
- [x] Add unit test verifying user `--stair` override takes priority over auto-selection
- [x] Add integration test: generate spec for narrow lot (6370mm wide), verify stair type is `straight` in output YAML
