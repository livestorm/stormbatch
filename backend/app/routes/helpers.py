from fastapi import HTTPException, Request

from app.services.livestorm_client import LivestormAPIError

SESSION_EXPIRED_DETAIL = "Your Livestorm session has expired. Please reconnect your account."


def livestorm_error_to_http(request: Request, exc: LivestormAPIError) -> HTTPException:
    """Map a Livestorm API error to an HTTP response.

    A 401 from Livestorm means the stored OAuth token is no longer valid, so we
    also drop it from the session — the frontend logs the user out on 401 and
    the auth status endpoint stays consistent.
    """
    if exc.status_code == 401:
        request.session.pop("livestorm_token", None)
        return HTTPException(status_code=401, detail=SESSION_EXPIRED_DETAIL)
    return HTTPException(status_code=502, detail=str(exc))
