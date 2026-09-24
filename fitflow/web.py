"""Production entry point: one server for both the API and the web app.

    /api/*   -> the FastAPI app (fitflow/api/main.py)
    /*       -> the built React app (frontend/dist), with index.html as the fallback

Serving both from one origin means one service to deploy and no CORS configuration.
Run with:  uvicorn fitflow.web:web --host 0.0.0.0 --port 8000
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from fitflow.api.main import app as api, init_db

FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", Path(__file__).resolve().parents[1] / "frontend" / "dist"))


class SinglePageApp(StaticFiles):
    """Static files, but unknown paths return index.html.

    The React app has its own routes (/chat, /progress...). When the user refreshes on /chat, the
    server has no file called "chat" - it must return index.html and let React Router take over.
    """

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as e:
            if e.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # a mounted app's own lifespan doesn't run, so start the database here
    yield


web = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
web.mount("/api", api)
if FRONTEND_DIST.is_dir():  # missing when running the API alone, e.g. in tests
    web.mount("/", SinglePageApp(directory=FRONTEND_DIST, html=True), name="frontend")
