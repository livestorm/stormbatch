from pydantic import BaseModel, Field


class BulkField(BaseModel):
    id: str
    value: str = ""


class BulkRegistrant(BaseModel):
    fields: list[BulkField] = Field(default_factory=list)


class BulkJobRequest(BaseModel):
    session_id: str
    # At most BULK_JOB_TASK_LIMIT registrants; the browser sends one chunk per request.
    registrants: list[BulkRegistrant] = Field(default_factory=list)


class BulkJobResponse(BaseModel):
    session_id: str
    job_id: str
    status: str
