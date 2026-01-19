# PDF → GitHub Pages (converted to HTML)

Push one or more PDF files into `pdfs/` and this repo will auto-generate a **static website** from them, then publish it to GitHub Pages.

## Output contract

- The published site is always a single entry point: `dist/index.html` (served as `/index.html`).
- The PDF is converted to images and laid out as one long page.
- Each PDF page is shown as a **viewport-sized block** and the page image is scaled to **fit within the screen** (no overflow), preserving aspect ratio.

## How it works

- PDFs live in `pdfs/`
- A Python build script converts PDFs into:
  - per-page PNG renderings (Poppler `pdftoppm`)
  - a single HTML file: `dist/index.html`
- GitHub Actions publishes the generated `dist/` folder to GitHub Pages

## Quick start

1. Push this repo to GitHub (default branch: `main`).
2. In GitHub: **Settings → Pages** → set **Source** to **GitHub Actions**.
3. Add/replace PDFs in `pdfs/` and push.

Your site will be available at:

- `https://<your-user>.github.io/<your-repo>/`

## Local build (optional)

You need Python 3.11+ and Poppler tools.

On Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils
```

Then:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build.py
```

## Troubleshooting

### "Failed to create deployment (status: 404)" in `actions/deploy-pages`

This usually means GitHub Pages isn’t enabled for the repo yet.

Fix: **Settings → Pages → Source: GitHub Actions**, then re-run the workflow.
