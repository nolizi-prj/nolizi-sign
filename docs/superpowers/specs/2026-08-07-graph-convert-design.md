# Graph-rendered PDF conversion with LibreOffice fallback

Date: 2026-08-07. Phase 1 of the conversion-fidelity plan the user
accepted: LibreOffice re-layouts OOXML approximately no matter how many
fonts we install; Microsoft Graph's `?format=pdf` renders with
Word/PowerPoint itself, and the app already has app-only Graph
credentials and a SharePoint drive (`SP_DRIVE_ID`, the archive mirror).
Documents never leave Pumasi's M365 tenant.

## Design

`app/graph_convert.py` — `convert_via_graph(data, ext, settings) ->
bytes | None`:

1. Gate: `GRAPH_CONVERT` truthy, `sp_drive_id` set, ext in
   {docx, pptx, ppt}. **xlsx is deliberately excluded**: Graph paginates
   by the workbook's print setup (tiling wide sheets), which would
   regress the SinglePageSheets one-page-per-sheet behavior.
2. Upload to `_convert_tmp/{uuid}.{ext}` on the drive (reuses
   `sharepoint._upload_file`, including the >4 MB upload-session path).
3. `GET /drives/{id}/root:/{path}:/content?format=pdf`
   (follow_redirects — Graph 302s to a pre-authenticated URL).
4. Delete the temp item (best-effort).
5. Any failure — token, upload, 406 "Error from Office Service", 429
   throttle, non-PDF body — returns `None`; **never raises**.

`conversion.to_pdf_bytes`/`to_pdf` accept an optional `settings`; when
given, eligible formats try Graph first and log which engine ran.
Without settings (tests, tools) or on failure, LibreOffice runs exactly
as before. Callers (template create, adhoc create, merged-document)
pass their request settings.

## Rollout

Set `GRAPH_CONVERT=1` on the `pumasi-sign` Railway service. Flipping it
off instantly restores pure-LibreOffice behavior; no data migration
either way.

## Testing

- Unit tests with `httpx.MockTransport`: success (upload → convert →
  delete), 406 fallback (still deletes), non-PDF body, disabled/xlsx/no
  token gates; `to_pdf_bytes` prefers Graph, falls back, and skips Graph
  without settings.
- Live check against the real tenant performed at development time: the
  office-fonts fixture converted with genuine Calibri/Cambria embedded
  (Word's rendering), temp file deleted.
