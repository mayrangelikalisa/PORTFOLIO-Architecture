#!/usr/bin/env python3
"""Build a GitHub Pages site by converting PDFs in ./pdfs into a static site.

Updated goal (interactive-PDF friendly):
- Preserve PDF interactivity better (links + selectable text) by using PDF.js.
- Publish a single entry point: `/index.html`.
- Display one page at a time, fit-to-screen and centered.
- Navigate pages with left/right arrows.

Implementation:
- Copy the first PDF from ./pdfs into dist/document.pdf.
- Generate dist/index.html that loads PDF.js from a CDN and renders the page
  to a canvas with a text layer + annotation layer.

Notes:
- This preserves links and selectable text for most PDFs.
- You must open the site via a web server (GitHub Pages / localhost). Some
  browsers block PDF loading from file:// for security reasons.
"""

from __future__ import annotations

import html
import shutil
import subprocess
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "pdfs"
DIST_DIR = ROOT / "dist"


def ensure_empty_dir(p: Path) -> None:
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)


def ensure_pdfjs_assets(dist_dir: Path, version: str = "4.10.38") -> Path:
    """Ensure PDF.js assets exist under dist/pdfjs.

    We vendor the minimal pdfjs-dist files into the published artifact so the
    site doesn't depend on external CDNs (often blocked by networks or CSP).

    Requires Node/npm in CI. GitHub hosted runners include it by default.
    """

    pdfjs_out = dist_dir / "pdfjs"
    pdfjs_out.mkdir(parents=True, exist_ok=True)

    # Use a throwaway npm prefix inside dist/. This keeps the repo clean.
    npm_prefix = dist_dir / ".npm"
    npm_prefix.mkdir(parents=True, exist_ok=True)

    # Install pdfjs-dist into dist/.npm/node_modules/...
    subprocess.run(
        [
            "npm",
            "install",
            "--no-audit",
            "--no-fund",
            "--silent",
            "--prefix",
            str(npm_prefix),
            f"pdfjs-dist@{version}",
        ],
        check=True,
    )

    pkg_root = npm_prefix / "node_modules" / "pdfjs-dist"
    build_dir = pkg_root / "build"
    web_dir = pkg_root / "web"

    required = [
        build_dir / "pdf.min.mjs",
        build_dir / "pdf.worker.min.mjs",
        web_dir / "pdf_viewer.mjs",
        web_dir / "pdf_viewer.css",
    ]
    missing = [p for p in required if not p.exists()]
    if missing:
        raise RuntimeError(
            "pdfjs-dist install succeeded, but required files are missing: "
            + ", ".join(str(p) for p in missing)
        )

    # Copy into dist/pdfjs
    shutil.copyfile(build_dir / "pdf.min.mjs", pdfjs_out / "pdf.min.mjs")
    shutil.copyfile(build_dir / "pdf.worker.min.mjs", pdfjs_out / "pdf.worker.min.mjs")
    shutil.copyfile(web_dir / "pdf_viewer.mjs", pdfjs_out / "pdf_viewer.mjs")
    shutil.copyfile(web_dir / "pdf_viewer.css", pdfjs_out / "pdf_viewer.css")

    # Remove the temporary npm install tree (keeps the published dist small/clean)
    shutil.rmtree(npm_prefix, ignore_errors=True)

    return pdfjs_out


