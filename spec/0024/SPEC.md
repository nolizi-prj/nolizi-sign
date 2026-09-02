# Specification: bounded document preparation

1. The sender UI rejects a source file or source set above 20 MB before upload
   or preview and preserves the prior prepared document.
2. The Worker checks source sizes before reading file bodies into typed arrays.
3. A document or combined envelope above 500 pages is rejected before storage.
4. PDF preview caps device-pixel ratio and canvas allocation at 16 million
   pixels, including unusually proportioned pages.
5. Rejections use actionable text and do not clear a previously valid document.
6. Document pickers do not pass the long extension allowlist into the Linux
   desktop portal. Pumasi validates extensions immediately after selection so
   portal/file-manager failures cannot be amplified by native filter parsing.

The upload utility tests verify individual and combined byte limits. Worker
contract coverage must retain these bounds when conversion moves to background
jobs.
