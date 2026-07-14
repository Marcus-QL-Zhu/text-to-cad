"""Global coordinate constraint solver for the current watch axis pattern.

This module is intentionally parallel to the chain solver. It solves all
axis coordinates for the fixed current topology from center-distance equations
first, then reuses the existing candidate hard-geometry validator.
"""

from __future__ import annotations

import math
import random
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from .current_pattern_solver import (
    BRIDGE_PERIMETER_RESERVED_BAND_MM,
    DEFAULT_CASE_INNER_RADIUS_MM,
    DEFAULT_TOOTH_COUNTS,
    DISPLAY_TOOTH_COUNT_SETS,
    EXTERNAL_ESCAPEMENT_TARGET_ESCAPE_TO_BALANCE_MM,
    _build_candidate,
    _center_distance,
)


GLOBAL_AXIS_IDS = (
    "minute_work_axis",
    "barrel_axis",
    "third_axis",
    "fourth_axis",
    "escape_axis",
    "balance_axis",
)
CONSTRAINT_EQUATIONS = [
    "distance(display_center, minute_work) = display_motion_mesh_distance",
    "distance(center, barrel) = barrel_center_mesh_distance",
    "distance(center, third) = center_third_mesh_distance",
    "distance(third, fourth) = third_fourth_mesh_distance",
    "distance(fourth, escape) = fourth_escape_mesh_distance",
    "distance(escape, balance) = external_escapement_reference_distance",
]
ANGLE_VARIABLE_DOMAINS = {
    "minute_work_angle_deg": (90.0, 180.0),
    "barrel_angle_deg": (160.0, 260.0),
    "third_angle_deg": (-70.0, 90.0),
    "fourth_angle_deg": (-60.0, 90.0),
    "escape_angle_deg": (-60.0, 100.0),
    "balance_angle_deg": (60.0, 170.0),
}
MODULE_DOMAIN = [0.16, 0.17]
DISPLAY_MOTION_MODULE_DOMAIN = [0.12]
DISPLAY_TOOTH_COUNT_SET_DOMAIN = ["wide_clearance_10_100_50_60"]


def solve_global_axis_constraints(
    *,
    seed: int = 42,
    target_count: int = 5,
    attempt_count: int = 80,
    case_inner_radius_mm: float = DEFAULT_CASE_INNER_RADIUS_MM,
    bridge_perimeter_reserved_band_mm: float = BRIDGE_PERIMETER_RESERVED_BAND_MM,
) -> dict[str, Any]:
    """Solve multiple whole-layout axis candidates for the fixed watch topology."""

    rng = random.Random(seed)
    feasible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    pruned_region_count = 0
    regions = _region_boxes(seed, rng, attempt_count)
    for region in regions:
        region_candidates: list[dict[str, Any]] = []
        for sample_index, variables in enumerate(_sample_region(region)):
            candidate = _refine_region_sample(
                region,
                sample_index,
                variables,
                len(feasible) + len(rejected),
                case_inner_radius_mm,
                bridge_perimeter_reserved_band_mm,
            )
            if candidate["status"] == "pass" and candidate["global_constraint_status"] == "pass":
                region_candidates.append(candidate)
            else:
                rejected.append(candidate)
        if region_candidates:
            feasible.append(region_candidates[0])
        else:
            pruned_region_count += 1
        if len(feasible) >= max(target_count * 6, target_count):
            break
    candidates = _select_representatives(feasible, target_count)
    return {
        "kind": "watch_global_axis_constraint_solver_report",
        "status": "pass" if len(candidates) >= target_count else "fail",
        "selection_strategy": "region_classify_prune_refine_cluster",
        "seed": seed,
        "target_count": target_count,
        "attempt_count": len(regions),
        "variable_domains": _variable_domains(),
        "constraint_equations": CONSTRAINT_EQUATIONS,
        "region_classification": {
            "classified_region_count": min(len(regions), len(feasible) + pruned_region_count),
            "feasible_region_count": len(feasible),
            "pruned_region_count": pruned_region_count,
            "classification_policy": "sample_region_box_then_prune_if_no_sample_passes_hard_geometry",
            "local_refinement": "least_squares_center_distance_refinement",
            "representative_selection": "farthest_first_axis_coverage_clusters",
        },
        "representative_clusters": _representative_clusters(candidates),
        "candidates": candidates,
        "rejected_candidate_count": len(rejected),
        "failed_reasons": [] if len(candidates) >= target_count else sorted({
            reason
            for candidate in rejected
            for reason in candidate.get("failed_reasons", [])
        }),
    }


