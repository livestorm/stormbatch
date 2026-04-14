from typing import Any, Optional

from pydantic import BaseModel, Field


class JobStatusRequest(BaseModel):
    session_id: str
    job_id: str


class RetryRegistrant(BaseModel):
    row_number: Optional[int] = None
    email: str
    fields: list[dict[str, Any]]


class RetryFailedRowsRequest(BaseModel):
    session_id: str
    registrants: list[RetryRegistrant]


class RetryFailedRowsResponse(BaseModel):
    session_id: str
    results: list[dict[str, Any]]


class JobStatusResponse(BaseModel):
    session_id: str
    job_id: str
    status: str
    tasks: list[Any] = Field(default_factory=list)
    tasks_error: Optional[str] = None
    raw: dict[str, Any] = Field(default_factory=dict)
