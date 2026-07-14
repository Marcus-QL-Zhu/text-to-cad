"""Axis-seed Voronoi probe for separate-display watch bridge planning."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

from .power_chain_mvp import CASE_RADIUS_MM, _build_separate_display_design
from .separate_display_bridge_probe import SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS
from .separate_display_pattern import solve_separate_display_layout


GROUP_COLORS = {
    "barrel_bridge": "#f8d7a1",
    "train_bridge": "#b9d7ff",
    "escapement_bridge": "#c8ead1",
}


def run_separate_display_axis_voronoi_probe(
    *,
    base_seed: int,
    layout_count: int = 5,
    output_dir: str | Path | None = None,
    grid_resolution: int = 161,
) -> dict[str, Any]:
    target = Path(output_dir) if output_dir is not None else None
    if target is not None:
        target.mkdir(parents=True, exist_ok=True)

    seeds = _select_feasible_seeds(base_seed, layout_count)
    layouts = []
    for seed in seeds:
        solver_report = solve_separate_display_layout(seed=seed)
        design = _build_separate_display_design(seed, solver_report)
        voronoi = _axis_voronoi(design, grid_resolution)
        layouts.append(
            {
                "seed": seed,
                "method": "axis_seed_voronoi_group_coloring",
                "axis_seed_count": len(voronoi["axis_ids"]),
                "axis_groups": list(SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS),
                "design": design,
                "voronoi": voronoi,
            }
        )

    report = {
        "kind": "watch_separate_display_axis_voronoi_probe",
        "status": "pass" if len(layouts) == layout_count else "fail",
        "base_seed": base_seed,
        "selected_seeds": seeds,
        "axis_group_policy": "each_axis_is_voronoi_seed_then_cells_are_colored_by_axis_system",
        "layouts": layouts,
        "artifacts": {},
    }
    if target is not None:
        _write_artifacts(report, target)
    return _public_report(report)


def run_separate_display_axis_voronoi_seam_probe(
    *,
    base_seed: int,
    layout_count: int = 5,
    output_dir: str | Path | None = None,
    grid_resolution: int = 161,
) -> dict[str, Any]:
    target = Path(output_dir) if output_dir is not None else None
    if target is not None:
        target.mkdir(parents=True, exist_ok=True)

    seeds = _select_feasible_seeds(base_seed, layout_count)
    layouts = []
    for seed in seeds:
        solver_report = solve_separate_display_layout(seed=seed)
        design = _build_separate_display_design(seed, solver_report)
        voronoi = _axis_voronoi(design, grid_resolution)
        seam_plan = _axis_voronoi_seam_plan(design, voronoi)
        layouts.append(
            {
                "seed": seed,
                "method": "axis_voronoi_boundary_inverse_synthesis",
                "design": design,
                "voronoi": voronoi,
                "seam_plan": seam_plan,
            }
        )

    hard_failures = [
        {"seed": layout["seed"], "failures": layout["seam_plan"]["hard_failures"]}
        for layout in layouts
        if layout["seam_plan"]["status"] != "pass"
    ]
    report = {
        "kind": "watch_separate_display_axis_voronoi_seam_probe",
        "status": "pass" if len(layouts) == layout_count and not hard_failures else "fail",
        "base_seed": base_seed,
        "selected_seeds": seeds,
        "seam_policy": "axis_voronoi_boundaries_reconstructed_as_polyline_filleted_and_native_smooth_seams",
        "layouts": layouts,
        "hard_failures": hard_failures,
        "artifacts": {},
    }
    if target is not None:
        _write_seam_artifacts(report, target)
    return _public_seam_report(report)


def _select_feasible_seeds(base_seed: int, count: int) -> list[int]:
    rng = random.Random(base_seed)
    seeds = []
    attempts = 0
    while len(seeds) < count and attempts < count * 200:
        attempts += 1
        seed = rng.randint(1, 9999)
        if seed in seeds:
            continue
        if solve_separate_display_layout(seed=seed)["status"] == "pass":
            seeds.append(seed)
    if len(seeds) < count:
        raise RuntimeError(f"Only found {len(seeds)} feasible seeds")
    return seeds


def _axis_voronoi_seam_plan(design: dict[str, Any], voronoi: dict[str, Any]) -> dict[str, Any]:
    seams = []
    hard_failures = []
    group_ids = voronoi["group_ids"]
    group_labels = np.array(voronoi["group_labels"])
    xs = np.array(voronoi["xs"], dtype=float)
    ys = np.array(voronoi["ys"], dtype=float)
    for left_index, left_id in enumerate(group_ids):
        for right_index in range(left_index + 1, len(group_ids)):
            right_id = group_ids[right_index]
            raw_points = _pair_boundary_points(group_labels, xs, ys, left_index, right_index)
            if len(raw_points) < 8:
                continue
            boundary_path = _trace_boundary_path(raw_points)
            polyline = _fit_boundary_polyline(boundary_path)
            polyline = _push_polyline_away_from_axes(design, polyline, minimum_clearance_mm=0.55)
            filleted = _fillet_polyline(polyline, radius_mm=0.75, samples_per_corner=7)
            native_smooth = _native_boundary_curve(boundary_path, guide_count=11, iterations=3)
            native_smooth = _push_polyline_away_from_axes(design, native_smooth, minimum_clearance_mm=0.55)
            checks = _seam_checks(design, polyline, filleted, native_smooth)
            fit_metrics = _boundary_fit_metrics(raw_points, filleted)
            native_fit_metrics = _boundary_fit_metrics(raw_points, native_smooth)
            checks.update(fit_metrics)
            checks.update(
                {
                    "native_smooth_mean_boundary_fit_error_mm": native_fit_metrics["mean_boundary_fit_error_mm"],
                    "native_smooth_max_boundary_fit_error_mm": native_fit_metrics["max_boundary_fit_error_mm"],
                }
            )
            if checks["status"] != "pass":
                hard_failures.extend(checks["failures"])
            seams.append(
                {
                    "seam_id": f"{left_id}__{right_id}",
                    "between": [left_id, right_id],
                    "fit_source": "voronoi_boundary_path_fit",
                    "raw_boundary": [_round_point(point) for point in _sample_points(raw_points, 90)],
                    "polyline": [_round_point(point) for point in polyline],
                    "filleted": [_round_point(point) for point in filleted],
                    "native_smooth": [_round_point(point) for point in native_smooth],
                    "checks": checks,
                }
            )
    if len(seams) < 2:
        hard_failures.append("less_than_two_group_boundaries_reconstructed")
    return {
        "status": "pass" if len(seams) >= 2 and not hard_failures else "fail",
        "variants": ["polyline", "filleted", "native_smooth"],
        "selected_variant": "native_smooth",
        "seams": seams,
        "hard_failures": sorted(set(hard_failures)),
    }


def _pair_boundary_points(
    labels: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    left_label: int,
    right_label: int,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    target = {left_label, right_label}
    for iy in range(labels.shape[0]):
        for ix in range(labels.shape[1]):
            current = int(labels[iy, ix])
            if current < 0:
                continue
            if ix + 1 < labels.shape[1] and {current, int(labels[iy, ix + 1])} == target:
                points.append(((float(xs[ix]) + float(xs[ix + 1])) / 2.0, float(ys[iy])))
            if iy + 1 < labels.shape[0] and {current, int(labels[iy + 1, ix])} == target:
                points.append((float(xs[ix]), (float(ys[iy]) + float(ys[iy + 1])) / 2.0))
    return points


def _trace_boundary_path(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    remaining = list(points)
    start_index = max(range(len(remaining)), key=lambda index: math.hypot(remaining[index][0], remaining[index][1]))
    path = [remaining.pop(start_index)]
    while remaining:
        last = path[-1]
        next_index = min(
            range(len(remaining)),
            key=lambda index: math.hypot(last[0] - remaining[index][0], last[1] - remaining[index][1]),
        )
        path.append(remaining.pop(next_index))
    first_radius = math.hypot(path[0][0], path[0][1])
    last_radius = math.hypot(path[-1][0], path[-1][1])
    if last_radius < first_radius:
        path.reverse()
    return path


def _fit_boundary_polyline(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) <= 3:
        return _ensure_minimum_polyline_points(_extend_polyline_to_case(points))
    epsilon = CASE_RADIUS_MM * 0.018
    simplified = points
    for _ in range(8):
        simplified = _rdp(points, epsilon)
        if 3 <= len(simplified) <= 7:
            break
        if len(simplified) > 7:
            epsilon *= 1.32
        else:
            epsilon *= 0.72
    if len(simplified) < 3:
        simplified = _ensure_minimum_polyline_points(simplified)
    if len(simplified) > 8:
        simplified = _resample_by_index(simplified, 7)
    return _ensure_minimum_polyline_points(_extend_polyline_to_case(simplified))


def _resample_by_index(points: list[tuple[float, float]], count: int) -> list[tuple[float, float]]:
    if len(points) <= count:
        return points
    return [
        points[int(round(index * (len(points) - 1) / (count - 1)))]
        for index in range(count)
    ]


def _push_polyline_away_from_axes(
    design: dict[str, Any],
    points: list[tuple[float, float]],
    *,
    minimum_clearance_mm: float,
) -> list[tuple[float, float]]:
    axes = [(float(axis["x"]), float(axis["y"])) for axis in design["axes"]]
    adjusted = []
    for point in points:
        nearest_distance, nearest_axis = min(
            (math.hypot(point[0] - axis[0], point[1] - axis[1]), axis)
            for axis in axes
        )
        if nearest_distance >= minimum_clearance_mm or nearest_distance <= 1e-9:
            adjusted.append(point)
            continue
        direction = ((point[0] - nearest_axis[0]) / nearest_distance, (point[1] - nearest_axis[1]) / nearest_distance)
        push = minimum_clearance_mm - nearest_distance
        adjusted.append((point[0] + direction[0] * push, point[1] + direction[1] * push))
    return adjusted


def _sample_points(points: list[tuple[float, float]], max_count: int) -> list[tuple[float, float]]:
    if len(points) <= max_count:
        return points
    return _resample_by_index(points, max_count)


def _sort_points_along_principal_axis(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    array = np.array(points, dtype=float)
    center = array.mean(axis=0)
    centered = array - center
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    direction = vh[0]
    order = np.argsort(centered @ direction)
    return [(float(array[index, 0]), float(array[index, 1])) for index in order]


def _simplify_polyline(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) <= 3:
        return points
    epsilon = CASE_RADIUS_MM * 0.045
    simplified = _rdp(points, epsilon)
    return simplified if len(simplified) >= 2 else [points[0], points[-1]]


def _rdp(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    start = points[0]
    end = points[-1]
    distances = [_point_line_distance(point, start, end) for point in points[1:-1]]
    max_distance = max(distances, default=0.0)
    if max_distance <= epsilon:
        return [start, end]
    split = distances.index(max_distance) + 1
    return _rdp(points[: split + 1], epsilon)[:-1] + _rdp(points[split:], epsilon)


def _point_line_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    vx = end[0] - start[0]
    vy = end[1] - start[1]
    length = math.hypot(vx, vy)
    if length <= 1e-9:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    return abs(vy * point[0] - vx * point[1] + end[0] * start[1] - end[1] * start[0]) / length


def _extend_polyline_to_case(
    points: list[tuple[float, float]],
    *,
    extend_start: bool | None = None,
    extend_end: bool | None = None,
) -> list[tuple[float, float]]:
    if len(points) < 2:
        return points
    result = list(points)
    if extend_start is None:
        extend_start = _is_near_case_edge(result[0])
    if extend_end is None:
        extend_end = _is_near_case_edge(result[-1])
    if extend_start:
        result[0] = _extend_endpoint_to_case(result[0], result[1])
    if extend_end:
        result[-1] = _extend_endpoint_to_case(result[-1], result[-2])
    return result


def _is_near_case_edge(point: tuple[float, float]) -> bool:
    return math.hypot(point[0], point[1]) >= CASE_RADIUS_MM - 1.0


def _extend_endpoint_to_case(point: tuple[float, float], neighbor: tuple[float, float]) -> tuple[float, float]:
    direction = (point[0] - neighbor[0], point[1] - neighbor[1])
    length = math.hypot(direction[0], direction[1])
    if length <= 1e-9:
        return point
    unit = (direction[0] / length, direction[1] / length)
    dot = point[0] * unit[0] + point[1] * unit[1]
    point_sq = point[0] ** 2 + point[1] ** 2
    discriminant = dot**2 + CASE_RADIUS_MM**2 - point_sq
    if discriminant < 0.0:
        return point
    t = -dot + math.sqrt(discriminant)
    if t < 0.0:
        t = -dot - math.sqrt(discriminant)
    if t < 0.0:
        return point
    return (point[0] + unit[0] * t, point[1] + unit[1] * t)


def _ensure_minimum_polyline_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) != 2:
        return points
    start, end = points
    midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    return [start, midpoint, end]


def _smooth_polyline(points: list[tuple[float, float]], iterations: int) -> list[tuple[float, float]]:
    smoothed = list(points)
    for _ in range(iterations):
        if len(smoothed) < 2:
            return smoothed
        next_points = [smoothed[0]]
        for start, end in zip(smoothed[:-1], smoothed[1:]):
            next_points.append((0.75 * start[0] + 0.25 * end[0], 0.75 * start[1] + 0.25 * end[1]))
            next_points.append((0.25 * start[0] + 0.75 * end[0], 0.25 * start[1] + 0.75 * end[1]))
        next_points.append(smoothed[-1])
        smoothed = next_points
    return smoothed


def _fillet_polyline(
    points: list[tuple[float, float]],
    *,
    radius_mm: float,
    samples_per_corner: int,
) -> list[tuple[float, float]]:
    if len(points) < 3:
        return list(points)
    result = [points[0]]
    for previous, corner, following in zip(points[:-2], points[1:-1], points[2:]):
        incoming = _unit_vector((corner[0] - previous[0], corner[1] - previous[1]))
        outgoing = _unit_vector((following[0] - corner[0], following[1] - corner[1]))
        previous_length = math.hypot(corner[0] - previous[0], corner[1] - previous[1])
        following_length = math.hypot(following[0] - corner[0], following[1] - corner[1])
        trim = min(radius_mm, previous_length * 0.38, following_length * 0.38)
        if trim <= 1e-6 or incoming == (0.0, 0.0) or outgoing == (0.0, 0.0):
            result.append(corner)
            continue
        entry = (corner[0] - incoming[0] * trim, corner[1] - incoming[1] * trim)
        exit = (corner[0] + outgoing[0] * trim, corner[1] + outgoing[1] * trim)
        if math.hypot(result[-1][0] - entry[0], result[-1][1] - entry[1]) > 1e-6:
            result.append(entry)
        for sample_index in range(1, samples_per_corner + 1):
            t = sample_index / (samples_per_corner + 1)
            one_minus = 1.0 - t
            result.append(
                (
                    one_minus * one_minus * entry[0] + 2.0 * one_minus * t * corner[0] + t * t * exit[0],
                    one_minus * one_minus * entry[1] + 2.0 * one_minus * t * corner[1] + t * t * exit[1],
                )
            )
        result.append(exit)
    result.append(points[-1])
    return result


def _native_boundary_curve(
    boundary_path: list[tuple[float, float]],
    *,
    guide_count: int,
    iterations: int,
) -> list[tuple[float, float]]:
    if len(boundary_path) <= 3:
        return _smooth_polyline(_extend_polyline_to_case(boundary_path), iterations=iterations)
    extend_start = _is_near_case_edge(boundary_path[0])
    extend_end = _is_near_case_edge(boundary_path[-1])
    guides = _resample_by_length(boundary_path, guide_count)
    guides = _ensure_minimum_polyline_points(
        _extend_polyline_to_case(guides, extend_start=extend_start, extend_end=extend_end)
    )
    smoothed = _smooth_polyline(guides, iterations=iterations)
    if len(smoothed) >= 2:
        if extend_start:
            smoothed[0] = _extend_endpoint_to_case(smoothed[0], smoothed[1])
        if extend_end:
            smoothed[-1] = _extend_endpoint_to_case(smoothed[-1], smoothed[-2])
    return smoothed


def _resample_by_length(points: list[tuple[float, float]], count: int) -> list[tuple[float, float]]:
    if len(points) <= count:
        return list(points)
    segment_lengths = [
        math.hypot(end[0] - start[0], end[1] - start[1])
        for start, end in zip(points[:-1], points[1:])
    ]
    total_length = sum(segment_lengths)
    if total_length <= 1e-9:
        return _resample_by_index(points, count)
    result = [points[0]]
    target_index = 1
    distance_so_far = 0.0
    current_target = total_length * target_index / (count - 1)
    for segment_index, segment_length in enumerate(segment_lengths):
        start = points[segment_index]
        end = points[segment_index + 1]
        while target_index < count - 1 and distance_so_far + segment_length >= current_target:
            t = (current_target - distance_so_far) / max(segment_length, 1e-9)
            result.append((start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t))
            target_index += 1
            current_target = total_length * target_index / (count - 1)
        distance_so_far += segment_length
    result.append(points[-1])
    return result


def _seam_checks(
    design: dict[str, Any],
    polyline: list[tuple[float, float]],
    filleted: list[tuple[float, float]],
    native_smooth: list[tuple[float, float]],
) -> dict[str, Any]:
    failures = []
    all_points = [*polyline, *filleted, *native_smooth]
    if any(math.hypot(point[0], point[1]) > CASE_RADIUS_MM + 0.08 for point in all_points):
        failures.append("seam_point_outside_case")
    axes = [(float(axis["x"]), float(axis["y"])) for axis in design["axes"]]
    min_axis_clearance = min(
        (math.hypot(point[0] - axis[0], point[1] - axis[1]) for point in all_points for axis in axes),
        default=999.0,
    )
    if min_axis_clearance < 0.18:
        failures.append("seam_intrudes_axis_core")
    max_filleted_turn_deg = _max_segment_turn_deg(filleted)
    max_native_smooth_turn_deg = _max_segment_turn_deg(native_smooth)
    return {
        "status": "pass" if not failures else "fail",
        "failures": sorted(set(failures)),
        "min_axis_clearance_mm": round(min_axis_clearance, 4),
        "polyline_point_count": len(polyline),
        "filleted_point_count": len(filleted),
        "native_smooth_point_count": len(native_smooth),
        "max_filleted_turn_deg": round(max_filleted_turn_deg, 3),
        "max_native_smooth_turn_deg": round(max_native_smooth_turn_deg, 3),
    }


def _max_segment_turn_deg(points: list[tuple[float, float]]) -> float:
    max_turn = 0.0
    for previous, current, following in zip(points[:-2], points[1:-1], points[2:]):
        incoming = _unit_vector((current[0] - previous[0], current[1] - previous[1]))
        outgoing = _unit_vector((following[0] - current[0], following[1] - current[1]))
        if incoming == (0.0, 0.0) or outgoing == (0.0, 0.0):
            continue
        dot = max(-1.0, min(1.0, incoming[0] * outgoing[0] + incoming[1] * outgoing[1]))
        max_turn = max(max_turn, math.degrees(math.acos(dot)))
    return max_turn


def _boundary_fit_metrics(
    boundary_points: list[tuple[float, float]],
    fitted_points: list[tuple[float, float]],
) -> dict[str, Any]:
    distances = [
        _distance_to_polyline(point, fitted_points)
        for point in boundary_points
    ]
    return {
        "raw_boundary_point_count": len(boundary_points),
        "mean_boundary_fit_error_mm": round(sum(distances) / max(1, len(distances)), 4),
        "max_boundary_fit_error_mm": round(max(distances, default=0.0), 4),
    }


def _distance_to_polyline(point: tuple[float, float], polyline: list[tuple[float, float]]) -> float:
    if len(polyline) < 2:
        return math.hypot(point[0] - polyline[0][0], point[1] - polyline[0][1]) if polyline else 999.0
    return min(
        _point_segment_distance(point, start, end)
        for start, end in zip(polyline[:-1], polyline[1:])
    )


def _point_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    vx = end[0] - start[0]
    vy = end[1] - start[1]
    length_sq = vx * vx + vy * vy
    if length_sq <= 1e-12:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    t = max(0.0, min(1.0, ((point[0] - start[0]) * vx + (point[1] - start[1]) * vy) / length_sq))
    projection = (start[0] + vx * t, start[1] + vy * t)
    return math.hypot(point[0] - projection[0], point[1] - projection[1])


def _safe_separating_polyline(
    design: dict[str, Any],
    left_group: str,
    right_group: str,
) -> list[tuple[float, float]]:
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    left_points = [
        (float(axis_by_id[axis_id]["x"]), float(axis_by_id[axis_id]["y"]))
        for axis_id in SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS[left_group]
    ]
    right_points = [
        (float(axis_by_id[axis_id]["x"]), float(axis_by_id[axis_id]["y"]))
        for axis_id in SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS[right_group]
    ]
    left_center = _mean_point(left_points)
    right_center = _mean_point(right_points)
    normal = _unit_vector((right_center[0] - left_center[0], right_center[1] - left_center[1]))
    if abs(normal[0]) + abs(normal[1]) <= 1e-9:
        normal = (1.0, 0.0)
    tangent = (-normal[1], normal[0])
    midpoint_offset = (_dot_point(left_center, normal) + _dot_point(right_center, normal)) / 2.0
    candidates: list[tuple[float, list[tuple[float, float]]]] = []
    for offset in np.linspace(-2.2, 2.2, 45):
        line_offset = midpoint_offset + float(offset)
        segment = _line_for_normal_offset(normal, tangent, line_offset)
        polyline = _ensure_minimum_polyline_points(segment)
        smooth = _smooth_polyline(polyline, iterations=2)
        clearance = _minimum_axis_clearance(design, [*polyline, *smooth])
        candidates.append((clearance, polyline))
    return max(candidates, key=lambda item: item[0])[1]


def _mean_point(points: list[tuple[float, float]]) -> tuple[float, float]:
    return (
        sum(point[0] for point in points) / max(1, len(points)),
        sum(point[1] for point in points) / max(1, len(points)),
    )


def _unit_vector(vector: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(vector[0], vector[1])
    if length <= 1e-9:
        return (0.0, 0.0)
    return (vector[0] / length, vector[1] / length)


def _dot_point(point: tuple[float, float], vector: tuple[float, float]) -> float:
    return point[0] * vector[0] + point[1] * vector[1]


def _line_for_normal_offset(
    normal: tuple[float, float],
    tangent: tuple[float, float],
    offset: float,
) -> list[tuple[float, float]]:
    base = (normal[0] * offset, normal[1] * offset)
    discriminant = CASE_RADIUS_MM**2 - offset**2
    if discriminant <= 0.0:
        span = 0.0
    else:
        span = math.sqrt(discriminant)
    return [
        (base[0] - tangent[0] * span, base[1] - tangent[1] * span),
        (base[0] + tangent[0] * span, base[1] + tangent[1] * span),
    ]


def _minimum_axis_clearance(design: dict[str, Any], points: list[tuple[float, float]]) -> float:
    axes = [(float(axis["x"]), float(axis["y"])) for axis in design["axes"]]
    return min(
        (math.hypot(point[0] - axis[0], point[1] - axis[1]) for point in points for axis in axes),
        default=999.0,
    )


def _round_point(point: tuple[float, float] | list[float]) -> list[float]:
    return [round(float(point[0]), 4), round(float(point[1]), 4)]


def _axis_voronoi(
    design: dict[str, Any],
    grid_resolution: int,
    axis_groups: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    groups = axis_groups or SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS
    axis_ids = [axis_id for axis_ids in groups.values() for axis_id in axis_ids]
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    axis_points = [(float(axis_by_id[axis_id]["x"]), float(axis_by_id[axis_id]["y"])) for axis_id in axis_ids]
    axis_group_by_id = {
        axis_id: bridge_id
        for bridge_id, axis_ids_for_group in groups.items()
        for axis_id in axis_ids_for_group
    }
    group_ids = list(groups)
    xs = np.linspace(-CASE_RADIUS_MM, CASE_RADIUS_MM, grid_resolution)
    ys = np.linspace(-CASE_RADIUS_MM, CASE_RADIUS_MM, grid_resolution)
    axis_labels = np.full((len(ys), len(xs)), -1, dtype=int)
    group_labels = np.full((len(ys), len(xs)), -1, dtype=int)
    for iy, y in enumerate(ys):
        for ix, x in enumerate(xs):
            if x * x + y * y > CASE_RADIUS_MM * CASE_RADIUS_MM:
                continue
            nearest_index = min(
                range(len(axis_points)),
                key=lambda index: (x - axis_points[index][0]) ** 2 + (y - axis_points[index][1]) ** 2,
            )
            axis_labels[iy, ix] = nearest_index
            group_labels[iy, ix] = group_ids.index(axis_group_by_id[axis_ids[nearest_index]])

    return {
        "axis_ids": axis_ids,
        "group_ids": group_ids,
        "axis_points": [[round(x, 4), round(y, 4)] for x, y in axis_points],
        "xs": [round(float(value), 4) for value in xs],
        "ys": [round(float(value), 4) for value in ys],
        "axis_labels": axis_labels,
        "group_labels": group_labels,
    }


def _write_artifacts(report: dict[str, Any], target: Path) -> None:
    contact_sheet = target / "separate_display_axis_voronoi_contact_sheet.png"
    html = target / "separate_display_axis_voronoi_review.html"
    report_json = target / "separate_display_axis_voronoi_probe.json"
    _render_contact_sheet(report["layouts"], contact_sheet)
    public = _public_report(report)
    public["artifacts"] = {
        "contact_sheet": str(contact_sheet.resolve()),
        "review_html": str(html.resolve()),
        "report_json": str(report_json.resolve()),
    }
    report["artifacts"] = public["artifacts"]
    report_json.write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    html.write_text(_render_html(public), encoding="utf-8")


def _write_seam_artifacts(report: dict[str, Any], target: Path) -> None:
    contact_sheet = target / "separate_display_axis_voronoi_seams_contact_sheet.png"
    filleted_contact_sheet = target / "separate_display_axis_voronoi_seams_filleted_contact_sheet.png"
    native_smooth_contact_sheet = target / "separate_display_axis_voronoi_seams_native_smooth_contact_sheet.png"
    html = target / "separate_display_axis_voronoi_seams_review.html"
    report_json = target / "separate_display_axis_voronoi_seam_probe.json"
    _render_seam_contact_sheet(report["layouts"], contact_sheet)
    _render_seam_variant_contact_sheet(report["layouts"], filleted_contact_sheet, variant="filleted")
    _render_seam_variant_contact_sheet(report["layouts"], native_smooth_contact_sheet, variant="native_smooth")
    public = _public_seam_report(report)
    public["artifacts"] = {
        "contact_sheet": str(contact_sheet.resolve()),
        "filleted_contact_sheet": str(filleted_contact_sheet.resolve()),
        "native_smooth_contact_sheet": str(native_smooth_contact_sheet.resolve()),
        "review_html": str(html.resolve()),
        "report_json": str(report_json.resolve()),
    }
    report["artifacts"] = public["artifacts"]
    report_json.write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    html.write_text(_render_seam_html(public), encoding="utf-8")


def _render_contact_sheet(layouts: list[dict[str, Any]], output_path: Path) -> None:
    fig, axes = plt.subplots(1, len(layouts), figsize=(4.2 * len(layouts), 4.4), dpi=180)
    if len(layouts) == 1:
        axes = [axes]
    for ax, layout in zip(axes, layouts):
        _render_axis_voronoi(ax, layout)
    fig.tight_layout()
    fig.savefig(output_path, facecolor="white")
    plt.close(fig)


def _render_seam_contact_sheet(layouts: list[dict[str, Any]], output_path: Path) -> None:
    fig, axes = plt.subplots(1, len(layouts), figsize=(4.4 * len(layouts), 4.6), dpi=180)
    if len(layouts) == 1:
        axes = [axes]
    for ax, layout in zip(axes, layouts):
        _render_axis_voronoi(ax, layout)
        _render_seam_overlay(ax, layout["seam_plan"])
        ax.set_title(f"seed {layout['seed']} Voronoi seams\n{layout['seam_plan']['status']}", fontsize=10)
    fig.tight_layout()
    fig.savefig(output_path, facecolor="white")
    plt.close(fig)


def _render_seam_variant_contact_sheet(layouts: list[dict[str, Any]], output_path: Path, *, variant: str) -> None:
    fig, axes = plt.subplots(1, len(layouts), figsize=(4.4 * len(layouts), 4.6), dpi=180)
    if len(layouts) == 1:
        axes = [axes]
    for ax, layout in zip(axes, layouts):
        _render_axis_voronoi(ax, layout, show_boundaries=False)
        _render_single_seam_variant_overlay(ax, layout["seam_plan"], variant=variant)
        label = "filleted seams" if variant == "filleted" else "native smooth seams"
        ax.set_title(f"seed {layout['seed']} {label}\n{layout['seam_plan']['status']}", fontsize=10)
    fig.tight_layout()
    fig.savefig(output_path, facecolor="white")
    plt.close(fig)


def _render_axis_voronoi(ax: Any, layout: dict[str, Any], *, show_boundaries: bool = True) -> None:
    voronoi = layout["voronoi"]
    radius = CASE_RADIUS_MM
    group_labels = np.ma.masked_where(np.array(voronoi["group_labels"]) < 0, np.array(voronoi["group_labels"]))
    ax.set_aspect("equal")
    ax.set_xlim(-radius - 1.5, radius + 1.5)
    ax.set_ylim(-radius - 1.5, radius + 1.5)
    ax.axis("off")
    ax.set_title(f"seed {layout['seed']} axis Voronoi", fontsize=10)
    ax.imshow(
        group_labels,
        origin="lower",
        extent=[-radius, radius, -radius, radius],
        cmap=ListedColormap([GROUP_COLORS[group_id] for group_id in voronoi["group_ids"]]),
        alpha=0.62,
        interpolation="nearest",
        zorder=0,
    )
    ax.add_patch(plt.Circle((0, 0), radius, fill=False, ec="#9aa5b1", lw=1.1, zorder=5))

    if show_boundaries:
        axis_labels = np.array(voronoi["axis_labels"])
        xs = np.array(voronoi["xs"], dtype=float)
        ys = np.array(voronoi["ys"], dtype=float)
        axis_boundary = _label_boundary_mask(axis_labels)
        group_boundary = _label_boundary_mask(np.array(voronoi["group_labels"]))
        ax.contour(xs, ys, axis_boundary.astype(float), levels=[0.5], colors=["white"], linewidths=0.7, zorder=2)
        ax.contour(xs, ys, group_boundary.astype(float), levels=[0.5], colors=["#344054"], linewidths=1.15, zorder=3)

    _draw_axis_links(ax, layout["design"])
    for axis_id, point in zip(voronoi["axis_ids"], voronoi["axis_points"]):
        group_id = _group_for_axis(axis_id)
        x, y = point
        ax.add_patch(plt.Circle((x, y), 0.24, color="#111827", zorder=6))
        ax.add_patch(plt.Circle((x, y), 0.68, fill=False, ec=GROUP_COLORS[group_id], lw=1.5, zorder=6))
        ax.text(x + 0.28, y + 0.2, axis_id.replace("_axis", ""), fontsize=5.2, color="#111827", zorder=7)


def _render_seam_overlay(ax: Any, seam_plan: dict[str, Any]) -> None:
    for seam in seam_plan["seams"]:
        raw = np.array(seam.get("raw_boundary", []), dtype=float)
        polyline = np.array(seam["polyline"], dtype=float)
        filleted = np.array(seam["filleted"], dtype=float)
        native_smooth = np.array(seam["native_smooth"], dtype=float)
        if len(raw) >= 2:
            ax.scatter(raw[:, 0], raw[:, 1], s=1.4, color="#667085", alpha=0.42, zorder=7)
        if len(polyline) >= 2:
            ax.plot(polyline[:, 0], polyline[:, 1], color="#d92d20", lw=1.15, alpha=0.72, zorder=8)
            ax.scatter(polyline[:, 0], polyline[:, 1], s=4, color="#d92d20", alpha=0.72, zorder=9)
        if len(filleted) >= 2:
            ax.plot(filleted[:, 0], filleted[:, 1], color="#155eef", lw=1.35, alpha=0.86, zorder=10)
        if len(native_smooth) >= 2:
            ax.plot(native_smooth[:, 0], native_smooth[:, 1], color="#079455", lw=1.25, alpha=0.92, zorder=11)


def _render_single_seam_variant_overlay(ax: Any, seam_plan: dict[str, Any], *, variant: str) -> None:
    color = "#155eef" if variant == "filleted" else "#079455"
    line_width = 2.0 if variant == "filleted" else 1.85
    for seam in seam_plan["seams"]:
        points = np.array(seam[variant], dtype=float)
        if len(points) >= 2:
            ax.plot(points[:, 0], points[:, 1], color=color, lw=line_width, alpha=0.96, zorder=10)


def _draw_axis_links(ax: Any, design: dict[str, Any]) -> None:
    axes = {axis["axis_id"]: axis for axis in design["axes"]}
    links = [
        ("barrel_axis", "train_stage_1_axis"),
        ("train_stage_1_axis", "train_stage_2_axis"),
        ("train_stage_2_axis", "train_stage_3_axis"),
        ("train_stage_3_axis", "escape_axis"),
        ("train_stage_3_axis", "display_input_relay_axis"),
        ("display_input_relay_axis", "minute_display_axis"),
        ("minute_display_axis", "display_relay_axis"),
        ("display_relay_axis", "hour_display_axis"),
        ("escape_axis", "pallet_axis"),
        ("pallet_axis", "balance_axis"),
    ]
    for left_id, right_id in links:
        left = axes.get(left_id)
        right = axes.get(right_id)
        if not left or not right:
            continue
        ax.plot([left["x"], right["x"]], [left["y"], right["y"]], color="#475467", lw=0.8, alpha=0.5, zorder=4)


def _label_boundary_mask(labels: np.ndarray) -> np.ndarray:
    boundary = np.zeros_like(labels, dtype=bool)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
        shifted = np.roll(np.roll(labels, dy, axis=0), dx, axis=1)
        boundary |= (labels >= 0) & (shifted >= 0) & (labels != shifted)
    return boundary


def _group_for_axis(axis_id: str) -> str:
    for group_id, axis_ids in SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS.items():
        if axis_id in axis_ids:
            return group_id
    raise KeyError(axis_id)


def _render_html(report: dict[str, Any]) -> str:
    artifacts = {key: Path(value).name for key, value in report["artifacts"].items()}
    groups = "".join(
        f"<li><span style=\"display:inline-block;width:12px;height:12px;background:{GROUP_COLORS[group_id]};border:1px solid #98a2b3;margin-right:6px\"></span>"
        f"<code>{group_id}</code>: {', '.join(axis_ids)}</li>"
        for group_id, axis_ids in SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS.items()
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Separate Display Axis Voronoi Probe</title>
  <style>
    body {{ margin: 0; padding: 28px; font-family: Arial, sans-serif; color: #1f2937; background: #f6f8fb; }}
    h1 {{ margin: 0 0 8px; font-size: 25px; }}
    .meta {{ color: #667085; margin-bottom: 18px; }}
    .legend {{ background: white; border: 1px solid #d0d7e2; border-radius: 8px; padding: 12px 16px; margin: 0 0 18px; }}
    .legend li {{ margin: 5px 0; font-size: 13px; }}
    img {{ display: block; max-width: 100%; border: 1px solid #d0d7e2; border-radius: 8px; background: white; }}
  </style>
</head>
<body>
  <h1>鍒嗙鏃堕拡/鍒嗛拡 Pattern锛氳酱绾?Voronoi 鍒嗗尯鎺㈤拡</h1>
  <div class="meta">base seed: {report['base_seed']} | selected seeds: {', '.join(str(seed) for seed in report['selected_seeds'])}</div>
  <div class="meta">姣忔牴杞翠綔涓?Voronoi seed锛岀粏鐧界嚎鏄酱绾?cell 杈圭晫锛屾繁鐏扮嚎鏄悓杞寸郴鍚堝苟鍚庣殑杈圭晫銆?/div>
  <ul class="legend">{groups}</ul>
  <img src="{artifacts['contact_sheet']}" alt="axis Voronoi contact sheet" />
</body>
</html>
"""


