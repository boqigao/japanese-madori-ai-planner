## 1. Consolidate Duplicate Constants

- [x] 1.1 Move `TOILET_SPACE_TYPES`, `WET_CORE_SPACE_TYPES`, `CIRCULATION_SPACE_TYPES` frozensets into `plan_engine/constants.py`. Update imports in `plan_engine/solver/workflow.py` and `plan_engine/preflight.py` to use the centralized definitions. Remove the local definitions.
- [x] 1.2 Run `python -m compileall plan_engine` and `uv run pytest` to verify no import breakage.

## 2. Split `plan_engine/models.py` into `models/` Package

- [x] 2.1 Create `plan_engine/models/` directory. Create `plan_engine/models/spec.py` with input spec dataclasses (`StairType`, `GridSpec`, `EnvelopeSpec`, `SiteSpec`, `AreaConstraint`, `SizeConstraints`, `ShapeSpec`, `BuildableRectSpec`, `SpaceSpec`, `EmbeddedClosetSpec`, `StairSpec`, `CoreSpec`, `AdjacencyRule`, `TopologySpec`, `FloorSpec`, `PlanSpec`).
- [x] 2.2 Create `plan_engine/models/geometry.py` with the `Rect` dataclass.
- [x] 2.3 Create `plan_engine/models/solution.py` with output solution dataclasses (`SpaceGeometry`, `EmbeddedClosetGeometry`, `StairGeometry`, `FloorSolution`, `PlanSolution`).
- [x] 2.4 Create `plan_engine/models/structure.py` with structural output dataclasses (`WallSegment`, `FloorStructureMetrics`, `ContinuityMetrics`, `VerticalTransferRequirement`, `StructureReport`).
- [x] 2.5 Create `plan_engine/models/validation.py` with `ValidationReport` and `BedroomReachabilityViolation`.
- [x] 2.6 Create `plan_engine/models/__init__.py` that re-exports all public symbols so `from plan_engine.models import X` continues to work. Remove the old `plan_engine/models.py`.
- [x] 2.7 Run full test suite to verify no import breakage.

## 3. Split `plan_engine/solver/workflow.py` into Sub-modules

- [x] 3.1 Create `plan_engine/solver/workflow_context.py` with `SolveContext`, `build_context`, `_create_stair_anchor`, `_constrain_rect_within_buildable_union`.
- [x] 3.2 Create `plan_engine/solver/workflow_spaces.py` with `_embedded_closet_area_adjustments`, `create_space_variables`.
- [x] 3.3 Create `plan_engine/solver/workflow_topology.py` with `add_floor_packing_constraints`, `add_topology_constraints`, `add_stair_connection_constraints`, `add_wc_ldk_non_adjacent_constraints`, `add_orientation_preference_constraints`, `resolve_north_south_edges`, `_space_edge_touch_bool`, `build_objective`, `_resolve_adjacency_strength`.
- [x] 3.4 Create `plan_engine/solver/workflow_wet.py` with `add_bath_wash_adjacency_constraints`, `add_wet_cluster_constraints`, `add_toilet_circulation_constraints`, `add_wet_core_circulation_constraints`, `add_closet_parent_constraints`.
- [x] 3.5 Update `plan_engine/solver/workflow.py` to become a re-export shim (import and re-export all public symbols from the 4 new modules). Update `plan_engine/solver/core.py` imports if needed.
- [x] 3.6 Run full test suite to verify no breakage.

## 4. Split `plan_engine/preflight.py` into `preflight/` Package

- [x] 4.1 Create `plan_engine/preflight/` directory. Create `plan_engine/preflight/core.py` with `FloorPreflightStats`, `PreflightResult`, `run_preflight`, `build_solver_failure_report`, `_stair_area_by_floor`, `_floor_area_budget`, `_check_envelope_alignment`, `_check_room_min_width`, `_check_major_room_exterior_touch_feasibility`, `_rect_touches_envelope_edge`, `_check_buildable_mask_consistency`, `_suggest_reduce_large_targets`, `cells_to_sqm`.
- [x] 4.2 Create `plan_engine/preflight/topology.py` with `_check_topology_reachability`, `_hall_fanout`, `_bfs_with_parents`, `_reconstruct_path`, `_edge_ids`.
- [x] 4.3 Create `plan_engine/preflight/wet.py` with `_check_wet_cluster_fit`, `_check_toilet_circulation_topology`, `_check_wet_core_circulation_topology`, `_can_pack_connected_wet_modules`, `_rects_overlap`.
- [x] 4.4 Create `plan_engine/preflight/closets.py` with `_check_reference_consistency`, `_check_closet_semantics`, `_warn_bedrooms_without_closet`.
- [x] 4.5 Create `plan_engine/preflight/__init__.py` that re-exports `run_preflight`, `build_solver_failure_report`, `PreflightResult`, `FloorPreflightStats`. Remove old `plan_engine/preflight.py`. Update imports in `main.py` and `plan_engine/solver/core.py`.
- [x] 4.6 Run full test suite to verify no breakage.

## 5. Split `plan_engine/renderer/core.py`

- [x] 5.1 Create `plan_engine/renderer/fixtures.py` — extract `_draw_fixtures` and `_draw_vent_marker` as standalone functions that accept drawing group and solution data as parameters. Update `SvgRenderer._draw_fixtures` to delegate to the new module.
- [x] 5.2 Create `plan_engine/renderer/openings.py` — extract `_draw_interior_doors`, `_draw_entry_door`, `_draw_windows` as standalone functions. Update `SvgRenderer` to delegate.
- [x] 5.3 Move `_should_draw_interior_door` and `_subtract_colinear_segment` into existing `plan_engine/renderer/helpers.py`.
- [x] 5.4 Verify `renderer/core.py` is now under 500 lines. Run full test suite.

## 6. Split `plan_engine/dsl.py`

- [x] 6.1 Create `plan_engine/dsl_closets.py` — extract `_parse_embedded_closets`, `_parse_embedded_closet_spec`, `_space_to_embedded_closet`, `_validate_floor_closet_references`. Update `dsl.py` to import from the new module.
- [x] 6.2 Verify `dsl.py` is now under 500 lines. Run test suite.

## 7. Split `plan_engine/renderer/dimensions.py`

- [x] 7.1 Create `plan_engine/renderer/dimensions_interior.py` — extract `draw_room_dimension_guides` and `_draw_rect_dimension_guide`.
- [x] 7.2 Create `plan_engine/renderer/dimensions_exterior.py` — extract `draw_dimensions`, `_draw_dimension_chain`, `_collect_perimeter_breakpoints`, `_collect_opening_breakpoints`, `_segment_on_side`, `_side_axis`, `_snap_to_minor`, `_normalize_breakpoints`, `draw_dimension_line`.
- [x] 7.3 Remove old `renderer/dimensions.py`. Update imports in `renderer/core.py` to use the two new modules.
- [x] 7.4 Run full test suite to verify no breakage.

## 8. Final Verification

- [x] 8.1 Run `ruff check plan_engine/` to verify no lint errors.
- [x] 8.2 Run `uv run pytest` to verify all tests pass.
- [x] 8.3 Run `make verify` for end-to-end validation.
- [x] 8.4 Verify all source files are under 500 lines: `find plan_engine -name "*.py" | xargs wc -l | sort -rn | head -20`.
