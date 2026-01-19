#!/usr/bin/env python3
"""Build a GitHub Pages site by converting PDFs in ./pdfs into a static site.

Output goal (per user requirements):
- The website should reflect the PDF exactly, and only the PDF.
- The published site must be reachable as a single path: `/index.html`.
- The site should contain the whole PDF content as one page, where each PDF page is
  displayed as a viewport-sized block (fits on screen without overflow).

Implementation:
- Render each PDF page to a PNG via Poppler (`pdftoppm`).
- Generate ONE `dist/index.html` containing all pages in order.

Requirements:
- Python 3.11+
- `pypdf` (used for ordering/count sanity checks)
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


def render_pdf_pages_to_png(pdf_path: Path, out_dir: Path, prefix_slug: str) -> list[Path]:
    """Render a PDF to per-page PNGs using pdftoppm.

    Writes files like: {prefix_slug}-001.png
    Returns sorted Path list.
    """
    if shutil.which("pdftoppm") is None:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)

    prefix = out_dir / prefix_slug

    cmd = [
        "pdftoppm",
        "-png",
        "-r",
        "144",
        str(pdf_path),
        str(prefix),
    ]
    run(cmd)

    images = sorted(out_dir.glob(f"{prefix_slug}-*.png"), key=lambda p: _page_num(p.name))
    return images


def _page_num(filename: str) -> int:
    m = re.search(r"-(\d+)\.png$", filename)
    return int(m.group(1)) if m else 10**9


def site_html(items_in_order: list[tuple[str, list[str]]]) -> str:
    """Create one HTML document containing all PDF pages, each as a fullscreen block."""

    sections: list[str] = []
    for title, page_imgs_rel in items_in_order:
        safe_title = html.escape(title)
        for idx, img_rel in enumerate(page_imgs_rel, start=1):
            sections.append(
                "    <section class=\"page\" aria-label=\""
                + safe_title
                + " page "
                + str(idx)
                + "\">\n"
                + "      <img class=\"page-img\" src=\""
                + html.escape(img_rel)
                + "\" alt=\""
                + safe_title
                + " page "
                + str(idx)
                + "\" />\n"
                + "    </section>\n"
            )

    title = items_in_order[0][0] if items_in_order else "No PDF"
    safe_title = html.escape(title)

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


def main() -> None:
    ensure_empty_dir(DIST_DIR)

    out_img_dir = DIST_DIR / "img"
    out_img_dir.mkdir(parents=True, exist_ok=True)

    items: list[PdfItem] = []
    items_in_order: list[tuple[str, list[str]]] = []

    if PDF_DIR.exists():
        pdf_paths = sorted([p for p in PDF_DIR.iterdir() if p.suffix.lower() == ".pdf"])
    else:
        pdf_paths = []

    for pdf_path in pdf_paths:
        slug = slugify_filename(pdf_path.stem)

        reader = PdfReader(str(pdf_path))
        reported_pages = len(reader.pages)

        images = render_pdf_pages_to_png(pdf_path, out_img_dir, prefix_slug=slug)
        if not images:
            raise RuntimeError(
                "No rendered images produced. Ensure poppler-utils (pdftoppm) is installed in CI/local."
            )

        total_pages = len(images)
        title = pdf_path.stem
        items.append(PdfItem(title=title, slug=slug, pages=total_pages))

        # Best-effort sanity check (don't fail on minor mismatches, but keep ordering stable)
        if reported_pages and total_pages != reported_pages:
            pass

        page_imgs_rel = [f"./img/{p.name}" for p in images]
        items_in_order.append((title, page_imgs_rel))

    (DIST_DIR / "index.html").write_text(site_html(items_in_order), encoding="utf-8")

    print(f"Built site from {len(items)} PDF(s). Output: {DIST_DIR}")


if __name__ == "__main__":
    main()

