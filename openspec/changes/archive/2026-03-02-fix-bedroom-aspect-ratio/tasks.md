## 1. Tighten Hard Constraint

- [x] 1.1 In `plan_engine/solver/workflow_spaces.py` lines 221-222, change `2 * rect.w <= 5 * rect.h` to `3 * rect.w <= 5 * rect.h` and `2 * rect.h <= 5 * rect.w` to `3 * rect.h <= 5 * rect.w` for bedroom/master_bedroom types.
- [x] 1.2 Add unit test in `tests/solver/` verifying that the solver rejects a bedroom configuration with ratio > 1:1.67 (e.g., 5 cells x 12 cells) and accepts ratio ≤ 1:1.67 (e.g., 5 cells x 8 cells).

## 2. Verification

- [x] 2.1 Run `uv run pytest -x -q` to verify all existing tests pass.
- [x] 2.2 Run `uv run ruff check plan_engine/` to verify no lint errors.
- [x] 2.3 Regenerate all 10 examples in `./examples/` (in parallel) and verify: all solve successfully, no bedroom exceeds 1:1.80 ratio.
- [x] 2.4 Run `make verify` for end-to-end validation.
