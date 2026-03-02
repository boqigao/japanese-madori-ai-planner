# Door Segment Computation Specification

## Purpose
Defines the door segment computation utility that calculates exact door segment positions for topology edges, providing a shared foundation for both the closet placement pipeline and the renderer.

## Requirements

### Requirement: Door Segment Computation Utility

The system MUST provide a function `compute_door_segments()` in `plan_engine/solver/solution_builder.py` that computes the exact door segment position for each topology edge that produces an interior door. The function takes solved spaces (dict of SpaceGeometry), topology pairs, and building rect, and returns a mapping of `frozenset({space_a_id, space_b_id})` to a segment `((x1, y1), (x2, y2))`.

The function MUST use `Rect.shared_edge_segment()` and `should_draw_interior_door()` from constants, producing identical results to the renderer's door position computation.

#### Scenario: Hall-bedroom door segment

- **GIVEN** a solved floor with `hall` rect (3640, 2275, 2730, 910) and `bed2` rect (0, 0, 3640, 3185)
- **AND** topology declares adjacency between `hall` and `bed2`
- **AND** `should_draw_interior_door("hall", "bedroom")` returns True
- **WHEN** `compute_door_segments()` runs
- **THEN** the result contains `frozenset({"hall", "bed2"})` mapped to the longest shared edge segment between hall's rects and bed2's rects

#### Scenario: Bedroom-bedroom adjacency produces no door segment

- **GIVEN** a solved floor with `bed2` and `bed3` both type `bedroom`, topology-adjacent
- **AND** `should_draw_interior_door("bedroom", "bedroom")` returns False
- **WHEN** `compute_door_segments()` runs
- **THEN** the result does NOT contain an entry for `frozenset({"bed2", "bed3"})`

#### Scenario: L-shaped hall with multiple rects

- **GIVEN** a hall with 3 rects and a bedroom with 1 rect
- **AND** only one hall rect shares an edge with the bedroom rect
- **WHEN** `compute_door_segments()` runs
- **THEN** the returned segment is from the shared edge of those two specific rects (the longest match across all rect pairs)
