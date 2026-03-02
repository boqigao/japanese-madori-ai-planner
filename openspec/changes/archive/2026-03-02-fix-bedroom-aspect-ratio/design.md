## Context

The solver uses CP-SAT with linear inequality constraints to bound bedroom aspect ratios. Currently, `workflow_spaces.py` lines 221-222 enforce:

```python
ctx.model.Add(2 * rect.w <= 5 * rect.h)  # w/h ≤ 2.5
ctx.model.Add(2 * rect.h <= 5 * rect.w)  # h/w ≤ 2.5
```

This allows ratios up to 1:2.5. Architectural review shows the standard range for Japanese bedrooms is 1:1.25 ~ 1:1.5. 47% of example bedrooms exceed 1:1.5.

An existing soft penalty `|w - h|` (shape_balance_penalties, lines 226-233) already pushes toward square shapes but is overpowered by other objectives due to the loose hard constraint.

## Goals / Non-Goals

**Goals:**
- Reduce the bedroom aspect ratio hard constraint to 1:1.80 so no bedroom can exceed this ratio.
- Verify all 10 examples still solve with the tighter constraint.

**Non-Goals:**
- Changing minimum short side dimensions (2275mm stays acceptable).
- Modifying soft penalty weights or formulation.
- Changing constraints for non-bedroom types.

## Decisions

### Decision: Use `5*w ≤ 9*h` (1:1.80) instead of stricter `2*w ≤ 3*h` (1:1.50)

**Rationale:** 1:1.80 provides margin beyond the ideal 1:1.5 range, reducing risk of solver infeasibility for compact envelopes while still eliminating the most problematic cases. Combined with the existing soft penalty pushing toward square, most rooms will naturally fall in 1:1 ~ 1:1.5.

**Alternatives considered:**
- `2*w ≤ 3*h` (1:1.50) — Matches the architectural ideal exactly but leaves zero margin. Compact houses with 4-5LDK may fail to solve.
- Keeping hard constraint loose + strengthening soft penalty — Does not guarantee elimination of worst cases; solver could still produce 1:2.0+ rooms under pressure.

### Decision: Change only the hard constraint, leave soft penalty unchanged

The existing `|w - h|` soft penalty already guides toward better proportions. With the tighter hard constraint acting as a safety net, the penalty becomes more effective within the narrower range.

## Risks / Trade-offs

- **[Solver infeasibility]** → Run all 10 examples to verify. If any fail, investigate whether the specific spec requires relaxation or is inherently over-constrained.
- **[Layout quality regression]** → Tighter ratio may force the solver into different room arrangements. Visual inspection of all regenerated examples is required.
- **[Performance]** → Tighter constraints reduce the search space, which typically helps solver performance. No negative impact expected.
