from __future__ import annotations

import html
import re
import shutil
from pathlib import Path
from urllib.parse import unquote

import markdown


REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = REPO_ROOT / "site"
REPO_WEB_ROOT = "https://github.com/ApartsinProjects/StableSteering"
EXCLUDED_PARTS = {
    ".git",
    ".github",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "site",
    "tmp",
    "temp",
    "tmp_real_smoke",
}
MARKDOWN_LINK_RE = re.compile(r"(!?\[[^\]]*\])\(([^)]+)\)")


def should_include(path: Path) -> bool:
    """Return whether one Markdown file should be published into the site."""

    parts = set(path.parts)
    if parts & EXCLUDED_PARTS:
        return False
    if path.suffix.lower() != ".md":
        return False
    return True


def gather_markdown_files() -> list[Path]:
    """Collect publishable Markdown files from the repository."""

    files = [path for path in REPO_ROOT.rglob("*.md") if should_include(path.relative_to(REPO_ROOT))]
    return sorted(files)


def output_rel_path(source: Path) -> Path:
    """Map one source Markdown file to its HTML output path inside the site."""

    relative = source.relative_to(REPO_ROOT)
    if relative.name.lower() == "readme.md":
        if relative.parent == Path("."):
            return Path("index.html")
        return relative.parent / "index.html"
    return relative.with_suffix(".html")


def build_mappings(files: list[Path]) -> dict[Path, Path]:
    """Return a mapping from source Markdown files to site output paths."""

    return {source: output_rel_path(source) for source in files}


def normalize_repo_target(raw_target: str, current_file: Path) -> Path | None:
    """Resolve a Markdown link target to a repository-local path when possible."""

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
        if candidate.exists():
            return candidate
        return None

    return (current_file.parent / normalized).resolve()


def rewrite_link(target: str, current_file: Path, mapping: dict[Path, Path]) -> str:
    """Rewrite one Markdown link for the generated HTML site."""

    if target.startswith(("http://", "https://", "mailto:", "#")):
        return target

    base, anchor = (target.split("#", 1) + [""])[:2] if "#" in target else (target, "")
    resolved = normalize_repo_target(base, current_file)
    if resolved is None:
        return target

    if resolved.is_dir():
        readme = resolved / "README.md"
        if readme in mapping:
            destination = mapping[readme]
            return relative_href(mapping[current_file], destination, anchor)
        if resolved.is_relative_to(REPO_ROOT):
            repo_rel = resolved.relative_to(REPO_ROOT).as_posix()
            return f"{REPO_WEB_ROOT}/tree/main/{repo_rel}"
        return target

    if resolved.suffix.lower() == ".md" and resolved in mapping:
        return relative_href(mapping[current_file], mapping[resolved], anchor)

    if resolved.is_relative_to(REPO_ROOT):
        repo_rel = resolved.relative_to(REPO_ROOT).as_posix()
        blob_or_tree = "blob" if resolved.is_file() else "tree"
        return f"{REPO_WEB_ROOT}/{blob_or_tree}/main/{repo_rel}"

    return target


def relative_href(from_page: Path, to_page: Path, anchor: str = "") -> str:
    """Return a relative hyperlink from one generated page to another."""

    href = Path(
        shutil.os.path.relpath(
            (SITE_ROOT / to_page),
            start=(SITE_ROOT / from_page).parent,
        )
    ).as_posix()
    if anchor:
        return f"{href}#{anchor}"
    return href


def rewrite_markdown_links(text: str, current_file: Path, mapping: dict[Path, Path]) -> str:
    """Rewrite Markdown links to point at generated HTML or GitHub sources."""

    def replacer(match: re.Match[str]) -> str:
        label, target = match.groups()
        cleaned = target.strip()
        title = ""
        if " \"" in cleaned and cleaned.endswith('"'):
            maybe_target, maybe_title = cleaned.rsplit(" \"", 1)
            cleaned = maybe_target
            title = f' "{maybe_title}'
        return f"{label}({rewrite_link(cleaned, current_file, mapping)}{title})"

    return MARKDOWN_LINK_RE.sub(replacer, text)


