"""PDF stamping: overlay signed field values onto a template PDF, and render
the "Signature Certificate" audit document.

Two public entry points, both pure functions (no DB, no storage) so they're
unit-testable in isolation — ``app.completion`` is responsible for gathering
everything they need (template bytes, field defs, completed submitters +
their users, signature image bytes, audit event rows) and handing them over:

- ``build_signed_pdf``: the document itself, field values stamped and every
  page watermarked. Deliberately does *not* include the certificate — per
  issue #15 the certificate is a separate artifact, linked from the
  completion email and the envelope page rather than merged into the
  document people forward around.
- ``build_certificate_pdf``: the standalone signature-certificate PDF
  (signers, timestamps, IPs, audit trail).

Coordinate system: ``FieldDef`` geometry (``x``/``y``/``w``/``h``) is
normalized (0..1) with a top-left origin, matching how the frontend places
boxes on a rendered page image. PDF page coordinates have a bottom-left
origin, so each field is converted with:

    pdf_x = x * page_w
    pdf_y = page_h - (y + h) * page_h

using the actual page's ``mediabox`` size (pages need not be uniform).
"""

import io
import textwrap
from datetime import UTC, datetime
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.models import Submitter, User

# ReportLab's built-in Helvetica is Latin-1 only: CJK (and most other
# non-Latin) text draws as missing glyphs *silently* — no exception. Any
# string Helvetica can't encode is drawn with this TrueType fallback
# instead. Candidates cover, in order: the Docker image and CI
# (fonts-nanum), Windows dev machines, macOS. Noto CJK is deliberately NOT
# a candidate even though the image ships it for LibreOffice conversion:
# Debian's NotoSansCJK TTCs have PostScript/CFF outlines, which reportlab's
# TTFont cannot embed ("postscript outlines are not supported") —
# NanumGothic is a real TrueType font.
_FALLBACK_FONT_CANDIDATES: list[str] = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
]


def _register_unicode_fallback() -> str | None:
    for path in _FALLBACK_FONT_CANDIDATES:
        try:
            pdfmetrics.registerFont(TTFont("UnicodeFallback", path))
        except Exception:  # noqa: BLE001 — any unusable candidate (missing, unparsable) means "try the next"
            continue
        return "UnicodeFallback"
    return None


UNICODE_FALLBACK_FONT: str | None = _register_unicode_fallback()


def _font_for(text: str, *, bold: bool = False) -> str:
    """Helvetica when it can render ``text``, the Unicode fallback otherwise.

    Falls back to Helvetica (broken glyphs, the pre-fallback behavior) when
    no fallback font could be registered on this machine — never raises.
    The fallback has no bold face; bold non-Latin text renders regular.
    """
    try:
        text.encode("latin-1")
    except UnicodeEncodeError:
        if UNICODE_FALLBACK_FONT is not None:
            return UNICODE_FALLBACK_FONT
    return "Helvetica-Bold" if bold else "Helvetica"


MIN_FONT_SIZE = 6.0
MAX_FONT_SIZE = 14.0
# Text wider than its box shrinks to fit (mirrored by the signing preview's
# fieldTextStyle); this floor stops pathological input reaching size 0.
ABS_MIN_FONT_SIZE = 4.0
_TEXT_INSET = 2.0
_CERT_MARGIN = 54.0  # 0.75in
_WATERMARK_TOP_MARGIN = 0.35 * 72  # 25.2pt, 0.35in
_WATERMARK_FONT_SIZE = 7.0
_WATERMARK_GREY = 0.45
_WATERMARK_LEFT_INSET = 4.0


