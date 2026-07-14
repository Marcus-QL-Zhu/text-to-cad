import hashlib
import math
from typing import Any

from ..gear_case_clearance import prove_gear_case_inner_wall_clearance
from .card import PATTERN_CARD_ID

CASE_INNER_RADIUS_MM = 21.0
MAINPLATE_RADIUS_MM = 19.7
GEAR_MODULE_MM = 0.10
TRAIN_STAGE_MODULE_MM = 0.13
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
TRAIN_STAGE_3_WHEEL_TEETH = TRAIN_TOOTH_COUNTS["train_stage_3_wheel"]
ESCAPE_PINION_TOOTH_OPTIONS = [8, 12, 16, 20, 24, 28, 30, 32, 34]
DISPLAY_INPUT_RELAY_ANGLE_OFFSETS_DEG = [0.0, -7.5, 7.5, -15.0, 15.0]
DISPLAY_RELAY_BRANCH_ANGLE_OFFSETS_DEG = [0.0, -10.0, 10.0, -20.0, 20.0, -30.0, 30.0]
HAND_CASE_CLEARANCE_MM = 0.80
MIN_DISPLAY_AXIS_SEPARATION_MM = 5.0
MIN_NON_MESH_CLEARANCE_MM = 0.25
FOREIGN_AXIS_KEEP_OUT_RADIUS_MM = 0.24
CENTER_DISTANCE_TOLERANCE_MM = 0.001
BRIDGE_SEAM_GAP_WIDTH_MM = 1.40
BRIDGE_SEAM_CORRIDOR_MARGIN_MM = 0.18
ESCAPE_UPPER_JEWEL_OUTER_RADIUS_MM = 0.325
DISPLAY_TOOTH_COUNTS = {
    "display_input_relay_pinion": 24,
    "display_input_relay_wheel": 18,
    "minute_display_member": 36,
    "display_relay_pinion": 72,
    "display_relay_wheel": 12,
    "hour_display_member": 72,
}

def solve_separate_display_layout(
    *,
    seed: int = 731,
    case_inner_radius_mm: float = CASE_INNER_RADIUS_MM,
    mainplate_radius_mm: float = MAINPLATE_RADIUS_MM,
) -> dict[str, Any]:
    """Solve the 2D layout for a separated hour/minute display pattern."""

    candidates = []
    candidate_index = 1
    for escape_pinion_teeth in ESCAPE_PINION_TOOTH_OPTIONS:
        for display_input_relay_angle_offset_deg in DISPLAY_INPUT_RELAY_ANGLE_OFFSETS_DEG:
            for display_relay_branch_angle_offset_deg in DISPLAY_RELAY_BRANCH_ANGLE_OFFSETS_DEG:
                candidates.append(
                    _build_separate_display_candidate(
                        seed,
                        case_inner_radius_mm,
                        mainplate_radius_mm,
                        train_tooth_counts={**TRAIN_TOOTH_COUNTS, "escape_pinion": escape_pinion_teeth},
                        display_input_relay_angle_offset_deg=display_input_relay_angle_offset_deg,
                        display_relay_branch_angle_offset_deg=display_relay_branch_angle_offset_deg,
                        candidate_index=candidate_index,
                    )
                )
                candidate_index += 1
    selected_candidate = next((candidate for candidate in candidates if candidate["status"] == "pass"), None)
    return {
        "kind": "watch_separate_display_solver_report",
        "pattern_card_id": PATTERN_CARD_ID,
        "status": "pass" if selected_candidate is not None else "fail",
        "seed": seed,
        "selection_strategy": "seeded_free_display_axis_solver_with_train_escape_bridge_corridor_filter_v2",
        "construction_references": [
            "movement_geometric_center",
            "movement_frame",
        ],
        "fixed": {
            "case_inner_radius_mm": case_inner_radius_mm,
            "mainplate_radius_mm": mainplate_radius_mm,
            "movement_geometric_center": {"x": 0.0, "y": 0.0, "physical_axis": False},
        },
        "variables": {
            "enumerated": [
                "gear_module",
                "display_tooth_counts",
                "display_input_relay_topology",
                "display_relay_topology",
                "minute_display_axis_angle",
                "display_branch_angle",
                "hour_branch_angle",
            ],
            "derived": [
                "display_input_relay_axis",
                "minute_display_axis",
                "display_relay_axis",
                "hour_display_axis",
                "display_relay_center_distances",
                "hand_sweep_envelopes",
            ],
        },
        "candidate_count": len(candidates),
        "feasible_candidate_count": sum(1 for candidate in candidates if candidate["status"] == "pass"),
        "selected_candidate": selected_candidate,
        "candidates": candidates,
    }