def render_page(source: Path, mapping: dict[Path, Path], all_pages: list[Path]) -> str:
    """Render one Markdown file into a full HTML document."""

    text = source.read_text(encoding="utf-8")
    rewritten = rewrite_markdown_links(text, source, mapping)
    body = markdown.markdown(
        rewritten,
        extensions=["extra", "toc", "sane_lists", "tables", "fenced_code"],
        output_format="html5",
    )
    title = source.stem if source.name.lower() != "readme.md" else source.parent.name or "StableSteering"
    current_output = mapping[source]
    nav_items = []
    for page in all_pages:
        target = mapping[page]
        label = page.stem if page.name.lower() != "readme.md" else (page.parent.name or "Home")
        nav_items.append(
            f'<li><a href="{html.escape(relative_href(current_output, target))}">{html.escape(label)}</a></li>'
        )
    source_rel = source.relative_to(REPO_ROOT).as_posix()
    source_url = f"{REPO_WEB_ROOT}/blob/main/{source_rel}"
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)} | StableSteering</title>
    <link rel="stylesheet" href="{html.escape(relative_href(current_output, Path('assets/site.css')))}">
  </head>
  <body>
    <div class="layout">
      <aside class="sidebar">
        <h1><a href="{html.escape(relative_href(current_output, Path('index.html')))}">StableSteering</a></h1>
        <p class="tagline">Project documentation site</p>
        <nav>
          <ul>
            {''.join(nav_items)}
          </ul>
        </nav>
      </aside>
      <main class="content">
        <p class="source-link"><a href="{html.escape(source_url)}">View source Markdown</a></p>
        {body}
      </main>
    </div>
  </body>
</html>
"""


def write_assets() -> None:
    """Write shared static assets for the generated documentation site."""

    assets_dir = SITE_ROOT / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "site.css").write_text(
        """
:root {
  color-scheme: light;
  --bg: #f5efe5;
  --panel: #fffdf8;
  --border: #d8cdbf;
  --text: #241d18;
  --muted: #6e5946;
  --accent: #8a4f14;
  --code-bg: #f7f1e9;
  font-family: "Segoe UI", system-ui, sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; background: linear-gradient(180deg, #f3ebdf, #fbf8f2); color: var(--text); }
.layout { display: grid; grid-template-columns: 280px minmax(0, 1fr); min-height: 100vh; }
.sidebar { padding: 24px 18px; border-right: 1px solid var(--border); background: rgba(255, 252, 247, 0.96); position: sticky; top: 0; height: 100vh; overflow: auto; }
.sidebar h1 { margin: 0 0 8px; font-size: 1.4rem; }
.sidebar a { color: var(--accent); text-decoration: none; }
.tagline { margin: 0 0 18px; color: var(--muted); }
.sidebar ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
.sidebar li { margin: 0; }
.content { max-width: 980px; padding: 32px 40px 48px; }
.content h1, .content h2, .content h3 { line-height: 1.2; }
.content a { color: var(--accent); }
.source-link { margin-top: 0; color: var(--muted); }
pre, code { font-family: Consolas, "Courier New", monospace; }
pre { background: var(--code-bg); border: 1px solid var(--border); border-radius: 14px; padding: 14px; overflow: auto; }
code { background: var(--code-bg); padding: 0.14rem 0.35rem; border-radius: 6px; }
pre code { background: transparent; padding: 0; }
table { width: 100%; border-collapse: collapse; margin: 16px 0; }
th, td { padding: 10px; border-top: 1px solid var(--border); text-align: left; vertical-align: top; }
blockquote { margin: 16px 0; padding: 8px 16px; border-left: 4px solid var(--accent); background: rgba(138, 79, 20, 0.06); }
img { max-width: 100%; height: auto; border-radius: 12px; }
@media (max-width: 960px) {
  .layout { grid-template-columns: 1fr; }
  .sidebar { position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--border); }
  .content { padding: 24px 18px 40px; }
}
""".strip(),
        encoding="utf-8",
    )
    (SITE_ROOT / ".nojekyll").write_text("", encoding="utf-8")


def build_site() -> None:
    """Generate the full HTML documentation site."""

    if SITE_ROOT.exists():
        shutil.rmtree(SITE_ROOT)
    SITE_ROOT.mkdir(parents=True, exist_ok=True)
    write_assets()

    files = gather_markdown_files()
    mapping = build_mappings(files)
    for source in files:
        output = SITE_ROOT / mapping[source]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_page(source, mapping, files), encoding="utf-8")


if __name__ == "__main__":
    build_site()
