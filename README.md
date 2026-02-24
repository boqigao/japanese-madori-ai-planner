# AI-Driven Plan Engine

Constraint-based Japanese detached house floor plan generator.
Takes a YAML DSL specification and produces structurally valid layouts as SVG/PNG using Google OR-Tools CP-SAT.

Pipeline: `DSL (YAML) -> Solver (CP-SAT) -> Validator -> Renderer (SVG/PNG)`

## Prerequisites

- Python 3.13+
- [`uv`](https://github.com/astral-sh/uv) for dependency management

Install dependencies:

```bash
make sync
```

## Quick Start

The repository includes a runnable two-story house example with stairs:
- Spec file: `tmp/spec.yaml`
- Default output: `tmp/plan_output`

Generate with one command:

```bash
make run-default
```

Output files:
- `tmp/plan_output/solution.json` -- solved layout data
- `tmp/plan_output/report.txt` -- validation report
- `tmp/plan_output/F1.svg`, `tmp/plan_output/F1.png` -- first floor plan
- `tmp/plan_output/F2.svg`, `tmp/plan_output/F2.png` -- second floor plan

## Commands

Show all available commands:

```bash
make help
```

Run with custom spec, output directory, or solver timeout:

```bash
make run SPEC=tmp/spec.yaml OUTDIR=tmp/plan_output TIMEOUT=120
```

Syntax check:

```bash
make check-syntax
```

Full verification (syntax check + default example generation):

```bash
make verify
```

Clean up generated outputs:

```bash
make clean-output OUTDIR=tmp/plan_output
make clean-tmp
```

## Running Without Make

```bash
uv run python main.py --spec tmp/spec.yaml --outdir tmp/plan_output --solver-timeout 90
```

## Project Structure

```
main.py                         CLI entrypoint
plan_engine/
  constants.py                  Grid constants, room types, unit conversions
  models.py                     Frozen dataclasses (PlanSpec, PlanSolution, Rect, etc.)
  dsl.py                        YAML spec parser -> PlanSpec
  stair_logic.py                Stair portal mapping logic
  io.py                         JSON/text file output
  solver/
    core.py                     PlanSolver class (orchestrates solving)
    workflow.py                 Constraint building pipeline (variables, packing, topology, wet cluster)
    rect_var.py                 RectVar factory, StairFootprint computation
    constraints.py              Low-level CP-SAT constraint builders (touch, overlap, adjacency)
    space_specs.py              Space-type constraint specifications (area, width, weights)
    solution_builder.py         Converts solved CP-SAT variables -> PlanSolution
  validator/
    core.py                     Validation orchestrator
    geometry.py                 Grid alignment, boundary, overlap, coverage checks
    connectivity.py             BFS reachability, WC-LDK separation
    stair.py                    Stair alignment, portal positioning, hall connectivity
    livability.py               Dimensional quality, area ratios, circulation metrics
  renderer/
    core.py                     SvgRenderer class (orchestrates drawing)
    annotations.py              Space labels, title block, legend, north arrow
    dimensions.py               Room dimension guides, exterior dimension lines
    stair.py                    Stair visualization (steps, voids, guardrails)
    symbols.py                  Door and window symbols
    helpers.py                  Geometry helpers, boundary segments, display formatting
tmp/                            Example specs and generated output
local-dev/                      Requirements docs, feedback, and refactor plans
```

## Troubleshooting

- **`dsl_parse_failed`**: Check `spec.yaml` field names, indentation, and grid alignment (455mm).
- **`solve_failed`**: Constraints are too tight or conflicting. Try reducing room count or adjacency relationships, then add back incrementally.
- **`Plan rejected by validation`**: Review `report.txt` for `Errors` and `Warnings`.
