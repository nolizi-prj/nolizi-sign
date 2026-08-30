"""Unit tests for app.stamping.build_signed_pdf — no DB, no storage.

Submitter/User are real SQLAlchemy declarative model instances, just never
persisted or attached to a session; build_signed_pdf only touches plain
columns (never relationships), so this is safe.
"""

import base64
import io
from datetime import UTC, datetime

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app import stamping
from app.models import Submitter, User
from app.stamping import build_certificate_pdf, build_signed_pdf

# A real (tiny, 1x1) PNG, base64-encoded — same fixture used in test_signing.py.
PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
PNG_BYTES = base64.b64decode(PNG_B64)


def _make_pdf(width: float, height: float, pages: int = 1) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    for i in range(pages):
        c.drawString(10, 10, f"page {i}")
        c.showPage()
    c.save()
    return buf.getvalue()


def _text_field(field_id: str, *, x: float = 0.5, y: float = 0.5, w: float = 0.2, h: float = 0.05) -> dict:
    return {
        "id": field_id,
        "type": "text",
        "role": "Signer 1",
        "page": 0,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "required": True,
    }


def _submitter(*, role: str = "Signer 1", user_id: int = 1, values: dict | None = None) -> Submitter:
    return Submitter(
        id=1,
        submission_id=1,
        user_id=user_id,
        role=role,
        status="completed",
        signed_at=datetime(2026, 7, 30, 12, 0, 0, tzinfo=UTC),
        ip_address="203.0.113.5",
        values=values or {},
    )


def _user(user_id: int = 1, name: str = "Jane Signer", email: str = "jane@example.com") -> User:
    return User(id=user_id, email=email, name=name, is_admin=False)


COMPLETED_AT = datetime(2026, 7, 30, 12, 0, 0, tzinfo=UTC)
ENVELOPE_UID = "4f5c2e91b7a04d3e9c12ab34cd56ef78"


def test_build_signed_pdf_stamps_text_value_without_certificate_page() -> None:
    """The signed PDF is the document alone: the signature certificate is a
    separate artifact (``build_certificate_pdf``), no longer appended."""
    template_pdf = _make_pdf(400, 300, pages=1)
    fields = [_text_field("f1")]
    submitter = _submitter(values={"f1": "Hello World"})
    users_by_id = {1: _user()}

    result = build_signed_pdf(
        template_pdf,
        fields,
        [submitter],
        users_by_id,
        {},
        envelope_uid=ENVELOPE_UID,
        completed_at=COMPLETED_AT,
    )

    reader = PdfReader(io.BytesIO(result))
    assert len(reader.pages) == 1  # document pages only — no certificate page

    page1_text = reader.pages[0].extract_text()
    assert "Hello World" in page1_text
    assert "Signature Certificate" not in page1_text


def test_korean_text_field_stamps_readable_text() -> None:
    """Non-Latin field values must render via the Unicode fallback font —
    Helvetica silently drops CJK glyphs (no exception, broken output)."""
    if stamping.UNICODE_FALLBACK_FONT is None:
        pytest.skip("no Unicode fallback font available on this machine")
    template_pdf = _make_pdf(400, 300, pages=1)
    fields = [_text_field("f1")]
    submitter = _submitter(values={"f1": "법인 인감 날인"})
    users_by_id = {1: _user()}

    result = build_signed_pdf(
        template_pdf,
        fields,
        [submitter],
        users_by_id,
        {},
        envelope_uid=ENVELOPE_UID,
        completed_at=COMPLETED_AT,
    )

    # Extraction only round-trips when a real Unicode-capable font drew the
    # text (Helvetica would leave mojibake or nothing) — the registered
    # alias itself never appears in the PDF, only the font's internal name.
    page_text = PdfReader(io.BytesIO(result)).pages[0].extract_text()
    assert "법인 인감 날인" in page_text


