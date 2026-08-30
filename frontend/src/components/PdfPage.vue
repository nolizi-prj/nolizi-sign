<script setup lang="ts">
/**
 * Renders one page of a PDF (given as a blob URL) onto a canvas, scaled to
 * fit the container's width and rendered at devicePixelRatio for sharpness.
 * The default slot is positioned absolutely over the canvas so callers can
 * overlay field boxes / placement UI at the same pixel size the canvas was
 * rendered at (see `rendered` emit).
 */
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as pdfjsLib from "pdfjs-dist";
import pdfjsWorkerUrl from "pdfjs-dist/build/pdf.worker.mjs?url";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorkerUrl;

const props = defineProps<{
  /** Blob URL of the PDF document. */
  src: string;
  /** 0-indexed page number to render. */
  page: number;
}>();

const emit = defineEmits<{
  /** Fired after each successful render with the canvas's CSS (unscaled) size
   *  in px, plus the page's intrinsic size in PDF points — callers that render
   *  text at stamped-PDF-equivalent sizes need px-per-point (see SignView). */
  rendered: [widthPx: number, heightPx: number, widthPt: number, heightPt: number];
  /** Fired once per loaded document with its page count (used by callers rendering local files). */
  loaded: [pageCount: number];
  /** Fired when loading or rendering the PDF fails (corrupt file, network error, unsupported feature, ...). */
  error: [message: string];
}>();

const containerRef = ref<HTMLDivElement | null>(null);
const canvasRef = ref<HTMLCanvasElement | null>(null);

/**
 * Module-level document cache, refcounted by blob URL. Views that mount
 * many PdfPage instances for the same document (every page of a signing
 * view, the builder's thumbnail rail) share one pdf.js document instead
 * of parsing the file N times. The document is destroyed when the last
 * instance using it unmounts.
 */
interface DocCacheEntry {
  task: pdfjsLib.PDFDocumentLoadingTask;
  promise: Promise<pdfjsLib.PDFDocumentProxy>;
  refCount: number;
}

const docCache = new Map<string, DocCacheEntry>();

function acquireDoc(src: string): Promise<pdfjsLib.PDFDocumentProxy> {
  let entry = docCache.get(src);
  if (!entry) {
    const task = pdfjsLib.getDocument({ url: src });
    const created: DocCacheEntry = {
      task,
      promise: task.promise.catch((err: unknown) => {
        // Don't cache failures — let a retry (or another instance) reload.
        if (docCache.get(src) === created) docCache.delete(src);
        throw err;
      }),
      refCount: 0,
    };
    entry = created;
    docCache.set(src, entry);
  }
  entry.refCount++;
  return entry.promise;
}

function releaseDoc(src: string): void {
  const entry = docCache.get(src);
  if (!entry) return;
  entry.refCount--;
  if (entry.refCount <= 0) {
    docCache.delete(src);
    void entry.task.destroy();
  }
}

let acquiredSrc: string | null = null;
let pdfDoc: pdfjsLib.PDFDocumentProxy | null = null;
let renderTask: pdfjsLib.RenderTask | null = null;

async function ensureDocLoaded(): Promise<void> {
  if (pdfDoc) return;
  acquiredSrc = props.src;
  pdfDoc = await acquireDoc(props.src);
  emit("loaded", pdfDoc.numPages);
}

function destroyDoc(): void {
  pdfDoc = null;
  if (acquiredSrc !== null) releaseDoc(acquiredSrc);
  acquiredSrc = null;
}

/**
 * Loads (if needed) and renders the current page. Never throws — load
 * failures (corrupt PDF, network error on the blob's bytes, unsupported
 * PDF feature, ...) and render failures are caught and surfaced via the
 * `error` emit instead of becoming an unhandled promise rejection, since
 * this is called fire-and-forget (`void renderPage()`) from onMounted and
 * the prop watchers below. Cancellation (a newer render superseding this
 * one) is expected, not an error, and is silently swallowed.
 */
async function renderPage(): Promise<void> {
  let task: pdfjsLib.RenderTask | null = null;
  try {
    await ensureDocLoaded();
    const doc = pdfDoc;
    const canvas = canvasRef.value;
    const container = containerRef.value;
    if (!doc || !canvas || !container) return;

    const pdfPage = await doc.getPage(props.page + 1);
    const containerWidth = container.clientWidth;
    const unscaledViewport = pdfPage.getViewport({ scale: 1 });
    const fitScale = containerWidth > 0 ? containerWidth / unscaledViewport.width : 1;
    const viewport = pdfPage.getViewport({ scale: fitScale });
    const dpr = window.devicePixelRatio || 1;

    canvas.width = Math.round(viewport.width * dpr);
    canvas.height = Math.round(viewport.height * dpr);
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;

    renderTask?.cancel();
    task = pdfPage.render({
      canvas,
      viewport,
      transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined,
    });
    renderTask = task;
    await task.promise;

    emit("rendered", viewport.width, viewport.height, unscaledViewport.width, unscaledViewport.height);
  } catch (err) {
    if (err instanceof Error && err.name === "RenderingCancelledException") return;
    console.error("PdfPage: failed to load or render PDF page", err);
    emit("error", err instanceof Error ? err.message : "Failed to load or render the PDF.");
  } finally {
    if (task && renderTask === task) renderTask = null;
  }
}

watch(
  () => props.src,
  async () => {
    destroyDoc();
    await renderPage();
  },
);

watch(
  () => props.page,
  () => {
    void renderPage();
  },
);

onMounted(() => {
  void renderPage();
});

onBeforeUnmount(() => {
  renderTask?.cancel();
  destroyDoc();
});
</script>

<template>
  <div ref="containerRef" class="pdf-page">
    <canvas ref="canvasRef" />
    <div class="pdf-page-overlay">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.pdf-page {
  position: relative;
  width: 100%;
}

.pdf-page canvas {
  display: block;
}

.pdf-page-overlay {
  position: absolute;
  inset: 0;
}
</style>
