import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.routes.auth import router as auth_router
from app.routes.contacts import router as contacts_router
from app.routes.jobs import router as jobs_router
from app.routes.preview import router as preview_router
from app.routes.registration import router as registration_router
from app.routes.transfer import router as transfer_router
from app.routes.validation import router as validation_router

_SESSION_SECRET = os.environ.get("SESSION_SECRET_KEY", "dev-secret-change-in-production")

app = FastAPI(title="StormBatch API")

app.add_middleware(
    SessionMiddleware,
    secret_key=_SESSION_SECRET,
    same_site="lax",
    https_only=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(preview_router, prefix="/api")
app.include_router(registration_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(transfer_router, prefix="/api")
app.include_router(validation_router, prefix="/api")
app.include_router(contacts_router, prefix="/api")


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"

if FRONTEND_DIST.exists() and FRONTEND_ASSETS.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_ASSETS),
        name="frontend-assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str) -> FileResponse:
        requested_file = FRONTEND_DIST / full_path
        if full_path and requested_file.is_file():
            return FileResponse(requested_file)
        # index.html must never be cached so browsers always fetch the latest
        # version after a deploy (hashed assets can still cache indefinitely).
        return FileResponse(
            FRONTEND_DIST / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
