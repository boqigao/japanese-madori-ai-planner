## Why

Writing a valid `spec.yaml` by hand requires deep knowledge of grid alignment rules, wet module sizing, area budgeting, topology constraints, and stair configuration. Users frequently produce specs that pass preflight but fail to solve — usually due to density over-packing or missing topology edges. A spec generator that accepts high-level requirements (envelope size, room count) and outputs a "highly likely solvable" spec.yaml would dramatically lower the barrier to entry and reduce iteration cycles.

## What Changes

- **New CLI tool `gen_spec.py`**: Accepts structured flags (`--envelope`, `--rooms`, `--f1`, `--f2`, etc.) and outputs a complete `spec.yaml`.
- **Room spec mini-language**: Concise syntax for specifying rooms — `bed:3@6/1820` means 3 bedrooms, 6 tatami target, 1820mm min_width. Supports count, area target, min_width, and attachments (`master+wic`).
- **5-stage derivation pipeline**: Grid snap → room distribution → wet module selection → proportional area allocation → topology generation. All stages are deterministic (no AI reasoning).
- **Proportional area allocation with min/max clamps**: Every room type has a weight, min, and max. Available area is distributed proportionally. User `@target` overrides are respected first, remaining rooms auto-allocate.
- **Feasibility self-check**: Before writing YAML, the generator prints per-floor density reports and warns when targets are too tight or too loose, with actionable suggestions.
- **Wet module auto-selection**: Automatically chooses compact (`ws+shower`) vs standard (`wash+bath`) per floor based on density threshold (>85% → compact).

## Non-goals

- Non-rectangular envelopes (recess, stepback, buildable_mask) — v1 supports rectangular only.
- Multi-stair configurations — v1 assumes single shared stair for 2F.
- Interactive / conversational mode — v1 is a single-shot CLI command.
- Auto-solving after generation — generator only outputs spec.yaml, user runs solver separately.

## Capabilities

### New Capabilities
- `spec-generator`: The core generation pipeline — CLI interface, room spec parsing, 5-stage derivation (metrics → room distribution → wet selection → area allocation → topology generation), feasibility check, YAML output.

### Modified Capabilities
(none — this is a standalone new tool that consumes the existing spec format)

## Impact

- **New file**: `gen_spec.py` (CLI entrypoint) at project root, alongside existing `main.py`.
- **New module**: `plan_engine/generator/` — pipeline stages, room profiles, topology templates, YAML serializer.
- **Dependencies on existing modules**: Reads constants from `plan_engine/constants.py` (grid sizes, wet module sizes, room type sets). Reuses `plan_engine/models.py` dataclasses for spec construction. Does NOT depend on solver, renderer, or validator.
- **Affected modules**: None modified. This is purely additive — new code only.
- **No changes to**: preflight, solver, renderer, validator, or structural modules.
