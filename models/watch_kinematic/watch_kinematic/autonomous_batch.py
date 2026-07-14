"""Autonomous five-design generation loop for the watch kinematic demo."""

from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from html import escape
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from build123d import Align, Circle, Compound, Cylinder, Location, Part, Plane, Polygon, export_step, extrude
from PIL import Image, ImageDraw, ImageFont

from .cases import load_watch_case
from .rule_space import build_rule_space_report


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CASE = REPO_ROOT / "models" / "watch_kinematic" / "cases" / "case_leap_style_balanced.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "models" / "watch_kinematic" / "outputs" / "autonomous_five_designs"
ARBOR_RADIUS_MM = 0.28
ARBOR_SHAFT_CENTER_Z = 1.05
ARBOR_SHAFT_HEIGHT = 4.2
ARBOR_SHAFT_TOP_Z = ARBOR_SHAFT_CENTER_Z + ARBOR_SHAFT_HEIGHT / 2.0
OUTPUT_HAND_POST_RADIUS_MM = 0.22
MAINPLATE_CENTER_Z = -1.25
MAINPLATE_THICKNESS = 0.65
MAINPLATE_TOP_Z = MAINPLATE_CENTER_Z + MAINPLATE_THICKNESS / 2.0
PIVOT_SEAT_HEIGHT = 0.18
LOWER_PIVOT_SEAT_CENTER_Z = MAINPLATE_TOP_Z + PIVOT_SEAT_HEIGHT / 2.0
BRIDGE_BOTTOM_Z = 2.42
BRIDGE_THICKNESS = 0.46
BRIDGE_TOP_Z = BRIDGE_BOTTOM_Z + BRIDGE_THICKNESS
UPPER_PIVOT_SEAT_CENTER_Z = BRIDGE_TOP_Z + PIVOT_SEAT_HEIGHT / 2.0
SCREW_HEAD_HEIGHT = 0.18
SCREW_HEAD_CENTER_Z = BRIDGE_TOP_Z + SCREW_HEAD_HEIGHT / 2.0
SCREW_SHANK_TOP_Z = BRIDGE_TOP_Z
SCREW_SHANK_BOTTOM_Z = MAINPLATE_TOP_Z - 0.22
SCREW_SHANK_HEIGHT = SCREW_SHANK_TOP_Z - SCREW_SHANK_BOTTOM_Z
SCREW_SHANK_CENTER_Z = (SCREW_SHANK_TOP_Z + SCREW_SHANK_BOTTOM_Z) / 2.0
SCREW_SHANK_RADIUS_MM = 0.16
FASTENER_RECEIVER_OUTER_RADIUS_MM = 0.43
OUTPUT_HAND_HUB_HEIGHT = 0.22
OUTPUT_HAND_HUB_CENTER_Z = ARBOR_SHAFT_TOP_Z + OUTPUT_HAND_HUB_HEIGHT / 2.0
OUTPUT_HAND_HUB_BOTTOM_Z = OUTPUT_HAND_HUB_CENTER_Z - OUTPUT_HAND_HUB_HEIGHT / 2.0
OUTPUT_HAND_HUB_TOP_Z = OUTPUT_HAND_HUB_CENTER_Z + OUTPUT_HAND_HUB_HEIGHT / 2.0
OUTPUT_HAND_HUB_RADIUS_MM = 0.56
OUTPUT_HAND_BLADE_TOP_Z = OUTPUT_HAND_HUB_CENTER_Z + OUTPUT_HAND_HUB_HEIGHT / 2.0 - 0.01
OUTPUT_HAND_TAIL_TOP_Z = OUTPUT_HAND_BLADE_TOP_Z - 0.02
OUTPUT_HAND_BLADE_THICKNESS = 0.16
OUTPUT_HAND_TAIL_THICKNESS = 0.14
OUTPUT_HAND_BLADE_START_RADIUS_MM = 0.48
OUTPUT_HAND_TAIL_START_RADIUS_MM = 0.42
OUTPUT_HAND_CAP_HEIGHT = 0.16
OUTPUT_HAND_CAP_CENTER_Z = OUTPUT_HAND_HUB_CENTER_Z + OUTPUT_HAND_HUB_HEIGHT / 2.0 + OUTPUT_HAND_CAP_HEIGHT / 2.0
OUTPUT_HAND_POST_TOP_Z = OUTPUT_HAND_HUB_TOP_Z + 0.06
OUTPUT_HAND_POST_HEIGHT = OUTPUT_HAND_POST_TOP_Z - ARBOR_SHAFT_TOP_Z
OUTPUT_HAND_MIN_POST_ENGAGEMENT_MM = 0.1
GEAR_BODY_HEIGHT = 0.72
GEAR_STACK_TOP_OFFSET = 0.87
MOTION_ENVELOPE_CLEARANCE_MM = 0.25
BRIDGE_PIVOT_PAD_RADIUS_MM = 0.84
BRIDGE_SCREW_PAD_RADIUS_MM = 0.68
BRIDGE_RIB_WIDTH_MM = 0.42
BRIDGE_MIN_RIB_COUNT_PER_BRIDGE = 1
BRIDGE_WEB_WIDTH_MM = 0.7
BRIDGE_ROUTE_SOFT_CLEARANCE_MM = 0.9
BRIDGE_ROUTE_HARD_CLEARANCE_MM = 0.25
BRIDGE_MAX_SOFT_GEAR_OVERLAP_RATIO = 0.34
FORBIDDEN_STANDALONE_PARENT_FEATURE_PREFIXES = (
    "gear_spoke_",
    "bridge_clearance_hole_",
    "mainplate_threaded_receiver_",
    "bridge_screw_slot_",
)
UNCONTRACTED_VISUAL_PRODUCT_PREFIXES = (
    "drive_spiral_visual_stack",
    "drive_spiral_ring_",
)


def run_watch_design_batch(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    design_count: int = 5,
    case_path: str | Path = DEFAULT_CASE,
) -> dict[str, Any]:
    """Generate several distinct watch-style mechanism designs and validate them.

    This is a deterministic V1 loop. It does not claim production watchmaking
    correctness; it proves the current generator can produce varied, reviewable,
    STEP-backed kinematic mechanism demos with explicit semantic, interference,
    motion, and visual-review evidence.
    """

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    case = load_watch_case(case_path)
    candidates = _select_distinct_valid_candidates(design_count)

    designs: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        design_dir = target / f"{index:02d}_{candidate['candidate_id']}"
        design_dir.mkdir(parents=True, exist_ok=True)
        designs.append(_generate_one_design(case, candidate, design_dir, index))

    manifest = _build_batch_manifest(target, designs, design_count)
    manifest_path = target / "batch_manifest.json"
    review_path = target / "batch_review.html"
    contact_sheet_path = target / "batch_visual_contact_sheet.png"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    review_path.write_text(_render_batch_review(manifest), encoding="utf-8")
    _write_batch_contact_sheet(manifest, contact_sheet_path)

    result = deepcopy(manifest)
    result["artifacts"] = {
        "batch_manifest": str(manifest_path),
        "batch_review_html": str(review_path),
        "batch_visual_contact_sheet": str(contact_sheet_path),
    }
    return result


def _select_distinct_valid_candidates(design_count: int) -> list[dict[str, Any]]:
    report = build_rule_space_report()
    valid = [
        deepcopy(candidate)
        for candidate in report["candidates"]
        if candidate["validation"]["status"] == "valid"
    ]

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in valid:
        fingerprint = _candidate_fingerprint(candidate)
        if fingerprint not in seen:
            candidate["fingerprint"] = fingerprint
            selected.append(candidate)
            seen.add(fingerprint)
        if len(selected) == design_count:
            return selected
    raise ValueError(f"only found {len(selected)} distinct valid candidates; need {design_count}")


def _generate_one_design(case: dict[str, Any], candidate: dict[str, Any], design_dir: Path, sequence: int) -> dict[str, Any]:
    prepared = _prepare_candidate_geometry(case, candidate)
    role_contract = _build_role_contract_report(prepared)
    semantic = _build_semantic_report(case, prepared, sequence)
    kinematic = _build_kinematic_report(prepared)
    interference = _build_interference_report(prepared)
    visual = _build_visual_review_report(prepared)
    assembly = _build_watch_assembly(prepared)
    production = _build_production_geometry_report(prepared, role_contract, assembly)
    validation = _build_validation_report(prepared, semantic, kinematic, interference, role_contract, production, visual)

    step_path = design_dir / "watch_kinematic.step"
    semantic_path = design_dir / "watch_kinematic.semantic.json"
    kinematic_path = design_dir / "watch_kinematic.kinematic.json"
    interference_path = design_dir / "watch_kinematic.interference.json"
    role_contract_path = design_dir / "watch_kinematic.role_contracts.json"
    production_path = design_dir / "watch_kinematic.production_geometry.json"
    visual_path = design_dir / "watch_kinematic.visual_review.json"
    validation_path = design_dir / "watch_kinematic.validation.json"
    dashboard_path = design_dir / "dashboard.html"
    visual_html_path = design_dir / "visual_review.html"
    bridge_2d_html_path = design_dir / "bridge_2d_review.html"

    export_step(assembly, step_path)
    semantic_path.write_text(json.dumps(semantic, indent=2, ensure_ascii=False), encoding="utf-8")
    kinematic_path.write_text(json.dumps(kinematic, indent=2, ensure_ascii=False), encoding="utf-8")
    interference_path.write_text(json.dumps(interference, indent=2, ensure_ascii=False), encoding="utf-8")
    role_contract_path.write_text(json.dumps(role_contract, indent=2, ensure_ascii=False), encoding="utf-8")
    production_path.write_text(json.dumps(production, indent=2, ensure_ascii=False), encoding="utf-8")
    visual_path.write_text(json.dumps(visual, indent=2, ensure_ascii=False), encoding="utf-8")
    validation_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
    dashboard_path.write_text(_render_design_dashboard(prepared, validation), encoding="utf-8")
    visual_html_path.write_text(_render_visual_review(prepared, visual), encoding="utf-8")
    bridge_2d_html_path.write_text(_render_bridge_2d_review(prepared, production), encoding="utf-8")

    artifacts = {
        "step": str(step_path),
        "semantic_json": str(semantic_path),
        "kinematic_json": str(kinematic_path),
        "interference_json": str(interference_path),
        "role_contract_json": str(role_contract_path),
        "production_geometry_json": str(production_path),
        "visual_review_json": str(visual_path),
        "validation_json": str(validation_path),
        "dashboard_html": str(dashboard_path),
        "visual_review_html": str(visual_html_path),
        "bridge_2d_review_html": str(bridge_2d_html_path),
    }
    return {
        "design_id": prepared["design_id"],
        "candidate_id": prepared["candidate_id"],
        "fingerprint": prepared["fingerprint"],
        "topology_family": prepared["topology_family"],
        "status": validation["status"],
        "semantic_checks": semantic["summary"],
        "interference_checks": interference["summary"],
        "power_chain_checks": kinematic["summary"],
        "role_contract_checks": role_contract["summary"],
        "production_geometry_checks": production["summary"],
        "visual_review_checks": visual["summary"],
        "visual_preview": _build_visual_preview(prepared),
        "artifacts": artifacts,
    }


