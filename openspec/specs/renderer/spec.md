# Renderer Specification

## Purpose
Defines the SVG/PNG rendering of solved floor plans. The renderer performs read-only consumption of `PlanSolution` and must never alter geometry. Implementation is split across `core.py` (orchestration), `annotations.py` (labels/legend), `dimensions.py` (dimension lines), `stair.py` (stair visualization), `symbols.py` (door/window), and `helpers.py` (geometry utilities).
## Requirements
### Requirement: SVG Generation
The system MUST generate an SVG file for each floor in the solution.

#### Scenario: Single floor rendering
- GIVEN a solved plan with 1 floor
- WHEN the renderer runs
- THEN one SVG file is produced named `{floor_id}.svg`

#### Scenario: Multi-floor rendering
- GIVEN a solved plan with 2 floors (F1, F2)
- WHEN the renderer runs
- THEN two SVG files are produced: `F1.svg` and `F2.svg`

### Requirement: PNG Export
The system MUST export PNG files from the generated SVGs using CairoSVG.

#### Scenario: PNG output
- GIVEN a generated SVG file
- WHEN PNG export runs
- THEN a corresponding `{floor_id}.png` file is produced

### Requirement: Grid Drawing
The system MUST draw the 455mm minor grid and 910mm major grid as visual reference lines.

#### Scenario: Grid overlay
- GIVEN a floor plan with envelope 9100mm x 7280mm
- WHEN the renderer draws the grid
- THEN minor grid lines appear at every 455mm and major grid lines at every 910mm with distinct styling

### Requirement: Space Visualization
The system MUST draw indoor and outdoor spaces with distinct visual semantics. Outdoor spaces (`balcony`/`veranda`) MUST use outdoor styling and remain read-only reflections of solved geometry.

#### Scenario: Balcony styling
- **GIVEN** a floor with `balcony_2f` and indoor rooms
- **WHEN** the renderer draws the floor
- **THEN** balcony is rendered with outdoor-specific fill/hatch style distinct from indoor room colors

### Requirement: Space Labels
The system MUST label each space with its name, dimensions, and area (sqm and tatami).

#### Scenario: Single-rect room label
- GIVEN a bedroom with one rectangle of 3640x2730mm
- WHEN the renderer draws labels
- THEN the label shows the room name, "3640x2730mm", and area in sqm/jo

#### Scenario: L-shaped room label
- GIVEN an L-shaped LDK with 2 rectangles
- WHEN the renderer draws labels
- THEN the label shows the room name, "L-shape (2 parts)", component dimensions, and total area

### Requirement: Read-Only Consumption
The renderer MUST NOT alter any geometry data from the `PlanSolution`.

#### Scenario: Geometry integrity
- GIVEN a `PlanSolution` object passed to the renderer
- WHEN the renderer completes
- THEN the `PlanSolution` object remains unchanged

### Requirement: Dimension Annotations
The system MUST draw interior room dimension guides and exterior site/building dimension lines.

#### Scenario: Interior dimensions
- GIVEN a space with width=3640mm and depth=2730mm
- WHEN the renderer draws dimension guides
- THEN horizontal and vertical dimension annotations are rendered inside the space

#### Scenario: Exterior dimensions
- GIVEN a floor plan with known boundary segments
- WHEN the renderer draws exterior dimensions
- THEN dimension lines with tick marks appear outside the building footprint

### Requirement: North Arrow
The system MUST draw a north arrow indicating the building orientation.

#### Scenario: North direction
- GIVEN a spec with north="top"
- WHEN the renderer draws the floor plan
- THEN a north arrow pointing upward is displayed

### Requirement: Legend
The system MUST include legend entries that distinguish indoor room types from outdoor space types.

#### Scenario: Legend with balcony
- **GIVEN** a rendered floor containing a balcony
- **WHEN** legend is generated
- **THEN** legend includes balcony/veranda entry with outdoor style swatch

### Requirement: Title Block and Scale
The system MUST draw a title block showing the floor ID, envelope dimensions, and rendering scale.

#### Scenario: Title block
- GIVEN floor F1 with envelope 9100x7280mm
- WHEN the renderer draws the title
- THEN "F1 Plan (9100 x 7280 mm)" and the scale ratio are displayed

### Requirement: Floor Area Summary
The system MUST draw area summaries that separate indoor and outdoor totals per floor and for the whole plan.

#### Scenario: Mixed indoor-outdoor floor summary
- **GIVEN** a floor containing indoor rooms and one balcony
- **WHEN** the renderer draws area summary
- **THEN** the summary displays indoor sqm/tsubo and outdoor sqm/tsubo as separate lines

### Requirement: Door Symbols
The system MUST draw opening symbols on realized shared boundaries for indoor-to-indoor and indoor-to-outdoor access edges where appropriate. When an embedded closet occupies a portion of the wall containing a door segment, the door symbol MUST be positioned on the portion of the shared segment that does not overlap with the CL rect.

#### Scenario: Indoor-to-balcony opening
- **GIVEN** an indoor room and balcony with realized shared boundary and declared topology edge
- **WHEN** the renderer draws openings
- **THEN** an opening symbol is rendered on the shared indoor-outdoor edge

