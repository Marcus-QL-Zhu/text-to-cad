"""Compatibility facade for the central hour/minute off-center seconds pattern.

New code should import from
`models.watch_kinematic.watch_kinematic.pattern_cards.central_hour_minute_offcenter_seconds`.
This module remains so older plans and notebooks can use a short stable name.
"""

from .pattern_cards.central_hour_minute_offcenter_seconds import (
    BRIDGE_PERIMETER_RESERVED_BAND_MM,
    BRIDGE_PERIMETER_SCREW_POLICY,
    BRIDGE_Z_STACK_FASTENER_POLICY,
    PATTERN_CARD_ID,
    build_current_pattern_card,
    render_current_pattern_markdown,
    solve_current_pattern_layout,
    write_current_pattern_card,
    write_current_pattern_review,
)

__all__ = [
    "PATTERN_CARD_ID",
    "build_current_pattern_card",
    "render_current_pattern_markdown",
    "write_current_pattern_card",
    "solve_current_pattern_layout",
    "write_current_pattern_review",
    "BRIDGE_PERIMETER_RESERVED_BAND_MM",
    "BRIDGE_PERIMETER_SCREW_POLICY",
    "BRIDGE_Z_STACK_FASTENER_POLICY",
]
