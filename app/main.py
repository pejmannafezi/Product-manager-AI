from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config, db, i18n
from app.auth import auth_middleware
from app.routers import (checklists, compliance, dashboard, intake, issues,
                         knowledge, pages, projects, tasks)
from app.seed import run_seeds


def _auto_ingest():
    """If the knowledge base is empty and a guide docx sits in data/, ingest it
    so a fresh deployment comes up populated without shell access."""
    docs = sorted(config.DATA_DIR.glob("*.docx"))
    if not docs:
        return
    with db.db_session() as conn:
        if conn.execute("SELECT COUNT(*) FROM kb_chapters").fetchone()[0]:
            return
    try:
        from scripts.ingest_docx import ingest
        ingest(docs[0])
    except Exception:
        pass  # the Knowledge page offers a manual import as fallback


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    with db.db_session() as conn:
        run_seeds(conn)
    i18n.load()
    _auto_ingest()
    yield


app = FastAPI(title="AI PM Command Center", lifespan=lifespan)
app.middleware("http")(auth_middleware)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

for r in (dashboard, projects, tasks, checklists, knowledge, compliance, issues, intake, pages):
    app.include_router(r.router)
