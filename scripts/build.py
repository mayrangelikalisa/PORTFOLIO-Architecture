#!/usr/bin/env python3
"""Build a GitHub Pages site by converting PDFs in ./pdfs into static HTML.

Strategy (no PDF embedding):
- For each PDF:
  - extract per-page text with pypdf
  - render each page to a PNG via the Poppler tool `pdftoppm`
  - generate an HTML page per PDF page that shows the image and selectable text
- Generate an index.html linking to each PDF's HTML.

Requirements:
- Python 3.11+
- `pypdf`
- Poppler utils installed (pdftoppm) in CI and locally
"""

from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "pdfs"
DIST_DIR = ROOT / "dist"


def slugify_filename(name: str) -> str:
    base = name.lower()
    base = re.sub(r"\s+", "-", base)
    base = re.sub(r"[^a-z0-9._-]", "-", base)
    base = re.sub(r"-+", "-", base).strip("-")
    return base


@dataclass
class PdfItem:
    title: str
    slug: str
    pages: int


def ensure_empty_dir(p: Path) -> None:
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    shutil.copytree(src, dst, dirs_exist_ok=True)


def require_tool(tool: str) -> None:
    if shutil.which(tool) is None:
        raise RuntimeError(
            f"Required tool '{tool}' not found in PATH. "
            "Install poppler-utils (pdftoppm) in CI/local."
        )


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def render_pdf_pages_to_png(pdf_path: Path, out_dir: Path) -> list[Path]:
    """Render pages to PNG using pdftoppm.

    Produces files like page-1.png, page-2.png, ...

    If pdftoppm isn't available, returns an empty list and the build will still
    produce text-only HTML pages.
    """
    if shutil.which("pdftoppm") is None:
        # Allow local builds without poppler; CI installs poppler-utils.
        return []

    out_dir.mkdir(parents=True, exist_ok=True)

    prefix = out_dir / "page"

    cmd = [
        "pdftoppm",
        "-png",
        "-r",
        "144",
        str(pdf_path),
        str(prefix),
    ]
    run(cmd)

    images = sorted(out_dir.glob("page-*.png"), key=lambda p: _page_num(p.name))
    return images


def _page_num(filename: str) -> int:
    m = re.search(r"-(\d+)\.png$", filename)
    return int(m.group(1)) if m else 10**9


def page_html(title: str, page_num: int, total_pages: int, img_rel: str, text: str, nav_rel_prefix: str) -> str:
    safe_title = html.escape(title)
    safe_text = html.escape(text or "")

    prev_link = ""
    next_link = ""
    if page_num > 1:
        prev_link = f'<a class="btn" href="{nav_rel_prefix}{page_num-1}.html">Prev</a>'
    if page_num < total_pages:
        next_link = f'<a class="btn" href="{nav_rel_prefix}{page_num+1}.html">Next</a>'

    img_block = (
        f'<figure class="page"><img class="page-img" src="{img_rel}" alt="{safe_title} page {page_num}" /></figure>'
        if img_rel
        else '<div class="notice muted">(No page image available in this build; showing extracted text only.)</div>'
    )

    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{safe_title} — Page {page_num}</title>
    <link rel=\"stylesheet\" href=\"{nav_rel_prefix}../assets/site.css\" />
  </head>
  <body>
    <header class=\"top\">
      <div class=\"wrap\">
        <a class=\"brand\" href=\"{nav_rel_prefix}../index.html\">PDF Site</a>
        <div class=\"title\">{safe_title}</div>
        <div class=\"pager\">
          {prev_link}
          <span class=\"muted\">Page {page_num} / {total_pages}</span>
          {next_link}
        </div>
      </div>
    </header>

    <main class=\"wrap\">
      {img_block}

      <section class=\"text\">
        <h2>Text (selectable)</h2>
        <pre>{safe_text}</pre>
      </section>
    </main>
  </body>
</html>
"""


def index_html(items: list[PdfItem]) -> str:
    links = "\n".join(
        f'<li><a href="./{html.escape(it.slug)}/1.html">{html.escape(it.title)}</a> <span class="muted">({it.pages} page(s))</span></li>'
        for it in items
    )

    empty = "<p class=\"muted\">No PDFs found. Add PDFs into the <code>pdfs/</code> folder and push.</p>"

    docs_block = empty if not items else f'<ul class="doc-list">{links}</ul>'

    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>PDF Site</title>
    <link rel=\"stylesheet\" href=\"./assets/site.css\" />
  </head>
  <body>
    <header class=\"top\">
      <div class=\"wrap\">
        <div class=\"brand\">PDF Site</div>
        <div class=\"muted\">Converted into static HTML on push</div>
      </div>
    </header>

    <main class=\"wrap\">
      <h1>Documents</h1>
      {docs_block}

      <p class=\"muted\">Tip: Each document is rendered as images + extracted text (no PDF embedding).</p>
    </main>
  </body>
</html>
"""


def main() -> None:
    ensure_empty_dir(DIST_DIR)

    # Static assets
    assets_dir = DIST_DIR / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    copy_tree(ROOT / "site_py" / "assets", assets_dir)

    items: list[PdfItem] = []

    if PDF_DIR.exists():
        pdf_paths = sorted([p for p in PDF_DIR.iterdir() if p.suffix.lower() == ".pdf"])
    else:
        pdf_paths = []

    for pdf_path in pdf_paths:
        slug = slugify_filename(pdf_path.stem)
        out_doc_dir = DIST_DIR / slug
        out_img_dir = out_doc_dir / "img"
        out_doc_dir.mkdir(parents=True, exist_ok=True)

        reader = PdfReader(str(pdf_path))
        pages = len(reader.pages)

        images = render_pdf_pages_to_png(pdf_path, out_img_dir)
        # If poppler outputs images, trust that count; otherwise fall back to PDF page count.
        total_pages = max(pages, len(images))

        title = pdf_path.stem
        items.append(PdfItem(title=title, slug=slug, pages=total_pages))

        for i in range(1, total_pages + 1):
            page_text = ""
            if i <= pages:
                try:
                    page_text = reader.pages[i - 1].extract_text() or ""
                except Exception:
                    page_text = ""

            img_name = f"page-{i}.png"
            img_path = out_img_dir / img_name
            img_rel = f"./img/{img_name}" if img_path.exists() else ""

            html_out = page_html(
                title=title,
                page_num=i,
                total_pages=total_pages,
                img_rel=img_rel,
                text=page_text,
                nav_rel_prefix="./",
            )
            (out_doc_dir / f"{i}.html").write_text(html_out, encoding="utf-8")

    (DIST_DIR / "index.html").write_text(index_html(items), encoding="utf-8")

    print(f"Built site with {len(items)} PDF(s). Output: {DIST_DIR}")


if __name__ == "__main__":
    main()

