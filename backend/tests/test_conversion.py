"""Tests for app.conversion: pdf passthrough, LibreOffice conversion, and validation."""

import io
import shutil
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.conversion import ALLOWED_EXTENSIONS, ConversionError, _convert_target, sniff_ok, to_pdf
from app.storage import LocalVolumeStorage

FIXTURES = Path(__file__).parent / "fixtures"

no_soffice = pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice not installed")

# Font-family substrings that indicate a CJK-capable face got picked during
# conversion. Covers the fonts realistically present per platform: Noto CJK
# (Linux, the Docker image and CI), Malgun/Gulim/Batang/Dotum (Windows),
# Apple SD Gothic (macOS), Nanum/UnDotum/Baekmuk (other Linux setups).
_CJK_FONT_MARKERS = (
    "notosanscjk",
    "notoserifcjk",
    "notosanskr",
    "sourcehans",
    "malgun",
    "gulim",
    "batang",
    "dotum",
    "nanum",
    "applesdgothic",
    "baekmuk",
)


def _embedded_font_names(pdf_bytes: bytes) -> set[str]:
    """Every /BaseFont name referenced by any page, subset prefixes stripped."""
    names: set[str] = set()
    for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
        fonts = page.get("/Resources", {}).get("/Font", {})
        for font in fonts.values():
            base = str(font.get_object().get("/BaseFont", ""))
            names.add(base.lstrip("/").split("+")[-1])
    return names


def test_allowed_extensions() -> None:
    assert {
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
        "png",
        "jpg",
        "jpeg",
        "gif",
        "webp",
        "bmp",
        "tif",
        "tiff",
    } == ALLOWED_EXTENSIONS


def test_sniff_ok_pdf_magic_bytes() -> None:
    data = (FIXTURES / "sample.pdf").read_bytes()
    assert sniff_ok(data, "pdf") is True


def test_sniff_ok_docx_magic_bytes() -> None:
    data = (FIXTURES / "sample.docx").read_bytes()
    assert sniff_ok(data, "docx") is True


def test_sniff_ok_xlsx_magic_bytes() -> None:
    data = (FIXTURES / "sample.xlsx").read_bytes()
    assert sniff_ok(data, "xlsx") is True


def test_sniff_ok_pptx_magic_bytes() -> None:
    data = (FIXTURES / "sample.pptx").read_bytes()
    assert sniff_ok(data, "pptx") is True


def test_sniff_ok_ppt_magic_bytes() -> None:
    # Legacy .ppt files are OLE compound documents; only the header matters for sniffing.
    data = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100
    assert sniff_ok(data, "ppt") is True
    assert sniff_ok(b"not an ole file", "ppt") is False


def test_sniff_ok_legacy_office_magic_bytes() -> None:
    # .doc and .xls share the OLE compound-document header with .ppt.
    ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100
    assert sniff_ok(ole, "doc") is True
    assert sniff_ok(ole, "xls") is True
    assert sniff_ok(b"not an ole file", "doc") is False


def test_sniff_ok_opendocument_and_rtf_magic_bytes() -> None:
    zip_header = b"PK\x03\x04" + b"\x00" * 100
    assert sniff_ok(zip_header, "odt") is True
    assert sniff_ok(zip_header, "ods") is True
    assert sniff_ok(zip_header, "odp") is True
    assert sniff_ok(b"{\\rtf1\\ansi Hello}", "rtf") is True
    assert sniff_ok(b"plain text, not rtf", "rtf") is False


def test_sniff_ok_image_magic_bytes() -> None:
    assert sniff_ok(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20, "png") is True
    assert sniff_ok(b"\xff\xd8\xff\xe0" + b"\x00" * 20, "jpg") is True
    assert sniff_ok(b"\xff\xd8\xff\xe1" + b"\x00" * 20, "jpeg") is True
    assert sniff_ok(b"GIF89a" + b"\x00" * 20, "gif") is True
    assert sniff_ok(b"BM" + b"\x00" * 20, "bmp") is True
    # TIFF has two byte orders.
    assert sniff_ok(b"II*\x00" + b"\x00" * 20, "tiff") is True
    assert sniff_ok(b"MM\x00*" + b"\x00" * 20, "tif") is True
    # WebP is a RIFF container whose format tag sits at offset 8.
    assert sniff_ok(b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 20, "webp") is True
    assert sniff_ok(b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 20, "webp") is False
    assert sniff_ok(b"\x89PNG\r\n\x1a\n", "jpg") is False


