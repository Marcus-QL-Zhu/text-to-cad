"""Compatibility facade for the independent hour/minute no-seconds pattern card."""

from .pattern_cards.independent_hour_minute_no_seconds import (
    MIN_DISPLAY_AXIS_SEPARATION_MM,
    PATTERN_CARD_ID,
    build_independent_display_pattern_card,
    render_independent_display_pattern_markdown,
    solve_independent_display_layout,
    write_independent_display_pattern_card,
    write_independent_display_review,
)

__all__ = [
    "PATTERN_CARD_ID",
    "build_independent_display_pattern_card",
    "render_independent_display_pattern_markdown",
    "write_independent_display_pattern_card",
    "solve_independent_display_layout",
    "write_independent_display_review",
    "MIN_DISPLAY_AXIS_SEPARATION_MM",
]
