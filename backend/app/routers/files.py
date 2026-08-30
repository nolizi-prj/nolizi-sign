"""Authorized binary file serving: template PDFs, signed PDFs, signature images.

Every route here checks two things, in order: (1) does the referenced DB row
(and, for the pdf routes, the underlying storage object) exist — 404 if not;
(2) is the current user allowed to see it — 403 if not. Authorization rules
per resource (see task brief):

- template-pdf: admins, the template's creator, or any user who is a
  submitter on — or the sender of — some submission that uses this template;
  or an external signer via the signer cookie (scoped to that submitter's
  own template).
- signed-pdf: the submission's sender (creator) or one of its submitters; or
  an external signer via the signer cookie (scoped to that submitter's own
  submission).
- document-preview: same access as signed-pdf; serves the current state of
  the document (already-signed values stamped, "In progress" watermark) —
  or the signed PDF once completed.
- certificate: the submission's sender (creator) or one of its submitters
  (session only, no cookie access).
- signature: the signature's owner, or an admin.
"""

from collections.abc import Callable
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app import completion
from app.auth import current_user, get_settings, optional_user, signer_identity
from app.config import Settings
from app.db import get_db
from app.models import Signature, Submission, Submitter, Template, User
from app.sharepoint import artifact_filename, sanitize_title
from app.storage import FileStorage, get_storage

router = APIRouter(prefix="/api/files", tags=["files"])


def _pdf_response(data: bytes, filename: str) -> Response:
    """A PDF response with a human filename (browser tab title / download name).

    ``filename*`` carries the real UTF-8 name (Korean titles survive);
    plain ``filename`` is an ASCII fallback for old agents. ``inline`` so
    browsers keep showing the PDF in a tab rather than force-downloading.
    """
    ascii_fallback = filename.encode("ascii", "ignore").decode().strip() or "document.pdf"
    disposition = f"inline; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )


def _submission_filename(submission: Submission, artifact: str) -> str:
    """The exact name the SharePoint archive uses — a download and its archived twin match."""
    return artifact_filename(submission.title, submission.completed_at or submission.created_at, artifact)


