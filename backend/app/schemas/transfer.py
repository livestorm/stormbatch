from typing import Any

from pydantic import BaseModel, Field


class SessionPeopleRequest(BaseModel):
    session_id: str


class SessionPeopleResponse(BaseModel):
    session_id: str
    headers: list[str]
    rows: list[dict[str, str]]
    total: int


class TransferRequest(BaseModel):
    target_session_ids: list[str]
    rows: list[dict[str, str]]
    included_fields: list[str]


class TransferJob(BaseModel):
    session_id: str
    job_id: str
    status: str
    chunk_index: int = 1
    chunk_count: int = 1
    row_start: int = 2
    row_count: int = 0
    row_results: list[dict[str, Any]] = Field(default_factory=list)


class TransferResponse(BaseModel):
    jobs: list[TransferJob]
    row_count: int
    row_results: list[dict[str, Any]]
