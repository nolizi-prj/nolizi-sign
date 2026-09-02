# Specification

- Feedback is limited to 5 submissions per authenticated owner or anonymous IP
  in a rolling hour.
- Standalone conversion is limited to 20 requests per authenticated owner or
  anonymous IP in a rolling 10 minutes.
- `worker.ts` calls a non-public Durable Object route before parsing payloads or
  contacting GitHub/Microsoft Graph.
- The Worker refuses all `/__internal/` requests from the public surface.
- Limiter unavailability fails closed with 503; exhaustion returns 429 and
  `Retry-After`.

Acceptance cases A-953 and A-954 prove both bypass routes cross the persistent
limiter before their external-service/configuration behavior.
