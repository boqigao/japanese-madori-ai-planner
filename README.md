# AI-Driven Plan Engine

Constraint-based Japanese detached house floor plan generator.
Takes a YAML DSL specification and produces structurally valid layouts as SVG/PNG using Google OR-Tools CP-SAT.

Pipeline: `DSL (YAML) -> Solver (CP-SAT) -> Validator -> Renderer (SVG/PNG)`

## Quick Start

### Prerequisites

- Python 3.13+
- [`uv`](https://github.com/astral-sh/uv) for dependency management

### Install & Run

```bash
make sync    # install dependencies

# generate a two-story compact house from the bundled examples
make run SPEC="examples/1. Compact 2F/spec.yaml" OUTDIR=out
```

Output files in `out/`:

| File | Description |
|---|---|
| `solution.json` | Solved layout data (includes extracted walls and structure report) |
| `report.txt` | Validation report |
| `F1.svg` / `F1.png` | First floor plan |
| `F2.svg` / `F2.png` | Second floor plan |

Optional structural wall overlay:

```bash
PLAN_ENGINE_DRAW_STRUCTURAL_WALLS=1 make run SPEC="examples/1. Compact 2F/spec.yaml" OUTDIR=out
```

### Running Without Make

```bash
uv run python main.py \
  --spec "examples/1. Compact 2F/spec.yaml" \
  --outdir out \
  --solver-timeout 90
```

## Examples

The [`examples/`](examples/) directory contains 10 pre-built house variants, each with a
`spec.yaml` input and pre-generated output in `plan_output/`.
See [`examples/README.md`](examples/README.md) for the full list.

Regenerate all examples:

```bash
for d in examples/*; do
  [ -f "$d/spec.yaml" ] || continue
  uv run python main.py --spec "$d/spec.yaml" --outdir "$d/plan_output" --solver-timeout 20
done
```

## Documentation

- [How to write a spec.yaml](docs/how_to_use.md) -- beginner guide starting from site dimensions

## Commands

```bash
make help            # show all targets
make sync            # install / update dependencies
make run             # generate (SPEC=... OUTDIR=... TIMEOUT=90)
make check-syntax    # Python compile check
make verify          # check-syntax + run default example
make fmt             # auto-format with ruff
make lint            # lint with ruff
make test            # pytest (80% coverage required)
make clean-output    # remove OUTDIR
```

## Topology Rule: Bedroom Reachability

Preflight enforces a residential circulation rule:

- Every `bedroom` / `master_bedroom` must be reachable from `entry`
  without using another bedroom as a transit room.
- If violated, generation stops before solve with an error like:
  `preflight: F2:bed3 is only reachable through bedroom transit (...)`

Typical fix: connect blocked bedrooms to `hall` (or stair-linked hall) in
`topology.adjacency`.

## Project Structure

```
main.py                           CLI entrypoint
Makefile                          Build / run / verify commands
pyproject.toml                    Project metadata and dependencies (uv)

plan_engine/                      Core library
  constants.py                    Grid constants, room types, unit conversions
  models.py                       Frozen dataclasses (PlanSpec, PlanSolution, Rect, etc.)
  dsl.py                          YAML spec parser -> PlanSpec
  preflight.py                    Pre-solve checks (bedroom reachability, etc.)
  stair_logic.py                  Stair portal mapping logic
  io.py                           JSON/text file output
  solver/
    core.py                       PlanSolver class (orchestrates solving)
    workflow.py                   Constraint building pipeline (variables, packing, topology, wet cluster)
    rect_var.py                   RectVar factory, StairFootprint computation
    constraints.py                Low-level CP-SAT constraint builders (touch, overlap, adjacency)
    space_specs.py                Space-type constraint specifications (area, width, weights)
    solution_builder.py           Converts solved CP-SAT variables -> PlanSolution
  validator/
    core.py                       Validation orchestrator
    geometry.py                   Grid alignment, boundary, overlap, coverage checks
    connectivity.py               BFS reachability, WC-LDK separation
    stair.py                      Stair alignment, portal positioning, hall connectivity
    livability.py                 Dimensional quality, area ratios, circulation metrics
    structural.py                 Bearing-wall proxy metrics and continuity diagnostics
  structural/
    walls.py                      Wall extraction + structural report computation
  renderer/
    core.py                       SvgRenderer class (orchestrates drawing)
    annotations.py                Space labels, title block, legend, north arrow
    dimensions.py                 Room dimension guides, exterior dimension lines
    stair.py                      Stair visualization (steps, voids, guardrails)
    symbols.py                    Door and window symbols
    helpers.py                    Geometry helpers, boundary segments, display formatting

docs/                             User-facing documentation
  how_to_use.md                   Beginner guide for writing spec.yaml
examples/                         Pre-built spec + output pairs (10 house variants)
resources/specs/                  YAML fixtures used by tests
tests/                            Pytest suite (unit + integration)
openspec/                         OpenSpec change-tracking (specs, proposals, tasks)
```

## Troubleshooting

- **`dsl_parse_failed`**: Check `spec.yaml` field names, indentation, and grid alignment (455 mm).
- **`solve_failed`**: Constraints are too tight or conflicting. Try reducing room count or adjacency relationships, then add back incrementally.
- **`preflight: ... only reachable through bedroom transit`**: Update `topology.adjacency` so each bedroom has a non-bedroom access route (usually hall).
- **`Plan rejected by validation`**: Review `report.txt` for `Errors` and `Warnings`.
