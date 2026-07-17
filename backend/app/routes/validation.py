from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.routes.helpers import livestorm_error_to_http
from app.services.livestorm_client import LivestormAPIError, LivestormClient

router = APIRouter(tags=["validation"])


class SessionFieldsRequest(BaseModel):
    session_id: str


@router.post("/session-fields")
async def get_session_fields(request: Request, body: SessionFieldsRequest) -> dict:
    token = request.session.get("livestorm_token")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please connect your Livestorm account.",
        )
    try:
        async with LivestormClient(token=token, use_bearer=True) as client:
            result = await client.get_session_fields(body.session_id)
        return {**result, "session_id": body.session_id}
    except LivestormAPIError as exc:
        raise livestorm_error_to_http(request, exc) from exc