def build_signed_pdf(
    template_pdf: bytes,
    fields: list[dict[str, Any]],
    submitters: list[Submitter],
    users_by_id: dict[int, User],
    signature_images: dict[str, bytes],
    *,
    envelope_uid: str,
    completed_at: datetime | None,
    status_note: str | None = None,
    attachment_names: dict[str, str] | None = None,
) -> bytes:
    """Stamp each submitter's field values onto ``template_pdf``.

    ``fields`` is a template's full field list (raw dicts, as stored on
    ``Template.fields``). ``submitters`` are the (completed) submitters
    whose values get stamped; a field is only drawn if some submitter in
    the list has ``field["role"] == submitter.role``. ``users_by_id`` maps
    ``Submitter.user_id -> User`` (for name-field text).
    ``signature_images`` maps ``str(signature_id) -> PNG bytes`` for every
    signature referenced by any submitter's ``values``.
    ``attachment_names`` maps ``str(attachment_id) -> filename`` for
    ``attachment`` fields, whose boxes are stamped with a note naming the
    file (the file itself is appended by ``append_attachments``).

    ``completed_at`` is stamped, DocuSign-style, as a small grey watermark
    line ("Pumasi Sign · Envelope <uid> · Completed <iso>") in the top
    margin of every page — see ``_render_watermark_overlay``. ``None``
    marks an in-progress rendition instead ("· In progress") — the
    document-preview endpoint stamps only the submitters who have signed
    so far, so later signers see earlier signatures (DocuSign-style).
    ``status_note`` overrides that default line for terminal renditions
    (DocuSign's VOID-watermark rule: a voided/declined/expired envelope's
    document must say so, not read as live); it's ignored when
    ``completed_at`` is set.
    ``envelope_uid`` is ``Submission.public_uid`` — random, so the stamp
    doesn't reveal how many envelopes have ever been issued.

    Only pages that actually have fields belonging to a submitter in
    ``submitters`` get a field-value reportlab overlay merged in; every
    page (with or without fields) gets the watermark overlay. Returns the
    resulting PDF bytes (same page count as the input — the signature
    certificate is a separate artifact, see ``build_certificate_pdf``).
    """
    reader = PdfReader(io.BytesIO(template_pdf))
    writer = PdfWriter()

    submitters_by_role = {s.role: s for s in submitters}
    fields_by_page: dict[int, list[dict[str, Any]]] = {}
    for field in fields:
        # Labels are role-less sender text, stamped unconditionally; other
        # fields only when a completed submitter owns their role.
        if field.get("type") == "label" or field["role"] in submitters_by_role:
            fields_by_page.setdefault(field["page"], []).append(field)

    status_line = f"Completed {_iso(completed_at)}" if completed_at is not None else status_note or "In progress"
    watermark_text = f"Pumasi Sign · Envelope {envelope_uid} · {status_line}"

    for page_index, page in enumerate(reader.pages):
        page_fields = fields_by_page.get(page_index, [])
        written_page = writer.add_page(page)
        page_w = float(page.mediabox.width)
        page_h = float(page.mediabox.height)
        if page_fields:
            overlay_bytes = _render_field_overlay(
                page_fields,
                submitters_by_role,
                users_by_id,
                signature_images,
                page_w,
                page_h,
                attachment_names or {},
            )
            overlay_page = PdfReader(io.BytesIO(overlay_bytes)).pages[0]
            written_page.merge_page(overlay_page)

        watermark_bytes = _render_watermark_overlay(watermark_text, page_w, page_h)
        watermark_page = PdfReader(io.BytesIO(watermark_bytes)).pages[0]
        written_page.merge_page(watermark_page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def build_certificate_pdf(
    submitters: list[Submitter],
    users_by_id: dict[int, User],
    audit_rows: list[dict[str, Any]],
    *,
    submission_title: str,
    envelope_uid: str,
    template_name: str,
    is_adhoc: bool = False,
) -> bytes:
    """Render the standalone "Signature Certificate" PDF.

    ``audit_rows`` is the submission's full audit trail, each a dict with
    ``event``, ``actor_name``, ``actor_email``, ``ip``, ``created_at`` —
    rendered as a trail in addition to the per-signer summary.

    ``is_adhoc`` (default ``False``) suppresses the per-signer
    "- role: <role>" suffix: for a one-off envelope, ``submitter.role`` is
    an internal ``signer-N`` bookkeeping string (see
    ``routers/submissions.py``'s ad-hoc create path), not something that
    should end up baked permanently into a legal-facing document.
    Template-based envelopes keep it, since there the role is a meaningful
    name the builder chose ("Employee", "Manager").
    """
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    width, height = letter
    y = height - _CERT_MARGIN

    c.setFont("Helvetica-Bold", 18)
    c.drawString(_CERT_MARGIN, y, "Signature Certificate")
    y -= 26

    for line in _wrap(f"Submission: {submission_title} (Envelope {envelope_uid})", 95):
        _draw_cert_line(c, y, line, 11)
        y -= 15
    for line in _wrap(f"Template: {template_name}", 95):
        _draw_cert_line(c, y, line, 11)
        y -= 15
    y -= 10

    c.setFont("Helvetica-Bold", 12)
    c.drawString(_CERT_MARGIN, y, "Signers")
    y -= 18

    for submitter in submitters:
        user = users_by_id.get(submitter.user_id)
        name = user.name if user else "Unknown"
        email = user.email if user else "unknown"
        identity_line = f"{name} <{email}>" if is_adhoc else f"{name} <{email}> - role: {submitter.role}"
        lines = [
            identity_line,
            f"Signed: {_iso(submitter.signed_at)}   IP: {submitter.ip_address or 'N/A'}",
        ]
        for raw_line in lines:
            for line in _wrap(raw_line, 100):
                _draw_cert_line(c, y, line, 10)
                y -= 13
        y -= 6

    if audit_rows:
        y -= 6
        c.setFont("Helvetica-Bold", 12)
        c.drawString(_CERT_MARGIN, y, "Audit Trail")
        y -= 16
        for row in audit_rows:
            actor = row.get("actor_name") or "system"
            email = row.get("actor_email")
            actor_display = f"{actor} <{email}>" if email else actor
            created_str = _iso(row.get("created_at"))
            ip = row.get("ip") or "N/A"
            raw_line = f"{created_str}  {row['event']:<10}  {actor_display}  IP: {ip}"
            for line in _wrap(raw_line, 110):
                _draw_cert_line(c, y, line, 9)
                y -= 11

    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(width / 2, _CERT_MARGIN / 2, "Generated by Pumasi Sign")
    c.save()
    return packet.getvalue()


def _draw_cert_line(c: canvas.Canvas, y: float, text: str, size: float) -> None:
    """One certificate body line at the left margin, in whichever font can render it."""
    c.setFont(_font_for(text), size)
    c.drawString(_CERT_MARGIN, y, text)


def _font_size_for(box_h_pt: float) -> float:
    return max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, box_h_pt * 0.6))


