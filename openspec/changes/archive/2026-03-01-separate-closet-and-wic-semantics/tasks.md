## 1. DSL and Model Semantics

- [x] 1.1 Extend `plan_engine/models.py` and `plan_engine/constants.py` with explicit closet/WIC semantic fields and type enums while keeping `storage` backward-compatible.
- [x] 1.2 Update `plan_engine/dsl.py` to parse closet metadata and `wic` parent references, including 455mm-grid validation for closet/WIC dimensions.
- [x] 1.3 Add parse-time unit tests under `tests/dsl/` for valid and invalid closet/WIC declarations.

## 2. Preflight and Solver Constraints

- [x] 2.1 Add declaration consistency checks in `plan_engine/preflight.py` for missing parent rooms, invalid WIC parent types, and impossible access declarations.
- [x] 2.2 Implement closet/WIC placement constraints in `plan_engine/solver/workflow.py` and supporting helpers in `plan_engine/solver/constraints.py` / `plan_engine/solver/space_specs.py`.
- [x] 2.3 Add solver tests under `tests/solver/` to verify parent association, 455mm alignment, and no bedroom-pass-through regressions with closet/WIC enabled.

## 3. Validator and Renderer Behavior

- [x] 3.1 Add validator checks in `plan_engine/validator/connectivity.py` and `plan_engine/validator/geometry.py` for closet/WIC topology, access edges, and parent mismatch diagnostics.
- [x] 3.2 Update renderer logic in `plan_engine/renderer/core.py`, `plan_engine/renderer/annotations.py`, and `plan_engine/renderer/symbols.py` to display closet/WIC distinctly and suppress bedroom-to-bedroom door symbols unless explicitly allowed.
- [x] 3.3 Add renderer/validator regression tests under `tests/renderer/` and `tests/validator/` using benchmark-like fixtures.

## 4. Benchmarks, Docs, and Verification

- [x] 4.1 Update affected benchmark/example specs in `examples/*/spec.yaml` to use closet/WIC semantics where intended instead of overloading `storage`.
- [x] 4.2 Update user documentation in `README.md` and `docs/how_to_use.md` to explain closet vs WIC vs storage modeling rules.
- [x] 4.3 Run `make verify` and `make test`, then store updated outputs for impacted examples.
