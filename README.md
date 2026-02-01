# PDF → GitHub Pages (interactive-friendly)

Push a PDF into `pdfs/` and this repo will auto-generate a **static website** for GitHub Pages.

## Output contract

- The published site is always a single entry point: `dist/index.html` (served as `/index.html`).
- The PDF is published as a **native web page** rendered with **PDF.js** (canvas + selectable text + clickable links).
- Navigation: left/right arrows (and keyboard arrow keys).
- Zoom:
  - Desktop: Ctrl/Cmd + mouse wheel
  - Mobile: pinch-to-zoom

## How it works

- PDFs live in `pdfs/`
- A Python build script copies the first PDF to `dist/document.pdf` and generates `dist/index.html`.
- The build also vendors a minimal set of `pdfjs-dist` files into `dist/pdfjs/` so the deployed site does **not** depend on external CDNs.
- GitHub Actions publishes the generated `dist/` folder to GitHub Pages.

## Setup (GitHub)

1. Push this repo to GitHub (default branch: `main`).
2. In GitHub: **Settings → Pages** → set **Source** to **GitHub Actions**.
3. Add/replace PDFs in `pdfs/` and push.

Your site will be available at:

- `https://<your-user>.github.io/<your-repo>/`

## Local preview

Use a local server (opening `index.html` via `file://` can block PDF loading in some browsers).

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build.py
cd dist
python -m http.server 8000
```

Then open:

- http://127.0.0.1:8000/

## Troubleshooting

### "Failed to create deployment (status: 404)" in `actions/deploy-pages`

This usually means GitHub Pages isn’t enabled for the repo yet.

Fix: **Settings → Pages → Source: GitHub Actions**, then re-run the workflow.
