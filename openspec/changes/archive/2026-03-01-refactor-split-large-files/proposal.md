## Why

Six source files in `plan_engine/` exceed 500 lines (the largest being `solver/workflow.py` at 1,166 lines), making navigation, code review, and maintenance harder than necessary. Splitting them along natural logical boundaries will improve readability without changing any runtime behavior.

## What Changes

- **Split `plan_engine/solver/workflow.py`** (1,166 lines) into 3 focused modules: context setup, space variable creation, and constraint groups.
- **Split `plan_engine/preflight.py`** (1,081 lines) into 3 focused modules: core orchestrator + area/envelope checks, topology reachability, and wet-module/circulation checks.
- **Split `plan_engine/renderer/core.py`** (1,067 lines) by extracting fixture drawing and door/window drawing into new sub-modules.
- **Split `plan_engine/models.py`** (632 lines) into a `models/` package with separate files for spec types, solution types, structural types, and validation types.
- **Split `plan_engine/dsl.py`** (599 lines) by extracting closet parsing into a separate module.
- **Split `plan_engine/renderer/dimensions.py`** (523 lines) by extracting interior dimension guides from the exterior dimension chain system.
- Move shared frozenset constants (`TOILET_SPACE_TYPES`, `WET_CORE_SPACE_TYPES`, `CIRCULATION_SPACE_TYPES`) currently duplicated in `workflow.py` and `preflight.py` into `constants.py`.
- All `__init__.py` re-exports preserved so external imports remain unchanged — **no breaking changes**.

## Non-goals

- No behavioral changes, new features, or bug fixes.
- No changes to public APIs or function signatures.
- No test logic changes (only import paths may be updated).
- No changes to modules already under 500 lines.

## Capabilities

### New Capabilities

(none — this is a pure refactoring)

### Modified Capabilities

(none — no spec-level behavior changes)

## Impact

- **Affected modules**: `preflight`, `solver`, `renderer`, `models`, `dsl`
- **Affected code**: Import paths in ~30 source files and ~20 test files may need updating.
- **APIs**: No public API changes. Re-exports via `__init__.py` ensure backward compatibility.
- **Dependencies**: No new external dependencies.
- **Risk**: Low — pure structural refactor. All existing tests must pass unchanged.
