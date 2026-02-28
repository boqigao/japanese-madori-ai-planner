## Context

The solver currently optimizes area, topology, compactness, and some room-shape quality, but it does not include directional livability preferences. In the benchmark outputs, this causes repeated anti-patterns: hall or wet/storage taking south-facing edges while LDK/bedrooms are pushed inward or north-side. The project already has `site.north` in DSL/PlanSpec, so orientation can be derived without schema changes.

This change is cross-cutting for solver objective shaping and validator interpretability, while keeping strict module boundaries: no renderer geometry edits and no new hard feasibility constraints.

## Goals / Non-Goals

**Goals:**
- Add orientation-aware soft objective terms in solver using `site.north`.
- Prefer major habitable spaces (`ldk`, `bedroom`, `master_bedroom`) to touch the inferred south boundary.
- Prefer service spaces (`washroom`, `bath`, `toilet`/`wc`, `storage`) to touch the inferred north boundary.
- Keep orientation as optimization preference (soft), not hard constraints.
- Emit validator warnings/diagnostics summarizing unmet orientation preferences.

**Non-Goals:**
- No change to DSL schema or units.
- No sunlight/daylight simulation.
- No window-placement redesign.
- No stair-type policy changes.

## Decisions

### 1) Direction mapping from `site.north`
- Decision: derive the south and north envelope edges per floor from `site.north` (`top/right/bottom/left`) and reuse this mapping in both solver and validator.
- Why: deterministic, no schema migration, and aligns with existing coordinate model.
- Alternative: add per-floor preferred facade in DSL.
- Rejected: introduces new schema complexity and migration work.

### 2) Objective formulation as edge-touch penalties
- Decision: add orientation penalty booleans in `plan_engine/solver/workflow.py` that measure whether each room group realizes required facade touch; unmet preference contributes weighted objective penalty.
- Why: fits existing CP-SAT pattern (`touching_constraint`/soft penalties), keeps model linear and explainable.
- Alternative: maximize south-overlap length in mm directly.
- Rejected: adds more integer vars/expressions and higher solve-time risk.

### 3) Weight profile
- Decision: place orientation weights in `plan_engine/solver/space_specs.py` (or a dedicated table there) with stronger south preference for `ldk`, then `master_bedroom`, then `bedroom`; moderate north preference for wet/storage.
- Why: centralized weight tuning consistent with current shortfall/overshoot weight management.
- Alternative: hardcoded constants inside workflow.
- Rejected: harder tuning and poorer maintainability.

### 4) Validator feedback as warnings (not errors)
- Decision: validator adds warning/diagnostic lines when orientation preferences are not satisfied.
- Why: objective preference can be traded off for feasibility/topology; failing hard would conflict with soft objective semantics.
- Alternative: hard validation error for any unmet preference.
- Rejected: would convert soft optimization intent into brittle hard gating.

## Risks / Trade-offs

- [Risk] Added objective terms may increase solve time in dense programs.
  - Mitigation: use coarse touch booleans, reuse existing edge-touch helpers, and cap penalty term count per space entity.
- [Risk] Overweighting orientation can inflate hall detours or degrade wet clustering quality.
  - Mitigation: keep hall overshoot and topology penalties active; tune weights by benchmark sweep.
- [Risk] Ambiguous user expectation on “south priority” strength.
  - Mitigation: expose clear report diagnostics and keep weights documented/tunable.

## Migration Plan

1. Add orientation edge-resolution utility from `site.north`.
2. Add soft orientation penalty construction to solver workflow and integrate into objective.
3. Add weight constants and unit tests for mapping and penalty behavior.
4. Add validator orientation diagnostics/warnings.
5. Regenerate benchmark examples and compare directional outcomes.
6. Rollback plan: remove new orientation penalty terms and weight table, retaining pre-existing objective stack.

## Open Questions

- Should hall receive explicit south-avoid penalty, or is positive preference for major/service rooms sufficient?
- Should floor-level preference differ (for example weaker south preference on F2 bedrooms in narrow lots)?
- Do we need future DSL knobs for user-configurable orientation strictness?
