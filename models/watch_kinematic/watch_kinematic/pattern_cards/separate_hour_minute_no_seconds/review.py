from pathlib import Path
from typing import Any

from .solver import MAINPLATE_RADIUS_MM, solve_separate_display_layout

def write_separate_display_review(output_dir: Path, *, seed: int = 731) -> Path:
    """Write a Gate 1 2D HTML review for the separated display solver."""

    output_dir.mkdir(parents=True, exist_ok=True)
    report = solve_separate_display_layout(seed=seed)
    html_path = output_dir / "separate_display_2d_review.html"
    html_path.write_text(_render_separate_display_review_html(report), encoding="utf-8")
    return html_path

def _render_separate_display_review_html(report: dict[str, Any]) -> str:
    candidate = report["selected_candidate"]
    axes = {axis["axis_id"]: axis for axis in candidate["axes"]}
    scale = 11.0
    center = 260.0

    def sx(x: float) -> float:
        return center + x * scale

    def sy(y: float) -> float:
        return center - y * scale

    visible_labels = {
        "movement_geometric_center": ("geom center", -6, 18),
        "display_input_relay_pinion": ("input pinion", 22, -22),
        "display_input_relay_wheel": ("input wheel", 22, 6),
        "minute_display_member": ("minute wheel", 16, 46),
        "display_relay_pinion": ("relay pinion", 28, -22),
        "display_relay_wheel": ("relay wheel", 28, 4),
        "hour_display_member": ("hour wheel", 18, -36),
        "barrel_axis": ("barrel", -34, 18),
        "train_stage_1_axis": ("train 1", 8, -16),
        "train_stage_2_axis": ("train 2", 8, -16),
        "train_stage_3_axis": ("train 3", 8, 18),
        "escape_axis": ("escape", 8, -14),
        "pallet_axis": ("pallet", 8, -14),
        "balance_axis": ("balance", 8, -14),
        "display_input_relay_axis": ("input relay", 20, 28),
        "minute_display_axis": ("minute axis", 18, 26),
        "display_relay_axis": ("relay axis", 30, 18),
        "hour_display_axis": ("hour axis", 20, -52),
    }

    def label_svg(label_id: str, x: float, y: float) -> str:
        text, dx, dy = visible_labels.get(label_id, (label_id, 6, -6))
        return f'<text x="{x + dx:.2f}" y="{y + dy:.2f}" class="small"><title>{label_id}</title>{text}</text>'

    construction_label = label_svg("movement_geometric_center", center, center)
    gear_circles = []
    for gear in candidate["display_gears"]:
        x = sx(gear["x"])
        y = sy(gear["y"])
        gear_circles.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{gear["pitch_radius"] * scale:.2f}" '
            f'class="pitch" />{label_svg(gear["gear_id"], x, y)}'
        )
    axis_marks = []
    for axis in candidate["axes"]:
        x = sx(axis["x"])
        y = sy(axis["y"])
        axis_marks.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" class="axis"><title>{axis["axis_id"]}</title></circle>'
            f'{label_svg(axis["axis_id"], x, y)}'
        )
    sweeps = []
    for envelope in candidate["sweep_envelopes"].values():
        sweeps.append(
            f'<circle cx="{sx(envelope["x"]):.2f}" cy="{sy(envelope["y"]):.2f}" r="{envelope["radius_mm"] * scale:.2f}" class="sweep" />'
        )

    checks = "\n".join(
        f"<li>{check_id}: <strong>{status}</strong></li>"
        for check_id, status in candidate["checks"].items()
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Separate Hour/Minute No-Seconds 2D Review</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; background: #f7fafc; }}
    svg {{ background: #ffffff; border: 1px solid #cbd5df; border-radius: 8px; }}
    .mainplate {{ fill: #edf2f7; stroke: #8da2b5; stroke-width: 2; }}
    .construction {{ fill: #ffffff; stroke: #e11d48; stroke-width: 2; }}
    .axis {{ fill: #1f78b4; stroke: #0f3552; stroke-width: 1; }}
    .pitch {{ fill: rgba(201,154,58,0.18); stroke: #c99a3a; stroke-width: 1.5; }}
    .sweep {{ fill: rgba(99,179,237,0.10); stroke: #3182ce; stroke-width: 1; stroke-dasharray: 5 4; }}
    .small {{ font-size: 11px; fill: #293846; }}
  </style>
</head>
<body>
  <h1>Separate Hour/Minute No-Seconds 2D Review</h1>
  <p>movement_geometric_center is a construction reference only. No seconds hand is generated.</p>
  <svg width="520" height="520" viewBox="0 0 520 520" role="img" aria-label="2D separate display solver review">
    <circle cx="{center}" cy="{center}" r="{MAINPLATE_RADIUS_MM * scale:.2f}" class="mainplate" />
    <circle cx="{center}" cy="{center}" r="5" class="construction" />
    {construction_label}
    {''.join(sweeps)}
    {''.join(gear_circles)}
    {''.join(axis_marks)}
  </svg>
  <h2>Checks</h2>
  <ul>{checks}</ul>
  <h2>Ratio</h2>
  <p>{candidate["display_ratio_proof"]["tooth_relation"]}</p>
  <p>No seconds hand</p>
</body>
</html>
"""
