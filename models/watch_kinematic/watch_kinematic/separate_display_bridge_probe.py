"""Bridge partition probe for the separate hour/minute watch pattern."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from .bridge_partition_loop import _candidate_validation
from .bridge_xy_partition import _render_candidate, solve_bridge_xy_partition
from .power_chain_mvp import CASE_RADIUS_MM, _build_separate_display_design
from .separate_display_pattern import solve_separate_display_layout


SCHEME_A_ID = "continuous_outer_arc_y"
SCHEME_B_ID = "service_island_power_partition"
LAYOUT_DIVERSITY_THRESHOLD = 0.035
SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS: dict[str, list[str]] = {
    "barrel_bridge": ["barrel_axis"],
    "train_bridge": [
        "train_stage_1_axis",
        "train_stage_2_axis",
        "train_stage_3_axis",
        "display_input_relay_axis",
        "minute_display_axis",
        "display_relay_axis",
        "hour_display_axis",
    ],
    "escapement_bridge": ["escape_axis", "pallet_axis", "balance_axis"],
}
SEPARATE_DISPLAY_BRIDGE_AXIS_GROUP_LINKS: dict[str, list[list[str]]] = {
    "train_bridge": [
        ["train_stage_1_axis", "train_stage_2_axis"],
        ["train_stage_2_axis", "train_stage_3_axis"],
        ["train_stage_3_axis", "display_input_relay_axis"],
        ["display_input_relay_axis", "minute_display_axis"],
        ["minute_display_axis", "display_relay_axis"],
        ["display_relay_axis", "hour_display_axis"],
    ],
    "escapement_bridge": [
        ["escape_axis", "pallet_axis"],
        ["pallet_axis", "balance_axis"],
    ],
}


def run_separate_display_bridge_partition_probe(
    *,
    base_seed: int,
    layout_count: int = 5,
    output_dir: str | Path | None = None,
    grid_resolution: int = 121,
) -> dict[str, Any]:
    """Generate random separate-display layouts and solve A/B bridge partitions."""

    target = Path(output_dir) if output_dir is not None else None
    if target is not None:
        target.mkdir(parents=True, exist_ok=True)

    candidate_seeds = _select_random_feasible_seeds(base_seed, max(layout_count * 4, layout_count))
    layouts = []
    rejected_layouts = []
    for seed in candidate_seeds:
        solver_report = solve_separate_display_layout(seed=seed)
        design = _build_separate_display_design(seed, solver_report)
        design["bridge_axis_groups"] = SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS
        design["bridge_axis_group_links"] = SEPARATE_DISPLAY_BRIDGE_AXIS_GROUP_LINKS
        partition = solve_bridge_xy_partition(
            design,
            grid_resolution=grid_resolution,
            axis_groups=SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS,
            axis_group_links=SEPARATE_DISPLAY_BRIDGE_AXIS_GROUP_LINKS,
        )
        scheme_results = {
            "A": _candidate_validation(partition, SCHEME_A_ID, "A"),
            "B": _candidate_validation(partition, SCHEME_B_ID, "B"),
        }
        if scheme_results["B"]["hard_status"] != "pass":
            rejected_layouts.append(
                {
                    "seed": seed,
                    "reason": "scheme_b_failed",
                    "hard_failures": scheme_results["B"]["hard_failures"],
                }
            )
            continue
        layouts.append(
            {
                "layout_id": f"separate_seed_{seed}",
                "seed": seed,
                "solver_status": solver_report["status"],
                "axis_groups": SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS,
                "scheme_results": scheme_results,
                "_design": design,
                "_partition": partition,
            }
        )
        if len(layouts) == layout_count:
            break

    hard_failures = [
        {
            "layout_id": layout["layout_id"],
            "scheme": "B",
            "hard_failures": layout["scheme_results"]["B"]["hard_failures"],
        }
        for layout in layouts
        if layout["scheme_results"]["B"]["hard_status"] != "pass"
    ]
    layout_diversity = _layout_diversity_report(layouts)
    if layout_diversity["status"] != "pass":
        hard_failures.append(
            {
                "layout_id": "batch",
                "scheme": "axis_layout",
                "hard_failures": ["layout_diversity_below_threshold"],
            }
        )
    report = {
        "kind": "watch_separate_display_bridge_partition_probe",
        "status": "pass" if len(layouts) == layout_count and not hard_failures else "fail",
        "base_seed": base_seed,
        "requested_layout_count": layout_count,
        "selected_seeds": [layout["seed"] for layout in layouts],
        "candidate_seed_pool": candidate_seeds,
        "rejected_layouts": rejected_layouts,
        "axis_group_policy": "separate_display_three_bridge_groups",
        "layout_diversity_status": layout_diversity["status"],
        "layout_diversity": layout_diversity,
        "scheme_render_counts": {"A": len(layouts), "B": len(layouts)},
        "layouts": layouts,
        "hard_failures": hard_failures,
        "artifacts": {},
    }
    if target is not None:
        _write_probe_artifacts(report, target)
    return _public_report(report)


def _select_random_feasible_seeds(base_seed: int, layout_count: int) -> list[int]:
    rng = random.Random(base_seed)
    feasible: list[tuple[int, tuple[float, ...]]] = []
    tried: set[int] = set()
    for _ in range(650):
        seed = rng.randint(1, 9999)
        if seed in tried:
            continue
        tried.add(seed)
        solver_report = solve_separate_display_layout(seed=seed)
        if solver_report["status"] == "pass" and solver_report["selected_candidate"] is not None:
            feasible.append((seed, _axis_layout_vector(solver_report["selected_candidate"])))
            if len(feasible) >= max(layout_count * 18, 120):
                break
    if len(feasible) < layout_count:
        raise RuntimeError(f"could not find {layout_count} feasible separate-display seeds")
    return _farthest_diverse_seed_subset(feasible, layout_count, rng)


def _axis_layout_vector(candidate: dict[str, Any]) -> tuple[float, ...]:
    axis_by_id = {axis["axis_id"]: axis for axis in candidate["axes"]}
    ordered_axis_ids = [
        "barrel_axis",
        "train_stage_1_axis",
        "train_stage_2_axis",
        "train_stage_3_axis",
        "escape_axis",
        "balance_axis",
        "display_input_relay_axis",
        "minute_display_axis",
        "display_relay_axis",
        "hour_display_axis",
    ]
    values: list[float] = []
    for axis_id in ordered_axis_ids:
        axis = axis_by_id[axis_id]
        values.extend([float(axis["x"]), float(axis["y"])])
    return tuple(values)


def _farthest_diverse_seed_subset(
    feasible: list[tuple[int, tuple[float, ...]]],
    layout_count: int,
    rng: random.Random,
) -> list[int]:
    first = rng.choice(feasible)
    selected = [first]
    remaining = [item for item in feasible if item[0] != first[0]]
    while len(selected) < layout_count:
        next_item = max(
            remaining,
            key=lambda item: min(_layout_vector_distance(item[1], chosen[1]) for chosen in selected),
        )
        selected.append(next_item)
        remaining = [item for item in remaining if item[0] != next_item[0]]
    return [seed for seed, _ in selected]


def _layout_vector_distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum((a - b) ** 2 for a, b in zip(left, right)) ** 0.5


def _layout_diversity_report(layouts: list[dict[str, Any]]) -> dict[str, Any]:
    vectors = {
        layout["seed"]: _design_axis_layout_vector(layout["_design"])
        for layout in layouts
    }
    angle_spans = _axis_angle_spans(layouts)
    distances = []
    seeds = list(vectors)
    for left_index, left_seed in enumerate(seeds):
        for right_seed in seeds[left_index + 1:]:
            normalized = _normalized_layout_vector_distance(vectors[left_seed], vectors[right_seed])
            distances.append(
                {
                    "pair": [left_seed, right_seed],
                    "normalized_distance": round(normalized, 6),
                }
            )
    minimum = min((item["normalized_distance"] for item in distances), default=0.0)
    return {
        "status": "pass" if len(layouts) >= 2 and minimum >= LAYOUT_DIVERSITY_THRESHOLD else "fail",
        "threshold": LAYOUT_DIVERSITY_THRESHOLD,
        "minimum_normalized_pairwise_distance": minimum,
        "pairwise_distances": distances,
        "axis_angle_spans_deg": angle_spans,
        "metric": "euclidean_distance_over_case_radius_and_axis_count",
    }


def _design_axis_layout_vector(design: dict[str, Any]) -> tuple[float, ...]:
    axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
    axis_ids = [
        "barrel_axis",
        "train_stage_1_axis",
        "train_stage_2_axis",
        "train_stage_3_axis",
        "escape_axis",
        "balance_axis",
        "display_input_relay_axis",
        "minute_display_axis",
        "display_relay_axis",
        "hour_display_axis",
    ]
    values: list[float] = []
    for axis_id in axis_ids:
        axis = axis_by_id[axis_id]
        values.extend([float(axis["x"]), float(axis["y"])])
    return tuple(values)


def _normalized_layout_vector_distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    raw = _layout_vector_distance(left, right)
    return raw / (CASE_RADIUS_MM * max(1.0, len(left) ** 0.5))


def _axis_angle_spans(layouts: list[dict[str, Any]]) -> dict[str, float]:
    axis_ids = [
        "train_stage_1_axis",
        "train_stage_2_axis",
        "train_stage_3_axis",
        "escape_axis",
        "balance_axis",
        "minute_display_axis",
        "hour_display_axis",
    ]
    spans = {}
    for axis_id in axis_ids:
        angles = []
        for layout in layouts:
            axis = next(axis for axis in layout["_design"]["axes"] if axis["axis_id"] == axis_id)
            angles.append(math.degrees(math.atan2(float(axis["y"]), float(axis["x"]))) % 360.0)
        spans[axis_id] = round(_circular_angle_span(angles), 6)
    return spans


def _circular_angle_span(angles: list[float]) -> float:
    if len(angles) <= 1:
        return 0.0
    ordered = sorted(angle % 360.0 for angle in angles)
    gaps = [
        ordered[index + 1] - ordered[index]
        for index in range(len(ordered) - 1)
    ]
    gaps.append(ordered[0] + 360.0 - ordered[-1])
    return 360.0 - max(gaps)


def _write_probe_artifacts(report: dict[str, Any], target: Path) -> None:
    axis_path = target / "separate_display_axis_layouts.png"
    scheme_a_path = target / "separate_display_scheme_a_partitions.png"
    scheme_b_path = target / "separate_display_scheme_b_partitions.png"
    ab_path = target / "separate_display_ab_partition_review.png"
    html_path = target / "separate_display_bridge_ab_review.html"
    json_path = target / "separate_display_bridge_ab_probe.json"

    _render_axis_contact_sheet(report["layouts"], axis_path)
    _render_scheme_contact_sheet(report["layouts"], "A", scheme_a_path)
    _render_scheme_contact_sheet(report["layouts"], "B", scheme_b_path)
    _render_ab_contact_sheet(report["layouts"], ab_path)
    report["artifacts"] = {
        "axis_layout_contact_sheet": str(axis_path.resolve()),
        "scheme_a_contact_sheet": str(scheme_a_path.resolve()),
        "scheme_b_contact_sheet": str(scheme_b_path.resolve()),
        "ab_review_contact_sheet": str(ab_path.resolve()),
        "review_html": str(html_path.resolve()),
        "report_json": str(json_path.resolve()),
    }
    public = _public_report(report)
    json_path.write_text(json.dumps(public, indent=2, ensure_ascii=False), encoding="utf-8")
    html_path.write_text(_render_probe_html(public), encoding="utf-8")


def _public_report(report: dict[str, Any]) -> dict[str, Any]:
    public = dict(report)
    public["layouts"] = [
        {key: value for key, value in layout.items() if not key.startswith("_")}
        for layout in report["layouts"]
    ]
    return public


def _render_axis_contact_sheet(layouts: list[dict[str, Any]], output_path: Path) -> None:
    fig, axes = plt.subplots(1, len(layouts), figsize=(4.1 * len(layouts), 4.2), dpi=160)
    if len(layouts) == 1:
        axes = [axes]
    for ax, layout in zip(axes, layouts):
        _render_axis_layout(ax, layout["_design"], f"seed {layout['seed']} axis layout")
    fig.tight_layout()
    fig.savefig(output_path, facecolor="white")
    plt.close(fig)


def _render_scheme_contact_sheet(layouts: list[dict[str, Any]], scheme: str, output_path: Path) -> None:
    fig, axes = plt.subplots(1, len(layouts), figsize=(4.1 * len(layouts), 4.2), dpi=160)
    if len(layouts) == 1:
        axes = [axes]
    candidate_id = SCHEME_A_ID if scheme == "A" else SCHEME_B_ID
    for ax, layout in zip(axes, layouts):
        candidate = layout["_partition"]["candidates"][candidate_id]
        status = layout["scheme_results"][scheme]["hard_status"]
        title = f"seed {layout['seed']}\n{scheme}: {candidate_id}\n{status}"
        _render_candidate(ax, layout["_partition"], candidate, title)
    fig.tight_layout()
    fig.savefig(output_path, facecolor="white")
    plt.close(fig)


def _render_ab_contact_sheet(layouts: list[dict[str, Any]], output_path: Path) -> None:
    fig, axes = plt.subplots(len(layouts), 2, figsize=(8.4, 4.1 * len(layouts)), dpi=150)
    if len(layouts) == 1:
        axes = [axes]
    for row, layout in zip(axes, layouts):
        for ax, scheme, candidate_id in [
            (row[0], "A", SCHEME_A_ID),
            (row[1], "B", SCHEME_B_ID),
        ]:
            result = layout["scheme_results"][scheme]
            candidate = layout["_partition"]["candidates"][candidate_id]
            title = f"seed {layout['seed']} | {scheme}\n{result['hard_status']} | {candidate_id}"
            _render_candidate(ax, layout["_partition"], candidate, title)
    fig.tight_layout()
    fig.savefig(output_path, facecolor="white")
    plt.close(fig)


def _render_axis_layout(ax: Any, design: dict[str, Any], title: str) -> None:
    ax.set_aspect("equal")
    ax.set_xlim(-CASE_RADIUS_MM - 1.5, CASE_RADIUS_MM + 1.5)
    ax.set_ylim(-CASE_RADIUS_MM - 1.5, CASE_RADIUS_MM + 1.5)
    ax.axis("off")
    ax.set_title(title, fontsize=10)
    ax.add_patch(plt.Circle((0, 0), CASE_RADIUS_MM, fill=False, ec="#9aa5b1", lw=1.2))

    gear_by_id = {gear["gear_id"]: gear for gear in [*design["gears"], *design["display_gears"]]}
    for mesh in [*design["meshes"], *design["display_meshes"]]:
        driver = gear_by_id[mesh["driver"]]
        driven = gear_by_id[mesh["driven"]]
        ax.plot([driver["x"], driven["x"]], [driver["y"], driven["y"]], color="#344054", lw=0.9, alpha=0.45, zorder=1)
    for gear in gear_by_id.values():
        color = "#a46f00" if gear["gear_type"] == "wheel" else "#7a2e0e"
        ax.add_patch(plt.Circle((gear["x"], gear["y"]), gear["pitch_radius"], fill=False, ec=color, lw=0.8, alpha=0.5, zorder=2))
    group_colors = {
        "barrel_bridge": "#a16207",
        "train_bridge": "#0b57d0",
        "escapement_bridge": "#067647",
    }
    for bridge_id, axis_ids in SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS.items():
        color = group_colors[bridge_id]
        for axis_id in axis_ids:
            axis = next(axis for axis in design["axes"] if axis["axis_id"] == axis_id)
            ax.add_patch(plt.Circle((axis["x"], axis["y"]), 0.18, color=color, zorder=5))
            ax.text(axis["x"] + 0.23, axis["y"] + 0.18, axis_id.replace("_axis", ""), fontsize=5.6, color=color, zorder=6)


def _render_probe_html(report: dict[str, Any]) -> str:
    artifacts = {key: Path(value).name for key, value in report["artifacts"].items()}
    rows = "\n".join(
        f"<tr><td>{layout['seed']}</td><td>{layout['scheme_results']['A']['hard_status']}</td>"
        f"<td>{', '.join(layout['scheme_results']['A']['hard_failures']) or '-'}</td>"
        f"<td>{layout['scheme_results']['B']['hard_status']}</td>"
        f"<td>{layout['scheme_results']['B']['functional_envelope_overlap']['status']}</td>"
        f"<td>{layout['scheme_results']['B']['bridge_footprint_status']}</td>"
        f"<td>{', '.join(layout['scheme_results']['B']['hard_failures']) or '-'}</td></tr>"
        for layout in report["layouts"]
    )
    diversity = report["layout_diversity"]
    span_text = ", ".join(
        f"{axis_id}: {span:.1f} deg"
        for axis_id, span in diversity["axis_angle_spans_deg"].items()
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Separate Display Bridge A/B Partition Review</title>
  <style>
    body {{ margin: 0; padding: 28px; font-family: Arial, sans-serif; color: #1f2937; background: #f6f8fb; }}
    h1 {{ margin: 0 0 8px; font-size: 26px; }}
    h2 {{ margin: 26px 0 12px; font-size: 18px; }}
    .meta {{ color: #667085; margin-bottom: 18px; }}
    img {{ display: block; max-width: 100%; border: 1px solid #d0d7e2; border-radius: 8px; background: white; margin-bottom: 20px; }}
    table {{ border-collapse: collapse; width: 100%; background: white; border: 1px solid #d0d7e2; border-radius: 8px; overflow: hidden; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 8px 10px; text-align: left; font-size: 13px; }}
    th {{ background: #eef2f7; }}
  </style>
</head>
<body>
  <h1>分离时针/分针 Pattern：桥板平面 A/B 求解检查</h1>
  <div class="meta">base seed: {report['base_seed']} | selected seeds: {', '.join(str(seed) for seed in report['selected_seeds'])}</div>
  <div class="meta">diversity: {report['layout_diversity_status']} | min normalized distance: {diversity['minimum_normalized_pairwise_distance']:.3f} / threshold {diversity['threshold']:.3f}</div>
  <div class="meta">angle spans: {span_text}</div>
  <h2>5 套随机轴位布局</h2>
  <img src="{artifacts['axis_layout_contact_sheet']}" alt="axis layouts" />
  <h2>A/B 对照</h2>
  <img src="{artifacts['ab_review_contact_sheet']}" alt="A/B bridge partition review" />
  <h2>算法 A：连续三分外缘</h2>
  <img src="{artifacts['scheme_a_contact_sheet']}" alt="scheme A partitions" />
  <h2>算法 B：服务岛/跨越式桥板</h2>
  <img src="{artifacts['scheme_b_contact_sheet']}" alt="scheme B partitions" />
  <h2>校验摘要</h2>
  <table>
    <thead><tr><th>seed</th><th>A 状态</th><th>A 失败项</th><th>B 状态</th><th>B 包络重叠</th><th>B footprint</th><th>B 失败项</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
"""