def _public_report(report: dict[str, Any]) -> dict[str, Any]:
    public = {key: value for key, value in report.items() if key != "layouts"}
    public["layouts"] = [
        {
            "seed": layout["seed"],
            "method": layout["method"],
            "axis_seed_count": layout["axis_seed_count"],
            "axis_groups": layout["axis_groups"],
        }
        for layout in report["layouts"]
    ]
    return public


def _public_seam_report(report: dict[str, Any]) -> dict[str, Any]:
    public = {key: value for key, value in report.items() if key != "layouts"}
    public["layouts"] = []
    for layout in report["layouts"]:
        seam_plan = layout["seam_plan"]
        polyline_counts = [
            seam["checks"]["polyline_point_count"]
            for seam in seam_plan["seams"]
        ]
        filleted_counts = [
            seam["checks"]["filleted_point_count"]
            for seam in seam_plan["seams"]
        ]
        native_smooth_counts = [
            seam["checks"]["native_smooth_point_count"]
            for seam in seam_plan["seams"]
        ]
        public["layouts"].append(
            {
                "seed": layout["seed"],
                "method": layout["method"],
                "seam_status": seam_plan["status"],
                "variants": seam_plan["variants"],
                "selected_variant": seam_plan["selected_variant"],
                "seam_count": len(seam_plan["seams"]),
                "minimum_polyline_point_count": min(polyline_counts, default=0),
                "minimum_filleted_point_count": min(filleted_counts, default=0),
                "minimum_native_smooth_point_count": min(native_smooth_counts, default=0),
                "hard_failures": seam_plan["hard_failures"],
                "seams": [
                    {
                        "seam_id": seam["seam_id"],
                        "between": seam["between"],
                        "fit_source": seam["fit_source"],
                        "checks": seam["checks"],
                    }
                    for seam in seam_plan["seams"]
                ],
            }
        )
    return public


