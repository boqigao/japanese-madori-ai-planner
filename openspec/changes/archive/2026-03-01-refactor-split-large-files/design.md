## Context

Six files in `plan_engine/` exceed the 500-line soft limit. Each file has clear internal logical groupings that map well to separate modules. The codebase already follows this pattern — `solver/`, `validator/`, and `renderer/` are already packages with multiple sub-modules. This change extends that pattern to the remaining large files.

Current state of files exceeding 500 lines:

| File | Lines | Problem |
|------|-------|---------|
| `solver/workflow.py` | 1,166 | Mixes context setup, variable creation, and 10+ constraint functions |
| `preflight.py` | 1,081 | Mixes area checks, topology BFS, wet-module fitting, closet validation |
| `renderer/core.py` | 1,067 | Monolithic class with fixture drawing (~250 lines) and door/window logic (~170 lines) |
| `models.py` | 632 | 29 dataclasses spanning input spec, geometry, solution, structural, and validation |
| `dsl.py` | 599 | Closet parsing (~115 lines) is an isolated concern |
| `renderer/dimensions.py` | 523 | Interior guides and exterior dimension chains are independent concerns |

## Goals / Non-Goals

**Goals:**
- Every source file under 500 lines (soft target)
- Preserve all existing public imports via `__init__.py` re-exports
- Zero behavioral changes — all tests pass without modification
- Eliminate duplicate constant definitions across modules

**Non-Goals:**
- Changing any function signatures or class interfaces
- Adding new features or fixing bugs
- Refactoring internal logic within functions
- Renaming any public symbols
- Modifying test assertions (only import paths if needed)

## Decisions

### D1: Convert `models.py` to a `models/` package with re-export `__init__.py`

**Choice**: Split into `models/spec.py`, `models/geometry.py`, `models/solution.py`, `models/structure.py`, `models/validation.py` with `models/__init__.py` re-exporting all symbols.

**Rationale**: `models.py` is imported by every other module in the project. Using a package with `__init__.py` re-exports means `from plan_engine.models import PlanSpec` continues to work unchanged. This is the standard Python pattern for growing a module into a package.

**Alternative considered**: Keep as single file (only 632 lines). Rejected because it's over the 500-line target and has 5 clearly distinct logical sections.

### D2: Split `solver/workflow.py` into 3 sub-modules by concern

**Choice**:
- `workflow_context.py`: `SolveContext` dataclass, `build_context`, `_create_stair_anchor`, `_constrain_rect_within_buildable_union` (~200 lines)
- `workflow_spaces.py`: `_embedded_closet_area_adjustments`, `create_space_variables` (~230 lines)
- `workflow_constraints.py`: All `add_*_constraints` functions, `resolve_north_south_edges`, `_space_edge_touch_bool`, `build_objective`, `_resolve_adjacency_strength` (~740 lines)

**Rationale**: Functions in `workflow.py` are already independent — each constraint function takes `(spec, ctx)` and only interacts through `SolveContext`. The split follows the natural pipeline: context → variables → constraints.

**Note**: `workflow_constraints.py` at ~740 lines still exceeds 500 lines. Further splitting into `workflow_topology.py` (~250 lines for adjacency/topology) and `workflow_wet.py` (~200 lines for wet/circulation) would bring all files under target. This is recommended.

**Revised split (4 modules)**:
- `workflow_context.py`: Context setup (~200 lines)
- `workflow_spaces.py`: Space variable creation (~230 lines)
- `workflow_topology.py`: `add_floor_packing_constraints`, `add_topology_constraints`, `add_stair_connection_constraints`, `add_wc_ldk_non_adjacent_constraints`, `add_orientation_preference_constraints`, `build_objective`, helper functions (~350 lines)
- `workflow_wet.py`: `add_bath_wash_adjacency_constraints`, `add_wet_cluster_constraints`, `add_toilet_circulation_constraints`, `add_wet_core_circulation_constraints`, `add_closet_parent_constraints` (~350 lines)

**Alternative considered**: Single split into 2 files. Rejected because the larger half would still exceed 500 lines.

### D3: Convert `preflight.py` to a `preflight/` package

