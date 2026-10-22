from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import IS_PRODUCTION, SESSION_SECRET
from app.routes.auth import router as auth_router
from app.routes.bulk_jobs import router as bulk_jobs_router
from app.routes.contacts import router as contacts_router
from app.routes.jobs import router as jobs_router
from app.routes.preview import router as preview_router
from app.routes.sessions import router as sessions_router
from app.routes.transfer import router as transfer_router
from app.services import excel_parser

app = FastAPI(title="StormBatch API")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=IS_PRODUCTION,
    # Expires with the browser session, as the About dialog promises.
    max_age=None,
)

if not IS_PRODUCTION:
    # Only for running the Vite dev server without its /api proxy.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def reject_oversized_uploads(request: Request, call_next):
    # Refuse big uploads from their Content-Length, before Starlette spools the
    # body to disk; the parser checks the actual size again.
    if request.url.path == "/api/preview":
        length = request.headers.get("content-length", "")
        # Allow for the multipart envelope around the file.
        if length.isdigit() and int(length) > excel_parser.MAX_UPLOAD_BYTES + 64 * 1024:
            return JSONResponse({"detail": excel_parser.upload_too_large_message()}, status_code=413)
    return await call_next(request)

app.include_router(auth_router, prefix="/api")
app.include_router(preview_router, prefix="/api")
app.include_router(bulk_jobs_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(transfer_router, prefix="/api")
app.include_router(contacts_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")


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

    _FRONTEND_ROOT = FRONTEND_DIST.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        # Resolve and require the file to sit inside dist/, so "../" segments
        # (plain or percent-encoded) can never reach files outside it.
        requested_file = (FRONTEND_DIST / full_path).resolve()
        if (
            full_path
            and requested_file.is_relative_to(_FRONTEND_ROOT)
            and requested_file.is_file()
        ):
            return FileResponse(requested_file)
        # index.html must never be cached so browsers always fetch the latest
        # version after a deploy (hashed assets can still cache indefinitely).
        return FileResponse(
            FRONTEND_DIST / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