def test_ascii_text_field_still_uses_helvetica() -> None:
    result = build_signed_pdf(
        _make_pdf(400, 300, pages=1),
        [_text_field("f1")],
        [_submitter(values={"f1": "Hello World"})],
        {1: _user()},
        {},
        envelope_uid=ENVELOPE_UID,
        completed_at=COMPLETED_AT,
    )

    assert b"Helvetica" in result


def test_korean_signer_name_on_certificate() -> None:
    if stamping.UNICODE_FALLBACK_FONT is None:
        pytest.skip("no Unicode fallback font available on this machine")
    submitter = _submitter()
    users_by_id = {1: _user(name="윤영목")}

    result = build_certificate_pdf(
        [submitter],
        users_by_id,
        [],
        submission_title="한국 지사 계약서",
        envelope_uid=ENVELOPE_UID,
        template_name="Test Template",
    )

    cert_text = PdfReader(io.BytesIO(result)).pages[0].extract_text()
    assert "윤영목" in cert_text
    assert "한국 지사 계약서" in cert_text


def test_build_certificate_pdf_contains_signers_and_audit_trail() -> None:
    submitter = _submitter()
    users_by_id = {1: _user()}
    audit_rows = [
        {
            "event": "signed",
            "actor_name": "Jane Signer",
            "actor_email": "jane@example.com",
            "ip": "203.0.113.5",
            "created_at": datetime(2026, 7, 30, 12, 0, 0, tzinfo=UTC),
        },
    ]

    result = build_certificate_pdf(
        [submitter],
        users_by_id,
        audit_rows,
        submission_title="Test Submission",
        envelope_uid=ENVELOPE_UID,
        template_name="Test Template",
    )

    cert_text = PdfReader(io.BytesIO(result)).pages[0].extract_text()
    assert "Signature Certificate" in cert_text
    assert "Jane Signer" in cert_text
    assert "Test Submission" in cert_text
    assert f"(Envelope {ENVELOPE_UID})" in cert_text
    assert "Audit Trail" in cert_text
    assert "Generated by Pumasi Sign" in cert_text


def test_build_certificate_pdf_includes_role_by_default() -> None:
    """Template-based envelopes: the role suffix is meaningful ("Employee",
    "Manager", ...) and should stay on the certificate. Not passing
    ``is_adhoc`` at all exercises its default (``False``)."""
    result = build_certificate_pdf(
        [_submitter()],
        {1: _user()},
        [],
        submission_title="Template Submission",
        envelope_uid=ENVELOPE_UID,
        template_name="Template",
    )

    cert_text = PdfReader(io.BytesIO(result)).pages[-1].extract_text()
    assert "role: Signer 1" in cert_text


def test_build_signed_pdf_certificate_omits_role_for_adhoc() -> None:
    """Ad-hoc (one-off) envelopes: ``submitter.role`` is an internal
    ``signer-N`` bookkeeping string, never meant to be user-facing — it
    must not get baked permanently into the certificate."""
    result = build_certificate_pdf(
        [_submitter(role="signer-1")],
        {1: _user()},
        [],
        submission_title="One-off Submission",
        envelope_uid=ENVELOPE_UID,
        template_name="One-off Submission",
        is_adhoc=True,
    )

    cert_text = PdfReader(io.BytesIO(result)).pages[-1].extract_text()
    assert "role:" not in cert_text
    assert "signer-1" not in cert_text
    assert "Jane Signer" in cert_text  # name/email still present, just no role suffix


def test_build_signed_pdf_watermarks_every_document_page() -> None:
    template_pdf = _make_pdf(400, 300, pages=3)
    fields = [_text_field("f1")]  # only page 0 has a field
    submitter = _submitter(values={"f1": "Hello World"})
    users_by_id = {1: _user()}

    result = build_signed_pdf(
        template_pdf,
        fields,
        [submitter],
        users_by_id,
        {},
        envelope_uid=ENVELOPE_UID,
        completed_at=COMPLETED_AT,
    )

    reader = PdfReader(io.BytesIO(result))
    assert len(reader.pages) == 3  # document pages only

    for page in reader.pages:
        text = page.extract_text()
        assert f"Envelope {ENVELOPE_UID}" in text
        assert "Envelope #" not in text
        assert "Completed 2026-07-30T12:00:00+00:00" in text