def test_sniff_ok_txt_accepts_text_rejects_binary() -> None:
    # .txt has no magic bytes; anything NUL-free counts as text (this still
    # rejects renamed binaries, which all contain NULs early on).
    assert sniff_ok(b"Hello, plain text.\nSecond line.", "txt") is True
    assert sniff_ok("한국어 텍스트도 괜찮다.".encode(), "txt") is True
    assert sniff_ok(b"binary\x00blob", "txt") is False


def test_sniff_ok_rejects_mismatched_magic_bytes() -> None:
    data = (FIXTURES / "sample.docx").read_bytes()
    assert sniff_ok(data, "pdf") is False


def test_sniff_ok_rejects_garbage() -> None:
    assert sniff_ok(b"not a real file at all", "pdf") is False
    assert sniff_ok(b"not a real file at all", "docx") is False


def test_pdf_passthrough_returns_page_count(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)
    data = (FIXTURES / "sample.pdf").read_bytes()

    pdf_key, page_count = to_pdf(data, "sample.pdf", storage, "templates/1")

    assert page_count == 2
    assert pdf_key.startswith("templates/1/")
    assert pdf_key.endswith(".pdf")
    assert storage.open(pdf_key) == data


def test_encrypted_pdf_raises_conversion_error(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)
    data = (FIXTURES / "sample-encrypted.pdf").read_bytes()

    with pytest.raises(ConversionError) as exc_info:
        to_pdf(data, "sample-encrypted.pdf", storage, "templates/1")

    assert exc_info.value.reason


def test_bad_magic_bytes_raises_conversion_error(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)
    data = b"this is not a pdf at all, just plain text"

    with pytest.raises(ConversionError) as exc_info:
        to_pdf(data, "sample.pdf", storage, "templates/1")

    assert exc_info.value.reason


def test_unsupported_extension_raises_conversion_error(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)
    data = b"hello"

    with pytest.raises(ConversionError) as exc_info:
        to_pdf(data, "sample.exe", storage, "templates/1")

    assert exc_info.value.reason


def test_corrupt_pdf_raises_conversion_error(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)
    # Valid magic bytes but truncated/corrupt body.
    data = b"%PDF-1.4\n%garbage, not a real pdf structure"

    with pytest.raises(ConversionError) as exc_info:
        to_pdf(data, "sample.pdf", storage, "templates/1")

    assert exc_info.value.reason


def test_convert_target_uses_single_page_sheets_for_spreadsheets() -> None:
    for ext in ("xlsx", "xls", "ods"):
        target = _convert_target(ext)
        assert target.startswith("pdf:calc_pdf_Export:"), ext
        assert "SinglePageSheets" in target, ext


def test_convert_target_is_plain_pdf_for_non_spreadsheets() -> None:
    assert _convert_target("docx") == "pdf"
    assert _convert_target("pptx") == "pdf"
    assert _convert_target("ppt") == "pdf"
    assert _convert_target("doc") == "pdf"
    assert _convert_target("txt") == "pdf"


def _png_bytes(width: int = 320, height: int = 200, mode: str = "RGB") -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new(mode, (width, height), (200, 30, 60) if mode == "RGB" else (200, 30, 60, 128)).save(buf, format="PNG")
    return buf.getvalue()


def test_png_converts_to_single_letter_page(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)

    pdf_key, page_count = to_pdf(_png_bytes(), "photo.png", storage, "templates/1")

    assert page_count == 1
    converted = storage.open(pdf_key)
    assert converted.startswith(b"%PDF")
    page = PdfReader(io.BytesIO(converted)).pages[0]
    assert round(float(page.mediabox.width)) == 612  # US Letter
    assert round(float(page.mediabox.height)) == 792


def test_jpeg_converts_to_pdf(tmp_path: Path) -> None:
    from PIL import Image

    storage = LocalVolumeStorage(tmp_path)
    buf = io.BytesIO()
    Image.new("RGB", (2000, 500), (10, 120, 200)).save(buf, format="JPEG")

    _, page_count = to_pdf(buf.getvalue(), "scan.JPG", storage, "templates/1")

    assert page_count == 1


def test_transparent_png_converts_to_pdf(tmp_path: Path) -> None:
    # Alpha channels must be flattened (reportlab can't draw RGBA directly).
    storage = LocalVolumeStorage(tmp_path)

    _, page_count = to_pdf(_png_bytes(mode="RGBA"), "logo.png", storage, "templates/1")

    assert page_count == 1


def test_decompression_bomb_image_raises_conversion_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A huge-pixel-count image must 422 as a ConversionError, not crash the
    # request with Pillow's DecompressionBombError (which is not an OSError).
    from PIL import Image

    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    storage = LocalVolumeStorage(tmp_path)

    with pytest.raises(ConversionError) as exc_info:
        to_pdf(_png_bytes(width=100, height=100), "bomb.png", storage, "templates/1")

    assert exc_info.value.reason


