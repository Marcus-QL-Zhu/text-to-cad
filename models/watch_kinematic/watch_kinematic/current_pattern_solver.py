"""Geometry solver for the current watch power-chain pattern.

This is the first synthesis layer between a pattern card and CAD generation.
It enumerates formula-backed candidates, filters infeasible layouts, and
returns the selected axis layout with validation evidence.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any


CURRENT_PATTERN_ID = "central_hour_minute_with_off_center_seconds_v1"
DEFAULT_CASE_INNER_RADIUS_MM = 22.0
DISPLAY_CENTER_AXIS = "display_center_axis"
BRIDGE_PERIMETER_SCREW_POLICY = {
    "policy_id": "provisional_sub_1mm_watch_bridge_screw",
    "basis": "reserve an outer service band for future bridge screw pads and raised standoffs before bridge CAD is generated",
    "thread_nominal_mm": 0.80,
    "head_or_counterbore_diameter_mm": 1.40,
    "outer_edge_wall_mm": 0.30,
    "inner_functional_clearance_mm": 0.30,
    "note": "M1.4 DIN 84-style screws have about 2.6 mm head diameter and would require a much wider band and a new solver pass.",
}
BRIDGE_Z_STACK_FASTENER_POLICY = {
    "policy_id": "m1_4_countersunk_bridge_plate_stack_v1",
    "standard": "DIN 965 / ISO 7046 countersunk flat head screw",
    "thread_size": "M1.4",
    "source": "supplier DIN 965 / ISO 7046 M1.4 countersunk screw dimensions",
    "countersunk_head_depth_mm": 0.90,
    "minimum_residual_material_below_countersink_mm": 0.30,
    "minimum_bridge_plate_thickness_mm": 1.20,
    "gear_to_bridge_bottom_clearance_mm": 0.25,
    "support_face_to_service_step_split": [2, 1],
    "basis": "bridge plate thickness is driven by countersink depth plus residual material; remaining height below bridge bottom is split 2/3 support face and 1/3 service step",
}
BRIDGE_PERIMETER_RESERVED_BAND_MM = round(
    BRIDGE_PERIMETER_SCREW_POLICY["outer_edge_wall_mm"]
    + BRIDGE_PERIMETER_SCREW_POLICY["head_or_counterbore_diameter_mm"]
    + BRIDGE_PERIMETER_SCREW_POLICY["inner_functional_clearance_mm"],
    6,
)
REQUIRED_AXIS_IDS = (
    DISPLAY_CENTER_AXIS,
    "minute_work_axis",
    "barrel_axis",
    "center_axis",
    "third_axis",
    "fourth_axis",
    "escape_axis",
    "pallet_axis",
    "balance_axis",
)
GEOMETRY_EQUATIONS = [
    "center_distance = module * (driver_teeth + driven_teeth) / 2",
    "axis_next = axis_previous + polar(center_distance, selected_angle)",
    "minute_work_axis = display_center_axis + polar(display_motion_center_distance, minute_work_angle)",
    "external_escapement_balance_axis = escape_axis + polar(source_scaled_escape_to_balance_distance, balance_angle)",
    "gear_pitch_radius = module * tooth_count / 2",
    "case_boundary_margin = case_inner_radius - (axis_distance_from_origin + entity_outer_radius)",
    "bridge_perimeter_service_margin = case_inner_radius - (axis_distance_from_origin + entity_outer_radius)",
    "bridge_perimeter_service_margin >= bridge_perimeter_reserved_band",
    "through_axis_clearance = distance(foreign_axis, gear_axis) - gear_outer_radius - shaft_keepout_radius",
    "bridge_plate_thickness = countersunk_head_depth + minimum_residual_material_below_countersink",
    "bridge_bottom_z = highest_gear_top_z + gear_to_bridge_bottom_clearance",
    "support_face_height : service_step_height = 2 : 1 below bridge bottom",
]
DEFAULT_TOOTH_COUNTS = {
    "barrel_outer_teeth": 80,
    "center_pinion": 10,
    "center_wheel": 64,
    "third_pinion": 8,
    "third_wheel": 60,
    "fourth_pinion": 8,
    "fourth_wheel": 56,
    "escape_pinion": 7,
    "escape_wheel": 15,
    "cannon_pinion_display_driver": 16,
    "minute_wheel": 64,
    "minute_pinion": 20,
    "hour_wheel": 60,
}
GEAR_AXIS_STRUCTURE_FAMILIES = {
    "baseline_diagonal": {
        "minute_work_angle_deg": 143.0,
        "barrel_angle_deg": 210.0,
        "third_angle_deg": 9.0,
        "fourth_angle_deg": -6.0,
        "escape_angle_deg": 31.0,
        "balance_angle_deg": 114.0,
    },
    "lower_train_sweep": {
        "minute_work_angle_deg": 111.0,
        "barrel_angle_deg": 193.0,
        "third_angle_deg": -51.0,
        "fourth_angle_deg": 17.0,
        "escape_angle_deg": 17.0,
        "balance_angle_deg": 88.0,
    },
    "upper_arc_sweep": {
        "minute_work_angle_deg": 176.0,
        "barrel_angle_deg": 251.0,
        "third_angle_deg": -1.0,
        "fourth_angle_deg": 39.0,
        "escape_angle_deg": 67.0,
        "balance_angle_deg": 116.0,
    },
    "high_escape_sweep": {
        "minute_work_angle_deg": 129.0,
        "barrel_angle_deg": 195.0,
        "third_angle_deg": -8.0,
        "fourth_angle_deg": 63.0,
        "escape_angle_deg": 87.0,
        "balance_angle_deg": 101.0,
    },
    "low_escape_sweep": {
        "minute_work_angle_deg": 156.0,
        "barrel_angle_deg": 228.0,
        "third_angle_deg": -20.0,
        "fourth_angle_deg": -40.0,
        "escape_angle_deg": -19.0,
        "balance_angle_deg": 63.0,
    },
}
DISPLAY_TOOTH_COUNT_SETS = {
    "standard_16_64_20_60": {
        "cannon_pinion_display_driver": 16,
        "minute_wheel": 64,
        "minute_pinion": 20,
        "hour_wheel": 60,
    },
    "wide_clearance_10_100_50_60": {
        "cannon_pinion_display_driver": 10,
        "minute_wheel": 100,
        "minute_pinion": 50,
        "hour_wheel": 60,
    },
}

POWER_MESHES = (
    ("barrel_outer_teeth", "center_pinion"),
    ("center_wheel", "third_pinion"),
    ("third_wheel", "fourth_pinion"),
    ("fourth_wheel", "escape_pinion"),
)
DISPLAY_MESHES = (
    ("cannon_pinion_display_driver", "minute_wheel"),
    ("minute_pinion", "hour_wheel"),
)
EXTERNAL_ESCAPEMENT_SOURCE_ESCAPE_TO_BALANCE_MM = 89.06
EXTERNAL_ESCAPEMENT_TARGET_ESCAPE_TO_BALANCE_MM = 5.2
EXTERNAL_BALANCE_WHEEL_SOURCE_RADIUS_MM = 45.0
EXTERNAL_ESCAPEMENT_MIN_CLEARANCE_MM = 0.25
THROUGH_AXIS_KEEP_OUT_RADIUS_MM = 0.34
THROUGH_AXIS_TO_GEAR_MIN_CLEARANCE_MM = 0.08
SAME_LAYER_NON_MESH_MIN_CLEARANCE_MM = 0.02
Z_LAYER_BY_GEAR = {
    "barrel_outer_teeth": 1,
    "center_pinion": 1,
    "center_wheel": 2,
    "third_pinion": 2,
    "third_wheel": 3,
    "fourth_pinion": 3,
    "escape_wheel": 3,
    "cannon_pinion_display_driver": 3,
    "minute_wheel": 3,
    "fourth_wheel": 4,
    "escape_pinion": 4,
    "minute_pinion": 4,
    "hour_wheel": 4,
}
def solve_current_pattern(
    *,
    seed: int = 123,
    case_inner_radius_mm: float = DEFAULT_CASE_INNER_RADIUS_MM,
    bridge_perimeter_reserved_band_mm: float = BRIDGE_PERIMETER_RESERVED_BAND_MM,
    candidate_limit: int | None = None,
) -> dict[str, Any]:
    """Enumerate and select a geometry candidate for the current pattern."""

    candidates, solver_stages = _build_candidates(seed, case_inner_radius_mm, bridge_perimeter_reserved_band_mm)
    if candidate_limit is not None:
        candidates = candidates[:candidate_limit]
    feasible = [candidate for candidate in candidates if candidate["status"] == "pass"]
    selected = _select_candidate(feasible, seed)
    failed_reasons = sorted({reason for candidate in candidates for reason in candidate["failed_reasons"]})
    return {
        "kind": "watch_current_pattern_solver_report",
        "pattern_card_id": CURRENT_PATTERN_ID,
        "status": "pass" if selected else "fail",
        "seed": seed,
        "selection_strategy": "chain_solve_then_score_feasible_candidates",
        "geometry_equations": GEOMETRY_EQUATIONS,
        "variables": {
            "fixed": {
                "case_inner_radius_mm": case_inner_radius_mm,
                "bridge_perimeter_screw_policy": BRIDGE_PERIMETER_SCREW_POLICY,
                "bridge_z_stack_fastener_policy": BRIDGE_Z_STACK_FASTENER_POLICY,
                "bridge_perimeter_reserved_band_mm": bridge_perimeter_reserved_band_mm,
                "hour_axis": DISPLAY_CENTER_AXIS,
                "minute_axis": DISPLAY_CENTER_AXIS,
                "center_wheel_axis": "center_axis",
            },
            "enumerated": [
                "module",
                "display_motion_module",
                "display_tooth_count_set_id",
                "minute_work_angle_deg",
                "barrel_angle_deg",
                "third_angle_deg",
                "fourth_angle_deg",
                "escape_angle_deg",
                "balance_angle_deg",
                "structure_family_id",
            ],
            "derived": [
                "minute_work_axis",
                "barrel_axis",
                "third_axis",
                "fourth_axis",
                "escape_axis",
                "pallet_axis",
                "balance_axis",
            ],
        },
        "candidate_count": len(candidates),
        "feasible_candidate_count": len(feasible),
        "solver_stages": solver_stages,
        "failed_reasons": [] if selected else failed_reasons,
        "selected_candidate": selected,
        "candidates": candidates,
    }


def _build_candidates(
    seed: int,
    case_inner_radius_mm: float,
    bridge_perimeter_reserved_band_mm: float = BRIDGE_PERIMETER_RESERVED_BAND_MM,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nominal = _nominal_variables(seed)
    base_states = [
        {
            "module": module,
            "display_motion_module": 0.12,
            "display_tooth_count_set_id": "wide_clearance_10_100_50_60",
        }
        for module in _unique([nominal["module"], 0.16, 0.17])
    ]
    rejected_candidates: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []

    stage_specs = [
        ("display_motion_axis", "minute_work_angle_deg", lambda state: _angle_values(nominal["minute_work_angle_deg"], 24.0, 7)),
        ("barrel_axis", "barrel_angle_deg", lambda state: _angle_values(nominal["barrel_angle_deg"], 24.0, 7)),
        ("third_axis", "third_angle_deg", lambda state: _third_angle_values(seed, nominal, state)),
        ("fourth_axis", "fourth_angle_deg", lambda state: _angle_values(nominal["fourth_angle_deg"], 10.0, 5)),
        ("escape_axis", "escape_angle_deg", lambda state: _angle_values(nominal["escape_angle_deg"], 10.0, 5)),
        ("balance_axis", "balance_angle_deg", lambda state: _angle_values(nominal["balance_angle_deg"], 26.0, 7)),
    ]

    states = base_states
    for stage_id, variable_name, value_factory in stage_specs:
        states, rejected = _solve_chain_stage(
            seed,
            stage_id,
            variable_name,
            value_factory,
            states,
            nominal,
            case_inner_radius_mm,
            bridge_perimeter_reserved_band_mm,
        )
        rejected_candidates.extend(rejected)
        stages.append(
            {
                "stage_id": stage_id,
                "variable": variable_name,
                "accepted_count": len(states),
                "rejected_count": len(rejected),
                "policy": "expand_from_seeded_domain_then_filter_by_stage_specific_geometry",
            }
        )
        if not states:
            return sorted(rejected_candidates, key=lambda candidate: candidate["candidate_id"]), stages

    candidates = []
    index = 0
    for state in states:
        variables = _complete_variables(state, nominal)
        candidates.append(
            _build_candidate(
                index,
                variables,
                case_inner_radius_mm,
                bridge_perimeter_reserved_band_mm,
                _variables_match_nominal(variables, nominal),
            )
        )
        index += 1
    return sorted([*candidates, *rejected_candidates], key=lambda candidate: candidate["candidate_id"]), stages


def _solve_chain_stage(
    seed: int,
    stage_id: str,
    variable_name: str,
    value_factory: Any,
    states: list[dict[str, Any]],
    nominal: dict[str, Any],
    case_inner_radius_mm: float,
    bridge_perimeter_reserved_band_mm: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for state in states:
        for value in value_factory(state):
            next_state = {**state, variable_name: value}
            variables = _complete_variables(next_state, nominal)
            candidate = _build_candidate(
                len(accepted) + len(rejected),
                variables,
                case_inner_radius_mm,
                bridge_perimeter_reserved_band_mm,
                _variables_match_nominal(variables, nominal),
            )
            candidate["chain_stage_id"] = stage_id
            if _candidate_passes_chain_stage(candidate, stage_id):
                accepted.append(next_state)
            else:
                rejected.append(candidate)
    accepted = sorted(
        accepted,
        key=lambda state: _chain_state_rank(seed, stage_id, state, nominal),
    )[:80]
    return accepted, rejected[:40]


def _complete_variables(state: dict[str, Any], nominal: dict[str, Any]) -> dict[str, Any]:
    variables = dict(nominal)
    variables.update(state)
    return variables


def _candidate_passes_chain_stage(candidate: dict[str, Any], stage_id: str) -> bool:
    if stage_id == "display_motion_axis":
        return _envelope_status(candidate, {"minute_wheel", "minute_pinion"}) == "pass"
    if stage_id == "barrel_axis":
        return _envelope_status(candidate, {"barrel_outer_teeth"}) == "pass"
    if stage_id == "third_axis":
        return (
            _envelope_status(candidate, {"third_pinion", "third_wheel"}) == "pass"
            and _same_layer_pair_status(candidate, "third_wheel", "minute_wheel") == "pass"
        )
    if stage_id == "fourth_axis":
        return _envelope_status(candidate, {"fourth_pinion", "fourth_wheel"}) == "pass"
    if stage_id == "escape_axis":
        return (
            _envelope_status(candidate, {"escape_pinion", "escape_wheel"}) == "pass"
            and not _same_layer_failures_involving(candidate, {"escape_wheel"})
        )
    if stage_id == "balance_axis":
        return candidate["status"] == "pass"
    return candidate["status"] == "pass"


def _envelope_status(candidate: dict[str, Any], entity_ids: set[str]) -> str:
    for envelope in candidate["envelopes"]:
        if envelope["entity_id"] in entity_ids and (
            envelope["case_boundary_check"]["status"] != "pass"
            or envelope["bridge_perimeter_service_band_check"]["status"] != "pass"
        ):
            return "fail"
    return "pass"


def _same_layer_pair_status(candidate: dict[str, Any], left_id: str, right_id: str) -> str:
    pair = {left_id, right_id}
    for proof in candidate["same_layer_gear_interference_proofs"]:
        if {proof["left_gear_id"], proof["right_gear_id"]} == pair:
            return proof["status"]
    return "pass"


def _same_layer_failures_involving(candidate: dict[str, Any], gear_ids: set[str]) -> list[dict[str, Any]]:
    return [
        proof
        for proof in candidate["same_layer_gear_interference_proofs"]
        if proof["status"] != "pass" and {proof["left_gear_id"], proof["right_gear_id"]} & gear_ids
    ]


def _angle_values(center: float, span: float, count: int) -> list[float]:
    if count <= 1:
        return [center]
    step = (span * 2.0) / (count - 1)
    return _unique([center - span + step * index for index in range(count)])


def _third_angle_values(seed: int, nominal: dict[str, Any], state: dict[str, Any]) -> list[float]:
    minute_angle = float(state["minute_work_angle_deg"])
    clearance_separation = 128.0 + _range_by_seed(seed, "third_axis_clearance_separation", -8.0, 8.0)
    center = minute_angle - clearance_separation
    return _unique([*_angle_values(center, 14.0, 7), *_angle_values(nominal["third_angle_deg"], 8.0, 5)])


def _chain_state_rank(seed: int, stage_id: str, state: dict[str, Any], nominal: dict[str, Any]) -> tuple[float, float]:
    variable_penalty = sum(
        abs(float(state[key]) - float(nominal[key]))
        for key in state
        if key.endswith("_angle_deg") and key in nominal
    )
    return (variable_penalty, _named_random(seed, f"{stage_id}:{sorted(state.items())}"))


def _nominal_variables(seed: int) -> dict[str, Any]:
    module = _choose_by_seed(seed, "module", [0.16, 0.17])
    family_id = _structure_family_id(seed)
    family = GEAR_AXIS_STRUCTURE_FAMILIES[family_id]
    return {
        "module": module,
        "display_motion_module": 0.12,
        "display_tooth_count_set_id": "wide_clearance_10_100_50_60",
        "structure_family_id": family_id,
        "minute_work_angle_deg": family["minute_work_angle_deg"] + _range_by_seed(seed, f"{family_id}:minute_work_axis_angle", -5.0, 5.0),
        "barrel_angle_deg": family["barrel_angle_deg"] + _range_by_seed(seed, f"{family_id}:barrel_axis_position", -7.0, 7.0),
        "third_angle_deg": family["third_angle_deg"] + _range_by_seed(seed, f"{family_id}:third_axis_position", -8.0, 8.0),
        "fourth_angle_deg": family["fourth_angle_deg"] + _range_by_seed(seed, f"{family_id}:fourth_axis_position", -7.0, 7.0),
        "escape_angle_deg": family["escape_angle_deg"] + _range_by_seed(seed, f"{family_id}:escape_axis_position", -7.0, 7.0),
        "balance_angle_deg": family["balance_angle_deg"] + _range_by_seed(seed, f"{family_id}:balance_axis_position", -10.0, 10.0),
    }


def _structure_family_id(seed: int) -> str:
    family_ids = list(GEAR_AXIS_STRUCTURE_FAMILIES)
    fixed_probe_mapping = {
        1: "baseline_diagonal",
        2: "lower_train_sweep",
        4: "upper_arc_sweep",
        5: "high_escape_sweep",
        6: "low_escape_sweep",
    }
    if seed in fixed_probe_mapping:
        return fixed_probe_mapping[seed]
    return family_ids[seed % len(family_ids)]


def _build_candidate(
    index: int,
    variables: dict[str, Any],
    case_inner_radius_mm: float,
    bridge_perimeter_reserved_band_mm: float,
    is_seed_nominal: bool,
) -> dict[str, Any]:
    tooth_counts = _tooth_counts_for_display_set(str(variables["display_tooth_count_set_id"]))
    module = variables["module"]
    display_module = variables["display_motion_module"]

    center = (0.0, 0.0)
    minute_work_distance = _center_distance(
        display_module,
        tooth_counts["cannon_pinion_display_driver"],
        tooth_counts["minute_wheel"],
    )
    minute_work = _polar_from(center, minute_work_distance, variables["minute_work_angle_deg"])
    barrel = _polar_from(
        center,
        _center_distance(module, tooth_counts["barrel_outer_teeth"], tooth_counts["center_pinion"]),
        variables["barrel_angle_deg"],
    )
    third = _polar_from(
        center,
        _center_distance(module, tooth_counts["center_wheel"], tooth_counts["third_pinion"]),
        variables["third_angle_deg"],
    )
    fourth = _polar_from(
        third,
        _center_distance(module, tooth_counts["third_wheel"], tooth_counts["fourth_pinion"]),
        variables["fourth_angle_deg"],
    )
    escape = _polar_from(
        fourth,
        _center_distance(module, tooth_counts["fourth_wheel"], tooth_counts["escape_pinion"]),
        variables["escape_angle_deg"],
    )
    balance = _polar_from(
        escape,
        EXTERNAL_ESCAPEMENT_TARGET_ESCAPE_TO_BALANCE_MM,
        variables["balance_angle_deg"],
    )
    pallet = _point_between(escape, balance, 45.0 / EXTERNAL_ESCAPEMENT_SOURCE_ESCAPE_TO_BALANCE_MM)

    axes = [
        _axis(DISPLAY_CENTER_AXIS, center, "central_hour_minute_display_axis", 0.9),
        _axis("minute_work_axis", minute_work, "motion_works_compound_arbor", 0.7),
        _axis("barrel_axis", barrel, "barrel_arbor", 3.0),
        _axis("center_axis", center, "compound_train_arbor_and_minute_source", 2.0),
        _axis("third_axis", third, "compound_train_arbor", 2.0),
        _axis("fourth_axis", fourth, "compound_train_arbor_and_sub_seconds_display", 2.0),
        _axis("escape_axis", escape, "escape_arbor", 2.1),
        _axis("pallet_axis", pallet, "pallet_fork_pivot", 1.15),
        _axis("balance_axis", balance, "balance_staff", 2.65),
    ]
    axes_by_id = {axis["axis_id"]: axis for axis in axes}
    gears = _gear_specs(tooth_counts, module, display_module, axes_by_id)
    center_distance_proofs = _center_distance_proofs(gears, axes_by_id)
    envelopes = _envelope_checks(gears, axes_by_id, case_inner_radius_mm, bridge_perimeter_reserved_band_mm)
    bridge_perimeter_service_band_proofs = _bridge_perimeter_service_band_proofs(envelopes, bridge_perimeter_reserved_band_mm)
    external_keepout_proofs = _external_escapement_keepout_proofs(gears, axes_by_id)
    shaft_keepout_proofs = _shaft_to_foreign_gear_keepout_proofs(gears, axes_by_id)
    same_layer_gear_interference_proofs = _same_layer_gear_interference_proofs(gears, axes_by_id)
    failed_reasons = _candidate_failures(
        center_distance_proofs,
        envelopes,
        bridge_perimeter_service_band_proofs,
        external_keepout_proofs,
        shaft_keepout_proofs,
        same_layer_gear_interference_proofs,
    )
    score = _candidate_score(
        envelopes,
        axes_by_id,
        external_keepout_proofs,
        shaft_keepout_proofs,
        same_layer_gear_interference_proofs,
    )
    status = "pass" if not failed_reasons else "fail"
    return {
        "candidate_id": f"cand_{index:04d}",
        "status": status,
        "is_seed_nominal": is_seed_nominal,
        "variables": {key: _serializable_variable(value) for key, value in variables.items()},
        "tooth_counts": tooth_counts,
        "axes": axes,
        "gears": gears,
        "meshes": [{"driver": driver, "driven": driven, "kind": "external"} for driver, driven in POWER_MESHES],
        "display_meshes": [{"driver": driver, "driven": driven, "kind": "external"} for driver, driven in DISPLAY_MESHES],
        "center_distance_proofs": center_distance_proofs,
        "envelopes": envelopes,
        "bridge_perimeter_service_band_proofs": bridge_perimeter_service_band_proofs,
        "external_escapement_keepout_proofs": external_keepout_proofs,
        "shaft_to_foreign_gear_keepout_proofs": shaft_keepout_proofs,
        "same_layer_gear_interference_proofs": same_layer_gear_interference_proofs,
        "display_strategy": {
            "kind": "central_hour_minute_with_off_center_seconds",
            "hour_axis": DISPLAY_CENTER_AXIS,
            "minute_axis": DISPLAY_CENTER_AXIS,
            "seconds_axis": "fourth_axis",
            "minute_work_axis": "minute_work_axis",
        },
        "score": round(score, 6),
        "failed_reasons": failed_reasons,
    }


def _gear_specs(
    tooth_counts: dict[str, int],
    module: float,
    display_module: float,
    axes_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    specs = [
        _gear("barrel_outer_teeth", "barrel_axis", tooth_counts, module, "wheel"),
        _gear("center_pinion", "center_axis", tooth_counts, module, "pinion"),
        _gear("center_wheel", "center_axis", tooth_counts, module, "wheel"),
        _gear("third_pinion", "third_axis", tooth_counts, module, "pinion"),
        _gear("third_wheel", "third_axis", tooth_counts, module, "wheel"),
        _gear("fourth_pinion", "fourth_axis", tooth_counts, module, "pinion"),
        _gear("fourth_wheel", "fourth_axis", tooth_counts, module, "wheel"),
        _gear("escape_pinion", "escape_axis", tooth_counts, module, "pinion"),
        _gear("escape_wheel", "escape_axis", tooth_counts, module, "escape"),
        _gear("cannon_pinion_display_driver", DISPLAY_CENTER_AXIS, tooth_counts, display_module, "pinion", display_role="motion_works"),
        _gear("minute_wheel", "minute_work_axis", tooth_counts, display_module, "wheel", display_role="motion_works"),
        _gear("minute_pinion", "minute_work_axis", tooth_counts, display_module, "pinion", display_role="motion_works"),
        _gear("hour_wheel", DISPLAY_CENTER_AXIS, tooth_counts, display_module, "wheel", display_role="motion_works"),
    ]
    for gear in specs:
        axis = axes_by_id[gear["axis_id"]]
        gear["x"] = axis["x"]
        gear["y"] = axis["y"]
    return specs


def _gear(
    gear_id: str,
    axis_id: str,
    tooth_counts: dict[str, int],
    module: float,
    gear_type: str,
    *,
    display_role: str | None = None,
) -> dict[str, Any]:
    pitch_radius = module * tooth_counts[gear_id] / 2.0
    addendum = module * (0.76 if gear_type == "pinion" else 0.72)
    dedendum = module * 1.08
    gear = {
        "gear_id": gear_id,
        "axis_id": axis_id,
        "tooth_count": tooth_counts[gear_id],
        "module": module,
        "pitch_radius": round(pitch_radius, 6),
        "outer_radius": round(pitch_radius + addendum, 6),
        "root_radius": round(max(0.28, pitch_radius - dedendum), 6),
        "gear_type": gear_type,
    }
    if display_role:
        gear["display_role"] = display_role
    return gear


def _center_distance_proofs(gears: list[dict[str, Any]], axes_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    gear_by_id = {gear["gear_id"]: gear for gear in gears}
    proofs = []
    for driver, driven in (*POWER_MESHES, *DISPLAY_MESHES):
        driver_gear = gear_by_id[driver]
        driven_gear = gear_by_id[driven]
        driver_axis = axes_by_id[driver_gear["axis_id"]]
        driven_axis = axes_by_id[driven_gear["axis_id"]]
        expected = _center_distance(driver_gear["module"], driver_gear["tooth_count"], driven_gear["tooth_count"])
        actual = _distance((driver_axis["x"], driver_axis["y"]), (driven_axis["x"], driven_axis["y"]))
        error = abs(actual - expected)
        proofs.append(
            {
                "driver": driver,
                "driven": driven,
                "formula": "center_distance = module * (driver_teeth + driven_teeth) / 2",
                "expected_distance_mm": round(expected, 6),
                "actual_distance_mm": round(actual, 6),
                "error_mm": round(error, 9),
                "status": "pass" if error <= 1e-6 else "fail",
            }
        )
    return proofs


def _envelope_checks(
    gears: list[dict[str, Any]],
    axes_by_id: dict[str, dict[str, Any]],
    case_inner_radius_mm: float,
    bridge_perimeter_reserved_band_mm: float,
) -> list[dict[str, Any]]:
    envelopes = []
    for gear in gears:
        axis = axes_by_id[gear["axis_id"]]
        envelopes.append(_envelope(gear["gear_id"], axis, gear["outer_radius"], case_inner_radius_mm, bridge_perimeter_reserved_band_mm, "gear"))
    for entity_id, axis_id, radius, kind in [
        ("pallet_fork_reference_envelope", "pallet_axis", 1.15, "escapement_reference"),
        ("balance_wheel_reference_envelope", "balance_axis", 2.65, "escapement_reference"),
    ]:
        envelopes.append(_envelope(entity_id, axes_by_id[axis_id], radius, case_inner_radius_mm, bridge_perimeter_reserved_band_mm, kind))
    return envelopes


def _envelope(
    entity_id: str,
    axis: dict[str, Any],
    radius: float,
    case_inner_radius_mm: float,
    bridge_perimeter_reserved_band_mm: float,
    kind: str,
) -> dict[str, Any]:
    center_distance = math.hypot(axis["x"], axis["y"])
    margin = case_inner_radius_mm - (center_distance + radius)
    return {
        "entity_id": entity_id,
        "axis_id": axis["axis_id"],
        "kind": kind,
        "x": axis["x"],
        "y": axis["y"],
        "radius_mm": round(radius, 6),
        "outer_distance_from_case_center_mm": round(center_distance + radius, 6),
        "case_boundary_check": {
            "status": "pass" if margin > 0.0 else "fail",
            "margin_mm": round(margin, 6),
        },
        "bridge_perimeter_service_band_check": {
            "status": "pass" if margin >= bridge_perimeter_reserved_band_mm else "fail",
            "margin_mm": round(margin, 6),
            "reserved_band_mm": round(bridge_perimeter_reserved_band_mm, 6),
            "screw_policy": BRIDGE_PERIMETER_SCREW_POLICY["policy_id"],
        },
    }


def _bridge_perimeter_service_band_proofs(envelopes: list[dict[str, Any]], bridge_perimeter_reserved_band_mm: float) -> dict[str, Any]:
    margins = [
        envelope["bridge_perimeter_service_band_check"]["margin_mm"]
        for envelope in envelopes
    ]
    minimum_margin = min(margins) if margins else -math.inf
    violations = [
        {
            "entity_id": envelope["entity_id"],
            "axis_id": envelope["axis_id"],
            "margin_mm": envelope["bridge_perimeter_service_band_check"]["margin_mm"],
            "reserved_band_mm": envelope["bridge_perimeter_service_band_check"]["reserved_band_mm"],
        }
        for envelope in envelopes
        if envelope["bridge_perimeter_service_band_check"]["status"] != "pass"
    ]
    return {
        "status": "pass" if not violations else "fail",
        "policy": BRIDGE_PERIMETER_SCREW_POLICY,
        "minimum_margin_mm": round(minimum_margin, 6),
        "reserved_band_mm": round(bridge_perimeter_reserved_band_mm, 6),
        "violations": violations,
    }


def _candidate_failures(
    center_distance_proofs: list[dict[str, Any]],
    envelopes: list[dict[str, Any]],
    bridge_perimeter_service_band_proofs: dict[str, Any],
    external_keepout_proofs: list[dict[str, Any]],
    shaft_keepout_proofs: list[dict[str, Any]],
    same_layer_gear_interference_proofs: list[dict[str, Any]],
) -> list[str]:
    failures = []
    if any(proof["status"] != "pass" for proof in center_distance_proofs):
        failures.append("center_distance")
    if any(envelope["case_boundary_check"]["status"] != "pass" for envelope in envelopes):
        failures.append("case_boundary")
    if bridge_perimeter_service_band_proofs["status"] != "pass":
        failures.append("bridge_perimeter_service_band")
    if any(proof["status"] != "pass" for proof in external_keepout_proofs):
        failures.append("external_escapement_keepout")
    if any(proof["status"] != "pass" for proof in shaft_keepout_proofs):
        failures.append("through_axis_to_foreign_gear_keepout")
    if any(proof["status"] != "pass" for proof in same_layer_gear_interference_proofs):
        failures.append("same_layer_non_mesh_gear_interference")
    return failures


def _external_escapement_keepout_proofs(
    gears: list[dict[str, Any]],
    axes_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    gear_by_id = {gear["gear_id"]: gear for gear in gears}
    fourth_wheel = gear_by_id["fourth_wheel"]
    fourth_axis = axes_by_id[fourth_wheel["axis_id"]]
    balance_axis = axes_by_id["balance_axis"]
    scale = _distance(
        (axes_by_id["escape_axis"]["x"], axes_by_id["escape_axis"]["y"]),
        (balance_axis["x"], balance_axis["y"]),
    ) / EXTERNAL_ESCAPEMENT_SOURCE_ESCAPE_TO_BALANCE_MM
    external_balance_radius = EXTERNAL_BALANCE_WHEEL_SOURCE_RADIUS_MM * scale
    center_distance = _distance((fourth_axis["x"], fourth_axis["y"]), (balance_axis["x"], balance_axis["y"]))
    hard_contact_distance = fourth_wheel["outer_radius"] + external_balance_radius
    required = hard_contact_distance + EXTERNAL_ESCAPEMENT_MIN_CLEARANCE_MM
    clearance = center_distance - hard_contact_distance
    return [
        {
            "proof_id": "balance_axis_vs_same_layer_fourth_wheel",
            "reason": "external balance wheel and the same-layer fourth wheel must not overlap in XY",
            "first_entity": "external_balance_wheel",
            "second_entity": "fourth_wheel",
            "center_distance_mm": round(center_distance, 6),
            "required_distance_mm": round(required, 6),
            "clearance_mm": round(clearance, 6),
            "minimum_clearance_mm": EXTERNAL_ESCAPEMENT_MIN_CLEARANCE_MM,
            "status": "pass" if clearance >= EXTERNAL_ESCAPEMENT_MIN_CLEARANCE_MM else "fail",
        }
    ]


def _shaft_to_foreign_gear_keepout_proofs(
    gears: list[dict[str, Any]],
    axes_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    proofs: list[dict[str, Any]] = []
    for gear in gears:
        gear_axis = axes_by_id[gear["axis_id"]]
        gear_point = (gear_axis["x"], gear_axis["y"])
        for axis in axes_by_id.values():
            if axis["axis_id"] == gear["axis_id"]:
                continue
            axis_point = (axis["x"], axis["y"])
            center_distance = _distance(gear_point, axis_point)
            if center_distance <= 1e-6:
                continue
            hard_contact_distance = gear["outer_radius"] + THROUGH_AXIS_KEEP_OUT_RADIUS_MM
            required = hard_contact_distance + THROUGH_AXIS_TO_GEAR_MIN_CLEARANCE_MM
            clearance = center_distance - hard_contact_distance
            proofs.append(
                {
                    "proof_id": f"{axis['axis_id']}_vs_{gear['gear_id']}",
                    "axis_id": axis["axis_id"],
                    "gear_id": gear["gear_id"],
                    "center_distance_mm": round(center_distance, 6),
                    "required_distance_mm": round(required, 6),
                    "gear_outer_radius_mm": gear["outer_radius"],
                    "shaft_keepout_radius_mm": THROUGH_AXIS_KEEP_OUT_RADIUS_MM,
                    "clearance_mm": round(clearance, 6),
                    "minimum_clearance_mm": THROUGH_AXIS_TO_GEAR_MIN_CLEARANCE_MM,
                    "status": "pass" if clearance >= THROUGH_AXIS_TO_GEAR_MIN_CLEARANCE_MM else "fail",
                }
            )
    return proofs


def _same_layer_gear_interference_proofs(
    gears: list[dict[str, Any]],
    axes_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    allowed_pairs = {frozenset(pair) for pair in (*POWER_MESHES, *DISPLAY_MESHES)}
    proofs: list[dict[str, Any]] = []
    for left_index, left in enumerate(gears):
        left_layer = Z_LAYER_BY_GEAR[left["gear_id"]]
        left_axis = axes_by_id[left["axis_id"]]
        for right in gears[left_index + 1 :]:
            right_layer = Z_LAYER_BY_GEAR[right["gear_id"]]
            if left_layer != right_layer:
                continue
            pair_key = frozenset((left["gear_id"], right["gear_id"]))
            if pair_key in allowed_pairs:
                continue
            right_axis = axes_by_id[right["axis_id"]]
            center_distance = _distance((left_axis["x"], left_axis["y"]), (right_axis["x"], right_axis["y"]))
            clearance = center_distance - left["outer_radius"] - right["outer_radius"]
            proofs.append(
                {
                    "proof_id": f"{left['gear_id']}_vs_{right['gear_id']}",
                    "left_gear_id": left["gear_id"],
                    "right_gear_id": right["gear_id"],
                    "z_layer": left_layer,
                    "center_distance_mm": round(center_distance, 6),
                    "left_outer_radius_mm": left["outer_radius"],
                    "right_outer_radius_mm": right["outer_radius"],
                    "clearance_mm": round(clearance, 6),
                    "minimum_clearance_mm": SAME_LAYER_NON_MESH_MIN_CLEARANCE_MM,
                    "status": "pass" if clearance >= SAME_LAYER_NON_MESH_MIN_CLEARANCE_MM else "fail",
                }
            )
    return proofs


def _candidate_score(
    envelopes: list[dict[str, Any]],
    axes_by_id: dict[str, dict[str, Any]],
    external_keepout_proofs: list[dict[str, Any]],
    shaft_keepout_proofs: list[dict[str, Any]],
    same_layer_gear_interference_proofs: list[dict[str, Any]],
) -> float:
    min_margin = min(envelope["case_boundary_check"]["margin_mm"] for envelope in envelopes)
    escape_axis = axes_by_id["escape_axis"]
    balance_axis = axes_by_id["balance_axis"]
    escapement_span = _distance((escape_axis["x"], escape_axis["y"]), (balance_axis["x"], balance_axis["y"]))
    min_external_clearance = min(proof["clearance_mm"] for proof in external_keepout_proofs)
    min_axis_clearance = min(proof["clearance_mm"] for proof in shaft_keepout_proofs)
    min_same_layer_clearance = min(proof["clearance_mm"] for proof in same_layer_gear_interference_proofs)
    return (
        max(0.0, min_margin)
        + 0.2 * escapement_span
        + 0.15 * max(0.0, min_external_clearance)
        + 0.05 * max(0.0, min_axis_clearance)
        + 0.05 * max(0.0, min_same_layer_clearance)
    )


def _select_candidate(candidates: list[dict[str, Any]], seed: int) -> dict[str, Any] | None:
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda candidate: (
            0 if candidate["is_seed_nominal"] else 1,
            _candidate_seed_rank(candidate["candidate_id"], seed),
            -candidate["score"],
        ),
    )
    return ranked[0]


def _candidate_seed_rank(candidate_id: str, seed: int) -> float:
    return _named_random(seed, f"candidate:{candidate_id}")


def _axis(axis_id: str, point: tuple[float, float], role: str, keepout_radius: float) -> dict[str, Any]:
    return {
        "axis_id": axis_id,
        "x": round(point[0], 9),
        "y": round(point[1], 9),
        "role": role,
        "keepout_radius": keepout_radius,
    }


def _center_distance(module: float, driver_teeth: int, driven_teeth: int) -> float:
    return module * (driver_teeth + driven_teeth) / 2.0


def _polar_from(origin: tuple[float, float], distance: float, angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return (origin[0] + math.cos(angle) * distance, origin[1] + math.sin(angle) * distance)


def _point_between(start: tuple[float, float], end: tuple[float, float], ratio: float) -> tuple[float, float]:
    return (start[0] + (end[0] - start[0]) * ratio, start[1] + (end[1] - start[1]) * ratio)


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _unique(values: list[float]) -> list[float]:
    unique_values = []
    for value in values:
        if not any(abs(value - existing) < 1e-12 for existing in unique_values):
            unique_values.append(value)
    return unique_values


def _unique_strings(values: list[str]) -> list[str]:
    unique_values = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return unique_values


def _tooth_counts_for_display_set(display_set_id: str) -> dict[str, int]:
    tooth_counts = dict(DEFAULT_TOOTH_COUNTS)
    tooth_counts.update(DISPLAY_TOOTH_COUNT_SETS[display_set_id])
    return tooth_counts


def _variables_match_nominal(variables: dict[str, Any], nominal: dict[str, Any]) -> bool:
    for key, value in variables.items():
        nominal_value = nominal.get(key)
        if isinstance(value, (float, int)) and isinstance(nominal_value, (float, int)):
            if abs(float(value) - float(nominal_value)) >= 1e-9:
                return False
        elif value != nominal_value:
            return False
    return True


def _serializable_variable(value: Any) -> Any:
    if isinstance(value, (float, int)):
        return round(float(value), 9)
    return value


def _choose_by_seed(seed: int | str, key: str, choices: list[Any] | tuple[Any, ...]) -> Any:
    index = min(int(_named_random(seed, key) * len(choices)), len(choices) - 1)
    return choices[index]


def _range_by_seed(seed: int | str, key: str, low: float, high: float) -> float:
    return low + (high - low) * _named_random(seed, key)


def _named_random(seed: int | str, key: str) -> float:
    digest = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big")
    return value / float(1 << 64)
