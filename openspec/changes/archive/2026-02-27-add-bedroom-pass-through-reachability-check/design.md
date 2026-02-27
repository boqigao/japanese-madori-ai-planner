## Context

Current preflight checks validate basic topology reachability but do not explicitly reject bedroom circulation patterns that require walking through another bedroom. This permits unrealistic benchmark specs and shifts discovery of circulation defects to late manual review. The change must stay within architecture boundaries: preflight performs graph-based feasibility checks, solver remains unchanged, renderer remains read-only.

## Goals / Non-Goals

**Goals:**
- Add a deterministic preflight check that fails when any bedroom is only reachable via bedroom pass-through paths.
- Produce actionable diagnostics (blocked bedroom IDs and representative path evidence) in CLI/report output.
- Update benchmark `examples/*/spec.yaml` topologies to satisfy the new preflight rule.
- Add tests to prevent regressions in preflight graph semantics.

**Non-Goals:**
- No new CP-SAT constraints or objective terms in `plan_engine/solver/`.
- No geometry post-processing in `plan_engine/renderer/`.
- No changes to stair dimensional rules or structural validator metrics.

## Decisions

1. **Implement bedroom pass-through guard in `plan_engine/preflight.py`**
   - Build a floor-level undirected topology graph from declared edges and stair connectors.
   - Evaluate bedroom accessibility from entry using a restricted traversal where bedroom nodes are terminal targets, not transit nodes.
   - Rationale: This captures the residential rule directly at spec level and fails fast before solve.
   - Alternative considered: post-solve validator-only rule. Rejected because invalid specs would still consume solve time.

2. **Treat bedroom pass-through violation as preflight error**
   - Violation blocks solver execution and appears in `report.txt` as actionable error text.
   - Rationale: The user expectation is hard feasibility, not soft warning.
   - Alternative considered: warning-only. Rejected because benchmark generation must be gated.

3. **Keep generic topology reachability behavior, extend with bedroom-specific rule**
   - Existing disconnected-graph warning remains, while bedroom pass-through becomes strict.
   - Rationale: preserves compatibility for non-bedroom exploratory specs while enforcing realistic private-room circulation.

4. **Benchmark migration by topology edge edits only**
   - Modify `examples/*/spec.yaml` adjacency so every bedroom has at least one non-bedroom access route (usually via hall).
   - Rationale: lowest-risk migration without changing area budgets or envelope assumptions.

## Risks / Trade-offs

- **[Risk] Over-restrictive traversal semantics may flag intentional suite-like layouts** → Mitigation: define pass-through rule narrowly (bedroom cannot be intermediate node; bedroom can still connect to multiple spaces).
- **[Risk] False positives from missing stair connector interpretation** → Mitigation: reuse existing stair portal mapping logic and include multi-floor unit tests.
- **[Risk] Benchmark edits may alter expected example character** → Mitigation: keep room sets and envelope sizes unchanged; only rewrite topology links.

## Migration Plan

1. Implement preflight helper(s) for restricted bedroom reachability and integrate into preflight result assembly.
2. Update preflight report formatting in `main.py`/`plan_engine/io.py` path if needed to expose new error details.
3. Add unit tests in `tests/preflight/` for valid/invalid bedroom pass-through graph patterns.
4. Patch benchmark specs failing the new check; regenerate `plan_output` artifacts.
5. Run targeted example generation and preflight test suite.

Rollback strategy:
- Revert the new preflight error check and spec topology edits in one change if unexpected false positives block valid user specs.

## Open Questions

- Should this rule apply to all bedroom-like labels (`bedroom`, `master_bedroom`) only, or configurable custom tags in future DSL extensions?
- Should generic topology disconnection also be upgraded from warning to error in a follow-up change for stricter spec gating?