def site_html(pdf_rel_path: str, title: str, total_pages: int) -> str:
    # NOTE: This function builds the entire index.html as a single string.
    # It must start with <!doctype html>.
    safe_title = html.escape(title)

    pdfjs_build = "./pdfjs"

    # Build using an explicit list of lines to avoid accidental truncation/implicit concatenation issues.
    lines: list[str] = []
    lines.append("<!doctype html>")
    lines.append('<html lang="en">')
    lines.append("  <head>")
    lines.append("    <meta charset=\"utf-8\" />")
    lines.append(
        "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=yes\" />"
    )
    lines.append(f"    <title>{safe_title}</title>")
    lines.append(f"    <link rel=\"stylesheet\" href=\"{pdfjs_build}/pdf_viewer.css\" />")
    lines.append("    <style>")
    lines.append("      :root {")
    lines.append("        color-scheme: light;")
    lines.append("        --pad-top: env(safe-area-inset-top, 0px);")
    lines.append("        --pad-right: env(safe-area-inset-right, 0px);")
    lines.append("        --pad-bottom: env(safe-area-inset-bottom, 0px);")
    lines.append("        --pad-left: env(safe-area-inset-left, 0px);")
    lines.append("        --fit-scale: 0.99;")
    lines.append("        --gutter: 72px;")
    lines.append("      }")
    lines.append("      html, body { height: 100%; width: 100%; }")
    lines.append("      body { margin: 0; overflow: hidden; background: #fff; -webkit-text-size-adjust: 100%; }")
    lines.append("")
    lines.append("      .viewer {")
    lines.append("        height: 100vh;")
    lines.append("        width: 100vw;")
    lines.append("        display: grid;")
    lines.append("        grid-template-columns: var(--gutter) 1fr var(--gutter);")
    lines.append("        align-items: center;")
    lines.append("        position: relative;")
    lines.append("        background: #fff;")
    lines.append("        padding: var(--pad-top) var(--pad-right) var(--pad-bottom) var(--pad-left);")
    lines.append("        box-sizing: border-box;")
    lines.append("      }")
    lines.append("")
    lines.append("      .content {")
    lines.append("        grid-column: 2;")
    lines.append("        height: 100%;")
    lines.append("        width: 100%;")
    lines.append("        display: grid;")
    lines.append("        place-items: center;")
    lines.append("        overflow: hidden;")
    lines.append("      }")
    lines.append("")
    lines.append("      .pan {")
    lines.append("        height: 100%;")
    lines.append("        width: 100%;")
    lines.append("        overflow: hidden;")
    lines.append("        display: grid;")
    lines.append("        align-items: center;")
    lines.append("        justify-items: center;")
    lines.append("        -webkit-overflow-scrolling: touch;")
    lines.append("        touch-action: manipulation;")
    lines.append("      }")
    lines.append("      .pan.is-zoomed { overflow: auto; }")
    lines.append("")
    lines.append("      #stage {")
    lines.append("        position: relative;")
    lines.append("        display: inline-block;")
    lines.append("        transform-origin: center center;")
    lines.append("      }")
    lines.append("")
    lines.append("      #pdfCanvas { display:block; opacity: 0.92; }")
    lines.append("      .textLayer { position:absolute; inset:0; transform-origin:0 0; overflow:hidden; opacity: 1;")
    lines.append("        -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;")
    lines.append("        text-rendering: geometricPrecision; mix-blend-mode: multiply; }")
    lines.append("      .annotationLayer { position:absolute; inset:0; transform-origin:0 0; }")
    lines.append("")
    lines.append("      .nav {")
    lines.append("        height: 100%;")
    lines.append("        display: grid;")
    lines.append("        place-items: center;")
    lines.append("        cursor: pointer;")
    lines.append("        user-select: none;")
    lines.append("        -webkit-tap-highlight-color: transparent;")
    lines.append("        color: rgba(0,0,0,0.65);")
    lines.append("        font: 700 40px/1 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;")
    lines.append("      }")
    lines.append("      .nav:hover { color: rgba(0,0,0,0.9); }")
    lines.append("      .nav[aria-disabled=\"true\"] { opacity: 0; pointer-events: none; }")
    lines.append("      .nav-left { grid-column: 1; background: linear-gradient(to right, rgba(255,255,255,0.80), rgba(255,255,255,0)); }")
    lines.append("      .nav-right { grid-column: 3; background: linear-gradient(to left, rgba(255,255,255,0.80), rgba(255,255,255,0)); }")
    lines.append("")
    lines.append("      .status {")
    lines.append("        position: absolute;")
    lines.append("        top: calc(10px + var(--pad-top));")
    lines.append("        left: 50%;")
    lines.append("        transform: translateX(-50%);")
    lines.append("        padding: 6px 10px;")
    lines.append("        border-radius: 999px;")
    lines.append("        background: rgba(0,0,0,0.06);")
    lines.append("        color: rgba(0,0,0,0.75);")
    lines.append("        font: 600 12px/1.2 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;")
    lines.append("      }")
    lines.append("")
    lines.append("      @media (max-width: 720px) {")
    lines.append("        :root { --gutter: 64px; --fit-scale: 1.10; }")
    lines.append("        .nav { font-size: 34px; }")
    lines.append("      }")
    lines.append("")
    lines.append("      * { box-sizing: border-box; }")
    lines.append("    </style>")
    lines.append("  </head>")
    lines.append("  <body>")
    lines.append("    <div class=\"viewer\" id=\"viewer\">")
    lines.append("      <div class=\"nav nav-left\" id=\"prevBtn\" aria-label=\"Previous page\" role=\"button\" tabindex=\"0\">&#10094;</div>")
    lines.append("      <div class=\"content\">")
    lines.append("        <div class=\"pan\" id=\"pan\">")
    lines.append("          <div id=\"stage\">")
    lines.append("            <canvas id=\"pdfCanvas\"></canvas>")
    lines.append("            <div class=\"textLayer\" id=\"textLayer\"></div>")
    lines.append("            <div class=\"annotationLayer\" id=\"annotationLayer\"></div>")
    lines.append("          </div>")
    lines.append("        </div>")
    lines.append("      </div>")
    lines.append("      <div class=\"nav nav-right\" id=\"nextBtn\" aria-label=\"Next page\" role=\"button\" tabindex=\"0\">&#10095;</div>")
    lines.append("      <div class=\"status\" id=\"status\">Loading…</div>")
    lines.append("    </div>")
    lines.append("")
    lines.append("    <script type=\"module\">")
    lines.append(f"      import * as pdfjsLib from '{pdfjs_build}/pdf.min.mjs';")
    lines.append(f"      import * as pdfjsViewer from '{pdfjs_build}/pdf_viewer.mjs';")
    lines.append("")
    lines.append(f"      const PDF_URL = {repr(pdf_rel_path)};")
    lines.append(f"      const PDF_PAGES = {int(total_pages) if total_pages else 0};")
    lines.append("")
    lines.append("      const pan = document.getElementById('pan');")
    lines.append("      const stage = document.getElementById('stage');")
    lines.append("      const canvas = document.getElementById('pdfCanvas');")
    lines.append("      const textLayerDiv = document.getElementById('textLayer');")
    lines.append("      const annotationLayerDiv = document.getElementById('annotationLayer');")
    lines.append("      const prevBtn = document.getElementById('prevBtn');")
    lines.append("      const nextBtn = document.getElementById('nextBtn');")
    lines.append("      const status = document.getElementById('status');")
    lines.append("")
    lines.append("      function setStatus(msg) { status.textContent = msg; status.style.display = msg ? 'block' : 'none'; }")
    lines.append("      function setError(msg, err) { setStatus(msg); console.error(msg, err); }")
    lines.append("      function clamp(n, lo, hi) { return Math.max(lo, Math.min(hi, n)); }")
    lines.append("")
    lines.append("      let pdfDoc = null;")
    lines.append("      let pageNumber = 1;")
    lines.append("      let baseScale = 1;")
    lines.append("      let zoom = 1;")
    lines.append("      let renderToken = 0;")
    lines.append("      let renderTask = null;")
    lines.append("      let refineTimer = null;")
    lines.append("")
    lines.append("      function setNavState() {")
    lines.append("        const total = (pdfDoc && pdfDoc.numPages) ? pdfDoc.numPages : (PDF_PAGES ? PDF_PAGES : 0);")
    lines.append("        prevBtn.setAttribute('aria-disabled', String(pageNumber <= 1));")
    lines.append("        nextBtn.setAttribute('aria-disabled', String(total && pageNumber >= total));")
    lines.append("      }")
    lines.append("")
    lines.append("      function computeBaseScale(viewportW, viewportH) {")
    lines.append("        const cs = getComputedStyle(document.documentElement);")
    lines.append("        const padTop = Number.parseFloat(cs.getPropertyValue('--pad-top'));")
    lines.append("        const padRight = Number.parseFloat(cs.getPropertyValue('--pad-right'));")
    lines.append("        const padBottom = Number.parseFloat(cs.getPropertyValue('--pad-bottom'));")
    lines.append("        const padLeft = Number.parseFloat(cs.getPropertyValue('--pad-left'));")
    lines.append("        const gutter = Number.parseFloat(cs.getPropertyValue('--gutter'));")
    lines.append("        const fitScale = Number.parseFloat(cs.getPropertyValue('--fit-scale'));")
    lines.append("        const pTop = Number.isFinite(padTop) ? padTop : 0;")
    lines.append("        const pRight = Number.isFinite(padRight) ? padRight : 0;")
    lines.append("        const pBottom = Number.isFinite(padBottom) ? padBottom : 0;")
    lines.append("        const pLeft = Number.isFinite(padLeft) ? padLeft : 0;")
    lines.append("        const gut = Number.isFinite(gutter) ? gutter : 0;")
    lines.append("        const fit = Number.isFinite(fitScale) ? fitScale : 1;")
    lines.append("        const margin = 4;")
    lines.append("        const availW = Math.max(1, window.innerWidth - pLeft - pRight - (2 * gut) - margin);")
    lines.append("        const availH = Math.max(1, window.innerHeight - pTop - pBottom - margin);")
    lines.append("        baseScale = Math.min(availW / viewportW, availH / viewportH) * fit;")
    lines.append("        baseScale = clamp(baseScale, 0.01, 10);")
    lines.append("      }")
    lines.append("")
    lines.append("      function applyScale() {")
    lines.append("        const s = baseScale * zoom;")
    lines.append("        stage.style.transform = `scale(${s})`;")
    lines.append("        pan.classList.toggle('is-zoomed', zoom > 1.01);")
    lines.append("      }")
    lines.append("")
    lines.append("      function recenter() {")
    lines.append("        const maxX = Math.max(0, pan.scrollWidth - pan.clientWidth);")
    lines.append("        const maxY = Math.max(0, pan.scrollHeight - pan.clientHeight);")
    lines.append("        pan.scrollLeft = maxX / 2;")
    lines.append("        pan.scrollTop = maxY / 2;")
    lines.append("      }")
    lines.append("")
    lines.append("      function next() { if (pdfDoc && pageNumber < pdfDoc.numPages) renderPage(pageNumber + 1); }")
    lines.append("      function prev() { if (pdfDoc && pageNumber > 1) renderPage(pageNumber - 1); }")
    lines.append("      prevBtn.addEventListener('click', prev);")
    lines.append("      nextBtn.addEventListener('click', next);")
    lines.append("      window.addEventListener('keydown', (e) => {")
    lines.append("        if (e.key === 'ArrowRight') next();")
    lines.append("        if (e.key === 'ArrowLeft') prev();")
    lines.append("      });")
    lines.append("")
    lines.append("      pan.addEventListener('wheel', (e) => {")
    lines.append("        if (!(e.ctrlKey ? true : e.metaKey)) return;")
    lines.append("        e.preventDefault();")
    lines.append("        const delta = e.deltaY;")
    lines.append("        const factor = delta > 0 ? 0.9 : 1.1;")
    lines.append("        zoom = clamp(zoom * factor, 1, 8);")
    lines.append("        applyScale();")
    lines.append("        recenter();")
    lines.append("      }, { passive: false });")
    lines.append("")
    lines.append("      // Pinch-to-zoom (mobile)")
    lines.append("      let pinchActive = false;")
    lines.append("      let pinchStartDist = 0;")
    lines.append("      let pinchStartZoom = 1;")
    lines.append("      function touchDist(t1, t2) {")
    lines.append("        const dx = t1.clientX - t2.clientX;")
    lines.append("        const dy = t1.clientY - t2.clientY;")
    lines.append("        return Math.hypot(dx, dy);")
    lines.append("      }")
    lines.append("      pan.addEventListener('touchstart', (e) => {")
    lines.append("        if (!e.touches || e.touches.length !== 2) return;")
    lines.append("        pinchActive = true;")
    lines.append("        pinchStartDist = touchDist(e.touches[0], e.touches[1]);")
    lines.append("        pinchStartZoom = zoom;")
    lines.append("      }, { passive: true });")
    lines.append("      pan.addEventListener('touchmove', (e) => {")
    lines.append("        if (!pinchActive || !e.touches || e.touches.length !== 2) return;")
    lines.append("        e.preventDefault();")
    lines.append("        const curDist = touchDist(e.touches[0], e.touches[1]);")
    lines.append("        if (pinchStartDist <= 0) return;")
    lines.append("        const ratio = curDist / pinchStartDist;")
    lines.append("        zoom = clamp(pinchStartZoom * ratio, 1, 8);")
    lines.append("        applyScale();")
    lines.append("      }, { passive: false });")
    lines.append("      pan.addEventListener('touchend', (e) => {")
    lines.append("        if (!pinchActive) return;")
    lines.append("        if (!e.touches || e.touches.length < 2) {")
    lines.append("          pinchActive = false;")
    lines.append("          recenter();")
    lines.append("        }")
    lines.append("      }, { passive: true });")
    lines.append("      pan.addEventListener('touchcancel', () => { pinchActive = false; }, { passive: true });")
    lines.append("")
    lines.append("      function getMemoryGiB() {")
    lines.append("        const dm = Number(navigator.deviceMemory);")
    lines.append("        return Number.isFinite(dm) && dm > 0 ? dm : 4;")
    lines.append("      }")
    lines.append("      function getMaxCanvasPixels() {")
    lines.append("        const mem = getMemoryGiB();")
    lines.append("        if (mem >= 8) return 28_000_000;")
    lines.append("        if (mem >= 4) return 18_000_000;")
    lines.append("        return 12_000_000;")
    lines.append("      }")
    lines.append("      function getQualityScaleForCurrentView(viewport) {")
    lines.append("        const dpr = window.devicePixelRatio || 1;")
    lines.append("        const compensate = 1 / Math.max(0.35, baseScale);")
    lines.append("        let s = dpr * compensate;")
    lines.append("        s = clamp(s, 1.5, 6);")
    lines.append("        const maxPx = getMaxCanvasPixels();")
    lines.append("        const pxAtS = viewport.width * viewport.height * (s * s);")
    lines.append("        if (pxAtS > maxPx) {")
    lines.append("          const factor = Math.sqrt(maxPx / Math.max(1, viewport.width * viewport.height));")
    lines.append("          s = Math.min(s, factor);")
    lines.append("        }")
    lines.append("        return clamp(s, 1.25, 6);")
    lines.append("      }")
    lines.append("")
    lines.append("      async function renderCanvas(page, viewport, outputScale, token, showStatus) {")
    lines.append("        if (token !== renderToken) return;")
    lines.append("        if (showStatus) setStatus('Rendering…');")
    lines.append("        canvas.width = Math.floor(viewport.width * outputScale);")
    lines.append("        canvas.height = Math.floor(viewport.height * outputScale);")
    lines.append("        canvas.style.width = `${viewport.width}px`;")
    lines.append("        canvas.style.height = `${viewport.height}px`;")
    lines.append("        stage.style.width = `${viewport.width}px`;")
    lines.append("        stage.style.height = `${viewport.height}px`;")
    lines.append("        const ctx = canvas.getContext('2d', { alpha: false });")
    lines.append("        const transform = outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null;")
    lines.append("        try { renderTask?.cancel?.(); } catch (_) {}")
    lines.append("        renderTask = page.render({ canvasContext: ctx, viewport, transform });")
    lines.append("        await renderTask.promise;")
    lines.append("        if (token !== renderToken) return;")
    lines.append("        if (showStatus) setStatus('');")
    lines.append("      }")
    lines.append("")
    lines.append("      async function renderLayers(page, viewport, token) {")
    lines.append("        try {")
    lines.append("          textLayerDiv.replaceChildren();")
    lines.append("          annotationLayerDiv.replaceChildren();")
    lines.append("          const textContent = await page.getTextContent({ includeMarkedContent: true });")
    lines.append("          if (token !== renderToken) return;")
    lines.append("          await pdfjsViewer.renderTextLayer({ textContentSource: textContent, container: textLayerDiv, viewport });")
    lines.append("          const linkService = new pdfjsViewer.PDFLinkService();")
    lines.append("          linkService.setDocument(pdfDoc);")
    lines.append("          const annotations = await page.getAnnotations({ intent: 'display' });")
    lines.append("          if (token !== renderToken) return;")
    lines.append("          // Forms are expensive; disable for faster load while keeping links.")
    lines.append("          pdfjsViewer.AnnotationLayer.render({ viewport, div: annotationLayerDiv, annotations, page, linkService, renderForms: false });")
    lines.append("        } catch (e) {")
    lines.append("          console.warn('Layer render error', e);")
    lines.append("        }")
    lines.append("      }")
    lines.append("")
    lines.append("      async function renderPage(num) {")
    lines.append("        if (!pdfDoc) return;")
    lines.append("        renderToken++;")
    lines.append("        const token = renderToken;")
    lines.append("        pageNumber = clamp(num, 1, pdfDoc.numPages);")
    lines.append("        setNavState();")
    lines.append("        zoom = 1;")
    lines.append("        const page = await pdfDoc.getPage(pageNumber);")
    lines.append("        const viewport = page.getViewport({ scale: 1 });")
    lines.append("        computeBaseScale(viewport.width, viewport.height);")
    lines.append("        applyScale();")
    lines.append("        recenter();")
    lines.append("        const maxScale = getQualityScaleForCurrentView(viewport);")
    lines.append("        const previewScale = Math.min(1.25, maxScale);")
    lines.append("        await renderCanvas(page, viewport, previewScale, token, true);")
    lines.append("        if (token !== renderToken) return;")
    lines.append("        setTimeout(() => renderLayers(page, viewport, token), 0);")
    lines.append("        if (refineTimer) clearTimeout(refineTimer);")
    lines.append("        if (maxScale > previewScale + 0.05) {")
    lines.append("          refineTimer = setTimeout(() => renderCanvas(page, viewport, maxScale, token, false), 250);")
    lines.append("        }")
    lines.append("      }")
    lines.append("")
    lines.append("      async function supportsRangeRequests(url) {")
    lines.append("        try {")
    lines.append("          const ctrl = new AbortController();")
    lines.append("          const to = setTimeout(() => ctrl.abort(), 2000);")
    lines.append("          const r = await fetch(url, { method: 'HEAD', cache: 'no-store', signal: ctrl.signal });")
    lines.append("          clearTimeout(to);")
    lines.append("          if (!r.ok) return false;")
    lines.append("          const ar = r.headers.get('accept-ranges');")
    lines.append("          return !!(ar && ar.toLowerCase() !== 'none');")
    lines.append("        } catch (_) {")
    lines.append("          return false;")
    lines.append("        }")
    lines.append("      }")
    lines.append("")
    lines.append("      async function loadPdf() {")
    lines.append("        setStatus('Loading…');")
    lines.append("        const hasRange = await supportsRangeRequests(PDF_URL);")
    lines.append("        const loadingTask = pdfjsLib.getDocument({ url: PDF_URL, disableRange: !hasRange, disableStream: !hasRange });")
    lines.append("        loadingTask.onProgress = (p) => {")
    lines.append("          if (!p || !p.loaded) return;")
    lines.append("          if (p.total) setStatus(`Loading… ${Math.round((p.loaded/p.total)*100)}%`);")
    lines.append("        };")
    lines.append("        const timeout = setTimeout(() => setError('Loading timed out.'), 60000);")
    lines.append("        try {")
    lines.append("          pdfDoc = await loadingTask.promise;")
    lines.append("          clearTimeout(timeout);")
    lines.append("          setStatus('');")
    lines.append("          setNavState();")
    lines.append("          await renderPage(1);")
    lines.append("        } catch (err) {")
    lines.append("          clearTimeout(timeout);")
    lines.append("          setError('Failed to load PDF.', err);")
    lines.append("        }")
    lines.append("      }")
    lines.append("")
    lines.append(f"      pdfjsLib.GlobalWorkerOptions.workerSrc = '{pdfjs_build}/pdf.worker.min.mjs';")
    lines.append("      loadPdf();")
    lines.append("    </script>")
    lines.append("  </body>")
    lines.append("</html>")

    return "\n".join(lines) + "\n"  # final newline


def main() -> None:
    ensure_empty_dir(DIST_DIR)

    if not PDF_DIR.exists():
        raise RuntimeError("Missing ./pdfs directory")

    pdf_paths = sorted([p for p in PDF_DIR.iterdir() if p.suffix.lower() == ".pdf"])
    if not pdf_paths:
        raise RuntimeError("No PDFs found in ./pdfs")

    # Keep behavior simple and deterministic: publish the first PDF in sorted order.
    pdf_path = pdf_paths[0]

    # Read page count for nav state.
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)

    # Copy PDF into dist. Use a stable filename for index.html to reference.
    out_pdf = DIST_DIR / "document.pdf"
    shutil.copyfile(pdf_path, out_pdf)

    # Vendor PDF.js into dist so GitHub Pages doesn't depend on a CDN.
    ensure_pdfjs_assets(DIST_DIR)

    # Generate index.html as the only entry point.
    (DIST_DIR / "index.html").write_text(
        site_html("./document.pdf", title="Portfolio Architecture", total_pages=total_pages),
        encoding="utf-8",
    )

    print(f"Built interactive-friendly site for: {pdf_path.name}. Output: {DIST_DIR}")


if __name__ == "__main__":
    main()

