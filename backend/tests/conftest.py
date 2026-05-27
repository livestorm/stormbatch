import base64
import json
import os

import pytest
from dotenv import load_dotenv
from itsdangerous import TimestampSigner
from starlette.testclient import TestClient

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

# ── Credentials ────────────────────────────────────────────────────────────────

LS_KEY = os.getenv("LS_KEY", "")
SOURCE_SESSION_ID = "51a6cda2-25cd-4657-b6dc-8519275f90e9"
TARGET_SESSION_ID = "de121ecd-9d38-43aa-a9e1-0d4216fd0bfc"
SESSION_SECRET = os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production")

needs_credentials = pytest.mark.skipif(
    not LS_KEY,
    reason="LS_KEY not in .env — skipping Livestorm API tests",
)

# ── Session cookie helper ──────────────────────────────────────────────────────

def make_session_cookie(data: dict) -> str:
    """
    Produce a signed Starlette session cookie.

    Matches Starlette's SessionMiddleware encoding exactly:
      json(data) → utf-8 bytes → base64 bytes → TimestampSigner.sign → str
    """
    signer = TimestampSigner(SESSION_SECRET)
    raw: bytes = base64.b64encode(json.dumps(data).encode("utf-8"))
    return signer.sign(raw).decode("utf-8")


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def session_cookie() -> str:
    """
    A signed session cookie that identifies as authenticated with LS_KEY.

    NOTE: The routes use use_bearer=True (expecting an OAuth token). Pairing
    this cookie with the use_api_key_auth fixture patches LivestormClient to
    send the key without a Bearer prefix, which is what Livestorm expects for
    private API keys.
    """
    return make_session_cookie({"livestorm_token": LS_KEY})


@pytest.fixture
def client(session_cookie):
    """
    Unauthenticated TestClient — 401 tests use this without a cookie.
    Authenticated tests pass cookies={"session": session_cookie} per-request
    until Starlette stabilises its client-level cookie API.
    """
    from app.main import app
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def use_api_key_auth(monkeypatch):
    """
    Force LivestormClient to send the key without a Bearer prefix.

    The FastAPI routes call LivestormClient(token=..., use_bearer=True) which
    would send "Authorization: Bearer LS_KEY" — but Livestorm's private API
    expects "Authorization: LS_KEY".  This fixture fixes that for any test
    that exercises the real Livestorm API through the routes.
    """
    from app.services import livestorm_client as lc_module

    original_init = lc_module.LivestormClient.__init__

    def patched_init(self, token, use_bearer=True):
        original_init(self, token=token, use_bearer=False)

    monkeypatch.setattr(lc_module.LivestormClient, "__init__", patched_init)
