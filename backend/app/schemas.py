"""Pydantic schemas for the templates API (request/response shapes)."""

import re
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FIELD_TYPES = (
    "signature",
    "initials",
    "name",
    "date",
    "text",
    "checkbox",
    "dropdown",
    "radio",
    "attachment",
    "label",
)

# Choice fields carry a sender-defined option list; bounded because every
# option is rendered in the signer UI and validated on completion.
MAX_FIELD_OPTIONS = 20
MAX_OPTION_LENGTH = 100

# Shared by UserCreate and UserUpdate: requires a 2+ character TLD so
# obviously-truncated addresses (e.g. "x@y.c") are rejected at the schema
# level rather than slipping through to become a real, undeliverable user.
EMAIL_RE = r"[^@\s]+@[^@\s]+\.[^@\s]{2,}"


def validate_future_expiry(value: datetime | None) -> datetime | None:
    """Normalize an optional expiry to tz-aware UTC and require it to be in the
    future. Shared by ``SubmissionCreate`` and the ad-hoc create route (which
    receives the value as a form string, outside pydantic)."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if value <= datetime.now(UTC):
        raise ValueError("expires_at must be in the future")
    return value


class FieldDef(BaseModel):
    """A single signable field placed on a template page.

    Coordinates are fractions of the page (0..1): ``x``/``y`` is the
    top-left corner, ``w``/``h`` the size. ``x + w`` and ``y + h`` must not
    exceed 1 so the field stays on the page.
    """

    id: str
    type: Literal[
        "signature",
        "initials",
        "name",
        "date",
        "text",
        "checkbox",
        "dropdown",
        "radio",
        "attachment",
        "label",
    ]
    role: str
    page: int
    x: float
    y: float
    w: float
    h: float
    required: bool
    # "text": optional prefill the signer sees (and may edit) in the input.
    # "label": the sender-authored static text itself — drawn for everyone
    # and stamped unconditionally. Ignored for other types.
    default_value: str | None = Field(None, max_length=500)
    # Sender-chosen text size in points for text/label/name/date fields;
    # None = automatic (0.6 × box height, capped at 14). Clamped to the box
    # height at render time, and still shrunk to fit the box width.
    font_size: int | None = Field(None, ge=6, le=72)
    # "dropdown"/"radio": the sender-defined choices the signer picks from
    # (required, non-empty, unique). Normalized to None for every other type.
    options: list[str] | None = None
    # "text" only: a format the signer's input must match. Normalized to
    # None for every other type.
    validation: Literal["email", "number"] | None = None

    @model_validator(mode="after")
    def _validate_options(self) -> "FieldDef":
        if self.type in ("dropdown", "radio"):
            if not self.options:
                raise ValueError(f"{self.type} fields need at least one option")
            stripped = [option.strip() for option in self.options]
            if any(not option for option in stripped):
                raise ValueError("options must be non-empty strings")
            if len(stripped) > MAX_FIELD_OPTIONS:
                raise ValueError(f"at most {MAX_FIELD_OPTIONS} options are allowed")
            if any(len(option) > MAX_OPTION_LENGTH for option in stripped):
                raise ValueError(f"options must be at most {MAX_OPTION_LENGTH} characters")
            if len(set(stripped)) != len(stripped):
                raise ValueError("duplicate options")
            self.options = stripped
        else:
            self.options = None
        if self.type != "text":
            self.validation = None
        return self

    @model_validator(mode="after")
    def _validate_geometry(self) -> "FieldDef":
        if self.type == "label":
            # Labels are sender text, not signable fields: no owning role,
            # never required — normalize rather than reject so clients don't
            # each need to special-case what "role" means for a label.
            self.role = ""
            self.required = False
        elif not self.role.strip():
            raise ValueError("role must be a non-empty string")
        if self.page < 0:
            raise ValueError("page must be >= 0")
        if self.w <= 0 or self.h <= 0:
            raise ValueError("w and h must be > 0")
        if self.x < 0 or self.y < 0:
            raise ValueError("x and y must be >= 0")
        if self.x + self.w > 1:
            raise ValueError("x + w must be <= 1")
        if self.y + self.h > 1:
            raise ValueError("y + h must be <= 1")
        return self


class TemplateOut(BaseModel):
    """Response shape for a template.

    ``owner`` identifies the creator so the Templates page can label shared
    templates ("Shared by ...") and gate the edit/archive/share actions to
    the owner client-side (the server enforces it regardless).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    page_count: int
    fields: list[FieldDef]
    roles: list[str]
    created_at: datetime
    shared: bool = False
    owner: "UserBrief" = Field(validation_alias="creator")


