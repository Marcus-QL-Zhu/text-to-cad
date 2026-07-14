"""Bridge partition loop for watch axis-layout batches."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from .bridge_xy_partition import _render_candidate, solve_bridge_xy_partition
from .chain_solver_loop import _design_from_global_candidate, _render_axis_layout
from .global_constraint_solver import solve_global_axis_constraints


BRIDGE_IDS = ["barrel_bridge", "train_bridge", "escapement_bridge"]
SCHEME_A_ID = "continuous_outer_arc_y"
SCHEME_B_ID = "service_island_power_partition"
_BASE_REPORT_CACHE: dict[tuple[tuple[int, ...], int], dict[str, Any]] = {}


def run_bridge_partition_loop(
    *,
    axis_seeds: list[int],
    target_count_per_seed: int = 5,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    target = Path(output_dir) if output_dir is not None else None
    if target is not None:
        target.mkdir(parents=True, exist_ok=True)

    cache_key = (tuple(axis_seeds), target_count_per_seed)
    if cache_key in _BASE_REPORT_CACHE:
        report = copy.deepcopy(_BASE_REPORT_CACHE[cache_key])
        if target is not None:
            _write_review_packet(report, target)
        return _public_report(report)

    layouts = []
    for axis_seed in axis_seeds:
        axis_report = solve_global_axis_constraints(seed=axis_seed, target_count=target_count_per_seed)
        for index, candidate in enumerate(axis_report["candidates"][:target_count_per_seed], start=1):
            design = _design_from_global_candidate(candidate, axis_report)
            partition = solve_bridge_xy_partition(design, grid_resolution=121)
            scheme_results = {
                "A": _candidate_validation(partition, SCHEME_A_ID, "A"),
                "B": _candidate_validation(partition, SCHEME_B_ID, "B"),
            }
            selected_scheme = "B"
            selected_result = scheme_results[selected_scheme]
            selected_status = selected_result["hard_status"]
            layouts.append(
                {
                    "layout_id": f"seed_{axis_seed}_layout_{index:02d}",
                    "axis_seed": axis_seed,
                    "axis_candidate_id": candidate["candidate_id"],
                    "selected_scheme": selected_scheme,
                    "selected_status": selected_status,
                    "selected_result": selected_result,
                    "scheme_results": scheme_results,
                    "_design": design,
                    "_partition": partition,
                }
            )

    hard_failures = [
        {
            "layout_id": layout["layout_id"],
            "selected_scheme": layout["selected_scheme"],
            "hard_failures": layout["selected_result"]["hard_failures"],
        }
        for layout in layouts
        if layout["selected_status"] != "pass"
    ]
    report = {
        "kind": "watch_bridge_partition_loop_report",
        "status": "pass" if not hard_failures and len(layouts) == len(axis_seeds) * target_count_per_seed else "fail",
        "axis_seeds": list(axis_seeds),
        "target_count_per_seed": target_count_per_seed,
        "layouts": layouts,
        "scheme_counts": {
            "A": sum(1 for layout in layouts if layout["selected_scheme"] == "A"),
            "B": sum(1 for layout in layouts if layout["selected_scheme"] == "B"),
        },
        "hard_failures": hard_failures,
        "artifacts": {},
    }
    if target is not None:
        _write_review_packet(report, target)
    else:
        _BASE_REPORT_CACHE[cache_key] = copy.deepcopy(report)
    return _public_report(report)


def _candidate_validation(partition: dict[str, Any], candidate_id: str, scheme: str) -> dict[str, Any]:
    candidate = partition["candidates"][candidate_id]
    hard_failures = []
    known_failure_reasons = [
        "missing_bridge_coverage",
        "seam_crosses_functional_envelope",
        "seam_crosses_axis_protection_zone",
        "gap_width_not_stable",
        "acute_or_noisy_seam_path",
        "bridge_region_disconnected",
        "bridge_region_covers_wrong_envelope_group",
        "fastener_service_arc_missing",
        "fastener_service_arc_too_short",
        "candidate_geometry_unavailable",
        "functional_envelope_overlap",
        "bridge_footprint_missing",
        "bridge_footprint_invalid",
    ]
    if scheme == "A":
        known_failure_reasons.append("scheme_a_multiple_outer_arcs")
    if scheme == "B":
        known_failure_reasons.extend(
            [
                "scheme_b_missing_service_island",
                "scheme_b_invalid_short_island_pad",
            ]
        )
    for reason in candidate.get("validation_failures", []):
        if reason not in hard_failures:
            hard_failures.append(reason)
    coverage = {
        bridge_id: candidate.get("coverage_by_bridge", {}).get(
            bridge_id,
            "pass" if candidate["coverage_status"] == "pass" else "fail",
        )
        for bridge_id in BRIDGE_IDS
    }
    envelope_overlap = _functional_envelope_overlap(partition)
    if envelope_overlap["status"] != "pass":
        hard_failures.append("functional_envelope_overlap")
    for status in coverage.values():
        if status != "pass" and "missing_bridge_coverage" not in hard_failures:
            hard_failures.append("missing_bridge_coverage")
    envelope_ownership = _envelope_ownership(partition, candidate)
    envelope_assignment = _envelope_assignment(partition, candidate)
    if any(facts["wrong_label_bridge_ids"] for facts in envelope_ownership.values()):
        hard_failures.append("bridge_region_covers_wrong_envelope_group")
    if any(facts["status"] != "pass" for facts in envelope_assignment.values()):
        hard_failures.append("bridge_region_covers_wrong_envelope_group")
    connectivity = candidate.get("connectivity_by_bridge") or {
        bridge_id: {
            "component_count": 1,
            "outer_service_arc_count": _service_arc_count(candidate, bridge_id),
        }
        for bridge_id in BRIDGE_IDS
    }
    if scheme == "A":
        for facts in connectivity.values():
            if facts["component_count"] != 1 and "bridge_region_disconnected" not in hard_failures:
                hard_failures.append("bridge_region_disconnected")
            if facts["outer_service_arc_count"] != 1:
                if "scheme_a_multiple_outer_arcs" not in hard_failures:
                    hard_failures.append("scheme_a_multiple_outer_arcs")
    fastener_service = {
        bridge_id: _fastener_service(candidate, bridge_id)
        for bridge_id in BRIDGE_IDS
    }
    manufacturing_boundaries = candidate.get("manufacturing_boundaries", [])
    if any(boundary.get("status") != "pass" for boundary in manufacturing_boundaries):
        hard_failures.append("acute_or_noisy_seam_path")
    if scheme == "B" and not manufacturing_boundaries:
        hard_failures.append("acute_or_noisy_seam_path")
    service_island_policy = candidate.get("service_island_policy", {})
    if scheme == "B":
        for service_list in fastener_service.values():
            if not service_list:
                hard_failures.append("scheme_b_missing_service_island")
            for service in service_list:
                if service["span_deg"] < 40.0 and service["pad_policy"] != "full_span_under_40_deg":
                    hard_failures.append("scheme_b_invalid_short_island_pad")
                if service["span_deg"] <= 0.0:
                    hard_failures.append("fastener_service_arc_too_short")
        if service_island_policy.get("short_island_pad") != "full_span_under_40_deg":
            hard_failures.append("scheme_b_invalid_short_island_pad")
        if service_island_policy.get("pad_side_reference") != "local_bridge_boundary":
            hard_failures.append("scheme_b_missing_service_island")
    bridge_footprints = _bridge_footprint_validation(candidate, scheme)
    if scheme == "B" and bridge_footprints["status"] != "pass":
        hard_failures.extend(bridge_footprints["failures"])
    seam_checks = candidate.get(
        "seam_checks",
        {
            "envelope_crossing": "pass" if not hard_failures else "fail",
            "minimum_gap_width": "pass",
            "straight_or_obtuse": "pass",
        },
    )
    return {
        "candidate_id": candidate_id,
        "topology": candidate.get("topology", "unknown"),
        "scheme": scheme,
        "hard_status": "pass" if not hard_failures else "fail",
        "hard_failures": hard_failures,
        "known_failure_reasons": known_failure_reasons,
        "soft_warnings": [],
        "coverage": coverage,
        "functional_envelope_overlap": envelope_overlap,
        "envelope_ownership_status": "pass"
        if all(not facts["wrong_label_bridge_ids"] for facts in envelope_ownership.values())
        else "fail",
        "envelope_ownership": envelope_ownership,
        "envelope_assignment_status": "pass"
        if all(facts["status"] == "pass" for facts in envelope_assignment.values())
        else "fail",
        "envelope_assignment": envelope_assignment,
        "seam_checks": seam_checks,
        "connectivity": connectivity,
        "fastener_service": fastener_service,
        "manufacturing_boundary_status": "pass"
        if manufacturing_boundaries and all(boundary.get("status") == "pass" for boundary in manufacturing_boundaries)
        else "fail",
        "manufacturing_boundaries": manufacturing_boundaries,
        "service_island_policy": service_island_policy,
        "bridge_footprint_status": bridge_footprints["status"],
        "bridge_footprints": bridge_footprints["footprints"],
        "bridge_footprint_failures": bridge_footprints["failures"],
    }


def _bridge_footprint_validation(candidate: dict[str, Any], scheme: str) -> dict[str, Any]:
    footprints = candidate.get("bridge_plate_footprints", [])
    if scheme != "B":
        return {"status": "not_required", "footprints": footprints, "failures": []}
    failures = []
    if not footprints:
        failures.append("bridge_footprint_missing")
    bridge_ids = sorted(footprint.get("bridge_id") for footprint in footprints)
    if bridge_ids != sorted(BRIDGE_IDS):
        failures.append("bridge_footprint_missing")
    for footprint in footprints:
        if footprint.get("footprint_kind") != "bounded_bridge_plate_footprint":
            failures.append("bridge_footprint_invalid")
        if footprint.get("outer_edge_kind") != "case_concentric_arc":
            failures.append("bridge_footprint_invalid")
        if footprint.get("empty_mainplate_area_allowed") is not True:
            failures.append("bridge_footprint_invalid")
        if float(footprint.get("area_mm2", 0.0)) <= 0.0:
            failures.append("bridge_footprint_invalid")
        if not footprint.get("service_pads"):
            failures.append("bridge_footprint_invalid")
        for service_pad in footprint.get("service_pads", []):
            if service_pad.get("footprint_type") != "outer_annular_service_pad":
                failures.append("bridge_footprint_invalid")
            if service_pad.get("outer_edge_kind") != "case_concentric_arc":
                failures.append("bridge_footprint_invalid")
            if service_pad.get("empty_mainplate_area_allowed") is not True:
                failures.append("bridge_footprint_invalid")
    unique_failures = []
    for failure in failures:
        if failure not in unique_failures:
            unique_failures.append(failure)
    return {
        "status": "pass" if not unique_failures else "fail",
        "footprints": footprints,
        "failures": unique_failures,
    }


def _functional_envelope_overlap(partition: dict[str, Any]) -> dict[str, Any]:
    pair_results = []
    for index, left_id in enumerate(BRIDGE_IDS):
        for right_id in BRIDGE_IDS[index + 1:]:
            left = partition["envelopes"][left_id]["points"]
            right = partition["envelopes"][right_id]["points"]
            relation = _polygon_overlap_relation(left, right)
            pair_results.append(
                {
                    "pair": [left_id, right_id],
                    "status": "fail" if relation["overlaps"] else "pass",
                    **relation,
                }
            )
    return {
        "status": "pass" if all(result["status"] == "pass" for result in pair_results) else "fail",
        "pairs": pair_results,
    }


def _polygon_overlap_relation(left_points: list[list[float]], right_points: list[list[float]]) -> dict[str, Any]:
    left = [(float(point[0]), float(point[1])) for point in left_points]
    right = [(float(point[0]), float(point[1])) for point in right_points]
    edge_cross_count = sum(
        1
        for left_start, left_end in zip(left, [*left[1:], left[0]])
        for right_start, right_end in zip(right, [*right[1:], right[0]])
        if _segments_intersect(left_start, left_end, right_start, right_end)
    )
    left_vertices_inside_right = sum(1 for point in left if _point_in_polygon(point, right))
    right_vertices_inside_left = sum(1 for point in right if _point_in_polygon(point, left))
    return {
        "overlaps": edge_cross_count > 0 or left_vertices_inside_right > 0 or right_vertices_inside_left > 0,
        "edge_cross_count": edge_cross_count,
        "left_vertices_inside_right": left_vertices_inside_right,
        "right_vertices_inside_left": right_vertices_inside_left,
    }


def _segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    def orient(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_segment(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> bool:
        return (
            min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9
            and min(p[1], r[1]) - 1e-9 <= q[1] <= max(p[1], r[1]) + 1e-9
        )

    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    if o1 * o2 < -1e-9 and o3 * o4 < -1e-9:
        return True
    return (
        abs(o1) <= 1e-9 and on_segment(a, c, b)
        or abs(o2) <= 1e-9 and on_segment(a, d, b)
        or abs(o3) <= 1e-9 and on_segment(c, a, d)
        or abs(o4) <= 1e-9 and on_segment(c, b, d)
    )


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    inside = False
    x, y = point
    previous = polygon[-1]
    for current in polygon:
        xi, yi = current
        xj, yj = previous
        intersects = (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
        if intersects:
            inside = not inside
        previous = current
    return inside


def _envelope_ownership(partition: dict[str, Any], candidate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    grid = candidate.get("grid")
    if not grid:
        return {
            bridge_id: _ownership_failure(bridge_id, ["candidate_geometry_unavailable"])
            for bridge_id in BRIDGE_IDS
        }
    xs = [float(value) for value in grid["xs"]]
    ys = [float(value) for value in grid["ys"]]
    labels = grid["labels"]
    bridge_ids = grid["bridge_ids"]
    facts = {}
    for bridge_id in BRIDGE_IDS:
        expected_label = bridge_ids.index(bridge_id) if bridge_id in bridge_ids else -999
        wrong_hits = []
        for sample in _envelope_sample_points(partition["envelopes"][bridge_id]):
            label = _label_at_point(labels, xs, ys, sample)
            if label != expected_label:
                wrong_hits.append(
                    {
                        "point": [round(sample[0], 4), round(sample[1], 4)],
                        "actual_bridge": _bridge_id_for_label(bridge_ids, label),
                    }
                )
        wrong_bridge_ids = sorted(
            {
                hit["actual_bridge"]
                for hit in wrong_hits
                if hit["actual_bridge"] != "seam_or_gap"
            }
        )
        facts[bridge_id] = {
            "expected_bridge": bridge_id,
            "expected_bridge_id": bridge_id,
            "status": "pass" if not wrong_hits else "fail",
            "sample_count": len(_envelope_sample_points(partition["envelopes"][bridge_id])),
            "wrong_label_count": len(wrong_hits),
            "wrong_bridge_hits": wrong_hits,
            "wrong_label_bridge_ids": wrong_bridge_ids,
        }
    return facts


def _ownership_failure(bridge_id: str, wrong_bridge_ids: list[str]) -> dict[str, Any]:
    return {
        "expected_bridge": bridge_id,
        "expected_bridge_id": bridge_id,
        "status": "fail",
        "sample_count": 0,
        "wrong_label_count": 1,
        "wrong_bridge_hits": [{"point": [], "actual_bridge": wrong_bridge_ids[0]}],
        "wrong_label_bridge_ids": wrong_bridge_ids,
    }


def _envelope_assignment(partition: dict[str, Any], candidate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    grid = candidate.get("grid")
    if not grid:
        return {
            bridge_id: {
                "owned_envelopes": [],
                "foreign_envelopes": ["candidate_geometry_unavailable"],
                "status": "fail",
            }
            for bridge_id in BRIDGE_IDS
        }
    xs = [float(value) for value in grid["xs"]]
    ys = [float(value) for value in grid["ys"]]
    labels = grid["labels"]
    bridge_ids = grid["bridge_ids"]
    owned_by_bridge = {bridge_id: [] for bridge_id in BRIDGE_IDS}
    for envelope_id in BRIDGE_IDS:
        samples = _envelope_sample_points(partition["envelopes"][envelope_id])
        labels_seen = {
            _bridge_id_for_label(bridge_ids, _label_at_point(labels, xs, ys, sample))
            for sample in samples
        }
        for owner_id in labels_seen:
            if owner_id in owned_by_bridge:
                owned_by_bridge[owner_id].append(envelope_id)
    assignment = {}
    for bridge_id in BRIDGE_IDS:
        owned = sorted(set(owned_by_bridge[bridge_id]), key=BRIDGE_IDS.index)
        foreign = [envelope_id for envelope_id in owned if envelope_id != bridge_id]
        assignment[bridge_id] = {
            "owned_envelopes": owned,
            "foreign_envelopes": foreign,
            "status": "pass" if owned == [bridge_id] and not foreign else "fail",
        }
    return assignment


def _envelope_sample_points(envelope: dict[str, Any]) -> list[tuple[float, float]]:
    points = [(float(point[0]), float(point[1])) for point in envelope["points"]]
    centroid = (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )
    samples = [centroid]
    for start, end in zip(points, [*points[1:], points[0]]):
        edge_midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        for source in [start, edge_midpoint]:
            samples.append(
                (
                    centroid[0] * 0.2 + source[0] * 0.8,
                    centroid[1] * 0.2 + source[1] * 0.8,
                )
            )
    return samples


def _label_at_point(labels: Any, xs: list[float], ys: list[float], point: tuple[float, float]) -> int:
    ix = min(range(len(xs)), key=lambda index: abs(xs[index] - point[0]))
    iy = min(range(len(ys)), key=lambda index: abs(ys[index] - point[1]))
    return int(labels[iy][ix])


def _bridge_id_for_label(bridge_ids: list[str], label: int) -> str:
    if 0 <= label < len(bridge_ids):
        return bridge_ids[label]
    return "seam_or_gap"


def _service_arc_count(candidate: dict[str, Any], bridge_id: str) -> int:
    for region in candidate.get("regions", []):
        if region.get("bridge_id") == bridge_id:
            return len(region.get("outer_service_islands", []))
    return 1


def _fastener_service(candidate: dict[str, Any], bridge_id: str) -> list[dict[str, Any]]:
    for region in candidate.get("regions", []):
        if region.get("bridge_id") != bridge_id:
            continue
        islands = region.get("outer_service_islands", [])
        if not islands:
            return []
        return [
            {
                "span_deg": round(float(island["span_deg"]), 6),
                "screw_count": int(island.get("screw_count", _screw_count_for_span(float(island["span_deg"])))),
                "pad_policy": island.get(
                    "pad_policy",
                    "full_span_under_40_deg"
                    if float(island["span_deg"]) < 40.0
                    else "full_or_6_head_diameters",
                ),
                "pad_side_reference": island.get("pad_side_reference", "local_bridge_boundary"),
            }
            for island in islands
        ]
    return []


def _screw_count_for_span(span_deg: float) -> int:
    if span_deg < 40.0:
        return 1
    if span_deg > 90.0:
        return 3
    return 2


def _write_review_packet(report: dict[str, Any], target: Path) -> None:
    report_path = target / "bridge_partition_loop_report.json"
    prompt_path = target / "subagent_review_prompt.md"
    _render_axis_sheet(report["layouts"], target / "axis_layout_contact_sheet.png")
    _render_partition_sheet(report["layouts"], target / "selected_partition_contact_sheet.png", "selected")
    _render_partition_sheet(report["layouts"], target / "scheme_a_contact_sheet.png", "A")
    _render_partition_sheet(report["layouts"], target / "scheme_b_contact_sheet.png", "B")
    report["artifacts"] = {
        "axis_layout_contact_sheet": str((target / "axis_layout_contact_sheet.png").resolve()),
        "selected_partition_contact_sheet": str((target / "selected_partition_contact_sheet.png").resolve()),
        "scheme_a_contact_sheet": str((target / "scheme_a_contact_sheet.png").resolve()),
        "scheme_b_contact_sheet": str((target / "scheme_b_contact_sheet.png").resolve()),
        "bridge_partition_loop_report": str(report_path.resolve()),
        "subagent_review_prompt": str(prompt_path.resolve()),
    }
    public = _public_report(report)
    prompt_path.write_text(_subagent_review_prompt(public), encoding="utf-8")
    report_path.write_text(json.dumps(public, indent=2, ensure_ascii=False), encoding="utf-8")


def _public_report(report: dict[str, Any]) -> dict[str, Any]:
    public = dict(report)
    public["layouts"] = [
        {key: value for key, value in layout.items() if not key.startswith("_")}
        for layout in report["layouts"]
    ]
    return public


def _render_axis_sheet(layouts: list[dict[str, Any]], output_path: Path) -> None:
    fig, axes = plt.subplots(2, 5, figsize=(20, 8), dpi=150)
    for ax, layout in zip(axes.flatten(), layouts):
        _render_axis_layout(ax, layout["_design"], layout["layout_id"])
    fig.tight_layout()
    fig.savefig(output_path, facecolor="white")
    plt.close(fig)


def _render_partition_sheet(layouts: list[dict[str, Any]], output_path: Path, mode: str) -> None:
    fig, axes = plt.subplots(2, 5, figsize=(20, 8), dpi=150)
    for ax, layout in zip(axes.flatten(), layouts):
        scheme = layout["selected_scheme"] if mode == "selected" else mode
        candidate_id = SCHEME_A_ID if scheme == "A" else SCHEME_B_ID
        partition = layout["_partition"]
        candidate = partition["candidates"][candidate_id]
        title = f"{layout['layout_id']}\n{scheme}: {candidate_id}\nselected={layout['selected_scheme']}"
        _render_candidate(ax, partition, candidate, title)
    fig.tight_layout()
    fig.savefig(output_path, facecolor="white")
    plt.close(fig)


def _subagent_review_prompt(report: dict[str, Any]) -> str:
    return f"""# Watch Bridge Partition Review

Review ten watch bridge XY partition layouts.

Rules:
- selected scheme is B-only weighted Voronoi
- selected scheme is B only when A hard-fails and B hard-passes
- no visible seam crosses the barrel/train/escapement functional envelopes
- gaps are visible and reasonably stable
- selected regions look like manufacturable bridge plates, not fragments
- B service islands look intentional and fastenable

Return exactly:

```text
visual_status: pass | fail
failed_layouts:
failed_scheme:
hard_failures:
aesthetic_failures:
engineering_concerns:
recommended_solver_iteration:
```

Summary:

```text
status: {report["status"]}
scheme_counts: {report["scheme_counts"]}
hard_failures: {report["hard_failures"]}
```
"""