**Choice**:
- `preflight/core.py`: `FloorPreflightStats`, `PreflightResult`, `run_preflight`, `build_solver_failure_report`, area budget functions, envelope checks (~300 lines)
- `preflight/topology.py`: `_check_topology_reachability`, `_hall_fanout`, `_bfs_with_parents`, `_reconstruct_path`, `_edge_ids` (~200 lines)
- `preflight/wet.py`: `_check_wet_cluster_fit`, `_check_toilet_circulation_topology`, `_check_wet_core_circulation_topology`, `_can_pack_connected_wet_modules`, `_rects_overlap` (~220 lines)
- `preflight/closets.py`: `_check_reference_consistency`, `_check_closet_semantics`, `_warn_bedrooms_without_closet` (~180 lines)
- `preflight/__init__.py`: Re-exports `run_preflight`, `build_solver_failure_report`, `PreflightResult`, `FloorPreflightStats`

**Rationale**: The topology BFS section is entirely self-contained with its own graph traversal utilities. The wet-module section has its own DFS packing solver. Closet validation is a distinct concern added later. This mirrors `validator/` which already splits along the same lines.

### D4: Extract fixture and door/window drawing from `renderer/core.py`

**Choice**:
- Extract `_draw_fixtures` and `_draw_vent_marker` → `renderer/fixtures.py` (~250 lines)
- Extract `_draw_interior_doors`, `_draw_entry_door`, `_draw_windows` → `renderer/openings.py` (~170 lines)
- Move `_should_draw_interior_door` and `_subtract_colinear_segment` → `renderer/helpers.py` (which already exists, these are utility functions)
- Remaining `renderer/core.py` becomes the orchestrator (~450 lines)

**Rationale**: `_draw_fixtures` alone is 211 lines and handles room-type-specific furniture (bed, kitchen counter, toilet, bathtub, etc.) — a completely independent concern. The door/window section is similarly self-contained. The renderer already delegates to `annotations.py`, `dimensions.py`, `stair.py`, and `symbols.py` — this extends the same pattern.

**Implementation note**: The extracted functions currently reference `self` (SvgRenderer methods). They will become standalone functions that accept the drawing group and solution data as parameters, called from `SvgRenderer` via delegation.

### D5: Extract closet parsing from `dsl.py`

**Choice**: Extract `_parse_embedded_closets`, `_parse_embedded_closet_spec`, `_space_to_embedded_closet`, `_validate_floor_closet_references` → `dsl_closets.py` (~115 lines). Remaining `dsl.py` becomes ~485 lines.

**Rationale**: Closet parsing is a self-contained concern added after the initial DSL parser. The 4 functions form a cohesive unit with no entanglement in the main parsing flow.

### D6: Split `renderer/dimensions.py` into interior and exterior concerns

**Choice**:
- `renderer/dimensions_interior.py`: `draw_room_dimension_guides`, `_draw_rect_dimension_guide` (~120 lines)
- `renderer/dimensions_exterior.py`: `draw_dimensions`, `_draw_dimension_chain`, breakpoint collectors, geometry helpers, `draw_dimension_line` (~400 lines)
- Remove `renderer/dimensions.py`, update imports in `renderer/core.py`

**Rationale**: Interior room dimension guides and exterior building dimension chains are independent concerns that happen to share a filename. They share no functions or data structures.

### D7: Consolidate duplicate frozenset constants into `constants.py`

**Choice**: Move `TOILET_SPACE_TYPES`, `WET_CORE_SPACE_TYPES`, `CIRCULATION_SPACE_TYPES` from `workflow.py` and `preflight.py` into `constants.py` (alongside existing `MAJOR_ROOM_TYPES`, `WET_SPACE_TYPES`, etc.).

**Rationale**: These frozensets are defined identically in both files. Centralizing them in `constants.py` follows the existing pattern and eliminates duplication.

## Risks / Trade-offs

- **Import path breakage** → Mitigation: Every split module uses `__init__.py` re-exports so existing `from plan_engine.X import Y` paths continue to work. Run `ruff check` and full test suite after each split.
- **Circular imports** → Mitigation: `models/` has zero internal-project imports (only stdlib). All other splits follow the existing dependency graph direction. No new cross-module dependencies introduced.
- **Merge conflicts with in-progress work** → Mitigation: Pure move-and-split operations. If conflicts arise, they're mechanical to resolve.
- **`git blame` history loss** → Mitigation: Use `git log --follow` for tracking. Accept this as an inherent cost of file splits. The improved readability outweighs the minor inconvenience.
