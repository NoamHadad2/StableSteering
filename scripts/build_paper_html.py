from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import unquote

import markdown


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = REPO_ROOT / "paper"
SOURCE = PAPER_ROOT / "manuscript_draft.md"
OUTPUT = PAPER_ROOT / "manuscript_draft.html"
REPO_WEB_ROOT = "https://github.com/ApartsinProjects/StableSteering"
MARKDOWN_LINK_RE = re.compile(r"(!?\[[^\]]*\])\(([^)]+)\)")


def normalize_repo_target(raw_target: str, current_file: Path) -> Path | None:
    """Resolve one Markdown link target to a repo-local path when possible."""

    target = unquote(raw_target.strip())
    if not target or target.startswith(("http://", "https://", "mailto:", "#")):
        return None

    normalized = target.replace("\\", "/")
    repo_prefix = REPO_ROOT.as_posix()
    repo_prefix_slash = f"/{repo_prefix}"

    if normalized.startswith(repo_prefix_slash):
        normalized = normalized[len(repo_prefix_slash) :].lstrip("/")
        return (REPO_ROOT / normalized).resolve()

    if normalized.startswith(repo_prefix):
        normalized = normalized[len(repo_prefix) :].lstrip("/")
        return (REPO_ROOT / normalized).resolve()

    if re.match(r"^[A-Za-z]:/", normalized):
        return Path(normalized).resolve()

    if normalized.startswith("/"):
        candidate = (REPO_ROOT / normalized.lstrip("/")).resolve()
        return candidate if candidate.exists() else None

    return (current_file.parent / normalized).resolve()


def rewrite_link(target: str, current_file: Path) -> str:
    """Rewrite a Markdown link target for the standalone paper HTML."""

    if target.startswith(("http://", "https://", "mailto:", "#")):
        return target

    base, anchor = (target.split("#", 1) + [""])[:2] if "#" in target else (target, "")
    resolved = normalize_repo_target(base, current_file)
    if resolved is None or not resolved.is_relative_to(REPO_ROOT):
        return target

    repo_rel = resolved.relative_to(REPO_ROOT).as_posix()
    blob_or_tree = "blob" if resolved.is_file() else "tree"
    rewritten = f"{REPO_WEB_ROOT}/{blob_or_tree}/main/{repo_rel}"
    if anchor:
        return f"{rewritten}#{anchor}"
    return rewritten


def rewrite_markdown_links(text: str, current_file: Path) -> str:
    """Rewrite Markdown links to GitHub URLs for a portable standalone HTML paper."""

    def replacer(match: re.Match[str]) -> str:
        label, target = match.groups()
        cleaned = target.strip()
        title = ""
        if " \"" in cleaned and cleaned.endswith('"'):
            maybe_target, maybe_title = cleaned.rsplit(' "', 1)
            cleaned = maybe_target
            title = f' "{maybe_title}'
        return f"{label}({rewrite_link(cleaned, current_file)}{title})"

    return MARKDOWN_LINK_RE.sub(replacer, text)


def build_html() -> str:
    """Render the manuscript Markdown into standalone HTML."""

    source_text = SOURCE.read_text(encoding="utf-8")
    rewritten = rewrite_markdown_links(source_text, SOURCE)
    body = markdown.markdown(
        rewritten,
        extensions=["extra", "toc", "sane_lists", "tables", "fenced_code"],
        output_format="html5",
    )
    source_url = f"{REPO_WEB_ROOT}/blob/main/paper/manuscript_draft.md"
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>StableSteering Paper</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f5efe5;
        --panel: #fffdf8;
        --border: #d8cdbf;
        --text: #241d18;
        --muted: #6e5946;
        --accent: #8a4f14;
        --code-bg: #f7f1e9;
        font-family: Georgia, "Times New Roman", serif;
      }}
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; background: linear-gradient(180deg, #f3ebdf, #fbf8f2); color: var(--text); }}
      main {{
        max-width: 980px;
        margin: 0 auto;
        padding: 32px 24px 56px;
      }}
      .paper {{
        background: rgba(255, 252, 247, 0.96);
        border: 1px solid var(--border);
        border-radius: 20px;
        box-shadow: 0 16px 36px rgba(73, 51, 25, 0.08);
        padding: 28px 34px 40px;
      }}
      .meta {{
        margin: 0 0 24px;
        color: var(--muted);
        font-family: "Segoe UI", system-ui, sans-serif;
      }}
      .meta a {{ color: var(--accent); text-decoration: none; }}
      h1, h2, h3 {{ line-height: 1.2; }}
      h1, h2 {{ font-family: "Segoe UI", system-ui, sans-serif; }}
      a {{ color: var(--accent); }}
      pre, code {{ font-family: Consolas, "Courier New", monospace; }}
      pre {{
        background: var(--code-bg);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 14px;
        overflow: auto;
      }}
      code {{
        background: var(--code-bg);
        padding: 0.14rem 0.35rem;
        border-radius: 6px;
      }}
      pre code {{ background: transparent; padding: 0; }}
      table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
      th, td {{ padding: 10px; border-top: 1px solid var(--border); text-align: left; vertical-align: top; }}
      blockquote {{
        margin: 16px 0;
        padding: 8px 16px;
        border-left: 4px solid var(--accent);
        background: rgba(138, 79, 20, 0.06);
      }}
      @media (max-width: 760px) {{
        .paper {{ padding: 20px 18px 28px; }}
        main {{ padding: 18px 12px 36px; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <div class="paper">
        <p class="meta">
          Standalone HTML render of the current manuscript draft.
          <a href="{html.escape(source_url)}">View source Markdown</a>
        </p>
        {body}
      </div>
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
