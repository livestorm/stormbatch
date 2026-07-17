import asyncio

from fastapi import APIRouter, HTTPException, Request

from app.schemas.transfer import (
    SessionPeopleRequest,
    SessionPeopleResponse,
    TransferJob,
    TransferRequest,
    TransferResponse,
)
from app.routes.helpers import livestorm_error_to_http
from app.services.livestorm_client import LivestormAPIError, LivestormClient
from app.services.transfer_service import extract_people_data

router = APIRouter(tags=["transfer"])

BULK_JOB_TASK_LIMIT = 50
LIVESTORM_REQUEST_DELAY_SECONDS = 0.25  # 4 req/s — safely under the 5 req/s burst limit


def _iter_chunks(items: list, size: int) -> list[tuple[int, list]]:
    return [
        (start, items[start: start + size])
        for start in range(0, len(items), size)
    ]


@router.post("/session-people", response_model=SessionPeopleResponse)
async def get_session_people(request: Request, payload: SessionPeopleRequest) -> SessionPeopleResponse:
    token = request.session.get("livestorm_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated. Please connect your Livestorm account.")
    try:
        async with LivestormClient(token=token, use_bearer=True) as client:
            people = await client.list_session_people(session_id=payload.session_id.strip())
        if not people:
            raise ValueError("No registrants found in this session.")
        data = extract_people_data(people)
        return SessionPeopleResponse(session_id=payload.session_id.strip(), **data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LivestormAPIError as exc:
        raise livestorm_error_to_http(request, exc) from exc


@router.post("/transfer", response_model=TransferResponse)
async def transfer_registrants(request: Request, payload: TransferRequest) -> TransferResponse:
    token = request.session.get("livestorm_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated. Please connect your Livestorm account.")

    if not payload.target_session_ids:
        raise HTTPException(status_code=400, detail="At least one target session ID is required.")
    if not payload.rows:
        raise HTTPException(status_code=400, detail="No registrants to transfer.")
    if "email" not in payload.included_fields:
        raise HTTPException(status_code=400, detail="Email field must be included.")

    try:
        tasks: list[dict] = []
        row_results: list[dict] = []

        for i, row in enumerate(payload.rows):
            email = row.get("email", "").strip()
            if not email:
                continue
            fields = [
                {"id": fid, "value": row.get(fid, "").strip()}
                for fid in payload.included_fields
                if row.get(fid, "").strip()
            ]
            tasks.append({"fields": fields})
            row_results.append({
                "row_number": i + 2,
                "email": email,
                "fields": [
                    {"attribute_id": fid, "value": row.get(fid, "")}
                    for fid in payload.included_fields
                ],
            })

        if not tasks:
            raise ValueError("No registrants with a valid email to transfer.")

        task_chunks = _iter_chunks(tasks, BULK_JOB_TASK_LIMIT)
        total_jobs = len(payload.target_session_ids) * len(task_chunks)
        created_count = 0
        jobs: list[dict] = []

        async with LivestormClient(token=token, use_bearer=True) as client:
            for session_id in payload.target_session_ids:
                for chunk_i, (row_offset, chunk_tasks) in enumerate(task_chunks):
                    result = await client.create_bulk_job(session_id=session_id, tasks=chunk_tasks)
                    created_count += 1
                    jobs.append({
                        "session_id": session_id,
                        "job_id": result["job_id"],
                        "status": result.get("status", "pending"),
                        "chunk_index": chunk_i + 1,
                        "chunk_count": len(task_chunks),
                        "row_start": row_offset + 2,
                        "row_count": len(chunk_tasks),
                        "row_results": row_results[row_offset: row_offset + len(chunk_tasks)],
                    })
                    if created_count < total_jobs:
                        await asyncio.sleep(LIVESTORM_REQUEST_DELAY_SECONDS)

        return TransferResponse(jobs=jobs, row_count=len(tasks), row_results=row_results)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LivestormAPIError as exc:
        raise livestorm_error_to_http(request, exc) from exc
