import os
import secrets
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

router = APIRouter(tags=["auth"])

_CLIENT_ID = os.environ.get("LIVESTORM_OAUTH_CLIENT_ID", "")
_CLIENT_SECRET = os.environ.get("LIVESTORM_OAUTH_CLIENT_SECRET", "")
_REDIRECT_URI = os.environ.get("LIVESTORM_OAUTH_REDIRECT_URI", "")
_SCOPES = os.environ.get("LIVESTORM_OAUTH_SCOPES", "events:read events:write")

_AUTHORIZE_URL = "https://app.livestorm.co/oauth/authorize"
_TOKEN_URL = "https://app.livestorm.co/oauth/token"


@router.get("/auth/livestorm/login")
async def login(request: Request) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    # Use quote (not quote_plus) so spaces encode as %20, not +, per OAuth spec.
    params = urlencode(
        {
            "client_id": _CLIENT_ID,
            "redirect_uri": _REDIRECT_URI,
            "response_type": "code",
            "scope": _SCOPES,
            "state": state,
        },
        quote_via=quote,
    )
    return RedirectResponse(f"{_AUTHORIZE_URL}?{params}")


@router.get("/auth/livestorm/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = "") -> RedirectResponse:
    if error:
        return RedirectResponse(f"/?auth_error={error}")

    expected_state = request.session.pop("oauth_state", None)
    if not expected_state or expected_state != state:
        return RedirectResponse("/?auth_error=invalid_state")

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            _TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
                "redirect_uri": _REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code >= 400:
        return RedirectResponse("/?auth_error=token_exchange_failed")

    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        return RedirectResponse("/?auth_error=no_access_token")

    request.session["livestorm_token"] = access_token
    return RedirectResponse("/")


@router.get("/auth/status")
async def auth_status(request: Request) -> dict:
    token = request.session.get("livestorm_token")
    return {"authenticated": bool(token)}


@router.get("/auth/me")
async def current_user_profile(request: Request) -> JSONResponse:
    import logging
    from app.services.livestorm_client import LivestormClient

    logger = logging.getLogger(__name__)
    token = request.session.get("livestorm_token")
    if not token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    try:
        async with LivestormClient(token=token, use_bearer=True) as client:
            resp = await client._request("GET", "/v1/me")
            logger.info("GET /v1/me → %s", resp.status_code)
            if resp.status_code == 200:
                body = resp.json()
                attrs = body.get("data", {}).get("attributes", {})
                # Livestorm may return camelCase or snake_case depending on token type
                return JSONResponse({
                    "email": attrs.get("email") or "",
                    "first_name": attrs.get("first_name") or attrs.get("firstName") or "",
                    "last_name": attrs.get("last_name") or attrs.get("lastName") or "",
                    "avatar_link": attrs.get("avatar_link") or attrs.get("avatarLink") or None,
                })
            else:
                logger.warning("GET /v1/me failed: %s %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.exception("Error fetching Livestorm user profile: %s", exc)

    return JSONResponse({"email": "", "first_name": "", "last_name": "", "avatar_link": None})


@router.post("/auth/logout")
async def logout(request: Request) -> JSONResponse:
    request.session.pop("livestorm_token", None)
    return JSONResponse({"status": "logged_out"})
