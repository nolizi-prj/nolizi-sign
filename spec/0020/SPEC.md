# Specification: production authentication and dependency readiness

## Requirements

1. `GET /api/health` remains a dependency-free liveness probe.
2. `GET /api/ready` succeeds only when the production Durable Object can execute
   a SQLite query and the R2 bucket can be listed.
3. A readiness failure returns 503 with a correlation identifier, logs structured
   dependency detail, and does not disclose that detail to the client.
4. Internal readiness is unreachable through the Worker's public fetch surface.
5. OAuth identity claims come from the provider UserInfo endpoint using the
   access token obtained by the authorization-code exchange.
6. Missing access token, failed UserInfo, malformed email, or a verified-email
   claim other than literal `true` creates no user or session.

## Acceptance evidence

- A-962 covers the distinct liveness/readiness behavior and both bindings.
- A-963 covers fail-closed R2 readiness without client-side error leakage.
- A-500–A-506 cover authorization state, exchange, authenticated UserInfo,
  verified email, rejection paths, and session creation.

