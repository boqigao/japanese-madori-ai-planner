# Spec Generator Guide

`gen_spec.py` automatically generates a valid `spec.yaml` from high-level inputs like envelope size and room count. It eliminates the need to hand-author grid alignments, area budgets, wet module sizes, and topology rules.

## Quick Start

```bash
# Simplest usage: just envelope + room count
uv run python gen_spec.py --envelope 8x9 --rooms 5ldk

# Output to a specific file
uv run python gen_spec.py --envelope 9.1x6.4 --rooms 3ldk --output my_spec.yaml

# Then solve it
uv run python main.py --spec spec.yaml --outdir plan_output --solver-timeout 90
```

## How It Works

The generator runs a 5-stage deterministic pipeline:

```
Envelope (meters) + Room count
        |
   [1] Metrics        -- snap to 910mm grid, compute cells/tatami
        |
   [2] Distribution   -- assign rooms to floors, add implied rooms
        |
   [3] Wet Selection  -- auto-select standard or compact wet per floor
        |
   [4] Allocation     -- proportional area allocation with min/max clamps
        |
   [5] Topology       -- generate adjacency edges from room types
        |
     spec.yaml
```

## CLI Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--envelope WxD` | Yes | - | Envelope in meters (e.g., `8x9`, `9.1x6.4`) |
| `--rooms NlDK` | No | - | Room shorthand (e.g., `5ldk`, `3ldk`) |
| `--floors N` | No | `2` | Number of floors (1 or 2) |
| `--north DIR` | No | `top` | North direction (`top`, `bottom`, `left`, `right`) |
| `--stair TYPE` | No | `U_turn` | Stair type (`straight`, `L_landing`, `U_turn`) |
| `--f1 SPEC` | No | - | Detailed F1 room spec (overrides `--rooms`) |
| `--f2 SPEC` | No | - | Detailed F2 room spec (overrides `--rooms`) |
| `--closets MODE` | No | `auto` | Closet generation (`auto`, `none`) |
| `--output PATH` | No | `spec.yaml` | Output file path |

## Two Input Modes

### Simple mode: `--rooms`

```bash
uv run python gen_spec.py --envelope 8x9 --rooms 5ldk
```

The generator automatically:
- Distributes 5 bedrooms across F1/F2 based on capacity
- Adds implied rooms (entry, hall, LDK, toilet, wet, storage, closets)
- Selects compact wet for tight floors
- Allocates area proportionally

### Detailed mode: `--f1` / `--f2`

```bash
uv run python gen_spec.py --envelope 8x9 \
  --f1 "ldk@18, bed@6, toilet, wash+bath" \
  --f2 "master+wic@8+2, bed:3@6, toilet, ws+shower"
```

When `--f1`/`--f2` are provided, they take full priority over `--rooms`.

## Room Spec Mini-Language

Each room token follows the format:

```
type[:count][@target][/min_width][+attachment]
```

### Examples

| Token | Meaning |
|-------|---------|
| `bed` | 1 bedroom, auto-allocated |
| `bed:3` | 3 bedrooms, auto-allocated |
| `bed:3@6` | 3 bedrooms, each 6 tatami |
| `bed:3@6/1820` | 3 bedrooms, 6 tatami, 1820mm min width |
| `ldk@18` | 1 LDK, 18 tatami |
| `master+wic@8+2` | master bedroom (8 tatami) + WIC (2 tatami) |
| `bed+cl` | bedroom + closet (both auto-allocated) |
| `wash+bath` | standard wet: washroom (1820x1820) + bath (1820x1820) |
| `ws+shower` | compact wet: washstand (910x910) + shower (910x1365) |
| `toilet` | toilet (910x1820, fixed) |

### Type aliases

| Shorthand | Expands to |
|-----------|-----------|
| `bed` | `bedroom` |
| `master` | `master_bedroom` |

## Area Allocation

The generator uses **proportional allocation** rather than fixed targets. Each variable-size room type has a weight, minimum, and maximum:

| Room Type | Weight | Min (jo) | Max (jo) |
|-----------|--------|----------|----------|
| ldk | 5.0 | 12.0 | 28.0 |
| master_bedroom | 3.0 | 6.0 | 14.0 |
| bedroom | 2.0 | 4.5 | 10.0 |
| hall | 1.5 | 3.0 | 7.0 |
| entry | 0.8 | 1.5 | 3.5 |
| storage | 1.0 | 1.5 | 5.0 |
| closet | 0.4 | 0.75 | 2.0 |
| wic | 0.8 | 1.5 | 3.5 |

Algorithm:
1. Deduct fixed rooms (wet, toilet, stair) from floor area
2. Deduct user-locked `@target` values
3. Distribute remainder proportionally by weight
4. Clamp to [min, max] bounds
5. Redistribute excess from clamped rooms

This means rooms scale naturally with envelope size -- a 10x12 house gets larger rooms than a 7x7 house, maintaining proportions.

## Wet Module Auto-Selection

Per floor, if the target density exceeds 85% with standard wet (washroom + bath), the generator automatically switches to compact wet (washstand + shower) to save ~2.5 tatami.

User-specified wet types in `--f1`/`--f2` are never overridden.

## Feasibility Report

Before writing YAML, the generator prints a per-floor summary:

```
=== Feasibility Report ===
  F1: 7 rooms, available=34.8jo, allocated=35.0jo, density=101%
  F2: 14 rooms, available=37.6jo, allocated=37.0jo, density=99%

Warnings:
  ! F1: density 101% > 85% -- consider compact wet, fewer rooms, or larger envelope
```

- **Density 75-85%**: safe zone, high solve success rate
- **Density >85%**: tight, may fail to solve -- warnings are printed
- **Density <60%**: under-packed -- suggests adding storage or WIC
- **Errors**: impossible configuration (min total exceeds available) -- YAML is not written

## Common Recipes

### Standard 3LDK (all beds on F2)

```bash
uv run python gen_spec.py --envelope 9.1x6.4 --rooms 3ldk
```

### Large 5LDK (beds spill to F1)

```bash
uv run python gen_spec.py --envelope 8x9 --rooms 5ldk
```

### 4LDK with custom master

```bash
uv run python gen_spec.py --envelope 10x8 --rooms 4ldk \
  --f2 "master+wic@10+2, bed:3@6, toilet, wash+bath"
```

### 1F hiraya (single floor)

```bash
uv run python gen_spec.py --envelope 12x8 --rooms 3ldk --floors 1
```

### No auto-closets

```bash
uv run python gen_spec.py --envelope 8x9 --rooms 5ldk --closets none
```

## Troubleshooting

| Problem | Suggestion |
|---------|-----------|
| Density warning >85% | Reduce bedrooms, enlarge envelope, or use compact wet |
| Density warning <60% | Add storage, WIC, or extra rooms |
| Generated spec fails to solve | Try `--solver-timeout 120`; reduce room count; relax targets |
| Want specific room sizes | Use `--f1`/`--f2` with `@target` overrides |
| Want standard wet on tight floor | Specify `wash+bath` explicitly in `--f2` |
