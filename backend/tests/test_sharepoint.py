"""Tests for app.sharepoint: path building, uploads, and archive_submission.

Seams mirror test_mailer.py: ``app.sharepoint._acquire_token`` is
monkeypatched (rebinding of ``app.graph.acquire_token``), and
``transport=httpx.MockTransport(...)`` mocks the Graph HTTP calls.
"""

import json
from datetime import UTC, datetime, timedelta, timezone
from urllib.parse import unquote

import httpx
import pytest
from sqlalchemy.orm import Session

from app import sharepoint
from app.config import Settings
from app.models import Submission, Template, User
from app.sharepoint import artifact_filename, folder_path, sanitize_title
from app.storage import LocalVolumeStorage


def test_sanitize_title_replaces_illegal_characters() -> None:
    assert sanitize_title('a"b*c:d<e>f?g/h\\i|j') == "a_b_c_d_e_f_g_h_i_j"


def test_sanitize_title_collapses_runs_and_trims() -> None:
    assert sanitize_title("  ::weird??  title..  ") == "_weird_ title"


def test_sanitize_title_truncates_to_100_chars() -> None:
    assert len(sanitize_title("x" * 250)) == 100


def test_sanitize_title_empty_becomes_underscore() -> None:
    assert sanitize_title("...") == "_"


def test_sanitize_title_strips_trailing_dot_space_exposed_by_truncation() -> None:
    result = sanitize_title("x" * 99 + ". " + "y" * 50)
    assert not result.endswith(".")
    assert not result.endswith(" ")


def test_sanitize_title_replaces_hash() -> None:
    # Unescaped '#' truncates a URL at the fragment (item name and
    # ':/content' suffix would never be sent to Graph).
    assert sanitize_title("PO #123") == "PO _123"


def test_sanitize_title_replaces_percent() -> None:
    # A stray '%' produces invalid percent-encoding in the Graph URL.
    assert sanitize_title("100% done") == "100_ done"


def test_folder_path_layout() -> None:
    path = folder_path(
        "Signed_document_archive",
        "jane@pumasi.ai",
        datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        "NDA - Acme Corp",
    )
    # Date-prefixed folder name (like the files inside): name-sorting the
    # year folder is chronological.
    assert path == "Signed_document_archive/jane@pumasi.ai/2026/2026-08-01 NDA - Acme Corp"


def test_folder_path_uses_utc_year_for_non_utc_completed_at() -> None:
    # 2026-01-01 00:30 JST (UTC+9) is still 2025-12-31 in UTC.
    completed_at = datetime(2026, 1, 1, 0, 30, tzinfo=timezone(timedelta(hours=9)))
    path = folder_path(
        "Signed_document_archive",
        "jane@pumasi.ai",
        completed_at,
        "NDA - Acme Corp",
    )
    assert path == "Signed_document_archive/jane@pumasi.ai/2025/2025-12-31 NDA - Acme Corp"


SP_SETTINGS = dict(sp_drive_id="drive-1", sp_archive_folder="Signed_document_archive")


def _make_completed_submission(
    db: Session,
    storage: LocalVolumeStorage,
    *,
    with_certificate: bool = True,
    title: str = "NDA - Acme Corp",
) -> Submission:
    """Insert a completed submission with real artifact files on disk."""
    owner = User(email="jane@pumasi.ai", name="Jane")
    db.add(owner)
    db.flush()
    template = Template(
        name="NDA",
        created_by=owner.id,
        original_file_key="t/1/o.pdf",
        pdf_key="t/1/d.pdf",
        page_count=1,
    )
    db.add(template)
    db.flush()
    submission = Submission(
        template_id=template.id,
        title=title,
        created_by=owner.id,
        status="completed",
        completed_at=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        signed_pdf_key="submissions/1/signed.pdf",
        certificate_pdf_key="submissions/1/certificate.pdf" if with_certificate else None,
    )
    db.add(submission)
    db.commit()
    storage.save("submissions/1/signed.pdf", b"%PDF signed")
    if with_certificate:
        storage.save("submissions/1/certificate.pdf", b"%PDF cert")
    return submission


def test_artifact_filename_is_dated_and_self_describing() -> None:
    name = artifact_filename("NDA - Acme Corp", datetime(2026, 8, 2, 12, 0, tzinfo=UTC), "signed")
    assert name == "2026-08-02 NDA - Acme Corp - signed.pdf"


def test_artifact_filename_uses_utc_date_and_sanitized_title() -> None:
    # 2026-01-01 00:30 JST is 2025-12-31 15:30 UTC — the UTC date must win.
    completed = datetime(2026, 1, 1, 0, 30, tzinfo=timezone(timedelta(hours=9)))
    name = artifact_filename("PO #123", completed, "certificate")
    assert name == "2025-12-31 PO _123 - certificate.pdf"


