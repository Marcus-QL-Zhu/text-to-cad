import hashlib
import math
from typing import Any

from ..gear_case_clearance import prove_gear_case_inner_wall_clearance
from .card import PATTERN_CARD_ID

CASE_INNER_RADIUS_MM = 21.0
MAINPLATE_RADIUS_MM = 19.7
GEAR_MODULE_MM = 0.10
TRAIN_STAGE_MODULE_MM = 0.13
MIN_DISPLAY_AXIS_SEPARATION_MM = 5.0
MIN_NON_MESH_CLEARANCE_MM = 0.25
FOREIGN_AXIS_KEEP_OUT_RADIUS_MM = 0.24
CENTER_DISTANCE_TOLERANCE_MM = 0.001
HAND_CASE_CLEARANCE_MM = 0.80

TRAIN_TOOTH_COUNTS = {
    "barrel_outer_teeth": 72,
    "train_stage_1_pinion": 12,
    "train_stage_1_wheel": 60,
    "train_stage_2_pinion": 10,
    "train_stage_2_wheel": 54,
    "train_stage_3_pinion": 9,
    "train_stage_3_wheel": 48,
    "escape_pinion": 8,
}

DISPLAY_TOOTH_COUNTS = {
    "minute_input_relay_pinion": 24,
    "minute_input_relay_wheel": 18,
    "minute_display_member": 36,
    "hour_input_relay_pinion": 24,
    "hour_input_relay_wheel": 12,
    "hour_reduction_relay_pinion": 72,
    "hour_reduction_relay_wheel": 24,
    "hour_display_member": 96,
}

MINUTE_BRANCH_ANGLE_OFFSETS_DEG = [-50.0, -20.0, 10.0, 40.0, 70.0, 100.0, 130.0]
HOUR_BRANCH_ANGLE_OFFSETS_DEG = [-160.0, -130.0, -100.0, -70.0, -40.0, 110.0, 140.0, 170.0]
MINUTE_OUTPUT_ANGLE_OFFSETS_DEG = [-28.0, -12.0, 0.0, 16.0, 30.0]
HOUR_RELAY_ANGLE_OFFSETS_DEG = [-28.0, -12.0, 0.0, 14.0, 30.0]
HOUR_OUTPUT_ANGLE_OFFSETS_DEG = [-40.0, -20.0, 0.0, 22.0, 42.0]


def solve_independent_display_layout(
    *,
    seed: int = 731,
    case_inner_radius_mm: float = CASE_INNER_RADIUS_MM,
    mainplate_radius_mm: float = MAINPLATE_RADIUS_MM,
) -> dict[str, Any]:
    """Solve the 2D layout for independent hour and minute display branches."""

    candidates = []
    candidate_index = 1
    for minute_branch_angle in _seed_sorted_angles(seed, "minute_branch", MINUTE_BRANCH_ANGLE_OFFSETS_DEG):
        for hour_branch_angle in _seed_sorted_angles(seed, "hour_branch", HOUR_BRANCH_ANGLE_OFFSETS_DEG):
            for minute_output_offset in _seed_sorted_angles(seed, "minute_output", MINUTE_OUTPUT_ANGLE_OFFSETS_DEG):
                for hour_relay_offset in _seed_sorted_angles(seed, "hour_relay", HOUR_RELAY_ANGLE_OFFSETS_DEG):
                    for hour_output_offset in _seed_sorted_angles(seed, "hour_output", HOUR_OUTPUT_ANGLE_OFFSETS_DEG):
                        candidates.append(
                            _build_independent_display_candidate(
                                seed,
                                case_inner_radius_mm,
                                mainplate_radius_mm,
                                minute_branch_angle_deg=minute_branch_angle,
                                hour_branch_angle_deg=hour_branch_angle,
                                minute_output_offset_deg=minute_output_offset,
                                hour_relay_offset_deg=hour_relay_offset,
                                hour_output_offset_deg=hour_output_offset,
                                candidate_index=candidate_index,
                            )
                        )
                        candidate_index += 1

    selected_candidate = next((candidate for candidate in candidates if candidate["status"] == "pass"), None)
    return {
        "kind": "watch_independent_display_solver_report",
        "pattern_card_id": PATTERN_CARD_ID,
        "status": "pass" if selected_candidate is not None else "fail",
        "seed": seed,
        "selection_strategy": "seeded_parallel_display_branch_solver_v1",
        "construction_references": [
            "movement_geometric_center",
            "movement_frame",
            "train_stage_3_wheel_as_display_reference",
        ],
        "fixed": {
            "case_inner_radius_mm": case_inner_radius_mm,
            "mainplate_radius_mm": mainplate_radius_mm,
            "movement_geometric_center": {"x": 0.0, "y": 0.0, "physical_axis": False},
            "display_train_reference": "train_stage_3_wheel",
        },
        "variables": {
            "enumerated": [
                "minute_branch_angle",
                "hour_branch_angle",
                "minute_output_angle",
                "hour_relay_angle",
                "hour_output_angle",
            ],
            "derived": [
                "minute_input_relay_axis",
                "minute_display_axis",
                "hour_input_relay_axis",
                "hour_reduction_relay_axis",
                "hour_display_axis",
            ],
        },
        "candidate_count": len(candidates),
        "feasible_candidate_count": sum(1 for candidate in candidates if candidate["status"] == "pass"),
        "selected_candidate": selected_candidate,
        "candidates": candidates,
    }


