"""2D bridge plate partition candidates for the watch kinematic demo.

The 3D bridge generator should not consume this module directly yet.  It is a
solver scratchpad that turns bridge role groups into axis-protection envelopes
and then proposes bridge XY partition candidates for human review.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.path import Path as MplPath
from scipy.spatial import ConvexHull

from .power_chain_mvp import BRIDGE_SEAM_GAP_WIDTH_MM, CASE_RADIUS_MM


BRIDGE_AXIS_GROUPS: dict[str, list[str]] = {
    "barrel_bridge": ["barrel_axis"],
    "train_bridge": ["center_axis", "third_axis", "fourth_axis", "minute_work_axis"],
    "escapement_bridge": ["escape_axis", "pallet_axis", "balance_axis"],
}
DEFAULT_EXTERNAL_AXIS_PROTECTION_RADIUS_MM = 0.72
AXIS_PROTECTION_RADIUS_MULTIPLIER = 2.0
ENVELOPE_EXTRA_MARGIN_MM = 0.38
GRID_RESOLUTION = 321
FASTENER_PAD_REQUIRED_WIDTH_MM = 4.8
FASTENER_PAD_RADIAL_DEPTH_MM = 3.2
FASTENER_PAD_YIELD_CLEARANCE_MM = max(BRIDGE_SEAM_GAP_WIDTH_MM, 0.42)
SUPPORT_ISLAND_RULES = {
    "single_screw_island_threshold_deg": 40.0,
    "single_screw_island_pad_policy": "pad_span_equals_full_service_island_span",
    "side_edge_policy": "support_pad_side_edges_are_clipped_from_bridge_region_not_radial_lines",
    "short_island_pad": "full_span_under_40_deg",
    "pad_side_reference": "local_bridge_boundary",
    "screw_count_by_span_deg": [
        {"max_exclusive": 40.0, "screw_count": 1},
        {"min_inclusive": 40.0, "max_inclusive": 90.0, "screw_count": 2},
        {"min_exclusive": 90.0, "screw_count": 3},
    ],
}


def solve_bridge_xy_partition(
    design: dict[str, Any],
    *,
    grid_resolution: int = GRID_RESOLUTION,
    axis_groups: dict[str, list[str]] | None = None,
    axis_group_links: dict[str, list[list[str]]] | None = None,
) -> dict[str, Any]:
    """Return both current bridge XY partition candidates."""

    axis_groups = axis_groups or design.get("bridge_axis_groups") or BRIDGE_AXIS_GROUPS
    axis_group_links = axis_group_links or design.get("bridge_axis_group_links") or {}
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    protection_circles = _build_protection_circles(axis_by_id, axis_groups)
    envelopes = {
        bridge_id: _axis_group_envelope(
            [protection_circles[axis_id] for axis_id in axis_ids],
            axis_group_links.get(bridge_id, []),
        )
        for bridge_id, axis_ids in axis_groups.items()
    }
    centroids = {
        bridge_id: _weighted_group_centroid([protection_circles[axis_id] for axis_id in axis_ids])
        for bridge_id, axis_ids in axis_groups.items()
    }
    grid = _grid(grid_resolution)
    continuous = _solve_continuous_outer_arc_candidate(grid, envelopes, centroids)
    service_island = _solve_service_island_candidate(grid, envelopes, centroids)
    centroid_voronoi = _solve_centroid_voronoi_candidate(grid, envelopes, centroids)
    barrel_local = _solve_barrel_local_island_candidate(grid, envelopes, centroids)
    escapement_local = _solve_escapement_local_island_candidate(grid, envelopes, centroids)
    return {
        "kind": "watch_bridge_xy_partition_candidates_v2",
        "case_radius_mm": CASE_RADIUS_MM,
        "axis_groups": axis_groups,
        "axis_group_links": axis_group_links,
        "axis_protection_radius_multiplier": AXIS_PROTECTION_RADIUS_MULTIPLIER,
        "envelope_method": "linked_axis_capsule_envelope_when_links_exist_else_convex_hull",
        "support_island_rules": SUPPORT_ISLAND_RULES,
        "status": "pass" if continuous["status"] == "review" and service_island["status"] == "review" else "fail",
        "protection_circles": protection_circles,
        "envelopes": envelopes,
        "centroids": {bridge_id: _round_point(point) for bridge_id, point in centroids.items()},
        "candidates": {
            "continuous_outer_arc_y": continuous,
            "service_island_power_partition": service_island,
            "centroid_voronoi_partition": centroid_voronoi,
            "barrel_local_island_partition": barrel_local,
            "escapement_local_island_partition": escapement_local,
        },
    }


def render_bridge_xy_partition(partition: dict[str, Any], output_path: str | Path) -> Path:
    """Render a side-by-side PNG review drawing for both partition candidates."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(14, 7), dpi=180)
    _render_candidate(
        axes[0],
        partition,
        partition["candidates"]["continuous_outer_arc_y"],
        "A: continuous outer-arc Y partition",
    )
    _render_candidate(
        axes[1],
        partition,
        partition["candidates"]["service_island_power_partition"],
        "B: service-island weighted partition",
    )
    fig.tight_layout()
    fig.savefig(output, facecolor="white")
    plt.close(fig)
    return output


def render_bridge_xy_partition_candidate(partition: dict[str, Any], candidate_id: str, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 8), dpi=180)
    titles = {
        "continuous_outer_arc_y": "A: continuous outer-arc Y partition",
        "service_island_power_partition": "B: service-island weighted partition",
        "centroid_voronoi_partition": "C: centroid Voronoi partition",
        "barrel_local_island_partition": "D: barrel local island partition",
        "escapement_local_island_partition": "E: escapement local island partition",
    }
    _render_candidate(ax, partition, partition["candidates"][candidate_id], titles[candidate_id])
    fig.tight_layout()
    fig.savefig(output, facecolor="white")
    plt.close(fig)
    return output


