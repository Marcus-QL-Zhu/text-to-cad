"""Executable checklist gates for watch Pattern Card runs.

The checklist is intentionally separate from the generator report.  Generator
metadata can explain intent, but this module re-computes geometry facts from the
selected pattern facts and generated BREP shapes before it marks a gate pass.
"""

from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import power_chain_mvp as p
from .bridge_lightening import solve_bridge_lightening_plan
from .partitioned_bridge_stage import build_separate_display_bridge_stage_plan
from .partitioned_bridge_stage import _make_analytic_bridge_stage
from .pattern_cards.separate_hour_minute_no_seconds import PATTERN_CARD_ID, solve_separate_display_layout


REQUIRED_PATTERN2_BRIDGE_IDS = ("barrel_bridge", "train_bridge", "escapement_bridge")
MIN_BRIDGE_AREA_MM2 = 8.0
MIN_BRIDGE_VOLUME_MM3 = 2.0
MIN_LIGHTENING_AREA_RATIO = {
    "barrel_bridge": 0.025,
    "train_bridge": 0.055,
    "escapement_bridge": 0.025,
}


@dataclass(frozen=True)
class ChecklistItem:
    check_id: str
    label: str
    status: str
    evidence: dict[str, Any]
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "label": self.label,
            "status": self.status,
            "checked": self.status == "pass",
            "severity": self.severity,
            "evidence": self.evidence,
        }


def run_pattern2_bridge_checklist(seed: int, *, generate_step: bool = False) -> dict[str, Any]:
    """Run Pattern 2 bridge gates and return checkbox-ready report data."""

    del generate_step  # This sprint validates geometry without exporting STEP.
    design, bridge_stage = _build_pattern2_design_and_bridge_stage(seed)
    bridges = bridge_stage["bridges"]
    bridge_by_id = {bridge["bridge_id"]: bridge for bridge in bridges}
    items = [
        _required_bridge_entities_exist(bridge_by_id),
        _supported_bearings_covered_by_bridge_footprints(bridges),
        _bridge_plate_seams_have_real_gap(bridges),
        _lightening_windows_required_and_valid(bridges),
        _screws_inside_service_pads(bridges),
        _final_bridge_solids_have_volume(design, bridge_stage),
    ]
    payload_items = [item.to_dict() for item in items]
    failed_items = [item for item in payload_items if item["status"] != "pass" and item["severity"] == "error"]
    return {
        "kind": "watch_pattern_card_checklist",
        "pattern_card_id": PATTERN_CARD_ID,
        "seed": seed,
        "status": "pass" if not failed_items else "fail",
        "items": payload_items,
        "failed_items": failed_items,
    }


def write_pattern2_checklist_artifacts(
    output_dir: str | Path,
    *,
    seed: int,
    generate_step: bool = False,
) -> dict[str, Any]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    report = run_pattern2_bridge_checklist(seed=seed, generate_step=generate_step)
    json_path = target / "checklist.json"
    html_path = target / "checklist.html"
    report_with_artifacts = {
        **report,
        "artifacts": {
            "checklist_json": str(json_path),
            "checklist_html": str(html_path),
        },
    }
    json_path.write_text(json.dumps(report_with_artifacts, indent=2, ensure_ascii=False), encoding="utf-8")
    html_path.write_text(_render_checklist_html(report_with_artifacts), encoding="utf-8")
    return report_with_artifacts


