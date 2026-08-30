"""Small HTTP-request helpers shared across routers."""

from fastapi import Request


def client_ip(request: Request) -> str | None:
    """Return the caller's IP, honoring ``X-Forwarded-For``'s right-most entry.

    Railway (and most PaaS reverse proxies) terminate TLS in front of the
    app, so ``request.client.host`` is the proxy's own address, not the end
    user's — and appends the address it saw as its own last hop to the
    *end* of ``X-Forwarded-For`` (each hop prepends its own view of the
    "client" to the left of whatever it received). The Dockerfile runs
    uvicorn with ``--forwarded-allow-ips '*'``, so this header is trusted
    for *whatever the last hop reports* — but the *first* entry is not
    trustworthy: it's whatever the original client sent (nothing stops a
    signer from sending their own ``X-Forwarded-For: 1.2.3.4`` and having
    it land, unmodified, as the first entry ahead of Railway's own
    append), and that value would otherwise land in the ``signed`` audit
    event and on the Signature Certificate as if it were verified. Only
    the right-most entry — the one the trusted last-hop proxy itself
    appended — is safe to use. Falls back to ``request.client.host`` when
    there's no ``X-Forwarded-For`` at all (e.g. in tests, which talk to the
    app directly with no proxy in front).
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        parts = [part.strip() for part in forwarded_for.split(",") if part.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else None
