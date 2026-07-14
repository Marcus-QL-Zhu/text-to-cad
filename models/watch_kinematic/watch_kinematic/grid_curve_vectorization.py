"""Promote grid contours into smooth CAD-ready closed curves.

The grid remains a solver/validation scratchpad.  This module turns a contour
sampled from that grid into a bounded, smoother vector curve contract that CAD
generation can consume without falling back to a faceted polyline.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from matplotlib.path import Path as MplPath
from scipy import interpolate


def vectorize_grid_contour_to_smooth_curve(
    raw_points: list[tuple[float, float]],
    *,
    protected_points: list[tuple[float, float]] | None = None,
    target_point_count: int = 72,
    max_point_count: int = 128,
    min_corner_angle_deg: float = 65.0,
    max_segment_length_mm: float = 0.85,
) -> dict[str, Any]:
    """Return a smooth closed curve candidate for a grid-derived contour.

    The function intentionally returns sampled points, not CAD objects.  This
    keeps the result inspectable and lets downstream CAD code choose the final
    curve primitive while still knowing the source was vectorized.
    """

    protected_points = protected_points or []
    normalized = _remove_duplicate_closure(_dedupe_adjacent(raw_points))
    if len(normalized) < 4:
        return _result([], "failed_too_few_points", protected_points)

    candidates: list[tuple[str, list[tuple[float, float]]]] = []
    for smoothing in (0.02, 0.06, 0.12, 0.24, 0.42):
        for samples in (target_point_count, 96, 64):
            spline_points = _periodic_spline_points(normalized, samples=samples, smoothing=smoothing)
            if spline_points:
                candidates.append((f"grid_mask_periodic_spline_s{str(smoothing).replace('.', '_')}_{samples}", spline_points))

    # Conservative fallback: smooth a lightly simplified raw contour, then
    # simplify again.  This is still a vectorized curve candidate, not a raw
    # grid contour, and is useful when a global spline over-shoots.
    raw_smoothed = _chaikin_closed(normalized, 2)
    for tolerance in (0.08, 0.12, 0.18):
        simplified = _simplify_closed_polyline(raw_smoothed, tolerance)
        for iterations in (1, 2):
            candidates.append(
                (
                    f"grid_mask_chaikin_vectorized_tol{str(tolerance).replace('.', '_')}_i{iterations}",
                    _chaikin_closed(simplified, iterations),
                )
            )

    ranked = [_curve_quality(points, source, protected_points) for source, points in candidates if len(points) >= 4]
    if not ranked:
        return _result([], "failed_no_curve_candidate", protected_points)

    passing = [
        item
        for item in ranked
        if item["protected_violation_count"] == 0
        and item["self_intersection_count"] == 0
        and item["minimum_corner_angle_deg"] >= min_corner_angle_deg
        and item["point_count"] <= max_point_count
    ]
    pool = passing or [
        item
        for item in ranked
        if item["protected_violation_count"] == 0
        and item["self_intersection_count"] == 0
        and item["point_count"] <= max_point_count
    ]
    pool = pool or ranked

    selected = min(
        pool,
        key=lambda item: (
            item["protected_violation_count"],
            item["self_intersection_count"],
            max(0.0, min_corner_angle_deg - item["minimum_corner_angle_deg"]),
            abs(item["point_count"] - target_point_count),
            -item["minimum_corner_angle_deg"],
        ),
    )
    output_points = _densify_closed_curve(
        selected["points"],
        max_segment_length_mm=max_segment_length_mm,
        max_point_count=max_point_count,
    )
    output_quality = _curve_quality(output_points, selected["source"], protected_points)
    max_segment_length = _max_closed_segment_length(output_points)

    status = (
        "pass"
        if output_quality["protected_violation_count"] == 0
        and output_quality["self_intersection_count"] == 0
        and output_quality["minimum_corner_angle_deg"] >= min_corner_angle_deg
        and output_quality["point_count"] <= max_point_count
        and max_segment_length <= max_segment_length_mm + 1e-6
        else "review"
    )
    return {
        "status": status,
        "curve_kind": "smooth_vector_curve",
        "source": selected["source"],
        "points": [_round_point(point) for point in output_points],
        "quality": {
            "point_count": output_quality["point_count"],
            "minimum_corner_angle_deg": round(output_quality["minimum_corner_angle_deg"], 4),
            "protected_violation_count": output_quality["protected_violation_count"],
            "self_intersection_count": output_quality["self_intersection_count"],
            "maximum_segment_length_mm": round(max_segment_length, 4),
            "target_point_count": target_point_count,
            "max_point_count": max_point_count,
            "minimum_required_corner_angle_deg": min_corner_angle_deg,
            "maximum_allowed_segment_length_mm": max_segment_length_mm,
        },
    }


def _result(points: list[tuple[float, float]], source: str, protected_points: list[tuple[float, float]]) -> dict[str, Any]:
    quality = _curve_quality(points, source, protected_points) if points else {
        "point_count": 0,
        "minimum_corner_angle_deg": 0.0,
        "protected_violation_count": 0,
        "self_intersection_count": 0,
    }
    return {
        "status": "review",
        "curve_kind": "smooth_vector_curve",
        "source": source,
        "points": [_round_point(point) for point in points],
        "quality": quality,
    }


def _periodic_spline_points(
    points: list[tuple[float, float]],
    *,
    samples: int,
    smoothing: float,
) -> list[tuple[float, float]]:
    base = _remove_duplicate_closure(_dedupe_adjacent(points))
    if len(base) < 4:
        return []
    x = np.array([point[0] for point in base], dtype=float)
    y = np.array([point[1] for point in base], dtype=float)
    try:
        smooth_budget = max(0.0, float(len(base)) * float(smoothing) * float(smoothing))
        tck, _u = interpolate.splprep([x, y], s=smooth_budget, per=True, k=3)
        u_new = np.linspace(0.0, 1.0, int(samples), endpoint=False)
        sx, sy = interpolate.splev(u_new, tck)
    except Exception:
        return []
    return [(float(px), float(py)) for px, py in zip(sx, sy)]


def _curve_quality(
    points: list[tuple[float, float]],
    source: str,
    protected_points: list[tuple[float, float]],
) -> dict[str, Any]:
    normalized = _remove_duplicate_closure(_dedupe_adjacent(points))
    return {
        "source": source,
        "points": normalized,
        "point_count": len(normalized),
        "minimum_corner_angle_deg": _minimum_polygon_angle(normalized) if len(normalized) >= 3 else 0.0,
        "protected_violation_count": _protected_violation_count(normalized, protected_points),
        "self_intersection_count": _self_intersection_count(normalized),
    }


def _densify_closed_curve(
    points: list[tuple[float, float]],
    *,
    max_segment_length_mm: float,
    max_point_count: int,
) -> list[tuple[float, float]]:
    normalized = _remove_duplicate_closure(_dedupe_adjacent(points))
    if len(normalized) < 2:
        return normalized
    dense: list[tuple[float, float]] = []
    for index, start in enumerate(normalized):
        end = normalized[(index + 1) % len(normalized)]
        dense.append(start)
        distance = math.dist(start, end)
        insert_count = max(0, int(math.ceil(distance / max_segment_length_mm)) - 1)
        for step in range(1, insert_count + 1):
            t = step / float(insert_count + 1)
            dense.append((start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t))
    if len(dense) <= max_point_count:
        return dense
    return _resample_closed_curve(dense, max_point_count)


def _resample_closed_curve(points: list[tuple[float, float]], count: int) -> list[tuple[float, float]]:
    normalized = _remove_duplicate_closure(_dedupe_adjacent(points))
    if len(normalized) < 2 or count <= 0:
        return normalized
    lengths = [math.dist(normalized[index], normalized[(index + 1) % len(normalized)]) for index in range(len(normalized))]
    perimeter = sum(lengths)
    if perimeter <= 1e-9:
        return normalized
    samples: list[tuple[float, float]] = []
    segment_index = 0
    segment_start_distance = 0.0
    for sample_index in range(count):
        target = perimeter * sample_index / float(count)
        while segment_index < len(lengths) - 1 and segment_start_distance + lengths[segment_index] < target:
            segment_start_distance += lengths[segment_index]
            segment_index += 1
        start = normalized[segment_index]
        end = normalized[(segment_index + 1) % len(normalized)]
        segment_length = max(lengths[segment_index], 1e-9)
        t = (target - segment_start_distance) / segment_length
        samples.append((start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t))
    return samples


def _max_closed_segment_length(points: list[tuple[float, float]]) -> float:
    normalized = _remove_duplicate_closure(_dedupe_adjacent(points))
    if len(normalized) < 2:
        return 0.0
    return max(math.dist(normalized[index], normalized[(index + 1) % len(normalized)]) for index in range(len(normalized)))


def _protected_violation_count(points: list[tuple[float, float]], protected_points: list[tuple[float, float]]) -> int:
    if len(points) < 3 or not protected_points:
        return 0
    path = MplPath(np.array(points, dtype=float))
    return sum(1 for point in protected_points if path.contains_point(point, radius=1e-6))


def _self_intersection_count(points: list[tuple[float, float]]) -> int:
    if len(points) < 4:
        return 0
    count = 0
    n = len(points)
    for i in range(n):
        a1 = points[i]
        a2 = points[(i + 1) % n]
        for j in range(i + 1, n):
            if abs(i - j) <= 1 or {i, j} == {0, n - 1}:
                continue
            b1 = points[j]
            b2 = points[(j + 1) % n]
            if _segments_intersect(a1, a2, b1, b2):
                count += 1
    return count


def _segments_intersect(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> bool:
    def orient(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    o1 = orient(a1, a2, b1)
    o2 = orient(a1, a2, b2)
    o3 = orient(b1, b2, a1)
    o4 = orient(b1, b2, a2)
    return (o1 * o2 < -1e-9) and (o3 * o4 < -1e-9)


def _chaikin_closed(points: list[tuple[float, float]], iterations: int) -> list[tuple[float, float]]:
    smoothed = _remove_duplicate_closure(points)
    for _ in range(iterations):
        next_points: list[tuple[float, float]] = []
        for index, point in enumerate(smoothed):
            nxt = smoothed[(index + 1) % len(smoothed)]
            next_points.append((0.75 * point[0] + 0.25 * nxt[0], 0.75 * point[1] + 0.25 * nxt[1]))
            next_points.append((0.25 * point[0] + 0.75 * nxt[0], 0.25 * point[1] + 0.75 * nxt[1]))
        smoothed = next_points
    return smoothed


def _simplify_closed_polyline(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    clean = _remove_duplicate_closure(points)
    if len(clean) <= 4:
        return clean
    simplified = _rdp(clean, tolerance)
    return simplified if len(simplified) >= 3 else clean


def _rdp(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    start = points[0]
    end = points[-1]
    max_distance = -1.0
    max_index = 0
    for index, point in enumerate(points[1:-1], start=1):
        distance = _point_to_segment_distance(point, start, end)
        if distance > max_distance:
            max_distance = distance
            max_index = index
    if max_distance <= tolerance:
        return [start, end]
    left = _rdp(points[: max_index + 1], tolerance)
    right = _rdp(points[max_index:], tolerance)
    return left[:-1] + right


def _point_to_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    vx = end[0] - start[0]
    vy = end[1] - start[1]
    length_squared = vx * vx + vy * vy
    if length_squared <= 1e-12:
        return math.dist(point, start)
    t = max(0.0, min(1.0, ((point[0] - start[0]) * vx + (point[1] - start[1]) * vy) / length_squared))
    projection = (start[0] + t * vx, start[1] + t * vy)
    return math.dist(point, projection)


def _minimum_polygon_angle(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    minimum = 180.0
    for index, point in enumerate(points):
        prev = points[index - 1]
        nxt = points[(index + 1) % len(points)]
        v1 = (prev[0] - point[0], prev[1] - point[1])
        v2 = (nxt[0] - point[0], nxt[1] - point[1])
        l1 = math.hypot(*v1)
        l2 = math.hypot(*v2)
        if l1 <= 1e-9 or l2 <= 1e-9:
            continue
        dot = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)))
        minimum = min(minimum, math.degrees(math.acos(dot)))
    return minimum


def _dedupe_adjacent(points: list[tuple[float, float]] | list[list[float]]) -> list[tuple[float, float]]:
    clean: list[tuple[float, float]] = []
    for point in points:
        item = (float(point[0]), float(point[1]))
        if not clean or math.dist(clean[-1], item) > 1e-7:
            clean.append(item)
    return clean


def _remove_duplicate_closure(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    clean = list(points)
    while len(clean) > 1 and math.dist(clean[0], clean[-1]) <= 1e-7:
        clean.pop()
    return clean


def _round_point(point: tuple[float, float]) -> list[float]:
    return [round(float(point[0]), 4), round(float(point[1]), 4)]
