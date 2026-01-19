import * as pdfjsLib from 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.min.mjs';

// Prefer local worker (bundled by build script). Fallback to CDN.
const LOCAL_WORKER = './vendor/pdfjs/pdf.worker.min.mjs';
const CDN_WORKER = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.min.mjs';

pdfjsLib.GlobalWorkerOptions.workerSrc = LOCAL_WORKER;

const els = {
  list: document.getElementById('pdf-list'),
  title: document.getElementById('doc-title'),
  meta: document.getElementById('doc-meta'),
  canvas: document.getElementById('pdf-canvas'),
  status: document.getElementById('status'),
  prev: document.getElementById('prev'),
  next: document.getElementById('next'),
  indicator: document.getElementById('page-indicator'),
  download: document.getElementById('download')
};

let current = {
  doc: null,
  item: null,
  page: 1,
  pages: 0,
  renderTask: null
};

function setStatus(msg) {
  els.status.textContent = msg || '';
}

function setControlsEnabled(enabled) {
  els.prev.disabled = !enabled;
  els.next.disabled = !enabled;
  els.download.classList.toggle('disabled', !enabled);
}

function updatePager() {
  const { page, pages } = current;
  els.prev.disabled = !(current.doc && page > 1);
  els.next.disabled = !(current.doc && page < pages);
  els.indicator.textContent = current.doc ? `Page ${page} / ${pages}` : '—';
}

async function renderPage(pageNum) {
  const doc = current.doc;
  if (!doc) return;

  // Cancel in-flight render
  if (current.renderTask) {
    try {
      current.renderTask.cancel();
    } catch {
      // ignore
    }
  }

  current.page = pageNum;
  updatePager();
  setStatus('Rendering…');

  const page = await doc.getPage(pageNum);
  const viewport = page.getViewport({ scale: 1.25 });
  const canvas = els.canvas;
  const ctx = canvas.getContext('2d', { alpha: false });

  canvas.width = Math.floor(viewport.width);
  canvas.height = Math.floor(viewport.height);

  const task = page.render({ canvasContext: ctx, viewport });
  current.renderTask = task;

  try {
    await task.promise;
    setStatus('');
  } catch (e) {
    if (e?.name === 'RenderingCancelledException') return;
    console.error(e);
    setStatus('Failed to render page.');
  }
}

async function loadPdf(item) {
  current.item = item;
  current.page = 1;
  current.pages = 0;
  current.doc = null;

  els.title.textContent = item.title;
  els.meta.textContent = '';
  els.download.href = `./pdfs/${encodeURIComponent(item.fileName)}`;
  els.download.download = item.fileName;

  setControlsEnabled(false);
  setStatus('Loading…');

  // Workaround: if local worker path fails (some cases on pages), fall back to CDN.
  try {
    const loadingTask = pdfjsLib.getDocument(els.download.href);
    const doc = await loadingTask.promise;
    current.doc = doc;
    current.pages = doc.numPages;
    els.meta.textContent = `${doc.numPages} page(s)`;
    setControlsEnabled(true);
    updatePager();
    await renderPage(1);
  } catch (err) {
    console.warn('Local worker or load failed, retrying with CDN worker.', err);
    pdfjsLib.GlobalWorkerOptions.workerSrc = CDN_WORKER;
    try {
      const loadingTask = pdfjsLib.getDocument(els.download.href);
      const doc = await loadingTask.promise;
      current.doc = doc;
      current.pages = doc.numPages;
      els.meta.textContent = `${doc.numPages} page(s)`;
      setControlsEnabled(true);
      updatePager();
      await renderPage(1);
    } catch (err2) {
      console.error(err2);
      setStatus('Failed to load PDF.');
    }
  }
}

function renderList() {
  els.list.innerHTML = '';

  if (!Array.isArray(PDF_LIST) || PDF_LIST.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'muted';
    empty.textContent = 'No PDFs found. Add PDFs to the pdfs/ folder and push.';
    els.list.appendChild(empty);
    return;
  }

  for (const item of PDF_LIST) {
    const btn = document.createElement('button');
    btn.textContent = item.title;
    btn.addEventListener('click', async () => {
      for (const b of els.list.querySelectorAll('button')) b.classList.remove('active');
      btn.classList.add('active');
      await loadPdf(item);
    });
    els.list.appendChild(btn);
  }
}

els.prev.addEventListener('click', () => renderPage(current.page - 1));
els.next.addEventListener('click', () => renderPage(current.page + 1));

renderList();