def _region_boxes(seed: int, rng: random.Random, count: int) -> list[dict[str, Any]]:
    angle_keys = list(ANGLE_VARIABLE_DOMAINS)
    strata = {}
    for key in angle_keys:
        indices = list(range(count))
        rng.shuffle(indices)
        strata[key] = indices
    regions = []
    for index in range(count):
        module = MODULE_DOMAIN[index % len(MODULE_DOMAIN)]
        center = {}
        half_width = {}
        for key in angle_keys:
            low, high = ANGLE_VARIABLE_DOMAINS[key]
            span = high - low
            jitter = rng.uniform(-0.35, 0.35)
            fraction = (strata[key][index] + 0.5 + jitter) / count
            center[key] = low + max(0.0, min(1.0, fraction)) * span
            half_width[key] = span / 18.0
        regions.append(
            {
                "region_id": f"region_box_{seed}_{index:04d}",
                "module": module,
                "display_motion_module": DISPLAY_MOTION_MODULE_DOMAIN[0],
                "display_tooth_count_set_id": DISPLAY_TOOTH_COUNT_SET_DOMAIN[0],
                "center": center,
                "half_width": half_width,
            }
        )
    return regions


def _sample_region(region: dict[str, Any]) -> list[dict[str, Any]]:
    samples = []
    offsets = [
        {},
        {"third_angle_deg": -0.65, "fourth_angle_deg": 0.65, "escape_angle_deg": -0.35},
        {"third_angle_deg": 0.65, "fourth_angle_deg": -0.65, "balance_angle_deg": 0.35},
    ]
    for offset in offsets:
        variables = {
            "module": region["module"],
            "display_motion_module": region["display_motion_module"],
            "display_tooth_count_set_id": region["display_tooth_count_set_id"],
            "structure_family_id": region["region_id"],
        }
        for key, center in region["center"].items():
            low, high = ANGLE_VARIABLE_DOMAINS[key]
            value = center + offset.get(key, 0.0) * region["half_width"][key]
            variables[key] = max(low, min(high, value))
        samples.append(variables)
    return samples


def _refine_region_sample(
    region: dict[str, Any],
    sample_index: int,
    variables: dict[str, Any],
    candidate_index: int,
    case_inner_radius_mm: float,
    bridge_perimeter_reserved_band_mm: float,
) -> dict[str, Any]:
    source_id = f"{region['region_id']}:sample_{sample_index}"
    guess = _guess_from_variables(source_id, variables)
    result = least_squares(
        _constraint_residuals,
        np.array(guess["vector"], dtype=float),
        args=(guess["module"], guess["display_motion_module"], guess["display_tooth_count_set_id"]),
        xtol=1e-10,
        ftol=1e-10,
        gtol=1e-10,
        max_nfev=400,
    )
    residual_norm = float(
        np.linalg.norm(
            _constraint_residuals(
                result.x,
                guess["module"],
                guess["display_motion_module"],
                guess["display_tooth_count_set_id"],
            )
        )
    )
    refined_variables = _variables_from_solution(
        result.x,
        guess["module"],
        guess["display_motion_module"],
        guess["display_tooth_count_set_id"],
        source_id,
    )
    candidate = _build_candidate(
        candidate_index,
        refined_variables,
        case_inner_radius_mm,
        bridge_perimeter_reserved_band_mm,
        False,
    )
    candidate["candidate_id"] = f"global_region_cand_{candidate_index:04d}"
    candidate["region_id"] = region["region_id"]
    candidate["global_constraint_status"] = "pass" if residual_norm <= 1e-6 else "fail"
    candidate["solver_residual_norm"] = round(residual_norm, 12)
    candidate["global_solver_source"] = f"region_box:{source_id}"
    candidate["region_box"] = {
        "center": {key: round(value, 6) for key, value in region["center"].items()},
        "half_width": {key: round(value, 6) for key, value in region["half_width"].items()},
    }
    return candidate


