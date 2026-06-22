from __future__ import annotations

import re
from pathlib import Path

import markdown


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = REPO_ROOT / "paper"
SOURCE = PAPER_ROOT / "journal_appendix.md"
OUTPUT = PAPER_ROOT / "journal_appendix.html"
MATHJAX_LOCAL = "assets/mathjax/tex-svg.js"


def _wrap_title_block(html: str) -> str:
    pattern = re.compile(r'(<h1[^>]*>.*?</h1>)', re.DOTALL)
    return pattern.sub(r'<section class="title-block">\1</section>', html, count=1)


def build_html() -> str:
    source_text = SOURCE.read_text(encoding="utf-8")
    body = markdown.markdown(
        source_text,
        extensions=["extra", "tables", "sane_lists"],
        output_format="html5",
    )
    body = _wrap_title_block(body)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>StableSteering Appendix</title>
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
    <script defer src="{MATHJAX_LOCAL}"></script>
    <style>
      :root {{
        --paper: #fffdfa;
        --bg: #efe8dd;
        --text: #201a15;
        --border: #d9cdbc;
        --table: #faf6ef;
      }}
      body {{ margin: 0; background: linear-gradient(180deg, #f5efe7 0%, #ece3d7 100%); color: var(--text); font-family: Georgia, "Times New Roman", serif; }}
      main {{ max-width: 980px; margin: 0 auto; padding: 30px 18px 52px; }}
      article {{ background: var(--paper); border: 1px solid var(--border); border-radius: 10px; padding: 44px 56px 54px; hyphens: auto; box-shadow: 0 18px 42px rgba(62, 40, 16, 0.08); }}
      .title-block {{ border-bottom: 1px solid #dfd2c0; margin-bottom: 1.6rem; }}
      .title-block h1 {{ margin: 0 0 1rem; text-align: center; font-size: 1.95rem; line-height: 1.15; }}
      h1, h2, h3 {{ line-height: 1.2; }}
      h2 {{ margin-top: 2rem; margin-bottom: 0.6rem; font-size: 1.34rem; }}
      h3 {{ margin-top: 1.45rem; margin-bottom: 0.45rem; font-size: 1.06rem; }}
      p, li {{ line-height: 1.68; font-size: 1.02rem; text-align: justify; text-justify: inter-word; }}
      p {{ margin: 0; }}
      p + p {{ text-indent: 1.6em; margin-top: 0.1rem; }}
      h1 + p, h2 + p, h3 + p, table + p, .equation + p {{ text-indent: 0; }}
      ul, ol {{ margin: 0.5rem 0 1rem 1.5rem; padding: 0; }}
      table {{ width: 100%; border-collapse: collapse; margin: 1rem 0 1.3rem; background: var(--table); }}
      th, td {{
        border: 1px solid var(--border);
        padding: 0.7rem 0.78rem;
        text-align: left;
        vertical-align: top;
        overflow-wrap: anywhere;
        word-break: normal;
        hyphens: auto;
        line-height: 1.46;
      }}
      th {{ background: #f2e8da; font-weight: 700; }}
      code {{
        white-space: normal;
        overflow-wrap: anywhere;
        word-break: break-word;
        font-size: 0.94em;
      }}
      .equation {{ margin: 1rem 0 1.15rem; padding: 0.95rem 1.1rem; background: #f8f4ee; border: 1px solid var(--border); border-radius: 8px; overflow-x: auto; box-shadow: inset 0 1px 0 rgba(255,255,255,0.6); }}
      .equation p {{ margin: 0; text-indent: 0; }}
      mjx-container[jax="SVG"] {{ margin: 0.4rem 0 !important; text-align: center !important; font-size: 108% !important; }}
      mjx-container[jax="SVG"] > svg {{ max-width: 100%; height: auto !important; }}
      table mjx-container[jax="SVG"] {{ margin: 0 !important; display: inline-block !important; font-size: 96% !important; vertical-align: middle; }}
      @media (max-width: 760px) {{
        article {{ padding: 24px 20px 34px; }}
        .title-block h1 {{ font-size: 1.55rem; }}
      }}
    </style>
  </head>
  <body>
    <main><article>{body}</article></main>
  </body>
</html>
"""


def main() -> int:
    OUTPUT.write_text(build_html(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
