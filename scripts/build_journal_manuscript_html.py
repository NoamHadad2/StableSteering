from __future__ import annotations

import re
from pathlib import Path

import markdown


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = REPO_ROOT / "paper"
SOURCE = PAPER_ROOT / "journal_manuscript.md"
APPENDIX_SOURCE = PAPER_ROOT / "journal_appendix.md"
OUTPUT = PAPER_ROOT / "journal_manuscript.html"
MATHJAX_LOCAL = "assets/mathjax/tex-svg.js"


def _wrap_abstract_block(html: str) -> str:
    pattern = re.compile(r'(<h2[^>]*>\s*Abstract\s*</h2>\s*<p>.*?</p>)', re.DOTALL)
    return pattern.sub(r'<section class="abstract">\1</section>', html, count=1)


def build_html() -> str:
    source_text = SOURCE.read_text(encoding="utf-8")
    appendix_text = APPENDIX_SOURCE.read_text(encoding="utf-8")
    manuscript_body = markdown.markdown(
        source_text,
        extensions=["extra", "toc", "sane_lists", "tables", "fenced_code", "md_in_html"],
        output_format="html5",
    )
    appendix_body = markdown.markdown(
        appendix_text,
        extensions=["extra", "toc", "sane_lists", "tables", "fenced_code", "md_in_html"],
        output_format="html5",
    )
    manuscript_body = _wrap_abstract_block(manuscript_body)
    body = (
        manuscript_body
        + '\n<section class="appendix-break">'
        + '<h1>Appendix</h1>'
        + '<p class="appendix-note">The following appendix is included directly in the HTML paper for self-contained reading. '
        + 'A standalone appendix page is also available in the paper package.</p>'
        + appendix_body
        + "</section>"
    )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>StableSteering: Interactive Preference-Guided Local Search for Iterative Text-to-Image Refinement</title>
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
        --bg: #efe8dd;
        --paper: #fffdfa;
        --text: #1f1b17;
        --muted: #6f6253;
        --border: #d7cab8;
        --accent: #7b4411;
        --table: #faf6ef;
        --rule: #dfd2c0;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background: linear-gradient(180deg, #f5efe7 0%, #ece3d7 100%);
        color: var(--text);
        font-family: Georgia, "Times New Roman", serif;
      }}
      main {{ max-width: 980px; margin: 0 auto; padding: 30px 18px 56px; }}
      article {{
        background: var(--paper);
        border: 1px solid var(--border);
        border-radius: 10px;
        box-shadow: 0 18px 42px rgba(62, 40, 16, 0.08);
        padding: 52px 64px 68px;
        hyphens: auto;
      }}
      h1, h2, h3 {{
        color: #17130f;
        line-height: 1.2;
        font-weight: 700;
      }}
      article > h1:first-of-type {{
        margin: 0 0 1.8rem;
        text-align: center;
        font-size: 2.15rem;
        line-height: 1.15;
        letter-spacing: -0.01em;
        padding-bottom: 1.15rem;
        border-bottom: 1px solid var(--rule);
      }}
      h2 {{
        font-size: 1.38rem;
        margin: 2.2rem 0 0.65rem;
        padding-top: 0.15rem;
      }}
      h3 {{
        font-size: 1.08rem;
        margin: 1.55rem 0 0.45rem;
      }}
      p, li {{
        font-size: 1.03rem;
        line-height: 1.68;
        text-align: justify;
        text-justify: inter-word;
      }}
      p {{
        margin: 0;
      }}
      p + p {{
        text-indent: 1.65em;
        margin-top: 0.1rem;
      }}
      h1 + p, h2 + p, h3 + p, figure + p, table + p, .abstract + figure + p, .equation + p, blockquote + p {{
        text-indent: 0;
        margin-top: 0;
      }}
      ul, ol {{
        margin: 0.5rem 0 1rem 1.5rem;
        padding: 0;
      }}
      li + li {{
        margin-top: 0.32rem;
      }}
      strong {{ color: #17130f; }}
      .abstract {{
        margin: 0 0 1.5rem;
        padding: 1rem 1.2rem 1.05rem;
        border: 1px solid var(--border);
        background: #fbf7f1;
        border-radius: 8px;
      }}
      .abstract h2 {{
        margin: 0 0 0.45rem;
        padding: 0;
        text-align: center;
        font-size: 1.14rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
      }}
      .abstract p {{
        text-indent: 0;
        font-size: 1.01rem;
      }}
      figure {{
        margin: 1.6rem auto 1.2rem;
        text-align: center;
      }}
      figure img {{
        max-width: 100%;
        height: auto;
        display: block;
        margin: 0 auto;
        border: 1px solid var(--border);
        border-radius: 6px;
        background: white;
        padding: 0;
        box-shadow: 0 5px 16px rgba(52, 40, 27, 0.06);
      }}
      figcaption {{
        max-width: 90%;
        margin: 0.72rem auto 0;
        font-size: 0.94rem;
        line-height: 1.5;
        color: #40352b;
        text-align: left;
        text-justify: auto;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        margin: 1rem 0 1.3rem;
        background: var(--table);
        font-size: 0.97rem;
      }}
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
      blockquote {{
        margin: 1.2rem 0;
        padding: 0.8rem 1rem;
        border-left: 4px solid var(--accent);
        background: #f7f1e8;
      }}
      code, pre {{ font-family: Consolas, "Courier New", monospace; }}
      code {{
        white-space: normal;
        overflow-wrap: anywhere;
        word-break: break-word;
        font-size: 0.94em;
      }}
      pre {{ background: #f6f0e8; border: 1px solid var(--border); border-radius: 10px; padding: 0.9rem; overflow-x: auto; }}
      .equation {{
        margin: 1.15rem auto 1.2rem;
        padding: 0.95rem 1.15rem;
        background: #f8f4ee;
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow-x: auto;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.6);
      }}
      .equation p {{
        margin: 0;
        text-indent: 0;
      }}
      mjx-container[jax="SVG"] {{
        margin: 0.45rem 0 !important;
        text-align: center !important;
        font-size: 109% !important;
      }}
      mjx-container[jax="SVG"] > svg {{
        max-width: 100%;
        height: auto !important;
      }}
      table mjx-container[jax="SVG"] {{
        margin: 0 !important;
        display: inline-block !important;
        font-size: 96% !important;
        vertical-align: middle;
      }}
      .toc {{
        background: #f6efe5;
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin: 1.2rem 0 1.7rem;
      }}
      .appendix-break {{
        margin-top: 3.2rem;
        padding-top: 2.6rem;
        border-top: 2px solid #d8cab8;
      }}
      .appendix-note {{
        margin-top: -0.1rem;
        margin-bottom: 1.25rem;
        color: var(--muted);
        font-size: 0.98rem;
      }}
      @media (max-width: 760px) {{
        article {{ padding: 24px 20px 34px; }}
        main {{ padding: 12px 10px 24px; }}
        article > h1:first-of-type {{ font-size: 1.6rem; }}
        figcaption {{ max-width: 100%; }}
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
