"""Rule-space sampler for Gate A1.5 of the watch kinematic demo."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from copy import deepcopy
from html import escape
import json
from math import hypot
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESEARCH_DIR = REPO_ROOT / "docs" / "research" / "watch_kinematic"
DEFAULT_JSON_OUTPUT = DEFAULT_RESEARCH_DIR / "rule_space_report.json"
DEFAULT_HTML_OUTPUT = DEFAULT_RESEARCH_DIR / "rule_space_dashboard.html"

MESH_TOLERANCE_MM = 0.03


def build_rule_space_report() -> dict:
    candidates = [_with_validation(candidate) for candidate in _build_seed_candidates()]
    summary = _summarize(candidates)
    return {
        "gate": "A1.5",
        "title": "Watch kinematic rule-space sampling validation",
        "scope": (
            "Abstract 2D topology/layout candidates only. No STEP/CAD and no claim of "
            "production mechanical-watch correctness."
        ),
        "formal_model": "docs/research/watch_kinematic/transmission_assembly_formal_model_v0.md",
        "evidence_map": "docs/research/watch_kinematic/literature_evidence_map.md",
        "summary": summary,
        "candidates": candidates,
    }


def validate_candidate(candidate: dict) -> dict:
    reasons: list[str] = []
    checks = {
        "all_outputs_connected": _outputs_connected(candidate, reasons),
        "mesh_equations_satisfied": _mesh_equations_satisfied(candidate, reasons),
        "compound_axes_satisfied": _compound_axes_satisfied(candidate, reasons),
        "all_arbors_supported": _all_arbors_supported(candidate, reasons),
        "bridge_screws_complete": _bridge_screws_complete(candidate, reasons),
    }
    status = "valid" if all(checks.values()) else "invalid"
    return {
        "status": status,
        "checks": checks,
        "reasons": sorted(set(reasons)),
    }


def write_rule_space_report(
    report: dict | None = None,
    output_path: str | Path = DEFAULT_JSON_OUTPUT,
) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = report if report is not None else build_rule_space_report()
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def write_rule_space_dashboard(report: dict | None = None, output_path: str | Path = DEFAULT_HTML_OUTPUT) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = report if report is not None else build_rule_space_report()
    target.write_text(_render_dashboard(data), encoding="utf-8")
    return target


def write_default_rule_space_artifacts() -> tuple[Path, Path]:
    report = build_rule_space_report()
    return write_rule_space_report(report, DEFAULT_JSON_OUTPUT), write_rule_space_dashboard(report, DEFAULT_HTML_OUTPUT)


def _with_validation(candidate: dict) -> dict:
    enriched = deepcopy(candidate)
    _fill_pitch_radii(enriched)
    _fill_mesh_metadata(enriched)
    enriched["validation"] = validate_candidate(enriched)
    return enriched


def _build_seed_candidates() -> list[dict]:
    specs = [
        {
            "candidate_id": "straight_3_arbor_center_seconds",
            "topology_family": "straight_chain",
            "arbor_count": 3,
            "outputs": ["a2"],
            "teeth": [64, 16, 60, 15],
            "bridge_groups": [["a0", "a1", "a2"]],
            "style_tags": ["openworked", "spiral_visual"],
        },
        {
            "candidate_id": "straight_4_arbor_slow_display",
            "topology_family": "straight_chain",
            "arbor_count": 4,
            "outputs": ["a3"],
            "teeth": [72, 18, 66, 16, 54, 18],
            "bridge_groups": [["a0", "a1", "a2", "a3"]],
            "style_tags": ["openworked", "large_center_cutout"],
        },
        {
            "candidate_id": "offset_4_arbor_upper_bridge",
            "topology_family": "offset_chain",
            "arbor_count": 4,
            "outputs": ["a3"],
            "teeth": [70, 14, 60, 15, 56, 16],
            "bridge_groups": [["a0", "a1"], ["a2", "a3"]],
            "style_tags": ["spiral_visual", "asymmetric_bridge"],
            "directions": [(1, 0), (0.45, 0.89), (0.9, -0.44)],
        },
        {
            "candidate_id": "offset_5_arbor_long_train",
            "topology_family": "offset_chain",
            "arbor_count": 5,
            "outputs": ["a4"],
            "teeth": [76, 19, 64, 16, 58, 14, 48, 16],
            "bridge_groups": [["a0", "a1", "a2"], ["a3", "a4"]],
            "style_tags": ["openworked", "staggered_axes"],
            "directions": [(1, 0), (0.35, 0.94), (0.9, 0.44), (0.2, -0.98)],
        },
        {
            "candidate_id": "branched_5_arbor_dual_output",
            "topology_family": "branched_outputs",
            "arbor_count": 5,
            "outputs": ["a3", "a4"],
            "teeth": [68, 17, 64, 16, 52, 13, 44, 22],
            "bridge_groups": [["a0", "a1", "a2"], ["a3", "a4"]],
            "style_tags": ["openworked", "multi_hand"],
            "branch": True,
        },
        {
            "candidate_id": "branched_6_arbor_three_output",
            "topology_family": "branched_outputs",
            "arbor_count": 6,
            "outputs": ["a3", "a4", "a5"],
            "teeth": [72, 18, 60, 15, 50, 20, 46, 23, 42, 21],
            "bridge_groups": [["a0", "a1", "a2"], ["a3", "a4", "a5"]],
            "style_tags": ["spiral_visual", "multi_hand", "skeletonized"],
            "branch": True,
        },
        {
            "candidate_id": "dual_bridge_5_arbor_balanced",
            "topology_family": "dual_bridge_compact",
            "arbor_count": 5,
            "outputs": ["a2", "a4"],
            "teeth": [66, 22, 58, 29, 60, 20, 48, 24],
            "bridge_groups": [["a0", "a1", "a2"], ["a2", "a3", "a4"]],
            "style_tags": ["openworked", "balanced_bridges"],
            "directions": [(1, 0), (0.4, 0.92), (0.8, -0.6), (0.9, 0.44)],
        },
        {
            "candidate_id": "regulator_style_6_arbor_three_subdials",
            "topology_family": "regulator_display",
            "arbor_count": 6,
            "outputs": ["a2", "a4", "a5"],
            "teeth": [80, 20, 64, 16, 54, 18, 48, 16, 44, 22],
            "bridge_groups": [["a0", "a1", "a2"], ["a3", "a4"], ["a5"]],
            "style_tags": ["spiral_visual", "separate_subdials"],
            "branch": True,
        },
        {
            "candidate_id": "invalid_missing_upper_support",
            "topology_family": "offset_chain",
            "arbor_count": 4,
            "outputs": ["a3"],
            "teeth": [70, 14, 60, 15, 56, 16],
            "bridge_groups": [["a0", "a1", "a2", "a3"]],
            "style_tags": ["openworked"],
            "missing_upper_support_axis": "a2",
        },
        {
            "candidate_id": "invalid_disconnected_output",
            "topology_family": "branched_outputs",
            "arbor_count": 5,
            "outputs": ["a3", "a4"],
            "teeth": [68, 17, 64, 16, 52, 13, 44, 22],
            "bridge_groups": [["a0", "a1", "a2"], ["a3", "a4"]],
            "style_tags": ["multi_hand"],
            "branch": True,
            "disconnect_last_output": True,
        },
        {
            "candidate_id": "invalid_bad_mesh_distance",
            "topology_family": "straight_chain",
            "arbor_count": 3,
            "outputs": ["a2"],
            "teeth": [64, 16, 60, 15],
            "bridge_groups": [["a0", "a1", "a2"]],
            "style_tags": ["spiral_visual"],
            "bad_mesh_distance": True,
        },
        {
            "candidate_id": "invalid_incomplete_bridge_screws",
            "topology_family": "dual_bridge_compact",
            "arbor_count": 4,
            "outputs": ["a3"],
            "teeth": [72, 18, 66, 16, 54, 18],
            "bridge_groups": [["a0", "a1"], ["a2", "a3"]],
            "style_tags": ["openworked"],
            "incomplete_bridge_screws": True,
        },
    ]
    return [_candidate_from_spec(spec) for spec in specs]


def _candidate_from_spec(spec: dict) -> dict:
    axes = _axes_for_spec(spec)
    gears: list[dict] = []
    meshes: list[dict] = []
    compound_pairs: list[dict] = []

    def add_gear(axis_index: int, suffix: str, tooth_count: int) -> str:
        gear_id = f"g{axis_index}_{suffix}"
        gears.append(
            {
                "gear_id": gear_id,
                "axis_id": f"a{axis_index}",
                "tooth_count": tooth_count,
                "module": 0.18,
            }
        )
        return gear_id

    tooth_values = spec["teeth"]
    if spec.get("branch"):
        previous_wheel = add_gear(0, "wheel", tooth_values[0])
        tooth_index = 1
        for axis_index in range(1, min(3, spec["arbor_count"])):
            pinion = add_gear(axis_index, "pinion", tooth_values[tooth_index])
            tooth_index += 1
            wheel = add_gear(axis_index, "wheel", tooth_values[tooth_index])
            tooth_index += 1
            meshes.append({"gear_a": previous_wheel, "gear_b": pinion})
            compound_pairs.append({"gear_a": pinion, "gear_b": wheel})
            previous_wheel = wheel
        branch_source = previous_wheel
        for axis_index in range(3, spec["arbor_count"]):
            pinion = add_gear(axis_index, "pinion", tooth_values[tooth_index])
            tooth_index += 1
            meshes.append({"gear_a": branch_source, "gear_b": pinion})
            if axis_index not in [int(axis[1:]) for axis in spec.get("outputs", [])]:
                wheel = add_gear(axis_index, "wheel", tooth_values[tooth_index])
                tooth_index += 1
                compound_pairs.append({"gear_a": pinion, "gear_b": wheel})
        if spec.get("disconnect_last_output"):
            meshes = meshes[:-1]
    else:
        previous_wheel = add_gear(0, "wheel", tooth_values[0])
        tooth_index = 1
        for axis_index in range(1, spec["arbor_count"]):
            pinion = add_gear(axis_index, "pinion", tooth_values[tooth_index])
            tooth_index += 1
            meshes.append({"gear_a": previous_wheel, "gear_b": pinion})
            if axis_index < spec["arbor_count"] - 1:
                wheel = add_gear(axis_index, "wheel", tooth_values[tooth_index])
                tooth_index += 1
                compound_pairs.append({"gear_a": pinion, "gear_b": wheel})
                previous_wheel = wheel

    bridges, screws = _bridge_and_screws(spec)
    supports = _supports_for_axes(spec, axes)
    return {
        "candidate_id": spec["candidate_id"],
        "topology_family": spec["topology_family"],
        "drive_axis": "a0",
        "axes": axes,
        "gears": gears,
        "meshes": meshes,
        "compound_pairs": compound_pairs,
        "outputs": [{"axis_id": axis_id, "hand_id": f"hand_{axis_id}"} for axis_id in spec["outputs"]],
        "supports": supports,
        "bridges": bridges,
        "screws": screws,
        "style_tags": spec.get("style_tags", []),
    }


def _axes_for_spec(spec: dict) -> list[dict]:
    axes = [{"axis_id": "a0", "x": 0.0, "y": 0.0, "role": "drive"}]
    directions = spec.get("directions") or [(1, 0), (0.7, 0.72), (0.9, -0.45), (0.55, 0.84), (0.8, -0.6)]
    tooth_values = spec["teeth"]
    module = 0.18
    if spec.get("branch"):
        # Build a visible trunk, then fan out the output axes from a shared source.
        trunk_count = min(3, spec["arbor_count"])
        for axis_index in range(1, trunk_count):
            previous_wheel_teeth = tooth_values[(axis_index - 1) * 2] if axis_index > 1 else tooth_values[0]
            pinion_teeth = tooth_values[(axis_index - 1) * 2 + 1]
            distance = module * (previous_wheel_teeth + pinion_teeth) / 2
            dx, dy = _unit(directions[axis_index - 1])
            axes.append(
                {
                    "axis_id": f"a{axis_index}",
                    "x": round(axes[-1]["x"] + dx * distance, 3),
                    "y": round(axes[-1]["y"] + dy * distance, 3),
                    "role": "intermediate",
                }
            )
        branch_source = axes[-1]
        branch_angles = [(0.9, -0.44), (-0.55, 0.83), (-0.8, -0.6), (0.2, 0.98)]
        tooth_index = 5 if trunk_count == 3 else 1
        for branch_number, axis_index in enumerate(range(trunk_count, spec["arbor_count"])):
            source_wheel_teeth = tooth_values[4] if trunk_count == 3 else tooth_values[0]
            pinion_teeth = tooth_values[min(tooth_index, len(tooth_values) - 1)]
            tooth_index += 1 if f"a{axis_index}" in set(spec["outputs"]) else 2
            distance = module * (source_wheel_teeth + pinion_teeth) / 2
            dx, dy = _unit(branch_angles[branch_number % len(branch_angles)])
            axes.append(
                {
                    "axis_id": f"a{axis_index}",
                    "x": round(branch_source["x"] + dx * distance, 3),
                    "y": round(branch_source["y"] + dy * distance, 3),
                    "role": "output",
                }
            )
    else:
        tooth_index = 1
        previous_wheel_teeth = tooth_values[0]
        for axis_index in range(1, spec["arbor_count"]):
            pinion_teeth = tooth_values[tooth_index]
            distance = module * (previous_wheel_teeth + pinion_teeth) / 2
            if spec.get("bad_mesh_distance") and axis_index == 1:
                distance += 1.3
            dx, dy = _unit(directions[(axis_index - 1) % len(directions)])
            axes.append(
                {
                    "axis_id": f"a{axis_index}",
                    "x": round(axes[-1]["x"] + dx * distance, 3),
                    "y": round(axes[-1]["y"] + dy * distance, 3),
                    "role": "output" if axis_index == spec["arbor_count"] - 1 else "intermediate",
                }
            )
            tooth_index += 1
            if axis_index < spec["arbor_count"] - 1:
                previous_wheel_teeth = tooth_values[tooth_index]
                tooth_index += 1
    output_ids = set(spec["outputs"])
    for axis in axes:
        if axis["axis_id"] in output_ids:
            axis["role"] = "output"
    return axes


def _unit(vector: tuple[float, float]) -> tuple[float, float]:
    x, y = vector
    length = hypot(x, y)
    if length == 0:
        return 1.0, 0.0
    return x / length, y / length


def _bridge_and_screws(spec: dict) -> tuple[list[dict], list[dict]]:
    bridges: list[dict] = []
    screws: list[dict] = []
    for bridge_index, axis_group in enumerate(spec["bridge_groups"], start=1):
        bridge_id = f"bridge_{bridge_index}"
        bridges.append({"bridge_id": bridge_id, "axis_ids": axis_group, "type": "TrainWheelBridge"})
        screw_count = 1 if spec.get("incomplete_bridge_screws") and bridge_index == 2 else 2
        for screw_index in range(1, screw_count + 1):
            screws.append(
                {
                    "screw_id": f"{bridge_id}_s{screw_index}",
                    "bridge_id": bridge_id,
                    "head_bearing_face": True,
                    "clearance_hole": True,
                    "receiving_feature": not (spec.get("incomplete_bridge_screws") and bridge_index == 2),
                }
            )
    return bridges, screws


def _supports_for_axes(spec: dict, axes: list[dict]) -> list[dict]:
    supports = []
    bridge_by_axis = {}
    for bridge_index, axis_group in enumerate(spec["bridge_groups"], start=1):
        for axis_id in axis_group:
            bridge_by_axis.setdefault(axis_id, f"bridge_{bridge_index}")
    for axis in axes:
        axis_id = axis["axis_id"]
        upper = axis_id != spec.get("missing_upper_support_axis")
        supports.append(
            {
                "axis_id": axis_id,
                "lower": True,
                "upper": upper,
                "lower_owner": "mainplate",
                "upper_owner": bridge_by_axis.get(axis_id),
            }
        )
    return supports


def _fill_pitch_radii(candidate: dict) -> None:
    for gear in candidate["gears"]:
        gear["pitch_radius"] = round(gear["module"] * gear["tooth_count"] / 2, 4)


def _fill_mesh_metadata(candidate: dict) -> None:
    gear_by_id = _gear_by_id(candidate)
    axis_by_id = _axis_by_id(candidate)
    for mesh in candidate["meshes"]:
        gear_a = gear_by_id[mesh["gear_a"]]
        gear_b = gear_by_id[mesh["gear_b"]]
        axis_a = axis_by_id[gear_a["axis_id"]]
        axis_b = axis_by_id[gear_b["axis_id"]]
        mesh["center_distance"] = round(hypot(axis_a["x"] - axis_b["x"], axis_a["y"] - axis_b["y"]), 4)
        mesh["target_center_distance"] = round(gear_a["pitch_radius"] + gear_b["pitch_radius"], 4)
        mesh["ratio"] = round(-gear_a["tooth_count"] / gear_b["tooth_count"], 6)


def _outputs_connected(candidate: dict, reasons: list[str]) -> bool:
    gears_by_axis = defaultdict(list)
    for gear in candidate["gears"]:
        gears_by_axis[gear["axis_id"]].append(gear["gear_id"])
    adjacency = defaultdict(set)
    for gear_ids in gears_by_axis.values():
        for gear_id in gear_ids:
            adjacency[gear_id].update(other for other in gear_ids if other != gear_id)
    for mesh in candidate["meshes"]:
        adjacency[mesh["gear_a"]].add(mesh["gear_b"])
        adjacency[mesh["gear_b"]].add(mesh["gear_a"])

    start_gears = gears_by_axis[candidate["drive_axis"]]
    visited = set(start_gears)
    queue = deque(start_gears)
    while queue:
        gear_id = queue.popleft()
        for next_gear in adjacency[gear_id]:
            if next_gear not in visited:
                visited.add(next_gear)
                queue.append(next_gear)
    ok = True
    for output in candidate["outputs"]:
        output_gears = set(gears_by_axis[output["axis_id"]])
        if not output_gears.intersection(visited):
            reasons.append("output_not_connected_to_drive")
            ok = False
    return ok


def _mesh_equations_satisfied(candidate: dict, reasons: list[str]) -> bool:
    gear_by_id = _gear_by_id(candidate)
    axis_by_id = _axis_by_id(candidate)
    ok = True
    for mesh in candidate["meshes"]:
        gear_a = gear_by_id[mesh["gear_a"]]
        gear_b = gear_by_id[mesh["gear_b"]]
        if gear_a["module"] != gear_b["module"]:
            reasons.append("mesh_module_mismatch")
            ok = False
        axis_a = axis_by_id[gear_a["axis_id"]]
        axis_b = axis_by_id[gear_b["axis_id"]]
        actual = hypot(axis_a["x"] - axis_b["x"], axis_a["y"] - axis_b["y"])
        target = gear_a["pitch_radius"] + gear_b["pitch_radius"]
        if abs(actual - target) > MESH_TOLERANCE_MM:
            reasons.append("mesh_center_distance_mismatch")
            ok = False
    return ok


def _compound_axes_satisfied(candidate: dict, reasons: list[str]) -> bool:
    gear_by_id = _gear_by_id(candidate)
    ok = True
    for pair in candidate["compound_pairs"]:
        if gear_by_id[pair["gear_a"]]["axis_id"] != gear_by_id[pair["gear_b"]]["axis_id"]:
            reasons.append("compound_axis_mismatch")
            ok = False
    return ok


def _all_arbors_supported(candidate: dict, reasons: list[str]) -> bool:
    support_by_axis = {support["axis_id"]: support for support in candidate["supports"]}
    ok = True
    for axis in candidate["axes"]:
        support = support_by_axis.get(axis["axis_id"])
        if not support or not support.get("lower"):
            reasons.append("missing_lower_support")
            ok = False
        if not support or not support.get("upper") or not support.get("upper_owner"):
            reasons.append("missing_upper_support")
            ok = False
    return ok


def _bridge_screws_complete(candidate: dict, reasons: list[str]) -> bool:
    screws_by_bridge = defaultdict(list)
    for screw in candidate["screws"]:
        screws_by_bridge[screw["bridge_id"]].append(screw)
    ok = True
    for bridge in candidate["bridges"]:
        screws = screws_by_bridge[bridge["bridge_id"]]
        if len(screws) < 2:
            reasons.append("bridge_has_fewer_than_two_screws")
            ok = False
        for screw in screws:
            if not (screw.get("head_bearing_face") and screw.get("clearance_hole") and screw.get("receiving_feature")):
                reasons.append("bridge_screw_interface_incomplete")
                ok = False
    return ok


def _summarize(candidates: list[dict]) -> dict:
    valid = [candidate for candidate in candidates if candidate["validation"]["status"] == "valid"]
    invalid_reasons = Counter(
        reason
        for candidate in candidates
        for reason in candidate["validation"]["reasons"]
    )
    return {
        "candidate_count": len(candidates),
        "valid_count": len(valid),
        "invalid_count": len(candidates) - len(valid),
        "topology_family_count": len({candidate["topology_family"] for candidate in valid}),
        "topology_families": sorted({candidate["topology_family"] for candidate in valid}),
        "arbor_count_values": sorted({len(candidate["axes"]) for candidate in valid}),
        "output_count_values": sorted({len(candidate["outputs"]) for candidate in valid}),
        "bridge_count_values": sorted({len(candidate["bridges"]) for candidate in valid}),
        "visual_style_values": sorted({tag for candidate in valid for tag in candidate["style_tags"]}),
        "invalid_reason_counts": dict(sorted(invalid_reasons.items())),
        "decision": _summary_decision(valid),
    }


def _summary_decision(valid: list[dict]) -> str:
    families = {candidate["topology_family"] for candidate in valid}
    arbors = {len(candidate["axes"]) for candidate in valid}
    outputs = {len(candidate["outputs"]) for candidate in valid}
    bridges = {len(candidate["bridges"]) for candidate in valid}
    if len(valid) >= 5 and len(families) >= 3 and len(arbors) >= 3 and len(outputs) >= 2 and len(bridges) >= 2:
        return "pass_for_pattern_card_regeneration"
    return "insufficient_diversity_or_validity"


def _render_dashboard(report: dict) -> str:
    summary = report["summary"]
    candidates = report["candidates"]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Watch Rule-Space Dashboard</title>
  <style>
    :root {{
      --ink: #202124;
      --muted: #5f6368;
      --line: #dadce0;
      --panel: #f8fafd;
      --blue: #1a73e8;
      --green: #137333;
      --red: #b3261e;
      --gold: #b06000;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      color: var(--ink);
      background: #fff;
      line-height: 1.5;
    }}
    header {{
      padding: 30px 38px 20px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #f8fbff, #ffffff);
    }}
    main {{ padding: 26px 38px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; letter-spacing: 0; }}
    h2 {{ margin: 30px 0 14px; font-size: 22px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 8px; font-size: 16px; letter-spacing: 0; }}
    p {{ margin: 0 0 10px; }}
    code {{ background: #f1f3f4; border-radius: 4px; padding: 1px 4px; }}
    .summary {{ max-width: 1080px; color: var(--muted); }}
    .metrics, .candidate-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 14px;
    }}
    .metric, .candidate {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 14px;
    }}
    .metric strong {{ display: block; font-size: 28px; }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 12px;
      border: 1px solid #aecbfa;
      color: #174ea6;
      background: #e8f0fe;
    }}
    .valid {{ border-color: #b7dfc0; }}
    .invalid {{ border-color: #f4c7c3; }}
    .badge.valid-label {{ border-color: #b7dfc0; color: var(--green); background: #e6f4ea; }}
    .badge.invalid-label {{ border-color: #f4c7c3; color: var(--red); background: #fce8e6; }}
    .map {{
      width: 100%;
      height: auto;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
      margin: 10px 0;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f1f3f4; }}
    ul {{ margin: 8px 0 0; padding-left: 18px; color: var(--muted); }}
  </style>
</head>
<body>
  <header>
    <h1>Gate A1.5：规则空间采样验证</h1>
    <p class="summary">这页验证形式化规则是否能产生变化多样的机械手表风格候选。当前只检查抽象传动图、2D 轴位、齿轮方程和装配语义，不生成 CAD，不声称候选已经是生产级机械表机芯。</p>
  </header>
  <main>
    <section>
      <h2>总体结论</h2>
      <div class="metrics">
        <div class="metric"><span class="badge">候选总数</span><strong>{summary["candidate_count"]}</strong></div>
        <div class="metric"><span class="badge valid-label">有效候选</span><strong>{summary["valid_count"]}</strong></div>
        <div class="metric"><span class="badge">拓扑家族</span><strong>{summary["topology_family_count"]}</strong></div>
        <div class="metric"><span class="badge">判定</span><strong style="font-size:18px">{escape(summary["decision"])}</strong></div>
      </div>
    </section>
    <section>
      <h2>多样性指标</h2>
      <table>
        <tr><th>指标</th><th>数值</th></tr>
        <tr><td>拓扑家族</td><td>{escape(", ".join(summary["topology_families"]))}</td></tr>
        <tr><td>轮轴数量变化</td><td>{escape(str(summary["arbor_count_values"]))}</td></tr>
        <tr><td>输出轴数量变化</td><td>{escape(str(summary["output_count_values"]))}</td></tr>
        <tr><td>桥板数量变化</td><td>{escape(str(summary["bridge_count_values"]))}</td></tr>
        <tr><td>视觉标签</td><td>{escape(", ".join(summary["visual_style_values"]))}</td></tr>
      </table>
    </section>
    <section>
      <h2>失败原因</h2>
      {_render_failure_table(summary["invalid_reason_counts"])}
    </section>
    <section>
      <h2>候选拓扑</h2>
      <div class="candidate-grid">
        {''.join(_render_candidate_card(candidate) for candidate in candidates)}
      </div>
    </section>
  </main>
</body>
</html>
"""


