from fastapi import Request

from app.core.config import settings


def client_ip(request: Request) -> str | None:
    """The caller's IP. X-Forwarded-For is trusted only as far as settings.trusted_proxy_hops."""
    peer = request.client.host if request.client else None
    hops = settings.trusted_proxy_hops
    if hops > 0:
        parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(parts) >= hops:
            # Each trusted proxy appends the address it received the connection from. The Nth entry
            # from the right was written by the outermost proxy we trust: that is the real client.
            return parts[-hops]
    return peer