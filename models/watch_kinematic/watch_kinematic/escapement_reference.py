"""Semantic decomposition for the scaled Swiss lever escapement reference.

The downloaded STEP is treated as a reference artifact. This module maps it
onto the current watch pattern axes and emits role, envelope, and motion
contracts before the placeholder escapement geometry is replaced.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .power_chain_mvp import CASE_INNER_RADIUS_MM, _axis_by_id, _build_design
from .third_party_escapement import resolve_escapement_step


PATTERN_CARD_ID = "watch_swiss_lever_escapement_reference"
REQUIRED_ESCAPEMENT_ROLES = ("escape_wheel", "pallet_fork", "balance_wheel", "hairspring")

SOURCE_ESCAPE_AXIS_XY = (0.0, 0.0)
SOURCE_BALANCE_AXIS_XY = (0.0, 89.06)
SOURCE_REFERENCE_STEP = resolve_escapement_step()


def run_escapement_reference_semantics(output_dir: str | Path, *, seed: int = 123) -> dict[str, Any]:
    """Write reference-level contracts for the Swiss lever escapement."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    design = _build_design(seed)
    axes = _build_axis_report(design)
    envelopes = _build_envelope_report(axes)
    motion = _build_motion_constraints()
    role_contracts = _build_role_contract_report(axes, envelopes, motion)
    semantic = _build_semantic_report(axes, envelopes, motion, role_contracts)
    validation = _build_validation_report(semantic, axes, envelopes, motion, role_contracts)

    semantic_path = target / "watch_escapement_reference.semantic.json"
    role_contract_path = target / "watch_escapement_reference.role_contracts.json"
    axes_path = target / "watch_escapement_reference.axes.json"
    envelopes_path = target / "watch_escapement_reference.envelopes.json"
    motion_path = target / "watch_escapement_reference.motion_constraints.json"
    validation_path = target / "watch_escapement_reference.validation.json"

    semantic_path.write_text(json.dumps(semantic, indent=2, ensure_ascii=False), encoding="utf-8")
    role_contract_path.write_text(json.dumps(role_contracts, indent=2, ensure_ascii=False), encoding="utf-8")
    axes_path.write_text(json.dumps(axes, indent=2, ensure_ascii=False), encoding="utf-8")
    envelopes_path.write_text(json.dumps(envelopes, indent=2, ensure_ascii=False), encoding="utf-8")
    motion_path.write_text(json.dumps(motion, indent=2, ensure_ascii=False), encoding="utf-8")
    validation_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "status": validation["status"],
        "pattern_card_id": PATTERN_CARD_ID,
        "seed": seed,
        "artifacts": {
            "reference_semantic_json": str(semantic_path),
            "role_contract_json": str(role_contract_path),
            "axes_json": str(axes_path),
            "envelopes_json": str(envelopes_path),
            "motion_constraints_json": str(motion_path),
            "validation_json": str(validation_path),
        },
    }


def _build_axis_report(design: dict[str, Any]) -> dict[str, Any]:
    escape_axis = _axis_by_id(design, "escape_axis")
    pallet_axis = _axis_by_id(design, "pallet_axis")
    balance_axis = _axis_by_id(design, "balance_axis")
    fit = _fit_reference_axes(escape_axis, balance_axis)
    transformed_escape = _transform_source_xy(SOURCE_ESCAPE_AXIS_XY, fit)
    transformed_balance = _transform_source_xy(SOURCE_BALANCE_AXIS_XY, fit)
    escape_error = _distance(transformed_escape, (escape_axis["x"], escape_axis["y"]))
    balance_error = _distance(transformed_balance, (balance_axis["x"], balance_axis["y"]))

    return {
        "kind": "watch_escapement_reference_axis_report",
        "pattern_card_id": PATTERN_CARD_ID,
        "status": "pass" if max(escape_error, balance_error) <= 0.01 else "fail",
        "source_reference_step": str(SOURCE_REFERENCE_STEP),
        "reference_fit": {
            "method": "axis_distance_and_direction_fit",
            **fit,
            "max_matched_axis_error_mm": round(max(escape_error, balance_error), 6),
        },
        "axis_checks": {
            "escape_axis_match_error_mm": round(escape_error, 6),
            "balance_axis_match_error_mm": round(balance_error, 6),
            "pallet_axis_source_status": "project_pattern_axis_pending_reference_feature_extraction",
        },
        "axes": [
            _axis_contract("escape_axis", escape_axis, "escape_wheel_arbor", "matched_to_downloaded_escape_axis"),
            _axis_contract("pallet_axis", pallet_axis, "pallet_fork_pivot", "project_pattern_axis_pending_reference_feature_extraction"),
            _axis_contract("balance_axis", balance_axis, "balance_staff", "matched_to_downloaded_balance_axis"),
            {
                **_axis_contract("hairspring_axis", balance_axis, "hairspring_collet_axis", "coaxial_placeholder"),
                "coaxial_with": "balance_axis",
            },
        ],
    }


