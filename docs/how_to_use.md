# How to Use This Project

This guide is for users who want to create a valid `spec.yaml` from scratch and generate realistic Japanese detached-house floor plans.

> **Tip:** If you want to skip hand-authoring, use the **Spec Generator** to create a `spec.yaml` automatically from envelope size and room count. See [docs/spec_generator.md](spec_generator.md) or run:
> ```bash
> uv run python gen_spec.py --envelope 8x9 --rooms 5ldk
> ```

## 1. Mental Model

The engine is strict and deterministic before solving:

1. **DSL parse** (`plan_engine/dsl.py`): schema + grid alignment checks
2. **Preflight** (`plan_engine/preflight.py`): feasibility/topology checks
3. **Solver** (`plan_engine/solver/*`): CP-SAT layout search
4. **Validator** (`plan_engine/validator/*`): geometry/connectivity/livability checks
5. **Renderer** (`plan_engine/renderer/*`): SVG + PNG output

If a hard rule fails, generation is rejected.

## 2. First Successful Run

```bash
uv sync
make run-default
```

Default input/output:

- input: `tmp/spec.yaml`
- output: `tmp/plan_output/`

Or run your own file:

```bash
uv run python main.py --spec tmp/spec.yaml --outdir tmp/plan_output --solver-timeout 90
```

## 3. Hard Constraints You Must Respect

- Units must be `mm`
- Grid must be `minor=455`, `major=910`
- Envelope type is rectangle only
- All coordinates/sizes must align to 455mm
- No overlap
- Entry must touch exterior boundary
- Indoor coverage is 100% of **floor buildable area**
- Stair must connect to the configured hall on each connected floor
- Bedroom pass-through is forbidden (a bedroom cannot be mandatory transit for another bedroom)

## 4. Full `spec.yaml` Skeleton

```yaml
version: 0.2
units: mm
grid:
  minor: 455
  major: 910
site:
  envelope:
    type: rectangle
    width: 9100
    depth: 7280
  north: top
floors:
  F1:
    core:
      stair: ...
    spaces: [...]
    topology:
      adjacency: [...]
  F2:
    buildable: [...]
    spaces: [...]
    topology:
      adjacency: [...]
```

## 5. Top-Level Fields

### `version`
Use `0.2`.

### `units`
Must be `mm`.

### `grid`
- `minor`: `455`
- `major`: `910`

### `site.envelope`
Rectangle only:

```yaml
site:
  envelope:
    type: rectangle
    width: 9100
    depth: 7280
```

`width/depth` must be divisible by `455`.

### `site.north`
Display orientation (`top` is common).

## 6. Floor Fields

Each floor (`F1`, `F2`, etc.) may contain:

- `core.stair` (usually defined on F1)
- `buildable` (optional indoor buildable mask)
- `spaces` (required)
- `topology.adjacency` (recommended and usually required for usable circulation)

### 6.1 `buildable` (optional)

Defines where **indoor** spaces may be placed on that floor.

If omitted, buildable defaults to full envelope.

Supported forms:

```yaml
buildable:
  - x: 0
    y: 0
    w: 8190
    h: 7280
```

or

```yaml
buildable:
  rects:
    - {x: 0, y: 0, w: 8190, h: 7280}
```

Rules:

- rectangles must be inside envelope
- no overlap between buildable rectangles
- `x,y,w,h` must align to 455mm
- `w,h > 0`

## 7. Space Definition

```yaml
- id: bed2
  type: bedroom
  area:
    min_tatami: 4.5
    target_tatami: 6.0
  size_constraints:
    min_width: 1820
  shape:
    allow: [rect]
    rect_components_max: 1
```

### Field meanings

- `id`: unique room ID on that floor
- `type`: semantic type
- `area.min_tatami`: hard minimum
- `area.target_tatami`: soft target (objective)
- `size_constraints.min_width`: minimum short side in mm
- `shape.allow`: allowed shapes (`rect`, `L2`)
- `shape.rect_components_max`: max rectangle components (effective only when `L2` is active)

### Important room type notes

Common indoor types:

- `entry`, `hall`, `ldk`
- `bedroom`, `master_bedroom`
- `storage`, `closet`, `wic`
- `toilet`/`wc`, `washroom`, `bath`

Outdoor types:

- `balcony`, `veranda`

Wet module sizes are fixed:

