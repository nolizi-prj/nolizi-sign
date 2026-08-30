"""Convert uploaded documents (PDF, Office, OpenDocument, rtf/txt, images) to PDF and store the result.

PDFs are validated (rejecting encrypted or corrupt input) and passed through
unchanged. Images are drawn onto a US-Letter page in-process (Pillow +
reportlab). Everything else is converted to PDF by shelling out to a headless
LibreOffice (``soffice``) process. The soffice binary is located via the
``SOFFICE_BIN`` environment variable or, failing that, ``shutil.which``.
"""

import io
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import Settings
from app.graph_convert import convert_via_graph
from app.storage import FileStorage

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    # Documents (LibreOffice, with a Graph first try for Word/PowerPoint).
    "pdf",
    "docx",
    "doc",
    "xlsx",
    "xls",
    "pptx",
    "ppt",
    "rtf",
    "odt",
    "ods",
    "odp",
    "txt",
    # Images (converted in-process — see _convert_image_to_pdf).
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "bmp",
    "tif",
    "tiff",
}

# Modern Office and OpenDocument files are both zip containers; legacy
# Office files (doc/xls/ppt) are OLE compound documents.
_ZIP_MAGIC = b"PK\x03\x04"
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# Accepted leading byte signatures per extension (any match passes). txt and
# webp don't fit the prefix model and are special-cased in sniff_ok.
_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    "pdf": (b"%PDF",),
    "docx": (_ZIP_MAGIC,),
    "xlsx": (_ZIP_MAGIC,),
    "pptx": (_ZIP_MAGIC,),
    "odt": (_ZIP_MAGIC,),
    "ods": (_ZIP_MAGIC,),
    "odp": (_ZIP_MAGIC,),
    "doc": (_OLE_MAGIC,),
    "xls": (_OLE_MAGIC,),
    "ppt": (_OLE_MAGIC,),
    "rtf": (b"{\\rtf",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "gif": (b"GIF8",),
    "bmp": (b"BM",),
    # TIFF comes in little- and big-endian flavors.
    "tif": (b"II*\x00", b"MM\x00*"),
    "tiff": (b"II*\x00", b"MM\x00*"),
}

_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff"}

_SOFFICE_TIMEOUT_SECONDS = 120

# Calc's PDF export honors the workbook's print setup, so a wide sheet tiles
# across many portrait pages of small slices. SinglePageSheets instead puts
# every sheet on exactly one page sized to its content — the DocuSeal-style
# "fit the entire tab" default people expect from an e-sign upload. The JSON
# filter-options CLI syntax needs LibreOffice >= 7.4 (Debian bookworm, the
# Docker base image, ships 7.4).
_CALC_PDF_TARGET = 'pdf:calc_pdf_Export:{"SinglePageSheets":{"type":"boolean","value":"true"}}'
_SPREADSHEET_EXTENSIONS = {"xlsx", "xls", "ods"}


def _convert_target(ext: str) -> str:
    """Return the soffice ``--convert-to`` target for ``ext``."""
    return _CALC_PDF_TARGET if ext in _SPREADSHEET_EXTENSIONS else "pdf"


class ConversionError(Exception):
    """Raised when a document cannot be converted to PDF.

    ``reason`` is a human-readable explanation suitable for surfacing to end
    users (Task 4 turns it into an HTTP 422 detail).
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def sniff_ok(data: bytes, ext: str) -> bool:
    """Return whether ``data``'s leading bytes are plausible for ``ext``."""
    if ext == "txt":
        # Plain text has no magic bytes; NUL-free is the pragmatic test — it
        # still rejects renamed binaries, which all contain NULs early on.
        return b"\x00" not in data[:8192]
    if ext == "webp":
        # RIFF container with the format tag at offset 8.
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    magics = _MAGIC_BYTES.get(ext)
    if magics is None:
        return False
    return any(data.startswith(magic) for magic in magics)


