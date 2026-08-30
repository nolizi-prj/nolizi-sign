# Excel fit-to-sheet conversion + larger default signature field

Date: 2026-08-04. Requested: (1) the default signature field is too small;
(2) xlsx uploads often convert to PDFs with many pages of small slices of the
sheet — the default should behave like DocuSeal/DocuSign, ideally fitting an
entire tab per page.

## 1. Default signature field size

`DEFAULT_SIZES.signature` in `frontend/src/composables/useFieldPlacement.ts`
goes from `{ w: 0.2, h: 0.06 }` to `{ w: 0.28, h: 0.09 }` — on a US-letter
page that's ~2.4in × 1.0in, close to DocuSign's default stamp. Frontend-only:
both the template builder and the one-off send path place fields through this
composable, and `stamping.py` draws the signature image into whatever box the
field defines (aspect ratio preserved). Other field types are unchanged; the
existing resize handles still allow per-field adjustment.

## 2. Excel → PDF: one page per sheet

Cause of the "too many pages" problem: LibreOffice (like Excel's own print
and DocuSign's converter) honors the workbook's print setup, and the default
for a wide sheet is tiling it across many portrait pages.

Fix: for spreadsheet input, pass the Calc PDF export filter with the
`SinglePageSheets` option — documented as "ignores each sheet's paper size,
print ranges and shown/hidden status and puts every sheet (even hidden
sheets) on exactly one page":

    soffice --headless --convert-to
      'pdf:calc_pdf_Export:{"SinglePageSheets":{"type":"boolean","value":"true"}}'

`_convert_with_soffice` picks the convert-to target by extension: `xlsx` gets
the Calc filter string, everything else keeps plain `pdf`. No API, schema, or
frontend changes — page count already flows from the converted PDF.

Trade-offs accepted: hidden sheets get exported, print ranges are ignored,
and a very large sheet yields one large page (readable by zooming, same as
DocuSeal's behavior) rather than tiny tiled slices. Requires LibreOffice ≥7.4
for JSON filter options on the CLI; the production image (Debian bookworm)
ships 7.4, verified empirically in Docker as part of this change.

## Testing

- Unit: the convert-to target is the Calc filter string for `xlsx`, plain
  `pdf` for `docx`/`pptx`/`ppt` (helper extracted so no subprocess mocking).
- Integration (auto-skips without soffice, runs in CI): a new committed
  fixture `sample-wide.xlsx` — two sheets, one wide enough to tile across
  multiple pages under default conversion — converts to exactly 2 pages.
- Manual: convert the wide fixture inside a bookworm LibreOffice container
  with and without the filter to confirm the page counts and that 7.4
  accepts the JSON syntax.
