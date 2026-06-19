"""Optional password gate for shared/internet deployments.

If the PMAI_PASSWORD environment variable is set, every page requires login;
if it is unset (local use), the app behaves exactly as before — no login.
"""
import hashlib
import os

from fastapi.responses import RedirectResponse

COOKIE = "pmai_auth"
EXEMPT_PREFIXES = ("/static/", "/login")


def password() -> str:
    return os.environ.get("PMAI_PASSWORD", "")


def token() -> str:
    return hashlib.sha256(f"pmai:{password()}".encode()).hexdigest()


async def auth_middleware(request, call_next):
    if not password() or request.url.path.startswith(EXEMPT_PREFIXES):
        return await call_next(request)
    if request.cookies.get(COOKIE) == token():
        return await call_next(request)
    return RedirectResponse("/login", status_code=303)