class TemplateSharingUpdate(BaseModel):
    """Body for PUT /api/templates/{id}/sharing."""

    shared: bool


class TemplateFieldsUpdate(BaseModel):
    """Body for PUT /api/templates/{id}/fields — replaces the field list (and role list) wholesale.

    ``roles`` is the template's ordered signer-role list. It may include
    roles that have no fields yet (they persist across saves so a
    half-built template doesn't lose them), but every field's ``role`` must
    appear in it. When omitted, roles are derived from the fields in order
    of first appearance — the pre-``roles`` behavior.
    """

    fields: list[FieldDef]
    roles: list[str] | None = None

    @model_validator(mode="after")
    def _validate_roles(self) -> "TemplateFieldsUpdate":
        if self.roles is None:
            return self
        stripped = [role.strip() for role in self.roles]
        if any(not role for role in stripped):
            raise ValueError("roles must be non-empty strings")
        if len(set(stripped)) != len(stripped):
            raise ValueError("duplicate role names")
        self.roles = stripped
        orphaned = sorted({field.role for field in self.fields if field.type != "label"} - set(stripped))
        if orphaned:
            raise ValueError(f"field role(s) not in roles: {', '.join(orphaned)}")
        return self


class SignerIn(BaseModel):
    """One recipient row in a submission-create request.

    ``order`` is the routing-order group (0-based): recipients with equal
    values are reached in parallel; a group's turn comes only once every
    lower group's *signers* have completed. Omitting it everywhere
    (default 0) keeps the original everyone-at-once behavior.

    ``is_cc`` marks a DocuSign-style "receives a copy" recipient: they're
    emailed a copy when routing reaches their group (and the signed PDF at
    completion), never sign, and never block routing. CC rows carry no
    role — it's normalized to ``""``.
    """

    role: str = ""
    user_id: int
    order: int = Field(0, ge=0, le=100)
    is_cc: bool = False

    @model_validator(mode="after")
    def _validate_role(self) -> "SignerIn":
        if self.is_cc:
            self.role = ""
        elif not self.role.strip():
            raise ValueError("role must be a non-empty string for signers")
        return self


class SubmissionCreate(BaseModel):
    """Body for POST /api/submissions.

    The signer rows in ``signers`` must map every role that appears on the
    template's fields exactly once, with no extra roles and no duplicates;
    the router validates this (and that every ``user_id`` exists) before
    creating anything. CC rows (``is_cc``) are free-form additions.
    """

    template_id: int
    title: str
    message: str | None = None
    signers: list[SignerIn]
    # Optional deadline; naive datetimes are taken as UTC. Must lie in the
    # future — an envelope born expired could never be signed.
    expires_at: datetime | None = None
    # Reminder policy for this envelope; defaults match the original
    # hard-coded behavior (on, every 3 days). The cap of 3 reminders per
    # signer is not sender-configurable.
    reminders_enabled: bool = True
    reminder_interval_days: int = Field(3, ge=1, le=30)
    # Save without sending: the envelope is created fully formed but no
    # recipient is emailed (or can even see it) until POST /{id}/send.
    draft: bool = False

    @field_validator("expires_at")
    @classmethod
    def _validate_expires_at(cls, value: datetime | None) -> datetime | None:
        return validate_future_expiry(value)


class SubmissionPatch(BaseModel):
    """Body for PATCH /api/submissions/{id} — sender/admin correcting a pending
    (or draft) envelope's title, message, expiration, and/or reminder policy
    (the DocuSign "advanced options" correctable set). At least one field
    must be present in the request body; omitting all is a no-op and
    rejected with 422.

    ``message`` and ``expires_at`` are nullable and clearable: an explicit
    ``null`` clears the stored value, while omitting the key entirely leaves
    it untouched — the two are distinguished via ``model_fields_set`` (which
    key was actually sent), not via the field's Python value, since both
    cases end up with ``None``. ``title`` stays required once the envelope
    exists — it can be *changed* but never *cleared* — so an explicit
    ``"title": null`` is rejected with 422 rather than silently ignored;
    the same goes for the two reminder fields, whose ``None`` means only
    "not provided".
    """

    title: str | None = None
    message: str | None = None
    # Clearable deadline: explicit null = "never expires". A non-null value
    # must lie in the future — same rule as at creation (and exactly how a
    # stale-expiry draft gets rescued into sendability).
    expires_at: datetime | None = None
    reminders_enabled: bool | None = None
    reminder_interval_days: int | None = Field(None, ge=1, le=30)

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be empty")
        if len(stripped) > 255:
            raise ValueError("title must be at most 255 characters")
        return stripped

    @field_validator("expires_at")
    @classmethod
    def _validate_expires_at(cls, value: datetime | None) -> datetime | None:
        return validate_future_expiry(value)

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "SubmissionPatch":
        provided = self.model_fields_set
        patchable = ("title", "message", "expires_at", "reminders_enabled", "reminder_interval_days")
        if not any(name in provided for name in patchable):
            raise ValueError(f"at least one of {', '.join(patchable)} is required")
        if "title" in provided and self.title is None:
            raise ValueError("title cannot be cleared")
        if "reminders_enabled" in provided and self.reminders_enabled is None:
            raise ValueError("reminders_enabled must not be null")
        if "reminder_interval_days" in provided and self.reminder_interval_days is None:
            raise ValueError("reminder_interval_days must not be null")
        return self


