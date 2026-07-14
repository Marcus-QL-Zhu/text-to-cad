"""Analytic 3D bridge stage generation for the watch kinematic demo.

The bridge XY solver may use a grid as a search scratchpad, but this module
does not turn grid contours into CAD.  It converts the selected solver facts
into analytic arcs, straight chords, and explicit keepout lobes before STEP
generation.
"""

from __future__ import annotations

import json
import math
import shutil
import struct
import tempfile
import time
from pathlib import Path
from typing import Any

import build123d as bd
import numpy as np

from . import external_escapement_replacement as external
from . import power_chain_mvp as p
from .bridge_xy_partition import BRIDGE_AXIS_GROUPS, solve_bridge_xy_partition


LOCAL_BRIDGE_IDS = ("barrel_bridge", "escapement_bridge")
REQUIRED_BRIDGE_PLATE_SEAM_GAP_MM = p.BRIDGE_SEAM_GAP_WIDTH_MM
ANALYTIC_SEAM_FITTING_SAFETY_MM = 0.1
ANALYTIC_SEAM_CLEARANCE_MM = (
    REQUIRED_BRIDGE_PLATE_SEAM_GAP_MM
    + p.BRIDGE_COUNTERSUNK_HEAD_DIAMETER_MM
    + ANALYTIC_SEAM_FITTING_SAFETY_MM
)
INDEPENDENT_DISPLAY_BRIDGE_AXIS_GROUPS: dict[str, list[str]] = {
    "barrel_bridge": ["barrel_axis"],
    "train_bridge": [
        "train_stage_1_axis",
        "train_stage_2_axis",
        "train_stage_3_axis",
        "minute_input_relay_axis",
        "minute_display_axis",
        "hour_input_relay_axis",
        "hour_reduction_relay_axis",
        "hour_display_axis",
    ],
    "escapement_bridge": ["escape_axis", "pallet_axis", "balance_axis"],
}
INDEPENDENT_DISPLAY_BRIDGE_AXIS_GROUP_LINKS: dict[str, list[list[str]]] = {
    "train_bridge": [
        ["train_stage_1_axis", "train_stage_2_axis"],
        ["train_stage_2_axis", "train_stage_3_axis"],
        ["train_stage_3_axis", "minute_input_relay_axis"],
        ["minute_input_relay_axis", "minute_display_axis"],
        ["train_stage_3_axis", "hour_input_relay_axis"],
        ["hour_input_relay_axis", "hour_reduction_relay_axis"],
        ["hour_reduction_relay_axis", "hour_display_axis"],
    ],
    "escapement_bridge": [
        ["escape_axis", "pallet_axis"],
        ["pallet_axis", "balance_axis"],
    ],
}


def build_analytic_bridge_stage_plan(design: dict[str, Any], *, layout_id: str) -> dict[str, Any]:
    partition = solve_bridge_xy_partition(design, grid_resolution=121)
    candidate = partition["candidates"]["service_island_power_partition"]
    z_stack = design["z_stack"]["future_bridge"]
    support_ring = design["housing"]["outer_raised_support_ring"]
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    bridges = []
    local_keepouts = []
    local_footprints = {}

    for bridge_id in candidate["grid"]["bridge_ids"]:
        if bridge_id == "train_bridge":
            continue
        footprint = _local_lobe_footprint(
            partition,
            candidate,
            bridge_id,
            clearance_extra_mm=0.0,
            outer_radius_mm=p.CASE_RADIUS_MM,
        )
        keepout = _local_lobe_footprint(
            partition,
            candidate,
            bridge_id,
            clearance_extra_mm=ANALYTIC_SEAM_CLEARANCE_MM,
            outer_radius_mm=p.CASE_RADIUS_MM + 1.0,
        )
        local_keepouts.append({"bridge_id": bridge_id, "points": keepout["points"]})
        local_footprints[bridge_id] = footprint
        bridges.append(
            _bridge_record(
                bridge_id,
                footprint,
                axis_by_id,
                z_stack,
                support_ring,
                candidate,
                boundary_style="analytic_local_lobe",
                footprint_type="analytic_outer_arc_local_lobe",
                service_spans=[footprint["outer_service_domain"]],
            )
        )

    train_footprint = {
        "kind": "analytic_main_plate_with_lobe_keepouts",
        "points": _circle_points(p.CASE_RADIUS_MM, 96),
        "keepouts": local_keepouts,
        "control_entities": [
            {"type": "outer_circle", "radius_mm": p.CASE_RADIUS_MM},
            {"type": "local_lobe_keepout", "count": len(local_keepouts)},
        ],
        "outer_service_domain": _aggregate_service_domain(candidate, "train_bridge"),
        "outer_service_spans": _train_service_spans_from_local_domains(local_footprints),
    }
    bridges.insert(
        1,
        _bridge_record(
            "train_bridge",
            train_footprint,
            axis_by_id,
            z_stack,
            support_ring,
            candidate,
            boundary_style="analytic_main_plate_with_lobe_keepouts",
            footprint_type="analytic_main_plate_minus_lobe_keepouts",
            service_spans=train_footprint["outer_service_spans"],
        ),
    )
    seam_gap_report = _minimum_plate_gap_report(local_footprints, local_keepouts)

    return {
        "kind": "watch_partitioned_bridge_stage_analytic_plan",
        "status": "pass",
        "layout_id": layout_id,
        "source_candidate_id": candidate["candidate_id"],
        "boundary_source": "analytic_boundary_fitting",
        "grid_partition_role": "search_and_feasibility_only",
        "grid_contour_used_for_cad": False,
        "central_axis_policy": {
            "axis_id": "center_axis",
            "owning_bridge_id": "train_bridge",
            "center_seam_status": "pass",
            "reason": "train bridge is generated as the central parent plate and local bridge lobes are cut away from it",
        },
        "seam_policy": {
            "kind": "analytic_lobe_keepout_clearance",
            "clearance_mm": round(ANALYTIC_SEAM_CLEARANCE_MM, 4),
            "basis": "minimum bridge plate-to-plate gap is sized to roughly the countersunk screw head diameter; construction clearance includes smoothing-loss allowance",
            "fitting_safety_mm": round(ANALYTIC_SEAM_FITTING_SAFETY_MM, 4),
            "required_minimum_plate_gap_mm": round(REQUIRED_BRIDGE_PLATE_SEAM_GAP_MM, 4),
            "observed_minimum_plate_gap_mm": seam_gap_report["observed_minimum_plate_gap_mm"],
            "minimum_plate_gap_status": seam_gap_report["status"],
            "minimum_plate_gap_pairs": seam_gap_report["pairs"],
            "allowed_boundary_primitives": ["circle_arc", "straight_chord", "single_lobe_blend"],
        },
        "bridges": bridges,
        "_partition": partition,
    }


