"""SharePoint archive mirror for completed envelopes (Microsoft Graph).

``archive_submission`` is the sole public entry point (Task 4). Like
``mailer.send`` it never raises to callers: any failure — feature disabled,
missing artifacts, token failure, HTTP error — is logged (submission id and
HTTP status only; never titles, tokens, or file bytes) and returns
``False``, so an archive outage can never fail a signer's request or the
daily job. SharePoint is a mirror; the Railway volume stays the source of
truth. Design: docs/superpowers/specs/2026-08-01-sharepoint-archive-design.md.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.graph import acquire_token as _acquire_token
from app.models import Submission
from app.storage import FileStorage

logger = logging.getLogger(__name__)

# SharePoint-illegal item-name characters, plus control chars. ``#`` and ``%``
# are included because they are interpolated into Graph URL strings
# (``_upload_file``/``archive_submission``): unescaped ``#`` truncates the URL
# at a fragment, and a stray ``%`` produces invalid percent-encoding.
_ILLEGAL = re.compile(r"[\"*:<>?/\\|#%\x00-\x1f\x7f]")
_MAX_TITLE_LEN = 100


def sanitize_title(title: str) -> str:
    """Make ``title`` safe as a SharePoint folder-name segment.

    Illegal characters become ``_`` (runs collapsed), whitespace runs
    collapse to a single space, surrounding whitespace and trailing dots are
    stripped, and the result is capped at 100 characters. Uniqueness comes
    from the ``({id})`` suffix appended by ``folder_path``, so lossy
    sanitization here is fine.
    """
    cleaned = _ILLEGAL.sub("_", title)
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip().rstrip(".").strip()
    cleaned = cleaned[:_MAX_TITLE_LEN]
    # Truncation can expose a trailing dot/space that was previously in the
    # interior of the string (e.g. "...99 x's..., <cut here>"); SharePoint
    # rejects segment names ending in either, so strip again.
    cleaned = cleaned.rstrip(".").strip()
    return cleaned or "_"


def folder_path(
    archive_folder: str,
    owner_email: str,
    completed_at: datetime,
    title: str,
) -> str:
    """Return the envelope's archive folder path inside the drive.

    Layout: ``{folder}/{owner email}/{year}/{UTC date} {title}`` — the
    folder name carries the completion date prefix just like the files
    inside it (2026-08-05 request), so name-sorting a year folder is
    chronological. The year/date are UTC (``Submission.completed_at`` is
    TIMESTAMPTZ and always tz-aware, but converting explicitly keeps this
    correct even if a non-UTC-but-aware value ever reaches here).

    The internal submission id was dropped from the name (2026-08-09
    request — it means nothing to users). Uniqueness comes from
    ``_claim_archive_folder`` instead: a name collision (same owner, same
    sanitized title, same UTC date) gets a ``_2``/``_3``... suffix, and
    the claimed path is persisted on the submission so retries reuse it.
    """
    completed_utc = completed_at.astimezone(UTC)
    date = completed_utc.date().isoformat()
    return f"{archive_folder}/{owner_email}/{completed_utc.year}/{date} {sanitize_title(title)}"


def artifact_filename(title: str, completed_at: datetime, artifact: str) -> str:
    """Return a self-describing filename: ``{UTC date} {title} - {artifact}.pdf``.

    Shared by the archive mirror and the download endpoints
    (``routers/files.py``), so a downloaded file and its archived twin
    carry the same name: completion date (UTC, sorts chronologically),
    sanitized title, and the artifact kind (``signed`` / ``certificate`` /
    ``in progress``).
    """
    date = completed_at.astimezone(UTC).date().isoformat()
    return f"{date} {sanitize_title(title)} - {artifact}.pdf"


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
# Graph's simple-PUT ceiling is 4 MB; larger files need an upload session.
SIMPLE_UPLOAD_LIMIT = 4 * 1024 * 1024
# Upload-session chunks must be multiples of 320 KiB; 10 of them ≈ 3.1 MB.
CHUNK_SIZE = 10 * 320 * 1024
# "_2".."_10": more same-day same-title collisions than this means something
# is systematically wrong — fail the run and let the daily sweep retry.
_MAX_FOLDER_ATTEMPTS = 10


def _claim_archive_folder(client: httpx.Client, drive_id: str, base_folder: str, token: str) -> str | None:
    """Atomically claim a collision-free archive folder; ``None`` on failure.

    Tries ``base_folder``, then ``…_2``, ``…_3``… by creating the folder
    with ``@microsoft.graph.conflictBehavior: fail`` — Graph's 201-vs-409
    makes the claim atomic (no probe-then-create race between two
    envelopes completing simultaneously). A 404 means the parent chain
    (``{archive}/{email}/{year}``) doesn't exist yet, so nothing can
    collide either — the file uploads auto-create it.
    """
    parent, _, leaf = base_folder.rpartition("/")
    headers = {"Authorization": f"Bearer {token}"}
    for attempt in range(1, _MAX_FOLDER_ATTEMPTS + 1):
        name = leaf if attempt == 1 else f"{leaf}_{attempt}"
        response = client.post(
            f"{GRAPH_ROOT}/drives/{drive_id}/root:/{parent}:/children",
            json={"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"},
            headers=headers,
        )
        if response.status_code == 201 or response.status_code == 404:
            return f"{parent}/{name}"
        if response.status_code == 409:
            continue
        logger.error("SharePoint folder claim failed with status %d", response.status_code)
        return None
    logger.error("SharePoint folder claim exhausted %d name candidates", _MAX_FOLDER_ATTEMPTS)
    return None


def _upload_file(client: httpx.Client, drive_id: str, item_path: str, data: bytes, token: str) -> bool:
    """Upload ``data`` to ``item_path`` in ``drive_id``. Returns success; never raises."""
    headers = {"Authorization": f"Bearer {token}"}
    if len(data) <= SIMPLE_UPLOAD_LIMIT:
        response = client.put(
            f"{GRAPH_ROOT}/drives/{drive_id}/root:/{item_path}:/content",
            params={"@microsoft.graph.conflictBehavior": "replace"},
            content=data,
            headers={**headers, "Content-Type": "application/octet-stream"},
        )
        if response.status_code >= 300:
            logger.error("SharePoint simple upload failed with status %d", response.status_code)
            return False
        return True

    response = client.post(
        f"{GRAPH_ROOT}/drives/{drive_id}/root:/{item_path}:/createUploadSession",
        json={"item": {"@microsoft.graph.conflictBehavior": "replace"}},
        headers=headers,
    )
    if response.status_code >= 300:
        logger.error("SharePoint createUploadSession failed with status %d", response.status_code)
        return False
    upload_url = response.json().get("uploadUrl")
    if not upload_url:
        logger.error("SharePoint createUploadSession response had no uploadUrl")
        return False

    total = len(data)
    for start in range(0, total, CHUNK_SIZE):
        chunk = data[start : start + CHUNK_SIZE]
        end = start + len(chunk) - 1
        # The uploadUrl is pre-authenticated — no Authorization header.
        response = client.put(
            upload_url,
            content=chunk,
            headers={
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {start}-{end}/{total}",
            },
        )
        if response.status_code >= 300:
            logger.error("SharePoint chunk upload failed with status %d", response.status_code)
            return False
    return True


def archive_submission(
    db: Session,
    submission: Submission,
    storage: FileStorage,
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> bool:
    """Mirror ``submission``'s artifacts to SharePoint. Returns success; never raises.

    No-op (``False``, quiet) when ``SP_DRIVE_ID`` is unset — the feature
    flag for local dev and tests. Only completed submissions with a signed
    PDF are eligible. On success of *all* uploads: sets ``archived_at`` and
    ``archive_url`` and commits — callers must invoke this only after their
    own ``db.commit()``, never mid-transaction (same rule as the completion
    email; see app/completion.py's docstring). A missing certificate is
    fine (pre-issue-#15 envelopes); a missing signed PDF is a failure.

    Single attempt per call, 30 s timeout per request — the daily job's
    sweep is the retry mechanism (unlike mail's in-call retries), keeping
    completion-time latency low.
    """
    if not settings.sp_drive_id:
        logger.debug("SharePoint archive disabled (SP_DRIVE_ID unset); skipping")
        return False
    if submission.status != "completed" or not submission.signed_pdf_key or submission.completed_at is None:
        logger.warning("archive_submission called for ineligible submission_id=%s", submission.id)
        return False

    try:
        signed_bytes = storage.open(submission.signed_pdf_key)
        certificate_bytes = None
        if submission.certificate_pdf_key and storage.exists(submission.certificate_pdf_key):
            certificate_bytes = storage.open(submission.certificate_pdf_key)

        token = _acquire_token(settings)
        if not token:
            return False

        signed_name = artifact_filename(submission.title, submission.completed_at, "signed")
        certificate_name = artifact_filename(submission.title, submission.completed_at, "certificate")

        client_kwargs = {"transport": transport} if transport is not None else {}
        with httpx.Client(timeout=30.0, **client_kwargs) as client:
            # First attempt claims a collision-free folder and persists it
            # immediately (committed before any upload), so a retry after a
            # partial failure lands back in its own folder instead of
            # suffixing against its own leftovers.
            folder = submission.archive_path
            if not folder:
                base = folder_path(
                    settings.sp_archive_folder,
                    submission.creator.email,
                    submission.completed_at,
                    submission.title,
                )
                folder = _claim_archive_folder(client, settings.sp_drive_id, base, token)
                if folder is None:
                    logger.error("SharePoint archive failed for submission_id=%s", submission.id)
                    return False
                submission.archive_path = folder
                db.commit()

            if not _upload_file(client, settings.sp_drive_id, f"{folder}/{signed_name}", signed_bytes, token):
                logger.error("SharePoint archive failed for submission_id=%s", submission.id)
                return False
            if certificate_bytes is not None and not _upload_file(
                client,
                settings.sp_drive_id,
                f"{folder}/{certificate_name}",
                certificate_bytes,
                token,
            ):
                logger.error("SharePoint archive failed for submission_id=%s", submission.id)
                return False

            # Folder webUrl for future UI use — best-effort; any failure here
            # (non-2xx status, connect/timeout error, invalid JSON body)
            # must not undo the two uploads that already succeeded, so it's
            # scoped to its own try/except rather than the outer one.
            archive_url = None
            try:
                response = client.get(
                    f"{GRAPH_ROOT}/drives/{settings.sp_drive_id}/root:/{folder}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if response.status_code < 300:
                    archive_url = response.json().get("webUrl")
            except Exception:
                logger.warning(
                    "SharePoint folder webUrl lookup failed for submission_id=%s",
                    submission.id,
                )

        submission.archived_at = datetime.now(UTC)
        submission.archive_url = archive_url
        db.commit()
    except Exception:
        logger.exception("SharePoint archive failed for submission_id=%s", submission.id)
        try:
            db.rollback()
        except Exception:
            logger.debug("SharePoint archive rollback also failed for submission_id=%s", submission.id)
        return False
    return True
