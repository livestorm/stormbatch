from __future__ import annotations

import csv
from io import BytesIO

import pandas as pd
from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool


AUTO_SUGGESTIONS = {
    "email": "email",
    "email_address": "email",
    "first_name": "first_name",
    "firstname": "first_name",
    "last_name": "last_name",
    "lastname": "last_name",
}


# Uploads are parsed in memory and every row goes back to the browser, so both
# are capped. 20,000 rows is 400 bulk jobs.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_ROWS = 20_000

# Read every cell as text: keeps leading zeros (zip codes, phone numbers), avoids
# "1234.0" from numeric columns with gaps, and only treats truly empty cells as
# missing, so values like "NA" or "Null" survive.
_READ_OPTIONS = {"dtype": str, "keep_default_na": False, "na_values": [""]}


def upload_too_large_message() -> str:
    return f"This file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB. Split it and upload the parts one after the other."


def normalize_header(header: str) -> str:
    return "_".join(str(header).strip().lower().split())


def clean_cell(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def read_excel_with_header_detection(raw_bytes: bytes) -> pd.DataFrame:
    dataframe = pd.read_excel(BytesIO(raw_bytes), engine="openpyxl", **_READ_OPTIONS)
    if dataframe.empty:
        return dataframe

    normalized_columns = [normalize_header(column) for column in dataframe.columns]
    has_placeholder_columns = any(column.startswith("unnamed") for column in normalized_columns)
    first_row_values = [
        clean_cell(value)
        for value in dataframe.iloc[0].tolist()
        if clean_cell(value)
    ]
    normalized_first_row = [normalize_header(value) for value in first_row_values]

    # Some exports include a title row before the real headers. If the first data row
    # looks more like a header row than pandas' detected columns, re-read from row 2.
    first_row_has_email = any(value in {"email", "email_address"} for value in normalized_first_row)
    columns_have_email = any(value in {"email", "email_address"} for value in normalized_columns)
    if has_placeholder_columns and first_row_has_email and not columns_have_email:
        return pd.read_excel(BytesIO(raw_bytes), engine="openpyxl", header=1, **_READ_OPTIONS)

    return dataframe


# Python's sniffer considers any character a delimiter, so a one-column list
# ("email" then addresses) used to split on "m". Only real delimiters qualify.
_CSV_DELIMITERS = ",;\t|"


def detect_csv_delimiter(raw_bytes: bytes) -> str:
    sample = raw_bytes[:64 * 1024].decode("utf-8", errors="ignore")
    try:
        return csv.Sniffer().sniff(sample, delimiters=_CSV_DELIMITERS).delimiter
    except csv.Error:
        # A single column, or a sample too small to tell.
        return ","


def read_csv_bytes(raw_bytes: bytes, **options) -> pd.DataFrame:
    try:
        return pd.read_csv(BytesIO(raw_bytes), encoding="utf-8", **options)
    except UnicodeDecodeError:
        # Excel on Windows saves CSV files as Windows-1252.
        return pd.read_csv(BytesIO(raw_bytes), encoding="cp1252", **options)


def read_csv_with_delimiter_detection(raw_bytes: bytes) -> pd.DataFrame:
    delimiter = detect_csv_delimiter(raw_bytes)
    dataframe = read_csv_bytes(raw_bytes, sep=delimiter, **_READ_OPTIONS)

    if dataframe.empty:
        return dataframe

    normalized_columns = [normalize_header(column) for column in dataframe.columns]
    first_row_values = [
        clean_cell(value)
        for value in dataframe.iloc[0].tolist()
        if clean_cell(value)
    ]
    normalized_first_row = [normalize_header(value) for value in first_row_values]
    first_row_has_email = any(value in {"email", "email_address"} for value in normalized_first_row)
    columns_have_email = any(value in {"email", "email_address"} for value in normalized_columns)

    if first_row_has_email and not columns_have_email:
        return read_csv_bytes(raw_bytes, sep=delimiter, header=1, **_READ_OPTIONS)

    return dataframe


def read_upload_to_dataframe(filename: str, raw_bytes: bytes) -> pd.DataFrame:
    lowered_filename = filename.lower()
    if lowered_filename.endswith(".xlsx"):
        return read_excel_with_header_detection(raw_bytes)
    if lowered_filename.endswith(".csv"):
        return read_csv_with_delimiter_detection(raw_bytes)
    raise ValueError("The uploaded file must be .xlsx or .csv")


def clean_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe = dataframe.dropna(axis="columns", how="all")
    dataframe.columns = [str(column).strip() for column in dataframe.columns]
    dataframe = dataframe.loc[:, [not normalize_header(column).startswith("unnamed") for column in dataframe.columns]]
    return dataframe.dropna(how="all")


async def parse_excel_upload(file: UploadFile) -> dict:
    if not file.filename:
        raise ValueError("The uploaded file must be .xlsx or .csv")

    raw_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if not raw_bytes:
        raise ValueError("Uploaded file is empty")
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(upload_too_large_message())

    # pandas parsing is CPU-bound; keep it off the event loop.
    return await run_in_threadpool(parse_upload_bytes, file.filename, raw_bytes)


def parse_upload_bytes(filename: str, raw_bytes: bytes) -> dict:
    dataframe = read_upload_to_dataframe(filename, raw_bytes)
    if dataframe.empty:
        raise ValueError("Uploaded file is empty")

    dataframe = clean_dataframe(dataframe)
    if dataframe.empty:
        raise ValueError("Uploaded file is empty")
    if len(dataframe) > MAX_ROWS:
        raise ValueError(
            f"This file has {len(dataframe):,} rows. StormBatch handles up to {MAX_ROWS:,} "
            "at a time: split the file and upload the parts one after the other."
        )

    rows = []
    for row in dataframe.to_dict(orient="records"):
        cleaned_row = {str(key).strip(): clean_cell(value) for key, value in row.items()}
        rows.append(cleaned_row)

    if not rows:
        raise ValueError("Must detect at least one row")

    headers = list(dataframe.columns)
    normalized_headers = {header: normalize_header(header) for header in headers}
    suggestions = {
        header: AUTO_SUGGESTIONS.get(normalized_headers[header], "")
        for header in headers
    }

    duplicate_email_columns = {}
    for header in headers:
        lowered_values = [row[header].lower() for row in rows if row[header]]
        counts = {}
        for email in lowered_values:
            counts[email] = counts.get(email, 0) + 1
        duplicate_email_columns[header] = sorted(
            [email for email, count in counts.items() if count > 1]
        )

    return {
        "headers": headers,
        "normalized_headers": normalized_headers,
        "suggestions": suggestions,
        "row_count": len(rows),
        "duplicate_email_columns": duplicate_email_columns,
        "rows": rows,
    }