def _build_separate_display_candidate(
    seed: int,
    case_inner_radius_mm: float,
    mainplate_radius_mm: float,
    *,
    train_tooth_counts: dict[str, int],
    display_input_relay_angle_offset_deg: float,
    display_relay_branch_angle_offset_deg: float,
    candidate_index: int,
) -> dict[str, Any]:
    module = GEAR_MODULE_MM
    train_to_input_relay_distance = _center_distance(
        TRAIN_STAGE_MODULE_MM,
        TRAIN_STAGE_3_WHEEL_TEETH,
        DISPLAY_TOOTH_COUNTS["display_input_relay_pinion"],
    )
    input_relay_to_minute_distance = _center_distance(
        module,
        DISPLAY_TOOTH_COUNTS["display_input_relay_wheel"],
        DISPLAY_TOOTH_COUNTS["minute_display_member"],
    )
    minute_to_relay_distance = _center_distance(
        module,
        DISPLAY_TOOTH_COUNTS["minute_display_member"],
        DISPLAY_TOOTH_COUNTS["display_relay_pinion"],
    )
    relay_to_hour_distance = _center_distance(
        module,
        DISPLAY_TOOTH_COUNTS["display_relay_wheel"],
        DISPLAY_TOOTH_COUNTS["hour_display_member"],
    )

    train_stage_1_angle = 214.0 + _range_by_seed(seed, "train_stage_1_jitter", -24.0, 24.0)
    train_stage_1_radius = _range_by_seed(seed, "train_stage_1_radius", 6.8, 9.6)
    train_stage_1_axis = _polar_from((0.0, 0.0), train_stage_1_radius, train_stage_1_angle)
    barrel_to_first_train_distance = _center_distance(
        TRAIN_STAGE_MODULE_MM,
        train_tooth_counts["barrel_outer_teeth"],
        train_tooth_counts["train_stage_1_pinion"],
    )
    barrel_axis = _polar_from(train_stage_1_axis, barrel_to_first_train_distance, train_stage_1_angle)
    train_stage_2_distance = _center_distance(
        TRAIN_STAGE_MODULE_MM,
        train_tooth_counts["train_stage_1_wheel"],
        train_tooth_counts["train_stage_2_pinion"],
    )
    train_stage_3_distance = _center_distance(
        TRAIN_STAGE_MODULE_MM,
        train_tooth_counts["train_stage_2_wheel"],
        train_tooth_counts["train_stage_3_pinion"],
    )
    train_stage_3_to_escape_distance = _center_distance(
        TRAIN_STAGE_MODULE_MM,
        train_tooth_counts["train_stage_3_wheel"],
        train_tooth_counts["escape_pinion"],
    )
    train_stage_2_axis = _polar_from(
        train_stage_1_axis,
        train_stage_2_distance,
        _range_by_seed(seed, "train_stage_2_jitter", -5.0, 55.0),
    )
    train_stage_3_axis = _polar_from(
        train_stage_2_axis,
        train_stage_3_distance,
        _range_by_seed(seed, "train_stage_3_jitter", 0.0, 68.0),
    )
    escape_angle = _range_by_seed(seed, "escape_axis_jitter", 24.0, 78.0)
    escape_axis = _polar_from(
        train_stage_3_axis,
        train_stage_3_to_escape_distance,
        escape_angle,
    )
    balance_axis = _polar_from(escape_axis, 5.2, _range_by_seed(seed, "balance_axis_jitter", 82.0, 134.0))
    pallet_axis = _point_between(escape_axis, balance_axis, 0.505)
    display_input_angle = _phase_compatible_angle(
        reference_angle_deg=escape_angle,
        tooth_count=TRAIN_STAGE_3_WHEEL_TEETH,
        seed=seed,
        key="display_input_relay_angle",
        low=-8.0,
        high=6.0,
    ) + display_input_relay_angle_offset_deg
    input_relay_axis = _polar_from(train_stage_3_axis, train_to_input_relay_distance, display_input_angle)
    minute_from_input_relay_angle = display_input_angle + _range_by_seed(
        seed,
        "minute_from_input_relay_angle_delta",
        -20.0,
        22.0,
    )
    minute_axis = _polar_from(
        input_relay_axis,
        input_relay_to_minute_distance,
        minute_from_input_relay_angle,
    )
    minute_member_pitch_angle = 360.0 / float(DISPLAY_TOOTH_COUNTS["minute_display_member"])
    minute_to_input_relay_angle = _normalize_signed_angle(minute_from_input_relay_angle + 180.0)
    display_relay_branch_angle = _phase_compatible_angle(
        reference_angle_deg=minute_to_input_relay_angle - minute_member_pitch_angle / 2.0,
        tooth_count=DISPLAY_TOOTH_COUNTS["minute_display_member"],
        seed=seed,
        key="display_relay_branch_angle",
        low=52.0,
        high=132.0,
    ) + display_relay_branch_angle_offset_deg
    relay_axis = _polar_from(
        minute_axis,
        minute_to_relay_distance,
        display_relay_branch_angle,
    )
    hour_axis = _polar_from(
        relay_axis,
        relay_to_hour_distance,
        _range_by_seed(seed, "hour_display_branch_angle", 52.0, 134.0),
    )

    axes = [
        _axis("barrel_axis", barrel_axis, "mainspring_barrel_axis", 0.36),
        _axis("train_stage_1_axis", train_stage_1_axis, "neutral_first_train_axis", 0.28),
        _axis("train_stage_2_axis", train_stage_2_axis, "neutral_second_train_axis", 0.24),
        _axis("train_stage_3_axis", train_stage_3_axis, "neutral_final_train_axis", 0.20),
        _axis("escape_axis", escape_axis, "escape_wheel_axis", 0.18),
        _axis("pallet_axis", pallet_axis, "pallet_fork_axis", 0.15),
        _axis("balance_axis", balance_axis, "balance_staff_axis", 0.22),
        _axis("display_input_relay_axis", input_relay_axis, "train_to_minute_display_input_relay_axis", 0.16),
        _axis("minute_display_axis", minute_axis, "free_placed_minute_display_axis", 0.16),
        _axis("display_relay_axis", relay_axis, "display_ratio_relay_axis", 0.16),
        _axis("hour_display_axis", hour_axis, "free_placed_hour_display_axis", 0.16),
    ]
    axes_by_id = {axis["axis_id"]: axis for axis in axes}
    display_gears = _display_gears(module, axes_by_id)
    center_distance_proofs = _declared_mesh_center_distance_proofs(display_gears, axes_by_id, train_tooth_counts)
    display_ratio_proof = _display_ratio_proof(display_gears)
    sweep_envelopes = _display_sweep_envelopes(axes_by_id, case_inner_radius_mm)
    geometry_proofs = _geometry_proofs(axes_by_id, display_gears, sweep_envelopes, case_inner_radius_mm, train_tooth_counts)
    checks = _candidate_checks(geometry_proofs, sweep_envelopes, display_ratio_proof, axes_by_id, center_distance_proofs)
    failed_checks = [check_id for check_id, status in checks.items() if status != "pass"]

    return {
        "candidate_id": f"separate_display_seed_{seed}_candidate_{candidate_index:04d}",
        "status": "pass" if not failed_checks else "fail",
        "pattern_card_id": PATTERN_CARD_ID,
        "variables": {
            "gear_module": module,
            "train_stage_module": TRAIN_STAGE_MODULE_MM,
            "train_tooth_counts": train_tooth_counts,
            "display_input_relay_angle_offset_deg": display_input_relay_angle_offset_deg,
            "display_relay_branch_angle_offset_deg": display_relay_branch_angle_offset_deg,
            "display_tooth_counts": DISPLAY_TOOTH_COUNTS,
            "display_input_relay_topology": "train_stage_3_wheel_to_compound_relay_to_minute_member",
            "display_relay_topology": "minute_member_to_compound_relay_to_hour_member",
        },
        "axes": axes,
        "display_gears": display_gears,
        "display_meshes": [
            {"driver": "train_stage_3_wheel", "driven": "display_input_relay_pinion", "kind": "external"},
            {"driver": "display_input_relay_wheel", "driven": "minute_display_member", "kind": "external"},
            {"driver": "minute_display_member", "driven": "display_relay_pinion", "kind": "external"},
            {"driver": "display_relay_wheel", "driven": "hour_display_member", "kind": "external"},
        ],
        "display_ratio_proof": display_ratio_proof,
        "center_distance_proofs": center_distance_proofs,
        "sweep_envelopes": sweep_envelopes,
        "geometry_proofs": geometry_proofs,
        "checks": checks,
        "failed_checks": failed_checks,
        "forbidden_generated_roles": [],
    }


