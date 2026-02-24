from __future__ import annotations

from ortools.sat.python import cp_model

from plan_engine.solver.rect_var import RectVar


def touching_constraint(
    model: cp_model.CpModel,
    rects_a: list[RectVar],
    rects_b: list[RectVar],
    max_w: int,
    max_h: int,
    prefix: str,
    required: bool,
) -> cp_model.IntVar:
    if not rects_a or not rects_b:
        raise ValueError("touching constraints require non-empty rectangle sets")

    touch_candidates: list[cp_model.IntVar] = []
    for i, rect_a in enumerate(rects_a):
        for j, rect_b in enumerate(rects_b):
            touch_candidates.append(
                pair_touch_bool(
                    model=model,
                    rect_a=rect_a,
                    rect_b=rect_b,
                    max_w=max_w,
                    max_h=max_h,
                    prefix=f"{prefix}_{i}_{j}",
                )
            )

    touch_any = model.NewBoolVar(f"{prefix}_touch_any")
    model.AddMaxEquality(touch_any, touch_candidates)
    if required:
        model.Add(touch_any == 1)
    return touch_any


def edge_touch_constraint(
    model: cp_model.CpModel,
    portal_rect: RectVar,
    rects_b: list[RectVar],
    edge: str,
    max_w: int,
    max_h: int,
    prefix: str,
    required: bool,
) -> cp_model.IntVar:
    if not rects_b:
        raise ValueError("edge touching constraints require non-empty counterpart rectangles")

    touch_candidates: list[cp_model.IntVar] = []
    for index, rect_b in enumerate(rects_b):
        touch_candidates.append(
            pair_edge_touch_bool(
                model=model,
                rect_a=portal_rect,
                rect_b=rect_b,
                edge=edge,
                max_w=max_w,
                max_h=max_h,
                prefix=f"{prefix}_{index}",
            )
        )
    touch_any = model.NewBoolVar(f"{prefix}_touch_any")
    model.AddMaxEquality(touch_any, touch_candidates)
    if required:
        model.Add(touch_any == 1)
    return touch_any


def pair_edge_touch_bool(
    model: cp_model.CpModel,
    rect_a: RectVar,
    rect_b: RectVar,
    edge: str,
    max_w: int,
    max_h: int,
    prefix: str,
) -> cp_model.IntVar:
    overlap_x = overlap_length(
        model=model,
        a_start=rect_a.x,
        a_end=rect_a.x_end,
        b_start=rect_b.x,
        b_end=rect_b.x_end,
        limit=max_w,
        prefix=f"{prefix}_ovx",
    )
    overlap_y = overlap_length(
        model=model,
        a_start=rect_a.y,
        a_end=rect_a.y_end,
        b_start=rect_b.y,
        b_end=rect_b.y_end,
        limit=max_h,
        prefix=f"{prefix}_ovy",
    )

    touch = model.NewBoolVar(f"{prefix}_touch")
    if edge == "left":
        model.Add(rect_b.x_end == rect_a.x).OnlyEnforceIf(touch)
        model.Add(overlap_y >= 1).OnlyEnforceIf(touch)
    elif edge == "right":
        model.Add(rect_b.x == rect_a.x_end).OnlyEnforceIf(touch)
        model.Add(overlap_y >= 1).OnlyEnforceIf(touch)
    elif edge == "top":
        model.Add(rect_b.y_end == rect_a.y).OnlyEnforceIf(touch)
        model.Add(overlap_x >= 1).OnlyEnforceIf(touch)
    elif edge == "bottom":
        model.Add(rect_b.y == rect_a.y_end).OnlyEnforceIf(touch)
        model.Add(overlap_x >= 1).OnlyEnforceIf(touch)
    else:
        raise ValueError(f"unsupported portal edge '{edge}'")
    return touch


def enforce_internal_portal_edge(
    model: cp_model.CpModel,
    portal_rect: RectVar,
    edge: str,
    max_w: int,
    max_h: int,
) -> None:
    if edge == "left":
        model.Add(portal_rect.x >= 1)
        return
    if edge == "right":
        model.Add(portal_rect.x_end <= max_w - 1)
        return
    if edge == "top":
        model.Add(portal_rect.y >= 1)
        return
    if edge == "bottom":
        model.Add(portal_rect.y_end <= max_h - 1)
        return
    raise ValueError(f"unsupported portal edge '{edge}'")


