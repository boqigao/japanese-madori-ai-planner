# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-Driven Madori Plan Engine: generates structurally valid Japanese detached house floor plans from a YAML DSL specification. Uses Google OR-Tools CP-SAT solver for constraint-based layout generation and renders output as SVG/PNG.

Pipeline: `DSL (YAML) -> Solver (CP-SAT) -> Validator -> Renderer (SVG/PNG)`

## Build & Run Commands

```bash
uv sync                          # Install/update dependencies
uv run python main.py --spec tmp/spec.yaml --outdir tmp/plan_output --solver-timeout 90
python -m compileall main.py plan_engine   # Quick syntax check
make verify                      # Syntax check + run default example
uv run pytest                    # When tests exist (add under tests/)
```

## Architecture

Strict separation of concerns -- these boundaries must never be crossed:
- **Solver** must not render; **Renderer** must not alter geometry; **Validator** runs only on solved output.

### Module Responsibilities

| Module | Role |
|---|---|
| `main.py` | CLI entrypoint. Orchestrates DSL -> solve -> validate -> render. |
| `plan_engine/models.py` | Frozen dataclasses: `PlanSpec`, `PlanSolution`, `Rect`, `SpaceGeometry`, `StairGeometry`, `ValidationReport`, etc. |
| `plan_engine/constants.py` | Grid constants (`MINOR_GRID_MM=455`, `MAJOR_GRID_MM=910`, `TATAMI_MM2`), room type sets (`MAJOR_ROOM_TYPES`, `WET_SPACE_TYPES`, `STAIR_TYPES`, `EDGE_NAMES`), wet module fixed sizes, unit conversion helpers. |
| `plan_engine/dsl.py` | Parses YAML spec into `PlanSpec`. Validates grid alignment, units, and schema. |
| `plan_engine/stair_logic.py` | `StairPortal` dataclass and deterministic portal mapping (`stair_portal_for_floor`). |
| `plan_engine/io.py` | Writes `solution.json` and `report.txt`. |

### Solver Package (`plan_engine/solver/`)

| Module | Role |
|---|---|
| `core.py` | `PlanSolver` class. Orchestrates context build -> constraint pipeline -> solve -> solution extraction. |
| `workflow.py` | `SolveContext` dataclass and constraint pipeline functions: `build_context`, `create_space_variables`, `add_floor_packing_constraints`, `add_topology_constraints`, `add_stair_connection_constraints`, `add_wc_ldk_non_adjacent_constraints`, `add_wet_cluster_constraints`, `build_objective`. |
| `rect_var.py` | `RectVar` and `StairFootprint` dataclasses. `new_rect` factory creates CP-SAT variables for a rectangle. `_compute_stair_footprint` calculates stair geometry. |
| `constraints.py` | Low-level CP-SAT constraint builders: `touching_constraint`, `edge_touch_constraint`, `pair_touch_bool`, `pair_edge_touch_bool`, `overlap_length`, `enforce_non_adjacent`, `enforce_exterior_touch`, `enforce_internal_portal_edge`. |
| `space_specs.py` | Space-type constraint lookup tables and functions: min/max area, min width, shortfall/overshoot weights, component counts. |
| `solution_builder.py` | `build_solution` converts solved cell-unit variables back to mm-unit `PlanSolution`. |

### Validator Package (`plan_engine/validator/`)

| Module | Role |
|---|---|
| `core.py` | `validate_solution` orchestrator -- calls all sub-validators and returns `ValidationReport`. |
| `geometry.py` | `validate_space_presence` (missing/extra spaces), `validate_geometry` (grid alignment, boundary, no overlap, 100% coverage), `validate_entry_exterior` (entry touches boundary). |
| `connectivity.py` | `validate_connectivity` -- BFS reachability from entry, WC-LDK non-adjacency check. |
| `stair.py` | `validate_stair` -- stair projection alignment across floors, portal positioning, hall connectivity via shared edge segments. |
| `livability.py` | `validate_livability` -- dimensional quality warnings (entry width, bedroom size, hall circulation, area ratios, stair dimensions). |

### Renderer Package (`plan_engine/renderer/`)

| Module | Role |
|---|---|
| `core.py` | `SvgRenderer` class. Read-only consumption of `PlanSolution`. Orchestrates all drawing passes and exports PNG via CairoSVG. |
| `annotations.py` | Space labels (name, dimensions, area), title block, color legend, north arrow. |
| `dimensions.py` | Room interior dimension guides, exterior site/building dimension lines. |
| `stair.py` | Stair visualization: component outlines, tread step lines, void hatching, guardrails, connection openings. |
| `symbols.py` | Door symbols (wall cut + swing arc) and window symbols (colored line). |
| `helpers.py` | Geometry helpers (boundary segments, bounding rect, shared edges, exterior segments), display name formatting, coordinate sorting, portal resolution. |

### Key Domain Concepts

- **Grid system**: 455mm minor grid (hard), 910mm major grid (soft preference for major rooms). All coordinates/dimensions must satisfy `value % 455 == 0`.
- **Solver works in cell units** (1 cell = 455mm). Converts back to mm when building `PlanSolution`.
- **Wet modules** (toilet, washroom, bath) have fixed sizes from `WET_MODULE_SIZES_MM` and must form a connected cluster adjacent to a hall.
- **Stair** is a shared structural element across floors -- single stair position (`stair_x`, `stair_y`) reused for all floors. Supports `straight` and `L_landing` types.
- **L-shaped rooms**: LDK can use 2 rectangles (`L2` shape) when spec allows.
- **100% coverage**: Solver enforces that total space area == envelope area per floor.
- **Adjacency** is modeled via touching constraints (shared edge with positive overlap length).
- **Non-adjacency** (WC away from LDK) enforced by requiring a 1-cell gap.

### Output Files

Each run produces in `--outdir`: `solution.json`, `{floor_id}.svg`, `{floor_id}.png`, `report.txt`.

## Coding Conventions

- Python 3.13+, PEP 8, 4-space indent, explicit type hints on public APIs.
- `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- All model dataclasses are `frozen=True` (immutable) except `ValidationReport`.
- All functions and public methods must have English docstrings.
- Conventional Commits (`feat:`, `fix:`, `refactor:`).

## Design Reference

`local-dev/coding-prompts/requirements.md` contains the full MVP specification.
`local-dev/feedback/` contains review notes on generated output quality.
