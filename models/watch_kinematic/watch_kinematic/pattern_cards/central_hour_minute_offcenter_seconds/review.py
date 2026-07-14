import json
from pathlib import Path

from .solver import solve_current_pattern_layout


def write_current_pattern_review(output_dir: str | Path, *, seed: int = 731) -> Path:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    report = solve_current_pattern_layout(seed=seed)
    candidate = report.get("selected_candidate") or {}
    axes = candidate.get("axes", [])
    path = target / "central_hour_minute_offcenter_seconds_2d_review.html"
    axis_rows = "\n".join(
        f"<tr><td>{axis['axis_id']}</td><td>{axis['x']:.3f}</td><td>{axis['y']:.3f}</td><td>{axis['role']}</td></tr>"
        for axis in axes
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Central Hour/Minute Off-Center Seconds Review</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; }}
    td, th {{ border: 1px solid #d8dee8; padding: 6px 8px; text-align: left; }}
    th {{ background: #eef3f8; }}
    code {{ background: #eef3f8; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Central Hour/Minute Off-Center Seconds Review</h1>
  <p>Pattern: <code>{report['pattern_card_id']}</code></p>
  <p>Status: <code>{report['status']}</code>, seed: <code>{seed}</code></p>
  <h2>Axes</h2>
  <table>
    <thead><tr><th>Axis</th><th>X</th><th>Y</th><th>Role</th></tr></thead>
    <tbody>{axis_rows}</tbody>
  </table>
  <script type="application/json" id="solver-report">{json.dumps(report)}</script>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
    return path
