## Why

The current system conflates `storage`, `closet`, and `walk-in closet` semantics, so generated plans frequently miss bedroom closet intent and produce misleading topology. This now blocks benchmark fidelity and makes generated output diverge from real Japanese detached-house conventions.

## What Changes

- Define explicit semantics for three storage-related concepts:
  - `storage`: independent room-level storage space.
  - `closet`: built-in storage allocated inside a parent room (typically bedroom), not rendered as a standalone room.
  - `wic` (walk-in closet): enterable closet zone associated with a parent room and represented with clear connectivity rules.
- Extend DSL to express bedroom closet requirements without forcing users to model closets as generic storage rooms.
- Update solver objectives/constraints to place and reserve closet/WIC geometry consistently with parent-room topology and circulation.
- Update renderer so closet/WIC are visually distinguishable from storage rooms and do not create misleading inter-bedroom door symbols.
- Add validator/preflight checks for closet assignment integrity, door placement legality, and reachability for closet-access paths.

## Capabilities

### New Capabilities
- `closet-semantics`: first-class closet and walk-in closet modeling, from DSL input through solved geometry and rendered output.

### Modified Capabilities
- `dsl`: support closet/WIC declarations and validation rules.
- `solver`: add closet/WIC placement constraints and adjacency behavior.
- `renderer`: add closet/WIC visual treatment and door-symbol filtering.
- `validator`: validate closet/WIC connectivity and topology correctness.
- `preflight`: reject contradictory closet/WIC declarations before solve.

## Non-goals

- Reworking global architecture boundaries (preflight/solver/validator/renderer separation remains unchanged).
- Replacing existing `storage` behavior for users who do not opt into closet/WIC semantics.
- Introducing furniture-level interior design optimization beyond closet zones.

## Impact

- Affected modules: `plan_engine/dsl.py`, `plan_engine/preflight.py`, `plan_engine/solver/*`, `plan_engine/renderer/*`, `plan_engine/validator/*`, and related dataclasses/constants.
- Specs: one new capability spec plus delta updates to existing capability specs.
- Outputs: `solution.json` and floor SVG/PNG include explicit closet/WIC semantics, improving benchmark alignment.