def test_build_signed_pdf_watermarks_unusually_small_page_without_raising() -> None:
    template_pdf = _make_pdf(10, 10, pages=1)  # far smaller than the 0.35in top margin
    result = build_signed_pdf(
        template_pdf,
        [],
        [],
        {},
        {},
        envelope_uid=ENVELOPE_UID,
        completed_at=COMPLETED_AT,
    )

    reader = PdfReader(io.BytesIO(result))
    assert len(reader.pages) == 1
    assert f"Envelope {ENVELOPE_UID}" in reader.pages[0].extract_text()


def test_build_signed_pdf_places_signature_image_without_raising() -> None:
    template_pdf = _make_pdf(400, 300, pages=1)
    fields = [
        {
            "id": "sig1",
            "type": "signature",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.1,
            "w": 0.3,
            "h": 0.1,
            "required": True,
        },
    ]
    submitter = _submitter(values={"sig1": 7})
    users_by_id = {1: _user()}
    signature_images = {"7": PNG_BYTES}

    result = build_signed_pdf(
        template_pdf,
        fields,
        [submitter],
        users_by_id,
        signature_images,
        envelope_uid=ENVELOPE_UID,
        completed_at=COMPLETED_AT,
    )

    reader = PdfReader(io.BytesIO(result))
    assert len(reader.pages) == 1


def test_build_signed_pdf_places_initials_image_without_raising() -> None:
    template_pdf = _make_pdf(400, 300, pages=1)
    fields = [
        {
            "id": "ini1",
            "type": "initials",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.1,
            "w": 0.09,
            "h": 0.05,
            "required": True,
        },
    ]
    submitter = _submitter(values={"ini1": 7})

    result = build_signed_pdf(
        template_pdf,
        fields,
        [submitter],
        {1: _user()},
        {"7": PNG_BYTES},
        envelope_uid=ENVELOPE_UID,
        completed_at=COMPLETED_AT,
    )

    assert len(PdfReader(io.BytesIO(result)).pages) == 1


def test_build_signed_pdf_stamps_name_date_checkbox() -> None:
    template_pdf = _make_pdf(400, 300, pages=1)
    fields = [
        {
            "id": "name1",
            "type": "name",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.1,
            "w": 0.3,
            "h": 0.05,
            "required": True,
        },
        {
            "id": "date1",
            "type": "date",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.2,
            "w": 0.3,
            "h": 0.05,
            "required": True,
        },
        {
            "id": "chk1",
            "type": "checkbox",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.3,
            "w": 0.05,
            "h": 0.05,
            "required": False,
        },
    ]
    submitter = _submitter(values={"chk1": True})
    users_by_id = {1: _user(name="Checked Signer")}

    result = build_signed_pdf(
        template_pdf,
        fields,
        [submitter],
        users_by_id,
        {},
        envelope_uid=ENVELOPE_UID,
        completed_at=COMPLETED_AT,
    )

    reader = PdfReader(io.BytesIO(result))
    page_text = reader.pages[0].extract_text()
    assert "Checked Signer" in page_text
    assert "2026-07-30" in page_text  # no date value supplied — falls back to submitter.signed_at
    assert "X" in page_text


