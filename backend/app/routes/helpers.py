from fastapi import HTTPException, Request

from app.services.livestorm_client import LivestormAPIError
from app.services.token_store import clear_token, read_token

NOT_AUTHENTICATED_DETAIL = "Not authenticated. Please connect your Livestorm account."
SESSION_EXPIRED_DETAIL = "Your Livestorm session has expired. Please reconnect your account."


def require_token(request: Request) -> str:
    """Route dependency: the connected user's Livestorm token, or 401."""
    token = read_token(request.session)
    if not token:
        raise HTTPException(status_code=401, detail=NOT_AUTHENTICATED_DETAIL)
    return token


def livestorm_error_to_http(request: Request, exc: LivestormAPIError) -> HTTPException:
    """Map a Livestorm API error to an HTTP response.

    A 401 from Livestorm means the stored OAuth token is no longer valid, so we
    also drop it from the session — the frontend logs the user out on 401 and
    the auth status endpoint stays consistent.
    """
    if exc.status_code == 401:
        clear_token(request.session)
        return HTTPException(status_code=401, detail=SESSION_EXPIRED_DETAIL)
    return HTTPException(status_code=502, detail=str(exc))