def test_corrupt_image_raises_conversion_error(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)
    # Valid PNG magic bytes but garbage body.
    data = b"\x89PNG\r\n\x1a\n" + b"garbage" * 10

    with pytest.raises(ConversionError) as exc_info:
        to_pdf(data, "broken.png", storage, "templates/1")

    assert exc_info.value.reason


@no_soffice
def test_txt_converts_to_pdf(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)
    data = b"Pumasi Sign plain-text sample.\nSecond line.\n"

    pdf_key, page_count = to_pdf(data, "notes.txt", storage, "templates/1")

    assert page_count >= 1
    assert storage.open(pdf_key).startswith(b"%PDF")


@no_soffice
def test_docx_converts_to_pdf(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)
    data = (FIXTURES / "sample.docx").read_bytes()

    pdf_key, page_count = to_pdf(data, "sample.docx", storage, "templates/1")

    assert page_count >= 1
    assert pdf_key.endswith(".pdf")
    converted = storage.open(pdf_key)
    assert converted.startswith(b"%PDF")


@no_soffice
def test_korean_docx_embeds_cjk_font(tmp_path: Path) -> None:
    # korean.docx's body is Korean-only. Without a CJK font installed,
    # LibreOffice substitutes a Latin face and renders every glyph as a tofu
    # box — and the converted PDF embeds no CJK font at all. The Docker
    # image and CI install fonts-noto-cjk so this must pass there.
    storage = LocalVolumeStorage(tmp_path)
    data = (FIXTURES / "korean.docx").read_bytes()

    pdf_key, _ = to_pdf(data, "korean.docx", storage, "templates/1")

    fonts = _embedded_font_names(storage.open(pdf_key))
    normalized = {name.lower().replace(" ", "") for name in fonts}
    assert any(marker in name for name in normalized for marker in _CJK_FONT_MARKERS), (
        f"no CJK-capable font embedded; got {sorted(fonts)}"
    )


@no_soffice
def test_office_fonts_docx_keeps_metric_compatible_fonts(tmp_path: Path) -> None:
    # office-fonts.docx has explicit Calibri and Cambria runs — the fonts
    # nearly every real Office upload uses. The converted PDF must embed
    # either the real fonts (Windows/macOS, where they exist) or their
    # metric-compatible substitutes (Carlito/Caladea, installed in the
    # Docker image and CI). An arbitrary fallback (DejaVu/Noto) has
    # different widths and visibly reflows the document.
    storage = LocalVolumeStorage(tmp_path)
    data = (FIXTURES / "office-fonts.docx").read_bytes()

    pdf_key, _ = to_pdf(data, "office-fonts.docx", storage, "templates/1")

    normalized = {name.lower().replace(" ", "") for name in _embedded_font_names(storage.open(pdf_key))}
    assert any("calibri" in n or "carlito" in n for n in normalized), (
        f"Calibri run lost its metrics; embedded fonts: {sorted(normalized)}"
    )
    assert any("cambria" in n or "caladea" in n for n in normalized), (
        f"Cambria run lost its metrics; embedded fonts: {sorted(normalized)}"
    )


@no_soffice
def test_xlsx_converts_to_pdf(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)
    data = (FIXTURES / "sample.xlsx").read_bytes()

    pdf_key, page_count = to_pdf(data, "sample.xlsx", storage, "templates/1")

    assert page_count >= 1
    assert pdf_key.endswith(".pdf")
    converted = storage.open(pdf_key)
    assert converted.startswith(b"%PDF")


@no_soffice
def test_wide_xlsx_converts_to_one_page_per_sheet(tmp_path: Path) -> None:
    # sample-wide.xlsx has two sheets, one far wider than a portrait page.
    # Without SinglePageSheets, LibreOffice tiles the wide sheet across many
    # pages; with it, each sheet lands on exactly one page.
    storage = LocalVolumeStorage(tmp_path)
    data = (FIXTURES / "sample-wide.xlsx").read_bytes()

    _, page_count = to_pdf(data, "sample-wide.xlsx", storage, "templates/1")

    assert page_count == 2


@no_soffice
def test_pptx_converts_to_pdf(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)
    data = (FIXTURES / "sample.pptx").read_bytes()

    pdf_key, page_count = to_pdf(data, "sample.pptx", storage, "templates/1")

    assert page_count >= 1
    assert pdf_key.endswith(".pdf")
    converted = storage.open(pdf_key)
    assert converted.startswith(b"%PDF")
