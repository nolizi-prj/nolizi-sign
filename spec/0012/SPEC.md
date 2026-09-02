# SPEC 0012 — Cloudflare template contract

## Required behavior

- Multipart template upload normalizes supported files to PDF.
- List/get/PDF include owned and unarchived shared templates.
- Only the owner may update fields/roles, toggle sharing, or archive.
- A viewer may copy a shared template; the copy is private and owns its bytes.
- Shared templates may create envelopes.
- `save-as-template` copies an envelope document and field layout into a private
  template with ordered `Signer N` placeholder roles.
- Page bounds and payload shapes are validated before persistence.

## Acceptance

Worker tests cover upload/build/archive, shared access and denied mutation,
independent copy/use, and envelope conversion. The root gate must pass.
Deployment is out of scope.

