## Why

The spec generator (`gen_spec.py`) currently hardcodes `U_turn` as the default stair type. On narrow lots (width ≤ ~6.5m / 14 cells), the U-turn stair footprint (4×5 cells = 1820×2275mm) is wider than the hall (2 cells = 910mm), creating a geometric blockage that makes multi-bedroom layouts INFEASIBLE. Switching to a straight stair (2×6 cells = 910×2730mm) on narrow lots resolves the issue — confirmed by a successful 5LDK solve on a 6370×12740mm lot.

## What Changes

- Add stair type auto-selection logic to the spec generator based on lot width
- Narrow lots (≤14 cells wide): default to `straight`
- Medium lots (15-17 cells wide): default to `straight` or `L_landing`
- Wide lots (≥18 cells wide): keep `U_turn` as default
- Update `STAIR_CELLS_ESTIMATE` usage to reflect the selected stair type (straight uses fewer cells than U_turn)
- User-specified `--stair TYPE` continues to override auto-selection

## Non-goals

- No changes to the solver, renderer, validator, or structural modules
- No changes to how stair types are handled once they're in `spec.yaml` — only the generator's default selection changes
- No new stair types or stair geometry changes

## Capabilities

### New Capabilities

- `auto-stair-type`: Spec generator auto-selects optimal stair type based on lot width to maximize solvability on narrow lots

### Modified Capabilities

(none — existing specs are unaffected; this is purely a generator-level change)

## Impact

- **Affected code**: `plan_engine/generator/` — primarily `profiles.py` (stair constants/thresholds), `emit.py` or `distribute.py` (stair type selection logic), `cli.py` (default override)
- **No breaking changes**: `--stair TYPE` CLI flag continues to work as before; auto-selection only applies when the user does not specify a stair type
- **Test coverage**: New unit tests for stair type selection logic
