"""
Security hardening: encrypted token in the session cookie, production config,
upload limits and request caps. No network: Livestorm calls are faked.

Run (from the backend/ directory):
    python -m pytest tests/test_hardening.py -v
"""

import base64
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx

from app.services import excel_parser
from tests.conftest import make_session_cookie

BACKEND_DIR = Path(__file__).resolve().parents[1]
OAUTH_TOKEN = "oauth-token-123"


class FakeTokenExchange:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def post(self, url, data, headers):
        return httpx.Response(200, json={"access_token": OAUTH_TOKEN})


def _cookie_payload(cookie: str) -> str:
    # Starlette cookies are "<base64 JSON>.<timestamp>.<signature>".
    return base64.b64decode(cookie.split(".")[0]).decode()


# ══════════════════════════════════════════════════════════════════════════════
# Token storage
# ══════════════════════════════════════════════════════════════════════════════


def test_oauth_callback_stores_the_token_encrypted(client, monkeypatch):
    from app.routes import auth as auth_routes

    monkeypatch.setattr(auth_routes, "httpx", SimpleNamespace(AsyncClient=FakeTokenExchange))

    response = client.get(
        "/api/auth/livestorm/callback",
        params={"code": "code-1", "state": "state-1"},
        cookies={"session": make_session_cookie({"oauth_state": "state-1"})},
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    set_cookie = response.headers["set-cookie"]
    cookie = response.cookies["session"]
    assert OAUTH_TOKEN not in _cookie_payload(cookie)
    # Browser-session cookie: no Max-Age or Expires.
    assert "max-age" not in set_cookie.lower() and "expires" not in set_cookie.lower()
    status = client.get("/api/auth/status", cookies={"session": cookie})
    assert status.json() == {"authenticated": True}


def test_plain_token_cookie_from_before_encryption_is_logged_out(client):
    legacy = make_session_cookie({"livestorm_token": "plain-oauth-token"})

    assert client.get("/api/auth/status", cookies={"session": legacy}).json() == {"authenticated": False}
    assert client.get("/api/sessions", cookies={"session": legacy}).status_code == 401


def test_logout_drops_the_token(client, session_cookie):
    response = client.post("/api/auth/logout", cookies={"session": session_cookie})

    assert response.status_code == 200
    cleared = response.cookies.get("session", "")
    assert client.get("/api/auth/status", cookies={"session": cleared}).json() == {"authenticated": False}


# ══════════════════════════════════════════════════════════════════════════════
# Upload limits and caps
# ══════════════════════════════════════════════════════════════════════════════


def _preview(client, cookie, content):
    cookies = {"session": cookie} if cookie else None
    return client.post("/api/preview", files={"file": ("people.csv", content)}, cookies=cookies)


def test_preview_requires_login(client):
    assert _preview(client, None, b"email\na@example.com\n").status_code == 401


def test_preview_rejects_large_body_before_reading_it(client, session_cookie, monkeypatch):
    monkeypatch.setattr(excel_parser, "MAX_UPLOAD_BYTES", 10)
    content = b"email\n" + b"a@example.com\n" * 6000  # ~84 KB, over the 64 KB envelope allowance

    response = _preview(client, session_cookie, content)

    assert response.status_code == 413
    assert "larger than" in response.json()["detail"]


def test_preview_rejects_large_file_without_trusting_content_length(client, session_cookie, monkeypatch):
    monkeypatch.setattr(excel_parser, "MAX_UPLOAD_BYTES", 10)

    response = _preview(client, session_cookie, b"email\na@example.com\nb@example.com\n")

    assert response.status_code == 400
    assert "larger than" in response.json()["detail"]


def test_preview_caps_rows(client, session_cookie, monkeypatch):
    monkeypatch.setattr(excel_parser, "MAX_ROWS", 3)
    content = b"email\n" + b"".join(f"p{i}@example.com\n".encode() for i in range(5))

    response = _preview(client, session_cookie, content)

    assert response.status_code == 400
    assert "5 rows" in response.json()["detail"]


def test_retry_failed_is_capped_to_one_batch(client, session_cookie):
    registrants = [{"email": f"p{i}@example.com", "fields": []} for i in range(51)]

    response = client.post(
        "/api/retry-failed",
        json={"session_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "registrants": registrants},
        cookies={"session": session_cookie},
    )

    assert response.status_code == 400
    assert "at most 50" in response.json()["detail"]


# ══════════════════════════════════════════════════════════════════════════════
# Production configuration (separate processes: config is read at import)
# ══════════════════════════════════════════════════════════════════════════════


def _run_in_production(code, secret):
    env = {k: v for k, v in os.environ.items() if k not in ("SESSION_SECRET_KEY", "RENDER", "STORMBATCH_ENV")}
    env["RENDER"] = "true"
    if secret is not None:
        env["SESSION_SECRET_KEY"] = secret
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True)


def test_production_refuses_missing_or_default_secret():
    for secret in (None, "", "dev-secret-change-in-production"):
        result = _run_in_production("import app.main", secret)
        assert result.returncode != 0, secret
        assert "SESSION_SECRET_KEY" in result.stderr


def test_production_uses_secure_browser_session_cookies_without_cors():
    code = (
        "from app.main import app\n"
        "from starlette.middleware.sessions import SessionMiddleware\n"
        "from fastapi.middleware.cors import CORSMiddleware\n"
        "session = next(m for m in app.user_middleware if m.cls is SessionMiddleware)\n"
        "print(session.kwargs['https_only'], session.kwargs['max_age'],"
        " any(m.cls is CORSMiddleware for m in app.user_middleware))\n"
    )

    result = _run_in_production(code, "a-long-random-production-secret")

    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["True", "None", "False"]
