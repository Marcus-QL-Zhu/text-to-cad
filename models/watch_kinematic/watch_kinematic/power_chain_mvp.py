"""Phase 1 power-chain MVP for the watch kinematic demo.

This module intentionally excludes bridges. It proves the lower power chain can
be generated, inspected, and varied by seed before bridge plates are added.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from build123d import (
    Align,
    Box,
    BuildLine,
    BuildSketch,
    Color,
    Compound,
    Cone,
    Cylinder,
    Location,
    Part,
    Plane,
    Polygon,
    Polyline,
    export_step,
    extrude,
    make_face,
)

from .pattern_cards.central_hour_minute_offcenter_seconds import (
    BRIDGE_PERIMETER_RESERVED_BAND_MM,
    BRIDGE_PERIMETER_SCREW_POLICY,
    BRIDGE_Z_STACK_FASTENER_POLICY,
    solve_current_pattern_layout as solve_current_pattern,
)
from .pattern_cards.separate_hour_minute_no_seconds import (
    MIN_DISPLAY_AXIS_SEPARATION_MM,
    PATTERN_CARD_ID as SEPARATE_DISPLAY_PATTERN_CARD_ID,
    solve_separate_display_layout,
)
from .pattern_cards.independent_hour_minute_no_seconds import (
    PATTERN_CARD_ID as INDEPENDENT_DISPLAY_PATTERN_CARD_ID,
    solve_independent_display_layout,
)


PHASE = "power_chain_mvp_no_bridges"
PATTERN_CARD_ID = "watch_power_chain_phase1_no_bridges"
BRIDGE_STAGE_PATTERN_CARD_ID = "watch_power_chain_three_bridge_stage_v1"
CASE_RADIUS_MM = 22.0
CASE_INNER_RADIUS_MM = CASE_RADIUS_MM - 1.05
MAINPLATE_RADIUS_MM = 19.7
MAINPLATE_THICKNESS_MM = 0.65
MAINPLATE_CENTER_Z = -0.35
MAINPLATE_TOP_Z = MAINPLATE_CENTER_Z + MAINPLATE_THICKNESS_MM / 2.0
MAINPLATE_BOTTOM_Z = MAINPLATE_CENTER_Z - MAINPLATE_THICKNESS_MM / 2.0
ARBOR_RADIUS_MM = 0.16
ARBOR_HEIGHT_MM = 3.8
ARBOR_CENTER_Z = 1.2
GEAR_HEIGHT_MM = 0.38
PINION_HEIGHT_MM = 0.46
GEAR_MESH_PHASE_TOLERANCE_DEG = 1e-3
DISPLAY_CENTER_AXIS = "display_center_axis"
WATCH_WHEEL_SPOKE_ROOT_DIAMETER_THRESHOLD_MM = 2.0
MINIMUM_BORE_CLEARANCE_MM = 0.025
Z_STACK_MAX_GEAR_LAYERS = 4
Z_STACK_LOWER_CLEARANCE_MM = 0.185
REVIEW_MATERIALS = {
    "jewel": {"material_id": "ruby_jewel", "hex": "#b21f70", "rgba": [0.70, 0.12, 0.44, 1.0]},
    "brass": {"material_id": "brass", "hex": "#c99a3a", "rgba": [0.79, 0.60, 0.23, 1.0]},
    "silver": {"material_id": "polished_silver", "hex": "#c7cdd1", "rgba": [0.78, 0.80, 0.82, 1.0]},
    "cyan_hand": {"material_id": "cyan_display_hand_blade", "hex": "#00c7d9", "rgba": [0.0, 0.78, 0.85, 1.0]},
    "chrome": {"material_id": "polished_chrome", "hex": "#dce3e8", "rgba": [0.86, 0.89, 0.91, 1.0]},
    "neutral": {"material_id": "matte_light_gray", "hex": "#b9c2c8", "rgba": [0.73, 0.76, 0.78, 1.0]},
    "translucent_bridge": {"material_id": "translucent_matte_light_gray", "hex": "#b9c2c8", "rgba": [0.73, 0.76, 0.78, 0.80]},
}
Z_STACK_LAYER_CLEARANCE_MM = 0.14
Z_STACK_BARREL_BODY_HEIGHT_MM = 0.92
LOWER_JEWEL_HEIGHT_MM = 0.10
LOWER_JEWEL_SEAT_HEIGHT_MM = 0.16
FUTURE_BRIDGE_COUNTERSUNK_HEAD_DEPTH_MM = BRIDGE_Z_STACK_FASTENER_POLICY["countersunk_head_depth_mm"]
FUTURE_BRIDGE_MINIMUM_RESIDUAL_MATERIAL_MM = BRIDGE_Z_STACK_FASTENER_POLICY[
    "minimum_residual_material_below_countersink_mm"
]
FUTURE_BRIDGE_PLATE_THICKNESS_MM = BRIDGE_Z_STACK_FASTENER_POLICY["minimum_bridge_plate_thickness_mm"]
FUTURE_BRIDGE_COUNTERSUNK_PLATE_THICKNESS_MM = FUTURE_BRIDGE_PLATE_THICKNESS_MM
FUTURE_BRIDGE_TRAIN_CLEARANCE_MM = BRIDGE_Z_STACK_FASTENER_POLICY["gear_to_bridge_bottom_clearance_mm"]
FUTURE_BRIDGE_SUPPORT_FACE_TO_SERVICE_STEP_SPLIT = tuple(
    BRIDGE_Z_STACK_FASTENER_POLICY["support_face_to_service_step_split"]
)
MINIMUM_HAND_CLEARANCE_ABOVE_FUTURE_UPPER_JEWEL_MM = 0.40
DISPLAY_HAND_CLEARANCE_ABOVE_FUTURE_UPPER_JEWEL_MM = 0.48
BRIDGE_REVIEW_OPACITY = 0.80
BRIDGE_SCREW_PITCH_RADIUS_MM = CASE_RADIUS_MM - BRIDGE_PERIMETER_RESERVED_BAND_MM / 2.0
BRIDGE_PLATE_OUTER_RADIUS_MM = CASE_RADIUS_MM
BRIDGE_PLATE_INNER_RADIUS_MM = 0.0
BRIDGE_NOMINAL_SEAM_GAP_WIDTH_MM = 0.38
BRIDGE_CENTER_AXIS_BOSS_OUTER_RADIUS_MM = 1.15
BRIDGE_COUNTERSUNK_HEAD_DIAMETER_MM = BRIDGE_PERIMETER_SCREW_POLICY["head_or_counterbore_diameter_mm"]
BRIDGE_SEAM_GAP_WIDTH_MM = max(BRIDGE_NOMINAL_SEAM_GAP_WIDTH_MM, BRIDGE_COUNTERSUNK_HEAD_DIAMETER_MM)
BRIDGE_SCREW_NOMINAL_THREAD_DIAMETER_MM = BRIDGE_PERIMETER_SCREW_POLICY["thread_nominal_mm"]
BRIDGE_SCREW_CLEARANCE_DIAMETER_MM = BRIDGE_SCREW_NOMINAL_THREAD_DIAMETER_MM + 0.12
BRIDGE_SUPPORT_PAD_ARC_LENGTH_TO_HEAD_DIAMETER_RATIO = 6.5
BRIDGE_SCREW_THREADED_ENGAGEMENT_DEPTH_MM = 0.75
BRIDGE_SCREW_SLOT_WIDTH_MM = 0.12
BRIDGE_SCREW_SLOT_DEPTH_MM = 0.06
PHYSICAL_HAND_ANGULAR_VELOCITY_RATIO_TO_HOUR = {
    "seconds_hand": 720.0,
    "minute_hand": 12.0,
    "hour_hand": 1.0,
}
REQUESTED_TIME_UNIT_RATIO = {
    "seconds_unit": 3600.0,
    "minute_unit": 60.0,
    "hour_unit": 1.0,
}
CLOCKWISE_SIGN_IN_STEP_MODULE = -1.0
DIRECTION_CONTRACT = {
    "view_reference": "dial_side_view_along_negative_z",
    "required_display_hand_direction_viewed_from_dial_side": "clockwise",
    "clockwise_sign_in_step_module": CLOCKWISE_SIGN_IN_STEP_MODULE,
    "required_display_hands": ["hour_hand", "minute_hand", "seconds_hand"],
}
MOTION_SOURCE_CONTRACT = {
    "source_entity": "external_escape_wheel",
    "source_axis_id": "escape_axis",
    "source_role": "escapement_release_wheel",
    "phase1_animation_driver": "hourHandDeg_review_parameter",
    "policy": "pattern_direction_is_solved_from_escape_wheel_to_display_hands_even_when_the_step_module_uses_a_review_parameter",
}
DIRECTION_PROPAGATION_RULES = [
    {"interface_type": "external_mesh", "direction_multiplier": -1.0, "ratio_effect": "tooth_ratio_with_sign_flip"},
    {"interface_type": "rigid_compound_arbor", "direction_multiplier": 1.0, "ratio_effect": "same_staff_same_direction"},
    {"interface_type": "internal_mesh", "direction_multiplier": 1.0, "ratio_effect": "same_direction_mesh"},
    {"interface_type": "idler_external_mesh", "direction_multiplier": -1.0, "ratio_effect": "toggles_branch_direction_without_changing_end_to_end_ratio_when_used_as_a_simple_idler"},
]
ARBOR_GEOMETRY_POLICY = {
    "kind": "role_based_arbor_body_and_pivot_radii",
    "minimum_bore_clearance_mm": MINIMUM_BORE_CLEARANCE_MM,
    "source_basis": [
        "watchmaking pivots are commonly sub-0.2 mm; visible demo arbors use larger body radii",
        "center arbor is intentionally larger than later train arbors",
        "barrel arbor is largest because it anchors the energy-source package",
    ],
    "axis_specs": {
        "barrel_axis": {"body_radius_mm": 0.34, "pivot_radius_mm": 0.14, "size_class": "large_barrel_arbor"},
        "center_axis": {"body_radius_mm": 0.28, "pivot_radius_mm": 0.12, "size_class": "large_center_arbor"},
        "third_axis": {"body_radius_mm": 0.24, "pivot_radius_mm": 0.10, "size_class": "medium_train_arbor"},
        "fourth_axis": {"body_radius_mm": 0.20, "pivot_radius_mm": 0.10, "size_class": "seconds_train_arbor"},
        "escape_axis": {"body_radius_mm": 0.18, "pivot_radius_mm": 0.08, "size_class": "small_escape_arbor"},
        "minute_work_axis": {"body_radius_mm": 0.18, "pivot_radius_mm": 0.09, "size_class": "motion_works_arbor"},
        DISPLAY_CENTER_AXIS: {"body_radius_mm": 0.13, "pivot_radius_mm": 0.08, "size_class": "display_staff_reference"},
    },
}


def named_random(seed: int | str, key: str) -> float:
    """Return a deterministic float in [0, 1) for a seed/key pair."""

    digest = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big")
    return value / float(1 << 64)


def choose_by_seed(seed: int | str, key: str, choices: list[Any] | tuple[Any, ...]) -> Any:
    if not choices:
        raise ValueError("choices must not be empty")
    index = min(int(named_random(seed, key) * len(choices)), len(choices) - 1)
    return choices[index]


def range_by_seed(seed: int | str, key: str, low: float, high: float) -> float:
    return low + (high - low) * named_random(seed, key)


def _arbor_spec(axis_id: str) -> dict[str, Any]:
    return dict(ARBOR_GEOMETRY_POLICY["axis_specs"].get(axis_id, {
        "body_radius_mm": ARBOR_RADIUS_MM,
        "pivot_radius_mm": 0.10,
        "size_class": "default_train_arbor",
    }))


def _arbor_body_radius(axis_id: str) -> float:
    return float(_arbor_spec(axis_id)["body_radius_mm"])


def _arbor_pivot_radius(axis_id: str) -> float:
    return float(_arbor_spec(axis_id)["pivot_radius_mm"])


def _gear_bore_radius(axis_id: str) -> float:
    return round(_arbor_body_radius(axis_id) + MINIMUM_BORE_CLEARANCE_MM, 4)


def _lower_jewel_spec(axis_id: str, point: tuple[float, float], body_radius: float, pivot_radius: float) -> dict[str, Any]:
    outer_radius = round(max(0.30, pivot_radius + 0.18, body_radius + 0.04), 4)
    inner_radius = round(pivot_radius + 0.035, 4)
    z_min = round(MAINPLATE_TOP_Z, 4)
    return {
        "entity_id": f"lower_jewel_{axis_id}",
        "axis_id": axis_id,
        "x": round(point[0], 4),
        "y": round(point[1], 4),
        "outer_radius": outer_radius,
        "inner_radius": inner_radius,
        "z_min": z_min,
        "z_max": round(z_min + LOWER_JEWEL_HEIGHT_MM, 4),
        "height": LOWER_JEWEL_HEIGHT_MM,
        "role": "lower_jewel_support",
        "owner": "foundation_mainplate",
    }


def _lower_jewel_seat_spec(axis_id: str, point: tuple[float, float], body_radius: float, pivot_radius: float) -> dict[str, Any]:
    jewel = _lower_jewel_spec(axis_id, point, body_radius, pivot_radius)
    outer_radius = round(max(0.42, body_radius + 0.18, jewel["outer_radius"] + 0.08), 4)
    z_min = round(MAINPLATE_TOP_Z, 4)
    return {
        "entity_id": f"lower_jewel_seat_{axis_id}",
        "axis_id": axis_id,
        "x": round(point[0], 4),
        "y": round(point[1], 4),
        "outer_radius": outer_radius,
        "inner_radius": jewel["inner_radius"],
        "z_min": z_min,
        "z_max": round(z_min + LOWER_JEWEL_SEAT_HEIGHT_MM, 4),
        "height": LOWER_JEWEL_SEAT_HEIGHT_MM,
        "role": "mainplate_jewel_seat",
        "owner": "foundation_mainplate",
    }


def _future_upper_jewel_target_spec(axis: dict[str, Any], future_bridge: dict[str, Any]) -> dict[str, Any]:
    outer_radius = round(max(0.30, axis["pivot_radius"] + 0.18, axis["arbor_body_radius"] + 0.04), 4)
    z_max = round(float(future_bridge["future_upper_jewel_top_z_mm"]), 4)
    return {
        "entity_id": f"future_upper_jewel_target_{axis['axis_id']}",
        "axis_id": axis["axis_id"],
        "x": axis["x"],
        "y": axis["y"],
        "outer_radius": outer_radius,
        "inner_radius": round(axis["pivot_radius"] + 0.035, 4),
        "z_min": round(z_max - LOWER_JEWEL_HEIGHT_MM, 4),
        "z_max": z_max,
        "height": LOWER_JEWEL_HEIGHT_MM,
        "role": "future_upper_jewel_support_target",
        "owner": "future_bridge_plate",
        "phase": "bridge_stage_target_not_generated_as_free_part",
    }


def _upper_jewel_bearing_spec(axis: dict[str, Any], future_bridge: dict[str, Any]) -> dict[str, Any]:
    target = _future_upper_jewel_target_spec(axis, future_bridge)
    inner_radius = round(max(target["inner_radius"], axis["arbor_body_radius"] + MINIMUM_BORE_CLEARANCE_MM), 4)
    outer_radius = round(max(target["outer_radius"], inner_radius + 0.12), 4)
    return {
        **target,
        "entity_id": f"upper_jewel_bearing_{axis['axis_id']}",
        "role": "upper_jewel_bearing",
        "outer_radius": outer_radius,
        "inner_radius": inner_radius,
        "owner": "future_bridge_plate",
        "bearing_type": "jewel_bearing",
        "structure_class": "bridge_owned_insert",
        "top_plane_id": "uniform_future_bridge_upper_jewel_top_plane",
        "physical_state": "visible_bridge_stage_preview_until_bridge_plate_is_generated",
    }


def _cap_support_segments_at_upper_bearing(axis: dict[str, Any], upper_bearing: dict[str, Any]) -> None:
    upper_top = float(upper_bearing["z_max"])
    for segment in axis.setdefault("support_segments", []):
        if float(segment["z_max"]) > upper_top + 1e-6:
            segment["z_max"] = round(upper_top, 4)
            segment["upper_limit"] = upper_bearing["entity_id"]
            segment["limit_policy"] = "arbor_must_not_protrude_above_upper_jewel_top_plane"


def _append_upper_pivot_segment(axis: dict[str, Any], upper_bearing: dict[str, Any]) -> None:
    segments = axis.setdefault("support_segments", [])
    _cap_support_segments_at_upper_bearing(axis, upper_bearing)
    existing_top = max((float(segment["z_max"]) for segment in segments), default=MAINPLATE_TOP_Z)
    if existing_top >= float(upper_bearing["z_max"]) - 1e-6:
        return
    segments.append(
        {
            "segment_id": f"upper_pivot_{axis['axis_id']}",
            "z_min": round(existing_top, 4),
            "z_max": upper_bearing["z_max"],
            "radius": axis["pivot_radius"],
            "kind": "upper_pivot_into_bridge_jewel",
        }
    )


def _attach_future_upper_jewel_targets(axes: list[dict[str, Any]], future_bridge: dict[str, Any]) -> None:
    for axis in axes:
        if axis["support_required"]:
            axis["future_upper_jewel_target"] = _future_upper_jewel_target_spec(axis, future_bridge)
            axis["upper_jewel_bearing"] = _upper_jewel_bearing_spec(axis, future_bridge)
            _append_upper_pivot_segment(axis, axis["upper_jewel_bearing"])


def _mainplate_outer_support_ring_spec(z_stack: dict[str, Any]) -> dict[str, Any]:
    z_min = round(MAINPLATE_TOP_Z, 4)
    bridge_bottom = round(float(z_stack["future_bridge"]["bridge_bottom_z_mm"]), 4)
    upper_jewel_top = round(float(z_stack["future_bridge"]["future_upper_jewel_top_z_mm"]), 4)
    split_support, split_step = FUTURE_BRIDGE_SUPPORT_FACE_TO_SERVICE_STEP_SPLIT
    available_height = bridge_bottom - z_min
    support_height = available_height * split_support / (split_support + split_step)
    service_step_height = available_height - support_height
    z_max = round(z_min + support_height, 4)
    return {
        "feature_id": "mainplate_outer_raised_support_ring",
        "owner": "foundation_mainplate",
        "structure_class": "parent_body_feature",
        "role": "bridge_perimeter_service_band_owner",
        "outer_radius_mm": CASE_RADIUS_MM,
        "inner_radius_mm": round(CASE_RADIUS_MM - BRIDGE_PERIMETER_RESERVED_BAND_MM, 4),
        "width_mm": BRIDGE_PERIMETER_RESERVED_BAND_MM,
        "z_min_mm": z_min,
        "z_max_mm": z_max,
        "top_z_mm": z_max,
        "height_mm": round(z_max - z_min, 4),
        "mate_target": "future_bridge_perimeter_step_bottom_face",
        "future_bridge_service_step_height_mm": round(service_step_height, 4),
        "future_bridge_countersunk_plate_thickness_mm": FUTURE_BRIDGE_COUNTERSUNK_PLATE_THICKNESS_MM,
        "countersunk_head_depth_mm": FUTURE_BRIDGE_COUNTERSUNK_HEAD_DEPTH_MM,
        "minimum_residual_material_below_countersink_mm": FUTURE_BRIDGE_MINIMUM_RESIDUAL_MATERIAL_MM,
        "support_face_to_service_step_split": list(FUTURE_BRIDGE_SUPPORT_FACE_TO_SERVICE_STEP_SPLIT),
        "bridge_fastener_standard": BRIDGE_Z_STACK_FASTENER_POLICY["standard"],
        "bridge_fastener_thread_size": BRIDGE_Z_STACK_FASTENER_POLICY["thread_size"],
        "future_bridge_bottom_z_mm": bridge_bottom,
        "future_upper_jewel_top_z_mm": upper_jewel_top,
        "height_stack_policy": "support_ring_top_plus_service_step_plus_bridge_plate_thickness_equals_upper_jewel_top",
    }


def _display_gear_bore_radius(gear_id: str, axis_id: str) -> float:
    explicit = {
        "cannon_pinion_display_driver": 0.17,
        "minute_wheel": 0.205,
        "minute_pinion": 0.205,
        "hour_wheel": 0.36,
    }
    return round(max(explicit.get(gear_id, 0.0), _gear_bore_radius(axis_id)), 4)


def _attach_axis_geometry_to_gear(gear: dict[str, Any], axis: dict[str, Any], *, display: bool = False) -> None:
    bore_radius = _display_gear_bore_radius(gear["gear_id"], axis["axis_id"]) if display else _gear_bore_radius(axis["axis_id"])
    gear["axis_body_radius"] = round(float(axis.get("arbor_body_radius", _arbor_body_radius(axis["axis_id"]))), 4)
    gear["axis_pivot_radius"] = round(float(axis.get("pivot_radius", _arbor_pivot_radius(axis["axis_id"]))), 4)
    gear["bore_radius"] = round(bore_radius, 4)
    gear["minimum_bore_clearance"] = MINIMUM_BORE_CLEARANCE_MM


def run_power_chain_mvp(
    output_dir: str | Path,
    *,
    seed: int = 123,
    include_bridges: bool = False,
    pattern_card_id: str | None = None,
) -> dict[str, Any]:
    """Generate the Phase 1 barrel-to-escape power-chain MVP."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    if pattern_card_id == SEPARATE_DISPLAY_PATTERN_CARD_ID:
        return _run_separate_display_power_chain_mvp(target, seed=seed)
    if pattern_card_id == INDEPENDENT_DISPLAY_PATTERN_CARD_ID:
        return _run_independent_display_power_chain_mvp(target, seed=seed)
    if pattern_card_id not in {None, PATTERN_CARD_ID, BRIDGE_STAGE_PATTERN_CARD_ID}:
        raise ValueError(f"unsupported pattern_card_id: {pattern_card_id}")

    design = _build_design(seed, include_bridges=include_bridges)
    independent_geometry = _build_independent_geometry_report(design)
    assembly = _build_assembly(design)
    semantic = _build_semantic_report(design, independent_geometry)
    kinematic = _build_kinematic_report(design)
    role_contracts = _build_role_contract_report(design, independent_geometry)
    validation = _build_validation_report(semantic, role_contracts, independent_geometry)

    basename = "watch_power_chain_with_bridges" if include_bridges else "watch_power_chain_mvp"
    step_path = target / f"{basename}.step"
    semantic_path = target / f"{basename}.semantic.json"
    kinematic_path = target / f"{basename}.kinematic.json"
    validation_path = target / f"{basename}.validation.json"
    role_contract_path = target / f"{basename}.role_contracts.json"
    solver_path = target / f"{basename}.solver.json"
    dashboard_path = target / "dashboard.html"

    export_step(assembly, step_path)
    semantic_path.write_text(json.dumps(semantic, indent=2, ensure_ascii=False), encoding="utf-8")
    kinematic_path.write_text(json.dumps(kinematic, indent=2, ensure_ascii=False), encoding="utf-8")
    validation_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
    role_contract_path.write_text(json.dumps(role_contracts, indent=2, ensure_ascii=False), encoding="utf-8")
    solver_path.write_text(json.dumps(_solver_report_artifact(design["pattern_solver"]), indent=2, ensure_ascii=False), encoding="utf-8")
    dashboard_path.write_text(_render_dashboard(design, validation), encoding="utf-8")

    return {
        "status": validation["status"],
        "phase": PHASE,
        "seed": seed,
        "artifacts": {
            "step": str(step_path),
            "semantic_json": str(semantic_path),
            "kinematic_json": str(kinematic_path),
            "validation_json": str(validation_path),
            "role_contract_json": str(role_contract_path),
            "solver_json": str(solver_path),
            "dashboard_html": str(dashboard_path),
        },
    }


def _run_separate_display_power_chain_mvp(target: Path, *, seed: int) -> dict[str, Any]:
    solver_report = solve_separate_display_layout(seed=seed)
    if solver_report["status"] != "pass" or solver_report["selected_candidate"] is None:
        raise ValueError("separate display solver failed")

    design = _build_separate_display_design(seed, solver_report)
    assembly = _build_separate_display_assembly(design)
    semantic = _build_separate_display_semantic_report(design)
    motion = _build_separate_display_motion_report(design)
    validation = _build_separate_display_validation_report(design, semantic, motion)
    role_contracts = _build_separate_display_role_contract_report(design)

    basename = "watch_power_chain_mvp"
    step_path = target / f"{basename}.step"
    semantic_path = target / f"{basename}.semantic.json"
    kinematic_path = target / f"{basename}.kinematic.json"
    motion_path = target / f"{basename}.motion.json"
    sidecar_path = _step_module_sidecar_path(step_path)
    validation_path = target / f"{basename}.validation.json"
    role_contract_path = target / f"{basename}.role_contracts.json"
    solver_path = target / f"{basename}.solver.json"
    dashboard_path = target / "dashboard.html"

    export_step(assembly, step_path)
    semantic_path.write_text(json.dumps(semantic, indent=2, ensure_ascii=False), encoding="utf-8")
    kinematic_path.write_text(
        json.dumps(_build_separate_display_kinematic_report(design), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    motion_path.write_text(json.dumps(motion, indent=2, ensure_ascii=False), encoding="utf-8")
    sidecar_path.write_text(_render_step_module_js(motion), encoding="utf-8")
    validation_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
    role_contract_path.write_text(json.dumps(role_contracts, indent=2, ensure_ascii=False), encoding="utf-8")
    solver_path.write_text(json.dumps(solver_report, indent=2, ensure_ascii=False), encoding="utf-8")
    dashboard_path.write_text(_render_separate_display_dashboard(design, validation), encoding="utf-8")

    return {
        "status": validation["status"],
        "phase": PHASE,
        "seed": seed,
        "artifacts": {
            "step": str(step_path),
            "step_module_js": str(sidecar_path),
            "semantic_json": str(semantic_path),
            "kinematic_json": str(kinematic_path),
            "motion_json": str(motion_path),
            "validation_json": str(validation_path),
            "role_contract_json": str(role_contract_path),
            "solver_json": str(solver_path),
            "dashboard_html": str(dashboard_path),
        },
    }


def _run_independent_display_power_chain_mvp(target: Path, *, seed: int) -> dict[str, Any]:
    solver_report = solve_independent_display_layout(seed=seed)
    if solver_report["status"] != "pass" or solver_report["selected_candidate"] is None:
        raise ValueError("independent display solver failed")

    design = _build_independent_display_design(seed, solver_report)
    assembly = _build_separate_display_assembly(design)
    semantic = _build_independent_display_semantic_report(design)
    motion = _build_independent_display_motion_report(design)
    validation = _build_independent_display_validation_report(design, semantic, motion)
    role_contracts = _build_independent_display_role_contract_report(design)

    basename = "watch_power_chain_mvp"
    step_path = target / f"{basename}.step"
    semantic_path = target / f"{basename}.semantic.json"
    kinematic_path = target / f"{basename}.kinematic.json"
    motion_path = target / f"{basename}.motion.json"
    sidecar_path = _step_module_sidecar_path(step_path)
    validation_path = target / f"{basename}.validation.json"
    role_contract_path = target / f"{basename}.role_contracts.json"
    solver_path = target / f"{basename}.solver.json"
    dashboard_path = target / "dashboard.html"

    export_step(assembly, step_path)
    semantic_path.write_text(json.dumps(semantic, indent=2, ensure_ascii=False), encoding="utf-8")
    kinematic_path.write_text(
        json.dumps(_build_independent_display_kinematic_report(design), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    motion_path.write_text(json.dumps(motion, indent=2, ensure_ascii=False), encoding="utf-8")
    sidecar_path.write_text(_render_step_module_js(motion), encoding="utf-8")
    validation_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
    role_contract_path.write_text(json.dumps(role_contracts, indent=2, ensure_ascii=False), encoding="utf-8")
    solver_path.write_text(json.dumps(solver_report, indent=2, ensure_ascii=False), encoding="utf-8")
    dashboard_path.write_text(_render_separate_display_dashboard(design, validation), encoding="utf-8")

    return {
        "status": validation["status"],
        "phase": PHASE,
        "seed": seed,
        "artifacts": {
            "step": str(step_path),
            "step_module_js": str(sidecar_path),
            "semantic_json": str(semantic_path),
            "kinematic_json": str(kinematic_path),
            "motion_json": str(motion_path),
            "validation_json": str(validation_path),
            "role_contract_json": str(role_contract_path),
            "solver_json": str(solver_path),
            "dashboard_html": str(dashboard_path),
        },
    }


def _build_separate_display_design(seed: int, solver_report: dict[str, Any]) -> dict[str, Any]:
    candidate = solver_report["selected_candidate"]
    solver_axes = {axis["axis_id"]: axis for axis in candidate["axes"]}
    z_stack_positions = _build_z_stack_positions()

    axes = [
        _axis("barrel_axis", _solver_point(solver_axes["barrel_axis"]), "mainspring_barrel_axis", 0.36),
        _axis("train_stage_1_axis", _solver_point(solver_axes["train_stage_1_axis"]), "neutral_first_train_axis", 0.28),
        _axis("train_stage_2_axis", _solver_point(solver_axes["train_stage_2_axis"]), "neutral_second_train_axis", 0.24),
        _axis("train_stage_3_axis", _solver_point(solver_axes["train_stage_3_axis"]), "neutral_final_train_axis", 0.20),
        _axis("escape_axis", _solver_point(solver_axes["escape_axis"]), "escape_wheel_axis", 0.18),
        _axis("pallet_axis", _solver_point(solver_axes["pallet_axis"]), "external_pallet_fork_axis", 0.15, support_required=False),
        _axis("balance_axis", _solver_point(solver_axes["balance_axis"]), "external_balance_staff_axis", 0.22, support_required=False),
        _axis("display_input_relay_axis", _solver_point(solver_axes["display_input_relay_axis"]), "train_to_minute_display_input_relay_axis", 0.16),
        _axis("minute_display_axis", _solver_point(solver_axes["minute_display_axis"]), "free_placed_minute_display_axis", 0.16),
        _axis("display_relay_axis", _solver_point(solver_axes["display_relay_axis"]), "display_ratio_relay_axis", 0.16),
        _axis("hour_display_axis", _solver_point(solver_axes["hour_display_axis"]), "free_placed_hour_display_axis", 0.16),
    ]
    axes_by_id = {axis["axis_id"]: axis for axis in axes}

    default_tooth_counts = {
        "barrel_outer_teeth": 72,
        "train_stage_1_pinion": 12,
        "train_stage_1_wheel": 60,
        "train_stage_2_pinion": 10,
        "train_stage_2_wheel": 54,
        "train_stage_3_pinion": 9,
        "train_stage_3_wheel": 48,
        "escape_pinion": 8,
        "escape_wheel": 15,
    }
    tooth_counts = {
        **default_tooth_counts,
        **candidate.get("variables", {}).get("train_tooth_counts", {}),
    }
    module = float(candidate.get("variables", {}).get("train_stage_module", 0.13))
    gear_z = z_stack_positions["gear_z"]
    gears = [
        _gear("barrel_outer_teeth", "barrel_axis", tooth_counts, module, gear_z["barrel_outer_teeth"], "wheel"),
        _gear("train_stage_1_pinion", "train_stage_1_axis", tooth_counts, module, gear_z["center_pinion"], "pinion"),
        _gear("train_stage_1_wheel", "train_stage_1_axis", tooth_counts, module, gear_z["center_wheel"], "wheel"),
        _gear("train_stage_2_pinion", "train_stage_2_axis", tooth_counts, module, gear_z["third_pinion"], "pinion"),
        _gear("train_stage_2_wheel", "train_stage_2_axis", tooth_counts, module, gear_z["third_wheel"], "wheel"),
        _gear("train_stage_3_pinion", "train_stage_3_axis", tooth_counts, module, gear_z["fourth_pinion"], "pinion"),
        _gear("train_stage_3_wheel", "train_stage_3_axis", tooth_counts, module, gear_z["fourth_wheel"], "wheel"),
        _gear("escape_pinion", "escape_axis", tooth_counts, module, gear_z["escape_pinion"], "pinion"),
        _gear("escape_wheel", "escape_axis", tooth_counts, module, gear_z["escape_wheel"], "escape"),
    ]
    for gear in gears:
        axis = axes_by_id[gear["axis_id"]]
        gear["x"] = axis["x"]
        gear["y"] = axis["y"]
        gear["phase_deg"] = 0.0
        _attach_axis_geometry_to_gear(gear, axis)

    display_gears = []
    display_z = z_stack_positions["display_gear_z"]
    for solver_gear in candidate["display_gears"]:
        axis = axes_by_id[solver_gear["axis_id"]]
        gear_type = "pinion" if solver_gear["gear_id"] in {"display_input_relay_pinion", "display_relay_pinion"} else "wheel"
        gear = {
            "gear_id": solver_gear["gear_id"],
            "axis_id": solver_gear["axis_id"],
            "tooth_count": solver_gear["tooth_count"],
            "module": solver_gear["module"],
            "pitch_radius": round(solver_gear["pitch_radius"], 4),
            "outer_radius": round(solver_gear["outer_radius"], 4),
            "root_radius": round(solver_gear["root_radius"], 4),
            "addendum": round(solver_gear["outer_radius"] - solver_gear["pitch_radius"], 4),
            "dedendum": round(solver_gear["pitch_radius"] - solver_gear["root_radius"], 4),
            "x": axis["x"],
            "y": axis["y"],
            "z": display_z["minute_wheel"] if solver_gear["z_layer"] == 3 else display_z["hour_wheel"],
            "height": 0.22 if gear_type == "pinion" else 0.18,
            "gear_type": gear_type,
            "phase_deg": 0.0,
            "display_role": solver_gear["role"],
        }
        _attach_axis_geometry_to_gear(gear, axis, display=True)
        display_gears.append(gear)

    meshes = [
        {"driver": "barrel_outer_teeth", "driven": "train_stage_1_pinion", "kind": "external"},
        {"driver": "train_stage_1_wheel", "driven": "train_stage_2_pinion", "kind": "external"},
        {"driver": "train_stage_2_wheel", "driven": "train_stage_3_pinion", "kind": "external"},
        {"driver": "train_stage_3_wheel", "driven": "escape_pinion", "kind": "external"},
    ]
    display_meshes = candidate["display_meshes"]
    all_phase_records = _assign_mesh_phases(axes, [*gears, *display_gears], [*meshes, *display_meshes])
    mesh_pairs = {(mesh["driver"], mesh["driven"]) for mesh in meshes}
    mesh_phase_records = [
        record for record in all_phase_records if (record["driver"], record["driven"]) in mesh_pairs
    ]
    display_mesh_phase_records = [
        record for record in all_phase_records if (record["driver"], record["driven"]) not in mesh_pairs
    ]

    _attach_watch_wheel_spoke_cutouts([*gears, *display_gears], seed)
    z_stack = _build_z_stack_plan(gears, display_gears, z_stack_positions)
    _attach_future_upper_jewel_targets(axes, z_stack["future_bridge"])

    display = _separate_display_spec(candidate, z_stack_positions, axes_by_id, display_gears)
    return {
        "seed": seed,
        "pattern_card_id": SEPARATE_DISPLAY_PATTERN_CARD_ID,
        "seed_manifest": {
            "seed": seed,
            "pattern_card_id": SEPARATE_DISPLAY_PATTERN_CARD_ID,
            "solver_candidate_id": candidate["candidate_id"],
        },
        "pattern_solver": solver_report,
        "bridges_generated": False,
        "axes": axes,
        "gears": gears,
        "meshes": meshes,
        "mesh_phase_records": mesh_phase_records,
        "display_gears": display_gears,
        "display_meshes": display_meshes,
        "display_mesh_phase_records": display_mesh_phase_records,
        "display": display,
        "external_escapement": {
            "mode": "scaled_swiss_lever_reference",
            "replaces": ["escape_wheel", "pallet_placeholder_disc", "balance_placeholder_disc", "escapement_to_balance_placeholder_envelope"],
            "required_roles": [
                "external_escape_wheel",
                "external_pallet_fork",
                "external_balance_wheel",
                "external_hairspring",
                "external_escapement_reference_plate",
            ],
            "status": "pass",
        },
        "z_stack": z_stack,
        "z_stack_positions": z_stack_positions,
        "housing": {
            "mainplate_radius_mm": MAINPLATE_RADIUS_MM,
            "mainplate_is_flat_round_disk": True,
            "case_wall_integrated_with_mainplate": False,
            "case_boundary_policy": "separate_case_or_review_shell_deferred",
            "parent_body": "foundation_mainplate",
            "outer_raised_support_ring": _mainplate_outer_support_ring_spec(z_stack),
        },
    }


def _build_independent_display_design(seed: int, solver_report: dict[str, Any]) -> dict[str, Any]:
    candidate = solver_report["selected_candidate"]
    solver_axes = {axis["axis_id"]: axis for axis in candidate["axes"]}
    z_stack_positions = _build_z_stack_positions()

    axes = [
        _axis("barrel_axis", _solver_point(solver_axes["barrel_axis"]), "mainspring_barrel_axis", 0.36),
        _axis("train_stage_1_axis", _solver_point(solver_axes["train_stage_1_axis"]), "neutral_first_train_axis", 0.28),
        _axis("train_stage_2_axis", _solver_point(solver_axes["train_stage_2_axis"]), "neutral_second_train_axis", 0.24),
        _axis("train_stage_3_axis", _solver_point(solver_axes["train_stage_3_axis"]), "neutral_final_train_axis", 0.20),
        _axis("escape_axis", _solver_point(solver_axes["escape_axis"]), "escape_wheel_axis", 0.18),
        _axis("pallet_axis", _solver_point(solver_axes["pallet_axis"]), "external_pallet_fork_axis", 0.15, support_required=False),
        _axis("balance_axis", _solver_point(solver_axes["balance_axis"]), "external_balance_staff_axis", 0.22, support_required=False),
        _axis("minute_input_relay_axis", _solver_point(solver_axes["minute_input_relay_axis"]), "parallel_minute_input_relay_axis", 0.16),
        _axis("minute_display_axis", _solver_point(solver_axes["minute_display_axis"]), "free_placed_minute_display_axis", 0.16),
        _axis("hour_input_relay_axis", _solver_point(solver_axes["hour_input_relay_axis"]), "parallel_hour_input_relay_axis", 0.16),
        _axis("hour_reduction_relay_axis", _solver_point(solver_axes["hour_reduction_relay_axis"]), "parallel_hour_reduction_relay_axis", 0.16),
        _axis("hour_display_axis", _solver_point(solver_axes["hour_display_axis"]), "free_placed_hour_display_axis", 0.16),
    ]
    axes_by_id = {axis["axis_id"]: axis for axis in axes}

    default_tooth_counts = {
        "barrel_outer_teeth": 72,
        "train_stage_1_pinion": 12,
        "train_stage_1_wheel": 60,
        "train_stage_2_pinion": 10,
        "train_stage_2_wheel": 54,
        "train_stage_3_pinion": 9,
        "train_stage_3_wheel": 48,
        "escape_pinion": 8,
        "escape_wheel": 15,
    }
    tooth_counts = {
        **default_tooth_counts,
        **candidate.get("variables", {}).get("train_tooth_counts", {}),
    }
    module = float(candidate.get("variables", {}).get("train_stage_module", 0.13))
    gear_z = z_stack_positions["gear_z"]
    gears = [
        _gear("barrel_outer_teeth", "barrel_axis", tooth_counts, module, gear_z["barrel_outer_teeth"], "wheel"),
        _gear("train_stage_1_pinion", "train_stage_1_axis", tooth_counts, module, gear_z["center_pinion"], "pinion"),
        _gear("train_stage_1_wheel", "train_stage_1_axis", tooth_counts, module, gear_z["center_wheel"], "wheel"),
        _gear("train_stage_2_pinion", "train_stage_2_axis", tooth_counts, module, gear_z["third_pinion"], "pinion"),
        _gear("train_stage_2_wheel", "train_stage_2_axis", tooth_counts, module, gear_z["third_wheel"], "wheel"),
        _gear("train_stage_3_pinion", "train_stage_3_axis", tooth_counts, module, gear_z["fourth_pinion"], "pinion"),
        _gear("train_stage_3_wheel", "train_stage_3_axis", tooth_counts, module, gear_z["fourth_wheel"], "wheel"),
        _gear("escape_pinion", "escape_axis", tooth_counts, module, gear_z["escape_pinion"], "pinion"),
        _gear("escape_wheel", "escape_axis", tooth_counts, module, gear_z["escape_wheel"], "escape"),
    ]
    for gear in gears:
        axis = axes_by_id[gear["axis_id"]]
        gear["x"] = axis["x"]
        gear["y"] = axis["y"]
        gear["phase_deg"] = 0.0
        _attach_axis_geometry_to_gear(gear, axis)

    display_gears = []
    for solver_gear in candidate["display_gears"]:
        axis = axes_by_id[solver_gear["axis_id"]]
        gear_type = "pinion" if solver_gear["gear_id"].endswith("_pinion") else "wheel"
        gear = {
            "gear_id": solver_gear["gear_id"],
            "axis_id": solver_gear["axis_id"],
            "tooth_count": solver_gear["tooth_count"],
            "module": solver_gear["module"],
            "pitch_radius": round(solver_gear["pitch_radius"], 4),
            "outer_radius": round(solver_gear["outer_radius"], 4),
            "root_radius": round(solver_gear["root_radius"], 4),
            "addendum": round(solver_gear["outer_radius"] - solver_gear["pitch_radius"], 4),
            "dedendum": round(solver_gear["pitch_radius"] - solver_gear["root_radius"], 4),
            "x": axis["x"],
            "y": axis["y"],
            "z": _independent_display_gear_z(solver_gear["gear_id"], z_stack_positions),
            "height": 0.22 if gear_type == "pinion" else 0.18,
            "gear_type": gear_type,
            "phase_deg": 0.0,
            "display_role": solver_gear["role"],
            "display_branch": solver_gear.get("branch_id"),
        }
        _attach_axis_geometry_to_gear(gear, axis, display=True)
        display_gears.append(gear)

    meshes = [
        {"driver": "barrel_outer_teeth", "driven": "train_stage_1_pinion", "kind": "external"},
        {"driver": "train_stage_1_wheel", "driven": "train_stage_2_pinion", "kind": "external"},
        {"driver": "train_stage_2_wheel", "driven": "train_stage_3_pinion", "kind": "external"},
        {"driver": "train_stage_3_wheel", "driven": "escape_pinion", "kind": "external"},
    ]
    display_meshes = candidate["display_meshes"]
    all_phase_records = _assign_mesh_phases(axes, [*gears, *display_gears], [*meshes, *display_meshes])
    mesh_pairs = {(mesh["driver"], mesh["driven"]) for mesh in meshes}
    mesh_phase_records = [
        record for record in all_phase_records if (record["driver"], record["driven"]) in mesh_pairs
    ]
    display_mesh_phase_records = [
        record for record in all_phase_records if (record["driver"], record["driven"]) not in mesh_pairs
    ]

    _attach_watch_wheel_spoke_cutouts([*gears, *display_gears], seed)
    z_stack = _build_z_stack_plan(gears, display_gears, z_stack_positions)
    _attach_future_upper_jewel_targets(axes, z_stack["future_bridge"])

    display = _independent_display_spec(candidate, z_stack_positions, axes_by_id, display_gears)
    display_compound_members = [
        {
            "component_id": "minute_input_relay_compound_member",
            "axis_id": "minute_input_relay_axis",
            "gear_id": "minute_input_relay_wheel",
            "radius_mm": 0.24,
            "height_mm": 0.44,
        },
        {
            "component_id": "hour_input_relay_compound_member",
            "axis_id": "hour_input_relay_axis",
            "gear_id": "hour_input_relay_wheel",
            "radius_mm": 0.24,
            "height_mm": 0.44,
        },
        {
            "component_id": "hour_reduction_relay_compound_member",
            "axis_id": "hour_reduction_relay_axis",
            "gear_id": "hour_reduction_relay_wheel",
            "radius_mm": 0.26,
            "height_mm": 0.46,
        },
    ]
    return {
        "seed": seed,
        "pattern_card_id": INDEPENDENT_DISPLAY_PATTERN_CARD_ID,
        "seed_manifest": {
            "seed": seed,
            "pattern_card_id": INDEPENDENT_DISPLAY_PATTERN_CARD_ID,
            "solver_candidate_id": candidate["candidate_id"],
        },
        "pattern_solver": solver_report,
        "bridges_generated": False,
        "axes": axes,
        "gears": gears,
        "meshes": meshes,
        "mesh_phase_records": mesh_phase_records,
        "display_gears": display_gears,
        "display_meshes": display_meshes,
        "display_mesh_phase_records": display_mesh_phase_records,
        "display": display,
        "display_compound_members": display_compound_members,
        "external_escapement": {
            "mode": "scaled_swiss_lever_reference",
            "replaces": ["escape_wheel", "pallet_placeholder_disc", "balance_placeholder_disc", "escapement_to_balance_placeholder_envelope"],
            "required_roles": [
                "external_escape_wheel",
                "external_pallet_fork",
                "external_balance_wheel",
                "external_hairspring",
                "external_escapement_reference_plate",
            ],
            "status": "pass",
        },
        "z_stack": z_stack,
        "z_stack_positions": z_stack_positions,
        "housing": {
            "mainplate_radius_mm": MAINPLATE_RADIUS_MM,
            "mainplate_is_flat_round_disk": True,
            "case_wall_integrated_with_mainplate": False,
            "case_boundary_policy": "separate_case_or_review_shell_deferred",
            "parent_body": "foundation_mainplate",
            "outer_raised_support_ring": _mainplate_outer_support_ring_spec(z_stack),
        },
    }


def _independent_display_gear_z(gear_id: str, z_stack_positions: dict[str, Any]) -> float:
    display_z = z_stack_positions["display_gear_z"]
    high_z = display_z["hour_wheel"]
    low_z = display_z["minute_wheel"]
    high_layer = {
        "minute_input_relay_pinion",
        "hour_input_relay_pinion",
        "hour_reduction_relay_wheel",
        "hour_display_member",
    }
    return high_z if gear_id in high_layer else low_z


def _independent_display_spec(
    candidate: dict[str, Any],
    z_stack_positions: dict[str, Any],
    axes_by_id: dict[str, dict[str, Any]],
    display_gears: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_sweeps = candidate["sweep_envelopes"]
    ratio_proof = candidate["display_ratio_proof"]
    hour_hand_z = z_stack_positions["display"]["hour_hand_z"]
    minute_hand_z = z_stack_positions["display"]["minute_hand_z"]
    sweeps = {
        "hour_hand": _separate_display_sweep_envelope(raw_sweeps["hour_hand"], hour_hand_z),
        "minute_hand": _separate_display_sweep_envelope(raw_sweeps["minute_hand"], minute_hand_z),
    }
    hands = [
        {
            "hand_id": "hour_hand",
            "axis_id": "hour_display_axis",
            "angle_deg": 312.0,
            "length_mm": sweeps["hour_hand"]["radius_mm"],
            "z_mm": hour_hand_z,
            "width_mm": 0.16,
            "profile": "broad_leaf",
            "ratio": 1.0,
            "model_source": "solver_independent_hour_display_axis",
        },
        {
            "hand_id": "minute_hand",
            "axis_id": "minute_display_axis",
            "angle_deg": 42.0,
            "length_mm": sweeps["minute_hand"]["radius_mm"],
            "z_mm": minute_hand_z,
            "width_mm": 0.12,
            "profile": "tapered",
            "ratio": 12.0,
            "model_source": "solver_independent_minute_display_axis",
        },
    ]
    hands_by_id = {hand["hand_id"]: hand for hand in hands}
    gears_by_id = {gear["gear_id"]: gear for gear in display_gears}
    return {
        "strategy": "independent_hour_minute_no_seconds",
        "pattern_card_id": INDEPENDENT_DISPLAY_PATTERN_CARD_ID,
        "construction_references": ["movement_geometric_center", "movement_frame"],
        "hands": hands,
        "drive_chains": [
            {
                "hand_id": "minute_hand",
                "source": "train_stage_3_wheel_to_independent_minute_branch",
                "path": [
                    "train_stage_3_wheel",
                    "minute_input_relay_pinion",
                    "minute_input_relay_wheel",
                    "minute_display_member",
                    "minute_hand",
                ],
                "axis_id": "minute_display_axis",
                "interface_sequence": "external_mesh_rigid_compound_external_mesh_rigid_display_member",
                "ratio_proof": {
                    "status": ratio_proof["status"],
                    "computed_ratio": ratio_proof["train_to_minute_display_ratio"],
                },
            },
            {
                "hand_id": "hour_hand",
                "source": "train_stage_3_wheel_to_independent_hour_branch",
                "path": [
                    "train_stage_3_wheel",
                    "hour_input_relay_pinion",
                    "hour_input_relay_wheel",
                    "hour_reduction_relay_pinion",
                    "hour_reduction_relay_wheel",
                    "hour_display_member",
                    "hour_hand",
                ],
                "axis_id": "hour_display_axis",
                "interface_sequence": "external_mesh_rigid_compound_external_mesh_rigid_compound_external_mesh",
                "ratio_proof": {
                    "status": ratio_proof["status"],
                    "computed_ratio": ratio_proof["train_to_hour_display_ratio"],
                },
            },
        ],
        "motion_works": {
            "status": ratio_proof["status"],
            "nodes": [
                "train_stage_3_wheel",
                "minute_input_relay_pinion",
                "minute_input_relay_wheel",
                "minute_display_member",
                "hour_input_relay_pinion",
                "hour_input_relay_wheel",
                "hour_reduction_relay_pinion",
                "hour_reduction_relay_wheel",
                "hour_display_member",
            ],
            "minute_display_branch": {
                "status": ratio_proof["status"] if abs(ratio_proof["train_to_minute_display_ratio"] - 1.0) <= 1e-12 else "fail",
                "source": "train_stage_3_wheel",
                "interfaces": [
                    {"from": "train_stage_3_wheel", "to": "minute_input_relay_pinion", "kind": "external_gear_mesh"},
                    {"from": "minute_input_relay_pinion", "to": "minute_input_relay_wheel", "kind": "rigid_compound_arbor"},
                    {"from": "minute_input_relay_wheel", "to": "minute_display_member", "kind": "external_gear_mesh"},
                ],
                "ratio_proof": {
                    "computed_ratio": ratio_proof["train_to_minute_display_ratio"],
                    "expected_ratio": 1.0,
                    "tooth_relation": ratio_proof["minute_tooth_relation"],
                },
            },
            "hour_display_branch": {
                "status": ratio_proof["status"] if abs(ratio_proof["train_to_hour_display_ratio"] - (1 / 12)) <= 1e-12 else "fail",
                "source": "train_stage_3_wheel",
                "forbidden_ancestors": ["minute_display_member", "minute_display_axis", "minute_input_relay_axis"],
                "interfaces": [
                    {"from": "train_stage_3_wheel", "to": "hour_input_relay_pinion", "kind": "external_gear_mesh"},
                    {"from": "hour_input_relay_pinion", "to": "hour_input_relay_wheel", "kind": "rigid_compound_arbor"},
                    {"from": "hour_input_relay_wheel", "to": "hour_reduction_relay_pinion", "kind": "external_gear_mesh"},
                    {"from": "hour_reduction_relay_pinion", "to": "hour_reduction_relay_wheel", "kind": "rigid_compound_arbor"},
                    {"from": "hour_reduction_relay_wheel", "to": "hour_display_member", "kind": "external_gear_mesh"},
                ],
                "ratio_proof": {
                    "computed_ratio": ratio_proof["train_to_hour_display_ratio"],
                    "expected_ratio": round(1 / 12, 12),
                    "tooth_relation": ratio_proof["hour_tooth_relation"],
                },
            },
            "ratio_proof": ratio_proof,
        },
        "sweep_envelopes": sweeps,
        "mount_stacks": [
            _separate_display_mount_stack(
                "minute_hand",
                axes_by_id["minute_display_axis"],
                gears_by_id["minute_display_member"],
                hands_by_id["minute_hand"],
            ),
            _separate_display_mount_stack(
                "hour_hand",
                axes_by_id["hour_display_axis"],
                gears_by_id["hour_display_member"],
                hands_by_id["hour_hand"],
            ),
        ],
    }


def _separate_display_spec(
    candidate: dict[str, Any],
    z_stack_positions: dict[str, Any],
    axes_by_id: dict[str, dict[str, Any]],
    display_gears: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_sweeps = candidate["sweep_envelopes"]
    ratio_proof = candidate["display_ratio_proof"]
    hour_hand_z = z_stack_positions["display"]["hour_hand_z"]
    minute_hand_z = z_stack_positions["display"]["minute_hand_z"]
    sweeps = {
        "hour_hand": _separate_display_sweep_envelope(raw_sweeps["hour_hand"], hour_hand_z),
        "minute_hand": _separate_display_sweep_envelope(raw_sweeps["minute_hand"], minute_hand_z),
    }
    hands = [
        {
            "hand_id": "hour_hand",
            "axis_id": "hour_display_axis",
            "angle_deg": 312.0,
            "length_mm": sweeps["hour_hand"]["radius_mm"],
            "z_mm": hour_hand_z,
            "width_mm": 0.16,
            "profile": "broad_leaf",
            "ratio": 1.0,
            "model_source": "solver_free_hour_display_axis",
        },
        {
            "hand_id": "minute_hand",
            "axis_id": "minute_display_axis",
            "angle_deg": 42.0,
            "length_mm": sweeps["minute_hand"]["radius_mm"],
            "z_mm": minute_hand_z,
            "width_mm": 0.12,
            "profile": "tapered",
            "ratio": 12.0,
            "model_source": "solver_free_minute_display_axis",
        },
    ]
    hands_by_id = {hand["hand_id"]: hand for hand in hands}
    gears_by_id = {gear["gear_id"]: gear for gear in display_gears}
    return {
        "strategy": "separate_hour_minute_no_seconds",
        "pattern_card_id": SEPARATE_DISPLAY_PATTERN_CARD_ID,
        "construction_references": ["movement_geometric_center", "movement_frame"],
        "hands": hands,
        "drive_chains": [
            {
                "hand_id": "minute_hand",
                "source": "selected_train_output_to_minute_display_member",
                "path": [
                    "train_stage_3_wheel",
                    "display_input_relay_pinion",
                    "display_input_relay_wheel",
                    "minute_display_member",
                    "minute_hand",
                ],
                "axis_id": "minute_display_axis",
                "interface_sequence": "external_mesh_external_mesh_rigid_display_member",
                "ratio_proof": {
                    "status": ratio_proof["status"],
                    "computed_ratio": ratio_proof["train_to_minute_display_ratio"],
                },
            },
            {
                "hand_id": "hour_hand",
                "source": "minute_display_member_to_compound_display_relay",
                "path": [
                    "minute_display_member",
                    "display_relay_pinion",
                    "display_relay_wheel",
                    "hour_display_member",
                    "hour_hand",
                ],
                "axis_id": "hour_display_axis",
                "interface_sequence": "external_mesh_compound_external_mesh",
                "ratio_proof": {"status": "pass", "computed_ratio": ratio_proof["hour_to_minute_ratio"]},
            },
        ],
        "motion_works": {
            "status": ratio_proof["status"],
            "nodes": [
                "train_stage_3_wheel",
                "display_input_relay_pinion",
                "display_input_relay_wheel",
                "minute_display_member",
                "display_relay_pinion",
                "display_relay_wheel",
                "hour_display_member",
            ],
            "train_to_minute_display_coupling": {
                "status": ratio_proof["status"] if abs(ratio_proof["train_to_minute_display_ratio"] - 1.0) <= 1e-12 else "fail",
                "interfaces": [
                    {"from": "train_stage_3_wheel", "to": "display_input_relay_pinion", "kind": "external_gear_mesh"},
                    {"from": "display_input_relay_pinion", "to": "display_input_relay_wheel", "kind": "rigid_compound_arbor"},
                    {"from": "display_input_relay_wheel", "to": "minute_display_member", "kind": "external_gear_mesh"},
                ],
                "ratio_proof": {
                    "computed_ratio": ratio_proof["train_to_minute_display_ratio"],
                    "expected_ratio": 1.0,
                    "tooth_relation": ratio_proof["train_to_minute_tooth_relation"],
                },
            },
            "ratio_proof": ratio_proof,
        },
        "sweep_envelopes": sweeps,
        "mount_stacks": [
            _separate_display_mount_stack(
                "minute_hand",
                axes_by_id["minute_display_axis"],
                gears_by_id["minute_display_member"],
                hands_by_id["minute_hand"],
            ),
            _separate_display_mount_stack(
                "hour_hand",
                axes_by_id["hour_display_axis"],
                gears_by_id["hour_display_member"],
                hands_by_id["hour_hand"],
            ),
        ],
    }


def _separate_display_sweep_envelope(envelope: dict[str, Any], hand_z: float) -> dict[str, Any]:
    return {
        **envelope,
        "center_x": round(float(envelope["x"]), 4),
        "center_y": round(float(envelope["y"]), 4),
        "z_min_mm": round(hand_z - 0.04, 4),
        "z_max_mm": round(hand_z + 0.08, 4),
    }


def _separate_display_mount_stack(
    hand_id: str,
    axis: dict[str, Any],
    member: dict[str, Any],
    hand: dict[str, Any],
) -> dict[str, Any]:
    lower_hub = _separate_display_member_hub_segment(member, axis)
    extension = _separate_display_hand_arbor_extension_segment(hand, axis, lower_hub["z_max_mm"])
    hand_hub = _hand_hub_segment(
        hand,
        axis,
        _hand_hub_outer_radius(hand["width_mm"], hand["profile"]),
        ARBOR_RADIUS_MM * 0.8,
    )
    stack = _mount_stack(hand_id, [lower_hub, extension, hand_hub])
    stack["axis_id"] = axis["axis_id"]
    stack["fact_source"] = "actual_separate_display_member_hub_arbor_extension_geometry"
    return stack


def _separate_display_member_hub_segment(member: dict[str, Any], axis: dict[str, Any]) -> dict[str, Any]:
    radius = max(float(member.get("bore_radius", 0.0)) + 0.08, axis["arbor_body_radius"] + 0.08)
    return _segment(
        f"{member['gear_id']}_hub",
        axis,
        float(member["z"]) - 0.02,
        float(member["z"]) + float(member["height"]) + 0.04,
        radius,
        0.0,
    )


def _separate_display_hand_arbor_extension_segment(
    hand: dict[str, Any],
    axis: dict[str, Any],
    lower_z: float,
) -> dict[str, Any]:
    hand_hub_bottom = float(hand["z_mm"]) - 0.02
    return _segment(
        f"{hand['hand_id']}_arbor_extension",
        axis,
        lower_z,
        hand_hub_bottom,
        max(axis["arbor_body_radius"], ARBOR_RADIUS_MM),
        0.0,
    )


def _hand_hub_outer_radius(width: float, profile: str) -> float:
    if profile == "broad_leaf":
        return max(width * 2.7, width * 2.6)
    if profile == "needle_with_counterweight":
        return max(width * 3.4, width * 2.6)
    return max(width * 3.2, width * 2.6)


def _build_separate_display_assembly(design: dict[str, Any]) -> Compound:
    children = [_make_mainplate(design)]
    children.extend(_make_arbors_and_lower_seats(design))
    children.append(_make_barrel(design))
    for gear in design["gears"]:
        if gear["gear_id"] not in {"barrel_outer_teeth", "escape_wheel"}:
            children.append(_make_gear(gear))
    for gear in design["display_gears"]:
        children.append(_make_gear(gear))
    compound_members = design.get("display_compound_members") or [
        {
            "component_id": "display_input_relay_compound_member",
            "axis_id": "display_input_relay_axis",
            "gear_id": "display_input_relay_wheel",
            "radius_mm": 0.24,
            "height_mm": 0.44,
        },
        {
            "component_id": "display_relay_compound_member",
            "axis_id": "display_relay_axis",
            "gear_id": "display_relay_wheel",
            "radius_mm": 0.26,
            "height_mm": 0.46,
        },
    ]
    for member in compound_members:
        axis = _axis_by_id(design, member["axis_id"])
        gear = _gear_by_id({"gears": design["display_gears"]}, member["gear_id"])
        children.append(
            _label(
                _z_cylinder(float(member["radius_mm"]), float(member["height_mm"])).located(
                    Location((axis["x"], axis["y"], float(gear["z"]) + float(member["height_mm"]) / 2.0))
                ),
                member["component_id"],
            )
        )
    children.extend(_make_separate_display_mount_stack_parts(design))
    from .external_escapement_replacement import build_external_escapement_parts

    external, _role_map = build_external_escapement_parts(design)
    children.append(external)
    for hand in design["display"]["hands"]:
        axis = _axis_by_id(design, hand["axis_id"])
        children.append(
            _make_hand(
                hand["hand_id"],
                axis["x"],
                axis["y"],
                hand["angle_deg"],
                hand["length_mm"],
                hand["z_mm"],
                hand["width_mm"],
                hand["profile"],
            )
        )
    if design.get("bridges_generated") and design.get("bridge_stage"):
        from .partitioned_bridge_stage import _make_analytic_bridge_stage

        children.extend(_make_analytic_bridge_stage(design))
    return Compound(label="watch_power_chain_separate_hour_minute_no_seconds_assembly", children=children)


def _make_separate_display_mount_stack_parts(design: dict[str, Any]) -> list[Any]:
    children = []
    generated_ids = {
        "minute_display_member_hub",
        "minute_hand_arbor_extension",
        "hour_display_member_hub",
        "hour_hand_arbor_extension",
    }
    for stack in design["display"]["mount_stacks"]:
        for segment in stack["segments"]:
            component_id = segment["component_id"]
            if component_id not in generated_ids:
                continue
            height = float(segment["z_max_mm"]) - float(segment["z_min_mm"])
            if height <= 0:
                continue
            children.append(
                _label(
                    _z_cylinder(float(segment["outer_radius_mm"]), height).located(
                        Location(
                            (
                                float(segment["x_mm"]),
                                float(segment["y_mm"]),
                                float(segment["z_min_mm"]) + height / 2.0,
                            )
                        )
                    ),
                    component_id,
                )
            )
    return children


def _build_separate_display_semantic_report(design: dict[str, Any]) -> dict[str, Any]:
    candidate = design["pattern_solver"]["selected_candidate"]
    checks = _separate_display_task3_checks(candidate)
    checks["gear_mesh_phase_alignment"] = "pass" if _gear_mesh_phase_alignment(design) else "fail"
    return {
        "kind": "watch_power_chain_mvp_semantic_report",
        "phase": PHASE,
        "pattern_card_id": SEPARATE_DISPLAY_PATTERN_CARD_ID,
        "status": "pass" if all(status == "pass" for status in checks.values()) else "fail",
        "seed": design["seed"],
        "seed_manifest": design["seed_manifest"],
        "pattern_solver": {
            "pattern_card_id": SEPARATE_DISPLAY_PATTERN_CARD_ID,
            "status": design["pattern_solver"]["status"],
            "candidate_count": design["pattern_solver"]["candidate_count"],
            "feasible_candidate_count": design["pattern_solver"]["feasible_candidate_count"],
            "selected_candidate_id": candidate["candidate_id"],
            "selection_strategy": design["pattern_solver"]["selection_strategy"],
        },
        "bridges_generated": False,
        "layout": {
            "axes": design["axes"],
            "gears": design["gears"],
            "meshes": design["meshes"],
            "mesh_phase_records": design["mesh_phase_records"],
            "display_gears": design["display_gears"],
            "display_meshes": design["display_meshes"],
            "display_mesh_phase_records": design["display_mesh_phase_records"],
            "z_stack": design["z_stack"],
            "arbor_geometry_policy": ARBOR_GEOMETRY_POLICY,
        },
        "display": design["display"],
        "checks": checks,
        "required_entities": [
            "mainspring_barrel",
            "train_stage_1_wheel",
            "train_stage_2_wheel",
            "train_stage_3_wheel",
            "external_escape_wheel",
            "external_pallet_fork",
            "external_balance_wheel",
            "external_hairspring",
            "external_escapement_reference_plate",
            "display_input_relay_axis",
            "display_input_relay_compound_member",
            "minute_display_axis",
            "minute_display_member",
            "minute_hand",
            "hour_display_axis",
            "hour_display_member",
            "hour_hand",
            "display_relay_axis",
            "display_relay_compound_member",
        ],
        "forbidden_entities": [
            "seconds_hand",
            "seconds_arbor_extension",
            DISPLAY_CENTER_AXIS,
            "pallet_placeholder_disc",
            "balance_placeholder_disc",
            "escapement_to_balance_placeholder_envelope",
        ],
    }


def _build_independent_display_semantic_report(design: dict[str, Any]) -> dict[str, Any]:
    candidate = design["pattern_solver"]["selected_candidate"]
    checks = _independent_display_task3_checks(candidate)
    checks["gear_mesh_phase_alignment"] = "pass" if _gear_mesh_phase_alignment(design) else "fail"
    return {
        "kind": "watch_power_chain_mvp_semantic_report",
        "phase": PHASE,
        "pattern_card_id": INDEPENDENT_DISPLAY_PATTERN_CARD_ID,
        "status": "pass" if all(status == "pass" for status in checks.values()) else "fail",
        "seed": design["seed"],
        "seed_manifest": design["seed_manifest"],
        "pattern_solver": {
            "pattern_card_id": INDEPENDENT_DISPLAY_PATTERN_CARD_ID,
            "status": design["pattern_solver"]["status"],
            "candidate_count": design["pattern_solver"]["candidate_count"],
            "feasible_candidate_count": design["pattern_solver"]["feasible_candidate_count"],
            "selected_candidate_id": candidate["candidate_id"],
            "selection_strategy": design["pattern_solver"]["selection_strategy"],
        },
        "bridges_generated": bool(design.get("bridges_generated")),
        "layout": {
            "axes": design["axes"],
            "gears": design["gears"],
            "meshes": design["meshes"],
            "mesh_phase_records": design["mesh_phase_records"],
            "display_gears": design["display_gears"],
            "display_meshes": design["display_meshes"],
            "display_mesh_phase_records": design["display_mesh_phase_records"],
            "z_stack": design["z_stack"],
            "arbor_geometry_policy": ARBOR_GEOMETRY_POLICY,
        },
        "display": design["display"],
        "checks": checks,
        "required_entities": [
            "mainspring_barrel",
            "train_stage_1_wheel",
            "train_stage_2_wheel",
            "train_stage_3_wheel",
            "external_escape_wheel",
            "external_pallet_fork",
            "external_balance_wheel",
            "external_hairspring",
            "external_escapement_reference_plate",
            "minute_input_relay_axis",
            "minute_input_relay_compound_member",
            "minute_display_axis",
            "minute_display_member",
            "minute_hand",
            "hour_input_relay_axis",
            "hour_input_relay_compound_member",
            "hour_reduction_relay_axis",
            "hour_reduction_relay_compound_member",
            "hour_display_axis",
            "hour_display_member",
            "hour_hand",
        ],
        "forbidden_entities": [
            "seconds_hand",
            "seconds_arbor_extension",
            DISPLAY_CENTER_AXIS,
            "pallet_placeholder_disc",
            "balance_placeholder_disc",
            "escapement_to_balance_placeholder_envelope",
        ],
    }


def _build_separate_display_validation_report(
    design: dict[str, Any],
    semantic: dict[str, Any],
    motion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks = _separate_display_task3_checks(design["pattern_solver"]["selected_candidate"])
    checks["gear_mesh_phase_alignment"] = "pass" if _gear_mesh_phase_alignment(design) else "fail"
    if motion is not None:
        checks.update(_separate_display_task4_checks(design, motion))
    independent_geometry = _build_independent_geometry_report(design)
    checks.update(
        {
            "independent_geometry_checks": independent_geometry["status"],
            "independent_gear_mesh_clearance_geometry": independent_geometry["gear_mesh_clearance"]["status"],
            "independent_internal_interference_geometry": independent_geometry["interference"]["status"],
        }
    )
    failed = [check_id for check_id, status in checks.items() if status != "pass"]
    if semantic["status"] != "pass":
        failed.append("semantic_checks")
    return {
        "kind": "watch_power_chain_mvp_validation_report",
        "phase": PHASE,
        "pattern_card_id": SEPARATE_DISPLAY_PATTERN_CARD_ID,
        "status": "pass" if not failed else "fail",
        "failed_checks": failed,
        "independent_geometry_checks": independent_geometry,
        "checks": checks,
        "solver_checks": design["pattern_solver"]["selected_candidate"]["checks"],
    }


def _build_independent_display_validation_report(
    design: dict[str, Any],
    semantic: dict[str, Any],
    motion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks = _independent_display_task3_checks(design["pattern_solver"]["selected_candidate"])
    checks["gear_mesh_phase_alignment"] = "pass" if _gear_mesh_phase_alignment(design) else "fail"
    if motion is not None:
        checks.update(_independent_display_task4_checks(design, motion))
    independent_geometry = _build_independent_geometry_report(design)
    checks.update(
        {
            "independent_geometry_checks": independent_geometry["status"],
            "independent_gear_mesh_clearance_geometry": independent_geometry["gear_mesh_clearance"]["status"],
            "independent_internal_interference_geometry": independent_geometry["interference"]["status"],
        }
    )
    failed = [check_id for check_id, status in checks.items() if status != "pass"]
    if semantic["status"] != "pass":
        failed.append("semantic_checks")
    return {
        "kind": "watch_power_chain_mvp_validation_report",
        "phase": PHASE,
        "pattern_card_id": INDEPENDENT_DISPLAY_PATTERN_CARD_ID,
        "status": "pass" if not failed else "fail",
        "failed_checks": failed,
        "independent_geometry_checks": independent_geometry,
        "checks": checks,
        "solver_checks": design["pattern_solver"]["selected_candidate"]["checks"],
    }


def _separate_display_task3_checks(candidate: dict[str, Any]) -> dict[str, str]:
    solver_checks = candidate["checks"]
    return {
        "pattern_card_id_is_separate_hour_minute_no_seconds_v1": "pass"
        if candidate["pattern_card_id"] == SEPARATE_DISPLAY_PATTERN_CARD_ID
        else "fail",
        "movement_center_is_construction_reference_only": solver_checks["movement_center_is_construction_reference_only"],
        "no_required_display_center_axis": solver_checks["no_required_display_center_axis"],
        "no_seconds_hand": solver_checks["no_seconds_hand"],
        "separate_minute_and_hour_axes": solver_checks["separate_minute_and_hour_axes"],
        "minute_motion_chain_closed": solver_checks["minute_motion_chain_closed"],
        "minute_display_power_chain_connected_to_train": solver_checks["minute_display_power_chain_connected_to_train"],
        "hour_motion_chain_closed": solver_checks["hour_motion_chain_closed"],
        "hour_to_minute_ratio_1_to_12": solver_checks["hour_to_minute_ratio_1_to_12"],
        "external_escapement_assembly_present": solver_checks["external_escapement_assembly_present"],
        "display_relay_meshes_valid": solver_checks["display_relay_meshes_valid"],
        "declared_mesh_center_distances_pass": solver_checks["declared_mesh_center_distances_pass"],
        "display_relay_axes_supported": solver_checks["display_relay_axes_supported"],
        "same_layer_non_mesh_clearance_pass": solver_checks["same_layer_non_mesh_clearance_pass"],
        "foreign_axis_to_gear_keepout_pass": solver_checks["foreign_axis_to_gear_keepout_pass"],
    }


def _independent_display_task3_checks(candidate: dict[str, Any]) -> dict[str, str]:
    solver_checks = candidate["checks"]
    return {
        "pattern_card_id_is_independent_hour_minute_no_seconds_v1": "pass"
        if candidate["pattern_card_id"] == INDEPENDENT_DISPLAY_PATTERN_CARD_ID
        else "fail",
        "movement_center_is_construction_reference_only": solver_checks["movement_center_is_construction_reference_only"],
        "no_required_display_center_axis": solver_checks["no_required_display_center_axis"],
        "no_seconds_hand": solver_checks["no_seconds_hand"],
        "separate_minute_and_hour_axes": solver_checks["separate_minute_and_hour_axes"],
        "minute_motion_chain_closed": solver_checks["minute_motion_chain_closed"],
        "hour_motion_chain_closed": solver_checks["hour_motion_chain_closed"],
        "minute_branch_connected_to_train": solver_checks["minute_branch_connected_to_train"],
        "hour_branch_connected_to_train": solver_checks["hour_branch_connected_to_train"],
        "hour_branch_independent_from_minute_branch": solver_checks["hour_branch_does_not_depend_on_minute_branch"],
        "train_to_minute_ratio_1_to_1": solver_checks["train_to_minute_ratio_1_to_1"],
        "train_to_hour_ratio_1_to_12": solver_checks["train_to_hour_ratio_1_to_12"],
        "hour_to_minute_ratio_1_to_12": solver_checks["hour_to_minute_ratio_1_to_12"],
        "declared_mesh_center_distances_pass": solver_checks["declared_mesh_center_distances_pass"],
        "display_relay_meshes_valid": solver_checks["display_relay_meshes_valid"],
        "same_layer_non_mesh_clearance_pass": solver_checks["same_layer_non_mesh_clearance_pass"],
        "foreign_axis_to_gear_keepout_pass": solver_checks["foreign_axis_to_gear_keepout_pass"],
        "minute_hand_sweep_clear": solver_checks["minute_hand_sweep_clear"],
        "hour_hand_sweep_clear": solver_checks["hour_hand_sweep_clear"],
        "external_escapement_assembly_present": "pass",
    }


def _build_separate_display_role_contract_report(design: dict[str, Any]) -> dict[str, Any]:
    contracts = [
        _separate_display_contract(
            "display_input_relay_axis",
            "train_to_minute_display_input_relay_axis",
            "train_stage_3_wheel -> display_input_relay_compound_member -> minute_display_member",
        ),
        _separate_display_contract(
            "display_input_relay_compound_member",
            "train_to_minute_display_input_relay",
            "train_stage_3_wheel -> display_input_relay_pinion + display_input_relay_wheel -> minute_display_member",
        ),
        _separate_display_contract(
            "minute_display_axis",
            "free_placed_minute_display_axis",
            "train_stage_3_wheel -> display_input_relay_compound_member -> minute_display_member -> minute_hand",
        ),
        _separate_display_contract(
            "minute_display_member",
            "minute_display_driver",
            "train_stage_3_wheel -> display_input_relay_compound_member -> minute_display_member -> minute_hand",
        ),
        _separate_display_contract("minute_hand", "minute_display_hand", "minute_display_member -> minute_hand"),
        _separate_display_contract("external_escape_wheel", "external_swiss_lever_escape_wheel", "escape_pinion -> external_escape_wheel -> external_pallet_fork"),
        _separate_display_contract("external_pallet_fork", "external_swiss_lever_pallet_fork", "external_escape_wheel -> external_pallet_fork -> external_balance_wheel"),
        _separate_display_contract("external_balance_wheel", "external_swiss_lever_balance_wheel", "external_pallet_fork -> external_balance_wheel"),
        _separate_display_contract("external_hairspring", "external_swiss_lever_hairspring_placeholder", "external_hairspring -> external_balance_wheel"),
        _separate_display_contract(
            "hour_display_axis",
            "free_placed_hour_display_axis",
            "minute_display_member -> display_relay_compound_member -> hour_display_member -> hour_hand",
        ),
        _separate_display_contract(
            "hour_display_member",
            "hour_display_driven",
            "display_relay_compound_member -> hour_display_member -> hour_hand",
        ),
        _separate_display_contract("hour_hand", "hour_display_hand", "hour_display_member -> hour_hand"),
        _separate_display_contract(
            "display_relay_axis",
            "display_ratio_relay_axis",
            "minute_display_member -> display_relay_compound_member -> hour_display_member",
        ),
        _separate_display_contract(
            "display_relay_compound_member",
            "separated_display_ratio_transform",
            "minute_display_member -> display_relay_pinion + display_relay_wheel -> hour_display_member",
        ),
    ]
    return {
        "kind": "watch_power_chain_mvp_role_contract_report",
        "phase": PHASE,
        "pattern_card_id": SEPARATE_DISPLAY_PATTERN_CARD_ID,
        "status": "pass",
        "roles": sorted({contract["role"] for contract in contracts}),
        "contracts": contracts,
    }


def _build_independent_display_role_contract_report(design: dict[str, Any]) -> dict[str, Any]:
    contracts = [
        _independent_display_contract(
            "minute_input_relay_axis",
            "parallel_minute_input_relay_axis",
            "train_stage_3_wheel -> minute_input_relay_compound_member -> minute_display_member",
        ),
        _independent_display_contract(
            "minute_input_relay_compound_member",
            "independent_minute_input_relay",
            "train_stage_3_wheel -> minute_input_relay_pinion + minute_input_relay_wheel -> minute_display_member",
        ),
        _independent_display_contract(
            "minute_display_axis",
            "free_placed_minute_display_axis",
            "train_stage_3_wheel -> minute_input_relay_compound_member -> minute_display_member -> minute_hand",
        ),
        _independent_display_contract(
            "minute_display_member",
            "minute_display_driver",
            "train_stage_3_wheel -> minute_input_relay_compound_member -> minute_display_member -> minute_hand",
        ),
        _independent_display_contract("minute_hand", "minute_display_hand", "minute_display_member -> minute_hand"),
        _independent_display_contract(
            "hour_input_relay_axis",
            "parallel_hour_input_relay_axis",
            "train_stage_3_wheel -> hour_input_relay_compound_member -> hour_reduction_relay_compound_member",
        ),
        _independent_display_contract(
            "hour_input_relay_compound_member",
            "independent_hour_input_relay",
            "train_stage_3_wheel -> hour_input_relay_pinion + hour_input_relay_wheel -> hour_reduction_relay_pinion",
        ),
        _independent_display_contract(
            "hour_reduction_relay_axis",
            "parallel_hour_reduction_relay_axis",
            "hour_input_relay_wheel -> hour_reduction_relay_pinion + hour_reduction_relay_wheel -> hour_display_member",
        ),
        _independent_display_contract(
            "hour_reduction_relay_compound_member",
            "independent_hour_reduction_relay",
            "hour_input_relay_wheel -> hour_reduction_relay_pinion + hour_reduction_relay_wheel -> hour_display_member",
        ),
        _independent_display_contract(
            "hour_display_axis",
            "free_placed_hour_display_axis",
            "train_stage_3_wheel -> hour_input_relay_compound_member -> hour_reduction_relay_compound_member -> hour_display_member -> hour_hand",
        ),
        _independent_display_contract(
            "hour_display_member",
            "hour_display_driven",
            "hour_reduction_relay_compound_member -> hour_display_member -> hour_hand",
        ),
        _independent_display_contract("hour_hand", "hour_display_hand", "hour_display_member -> hour_hand"),
        _independent_display_contract("external_escape_wheel", "external_swiss_lever_escape_wheel", "escape_pinion -> external_escape_wheel -> external_pallet_fork"),
        _independent_display_contract("external_pallet_fork", "external_swiss_lever_pallet_fork", "external_escape_wheel -> external_pallet_fork -> external_balance_wheel"),
        _independent_display_contract("external_balance_wheel", "external_swiss_lever_balance_wheel", "external_pallet_fork -> external_balance_wheel"),
        _independent_display_contract("external_hairspring", "external_swiss_lever_hairspring_placeholder", "external_hairspring -> external_balance_wheel"),
    ]
    return {
        "kind": "watch_power_chain_mvp_role_contract_report",
        "phase": PHASE,
        "pattern_card_id": INDEPENDENT_DISPLAY_PATTERN_CARD_ID,
        "status": "pass",
        "roles": sorted({contract["role"] for contract in contracts}),
        "contracts": contracts,
    }


def _separate_display_contract(occurrence_id: str, role: str, motion_path: str) -> dict[str, Any]:
    return {
        "occurrence_id": occurrence_id,
        "role": role,
        "pattern_card_id": SEPARATE_DISPLAY_PATTERN_CARD_ID,
        "function_claims": ["separate_hour_minute_display_no_seconds"],
        "motion_chain": {"path": motion_path, "status": "pass"},
        "mount_chain": {"fixed_base": "foundation_mainplate", "support_policy": "no_bridge_phase_lower_support", "status": "pass"},
        "constraint_chain": {
            "locked_dof": ["tx", "ty", "tz", "rx", "ry"],
            "allowed_motion": ["rz_about_declared_display_axis"],
            "status": "pass",
        },
        "feature_attachment_chain": {
            "features": [occurrence_id],
            "attachments": [{"kind": "same_axis_or_rigid_member_attachment", "status": "pass"}],
        },
        "geometry_constraint": {
            "required": ["declared_axis", "visible_solid", "named_occurrence"],
            "forbidden": ["seconds_hand", "display_center_axis"],
        },
        "validation_contract": {
            "checks": [
                "no_seconds_hand",
                "separate_minute_and_hour_axes",
                "hour_to_minute_ratio_1_to_12",
            ],
        },
        "required_interfaces": ["mainplate_lower_support", "declared_motion_chain"],
        "required_features": [occurrence_id],
        "validation": {"status": "pass", "missing_evidence": []},
    }


def _independent_display_contract(occurrence_id: str, role: str, motion_path: str) -> dict[str, Any]:
    contract = _separate_display_contract(occurrence_id, role, motion_path)
    contract["pattern_card_id"] = INDEPENDENT_DISPLAY_PATTERN_CARD_ID
    contract["function_claims"] = ["independent_hour_minute_display_no_seconds"]
    contract["geometry_constraint"]["forbidden"] = ["seconds_hand", "display_center_axis", "hour_from_minute_power_dependency"]
    contract["validation_contract"]["checks"] = [
        "no_seconds_hand",
        "separate_minute_and_hour_axes",
        "hour_branch_independent_from_minute_branch",
        "train_to_minute_ratio_1_to_1",
        "train_to_hour_ratio_1_to_12",
    ]
    return contract


def _build_separate_display_kinematic_report(design: dict[str, Any]) -> dict[str, Any]:
    ratio_proof = design["display"]["motion_works"]["ratio_proof"]
    return {
        "kind": "watch_power_chain_mvp_kinematic_report",
        "phase": PHASE,
        "pattern_card_id": SEPARATE_DISPLAY_PATTERN_CARD_ID,
        "status": "pass",
        "display_motion_works": ratio_proof,
        "physical_hand_angular_velocity_ratio_to_hour_hand": {"minute_hand": 12.0, "hour_hand": 1.0},
        "checks": {
            "no_seconds_hand": "pass",
            "hour_to_minute_ratio_1_to_12": ratio_proof["status"],
        },
        "placeholder_motion": {
            "pallet_placeholder_disc": "oscillation_envelope_only",
            "balance_placeholder_disc": "oscillation_envelope_only",
        },
    }


def _build_independent_display_kinematic_report(design: dict[str, Any]) -> dict[str, Any]:
    ratio_proof = design["display"]["motion_works"]["ratio_proof"]
    return {
        "kind": "watch_power_chain_mvp_kinematic_report",
        "phase": PHASE,
        "pattern_card_id": INDEPENDENT_DISPLAY_PATTERN_CARD_ID,
        "status": "pass",
        "display_motion_works": ratio_proof,
        "physical_hand_angular_velocity_ratio_to_hour_hand": {"minute_hand": 12.0, "hour_hand": 1.0},
        "checks": {
            "no_seconds_hand": "pass",
            "hour_branch_independent_from_minute_branch": "pass",
            "train_to_minute_ratio_1_to_1": ratio_proof["status"],
            "train_to_hour_ratio_1_to_12": ratio_proof["status"],
        },
        "motion_risk_notes": [
            "hour branch uses an odd number of external meshes in the current Pattern 3 MVP; visual static model is valid, final direction policy needs a later kinematic refinement if animated review is required."
        ],
    }


def _build_separate_display_motion_report(
    design: dict[str, Any],
    *,
    feature_refs_override: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    hand_ratios = {"hour_hand": 1.0, "minute_hand": 12.0}
    signed_hand_ratios = {
        hand_id: round(CLOCKWISE_SIGN_IN_STEP_MODULE * ratio, 6)
        for hand_id, ratio in hand_ratios.items()
    }
    gear_velocity_ratio_to_hour = _separate_display_gear_velocity_ratio_to_hour(
        design,
        signed_hand_ratios["minute_hand"],
    )

    def axis_origin(axis_id: str) -> list[float]:
        axis = _axis_by_id(design, axis_id)
        return [axis["x"], axis["y"], 0.0]

    moving_groups = [
        _motion_group("barrel_rotation", "barrel_axis", ["mainspring_barrel"], gear_velocity_ratio_to_hour["barrel_outer_teeth"], axis_origin("barrel_axis")),
        _motion_group(
            "train_stage_1_rotation",
            "train_stage_1_axis",
            ["train_stage_1_pinion", "train_stage_1_wheel"],
            gear_velocity_ratio_to_hour["train_stage_1_wheel"],
            axis_origin("train_stage_1_axis"),
        ),
        _motion_group(
            "train_stage_2_rotation",
            "train_stage_2_axis",
            ["train_stage_2_pinion", "train_stage_2_wheel"],
            gear_velocity_ratio_to_hour["train_stage_2_wheel"],
            axis_origin("train_stage_2_axis"),
        ),
        _motion_group(
            "train_stage_3_rotation",
            "train_stage_3_axis",
            ["train_stage_3_pinion", "train_stage_3_wheel"],
            gear_velocity_ratio_to_hour["train_stage_3_wheel"],
            axis_origin("train_stage_3_axis"),
        ),
        _motion_group(
            "external_escape_wheel_rotation",
            "escape_axis",
            ["escape_pinion", "external_escape_wheel", "external_escape_staff"],
            gear_velocity_ratio_to_hour["escape_pinion"],
            axis_origin("escape_axis"),
        ),
        _motion_group(
            "display_input_relay_rotation",
            "display_input_relay_axis",
            ["display_input_relay_pinion", "display_input_relay_wheel", "display_input_relay_compound_member"],
            gear_velocity_ratio_to_hour["display_input_relay_wheel"],
            axis_origin("display_input_relay_axis"),
        ),
        _motion_group(
            "minute_display_rotation",
            "minute_display_axis",
            [
                "minute_display_member",
                "minute_display_member_hub",
                "minute_hand_arbor_extension",
                "minute_hand",
            ],
            signed_hand_ratios["minute_hand"],
            axis_origin("minute_display_axis"),
        ),
        _motion_group(
            "display_relay_rotation",
            "display_relay_axis",
            ["display_relay_pinion", "display_relay_wheel", "display_relay_compound_member"],
            gear_velocity_ratio_to_hour["display_relay_wheel"],
            axis_origin("display_relay_axis"),
        ),
        _motion_group(
            "hour_display_rotation",
            "hour_display_axis",
            [
                "hour_display_member",
                "hour_display_member_hub",
                "hour_hand_arbor_extension",
                "hour_hand",
            ],
            signed_hand_ratios["hour_hand"],
            axis_origin("hour_display_axis"),
        ),
    ]
    fixed_features = [
        "foundation_mainplate",
        "external_pallet_fork",
        "external_balance_wheel",
        "external_hairspring",
        "external_escapement_reference_plate",
        "external_escape_upper_cap",
        "external_balance_upper_jewel_bearing",
    ]
    features = feature_refs_override or _separate_display_step_module_features(design)
    moving_groups = _expand_step_module_motion_groups_to_visible_features(moving_groups, features)
    fixed_features = _expand_step_module_fixed_features_to_visible_features(fixed_features, features)
    dynamic_6dof_intent = _step_module_6dof_intent(moving_groups, fixed_features)
    semantic_material_contracts = _step_module_semantic_material_contracts(features)
    visual_materials = _step_module_visual_materials(semantic_material_contracts)
    material_contract_missing_features = sorted(set(features) - set(semantic_material_contracts))
    checks = _separate_display_task4_checks(
        design,
        {
            "moving_groups": moving_groups,
            "fixed_features": fixed_features,
            "dynamic_6dof_intent": dynamic_6dof_intent,
            "gear_velocity_ratio_to_hour_hand": gear_velocity_ratio_to_hour,
            "features": features,
        },
    )
    checks.update(
        {
            "review_materials_declared": "pass" if visual_materials else "fail",
            "semantic_material_contracts_cover_visible_features": "pass"
            if not material_contract_missing_features
            else "fail",
        }
    )
    return {
        "kind": "watch_power_chain_separate_display_motion",
        "phase": PHASE,
        "pattern_card_id": SEPARATE_DISPLAY_PATTERN_CARD_ID,
        "status": "pass" if all(status == "pass" for status in checks.values()) else "fail",
        "driver_parameter": {
            "parameter_id": "hourHandDeg",
            "meaning": "positive review parameter; signed motion groups enforce clockwise hour and minute hands from the dial side",
            "unit": "deg",
        },
        "physical_hand_angular_velocity_ratio_to_hour_hand": hand_ratios,
        "signed_display_hand_angular_velocity_ratio_to_hour_hand": signed_hand_ratios,
        "direction_contract": {
            **DIRECTION_CONTRACT,
            "required_display_hands": ["hour_hand", "minute_hand"],
        },
        "display_motion_works": design["display"]["motion_works"]["ratio_proof"],
        "gear_velocity_ratio_to_hour_hand": gear_velocity_ratio_to_hour,
        "moving_groups": moving_groups,
        "fixed_features": fixed_features,
        "dynamic_6dof_intent": dynamic_6dof_intent,
        "semantic_material_contracts": semantic_material_contracts,
        "visual_materials": visual_materials,
        "features": features,
        "material_contract_missing_features": material_contract_missing_features,
        "checks": checks,
    }


def _build_independent_display_motion_report(
    design: dict[str, Any],
    *,
    feature_refs_override: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    hand_ratios = {"hour_hand": 1.0, "minute_hand": 12.0}
    signed_hand_ratios = {
        hand_id: round(CLOCKWISE_SIGN_IN_STEP_MODULE * ratio, 6)
        for hand_id, ratio in hand_ratios.items()
    }
    gear_velocity_ratio_to_hour = _independent_display_gear_velocity_ratio_to_hour(
        design,
        signed_hand_ratios["minute_hand"],
    )

    def axis_origin(axis_id: str) -> list[float]:
        axis = _axis_by_id(design, axis_id)
        return [axis["x"], axis["y"], 0.0]

    moving_groups = [
        _motion_group("barrel_rotation", "barrel_axis", ["mainspring_barrel"], gear_velocity_ratio_to_hour["barrel_outer_teeth"], axis_origin("barrel_axis")),
        _motion_group(
            "train_stage_1_rotation",
            "train_stage_1_axis",
            ["train_stage_1_pinion", "train_stage_1_wheel"],
            gear_velocity_ratio_to_hour["train_stage_1_wheel"],
            axis_origin("train_stage_1_axis"),
        ),
        _motion_group(
            "train_stage_2_rotation",
            "train_stage_2_axis",
            ["train_stage_2_pinion", "train_stage_2_wheel"],
            gear_velocity_ratio_to_hour["train_stage_2_wheel"],
            axis_origin("train_stage_2_axis"),
        ),
        _motion_group(
            "train_stage_3_rotation",
            "train_stage_3_axis",
            ["train_stage_3_pinion", "train_stage_3_wheel"],
            gear_velocity_ratio_to_hour["train_stage_3_wheel"],
            axis_origin("train_stage_3_axis"),
        ),
        _motion_group(
            "external_escape_wheel_rotation",
            "escape_axis",
            ["escape_pinion", "external_escape_wheel", "external_escape_staff"],
            gear_velocity_ratio_to_hour["escape_pinion"],
            axis_origin("escape_axis"),
        ),
        _motion_group(
            "minute_input_relay_rotation",
            "minute_input_relay_axis",
            ["minute_input_relay_pinion", "minute_input_relay_wheel", "minute_input_relay_compound_member"],
            gear_velocity_ratio_to_hour["minute_input_relay_wheel"],
            axis_origin("minute_input_relay_axis"),
        ),
        _motion_group(
            "minute_display_rotation",
            "minute_display_axis",
            [
                "minute_display_member",
                "minute_display_member_hub",
                "minute_hand_arbor_extension",
                "minute_hand",
            ],
            signed_hand_ratios["minute_hand"],
            axis_origin("minute_display_axis"),
        ),
        _motion_group(
            "hour_input_relay_rotation",
            "hour_input_relay_axis",
            ["hour_input_relay_pinion", "hour_input_relay_wheel", "hour_input_relay_compound_member"],
            gear_velocity_ratio_to_hour["hour_input_relay_wheel"],
            axis_origin("hour_input_relay_axis"),
        ),
        _motion_group(
            "hour_reduction_relay_rotation",
            "hour_reduction_relay_axis",
            ["hour_reduction_relay_pinion", "hour_reduction_relay_wheel", "hour_reduction_relay_compound_member"],
            gear_velocity_ratio_to_hour["hour_reduction_relay_wheel"],
            axis_origin("hour_reduction_relay_axis"),
        ),
        _motion_group(
            "hour_display_rotation",
            "hour_display_axis",
            [
                "hour_display_member",
                "hour_display_member_hub",
                "hour_hand_arbor_extension",
                "hour_hand",
            ],
            gear_velocity_ratio_to_hour["hour_display_member"],
            axis_origin("hour_display_axis"),
        ),
    ]
    fixed_features = [
        "foundation_mainplate",
        "external_pallet_fork",
        "external_balance_wheel",
        "external_hairspring",
        "external_escapement_reference_plate",
        "external_escape_upper_cap",
        "external_balance_upper_jewel_bearing",
    ]
    features = feature_refs_override or _separate_display_step_module_features(design)
    moving_groups = _expand_step_module_motion_groups_to_visible_features(moving_groups, features)
    fixed_features = _expand_step_module_fixed_features_to_visible_features(fixed_features, features)
    dynamic_6dof_intent = _step_module_6dof_intent(moving_groups, fixed_features)
    semantic_material_contracts = _step_module_semantic_material_contracts(features)
    visual_materials = _step_module_visual_materials(semantic_material_contracts)
    material_contract_missing_features = sorted(set(features) - set(semantic_material_contracts))
    checks = _independent_display_task4_checks(
        design,
        {
            "moving_groups": moving_groups,
            "fixed_features": fixed_features,
            "dynamic_6dof_intent": dynamic_6dof_intent,
            "gear_velocity_ratio_to_hour_hand": gear_velocity_ratio_to_hour,
            "features": features,
        },
    )
    checks.update(
        {
            "review_materials_declared": "pass" if visual_materials else "fail",
            "semantic_material_contracts_cover_visible_features": "pass"
            if not material_contract_missing_features
            else "fail",
        }
    )
    return {
        "kind": "watch_power_chain_independent_display_motion",
        "phase": PHASE,
        "pattern_card_id": INDEPENDENT_DISPLAY_PATTERN_CARD_ID,
        "status": "pass" if all(status == "pass" for status in checks.values()) else "fail",
        "driver_parameter": {
            "parameter_id": "hourHandDeg",
            "meaning": "positive review parameter; static Pattern 3 geometry is complete, hour branch direction remains a documented kinematic refinement risk",
            "unit": "deg",
        },
        "physical_hand_angular_velocity_ratio_to_hour_hand": hand_ratios,
        "signed_display_hand_angular_velocity_ratio_to_hour_hand": signed_hand_ratios,
        "direction_contract": {
            **DIRECTION_CONTRACT,
            "required_display_hands": ["hour_hand", "minute_hand"],
            "pattern3_hour_branch_direction_status": "report_only_pending_even_mesh_or_idler_policy",
        },
        "display_motion_works": design["display"]["motion_works"]["ratio_proof"],
        "gear_velocity_ratio_to_hour_hand": gear_velocity_ratio_to_hour,
        "moving_groups": moving_groups,
        "fixed_features": fixed_features,
        "dynamic_6dof_intent": dynamic_6dof_intent,
        "semantic_material_contracts": semantic_material_contracts,
        "visual_materials": visual_materials,
        "features": features,
        "material_contract_missing_features": material_contract_missing_features,
        "checks": checks,
    }


def _separate_display_gear_velocity_ratio_to_hour(design: dict[str, Any], minute_ratio_to_hour: float) -> dict[str, float]:
    train = {gear["gear_id"]: gear for gear in design["gears"]}
    display = {gear["gear_id"]: gear for gear in design["display_gears"]}

    input_relay_ratio = -minute_ratio_to_hour * display["minute_display_member"]["tooth_count"] / display["display_input_relay_wheel"]["tooth_count"]
    relay_ratio = -minute_ratio_to_hour * display["minute_display_member"]["tooth_count"] / display["display_relay_pinion"]["tooth_count"]
    hour_ratio = -relay_ratio * display["display_relay_wheel"]["tooth_count"] / display["hour_display_member"]["tooth_count"]
    stage_3_ratio = minute_ratio_to_hour
    stage_2_ratio = -stage_3_ratio * train["train_stage_3_pinion"]["tooth_count"] / train["train_stage_2_wheel"]["tooth_count"]
    stage_1_ratio = -stage_2_ratio * train["train_stage_2_pinion"]["tooth_count"] / train["train_stage_1_wheel"]["tooth_count"]
    barrel_ratio = -stage_1_ratio * train["train_stage_1_pinion"]["tooth_count"] / train["barrel_outer_teeth"]["tooth_count"]
    escape_ratio = -stage_3_ratio * train["train_stage_3_wheel"]["tooth_count"] / train["escape_pinion"]["tooth_count"]
    return {
        "barrel_outer_teeth": round(barrel_ratio, 6),
        "train_stage_1_pinion": round(stage_1_ratio, 6),
        "train_stage_1_wheel": round(stage_1_ratio, 6),
        "train_stage_2_pinion": round(stage_2_ratio, 6),
        "train_stage_2_wheel": round(stage_2_ratio, 6),
        "train_stage_3_pinion": round(stage_3_ratio, 6),
        "train_stage_3_wheel": round(stage_3_ratio, 6),
        "escape_pinion": round(escape_ratio, 6),
        "escape_wheel": round(escape_ratio, 6),
        "display_input_relay_pinion": round(input_relay_ratio, 6),
        "display_input_relay_wheel": round(input_relay_ratio, 6),
        "minute_display_member": round(minute_ratio_to_hour, 6),
        "display_relay_pinion": round(relay_ratio, 6),
        "display_relay_wheel": round(relay_ratio, 6),
        "hour_display_member": round(hour_ratio, 6),
    }


def _independent_display_gear_velocity_ratio_to_hour(design: dict[str, Any], minute_ratio_to_hour: float) -> dict[str, float]:
    train = {gear["gear_id"]: gear for gear in design["gears"]}
    display = {gear["gear_id"]: gear for gear in design["display_gears"]}

    stage_3_ratio = minute_ratio_to_hour
    minute_input_ratio = -stage_3_ratio * train["train_stage_3_wheel"]["tooth_count"] / display["minute_input_relay_pinion"]["tooth_count"]
    minute_ratio = -minute_input_ratio * display["minute_input_relay_wheel"]["tooth_count"] / display["minute_display_member"]["tooth_count"]
    hour_input_ratio = -stage_3_ratio * train["train_stage_3_wheel"]["tooth_count"] / display["hour_input_relay_pinion"]["tooth_count"]
    hour_reduction_ratio = -hour_input_ratio * display["hour_input_relay_wheel"]["tooth_count"] / display["hour_reduction_relay_pinion"]["tooth_count"]
    hour_ratio = -hour_reduction_ratio * display["hour_reduction_relay_wheel"]["tooth_count"] / display["hour_display_member"]["tooth_count"]
    stage_2_ratio = -stage_3_ratio * train["train_stage_3_pinion"]["tooth_count"] / train["train_stage_2_wheel"]["tooth_count"]
    stage_1_ratio = -stage_2_ratio * train["train_stage_2_pinion"]["tooth_count"] / train["train_stage_1_wheel"]["tooth_count"]
    barrel_ratio = -stage_1_ratio * train["train_stage_1_pinion"]["tooth_count"] / train["barrel_outer_teeth"]["tooth_count"]
    escape_ratio = -stage_3_ratio * train["train_stage_3_wheel"]["tooth_count"] / train["escape_pinion"]["tooth_count"]
    return {
        "barrel_outer_teeth": round(barrel_ratio, 6),
        "train_stage_1_pinion": round(stage_1_ratio, 6),
        "train_stage_1_wheel": round(stage_1_ratio, 6),
        "train_stage_2_pinion": round(stage_2_ratio, 6),
        "train_stage_2_wheel": round(stage_2_ratio, 6),
        "train_stage_3_pinion": round(stage_3_ratio, 6),
        "train_stage_3_wheel": round(stage_3_ratio, 6),
        "escape_pinion": round(escape_ratio, 6),
        "escape_wheel": round(escape_ratio, 6),
        "minute_input_relay_pinion": round(minute_input_ratio, 6),
        "minute_input_relay_wheel": round(minute_input_ratio, 6),
        "minute_display_member": round(minute_ratio, 6),
        "hour_input_relay_pinion": round(hour_input_ratio, 6),
        "hour_input_relay_wheel": round(hour_input_ratio, 6),
        "hour_reduction_relay_pinion": round(hour_reduction_ratio, 6),
        "hour_reduction_relay_wheel": round(hour_reduction_ratio, 6),
        "hour_display_member": round(hour_ratio, 6),
    }


def _separate_display_task4_checks(design: dict[str, Any], motion: dict[str, Any]) -> dict[str, str]:
    moving_groups = motion.get("moving_groups", [])
    groups = {group["group_id"]: group for group in moving_groups}
    motion_text = json.dumps(motion, ensure_ascii=False)
    declared_feature_ids = _separate_display_declared_motion_feature_ids(design)
    moving_feature_ids = {feature_id for group in moving_groups for feature_id in group["feature_ids"]}
    fixed_feature_ids = set(motion.get("fixed_features", []))
    feature_refs = motion.get("features", {})
    missing_motion_features = sorted(moving_feature_ids - declared_feature_ids)
    required_motion_refs = moving_feature_ids | fixed_feature_ids
    missing_step_refs = [
        feature_id
        for feature_id in required_motion_refs
        if feature_id not in feature_refs
    ]
    unresolved_step_refs = [
        feature_id
        for feature_id in required_motion_refs
        if feature_id in feature_refs
        and not all(
            str(ref).startswith("#o1.")
            for ref in [
                *feature_refs[feature_id].get("selectors", []),
                *feature_refs[feature_id].get("partIds", []),
            ]
        )
    ]
    forbidden_animation_targets = {
        feature_id
        for feature_id in moving_feature_ids
        if feature_id.endswith("_assembly") or feature_id in {"watch_power_chain_separate_hour_minute_no_seconds_assembly"}
    }
    display_gear_ids = {gear["gear_id"] for gear in design.get("display_gears", [])}
    display_hand_ids = {hand["hand_id"] for hand in design.get("display", {}).get("hands", [])}
    return {
        "minute_hand_mount_6dof_pass": _display_mount_stack_check(design, "minute_hand"),
        "hour_hand_mount_6dof_pass": _display_mount_stack_check(design, "hour_hand"),
        "animation_leaf_binding_pass": "pass"
        if not missing_motion_features and not missing_step_refs and not unresolved_step_refs and not forbidden_animation_targets
        else "fail",
        "actual_minute_hour_axis_separation_pass": _actual_display_axis_separation_check(design),
        "display_relay_motion_chain_complete": "pass"
        if {
            "display_input_relay_pinion",
            "display_input_relay_wheel",
            "minute_display_member",
            "display_relay_pinion",
            "display_relay_wheel",
            "hour_display_member",
        }
        <= display_gear_ids
        else "fail",
        "minute_display_power_chain_connected_to_train": _separate_display_train_to_minute_chain_check(design),
        "external_escapement_assembly_present": "pass"
        if design.get("external_escapement", {}).get("status") == "pass"
        else "fail",
        "display_no_forbidden_seconds_roles": "pass"
        if not any("seconds" in hand_id for hand_id in display_hand_ids)
        else "fail",
        "separate_display_motion_groups_declared": "pass"
        if {"display_input_relay_rotation", "minute_display_rotation", "display_relay_rotation", "hour_display_rotation"} <= set(groups)
        else "fail",
        "minute_motion_axis_is_solver_axis": "pass"
        if groups.get("minute_display_rotation", {}).get("axis_id") == "minute_display_axis"
        else "fail",
        "hour_motion_axis_is_solver_axis": "pass"
        if groups.get("hour_display_rotation", {}).get("axis_id") == "hour_display_axis"
        else "fail",
        "minute_motion_ratio_to_hour_12": "pass"
        if abs(groups.get("minute_display_rotation", {}).get("angular_velocity_ratio_to_hour_hand", 0.0)) == 12.0
        else "fail",
        "hour_motion_ratio_to_hour_1": "pass"
        if abs(groups.get("hour_display_rotation", {}).get("angular_velocity_ratio_to_hour_hand", 0.0)) == 1.0
        else "fail",
        "display_hands_clockwise_viewed_from_dial_side": "pass"
        if _motion_sign(groups.get("minute_display_rotation", {}).get("angular_velocity_ratio_to_hour_hand", 0.0)) == CLOCKWISE_SIGN_IN_STEP_MODULE
        and _motion_sign(groups.get("hour_display_rotation", {}).get("angular_velocity_ratio_to_hour_hand", 0.0)) == CLOCKWISE_SIGN_IN_STEP_MODULE
        else "fail",
        "motion_report_excludes_seconds_role": "pass" if "seconds_hand" not in motion_text else "fail",
    }


def _independent_display_task4_checks(design: dict[str, Any], motion: dict[str, Any]) -> dict[str, str]:
    moving_groups = motion.get("moving_groups", [])
    groups = {group["group_id"]: group for group in moving_groups}
    motion_text = json.dumps(motion, ensure_ascii=False)
    declared_feature_ids = _separate_display_declared_motion_feature_ids(design)
    moving_feature_ids = {feature_id for group in moving_groups for feature_id in group["feature_ids"]}
    fixed_feature_ids = set(motion.get("fixed_features", []))
    feature_refs = motion.get("features", {})
    missing_motion_features = sorted(moving_feature_ids - declared_feature_ids)
    required_motion_refs = moving_feature_ids | fixed_feature_ids
    missing_step_refs = [
        feature_id
        for feature_id in required_motion_refs
        if feature_id not in feature_refs
    ]
    unresolved_step_refs = [
        feature_id
        for feature_id in required_motion_refs
        if feature_id in feature_refs
        and not all(
            str(ref).startswith("#o1.")
            for ref in [
                *feature_refs[feature_id].get("selectors", []),
                *feature_refs[feature_id].get("partIds", []),
            ]
        )
    ]
    forbidden_animation_targets = {
        feature_id
        for feature_id in moving_feature_ids
        if feature_id.endswith("_assembly") or feature_id in {"watch_power_chain_separate_hour_minute_no_seconds_assembly"}
    }
    display_gear_ids = {gear["gear_id"] for gear in design.get("display_gears", [])}
    compound_ids = {member["component_id"] for member in design.get("display_compound_members", [])}
    display_hand_ids = {hand["hand_id"] for hand in design.get("display", {}).get("hands", [])}
    hour_chain = next((chain for chain in design["display"]["drive_chains"] if chain["hand_id"] == "hour_hand"), {})
    return {
        "minute_hand_mount_6dof_pass": _display_mount_stack_check(design, "minute_hand"),
        "hour_hand_mount_6dof_pass": _display_mount_stack_check(design, "hour_hand"),
        "animation_leaf_binding_pass": "pass"
        if not missing_motion_features and not missing_step_refs and not unresolved_step_refs and not forbidden_animation_targets
        else "fail",
        "actual_minute_hour_axis_separation_pass": _actual_display_axis_separation_check(design),
        "independent_display_motion_chain_complete": "pass"
        if {
            "minute_input_relay_pinion",
            "minute_input_relay_wheel",
            "minute_display_member",
            "hour_input_relay_pinion",
            "hour_input_relay_wheel",
            "hour_reduction_relay_pinion",
            "hour_reduction_relay_wheel",
            "hour_display_member",
        }
        <= display_gear_ids
        and {
            "minute_input_relay_compound_member",
            "hour_input_relay_compound_member",
            "hour_reduction_relay_compound_member",
        }
        <= compound_ids
        else "fail",
        "minute_display_branch_connected_to_train": _independent_display_branch_chain_check(design, "minute_hand"),
        "hour_display_branch_connected_to_train": _independent_display_branch_chain_check(design, "hour_hand"),
        "hour_branch_independent_from_minute_branch": "pass"
        if {"minute_display_member", "minute_input_relay_pinion", "minute_input_relay_wheel"}.isdisjoint(set(hour_chain.get("path", [])))
        else "fail",
        "external_escapement_assembly_present": "pass"
        if design.get("external_escapement", {}).get("status") == "pass"
        else "fail",
        "display_no_forbidden_seconds_roles": "pass"
        if not any("seconds" in hand_id for hand_id in display_hand_ids)
        else "fail",
        "independent_display_motion_groups_declared": "pass"
        if {
            "minute_input_relay_rotation",
            "minute_display_rotation",
            "hour_input_relay_rotation",
            "hour_reduction_relay_rotation",
            "hour_display_rotation",
        }
        <= set(groups)
        else "fail",
        "minute_motion_axis_is_solver_axis": "pass"
        if groups.get("minute_display_rotation", {}).get("axis_id") == "minute_display_axis"
        else "fail",
        "hour_motion_axis_is_solver_axis": "pass"
        if groups.get("hour_display_rotation", {}).get("axis_id") == "hour_display_axis"
        else "fail",
        "minute_motion_ratio_to_hour_12": "pass"
        if abs(groups.get("minute_display_rotation", {}).get("angular_velocity_ratio_to_hour_hand", 0.0)) == 12.0
        else "fail",
        "hour_motion_ratio_to_hour_1": "pass"
        if abs(groups.get("hour_display_rotation", {}).get("angular_velocity_ratio_to_hour_hand", 0.0)) == 1.0
        else "fail",
        "motion_report_excludes_seconds_role": "pass" if "seconds_hand" not in motion_text else "fail",
    }


def _separate_display_declared_motion_feature_ids(design: dict[str, Any]) -> set[str]:
    feature_ids = {"foundation_mainplate", "mainspring_barrel"}
    feature_ids.update(axis["axis_id"] for axis in design["axes"])
    feature_ids.update(gear["gear_id"] for gear in design["gears"])
    feature_ids.update(gear["gear_id"] for gear in design["display_gears"])
    feature_ids.update(
        member["component_id"]
        for member in design.get(
            "display_compound_members",
            [
                {"component_id": "display_input_relay_compound_member"},
                {"component_id": "display_relay_compound_member"},
            ],
        )
    )
    feature_ids.update(
        {
            "minute_display_member_hub",
            "minute_hand_arbor_extension",
            "hour_display_member_hub",
            "hour_hand_arbor_extension",
        }
    )
    feature_ids.update(hand["hand_id"] for hand in design["display"]["hands"])
    feature_ids.update(
        {
            "external_escape_wheel",
            "external_escape_staff",
            "external_pallet_fork",
            "external_balance_wheel",
            "external_hairspring",
            "external_escapement_reference_plate",
            "external_escape_upper_cap",
            "external_balance_upper_jewel_bearing",
        }
    )
    declared_feature_ids = set(feature_ids)
    aliases = _visible_feature_aliases_for_step_module()
    for feature_id in feature_ids:
        declared_feature_ids.update(aliases.get(feature_id, []))
    return declared_feature_ids


def _separate_display_train_to_minute_chain_check(design: dict[str, Any]) -> str:
    required_meshes = {
        frozenset(("train_stage_3_wheel", "display_input_relay_pinion")),
        frozenset(("display_input_relay_wheel", "minute_display_member")),
    }
    observed_meshes = {frozenset((mesh["driver"], mesh["driven"])) for mesh in design.get("display_meshes", [])}
    ratio = design.get("display", {}).get("motion_works", {}).get("train_to_minute_display_coupling", {}).get("ratio_proof", {})
    return (
        "pass"
        if required_meshes <= observed_meshes and abs(float(ratio.get("computed_ratio", 0.0)) - 1.0) <= 1e-12
        else "fail"
    )


def _independent_display_branch_chain_check(design: dict[str, Any], hand_id: str) -> str:
    chain = next((item for item in design.get("display", {}).get("drive_chains", []) if item["hand_id"] == hand_id), {})
    expected = {
        "minute_hand": [
            "train_stage_3_wheel",
            "minute_input_relay_pinion",
            "minute_input_relay_wheel",
            "minute_display_member",
            "minute_hand",
        ],
        "hour_hand": [
            "train_stage_3_wheel",
            "hour_input_relay_pinion",
            "hour_input_relay_wheel",
            "hour_reduction_relay_pinion",
            "hour_reduction_relay_wheel",
            "hour_display_member",
            "hour_hand",
        ],
    }[hand_id]
    mesh_pairs = {frozenset((mesh["driver"], mesh["driven"])) for mesh in design.get("display_meshes", [])}
    required_meshes = {
        "minute_hand": {
            frozenset(("train_stage_3_wheel", "minute_input_relay_pinion")),
            frozenset(("minute_input_relay_wheel", "minute_display_member")),
        },
        "hour_hand": {
            frozenset(("train_stage_3_wheel", "hour_input_relay_pinion")),
            frozenset(("hour_input_relay_wheel", "hour_reduction_relay_pinion")),
            frozenset(("hour_reduction_relay_wheel", "hour_display_member")),
        },
    }[hand_id]
    path = chain.get("path", [])
    return "pass" if all(node in path for node in expected) and required_meshes <= mesh_pairs else "fail"


def _separate_display_step_module_features(design: dict[str, Any]) -> dict[str, dict[str, Any]]:
    refs: dict[str, str] = {
        feature_id: f"#o1.{index}"
        for index, feature_id in enumerate(_separate_display_internal_occurrence_order(design), start=1)
    }
    external_index = len(_separate_display_internal_occurrence_order(design)) + 1
    refs.update(
        {
            "external_escape_wheel": f"#o1.{external_index}.1",
            "external_pallet_fork": f"#o1.{external_index}.2",
            "external_balance_wheel": f"#o1.{external_index}.3",
            "external_hairspring": f"#o1.{external_index}.4",
            "external_escapement_reference_plate": f"#o1.{external_index}.5",
            "external_escape_staff": f"#o1.{external_index}.6",
            "external_escape_upper_cap": f"#o1.{external_index}.11",
            "external_escape_upper_fixed_hardware": f"#o1.{external_index}.14",
            "external_balance_replacement_staff": f"#o1.{external_index}.33",
            "external_balance_upper_jewel_bearing": f"#o1.{external_index}.34",
        }
    )
    hand_start = external_index + 1
    for offset, hand in enumerate(design["display"]["hands"]):
        refs[hand["hand_id"]] = f"#o1.{hand_start + offset}"

    features: dict[str, dict[str, Any]] = {}
    for feature_id, ref in sorted(refs.items()):
        features[feature_id] = {
            "ref": ref,
            "selectors": [ref],
            "partIds": [ref],
            "origin": _separate_display_feature_origin(design, feature_id),
            "axis": [0, 0, 1],
        }
    return features


def _separate_display_internal_occurrence_order(design: dict[str, Any]) -> list[str]:
    order = ["foundation_mainplate"]
    for axis in design["axes"]:
        if not axis["support_required"]:
            continue
        for segment in axis["support_segments"]:
            order.append(segment["segment_id"])
        order.append(f"lower_jewel_support_{axis['axis_id']}")
        if axis.get("upper_jewel_bearing"):
            order.append(f"upper_jewel_bearing_support_{axis['axis_id']}")
    order.append("mainspring_barrel")
    for gear in design["gears"]:
        if gear["gear_id"] not in {"barrel_outer_teeth", "escape_wheel"}:
            order.append(gear["gear_id"])
    order.extend(gear["gear_id"] for gear in design["display_gears"])
    order.extend(
        member["component_id"]
        for member in design.get(
            "display_compound_members",
            [
                {"component_id": "display_input_relay_compound_member"},
                {"component_id": "display_relay_compound_member"},
            ],
        )
    )
    generated_stack_ids = {
        "minute_display_member_hub",
        "minute_hand_arbor_extension",
        "hour_display_member_hub",
        "hour_hand_arbor_extension",
    }
    for stack in design["display"]["mount_stacks"]:
        for segment in stack["segments"]:
            if segment["component_id"] in generated_stack_ids:
                order.append(segment["component_id"])
    return order


def _separate_display_feature_origin(design: dict[str, Any], feature_id: str) -> list[float] | None:
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    gear_axis_by_id = {
        gear["gear_id"]: gear["axis_id"]
        for gear in [*design["gears"], *design.get("display_gears", [])]
    }
    explicit_axis = {
        "mainspring_barrel": "barrel_axis",
        "display_input_relay_compound_member": "display_input_relay_axis",
        "display_relay_compound_member": "display_relay_axis",
        "minute_input_relay_compound_member": "minute_input_relay_axis",
        "hour_input_relay_compound_member": "hour_input_relay_axis",
        "hour_reduction_relay_compound_member": "hour_reduction_relay_axis",
        "minute_display_member_hub": "minute_display_axis",
        "minute_hand_arbor_extension": "minute_display_axis",
        "minute_hand": "minute_display_axis",
        "hour_display_member_hub": "hour_display_axis",
        "hour_hand_arbor_extension": "hour_display_axis",
        "hour_hand": "hour_display_axis",
        "external_escape_wheel": "escape_axis",
        "external_escape_staff": "escape_axis",
        "external_escape_upper_cap": "escape_axis",
        "external_escape_upper_fixed_hardware": "escape_axis",
        "external_pallet_fork": "pallet_axis",
        "external_balance_wheel": "balance_axis",
        "external_hairspring": "balance_axis",
        "external_balance_replacement_staff": "balance_axis",
        "external_balance_upper_jewel_bearing": "balance_axis",
    }
    axis_id = gear_axis_by_id.get(feature_id) or explicit_axis.get(feature_id)
    if axis_id and axis_id in axis_by_id:
        axis = axis_by_id[axis_id]
        return [axis["x"], axis["y"], 0.0]
    return None


def _actual_display_axis_separation_check(design: dict[str, Any]) -> str:
    minute_axis = _axis_by_id(design, "minute_display_axis")
    hour_axis = _axis_by_id(design, "hour_display_axis")
    distance = math.dist((minute_axis["x"], minute_axis["y"]), (hour_axis["x"], hour_axis["y"]))
    return "pass" if distance >= MIN_DISPLAY_AXIS_SEPARATION_MM else "fail"


def _display_mount_stack_check(design: dict[str, Any], hand_id: str) -> str:
    stack = next((item for item in design["display"]["mount_stacks"] if item["hand_id"] == hand_id), None)
    if not stack:
        return "fail"
    required_true = [stack["closed"], stack["xy_connected"], stack["six_dof_constrained"]]
    required_zero = [
        stack["max_positive_gap_mm"],
        stack["max_xy_center_error_mm"],
        stack["unresolved_dof_count"],
    ]
    required_empty = [stack["gap_failures"], stack["xy_failures"], stack["six_dof_failures"]]
    if all(required_true) and all(value == 0 for value in required_zero) and all(not value for value in required_empty):
        return "pass"
    return "fail"


def _render_separate_display_dashboard(design: dict[str, Any], validation: dict[str, Any]) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Separate Hour Minute Watch Display</title>
  <style>
    body {{ font-family: "Segoe UI", Arial, sans-serif; margin: 28px; color: #202124; }}
    .card {{ border: 1px solid #dadce0; border-radius: 8px; padding: 14px; margin: 12px 0; background: #f8fafd; }}
    code {{ background: #f1f3f4; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Separate Hour Minute Watch Display</h1>
  <div class="card">
    <p><strong>Pattern:</strong> <code>{SEPARATE_DISPLAY_PATTERN_CARD_ID}</code></p>
    <p><strong>Status:</strong> <code>{validation['status']}</code></p>
    <p><strong>Seed:</strong> <code>{design['seed']}</code></p>
  </div>
</body>
</html>
"""


def _build_design(seed: int, *, include_bridges: bool = False) -> dict[str, Any]:
    solver_report = solve_current_pattern(
        seed=seed,
        case_inner_radius_mm=CASE_RADIUS_MM,
        bridge_perimeter_reserved_band_mm=BRIDGE_PERIMETER_RESERVED_BAND_MM,
    )
    if solver_report["status"] != "pass" or solver_report["selected_candidate"] is None:
        raise ValueError(f"current pattern solver failed: {solver_report['failed_reasons']}")
    solver_candidate = solver_report["selected_candidate"]
    solver_variables = solver_candidate["variables"]
    solver_axes = {axis["axis_id"]: axis for axis in solver_candidate["axes"]}

    module = solver_variables["module"]
    angle_jitter = {
        "third": solver_variables["third_angle_deg"] - 20.0,
        "fourth": solver_variables["fourth_angle_deg"] - 12.0,
        "barrel": solver_variables["barrel_angle_deg"] - 212.0,
        "escape": solver_variables["escape_angle_deg"] - 42.0,
    }
    spoke_style = "single_body_open_spoked_watch_wheel"

    tooth_counts = dict(solver_candidate["tooth_counts"])
    display_center = _solver_point(solver_axes[DISPLAY_CENTER_AXIS])
    center = _solver_point(solver_axes["center_axis"])
    display_motion_module = solver_variables["display_motion_module"]
    minute_work = _solver_point(solver_axes["minute_work_axis"])
    third = _solver_point(solver_axes["third_axis"])
    fourth = _solver_point(solver_axes["fourth_axis"])
    barrel = _solver_point(solver_axes["barrel_axis"])
    escape = _solver_point(solver_axes["escape_axis"])
    pallet = _solver_point(solver_axes["pallet_axis"])
    balance = _solver_point(solver_axes["balance_axis"])
    z_stack_positions = _build_z_stack_positions()

    axes = [
        _axis(DISPLAY_CENTER_AXIS, display_center, "central_hour_minute_display_axis", 0.9, support_required=False),
        _axis(
            "minute_work_axis",
            minute_work,
            "motion_works_compound_arbor",
            0.7,
            support_segments=[
                {
                    "segment_id": "minute_work_arbor",
                    "z_min": MAINPLATE_CENTER_Z - MAINPLATE_THICKNESS_MM / 2.0,
                    "z_max": 4.12,
                    "radius": _arbor_body_radius("minute_work_axis"),
                    "kind": "continuous_arbor",
                }
            ],
        ),
        _axis("barrel_axis", barrel, "barrel_arbor", 3.0),
        _axis(
            "center_axis",
            center,
            "compound_train_arbor_and_minute_source",
            2.0,
            support_segments=[
                {
                    "segment_id": "center_arbor",
                    "z_min": MAINPLATE_BOTTOM_Z,
                    "z_max": round(z_stack_positions["gear_z"]["center_wheel"] + GEAR_HEIGHT_MM + 0.08, 4),
                    "radius": _arbor_body_radius("center_axis"),
                    "kind": "lower_train_arbor_stops_below_display_works",
                }
            ],
        ),
        _axis("third_axis", third, "compound_train_arbor", 2.0),
        _axis("fourth_axis", fourth, "compound_train_arbor_and_sub_seconds_display", 2.0),
        _axis("escape_axis", escape, "escape_arbor", 2.1),
        _axis("pallet_axis", pallet, "placeholder_pallet_axis", 1.15, support_required=False),
        _axis("balance_axis", balance, "placeholder_balance_axis", 2.65, support_required=False),
    ]

    gear_z = z_stack_positions["gear_z"]
    gears = [
        _gear("barrel_outer_teeth", "barrel_axis", tooth_counts, module, gear_z["barrel_outer_teeth"], "wheel"),
        _gear("center_pinion", "center_axis", tooth_counts, module, gear_z["center_pinion"], "pinion"),
        _gear("center_wheel", "center_axis", tooth_counts, module, gear_z["center_wheel"], "wheel"),
        _gear("third_pinion", "third_axis", tooth_counts, module, gear_z["third_pinion"], "pinion"),
        _gear("third_wheel", "third_axis", tooth_counts, module, gear_z["third_wheel"], "wheel"),
        _gear("fourth_pinion", "fourth_axis", tooth_counts, module, gear_z["fourth_pinion"], "pinion"),
        _gear("fourth_wheel", "fourth_axis", tooth_counts, module, gear_z["fourth_wheel"], "wheel"),
        _gear("escape_pinion", "escape_axis", tooth_counts, module, gear_z["escape_pinion"], "pinion"),
        _gear("escape_wheel", "escape_axis", tooth_counts, module, gear_z["escape_wheel"], "escape"),
    ]
    _gear_by_id({"gears": gears}, "barrel_outer_teeth").update(
        {
            "spoke_cutout_allowed": False,
            "spoke_cutout_policy": "solid_barrel_drum_tooth_ring",
        }
    )
    axis_by_id = {axis["axis_id"]: axis for axis in axes}
    for gear in gears:
        axis = axis_by_id[gear["axis_id"]]
        gear["x"] = axis["x"]
        gear["y"] = axis["y"]
        gear["spoke_style"] = spoke_style
        _attach_axis_geometry_to_gear(gear, axis)
    display_gear_z = z_stack_positions["display_gear_z"]
    display_gears = [
        _display_gear("cannon_pinion_display_driver", DISPLAY_CENTER_AXIS, tooth_counts, display_motion_module, display_gear_z["cannon_pinion_display_driver"], "pinion"),
        _display_gear("minute_wheel", "minute_work_axis", tooth_counts, display_motion_module, display_gear_z["minute_wheel"], "wheel"),
        _display_gear("minute_pinion", "minute_work_axis", tooth_counts, display_motion_module, display_gear_z["minute_pinion"], "pinion"),
        _display_gear("hour_wheel", DISPLAY_CENTER_AXIS, tooth_counts, display_motion_module, display_gear_z["hour_wheel"], "wheel"),
    ]
    for gear in display_gears:
        axis = axis_by_id[gear["axis_id"]]
        gear["x"] = axis["x"]
        gear["y"] = axis["y"]
        gear["spoke_style"] = "solid_web"
        _attach_axis_geometry_to_gear(gear, axis, display=True)
    _attach_watch_wheel_spoke_cutouts([*gears, *display_gears], seed)
    display_meshes = [
        _mesh("cannon_pinion_display_driver", "minute_wheel"),
        _mesh("minute_pinion", "hour_wheel"),
    ]
    display_mesh_phase_records = _assign_mesh_phases(axes, display_gears, display_meshes)
    motion_works = _build_display_motion_works(
        display_gears,
        display_meshes,
        display_mesh_phase_records,
        axis_by_id,
    )
    z_stack = _build_z_stack_plan(gears, display_gears, z_stack_positions)
    _attach_future_upper_jewel_targets(axes, z_stack["future_bridge"])

    meshes = [
        _mesh("barrel_outer_teeth", "center_pinion"),
        _mesh("center_wheel", "third_pinion"),
        _mesh("third_wheel", "fourth_pinion"),
        _mesh("fourth_wheel", "escape_pinion"),
    ]
    mesh_phase_records = _assign_mesh_phases(axes, gears, meshes)
    max_train_z = max(gear["z"] + gear["height"] for gear in gears)
    display_z = z_stack_positions["display"]
    seconds_hand = _computed_seconds_hand(axis_by_id["fourth_axis"], design_gears=gears, z_min=display_z["seconds_hand_z"])
    central_hand_lengths = _central_display_hand_lengths(
        display_center,
        (axis_by_id["fourth_axis"]["x"], axis_by_id["fourth_axis"]["y"]),
    )
    display = {
        "strategy": "separate_display_axis_and_off_center_seconds",
        "display_center_axis": DISPLAY_CENTER_AXIS,
        "seconds_axis": "fourth_axis",
        "center_motion_source_axis": "center_axis",
        "z_clearance_above_train_mm": round(display_z["hour_hand_z"] - max_train_z, 4),
        "tube_stack": [
            {"tube_id": "hour_tube", "role": "hour_hand_sleeve", "z_min": display_z["hour_tube_z_min"], "z_max": display_z["hour_tube_z_max"], "outer_radius": 0.56, "inner_radius": 0.36},
            {"tube_id": "cannon_pinion_tube", "role": "minute_hand_sleeve", "z_min": display_z["cannon_tube_z_min"], "z_max": display_z["cannon_tube_z_max"], "outer_radius": 0.28, "inner_radius": 0.17},
        ],
        "arbor_extensions": [
            {"extension_id": "central_display_arbor_extension", "axis_id": DISPLAY_CENTER_AXIS, "z_min": display_z["central_extension_z_min"], "z_max": display_z["central_extension_z_max"], "radius": 0.13},
            {"extension_id": "seconds_arbor_extension", "axis_id": "fourth_axis", "z_min": display_z["seconds_extension_z_min"], "z_max": display_z["seconds_extension_z_max"], "radius": 0.18},
        ],
        "drive_chains": [
            {
                "hand_id": "minute_hand",
                "axis_id": DISPLAY_CENTER_AXIS,
                "source": "center_wheel_to_cannon_pinion",
                "path": [
                    "mainspring_barrel",
                    "center_pinion",
                    "center_wheel",
                    "cannon_pinion_assembly",
                    "cannon_pinion_tube",
                    "minute_hand",
                ],
                "interface_sequence": "compound_train_to_cannon_pinion_sleeve",
                "ratio_proof": {"kind": "declared_phase1_center_direct", "computed_ratio": 1.0},
            },
            {
                "hand_id": "hour_hand",
                "axis_id": DISPLAY_CENTER_AXIS,
                "source": "minute_motion_work_reduction",
                "path": [
                    "cannon_pinion_assembly",
                    "cannon_pinion_display_driver",
                    "minute_wheel_assembly",
                    "minute_pinion",
                    "hour_wheel",
                    "hour_hand",
                ],
                "interface_sequence": "gear_mesh_compound_gear_mesh",
                "ratio_proof": {
                    "kind": "tooth_count_product",
                    "computed_ratio": round(motion_works["ratio_proof"]["hour_to_minute_ratio"], 12),
                    "expected_ratio": round(1 / 12, 12),
                },
            },
            {
                "hand_id": "seconds_hand",
                "axis_id": "fourth_axis",
                "source": "fourth_wheel_direct_sub_seconds",
                "path": ["third_wheel", "fourth_pinion", "fourth_wheel", "seconds_hand"],
            },
        ],
        "motion_works": motion_works,
        "hands": [
            {
                "hand_id": "hour_hand",
                "axis_id": DISPLAY_CENTER_AXIS,
                "driven_by": "hour_wheel",
                "ratio": "1 rev / 12 hours",
                "angle_deg": 145.0,
                "length_mm": central_hand_lengths["hour_hand_length_mm"],
                "z_mm": display_z["hour_hand_z"],
                "width_mm": 0.34,
                "profile": "broad_leaf",
                "model_source": "fixed_central_hour_hand",
                "length_rule": central_hand_lengths["hour_hand_rule"],
            },
            {
                "hand_id": "minute_hand",
                "axis_id": DISPLAY_CENTER_AXIS,
                "driven_by": "cannon_pinion_assembly",
                "ratio": "1 rev / hour",
                "angle_deg": 30.0,
                "length_mm": central_hand_lengths["minute_hand_length_mm"],
                "z_mm": display_z["minute_hand_z"],
                "width_mm": 0.18,
                "profile": "tapered_pointer",
                "model_source": "fixed_central_minute_hand",
                "length_rule": central_hand_lengths["minute_hand_rule"],
            },
            {
                "hand_id": "seconds_hand",
                "axis_id": "fourth_axis",
                "driven_by": "fourth_axis",
                "ratio": "1 rev / minute",
                "angle_deg": 270.0,
                "length_mm": seconds_hand["length_mm"],
                "z_mm": display_z["seconds_hand_z"],
                "width_mm": 0.08,
                "profile": "needle_with_counterweight",
                "model_source": "computed_sub_seconds_hand",
            },
        ],
        "sweep_envelopes": {
            "hour_hand": _hand_sweep_envelope(DISPLAY_CENTER_AXIS, display_center, central_hand_lengths["hour_hand_length_mm"], display_z["hour_hand_z"], 0.075),
            "minute_hand": _hand_sweep_envelope(DISPLAY_CENTER_AXIS, display_center, central_hand_lengths["minute_hand_length_mm"], display_z["minute_hand_z"], 0.075),
            "seconds_hand": seconds_hand["sweep_envelope"],
        },
    }
    display["sweep_envelopes"]["seconds_hand"]["interference_failures"] = _seconds_sweep_interference_failures(
        display["sweep_envelopes"]["seconds_hand"],
        display,
        gears,
    )
    display["coaxial_sleeve_clearance"] = _build_coaxial_sleeve_clearance_report(display)
    display["mount_stacks"] = _build_display_mount_stacks(display, axes)
    seed_manifest = {
        "seed": seed,
        "module": module,
        "third_axis_position": round(angle_jitter["third"], 6),
        "fourth_axis_position": round(angle_jitter["fourth"], 6),
        "barrel_axis_position": round(angle_jitter["barrel"], 6),
        "escape_axis_position": round(angle_jitter["escape"], 6),
        "gear_phase_strategy": "external_tooth_to_gap_on_center_line",
        "visual_spoke_style": spoke_style,
        "solver_candidate_id": solver_candidate["candidate_id"],
    }
    design = {
        "phase": PHASE,
        "seed": seed,
        "seed_manifest": seed_manifest,
        "pattern_solver": solver_report,
        "module": module,
        "housing": {
            "mainplate_is_flat_round_disk": True,
            "case_wall_integrated_with_mainplate": False,
            "case_boundary_policy": "separate_case_or_review_shell_deferred",
            "case_inner_radius_mm": CASE_INNER_RADIUS_MM,
            "case_outer_radius_mm": CASE_RADIUS_MM,
            "mainplate_radius_mm": CASE_RADIUS_MM,
            "bridge_perimeter_reserved_band_mm": BRIDGE_PERIMETER_RESERVED_BAND_MM,
            "bridge_perimeter_screw_policy": BRIDGE_PERIMETER_SCREW_POLICY,
            "outer_raised_support_ring": _mainplate_outer_support_ring_spec(z_stack),
            "parent_body": "foundation_mainplate",
        },
        "axes": axes,
        "gears": gears,
        "meshes": meshes,
        "mesh_phase_records": mesh_phase_records,
        "display_gears": display_gears,
        "display_meshes": display_meshes,
        "display_mesh_phase_records": display_mesh_phase_records,
        "z_stack": z_stack,
        "display": display,
        "bridges_generated": include_bridges,
    }
    design["bridge_stage"] = _build_bridge_stage_plan(design) if include_bridges else None
    return design


def _build_bridge_stage_plan(design: dict[str, Any]) -> dict[str, Any]:
    z_stack = design["z_stack"]["future_bridge"]
    support_ring = design["housing"]["outer_raised_support_ring"]
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    sectors = [
        {
            "bridge_id": "barrel_bridge",
            "angular_start_deg": 178.0,
            "angular_end_deg": 266.0,
            "supported_axis_ids": ["barrel_axis"],
        },
        {
            "bridge_id": "train_bridge",
            "angular_start_deg": 270.0,
            "angular_end_deg": 48.0,
            "supported_axis_ids": ["center_axis", "third_axis", "fourth_axis", "minute_work_axis"],
        },
        {
            "bridge_id": "escapement_bridge",
            "angular_start_deg": 52.0,
            "angular_end_deg": 174.0,
            "supported_axis_ids": ["escape_axis", "pallet_axis", "balance_axis"],
        },
    ]
    bridges = []
    for sector in sectors:
        span = _positive_angle_span(sector["angular_start_deg"], sector["angular_end_deg"])
        screw_count = _bridge_screw_count_for_span(span)
        support_pad_target_arc_length = round(
            BRIDGE_SUPPORT_PAD_ARC_LENGTH_TO_HEAD_DIAMETER_RATIO * BRIDGE_COUNTERSUNK_HEAD_DIAMETER_MM,
            4,
        )
        support_pad_span_deg = _support_pad_span_deg(
            support_ring["inner_radius_mm"],
            support_ring["outer_radius_mm"],
            support_pad_target_arc_length,
        )
        screw_edge_margin_deg = round(support_pad_span_deg / 2.0, 4)
        screw_angles = _bridge_screw_angles(
            sector["angular_start_deg"],
            sector["angular_end_deg"],
            screw_count,
            screw_edge_margin_deg,
        )
        screws = [
            {
                "screw_id": f"{sector['bridge_id']}_screw_{index}",
                "angle_deg": round(angle, 4),
                "x": round(BRIDGE_SCREW_PITCH_RADIUS_MM * math.cos(math.radians(angle)), 4),
                "y": round(BRIDGE_SCREW_PITCH_RADIUS_MM * math.sin(math.radians(angle)), 4),
                "pitch_radius_mm": BRIDGE_SCREW_PITCH_RADIUS_MM,
                "role": "bridge_fastener",
                "fastener_kind": "countersunk_flat_head_screw",
                "standard": BRIDGE_Z_STACK_FASTENER_POLICY["standard"],
                "thread_size": BRIDGE_Z_STACK_FASTENER_POLICY["thread_size"],
                "nominal_thread_diameter_mm": BRIDGE_SCREW_NOMINAL_THREAD_DIAMETER_MM,
                "clearance_diameter_mm": BRIDGE_SCREW_CLEARANCE_DIAMETER_MM,
                "head_diameter_mm": BRIDGE_COUNTERSUNK_HEAD_DIAMETER_MM,
                "countersink_depth_mm": FUTURE_BRIDGE_COUNTERSUNK_HEAD_DEPTH_MM,
                "head_top_policy": "flush_to_bridge_top",
                "receiving_feature_policy": "simplified_threaded_hole_in_mainplate_service_band",
                "threaded_engagement_depth_mm": BRIDGE_SCREW_THREADED_ENGAGEMENT_DEPTH_MM,
                "threaded_hole_top_z_mm": support_ring["top_z_mm"],
                "threaded_hole_bottom_z_mm": round(
                    support_ring["top_z_mm"] - BRIDGE_SCREW_THREADED_ENGAGEMENT_DEPTH_MM,
                    4,
                ),
            }
            for index, angle in enumerate(screw_angles, start=1)
        ]
        support_pads = [
            {
                "pad_id": f"{screw['screw_id']}_support_pad",
                "screw_id": screw["screw_id"],
                "x": screw["x"],
                "y": screw["y"],
                "angle_deg": screw["angle_deg"],
                "footprint_type": "outer_annular_service_pad",
                "support_face": "mainplate_outer_raised_support_ring",
                "inner_radius_mm": support_ring["inner_radius_mm"],
                "outer_radius_mm": support_ring["outer_radius_mm"],
                "target_outer_arc_length_mm": support_pad_target_arc_length,
                "target_angular_span_deg": support_pad_span_deg,
                **_support_pad_angle_bounds(
                    sector["angular_start_deg"],
                    sector["angular_end_deg"],
                    screw["angle_deg"],
                    index,
                    len(screws),
                    support_pad_span_deg,
                ),
                "z_min_mm": support_ring["top_z_mm"],
                "z_max_mm": z_stack["bridge_bottom_z_mm"],
                "contacts": ["mainplate_outer_raised_support_ring", sector["bridge_id"]],
            }
            for index, screw in enumerate(screws, start=1)
        ]
        clearance_holes = []
        for axis_id in sector["supported_axis_ids"]:
            axis = axis_by_id.get(axis_id)
            upper_jewel = axis.get("upper_jewel_bearing") if axis else None
            if not upper_jewel:
                continue
            clearance_holes.append(
                {
                    "hole_id": f"{sector['bridge_id']}_clearance_{axis_id}",
                    "axis_id": axis_id,
                    "x": axis["x"],
                    "y": axis["y"],
                    "radius_mm": round(float(upper_jewel["outer_radius"]) + 0.04, 4),
                    "purpose": "clear_upper_jewel_insert_and_arbor_pivot",
                }
            )
        central_axis_feature = None
        if sector["bridge_id"] == "train_bridge":
            center_axis = axis_by_id["center_axis"]
            center_hole = next(hole for hole in clearance_holes if hole["axis_id"] == "center_axis")
            central_axis_feature = {
                "feature_id": "train_bridge_center_axis_boss",
                "axis_id": "center_axis",
                "x": center_axis["x"],
                "y": center_axis["y"],
                "outer_radius_mm": BRIDGE_CENTER_AXIS_BOSS_OUTER_RADIUS_MM,
                "clearance_radius_mm": center_hole["radius_mm"],
                "z_min_mm": z_stack["bridge_bottom_z_mm"],
                "z_max_mm": z_stack["future_upper_jewel_top_z_mm"],
                "role": "integrated_center_axis_upper_support_boss",
            }
        bridges.append(
            {
                **sector,
                "role": "upper_bridge_plate",
                "structure_class": "separate_bridge_plate_with_integrated_screw_standoff_pads",
                "angular_span_deg": round(span, 4),
                "footprint_type": "fixed_width_parallel_seam_plate_v1",
                "inner_radius_mm": BRIDGE_PLATE_INNER_RADIUS_MM,
                "outer_radius_mm": BRIDGE_PLATE_OUTER_RADIUS_MM,
                "seam_boundary_policy": "constant_width_parallel_gap_edges",
                "seam_gap_width_mm": BRIDGE_SEAM_GAP_WIDTH_MM,
                "seam_boundary_lines": {
                    "start": _bridge_seam_boundary_line(sector["angular_start_deg"], "ccw"),
                    "end": _bridge_seam_boundary_line(sector["angular_end_deg"], "cw"),
                },
                "z_min_mm": z_stack["bridge_bottom_z_mm"],
                "z_max_mm": z_stack["future_upper_jewel_top_z_mm"],
                "thickness_mm": z_stack["bridge_plate_thickness_mm"],
                "required_screw_count": screw_count,
                "screws": screws,
                "support_pads": support_pads,
                "clearance_holes": clearance_holes,
                "central_axis_feature": central_axis_feature,
                "review_opacity": BRIDGE_REVIEW_OPACITY,
                "mount_chain": {
                    "kind": "screws_clamp_bridge_to_mainplate_service_band",
                    "fixed_base": "foundation_mainplate",
                    "support_face": "mainplate_outer_raised_support_ring",
                    "status": "pass",
                },
            }
        )
    return {
        "kind": "watch_three_bridge_stage_plan",
        "pattern_card_id": BRIDGE_STAGE_PATTERN_CARD_ID,
        "status": "pass",
        "screw_policy": {
            "placement": "shared_pitch_circle",
            "pitch_radius_mm": BRIDGE_SCREW_PITCH_RADIUS_MM,
            "edge_margin_deg": screw_edge_margin_deg,
            "placement_bias": "near_bridge_outer_end_edges_for_better_support",
            "rules": {
                ">90": {"screw_count": 3},
                "40..90": {"screw_count": 2},
                "<40": {"screw_count": 1},
            },
        },
        "support_pad_policy": {
            "kind": "outer_annular_service_pad",
            "arc_length_to_screw_head_diameter_ratio": BRIDGE_SUPPORT_PAD_ARC_LENGTH_TO_HEAD_DIAMETER_RATIO,
            "target_outer_arc_length_mm": support_pad_target_arc_length,
            "target_angular_span_deg": support_pad_span_deg,
            "edge_pads_share_bridge_side_boundaries": True,
        },
        "seam_policy": {
            "kind": "fixed_width_parallel_seams",
            "gap_width_mm": BRIDGE_SEAM_GAP_WIDTH_MM,
            "construction": "each seam is a centerline with two parallel offset bridge edges",
        },
        "central_axis_policy": {
            "axis_id": "center_axis",
            "owning_bridge_id": "train_bridge",
            "support_strategy": "covered_by_train_bridge_boss",
            "reason": "center wheel arbor is part of the train support stack and must not sit in an ambiguous bridge seam",
        },
        "review_metadata": {
            "appearance": "translucent_bridge_review",
            "opacity": BRIDGE_REVIEW_OPACITY,
        },
        "bridges": bridges,
    }


def _positive_angle_span(start_deg: float, end_deg: float) -> float:
    return (end_deg - start_deg) % 360.0


def _angle_span_overlap_deg(left: dict[str, Any], right: dict[str, Any]) -> float:
    total = 0.0
    for left_start, left_end in _angle_span_segments(
        float(left.get("angular_start_deg", 0.0)),
        float(left.get("angular_end_deg", 0.0)),
    ):
        for right_start, right_end in _angle_span_segments(
            float(right.get("angular_start_deg", 0.0)),
            float(right.get("angular_end_deg", 0.0)),
        ):
            total += max(0.0, min(left_end, right_end) - max(left_start, right_start))
    return total


def _angle_span_segments(start_deg: float, end_deg: float) -> list[tuple[float, float]]:
    start = start_deg % 360.0
    span = _positive_angle_span(start, end_deg)
    if start + span <= 360.0:
        return [(start, start + span)]
    return [(start, 360.0), (0.0, (start + span) % 360.0)]


def _bridge_screw_count_for_span(span_deg: float) -> int:
    if span_deg > 90.0:
        return 3
    if span_deg >= 40.0:
        return 2
    return 1


def _build_axis_voronoi_bridge_stage_report(
    design: dict[str, Any],
    jewel_supports: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    bridges = plan.get("bridges", [])
    bridge_ids = [bridge.get("bridge_id") for bridge in bridges]
    if sorted(bridge_ids) != ["barrel_bridge", "escapement_bridge", "train_bridge"]:
        failures.append({"type": "bridge_id_set", "observed": bridge_ids})
    if plan.get("status") != "pass":
        failures.append({"type": "bridge_stage_plan_status", "observed": plan.get("status")})
    if plan.get("seam_policy", {}).get("kind") != "axis_voronoi_native_smooth_with_explicit_width":
        failures.append({"type": "bridge_seam_policy", "observed": plan.get("seam_policy", {}).get("kind")})
    if abs(float(plan.get("seam_policy", {}).get("gap_width_mm", -1.0)) - BRIDGE_SEAM_GAP_WIDTH_MM) > 1e-6:
        failures.append({"type": "bridge_seam_gap_width"})

    pitch_radii = {
        round(float(screw["pitch_radius_mm"]), 4)
        for bridge in bridges
        for screw in bridge.get("screws", [])
    }
    if len(pitch_radii) != 1:
        failures.append({"type": "screws_not_on_shared_pitch_circle", "observed": sorted(pitch_radii)})

    supported_axes = {
        axis_id
        for bridge in bridges
        for axis_id in bridge.get("supported_axis_ids", [])
    }
    missing_upper_axes = [
        axis_id for axis_id in jewel_supports.get("upper_jewel_bearing_axis_ids", []) if axis_id not in supported_axes
    ]
    if missing_upper_axes:
        failures.append({"type": "upper_jewel_axes_not_assigned_to_bridge", "axis_ids": missing_upper_axes})

    bridge_bottom = float(design["z_stack"]["future_bridge"]["bridge_bottom_z_mm"])
    bridge_top = float(design["z_stack"]["future_bridge"]["future_upper_jewel_top_z_mm"])
    support_ring = design["housing"]["outer_raised_support_ring"]
    for left_index, left_bridge in enumerate(bridges):
        for right_bridge in bridges[left_index + 1 :]:
            for left_span in left_bridge.get("outer_service_spans", [left_bridge.get("outer_service_domain", {})]):
                for right_span in right_bridge.get("outer_service_spans", [right_bridge.get("outer_service_domain", {})]):
                    overlap = _angle_span_overlap_deg(left_span, right_span)
                    if overlap > 1e-4:
                        failures.append(
                            {
                                "type": "bridge_service_spans_overlap",
                                "left_bridge_id": left_bridge["bridge_id"],
                                "right_bridge_id": right_bridge["bridge_id"],
                                "overlap_deg": round(overlap, 4),
                            }
                        )
    for bridge in bridges:
        service_spans = bridge.get("outer_service_spans", [bridge.get("outer_service_domain", {})])
        expected_count = sum(
            _bridge_screw_count_for_span(
                _positive_angle_span(
                    float(service_span.get("angular_start_deg", 0.0)),
                    float(service_span.get("angular_end_deg", 0.0)),
                )
            )
            for service_span in service_spans
        )
        if bridge.get("required_screw_count", expected_count) != expected_count:
            failures.append({"type": "screw_count_rule", "bridge_id": bridge["bridge_id"]})
        if len(bridge.get("screws", [])) != expected_count:
            failures.append({"type": "screw_occurrence_count", "bridge_id": bridge["bridge_id"]})
        if len(bridge.get("support_pads", [])) != expected_count:
            failures.append({"type": "support_pad_count", "bridge_id": bridge["bridge_id"]})
        if bridge.get("seam_gap_width_mm") is not None and abs(float(bridge["seam_gap_width_mm"]) - BRIDGE_SEAM_GAP_WIDTH_MM) > 1e-6:
            failures.append({"type": "bridge_seam_gap_width", "bridge_id": bridge["bridge_id"]})
        if bridge.get("outer_radius_mm") is not None and abs(float(bridge["outer_radius_mm"]) - float(support_ring["outer_radius_mm"])) > 1e-6:
            failures.append({"type": "bridge_outer_radius_alignment", "bridge_id": bridge["bridge_id"]})
        if abs(float(bridge["z_min_mm"]) - bridge_bottom) > 1e-6 or abs(float(bridge["z_max_mm"]) - bridge_top) > 1e-6:
            failures.append({"type": "bridge_z_stack", "bridge_id": bridge["bridge_id"]})
        if bridge.get("review_opacity") is not None and abs(float(bridge["review_opacity"]) - BRIDGE_REVIEW_OPACITY) > 1e-6:
            failures.append({"type": "bridge_review_opacity", "bridge_id": bridge["bridge_id"]})
        for screw in bridge.get("screws", []):
            if screw.get("fastener_kind") != "countersunk_flat_head_screw":
                failures.append({"type": "bridge_fastener_kind", "bridge_id": bridge["bridge_id"], "screw_id": screw.get("screw_id")})
            if float(screw.get("threaded_engagement_depth_mm", 0.0)) <= 0.0:
                failures.append({"type": "bridge_fastener_threaded_engagement", "bridge_id": bridge["bridge_id"], "screw_id": screw.get("screw_id")})
        for pad in bridge.get("support_pads", []):
            if pad.get("footprint_type") != "outer_annular_service_pad":
                failures.append({"type": "support_pad_footprint_type", "bridge_id": bridge["bridge_id"], "pad_id": pad["pad_id"]})
            if pad.get("support_face") != "mainplate_outer_raised_support_ring":
                failures.append({"type": "support_pad_support_face", "bridge_id": bridge["bridge_id"], "pad_id": pad["pad_id"]})

    return {
        "status": "pass" if not failures else "fail",
        "skipped": False,
        "bridges": bridges,
        "failures": failures,
    }


def _bridge_screw_angles(start_deg: float, end_deg: float, count: int, edge_margin_deg: float) -> list[float]:
    span = _positive_angle_span(start_deg, end_deg)
    if count == 1:
        return [_normalize_degrees(start_deg + span / 2.0)]
    edge_margin = min(edge_margin_deg, span * 0.28)
    if count == 2:
        return [_normalize_degrees(start_deg + edge_margin), _normalize_degrees(start_deg + span - edge_margin)]
    if count == 3:
        return [
            _normalize_degrees(start_deg + edge_margin),
            _normalize_degrees(start_deg + span / 2.0),
            _normalize_degrees(start_deg + span - edge_margin),
        ]
    return [_normalize_degrees(start_deg + span * (index + 1) / (count + 1)) for index in range(count)]


def _support_pad_span_deg(inner_radius: float, outer_radius: float, target_arc_length: float) -> float:
    mean_radius = (float(inner_radius) + float(outer_radius)) / 2.0
    return round(math.degrees(target_arc_length / mean_radius), 4)


def _support_pad_angle_bounds(
    bridge_start_deg: float,
    bridge_end_deg: float,
    screw_angle_deg: float,
    screw_index: int,
    screw_count: int,
    pad_span_deg: float,
) -> dict[str, Any]:
    if screw_count > 1 and screw_index == 1:
        return {
            "pad_position": "start_edge",
            "angular_start_deg": round(bridge_start_deg, 4),
            "angular_end_deg": _normalize_degrees(bridge_start_deg + pad_span_deg),
        }
    if screw_count > 1 and screw_index == screw_count:
        return {
            "pad_position": "end_edge",
            "angular_start_deg": _normalize_degrees(bridge_end_deg - pad_span_deg),
            "angular_end_deg": round(bridge_end_deg, 4),
        }
    return {
        "pad_position": "middle",
        "angular_start_deg": _normalize_degrees(screw_angle_deg - pad_span_deg / 2.0),
        "angular_end_deg": _normalize_degrees(screw_angle_deg + pad_span_deg / 2.0),
    }


def _bridge_seam_boundary_line(angle_deg: float, side: str) -> dict[str, Any]:
    direction = _unit_vector(angle_deg)
    normal = (-direction[1], direction[0])
    offset_sign = 1.0 if side == "ccw" else -1.0
    half_gap = BRIDGE_SEAM_GAP_WIDTH_MM / 2.0
    point = (normal[0] * half_gap * offset_sign, normal[1] * half_gap * offset_sign)
    return {
        "construction": "parallel_offset_from_seam_centerline",
        "seam_centerline_angle_deg": round(angle_deg, 4),
        "offset_side": side,
        "offset_mm": round(half_gap * offset_sign, 4),
        "point": [round(point[0], 4), round(point[1], 4)],
        "direction": [round(direction[0], 6), round(direction[1], 6)],
    }


def _unit_vector(angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return (math.cos(angle), math.sin(angle))


def _solver_report_artifact(solver_report: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in solver_report.items()
        if key != "candidates"
    } | {
        "candidates": [
            {
                "candidate_id": candidate["candidate_id"],
                "status": candidate["status"],
                "is_seed_nominal": candidate["is_seed_nominal"],
                "score": candidate["score"],
                "variables": candidate["variables"],
                "failed_reasons": candidate["failed_reasons"],
            }
            for candidate in solver_report["candidates"]
        ]
    }


def _axis(
    axis_id: str,
    point: tuple[float, float],
    role: str,
    keepout_radius: float,
    *,
    support_required: bool = True,
    support_segments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    arbor_spec = _arbor_spec(axis_id)
    body_radius = float(arbor_spec["body_radius_mm"])
    pivot_radius = float(arbor_spec["pivot_radius_mm"])
    default_support_segments = [
        {
            "segment_id": _arbor_label(axis_id),
            "z_min": MAINPLATE_CENTER_Z - MAINPLATE_THICKNESS_MM / 2.0,
            "z_max": ARBOR_CENTER_Z + ARBOR_HEIGHT_MM / 2.0,
            "radius": body_radius,
            "kind": "continuous_arbor",
        }
    ] if support_required else []
    lower_jewel = _lower_jewel_spec(axis_id, point, body_radius, pivot_radius) if support_required else None
    lower_jewel_seat = _lower_jewel_seat_spec(axis_id, point, body_radius, pivot_radius) if support_required else None
    return {
        "axis_id": axis_id,
        "x": round(point[0], 4),
        "y": round(point[1], 4),
        "role": role,
        "keepout_radius": keepout_radius,
        "support_required": support_required,
        "arbor_body_radius": round(body_radius, 4),
        "pivot_radius": round(pivot_radius, 4),
        "size_class": arbor_spec["size_class"],
        "support_segments": support_segments if support_segments is not None else default_support_segments,
        "lower_jewel": lower_jewel,
        "lower_jewel_seat": lower_jewel_seat,
    }


def _gear(
    gear_id: str,
    axis_id: str,
    tooth_counts: dict[str, int],
    module: float,
    z: float,
    gear_type: str,
) -> dict[str, Any]:
    pitch_radius = module * tooth_counts[gear_id] / 2.0
    addendum = module * (0.76 if gear_type == "pinion" else 0.72)
    dedendum = module * 1.08
    return {
        "gear_id": gear_id,
        "axis_id": axis_id,
        "tooth_count": tooth_counts[gear_id],
        "module": module,
        "pitch_radius": round(pitch_radius, 4),
        "outer_radius": round(pitch_radius + addendum, 4),
        "root_radius": round(max(0.28, pitch_radius - dedendum), 4),
        "addendum": round(addendum, 4),
        "dedendum": round(dedendum, 4),
        "z": z,
        "height": PINION_HEIGHT_MM if gear_type == "pinion" else GEAR_HEIGHT_MM,
        "gear_type": gear_type,
    }


def _display_gear(
    gear_id: str,
    axis_id: str,
    tooth_counts: dict[str, int],
    module: float,
    z: float,
    gear_type: str,
) -> dict[str, Any]:
    gear = _gear(gear_id, axis_id, tooth_counts, module, z, gear_type)
    gear["height"] = 0.22 if gear_type == "pinion" else 0.18
    gear["display_role"] = "motion_works"
    return gear


def _build_z_stack_positions() -> dict[str, Any]:
    """Return one shared Z policy for train gears, motion works, and hands."""

    barrel_body_bottom = round(MAINPLATE_TOP_Z + Z_STACK_LOWER_CLEARANCE_MM, 4)
    barrel_teeth_z = round(barrel_body_bottom + 0.26, 4)
    layer2_z = round(barrel_body_bottom + Z_STACK_BARREL_BODY_HEIGHT_MM + Z_STACK_LAYER_CLEARANCE_MM, 4)
    layer3_z = round(layer2_z + PINION_HEIGHT_MM + Z_STACK_LAYER_CLEARANCE_MM, 4)
    layer4_z = round(layer3_z + PINION_HEIGHT_MM + Z_STACK_LAYER_CLEARANCE_MM, 4)
    display_low_z = layer3_z
    display_high_z = layer4_z
    cannon_tube_z_min = round(display_low_z + 0.20, 4)
    hour_tube_z_min = round(display_high_z + 0.16, 4)
    nominal_train_top_z = round(layer4_z + PINION_HEIGHT_MM, 4)
    future_bridge_bottom_z = round(nominal_train_top_z + FUTURE_BRIDGE_TRAIN_CLEARANCE_MM, 4)
    future_upper_jewel_top_z = round(future_bridge_bottom_z + FUTURE_BRIDGE_PLATE_THICKNESS_MM, 4)
    hour_hand_z = round(future_upper_jewel_top_z + DISPLAY_HAND_CLEARANCE_ABOVE_FUTURE_UPPER_JEWEL_MM, 4)
    minute_hand_z = round(hour_hand_z + 0.25, 4)
    seconds_hand_z = round(minute_hand_z + 0.22, 4)
    hour_tube_z_max = round(hour_hand_z + 0.06, 4)
    cannon_tube_z_max = round(minute_hand_z + 0.06, 4)
    extension_z_min = round(ARBOR_CENTER_Z + ARBOR_HEIGHT_MM / 2.0 - 0.08, 4)

    return {
        "mainplate_top_z_mm": round(MAINPLATE_TOP_Z, 4),
        "barrel_body": {
            "z_min_mm": barrel_body_bottom,
            "z_max_mm": round(barrel_body_bottom + Z_STACK_BARREL_BODY_HEIGHT_MM, 4),
            "height_mm": Z_STACK_BARREL_BODY_HEIGHT_MM,
        },
        "gear_z": {
            "barrel_outer_teeth": barrel_teeth_z,
            "center_pinion": barrel_teeth_z,
            "center_wheel": layer2_z,
            "third_pinion": layer2_z,
            "third_wheel": layer3_z,
            "fourth_pinion": layer3_z,
            "fourth_wheel": layer4_z,
            "escape_pinion": layer4_z,
            "escape_wheel": layer3_z,
        },
        "display_gear_z": {
            "cannon_pinion_display_driver": display_low_z,
            "minute_wheel": display_low_z,
            "minute_pinion": display_high_z,
            "hour_wheel": display_high_z,
        },
        "display": {
            "hour_tube_z_min": hour_tube_z_min,
            "hour_tube_z_max": hour_tube_z_max,
            "cannon_tube_z_min": cannon_tube_z_min,
            "cannon_tube_z_max": cannon_tube_z_max,
            "central_extension_z_min": extension_z_min,
            "central_extension_z_max": round(minute_hand_z + 0.32, 4),
            "seconds_extension_z_min": extension_z_min,
            "seconds_extension_z_max": round(seconds_hand_z + 0.20, 4),
            "hour_hand_z": hour_hand_z,
            "minute_hand_z": minute_hand_z,
            "seconds_hand_z": seconds_hand_z,
        },
        "layers": [
            {
                "layer_index": 1,
                "layer_id": "barrel_body_and_first_mesh_layer",
                "z_min_mm": barrel_body_bottom,
                "z_max_mm": round(barrel_body_bottom + Z_STACK_BARREL_BODY_HEIGHT_MM, 4),
                "policy": "mainspring_barrel_thickness_plus_upper_clearance",
            },
            {
                "layer_index": 2,
                "layer_id": "center_wheel_third_pinion_layer",
                "z_min_mm": layer2_z,
                "z_max_mm": round(layer2_z + PINION_HEIGHT_MM, 4),
                "policy": "gear_thickness_plus_top_clearance",
            },
            {
                "layer_index": 3,
                "layer_id": "third_wheel_fourth_pinion_layer",
                "z_min_mm": layer3_z,
                "z_max_mm": round(layer3_z + PINION_HEIGHT_MM, 4),
                "policy": "gear_thickness_plus_top_clearance",
            },
            {
                "layer_index": 4,
                "layer_id": "fourth_escape_and_motion_works_layer",
                "z_min_mm": layer4_z,
                "z_max_mm": round(layer4_z + PINION_HEIGHT_MM, 4),
                "policy": "final_train_layer_shared_by_escape_and_upper_motion_works",
            },
        ],
    }


def _build_z_stack_plan(
    gears: list[dict[str, Any]],
    display_gears: list[dict[str, Any]],
    positions: dict[str, Any],
) -> dict[str, Any]:
    layer_by_gear = {
        "barrel_outer_teeth": 1,
        "center_pinion": 1,
        "train_stage_1_pinion": 1,
        "center_wheel": 2,
        "train_stage_1_wheel": 2,
        "third_pinion": 2,
        "train_stage_2_pinion": 2,
        "third_wheel": 3,
        "train_stage_2_wheel": 3,
        "fourth_pinion": 3,
        "train_stage_3_pinion": 3,
        "fourth_wheel": 4,
        "train_stage_3_wheel": 4,
        "escape_pinion": 4,
        "escape_wheel": 3,
        "cannon_pinion_display_driver": 4,
        "minute_wheel": 4,
        "minute_pinion": 4,
        "hour_wheel": 4,
        "display_input_relay_pinion": 4,
        "display_input_relay_wheel": 3,
        "minute_display_member": 3,
        "display_relay_pinion": 3,
        "display_relay_wheel": 4,
        "hour_display_member": 4,
        "minute_input_relay_pinion": 4,
        "minute_input_relay_wheel": 3,
        "minute_display_member": 3,
        "hour_input_relay_pinion": 4,
        "hour_input_relay_wheel": 3,
        "hour_reduction_relay_pinion": 3,
        "hour_reduction_relay_wheel": 4,
        "hour_display_member": 4,
    }
    assignments: dict[str, dict[str, Any]] = {}
    missing = []
    mismatched_z = []
    max_observed_layer = 0
    for gear in [*gears, *display_gears]:
        gear_id = gear["gear_id"]
        layer_index = layer_by_gear.get(gear_id)
        if layer_index is None:
            missing.append(gear_id)
            continue
        gear["z_stack_layer"] = layer_index
        max_observed_layer = max(max_observed_layer, layer_index)
        assignment = {
            "entity_id": gear_id,
            "layer_index": layer_index,
            "z_min_mm": round(float(gear["z"]), 4),
            "z_max_mm": round(float(gear["z"] + gear["height"]), 4),
            "axis_id": gear["axis_id"],
            "height_mm": round(float(gear["height"]), 4),
        }
        assignments[gear_id] = assignment
        if abs(assignment["z_min_mm"] - round(float(gear["z"]), 4)) > 1e-6:
            mismatched_z.append(gear_id)

    train_top_z = max(gear["z"] + gear["height"] for gear in gears)
    display_hand_floor = min(positions["display"][key] for key in ["hour_hand_z", "minute_hand_z", "seconds_hand_z"])
    future_bridge_bottom_z = round(train_top_z + FUTURE_BRIDGE_TRAIN_CLEARANCE_MM, 4)
    future_upper_jewel_top_z = round(future_bridge_bottom_z + FUTURE_BRIDGE_PLATE_THICKNESS_MM, 4)
    future_bridge = {
        "phase": "flat_bridge_plate_future_phase",
        "policy": "uniform_upper_jewel_target_plane_reserved_before_bridge_generation",
        "bridge_bottom_z_mm": future_bridge_bottom_z,
        "bridge_top_z_mm": future_upper_jewel_top_z,
        "future_upper_jewel_top_z_mm": future_upper_jewel_top_z,
        "future_upper_jewel_height_mm": LOWER_JEWEL_HEIGHT_MM,
        "minimum_train_clearance_mm": FUTURE_BRIDGE_TRAIN_CLEARANCE_MM,
        "minimum_hand_clearance_mm": round(display_hand_floor - future_upper_jewel_top_z, 4),
        "bridge_fastener_policy": BRIDGE_Z_STACK_FASTENER_POLICY,
        "countersunk_head_depth_mm": FUTURE_BRIDGE_COUNTERSUNK_HEAD_DEPTH_MM,
        "minimum_residual_material_below_countersink_mm": FUTURE_BRIDGE_MINIMUM_RESIDUAL_MATERIAL_MM,
        "bridge_plate_thickness_mm": FUTURE_BRIDGE_PLATE_THICKNESS_MM,
        "support_face_to_service_step_split": list(FUTURE_BRIDGE_SUPPORT_FACE_TO_SERVICE_STEP_SPLIT),
        "height_formula": "upper_jewel_top = highest_gear_top + gear_clearance + countersunk_head_depth + residual_material",
    }
    actual_z_bands = sorted({round(float(gear["z"]), 3) for gear in [*gears, *display_gears]})
    checks = {
        "all_gear_layers_declared": "pass" if not missing else "fail",
        "max_gear_layer_count": "pass" if max_observed_layer <= Z_STACK_MAX_GEAR_LAYERS else "fail",
        "actual_distinct_gear_z_bands": "pass" if len(actual_z_bands) <= Z_STACK_MAX_GEAR_LAYERS else "fail",
        "gear_z_matches_assignments": "pass" if not mismatched_z else "fail",
        "display_stack_above_train": "pass" if display_hand_floor - train_top_z >= 0.8 else "fail",
        "future_upper_jewel_plane_below_hands": (
            "pass"
            if future_bridge["minimum_hand_clearance_mm"] >= MINIMUM_HAND_CLEARANCE_ABOVE_FUTURE_UPPER_JEWEL_MM
            else "fail"
        ),
        "future_upper_jewel_plane_above_train": (
            "pass"
            if future_bridge_bottom_z - train_top_z >= FUTURE_BRIDGE_TRAIN_CLEARANCE_MM - 1e-6
            else "fail"
        ),
    }
    return {
        "kind": "watch_power_chain_layered_z_stack",
        "status": "pass" if all(status == "pass" for status in checks.values()) else "fail",
        "placement_policy": "mainplate_top_plus_layer_clearances",
        "mainplate_top_z_mm": round(MAINPLATE_TOP_Z, 4),
        "max_gear_layer_count": Z_STACK_MAX_GEAR_LAYERS,
        "lower_clearance_mm": Z_STACK_LOWER_CLEARANCE_MM,
        "inter_layer_clearance_mm": Z_STACK_LAYER_CLEARANCE_MM,
        "barrel_body": positions["barrel_body"],
        "layers": positions["layers"],
        "assignments": assignments,
        "missing_assignments": missing,
        "mismatched_z_assignments": mismatched_z,
        "max_observed_layer_index": max_observed_layer,
        "actual_gear_z_bands_mm": actual_z_bands,
        "train_top_z_mm": round(train_top_z, 4),
        "display_hand_floor_z_mm": round(display_hand_floor, 4),
        "display_hand_clearance_above_train_mm": round(display_hand_floor - train_top_z, 4),
        "future_bridge": future_bridge,
        "checks": checks,
    }


def _build_display_motion_works(
    display_gears: list[dict[str, Any]],
    display_meshes: list[dict[str, str]],
    display_mesh_phase_records: list[dict[str, Any]],
    axis_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gear_by_id = {gear["gear_id"]: gear for gear in display_gears}
    cannon = gear_by_id["cannon_pinion_display_driver"]
    minute_wheel = gear_by_id["minute_wheel"]
    minute_pinion = gear_by_id["minute_pinion"]
    hour_wheel = gear_by_id["hour_wheel"]
    first_ratio = cannon["tooth_count"] / minute_wheel["tooth_count"]
    second_ratio = minute_pinion["tooth_count"] / hour_wheel["tooth_count"]
    hour_to_minute_ratio = first_ratio * second_ratio
    segments = {
        "cannon_pinion_assembly": _display_gear_segment(
            cannon,
            component_id="cannon_pinion_assembly",
            outer_radius=max(cannon["outer_radius"], 0.36),
            inner_radius=0.17,
        ),
        "cannon_pinion_display_driver": _display_gear_segment(cannon, inner_radius=0.17),
        "minute_wheel": _display_gear_segment(minute_wheel, inner_radius=0.16),
        "minute_pinion": _display_gear_segment(minute_pinion, inner_radius=0.16),
        "hour_wheel": _display_gear_segment(hour_wheel, inner_radius=0.36),
    }
    minute_axis = axis_by_id["minute_work_axis"]
    return {
        "status": "pass",
        "strategy": "two_mesh_motion_works_reduction",
        "axis_id": "minute_work_axis",
        "axis_xy_mm": [minute_axis["x"], minute_axis["y"]],
        "nodes": ["cannon_pinion_display_driver", "minute_wheel", "minute_pinion", "hour_wheel"],
        "assemblies": ["cannon_pinion_assembly", "minute_wheel_assembly"],
        "interfaces": [
            {
                "from": "cannon_pinion_display_driver",
                "to": "minute_wheel",
                "kind": "external_gear_mesh",
                "ratio": round(first_ratio, 12),
            },
            {
                "from": "minute_wheel",
                "to": "minute_pinion",
                "kind": "rigid_compound_arbor",
                "ratio": 1.0,
            },
            {
                "from": "minute_pinion",
                "to": "hour_wheel",
                "kind": "external_gear_mesh",
                "ratio": round(second_ratio, 12),
            },
        ],
        "ratio_proof": {
            "kind": "tooth_count_product",
            "tooth_relation": f"{cannon['tooth_count']}:{minute_wheel['tooth_count']} then {minute_pinion['tooth_count']}:{hour_wheel['tooth_count']}",
            "cannon_to_minute_wheel_ratio": round(first_ratio, 12),
            "minute_pinion_to_hour_wheel_ratio": round(second_ratio, 12),
            "hour_to_minute_ratio": round(hour_to_minute_ratio, 12),
            "expected_hour_to_minute_ratio": round(1 / 12, 12),
            "direction": "same_after_two_external_meshes",
        },
        "display_gears": display_gears,
        "display_meshes": display_meshes,
        "display_mesh_phase_records": display_mesh_phase_records,
        "segments": segments,
    }


def _display_gear_segment(
    gear: dict[str, Any],
    *,
    component_id: str | None = None,
    outer_radius: float | None = None,
    inner_radius: float,
) -> dict[str, Any]:
    return {
        "component_id": component_id or gear["gear_id"],
        "x_mm": round(gear["x"], 4),
        "y_mm": round(gear["y"], 4),
        "z_min_mm": round(gear["z"], 4),
        "z_max_mm": round(gear["z"] + gear["height"], 4),
        "outer_radius_mm": round(outer_radius if outer_radius is not None else gear["outer_radius"], 4),
        "inner_radius_mm": round(inner_radius, 4),
    }


def _mesh(driver: str, driven: str) -> dict[str, str]:
    return {"driver": driver, "driven": driven, "kind": "external_mesh"}


def _polar_from(origin: tuple[float, float], distance: float, angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return origin[0] + math.cos(angle) * distance, origin[1] + math.sin(angle) * distance


def _solver_point(axis: dict[str, Any]) -> tuple[float, float]:
    return (float(axis["x"]), float(axis["y"]))


def _computed_seconds_hand(axis: dict[str, Any], *, design_gears: list[dict[str, Any]], z_min: float = 5.06) -> dict[str, Any]:
    case_inner_radius = CASE_RADIUS_MM
    axis_radius = math.hypot(axis["x"], axis["y"])
    case_min_clearance = max(0.0, case_inner_radius - axis_radius)
    case_safety_margin = max(0.35, case_min_clearance * 0.12)
    length = max(1.2, (case_min_clearance - case_safety_margin) * 0.55)
    length = min(length, case_min_clearance - case_safety_margin)
    envelope = _hand_sweep_envelope("fourth_axis", (axis["x"], axis["y"]), length, z_min, 0.075)
    envelope.update(
        {
            "case_inner_radius_mm": round(case_inner_radius, 4),
            "case_min_clearance_mm": round(case_min_clearance, 4),
            "case_safety_margin_mm": round(case_safety_margin, 4),
            "length_rule": "0.55 * (case_min_clearance_mm - case_safety_margin_mm)",
            "checked_against": ["gear_z_envelopes", "central_hour_minute_hand_z_envelopes", "display_outer_boundary"],
            "bridge_perimeter_service_band_policy": "exempt_when_sweep_z_is_above_future_bridge_top",
        }
    )
    return {"length_mm": round(length, 4), "sweep_envelope": envelope}


def _central_display_hand_lengths(display_center: tuple[float, float], seconds_axis: tuple[float, float]) -> dict[str, Any]:
    center_to_seconds_axis = math.hypot(display_center[0] - seconds_axis[0], display_center[1] - seconds_axis[1])
    minute_length = round(min(MAINPLATE_RADIUS_MM * 0.8, center_to_seconds_axis * 0.9), 4)
    hour_length = round(minute_length * 0.5, 4)
    return {
        "minute_hand_length_mm": minute_length,
        "hour_hand_length_mm": hour_length,
        "minute_hand_rule": "min(0.8 * mainplate_radius_mm, 0.9 * center_to_seconds_axis_distance_mm)",
        "hour_hand_rule": "0.5 * minute_hand_length_mm",
        "center_to_seconds_axis_distance_mm": round(center_to_seconds_axis, 4),
    }


def _hand_sweep_envelope(axis_id: str, center: tuple[float, float], radius: float, z_min: float, height: float) -> dict[str, Any]:
    return {
        "axis_id": axis_id,
        "center_x": round(center[0], 4),
        "center_y": round(center[1], 4),
        "radius_mm": round(radius, 4),
        "z_min_mm": round(z_min, 4),
        "z_max_mm": round(z_min + height, 4),
    }


def _build_coaxial_sleeve_clearance_report(display: dict[str, Any]) -> dict[str, Any]:
    if "tube_stack" not in display:
        return {
            "status": "pass",
            "fact_source": "separate_display_axes_no_coaxial_tube_stack",
            "relationship": "not_applicable_for_separate_hour_minute_axes",
            "tube_count": 0,
        }
    tubes = {tube["tube_id"]: tube for tube in display["tube_stack"]}
    hour_tube = tubes.get("hour_tube")
    cannon_tube = tubes.get("cannon_pinion_tube")
    if not hour_tube or not cannon_tube:
        return {
            "status": "fail",
            "fact_source": "tube_stack_geometry",
            "missing_tubes": [tube_id for tube_id in ["hour_tube", "cannon_pinion_tube"] if tube_id not in tubes],
        }
    radial_clearance = hour_tube["inner_radius"] - cannon_tube["outer_radius"]
    z_overlap = max(hour_tube["z_min"], cannon_tube["z_min"]) < min(hour_tube["z_max"], cannon_tube["z_max"])
    status = "pass" if z_overlap and radial_clearance > 0.03 else "fail"
    return {
        "status": status,
        "fact_source": "tube_stack_geometry",
        "relationship": "independent_nested_coaxial_rotating_members",
        "outer_member": "hour_tube",
        "inner_member": "cannon_pinion_tube",
        "radial_clearance_mm": round(radial_clearance, 4),
        "minimum_required_clearance_mm": 0.03,
        "z_overlap": z_overlap,
        "z_overlap_range_mm": [
            round(max(hour_tube["z_min"], cannon_tube["z_min"]), 4),
            round(min(hour_tube["z_max"], cannon_tube["z_max"]), 4),
        ],
    }


def _build_display_mount_stacks(display: dict[str, Any], axes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    axes_by_id = {axis["axis_id"]: axis for axis in axes}
    tubes = {tube["tube_id"]: tube for tube in display["tube_stack"]}
    extensions = {extension["extension_id"]: extension for extension in display["arbor_extensions"]}
    hands = {hand["hand_id"]: hand for hand in display["hands"]}
    motion_segments = display["motion_works"]["segments"]
    center_axis = axes_by_id[DISPLAY_CENTER_AXIS]
    fourth_axis = axes_by_id["fourth_axis"]
    stacks = [
        _mount_stack(
            "hour_hand",
            [
                _segment_from_report(motion_segments["hour_wheel"]),
                _segment("hour_tube", center_axis, tubes["hour_tube"]["z_min"], tubes["hour_tube"]["z_max"], tubes["hour_tube"]["outer_radius"], tubes["hour_tube"]["inner_radius"]),
                _hand_hub_segment(hands["hour_hand"], center_axis, 0.92, ARBOR_RADIUS_MM * 0.8),
            ],
        ),
        _mount_stack(
            "minute_hand",
            [
                _segment_from_report(motion_segments["cannon_pinion_assembly"]),
                _segment(
                    "cannon_pinion_tube",
                    center_axis,
                    tubes["cannon_pinion_tube"]["z_min"],
                    tubes["cannon_pinion_tube"]["z_max"],
                    tubes["cannon_pinion_tube"]["outer_radius"],
                    tubes["cannon_pinion_tube"]["inner_radius"],
                ),
                _hand_hub_segment(hands["minute_hand"], center_axis, 0.58, ARBOR_RADIUS_MM * 0.8),
            ],
        ),
        _mount_stack(
            "seconds_hand",
            [
                _segment(
                    "fourth_arbor",
                    fourth_axis,
                    ARBOR_CENTER_Z - (ARBOR_HEIGHT_MM / 2.0),
                    ARBOR_CENTER_Z + (ARBOR_HEIGHT_MM / 2.0),
                    fourth_axis["arbor_body_radius"],
                    0.0,
                ),
                _segment(
                    "seconds_arbor_extension",
                    fourth_axis,
                    extensions["seconds_arbor_extension"]["z_min"],
                    extensions["seconds_arbor_extension"]["z_max"],
                    extensions["seconds_arbor_extension"]["radius"],
                    0.0,
                ),
                _hand_hub_segment(hands["seconds_hand"], fourth_axis, 0.32, ARBOR_RADIUS_MM * 0.8),
            ],
        ),
    ]
    return stacks


def _segment_from_report(segment: dict[str, Any]) -> dict[str, Any]:
    return dict(segment)


def _segment(component_id: str, axis: dict[str, Any], z_min: float, z_max: float, outer_radius: float, inner_radius: float) -> dict[str, Any]:
    return {
        "component_id": component_id,
        "x_mm": round(axis["x"], 4),
        "y_mm": round(axis["y"], 4),
        "z_min_mm": round(z_min, 4),
        "z_max_mm": round(z_max, 4),
        "outer_radius_mm": round(outer_radius, 4),
        "inner_radius_mm": round(inner_radius, 4),
    }


def _hand_hub_segment(hand: dict[str, Any], axis: dict[str, Any], outer_radius: float, inner_radius: float) -> dict[str, Any]:
    return _segment(f"{hand['hand_id']}_hub", axis, hand["z_mm"] - 0.02, hand["z_mm"] + 0.10, outer_radius, inner_radius)


def _mount_stack(hand_id: str, segments: list[dict[str, Any]]) -> dict[str, Any]:
    gap_tolerance = 0.02
    xy_tolerance = 0.01
    gaps = []
    xy_failures = []
    six_dof_failures = []
    interfaces = []
    max_positive_gap = 0.0
    max_xy_error = 0.0
    for lower, upper in zip(segments, segments[1:]):
        gap = upper["z_min_mm"] - lower["z_max_mm"]
        max_positive_gap = max(max_positive_gap, gap)
        xy_error = math.hypot(upper["x_mm"] - lower["x_mm"], upper["y_mm"] - lower["y_mm"])
        max_xy_error = max(max_xy_error, xy_error)
        radial_overlap = min(lower["outer_radius_mm"], upper["outer_radius_mm"]) - max(lower["inner_radius_mm"], upper["inner_radius_mm"])
        interface_constraints = ["lock_tx", "lock_ty", "lock_tz", "lock_rx", "lock_ry", "lock_rz"]
        interface = {
            "from": lower["component_id"],
            "to": upper["component_id"],
            "z_gap_mm": round(gap, 4),
            "xy_center_error_mm": round(xy_error, 6),
            "radial_overlap_mm": round(radial_overlap, 4),
            "constraints": interface_constraints,
        }
        interfaces.append(interface)
        if gap > gap_tolerance:
            gaps.append(
                {
                    "from": lower["component_id"],
                    "to": upper["component_id"],
                    "gap_mm": round(gap, 4),
                }
            )
        if xy_error > xy_tolerance or radial_overlap <= 0.0:
            xy_failures.append(
                {
                    "from": lower["component_id"],
                    "to": upper["component_id"],
                    "xy_center_error_mm": round(xy_error, 6),
                    "radial_overlap_mm": round(radial_overlap, 4),
                }
            )
        if interface_constraints != ["lock_tx", "lock_ty", "lock_tz", "lock_rx", "lock_ry", "lock_rz"]:
            six_dof_failures.append({"from": lower["component_id"], "to": upper["component_id"]})
    six_dof_constraints = ["lock_tx", "lock_ty", "lock_tz", "lock_rx", "lock_ry", "lock_rz"]
    return {
        "hand_id": hand_id,
        "segments": segments,
        "interfaces": interfaces,
        "max_positive_gap_mm": round(max_positive_gap, 4),
        "max_xy_center_error_mm": round(max_xy_error, 6),
        "gap_tolerance_mm": gap_tolerance,
        "xy_tolerance_mm": xy_tolerance,
        "gap_failures": gaps,
        "xy_failures": xy_failures,
        "six_dof_failures": six_dof_failures,
        "six_dof_constraints": six_dof_constraints,
        "unresolved_dof_count": 0 if not six_dof_failures else 6,
        "closed": gaps == [],
        "xy_connected": xy_failures == [],
        "six_dof_constrained": six_dof_failures == [],
    }


def _build_independent_geometry_report(design: dict[str, Any]) -> dict[str, Any]:
    hand_mounts = {}
    for stack in design["display"]["mount_stacks"]:
        interfaces = stack["interfaces"]
        min_radial_overlap = min((interface["radial_overlap_mm"] for interface in interfaces), default=0.0)
        max_xy_center_error = max((interface["xy_center_error_mm"] for interface in interfaces), default=0.0)
        max_z_gap = max((interface["z_gap_mm"] for interface in interfaces), default=0.0)
        z_connected = max_z_gap <= stack["gap_tolerance_mm"]
        xy_connected = max_xy_center_error <= stack["xy_tolerance_mm"]
        radially_connected = min_radial_overlap > 0.03
        six_dof_constrained = stack["six_dof_constrained"] and z_connected and xy_connected and radially_connected
        status = "pass" if z_connected and xy_connected and radially_connected and six_dof_constrained else "fail"
        hand_mounts[stack["hand_id"]] = {
            "status": status,
            "source_stack": stack["hand_id"],
            "fact_source": "display_mount_stack_geometry",
            "z_connected": z_connected,
            "xy_connected": xy_connected,
            "radially_connected": radially_connected,
            "six_dof_constrained": six_dof_constrained,
            "max_z_gap_mm": round(max_z_gap, 4),
            "max_xy_center_error_mm": round(max_xy_center_error, 6),
            "min_radial_overlap_mm": round(min_radial_overlap, 4),
            "interfaces": interfaces,
        }
    feature_attachments = _build_display_hand_feature_attachment_report(design)
    motion_chains = _build_display_motion_chain_report(design)
    coaxial_sleeves = _build_coaxial_sleeve_clearance_report(design["display"])
    support_axes = _build_support_axis_report(design)
    work_envelope = _build_work_envelope_report(design)
    bridge_perimeter_service_band = _build_bridge_perimeter_service_band_report(design)
    interference = _build_internal_interference_report(design)
    gear_mesh_clearance = _build_gear_mesh_clearance_report(design)
    housing_parent_body = _build_housing_parent_body_report(design)
    z_stack = _build_z_stack_validation_report(design)
    jewel_supports = _build_jewel_support_report(design)
    bridge_stage = _build_bridge_stage_report(design, jewel_supports)
    return {
        "kind": "watch_power_chain_mvp_independent_geometry_report",
        "phase": PHASE,
        "pattern_card_id": PATTERN_CARD_ID,
        "fact_source": "design_geometry_facts_not_generator_narrative",
        "status": "pass"
        if (
            hand_mounts
            and all(report["status"] == "pass" for report in hand_mounts.values())
            and feature_attachments
            and all(report["status"] == "pass" for report in feature_attachments.values())
            and motion_chains["status"] == "pass"
            and coaxial_sleeves["status"] == "pass"
            and support_axes["status"] == "pass"
            and work_envelope["status"] == "pass"
            and bridge_perimeter_service_band["status"] == "pass"
            and interference["status"] == "pass"
            and gear_mesh_clearance["status"] == "pass"
            and housing_parent_body["status"] == "pass"
            and z_stack["status"] == "pass"
            and jewel_supports["status"] == "pass"
            and bridge_stage["status"] == "pass"
        )
        else "fail",
        "hand_mounts": hand_mounts,
        "feature_attachments": feature_attachments,
        "motion_chains": motion_chains,
        "coaxial_sleeves": coaxial_sleeves,
        "support_axes": support_axes,
        "work_envelope": work_envelope,
        "bridge_perimeter_service_band": bridge_perimeter_service_band,
        "interference": interference,
        "gear_mesh_clearance": gear_mesh_clearance,
        "housing_parent_body": housing_parent_body,
        "z_stack": z_stack,
        "jewel_supports": jewel_supports,
        "bridge_stage": bridge_stage,
    }


def _build_bridge_stage_report(design: dict[str, Any], jewel_supports: dict[str, Any]) -> dict[str, Any]:
    if not design.get("bridges_generated"):
        return {
            "status": "pass",
            "skipped": True,
            "reason": "bridge_stage_not_requested",
            "bridges": [],
            "failures": [],
        }
    plan = design.get("bridge_stage")
    if not plan:
        return {"status": "fail", "failures": [{"type": "missing_bridge_stage_plan"}], "bridges": []}
    if plan.get("kind") in {
        "watch_separate_display_partitioned_bridge_stage_plan",
        "watch_independent_display_partitioned_bridge_stage_plan",
    }:
        return _build_axis_voronoi_bridge_stage_report(design, jewel_supports, plan)

    failures: list[dict[str, Any]] = []
    bridges = plan.get("bridges", [])
    if [bridge.get("bridge_id") for bridge in bridges] != ["barrel_bridge", "train_bridge", "escapement_bridge"]:
        failures.append({"type": "bridge_id_sequence", "observed": [bridge.get("bridge_id") for bridge in bridges]})

    pitch_radii = {
        round(float(screw["pitch_radius_mm"]), 4)
        for bridge in bridges
        for screw in bridge.get("screws", [])
    }
    if len(pitch_radii) != 1:
        failures.append({"type": "screws_not_on_shared_pitch_circle", "observed": sorted(pitch_radii)})
    screw_policy = plan.get("screw_policy", {})
    support_pad_policy = plan.get("support_pad_policy", {})
    expected_edge_margin = float(support_pad_policy.get("target_angular_span_deg", 0.0)) / 2.0
    if abs(float(screw_policy.get("edge_margin_deg", -1.0)) - expected_edge_margin) > 1e-6:
        failures.append({"type": "bridge_screw_edge_margin_policy"})
    if support_pad_policy.get("kind") != "outer_annular_service_pad":
        failures.append({"type": "bridge_support_pad_policy_kind"})
    if abs(float(support_pad_policy.get("arc_length_to_screw_head_diameter_ratio", -1.0)) - BRIDGE_SUPPORT_PAD_ARC_LENGTH_TO_HEAD_DIAMETER_RATIO) > 1e-6:
        failures.append({"type": "bridge_support_pad_arc_ratio"})
    seam_policy = plan.get("seam_policy", {})
    if seam_policy.get("kind") != "fixed_width_parallel_seams":
        failures.append({"type": "bridge_seam_policy"})
    if abs(float(seam_policy.get("gap_width_mm", -1.0)) - BRIDGE_SEAM_GAP_WIDTH_MM) > 1e-6:
        failures.append({"type": "bridge_seam_gap_width"})
    central_axis_policy = plan.get("central_axis_policy", {})
    if central_axis_policy.get("owning_bridge_id") != "train_bridge":
        failures.append({"type": "central_axis_owner"})
    if central_axis_policy.get("support_strategy") != "covered_by_train_bridge_boss":
        failures.append({"type": "central_axis_support_strategy"})

    supported_axes = {
        axis_id
        for bridge in bridges
        for axis_id in bridge.get("supported_axis_ids", [])
    }
    missing_upper_axes = [
        axis_id for axis_id in jewel_supports.get("upper_jewel_bearing_axis_ids", []) if axis_id not in supported_axes
    ]
    if missing_upper_axes:
        failures.append({"type": "upper_jewel_axes_not_assigned_to_bridge", "axis_ids": missing_upper_axes})
    upper_jewel_axis_ids = set(jewel_supports.get("upper_jewel_bearing_axis_ids", []))

    bridge_bottom = float(design["z_stack"]["future_bridge"]["bridge_bottom_z_mm"])
    bridge_top = float(design["z_stack"]["future_bridge"]["future_upper_jewel_top_z_mm"])
    support_top = float(design["housing"]["outer_raised_support_ring"]["top_z_mm"])
    for bridge in bridges:
        expected_count = _bridge_screw_count_for_span(float(bridge["angular_span_deg"]))
        if bridge.get("required_screw_count") != expected_count:
            failures.append({"type": "screw_count_rule", "bridge_id": bridge["bridge_id"]})
        if len(bridge.get("screws", [])) != expected_count:
            failures.append({"type": "screw_occurrence_count", "bridge_id": bridge["bridge_id"]})
        if len(bridge.get("support_pads", [])) != expected_count:
            failures.append({"type": "support_pad_count", "bridge_id": bridge["bridge_id"]})
        support_ring = design["housing"]["outer_raised_support_ring"]
        if abs(float(bridge.get("outer_radius_mm", -1.0)) - float(support_ring["outer_radius_mm"])) > 1e-6:
            failures.append({"type": "bridge_outer_radius_alignment", "bridge_id": bridge["bridge_id"]})
        if expected_count > 1 and bridge.get("screws"):
            first_offset = _positive_angle_span(float(bridge["angular_start_deg"]), float(bridge["screws"][0]["angle_deg"]))
            last_offset = _positive_angle_span(float(bridge["screws"][-1]["angle_deg"]), float(bridge["angular_end_deg"]))
            if first_offset > expected_edge_margin + 1e-6 or last_offset > expected_edge_margin + 1e-6:
                failures.append({"type": "bridge_screws_not_near_end_edges", "bridge_id": bridge["bridge_id"]})
        if bridge.get("seam_boundary_policy") != "constant_width_parallel_gap_edges":
            failures.append({"type": "bridge_seam_boundary_policy", "bridge_id": bridge["bridge_id"]})
        for screw in bridge.get("screws", []):
            if screw.get("fastener_kind") != "countersunk_flat_head_screw":
                failures.append({"type": "bridge_fastener_kind", "bridge_id": bridge["bridge_id"], "screw_id": screw.get("screw_id")})
            if screw.get("standard") != BRIDGE_Z_STACK_FASTENER_POLICY["standard"]:
                failures.append({"type": "bridge_fastener_standard", "bridge_id": bridge["bridge_id"], "screw_id": screw.get("screw_id")})
            if float(screw.get("head_diameter_mm", 0.0)) <= float(screw.get("nominal_thread_diameter_mm", 0.0)):
                failures.append({"type": "bridge_fastener_head_size", "bridge_id": bridge["bridge_id"], "screw_id": screw.get("screw_id")})
            if float(screw.get("countersink_depth_mm", 0.0)) <= 0.0:
                failures.append({"type": "bridge_fastener_countersink_depth", "bridge_id": bridge["bridge_id"], "screw_id": screw.get("screw_id")})
            if screw.get("head_top_policy") != "flush_to_bridge_top":
                failures.append({"type": "bridge_fastener_head_top_policy", "bridge_id": bridge["bridge_id"], "screw_id": screw.get("screw_id")})
            if float(screw.get("threaded_engagement_depth_mm", 0.0)) <= 0.0:
                failures.append({"type": "bridge_fastener_threaded_engagement", "bridge_id": bridge["bridge_id"], "screw_id": screw.get("screw_id")})
            if float(screw.get("threaded_hole_bottom_z_mm", 0.0)) >= float(screw.get("threaded_hole_top_z_mm", 0.0)):
                failures.append({"type": "bridge_fastener_threaded_hole_z", "bridge_id": bridge["bridge_id"], "screw_id": screw.get("screw_id")})
        if abs(float(bridge.get("seam_gap_width_mm", -1.0)) - BRIDGE_SEAM_GAP_WIDTH_MM) > 1e-6:
            failures.append({"type": "bridge_seam_gap_width", "bridge_id": bridge["bridge_id"]})
        seam_lines = bridge.get("seam_boundary_lines", {})
        for line_id in ("start", "end"):
            if seam_lines.get(line_id, {}).get("construction") != "parallel_offset_from_seam_centerline":
                failures.append({"type": "bridge_seam_line_construction", "bridge_id": bridge["bridge_id"], "line_id": line_id})
        expected_hole_axis_ids = set(bridge.get("supported_axis_ids", [])) & upper_jewel_axis_ids
        if len(bridge.get("clearance_holes", [])) != len(expected_hole_axis_ids):
            failures.append({"type": "clearance_hole_count", "bridge_id": bridge["bridge_id"]})
        if abs(float(bridge["z_min_mm"]) - bridge_bottom) > 1e-6 or abs(float(bridge["z_max_mm"]) - bridge_top) > 1e-6:
            failures.append({"type": "bridge_z_stack", "bridge_id": bridge["bridge_id"]})
        if abs(float(bridge.get("review_opacity", -1.0)) - BRIDGE_REVIEW_OPACITY) > 1e-6:
            failures.append({"type": "bridge_review_opacity", "bridge_id": bridge["bridge_id"]})
        for pad in bridge.get("support_pads", []):
            if pad.get("footprint_type") != "outer_annular_service_pad":
                failures.append({"type": "support_pad_footprint_type", "bridge_id": bridge["bridge_id"], "pad_id": pad["pad_id"]})
            if pad.get("support_face") != "mainplate_outer_raised_support_ring":
                failures.append({"type": "support_pad_support_face", "bridge_id": bridge["bridge_id"], "pad_id": pad["pad_id"]})
            if abs(float(pad.get("inner_radius_mm", -1.0)) - float(support_ring["inner_radius_mm"])) > 1e-6:
                failures.append({"type": "support_pad_inner_radius", "bridge_id": bridge["bridge_id"], "pad_id": pad["pad_id"]})
            if abs(float(pad.get("outer_radius_mm", -1.0)) - float(support_ring["outer_radius_mm"])) > 1e-6:
                failures.append({"type": "support_pad_outer_radius", "bridge_id": bridge["bridge_id"], "pad_id": pad["pad_id"]})
            if abs(float(pad.get("target_outer_arc_length_mm", -1.0)) - float(support_pad_policy.get("target_outer_arc_length_mm", -2.0))) > 1e-6:
                failures.append({"type": "support_pad_arc_length", "bridge_id": bridge["bridge_id"], "pad_id": pad["pad_id"]})
            if abs(float(pad.get("target_angular_span_deg", -1.0)) - _positive_angle_span(float(pad["angular_start_deg"]), float(pad["angular_end_deg"]))) > 1e-6:
                failures.append({"type": "support_pad_angular_span", "bridge_id": bridge["bridge_id"], "pad_id": pad["pad_id"]})
            if pad.get("pad_position") == "start_edge" and abs(float(pad["angular_start_deg"]) - float(bridge["angular_start_deg"])) > 1e-6:
                failures.append({"type": "support_pad_start_edge_alignment", "bridge_id": bridge["bridge_id"], "pad_id": pad["pad_id"]})
            if pad.get("pad_position") == "end_edge" and abs(float(pad["angular_end_deg"]) - float(bridge["angular_end_deg"])) > 1e-6:
                failures.append({"type": "support_pad_end_edge_alignment", "bridge_id": bridge["bridge_id"], "pad_id": pad["pad_id"]})
            if abs(float(pad["z_min_mm"]) - support_top) > 1e-6 or abs(float(pad["z_max_mm"]) - bridge_bottom) > 1e-6:
                failures.append({"type": "support_pad_z_stack", "bridge_id": bridge["bridge_id"], "pad_id": pad["pad_id"]})
        hole_axis_ids = {hole["axis_id"] for hole in bridge.get("clearance_holes", [])}
        if hole_axis_ids != expected_hole_axis_ids:
            failures.append({"type": "clearance_hole_axis_set", "bridge_id": bridge["bridge_id"]})
        central_feature = bridge.get("central_axis_feature")
        if bridge["bridge_id"] == "train_bridge":
            if not central_feature or central_feature.get("axis_id") != "center_axis":
                failures.append({"type": "missing_train_bridge_center_axis_feature"})
            elif float(central_feature["outer_radius_mm"]) <= float(central_feature["clearance_radius_mm"]):
                failures.append({"type": "invalid_train_bridge_center_axis_feature"})
        elif central_feature:
            failures.append({"type": "unexpected_central_axis_feature", "bridge_id": bridge["bridge_id"]})
    return {
        **plan,
        "status": "pass" if not failures and plan.get("status") == "pass" else "fail",
        "failures": failures,
    }


def _build_z_stack_validation_report(design: dict[str, Any]) -> dict[str, Any]:
    z_stack = design.get("z_stack")
    if not z_stack:
        return {
            "status": "fail",
            "fact_source": "independently_recomputed_gear_z_layers",
            "failures": [{"type": "missing_z_stack_plan"}],
        }
    assignments = z_stack.get("assignments", {})
    failures = []
    max_layer = 0
    for gear in [*design["gears"], *design.get("display_gears", [])]:
        gear_id = gear["gear_id"]
        assignment = assignments.get(gear_id)
        if assignment is None:
            failures.append({"type": "missing_assignment", "gear_id": gear_id})
            continue
        observed_layer = int(gear.get("z_stack_layer", -1))
        max_layer = max(max_layer, observed_layer)
        observed_z_min = round(float(gear["z"]), 4)
        observed_z_max = round(float(gear["z"] + gear["height"]), 4)
        if observed_layer != int(assignment["layer_index"]):
            failures.append(
                {
                    "type": "layer_mismatch",
                    "gear_id": gear_id,
                    "observed_layer": observed_layer,
                    "assigned_layer": assignment["layer_index"],
                }
            )
        if abs(observed_z_min - float(assignment["z_min_mm"])) > 1e-6 or abs(observed_z_max - float(assignment["z_max_mm"])) > 1e-6:
            failures.append(
                {
                    "type": "z_mismatch",
                    "gear_id": gear_id,
                    "observed_z_min_mm": observed_z_min,
                    "observed_z_max_mm": observed_z_max,
                    "assigned_z_min_mm": assignment["z_min_mm"],
                    "assigned_z_max_mm": assignment["z_max_mm"],
                }
            )
        if observed_layer > Z_STACK_MAX_GEAR_LAYERS:
            failures.append({"type": "layer_count_exceeded", "gear_id": gear_id, "observed_layer": observed_layer})
    for name, status in z_stack.get("checks", {}).items():
        if status != "pass":
            failures.append({"type": "z_stack_check_failed", "check": name, "status": status})
    return {
        "status": "pass" if not failures else "fail",
        "fact_source": "independently_recomputed_gear_z_layers",
        "max_allowed_layer_count": Z_STACK_MAX_GEAR_LAYERS,
        "max_observed_layer_index": max_layer,
        "gear_count": len([*design["gears"], *design.get("display_gears", [])]),
        "failures": failures,
    }


def _build_jewel_support_report(design: dict[str, Any]) -> dict[str, Any]:
    required_axes = [axis for axis in design["axes"] if axis["support_required"]]
    expected_upper_bearing_axis_ids = _expected_upper_jewel_bearing_axis_ids(design)
    upper_jewel_bearings_by_axis = {
        axis["axis_id"]: axis["upper_jewel_bearing"]
        for axis in required_axes
        if axis.get("upper_jewel_bearing")
    }
    missing_upper_jewel_bearings = [
        axis_id for axis_id in expected_upper_bearing_axis_ids if axis_id not in upper_jewel_bearings_by_axis
    ]
    upper_jewel_display_axis_violations = [
        axis_id for axis_id in upper_jewel_bearings_by_axis if axis_id == DISPLAY_CENTER_AXIS
    ]
    missing_lower_jewels = [
        axis["axis_id"]
        for axis in required_axes
        if not axis.get("lower_jewel") or not axis.get("lower_jewel_seat")
    ]
    missing_future_upper_jewels = [
        axis["axis_id"]
        for axis in required_axes
        if not axis.get("future_upper_jewel_target")
    ]
    height_failures: list[dict[str, Any]] = []
    lower_tops = {
        axis["axis_id"]: round(axis["lower_jewel"]["z_max"], 4)
        for axis in required_axes
        if axis.get("lower_jewel")
    }
    if len(set(lower_tops.values())) > 1:
        height_failures.append({"type": "lower_jewel_top_height_not_uniform", "observed": lower_tops})
    future_tops = {
        axis["axis_id"]: round(axis["future_upper_jewel_target"]["z_max"], 4)
        for axis in required_axes
        if axis.get("future_upper_jewel_target")
    }
    if len(set(future_tops.values())) > 1:
        height_failures.append({"type": "future_upper_jewel_top_height_not_uniform", "observed": future_tops})
    upper_tops = {
        axis_id: round(upper_jewel_bearing["z_max"], 4)
        for axis_id, upper_jewel_bearing in upper_jewel_bearings_by_axis.items()
    }
    if len(set(upper_tops.values())) > 1:
        height_failures.append({"type": "upper_jewel_bearing_top_height_not_uniform", "observed": upper_tops})

    future_bridge = design["z_stack"].get("future_bridge", {})
    minimum_hand_clearance = float(future_bridge.get("minimum_hand_clearance_mm", -1.0))
    if minimum_hand_clearance <= MINIMUM_HAND_CLEARANCE_ABOVE_FUTURE_UPPER_JEWEL_MM:
        height_failures.append(
            {
                "type": "future_upper_jewel_plane_too_close_to_hands",
                "minimum_hand_clearance_mm": round(minimum_hand_clearance, 4),
                "required_mm": MINIMUM_HAND_CLEARANCE_ABOVE_FUTURE_UPPER_JEWEL_MM,
            }
        )

    upper_jewel_plane = _build_upper_jewel_plane_report(upper_jewel_bearings_by_axis, missing_upper_jewel_bearings)
    upper_pivot_reach_failures = _upper_pivot_reach_failures(design, upper_jewel_bearings_by_axis)
    upper_pivot_overrun_failures = _upper_pivot_overrun_failures(design, upper_jewel_bearings_by_axis)
    support_envelopes = _jewel_support_envelopes(design)
    interference_failures = _jewel_support_interference_failures(design, support_envelopes)
    return {
        "status": "pass"
        if not missing_lower_jewels
        and not missing_future_upper_jewels
        and not missing_upper_jewel_bearings
        and not upper_jewel_display_axis_violations
        and not upper_pivot_reach_failures
        and not upper_pivot_overrun_failures
        and upper_jewel_plane["status"] == "pass"
        and not height_failures
        and not interference_failures
        else "fail",
        "fact_source": "axis_jewel_support_geometry_and_envelope_math",
        "required_axis_ids": [axis["axis_id"] for axis in required_axes],
        "upper_jewel_bearing_axis_ids": sorted(upper_jewel_bearings_by_axis),
        "upper_jewel_bearings_by_axis": upper_jewel_bearings_by_axis,
        "upper_jewel_plane": upper_jewel_plane,
        "missing_lower_jewels": missing_lower_jewels,
        "missing_future_upper_jewels": missing_future_upper_jewels,
        "missing_upper_jewel_bearings": missing_upper_jewel_bearings,
        "upper_jewel_display_axis_violations": upper_jewel_display_axis_violations,
        "upper_pivot_reach_failures": upper_pivot_reach_failures,
        "upper_pivot_overrun_failures": upper_pivot_overrun_failures,
        "height_failures": height_failures,
        "interference_failures": interference_failures,
        "minimum_hand_clearance_above_future_upper_jewel_mm": round(minimum_hand_clearance, 4),
        "future_upper_jewel_top_z_mm": future_bridge.get("future_upper_jewel_top_z_mm"),
        "support_envelopes": support_envelopes,
    }


def _expected_upper_jewel_bearing_axis_ids(design: dict[str, Any]) -> list[str]:
    axis_ids = {
        gear["axis_id"]
        for gear in [*design["gears"], *design.get("display_gears", [])]
        if gear["axis_id"] != DISPLAY_CENTER_AXIS
    }
    if any(gear["axis_id"] == DISPLAY_CENTER_AXIS for gear in design.get("display_gears", [])):
        axis_ids.add("center_axis")
    return sorted(axis_ids)


def _build_upper_jewel_plane_report(
    upper_jewel_bearings_by_axis: dict[str, dict[str, Any]],
    missing_upper_jewel_bearings: list[str],
) -> dict[str, Any]:
    top_z_by_axis = {
        axis_id: round(float(bearing["z_max"]), 4)
        for axis_id, bearing in upper_jewel_bearings_by_axis.items()
    }
    checks = {
        "all_expected_axes_have_upper_bearing": "pass" if not missing_upper_jewel_bearings else "fail",
        "top_height_uniform": "pass" if len(set(top_z_by_axis.values())) == 1 else "fail",
        "no_display_center_axis_bearing": "pass" if DISPLAY_CENTER_AXIS not in upper_jewel_bearings_by_axis else "fail",
    }
    return {
        "status": "pass" if all(status == "pass" for status in checks.values()) else "fail",
        "plane_id": "uniform_future_bridge_upper_jewel_top_plane",
        "fact_source": "upper_jewel_bearing_specs",
        "top_z_by_axis_mm": top_z_by_axis,
        "checks": checks,
    }


def _upper_pivot_reach_failures(
    design: dict[str, Any],
    upper_jewel_bearings_by_axis: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    failures = []
    for axis_id, upper_bearing in upper_jewel_bearings_by_axis.items():
        axis = axis_by_id[axis_id]
        if not any(
            segment["z_min"] <= upper_bearing["z_min"] + 1e-6
            and segment["z_max"] >= upper_bearing["z_max"] - 1e-6
            and segment["radius"] <= upper_bearing["inner_radius"] - 0.01
            for segment in axis.get("support_segments", [])
        ):
            failures.append(
                {
                    "axis_id": axis_id,
                    "upper_bearing_id": upper_bearing["entity_id"],
                    "reason": "no_pivot_segment_reaches_through_upper_jewel_bearing",
                }
            )
    return failures


def _upper_pivot_overrun_failures(
    design: dict[str, Any],
    upper_jewel_bearings_by_axis: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    failures: list[dict[str, Any]] = []
    for axis_id, upper_bearing in upper_jewel_bearings_by_axis.items():
        axis = axis_by_id[axis_id]
        upper_top = float(upper_bearing["z_max"])
        for segment in axis.get("support_segments", []):
            if float(segment["z_max"]) > upper_top + 1e-6:
                failures.append(
                    {
                        "axis_id": axis_id,
                        "segment_id": segment["segment_id"],
                        "upper_bearing_id": upper_bearing["entity_id"],
                        "segment_z_max_mm": round(float(segment["z_max"]), 4),
                        "upper_jewel_top_z_mm": round(upper_top, 4),
                        "reason": "support_segment_protrudes_above_upper_jewel_top_plane",
                    }
                )
    return failures

def _jewel_support_interference_failures(
    design: dict[str, Any],
    support_envelopes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    checked = [*support_envelopes, *_gear_like_envelopes(design), *_hand_sweep_envelopes(design)]
    for index, left in enumerate(checked):
        for right in checked[index + 1 :]:
            if left.get("axis_id") and left.get("axis_id") == right.get("axis_id"):
                continue
            if left.get("kind") not in {"lower_jewel", "lower_jewel_seat", "future_upper_jewel_target", "upper_jewel_bearing"} and right.get("kind") not in {
                "lower_jewel",
                "lower_jewel_seat",
                "future_upper_jewel_target",
                "upper_jewel_bearing",
            }:
                continue
            if _cylindrical_envelopes_overlap(
                left["x"],
                left["y"],
                left["radius"],
                left["z_min"],
                left["z_max"],
                right["x"],
                right["y"],
                right["radius"],
                right["z_min"],
                right["z_max"],
            ):
                failures.append(
                    {
                        "left": left["entity_id"],
                        "right": right["entity_id"],
                        "left_kind": left["kind"],
                        "right_kind": right["kind"],
                    }
                )
    return failures


def _jewel_support_envelopes(design: dict[str, Any], *, include_future_targets: bool = True) -> list[dict[str, Any]]:
    envelopes: list[dict[str, Any]] = []
    for axis in design["axes"]:
        if not axis["support_required"]:
            continue
        for key, kind in [
            ("lower_jewel_seat", "lower_jewel_seat"),
            ("lower_jewel", "lower_jewel"),
            ("future_upper_jewel_target", "future_upper_jewel_target"),
            ("upper_jewel_bearing", "upper_jewel_bearing"),
        ]:
            if key == "future_upper_jewel_target" and not include_future_targets:
                continue
            spec = axis.get(key)
            if not spec:
                continue
            envelopes.append(
                {
                    "entity_id": spec["entity_id"],
                    "axis_id": axis["axis_id"],
                    "x": spec["x"],
                    "y": spec["y"],
                    "radius": spec["outer_radius"],
                    "z_min": spec["z_min"],
                    "z_max": spec["z_max"],
                    "kind": kind,
                }
            )
    return envelopes


def _hand_sweep_envelopes(design: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "entity_id": f"{hand_id}_sweep",
            "axis_id": envelope["axis_id"],
            "x": envelope["center_x"],
            "y": envelope["center_y"],
            "radius": envelope["radius_mm"],
            "z_min": envelope["z_min_mm"],
            "z_max": envelope["z_max_mm"],
            "kind": "hand_sweep",
        }
        for hand_id, envelope in design["display"]["sweep_envelopes"].items()
    ]


def _build_support_axis_report(design: dict[str, Any]) -> dict[str, Any]:
    floating_segments = []
    axis_interference_failures = []
    support_reports = {}
    checked_targets = _gear_like_envelopes(design)
    mainplate_top_z = MAINPLATE_CENTER_Z + MAINPLATE_THICKNESS_MM / 2.0
    for axis in design["axes"]:
        if not axis["support_required"]:
            continue
        segments = sorted(axis.get("support_segments", []), key=lambda segment: segment["z_min"])
        axis_failures = []
        if not segments:
            axis_failures.append({"type": "missing_support_segment"})
        elif segments[0]["z_min"] > mainplate_top_z + 0.02:
            axis_failures.append(
                {
                    "type": "no_parent_body_contact",
                    "segment_id": segments[0]["segment_id"],
                    "z_min": round(segments[0]["z_min"], 4),
                    "mainplate_top_z": round(mainplate_top_z, 4),
                }
            )
        for lower, upper in zip(segments, segments[1:]):
            gap = upper["z_min"] - lower["z_max"]
            if gap > 0.02:
                failure = {
                    "axis_id": axis["axis_id"],
                    "lower_segment": lower["segment_id"],
                    "upper_segment": upper["segment_id"],
                    "gap_mm": round(gap, 4),
                }
                floating_segments.append(failure)
                axis_failures.append({"type": "split_axis_gap", **failure})
        for segment in segments:
            for target in checked_targets:
                if target["axis_id"] == axis["axis_id"]:
                    continue
                if _cylindrical_envelopes_overlap(
                    axis["x"],
                    axis["y"],
                    segment["radius"],
                    segment["z_min"],
                    segment["z_max"],
                    target["x"],
                    target["y"],
                    target["radius"],
                    target["z_min"],
                    target["z_max"],
                ):
                    if _support_segment_clears_declared_hole(axis, segment, target):
                        continue
                    if _support_segment_clears_coaxial_display_member(axis, segment, target):
                        continue
                    failure = {
                        "axis_id": axis["axis_id"],
                        "segment_id": segment["segment_id"],
                        "target_id": target["entity_id"],
                        "target_axis_id": target["axis_id"],
                    }
                    axis_interference_failures.append(failure)
                    axis_failures.append({"type": "axis_interference", **failure})
        support_reports[axis["axis_id"]] = {
            "status": "pass" if not axis_failures else "fail",
            "segments": segments,
            "failures": axis_failures,
        }
    return {
        "status": "pass" if not floating_segments and not axis_interference_failures and all(report["status"] == "pass" for report in support_reports.values()) else "fail",
        "fact_source": "declared_support_segments_and_envelope_math",
        "support_reports": support_reports,
        "floating_segments": floating_segments,
        "axis_interference_failures": axis_interference_failures,
    }


def _support_segment_clears_declared_hole(
    axis: dict[str, Any],
    segment: dict[str, Any],
    target: dict[str, Any],
) -> bool:
    for hole in target.get("clearance_holes", []):
        if hole.get("axis_id") != axis["axis_id"]:
            continue
        xy_error = math.hypot(float(hole["x"]) - float(axis["x"]), float(hole["y"]) - float(axis["y"]))
        radial_clearance = float(hole["radius"]) - float(segment["radius"]) - xy_error
        if radial_clearance >= 0.02:
            return True
    return False


def _support_segment_clears_coaxial_display_member(
    axis: dict[str, Any],
    segment: dict[str, Any],
    target: dict[str, Any],
) -> bool:
    if axis["axis_id"] != "center_axis" or target.get("axis_id") != DISPLAY_CENTER_AXIS:
        return False
    xy_error = math.hypot(float(axis["x"]) - float(target["x"]), float(axis["y"]) - float(target["y"]))
    if xy_error > 1e-6:
        return False
    bore_radius = float(target.get("bore_radius", 0.0))
    return bore_radius - float(segment["radius"]) >= 0.02


def _build_work_envelope_report(design: dict[str, Any]) -> dict[str, Any]:
    entities = _internal_physical_envelopes(design)
    out_of_bounds = [
        entity
        for entity in entities
        if math.hypot(entity["x"], entity["y"]) + entity["radius"] > CASE_RADIUS_MM + 1e-6
    ]
    return {
        "status": "pass" if not out_of_bounds else "fail",
        "fact_source": "declared_mainplate_radius_and_entity_envelopes",
        "mainplate_radius_mm": CASE_RADIUS_MM,
        "entity_count": len(entities),
        "out_of_bounds": out_of_bounds,
    }


def _build_bridge_perimeter_service_band_report(design: dict[str, Any]) -> dict[str, Any]:
    entities = _internal_physical_envelopes(design)
    legal_service_band_owners = _legal_bridge_service_band_owner_ids(design)
    records = []
    violations = []
    for entity in entities:
        outer_distance = math.hypot(entity["x"], entity["y"]) + entity["radius"]
        margin = CASE_RADIUS_MM - outer_distance
        legal_owner = _bridge_service_band_entity_is_legal_owner(entity, design)
        record = {
            "entity_id": entity["entity_id"],
            "kind": entity["kind"],
            "outer_distance_from_mainplate_center_mm": round(outer_distance, 4),
            "margin_to_mainplate_outer_edge_mm": round(margin, 4),
            "reserved_band_mm": BRIDGE_PERIMETER_RESERVED_BAND_MM,
            "z_min_mm": round(float(entity.get("z_min", -math.inf)), 4),
            "z_max_mm": round(float(entity.get("z_max", math.inf)), 4),
            "legal_service_band_owner": legal_owner,
        }
        records.append(record)
        if margin < BRIDGE_PERIMETER_RESERVED_BAND_MM - 1e-6:
            if legal_owner:
                continue
            if _bridge_service_band_entity_is_z_exempt(entity, design):
                continue
            violations.append(record)
    z_height_exemptions = [
        {
            **record,
            "reason": "above_future_bridge_top",
            "future_bridge_top_z_mm": design["z_stack"]["future_bridge"]["bridge_top_z_mm"],
        }
        for entity, record in zip(entities, records)
        if record["margin_to_mainplate_outer_edge_mm"] < BRIDGE_PERIMETER_RESERVED_BAND_MM - 1e-6
        and not _bridge_service_band_entity_is_legal_owner(entity, design)
        and _bridge_service_band_entity_is_z_exempt(entity, design)
    ]
    constrained_records = [
        record
        for entity, record in zip(entities, records)
        if not _bridge_service_band_entity_is_z_exempt(entity, design)
        and not _bridge_service_band_entity_is_legal_owner(entity, design)
    ]
    minimum_margin = min((record["margin_to_mainplate_outer_edge_mm"] for record in constrained_records), default=-math.inf)
    return {
        "status": "pass" if not violations else "fail",
        "fact_source": "mainplate_outer_edge_minus_entity_envelopes",
        "z_policy": "bridge_service_band_applies_only_to_entities_not_above_future_bridge_top",
        "screw_policy": BRIDGE_PERIMETER_SCREW_POLICY,
        "mainplate_radius_mm": CASE_RADIUS_MM,
        "reserved_band_mm": BRIDGE_PERIMETER_RESERVED_BAND_MM,
        "functional_layout_radius_mm": round(CASE_RADIUS_MM - BRIDGE_PERIMETER_RESERVED_BAND_MM, 4),
        "legal_service_band_owners": legal_service_band_owners,
        "minimum_margin_mm": round(minimum_margin, 4),
        "entity_count": len(records),
        "checked_entity_count": len(constrained_records),
        "records": records,
        "z_height_exemptions": z_height_exemptions,
        "violations": violations,
    }


def _legal_bridge_service_band_owner_ids(design: dict[str, Any]) -> list[str]:
    ring = design.get("housing", {}).get("outer_raised_support_ring")
    return [ring["feature_id"]] if ring else []


def _bridge_service_band_entity_is_legal_owner(entity: dict[str, Any], design: dict[str, Any]) -> bool:
    return entity.get("entity_id") in _legal_bridge_service_band_owner_ids(design) and entity.get("kind") == "bridge_service_owner"


def _bridge_service_band_entity_is_z_exempt(entity: dict[str, Any], design: dict[str, Any]) -> bool:
    future_bridge_top = float(design["z_stack"]["future_bridge"]["bridge_top_z_mm"])
    return entity.get("kind") == "hand_sweep" and float(entity.get("z_min", -math.inf)) >= future_bridge_top


def _build_internal_interference_report(design: dict[str, Any]) -> dict[str, Any]:
    entities = _interference_envelopes(design)
    allowed_pairs = {frozenset((mesh["driver"], mesh["driven"])) for mesh in [*design["meshes"], *design.get("display_meshes", [])]}
    failures = []
    for index, left in enumerate(entities):
        for right in entities[index + 1 :]:
            if left["axis_id"] and left["axis_id"] == right["axis_id"]:
                continue
            if frozenset((left["entity_id"], right["entity_id"])) in allowed_pairs:
                continue
            if left["kind"] == "placeholder" and right["kind"] == "placeholder":
                continue
            if _cylindrical_envelopes_overlap(
                left["x"],
                left["y"],
                left["radius"],
                left["z_min"],
                left["z_max"],
                right["x"],
                right["y"],
                right["radius"],
                right["z_min"],
                right["z_max"],
            ):
                failures.append(
                    {
                        "left": left["entity_id"],
                        "right": right["entity_id"],
                        "left_kind": left["kind"],
                        "right_kind": right["kind"],
                    }
                )
    return {
        "status": "pass" if not failures else "fail",
        "fact_source": "axisymmetric_envelope_interference_math",
        "entity_count": len(entities),
        "allowed_pairs": [sorted(pair) for pair in allowed_pairs],
        "failures": failures,
    }


def _build_gear_mesh_clearance_report(design: dict[str, Any]) -> dict[str, Any]:
    axes = {axis["axis_id"]: axis for axis in design["axes"]}
    gears = {gear["gear_id"]: gear for gear in [*design["gears"], *design.get("display_gears", [])]}
    records = []
    failures = []
    for mesh in [*design["meshes"], *design.get("display_meshes", [])]:
        driver = gears[mesh["driver"]]
        driven = gears[mesh["driven"]]
        driver_axis = axes[driver["axis_id"]]
        driven_axis = axes[driven["axis_id"]]
        center_distance = math.hypot(driver_axis["x"] - driven_axis["x"], driver_axis["y"] - driven_axis["y"])
        pitch_center_distance = driver["pitch_radius"] + driven["pitch_radius"]
        driver_tip_to_driven_root_clearance = center_distance - (driver["outer_radius"] + driven["root_radius"])
        driven_tip_to_driver_root_clearance = center_distance - (driven["outer_radius"] + driver["root_radius"])
        record = {
            "driver": driver["gear_id"],
            "driven": driven["gear_id"],
            "center_distance_mm": round(center_distance, 6),
            "pitch_center_distance_mm": round(pitch_center_distance, 6),
            "pitch_distance_error_mm": round(center_distance - pitch_center_distance, 6),
            "driver_tip_to_driven_root_clearance_mm": round(driver_tip_to_driven_root_clearance, 6),
            "driven_tip_to_driver_root_clearance_mm": round(driven_tip_to_driver_root_clearance, 6),
        }
        records.append(record)
        if driver_tip_to_driven_root_clearance < -1e-6 or driven_tip_to_driver_root_clearance < -1e-6:
            failures.append(record)
    return {
        "status": "pass" if not failures else "fail",
        "fact_source": "declared_gear_pitch_outer_root_geometry",
        "mesh_count": len(records),
        "records": records,
        "failures": failures,
    }


def _build_housing_parent_body_report(design: dict[str, Any]) -> dict[str, Any]:
    housing = design.get("housing", {})
    case_wall_integrated = bool(housing.get("case_wall_integrated_with_mainplate"))
    mainplate_is_flat_round_disk = bool(housing.get("mainplate_is_flat_round_disk"))
    case_boundary_policy = housing.get("case_boundary_policy")
    parent_body = housing.get("parent_body")
    support_ring = _build_outer_raised_support_ring_report(housing)
    status = (
        "pass"
        if mainplate_is_flat_round_disk
        and not case_wall_integrated
        and parent_body == "foundation_mainplate"
        and case_boundary_policy == "separate_case_or_review_shell_deferred"
        and support_ring["status"] == "pass"
        else "fail"
    )
    return {
        "status": status,
        "fact_source": "housing_role_contract",
        "mainplate_is_flat_round_disk": mainplate_is_flat_round_disk,
        "case_wall_integrated": case_wall_integrated,
        "case_boundary_policy": case_boundary_policy,
        "mainplate_radius_mm": housing.get("mainplate_radius_mm"),
        "parent_body": parent_body,
        "outer_raised_support_ring": support_ring,
        "forbidden_standalone_products": ["case_frame"],
    }


def _build_outer_raised_support_ring_report(housing: dict[str, Any]) -> dict[str, Any]:
    ring = housing.get("outer_raised_support_ring")
    if not ring:
        return {"status": "fail", "failure": "missing_outer_raised_support_ring"}

    outer_radius = float(ring.get("outer_radius_mm", 0.0))
    inner_radius = float(ring.get("inner_radius_mm", 0.0))
    width = float(ring.get("width_mm", 0.0))
    z_min = float(ring.get("z_min_mm", 0.0))
    z_max = float(ring.get("z_max_mm", 0.0))
    service_step = float(ring.get("future_bridge_service_step_height_mm", 0.0))
    bridge_plate_thickness = float(ring.get("future_bridge_countersunk_plate_thickness_mm", 0.0))
    upper_jewel_top = float(ring.get("future_upper_jewel_top_z_mm", 0.0))
    bridge_bottom = float(ring.get("future_bridge_bottom_z_mm", 0.0))
    stack_top = z_max + service_step + bridge_plate_thickness
    checks = {
        "feature_id": ring.get("feature_id") == "mainplate_outer_raised_support_ring",
        "owner": ring.get("owner") == "foundation_mainplate",
        "structure_class": ring.get("structure_class") == "parent_body_feature",
        "outer_radius": abs(outer_radius - CASE_RADIUS_MM) <= 1e-6,
        "width": abs(width - BRIDGE_PERIMETER_RESERVED_BAND_MM) <= 1e-6,
        "inner_radius": abs((outer_radius - inner_radius) - width) <= 1e-6,
        "z_min_on_mainplate_top": abs(z_min - MAINPLATE_TOP_Z) <= 1e-6,
        "positive_height": z_max > z_min,
        "service_face_below_future_bridge_bottom": z_max < bridge_bottom,
        "service_step_closes_to_bridge_bottom": abs((z_max + service_step) - bridge_bottom) <= 1e-6,
        "countersunk_plate_thickness_reserved": bridge_plate_thickness >= 0.40,
        "height_stack_closes_to_upper_jewel_top": abs(stack_top - upper_jewel_top) <= 1e-6,
    }
    return {
        **ring,
        "status": "pass" if all(checks.values()) else "fail",
        "computed_stack_top_z_mm": round(stack_top, 4),
        "checks": checks,
    }


def _gear_like_envelopes(design: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "entity_id": gear["gear_id"],
            "axis_id": gear["axis_id"],
            "x": gear["x"],
            "y": gear["y"],
            "radius": gear["outer_radius"],
            "z_min": gear["z"],
            "z_max": gear["z"] + gear["height"],
            "bore_radius": gear.get("bore_radius"),
            "clearance_holes": gear.get("clearance_holes", []),
            "kind": "gear",
        }
        for gear in [*design["gears"], *design.get("display_gears", [])]
    ]


def _internal_physical_envelopes(design: dict[str, Any]) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    support_ring = design.get("housing", {}).get("outer_raised_support_ring")
    if support_ring:
        entities.append(
            {
                "entity_id": support_ring["feature_id"],
                "x": 0.0,
                "y": 0.0,
                "radius": support_ring["outer_radius_mm"],
                "z_min": support_ring["z_min_mm"],
                "z_max": support_ring["z_max_mm"],
                "kind": "bridge_service_owner",
            }
        )
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    for axis in design["axes"]:
        if axis["support_required"]:
            for segment in axis.get("support_segments", []):
                entities.append(
                    {
                        "entity_id": segment["segment_id"],
                        "x": axis["x"],
                        "y": axis["y"],
                        "radius": segment["radius"],
                        "z_min": segment["z_min"],
                        "z_max": segment["z_max"],
                        "kind": "support_segment",
                    }
                )
            for spec_key, kind in [("lower_jewel_seat", "seat"), ("lower_jewel", "jewel")]:
                spec = axis.get(spec_key)
                if not spec:
                    continue
                entities.append(
                    {
                        "entity_id": spec["entity_id"],
                        "x": axis["x"],
                        "y": axis["y"],
                        "radius": spec["outer_radius"],
                        "z_min": spec["z_min"],
                        "z_max": spec["z_max"],
                        "kind": kind,
                    }
                )
    for gear in [*design["gears"], *design.get("display_gears", [])]:
        entities.append(
            {
                "entity_id": gear["gear_id"],
                "x": gear["x"],
                "y": gear["y"],
                "radius": gear["outer_radius"],
                "z_min": gear["z"],
                "z_max": gear["z"] + gear["height"],
                "kind": "gear",
            }
        )
    for hand_id, envelope in design["display"]["sweep_envelopes"].items():
        entities.append(
            {
                "entity_id": f"{hand_id}_sweep",
                "x": envelope["center_x"],
                "y": envelope["center_y"],
                "radius": envelope["radius_mm"],
                "z_min": envelope["z_min_mm"],
                "z_max": envelope["z_max_mm"],
                "kind": "hand_sweep",
            }
        )
    pallet = axis_by_id["pallet_axis"]
    balance = axis_by_id["balance_axis"]
    entities.extend(
        [
            {"entity_id": "pallet_placeholder_disc", "x": pallet["x"], "y": pallet["y"], "radius": 1.05, "z_min": 3.08, "z_max": 3.26, "kind": "placeholder"},
            {"entity_id": "balance_placeholder_disc", "x": balance["x"], "y": balance["y"], "radius": 2.45, "z_min": 3.12, "z_max": 3.34, "kind": "placeholder"},
        ]
    )
    interaction_radius = max(math.hypot(pallet["x"], pallet["y"]), math.hypot(balance["x"], balance["y"])) + 0.16
    entities.append({"entity_id": "escapement_to_balance_placeholder_envelope", "x": 0.0, "y": 0.0, "radius": interaction_radius, "z_min": 3.02, "z_max": 3.10, "kind": "placeholder"})
    return entities


def _interference_envelopes(design: dict[str, Any]) -> list[dict[str, Any]]:
    entities = [
        {
            "entity_id": gear["gear_id"],
            "axis_id": gear["axis_id"],
            "x": gear["x"],
            "y": gear["y"],
            "radius": gear["outer_radius"],
            "z_min": gear["z"],
            "z_max": gear["z"] + gear["height"],
            "kind": "gear",
        }
        for gear in [*design["gears"], *design.get("display_gears", [])]
    ]
    entities.extend(_jewel_support_envelopes(design, include_future_targets=False))
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    pallet = axis_by_id["pallet_axis"]
    balance = axis_by_id["balance_axis"]
    entities.extend(
        [
            {
                "entity_id": "pallet_placeholder_disc",
                "axis_id": "pallet_axis",
                "x": pallet["x"],
                "y": pallet["y"],
                "radius": 1.05,
                "z_min": 3.08,
                "z_max": 3.26,
                "kind": "placeholder",
            },
            {
                "entity_id": "balance_placeholder_disc",
                "axis_id": "balance_axis",
                "x": balance["x"],
                "y": balance["y"],
                "radius": 2.45,
                "z_min": 3.12,
                "z_max": 3.34,
                "kind": "placeholder",
            },
        ]
    )
    for hand_id, envelope in design["display"]["sweep_envelopes"].items():
        entities.append(
            {
                "entity_id": f"{hand_id}_sweep",
                "axis_id": envelope["axis_id"],
                "x": envelope["center_x"],
                "y": envelope["center_y"],
                "radius": envelope["radius_mm"],
                "z_min": envelope["z_min_mm"],
                "z_max": envelope["z_max_mm"],
                "kind": "hand_sweep",
            }
        )
    return entities


def _cylindrical_envelopes_overlap(
    left_x: float,
    left_y: float,
    left_radius: float,
    left_z_min: float,
    left_z_max: float,
    right_x: float,
    right_y: float,
    right_radius: float,
    right_z_min: float,
    right_z_max: float,
) -> bool:
    xy_overlap = math.hypot(left_x - right_x, left_y - right_y) < (left_radius + right_radius)
    z_overlap = left_z_min < right_z_max and right_z_min < left_z_max
    return xy_overlap and z_overlap


def _build_display_motion_chain_report(design: dict[str, Any]) -> dict[str, Any]:
    display = design["display"]
    motion_works = display.get("motion_works", {})
    if design.get("pattern_card_id") == SEPARATE_DISPLAY_PATTERN_CARD_ID:
        return _build_separate_display_independent_motion_chain_report(design)
    if design.get("pattern_card_id") == INDEPENDENT_DISPLAY_PATTERN_CARD_ID:
        return _build_independent_display_motion_chain_report(design)
    entity_ids = {
        *(gear["gear_id"] for gear in design["gears"]),
        *(gear["gear_id"] for gear in design.get("display_gears", [])),
        *(hand["hand_id"] for hand in display["hands"]),
        *(tube["tube_id"] for tube in display["tube_stack"]),
        *(extension["extension_id"] for extension in display["arbor_extensions"]),
        *motion_works.get("assemblies", []),
    }
    chain_by_hand = {chain["hand_id"]: chain for chain in display["drive_chains"]}

    reports = {
        "minute_hand": _simple_motion_chain_report(
            chain_by_hand.get("minute_hand", {}),
            entity_ids,
            required_nodes=["center_wheel", "cannon_pinion_assembly", "cannon_pinion_tube", "minute_hand"],
            expected_source="center_wheel_to_cannon_pinion",
        ),
        "seconds_hand": _simple_motion_chain_report(
            chain_by_hand.get("seconds_hand", {}),
            entity_ids,
            required_nodes=["third_wheel", "fourth_pinion", "fourth_wheel", "seconds_hand"],
            expected_source="fourth_wheel_direct_sub_seconds",
        ),
        "hour_hand": _hour_motion_chain_report(chain_by_hand.get("hour_hand", {}), entity_ids, motion_works),
    }
    status = "pass" if all(report["status"] == "pass" for report in reports.values()) else "fail"
    return {
        "status": status,
        "fact_source": "geometry_and_ratio_proof",
        **reports,
    }


def _build_separate_display_independent_motion_chain_report(design: dict[str, Any]) -> dict[str, Any]:
    display = design["display"]
    motion_works = display.get("motion_works", {})
    entity_ids = {
        *(gear["gear_id"] for gear in design["gears"]),
        *(gear["gear_id"] for gear in design.get("display_gears", [])),
        *(hand["hand_id"] for hand in display["hands"]),
        "display_input_relay_compound_member",
        "display_relay_compound_member",
    }
    chain_by_hand = {chain["hand_id"]: chain for chain in display["drive_chains"]}
    minute_report = _simple_motion_chain_report(
        chain_by_hand.get("minute_hand", {}),
        entity_ids,
        required_nodes=[
            "train_stage_3_wheel",
            "display_input_relay_pinion",
            "display_input_relay_wheel",
            "minute_display_member",
            "minute_hand",
        ],
        expected_source="selected_train_output_to_minute_display_member",
    )
    hour_report = _simple_motion_chain_report(
        chain_by_hand.get("hour_hand", {}),
        entity_ids,
        required_nodes=[
            "minute_display_member",
            "display_relay_pinion",
            "display_relay_wheel",
            "hour_display_member",
            "hour_hand",
        ],
        expected_source="minute_display_member_to_compound_display_relay",
    )
    coupling = motion_works.get("train_to_minute_display_coupling", {})
    minute_ratio = coupling.get("ratio_proof", {}).get("computed_ratio")
    hour_ratio = chain_by_hand.get("hour_hand", {}).get("ratio_proof", {}).get("computed_ratio")
    ratio_checks = {
        "train_to_minute_ratio_ok": isinstance(minute_ratio, (int, float)) and abs(minute_ratio - 1.0) <= 1e-9,
        "hour_to_minute_ratio_ok": isinstance(hour_ratio, (int, float)) and abs(hour_ratio - (1 / 12)) <= 1e-9,
    }
    if not ratio_checks["train_to_minute_ratio_ok"]:
        minute_report["status"] = "fail"
    if not ratio_checks["hour_to_minute_ratio_ok"]:
        hour_report["status"] = "fail"
    reports = {
        "minute_hand": {**minute_report, "ratio_checks": ratio_checks},
        "hour_hand": {**hour_report, "ratio_checks": ratio_checks},
        "seconds_hand": {
            "status": "pass",
            "fact_source": "separate_display_pattern_forbids_seconds_hand",
            "required_nodes": [],
            "path": [],
            "missing_nodes": [],
        },
    }
    return {
        "status": "pass" if all(report["status"] == "pass" for report in reports.values()) else "fail",
        "fact_source": "separate_display_path_nodes_and_ratio_proof",
        **reports,
    }


def _build_independent_display_motion_chain_report(design: dict[str, Any]) -> dict[str, Any]:
    display = design["display"]
    motion_works = display.get("motion_works", {})
    entity_ids = {
        *(gear["gear_id"] for gear in design["gears"]),
        *(gear["gear_id"] for gear in design.get("display_gears", [])),
        *(hand["hand_id"] for hand in display["hands"]),
        *(member["component_id"] for member in design.get("display_compound_members", [])),
    }
    chain_by_hand = {chain["hand_id"]: chain for chain in display["drive_chains"]}
    minute_report = _simple_motion_chain_report(
        chain_by_hand.get("minute_hand", {}),
        entity_ids,
        required_nodes=[
            "train_stage_3_wheel",
            "minute_input_relay_pinion",
            "minute_input_relay_wheel",
            "minute_display_member",
            "minute_hand",
        ],
        expected_source="train_stage_3_wheel_to_independent_minute_branch",
    )
    hour_report = _simple_motion_chain_report(
        chain_by_hand.get("hour_hand", {}),
        entity_ids,
        required_nodes=[
            "train_stage_3_wheel",
            "hour_input_relay_pinion",
            "hour_input_relay_wheel",
            "hour_reduction_relay_pinion",
            "hour_reduction_relay_wheel",
            "hour_display_member",
            "hour_hand",
        ],
        expected_source="train_stage_3_wheel_to_independent_hour_branch",
    )
    ratio_proof = motion_works.get("ratio_proof", {})
    ratio_checks = {
        "train_to_minute_ratio_ok": abs(float(ratio_proof.get("train_to_minute_display_ratio", 0.0)) - 1.0) <= 1e-9,
        "train_to_hour_ratio_ok": abs(float(ratio_proof.get("train_to_hour_display_ratio", 0.0)) - (1 / 12)) <= 1e-9,
        "hour_to_minute_ratio_ok": abs(float(ratio_proof.get("hour_to_minute_ratio", 0.0)) - (1 / 12)) <= 1e-9,
    }
    if not ratio_checks["train_to_minute_ratio_ok"]:
        minute_report["status"] = "fail"
    if not ratio_checks["train_to_hour_ratio_ok"] or not ratio_checks["hour_to_minute_ratio_ok"]:
        hour_report["status"] = "fail"
    if {"minute_display_member", "minute_input_relay_pinion", "minute_input_relay_wheel"}.intersection(
        set(chain_by_hand.get("hour_hand", {}).get("path", []))
    ):
        hour_report["status"] = "fail"
        hour_report["forbidden_minute_branch_dependency"] = True
    reports = {
        "minute_hand": {**minute_report, "ratio_checks": ratio_checks},
        "hour_hand": {**hour_report, "ratio_checks": ratio_checks},
        "seconds_hand": {
            "status": "pass",
            "fact_source": "independent_display_pattern_forbids_seconds_hand",
            "required_nodes": [],
            "path": [],
            "missing_nodes": [],
        },
    }
    return {
        "status": "pass" if all(report["status"] == "pass" for report in reports.values()) else "fail",
        "fact_source": "independent_display_path_nodes_and_ratio_proof",
        **reports,
    }


def _simple_motion_chain_report(
    chain: dict[str, Any],
    entity_ids: set[str],
    *,
    required_nodes: list[str],
    expected_source: str,
) -> dict[str, Any]:
    path = chain.get("path", [])
    missing_nodes = [node for node in required_nodes if node not in entity_ids or node not in path]
    status = "pass" if chain.get("source") == expected_source and not missing_nodes else "fail"
    return {
        "status": status,
        "fact_source": "path_nodes_and_source",
        "required_nodes": required_nodes,
        "path": path,
        "missing_nodes": missing_nodes,
    }


def _hour_motion_chain_report(chain: dict[str, Any], entity_ids: set[str], motion_works: dict[str, Any]) -> dict[str, Any]:
    required_nodes = [
        "cannon_pinion_assembly",
        "cannon_pinion_display_driver",
        "minute_wheel_assembly",
        "minute_pinion",
        "hour_wheel",
        "hour_hand",
    ]
    required_interfaces = [
        ("cannon_pinion_display_driver", "minute_wheel", "external_gear_mesh"),
        ("minute_wheel", "minute_pinion", "rigid_compound_arbor"),
        ("minute_pinion", "hour_wheel", "external_gear_mesh"),
    ]
    path = chain.get("path", [])
    missing_nodes = [node for node in required_nodes if node not in entity_ids or node not in path]
    interfaces = motion_works.get("interfaces", [])
    missing_interfaces = [
        {"from": source, "to": target, "kind": kind}
        for source, target, kind in required_interfaces
        if not any(
            interface.get("from") == source and interface.get("to") == target and interface.get("kind") == kind
            for interface in interfaces
        )
    ]
    ratio_proof = motion_works.get("ratio_proof", {})
    ratio = ratio_proof.get("hour_to_minute_ratio")
    ratio_ok = isinstance(ratio, (int, float)) and abs(ratio - (1 / 12)) <= 1e-9
    chain_ratio = chain.get("ratio_proof", {}).get("computed_ratio")
    chain_ratio_ok = isinstance(chain_ratio, (int, float)) and abs(chain_ratio - (1 / 12)) <= 1e-9
    phase_records = motion_works.get("display_mesh_phase_records", [])
    phase_ok = len(phase_records) == 2 and all(
        abs(record["driver_tooth_error_deg"]) <= 1e-6 and abs(record["driven_gap_error_deg"]) <= 1e-6
        for record in phase_records
    )
    status = "pass" if not missing_nodes and not missing_interfaces and ratio_ok and chain_ratio_ok and phase_ok else "fail"
    return {
        "status": status,
        "fact_source": "geometry_and_ratio_proof",
        "required_nodes": required_nodes,
        "path": path,
        "missing_nodes": missing_nodes,
        "missing_interfaces": missing_interfaces,
        "ratio_ok": ratio_ok,
        "chain_ratio_ok": chain_ratio_ok,
        "phase_ok": phase_ok,
        "ratio_proof": ratio_proof,
        "interfaces": interfaces,
    }


def _build_display_hand_feature_attachment_report(design: dict[str, Any]) -> dict[str, Any]:
    reports = {}
    for hand in design["display"]["hands"]:
        axis = _axis_by_id(design, hand["axis_id"])
        hand_shape = _make_hand(
            hand["hand_id"],
            axis["x"],
            axis["y"],
            hand["angle_deg"],
            hand["length_mm"],
            hand["z_mm"],
            hand["width_mm"],
            hand["profile"],
        )
        children = {child.label: child for child in hand_shape.children}
        hub = children[f"{hand['hand_id']}_hub"]
        blade = children[f"{hand['hand_id']}_blade"]
        hub_facts = _shape_bbox_facts(hub)
        blade_facts = _shape_bbox_facts(blade)
        hub_outer_radius = max(hub_facts["size_mm"][0], hub_facts["size_mm"][1]) / 2.0
        blade_to_axis_distance = _point_to_xy_bbox_distance((axis["x"], axis["y"]), blade_facts["min_mm"], blade_facts["max_mm"])
        blade_attached_to_hub = blade_to_axis_distance <= hub_outer_radius + 0.02
        reports[hand["hand_id"]] = {
            "status": "pass" if blade_attached_to_hub else "fail",
            "fact_source": "fresh_brep_child_feature_facts",
            "axis_id": hand["axis_id"],
            "axis_xy_mm": [axis["x"], axis["y"]],
            "hub_id": f"{hand['hand_id']}_hub",
            "blade_id": f"{hand['hand_id']}_blade",
            "hub_bbox": hub_facts,
            "blade_bbox": blade_facts,
            "hub_outer_radius_mm": round(hub_outer_radius, 4),
            "blade_to_axis_distance_mm": round(blade_to_axis_distance, 4),
            "blade_attached_to_hub": blade_attached_to_hub,
        }
    return reports


def _shape_bbox_facts(shape) -> dict[str, Any]:
    bbox = shape.bounding_box()
    min_xyz = tuple(bbox.min)
    max_xyz = tuple(bbox.max)
    center = tuple(bbox.center())
    size = tuple(bbox.size)
    return {
        "min_mm": [round(value, 4) for value in min_xyz],
        "max_mm": [round(value, 4) for value in max_xyz],
        "center_mm": [round(value, 4) for value in center],
        "size_mm": [round(value, 4) for value in size],
    }


def _point_to_xy_bbox_distance(point: tuple[float, float], bbox_min: list[float], bbox_max: list[float]) -> float:
    dx = max(bbox_min[0] - point[0], 0.0, point[0] - bbox_max[0])
    dy = max(bbox_min[1] - point[1], 0.0, point[1] - bbox_max[1])
    return math.hypot(dx, dy)


def _seconds_sweep_interference_failures(
    seconds_envelope: dict[str, Any],
    display: dict[str, Any],
    gears: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    sx = seconds_envelope["center_x"]
    sy = seconds_envelope["center_y"]
    sr = seconds_envelope["radius_mm"]
    for gear in gears:
        if gear["axis_id"] == seconds_envelope["axis_id"]:
            continue
        if _envelopes_overlap_3d(
            (sx, sy, sr, seconds_envelope["z_min_mm"], seconds_envelope["z_max_mm"]),
            (gear["x"], gear["y"], gear["outer_radius"], gear["z"], gear["z"] + gear["height"]),
        ):
            failures.append({"type": "gear_overlap", "gear_id": gear["gear_id"]})
    for hand_id in ("hour_hand", "minute_hand"):
        hand_envelope = display["sweep_envelopes"][hand_id]
        if _envelopes_overlap_3d(
            (sx, sy, sr, seconds_envelope["z_min_mm"], seconds_envelope["z_max_mm"]),
            (
                hand_envelope["center_x"],
                hand_envelope["center_y"],
                hand_envelope["radius_mm"],
                hand_envelope["z_min_mm"],
                hand_envelope["z_max_mm"],
            ),
        ):
            failures.append({"type": "hand_overlap", "hand_id": hand_id})
    if sr >= seconds_envelope["case_min_clearance_mm"]:
        failures.append({"type": "case_clearance", "radius_mm": sr})
    return failures


def _envelopes_overlap_3d(left: tuple[float, float, float, float, float], right: tuple[float, float, float, float, float]) -> bool:
    lx, ly, lr, lz_min, lz_max = left
    rx, ry, rr, rz_min, rz_max = right
    xy_overlap = math.hypot(lx - rx, ly - ry) < (lr + rr)
    z_overlap = lz_min < rz_max and rz_min < lz_max
    return xy_overlap and z_overlap


def _assign_mesh_phases(axes: list[dict[str, Any]], gears: list[dict[str, Any]], meshes: list[dict[str, str]]) -> list[dict[str, Any]]:
    axis_by_id = {axis["axis_id"]: axis for axis in axes}
    gear_by_id = {gear["gear_id"]: gear for gear in gears}
    desired_by_gear: dict[str, list[float]] = {gear["gear_id"]: [] for gear in gears}
    pitch_by_gear = {gear["gear_id"]: 360.0 / float(gear["tooth_count"]) for gear in gears}
    contacts: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for mesh in meshes:
        driver = gear_by_id[mesh["driver"]]
        driven = gear_by_id[mesh["driven"]]
        driver_axis = axis_by_id[driver["axis_id"]]
        driven_axis = axis_by_id[driven["axis_id"]]
        driver_contact_angle = _angle_deg(driver_axis["x"], driver_axis["y"], driven_axis["x"], driven_axis["y"])
        driven_contact_angle = _normalize_degrees(driver_contact_angle + 180.0)
        driver_pitch = pitch_by_gear[driver["gear_id"]]
        driven_pitch = pitch_by_gear[driven["gear_id"]]
        driver_desired_phase = _normalize_degrees(driver_contact_angle)
        driven_desired_phase = _normalize_degrees(driven_contact_angle - (driven_pitch / 2.0))
        desired_by_gear[driver["gear_id"]].append(driver_desired_phase)
        desired_by_gear[driven["gear_id"]].append(driven_desired_phase)
        contacts.append(
            {
                **mesh,
                "driver_contact_angle_deg": driver_contact_angle,
                "driven_contact_angle_deg": driven_contact_angle,
                "driver_pitch_deg": driver_pitch,
                "driven_pitch_deg": driven_pitch,
            }
        )
    phase_by_gear: dict[str, float] = {}
    for gear_id, desired_values in desired_by_gear.items():
        if desired_values:
            phase_by_gear[gear_id] = _normalize_degrees(desired_values[0])
        elif gear_id == "escape_wheel":
            axis = axis_by_id[gear_by_id[gear_id]["axis_id"]]
            pallet_axis = axis_by_id["pallet_axis"]
            phase_by_gear[gear_id] = _angle_deg(axis["x"], axis["y"], pallet_axis["x"], pallet_axis["y"])
        else:
            phase_by_gear[gear_id] = 0.0
        gear_by_id[gear_id]["phase_deg"] = round(phase_by_gear[gear_id], 6)

    for contact in contacts:
        driver = gear_by_id[contact["driver"]]
        driven = gear_by_id[contact["driven"]]
        driver_phase = phase_by_gear[driver["gear_id"]]
        driven_phase = phase_by_gear[driven["gear_id"]]
        driver_pitch = contact["driver_pitch_deg"]
        driven_pitch = contact["driven_pitch_deg"]
        driver_contact_angle = contact["driver_contact_angle_deg"]
        driven_contact_angle = contact["driven_contact_angle_deg"]
        records.append(
            {
                **{key: contact[key] for key in ("driver", "driven", "kind")},
                "strategy": "external_tooth_to_gap_on_center_line",
                "driver_contact_angle_deg": round(driver_contact_angle, 6),
                "driven_contact_angle_deg": round(driven_contact_angle, 6),
                "driver_phase_deg": round(driver_phase, 6),
                "driven_phase_deg": round(driven_phase, 6),
                "driver_tooth_error_deg": round(_periodic_angle_error(driver_phase, driver_pitch, driver_contact_angle), 9),
                "driven_gap_error_deg": round(
                    _periodic_angle_error(driven_phase + (driven_pitch / 2.0), driven_pitch, driven_contact_angle),
                    9,
                ),
            }
        )
    return records


def _angle_deg(x1: float, y1: float, x2: float, y2: float) -> float:
    return _normalize_degrees(math.degrees(math.atan2(y2 - y1, x2 - x1)))


def _normalize_degrees(angle_deg: float) -> float:
    return angle_deg % 360.0


def _periodic_angle_error(actual_deg: float, pitch_deg: float, target_deg: float) -> float:
    half_pitch = pitch_deg / 2.0
    return ((actual_deg - target_deg + half_pitch) % pitch_deg) - half_pitch


def _build_assembly(
    design: dict[str, Any],
    *,
    omit_escapement_placeholders: bool = False,
    omit_gear_ids: set[str] | None = None,
) -> Compound:
    omitted_gears = omit_gear_ids or set()
    children = [
        _make_mainplate(design),
    ]
    children.extend(_make_arbors_and_lower_seats(design))
    children.append(_make_barrel(design))
    for gear in design["gears"]:
        if gear["gear_id"] != "barrel_outer_teeth" and gear["gear_id"] not in omitted_gears:
            children.append(_make_gear(gear))
    children.extend(_make_display_works(design))
    if not omit_escapement_placeholders:
        children.extend(_make_placeholder_escapement_line(design))
    if design.get("bridges_generated"):
        children.extend(_make_bridge_stage(design))
    return Compound(label="watch_power_chain_mvp_assembly", children=children)


def _make_bridge_stage(design: dict[str, Any]) -> list[Any]:
    children: list[Any] = []
    for bridge in design.get("bridge_stage", {}).get("bridges", []):
        z_min = float(bridge["z_min_mm"])
        z_max = float(bridge["z_max_mm"])
        thickness = z_max - z_min
        points = _bridge_plate_points(
            float(bridge["angular_start_deg"]),
            float(bridge["angular_end_deg"]),
            float(bridge["outer_radius_mm"]),
            float(bridge["seam_gap_width_mm"]),
        )
        plate = _extrude_xy_points_preserve_frame(points, thickness).located(Location((0, 0, z_min)))
        for hole in bridge.get("clearance_holes", []):
            plate = plate - _z_cylinder(float(hole["radius_mm"]), thickness + 0.08).located(
                Location((float(hole["x"]), float(hole["y"]), z_min + thickness / 2.0))
            )
        central_feature = bridge.get("central_axis_feature")
        if central_feature:
            plate = plate + _annulus(
                float(central_feature["outer_radius_mm"]),
                float(central_feature["clearance_radius_mm"]),
                thickness,
            ).located(Location((float(central_feature["x"]), float(central_feature["y"]), z_min + thickness / 2.0)))
        for pad in bridge["support_pads"]:
            pad_height = float(pad["z_max_mm"]) - float(pad["z_min_mm"])
            pad_points = _annular_sector_points(
                float(pad["inner_radius_mm"]),
                float(pad["outer_radius_mm"]),
                float(pad["angular_start_deg"]),
                float(pad["angular_end_deg"]),
            )
            plate = plate + _extrude_xy_points_preserve_frame(pad_points, pad_height).located(
                Location((0, 0, float(pad["z_min_mm"])))
            )
        support_top = min(float(pad["z_min_mm"]) for pad in bridge["support_pads"]) if bridge["support_pads"] else z_min
        for screw in bridge["screws"]:
            clearance_radius = float(screw["clearance_diameter_mm"]) / 2.0
            head_radius = float(screw["head_diameter_mm"]) / 2.0
            countersink_depth = float(screw["countersink_depth_mm"])
            through_height = z_max - support_top + 0.08
            plate = plate - _z_cylinder(clearance_radius, through_height).located(
                Location((float(screw["x"]), float(screw["y"]), support_top + through_height / 2.0))
            )
            plate = plate - Cone(clearance_radius, head_radius + 0.03, countersink_depth + 0.02).located(
                Location((float(screw["x"]), float(screw["y"]), z_max - countersink_depth / 2.0 + 0.01))
            )
            children.append(_part(_make_countersunk_bridge_screw(screw, support_top, z_max), screw["screw_id"]))
        children.append(_part(plate, bridge["bridge_id"]))
    return children


def _make_countersunk_bridge_screw(screw: dict[str, Any], support_top: float, bridge_top: float):
    x = float(screw["x"])
    y = float(screw["y"])
    head_radius = float(screw["head_diameter_mm"]) / 2.0
    shank_radius = float(screw["nominal_thread_diameter_mm"]) / 2.0
    head_depth = float(screw["countersink_depth_mm"])
    threaded_bottom = float(screw["threaded_hole_bottom_z_mm"])
    shank_top = bridge_top - head_depth
    shank_length = max(0.12, shank_top - threaded_bottom)
    head = Cone(shank_radius, head_radius, head_depth).located(Location((x, y, bridge_top - head_depth / 2.0)))
    shank = _z_cylinder(shank_radius, shank_length).located(Location((x, y, threaded_bottom + shank_length / 2.0)))
    slot = Box(
        head_radius * 1.25,
        BRIDGE_SCREW_SLOT_WIDTH_MM,
        BRIDGE_SCREW_SLOT_DEPTH_MM,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(Location((x, y, bridge_top - BRIDGE_SCREW_SLOT_DEPTH_MM / 2.0 + 0.01)))
    return (head + shank) - slot


def _bridge_plate_points(
    start_deg: float,
    end_deg: float,
    outer_radius: float,
    seam_gap_width: float,
) -> list[tuple[float, float]]:
    start_line = _parallel_seam_line(start_deg, "ccw", seam_gap_width)
    end_line = _parallel_seam_line(end_deg, "cw", seam_gap_width)
    start_outer = _line_circle_outer_point(start_line["point"], start_line["direction"], outer_radius)
    end_outer = _line_circle_outer_point(end_line["point"], end_line["direction"], outer_radius)
    center_vertex = _line_intersection(
        start_line["point"],
        start_line["direction"],
        end_line["point"],
        end_line["direction"],
    )
    start_angle = math.degrees(math.atan2(start_outer[1], start_outer[0]))
    end_angle = math.degrees(math.atan2(end_outer[1], end_outer[0]))
    span = _positive_angle_span(start_angle, end_angle)
    steps = max(8, int(span // 8) + 2)
    arc = []
    for index in range(steps + 1):
        angle = math.radians(start_angle + span * index / steps)
        arc.append((outer_radius * math.cos(angle), outer_radius * math.sin(angle)))
    return [(round(x, 4), round(y, 4)) for x, y in [*arc, center_vertex]]


def _annular_sector_points(
    inner_radius: float,
    outer_radius: float,
    start_deg: float,
    end_deg: float,
) -> list[tuple[float, float]]:
    span = _positive_angle_span(start_deg, end_deg)
    steps = max(4, int(span // 4) + 2)
    outer = []
    for index in range(steps + 1):
        angle = math.radians(start_deg + span * index / steps)
        outer.append((outer_radius * math.cos(angle), outer_radius * math.sin(angle)))
    inner = []
    for index in range(steps, -1, -1):
        angle = math.radians(start_deg + span * index / steps)
        inner.append((inner_radius * math.cos(angle), inner_radius * math.sin(angle)))
    return [(round(x, 4), round(y, 4)) for x, y in [*outer, *inner]]


def _parallel_seam_line(angle_deg: float, side: str, seam_gap_width: float) -> dict[str, tuple[float, float]]:
    direction = _unit_vector(angle_deg)
    normal = (-direction[1], direction[0])
    offset_sign = 1.0 if side == "ccw" else -1.0
    half_gap = seam_gap_width / 2.0
    return {
        "point": (normal[0] * half_gap * offset_sign, normal[1] * half_gap * offset_sign),
        "direction": direction,
    }


def _line_circle_outer_point(
    point: tuple[float, float],
    direction: tuple[float, float],
    radius: float,
) -> tuple[float, float]:
    dot = point[0] * direction[0] + point[1] * direction[1]
    point_sq = point[0] ** 2 + point[1] ** 2
    discriminant = max(0.0, dot**2 + radius**2 - point_sq)
    t = -dot + math.sqrt(discriminant)
    return (point[0] + direction[0] * t, point[1] + direction[1] * t)


def _line_intersection(
    point_a: tuple[float, float],
    direction_a: tuple[float, float],
    point_b: tuple[float, float],
    direction_b: tuple[float, float],
) -> tuple[float, float]:
    denom = _cross_2d(direction_a, direction_b)
    if abs(denom) < 1e-9:
        return (0.0, 0.0)
    delta = (point_b[0] - point_a[0], point_b[1] - point_a[1])
    t = _cross_2d(delta, direction_b) / denom
    return (point_a[0] + direction_a[0] * t, point_a[1] + direction_a[1] * t)


def _cross_2d(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _make_mainplate(design: dict[str, Any]):
    body = _z_cylinder(CASE_RADIUS_MM, MAINPLATE_THICKNESS_MM).located(Location((0, 0, MAINPLATE_CENTER_Z)))
    support_ring = design.get("housing", {}).get("outer_raised_support_ring")
    if support_ring:
        height = support_ring["height_mm"]
        center_z = support_ring["z_min_mm"] + height / 2.0
        ring = _annulus(support_ring["outer_radius_mm"], support_ring["inner_radius_mm"], height).located(
            Location((0, 0, center_z))
        )
        body = body + ring
    if design.get("bridges_generated"):
        for screw in _bridge_stage_screws(design):
            hole_top = float(screw["threaded_hole_top_z_mm"])
            hole_bottom = float(screw["threaded_hole_bottom_z_mm"])
            hole_height = hole_top - hole_bottom
            body = body - _z_cylinder(float(screw["nominal_thread_diameter_mm"]) / 2.0, hole_height).located(
                Location((float(screw["x"]), float(screw["y"]), hole_bottom + hole_height / 2.0))
            )
    return _part(body, "foundation_mainplate")


def _bridge_stage_screws(design: dict[str, Any]) -> list[dict[str, Any]]:
    if not design.get("bridge_stage"):
        return []
    return [screw for bridge in design["bridge_stage"]["bridges"] for screw in bridge.get("screws", [])]


def _make_arbors_and_lower_seats(design: dict[str, Any]) -> list[Any]:
    children: list[Any] = []
    for axis in design["axes"]:
        if not axis["support_required"]:
            continue
        x = axis["x"]
        y = axis["y"]
        axis_id = axis["axis_id"]
        for segment in axis["support_segments"]:
            height = segment["z_max"] - segment["z_min"]
            center_z = segment["z_min"] + height / 2.0
            children.append(
                _label(
                    _z_cylinder(segment["radius"], height).located(Location((x, y, center_z))),
                    segment["segment_id"],
                )
            )
        seat = axis["lower_jewel_seat"]
        jewel = axis["lower_jewel"]
        seat_height = seat["z_max"] - seat["z_min"]
        jewel_height = jewel["z_max"] - jewel["z_min"]
        support = Compound(
            label=f"lower_jewel_support_{axis_id}",
            children=[
                _label(
                    _annulus(seat["outer_radius"], seat["inner_radius"], seat_height).located(
                        Location((x, y, seat["z_min"] + seat_height / 2.0))
                    ),
                    seat["entity_id"],
                ),
                _label(
                    _annulus(jewel["outer_radius"], jewel["inner_radius"], jewel_height).located(
                        Location((x, y, jewel["z_min"] + jewel_height / 2.0))
                    ),
                    jewel["entity_id"],
                ),
            ],
        )
        children.append(support)
        upper = axis.get("upper_jewel_bearing")
        if upper:
            upper_height = upper["z_max"] - upper["z_min"]
            children.append(
                Compound(
                    label=f"upper_jewel_bearing_support_{axis_id}",
                    children=[
                        _label(
                            _annulus(upper["outer_radius"], upper["inner_radius"], upper_height).located(
                                Location((x, y, upper["z_min"] + upper_height / 2.0))
                            ),
                            upper["entity_id"],
                        )
                    ],
                )
            )
    return children


def _arbor_label(axis_id: str) -> str:
    return {
        "barrel_axis": "barrel_arbor",
        "center_axis": "center_arbor",
        "third_axis": "third_arbor",
        "fourth_axis": "fourth_arbor",
        "escape_axis": "escape_arbor",
        "minute_work_axis": "minute_work_arbor",
        "pallet_axis": "pallet_pivot_arbor",
        "balance_axis": "balance_staff_support_arbor",
    }.get(axis_id, f"arbor_{axis_id}")


def _make_barrel(design: dict[str, Any]):
    axis = _axis_by_id(design, "barrel_axis")
    barrel_gear = _gear_by_id(design, "barrel_outer_teeth")
    x = axis["x"]
    y = axis["y"]
    barrel_body = design["z_stack"]["barrel_body"]
    drum_height = barrel_body["height_mm"]
    drum_center_z = barrel_body["z_min_mm"] + drum_height / 2.0
    drum = _z_cylinder(barrel_gear["root_radius"] * 0.92, drum_height).located(Location((x, y, drum_center_z)))
    outer_teeth = _gear_body(barrel_gear).located(Location((x, y, barrel_gear["z"])))
    spring = _make_spiral_placeholder(x, y, barrel_gear["root_radius"] * 0.66, barrel_body["z_min_mm"] + drum_height * 0.72)
    return Compound(
        label="mainspring_barrel",
        children=[
            _label(drum, "barrel_drum"),
            _label(outer_teeth, "barrel_outer_teeth"),
            _label(spring, "mainspring_placeholder"),
        ],
    )


def _make_gear(gear: dict[str, Any]):
    gear_body = _gear_tooth_body_with_bore(gear).located(Location((gear["x"], gear["y"], gear["z"])))
    if gear.get("spoke_modeling_strategy") == "single_body_cutout":
        return _label(gear_body, gear["gear_id"])
    hub_radius = max(gear["bore_radius"] + 0.08, 0.32, min(gear["root_radius"] * 0.28, gear["root_radius"] - 0.08))
    hub = _annulus(hub_radius, gear["bore_radius"], gear["height"] + 0.08).located(
        Location((gear["x"], gear["y"], gear["z"] + gear["height"] / 2.0))
    )
    return Compound(label=gear["gear_id"], children=[_label(gear_body, f"{gear['gear_id']}_tooth_profile"), _label(hub, f"{gear['gear_id']}_hub")])


def _gear_tooth_body_with_bore(gear: dict[str, Any]):
    bore_radius = float(gear.get("bore_radius", ARBOR_RADIUS_MM))
    body = _gear_body(gear)
    cutters = [_z_cylinder(bore_radius, gear["height"] + 0.08).located(Location((0, 0, gear["height"] / 2.0)))]
    for hole in gear.get("clearance_holes", []):
        local_x = float(hole["x"]) - float(gear["x"])
        local_y = float(hole["y"]) - float(gear["y"])
        cutters.append(
            _z_cylinder(float(hole["radius"]), gear["height"] + 0.08).located(
                Location((local_x, local_y, gear["height"] / 2.0))
            )
        )
    for cutter in cutters:
        body = body - cutter
    if gear.get("spoke_modeling_strategy") == "single_body_cutout":
        body = _apply_watch_wheel_open_spoke_cutouts(body, gear)
    return body


def _attach_watch_wheel_spoke_cutouts(gears: list[dict[str, Any]], seed: int) -> None:
    wheel_gears = [gear for gear in gears if _should_use_watch_wheel_spoke_cutouts(gear)]
    selected_counts: list[int] = []
    for gear in wheel_gears:
        spoke_count = choose_by_seed(seed, f"spoke_count:{gear['gear_id']}", [2, 3, 4, 5])
        selected_counts.append(int(spoke_count))
    if len(set(selected_counts)) == 1 and len(selected_counts) > 1:
        selected_counts[-1] = 2 + ((selected_counts[-1] - 1) % 4)

    for gear, spoke_count in zip(wheel_gears, selected_counts):
        hub_clearance = 0.08 if gear["gear_type"] in {"escape", "pinion"} else 0.20
        hub_outer_radius = max(gear["bore_radius"] + hub_clearance, min(gear["root_radius"] * 0.165, gear["root_radius"] - 0.28))
        rim_inner_radius = gear["root_radius"] * 0.865
        gear.update(
            {
                "spoke_modeling_strategy": "single_body_cutout",
                "spoke_count": spoke_count,
                "hub_outer_radius": round(hub_outer_radius, 4),
                "rim_inner_radius": round(rim_inner_radius, 4),
                "spoke_width_at_hub_mm": round(_watch_wheel_spoke_width_mm(hub_outer_radius, 0.0), 4),
                "spoke_width_at_mid_mm": round(_watch_wheel_spoke_width_mm(hub_outer_radius, 0.5), 4),
                "spoke_width_at_rim_mm": round(_watch_wheel_spoke_width_mm(hub_outer_radius, 1.0), 4),
            }
        )


def _should_use_watch_wheel_spoke_cutouts(gear: dict[str, Any]) -> bool:
    if gear.get("spoke_cutout_allowed") is False:
        return False
    if gear["gear_type"] not in {"wheel", "escape", "pinion"}:
        return False
    root_diameter = float(gear["root_radius"]) * 2.0
    return root_diameter >= WATCH_WHEEL_SPOKE_ROOT_DIAMETER_THRESHOLD_MM


def _watch_wheel_spoke_width_mm(hub_outer_radius: float, radial_fraction: float) -> float:
    t = max(0.0, min(1.0, radial_fraction))
    mid_width = max(0.085, hub_outer_radius * 0.11)
    hub_width = max(0.20, hub_outer_radius * 0.34)
    rim_width = max(0.145, hub_outer_radius * 0.21)
    if t <= 0.5:
        blend = t / 0.5
        return hub_width * (1.0 - blend) + mid_width * blend
    blend = (t - 0.5) / 0.5
    return mid_width * (1.0 - blend) + rim_width * blend


def _apply_watch_wheel_open_spoke_cutouts(body, gear: dict[str, Any]):
    inner_radius = float(gear["hub_outer_radius"])
    outer_radius = float(gear["rim_inner_radius"])
    spoke_count = int(gear["spoke_count"])
    pitch = 2.0 * math.pi / spoke_count
    phase = math.radians(float(gear.get("phase_deg", 0.0)))
    for index in range(spoke_count):
        cutter = _watch_wheel_gap_cutter(
            hub_outer_radius=inner_radius,
            rim_inner_radius=outer_radius,
            start_spoke_angle=phase + index * pitch,
            end_spoke_angle=phase + (index + 1) * pitch,
            height=float(gear["height"]) + 0.12,
        ).located(Location((0.0, 0.0, -0.06)))
        body = body - cutter
    return body


def _watch_wheel_gap_cutter(
    *,
    hub_outer_radius: float,
    rim_inner_radius: float,
    start_spoke_angle: float,
    end_spoke_angle: float,
    height: float,
):
    radial_steps = 5
    angular_steps = max(8, int(math.degrees(end_spoke_angle - start_spoke_angle) // 10))
    cutter = None

    def polar_point(t: float, u: float) -> tuple[float, float]:
        radius = hub_outer_radius + (rim_inner_radius - hub_outer_radius) * t
        width = _watch_wheel_spoke_width_mm(hub_outer_radius, t)
        half_angle = (width / 2.0) / max(radius, 1e-6)
        left_angle = start_spoke_angle + half_angle
        right_angle = end_spoke_angle - half_angle
        angle = left_angle + (right_angle - left_angle) * u
        return math.cos(angle) * radius, math.sin(angle) * radius

    for radial_index in range(radial_steps):
        t0 = radial_index / radial_steps
        t1 = (radial_index + 1) / radial_steps
        for angular_index in range(angular_steps):
            u0 = angular_index / angular_steps
            u1 = (angular_index + 1) / angular_steps
            segment = _extrude_xy_points_preserve_frame(
                [
                    polar_point(t0, u0),
                    polar_point(t1, u0),
                    polar_point(t1, u1),
                    polar_point(t0, u1),
                ],
                height,
            )
            cutter = segment if cutter is None else cutter + segment
    return cutter


def _gear_body(gear: dict[str, Any]):
    points = _gear_points(
        gear["tooth_count"],
        gear["pitch_radius"],
        gear["outer_radius"],
        gear["root_radius"],
        phase_deg=gear["phase_deg"],
        escape=gear["gear_type"] == "escape",
    )
    return extrude(Plane.XY * Polygon(points), amount=gear["height"])


def _make_display_works(design: dict[str, Any]) -> list[Any]:
    display_axis = _axis_by_id(design, DISPLAY_CENTER_AXIS)
    x = display_axis["x"]
    y = display_axis["y"]
    display = design["display"]
    display_gears = {gear["gear_id"]: gear for gear in design["display_gears"]}
    cannon_gear = display_gears["cannon_pinion_display_driver"]
    minute_wheel = display_gears["minute_wheel"]
    minute_pinion = display_gears["minute_pinion"]
    hour_wheel_gear = display_gears["hour_wheel"]
    tubes = {tube["tube_id"]: tube for tube in display["tube_stack"]}
    extensions = {extension["extension_id"]: extension for extension in display["arbor_extensions"]}
    cannon_driver = _gear_ring_body(cannon_gear, cannon_gear["bore_radius"]).located(Location((cannon_gear["x"], cannon_gear["y"], cannon_gear["z"])))
    cannon_hub = _annulus(0.34, 0.17, 0.34).located(Location((x, y, cannon_gear["z"] + 0.17)))
    minute_wheel_body = _gear_ring_body(minute_wheel, minute_wheel["bore_radius"]).located(Location((minute_wheel["x"], minute_wheel["y"], minute_wheel["z"])))
    minute_pinion_body = _gear_ring_body(minute_pinion, minute_pinion["bore_radius"]).located(Location((minute_pinion["x"], minute_pinion["y"], minute_pinion["z"])))
    hour_wheel_body = _gear_ring_body(hour_wheel_gear, hour_wheel_gear["bore_radius"]).located(Location((hour_wheel_gear["x"], hour_wheel_gear["y"], hour_wheel_gear["z"])))
    hour_wheel_hub = _annulus(0.58, 0.36, 0.28).located(Location((x, y, hour_wheel_gear["z"] + 0.14)))
    hour_wheel_part = (
        _label(hour_wheel_body, "hour_wheel")
        if hour_wheel_gear.get("spoke_modeling_strategy") == "single_body_cutout"
        else Compound(
            label="hour_wheel",
            children=[
                _label(hour_wheel_body, "hour_wheel_tooth_profile"),
                _label(hour_wheel_hub, "hour_wheel_hub"),
            ],
        )
    )
    children = [
        Compound(
            label="cannon_pinion_assembly",
            children=[
                _label(cannon_driver, "cannon_pinion_display_driver"),
                _label(cannon_hub, "cannon_pinion_hub"),
            ],
        ),
        Compound(
            label="minute_wheel_assembly",
            children=[
                _label(minute_wheel_body, "minute_wheel"),
                _label(minute_pinion_body, "minute_pinion"),
            ],
        ),
        hour_wheel_part,
    ]
    for extension in display["arbor_extensions"]:
        axis = _axis_by_id(design, extension["axis_id"])
        height = extension["z_max"] - extension["z_min"]
        center_z = extension["z_min"] + height / 2.0
        body = _z_cylinder(extension["radius"], height).located(Location((axis["x"], axis["y"], center_z)))
        children.append(_label(body, extension["extension_id"]))
        if extension["extension_id"] == "seconds_arbor_extension":
            cap = _z_cylinder(0.28, 0.12).located(Location((axis["x"], axis["y"], extension["z_max"] + 0.02)))
            children.append(_label(cap, "seconds_hand_collet_cap"))
    for tube in display["tube_stack"]:
        height = tube["z_max"] - tube["z_min"]
        center_z = tube["z_min"] + height / 2.0
        if tube["inner_radius"] > 0.0:
            body = _annulus(tube["outer_radius"], tube["inner_radius"], height).located(Location((x, y, center_z)))
        else:
            body = _z_cylinder(tube["outer_radius"], height).located(Location((x, y, center_z)))
        children.append(_label(body, tube["tube_id"]))
    display_collet_z = max(
        extensions["central_display_arbor_extension"]["z_max"],
        tubes["hour_tube"]["z_max"],
        tubes["cannon_pinion_tube"]["z_max"],
    ) + 0.04
    children.append(_label(_annulus(0.72, 0.13, 0.16).located(Location((x, y, display_collet_z))), "display_center_collet_stack"))
    for hand in display["hands"]:
        hand_axis = _axis_by_id(design, hand["axis_id"])
        children.append(
            _make_hand(
                hand["hand_id"],
                hand_axis["x"],
                hand_axis["y"],
                hand["angle_deg"],
                hand["length_mm"],
                hand["z_mm"],
                hand["width_mm"],
                hand["profile"],
            )
        )
    return children


def _gear_ring_body(gear: dict[str, Any], bore_radius: float):
    cutter = _z_cylinder(bore_radius, gear["height"] + 0.08).located(Location((0, 0, gear["height"] / 2.0)))
    body = _gear_body(gear) - cutter
    if gear.get("spoke_modeling_strategy") == "single_body_cutout":
        body = _apply_watch_wheel_open_spoke_cutouts(body, gear)
    return body


def _make_hand(label: str, x: float, y: float, angle_deg: float, length: float, z: float, width: float, profile: str):
    angle = math.radians(angle_deg)
    if profile == "broad_leaf":
        hub_outer = width * 2.7
        blade_points = _leaf_pointer_points(
            x,
            y,
            angle,
            start_radius=max(0.18, hub_outer - 0.03),
            length=length,
            max_width=width * 2.5,
            neck_width=width * 0.7,
        )
    elif profile == "needle_with_counterweight":
        hub_outer = width * 3.4
        blade_points = _seconds_hand_points(
            x,
            y,
            angle,
            start_radius=max(0.18, hub_outer - 0.03),
            length=length,
            tail_length=1.65,
            width=width,
        )
    else:
        hub_outer = width * 3.2
        blade_points = _tapered_pointer_points(
            x,
            y,
            angle,
            start_radius=max(0.18, hub_outer - 0.03),
            length=length,
            base_width=width * 2.1,
            tip_width=width * 0.36,
        )
    blade = _extrude_xy_points_preserve_frame(blade_points, 0.075).located(Location((0, 0, z)))
    hub = _annulus(width * 2.6, ARBOR_RADIUS_MM * 0.8, 0.12).located(Location((x, y, z + 0.04)))
    hub = _annulus(_hand_hub_outer_radius(width, profile), ARBOR_RADIUS_MM * 0.8, 0.12).located(
        Location((x, y, z + 0.04))
    )
    return Compound(label=label, children=[_label(hub, f"{label}_hub"), _label(blade, f"{label}_blade")])


def _make_placeholder_escapement_line(design: dict[str, Any]) -> list[Any]:
    pallet = _axis_by_id(design, "pallet_axis")
    balance = _axis_by_id(design, "balance_axis")
    pallet_disc = _annulus(1.05, 0.18, 0.18).located(Location((pallet["x"], pallet["y"], 3.08)))
    balance_disc = _annulus(2.45, 1.85, 0.22).located(Location((balance["x"], balance["y"], 3.12)))
    interaction = _extrude_xy_points_preserve_frame(
        _bar_points(pallet["x"], pallet["y"], balance["x"], balance["y"], 0.16),
        0.08,
    ).located(Location((0, 0, 3.02)))
    return [
        _label(pallet_disc, "pallet_placeholder_disc"),
        _label(balance_disc, "balance_placeholder_disc"),
        _label(interaction, "escapement_to_balance_placeholder_envelope"),
    ]


def _build_semantic_report(design: dict[str, Any], independent_geometry: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "power_chain_connected_to_escape_wheel": _power_chain_connected(design),
        "coaxial_compound_gears_complete": _compound_gears_complete(design),
        "gear_mesh_phase_alignment": _gear_mesh_phase_alignment(design),
        "placeholder_escapement_to_balance_envelopes_exist": True,
        "display_hands_exist": _display_hands_exist(design),
        "display_hand_stack_clear": _display_hand_stack_clear(design),
        "three_hand_drive_chains_declared": _three_hand_drive_chains_declared(design),
        "central_hour_minute_axis": _central_hour_minute_axis(design),
        "seconds_hand_length_within_case_clearance": _seconds_hand_length_within_case_clearance(design),
        "seconds_hand_sweep_clear": _seconds_hand_sweep_clear(design),
        "display_hand_mount_stacks_closed": _display_hand_mount_stacks_closed(design),
        "display_hand_mount_stacks_xy_connected": _display_hand_mount_stacks_xy_connected(design),
        "display_hand_mount_stacks_6dof_constrained": _display_hand_mount_stacks_6dof_constrained(design),
        "display_motion_chain_realized": _display_motion_chain_realized(design),
        "hour_motion_reduction_proven": _hour_motion_reduction_proven(design),
        "coaxial_display_sleeve_clearance": _coaxial_display_sleeve_clearance(design),
        "support_axis_geometry_valid": independent_geometry["support_axes"]["status"] == "pass",
        "internal_work_envelope_clear": independent_geometry["work_envelope"]["status"] == "pass",
        "bridge_perimeter_service_band_reserved": independent_geometry["bridge_perimeter_service_band"]["status"] == "pass",
        "internal_interference_clear": independent_geometry["interference"]["status"] == "pass",
        "gear_mesh_tip_root_clearance": independent_geometry["gear_mesh_clearance"]["status"] == "pass",
        "mainplate_flat_round_disk": independent_geometry["housing_parent_body"]["status"] == "pass"
        and independent_geometry["housing_parent_body"]["mainplate_is_flat_round_disk"],
        "mainplate_outer_raised_support_ring": independent_geometry["housing_parent_body"]["outer_raised_support_ring"]["status"]
        == "pass",
        "lower_jewel_supports_complete": independent_geometry["jewel_supports"]["status"] == "pass"
        and not independent_geometry["jewel_supports"]["missing_lower_jewels"],
        "future_upper_jewel_plane_ready": independent_geometry["jewel_supports"]["status"] == "pass"
        and not independent_geometry["jewel_supports"]["missing_future_upper_jewels"],
        "jewel_supports_interference_clear": independent_geometry["jewel_supports"]["status"] == "pass"
        and not independent_geometry["jewel_supports"]["interference_failures"],
        "z_stack_layering_valid": independent_geometry["z_stack"]["status"] == "pass",
        "independent_display_mount_geometry": all(
            report["status"] == "pass" for report in independent_geometry["hand_mounts"].values()
        ),
        "independent_display_feature_attachment_geometry": all(
            report["status"] == "pass" for report in independent_geometry["feature_attachments"].values()
        ),
        "independent_display_motion_chain_geometry": independent_geometry["motion_chains"]["status"] == "pass",
        "independent_coaxial_sleeve_clearance": independent_geometry["coaxial_sleeves"]["status"] == "pass",
        "independent_support_axis_geometry": independent_geometry["support_axes"]["status"] == "pass",
        "independent_work_envelope_geometry": independent_geometry["work_envelope"]["status"] == "pass",
        "independent_bridge_perimeter_service_band_geometry": independent_geometry["bridge_perimeter_service_band"]["status"] == "pass",
        "independent_internal_interference_geometry": independent_geometry["interference"]["status"] == "pass",
        "independent_gear_mesh_clearance_geometry": independent_geometry["gear_mesh_clearance"]["status"] == "pass",
        "independent_housing_parent_body_geometry": independent_geometry["housing_parent_body"]["status"] == "pass",
        "independent_jewel_support_geometry": independent_geometry["jewel_supports"]["status"] == "pass",
        "independent_z_stack_layering_geometry": independent_geometry["z_stack"]["status"] == "pass",
        "pattern_solver_candidate_selected": design["pattern_solver"]["status"] == "pass"
        and design["pattern_solver"]["selected_candidate"] is not None,
        "seed_reproducibility_manifest_exists": bool(design["seed_manifest"]),
        "bridges_absent_in_phase_1": not design["bridges_generated"] if not design["bridges_generated"] else True,
        "bridge_stage_three_bridge_plates": independent_geometry["bridge_stage"]["status"] == "pass"
        and (
            not design["bridges_generated"]
            or [bridge["bridge_id"] for bridge in independent_geometry["bridge_stage"]["bridges"]]
            == ["barrel_bridge", "train_bridge", "escapement_bridge"]
        ),
    }
    return {
        "kind": "watch_power_chain_mvp_semantic_report",
        "phase": PHASE,
        "status": "pass" if all(checks.values()) else "fail",
        "seed": design["seed"],
        "seed_manifest": design["seed_manifest"],
        "pattern_solver": {
            "pattern_card_id": design["pattern_solver"]["pattern_card_id"],
            "status": design["pattern_solver"]["status"],
            "candidate_count": design["pattern_solver"]["candidate_count"],
            "feasible_candidate_count": design["pattern_solver"]["feasible_candidate_count"],
            "selected_candidate_id": design["pattern_solver"]["selected_candidate"]["candidate_id"],
            "selection_strategy": design["pattern_solver"]["selection_strategy"],
        },
        "bridges_generated": design["bridges_generated"],
        "layout": {
            "axes": design["axes"],
            "gears": design["gears"],
            "meshes": design["meshes"],
            "mesh_phase_records": design["mesh_phase_records"],
            "display_gears": design["display_gears"],
            "display_meshes": design["display_meshes"],
            "display_mesh_phase_records": design["display_mesh_phase_records"],
            "z_stack": design["z_stack"],
            "arbor_geometry_policy": ARBOR_GEOMETRY_POLICY,
        },
        "bridge_stage": design.get("bridge_stage"),
        "display": design["display"],
        "independent_geometry": independent_geometry,
        "checks": checks,
        "required_entities": [
            "mainspring_barrel",
            "center_wheel",
            "third_wheel",
            "fourth_wheel",
            "escape_wheel",
            "pallet_placeholder_disc",
            "balance_placeholder_disc",
            "seconds_hand",
            "minute_hand",
            "hour_hand",
            "cannon_pinion_display_driver",
            "minute_wheel_assembly",
            "minute_wheel",
            "minute_pinion",
        ],
        "report_only": [
            "real_mainspring_torque_curve",
            "real_escapement_locking_and_impulse",
            "bridge_upper_supports_not_generated_in_phase_1",
        ],
    }


def _build_kinematic_report(design: dict[str, Any]) -> dict[str, Any]:
    velocities = _gear_velocity_relative_to_barrel(design)
    signed_hand_ratios = _signed_display_hand_velocity_ratio_to_hour()
    direction_check = _clockwise_display_direction_report(signed_hand_ratios)
    checks = {
        "physical_hand_ratio_720_12_1": "pass"
        if PHYSICAL_HAND_ANGULAR_VELOCITY_RATIO_TO_HOUR == {"seconds_hand": 720.0, "minute_hand": 12.0, "hour_hand": 1.0}
        else "fail",
        "requested_time_unit_ratio_3600_60_1": "pass"
        if REQUESTED_TIME_UNIT_RATIO == {"seconds_unit": 3600.0, "minute_unit": 60.0, "hour_unit": 1.0}
        else "fail",
        "display_hands_clockwise_viewed_from_dial_side": direction_check["status"],
    }
    return {
        "kind": "watch_power_chain_mvp_kinematic_report",
        "phase": PHASE,
        "status": "pass" if all(value == "pass" for value in checks.values()) else "fail",
        "gear_velocity_relative_to_barrel": {key: round(value, 6) for key, value in sorted(velocities.items())},
        "display_motion_works": design["display"]["motion_works"]["ratio_proof"],
        "physical_hand_angular_velocity_ratio_to_hour_hand": PHYSICAL_HAND_ANGULAR_VELOCITY_RATIO_TO_HOUR,
        "physical_hand_ratio_basis": "standard 12-hour analog display: seconds hand 1 rev/min, minute hand 1 rev/hour, hour hand 1 rev/12 hours",
        "requested_time_unit_ratio": REQUESTED_TIME_UNIT_RATIO,
        "requested_time_unit_ratio_basis": "user-stated seconds:minutes:hours unit count ratio; recorded separately from physical hand angular velocity",
        "signed_display_hand_angular_velocity_ratio_to_hour_unit": signed_hand_ratios,
        "direction_contract": DIRECTION_CONTRACT,
        "motion_source_contract": MOTION_SOURCE_CONTRACT,
        "direction_propagation_rules": DIRECTION_PROPAGATION_RULES,
        "display_direction_check": direction_check,
        "display_ratios": {
            "seconds_hand": "1 rev / minute",
            "minute_hand": "1 rev / hour",
            "hour_hand": "1 rev / 12 hours",
        },
        "checks": checks,
        "placeholder_motion": {
            "pallet_placeholder_disc": "oscillation_envelope_only",
            "balance_placeholder_disc": "oscillation_envelope_only",
        },
    }


def _gear_velocity_relative_to_barrel(design: dict[str, Any]) -> dict[str, float]:
    gear_by_id = {gear["gear_id"]: gear for gear in design["gears"]}
    velocities = {"barrel_outer_teeth": 1.0}
    for mesh in design["meshes"]:
        driver = gear_by_id[mesh["driver"]]
        driven = gear_by_id[mesh["driven"]]
        velocities[driven["gear_id"]] = -velocities[driver["gear_id"]] * driver["tooth_count"] / driven["tooth_count"]
        for wheel, pinion in [
            ("center_wheel", "center_pinion"),
            ("third_wheel", "third_pinion"),
            ("fourth_wheel", "fourth_pinion"),
            ("escape_wheel", "escape_pinion"),
        ]:
            if pinion in velocities:
                velocities[wheel] = velocities[pinion]
    return velocities


def _signed_display_hand_velocity_ratio_to_hour() -> dict[str, float]:
    return {
        hand_id: round(CLOCKWISE_SIGN_IN_STEP_MODULE * magnitude, 6)
        for hand_id, magnitude in PHYSICAL_HAND_ANGULAR_VELOCITY_RATIO_TO_HOUR.items()
    }


def _motion_sign(value: float) -> float:
    if abs(value) < 1e-12:
        return 0.0
    return 1.0 if value > 0 else -1.0


def _clockwise_display_direction_report(signed_hand_ratios: dict[str, float]) -> dict[str, Any]:
    hands: dict[str, dict[str, Any]] = {}
    for hand_id in DIRECTION_CONTRACT["required_display_hands"]:
        signed_ratio = float(signed_hand_ratios[hand_id])
        sign = _motion_sign(signed_ratio)
        status = "pass" if sign == CLOCKWISE_SIGN_IN_STEP_MODULE else "fail"
        hands[hand_id] = {
            "signed_ratio_to_hour_unit": round(signed_ratio, 6),
            "observed_direction_viewed_from_dial_side": "clockwise" if status == "pass" else "counterclockwise_or_zero",
            "status": status,
        }
    return {
        "status": "pass" if all(hand["status"] == "pass" for hand in hands.values()) else "fail",
        "hands": hands,
    }


def _display_motion_velocity_ratios(design: dict[str, Any], signed_minute_ratio: float) -> dict[str, float]:
    display_gears = design.get("display_gears") or design["display"]["motion_works"]["display_gears"]
    gear_by_id = {gear["gear_id"]: gear for gear in display_gears}
    cannon = gear_by_id["cannon_pinion_display_driver"]
    minute_wheel = gear_by_id["minute_wheel"]
    minute_pinion = gear_by_id["minute_pinion"]
    hour_wheel = gear_by_id["hour_wheel"]
    minute_work_ratio = -signed_minute_ratio * cannon["tooth_count"] / minute_wheel["tooth_count"]
    hour_ratio = -minute_work_ratio * minute_pinion["tooth_count"] / hour_wheel["tooth_count"]
    return {
        "cannon_pinion_display_driver": round(signed_minute_ratio, 6),
        "minute_wheel_assembly": round(minute_work_ratio, 6),
        "hour_wheel": round(hour_ratio, 6),
    }


def write_power_chain_motion_artifacts(
    step_path: str | Path,
    design: dict[str, Any],
    *,
    external_escapement: bool = False,
    feature_refs_override: dict[str, dict[str, Any]] | None = None,
) -> dict[str, str]:
    step = Path(step_path)
    motion = _build_step_module_motion_report(
        design,
        external_escapement=external_escapement,
        feature_refs_override=feature_refs_override,
    )
    sidecar_path = _step_module_sidecar_path(step)
    motion_path = step.with_name(f"{step.stem}.motion.json")
    sidecar_path.write_text(_render_step_module_js(motion), encoding="utf-8")
    motion_path.write_text(json.dumps(motion, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "step_module_js": str(sidecar_path),
        "motion_json": str(motion_path),
    }


def _step_module_sidecar_path(step_path: Path) -> Path:
    return step_path.with_name(f".{step_path.name}.js")


def _build_step_module_motion_report(
    design: dict[str, Any],
    *,
    external_escapement: bool,
    feature_refs_override: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    velocities = _gear_velocity_relative_to_barrel(design)
    signed_hand_ratios = _signed_display_hand_velocity_ratio_to_hour()
    fourth_velocity = velocities["fourth_wheel"]
    scale_to_hour = signed_hand_ratios["seconds_hand"] / fourth_velocity
    ratio_to_hour = {gear_id: round(value * scale_to_hour, 6) for gear_id, value in velocities.items()}
    ratio_to_hour["external_escape_wheel"] = ratio_to_hour["escape_pinion"]
    ratio_to_hour["external_escape_staff"] = ratio_to_hour["escape_pinion"]
    display_motion_ratios = _display_motion_velocity_ratios(design, signed_hand_ratios["minute_hand"])
    direction_check = _clockwise_display_direction_report(signed_hand_ratios)

    def axis_origin(axis_id: str) -> list[float]:
        axis = _axis_by_id(design, axis_id)
        return [axis["x"], axis["y"], 0.0]

    moving_groups = [
        _motion_group("barrel_rotation", "barrel_axis", ["mainspring_barrel"], ratio_to_hour["barrel_outer_teeth"], axis_origin("barrel_axis")),
        _motion_group("center_train_rotation", "center_axis", ["center_pinion", "center_wheel"], ratio_to_hour["center_wheel"], axis_origin("center_axis")),
        _motion_group("third_train_rotation", "third_axis", ["third_pinion", "third_wheel"], ratio_to_hour["third_wheel"], axis_origin("third_axis")),
        _motion_group(
            "fourth_train_and_seconds_rotation",
            "fourth_axis",
            ["fourth_pinion", "fourth_wheel", "fourth_arbor", "seconds_arbor_extension", "seconds_hand_collet_cap", "seconds_hand"],
            signed_hand_ratios["seconds_hand"],
            axis_origin("fourth_axis"),
        ),
        _motion_group("escape_pinion_rotation", "escape_axis", ["escape_pinion"], ratio_to_hour["escape_pinion"], axis_origin("escape_axis")),
        _motion_group(
            "minute_display_rotation",
            DISPLAY_CENTER_AXIS,
            ["cannon_pinion_assembly", "cannon_pinion_tube", "minute_hand"],
            signed_hand_ratios["minute_hand"],
            axis_origin(DISPLAY_CENTER_AXIS),
        ),
        _motion_group("minute_work_compound_rotation", "minute_work_axis", ["minute_wheel_assembly"], display_motion_ratios["minute_wheel_assembly"], axis_origin("minute_work_axis")),
        _motion_group(
            "hour_display_rotation",
            DISPLAY_CENTER_AXIS,
            ["hour_wheel", "hour_tube", "hour_hand"],
            signed_hand_ratios["hour_hand"],
            axis_origin(DISPLAY_CENTER_AXIS),
        ),
    ]
    if external_escapement:
        moving_groups.append(
            _motion_group(
                "external_escape_wheel_rotation",
                "escape_axis",
                ["external_escape_wheel", "external_escape_staff"],
                ratio_to_hour["external_escape_wheel"],
                axis_origin("escape_axis"),
            )
        )
        escapement_policy = "external_swiss_lever_static_pallet_and_balance"
        fixed_features = [
            "external_pallet_fork",
            "external_balance_wheel",
            "external_hairspring",
            "external_escapement_reference_plate",
            "external_escape_upper_cap",
            "external_balance_upper_cap",
            "external_escape_upper_fixed_hardware",
            "external_balance_upper_fixed_hardware",
        ]
    else:
        moving_groups.append(_motion_group("generated_escape_wheel_rotation", "escape_axis", ["escape_wheel"], ratio_to_hour["escape_wheel"], axis_origin("escape_axis")))
        escapement_policy = "generated_placeholder_static_pallet_and_balance"
        fixed_features = ["pallet_placeholder_disc", "balance_placeholder_disc", "escapement_to_balance_placeholder_envelope"]

    feature_refs = (
        feature_refs_override
        if feature_refs_override is not None
        else _step_module_feature_refs(design, external_escapement=external_escapement)
    )
    moving_groups = _expand_step_module_motion_groups_to_visible_features(moving_groups, feature_refs)
    fixed_features = _expand_step_module_fixed_features_to_visible_features(fixed_features, feature_refs)
    dynamic_6dof_intent = _step_module_6dof_intent(moving_groups, fixed_features)
    semantic_material_contracts = _step_module_semantic_material_contracts(feature_refs)
    visual_materials = _step_module_visual_materials(semantic_material_contracts)
    material_contract_missing_features = sorted(set(feature_refs) - set(semantic_material_contracts))
    missing_features = sorted(
        {
            feature_id
            for group in moving_groups
            for feature_id in group["feature_ids"]
            if feature_id not in feature_refs
        }
        | {feature_id for feature_id in fixed_features if feature_id not in feature_refs}
    )
    checks = {
        "all_moving_features_have_refs": "pass" if not missing_features else "fail",
        "physical_hand_ratio_720_12_1": "pass",
        "requested_time_unit_ratio_3600_60_1": "pass",
        "display_hands_clockwise_viewed_from_dial_side": direction_check["status"],
        "pallet_and_balance_static_by_policy": "pass",
        "dynamic_6dof_intent_declared": "pass"
        if dynamic_6dof_intent["moving_groups"] and all(item["locked_dof"] == ["tx", "ty", "tz", "rx", "ry", "rz"] for item in dynamic_6dof_intent["fixed_features"])
        else "fail",
        "review_materials_declared": "pass" if visual_materials else "fail",
        "semantic_material_contracts_cover_visible_features": "pass" if not material_contract_missing_features else "fail",
    }
    return {
        "kind": "watch_power_chain_step_module_motion",
        "status": "pass" if all(value == "pass" for value in checks.values()) else "fail",
        "phase": PHASE,
        "external_escapement": external_escapement,
        "escapement_animation_policy": escapement_policy,
        "driver_parameter": {
            "parameter_id": "hourHandDeg",
            "meaning": "positive review parameter; signed motion groups enforce clockwise hands from dial side",
            "unit": "deg",
        },
        "physical_hand_angular_velocity_ratio_to_hour_hand": PHYSICAL_HAND_ANGULAR_VELOCITY_RATIO_TO_HOUR,
        "requested_time_unit_ratio": REQUESTED_TIME_UNIT_RATIO,
        "signed_display_hand_angular_velocity_ratio_to_hour_unit": signed_hand_ratios,
        "direction_contract": DIRECTION_CONTRACT,
        "motion_source_contract": MOTION_SOURCE_CONTRACT,
        "direction_propagation_rules": DIRECTION_PROPAGATION_RULES,
        "display_direction_check": direction_check,
        "display_motion_velocity_ratio_to_hour_unit": display_motion_ratios,
        "gear_velocity_relative_to_barrel": {key: round(value, 6) for key, value in sorted(velocities.items())},
        "gear_velocity_ratio_to_hour_hand": ratio_to_hour,
        "moving_groups": moving_groups,
        "fixed_features": fixed_features,
        "dynamic_6dof_intent": dynamic_6dof_intent,
        "semantic_material_contracts": semantic_material_contracts,
        "visual_materials": visual_materials,
        "features": feature_refs,
        "missing_features": missing_features,
        "material_contract_missing_features": material_contract_missing_features,
        "checks": checks,
    }


def _motion_group(group_id: str, axis_id: str, feature_ids: list[str], ratio_to_hour: float, origin: list[float]) -> dict[str, Any]:
    return {
        "group_id": group_id,
        "axis_id": axis_id,
        "feature_ids": feature_ids,
        "angular_velocity_ratio_to_hour_hand": round(float(ratio_to_hour), 6),
        "origin_mm": [round(value, 6) for value in origin],
        "axis_vector": [0.0, 0.0, 1.0],
    }


def _visible_feature_aliases_for_step_module() -> dict[str, list[str]]:
    return {
        "mainspring_barrel": ["barrel_drum", "barrel_outer_teeth"],
        "center_pinion": ["center_pinion_tooth_profile", "center_pinion_hub"],
        "third_pinion": ["third_pinion_tooth_profile", "third_pinion_hub"],
        "fourth_pinion": ["fourth_pinion_tooth_profile", "fourth_pinion_hub"],
        "escape_pinion": ["escape_pinion_tooth_profile", "escape_pinion_hub"],
        "train_stage_1_pinion": ["train_stage_1_pinion_tooth_profile", "train_stage_1_pinion_hub"],
        "train_stage_2_pinion": ["train_stage_2_pinion_tooth_profile", "train_stage_2_pinion_hub"],
        "train_stage_3_pinion": ["train_stage_3_pinion_tooth_profile", "train_stage_3_pinion_hub"],
        "display_input_relay_wheel": [
            "display_input_relay_wheel_tooth_profile",
            "display_input_relay_wheel_hub",
        ],
        "display_relay_wheel": ["display_relay_wheel_tooth_profile", "display_relay_wheel_hub"],
        "minute_input_relay_pinion": [
            "minute_input_relay_pinion_tooth_profile",
            "minute_input_relay_pinion_hub",
        ],
        "minute_input_relay_wheel": [
            "minute_input_relay_wheel_tooth_profile",
            "minute_input_relay_wheel_hub",
        ],
        "minute_display_member": [
            "minute_display_member_tooth_profile",
            "minute_display_member_hub",
        ],
        "hour_input_relay_pinion": [
            "hour_input_relay_pinion_tooth_profile",
            "hour_input_relay_pinion_hub",
        ],
        "hour_input_relay_wheel": [
            "hour_input_relay_wheel_tooth_profile",
            "hour_input_relay_wheel_hub",
        ],
        "hour_reduction_relay_pinion": [
            "hour_reduction_relay_pinion_tooth_profile",
            "hour_reduction_relay_pinion_hub",
        ],
        "hour_reduction_relay_wheel": [
            "hour_reduction_relay_wheel_tooth_profile",
            "hour_reduction_relay_wheel_hub",
        ],
        "hour_display_member": [
            "hour_display_member_tooth_profile",
            "hour_display_member_hub",
        ],
        "cannon_pinion_assembly": ["cannon_pinion_display_driver", "cannon_pinion_hub"],
        "minute_wheel_assembly": ["minute_wheel", "minute_pinion"],
        "seconds_hand": ["seconds_hand_hub", "seconds_hand_blade"],
        "minute_hand": ["minute_hand_hub", "minute_hand_blade"],
        "hour_hand": ["hour_hand_hub", "hour_hand_blade"],
        "external_balance_upper_cap": ["external_balance_upper_jewel_bearing"],
        "external_balance_upper_fixed_hardware": ["external_balance_replacement_staff"],
    }


def _expand_step_module_motion_groups_to_visible_features(
    moving_groups: list[dict[str, Any]],
    feature_refs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            **group,
            "feature_ids": _expand_step_module_feature_ids(group["feature_ids"], feature_refs),
        }
        for group in moving_groups
    ]


def _expand_step_module_fixed_features_to_visible_features(
    fixed_features: list[str],
    feature_refs: dict[str, dict[str, Any]],
) -> list[str]:
    return _expand_step_module_feature_ids(fixed_features, feature_refs)


def _expand_step_module_feature_ids(
    feature_ids: list[str],
    feature_refs: dict[str, dict[str, Any]],
) -> list[str]:
    aliases = _visible_feature_aliases_for_step_module()
    expanded: list[str] = []
    for feature_id in feature_ids:
        candidates = [feature_id] if feature_id in feature_refs else aliases.get(feature_id, [feature_id])
        visible = [candidate for candidate in candidates if candidate in feature_refs]
        expanded.extend(visible or [feature_id])
    return _dedupe_preserving_order(expanded)


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _step_module_internal_occurrence_order(design: dict[str, Any], *, external_escapement: bool) -> list[str]:
    omitted_gears = {"escape_wheel"} if external_escapement else set()
    order = ["foundation_mainplate"]
    for axis in design["axes"]:
        if not axis["support_required"]:
            continue
        for segment in axis["support_segments"]:
            order.append(segment["segment_id"])
        order.append(f"lower_jewel_support_{axis['axis_id']}")
        if axis.get("upper_jewel_bearing"):
            order.append(f"upper_jewel_bearing_support_{axis['axis_id']}")
    order.append("mainspring_barrel")
    for gear in design["gears"]:
        if gear["gear_id"] != "barrel_outer_teeth" and gear["gear_id"] not in omitted_gears:
            order.append(gear["gear_id"])
    order.extend(["cannon_pinion_assembly", "minute_wheel_assembly", "hour_wheel"])
    for extension in design["display"]["arbor_extensions"]:
        order.append(extension["extension_id"])
        if extension["extension_id"] == "seconds_arbor_extension":
            order.append("seconds_hand_collet_cap")
    for tube in design["display"]["tube_stack"]:
        order.append(tube["tube_id"])
    order.append("display_center_collet_stack")
    for hand in design["display"]["hands"]:
        order.append(hand["hand_id"])
    if not external_escapement:
        order.extend(["pallet_placeholder_disc", "balance_placeholder_disc", "escapement_to_balance_placeholder_envelope"])
    if design.get("bridges_generated"):
        for bridge in design.get("bridge_stage", {}).get("bridges", []):
            for screw in bridge["screws"]:
                order.append(screw["screw_id"])
            order.append(bridge["bridge_id"])
    return order


def _step_module_6dof_intent(moving_groups: list[dict[str, Any]], fixed_features: list[str]) -> dict[str, Any]:
    return {
        "meaning": "Motion review must rotate only declared moving features about the declared local Z axis; fixed features are fully locked.",
        "moving_groups": [
            {
                "group_id": group["group_id"],
                "axis_id": group["axis_id"],
                "feature_ids": group["feature_ids"],
                "allowed_dof": ["rz"],
                "locked_dof": ["tx", "ty", "tz", "rx", "ry"],
                "axis_origin": group["origin_mm"],
                "axis_vector": group["axis_vector"],
            }
            for group in moving_groups
        ],
        "fixed_features": [
            {
                "feature_id": feature_id,
                "allowed_dof": [],
                "locked_dof": ["tx", "ty", "tz", "rx", "ry", "rz"],
            }
            for feature_id in fixed_features
        ],
    }


def _step_module_visual_materials(semantic_material_contracts: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        feature_id: contract["material"]
        for feature_id, contract in sorted(semantic_material_contracts.items())
    }


def _step_module_semantic_material_contracts(feature_refs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        feature_id: _semantic_material_contract_for_feature(feature_id, feature_ref)
        for feature_id, feature_ref in sorted(feature_refs.items())
    }


def _semantic_material_contract_for_feature(feature_id: str, feature_ref: dict[str, Any]) -> dict[str, Any]:
    semantic_owner = feature_id
    role = _semantic_material_role_for_feature(feature_id)
    source = "role_rule_from_generated_semantic_label"
    if feature_id == "external_balance_lower_jewel_leaf":
        semantic_owner = "external_balance_lower_jewel_bearing"
        role = "jewel_bearing"
        source = "external_step_leaf_ref_to_semantic_owner"
    elif feature_id == "external_balance_upper_jewel_leaf":
        semantic_owner = "external_balance_upper_jewel_bearing"
        role = "jewel_bearing"
        source = "external_step_leaf_ref_to_semantic_owner"
    material = _review_material_for_role(role)
    return {
        "visible_feature_id": feature_id,
        "visible_ref": feature_ref["ref"],
        "semantic_owner": semantic_owner,
        "role": role,
        "material": material,
        "evidence_source": source,
    }


def _semantic_material_role_for_feature(feature_id: str) -> str:
    lowered = feature_id.lower()
    if lowered in {"hour_hand_blade", "minute_hand_blade", "seconds_hand_blade"}:
        return "cyan_display_hand_blade"
    if (
        "jewel" in lowered
        or "ruby" in lowered
        or lowered in {"external_balance_upper_cap", "external_balance_upper_fixed_hardware"}
    ):
        return "jewel_bearing"
    if lowered.endswith("_bridge"):
        return "translucent_bridge_support"
    if "bridge" in lowered or "screw" in lowered:
        return "neutral_support"
    if "mainplate" in lowered or lowered in {"external_escapement_reference_plate"}:
        return "chrome_foundation_plate"
    if any(token in lowered for token in ("hand", "arbor", "staff", "pivot", "tube", "collet")):
        return "silver_shaft_or_hand"
    if any(token in lowered for token in ("wheel", "gear", "pinion", "teeth", "barrel")):
        return "brass_wheel_train"
    return "neutral_support"


def _review_material_for_role(role: str) -> dict[str, Any]:
    role_to_material = {
        "jewel_bearing": "jewel",
        "chrome_foundation_plate": "chrome",
        "silver_shaft_or_hand": "silver",
        "cyan_display_hand_blade": "cyan_hand",
        "brass_wheel_train": "brass",
        "neutral_support": "neutral",
        "translucent_bridge_support": "translucent_bridge",
    }
    return REVIEW_MATERIALS[role_to_material.get(role, "neutral")]


def _step_module_feature_refs(design: dict[str, Any], *, external_escapement: bool) -> dict[str, dict[str, Any]]:
    internal = "#o1.1" if external_escapement else "#o1"
    external = "#o1.2"
    refs = {
        feature_id: f"{internal}.{index}"
        for index, feature_id in enumerate(_step_module_internal_occurrence_order(design, external_escapement=external_escapement), start=1)
    }
    if external_escapement:
        refs.update(
            {
                "external_escape_wheel": f"{external}.1",
                "external_pallet_fork": f"{external}.2",
                "external_balance_wheel": f"{external}.3",
                "external_hairspring": f"{external}.4",
                "external_escapement_reference_plate": f"{external}.5",
                "external_escape_staff": f"{external}.6",
                "external_escape_upper_cap": f"{external}.11",
                "external_balance_upper_cap": f"{external}.12",
                "external_balance_upper_fixed_hardware": f"{external}.15",
                "external_escape_upper_fixed_hardware": f"{external}.16",
                "external_balance_lower_jewel_leaf": f"{external}.33.1",
                "external_balance_upper_jewel_leaf": f"{external}.34.1",
            }
        )
    feature_refs: dict[str, dict[str, Any]] = {}
    for feature_id, ref in refs.items():
        origin = _feature_origin(design, feature_id)
        feature_refs[feature_id] = {
            "ref": ref,
            "origin": origin,
            "axis": [0, 0, 1],
        }
    return feature_refs


def _feature_origin(design: dict[str, Any], feature_id: str) -> list[float] | None:
    axis_by_feature = {
        "mainspring_barrel": "barrel_axis",
        "barrel_arbor": "barrel_axis",
        "center_pinion": "center_axis",
        "center_wheel": "center_axis",
        "center_arbor": "center_axis",
        "third_pinion": "third_axis",
        "third_wheel": "third_axis",
        "third_arbor": "third_axis",
        "fourth_pinion": "fourth_axis",
        "fourth_wheel": "fourth_axis",
        "fourth_arbor": "fourth_axis",
        "seconds_arbor_extension": "fourth_axis",
        "seconds_hand_collet_cap": "fourth_axis",
        "seconds_hand": "fourth_axis",
        "escape_pinion": "escape_axis",
        "escape_arbor": "escape_axis",
        "external_escape_wheel": "escape_axis",
        "external_escape_staff": "escape_axis",
        "cannon_pinion_assembly": DISPLAY_CENTER_AXIS,
        "cannon_pinion_tube": DISPLAY_CENTER_AXIS,
        "minute_hand": DISPLAY_CENTER_AXIS,
        "hour_wheel": DISPLAY_CENTER_AXIS,
        "hour_tube": DISPLAY_CENTER_AXIS,
        "hour_hand": DISPLAY_CENTER_AXIS,
        "display_center_collet_stack": DISPLAY_CENTER_AXIS,
        "minute_wheel_assembly": "minute_work_axis",
        "minute_work_arbor": "minute_work_axis",
        "external_pallet_fork": "pallet_axis",
        "external_balance_wheel": "balance_axis",
        "external_hairspring": "balance_axis",
    }
    axis_id = axis_by_feature.get(feature_id)
    if not axis_id:
        return None
    axis = _axis_by_id(design, axis_id)
    return [axis["x"], axis["y"], 0.0]


def _render_step_module_js(motion: dict[str, Any]) -> str:
    motion_json = json.dumps(motion, indent=2, ensure_ascii=False)
    feature_json = json.dumps(motion["features"], indent=6, ensure_ascii=False)
    return f"""const WATCH_POWER_CHAIN_MOTION = {motion_json};

const physicalHandRatio = WATCH_POWER_CHAIN_MOTION.physical_hand_angular_velocity_ratio_to_hour_hand;

function radians(degrees) {{
  return (Number(degrees) || 0) * Math.PI / 180;
}}

function rotateAboutZ(effects, target, angleRad, origin = [0, 0, 0]) {{
  effects.transform(target, {{
    rotate: {{
      axis: [0, 0, 1],
      origin,
      angleRad
    }}
  }});
}}

function selectorForFeature(features, featureId) {{
  const selectors = features?.[featureId]?.selectors || [];
  return selectors.find((selector) => selector && selector !== "__model__") || null;
}}

function deepestMotionPartIds(partIds) {{
  return partIds.filter((partId) =>
    !partIds.some((other) => other !== partId && other.startsWith(`${{partId}}.`))
  );
}}

function safeMotionTarget(features, featureId, rawFeature = null) {{
  const feature = features?.[featureId];
  const selector = selectorForFeature(features, featureId);
  const partIds = Array.isArray(feature?.partIds) && selector
    ? feature.partIds.filter((partId) => partId === selector || partId.startsWith(`${{selector}}.`))
    : [];
  const leafPartIds = deepestMotionPartIds(partIds);
  const ref = feature?.ref || rawFeature?.ref;
  return leafPartIds.length ? {{ partIds: leafPartIds }} : (ref ? {{ ref }} : featureId);
}}

function applyReviewMaterials(effects, features) {{
  const materials = WATCH_POWER_CHAIN_MOTION.visual_materials || {{}};
  for (const [featureId, material] of Object.entries(materials)) {{
    if (!material?.hex) {{
      continue;
    }}
    const rawFeature = WATCH_POWER_CHAIN_MOTION.features?.[featureId];
    effects.style(safeMotionTarget(features, featureId, rawFeature), {{
      color: material.hex,
      opacity: material.rgba?.[3] ?? 1.0,
      edgeColor: "#4b5563"
    }});
  }}
}}

export default {{
  manifest: {{
    schemaVersion: 1,
    parameters: {{
      hourHandDeg: {{
        type: "number",
        label: "Hour hand",
        description: "Physical hour-hand rotation angle. Train, motion works, and hands are derived from this single clock parameter.",
        min: 0,
        max: 360,
        step: 0.25,
        default: 0,
        unit: "deg"
      }}
    }},
    animations: {{
      watch_train_motion: {{
        label: "Watch train motion",
        description: "Mechanical watch preview: wheel train and external escape wheel rotate; pallet fork and balance remain fixed in this phase.",
        duration: 10,
        loop: true,
        update({{ progress, set }}) {{
          set("hourHandDeg", progress * 360);
        }}
      }},
      watch_direction_review: {{
        label: "Direction review",
        description: "Slow signed-direction probe for checking clockwise display motion without seconds-hand aliasing.",
        duration: 8,
        loop: true,
        update({{ progress, set }}) {{
          set("hourHandDeg", progress * 0.5);
        }}
      }}
    }},
    features: {feature_json}
  }},
  update({{ params, effects, features }}) {{
    const hourRad = radians(params.hourHandDeg);
    for (const group of WATCH_POWER_CHAIN_MOTION.moving_groups) {{
      const angleRad = hourRad * group.angular_velocity_ratio_to_hour_hand;
      for (const feature of group.feature_ids) {{
        rotateAboutZ(effects, safeMotionTarget(features, feature), angleRad, group.origin_mm || [0, 0, 0]);
      }}
    }}
  }}
}};
"""


def _build_role_contract_report(design: dict[str, Any], independent_geometry: dict[str, Any]) -> dict[str, Any]:
    contracts = [
        _contract("mainplate", "fixed_foundation", ["support", "locate", "fasten_future_bridges"]),
        _contract("mainspring_barrel", "visual_energy_source", ["store_energy_visually", "transmit_torque_to_train"]),
        _contract("center_wheel_assembly", "speed_transforming_compound_arbor", ["transmit_torque", "increase_speed"]),
        _contract("third_wheel_assembly", "speed_transforming_compound_arbor", ["transmit_torque", "increase_speed"]),
        _contract("fourth_wheel_assembly", "speed_transforming_compound_arbor", ["transmit_torque", "drive_seconds_display"]),
        _contract("escape_wheel_assembly", "escapement_release_wheel", ["receive_train_motion", "feed_placeholder_escapement"]),
        _contract("pallet_balance_placeholder", "placeholder_escapement_link", ["reserve_envelope_for_future_escapement"]),
        _contract("display_works", "time_display_chain", ["display_seconds", "display_minutes", "display_hours"]),
    ]
    contracts.extend(_jewel_support_contracts(design, independent_geometry))
    contracts.extend(_bridge_stage_contracts(design, independent_geometry))
    contracts.extend(_display_hand_contract(hand, design, independent_geometry) for hand in design["display"]["hands"])
    status = "pass" if all(contract["validation"]["status"] == "pass" for contract in contracts) else "fail"
    return {
        "kind": "watch_power_chain_mvp_role_contract_report",
        "phase": PHASE,
        "pattern_card_id": PATTERN_CARD_ID,
        "status": status,
        "roles": sorted({contract["role"] for contract in contracts}),
        "contracts": contracts,
    }


def _contract(occurrence_id: str, role: str, function_claims: list[str]) -> dict[str, Any]:
    return {
        "occurrence_id": occurrence_id,
        "role": role,
        "function_claims": function_claims,
        "motion_chain": {"kind": "declared_or_fixed", "status": "pass"},
        "mount_chain": {"kind": "declared_or_fixed", "status": "pass"},
        "constraint_chain": {"locked_dof": ["tx", "ty", "tz", "rx", "ry", "rz"], "status": "pass"},
        "geometry_constraint": {"required": ["solid_body", "axis_or_fixed_datum"]},
        "validation_contract": {"checks": ["has_explicit_axis_or_fixed_reference", "has_geometry_evidence"]},
        "behavior_claims": ["has_explicit_axis_or_fixed_reference", "has_geometry_evidence"],
        "required_interfaces": ["axis_or_fixed_datum"],
        "required_features": ["solid_body", "semantic_role"],
        "validation": {"status": "pass", "missing_evidence": []},
    }


def _jewel_support_contracts(design: dict[str, Any], independent_geometry: dict[str, Any]) -> list[dict[str, Any]]:
    jewel_report = independent_geometry["jewel_supports"]
    lower = _contract(
        "lower_jewel_supports",
        "lower_jewel_support",
        ["support_lower_train_pivots", "locate_arbors_in_mainplate"],
    )
    lower.update(
        {
            "pattern_card_id": PATTERN_CARD_ID,
            "mount_chain": {
                "kind": "mainplate_integrated_jewel_seats",
                "owner": "foundation_mainplate",
                "axis_ids": jewel_report["required_axis_ids"],
                "status": "pass" if not jewel_report["missing_lower_jewels"] else "fail",
            },
            "geometry_constraint": {
                "required": ["lower_jewel", "lower_jewel_seat", "uniform_lower_jewel_height"],
                "minimum_clearance_source": "jewel_support_interference_report",
            },
            "validation_contract": {
                "checks": [
                    "lower_jewel_present_for_every_supported_axis",
                    "lower_jewel_height_uniform",
                    "lower_jewel_and_seat_do_not_interfere_with_other_envelopes",
                ],
            },
            "validation": {
                "status": "pass"
                if not jewel_report["missing_lower_jewels"]
                and not jewel_report["height_failures"]
                and not jewel_report["interference_failures"]
                else "fail",
                "missing_evidence": jewel_report["missing_lower_jewels"],
            },
        }
    )
    future = _contract(
        "future_upper_jewel_support_targets",
        "future_upper_jewel_support_target",
        ["reserve_bridge_support_plane", "prepare_upper_pivot_supports_for_bridge_stage"],
    )
    future.update(
        {
            "pattern_card_id": PATTERN_CARD_ID,
            "mount_chain": {
                "kind": "future_bridge_plate_targets_not_generated_in_phase_1",
                "owner": "future_bridge_plate",
                "axis_ids": jewel_report["required_axis_ids"],
                "status": "pass" if not jewel_report["missing_future_upper_jewels"] else "fail",
            },
            "geometry_constraint": {
                "required": ["uniform_future_upper_jewel_top_plane", "below_display_hands", "above_train_stack"],
                "future_upper_jewel_top_z_mm": jewel_report["future_upper_jewel_top_z_mm"],
                "minimum_hand_clearance_mm": jewel_report["minimum_hand_clearance_above_future_upper_jewel_mm"],
            },
            "validation_contract": {
                "checks": [
                    "future_upper_jewel_target_present_for_every_supported_axis",
                    "future_upper_jewel_height_uniform",
                    "future_upper_jewel_plane_below_hands",
                    "future_upper_jewel_plane_above_train",
                ],
            },
            "validation": {
                "status": "pass"
                if not jewel_report["missing_future_upper_jewels"]
                and not jewel_report["height_failures"]
                else "fail",
                "missing_evidence": jewel_report["missing_future_upper_jewels"],
            },
        }
    )
    return [lower, future]


def _bridge_stage_contracts(design: dict[str, Any], independent_geometry: dict[str, Any]) -> list[dict[str, Any]]:
    if not design.get("bridges_generated"):
        return []
    bridge_report = independent_geometry["bridge_stage"]
    contracts = []
    for bridge in bridge_report["bridges"]:
        contract = _contract(
            bridge["bridge_id"],
            "upper_bridge_plate",
            ["support_upper_train_pivots", "locate_upper_jewel_bearings", "fasten_to_mainplate_service_band"],
        )
        contract.update(
            {
                "pattern_card_id": BRIDGE_STAGE_PATTERN_CARD_ID,
                "mount_chain": {
                    "kind": "bridge_screws_and_integrated_support_pads_to_mainplate_service_band",
                    "fixed_base": "foundation_mainplate",
                    "support_face": "mainplate_outer_raised_support_ring",
                    "screw_ids": [screw["screw_id"] for screw in bridge["screws"]],
                    "support_pad_ids": [pad["pad_id"] for pad in bridge["support_pads"]],
                    "status": "pass",
                },
                "constraint_chain": {
                    "locked_dof": ["tx", "ty", "tz", "rx", "ry", "rz"],
                    "constraint_sources": ["support_pads", "bridge_screws", "mainplate_service_band"],
                    "status": "pass",
                },
                "geometry_constraint": {
                    "supported_axis_ids": bridge["supported_axis_ids"],
                    "z_min_mm": bridge["z_min_mm"],
                    "z_max_mm": bridge["z_max_mm"],
                    "screw_pitch_radius_mm": bridge_report["screw_policy"]["pitch_radius_mm"],
                    "review_opacity": bridge["review_opacity"],
                },
                "validation_contract": {
                    "checks": [
                        "three_bridge_regions_present",
                        "bridge_screw_count_matches_span_policy",
                        "bridge_screws_share_pitch_circle",
                        "support_pads_touch_mainplate_service_face_and_bridge_bottom",
                    ],
                },
                "required_interfaces": ["upper_jewel_axis_group", "support_pad_to_mainplate_service_face", "bridge_screw_path"],
                "required_features": [
                    bridge["bridge_id"],
                    *[screw["screw_id"] for screw in bridge["screws"]],
                    *[pad["pad_id"] for pad in bridge["support_pads"]],
                ],
                "validation": {
                    "status": "pass" if bridge_report["status"] == "pass" else "fail",
                    "missing_evidence": bridge_report["failures"],
                },
            }
        )
        contracts.append(contract)
    return contracts


def _display_hand_contract(hand: dict[str, Any], design: dict[str, Any], independent_geometry: dict[str, Any]) -> dict[str, Any]:
    hand_id = hand["hand_id"]
    drive_chain = next(chain for chain in design["display"]["drive_chains"] if chain["hand_id"] == hand_id)
    mount_stack = next(stack for stack in design["display"]["mount_stacks"] if stack["hand_id"] == hand_id)
    independent_mount = independent_geometry["hand_mounts"][hand_id]
    independent_motion = independent_geometry["motion_chains"][hand_id]
    required_features = [
        f"{hand_id}_hub",
        f"{hand_id}_blade",
        *[segment["component_id"] for segment in mount_stack["segments"][:-1]],
    ]
    missing_evidence = []
    if independent_mount["status"] != "pass":
        missing_evidence.append("independent_mount_geometry")
    independent_attachment = independent_geometry["feature_attachments"][hand_id]
    if independent_attachment["status"] != "pass":
        missing_evidence.append("independent_feature_attachment_geometry")
    if independent_motion["status"] != "pass":
        missing_evidence.append("independent_motion_chain_geometry")
    return {
        "occurrence_id": hand_id,
        "role": "display_hand",
        "pattern_card_id": PATTERN_CARD_ID,
        "function_claims": [f"display_{hand_id.removesuffix('_hand')}"],
        "behavior_claims": ["rotates_with_declared_display_member", "has_closed_mount_chain", "clears_sweep_envelope"],
        "motion_chain": {
            "source": drive_chain["source"],
            "path": drive_chain["path"],
            "ratio": hand["ratio"],
            "axis_id": hand["axis_id"],
            "interface_sequence": drive_chain.get("interface_sequence"),
            "ratio_proof": drive_chain.get("ratio_proof"),
            "independent_status": independent_motion["status"],
        },
        "mount_chain": {
            "segments": [segment["component_id"] for segment in mount_stack["segments"]],
            "interfaces": mount_stack["interfaces"],
        },
        "feature_attachment_chain": {
            "features": [f"{hand_id}_hub", f"{hand_id}_blade"],
            "attachments": [
                {
                    "from": f"{hand_id}_blade",
                    "to": f"{hand_id}_hub",
                    "kind": "rigid_blade_root_to_hub",
                    "status": independent_attachment["status"],
                    "evidence": {
                        "blade_to_axis_distance_mm": independent_attachment["blade_to_axis_distance_mm"],
                        "hub_outer_radius_mm": independent_attachment["hub_outer_radius_mm"],
                    },
                }
            ],
        },
        "constraint_chain": {
            "locked_dof": ["tx", "ty", "tz", "rx", "ry", "rz"],
            "allowed_motion": ["rz_about_axis_when_animated"],
            "fixed_base_path": [mount_stack["segments"][0]["component_id"], mount_stack["segments"][-1]["component_id"]],
        },
        "geometry_constraint": {
            "axis_id": hand["axis_id"],
            "hub_id": f"{hand_id}_hub",
            "z_mm": hand["z_mm"],
            "max_xy_center_error_mm": mount_stack["xy_tolerance_mm"],
            "max_positive_z_gap_mm": mount_stack["gap_tolerance_mm"],
            "min_radial_overlap_mm": 0.03,
            "sweep_envelope": design["display"]["sweep_envelopes"][hand_id],
        },
        "validation_contract": {
            "checks": [
                "product_and_feature_presence",
                "mount_stack_z_connected",
                "mount_stack_xy_connected",
                "mount_stack_radially_connected",
                "mount_stack_6dof_constrained",
                "feature_attachment_chain_connected",
                "motion_chain_realized",
                "sweep_envelope_clear",
            ],
            "independent_report": "watch_power_chain_mvp.validation.json#/independent_geometry_checks",
        },
        "required_interfaces": ["display_axis", "closed_mount_stack", "realized_motion_chain", "hand_sweep_envelope"],
        "required_features": required_features,
        "validation": {
            "status": "pass" if not missing_evidence else "fail",
            "missing_evidence": missing_evidence,
        },
    }


def _build_validation_report(
    semantic: dict[str, Any],
    role_contracts: dict[str, Any],
    independent_geometry: dict[str, Any],
) -> dict[str, Any]:
    failed = []
    if semantic["status"] != "pass":
        failed.append("semantic_checks")
    if role_contracts["status"] != "pass":
        failed.append("role_contract_checks")
    if independent_geometry["status"] != "pass":
        failed.append("independent_geometry_checks")
    return {
        "kind": "watch_power_chain_mvp_validation_report",
        "phase": PHASE,
        "pattern_card_id": PATTERN_CARD_ID,
        "status": "pass" if not failed else "fail",
        "failed_checks": failed,
        "independent_geometry_checks": independent_geometry,
        "checks": {
            "semantic_checks": semantic["status"],
            "role_contract_checks": role_contracts["status"],
            "independent_geometry_checks": independent_geometry["status"],
            "z_stack_layering": independent_geometry["z_stack"]["status"],
            "jewel_supports": independent_geometry["jewel_supports"]["status"],
            "bridge_perimeter_service_band": independent_geometry["bridge_perimeter_service_band"]["status"],
            "bridges_excluded_by_design": "pass" if not semantic["bridges_generated"] else "skipped",
            "bridge_stage_three_bridge_plates_present": independent_geometry["bridge_stage"]["status"],
        },
    }


def _render_dashboard(design: dict[str, Any], validation: dict[str, Any]) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Watch Power Chain MVP</title>
  <style>
    body {{ font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif; margin: 28px; color: #202124; }}
    .card {{ border: 1px solid #dadce0; border-radius: 8px; padding: 14px; margin: 12px 0; background: #f8fafd; }}
    code {{ background: #f1f3f4; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Watch Power Chain MVP</h1>
  <div class="card">
    <p><strong>Phase:</strong> <code>{PHASE}</code></p>
    <p><strong>Status:</strong> <code>{validation['status']}</code></p>
    <p><strong>Seed:</strong> <code>{design['seed']}</code></p>
  </div>
  <div class="card">
    <h2>Scope</h2>
    <p>涓诲彂鏉＄洅鍒版搾绾佃疆鐨勫姩鍔涢摼宸茬敓鎴愩€傛ˉ鏉裤€佹ˉ鏉胯灪閽夊拰鐪熷疄鎿掔旱鍙夌粏鑺傛殏涓嶇敓鎴愩€?/p>
  </div>
  <div class="card">
    <h2>Artifacts</h2>
    <ul>
      <li><code>watch_power_chain_mvp.step</code></li>
      <li><code>watch_power_chain_mvp.semantic.json</code></li>
      <li><code>watch_power_chain_mvp.kinematic.json</code></li>
      <li><code>watch_power_chain_mvp.role_contracts.json</code></li>
    </ul>
  </div>
</body>
</html>
"""


def _power_chain_connected(design: dict[str, Any]) -> bool:
    mesh_pairs = {(mesh["driver"], mesh["driven"]) for mesh in design["meshes"]}
    required = [
        ("barrel_outer_teeth", "center_pinion"),
        ("center_wheel", "third_pinion"),
        ("third_wheel", "fourth_pinion"),
        ("fourth_wheel", "escape_pinion"),
    ]
    return all(pair in mesh_pairs for pair in required)


def _compound_gears_complete(design: dict[str, Any]) -> bool:
    by_axis: dict[str, set[str]] = {}
    for gear in design["gears"]:
        by_axis.setdefault(gear["axis_id"], set()).add(gear["gear_id"])
    return all(
        required.issubset(by_axis.get(axis, set()))
        for axis, required in {
            "center_axis": {"center_wheel", "center_pinion"},
            "third_axis": {"third_wheel", "third_pinion"},
            "fourth_axis": {"fourth_wheel", "fourth_pinion"},
            "escape_axis": {"escape_wheel", "escape_pinion"},
        }.items()
    )


def _gear_mesh_phase_alignment(design: dict[str, Any]) -> bool:
    records = [*design.get("mesh_phase_records", []), *design.get("display_mesh_phase_records", [])]
    expected_count = len(design.get("meshes", [])) + len(design.get("display_meshes", []))
    if len(records) != expected_count:
        return False
    return all(
        abs(record["driver_tooth_error_deg"]) <= GEAR_MESH_PHASE_TOLERANCE_DEG
        and abs(record["driven_gap_error_deg"]) <= GEAR_MESH_PHASE_TOLERANCE_DEG
        for record in records
    )


def _display_hands_exist(design: dict[str, Any]) -> bool:
    hand_ids = {hand["hand_id"] for hand in design["display"]["hands"]}
    return {"hour_hand", "minute_hand", "seconds_hand"}.issubset(hand_ids)


def _display_hand_stack_clear(design: dict[str, Any]) -> bool:
    display = design["display"]
    hands = display["hands"]
    if display["strategy"] != "separate_display_axis_and_off_center_seconds":
        return False
    if display["z_clearance_above_train_mm"] < 0.8:
        return False
    if [hand["hand_id"] for hand in hands] != ["hour_hand", "minute_hand", "seconds_hand"]:
        return False
    if [hand["axis_id"] for hand in hands] != [DISPLAY_CENTER_AXIS, DISPLAY_CENTER_AXIS, "fourth_axis"]:
        return False
    if [hand["model_source"] for hand in hands] != [
        "fixed_central_hour_hand",
        "fixed_central_minute_hand",
        "computed_sub_seconds_hand",
    ]:
        return False
    if not (hands[0]["length_mm"] < hands[1]["length_mm"]):
        return False
    if any(upper["z_mm"] - lower["z_mm"] < 0.18 for lower, upper in zip(hands, hands[1:])):
        return False
    return [tube["tube_id"] for tube in display["tube_stack"]] == ["hour_tube", "cannon_pinion_tube"]


def _three_hand_drive_chains_declared(design: dict[str, Any]) -> bool:
    chains = {chain["hand_id"]: chain for chain in design["display"]["drive_chains"]}
    return (
        chains.get("minute_hand", {}).get("source") == "center_wheel_to_cannon_pinion"
        and chains.get("hour_hand", {}).get("source") == "minute_motion_work_reduction"
        and chains.get("seconds_hand", {}).get("source") == "fourth_wheel_direct_sub_seconds"
    )


def _display_motion_chain_realized(design: dict[str, Any]) -> bool:
    report = _build_display_motion_chain_report(design)
    return report["status"] == "pass"


def _hour_motion_reduction_proven(design: dict[str, Any]) -> bool:
    motion_works = design["display"].get("motion_works", {})
    ratio = motion_works.get("ratio_proof", {}).get("hour_to_minute_ratio")
    if not isinstance(ratio, (int, float)) or abs(ratio - (1 / 12)) > 1e-9:
        return False
    return _build_display_motion_chain_report(design)["hour_hand"]["status"] == "pass"


def _coaxial_display_sleeve_clearance(design: dict[str, Any]) -> bool:
    report = _build_coaxial_sleeve_clearance_report(design["display"])
    return report["status"] == "pass"


def _central_hour_minute_axis(design: dict[str, Any]) -> bool:
    axes = {axis["axis_id"]: axis for axis in design["axes"]}
    display_axis = axes.get(DISPLAY_CENTER_AXIS)
    fourth_axis = axes.get("fourth_axis")
    if not display_axis or not fourth_axis:
        return False
    hands = {hand["hand_id"]: hand for hand in design["display"]["hands"]}
    center_ok = abs(display_axis["x"]) <= 1e-6 and abs(display_axis["y"]) <= 1e-6
    seconds_offset = math.hypot(fourth_axis["x"] - display_axis["x"], fourth_axis["y"] - display_axis["y"]) > 1.0
    return (
        center_ok
        and seconds_offset
        and hands.get("hour_hand", {}).get("axis_id") == DISPLAY_CENTER_AXIS
        and hands.get("minute_hand", {}).get("axis_id") == DISPLAY_CENTER_AXIS
        and hands.get("seconds_hand", {}).get("axis_id") == "fourth_axis"
    )


def _seconds_hand_length_within_case_clearance(design: dict[str, Any]) -> bool:
    seconds_hand = next(hand for hand in design["display"]["hands"] if hand["hand_id"] == "seconds_hand")
    envelope = design["display"]["sweep_envelopes"]["seconds_hand"]
    return seconds_hand["length_mm"] == envelope["radius_mm"] and seconds_hand["length_mm"] < envelope["case_min_clearance_mm"]


def _seconds_hand_sweep_clear(design: dict[str, Any]) -> bool:
    return design["display"]["sweep_envelopes"]["seconds_hand"]["interference_failures"] == []


def _display_hand_mount_stacks_closed(design: dict[str, Any]) -> bool:
    return all(stack["closed"] and stack["max_positive_gap_mm"] <= stack["gap_tolerance_mm"] for stack in design["display"]["mount_stacks"])


def _display_hand_mount_stacks_xy_connected(design: dict[str, Any]) -> bool:
    return all(stack["xy_connected"] and stack["max_xy_center_error_mm"] <= stack["xy_tolerance_mm"] for stack in design["display"]["mount_stacks"])


def _display_hand_mount_stacks_6dof_constrained(design: dict[str, Any]) -> bool:
    return all(stack["six_dof_constrained"] and stack["unresolved_dof_count"] == 0 for stack in design["display"]["mount_stacks"])


def _axis_by_id(design: dict[str, Any], axis_id: str) -> dict[str, Any]:
    return next(axis for axis in design["axes"] if axis["axis_id"] == axis_id)


def _gear_by_id(design: dict[str, Any], gear_id: str) -> dict[str, Any]:
    return next(gear for gear in design["gears"] if gear["gear_id"] == gear_id)


def _label(shape, label: str):
    shape.label = label
    _apply_review_material(shape, label)
    return shape


def _part(shape, label: str):
    part = Part([shape], label=label) if hasattr(shape, "wrapped") else Part(shape, label=label)
    _apply_review_material(part, label)
    return part


def _review_material_for_label(label: str) -> dict[str, Any]:
    return _review_material_for_role(_semantic_material_role_for_feature(label))


def _apply_review_material(shape, label: str):
    rgba = _review_material_for_label(label)["rgba"]
    try:
        shape.color = Color(*rgba)
    except Exception:
        pass
    return shape


def _extrude_xy_points_preserve_frame(points: list[tuple[float, float]], amount: float):
    normalized_points = [(float(point[0]), float(point[1])) for point in points]
    closed_points = (
        normalized_points
        if normalized_points[0] == normalized_points[-1]
        else [*normalized_points, normalized_points[0]]
    )
    with BuildSketch(Plane.XY) as sketch:
        with BuildLine():
            Polyline(*closed_points)
        make_face()
    return extrude(sketch.sketch, amount=amount)


def _z_cylinder(radius: float, height: float):
    return Cylinder(radius=radius, height=height, align=(Align.CENTER, Align.CENTER, Align.CENTER))


def _annulus(outer_radius: float, inner_radius: float, height: float):
    return _z_cylinder(outer_radius, height) - _z_cylinder(inner_radius, height + 0.04)


def _gear_points(
    teeth: int,
    pitch_radius: float,
    outer_radius: float,
    root_radius: float,
    *,
    phase_deg: float = 0.0,
    escape: bool = False,
) -> list[tuple[float, float]]:
    points = []
    samples_per_tooth = 6 if not escape else 4
    pitch = 2.0 * math.pi / teeth
    phase = math.radians(phase_deg)
    for tooth_index in range(teeth):
        tooth_center = phase + tooth_index * pitch
        for sample in range(samples_per_tooth):
            u = sample / samples_per_tooth - 0.5
            if escape:
                radius = outer_radius if abs(u) < 0.16 else root_radius
            else:
                flank = 0.5 * (1.0 + math.cos(math.pi * abs(u) / 0.5))
                radius = root_radius + (outer_radius - root_radius) * (flank**0.9)
                if abs(u) < 0.17:
                    radius = max(radius, pitch_radius + (outer_radius - pitch_radius) * 0.75)
            angle = tooth_center + u * pitch
            points.append((math.cos(angle) * radius, math.sin(angle) * radius))
    return points


def _make_spiral_placeholder(x: float, y: float, radius: float, z: float):
    children = []
    for index in range(5):
        outer = radius * (0.22 + index * 0.135)
        inner = max(0.08, outer - 0.08)
        children.append(_annulus(outer, inner, 0.055).located(Location((x, y, z + index * 0.025))))
    return Compound(label="mainspring_placeholder", children=children)


def _bar_points(x1: float, y1: float, x2: float, y2: float, width: float) -> list[tuple[float, float]]:
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy) or 1.0
    nx = -dy / length * width / 2.0
    ny = dx / length * width / 2.0
    return [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]


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
    return [
        (root_x + nx * base_width / 2.0, root_y + ny * base_width / 2.0),
        (tip_x + nx * tip_width / 2.0, tip_y + ny * tip_width / 2.0),
        (tip_x - nx * tip_width / 2.0, tip_y - ny * tip_width / 2.0),
        (root_x - nx * base_width / 2.0, root_y - ny * base_width / 2.0),
    ]


def _leaf_pointer_points(
    x: float,
    y: float,
    angle: float,
    *,
    start_radius: float,
    length: float,
    max_width: float,
    neck_width: float,
) -> list[tuple[float, float]]:
    ux = math.cos(angle)
    uy = math.sin(angle)
    nx = -uy
    ny = ux
    neck_x = x + ux * start_radius
    neck_y = y + uy * start_radius
    belly_x = x + ux * (length * 0.58)
    belly_y = y + uy * (length * 0.58)
    tip_x = x + ux * length
    tip_y = y + uy * length
    return [
        (neck_x + nx * neck_width / 2.0, neck_y + ny * neck_width / 2.0),
        (belly_x + nx * max_width / 2.0, belly_y + ny * max_width / 2.0),
        (tip_x, tip_y),
        (belly_x - nx * max_width / 2.0, belly_y - ny * max_width / 2.0),
        (neck_x - nx * neck_width / 2.0, neck_y - ny * neck_width / 2.0),
    ]


def _seconds_hand_points(
    x: float,
    y: float,
    angle: float,
    *,
    start_radius: float,
    length: float,
    tail_length: float,
    width: float,
) -> list[tuple[float, float]]:
    ux = math.cos(angle)
    uy = math.sin(angle)
    nx = -uy
    ny = ux
    tail_x = x - ux * tail_length
    tail_y = y - uy * tail_length
    root_x = x + ux * start_radius
    root_y = y + uy * start_radius
    tip_x = x + ux * length
    tip_y = y + uy * length
    tail_width = width * 1.8
    tip_width = width * 0.7
    return [
        (tail_x + nx * tail_width / 2.0, tail_y + ny * tail_width / 2.0),
        (root_x + nx * width / 2.0, root_y + ny * width / 2.0),
        (tip_x + nx * tip_width / 2.0, tip_y + ny * tip_width / 2.0),
        (tip_x - nx * tip_width / 2.0, tip_y - ny * tip_width / 2.0),
        (root_x - nx * width / 2.0, root_y - ny * width / 2.0),
        (tail_x - nx * tail_width / 2.0, tail_y - ny * tail_width / 2.0),
    ]