def _select_representatives(candidates: list[dict[str, Any]], target_count: int) -> list[dict[str, Any]]:
    unique_by_region: list[dict[str, Any]] = []
    seen_regions = set()
    for candidate in candidates:
        if candidate["region_id"] in seen_regions:
            continue
        seen_regions.add(candidate["region_id"])
        unique_by_region.append(candidate)
    if not unique_by_region:
        return []
    selected = [unique_by_region[0]]
    remaining = unique_by_region[1:]
    while remaining and len(selected) < target_count:
        next_candidate = max(
            remaining,
            key=lambda candidate: min(
                _axis_vector_distance(candidate, selected_candidate)
                for selected_candidate in selected
            ),
        )
        selected.append(next_candidate)
        remaining = [candidate for candidate in remaining if candidate is not next_candidate]
    for index, candidate in enumerate(selected, start=1):
        candidate["cluster_id"] = f"axis_coverage_cluster_{index:02d}"
    return selected


def _representative_clusters(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "cluster_id": candidate["cluster_id"],
            "status": candidate["status"],
            "representative_candidate_id": candidate["candidate_id"],
            "region_id": candidate["region_id"],
            "axis_signature": _axis_signature(candidate),
        }
        for candidate in candidates
    ]


def _guess_from_variables(source_id: str, variables: dict[str, Any]) -> dict[str, Any]:
    return _guess_from_angles(
        source_id,
        variables["module"],
        variables["display_motion_module"],
        variables["display_tooth_count_set_id"],
        variables,
    )


def _guess_from_angles(
    source_id: str,
    module: float,
    display_motion_module: float,
    display_tooth_count_set_id: str,
    angles: dict[str, float],
) -> dict[str, Any]:
    tooth_counts = _tooth_counts(display_tooth_count_set_id)
    center = (0.0, 0.0)
    minute = _polar(center, _center_distance(display_motion_module, tooth_counts["cannon_pinion_display_driver"], tooth_counts["minute_wheel"]), angles["minute_work_angle_deg"])
    barrel = _polar(center, _center_distance(module, tooth_counts["barrel_outer_teeth"], tooth_counts["center_pinion"]), angles["barrel_angle_deg"])
    third = _polar(center, _center_distance(module, tooth_counts["center_wheel"], tooth_counts["third_pinion"]), angles["third_angle_deg"])
    fourth = _polar(third, _center_distance(module, tooth_counts["third_wheel"], tooth_counts["fourth_pinion"]), angles["fourth_angle_deg"])
    escape = _polar(fourth, _center_distance(module, tooth_counts["fourth_wheel"], tooth_counts["escape_pinion"]), angles["escape_angle_deg"])
    balance = _polar(escape, EXTERNAL_ESCAPEMENT_TARGET_ESCAPE_TO_BALANCE_MM, angles["balance_angle_deg"])
    return {
        "source_id": source_id,
        "module": module,
        "display_motion_module": display_motion_module,
        "display_tooth_count_set_id": display_tooth_count_set_id,
        "vector": [
            *minute,
            *barrel,
            *third,
            *fourth,
            *escape,
            *balance,
        ],
    }


