# PDF → GitHub Pages (converted to HTML)

Push one or more PDF files into `pdfs/` and this repo will auto-generate a **native static website** (HTML pages) from them, then publish it to GitHub Pages.

## How it works

- PDFs live in `pdfs/`
- A Python build script converts each PDF into:
  - per-page PNG renderings (Poppler `pdftoppm`)
  - per-page HTML files that show the image + extracted selectable text (`pypdf`)
- GitHub Actions publishes the generated `dist/` folder to GitHub Pages

## Quick start

1. Push this repo to GitHub (default branch: `main`).
2. In GitHub: **Settings → Pages** → set **Source** to **GitHub Actions**.
3. Add PDFs to `pdfs/` and push.

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