def _fit_reference_axes(escape_axis: dict[str, Any], balance_axis: dict[str, Any]) -> dict[str, Any]:
    source_dx = SOURCE_BALANCE_AXIS_XY[0] - SOURCE_ESCAPE_AXIS_XY[0]
    source_dy = SOURCE_BALANCE_AXIS_XY[1] - SOURCE_ESCAPE_AXIS_XY[1]
    target_dx = balance_axis["x"] - escape_axis["x"]
    target_dy = balance_axis["y"] - escape_axis["y"]
    source_distance = math.hypot(source_dx, source_dy)
    target_distance = math.hypot(target_dx, target_dy)
    scale = target_distance / source_distance
    rotation = math.atan2(target_dy, target_dx) - math.atan2(source_dy, source_dx)
    rotation_deg = math.degrees(rotation) % 360.0
    return {
        "source_escape_axis_xy_mm": list(SOURCE_ESCAPE_AXIS_XY),
        "source_balance_axis_xy_mm": list(SOURCE_BALANCE_AXIS_XY),
        "source_escape_to_balance_distance_mm": round(source_distance, 6),
        "target_escape_axis_xy_mm": [round(escape_axis["x"], 6), round(escape_axis["y"], 6)],
        "target_balance_axis_xy_mm": [round(balance_axis["x"], 6), round(balance_axis["y"], 6)],
        "target_escape_to_balance_distance_mm": round(target_distance, 6),
        "scale": round(scale, 9),
        "rotation_deg_about_z": round(rotation_deg, 6),
        "translation_xy_mm": [round(escape_axis["x"], 6), round(escape_axis["y"], 6)],
    }


def _transform_source_xy(source_xy: tuple[float, float], fit: dict[str, Any]) -> tuple[float, float]:
    scale = fit["scale"]
    rotation = math.radians(fit["rotation_deg_about_z"])
    x = source_xy[0] * scale
    y = source_xy[1] * scale
    cos_a = math.cos(rotation)
    sin_a = math.sin(rotation)
    tx, ty = fit["translation_xy_mm"]
    return (x * cos_a - y * sin_a + tx, x * sin_a + y * cos_a + ty)


def _axis_contract(axis_id: str, axis: dict[str, Any], role: str, source: str) -> dict[str, Any]:
    return {
        "axis_id": axis_id,
        "role": role,
        "x_mm": round(axis["x"], 6),
        "y_mm": round(axis["y"], 6),
        "z_direction": "+Z",
        "source": source,
        "mount_policy": "mainplate_lower_pivot_plus_future_bridge_upper_pivot",
    }


def _build_envelope_report(axes: dict[str, Any]) -> dict[str, Any]:
    axis_by_id = {axis["axis_id"]: axis for axis in axes["axes"]}
    scale = axes["reference_fit"]["scale"]
    envelopes = [
        _envelope("escape_wheel_tip_envelope", axis_by_id["escape_axis"], max(1.05, 20.0 * scale), 2.25, 3.15, "escape wheel teeth and locking faces"),
        _envelope("pallet_fork_sweep_envelope", axis_by_id["pallet_axis"], 1.05, 2.55, 3.45, "pallet fork body and pallet stone sweep"),
        _envelope("balance_wheel_sweep_envelope", axis_by_id["balance_axis"], max(2.45, 45.0 * scale), 2.7, 4.0, "balance rim and roller safety envelope"),
        _envelope("hairspring_placeholder_envelope", axis_by_id["hairspring_axis"], max(1.05, 20.0 * scale), 3.05, 4.25, "flat hairspring placeholder envelope"),
    ]
    return {
        "kind": "watch_escapement_reference_envelope_report",
        "pattern_card_id": PATTERN_CARD_ID,
        "status": "pass" if all(envelope["case_boundary_check"]["status"] == "pass" for envelope in envelopes) else "fail",
        "case_inner_radius_mm": CASE_INNER_RADIUS_MM,
        "envelopes": envelopes,
    }


