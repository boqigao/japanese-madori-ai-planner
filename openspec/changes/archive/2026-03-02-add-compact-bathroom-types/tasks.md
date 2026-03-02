## 1. Constants & Type Registration

- [x] 1.1 In `plan_engine/constants.py`: add `"washstand"` and `"shower"` to `WET_SPACE_TYPES`, `WET_CORE_SPACE_TYPES`. Add entries to `WET_MODULE_SIZES_MM`: `"washstand": (910, 910)`, `"shower": (910, 1365)`.
- [x] 1.2 In `plan_engine/constants.py`: extend `should_place_door` to suppress doors on `shower`↔non-`washstand` edges (parallel to existing `bath`↔non-`washroom` logic).

## 2. DSL Parser

- [x] 2.1 In `plan_engine/dsl.py`: verify `washstand` and `shower` are accepted as valid space types. Add them to any type whitelist/enum if one exists. Add unit test confirming both types parse successfully.

## 3. Preflight

- [x] 3.1 In `plan_engine/preflight/wet.py`: ensure `_check_wet_cluster_fit` includes compact modules in cluster packing checks. Add preflight validation that `shower` requires at least one `washstand` on the same floor (error if missing).
- [x] 3.2 Add unit tests for preflight: washstand+shower fit check, shower-without-washstand error.

## 4. Solver

- [x] 4.1 In `plan_engine/solver/workflow_wet.py`: extend `add_bath_wash_adjacency_constraints` to also enforce shower↔washstand adjacency (each shower must touch at least one washstand). Raise `ValueError` if floor has shower but no washstand.
- [x] 4.2 In `plan_engine/solver/space_specs.py`: register `washstand` and `shower` types if type-specific solver configuration exists.
- [x] 4.3 Add unit tests for solver: shower↔washstand adjacency constraint, error on missing washstand.

## 5. Renderer

- [x] 5.1 In `plan_engine/renderer/fixtures.py`: add fixture drawing for `washstand` (single sink symbol, centered) and `shower` (shower head symbol, no bathtub).
- [x] 5.2 In `plan_engine/renderer/openings.py`: verify door suppression works for `shower`↔non-`washstand` (should follow from constants change in 1.2, but confirm).

## 6. Validator

- [x] 6.1 In `plan_engine/validator/connectivity.py`: verify compact wet types are included in wet-cluster connectivity validation. No code change expected if it reads from `WET_CORE_SPACE_TYPES` constant.

## 7. Integration & Verification

- [x] 7.1 Create an example spec that uses compact bathroom types on F2 (e.g., modify one 2F example to use washstand+shower instead of washroom+bath on F2). Verify it solves and renders correctly.
- [x] 7.2 Run `uv run pytest -x -q` — all tests pass.
- [x] 7.3 Run `uv run ruff check plan_engine/` — no lint errors.
- [x] 7.4 Run `make verify` — end-to-end validation passes.
