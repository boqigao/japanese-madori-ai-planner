## MODIFIED Requirements

### Requirement: Soft Objective Minimization
The system MUST minimize a combined objective covering area targets, alignment, compactness, and orientation preference. Hall area overshoot above target MUST receive strong penalty so circulation expansion is disfavored. In addition, orientation preference terms MUST use `site.north` to infer north/south envelope edges, then prefer `ldk`/`bedroom`/`master_bedroom` touching the inferred south edge and prefer `washroom`/`bath`/`toilet`/`wc`/`storage` touching the inferred north edge.

#### Scenario: Hall overshoot is strongly penalized
- **GIVEN** a feasible floor where hall can expand while keeping all hard constraints satisfied
- **WHEN** the solver optimizes objective terms
- **THEN** hall area above target incurs high overshoot cost and the selected plan favors smaller hall area in grid cells

#### Scenario: South preference for major rooms
- **GIVEN** `site.north=top` and a feasible floor containing `ldk` and `bedroom2`
- **WHEN** solver objective penalties are evaluated
- **THEN** plans where `ldk`/`bedroom2` touch the bottom envelope edge (south) receive lower orientation penalty than plans without south touch

#### Scenario: North preference for service rooms
- **GIVEN** `site.north=top` and a feasible floor containing `wash1`, `bath1`, and `storage1`
- **WHEN** solver objective penalties are evaluated
- **THEN** plans where those rooms touch the top envelope edge (north) receive lower orientation penalty than plans without north touch

#### Scenario: Orientation remains soft under tight topology
- **GIVEN** a constrained floor where adjacency and 455mm-grid-aligned packing make full orientation preference impossible
- **WHEN** the solver optimizes
- **THEN** the solver MAY accept unmet orientation preference by paying configured soft penalty while still satisfying all hard constraints