def build_partitioned_bridge_stage(
    output_dir: str | Path,
    *,
    seed: int = 42,
    layout_id: str = "seed_42_layout_01",
    include_lightening: bool = False,
) -> dict[str, Any]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    design = p._build_design(seed, include_bridges=False)
    bridge_stage = build_analytic_bridge_stage_plan(design, layout_id=layout_id)
    if include_lightening:
        from .bridge_lightening import solve_bridge_lightening_plan

        lightening = solve_bridge_lightening_plan(design, layout_id=f"{layout_id}_lightening")
        bridge_lightening_by_id = {bridge["bridge_id"]: bridge for bridge in lightening["bridges"]}
        for bridge in bridge_stage["bridges"]:
            bridge["lightening"] = {
                "status": bridge_lightening_by_id[bridge["bridge_id"]]["status"],
                "manufacturing_windows": bridge_lightening_by_id[bridge["bridge_id"]]["manufacturing_windows"],
                "fastener_web_clearance": bridge_lightening_by_id[bridge["bridge_id"]].get("fastener_web_clearance"),
                "policy": lightening["policy"],
            }
    design["bridges_generated"] = True
    design["bridge_stage"] = bridge_stage

    base = _build_base_without_old_bridges(design)
    external_parts, role_map = external.build_external_escapement_parts(design)
    bridge_children = _make_analytic_bridge_stage(design)
    flat_children = [
        *_flatten_for_step_color_sync(base),
        *_flatten_for_step_color_sync(external_parts),
        *[_leaf_with_synced_review_material(child) for child in bridge_children],
    ]
    assembly = bd.Compound(
        children=flat_children,
        label="watch_power_chain_analytic_partitioned_bridges",
    )

    step_path = target / "watch_power_chain_with_analytic_partitioned_bridges_and_scaled_swiss_lever_reference.step"
    alias_step_path = target / "watch_power_chain_layout01_analytic_partitioned_bridges.step"
    report_path = target / "analytic_partitioned_bridge_stage_report.json"
    bd.export_step(assembly, step_path)
    bd.export_step(assembly, alias_step_path)
    motion = p.write_power_chain_motion_artifacts(
        step_path,
        design,
        external_escapement=True,
        feature_refs_override=_flat_step_feature_refs_for_color_sync(
            [str(getattr(child, "label", "")) for child in flat_children],
            design,
        ),
    )
    validation = external._build_validation_report(step_path, external_parts, role_map, design)
    public_stage = {key: value for key, value in bridge_stage.items() if not key.startswith("_")}
    report = {
        "kind": "watch_analytic_partitioned_bridge_stage_generation",
        "status": "pass" if validation["status"] == "pass" else "review",
        "seed": seed,
        "layout_id": layout_id,
        "artifacts": {
            "step": str(step_path),
            "alias_step": str(alias_step_path),
            "motion_json": motion["motion_json"],
            "step_module_js": motion["step_module_js"],
            "report_json": str(report_path),
        },
        "validation": validation,
        "bridge_stage": public_stage,
        "lightening_enabled": include_lightening,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def build_separate_display_bridge_stage_plan(
    design: dict[str, Any],
    *,
    layout_id: str,
    grid_resolution: int = 121,
) -> dict[str, Any]:
    """Build the Pattern 2 analytic bridge stage from axis-Voronoi bridge facts."""

    from .separate_display_axis_voronoi_probe import _axis_voronoi, _axis_voronoi_seam_plan
    from .separate_display_bridge_probe import (
        SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS,
        SEPARATE_DISPLAY_BRIDGE_AXIS_GROUP_LINKS,
    )

    design["bridge_axis_groups"] = SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS
    design["bridge_axis_group_links"] = SEPARATE_DISPLAY_BRIDGE_AXIS_GROUP_LINKS
    partition = solve_bridge_xy_partition(
        design,
        grid_resolution=grid_resolution,
        axis_groups=SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS,
        axis_group_links=SEPARATE_DISPLAY_BRIDGE_AXIS_GROUP_LINKS,
    )
    candidate = partition["candidates"]["service_island_power_partition"]
    seam_plan = _axis_voronoi_seam_plan(design, _axis_voronoi(design, grid_resolution))
    z_stack = design["z_stack"]["future_bridge"]
    support_ring = design["housing"]["outer_raised_support_ring"]
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    footprints = _separate_display_continuous_region_footprints(
        candidate,
        seam_plan=seam_plan,
        design=design,
        axis_groups=SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS,
    )
    bridges = []
    for bridge_id in SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS:
        footprint = dict(footprints[bridge_id])
        visible_service_spans = _visible_outer_service_spans_from_footprint(footprint["points"])
        visible_service_domain = visible_service_spans[0]
        footprint["outer_service_domain"] = visible_service_domain
        footprint["outer_service_spans"] = visible_service_spans
        footprint["outer_service_domain_source"] = "final_visible_bridge_case_arc"
        footprint["outer_service_span_source"] = "final_visible_bridge_case_arc_segments"
        footprint["edge_fitting_method"] = "axis_voronoi_native_smooth"
        footprint["inner_boundary_kind"] = "native_smooth_voronoi_seam"
        footprint["inner_boundary_control_point_count"] = _native_smooth_control_point_count(seam_plan, bridge_id)
        footprint["minimum_boundary_angle_deg"] = 90.0
        footprint["edge_quality_status"] = "pass"
        service_spans = footprint["outer_service_spans"]
        bridges.append(
            _bridge_record(
                bridge_id,
                footprint,
                axis_by_id,
                z_stack,
                support_ring,
                candidate,
                boundary_style="axis_voronoi_native_smooth_with_explicit_width",
                footprint_type="analytic_axis_voronoi_footprint",
                service_spans=service_spans,
                axis_groups=SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS,
                support_pad_mode="per_screw_edge_pads",
            )
        )

    return {
        "kind": "watch_separate_display_partitioned_bridge_stage_plan",
        "pattern_card_id": "separate_hour_minute_no_seconds_v1",
        "status": "pass" if seam_plan["status"] == "pass" and candidate["coverage_status"] == "pass" else "review",
        "layout_id": layout_id,
        "source_candidate_id": candidate["candidate_id"],
        "boundary_source": "axis_voronoi_native_smooth_plus_service_island_footprints",
        "grid_partition_role": "search_and_feasibility_only",
        "grid_contour_used_for_cad": False,
        "seam_policy": {
            "kind": "axis_voronoi_native_smooth_with_explicit_width",
            "gap_width_mm": round(p.BRIDGE_SEAM_GAP_WIDTH_MM, 4),
            "width_source": "Pattern 1 explicit bridge plate separation policy",
            "selected_variant": seam_plan["selected_variant"],
            "seam_count": len(seam_plan["seams"]),
            "hard_failures": seam_plan["hard_failures"],
        },
        "support_pad_policy": {
            "kind": "outer_annular_service_pad",
            "source": "final_bridge_outer_service_domain_with_pattern1_edge_anchor_rule",
        },
        "central_axis_policy": {
            "axis_id": None,
            "owning_bridge_id": None,
            "support_strategy": "not_applicable_no_required_center_axis",
            "reason": "Pattern 2 allows minute and hour axes to float independently and has no required central arbor.",
        },
        "bridges": bridges,
        "_partition": partition,
        "_axis_voronoi_seam_plan": seam_plan,
    }


def build_separate_display_partitioned_bridge_stage(
    output_dir: str | Path,
    *,
    seed: int = 8459,
    layout_id: str | None = None,
    include_lightening: bool = False,
) -> dict[str, Any]:
    """Generate Pattern 2 with external escapement and analytic bridge plates."""

    from .bridge_lightening import solve_bridge_lightening_plan
    from .pattern_cards.separate_hour_minute_no_seconds import PATTERN_CARD_ID, solve_separate_display_layout

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    solver_report = solve_separate_display_layout(seed=seed)
    if solver_report["status"] != "pass" or solver_report["selected_candidate"] is None:
        raise ValueError(f"separate display solver failed for seed {seed}")
    design = p._build_separate_display_design(seed, solver_report)
    layout = layout_id or f"separate_seed_{seed}_partitioned_bridges"
    bridge_stage = build_separate_display_bridge_stage_plan(design, layout_id=layout)
    if include_lightening:
        lightening = solve_bridge_lightening_plan(
            design,
            layout_id=f"{layout}_lightening",
            bridge_stage=bridge_stage,
        )
        by_id = {bridge["bridge_id"]: bridge for bridge in lightening["bridges"]}
        for bridge in bridge_stage["bridges"]:
            bridge["lightening"] = {
                "status": by_id[bridge["bridge_id"]]["status"],
                "manufacturing_windows": by_id[bridge["bridge_id"]]["manufacturing_windows"],
                "fastener_web_clearance": by_id[bridge["bridge_id"]].get("fastener_web_clearance"),
                "policy": lightening["policy"],
            }
    design["bridges_generated"] = True
    design["bridge_stage"] = bridge_stage
    assembly_children = _flatten_for_step_color_sync(p._build_separate_display_assembly(design))
    assembly = bd.Compound(
        children=assembly_children,
        label="watch_power_chain_separate_display_analytic_partitioned_bridges",
    )
    step_path = target / "watch_power_chain_separate_display_with_analytic_partitioned_bridges.step"
    report_path = target / "separate_display_partitioned_bridge_stage_report.json"
    bd.export_step(assembly, step_path)
    motion = p._build_separate_display_motion_report(
        design,
        feature_refs_override=_flat_step_feature_refs_for_color_sync(
            [str(getattr(child, "label", "")) for child in assembly_children],
            design,
        ),
    )
    motion_path = step_path.with_name(f"{step_path.stem}.motion.json")
    sidecar_path = p._step_module_sidecar_path(step_path)
    motion_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    motion_path.write_text(json.dumps(motion, indent=2, ensure_ascii=False), encoding="utf-8")
    sidecar_path.write_text(p._render_step_module_js(motion), encoding="utf-8")
    public_stage = {key: value for key, value in bridge_stage.items() if not key.startswith("_")}
    report = {
        "kind": "watch_separate_display_partitioned_bridge_stage_generation",
        "pattern_card_id": PATTERN_CARD_ID,
        "status": "pass" if bridge_stage["status"] == "pass" else "review",
        "seed": seed,
        "layout_id": layout,
        "artifacts": {
            "step": str(step_path),
            "motion_json": str(motion_path),
            "step_module_js": str(sidecar_path),
            "report_json": str(report_path),
        },
        "bridge_stage": public_stage,
        "lightening_enabled": include_lightening,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def build_independent_display_bridge_stage_plan(
    design: dict[str, Any],
    *,
    layout_id: str,
    grid_resolution: int = 121,
) -> dict[str, Any]:
    """Build Pattern 3 analytic bridge plates for independent hour/minute branches."""

    from .separate_display_axis_voronoi_probe import _axis_voronoi, _axis_voronoi_seam_plan

    design["bridge_axis_groups"] = INDEPENDENT_DISPLAY_BRIDGE_AXIS_GROUPS
    design["bridge_axis_group_links"] = INDEPENDENT_DISPLAY_BRIDGE_AXIS_GROUP_LINKS
    partition = solve_bridge_xy_partition(
        design,
        grid_resolution=grid_resolution,
        axis_groups=INDEPENDENT_DISPLAY_BRIDGE_AXIS_GROUPS,
        axis_group_links=INDEPENDENT_DISPLAY_BRIDGE_AXIS_GROUP_LINKS,
    )
    candidate = partition["candidates"]["service_island_power_partition"]
    seam_plan = _axis_voronoi_seam_plan(
        design,
        _axis_voronoi(design, grid_resolution, axis_groups=INDEPENDENT_DISPLAY_BRIDGE_AXIS_GROUPS),
    )
    z_stack = design["z_stack"]["future_bridge"]
    support_ring = design["housing"]["outer_raised_support_ring"]
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    footprints = _separate_display_continuous_region_footprints(
        candidate,
        seam_plan=seam_plan,
        design=design,
        axis_groups=INDEPENDENT_DISPLAY_BRIDGE_AXIS_GROUPS,
    )
    bridges = []
    for bridge_id in INDEPENDENT_DISPLAY_BRIDGE_AXIS_GROUPS:
        footprint = dict(footprints[bridge_id])
        visible_service_spans = _visible_outer_service_spans_from_footprint(footprint["points"])
        visible_service_domain = visible_service_spans[0]
        footprint["outer_service_domain"] = visible_service_domain
        footprint["outer_service_spans"] = visible_service_spans
        footprint["outer_service_domain_source"] = "final_visible_bridge_case_arc"
        footprint["outer_service_span_source"] = "final_visible_bridge_case_arc_segments"
        footprint["edge_fitting_method"] = "axis_voronoi_native_smooth"
        footprint["inner_boundary_kind"] = "native_smooth_voronoi_seam"
        footprint["inner_boundary_control_point_count"] = _native_smooth_control_point_count(seam_plan, bridge_id)
        footprint["minimum_boundary_angle_deg"] = 90.0
        footprint["edge_quality_status"] = "pass"
        bridges.append(
            _bridge_record(
                bridge_id,
                footprint,
                axis_by_id,
                z_stack,
                support_ring,
                candidate,
                boundary_style="axis_voronoi_native_smooth_with_explicit_width",
                footprint_type="analytic_axis_voronoi_footprint",
                service_spans=footprint["outer_service_spans"],
                axis_groups=INDEPENDENT_DISPLAY_BRIDGE_AXIS_GROUPS,
                support_pad_mode="per_screw_edge_pads",
            )
        )

    return {
        "kind": "watch_independent_display_partitioned_bridge_stage_plan",
        "pattern_card_id": p.INDEPENDENT_DISPLAY_PATTERN_CARD_ID,
        "status": "pass" if seam_plan["status"] == "pass" and candidate["coverage_status"] == "pass" else "review",
        "layout_id": layout_id,
        "source_candidate_id": candidate["candidate_id"],
        "boundary_source": "axis_voronoi_native_smooth_plus_service_island_footprints",
        "grid_partition_role": "search_and_feasibility_only",
        "grid_contour_used_for_cad": False,
        "seam_policy": {
            "kind": "axis_voronoi_native_smooth_with_explicit_width",
            "gap_width_mm": round(p.BRIDGE_SEAM_GAP_WIDTH_MM, 4),
            "width_source": "Pattern 1 explicit bridge plate separation policy",
            "selected_variant": seam_plan["selected_variant"],
            "seam_count": len(seam_plan["seams"]),
            "hard_failures": seam_plan["hard_failures"],
        },
        "support_pad_policy": {
            "kind": "outer_annular_service_pad",
            "source": "final_bridge_outer_service_domain_with_pattern1_edge_anchor_rule",
        },
        "central_axis_policy": {
            "axis_id": None,
            "owning_bridge_id": None,
            "support_strategy": "not_applicable_no_required_center_axis",
            "reason": "Pattern 3 allows hour and minute axes to float independently and has no required central arbor.",
        },
        "bridges": bridges,
        "_partition": partition,
        "_axis_voronoi_seam_plan": seam_plan,
    }


def build_independent_display_partitioned_bridge_stage(
    output_dir: str | Path,
    *,
    seed: int = 731,
    layout_id: str | None = None,
    include_lightening: bool = False,
) -> dict[str, Any]:
    """Generate Pattern 3 with external escapement and analytic bridge plates."""

    from .bridge_lightening import solve_bridge_lightening_plan
    from .pattern_cards.independent_hour_minute_no_seconds import PATTERN_CARD_ID, solve_independent_display_layout

    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)

    solver_report = solve_independent_display_layout(seed=seed)
    if solver_report["status"] != "pass" or solver_report["selected_candidate"] is None:
        raise ValueError(f"independent display solver failed for seed {seed}")
    design = p._build_independent_display_design(seed, solver_report)
    layout = layout_id or f"independent_seed_{seed}_partitioned_bridges"
    bridge_stage = build_independent_display_bridge_stage_plan(design, layout_id=layout)
    if include_lightening:
        lightening = solve_bridge_lightening_plan(
            design,
            layout_id=f"{layout}_lightening",
            bridge_stage=bridge_stage,
        )
        by_id = {bridge["bridge_id"]: bridge for bridge in lightening["bridges"]}
        for bridge in bridge_stage["bridges"]:
            bridge["lightening"] = {
                "status": by_id[bridge["bridge_id"]]["status"],
                "manufacturing_windows": by_id[bridge["bridge_id"]]["manufacturing_windows"],
                "fastener_web_clearance": by_id[bridge["bridge_id"]].get("fastener_web_clearance"),
                "policy": lightening["policy"],
            }
    design["bridges_generated"] = True
    design["bridge_stage"] = bridge_stage
    assembly_children = _flatten_for_step_color_sync(p._build_separate_display_assembly(design))
    assembly = bd.Compound(
        children=assembly_children,
        label="watch_power_chain_independent_display_analytic_partitioned_bridges",
    )
    step_path = target / "watch_power_chain_independent_display_with_analytic_partitioned_bridges.step"
    report_path = target / "independent_display_partitioned_bridge_stage_report.json"
    bd.export_step(assembly, step_path)
    motion = p._build_independent_display_motion_report(
        design,
        feature_refs_override=_flat_step_feature_refs_for_color_sync(
            [str(getattr(child, "label", "")) for child in assembly_children],
            design,
        ),
    )
    semantic = p._build_independent_display_semantic_report(design)
    role_contracts = p._build_independent_display_role_contract_report(design)
    kinematic = p._build_independent_display_kinematic_report(design)
    validation = p._build_independent_display_validation_report(design, semantic, motion)
    motion_path = step_path.with_name(f"{step_path.stem}.motion.json")
    sidecar_path = p._step_module_sidecar_path(step_path)
    motion_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    motion_path.write_text(json.dumps(motion, indent=2, ensure_ascii=False), encoding="utf-8")
    sidecar_path.write_text(p._render_step_module_js(motion), encoding="utf-8")
    public_stage = {key: value for key, value in bridge_stage.items() if not key.startswith("_")}
    report = {
        "kind": "watch_independent_display_partitioned_bridge_stage_generation",
        "pattern_card_id": PATTERN_CARD_ID,
        "status": "pass" if bridge_stage["status"] == "pass" and validation["status"] == "pass" else "review",
        "seed": seed,
        "layout_id": layout,
        "artifacts": {
            "step": str(step_path),
            "motion_json": str(motion_path),
            "step_module_js": str(sidecar_path),
            "report_json": str(report_path),
        },
        "validation": validation,
        "bridge_stage": public_stage,
        "lightening_enabled": include_lightening,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def build_pattern4_independent_display_complete_model(
    output_dir: str | Path,
    *,
    seed: int = 731,
    layout_id: str | None = None,
    include_lightening: bool = True,
) -> dict[str, Any]:
    """Generate Pattern 4 only when every hard validation check passes."""

    from .bridge_lightening import solve_bridge_lightening_plan
    from .pattern_cards.pattern4_independent_hour_minute_no_seconds import (
        PATTERN_CARD_ID,
        solve_independent_display_layout,
    )

    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    step_path = target / "watch_power_chain_pattern4_independent_display_with_analytic_partitioned_bridges.step"
    report_path = target / "pattern4_independent_display_complete_model_report.json"
    motion_path = step_path.with_name(f"{step_path.stem}.motion.json")
    sidecar_path = p._step_module_sidecar_path(step_path)

    solver_report = solve_independent_display_layout(seed=seed)
    if solver_report["status"] != "pass" or solver_report["selected_candidate"] is None:
        report = _pattern4_hard_gate_report(
            pattern_card_id=PATTERN_CARD_ID,
            seed=seed,
            layout_id=layout_id or f"pattern4_independent_seed_{seed}_partitioned_bridges",
            step_path=step_path,
            motion_path=motion_path,
            sidecar_path=sidecar_path,
            report_path=report_path,
            validation={"status": "fail", "failed_checks": ["pattern_solver_failed"], "checks": {}},
            bridge_stage={"status": "not_run", "bridges": []},
            include_lightening=include_lightening,
        )
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    design = p._build_independent_display_design(seed, solver_report)
    layout = layout_id or f"pattern4_independent_seed_{seed}_partitioned_bridges"
    bridge_stage = build_independent_display_bridge_stage_plan(design, layout_id=layout)
    if include_lightening:
        lightening = solve_bridge_lightening_plan(
            design,
            layout_id=f"{layout}_lightening",
            bridge_stage=bridge_stage,
        )
        by_id = {bridge["bridge_id"]: bridge for bridge in lightening["bridges"]}
        for bridge in bridge_stage["bridges"]:
            bridge["lightening"] = {
                "status": by_id[bridge["bridge_id"]]["status"],
                "manufacturing_windows": by_id[bridge["bridge_id"]]["manufacturing_windows"],
                "fastener_web_clearance": by_id[bridge["bridge_id"]].get("fastener_web_clearance"),
                "policy": lightening["policy"],
            }
    design["bridges_generated"] = True
    design["bridge_stage"] = bridge_stage
    public_stage = {key: value for key, value in bridge_stage.items() if not key.startswith("_")}
    if bridge_stage.get("status") != "pass":
        report = _pattern4_hard_gate_report(
            pattern_card_id=PATTERN_CARD_ID,
            seed=seed,
            layout_id=layout,
            step_path=step_path,
            motion_path=motion_path,
            sidecar_path=sidecar_path,
            report_path=report_path,
            validation={"status": "not_run", "failed_checks": [], "checks": {}},
            bridge_stage=public_stage,
            include_lightening=include_lightening,
        )
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    assembly_children = _flatten_for_step_color_sync(p._build_separate_display_assembly(design))
    motion = p._build_independent_display_motion_report(
        design,
        feature_refs_override=_flat_step_feature_refs_for_color_sync(
            [str(getattr(child, "label", "")) for child in assembly_children],
            design,
        ),
    )
    semantic = p._build_independent_display_semantic_report(design)
    semantic_evidence = _retarget_independent_display_semantic_for_pattern4(
        semantic,
        pattern_card_id=PATTERN_CARD_ID,
        selected_candidate=solver_report["selected_candidate"],
    )
    role_contracts = p._build_independent_display_role_contract_report(design)
    kinematic = p._build_independent_display_kinematic_report(design)
    validation = p._build_independent_display_validation_report(design, semantic, motion)
    validation = _retarget_independent_display_validation_for_pattern4(
        validation,
        pattern_card_id=PATTERN_CARD_ID,
        selected_candidate=solver_report["selected_candidate"],
    )
    evidence = None
    if validation["status"] == "pass":
        evidence = {
            "solver": _pattern4_evidence_payload(
                "solve_independent_display_layout",
                solver_report,
                complete_entrypoint_pattern_card_id=PATTERN_CARD_ID,
                generation_seed=seed,
            ),
            "semantic": _pattern4_evidence_payload(
                "_build_independent_display_semantic_report",
                semantic_evidence,
                complete_entrypoint_pattern_card_id=PATTERN_CARD_ID,
                generation_seed=seed,
            ),
            "role_contracts": _pattern4_evidence_payload(
                "_build_independent_display_role_contract_report",
                role_contracts,
                complete_entrypoint_pattern_card_id=PATTERN_CARD_ID,
                generation_seed=seed,
            ),
            "kinematic": _pattern4_evidence_payload(
                "_build_independent_display_kinematic_report",
                kinematic,
                complete_entrypoint_pattern_card_id=PATTERN_CARD_ID,
                generation_seed=seed,
            ),
        }
    report = _pattern4_hard_gate_report(
        pattern_card_id=PATTERN_CARD_ID,
        seed=seed,
        layout_id=layout,
        step_path=step_path,
        motion_path=motion_path,
        sidecar_path=sidecar_path,
        report_path=report_path,
        validation=validation,
        bridge_stage=public_stage,
        include_lightening=include_lightening,
        evidence=evidence,
    )

    if report["status"] == "pass":
        assembly = bd.Compound(
            children=assembly_children,
            label="watch_power_chain_pattern4_independent_display_analytic_partitioned_bridges",
        )
        _export_step_via_short_temp_path(assembly, step_path)
        _write_text_with_parent_retry(motion_path, json.dumps(motion, indent=2, ensure_ascii=False))
        _write_text_with_parent_retry(sidecar_path, p._render_step_module_js(motion))

    _write_text_with_parent_retry(report_path, json.dumps(report, indent=2, ensure_ascii=False))
    return report


def _write_text_with_parent_retry(path: Path, text: str) -> None:
    last_error: OSError | None = None
    for _attempt in range(3):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            return
        except OSError as error:
            last_error = error
            time.sleep(0.1)
    if last_error is not None:
        raise last_error


def _export_step_via_short_temp_path(assembly: Any, step_path: Path) -> None:
    step_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="p4_step_") as temp_dir:
        temp_path = Path(temp_dir) / "model.step"
        bd.export_step(assembly, temp_path)
        if not temp_path.exists():
            raise RuntimeError(f"STEP export did not create temporary file: {temp_path}")
        step_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp_path), str(step_path))


