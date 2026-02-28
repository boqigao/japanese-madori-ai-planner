## 1. Preflight Toilet Topology Contract

- [x] 1.1 Add toilet circulation topology checks in `plan_engine/preflight.py` (require each `toilet/wc` to have topology adjacency to `hall`/`entry`/`stair`).
- [x] 1.2 Update wet-fit preflight logic in `plan_engine/preflight.py` so wet core fit focuses on `washroom` + `bath`, with toilet validated independently.
- [x] 1.3 Add preflight regression tests in `tests/preflight/` covering missing toilet topology edge and valid independent toilet case.

## 2. Solver Wet-Core and Toilet Constraint Split

- [x] 2.1 Refactor `plan_engine/solver/workflow.py` wet constraints to keep mandatory bath-washroom coupling while removing forced toilet-in-cluster connectivity.
- [x] 2.2 Add explicit solver constraints in `plan_engine/solver/workflow.py` to realize at least one toilet circulation adjacency edge when toilet exists.
- [x] 2.3 Add/extend solver tests in `tests/solver/` for feasible toilet circulation layouts and infeasible missing-circulation layouts.

## 3. Validator Reachability and Pass-through Rules

- [x] 3.1 Extend toilet reachability validation in `plan_engine/validator/connectivity.py` so `toilet/wc` must be reachable from entry via realized topology.
- [x] 3.2 Add bedroom-pass-through detection for toilet routes in `plan_engine/validator/connectivity.py` and emit hard errors when violated.
- [x] 3.3 Add validator regression tests in `tests/validator/` for unreachable toilet and bedroom-pass-through toilet path cases.

## 4. Spec and Example Alignment

- [x] 4.1 Update affected benchmark/example specs under `examples/*/spec.yaml` to include explicit toilet circulation topology edges.
- [x] 4.2 Regenerate affected example outputs and confirm toilet doors appear through topology-driven rendering (no renderer rule changes).

## 5. End-to-End Verification

- [x] 5.1 Run `make verify` and fix any failures.
- [x] 5.2 Run `make test` and confirm the full suite passes with coverage threshold met.
