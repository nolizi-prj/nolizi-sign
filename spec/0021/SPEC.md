# Specification: field-specific signature and initials artifacts

1. Each signature or initials field resolves its stored signature reference for
   the same submitter during finalization.
2. The stamping core prefers the field-specific image over the legacy
   signer-level image.
3. An initials-only signer retains an image for legacy/certificate fallback.
4. If no initials image is available, render initials derived from the signer's
   name, never the full name.
5. A signature reference owned by another signer remains invalid.

A-607 verifies the initials-only and field-specific completion behavior.
