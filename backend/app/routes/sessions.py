from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.routes.helpers import livestorm_error_to_http, require_token
from app.schemas.sessions import RegisteredEmailsResponse, SessionDetailResponse, SessionListResponse
from app.services.livestorm_client import LivestormAPIError, LivestormClient, TooManyRecordsError
from app.services.sessions_service import (
    REGISTERED_CHECK_LIMIT,
    build_event_search_params,
    build_session_list_params,
    is_session_id,
    next_page,
    registrant_emails,
    session_detail,
    sessions_from_event_search,
    summarize_session_list,
)

router = APIRouter(tags=["sessions"])

SESSION_NOT_FOUND_DETAIL = "No session found with this ID in your workspace."


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    request: Request,
    token: str = Depends(require_token),
    q: str = "",
    scope: Literal["upcoming", "any"] = "upcoming",
    date_from: Optional[int] = Query(None, ge=0),
    date_to: Optional[int] = Query(None, ge=0),
    page: int = Query(0, ge=0),
) -> SessionListResponse:
    """Sessions for the picker, 10 per page.

    `q` is either a session ID (exact lookup, any status) or part of an event
    title. `scope="upcoming"` keeps upcoming and live sessions only; dates are
    unix timestamps bounding the session start.
    """
    query = q.strip()
    try:
        async with LivestormClient(token=token, use_bearer=True) as client:
            if is_session_id(query):
                try:
                    payload = await client.get_session(query)
                except LivestormAPIError as exc:
                    if exc.status_code == 404:
                        return SessionListResponse(sessions=[])
                    raise
                return SessionListResponse(sessions=[session_detail(payload)])

            if query:
                payload = await client.list_events(build_event_search_params(query, scope, page))
                sessions = sessions_from_event_search(payload, scope, date_from, date_to)
            else:
                payload = await client.list_sessions(
                    build_session_list_params(scope, date_from, date_to, page)
                )
                sessions = summarize_session_list(payload)
        return SessionListResponse(sessions=sessions, next_page=next_page(payload))
    except LivestormAPIError as exc:
        raise livestorm_error_to_http(request, exc) from exc


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(request: Request, session_id: str, token: str = Depends(require_token)) -> SessionDetailResponse:
    """One session with its event's registration form fields."""
    if not is_session_id(session_id):
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND_DETAIL)

    try:
        async with LivestormClient(token=token, use_bearer=True) as client:
            payload = await client.get_session(session_id.strip())
        return SessionDetailResponse(**session_detail(payload))
    except LivestormAPIError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND_DETAIL) from exc
        raise livestorm_error_to_http(request, exc) from exc


@router.get("/sessions/{session_id}/emails", response_model=RegisteredEmailsResponse)
async def get_registered_emails(request: Request, session_id: str, token: str = Depends(require_token)) -> RegisteredEmailsResponse:
    """Emails already registered to a session, to skip them before sending a batch.

    Sessions over REGISTERED_CHECK_LIMIT registrants are not listed (one call
    tells): the answer then says checked=false and Livestorm refuses duplicates.
    """
    if not is_session_id(session_id):
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND_DETAIL)

    try:
        async with LivestormClient(token=token, use_bearer=True) as client:
            people = await client.list_session_people(
                session_id=session_id.strip(), max_records=REGISTERED_CHECK_LIMIT
            )
        return RegisteredEmailsResponse(
            session_id=session_id.strip(), emails=registrant_emails(people), registrants_count=len(people)
        )
    except TooManyRecordsError as exc:
        return RegisteredEmailsResponse(
            session_id=session_id.strip(), emails=[], checked=False, registrants_count=exc.record_count
        )
    except LivestormAPIError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND_DETAIL) from exc
        raise livestorm_error_to_http(request, exc) from exc