class SubmitterReplace(BaseModel):
    """Body for PUT /api/submissions/{id}/submitters/{submitter_id} — replace a
    pending signer with a different user (sender/admin correction)."""

    user_id: int


class UserBrief(BaseModel):
    """Minimal user identity, embedded in submitter/submission responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    is_external: bool


class UserOut(BaseModel):
    """Response shape for GET /api/users and PUT /api/users/{id}."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    is_admin: bool
    is_external: bool
    can_send: bool


class UserUpdate(BaseModel):
    """Body for PUT /api/users/{id} — a two-tier update, all fields optional.

    The router uses ``exclude_unset=True`` to tell "field absent" from an
    explicit value, so a request only has to touch the fields it means to
    change:

    - ``is_admin``/``can_send``: admin-only (the caller must be an admin;
      the existing self-demotion guard on ``is_admin`` still applies).
    - ``name``/``email``: contact correction for an external signer — any
      sender may touch these, but only on a target user with
      ``is_external`` set (internal identity comes from SSO/login, not a
      manual edit). ``email`` is normalized the same way as
      :class:`UserCreate`'s and is additionally checked by the router for
      uniqueness and for staying outside the internal domain allowlist.

    Every field is nullable in the type (so the model can express "absent"),
    but an explicit ``null`` for any of them is still rejected with a 422 —
    ``None`` is not a meaningful value for a bool flag or a contact field,
    only "not provided" is, and that's already handled by leaving the key
    out of the payload entirely (``exclude_unset=True`` on the router side).
    """

    is_admin: bool | None = None
    can_send: bool | None = None
    name: str | None = None
    email: str | None = None

    @field_validator("is_admin")
    @classmethod
    def _reject_null_is_admin(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("is_admin must not be null")
        return value

    @field_validator("can_send")
    @classmethod
    def _reject_null_can_send(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("can_send must not be null")
        return value

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("email must not be null")
        normalized = value.strip().lower()
        if not re.fullmatch(EMAIL_RE, normalized):
            raise ValueError("must be a valid email address")
        return normalized

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name must not be empty")
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be empty")
        return stripped


class UserCreate(BaseModel):
    """Body for POST /api/users — provision a signer by email ahead of their first login."""

    email: str
    name: str | None = None

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(EMAIL_RE, normalized):
            raise ValueError("must be a valid email address")
        return normalized

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TemplateBrief(BaseModel):
    """Minimal template identity, embedded in submission responses.

    ``is_adhoc`` lets the frontend suppress internal ``signer-N`` role
    strings on one-off envelopes (they're bookkeeping ids, never display
    text) without each view rediscovering that rule.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_adhoc: bool


class SubmitterOut(BaseModel):
    """Response shape for a single submitter within a submission."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user: UserBrief
    role: str
    status: str
    signed_at: datetime | None
    email_status: str | None = None
    last_reminded_at: datetime | None = None
    reminder_count: int = 0
    order_index: int = 0
    is_cc: bool = False


class SubmissionOut(BaseModel):
    """Response shape for a submission, including its submitters."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    # Random ID stamped on the signed PDF's watermark and certificate —
    # exposed so the stamp on an externally received document can be
    # matched back to its envelope.
    public_uid: str
    title: str
    message: str | None
    status: str
    created_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None = None
    reminders_enabled: bool = True
    reminder_interval_days: int = 3
    template: TemplateBrief
    sender: UserBrief = Field(validation_alias="creator")
    submitters: list[SubmitterOut]
    my_submitter_id: int | None = None
    has_certificate: bool = False
    # Whether the *viewer* archived this envelope out of their own lists
    # (per-user hide; see SubmissionArchive) — set by the routers, not
    # derived from the submission row.
    archived_by_me: bool = False


class AuditEventOut(BaseModel):
    """One audit-trail entry for GET /api/submissions/{id}/events.

    ``ip_address`` is deliberately not exposed — the sender-facing timeline
    doesn't need signer IPs; they stay queryable in the database for a real
    forensic need.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    event: str
    created_at: datetime
    actor: UserBrief | None
    detail: dict[str, Any] | None


class FormDataEntryOut(BaseModel):
    """One data field's entry in an envelope's form data (DocuSign "Form Data").

    ``value`` is ``None`` until the owning recipient completes (and for
    optional fields they left blank). Signature/initials/label fields are
    not data fields and never appear here — the signed PDF is their record.
    """

    submitter_id: int
    recipient: UserBrief
    # "" for ad-hoc envelopes, whose signer-N role strings are internal
    # bookkeeping ids (same suppression rule as the certificate).
    role: str
    field_id: str
    field_type: str
    page: int
    value: Any | None = None
    signed_at: datetime | None = None


class FormDataOut(BaseModel):
    """Response for GET /api/submissions/{id}/form-data."""

    submission_id: int
    public_uid: str
    title: str
    status: str
    entries: list[FormDataEntryOut]


class SignSubmissionBrief(BaseModel):
    """Submission identity shown to a submitter on their signing page."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message: str | None
    status: str
    # Lets the signing page show "expires on ..." (and an expired state as
    # soon as the deadline passes, before the daily sweep flips the status).
    expires_at: datetime | None = None


class SignTemplateBrief(BaseModel):
    """Template identity + full field list shown to a submitter on their signing page."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    page_count: int
    fields: list[FieldDef]


class SignerViewOut(BaseModel):
    """Response shape for GET /api/sign/{submitter_id}."""

    submission: SignSubmissionBrief
    template: SignTemplateBrief
    my_fields: list[str]
    my_status: str
    # False while earlier-order submitters haven't all completed: the signing
    # page shows a "you'll be notified when it's your turn" state and the
    # /complete route rejects with 409.
    my_turn: bool = True
    # The signer's display name — the signing page renders it into `name`
    # fields; external signers have no auth session to read it from.
    my_name: str
    saved_signature_id: int | None
    # role -> that submitter's display name, one entry per submitter on this
    # submission (including the caller). Lets the signing page label every
    # field — including co-signers' fields, shown read-only — by the actual
    # person's name instead of the raw role string, which for an ad-hoc
    # envelope is an internal `signer-N` bookkeeping id never meant to be
    # user-facing (and reads better than a template role like "Manager" too).
    role_names: dict[str, str]


class SignTokenViewOut(BaseModel):
    """Response for GET /api/sign/token/{access_uid} — the external landing page."""

    status: Literal["open", "already_signed", "completed", "cancelled", "declined"]
    title: str
    sender_name: str
    masked_email: str


class SignTokenVerifyIn(BaseModel):
    """Body for POST /api/sign/token/{access_uid}/verify."""

    code: str


class SignTokenVerifyOut(BaseModel):
    """Response for a successful verify: the submitter to drive /api/sign/{id} with."""

    submitter_id: int


class AttachmentOut(BaseModel):
    """Response for POST /api/sign/{submitter_id}/attachment."""

    attachment_id: int
    filename: str


class SignatureImageIn(BaseModel):
    """Body for POST /api/sign/{submitter_id}/signature."""

    image: str


class SignatureOut(BaseModel):
    """Response for POST /api/sign/{submitter_id}/signature."""

    signature_id: int


class SignCompleteIn(BaseModel):
    """Body for POST /api/sign/{submitter_id}/complete.

    ``values`` maps field id -> client-supplied value. Only ``signature``
    (int signature id), ``date`` (ISO ``YYYY-MM-DD`` string), ``checkbox``
    (bool), and ``text`` (str, <=500 chars) field types are expected here;
    ``name`` fields are filled in server-side at stamping time (Task 7) and
    are never required from the client.
    """

    values: dict[str, Any]


class SignDeclineIn(BaseModel):
    """Body for POST /api/sign/{submitter_id}/decline."""

    reason: str | None = Field(None, max_length=500)


class SubmissionCancelIn(BaseModel):
    """Body for POST /api/submissions/{id}/cancel. The whole body is optional
    (voiding without a reason stays a bare POST), but a reason, when given,
    lands in the audit trail and the void notification emails."""

    reason: str | None = Field(None, max_length=500)