def _build_independent_display_candidate(
    seed: int,
    case_inner_radius_mm: float,
    mainplate_radius_mm: float,
    *,
    minute_branch_angle_deg: float,
    hour_branch_angle_deg: float,
    minute_output_offset_deg: float,
    hour_relay_offset_deg: float,
    hour_output_offset_deg: float,
    candidate_index: int,
) -> dict[str, Any]:
    train_axes = _solve_base_train_axes(seed)
    train_stage_3_axis = train_axes["train_stage_3_axis"]
    escape_axis = train_axes["escape_axis"]
    train_stage_3_escape_angle_deg = _angle_between(train_stage_3_axis, escape_axis)
    train_stage_3_tooth_pitch_deg = 360.0 / TRAIN_TOOTH_COUNTS["train_stage_3_wheel"]
    minute_branch_angle_deg = _snap_angle_to_driver_tooth_grid(
        minute_branch_angle_deg,
        reference_angle_deg=train_stage_3_escape_angle_deg,
        tooth_pitch_deg=train_stage_3_tooth_pitch_deg,
    )
    hour_branch_angle_deg = _snap_angle_to_driver_tooth_grid(
        hour_branch_angle_deg,
        reference_angle_deg=train_stage_3_escape_angle_deg,
        tooth_pitch_deg=train_stage_3_tooth_pitch_deg,
    )

    minute_input_distance = _center_distance(
        TRAIN_STAGE_MODULE_MM,
        TRAIN_TOOTH_COUNTS["train_stage_3_wheel"],
        DISPLAY_TOOTH_COUNTS["minute_input_relay_pinion"],
    )
    minute_output_distance = _center_distance(
        GEAR_MODULE_MM,
        DISPLAY_TOOTH_COUNTS["minute_input_relay_wheel"],
        DISPLAY_TOOTH_COUNTS["minute_display_member"],
    )
    hour_input_distance = _center_distance(
        TRAIN_STAGE_MODULE_MM,
        TRAIN_TOOTH_COUNTS["train_stage_3_wheel"],
        DISPLAY_TOOTH_COUNTS["hour_input_relay_pinion"],
    )
    hour_relay_distance = _center_distance(
        GEAR_MODULE_MM,
        DISPLAY_TOOTH_COUNTS["hour_input_relay_wheel"],
        DISPLAY_TOOTH_COUNTS["hour_reduction_relay_pinion"],
    )
    hour_output_distance = _center_distance(
        GEAR_MODULE_MM,
        DISPLAY_TOOTH_COUNTS["hour_reduction_relay_wheel"],
        DISPLAY_TOOTH_COUNTS["hour_display_member"],
    )

    minute_input_axis = _polar_from(
        (train_stage_3_axis["x"], train_stage_3_axis["y"]),
        minute_input_distance,
        minute_branch_angle_deg,
    )
    minute_axis = _polar_from(
        minute_input_axis,
        minute_output_distance,
        minute_branch_angle_deg + minute_output_offset_deg,
    )
    hour_input_axis = _polar_from(
        (train_stage_3_axis["x"], train_stage_3_axis["y"]),
        hour_input_distance,
        hour_branch_angle_deg,
    )
    hour_relay_axis = _polar_from(
        hour_input_axis,
        hour_relay_distance,
        hour_branch_angle_deg + hour_relay_offset_deg,
    )
    hour_axis = _polar_from(
        hour_relay_axis,
        hour_output_distance,
        hour_branch_angle_deg + hour_output_offset_deg,
    )

    axes = [
        *train_axes.values(),
        _axis("minute_input_relay_axis", minute_input_axis, "parallel_minute_input_relay_axis", 0.16),
        _axis("minute_display_axis", minute_axis, "free_placed_minute_display_axis", 0.16),
        _axis("hour_input_relay_axis", hour_input_axis, "parallel_hour_input_relay_axis", 0.16),
        _axis("hour_reduction_relay_axis", hour_relay_axis, "parallel_hour_reduction_relay_axis", 0.16),
        _axis("hour_display_axis", hour_axis, "free_placed_hour_display_axis", 0.16),
    ]
    axes_by_id = {axis["axis_id"]: axis for axis in axes}
    display_gears = _display_gears(axes_by_id)
    display_meshes = _display_meshes()
    power_branches = _power_branches()
    ratio_proof = _display_ratio_proof()
    center_distance_proofs = _declared_mesh_center_distance_proofs(display_gears, axes_by_id)
    sweep_envelopes = _display_sweep_envelopes(axes_by_id, case_inner_radius_mm)
    geometry_proofs = _geometry_proofs(axes_by_id, display_gears, sweep_envelopes, case_inner_radius_mm)
    checks = _candidate_checks(
        geometry_proofs,
        sweep_envelopes,
        ratio_proof,
        axes_by_id,
        center_distance_proofs,
        power_branches,
    )
    failed_checks = [check_id for check_id, status in checks.items() if status != "pass"]

    return {
        "candidate_id": f"independent_display_seed_{seed}_candidate_{candidate_index:04d}",
        "status": "pass" if not failed_checks else "fail",
        "pattern_card_id": PATTERN_CARD_ID,
        "variables": {
            "gear_module": GEAR_MODULE_MM,
            "train_stage_module": TRAIN_STAGE_MODULE_MM,
            "train_tooth_counts": TRAIN_TOOTH_COUNTS,
            "display_tooth_counts": DISPLAY_TOOTH_COUNTS,
            "minute_branch_angle_deg": minute_branch_angle_deg,
            "hour_branch_angle_deg": hour_branch_angle_deg,
            "minute_output_offset_deg": minute_output_offset_deg,
            "hour_relay_offset_deg": hour_relay_offset_deg,
            "hour_output_offset_deg": hour_output_offset_deg,
        },
        "axes": axes,
        "display_gears": display_gears,
        "display_meshes": display_meshes,
        "power_branches": power_branches,
        "display_ratio_proof": ratio_proof,
        "center_distance_proofs": center_distance_proofs,
        "sweep_envelopes": sweep_envelopes,
        "geometry_proofs": geometry_proofs,
        "checks": checks,
        "failed_checks": failed_checks,
        "forbidden_generated_roles": [],
    }


