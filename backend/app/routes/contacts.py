from fastapi import APIRouter, HTTPException, Request

from app.schemas.contacts import (
    ContactUpdateRequest,
    ContactUpdateResponse,
    SessionContactsRequest,
    SessionContactsResponse,
)
from app.services.contacts_service import extract_contacts
from app.services.livestorm_client import LivestormAPIError, LivestormClient

router = APIRouter(tags=["contacts"])

# Livestorm rejects updates to protected identity fields.
PROTECTED_FIELD_IDS = {"email"}


@router.post("/session-contacts", response_model=SessionContactsResponse)
async def get_session_contacts(request: Request, payload: SessionContactsRequest) -> SessionContactsResponse:
    token = request.session.get("livestorm_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated. Please connect your Livestorm account.")
    try:
        async with LivestormClient(token=token, use_bearer=True) as client:
            people = await client.list_session_people(session_id=payload.session_id.strip())
        if not people:
            raise ValueError("No registrants found in this session.")
        data = extract_contacts(people)
        return SessionContactsResponse(session_id=payload.session_id.strip(), **data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LivestormAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/update-contact", response_model=ContactUpdateResponse)
async def update_contact(request: Request, payload: ContactUpdateRequest) -> ContactUpdateResponse:
    token = request.session.get("livestorm_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated. Please connect your Livestorm account.")

    fields = [
        {"id": field.id.strip(), "value": field.value}
        for field in payload.fields
        if field.id.strip() and field.id.strip() not in PROTECTED_FIELD_IDS
    ]
    if not fields:
        raise HTTPException(
            status_code=400,
            detail="No editable fields to update. Email cannot be modified through the Livestorm API.",
        )

    try:
        async with LivestormClient(token=token, use_bearer=True) as client:
            await client.update_session_person(
                session_id=payload.session_id.strip(),
                person_id=payload.person_id.strip(),
                fields=fields,
                verify_email=payload.email.strip() or None,
            )
        return ContactUpdateResponse(
            session_id=payload.session_id.strip(),
            person_id=payload.person_id.strip(),
            status="updated",
            updated_fields={field["id"]: field["value"] for field in fields},
        )
    except LivestormAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
