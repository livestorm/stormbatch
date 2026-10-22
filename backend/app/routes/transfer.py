from fastapi import APIRouter, HTTPException, Request

from app.schemas.transfer import SessionPeopleRequest, SessionPeopleResponse
from app.routes.helpers import livestorm_error_to_http
from app.services.livestorm_client import LivestormAPIError, LivestormClient
from app.services.transfer_service import extract_people_data

router = APIRouter(tags=["transfer"])


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
