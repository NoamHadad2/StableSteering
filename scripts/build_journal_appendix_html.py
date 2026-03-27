from __future__ import annotations

from pathlib import Path

import markdown


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = REPO_ROOT / "paper"
SOURCE = PAPER_ROOT / "journal_appendix.md"
OUTPUT = PAPER_ROOT / "journal_appendix.html"


def build_html() -> str:
    source_text = SOURCE.read_text(encoding="utf-8")
    body = markdown.markdown(
        source_text,
        extensions=["extra", "tables", "sane_lists"],
        output_format="html5",
    )
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
    <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
    <style>
      body {{ margin: 0; background: #f3ece2; color: #201a15; font-family: Georgia, "Times New Roman", serif; }}
      main {{ max-width: 960px; margin: 0 auto; padding: 28px 18px 48px; }}
      article {{ background: #fffdfa; border: 1px solid #d9cdbc; border-radius: 18px; padding: 34px 38px 42px; }}
      h1, h2, h3 {{ line-height: 1.2; }}
      p, li {{ line-height: 1.68; font-size: 1.03rem; text-align: justify; text-justify: inter-word; }}
      table {{ width: 100%; border-collapse: collapse; margin: 1rem 0 1.3rem; }}
      th, td {{ border: 1px solid #d9cdbc; padding: 0.7rem 0.78rem; text-align: left; vertical-align: top; }}
      th {{ background: #f2e8da; }}
      .equation {{ margin: 1rem 0; padding: 0.8rem 1rem; background: #f8f4ee; border: 1px solid #d9cdbc; border-radius: 14px; overflow-x: auto; }}
      mjx-container[jax="SVG"] {{ margin: 0.35rem 0 !important; text-align: center !important; }}
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