def _open_or_404(storage: FileStorage, key: str) -> bytes:
    try:
        return storage.open(key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc


def _is_submitter(db: Session, *, submission_id: int, user_id: int) -> bool:
    return (
        db.scalar(
            select(Submitter.id).where(
                Submitter.submission_id == submission_id,
                Submitter.user_id == user_id,
            ),
        )
        is not None
    )


def _cookie_submitter(db: Session, request: Request, settings: Settings) -> Submitter | None:
    """The Submitter a valid sign_signer cookie points at, else None.

    Checks the cookie's ``uid`` against the submitter row's *current*
    ``user_id``, not just ``sid`` against its id — a submitter row can be
    reassigned to a different user by ``replace_submitter`` without its id
    changing, and the old signer's still-unexpired cookie must not keep
    granting access to that row's (now different) documents.
    """
    cookie = signer_identity(request, settings)
    if cookie is None:
        return None
    sid, uid = cookie
    submitter = db.get(Submitter, sid)
    if submitter is None or submitter.user_id != uid:
        return None
    return submitter


@router.get("/template-pdf/{template_id}")
def get_template_pdf(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(optional_user),
) -> Response:
    """Serve a template's converted PDF to admins or submitters of its submissions."""
    template = db.get(Template, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    if user is not None:
        if not user.is_admin and template.created_by != user.id:
            party_on_template = db.scalar(
                select(Submission.id)
                .outerjoin(Submitter, Submitter.submission_id == Submission.id)
                .where(
                    Submission.template_id == template_id,
                    or_(
                        Submission.created_by == user.id,
                        and_(Submitter.user_id == user.id, Submission.status != "draft"),
                    ),
                )
                .limit(1),
            )
            if party_on_template is None:
                raise HTTPException(status_code=403, detail="Forbidden")
    else:
        submitter = _cookie_submitter(db, request, settings)
        if submitter is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if submitter.submission.template_id != template_id:
            raise HTTPException(status_code=403, detail="Forbidden")

    storage = get_storage(settings)
    data = _open_or_404(storage, template.pdf_key)
    return _pdf_response(data, f"{sanitize_title(template.name)}.pdf")


def _serve_submission_pdf(
    db: Session,
    settings: Settings,
    user: User | None,
    submission_id: int,
    *,
    key: Callable[[Submission], str | None],
    missing_detail: str,
    artifact: str,
    cookie_submitter: Submitter | None = None,
) -> Response:
    """Serve one of a submission's PDF artifacts to its sender or its submitters.

    The shared access rule for signed-PDF and certificate downloads —
    deliberately *not* "admins" too (see the module docstring). ``key``
    picks the storage key off the submission; a missing key 404s with
    ``missing_detail``.
    """
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    if user is not None:
        is_sender = submission.created_by == user.id
        # Unsent drafts are sender-only — a listed submitter of a draft must
        # not even learn (via the artifact-specific 404 below) that it
        # exists, same rule as document-preview.
        if submission.status == "draft" and not is_sender:
            raise HTTPException(status_code=403, detail="Forbidden")
        if not is_sender and not _is_submitter(db, submission_id=submission_id, user_id=user.id):
            raise HTTPException(status_code=403, detail="Forbidden")
    elif cookie_submitter is not None:
        if cookie_submitter.submission_id != submission_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        raise HTTPException(status_code=401, detail="Not authenticated")

    storage_key = key(submission)
    if not storage_key:
        raise HTTPException(status_code=404, detail=missing_detail)

    storage = get_storage(settings)
    data = _open_or_404(storage, storage_key)
    return _pdf_response(data, _submission_filename(submission, artifact))


@router.get("/signed-pdf/{submission_id}")
def get_signed_pdf(
    submission_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(optional_user),
) -> Response:
    """Serve a submission's signed PDF to its sender or its submitters."""
    cookie_submitter = _cookie_submitter(db, request, settings)
    return _serve_submission_pdf(
        db,
        settings,
        user,
        submission_id,
        key=lambda s: s.signed_pdf_key,
        missing_detail="Signed PDF not available",
        artifact="signed",
        cookie_submitter=cookie_submitter,
    )


@router.get("/document-preview/{submission_id}")
def get_document_preview(
    submission_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(optional_user),
) -> Response:
    """Serve the document as it currently stands (DocuSign-style).

    Pending envelope: the template PDF with every already-signed
    submitter's values stamped and an "In progress" watermark — so later
    signers (and the sender) see earlier signatures. Completed envelope:
    the stored signed PDF. Access mirrors ``signed-pdf``: the sender, any
    submitter, or an external signer via the scoped cookie.
    """
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    if user is not None:
        is_sender = submission.created_by == user.id
        # Unsent drafts are sender-only (recipients haven't been notified).
        if submission.status == "draft" and not is_sender:
            raise HTTPException(status_code=403, detail="Forbidden")
        if not is_sender and not _is_submitter(db, submission_id=submission_id, user_id=user.id):
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        cookie_submitter = _cookie_submitter(db, request, settings)
        if cookie_submitter is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if cookie_submitter.submission_id != submission_id:
            raise HTTPException(status_code=403, detail="Forbidden")

    storage = get_storage(settings)
    try:
        data = completion.build_preview_pdf(db, storage, submission)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    artifact = "signed" if submission.status == "completed" and submission.signed_pdf_key else "in progress"
    return _pdf_response(data, _submission_filename(submission, artifact))


@router.get("/certificate/{submission_id}")
def get_certificate_pdf(
    submission_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> Response:
    """Serve a submission's signature-certificate PDF to its sender or its submitters.

    404 for envelopes completed before the certificate became a separate
    artifact — their certificate page lives inside the signed PDF.
    """
    return _serve_submission_pdf(
        db,
        settings,
        user,
        submission_id,
        key=lambda s: s.certificate_pdf_key,
        missing_detail="Certificate not available",
        artifact="certificate",
        cookie_submitter=None,
    )


@router.get("/signature/{signature_id}")
def get_signature_image(
    signature_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> Response:
    """Serve a stored signature image to its owner or an admin."""
    signature = db.get(Signature, signature_id)
    if signature is None:
        raise HTTPException(status_code=404, detail="Signature not found")

    if not (user.is_admin or signature.user_id == user.id):
        raise HTTPException(status_code=403, detail="Forbidden")

    storage = get_storage(settings)
    data = _open_or_404(storage, signature.image_key)
    return Response(content=data, media_type="image/png")