def _constraint_residuals(
    vector: np.ndarray,
    module: float,
    display_motion_module: float,
    display_tooth_count_set_id: str,
) -> np.ndarray:
    points = _points_from_vector(vector)
    tooth_counts = _tooth_counts(display_tooth_count_set_id)
    center = (0.0, 0.0)
    constraints = [
        (_distance(center, points["minute_work_axis"]), _center_distance(display_motion_module, tooth_counts["cannon_pinion_display_driver"], tooth_counts["minute_wheel"])),
        (_distance(center, points["barrel_axis"]), _center_distance(module, tooth_counts["barrel_outer_teeth"], tooth_counts["center_pinion"])),
        (_distance(center, points["third_axis"]), _center_distance(module, tooth_counts["center_wheel"], tooth_counts["third_pinion"])),
        (_distance(points["third_axis"], points["fourth_axis"]), _center_distance(module, tooth_counts["third_wheel"], tooth_counts["fourth_pinion"])),
        (_distance(points["fourth_axis"], points["escape_axis"]), _center_distance(module, tooth_counts["fourth_wheel"], tooth_counts["escape_pinion"])),
        (_distance(points["escape_axis"], points["balance_axis"]), EXTERNAL_ESCAPEMENT_TARGET_ESCAPE_TO_BALANCE_MM),
    ]
    return np.array([actual - expected for actual, expected in constraints], dtype=float)


def _variables_from_solution(
    vector: np.ndarray,
    module: float,
    display_motion_module: float,
    display_tooth_count_set_id: str,
    source_id: str,
) -> dict[str, Any]:
    points = _points_from_vector(vector)
    center = (0.0, 0.0)
    return {
        "module": module,
        "display_motion_module": display_motion_module,
        "display_tooth_count_set_id": display_tooth_count_set_id,
        "structure_family_id": f"global:{source_id}",
        "minute_work_angle_deg": _angle(center, points["minute_work_axis"]),
        "barrel_angle_deg": _angle(center, points["barrel_axis"]),
        "third_angle_deg": _angle(center, points["third_axis"]),
        "fourth_angle_deg": _angle(points["third_axis"], points["fourth_axis"]),
        "escape_angle_deg": _angle(points["fourth_axis"], points["escape_axis"]),
        "balance_angle_deg": _angle(points["escape_axis"], points["balance_axis"]),
    }


def _points_from_vector(vector: np.ndarray) -> dict[str, tuple[float, float]]:
    return {
        axis_id: (float(vector[index * 2]), float(vector[index * 2 + 1]))
        for index, axis_id in enumerate(GLOBAL_AXIS_IDS)
    }


def _tooth_counts(display_tooth_count_set_id: str) -> dict[str, int]:
    counts = dict(DEFAULT_TOOTH_COUNTS)
    counts.update(DISPLAY_TOOTH_COUNT_SETS[display_tooth_count_set_id])
    return counts


def _polar(origin: tuple[float, float], distance: float, angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return (origin[0] + distance * math.cos(angle), origin[1] + distance * math.sin(angle))


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _angle(origin: tuple[float, float], point: tuple[float, float]) -> float:
    return math.degrees(math.atan2(point[1] - origin[1], point[0] - origin[0]))


def _axis_signature(candidate: dict[str, Any]) -> tuple[tuple[str, float, float], ...]:
    axes = {axis["axis_id"]: axis for axis in candidate["axes"]}
    return tuple(
        (axis_id, round(axes[axis_id]["x"], 1), round(axes[axis_id]["y"], 1))
        for axis_id in ["barrel_axis", "third_axis", "fourth_axis", "escape_axis", "balance_axis"]
    )


def _axis_vector_distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_axes = {axis["axis_id"]: axis for axis in left["axes"]}
    right_axes = {axis["axis_id"]: axis for axis in right["axes"]}
    return math.sqrt(
        sum(
            (left_axes[axis_id]["x"] - right_axes[axis_id]["x"]) ** 2
            + (left_axes[axis_id]["y"] - right_axes[axis_id]["y"]) ** 2
            for axis_id in ["barrel_axis", "third_axis", "fourth_axis", "escape_axis", "balance_axis"]
        )
    )


def _variable_domains() -> dict[str, Any]:
    return {
        "module": MODULE_DOMAIN,
        "display_motion_module": DISPLAY_MOTION_MODULE_DOMAIN,
        "display_tooth_count_set_id": DISPLAY_TOOTH_COUNT_SET_DOMAIN,
        **ANGLE_VARIABLE_DOMAINS,
    }
