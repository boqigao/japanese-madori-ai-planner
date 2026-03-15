## Context

The spec generator (`gen_spec.py`) hardcodes `DEFAULT_STAIR_TYPE = "U_turn"` in `profiles.py`. The U-turn stair occupies a 4×5 cell bounding box (1820×2275mm), which on narrow lots (≤14 cells / 6370mm wide) is wider than the hall corridor (2 cells / 910mm). This creates a geometric blockage where the hall cannot pass alongside the stair, making multi-bedroom layouts INFEASIBLE.

Stair footprints by type:
- `straight`: 2×6 cells (910×2730mm) — same width as hall
- `L_landing`: 5×5 cells (2275×2275mm)
- `U_turn`: 4×5 cells (1820×2275mm)

The fix is purely in the generator pipeline. The solver, renderer, and validator already support all three stair types.

## Goals / Non-Goals

**Goals:**
- Auto-select an appropriate stair type based on lot width when user does not specify `--stair`
- Preserve user override: `--stair TYPE` always takes priority
- Update stair cell estimates so area allocation uses the correct footprint

**Non-Goals:**
- No solver/renderer/validator changes
- No new stair types
- No fallback retry logic in the solver (that would be a separate change)

## Decisions

### 1. Width-based stair type selection

Add a function `select_stair_type(envelope_width_mm: int) -> str` in `profiles.py`:

| Lot width (cells) | Lot width (mm) | Default stair type | Rationale |
|-|-|-|-|
| ≤14 | ≤6370 | `straight` | U-turn/L-landing too wide; only straight (2 cells) fits alongside hall |
| 15–17 | 6825–7735 | `L_landing` | L-landing (5 cells) fits but U-turn still tight |
| ≥18 | ≥8190 | `U_turn` | All types fit comfortably |

**Why these thresholds?** The critical metric is `stair_width + hall_width + min_room_width ≤ lot_width`. For a bedroom with min_width=4 cells (1820mm) and hall=2 cells: straight needs 2+2+4=8, L_landing needs 5+2+4=11, U_turn needs 4+2+4=10. So even U_turn fits at 10 cells width — but the 100% coverage + adjacency constraints make it practically infeasible at ≤14 cells because rooms need to be arranged on both sides of the hall.

**Alternative considered:** Always use `straight` as default. Rejected because U-turn stairs are architecturally preferred (more compact vertical footprint, better circulation) when lot width allows.

### 2. Integration point

The selection happens in `emit.py` (YAML emission stage), which already constructs the stair YAML block. Currently it reads `DEFAULT_STAIR_TYPE` from `profiles.py`. The change:
- `emit.py` calls `select_stair_type(envelope_width_mm)` when `args.stair_type` is the default
- If user explicitly passed `--stair`, that value is used unchanged

### 3. Stair cell estimate update

`STAIR_CELLS_ESTIMATE` in `profiles.py` is used by `distribute.py` for floor capacity estimation. Currently the estimate is looked up by a hardcoded type. After this change, the lookup uses the selected stair type so that area allocation is accurate for straight stairs (8 cells vs 12 for U_turn).

## Risks / Trade-offs

- [Threshold values may need tuning] → Start with the conservative thresholds above; can be adjusted based on solve success rates across examples
- [User confusion if auto-selected type differs from expectation] → Log the selected stair type in the feasibility report so users see what was chosen
