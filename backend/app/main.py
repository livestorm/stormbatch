from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes.jobs import router as jobs_router
from app.routes.preview import router as preview_router
from app.routes.registration import router as registration_router


app = FastAPI(title="StormBatch API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(preview_router, prefix="/api")
app.include_router(registration_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="frontend-assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str) -> FileResponse:
        requested_file = FRONTEND_DIST / full_path
        if full_path and requested_file.is_file():
            return FileResponse(requested_file)
        return FileResponse(FRONTEND_DIST / "index.html")