def _render_failure_table(reason_counts: dict) -> str:
    if not reason_counts:
        return "<p>没有失败候选。这个结果反而需要警惕，因为 sampler 应该能证明验证器会拒绝坏设计。</p>"
    rows = "".join(
        f"<tr><td><code>{escape(reason)}</code></td><td>{count}</td></tr>"
        for reason, count in reason_counts.items()
    )
    return f"<table><tr><th>失败原因</th><th>次数</th></tr>{rows}</table>"


def _render_candidate_card(candidate: dict) -> str:
    status = candidate["validation"]["status"]
    reasons = candidate["validation"]["reasons"] or ["通过全部 A1.5 抽象检查"]
    reason_items = "".join(f"<li>{escape(reason)}</li>" for reason in reasons)
    ratios = ", ".join(f"{mesh['gear_a']}->{mesh['gear_b']}: {mesh['ratio']}" for mesh in candidate["meshes"])
    return f"""
<article class="candidate {escape(status)}">
  <h3>{escape(candidate["candidate_id"])}</h3>
  <span class="badge {'valid-label' if status == 'valid' else 'invalid-label'}">{escape(status)}</span>
  <p><strong>家族：</strong>{escape(candidate["topology_family"])}</p>
  <p><strong>轮轴/输出/桥板：</strong>{len(candidate["axes"])} / {len(candidate["outputs"])} / {len(candidate["bridges"])}</p>
  {_render_svg(candidate)}
  <p><strong>速比片段：</strong>{escape(ratios)}</p>
  <ul>{reason_items}</ul>
</article>
"""


