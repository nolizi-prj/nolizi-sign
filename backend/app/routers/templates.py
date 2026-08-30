"""Template routes: upload-to-create, field-layout editing, list/get/archive.

Templates are private per user: the list shows only the caller's own, and
get/fields/archive require the caller to be the template's creator (admins
may operate on any template by id, as an escape hatch — but even an admin's
list shows only their own).

Upload flow: the DB row is created and flushed first (to get an id for the
storage key prefix), then the file is converted to PDF and both the original
and the converted PDF are saved under ``templates/{id}/...``. If conversion
fails, the transaction is rolled back so nothing persists — the template row,
the original file, and the pdf are all-or-nothing for a single request.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_settings, require_sender
from app.config import Settings
from app.conversion import ConversionError, to_pdf
from app.db import get_db
from app.models import Template, User
from app.schemas import TemplateFieldsUpdate, TemplateOut, TemplateSharingUpdate
from app.storage import get_storage

router = APIRouter(prefix="/api/templates", tags=["templates"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_UPLOAD_CHUNK_BYTES = 1024 * 1024


def _get_owned_template(db: Session, template_id: int, sender: User, *, allow_shared: bool = False) -> Template:
    """Return the template if ``sender`` owns it (or is an admin); 404/403 otherwise.

    ``allow_shared=True`` additionally admits any sender when the template
    is shared — for *read* access only (the send flow needs the fields);
    every mutating route keeps the owner-or-admin rule.
    """
    template = db.get(Template, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    is_owner = template.created_by == sender.id or sender.is_admin
    if not is_owner and not (allow_shared and template.shared):
        raise HTTPException(status_code=403, detail="Forbidden")
    return template


def clone_template(
    db: Session,
    settings: Settings,
    source: Template,
    *,
    owner_id: int,
    name: str,
    is_adhoc: bool,
) -> Template:
    """Insert (flush, not commit) a copy of ``source`` with its own storage files.

    The copy always gets fresh file keys — never shared with the source —
    because template files follow their row's lifecycle (an ad-hoc draft's
    deletion removes its template's files; see submissions.delete_draft),
    and shared keys would let deleting one destroy the other's document.
    Also used by the envelope Copy flow, which clones every source into a standalone ad-hoc template.
    """
    clone = Template(
        name=name[:255],
        created_by=owner_id,
        original_file_key="",
        pdf_key="",
        page_count=source.page_count,
        fields=list(source.fields),
        roles=list(source.roles),
        is_adhoc=is_adhoc,
        shared=False,
    )
    storage = get_storage(settings)
    if not storage.exists(source.pdf_key):
        # A copy without its working PDF would be unusable everywhere
        # downstream (builder, signing, stamping) — fail cleanly instead.
        raise HTTPException(status_code=409, detail="The source document's PDF file is missing from storage")

    db.add(clone)
    db.flush()  # assign clone.id for the storage key prefix

    for attr in ("original_file_key", "pdf_key"):
        source_key = getattr(source, attr)
        # The original upload is archival — a missing one must not block the
        # copy; the clone just keeps an empty key for it.
        if source_key and storage.exists(source_key):
            new_key = f"templates/{clone.id}/{source_key.rsplit('/', 1)[-1]}"
            storage.save(new_key, storage.open(source_key))
            setattr(clone, attr, new_key)
    return clone


async def _read_upload_within_limit(file: UploadFile) -> bytes:
    """Read ``file`` in chunks, raising 413 as soon as MAX_UPLOAD_BYTES is exceeded."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds the 25 MB upload limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _extension_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.post("", response_model=TemplateOut, status_code=201)
