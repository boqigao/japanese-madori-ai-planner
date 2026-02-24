# AGNETS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-Driven Madori Plan Engine: generates structurally valid Japanese detached house floor plans from a YAML DSL specification. Uses Google OR-Tools CP-SAT solver for constraint-based layout generation and renders output as SVG/PNG.

Pipeline: `DSL (YAML) → Solver (CP-SAT) → Validator → Renderer (SVG/PNG)`

## Build & Run Commands

```bash
uv sync                          # Install/update dependencies
uv run python main.py --spec tmp/sample_spec.yaml --outdir tmp/plan_output --solver-timeout 10
python -m compileall main.py plan_engine   # Quick syntax check
uv run pytest                    # When tests exist (add under tests/)
```

## Architecture

Strict separation of concerns — these boundaries must never be crossed:
- **Solver** must not render; **Renderer** must not alter geometry; **Validator** runs only on solved output.

### Module Responsibilities

| Module | Role |
|---|---|
| `main.py` | CLI entrypoint. Orchestrates DSL → solve → validate → render. |
| `plan_engine/dsl.py` | Parses YAML spec into `PlanSpec`. Validates grid alignment and schema. |
| `plan_engine/solver.py` | CP-SAT model: creates `RectVar` decision variables per space, enforces hard constraints (no-overlap, envelope, adjacency, wet-cluster), minimizes soft objective (area targets, alignment, compactness). |
| `plan_engine/validator.py` | Post-solve checks: space presence, grid alignment (`% 455 == 0`), no overlap, 100% envelope coverage, entry-reachability (BFS), stair projection alignment, WC-LDK non-adjacency. |
| `plan_engine/renderer.py` | `SvgRenderer` — read-only consumption of `PlanSolution`. Draws grid, spaces, stairs, doors, windows, labels, legend, north arrow, dimensions. Exports PNG via CairoSVG. |
| `plan_engine/models.py` | Frozen dataclasses: `PlanSpec`, `PlanSolution`, `Rect`, `SpaceGeometry`, `StairGeometry`, `ValidationReport`, etc. |
| `plan_engine/constants.py` | Grid constants (`MINOR_GRID_MM=455`, `MAJOR_GRID_MM=910`, `TATAMI_MM2`), room type sets, wet module fixed sizes, unit conversion helpers. |
| `plan_engine/io.py` | Writes `solution.json` and `report.txt`. |

### Key Domain Concepts

- **Grid system**: 455mm minor grid (hard), 910mm major grid (soft preference for major rooms). All coordinates/dimensions must satisfy `value % 455 == 0`.
- **Solver works in cell units** (1 cell = 455mm). Converts back to mm when building `PlanSolution`.
- **Wet modules** (toilet, washroom, bath) have fixed sizes from `WET_MODULE_SIZES_MM` and must form a connected cluster adjacent to a hall.
- **Stair** is a shared structural element across floors — single stair position (`stair_x`, `stair_y`) reused for all floors. Supports `straight` and `L_landing` types.
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
- Conventional Commits (`feat:`, `fix:`, `refactor:`).

## Design Reference

`local-dev/coding-prompts/requirements.md` contains the full MVP specification.
`local-dev/feedback/` contains review notes on generated output quality.
