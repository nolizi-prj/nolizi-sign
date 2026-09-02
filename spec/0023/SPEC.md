# Specification: safe signer-attachment filenames

1. PDF, PNG, and JPEG attachment types continue to be determined from file
   signatures, not the multipart MIME type.
2. Stored filenames are Unicode NFKC normalized and have control characters,
   path separators, reserved filename characters, redundant whitespace, and
   leading dots removed.
3. A supplied extension must agree with the verified byte type. JPEG accepts
   `.jpg` or `.jpeg`; the canonical stored extension is `.jpg`.
4. A missing or empty filename receives a safe type-derived filename.
5. A mismatch returns 422 and stores neither metadata nor bytes.

A-803 verifies deceptive-extension rejection and normalized storage.