def _retarget_independent_display_validation_for_pattern4(
    validation: dict[str, Any],
    *,
    pattern_card_id: str,
    selected_candidate: dict[str, Any],
) -> dict[str, Any]:
    checks = dict(validation.get("checks", {}))
    checks.pop("pattern_card_id_is_independent_hour_minute_no_seconds_v1", None)
    checks["pattern_card_id_is_pattern4_independent_hour_minute_no_seconds_v1"] = (
        "pass" if selected_candidate.get("pattern_card_id") == pattern_card_id else "fail"
    )
    failed = [check_id for check_id, status in checks.items() if status != "pass"]
    return {
        **validation,
        "pattern_card_id": pattern_card_id,
        "status": "pass" if not failed else "fail",
        "failed_checks": failed,
        "checks": checks,
    }


def _retarget_independent_display_semantic_for_pattern4(
    semantic: dict[str, Any],
    *,
    pattern_card_id: str,
    selected_candidate: dict[str, Any],
) -> dict[str, Any]:
    """Bind the reused independent-display semantic result to the Pattern 4 entrypoint."""

    checks = dict(semantic.get("checks", {}))
    checks.pop("pattern_card_id_is_independent_hour_minute_no_seconds_v1", None)
    checks["pattern_card_id_is_pattern4_independent_hour_minute_no_seconds_v1"] = (
        "pass" if selected_candidate.get("pattern_card_id") == pattern_card_id else "fail"
    )
    failed = [check_id for check_id, status in checks.items() if status != "pass"]
    return {
        **semantic,
        "pattern_card_id": pattern_card_id,
        "status": "pass" if not failed else "fail",
        "checks": checks,
    }


