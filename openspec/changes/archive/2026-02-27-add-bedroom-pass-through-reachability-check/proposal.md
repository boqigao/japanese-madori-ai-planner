## Why

Several benchmark specs still permit bedroom access that requires traversing another bedroom, which is unrealistic for detached-house circulation and causes invalid examples to pass early checks. We need a deterministic preflight rule to fail these topologies before solve, and we need benchmark specs updated to satisfy that rule.

## What Changes

- Add a preflight bedroom reachability rule that rejects specs where any bedroom can only be reached through one or more bedrooms.
- Define explicit traversal semantics for preflight circulation graph construction (hall, entry, stair portals, non-bedroom rooms) to avoid ambiguous pass-through behavior.
- Add machine-readable warning/error output in preflight diagnostics for blocked bedrooms, including the path evidence.
- Update benchmark `examples/*/spec.yaml` topologies so bedroom reachability no longer depends on crossing other bedrooms.
- Add regression tests covering positive and negative bedroom-reachability cases.

## Capabilities

### New Capabilities
- `bedroom-pass-through-reachability`: Preflight circulation feasibility checks that detect bedroom-only access chains and provide actionable diagnostics.

### Modified Capabilities
- `preflight`: Extend preflight validation requirements to include bedroom reachability topology constraints and enforce failure on violation.

## Impact

- Affected modules: `plan_engine/preflight.py`, `plan_engine/models.py` (diagnostic payload if needed), `main.py` (preflight reporting path), and benchmark assets under `examples/*/spec.yaml`.
- Affected system stages: preflight (primary), CLI/reporting (secondary).
- No rendering geometry changes and no CP-SAT objective changes.
- Existing specs with bedroom pass-through circulation will fail fast until corrected.

## Non-goals

- Do not redesign the solver adjacency model or add new CP-SAT hard constraints for this change.
- Do not alter renderer styling or door symbol drawing.
- Do not introduce multi-floor evacuation or fire-code compliance modeling beyond bedroom reachability.
