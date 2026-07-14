"""Compatibility facade for the separate hour/minute no-seconds pattern card.

New code should import from
`models.watch_kinematic.watch_kinematic.pattern_cards.separate_hour_minute_no_seconds`.
This module remains so older plans, tests, and generator entrypoints continue to work.
"""

from .pattern_cards.separate_hour_minute_no_seconds import (
    MIN_DISPLAY_AXIS_SEPARATION_MM,
    PATTERN_CARD_ID,
    build_separate_display_pattern_card,
    render_separate_display_pattern_markdown,
    solve_separate_display_layout,
    write_separate_display_pattern_card,
    write_separate_display_review,
)

__all__ = [
    "PATTERN_CARD_ID",
    "build_separate_display_pattern_card",
    "render_separate_display_pattern_markdown",
    "write_separate_display_pattern_card",
    "solve_separate_display_layout",
    "write_separate_display_review",
    "MIN_DISPLAY_AXIS_SEPARATION_MM",
]
