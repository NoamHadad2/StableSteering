from __future__ import annotations

from pathlib import Path

import markdown


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = REPO_ROOT / "paper"
SOURCE = PAPER_ROOT / "journal_manuscript.md"
OUTPUT = PAPER_ROOT / "journal_manuscript.html"


def build_html() -> str:
    source_text = SOURCE.read_text(encoding="utf-8")
    body = markdown.markdown(
        source_text,
        extensions=["extra", "toc", "sane_lists", "tables", "fenced_code", "md_in_html"],
        output_format="html5",
    )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>StableSteering Journal Manuscript</title>
    <script>
      window.MathJax = {{
        tex: {{
          inlineMath: [['\\\\(', '\\\\)'], ['$', '$']],
          displayMath: [['\\\\[', '\\\\]'], ['$$', '$$']]
        }},
        svg: {{
          fontCache: 'global'
        }}
      }};
    </script>
    <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
    <style>
      :root {{
        --bg: #f1ebe2;
        --paper: #fffdfa;
        --text: #1f1b17;
        --muted: #6f6253;
        --border: #d9cdbc;
        --accent: #7b4411;
        --table: #faf6ef;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background: radial-gradient(circle at top, #f6f0e7, #eee6da 68%);
        color: var(--text);
        font-family: Georgia, "Times New Roman", serif;
      }}
      main {{ max-width: 1040px; margin: 0 auto; padding: 28px 20px 48px; }}
      article {{
        background: var(--paper);
        border: 1px solid var(--border);
        border-radius: 18px;
        box-shadow: 0 16px 44px rgba(62, 40, 16, 0.08);
        padding: 40px 46px 56px;
      }}
      h1, h2, h3 {{ color: #17130f; line-height: 1.2; }}
      h1 {{ font-size: 2.1rem; margin-bottom: 0.4rem; }}
      h2 {{ font-size: 1.45rem; margin-top: 2rem; }}
      h3 {{ font-size: 1.08rem; margin-top: 1.4rem; }}
      p, li {{ font-size: 1.04rem; line-height: 1.72; text-align: justify; text-justify: inter-word; }}
      figcaption {{ text-align: justify; text-justify: inter-word; }}
      figure {{ margin: 1.8rem auto; text-align: center; }}
      figure img {{ max-width: 100%; border: 1px solid var(--border); border-radius: 14px; background: white; }}
      figcaption {{ margin-top: 0.8rem; font-size: 0.96rem; line-height: 1.55; color: #40352b; }}
      table {{ width: 100%; border-collapse: collapse; margin: 1rem 0 1.4rem; background: var(--table); }}
      th, td {{ border: 1px solid var(--border); padding: 0.7rem 0.78rem; text-align: left; vertical-align: top; }}
      th {{ background: #f2e8da; }}
      blockquote {{ margin: 1.2rem 0; padding: 0.8rem 1rem; border-left: 4px solid var(--accent); background: #f7f1e8; }}
      code, pre {{ font-family: Consolas, "Courier New", monospace; }}
      pre {{ background: #f6f0e8; border: 1px solid var(--border); border-radius: 10px; padding: 0.9rem; overflow-x: auto; }}
      .equation {{
        margin: 1.2rem auto 1.35rem;
        padding: 0.8rem 1rem;
        background: #f8f4ee;
        border: 1px solid var(--border);
        border-radius: 14px;
        overflow-x: auto;
      }}
      mjx-container[jax="SVG"] {{
        margin: 0.35rem 0 !important;
        text-align: center !important;
      }}
      .toc {{ background: #f6efe5; border: 1px solid var(--border); border-radius: 14px; padding: 1rem 1.2rem; margin: 1.4rem 0 2rem; }}
      @media (max-width: 760px) {{
        article {{ padding: 22px 18px 30px; }}
        main {{ padding: 12px 10px 24px; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <article>{body}</article>
    </main>
  </body>
</html>
"""


def main() -> int:
    OUTPUT.write_text(build_html(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