async def create_template(
    name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    sender: User = Depends(require_sender),
) -> Template:
    """Upload a document, convert it to PDF, and create a Template row for it."""
    data = await _read_upload_within_limit(file)

    template = Template(
        name=name,
        created_by=sender.id,
        original_file_key="",
        pdf_key="",
        page_count=0,
        fields=[],
    )
    db.add(template)
    db.flush()  # assign template.id without committing yet

    storage = get_storage(settings)
    key_prefix = f"templates/{template.id}"
    filename = file.filename or "upload"

    try:
        tmp_pdf_key, page_count = to_pdf(data, filename, storage, key_prefix, settings)
    except ConversionError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=exc.reason) from exc

    pdf_bytes = storage.open(tmp_pdf_key)
    storage.delete(tmp_pdf_key)

    ext = _extension_of(filename)
    original_key = f"{key_prefix}/original.{ext}" if ext else f"{key_prefix}/original"
    pdf_key = f"{key_prefix}/document.pdf"
    storage.save(original_key, data)
    storage.save(pdf_key, pdf_bytes)

    template.original_file_key = original_key
    template.pdf_key = pdf_key
    template.page_count = page_count
    db.commit()
    db.refresh(template)
    return template


@router.get("", response_model=list[TemplateOut])
def list_templates(
    db: Session = Depends(get_db),
    sender: User = Depends(require_sender),
) -> list[Template]:
    """List the caller's own templates plus every shared one (non-ad-hoc, non-archived)."""
    stmt = (
        select(Template)
        .options(selectinload(Template.creator))
        .where(
            Template.is_adhoc.is_(False),
            Template.archived_at.is_(None),
            or_(Template.created_by == sender.id, Template.shared.is_(True)),
        )
        .order_by(Template.id)
    )
    return list(db.scalars(stmt))


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    sender: User = Depends(require_sender),
) -> Template:
    """Fetch a single template by id; owner, admin, or anyone when shared."""
    return _get_owned_template(db, template_id, sender, allow_shared=True)


@router.post("/{template_id}/copy", response_model=TemplateOut, status_code=201)
def copy_template(
    template_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    sender: User = Depends(require_sender),
) -> Template:
    """Copy a visible template into a private "Copy of X" owned by the caller.

    Anyone who can see the template may copy it (owner, admin, or any sender
    when shared) — the point is tweaking a shared template you don't own.
    The copy starts unshared regardless of the source's flag.
    """
    source = _get_owned_template(db, template_id, sender, allow_shared=True)
    if source.archived_at is not None:
        raise HTTPException(status_code=409, detail="Template is archived")

    clone = clone_template(
        db,
        settings,
        source,
        owner_id=sender.id,
        name=f"Copy of {source.name}",
        is_adhoc=False,
    )
    db.commit()
    db.refresh(clone)
    return clone


@router.put("/{template_id}/fields", response_model=TemplateOut)
def update_fields(
    template_id: int,
    payload: TemplateFieldsUpdate,
    db: Session = Depends(get_db),
    sender: User = Depends(require_sender),
) -> Template:
    """Replace a template's field and role lists wholesale; owner or admin only."""
    template = _get_owned_template(db, template_id, sender)

    for field in payload.fields:
        if field.page >= template.page_count:
            raise HTTPException(status_code=422, detail="page out of range")

    roles = payload.roles
    if roles is None:
        # Labels are role-less sender text — never a signer role.
        roles = list(dict.fromkeys(field.role for field in payload.fields if field.type != "label"))

    template.fields = [field.model_dump() for field in payload.fields]
    template.roles = roles
    db.commit()
    db.refresh(template)
    return template


@router.put("/{template_id}/sharing", response_model=TemplateOut)
def update_sharing(
    template_id: int,
    payload: TemplateSharingUpdate,
    db: Session = Depends(get_db),
    sender: User = Depends(require_sender),
) -> Template:
    """Share (or unshare) a template with every sender; owner or admin only."""
    template = _get_owned_template(db, template_id, sender)
    template.shared = payload.shared
    db.commit()
    db.refresh(template)
    return template


@router.post("/{template_id}/archive")
def archive_template(
    template_id: int,
    db: Session = Depends(get_db),
    sender: User = Depends(require_sender),
) -> dict[str, str]:
    """Mark a template as archived, hiding it from GET /api/templates; owner or admin only."""
    template = _get_owned_template(db, template_id, sender)

    template.archived_at = datetime.now(UTC)
    db.commit()
    return {"status": "ok"}
