## Why

Current examples can produce a toilet with no door because `toilet` is modeled as part of one wet-cluster group while topology does not require a toilet circulation edge. This is unrealistic for Japanese detached-house layouts and slips through validation because toilet reachability/door intent is not checked as a hard rule.

## What Changes

- Redefine wet-area semantics in solver: only `washroom` + `bath` are mandatory wet-core coupling targets; `toilet/wc` is independent from that coupling.
- Add hard circulation requirement for each `toilet/wc`: it must have an explicit topology doorway edge to hall/circulation space (not only geometric contact).
- Add preflight checks to fail early when toilet topology is missing or when wet-core minimum adjacency cannot be satisfied.
- Add validator rules to flag toilets that are unreachable via passable topology or only reachable through bedroom pass-through.
- Update benchmark/example specs to match the new topology contract.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `solver`: change wet-cluster constraints so toilet is no longer forced into bath/wash clustering; enforce explicit toilet circulation adjacency.
- `validator`: add hard toilet access checks (door/topology-based reachability and no bedroom pass-through routing).
- `preflight`: detect and reject specs missing mandatory toilet access edges before solve.

## Impact

- Affected modules: `plan_engine/solver/workflow.py`, `plan_engine/preflight.py`, `plan_engine/validator/connectivity.py`, related tests and example specs.
- Affected pipeline stages: preflight, solver, validator.
- Renderer behavior changes indirectly (toilet door appears once topology is guaranteed), without renderer geometry logic changes.
- No new runtime dependencies.

## Non-goals

- No redesign of stair modeling, structural analysis, or exterior/window rendering.
- No introduction of new DSL room types.
- No optimization retuning beyond constraints needed to enforce realistic toilet access.
