"""
End-to-end tests for the contact update feature.

Layout mirrors test_e2e_transfer.py:

  1. Client layer  — calls LivestormClient directly with LS_KEY (use_bearer=False).
  2. Route layer   — calls the FastAPI endpoints via TestClient.

Run (from the backend/ directory):
    python -m pytest tests/test_e2e_contacts.py -v -s

NOTE: The PATCH test mutates a registrant's first_name in CONTACTS_SESSION_ID
and restores the original value afterwards. It skips (rather than fails) when
the API key lacks write permission, since read-only keys return an empty 403.
"""

import pytest

from tests.conftest import LS_KEY, make_session_cookie, needs_credentials

CONTACTS_SESSION_ID = "64fe6880-1555-4a17-b6ed-3d2ac51bcede"


# ══════════════════════════════════════════════════════════════════════════════
# 1. Client layer — real Livestorm API calls via LivestormClient directly
# ══════════════════════════════════════════════════════════════════════════════


@needs_credentials
async def test_extract_contacts_keeps_person_ids():
    """Every extracted contact must carry the Livestorm person ID and an email."""
    from app.services.contacts_service import extract_contacts
    from app.services.livestorm_client import LivestormClient

    async with LivestormClient(token=LS_KEY, use_bearer=False) as client:
        people = await client.list_session_people(CONTACTS_SESSION_ID)

    assert people, "Expected registrants in the contacts test session"
    data = extract_contacts(people)

    assert data["headers"][0] == "email", "email must be the first column"
    assert data["total"] == len(data["people"])
    for contact in data["people"]:
        assert contact["id"], f"Contact missing person ID: {contact}"
        assert contact["fields"].get("email"), f"Contact missing email: {contact}"


@needs_credentials
async def test_update_contact_roundtrip():
    """
    PATCH a participant's first_name, verify Livestorm persisted it,
    then restore the original value.

    Livestorm's PATCH endpoint applies the write but often never completes the
    response — update_session_person handles that by re-reading the contact,
    which is exactly the behavior this test exercises.
    """
    from app.services.contacts_service import extract_contacts
    from app.services.livestorm_client import LivestormAPIError, LivestormClient

    async with LivestormClient(token=LS_KEY, use_bearer=False) as client:
        people = await client.list_session_people(CONTACTS_SESSION_ID)
        data = extract_contacts(people)
        target = next(
            (c for c in data["people"] if "+" in c["fields"].get("email", "")),
            None,
        )
        assert target, "Expected a fake (+aliased) participant to test updates on"

        email = target["fields"]["email"]
        original = target["fields"].get("first_name", "")
        updated = f"{original}-edited" if original else "Edited"

        try:
            result = await client.update_session_person(
                session_id=CONTACTS_SESSION_ID,
                person_id=target["id"],
                fields=[{"id": "first_name", "value": updated}],
                verify_email=email,
            )
        except LivestormAPIError as exc:
            if "403" in str(exc):
                pytest.skip(f"API key lacks write permission: {exc}")
            raise

        assert result["status"] == "updated"

        try:
            refreshed = await client.list_session_people(CONTACTS_SESSION_ID, email=email)
            refreshed_fields = extract_contacts(refreshed)["people"][0]["fields"]
            assert refreshed_fields.get("first_name") == updated
        finally:
            restore = await client.update_session_person(
                session_id=CONTACTS_SESSION_ID,
                person_id=target["id"],
                fields=[{"id": "first_name", "value": original}],
                verify_email=email,
            )
            assert restore["status"] == "updated"


@needs_credentials
async def test_delete_contact_roundtrip():
    """
    Register a throwaway participant, delete them via the DELETE endpoint,
    then verify they are gone from the session.
    """
    from app.services.livestorm_client import LivestormAPIError, LivestormClient

    throwaway_email = "fares.harrazi+deleteroundtrip@livestorm.co"

    async with LivestormClient(token=LS_KEY, use_bearer=False) as client:
        await client.register_person(
            session_id=CONTACTS_SESSION_ID,
            fields=[
                {"id": "email", "value": throwaway_email},
                {"id": "first_name", "value": "Delete"},
                {"id": "last_name", "value": "Roundtrip"},
            ],
        )
        created = await client.list_session_people(CONTACTS_SESSION_ID, email=throwaway_email)
        assert created, "Throwaway participant was not registered"
        person_id = created[0]["id"]

        try:
            result = await client.delete_session_person(
                session_id=CONTACTS_SESSION_ID, person_id=person_id
            )
        except LivestormAPIError as exc:
            if "403" in str(exc):
                pytest.skip(f"API key lacks delete permission: {exc}")
            raise

        assert result["status"] == "deleted"
        remaining = await client.list_session_people(CONTACTS_SESSION_ID, email=throwaway_email)
        assert not remaining, "Participant still present after deletion"


# ══════════════════════════════════════════════════════════════════════════════
# 2. Route layer — FastAPI endpoints via TestClient
# ══════════════════════════════════════════════════════════════════════════════


def test_session_contacts_requires_auth(client):
    response = client.post("/api/session-contacts", json={"session_id": CONTACTS_SESSION_ID})
    assert response.status_code == 401


def test_update_contact_requires_auth(client):
    response = client.post(
        "/api/update-contact",
        json={"session_id": CONTACTS_SESSION_ID, "person_id": "x", "fields": []},
    )
    assert response.status_code == 401


def test_delete_contact_requires_auth(client):
    response = client.post(
        "/api/delete-contact",
        json={"session_id": CONTACTS_SESSION_ID, "person_id": "x"},
    )
    assert response.status_code == 401


def test_delete_contact_rejects_blank_ids(client, session_cookie):
    response = client.post(
        "/api/delete-contact",
        json={"session_id": "  ", "person_id": ""},
        cookies={"session": session_cookie},
    )
    assert response.status_code == 400


def test_update_contact_rejects_email_only_update(client, session_cookie):
    """Email is a protected field — an update touching only email must 400."""
    response = client.post(
        "/api/update-contact",
        json={
            "session_id": CONTACTS_SESSION_ID,
            "person_id": "some-person",
            "fields": [{"id": "email", "value": "new@example.com"}],
        },
        cookies={"session": session_cookie},
    )
    assert response.status_code == 400
    assert "email" in response.json()["detail"].lower()


def test_update_contact_rejects_empty_fields(client, session_cookie):
    response = client.post(
        "/api/update-contact",
        json={"session_id": CONTACTS_SESSION_ID, "person_id": "some-person", "fields": []},
        cookies={"session": session_cookie},
    )
    assert response.status_code == 400


@needs_credentials
def test_session_contacts_route_returns_people(client, session_cookie, use_api_key_auth):
    response = client.post(
        "/api/session-contacts",
        json={"session_id": CONTACTS_SESSION_ID},
        cookies={"session": session_cookie},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["session_id"] == CONTACTS_SESSION_ID
    assert data["total"] > 0
    assert data["headers"][0] == "email"
    for person in data["people"]:
        assert person["id"]
        assert person["fields"].get("email")