def _fitted_font_size(
    text: str,
    box_w_pt: float,
    box_h_pt: float,
    font_size: float | None = None,
    font_name: str = "Helvetica",
) -> float:
    """The size ``text`` actually renders at, mirrored by the preview.

    Base size: the sender's explicit ``font_size`` when set (clamped to the
    box height so text can't spill vertically), else the height-based auto
    formula. Either way the result shrinks further (down to
    ABS_MIN_FONT_SIZE) so ``text`` fits the box width — what the signer sees
    is what gets stamped. Measured with ``font_name``, the font the text is
    actually drawn in.
    """
    size = min(float(font_size), box_h_pt) if font_size else _font_size_for(box_h_pt)
    available = max(box_w_pt - 2 * _TEXT_INSET, 1.0)
    width = stringWidth(text, font_name, size)
    if width > available:
        size = max(ABS_MIN_FONT_SIZE, size * available / width)
    return size


def _draw_text(
    c: canvas.Canvas,
    text: str,
    pdf_x: float,
    pdf_y: float,
    box_w_pt: float,
    box_h_pt: float,
    font_size: float | None = None,
) -> None:
    font_name = _font_for(text)
    fitted = _fitted_font_size(text, box_w_pt, box_h_pt, font_size, font_name)
    c.setFont(font_name, fitted)
    baseline_y = pdf_y + (box_h_pt - fitted) / 2 + fitted * 0.2
    c.drawString(pdf_x + _TEXT_INSET, baseline_y, text)


