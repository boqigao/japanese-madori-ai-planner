# Repository Guidelines

## Project Structure & Module Organization
- `main.py`: CLI entrypoint. Orchestrates `DSL -> solve -> validate -> render`.
- `plan_engine/`: core package.
  - `dsl.py`: YAML spec parsing and schema checks.
  - `solver.py`: CP-SAT layout generation.
  - `validator.py`: post-solve hard checks.
  - `renderer.py`: SVG/PNG output only (no geometry mutation).
  - `models.py`, `constants.py`, `io.py`: shared types/constants/output helpers.
- `local-dev/coding-prompts/requirements.md`: MVP design reference.
- `tmp/`: local specs and generated artifacts (treat as scratch space).

## Build, Test, and Development Commands
- `uv sync`: install/update dependencies from `pyproject.toml` and `uv.lock`.
- `uv run python main.py --spec tmp/sample_spec.yaml --outdir tmp/plan_output --solver-timeout 10`: run end-to-end generation.
- `python -m compileall main.py plan_engine`: quick syntax check before commits.
- If/when tests are added: `uv run pytest`.

## Coding Style & Naming Conventions
- Python 3.13+, 4-space indentation, PEP 8 style.
- Prefer explicit type hints on public functions and dataclass fields.
- Naming:
  - modules/functions/variables: `snake_case`
  - classes/dataclasses: `PascalCase`
  - constants: `UPPER_SNAKE_CASE`
- Keep architectural boundaries strict:
  - solver must not render;
  - renderer must not alter solved geometry;
  - validator must run on solved output.

## Testing Guidelines
- Current repo has no formal `tests/` suite yet; add new tests under `tests/`.
- Use `pytest` naming conventions: files `test_*.py`, functions `test_*`.
- Prioritize regression tests for:
  - grid alignment (`% 455 == 0`)
  - no overlap / inside envelope
  - mandatory space presence
  - stair-floor alignment and hall adjacency

## Commit & Pull Request Guidelines
- Follow Conventional Commits where possible (e.g., `feat:`, `fix:`, `refactor:`).
- PRs should include:
  - purpose and scope,
  - sample spec used,
  - validation result (`report.txt` summary),
  - output impact (attach or reference `F1/F2` SVG/PNG when layout behavior changes).
- Avoid committing transient files (`__pycache__/`, `.venv/`, ad-hoc `tmp/` outputs) unless intentionally required as fixtures.

