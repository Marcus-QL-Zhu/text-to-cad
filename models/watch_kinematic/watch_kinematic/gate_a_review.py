from __future__ import annotations

from html import escape
from pathlib import Path
import shutil

from .cases import load_watch_case
from .patterns import build_watch_pattern_cards


REPO_ROOT = Path(__file__).resolve().parents[3]
CASE_DIR = REPO_ROOT / "models" / "watch_kinematic" / "cases"
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "design_patterns"
    / "sprints"
    / "watch_kinematic_demo"
    / "gate_a_review.html"
)

REFERENCE_IMAGES = {
    "leap_style_balanced": {
        "label": "案例 1：右侧大螺旋，左侧低位输出轴",
        "target": "leap_style_balanced.png",
        "source": Path(
            "C:/Users/wande/AppData/Local/Temp/"
            "codex-clipboard-ba44939c-d1cd-46ed-893d-6c66bf0bba00.png"
        ),
    },
    "leap_style_low_dense": {
        "label": "案例 2：左下密集轮系，右侧大螺旋",
        "target": "leap_style_low_dense.png",
        "source": Path(
            "C:/Users/wande/AppData/Local/Temp/"
            "codex-clipboard-ee03f642-bd44-448a-b4b1-7c33b5120bec.png"
        ),
    },
    "leap_style_vertical_offset": {
        "label": "案例 3：上下错位的大输出轴布局",
        "target": "leap_style_vertical_offset.png",
        "source": Path(
            "C:/Users/wande/AppData/Local/Temp/"
            "codex-clipboard-f409a54c-59ff-4912-951a-646edc939a6e.png"
        ),
    },
}

CASE_FILENAMES = [
    "case_leap_style_balanced.json",
    "case_leap_style_low_dense.json",
    "case_leap_style_vertical_offset.json",
]


def write_gate_a_review(output_path: str | Path = DEFAULT_OUTPUT) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _copy_reference_images(target.parent)

    cases = [load_watch_case(CASE_DIR / filename) for filename in CASE_FILENAMES]
    cards = build_watch_pattern_cards()
    target.write_text(_render_html(cases, cards), encoding="utf-8")
    return target


def _copy_reference_images(output_dir: Path) -> None:
    image_dir = output_dir / "reference_images"
    image_dir.mkdir(parents=True, exist_ok=True)
    for image in REFERENCE_IMAGES.values():
        source = image["source"]
        if source.exists():
            shutil.copyfile(source, image_dir / image["target"])