def test_archive_disabled_returns_false_without_http(db: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage)

    def explode(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no HTTP call expected when SP_DRIVE_ID is unset")

    ok = sharepoint.archive_submission(
        db,
        submission,
        storage,
        Settings(),
        transport=httpx.MockTransport(explode),
    )
    assert ok is False
    assert submission.archived_at is None


def test_archive_uploads_both_artifacts_and_marks_row(db: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sharepoint, "_acquire_token", lambda settings: "tok")
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage)
    puts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":  # folder claim (conflictBehavior=fail)
            return httpx.Response(201, json={"id": "folder1"})
        if request.method == "PUT":
            puts.append(str(request.url))
            return httpx.Response(201, json={"webUrl": "https://pumasiinc.sharepoint.com/x/file"})
        # folder webUrl lookup
        return httpx.Response(200, json={"webUrl": "https://pumasiinc.sharepoint.com/x/folder"})

    ok = sharepoint.archive_submission(
        db,
        submission,
        storage,
        Settings(**SP_SETTINGS),
        transport=httpx.MockTransport(handler),
    )
    assert ok is True
    base = "Signed_document_archive/jane@pumasi.ai/2026/2026-08-01 NDA - Acme Corp"
    # httpx percent-encodes spaces in URLs (e.g. "NDA - Acme" -> "NDA%20-%20Acme"),
    # so compare against the decoded form to check the folder-path structure.
    decoded_puts = [unquote(u) for u in puts]
    assert any(f"root:/{base}/2026-08-01 NDA - Acme Corp - signed.pdf:/content" in u for u in decoded_puts)
    assert any(f"root:/{base}/2026-08-01 NDA - Acme Corp - certificate.pdf:/content" in u for u in decoded_puts)
    assert all("conflictBehavior=replace" in u for u in puts)
    db.refresh(submission)
    assert submission.archived_at is not None
    assert submission.archive_url == "https://pumasiinc.sharepoint.com/x/folder"


def test_archive_with_hash_in_title_uploads_to_sanitized_folder(
    db: Session,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A '#' in the title must not truncate the Graph URL at a fragment: the
    item name and ':/content' suffix must still reach the server, and the
    uploaded path must use the sanitized (underscored) folder name.
    """
    monkeypatch.setattr(sharepoint, "_acquire_token", lambda settings: "tok")
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage, title="PO #123")
    puts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":  # folder claim
            return httpx.Response(201, json={"id": "folder1"})
        if request.method == "PUT":
            puts.append(str(request.url))
            return httpx.Response(201, json={"webUrl": "https://pumasiinc.sharepoint.com/x/file"})
        return httpx.Response(200, json={"webUrl": "https://pumasiinc.sharepoint.com/x/folder"})

    ok = sharepoint.archive_submission(
        db,
        submission,
        storage,
        Settings(**SP_SETTINGS),
        transport=httpx.MockTransport(handler),
    )
    assert ok is True
    base = "Signed_document_archive/jane@pumasi.ai/2026/2026-08-01 PO _123"
    decoded_puts = [unquote(u) for u in puts]
    assert any(f"root:/{base}/2026-08-01 PO _123 - signed.pdf:/content" in u for u in decoded_puts)
    assert any(f"root:/{base}/2026-08-01 PO _123 - certificate.pdf:/content" in u for u in decoded_puts)
    # No raw '#' ever reaches the URL, so httpx never treats anything after
    # it as a fragment: the ':/content' suffix and query string must survive.
    assert all("#" not in u for u in puts)
    assert all(":/content" in u for u in puts)
    db.refresh(submission)
    assert submission.archived_at is not None


def test_archive_folder_url_lookup_failure_still_marks_row_archived(
    db: Session,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The folder webUrl GET is best-effort: a raised exception there (not just
    a non-2xx status) must not discard the two uploads that already succeeded.
    """
    monkeypatch.setattr(sharepoint, "_acquire_token", lambda settings: "tok")
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":  # folder claim
            return httpx.Response(201, json={"id": "folder1"})
        if request.method == "PUT":
            return httpx.Response(201, json={"webUrl": "https://pumasiinc.sharepoint.com/x/file"})
        # folder webUrl lookup: simulate a transport-level failure
        raise httpx.ConnectError("boom", request=request)

    ok = sharepoint.archive_submission(
        db,
        submission,
        storage,
        Settings(**SP_SETTINGS),
        transport=httpx.MockTransport(handler),
    )
    assert ok is True
    db.refresh(submission)
    assert submission.archived_at is not None
    assert submission.archive_url is None


def test_archive_without_certificate_uploads_signed_only(db: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sharepoint, "_acquire_token", lambda settings: "tok")
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage, with_certificate=False)
    puts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":  # folder claim
            return httpx.Response(201, json={"id": "folder1"})
        if request.method == "PUT":
            puts.append(str(request.url))
            return httpx.Response(201, json={"webUrl": "u"})
        return httpx.Response(200, json={"webUrl": "u"})

    ok = sharepoint.archive_submission(
        db,
        submission,
        storage,
        Settings(**SP_SETTINGS),
        transport=httpx.MockTransport(handler),
    )
    assert ok is True
    assert len(puts) == 1
    assert "signed.pdf" in puts[0]