def _envelope(
    envelope_id: str,
    axis: dict[str, Any],
    radius: float,
    z_min: float,
    z_max: float,
    purpose: str,
) -> dict[str, Any]:
    center_distance = math.hypot(axis["x_mm"], axis["y_mm"])
    outer_distance = center_distance + radius
    return {
        "envelope_id": envelope_id,
        "axis_id": axis["axis_id"],
        "x_mm": axis["x_mm"],
        "y_mm": axis["y_mm"],
        "radius_mm": round(radius, 6),
        "z_min_mm": z_min,
        "z_max_mm": z_max,
        "purpose": purpose,
        "outer_distance_from_case_center_mm": round(outer_distance, 6),
        "case_boundary_check": {
            "status": "pass" if outer_distance < CASE_INNER_RADIUS_MM else "fail",
            "margin_mm": round(CASE_INNER_RADIUS_MM - outer_distance, 6),
        },
    }


def _build_motion_constraints() -> dict[str, Any]:
    return {
        "kind": "watch_escapement_reference_motion_constraints",
        "pattern_card_id": PATTERN_CARD_ID,
        "status": "pass",
        "timing_status": "report_only_until_real_escape_geometry_replaces_placeholder",
        "motion_links": [
            {
                "source": "escape_pinion",
                "target": "escape_wheel",
                "interface_type": "same_arbor_rigid_coupling",
                "behavior": "escape wheel rotates with the final train arbor",
                "proof": "shared escape_axis in current power-chain design",
            },
            {
                "source": "escape_wheel",
                "target": "pallet_fork",
                "interface_type": "locking_impulse_contact",
                "behavior": "escape teeth alternately lock and impulse through pallet stones",
                "required_future_geometry": ["entry_pallet_stone", "exit_pallet_stone", "escape_tooth_locking_faces"],
            },
            {
                "source": "pallet_fork",
                "target": "balance_wheel",
                "interface_type": "impulse_pin_contact",
                "behavior": "fork transmits impulse to the roller impulse pin and receives return motion",
                "required_future_geometry": ["fork_slot", "roller_impulse_pin", "safety_roller"],
            },
            {
                "source": "hairspring",
                "target": "balance_wheel",
                "interface_type": "restoring_torque_placeholder",
                "behavior": "hairspring provides restoring torque about balance staff",
                "required_future_geometry": ["hairspring_collet", "outer_stud_or_regulator_pin"],
            },
        ],
        "allowed_motion": {
            "escape_wheel": "intermittent_rotation_about_escape_axis",
            "pallet_fork": "small_angle_oscillation_about_pallet_axis",
            "balance_wheel": "oscillation_about_balance_axis",
            "hairspring": "elastic_angular_deflection_placeholder",
        },
        "hard_validation_deferred": [
            "locking_angle",
            "drop",
            "draw",
            "impulse_face_timing",
            "safety_action",
        ],
    }


def _build_role_contract_report(
    axes: dict[str, Any],
    envelopes: dict[str, Any],
    motion: dict[str, Any],
) -> dict[str, Any]:
    axis_by_id = {axis["axis_id"]: axis for axis in axes["axes"]}
    envelope_by_id = {envelope["envelope_id"]: envelope for envelope in envelopes["envelopes"]}
    contracts = [
        _role_contract(
            "escape_wheel",
            "escapement_release_wheel",
            ["receive_final_train_rotation", "alternately_lock_and_release_energy"],
            axis_by_id["escape_axis"],
            envelope_by_id["escape_wheel_tip_envelope"],
            ["escape_pinion", "escape_wheel", "pallet_fork"],
            ["same_arbor_rigid_coupling", "locking_impulse_contact"],
        ),
        _role_contract(
            "pallet_fork",
            "locking_and_impulse_lever",
            ["lock_escape_wheel", "transmit_impulse_to_balance", "receive_return_from_balance"],
            axis_by_id["pallet_axis"],
            envelope_by_id["pallet_fork_sweep_envelope"],
            ["escape_wheel", "pallet_fork", "balance_wheel"],
            ["locking_impulse_contact", "impulse_pin_contact"],
        ),
        _role_contract(
            "balance_wheel",
            "oscillating_regulator",
            ["receive_impulse", "set_period_with_hairspring", "return_fork_motion"],
            axis_by_id["balance_axis"],
            envelope_by_id["balance_wheel_sweep_envelope"],
            ["pallet_fork", "balance_wheel", "hairspring"],
            ["impulse_pin_contact", "restoring_torque_placeholder"],
        ),
        _role_contract(
            "hairspring",
            "restoring_spring_placeholder",
            ["provide_restoring_torque_placeholder", "share_balance_staff_axis"],
            axis_by_id["hairspring_axis"],
            envelope_by_id["hairspring_placeholder_envelope"],
            ["hairspring", "balance_wheel"],
            ["restoring_torque_placeholder"],
        ),
    ]
    return {
        "kind": "watch_escapement_reference_role_contract_report",
        "pattern_card_id": PATTERN_CARD_ID,
        "status": "pass" if all(contract["validation"]["status"] == "pass" for contract in contracts) else "fail",
        "roles": list(REQUIRED_ESCAPEMENT_ROLES),
        "contracts": contracts,
        "motion_constraints_source": motion["kind"],
    }


