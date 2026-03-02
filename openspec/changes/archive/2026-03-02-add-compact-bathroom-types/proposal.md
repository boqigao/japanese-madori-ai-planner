## Why

Japanese 2-story homes commonly use a compact second-floor sanitary setup: a standalone washstand (洗面台のみ, no washing machine space) and a shower-only room (シャワールーム, no bathtub). Major manufacturers (TOTO JSV-0808, LIXIL SPB-0808) offer standardized 800×800mm shower units for this purpose. Currently the engine only models full-size `washroom` (1820×1820mm) and `bath` (1820×1820mm), forcing users to over-allocate F2 space by ~2.5 tatami for scenarios where compact sanitary is appropriate. This blocks feasibility for tighter envelopes (e.g., 5LDK in 8×9m) and misrepresents the intended design.

## What Changes

- Add two new room types to the engine: `washstand` and `shower`.
- `washstand`: a compact wash area with sink only (no washing machine space). Fixed module size 910×910mm (0.5 tatami).
- `shower`: a shower-only room without bathtub. Fixed module size 910×1365mm (~0.75 tatami).
- Both types join the wet-space cluster (must be adjacent to hall, form connected wet group).
- `shower` requires adjacency to `washstand` (same relationship as `bath` requires `washroom`).
- Renderer draws appropriate fixtures: sink symbol for `washstand`, shower head symbol for `shower` (no bathtub, no washing machine).
- DSL parser accepts the new types in spec.yaml.
- Preflight validates the new types in wet-cluster checks.

## Non-goals

- Changing existing `washroom` or `bath` behavior — they remain as-is for full-size setups.
- Spec generator CLI — that is a separate future change that will consume these types.
- Structural or bearing model changes — wet rooms don't affect structural analysis.

## Capabilities

### New Capabilities
- `compact-bathroom-types`: Defines the `washstand` and `shower` room types, their fixed module sizes, wet-cluster membership, adjacency rules, and renderer fixtures.

### Modified Capabilities
- `solver`: Delta spec for new wet module sizes and `shower`↔`washstand` adjacency constraint (analogous to `bath`↔`washroom`).
- `renderer`: Delta spec for new fixture symbols (washstand sink, shower head).
- `preflight`: Delta spec for wet-cluster validation accepting the new types.
- `dsl`: Delta spec for parser accepting `washstand` and `shower` as valid room types.

## Impact

- **plan_engine/constants.py**: Add `washstand` and `shower` to `WET_SPACE_TYPES`, `WET_MODULE_SIZES_MM`, and a new `WET_CORE_SPACE_TYPES` expansion.
- **plan_engine/dsl.py**: Accept new types during spec parsing.
- **plan_engine/preflight/wet.py**: Validate compact wet types in cluster checks.
- **plan_engine/solver/workflow_wet.py**: Handle new module sizes and `shower`↔`washstand` adjacency.
- **plan_engine/solver/space_specs.py**: Register new types.
- **plan_engine/renderer/fixtures.py**: Draw sink for `washstand`, shower head for `shower`.
- **plan_engine/renderer/openings.py**: Door suppression: `shower`↔non-`washstand` (same pattern as `bath`↔non-`washroom`).
- **plan_engine/validator/connectivity.py**: Include new types in wet-cluster connectivity.
- **tests/**: New unit tests for each affected module.
