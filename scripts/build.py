#!/usr/bin/env python3
"""Build a GitHub Pages site by converting PDFs in ./pdfs into a static site.

Output goal: the website should reflect the PDF, and only the PDF.

Implementation:
- Render each PDF page to a PNG via Poppler (`pdftoppm`).
- Generate one HTML file per page that contains only the page image.
- Root index redirects to the first PDF’s first page.

Requirements:
- Python 3.11+
- `pypdf` (used for page count)
- Poppler utils installed (pdftoppm)
"""

from __future__ import annotations

import html
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


def page_html(title: str, page_num: int, total_pages: int, img_rel: str) -> str:
    # PDF-only rendering: no header, no navigation, no extra text.
    # The browser window should show only the rendered page image.
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{safe_title} — Page {page_num}</title>
    <style>
      html, body {{ margin: 0; padding: 0; background: #fff; }}
      img {{ display: block; width: 100%; height: auto; }}
    </style>
  </head>
  <body>
    <img src=\"{img_rel}\" alt=\"{safe_title} page {page_num}\" />
  </body>
</html>
"""


def index_html(items: list[PdfItem]) -> str:
    # PDF-only: if there is at least one PDF, show the first one immediately.
    if items:
        first = items[0]
        return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{html.escape(first.title)}</title>
    <meta http-equiv=\"refresh\" content=\"0; url=./{html.escape(first.slug)}/1.html\" />
  </head>
  <body>
    <a href=\"./{html.escape(first.slug)}/1.html\">Open</a>
  </body>
</html>
"""

    return """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>No PDF</title>
  </head>
  <body>
    No PDFs found.
  </body>
</html>
"""


def main() -> None:
    ensure_empty_dir(DIST_DIR)

    # No extra site assets: output should reflect the PDF only.

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
        total_pages = max(pages, len(images))

        title = pdf_path.stem
        items.append(PdfItem(title=title, slug=slug, pages=total_pages))

        for i in range(1, total_pages + 1):
            img_name = f"page-{i}.png"
            img_path = out_img_dir / img_name
            img_rel = f"./img/{img_name}" if img_path.exists() else ""

            if not img_rel:
                raise RuntimeError(
                    f"Missing rendered image for {pdf_path.name} page {i}. "
                    "Ensure poppler-utils (pdftoppm) is installed in CI."
                )

            html_out = page_html(
                title=title,
                page_num=i,
                total_pages=total_pages,
                img_rel=img_rel,
            )
            (out_doc_dir / f"{i}.html").write_text(html_out, encoding="utf-8")

    (DIST_DIR / "index.html").write_text(index_html(items), encoding="utf-8")

    print(f"Built site with {len(items)} PDF(s). Output: {DIST_DIR}")


if __name__ == "__main__":
    main()

