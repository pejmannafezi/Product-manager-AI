from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app import auth
from app.web import render

router = APIRouter()


@router.post("/lang/{code}")
def set_lang(code: str, request: Request):
    back = request.headers.get("referer") or "/"
    resp = RedirectResponse(back, status_code=303)
    resp.set_cookie("lang", code if code in ("en", "fa") else "en", max_age=3600 * 24 * 365)
    return resp


@router.get("/login")
def login_form(request: Request, error: int = 0):
    if not auth.password():
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html", error=error)


@router.post("/login")
def login(request: Request, password: str = Form(...)):
    if auth.password() and password == auth.password():
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(auth.COOKIE, auth.token(), max_age=3600 * 24 * 30, httponly=True)
        return resp
    return RedirectResponse("/login?error=1", status_code=303)