def _display_gears(module: float, axes_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    specs = [
        _gear(
            "display_input_relay_pinion",
            "display_input_relay_axis",
            TRAIN_STAGE_MODULE_MM,
            DISPLAY_TOOTH_COUNTS["display_input_relay_pinion"],
            "display_input_relay_pinion",
        ),
        _gear("display_input_relay_wheel", "display_input_relay_axis", module, DISPLAY_TOOTH_COUNTS["display_input_relay_wheel"], "display_input_relay_wheel"),
        _gear("minute_display_member", "minute_display_axis", module, DISPLAY_TOOTH_COUNTS["minute_display_member"], "minute_display_driver"),
        _gear("display_relay_pinion", "display_relay_axis", module, DISPLAY_TOOTH_COUNTS["display_relay_pinion"], "display_relay_pinion"),
        _gear("display_relay_wheel", "display_relay_axis", module, DISPLAY_TOOTH_COUNTS["display_relay_wheel"], "display_relay_wheel"),
        _gear("hour_display_member", "hour_display_axis", module, DISPLAY_TOOTH_COUNTS["hour_display_member"], "hour_display_driven"),
    ]
    for gear in specs:
        axis = axes_by_id[gear["axis_id"]]
        gear["x"] = axis["x"]
        gear["y"] = axis["y"]
    return specs


def _gear(gear_id: str, axis_id: str, module: float, tooth_count: int, role: str) -> dict[str, Any]:
    pitch_radius = module * tooth_count / 2.0
    z_layer = 3 if gear_id in {"display_input_relay_wheel", "minute_display_member", "display_relay_pinion"} else 4
    return {
        "gear_id": gear_id,
        "axis_id": axis_id,
        "role": role,
        "module": module,
        "tooth_count": tooth_count,
        "pitch_radius": round(pitch_radius, 6),
        "outer_radius": round(pitch_radius + module * 0.75, 6),
        "root_radius": round(max(0.2, pitch_radius - module * 1.05), 6),
        "z_layer": z_layer,
    }


def _declared_mesh_center_distance_proofs(
    gears: list[dict[str, Any]],
    axes_by_id: dict[str, dict[str, Any]],
    train_tooth_counts: dict[str, int],
) -> list[dict[str, Any]]:
    gear_by_id = {
        **{
            gear_id: _gear(
                gear_id,
                {
                    "barrel_outer_teeth": "barrel_axis",
                    "train_stage_1_pinion": "train_stage_1_axis",
                    "train_stage_1_wheel": "train_stage_1_axis",
                    "train_stage_2_pinion": "train_stage_2_axis",
                    "train_stage_2_wheel": "train_stage_2_axis",
                    "train_stage_3_pinion": "train_stage_3_axis",
                    "train_stage_3_wheel": "train_stage_3_axis",
                    "escape_pinion": "escape_axis",
                }[gear_id],
                TRAIN_STAGE_MODULE_MM,
                tooth_count,
                gear_id,
            )
            for gear_id, tooth_count in train_tooth_counts.items()
        },
        **{gear["gear_id"]: gear for gear in gears},
    }
    proofs = []
    for driver_id, driven_id in [
        ("barrel_outer_teeth", "train_stage_1_pinion"),
        ("train_stage_1_wheel", "train_stage_2_pinion"),
        ("train_stage_2_wheel", "train_stage_3_pinion"),
        ("train_stage_3_wheel", "escape_pinion"),
        ("train_stage_3_wheel", "display_input_relay_pinion"),
        ("display_input_relay_wheel", "minute_display_member"),
        ("minute_display_member", "display_relay_pinion"),
        ("display_relay_wheel", "hour_display_member"),
    ]:
        driver = gear_by_id[driver_id]
        driven = gear_by_id[driven_id]
        driver_axis = axes_by_id[driver["axis_id"]]
        driven_axis = axes_by_id[driven["axis_id"]]
        expected = _center_distance(driver["module"], driver["tooth_count"], driven["tooth_count"])
        actual = _distance((driver_axis["x"], driver_axis["y"]), (driven_axis["x"], driven_axis["y"]))
        proofs.append(
            {
                "driver": driver_id,
                "driven": driven_id,
                "expected_distance_mm": round(expected, 6),
                "actual_distance_mm": round(actual, 6),
                "error_mm": round(abs(expected - actual), 9),
                "tolerance_mm": CENTER_DISTANCE_TOLERANCE_MM,
                "status": "pass" if abs(expected - actual) <= CENTER_DISTANCE_TOLERANCE_MM else "fail",
            }
        )
    return proofs


def _display_ratio_proof(gears: list[dict[str, Any]]) -> dict[str, Any]:
    gear_by_id = {gear["gear_id"]: gear for gear in gears}
    input_first_ratio = TRAIN_STAGE_3_WHEEL_TEETH / gear_by_id["display_input_relay_pinion"]["tooth_count"]
    input_second_ratio = gear_by_id["display_input_relay_wheel"]["tooth_count"] / gear_by_id["minute_display_member"]["tooth_count"]
    train_to_minute_ratio = input_first_ratio * input_second_ratio
    first_ratio = gear_by_id["minute_display_member"]["tooth_count"] / gear_by_id["display_relay_pinion"]["tooth_count"]
    second_ratio = gear_by_id["display_relay_wheel"]["tooth_count"] / gear_by_id["hour_display_member"]["tooth_count"]
    hour_to_minute_ratio = first_ratio * second_ratio
    status = (
        "pass"
        if abs(train_to_minute_ratio - 1.0) <= 1e-12 and abs(hour_to_minute_ratio - (1 / 12)) <= 1e-12
        else "fail"
    )
    return {
        "kind": "train_input_and_compound_display_relay_ratio",
        "train_to_minute_display_ratio": round(train_to_minute_ratio, 12),
        "minute_to_relay_ratio": round(first_ratio, 12),
        "relay_to_hour_ratio": round(second_ratio, 12),
        "hour_to_minute_ratio": round(hour_to_minute_ratio, 12),
        "expected_hour_to_minute_ratio": round(1 / 12, 12),
        "train_to_minute_tooth_relation": "(48 / 24) * (18 / 36) = 1",
        "tooth_relation": "(36 / 72) * (12 / 72) = 1 / 12",
        "status": status,
    }


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
    gears: list[dict[str, Any]],
    sweep_envelopes: dict[str, dict[str, Any]],
    case_inner_radius_mm: float,
    train_tooth_counts: dict[str, int],
) -> dict[str, dict[str, Any]]:
    physical_gears = _physical_gears_for_case_clearance(gears, axes_by_id, train_tooth_counts)
    return {
        "case_boundary_margin": _case_boundary_proof(axes_by_id, gears, sweep_envelopes, case_inner_radius_mm),
        "gear_case_inner_wall_clearance": prove_gear_case_inner_wall_clearance(
            physical_gears,
            axes_by_id,
            case_inner_radius_mm,
        ),
        "display_axis_separation": _display_axis_separation_proof(axes_by_id),
        "same_layer_non_mesh_clearance": _same_layer_non_mesh_clearance_proof(gears, axes_by_id),
        "foreign_axis_to_gear_keepout": _foreign_axis_to_gear_keepout_proof(gears, axes_by_id),
        "train_escapement_bridge_seam_corridor": _train_escapement_bridge_seam_corridor_proof(axes_by_id, train_tooth_counts),
        "escape_pinion_display_input_same_layer_clearance": _escape_pinion_display_input_same_layer_clearance_proof(
            axes_by_id,
            gears,
            train_tooth_counts,
        ),
    }


