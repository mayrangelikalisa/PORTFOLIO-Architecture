import fs from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const pdfDir = path.join(root, 'pdfs');
const distDir = path.join(root, 'dist');

function slugifyFilename(name) {
  return name
    .toLowerCase()
    .replaceAll(/\s+/g, '-')
    .replaceAll(/[^a-z0-9._-]/g, '-')
    .replaceAll(/-+/g, '-')
    .replaceAll(/^-|-$/g, '');
}

async function ensureEmptyDir(dir) {
  await fs.rm(dir, { recursive: true, force: true });
  await fs.mkdir(dir, { recursive: true });
}

async function copyDir(src, dst) {
  await fs.mkdir(dst, { recursive: true });
  const entries = await fs.readdir(src, { withFileTypes: true });
  for (const e of entries) {
    const s = path.join(src, e.name);
    const d = path.join(dst, e.name);
    if (e.isDirectory()) await copyDir(s, d);
    else if (e.isFile()) await fs.copyFile(s, d);
  }
}

async function fileExists(p) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

async function main() {
  await ensureEmptyDir(distDir);

  // Copy static assets
  await copyDir(path.join(root, 'site'), distDir);

  // Copy PDFs
  const pdfOutDir = path.join(distDir, 'pdfs');
  await fs.mkdir(pdfOutDir, { recursive: true });

  const pdfsPresent = await fileExists(pdfDir);
  const files = pdfsPresent ? await fs.readdir(pdfDir) : [];
  const pdfFiles = files
    .filter((f) => f.toLowerCase().endsWith('.pdf'))
    .sort((a, b) => a.localeCompare(b));

  const items = [];
  for (const f of pdfFiles) {
    const safeName = slugifyFilename(f);
    // Keep original filename in output if it’s safe; otherwise use slug.
    const outName = safeName.endsWith('.pdf') ? safeName : `${safeName}.pdf`;
    await fs.copyFile(path.join(pdfDir, f), path.join(pdfOutDir, outName));
    items.push({
      title: f.replace(/\.pdf$/i, ''),
      fileName: outName
    });
  }

  const indexHtml = await fs.readFile(path.join(distDir, 'index.html'), 'utf8');
  const injected = indexHtml.replace(
    '/*__PDF_LIST__*/[]',
    `/*__PDF_LIST__*/${JSON.stringify(items, null, 2)}`
  );
  await fs.writeFile(path.join(distDir, 'index.html'), injected, 'utf8');

  // Bundle a minimal pdf.js worker copy into dist for offline use.
  // pdfjs-dist ships ESM + worker files in node_modules.
  const pdfjsDir = path.join(root, 'node_modules', 'pdfjs-dist');
  const legacyWorker = path.join(pdfjsDir, 'build', 'pdf.worker.min.mjs');
  const workerDestDir = path.join(distDir, 'vendor', 'pdfjs');
  await fs.mkdir(workerDestDir, { recursive: true });

  // Support a couple of possible paths across pdfjs-dist versions.
  const candidates = [
    legacyWorker,
    path.join(pdfjsDir, 'build', 'pdf.worker.min.js'),
    path.join(pdfjsDir, 'build', 'pdf.worker.mjs')
  ];

  let copied = false;
  for (const c of candidates) {
    if (await fileExists(c)) {
      await fs.copyFile(c, path.join(workerDestDir, path.basename(c)));
      copied = true;
      break;
    }
  }

  if (!copied) {
    console.warn('Warning: could not locate pdf.js worker file; viewer may still work via dynamic import but is less reliable.');
  }

  console.log(`Built site with ${items.length} PDF(s). Output: ${path.relative(root, distDir)}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
