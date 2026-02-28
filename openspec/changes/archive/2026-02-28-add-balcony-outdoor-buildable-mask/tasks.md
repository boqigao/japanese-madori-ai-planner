## 1. Models and DSL Extensions

- [x] 1.1 Extend `plan_engine/models.py` with floor-level buildable-mask data structures and indoor/outdoor space classification fields.
- [x] 1.2 Update `plan_engine/constants.py` with outdoor room type sets (`balcony`, `veranda`) and helper predicates for indoor/outdoor logic.
- [x] 1.3 Modify `plan_engine/dsl.py` to parse optional floor buildable rectangles and outdoor space types, including 455mm grid validation for mask coordinates.

## 2. Preflight Feasibility Rules

- [x] 2.1 Update `plan_engine/preflight.py` area-budget calculations to target per-floor indoor buildable area instead of full envelope area.
- [x] 2.2 Add preflight checks for buildable-mask consistency (inside envelope, non-overlap, positive area, grid aligned).
- [x] 2.3 Update topology preflight checks so indoor reachability remains mandatory while each outdoor space must declare at least one indoor access edge.

## 3. Solver Coverage and Topology

- [x] 3.1 Update `plan_engine/solver/workflow.py` and `plan_engine/solver/rect_var.py` to constrain indoor placements to buildable mask cells.
- [x] 3.2 Revise coverage constraints in `plan_engine/solver/workflow.py` to enforce `indoor_area == buildable_indoor_area` per floor.
- [x] 3.3 Update adjacency handling in `plan_engine/solver/constraints.py` and `plan_engine/solver/workflow.py` to support required indoor-to-outdoor access edges.
- [x] 3.4 Update `plan_engine/solver/solution_builder.py` to persist indoor/outdoor and buildable-area metadata in `PlanSolution` outputs.

## 4. Validator and Structural Semantics

- [x] 4.1 Update `plan_engine/validator/geometry.py` coverage checks to validate indoor buildable coverage and report indoor/outdoor area breakdown.
- [x] 4.2 Update `plan_engine/validator/connectivity.py` to keep entry BFS indoor-only and add explicit outdoor-access realization checks.
- [x] 4.3 Update `plan_engine/structural/walls.py` extraction/classification to exclude outdoor-only boundaries from structural wall metrics.

## 5. Rendering and Reporting

- [x] 5.1 Update `plan_engine/renderer/core.py` and `plan_engine/renderer/helpers.py` to style outdoor spaces distinctly and keep merged-shape boundary behavior consistent.
- [x] 5.2 Update `plan_engine/renderer/symbols.py` and related render passes to draw openings on realized indoor-to-outdoor shared edges.
- [x] 5.3 Update `plan_engine/renderer/annotations.py` and `plan_engine/io.py` area summaries to separate indoor and outdoor totals (sqm/tsubo).

## 6. Example Migration and Regression Tests

- [x] 6.1 Migrate Case 08 in `examples/` to a true balcony/veranda spec using buildable mask semantics and regenerate `plan_output` artifacts.
- [x] 6.2 Add/extend tests under `tests/dsl/`, `tests/preflight/`, `tests/solver/`, `tests/validator/`, `tests/renderer/`, and `tests/structural/` for balcony/buildable-mask behavior.
- [x] 6.3 Run `make verify` and `make test` to confirm the change is stable end-to-end.
