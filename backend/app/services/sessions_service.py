from __future__ import annotations

import re
import time
from typing import Any, Optional

from app.services.transfer_service import _extract_person_fields

SESSIONS_PAGE_SIZE = 10
# Listing registrants costs one Livestorm call per 100 people, out of a
# 10,000-call rolling monthly quota, so larger sessions are not checked ahead.
REGISTERED_CHECK_LIMIT = 2_000
UPCOMING_STATUSES = {"upcoming", "live"}
# Sessions that never started keep the "upcoming" status forever, so lists only
# keep sessions planned from a few hours ago onwards (this also keeps live ones).
UPCOMING_GRACE_SECONDS = 6 * 3600

_SESSION_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def is_session_id(value: str) -> bool:
    return bool(_SESSION_ID_RE.match(value.strip()))


def _upcoming_cutoff() -> int:
    return int(time.time()) - UPCOMING_GRACE_SECONDS


def build_session_list_params(
    scope: str, date_from: Optional[int], date_to: Optional[int], page: int
) -> dict[str, Any]:
    """Livestorm /v1/sessions query for the picker, soonest first.

    Without an explicit date window, upcoming lists start a few hours ago; the
    API's default order is newest first, so the sort must always be explicit.
    """
    params: dict[str, Any] = {
        "sort": "estimated_started_at",
        "page[size]": SESSIONS_PAGE_SIZE,
        "page[number]": page,
        "include": "event",
    }
    if scope == "upcoming":
        params["filter[status]"] = ",".join(sorted(UPCOMING_STATUSES))
    if date_from is None and date_to is None:
        params["filter[date_from]"] = _upcoming_cutoff()
    if date_from is not None:
        params["filter[date_from]"] = date_from
    if date_to is not None:
        params["filter[date_to]"] = date_to
    return params


def build_event_search_params(title: str, scope: str, page: int) -> dict[str, Any]:
    """Sessions have no title filter, so title search goes through events."""
    params: dict[str, Any] = {
        "filter[title]": title,
        "page[size]": SESSIONS_PAGE_SIZE,
        "page[number]": page,
        "include": "sessions",
    }
    if scope == "upcoming":
        params["filter[scheduling_status]"] = ",".join(sorted(UPCOMING_STATUSES))
    return params


def _included(payload: dict[str, Any], resource_type: str) -> list[dict[str, Any]]:
    return [item for item in payload.get("included", []) if item.get("type") == resource_type]


def _event_id(session: dict[str, Any]) -> str:
    relationship = (session.get("relationships") or {}).get("event", {}).get("data") or {}
    return relationship.get("id") or session.get("attributes", {}).get("event_id") or ""


def summarize_session(session: dict[str, Any], event: Optional[dict[str, Any]]) -> dict[str, Any]:
    attrs = session.get("attributes", {})
    event_attrs = (event or {}).get("attributes", {})
    name = (attrs.get("name") or "").strip()
    return {
        "id": session.get("id", ""),
        "title": (event_attrs.get("title") or "").strip() or name or "Untitled session",
        "name": name,
        "status": attrs.get("status") or "",
        "estimated_started_at": attrs.get("estimated_started_at"),
        "timezone": attrs.get("timezone") or "",
        "registrants_count": attrs.get("registrants_count") or 0,
        "event_id": _event_id(session),
    }


def form_fields(event: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (event or {}).get("attributes", {}).get("fields") or []
    ordered = sorted(
        (field for field in fields if field.get("id")),
        key=lambda field: field.get("order") or 0,
    )
    return [
        {
            "id": field["id"],
            "type": field.get("type") or "text",
            "required": bool(field.get("required")),
        }
        for field in ordered
    ]


def summarize_session_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Summaries for a /v1/sessions?include=event page, in the API's order."""
    events = {event["id"]: event for event in _included(payload, "events")}
    return [summarize_session(session, events.get(_event_id(session))) for session in payload.get("data", [])]


def session_detail(payload: dict[str, Any]) -> dict[str, Any]:
    """Summary plus form fields for a /v1/sessions/{id}?include=event response."""
    session = payload.get("data") or {}
    events = {event["id"]: event for event in _included(payload, "events")}
    event = events.get(_event_id(session))
    return {**summarize_session(session, event), "fields": form_fields(event)}


def sessions_from_event_search(
    payload: dict[str, Any],
    scope: str,
    date_from: Optional[int],
    date_to: Optional[int],
) -> list[dict[str, Any]]:
    """Flatten the sessions included in an events search page.

    Events include all their sessions, past ones too, so the scope and date
    window are applied here. Upcoming results are soonest first; "any" puts
    upcoming sessions first, then the most recent past ones.
    """
    events = {event["id"]: event for event in payload.get("data", [])}
    if scope == "upcoming" and date_from is None and date_to is None:
        date_from = _upcoming_cutoff()

    summaries = []
    for session in _included(payload, "sessions"):
        summary = summarize_session(session, events.get(_event_id(session)))
        started_at = summary["estimated_started_at"]
        if scope == "upcoming" and summary["status"] not in UPCOMING_STATUSES:
            continue
        if date_from is not None and (started_at is None or started_at < date_from):
            continue
        if date_to is not None and (started_at is None or started_at > date_to):
            continue
        summaries.append(summary)

    upcoming = sorted(
        (s for s in summaries if s["status"] in UPCOMING_STATUSES),
        key=lambda s: s["estimated_started_at"] or 0,
    )
    others = sorted(
        (s for s in summaries if s["status"] not in UPCOMING_STATUSES),
        key=lambda s: s["estimated_started_at"] or 0,
        reverse=True,
    )
    return upcoming + others


def next_page(payload: dict[str, Any]) -> Optional[int]:
    value = (payload.get("meta") or {}).get("next_page")
    return int(value) if value is not None else None


def registrant_emails(people: list[dict[str, Any]]) -> list[str]:
    """Lowercased, de-duplicated emails of a session's registrants."""
    emails = {
        _extract_person_fields(person).get("email", "").strip().lower() for person in people
    }
    return sorted(email for email in emails if email)
