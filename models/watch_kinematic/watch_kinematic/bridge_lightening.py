"""2D lightening-window solver for watch bridge plates.

This module is intentionally review-first.  It uses a grid as a validation
scratchpad, but the design entities it reports are boundary bands, bearing
islands, and smooth ligament centerlines that can later be promoted to
analytic CAD curves.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.path import Path as MplPath
from scipy import ndimage

from . import power_chain_mvp as p
from .bridge_xy_partition import BRIDGE_AXIS_GROUPS
from .grid_curve_vectorization import vectorize_grid_contour_to_smooth_curve
from .partitioned_bridge_stage import build_analytic_bridge_stage_plan


LIGHTENING_GRID_RESOLUTION = 361
LIGHTENING_PERIMETER_SUPPORT_WIDTH_MM = max(2.4, p.BRIDGE_PERIMETER_RESERVED_BAND_MM)
LIGHTENING_BEARING_KEEP_RADIUS_MULTIPLIER = 2.5
LIGHTENING_FUNCTION_ENVELOPE_MARGIN_MM = 0.45
LIGHTENING_LIGAMENT_MIN_HALF_WIDTH_MM = 0.34
LIGHTENING_LIGAMENT_BULGE_HALF_WIDTH_MM = 0.98
LIGHTENING_MIN_WINDOW_AREA_MM2 = 1.6
LIGHTENING_MAX_WINDOW_COUNT = 2
LIGHTENING_WINDOW_FILLET_ITERATIONS = 3
LIGHTENING_WINDOW_SIMPLIFY_TOLERANCE_MM = 0.55
LIGHTENING_WINDOW_RAW_SMOOTH_SIMPLIFY_TOLERANCE_MM = 0.12
LIGHTENING_FASTENER_MIN_WEB_WIDTH_MM = max(
    1.4,
    p.FUTURE_BRIDGE_PLATE_THICKNESS_MM * 1.2,
    p.BRIDGE_COUNTERSUNK_HEAD_DIAMETER_MM,
)
LIGHTENING_FASTENER_WEB_SAFETY_MARGIN_MM = 0.35


def solve_bridge_lightening_plan(
    design: dict[str, Any],
    *,
    layout_id: str,
    grid_resolution: int = LIGHTENING_GRID_RESOLUTION,
    bridge_stage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a 2D lightening-window plan for the current analytic bridges."""

    bridge_stage = bridge_stage or build_analytic_bridge_stage_plan(design, layout_id=layout_id)
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    grid = _grid(grid_resolution)
    bridge_plans = []
    for bridge in bridge_stage["bridges"]:
        envelope = bridge_stage["_partition"]["envelopes"][bridge["bridge_id"]]
        bridge_plans.append(_solve_bridge_lightening(bridge, axis_by_id, envelope, grid))
    status = "pass" if all(item["status"] == "pass" for item in bridge_plans) else "review"
    return {
        "kind": "watch_bridge_lightening_plan_v1",
        "status": status,
        "layout_id": layout_id,
        "grid_resolution": grid_resolution,
        "policy": {
            "perimeter_support_width_mm": LIGHTENING_PERIMETER_SUPPORT_WIDTH_MM,
            "bearing_keep_radius_multiplier": LIGHTENING_BEARING_KEEP_RADIUS_MULTIPLIER,
            "functional_group_source": "existing bridge axis-system envelope",
            "ligament_shape": "group-level cubic bezier centerline with gaussian half-width bulge",
            "grid_role": "solver_and_validation_scratchpad_not_final_cad_boundary",
            "minimum_window_area_mm2": LIGHTENING_MIN_WINDOW_AREA_MM2,
            "max_window_count": LIGHTENING_MAX_WINDOW_COUNT,
            "fastener_minimum_web_width_mm": LIGHTENING_FASTENER_MIN_WEB_WIDTH_MM,
            "fastener_web_safety_margin_mm": LIGHTENING_FASTENER_WEB_SAFETY_MARGIN_MM,
        },
        "bridge_stage": {key: value for key, value in bridge_stage.items() if not key.startswith("_")},
        "bridges": bridge_plans,
    }


