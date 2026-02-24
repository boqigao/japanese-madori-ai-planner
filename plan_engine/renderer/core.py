from __future__ import annotations

from pathlib import Path

import cairosvg
import svgwrite

from plan_engine.constants import MINOR_GRID_MM
from plan_engine.models import FloorSolution, PlanSolution, Rect
from plan_engine.renderer.annotations import (
    draw_floor_area_summary,
    draw_legend,
    draw_north_arrow,
    draw_space_labels,
    draw_title_block,
)
from plan_engine.renderer.dimensions import (
    draw_dimension_line,
    draw_dimensions,
    draw_room_dimension_guides,
)
from plan_engine.renderer.helpers import (
    SPACE_COLORS,
    WINDOW_SPACE_TYPES,
    _bounding_rect,
    _door_line_key,
    _entity_rects,
    _exterior_segments,
    _floor_rects,
    _ordered_spaces,
    _segment_length,
    _segment_key,
    _shared_segment,
    _sorted_floor_ids,
    _space_boundary_segments,
)
from plan_engine.renderer.stair import (
    draw_stair,
    draw_stair_connection_opening,
    draw_stair_steps,
    draw_void_guardrail,
    draw_void_hatch,
)
from plan_engine.renderer.symbols import draw_door_symbol, draw_window_symbol


