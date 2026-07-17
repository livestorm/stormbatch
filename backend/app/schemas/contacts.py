from pydantic import BaseModel, Field


class SessionContactsRequest(BaseModel):
    session_id: str


class ContactPerson(BaseModel):
    id: str
    fields: dict[str, str]


class SessionContactsResponse(BaseModel):
    session_id: str
    headers: list[str]
    people: list[ContactPerson]
    total: int


class ContactFieldUpdate(BaseModel):
    id: str
    value: str = ""


class ContactUpdateRequest(BaseModel):
    session_id: str
    person_id: str
    # Used to verify the update by re-reading the contact when Livestorm's
    # PATCH response times out. Never sent as an update field.
    email: str = ""
    fields: list[ContactFieldUpdate] = Field(default_factory=list)


class ContactUpdateResponse(BaseModel):
    session_id: str
    person_id: str
    status: str
    updated_fields: dict[str, str]


class ContactDeleteRequest(BaseModel):
    session_id: str
    person_id: str


class ContactDeleteResponse(BaseModel):
    session_id: str
    person_id: str
    status: str
