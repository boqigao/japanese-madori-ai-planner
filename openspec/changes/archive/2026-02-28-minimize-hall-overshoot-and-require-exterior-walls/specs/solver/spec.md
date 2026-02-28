## MODIFIED Requirements

### Requirement: Space Placement
The system MUST create `RectVar` decision variables for each space and place indoor spaces within the floor indoor buildable mask. Outdoor spaces (`balcony`/`veranda`) MUST be placed within floor envelope bounds and MAY occupy regions outside indoor buildable mask. In addition, each `bedroom`, `master_bedroom`, and `ldk` MUST realize at least one shared edge segment with the floor exterior boundary.

#### Scenario: Indoor placement constrained by buildable mask
- **GIVEN** a floor with buildable mask narrower than the full envelope
- **WHEN** the solver runs
- **THEN** every indoor space rectangle is placed fully inside buildable mask cells

#### Scenario: Bedroom requires exterior-touch
- **GIVEN** a floor with `bedroom2` defined and all dimensions aligned to the 455mm grid
- **WHEN** the solver completes
- **THEN** `bedroom2` has at least one exterior-touch edge with positive length in mm

#### Scenario: LDK requires exterior-touch
- **GIVEN** a floor with `ldk` that may use one or more rectangles
- **WHEN** the solver completes
- **THEN** at least one `ldk` component touches the envelope boundary with positive overlap length

### Requirement: Soft Objective Minimization
The system MUST minimize a combined objective covering area targets, alignment, and compactness. Hall area overshoot above target MUST receive a stronger penalty than before so circulation expansion is disfavored relative to major-room area preservation.

#### Scenario: Hall overshoot is strongly penalized
- **GIVEN** a feasible floor where hall can expand while keeping all hard constraints satisfied
- **WHEN** the solver optimizes objective terms
- **THEN** hall area above target incurs high overshoot cost and the selected plan favors smaller hall area in cells

#### Scenario: Hall remains feasible under strong penalty
- **GIVEN** a constrained floor where hall must grow to keep topology connected
- **WHEN** the solver optimizes
- **THEN** hall may still exceed target, but only after paying the configured overshoot penalty
