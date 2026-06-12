from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config, db, i18n
from app.routers import (checklists, compliance, dashboard, intake, issues,
                         knowledge, pages, projects, tasks)
from app.seed import run_seeds


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    with db.db_session() as conn:
        run_seeds(conn)
    i18n.load()
    yield


app = FastAPI(title="AI PM Command Center", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

for r in (dashboard, projects, tasks, checklists, knowledge, compliance, issues, intake, pages):
    app.include_router(r.router)
