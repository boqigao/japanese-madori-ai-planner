# CLI Specification

## Purpose
Defines the command-line interface that orchestrates the full pipeline: DSL parsing, preflight feasibility checks, solving, validation, and rendering. The CLI is the primary user entrypoint via `main.py`.

## Requirements

### Requirement: Pipeline Orchestration
The system MUST execute the full pipeline in order: DSL parse → Preflight → Solve → Validate → Render.

#### Scenario: Successful run
- GIVEN a valid YAML spec file and an output directory
- WHEN the user runs `python main.py --spec <path> --outdir <path>`
- THEN the system parses the spec, runs preflight checks, solves the layout, validates, renders SVG/PNG, and writes all output files

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
The system MUST accept a `--solver-timeout` flag to control the maximum CP-SAT solve time in seconds (default: 20).

#### Scenario: Custom timeout
- GIVEN `--solver-timeout 10`
- WHEN the solver runs
- THEN the solver is limited to 10 seconds of computation time

### Requirement: Output Files
The system MUST produce `solution.json`, `{floor_id}.svg`, `{floor_id}.png`, and `report.txt` in the output directory.

#### Scenario: Complete output
- GIVEN a successful pipeline run for a 2-floor plan
- WHEN the output directory is inspected
- THEN it contains: `solution.json`, `F1.svg`, `F1.png`, `F2.svg`, `F2.png`, `report.txt`

### Requirement: Distinct Exit Codes
The system MUST return distinct exit codes for each failure mode.

#### Scenario: DSL parse failure
- GIVEN an invalid YAML spec file
- WHEN the parser raises an exception
- THEN the system writes a report with `dsl_parse_failed` and exits with code 2

#### Scenario: Preflight failure
- GIVEN a spec that fails preflight feasibility checks (e.g., minimum area exceeds envelope)
- WHEN the preflight checker detects errors
- THEN the system writes a report with preflight errors and exits with code 3

#### Scenario: Solver failure
- GIVEN a spec that the solver cannot satisfy within the timeout
- WHEN the solver raises an exception
- THEN the system writes a report with solver failure diagnostics, preflight warnings, and floor stats, and exits with code 3

#### Scenario: Validation failure
- GIVEN a solved plan that fails validation checks
- WHEN validation reports errors
- THEN the system writes a report and exits with code 4

### Requirement: Preflight Integration
The system MUST run preflight checks before solving and merge preflight warnings, diagnostics, and suggestions into the final report.

#### Scenario: Preflight warnings carried forward
- GIVEN a spec that passes preflight with warnings
- WHEN the pipeline completes successfully
- THEN the final report includes both preflight warnings and validation findings
