# Versioned consent and separate completion evidence

The signing checkbox was only a client-side gate. A caller could omit it and
the production backend would still mark the signer complete. Completion must
store what was accepted and what bytes were reviewed, and the certificate
advertised by the UI must exist as its own protected artifact.
