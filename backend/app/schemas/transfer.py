from pydantic import BaseModel


class SessionPeopleRequest(BaseModel):
    session_id: str


class SessionPeopleResponse(BaseModel):
    session_id: str
    headers: list[str]
    rows: list[dict[str, str]]
    total: int
