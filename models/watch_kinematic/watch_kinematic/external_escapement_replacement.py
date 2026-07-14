from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Any

import build123d as bd

from . import power_chain_mvp


WATCH_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = WATCH_ROOT / "references" / "escapement" / "swiss_lever_grabcad_snapshot_15"
SOURCE_STEP = REFERENCE_DIR / "Escapement Model.STEP"

# The OpenSCAD source for the downloaded Swiss lever model places the escape
# arbor at (0, 0) and the balance staff at approximately (0, 89.06).
SOURCE_ESCAPE_AXIS_XY = (0.0, 0.0)
SOURCE_BALANCE_AXIS_XY = (0.0, 89.06)
REFERENCE_PLATE_SOURCE_INDEX = 4

EXCLUDED_SOURCE_SOLID_INDICES: tuple[int, ...] = (11, 14, 18)
SOURCE_SOLID_ROLE_OVERRIDES: dict[int, dict[str, str]] = {
    0: {
        "occurrence_id": "external_escape_wheel",
        "role": "escape_wheel",
        "reason": "largest source solid centered on the source escape arbor",
    },
    1: {
        "occurrence_id": "external_pallet_fork",
        "role": "pallet_fork",
        "reason": "source solid between the escape arbor and balance staff",
    },
    2: {
        "occurrence_id": "external_balance_wheel",
        "role": "balance_wheel",
        "reason": "large circular source solid centered on the balance staff region",
    },
    3: {
        "occurrence_id": "external_hairspring",
        "role": "hairspring",
        "reason": "thin source solid inside the balance envelope",
    },
    REFERENCE_PLATE_SOURCE_INDEX: {
        "occurrence_id": "external_escapement_reference_plate",
        "role": "escapement_reference_plate",
        "reason": "source assembly plate that preserves the escapement component positioning and support relationship",
    },
    5: {
        "occurrence_id": "external_escape_staff",
        "role": "escape_wheel_staff",
        "reason": "coaxial shaft on the source escape arbor",
    },
    10: {
        "occurrence_id": "external_escape_upper_cap",
        "role": "escape_wheel_upper_retainer",
        "reason": "upper retaining feature on the source escape arbor",
    },
    15: {
        "occurrence_id": "external_escape_upper_fixed_hardware",
        "role": "escape_wheel_upper_fixed_hardware",
        "reason": "upper fixed hardware on the source escape arbor",
    },
    18: {
        "occurrence_id": "external_balance_staff",
        "role": "balance_staff",
        "reason": "coaxial shaft through the source balance wheel",
    },
    11: {
        "occurrence_id": "external_balance_upper_cap",
        "role": "balance_upper_retainer",
        "reason": "upper retaining feature on the source balance staff",
    },
    14: {
        "occurrence_id": "external_balance_upper_fixed_hardware",
        "role": "balance_upper_fixed_hardware",
        "reason": "upper fixed hardware on the source balance staff",
    },
}


