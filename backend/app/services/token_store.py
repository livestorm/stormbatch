"""The Livestorm OAuth token kept in the session cookie.

Starlette signs the session cookie but does not encrypt it: its content is
base64 JSON anyone holding the cookie can read. The token is therefore
encrypted before it is stored there.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import SESSION_SECRET

_SESSION_KEY = "livestorm_token"
# Separate key from the cookie signature, derived from the same secret.
_fernet = Fernet(
    base64.urlsafe_b64encode(hashlib.sha256(b"stormbatch-livestorm-token:" + SESSION_SECRET.encode()).digest())
)


def encrypt_token(token: str) -> str:
    return _fernet.encrypt(token.encode()).decode()


def store_token(session: dict, token: str) -> None:
    session[_SESSION_KEY] = encrypt_token(token)


def read_token(session: dict) -> Optional[str]:
    value = session.get(_SESSION_KEY)
    if not value:
        return None
    try:
        return _fernet.decrypt(str(value).encode()).decode() or None
    except InvalidToken:
        # Plain tokens from before encryption, or a rotated secret: log in again.
        return None


def clear_token(session: dict) -> None:
    session.pop(_SESSION_KEY, None)
