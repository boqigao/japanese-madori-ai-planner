from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationReport:
    """Mutable report collecting errors and warnings."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    structural: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return True if the report contains no errors."""
        return len(self.errors) == 0

    def to_text(self) -> str:
        """Format the report as human-readable plain text.

        Returns:
            A stable, sectioned text representation used by ``report.txt``.
            Sections appear only when they contain at least one item.
        """
        lines = [
            f"valid={self.is_valid}",
            f"errors={len(self.errors)}",
            f"warnings={len(self.warnings)}",
            f"structural={len(self.structural)}",
        ]
        if self.errors:
            lines.append("")
            lines.append("Errors:")
            for item in self.errors:
                lines.append(f"- {item}")
        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            for item in self.warnings:
                lines.append(f"- {item}")
        if self.structural:
            lines.append("")
            lines.append("Structural:")
            for item in self.structural:
                lines.append(f"- {item}")
        if self.diagnostics:
            lines.append("")
            lines.append("Diagnostics:")
            for item in self.diagnostics:
                lines.append(f"- {item}")
        if self.suggestions:
            lines.append("")
            lines.append("Suggestions:")
            for item in self.suggestions:
                lines.append(f"- {item}")
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class BedroomReachabilityViolation:
    """Structured preflight finding for bedroom pass-through circulation.

    Attributes:
        floor_id: Floor identifier containing the blocked bedroom.
        bedroom_id: Target bedroom-like space ID that is blocked.
        transit_bedroom_ids: Ordered tuple of bedroom-like IDs that appear as
            intermediate nodes on a discovered entry-to-target path.
        path: Ordered tuple of floor-local node IDs from entry to target used
            as representative path evidence.
    """

    floor_id: str
    bedroom_id: str
    transit_bedroom_ids: tuple[str, ...]
    path: tuple[str, ...]
