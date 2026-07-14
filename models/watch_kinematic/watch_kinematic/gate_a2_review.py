from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path

from .patterns import build_watch_pattern_cards


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "design_patterns"
    / "sprints"
    / "watch_kinematic_demo"
    / "gate_a2_review.html"
)


def write_gate_a2_review(output_path: str | Path = DEFAULT_OUTPUT) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    cards = build_watch_pattern_cards()
    target.write_text(_render_html(cards), encoding="utf-8")
    return target


def _render_html(cards: list[dict]) -> str:
    class_counts = Counter(card["pattern_class"] for card in cards)
    evidence_counts = Counter(
        source["type"]
        for card in cards
        for source in card["evidence_sources"]
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Gate A2 Watch Pattern Cards Review</title>
  <style>
    :root {{
      --ink: #202124;
      --muted: #5f6368;
      --line: #dadce0;
      --panel: #f8fafd;
      --blue: #1a73e8;
      --green: #137333;
      --amber: #b06000;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      color: var(--ink);
      background: #fff;
      line-height: 1.55;
    }}
    header {{
      padding: 30px 38px 20px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #f8fbff, #ffffff);
    }}
    main {{ padding: 26px 38px 52px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; letter-spacing: 0; }}
    h2 {{ margin: 30px 0 14px; font-size: 22px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 8px; font-size: 16px; letter-spacing: 0; }}
    p {{ margin: 0 0 10px; }}
    code {{ background: #f1f3f4; border-radius: 4px; padding: 1px 4px; }}
    .summary {{ max-width: 1120px; color: var(--muted); }}
    .notice {{
      margin-top: 16px;
      padding: 14px 16px;
      border: 1px solid #f9ab00;
      background: #fff8e1;
      border-radius: 8px;
      max-width: 1120px;
      font-weight: 600;
    }}
    .metrics, .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 14px;
    }}
    .metric, .card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 15px;
    }}
    .metric strong {{ display: block; font-size: 26px; }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      border: 1px solid #aecbfa;
      color: #174ea6;
      background: #e8f0fe;
      margin-bottom: 8px;
    }}
    .engineering {{ border-color: #b7dfc0; }}
    .visual {{ border-color: #fdd663; }}
    .evidence {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 8px 0;
    }}
    .pill {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 8px;
      background: #fff;
      font-size: 12px;
    }}
    ul {{ margin: 8px 0 0; padding-left: 18px; color: var(--muted); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f1f3f4; }}
  </style>
</head>
<body>
  <header>
    <h1>Gate A2：文献驱动 Pattern Cards 审阅</h1>
    <p class="summary">这页只审阅 pattern cards 的工程语义来源：工程类 pattern 必须来自手表文献、A1 形式化模型和 A1.5 规则空间采样；截图只能作为视觉风格证据，不能作为工程规则主证据。</p>
    <div class="notice">如果这一页通过，下一步才允许进入 synthesis package 和候选搜索。当前仍不生成 STEP，也不声称完整机械表机芯能力。</div>
  </header>
  <main>
    <section>
      <h2>总体结构</h2>
      <div class="metrics">
        <div class="metric"><span class="badge">Pattern Cards</span><strong>{len(cards)}</strong></div>
        <div class="metric"><span class="badge">工程类</span><strong>{class_counts["executable_engineering_pattern"]}</strong></div>
        <div class="metric"><span class="badge">视觉类</span><strong>{class_counts["visual_style_pattern"]}</strong></div>
        <div class="metric"><span class="badge">证据类型</span><strong>{len(evidence_counts)}</strong></div>
      </div>
    </section>
    <section>
      <h2>证据类型分布</h2>
      {_render_evidence_table(evidence_counts)}
    </section>
    <section>
      <h2>Pattern Cards</h2>
      <div class="grid">
        {''.join(_render_card(card) for card in cards)}
      </div>
    </section>
  </main>
</body>
</html>
"""


def _render_evidence_table(evidence_counts: Counter) -> str:
    rows = "".join(
        f"<tr><td><code>{escape(kind)}</code></td><td>{count}</td></tr>"
        for kind, count in sorted(evidence_counts.items())
    )
    return f"<table><tr><th>证据类型</th><th>引用次数</th></tr>{rows}</table>"


def _render_card(card: dict) -> str:
    card_class = "engineering" if card["pattern_class"] == "executable_engineering_pattern" else "visual"
    evidence = "".join(
        f'<span class="pill">{escape(source["id"])} / {escape(source["type"])}</span>'
        for source in card["evidence_sources"]
    )
    formal_refs = "".join(f"<li>{escape(item)}</li>" for item in card["formal_model_refs"][:4])
    rule_refs = "".join(f"<li>{escape(item)}</li>" for item in card["rule_space_refs"])
    checks = "".join(f"<li>{escape(item)}</li>" for item in card["validation_checks"][:3])
    return f"""
<article class="card {card_class}">
  <h3>{escape(card["name"])}</h3>
  <span class="badge">{escape(card["pattern_class"])}</span>
  <p><code>{escape(card["id"])}</code></p>
  <p>{escape(card["solved_function"])}</p>
  <div class="evidence">{evidence}</div>
  <p><strong>形式化引用</strong></p>
  <ul>{formal_refs}</ul>
  <p><strong>A1.5 规则空间证据</strong></p>
  <ul>{rule_refs}</ul>
  <p><strong>验证重点</strong></p>
  <ul>{checks}</ul>
</article>
"""


if __name__ == "__main__":
    print(write_gate_a2_review())
