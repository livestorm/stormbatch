from __future__ import annotations

_PRIORITY_FIELDS = ["email", "first_name", "last_name"]
# System metadata fields that are not useful for re-registration.
_SKIP_ATTRIBUTES = {"created_at", "updated_at", "role", "locale", "time_zone", "id", "type"}


def _extract_person_fields(person: dict) -> dict[str, str]:
    attrs = person.get("attributes", person)

    # Fields are nested under registrant_detail per the Livestorm v1 API response.
    registrant_detail = attrs.get("registrant_detail") or {}
    fields_list = registrant_detail.get("fields")
    if isinstance(fields_list, list) and fields_list:
        result: dict[str, str] = {}
        for field in fields_list:
            fid = field.get("id")
            val = field.get("value")
            if fid and val is not None:
                result[fid] = str(val).strip()
        if result:
            return result

    # Fall back to well-known top-level attribute keys.
    result = {}
    for key in _PRIORITY_FIELDS:
        val = attrs.get(key)
        if val is not None and str(val).strip():
            result[key] = str(val).strip()
    return result


def _sort_headers(field_ids: list[str]) -> list[str]:
    priority = {fid: i for i, fid in enumerate(_PRIORITY_FIELDS)}
    return sorted(field_ids, key=lambda f: (priority.get(f, 999), f))


def extract_people_data(people: list[dict]) -> dict:
    rows = [_extract_person_fields(p) for p in people]

    all_ids: set[str] = set()
    for row in rows:
        all_ids.update(row.keys())

    headers = _sort_headers(list(all_ids))
    normalized = [{fid: row.get(fid, "") for fid in headers} for row in rows]

    return {"headers": headers, "rows": normalized, "total": len(normalized)}
