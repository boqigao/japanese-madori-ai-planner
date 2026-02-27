# How to Use This Project: Design a `spec.yaml` from Your Site

This guide is for users with **no prior knowledge of this repository** who want to generate a detached-house floor plan from their site dimensions.

## 1. What This Project Does

This project generates floor plans with a fixed pipeline:

`spec.yaml -> DSL parser -> CP-SAT solver -> validator -> SVG/PNG output`

You provide a YAML spec (`spec.yaml`).
The solver places rooms and stairs under hard constraints (no overlap, grid alignment, connectivity, 100% coverage). The validator checks geometric and livability rules, then the renderer outputs drawings.

## 2. What You Must Know Before Writing `spec.yaml`

This MVP has strict boundaries:

- Unit must be `mm`.
- Grid is fixed: `minor=455`, `major=910`.
- Building envelope supports rectangle only.
- Every coordinate and important dimension must align to 455 mm.
- Floor area must be used 100% (no white space left unassigned).
- Only `ldk` and `hall` can use L-shape (`L2`) components.
- Stair supports only `straight` or `L_landing`.

If your site is irregular, define a **buildable rectangle** inside it and use that as `site.envelope`.

## 3. Quick Start Commands

```bash
uv sync
uv run python main.py --spec tmp/spec.yaml --outdir tmp/plan_output --solver-timeout 60
```

Generated files:

- `solution.json`: solved geometry
- `report.txt`: validation results
- `F1.svg/F1.png`, `F2.svg/F2.png`, ...

## 4. `spec.yaml` Structure (Top Level)

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
  F1: ...
  F2: ...
```

Required top-level keys:

- `version` (string)
- `units` (`mm` only)
- `grid` (`minor=455`, `major=910`)
- `site`
- `floors`

## 5. Floor Section Format

Each floor contains:

- Optional `core.stair`
- Required `spaces` list
- Optional `topology.adjacency`

Example skeleton:

```yaml
floors:
  F1:
    core:
      stair: ...
    spaces:
      - id: entry
        type: entry
        ...
    topology:
      adjacency:
        - [entry, hall1]
        - [hall1, stair]
```

Use stable floor IDs like `F1`, `F2`. The code sorts floors by numeric order.

## 6. Space Definition Format

Each space item:

```yaml
- id: bed2
  type: bedroom
  area:
    min_tatami: 6.0
    target_tatami: 7.5
  size_constraints:
    min_width: 1820
  shape:
    allow: [rect]
    rect_components_max: 1
```

Fields:

- `id`: room identifier. Keep unique within a floor.
- `type`: semantic room type.
- `area.min_tatami`: hard lower bound.
- `area.target_tatami`: soft optimization target. In current solver, if `min_tatami` is absent, target also behaves as a minimum floor.
- `size_constraints.min_width`: hard minimum short side in mm (must be multiple of 455).
- `shape.allow`: allowed shapes (`rect`, `L2`).
- `shape.rect_components_max`: requested component count cap.

Supported/expected room types in practice:

- `entry`, `hall`, `ldk`
- `bedroom`, `master_bedroom`
- `toilet` or `wc`, `washroom`, `bath`
- `storage`

## 7. Shape Rules You Must Follow

Current implementation behavior:

- Default is one rectangle (`rect`).
- Only `ldk` and `hall` may declare `L2`.
- `ldk` max components: 2.
- `hall` max components: 4.
- Wet modules (`toilet/wc/washroom/bath`) are forced to one fixed-size rectangle.

Important implementation detail:

- `L2` is active only when `shape.allow` excludes `rect`.
- If you set `allow: [rect, L2]`, current component logic falls back to single-rect.

To force L-shape for hall/LDK, use:

```yaml
shape:
  allow: [L2]
  rect_components_max: 4   # hall example
```

## 8. Stair Definition Format

```yaml
core:
  stair:
    id: stair
    type: straight            # or L_landing
    width: 910
    floor_height: 2730
    riser_pref: 230
    tread_pref: 210
    connects:
      F1: hall1
      F2: hall2
    placement:
      x: 3640
      y: 3640