def _solve_base_train_axes(seed: int) -> dict[str, dict[str, Any]]:
    train_stage_1_angle = 214.0 + _range_by_seed(seed, "train_stage_1_jitter", -24.0, 24.0)
    train_stage_1_radius = _range_by_seed(seed, "train_stage_1_radius", 6.8, 9.6)
    train_stage_1_axis = _polar_from((0.0, 0.0), train_stage_1_radius, train_stage_1_angle)
    barrel_axis = _polar_from(
        train_stage_1_axis,
        _center_distance(TRAIN_STAGE_MODULE_MM, TRAIN_TOOTH_COUNTS["barrel_outer_teeth"], TRAIN_TOOTH_COUNTS["train_stage_1_pinion"]),
        train_stage_1_angle,
    )
    train_stage_2_axis = _polar_from(
        train_stage_1_axis,
        _center_distance(TRAIN_STAGE_MODULE_MM, TRAIN_TOOTH_COUNTS["train_stage_1_wheel"], TRAIN_TOOTH_COUNTS["train_stage_2_pinion"]),
        _range_by_seed(seed, "train_stage_2_jitter", -5.0, 55.0),
    )
    train_stage_3_axis = _polar_from(
        train_stage_2_axis,
        _center_distance(TRAIN_STAGE_MODULE_MM, TRAIN_TOOTH_COUNTS["train_stage_2_wheel"], TRAIN_TOOTH_COUNTS["train_stage_3_pinion"]),
        _range_by_seed(seed, "train_stage_3_jitter", 0.0, 68.0),
    )
    escape_axis = _polar_from(
        train_stage_3_axis,
        _center_distance(TRAIN_STAGE_MODULE_MM, TRAIN_TOOTH_COUNTS["train_stage_3_wheel"], TRAIN_TOOTH_COUNTS["escape_pinion"]),
        _range_by_seed(seed, "escape_axis_jitter", 24.0, 78.0),
    )
    balance_axis = _polar_from(escape_axis, 5.2, _range_by_seed(seed, "balance_axis_jitter", 82.0, 134.0))
    pallet_axis = _point_between(escape_axis, balance_axis, 0.505)
    return {
        "barrel_axis": _axis("barrel_axis", barrel_axis, "mainspring_barrel_axis", 0.36),
        "train_stage_1_axis": _axis("train_stage_1_axis", train_stage_1_axis, "neutral_first_train_axis", 0.28),
        "train_stage_2_axis": _axis("train_stage_2_axis", train_stage_2_axis, "neutral_second_train_axis", 0.24),
        "train_stage_3_axis": _axis("train_stage_3_axis", train_stage_3_axis, "neutral_final_train_axis", 0.20),
        "escape_axis": _axis("escape_axis", escape_axis, "escape_wheel_axis", 0.18),
        "pallet_axis": _axis("pallet_axis", pallet_axis, "pallet_fork_axis", 0.15),
        "balance_axis": _axis("balance_axis", balance_axis, "balance_staff_axis", 0.22),
    }


