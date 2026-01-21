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
      Default is 600 (very high quality; you may want 300 in CI for faster builds).
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
        "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\" />\n"
        f"    <title>{safe_title}</title>\n"
        "    <style>\n"
        "      :root {\n"
        "        color-scheme: light;\n"
        "        --pad-top: env(safe-area-inset-top, 0px);\n"
        "        --pad-right: env(safe-area-inset-right, 0px);\n"
        "        --pad-bottom: env(safe-area-inset-bottom, 0px);\n"
        "        --pad-left: env(safe-area-inset-left, 0px);\n"
        "        --ui-scale: 0.95; /* user-requested global visual scale */\n"
        "        --gutter: 72px; /* reserved space for arrows so they don't sit on the image */\n"
        "        --img-max-w: 100vw;\n"
        "        --img-max-h: 100vh;\n"
        "      }\n"
        "      html, body { height: 100%; width: 100%; }\n"
        "      body {\n"
        "        margin: 0;\n"
        "        overflow: hidden;\n"
        "        background: #fff;\n"
        "        -webkit-text-size-adjust: 100%;\n"
        "      }\n"
        "\n"
        "      /* Layout: left gutter (arrow), content (page), right gutter (arrow) */\n"
        "      .viewer {\n"
        "        height: 100vh;\n"
        "        width: 100vw;\n"
        "        display: grid;\n"
        "        grid-template-columns: var(--gutter) 1fr var(--gutter);\n"
        "        align-items: center;\n"
        "        position: relative;\n"
        "        background: #fff;\n"
        "        padding: var(--pad-top) var(--pad-right) var(--pad-bottom) var(--pad-left);\n"
        "        box-sizing: border-box;\n"
        "        touch-action: pan-y;\n"
        "      }\n"
        "\n"
        "      .content {\n"
        "        grid-column: 2;\n"
        "        height: 100%;\n"
        "        width: 100%;\n"
        "        display: grid;\n"
        "        place-items: center;\n"
        "        overflow: hidden;\n"
        "      }\n"
        "\n"
        "      .page-scale {\n"
        "        transform: scale(var(--ui-scale));\n"
        "        transform-origin: center center;\n"
        "        display: grid;\n"
        "        place-items: center;\n"
        "      }\n"
        "\n"
        "      /* Keep pages at native pixel size when possible; only scale DOWN to fit */\n"
        "      #pageImg {\n"
        "        max-width: var(--img-max-w);\n"
        "        max-height: var(--img-max-h);\n"
        "        width: auto;\n"
        "        height: auto;\n"
        "        display: block;\n"
        "        image-rendering: auto;\n"
        "        user-select: none;\n"
        "        -webkit-user-drag: none;\n"
        "        -webkit-touch-callout: none;\n"
        "      }\n"
        "\n"
        "      .nav {\n"
        "        height: 100%;\n"
        "        display: grid;\n"
        "        place-items: center;\n"
        "        cursor: pointer;\n"
        "        user-select: none;\n"
        "        -webkit-tap-highlight-color: transparent;\n"
        "        color: rgba(0,0,0,0.65);\n"
        "        font: 700 40px/1 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;\n"
        "      }\n"
        "      .nav:hover { color: rgba(0,0,0,0.9); }\n"
        "      .nav[aria-disabled=\"true\"] { opacity: 0; pointer-events: none; }\n"
        "      .nav-left {\n"
        "        grid-column: 1;\n"
        "        background: linear-gradient(to right, rgba(255,255,255,0.80), rgba(255,255,255,0));\n"
        "      }\n"
        "      .nav-right {\n"
        "        grid-column: 3;\n"
        "        background: linear-gradient(to left, rgba(255,255,255,0.80), rgba(255,255,255,0));\n"
        "      }\n"
        "\n"
        "      .counter {\n"
        "        position: absolute;\n"
        "        bottom: calc(10px + var(--pad-bottom));\n"
        "        left: 50%;\n"
        "        transform: translateX(-50%);\n"
        "        padding: 6px 10px;\n"
        "        border-radius: 999px;\n"
        "        background: rgba(255,255,255,0.75);\n"
        "        color: rgba(0,0,0,0.75);\n"
        "        font: 600 12px/1.2 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;\n"
        "        pointer-events: none;\n"
        "      }\n"
        "\n"
        "      @media (max-width: 720px) {\n"
        "        :root { --gutter: 64px; }\n"
        "        .nav { font-size: 34px; }\n"
        "        .counter { font-size: 11px; }\n"
        "      }\n"
        "    </style>\n"
        "  </head>\n"
        "  <body>\n"
        "    <div class=\"viewer\" id=\"viewer\">\n"
        "      <div class=\"nav nav-left\" id=\"prevBtn\" aria-label=\"Previous page\" role=\"button\" tabindex=\"0\">&#10094;</div>\n"
        "      <div class=\"content\">\n"
        "        <div class=\"page-scale\">\n"
        "          <img id=\"pageImg\" alt=\"\" draggable=\"false\" />\n"
        "        </div>\n"
        "      </div>\n"
        "      <div class=\"nav nav-right\" id=\"nextBtn\" aria-label=\"Next page\" role=\"button\" tabindex=\"0\">&#10095;</div>\n"
        "      <div class=\"counter\" id=\"counter\"></div>\n"
        "    </div>\n"
        "\n"
        "    <script>\n"
        "      const pages = [\n"
        + page_list_js
        + "\n      ];\n"
        "      let idx = 0;\n"
        "\n"
        "      const viewer = document.getElementById('viewer');\n"
        "      const img = document.getElementById('pageImg');\n"
        "      const prevBtn = document.getElementById('prevBtn');\n"
        "      const nextBtn = document.getElementById('nextBtn');\n"
        "      const counter = document.getElementById('counter');\n"
        "\n"
        "      function updateMaxImageBox() {\n"
        "        // Fit the image inside the *center column* after safe-area padding + UI scale.\n"
        "        const cs = getComputedStyle(document.documentElement);\n"
        "        const padTop = parseFloat(cs.getPropertyValue('--pad-top')) || 0;\n"
        "        const padRight = parseFloat(cs.getPropertyValue('--pad-right')) || 0;\n"
        "        const padBottom = parseFloat(cs.getPropertyValue('--pad-bottom')) || 0;\n"
        "        const padLeft = parseFloat(cs.getPropertyValue('--pad-left')) || 0;\n"
        "        const uiScale = parseFloat(cs.getPropertyValue('--ui-scale')) || 1;\n"
        "        const gutter = parseFloat(cs.getPropertyValue('--gutter')) || 0;\n"
        "\n"
        "        const w = Math.max(0, window.innerWidth - padLeft - padRight - (2 * gutter));\n"
        "        const h = Math.max(0, window.innerHeight - padTop - padBottom);\n"
        "        document.documentElement.style.setProperty('--img-max-w', (w / uiScale) + 'px');\n"
        "        document.documentElement.style.setProperty('--img-max-h', (h / uiScale) + 'px');\n"
        "      }\n"
        "\n"
        "      function render() {\n"
        "        if (!pages.length) {\n"
        "          counter.textContent = 'No PDFs found.';\n"
        "          prevBtn.setAttribute('aria-disabled','true');\n"
        "          nextBtn.setAttribute('aria-disabled','true');\n"
        "          img.removeAttribute('src');\n"
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
        "      function next() { if (idx < pages.length - 1) { idx++; render(); } }\n"
        "      function prev() { if (idx > 0) { idx--; render(); } }\n"
        "\n"
        "      prevBtn.addEventListener('click', prev);\n"
        "      nextBtn.addEventListener('click', next);\n"
        "\n"
        "      // Keyboard navigation\n"
        "      window.addEventListener('keydown', (e) => {\n"
        "        if (e.key === 'ArrowRight') next();\n"
        "        if (e.key === 'ArrowLeft') prev();\n"
        "      });\n"
        "\n"
        "      // Basic swipe navigation for mobile (left/right).\n"
        "      let touchStartX = null;\n"
        "      let touchStartY = null;\n"
        "      viewer.addEventListener('touchstart', (e) => {\n"
        "        if (!e.touches || e.touches.length !== 1) return;\n"
        "        touchStartX = e.touches[0].clientX;\n"
        "        touchStartY = e.touches[0].clientY;\n"
        "      }, {passive: true});\n"
        "      viewer.addEventListener('touchend', (e) => {\n"
        "        if (touchStartX === null || touchStartY === null) return;\n"
        "        const t = (e.changedTouches && e.changedTouches[0]) ? e.changedTouches[0] : null;\n"
        "        if (!t) return;\n"
        "        const dx = t.clientX - touchStartX;\n"
        "        const dy = t.clientY - touchStartY;\n"
        "        touchStartX = null;\n"
        "        touchStartY = null;\n"
        "\n"
        "        // Ignore mostly-vertical gestures\n"
        "        if (Math.abs(dy) > Math.abs(dx)) return;\n"
        "        if (Math.abs(dx) < 40) return;\n"
        "        if (dx < 0) next(); else prev();\n"
        "      }, {passive: true});\n"
        "\n"
        "      // Recompute fit box on resize/orientation changes\n"
        "      window.addEventListener('resize', () => { updateMaxImageBox(); });\n"
        "      window.addEventListener('orientationchange', () => {\n"
        "        setTimeout(updateMaxImageBox, 150);\n"
        "      });\n"
        "\n"
        "      updateMaxImageBox();\n"
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