def test_archive_http_failure_returns_false_and_leaves_row(
    db: Session,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sharepoint, "_acquire_token", lambda settings: "tok")
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage)

    handler = lambda request: httpx.Response(503)  # noqa: E731

    ok = sharepoint.archive_submission(
        db,
        submission,
        storage,
        Settings(**SP_SETTINGS),
        transport=httpx.MockTransport(handler),
    )
    assert ok is False
    db.refresh(submission)
    assert submission.archived_at is None
    assert submission.archive_url is None


def test_archive_token_failure_returns_false(db: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sharepoint, "_acquire_token", lambda settings: None)
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage)

    ok = sharepoint.archive_submission(db, submission, storage, Settings(**SP_SETTINGS))
    assert ok is False


def test_archive_large_file_uses_upload_session(db: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sharepoint, "_acquire_token", lambda settings: "tok")
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage, with_certificate=False)
    storage.save("submissions/1/signed.pdf", b"x" * (sharepoint.SIMPLE_UPLOAD_LIMIT + 1))
    calls: list[tuple[str, str, str]] = []  # (method, url, content-range)
    chunk_auth_headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url), request.headers.get("content-range", "")))
        if request.url.path.endswith(":/children"):  # folder claim
            return httpx.Response(201, json={"id": "folder1"})
        if request.url.path.endswith(":/createUploadSession"):
            return httpx.Response(200, json={"uploadUrl": "https://upload.example/session-1"})
        if request.url.host == "upload.example":
            chunk_auth_headers.append(request.headers.get("authorization", ""))
            done = calls[-1][2].endswith(f"/{sharepoint.SIMPLE_UPLOAD_LIMIT + 1}") and calls[-1][2].split("-")[1].split(
                "/",
            )[0] == str(sharepoint.SIMPLE_UPLOAD_LIMIT)
            return httpx.Response(201 if done else 202, json={"webUrl": "u"} if done else {})
        return httpx.Response(200, json={"webUrl": "u"})

    ok = sharepoint.archive_submission(
        db,
        submission,
        storage,
        Settings(**SP_SETTINGS),
        transport=httpx.MockTransport(handler),
    )
    assert ok is True
    session_calls = [c for c in calls if "createUploadSession" in c[1]]
    chunk_calls = [c for c in calls if c[1].startswith("https://upload.example")]
    assert len(session_calls) == 1
    assert len(chunk_calls) >= 2  # > CHUNK_SIZE bytes means at least two chunks
    assert all(c[0] == "PUT" for c in chunk_calls)
    # The pre-authenticated uploadUrl must NOT receive the bearer token.
    assert all(header == "" for header in chunk_auth_headers)


def test_archive_collision_claims_suffixed_folder(db: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Another envelope already owns the base name: the claim walks to _2 and
    the chosen path is persisted for retries."""
    monkeypatch.setattr(sharepoint, "_acquire_token", lambda settings: "tok")
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage)
    puts: list[str] = []
    claims: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            name = json.loads(request.read())["name"]
            claims.append(name)
            if name.endswith("_2"):
                return httpx.Response(201, json={"id": "folder2"})
            return httpx.Response(409, json={"error": {"code": "nameAlreadyExists"}})
        if request.method == "PUT":
            puts.append(str(request.url))
            return httpx.Response(201, json={})
        return httpx.Response(200, json={"webUrl": "https://pumasiinc.sharepoint.com/x/folder"})

    ok = sharepoint.archive_submission(
        db,
        submission,
        storage,
        Settings(**SP_SETTINGS),
        transport=httpx.MockTransport(handler),
    )
    assert ok is True
    assert len(claims) == 2  # base 409'd, _2 claimed
    decoded_puts = [unquote(u) for u in puts]
    suffixed = "Signed_document_archive/jane@pumasi.ai/2026/2026-08-01 NDA - Acme Corp_2"
    assert all(f"root:/{suffixed}/" in u for u in decoded_puts)
    db.refresh(submission)
    assert submission.archive_path == suffixed
    assert submission.archived_at is not None


def test_archive_retry_reuses_claimed_folder(db: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A retry after a partial failure must upload into the persisted folder
    and never attempt a fresh claim (which would see its own leftovers)."""
    monkeypatch.setattr(sharepoint, "_acquire_token", lambda settings: "tok")
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage)
    claimed = "Signed_document_archive/jane@pumasi.ai/2026/2026-08-01 NDA - Acme Corp_3"
    submission.archive_path = claimed
    db.commit()
    puts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            raise AssertionError("retry must not re-claim a folder")
        if request.method == "PUT":
            puts.append(str(request.url))
            return httpx.Response(201, json={})
        return httpx.Response(200, json={"webUrl": "https://pumasiinc.sharepoint.com/x/folder"})

    ok = sharepoint.archive_submission(
        db,
        submission,
        storage,
        Settings(**SP_SETTINGS),
        transport=httpx.MockTransport(handler),
    )
    assert ok is True
    decoded_puts = [unquote(u) for u in puts]
    assert all(f"root:/{claimed}/" in u for u in decoded_puts)
