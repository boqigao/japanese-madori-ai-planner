# Renderer Specification

## Purpose
Defines the SVG/PNG rendering of solved floor plans. The renderer performs read-only consumption of `PlanSolution` and must never alter geometry. Produces visual output including grid lines, spaces, stairs, doors, windows, labels, legend, north arrow, and dimensions.

## Requirements

### Requirement: SVG Generation
The system MUST generate an SVG file for each floor in the solution.

#### Scenario: Single floor rendering
- GIVEN a solved plan with 1 floor
- WHEN the renderer runs
- THEN one SVG file is produced named `{floor_id}.svg`

#### Scenario: Multi-floor rendering
- GIVEN a solved plan with 2 floors (1F, 2F)
- WHEN the renderer runs
- THEN two SVG files are produced: `1F.svg` and `2F.svg`

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
- THEN minor grid lines appear at every 455mm and major grid lines at every 910mm

### Requirement: Space Visualization
The system MUST draw each space as a labeled rectangle with distinct visual styling per room type.

#### Scenario: Room labeling
- GIVEN a floor with spaces (LDK, bedroom, bath, etc.)
- WHEN the renderer draws the floor
- THEN each space is drawn as a filled rectangle with its name label

### Requirement: Read-Only Consumption
The renderer MUST NOT alter any geometry data from the `PlanSolution`.

#### Scenario: Geometry integrity
- GIVEN a `PlanSolution` object passed to the renderer
- WHEN the renderer completes
- THEN the `PlanSolution` object remains unchanged

### Requirement: Dimension Annotations
The system SHOULD draw dimension annotations showing space widths and depths in mm.

#### Scenario: Dimension labels
- GIVEN a space with width=3640mm and depth=2730mm
- WHEN the renderer draws the space
- THEN dimension annotations display "3640" and "2730"

### Requirement: North Arrow
The system MUST draw a north arrow indicating the building orientation.

#### Scenario: North direction
- GIVEN a spec with north="top"
- WHEN the renderer draws the floor plan
- THEN a north arrow pointing upward is displayed

### Requirement: Legend
The system SHOULD include a legend mapping room colors/styles to room type names.

#### Scenario: Legend display
- GIVEN a floor plan with multiple room types
- WHEN the renderer draws the floor
- THEN a legend showing room type to color mappings is included