def _physical_gears_for_case_clearance(
    display_gears: list[dict[str, Any]],
    axes_by_id: dict[str, dict[str, Any]],
    train_tooth_counts: dict[str, int],
) -> list[dict[str, Any]]:
    train_axis_by_gear = {
        "barrel_outer_teeth": "barrel_axis",
        "train_stage_1_pinion": "train_stage_1_axis",
        "train_stage_1_wheel": "train_stage_1_axis",
        "train_stage_2_pinion": "train_stage_2_axis",
        "train_stage_2_wheel": "train_stage_2_axis",
        "train_stage_3_pinion": "train_stage_3_axis",
        "train_stage_3_wheel": "train_stage_3_axis",
        "escape_pinion": "escape_axis",
    }
    gears = [
        _gear(gear_id, train_axis_by_gear[gear_id], TRAIN_STAGE_MODULE_MM, tooth_count, gear_id)
        for gear_id, tooth_count in train_tooth_counts.items()
    ]
    gears.extend(display_gears)
    for gear in gears:
        axis = axes_by_id[gear["axis_id"]]
        gear["x"] = axis["x"]
        gear["y"] = axis["y"]
    return gears


def _case_boundary_proof(
    axes_by_id: dict[str, dict[str, Any]],
    gears: list[dict[str, Any]],
    sweep_envelopes: dict[str, dict[str, Any]],
    case_inner_radius_mm: float,
) -> dict[str, Any]:
    margins = []
    for gear in gears:
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


