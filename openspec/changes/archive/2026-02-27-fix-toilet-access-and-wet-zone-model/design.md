## Context

The current pipeline allows a solved plan where `toilet/wc` exists geometrically but has no declared doorway topology edge, so renderer does not place a toilet door. This comes from two mismatches: (1) solver wet-constraint modeling treats toilet as part of one wet cluster with washroom/bath, and (2) validator connectivity excludes wet spaces from required reachability checks. As a result, unrealistic plans pass validation and appear in examples.

## Goals / Non-Goals

**Goals:**
- Separate wet-core coupling semantics (`washroom` + `bath`) from toilet circulation semantics.
- Require explicit toilet circulation adjacency in topology and in solved realizations.
- Ensure validator catches unreachable toilets and bedroom-pass-through toilet routes.
- Fail early in preflight when required toilet topology contract is missing.
- Keep renderer read-only; door visibility should be fixed by stronger topology guarantees.

**Non-Goals:**
- No changes to stair portal mapping, structural checks, or room shape grammar.
- No new room types or large DSL schema redesign.
- No forced requirement that toilet must physically touch washroom/bath.

## Decisions

1. Split wet constraints into two layers.
- Layer A (wet core): keep/enforce `bath` adjacent to at least one `washroom`.
- Layer B (toilet access): require each `toilet/wc` to have at least one declared topology edge to hall/circulation type and enforce that edge as realized touching.
- Alternative considered: keep current global wet cluster and add validator-only patch. Rejected because solver would still optimize toward unrealistic topology and create avoidable invalid candidates.

2. Add preflight topology contract checks.
- In `plan_engine/preflight.py`, add checks per floor: each toilet must have at least one required/preferred adjacency edge to `hall` (or configured circulation types).
- Alternative considered: solver-only enforcement. Rejected because late failure increases solver iterations and unclear error messages for spec authors.

3. Add validator path-quality checks.
- In `plan_engine/validator/connectivity.py`, include toilets in required-reachability validation and detect paths where all entry→toilet routes traverse another bedroom as transit.
- Alternative considered: pure adjacency check only. Rejected because adjacency alone does not guarantee practical circulation quality.

4. Keep renderer unchanged except behavior through topology.
- No renderer algorithm change; interior door drawing remains topology-driven.
- This preserves module boundaries and avoids hidden geometry-side “auto doors”.

## Risks / Trade-offs

- [Risk] New hard toilet topology requirements may make some legacy specs infeasible.
  → Mitigation: preflight errors with actionable messages and batch-update example specs.
- [Risk] Additional CP-SAT adjacency booleans can increase solve time on dense plans.
  → Mitigation: constrain only toilet-related edges, reuse existing touching booleans where possible, keep timeout defaults unchanged.
- [Risk] Bedroom-pass-through detection may over-flag compact layouts.
  → Mitigation: encode precise rule (“toilet route requires traversing bedroom as intermediate node”) and add targeted tests.

## Migration Plan

1. Update preflight checks and solver constraints together behind the same topology contract.
2. Update validator connectivity and add regression tests for no-door toilet cases.
3. Regenerate benchmark examples and patch specs that violate new contract.
4. If rollout causes excessive infeasible solves, temporarily relax preflight from error to warning for one cycle, then re-enable hard errors after spec updates.

## Open Questions

- Should circulation adjacency for toilet allow only `hall`, or also `entry` when no hall exists on a one-floor minimal plan?
- Should toilet adjacency require `required` strength specifically, or allow `preferred` with validator hard-fail if unrealized?
- Should we expose the allowed toilet-neighbor types as a DSL-level configurable policy, or keep it fixed in constants for MVP?
