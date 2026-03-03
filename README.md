# Japanese Madori AI Planner

Constraint-based Japanese detached-house floor plan generator.

This project reads a YAML DSL (`spec.yaml`), solves layout geometry with OR-Tools CP-SAT, validates hard rules, and renders floor plans as SVG/PNG.

Pipeline: `DSL -> Solver -> Validator -> Renderer`

Includes a **Spec Generator** (`gen_spec.py`) that auto-creates `spec.yaml` from high-level inputs (envelope size + room count), eliminating the need to hand-author grid alignments, area budgets, and topology rules.

## What It Supports

- 455mm grid-based planning (`minor=455`, `major=910`)
- 1F / 2F layouts with shared stair shaft
- Fixed wet modules (`toilet`, `washroom`, `bath`)
- Distinct storage semantics:
  - `storage`: independent storage room
  - `closet`: built-in closet zone inside a parent room (`parent_id` required; rendered as hatched CL zone)
  - `wic`: walk-in closet (`parent_id` required, bedroom/master parent)
- Hall/LDK multi-rectangle support (`L2`)
- Floor-level indoor buildable masks
- Outdoor spaces (`balcony`, `veranda`) with explicit indoor-access rules
- Compact wet module types (`washstand`, `shower`) for tight layouts
- Output artifacts: `solution.json`, `report.txt`, `{floor}.svg`, `{floor}.png`
- **Spec Generator**: auto-generate `spec.yaml` from `--envelope 8x9 --rooms 5ldk`

## Quick Start

### Prerequisites

- Python 3.13+
- [`uv`](https://github.com/astral-sh/uv)

### Install

```bash
uv sync
```

### Generate a spec (recommended for new users)

```bash
uv run python gen_spec.py --envelope 8x9 --rooms 5ldk
```

This creates `spec.yaml` with proper grid alignment, area allocation, and topology. Then solve it:

```bash
uv run python main.py --spec spec.yaml --outdir plan_output --solver-timeout 90
```

For more options, see [docs/spec_generator.md](docs/spec_generator.md).

### Run (default tmp spec)

```bash
make run-default
```

### Run a specific spec

```bash
make run SPEC="examples/1. Compact 2F/spec.yaml" OUTDIR="tmp/plan_output" TIMEOUT=90
```

Or without Make:

```bash
uv run python main.py \
  --spec "examples/1. Compact 2F/spec.yaml" \
  --outdir "tmp/plan_output" \
  --solver-timeout 90
```

## Common Commands

```bash
make help            # list all targets
make sync            # uv sync
make run             # run with SPEC / OUTDIR / TIMEOUT
make run-default     # run tmp/spec.yaml -> tmp/plan_output
make check-syntax    # compile check
make verify          # check-syntax + run-default
make fmt             # ruff fix + format
make lint            # ruff checks
make test            # pytest + coverage (>=80%)
make clean-output    # remove OUTDIR
make clean-tmp       # remove tmp/*
```

## Output Files

Each run writes to `--outdir`:

- `solution.json`: solved geometry + structural metrics
- `report.txt`: validation result with diagnostics/suggestions
- `F1.svg`, `F1.png` (and `F2.*` for two-floor specs)

Optional structural overlay:

```bash
PLAN_ENGINE_DRAW_STRUCTURAL_WALLS=1 make run SPEC="examples/1. Compact 2F/spec.yaml" OUTDIR="tmp/plan_output"
```

## Examples

`examples/` contains benchmark-ready specs and generated outputs.

- Case list: [examples/README.md](examples/README.md)
- Each case folder contains `spec.yaml` + `plan_output/`

Regenerate all examples:

```bash
for d in examples/*; do
  [ -f "$d/spec.yaml" ] || continue
  uv run python main.py --spec "$d/spec.yaml" --outdir "$d/plan_output" --solver-timeout 30
done
```

## Spec Authoring Guide

**Auto-generate** (recommended): [docs/spec_generator.md](docs/spec_generator.md)
- Generate `spec.yaml` from `--envelope 8x9 --rooms 5ldk`
- Handles grid snap, area allocation, wet selection, topology

**Hand-author**: [docs/how_to_use.md](docs/how_to_use.md)
- Complete `spec.yaml` schema walkthrough
- Room type and shape rules (including `storage` vs `closet` vs `wic`)
- Buildable mask + balcony/veranda semantics
- Topology best practices and strength levels
- Error-to-fix troubleshooting map (`report.txt`)

## Project Structure

```text
main.py              # solver/renderer entrypoint
gen_spec.py          # spec generator entrypoint
Makefile

plan_engine/
  constants.py
  models.py
  dsl.py
  preflight.py
  stair_logic.py
  io.py
  solver/
  validator/
  renderer/
  structural/
  generator/         # spec generator pipeline
    cli.py           #   CLI + room spec parser
    metrics.py       #   grid snap + floor metrics
    distribute.py    #   room distribution + wet selection
    allocate.py      #   proportional area allocation
    topology.py      #   adjacency generation
    emit.py          #   YAML emission + feasibility check
    profiles.py      #   room profiles + constants

docs/
  how_to_use.md      # manual spec authoring guide
  spec_generator.md  # generator usage guide
examples/
resources/specs/
tests/
openspec/
```

## Troubleshooting

- `dsl_parse_failed`: schema/indent/grid issue in `spec.yaml`
- `preflight:` errors: deterministic feasibility/topology issues before solve
- `solve_failed`: constraints too tight/conflicting
- `valid=False`: check `report.txt` `Errors` section first, then `Diagnostics`

If a bedroom is reachable only through another bedroom, preflight rejects it by design.

For closet/WIC modeling:
- `closet`/`wic` must define `parent_id`
- `wic` parent must be `bedroom` or `master_bedroom`
- `wic` shortest side is constrained to at least `1820mm`
- topology must include at least `wic <-> parent` and normally one circulation edge (`hall`/`entry`/`stair`)