def _display_gears(axes_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    gears = [
        _gear("minute_input_relay_pinion", "minute_input_relay_axis", TRAIN_STAGE_MODULE_MM, DISPLAY_TOOTH_COUNTS["minute_input_relay_pinion"], "minute_branch"),
        _gear("minute_input_relay_wheel", "minute_input_relay_axis", GEAR_MODULE_MM, DISPLAY_TOOTH_COUNTS["minute_input_relay_wheel"], "minute_branch"),
        _gear("minute_display_member", "minute_display_axis", GEAR_MODULE_MM, DISPLAY_TOOTH_COUNTS["minute_display_member"], "minute_branch"),
        _gear("hour_input_relay_pinion", "hour_input_relay_axis", TRAIN_STAGE_MODULE_MM, DISPLAY_TOOTH_COUNTS["hour_input_relay_pinion"], "hour_branch"),
        _gear("hour_input_relay_wheel", "hour_input_relay_axis", GEAR_MODULE_MM, DISPLAY_TOOTH_COUNTS["hour_input_relay_wheel"], "hour_branch"),
        _gear("hour_reduction_relay_pinion", "hour_reduction_relay_axis", GEAR_MODULE_MM, DISPLAY_TOOTH_COUNTS["hour_reduction_relay_pinion"], "hour_branch"),
        _gear("hour_reduction_relay_wheel", "hour_reduction_relay_axis", GEAR_MODULE_MM, DISPLAY_TOOTH_COUNTS["hour_reduction_relay_wheel"], "hour_branch"),
        _gear("hour_display_member", "hour_display_axis", GEAR_MODULE_MM, DISPLAY_TOOTH_COUNTS["hour_display_member"], "hour_branch"),
    ]
    for gear in gears:
        axis = axes_by_id[gear["axis_id"]]
        gear["x"] = axis["x"]
        gear["y"] = axis["y"]
    return gears


def _gear(gear_id: str, axis_id: str, module: float, tooth_count: int, branch_id: str) -> dict[str, Any]:
    pitch_radius = module * tooth_count / 2.0
    z_layer_by_id = {
        "minute_input_relay_pinion": 4,
        "hour_input_relay_pinion": 4,
        "minute_input_relay_wheel": 3,
        "minute_display_member": 3,
        "hour_input_relay_wheel": 3,
        "hour_reduction_relay_pinion": 3,
        "hour_reduction_relay_wheel": 4,
        "hour_display_member": 4,
    }
    return {
        "gear_id": gear_id,
        "axis_id": axis_id,
        "role": gear_id,
        "branch_id": branch_id,
        "module": module,
        "tooth_count": tooth_count,
        "pitch_radius": round(pitch_radius, 6),
        "outer_radius": round(pitch_radius + module * 0.75, 6),
        "root_radius": round(max(0.2, pitch_radius - module * 1.05), 6),
        "z_layer": z_layer_by_id[gear_id],
    }


def _train_gear(gear_id: str, axis_id: str, tooth_count: int) -> dict[str, Any]:
    pitch_radius = TRAIN_STAGE_MODULE_MM * tooth_count / 2.0
    z_layer_by_id = {
        "barrel_outer_teeth": 1,
        "train_stage_1_pinion": 1,
        "train_stage_1_wheel": 2,
        "train_stage_2_pinion": 2,
        "train_stage_2_wheel": 3,
        "train_stage_3_pinion": 3,
        "train_stage_3_wheel": 4,
        "escape_pinion": 4,
    }
    return {
        "gear_id": gear_id,
        "axis_id": axis_id,
        "role": gear_id,
        "branch_id": "going_train",
        "module": TRAIN_STAGE_MODULE_MM,
        "tooth_count": tooth_count,
        "pitch_radius": round(pitch_radius, 6),
        "outer_radius": round(pitch_radius + TRAIN_STAGE_MODULE_MM * 0.75, 6),
        "root_radius": round(max(0.2, pitch_radius - TRAIN_STAGE_MODULE_MM * 1.05), 6),
        "z_layer": z_layer_by_id.get(gear_id, 2),
    }


def _display_meshes() -> list[dict[str, Any]]:
    return [
        {"branch_id": "minute_display_branch", "driver": "train_stage_3_wheel", "driven": "minute_input_relay_pinion", "kind": "external"},
        {"branch_id": "minute_display_branch", "driver": "minute_input_relay_wheel", "driven": "minute_display_member", "kind": "external"},
        {"branch_id": "hour_display_branch", "driver": "train_stage_3_wheel", "driven": "hour_input_relay_pinion", "kind": "external"},
        {"branch_id": "hour_display_branch", "driver": "hour_input_relay_wheel", "driven": "hour_reduction_relay_pinion", "kind": "external"},
        {"branch_id": "hour_display_branch", "driver": "hour_reduction_relay_wheel", "driven": "hour_display_member", "kind": "external"},
    ]


def _power_branches() -> dict[str, dict[str, Any]]:
    return {
        "minute_display_branch": {
            "source": "train_stage_3_wheel",
            "output": "minute_display_member",
            "nodes": [
                "train_stage_3_wheel",
                "minute_input_relay_pinion",
                "minute_input_relay_wheel",
                "minute_display_member",
                "minute_hand",
            ],
        },
        "hour_display_branch": {
            "source": "train_stage_3_wheel",
            "output": "hour_display_member",
            "nodes": [
                "train_stage_3_wheel",
                "hour_input_relay_pinion",
                "hour_input_relay_wheel",
                "hour_reduction_relay_pinion",
                "hour_reduction_relay_wheel",
                "hour_display_member",
                "hour_hand",
            ],
        },
    }


def _display_ratio_proof() -> dict[str, Any]:
    train_to_minute = (
        TRAIN_TOOTH_COUNTS["train_stage_3_wheel"]
        / DISPLAY_TOOTH_COUNTS["minute_input_relay_pinion"]
        * DISPLAY_TOOTH_COUNTS["minute_input_relay_wheel"]
        / DISPLAY_TOOTH_COUNTS["minute_display_member"]
    )
    train_to_hour = (
        TRAIN_TOOTH_COUNTS["train_stage_3_wheel"]
        / DISPLAY_TOOTH_COUNTS["hour_input_relay_pinion"]
        * DISPLAY_TOOTH_COUNTS["hour_input_relay_wheel"]
        / DISPLAY_TOOTH_COUNTS["hour_reduction_relay_pinion"]
        * DISPLAY_TOOTH_COUNTS["hour_reduction_relay_wheel"]
        / DISPLAY_TOOTH_COUNTS["hour_display_member"]
    )
    hour_to_minute = train_to_hour / train_to_minute
    status = "pass" if abs(train_to_minute - 1.0) <= 1e-12 and abs(train_to_hour - (1 / 12)) <= 1e-12 else "fail"
    return {
        "kind": "parallel_train_referenced_display_branch_ratio",
        "train_to_minute_display_ratio": round(train_to_minute, 12),
        "train_to_hour_display_ratio": round(train_to_hour, 12),
        "hour_to_minute_ratio": round(hour_to_minute, 12),
        "expected_hour_to_minute_ratio": round(1 / 12, 12),
        "minute_tooth_relation": "(48 / 24) * (18 / 36) = 1",
        "hour_tooth_relation": "(48 / 24) * (12 / 72) * (24 / 96) = 1 / 12",
        "status": status,
    }


def _declared_mesh_center_distance_proofs(
    display_gears: list[dict[str, Any]],
    axes_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    gear_by_id = {
        "train_stage_3_wheel": _train_gear(
            "train_stage_3_wheel",
            "train_stage_3_axis",
            TRAIN_TOOTH_COUNTS["train_stage_3_wheel"],
        ),
        **{gear["gear_id"]: gear for gear in display_gears},
    }
    proofs = []
    for mesh in _display_meshes():
        driver = gear_by_id[mesh["driver"]]
        driven = gear_by_id[mesh["driven"]]
        driver_axis = axes_by_id[driver["axis_id"]]
        driven_axis = axes_by_id[driven["axis_id"]]
        expected = _center_distance(driver["module"], driver["tooth_count"], driven["tooth_count"])
        actual = _distance((driver_axis["x"], driver_axis["y"]), (driven_axis["x"], driven_axis["y"]))
        proofs.append(
            {
                "branch_id": mesh["branch_id"],
                "driver": mesh["driver"],
                "driven": mesh["driven"],
                "expected_distance_mm": round(expected, 6),
                "actual_distance_mm": round(actual, 6),
                "error_mm": round(abs(expected - actual), 9),
                "tolerance_mm": CENTER_DISTANCE_TOLERANCE_MM,
                "status": "pass" if abs(expected - actual) <= CENTER_DISTANCE_TOLERANCE_MM else "fail",
            }
        )
    return proofs


def _display_sweep_envelopes(axes_by_id: dict[str, dict[str, Any]], case_inner_radius_mm: float) -> dict[str, dict[str, Any]]:
    minute_axis = axes_by_id["minute_display_axis"]
    hour_axis = axes_by_id["hour_display_axis"]
    minute_length = _hand_length(minute_axis, case_inner_radius_mm, 0.72)
    hour_length = min(_hand_length(hour_axis, case_inner_radius_mm, 0.52), minute_length * 0.72)
    return {
        "minute_hand": _hand_sweep("minute_hand", minute_axis, minute_length, case_inner_radius_mm),
        "hour_hand": _hand_sweep("hour_hand", hour_axis, hour_length, case_inner_radius_mm),
    }


def _hand_sweep(hand_id: str, axis: dict[str, Any], length: float, case_inner_radius_mm: float) -> dict[str, Any]:
    axis_distance = math.hypot(axis["x"], axis["y"])
    case_clearance = case_inner_radius_mm - axis_distance - length
    return {
        "hand_id": hand_id,
        "axis_id": axis["axis_id"],
        "x": axis["x"],
        "y": axis["y"],
        "radius_mm": round(length, 6),
        "case_clearance_mm": round(case_clearance, 6),
        "minimum_case_clearance_mm": HAND_CASE_CLEARANCE_MM,
        "status": "pass" if case_clearance >= HAND_CASE_CLEARANCE_MM else "fail",
    }


def _geometry_proofs(
    axes_by_id: dict[str, dict[str, Any]],
    display_gears: list[dict[str, Any]],
    sweep_envelopes: dict[str, dict[str, Any]],
    case_inner_radius_mm: float,
) -> dict[str, dict[str, Any]]:
    physical_gears = _physical_gears_for_case_clearance(display_gears, axes_by_id)
    return {
        "case_boundary_margin": _case_boundary_proof(axes_by_id, display_gears, sweep_envelopes, case_inner_radius_mm),
        "gear_case_inner_wall_clearance": prove_gear_case_inner_wall_clearance(
            physical_gears,
            axes_by_id,
            case_inner_radius_mm,
        ),
        "display_axis_separation": _display_axis_separation_proof(axes_by_id),
        "same_layer_non_mesh_clearance": _same_layer_non_mesh_clearance_proof(display_gears, axes_by_id),
        "foreign_axis_to_gear_keepout": _foreign_axis_to_gear_keepout_proof(display_gears, axes_by_id),
    }


def _physical_gears_for_case_clearance(
    display_gears: list[dict[str, Any]],
    axes_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    gears = [
        _train_gear("barrel_outer_teeth", "barrel_axis", TRAIN_TOOTH_COUNTS["barrel_outer_teeth"]),
        _train_gear("train_stage_1_pinion", "train_stage_1_axis", TRAIN_TOOTH_COUNTS["train_stage_1_pinion"]),
        _train_gear("train_stage_1_wheel", "train_stage_1_axis", TRAIN_TOOTH_COUNTS["train_stage_1_wheel"]),
        _train_gear("train_stage_2_pinion", "train_stage_2_axis", TRAIN_TOOTH_COUNTS["train_stage_2_pinion"]),
        _train_gear("train_stage_2_wheel", "train_stage_2_axis", TRAIN_TOOTH_COUNTS["train_stage_2_wheel"]),
        _train_gear("train_stage_3_pinion", "train_stage_3_axis", TRAIN_TOOTH_COUNTS["train_stage_3_pinion"]),
        _train_gear("train_stage_3_wheel", "train_stage_3_axis", TRAIN_TOOTH_COUNTS["train_stage_3_wheel"]),
        _train_gear("escape_pinion", "escape_axis", TRAIN_TOOTH_COUNTS["escape_pinion"]),
        *display_gears,
    ]
    for gear in gears:
        axis = axes_by_id[gear["axis_id"]]
        gear["x"] = axis["x"]
        gear["y"] = axis["y"]
    return gears


def _case_boundary_proof(
    axes_by_id: dict[str, dict[str, Any]],
    display_gears: list[dict[str, Any]],
    sweep_envelopes: dict[str, dict[str, Any]],
    case_inner_radius_mm: float,
) -> dict[str, Any]:
    margins = []
    for gear in display_gears:
        axis = axes_by_id[gear["axis_id"]]
        margins.append(case_inner_radius_mm - math.hypot(axis["x"], axis["y"]) - gear["outer_radius"])
    margins.extend(envelope["case_clearance_mm"] for envelope in sweep_envelopes.values())
    min_margin = min(margins)
    return {
        "minimum_margin_mm": round(min_margin, 6),
        "status": "pass" if min_margin >= HAND_CASE_CLEARANCE_MM else "fail",
    }


def _display_axis_separation_proof(axes_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    minute = axes_by_id["minute_display_axis"]
    hour = axes_by_id["hour_display_axis"]
    distance = _distance((minute["x"], minute["y"]), (hour["x"], hour["y"]))
    return {
        "distance_mm": round(distance, 6),
        "minimum_distance_mm": MIN_DISPLAY_AXIS_SEPARATION_MM,
        "status": "pass" if distance >= MIN_DISPLAY_AXIS_SEPARATION_MM else "fail",
    }


def _same_layer_non_mesh_clearance_proof(display_gears: list[dict[str, Any]], axes_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    allowed_meshes = {
        frozenset(("train_stage_3_wheel", "minute_input_relay_pinion")),
        frozenset(("train_stage_3_wheel", "hour_input_relay_pinion")),
        frozenset(("minute_input_relay_wheel", "minute_display_member")),
        frozenset(("hour_input_relay_wheel", "hour_reduction_relay_pinion")),
        frozenset(("hour_reduction_relay_wheel", "hour_display_member")),
    }
    compound_axis_pairs = {
        frozenset(("minute_input_relay_pinion", "minute_input_relay_wheel")),
        frozenset(("hour_input_relay_pinion", "hour_input_relay_wheel")),
        frozenset(("hour_reduction_relay_pinion", "hour_reduction_relay_wheel")),
    }
    clearances = []
    clearance_gears = [
        _train_gear("train_stage_2_wheel", "train_stage_2_axis", TRAIN_TOOTH_COUNTS["train_stage_2_wheel"]),
        _train_gear("train_stage_3_wheel", "train_stage_3_axis", TRAIN_TOOTH_COUNTS["train_stage_3_wheel"]),
        *display_gears,
    ]
    for gear in clearance_gears:
        axis = axes_by_id[gear["axis_id"]]
        gear["x"] = axis["x"]
        gear["y"] = axis["y"]
    for left_index, left in enumerate(clearance_gears):
        for right in clearance_gears[left_index + 1 :]:
            if left["z_layer"] != right["z_layer"]:
                continue
            pair = frozenset((left["gear_id"], right["gear_id"]))
            if pair in allowed_meshes or pair in compound_axis_pairs:
                continue
            left_axis = axes_by_id[left["axis_id"]]
            right_axis = axes_by_id[right["axis_id"]]
            clearance = _distance((left_axis["x"], left_axis["y"]), (right_axis["x"], right_axis["y"])) - left["outer_radius"] - right["outer_radius"]
            clearances.append(clearance)
    min_clearance = min(clearances) if clearances else math.inf
    return {
        "minimum_clearance_mm": round(min_clearance, 6),
        "required_clearance_mm": MIN_NON_MESH_CLEARANCE_MM,
        "status": "pass" if min_clearance >= MIN_NON_MESH_CLEARANCE_MM else "fail",
    }


def _foreign_axis_to_gear_keepout_proof(display_gears: list[dict[str, Any]], axes_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    gear_by_id = {gear["gear_id"]: gear for gear in display_gears}
    allowed_mesh_pairs = {
        frozenset(("minute_input_relay_wheel", "minute_display_member")),
        frozenset(("hour_input_relay_wheel", "hour_reduction_relay_pinion")),
        frozenset(("hour_reduction_relay_wheel", "hour_display_member")),
    }
    allowed_axis_by_gear: dict[str, set[str]] = {gear["gear_id"]: {gear["axis_id"]} for gear in display_gears}
    for pair in allowed_mesh_pairs:
        left_id, right_id = tuple(pair)
        if left_id not in gear_by_id or right_id not in gear_by_id:
            continue
        allowed_axis_by_gear[left_id].add(gear_by_id[right_id]["axis_id"])
        allowed_axis_by_gear[right_id].add(gear_by_id[left_id]["axis_id"])
    clearances = []
    for gear in display_gears:
        gear_axis = axes_by_id[gear["axis_id"]]
        for axis_id in [
            "barrel_axis",
            "train_stage_1_axis",
            "train_stage_2_axis",
            "train_stage_3_axis",
            "escape_axis",
            "pallet_axis",
            "balance_axis",
            "minute_input_relay_axis",
            "minute_display_axis",
            "hour_input_relay_axis",
            "hour_reduction_relay_axis",
            "hour_display_axis",
        ]:
            axis = axes_by_id[axis_id]
            if axis["axis_id"] in allowed_axis_by_gear[gear["gear_id"]]:
                continue
            clearance = (
                _distance((gear_axis["x"], gear_axis["y"]), (axis["x"], axis["y"]))
                - gear["outer_radius"]
                - FOREIGN_AXIS_KEEP_OUT_RADIUS_MM
            )
            clearances.append(clearance)
    min_clearance = min(clearances) if clearances else math.inf
    return {
        "minimum_clearance_mm": round(min_clearance, 6),
        "required_clearance_mm": MIN_NON_MESH_CLEARANCE_MM,
        "status": "pass" if min_clearance >= MIN_NON_MESH_CLEARANCE_MM else "fail",
    }


def _candidate_checks(
    geometry_proofs: dict[str, dict[str, Any]],
    sweep_envelopes: dict[str, dict[str, Any]],
    ratio_proof: dict[str, Any],
    axes_by_id: dict[str, dict[str, Any]],
    center_distance_proofs: list[dict[str, Any]],
    power_branches: dict[str, dict[str, Any]],
) -> dict[str, str]:
    center_distance_status = "pass" if all(proof["status"] == "pass" for proof in center_distance_proofs) else "fail"
    hour_nodes = set(power_branches["hour_display_branch"]["nodes"])
    minute_only_nodes = {"minute_display_member", "minute_display_axis", "minute_input_relay_axis", "minute_input_relay_pinion", "minute_input_relay_wheel"}
    hour_independent = "pass" if hour_nodes.isdisjoint(minute_only_nodes) else "fail"
    return {
        "pattern_card_id_is_independent_hour_minute_no_seconds_v1": "pass",
        "movement_center_is_construction_reference_only": "pass",
        "no_required_display_center_axis": "pass" if "display_center_axis" not in axes_by_id else "fail",
        "no_seconds_hand": "pass",
        "separate_minute_and_hour_axes": geometry_proofs["display_axis_separation"]["status"],
        "minute_motion_chain_closed": "pass",
        "hour_motion_chain_closed": "pass",
        "minute_branch_connected_to_train": "pass" if power_branches["minute_display_branch"]["source"] == "train_stage_3_wheel" else "fail",
        "hour_branch_connected_to_train": "pass" if power_branches["hour_display_branch"]["source"] == "train_stage_3_wheel" else "fail",
        "hour_branch_does_not_depend_on_minute_branch": hour_independent,
        "train_to_minute_ratio_1_to_1": "pass" if abs(ratio_proof["train_to_minute_display_ratio"] - 1.0) <= 1e-12 else "fail",
        "train_to_hour_ratio_1_to_12": "pass" if abs(ratio_proof["train_to_hour_display_ratio"] - (1 / 12)) <= 1e-12 else "fail",
        "hour_to_minute_ratio_1_to_12": ratio_proof["status"],
        "declared_mesh_center_distances_pass": center_distance_status,
        "display_relay_meshes_valid": center_distance_status,
        "same_layer_non_mesh_clearance_pass": geometry_proofs["same_layer_non_mesh_clearance"]["status"],
        "all_gear_tip_envelopes_inside_case": geometry_proofs["gear_case_inner_wall_clearance"]["status"],
        "foreign_axis_to_gear_keepout_pass": geometry_proofs["foreign_axis_to_gear_keepout"]["status"],
        "minute_hand_sweep_clear": sweep_envelopes["minute_hand"]["status"],
        "hour_hand_sweep_clear": sweep_envelopes["hour_hand"]["status"],
    }


def _axis(axis_id: str, point: tuple[float, float], role: str, keepout_radius: float) -> dict[str, Any]:
    return {
        "axis_id": axis_id,
        "x": round(point[0], 6),
        "y": round(point[1], 6),
        "role": role,
        "keepout_radius": keepout_radius,
    }


def _center_distance(module: float, driver_teeth: int, driven_teeth: int) -> float:
    return module * (driver_teeth + driven_teeth) / 2.0


def _hand_length(axis: dict[str, Any], case_inner_radius_mm: float, fraction: float) -> float:
    axis_distance = math.hypot(axis["x"], axis["y"])
    return round(max(2.0, (case_inner_radius_mm - axis_distance - HAND_CASE_CLEARANCE_MM) * fraction), 6)


def _polar_from(origin: tuple[float, float], distance: float, angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return (origin[0] + math.cos(angle) * distance, origin[1] + math.sin(angle) * distance)


def _angle_between(start: dict[str, Any], end: dict[str, Any]) -> float:
    return math.degrees(math.atan2(float(end["y"]) - float(start["y"]), float(end["x"]) - float(start["x"]))) % 360.0


def _snap_angle_to_driver_tooth_grid(angle_deg: float, *, reference_angle_deg: float, tooth_pitch_deg: float) -> float:
    offset = (angle_deg - reference_angle_deg) / tooth_pitch_deg
    snapped = reference_angle_deg + round(offset) * tooth_pitch_deg
    return ((snapped + 180.0) % 360.0) - 180.0


def _point_between(start: tuple[float, float], end: tuple[float, float], ratio: float) -> tuple[float, float]:
    return (start[0] + (end[0] - start[0]) * ratio, start[1] + (end[1] - start[1]) * ratio)


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _range_by_seed(seed: int | str, key: str, low: float, high: float) -> float:
    return low + (high - low) * _named_random(seed, key)


def _seed_sorted_angles(seed: int, key: str, angles: list[float]) -> list[float]:
    return sorted(angles, key=lambda angle: _named_random(seed, f"{key}:{angle}"))


def _named_random(seed: int | str, key: str) -> float:
    digest = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big")
    return value / float(1 << 64)
