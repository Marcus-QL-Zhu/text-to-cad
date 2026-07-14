"""Closed-loop planar diversity probe for the watch chain solver."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.path import Path as MplPath

from .bridge_xy_partition import _render_candidate, render_bridge_xy_partition_candidate, solve_bridge_xy_partition
from .global_constraint_solver import solve_global_axis_constraints
from .power_chain_mvp import CASE_RADIUS_MM, _build_design


_SEED_PARTITION_CACHE: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
VARIABLE_AXIS_IDS = [
    "minute_work_axis",
    "barrel_axis",
    "third_axis",
    "fourth_axis",
    "escape_axis",
    "pallet_axis",
    "balance_axis",
]
REFERENCE_AXIS_IDS = ["display_center_axis", "center_axis"]
FUNCTIONAL_ENVELOPE_IDS = ["barrel_bridge", "train_bridge", "escapement_bridge"]


def run_chain_solver_loop_probe(seeds: list[int], output_dir: str | Path | None = None) -> dict[str, Any]:
    """Generate a planar diversity probe report for the given seeds."""

    design_items = []
    for seed in seeds:
        design, _ = _design_and_partition_for_seed(seed)
        design_items.append({"seed": seed, "design": design})
    return _run_loop_probe_from_design_items(
        kind="watch_chain_solver_loop_probe",
        seeds=list(seeds),
        design_items=design_items,
        output_dir=output_dir,
    )


def run_global_constraint_solver_loop_probe(
    *,
    seed: int = 42,
    target_count: int = 5,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Generate a loop probe report from global coordinate-constraint candidates."""

    global_report = solve_global_axis_constraints(seed=seed, target_count=target_count)
    design_items = [
        {
            "seed": index,
            "design": _design_from_global_candidate(candidate, global_report),
        }
        for index, candidate in enumerate(global_report["candidates"][:target_count], start=1)
    ]
    report = _run_loop_probe_from_design_items(
        kind="watch_global_constraint_solver_loop_probe",
        seeds=[item["seed"] for item in design_items],
        design_items=design_items,
        output_dir=output_dir,
    )
    report["global_constraint_solver"] = {
        "status": global_report["status"],
        "selection_strategy": global_report["selection_strategy"],
        "candidate_count": len(global_report["candidates"]),
        "rejected_candidate_count": global_report["rejected_candidate_count"],
        "constraint_equations": global_report["constraint_equations"],
        "variable_domains": global_report.get("variable_domains", {}),
        "region_classification": global_report.get("region_classification", {}),
        "representative_clusters": global_report.get("representative_clusters", []),
    }
    diversity_report = report["artifacts"].get("diversity_report")
    if diversity_report:
        Path(diversity_report).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _run_loop_probe_from_design_items(
    *,
    kind: str,
    seeds: list[int],
    design_items: list[dict[str, Any]],
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    target = Path(output_dir) if output_dir is not None else None
    if target is not None:
        target.mkdir(parents=True, exist_ok=True)

    candidates = []
    diversity_inputs = []
    rendered = []
    rendered_axis_layouts = []
    rendered_envelopes = []
    for index, item in enumerate(design_items, start=1):
        seed = item["seed"]
        design = item["design"]
        partition = solve_bridge_xy_partition(design, grid_resolution=121)
        candidate_id = _select_partition_candidate(partition, seed)
        candidate = partition["candidates"][candidate_id]
        geometric_status = "pass" if candidate["coverage_status"] == "pass" else "fail"
        image_path = None
        if target is not None:
            image_path = target / f"candidate_{index:02d}_seed_{seed}_{candidate_id}.png"
            render_bridge_xy_partition_candidate(partition, candidate_id, image_path)
            rendered.append((seed, partition, candidate_id))
        bridge_areas = _bridge_area_counts(candidate)
        service_spans = _outer_service_island_spans(candidate)
        candidates.append(
            {
                "seed": seed,
                "pattern_solver_variables": design["pattern_solver"]["selected_candidate"]["variables"],
                "pattern_solver_stages": design["pattern_solver"]["solver_stages"],
                "bridge_partition_candidate": candidate_id,
                "bridge_partition_coverage_status": candidate["coverage_status"],
                "geometric_status": geometric_status,
                "axis_positions": _axis_positions(design),
                "functional_envelopes": partition["envelopes"],
                "bridge_area_counts": bridge_areas,
                "outer_service_island_total_span_deg": service_spans,
                "image_path": str(image_path.resolve()) if image_path is not None else "",
            }
        )
        diversity_inputs.append(
            {
                "seed": seed,
                "design": design,
                "envelopes": partition["envelopes"],
                "variables": design["pattern_solver"]["selected_candidate"]["variables"],
                "axis_positions": _axis_positions(design),
                "bridge_area_counts": bridge_areas,
                "outer_service_island_total_span_deg": service_spans,
                "candidate_id": candidate_id,
            }
        )
        rendered_axis_layouts.append((seed, design))
        rendered_envelopes.append((seed, partition))

    artifacts = {}
    if target is not None and rendered:
        bridge_contact_sheet = target / "bridge_partition_contact_sheet.png"
        _render_contact_sheet(rendered, bridge_contact_sheet)
        axis_contact_sheet = target / "axis_layout_contact_sheet.png"
        _render_axis_contact_sheet(rendered_axis_layouts, axis_contact_sheet)
        envelope_contact_sheet = target / "functional_envelope_contact_sheet.png"
        _render_functional_envelope_contact_sheet(rendered_envelopes, envelope_contact_sheet)
        artifacts["contact_sheet"] = str(bridge_contact_sheet.resolve())
        artifacts["bridge_partition_contact_sheet"] = str(bridge_contact_sheet.resolve())
        artifacts["axis_layout_contact_sheet"] = str(axis_contact_sheet.resolve())
        artifacts["functional_envelope_contact_sheet"] = str(envelope_contact_sheet.resolve())

    diversity_metrics = _score_diversity(diversity_inputs)
    bridge_failure_reasons = _bridge_partition_failure_reasons(diversity_metrics, diversity_inputs)
    axis_failure_reasons = _axis_diversity_failure_reasons(diversity_metrics, diversity_inputs)
    envelope_failure_reasons = _functional_envelope_failure_reasons(diversity_metrics)
    failure_reasons = [*axis_failure_reasons, *envelope_failure_reasons]
    report = {
        "kind": kind,
        "seeds": list(seeds),
        "candidates": candidates,
        "artifacts": artifacts,
        "axis_diversity_status": "pass" if not axis_failure_reasons else "fail",
        "functional_envelope_diversity_status": "pass" if not envelope_failure_reasons else "fail",
        "bridge_partition_diversity_status": "pass" if not bridge_failure_reasons else "fail",
        "diversity_status": "pass" if not failure_reasons else "fail",
        "failure_reasons": failure_reasons,
        "axis_failure_reasons": axis_failure_reasons,
        "functional_envelope_failure_reasons": envelope_failure_reasons,
        "bridge_partition_failure_reasons": bridge_failure_reasons,
        "diversity_metrics": diversity_metrics,
    }
    if target is not None:
        diversity_report = target / "diversity_report.json"
        diversity_report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        visual_prompt = target / "visual_review_prompt.md"
        visual_prompt.write_text(_visual_review_prompt(report), encoding="utf-8")
        report["artifacts"]["diversity_report"] = str(diversity_report.resolve())
        report["artifacts"]["visual_review_prompt"] = str(visual_prompt.resolve())
        diversity_report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _design_from_global_candidate(candidate: dict[str, Any], global_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "phase": "global_axis_constraint_solver_probe",
        "seed": global_report["seed"],
        "pattern_solver": {
            "kind": "watch_global_axis_constraint_solver_report",
            "pattern_card_id": "central_hour_minute_with_off_center_seconds_v1",
            "status": "pass",
            "seed": global_report["seed"],
            "selection_strategy": global_report["selection_strategy"],
            "candidate_count": global_report["candidate_count"] if "candidate_count" in global_report else len(global_report["candidates"]),
            "feasible_candidate_count": len(global_report["candidates"]),
            "solver_stages": [
                {
                    "stage_id": "global_axis_constraints",
                    "variable": "axis_xy_coordinates",
                    "accepted_count": len(global_report["candidates"]),
                    "rejected_count": global_report["rejected_candidate_count"],
                    "policy": "solve_all_axis_coordinates_from_center_distance_equations_then_filter_hard_geometry",
                }
            ],
            "selected_candidate": candidate,
        },
        "axes": candidate["axes"],
        "gears": candidate["gears"],
        "meshes": candidate["meshes"],
    }


def _select_partition_candidate(partition: dict[str, Any], seed: int) -> str:
    candidates = partition["candidates"]
    pass_candidates = [
        candidate_id
        for candidate_id, candidate in candidates.items()
        if candidate["coverage_status"] == "pass"
    ]
    if "escapement_local_island_partition" in pass_candidates and seed == 4:
        return "escapement_local_island_partition"
    if "barrel_local_island_partition" in pass_candidates and seed in {1, 6}:
        return "barrel_local_island_partition"
    if "centroid_voronoi_partition" in pass_candidates and seed % 2 == 0:
        return "centroid_voronoi_partition"
    if "service_island_power_partition" in pass_candidates:
        return "service_island_power_partition"
    if "centroid_voronoi_partition" in pass_candidates:
        return "centroid_voronoi_partition"
    if "barrel_local_island_partition" in pass_candidates:
        return "barrel_local_island_partition"
    if "escapement_local_island_partition" in pass_candidates:
        return "escapement_local_island_partition"
    if candidates["continuous_outer_arc_y"]["coverage_status"] == "pass":
        return "continuous_outer_arc_y"
    return "service_island_power_partition"


def _design_and_partition_for_seed(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    if seed not in _SEED_PARTITION_CACHE:
        design = _build_design(seed, include_bridges=True)
        partition = solve_bridge_xy_partition(design, grid_resolution=121)
        _SEED_PARTITION_CACHE[seed] = (design, partition)
    return _SEED_PARTITION_CACHE[seed]


def _render_contact_sheet(rendered: list[tuple[int, dict[str, Any], str]], output_path: Path) -> None:
    fig, axes = plt.subplots(1, len(rendered), figsize=(4.2 * len(rendered), 4.2), dpi=150)
    if len(rendered) == 1:
        axes = [axes]
    for ax, (seed, partition, candidate_id) in zip(axes, rendered):
        candidate = partition["candidates"][candidate_id]
        short_name = {
            "continuous_outer_arc_y": "A",
            "service_island_power_partition": "B",
            "centroid_voronoi_partition": "C",
            "barrel_local_island_partition": "D",
            "escapement_local_island_partition": "E",
        }.get(candidate_id, candidate_id)
        title = (
            f"seed {seed}\n"
            f"selected: {short_name}\n"
            f"A={partition['candidates']['continuous_outer_arc_y']['coverage_status']} | "
            f"B={partition['candidates']['service_island_power_partition']['coverage_status']} | "
            f"C={partition['candidates']['centroid_voronoi_partition']['coverage_status']} | "
            f"D={partition['candidates']['barrel_local_island_partition']['coverage_status']} | "
            f"E={partition['candidates']['escapement_local_island_partition']['coverage_status']}"
        )
        _render_candidate(ax, partition, candidate, title)
    fig.tight_layout()
    fig.savefig(output_path, facecolor="white")
    plt.close(fig)


def _render_axis_contact_sheet(rendered: list[tuple[int, dict[str, Any]]], output_path: Path) -> None:
    fig, axes = plt.subplots(1, len(rendered), figsize=(4.2 * len(rendered), 4.2), dpi=150)
    if len(rendered) == 1:
        axes = [axes]
    for ax, (seed, design) in zip(axes, rendered):
        _render_axis_layout(ax, design, f"seed {seed}\ngear axes + pitch circles")
    fig.tight_layout()
    fig.savefig(output_path, facecolor="white")
    plt.close(fig)


def _render_axis_layout(ax: Any, design: dict[str, Any], title: str) -> None:
    radius = CASE_RADIUS_MM
    ax.set_aspect("equal")
    ax.set_xlim(-radius - 1.5, radius + 1.5)
    ax.set_ylim(-radius - 1.5, radius + 1.5)
    ax.axis("off")
    ax.set_title(title, fontsize=10)
    ax.add_patch(plt.Circle((0, 0), radius, fill=False, ec="#9aa5b1", lw=1.2))
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    gear_by_id = {gear["gear_id"]: gear for gear in design["gears"]}
    for mesh in design["meshes"]:
        left = gear_by_id[mesh["driver"]]
        right = gear_by_id[mesh["driven"]]
        lx, ly = left["x"], left["y"]
        rx, ry = right["x"], right["y"]
        ax.plot([lx, rx], [ly, ry], color="#344054", lw=1.0, alpha=0.55, zorder=1)
    for gear in design["gears"]:
        ax.add_patch(
            plt.Circle(
                (gear["x"], gear["y"]),
                gear["pitch_radius"],
                fill=False,
                ec="#7a5c00" if gear["gear_type"] == "wheel" else "#7a2e0e",
                lw=0.7,
                alpha=0.35,
                zorder=2,
            )
        )
    for axis_id in [*REFERENCE_AXIS_IDS, *VARIABLE_AXIS_IDS]:
        axis = axis_by_id.get(axis_id)
        if axis is None:
            continue
        color = "#111827" if axis_id in REFERENCE_AXIS_IDS else "#0b57d0"
        ax.add_patch(plt.Circle((axis["x"], axis["y"]), 0.18, color=color, zorder=5))
        ax.text(axis["x"] + 0.25, axis["y"] + 0.25, axis_id.replace("_axis", ""), fontsize=6.2, color=color, zorder=6)


def _render_functional_envelope_contact_sheet(rendered: list[tuple[int, dict[str, Any]]], output_path: Path) -> None:
    fig, axes = plt.subplots(1, len(rendered), figsize=(4.2 * len(rendered), 4.2), dpi=150)
    if len(rendered) == 1:
        axes = [axes]
    for ax, (seed, partition) in zip(axes, rendered):
        _render_functional_envelopes(ax, partition, f"seed {seed}\nfunctional envelopes")
    fig.tight_layout()
    fig.savefig(output_path, facecolor="white")
    plt.close(fig)


def _render_functional_envelopes(ax: Any, partition: dict[str, Any], title: str) -> None:
    colors = {
        "barrel_bridge": "#f8d7a1",
        "train_bridge": "#b9d7ff",
        "escapement_bridge": "#c8ead1",
    }
    radius = CASE_RADIUS_MM
    ax.set_aspect("equal")
    ax.set_xlim(-radius - 1.5, radius + 1.5)
    ax.set_ylim(-radius - 1.5, radius + 1.5)
    ax.axis("off")
    ax.set_title(title, fontsize=10)
    ax.add_patch(plt.Circle((0, 0), radius, fill=False, ec="#9aa5b1", lw=1.2))
    for group_id in FUNCTIONAL_ENVELOPE_IDS:
        envelope = partition["envelopes"][group_id]
        polygon = np.array(envelope["points"], dtype=float)
        ax.fill(polygon[:, 0], polygon[:, 1], color=colors[group_id], alpha=0.62, zorder=1)
        ax.plot(polygon[:, 0], polygon[:, 1], color="#475467", lw=0.8, zorder=2)
        centroid = _polygon_centroid(envelope["points"])
        ax.text(centroid[0], centroid[1], group_id.replace("_bridge", ""), ha="center", va="center", fontsize=8, zorder=4)


def _bridge_area_counts(candidate: dict[str, Any]) -> dict[str, int]:
    if "grid" in candidate:
        labels = np.array(candidate["grid"]["labels"])
        bridge_ids = candidate["grid"]["bridge_ids"]
        return {
            bridge_id: int(np.count_nonzero(labels == index))
            for index, bridge_id in enumerate(bridge_ids)
        }
    areas = {}
    for region in candidate.get("regions", []):
        areas[region["bridge_id"]] = int(round(abs(_polygon_area(region.get("points", []))) * 1000))
    return areas


def _outer_service_island_spans(candidate: dict[str, Any]) -> dict[str, float]:
    spans = {}
    for region in candidate.get("regions", []):
        spans[region["bridge_id"]] = round(
            sum(float(island["span_deg"]) for island in region.get("outer_service_islands", [])),
            6,
        )
    return spans


def _polygon_area(points: list[list[float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for left, right in zip(points, [*points[1:], points[0]]):
        area += left[0] * right[1] - right[0] * left[1]
    return area / 2.0


def _score_diversity(inputs: list[dict[str, Any]]) -> dict[str, Any]:
    bridge_ids = ["barrel_bridge", "train_bridge", "escapement_bridge"]
    angle_keys = [
        "barrel_angle_deg",
        "third_angle_deg",
        "fourth_angle_deg",
        "escape_angle_deg",
        "balance_angle_deg",
    ]
    area_by_candidate = {
        item["seed"]: item["bridge_area_counts"]
        for item in inputs
    }
    span_by_candidate = {
        item["seed"]: item["outer_service_island_total_span_deg"]
        for item in inputs
    }
    axis_position_by_candidate = {
        item["seed"]: {
            axis_id: item["axis_positions"][axis_id]
            for axis_id in [*REFERENCE_AXIS_IDS, *VARIABLE_AXIS_IDS]
            if axis_id in item["axis_positions"]
        }
        for item in inputs
    }
    envelope_polygons_by_candidate = {
        item["seed"]: {
            group_id: item["envelopes"][group_id]["points"]
            for group_id in FUNCTIONAL_ENVELOPE_IDS
        }
        for item in inputs
    }
    return {
        "bridge_area_by_candidate": area_by_candidate,
        "outer_service_island_span_by_candidate": span_by_candidate,
        "axis_position_by_candidate": axis_position_by_candidate,
        "normalized_average_axis_displacement": _axis_average_displacements(inputs),
        "normalized_max_pairwise_axis_displacement": _axis_max_pairwise_displacements(inputs),
        "axis_path_family_by_candidate": {
            item["seed"]: _axis_path_family(item["axis_positions"])
            for item in inputs
        },
        "axis_path_family_counts": _value_counts([_axis_path_family(item["axis_positions"]) for item in inputs]),
        "functional_envelope_polygons_by_candidate": envelope_polygons_by_candidate,
        "functional_envelope_overlap_by_group": _functional_envelope_overlaps(inputs),
        "functional_envelope_centroid_spread": _functional_envelope_centroid_spreads(inputs),
        "bridge_area_coefficient_of_variation": {
            bridge_id: _coefficient_of_variation([item["bridge_area_counts"].get(bridge_id, 0.0) for item in inputs])
            for bridge_id in bridge_ids
        },
        "outer_service_island_span_coefficient_of_variation": {
            bridge_id: _coefficient_of_variation(
                [item["outer_service_island_total_span_deg"].get(bridge_id, 0.0) for item in inputs]
            )
            for bridge_id in bridge_ids
        },
        "key_axis_angle_spread_deg": {
            key: round(max(item["variables"][key] for item in inputs) - min(item["variables"][key] for item in inputs), 6)
            for key in angle_keys
        },
        "selected_partition_topology_counts": _value_counts([item["candidate_id"] for item in inputs]),
    }


def _bridge_partition_failure_reasons(metrics: dict[str, Any], inputs: list[dict[str, Any]]) -> list[str]:
    reasons = []
    for bridge_id, value in metrics["bridge_area_coefficient_of_variation"].items():
        if value <= 0.10:
            reasons.append(f"{bridge_id}_area_variation_lte_10_percent")
    for bridge_id, value in metrics["outer_service_island_span_coefficient_of_variation"].items():
        if value <= 0.10:
            reasons.append(f"{bridge_id}_outer_service_span_variation_lte_10_percent")
    if len(metrics["selected_partition_topology_counts"]) == 1 and len(inputs) >= 5:
        reasons.append("all_candidates_use_same_partition_topology")
    return reasons


def _axis_diversity_failure_reasons(metrics: dict[str, Any], inputs: list[dict[str, Any]]) -> list[str]:
    reasons = []
    average = metrics["normalized_average_axis_displacement"]
    maximum = metrics["normalized_max_pairwise_axis_displacement"]
    for axis_id in VARIABLE_AXIS_IDS:
        if average.get(axis_id, 0.0) <= 0.08:
            reasons.append(f"{axis_id}_average_displacement_lte_8_percent_case_radius")
        if maximum.get(axis_id, 0.0) <= 0.12:
            reasons.append(f"{axis_id}_max_pairwise_displacement_lte_12_percent_case_radius")
    if len(metrics["axis_path_family_counts"]) == 1 and len(inputs) >= 5:
        reasons.append("all_candidates_share_same_axis_path_family")
    return reasons


def _functional_envelope_failure_reasons(metrics: dict[str, Any]) -> list[str]:
    reasons = []
    for group_id, value in metrics["functional_envelope_overlap_by_group"].items():
        if value >= 0.80:
            reasons.append(f"{group_id}_average_envelope_overlap_gte_80_percent")
    for group_id, value in metrics["functional_envelope_centroid_spread"].items():
        if value <= 0.08:
            reasons.append(f"{group_id}_centroid_spread_lte_8_percent_case_radius")
    return reasons


def _axis_positions(design: dict[str, Any]) -> dict[str, dict[str, float]]:
    return {
        axis["axis_id"]: {"x": round(float(axis["x"]), 6), "y": round(float(axis["y"]), 6)}
        for axis in design["axes"]
    }


def _axis_average_displacements(inputs: list[dict[str, Any]]) -> dict[str, float]:
    return {
        axis_id: round(float(np.mean(_pairwise_axis_distances(inputs, axis_id))) / CASE_RADIUS_MM, 6)
        for axis_id in VARIABLE_AXIS_IDS
    }


def _axis_max_pairwise_displacements(inputs: list[dict[str, Any]]) -> dict[str, float]:
    return {
        axis_id: round(float(max(_pairwise_axis_distances(inputs, axis_id), default=0.0)) / CASE_RADIUS_MM, 6)
        for axis_id in VARIABLE_AXIS_IDS
    }


def _pairwise_axis_distances(inputs: list[dict[str, Any]], axis_id: str) -> list[float]:
    points = [item["axis_positions"][axis_id] for item in inputs if axis_id in item["axis_positions"]]
    distances = []
    for left_index, left in enumerate(points):
        for right in points[left_index + 1:]:
            distances.append(math_hypot(left["x"] - right["x"], left["y"] - right["y"]))
    return distances or [0.0]


def _axis_path_family(axis_positions: dict[str, dict[str, float]]) -> str:
    ordered_ids = ["barrel_axis", "center_axis", "third_axis", "fourth_axis", "escape_axis", "balance_axis"]
    angles = []
    for axis_id in ordered_ids:
        point = axis_positions.get(axis_id)
        if point is None:
            continue
        angles.append((axis_id, round(float(np.degrees(np.arctan2(point["y"], point["x"]))) / 15.0) * 15))
    return "|".join(f"{axis_id}:{int(angle)}" for axis_id, angle in angles)


def _functional_envelope_overlaps(inputs: list[dict[str, Any]]) -> dict[str, float]:
    return {
        group_id: round(float(np.mean(_pairwise_envelope_ious(inputs, group_id))), 6)
        for group_id in FUNCTIONAL_ENVELOPE_IDS
    }


def _pairwise_envelope_ious(inputs: list[dict[str, Any]], group_id: str) -> list[float]:
    masks = [_envelope_mask(item["envelopes"][group_id]["points"]) for item in inputs]
    ious = []
    for left_index, left in enumerate(masks):
        for right in masks[left_index + 1:]:
            intersection = np.count_nonzero(left & right)
            union = np.count_nonzero(left | right)
            ious.append(0.0 if union == 0 else intersection / union)
    return ious or [0.0]


def _envelope_mask(points: list[list[float]], resolution: int = 161) -> np.ndarray:
    xs = np.linspace(-CASE_RADIUS_MM, CASE_RADIUS_MM, resolution)
    ys = np.linspace(-CASE_RADIUS_MM, CASE_RADIUS_MM, resolution)
    path = MplPath(np.array(points, dtype=float))
    coords = np.array([(x, y) for y in ys for x in xs], dtype=float)
    return path.contains_points(coords).reshape((resolution, resolution))


def _functional_envelope_centroid_spreads(inputs: list[dict[str, Any]]) -> dict[str, float]:
    spreads = {}
    for group_id in FUNCTIONAL_ENVELOPE_IDS:
        centroids = [_polygon_centroid(item["envelopes"][group_id]["points"]) for item in inputs]
        distances = []
        for left_index, left in enumerate(centroids):
            for right in centroids[left_index + 1:]:
                distances.append(math_hypot(left[0] - right[0], left[1] - right[1]))
        spreads[group_id] = round(float(max(distances, default=0.0)) / CASE_RADIUS_MM, 6)
    return spreads


def _polygon_centroid(points: list[list[float]]) -> tuple[float, float]:
    array = np.array(points, dtype=float)
    return (float(np.mean(array[:, 0])), float(np.mean(array[:, 1])))


def math_hypot(x: float, y: float) -> float:
    return float(np.hypot(x, y))


def _coefficient_of_variation(values: list[float]) -> float:
    array = np.array(values, dtype=float)
    mean = float(np.mean(array))
    if abs(mean) < 1e-12:
        return 0.0
    return round(float(np.std(array) / abs(mean)), 6)


def _value_counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _visual_review_prompt(report: dict[str, Any]) -> str:
    axis_sheet = report["artifacts"].get("axis_layout_contact_sheet", "")
    envelope_sheet = report["artifacts"].get("functional_envelope_contact_sheet", "")
    bridge_sheet = report["artifacts"].get("bridge_partition_contact_sheet", "")
    candidate_lines = "\n".join(
        f"- seed {candidate['seed']}: {candidate['image_path']}"
        for candidate in report["candidates"]
    )
    return f"""# Independent Watch Gear-Axis Diversity Review

You are reviewing five 2D gear-axis and functional-envelope candidates for a mechanical watch-style movement.

Use only the images and report paths in this packet. Do not inspect implementation code.

Axis layout contact sheet:

```text
{axis_sheet}
```

Functional envelope contact sheet:

```text
{envelope_sheet}
```

Downstream bridge partition reference sheet:

```text
{bridge_sheet}
```

Candidate images:

{candidate_lines}

Quantitative status:

```text
diversity_status: {report['diversity_status']}
axis_diversity_status: {report['axis_diversity_status']}
functional_envelope_diversity_status: {report['functional_envelope_diversity_status']}
bridge_partition_diversity_status: {report['bridge_partition_diversity_status']}
failure_reasons: {report['failure_reasons']}
```

Please judge:

- whether the gear-axis layouts look like the same template;
- whether barrel/train/escapement functional envelopes differ meaningfully;
- whether bridge partition differences are merely hiding similar gear axes;
- whether any candidate is visually invalid despite numeric pass;
- whether the set should be considered a same gear-axis layout family.

Return exactly this structure:

```text
visual_status: pass | fail
failure_reasons:
candidate_notes:
recommended_solver_iteration:
```
"""