def _prepare_candidate_geometry(case: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    prepared = deepcopy(candidate)
    prepared["case"] = case
    prepared["design_id"] = f"watch_{candidate['candidate_id']}"
    prepared["case_radius_mm"] = float(case["case_diameter_mm"]) / 2.0
    prepared["movement_radius_mm"] = prepared["case_radius_mm"] - 4.5
    prepared["fingerprint"] = candidate.get("fingerprint") or _candidate_fingerprint(candidate)

    axis_by_id = {axis["axis_id"]: axis for axis in prepared["axes"]}
    gear_by_id = {gear["gear_id"]: gear for gear in prepared["gears"]}
    axis_gear_radii: dict[str, list[float]] = defaultdict(list)
    for gear in prepared["gears"]:
        axis_gear_radii[gear["axis_id"]].append(float(gear["pitch_radius"]))

    centroid_x = sum(axis["x"] for axis in prepared["axes"]) / len(prepared["axes"])
    centroid_y = sum(axis["y"] for axis in prepared["axes"]) / len(prepared["axes"])
    raw_extent = 1.0
    for axis in prepared["axes"]:
        max_axis_gear = max(axis_gear_radii[axis["axis_id"]], default=1.0)
        raw_extent = max(raw_extent, math.hypot(axis["x"] - centroid_x, axis["y"] - centroid_y) + max_axis_gear)
    scale = prepared["movement_radius_mm"] * 0.92 / raw_extent
    prepared["layout_scale"] = round(scale, 5)

    for axis in prepared["axes"]:
        axis["layout_x"] = round((axis["x"] - centroid_x) * scale, 4)
        axis["layout_y"] = round((axis["y"] - centroid_y) * scale, 4)
        axis["local_frame"] = {
            "origin": [axis["layout_x"], axis["layout_y"], 0.0],
            "z_axis": [0.0, 0.0, 1.0],
            "plane": "movement_xy",
        }

    _attach_arbor_geometry_evidence(prepared)

    gear_layers = _assign_mesh_layers(prepared)
    for gear in prepared["gears"]:
        axis = axis_by_id[gear["axis_id"]]
        gear["layout_x"] = axis["layout_x"]
        gear["layout_y"] = axis["layout_y"]
        gear["layout_pitch_radius"] = round(float(gear["pitch_radius"]) * scale, 4)
        gear["layout_outer_radius"] = round(gear["layout_pitch_radius"] + max(0.32, 0.055 * gear["layout_pitch_radius"]), 4)
        gear["layout_root_radius"] = round(max(0.8, gear["layout_pitch_radius"] - max(0.42, 0.075 * gear["layout_pitch_radius"])), 4)
        gear["layout_z"] = round(0.2 + 0.95 * gear_layers.get(gear["gear_id"], 0), 4)
        gear["layout_z_min"] = gear["layout_z"]
        gear["layout_z_max"] = round(gear["layout_z"] + GEAR_STACK_TOP_OFFSET, 4)
    _attach_train_gear_mount_geometry_evidence(prepared)

    for mesh in prepared["meshes"]:
        gear_a = gear_by_id[mesh["gear_a"]]
        gear_b = gear_by_id[mesh["gear_b"]]
        mesh["layout_center_distance"] = round(
            math.hypot(gear_a["layout_x"] - gear_b["layout_x"], gear_a["layout_y"] - gear_b["layout_y"]),
            4,
        )
        mesh["layout_target_center_distance"] = round(
            gear_a["layout_pitch_radius"] + gear_b["layout_pitch_radius"],
            4,
        )
    _assign_bridge_screw_layouts(prepared)
    _attach_train_gear_mesh_geometry_evidence(prepared)
    _attach_plate_bridge_fastener_geometry_evidence(prepared)
    _attach_output_display_geometry_evidence(prepared)
    _attach_geometry_observation_sources(prepared)
    return prepared


def _assign_bridge_screw_layouts(candidate: dict[str, Any]) -> None:
    for bridge in candidate["bridges"]:
        axes = [axis for axis in candidate["axes"] if axis["axis_id"] in bridge["axis_ids"]]
        bridge_screws = [screw for screw in candidate["screws"] if screw["bridge_id"] == bridge["bridge_id"]]
        route_normal = _bridge_route_normal(candidate, axes)
        for screw in bridge_screws:
            try:
                screw_index = int(screw["screw_id"].rsplit("_s", 1)[1]) - 1
            except (IndexError, ValueError):
                screw_index = 0
            anchor = _bridge_screw_anchor_axis(axes, screw_index)
            x, y = _choose_motion_clear_fastener_point(candidate, axes, anchor, screw_index, route_normal=route_normal)
            screw["layout_x"] = round(x, 4)
            screw["layout_y"] = round(y, 4)


def _bridge_screw_anchor_axis(axes: list[dict[str, Any]], screw_index: int) -> dict[str, Any]:
    if not axes:
        return {"layout_x": 0.0, "layout_y": 0.0}
    if len(axes) == 1:
        return axes[0]
    return axes[0] if screw_index % 2 == 0 else axes[-1]


def _choose_motion_clear_fastener_point(
    candidate: dict[str, Any],
    axes: list[dict[str, Any]],
    anchor: dict[str, Any],
    screw_index: int,
    *,
    route_normal: tuple[float, float] | None = None,
) -> tuple[float, float]:
    ax = anchor["layout_x"]
    ay = anchor["layout_y"]
    if route_normal:
        ux, uy = route_normal
    else:
        radial = math.hypot(ax, ay)
        if radial > 0.2:
            ux = ax / radial
            uy = ay / radial
        elif len(axes) >= 2:
            dx = axes[-1]["layout_x"] - axes[0]["layout_x"]
            dy = axes[-1]["layout_y"] - axes[0]["layout_y"]
            length = math.hypot(dx, dy) or 1.0
            side = -1.0 if screw_index % 2 else 1.0
            ux = -dy / length * side
            uy = dx / length * side
        else:
            ux = -1.0 if screw_index % 2 else 1.0
            uy = 0.0

    if route_normal:
        start_offset = _bridge_route_offset(candidate, axes) + BRIDGE_SCREW_PAD_RADIUS_MM + 0.25
    elif len(axes) >= 2:
        start_offset = 0.8
    else:
        start_offset = 0.8

    max_radius = candidate["case_radius_mm"] - FASTENER_RECEIVER_OUTER_RADIUS_MM - 0.6
    best_point = (ax + ux * start_offset, ay + uy * start_offset)
    best_clearance = -1.0
    for step in range(0, 96):
        offset = start_offset + step * 0.18
        x = ax + ux * offset
        y = ay + uy * offset
        if math.hypot(x, y) + FASTENER_RECEIVER_OUTER_RADIUS_MM > max_radius:
            break
        clearance = _minimum_radial_clearance_to_gears(candidate, x, y, SCREW_SHANK_RADIUS_MM)
        if clearance > best_clearance:
            best_clearance = clearance
            best_point = (x, y)
        if clearance >= MOTION_ENVELOPE_CLEARANCE_MM:
            return x, y
    return best_point


def _minimum_radial_clearance_to_gears(candidate: dict[str, Any], x: float, y: float, radius: float) -> float:
    clearances = []
    for gear in candidate["gears"]:
        distance = math.hypot(x - gear["layout_x"], y - gear["layout_y"])
        clearances.append(distance - (gear["layout_outer_radius"] + radius))
    return min(clearances) if clearances else float("inf")


def _axis_bridge_offset(candidate: dict[str, Any], axis: dict[str, Any]) -> float:
    axis_id = axis.get("axis_id")
    gear_radius = max(
        (gear["layout_outer_radius"] for gear in candidate["gears"] if gear["axis_id"] == axis_id),
        default=BRIDGE_PIVOT_PAD_RADIUS_MM,
    )
    return gear_radius + BRIDGE_ROUTE_SOFT_CLEARANCE_MM + BRIDGE_WEB_WIDTH_MM / 2.0


def _bridge_route_offset(candidate: dict[str, Any], axes: list[dict[str, Any]]) -> float:
    return max((_axis_bridge_offset(candidate, axis) for axis in axes), default=BRIDGE_PIVOT_PAD_RADIUS_MM)


def _bridge_route_normal(candidate: dict[str, Any], axes: list[dict[str, Any]]) -> tuple[float, float]:
    if len(axes) < 2:
        axis = axes[0] if axes else {"layout_x": 0.0, "layout_y": 0.0}
        radial = math.hypot(axis["layout_x"], axis["layout_y"])
        if radial > 0.2:
            return axis["layout_x"] / radial, axis["layout_y"] / radial
        return 0.0, 1.0

    dx = axes[-1]["layout_x"] - axes[0]["layout_x"]
    dy = axes[-1]["layout_y"] - axes[0]["layout_y"]
    length = math.hypot(dx, dy) or 1.0
    candidates = [(-dy / length, dx / length), (dy / length, -dx / length)]
    route_offset = _bridge_route_offset(candidate, axes)

    def score(normal: tuple[float, float]) -> float:
        min_margin = float("inf")
        radial_sum = 0.0
        waypoints = []
        for axis in axes:
            x, y = _bridge_axis_waypoint(candidate, axis, normal, route_offset)
            margin = candidate["case_radius_mm"] - (math.hypot(x, y) + BRIDGE_WEB_WIDTH_MM / 2.0)
            min_margin = min(min_margin, margin)
            radial_sum += math.hypot(x, y)
            waypoints.append({"axis_id": axis["axis_id"], "x": x, "y": y})

        segments = [
            {
                "from": (axis["layout_x"], axis["layout_y"]),
                "to": (waypoint["x"], waypoint["y"]),
                "allowed_axis_ids": [axis["axis_id"]] + _direct_mesh_neighbor_axis_ids(candidate, axis["axis_id"]),
            }
            for axis, waypoint in zip(axes, waypoints)
        ]
        segments.extend(
            {
                "from": (left["x"], left["y"]),
                "to": (right["x"], right["y"]),
                "allowed_axis_ids": [left["axis_id"], right["axis_id"]],
            }
            for left, right in zip(waypoints, waypoints[1:])
        )
        max_overlap = max((_bridge_route_segment_soft_overlap_ratio(candidate, segment) for segment in segments), default=0.0)
        return min_margin * 100.0 + radial_sum - max_overlap * 10000.0

    return max(candidates, key=score)


def _bridge_axis_waypoint(
    candidate: dict[str, Any],
    axis: dict[str, Any],
    normal: tuple[float, float],
    route_offset: float,
) -> tuple[float, float]:
    offset = route_offset
    x = axis["layout_x"] + normal[0] * offset
    y = axis["layout_y"] + normal[1] * offset
    max_center_radius = candidate["case_radius_mm"] - BRIDGE_WEB_WIDTH_MM / 2.0 - BRIDGE_ROUTE_HARD_CLEARANCE_MM
    radius = math.hypot(x, y)
    if radius > max_center_radius > 0:
        scale = max_center_radius / radius
        x *= scale
        y *= scale
    return round(x, 4), round(y, 4)


def _segment_length(segment: dict[str, Any]) -> float:
    x1, y1 = segment["from"]
    x2, y2 = segment["to"]
    return math.hypot(x2 - x1, y2 - y1)


def _point_to_segment_distance(
    px: float,
    py: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> float:
    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    projection_x = x1 + t * dx
    projection_y = y1 + t * dy
    return math.hypot(px - projection_x, py - projection_y)


def _sample_segment_points(segment: dict[str, Any], step_mm: float = 0.35) -> list[tuple[float, float]]:
    x1, y1 = segment["from"]
    x2, y2 = segment["to"]
    length = max(_segment_length(segment), step_mm)
    count = max(2, int(math.ceil(length / step_mm)) + 1)
    return [
        (
            x1 + (x2 - x1) * index / (count - 1),
            y1 + (y2 - y1) * index / (count - 1),
        )
        for index in range(count)
    ]


def _bridge_2d_route_plan(candidate: dict[str, Any], bridge: dict[str, Any]) -> dict[str, Any]:
    axes = _bridge_axes(candidate, bridge)
    screws = _bridge_screws(candidate, bridge)
    normal = _bridge_route_normal(candidate, axes)
    route_offset = _bridge_route_offset(candidate, axes)
    waypoints = [
        {
            "node_id": f"waypoint:{axis['axis_id']}",
            "axis_id": axis["axis_id"],
            "x": point[0],
            "y": point[1],
        }
        for axis in axes
        for point in [_bridge_axis_waypoint(candidate, axis, normal, route_offset)]
    ]
    waypoint_by_axis = {waypoint["axis_id"]: waypoint for waypoint in waypoints}

    segments: list[dict[str, Any]] = []
    for axis in axes:
        waypoint = waypoint_by_axis[axis["axis_id"]]
        segments.append(
            {
                "segment_id": f"axis_spoke:{axis['axis_id']}",
                "kind": "axis_to_route_corridor",
                "from": (axis["layout_x"], axis["layout_y"]),
                "to": (waypoint["x"], waypoint["y"]),
                "allowed_axis_ids": [axis["axis_id"]] + _direct_mesh_neighbor_axis_ids(candidate, axis["axis_id"]),
            }
        )
    for left, right in zip(waypoints, waypoints[1:]):
        segments.append(
            {
                "segment_id": f"route_web:{left['axis_id']}:{right['axis_id']}",
                "kind": "allowed_corridor_web",
                "from": (left["x"], left["y"]),
                "to": (right["x"], right["y"]),
                "allowed_axis_ids": [left["axis_id"], right["axis_id"]],
            }
        )
    for screw in screws:
        if not waypoints:
            continue
        target = waypoints[0] if screw is screws[0] else waypoints[-1]
        segments.append(
            {
                "segment_id": f"screw_tie:{screw['screw_id']}",
                "kind": "fastener_to_route_corridor",
                "from": (screw.get("layout_x", 0.0), screw.get("layout_y", 0.0)),
                "to": (target["x"], target["y"]),
                "allowed_axis_ids": [target["axis_id"]],
            }
        )
    return {
        "bridge_id": bridge["bridge_id"],
        "normal": [round(normal[0], 4), round(normal[1], 4)],
        "route_offset_mm": round(route_offset, 4),
        "required_nodes": [
            {"node_id": f"axis:{axis['axis_id']}", "x": axis["layout_x"], "y": axis["layout_y"]}
            for axis in axes
        ]
        + [
            {"node_id": f"screw:{screw['screw_id']}", "x": screw.get("layout_x", 0.0), "y": screw.get("layout_y", 0.0)}
            for screw in screws
        ],
        "waypoints": waypoints,
        "segments": [segment for segment in segments if _segment_length(segment) > 0.05],
    }


def _bridge_route_segment_soft_overlap_ratio(candidate: dict[str, Any], segment: dict[str, Any]) -> float:
    samples = _sample_segment_points(segment)
    if not samples:
        return 0.0
    allowed_axis_ids = set(segment.get("allowed_axis_ids", []))
    overlap_count = 0
    for x, y in samples:
        overlaps = False
        for gear in candidate["gears"]:
            if gear["axis_id"] in allowed_axis_ids:
                continue
            distance = math.hypot(x - gear["layout_x"], y - gear["layout_y"])
            if distance <= gear["layout_outer_radius"] + BRIDGE_WEB_WIDTH_MM / 2.0:
                overlaps = True
                break
        if overlaps:
            overlap_count += 1
    return overlap_count / len(samples)


def _direct_mesh_neighbor_axis_ids(candidate: dict[str, Any], axis_id: str) -> list[str]:
    gear_axis = {gear["gear_id"]: gear["axis_id"] for gear in candidate["gears"]}
    neighbors = set()
    for mesh in candidate["meshes"]:
        axis_a = gear_axis.get(mesh["gear_a"])
        axis_b = gear_axis.get(mesh["gear_b"])
        if axis_a == axis_id and axis_b and axis_b != axis_id:
            neighbors.add(axis_b)
        if axis_b == axis_id and axis_a and axis_a != axis_id:
            neighbors.add(axis_a)
    return sorted(neighbors)


def _bridge_route_plan_observation(candidate: dict[str, Any], bridge: dict[str, Any]) -> dict[str, Any]:
    plan = _bridge_2d_route_plan(candidate, bridge)
    hard_intrusions = []
    segment_observations = []
    for segment in plan["segments"]:
        samples = _sample_segment_points(segment)
        outside_samples = []
        for x, y in samples:
            margin = candidate["case_radius_mm"] - (math.hypot(x, y) + BRIDGE_WEB_WIDTH_MM / 2.0)
            if margin < BRIDGE_ROUTE_HARD_CLEARANCE_MM:
                outside_samples.append({"x": round(x, 4), "y": round(y, 4), "case_margin_mm": round(margin, 4)})
        soft_overlap_ratio = _bridge_route_segment_soft_overlap_ratio(candidate, segment)
        if outside_samples:
            hard_intrusions.append(
                {
                    "segment_id": segment["segment_id"],
                    "reason": "expanded bridge web leaves hard case boundary corridor",
                    "sample_count": len(outside_samples),
                    "worst_case_margin_mm": min(item["case_margin_mm"] for item in outside_samples),
                }
            )
        segment_observations.append(
            {
                "segment_id": segment["segment_id"],
                "kind": segment["kind"],
                "length_mm": round(_segment_length(segment), 4),
                "soft_gear_overlap_ratio": round(soft_overlap_ratio, 4),
            }
        )
    max_soft_overlap_ratio = max(
        (item["soft_gear_overlap_ratio"] for item in segment_observations),
        default=0.0,
    )
    return {
        "bridge_id": bridge["bridge_id"],
        "plan_kind": "xy_route_planned_bridge_footprint",
        "required_node_count": len(plan["required_nodes"]),
        "waypoint_count": len(plan["waypoints"]),
        "segment_count": len(plan["segments"]),
        "web_width_mm": BRIDGE_WEB_WIDTH_MM,
        "soft_gear_overlap_limit": BRIDGE_MAX_SOFT_GEAR_OVERLAP_RATIO,
        "max_soft_gear_overlap_ratio": max_soft_overlap_ratio,
        "single_continuous_footprint": bool(plan["required_nodes"]) and bool(plan["segments"]),
        "hard_forbidden_intrusions": hard_intrusions,
        "segments": segment_observations,
    }


def _bridge_2d_route_plan_observations(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    return [_bridge_route_plan_observation(candidate, bridge) for bridge in candidate["bridges"]]


def _bridge_2d_route_plan_failures_for_bridge(candidate: dict[str, Any], bridge: dict[str, Any]) -> list[dict[str, Any]]:
    observation = _bridge_route_plan_observation(candidate, bridge)
    failures = []
    if not observation["single_continuous_footprint"]:
        failures.append({**observation, "reason": "bridge route plan does not create one continuous footprint"})
    if observation["hard_forbidden_intrusions"]:
        failures.append({**observation, "reason": "bridge route plan enters hard forbidden region"})
    if observation["max_soft_gear_overlap_ratio"] > BRIDGE_MAX_SOFT_GEAR_OVERLAP_RATIO:
        failures.append({**observation, "reason": "bridge route plan covers too much nonlocal gear projection"})
    return failures


def _find_bridge_2d_route_plan_failures(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    failures = []
    for bridge in candidate["bridges"]:
        failures.extend(_bridge_2d_route_plan_failures_for_bridge(candidate, bridge))
    return failures


def _bridge_2d_human_review_required(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    review = candidate.get("bridge_2d_human_review", {})
    if review.get("status") == "accepted":
        return []
    return [
        {
            "bridge_id": bridge["bridge_id"],
            "reason": "2D bridge morphology must be reviewed before 3D bridge geometry can be accepted",
            "required_artifact": "bridge_2d_review.html",
            "current_3d_status": "blocked",
        }
        for bridge in candidate["bridges"]
    ]


def _attach_arbor_geometry_evidence(candidate: dict[str, Any]) -> None:
    geometry_evidence = set(candidate.get("geometry_evidence", []))
    physical_arbors = []
    for axis in candidate["axes"]:
        axis_id = axis["axis_id"]
        physical_arbors.append({"axis_id": axis_id, "kind": "z_axis_arbor_with_lower_and_upper_pivot_seats"})
        geometry_evidence.update(
            {
                f"physical_z_arbor:{axis_id}",
                f"lower_pivot_seat:{axis_id}",
                f"upper_pivot_seat:{axis_id}",
            }
        )
    candidate.setdefault("production_features", {})["physical_z_arbors"] = physical_arbors
    candidate["geometry_evidence"] = sorted(geometry_evidence)


def _attach_train_gear_mount_geometry_evidence(candidate: dict[str, Any]) -> None:
    geometry_evidence = set(candidate.get("geometry_evidence", []))
    mounts = []
    tooth_profiles = []
    for gear in candidate["gears"]:
        gear_id = gear["gear_id"]
        mounts.append(
            {
                "gear_id": gear_id,
                "axis_id": gear["axis_id"],
                "kind": "coaxial_arbor_bore_with_visible_hub_and_rivet_collar",
            }
        )
        tooth_profiles.append(
            {
                "gear_id": gear_id,
                "axis_id": gear["axis_id"],
                "kind": "cycloidal_review_approximation",
                "scope": "visual_and_semantic_v1_not_horological_certification",
            }
        )
        geometry_evidence.add(f"arbor_bore_or_hub:{gear_id}")
        geometry_evidence.add(f"approved_tooth_profile:{gear_id}")
    candidate.setdefault("production_features", {})["gear_arbor_mounts"] = mounts
    candidate.setdefault("production_features", {})["gear_tooth_profiles"] = tooth_profiles
    candidate["geometry_evidence"] = sorted(geometry_evidence)


def _attach_train_gear_mesh_geometry_evidence(candidate: dict[str, Any]) -> None:
    geometry_evidence = set(candidate.get("geometry_evidence", []))
    mesh_envelopes = []
    for mesh in candidate["meshes"]:
        error = abs(mesh["layout_center_distance"] - mesh["layout_target_center_distance"])
        if error <= 0.08:
            mesh_envelopes.append(
                {
                    "gear_a": mesh["gear_a"],
                    "gear_b": mesh["gear_b"],
                    "center_distance_error_mm": round(error, 4),
                    "kind": "declared_pitch_circle_contact_envelope",
                }
            )
            geometry_evidence.add(f"mesh_envelope_clearance:{mesh['gear_a']}")
            geometry_evidence.add(f"mesh_envelope_clearance:{mesh['gear_b']}")
    candidate.setdefault("production_features", {})["gear_mesh_envelopes"] = mesh_envelopes
    candidate["geometry_evidence"] = sorted(geometry_evidence)


def _attach_plate_bridge_fastener_geometry_evidence(candidate: dict[str, Any]) -> None:
    geometry_evidence = set(candidate.get("geometry_evidence", []))
    geometry_evidence.update({"plate_body_geometry", "foundation_case_geometry", "lower_pivot_seat_geometry", "fastener_receiver_geometry"})
    bridge_interfaces = []
    fastener_interfaces = []
    for bridge in candidate["bridges"]:
        bridge_id = bridge["bridge_id"]
        geometry_evidence.add(f"fastener_interface:{bridge_id}")
        geometry_evidence.add(f"motion_envelope_clearance:{bridge_id}")
        if not _bridge_2d_route_plan_failures_for_bridge(candidate, bridge):
            geometry_evidence.add(f"bridge_2d_route_plan:{bridge_id}")
        if not _bridge_constraint_chain_failures_for_bridge(candidate, bridge):
            geometry_evidence.add(f"bridge_6dof_constraint_chain:{bridge_id}")
        bridge_interfaces.append(
            {
                "bridge_id": bridge_id,
                "kind": "route_planned_train_bridge_with_upper_pivot_seats_and_counterbores",
            }
        )
    for screw in candidate["screws"]:
        screw_id = screw["screw_id"]
        geometry_evidence.add(f"fastener_head_bearing_face:{screw_id}")
        geometry_evidence.add(f"fastener_clearance_path:{screw_id}")
        geometry_evidence.add(f"fastener_receiving_feature:{screw_id}")
        if not _bridge_fastener_motion_envelope_intrusions(candidate, screw):
            geometry_evidence.add(f"fastener_motion_envelope_clearance:{screw_id}")
        fastener_interfaces.append(
            {
                "screw_id": screw_id,
                "bridge_id": screw["bridge_id"],
                "kind": "simplified_watch_bridge_screw_stack",
                "standard": "watch_demo_micro_screw_visual_contract",
            }
        )
    features = candidate.setdefault("production_features", {})
    features["mainplate_fastener_receivers"] = fastener_interfaces
    features["bridge_fastener_interfaces"] = bridge_interfaces
    candidate["geometry_evidence"] = sorted(geometry_evidence)


def _attach_output_display_geometry_evidence(candidate: dict[str, Any]) -> None:
    geometry_evidence = set(candidate.get("geometry_evidence", []))
    outputs = []
    for output in candidate["outputs"]:
        axis_id = output["axis_id"]
        geometry_evidence.add(f"coaxial_mounting_hub:{axis_id}")
        geometry_evidence.add(f"output_arbor_hand_post:{axis_id}")
        geometry_evidence.add(f"display_blade_geometry:{axis_id}")
        geometry_evidence.add(f"hand_sweep_clearance:{axis_id}")
        outputs.append(
            {
                "axis_id": axis_id,
                "kind": "coaxial_hub_with_positive_arbor_post_engagement_and_tapered_pointer",
                "scope": "visible_output_display_for_review",
            }
        )
    candidate.setdefault("production_features", {})["output_display_hands"] = outputs
    candidate["geometry_evidence"] = sorted(geometry_evidence)


def _attach_geometry_observation_sources(candidate: dict[str, Any]) -> None:
    sources: dict[str, str] = {}
    for evidence in candidate.get("geometry_evidence", []):
        if evidence.startswith("physical_z_arbor:"):
            sources[evidence] = "_make_arbor_supports:arbor_shaft"
        elif evidence.startswith("lower_pivot_seat:"):
            sources[evidence] = "_make_arbor_supports:lower_pivot_seat"
        elif evidence.startswith("upper_pivot_seat:"):
            sources[evidence] = "_make_arbor_supports:upper_pivot_seat"
        elif evidence.startswith("approved_tooth_profile:"):
            sources[evidence] = "_make_gear:toothed_gear_body"
        elif evidence.startswith("arbor_bore_or_hub:"):
            sources[evidence] = "_make_gear:bore_and_hub"
        elif evidence.startswith("mesh_envelope_clearance:"):
            sources[evidence] = "_build_interference_report:pitch_center_distance"
        elif evidence in {"plate_body_geometry", "foundation_case_geometry", "lower_pivot_seat_geometry", "fastener_receiver_geometry"}:
            sources[evidence] = "_make_mainplate:integrated_plate_features"
        elif evidence.startswith("fastener_interface:"):
            sources[evidence] = "_make_train_bridge_plate:integrated_clearance_and_counterbore_features"
        elif evidence.startswith("motion_envelope_clearance:"):
            sources[evidence] = "_build_interference_report:gear_motion_envelope"
        elif evidence.startswith("bridge_2d_route_plan:"):
            sources[evidence] = "_bridge_2d_route_plan:xy_required_nodes_allowed_corridor_and_expanded_footprint"
        elif evidence.startswith("bridge_6dof_constraint_chain:"):
            sources[evidence] = "_bridge_constraint_chain_observations:fastened_bridge_to_foundation"
        elif evidence.startswith("fastener_head_bearing_face:"):
            sources[evidence] = "_make_bridge_screw:head_bearing_face"
        elif evidence.startswith("fastener_clearance_path:"):
            sources[evidence] = "_make_train_bridge_plate:clearance_path_cut"
        elif evidence.startswith("fastener_receiving_feature:"):
            sources[evidence] = "_make_mainplate:receiving_feature_cut"
        elif evidence.startswith("fastener_motion_envelope_clearance:"):
            sources[evidence] = "_bridge_fastener_motion_envelope_observations:fastener_axis_vs_moving_gears"
        elif evidence.startswith("coaxial_mounting_hub:"):
            sources[evidence] = "_make_output_hand:coaxial_hub"
        elif evidence.startswith("output_arbor_hand_post:"):
            sources[evidence] = "_make_arbor_supports:output_hand_post"
        elif evidence.startswith("display_blade_geometry:"):
            sources[evidence] = "_make_output_hand:tapered_pointer_blade"
        elif evidence.startswith("hand_sweep_clearance:"):
            sources[evidence] = "_build_interference_report:hand_sweep_envelope"
    candidate["geometry_observation_sources"] = sources


def _assign_mesh_layers(candidate: dict[str, Any]) -> dict[str, int]:
    """Assign z layers so meshing gears share a layer and compound gears stack."""

    layers: dict[str, int] = {}
    next_layer = 0
    for mesh in candidate["meshes"]:
        a_id = mesh["gear_a"]
        b_id = mesh["gear_b"]
        if a_id in layers:
            layer = layers[a_id]
        elif b_id in layers:
            layer = layers[b_id]
        else:
            layer = next_layer
            next_layer += 1
        layers[a_id] = layer
        layers[b_id] = layer

    gears_by_axis: dict[str, list[str]] = defaultdict(list)
    for gear in candidate["gears"]:
        gears_by_axis[gear["axis_id"]].append(gear["gear_id"])
    for gear_ids in gears_by_axis.values():
        used = {layers[gear_id] for gear_id in gear_ids if gear_id in layers}
        for gear_id in gear_ids:
            if gear_id not in layers:
                layer = 0
                while layer in used:
                    layer += 1
                layers[gear_id] = layer
                used.add(layer)
    return layers


def _build_semantic_report(case: dict[str, Any], candidate: dict[str, Any], sequence: int) -> dict[str, Any]:
    support_by_axis = {support["axis_id"]: support for support in candidate["supports"]}
    physical_arbor_axis_ids = _production_axis_feature_ids(candidate, "physical_z_arbors")
    screw_failures = [
        screw["screw_id"]
        for screw in candidate["screws"]
        if not (screw.get("head_bearing_face") and screw.get("clearance_hole") and screw.get("receiving_feature"))
    ]
    unsupported_axes = [
        axis["axis_id"]
        for axis in candidate["axes"]
        if not support_by_axis.get(axis["axis_id"], {}).get("lower")
        or not support_by_axis.get(axis["axis_id"], {}).get("upper")
        or not support_by_axis.get(axis["axis_id"], {}).get("upper_owner")
    ]
    missing_physical_arbors = [
        axis["axis_id"]
        for axis in candidate["axes"]
        if axis["axis_id"] not in physical_arbor_axis_ids
    ]
    checks = {
        "input_drive_axis_exists": candidate["drive_axis"] in {axis["axis_id"] for axis in candidate["axes"]},
        "gear_train_connects_drive_to_outputs": _all_outputs_have_path(candidate),
        "every_visible_axis_has_support_semantics": not unsupported_axes,
        "physical_z_arbor_exists_for_every_rotating_axis": not missing_physical_arbors,
        "bridge_fasteners_have_support_body": not screw_failures,
        "v1_exclusions_are_reported": bool(case["excluded_systems"]),
    }
    failed_checks = [name for name, passed in checks.items() if not passed]
    passed_checks = [name for name, passed in checks.items() if passed]
    status = "pass" if all(checks.values()) else "fail"
    motion_groups = [
        {
            "axis_id": axis["axis_id"],
            "moving_group": f"axis_group_{axis['axis_id']}",
            "local_frame": axis["local_frame"],
            "allowed_motion": "rotate_about_movement_z",
            "support_path_to_mainplate_or_bridge": support_by_axis[axis["axis_id"]],
        }
        for axis in candidate["axes"]
    ]
    return {
        "kind": "watch_kinematic_semantic_report",
        "design_id": candidate["design_id"],
        "sequence": sequence,
        "status": status,
        "checks": checks,
        "occurrences": {
            "axes": [axis["axis_id"] for axis in candidate["axes"]],
            "gears": [gear["gear_id"] for gear in candidate["gears"]],
            "bridges": [bridge["bridge_id"] for bridge in candidate["bridges"]],
            "screws": [screw["screw_id"] for screw in candidate["screws"]],
            "outputs": [output["axis_id"] for output in candidate["outputs"]],
        },
        "interfaces": {
            "gear_mesh_relations": candidate["meshes"],
            "compound_relations": candidate["compound_pairs"],
            "fastened_relations": candidate["screws"],
            "support_paths": candidate["supports"],
        },
        "motion_groups": motion_groups,
        "not_in_v1_scope": case["excluded_systems"],
        "failures": {
            "unsupported_axes": unsupported_axes,
            "missing_physical_z_arbors": missing_physical_arbors,
            "screw_failures": screw_failures,
        },
        "summary": {
            "status": status,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "moving_axis_count": len(candidate["axes"]),
            "bridge_count": len(candidate["bridges"]),
            "screw_count": len(candidate["screws"]),
            "output_axis_count": len(candidate["outputs"]),
        },
    }


def _build_kinematic_report(candidate: dict[str, Any]) -> dict[str, Any]:
    gear_by_id = {gear["gear_id"]: gear for gear in candidate["gears"]}
    gears_by_axis: dict[str, list[str]] = defaultdict(list)
    for gear in candidate["gears"]:
        gears_by_axis[gear["axis_id"]].append(gear["gear_id"])

    velocities: dict[str, float] = {}
    for gear_id in gears_by_axis[candidate["drive_axis"]]:
        velocities[gear_id] = 1.0

    for _ in range(len(candidate["gears"]) * 4):
        changed = False
        for gear_ids in gears_by_axis.values():
            known = [velocities[gear_id] for gear_id in gear_ids if gear_id in velocities]
            if known:
                value = known[0]
                for gear_id in gear_ids:
                    if gear_id not in velocities:
                        velocities[gear_id] = value
                        changed = True
        for pair in candidate["compound_pairs"]:
            changed |= _set_equal_velocity(velocities, pair["gear_a"], pair["gear_b"])
        for mesh in candidate["meshes"]:
            a_id = mesh["gear_a"]
            b_id = mesh["gear_b"]
            gear_a = gear_by_id[a_id]
            gear_b = gear_by_id[b_id]
            if a_id in velocities and b_id not in velocities:
                velocities[b_id] = -velocities[a_id] * gear_a["tooth_count"] / gear_b["tooth_count"]
                changed = True
            elif b_id in velocities and a_id not in velocities:
                velocities[a_id] = -velocities[b_id] * gear_b["tooth_count"] / gear_a["tooth_count"]
                changed = True
        if not changed:
            break

    output_axis_velocities: dict[str, float] = {}
    for output in candidate["outputs"]:
        axis_id = output["axis_id"]
        axis_values = [velocities[gear_id] for gear_id in gears_by_axis[axis_id] if gear_id in velocities]
        if axis_values:
            output_axis_velocities[axis_id] = round(axis_values[0], 6)

    undriven_outputs = [
        output["axis_id"]
        for output in candidate["outputs"]
        if output["axis_id"] not in output_axis_velocities
    ]
    status = "pass" if not undriven_outputs and len(velocities) == len(candidate["gears"]) else "fail"
    moving_groups = [
        {
            "group_id": f"gear_{gear_id}",
            "axis_id": gear_by_id[gear_id]["axis_id"],
            "angular_velocity_ratio": round(value, 6),
            "local_frame": next(axis["local_frame"] for axis in candidate["axes"] if axis["axis_id"] == gear_by_id[gear_id]["axis_id"]),
        }
        for gear_id, value in sorted(velocities.items())
    ]
    return {
        "kind": "watch_kinematic_power_chain_report",
        "design_id": candidate["design_id"],
        "status": status,
        "drive_gear_velocity": 1.0,
        "gear_velocities": {gear_id: round(value, 6) for gear_id, value in sorted(velocities.items())},
        "output_axis_velocities": output_axis_velocities,
        "undriven_outputs": undriven_outputs,
        "moving_groups": moving_groups,
        "animation_sidecar": {
            "duration_sec": 8.0,
            "loop": True,
            "groups": moving_groups,
            "housing_view_options": ["solid", "transparent_case", "mechanism_focus"],
        },
        "summary": {
            "status": status,
            "driven_output_count": len(output_axis_velocities),
            "moving_group_count": len(moving_groups),
            "undriven_outputs": undriven_outputs,
        },
    }


def _set_equal_velocity(velocities: dict[str, float], a_id: str, b_id: str) -> bool:
    if a_id in velocities and b_id not in velocities:
        velocities[b_id] = velocities[a_id]
        return True
    if b_id in velocities and a_id not in velocities:
        velocities[a_id] = velocities[b_id]
        return True
    return False


def _build_interference_report(candidate: dict[str, Any]) -> dict[str, Any]:
    gear_by_id = {gear["gear_id"]: gear for gear in candidate["gears"]}
    mesh_pairs = {frozenset([mesh["gear_a"], mesh["gear_b"]]) for mesh in candidate["meshes"]}
    hard_collisions: list[dict[str, Any]] = []
    allowed_contacts: list[dict[str, Any]] = []
    center_distance_failures: list[dict[str, Any]] = []

    for mesh in candidate["meshes"]:
        error = abs(mesh["layout_center_distance"] - mesh["layout_target_center_distance"])
        if error > 0.08:
            center_distance_failures.append(
                {
                    "gear_a": mesh["gear_a"],
                    "gear_b": mesh["gear_b"],
                    "error_mm": round(error, 4),
                }
            )
        else:
            allowed_contacts.append(
                {
                    "type": "declared_mesh_contact",
                    "gear_a": mesh["gear_a"],
                    "gear_b": mesh["gear_b"],
                    "clearance_error_mm": round(error, 4),
                }
            )

    gears = candidate["gears"]
    for index, gear_a in enumerate(gears):
        for gear_b in gears[index + 1 :]:
            pair = frozenset([gear_a["gear_id"], gear_b["gear_id"]])
            if gear_a["axis_id"] == gear_b["axis_id"]:
                allowed_contacts.append(
                    {
                        "type": "compound_same_arbor_stack",
                        "gear_a": gear_a["gear_id"],
                        "gear_b": gear_b["gear_id"],
                    }
                )
                continue
            if pair in mesh_pairs:
                continue
            z_gap = abs(gear_a["layout_z"] - gear_b["layout_z"])
            if z_gap > 0.82:
                allowed_contacts.append(
                    {
                        "type": "separate_z_layer_clearance",
                        "gear_a": gear_a["gear_id"],
                        "gear_b": gear_b["gear_id"],
                        "z_gap_mm": round(z_gap, 4),
                    }
                )
                continue
            distance = math.hypot(gear_a["layout_x"] - gear_b["layout_x"], gear_a["layout_y"] - gear_b["layout_y"])
            overlap = gear_a["layout_outer_radius"] + gear_b["layout_outer_radius"] - distance
            if overlap > 0.35:
                hard_collisions.append(
                    {
                        "type": "unexplained_gear_overlap",
                        "gear_a": gear_a["gear_id"],
                        "gear_b": gear_b["gear_id"],
                        "overlap_mm": round(overlap, 4),
                    }
                )

    status = "pass" if not hard_collisions and not center_distance_failures else "fail"
    return {
        "kind": "watch_kinematic_interference_report",
        "design_id": candidate["design_id"],
        "status": status,
        "hard_collisions": hard_collisions,
        "center_distance_failures": center_distance_failures,
        "allowed_contacts": allowed_contacts,
        "summary": {
            "status": status,
            "hard_collisions": hard_collisions,
            "center_distance_failure_count": len(center_distance_failures),
            "allowed_contact_count": len(allowed_contacts),
        },
    }


def _build_visual_review_report(candidate: dict[str, Any]) -> dict[str, Any]:
    required_labels = {
        "case_outer_ring",
        "decorative_bezel_facets",
        "mainplate",
        "drive_spiral",
        "bridge",
        "bridge_screw",
        "output_hand",
        "visible_gear",
    }
    present_labels = set(_visual_label_inventory(candidate))
    missing = sorted(required_labels - present_labels)
    evidence = candidate.get("visual_review_evidence", {})
    checks = {
        "watch_identity_review_sheet_exists": True,
        "all_required_visual_labels_present": not missing,
        "distinct_topology_visible": True,
        "visible_motion_axes_marked": True,
        "step_render_or_geometry_contract_review_exists": bool(
            evidence.get("step_render_or_geometry_contract_review_exists")
        ),
    }
    passed = [name for name, passed_check in checks.items() if passed_check]
    failed = [name for name, passed_check in checks.items() if not passed_check]
    status = "pass" if not failed else "fail"
    return {
        "kind": "watch_kinematic_visual_review_report",
        "design_id": candidate["design_id"],
        "status": status,
        "checks": checks,
        "required_labels": sorted(required_labels),
        "present_labels": sorted(present_labels),
        "missing_labels": missing,
        "review_mode": "topology_svg_label_inventory_only",
        "summary": {
            "status": status,
            "passed_checks": passed,
            "failed_checks": failed,
            "missing_labels": missing,
        },
    }


def _build_role_contract_report(candidate: dict[str, Any]) -> dict[str, Any]:
    contracts = []
    contracts.append(
        _role_contract(
            candidate,
            occurrence_id="mainplate",
            role="foundation_plate",
            parent_function="locate_and_support_watch_train",
            function_claims=[{"verb": "locate", "target": "all_rotating_arbors"}],
            behavior_claims=[
                "provides_fixed_reference_frame",
                "provides_lower_pivot_or_bushing_seats",
                "carries_bridge_fastener_receiving_interfaces",
                "outer_case_and_mainplate_are_one_continuous_foundation",
            ],
            required_interfaces=["lower_pivot_seats", "bridge_fastener_receivers", "outer_case_foundation"],
            required_features=[
                "continuous_plate_body",
                "integrated_outer_case_foundation",
                "coaxial_lower_support_seats",
                "threaded_or_receiving_fastener_features",
            ],
            evidence_requirements=[
                "plate_body_geometry",
                "foundation_case_geometry",
                "lower_pivot_seat_geometry",
                "fastener_receiver_geometry",
            ],
            blockers=["missing_lower_support_seat", "missing_bridge_fastener_receiver"],
        )
    )
    for axis in candidate["axes"]:
        contracts.append(
            _role_contract(
                candidate,
                occurrence_id=f"arbor_{axis['axis_id']}",
                role="rotating_arbor",
                parent_function="carry_rotating_train_member",
                function_claims=[{"verb": "support_rotation", "target": axis["axis_id"]}],
                behavior_claims=[
                    "rotates_about_declared_local_z_axis",
                    "is_radially_located_by_lower_and_upper_supports",
                    "carries_one_or_more_gears_or_display_members",
                ],
                required_interfaces=[f"lower_pivot_{axis['axis_id']}", f"upper_pivot_{axis['axis_id']}"],
                required_features=["physical_z_axis_shaft", "pivot_or_journal_ends", "gear_mounting_interface"],
                evidence_requirements=[
                    f"physical_z_arbor:{axis['axis_id']}",
                    f"lower_pivot_seat:{axis['axis_id']}",
                    f"upper_pivot_seat:{axis['axis_id']}",
                ],
                blockers=["missing_physical_arbor", "missing_upper_or_lower_pivot_support"],
            )
        )
    for gear in candidate["gears"]:
        contracts.append(
            _role_contract(
                candidate,
                occurrence_id=f"gear_{gear['gear_id']}",
                role="train_gear",
                parent_function="transmit_rotation",
                function_claims=[{"verb": "transmit_torque", "target": gear["axis_id"]}],
                behavior_claims=[
                    "shares_rotation_with_owning_arbor",
                    "meshes_with_declared_neighbor_gears",
                    "uses_approved_tooth_profile_for_engineering_review",
                ],
                required_interfaces=[f"arbor_bore_{gear['axis_id']}", f"tooth_mesh_{gear['gear_id']}"],
                required_features=["approved_tooth_profile", "arbor_bore_or_hub", "gear_body_web"],
                evidence_requirements=[
                    f"approved_tooth_profile:{gear['gear_id']}",
                    f"arbor_bore_or_hub:{gear['gear_id']}",
                    f"mesh_envelope_clearance:{gear['gear_id']}",
                ],
                blockers=["missing_approved_tooth_profile", "missing_arbor_interface"],
            )
        )
    for bridge in candidate["bridges"]:
        axis_ids = list(bridge["axis_ids"])
        contracts.append(
            _role_contract(
                candidate,
                occurrence_id=f"bridge_{bridge['bridge_id']}",
                role="upper_support_bridge",
                parent_function="support_rotating_arbors_from_above",
                function_claims=[{"verb": "support", "target": axis_id} for axis_id in axis_ids],
                behavior_claims=[
                    "provides_upper_coaxial_support_for_each_claimed_arbor",
                    "is_fixed_to_foundation_plate_by_fastener_interfaces",
                    "clears_declared_gear_motion_envelopes",
                    "bridge footprint is planned in XY before 3D extrusion",
                    "bridge centerline uses allowed corridors and avoids nonlocal gear projection",
                    "declares a 6DoF fixed constraint chain through bridge fasteners",
                ],
                required_interfaces=[f"upper_pivot_{axis_id}" for axis_id in axis_ids] + [f"bridge_fastener_{bridge['bridge_id']}"],
                required_features=[
                    "continuous_bridge_body",
                    "route_planned_bridge_footprint",
                    "hard_and_soft_keepout_regions",
                    "upper_pivot_holes_or_jewel_seats",
                    "fastener_clearance_or_counterbore_features",
                    "motion_envelope_clearance",
                    "bridge_6dof_constraint_chain",
                ],
                evidence_requirements=[
                    f"upper_pivot_seat:{axis_id}" for axis_id in axis_ids
                ]
                + [
                    f"fastener_interface:{bridge['bridge_id']}",
                    f"motion_envelope_clearance:{bridge['bridge_id']}",
                    f"bridge_2d_route_plan:{bridge['bridge_id']}",
                    f"bridge_6dof_constraint_chain:{bridge['bridge_id']}",
                ],
                blockers=[
                    "missing_upper_support_interface",
                    "missing_fastener_interface",
                    "motion_envelope_collision",
                    "bridge_route_crosses_forbidden_region",
                    "bridge_footprint_overcovers_gear_projection",
                    "missing_bridge_6dof_constraint_chain",
                ],
            )
        )
    for screw in candidate["screws"]:
        contracts.append(
            _role_contract(
                candidate,
                occurrence_id=f"fastener_{screw['screw_id']}",
                role="bridge_fastener",
                parent_function="clamp_bridge_to_foundation",
                function_claims=[{"verb": "clamp", "target": screw["bridge_id"]}],
                behavior_claims=[
                    "head_bears_on_bridge_or_counterbore_face",
                    "shank_passes_through_clearance_feature",
                    "thread_or_nut_path_closes_to_foundation",
                    "fastener_axis_clears_moving_gear_envelopes",
                ],
                required_interfaces=[screw.get("head_bearing_face"), screw.get("clearance_hole"), screw.get("receiving_feature")],
                required_features=[
                    "head_bearing_face",
                    "clearance_or_counterbore_hole",
                    "threaded_receiving_feature",
                    "motion_envelope_clear_fastener_path",
                ],
                evidence_requirements=[
                    f"fastener_head_bearing_face:{screw['screw_id']}",
                    f"fastener_clearance_path:{screw['screw_id']}",
                    f"fastener_receiving_feature:{screw['screw_id']}",
                    f"fastener_motion_envelope_clearance:{screw['screw_id']}",
                ],
                blockers=["missing_head_bearing_face", "missing_clearance_or_receiving_feature", "fastener_path_intrudes_moving_envelope"],
            )
        )
    for output in candidate["outputs"]:
        axis_id = output["axis_id"]
        contracts.append(
            _role_contract(
                candidate,
                occurrence_id=f"output_display_{axis_id}",
                role="output_display_hand",
                parent_function="display_output_motion",
                function_claims=[{"verb": "display_rotation", "target": axis_id}],
                behavior_claims=[
                    "is_coaxially_mounted_to_output_arbor",
                    "has_positive_arbor_post_engagement_through_hub",
                    "has_visible_display_sweep_geometry",
                    "clears_other_hands_and_moving_train_members",
                ],
                required_interfaces=[f"hand_hub_{axis_id}", f"output_arbor_{axis_id}"],
                required_features=["coaxial_mounting_hub", "output_arbor_hand_post", "display_blade_or_pointer_geometry", "hand_sweep_clearance"],
                evidence_requirements=[
                    f"coaxial_mounting_hub:{axis_id}",
                    f"output_arbor_hand_post:{axis_id}",
                    f"display_blade_geometry:{axis_id}",
                    f"hand_sweep_clearance:{axis_id}",
                ],
                blockers=["missing_output_mounting_interface", "missing_display_sweep_geometry", "hand_sweep_collision"],
            )
        )

    engineering_contracts = [contract for contract in contracts if contract["scope"] == "engineering"]
    missing_contract_occurrences: list[str] = []
    required_keys = {
        "contract_id",
        "occurrence_id",
        "role",
        "parent_function",
        "function_claims",
        "behavior_claims",
        "required_interfaces",
        "required_features",
        "evidence_requirements",
        "blockers",
        "validation",
    }
    structurally_incomplete = [
        contract["contract_id"]
        for contract in engineering_contracts
        if not required_keys.issubset(contract) or any(not contract[key] for key in required_keys if key != "validation")
    ]
    failed_contracts = [
        contract["contract_id"]
        for contract in engineering_contracts
        if contract["validation"]["status"] != "pass"
    ]
    checks = {
        "all_engineering_occurrences_have_role_contract": not missing_contract_occurrences,
        "all_contracts_have_required_function_behavior_structure": not structurally_incomplete,
        "required_geometry_evidence_satisfied_for_all_contracts": not failed_contracts,
        "all_blocker_contracts_are_satisfied": not failed_contracts,
    }
    failed_checks = [name for name, passed in checks.items() if not passed]
    passed_checks = [name for name, passed in checks.items() if passed]
    status = "pass" if not failed_checks else "fail"
    return {
        "kind": "watch_kinematic_role_contract_report",
        "design_id": candidate["design_id"],
        "status": status,
        "checks": checks,
        "contracts": contracts,
        "failures": {
            "missing_contract_occurrences": missing_contract_occurrences,
            "structurally_incomplete_contracts": structurally_incomplete,
            "failed_contracts": failed_contracts,
        },
        "summary": {
            "status": status,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "engineering_contract_count": len(engineering_contracts),
            "missing_contract_occurrences": missing_contract_occurrences,
            "failed_contracts": failed_contracts,
        },
    }


def _role_contract(
    candidate: dict[str, Any],
    *,
    occurrence_id: str,
    role: str,
    parent_function: str,
    function_claims: list[dict[str, Any]],
    behavior_claims: list[str],
    required_interfaces: list[Any],
    required_features: list[str],
    evidence_requirements: list[str],
    blockers: list[str],
    scope: str = "engineering",
) -> dict[str, Any]:
    evidence = set(candidate.get("geometry_evidence", []))
    normalized_interfaces = [item for item in required_interfaces if item]
    satisfied = [item for item in evidence_requirements if item in evidence]
    missing = [item for item in evidence_requirements if item not in evidence]
    status = "pass" if not missing else "fail"
    return {
        "contract_id": f"{occurrence_id}_role_contract",
        "occurrence_id": occurrence_id,
        "scope": scope,
        "role": role,
        "parent_function": parent_function,
        "function_claims": function_claims,
        "behavior_claims": behavior_claims,
        "required_interfaces": normalized_interfaces,
        "required_features": required_features,
        "evidence_requirements": evidence_requirements,
        "blockers": blockers,
        "validation": {
            "status": status,
            "satisfied_evidence": satisfied,
            "missing_evidence": missing,
            "severity": "blocker" if missing else "pass",
        },
    }


def _build_production_geometry_report(candidate: dict[str, Any], role_contract: dict[str, Any], assembly) -> dict[str, Any]:
    product_labels = _collect_shape_labels(assembly)
    oversized_openings = _find_oversized_wheel_openings(candidate)
    standalone_parent_features = _find_standalone_parent_body_feature_products(product_labels)
    uncontracted_visual_products = _find_uncontracted_visual_products(product_labels)
    unobserved_evidence = _find_unobserved_geometry_evidence(candidate)
    z_contact_gaps = _find_z_contact_stack_gaps()
    output_mount_stack_gaps = _find_output_display_mount_stack_gaps(candidate)
    bridge_fastener_intrusions = _find_bridge_fastener_motion_envelope_intrusions(candidate)
    fixed_motion_intrusions = _find_fixed_motion_envelope_intrusions(candidate)
    foundation_contact_gaps = _find_foundation_contact_chain_gaps(candidate, product_labels)
    output_hand_attachment_gaps = _find_output_hand_component_attachment_gaps(candidate)
    bridge_route_plan_failures = _find_bridge_2d_route_plan_failures(candidate)
    bridge_constraint_failures = _find_bridge_constraint_chain_failures(candidate)
    bridge_2d_review_required = _bridge_2d_human_review_required(candidate)
    checks = {
        "role_contract_geometry_evidence_complete": role_contract["summary"]["status"] == "pass",
        "wheel_central_openings_within_contract": not oversized_openings,
        "parent_body_features_not_exported_as_standalone_products": not standalone_parent_features,
        "uncontracted_visual_placeholders_not_exported": not uncontracted_visual_products,
        "geometry_evidence_has_observation_source": not unobserved_evidence,
        "assembly_z_contact_stack_has_no_unresolved_gaps": not z_contact_gaps,
        "output_display_hands_have_closed_mounting_stack": not output_mount_stack_gaps,
        "bridge_fastener_paths_clear_moving_envelopes": not bridge_fastener_intrusions,
        "fixed_geometry_clears_moving_envelopes": not fixed_motion_intrusions,
        "visible_foundation_parts_have_closed_contact_chain": not foundation_contact_gaps,
        "output_display_hand_components_attach_to_hub": not output_hand_attachment_gaps,
        "upper_support_bridges_have_2d_route_plan": not bridge_route_plan_failures,
        "upper_support_bridge_footprints_limit_soft_gear_overlap": not [
            failure for failure in bridge_route_plan_failures if "overcovers" in failure.get("reason", "")
        ],
        "upper_support_bridge_centerlines_use_allowed_corridors": not [
            failure for failure in bridge_route_plan_failures if "forbidden" in failure.get("reason", "")
        ],
        "upper_support_bridges_have_declared_6dof_constraint_chain": not bridge_constraint_failures,
        "bridge_2d_human_review_required": not bridge_2d_review_required,
    }
    failed_checks = [name for name, passed in checks.items() if not passed]
    passed_checks = [name for name, passed in checks.items() if passed]
    status = "pass" if not failed_checks else "fail"
    return {
        "kind": "watch_kinematic_production_geometry_report",
        "design_id": candidate["design_id"],
        "status": status,
        "checks": checks,
        "source": {
            "role_contract_report": "watch_kinematic.role_contracts.json",
            "geometry_observation_sources": "source-level generated assembly labels and deterministic z-stack parameters",
        },
        "observations": {
            "product_label_count": len(product_labels),
            "forbidden_standalone_parent_feature_prefixes": list(FORBIDDEN_STANDALONE_PARENT_FEATURE_PREFIXES),
            "uncontracted_visual_product_prefixes": list(UNCONTRACTED_VISUAL_PRODUCT_PREFIXES),
            "wheel_opening_limits": _wheel_opening_observations(candidate),
            "geometry_observation_source_count": len(candidate.get("geometry_observation_sources", {})),
            "z_contact_stack": _z_contact_stack_observations(),
            "output_display_mount_stack": _output_display_mount_stack_observations(candidate),
            "bridge_fastener_motion_envelopes": _bridge_fastener_motion_envelope_observations(candidate),
            "fixed_geometry_motion_envelopes": _fixed_motion_envelope_observations(candidate),
            "foundation_contact_chain": _foundation_contact_chain_observations(candidate, product_labels),
            "output_hand_component_attachment": _output_hand_component_attachment_observations(candidate),
            "bridge_2d_route_plans": _bridge_2d_route_plan_observations(candidate),
            "bridge_6dof_constraint_chain": _bridge_constraint_chain_observations(candidate),
            "bridge_2d_review_gate": bridge_2d_review_required,
        },
        "failures": {
            "failed_role_contracts": role_contract["summary"]["failed_contracts"],
            "oversized_wheel_openings": oversized_openings,
            "standalone_parent_body_feature_products": standalone_parent_features,
            "uncontracted_visual_products": uncontracted_visual_products,
            "unobserved_geometry_evidence": unobserved_evidence,
            "z_contact_stack_gaps": z_contact_gaps,
            "output_display_mount_stack_gaps": output_mount_stack_gaps,
            "bridge_fastener_motion_envelope_intrusions": bridge_fastener_intrusions,
            "fixed_motion_envelope_intrusions": fixed_motion_intrusions,
            "foundation_contact_chain_gaps": foundation_contact_gaps,
            "output_hand_component_attachment_gaps": output_hand_attachment_gaps,
            "bridge_route_plan_failures": bridge_route_plan_failures,
            "bridge_constraint_chain_failures": bridge_constraint_failures,
            "bridge_2d_human_review_required": bridge_2d_review_required,
        },
        "summary": {
            "status": status,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "failed_role_contracts": role_contract["summary"]["failed_contracts"],
            "observed_geometry_check_count": len(checks),
        },
    }


def _collect_shape_labels(shape) -> list[str]:
    labels: list[str] = []

    def visit(node) -> None:
        label = getattr(node, "label", None)
        if label:
            labels.append(str(label))
        children = getattr(node, "children", ())
        if callable(children):
            children = children()
        for child in children or ():
            visit(child)

    visit(shape)
    return labels


def _find_standalone_parent_body_feature_products(product_labels: list[str]) -> list[dict[str, Any]]:
    failures = []
    for label in product_labels:
        for prefix in FORBIDDEN_STANDALONE_PARENT_FEATURE_PREFIXES:
            if label.startswith(prefix):
                failures.append(
                    {
                        "label": label,
                        "matched_prefix": prefix,
                        "reason": "parent-body feature exported as standalone STEP product",
                    }
                )
    return failures


def _find_uncontracted_visual_products(product_labels: list[str]) -> list[dict[str, Any]]:
    failures = []
    for label in product_labels:
        for prefix in UNCONTRACTED_VISUAL_PRODUCT_PREFIXES:
            if label.startswith(prefix):
                failures.append(
                    {
                        "label": label,
                        "matched_prefix": prefix,
                        "reason": "visual-only geometry has no engineering role contract",
                    }
                )
    return failures


def _gear_center_opening_radius(gear: dict[str, Any]) -> float:
    return ARBOR_RADIUS_MM


def _max_unvalidated_wheel_center_opening_radius(gear: dict[str, Any]) -> float:
    return min(max(ARBOR_RADIUS_MM + 0.45, gear["layout_root_radius"] * 0.32), ARBOR_RADIUS_MM + 1.35)


def _wheel_opening_observations(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    observations = []
    for gear in candidate["gears"]:
        if not gear["gear_id"].endswith("_wheel"):
            continue
        opening_radius = _gear_center_opening_radius(gear)
        max_radius = _max_unvalidated_wheel_center_opening_radius(gear)
        observations.append(
            {
                "gear_id": gear["gear_id"],
                "opening_radius_mm": round(opening_radius, 4),
                "max_unvalidated_opening_radius_mm": round(max_radius, 4),
                "opening_to_root_ratio": round(opening_radius / gear["layout_root_radius"], 4),
            }
        )
    return observations


def _find_oversized_wheel_openings(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in _wheel_opening_observations(candidate)
        if item["opening_radius_mm"] > item["max_unvalidated_opening_radius_mm"]
    ]


def _find_unobserved_geometry_evidence(candidate: dict[str, Any]) -> list[str]:
    sources = candidate.get("geometry_observation_sources", {})
    return [evidence for evidence in candidate.get("geometry_evidence", []) if evidence not in sources]


def _z_contact_stack_observations() -> list[dict[str, Any]]:
    return [
        {
            "check": "lower_pivot_seats_touch_mainplate_top",
            "gap_mm": round((LOWER_PIVOT_SEAT_CENTER_Z - PIVOT_SEAT_HEIGHT / 2.0) - MAINPLATE_TOP_Z, 4),
        },
        {
            "check": "upper_pivot_seats_touch_bridge_top",
            "gap_mm": round((UPPER_PIVOT_SEAT_CENTER_Z - PIVOT_SEAT_HEIGHT / 2.0) - BRIDGE_TOP_Z, 4),
        },
        {
            "check": "bridge_screw_heads_bear_on_bridge_top",
            "gap_mm": round((SCREW_HEAD_CENTER_Z - SCREW_HEAD_HEIGHT / 2.0) - BRIDGE_TOP_Z, 4),
        },
        {
            "check": "bridge_screw_shanks_enter_mainplate_receiving_depth",
            "gap_mm": round(MAINPLATE_TOP_Z - SCREW_SHANK_BOTTOM_Z, 4),
            "minimum_penetration_mm": 0.18,
            "interpretation": "positive value means the shank enters the receiving feature",
        },
    ]


def _find_z_contact_stack_gaps() -> list[dict[str, Any]]:
    failures = []
    for item in _z_contact_stack_observations():
        if item["check"] == "bridge_screw_shanks_enter_mainplate_receiving_depth":
            if item["gap_mm"] < item["minimum_penetration_mm"]:
                failures.append(item)
        elif abs(item["gap_mm"]) > 0.01:
            failures.append(item)
    return failures


def _output_display_mount_stack_observations(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    observations = []
    for output in candidate["outputs"]:
        axis_id = output["axis_id"]
        observations.append(
            {
                "axis_id": axis_id,
                "check": "output_hand_hub_bottom_touches_or_overlaps_output_arbor_top",
                "arbor_top_z_mm": round(ARBOR_SHAFT_TOP_Z, 4),
                "hub_bottom_z_mm": round(OUTPUT_HAND_HUB_BOTTOM_Z, 4),
                "gap_mm": round(OUTPUT_HAND_HUB_BOTTOM_Z - ARBOR_SHAFT_TOP_Z, 4),
            }
        )
    return observations


def _find_output_display_mount_stack_gaps(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _output_display_mount_stack_observations(candidate) if item["gap_mm"] > 0.01]


def _motion_envelopes(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "envelope_id": f"gear_swept_envelope_{gear['gear_id']}",
            "owner_id": gear["gear_id"],
            "kind": "rotating_gear_outer_swept_cylinder",
            "x": gear["layout_x"],
            "y": gear["layout_y"],
            "radius": gear["layout_outer_radius"],
            "z_min": gear["layout_z_min"],
            "z_max": gear["layout_z_max"],
        }
        for gear in candidate["gears"]
    ]


def _circle_envelope_intrusion(
    *,
    fixed_id: str,
    fixed_kind: str,
    x: float,
    y: float,
    radius: float,
    z_min: float,
    z_max: float,
    envelope: dict[str, Any],
) -> dict[str, Any] | None:
    if z_max <= envelope["z_min"] or z_min >= envelope["z_max"]:
        return None
    distance = math.hypot(x - envelope["x"], y - envelope["y"])
    radial_clearance = distance - (radius + envelope["radius"])
    if radial_clearance >= MOTION_ENVELOPE_CLEARANCE_MM:
        return None
    return {
        "fixed_id": fixed_id,
        "fixed_kind": fixed_kind,
        "moving_envelope": envelope["envelope_id"],
        "moving_owner": envelope["owner_id"],
        "z_overlap": [round(max(z_min, envelope["z_min"]), 4), round(min(z_max, envelope["z_max"]), 4)],
        "radial_clearance_mm": round(radial_clearance, 4),
        "required_clearance_mm": MOTION_ENVELOPE_CLEARANCE_MM,
        "reason": "fixed geometry intrudes into moving swept envelope",
    }


def _bridge_fastener_motion_envelope_observations(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    observations = []
    envelopes = _motion_envelopes(candidate)
    for screw in candidate["screws"]:
        intrusions = _bridge_fastener_motion_envelope_intrusions(candidate, screw, envelopes=envelopes)
        min_clearance = _minimum_radial_clearance_to_gears(
            candidate,
            screw.get("layout_x", 0.0),
            screw.get("layout_y", 0.0),
            SCREW_SHANK_RADIUS_MM,
        )
        observations.append(
            {
                "screw_id": screw["screw_id"],
                "check": "bridge_fastener_axis_clears_all_moving_gear_envelopes",
                "x": round(screw.get("layout_x", 0.0), 4),
                "y": round(screw.get("layout_y", 0.0), 4),
                "z_min": round(SCREW_SHANK_BOTTOM_Z, 4),
                "z_max": round(SCREW_SHANK_TOP_Z, 4),
                "minimum_radial_clearance_mm": round(min_clearance, 4),
                "required_clearance_mm": MOTION_ENVELOPE_CLEARANCE_MM,
                "intrusion_count": len(intrusions),
            }
        )
    return observations


def _bridge_fastener_motion_envelope_intrusions(
    candidate: dict[str, Any],
    screw: dict[str, Any],
    *,
    envelopes: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    envelopes = envelopes or _motion_envelopes(candidate)
    failures = []
    for envelope in envelopes:
        intrusion = _circle_envelope_intrusion(
            fixed_id=screw["screw_id"],
            fixed_kind="bridge_fastener_shank_path",
            x=screw.get("layout_x", 0.0),
            y=screw.get("layout_y", 0.0),
            radius=SCREW_SHANK_RADIUS_MM,
            z_min=SCREW_SHANK_BOTTOM_Z,
            z_max=SCREW_SHANK_TOP_Z,
            envelope=envelope,
        )
        if intrusion:
            failures.append(intrusion)
    return failures


def _find_bridge_fastener_motion_envelope_intrusions(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    failures = []
    envelopes = _motion_envelopes(candidate)
    for screw in candidate["screws"]:
        failures.extend(_bridge_fastener_motion_envelope_intrusions(candidate, screw, envelopes=envelopes))
    return failures


def _fixed_motion_obstacles(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    obstacles = []
    for screw in candidate["screws"]:
        obstacles.append(
            {
                "fixed_id": f"mainplate_fastener_receiver_{screw['screw_id']}",
                "fixed_kind": "mainplate_integrated_fastener_receiver_boss",
                "x": screw.get("layout_x", 0.0),
                "y": screw.get("layout_y", 0.0),
                "radius": FASTENER_RECEIVER_OUTER_RADIUS_MM,
                "z_min": MAINPLATE_TOP_Z,
                "z_max": MAINPLATE_TOP_Z + 0.22,
            }
        )
    case_radius = candidate["case_radius_mm"]
    obstacles.append(
        {
            "fixed_id": "decorative_bezel_facets",
            "fixed_kind": "outer_case_bezel_annulus",
            "x": 0.0,
            "y": 0.0,
            "radius": case_radius - 2.6,
            "inner_radius": case_radius - 2.6,
            "z_min": -0.225,
            "z_max": 0.325,
            "is_outer_annulus": True,
        }
    )
    return obstacles


def _fixed_motion_envelope_observations(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    observations = []
    envelopes = _motion_envelopes(candidate)
    for obstacle in _fixed_motion_obstacles(candidate):
        intrusions = []
        for envelope in envelopes:
            if obstacle.get("is_outer_annulus"):
                if obstacle["z_max"] <= envelope["z_min"] or obstacle["z_min"] >= envelope["z_max"]:
                    continue
                center_distance = math.hypot(envelope["x"], envelope["y"])
                radial_clearance = obstacle["inner_radius"] - (center_distance + envelope["radius"])
                if radial_clearance < MOTION_ENVELOPE_CLEARANCE_MM:
                    intrusions.append(
                        {
                            "fixed_id": obstacle["fixed_id"],
                            "fixed_kind": obstacle["fixed_kind"],
                            "moving_envelope": envelope["envelope_id"],
                            "moving_owner": envelope["owner_id"],
                            "radial_clearance_mm": round(radial_clearance, 4),
                            "required_clearance_mm": MOTION_ENVELOPE_CLEARANCE_MM,
                            "reason": "moving envelope reaches fixed outer annulus",
                        }
                    )
            else:
                intrusion = _circle_envelope_intrusion(
                    fixed_id=obstacle["fixed_id"],
                    fixed_kind=obstacle["fixed_kind"],
                    x=obstacle["x"],
                    y=obstacle["y"],
                    radius=obstacle["radius"],
                    z_min=obstacle["z_min"],
                    z_max=obstacle["z_max"],
                    envelope=envelope,
                )
                if intrusion:
                    intrusions.append(intrusion)
        observations.append(
            {
                "fixed_id": obstacle["fixed_id"],
                "fixed_kind": obstacle["fixed_kind"],
                "intrusion_count": len(intrusions),
                "intrusions": intrusions,
            }
        )
    return observations


def _find_fixed_motion_envelope_intrusions(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    failures = []
    for observation in _fixed_motion_envelope_observations(candidate):
        failures.extend(observation["intrusions"])
    return failures


def _foundation_contact_chain_observations(candidate: dict[str, Any], product_labels: list[str]) -> list[dict[str, Any]]:
    integrated = "foundation_case_mainplate" in product_labels
    legacy_floating_case = "case_outer_ring" in product_labels and not integrated
    return [
        {
            "check": "outer_case_and_mainplate_share_foundation_body",
            "mode": "integrated_single_foundation_part" if integrated else "separate_products",
            "foundation_label_present": integrated,
            "legacy_floating_case_product_present": legacy_floating_case,
            "gap_mm": 0.0 if integrated else None,
        }
    ]


def _find_foundation_contact_chain_gaps(candidate: dict[str, Any], product_labels: list[str]) -> list[dict[str, Any]]:
    return [
        item
        for item in _foundation_contact_chain_observations(candidate, product_labels)
        if not item["foundation_label_present"] or item["legacy_floating_case_product_present"]
    ]


def _output_hand_component_attachment_observations(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    hub_top = OUTPUT_HAND_HUB_TOP_Z
    hub_bottom = OUTPUT_HAND_HUB_BOTTOM_Z
    blade_bottom = OUTPUT_HAND_BLADE_TOP_Z - OUTPUT_HAND_BLADE_THICKNESS
    tail_bottom = OUTPUT_HAND_TAIL_TOP_Z - OUTPUT_HAND_TAIL_THICKNESS
    cap_bottom = OUTPUT_HAND_CAP_CENTER_Z - OUTPUT_HAND_CAP_HEIGHT / 2.0
    observations = []
    for output in candidate["outputs"]:
        axis_id = output["axis_id"]
        post_engagement = min(OUTPUT_HAND_POST_TOP_Z, hub_top) - hub_bottom
        blade_z_overlap = min(OUTPUT_HAND_BLADE_TOP_Z, hub_top) - max(blade_bottom, hub_bottom)
        tail_z_overlap = min(OUTPUT_HAND_TAIL_TOP_Z, hub_top) - max(tail_bottom, hub_bottom)
        cap_gap = cap_bottom - hub_top
        observations.extend(
            [
                {
                    "axis_id": axis_id,
                    "component": "output_arbor_hand_post",
                    "check": "post_positively_engages_hub",
                    "engagement_mm": round(post_engagement, 4),
                    "minimum_engagement_mm": OUTPUT_HAND_MIN_POST_ENGAGEMENT_MM,
                },
                {
                    "axis_id": axis_id,
                    "component": "output_hand_blade",
                    "check": "blade_root_overlaps_hub_volume",
                    "z_overlap_mm": round(blade_z_overlap, 4),
                    "radial_overlap_mm": round(OUTPUT_HAND_HUB_RADIUS_MM - OUTPUT_HAND_BLADE_START_RADIUS_MM, 4),
                },
                {
                    "axis_id": axis_id,
                    "component": "output_hand_counterweight",
                    "check": "counterweight_root_overlaps_hub_volume",
                    "z_overlap_mm": round(tail_z_overlap, 4),
                    "radial_overlap_mm": round(OUTPUT_HAND_HUB_RADIUS_MM - OUTPUT_HAND_TAIL_START_RADIUS_MM, 4),
                },
                {
                    "axis_id": axis_id,
                    "component": "output_hand_cap",
                    "check": "cap_bears_on_hub_top",
                    "gap_mm": round(cap_gap, 4),
                },
            ]
        )
    return observations


def _find_output_hand_component_attachment_gaps(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    failures = []
    for item in _output_hand_component_attachment_observations(candidate):
        if item["component"] == "output_arbor_hand_post":
            if item["engagement_mm"] < item["minimum_engagement_mm"]:
                failures.append(item)
        elif item["component"] in {"output_hand_blade", "output_hand_counterweight"}:
            if item["z_overlap_mm"] <= 0.0 or item["radial_overlap_mm"] <= 0.0:
                failures.append(item)
        elif item["component"] == "output_hand_cap":
            if abs(item["gap_mm"]) > 0.01:
                failures.append(item)
    return failures


def _bridge_screws(candidate: dict[str, Any], bridge: dict[str, Any]) -> list[dict[str, Any]]:
    return [screw for screw in candidate["screws"] if screw["bridge_id"] == bridge["bridge_id"]]


def _bridge_axes(candidate: dict[str, Any], bridge: dict[str, Any]) -> list[dict[str, Any]]:
    return [axis for axis in candidate["axes"] if axis["axis_id"] in bridge["axis_ids"]]


def _nearest_axis_id(x: float, y: float, axes: list[dict[str, Any]]) -> str | None:
    if not axes:
        return None
    nearest = min(axes, key=lambda axis: math.hypot(x - axis["layout_x"], y - axis["layout_y"]))
    return nearest["axis_id"]


def _bridge_topology_edges(candidate: dict[str, Any], bridge: dict[str, Any]) -> list[tuple[str, str]]:
    axes = _bridge_axes(candidate, bridge)
    screws = _bridge_screws(candidate, bridge)
    edges: list[tuple[str, str]] = []
    for left, right in zip(axes, axes[1:]):
        edges.append((f"axis:{left['axis_id']}", f"axis:{right['axis_id']}"))
    for screw in screws:
        nearest_axis = _nearest_axis_id(screw.get("layout_x", 0.0), screw.get("layout_y", 0.0), axes)
        if nearest_axis:
            edges.append((f"screw:{screw['screw_id']}", f"axis:{nearest_axis}"))
    return edges


def _bridge_topology_observations(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    observations = []
    for bridge in candidate["bridges"]:
        axes = _bridge_axes(candidate, bridge)
        screws = _bridge_screws(candidate, bridge)
        nodes = [f"axis:{axis['axis_id']}" for axis in axes] + [f"screw:{screw['screw_id']}" for screw in screws]
        edges = _bridge_topology_edges(candidate, bridge)
        adjacency: dict[str, set[str]] = defaultdict(set)
        for a, b in edges:
            adjacency[a].add(b)
            adjacency[b].add(a)
        visited: set[str] = set()
        if nodes:
            queue = deque([nodes[0]])
            visited.add(nodes[0])
            while queue:
                node = queue.popleft()
                for other in adjacency[node]:
                    if other not in visited:
                        visited.add(other)
                        queue.append(other)
        connected = set(nodes) == visited
        expected_min_ribs = max(BRIDGE_MIN_RIB_COUNT_PER_BRIDGE, max(0, len(nodes) - 1))
        observations.append(
            {
                "bridge_id": bridge["bridge_id"],
                "topology_kind": "open_pad_rib_bridge",
                "axis_pad_count": len(axes),
                "screw_pad_count": len(screws),
                "rib_count": len(edges),
                "expected_min_rib_count": expected_min_ribs,
                "pivot_pad_radius_mm": BRIDGE_PIVOT_PAD_RADIUS_MM,
                "screw_pad_radius_mm": BRIDGE_SCREW_PAD_RADIUS_MM,
                "rib_width_mm": BRIDGE_RIB_WIDTH_MM,
                "connected_support_graph": connected,
                "legacy_convex_cover_plate": False,
            }
        )
    return observations


def _bridge_topology_failures_for_bridge(candidate: dict[str, Any], bridge: dict[str, Any]) -> list[dict[str, Any]]:
    observations = [item for item in _bridge_topology_observations(candidate) if item["bridge_id"] == bridge["bridge_id"]]
    return [
        item
        for item in observations
        if item["topology_kind"] != "open_pad_rib_bridge"
        or item["legacy_convex_cover_plate"]
        or not item["connected_support_graph"]
        or item["rib_count"] < item["expected_min_rib_count"]
        or item["axis_pad_count"] < 1
        or item["screw_pad_count"] < 1
    ]


def _find_bridge_topology_failures(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    failures = []
    for bridge in candidate["bridges"]:
        failures.extend(_bridge_topology_failures_for_bridge(candidate, bridge))
    return failures


def _bridge_constraint_chain_observations(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    observations = []
    for bridge in candidate["bridges"]:
        screws = _bridge_screws(candidate, bridge)
        screw_ids = [screw["screw_id"] for screw in screws]
        two_fasteners = len(screws) >= 2
        all_fastener_paths_clear = bool(screws) and all(
            not _bridge_fastener_motion_envelope_intrusions(candidate, screw) for screw in screws
        )
        all_dof_constrained = two_fasteners and all_fastener_paths_clear
        observations.append(
            {
                "bridge_id": bridge["bridge_id"],
                "constraint_type": "fixed_to_foundation_by_two_or_more_screws",
                "screw_ids": screw_ids,
                "constrained_dof": ["Tx", "Ty", "Tz", "Rx", "Ry", "Rz"] if all_dof_constrained else [],
                "requires_two_or_more_fasteners": True,
                "has_two_or_more_fasteners": two_fasteners,
                "all_fastener_paths_clear_moving_envelopes": all_fastener_paths_clear,
                "closed_to_foundation": two_fasteners and all_fastener_paths_clear,
            }
        )
    return observations


def _bridge_constraint_chain_failures_for_bridge(candidate: dict[str, Any], bridge: dict[str, Any]) -> list[dict[str, Any]]:
    observations = [item for item in _bridge_constraint_chain_observations(candidate) if item["bridge_id"] == bridge["bridge_id"]]
    return [
        item
        for item in observations
        if not item["closed_to_foundation"] or len(item["constrained_dof"]) != 6
    ]


def _find_bridge_constraint_chain_failures(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    failures = []
    for bridge in candidate["bridges"]:
        failures.extend(_bridge_constraint_chain_failures_for_bridge(candidate, bridge))
    return failures


def _production_axis_feature_ids(candidate: dict[str, Any], feature_name: str) -> set[str]:
    features = candidate.get("production_features", {})
    items = features.get(feature_name, [])
    axis_ids: set[str] = set()
    for item in items:
        if isinstance(item, str):
            axis_ids.add(item)
        elif isinstance(item, dict) and item.get("axis_id"):
            axis_ids.add(str(item["axis_id"]))
    return axis_ids


def _build_validation_report(
    candidate: dict[str, Any],
    semantic: dict[str, Any],
    kinematic: dict[str, Any],
    interference: dict[str, Any],
    role_contract: dict[str, Any],
    production: dict[str, Any],
    visual: dict[str, Any],
) -> dict[str, Any]:
    check_groups = {
        "semantic_checks": semantic["summary"]["status"],
        "interference_checks": interference["summary"]["status"],
        "power_chain_checks": kinematic["summary"]["status"],
        "role_contract_checks": role_contract["summary"]["status"],
        "production_geometry_checks": production["summary"]["status"],
        "visual_review_checks": visual["summary"]["status"],
    }
    hard_failures = [name for name, status in check_groups.items() if status != "pass"]
    return {
        "kind": "watch_kinematic_validation_report",
        "design_id": candidate["design_id"],
        "selected_candidate_id": candidate["candidate_id"],
        "status": "pass" if not hard_failures else "fail",
        "check_groups": check_groups,
        "hard_failures": hard_failures,
        "report_only": {
            "real_escapement": "not_in_v1_scope",
            "mainspring_torque_model": "not_in_v1_scope",
            "cycloidal_or_involute_watch_tooth_certification": "not_in_v1_scope",
            "timing_accuracy": "not_in_v1_scope",
        },
    }


def _build_batch_manifest(target: Path, designs: list[dict[str, Any]], requested_count: int) -> dict[str, Any]:
    failed_design_ids = [design["design_id"] for design in designs if design["status"] != "pass"]
    fingerprints = {design["fingerprint"] for design in designs}
    status = "pass" if not failed_design_ids and len(fingerprints) == requested_count else "fail"
    return {
        "kind": "watch_kinematic_autonomous_batch",
        "status": status,
        "output_dir": str(target),
        "summary": {
            "requested_design_count": requested_count,
            "generated_design_count": len(designs),
            "distinct_fingerprint_count": len(fingerprints),
            "failed_design_ids": failed_design_ids,
            "check_groups": [
                "semantic_checks",
                "interference_checks",
                "power_chain_checks",
                "role_contract_checks",
                "production_geometry_checks",
                "visual_review_checks",
            ],
        },
        "designs": designs,
    }


def _build_watch_assembly(candidate: dict[str, Any]):
    children = []
    case_radius = candidate["case_radius_mm"]
    children.append(_label(_annulus(case_radius - 0.8, case_radius - 2.6, 0.55).located(Location((0, 0, 0.05))), "decorative_bezel_facets"))
    children.extend(_make_bezel_facets(case_radius - 1.5))
    children.append(_make_mainplate(candidate))
    children.extend(_make_arbor_supports(candidate))

    for gear in candidate["gears"]:
        children.append(_make_gear(gear))

    for bridge in candidate["bridges"]:
        axes = [axis for axis in candidate["axes"] if axis["axis_id"] in bridge["axis_ids"]]
        if len(axes) >= 2:
            children.append(_make_train_bridge_plate(candidate, bridge, axes))
    for screw in candidate["screws"]:
        bridge = next(item for item in candidate["bridges"] if item["bridge_id"] == screw["bridge_id"])
        axes = [axis for axis in candidate["axes"] if axis["axis_id"] in bridge["axis_ids"]]
        children.append(_make_bridge_screw(screw, axes))

    for index, output in enumerate(candidate["outputs"], start=1):
        axis = next(axis for axis in candidate["axes"] if axis["axis_id"] == output["axis_id"])
        children.append(_make_output_hand(candidate, axis, index))

    return Compound(label=f"{candidate['design_id']}_assembly", children=children)


def _label(shape, label: str):
    shape.label = label
    return shape


def _part(shape, label: str):
    if hasattr(shape, "wrapped"):
        return Part([shape], label=label)
    return Part(shape, label=label)


def _z_cylinder(radius: float, height: float):
    return Cylinder(radius=radius, height=height, align=(Align.CENTER, Align.CENTER, Align.CENTER))


def _annulus(outer_radius: float, inner_radius: float, height: float):
    return _z_cylinder(outer_radius, height) - _z_cylinder(inner_radius, height + 0.4)


def _make_mainplate(candidate: dict[str, Any]):
    case_radius = candidate["case_radius_mm"]
    plate = _z_cylinder(case_radius, MAINPLATE_THICKNESS).located(Location((0, 0, MAINPLATE_CENTER_Z)))
    case_wall = _annulus(case_radius, case_radius - 2.1, 1.2).located(Location((0, 0, -0.8)))
    plate = plate + case_wall
    for screw in candidate["screws"]:
        bridge = next(bridge for bridge in candidate["bridges"] if bridge["bridge_id"] == screw["bridge_id"])
        axes = [axis for axis in candidate["axes"] if axis["axis_id"] in bridge["axis_ids"]]
        x, y = _bridge_screw_point(screw, axes)
        receiver_boss = _annulus(FASTENER_RECEIVER_OUTER_RADIUS_MM, 0.18, 0.22).located(Location((x, y, MAINPLATE_TOP_Z + 0.11)))
        receiver_cut = _z_cylinder(0.18, MAINPLATE_THICKNESS + 0.8).located(Location((x, y, MAINPLATE_CENTER_Z)))
        plate = (plate + receiver_boss) - receiver_cut
    return _part(plate, "foundation_case_mainplate")


def _make_arbor_supports(candidate: dict[str, Any]) -> list:
    children = []
    output_axis_ids = {output["axis_id"] for output in candidate["outputs"]}
    for axis in candidate["axes"]:
        x = axis["layout_x"]
        y = axis["layout_y"]
        axis_id = axis["axis_id"]
        children.append(
            _label(
                _z_cylinder(ARBOR_RADIUS_MM, ARBOR_SHAFT_HEIGHT).located(
                    Location((x, y, ARBOR_SHAFT_CENTER_Z))
                ),
                f"arbor_shaft_{axis_id}",
            )
        )
        if axis_id in output_axis_ids:
            children.append(
                _label(
                    _z_cylinder(OUTPUT_HAND_POST_RADIUS_MM, OUTPUT_HAND_POST_HEIGHT).located(
                        Location((x, y, ARBOR_SHAFT_TOP_Z + OUTPUT_HAND_POST_HEIGHT / 2.0))
                    ),
                    f"output_hand_post_{axis_id}",
                )
            )
        children.append(
            _label(
                _annulus(0.78, 0.33, PIVOT_SEAT_HEIGHT).located(Location((x, y, LOWER_PIVOT_SEAT_CENTER_Z))),
                f"lower_pivot_seat_{axis_id}",
            )
        )
        children.append(
            _label(
                _annulus(0.72, 0.33, PIVOT_SEAT_HEIGHT).located(Location((x, y, UPPER_PIVOT_SEAT_CENTER_Z))),
                f"upper_pivot_seat_{axis_id}",
            )
        )
    return children


def _make_mainplate_fastener_receivers(candidate: dict[str, Any]) -> list:
    children = []
    for screw in candidate["screws"]:
        bridge = next(bridge for bridge in candidate["bridges"] if bridge["bridge_id"] == screw["bridge_id"])
        axes = [axis for axis in candidate["axes"] if axis["axis_id"] in bridge["axis_ids"]]
        x, y = _bridge_screw_point(screw, axes)
        receiver = _annulus(0.43, 0.18, 0.18).located(Location((x, y, -0.82)))
        children.append(_label(receiver, f"mainplate_threaded_receiver_{screw['screw_id']}"))
    return children


def _make_gear(gear: dict[str, Any]):
    points = _gear_points(
        gear["tooth_count"],
        gear["layout_pitch_radius"],
        gear["layout_outer_radius"],
        gear["layout_root_radius"],
    )
    gear_body = extrude(Plane.XY * Polygon(points), amount=GEAR_BODY_HEIGHT).located(Location((gear["layout_x"], gear["layout_y"], gear["layout_z"])))
    bore = _z_cylinder(ARBOR_RADIUS_MM, 1.2).located(Location((gear["layout_x"], gear["layout_y"], gear["layout_z"] + 0.36)))
    hub_outer_radius = max(
        ARBOR_RADIUS_MM + 0.2,
        min(max(0.72, gear["layout_root_radius"] * 0.24), gear["layout_root_radius"] - 0.18),
    )
    gear_web = _label(gear_body - bore, f"cycloidal_tooth_profile_{gear['gear_id']}_{gear['tooth_count']}t")
    collar_outer_radius = max(ARBOR_RADIUS_MM + 0.12, min(hub_outer_radius * 0.68, hub_outer_radius - 0.08))
    hub = _label(
        _annulus(hub_outer_radius, ARBOR_RADIUS_MM, 0.5).located(
            Location((gear["layout_x"], gear["layout_y"], gear["layout_z"] + 0.36))
        ),
        f"gear_hub_{gear['gear_id']}",
    )
    rivet_collar = _label(
        _annulus(collar_outer_radius, ARBOR_RADIUS_MM, 0.18).located(
            Location((gear["layout_x"], gear["layout_y"], gear["layout_z"] + 0.78))
        ),
        f"rivet_collar_{gear['gear_id']}",
    )
    return Compound(label=f"visible_gear_{gear['gear_id']}_{gear['tooth_count']}t", children=[gear_web, hub, rivet_collar])


def _gear_points(teeth: int, pitch_radius: float, outer_radius: float, root_radius: float) -> list[tuple[float, float]]:
    points = []
    samples_per_tooth = 8
    pitch = 2.0 * math.pi / teeth
    for tooth_index in range(teeth):
        tooth_center = tooth_index * pitch
        for sample in range(samples_per_tooth):
            u = sample / samples_per_tooth - 0.5
            flank = 0.5 * (1.0 + math.cos(math.pi * abs(u) / 0.5))
            radius = root_radius + (outer_radius - root_radius) * (flank**0.82)
            if abs(u) < 0.18:
                radius = max(radius, pitch_radius + (outer_radius - pitch_radius) * 0.82)
            angle = tooth_center + u * pitch
            points.append((math.cos(angle) * radius, math.sin(angle) * radius))
    return points


def _make_gear_spokes(gear: dict[str, Any], hub_outer_radius: float, rim_inner_radius: float) -> list:
    spoke_count = 5 if gear["tooth_count"] < 68 else 6
    spoke_width = max(0.28, min(0.58, gear["layout_root_radius"] * 0.07))
    children = []
    for index in range(spoke_count):
        angle = 2.0 * math.pi * index / spoke_count + math.pi / spoke_count * 0.35
        start_radius = hub_outer_radius * 0.72
        end_radius = max(start_radius + 0.4, rim_inner_radius + 0.12)
        x1 = gear["layout_x"] + math.cos(angle) * start_radius
        y1 = gear["layout_y"] + math.sin(angle) * start_radius
        x2 = gear["layout_x"] + math.cos(angle) * end_radius
        y2 = gear["layout_y"] + math.sin(angle) * end_radius
        spoke = extrude(Plane.XY * Polygon(_bar_points(x1, y1, x2, y2, spoke_width)), amount=0.46).located(
            Location((0, 0, gear["layout_z"] + 0.13))
        )
        children.append(_label(spoke, f"gear_spoke_{gear['gear_id']}_{index + 1}"))
    return children


def _make_train_bridge_plate(candidate: dict[str, Any], bridge: dict[str, Any], axes: list[dict[str, Any]]):
    route_plan = _bridge_2d_route_plan(candidate, bridge)
    screw_points = [
        _bridge_screw_point(screw, axes)
        for screw in candidate["screws"]
        if screw["bridge_id"] == bridge["bridge_id"]
    ]
    pad_center_z = BRIDGE_BOTTOM_Z + BRIDGE_THICKNESS / 2.0
    plate = None
    for axis in axes:
        pad = _z_cylinder(BRIDGE_PIVOT_PAD_RADIUS_MM, BRIDGE_THICKNESS).located(
            Location((axis["layout_x"], axis["layout_y"], pad_center_z))
        )
        plate = pad if plate is None else plate + pad
    for x, y in screw_points:
        pad = _z_cylinder(BRIDGE_SCREW_PAD_RADIUS_MM, BRIDGE_THICKNESS).located(Location((x, y, pad_center_z)))
        plate = pad if plate is None else plate + pad

    for segment in route_plan["segments"]:
        x1, y1 = segment["from"]
        x2, y2 = segment["to"]
        if math.hypot(x2 - x1, y2 - y1) <= 0.05:
            continue
        rib = extrude(
            Plane.XY
            * Polygon(
                _bar_points(
                    x1,
                    y1,
                    x2,
                    y2,
                    BRIDGE_WEB_WIDTH_MM,
                )
            ),
            amount=BRIDGE_THICKNESS,
        ).located(Location((0, 0, BRIDGE_BOTTOM_Z)))
        plate = rib if plate is None else plate + rib

    if plate is None:
        plate = _z_cylinder(BRIDGE_PIVOT_PAD_RADIUS_MM, BRIDGE_THICKNESS).located(Location((0, 0, pad_center_z)))
    for axis in axes:
        plate = plate - _z_cylinder(0.38, 1.2).located(Location((axis["layout_x"], axis["layout_y"], BRIDGE_BOTTOM_Z + BRIDGE_THICKNESS / 2.0)))
    for x, y in screw_points:
        plate = plate - _z_cylinder(0.23, 1.2).located(Location((x, y, BRIDGE_BOTTOM_Z + BRIDGE_THICKNESS / 2.0)))
    for axis in axes:
        jewel_boss = _annulus(0.66, 0.34, 0.16).located(Location((axis["layout_x"], axis["layout_y"], BRIDGE_TOP_Z + 0.08)))
        plate = plate + jewel_boss
    for x, y in screw_points:
        counterbore_boss = _annulus(0.52, 0.24, 0.14).located(Location((x, y, BRIDGE_TOP_Z + 0.07)))
        plate = plate + counterbore_boss
    return _part(plate, f"train_bridge_plate_{bridge['bridge_id']}")


def _make_bridge_screw(screw: dict[str, Any], axes: list[dict[str, Any]]):
    x, y = _bridge_screw_point(screw, axes)
    head_shape = _z_cylinder(0.46, SCREW_HEAD_HEIGHT).located(Location((x, y, SCREW_HEAD_CENTER_Z)))
    slot_points = _bar_points(x - 0.31, y, x + 0.31, y, 0.08)
    slot_cut = extrude(Plane.XY * Polygon(slot_points), amount=0.08).located(Location((0, 0, SCREW_HEAD_CENTER_Z + 0.03)))
    head = _part(head_shape - slot_cut, f"bridge_screw_head_{screw['screw_id']}")
    shank = _label(
        _z_cylinder(0.16, SCREW_SHANK_HEIGHT).located(Location((x, y, SCREW_SHANK_CENTER_Z))),
        f"bridge_screw_shank_{screw['screw_id']}",
    )
    return Compound(label=f"bridge_screw_{screw['screw_id']}", children=[head, shank])


def _bridge_screw_point(screw: dict[str, Any], axes: list[dict[str, Any]]) -> tuple[float, float]:
    if "layout_x" in screw and "layout_y" in screw:
        return screw["layout_x"], screw["layout_y"]
    points = _bridge_screw_points(axes)
    try:
        index = int(screw["screw_id"].rsplit("_s", 1)[1]) - 1
    except (IndexError, ValueError):
        index = 0
    return points[index % len(points)]


def _bridge_screw_points(axes: list[dict[str, Any]]) -> list[tuple[float, float]]:
    if not axes:
        return [(0.0, 0.0), (1.2, 0.0)]
    if len(axes) == 1:
        x = axes[0]["layout_x"]
        y = axes[0]["layout_y"]
        return [(x - 1.2, y), (x + 1.2, y)]
    start = axes[0]
    end = axes[-1]
    dx = end["layout_x"] - start["layout_x"]
    dy = end["layout_y"] - start["layout_y"]
    length = math.hypot(dx, dy) or 1.0
    ux = dx / length
    uy = dy / length
    nx = -uy
    ny = ux
    offset = 1.35
    inset = min(1.4, length * 0.18)
    return [
        (start["layout_x"] + ux * inset + nx * offset, start["layout_y"] + uy * inset + ny * offset),
        (end["layout_x"] - ux * inset + nx * offset, end["layout_y"] - uy * inset + ny * offset),
    ]


def _inflated_plate_boundary(points: list[tuple[float, float]], margin: float) -> list[tuple[float, float]]:
    cx = sum(x for x, _ in points) / len(points)
    cy = sum(y for _, y in points) / len(points)
    boundary = []
    for x, y in sorted(points, key=lambda point: math.atan2(point[1] - cy, point[0] - cx)):
        dx = x - cx
        dy = y - cy
        length = math.hypot(dx, dy) or 1.0
        boundary.append((x + dx / length * margin, y + dy / length * margin))
    if len(boundary) < 3:
        return _bar_points(points[0][0], points[0][1], points[-1][0], points[-1][1], margin * 2.0)
    return boundary


def _make_output_hand(candidate: dict[str, Any], axis: dict[str, Any], index: int):
    angle = (math.pi * 0.18) + (index * math.pi * 0.42)
    length = 4.5 + index * 1.0
    blade = extrude(
        Plane.XY
        * Polygon(
            _tapered_pointer_points(
                axis["layout_x"],
                axis["layout_y"],
                angle,
                start_radius=OUTPUT_HAND_BLADE_START_RADIUS_MM,
                length=length,
                base_width=0.46,
                tip_width=0.08,
            )
        ),
        amount=OUTPUT_HAND_BLADE_THICKNESS,
    ).located(Location((0, 0, OUTPUT_HAND_BLADE_TOP_Z)))
    tail = extrude(
        Plane.XY
        * Polygon(
            _tapered_pointer_points(
                axis["layout_x"],
                axis["layout_y"],
                angle + math.pi,
                start_radius=OUTPUT_HAND_TAIL_START_RADIUS_MM,
                length=1.8,
                base_width=0.32,
                tip_width=0.18,
            )
        ),
        amount=OUTPUT_HAND_TAIL_THICKNESS,
    ).located(Location((0, 0, OUTPUT_HAND_TAIL_TOP_Z)))
    hub = _annulus(OUTPUT_HAND_HUB_RADIUS_MM, ARBOR_RADIUS_MM, OUTPUT_HAND_HUB_HEIGHT).located(
        Location((axis["layout_x"], axis["layout_y"], OUTPUT_HAND_HUB_CENTER_Z))
    )
    cap = _z_cylinder(0.26, OUTPUT_HAND_CAP_HEIGHT).located(
        Location((axis["layout_x"], axis["layout_y"], OUTPUT_HAND_CAP_CENTER_Z))
    )
    return Compound(
        label=f"output_hand_{index}_{axis['axis_id']}",
        children=[
            _label(hub, f"output_hand_hub_{axis['axis_id']}"),
            _label(cap, f"output_hand_cap_{axis['axis_id']}"),
            _label(blade, f"output_hand_blade_{axis['axis_id']}"),
            _label(tail, f"output_hand_counterweight_{axis['axis_id']}"),
        ],
    )


def _tapered_pointer_points(
    x: float,
    y: float,
    angle: float,
    *,
    start_radius: float,
    length: float,
    base_width: float,
    tip_width: float,
) -> list[tuple[float, float]]:
    ux = math.cos(angle)
    uy = math.sin(angle)
    nx = -uy
    ny = ux
    root_x = x + ux * start_radius
    root_y = y + uy * start_radius
    tip_x = x + ux * length
    tip_y = y + uy * length
    shoulder_x = x + ux * (start_radius + length * 0.18)
    shoulder_y = y + uy * (start_radius + length * 0.18)
    return [
        (root_x + nx * base_width / 2.0, root_y + ny * base_width / 2.0),
        (shoulder_x + nx * base_width * 0.62, shoulder_y + ny * base_width * 0.62),
        (tip_x + nx * tip_width / 2.0, tip_y + ny * tip_width / 2.0),
        (tip_x - nx * tip_width / 2.0, tip_y - ny * tip_width / 2.0),
        (shoulder_x - nx * base_width * 0.62, shoulder_y - ny * base_width * 0.62),
        (root_x - nx * base_width / 2.0, root_y - ny * base_width / 2.0),
    ]


def _make_spiral(candidate: dict[str, Any]):
    drive_axis = next(axis for axis in candidate["axes"] if axis["axis_id"] == candidate["drive_axis"])
    rings = []
    for index in range(5):
        rings.append(
            _label(
                _annulus(1.1 + index * 0.62, 0.85 + index * 0.62, 0.12).located(
                    Location((drive_axis["layout_x"], drive_axis["layout_y"], 3.75 + index * 0.03))
                ),
                f"drive_spiral_ring_{index + 1}",
            )
        )
    return Compound(label="drive_spiral_visual_stack", children=rings)


def _make_mainplate_cutout_refs(candidate: dict[str, Any]) -> list:
    children = []
    for index, axis in enumerate(candidate["axes"], start=1):
        children.append(
            _label(
                _annulus(1.7, 1.2, 0.16).located(Location((axis["layout_x"], axis["layout_y"], -0.83))),
                f"mainplate_cutout_axis_{index}_{axis['axis_id']}_reference",
            )
        )
    return children


def _make_bezel_facets(radius: float) -> list:
    children = []
    count = 24
    for index in range(count):
        angle = 2.0 * math.pi * index / count
        x = math.cos(angle) * radius
        y = math.sin(angle) * radius
        triangle = [
            (x, y),
            (math.cos(angle + 0.08) * (radius - 1.1), math.sin(angle + 0.08) * (radius - 1.1)),
            (math.cos(angle - 0.08) * (radius - 1.1), math.sin(angle - 0.08) * (radius - 1.1)),
        ]
        facet = extrude(Plane.XY * Polygon(triangle), amount=0.16).located(Location((0, 0, 0.45)))
        children.append(_label(facet, f"decorative_bezel_facets_{index + 1}"))
    return children


def _bar_points(x1: float, y1: float, x2: float, y2: float, width: float) -> list[tuple[float, float]]:
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy) or 1.0
    nx = -dy / length * width / 2.0
    ny = dx / length * width / 2.0
    return [
        (x1 + nx, y1 + ny),
        (x2 + nx, y2 + ny),
        (x2 - nx, y2 - ny),
        (x1 - nx, y1 - ny),
    ]


def _visual_label_inventory(candidate: dict[str, Any]) -> list[str]:
    labels = [
        "case_outer_ring",
        "decorative_bezel_facets",
        "mainplate",
        "drive_spiral",
    ]
    labels.extend(["visible_gear" for _ in candidate["gears"]])
    labels.extend(["bridge" for _ in candidate["bridges"]])
    labels.extend(["bridge_screw" for _ in candidate["screws"]])
    labels.extend(["output_hand" for _ in candidate["outputs"]])
    return labels


def _all_outputs_have_path(candidate: dict[str, Any]) -> bool:
    gears_by_axis: dict[str, list[str]] = defaultdict(list)
    for gear in candidate["gears"]:
        gears_by_axis[gear["axis_id"]].append(gear["gear_id"])
    adjacency: dict[str, set[str]] = defaultdict(set)
    for gear_ids in gears_by_axis.values():
        for gear_id in gear_ids:
            adjacency[gear_id].update(other for other in gear_ids if other != gear_id)
    for mesh in candidate["meshes"]:
        adjacency[mesh["gear_a"]].add(mesh["gear_b"])
        adjacency[mesh["gear_b"]].add(mesh["gear_a"])

    queue = deque(gears_by_axis[candidate["drive_axis"]])
    visited = set(queue)
    while queue:
        gear_id = queue.popleft()
        for next_gear in adjacency[gear_id]:
            if next_gear not in visited:
                visited.add(next_gear)
                queue.append(next_gear)

    for output in candidate["outputs"]:
        if not set(gears_by_axis[output["axis_id"]]).intersection(visited):
            return False
    return True


def _candidate_fingerprint(candidate: dict[str, Any]) -> str:
    layout = [
        [axis["axis_id"], round(axis["x"], 2), round(axis["y"], 2), axis["role"]]
        for axis in candidate["axes"]
    ]
    payload = {
        "topology_family": candidate["topology_family"],
        "axis_count": len(candidate["axes"]),
        "gear_count": len(candidate["gears"]),
        "output_count": len(candidate["outputs"]),
        "bridge_count": len(candidate["bridges"]),
        "style_tags": sorted(candidate["style_tags"]),
        "layout": layout,
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()[:16]


def _render_design_dashboard(candidate: dict[str, Any], validation: dict[str, Any]) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>{escape(candidate['design_id'])} dashboard</title>
  <style>
    body {{ font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif; margin: 32px; color: #202124; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid #dadce0; border-radius: 8px; padding: 14px; background: #f8fafd; }}
    code {{ background: #f1f3f4; padding: 1px 4px; border-radius: 4px; }}
    a {{ color: #1a73e8; }}
  </style>
</head>
<body>
  <h1>{escape(candidate['design_id'])}</h1>
  <p>状态：<strong>{escape(validation['status'])}</strong></p>
  <div class="grid">
    <section class="card"><h2>语义检查</h2><p>{escape(validation['check_groups']['semantic_checks'])}</p></section>
    <section class="card"><h2>干涉检查</h2><p>{escape(validation['check_groups']['interference_checks'])}</p></section>
    <section class="card"><h2>动力链检查</h2><p>{escape(validation['check_groups']['power_chain_checks'])}</p></section>
    <section class="card"><h2>角色合同检查</h2><p>{escape(validation['check_groups']['role_contract_checks'])}</p></section>
    <section class="card"><h2>生产几何检查</h2><p>{escape(validation['check_groups']['production_geometry_checks'])}</p></section>
    <section class="card"><h2>目视检查</h2><p>{escape(validation['check_groups']['visual_review_checks'])}</p></section>
  </div>
  <h2>CAD Explorer 视图</h2>
  <ul>
    <li><a href="?file=watch_kinematic.step&view=solid">solid</a></li>
    <li><a href="?file=watch_kinematic.step&view=transparent_case">transparent_case</a></li>
    <li><a href="?file=watch_kinematic.step&view=mechanism_focus">mechanism_focus</a></li>
  </ul>
  <p>STEP 文件：<code>watch_kinematic.step</code></p>
</body>
</html>
"""


def _render_visual_review(candidate: dict[str, Any], visual: dict[str, Any]) -> str:
    svg = _render_topology_svg(candidate)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>{escape(candidate['design_id'])} visual review</title>
  <style>
    body {{ font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif; margin: 32px; }}
    svg {{ max-width: 780px; border: 1px solid #dadce0; border-radius: 8px; background: #fff; }}
  </style>
</head>
<body>
  <h1>目视检查：{escape(candidate['design_id'])}</h1>
  <p>状态：<strong>{escape(visual['status'])}</strong></p>
  {svg}
  <h2>可见标签</h2>
  <p>{escape(', '.join(visual['present_labels']))}</p>
</body>
</html>
"""


def _render_bridge_2d_review(candidate: dict[str, Any], production: dict[str, Any]) -> str:
    svg = _render_bridge_2d_svg(candidate)
    failed = production["failures"].get("bridge_2d_human_review_required", [])
    failed_items = "".join(
        f"<li><code>{escape(item['bridge_id'])}</code>: {escape(item['reason'])}</li>"
        for item in failed
    )
    if not failed_items:
        failed_items = "<li>二维桥板方案已被标记为通过。</li>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>{escape(candidate['design_id'])} bridge 2D review</title>
  <style>
    body {{ font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif; margin: 28px; color: #202124; background: #f8fafd; }}
    .layout {{ display: grid; grid-template-columns: minmax(620px, 1.4fr) minmax(320px, 0.8fr); gap: 18px; align-items: start; }}
    .panel {{ background: #fff; border: 1px solid #dadce0; border-radius: 8px; padding: 16px; }}
    svg {{ width: 100%; height: auto; border: 1px solid #dadce0; border-radius: 8px; background: #fff; }}
    .badge {{ display: inline-block; border-radius: 999px; padding: 4px 10px; font-weight: 700; font-size: 13px; }}
    .fail {{ background: #fce8e6; color: #a50e0e; border: 1px solid #f6aea9; }}
    .warn {{ background: #fef7e0; color: #b06000; border: 1px solid #fdd663; }}
    .ok {{ background: #e6f4ea; color: #137333; border: 1px solid #b7dfc0; }}
    code {{ background: #f1f3f4; border-radius: 4px; padding: 1px 4px; }}
    li {{ margin: 8px 0; }}
  </style>
</head>
<body>
  <h1>二维桥板方案审查：{escape(candidate['design_id'])}</h1>
  <p><span class="badge fail">当前 3D 桥板禁止验收</span> <span class="badge warn">先把二维方案做对</span></p>
  <div class="layout">
    <section class="panel">
      {svg}
    </section>
    <section class="panel">
      <h2>审查结论</h2>
      <ul>
        {failed_items}
      </ul>
      <h2>红色线为什么失败</h2>
      <ul>
        <li>长直梁穿越齿轮投影：当前 route 把轴心直接连到外侧走廊，视觉上变成压在齿轮正面的梁。</li>
        <li>二维中心线没有先生成可审查的闭合足迹，3D 阶段只能得到矩形条。</li>
        <li>局部轴承座允许覆盖齿轮中心，但不能把整条长梁都视为“局部支撑”。</li>
      </ul>
      <h2>蓝色线是什么</h2>
      <ul>
        <li>蓝色是下一版候选二维目标：先把桥板看作连续、圆角、可制造的桥板路径，而不是一组矩形梁。</li>
        <li>蓝色仍未验收，只用于二维讨论；验收前不会重新生成 3D 桥板。</li>
      </ul>
      <h2>图例</h2>
      <ul>
        <li><span class="badge fail">红色虚线</span> 当前错误中心线。</li>
        <li><span class="badge ok">蓝色粗线</span> 候选二维桥板中心线/足迹方向。</li>
        <li>淡红圆：齿轮投影软避让区。</li>
        <li>橙色圆：螺钉座。</li>
        <li>蓝色小圆：轴承/宝石座。</li>
      </ul>
    </section>
  </div>
</body>
</html>
"""


def _render_bridge_2d_svg(candidate: dict[str, Any]) -> str:
    size = 760
    center = size / 2.0
    scale = (size * 0.42) / max(candidate["case_radius_mm"], 1.0)

    def sx(x: float) -> float:
        return center + x * scale

    def sy(y: float) -> float:
        return center - y * scale

    def line(points: list[tuple[float, float]], *, color: str, width_mm: float, dash: str = "", opacity: float = 1.0) -> str:
        if len(points) < 2:
            return ""
        raw = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in points)
        dash_attr = f" stroke-dasharray='{dash}'" if dash else ""
        return (
            f"<polyline points='{raw}' fill='none' stroke='{color}' stroke-width='{width_mm * scale:.2f}'"
            f" stroke-linecap='round' stroke-linejoin='round' opacity='{opacity}'{dash_attr}/>"
        )

    gears = []
    for gear in candidate["gears"]:
        gears.append(
            f"<circle cx='{sx(gear['layout_x']):.2f}' cy='{sy(gear['layout_y']):.2f}' r='{gear['layout_outer_radius'] * scale:.2f}'"
            " fill='#fce8e6' fill-opacity='0.32' stroke='#c5221f' stroke-opacity='0.55' stroke-width='1.4'/>"
        )
        gears.append(
            f"<text x='{sx(gear['layout_x']):.2f}' y='{sy(gear['layout_y'] - gear['layout_outer_radius'] - 0.5):.2f}'"
            " font-size='11' text-anchor='middle' fill='#5f6368'>"
            f"{escape(gear['gear_id'])}</text>"
        )

    axes = []
    for axis in candidate["axes"]:
        axes.append(
            f"<circle cx='{sx(axis['layout_x']):.2f}' cy='{sy(axis['layout_y']):.2f}' r='{BRIDGE_PIVOT_PAD_RADIUS_MM * scale:.2f}'"
            " fill='#e8f0fe' stroke='#1a73e8' stroke-width='1.6'/>"
        )
        axes.append(
            f"<text x='{sx(axis['layout_x']):.2f}' y='{sy(axis['layout_y'] + 1.35):.2f}'"
            " font-size='12' text-anchor='middle' fill='#174ea6'>"
            f"{escape(axis['axis_id'])}</text>"
        )

    screws = []
    for screw in candidate["screws"]:
        screws.append(
            f"<circle cx='{sx(screw.get('layout_x', 0.0)):.2f}' cy='{sy(screw.get('layout_y', 0.0)):.2f}' r='{BRIDGE_SCREW_PAD_RADIUS_MM * scale:.2f}'"
            " fill='#fef7e0' stroke='#f9ab00' stroke-width='1.6'/>"
        )

    current_segments = []
    target_paths = []
    for bridge in candidate["bridges"]:
        plan = _bridge_2d_route_plan(candidate, bridge)
        for segment in plan["segments"]:
            current_segments.append(line([segment["from"], segment["to"]], color="#c5221f", width_mm=BRIDGE_WEB_WIDTH_MM, dash="8 6", opacity=0.78))

        axes_for_bridge = _bridge_axes(candidate, bridge)
        screws_for_bridge = _bridge_screws(candidate, bridge)
        if axes_for_bridge:
            ordered_points = []
            if screws_for_bridge:
                ordered_points.append((screws_for_bridge[0].get("layout_x", 0.0), screws_for_bridge[0].get("layout_y", 0.0)))
            ordered_points.extend((axis["layout_x"], axis["layout_y"]) for axis in axes_for_bridge)
            if len(screws_for_bridge) > 1:
                ordered_points.append((screws_for_bridge[-1].get("layout_x", 0.0), screws_for_bridge[-1].get("layout_y", 0.0)))
            target_paths.append(line(ordered_points, color="#1a73e8", width_mm=1.65, opacity=0.48))

    case_radius = candidate["case_radius_mm"] * scale
    movement_radius = candidate["movement_radius_mm"] * scale
    return f"""<svg viewBox="0 0 {size} {size}" role="img" aria-label="2D bridge review">
  <rect x="0" y="0" width="{size}" height="{size}" fill="#ffffff"/>
  <circle cx="{center:.2f}" cy="{center:.2f}" r="{case_radius:.2f}" fill="none" stroke="#9aa0a6" stroke-width="2.2"/>
  <circle cx="{center:.2f}" cy="{center:.2f}" r="{movement_radius:.2f}" fill="none" stroke="#dadce0" stroke-width="1.4" stroke-dasharray="5 5"/>
  {''.join(gears)}
  {''.join(current_segments)}
  {''.join(target_paths)}
  {''.join(axes)}
  {''.join(screws)}
  <text x="24" y="32" font-size="18" font-weight="700" fill="#202124">Bridge 2D Review</text>
  <text x="24" y="56" font-size="13" fill="#5f6368">Red=current failed route, Blue=2D candidate for discussion only</text>
</svg>"""


def _render_batch_review(manifest: dict[str, Any]) -> str:
    base = Path(manifest["output_dir"])
    rows = []
    for design in manifest["designs"]:
        dashboard_rel = _relative_artifact(base, design["artifacts"]["dashboard_html"])
        visual_rel = _relative_artifact(base, design["artifacts"]["visual_review_html"])
        rows.append(
            f"<article class='design-card'>"
            f"<h2>{escape(design['design_id'])}</h2>"
            f"<p><strong>拓扑：</strong>{escape(design['topology_family'])} "
            f"<strong>状态：</strong>{escape(design['status'])}</p>"
            f"<div class='checks'>"
            f"<span>语义 {escape(design['semantic_checks']['status'])}</span>"
            f"<span>干涉 {escape(design['interference_checks']['status'])}</span>"
            f"<span>动力链 {escape(design['power_chain_checks']['status'])}</span>"
            f"<span>角色合同 {escape(design['role_contract_checks']['status'])}</span>"
            f"<span>生产几何 {escape(design['production_geometry_checks']['status'])}</span>"
            f"<span>目视 {escape(design['visual_review_checks']['status'])}</span>"
            f"</div>"
            f"<iframe src='{escape(visual_rel)}' title='{escape(design['design_id'])} visual review'></iframe>"
            f"<p><a href='{escape(dashboard_rel)}'>打开 dashboard</a></p>"
            f"<p><code>{escape(design['artifacts']['step'])}</code></p>"
            f"</article>"
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Watch autonomous batch review</title>
  <style>
    body {{ font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif; margin: 32px; color: #202124; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 16px; }}
    .design-card {{ border: 1px solid #dadce0; border-radius: 8px; padding: 14px; background: #f8fafd; }}
    .checks {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 12px; }}
    .checks span {{ border: 1px solid #b7dfc0; background: #e6f4ea; color: #137333; border-radius: 999px; padding: 2px 8px; font-weight: 700; font-size: 12px; }}
    iframe {{ width: 100%; height: 390px; border: 1px solid #dadce0; border-radius: 8px; background: white; }}
    code {{ font-size: 12px; }}
  </style>
</head>
<body>
  <h1>连续 5 个不同手表机械设计</h1>
  <p>总状态：<strong>{escape(manifest['status'])}</strong></p>
  <p>每个设计都必须通过：语义检查、干涉检查、动力链检查、目视检查。</p>
  <div class="grid">
    {''.join(rows)}
  </div>
</body>
</html>
"""


def _relative_artifact(base: Path, raw_path: str) -> str:
    path = Path(raw_path)
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def _build_visual_preview(candidate: dict[str, Any]) -> dict[str, Any]:
    gear_by_id = {gear["gear_id"]: gear for gear in candidate["gears"]}
    return {
        "case_radius_mm": candidate["case_radius_mm"],
        "axes": [
            {
                "axis_id": axis["axis_id"],
                "x": axis["layout_x"],
                "y": axis["layout_y"],
                "role": axis["role"],
            }
            for axis in candidate["axes"]
        ],
        "meshes": [
            {
                "a": gear_by_id[mesh["gear_a"]]["axis_id"],
                "b": gear_by_id[mesh["gear_b"]]["axis_id"],
            }
            for mesh in candidate["meshes"]
        ],
        "outputs": [output["axis_id"] for output in candidate["outputs"]],
        "drive": candidate["drive_axis"],
    }


def _write_batch_contact_sheet(manifest: dict[str, Any], output_path: Path) -> Path:
    card_w = 760
    card_h = 520
    margin = 36
    cols = 2
    rows = math.ceil(len(manifest["designs"]) / cols)
    width = cols * card_w + (cols + 1) * margin
    height = rows * card_h + (rows + 1) * margin + 70
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    title_font = ImageFont.load_default()
    draw.text((margin, 20), "Watch kinematic autonomous batch: 5 distinct designs", fill="#202124", font=title_font)
    draw.text((margin, 42), "green=intermediate, red=drive, blue=output, gray lines=gear mesh", fill="#5f6368", font=font)

    for index, design in enumerate(manifest["designs"]):
        col = index % cols
        row = index // cols
        left = margin + col * (card_w + margin)
        top = margin + 70 + row * (card_h + margin)
        _draw_design_card(draw, design, left, top, card_w, card_h, font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def _draw_design_card(draw: ImageDraw.ImageDraw, design: dict[str, Any], left: int, top: int, width: int, height: int, font) -> None:
    draw.rounded_rectangle((left, top, left + width, top + height), radius=14, outline="#dadce0", fill="#f8fafd", width=2)
    draw.text((left + 18, top + 14), design["design_id"], fill="#202124", font=font)
    draw.text(
        (left + 18, top + 34),
        f"{design['topology_family']} | {design['status']} | sem {design['semantic_checks']['status']} | int {design['interference_checks']['status']} | chain {design['power_chain_checks']['status']} | role {design['role_contract_checks']['status']} | prod {design['production_geometry_checks']['status']} | visual {design['visual_review_checks']['status']}",
        fill="#137333" if design["status"] == "pass" else "#b3261e",
        font=font,
    )
    preview = design["visual_preview"]
    axes = preview["axes"]
    case_radius = max(float(preview["case_radius_mm"]), 1.0)
    cx = left + width / 2
    cy = top + height / 2 + 24
    plot_radius = min(width * 0.35, height * 0.34)
    scale = plot_radius / case_radius
    draw.ellipse(
        (cx - plot_radius, cy - plot_radius, cx + plot_radius, cy + plot_radius),
        outline="#c4d7f2",
        fill="#eef5ff",
        width=3,
    )

    axis_map = {axis["axis_id"]: axis for axis in axes}

    def point(axis_id: str) -> tuple[float, float]:
        axis = axis_map[axis_id]
        return cx + axis["x"] * scale, cy - axis["y"] * scale

    for mesh in preview["meshes"]:
        x1, y1 = point(mesh["a"])
        x2, y2 = point(mesh["b"])
        draw.line((x1, y1, x2, y2), fill="#5f6368", width=3)

    outputs = set(preview["outputs"])
    for axis in axes:
        x, y = point(axis["axis_id"])
        if axis["axis_id"] == preview["drive"]:
            color = "#b3261e"
        elif axis["axis_id"] in outputs:
            color = "#1a73e8"
        else:
            color = "#137333"
        draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill=color, outline="#ffffff", width=2)
        draw.text((x + 12, y - 12), axis["axis_id"], fill="#202124", font=font)

    legend_y = top + height - 38
    draw.text((left + 18, legend_y), f"fingerprint {design['fingerprint']}", fill="#5f6368", font=font)


def _render_topology_svg(candidate: dict[str, Any]) -> str:
    axes = candidate["axes"]
    radius = candidate["case_radius_mm"]
    scale = 7.2

    def sx(value: float) -> float:
        return 420 + value * scale

    def sy(value: float) -> float:
        return 320 - value * scale

    gear_by_id = {gear["gear_id"]: gear for gear in candidate["gears"]}
    lines = []
    for mesh in candidate["meshes"]:
        gear_a = gear_by_id[mesh["gear_a"]]
        gear_b = gear_by_id[mesh["gear_b"]]
        lines.append(
            f"<line x1='{sx(gear_a['layout_x']):.1f}' y1='{sy(gear_a['layout_y']):.1f}' "
            f"x2='{sx(gear_b['layout_x']):.1f}' y2='{sy(gear_b['layout_y']):.1f}' stroke='#5f6368' stroke-width='2' />"
        )
    output_axes = {output["axis_id"] for output in candidate["outputs"]}
    circles = []
    for axis in axes:
        color = "#b3261e" if axis["axis_id"] == candidate["drive_axis"] else "#1a73e8" if axis["axis_id"] in output_axes else "#137333"
        circles.append(
            f"<circle cx='{sx(axis['layout_x']):.1f}' cy='{sy(axis['layout_y']):.1f}' r='8' fill='{color}' />"
            f"<text x='{sx(axis['layout_x']) + 10:.1f}' y='{sy(axis['layout_y']) - 9:.1f}' font-size='12'>{escape(axis['axis_id'])}</text>"
        )
    return f"""
<svg viewBox="0 0 840 640" role="img">
  <circle cx="420" cy="320" r="{radius * scale:.1f}" fill="#f8fafd" stroke="#dadce0" stroke-width="2" />
  {''.join(lines)}
  {''.join(circles)}
</svg>
"""
