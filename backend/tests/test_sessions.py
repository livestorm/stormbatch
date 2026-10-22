"""
Tests for the session picker endpoints (/api/sessions and /api/sessions/{id}).

  1. Service layer — JSON:API normalization, no network.
  2. Route layer   — FastAPI routes with a fake LivestormClient, no network.
  3. Live layer    — real Livestorm API calls through the routes (needs LS_KEY).

Run (from the backend/ directory):
    python -m pytest tests/test_sessions.py -v
"""

import time

import httpx
import pytest

from app.services import sessions_service
from app.services.livestorm_client import LivestormAPIError, LivestormClient, TooManyRecordsError
from tests.conftest import needs_credentials

NOW = int(time.time())
EVENT_ID = "11111111-1111-1111-1111-111111111111"
SESSION_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
SESSION_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
SESSION_C = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def _session(session_id, status, started_at, name=None, registrants=0):
    return {
        "id": session_id,
        "type": "sessions",
        "attributes": {
            "event_id": EVENT_ID,
            "status": status,
            "estimated_started_at": started_at,
            "timezone": "Europe/Paris",
            "registrants_count": registrants,
            "name": name,
        },
    }


def _event(fields=None):
    return {
        "id": EVENT_ID,
        "type": "events",
        "attributes": {
            "title": "  Product onboarding  ",
            "fields": fields
            if fields is not None
            else [
                {"id": "company", "type": "text", "order": 3, "required": False},
                {"id": "first_name", "type": "text", "order": 1, "required": True},
                {"id": "last_name", "type": "text", "order": 2, "required": True},
            ],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 1. Service layer
# ══════════════════════════════════════════════════════════════════════════════


def test_is_session_id():
    assert sessions_service.is_session_id(SESSION_A)
    assert sessions_service.is_session_id(f"  {SESSION_A.upper()} ")
    assert not sessions_service.is_session_id("onboarding")
    assert not sessions_service.is_session_id(SESSION_A[:-1])


def test_list_params_default_to_upcoming_from_a_few_hours_ago():
    params = sessions_service.build_session_list_params("upcoming", None, None, page=2)

    assert params["sort"] == "estimated_started_at"
    assert params["filter[status]"] == "live,upcoming"
    assert params["page[number]"] == 2
    assert params["page[size]"] == 10
    assert params["include"] == "event"
    cutoff = NOW - sessions_service.UPCOMING_GRACE_SECONDS
    assert abs(params["filter[date_from]"] - cutoff) < 60


def test_list_params_use_explicit_date_window():
    params = sessions_service.build_session_list_params("any", 1000, 2000, page=0)

    assert params["filter[date_from]"] == 1000
    assert params["filter[date_to]"] == 2000
    assert "filter[status]" not in params


def test_summarize_session_list_uses_event_title():
    payload = {
        "data": [_session(SESSION_A, "upcoming", NOW + 3600, registrants=4)],
        "included": [_event()],
        "meta": {"next_page": 1},
    }

    [summary] = sessions_service.summarize_session_list(payload)

    assert summary["title"] == "Product onboarding"
    assert summary["name"] == ""
    assert summary["registrants_count"] == 4
    assert summary["event_id"] == EVENT_ID
    assert sessions_service.next_page(payload) == 1
    assert sessions_service.next_page({"meta": {"next_page": None}}) is None


def test_session_detail_orders_form_fields():
    payload = {"data": _session(SESSION_A, "upcoming", NOW + 3600), "included": [_event()]}

    detail = sessions_service.session_detail(payload)

    assert [f["id"] for f in detail["fields"]] == ["first_name", "last_name", "company"]
    assert detail["fields"][0] == {"id": "first_name", "type": "text", "required": True}


def test_session_without_event_title_falls_back_to_name():
    payload = {"data": _session(SESSION_A, "upcoming", NOW, name="Morning run"), "included": []}

    detail = sessions_service.session_detail(payload)

    assert detail["title"] == "Morning run"
    assert detail["fields"] == []


def test_event_search_keeps_recent_upcoming_sessions_soonest_first():
    payload = {
        "data": [_event()],
        "included": [
            _session(SESSION_A, "upcoming", NOW + 7200),
            _session(SESSION_B, "upcoming", NOW + 3600),
            _session(SESSION_C, "past", NOW - 86400),
            # Never started, years ago: still "upcoming" in Livestorm.
            _session("dddddddd-dddd-dddd-dddd-dddddddddddd", "upcoming", NOW - 400 * 86400),
        ],
    }

    sessions = sessions_service.sessions_from_event_search(payload, "upcoming", None, None)

    assert [s["id"] for s in sessions] == [SESSION_B, SESSION_A]
    assert sessions[0]["title"] == "Product onboarding"


def test_event_search_any_scope_puts_upcoming_first_then_recent_past():
    payload = {
        "data": [_event()],
        "included": [
            _session(SESSION_A, "past", NOW - 86400 * 30),
            _session(SESSION_B, "past", NOW - 86400),
            _session(SESSION_C, "upcoming", NOW + 3600),
        ],
    }

    sessions = sessions_service.sessions_from_event_search(payload, "any", None, None)

    assert [s["id"] for s in sessions] == [SESSION_C, SESSION_B, SESSION_A]


def test_event_search_applies_date_window():
    payload = {
        "data": [_event()],
        "included": [
            _session(SESSION_A, "upcoming", 5000),
            _session(SESSION_B, "upcoming", 15000),
        ],
    }

    sessions = sessions_service.sessions_from_event_search(payload, "upcoming", 1000, 10000)

    assert [s["id"] for s in sessions] == [SESSION_A]


# ══════════════════════════════════════════════════════════════════════════════
# 2. Route layer — fake Livestorm client
# ══════════════════════════════════════════════════════════════════════════════


class FakeLivestormClient:
    calls: list = []
    session_payload: dict = {}
    raise_on_get: LivestormAPIError = None

    def __init__(self, token, use_bearer=True):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def list_sessions(self, params):
        FakeLivestormClient.calls.append(("list_sessions", params))
        return {
            "data": [_session(SESSION_A, "upcoming", NOW + 3600)],
            "included": [_event()],
            "meta": {"next_page": 1},
        }

    async def list_events(self, params):
        FakeLivestormClient.calls.append(("list_events", params))
        return {
            "data": [_event()],
            "included": [_session(SESSION_B, "upcoming", NOW + 3600)],
            "meta": {"next_page": None},
        }

    async def get_session(self, session_id):
        FakeLivestormClient.calls.append(("get_session", session_id))
        if FakeLivestormClient.raise_on_get:
            raise FakeLivestormClient.raise_on_get
        return {"data": _session(session_id, "past", NOW - 86400), "included": [_event()]}

    async def list_session_people(self, session_id, max_records=None):
        FakeLivestormClient.calls.append(("list_session_people", session_id, max_records))
        if FakeLivestormClient.raise_on_get:
            raise FakeLivestormClient.raise_on_get
        return [
            {"id": "p1", "attributes": {"registrant_detail": {"fields": [{"id": "email", "value": "Ann@Example.com "}]}}},
            {"id": "p2", "attributes": {"registrant_detail": {"fields": [{"id": "email", "value": "bob@example.com"}]}}},
            {"id": "p3", "attributes": {"registrant_detail": {"fields": [{"id": "email", "value": "ann@example.com"}]}}},
        ]


@pytest.fixture
def fake_livestorm(monkeypatch):
    from app.routes import sessions as sessions_routes

    FakeLivestormClient.calls = []
    FakeLivestormClient.raise_on_get = None
    monkeypatch.setattr(sessions_routes, "LivestormClient", FakeLivestormClient)
    return FakeLivestormClient


def test_sessions_requires_auth(client):
    assert client.get("/api/sessions").status_code == 401
    assert client.get(f"/api/sessions/{SESSION_A}").status_code == 401


def test_sessions_lists_upcoming_by_default(client, session_cookie, fake_livestorm):
    response = client.get("/api/sessions", cookies={"session": session_cookie})

    assert response.status_code == 200
    body = response.json()
    assert body["next_page"] == 1
    assert body["sessions"][0]["id"] == SESSION_A
    assert body["sessions"][0]["title"] == "Product onboarding"
    [(method, params)] = fake_livestorm.calls
    assert method == "list_sessions"
    assert params["filter[status]"] == "live,upcoming"
    assert params["page[number]"] == 0


def test_sessions_title_search_goes_through_events(client, session_cookie, fake_livestorm):
    response = client.get(
        "/api/sessions", params={"q": " onboarding ", "page": 1}, cookies={"session": session_cookie}
    )

    assert response.status_code == 200
    assert [s["id"] for s in response.json()["sessions"]] == [SESSION_B]
    [(method, params)] = fake_livestorm.calls
    assert method == "list_events"
    assert params["filter[title]"] == "onboarding"
    assert params["page[number]"] == 1


def test_sessions_id_search_returns_session_of_any_status(client, session_cookie, fake_livestorm):
    response = client.get("/api/sessions", params={"q": SESSION_C}, cookies={"session": session_cookie})

    assert response.status_code == 200
    body = response.json()
    assert [s["id"] for s in body["sessions"]] == [SESSION_C]
    assert body["sessions"][0]["status"] == "past"
    assert body["next_page"] is None


def test_sessions_id_search_unknown_id_is_empty(client, session_cookie, fake_livestorm):
    fake_livestorm.raise_on_get = LivestormAPIError("not found", status_code=404)

    response = client.get("/api/sessions", params={"q": SESSION_C}, cookies={"session": session_cookie})

    assert response.status_code == 200
    assert response.json() == {"sessions": [], "next_page": None}


def test_sessions_rejects_negative_page(client, session_cookie, fake_livestorm):
    response = client.get("/api/sessions", params={"page": -1}, cookies={"session": session_cookie})
    assert response.status_code == 422


def test_session_detail_returns_form_fields(client, session_cookie, fake_livestorm):
    response = client.get(f"/api/sessions/{SESSION_A}", cookies={"session": session_cookie})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == SESSION_A
    assert [f["id"] for f in body["fields"]] == ["first_name", "last_name", "company"]


def test_session_detail_rejects_malformed_id_without_calling_livestorm(
    client, session_cookie, fake_livestorm
):
    response = client.get("/api/sessions/not-a-session", cookies={"session": session_cookie})

    assert response.status_code == 404
    assert fake_livestorm.calls == []


def test_session_detail_unknown_session_is_404(client, session_cookie, fake_livestorm):
    fake_livestorm.raise_on_get = LivestormAPIError("not found", status_code=404)

    response = client.get(f"/api/sessions/{SESSION_A}", cookies={"session": session_cookie})

    assert response.status_code == 404


def test_session_detail_expired_token_is_401(client, session_cookie, fake_livestorm):
    fake_livestorm.raise_on_get = LivestormAPIError("expired", status_code=401)

    response = client.get(f"/api/sessions/{SESSION_A}", cookies={"session": session_cookie})

    assert response.status_code == 401


def test_registered_emails_are_lowercased_and_unique(client, session_cookie, fake_livestorm):
    response = client.get(f"/api/sessions/{SESSION_A}/emails", cookies={"session": session_cookie})

    assert response.status_code == 200
    assert response.json() == {
        "session_id": SESSION_A,
        "emails": ["ann@example.com", "bob@example.com"],
        "checked": True,
        "registrants_count": 3,
    }
    [(_, _, max_records)] = fake_livestorm.calls
    assert max_records == sessions_service.REGISTERED_CHECK_LIMIT


def test_registered_emails_skips_sessions_too_large_to_list(client, session_cookie, fake_livestorm):
    fake_livestorm.raise_on_get = TooManyRecordsError(12_345)

    response = client.get(f"/api/sessions/{SESSION_A}/emails", cookies={"session": session_cookie})

    assert response.status_code == 200
    assert response.json() == {
        "session_id": SESSION_A,
        "emails": [],
        "checked": False,
        "registrants_count": 12_345,
    }


def _people_page(page, record_count, page_count):
    return {
        "data": [{"id": f"p{page}", "attributes": {}}],
        "meta": {
            "current_page": page,
            "next_page": page + 1 if page + 1 < page_count else None,
            "record_count": record_count,
            "page_count": page_count,
        },
    }


async def test_listing_a_large_session_costs_one_call(monkeypatch):
    calls = []

    async def fake_request(self, method, path, **kwargs):
        calls.append(kwargs["params"]["page[number]"])
        return httpx.Response(200, json=_people_page(0, record_count=2_500, page_count=25))

    monkeypatch.setattr(LivestormClient, "_request", fake_request)
    async with LivestormClient(token="token") as client:
        with pytest.raises(TooManyRecordsError) as raised:
            await client.list_session_people(SESSION_A, max_records=2_000)

    assert raised.value.record_count == 2_500
    assert calls == [0]


async def test_listing_under_the_limit_reads_every_page(monkeypatch):
    calls = []

    async def fake_request(self, method, path, **kwargs):
        page = kwargs["params"]["page[number]"]
        calls.append(page)
        return httpx.Response(200, json=_people_page(page, record_count=150, page_count=2))

    monkeypatch.setattr(LivestormClient, "_request", fake_request)
    async with LivestormClient(token="token") as client:
        people = await client.list_session_people(SESSION_A, max_records=2_000, inter_page_delay=0)

    assert calls == [0, 1]
    assert [p["id"] for p in people] == ["p0", "p1"]


def test_registered_emails_requires_auth_and_valid_id(client, session_cookie, fake_livestorm):
    assert client.get(f"/api/sessions/{SESSION_A}/emails").status_code == 401
    assert client.get("/api/sessions/nope/emails", cookies={"session": session_cookie}).status_code == 404
    assert fake_livestorm.calls == []


# ══════════════════════════════════════════════════════════════════════════════
# 3. Live layer — real Livestorm API
# ══════════════════════════════════════════════════════════════════════════════


@needs_credentials
def test_live_upcoming_sessions_are_sorted_and_paginated(client, session_cookie, use_api_key_auth):
    first = client.get("/api/sessions", cookies={"session": session_cookie})
    assert first.status_code == 200, first.text
    body = first.json()
    sessions = body["sessions"]

    assert 0 < len(sessions) <= sessions_service.SESSIONS_PAGE_SIZE
    assert all(s["status"] in {"upcoming", "live"} for s in sessions)
    starts = [s["estimated_started_at"] for s in sessions]
    assert starts == sorted(starts)
    assert min(starts) >= int(time.time()) - sessions_service.UPCOMING_GRACE_SECONDS - 60

    if body["next_page"] is not None:
        second = client.get(
            "/api/sessions", params={"page": body["next_page"]}, cookies={"session": session_cookie}
        ).json()
        assert {s["id"] for s in second["sessions"]}.isdisjoint({s["id"] for s in sessions})


@needs_credentials
def test_live_title_and_id_search_find_the_same_session(client, session_cookie, use_api_key_auth):
    [first] = client.get("/api/sessions", cookies={"session": session_cookie}).json()["sessions"][:1]
    term = max(first["title"].split(), key=len)

    by_title = client.get("/api/sessions", params={"q": term}, cookies={"session": session_cookie})
    by_id = client.get("/api/sessions", params={"q": first["id"]}, cookies={"session": session_cookie})

    assert by_title.status_code == 200, by_title.text
    assert first["id"] in {s["id"] for s in by_title.json()["sessions"]} or by_title.json()["next_page"]
    assert [s["id"] for s in by_id.json()["sessions"]] == [first["id"]]


@needs_credentials
def test_live_session_detail_has_form_fields(client, session_cookie, use_api_key_auth):
    [first] = client.get("/api/sessions", cookies={"session": session_cookie}).json()["sessions"][:1]

    detail = client.get(f"/api/sessions/{first['id']}", cookies={"session": session_cookie})

    assert detail.status_code == 200, detail.text
    field_ids = {f["id"] for f in detail.json()["fields"]}
    assert {"first_name", "last_name"} <= field_ids
