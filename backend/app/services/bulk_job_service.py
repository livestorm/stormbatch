from __future__ import annotations

from app.schemas.bulk_jobs import BulkRegistrant

# Livestorm accepts at most 50 tasks per bulk job.
BULK_JOB_TASK_LIMIT = 50


def build_bulk_tasks(registrants: list[BulkRegistrant]) -> list[dict]:
    """Livestorm bulk job tasks for one chunk; blank values are left out."""
    if not registrants:
        raise ValueError("No registrants to send.")
    if len(registrants) > BULK_JOB_TASK_LIMIT:
        raise ValueError(
            f"A batch can hold at most {BULK_JOB_TASK_LIMIT} registrants, got {len(registrants)}."
        )

    tasks = []
    for position, registrant in enumerate(registrants, start=1):
        fields = []
        seen_ids: set[str] = set()
        for field in registrant.fields:
            field_id = field.id.strip()
            value = field.value.strip()
            if not field_id or not value:
                continue
            if field_id in seen_ids:
                raise ValueError(f"Registrant {position} has the field '{field_id}' more than once.")
            seen_ids.add(field_id)
            fields.append({"id": field_id, "value": value})
        if "email" not in seen_ids:
            raise ValueError(f"Registrant {position} has no email.")
        tasks.append({"fields": fields})
    return tasks
