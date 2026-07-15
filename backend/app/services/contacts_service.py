from __future__ import annotations

from app.services.transfer_service import _extract_person_fields, _sort_headers


def extract_contacts(people: list[dict]) -> dict:
    """Like extract_people_data, but keeps each person's ID so rows can be PATCHed."""
    contacts = [
        {
            "id": person.get("id", ""),
            "fields": _extract_person_fields(person),
        }
        for person in people
        if person.get("id")
    ]

    all_ids: set[str] = set()
    for contact in contacts:
        all_ids.update(contact["fields"].keys())

    headers = _sort_headers(list(all_ids))
    for contact in contacts:
        contact["fields"] = {fid: contact["fields"].get(fid, "") for fid in headers}

    return {"headers": headers, "people": contacts, "total": len(contacts)}