- toilet/wc: `910 x 1820`
- washroom: `1820 x 1820`
- bath: `1820 x 1820`

### 7.1 Storage vs Closet vs WIC (Important)

- `storage`: independent room-level storage (pantry, generic store room)
- `closet`: built-in closet zone attached to a parent room (`parent_id` required). It is rendered as hatched `CL` area, not as a standalone room block.
- `wic`: walk-in closet; also needs `parent_id`, and parent must be `bedroom` or `master_bedroom`

Example:

```yaml
- id: master
  type: master_bedroom
  area:
    target_tatami: 8.0

- id: wic1
  type: wic
  parent_id: master
  size_constraints:
    min_width: 910
  area:
    target_tatami: 2.0

- id: closet_bed2
  type: closet
  parent_id: bed2
  size_constraints:
    min_width: 910
  area:
    target_tatami: 1.0
```

Hard checks:

- `parent_id` must exist on the same floor
- `parent_id` cannot point to itself
- closet/WIC size constraints must still align to 455mm
- `wic` shortest side must be at least `1820mm`

## 8. Shape Rules (Current Stage)

- `ldk` can be multi-rect (`L2`) up to 2 parts
- `hall` can be multi-rect (`L2`) up to 4 parts
- other room types should remain rectangular
- wet modules are single fixed rectangles

Practical note:

- If `shape.allow` includes `rect`, component count falls back to 1
- To actually allow multi-rect behavior, use `allow: [L2]`

## 9. Stair Definition

```yaml
core:
  stair:
    id: stair
    type: straight        # straight | L_landing
    width: 910
    floor_height: 2730
    riser_pref: 230
    tread_pref: 210
    connects:
      F1: hall1
      F2: hall2
    placement:
      x: 3640
      y: 2730
```

Rules:

- `width`, `placement.x`, `placement.y` must align to 455
- `connects` hall IDs must exist and be `hall` type
- Stair position is shared structurally across connected floors

## 10. Topology: Adjacency Graph

Topology edges drive passable connectivity and doorway candidates.

```yaml
topology:
  adjacency:
    - [entry, hall1]
    - [hall1, ldk]
    - [hall1, stair]
    - [hall1, toilet1]
    - [hall1, wash1]
    - [wash1, bath1]
```

### Edge format

- 2-item: `[a, b]` (strength defaults to `auto`)
- 3-item: `[a, b, required|preferred|optional]`

`auto` resolves by type-pair defaults in solver; most pairs end up required.

### Topology recommendations

- Keep circulation simple: `entry -> hall -> rooms`
- Always connect hall to stair on stair floors
- Keep toilet and wet-core linked to circulation (hall/entry/stair)
- For `closet`/`wic`, always add at least parent adjacency:
  - `[closet_or_wic, parent_room, required]`
- For `wic`, also add a circulation-side edge when possible:
  - `[hallX, wicY, required]` or `[entry, wicY, preferred]`
- Do not force bedroom chains (`bed1 -> bed2 -> bed3`)

## 11. Balcony/Veranda Semantics

Outdoor spaces are first-class room types.

Behavior:

- classified as outdoor in solution/report
- excluded from indoor buildable coverage equation
- must declare topology access to at least one indoor room
- validator checks realized indoor-outdoor access

Example:

```yaml
- id: balcony1
  type: balcony
  area:
    target_tatami: 2.5

# topology
- [master, balcony1, required]
```

## 12. Step-by-Step Authoring Workflow

### Step 1: Set envelope on grid

Pick rectangle dimensions divisible by 455.

### Step 2: Define floor program

Start small. Get one feasible plan first, then add rooms.

### Step 3: Add stair + halls

Declare stair and hall IDs (`hall1`, `hall2`) early.

### Step 4: Add spaces with realistic ranges

Use targets that roughly match desired total floor area.

### Step 5: Add minimal topology

Only necessary edges first. Over-constraining is a common infeasibility source.

### Step 6: Run, inspect `report.txt`, iterate

Fix errors first, then optimize warnings.

## 13. Minimal 2F Example (With Balcony)

