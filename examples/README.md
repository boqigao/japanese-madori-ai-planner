# Example Specs

This folder contains 10 runnable benchmark-style examples. Each case has:

- `spec.yaml`: input DSL
- `plan_output/`: generated `F*.svg`, `F*.png`, `solution.json`, `report.txt`

## Cases

1. `1. Compact 2F` - compact two-floor baseline
2. `2. Mid 2F` - mid-size two-floor with pantry + 3 bedrooms + WIC
3. `3. Slim 2F` - slim two-floor variant (uses `L_landing` stair for feasibility)
4. `4. Near-square 2F` - near-square two-floor with larger room mix
5. `5. Recess-inspired 2F` - recess-inspired program on rectangular envelope
6. `6. 1F Hiraya Standard` - one-floor standard hiraya layout
7. `7. 1F Hiraya Wide` - wider one-floor hiraya with more private rooms + WIC
8. `8. Balcony-side 2F` - balcony-side inspired two-floor zoning
9. `9. Stepback-inspired 2F` - stepback-inspired program on rectangular envelope
10. `10. Public-Private Split 2F` - larger two-floor public/private split

## Regenerate All Examples

```bash
for d in examples/*; do
  [ -f "$d/spec.yaml" ] || continue
  uv run python main.py --spec "$d/spec.yaml" --outdir "$d/plan_output" --solver-timeout 20
done
```

Several cases now model bedroom storage explicitly with `closet` / `wic` (instead of generic `storage`).
All 10 examples currently generate with `valid=True` on the latest solver/validator.
