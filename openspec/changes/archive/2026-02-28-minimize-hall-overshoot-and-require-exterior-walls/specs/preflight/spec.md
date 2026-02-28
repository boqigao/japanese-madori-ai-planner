## ADDED Requirements

### Requirement: Major Room Exterior-Touch Feasibility
The system MUST run a deterministic preflight feasibility check for the exterior-touch hard rule. If a floor contains any `bedroom`, `master_bedroom`, or `ldk`, then the floor buildable mask MUST provide envelope-contact opportunity; otherwise preflight MUST fail before solving.

#### Scenario: Buildable mask has no exterior contact and major room exists
- **GIVEN** floor `F2` has only interior buildable rectangles (no shared edge with envelope boundary)
- **AND** `F2` includes `bedroom2` or `ldk`
- **WHEN** preflight runs
- **THEN** preflight reports an error that major-room exterior-touch is impossible on that floor

#### Scenario: Buildable mask touches envelope and major room exists
- **GIVEN** floor `F2` buildable mask shares boundary segments with the envelope
- **AND** `F2` includes `master_bedroom`
- **WHEN** preflight runs
- **THEN** no exterior-touch feasibility error is produced for that floor
