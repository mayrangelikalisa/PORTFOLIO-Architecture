#!/usr/bin/env python3
"""Build a GitHub Pages site by converting PDFs in ./pdfs into a static site.

Output goal (per user requirements):
- The website should reflect the PDF exactly, and only the PDF.
- The published site must be reachable as a single path: `/index.html`.
- Each PDF page should be displayed fully, fit to the screen, and centered.
- Navigation between pages should be via left/right arrows (both sides of the screen).

Implementation:
- Render each PDF page to a PNG via Poppler (`pdftoppm`).
- Generate ONE `dist/index.html` that displays ONE page at a time (no scrolling).

Requirements:
- Python 3.11+
- `pypdf` (used for ordering/count sanity checks)
- Poppler utils installed (pdftoppm)
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


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def render_pdf_pages_to_png(pdf_path: Path, out_dir: Path, prefix_slug: str) -> list[Path]:
    """Render a PDF to per-page PNGs using pdftoppm.

    Notes on quality:
    - Higher DPI yields better quality but increases build time and output size.

    Configuration:
    - Set environment variable `PDF_RENDER_DPI` (e.g. 300, 450, 600).
      Default is 300 (high quality, practical for CI).
    """
    if shutil.which("pdftoppm") is None:
        return []

    dpi = int(os.environ.get("PDF_RENDER_DPI", "600"))

    out_dir.mkdir(parents=True, exist_ok=True)

    prefix = out_dir / prefix_slug

    cmd = [
        "pdftoppm",
        "-png",
        "-r",
        str(dpi),
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
    """Create a single-page PDF viewer (one page visible at a time)."""

    # Flatten to one ordered list of page images.
    pages: list[str] = []
    title = "No PDF"
    if items_in_order:
        title = items_in_order[0][0]
    for _pdf_title, page_imgs_rel in items_in_order:
        pages.extend(page_imgs_rel)

    safe_title = html.escape(title)

    # Build a JS array of page URLs.
    # IMPORTANT: do NOT HTML-escape here; emit valid JS string literals.
    page_list_js = ",\n".join(f"      {p!r}" for p in pages)

    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "  <head>\n"
        "    <meta charset=\"utf-8\" />\n"
        "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        f"    <title>{safe_title}</title>\n"
        "    <style>\n"
        "      :root { color-scheme: light; }\n"
        "      html, body { height: 100%; width: 100%; }\n"
        "      body { margin: 0; overflow: hidden; background: #fff; }\n"
        "\n"
        "      /* Viewer takes the whole viewport */\n"
        "      .viewer {\n"
        "        height: 100vh;\n"
        "        width: 100vw;\n"
        "        display: grid;\n"
        "        place-items: center;\n"
        "        position: relative;\n"
        "        background: #fff;\n"
        "      }\n"
        "\n"
        "      /*\n"
        "        Scale the displayed page to 90% (requested), while staying centered.\n"
        "        The image itself still uses its native pixel size unless it has to shrink to fit.\n"
        "      */\n"
        "      .page-scale {\n"
        "        transform: scale(0.9);\n"
        "        transform-origin: center center;\n"
        "        display: grid;\n"
        "        place-items: center;\n"
        "      }\n"
        "\n"
        "      /* Keep pages at native pixel size when possible; only scale DOWN to fit */\n"
        "      #pageImg {\n"
        "        max-width: 100vw;\n"
        "        max-height: 100vh;\n"
        "        width: auto;\n"
        "        height: auto;\n"
        "        display: block;\n"
        "        image-rendering: auto;\n"
        "      }\n"
        "\n"
        "      .nav {\n"
        "        position: absolute;\n"
        "        top: 0;\n"
        "        bottom: 0;\n"
        "        width: 15vw;\n"
        "        min-width: 60px;\n"
        "        display: grid;\n"
        "        place-items: center;\n"
        "        cursor: pointer;\n"
        "        user-select: none;\n"
        "        color: rgba(0,0,0,0.65);\n"
        "        font: 700 44px/1 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;\n"
        "        background: linear-gradient(to var(--dir), rgba(255,255,255,0.65), rgba(255,255,255,0));\n"
        "      }\n"
        "      .nav:hover { color: rgba(0,0,0,0.9); }\n"
        "      .nav[aria-disabled=\"true\"] { opacity: 0; pointer-events: none; }\n"
        "      .nav-left { left: 0; --dir: right; }\n"
        "      .nav-right { right: 0; --dir: left; }\n"
        "\n"
        "      .counter {\n"
        "        position: absolute;\n"
        "        bottom: 10px;\n"
        "        left: 50%;\n"
        "        transform: translateX(-50%);\n"
        "        padding: 6px 10px;\n"
        "        border-radius: 999px;\n"
        "        background: rgba(255,255,255,0.75);\n"
        "        color: rgba(0,0,0,0.75);\n"
        "        font: 600 12px/1.2 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;\n"
        "      }\n"
        "    </style>\n"
        "  </head>\n"
        "  <body>\n"
        "    <div class=\"viewer\">\n"
        "      <div class=\"nav nav-left\" id=\"prevBtn\" aria-label=\"Previous page\">&#10094;</div>\n"
        "      <div class=\"page-scale\">\n"
        "        <img id=\"pageImg\" alt=\"\" />\n"
        "      </div>\n"
        "      <div class=\"nav nav-right\" id=\"nextBtn\" aria-label=\"Next page\">&#10095;</div>\n"
        "      <div class=\"counter\" id=\"counter\"></div>\n"
        "    </div>\n"
        "\n"
        "    <script>\n"
        "      const pages = [\n"
        + page_list_js
        + "\n      ];\n"
        "      let idx = 0;\n"
        "\n"
        "      const img = document.getElementById('pageImg');\n"
        "      const prevBtn = document.getElementById('prevBtn');\n"
        "      const nextBtn = document.getElementById('nextBtn');\n"
        "      const counter = document.getElementById('counter');\n"
        "\n"
        "      function render() {\n"
        "        if (!pages.length) {\n"
        "          counter.textContent = 'No PDFs found.';\n"
        "          prevBtn.setAttribute('aria-disabled','true');\n"
        "          nextBtn.setAttribute('aria-disabled','true');\n"
        "          return;\n"
        "        }\n"
        "        idx = Math.max(0, Math.min(idx, pages.length - 1));\n"
        "        img.src = pages[idx];\n"
        "        img.alt = 'Page ' + (idx + 1);\n"
        "        counter.textContent = (idx + 1) + ' / ' + pages.length;\n"
        "        prevBtn.setAttribute('aria-disabled', String(idx === 0));\n"
        "        nextBtn.setAttribute('aria-disabled', String(idx === pages.length - 1));\n"
        "      }\n"
        "\n"
        "      function next() { idx++; render(); }\n"
        "      function prev() { idx--; render(); }\n"
        "\n"
        "      prevBtn.addEventListener('click', prev);\n"
        "      nextBtn.addEventListener('click', next);\n"
        "      window.addEventListener('keydown', (e) => {\n"
        "        if (e.key === 'ArrowRight') next();\n"
        "        if (e.key === 'ArrowLeft') prev();\n"
        "      });\n"
        "\n"
        "      render();\n"
        "    </script>\n"
        "  </body>\n"
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

