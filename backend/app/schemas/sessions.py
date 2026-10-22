from typing import Optional

from pydantic import BaseModel, Field


class SessionField(BaseModel):
    id: str
    type: str = "text"
    required: bool = False


class SessionSummary(BaseModel):
    id: str
    # Event title; sessions rarely have their own name.
    title: str
    name: str = ""
    status: str = ""
    estimated_started_at: Optional[int] = None
    timezone: str = ""
    registrants_count: int = 0
    event_id: str = ""


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]
    next_page: Optional[int] = None


class SessionDetailResponse(SessionSummary):
    # Registration form fields of the session's event. Email is implicit and
    # not always listed, so clients must treat it as always valid.
    fields: list[SessionField] = Field(default_factory=list)


class RegisteredEmailsResponse(BaseModel):
    session_id: str
    # Lowercased, so callers can compare case-insensitively.
    emails: list[str]
    # False when the session was too large to list; emails is then empty.
    checked: bool = True
    registrants_count: Optional[int] = None
