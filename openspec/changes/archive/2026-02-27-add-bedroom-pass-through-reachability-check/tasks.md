## 1. Preflight Reachability Rule

- [x] 1.1 Extend `plan_engine/preflight.py` with a bedroom-reachability traversal that treats `bedroom`/`master_bedroom` as non-transit nodes.
- [x] 1.2 Add violation collection and structured diagnostics (floor ID, blocked bedroom ID, path evidence) to the preflight result model (`plan_engine/models.py` if additional fields are required).
- [x] 1.3 Integrate the new preflight error into CLI/report generation path (`main.py`, `plan_engine/io.py`) so solver execution is blocked on violation.

## 2. Benchmark Topology Migration

- [x] 2.1 Scan `examples/*/spec.yaml` for bedroom pass-through circulation patterns and list affected cases.
- [x] 2.2 Patch affected topology adjacency in each failing benchmark spec to provide non-bedroom access routes (typically hall-linked).
- [x] 2.3 Regenerate each modified example output under `examples/*/plan_output` and confirm preflight passes without bedroom-transit errors.

## 3. Test Coverage

- [x] 3.1 Add unit tests under `tests/preflight/` for valid/invalid bedroom reachability patterns, including multi-floor stair-linked circulation.
- [x] 3.2 Add regression tests that assert deterministic error messages for blocked bedrooms.
- [x] 3.3 Add/adjust fixture resources under `resources/` for the new preflight scenarios.

## 4. Verification and Documentation

- [x] 4.1 Run `make verify` and `make test` to validate implementation and coverage impact.
- [x] 4.2 Update user-facing docs that describe topology authoring constraints (README and/or usage docs) to include the bedroom non-pass-through rule.
- [x] 4.3 Manually run representative examples (including modified benchmarks) and confirm report output is actionable.