def test_build_signed_pdf_stamps_submitted_name_and_date_values() -> None:
    """A signer-edited name and a signer-picked date take precedence over the
    account name / signed_at fallbacks — what the signer previewed is what
    gets stamped."""
    template_pdf = _make_pdf(400, 300, pages=1)
    fields = [
        {
            "id": "name1",
            "type": "name",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.1,
            "w": 0.3,
            "h": 0.05,
            "required": True,
        },
        {
            "id": "date1",
            "type": "date",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.2,
            "w": 0.3,
            "h": 0.05,
            "required": True,
        },
    ]
    submitter = _submitter(values={"name1": "Preferred Name", "date1": "2026-01-15"})
    users_by_id = {1: _user(name="Account Name")}

    result = build_signed_pdf(
        template_pdf,
        fields,
        [submitter],
        users_by_id,
        {},
        envelope_uid=ENVELOPE_UID,
        # Distinct from signed_at (2026-07-30) so the watermark line can't
        # mask the "signed_at was not stamped" assertion below.
        completed_at=datetime(2026, 6, 1, 9, 0, 0, tzinfo=UTC),
    )

    page_text = PdfReader(io.BytesIO(result)).pages[0].extract_text()
    assert "Preferred Name" in page_text
    assert "Account Name" not in page_text
    assert "2026-01-15" in page_text
    assert "2026-07-30" not in page_text


def test_build_signed_pdf_stamps_label_fields_unconditionally() -> None:
    """Sender-authored label text is part of the document: stamped even
    though no submitter's role matches it (labels are role-less)."""
    template_pdf = _make_pdf(400, 300, pages=1)
    fields = [
        {
            "id": "lbl1",
            "type": "label",
            "role": "",
            "page": 0,
            "x": 0.1,
            "y": 0.1,
            "w": 0.5,
            "h": 0.05,
            "required": False,
            "default_value": "Sender wrote this",
        },
        _text_field("f1"),
    ]
    submitter = _submitter(values={"f1": "signer text"})

    result = build_signed_pdf(
        template_pdf,
        fields,
        [submitter],
        {1: _user()},
        {},
        envelope_uid=ENVELOPE_UID,
        completed_at=COMPLETED_AT,
    )

    page_text = PdfReader(io.BytesIO(result)).pages[0].extract_text()
    assert "Sender wrote this" in page_text
    assert "signer text" in page_text


def test_explicit_font_size_overrides_auto_and_clamps_to_box() -> None:
    """A sender-set font_size replaces the height-based auto size, clamped to
    the box height (text can't spill vertically) and still shrunk to fit the
    box width — the same rule the preview applies."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    from app.stamping import _TEXT_INSET, _fitted_font_size

    box_w, box_h = 400.0, 40.0
    # Auto for a 40pt box would cap at 14; explicit 24 must win.
    assert _fitted_font_size("Hi", box_w, box_h, font_size=24) == 24.0
    # Bigger than the box height: clamped to it.
    assert _fitted_font_size("Hi", box_w, box_h, font_size=60) == box_h
    # Width shrink still applies on top of the explicit size.
    long_text = "This long value cannot fit at 24pt in the available width " * 2
    fitted = _fitted_font_size(long_text, box_w, box_h, font_size=24)
    assert fitted < 24.0
    assert stringWidth(long_text, "Helvetica", fitted) <= box_w - 2 * _TEXT_INSET + 0.01


def test_long_text_shrinks_to_fit_box_width() -> None:
    """WYSIWYG: text wider than its box shrinks (down to a hard floor) so the
    stamped output stays inside the box, exactly like the signing preview."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    from app.stamping import _TEXT_INSET, _fitted_font_size

    box_w, box_h = 150.0, 20.0
    short_size = _fitted_font_size("Hi", box_w, box_h)
    long_text = "A rather long value that cannot possibly fit in a 150pt box"
    long_size = _fitted_font_size(long_text, box_w, box_h)

    assert long_size < short_size
    assert stringWidth(long_text, "Helvetica", long_size) <= box_w - 2 * _TEXT_INSET + 0.01
    # The floor keeps pathological input from reaching size 0.
    assert _fitted_font_size("x" * 5000, box_w, box_h) >= 4.0