#### Scenario: Door avoids CL on shared wall

- **GIVEN** a bedroom with hall adjacency on the right wall
- **AND** the shared segment between hall and bedroom spans y=3185 to y=5460 (2275mm)
- **AND** CL occupies the right wall from y=3185 to y=4550 (1365mm deep into the room)
- **WHEN** the renderer draws the interior door
- **THEN** the door symbol is drawn on the non-CL portion of the shared segment (y=4550 to y=5460)

### Requirement: Window Symbols
The system MUST draw window symbols on exterior edges of eligible room types. Exterior segments occupied by embedded closets or entry doors MUST be subtracted from candidate segments before window placement. When a blocked segment partially overlaps a candidate exterior segment, the candidate MUST be split into unblocked sub-segments. Window count and position are determined independently on each sub-segment using the standard thresholds (≥3600mm → 2 windows, ≥1365mm → 1 window, <1365mm → skip).

#### Scenario: Partial exterior blockage — subtraction reduces window count

- **GIVEN** a bedroom rect (5460, 0, 3640, 3185) with exterior north wall segment (5460, 0) → (9100, 0), length 3640mm
- **AND** CL rect (8190, 0, 910, 3185) blocks the north edge sub-segment (8190, 0) → (9100, 0)
- **WHEN** the renderer subtracts blocked segments from the candidate
- **THEN** the remaining sub-segment is (5460, 0) → (8190, 0), length 2730mm
- **AND** 1 window is drawn (centered, since 2730mm < 3600mm threshold)
- **AND** no window appears in the blocked (8190, 0) → (9100, 0) range

#### Scenario: Full exterior blockage — no window

- **GIVEN** a bedroom rect (6370, 0, 2730, 5460) with CL rect (6370, 0, 2730, 910) blocking the entire north edge (6370, 0) → (9100, 0)
- **WHEN** the renderer subtracts blocked segments from the north wall candidate (6370, 0) → (9100, 0)
- **THEN** subtraction produces an empty list (blocked segment equals candidate)
- **AND** no window is drawn on the north edge

#### Scenario: No blockage — unchanged

- **GIVEN** a bedroom with exterior south wall and no CL or entry door on that wall
- **WHEN** the renderer processes window candidates
- **THEN** the full south wall segment is retained and windows are placed normally

#### Scenario: Multiple blocked segments on one wall

- **GIVEN** an exterior wall segment (0, 0) → (9100, 0), length 9100mm
- **AND** two blocked sub-segments: (0, 0) → (910, 0) and (8190, 0) → (9100, 0)
- **WHEN** the renderer subtracts both blocked segments
- **THEN** the remaining sub-segment is (910, 0) → (8190, 0), length 7280mm
- **AND** 2 windows are drawn on the remaining sub-segment

#### Scenario: Blocked segment leaves remainder too short for window

- **GIVEN** an exterior wall segment (0, 0) → (2730, 0), length 2730mm
- **AND** CL blocks (0, 0) → (1820, 0)
- **WHEN** the renderer subtracts the blocked segment
- **THEN** the remaining sub-segment is (1820, 0) → (2730, 0), length 910mm
- **AND** no window is drawn (910mm < 1365mm minimum)

### Requirement: Stair Visualization
The system MUST draw stair components with tread step lines, void hatching, guardrails, and connection openings for supported stair types (`straight`, `L_landing`, `U_turn`).

#### Scenario: Straight stair
- **GIVEN** a straight stair with calculated treads
- **WHEN** the renderer draws the stair
- **THEN** component outlines, evenly spaced tread lines, and guardrails are drawn

#### Scenario: L-landing stair
- **GIVEN** an L-landing stair with two flights and a landing
- **WHEN** the renderer draws the stair
- **THEN** both flights with tread lines, the landing, and connection openings are drawn

#### Scenario: U-turn stair
- **GIVEN** a U-turn stair with two opposite-direction flights and a landing
- **WHEN** the renderer draws the stair
- **THEN** both flights are rendered with directional tread lines, the landing is rendered as a component, and guardrail/opening indicators follow solved portal semantics

#### Scenario: Void floor (upper floor stair)
- **GIVEN** an upper floor with a stair void
- **WHEN** the renderer draws the void
- **THEN** cross-hatching and guardrail lines indicate the opening

### Requirement: Fixture Symbols
The system MUST draw lightweight furniture/fixture symbols in applicable spaces.

#### Scenario: Wet space fixtures
- GIVEN toilet, washroom, and bath spaces
- WHEN the renderer draws fixtures
- THEN simplified fixture outlines (toilet bowl, sink, bathtub) are rendered

### Requirement: Structural Wall Overlay (Optional)
The system MUST support an optional structural wall overlay controlled by the `PLAN_ENGINE_DRAW_STRUCTURAL_WALLS` environment variable.

#### Scenario: Structural walls enabled
- GIVEN `PLAN_ENGINE_DRAW_STRUCTURAL_WALLS=1`
- WHEN the renderer draws the floor
- THEN bearing walls are drawn with thicker lines and distinct colors by role

