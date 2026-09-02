# Safe document replacement

The envelope detail UI already offered a DocuSign-style Replace document action,
but production returned 501. Implement correction without ever moving a stored
signature onto an agreement that signer did not review.

Replacement supports the ordered multi-document contract and keeps the draft's
backing rendition synchronized so reopening the wizard cannot restore old bytes.
