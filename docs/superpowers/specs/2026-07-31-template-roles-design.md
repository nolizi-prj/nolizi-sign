# First-class template roles (additional signers on templates)

Date: 2026-07-31
Status: approved for implementation (autonomous session; assumptions noted below)

## Problem

Multiple signers per envelope already work end-to-end: `Submitter` rows are
per-signer, `POST /api/submissions` takes a `signers` list mapping each
template role to a user, everyone signs in any order, and completion fires
when the last signer finishes. The template builder even has a Roles card.

But roles exist only *implicitly*, as the `role` string on each field:

- A role added in the builder is kept in component state only. Save persists
  fields; a role with no fields yet silently vanishes on reload.
- The Send flow derives roles from fields, so a fieldless role never shows up
  as an assignable signer.
- There is no way to delete a role in the builder.

Net effect: "add an additional signer to a template" only works if you
remember to place at least one field for them before saving — otherwise the
role is lost with no feedback. This spec makes roles a first-class, persisted
attribute of a template.

### Assumption (autonomous session)

The request "we should be able to add additional signer in the template too"
is read as: template roles should be robust, persistent, and manageable —
not as send-time extra signers or per-send field placement (both explicitly
out of scope in the original design doc).

## Design

### Data model

- `templates.roles` — new `JSONB` column, `list[str]`, `server_default '[]'`,
  not null. Ordered; order drives swatch colors and Send-flow listing.
- Alembic migration adds the column and backfills existing rows with the
  distinct roles of their `fields`, in order of first appearance.

### API

- `TemplateOut` gains `roles: list[str]`.
- `PUT /api/templates/{id}/fields` body gains optional `roles: list[str]`.
  - When provided: roles must be unique, non-empty after trimming; every
    `field.role` must appear in `roles`, else 422.
  - When omitted (back-compat): roles are derived from the submitted fields,
    preserving previous behavior.
- Submission-create validation (`_validate_role_mapping`) validates `signers`
  against the union of `template.roles` and the roles present on fields
  (union guards legacy rows where `roles` may be stale or empty).
- New send-time rule: a mapped role with zero fields is rejected with
  `422 role(s) have no signable fields: X` — a signer with nothing to fill
  cannot meaningfully sign, and the signing view is untested for that case.
  The ad-hoc path enforces the same rule server-side (the compose UI already
  enforces it client-side). The ad-hoc path stores the signer roles as the
  throwaway template's `roles`.

### Frontend

- `TemplateOut` type gains `roles: string[]`.
- Template builder:
  - Roles initialize from `template.roles` (falling back to deriving from
    fields for templates saved before this change), and are persisted by
    Save alongside fields.
  - A fresh template starts with an empty role list and a hint to add one —
    no auto-seeded "Signer 1" placeholder. Now that roles persist, a
    placeholder the sender never used would survive as a fieldless role and
    block sending (this broke the sign-flow e2e before it was caught).
  - Roles can be deleted, down to zero; deleting a role also deletes its
    fields (with a confirm dialog when fields exist).
  - A role with no fields shows a "no fields" warning chip, mirroring the
    envelope compose view.
- Send flow (`SendView`): lists `template.roles` (same fallback), shows a
  "no fields" note on fieldless roles, and blocks Send until the template is
  fixed in the builder.

### Error handling

All new validation failures are 422s with actionable messages naming the
offending role(s). No changes to signing, stamping, completion, or
notification paths.

### Testing

Backend (pytest, Postgres): roles round-trip through PUT/GET; 422 when a
field references a role not in `roles`; derive-from-fields when `roles`
omitted; send blocked for a fieldless mapped role (template and ad-hoc
paths); existing multi-signer tests keep passing. Frontend: `vue-tsc` and
`npm run build` (no component test harness exists in this repo).

## Out of scope

Send-time extra signers, per-send field placement, sequential signing order,
external signers, fieldless "approver" signers.