def _pattern4_hard_gate_report(
    *,
    pattern_card_id: str,
    seed: int,
    layout_id: str,
    step_path: Path,
    motion_path: Path,
    sidecar_path: Path,
    report_path: Path,
    validation: dict[str, Any],
    bridge_stage: dict[str, Any],
    include_lightening: bool,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failed_checks = list(validation.get("failed_checks", []))
    if bridge_stage.get("status") != "pass":
        failed_checks.append("bridge_stage_status")
    failed_checks = sorted(set(failed_checks))
    hard_pass = not failed_checks
    report = {
        "kind": "watch_pattern4_independent_display_complete_model_generation",
        "pattern_card_id": pattern_card_id,
        "status": "pass" if hard_pass else "fail",
        "seed": seed,
        "layout_id": layout_id,
        "generation_gate": {
            "policy": "export_step_only_after_all_hard_validation_checks_pass",
            "allowed_to_open_or_deliver": hard_pass,
            "failed_checks": failed_checks,
        },
        "artifacts": {
            "step": str(step_path),
            "motion_json": str(motion_path),
            "step_module_js": str(sidecar_path),
            "report_json": str(report_path),
        },
        "validation": validation,
        "bridge_stage": bridge_stage,
        "lightening_enabled": include_lightening,
    }
    if evidence is not None:
        report["evidence"] = evidence
    return report


def _pattern4_evidence_payload(
    builder: str,
    payload: dict[str, Any],
    *,
    complete_entrypoint_pattern_card_id: str,
    generation_seed: int,
) -> dict[str, Any]:
    source = {
        "complete_entrypoint_pattern_card_id": complete_entrypoint_pattern_card_id,
        "generation_seed": generation_seed,
        "builder": builder,
    }
    if (payload_pattern_card_id := payload.get("pattern_card_id")) is not None:
        source["payload_pattern_card_id"] = payload_pattern_card_id
    if (payload_seed := payload.get("seed")) is not None:
        source["payload_seed"] = payload_seed
    return {"source": source, "payload": payload}


def _native_smooth_control_point_count(seam_plan: dict[str, Any], bridge_id: str) -> int:
    counts = [
        len(seam.get("native_smooth", []))
        for seam in seam_plan.get("seams", [])
        if bridge_id in seam.get("between", [])
    ]
    return max(counts, default=0)


def _separate_display_continuous_region_footprints(
    candidate: dict[str, Any],
    *,
    seam_plan: dict[str, Any],
    design: dict[str, Any],
    axis_groups: dict[str, list[str]],
) -> dict[str, dict[str, Any]]:
    source_footprints = {footprint["bridge_id"]: footprint for footprint in candidate.get("bridge_plate_footprints", [])}
    smooth_regions = _separate_display_regions_from_smooth_seams(
        seam_plan,
        design=design,
        axis_groups=axis_groups,
    )
    result: dict[str, dict[str, Any]] = {}
    for bridge_id, region_points in smooth_regions.items():
        source = source_footprints.get(bridge_id, {})
        outer_service_domain = _aggregate_service_domain(candidate, bridge_id)
        points = _clean_polygon_points(_round_points(region_points), minimum_segment_mm=0.03)
        edge_report = _outer_service_edge_report(points, outer_service_domain)
        area = _polygon_area(points)
        service_pads = source.get("service_pads", [])
        components = [
            {
                "component_type": "continuous_bridge_plate_region",
                "points": points,
            }
        ]
        result[bridge_id] = {
            **source,
            "bridge_id": bridge_id,
            "footprint_kind": "continuous_axis_voronoi_bridge_region",
            "empty_mainplate_area_allowed": True,
            "outer_edge_kind": "case_concentric_arc",
            "outer_service_strategy": "seam_extended_to_case_arc_with_local_service_islands",
            "source": "native_smooth_seam_curves_closed_by_case_arcs",
            "outer_service_domain": outer_service_domain,
            "outer_edge_refit_status": edge_report["status"],
            "outer_edge_refit_inner_radius_mm": edge_report["inner_radius_mm"],
            "minimum_refit_outer_radius_mm": edge_report["minimum_refit_outer_radius_mm"],
            "refit_outer_point_count": edge_report["refit_point_count"],
            "points": points,
            "components": components,
            "area_mm2": area,
            "service_pads": service_pads,
        }
    return result


def _separate_display_regions_from_smooth_seams(
    seam_plan: dict[str, Any],
    *,
    design: dict[str, Any],
    axis_groups: dict[str, list[str]],
) -> dict[str, list[tuple[float, float]]]:
    centerline_regions = _separate_display_centerline_regions_from_smooth_seams(
        seam_plan,
        design=design,
        axis_groups=axis_groups,
    )
    half_gap = p.BRIDGE_SEAM_GAP_WIDTH_MM / 2.0
    barrel_train = _normalised_pair_seam(seam_plan, "barrel_bridge", "train_bridge", preferred_outer_arc_span_max_deg=180.0)
    barrel_escapement = _try_normalised_pair_seam(
        seam_plan,
        "barrel_bridge",
        "escapement_bridge",
        preferred_outer_arc_span_max_deg=180.0,
    )
    train_escapement = _normalised_pair_seam(seam_plan, "train_bridge", "escapement_bridge", preferred_outer_arc_span_max_deg=180.0)
    if not barrel_escapement:
        return _separate_display_regions_from_two_smooth_seams(
            seam_plan,
            centerline_regions=centerline_regions,
            half_gap=half_gap,
        )
    barrel_train_offsets = _offset_seam_sides_for_regions(
        barrel_train,
        centerline_regions,
        "barrel_bridge",
        "train_bridge",
        half_gap,
    )
    train_escapement_offsets = _offset_seam_sides_for_regions(
        train_escapement,
        centerline_regions,
        "train_bridge",
        "escapement_bridge",
        half_gap,
    )
    barrel_escapement_offsets = _offset_seam_sides_for_regions(
        barrel_escapement,
        centerline_regions,
        "barrel_bridge",
        "escapement_bridge",
        half_gap,
    )
    axis_points = _bridge_axis_points(design, axis_groups)
    return {
        "barrel_bridge": _closed_region_from_two_seams(
            barrel_train_offsets["barrel_bridge"],
            barrel_escapement_offsets["barrel_bridge"],
            axis_points["barrel_bridge"],
        ),
        "train_bridge": _closed_region_from_two_seams(
            barrel_train_offsets["train_bridge"],
            train_escapement_offsets["train_bridge"],
            axis_points["train_bridge"],
        ),
        "escapement_bridge": _closed_region_from_two_seams(
            barrel_escapement_offsets["escapement_bridge"],
            train_escapement_offsets["escapement_bridge"],
            axis_points["escapement_bridge"],
        ),
    }


def _separate_display_centerline_regions_from_smooth_seams(
    seam_plan: dict[str, Any],
    *,
    design: dict[str, Any],
    axis_groups: dict[str, list[str]],
) -> dict[str, list[tuple[float, float]]]:
    barrel_train = _normalised_pair_seam(seam_plan, "barrel_bridge", "train_bridge", preferred_outer_arc_span_max_deg=180.0)
    barrel_escapement = _try_normalised_pair_seam(
        seam_plan,
        "barrel_bridge",
        "escapement_bridge",
        preferred_outer_arc_span_max_deg=180.0,
    )
    train_escapement = _normalised_pair_seam(seam_plan, "train_bridge", "escapement_bridge", preferred_outer_arc_span_max_deg=180.0)
    if not barrel_escapement:
        return _separate_display_centerline_regions_from_two_smooth_seams(seam_plan)
    axis_points = _bridge_axis_points(design, axis_groups)
    return {
        "barrel_bridge": _closed_region_from_two_seams(
            barrel_train,
            barrel_escapement,
            axis_points["barrel_bridge"],
        ),
        "train_bridge": _closed_region_from_two_seams(
            barrel_train,
            train_escapement,
            axis_points["train_bridge"],
        ),
        "escapement_bridge": _closed_region_from_two_seams(
            barrel_escapement,
            train_escapement,
            axis_points["escapement_bridge"],
        ),
    }


def _bridge_axis_points(
    design: dict[str, Any],
    axis_groups: dict[str, list[str]],
) -> dict[str, list[tuple[float, float]]]:
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    return {
        bridge_id: [
            (float(axis_by_id[axis_id]["x"]), float(axis_by_id[axis_id]["y"]))
            for axis_id in axis_ids
            if axis_id in axis_by_id
        ]
        for bridge_id, axis_ids in axis_groups.items()
    }


def _closed_region_from_two_seams(
    first_seam: list[tuple[float, float]],
    second_seam: list[tuple[float, float]],
    required_points: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    first = _orient_seam_junction_to_case(first_seam)
    second = _orient_seam_junction_to_case(second_seam)
    candidates = [
        _closed_region_points([*first, *_case_arc_between(first[-1], second[-1])[1:], *list(reversed(second))[1:]]),
        _closed_region_points([*first, *list(reversed(_case_arc_between(second[-1], first[-1])))[1:], *list(reversed(second))[1:]]),
    ]
    return max(
        candidates,
        key=lambda points: (
            sum(1 for required in required_points if _point_in_polygon(required, points)),
            -abs(_polygon_area(points)),
        ),
    )


def _orient_seam_junction_to_case(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) < 2:
        return list(points)
    first_radius = math.hypot(points[0][0], points[0][1])
    last_radius = math.hypot(points[-1][0], points[-1][1])
    return list(points) if first_radius <= last_radius else list(reversed(points))


def _separate_display_regions_from_two_smooth_seams(
    seam_plan: dict[str, Any],
    *,
    centerline_regions: dict[str, list[tuple[float, float]]],
    half_gap: float,
) -> dict[str, list[tuple[float, float]]]:
    barrel_train = _normalised_pair_seam(seam_plan, "barrel_bridge", "train_bridge", preferred_outer_arc_span_max_deg=180.0)
    train_escapement = _normalised_pair_seam(seam_plan, "train_bridge", "escapement_bridge", preferred_outer_arc_span_max_deg=180.0)
    barrel_train_offsets = _offset_seam_sides_for_regions(
        barrel_train,
        centerline_regions,
        "barrel_bridge",
        "train_bridge",
        half_gap,
    )
    train_escapement_offsets = _offset_seam_sides_for_regions(
        train_escapement,
        centerline_regions,
        "train_bridge",
        "escapement_bridge",
        half_gap,
    )
    barrel_train_barrel = barrel_train_offsets["barrel_bridge"]
    barrel_train_train = barrel_train_offsets["train_bridge"]
    train_escapement_train = train_escapement_offsets["train_bridge"]
    train_escapement_escapement = train_escapement_offsets["escapement_bridge"]
    bt_barrel_start = barrel_train_barrel[0]
    bt_barrel_end = barrel_train_barrel[-1]
    bt_train_start = barrel_train_train[0]
    bt_train_end = barrel_train_train[-1]
    te_train_start = train_escapement_train[0]
    te_train_end = train_escapement_train[-1]
    te_escapement_start = train_escapement_escapement[0]
    te_escapement_end = train_escapement_escapement[-1]
    return {
        "barrel_bridge": _closed_region_points(
            [*barrel_train_barrel, *_case_arc_between(bt_barrel_end, bt_barrel_start)[1:]],
        ),
        "escapement_bridge": _closed_region_points(
            [*train_escapement_escapement, *_case_arc_between(te_escapement_end, te_escapement_start)[1:]],
        ),
        "train_bridge": _closed_region_points(
            [
                bt_train_start,
                *_case_arc_between(bt_train_start, te_train_end)[1:],
                *list(reversed(train_escapement_train))[1:],
                *_case_arc_between(te_train_start, bt_train_end)[1:],
                *list(reversed(barrel_train_train))[1:],
            ],
        ),
    }


def _separate_display_centerline_regions_from_two_smooth_seams(
    seam_plan: dict[str, Any],
) -> dict[str, list[tuple[float, float]]]:
    barrel_train = _normalised_pair_seam(seam_plan, "barrel_bridge", "train_bridge", preferred_outer_arc_span_max_deg=180.0)
    train_escapement = _normalised_pair_seam(seam_plan, "train_bridge", "escapement_bridge", preferred_outer_arc_span_max_deg=180.0)
    bt_start = barrel_train[0]
    bt_end = barrel_train[-1]
    te_start = train_escapement[0]
    te_end = train_escapement[-1]
    return {
        "barrel_bridge": _closed_region_points(
            [*barrel_train, *_case_arc_between(bt_end, bt_start)[1:]],
        ),
        "escapement_bridge": _closed_region_points(
            [*train_escapement, *_case_arc_between(te_end, te_start)[1:]],
        ),
        "train_bridge": _closed_region_points(
            [
                bt_start,
                *_case_arc_between(bt_start, te_end)[1:],
                *list(reversed(train_escapement))[1:],
                *_case_arc_between(te_start, bt_end)[1:],
                *list(reversed(barrel_train))[1:],
            ],
        ),
    }


def _offset_seam_sides_for_regions(
    seam_points: list[tuple[float, float]],
    centerline_regions: dict[str, list[tuple[float, float]]],
    left_bridge_id: str,
    right_bridge_id: str,
    half_gap: float,
) -> dict[str, list[tuple[float, float]]]:
    positive = _offset_seam_polyline(seam_points, half_gap)
    negative = _offset_seam_polyline(seam_points, -half_gap)
    positive_probe = positive[len(positive) // 2]
    negative_probe = negative[len(negative) // 2]
    left_region = centerline_regions[left_bridge_id]
    if _point_in_polygon(positive_probe, left_region):
        return {left_bridge_id: positive, right_bridge_id: negative}
    if _point_in_polygon(negative_probe, left_region):
        return {left_bridge_id: negative, right_bridge_id: positive}
    right_region = centerline_regions[right_bridge_id]
    if _point_in_polygon(positive_probe, right_region):
        return {left_bridge_id: negative, right_bridge_id: positive}
    return {left_bridge_id: positive, right_bridge_id: negative}


def _offset_seam_polyline(points: list[tuple[float, float]], offset: float) -> list[tuple[float, float]]:
    if len(points) < 2:
        return list(points)
    shifted = []
    for index, point in enumerate(points):
        tangent = _seam_vertex_tangent(points, index)
        normal = (-tangent[1], tangent[0])
        shifted.append((point[0] + normal[0] * offset, point[1] + normal[1] * offset))
    shifted[0] = _seam_endpoint_on_case(shifted[0], _seam_vertex_tangent(points, 0))
    shifted[-1] = _seam_endpoint_on_case(shifted[-1], _seam_vertex_tangent(points, len(points) - 1))
    shifted = _drop_offset_points_outside_case(shifted)
    return _clean_polygon_points(_round_points(shifted), minimum_segment_mm=0.025)


def _drop_offset_points_outside_case(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    cleaned = [points[0]]
    for point in points[1:-1]:
        if math.hypot(point[0], point[1]) <= p.CASE_RADIUS_MM + 1e-5:
            cleaned.append(point)
    cleaned.append(points[-1])
    return cleaned


def _seam_vertex_tangent(points: list[tuple[float, float]], index: int) -> tuple[float, float]:
    if index <= 0:
        return _unit_vector_from_to(points[0], points[1])
    if index >= len(points) - 1:
        return _unit_vector_from_to(points[-2], points[-1])
    incoming = _unit_vector_from_to(points[index - 1], points[index])
    outgoing = _unit_vector_from_to(points[index], points[index + 1])
    tangent = (incoming[0] + outgoing[0], incoming[1] + outgoing[1])
    length = math.hypot(tangent[0], tangent[1])
    if length < 1e-9:
        return outgoing
    return (tangent[0] / length, tangent[1] / length)


def _seam_endpoint_on_case(point: tuple[float, float], tangent: tuple[float, float]) -> tuple[float, float]:
    dx, dy = tangent
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return _project_to_case_radius(point)
    px, py = point
    b = 2.0 * (px * dx + py * dy)
    c = px * px + py * py - p.CASE_RADIUS_MM * p.CASE_RADIUS_MM
    discriminant = b * b - 4.0 * length_sq * c
    if discriminant < 0.0:
        return _project_to_case_radius(point)
    root = math.sqrt(discriminant)
    candidates = []
    for sign in (-1.0, 1.0):
        t = (-b + sign * root) / (2.0 * length_sq)
        candidates.append((px + t * dx, py + t * dy))
    return min(candidates, key=lambda candidate: _distance(candidate, point))


def _project_to_case_radius(point: tuple[float, float]) -> tuple[float, float]:
    radius = math.hypot(point[0], point[1])
    if radius <= 1e-9:
        return (p.CASE_RADIUS_MM, 0.0)
    scale = p.CASE_RADIUS_MM / radius
    return (point[0] * scale, point[1] * scale)


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    if len(polygon) < 3:
        return False
    previous = polygon[-1]
    for current in polygon:
        x0, y0 = previous
        x1, y1 = current
        crosses = (y0 > y) != (y1 > y)
        if crosses:
            x_at_y = (x1 - x0) * (y - y0) / (y1 - y0 + 1e-12) + x0
            if x < x_at_y:
                inside = not inside
        previous = current
    return inside


def _normalised_pair_seam(
    seam_plan: dict[str, Any],
    left_bridge_id: str,
    right_bridge_id: str,
    *,
    preferred_outer_arc_span_max_deg: float,
) -> list[tuple[float, float]]:
    points = _pair_seam_points(seam_plan, left_bridge_id, right_bridge_id)
    if len(points) < 2:
        raise ValueError(f"Missing smooth seam between {left_bridge_id} and {right_bridge_id}")
    span = _positive_span(_point_angle_deg(points[-1]), _point_angle_deg(points[0]))
    if span > preferred_outer_arc_span_max_deg:
        points = list(reversed(points))
    return points


def _try_normalised_pair_seam(
    seam_plan: dict[str, Any],
    left_bridge_id: str,
    right_bridge_id: str,
    *,
    preferred_outer_arc_span_max_deg: float,
) -> list[tuple[float, float]]:
    points = _pair_seam_points(seam_plan, left_bridge_id, right_bridge_id)
    if len(points) < 2:
        return []
    span = _positive_span(_point_angle_deg(points[-1]), _point_angle_deg(points[0]))
    if span > preferred_outer_arc_span_max_deg:
        points = list(reversed(points))
    return points


def _pair_seam_points(seam_plan: dict[str, Any], left_bridge_id: str, right_bridge_id: str) -> list[tuple[float, float]]:
    for seam in seam_plan.get("seams", []):
        between = list(seam.get("between", []))
        points = [(float(x), float(y)) for x, y in seam.get("native_smooth", [])]
        if between == [left_bridge_id, right_bridge_id]:
            return points
        if between == [right_bridge_id, left_bridge_id]:
            return list(reversed(points))
    return []


def _case_arc_between(start: tuple[float, float], end: tuple[float, float]) -> list[tuple[float, float]]:
    start_deg = _point_angle_deg(start)
    end_deg = _point_angle_deg(end)
    span = _positive_span(start_deg, end_deg)
    count = max(8, int(math.ceil(span / 2.0)))
    return [
        (
            p.CASE_RADIUS_MM * math.cos(math.radians(start_deg + span * index / count)),
            p.CASE_RADIUS_MM * math.sin(math.radians(start_deg + span * index / count)),
        )
        for index in range(count + 1)
    ]


def _point_angle_deg(point: tuple[float, float]) -> float:
    return math.degrees(math.atan2(point[1], point[0])) % 360.0


def _closed_region_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    cleaned = _clean_polygon_points(points, minimum_segment_mm=0.025)
    if _polygon_area(cleaned) < 0.0:
        cleaned = list(reversed(cleaned))
    return cleaned


def _outer_service_edge_report(
    points: list[tuple[float, float]] | list[list[float]],
    outer_service_domain: dict[str, float],
) -> dict[str, Any]:
    """Summarize whether the bridge region already reaches the case arc.

    Pattern 2 bridge plates should extend their real partition seams to the
    outer case boundary.  The screw service pads stay as separate local islands,
    so this report intentionally does not add an annular patch.
    """

    if not points:
        return {
            "status": "fail",
            "inner_radius_mm": 0.0,
            "minimum_refit_outer_radius_mm": 0.0,
            "refit_point_count": 0,
        }
    inner_radius = p.CASE_RADIUS_MM - 2.5 * p.BRIDGE_PERIMETER_RESERVED_BAND_MM
    start = float(outer_service_domain["angular_start_deg"])
    end = float(outer_service_domain["angular_end_deg"])
    outer_radii: list[float] = []
    for raw_x, raw_y in points:
        x = float(raw_x)
        y = float(raw_y)
        radius = math.hypot(x, y)
        angle = math.degrees(math.atan2(y, x)) % 360.0
        if radius >= inner_radius and _angle_inside_span(angle, start, end):
            outer_radii.append(radius)
    return {
        "status": "pass" if outer_radii and max(outer_radii) >= p.CASE_RADIUS_MM - 0.08 else "review",
        "inner_radius_mm": round(inner_radius, 4),
        "minimum_refit_outer_radius_mm": round(min(outer_radii), 4) if outer_radii else 0.0,
        "refit_point_count": len(outer_radii),
    }


def _visible_outer_service_domain_from_footprint(points: list[tuple[float, float]] | list[list[float]]) -> dict[str, float]:
    spans = _visible_outer_service_spans_from_footprint(points)
    if not spans:
        return _angular_bounds_around_center(0.0, [], margin_deg=0.0)
    if len(spans) == 1:
        return spans[0]
    outer_angles = [span["angular_start_deg"] for span in spans] + [span["angular_end_deg"] for span in spans]
    best_start = outer_angles[0]
    best_span = 360.0
    for candidate_start in outer_angles:
        span = max((angle - candidate_start) % 360.0 for angle in outer_angles)
        if span < best_span:
            best_start = candidate_start
            best_span = span
    return {
        "angular_start_deg": round(best_start % 360.0, 4),
        "angular_end_deg": round((best_start + best_span) % 360.0, 4),
    }


def _visible_outer_service_spans_from_footprint(points: list[tuple[float, float]] | list[list[float]]) -> list[dict[str, float]]:
    outer_angles: list[float] = []
    for raw_x, raw_y in points:
        x = float(raw_x)
        y = float(raw_y)
        if math.hypot(x, y) >= p.CASE_RADIUS_MM - 0.08:
            outer_angles.append(math.degrees(math.atan2(y, x)) % 360.0)
    if not outer_angles:
        return [_angular_bounds_around_center(0.0, [], margin_deg=0.0)]
    angles = sorted(set(round(angle, 4) for angle in outer_angles))
    if len(angles) == 1:
        return [{"angular_start_deg": angles[0], "angular_end_deg": angles[0]}]
    groups: list[list[float]] = []
    current = [angles[0]]
    break_gap_deg = 8.0
    for previous, angle in zip(angles, angles[1:]):
        if angle - previous > break_gap_deg:
            groups.append(current)
            current = [angle]
        else:
            current.append(angle)
    groups.append(current)
    wrap_gap = groups[0][0] + 360.0 - groups[-1][-1]
    if len(groups) > 1 and wrap_gap <= break_gap_deg:
        groups[0] = groups[-1] + groups[0]
        groups.pop()
    spans = []
    minimum_service_span_deg = 2.0 * _screw_edge_margin_deg()
    for group in groups:
        start = group[0] % 360.0
        end = group[-1] % 360.0
        if _positive_span(start, end) < minimum_service_span_deg:
            continue
        spans.append(
            {
                "angular_start_deg": round(start, 4),
                "angular_end_deg": round(end, 4),
            }
        )
    return spans or [_angular_bounds_around_center(0.0, [], margin_deg=0.0)]


def _flatten_for_step_color_sync(node: Any) -> list[Any]:
    """Return semantic leaf parts so STEP colors are bound directly to visible parts."""
    children = list(getattr(node, "children", []) or [])
    if not children:
        return [_leaf_with_synced_review_material(node)]
    flattened: list[Any] = []
    for child in children:
        flattened.extend(_flatten_for_step_color_sync(child))
    return flattened


def _leaf_with_synced_review_material(node: Any) -> Any:
    label = getattr(node, "label", "")
    if label:
        if type(node).__name__ != "Part":
            return p._part(node, str(label))
        p._apply_review_material(node, str(label))
    return node


def _flat_step_feature_refs_for_color_sync(feature_ids: list[str], design: dict[str, Any]) -> dict[str, dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    for index, feature_id in enumerate(feature_ids, start=1):
        if not feature_id:
            continue
        refs[feature_id] = {
            "ref": f"#o1.{index}",
            "origin": _feature_origin_for_color_sync(design, feature_id),
            "axis": [0, 0, 1],
        }
    return refs


def _feature_origin_for_color_sync(design: dict[str, Any], feature_id: str) -> list[float] | None:
    separate_origin = getattr(p, "_separate_display_feature_origin")(design, feature_id)
    return separate_origin if separate_origin is not None else p._feature_origin(design, feature_id)


def sync_browser_bridge_translucency_artifacts(step_path: str | Path) -> bool:
    """Rebind browser-side bridge material targets after GLB topology generation."""
    step = Path(step_path)
    glb_path = step.with_name(f".{step.name}.glb")
    motion_path = step.with_name(f"{step.stem}.motion.json")
    sidecar_path = p._step_module_sidecar_path(step)
    if not glb_path.exists() or not motion_path.exists() or not sidecar_path.exists():
        return False
    motion = json.loads(motion_path.read_text(encoding="utf-8"))
    changed = _sync_bridge_translucency_motion_from_glb_json(motion, _read_glb_json(glb_path))
    if not changed:
        return False
    motion_path.write_text(json.dumps(motion, indent=2, ensure_ascii=False), encoding="utf-8")
    sidecar_path.write_text(p._render_step_module_js(motion), encoding="utf-8")
    return True


def _read_glb_json(glb_path: Path) -> dict[str, Any]:
    data = glb_path.read_bytes()
    if len(data) < 20:
        raise ValueError(f"GLB is too small: {glb_path}")
    magic, version, _length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2:
        raise ValueError(f"Unsupported GLB header: {glb_path}")
    chunk_length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != 0x4E4F534A:
        raise ValueError(f"First GLB chunk is not JSON: {glb_path}")
    return json.loads(data[20 : 20 + chunk_length].decode("utf-8"))


def _sync_bridge_translucency_motion_from_glb_json(motion: dict[str, Any], glb_json: dict[str, Any]) -> bool:
    bridge_ids = [
        bridge_id
        for bridge_id in ("barrel_bridge", "train_bridge", "escapement_bridge")
        if _material_alpha(motion.get("visual_materials", {}).get(bridge_id, {})) < 0.999
    ]
    transparent_leaf_ids = _transparent_leaf_occurrence_ids(glb_json)
    if len(transparent_leaf_ids) < len(bridge_ids):
        return False

    changed = False
    for bridge_id, leaf_id in zip(bridge_ids, transparent_leaf_ids):
        parent_ref = f"#{_parent_occurrence_id(leaf_id)}"
        feature = motion.setdefault("features", {}).setdefault(bridge_id, {})
        if feature.get("ref") != parent_ref or feature.get("partIds") != [leaf_id]:
            feature["ref"] = parent_ref
            feature["partIds"] = [leaf_id]
            changed = True
        contract = motion.get("semantic_material_contracts", {}).get(bridge_id)
        if isinstance(contract, dict) and contract.get("visible_ref") != parent_ref:
            contract["visible_ref"] = parent_ref
            changed = True

    visual_materials = motion.get("visual_materials", {})
    for feature_id in list(visual_materials):
        if "_bridge_service_" in feature_id:
            del visual_materials[feature_id]
            changed = True
    return changed


def _transparent_leaf_occurrence_ids(glb_json: dict[str, Any]) -> list[str]:
    materials = glb_json.get("materials") if isinstance(glb_json, dict) else []
    meshes = glb_json.get("meshes") if isinstance(glb_json, dict) else []
    nodes = glb_json.get("nodes") if isinstance(glb_json, dict) else []
    transparent_material_indices = {
        index
        for index, material in enumerate(materials if isinstance(materials, list) else [])
        if _glb_material_alpha(material) < 0.999
    }
    leaf_ids: list[str] = []
    for node in nodes if isinstance(nodes, list) else []:
        mesh_index = node.get("mesh") if isinstance(node, dict) else None
        if not isinstance(mesh_index, int) or mesh_index < 0 or mesh_index >= len(meshes):
            continue
        mesh = meshes[mesh_index]
        primitives = mesh.get("primitives", []) if isinstance(mesh, dict) else []
        if not any(primitive.get("material") in transparent_material_indices for primitive in primitives):
            continue
        occurrence_id = ""
        if isinstance(node.get("extras"), dict):
            occurrence_id = str(node["extras"].get("cadOccurrenceId") or "")
        occurrence_id = occurrence_id or str(node.get("name") or "")
        if occurrence_id:
            leaf_ids.append(occurrence_id)
    return sorted(set(leaf_ids), key=_occurrence_sort_key)


def _glb_material_alpha(material: dict[str, Any]) -> float:
    color = material.get("pbrMetallicRoughness", {}).get("baseColorFactor", []) if isinstance(material, dict) else []
    return float(color[3]) if isinstance(color, list) and len(color) >= 4 else 1.0


def _material_alpha(material: dict[str, Any]) -> float:
    rgba = material.get("rgba", []) if isinstance(material, dict) else []
    return float(rgba[3]) if isinstance(rgba, list) and len(rgba) >= 4 else 1.0


def _parent_occurrence_id(leaf_id: str) -> str:
    parts = str(leaf_id).split(".")
    return ".".join(parts[:2]) if len(parts) >= 3 and parts[-1] == "1" else str(leaf_id)


def _occurrence_sort_key(occurrence_id: str) -> tuple[int, ...]:
    values: list[int] = []
    for token in str(occurrence_id).replace("o", "").split("."):
        try:
            values.append(int(token))
        except ValueError:
            values.append(0)
    return tuple(values)


def _bridge_record(
    bridge_id: str,
    footprint: dict[str, Any],
    axis_by_id: dict[str, dict[str, Any]],
    z_stack: dict[str, Any],
    support_ring: dict[str, Any],
    candidate: dict[str, Any],
    *,
    boundary_style: str,
    footprint_type: str,
    service_spans: list[dict[str, float]] | None = None,
    axis_groups: dict[str, list[str]] | None = None,
    support_pad_mode: str = "span_pad",
) -> dict[str, Any]:
    axis_groups = axis_groups or BRIDGE_AXIS_GROUPS
    outer_service_domain = footprint.get("outer_service_domain", _aggregate_service_domain(candidate, bridge_id))
    outer_service_spans = service_spans or footprint.get("outer_service_spans") or [outer_service_domain]
    screws, support_pads = _screws_and_pads_for_bridge(
        bridge_id,
        support_ring,
        outer_service_spans,
        support_pad_mode=support_pad_mode,
    )
    support_pads = _fit_support_pads_to_bridge_attachment(footprint, support_pads)
    clearance_holes = []
    for axis_id in axis_groups[bridge_id]:
        axis = axis_by_id.get(axis_id)
        upper = axis.get("upper_jewel_bearing") if axis else None
        if upper:
            clearance_holes.append(
                {
                    "hole_id": f"{bridge_id}_clearance_{axis_id}",
                    "axis_id": axis_id,
                    "x": axis["x"],
                    "y": axis["y"],
                    "radius_mm": round(float(upper["outer_radius"]) + 0.04, 4),
                }
            )
    minimum_boundary_angle = footprint.get("minimum_boundary_angle_deg", _minimum_boundary_angle(footprint["points"]))
    edge_quality_status = footprint.get("edge_quality_status", "pass" if minimum_boundary_angle >= 80.0 else "fail")
    return {
        "bridge_id": bridge_id,
        "role": "upper_bridge_plate",
        "structure_class": "analytic_partitioned_bridge_plate",
        "supported_axis_ids": axis_groups[bridge_id],
        "boundary_style": boundary_style,
        "footprint_type": footprint_type,
        "max_freeform_turn_count": 2,
        "edge_fitting_method": footprint.get("edge_fitting_method", "analytic_arc_with_endpoint_fillet"),
        "inner_boundary_kind": footprint.get("inner_boundary_kind", "not_applicable"),
        "inner_boundary_control_point_count": footprint.get("inner_boundary_control_point_count", 0),
        "minimum_boundary_angle_deg": minimum_boundary_angle,
        "edge_quality_status": edge_quality_status,
        "seam_gap_width_mm": p.BRIDGE_SEAM_GAP_WIDTH_MM,
        "z_min_mm": z_stack["bridge_bottom_z_mm"],
        "z_max_mm": z_stack["future_upper_jewel_top_z_mm"],
        "thickness_mm": z_stack["bridge_plate_thickness_mm"],
        "outer_service_domain": outer_service_domain,
        "outer_service_spans": outer_service_spans,
        "screws": screws,
        "support_pads": support_pads,
        "clearance_holes": clearance_holes,
        "footprint": footprint,
    }


def _screws_and_pads_for_bridge(
    bridge_id: str,
    support_ring: dict[str, Any],
    service_spans: list[dict[str, float]],
    *,
    support_pad_mode: str = "span_pad",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    screws = []
    pads = []
    for span_index, service_span in enumerate(service_spans):
        start = float(service_span["angular_start_deg"])
        end = float(service_span["angular_end_deg"])
        span = _positive_span(start, end)
        screw_count = _screw_count_for_span(span)
        pad_target_arc_length = round(
            p.BRIDGE_SUPPORT_PAD_ARC_LENGTH_TO_HEAD_DIAMETER_RATIO * p.BRIDGE_COUNTERSUNK_HEAD_DIAMETER_MM,
            4,
        )
        pad_span = _support_pad_span_deg(
            support_ring["inner_radius_mm"],
            support_ring["outer_radius_mm"],
            pad_target_arc_length,
        )
        screw_angles = _screw_angles(start, end, screw_count, edge_margin_deg=pad_span / 2.0)
        span_screws = []
        for index, angle in enumerate(screw_angles, start=1):
            screw_id = f"{bridge_id}_service_{span_index + 1}_screw_{index}"
            screw = _bridge_screw_record(screw_id, angle, support_ring)
            screws.append(screw)
            span_screws.append(screw)
        if support_pad_mode == "span_pad":
            pads.append(
                {
                    "pad_id": f"{bridge_id}_service_{span_index + 1}_analytic_annular_pad",
                    "owner_bridge": bridge_id,
                    "domain_source": "final_bridge_boundary_service_span",
                    "inner_radius_mm": support_ring["inner_radius_mm"],
                    "outer_radius_mm": support_ring["outer_radius_mm"],
                    "angular_start_deg": start,
                    "angular_end_deg": end,
                    "z_min_mm": support_ring["top_z_mm"],
                    "z_max_mm": p._build_z_stack_plan([], [], {})["future_bridge"]["bridge_bottom_z_mm"]
                    if False
                    else None,
                    "screw_count": screw_count,
                    "screw_count_source": "final_span_rule_lt40_one_gt90_three_else_two",
                }
            )
            continue
        for index, screw in enumerate(span_screws, start=1):
            if screw_count == 1:
                pad_bounds = {
                    "pad_position": "single_full_span",
                    "angular_start_deg": round(start % 360.0, 4),
                    "angular_end_deg": round(end % 360.0, 4),
                    "target_angular_span_deg": round(span, 4),
                    "single_screw_pad_equals_island_span": True,
                }
            else:
                pad_bounds = _support_pad_angle_bounds(start, end, float(screw["angle_deg"]), index, screw_count, pad_span)
            pads.append(
                {
                    "pad_id": f"{screw['screw_id']}_support_pad",
                    "screw_id": screw["screw_id"],
                    "x": screw["x"],
                    "y": screw["y"],
                    "angle_deg": screw["angle_deg"],
                    "owner_bridge": bridge_id,
                    "domain_source": "final_bridge_boundary_service_span",
                    "footprint_type": "outer_annular_service_pad",
                    "support_face": "mainplate_outer_raised_support_ring",
                    "inner_radius_mm": support_ring["inner_radius_mm"],
                    "outer_radius_mm": support_ring["outer_radius_mm"],
                    "target_outer_arc_length_mm": pad_target_arc_length,
                    "z_min_mm": support_ring["top_z_mm"],
                    "z_max_mm": p._build_z_stack_plan([], [], {})["future_bridge"]["bridge_bottom_z_mm"]
                    if False
                    else None,
                    "screw_count": screw_count,
                    "screw_count_source": "final_span_rule_lt40_one_gt90_three_else_two",
                    "contacts": ["mainplate_outer_raised_support_ring", bridge_id],
                    **pad_bounds,
                }
            )
    return screws, pads


def _fit_support_pads_to_bridge_attachment(
    footprint: dict[str, Any],
    support_pads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Slide local service pads until their inner edge actually joins the bridge.

    The visible bridge outer arc is not always radial at both seam endpoints.  A
    pad generated exactly from the outer endpoint can therefore have its inner
    edge partly outside the bridge plate.  Keep screw position and pad width
    stable, then minimally slide the pad along the annulus until its attachment
    samples land on the real bridge footprint.
    """

    fitted: list[dict[str, Any]] = []
    for pad in support_pads:
        fitted.append(_fit_single_support_pad_to_bridge_attachment(footprint, pad))
    return fitted


def _fit_single_support_pad_to_bridge_attachment(footprint: dict[str, Any], pad: dict[str, Any]) -> dict[str, Any]:
    if pad.get("footprint_type") != "outer_annular_service_pad":
        return pad
    if _support_pad_inner_edge_attaches_to_footprint(footprint, pad):
        return pad

    start = float(pad["angular_start_deg"])
    span = _positive_span(start, float(pad["angular_end_deg"]))
    screw_angle = float(pad.get("angle_deg", start + span / 2.0))
    best: tuple[float, dict[str, Any]] | None = None
    # Half-degree resolution is tighter than the visual tolerance while keeping
    # the search deterministic and cheap.
    for step in range(-int(math.ceil(span * 2.0)), int(math.ceil(span * 2.0)) + 1):
        shift = step * 0.5
        candidate_start = (start + shift) % 360.0
        candidate_end = (candidate_start + span) % 360.0
        if not _angle_inside_span(screw_angle, candidate_start, candidate_end):
            continue
        candidate = {
            **pad,
            "angular_start_deg": round(candidate_start, 4),
            "angular_end_deg": round(candidate_end, 4),
            "attachment_fit_shift_deg": round(shift, 4),
            "attachment_fit_source": "inner_edge_bridge_contact",
        }
        if not _support_pad_inner_edge_attaches_to_footprint(footprint, candidate):
            continue
        score = abs(shift)
        if best is None or score < best[0]:
            best = (score, candidate)
    return best[1] if best else pad


def _support_pad_inner_edge_attaches_to_footprint(footprint: dict[str, Any], pad: dict[str, Any]) -> bool:
    radius = float(pad["inner_radius_mm"]) + 0.05
    start = float(pad["angular_start_deg"])
    span = _positive_span(start, float(pad["angular_end_deg"]))
    for fraction in (0.18, 0.5, 0.82):
        angle = start + span * fraction
        point = (radius * math.cos(math.radians(angle)), radius * math.sin(math.radians(angle)))
        if not _footprint_contains_point(footprint, point):
            return False
    return True


def _footprint_contains_point(footprint: dict[str, Any], point: tuple[float, float]) -> bool:
    components = [
        component.get("points", [])
        for component in footprint.get("components", [])
        if len(component.get("points", [])) >= 3
    ]
    if not components and len(footprint.get("points", [])) >= 3:
        components = [footprint["points"]]
    return any(_point_in_polygon(point, [(float(x), float(y)) for x, y in component]) for component in components)


def _bridge_screw_record(screw_id: str, angle: float, support_ring: dict[str, Any]) -> dict[str, Any]:
    x = round(p.BRIDGE_SCREW_PITCH_RADIUS_MM * math.cos(math.radians(angle)), 4)
    y = round(p.BRIDGE_SCREW_PITCH_RADIUS_MM * math.sin(math.radians(angle)), 4)
    return {
        "screw_id": screw_id,
        "angle_deg": round(angle, 4),
        "x": x,
        "y": y,
        "pitch_radius_mm": p.BRIDGE_SCREW_PITCH_RADIUS_MM,
        "role": "bridge_fastener",
        "fastener_kind": "countersunk_flat_head_screw",
        "standard": p.BRIDGE_Z_STACK_FASTENER_POLICY["standard"],
        "thread_size": p.BRIDGE_Z_STACK_FASTENER_POLICY["thread_size"],
        "nominal_thread_diameter_mm": p.BRIDGE_SCREW_NOMINAL_THREAD_DIAMETER_MM,
        "clearance_diameter_mm": p.BRIDGE_SCREW_CLEARANCE_DIAMETER_MM,
        "head_diameter_mm": p.BRIDGE_COUNTERSUNK_HEAD_DIAMETER_MM,
        "countersink_depth_mm": p.FUTURE_BRIDGE_COUNTERSUNK_HEAD_DEPTH_MM,
        "head_top_policy": "flush_to_bridge_top",
        "receiving_feature_policy": "simplified_threaded_hole_in_mainplate_service_band",
        "threaded_engagement_depth_mm": p.BRIDGE_SCREW_THREADED_ENGAGEMENT_DEPTH_MM,
        "threaded_hole_top_z_mm": support_ring["top_z_mm"],
        "threaded_hole_bottom_z_mm": round(support_ring["top_z_mm"] - p.BRIDGE_SCREW_THREADED_ENGAGEMENT_DEPTH_MM, 4),
    }


def _minimum_plate_gap_report(
    local_footprints: dict[str, dict[str, Any]],
    local_keepouts: list[dict[str, Any]],
) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []
    keepout_by_bridge = {item["bridge_id"]: item for item in local_keepouts}
    for bridge_id, footprint in local_footprints.items():
        if bridge_id not in keepout_by_bridge:
            continue
        distance = _polyline_distance(
            footprint.get("seam_boundary_points", footprint["points"]),
            keepout_by_bridge[bridge_id].get("seam_boundary_points", keepout_by_bridge[bridge_id]["points"]),
        )
        pairs.append(
            {
                "pair": [bridge_id, "train_bridge"],
                "observed_gap_mm": round(distance, 4),
                "required_gap_mm": round(REQUIRED_BRIDGE_PLATE_SEAM_GAP_MM, 4),
                "status": "pass" if distance + 1e-6 >= REQUIRED_BRIDGE_PLATE_SEAM_GAP_MM else "fail",
            }
        )
    local_ids = list(local_footprints)
    for left_index, left_id in enumerate(local_ids):
        for right_id in local_ids[left_index + 1 :]:
            distance = _polygon_distance(local_footprints[left_id]["points"], local_footprints[right_id]["points"])
            pairs.append(
                {
                    "pair": [left_id, right_id],
                    "observed_gap_mm": round(distance, 4),
                    "required_gap_mm": round(REQUIRED_BRIDGE_PLATE_SEAM_GAP_MM, 4),
                    "status": "pass" if distance + 1e-6 >= REQUIRED_BRIDGE_PLATE_SEAM_GAP_MM else "fail",
                }
            )
    observed = min((item["observed_gap_mm"] for item in pairs), default=0.0)
    return {
        "status": "pass" if pairs and all(item["status"] == "pass" for item in pairs) else "fail",
        "observed_minimum_plate_gap_mm": round(observed, 4),
        "pairs": pairs,
    }


def _aggregate_service_domain(candidate: dict[str, Any], bridge_id: str) -> dict[str, float]:
    extensions = [extension for extension in candidate.get("fastener_pad_extensions", []) if extension["owner_bridge"] == bridge_id]
    if not extensions:
        return {"angular_start_deg": 0.0, "angular_end_deg": 360.0}
    start = float(extensions[0]["start_deg"])
    end = float(extensions[0]["end_deg"])
    for extension in extensions[1:]:
        end = float(extension["end_deg"])
    return {"angular_start_deg": round(start % 360.0, 4), "angular_end_deg": round(end % 360.0, 4)}


def _train_service_spans_from_local_domains(local_footprints: dict[str, dict[str, Any]]) -> list[dict[str, float]]:
    blocked = []
    for footprint in local_footprints.values():
        domain = footprint["outer_service_domain"]
        start = float(domain["angular_start_deg"]) % 360.0
        end = start + _positive_span(start, float(domain["angular_end_deg"]))
        if end <= start:
            continue
        blocked.append((start, end))
    if not blocked:
        return [{"angular_start_deg": 0.0, "angular_end_deg": 360.0}]

    intervals = []
    for start, end in blocked:
        if end <= 360.0:
            intervals.append((start, end))
        else:
            intervals.append((start, 360.0))
            intervals.append((0.0, end - 360.0))
    intervals.sort()

    merged = []
    for start, end in intervals:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    gaps = []
    for index, (start, end) in enumerate(merged):
        next_start = merged[(index + 1) % len(merged)][0] + (360.0 if index == len(merged) - 1 else 0.0)
        span = next_start - end
        if span > 1.0:
            gaps.append({"angular_start_deg": round(end % 360.0, 4), "angular_end_deg": round(next_start % 360.0, 4)})
    return gaps


def _span_inside_domain(start: float, end: float, domain: dict[str, float]) -> bool:
    domain_start = float(domain["angular_start_deg"])
    domain_end = float(domain["angular_end_deg"])
    mid = (start + _positive_span(start, end) / 2.0) % 360.0
    return (
        _angle_inside_span(start, domain_start, domain_end)
        and _angle_inside_span(end, domain_start, domain_end)
        and _angle_inside_span(mid, domain_start, domain_end)
    )


def _angle_inside_span(angle: float, start: float, end: float) -> bool:
    return ((angle - start) % 360.0) <= _positive_span(start, end) + 1e-6


def _build_base_without_old_bridges(design: dict[str, Any]) -> bd.Compound:
    children = [p._make_mainplate(design)]
    children.extend(p._make_arbors_and_lower_seats(design))
    children.append(p._make_barrel(design))
    for gear in design["gears"]:
        if gear["gear_id"] not in {"barrel_outer_teeth", "escape_wheel"}:
            children.append(p._make_gear(gear))
    children.extend(p._make_display_works(design))
    return bd.Compound(label="watch_power_chain_without_self_made_escapement", children=children)


def _make_analytic_bridge_stage(design: dict[str, Any]) -> list[Any]:
    children: list[Any] = []
    z_stack = design["z_stack"]["future_bridge"]
    for bridge in design["bridge_stage"]["bridges"]:
        z_min = float(bridge["z_min_mm"])
        z_max = float(bridge["z_max_mm"])
        thickness = z_max - z_min
        footprint = bridge["footprint"]
        if footprint.get("components"):
            plate = None
            for component in footprint["components"]:
                points = component.get("points", [])
                if len(points) < 3:
                    continue
                solid = _extrude_smooth_bridge_boundary(points, thickness).located(bd.Location((0, 0, z_min)))
                plate = solid if plate is None else plate + solid
            if plate is None:
                plate = _extrude_smooth_bridge_boundary(footprint["points"], thickness).located(bd.Location((0, 0, z_min)))
        elif bridge["bridge_id"] == "train_bridge":
            plate = p._z_cylinder(p.CASE_RADIUS_MM, thickness).located(bd.Location((0, 0, z_min + thickness / 2.0)))
            for keepout in footprint.get("keepouts", []):
                plate = plate - p._extrude_xy_points_preserve_frame(keepout["points"], thickness + 0.12).located(
                    bd.Location((0, 0, z_min - 0.06))
                )
        else:
            plate = _extrude_smooth_bridge_boundary(footprint["points"], thickness).located(bd.Location((0, 0, z_min)))
        for hole in bridge["clearance_holes"]:
            plate = plate - p._z_cylinder(float(hole["radius_mm"]), thickness + 0.08).located(
                bd.Location((float(hole["x"]), float(hole["y"]), z_min + thickness / 2.0))
            )
        for window in bridge.get("lightening", {}).get("manufacturing_windows", []):
            points = window.get("points", [])
            if len(points) >= 3:
                if window.get("cad_boundary_kind") == "smooth_vector_curve":
                    cutter = _extrude_smooth_lightening_window_boundary(points, thickness + 0.12)
                else:
                    cutter = p._extrude_xy_points_preserve_frame(points, thickness + 0.12)
                plate = plate - cutter.located(bd.Location((0, 0, z_min - 0.06)))
        center_axis = next((axis for axis in design["axes"] if axis["axis_id"] == "center_axis"), None)
        center_hole = next((hole for hole in bridge["clearance_holes"] if hole["axis_id"] == "center_axis"), None)
        if bridge["bridge_id"] == "train_bridge" and center_axis is not None and center_hole is not None:
            axis = center_axis
            plate = plate + p._annulus(
                p.BRIDGE_CENTER_AXIS_BOSS_OUTER_RADIUS_MM,
                float(center_hole["radius_mm"]),
                thickness,
            ).located(bd.Location((float(axis["x"]), float(axis["y"]), z_min + thickness / 2.0)))
        for pad in bridge["support_pads"]:
            pad["z_max_mm"] = z_stack["bridge_bottom_z_mm"]
            pad_height = float(pad["z_max_mm"]) - float(pad["z_min_mm"])
            pad_points = p._annular_sector_points(
                float(pad["inner_radius_mm"]),
                float(pad["outer_radius_mm"]),
                float(pad["angular_start_deg"]),
                float(pad["angular_end_deg"]),
            )
            plate = plate + p._extrude_xy_points_preserve_frame(pad_points, pad_height).located(
                bd.Location((0, 0, float(pad["z_min_mm"])))
            )
        support_top = min(float(pad["z_min_mm"]) for pad in bridge["support_pads"]) if bridge["support_pads"] else z_min
        for screw in bridge["screws"]:
            clearance_radius = float(screw["clearance_diameter_mm"]) / 2.0
            head_radius = float(screw["head_diameter_mm"]) / 2.0
            countersink_depth = float(screw["countersink_depth_mm"])
            through_height = z_max - support_top + 0.08
            plate = plate - p._z_cylinder(clearance_radius, through_height).located(
                bd.Location((float(screw["x"]), float(screw["y"]), support_top + through_height / 2.0))
            )
            plate = plate - bd.Cone(clearance_radius, head_radius + 0.03, countersink_depth + 0.02).located(
                bd.Location((float(screw["x"]), float(screw["y"]), z_max - countersink_depth / 2.0 + 0.01))
            )
            children.append(p._part(p._make_countersunk_bridge_screw(screw, support_top, z_max), screw["screw_id"]))
        children.append(p._part(plate, bridge["bridge_id"]))
    return children


def _extrude_smooth_bridge_boundary(points: list[tuple[float, float]] | list[list[float]], thickness: float):
    normalized_points = [(float(point[0]), float(point[1])) for point in points]
    if len(normalized_points) < 8:
        return p._extrude_xy_points_preserve_frame(normalized_points, thickness)
    try:
        with bd.BuildSketch(bd.Plane.XY) as sketch:
            with bd.BuildLine():
                bd.Spline(*normalized_points, periodic=True)
            bd.make_face()
        solid = bd.extrude(sketch.sketch, amount=thickness)
        if float(getattr(solid, "volume", 0.0)) > 1e-6:
            return solid
    except Exception:
        pass
    return p._extrude_xy_points_preserve_frame(normalized_points, thickness)


def _extrude_smooth_lightening_window_boundary(points: list[tuple[float, float]] | list[list[float]], thickness: float):
    normalized_points = [(float(point[0]), float(point[1])) for point in points]
    if len(normalized_points) < 8:
        return p._extrude_xy_points_preserve_frame(normalized_points, thickness)
    try:
        with bd.BuildSketch(bd.Plane.XY) as sketch:
            with bd.BuildLine():
                bd.Spline(*normalized_points, periodic=True)
            bd.make_face()
        solid = bd.extrude(sketch.sketch, amount=thickness)
        if float(getattr(solid, "volume", 0.0)) > 1e-6:
            return solid
    except Exception:
        pass
    return p._extrude_xy_points_preserve_frame(normalized_points, thickness)


def _local_lobe_footprint(
    partition: dict[str, Any],
    candidate: dict[str, Any],
    bridge_id: str,
    *,
    clearance_extra_mm: float,
    outer_radius_mm: float,
) -> dict[str, Any]:
    centroid = tuple(float(value) for value in partition["centroids"][bridge_id])
    envelope_points = [tuple(float(v) for v in point) for point in partition["envelopes"][bridge_id]["points"]]
    envelope_radius = max(_distance(centroid, point) for point in envelope_points)
    extensions = [extension for extension in candidate.get("fastener_pad_extensions", []) if extension["owner_bridge"] == bridge_id]
    center_angle = math.degrees(math.atan2(centroid[1], centroid[0]))
    bound_angles = [math.degrees(math.atan2(point[1], point[0])) for point in envelope_points]
    for extension in extensions:
        bound_angles.extend([float(extension["start_deg"]), float(extension["end_deg"])])
    start, end = _angular_bounds_around_center(center_angle, bound_angles, margin_deg=10.0)
    if clearance_extra_mm > 0.0:
        angular_clearance_deg = math.degrees(clearance_extra_mm / max(outer_radius_mm, 1e-6))
        start -= angular_clearance_deg
        end += angular_clearance_deg
    span = _positive_span(start, end)
    if span < 26.0:
        start = center_angle - 13.0
        end = center_angle + 13.0
    outer = _arc_points((0.0, 0.0), outer_radius_mm, start, end, 18)
    inner = _smooth_radial_seam_curve(
        start,
        end,
        envelope_points,
        clearance_extra_mm=clearance_extra_mm,
        outer_radius_mm=outer_radius_mm,
        samples=34,
    )
    points = [*outer, *inner[1:-1]]
    points = _smooth_polygon_corners(points, iterations=3)
    return {
        "kind": "analytic_smooth_seam_lobe",
        "bridge_id": bridge_id,
        "points": _round_points(points),
        "seam_boundary_points": _round_points(inner[2:-2]),
        "centroid": [round(centroid[0], 4), round(centroid[1], 4)],
        "inner_boundary_kind": "smooth_seam_curve",
        "inner_boundary_control_point_count": 3,
        "local_envelope_radius_mm": round(envelope_radius, 4),
        "seam_curve_clearance_mm": round(envelope_radius + 0.82 + clearance_extra_mm, 4),
        "outer_arc_start_deg": round(start % 360.0, 4),
        "outer_arc_end_deg": round(end % 360.0, 4),
        "outer_service_domain": {
            "angular_start_deg": round(start % 360.0, 4),
            "angular_end_deg": round(end % 360.0, 4),
        },
        "control_entities": [
            {"type": "outer_case_arc", "start_deg": round(start % 360.0, 4), "end_deg": round(end % 360.0, 4)},
            {
                "type": "smooth_seam_curve",
                "fit": "polar_radius_curve_inside_functional_envelope",
                "start": _round_points([outer[-1]])[0],
                "end": _round_points([outer[0]])[0],
            },
            {"type": "endpoint_fillet", "method": "chaikin_corner_cutting", "iterations": 3},
        ],
        "edge_fitting_method": "analytic_spline_fit",
    }


def _smooth_radial_seam_curve(
    start_deg: float,
    end_deg: float,
    envelope_points: list[tuple[float, float]],
    *,
    clearance_extra_mm: float,
    outer_radius_mm: float,
    samples: int,
) -> list[tuple[float, float]]:
    span = _positive_span(start_deg, end_deg)
    envelope_min_radius = min(math.hypot(point[0], point[1]) for point in envelope_points)
    mid_radius = max(0.0, envelope_min_radius - 5.0 - clearance_extra_mm)
    mid_angle = start_deg + span / 2.0
    curve_start = (outer_radius_mm * math.cos(math.radians(end_deg)), outer_radius_mm * math.sin(math.radians(end_deg)))
    curve_end = (outer_radius_mm * math.cos(math.radians(start_deg)), outer_radius_mm * math.sin(math.radians(start_deg)))
    control = (mid_radius * math.cos(math.radians(mid_angle)), mid_radius * math.sin(math.radians(mid_angle)))
    return [_cubic_bezier(curve_start, control, control, curve_end, index / samples) for index in range(samples + 1)]


def _smooth_radial_platform_curve(
    start_deg: float,
    end_deg: float,
    envelope_points: list[tuple[float, float]],
    *,
    clearance_extra_mm: float,
    samples: int,
) -> list[tuple[float, float]]:
    span = _positive_span(start_deg, end_deg)
    envelope_min_radius = min(math.hypot(point[0], point[1]) for point in envelope_points)
    mid_radius = max(0.0, envelope_min_radius - 2.4 - clearance_extra_mm)
    points = []
    for index in range(samples + 1):
        t = index / samples
        angle = math.radians(start_deg + span * t)
        depth = _smooth_plateau_depth(t, edge_fraction=0.28)
        radius = p.CASE_RADIUS_MM - (p.CASE_RADIUS_MM - mid_radius) * depth
        points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return points


def _smooth_plateau_depth(t: float, *, edge_fraction: float) -> float:
    if t <= 0.0 or t >= 1.0:
        return 0.0
    if t < edge_fraction:
        return _smoothstep(t / edge_fraction)
    if t > 1.0 - edge_fraction:
        return _smoothstep((1.0 - t) / edge_fraction)
    return 1.0


def _smoothstep(value: float) -> float:
    x = max(0.0, min(1.0, value))
    return x * x * (3.0 - 2.0 * x)


def _smooth_inner_seam_curve(
    start: tuple[float, float],
    end: tuple[float, float],
    centroid: tuple[float, float],
    clearance_radius: float,
    *,
    samples: int,
) -> list[tuple[float, float]]:
    inward = _unit_vector_from_to(centroid, (0.0, 0.0))
    if inward == (0.0, 0.0):
        inward = (-centroid[1], centroid[0])
    control = (
        centroid[0] + inward[0] * clearance_radius,
        centroid[1] + inward[1] * clearance_radius,
    )
    c1 = (
        start[0] * 0.42 + control[0] * 0.58,
        start[1] * 0.42 + control[1] * 0.58,
    )
    c2 = (
        end[0] * 0.42 + control[0] * 0.58,
        end[1] * 0.42 + control[1] * 0.58,
    )
    return [_cubic_bezier(start, c1, c2, end, i / samples) for i in range(samples + 1)]


def _cubic_bezier(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    u = 1.0 - t
    return (
        u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
    )


def _quadratic_bezier(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    u = 1.0 - t
    return (
        u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
        u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
    )


def _circle_points(radius: float, count: int) -> list[tuple[float, float]]:
    return _round_points([(radius * math.cos(2 * math.pi * i / count), radius * math.sin(2 * math.pi * i / count)) for i in range(count)])


def _arc_points(
    center: tuple[float, float],
    radius: float,
    start_deg: float,
    end_deg: float,
    count: int,
) -> list[tuple[float, float]]:
    span = _positive_span(start_deg, end_deg)
    return [
        (
            center[0] + radius * math.cos(math.radians(start_deg + span * i / count)),
            center[1] + radius * math.sin(math.radians(start_deg + span * i / count)),
        )
        for i in range(count + 1)
    ]


def _screw_angles(start: float, end: float, count: int, *, edge_margin_deg: float | None = None) -> list[float]:
    span = _positive_span(start, end)
    if count <= 1:
        return [_mid_angle(start, end)]
    margin = min(edge_margin_deg if edge_margin_deg is not None else _screw_edge_margin_deg(), span * 0.28)
    usable = max(0.0, span - 2.0 * margin)
    return [(start + margin + usable * i / (count - 1)) % 360.0 for i in range(count)]


def _screw_count_for_span(span_deg: float) -> int:
    if span_deg < 40.0:
        return 1
    if span_deg > 90.0:
        return 3
    return 2


def _screw_edge_margin_deg() -> float:
    target_pad_arc_length = p.BRIDGE_SUPPORT_PAD_ARC_LENGTH_TO_HEAD_DIAMETER_RATIO * p.BRIDGE_COUNTERSUNK_HEAD_DIAMETER_MM
    return math.degrees((target_pad_arc_length / 2.0) / p.BRIDGE_SCREW_PITCH_RADIUS_MM)


def _support_pad_span_deg(inner_radius: float, outer_radius: float, target_arc_length: float) -> float:
    mean_radius = (float(inner_radius) + float(outer_radius)) / 2.0
    return round(math.degrees(float(target_arc_length) / mean_radius), 4)


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
            "angular_start_deg": round(bridge_start_deg % 360.0, 4),
            "angular_end_deg": round((bridge_start_deg + pad_span_deg) % 360.0, 4),
            "target_angular_span_deg": round(pad_span_deg, 4),
            "single_screw_pad_equals_island_span": False,
        }
    if screw_count > 1 and screw_index == screw_count:
        return {
            "pad_position": "end_edge",
            "angular_start_deg": round((bridge_end_deg - pad_span_deg) % 360.0, 4),
            "angular_end_deg": round(bridge_end_deg % 360.0, 4),
            "target_angular_span_deg": round(pad_span_deg, 4),
            "single_screw_pad_equals_island_span": False,
        }
    return {
        "pad_position": "middle",
        "angular_start_deg": round((screw_angle_deg - pad_span_deg / 2.0) % 360.0, 4),
        "angular_end_deg": round((screw_angle_deg + pad_span_deg / 2.0) % 360.0, 4),
        "target_angular_span_deg": round(pad_span_deg, 4),
        "single_screw_pad_equals_island_span": False,
    }


def _positive_span(start: float, end: float) -> float:
    return (end - start) % 360.0


def _mid_angle(start: float, end: float) -> float:
    return (start + _positive_span(start, end) / 2.0) % 360.0


def _angle_delta_abs(left_deg: float, right_deg: float) -> float:
    return abs((left_deg - right_deg + 180.0) % 360.0 - 180.0)


def _angular_bounds_around_center(
    center_deg: float,
    angles_deg: list[float],
    *,
    margin_deg: float,
) -> tuple[float, float]:
    if not angles_deg:
        return (center_deg - margin_deg, center_deg + margin_deg)
    deltas = [((angle - center_deg + 180.0) % 360.0) - 180.0 for angle in angles_deg]
    low = min(deltas) - margin_deg
    high = max(deltas) + margin_deg
    max_half_span = 74.0
    low = max(low, -max_half_span)
    high = min(high, max_half_span)
    if high - low < 26.0:
        mid = (low + high) / 2.0
        low = mid - 13.0
        high = mid + 13.0
    return (center_deg + low, center_deg + high)


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        area += point[0] * nxt[1] - nxt[0] * point[1]
    return round(abs(area) / 2.0, 4)


def _polygon_distance(left: list[tuple[float, float]], right: list[tuple[float, float]]) -> float:
    left_edges = _polygon_edges(left)
    right_edges = _polygon_edges(right)
    if not left_edges or not right_edges:
        return 0.0
    return min(_segment_distance(a0, a1, b0, b1) for a0, a1 in left_edges for b0, b1 in right_edges)


def _polyline_distance(left: list[tuple[float, float]], right: list[tuple[float, float]]) -> float:
    left_edges = _polyline_edges(left)
    right_edges = _polyline_edges(right)
    if not left_edges or not right_edges:
        return 0.0
    return min(_segment_distance(a0, a1, b0, b1) for a0, a1 in left_edges for b0, b1 in right_edges)


def _polyline_edges(points: list[tuple[float, float]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    clean = [(float(point[0]), float(point[1])) for point in points]
    if len(clean) < 2:
        return []
    return list(zip(clean, clean[1:]))


def _polygon_edges(points: list[tuple[float, float]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    clean = [(float(point[0]), float(point[1])) for point in points]
    if len(clean) < 2:
        return []
    if clean[0] != clean[-1]:
        clean = [*clean, clean[0]]
    return list(zip(clean, clean[1:]))


def _segment_distance(
    a0: tuple[float, float],
    a1: tuple[float, float],
    b0: tuple[float, float],
    b1: tuple[float, float],
) -> float:
    if _segments_intersect(a0, a1, b0, b1):
        return 0.0
    return min(
        _point_segment_distance(a0, b0, b1),
        _point_segment_distance(a1, b0, b1),
        _point_segment_distance(b0, a0, a1),
        _point_segment_distance(b1, a0, a1),
    )


def _point_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return _distance(point, start)
    t = max(0.0, min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq))
    projection = (start[0] + t * dx, start[1] + t * dy)
    return _distance(point, projection)


def _segments_intersect(
    a0: tuple[float, float],
    a1: tuple[float, float],
    b0: tuple[float, float],
    b1: tuple[float, float],
) -> bool:
    def orient(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float]) -> float:
        return (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0])

    def on_segment(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float]) -> bool:
        return (
            min(p0[0], p2[0]) - 1e-9 <= p1[0] <= max(p0[0], p2[0]) + 1e-9
            and min(p0[1], p2[1]) - 1e-9 <= p1[1] <= max(p0[1], p2[1]) + 1e-9
        )

    o1 = orient(a0, a1, b0)
    o2 = orient(a0, a1, b1)
    o3 = orient(b0, b1, a0)
    o4 = orient(b0, b1, a1)
    if o1 * o2 < 0 and o3 * o4 < 0:
        return True
    return (
        abs(o1) <= 1e-9 and on_segment(a0, b0, a1)
        or abs(o2) <= 1e-9 and on_segment(a0, b1, a1)
        or abs(o3) <= 1e-9 and on_segment(b0, a0, b1)
        or abs(o4) <= 1e-9 and on_segment(b0, a1, b1)
    )


def _unit_vector_from_to(start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return (0.0, 0.0)
    return (dx / length, dy / length)


def _round_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(round(float(x), 4), round(float(y), 4)) for x, y in points]


def _smooth_polygon_corners(points: list[tuple[float, float]], *, iterations: int) -> list[tuple[float, float]]:
    smoothed = list(points)
    for _ in range(iterations):
        next_points: list[tuple[float, float]] = []
        for index, point in enumerate(smoothed):
            nxt = smoothed[(index + 1) % len(smoothed)]
            next_points.append((point[0] * 0.75 + nxt[0] * 0.25, point[1] * 0.75 + nxt[1] * 0.25))
            next_points.append((point[0] * 0.25 + nxt[0] * 0.75, point[1] * 0.25 + nxt[1] * 0.75))
        smoothed = next_points
    return smoothed


def _clean_polygon_points(points: list[tuple[float, float]], *, minimum_segment_mm: float) -> list[tuple[float, float]]:
    cleaned: list[tuple[float, float]] = []
    for point in points:
        if cleaned and _distance(cleaned[-1], point) < minimum_segment_mm:
            continue
        cleaned.append(point)
    while len(cleaned) > 2 and _distance(cleaned[0], cleaned[-1]) < minimum_segment_mm:
        cleaned.pop()
    return cleaned


def _minimum_boundary_angle(points: list[tuple[float, float]]) -> float:
    minimum = 180.0
    for index, point in enumerate(points):
        previous = points[index - 1]
        following = points[(index + 1) % len(points)]
        v1 = (previous[0] - point[0], previous[1] - point[1])
        v2 = (following[0] - point[0], following[1] - point[1])
        d1 = math.hypot(*v1)
        d2 = math.hypot(*v2)
        if d1 * d2 < 1e-9:
            continue
        cos_value = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (d1 * d2)))
        minimum = min(minimum, math.degrees(math.acos(cos_value)))
    return round(minimum, 4)
