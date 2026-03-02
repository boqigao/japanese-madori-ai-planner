## MODIFIED Requirements

### Requirement: Window Symbols

The system MUST draw window symbols on exterior edges of eligible room types. Exterior segments occupied by embedded closets MUST be excluded from window placement. The renderer MUST read `blocked_exterior_segments` from each `EmbeddedClosetGeometry` and add them to the window blocked set alongside entry door blocked segments.

#### Scenario: Exterior window on unblocked wall

- **GIVEN** a bedroom with an exterior-facing edge on the south wall
- **AND** no embedded closet occupies that edge
- **WHEN** the renderer draws windows
- **THEN** a window symbol is rendered on the south exterior edge

#### Scenario: No window on CL-occupied exterior edge

- **GIVEN** a bedroom rect (6370, 0, 2730, 5460) with CL rect (6370, 0, 2730, 910) at the north end
- **AND** the north edge (y=0) is on the building boundary (exterior)
- **AND** the CL reports `blocked_exterior_segments` containing the segment ((6370, 0), (9100, 0))
- **WHEN** the renderer draws windows
- **THEN** no window is drawn on the north edge segment ((6370, 0), (9100, 0))
- **AND** windows ARE drawn on other eligible exterior edges (east wall below CL, south wall)

#### Scenario: Partial exterior blockage

- **GIVEN** a bedroom where CL occupies the right end of the north exterior wall
- **AND** the CL blocks the segment ((7280, 0), (9100, 0)) but leaves ((6370, 0), (7280, 0)) unblocked
- **WHEN** the renderer draws windows
- **THEN** a window may be drawn on the unblocked segment if it meets the minimum window length (1365mm)

### Requirement: Door Symbols

The system MUST draw opening symbols on realized shared boundaries for indoor-to-indoor and indoor-to-outdoor access edges where appropriate. When an embedded closet occupies a portion of the wall containing a door segment, the door symbol MUST be positioned on the portion of the shared segment that does not overlap with the CL rect.

#### Scenario: Door avoids CL on shared wall

- **GIVEN** a bedroom with hall adjacency on the right wall
- **AND** the shared segment between hall and bedroom spans y=3185 to y=5460 (2275mm)
- **AND** CL occupies the right wall from y=3185 to y=4550 (1365mm deep into the room)
- **WHEN** the renderer draws the interior door
- **THEN** the door symbol is drawn on the non-CL portion of the shared segment (y=4550 to y=5460)