class SvgRenderer:
    """SVG/PNG renderer for floor plan solutions. Converts PlanSolution into annotated architectural drawings."""

    def __init__(self, scale: float = 0.12, margin_px: float = 220.0) -> None:
        """Initialize renderer with scale factor and margin."""
        self.scale = scale
        self.margin_px = margin_px

    def render(self, solution: PlanSolution, outdir: str | Path) -> list[Path]:
        """Render all floors to SVG and PNG files. Returns list of output paths."""
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
        """Render a single floor plan to an SVG file."""
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
        self._draw_fixtures(drawing, floor)
        self._draw_stair(drawing, floor, floor_index, total_floors)
        self._draw_stair_connection_opening(drawing, floor, floor_index, total_floors)
        self._draw_interior_doors(drawing, floor)
        entry_wall_segment: tuple[tuple[int, int], tuple[int, int]] | None = None
        entry_opening_segment: tuple[tuple[int, int], tuple[int, int]] | None = None
        entry_result = self._draw_entry_door(drawing, floor, building_rect)
        if entry_result is not None:
            entry_wall_segment, entry_opening_segment = entry_result
        blocked_segments: set[tuple[tuple[int, int], tuple[int, int]]] = set()
        if entry_wall_segment is not None:
            blocked_segments.add(_segment_key(entry_wall_segment))
        window_opening_segments = self._draw_windows(drawing, floor, building_rect, blocked_segments)
        opening_segments = list(window_opening_segments)
        if entry_opening_segment is not None:
            opening_segments.append(entry_opening_segment)
        self._draw_room_dimension_guides(drawing, floor)
        self._draw_space_labels(drawing, floor)
        self._draw_title_block(drawing, floor_id, solution)
        self._draw_legend(drawing, floor, site_rect)
        self._draw_floor_area_summary(drawing, solution, floor_id, site_rect)
        self._draw_north_arrow(drawing, solution.north)
        self._draw_dimensions(drawing, site_rect, building_rect, floor, opening_segments)

        drawing.save()

    def _draw_grid(
        self,
        drawing: svgwrite.Drawing,
        site_rect: Rect,
        minor_grid_mm: int,
        major_grid_mm: int,
    ) -> None:
        """Draw minor and major grid lines on the site envelope."""
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
        """Draw the site envelope outline and building footprint."""
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
        """Draw colored space rectangles with boundary segments."""
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

    def _draw_fixtures(self, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
        """Draw lightweight furniture/fixture symbols for readability.

        Args:
            drawing: Floor drawing to mutate.
            floor: Floor solution containing room geometries.

        Returns:
            None.
        """
        for space in floor.spaces.values():
            if not space.rects:
                continue
            rect = max(space.rects, key=lambda value: value.area)
            if rect.w < 1365 or rect.h < 1365:
                continue

            if space.type in {"bedroom", "master_bedroom"}:
                bed_w = min(rect.w * 0.56, 1820)
                bed_h = min(rect.h * 0.34, 1365)
                bed_x = rect.x + (rect.w - bed_w) / 2
                bed_y = rect.y + rect.h * 0.18
                drawing.add(
                    drawing.rect(
                        insert=(self._x(bed_x), self._y(bed_y)),
                        size=(bed_w * self.scale, bed_h * self.scale),
                        fill="none",
                        stroke="#7f7f7f",
                        stroke_width=1.1,
                    )
                )
                drawing.add(
                    drawing.line(
                        start=(self._x(bed_x), self._y(bed_y + bed_h * 0.35)),
                        end=(self._x(bed_x + bed_w), self._y(bed_y + bed_h * 0.35)),
                        stroke="#7f7f7f",
                        stroke_width=0.9,
                    )
                )
                continue

            if space.type == "ldk":
                counter_w = min(rect.w * 0.42, 2730)
                counter_h = min(rect.h * 0.12, 820)
                counter_x = rect.x + rect.w * 0.48
                counter_y = rect.y + rect.h * 0.10
                drawing.add(
                    drawing.rect(
                        insert=(self._x(counter_x), self._y(counter_y)),
                        size=(counter_w * self.scale, counter_h * self.scale),
                        fill="none",
                        stroke="#8a6b4a",
                        stroke_width=1.0,
                    )
                )
                island_w = min(rect.w * 0.22, 1365)
                island_h = min(rect.h * 0.12, 820)
                island_x = rect.x + rect.w * 0.40
                island_y = rect.y + rect.h * 0.42
                drawing.add(
                    drawing.rect(
                        insert=(self._x(island_x), self._y(island_y)),
                        size=(island_w * self.scale, island_h * self.scale),
                        fill="none",
                        stroke="#8a6b4a",
                        stroke_width=1.0,
                    )
                )
                continue

            if space.type in {"toilet", "wc"}:
                cx = rect.x + rect.w * 0.5
                cy = rect.y + rect.h * 0.55
                drawing.add(
                    drawing.ellipse(
                        center=(self._x(cx), self._y(cy)),
                        r=(max(12, rect.w * self.scale * 0.13), max(8, rect.h * self.scale * 0.18)),
                        fill="none",
                        stroke="#6f6f6f",
                        stroke_width=1.0,
                    )
                )
                continue

            if space.type == "washroom":
                sink_w = min(rect.w * 0.42, 910)
                sink_h = min(rect.h * 0.22, 455)
                sink_x = rect.x + rect.w * 0.30
                sink_y = rect.y + rect.h * 0.18
                drawing.add(
                    drawing.rect(
                        insert=(self._x(sink_x), self._y(sink_y)),
                        size=(sink_w * self.scale, sink_h * self.scale),
                        fill="none",
                        stroke="#6f6f6f",
                        stroke_width=1.0,
                    )
                )
                continue

            if space.type == "bath":
                tub_w = min(rect.w * 0.62, 1365)
                tub_h = min(rect.h * 0.55, 910)
                tub_x = rect.x + rect.w * 0.2
                tub_y = rect.y + rect.h * 0.22
                drawing.add(
                    drawing.rect(
                        insert=(self._x(tub_x), self._y(tub_y)),
                        size=(tub_w * self.scale, tub_h * self.scale),
                        rx=6,
                        ry=6,
                        fill="none",
                        stroke="#6f6f6f",
                        stroke_width=1.0,
                    )
                )
                continue

            if space.type == "storage":
                x1 = rect.x + rect.w * 0.12
                x2 = rect.x2 - rect.w * 0.12
                y1 = rect.y + rect.h * 0.18
                y2 = rect.y2 - rect.h * 0.18
                drawing.add(
                    drawing.line(
                        start=(self._x(x1), self._y(y1)),
                        end=(self._x(x2), self._y(y1)),
                        stroke="#9a9a9a",
                        stroke_width=0.9,
                    )
                )
                drawing.add(
                    drawing.line(
                        start=(self._x(x1), self._y(y2)),
                        end=(self._x(x2), self._y(y2)),
                        stroke="#9a9a9a",
                        stroke_width=0.9,
                    )
                )

    def _draw_stair(
        self,
        drawing: svgwrite.Drawing,
        floor: FloorSolution,
        floor_index: int,
        total_floors: int,
    ) -> None:
        """Delegate stair rendering to the stair sub-module."""
        draw_stair(self, drawing, floor, floor_index, total_floors)

    def _draw_stair_connection_opening(
        self,
        drawing: svgwrite.Drawing,
        floor: FloorSolution,
        floor_index: int,
        total_floors: int,
    ) -> None:
        """Delegate stair-hall opening rendering."""
        draw_stair_connection_opening(self, drawing, floor, floor_index, total_floors)

    def _draw_interior_doors(self, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
        """Draw door symbols at shared edges between adjacent spaces."""
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
    ) -> tuple[
        tuple[tuple[int, int], tuple[int, int]],
        tuple[tuple[int, int], tuple[int, int]],
    ] | None:
        """Draw the primary entry door and return wall/opening segments.

        Args:
            drawing: Floor drawing to mutate.
            floor: Floor solution containing spaces/topology.
            building_rect: Building footprint boundary.

        Returns:
            ``(wall_segment, opening_segment)`` when an entry door is placed, else ``None``.
        """
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
        opening_segment = self._draw_door_symbol(
            drawing,
            best_segment[0],
            best_segment[1],
            exterior=True,
            boundary=building_rect,
            reverse_swing=False,
            draw_arc=True,
        )
        return best_segment, opening_segment

    def _draw_windows(
        self,
        drawing: svgwrite.Drawing,
        floor: FloorSolution,
        building_rect: Rect,
        blocked_segments: set[tuple[tuple[int, int], tuple[int, int]]],
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """Draw exterior window symbols and return their opening segments.

        Args:
            drawing: Floor drawing to mutate.
            floor: Floor solution containing spaces.
            building_rect: Building footprint boundary.
            blocked_segments: Exterior segments reserved by doors and excluded from windows.

        Returns:
            List of window opening segments in mm coordinates.
        """
        min_window_segment = 1365
        opening_segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
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
                    opening_segments.append(
                        self._draw_window_symbol(drawing, segment[0], segment[1], offset_ratio=0.28)
                    )
                    opening_segments.append(
                        self._draw_window_symbol(drawing, segment[0], segment[1], offset_ratio=0.72)
                    )
                else:
                    opening_segments.append(
                        self._draw_window_symbol(drawing, segment[0], segment[1], offset_ratio=0.5)
                    )
        return opening_segments

    def _draw_space_labels(self, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
        """Delegate space label rendering."""
        draw_space_labels(self, drawing, floor)

    def _draw_room_dimension_guides(self, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
        """Delegate room dimension guide rendering."""
        draw_room_dimension_guides(self, drawing, floor)

    def _draw_title_block(self, drawing: svgwrite.Drawing, floor_id: str, solution: PlanSolution) -> None:
        """Delegate title block rendering."""
        draw_title_block(self, drawing, floor_id, solution)

    def _draw_legend(self, drawing: svgwrite.Drawing, floor: FloorSolution, site_rect: Rect) -> None:
        """Delegate legend rendering."""
        draw_legend(self, drawing, floor, site_rect)

    def _draw_floor_area_summary(
        self,
        drawing: svgwrite.Drawing,
        solution: PlanSolution,
        floor_id: str,
        site_rect: Rect,
    ) -> None:
        """Delegate floor-area summary rendering."""
        draw_floor_area_summary(self, drawing, solution, floor_id, site_rect)

    def _draw_north_arrow(self, drawing: svgwrite.Drawing, north: str) -> None:
        """Delegate north arrow rendering."""
        draw_north_arrow(self, drawing, north)

    def _draw_dimensions(
        self,
        drawing: svgwrite.Drawing,
        site_rect: Rect,
        building_rect: Rect,
        floor: FloorSolution,
        opening_segments: list[tuple[tuple[int, int], tuple[int, int]]],
    ) -> None:
        """Delegate exterior dimension rendering with perimeter/opening chains.

        Args:
            drawing: Floor drawing to mutate.
            site_rect: Site envelope rectangle.
            building_rect: Building footprint rectangle.
            floor: Floor geometry used for room-derived perimeter segmentation.
            opening_segments: Exterior opening segments (door/window) for opening chains.

        Returns:
            None.
        """
        draw_dimensions(
            self,
            drawing,
            site_rect,
            building_rect,
            floor,
            opening_segments,
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
        """Delegate single dimension line rendering."""
        draw_dimension_line(self, drawing, p1, p2, offset_px=offset_px, label=label, vertical=vertical)

    def _draw_stair_steps(
        self,
        drawing: svgwrite.Drawing,
        stair_type: str,
        tread_count: int,
        components: list[Rect],
        visible_indices: set[int] | None = None,
    ) -> None:
        """Delegate stair step rendering."""
        draw_stair_steps(self, drawing, stair_type, tread_count, components, visible_indices=visible_indices)

    def _draw_void_hatch(self, drawing: svgwrite.Drawing, rect: Rect) -> None:
        """Delegate void hatch pattern rendering."""
        draw_void_hatch(self, drawing, rect)

    def _draw_void_guardrail(self, drawing: svgwrite.Drawing, rect: Rect) -> None:
        """Delegate void guardrail rendering."""
        draw_void_guardrail(self, drawing, rect)

    def _draw_door_symbol(
        self,
        drawing: svgwrite.Drawing,
        p1: tuple[int, int],
        p2: tuple[int, int],
        exterior: bool,
        boundary: Rect | None,
        reverse_swing: bool,
        draw_arc: bool = True,
    ) -> tuple[tuple[int, int], tuple[int, int]]:
        """Delegate door symbol rendering and return the opening segment."""
        return draw_door_symbol(
            drawing=drawing,
            p1=p1,
            p2=p2,
            exterior=exterior,
            boundary=boundary,
            reverse_swing=reverse_swing,
            draw_arc=draw_arc,
            x_fn=self._x,
            y_fn=self._y,
            scale=self.scale,
        )

    def _draw_window_symbol(
        self,
        drawing: svgwrite.Drawing,
        p1: tuple[int, int],
        p2: tuple[int, int],
        offset_ratio: float = 0.5,
    ) -> tuple[tuple[int, int], tuple[int, int]]:
        """Delegate window symbol rendering and return the opening segment."""
        return draw_window_symbol(
            drawing=drawing,
            p1=p1,
            p2=p2,
            offset_ratio=offset_ratio,
            x_fn=self._x,
            y_fn=self._y,
        )

    def _x(self, mm: float) -> float:
        """Convert mm coordinate to pixel x-position."""
        return self.margin_px + (mm * self.scale)

    def _y(self, mm: float) -> float:
        """Convert mm coordinate to pixel y-position."""
        return self.margin_px + (mm * self.scale)

    def _export_png(self, svg_path: Path, png_path: Path) -> None:
        """Convert an SVG file to PNG using CairoSVG."""
        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))
