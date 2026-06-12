from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse

from app import config
from app.agents.knowledge import KnowledgeAgent
from app.db import get_db
from app.services.ai import get_ai
from app.web import render

router = APIRouter()


@router.get("/knowledge")
def knowledge(request: Request, conn=Depends(get_db)):
    agent = KnowledgeAgent(conn, get_ai())
    return render(request, "knowledge.html", chapters=agent.chapters())


@router.post("/api/knowledge/import")
async def import_guide(file: UploadFile = File(...)):
    """Import/replace the guide docx through the browser, so deployed instances
    can be populated without shell access."""
    from scripts.ingest_docx import ingest
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = config.DATA_DIR / "ai-pm-guide.docx"
    path.write_bytes(await file.read())
    ingest(path, replace=True)
    return RedirectResponse("/knowledge", status_code=303)


@router.get("/knowledge/chapter/{number}")
def chapter(request: Request, number: int, conn=Depends(get_db)):
    agent = KnowledgeAgent(conn, get_ai())
    ch, sections = agent.chapter(number)
    if not ch:
        return RedirectResponse("/knowledge", status_code=303)
    return render(request, "chapter.html", chapter=ch, sections=sections)


@router.get("/search")
def search(request: Request, q: str = "", deep: int = 0, conn=Depends(get_db)):
    agent = KnowledgeAgent(conn, get_ai())
    results, ai_used = agent.search(q, deep=bool(deep)) if q else ([], False)
    return render(request, "search.html", q=q, deep=deep, results=results,
                  ai_used=ai_used, ai_on=get_ai().available)


@router.get("/api/search")
def api_search(q: str = "", deep: int = 0, conn=Depends(get_db)):
    agent = KnowledgeAgent(conn, get_ai())
    results, ai_used = agent.search(q, deep=bool(deep)) if q else ([], False)
    return {"ai_expanded": ai_used, "results": [dict(r) for r in results]}


@router.get("/glossary")
def glossary(request: Request, q: str = "", conn=Depends(get_db)):
    agent = KnowledgeAgent(conn, get_ai())
    return render(request, "glossary.html", terms=agent.glossary(q), q=q)
