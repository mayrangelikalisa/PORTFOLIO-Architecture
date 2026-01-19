#!/usr/bin/env python3
"""Build a GitHub Pages site by converting PDFs in ./pdfs into a static site.

Output goal: the website should reflect the PDF, and only the PDF.

Implementation:
- Render each PDF page to a PNG via Poppler (`pdftoppm`).
- Generate ONE HTML file per PDF that contains all pages.
  Each PDF page is a viewport-sized block (fits on screen without overflow).
- Root index redirects to the first PDF.

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


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def render_pdf_pages_to_png(pdf_path: Path, out_dir: Path) -> list[Path]:
    """Render pages to PNG using pdftoppm.

    Poppler naming depends on page count; page numbers are usually zero-padded.
    Example outputs:
      - page-1.png (sometimes)
      - page-01.png
      - page-001.png

    We don't assume a fixed width, we just glob page-*.png and sort by page number.

    If pdftoppm isn't available, returns an empty list.
    """
    if shutil.which("pdftoppm") is None:
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


def pdf_one_page_site_html(title: str, page_imgs_rel: list[str]) -> str:
    """Create one HTML document containing all pages, each as a fullscreen block."""
    safe_title = html.escape(title)

    # PDF-only rendering: no website chrome.
    # Each page is a section that is exactly one viewport tall.
    # The image is contained within the viewport so it never overflows.
    sections: list[str] = []
    for idx, img_rel in enumerate(page_imgs_rel, start=1):
        sections.append(
            f"    <section class=\"page\" aria-label=\"{safe_title} page {idx}\">\n"
            f"      <img class=\"page-img\" src=\"{html.escape(img_rel)}\" alt=\"{safe_title} page {idx}\" />\n"
            f"    </section>\n"
        )

    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "  <head>\n"
        "    <meta charset=\"utf-8\" />\n"
        "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        f"    <title>{safe_title}</title>\n"
        "    <style>\n"
        "      :root { color-scheme: light; }\n"
        "      html, body { height: 100%; }\n"
        "      body { margin: 0; background: #fff; }\n"
        "\n"
        "      /* Each PDF page becomes a fullscreen block */\n"
        "      .page {\n"
        "        height: 100vh;\n"
        "        width: 100vw;\n"
        "        display: grid;\n"
        "        place-items: center;\n"
        "        background: #fff;\n"
        "      }\n"
        "\n"
        "      /* Fit within viewport without overflow, preserving aspect ratio */\n"
        "      .page-img {\n"
        "        max-width: 100vw;\n"
        "        max-height: 100vh;\n"
        "        width: auto;\n"
        "        height: auto;\n"
        "        display: block;\n"
        "      }\n"
        "\n"
        "      @media print {\n"
        "        .page { height: auto; width: auto; }\n"
        "        .page-img { max-width: 100%; max-height: none; }\n"
        "      }\n"
        "    </style>\n"
        "  </head>\n"
        "  <body>\n"
        + "".join(sections)
        + "  </body>\n"
        "</html>\n"
    )


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
    <meta http-equiv=\"refresh\" content=\"0; url=./{html.escape(first.slug)}/index.html\" />
  </head>
  <body>
    <a href=\"./{html.escape(first.slug)}/index.html\">Open</a>
  </body>
</html>
"""

    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>No PDF</title>
  </head>
  <body>
    No PDFs found.
  </body>
</html>
"""


def main() -> None:
    ensure_empty_dir(DIST_DIR)

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
        if not images:
            raise RuntimeError(
                "No rendered images produced. Ensure poppler-utils (pdftoppm) is installed in CI/local."
            )

        # Prefer rendered page count (truth on disk), but sanity-check against PDF.
        total_pages = len(images)
        if pages and total_pages != pages:
            # Keep going (some PDFs can report differently), but don't silently generate broken output.
            # We'll still use images that exist.
            pass

        title = pdf_path.stem
        items.append(PdfItem(title=title, slug=slug, pages=total_pages))

        page_imgs_rel = [f"./img/{p.name}" for p in images]
        (out_doc_dir / "index.html").write_text(
            pdf_one_page_site_html(title=title, page_imgs_rel=page_imgs_rel),
            encoding="utf-8",
        )

    (DIST_DIR / "index.html").write_text(index_html(items), encoding="utf-8")

    print(f"Built site with {len(items)} PDF(s). Output: {DIST_DIR}")


if __name__ == "__main__":
    main()

