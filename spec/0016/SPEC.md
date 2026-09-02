# Specification

Native conversion:

- PDF
- PNG, JPG, JPEG
- UTF-8 TXT and CSV (paginated monospaced PDF; unsupported standard-font
  characters are visibly replaced rather than causing conversion failure)

Microsoft Graph conversion when configured:

- DOC, DOCX, DOT, DOTM, DOTX
- XLS, XLSM, XLSX
- PPT, PPTX, PPS, PPSX
- RTF, ODT, ODS, ODP
- HTM, HTML, MD, MARKDOWN
- EML, MSG, EPUB
- TIF, TIFF

The browser picker must advertise only formats the production Worker routes.
All normalized output remains subject to the existing readable-PDF and size
checks. Acceptance case A-904 covers conversion that works without Graph.
