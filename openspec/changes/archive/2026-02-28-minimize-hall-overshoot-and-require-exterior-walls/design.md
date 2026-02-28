## Context

Current generated plans still produce oversized halls and occasionally place major habitable rooms (bedroom/master/LDK) in interior positions without exterior contact. This conflicts with practical residential expectations from professional feedback (`local-dev/floor-feedback/v8/professional.md`).

The change touches multiple modules: solver objective tuning, solver hard constraints, preflight feasibility diagnostics, and post-solve validator guarantees. It must preserve existing architecture boundaries: preflight only predicts feasibility, solver enforces constraints, validator verifies solved output.

## Goals / Non-Goals

**Goals:**
- Reduce hall over-expansion tendency by increasing hall overshoot penalty in objective shaping.
- Enforce a hard exterior-touch rule for `bedroom`, `master_bedroom`, and `ldk` spaces.
- Provide deterministic early feedback when specs make exterior-touch impossible.
- Ensure validator rejects any plan violating the new exterior-touch requirement.

**Non-Goals:**
- No orientation optimization (south-facing preference) in this change.
- No window object generation or daylight scoring model.
- No stair-type policy redesign.

## Decisions

### 1) Raise hall overshoot penalty at objective-weight layer
- **Decision:** increase `OVERSHOOT_WEIGHT_BY_TYPE["hall"]` in `plan_engine/solver/space_specs.py` and keep hall-area penalty term in objective.
- **Why:** this is the least invasive way to prioritize compact circulation while keeping feasibility flexibility.
- **Alternative considered:** add hard max hall area cap per floor.
- **Rejected because:** hard caps can create unnecessary infeasibility on tight programs.

### 2) Add hard exterior-touch constraints for major habitable spaces
- **Decision:** in solver workflow, for each `bedroom`/`master_bedroom`/`ldk`, enforce at least one component touching envelope boundary (using existing exterior-touch primitives).
- **Why:** guarantees no interior-only major rooms in accepted solutions.
- **Alternative considered:** validator-only check.
- **Rejected because:** validator-only would repeatedly solve invalid candidates and fail late.

### 3) Add preflight feasibility diagnostic for exterior-touch rule
- **Decision:** preflight checks whether floor buildable mask has any envelope-contact boundary when required room types exist.
- **Why:** catches obviously impossible specs before CP-SAT runtime.
- **Alternative considered:** no preflight addition.
- **Rejected because:** user feedback quality suffers when failure appears only as generic INFEASIBLE.

### 4) Add validator hard checks mirroring solver rule
- **Decision:** validator geometry stage explicitly errors when any required space type lacks exterior touch.
- **Why:** defense in depth and output-contract clarity.

## Risks / Trade-offs

- [Risk] Stronger hall overshoot penalty may push excess area into storage/bedrooms in edge cases.  
  → Mitigation: calibrate weight increment conservatively and verify across example suite.
- [Risk] Exterior-touch constraints reduce solver solution space and may increase infeasibility for dense specs.  
  → Mitigation: add preflight diagnostic and guidance text for affected floors.
- [Risk] Additional adjacency/exterior booleans may slightly increase solve time.  
  → Mitigation: reuse existing constraint helpers and benchmark with standard 10-example run.

## Migration Plan

1. Update solver weights and add new exterior-touch hard constraints.
2. Add preflight diagnostics and validator checks.
3. Update/add tests for objective shaping and exterior-touch validity.
4. Regenerate and review benchmark outputs; adjust impacted spec targets if needed.
5. If regression is severe, rollback by reverting new exterior-touch constraint block and weight changes.

## Open Questions

- Should this rule eventually include `study` and other habitable room types beyond bedroom/master/LDK?
- Do we want a configurable strictness flag (hard vs soft) for exterior-touch in future phases?