def pair_touch_bool(
    model: cp_model.CpModel,
    rect_a: RectVar,
    rect_b: RectVar,
    max_w: int,
    max_h: int,
    prefix: str,
) -> cp_model.IntVar:
    overlap_x = overlap_length(
        model=model,
        a_start=rect_a.x,
        a_end=rect_a.x_end,
        b_start=rect_b.x,
        b_end=rect_b.x_end,
        limit=max_w,
        prefix=f"{prefix}_ovx",
    )
    overlap_y = overlap_length(
        model=model,
        a_start=rect_a.y,
        a_end=rect_a.y_end,
        b_start=rect_b.y,
        b_end=rect_b.y_end,
        limit=max_h,
        prefix=f"{prefix}_ovy",
    )

    left = model.NewBoolVar(f"{prefix}_left")
    right = model.NewBoolVar(f"{prefix}_right")
    up = model.NewBoolVar(f"{prefix}_up")
    down = model.NewBoolVar(f"{prefix}_down")

    model.Add(rect_a.x_end == rect_b.x).OnlyEnforceIf(right)
    model.Add(overlap_y >= 1).OnlyEnforceIf(right)

    model.Add(rect_b.x_end == rect_a.x).OnlyEnforceIf(left)
    model.Add(overlap_y >= 1).OnlyEnforceIf(left)

    model.Add(rect_a.y_end == rect_b.y).OnlyEnforceIf(down)
    model.Add(overlap_x >= 1).OnlyEnforceIf(down)

    model.Add(rect_b.y_end == rect_a.y).OnlyEnforceIf(up)
    model.Add(overlap_x >= 1).OnlyEnforceIf(up)

    touch = model.NewBoolVar(f"{prefix}_touch")
    model.AddMaxEquality(touch, [left, right, up, down])
    return touch


def overlap_length(
    model: cp_model.CpModel,
    a_start: cp_model.IntVar,
    a_end: cp_model.IntVar,
    b_start: cp_model.IntVar,
    b_end: cp_model.IntVar,
    limit: int,
    prefix: str,
) -> cp_model.IntVar:
    low = model.NewIntVar(0, limit, f"{prefix}_low")
    high = model.NewIntVar(0, limit, f"{prefix}_high")
    overlap = model.NewIntVar(-limit, limit, f"{prefix}_ov")
    model.AddMaxEquality(low, [a_start, b_start])
    model.AddMinEquality(high, [a_end, b_end])
    model.Add(overlap == high - low)
    return overlap


def enforce_non_adjacent(
    model: cp_model.CpModel,
    rects_a: list[RectVar],
    rects_b: list[RectVar],
    prefix: str,
) -> None:
    for i, rect_a in enumerate(rects_a):
        for j, rect_b in enumerate(rects_b):
            a_right = model.NewBoolVar(f"{prefix}_{i}_{j}_a_right")
            b_right = model.NewBoolVar(f"{prefix}_{i}_{j}_b_right")
            a_below = model.NewBoolVar(f"{prefix}_{i}_{j}_a_below")
            b_below = model.NewBoolVar(f"{prefix}_{i}_{j}_b_below")

            model.Add(rect_a.x >= rect_b.x_end + 1).OnlyEnforceIf(a_right)
            model.Add(rect_b.x >= rect_a.x_end + 1).OnlyEnforceIf(b_right)
            model.Add(rect_a.y >= rect_b.y_end + 1).OnlyEnforceIf(a_below)
            model.Add(rect_b.y >= rect_a.y_end + 1).OnlyEnforceIf(b_below)

            model.AddBoolOr([a_right, b_right, a_below, b_below])


def enforce_exterior_touch(
    model: cp_model.CpModel,
    rects: list[RectVar],
    max_w: int,
    max_h: int,
    prefix: str,
) -> None:
    if not rects:
        raise ValueError("exterior touch constraints require non-empty rectangles")

    per_rect_touch: list[cp_model.IntVar] = []
    for index, rect in enumerate(rects):
        left = model.NewBoolVar(f"{prefix}_{index}_left")
        right = model.NewBoolVar(f"{prefix}_{index}_right")
        top = model.NewBoolVar(f"{prefix}_{index}_top")
        bottom = model.NewBoolVar(f"{prefix}_{index}_bottom")

        model.Add(rect.x == 0).OnlyEnforceIf(left)
        model.Add(rect.x_end == max_w).OnlyEnforceIf(right)
        model.Add(rect.y == 0).OnlyEnforceIf(top)
        model.Add(rect.y_end == max_h).OnlyEnforceIf(bottom)

        rect_touch = model.NewBoolVar(f"{prefix}_{index}_touch")
        model.AddMaxEquality(rect_touch, [left, right, top, bottom])
        per_rect_touch.append(rect_touch)

    touch_any = model.NewBoolVar(f"{prefix}_touch_any")
    model.AddMaxEquality(touch_any, per_rect_touch)
    model.Add(touch_any == 1)
