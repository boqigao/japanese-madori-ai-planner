# Spec Generator Specification

## Purpose

Defines the CLI tool that auto-generates a valid `spec.yaml` from high-level requirements. The generator accepts an envelope size and room program (shorthand or detailed per-floor), performs grid snapping, area allocation, wet module selection, closet generation, topology wiring, and feasibility checking, then outputs a DSL-conformant spec file ready for the solver.

## Requirements

### Requirement: Grid-snapped envelope parsing
The generator SHALL accept envelope dimensions in meters and snap them to the nearest 910mm (major grid) multiple. The snapped values SHALL be used for all subsequent calculations.

#### Scenario: Standard envelope snap
- **WHEN** user provides `--envelope 8x9`
- **THEN** generator snaps to 8190x9100mm (nearest 910mm multiples) and reports the snapped values

#### Scenario: Already-aligned envelope
- **WHEN** user provides `--envelope 9.1x6.37`
- **THEN** generator produces 9100x6370mm (exact 910mm multiples, no adjustment needed)

### Requirement: Shorthand room mode
The generator SHALL accept `--rooms NlDK` (e.g., `5ldk`) and automatically distribute N bedrooms across floors, adding implied rooms (entry, hall, stair, toilet, wet area, closets, storage).

#### Scenario: 5LDK shorthand on 2F
- **WHEN** user provides `--envelope 8x9 --rooms 5ldk`
- **THEN** generator produces a 2-floor spec with 5 bedrooms distributed across F1 and F2, plus entry, halls, stair, toilets, wet modules, closets, and storage on appropriate floors

#### Scenario: 3LDK shorthand on 2F
- **WHEN** user provides `--envelope 9.1x6.4 --rooms 3ldk`
- **THEN** generator produces a 2-floor spec with 0 bedrooms on F1 and 3 bedrooms (1 master + 2 bedroom) on F2

### Requirement: Per-floor detailed room specification
The generator SHALL accept `--f1` and `--f2` flags with room spec mini-language. When both `--rooms` and `--f1`/`--f2` are provided, `--f1`/`--f2` SHALL take full priority.

#### Scenario: Detailed F2 specification
- **WHEN** user provides `--f2 "master@12, bed:3@6, toilet, ws+shower"`
- **THEN** generator uses exactly those rooms on F2 with master target locked at 12 tatami and each bedroom at 6 tatami

#### Scenario: Override precedence
- **WHEN** user provides `--rooms 5ldk --f2 "master, bed:2"`
- **THEN** F2 uses the explicit `--f2` specification (master + 2 bedrooms), ignoring the 5ldk shorthand for F2

### Requirement: Room spec mini-language parsing
The generator SHALL parse room specifications in the format `type[:count][@target][/min_width][+attachment]`.

#### Scenario: Full room spec
- **WHEN** a room spec is `bed:3@6/1820`
- **THEN** generator creates 3 bedrooms, each with target_tatami=6.0 and min_width=1820mm

#### Scenario: Room with attachment
- **WHEN** a room spec is `master+wic@8+2`
- **THEN** generator creates 1 master_bedroom with target 8.0 tatami and 1 WIC with target 2.0 tatami, plus a preferred adjacency between them

#### Scenario: Wet module shorthand
- **WHEN** a room spec is `wash+bath`
- **THEN** generator creates 1 washroom (fixed 1820x1820mm) and 1 bath (fixed 1820x1820mm) with required adjacency between them

#### Scenario: Compact wet shorthand
- **WHEN** a room spec is `ws+shower`
- **THEN** generator creates 1 washstand (fixed 910x910mm) and 1 shower (fixed 910x1365mm) with required adjacency between them

#### Scenario: Minimal spec with count
- **WHEN** a room spec is `bed:3`
- **THEN** generator creates 3 bedrooms with auto-allocated targets (no user override)

### Requirement: Proportional area allocation
The generator SHALL allocate area to variable-size rooms proportionally by weight. User-specified `@target` values SHALL be deducted first; remaining space SHALL be distributed among auto rooms. Each room type has a weight, minimum, and maximum tatami bound.

#### Scenario: All auto allocation on medium envelope
- **WHEN** envelope is 8190x9100mm and F1 has rooms ldk, bed, hall, entry, storage, closet with no user `@target` overrides
- **THEN** each room receives area proportional to its weight, and all targets fall within their [min, max] bounds

#### Scenario: User override with auto remainder
- **WHEN** F2 has `master@12` (user-locked) and `bed:3, hall, closet:4` (auto)
- **THEN** 12.0 tatami is deducted from available space, and remaining rooms are proportionally allocated from the remainder

#### Scenario: Large envelope triggers max clamps
- **WHEN** envelope is 10010x11830mm (10x12m snapped) with 5LDK
- **THEN** rooms that exceed their max bound are clamped, and the generator warns about unallocated excess area with suggestions to add rooms

#### Scenario: Small envelope triggers min clamps
- **WHEN** envelope is 7280x7280mm (7x7m snapped) with 5LDK and rooms hit min bounds
- **THEN** rooms are clamped at their minimum values and the generator warns if total minimum exceeds available space

### Requirement: Automatic wet module selection
The generator SHALL automatically select compact wet (washstand+shower) or standard wet (washroom+bath) per floor based on area density. When target density exceeds 85% with standard wet, compact wet SHALL be selected.

#### Scenario: Tight F2 gets compact wet
- **WHEN** F2 has 4 bedrooms and standard wet would produce >85% target density
- **THEN** generator selects washstand+shower for F2 and reports the selection