def _render_html(cases: list[dict], cards: list[dict]) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Watch Kinematic Demo Gate A Review</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2328;
      --muted: #667085;
      --line: #d8dee8;
      --panel: #f8fafc;
      --blue: #2563eb;
      --green: #16803c;
      --gold: #b7791f;
      --red: #c2410c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      background: #ffffff;
      color: var(--ink);
      line-height: 1.55;
    }}
    header {{
      padding: 28px 36px 18px;
      border-bottom: 1px solid var(--line);
    }}
    main {{ padding: 26px 36px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; letter-spacing: 0; }}
    h2 {{ margin: 34px 0 14px; font-size: 22px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 10px; font-size: 16px; letter-spacing: 0; }}
    p {{ margin: 0 0 12px; }}
    .summary {{
      max-width: 1040px;
      color: var(--muted);
      font-size: 15px;
    }}
    .notice {{
      margin-top: 18px;
      max-width: 1040px;
      padding: 14px 16px;
      background: #fff7ed;
      border: 1px solid #fed7aa;
      border-radius: 8px;
      color: #7c2d12;
      font-weight: 600;
    }}
    .grid {{
      display: grid;
      gap: 18px;
    }}
    .case-grid {{
      grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
    }}
    .pattern-grid {{
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 16px;
    }}
    .case-img {{
      width: 100%;
      aspect-ratio: 1.38;
      object-fit: cover;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: #eef2f7;
      display: block;
    }}
    .axis-map {{
      width: 100%;
      height: auto;
      margin-top: 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
    }}
    .meta {{
      margin-top: 12px;
      font-size: 13px;
      color: var(--muted);
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      background: #e8f1ff;
      color: #1d4ed8;
      border: 1px solid #bfdbfe;
    }}
    .badge.draft {{
      background: #fff7ed;
      color: #9a3412;
      border-color: #fed7aa;
    }}
    .list {{
      margin: 8px 0 0;
      padding-left: 18px;
      color: var(--muted);
      font-size: 13px;
    }}
    .exclusion {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      max-width: 980px;
    }}
    .tag {{
      padding: 5px 9px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
    }}
    .legend {{
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .dot {{
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      margin-right: 5px;
    }}
    .drive {{ background: var(--red); }}
    .output {{ background: var(--blue); }}
    .case-note {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Gate A 审阅页：手表风格运动机构 Demo</h1>
    <p class="summary">这页把 JSON/Markdown 的工程语义翻译成可目视检查的材料：参考截图、三套 case 的轴位抽象、7 张 pattern card 的人话摘要，以及 V1 明确不做的机械表功能。</p>
    <div class="notice">当前目标不是真实机械表机芯，而是 watch-style kinematic mechanism demo：能看到表壳、主夹板、齿轮、桥板、螺钉、螺旋视觉件和多个输出指针轴。</div>
  </header>
  <main>
    <section>
      <h2>1. 三个参考案例与轴位抽象</h2>
      <div class="grid case-grid">
        {''.join(_render_case(case) for case in cases)}
      </div>
      <div class="legend">
        <span><span class="dot drive"></span>红点：输入/螺旋视觉驱动轴</span>
        <span><span class="dot output"></span>蓝点：输出指针轴</span>
      </div>
    </section>
    <section>
      <h2>2. V1 明确排除项</h2>
      <p class="summary">这些词必须继续出现在后续 validation/dashboard 里，避免视觉符号被误解为工程认证能力。</p>
      <div class="exclusion">
        {''.join(f'<span class="tag">{escape(item)}</span>' for item in cases[0]['excluded_systems'])}
      </div>
    </section>
    <section>
      <h2>3. Pattern Cards 人话版</h2>
      <div class="grid pattern-grid">
        {''.join(_render_pattern(card) for card in cards)}
      </div>
    </section>
  </main>
</body>
</html>
"""


def _render_case(case: dict) -> str:
    image = REFERENCE_IMAGES[case["case_id"]]
    outputs = "".join(
        f"<li><code>{escape(axis['id'])}</code> at {axis['anchor_xy_mm']}, ratio {axis['visible_speed_ratio']}</li>"
        for axis in case["output_axes"]
    )
    return f"""
<article class="card">
  <h3>{escape(image['label'])}</h3>
  <img class="case-img" src="reference_images/{escape(image['target'])}" alt="{escape(case['case_id'])} reference" />
  {_render_axis_svg(case)}
  <div class="meta">
    <p><strong>Case:</strong> <code>{escape(case['case_id'])}</code></p>
    <p><strong>Drive:</strong> <code>{escape(case['drive_axis']['id'])}</code> at {case['drive_axis']['anchor_xy_mm']}</p>
    <ul class="list">{outputs}</ul>
  </div>
  <p class="case-note">这不是最终 CAD，只是把参考图中的视觉布局压缩成后续 synthesis 可用的输入边界。</p>
</article>
"""


def _render_axis_svg(case: dict) -> str:
    def map_xy(point: list[float]) -> tuple[float, float]:
        scale = 4.2
        return 120 + point[0] * scale, 120 - point[1] * scale

    drive_x, drive_y = map_xy(case["drive_axis"]["anchor_xy_mm"])
    output_nodes = []
    for axis in case["output_axes"]:
        x, y = map_xy(axis["anchor_xy_mm"])
        output_nodes.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#2563eb" />'
            f'<text x="{x + 10:.1f}" y="{y - 8:.1f}" font-size="9" fill="#1f2328">{escape(axis["id"])}</text>'
        )
    return f"""
<svg class="axis-map" viewBox="0 0 240 240" role="img" aria-label="{escape(case['case_id'])} axis map">
  <circle cx="120" cy="120" r="92" fill="#fffdf5" stroke="#c4a15a" stroke-width="10" />
  <circle cx="120" cy="120" r="72" fill="#ffffff" stroke="#d8dee8" stroke-width="1" />
  <line x1="28" y1="120" x2="212" y2="120" stroke="#edf0f5" />
  <line x1="120" y1="28" x2="120" y2="212" stroke="#edf0f5" />
  <circle cx="{drive_x:.1f}" cy="{drive_y:.1f}" r="8" fill="#c2410c" />
  <text x="{drive_x + 10:.1f}" y="{drive_y + 12:.1f}" font-size="9" fill="#1f2328">{escape(case['drive_axis']['id'])}</text>
  {''.join(output_nodes)}
</svg>
"""


def _render_pattern(card: dict) -> str:
    badge_class = "draft" if card["lifecycle_state"] == "draft_pattern" else ""
    checks = "".join(f"<li>{escape(item)}</li>" for item in card["validation_checks"][:3])
    failures = "".join(f"<li>{escape(item)}</li>" for item in card["known_failure_modes"][:2])
    return f"""
<article class="card">
  <h3>{escape(card['name'])}</h3>
  <span class="badge {badge_class}">{escape(card['lifecycle_state'])}</span>
  <p class="meta"><code>{escape(card['id'])}</code></p>
  <p>{escape(card['solved_function'])}</p>
  <p><strong>后续会生成/约束：</strong>{escape(', '.join(card['generated_components'][:4]))}</p>
  <p><strong>验证重点：</strong></p>
  <ul class="list">{checks}</ul>
  <p><strong>常见失败：</strong></p>
  <ul class="list">{failures}</ul>
</article>
"""


if __name__ == "__main__":
    print(write_gate_a_review())
