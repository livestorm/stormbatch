from fastapi import APIRouter, HTTPException, Request

from app.routes.helpers import livestorm_error_to_http
from app.schemas.bulk_jobs import BulkJobRequest, BulkJobResponse
from app.services.bulk_job_service import build_bulk_tasks
from app.services.livestorm_client import LivestormAPIError, LivestormClient
from app.services.sessions_service import is_session_id

router = APIRouter(tags=["bulk-jobs"])


@router.post("/bulk-jobs", response_model=BulkJobResponse)
async def create_bulk_job(request: Request, payload: BulkJobRequest) -> BulkJobResponse:
    """Create one Livestorm bulk registration job for a chunk of up to 50 registrants.

    The browser already holds every row (from the preview or the source session),
    so it sends one small JSON chunk per job instead of re-uploading the file.
    """
    token = request.session.get("livestorm_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated. Please connect your Livestorm account.")

    session_id = payload.session_id.strip()
    if not is_session_id(session_id):
        raise HTTPException(status_code=400, detail=f"'{session_id}' isn't a valid Livestorm session ID.")

    try:
        tasks = build_bulk_tasks(payload.registrants)
        async with LivestormClient(token=token, use_bearer=True) as client:
            created = await client.create_bulk_job(session_id=session_id, tasks=tasks)
        return BulkJobResponse(session_id=session_id, job_id=created["job_id"], status=created["status"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LivestormAPIError as exc:
        raise livestorm_error_to_http(request, exc) from exc