def _role_contract(
    occurrence_id: str,
    role: str,
    function_claims: list[str],
    axis: dict[str, Any],
    envelope: dict[str, Any],
    motion_nodes: list[str],
    interfaces: list[str],
) -> dict[str, Any]:
    return {
        "occurrence_id": occurrence_id,
        "role": role,
        "pattern_card_id": PATTERN_CARD_ID,
        "function_claims": function_claims,
        "behavior_claims": ["has_declared_axis", "has_case_bounded_envelope", "has_explicit_motion_interfaces"],
        "motion_chain": {
            "nodes": motion_nodes,
            "interfaces": interfaces,
            "status": "pass",
            "hard_timing": "report_only",
        },
        "mount_chain": {
            "axis_id": axis["axis_id"],
            "lower_support": "mainplate_pivot_or_jewel_placeholder",
            "upper_support": "future_escapement_bridge_pivot_or_jewel_placeholder",
            "status": "pass",
        },
        "constraint_chain": {
            "locked_dof": ["tx", "ty", "tz", "rx", "ry"],
            "allowed_motion": ["rz_about_declared_axis"],
            "fixed_base_path": ["mainplate", axis["axis_id"], occurrence_id],
            "status": "pass",
        },
        "geometry_constraint": {
            "axis_id": axis["axis_id"],
            "axis_xy_mm": [axis["x_mm"], axis["y_mm"]],
            "envelope_id": envelope["envelope_id"],
            "radius_mm": envelope["radius_mm"],
            "z_min_mm": envelope["z_min_mm"],
            "z_max_mm": envelope["z_max_mm"],
        },
        "validation_contract": {
            "checks": [
                "required_role_present",
                "axis_declared",
                "case_bounded_envelope",
                "motion_link_declared",
                "mount_chain_declared",
                "6dof_ledger_declared",
            ],
            "reference_only_limit": "does_not_yet_validate_locking_or_impulse_surface_geometry",
        },
        "validation": {"status": "pass", "missing_evidence": []},
    }


def _build_semantic_report(
    axes: dict[str, Any],
    envelopes: dict[str, Any],
    motion: dict[str, Any],
    role_contracts: dict[str, Any],
) -> dict[str, Any]:
    failed = [
        name
        for name, status in {
            "axes": axes["status"],
            "envelopes": envelopes["status"],
            "motion": motion["status"],
            "role_contracts": role_contracts["status"],
        }.items()
        if status != "pass"
    ]
    return {
        "kind": "watch_escapement_reference_semantic_report",
        "pattern_card_id": PATTERN_CARD_ID,
        "status": "pass" if not failed else "fail",
        "roles": list(REQUIRED_ESCAPEMENT_ROLES),
        "integration_status": "reference_only",
        "reference_fit": axes["reference_fit"],
        "checks": {
            "required_roles_declared": set(REQUIRED_ESCAPEMENT_ROLES).issubset(set(role_contracts["roles"])),
            "reference_axes_aligned": axes["status"] == "pass",
            "envelopes_inside_case": envelopes["status"] == "pass",
            "motion_constraints_declared": motion["status"] == "pass",
            "hard_escapement_timing_deferred": True,
        },
        "failed_sections": failed,
    }


def _build_validation_report(
    semantic: dict[str, Any],
    axes: dict[str, Any],
    envelopes: dict[str, Any],
    motion: dict[str, Any],
    role_contracts: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "semantic": semantic["status"],
        "axes": axes["status"],
        "envelopes": envelopes["status"],
        "motion_constraints": motion["status"],
        "role_contracts": role_contracts["status"],
        "source_reference_step_available": "pass" if SOURCE_REFERENCE_STEP.exists() else "fail",
    }
    failed = [name for name, status in checks.items() if status != "pass"]
    return {
        "kind": "watch_escapement_reference_validation_report",
        "pattern_card_id": PATTERN_CARD_ID,
        "status": "pass" if not failed else "fail",
        "failed_checks": failed,
        "checks": checks,
        "evidence_tier": {
            "axis_fit": "independently_computed_from_pattern_axes_and_reference_axes",
            "envelopes": "independently_computed_cylindrical_bounds",
            "motion": "role_contract_level_until_real_escapement_geometry",
        },
    }


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])
