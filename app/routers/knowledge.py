from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.agents.knowledge import KnowledgeAgent
from app.db import get_db
from app.services.ai import get_ai
from app.web import render

router = APIRouter()


@router.get("/knowledge")
def knowledge(request: Request, conn=Depends(get_db)):
    agent = KnowledgeAgent(conn, get_ai())
    return render(request, "knowledge.html", chapters=agent.chapters())


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
