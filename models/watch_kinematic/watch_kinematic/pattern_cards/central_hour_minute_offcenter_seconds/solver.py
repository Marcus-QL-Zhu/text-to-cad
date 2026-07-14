"""Pattern 1 solver package facade.

The current solver was built before pattern cards were split into packages.
This module is the dedicated Pattern 1 entrypoint and delegates to the
behavior-compatible solver while the CAD generator remains unchanged.
"""

from ...current_pattern_solver import (
    BRIDGE_PERIMETER_RESERVED_BAND_MM,
    BRIDGE_PERIMETER_SCREW_POLICY,
    BRIDGE_Z_STACK_FASTENER_POLICY,
    CURRENT_PATTERN_ID,
    solve_current_pattern,
)
from .card import PATTERN_CARD_ID


def solve_current_pattern_layout(*args, **kwargs) -> dict:
    report = solve_current_pattern(*args, **kwargs)
    if report.get("pattern_card_id") != PATTERN_CARD_ID:
        raise ValueError(
            f"unexpected pattern_card_id {report.get('pattern_card_id')!r}; "
            f"expected {PATTERN_CARD_ID!r}"
        )
    return report


if CURRENT_PATTERN_ID != PATTERN_CARD_ID:
    raise RuntimeError(f"Pattern ID mismatch: {CURRENT_PATTERN_ID!r} != {PATTERN_CARD_ID!r}")
