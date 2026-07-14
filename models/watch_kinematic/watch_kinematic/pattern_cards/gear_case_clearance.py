"""Shared hard constraint for gear envelopes inside the watch case."""

import math
from typing import Any


GEAR_CASE_INNER_WALL_SAFETY_MM = 0.80


def prove_gear_case_inner_wall_clearance(
    gears: list[dict[str, Any]],
    axes_by_id: dict[str, dict[str, Any]],
    case_inner_radius_mm: float,
) -> dict[str, Any]:
    """Prove every gear tip envelope clears the case inner wall by 0.80 mm."""

    records = []
    for gear in gears:
        axis = axes_by_id[gear["axis_id"]]
        axis_distance_mm = math.hypot(float(axis["x"]), float(axis["y"]))
        tip_radius_mm = float(gear["outer_radius"])
        envelope_radius_mm = axis_distance_mm + tip_radius_mm
        margin_mm = case_inner_radius_mm - envelope_radius_mm
        records.append(
            {
                "gear_id": gear["gear_id"],
                "axis_id": gear["axis_id"],
                "axis_distance_from_case_center_mm": round(axis_distance_mm, 6),
                "gear_tip_radius_mm": round(tip_radius_mm, 6),
                "tip_envelope_radius_mm": round(envelope_radius_mm, 6),
                "margin_to_case_inner_wall_mm": round(margin_mm, 6),
            }
        )

    violations = [
        record
        for record in records
        if record["margin_to_case_inner_wall_mm"] < GEAR_CASE_INNER_WALL_SAFETY_MM - 1e-6
    ]
    minimum_margin = min((record["margin_to_case_inner_wall_mm"] for record in records), default=math.inf)
    return {
        "case_inner_radius_mm": case_inner_radius_mm,
        "required_safety_margin_mm": GEAR_CASE_INNER_WALL_SAFETY_MM,
        "minimum_margin_mm": round(minimum_margin, 6),
        "records": records,
        "violations": violations,
        "status": "pass" if not violations else "fail",
    }