def _draw_checkbox_mark(c: canvas.Canvas, pdf_x: float, pdf_y: float, box_w_pt: float, box_h_pt: float) -> None:
    font_size = _font_size_for(box_h_pt)
    c.setFont("Helvetica-Bold", font_size)
    c.drawCentredString(pdf_x + box_w_pt / 2, pdf_y + (box_h_pt - font_size) / 2 + font_size * 0.2, "X")


def trimmed_signature(png_bytes: bytes) -> bytes:
    """Crop a signature PNG to its ink (alpha bounding box), plus a small margin.

    Signatures drawn small on a large pad — or saved by an older pad with
    different proportions — carry big transparent margins; fitting the whole
    canvas into a field box renders the actual ink tiny. Cropping to the ink
    makes every signature fill its field the same way regardless of how it
    was drawn. Best-effort: anything untrimmable (not a PNG, no alpha, fully
    transparent) comes back unchanged.
    """
    try:
        from PIL import Image

        with Image.open(io.BytesIO(png_bytes)) as img:
            rgba = img.convert("RGBA")
            bbox = rgba.getchannel("A").getbbox()
            if bbox is None:
                return png_bytes
            margin = max(2, round(0.03 * max(rgba.width, rgba.height)))
            left = max(0, bbox[0] - margin)
            top = max(0, bbox[1] - margin)
            right = min(rgba.width, bbox[2] + margin)
            bottom = min(rgba.height, bbox[3] + margin)
            if (left, top, right, bottom) == (0, 0, rgba.width, rgba.height):
                return png_bytes
            out = io.BytesIO()
            rgba.crop((left, top, right, bottom)).save(out, "PNG")
            return out.getvalue()
    except Exception:
        return png_bytes


def _draw_signature(
    c: canvas.Canvas,
    png_bytes: bytes,
    pdf_x: float,
    pdf_y: float,
    box_w_pt: float,
    box_h_pt: float,
) -> None:
    image = ImageReader(io.BytesIO(trimmed_signature(png_bytes)))
    c.drawImage(
        image,
        pdf_x,
        pdf_y,
        width=box_w_pt,
        height=box_h_pt,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )


def _draw_field(
    c: canvas.Canvas,
    field: dict[str, Any],
    submitter: Submitter,
    users_by_id: dict[int, User],
    signature_images: dict[str, bytes],
    page_w: float,
    page_h: float,
    attachment_names: dict[str, str],
) -> None:
    pdf_x = field["x"] * page_w
    pdf_y = page_h - (field["y"] + field["h"]) * page_h
    box_w = field["w"] * page_w
    box_h = field["h"] * page_h
    value = submitter.values.get(field["id"])
    field_type = field["type"]

    if field_type in ("signature", "initials"):
        if value is None:
            return
        png_bytes = signature_images.get(str(value))
        if png_bytes is None:
            return
        _draw_signature(c, png_bytes, pdf_x, pdf_y, box_w, box_h)
    elif field_type == "name":
        # Signers may edit their name field; fall back to the account name
        # when no value was submitted (older clients, or the field was left
        # untouched server-side).
        if isinstance(value, str) and value.strip():
            text = value.strip()
        else:
            user = users_by_id.get(submitter.user_id)
            text = user.name if user else ""
        _draw_text(c, text, pdf_x, pdf_y, box_w, box_h, field.get("font_size"))
    elif field_type == "date":
        # The signer's chosen date (validated ISO YYYY-MM-DD) — what they saw
        # in the preview — with signed_at as the fallback when absent.
        if isinstance(value, str) and value:
            text = value
        else:
            text = submitter.signed_at.strftime("%Y-%m-%d") if submitter.signed_at else ""
        _draw_text(c, text, pdf_x, pdf_y, box_w, box_h, field.get("font_size"))
    elif field_type in ("text", "dropdown", "radio"):
        if value:
            _draw_text(c, str(value), pdf_x, pdf_y, box_w, box_h, field.get("font_size"))
    elif field_type == "attachment":
        if value is not None:
            name = attachment_names.get(str(value), "file")
            _draw_text(c, f"[Attached: {name}]", pdf_x, pdf_y, box_w, box_h, field.get("font_size"))
    elif field_type == "checkbox" and value:
        _draw_checkbox_mark(c, pdf_x, pdf_y, box_w, box_h)


