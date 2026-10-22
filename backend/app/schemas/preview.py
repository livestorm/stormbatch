from pydantic import BaseModel


class PreviewResponse(BaseModel):
    headers: list[str]
    normalized_headers: dict[str, str]
    suggestions: dict[str, str]
    row_count: int
    duplicate_email_columns: dict[str, list[str]]
    # Every row, so the browser can build registration chunks without re-uploading.
    rows: list[dict[str, str]]
