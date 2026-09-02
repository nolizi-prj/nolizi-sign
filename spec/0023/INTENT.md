# Intent: safe signer-attachment filenames

Signer attachments become part of the evidence package and may later be
downloaded, mailed, archived, or passed to an integration. Treat the multipart
filename as untrusted display data and ensure it cannot disguise the file type
verified from the bytes.
