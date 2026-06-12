from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.post("/lang/{code}")
def set_lang(code: str, request: Request):
    back = request.headers.get("referer") or "/"
    resp = RedirectResponse(back, status_code=303)
    resp.set_cookie("lang", code if code in ("en", "fa") else "en", max_age=3600 * 24 * 365)
    return resp
