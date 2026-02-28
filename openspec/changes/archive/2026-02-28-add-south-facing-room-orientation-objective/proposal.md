## Why

Current layouts often place circulation and service rooms on the most valuable facade while putting LDK/bedrooms away from the preferred sun side. Professional review in `local-dev/floor-feedback/v8/professional.md` highlights this as a recurring livability issue that should be addressed in optimization.

## What Changes

- Add orientation-aware soft objective terms in solver using `site.north` to infer south/north envelope edges per floor.
- Prefer `ldk`, `bedroom`, and `master_bedroom` to touch the inferred south edge.
- Prefer `washroom`, `bath`, `toilet`/`wc`, and `storage` to touch the inferred north edge.
- Keep these as soft preferences only; hard feasibility/placement constraints remain unchanged.
- Add diagnostics to explain when orientation preference could not be realized strongly due to topology/packing tradeoffs.
- Add tests and benchmark checks to validate directional preference behavior and avoid regressions.

## Non-goals

- No requirement that all major rooms must be south-facing.
- No daylight simulation, climate-zone logic, or seasonal solar analysis.
- No change to renderer geometry or window generation.
- No change to stair policy (straight/L/U strategy remains separate work).

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `solver`: extend soft objective to include orientation preferences for major rooms (south) and service rooms (north), derived from `site.north`.
- `validator`: add orientation-related warning/diagnostic checks to make optimization outcomes interpretable in reports.

## Impact

- Affected modules: `plan_engine/solver/workflow.py`, `plan_engine/solver/space_specs.py` (or new orientation weight table), `plan_engine/validator/livability.py` (diagnostics), and related tests.
- Affected pipeline stages: solver objective, validator reporting.
- No DSL schema change expected; existing `site.north` is reused.
- Output impact: improved south allocation for LDK/bedrooms and north allocation for wet/storage in feasible examples.
