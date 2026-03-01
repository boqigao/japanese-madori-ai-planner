## Context

The current pipeline already supports room-level `storage` and room-level connectivity constraints, but it does not represent built-in closet intent from Japanese residential plans. Benchmark feedback shows two concrete gaps: (1) bedroom closet intent is being modeled as standalone storage rooms, and (2) rendered door symbols can imply illegal circulation between private rooms. This change spans `dsl`, `preflight`, `solver`, `validator`, and `renderer`, so design-level alignment is required before implementation.

## Goals / Non-Goals

**Goals:**
- Introduce first-class closet semantics that distinguish `closet` (built-in) from `wic` (walk-in) and `storage` (room-level).
- Preserve strict module boundaries while propagating closet semantics from input to solve, validate, and render.
- Prevent misleading door symbols (especially bedroom-to-bedroom visual doors).
- Keep solver feasible under existing timeout budgets by using bounded additional constraints.

**Non-Goals:**
- Replacing full room-packing strategy or introducing furniture-level optimization.
- Requiring every plan to define closets/WIC.
- Converting all existing `storage` spaces automatically into closets.

## Decisions

1. Closet taxonomy and data model
- Decision: add explicit semantic categories: `storage` (independent room), `closet` (non-enterable built-in zone), and `wic` (enterable closet zone attached to a parent room).
- Rationale: user intent differs materially across these categories, and merged semantics produce invalid benchmarks.
- Alternative considered: keep only `storage` and emulate closets by naming convention; rejected because it is ambiguous and untestable.

2. Solver geometry strategy
- Decision: model closet/WIC as parent-associated geometry with deterministic constraints, not as unconstrained generic rooms.
- Rationale: keeps bedroom topology coherent and avoids creating fake circulation corridors through closet artifacts.
- Alternative considered: fully independent room modeling for all closet types; rejected because it recreates the current semantic confusion.

3. Door and connectivity policy
- Decision: renderer door symbols are emitted only for validated topology edges that pass type-policy checks, and bedroom-to-bedroom door symbols are always suppressed. Validator enforces closet/WIC access consistency.
- Rationale: visuals must reflect legal circulation, not mere geometric contact.
- Alternative considered: allow explicit bedroom-to-bedroom openings; rejected in current phase to avoid privacy-breaking interpretations in benchmark outputs.

4. Preflight and validation layering
- Decision: preflight checks static declaration consistency; validator checks solved topology and access paths.
- Rationale: impossible specs fail early; solve-time regressions are caught post-solve with actionable errors.
- Alternative considered: defer all checks to validator; rejected because it wastes solver time on invalid inputs.

5. Performance guardrails
- Decision: closet/WIC constraints use bounded adjacency booleans and existing edge-touch primitives; avoid occupancy-grid expansion.
- Rationale: limits CP-SAT variable growth and preserves solver timeout behavior.
- Alternative considered: cell-level occupancy constraints for closet interiors; rejected for high complexity.

## Risks / Trade-offs

- [Risk] Additional closet constraints increase CP-SAT search space on dense two-floor specs. → Mitigation: keep closet models bounded and optional; tune soft penalties conservatively.
- [Risk] Backward compatibility issues for older specs using `storage` to mean closet. → Mitigation: keep `storage` behavior unchanged and add explicit migration guidance in docs.
- [Risk] Door suppression rules may hide legitimate doors when topology is underspecified. → Mitigation: validator emits targeted warnings when expected access edges are missing.
- [Risk] Semantic overlap between `wic` and small storage rooms may confuse users. → Mitigation: enforce parent-room association rules and naming conventions in DSL/preflight.

## Migration Plan

1. Extend DSL schema and models to accept closet/WIC declarations while preserving existing specs.
2. Add preflight checks for declaration consistency and parent references.
3. Add solver constraints/objective hooks for closet/WIC placement and access policy.
4. Add validator checks for closet/WIC topology and reachability.
5. Update renderer legend, styling, and door-symbol filtering.
6. Update benchmark specs to explicitly use closet/WIC where intended.
7. Run regression on benchmark examples and compare report diagnostics before/after.

Rollback strategy: disable closet/WIC-specific solver and renderer branches behind feature checks while keeping parser backward-compatible.

## Open Questions

- Should `closet` always be non-enterable in MVP, or can it optionally expose a door opening in advanced mode?
- Should `wic` be required to connect directly to exactly one parent bedroom, or allow hall-only access in specific spec flags?
- Should benchmark migration prefer converting some existing `storage` to `wic` automatically via helper tooling?
