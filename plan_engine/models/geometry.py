from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    """Immutable rectangle with geometry query methods."""

    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        """Right edge x-coordinate (x + w)."""
        return self.x + self.w

    @property
    def y2(self) -> int:
        """Bottom edge y-coordinate (y + h)."""
        return self.y + self.h

    @property
    def area(self) -> int:
        """Area of the rectangle in square units."""
        return self.w * self.h

    def to_dict(self) -> dict[str, int]:
        """Return the rectangle as a plain dictionary."""
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    def overlaps(self, other: Rect) -> bool:
        """Return True if this rectangle overlaps with *other*."""
        return not (self.x2 <= other.x or other.x2 <= self.x or self.y2 <= other.y or other.y2 <= self.y)

    def shares_edge_with(self, other: Rect) -> bool:
        """Return True if this rectangle shares a non-zero-length edge with *other*."""
        if self.x2 == other.x or other.x2 == self.x:
            y_overlap = min(self.y2, other.y2) - max(self.y, other.y)
            return y_overlap > 0
        if self.y2 == other.y or other.y2 == self.y:
            x_overlap = min(self.x2, other.x2) - max(self.x, other.x)
            return x_overlap > 0
        return False

    def shared_edge_segment(self, other: Rect) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """Return the shared edge as a pair of endpoints, or None if no edge is shared."""
        if self.x2 == other.x or other.x2 == self.x:
            y1 = max(self.y, other.y)
            y2 = min(self.y2, other.y2)
            if y2 > y1:
                edge_x = other.x if self.x2 == other.x else self.x
                return (edge_x, y1), (edge_x, y2)
        if self.y2 == other.y or other.y2 == self.y:
            x1 = max(self.x, other.x)
            x2 = min(self.x2, other.x2)
            if x2 > x1:
                edge_y = other.y if self.y2 == other.y else self.y
                return (x1, edge_y), (x2, edge_y)
        return None
