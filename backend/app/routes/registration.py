import asyncio
import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.registration import RegisterResponse
from app.services.excel_parser import parse_excel_upload
from app.services.livestorm_client import LivestormAPIError, LivestormClient
from app.services.mapping_service import normalize_session_ids, validate_mapping_and_rows
from app.services.payload_builder import build_bulk_job_payload
from app.services.row_metadata import build_row_results


router = APIRouter(tags=["registration"])
BULK_JOB_TASK_LIMIT = 50
LIVESTORM_REQUEST_DELAY_SECONDS = 1.25


def iter_chunks(items: list[dict], size: int) -> list[tuple[int, list[dict]]]:
    return [
        (start_index, items[start_index:start_index + size])
        for start_index in range(0, len(items), size)
    ]


@router.post("/register", response_model=RegisterResponse)
async def register_people(
    api_key: str = Form(...),
    session_ids: str = Form(...),
    mapping: str = Form(...),
    file: UploadFile = File(...),
) -> RegisterResponse:
    try:
        parsed = await parse_excel_upload(file)
        mapping_dict = json.loads(mapping)
        session_id_list = normalize_session_ids(session_ids)
        validation = validate_mapping_and_rows(mapping_dict, parsed["rows"])

        tasks = build_bulk_job_payload(parsed["rows"], validation["column_to_attribute"])
        row_results = build_row_results(parsed["rows"], validation["column_to_attribute"])
        task_chunks = iter_chunks(tasks, BULK_JOB_TASK_LIMIT)
        total_job_count = len(session_id_list) * len(task_chunks)

        async with LivestormClient(api_key=api_key.strip()) as client:
            jobs = []
            created_job_count = 0
            for session_id in session_id_list:
                for chunk_index, (row_start_index, chunk_tasks) in enumerate(task_chunks, start=1):
                    created = await client.create_bulk_job(session_id=session_id, tasks=chunk_tasks)
                    created_job_count += 1
                    jobs.append(
                        {
                            "session_id": session_id,
                            "job_id": created["job_id"],
                            "status": created.get("status", "pending"),
                            "chunk_index": chunk_index,
                            "chunk_count": len(task_chunks),
                            "row_start": row_start_index + 2,
                            "row_count": len(chunk_tasks),
                            "row_results": row_results[
                                row_start_index:row_start_index + len(chunk_tasks)
                            ],
                        }
                    )
                    if created_job_count < total_job_count:
                        await asyncio.sleep(LIVESTORM_REQUEST_DELAY_SECONDS)

        return RegisterResponse(
            jobs=jobs,
            duplicate_emails=validation["duplicate_emails"],
            row_count=len(parsed["rows"]),
            row_results=row_results,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid mapping payload") from exc
    except LivestormAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
