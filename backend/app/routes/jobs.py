from fastapi import APIRouter, HTTPException, Request

from app.schemas.jobs import (
    JobStatusRequest,
    JobStatusResponse,
    RetryFailedRowsRequest,
    RetryFailedRowsResponse,
)
from app.services.livestorm_client import LivestormAPIError, LivestormClient


router = APIRouter(tags=["jobs"])


@router.post("/job-status", response_model=JobStatusResponse)
async def job_status(request: Request, payload: JobStatusRequest) -> JobStatusResponse:
    token = request.session.get("livestorm_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated. Please connect your Livestorm account.")
    try:
        async with LivestormClient(token=token, use_bearer=True) as client:
            status_response = await client.get_job_status(
                session_id=payload.session_id,
                job_id=payload.job_id,
            )
        return JobStatusResponse(**status_response)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LivestormAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/retry-failed", response_model=RetryFailedRowsResponse)
async def retry_failed_rows(request: Request, payload: RetryFailedRowsRequest) -> RetryFailedRowsResponse:
    token = request.session.get("livestorm_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated. Please connect your Livestorm account.")
    try:
        results = []
        async with LivestormClient(token=token, use_bearer=True) as client:
            for registrant in payload.registrants:
                existing_people = await client.list_session_people(
                    session_id=payload.session_id,
                    email=registrant.email,
                )
                if existing_people:
                    results.append(
                        {
                            "row_number": registrant.row_number,
                            "email": registrant.email,
                            "status": "registered",
                            "error": "",
                            "raw": existing_people[0],
                        }
                    )
                    continue

                fields = [
                    {
                        "id": field.get("attribute_id") or field.get("id"),
                        "value": field.get("value", ""),
                    }
                    for field in registrant.fields
                    if field.get("value")
                ]
                try:
                    created = await client.register_person(
                        session_id=payload.session_id,
                        fields=fields,
                    )
                    results.append(
                        {
                            "row_number": registrant.row_number,
                            "email": registrant.email,
                            "status": "succeeded",
                            "error": "",
                            "raw": created.get("raw", {}),
                        }
                    )
                except LivestormAPIError as exc:
                    results.append(
                        {
                            "row_number": registrant.row_number,
                            "email": registrant.email,
                            "status": "failed",
                            "error": str(exc),
                            "raw": {},
                        }
                    )
        return RetryFailedRowsResponse(session_id=payload.session_id, results=results)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
