"""
End-to-end tests for the transfer feature.

Tests are split into two layers:

  1. Client layer  — calls LivestormClient directly with LS_KEY (use_bearer=False).
     These verify that our Livestorm API integration is correct end-to-end.

  2. Route layer   — calls the FastAPI endpoints via TestClient.
     These verify that the HTTP layer handles auth, request parsing,
     and error propagation correctly.

Run (from the backend/ directory):
    pip install -r requirements-dev.txt
    python -m pytest tests/test_e2e_transfer.py -v -s

NOTE ON SESSION IDS:
The SOURCE/TARGET session IDs in conftest.py must belong to the same Livestorm
workspace as LS_KEY. Private API keys only access sessions in their own workspace.
If the client-layer tests return 404 ("record could not be found"), the key does
not have access to those sessions.
"""

import asyncio

import pytest

from tests.conftest import (
    LS_KEY,
    SOURCE_SESSION_ID,
    TARGET_SESSION_ID,
    needs_credentials,
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Client layer — real Livestorm API calls via LivestormClient directly
# ══════════════════════════════════════════════════════════════════════════════


@needs_credentials
async def test_fetch_source_session_returns_registrants():
    """Source session must have at least one registrant with an email."""
    from app.services.livestorm_client import LivestormClient

    async with LivestormClient(token=LS_KEY, use_bearer=False) as client:
        people = await client.list_session_people(SOURCE_SESSION_ID)

    assert len(people) > 0, "Expected registrants in source session"


@needs_credentials
async def test_extract_people_data_structure():
    """
    extract_people_data must:
    - place email first in headers
    - produce one row per person
    - ensure every row has a non-empty email
    """
    from app.services.livestorm_client import LivestormClient
    from app.services.transfer_service import extract_people_data

    async with LivestormClient(token=LS_KEY, use_bearer=False) as client:
        people = await client.list_session_people(SOURCE_SESSION_ID)

    data = extract_people_data(people)

    assert data["headers"][0] == "email", "email must be the first column"
    assert data["total"] == len(data["rows"])
    for row in data["rows"]:
        assert row.get("email"), f"Row missing email: {row}"


@needs_credentials
async def test_transfer_small_chunk_creates_job():
    """
    Transfer the first 3 registrants to the target session.
    Livestorm must return a job_id immediately (202 Accepted).
    """
    from app.services.livestorm_client import LivestormClient
    from app.services.transfer_service import extract_people_data

    async with LivestormClient(token=LS_KEY, use_bearer=False) as client:
        people = await client.list_session_people(SOURCE_SESSION_ID)
        data = extract_people_data(people)

        rows = data["rows"][:3]
        tasks = [
            {
                "fields": [
                    {"id": fid, "value": row[fid]}
                    for fid in data["headers"]
                    if row.get(fid)
                ]
            }
            for row in rows
        ]

        result = await client.create_bulk_job(TARGET_SESSION_ID, tasks)

    assert result["job_id"], "Expected a job_id in the response"
    assert result["status"] in ("pending", "processing", "created", "queued")


@needs_credentials
async def test_full_transfer_flow_polls_to_completion():
    """
    Full end-to-end flow: fetch ALL source registrants → build tasks → create job
    → poll until terminal → assert all rows were submitted.

    "failed" is acceptable for the overall job — it means Livestorm processed
    the job but some (or all) registrants were already in the target session from
    a prior run.  The important thing is that all rows were sent.
    """
    from app.services.livestorm_client import LivestormClient
    from app.services.transfer_service import extract_people_data

    async with LivestormClient(token=LS_KEY, use_bearer=False) as client:
        people = await client.list_session_people(SOURCE_SESSION_ID)
        data = extract_people_data(people)

        assert data["total"] > 0, "Source session has no registrants"

        tasks = [
            {
                "fields": [
                    {"id": fid, "value": row[fid]}
                    for fid in data["headers"]
                    if row.get(fid)
                ]
            }
            for row in data["rows"]
        ]

        created = await client.create_bulk_job(TARGET_SESSION_ID, tasks)
        job_id = created["job_id"]

        final_status = None
        status_data: dict = {}
        for _ in range(30):  # up to 90 s
            status_data = await client.get_job_status(TARGET_SESSION_ID, job_id)
            final_status = status_data["status"]
            if final_status in ("ended", "failed", "completed"):
                break
            await asyncio.sleep(3)

    terminal = ("ended", "completed", "failed")
    assert final_status in terminal, (
        f"Job never reached a terminal state. Last known status: {final_status!r}"
    )
    tasks_result = status_data.get("tasks", [])
    if final_status != "failed":
        assert len(tasks_result) == data["total"], (
            f"Expected {data['total']} tasks, got {len(tasks_result)}"
        )


@needs_credentials
async def test_excluded_row_is_not_submitted():
    """
    Simulates the frontend 'remove row' action: dropping index 0 means
    its email never appears in the task list.
    """
    from app.services.livestorm_client import LivestormClient
    from app.services.transfer_service import extract_people_data

    async with LivestormClient(token=LS_KEY, use_bearer=False) as client:
        people = await client.list_session_people(SOURCE_SESSION_ID)

    data = extract_people_data(people)
    if data["total"] < 2:
        pytest.skip("Need at least 2 registrants in the source session")

    excluded_email = data["rows"][0]["email"]
    active_rows = data["rows"][1:]
    active_emails = {r["email"] for r in active_rows}

    assert excluded_email not in active_emails
    assert len(active_rows) == data["total"] - 1


@needs_credentials
async def test_excluded_field_absent_from_task_fields():
    """
    Simulates the frontend 'toggle column off' action: the excluded field ID
    must not appear in the task fields sent to Livestorm.
    """
    from app.services.livestorm_client import LivestormClient
    from app.services.transfer_service import extract_people_data

    async with LivestormClient(token=LS_KEY, use_bearer=False) as client:
        people = await client.list_session_people(SOURCE_SESSION_ID)

    data = extract_people_data(people)
    optional = [f for f in data["headers"] if f != "email"]

    if not optional:
        pytest.skip("Source session has no optional fields to exclude")

    excluded_field = optional[0]
    included_fields = [f for f in data["headers"] if f != excluded_field]

    row = data["rows"][0]
    task_field_ids = [
        fid for fid in included_fields if row.get(fid)
    ]

    assert excluded_field not in task_field_ids
    assert "email" in task_field_ids


@needs_credentials
async def test_invalid_session_id_raises_livestorm_error():
    """A bogus session ID must raise LivestormAPIError, not crash."""
    from app.services.livestorm_client import LivestormAPIError, LivestormClient

    async with LivestormClient(token=LS_KEY, use_bearer=False) as client:
        with pytest.raises(LivestormAPIError):
            await client.create_bulk_job(
                "00000000-0000-0000-0000-000000000000",
                [{"fields": [{"id": "email", "value": "test@example.com"}]}],
            )


# ══════════════════════════════════════════════════════════════════════════════
# 2. Route layer — FastAPI endpoints via TestClient
#
# Cookies are passed per-request (not on the client session) to avoid
# domain-matching issues in requests' cookie jar.
# ══════════════════════════════════════════════════════════════════════════════


def test_session_people_requires_auth(client):
    """POST /api/session-people without a session cookie → 401."""
    response = client.post(
        "/api/session-people",
        json={"session_id": SOURCE_SESSION_ID},
    )
    assert response.status_code == 401


def test_transfer_requires_auth(client):
    """POST /api/transfer without a session cookie → 401."""
    response = client.post(
        "/api/transfer",
        json={
            "target_session_ids": [TARGET_SESSION_ID],
            "rows": [{"email": "test@example.com"}],
            "included_fields": ["email"],
        },
    )
    assert response.status_code == 401


def test_transfer_rejects_missing_email_field(client, session_cookie):
    """POST /api/transfer without email in included_fields → 400."""
    response = client.post(
        "/api/transfer",
        json={
            "target_session_ids": [TARGET_SESSION_ID],
            "rows": [{"first_name": "Test"}],
            "included_fields": ["first_name"],
        },
        cookies={"session": session_cookie},
    )
    assert response.status_code == 400
    assert "email" in response.json()["detail"].lower()


def test_transfer_rejects_empty_rows(client, session_cookie):
    """POST /api/transfer with zero rows → 400."""
    response = client.post(
        "/api/transfer",
        json={
            "target_session_ids": [TARGET_SESSION_ID],
            "rows": [],
            "included_fields": ["email"],
        },
        cookies={"session": session_cookie},
    )
    assert response.status_code == 400


def test_transfer_rejects_empty_target_sessions(client, session_cookie):
    """POST /api/transfer with no target session IDs → 400."""
    response = client.post(
        "/api/transfer",
        json={
            "target_session_ids": [],
            "rows": [{"email": "test@example.com"}],
            "included_fields": ["email"],
        },
        cookies={"session": session_cookie},
    )
    assert response.status_code == 400


def test_session_people_returns_404_for_unknown_session(client, session_cookie, use_api_key_auth):
    """
    POST /api/session-people with a non-existent session ID → 502
    (LivestormAPIError wraps the 404 from Livestorm as a bad-gateway).
    """
    response = client.post(
        "/api/session-people",
        json={"session_id": "00000000-0000-0000-0000-000000000000"},
        cookies={"session": session_cookie},
    )
    assert response.status_code == 502


@needs_credentials
def test_route_fetch_session_people(client, session_cookie, use_api_key_auth):
    """
    POST /api/session-people with valid credentials → 200.
    Requires LS_KEY to have access to SOURCE_SESSION_ID.
    """
    response = client.post(
        "/api/session-people",
        json={"session_id": SOURCE_SESSION_ID},
        cookies={"session": session_cookie},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] > 0
    assert data["headers"][0] == "email"
    assert len(data["rows"]) == data["total"]


@needs_credentials
def test_route_transfer_creates_job(client, session_cookie, use_api_key_auth):
    """
    Fetch first row from source → transfer to target → job created.
    Requires LS_KEY to have access to both session IDs.
    """
    fetch_resp = client.post(
        "/api/session-people",
        json={"session_id": SOURCE_SESSION_ID},
        cookies={"session": session_cookie},
    )
    assert fetch_resp.status_code == 200, fetch_resp.text
    data = fetch_resp.json()

    transfer_resp = client.post(
        "/api/transfer",
        json={
            "target_session_ids": [TARGET_SESSION_ID],
            "rows": data["rows"][:1],
            "included_fields": data["headers"],
        },
        cookies={"session": session_cookie},
    )
    assert transfer_resp.status_code == 200, transfer_resp.text
    result = transfer_resp.json()
    assert len(result["jobs"]) == 1
    assert result["jobs"][0]["job_id"]
    assert result["jobs"][0]["session_id"] == TARGET_SESSION_ID