```yaml
version: 0.2
units: mm
grid:
  minor: 455
  major: 910
site:
  envelope:
    type: rectangle
    width: 9100
    depth: 5460
  north: top
floors:
  F1:
    core:
      stair:
        id: stair
        type: straight
        width: 910
        floor_height: 2730
        riser_pref: 230
        tread_pref: 210
        connects:
          F1: hall1
          F2: hall2
    spaces:
      - id: entry
        type: entry
        size_constraints: {min_width: 1365}
        area: {target_tatami: 2.0}
      - id: hall1
        type: hall
        size_constraints: {min_width: 910}
        area: {target_tatami: 4.0}
        shape:
          allow: [L2]
          rect_components_max: 3
      - id: ldk
        type: ldk
        area: {target_tatami: 15.0}
        shape:
          allow: [L2]
          rect_components_max: 2
      - id: toilet1
        type: toilet
      - id: wash1
        type: washroom
      - id: bath1
        type: bath
      - id: storage1
        type: storage
        size_constraints: {min_width: 910}
        area: {target_tatami: 2.0}
    topology:
      adjacency:
        - [entry, hall1]
        - [hall1, ldk]
        - [hall1, toilet1]
        - [hall1, wash1]
        - [wash1, bath1]
        - [hall1, storage1]
        - [hall1, stair]

  F2:
    buildable:
      - {x: 0, y: 0, w: 8190, h: 5460}
    spaces:
      - id: hall2
        type: hall
        size_constraints: {min_width: 910}
        area: {target_tatami: 4.0}
        shape:
          allow: [L2]
          rect_components_max: 2
      - id: master
        type: master_bedroom
        size_constraints: {min_width: 1820}
        area: {target_tatami: 7.0}
      - id: bed2
        type: bedroom
        size_constraints: {min_width: 1820}
        area: {target_tatami: 5.5}
      - id: bed3
        type: bedroom
        size_constraints: {min_width: 1820}
        area: {target_tatami: 5.5}
      - id: wic1
        type: storage
        size_constraints: {min_width: 910}
        area: {target_tatami: 2.0}
      - id: balcony1
        type: balcony
        size_constraints: {min_width: 910}
        area: {target_tatami: 2.5}
    topology:
      adjacency:
        - [hall2, stair]
        - [hall2, master]
        - [hall2, bed2]
        - [hall2, bed3]
        - [hall2, wic1]
        - [master, balcony1]
```

## 14. How to Read `report.txt`

### `Errors`
Hard failures. Fix these first.

### `Warnings`
Output is valid but quality is not ideal.

### `Diagnostics`
Useful numeric context (area budgets, buildable stats, breakdowns).

### Typical failure mapping

- `dsl_parse_failed`: schema, type, or alignment issue
- `preflight: ... max area cannot fill buildable`: increase targets/add room/reduce buildable
- `preflight: ... bedroom transit`: connect blocked bedroom to hall/circulation
- `solve_failed`: topology/size constraints over-constrained
- `entry must touch exterior`: adjust entry placement pressure via topology/targets
- `outdoor access ... missing/not realized`: add indoor↔balcony topology edge and ensure adjacency is solvable

## 15. Practical Tuning Order (When Infeasible)

1. Reduce topology edges to essentials
2. Remove strict stair placement (`placement`)
3. Relax min widths (except hard necessities)
4. Lower room targets
5. Reduce hall/LDK L-shape complexity
6. Re-check buildable mask area against indoor program

## 16. Pre-Run Checklist

- [ ] every mm value is divisible by 455
- [ ] floor IDs and room IDs are consistent
- [ ] stair `connects` references existing hall IDs
- [ ] each bedroom has hall-based access path
- [ ] washroom and bath have adjacency edge
- [ ] buildable masks are valid (inside, non-overlap)
- [ ] outdoor spaces have at least one indoor access edge

---

## 17. Spec Generator (Auto-Generate `spec.yaml`)

Instead of hand-authoring, you can use `gen_spec.py` to generate a complete `spec.yaml` from high-level inputs:

```bash
# Simple: just envelope + room count
uv run python gen_spec.py --envelope 8x9 --rooms 5ldk

# Detailed: per-floor room specs
uv run python gen_spec.py --envelope 8x9 \
  --f1 "ldk@18, bed, toilet, wash+bath" \
  --f2 "master+wic@8+2, bed:3@6, toilet, ws+shower"
```

The generator handles grid snapping, room distribution, area allocation, wet module selection, and topology generation automatically. It prints a feasibility report before writing the YAML.

For the full guide, see [docs/spec_generator.md](spec_generator.md).
