"""
Tests for spreadsheet preview parsing and the JSON bulk-job endpoint.

No network: the Livestorm client is replaced by a fake that records calls.

Run (from the backend/ directory):
    python -m pytest tests/test_bulk_jobs.py -v
"""

from io import BytesIO

import pytest
from openpyxl import Workbook

from app.schemas.bulk_jobs import BulkRegistrant
from app.services.bulk_job_service import BULK_JOB_TASK_LIMIT, build_bulk_tasks
from app.services.livestorm_client import LivestormAPIError

SESSION_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _registrant(**fields):
    return {"fields": [{"id": key, "value": value} for key, value in fields.items()]}


def _preview(client, filename, content):
    return client.post("/api/preview", files={"file": (filename, content)})


# ══════════════════════════════════════════════════════════════════════════════
# Preview parsing
# ══════════════════════════════════════════════════════════════════════════════


def test_preview_keeps_cells_as_text(client):
    csv = (
        "email,zip,last_name,phone,score\n"
        "a@example.com,01234,NA,0612345678,12\n"
        "b@example.com,,Null,,\n"
    )

    response = _preview(client, "people.csv", csv.encode())

    assert response.status_code == 200, response.text
    body = response.json()
    first, second = body["rows"]
    assert first == {
        "email": "a@example.com",
        "zip": "01234",
        "last_name": "NA",
        "phone": "0612345678",
        "score": "12",
    }
    assert second["last_name"] == "Null"
    assert second["zip"] == ""
    assert body["row_count"] == 2


def test_preview_returns_every_row(client):
    csv = "email\n" + "".join(f"person{i}@example.com\n" for i in range(120))

    body = _preview(client, "people.csv", csv.encode()).json()

    assert body["row_count"] == 120
    assert len(body["rows"]) == 120
    assert body["rows"][-1]["email"] == "person119@example.com"


def test_preview_xlsx_numbers_with_gaps_have_no_float_suffix(client):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Email", "Employees"])
    sheet.append(["a@example.com", 1234])
    sheet.append(["b@example.com", None])
    buffer = BytesIO()
    workbook.save(buffer)

    body = _preview(client, "people.xlsx", buffer.getvalue()).json()

    assert body["rows"][0]["Employees"] == "1234"
    assert body["rows"][1]["Employees"] == ""
    assert body["suggestions"]["Email"] == "email"


def test_preview_drops_empty_rows_and_columns(client):
    csv = "email,,first_name\na@example.com,,Ann\n,,\nb@example.com,,Bob\n"

    body = _preview(client, "people.csv", csv.encode()).json()

    assert body["headers"] == ["email", "first_name"]
    assert [row["email"] for row in body["rows"]] == ["a@example.com", "b@example.com"]


# ══════════════════════════════════════════════════════════════════════════════
# Chunk validation
# ══════════════════════════════════════════════════════════════════════════════


def test_build_bulk_tasks_trims_and_drops_blank_values():
    registrants = [BulkRegistrant(**_registrant(email=" a@example.com ", first_name="", company="Acme"))]

    assert build_bulk_tasks(registrants) == [
        {"fields": [{"id": "email", "value": "a@example.com"}, {"id": "company", "value": "Acme"}]}
    ]


def test_build_bulk_tasks_rejects_oversized_chunk():
    registrants = [
        BulkRegistrant(**_registrant(email=f"p{i}@example.com")) for i in range(BULK_JOB_TASK_LIMIT + 1)
    ]

    with pytest.raises(ValueError, match="at most 50"):
        build_bulk_tasks(registrants)


def test_build_bulk_tasks_rejects_missing_email_and_repeated_field():
    with pytest.raises(ValueError, match="Registrant 2 has no email"):
        build_bulk_tasks([
            BulkRegistrant(**_registrant(email="a@example.com")),
            BulkRegistrant(**_registrant(first_name="Bob")),
        ])

    repeated = BulkRegistrant(fields=[{"id": "email", "value": "a@x.co"}, {"id": "email", "value": "b@x.co"}])
    with pytest.raises(ValueError, match="more than once"):
        build_bulk_tasks([repeated])


# ══════════════════════════════════════════════════════════════════════════════
# Route — fake Livestorm client
# ══════════════════════════════════════════════════════════════════════════════


class FakeLivestormClient:
    created: list = []
    error: LivestormAPIError = None

    def __init__(self, token, use_bearer=True):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def create_bulk_job(self, session_id, tasks):
        if FakeLivestormClient.error:
            raise FakeLivestormClient.error
        FakeLivestormClient.created.append((session_id, tasks))
        return {"job_id": "job-1", "status": "pending"}


@pytest.fixture
def fake_livestorm(monkeypatch):
    from app.routes import bulk_jobs as bulk_jobs_routes

    FakeLivestormClient.created = []
    FakeLivestormClient.error = None
    monkeypatch.setattr(bulk_jobs_routes, "LivestormClient", FakeLivestormClient)
    return FakeLivestormClient


def test_bulk_job_route_creates_one_job_per_chunk(client, session_cookie, fake_livestorm):
    response = client.post(
        "/api/bulk-jobs",
        json={
            "session_id": SESSION_ID,
            "registrants": [_registrant(email="a@example.com", first_name="Ann")],
        },
        cookies={"session": session_cookie},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"session_id": SESSION_ID, "job_id": "job-1", "status": "pending"}
    [(session_id, tasks)] = fake_livestorm.created
    assert session_id == SESSION_ID
    assert tasks == [{"fields": [{"id": "email", "value": "a@example.com"}, {"id": "first_name", "value": "Ann"}]}]


def test_bulk_job_route_rejects_bad_chunk_without_calling_livestorm(client, session_cookie, fake_livestorm):
    response = client.post(
        "/api/bulk-jobs",
        json={"session_id": SESSION_ID, "registrants": [_registrant(first_name="Ann")]},
        cookies={"session": session_cookie},
    )

    assert response.status_code == 400
    assert fake_livestorm.created == []


def test_bulk_job_route_maps_expired_token_to_401(client, session_cookie, fake_livestorm):
    fake_livestorm.error = LivestormAPIError("expired", status_code=401)

    response = client.post(
        "/api/bulk-jobs",
        json={"session_id": SESSION_ID, "registrants": [_registrant(email="a@example.com")]},
        cookies={"session": session_cookie},
    )

    assert response.status_code == 401


def test_removed_endpoints_are_gone(client, session_cookie):
    for path in ("/api/register", "/api/transfer", "/api/session-fields"):
        assert client.post(path, json={}, cookies={"session": session_cookie}).status_code in (404, 405)
    assert client.get("/api/auth/me", cookies={"session": session_cookie}).status_code in (404, 405)


def test_preview_reads_single_column_and_semicolon_csv(client):
    single = _preview(client, "list.csv", b"Email\nann@example.com\nbob@test.org\n").json()
    assert single["headers"] == ["Email"]
    assert [row["Email"] for row in single["rows"]] == ["ann@example.com", "bob@test.org"]

    semicolon = _preview(client, "list.csv", b"email;first_name\nann@example.com;Ann\n").json()
    assert semicolon["rows"] == [{"email": "ann@example.com", "first_name": "Ann"}]


def test_preview_reads_windows_1252_csv(client):
    content = "email,last_name\nann@example.com,Lefèvre\n".encode("cp1252")

    body = _preview(client, "list.csv", content).json()

    assert body["rows"][0]["last_name"] == "Lefèvre"
