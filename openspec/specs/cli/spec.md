# CLI Specification

## Purpose
Defines the command-line interface that orchestrates the full pipeline: DSL parsing, solving, validation, and rendering. The CLI is the primary user entrypoint via `main.py`.

## Requirements

### Requirement: Pipeline Orchestration
The system MUST execute the full pipeline in order: DSL parse → Solve → Validate → Render.

#### Scenario: Successful run
- GIVEN a valid YAML spec file and an output directory
- WHEN the user runs `python main.py --spec <path> --outdir <path>`
- THEN the system parses the spec, solves the layout, validates, renders SVG/PNG, and writes all output files

### Requirement: Required Arguments
The system MUST require a `--spec` argument pointing to a YAML specification file.

#### Scenario: Missing spec argument
- GIVEN no `--spec` argument is provided
- WHEN the user runs `python main.py`
- THEN an error message is displayed indicating `--spec` is required

### Requirement: Output Directory
The system MUST write output files to the directory specified by `--outdir` (default: `output/`).

#### Scenario: Custom output directory
- GIVEN `--outdir tmp/plan_output`
- WHEN the pipeline completes
- THEN `solution.json`, floor SVGs, floor PNGs, and `report.txt` are written to `tmp/plan_output/`

### Requirement: Solver Timeout Configuration
The system MUST accept a `--solver-timeout` flag to control the maximum CP-SAT solve time in seconds.

#### Scenario: Custom timeout
- GIVEN `--solver-timeout 10`
- WHEN the solver runs
- THEN the solver is limited to 10 seconds of computation time

### Requirement: Output Files
The system MUST produce `solution.json`, `{floor_id}.svg`, `{floor_id}.png`, and `report.txt` in the output directory.

#### Scenario: Complete output
- GIVEN a successful pipeline run for a 2-floor plan
- WHEN the output directory is inspected
- THEN it contains: `solution.json`, `1F.svg`, `1F.png`, `2F.svg`, `2F.png`, `report.txt`
