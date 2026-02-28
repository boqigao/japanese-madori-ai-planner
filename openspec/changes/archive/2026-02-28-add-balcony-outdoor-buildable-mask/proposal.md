## Why

Case 08 in the benchmark requires a real 2F balcony (ベランダ/バルコニー), but the current engine can only model one global rectangular envelope with per-floor 100% indoor coverage. This forces balcony-like intent to be approximated as indoor storage/room area, which is semantically wrong for circulation, area accounting, and rendering.

## What Changes

- Add floor-level buildable-area support so each floor can define where indoor rooms may be placed, instead of forcing indoor coverage across the entire global envelope.
- Introduce explicit outdoor-space semantics for balcony/veranda-like areas, including classification in DSL and solution output.
- Change solver coverage constraints from “fill full envelope” to “fill indoor buildable area” per floor.
- Extend validator checks to distinguish indoor reachability/coverage from outdoor access semantics.
- Update renderer to display outdoor balcony regions distinctly and render openings/doors between indoor rooms and balcony boundaries.
- Update example Case 08 to use true balcony semantics instead of interior approximation.

## Non-goals

- No support for arbitrary polygon geometry in this change; initial scope is grid-aligned rectangular components.
- No CFD/thermal/daylighting simulation for balcony design quality.
- No attempt to redesign all benchmark cases beyond those directly affected by balcony/buildable-area semantics.

## Capabilities

### New Capabilities
- `outdoor-space-semantics`: Add explicit DSL/solution/render semantics for balcony/veranda spaces and indoor-to-outdoor access.
- `floor-buildable-mask`: Add per-floor buildable-area modeling so indoor coverage can target buildable zones rather than full envelope.

### Modified Capabilities
- `dsl`: Extend schema to parse floor-level buildable areas and outdoor-space metadata.
- `preflight`: Validate buildable-area feasibility and indoor/outdoor topology consistency before solve.
- `solver`: Update packing/coverage constraints to respect floor buildable masks and outdoor classification.
- `validator`: Validate indoor coverage/reachability against buildable masks and outdoor access rules.
- `renderer`: Render balcony/outdoor areas with distinct styling and opening logic.
- `structural`: Ensure bearing-wall extraction and continuity diagnostics use indoor/buildable geometry semantics.

## Impact

- Affected modules: `plan_engine/models.py`, `plan_engine/dsl.py`, `plan_engine/preflight.py`, `plan_engine/solver/workflow.py`, `plan_engine/solver/core.py`, `plan_engine/validator/geometry.py`, `plan_engine/validator/connectivity.py`, `plan_engine/renderer/core.py`, `plan_engine/renderer/helpers.py`, `plan_engine/structural/*`, `main.py` (report wording only).
- Output contract changes: `solution.json` and `report.txt` will include/build on indoor vs outdoor/buildable semantics.
- Backward compatibility risk: existing specs may need migration defaults if they rely on implicit full-envelope indoor coverage.