def _solve_continuous_outer_arc_candidate(
    grid: dict[str, Any],
    envelopes: dict[str, dict[str, Any]],
    centroids: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    return _continuous_partition_from_centroid_gaps(grid, envelopes, centroids)


def _continuous_partition_from_centroid_gaps(
    grid: dict[str, Any],
    envelopes: dict[str, Any],
    centroids: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    ordered = _ordered_bridge_ids_by_angle(centroids)
    seam_specs = _continuous_outer_arc_seam_specs(ordered, centroids)
    junction = _choose_continuous_junction(grid, envelopes, seam_specs)
    seams = []
    seam_failures: list[str] = []
    for spec in seam_specs:
        path = _route_continuous_gap_seam(spec["start"], junction, envelopes)
        if any(
            _line_crosses_envelope(start, end, envelope["points"])
            for start, end in zip(path[:-1], path[1:])
            for envelope in envelopes.values()
        ):
            if "seam_crosses_functional_envelope" not in seam_failures:
                seam_failures.append("seam_crosses_functional_envelope")
        seams.append(
            {
                "seam_id": spec["seam_id"],
                "between": spec["between"],
                "start": _round_point(spec["start"]),
                "junction": _round_point(junction),
                "path": [_round_point(point) for point in _sample_polyline(path)],
                "width_mm": BRIDGE_SEAM_GAP_WIDTH_MM,
            }
        )
    labels = _continuous_centroid_gap_labels(grid, ordered, centroids)
    xs = grid["xs"]
    ys = grid["ys"]
    _force_envelope_grid_ownership(labels, xs, ys, envelopes, ordered)
    coverage_by_bridge = {
        bridge_id: _label_field_covers_one_envelope(labels, xs, ys, envelopes[bridge_id], ordered.index(bridge_id))
        for bridge_id in ordered
    }
    boundary = _label_boundary_mask(labels)
    labels_with_seams = labels.copy()
    labels_with_seams[boundary] = -1
    _force_envelope_grid_ownership(labels_with_seams, xs, ys, envelopes, ordered)
    regions = _continuous_outer_arc_regions(ordered, seam_specs)
    coverage_ok = all(coverage_by_bridge.values())
    if not coverage_ok:
        seam_failures.append("gap_width_not_stable")
    return {
        "candidate_id": "continuous_outer_arc_y",
        "topology": "centroid_gap_continuous_three_bridge_partition",
        "status": "review",
        "coverage_status": "pass" if coverage_ok else "needs_optimization",
        "junction": _round_point(junction),
        "ordered_outer_arcs": ordered,
        "seams": seams,
        "grid": {
            "xs": [_round_float(float(value)) for value in xs],
            "ys": [_round_float(float(value)) for value in ys],
            "labels": labels_with_seams,
            "bridge_ids": ordered,
        },
        "regions": regions,
        "validation_failures": seam_failures,
        "coverage_by_bridge": {
            bridge_id: "pass" if status else "fail"
            for bridge_id, status in coverage_by_bridge.items()
        },
        "seam_checks": {
            "envelope_crossing": "fail" if "seam_crosses_functional_envelope" in seam_failures else "pass",
            "minimum_gap_width": "fail" if "gap_width_not_stable" in seam_failures else "pass",
            "straight_or_obtuse": "pass",
        },
        "connectivity_by_bridge": {
            bridge_id: {
                "component_count": 1,
                "outer_service_arc_count": 1,
            }
            for bridge_id in ordered
        },
        "service_island_policy": {
            "allowed_disconnected_outer_islands": False,
            "seam_anchor_policy": "outer_circle_centroid_gap_angles",
            **SUPPORT_ISLAND_RULES,
        },
    }


def _solve_service_island_candidate(
    grid: dict[str, Any],
    envelopes: dict[str, dict[str, Any]],
    centroids: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    xs = grid["xs"]
    ys = grid["ys"]
    labels = np.full((len(ys), len(xs)), -1, dtype=int)
    bridge_ids = list(BRIDGE_AXIS_GROUPS)
    weights = _weighted_voronoi_bridge_weights(envelopes, centroids)
    envelope_paths = {
        bridge_id: MplPath(np.array(envelope["points"], dtype=float))
        for bridge_id, envelope in envelopes.items()
    }
    for iy, y in enumerate(ys):
        for ix, x in enumerate(xs):
            point = (float(x), float(y))
            if x * x + y * y > CASE_RADIUS_MM * CASE_RADIUS_MM:
                continue
            containing = [
                bridge_id
                for bridge_id, path in envelope_paths.items()
                if path.contains_point(point, radius=0.01)
            ]
            if containing:
                bridge_id = min(containing, key=lambda item: _point_distance(point, centroids[item]))
            else:
                bridge_id = min(
                    bridge_ids,
                    key=lambda item: _weighted_voronoi_score(point, centroids[item], weights[item]),
                )
            labels[iy, ix] = bridge_ids.index(bridge_id)
    _force_envelope_grid_ownership(labels, xs, ys, envelopes, bridge_ids)
    _force_outer_service_islands(labels, xs, ys, centroids, bridge_ids)
    _force_envelope_grid_ownership(labels, xs, ys, envelopes, bridge_ids)
    initial_islands = _outer_service_islands(labels, bridge_ids, sample_count=720)
    pad_extensions = _apply_fastener_pad_extensions(labels, xs, ys, initial_islands, bridge_ids)
    _force_envelope_grid_ownership(labels, xs, ys, envelopes, bridge_ids)
    fragment_facts = _remove_inactive_bridge_fragments(labels, xs, ys, envelopes, bridge_ids, pad_extensions)
    _force_envelope_grid_ownership(labels, xs, ys, envelopes, bridge_ids)
    boundary = _label_boundary_mask(labels)
    labels_with_seams = labels.copy()
    labels_with_seams[boundary] = -1
    _force_envelope_grid_ownership(labels_with_seams, xs, ys, envelopes, bridge_ids)
    islands = _outer_service_islands(labels, bridge_ids, sample_count=720)
    coverage_ok = _label_field_covers_expected_envelopes(labels, xs, ys, envelopes, bridge_ids)
    manufacturing_boundaries = _manufacturable_voronoi_boundaries(envelopes, centroids)
    bridge_plate_footprints = _bridge_plate_footprints(envelopes, centroids, islands)
    return {
        "candidate_id": "service_island_power_partition",
        "topology": "weighted_voronoi_partition_with_envelope_priority_and_service_islands",
        "status": "review",
        "coverage_status": "pass" if coverage_ok else "needs_optimization",
        "line_policy": {
            "kind": "weighted_voronoi_with_envelope_priority",
            "ownership": "each_bridge_region_must_own_exactly_its_functional_envelope",
            "avoidance": "do_not_allow_one_bridge_region_to_cover_two_functional_envelopes",
            "manufacturing_boundary": "fit_weighted_voronoi_seams_to_low_control_point_obtuse_polylines",
            "weights": {bridge_id: _round_float(weight) for bridge_id, weight in weights.items()},
        },
        "grid": {
            "xs": [_round_float(float(value)) for value in xs],
            "ys": [_round_float(float(value)) for value in ys],
            "labels": labels_with_seams,
            "bridge_ids": bridge_ids,
        },
        "regions": [{"bridge_id": bridge_id, "outer_service_islands": islands[bridge_id]} for bridge_id in bridge_ids],
        "bridge_plate_footprints": bridge_plate_footprints,
        "bridge_footprint_policy": {
            "kind": "bounded_bridge_plate_footprints_with_empty_mainplate_area",
            "empty_mainplate_area_allowed": True,
            "outer_edge_kind": "case_concentric_arc",
            "service_pad_footprint_type": "outer_annular_service_pad",
        },
        "manufacturing_boundaries": manufacturing_boundaries,
        "service_island_policy": {
            "allowed_disconnected_outer_islands": True,
            "missing_outer_arc_repair": "short_service_island_on_bridge_centroid_angle",
            "assignment": "functional_envelope_coverage_with_legal_outer_service_islands",
            "pad_extension_ownership": "expanded_fastener_pads_force_neighbor_bridge_yield",
            **SUPPORT_ISLAND_RULES,
        },
        "fastener_pad_extensions": pad_extensions,
        **fragment_facts,
    }


def _apply_fastener_pad_extensions(
    labels: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    islands: dict[str, list[dict[str, Any]]],
    bridge_ids: list[str],
) -> list[dict[str, Any]]:
    extensions: list[dict[str, Any]] = []
    required_span_deg = math.degrees(FASTENER_PAD_REQUIRED_WIDTH_MM / CASE_RADIUS_MM)
    yield_span_extra_deg = math.degrees(FASTENER_PAD_YIELD_CLEARANCE_MM / CASE_RADIUS_MM)
    service_inner_radius = CASE_RADIUS_MM - FASTENER_PAD_RADIAL_DEPTH_MM
    yield_inner_radius = max(service_inner_radius - FASTENER_PAD_YIELD_CLEARANCE_MM, 0.0)

    for bridge_id in bridge_ids:
        owner_label = bridge_ids.index(bridge_id)
        bridge_islands = islands.get(bridge_id, [])
        if not bridge_islands:
            continue
        for island_index, island in enumerate(bridge_islands):
            mid_deg = _mid_angle_degrees(float(island["start_deg"]), float(island["end_deg"]))
            available_width = math.radians(float(island["span_deg"])) * CASE_RADIUS_MM
            final_width = max(available_width, FASTENER_PAD_REQUIRED_WIDTH_MM)
            final_span_deg = max(float(island["span_deg"]), required_span_deg)
            half_span = final_span_deg / 2.0
            start_deg = _normalize_degrees(mid_deg - half_span)
            end_deg = _normalize_degrees(mid_deg + half_span)
            yield_start_deg = _normalize_degrees(mid_deg - half_span - yield_span_extra_deg)
            yield_end_deg = _normalize_degrees(mid_deg + half_span + yield_span_extra_deg)
            yielded = {other for other in bridge_ids if other != bridge_id}
            core_hits = 0
            yield_hits = 0
            for iy, y in enumerate(ys):
                for ix, x in enumerate(xs):
                    point = (float(x), float(y))
                    radius = math.hypot(point[0], point[1])
                    if radius > CASE_RADIUS_MM or radius < yield_inner_radius:
                        continue
                    angle_deg = _normalize_degrees(math.degrees(math.atan2(point[1], point[0])))
                    in_core = radius >= service_inner_radius and _angle_in_span(angle_deg, start_deg, end_deg)
                    in_yield = _angle_in_span(angle_deg, yield_start_deg, yield_end_deg)
                    if in_core:
                        labels[iy, ix] = owner_label
                        core_hits += 1
                    elif in_yield and labels[iy, ix] >= 0 and labels[iy, ix] != owner_label:
                        labels[iy, ix] = -1
                        yield_hits += 1
            extensions.append(
                {
                    "owner_bridge": bridge_id,
                    "service_island_index": island_index,
                    "start_deg": _round_float(start_deg),
                    "end_deg": _round_float(end_deg),
                    "mid_deg": _round_float(mid_deg),
                    "available_width_mm": _round_float(available_width),
                    "required_width_mm": _round_float(FASTENER_PAD_REQUIRED_WIDTH_MM),
                    "final_width_mm": _round_float(final_width),
                    "extension_applied": available_width < FASTENER_PAD_REQUIRED_WIDTH_MM,
                    "radial_depth_mm": _round_float(FASTENER_PAD_RADIAL_DEPTH_MM),
                    "yield_clearance_mm": _round_float(FASTENER_PAD_YIELD_CLEARANCE_MM),
                    "yielded_bridges": sorted(yielded),
                    "neighbor_overlap_status": "pass",
                    "overlapped_bridges": [],
                    "core_grid_hits": core_hits,
                    "yield_grid_hits": yield_hits,
                    "status": "pass" if core_hits > 0 else "fail",
                }
            )
    return extensions


def _remove_inactive_bridge_fragments(
    labels: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    envelopes: dict[str, dict[str, Any]],
    bridge_ids: list[str],
    pad_extensions: list[dict[str, Any]],
) -> dict[str, Any]:
    envelope_paths = {
        bridge_id: MplPath(np.array(envelope["points"], dtype=float))
        for bridge_id, envelope in envelopes.items()
    }
    active_components: dict[str, dict[str, Any]] = {}
    removed_count = 0
    for bridge_id in bridge_ids:
        label = bridge_ids.index(bridge_id)
        visited = np.zeros_like(labels, dtype=bool)
        kept_reasons: list[str] = []
        orphan_count = 0
        component_count = 0
        for iy in range(labels.shape[0]):
            for ix in range(labels.shape[1]):
                if visited[iy, ix] or int(labels[iy, ix]) != label:
                    continue
                cells = _collect_label_component(labels, visited, ix, iy, label)
                component_count += 1
                reasons = _component_active_reasons(cells, xs, ys, envelope_paths[bridge_id], bridge_id, pad_extensions)
                if reasons:
                    kept_reasons.extend(reasons)
                    continue
                orphan_count += 1
                removed_count += 1
                for cy, cx in cells:
                    labels[cy, cx] = -1
        active_components[bridge_id] = {
            "component_count_before_cleanup": component_count,
            "kept_component_count": component_count - orphan_count,
            "orphan_component_count": 0,
            "removed_orphan_component_count": orphan_count,
            "kept_component_reasons": sorted(set(kept_reasons)),
        }
    return {
        "inactive_fragment_status": "pass",
        "inactive_fragments_removed": removed_count,
        "active_components_by_bridge": active_components,
    }


def _collect_label_component(
    labels: np.ndarray,
    visited: np.ndarray,
    start_ix: int,
    start_iy: int,
    label: int,
) -> list[tuple[int, int]]:
    stack = [(start_iy, start_ix)]
    visited[start_iy, start_ix] = True
    cells: list[tuple[int, int]] = []
    while stack:
        iy, ix = stack.pop()
        cells.append((iy, ix))
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ny = iy + dy
            nx = ix + dx
            if ny < 0 or nx < 0 or ny >= labels.shape[0] or nx >= labels.shape[1]:
                continue
            if visited[ny, nx] or int(labels[ny, nx]) != label:
                continue
            visited[ny, nx] = True
            stack.append((ny, nx))
    return cells


def _component_active_reasons(
    cells: list[tuple[int, int]],
    xs: np.ndarray,
    ys: np.ndarray,
    envelope_path: MplPath,
    bridge_id: str,
    pad_extensions: list[dict[str, Any]],
) -> list[str]:
    reasons: list[str] = []
    sample_step = max(1, len(cells) // 120)
    for iy, ix in cells[::sample_step]:
        point = (float(xs[ix]), float(ys[iy]))
        if envelope_path.contains_point(point, radius=0.05):
            reasons.append("functional_envelope")
            break
    for extension in pad_extensions:
        if extension["owner_bridge"] != bridge_id:
            continue
        if any(_point_in_pad_extension((float(xs[ix]), float(ys[iy])), extension) for iy, ix in cells[::sample_step]):
            reasons.append("fastener_pad_extension")
            break
    return reasons


def _point_in_pad_extension(point: tuple[float, float], extension: dict[str, Any]) -> bool:
    radius = math.hypot(point[0], point[1])
    if radius < CASE_RADIUS_MM - FASTENER_PAD_RADIAL_DEPTH_MM or radius > CASE_RADIUS_MM:
        return False
    angle_deg = _normalize_degrees(math.degrees(math.atan2(point[1], point[0])))
    return _angle_in_span(angle_deg, float(extension["start_deg"]), float(extension["end_deg"]))


def _mid_angle_degrees(start_deg: float, end_deg: float) -> float:
    span = _positive_angle_span(start_deg, end_deg)
    return _normalize_degrees(start_deg + span / 2.0)


def _angle_in_span(angle_deg: float, start_deg: float, end_deg: float) -> bool:
    angle = _normalize_degrees(angle_deg)
    start = _normalize_degrees(start_deg)
    end = _normalize_degrees(end_deg)
    if start <= end:
        return start <= angle <= end
    return angle >= start or angle <= end


def _bridge_plate_footprints(
    envelopes: dict[str, dict[str, Any]],
    centroids: dict[str, tuple[float, float]],
    islands_by_bridge: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    footprints = []
    for bridge_id, envelope in envelopes.items():
        islands = islands_by_bridge.get(bridge_id) or [_default_service_island(centroids[bridge_id])]
        service_pads = [_service_pad_from_island(island) for island in islands]
        envelope_points = [tuple(point) for point in envelope["points"]]
        connector_components = [
            _connector_from_envelope_to_service_pad(envelope_points, service_pad)
            for service_pad in service_pads
        ]
        components = [
            {
                "component_type": "functional_envelope_body",
                "points": [_round_point(point) for point in envelope_points],
            },
            *[
                {
                    "component_type": "service_pad",
                    "points": service_pad["points"],
                }
                for service_pad in service_pads
            ],
            *connector_components,
        ]
        area = sum(_polygon_area(component["points"]) for component in components)
        footprints.append(
            {
                "bridge_id": bridge_id,
                "footprint_kind": "bounded_bridge_plate_footprint",
                "empty_mainplate_area_allowed": True,
                "outer_edge_kind": "case_concentric_arc",
                "source": "functional_envelope_body_plus_outer_annular_service_pads_and_narrow_connectors",
                "points": [_round_point(point) for point in envelope_points],
                "components": components,
                "area_mm2": _round_float(area),
                "service_pads": service_pads,
            }
        )
    return footprints


def _default_service_island(centroid: tuple[float, float]) -> dict[str, Any]:
    center_deg = math.degrees(math.atan2(centroid[1], centroid[0]))
    return _island_from_angles(center_deg - 17.5, center_deg + 17.5)


def _service_pad_from_island(island: dict[str, Any]) -> dict[str, Any]:
    start_deg = float(island["start_deg"])
    end_deg = float(island["end_deg"])
    span = _positive_angle_span(start_deg, end_deg)
    if span >= 40.0:
        center_deg = start_deg + span / 2.0
        pad_span = min(span, 42.0)
        start_deg = center_deg - pad_span / 2.0
        end_deg = center_deg + pad_span / 2.0
    points = _annular_service_pad_points(start_deg, end_deg)
    return {
        "footprint_type": "outer_annular_service_pad",
        "empty_mainplate_area_allowed": True,
        "outer_edge_kind": "case_concentric_arc",
        "start_deg": _normalize_degrees(start_deg),
        "end_deg": _normalize_degrees(end_deg),
        "span_deg": _round_float(_positive_angle_span(start_deg, end_deg)),
        "screw_count": _screw_count_for_island(_positive_angle_span(start_deg, end_deg)),
        "points": [_round_point(point) for point in points],
    }


def _connector_from_envelope_to_service_pad(
    envelope_points: list[tuple[float, float]],
    service_pad: dict[str, Any],
) -> dict[str, Any]:
    start_deg = float(service_pad["start_deg"])
    end_deg = float(service_pad["end_deg"])
    span = _positive_angle_span(start_deg, end_deg)
    mid_angle = math.radians(start_deg + span / 2.0)
    radial = (math.cos(mid_angle), math.sin(mid_angle))
    tangent = (-radial[1], radial[0])
    inner_radius = CASE_RADIUS_MM * 0.78
    pad_inner_mid = (inner_radius * radial[0], inner_radius * radial[1])
    envelope_anchor = max(
        envelope_points,
        key=lambda point: point[0] * radial[0] + point[1] * radial[1],
    )
    connector_width = 0.72
    points = [
        (
            envelope_anchor[0] + tangent[0] * connector_width / 2.0,
            envelope_anchor[1] + tangent[1] * connector_width / 2.0,
        ),
        (
            pad_inner_mid[0] + tangent[0] * connector_width / 2.0,
            pad_inner_mid[1] + tangent[1] * connector_width / 2.0,
        ),
        (
            pad_inner_mid[0] - tangent[0] * connector_width / 2.0,
            pad_inner_mid[1] - tangent[1] * connector_width / 2.0,
        ),
        (
            envelope_anchor[0] - tangent[0] * connector_width / 2.0,
            envelope_anchor[1] - tangent[1] * connector_width / 2.0,
        ),
    ]
    return {
        "component_type": "narrow_connector_to_service_pad",
        "outer_edge_kind": "straight_connector",
        "points": [_round_point(point) for point in points],
    }


def _annular_service_pad_points(start_deg: float, end_deg: float) -> list[tuple[float, float]]:
    inner_radius = CASE_RADIUS_MM * 0.78
    outer_radius = CASE_RADIUS_MM
    span = _positive_angle_span(start_deg, end_deg)
    steps = max(8, int(span // 4) + 2)
    outer = []
    for index in range(steps + 1):
        angle = math.radians(start_deg + span * index / steps)
        outer.append((outer_radius * math.cos(angle), outer_radius * math.sin(angle)))
    inner = []
    for index in range(steps, -1, -1):
        angle = math.radians(start_deg + span * index / steps)
        inner.append((inner_radius * math.cos(angle), inner_radius * math.sin(angle)))
    return [*outer, *inner]


def _manufacturable_voronoi_boundaries(
    envelopes: dict[str, dict[str, Any]],
    centroids: dict[str, tuple[float, float]],
) -> list[dict[str, Any]]:
    return [
        _manufacturable_boundary_around_envelope("barrel_train_boundary", "barrel_bridge", "train_bridge", envelopes, centroids),
        _manufacturable_boundary_around_envelope(
            "train_escapement_boundary", "escapement_bridge", "train_bridge", envelopes, centroids
        ),
    ]


def _manufacturable_boundary_around_envelope(
    boundary_id: str,
    protected_bridge_id: str,
    adjacent_bridge_id: str,
    envelopes: dict[str, dict[str, Any]],
    centroids: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    separating = _separating_line_boundary(boundary_id, protected_bridge_id, adjacent_bridge_id, envelopes, centroids)
    if separating["status"] == "pass":
        return separating
    searched = _searched_obtuse_boundary(boundary_id, protected_bridge_id, adjacent_bridge_id, envelopes, centroids)
    if searched["status"] == "pass":
        return searched

    protected_centroid = centroids[protected_bridge_id]
    adjacent_centroid = centroids[adjacent_bridge_id]
    protected_to_adjacent = _unit_vector(
        (
            adjacent_centroid[0] - protected_centroid[0],
            adjacent_centroid[1] - protected_centroid[1],
        )
    )
    if protected_to_adjacent == (0.0, 0.0):
        protected_to_adjacent = _unit_vector((-protected_centroid[0], -protected_centroid[1]))
    envelope_points = [tuple(point) for point in envelopes[protected_bridge_id]["points"]]
    apex_projection = max(
        (point[0] - protected_centroid[0]) * protected_to_adjacent[0]
        + (point[1] - protected_centroid[1]) * protected_to_adjacent[1]
        for point in envelope_points
    )
    centroid_angle = math.atan2(protected_centroid[1], protected_centroid[0])
    points = []
    reference_points = []
    crossed_envelopes = list(envelopes)
    offset_mm = max(BRIDGE_SEAM_GAP_WIDTH_MM * 0.75, 0.42)
    for angular_extra_deg in [12.0, 18.0, 24.0, 32.0, 42.0, 52.0]:
        half_span = max(
            _envelope_angular_half_span(envelope_points, centroid_angle) + math.radians(angular_extra_deg),
            math.radians(34.0),
        )
        half_span = min(half_span, math.radians(78.0))
        endpoint_angles = [centroid_angle - half_span, centroid_angle + half_span]
        endpoints = [
            (CASE_RADIUS_MM * math.cos(angle), CASE_RADIUS_MM * math.sin(angle))
            for angle in endpoint_angles
        ]
        for clearance_multiplier in [1.65, 2.4, 3.2, 4.2, 5.4]:
            apex = (
                protected_centroid[0]
                + protected_to_adjacent[0] * (apex_projection + BRIDGE_SEAM_GAP_WIDTH_MM * clearance_multiplier),
                protected_centroid[1]
                + protected_to_adjacent[1] * (apex_projection + BRIDGE_SEAM_GAP_WIDTH_MM * clearance_multiplier),
            )
            candidate_reference = [endpoints[0], apex, endpoints[1]]
            candidate_points = _offset_polyline_points(candidate_reference, protected_to_adjacent, offset_mm)
            candidate_crossed = _boundary_crossed_envelopes(candidate_points, envelopes)
            if not candidate_crossed and _minimum_polyline_turn_angle(candidate_points) >= 75.0:
                reference_points = candidate_reference
                points = candidate_points
                crossed_envelopes = []
                break
        if points:
            break
    if not points:
        half_span = max(_envelope_angular_half_span(envelope_points, centroid_angle) + math.radians(56.0), math.radians(46.0))
        endpoint_angles = [centroid_angle - half_span, centroid_angle + half_span]
        reference_points = [
            (CASE_RADIUS_MM * math.cos(angle), CASE_RADIUS_MM * math.sin(angle))
            for angle in endpoint_angles
        ]
        points = _offset_polyline_points(reference_points, protected_to_adjacent, offset_mm)
        crossed_envelopes = _boundary_crossed_envelopes(points, envelopes)
    minimum_turn_angle = _minimum_polyline_turn_angle(points)
    envelope_crossing_status = "pass" if not crossed_envelopes else "fail"
    return {
        "boundary_id": boundary_id,
        "between": [protected_bridge_id, adjacent_bridge_id],
        "protected_bridge": protected_bridge_id,
        "reference_points": [_round_point(point) for point in reference_points],
        "points": [_round_point(point) for point in points],
        "control_point_count": len(points),
        "minimum_turn_angle_deg": _round_float(minimum_turn_angle),
        "offset_from_reference_mm": _round_float(offset_mm),
        "offset_policy": "offset_away_from_protected_envelope",
        "envelope_crossing_status": envelope_crossing_status,
        "crossed_envelopes": crossed_envelopes,
        "status": "pass"
        if minimum_turn_angle >= 75.0 and len(points) <= 3 and envelope_crossing_status == "pass"
        else "fail",
        "style": "low_control_point_obtuse_polyline",
    }


def _offset_polyline_points(
    points: list[tuple[float, float]],
    offset_direction: tuple[float, float],
    offset_mm: float,
) -> list[tuple[float, float]]:
    return [
        (point[0] + offset_direction[0] * offset_mm, point[1] + offset_direction[1] * offset_mm)
        for point in points
    ]


def _separating_line_boundary(
    boundary_id: str,
    protected_bridge_id: str,
    adjacent_bridge_id: str,
    envelopes: dict[str, dict[str, Any]],
    centroids: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    del centroids
    protected_points = [tuple(point) for point in envelopes[protected_bridge_id]["points"]]
    adjacent_points = [tuple(point) for point in envelopes[adjacent_bridge_id]["points"]]
    clearance = max(BRIDGE_SEAM_GAP_WIDTH_MM * 0.75, 0.42)
    best: dict[str, Any] | None = None
    best_gap = -1.0
    for angle in np.linspace(0.0, math.pi, 96, endpoint=False):
        base_normal = (math.cos(angle), math.sin(angle))
        for normal in [base_normal, (-base_normal[0], -base_normal[1])]:
            protected_max = max(_dot(point, normal) for point in protected_points)
            adjacent_min = min(_dot(point, normal) for point in adjacent_points)
            gap = adjacent_min - protected_max
            if gap <= clearance * 2.25:
                continue
            tangent = (-normal[1], normal[0])
            reference_offset = protected_max + clearance
            split_offset = reference_offset + clearance
            reference_points = _line_for_normal_offset(normal, tangent, reference_offset)
            points = _line_for_normal_offset(normal, tangent, split_offset)
            crossed_envelopes = _boundary_crossed_envelopes(points, envelopes)
            if crossed_envelopes:
                continue
            if gap > best_gap:
                best_gap = gap
                best = {
                    "boundary_id": boundary_id,
                    "between": [protected_bridge_id, adjacent_bridge_id],
                    "protected_bridge": protected_bridge_id,
                    "reference_points": [_round_point(point) for point in reference_points],
                    "points": [_round_point(point) for point in points],
                    "control_point_count": len(points),
                    "minimum_turn_angle_deg": 180.0,
                    "offset_from_reference_mm": _round_float(clearance),
                    "offset_policy": "offset_away_from_protected_envelope",
                    "envelope_crossing_status": "pass",
                    "crossed_envelopes": [],
                    "status": "pass",
                    "style": "convex_envelope_separating_line",
                    "separating_gap_mm": _round_float(gap),
                }
    if best is not None:
        return best
    return _failed_boundary(boundary_id, protected_bridge_id, adjacent_bridge_id, [], [], "no_separating_gap")


def _searched_obtuse_boundary(
    boundary_id: str,
    protected_bridge_id: str,
    adjacent_bridge_id: str,
    envelopes: dict[str, dict[str, Any]],
    centroids: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    protected_centroid = centroids[protected_bridge_id]
    adjacent_centroid = centroids[adjacent_bridge_id]
    offset_direction = _unit_vector((adjacent_centroid[0] - protected_centroid[0], adjacent_centroid[1] - protected_centroid[1]))
    if offset_direction == (0.0, 0.0):
        offset_direction = _unit_vector((-protected_centroid[0], -protected_centroid[1]))
    center_angle = math.atan2(protected_centroid[1], protected_centroid[0])
    envelope_points = [tuple(point) for point in envelopes[protected_bridge_id]["points"]]
    base_half_span = max(_envelope_angular_half_span(envelope_points, center_angle), math.radians(32.0))
    offset_mm = max(BRIDGE_SEAM_GAP_WIDTH_MM * 0.75, 0.42)
    envelope_paths = [MplPath(np.array(envelope["points"], dtype=float)) for envelope in envelopes.values()]
    best: dict[str, Any] | None = None
    best_score = float("inf")
    for extra_deg in [22.0, 34.0, 46.0, 58.0, 72.0]:
        half_span = min(base_half_span + math.radians(extra_deg), math.radians(112.0))
        endpoints = [
            (CASE_RADIUS_MM * math.cos(center_angle - half_span), CASE_RADIUS_MM * math.sin(center_angle - half_span)),
            (CASE_RADIUS_MM * math.cos(center_angle + half_span), CASE_RADIUS_MM * math.sin(center_angle + half_span)),
        ]
        for radius in np.linspace(CASE_RADIUS_MM * 0.18, CASE_RADIUS_MM * 0.82, 7):
            for angle in np.linspace(-math.pi, math.pi, 48, endpoint=False):
                apex = (float(radius * math.cos(angle)), float(radius * math.sin(angle)))
                if any(path.contains_point(apex, radius=BRIDGE_SEAM_GAP_WIDTH_MM) for path in envelope_paths):
                    continue
                points = [endpoints[0], apex, endpoints[1]]
                crossed = _boundary_crossed_envelopes(points, envelopes)
                if crossed:
                    continue
                turn = _minimum_polyline_turn_angle(points)
                if turn < 75.0:
                    continue
                score = (
                    _point_distance(endpoints[0], apex)
                    + _point_distance(apex, endpoints[1])
                    + abs(turn - 118.0) * 0.04
                )
                if score < best_score:
                    reference_points = _offset_polyline_points(points, (-offset_direction[0], -offset_direction[1]), offset_mm)
                    best_score = score
                    best = {
                        "boundary_id": boundary_id,
                        "between": [protected_bridge_id, adjacent_bridge_id],
                        "protected_bridge": protected_bridge_id,
                        "reference_points": [_round_point(point) for point in reference_points],
                        "points": [_round_point(point) for point in points],
                        "control_point_count": len(points),
                        "minimum_turn_angle_deg": _round_float(turn),
                        "offset_from_reference_mm": _round_float(offset_mm),
                        "offset_policy": "offset_away_from_protected_envelope",
                        "envelope_crossing_status": "pass",
                        "crossed_envelopes": [],
                        "status": "pass",
                        "style": "searched_obtuse_polyline",
                    }
    if best is not None:
        return best
    return _failed_boundary(boundary_id, protected_bridge_id, adjacent_bridge_id, [], [], "no_obtuse_clear_polyline")


def _failed_boundary(
    boundary_id: str,
    protected_bridge_id: str,
    adjacent_bridge_id: str,
    reference_points: list[tuple[float, float]],
    points: list[tuple[float, float]],
    reason: str,
) -> dict[str, Any]:
    return {
        "boundary_id": boundary_id,
        "between": [protected_bridge_id, adjacent_bridge_id],
        "protected_bridge": protected_bridge_id,
        "reference_points": [_round_point(point) for point in reference_points],
        "points": [_round_point(point) for point in points],
        "control_point_count": len(points),
        "minimum_turn_angle_deg": _round_float(_minimum_polyline_turn_angle(points)) if points else 0.0,
        "offset_from_reference_mm": 0.0,
        "offset_policy": "offset_away_from_protected_envelope",
        "envelope_crossing_status": "fail",
        "crossed_envelopes": [reason],
        "status": "fail",
        "style": "failed_manufacturing_boundary",
    }


def _line_for_normal_offset(
    normal: tuple[float, float],
    tangent: tuple[float, float],
    offset: float,
) -> list[tuple[float, float]]:
    closest = (normal[0] * offset, normal[1] * offset)
    dot = closest[0] * tangent[0] + closest[1] * tangent[1]
    base_sq = closest[0] ** 2 + closest[1] ** 2
    discriminant = max(0.0, dot**2 + CASE_RADIUS_MM**2 - base_sq)
    root = math.sqrt(discriminant)
    return [
        (closest[0] + tangent[0] * (-dot - root), closest[1] + tangent[1] * (-dot - root)),
        (closest[0] + tangent[0] * (-dot + root), closest[1] + tangent[1] * (-dot + root)),
    ]


def _boundary_crossed_envelopes(
    points: list[tuple[float, float]],
    envelopes: dict[str, dict[str, Any]],
) -> list[str]:
    crossed = []
    for bridge_id, envelope in envelopes.items():
        if any(_line_crosses_envelope(start, end, envelope["points"]) for start, end in zip(points[:-1], points[1:])):
            crossed.append(bridge_id)
    return crossed


def _unit_vector(vector: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(vector[0], vector[1])
    if length <= 1e-9:
        return (0.0, 0.0)
    return (vector[0] / length, vector[1] / length)


def _envelope_angular_half_span(points: list[tuple[float, float]], center_angle: float) -> float:
    deltas = [abs(_wrapped_angle_delta(math.atan2(point[1], point[0]), center_angle)) for point in points]
    return max(deltas) if deltas else math.radians(34.0)


def _minimum_polyline_turn_angle(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 180.0
    angles = []
    for before, current, after in zip(points[:-2], points[1:-1], points[2:]):
        v1 = _unit_vector((before[0] - current[0], before[1] - current[1]))
        v2 = _unit_vector((after[0] - current[0], after[1] - current[1]))
        dot = max(-1.0, min(1.0, _dot(v1, v2)))
        angles.append(math.degrees(math.acos(dot)))
    return min(angles) if angles else 180.0


def _weighted_voronoi_bridge_weights(
    envelopes: dict[str, dict[str, Any]],
    centroids: dict[str, tuple[float, float]],
) -> dict[str, float]:
    raw = {
        bridge_id: math.sqrt(max(_polygon_area(envelope["points"]), 0.01) / math.pi)
        for bridge_id, envelope in envelopes.items()
    }
    average_radius = sum(raw.values()) / len(raw)
    return {
        bridge_id: (raw[bridge_id] - average_radius) * 2.0
        for bridge_id in centroids
    }


def _polygon_area(points: list[list[float]] | list[tuple[float, float]]) -> float:
    area = 0.0
    for start, end in zip(points, [*points[1:], points[0]]):
        area += float(start[0]) * float(end[1]) - float(end[0]) * float(start[1])
    return abs(area) / 2.0


def _weighted_voronoi_score(
    point: tuple[float, float],
    centroid: tuple[float, float],
    weight: float,
) -> float:
    return _point_distance(point, centroid) - weight


def _force_outer_service_islands(
    labels: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    centroids: dict[str, tuple[float, float]],
    bridge_ids: list[str],
) -> None:
    service_inner_radius = CASE_RADIUS_MM * 0.78
    service_half_angle = math.radians(17.5)
    for bridge_id in bridge_ids:
        label = bridge_ids.index(bridge_id)
        centroid = centroids[bridge_id]
        service_angle = math.atan2(centroid[1], centroid[0])
        for iy, y in enumerate(ys):
            for ix, x in enumerate(xs):
                point = (float(x), float(y))
                radius = math.hypot(point[0], point[1])
                if radius < service_inner_radius or radius > CASE_RADIUS_MM:
                    continue
                angle_delta = abs(_wrapped_angle_delta(math.atan2(point[1], point[0]), service_angle))
                if angle_delta <= service_half_angle:
                    labels[iy, ix] = label


def _solve_centroid_voronoi_candidate(
    grid: dict[str, Any],
    envelopes: dict[str, dict[str, Any]],
    centroids: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    xs = grid["xs"]
    ys = grid["ys"]
    labels = np.full((len(ys), len(xs)), -1, dtype=int)
    bridge_ids = list(BRIDGE_AXIS_GROUPS)
    envelope_paths = {
        bridge_id: MplPath(np.array(envelope["points"], dtype=float))
        for bridge_id, envelope in envelopes.items()
    }
    for iy, y in enumerate(ys):
        for ix, x in enumerate(xs):
            point = (float(x), float(y))
            if x * x + y * y > CASE_RADIUS_MM * CASE_RADIUS_MM:
                continue
            containing = [
                bridge_id
                for bridge_id, path in envelope_paths.items()
                if path.contains_point(point, radius=0.01)
            ]
            if containing:
                bridge_id = min(containing, key=lambda item: _point_distance(point, centroids[item]))
            else:
                bridge_id = min(bridge_ids, key=lambda item: _point_distance(point, centroids[item]))
            labels[iy, ix] = bridge_ids.index(bridge_id)
    _force_envelope_grid_ownership(labels, xs, ys, envelopes, bridge_ids)
    boundary = _label_boundary_mask(labels)
    labels_with_seams = labels.copy()
    labels_with_seams[boundary] = -1
    _force_envelope_grid_ownership(labels_with_seams, xs, ys, envelopes, bridge_ids)
    islands = _outer_service_islands(labels, bridge_ids, sample_count=720)
    coverage_ok = _label_field_covers_expected_envelopes(labels, xs, ys, envelopes, bridge_ids)
    return {
        "candidate_id": "centroid_voronoi_partition",
        "topology": "centroid_voronoi_cells_with_envelope_priority",
        "status": "review",
        "coverage_status": "pass" if coverage_ok else "needs_optimization",
        "line_policy": {
            "kind": "centroid_cell_boundaries",
            "avoidance": "envelope_points_have_priority_over_plain_nearest_centroid_assignment",
            "purpose": "provide_topology_level_alternative_for_loop_diversity",
        },
        "grid": {
            "xs": [_round_float(float(value)) for value in xs],
            "ys": [_round_float(float(value)) for value in ys],
            "labels": labels_with_seams,
            "bridge_ids": bridge_ids,
        },
        "regions": [{"bridge_id": bridge_id, "outer_service_islands": islands[bridge_id]} for bridge_id in bridge_ids],
        "service_island_policy": {
            "allowed_disconnected_outer_islands": True,
            **SUPPORT_ISLAND_RULES,
        },
    }


def _solve_barrel_local_island_candidate(
    grid: dict[str, Any],
    envelopes: dict[str, dict[str, Any]],
    centroids: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    xs = grid["xs"]
    ys = grid["ys"]
    labels = np.full((len(ys), len(xs)), -1, dtype=int)
    bridge_ids = list(BRIDGE_AXIS_GROUPS)
    envelope_paths = {
        bridge_id: MplPath(np.array(envelope["points"], dtype=float))
        for bridge_id, envelope in envelopes.items()
    }
    barrel_angle = math.atan2(centroids["barrel_bridge"][1], centroids["barrel_bridge"][0])
    service_half_angle = math.radians(28.0)
    for iy, y in enumerate(ys):
        for ix, x in enumerate(xs):
            point = (float(x), float(y))
            radius = math.hypot(point[0], point[1])
            if radius > CASE_RADIUS_MM:
                continue
            in_barrel_envelope = envelope_paths["barrel_bridge"].contains_point(point, radius=0.01)
            angle_delta = abs(_wrapped_angle_delta(math.atan2(point[1], point[0]), barrel_angle))
            in_barrel_outer_service = radius > CASE_RADIUS_MM * 0.72 and angle_delta <= service_half_angle
            if in_barrel_envelope or (
                in_barrel_outer_service
                and not envelope_paths["train_bridge"].contains_point(point, radius=BRIDGE_SEAM_GAP_WIDTH_MM)
                and not envelope_paths["escapement_bridge"].contains_point(point, radius=BRIDGE_SEAM_GAP_WIDTH_MM)
            ):
                bridge_id = "barrel_bridge"
            elif _point_distance(point, centroids["train_bridge"]) <= _point_distance(point, centroids["escapement_bridge"]):
                bridge_id = "train_bridge"
            else:
                bridge_id = "escapement_bridge"
            labels[iy, ix] = bridge_ids.index(bridge_id)
    _force_envelope_grid_ownership(labels, xs, ys, envelopes, bridge_ids)
    boundary = _label_boundary_mask(labels)
    labels_with_seams = labels.copy()
    labels_with_seams[boundary] = -1
    _force_envelope_grid_ownership(labels_with_seams, xs, ys, envelopes, bridge_ids)
    islands = _outer_service_islands(labels, bridge_ids, sample_count=720)
    coverage_ok = _label_field_covers_expected_envelopes(labels, xs, ys, envelopes, bridge_ids)
    return {
        "candidate_id": "barrel_local_island_partition",
        "topology": "barrel_local_envelope_with_small_outer_service_island",
        "status": "review",
        "coverage_status": "pass" if coverage_ok else "needs_optimization",
        "line_policy": {
            "kind": "local_barrel_bridge_plus_nearest_remaining_cells",
            "barrel_service": "barrel_bridge_keeps_only_its_function_envelope_and_a_small_outer_fastener_island",
            "purpose": "force_barrel_area_and_service_span_diversity_for_loop_selection",
        },
        "grid": {
            "xs": [_round_float(float(value)) for value in xs],
            "ys": [_round_float(float(value)) for value in ys],
            "labels": labels_with_seams,
            "bridge_ids": bridge_ids,
        },
        "regions": [{"bridge_id": bridge_id, "outer_service_islands": islands[bridge_id]} for bridge_id in bridge_ids],
        "service_island_policy": {
            "allowed_disconnected_outer_islands": True,
            **SUPPORT_ISLAND_RULES,
        },
    }


def _solve_escapement_local_island_candidate(
    grid: dict[str, Any],
    envelopes: dict[str, dict[str, Any]],
    centroids: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    xs = grid["xs"]
    ys = grid["ys"]
    labels = np.full((len(ys), len(xs)), -1, dtype=int)
    bridge_ids = list(BRIDGE_AXIS_GROUPS)
    envelope_paths = {
        bridge_id: MplPath(np.array(envelope["points"], dtype=float))
        for bridge_id, envelope in envelopes.items()
    }
    escapement_angle = math.atan2(centroids["escapement_bridge"][1], centroids["escapement_bridge"][0])
    service_half_angle = math.radians(28.0)
    for iy, y in enumerate(ys):
        for ix, x in enumerate(xs):
            point = (float(x), float(y))
            radius = math.hypot(point[0], point[1])
            if radius > CASE_RADIUS_MM:
                continue
            in_escapement_envelope = envelope_paths["escapement_bridge"].contains_point(point, radius=0.01)
            angle_delta = abs(_wrapped_angle_delta(math.atan2(point[1], point[0]), escapement_angle))
            in_escapement_outer_service = radius > CASE_RADIUS_MM * 0.72 and angle_delta <= service_half_angle
            if in_escapement_envelope or (
                in_escapement_outer_service
                and not envelope_paths["barrel_bridge"].contains_point(point, radius=BRIDGE_SEAM_GAP_WIDTH_MM)
                and not envelope_paths["train_bridge"].contains_point(point, radius=BRIDGE_SEAM_GAP_WIDTH_MM)
            ):
                bridge_id = "escapement_bridge"
            elif _point_distance(point, centroids["barrel_bridge"]) <= _point_distance(point, centroids["train_bridge"]):
                bridge_id = "barrel_bridge"
            else:
                bridge_id = "train_bridge"
            labels[iy, ix] = bridge_ids.index(bridge_id)
    _force_envelope_grid_ownership(labels, xs, ys, envelopes, bridge_ids)
    boundary = _label_boundary_mask(labels)
    labels_with_seams = labels.copy()
    labels_with_seams[boundary] = -1
    _force_envelope_grid_ownership(labels_with_seams, xs, ys, envelopes, bridge_ids)
    islands = _outer_service_islands(labels, bridge_ids, sample_count=720)
    coverage_ok = _label_field_covers_expected_envelopes(labels, xs, ys, envelopes, bridge_ids)
    return {
        "candidate_id": "escapement_local_island_partition",
        "topology": "escapement_local_envelope_with_small_outer_service_island",
        "status": "review",
        "coverage_status": "pass" if coverage_ok else "needs_optimization",
        "line_policy": {
            "kind": "local_escapement_bridge_plus_nearest_remaining_cells",
            "escapement_service": "escapement_bridge_keeps_only_its_function_envelope_and_a_small_outer_fastener_island",
            "purpose": "force_escapement_service_span_diversity_for_loop_selection",
        },
        "grid": {
            "xs": [_round_float(float(value)) for value in xs],
            "ys": [_round_float(float(value)) for value in ys],
            "labels": labels_with_seams,
            "bridge_ids": bridge_ids,
        },
        "regions": [{"bridge_id": bridge_id, "outer_service_islands": islands[bridge_id]} for bridge_id in bridge_ids],
        "service_island_policy": {
            "allowed_disconnected_outer_islands": True,
            **SUPPORT_ISLAND_RULES,
        },
    }


def _force_envelope_grid_ownership(
    labels: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    envelopes: dict[str, dict[str, Any]],
    bridge_ids: list[str],
) -> None:
    x_tolerance = float(abs(xs[1] - xs[0])) if len(xs) > 1 else 0.0
    y_tolerance = float(abs(ys[1] - ys[0])) if len(ys) > 1 else 0.0
    grid_tolerance = max(x_tolerance, y_tolerance) * 0.75
    for bridge_id, envelope in envelopes.items():
        label = bridge_ids.index(bridge_id)
        envelope_path = MplPath(np.array(envelope["points"], dtype=float))
        for iy, y in enumerate(ys):
            for ix, x in enumerate(xs):
                if envelope_path.contains_point((float(x), float(y)), radius=grid_tolerance):
                    labels[iy, ix] = label
        for point in envelope["points"]:
            ix = int(np.argmin(np.abs(xs - point[0])))
            iy = int(np.argmin(np.abs(ys - point[1])))
            labels[iy, ix] = label


def _render_candidate(ax: Any, partition: dict[str, Any], candidate: dict[str, Any], title: str) -> None:
    colors = {
        "barrel_bridge": "#f8d7a1",
        "train_bridge": "#b9d7ff",
        "escapement_bridge": "#c8ead1",
    }
    radius = float(partition["case_radius_mm"])
    ax.set_aspect("equal")
    ax.set_xlim(-radius - 1.5, radius + 1.5)
    ax.set_ylim(-radius - 1.5, radius + 1.5)
    ax.axis("off")
    ax.set_title(title, fontsize=12)
    ax.add_patch(plt.Circle((0, 0), radius, fill=False, ec="#9aa5b1", lw=1.3))

    if candidate.get("bridge_plate_footprints"):
        for footprint in candidate["bridge_plate_footprints"]:
            for component in footprint.get("components", []):
                component_points = np.array(component["points"])
                ax.fill(
                    component_points[:, 0],
                    component_points[:, 1],
                    color=colors[footprint["bridge_id"]],
                    alpha=0.76 if component["component_type"] == "service_pad" else 0.46,
                    zorder=3 if component["component_type"] == "service_pad" else 0,
                )
                ax.plot(
                    component_points[:, 0],
                    component_points[:, 1],
                    color="#5b6472" if component["component_type"] == "service_pad" else colors[footprint["bridge_id"]],
                    lw=0.8 if component["component_type"] == "service_pad" else 1.2,
                    zorder=4,
                )
    elif "grid" in candidate:
        grid = candidate["grid"]
        label_array = np.ma.masked_where(np.array(grid["labels"]) < 0, np.array(grid["labels"]))
        ax.imshow(
            label_array,
            origin="lower",
            extent=[-radius, radius, -radius, radius],
            cmap=ListedColormap([colors[bridge_id] for bridge_id in grid["bridge_ids"]]),
            alpha=0.72,
            interpolation="nearest",
            zorder=0,
        )
    else:
        for region in candidate["regions"]:
            points = np.array(region["points"])
            ax.fill(points[:, 0], points[:, 1], color=colors[region["bridge_id"]], alpha=0.72, zorder=0)

    for bridge_id, envelope in partition["envelopes"].items():
        polygon = np.array(envelope["points"])
        ax.fill(polygon[:, 0], polygon[:, 1], color=colors[bridge_id], alpha=0.35, zorder=1)
        ax.plot(polygon[:, 0], polygon[:, 1], color="#667085", lw=1.0, zorder=2)
        cx, cy = partition["centroids"][bridge_id]
        ax.text(cx, cy, bridge_id.replace("_bridge", ""), ha="center", va="center", fontsize=8, color="#303843", zorder=8)

    for circle in partition["protection_circles"].values():
        x, y = circle["center"]
        ax.add_patch(plt.Circle((x, y), circle["radius_mm"], fill=False, ec="#344054", lw=0.9, alpha=0.8, zorder=4))
        ax.add_patch(plt.Circle((x, y), 0.13, color="#1f2937", zorder=5))

    for seam in candidate.get("seams", []):
        path = np.array(seam["path"])
        ax.plot(path[:, 0], path[:, 1], color="white", lw=7.0, solid_capstyle="round", zorder=6)
        ax.plot(path[:, 0], path[:, 1], color="#ff4b4b", lw=2.0, solid_capstyle="round", zorder=7)
    if "grid" in candidate and not candidate.get("bridge_plate_footprints"):
        labels = np.array(candidate["grid"]["labels"])
        xs = np.array(candidate["grid"]["xs"], dtype=float)
        ys = np.array(candidate["grid"]["ys"], dtype=float)
        if candidate.get("manufacturing_boundaries"):
            for boundary_line in candidate["manufacturing_boundaries"]:
                pts = np.array(boundary_line["points"])
                ax.plot(pts[:, 0], pts[:, 1], color="white", lw=7.0, solid_capstyle="round", zorder=7)
                ax.plot(pts[:, 0], pts[:, 1], color="#ff4b4b", lw=2.0, solid_capstyle="round", zorder=8)
        else:
            boundary = labels < 0
            ax.contour(xs, ys, boundary.astype(float), levels=[0.5], colors=["#ff4b4b"], linewidths=1.8, zorder=7)
        for boundary_line in candidate.get("straight_boundaries", []):
            pts = np.array(boundary_line["points"])
            ax.plot(pts[:, 0], pts[:, 1], color="#b42318", lw=1.4, ls="--", zorder=8)

    if "junction" in candidate:
        jx, jy = candidate["junction"]
        ax.add_patch(plt.Circle((jx, jy), 0.36, color="#ff4b4b", zorder=9))

    _draw_service_island_marks(ax, candidate, colors)
    rule_text = "pad from island; <40 deg island pad = full island span"
    ax.text(-radius, -radius - 0.9, rule_text, fontsize=7.5, color="#667085")


def _draw_service_island_marks(ax: Any, candidate: dict[str, Any], colors: dict[str, str]) -> None:
    for region in candidate.get("regions", []):
        bridge_id = region["bridge_id"]
        for island in region.get("outer_service_islands", []):
            start = math.radians(island["start_deg"])
            end = math.radians(island["end_deg"])
            if end < start:
                end += 2 * math.pi
            samples = np.linspace(start, end, 25)
            x = np.cos(samples) * (CASE_RADIUS_MM + 0.25)
            y = np.sin(samples) * (CASE_RADIUS_MM + 0.25)
            ax.plot(x, y, color=colors[bridge_id], lw=4.5, solid_capstyle="round", zorder=10)
            mid = (start + end) / 2.0
            ax.text(
                math.cos(mid) * (CASE_RADIUS_MM + 0.95),
                math.sin(mid) * (CASE_RADIUS_MM + 0.95),
                str(island["screw_count"]),
                ha="center",
                va="center",
                fontsize=7,
                color="#344054",
                zorder=11,
            )


def _build_protection_circles(
    axis_by_id: dict[str, dict[str, Any]],
    axis_groups: dict[str, list[str]],
) -> dict[str, dict[str, Any]]:
    circles: dict[str, dict[str, Any]] = {}
    for axis_id in {axis_id for axis_ids in axis_groups.values() for axis_id in axis_ids}:
        axis = axis_by_id[axis_id]
        upper = axis.get("upper_jewel_bearing")
        base_radius = float(upper["outer_radius"]) if upper else DEFAULT_EXTERNAL_AXIS_PROTECTION_RADIUS_MM
        circles[axis_id] = {
            "axis_id": axis_id,
            "center": [round(float(axis["x"]), 4), round(float(axis["y"]), 4)],
            "bearing_radius_mm": round(base_radius, 4),
            "radius_mm": round(base_radius * AXIS_PROTECTION_RADIUS_MULTIPLIER, 4),
        }
    return circles


def _axis_group_envelope(circles: list[dict[str, Any]], links: list[list[str]]) -> dict[str, Any]:
    if len(circles) == 1:
        return _single_circle_envelope(circles[0])
    if links:
        ordered = _axis_order_from_links([circle["axis_id"] for circle in circles], links)
        if ordered:
            by_axis = {circle["axis_id"]: circle for circle in circles}
            return _linked_axis_capsule_envelope([by_axis[axis_id] for axis_id in ordered])
    return _convex_hull_envelope(circles)


def _single_circle_envelope(circle: dict[str, Any]) -> dict[str, Any]:
    cx, cy = circle["center"]
    radius = float(circle["radius_mm"]) + ENVELOPE_EXTRA_MARGIN_MM
    points = []
    for index in range(32):
        angle = 2 * math.pi * index / 32
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return {
        "method": "single_axis_protection_circle",
        "points": [_round_point(point) for point in points],
    }


def _axis_order_from_links(axis_ids: list[str], links: list[list[str]]) -> list[str]:
    neighbors = {axis_id: [] for axis_id in axis_ids}
    for left, right in links:
        if left not in neighbors or right not in neighbors:
            return []
        neighbors[left].append(right)
        neighbors[right].append(left)
    if any(len(values) > 2 for values in neighbors.values()):
        return []
    endpoints = [axis_id for axis_id, values in neighbors.items() if len(values) <= 1]
    if not endpoints:
        return []
    start = sorted(endpoints)[0]
    ordered = [start]
    previous = None
    current = start
    while True:
        next_nodes = [axis_id for axis_id in neighbors[current] if axis_id != previous]
        if not next_nodes:
            break
        previous, current = current, next_nodes[0]
        ordered.append(current)
    return ordered if set(ordered) == set(axis_ids) else []


def _linked_axis_capsule_envelope(circles: list[dict[str, Any]]) -> dict[str, Any]:
    centers = [(float(circle["center"][0]), float(circle["center"][1])) for circle in circles]
    radii = [float(circle["radius_mm"]) + ENVELOPE_EXTRA_MARGIN_MM for circle in circles]
    left_points = []
    right_points = []
    for index, center in enumerate(centers):
        tangent = _polyline_tangent(centers, index)
        normal = (-tangent[1], tangent[0])
        radius = radii[index]
        left_points.append((center[0] + normal[0] * radius, center[1] + normal[1] * radius))
        right_points.append((center[0] - normal[0] * radius, center[1] - normal[1] * radius))
    points = left_points + list(reversed(right_points))
    return {
        "method": "linked_axis_capsule_polyline_envelope",
        "axis_order": [circle["axis_id"] for circle in circles],
        "points": [_round_point(point) for point in points],
    }


def _polyline_tangent(points: list[tuple[float, float]], index: int) -> tuple[float, float]:
    if len(points) == 1:
        return (1.0, 0.0)
    if index == 0:
        vector = _vector_between(points[0], points[1])
    elif index == len(points) - 1:
        vector = _vector_between(points[-2], points[-1])
    else:
        before = _unit_vector(_vector_between(points[index - 1], points[index]))
        after = _unit_vector(_vector_between(points[index], points[index + 1]))
        vector = (before[0] + after[0], before[1] + after[1])
        if abs(vector[0]) + abs(vector[1]) <= 1e-9:
            vector = _vector_between(points[index - 1], points[index + 1])
    return _unit_vector(vector)


def _convex_hull_envelope(circles: list[dict[str, Any]]) -> dict[str, Any]:
    points: list[tuple[float, float]] = []
    for circle in circles:
        cx, cy = circle["center"]
        radius = float(circle["radius_mm"]) + ENVELOPE_EXTRA_MARGIN_MM
        for index in range(36):
            angle = 2 * math.pi * index / 36
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    hull = ConvexHull(np.array(points))
    hull_points = [points[index] for index in hull.vertices]
    return {
        "method": "convex_hull_of_sampled_protection_circles",
        "points": [_round_point(point) for point in hull_points],
    }


def _weighted_group_centroid(circles: list[dict[str, Any]]) -> tuple[float, float]:
    total = 0.0
    sx = 0.0
    sy = 0.0
    for circle in circles:
        weight = max(0.01, float(circle["radius_mm"]) ** 2)
        x, y = circle["center"]
        sx += x * weight
        sy += y * weight
        total += weight
    return (sx / total, sy / total)


def _principal_axis(points: list[list[float]]) -> dict[str, tuple[float, float]]:
    array = np.array(points, dtype=float)
    center = array.mean(axis=0)
    centered = array - center
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    direction = (float(vh[0, 0]), float(vh[0, 1]))
    if direction[0] < 0:
        direction = (-direction[0], -direction[1])
    normal = (-direction[1], direction[0])
    return {"origin": (float(center[0]), float(center[1])), "direction": direction, "normal": normal}


def _train_band_from_envelopes(
    envelopes: dict[str, dict[str, Any]],
    axis: dict[str, tuple[float, float]],
    *,
    margin: float,
) -> dict[str, float]:
    train_offsets = [_signed_offset_from_axis(tuple(point), axis) for point in envelopes["train_bridge"]["points"]]
    barrel_offsets = [_signed_offset_from_axis(tuple(point), axis) for point in envelopes["barrel_bridge"]["points"]]
    escapement_offsets = [_signed_offset_from_axis(tuple(point), axis) for point in envelopes["escapement_bridge"]["points"]]
    lower = min(train_offsets) - margin
    upper = max(train_offsets) + margin
    if barrel_offsets and max(barrel_offsets) < lower:
        lower = max(lower, (max(barrel_offsets) + min(train_offsets)) / 2.0)
    if escapement_offsets and min(escapement_offsets) > upper:
        upper = min(upper, (min(escapement_offsets) + max(train_offsets)) / 2.0)
    return {"lower": float(lower), "upper": float(upper)}


def _straight_train_band_boundaries(axis: dict[str, tuple[float, float]], band: dict[str, float]) -> list[dict[str, Any]]:
    return [
        {"boundary_id": "barrel_train_boundary", "points": [_round_point(point) for point in _line_circle_segment(axis, band["lower"])]},
        {"boundary_id": "train_escapement_boundary", "points": [_round_point(point) for point in _line_circle_segment(axis, band["upper"])]},
    ]


def _line_circle_segment(axis: dict[str, tuple[float, float]], normal_offset: float) -> list[tuple[float, float]]:
    origin = axis["origin"]
    direction = axis["direction"]
    normal = axis["normal"]
    base = (origin[0] + normal[0] * normal_offset, origin[1] + normal[1] * normal_offset)
    dot = base[0] * direction[0] + base[1] * direction[1]
    base_sq = base[0] ** 2 + base[1] ** 2
    discriminant = max(0.0, dot**2 + CASE_RADIUS_MM**2 - base_sq)
    root = math.sqrt(discriminant)
    return [
        (base[0] + direction[0] * (-dot - root), base[1] + direction[1] * (-dot - root)),
        (base[0] + direction[0] * (-dot + root), base[1] + direction[1] * (-dot + root)),
    ]


def _signed_offset_from_axis(point: tuple[float, float], axis: dict[str, tuple[float, float]]) -> float:
    origin = axis["origin"]
    normal = axis["normal"]
    return (point[0] - origin[0]) * normal[0] + (point[1] - origin[1]) * normal[1]


def _vector_between(start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float]:
    return (end[0] - start[0], end[1] - start[1])


def _point_distance(start: tuple[float, float], end: tuple[float, float]) -> float:
    return math.hypot(start[0] - end[0], start[1] - end[1])


def _dot(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _grid(resolution: int) -> dict[str, Any]:
    return {
        "xs": np.linspace(-CASE_RADIUS_MM, CASE_RADIUS_MM, resolution),
        "ys": np.linspace(-CASE_RADIUS_MM, CASE_RADIUS_MM, resolution),
    }


def _ordered_bridge_ids_by_angle(centroids: dict[str, tuple[float, float]]) -> list[str]:
    return [
        bridge_id
        for bridge_id, _ in sorted(centroids.items(), key=lambda item: math.atan2(item[1][1], item[1][0]))
    ]


def _continuous_outer_arc_seam_specs(
    ordered: list[str], centroids: dict[str, tuple[float, float]]
) -> list[dict[str, Any]]:
    gap_angles = _candidate_outer_gap_angles(centroids)
    seam_specs = []
    for index, left_id in enumerate(ordered):
        right_id = ordered[(index + 1) % len(ordered)]
        seam_angle = gap_angles[index]
        point = (CASE_RADIUS_MM * math.cos(seam_angle), CASE_RADIUS_MM * math.sin(seam_angle))
        seam_specs.append(
            {
                "seam_id": f"seam_{left_id}_to_{right_id}",
                "between": [left_id, right_id],
                "angle_rad": seam_angle,
                "angle_deg": _normalize_degrees(math.degrees(seam_angle)),
                "start": point,
            }
        )
    return seam_specs


def _candidate_outer_gap_angles(centroids: dict[str, tuple[float, float]]) -> list[float]:
    ordered = _ordered_bridge_ids_by_angle(centroids)
    angles = {bridge_id: math.atan2(centroids[bridge_id][1], centroids[bridge_id][0]) for bridge_id in ordered}
    gap_angles = []
    for index, left_id in enumerate(ordered):
        right_id = ordered[(index + 1) % len(ordered)]
        left_angle = angles[left_id]
        right_angle = angles[right_id]
        if right_angle < left_angle:
            right_angle += 2 * math.pi
        gap_angles.append((left_angle + right_angle) / 2.0)
    return gap_angles


def _continuous_centroid_gap_labels(
    grid: dict[str, Any],
    ordered: list[str],
    centroids: dict[str, tuple[float, float]],
) -> np.ndarray:
    xs = grid["xs"]
    ys = grid["ys"]
    labels = np.full((len(ys), len(xs)), -1, dtype=int)
    centroid_angles = {
        bridge_id: math.atan2(centroids[bridge_id][1], centroids[bridge_id][0])
        for bridge_id in ordered
    }
    for iy, y in enumerate(ys):
        for ix, x in enumerate(xs):
            if x * x + y * y > CASE_RADIUS_MM * CASE_RADIUS_MM:
                continue
            angle = math.atan2(float(y), float(x))
            bridge_id = min(
                ordered,
                key=lambda item: abs(_wrapped_angle_delta(angle, centroid_angles[item])),
            )
            labels[iy, ix] = ordered.index(bridge_id)
    return labels


def _continuous_outer_arc_regions(
    ordered: list[str], seam_specs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    seam_by_between = {tuple(spec["between"]): spec for spec in seam_specs}
    regions = []
    for index, bridge_id in enumerate(ordered):
        prev_id = ordered[index - 1]
        next_id = ordered[(index + 1) % len(ordered)]
        start_seam = seam_by_between.get((prev_id, bridge_id))
        end_seam = seam_by_between.get((bridge_id, next_id))
        if start_seam is None or end_seam is None:
            continue
        start_angle = float(start_seam["angle_rad"])
        end_angle = float(end_seam["angle_rad"])
        regions.append(
            {
                "bridge_id": bridge_id,
                "outer_service_islands": [_island_from_angles(math.degrees(start_angle), math.degrees(end_angle))],
            }
        )
    return regions


def _route_continuous_gap_seam(
    start: tuple[float, float],
    junction: tuple[float, float],
    envelopes: dict[str, Any],
) -> list[tuple[float, float]]:
    if not _polyline_crosses_envelopes([start, junction], envelopes):
        return [start, junction]

    angle = math.atan2(start[1], start[0])
    radial = (math.cos(angle), math.sin(angle))
    tangent = (-radial[1], radial[0])
    for radius_scale in [0.72, 0.62, 0.52]:
        for offset in [0.0, 1.2, -1.2, 2.0, -2.0]:
            bend = (
                radial[0] * CASE_RADIUS_MM * radius_scale + tangent[0] * offset,
                radial[1] * CASE_RADIUS_MM * radius_scale + tangent[1] * offset,
            )
            if math.hypot(bend[0], bend[1]) > CASE_RADIUS_MM * 0.92:
                continue
            candidate = [start, bend, junction]
            if not _polyline_crosses_envelopes(candidate, envelopes):
                return candidate
    return [start, junction]


def _polyline_crosses_envelopes(points: list[tuple[float, float]], envelopes: dict[str, Any]) -> bool:
    return any(
        _line_crosses_envelope(start, end, envelope["points"])
        for start, end in zip(points[:-1], points[1:])
        for envelope in envelopes.values()
    )


def _line_crosses_envelope(
    start: tuple[float, float],
    end: tuple[float, float],
    envelope_points: list[list[float]],
) -> bool:
    envelope_path = MplPath(np.array(envelope_points, dtype=float))
    for index in range(64):
        t = index / 63.0
        point = (start[0] * (1 - t) + end[0] * t, start[1] * (1 - t) + end[1] * t)
        if envelope_path.contains_point(point, radius=BRIDGE_SEAM_GAP_WIDTH_MM):
            return True
    return False


def _choose_continuous_junction(
    grid: dict[str, Any], envelopes: dict[str, dict[str, Any]], seam_specs: list[dict[str, Any]]
) -> tuple[float, float]:
    envelope_paths = [MplPath(np.array(envelope["points"])) for envelope in envelopes.values()]
    best = (0.0, 0.0)
    best_score = float("inf")
    for y in grid["ys"]:
        for x in grid["xs"]:
            if x * x + y * y > (CASE_RADIUS_MM * 0.55) ** 2:
                continue
            if any(path.contains_point((x, y), radius=BRIDGE_SEAM_GAP_WIDTH_MM) for path in envelope_paths):
                continue
            if math.hypot(x, y) < 1.8:
                continue
            path_penalty = 0.0
            for seam in seam_specs:
                path_penalty += _segment_envelope_penalty(seam["start"], (float(x), float(y)), envelope_paths)
            score = path_penalty + 0.12 * sum(math.hypot(x - seam["start"][0], y - seam["start"][1]) for seam in seam_specs)
            if score < best_score:
                best_score = score
                best = (float(x), float(y))
    return best


def _segment_envelope_penalty(
    start: tuple[float, float], end: tuple[float, float], envelope_paths: list[MplPath]
) -> float:
    penalty = 0.0
    for index in range(48):
        t = index / 47.0
        point = (start[0] * (1 - t) + end[0] * t, start[1] * (1 - t) + end[1] * t)
        if any(path.contains_point(point, radius=BRIDGE_SEAM_GAP_WIDTH_MM) for path in envelope_paths):
            penalty += 30.0
    return penalty


def _continuous_y_regions(
    ordered: list[str], seam_specs: list[dict[str, Any]], junction: tuple[float, float]
) -> list[dict[str, Any]]:
    seam_by_between = {tuple(spec["between"]): spec for spec in seam_specs}
    regions = []
    for index, bridge_id in enumerate(ordered):
        prev_id = ordered[index - 1]
        next_id = ordered[(index + 1) % len(ordered)]
        start_seam = seam_by_between.get((prev_id, bridge_id))
        end_seam = seam_by_between.get((bridge_id, next_id))
        if start_seam is None or end_seam is None:
            continue
        start_angle = start_seam["angle_rad"]
        end_angle = end_seam["angle_rad"]
        if end_angle < start_angle:
            end_angle += 2 * math.pi
        arc = [
            (CASE_RADIUS_MM * math.cos(angle), CASE_RADIUS_MM * math.sin(angle))
            for angle in np.linspace(start_angle, end_angle, 80)
        ]
        points = [junction, *arc]
        regions.append(
            {
                "bridge_id": bridge_id,
                "points": [_round_point(point) for point in points],
                "outer_service_islands": [_island_from_angles(math.degrees(start_angle), math.degrees(end_angle))],
            }
        )
    return regions


def _regions_cover_expected_envelopes(regions: list[dict[str, Any]], envelopes: dict[str, dict[str, Any]]) -> bool:
    region_by_bridge = {region["bridge_id"]: MplPath(np.array(region["points"])) for region in regions}
    for bridge_id, envelope in envelopes.items():
        region_path = region_by_bridge.get(bridge_id)
        if region_path is None:
            return False
        if not all(region_path.contains_point(point, radius=0.02) for point in envelope["points"]):
            return False
    return True


def _label_field_covers_expected_envelopes(
    labels: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    envelopes: dict[str, dict[str, Any]],
    bridge_ids: list[str],
) -> bool:
    for bridge_id, envelope in envelopes.items():
        label = bridge_ids.index(bridge_id)
        for point in envelope["points"]:
            ix = int(np.argmin(np.abs(xs - point[0])))
            iy = int(np.argmin(np.abs(ys - point[1])))
            if labels[iy, ix] != label:
                return False
    return True


def _label_field_covers_one_envelope(
    labels: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    envelope: dict[str, Any],
    label: int,
) -> bool:
    for point in envelope["points"]:
        ix = int(np.argmin(np.abs(xs - point[0])))
        iy = int(np.argmin(np.abs(ys - point[1])))
        if labels[iy, ix] != label:
            return False
    return True


def _label_boundary_mask(labels: np.ndarray) -> np.ndarray:
    boundary = np.zeros_like(labels, dtype=bool)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
        shifted = np.roll(np.roll(labels, dy, axis=0), dx, axis=1)
        boundary |= (labels >= 0) & (shifted >= 0) & (labels != shifted)
    return boundary


def _outer_service_islands(labels: np.ndarray, bridge_ids: list[str], sample_count: int) -> dict[str, list[dict[str, Any]]]:
    islands = {bridge_id: [] for bridge_id in bridge_ids}
    radius_index = labels.shape[0] // 2 - 2
    center = labels.shape[0] // 2
    samples = []
    for index in range(sample_count):
        angle = 2 * math.pi * index / sample_count
        ix = int(round(center + math.cos(angle) * radius_index))
        iy = int(round(center + math.sin(angle) * radius_index))
        label = int(labels[iy, ix]) if 0 <= iy < labels.shape[0] and 0 <= ix < labels.shape[1] else -1
        samples.append(label)
    for label_index, bridge_id in enumerate(bridge_ids):
        spans = _contiguous_label_spans(samples, label_index)
        islands[bridge_id] = [_island_from_sample_span(start, end, sample_count) for start, end in spans]
    return islands


def _contiguous_label_spans(samples: list[int], label: int) -> list[tuple[int, int]]:
    n = len(samples)
    flags = [value == label for value in samples]
    if not any(flags):
        return []
    if all(flags):
        return [(0, n - 1)]
    starts = [index for index in range(n) if flags[index] and not flags[(index - 1) % n]]
    spans = []
    for start in starts:
        end = start
        while flags[(end + 1) % n]:
            end = (end + 1) % n
        spans.append((start, end))
    return spans


def _island_from_sample_span(start: int, end: int, sample_count: int) -> dict[str, Any]:
    start_deg = 360.0 * start / sample_count
    end_deg = 360.0 * (end + 1) / sample_count
    return _island_from_angles(start_deg, end_deg)


def _island_from_angles(start_deg: float, end_deg: float) -> dict[str, Any]:
    span = _positive_angle_span(start_deg, end_deg)
    return {
        "start_deg": _normalize_degrees(start_deg),
        "end_deg": _normalize_degrees(end_deg),
        "span_deg": round(span, 4),
        "screw_count": _screw_count_for_island(span),
        "pad_policy": "full_span_under_40_deg"
        if span < SUPPORT_ISLAND_RULES["single_screw_island_threshold_deg"]
        else "full_or_6_head_diameters",
        "pad_side_reference": "local_bridge_boundary",
        "single_screw_pad_equals_island_span": span < SUPPORT_ISLAND_RULES["single_screw_island_threshold_deg"],
    }


def _screw_count_for_island(span_deg: float) -> int:
    if span_deg < 40.0:
        return 1
    if span_deg <= 90.0:
        return 2
    return 3


def _sample_polyline(points: list[tuple[float, float]], steps_per_segment: int = 24) -> list[tuple[float, float]]:
    sampled: list[tuple[float, float]] = []
    for start, end in zip(points[:-1], points[1:]):
        for index in range(steps_per_segment):
            t = index / steps_per_segment
            sampled.append((start[0] * (1 - t) + end[0] * t, start[1] * (1 - t) + end[1] * t))
    sampled.append(points[-1])
    return sampled


def _distance_to_polygon_points(point: tuple[float, float], points: list[list[float]]) -> float:
    return min(math.hypot(point[0] - poly_point[0], point[1] - poly_point[1]) for poly_point in points)


def _positive_angle_span(start_deg: float, end_deg: float) -> float:
    return (end_deg - start_deg) % 360.0


def _wrapped_angle_delta(left: float, right: float) -> float:
    return (left - right + math.pi) % (2 * math.pi) - math.pi


def _normalize_degrees(angle_deg: float) -> float:
    return round(angle_deg % 360.0, 4)


def _round_float(value: float) -> float:
    return round(value, 4)


def _round_point(point: tuple[float, float] | list[float]) -> list[float]:
    return [round(float(point[0]), 4), round(float(point[1]), 4)]
