/**
 * Reading a produced PDF back, and standing in for R2.
 *
 * WHY THIS EXISTS. Every stamping assertion this repository had before
 * spec/0010 was a SHAPE assertion -- bytes longer, page count 2, two hashes
 * that differ. None of them read a word of what was stamped, so almost any
 * mutation of the stamped CONTENT passed them (spec/0010 §S2). This file is
 * the smallest thing that makes content assertions possible: a per-page text
 * reader, and an in-memory bucket that behaves the way `storage/r2.ts` expects
 * its binding to behave.
 *
 * WHAT THE READER DOES NOT CLAIM. It is NOT a general PDF text extractor and
 * must not be read as one. It walks each page's content stream, decodes it
 * through pdf-lib's own `decodePDFRawStream`, and returns the operands of the
 * `Tj` show-text operators in stream order. That covers exactly the output
 * `core/stamping.ts` produces -- pdf-lib `drawText` emits one `Tj` per call --
 * and nothing else. A PDF using `TJ` arrays, `'`/`"`, or a font whose encoding
 * is not a byte-per-glyph map would come back wrong or empty, and no case here
 * should be written against a PDF this project did not itself create.
 *
 * That is stated so a green count is not over-read, which is the whole failure
 * pumasi/lessons/L-006 names. The reader's own guard is A-600: if it ever
 * stops finding text, that case goes red before any content case can pass
 * vacuously.
 */

import {
  PDFArray,
  PDFDocument,
  PDFRawStream,
  StandardFonts,
  decodePDFRawStream,
  rgb,
} from 'pdf-lib';

/**
 * The raw content-stream operators of one page, concatenated.
 *
 * A page's `/Contents` is either one stream or an array of references to
 * several; pdf-lib's own writer produces the second shape once a page has been
 * drawn on after loading, which is exactly what stamping does.
 */
function pageOps(doc: PDFDocument, page: ReturnType<PDFDocument['getPages']>[number]): string {
  const contents = page.node.Contents();
  const streams = contents instanceof PDFArray
    ? contents.asArray().map((ref) => doc.context.lookup(ref))
    : [contents];
  let out = '';
  for (const s of streams) {
    if (s instanceof PDFRawStream) {
      out += Buffer.from(decodePDFRawStream(s).decode()).toString('latin1') + '\n';
    } else if (s && typeof (s as any).getContents === 'function') {
      out += Buffer.from((s as any).getContents()).toString('latin1') + '\n';
    }
  }
  return out;
}

/** Every `Tj` operand on a page, decoded, in stream order. */
function showText(ops: string): string[] {
  const out: string[] = [];
  for (const m of ops.matchAll(/<([0-9A-Fa-f\s]+)>\s*Tj/g)) {
    out.push(Buffer.from(m[1].replace(/\s+/g, ''), 'hex').toString('latin1'));
  }
  for (const m of ops.matchAll(/\(((?:\\.|[^()\\])*)\)\s*Tj/g)) {
    out.push(m[1].replace(/\\([()\\])/g, '$1'));
  }
  return out;
}

export interface PdfProbe {
  /** One entry per page, each the text drawn on that page. */
  pages: string[][];
  /** Every page's text, flattened -- for "does this document say X anywhere". */
  all: string[];
  pageCount: number;
  /** True when the page draws an XObject, which is how an embedded image is stamped. */
  drawsImage: boolean[];
}

/** Read a PDF this project produced. See the caveat at the top of this file. */
export async function readPdf(bytes: Uint8Array): Promise<PdfProbe> {
  const doc = await PDFDocument.load(bytes);
  const pages: string[][] = [];
  const drawsImage: boolean[] = [];
  for (const page of doc.getPages()) {
    const ops = pageOps(doc, page);
    pages.push(showText(ops));
    // `/Name Do` paints a form or image XObject. stamping.ts draws an XObject
    // only via `page.drawImage`, so on these documents it means "a signature
    // image was embedded here rather than a name typed".
    drawsImage.push(/\/[A-Za-z0-9_.-]+\s+Do\b/.test(ops));
  }
  return { pages, all: pages.flat(), pageCount: pages.length, drawsImage };
}

/** A real PDF with one identifiable line per page, for seeding an envelope. */
export async function makePdf(pageTexts: string[]): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  const font = await doc.embedFont(StandardFonts.Helvetica);
  for (const text of pageTexts) {
    const page = doc.addPage([612, 792]);
    page.drawText(text, { x: 50, y: 700, size: 12, font, color: rgb(0, 0, 0) });
  }
  return await doc.save();
}

/**
 * A 1x1 transparent PNG, as a data URL -- the smallest thing
 * `POST /api/sign/:id/signature` accepts and `pdf-lib.embedPng` will embed.
 */
export const TINY_PNG_DATA_URL =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

export interface FakeBucket {
  /** Keys currently held, with their bytes and content type. */
  objects: Map<string, { data: Uint8Array; contentType?: string }>;
  /** Every call made, in order -- so a case can prove the boundary was crossed. */
  calls: { op: 'put' | 'get' | 'delete'; key: string }[];
  put(key: string, data: Uint8Array | ArrayBuffer, opts?: any): Promise<void>;
  get(key: string): Promise<{ arrayBuffer(): Promise<ArrayBuffer>; httpMetadata?: any } | null>;
  delete(key: string): Promise<void>;
}

/**
 * An in-memory stand-in for the R2 bucket binding.
 *
 * It implements the three methods `storage/r2.ts` calls and nothing more, with
 * the shapes that file consumes: `put(key, data, { httpMetadata })`, a `get`
 * returning an object with `arrayBuffer()` and `httpMetadata`, and `delete`.
 * The wrapper under test is REAL -- `R2SignStorage` is constructed by
 * `durable.ts` and its own key building, content type and null handling all
 * execute. What is stood in for is Cloudflare, which a test machine cannot
 * reach.
 *
 * A case using this is evidence about `storage/r2.ts` and `durable.ts`. It is
 * not evidence about R2's durability, consistency or limits, and spec/0010
 * §S1c says so in the same words.
 */
export function fakeBucket(): FakeBucket {
  const objects = new Map<string, { data: Uint8Array; contentType?: string }>();
  const calls: { op: 'put' | 'get' | 'delete'; key: string }[] = [];
  return {
    objects,
    calls,
    async put(key, data, opts) {
      calls.push({ op: 'put', key });
      const bytes = data instanceof Uint8Array ? new Uint8Array(data) : new Uint8Array(data);
      objects.set(key, { data: bytes, contentType: opts?.httpMetadata?.contentType });
    },
    async get(key) {
      calls.push({ op: 'get', key });
      const held = objects.get(key);
      if (!held) return null;
      const copy = held.data.slice();
      return {
        async arrayBuffer() {
          return copy.buffer.slice(copy.byteOffset, copy.byteOffset + copy.byteLength) as ArrayBuffer;
        },
        httpMetadata: { contentType: held.contentType },
      };
    },
    async delete(key) {
      calls.push({ op: 'delete', key });
      objects.delete(key);
    },
  };
}
