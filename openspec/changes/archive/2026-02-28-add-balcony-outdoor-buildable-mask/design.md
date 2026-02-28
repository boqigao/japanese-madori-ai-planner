## Context

Current planning assumes one global rectangular envelope and enforces per-floor indoor 100% coverage against that full rectangle. This makes Case 08 balcony intent impossible to model without semantic distortion (e.g., substituting storage as a fake balcony). The change crosses DSL, models, preflight, solver, validator, renderer, and structural analysis, so a design-first approach is required.

Constraints:
- All geometry remains 455mm grid aligned.
- Existing single-envelope specs must continue working without edits.
- Module boundaries remain strict: preflight/solver/validator/renderer/structural responsibilities must not blur.

## Goals / Non-Goals

**Goals:**
- Support per-floor buildable indoor area definitions (initially as unions of axis-aligned rectangular components).
- Support explicit outdoor spaces (`balcony`, `veranda`) with distinct semantics from indoor rooms.
- Change coverage logic to target indoor buildable area per floor, not full envelope.
- Keep topology semantics explicit: indoor reachability is hard; indoor→outdoor access is validated separately.
- Keep backward compatibility via default behavior when new fields are absent.

**Non-Goals:**
- Arbitrary polygon footprints or freeform geometry.
- Climate/daylight optimization.
- Full redesign of all examples in this change.

## Decisions

### Decision 1: Add floor-level indoor buildable masks (rect-union)
- Chosen: each floor can optionally declare `buildable` as one or more grid-aligned rectangles.
- Why: minimal expressive upgrade that enables balcony strips/stepbacks while fitting current rect-based solver.
- Alternative considered: per-floor full envelope replacement only.
  - Rejected: too limited for balcony strips and recess-like layouts.

### Decision 2: Introduce outdoor class semantics, not just room name
- Chosen: add outdoor types (`balcony`, `veranda`) with class-level behavior.
- Why: area accounting, coverage, and validation rules differ from indoor rooms.
- Alternative considered: treat balcony as normal `storage`-like room.
  - Rejected: breaks semantics and produces misleading reports.

### Decision 3: Solver coverage shifts to indoor-buildable target
- Chosen CP-SAT updates:
  - Indoor placement rectangles MUST lie within floor buildable mask.
  - Outdoor spaces are excluded from indoor coverage equation.
  - `used_indoor_area == buildable_indoor_area` per floor.
- Why: preserves 100% utilization discipline while allowing intentional outdoor regions.
- Alternative considered: keep full-envelope coverage and allow negative/exempt areas.
  - Rejected: harder to reason and validate.

### Decision 4: Validator split for circulation semantics
- Chosen:
  - Indoor spaces MUST be reachable from entry.
  - Outdoor spaces MUST have at least one realized adjacency from indoor circulation/eligible rooms, but are not circulation transit hubs.
- Why: matches practical residential use and avoids balcony-as-corridor artifacts.

### Decision 5: Compatibility defaults
- Chosen: if floor buildable mask is absent, derive `buildable = full envelope`.
- Why: preserves existing specs/examples and avoids forced migration.

## Risks / Trade-offs

- [Risk] CP-SAT search space increases due to mask-constrained placement and outdoor class logic. → Mitigation: keep mask geometry rectilinear; add preflight early rejection; review timeout scaling by component count.
- [Risk] Ambiguity in indoor/outdoor topology rules. → Mitigation: explicit validator errors for invalid outdoor links and forbidden transit.
- [Risk] Structural analysis drift if outdoor edges are treated as bearing candidates. → Mitigation: structural extraction consumes indoor/buildable boundaries only.
- [Risk] Renderer confusion with mixed indoor/outdoor boundaries. → Mitigation: add deterministic style palette + legend class labels + opening rules.

## Migration Plan

1. Extend models + DSL parser for optional floor buildable mask and outdoor space classification.
2. Add preflight checks for mask validity (grid alignment, inside envelope, no invalid overlaps, positive buildable area).
3. Update solver coverage/placement constraints to use indoor buildable area semantics.
4. Update validator geometry/connectivity checks with indoor/outdoor split.
5. Update renderer for balcony/veranda visual semantics and opening display.
6. Update structural extraction inputs to indoor/buildable geometry only.
7. Migrate example Case 08 and add regression tests.
8. Rollback plan: disable new semantics by omitting new DSL fields (defaults preserve old behavior).

## Open Questions

- Should outdoor spaces be included in total area summary by default, or reported as a separate subtotal?
- Do we need distinct rules for `balcony` vs `veranda` (e.g., roofed/unroofed), or same semantics in MVP?
- For indoor→outdoor access, should acceptable source spaces be restricted (e.g., disallow toilet→balcony)?
- Should phase-1 buildable mask permit disconnected indoor islands, or require a connected indoor buildable region per floor?