```

Rules:

- Stair `id` must be shared logically across floors (single vertical shaft model).
- `width`, `placement.x`, `placement.y` must align to 455.
- `connects` maps floor ID -> hall ID that must connect to stair portal.
- If `placement` is omitted, solver chooses location.

## 9. Topology Adjacency: How It Works

`topology.adjacency` requires **physical touching** (shared edge with positive overlap), not just conceptual relation.

Example:

```yaml
topology:
  adjacency:
    - [entry, hall1]
    - [hall1, ldk]
    - [hall1, bed1]
    - [hall1, stair]
    - [wash1, bath1]
```

Guidelines:

- Add only truly necessary edges.
- Over-constraining adjacency is a common cause of `solve_failed`.
- Always include stair-hall adjacency in topology (`[hallX, stair]`).
- Every bedroom must have a path from `entry` that does not pass through another bedroom.
  - Good: `entry -> hall -> bedroom`
  - Bad: `entry -> hall -> bedroom A -> bedroom B`

## 10. Hard Constraints Enforced by Solver/Validator

These are non-negotiable:

- No overlap of any rooms or stair components.
- Every rectangle stays inside the envelope.
- 100% envelope coverage per floor.
- Entry must touch exterior boundary.
- Entry has hard max area ≈ `2.5 jo`.
- Wet module fixed sizes:
  - toilet/wc: `910 x 1820`
  - washroom: `1820 x 1820`
  - bath: `1820 x 1820`
- Bath must touch at least one washroom.
- Wet spaces must form a connected cluster and connect to hall.
- Toilet/WC must not be adjacent to LDK (1 minor-cell gap).
- Hall short side must be <= `1820 mm`.
- Stair portal edge must connect to configured hall on each connected floor.
- Stair portal edge cannot sit on exterior boundary.
- Bedroom pass-through is forbidden in preflight:
  - `bedroom` / `master_bedroom` may be destination rooms, but must not be required as transit to reach another bedroom.

## 11. Recommended Area/Width Ranges (Practical Defaults)

Use these as starting points:

- `entry`: 1.5 to 2.5 jo, min width 1365
- `hall`: 3.0 to 5.5 jo, min width 910
- `toilet`: 1.0 jo
- `washroom`: 2.0 jo
- `bath`: 2.0 jo
- `bedroom`: 6.0 to 8.0 jo, min width 1820 or 2275
- `master_bedroom`: 8.0 to 10.0 jo, min width 1820+
- `ldk`: 12.0 to 18.0 jo
- `storage/wic`: 1.5 to 3.0 jo

Because coverage is 100%, if total targets are too small, some rooms will grow to fill area. Plan target areas accordingly.

## 12. Step-by-Step Workflow from Land Shape to `spec.yaml`

### Step 1: Decide Buildable Rectangle

- Measure your intended building footprint (not total site if irregular).
- Snap both width/depth to multiples of 455.
- Example: 9000 x 7300 becomes 9100 x 7280.

### Step 2: Decide Floor Program

- List rooms needed per floor.
- Keep F1 around entry/living/wet/core.
- Keep F2 around bedrooms/hall/storage.

### Step 3: Define Stair + Hall Pairing

- Pick stair type (`straight` is easiest for first attempt).
- Define `connects` to one hall per connected floor.
- Ensure each connected floor actually has that hall ID.

### Step 4: Write Spaces with Realistic Bounds

- Start with `target_tatami` for each room.
- Add `min_width` for bedrooms and entry.
- Keep IDs simple (`bed1`, `bed2`, `hall1`, `hall2`).

### Step 5: Add Shape Constraints

- Keep all non-hall/non-LDK rooms rectangular.
- If you need flexible circulation, set hall as `L2` with `rect_components_max: 3~4`.
- If you need LDK L-shape, set `allow: [L2]`.

### Step 6: Add Minimal Topology

- Start with core circulation edges only.
- Add wet adjacency `[wash, bath]`.
- Add stair adjacency `[hall, stair]`.
- Add extra adjacency only if required.

### Step 7: Run and Read `report.txt`

- If parse error: fix schema/alignment first.
- If solve fails: relax adjacency and width/area pressure.
- If validation fails: address exact `Errors:` line-by-line.

### Step 8: Iterate

Recommended order when infeasible:

1. Reduce topology edges.
2. Relax bedroom `min_width`.
3. Lower area targets for large rooms.
4. Remove forced stair placement.
5. Re-check hall IDs in `stair.connects`.

## 13. How to Read `report.txt`

`report.txt` has:

- `Errors`: hard failures (output rejected)
- `Warnings`: plan is valid but quality issues exist
- `Structural`: proxy structural diagnostics (warn-only)

Common messages and fixes:

- `dsl_parse_failed: ... align to 455mm`: snap all dimensions to 455.
- `solve_failed`: constraints conflict; reduce adjacency and targets.
- `area coverage must be 100%`: happens if geometry invalid or missing entities.
- `entry must touch exterior boundary`: topology alone is not enough; entry rectangle must touch outer wall.
- `stair ... connect hall missing`: hall ID in `connects` is wrong or absent.
- `bath is not adjacent to any washroom`: add washroom and adjacency pressure.

## 14. Full Two-Floor Example (Starter Template)

This is a practical starter that aligns with current rules:

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
        size_constraints:
          min_width: 1365
        area:
          target_tatami: 2.0
      - id: hall1
        type: hall
        size_constraints:
          min_width: 910
        area:
          target_tatami: 4.5
        shape:
          allow: [L2]
          rect_components_max: 4
      - id: ldk
        type: ldk
        area:
          target_tatami: 15.0
        shape:
          allow: [L2]
          rect_components_max: 2
      - id: bed1
        type: bedroom
        size_constraints:
          min_width: 1820
        area:
          target_tatami: 8.0
      - id: toilet1
        type: toilet
        area:
          target_tatami: 1.0
      - id: wash1
        type: washroom
        area:
          target_tatami: 2.0
      - id: bath1
        type: bath
        area:
          target_tatami: 2.0
    topology:
      adjacency:
        - [entry, hall1]
        - [hall1, ldk]
        - [hall1, bed1]
        - [hall1, toilet1]
        - [hall1, wash1]
        - [hall1, stair]
        - [wash1, bath1]

  F2:
    spaces:
      - id: hall2
        type: hall
        size_constraints:
          min_width: 910
        area:
          target_tatami: 4.5
        shape:
          allow: [L2]
          rect_components_max: 4
      - id: master
        type: master_bedroom
        size_constraints:
          min_width: 1820
        area:
          target_tatami: 8.0
      - id: bed2
        type: bedroom
        size_constraints:
          min_width: 1820
        area:
          target_tatami: 7.0
      - id: bed3
        type: bedroom
        size_constraints:
          min_width: 1820
        area:
          target_tatami: 7.0
      - id: bed4
        type: bedroom
        size_constraints:
          min_width: 1820
        area:
          target_tatami: 5.0
      - id: wic1
        type: storage
        size_constraints:
          min_width: 910
        area:
          target_tatami: 2.0
    topology:
      adjacency:
        - [hall2, master]
        - [hall2, bed2]
        - [hall2, bed3]
        - [hall2, bed4]
        - [hall2, wic1]
        - [hall2, stair]
```

## 15. Final Checklist Before Running

- All mm values snapped to 455.
- Envelope is rectangle.
- Each floor has realistic room list.
- Entry exists on ground floor and can touch exterior.
- Wet trio (`toilet/wash/bath`) designed with hall access.
- Bath has washroom adjacency pressure.
- Stair `connects` hall IDs exist on each connected floor.
- Topology is necessary but not over-constrained.
- Hall and LDK shape settings match desired behavior.

If you want, the next step can be a second document with “design patterns” (for example: compact 4LDK, 5LDK+WIC, narrow-frontage lot patterns) that you can copy directly.