#### Scenario: Spacious F2 keeps standard wet
- **WHEN** F2 has 2 bedrooms and standard wet produces <=85% target density
- **THEN** generator uses washroom+bath for F2

#### Scenario: User explicit wet overrides auto-selection
- **WHEN** user specifies `--f2 "master, bed:2, toilet, wash+bath"` on a tight floor
- **THEN** generator uses standard wet as explicitly requested, even if density exceeds 85%, and issues a density warning

### Requirement: Automatic floor distribution
The generator SHALL distribute bedrooms across floors based on F2 capacity. F2 capacity is calculated from buildable cells minus fixed modules (stair + wet + toilet) divided by per-bedroom cell weight.

#### Scenario: 5LDK distribution on 8x9 envelope
- **WHEN** user provides `--rooms 5ldk --envelope 8x9`
- **THEN** generator places 1 bedroom on F1 and 4 bedrooms (1 master + 3 bedroom) on F2

#### Scenario: 3LDK all on F2
- **WHEN** user provides `--rooms 3ldk --envelope 9.1x6.4`
- **THEN** generator places 0 bedrooms on F1 and 3 bedrooms (1 master + 2 bedroom) on F2

### Requirement: Automatic topology generation
The generator SHALL produce topology adjacency rules based on room types present on each floor. Rules follow a deterministic template: hall connects to all rooms, wet pairs are required-adjacent, bedroom-closet pairs are required-adjacent, WIC-master pairs are preferred-adjacent.

#### Scenario: Standard F1 topology
- **WHEN** F1 has entry, hall, ldk, toilet, washroom, bath, storage, stair
- **THEN** generator produces required adjacency edges: entry-hall, hall-ldk, hall-toilet, hall-washroom, washroom-bath, hall-storage, hall-stair

#### Scenario: F2 with compact wet and closets
- **WHEN** F2 has hall, master, bed2, bed3, toilet, washstand, shower, master_cl, bed2_cl, bed3_cl, stair
- **THEN** generator produces required edges for hall-rooms, washstand-shower, bedroom-closet pairs, and hall-stair

#### Scenario: WIC uses preferred adjacency
- **WHEN** F2 has master+wic
- **THEN** the master-wic adjacency edge is generated with strength `preferred` (not `required`)

### Requirement: Automatic closet generation
When `--closets auto` (the default), the generator SHALL add one closet per bedroom with target_tatami=1.0 (auto-allocated, scales with envelope) and min_width=910mm.

#### Scenario: Auto closets for 3 bedrooms
- **WHEN** F2 has master, bed2, bed3 and `--closets auto`
- **THEN** generator adds master_cl, bed2_cl, bed3_cl each as closet type with parent_id set to their respective bedroom

#### Scenario: Closets disabled
- **WHEN** user specifies `--closets none`
- **THEN** no closets are auto-generated (user can still explicitly include closets in `--f1`/`--f2`)

### Requirement: Default stair configuration
For 2-floor specs, the generator SHALL produce a U_turn stair by default with width=910mm, floor_height=2730mm, riser_pref=230mm, tread_pref=210mm. The stair type can be overridden with `--stair`.

#### Scenario: Default stair
- **WHEN** user provides `--envelope 8x9 --rooms 3ldk` (2F, no stair override)
- **THEN** generated spec includes a U_turn stair with standard parameters connecting F1 hall to F2 hall

#### Scenario: Override stair type
- **WHEN** user provides `--stair L_landing`
- **THEN** generated spec uses L_landing stair type instead of U_turn

#### Scenario: 1F no stair
- **WHEN** user provides `--floors 1`
- **THEN** generated spec has no stair definition

### Requirement: Feasibility self-check output
Before writing the YAML file, the generator SHALL print a per-floor summary showing room count, fixed cells, target cells, buildable cells, and density percentage. Warnings SHALL be printed when density is outside the 75-85% safe zone, with actionable suggestions.

#### Scenario: Normal density report
- **WHEN** generation completes with all floors in safe density range
- **THEN** generator prints per-floor summary with density% and a checkmark, then writes spec.yaml

#### Scenario: Over-tight density warning
- **WHEN** F2 target density exceeds 85%
- **THEN** generator prints a warning with suggestions: use compact wet, reduce a bedroom, or enlarge envelope

#### Scenario: Under-packed density warning
- **WHEN** F1 target density is below 60% (all rooms hit max clamps with excess remaining)
- **THEN** generator prints a warning suggesting additional rooms (storage, WIC) to absorb excess area

#### Scenario: Impossible configuration error
- **WHEN** total minimum area of all rooms exceeds buildable cells on any floor
- **THEN** generator prints an error and refuses to write spec.yaml, with suggestions to remove rooms or enlarge envelope

### Requirement: Hall shape configuration
The generator SHALL configure halls with `allow: [L2]` and `rect_components_max: 3` by default. For 1F specs with fewer rooms, `rect_components_max: 2` MAY be used.

#### Scenario: Standard 2F hall
- **WHEN** generating a 2F spec
- **THEN** both F1 and F2 halls have shape `allow: [L2], rect_components_max: 3`

### Requirement: YAML output format
The generator SHALL output a valid spec.yaml that conforms to the existing DSL schema (version 0.2). All dimensions SHALL be in mm. All coordinates SHALL satisfy `value % 455 == 0` (minor grid alignment).

#### Scenario: Output passes DSL parsing
- **WHEN** generator writes spec.yaml
- **THEN** the output file is successfully parsed by `load_plan_spec()` without errors

#### Scenario: Output passes preflight
- **WHEN** generator writes spec.yaml
- **THEN** running preflight on the output produces zero errors
