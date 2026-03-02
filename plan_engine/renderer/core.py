from __future__ import annotations

import os
from pathlib import Path

import cairosvg
import svgwrite

from plan_engine.models import FloorSolution, PlanSolution, Rect
from plan_engine.renderer.annotations import (
    draw_floor_area_summary,
    draw_legend,
    draw_north_arrow,
    draw_space_labels,
    draw_title_block,
)
from plan_engine.renderer.dimensions_exterior import draw_dimension_line, draw_dimensions
from plan_engine.renderer.dimensions_interior import draw_room_dimension_guides
from plan_engine.renderer.fixtures import draw_fixtures as _mod_draw_fixtures
from plan_engine.renderer.fixtures import draw_vent_marker as _mod_draw_vent_marker
from plan_engine.renderer.helpers import (
    SPACE_COLORS,
    _bounding_rect,
    _floor_rects,
    _ordered_spaces,
    _segment_key,
    _sorted_floor_ids,
    _space_boundary_segments,
    _subtract_colinear_segment,
)
from plan_engine.renderer.openings import draw_entry_door as _mod_draw_entry_door
from plan_engine.renderer.openings import draw_interior_doors as _mod_draw_interior_doors
from plan_engine.renderer.openings import draw_windows as _mod_draw_windows
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
        self._draw_structural_overlay(drawing, solution, floor_id)
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
        for closet in floor.embedded_closets:
            for seg in closet.blocked_exterior_segments:
                blocked_segments.add(_segment_key(seg))
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

    def _draw_site_and_footprint(self, drawing: svgwrite.Drawing, site_rect: Rect, building_rect: Rect) -> None:
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
        """Draw colored space rectangles with boundary segments.

        Embedded closet zones are rendered as built-in hatched areas and
        intentionally avoid room-like wall strokes. Parent room boundary
        segments shared with closet zones are trimmed so closet edges read as
        interior partitions.
        """
        closet_rects_by_parent: dict[str, list[Rect]] = {}
        for closet in floor.embedded_closets:
            closet_rects_by_parent.setdefault(closet.parent_id, []).append(closet.rect)

        for space in _ordered_spaces(floor):
            fill = SPACE_COLORS.get(space.type, "#eeeeee")
            is_outdoor = space.type in {"balcony", "veranda"}
            stroke_dash = "6,4" if space.id.startswith("auto_fill_") else None
            if is_outdoor:
                stroke_dash = "8,4"
            for rect in space.rects:
                attrs = {
                    "insert": (self._x(rect.x), self._y(rect.y)),
                    "size": (rect.w * self.scale, rect.h * self.scale),
                    "fill": fill,
                    "stroke": "none",
                }
                if is_outdoor:
                    attrs["fill_opacity"] = 0.82
                drawing.add(drawing.rect(**attrs))
                if is_outdoor:
                    drawing.add(
                        drawing.line(
                            start=(self._x(rect.x), self._y(rect.y)),
                            end=(self._x(rect.x2), self._y(rect.y2)),
                            stroke="#8da7b8",
                            stroke_width=0.9,
                            stroke_opacity=0.6,
                        )
                    )
                    drawing.add(
                        drawing.line(
                            start=(self._x(rect.x), self._y(rect.y2)),
                            end=(self._x(rect.x2), self._y(rect.y)),
                            stroke="#8da7b8",
                            stroke_width=0.9,
                            stroke_opacity=0.6,
                        )
                    )

            shared_with_closet: list[tuple[tuple[int, int], tuple[int, int]]] = []
            parent_closet_rects = closet_rects_by_parent.get(space.id, [])
            if parent_closet_rects:
                for base_rect in space.rects:
                    for closet_rect in parent_closet_rects:
                        segment = base_rect.shared_edge_segment(closet_rect)
                        if segment is not None:
                            shared_with_closet.append(segment)

            for p1, p2 in _space_boundary_segments(space.rects):
                segments = [(p1, p2)]
                for cut in shared_with_closet:
                    next_segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
                    for segment in segments:
                        next_segments.extend(_subtract_colinear_segment(segment, cut))
                    segments = next_segments
                for seg_start, seg_end in segments:
                    line_attrs: dict[str, object] = {
                        "start": (self._x(seg_start[0]), self._y(seg_start[1])),
                        "end": (self._x(seg_end[0]), self._y(seg_end[1])),
                        "stroke": "#2f2f2f",
                        "stroke_width": 2.2,
                    }
                    if stroke_dash:
                        line_attrs["stroke_dasharray"] = stroke_dash
                    drawing.add(drawing.line(**line_attrs))

        self._draw_embedded_closets(drawing, floor)

    def _draw_embedded_closets(self, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
        """Draw embedded closet overlays inside parent rooms."""
        for closet in floor.embedded_closets:
            rect = closet.rect
            drawing.add(
                drawing.rect(
                    insert=(self._x(rect.x), self._y(rect.y)),
                    size=(rect.w * self.scale, rect.h * self.scale),
                    fill=SPACE_COLORS.get("closet", "#f7f3ea"),
                    fill_opacity=0.35,
                    stroke="#9a9a9a",
                    stroke_width=0.9,
                    stroke_dasharray="4,3",
                )
            )
            self._draw_closet_hatch(drawing, rect)

    def _draw_closet_hatch(self, drawing: svgwrite.Drawing, rect: Rect) -> None:
        """Draw diagonal hatch lines for built-in closet zones."""
        spacing_mm = 160
        start = -rect.h
        end = rect.w + rect.h
        for offset in range(start, end + spacing_mm, spacing_mm):
            x1 = rect.x + max(offset, 0)
            y1 = rect.y + max(-offset, 0)
            length = min(rect.x2 - x1, rect.y2 - y1)
            if length <= 0:
                continue
            x2 = x1 + length
            y2 = y1 + length
            drawing.add(
                drawing.line(
                    start=(self._x(x1), self._y(y1)),
                    end=(self._x(x2), self._y(y2)),
                    stroke="#9c9c9c",
                    stroke_width=0.8,
                    stroke_opacity=0.7,
                )
            )

    def _draw_structural_overlay(
        self,
        drawing: svgwrite.Drawing,
        solution: PlanSolution,
        floor_id: str,
    ) -> None:
        """Draw structural wall-role overlay (only when PLAN_ENGINE_DRAW_STRUCTURAL_WALLS=1)."""
        if os.getenv("PLAN_ENGINE_DRAW_STRUCTURAL_WALLS", "0") != "1":
            return
        floor_walls = solution.walls.get(floor_id, [])
        if not floor_walls:
            return
        for wall in floor_walls:
            if wall.role == "partition":
                continue
            if wall.orientation == "vertical":
                start = (self._x(wall.line_coord_mm), self._y(wall.span_start_mm))
                end = (self._x(wall.line_coord_mm), self._y(wall.span_end_mm))
            else:
                start = (self._x(wall.span_start_mm), self._y(wall.line_coord_mm))
                end = (self._x(wall.span_end_mm), self._y(wall.line_coord_mm))
            stroke = "#a80000" if wall.role == "load_bearing" else "#cf6f00"
            stroke_width = 2.8 if wall.role == "load_bearing" else 2.2
            dash = None if wall.role == "load_bearing" else "6,4"
            line_attrs: dict[str, object] = {
                "start": start,
                "end": end,
                "stroke": stroke,
                "stroke_width": stroke_width,
                "opacity": 0.9,
            }
            if dash is not None:
                line_attrs["stroke_dasharray"] = dash
            drawing.add(drawing.line(**line_attrs))

    def _draw_fixtures(self, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
        """Delegate fixture rendering to the fixtures sub-module."""
        _mod_draw_fixtures(self, drawing, floor)

    def _draw_vent_marker(self, drawing: svgwrite.Drawing, rect: Rect) -> None:
        """Delegate vent marker rendering to the fixtures sub-module."""
        _mod_draw_vent_marker(self, drawing, rect)

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
        """Delegate interior door rendering to the openings sub-module."""
        _mod_draw_interior_doors(self, drawing, floor)

    def _draw_entry_door(self, drawing, floor, building_rect):
        """Delegate entry door rendering to the openings sub-module."""
        return _mod_draw_entry_door(self, drawing, floor, building_rect)

    def _draw_windows(self, drawing, floor, building_rect, blocked_segments):
        """Delegate window rendering to the openings sub-module."""
        return _mod_draw_windows(self, drawing, floor, building_rect, blocked_segments)

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

    def _draw_dimensions(self, drawing, site_rect, building_rect, floor, opening_segments):
        """Delegate exterior dimension rendering."""
        draw_dimensions(self, drawing, site_rect, building_rect, floor, opening_segments)

    def _draw_dimension_line(self, drawing, p1, p2, offset_px, label, vertical=False):
        """Delegate single dimension line rendering."""
        draw_dimension_line(self, drawing, p1, p2, offset_px=offset_px, label=label, vertical=vertical)

    def _draw_stair_steps(self, drawing, stair_type, tread_count, components, visible_indices=None):
        """Delegate stair step rendering."""
        draw_stair_steps(self, drawing, stair_type, tread_count, components, visible_indices=visible_indices)

    def _draw_void_hatch(self, drawing: svgwrite.Drawing, rect: Rect) -> None:
        """Delegate void hatch pattern rendering."""
        draw_void_hatch(self, drawing, rect)

    def _draw_void_guardrail(self, drawing: svgwrite.Drawing, rect: Rect) -> None:
        """Delegate void guardrail rendering."""
        draw_void_guardrail(self, drawing, rect)

    def _draw_door_symbol(
        self, drawing, p1, p2, exterior, boundary, reverse_swing, draw_arc=True, force_arc_small=False
    ):
        """Delegate door symbol rendering and return the opening segment."""
        return draw_door_symbol(
            drawing=drawing,
            p1=p1,
            p2=p2,
            exterior=exterior,
            boundary=boundary,
            reverse_swing=reverse_swing,
            draw_arc=draw_arc,
            force_arc_small=force_arc_small,
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
