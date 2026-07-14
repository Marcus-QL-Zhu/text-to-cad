from pathlib import Path
from typing import Any

from .solver import MAINPLATE_RADIUS_MM, solve_independent_display_layout


def write_independent_display_review(output_dir: Path, *, seed: int = 731) -> Path:
    """Write a Gate 1 2D HTML review for independent display branches."""

    output_dir.mkdir(parents=True, exist_ok=True)
    report = solve_independent_display_layout(seed=seed)
    html_path = output_dir / "independent_display_2d_review.html"
    html_path.write_text(_render_independent_display_review_html(report), encoding="utf-8")
    return html_path


def _render_independent_display_review_html(report: dict[str, Any]) -> str:
    candidate = report["selected_candidate"]
    if candidate is None:
        raise ValueError("independent display solver did not find a passing candidate")

    scale = 11.0
    center = 280.0

    def sx(x: float) -> float:
        return center + x * scale

    def sy(y: float) -> float:
        return center - y * scale

    labels = {
        "movement_geometric_center": ("geom center", -10, 18),
        "barrel_axis": ("barrel", -42, 18),
        "train_stage_1_axis": ("train 1", 8, -16),
        "train_stage_2_axis": ("train 2", 8, -16),
        "train_stage_3_axis": ("train 3 / branch source", 8, 18),
        "escape_axis": ("escape", 8, -14),
        "pallet_axis": ("pallet", 8, -14),
        "balance_axis": ("balance", 8, -14),
        "minute_input_relay_axis": ("minute input", -80, -24),
        "minute_display_axis": ("minute axis", 16, 32),
        "hour_input_relay_axis": ("hour input", 18, 28),
        "hour_reduction_relay_axis": ("hour relay", -92, -26),
        "hour_display_axis": ("hour axis", 18, -34),
        "minute_input_relay_pinion": ("m pinion", -76, -18),
        "minute_input_relay_wheel": ("m relay", -72, 10),
        "minute_display_member": ("m output", 14, 44),
        "hour_input_relay_pinion": ("h pinion", 16, 46),
        "hour_input_relay_wheel": ("h input wheel", 16, 62),
        "hour_reduction_relay_pinion": ("h relay pinion", -110, -28),
        "hour_reduction_relay_wheel": ("h relay wheel", -108, -12),
        "hour_display_member": ("hour wheel", 14, -38),
    }

    def label_svg(label_id: str, x: float, y: float) -> str:
        text, dx, dy = labels.get(label_id, (label_id, 6, -6))
        return f'<text x="{x + dx:.2f}" y="{y + dy:.2f}" class="small"><title>{label_id}</title>{text}</text>'

    axes = candidate["axes"]
    axis_by_id = {axis["axis_id"]: axis for axis in axes}

    axis_marks = []
    for axis in axes:
        x = sx(axis["x"])
        y = sy(axis["y"])
        css_class = "axis"
        if axis["axis_id"].startswith("minute"):
            css_class = "axis minute-axis"
        elif axis["axis_id"].startswith("hour"):
            css_class = "axis hour-axis"
        axis_marks.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" class="{css_class}"><title>{axis["axis_id"]}</title></circle>'
            f'{label_svg(axis["axis_id"], x, y)}'
        )

    gear_circles = []
    for gear in candidate["display_gears"]:
        x = sx(gear["x"])
        y = sy(gear["y"])
        css_class = "pitch minute-pitch" if gear["branch_id"] == "minute_branch" else "pitch hour-pitch"
        gear_circles.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{gear["pitch_radius"] * scale:.2f}" class="{css_class}" />'
            f'{label_svg(gear["gear_id"], x, y)}'
        )

    mesh_lines = []
    for mesh in candidate["display_meshes"]:
        if mesh["driver"] == "train_stage_3_wheel":
            left_axis = axis_by_id["train_stage_3_axis"]
        else:
            left_gear = next(gear for gear in candidate["display_gears"] if gear["gear_id"] == mesh["driver"])
            left_axis = axis_by_id[left_gear["axis_id"]]
        right_gear = next(gear for gear in candidate["display_gears"] if gear["gear_id"] == mesh["driven"])
        right_axis = axis_by_id[right_gear["axis_id"]]
        css_class = "mesh minute-mesh" if mesh["branch_id"] == "minute_display_branch" else "mesh hour-mesh"
        mesh_lines.append(
            f'<line x1="{sx(left_axis["x"]):.2f}" y1="{sy(left_axis["y"]):.2f}" '
            f'x2="{sx(right_axis["x"]):.2f}" y2="{sy(right_axis["y"]):.2f}" class="{css_class}" />'
        )

    sweeps = []
    for envelope in candidate["sweep_envelopes"].values():
        css_class = "sweep minute-sweep" if envelope["hand_id"] == "minute_hand" else "sweep hour-sweep"
        sweeps.append(
            f'<circle cx="{sx(envelope["x"]):.2f}" cy="{sy(envelope["y"]):.2f}" '
            f'r="{envelope["radius_mm"] * scale:.2f}" class="{css_class}" />'
        )

    checks = "\n".join(
        f"<li>{check_id}: <strong>{status}</strong></li>"
        for check_id, status in candidate["checks"].items()
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Independent Hour/Minute No-Seconds 2D Review</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; background: #f7fafc; }}
    svg {{ background: #ffffff; border: 1px solid #cbd5df; border-radius: 8px; }}
    .mainplate {{ fill: #edf2f7; stroke: #8da2b5; stroke-width: 2; }}
    .construction {{ fill: #ffffff; stroke: #e11d48; stroke-width: 2; }}
    .axis {{ fill: #4a5568; stroke: #1a202c; stroke-width: 1; }}
    .minute-axis {{ fill: #1f78b4; }}
    .hour-axis {{ fill: #9b2c2c; }}
    .pitch {{ stroke-width: 1.5; }}
    .minute-pitch {{ fill: rgba(49,130,206,0.16); stroke: #3182ce; }}
    .hour-pitch {{ fill: rgba(221,107,32,0.16); stroke: #dd6b20; }}
    .mesh {{ stroke-width: 2; stroke-dasharray: 5 3; }}
    .minute-mesh {{ stroke: #3182ce; }}
    .hour-mesh {{ stroke: #dd6b20; }}
    .sweep {{ fill: none; stroke-width: 1; stroke-dasharray: 5 4; }}
    .minute-sweep {{ stroke: #3182ce; }}
    .hour-sweep {{ stroke: #dd6b20; }}
    .small {{ font-size: 11px; fill: #293846; }}
  </style>
</head>
<body>
  <h1>Independent Hour/Minute No-Seconds 2D Review</h1>
  <p>hour branch independent from minute branch; both start from train_stage_3_wheel. No seconds hand is generated.</p>
  <svg width="560" height="560" viewBox="0 0 560 560" role="img" aria-label="2D independent display solver review">
    <circle cx="{center}" cy="{center}" r="{MAINPLATE_RADIUS_MM * scale:.2f}" class="mainplate" />
    <circle cx="{center}" cy="{center}" r="5" class="construction" />
    {label_svg("movement_geometric_center", center, center)}
    {''.join(sweeps)}
    {''.join(mesh_lines)}
    {''.join(gear_circles)}
    {''.join(axis_marks)}
  </svg>
  <h2>Checks</h2>
  <ul>{checks}</ul>
  <h2>Ratio</h2>
  <p>Branches: minute_display_branch and hour_display_branch are solved as parallel display branches.</p>
  <p>Minute: {candidate["display_ratio_proof"]["minute_tooth_relation"]}</p>
  <p>Hour: {candidate["display_ratio_proof"]["hour_tooth_relation"]}</p>
</body>
</html>
"""
