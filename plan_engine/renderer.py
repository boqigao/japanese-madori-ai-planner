from __future__ import annotations

from pathlib import Path

import cairosvg
import svgwrite

from .constants import MINOR_GRID_MM, TATAMI_MM2
from .models import FloorSolution, PlanSolution, Rect, SpaceGeometry
from .stair_logic import StairPortal, stair_portal_for_floor


SPACE_COLORS = {
    "entry": "#f8f0d9",
    "hall": "#efe9ff",
    "ldk": "#ffe2b8",
    "bedroom": "#d9f2ff",
    "master_bedroom": "#c5e8ff",
    "toilet": "#fbe7e6",
    "wc": "#fbe7e6",
    "washroom": "#e7fbfb",
    "bath": "#dcecff",
    "storage": "#f0f0f0",
}
WINDOW_SPACE_TYPES = {"ldk", "bedroom", "master_bedroom", "entry"}
LEGEND_ORDER = [
    "entry",
    "hall",
    "ldk",
    "master_bedroom",
    "bedroom",
    "toilet",
    "washroom",
    "bath",
    "storage",
]


class SvgRenderer:
    def __init__(self, scale: float = 0.12, margin_px: float = 220.0) -> None:
        self.scale = scale
        self.margin_px = margin_px

    def render(self, solution: PlanSolution, outdir: str | Path) -> list[Path]:
        output_dir = Path(outdir)
        output_dir.mkdir(parents=True, exist_ok=True)
        floor_ids = _sorted_floor_ids(solution.floors.keys())
        written: list[Path] = []
        for index, floor_id in enumerate(floor_ids):
            floor = solution.floors[floor_id]
            svg_target = output_dir / f"{floor_id}.svg"
            png_target = output_dir / f"{floor_id}.png"
            self._render_floor(solution, floor_id, floor, index, len(floor_ids), svg_target)
            self._export_png(svg_target, png_target)
            written.extend([svg_target, png_target])
        return written

    def _render_floor(
        self,
        solution: PlanSolution,
        floor_id: str,
        floor: FloorSolution,
        floor_index: int,
        total_floors: int,
        target: Path,
    ) -> None:
        width_px = self._x(solution.envelope.width) + self.margin_px
        height_px = self._y(solution.envelope.depth) + self.margin_px
        drawing = svgwrite.Drawing(
            filename=str(target),
            size=(f"{width_px}px", f"{height_px}px"),
            profile="tiny",
        )
        drawing.add(drawing.rect(insert=(0, 0), size=(width_px, height_px), fill="#fafafa"))

        site_rect = Rect(0, 0, solution.envelope.width, solution.envelope.depth)
        occupied_rects = _floor_rects(floor)
        building_rect = _bounding_rect(occupied_rects)

        self._draw_grid(drawing, site_rect, solution.grid.minor, solution.grid.major)
        self._draw_site_and_footprint(drawing, site_rect, building_rect)
        self._draw_spaces(drawing, floor)
        self._draw_stair(drawing, floor, floor_index, total_floors)
        self._draw_stair_connection_opening(drawing, floor, floor_index, total_floors)
        self._draw_interior_doors(drawing, floor)
        entry_segment = self._draw_entry_door(drawing, floor, building_rect)
        blocked_segments: set[tuple[tuple[int, int], tuple[int, int]]] = set()
        if entry_segment is not None:
            blocked_segments.add(_segment_key(entry_segment))
        self._draw_windows(drawing, floor, building_rect, blocked_segments)
        self._draw_room_dimension_guides(drawing, floor)
        self._draw_space_labels(drawing, floor)
        self._draw_title_block(drawing, floor_id, solution)
        self._draw_legend(drawing, floor, site_rect)
        self._draw_north_arrow(drawing, solution.north)
        self._draw_dimensions(drawing, site_rect, building_rect)

        drawing.save()

    def _draw_grid(
        self,
        drawing: svgwrite.Drawing,
        site_rect: Rect,
        minor_grid_mm: int,
        major_grid_mm: int,
    ) -> None:
        color = "#ececec"
        for x in range(site_rect.x, site_rect.x2 + 1, minor_grid_mm):
            drawing.add(
                drawing.line(
                    start=(self._x(x), self._y(site_rect.y)),
                    end=(self._x(x), self._y(site_rect.y2)),
                    stroke=color,
                    stroke_width=0.7,
                )
            )
        major_color = "#d1d1d1"
        for x in range(site_rect.x, site_rect.x2 + 1, major_grid_mm):
            drawing.add(
                drawing.line(
                    start=(self._x(x), self._y(site_rect.y)),
                    end=(self._x(x), self._y(site_rect.y2)),
                    stroke=major_color,
                    stroke_width=1.1,
                )
            )
        for y in range(site_rect.y, site_rect.y2 + 1, major_grid_mm):
            drawing.add(
                drawing.line(
                    start=(self._x(site_rect.x), self._y(y)),
                    end=(self._x(site_rect.x2), self._y(y)),
                    stroke=major_color,
                    stroke_width=1.1,
                )
            )
        for y in range(site_rect.y, site_rect.y2 + 1, minor_grid_mm):
            drawing.add(
                drawing.line(
                    start=(self._x(site_rect.x), self._y(y)),
                    end=(self._x(site_rect.x2), self._y(y)),
                    stroke=color,
                    stroke_width=0.7,
                )
            )

    def _draw_site_and_footprint(
        self, drawing: svgwrite.Drawing, site_rect: Rect, building_rect: Rect
    ) -> None:
        drawing.add(
            drawing.rect(
                insert=(self._x(site_rect.x), self._y(site_rect.y)),
                size=(site_rect.w * self.scale, site_rect.h * self.scale),
                fill="none",
                stroke="#6a6a6a",
                stroke_width=2,
                stroke_dasharray="8,4",
            )
        )
        drawing.add(
            drawing.rect(
                insert=(self._x(building_rect.x), self._y(building_rect.y)),
                size=(building_rect.w * self.scale, building_rect.h * self.scale),
                fill="none",
                stroke="#1f1f1f",
                stroke_width=3.5,
            )
        )
        if building_rect == site_rect:
            drawing.add(
                drawing.text(
                    "Site Envelope = Building Footprint",
                    insert=(self.margin_px + 2, self.margin_px - 60),
                    fill="#555555",
                    font_size=10,
                )
            )
        else:
            drawing.add(
                drawing.text(
                    "Site Envelope",
                    insert=(self.margin_px + 2, self.margin_px - 76),
                    fill="#666666",
                    font_size=10,
                )
            )
            drawing.add(
                drawing.text(
                    "Building Footprint",
                    insert=(self.margin_px + 2, self.margin_px - 60),
                    fill="#1f1f1f",
                    font_size=10,
                )
            )

    def _draw_spaces(self, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
        for space in _ordered_spaces(floor):
            fill = SPACE_COLORS.get(space.type, "#eeeeee")
            stroke_dash = "6,4" if space.id.startswith("auto_fill_") else None
            for rect in space.rects:
                attrs = {
                    "insert": (self._x(rect.x), self._y(rect.y)),
                    "size": (rect.w * self.scale, rect.h * self.scale),
                    "fill": fill,
                    "stroke": "none",
                }
                drawing.add(drawing.rect(**attrs))
            for p1, p2 in _space_boundary_segments(space.rects):
                line_attrs: dict[str, object] = {
                    "start": (self._x(p1[0]), self._y(p1[1])),
                    "end": (self._x(p2[0]), self._y(p2[1])),
                    "stroke": "#2f2f2f",
                    "stroke_width": 2.2,
                }
                if stroke_dash:
                    line_attrs["stroke_dasharray"] = stroke_dash
                drawing.add(drawing.line(**line_attrs))

    def _draw_stair(
        self,
        drawing: svgwrite.Drawing,
        floor: FloorSolution,
        floor_index: int,
        total_floors: int,
    ) -> None:
        if floor.stair is None:
            return
        stair = floor.stair
        is_top_floor = total_floors > 1 and floor_index == total_floors - 1
        portal = _portal_for_floor(
            floor=floor,
            floor_index=floor_index,
            total_floors=total_floors,
        )
        access_indices = [portal.component_index]
        for index, component in enumerate(stair.components):
            is_void = is_top_floor and index not in access_indices
            drawing.add(
                drawing.rect(
                    insert=(self._x(component.x), self._y(component.y)),
                    size=(component.w * self.scale, component.h * self.scale),
                    fill="#f4f4f4" if is_void else "#ffffff",
                    stroke="#202020",
                    stroke_width=2.6,
                    stroke_dasharray="4,3" if is_void else "8,4",
                )
            )
            if is_void:
                self._draw_void_hatch(drawing, component)

        visible_step_indices = set(range(len(stair.components)))
        if is_top_floor:
            visible_step_indices = set(access_indices)
            void_components = [
                stair.components[index]
                for index in range(len(stair.components))
                if index not in access_indices
            ]
            if void_components:
                void_bbox = _bounding_rect(void_components)
                drawing.add(
                    drawing.text(
                        "Open To Below",
                        insert=(self._x(void_bbox.x + void_bbox.w / 2), self._y(void_bbox.y + void_bbox.h / 2)),
                        fill="#555555",
                        font_size=9,
                        text_anchor="middle",
                    )
                )
                self._draw_void_guardrail(drawing, void_bbox)

        self._draw_stair_steps(
            drawing,
            stair.type,
            stair.tread_count,
            stair.components,
            visible_indices=visible_step_indices,
        )
        direction = "UP"
        if is_top_floor:
            direction = "DN"
        label_x, label_y = _stair_label_point(stair.components, portal.component_index)
        drawing.add(
            drawing.text(
                f"Stair ({direction})",
                insert=(self._x(label_x), self._y(label_y)),
                fill="#202020",
                font_size=11,
                text_anchor="middle",
            )
        )
        stair_area_sqm = sum(component.area for component in stair.components) / 1_000_000
        drawing.add(
            drawing.text(
                f"{stair_area_sqm:.1f}sqm  H{stair.floor_height}  R{stair.riser_count}@{stair.riser_mm}",
                insert=(self._x(label_x), self._y(label_y + 120)),
                fill="#3a3a3a",
                font_size=8.5,
                text_anchor="middle",
            )
        )
        drawing.add(
            drawing.text(
                f"T{stair.tread_count}@{stair.tread_mm}  Landing {stair.landing_size[0]}x{stair.landing_size[1]}",
                insert=(self._x(label_x), self._y(label_y + 205)),
                fill="#3a3a3a",
                font_size=8.0,
                text_anchor="middle",
            )
        )

    def _draw_stair_connection_opening(
        self,
        drawing: svgwrite.Drawing,
        floor: FloorSolution,
        floor_index: int,
        total_floors: int,
    ) -> None:
        if floor.stair is None:
            return
        hall_id = floor.stair.connects.get(floor.id)
        if hall_id is None:
            return
        hall = floor.spaces.get(hall_id)
        if hall is None:
            return
        portal = _portal_for_floor(
            floor=floor,
            floor_index=floor_index,
            total_floors=total_floors,
        )
        portal_component = floor.stair.components[portal.component_index]
        segment = _portal_hall_opening_segment(portal_component, hall.rects, portal.edge)
        if segment is None:
            return
        drawing.add(
            drawing.line(
                start=(self._x(segment[0][0]), self._y(segment[0][1])),
                end=(self._x(segment[1][0]), self._y(segment[1][1])),
                stroke="#ffffff",
                stroke_width=7,
            )
        )
        drawing.add(
            drawing.line(
                start=(self._x(segment[0][0]), self._y(segment[0][1])),
                end=(self._x(segment[1][0]), self._y(segment[1][1])),
                stroke="#5e5e5e",
                stroke_width=1.0,
            )
        )

    def _draw_interior_doors(self, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
        door_entries: list[tuple[int, tuple[tuple[int, int], tuple[int, int]]]] = []
        for index, (left_id, right_id) in enumerate(floor.topology):
            if floor.stair is not None and (left_id == floor.stair.id or right_id == floor.stair.id):
                continue
            left_rects = _entity_rects(floor, left_id)
            right_rects = _entity_rects(floor, right_id)
            if not left_rects or not right_rects:
                continue
            segment = _shared_segment(left_rects, right_rects)
            if segment is None:
                continue
            door_entries.append((index, segment))

        line_counts: dict[tuple[str, int], int] = {}
        for _, segment in door_entries:
            key = _door_line_key(segment)
            line_counts[key] = line_counts.get(key, 0) + 1

        for index, segment in door_entries:
            key = _door_line_key(segment)
            crowded_line = line_counts.get(key, 0) >= 3
            self._draw_door_symbol(
                drawing,
                segment[0],
                segment[1],
                exterior=False,
                boundary=None,
                reverse_swing=(index % 2 == 1),
                draw_arc=not crowded_line,
            )

    def _draw_entry_door(
        self, drawing: svgwrite.Drawing, floor: FloorSolution, building_rect: Rect
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        entry_spaces = [space for space in floor.spaces.values() if space.type == "entry"]
        if not entry_spaces:
            return None

        best_segment: tuple[tuple[int, int], tuple[int, int]] | None = None
        best_len = -1
        for entry in entry_spaces:
            for rect in entry.rects:
                for segment in _exterior_segments(rect, building_rect):
                    seg_len = _segment_length(segment[0], segment[1])
                    if seg_len > best_len:
                        best_len = seg_len
                        best_segment = segment
        if best_segment is None:
            return None
        self._draw_door_symbol(
            drawing,
            best_segment[0],
            best_segment[1],
            exterior=True,
            boundary=building_rect,
            reverse_swing=False,
            draw_arc=True,
        )
        return best_segment

    def _draw_windows(
        self,
        drawing: svgwrite.Drawing,
        floor: FloorSolution,
        building_rect: Rect,
        blocked_segments: set[tuple[tuple[int, int], tuple[int, int]]],
    ) -> None:
        min_window_segment = 1365
        for space in floor.spaces.values():
            if space.type not in WINDOW_SPACE_TYPES:
                continue
            candidate_segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
            for rect in space.rects:
                candidate_segments.extend(_exterior_segments(rect, building_rect))
            if not candidate_segments:
                continue

            seen: set[tuple[tuple[int, int], tuple[int, int]]] = set()
            unique_segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
            for segment in candidate_segments:
                key = _segment_key(segment)
                if key in seen:
                    continue
                seen.add(key)
                unique_segments.append(segment)

            for segment in unique_segments:
                key = _segment_key(segment)
                if key in blocked_segments:
                    continue
                length = _segment_length(segment[0], segment[1])
                if length < min_window_segment:
                    continue
                if length >= 3600:
                    self._draw_window_symbol(drawing, segment[0], segment[1], offset_ratio=0.28)
                    self._draw_window_symbol(drawing, segment[0], segment[1], offset_ratio=0.72)
                else:
                    self._draw_window_symbol(drawing, segment[0], segment[1], offset_ratio=0.5)

    def _draw_space_labels(self, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
        for space in _ordered_spaces(floor):
            area_mm2 = sum(rect.area for rect in space.rects)
            area_sqm = area_mm2 / 1_000_000
            area_jo = area_mm2 / TATAMI_MM2
            dims = _space_dimensions(space.rects)
            title = _display_space_name(space.id, space.type)
            lines = [title, f"{dims[0]}x{dims[1]}mm", f"{area_sqm:.1f}sqm / {area_jo:.1f}jo"]
            anchor = _clamped_room_label_anchor(space.rects, lines, self.scale)
            for idx, line in enumerate(lines):
                drawing.add(
                    drawing.text(
                        line,
                        insert=(self._x(anchor[0]), self._y(anchor[1] - 120 + idx * 90)),
                        fill="#1b1b1b",
                        font_size=10,
                        text_anchor="middle",
                    )
                )

    def _draw_room_dimension_guides(self, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
        for space in _ordered_spaces(floor):
            if space.type == "hall":
                continue
            if space.type in {"entry", "toilet", "wc"}:
                continue
            if len(space.rects) != 1:
                continue
            rect = space.rects[0]
            if rect.w < 1365 or rect.h < 1820:
                continue
            inset = 90
            x1 = rect.x + inset
            x2 = rect.x2 - inset
            y1 = rect.y + inset
            y2 = rect.y2 - inset

            if x2 - x1 >= 700:
                y = rect.y + inset
                drawing.add(
                    drawing.line(
                        start=(self._x(x1), self._y(y)),
                        end=(self._x(x2), self._y(y)),
                        stroke="#9a9a9a",
                        stroke_width=0.8,
                    )
                )
                drawing.add(
                    drawing.line(
                        start=(self._x(x1), self._y(y - 30)),
                        end=(self._x(x1), self._y(y + 30)),
                        stroke="#9a9a9a",
                        stroke_width=0.8,
                    )
                )
                drawing.add(
                    drawing.line(
                        start=(self._x(x2), self._y(y - 30)),
                        end=(self._x(x2), self._y(y + 30)),
                        stroke="#9a9a9a",
                        stroke_width=0.8,
                    )
                )
                drawing.add(
                    drawing.text(
                        f"{rect.w}mm",
                        insert=(self._x((x1 + x2) / 2), self._y(y - 24)),
                        fill="#7a7a7a",
                        font_size=8,
                        text_anchor="middle",
                    )
                )

            if y2 - y1 >= 700:
                x = rect.x + inset
                drawing.add(
                    drawing.line(
                        start=(self._x(x), self._y(y1)),
                        end=(self._x(x), self._y(y2)),
                        stroke="#9a9a9a",
                        stroke_width=0.8,
                    )
                )
                drawing.add(
                    drawing.line(
                        start=(self._x(x - 30), self._y(y1)),
                        end=(self._x(x + 30), self._y(y1)),
                        stroke="#9a9a9a",
                        stroke_width=0.8,
                    )
                )
                drawing.add(
                    drawing.line(
                        start=(self._x(x - 30), self._y(y2)),
                        end=(self._x(x + 30), self._y(y2)),
                        stroke="#9a9a9a",
                        stroke_width=0.8,
                    )
                )
                drawing.add(
                    drawing.text(
                        f"{rect.h}mm",
                        insert=(self._x(x + 46), self._y((y1 + y2) / 2)),
                        fill="#7a7a7a",
                        font_size=8,
                    )
                )

    def _draw_title_block(self, drawing: svgwrite.Drawing, floor_id: str, solution: PlanSolution) -> None:
        drawing.add(
            drawing.text(
                f"{floor_id} Plan  ({solution.envelope.width} x {solution.envelope.depth} mm)",
                insert=(self.margin_px, self.margin_px - 40),
                fill="#111111",
                font_size=14,
            )
        )
        drawing.add(
            drawing.text(
                f"Scale: 1px={1 / self.scale:.1f}mm",
                insert=(self.margin_px, self.margin_px - 22),
                fill="#444444",
                font_size=10,
            )
        )

    def _draw_legend(self, drawing: svgwrite.Drawing, floor: FloorSolution, site_rect: Rect) -> None:
        used_types = {space.type for space in floor.spaces.values()}
        legend_items = [space_type for space_type in LEGEND_ORDER if space_type in used_types]
        if not legend_items:
            return

        box_x = self._x(site_rect.x2) + 16
        box_y = self.margin_px - 70
        row_h = 18
        box_h = row_h * (len(legend_items) + 3)
        drawing.add(
            drawing.rect(
                insert=(box_x, box_y),
                size=(170, box_h),
                fill="#ffffff",
                stroke="#777777",
                stroke_width=1,
            )
        )
        drawing.add(drawing.text("Legend", insert=(box_x + 8, box_y + 14), fill="#111111", font_size=11))
        for idx, space_type in enumerate(legend_items):
            y = box_y + 24 + idx * row_h
            drawing.add(
                drawing.rect(
                    insert=(box_x + 8, y),
                    size=(12, 12),
                    fill=SPACE_COLORS.get(space_type, "#eeeeee"),
                    stroke="#333333",
                    stroke_width=1,
                )
            )
            drawing.add(
                drawing.text(
                    _display_space_name(space_type, space_type),
                    insert=(box_x + 26, y + 10),
                    fill="#222222",
                    font_size=10,
                )
            )
        symbol_y = box_y + 24 + len(legend_items) * row_h + 4
        drawing.add(
            drawing.line(
                start=(box_x + 8, symbol_y + 8),
                end=(box_x + 35, symbol_y + 8),
                stroke="#6aa4ff",
                stroke_width=4,
            )
        )
        drawing.add(drawing.text("Window", insert=(box_x + 42, symbol_y + 11), fill="#222222", font_size=10))
        drawing.add(
            drawing.line(
                start=(box_x + 8, symbol_y + 24),
                end=(box_x + 35, symbol_y + 24),
                stroke="#666666",
                stroke_width=2.4,
            )
        )
        drawing.add(
            drawing.path(
                d=f"M {box_x + 8},{symbol_y + 24} A 10,10 0 0 1 {box_x + 18},{symbol_y + 14}",
                fill="none",
                stroke="#666666",
                stroke_width=1.2,
            )
        )
        drawing.add(drawing.text("Door", insert=(box_x + 42, symbol_y + 27), fill="#222222", font_size=10))

    def _draw_north_arrow(self, drawing: svgwrite.Drawing, north: str) -> None:
        center_x = self.margin_px - 45
        center_y = self.margin_px + 18
        vectors = {
            "top": (0, -1),
            "bottom": (0, 1),
            "left": (-1, 0),
            "right": (1, 0),
        }
        dx, dy = vectors.get(north, (0, -1))
        end_x = center_x + dx * 30
        end_y = center_y + dy * 30
        drawing.add(
            drawing.line(
                start=(center_x, center_y),
                end=(end_x, end_y),
                stroke="#111111",
                stroke_width=2,
            )
        )
        head = [
            (end_x, end_y),
            (end_x - 6 * (dx + dy), end_y - 6 * (dy - dx)),
            (end_x - 6 * (dx - dy), end_y - 6 * (dy + dx)),
        ]
        drawing.add(drawing.polygon(points=head, fill="#111111"))
        drawing.add(drawing.text("N", insert=(center_x - 5, center_y - 36), fill="#111111", font_size=12))

    def _draw_dimensions(self, drawing: svgwrite.Drawing, site_rect: Rect, building_rect: Rect) -> None:
        self._draw_dimension_line(
            drawing,
            (site_rect.x, site_rect.y),
            (site_rect.x2, site_rect.y),
            offset_px=-26,
            label=f"{site_rect.w} mm",
        )
        self._draw_dimension_line(
            drawing,
            (site_rect.x, site_rect.y),
            (site_rect.x, site_rect.y2),
            offset_px=-26,
            label=f"{site_rect.h} mm",
            vertical=True,
        )
        if building_rect != site_rect:
            self._draw_dimension_line(
                drawing,
                (building_rect.x, building_rect.y2),
                (building_rect.x2, building_rect.y2),
                offset_px=24,
                label=f"Building: {building_rect.w} mm",
            )
            self._draw_dimension_line(
                drawing,
                (building_rect.x2, building_rect.y),
                (building_rect.x2, building_rect.y2),
                offset_px=24,
                label=f"{building_rect.h} mm",
                vertical=True,
            )

    def _draw_dimension_line(
        self,
        drawing: svgwrite.Drawing,
        p1: tuple[int, int],
        p2: tuple[int, int],
        offset_px: float,
        label: str,
        vertical: bool = False,
    ) -> None:
        if vertical:
            x = self._x(p1[0]) + offset_px
            y1 = self._y(min(p1[1], p2[1]))
            y2 = self._y(max(p1[1], p2[1]))
            drawing.add(drawing.line(start=(x, y1), end=(x, y2), stroke="#666666", stroke_width=1.2))
            drawing.add(drawing.line(start=(x - 4, y1), end=(x + 4, y1), stroke="#666666", stroke_width=1.2))
            drawing.add(drawing.line(start=(x - 4, y2), end=(x + 4, y2), stroke="#666666", stroke_width=1.2))
            drawing.add(drawing.text(label, insert=(x + 6, (y1 + y2) / 2), fill="#666666", font_size=9))
            return

        y = self._y(p1[1]) + offset_px
        x1 = self._x(min(p1[0], p2[0]))
        x2 = self._x(max(p1[0], p2[0]))
        drawing.add(drawing.line(start=(x1, y), end=(x2, y), stroke="#666666", stroke_width=1.2))
        drawing.add(drawing.line(start=(x1, y - 4), end=(x1, y + 4), stroke="#666666", stroke_width=1.2))
        drawing.add(drawing.line(start=(x2, y - 4), end=(x2, y + 4), stroke="#666666", stroke_width=1.2))
        drawing.add(drawing.text(label, insert=((x1 + x2) / 2 - 24, y - 4), fill="#666666", font_size=9))

    def _draw_stair_steps(
        self,
        drawing: svgwrite.Drawing,
        stair_type: str,
        tread_count: int,
        components: list[Rect],
        visible_indices: set[int] | None = None,
    ) -> None:
        if tread_count <= 0 or not components:
            return
        if visible_indices is None:
            visible_indices = set(range(len(components)))

        if stair_type == "straight":
            if 0 not in visible_indices:
                return
            flight = components[0]
            for index in range(1, tread_count + 1):
                y = flight.y + (flight.h * index) / (tread_count + 1)
                drawing.add(
                    drawing.line(
                        start=(self._x(flight.x + 0.12 * flight.w), self._y(y)),
                        end=(self._x(flight.x + 0.88 * flight.w), self._y(y)),
                        stroke="#2a2a2a",
                        stroke_width=1.4,
                    )
                )
            return

        if len(components) < 3:
            return
        flight1, _, flight2 = components[0], components[1], components[2]
        run1 = max(1, tread_count // 2)
        run2 = max(1, tread_count - run1)
        if 0 in visible_indices:
            for index in range(1, run1 + 1):
                x = flight1.x + (flight1.w * index) / (run1 + 1)
                drawing.add(
                    drawing.line(
                        start=(self._x(x), self._y(flight1.y)),
                        end=(self._x(x), self._y(flight1.y + flight1.h)),
                        stroke="#2a2a2a",
                        stroke_width=1.4,
                    )
                )
        if 2 in visible_indices:
            for index in range(1, run2 + 1):
                y = flight2.y + (flight2.h * index) / (run2 + 1)
                drawing.add(
                    drawing.line(
                        start=(self._x(flight2.x), self._y(y)),
                        end=(self._x(flight2.x + flight2.w), self._y(y)),
                        stroke="#2a2a2a",
                        stroke_width=1.4,
                    )
                )

    def _draw_void_hatch(self, drawing: svgwrite.Drawing, rect: Rect) -> None:
        spacing = 160
        y = rect.y + 80
        while y < rect.y2:
            drawing.add(
                drawing.line(
                    start=(self._x(rect.x + 45), self._y(y)),
                    end=(self._x(rect.x2 - 45), self._y(y)),
                    stroke="#b8b8b8",
                    stroke_width=0.9,
                )
            )
            y += spacing

    def _draw_void_guardrail(self, drawing: svgwrite.Drawing, rect: Rect) -> None:
        drawing.add(
            drawing.rect(
                insert=(self._x(rect.x), self._y(rect.y)),
                size=(rect.w * self.scale, rect.h * self.scale),
                fill="none",
                stroke="#7e7e7e",
                stroke_width=2.0,
                stroke_dasharray="3,2",
            )
        )
        drawing.add(
            drawing.text(
                "Guardrail",
                insert=(self._x(rect.x + rect.w / 2), self._y(rect.y + 120)),
                fill="#666666",
                font_size=8.5,
                text_anchor="middle",
            )
        )

    def _draw_door_symbol(
        self,
        drawing: svgwrite.Drawing,
        p1: tuple[int, int],
        p2: tuple[int, int],
        exterior: bool,
        boundary: Rect | None,
        reverse_swing: bool,
        draw_arc: bool = True,
    ) -> None:
        wall_cut_width = 7 if exterior else 6
        if p1[0] == p2[0]:
            x = p1[0]
            y_low = min(p1[1], p2[1])
            y_high = max(p1[1], p2[1])
            seg_len = y_high - y_low
            opening = min(980, max(760, int(seg_len * 0.45)))
            center = (y_low + y_high) / 2
            y1 = center - opening / 2
            y2 = center + opening / 2
            drawing.add(
                drawing.line(
                    start=(self._x(x), self._y(y1)),
                    end=(self._x(x), self._y(y2)),
                    stroke="#ffffff",
                    stroke_width=wall_cut_width,
                )
            )
            if not exterior and seg_len <= 1100:
                return
            swing_sign = -1 if reverse_swing else 1
            if exterior and boundary is not None and x == boundary.x2 and not reverse_swing:
                swing_sign = -1
            if draw_arc:
                hinge = (x, y1)
                leaf = (x + swing_sign * opening * 0.65, y1 + opening * 0.65)
                drawing.add(
                    drawing.line(
                        start=(self._x(hinge[0]), self._y(hinge[1])),
                        end=(self._x(leaf[0]), self._y(leaf[1])),
                        stroke="#595959",
                        stroke_width=1.2,
                    )
                )
                arc_radius_px = opening * 0.65 * self.scale
                drawing.add(
                    drawing.path(
                        d=(
                            f"M {self._x(x)},{self._y(y1 + opening * 0.65)} "
                            f"A {arc_radius_px},{arc_radius_px} 0 0 1 {self._x(leaf[0])},{self._y(leaf[1])}"
                        ),
                        fill="none",
                        stroke="#7a7a7a",
                        stroke_width=1.0,
                    )
                )
            return

        y = p1[1]
        x_low = min(p1[0], p2[0])
        x_high = max(p1[0], p2[0])
        seg_len = x_high - x_low
        opening = min(980, max(760, int(seg_len * 0.45)))
        center = (x_low + x_high) / 2
        x1 = center - opening / 2
        x2 = center + opening / 2
        drawing.add(
            drawing.line(
                start=(self._x(x1), self._y(y)),
                end=(self._x(x2), self._y(y)),
                stroke="#ffffff",
                stroke_width=wall_cut_width,
            )
        )
        if not exterior and seg_len <= 1100:
            return
        swing_sign = -1 if reverse_swing else 1
        if exterior and boundary is not None and y == boundary.y2 and not reverse_swing:
            swing_sign = -1
        if draw_arc:
            hinge = (x1, y)
            leaf = (x1 + opening * 0.65, y + swing_sign * opening * 0.65)
            drawing.add(
                drawing.line(
                    start=(self._x(hinge[0]), self._y(hinge[1])),
                    end=(self._x(leaf[0]), self._y(leaf[1])),
                    stroke="#595959",
                    stroke_width=1.2,
                )
            )
            arc_radius_px = opening * 0.65 * self.scale
            drawing.add(
                drawing.path(
                    d=(
                        f"M {self._x(x1 + opening * 0.65)},{self._y(y)} "
                        f"A {arc_radius_px},{arc_radius_px} 0 0 1 {self._x(leaf[0])},{self._y(leaf[1])}"
                    ),
                    fill="none",
                    stroke="#7a7a7a",
                    stroke_width=1.0,
                )
            )

    def _draw_window_symbol(
        self,
        drawing: svgwrite.Drawing,
        p1: tuple[int, int],
        p2: tuple[int, int],
        offset_ratio: float = 0.5,
    ) -> None:
        if p1[0] == p2[0]:
            x = p1[0]
            y_low = min(p1[1], p2[1])
            y_high = max(p1[1], p2[1])
            seg_len = y_high - y_low
            win_len = min(1600, max(910, int(seg_len * 0.34)))
            center = y_low + seg_len * offset_ratio
            y1 = max(y_low + 120, center - win_len / 2)
            y2 = min(y_high - 120, y1 + win_len)
            drawing.add(
                drawing.line(
                    start=(self._x(x), self._y(y1)),
                    end=(self._x(x), self._y(y2)),
                    stroke="#66a7ff",
                    stroke_width=4.5,
                )
            )
            return

        y = p1[1]
        x_low = min(p1[0], p2[0])
        x_high = max(p1[0], p2[0])
        seg_len = x_high - x_low
        win_len = min(1600, max(910, int(seg_len * 0.34)))
        center = x_low + seg_len * offset_ratio
        x1 = max(x_low + 120, center - win_len / 2)
        x2 = min(x_high - 120, x1 + win_len)
        drawing.add(
            drawing.line(
                start=(self._x(x1), self._y(y)),
                end=(self._x(x2), self._y(y)),
                stroke="#66a7ff",
                stroke_width=4.5,
            )
        )

    def _x(self, mm: float) -> float:
        return self.margin_px + (mm * self.scale)

    def _y(self, mm: float) -> float:
        return self.margin_px + (mm * self.scale)

    def _export_png(self, svg_path: Path, png_path: Path) -> None:
        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))


def _ordered_spaces(floor: FloorSolution) -> list[SpaceGeometry]:
    return [floor.spaces[key] for key in sorted(floor.spaces.keys())]


def _floor_rects(floor: FloorSolution) -> list[Rect]:
    rects: list[Rect] = []
    for space in floor.spaces.values():
        rects.extend(space.rects)
    if floor.stair is not None:
        rects.extend(floor.stair.components)
    return rects


def _bounding_rect(rects: list[Rect]) -> Rect:
    min_x = min(rect.x for rect in rects)
    min_y = min(rect.y for rect in rects)
    max_x = max(rect.x2 for rect in rects)
    max_y = max(rect.y2 for rect in rects)
    return Rect(min_x, min_y, max_x - min_x, max_y - min_y)


def _entity_rects(floor: FloorSolution, entity_id: str) -> list[Rect]:
    if entity_id in floor.spaces:
        return floor.spaces[entity_id].rects
    if floor.stair is not None and floor.stair.id == entity_id:
        return floor.stair.components
    return []


def _space_boundary_segments(rects: list[Rect]) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    cell = MINOR_GRID_MM
    occupied: set[tuple[int, int]] = set()
    for rect in rects:
        for x in range(rect.x, rect.x2, cell):
            for y in range(rect.y, rect.y2, cell):
                occupied.add((x, y))

    horizontal: dict[int, list[tuple[int, int]]] = {}
    vertical: dict[int, list[tuple[int, int]]] = {}

    for x, y in occupied:
        if (x, y - cell) not in occupied:
            horizontal.setdefault(y, []).append((x, x + cell))
        if (x, y + cell) not in occupied:
            horizontal.setdefault(y + cell, []).append((x, x + cell))
        if (x - cell, y) not in occupied:
            vertical.setdefault(x, []).append((y, y + cell))
        if (x + cell, y) not in occupied:
            vertical.setdefault(x + cell, []).append((y, y + cell))

    segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for y, spans in horizontal.items():
        for x1, x2 in _merge_spans(spans):
            segments.append(((x1, y), (x2, y)))
    for x, spans in vertical.items():
        for y1, y2 in _merge_spans(spans):
            segments.append(((x, y1), (x, y2)))
    return segments


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    spans = sorted(spans)
    merged: list[tuple[int, int]] = []
    cur_start, cur_end = spans[0]
    for start, end in spans[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
            continue
        merged.append((cur_start, cur_end))
        cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))
    return merged


def _shared_segment(
    rects_a: list[Rect], rects_b: list[Rect]
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    best_segment: tuple[tuple[int, int], tuple[int, int]] | None = None
    best_length = 0
    for rect_a in rects_a:
        for rect_b in rects_b:
            segment = rect_a.shared_edge_segment(rect_b)
            if segment is None:
                continue
            length = _segment_length(segment[0], segment[1])
            if length > best_length:
                best_length = length
                best_segment = segment
    return best_segment


def _room_label_anchor(rects: list[Rect]) -> tuple[float, float]:
    total_area = sum(rect.area for rect in rects)
    if total_area <= 0:
        return float(rects[0].x), float(rects[0].y)
    cx = sum((rect.x + rect.w / 2) * rect.area for rect in rects) / total_area
    cy = sum((rect.y + rect.h / 2) * rect.area for rect in rects) / total_area
    return cx, cy


def _space_dimensions(rects: list[Rect]) -> tuple[int, int]:
    if len(rects) == 1:
        return rects[0].w, rects[0].h
    bbox = _bounding_rect(rects)
    return bbox.w, bbox.h


def _display_space_name(space_id: str, space_type: str) -> str:
    pretty_type = space_type.replace("_", " ").title()
    if space_id.startswith("auto_fill_"):
        return "Storage"
    if space_id == space_type:
        return pretty_type
    if space_type == "storage" and space_id.startswith("pantry"):
        return _humanize_space_id(space_id)
    if space_type == "hall" and space_id.startswith("hall"):
        return _humanize_space_id(space_id)
    if space_type in {"bedroom", "master_bedroom"} and space_id.startswith("bed"):
        suffix = "".join(ch for ch in space_id if ch.isdigit())
        if space_type == "master_bedroom":
            return f"Master Bedroom {suffix}" if suffix else "Master Bedroom"
        return f"Bedroom {suffix}" if suffix else "Bedroom"
    return _humanize_space_id(space_id)


def _humanize_space_id(space_id: str) -> str:
    chars: list[str] = []
    for idx, char in enumerate(space_id.replace("_", " ")):
        if char.isdigit() and idx > 0 and chars and chars[-1] != " ":
            chars.append(" ")
        chars.append(char)
    return "".join(chars).strip().title()


def _clamped_room_label_anchor(
    rects: list[Rect],
    lines: list[str],
    scale: float,
    font_size_px: float = 10.0,
) -> tuple[float, float]:
    anchor_x, anchor_y = _room_label_anchor(rects)
    bbox = _bounding_rect(rects)
    longest = max((len(line) for line in lines), default=8)
    approx_char_px = font_size_px * 0.58
    half_label_px = (longest * approx_char_px) / 2
    half_label_mm = half_label_px / scale
    x_margin_mm = max(220.0, half_label_mm + 60.0)
    y_margin_mm = 260.0

    min_x = bbox.x + x_margin_mm
    max_x = bbox.x2 - x_margin_mm
    min_y = bbox.y + y_margin_mm
    max_y = bbox.y2 - y_margin_mm

    if min_x <= max_x:
        anchor_x = min(max(anchor_x, min_x), max_x)
    else:
        anchor_x = bbox.x + bbox.w / 2
    if min_y <= max_y:
        anchor_y = min(max(anchor_y, min_y), max_y)
    else:
        anchor_y = bbox.y + bbox.h / 2
    return anchor_x, anchor_y


def _sorted_floor_ids(ids: set[str] | list[str]) -> list[str]:
    def key(value: str) -> tuple[int, str]:
        digits = "".join(ch for ch in value if ch.isdigit())
        return (int(digits) if digits else 10_000, value)

    return sorted(ids, key=key)


def _exterior_segments(rect: Rect, boundary: Rect) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
    if rect.x == boundary.x:
        segments.append(((rect.x, rect.y), (rect.x, rect.y2)))
    if rect.x2 == boundary.x2:
        segments.append(((rect.x2, rect.y), (rect.x2, rect.y2)))
    if rect.y == boundary.y:
        segments.append(((rect.x, rect.y), (rect.x2, rect.y)))
    if rect.y2 == boundary.y2:
        segments.append(((rect.x, rect.y2), (rect.x2, rect.y2)))
    return segments


def _segment_length(p1: tuple[int, int], p2: tuple[int, int]) -> int:
    return abs(p2[0] - p1[0]) + abs(p2[1] - p1[1])


def _segment_key(
    segment: tuple[tuple[int, int], tuple[int, int]]
) -> tuple[tuple[int, int], tuple[int, int]]:
    p1, p2 = segment
    if p1 <= p2:
        return p1, p2
    return p2, p1


def _door_line_key(segment: tuple[tuple[int, int], tuple[int, int]]) -> tuple[str, int]:
    p1, p2 = segment
    if p1[0] == p2[0]:
        return ("v", p1[0])
    return ("h", p1[1])


def _portal_for_floor(floor: FloorSolution, floor_index: int, total_floors: int) -> StairPortal:
    if floor.stair is None:
        raise ValueError("cannot resolve stair portal without stair geometry")
    if floor.stair.portal_component is not None and floor.stair.portal_edge is not None:
        return StairPortal(component_index=floor.stair.portal_component, edge=floor.stair.portal_edge)
    return stair_portal_for_floor(
        stair_type=floor.stair.type,
        floor_index=floor_index,
        floor_count=total_floors,
        component_count=len(floor.stair.components),
    )


def _portal_hall_opening_segment(
    portal_component: Rect,
    hall_rects: list[Rect],
    edge: str,
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    best_segment: tuple[tuple[int, int], tuple[int, int]] | None = None
    best_length = 0
    for hall_rect in hall_rects:
        segment = _edge_shared_segment(portal_component, hall_rect, edge)
        if segment is None:
            continue
        length = _segment_length(segment[0], segment[1])
        if length > best_length:
            best_length = length
            best_segment = segment
    return best_segment


def _edge_shared_segment(
    portal_component: Rect,
    other: Rect,
    edge: str,
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    if edge == "left":
        if other.x2 != portal_component.x:
            return None
        y1 = max(portal_component.y, other.y)
        y2 = min(portal_component.y2, other.y2)
        return ((portal_component.x, y1), (portal_component.x, y2)) if y2 > y1 else None
    if edge == "right":
        if other.x != portal_component.x2:
            return None
        y1 = max(portal_component.y, other.y)
        y2 = min(portal_component.y2, other.y2)
        return ((portal_component.x2, y1), (portal_component.x2, y2)) if y2 > y1 else None
    if edge == "top":
        if other.y2 != portal_component.y:
            return None
        x1 = max(portal_component.x, other.x)
        x2 = min(portal_component.x2, other.x2)
        return ((x1, portal_component.y), (x2, portal_component.y)) if x2 > x1 else None
    if edge == "bottom":
        if other.y != portal_component.y2:
            return None
        x1 = max(portal_component.x, other.x)
        x2 = min(portal_component.x2, other.x2)
        return ((x1, portal_component.y2), (x2, portal_component.y2)) if x2 > x1 else None
    return None


def _stair_label_point(components: list[Rect], portal_component_index: int) -> tuple[float, float]:
    if 0 <= portal_component_index < len(components):
        portal = components[portal_component_index]
        return portal.x + portal.w / 2, portal.y + portal.h / 2
    if len(components) >= 2:
        landing = components[1]
        return landing.x + landing.w / 2, landing.y + landing.h / 2
    first = components[0]
    return first.x + first.w / 2, first.y + first.h / 2