def build_external_escapement_replacement(output_dir: str | Path, *, seed: int = 123, include_bridges: bool = False) -> dict[str, Any]:
    """Replace generated escapement placeholders with selected external STEP solids."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    design = power_chain_mvp._build_design(seed, include_bridges=include_bridges)
    base = power_chain_mvp._build_assembly(
        design,
        omit_escapement_placeholders=True,
        omit_gear_ids={"escape_wheel"},
    )
    base.label = "watch_power_chain_without_self_made_escapement"

    external, role_map = build_external_escapement_parts(design)
    assembly = bd.Compound(
        children=[base, external],
        label="watch_power_chain_with_scaled_swiss_lever_reference",
    )

    step_basename = (
        "watch_power_chain_with_bridges_and_scaled_swiss_lever_reference"
        if include_bridges
        else "watch_power_chain_with_scaled_swiss_lever_reference"
    )
    step_path = target / f"{step_basename}.step"
    alias_step_path = target / (
        "watch_power_chain_with_bridges_and_external_escapement.step"
        if include_bridges
        else "watch_power_chain_with_external_escapement.step"
    )
    external_step_path = target / "swiss_lever_escapement_selected_external_parts.step"
    fit_report_path = target / "swiss_lever_escapement_fit_report.json"
    role_map_path = target / "watch_external_escapement_replacement.role_map.json"
    validation_path = target / "watch_external_escapement_replacement.validation.json"

    bd.export_step(external, external_step_path)
    bd.export_step(assembly, step_path)
    bd.export_step(assembly, alias_step_path)

    validation = _build_validation_report(step_path, external, role_map, design)
    motion_artifacts = power_chain_mvp.write_power_chain_motion_artifacts(
        step_path,
        design,
        external_escapement=True,
    )
    fit_report_path.write_text(
        json.dumps(
            {
                "kind": "swiss_lever_escapement_fit_report",
                "status": validation["status"],
                "integration_mode": "selected_external_step_solids_replace_generated_escapement_placeholders",
                "source_step": role_map["source_step"],
                "fit": role_map["fit"],
                "included_source_solids": role_map["included_source_solids"],
                "excluded_source_solid_indices": role_map["excluded_source_solid_indices"],
                "validation": validation,
                "caveats": role_map["caveats"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    role_map_path.write_text(json.dumps(role_map, indent=2), encoding="utf-8")
    validation_path.write_text(json.dumps(validation, indent=2), encoding="utf-8")

    return {
        "status": validation["status"],
        "artifacts": {
            "step": str(step_path),
            "alias_step": str(alias_step_path),
            "external_step": str(external_step_path),
            "step_module_js": motion_artifacts["step_module_js"],
            "motion_json": motion_artifacts["motion_json"],
            "fit_report_json": str(fit_report_path),
            "role_map_json": str(role_map_path),
            "validation_json": str(validation_path),
        },
    }


def build_external_escapement_bridge_stage(output_dir: str | Path, *, seed: int = 123) -> dict[str, Any]:
    return build_external_escapement_replacement(output_dir, seed=seed, include_bridges=True)


def build_external_escapement_parts(design: dict[str, Any]) -> tuple[bd.Compound, dict[str, Any]]:
    fit = _fit_transform(design)
    source_solids = _source_leaf_solids()
    included = []
    transformed_parts = []
    for source_index, source_solid in enumerate(source_solids):
        if source_index in EXCLUDED_SOURCE_SOLID_INDICES:
            continue
        entry = _source_solid_entry(source_index)
        source_index = int(entry["source_solid_index"])
        transformed = source_solid.scale(float(fit["scale"]))
        transformed = transformed.rotate(bd.Axis.Z, float(fit["rotation_deg_about_z"]))
        transformed = transformed.translate(tuple(fit["translation_mm"]))
        transformed.label = str(entry["occurrence_id"])
        power_chain_mvp._apply_review_material(transformed, str(entry["occurrence_id"]))
        bounds = _bounds(transformed)
        transformed_parts.append(transformed)
        included.append(
            {
                **entry,
                "source_bounds_mm": _bounds(source_solid),
                "transformed_bounds_mm": bounds,
            }
        )

    generated_replacement_parts, generated_replacements = _generated_balance_axis_replacement_parts(design)
    transformed_parts.extend(generated_replacement_parts)

    external = bd.Compound(children=transformed_parts, label="external_swiss_lever_escapement_replacement")
    role_map = {
        "kind": "watch_external_escapement_replacement_role_map",
        "status": "pass",
        "source_step": str(SOURCE_STEP),
        "fit": fit,
        "included_source_solids": included,
        "excluded_source_solid_indices": list(EXCLUDED_SOURCE_SOLID_INDICES),
        "generated_replacement_solids": generated_replacements,
        "caveats": [
            "This is a physical STEP-child mapping layered on top of the earlier role-contract semantics.",
            "The downloaded source STEP has generic SOLID names, so source indices are pinned by observed geometry and OpenSCAD source axes.",
            "The external escapement is inserted as one complete subassembly after the solver fixes the escape-wheel and balance-wheel axes.",
        ],
    }
    return external, role_map


def _generated_balance_axis_replacement_parts(design: dict[str, Any]) -> tuple[list[bd.Shape], list[dict[str, Any]]]:
    axis = next(axis for axis in design["axes"] if axis["axis_id"] == "balance_axis")
    upper_top = float(design["z_stack"]["future_bridge"]["future_upper_jewel_top_z_mm"])
    staff_z_min = power_chain_mvp.MAINPLATE_BOTTOM_Z
    staff_height = upper_top - staff_z_min
    staff_radius = 0.09
    x = float(axis["x"])
    y = float(axis["y"])
    staff = power_chain_mvp._z_cylinder(staff_radius, staff_height).located(
        bd.Location((x, y, staff_z_min + staff_height / 2.0))
    )
    staff.label = "external_balance_replacement_staff"
    power_chain_mvp._apply_review_material(staff, "external_balance_replacement_staff")

    bearing_height = power_chain_mvp.LOWER_JEWEL_HEIGHT_MM
    bearing_inner_radius = staff_radius + power_chain_mvp.MINIMUM_BORE_CLEARANCE_MM + 0.02
    bearing_outer_radius = max(0.32, bearing_inner_radius + 0.16)
    bearing_z_min = upper_top - bearing_height
    bearing = power_chain_mvp._annulus(bearing_outer_radius, bearing_inner_radius, bearing_height).located(
        bd.Location((x, y, bearing_z_min + bearing_height / 2.0))
    )
    bearing.label = "external_balance_upper_jewel_bearing"
    power_chain_mvp._apply_review_material(bearing, "external_balance_upper_jewel_bearing")

    replacements = [
        {
            "occurrence_id": "external_balance_replacement_staff",
            "role": "generated_balance_staff",
            "axis_id": "balance_axis",
            "replacement_for_source_solid_indices": [18],
            "z_min_mm": round(staff_z_min, 4),
            "z_max_mm": round(upper_top, 4),
            "radius_mm": staff_radius,
            "reason": "replace source screw-like balance staff with project-consistent watch arbor",
        },
        {
            "occurrence_id": "external_balance_upper_jewel_bearing",
            "role": "generated_balance_upper_jewel_bearing",
            "axis_id": "balance_axis",
            "replacement_for_source_solid_indices": [11, 14],
            "z_min_mm": round(bearing_z_min, 4),
            "z_max_mm": round(upper_top, 4),
            "inner_radius_mm": round(bearing_inner_radius, 4),
            "outer_radius_mm": round(bearing_outer_radius, 4),
            "reason": "replace source upper screw/nut hardware with uniform upper jewel bearing plane",
        },
    ]
    return [staff, bearing], replacements

def _source_solid_entry(source_index: int) -> dict[str, Any]:
    override = SOURCE_SOLID_ROLE_OVERRIDES.get(source_index)
    if override:
        return {"source_solid_index": source_index, **override}
    return {
        "source_solid_index": source_index,
        "occurrence_id": f"external_escapement_auxiliary_solid_{source_index:02d}",
        "role": "escapement_auxiliary_hardware",
        "reason": "non-base source solid retained to preserve the external escapement's shaft, retainer, and support details",
    }


def _source_leaf_solids() -> list[bd.Shape]:
    imported = bd.import_step(SOURCE_STEP)
    solids = _leaf_shapes(imported)
    if len(solids) < 5:
        raise ValueError(f"expected at least 5 source solids in {SOURCE_STEP}, found {len(solids)}")
    return solids


def _leaf_shapes(shape: bd.Shape) -> list[bd.Shape]:
    children = list(getattr(shape, "children", []) or [])
    if not children:
        return [shape]
    leaves: list[bd.Shape] = []
    for child in children:
        leaves.extend(_leaf_shapes(child))
    return leaves


def _fit_transform(design: dict[str, Any]) -> dict[str, Any]:
    target_escape = _axis_xy(design, "escape_axis")
    target_balance = _axis_xy(design, "balance_axis")
    source_dx = SOURCE_BALANCE_AXIS_XY[0] - SOURCE_ESCAPE_AXIS_XY[0]
    source_dy = SOURCE_BALANCE_AXIS_XY[1] - SOURCE_ESCAPE_AXIS_XY[1]
    target_dx = target_balance[0] - target_escape[0]
    target_dy = target_balance[1] - target_escape[1]
    source_distance = math.hypot(source_dx, source_dy)
    target_distance = math.hypot(target_dx, target_dy)
    scale = target_distance / source_distance
    rotation_deg = math.degrees(math.atan2(target_dy, target_dx) - math.atan2(source_dy, source_dx)) % 360.0
    source_plate = _source_leaf_solids()[REFERENCE_PLATE_SOURCE_INDEX]
    source_plate_bounds = _bounds(source_plate)
    source_plate_lower_z = float(source_plate_bounds["min"][2])
    mainplate_top_z = power_chain_mvp.MAINPLATE_TOP_Z
    target_z_origin = mainplate_top_z - source_plate_lower_z * scale
    transformed_plate_lower_z = source_plate_lower_z * scale + target_z_origin
    z_gap = transformed_plate_lower_z - mainplate_top_z
    return {
        "source_escape_axis_xy_mm": SOURCE_ESCAPE_AXIS_XY,
        "source_balance_axis_xy_mm": SOURCE_BALANCE_AXIS_XY,
        "target_escape_axis_xy_mm": target_escape,
        "target_balance_axis_xy_mm": target_balance,
        "source_escape_to_balance_distance_mm": source_distance,
        "target_escape_to_balance_distance_mm": target_distance,
        "scale": scale,
        "rotation_deg_about_z": rotation_deg,
        "translation_mm": [target_escape[0], target_escape[1], target_z_origin],
        "target_z_origin_policy": "reference_plate_lower_face_flush_to_mainplate_top",
        "plate_to_mainplate_mate": {
            "occurrence_id": "external_escapement_reference_plate",
            "source_solid_index": REFERENCE_PLATE_SOURCE_INDEX,
            "source_plate_lower_z_mm": round(source_plate_lower_z, 6),
            "source_plate_lower_z_after_scale_mm": round(source_plate_lower_z * scale, 6),
            "transformed_plate_lower_z_mm": round(transformed_plate_lower_z, 6),
            "mainplate_top_z_mm": round(mainplate_top_z, 6),
            "z_gap_mm": round(z_gap, 6),
            "tolerance_mm": 0.01,
        },
    }


def _train_top_z_without_generated_escape_wheel(design: dict[str, Any]) -> float:
    top_z = max(
        float(gear["z"]) + float(gear["height"]) + 0.08
        for gear in design["gears"]
        if gear["gear_id"] != "escape_wheel"
    )
    return round(top_z, 6)


def _axis_xy(design: dict[str, Any], axis_id: str) -> tuple[float, float]:
    axis = next(axis for axis in design["axes"] if axis["axis_id"] == axis_id)
    return (float(axis["x"]), float(axis["y"]))


def _build_validation_report(
    step_path: Path,
    external: bd.Compound,
    role_map: dict[str, Any],
    design: dict[str, Any],
) -> dict[str, Any]:
    step_text = step_path.read_text(encoding="utf-8", errors="ignore")
    role_labels = [entry["occurrence_id"] for entry in role_map["included_source_solids"]]
    generated_labels = [entry["occurrence_id"] for entry in role_map.get("generated_replacement_solids", [])]
    removed_balance_labels = [
        SOURCE_SOLID_ROLE_OVERRIDES[source_index]["occurrence_id"]
        for source_index in EXCLUDED_SOURCE_SOLID_INDICES
    ]
    train_top_z = _train_top_z_without_generated_escape_wheel(design)
    same_layer_clearance = _same_layer_fourth_wheel_balance_clearance(role_map, design)
    plate_entry = next(
        entry
        for entry in role_map["included_source_solids"]
        if entry["source_solid_index"] == REFERENCE_PLATE_SOURCE_INDEX
    )
    plate_mate = role_map["fit"]["plate_to_mainplate_mate"]
    plate_gap = float(plate_entry["transformed_bounds_mm"]["min"][2]) - float(plate_mate["mainplate_top_z_mm"])
    checks = {
        "self_made_escapement_placeholders_removed": _pass_fail(
            all(
                label not in step_text
                for label in (
                    "pallet_placeholder_disc",
                    "balance_placeholder_disc",
                    "escapement_to_balance_placeholder_envelope",
                )
            )
        ),
        "generated_escape_wheel_removed": _pass_fail(re.search(r"PRODUCT\('escape_wheel'", step_text) is None),
        "external_role_solids_present": _pass_fail(all(label in step_text for label in role_labels)),
        "external_escape_staff_and_upper_hardware_present": _pass_fail(
            all(
                label in step_text
                for label in (
                    "external_escape_staff",
                    "external_escape_upper_cap",
                )
            )
        ),
        "external_balance_source_staff_hardware_removed": _pass_fail(
            all(label not in step_text for label in removed_balance_labels)
            and sorted(role_map["excluded_source_solid_indices"]) == sorted(EXCLUDED_SOURCE_SOLID_INDICES)
        ),
        "generated_balance_staff_and_upper_bearing_present": _pass_fail(
            all(label in step_text for label in generated_labels)
            and {"external_balance_replacement_staff", "external_balance_upper_jewel_bearing"}.issubset(set(generated_labels))
        ),
        "external_source_solids_retained_except_replaced_balance_hardware": _pass_fail(
            len(role_map["included_source_solids"]) == len(_source_leaf_solids()) - len(EXCLUDED_SOURCE_SOLID_INDICES)
        ),
        "external_reference_plate_retained": _pass_fail("external_escapement_reference_plate" in step_text),
        "external_reference_plate_lower_face_mated_to_mainplate": _pass_fail(
            abs(plate_gap) <= float(plate_mate["tolerance_mm"])
            and abs(float(plate_mate["z_gap_mm"])) <= float(plate_mate["tolerance_mm"])
        ),
        "same_layer_fourth_wheel_external_balance_clearance": _pass_fail(same_layer_clearance["status"] == "pass"),
        "bridge_stage_three_bridge_plates_present": _pass_fail(
            not design.get("bridges_generated")
            or all(label in step_text for label in ("barrel_bridge", "train_bridge", "escapement_bridge"))
        ),
    }
    failed = [name for name, status in checks.items() if status != "pass"]
    return {
        "kind": "watch_external_escapement_replacement_validation",
        "status": "pass" if not failed else "fail",
        "failed_checks": failed,
        "checks": checks,
        "train_top_z_without_generated_escape_wheel_mm": train_top_z,
        "external_bounds_mm": _bounds(external),
        "external_reference_plate_to_mainplate_mate": {
            **plate_mate,
            "observed_transformed_plate_lower_z_mm": round(float(plate_entry["transformed_bounds_mm"]["min"][2]), 6),
            "observed_z_gap_mm": round(plate_gap, 6),
        },
        "allowed_interference_exceptions": [
            {
                "exception_id": "under_reference_plate_imported_geometry_may_overlap_mainplate",
                "owner": "external_escapement_reference_plate",
                "reference_face": "lower_face_mated_to_foundation_mainplate_top",
                "scope": "imported external solids or subfeatures below the reference plate lower face",
                "reason": "phase-level integration keeps the downloaded escapement assembly intact; below-face source details may embed into the mainplate until a production support bridge is remodeled.",
            }
        ],
        "same_layer_fourth_wheel_external_balance_clearance": same_layer_clearance,
    }


def _same_layer_fourth_wheel_balance_clearance(role_map: dict[str, Any], design: dict[str, Any]) -> dict[str, Any]:
    gear = next(gear for gear in design["gears"] if gear["gear_id"] == "fourth_wheel")
    fourth_axis = next(axis for axis in design["axes"] if axis["axis_id"] == gear["axis_id"])
    balance_axis = next(axis for axis in design["axes"] if axis["axis_id"] == "balance_axis")
    balance_entry = next(entry for entry in role_map["included_source_solids"] if entry["role"] == "balance_wheel")
    balance_bounds = balance_entry["transformed_bounds_mm"]
    balance_radius = max(balance_bounds["size"][0], balance_bounds["size"][1]) / 2.0
    center_distance = math.hypot(fourth_axis["x"] - balance_axis["x"], fourth_axis["y"] - balance_axis["y"])
    hard_contact_distance = gear["outer_radius"] + balance_radius
    minimum_clearance = 0.25
    clearance = center_distance - hard_contact_distance
    return {
        "proof_id": "same_layer_fourth_wheel_external_balance_clearance",
        "first_entity": "fourth_wheel",
        "second_entity": "external_balance_wheel",
        "center_distance_mm": round(center_distance, 6),
        "fourth_wheel_outer_radius_mm": gear["outer_radius"],
        "external_balance_radius_mm": round(balance_radius, 6),
        "clearance_mm": round(clearance, 6),
        "minimum_clearance_mm": minimum_clearance,
        "status": "pass" if clearance >= minimum_clearance else "fail",
    }


def _pass_fail(value: bool) -> str:
    return "pass" if value else "fail"


def _bounds(shape: bd.Shape) -> dict[str, list[float]]:
    box = shape.bounding_box()
    return {
        "min": [box.min.X, box.min.Y, box.min.Z],
        "max": [box.max.X, box.max.Y, box.max.Z],
        "size": [
            box.max.X - box.min.X,
            box.max.Y - box.min.Y,
            box.max.Z - box.min.Z,
        ],
    }