def render_bridge_lightening_plan(plan: dict[str, Any], output_path: str | Path) -> Path:
    """Render a human-reviewable XY drawing of the lightening plan."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), dpi=180)
    colors = {
        "barrel_bridge": "#e8c15b",
        "train_bridge": "#b8c7d8",
        "escapement_bridge": "#b9dfc5",
    }
    for ax, bridge in zip(axes, plan["bridges"]):
        _render_bridge_lightening_axis(ax, bridge, colors.get(bridge["bridge_id"], "#dddddd"))
    fig.suptitle(
        f"Bridge lightening proposal: {plan['layout_id']} | {plan['status']} | grid is validation scratchpad",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(output, facecolor="white")
    plt.close(fig)
    return output


def write_bridge_lightening_review(
    output_dir: str | Path,
    *,
    seed: int = 927,
    layout_id: str | None = None,
    grid_resolution: int = LIGHTENING_GRID_RESOLUTION,
) -> dict[str, Any]:
    """Generate the current 2D lightening review packet."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    layout = layout_id or f"seed_{seed}_lightening_01"
    design = p._build_design(seed, include_bridges=False)
    plan = solve_bridge_lightening_plan(design, layout_id=layout, grid_resolution=grid_resolution)
    png_path = target / "bridge_lightening_xy_review.png"
    json_path = target / "bridge_lightening_plan.json"
    render_bridge_lightening_plan(plan, png_path)
    json_path.write_text(json.dumps(_compact_plan_for_json(plan), indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "kind": "watch_bridge_lightening_review_packet",
        "status": plan["status"],
        "seed": seed,
        "layout_id": layout,
        "artifacts": {
            "review_png": str(png_path),
            "plan_json": str(json_path),
        },
        "summary": _plan_summary(plan),
    }


def _solve_bridge_lightening(
    bridge: dict[str, Any],
    axis_by_id: dict[str, dict[str, Any]],
    envelope: dict[str, Any],
    grid: dict[str, Any],
) -> dict[str, Any]:
    bridge_id = bridge["bridge_id"]
    xs = grid["xs"]
    ys = grid["ys"]
    pitch = grid["pitch"]
    mask = _bridge_mask(bridge, xs, ys)
    boundary_band = mask & (ndimage.distance_transform_edt(mask) * pitch <= LIGHTENING_PERIMETER_SUPPORT_WIDTH_MM)
    axis_records = [
        _axis_keepout_record(axis_by_id[axis_id])
        for axis_id in bridge.get("supported_axis_ids", BRIDGE_AXIS_GROUPS.get(bridge_id, []))
        if axis_id in axis_by_id
    ]
    bearing_keepouts = np.zeros_like(mask, dtype=bool)
    for axis in axis_records:
        bearing_keepouts |= _circle_mask(xs, ys, axis["x"], axis["y"], axis["keep_radius_mm"])
    fastener_records = _fastener_keepout_records(bridge)
    fastener_keepouts = np.zeros_like(mask, dtype=bool)
    for fastener in fastener_records:
        fastener_keepouts |= _circle_mask(xs, ys, fastener["x"], fastener["y"], fastener["keep_radius_mm"])
    functional_island = _functional_envelope_mask(envelope, xs, ys) & mask
    record, ligaments = _group_ligament_for_envelope(envelope, axis_records, mask, boundary_band, xs, ys)
    retained = mask & (boundary_band | functional_island | bearing_keepouts | fastener_keepouts | ligaments)
    raw_windows = mask & ~retained
    windows = _keep_primary_windows(raw_windows, pitch, max_count=_max_window_count_for_bridge(bridge_id))
    retained = mask & ~windows
    manufacturing_windows = _manufacturing_windows_from_mask(
        windows,
        xs,
        ys,
        protected_points=[*_bearing_protected_points(axis_records), *_fastener_protected_points(fastener_records)],
    )
    window_components = _component_summary(windows, pitch)
    bearing_connectivity = _bearing_connectivity(axis_records, retained, boundary_band, xs, ys)
    fastener_web_clearance = _fastener_web_clearance_report(manufacturing_windows, fastener_records)
    status = (
        "pass"
        if window_components["large_component_count"] > 0
        and all(item["status"] == "pass" for item in bearing_connectivity)
        and fastener_web_clearance["status"] == "pass"
        else "review"
    )
    return {
        "bridge_id": bridge_id,
        "status": status,
        "footprint_type": bridge["footprint_type"],
        "supported_axis_ids": list(bridge.get("supported_axis_ids", BRIDGE_AXIS_GROUPS.get(bridge_id, []))),
        "masks": {
            "xs": xs,
            "ys": ys,
            "bridge": mask,
            "boundary_band": boundary_band,
            "functional_island": functional_island,
            "bearing_keepouts": bearing_keepouts,
            "fastener_keepouts": fastener_keepouts,
            "ligaments": ligaments,
            "retained_material": retained,
            "lightening_windows": windows,
        },
        "manufacturing_windows": manufacturing_windows,
        "axes": axis_records,
        "functional_envelope": {
            "source": "bridge_xy_partition.envelopes",
            "points": [_round_point(tuple(point)) for point in envelope["points"]],
            "margin_mm": LIGHTENING_FUNCTION_ENVELOPE_MARGIN_MM,
        },
        "ligaments": [record],
        "window_components": window_components,
        "bearing_connectivity": bearing_connectivity,
        "fastener_web_clearance": fastener_web_clearance,
    }


def _max_window_count_for_bridge(bridge_id: str) -> int:
    return 2 if bridge_id == "train_bridge" else 1


def _render_bridge_lightening_axis(ax: Any, bridge: dict[str, Any], color: str) -> None:
    xs = np.array(bridge["masks"]["xs"])
    ys = np.array(bridge["masks"]["ys"])
    extent = [float(xs[0]), float(xs[-1]), float(ys[0]), float(ys[-1])]
    bridge_mask = np.array(bridge["masks"]["bridge"], dtype=bool)
    retained = np.array(bridge["masks"]["retained_material"], dtype=bool)
    windows = np.array(bridge["masks"]["lightening_windows"], dtype=bool)
    boundary = np.array(bridge["masks"]["boundary_band"], dtype=bool)
    functional_island = np.array(bridge["masks"]["functional_island"], dtype=bool)
    bearing = np.array(bridge["masks"]["bearing_keepouts"], dtype=bool)
    fastener = np.array(bridge["masks"].get("fastener_keepouts", np.zeros_like(bridge_mask)), dtype=bool)
    ligament = np.array(bridge["masks"]["ligaments"], dtype=bool)

    ax.imshow(np.ma.masked_where(~bridge_mask, bridge_mask), extent=extent, origin="lower", cmap=_single_color_cmap(color), alpha=0.22)
    ax.imshow(np.ma.masked_where(~windows, windows), extent=extent, origin="lower", cmap=_single_color_cmap("#ffffff"), alpha=0.88)
    ax.imshow(np.ma.masked_where(~boundary, boundary), extent=extent, origin="lower", cmap=_single_color_cmap("#59636f"), alpha=0.32)
    ax.imshow(np.ma.masked_where(~functional_island, functional_island), extent=extent, origin="lower", cmap=_single_color_cmap("#d5a0a0"), alpha=0.32)
    ax.imshow(np.ma.masked_where(~ligament, ligament), extent=extent, origin="lower", cmap=_single_color_cmap("#8b949e"), alpha=0.48)
    ax.imshow(np.ma.masked_where(~bearing, bearing), extent=extent, origin="lower", cmap=_single_color_cmap("#d86a6a"), alpha=0.52)
    ax.imshow(np.ma.masked_where(~fastener, fastener), extent=extent, origin="lower", cmap=_single_color_cmap("#9b59b6"), alpha=0.3)

    _draw_contour(ax, xs, ys, bridge_mask, "#222222", 1.2)
    _draw_contour(ax, xs, ys, retained, "#5f6872", 1.0)
    _draw_contour(ax, xs, ys, windows, "#1e9bd7", 1.4)
    for window in bridge.get("manufacturing_windows", []):
        points = np.array(window["points"], dtype=float)
        if len(points) > 1:
            closed = np.vstack([points, points[0]])
            ax.plot(closed[:, 0], closed[:, 1], color="#e04141", lw=1.6, zorder=12)
    for record in bridge["ligaments"]:
        points = np.array(record["centerline_points"], dtype=float)
        ax.plot(points[:, 0], points[:, 1], color="#6f7780", lw=1.15, ls="--")
    for axis in bridge["axes"]:
        ax.scatter([axis["x"]], [axis["y"]], s=10, color="#1e2530", zorder=10)
        ax.text(axis["x"], axis["y"] + axis["keep_radius_mm"] + 0.25, axis["axis_id"].replace("_axis", ""), fontsize=6, ha="center")
    ax.set_title(
        f"{bridge['bridge_id']} | {bridge['status']}\n"
        f"windows={bridge['window_components']['large_component_count']} "
        f"min area={bridge['window_components']['minimum_large_area_mm2']:.1f} mm2",
        fontsize=9,
    )
    ax.set_aspect("equal")
    ax.set_xlim(-p.CASE_RADIUS_MM - 1.5, p.CASE_RADIUS_MM + 1.5)
    ax.set_ylim(-p.CASE_RADIUS_MM - 1.5, p.CASE_RADIUS_MM + 1.5)
    ax.grid(True, color="#d9dee5", lw=0.35)


def _bridge_mask(bridge: dict[str, Any], xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    xv, yv = np.meshgrid(xs, ys)
    points = np.column_stack([xv.ravel(), yv.ravel()])
    footprint = bridge["footprint"]
    if footprint.get("components"):
        mask = np.zeros_like(xv, dtype=bool)
        for component in footprint["components"]:
            points_for_component = component.get("points", [])
            if len(points_for_component) < 3:
                continue
            path = MplPath(np.array(points_for_component, dtype=float))
            mask |= path.contains_points(points, radius=0.01).reshape(xv.shape)
        return mask
    if bridge["bridge_id"] == "train_bridge":
        mask = (xv * xv + yv * yv <= p.CASE_RADIUS_MM * p.CASE_RADIUS_MM).reshape(xv.shape)
        for keepout in footprint.get("keepouts", []):
            path = MplPath(np.array(keepout["points"], dtype=float))
            mask &= ~path.contains_points(points, radius=0.01).reshape(xv.shape)
        return mask
    path = MplPath(np.array(footprint["points"], dtype=float))
    return path.contains_points(points, radius=0.01).reshape(xv.shape)


def _axis_keepout_record(axis: dict[str, Any]) -> dict[str, Any]:
    bearing = axis.get("upper_jewel_bearing") or axis.get("future_upper_jewel_target") or {}
    radius = float(bearing.get("outer_radius", 0.42)) * LIGHTENING_BEARING_KEEP_RADIUS_MULTIPLIER
    return {
        "axis_id": axis["axis_id"],
        "x": float(axis["x"]),
        "y": float(axis["y"]),
        "bearing_outer_radius_mm": float(bearing.get("outer_radius", 0.42)),
        "keep_radius_mm": round(radius, 4),
    }


def _fastener_keepout_records(bridge: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for screw in bridge.get("screws", []):
        head_radius = float(screw.get("head_diameter_mm", p.BRIDGE_COUNTERSUNK_HEAD_DIAMETER_MM)) / 2.0
        records.append(
            {
                "screw_id": screw["screw_id"],
                "x": float(screw["x"]),
                "y": float(screw["y"]),
                "head_radius_mm": round(head_radius, 4),
                "minimum_web_width_mm": round(LIGHTENING_FASTENER_MIN_WEB_WIDTH_MM, 4),
                "keep_radius_mm": round(
                    head_radius + LIGHTENING_FASTENER_MIN_WEB_WIDTH_MM + LIGHTENING_FASTENER_WEB_SAFETY_MARGIN_MM,
                    4,
                ),
            }
        )
    return records


def _fastener_protected_points(fastener_records: list[dict[str, Any]]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for fastener in fastener_records:
        radius = float(fastener["head_radius_mm"]) + float(fastener["minimum_web_width_mm"])
        points.append((float(fastener["x"]), float(fastener["y"])))
        for index in range(24):
            angle = 2.0 * math.pi * index / 24
            points.append(
                (
                    float(fastener["x"]) + radius * math.cos(angle),
                    float(fastener["y"]) + radius * math.sin(angle),
                )
            )
    return points


def _functional_envelope_mask(envelope: dict[str, Any], xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    xv, yv = np.meshgrid(xs, ys)
    points = np.column_stack([xv.ravel(), yv.ravel()])
    path = MplPath(np.array(envelope["points"], dtype=float))
    return path.contains_points(points, radius=LIGHTENING_FUNCTION_ENVELOPE_MARGIN_MM).reshape(xv.shape)


def _group_ligament_for_envelope(
    envelope: dict[str, Any],
    axes: list[dict[str, Any]],
    bridge_mask: np.ndarray,
    boundary_band: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
) -> tuple[dict[str, Any], np.ndarray]:
    start = _envelope_connection_start(envelope, axes)
    end = _boundary_target(start, boundary_band, xs, ys)
    centerline = _smooth_centerline(start, end)
    mask = _variable_width_tube(centerline, xs, ys)
    mask &= bridge_mask
    return (
        {
            "axis_ids": [axis["axis_id"] for axis in axes],
            "shape": "group_level_bezier_gaussian_bulged_ligament",
            "start": _round_point(start),
            "end": _round_point(end),
            "centerline_points": [_round_point(point) for point in centerline[:: max(1, len(centerline) // 18)]],
            "min_half_width_mm": LIGHTENING_LIGAMENT_MIN_HALF_WIDTH_MM,
            "max_half_width_mm": LIGHTENING_LIGAMENT_MIN_HALF_WIDTH_MM + LIGHTENING_LIGAMENT_BULGE_HALF_WIDTH_MM,
        },
        mask,
    )


def _envelope_connection_start(envelope: dict[str, Any], axes: list[dict[str, Any]]) -> tuple[float, float]:
    points = np.array(envelope["points"], dtype=float)
    centroid = points.mean(axis=0)
    axis_centroid = np.array([[axis["x"], axis["y"]] for axis in axes], dtype=float).mean(axis=0)
    direction = centroid - axis_centroid
    if np.linalg.norm(direction) < 1e-6:
        direction = centroid
    norm = np.linalg.norm(direction)
    if norm < 1e-6:
        return (float(axis_centroid[0]), float(axis_centroid[1]))
    direction = direction / norm
    scores = points @ direction
    target = points[int(np.argmax(scores))]
    start = 0.55 * target + 0.45 * axis_centroid
    return (float(start[0]), float(start[1]))


def _boundary_target(start: tuple[float, float], boundary_band: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> tuple[float, float]:
    xv, yv = np.meshgrid(xs, ys)
    candidates = np.column_stack([xv[boundary_band], yv[boundary_band]])
    if len(candidates) == 0:
        angle = math.atan2(start[1], start[0])
        return ((p.CASE_RADIUS_MM - LIGHTENING_PERIMETER_SUPPORT_WIDTH_MM * 0.45) * math.cos(angle), (p.CASE_RADIUS_MM - LIGHTENING_PERIMETER_SUPPORT_WIDTH_MM * 0.45) * math.sin(angle))
    outer_score = np.hypot(candidates[:, 0], candidates[:, 1])
    direction = np.array(start, dtype=float)
    direction_norm = np.linalg.norm(direction)
    if direction_norm < 1e-6:
        direction = np.array([1.0, 0.0])
    else:
        direction = direction / direction_norm
    alignment = candidates @ direction
    distance = np.hypot(candidates[:, 0] - start[0], candidates[:, 1] - start[1])
    score = outer_score * 1.8 + alignment * 0.65 - distance * 0.12
    target = candidates[int(np.argmax(score))]
    return (float(target[0]), float(target[1]))


def _smooth_centerline(start: tuple[float, float], end: tuple[float, float], samples: int = 80) -> list[tuple[float, float]]:
    sx, sy = start
    ex, ey = end
    vx, vy = ex - sx, ey - sy
    length = max(math.hypot(vx, vy), 1e-6)
    nx, ny = -vy / length, vx / length
    bend = min(1.1, length * 0.075)
    sign = 1.0 if sx * ey - sy * ex >= 0 else -1.0
    c1 = (sx + 0.34 * vx + sign * nx * bend, sy + 0.34 * vy + sign * ny * bend)
    c2 = (sx + 0.72 * vx - sign * nx * bend * 0.45, sy + 0.72 * vy - sign * ny * bend * 0.45)
    points = []
    for t in np.linspace(0.0, 1.0, samples):
        u = 1.0 - t
        x = u**3 * sx + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * ex
        y = u**3 * sy + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * ey
        points.append((float(x), float(y)))
    return points


def _variable_width_tube(centerline: list[tuple[float, float]], xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    xv, yv = np.meshgrid(xs, ys)
    mask = np.zeros_like(xv, dtype=bool)
    pts = np.array(centerline, dtype=float)
    for index, (left, right) in enumerate(zip(pts[:-1], pts[1:])):
        segment = right - left
        seg_len2 = float(segment @ segment)
        if seg_len2 <= 1e-9:
            continue
        t_local = ((xv - left[0]) * segment[0] + (yv - left[1]) * segment[1]) / seg_len2
        t_clamped = np.clip(t_local, 0.0, 1.0)
        nearest_x = left[0] + t_clamped * segment[0]
        nearest_y = left[1] + t_clamped * segment[1]
        t_global = (index + t_clamped) / max(len(pts) - 1, 1)
        width = LIGHTENING_LIGAMENT_MIN_HALF_WIDTH_MM + LIGHTENING_LIGAMENT_BULGE_HALF_WIDTH_MM * np.exp(-((t_global - 0.18) ** 2) / (2 * 0.18**2))
        distance = np.hypot(xv - nearest_x, yv - nearest_y)
        mask |= distance <= width
    return mask


def _bearing_connectivity(axis_records: list[dict[str, Any]], retained: np.ndarray, boundary_band: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> list[dict[str, Any]]:
    labels, _count = ndimage.label(retained)
    xv, yv = np.meshgrid(xs, ys)
    boundary_labels = set(int(value) for value in np.unique(labels[boundary_band]) if int(value) > 0)
    result = []
    for axis in axis_records:
        axis_mask = _circle_mask(xs, ys, axis["x"], axis["y"], axis["keep_radius_mm"] * 0.6)
        axis_labels = set(int(value) for value in np.unique(labels[axis_mask]) if int(value) > 0)
        connected = bool(axis_labels & boundary_labels)
        result.append(
            {
                "axis_id": axis["axis_id"],
                "status": "pass" if connected else "fail",
                "connected_to_boundary_band": connected,
            }
        )
    return result


def _component_summary(mask: np.ndarray, pitch: float) -> dict[str, Any]:
    labels, count = ndimage.label(mask)
    areas = []
    for index in range(1, count + 1):
        area = float((labels == index).sum() * pitch * pitch)
        if area >= LIGHTENING_MIN_WINDOW_AREA_MM2:
            areas.append(area)
    return {
        "component_count": int(count),
        "large_component_count": len(areas),
        "large_areas_mm2": [round(value, 4) for value in sorted(areas, reverse=True)],
        "minimum_large_area_mm2": round(min(areas), 4) if areas else 0.0,
    }


def _fastener_web_clearance_report(
    windows: list[dict[str, Any]],
    fasteners: list[dict[str, Any]],
) -> dict[str, Any]:
    observations = []
    minimum_gap = float("inf")
    for window in windows:
        points = [tuple(float(value) for value in point) for point in window.get("points", [])]
        if len(points) < 3:
            continue
        for fastener in fasteners:
            distance_to_center = _minimum_closed_polyline_distance_to_point(points, (fastener["x"], fastener["y"]))
            gap = distance_to_center - fastener["head_radius_mm"]
            minimum_gap = min(minimum_gap, gap)
            observations.append(
                {
                    "window_id": window["window_id"],
                    "screw_id": fastener["screw_id"],
                    "gap_to_head_mm": round(gap, 4),
                    "minimum_required_web_mm": round(LIGHTENING_FASTENER_MIN_WEB_WIDTH_MM, 4),
                    "status": "pass" if gap + 1e-6 >= LIGHTENING_FASTENER_MIN_WEB_WIDTH_MM else "fail",
                }
            )
    if not observations:
        return {
            "status": "pass",
            "minimum_gap_to_fastener_head_mm": None,
            "minimum_required_web_mm": round(LIGHTENING_FASTENER_MIN_WEB_WIDTH_MM, 4),
            "observations": [],
        }
    return {
        "status": "pass" if all(item["status"] == "pass" for item in observations) else "fail",
        "minimum_gap_to_fastener_head_mm": round(minimum_gap, 4),
        "minimum_required_web_mm": round(LIGHTENING_FASTENER_MIN_WEB_WIDTH_MM, 4),
        "observations": observations,
    }


def _minimum_closed_polyline_distance_to_point(points: list[tuple[float, float]], point: tuple[float, float]) -> float:
    minimum = float("inf")
    px, py = point
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        sx, sy = float(start[0]), float(start[1])
        ex, ey = float(end[0]), float(end[1])
        vx, vy = ex - sx, ey - sy
        length_squared = vx * vx + vy * vy
        if length_squared <= 1e-12:
            distance = math.hypot(px - sx, py - sy)
        else:
            t = max(0.0, min(1.0, ((px - sx) * vx + (py - sy) * vy) / length_squared))
            distance = math.hypot(px - (sx + t * vx), py - (sy + t * vy))
        minimum = min(minimum, distance)
    return minimum


def _keep_primary_windows(mask: np.ndarray, pitch: float, *, max_count: int) -> np.ndarray:
    labels, count = ndimage.label(mask)
    if count == 0:
        return mask
    components: list[tuple[float, int]] = []
    for index in range(1, count + 1):
        area = float((labels == index).sum() * pitch * pitch)
        if area >= LIGHTENING_MIN_WINDOW_AREA_MM2:
            components.append((area, index))
    kept = np.zeros_like(mask, dtype=bool)
    for _area, index in sorted(components, reverse=True)[:max_count]:
        kept |= labels == index
    return kept


def _manufacturing_windows_from_mask(
    mask: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    *,
    protected_points: list[tuple[float, float]] | None = None,
) -> list[dict[str, Any]]:
    if not np.any(mask):
        return []
    labels, count = ndimage.label(mask)
    windows: list[dict[str, Any]] = []
    pitch = float(xs[1] - xs[0]) if len(xs) > 1 else 1.0
    protected_points = protected_points or []
    for index in range(1, count + 1):
        component = labels == index
        area = float(component.sum() * pitch * pitch)
        if area < LIGHTENING_MIN_WINDOW_AREA_MM2:
            continue
        contour = _largest_contour_points(component, xs, ys)
        if len(contour) < 4:
            continue
        simplified = _simplify_closed_polyline(contour, LIGHTENING_WINDOW_SIMPLIFY_TOLERANCE_MM)
        vectorized = vectorize_grid_contour_to_smooth_curve(
            contour,
            protected_points=protected_points,
            target_point_count=72,
            max_point_count=128,
            min_corner_angle_deg=65.0,
        )
        points = [tuple(float(value) for value in point) for point in vectorized.get("points", [])]
        if not points:
            continue
        quality = vectorized.get("quality", {})
        windows.append(
            {
                "window_id": f"window_{index}",
                "source": vectorized["source"],
                "cad_boundary_kind": vectorized["curve_kind"],
                "vectorization_status": vectorized["status"],
                "vectorization_quality": quality,
                "area_mm2": round(area, 4),
                "minimum_corner_angle_deg": round(float(quality.get("minimum_corner_angle_deg", _minimum_polygon_angle(points))), 4),
                "points": [_round_point(point) for point in points],
                "raw_point_count": len(contour),
                "simplified_point_count": len(simplified),
                "rounded_point_count": len(points),
                "vectorized_point_count": len(points),
            }
        )
    return sorted(windows, key=lambda item: item["area_mm2"], reverse=True)


def _bearing_protected_points(axis_records: list[dict[str, Any]]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for axis in axis_records:
        radius = max(float(axis["bearing_outer_radius_mm"]) + 0.18, float(axis["keep_radius_mm"]) * 0.64)
        points.append((float(axis["x"]), float(axis["y"])))
        for index in range(20):
            angle = 2.0 * math.pi * index / 20
            points.append(
                (
                    float(axis["x"]) + radius * math.cos(angle),
                    float(axis["y"]) + radius * math.sin(angle),
                )
            )
    return points


def _select_protected_safe_contour(
    raw: list[tuple[float, float]],
    simplified: list[tuple[float, float]],
    rounded: list[tuple[float, float]],
    protected_points: list[tuple[float, float]],
) -> tuple[list[tuple[float, float]], str]:
    raw_smoothed = _simplify_closed_polyline(
        _chaikin_closed(raw, 1),
        LIGHTENING_WINDOW_RAW_SMOOTH_SIMPLIFY_TOLERANCE_MM,
    )
    candidates = [
        (rounded, "grid_contour_simplified_then_chaikin_rounded_protected"),
        (raw_smoothed, "grid_contour_raw_then_chaikin_simplified_protected"),
        (simplified, "grid_contour_simplified_protected_fallback"),
        (raw, "grid_contour_raw_protected_fallback"),
    ]
    for points, source in candidates:
        if len(points) < 3:
            continue
        if not _polygon_contains_any(points, protected_points):
            return points, source
    return [], "rejected_window_would_cut_protected_bearing_keepout"


def _polygon_contains_any(points: list[tuple[float, float]], protected_points: list[tuple[float, float]]) -> bool:
    if not protected_points:
        return False
    path = MplPath(np.array(points, dtype=float))
    return any(path.contains_point(point, radius=1e-6) for point in protected_points)


def _largest_contour_points(mask: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> list[tuple[float, float]]:
    fig, ax = plt.subplots()
    try:
        contour_set = ax.contour(xs, ys, mask.astype(float), levels=[0.5])
        segments: list[np.ndarray] = []
        if hasattr(contour_set, "allsegs"):
            for level_segments in contour_set.allsegs:
                for vertices in level_segments:
                    if len(vertices) >= 4:
                        segments.append(vertices)
        else:
            for collection in contour_set.collections:
                for path in collection.get_paths():
                    vertices = path.vertices
                    if len(vertices) >= 4:
                        segments.append(vertices)
        if not segments:
            return []
        longest = max(segments, key=len)
        return [(float(x), float(y)) for x, y in longest]
    finally:
        plt.close(fig)


def _simplify_closed_polyline(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    if len(points) <= 4:
        return points
    open_points = points[:-1] if _distance(points[0], points[-1]) < 1e-6 else points
    simplified = _rdp(open_points, tolerance)
    return simplified if len(simplified) >= 3 else open_points


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
    if max_distance > tolerance:
        left = _rdp(points[: max_index + 1], tolerance)
        right = _rdp(points[max_index:], tolerance)
        return [*left[:-1], *right]
    return [start, end]


def _chaikin_closed(points: list[tuple[float, float]], iterations: int) -> list[tuple[float, float]]:
    result = list(points)
    for _ in range(iterations):
        next_points: list[tuple[float, float]] = []
        for index, current in enumerate(result):
            nxt = result[(index + 1) % len(result)]
            next_points.append((0.75 * current[0] + 0.25 * nxt[0], 0.75 * current[1] + 0.25 * nxt[1]))
            next_points.append((0.25 * current[0] + 0.75 * nxt[0], 0.25 * current[1] + 0.75 * nxt[1]))
        result = next_points
    return result


def _minimum_polygon_angle(points: list[tuple[float, float]]) -> float:
    result = 180.0
    for index, point in enumerate(points):
        prev = points[index - 1]
        nxt = points[(index + 1) % len(points)]
        v1 = (prev[0] - point[0], prev[1] - point[1])
        v2 = (nxt[0] - point[0], nxt[1] - point[1])
        d1 = math.hypot(*v1)
        d2 = math.hypot(*v2)
        if d1 * d2 <= 1e-9:
            continue
        cos_value = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (d1 * d2)))
        result = min(result, math.degrees(math.acos(cos_value)))
    return result


def _point_to_segment_distance(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    sx, sy = start
    ex, ey = end
    px, py = point
    vx, vy = ex - sx, ey - sy
    length2 = vx * vx + vy * vy
    if length2 <= 1e-9:
        return math.hypot(px - sx, py - sy)
    t = max(0.0, min(1.0, ((px - sx) * vx + (py - sy) * vy) / length2))
    nearest = (sx + t * vx, sy + t * vy)
    return math.hypot(px - nearest[0], py - nearest[1])


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _circle_mask(xs: np.ndarray, ys: np.ndarray, x: float, y: float, radius: float) -> np.ndarray:
    xv, yv = np.meshgrid(xs, ys)
    return (xv - x) ** 2 + (yv - y) ** 2 <= radius * radius


def _grid(resolution: int) -> dict[str, Any]:
    xs = np.linspace(-p.CASE_RADIUS_MM, p.CASE_RADIUS_MM, resolution)
    ys = np.linspace(-p.CASE_RADIUS_MM, p.CASE_RADIUS_MM, resolution)
    pitch = float(xs[1] - xs[0]) if len(xs) > 1 else 1.0
    return {"xs": xs, "ys": ys, "pitch": pitch}


def _draw_contour(ax: Any, xs: np.ndarray, ys: np.ndarray, mask: np.ndarray, color: str, linewidth: float) -> None:
    if not np.any(mask):
        return
    ax.contour(xs, ys, mask.astype(float), levels=[0.5], colors=[color], linewidths=linewidth)


def _single_color_cmap(color: str) -> Any:
    from matplotlib.colors import ListedColormap

    return ListedColormap([color])


def _plan_summary(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": plan["status"],
        "bridges": [
            {
                "bridge_id": bridge["bridge_id"],
                "status": bridge["status"],
                "large_window_count": bridge["window_components"]["large_component_count"],
                "bearing_connectivity": bridge["bearing_connectivity"],
            }
            for bridge in plan["bridges"]
        ],
    }


def _compact_plan_for_json(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": plan["kind"],
        "status": plan["status"],
        "layout_id": plan["layout_id"],
        "grid_resolution": plan["grid_resolution"],
        "policy": plan["policy"],
        "bridges": [
            {
                key: value
                for key, value in bridge.items()
                if key not in {"masks"}
            }
            for bridge in plan["bridges"]
        ],
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.astype(int).tolist() if value.dtype == bool else value.tolist()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    return value


def _round_point(point: tuple[float, float]) -> list[float]:
    return [round(float(point[0]), 4), round(float(point[1]), 4)]