def _render_field_overlay(
    page_fields: list[dict[str, Any]],
    submitters_by_role: dict[str, Submitter],
    users_by_id: dict[int, User],
    signature_images: dict[str, bytes],
    page_w: float,
    page_h: float,
    attachment_names: dict[str, str],
) -> bytes:
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_w, page_h))
    for field in page_fields:
        if field["type"] == "label":
            text = (field.get("default_value") or "").strip()
            if text:
                pdf_x = field["x"] * page_w
                pdf_y = page_h - (field["y"] + field["h"]) * page_h
                _draw_text(c, text, pdf_x, pdf_y, field["w"] * page_w, field["h"] * page_h, field.get("font_size"))
            continue
        submitter = submitters_by_role[field["role"]]
        _draw_field(c, field, submitter, users_by_id, signature_images, page_w, page_h, attachment_names)
    c.save()
    return packet.getvalue()


def append_attachments(pdf_bytes: bytes, attachments: list[tuple[str, bytes]]) -> bytes:
    """Append each ``(filename, file bytes)`` attachment to ``pdf_bytes``.

    PDF attachments contribute their pages verbatim; PNG/JPEG images each
    become one letter-size page with a header naming the file and the image
    aspect-fit inside the margins. Unrecognized bytes (unreachable — the
    upload endpoint sniffs magic) are skipped rather than failing the whole
    completion. No-op (input returned as-is) with an empty list.
    """
    if not attachments:
        return pdf_bytes

    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
        writer.add_page(page)

    for filename, data in attachments:
        if data.startswith(b"%PDF"):
            for page in PdfReader(io.BytesIO(data)).pages:
                writer.add_page(page)
        elif data.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")):
            for page in PdfReader(io.BytesIO(_image_attachment_page(filename, data))).pages:
                writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _image_attachment_page(filename: str, image_bytes: bytes) -> bytes:
    """One letter-size PDF page: an "Attachment: <name>" header and the image
    aspect-fit within the margins."""
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    width, height = letter

    header = f"Attachment: {filename}"
    c.setFont(_font_for(header), 11)
    c.drawString(_CERT_MARGIN, height - _CERT_MARGIN, header)

    image = ImageReader(io.BytesIO(image_bytes))
    frame_x = _CERT_MARGIN
    frame_y = _CERT_MARGIN
    frame_w = width - 2 * _CERT_MARGIN
    frame_h = height - 2 * _CERT_MARGIN - 24  # room for the header line
    c.drawImage(
        image,
        frame_x,
        frame_y,
        width=frame_w,
        height=frame_h,
        preserveAspectRatio=True,
        anchor="n",
        mask="auto",
    )
    c.save()
    return packet.getvalue()


def _render_watermark_overlay(text: str, page_w: float, page_h: float) -> bytes:
    """Render a single-line grey watermark in a page's top-left margin, DocuSign-style.

    The overlay canvas is created at the target page's own ``(page_w,
    page_h)``, so ``merge_page`` never needs to rescale or rotate it onto
    the underlying page. ``x``/``y`` are clamped into ``[0, page_w]`` /
    ``[0, page_h]`` so an unusually small page still gets a watermark
    (possibly outside its intended 0.35in margin) instead of this function
    raising and taking down the whole stamping run.
    """
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_w, page_h))
    c.setFont("Helvetica", _WATERMARK_FONT_SIZE)
    c.setFillGray(_WATERMARK_GREY)

    x = max(0.0, min(_WATERMARK_LEFT_INSET, page_w))
    top_margin = min(_WATERMARK_TOP_MARGIN, page_h)
    y = max(0.0, min(page_h - top_margin, page_h))
    c.drawString(x, y, text)
    c.save()
    return packet.getvalue()


def _wrap(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width) or [""]


def _iso(value: datetime | None) -> str:
    if value is None:
        return "N/A"
    dt = value if value.tzinfo else value.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()
