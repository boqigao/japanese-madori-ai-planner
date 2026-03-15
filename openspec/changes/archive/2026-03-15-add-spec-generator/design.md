## Context

Users currently write `spec.yaml` files by hand, which requires deep domain knowledge of grid alignment, wet module sizing, area budgeting, and topology rules. Even experienced users frequently produce specs that are technically valid (pass preflight) but unsolvable by the CP-SAT solver — typically due to over-packing or missing adjacency edges.

The generator is a standalone CLI tool that accepts high-level inputs (envelope size, room count) and deterministically derives a complete, solvable spec. It reuses existing constants and models but does NOT touch the solver, renderer, or validator pipeline.

## Goals / Non-Goals

**Goals:**
- Accept minimal input (`--envelope 8x9 --rooms 5ldk`) and produce a solvable spec.yaml
- Support granular overrides (`--f1 "ldk@18, bed@6"`) for power users
- Print feasibility diagnostics before writing YAML
- Generate specs that pass preflight and solve successfully in >95% of cases

**Non-Goals:**
- Non-rectangular envelopes (recess, stepback, buildable_mask)
- Multi-stair or spiral stair configurations
- Interactive / conversational refinement mode
- Auto-running the solver after generation
- Supporting 3+ floor buildings

## Decisions

### Decision 1: 5-stage deterministic pipeline

**Choice:** Decompose generation into 5 sequential stages: metrics → room distribution → wet selection → area allocation → topology generation.

**Why:** Each stage makes one category of decisions with clear inputs/outputs. This avoids entangled logic and makes each stage independently testable. The sequential dependency is real — room distribution needs metrics, wet selection needs room counts, area allocation needs wet module sizes.

**Alternative considered:** Single-pass template system (pick a template by nLDK+envelope). Rejected because the combinatorial space is too large (envelope is continuous, nLDK ranges 1-6, wet type varies per floor) and templates can't handle user overrides.

### Decision 2: Proportional area allocation with min/max clamps

**Choice:** All variable-size rooms receive area proportional to their weight. User `@target` overrides are subtracted first, remaining space distributed among auto rooms. Min/max clamps prevent absurdly small or large rooms.

```python
ROOM_PROFILE = {
    #                weight   min     max
    "ldk":           (5.0,   12.0,   28.0),
    "master_bedroom":(3.0,    6.0,   14.0),
    "bedroom":       (2.0,    4.5,   10.0),
    "hall":          (1.5,    3.0,    7.0),
    "entry":         (0.8,    1.5,    3.5),
    "storage":       (1.0,    1.5,    5.0),
    "closet":        (0.4,    0.75,   2.0),
    "wic":           (0.8,    1.5,    3.5),
}
```

**Why:** Fixed targets fail at extreme envelope sizes — a 10×12 house with bedroom@6 produces a 49jo LDK (absurd), while a 7×7 house with bedroom@6 can't fit 5 bedrooms. Proportional allocation naturally scales to any envelope while maintaining room-to-room proportions.

**Alternative considered:** Fixed base targets with LDK as residual absorber. Rejected because it produces wildly unbalanced layouts when the envelope is significantly larger or smaller than the "typical" case.

### Decision 3: Room spec mini-language

**Choice:** Inline DSL for room specifications in CLI flags.

```
type[:count][@target][/min_width][+attachment]

bed:3@6/1820    → 3 bedrooms, 6jo each, 1820mm min_width
master+wic@8+2  → master 8jo + WIC 2jo
wash+bath       → standard wet pair
ws+shower       → compact wet pair
```

**Why:** Balances expressiveness with CLI ergonomics. Users can specify as little as `bed:3` or as much as `bed:3@6/1820`. The `@` marker distinguishes user-locked targets from auto-allocated ones.

**Alternative considered:** Separate flags per room (`--ldk-target 18 --bed-count 3 --bed-target 6`). Rejected because the flag count explodes with room count and doesn't support per-floor differentiation.

### Decision 4: Density-driven wet module auto-selection

**Choice:** Per-floor decision — if target density exceeds 85% with standard wet (wash+bath), automatically switch to compact wet (ws+shower) to save ~2.5 tatami.

**Why:** F2 of 2-story houses frequently has tight area budgets (many bedrooms + closets). Compact wet saves significant area without user intervention. The 85% threshold is derived from successful example analysis (75-85% target density is the safe zone).

**Alternative considered:** Always use standard wet unless user explicitly specifies `ws+shower`. Rejected because many configurations would produce warnings or unsolvable specs, defeating the "works by default" goal.

### Decision 5: Topology generation via template rules

**Choice:** A declarative rule table maps room types to adjacency edges with strength (required/preferred).

```python
TOPOLOGY_RULES = [
    ("always",       "entry",     "hall",      "required"),
    ("always",       "hall",      "stair",     "required"),
    ("always",       "hall",      "ldk",       "required"),
    ("if_exists",    "hall",      "toilet",    "required"),
    ("if_exists",    "hall",      "washroom",  "required"),
    ("if_exists",    "hall",      "washstand", "required"),
    ("if_exists",    "washroom",  "bath",      "required"),
    ("if_exists",    "washstand", "shower",    "required"),
    ("if_exists",    "hall",      "storage",   "required"),
    ("per_bedroom",  "hall",      "{bed}",     "required"),
    ("per_bedroom",  "{bed}",     "{bed_cl}",  "required"),
    ("if_wic",       "{master}",  "{wic}",     "preferred"),
]
```

**Why:** All 10 existing examples follow this pattern. The rule table is easy to extend and validate. Using `preferred` for WIC-master (not `required`) matches proven patterns from examples 2 and 3.

### Decision 6: Module placement as `plan_engine/generator/`

**Choice:** New `plan_engine/generator/` package with submodules per pipeline stage. CLI entrypoint at `gen_spec.py` (project root).

**Why:** Keeps generator logic inside plan_engine for shared constant/model access while maintaining clear separation from the solve/render pipeline. The generator never imports from solver, renderer, or validator — only from constants and models.

### Decision 7: Two input modes with clear priority

**Choice:** `--rooms NlDK` shorthand and `--f1`/`--f2` detailed mode. If both provided, `--f1`/`--f2` takes full priority (overrides `--rooms`).

**Why:** Simple for beginners (`--rooms 5ldk`), powerful for advanced users (`--f1 "ldk@18, ..." --f2 "master@12, ..."`). No ambiguous merging — explicit wins.

## Risks / Trade-offs

- **[Weight/min/max values may need tuning]** → Initial values are derived from 10 existing examples. The profile table is a single constant — easy to adjust after real-world testing. Add integration tests that verify generated specs solve successfully.
- **[Room spec parser complexity]** → The mini-language (`bed:3@6/1820+cl`) has several optional parts. Implement with a small regex-based parser with clear error messages for malformed input.
- **[Stair footprint estimation]** → Generator needs to estimate stair cell consumption without running the full stair computation. Use a conservative estimate based on stair type (U_turn ≈ 12 cells, L_landing ≈ 12 cells, straight ≈ 6-8 cells).
- **[Generated spec may still fail to solve]** → The generator targets >95% success rate, not 100%. Include a "try running with --solver-timeout 120" suggestion in output. Users can adjust targets and re-generate.

## Open Questions

- Exact weight/min/max profile values — need statistical validation against all 10 examples before finalizing.
- Should the generator support `--adj` for manual topology overrides in v1, or defer to v2?
- Rounding strategy for target_tatami — round to 0.5jo increments for clean specs, or use exact proportional values?
