"""Reference artifact for open-spoked watch wheel visuals."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from build123d import Compound, Location, export_step

from .power_chain_mvp import (
    _extrude_xy_points_preserve_frame,
    _gear_body,
    _label,
    _z_cylinder,
)


REFERENCE_TOOTH_COUNT = 64
REFERENCE_MODULE_MM = 0.155
REFERENCE_HEIGHT_MM = 0.34
REFERENCE_BORE_RADIUS_MM = 0.18


def run_spoked_gear_reference(output_dir: Path, *, seed: int = 731) -> dict[str, Any]:
    """Generate a four-variant STEP reference for 2/3/4/5 spoke watch wheels."""

    output_dir.mkdir(parents=True, exist_ok=True)
    step_path = output_dir / "watch_spoked_gear_reference.step"
    contract_path = output_dir / "watch_spoked_gear_reference.visual_contract.json"

    variants = [
        _spoked_gear_variant(spoke_count, index=index, seed=seed)
        for index, spoke_count in enumerate([2, 3, 4, 5])
    ]
    assembly = Compound(
        label="watch_spoked_gear_reference",
        children=[variant["shape"] for variant in variants],
    )
    export_step(assembly, step_path)

    contract = {
        "artifact": "watch_spoked_gear_reference",
        "seed": seed,
        "status": "pass",
        "purpose": "single-function reference artifact for open-spoked watch wheel visuals",
        "variants": [_variant_contract(variant) for variant in variants],
    }
    contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")

    return {
        "status": "pass",
        "seed": seed,
        "artifacts": {
            "step": str(step_path),
            "visual_contract_json": str(contract_path),
        },
    }


def _spoked_gear_variant(spoke_count: int, *, index: int, seed: int) -> dict[str, Any]:
    gear = _reference_gear(spoke_count, seed=seed)
    x_offset = (index - 1.5) * 14.0
    shape = _make_open_spoked_wheel(gear, label=f"spoked_watch_wheel_{spoke_count}_spokes").located(
        Location((x_offset, 0.0, 0.0))
    )
    return {
        "shape": shape,
        "spoke_count": spoke_count,
        "x_offset": x_offset,
        **gear,
    }


def _reference_gear(spoke_count: int, *, seed: int) -> dict[str, Any]:
    pitch_radius = REFERENCE_MODULE_MM * REFERENCE_TOOTH_COUNT / 2.0
    outer_radius = pitch_radius + REFERENCE_MODULE_MM * 0.82
    root_radius = pitch_radius - REFERENCE_MODULE_MM * 0.95
    hub_outer_radius = max(0.48, root_radius * 0.165)
    rim_inner_radius = root_radius * 0.865
    phase_deg = (seed % 17) * 360.0 / REFERENCE_TOOTH_COUNT / 17.0
    return {
        "gear_id": f"reference_{spoke_count}_spoke_watch_wheel",
        "gear_type": "wheel",
        "tooth_count": REFERENCE_TOOTH_COUNT,
        "pitch_radius": pitch_radius,
        "outer_radius": outer_radius,
        "root_radius": root_radius,
        "rim_inner_radius": rim_inner_radius,
        "hub_outer_radius": hub_outer_radius,
        "bore_radius": REFERENCE_BORE_RADIUS_MM,
        "height": REFERENCE_HEIGHT_MM,
        "phase_deg": phase_deg,
        "spoke_count": spoke_count,
        "spoke_inner_overlap_mm": 0.16,
        "spoke_outer_overlap_mm": 0.20,
    }


def _make_open_spoked_wheel(gear: dict[str, Any], *, label: str):
    rim_inner = float(gear["rim_inner_radius"])
    hub_outer = float(gear["hub_outer_radius"])
    bore = float(gear["bore_radius"])
    height = float(gear["height"])
    spoke_count = int(gear["spoke_count"])

    body = _gear_body(gear)
    bore_cutter = _z_cylinder(bore, height + 0.12).located(Location((0.0, 0.0, height / 2.0)))
    body = body - bore_cutter

    pitch = 2.0 * math.pi / spoke_count
    phase = math.radians(float(gear["phase_deg"]))
    for index in range(spoke_count):
        cutter = _annular_sector_cutter(
            gear=gear,
            inner_radius=hub_outer,
            outer_radius=rim_inner,
            start_spoke_angle=phase + index * pitch,
            end_spoke_angle=phase + (index + 1) * pitch,
            height=height + 0.12,
        ).located(Location((0.0, 0.0, -0.06)))
        body = body - cutter

    return _label(body, label)


def _spoke_width_mm(gear: dict[str, Any], radial_fraction: float) -> float:
    """Width of one retained spoke at a normalized radius from hub to rim."""

    hub_outer = float(gear["hub_outer_radius"])
    t = max(0.0, min(1.0, radial_fraction))
    mid_width = max(0.085, hub_outer * 0.11)
    hub_width = max(0.20, hub_outer * 0.34)
    rim_width = max(0.145, hub_outer * 0.21)
    if t <= 0.5:
        blend = t / 0.5
        return hub_width * (1.0 - blend) + mid_width * blend
    blend = (t - 0.5) / 0.5
    return mid_width * (1.0 - blend) + rim_width * blend


def _annular_sector_cutter(
    *,
    gear: dict[str, Any],
    inner_radius: float,
    outer_radius: float,
    start_spoke_angle: float,
    end_spoke_angle: float,
    height: float,
):
    radial_steps = 7
    angular_steps = max(10, int(math.degrees(end_spoke_angle - start_spoke_angle) // 7))
    cutter = None

    def edge_angles(t: float) -> tuple[float, float]:
        radius = inner_radius + (outer_radius - inner_radius) * t
        half_angle = (_spoke_width_mm(gear, t) / 2.0) / max(radius, 1e-6)
        return start_spoke_angle + half_angle, end_spoke_angle - half_angle

    def polar_point(t: float, u: float) -> tuple[float, float]:
        radius = inner_radius + (outer_radius - inner_radius) * t
        left_angle, right_angle = edge_angles(t)
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


def _variant_contract(variant: dict[str, Any]) -> dict[str, Any]:
    spoke_count = int(variant["spoke_count"])
    return {
        "gear_id": variant["gear_id"],
        "spoke_count": spoke_count,
        "role_contract": {
            "visual_role": "open_spoked_watch_wheel",
            "feature_attachment_chain": "spokes overlap both hub and tooth rim",
            "motion_role": "visual wheel body only; no ratio or mesh claim in this reference artifact",
        },
        "features": [
            "tooth_rim",
            "hub",
            *[f"spoke_{index + 1}" for index in range(spoke_count)],
            "open_cutouts",
        ],
        "tooth_count": variant["tooth_count"],
        "outer_radius_mm": round(variant["outer_radius"], 4),
        "root_radius_mm": round(variant["root_radius"], 4),
        "rim_inner_radius_mm": round(variant["rim_inner_radius"], 4),
        "hub_outer_radius_mm": round(variant["hub_outer_radius"], 4),
        "bore_radius_mm": round(variant["bore_radius"], 4),
        "spoke_inner_overlap_mm": variant["spoke_inner_overlap_mm"],
        "spoke_outer_overlap_mm": variant["spoke_outer_overlap_mm"],
        "spoke_width_at_hub_mm": round(_spoke_width_mm(variant, 0.0), 4),
        "spoke_width_at_mid_mm": round(_spoke_width_mm(variant, 0.5), 4),
        "spoke_width_at_rim_mm": round(_spoke_width_mm(variant, 1.0), 4),
    }