def _render_svg(candidate: dict) -> str:
    axes = candidate["axes"]
    if not axes:
        return ""
    xs = [axis["x"] for axis in axes]
    ys = [axis["y"] for axis in axes]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max(max_x - min_x, 1)
    height = max(max_y - min_y, 1)

    def map_point(axis_id: str) -> tuple[float, float]:
        axis = next(item for item in axes if item["axis_id"] == axis_id)
        x = 24 + (axis["x"] - min_x) / width * 202
        y = 146 - (axis["y"] - min_y) / height * 112
        return x, y

    gear_by_id = _gear_by_id(candidate)
    lines = []
    for mesh in candidate["meshes"]:
        a_axis = gear_by_id[mesh["gear_a"]]["axis_id"]
        b_axis = gear_by_id[mesh["gear_b"]]["axis_id"]
        x1, y1 = map_point(a_axis)
        x2, y2 = map_point(b_axis)
        lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#5f6368" stroke-width="2" />')
    output_axes = {output["axis_id"] for output in candidate["outputs"]}
    circles = []
    for axis in axes:
        x, y = map_point(axis["axis_id"])
        if axis["axis_id"] == candidate["drive_axis"]:
            color = "#b3261e"
        elif axis["axis_id"] in output_axes:
            color = "#1a73e8"
        else:
            color = "#137333"
        circles.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{color}" />'
            f'<text x="{x + 9:.1f}" y="{y - 8:.1f}" font-size="10" fill="#202124">{escape(axis["axis_id"])}</text>'
        )
    return f"""
<svg class="map" viewBox="0 0 250 170" role="img" aria-label="{escape(candidate['candidate_id'])} topology map">
  <rect x="10" y="10" width="230" height="150" rx="8" fill="#fff" stroke="#dadce0" />
  {''.join(lines)}
  {''.join(circles)}
</svg>
"""


def _gear_by_id(candidate: dict) -> dict:
    return {gear["gear_id"]: gear for gear in candidate["gears"]}


def _axis_by_id(candidate: dict) -> dict:
    return {axis["axis_id"]: axis for axis in candidate["axes"]}


if __name__ == "__main__":
    json_path, html_path = write_default_rule_space_artifacts()
    print(json_path)
    print(html_path)