def _render_seam_html(report: dict[str, Any]) -> str:
    artifacts = {key: Path(value).name for key, value in report["artifacts"].items()}
    rows = "\n".join(
        f"<tr><td>{layout['seed']}</td><td>{layout['seam_status']}</td>"
        f"<td>{layout['seam_count']}</td><td>{', '.join(layout['variants'])}</td>"
        f"<td>{', '.join(layout['hard_failures']) or '-'}</td></tr>"
        for layout in report["layouts"]
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Separate Display Axis Voronoi Seam Synthesis</title>
  <style>
    body {{ margin: 0; padding: 28px; font-family: Arial, sans-serif; color: #1f2937; background: #f6f8fb; }}
    h1 {{ margin: 0 0 8px; font-size: 25px; }}
    .meta {{ color: #667085; margin-bottom: 18px; }}
    img {{ display: block; max-width: 100%; border: 1px solid #d0d7e2; border-radius: 8px; background: white; margin-bottom: 18px; }}
    table {{ border-collapse: collapse; width: 100%; background: white; border: 1px solid #d0d7e2; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 8px 10px; text-align: left; font-size: 13px; }}
    th {{ background: #eef2f7; }}
    .legend span {{ display: inline-block; margin-right: 18px; }}
  </style>
</head>
<body>
  <h1>鍒嗙鏃堕拡/鍒嗛拡 Pattern锛氳酱绾?Voronoi 杈圭晫鏇茬嚎鎷熷悎</h1>
  <div class="meta">base seed: {report['base_seed']} | selected seeds: {', '.join(str(seed) for seed in report['selected_seeds'])}</div>
  <div class="meta legend"><span style="color:#d92d20">绾㈣壊锛氳瘖鏂姌绾?/span><span style="color:#155eef">钃濊壊锛氭姌绾垮悗鍦嗚鍖?/span><span style="color:#079455">缁胯壊锛氬師鐢熻繛缁洸绾?/span></div>
  <h2>Filleted seams only</h2>
  <img src="{artifacts['filleted_contact_sheet']}" alt="filleted seam synthesis contact sheet" />
  <h2>Native smooth seams only</h2>
  <img src="{artifacts['native_smooth_contact_sheet']}" alt="native smooth seam synthesis contact sheet" />
  <h2>Debug overlay</h2>
  <img src="{artifacts['contact_sheet']}" alt="axis Voronoi seam synthesis contact sheet" />
  <table>
    <thead><tr><th>seed</th><th>鐘舵€?/th><th>杈圭晫鏁?/th><th>杈撳嚭鐗堟湰</th><th>澶辫触椤?/th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
"""
