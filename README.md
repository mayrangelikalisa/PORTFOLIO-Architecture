# PDF → GitHub Pages

Push one or more PDF files into `pdfs/` and this repo will auto-generate a small website that lists the PDFs and renders each PDF directly in the browser.

## How it works

- PDFs live in `pdfs/`
- A GitHub Action builds the site into `dist/`
- The Action publishes `dist/` to GitHub Pages

## Quick start

1. Create a new GitHub repo from this folder (or upload these files).
2. In GitHub: **Settings → Pages**
   - **Build and deployment**: set **Source** to **GitHub Actions**
3. Commit and push.
4. Add PDFs to `pdfs/` and push again.

The site will be available at:

- `https://<your-user>.github.io/<your-repo>/`

## Adding PDFs

Put files in:

- `pdfs/your-file.pdf`

and commit + push.

## Local build (optional)

If you have Node.js 20+ installed:

```bash
npm install
npm run build
npm run preview
```

## Notes

- Rendering uses Mozilla’s `pdfjs-dist` (client-side), so the published site includes your PDFs unchanged.
- Filenames are used as titles; rename PDFs if you want nicer titles.

