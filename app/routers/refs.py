"""Reference Library UI + API: documents/info the agents consult, either
globally (all projects) or scoped to one chosen project."""
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.db import get_db
from app.services import refs as refs_svc
from app.services.ai import get_ai
from app.services.docparse import DocParseError, extract_text
from app.web import render

router = APIRouter()


@router.get("/references")
def references_page(request: Request, error: str = "", conn=Depends(get_db)):
    globals_ = refs_svc.list_references(conn, scope="global")
    project_refs = refs_svc.list_references(conn, scope="project")
    projects = conn.execute("SELECT id, name FROM projects ORDER BY name").fetchall()
    return render(request, "references.html",
                  globals=globals_, project_refs=project_refs,
                  projects=projects, ai_on=get_ai().available, error=error)


@router.post("/api/references")
async def add_reference(
    scope: str = Form("global"),
    project_id: str = Form(""),
    title: str = Form(""),
    text: str = Form(""),
    file: UploadFile | None = File(None),
    conn=Depends(get_db),
):
    body = (text or "").strip()
    filename, mime = "", "text/plain"
    if file is not None and file.filename:
        data = await file.read()
        try:
            body = extract_text(file.filename, data)
        except DocParseError as exc:
            return RedirectResponse(f"/references?error={exc}", status_code=303)
        filename, mime = file.filename, file.content_type or "application/octet-stream"

    if not body:
        return RedirectResponse("/references?error=Add+a+file+or+paste+some+text.",
                                status_code=303)

    pid = int(project_id) if (scope == "project" and project_id.isdigit()) else None
    if scope == "project" and not pid:
        return RedirectResponse("/references?error=Choose+a+project+for+a+project+reference.",
                                status_code=303)

    refs_svc.add_reference(conn, scope, pid, title, filename, mime, body)
    return RedirectResponse("/references", status_code=303)


@router.post("/api/references/{ref_id}/toggle")
def toggle_reference(ref_id: int, conn=Depends(get_db)):
    refs_svc.toggle_reference(conn, ref_id)
    return RedirectResponse("/references", status_code=303)


@router.post("/api/references/{ref_id}/delete")
def delete_reference(ref_id: int, conn=Depends(get_db)):
    refs_svc.delete_reference(conn, ref_id)
    return RedirectResponse("/references", status_code=303)
