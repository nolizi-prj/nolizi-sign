"""High-fidelity PDF conversion via Microsoft Graph (``?format=pdf``).

Graph renders Office documents with Word/PowerPoint's own engines, so the
PDF matches what the sender saw — no LibreOffice re-layout. Flow: upload
the file to a temp folder on the existing SharePoint drive (the archive
mirror's ``SP_DRIVE_ID``), request the PDF rendition, delete the temp file.

``convert_via_graph`` is strictly best-effort: ``None`` on any failure —
feature off, xlsx (see ``GRAPH_CONVERT_EXTENSIONS``), token/upload/convert
errors, non-PDF response — and callers (``app.conversion``) fall back to
LibreOffice. It never raises. Known Graph limits: large files can fail with
406 "Error from Office Service", and bursts can be throttled (429); both
simply fall back.

Design: docs/superpowers/specs/2026-08-07-graph-convert-design.md.
"""

from __future__ import annotations

import logging
import uuid

import httpx

from app.config import Settings
from app.graph import acquire_token
from app.sharepoint import GRAPH_ROOT, _upload_file

logger = logging.getLogger(__name__)

# Word/PowerPoint formats where Graph's native rendering beats LibreOffice.
# Spreadsheets (xlsx/xls/ods) are deliberately excluded: Graph paginates
# them by the workbook's print setup (tiling wide sheets across pages),
# which would regress the one-page-per-sheet SinglePageSheets behavior
# LibreOffice gives us (see conversion._CALC_PDF_TARGET). Other
# LibreOffice-native formats (odt/odp/rtf/txt) also stay on LibreOffice.
GRAPH_CONVERT_EXTENSIONS = {"docx", "doc", "pptx", "ppt"}

_TMP_FOLDER = "_convert_tmp"
_TIMEOUT_SECONDS = 60.0


def convert_via_graph(
    data: bytes,
    ext: str,
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> bytes | None:
    """Convert ``data`` (an ``ext`` Office document) to PDF bytes via Graph.

    Returns ``None`` whenever the Graph path can't or shouldn't produce a
    result — the caller's LibreOffice fallback is the error handling.
    """
    if not settings.graph_convert or not settings.sp_drive_id:
        return None
    if ext not in GRAPH_CONVERT_EXTENSIONS:
        return None
    token = acquire_token(settings)
    if not token:
        return None

    drive = settings.sp_drive_id
    item_path = f"{_TMP_FOLDER}/{uuid.uuid4().hex}.{ext}"
    headers = {"Authorization": f"Bearer {token}"}
    client_kwargs = {"transport": transport} if transport is not None else {}
    try:
        # follow_redirects: the ?format=pdf endpoint 302s to a
        # pre-authenticated download URL (httpx drops the Authorization
        # header on the cross-host hop, which is what Graph expects).
        with httpx.Client(timeout=_TIMEOUT_SECONDS, follow_redirects=True, **client_kwargs) as client:
            if not _upload_file(client, drive, item_path, data, token):
                return None
            try:
                response = client.get(
                    f"{GRAPH_ROOT}/drives/{drive}/root:/{item_path}:/content",
                    params={"format": "pdf"},
                    headers=headers,
                )
                if response.status_code >= 300 or not response.content.startswith(b"%PDF"):
                    logger.warning(
                        "Graph PDF conversion failed for .%s (status %d); falling back to LibreOffice",
                        ext,
                        response.status_code,
                    )
                    return None
                return response.content
            finally:
                # Best-effort temp cleanup — a leftover file is harmless
                # (the temp folder holds nothing user-facing) but untidy.
                try:
                    client.delete(f"{GRAPH_ROOT}/drives/{drive}/root:/{item_path}", headers=headers)
                except Exception:
                    logger.debug("Graph temp-file delete failed for %s", item_path)
    except Exception:
        logger.warning("Graph PDF conversion errored for .%s; falling back to LibreOffice", ext, exc_info=True)
        return None