def _build_pattern2_design_and_bridge_stage(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    solver_report = solve_separate_display_layout(seed=seed)
    if solver_report["status"] != "pass" or solver_report["selected_candidate"] is None:
        raise ValueError(f"Pattern 2 solver failed for seed {seed}")
    design = p._build_separate_display_design(seed, solver_report)
    bridge_stage = build_separate_display_bridge_stage_plan(design, layout_id=f"checklist_seed_{seed}")
    lightening = solve_bridge_lightening_plan(
        design,
        layout_id=f"checklist_seed_{seed}_lightening",
        bridge_stage=bridge_stage,
    )
    lightening_by_id = {bridge["bridge_id"]: bridge for bridge in lightening["bridges"]}
    for bridge in bridge_stage["bridges"]:
        lightening_record = lightening_by_id[bridge["bridge_id"]]
        bridge["lightening"] = {
            "status": lightening_record["status"],
            "manufacturing_windows": lightening_record["manufacturing_windows"],
            "fastener_web_clearance": lightening_record.get("fastener_web_clearance"),
            "policy": lightening["policy"],
        }
    design["bridges_generated"] = True
    design["bridge_stage"] = bridge_stage
    return design, bridge_stage


def _required_bridge_entities_exist(bridge_by_id: dict[str, dict[str, Any]]) -> ChecklistItem:
    missing = [bridge_id for bridge_id in REQUIRED_PATTERN2_BRIDGE_IDS if bridge_id not in bridge_by_id]
    area_records = {}
    for bridge_id in REQUIRED_PATTERN2_BRIDGE_IDS:
        bridge = bridge_by_id.get(bridge_id)
        if not bridge:
            continue
        area = _effective_bridge_area(bridge)
        area_records[bridge_id] = round(area, 4)
        if area < MIN_BRIDGE_AREA_MM2:
            missing.append(f"{bridge_id}:area<{MIN_BRIDGE_AREA_MM2}")
    return ChecklistItem(
        check_id="required_bridge_entities_exist",
        label="Required bridge entities exist with usable footprint area",
        status="pass" if not missing else "fail",
        evidence={"required_bridge_ids": list(REQUIRED_PATTERN2_BRIDGE_IDS), "area_mm2": area_records, "failures": missing},
    )


def _supported_bearings_covered_by_bridge_footprints(bridges: list[dict[str, Any]]) -> ChecklistItem:
    failures = []
    for bridge in bridges:
        for hole in bridge.get("clearance_holes", []):
            radius = float(hole["radius_mm"]) + 0.08
            samples = _sample_circle_points(float(hole["x"]), float(hole["y"]), radius, count=20)
            uncovered = [point for point in samples if not _effective_bridge_contains_point(bridge, point)]
            if uncovered:
                failures.append(
                    {
                        "bridge_id": bridge["bridge_id"],
                        "axis_id": hole["axis_id"],
                        "uncovered_sample_count": len(uncovered),
                    }
                )
    return ChecklistItem(
        check_id="supported_bearings_covered_by_bridge_footprints",
        label="Every supported upper bearing is covered by its owning bridge footprint",
        status="pass" if not failures else "fail",
        evidence={"failures": failures},
    )


def _bridge_plate_seams_have_real_gap(bridges: list[dict[str, Any]]) -> ChecklistItem:
    records = []
    failures = []
    for left, right in _pairwise(bridges):
        distance = _minimum_component_distance(left, right)
        record = {
            "left_bridge_id": left["bridge_id"],
            "right_bridge_id": right["bridge_id"],
            "minimum_gap_mm": round(distance, 4),
            "required_gap_mm": p.BRIDGE_SEAM_GAP_WIDTH_MM,
        }
        records.append(record)
        if distance + 0.05 < p.BRIDGE_SEAM_GAP_WIDTH_MM:
            failures.append(record)
    return ChecklistItem(
        check_id="bridge_plate_seams_have_real_gap",
        label="Bridge plates have real final XY gaps between adjacent regions",
        status="pass" if not failures else "fail",
        evidence={"pairs": records, "failures": failures},
        severity="warning",
    )


def _lightening_windows_required_and_valid(bridges: list[dict[str, Any]]) -> ChecklistItem:
    failures = []
    records = []
    for bridge in bridges:
        windows = bridge.get("lightening", {}).get("manufacturing_windows", [])
        bridge_area = max(_effective_bridge_area(bridge), 1e-9)
        window_area = sum(_polygon_area(_points(window.get("points", []))) for window in windows)
        ratio = window_area / bridge_area
        record = {
            "bridge_id": bridge["bridge_id"],
            "window_count": len(windows),
            "window_area_mm2": round(window_area, 4),
            "bridge_area_mm2": round(bridge_area, 4),
            "window_area_ratio": round(ratio, 4),
            "minimum_ratio": MIN_LIGHTENING_AREA_RATIO.get(bridge["bridge_id"], 0.025),
        }
        records.append(record)
        if not windows:
            failures.append({**record, "reason": "missing_lightening_window"})
            continue
        if ratio + 1e-6 < MIN_LIGHTENING_AREA_RATIO.get(bridge["bridge_id"], 0.025):
            failures.append({**record, "reason": "lightening_area_too_small"})
        for window in windows:
            if window.get("cad_boundary_kind") != "smooth_vector_curve":
                failures.append({"bridge_id": bridge["bridge_id"], "window_id": window.get("window_id"), "reason": "not_smooth_vector_curve"})
            points = _points(window.get("points", []))
            if len(points) < 3:
                failures.append({"bridge_id": bridge["bridge_id"], "window_id": window.get("window_id"), "reason": "window_has_too_few_points"})
                continue
            outside = [point for point in points if not _effective_bridge_contains_point(bridge, point)]
            if outside:
                failures.append(
                    {
                        "bridge_id": bridge["bridge_id"],
                        "window_id": window.get("window_id"),
                        "reason": "window_outside_bridge_footprint",
                        "outside_point_count": len(outside),
                    }
                )
            for hole in bridge.get("clearance_holes", []):
                protected = _sample_circle_points(float(hole["x"]), float(hole["y"]), float(hole["radius_mm"]) + 0.12, count=16)
                if any(_point_in_polygon(point, points) for point in protected):
                    failures.append(
                        {
                            "bridge_id": bridge["bridge_id"],
                            "window_id": window.get("window_id"),
                            "axis_id": hole["axis_id"],
                            "reason": "window_intrudes_bearing_keepout",
                        }
                    )
    return ChecklistItem(
        check_id="lightening_windows_required_and_valid",
        label="Lightening windows are useful, smooth, inside bridge footprints, and outside bearing keepouts",
        status="pass" if not failures else "fail",
        evidence={"records": records, "failures": failures},
    )


def _screws_inside_service_pads(bridges: list[dict[str, Any]]) -> ChecklistItem:
    failures = []
    records = []
    for bridge in bridges:
        pads = bridge.get("support_pads", [])
        for screw in bridge.get("screws", []):
            containing_pads = [pad["pad_id"] for pad in pads if _annular_sector_contains(pad, float(screw["x"]), float(screw["y"]))]
            record = {
                "bridge_id": bridge["bridge_id"],
                "screw_id": screw["screw_id"],
                "containing_pad_ids": containing_pads,
            }
            records.append(record)
            if not containing_pads:
                failures.append({**record, "reason": "screw_not_inside_service_pad"})
        for pad in pads:
            samples = _support_pad_samples(pad)
            outside = [point for point in samples if not _effective_bridge_or_pad_contains_point(bridge, point)]
            if outside:
                failures.append(
                    {
                        "bridge_id": bridge["bridge_id"],
                        "pad_id": pad["pad_id"],
                        "reason": "support_pad_not_joined_to_bridge_body",
                        "outside_sample_count": len(outside),
                    }
                )
            attachment_samples = _support_pad_inner_attachment_samples(pad)
            unattached = [point for point in attachment_samples if not _effective_bridge_contains_point(bridge, point)]
            if unattached:
                failures.append(
                    {
                        "bridge_id": bridge["bridge_id"],
                        "pad_id": pad["pad_id"],
                        "reason": "support_pad_inner_edge_not_attached_to_bridge_plate",
                        "unattached_sample_count": len(unattached),
                    }
                )
    return ChecklistItem(
        check_id="screws_inside_service_pads",
        label="Bridge screws sit inside matching service support pads",
        status="pass" if not failures else "fail",
        evidence={"records": records, "failures": failures},
    )


def _final_bridge_solids_have_volume(design: dict[str, Any], bridge_stage: dict[str, Any]) -> ChecklistItem:
    del bridge_stage
    failures = []
    records = []
    try:
        children = _make_analytic_bridge_stage(design)
    except Exception as exc:
        return ChecklistItem(
            check_id="final_bridge_solids_have_volume",
            label="Generated bridge BREP solids exist and have nonzero volume",
            status="fail",
            evidence={"exception": repr(exc)},
        )
    by_label = {str(getattr(child, "label", "")): child for child in children}
    for bridge_id in REQUIRED_PATTERN2_BRIDGE_IDS:
        child = by_label.get(bridge_id)
        bridge_record = next((bridge for bridge in design["bridge_stage"]["bridges"] if bridge["bridge_id"] == bridge_id), None)
        if child is None:
            failures.append({"bridge_id": bridge_id, "reason": "missing_brep_child"})
            continue
        volume = float(getattr(child, "volume", 0.0))
        edge_count = len(child.edges())
        bbox = child.bounding_box()
        observed_z_thickness = float(bbox.max.Z) - float(bbox.min.Z)
        expected_z_thickness = (
            float(bridge_record["z_max_mm"]) - float(bridge_record["z_min_mm"]) if bridge_record else 0.0
        )
        record = {
            "bridge_id": bridge_id,
            "volume_mm3": round(volume, 4),
            "edge_count": edge_count,
            "observed_z_thickness_mm": round(observed_z_thickness, 4),
            "expected_z_thickness_mm": round(expected_z_thickness, 4),
            "bbox_min": [round(float(value), 4) for value in tuple(bbox.min)],
            "bbox_max": [round(float(value), 4) for value in tuple(bbox.max)],
        }
        records.append(record)
        if observed_z_thickness + 1e-6 < expected_z_thickness * 0.75:
            failures.append({**record, "reason": "z_thickness_too_small_for_visible_bridge_solid"})
        if volume < MIN_BRIDGE_VOLUME_MM3:
            record["volume_warning"] = "volume_property_is_zero_or_tiny"
        if edge_count > 900:
            failures.append({**record, "reason": "edge_count_too_high_for_smooth_bridge"})
    return ChecklistItem(
        check_id="final_bridge_solids_have_volume",
        label="Generated bridge BREP solids exist, stay visible, and are not pathological",
        status="pass" if not failures else "fail",
        evidence={"records": records, "failures": failures},
    )


def _render_checklist_html(report: dict[str, Any]) -> str:
    rows = []
    for item in report["items"]:
        checked = " checked" if item["checked"] else ""
        rows.append(
            "<tr>"
            f"<td><input type=\"checkbox\" disabled{checked}></td>"
            f"<td><code>{html.escape(item['check_id'])}</code></td>"
            f"<td>{html.escape(item['status'])}</td>"
            f"<td>{html.escape(item['label'])}</td>"
            f"<td><pre>{html.escape(json.dumps(item['evidence'], indent=2, ensure_ascii=False))}</pre></td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <title>Pattern Card Checklist</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 28px; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d8dee8; padding: 8px; vertical-align: top; }}
    pre {{ margin: 0; white-space: pre-wrap; font-size: 12px; }}
    code {{ background: #eef3f8; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Pattern Card Checklist</h1>
  <p>Pattern: <code>{html.escape(report['pattern_card_id'])}</code></p>
  <p>Seed: <code>{report['seed']}</code> | Status: <strong>{html.escape(report['status'])}</strong></p>
  <table>
    <thead><tr><th>Done</th><th>Check</th><th>Status</th><th>Label</th><th>Evidence</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>
"""


def _points(raw_points: Iterable[Any]) -> list[tuple[float, float]]:
    return [(float(point[0]), float(point[1])) for point in raw_points]


def _effective_bridge_components(bridge: dict[str, Any]) -> list[list[tuple[float, float]]]:
    components = [
        _points(component.get("points", []))
        for component in bridge.get("footprint", {}).get("components", [])
        if len(component.get("points", [])) >= 3
    ]
    if components:
        return components
    points = _points(bridge.get("footprint", {}).get("points", []))
    return [points] if len(points) >= 3 else []


def _effective_bridge_area(bridge: dict[str, Any]) -> float:
    return sum(abs(_polygon_area(points)) for points in _effective_bridge_components(bridge))


def _effective_bridge_contains_point(bridge: dict[str, Any], point: tuple[float, float]) -> bool:
    return any(_point_in_polygon(point, component) for component in _effective_bridge_components(bridge))


def _effective_bridge_or_pad_contains_point(bridge: dict[str, Any], point: tuple[float, float]) -> bool:
    if _effective_bridge_contains_point(bridge, point):
        return True
    return any(_annular_sector_contains(pad, point[0], point[1]) for pad in bridge.get("support_pads", []))


def _polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for left, right in zip(points, [*points[1:], points[0]]):
        area += left[0] * right[1] - right[0] * left[1]
    return abs(area) / 2.0


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, pi in enumerate(polygon):
        xi, yi = pi
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) if abs(yj - yi) > 1e-12 else 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    if inside:
        return True
    return _minimum_closed_polyline_distance_to_point(polygon, point) <= 1e-6


def _sample_circle_points(x: float, y: float, radius: float, *, count: int) -> list[tuple[float, float]]:
    return [
        (x + radius * math.cos(2 * math.pi * index / count), y + radius * math.sin(2 * math.pi * index / count))
        for index in range(count)
    ]


def _annular_sector_contains(pad: dict[str, Any], x: float, y: float) -> bool:
    radius = math.hypot(x, y)
    if radius + 1e-6 < float(pad["inner_radius_mm"]) or radius - 1e-6 > float(pad["outer_radius_mm"]):
        return False
    angle = math.degrees(math.atan2(y, x)) % 360.0
    return _angle_inside_span(angle, float(pad["angular_start_deg"]), float(pad["angular_end_deg"]))


def _support_pad_samples(pad: dict[str, Any]) -> list[tuple[float, float]]:
    inner = float(pad["inner_radius_mm"])
    outer = float(pad["outer_radius_mm"])
    start = float(pad["angular_start_deg"])
    end = float(pad["angular_end_deg"])
    span = _positive_span(start, end)
    radii = [inner + (outer - inner) * fraction for fraction in (0.18, 0.5, 0.82)]
    angles = [start + span * fraction for fraction in (0.1, 0.5, 0.9)]
    return [(radius * math.cos(math.radians(angle)), radius * math.sin(math.radians(angle))) for radius in radii for angle in angles]


def _support_pad_inner_attachment_samples(pad: dict[str, Any]) -> list[tuple[float, float]]:
    radius = float(pad["inner_radius_mm"]) + 0.05
    start = float(pad["angular_start_deg"])
    span = _positive_span(start, float(pad["angular_end_deg"]))
    angles = [start + span * fraction for fraction in (0.18, 0.5, 0.82)]
    return [(radius * math.cos(math.radians(angle)), radius * math.sin(math.radians(angle))) for angle in angles]


def _bridge_components_for_distance(bridge: dict[str, Any]) -> list[list[tuple[float, float]]]:
    components = _effective_bridge_components(bridge)
    for pad in bridge.get("support_pads", []):
        components.append(_annular_sector_points(pad))
    return components


def _annular_sector_points(pad: dict[str, Any], *, count: int = 12) -> list[tuple[float, float]]:
    inner = float(pad["inner_radius_mm"])
    outer = float(pad["outer_radius_mm"])
    start = float(pad["angular_start_deg"])
    span = _positive_span(start, float(pad["angular_end_deg"]))
    outer_points = [
        (outer * math.cos(math.radians(start + span * index / count)), outer * math.sin(math.radians(start + span * index / count)))
        for index in range(count + 1)
    ]
    inner_points = [
        (inner * math.cos(math.radians(start + span * index / count)), inner * math.sin(math.radians(start + span * index / count)))
        for index in range(count, -1, -1)
    ]
    return [*outer_points, *inner_points]


def _minimum_component_distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    minimum = math.inf
    for left_component in _bridge_components_for_distance(left):
        for right_component in _bridge_components_for_distance(right):
            if _polygons_overlap(left_component, right_component):
                return 0.0
            minimum = min(minimum, _minimum_polyline_distance(left_component, right_component))
    return minimum


def _polygons_overlap(left: list[tuple[float, float]], right: list[tuple[float, float]]) -> bool:
    if any(_point_in_polygon(point, right) for point in left):
        return True
    if any(_point_in_polygon(point, left) for point in right):
        return True
    for a1, a2 in _segments(left):
        for b1, b2 in _segments(right):
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False


def _minimum_polyline_distance(left: list[tuple[float, float]], right: list[tuple[float, float]]) -> float:
    return min(_segment_distance(a1, a2, b1, b2) for a1, a2 in _segments(left) for b1, b2 in _segments(right))


def _minimum_closed_polyline_distance_to_point(points: list[tuple[float, float]], point: tuple[float, float]) -> float:
    if len(points) < 2:
        return math.inf
    return min(_point_to_segment_distance(point, start, end) for start, end in _segments(points))


def _segments(points: list[tuple[float, float]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return list(zip(points, [*points[1:], points[0]]))


def _segments_intersect(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> bool:
    def orientation(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float]) -> float:
        return (p1[1] - p0[1]) * (p2[0] - p1[0]) - (p1[0] - p0[0]) * (p2[1] - p1[1])

    o1 = orientation(a1, a2, b1)
    o2 = orientation(a1, a2, b2)
    o3 = orientation(b1, b2, a1)
    o4 = orientation(b1, b2, a2)
    return o1 * o2 < -1e-9 and o3 * o4 < -1e-9


def _segment_distance(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> float:
    if _segments_intersect(a1, a2, b1, b2):
        return 0.0
    return min(
        _point_to_segment_distance(a1, b1, b2),
        _point_to_segment_distance(a2, b1, b2),
        _point_to_segment_distance(b1, a1, a2),
        _point_to_segment_distance(b2, a1, a2),
    )


def _point_to_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return math.hypot(px - sx, py - sy)
    t = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / length_sq))
    return math.hypot(px - (sx + t * dx), py - (sy + t * dy))


def _pairwise(items: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [(items[i], items[j]) for i in range(len(items)) for j in range(i + 1, len(items))]


def _angle_inside_span(angle: float, start: float, end: float) -> bool:
    return ((angle - start) % 360.0) <= _positive_span(start, end) + 1e-6


def _positive_span(start: float, end: float) -> float:
    return (end - start) % 360.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run watch Pattern 2 executable checklist gates.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generate-step", action="store_true")
    args = parser.parse_args()
    report = write_pattern2_checklist_artifacts(args.output, seed=args.seed, generate_step=args.generate_step)
    print(json.dumps({"status": report["status"], "artifacts": report["artifacts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
