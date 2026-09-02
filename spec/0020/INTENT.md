# Intent: production authentication and dependency readiness

Phase 1 must fail closed when its state/document dependencies are unavailable,
and OAuth must not create an application session from unverified claims.

This change separates shallow liveness from storage-backed readiness. It also
uses the OAuth provider's authenticated UserInfo endpoint after code exchange
instead of trusting a locally decoded, unverified ID-token payload. A verified
email claim is required explicitly.