def test_build_signed_pdf_skips_pages_without_fields() -> None:
    template_pdf = _make_pdf(400, 300, pages=3)
    fields = [_text_field("f1")]  # only on page 0
    submitter = _submitter(values={"f1": "only page zero"})
    users_by_id = {1: _user()}

    result = build_signed_pdf(
        template_pdf,
        fields,
        [submitter],
        users_by_id,
        {},
        envelope_uid=ENVELOPE_UID,
        completed_at=COMPLETED_AT,
    )

    reader = PdfReader(io.BytesIO(result))
    assert len(reader.pages) == 3  # document pages only
    assert "only page zero" in reader.pages[0].extract_text()
    assert "only page zero" not in reader.pages[1].extract_text()
    assert "only page zero" not in reader.pages[2].extract_text()


# --- signature whitespace trimming ----------------------------------------


def _ink_png(canvas_size: tuple[int, int], ink_box: tuple[int, int, int, int]) -> bytes:
    """A transparent PNG of ``canvas_size`` with opaque 'ink' only inside ``ink_box``."""
    from PIL import Image

    img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    ink = Image.new("RGBA", (ink_box[2] - ink_box[0], ink_box[3] - ink_box[1]), (20, 20, 60, 255))
    img.paste(ink, (ink_box[0], ink_box[1]))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_trimmed_signature_crops_transparent_margins() -> None:
    """A signature drawn small on a big pad must crop to its ink (plus a
    small breathing margin), so it no longer renders tiny in the field."""
    from PIL import Image

    from app.stamping import trimmed_signature

    png = _ink_png((400, 200), (10, 150, 90, 190))  # ink in the bottom-left corner

    with Image.open(io.BytesIO(trimmed_signature(png))) as out:
        # Ink is 80x40; the crop keeps a small (~3%) breathing margin.
        assert out.width < 120, f"width {out.width} — margins not cropped"
        assert out.height < 70, f"height {out.height} — margins not cropped"


def test_trimmed_signature_keeps_full_ink_image() -> None:
    from PIL import Image

    from app.stamping import trimmed_signature

    png = _ink_png((300, 120), (0, 0, 300, 120))  # ink everywhere

    with Image.open(io.BytesIO(trimmed_signature(png))) as out:
        assert (out.width, out.height) == (300, 120)


def test_trimmed_signature_survives_blank_or_garbage_input() -> None:
    """Anything untrimmable comes back unchanged — trimming is best-effort."""
    from PIL import Image

    from app.stamping import trimmed_signature

    assert trimmed_signature(b"not a png") == b"not a png"

    img = Image.new("RGBA", (200, 100), (0, 0, 0, 0))  # fully transparent
    buf = io.BytesIO()
    img.save(buf, "PNG")
    assert trimmed_signature(buf.getvalue()) == buf.getvalue()


def test_build_signed_pdf_stamps_status_note_on_terminal_envelopes() -> None:
    """A dead envelope's rendition must say so on every page (DocuSign's VOID
    watermark rule): ``status_note`` replaces the default "In progress" line
    when there's no completion timestamp."""
    template_pdf = _make_pdf(400, 300, pages=2)

    result = build_signed_pdf(
        template_pdf,
        [],
        [],
        {},
        {},
        envelope_uid=ENVELOPE_UID,
        completed_at=None,
        status_note="Voided",
    )

    for page in PdfReader(io.BytesIO(result)).pages:
        text = page.extract_text()
        assert "Voided" in text
        assert "In progress" not in text


def test_build_signed_pdf_defaults_to_in_progress_without_status_note() -> None:
    template_pdf = _make_pdf(400, 300, pages=1)

    result = build_signed_pdf(
        template_pdf,
        [],
        [],
        {},
        {},
        envelope_uid=ENVELOPE_UID,
        completed_at=None,
    )

    assert "In progress" in PdfReader(io.BytesIO(result)).pages[0].extract_text()