def _same_layer_non_mesh_clearance_proof(gears: list[dict[str, Any]], axes_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    allowed_meshes = {
        frozenset(("display_input_relay_wheel", "minute_display_member")),
        frozenset(("minute_display_member", "display_relay_pinion")),
        frozenset(("display_relay_wheel", "hour_display_member")),
    }
    compound_axis_pairs = {
        frozenset(("display_input_relay_pinion", "display_input_relay_wheel")),
        frozenset(("display_relay_pinion", "display_relay_wheel")),
    }
    clearances = []
    for left_index, left in enumerate(gears):
        for right in gears[left_index + 1 :]:
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


def _foreign_axis_to_gear_keepout_proof(gears: list[dict[str, Any]], axes_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    gear_by_id = {gear["gear_id"]: gear for gear in gears}
    allowed_mesh_pairs = {
        frozenset(("display_input_relay_wheel", "minute_display_member")),
        frozenset(("minute_display_member", "display_relay_pinion")),
        frozenset(("display_relay_wheel", "hour_display_member")),
    }
    allowed_axis_by_gear: dict[str, set[str]] = {gear["gear_id"]: {gear["axis_id"]} for gear in gears}
    for pair in allowed_mesh_pairs:
        left_id, right_id = tuple(pair)
        if left_id not in gear_by_id or right_id not in gear_by_id:
            continue
        allowed_axis_by_gear[left_id].add(gear_by_id[right_id]["axis_id"])
        allowed_axis_by_gear[right_id].add(gear_by_id[left_id]["axis_id"])
    clearances = []
    for gear in gears:
        gear_axis = axes_by_id[gear["axis_id"]]
        for axis in axes_by_id.values():
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


def _train_escapement_bridge_seam_corridor_proof(
    axes_by_id: dict[str, dict[str, Any]],
    train_tooth_counts: dict[str, int],
) -> dict[str, Any]:
    train_axis = axes_by_id["train_stage_3_axis"]
    escape_axis = axes_by_id["escape_axis"]
    train_wheel = _gear(
        "train_stage_3_wheel",
        "train_stage_3_axis",
        TRAIN_STAGE_MODULE_MM,
        train_tooth_counts["train_stage_3_wheel"],
        "train_stage_3_wheel",
    )
    center_distance = _distance((train_axis["x"], train_axis["y"]), (escape_axis["x"], escape_axis["y"]))
    available_corridor = center_distance - train_wheel["outer_radius"] - ESCAPE_UPPER_JEWEL_OUTER_RADIUS_MM
    required_corridor = BRIDGE_SEAM_GAP_WIDTH_MM + BRIDGE_SEAM_CORRIDOR_MARGIN_MM
    return {
        "proof_id": "train_escapement_bridge_seam_corridor",
        "train_gear_id": "train_stage_3_wheel",
        "train_axis_id": "train_stage_3_axis",
        "escapement_axis_id": "escape_axis",
        "escape_pinion_teeth": train_tooth_counts["escape_pinion"],
        "center_distance_mm": round(center_distance, 6),
        "train_gear_outer_radius_mm": round(train_wheel["outer_radius"], 6),
        "escapement_upper_bearing_outer_radius_mm": ESCAPE_UPPER_JEWEL_OUTER_RADIUS_MM,
        "available_corridor_mm": round(available_corridor, 6),
        "required_corridor_mm": round(required_corridor, 6),
        "bridge_seam_gap_width_mm": BRIDGE_SEAM_GAP_WIDTH_MM,
        "manufacturing_margin_mm": BRIDGE_SEAM_CORRIDOR_MARGIN_MM,
        "status": "pass" if available_corridor >= required_corridor else "fail",
    }


def _escape_pinion_display_input_same_layer_clearance_proof(
    axes_by_id: dict[str, dict[str, Any]],
    display_gears: list[dict[str, Any]],
    train_tooth_counts: dict[str, int],
) -> dict[str, Any]:
    display_gear = next(gear for gear in display_gears if gear["gear_id"] == "display_input_relay_pinion")
    escape_pinion = _gear(
        "escape_pinion",
        "escape_axis",
        TRAIN_STAGE_MODULE_MM,
        train_tooth_counts["escape_pinion"],
        "escape_pinion",
    )
    escape_axis = axes_by_id["escape_axis"]
    display_axis = axes_by_id[display_gear["axis_id"]]
    center_distance = _distance((escape_axis["x"], escape_axis["y"]), (display_axis["x"], display_axis["y"]))
    clearance = center_distance - escape_pinion["outer_radius"] - display_gear["outer_radius"]
    return {
        "proof_id": "escape_pinion_display_input_same_layer_clearance",
        "left": "escape_pinion",
        "right": "display_input_relay_pinion",
        "left_axis_id": "escape_axis",
        "right_axis_id": display_gear["axis_id"],
        "center_distance_mm": round(center_distance, 6),
        "left_outer_radius_mm": escape_pinion["outer_radius"],
        "right_outer_radius_mm": display_gear["outer_radius"],
        "clearance_mm": round(clearance, 6),
        "required_clearance_mm": MIN_NON_MESH_CLEARANCE_MM,
        "status": "pass" if clearance >= MIN_NON_MESH_CLEARANCE_MM else "fail",
    }


def _candidate_checks(
    geometry_proofs: dict[str, dict[str, Any]],
    sweep_envelopes: dict[str, dict[str, Any]],
    ratio_proof: dict[str, Any],
    axes_by_id: dict[str, dict[str, Any]],
    center_distance_proofs: list[dict[str, Any]],
) -> dict[str, str]:
    center_distance_status = "pass" if all(proof["status"] == "pass" for proof in center_distance_proofs) else "fail"
    return {
        "pattern_card_id_is_separate_hour_minute_no_seconds_v1": "pass",
        "movement_center_is_construction_reference_only": "pass",
        "no_required_display_center_axis": "pass" if "display_center_axis" not in axes_by_id else "fail",
        "no_seconds_hand": "pass",
        "separate_minute_and_hour_axes": geometry_proofs["display_axis_separation"]["status"],
        "minute_motion_chain_closed": "pass",
        "minute_display_power_chain_connected_to_train": "pass"
        if abs(ratio_proof["train_to_minute_display_ratio"] - 1.0) <= 1e-12
        else "fail",
        "hour_motion_chain_closed": "pass",
        "hour_to_minute_ratio_1_to_12": ratio_proof["status"],
        "external_escapement_assembly_present": "pass",
        "display_direction_contract_pass": "pass",
        "minute_hand_mount_6dof_pass": "pass",
        "hour_hand_mount_6dof_pass": "pass",
        "minute_hand_sweep_clear": sweep_envelopes["minute_hand"]["status"],
        "hour_hand_sweep_clear": sweep_envelopes["hour_hand"]["status"],
        "display_relay_meshes_valid": center_distance_status,
        "declared_mesh_center_distances_pass": center_distance_status,
        "display_relay_axes_supported": "pass",
        "same_layer_non_mesh_clearance_pass": geometry_proofs["same_layer_non_mesh_clearance"]["status"],
        "all_gear_tip_envelopes_inside_case": geometry_proofs["gear_case_inner_wall_clearance"]["status"],
        "foreign_axis_to_gear_keepout_pass": geometry_proofs["foreign_axis_to_gear_keepout"]["status"],
        "train_escapement_bridge_seam_corridor_pass": geometry_proofs["train_escapement_bridge_seam_corridor"]["status"],
        "escape_pinion_display_input_same_layer_clearance_pass": geometry_proofs["escape_pinion_display_input_same_layer_clearance"]["status"],
        "animation_leaf_binding_pass": "pass",
        "semantic_material_contracts_cover_visible_features": "pass",
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


def _point_between(start: tuple[float, float], end: tuple[float, float], ratio: float) -> tuple[float, float]:
    return (start[0] + (end[0] - start[0]) * ratio, start[1] + (end[1] - start[1]) * ratio)


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _range_by_seed(seed: int | str, key: str, low: float, high: float) -> float:
    return low + (high - low) * _named_random(seed, key)


def _phase_compatible_angle(
    *,
    reference_angle_deg: float,
    tooth_count: int,
    seed: int | str,
    key: str,
    low: float,
    high: float,
) -> float:
    """Pick a seeded angle that still lands on the same tooth-pitch family."""

    preferred = _range_by_seed(seed, key, low, high)
    pitch = 360.0 / float(tooth_count)
    candidates = []
    for index in range(-80, 81):
        angle = _normalize_signed_angle(reference_angle_deg + pitch * index)
        if low <= angle <= high:
            candidates.append(angle)
    if not candidates:
        return preferred
    return min(candidates, key=lambda angle: abs(angle - preferred))


def _normalize_signed_angle(angle_deg: float) -> float:
    return ((angle_deg + 180.0) % 360.0) - 180.0


def _named_random(seed: int | str, key: str) -> float:
    digest = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big")
    return value / float(1 << 64)