def _extension_of(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


def _find_soffice() -> str | None:
    """Locate the soffice binary via SOFFICE_BIN or the system PATH."""
    return os.environ.get("SOFFICE_BIN") or shutil.which("soffice")


def _validate_pdf(data: bytes) -> int:
    """Return the page count of a well-formed, unencrypted PDF, or raise ConversionError."""
    try:
        reader = PdfReader(io.BytesIO(data))
    except PdfReadError as exc:
        raise ConversionError(f"Could not read PDF: {exc}") from exc
    if reader.is_encrypted:
        raise ConversionError("PDF is password-protected; please upload an unencrypted file.")
    try:
        return len(reader.pages)
    except PdfReadError as exc:
        raise ConversionError(f"Could not read PDF pages: {exc}") from exc


def _convert_image_to_pdf(data: bytes) -> bytes:
    """Draw an image centered on a US-Letter page and return the PDF bytes.

    In-process (Pillow + reportlab), no LibreOffice. The image is scaled
    down to fit inside the page margins but never scaled up — a small logo
    stays small instead of blowing up to a blurry full page. Alpha is
    flattened over white (reportlab can't draw RGBA), and EXIF orientation
    is applied so phone photos come out upright.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "L"):
            flattened = Image.new("RGB", image.size, (255, 255, 255))
            rgba = image.convert("RGBA")
            flattened.paste(rgba, mask=rgba.getchannel("A"))
            image = flattened
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise ConversionError(f"Could not read image: {exc}") from exc

    page_width, page_height = letter
    margin = 36.0  # 0.5"
    scale = min((page_width - 2 * margin) / image.width, (page_height - 2 * margin) / image.height, 1.0)
    draw_width = image.width * scale
    draw_height = image.height * scale

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=letter)
    pdf.drawImage(
        ImageReader(image),
        (page_width - draw_width) / 2,
        (page_height - draw_height) / 2,
        width=draw_width,
        height=draw_height,
    )
    pdf.showPage()
    pdf.save()
    return buf.getvalue()


def _convert_with_soffice(data: bytes, ext: str) -> bytes:
    """Convert office document bytes to PDF bytes via a headless LibreOffice subprocess."""
    soffice = _find_soffice()
    if soffice is None:
        raise ConversionError("LibreOffice is not available on this server; cannot convert this file type.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        infile = tmp_path / f"input.{ext}"
        infile.write_bytes(data)

        try:
            result = subprocess.run(  # noqa: S603
                [soffice, "--headless", "--convert-to", _convert_target(ext), "--outdir", str(tmp_path), str(infile)],
                capture_output=True,
                timeout=_SOFFICE_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ConversionError("Document conversion timed out.") from exc

        outfile = tmp_path / "input.pdf"
        if result.returncode != 0 or not outfile.is_file():
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise ConversionError(f"LibreOffice conversion failed: {stderr or 'unknown error'}")

        return outfile.read_bytes()


def to_pdf_bytes(data: bytes, filename: str, settings: Settings | None = None) -> tuple[bytes, int]:
    """Convert ``data`` (named ``filename``) to PDF and return (pdf_bytes, page_count).

    Pure conversion — no storage involved (callers that just merge or
    inspect the result shouldn't pay a disk round-trip). Raises
    ConversionError for unsupported extensions, magic-byte mismatches,
    encrypted PDFs, or corrupt/unconvertible input.

    With ``settings``, eligible Office formats are first converted through
    Microsoft Graph (Word/PowerPoint's own rendering — see
    ``app.graph_convert``); LibreOffice remains the fallback and, without
    ``settings`` or for spreadsheets, the only engine.
    """
    ext = _extension_of(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ConversionError(f"Unsupported file type: .{ext or '?'}. Allowed types: {sorted(ALLOWED_EXTENSIONS)}.")

    if not sniff_ok(data, ext):
        raise ConversionError(f"File content does not match its .{ext} extension.")

    if ext == "pdf":
        page_count = _validate_pdf(data)
        pdf_bytes = data
    elif ext in _IMAGE_EXTENSIONS:
        pdf_bytes = _convert_image_to_pdf(data)
        page_count = _validate_pdf(pdf_bytes)
    else:
        pdf_bytes = convert_via_graph(data, ext, settings) if settings is not None else None
        if pdf_bytes is not None:
            logger.info("Converted .%s via Graph", ext)
        else:
            pdf_bytes = _convert_with_soffice(data, ext)
        page_count = _validate_pdf(pdf_bytes)

    return pdf_bytes, page_count


def to_pdf(
    data: bytes,
    filename: str,
    storage: FileStorage,
    key_prefix: str,
    settings: Settings | None = None,
) -> tuple[str, int]:
    """`to_pdf_bytes`, plus saving the result under ``key_prefix``; returns (pdf_key, page_count)."""
    pdf_bytes, page_count = to_pdf_bytes(data, filename, settings)
    pdf_key = f"{key_prefix.rstrip('/')}/{uuid.uuid4().hex}.pdf"
    storage.save(pdf_key, pdf_bytes)
    return pdf_key, page_count
