## 1. Module Structure & Constants

- [x] 1.1 Create `plan_engine/generator/` package with `__init__.py`. Add submodule stubs: `cli.py`, `metrics.py`, `distribute.py`, `allocate.py`, `topology.py`, `profiles.py`, `emit.py`.
- [x] 1.2 In `plan_engine/generator/profiles.py`: define `ROOM_PROFILE` dict (weight, min, max per room type), `ROOM_WEIGHT` for capacity estimation, `FLEX_CAP` limits, `TOPOLOGY_RULES` template table, and default stair parameters.

## 2. CLI & Room Spec Parser

- [x] 2.1 In `plan_engine/generator/cli.py`: implement argparse CLI with flags: `--envelope` (required), `--rooms`, `--floors`, `--north`, `--stair`, `--f1`, `--f2`, `--closets`, `--output`. Parse `--envelope WxD` (meters) and validate input.
- [x] 2.2 In `plan_engine/generator/cli.py`: implement room spec mini-language parser — parse `type[:count][@target][/min_width][+attachment]` syntax. Handle `wash+bath`, `ws+shower` compound types. Return structured room list.
- [x] 2.3 Add unit tests for room spec parser: single room, count, target, min_width, attachment, compound wet types, malformed input errors.

## 3. Stage 1 — Metrics

- [x] 3.1 In `plan_engine/generator/metrics.py`: implement `compute_metrics(envelope_w_m, envelope_d_m)` — snap to 910mm grid, compute cells per floor, area in tatami. Return a `FloorMetrics` dataclass.
- [x] 3.2 Add unit tests for grid snap: exact alignment, round-up, round-down, edge cases (very small/large values).

## 4. Stage 2 — Room Distribution

- [x] 4.1 In `plan_engine/generator/distribute.py`: implement `distribute_rooms(n_ldk, metrics, stair_type)` — compute F2 capacity, distribute bedrooms across floors, add implied rooms (entry, hall, toilet, wet, storage, closets). Return per-floor room lists.
- [x] 4.2 Implement `--rooms NlDK` shorthand parsing and `--f1`/`--f2` override precedence logic.
- [x] 4.3 Add unit tests: 3LDK/4LDK/5LDK distribution, F1/F2 override, 1F mode (no stair), capacity limits.

## 5. Stage 3 — Wet Module Selection

- [x] 5.1 In `plan_engine/generator/distribute.py`: implement per-floor wet module auto-selection — compute density with standard wet, switch to compact if >85%. Respect user explicit wet type.
- [x] 5.2 Add unit tests: tight floor → compact, spacious floor → standard, user explicit override respected.

## 6. Stage 4 — Area Allocation

- [x] 6.1 In `plan_engine/generator/allocate.py`: implement `allocate_floor(available_jo, rooms, user_overrides)` — deduct user-locked `@target` values, proportionally distribute remainder by weight, clamp to [min, max], detect excess/deficit.
- [x] 6.2 Implement min/max clamp redistribution — when clamped rooms release excess, redistribute to unclamped rooms proportionally.
- [x] 6.3 Add unit tests: normal allocation (8×9 5LDK), large envelope (all hit max), small envelope (near min), user override + auto remainder, impossible configuration error.

## 7. Stage 5 — Topology Generation

- [x] 7.1 In `plan_engine/generator/topology.py`: implement `generate_topology(floor_rooms)` — apply `TOPOLOGY_RULES` template to produce adjacency list. Handle per_bedroom expansion, if_exists filtering, WIC preferred edges.
- [x] 7.2 Add unit tests: standard F1 topology, F2 with compact wet, WIC preferred edge, no false edges for missing rooms.

## 8. YAML Emission & Feasibility Check

- [x] 8.1 In `plan_engine/generator/emit.py`: implement `build_spec(metrics, floor_plans, topology)` — assemble a complete spec dict matching DSL schema v0.2. Serialize with `yaml.safe_dump`.
- [x] 8.2 Implement feasibility self-check — compute per-floor density, print summary table, emit warnings/errors with suggestions. Gate YAML output on no-error status.
- [x] 8.3 Add unit tests: verify output dict structure matches DSL schema, verify density warnings trigger correctly.

## 9. CLI Entrypoint

- [x] 9.1 Create `gen_spec.py` at project root: wire argparse → pipeline stages → YAML output. Handle errors with user-friendly messages.
- [x] 9.2 Add integration test: run `gen_spec.py --envelope 8x9 --rooms 5ldk`, verify output passes `load_plan_spec()` and `run_preflight()` with zero errors.

## 10. End-to-End Validation

- [x] 10.1 Generate specs for multiple configurations (3LDK 9.1×6.4, 5LDK 8×9, 4LDK 10×8, 1F 3LDK 12×8) and verify each passes preflight with zero errors.
- [x] 10.2 Run at least 2 generated specs through the full solver pipeline and confirm they produce valid solutions.
- [x] 10.3 Run `uv run pytest -x -q` — all tests pass.
- [x] 10.4 Run `uv run ruff check plan_engine/ gen_spec.py` — no lint errors.
