# StormBatch

StormBatch is a simple local MVP for bulk-registering people into Livestorm sessions. The flow is session-first: pick a session (upcoming sessions are listed, with search by event title, date or session ID), then upload a spreadsheet, import the registrants of another session, or edit the session's registrants in place.

## Stack

- Frontend: Vue 3 + Vite
- Backend: FastAPI
- Spreadsheet parsing: pandas + openpyxl
- Livestorm HTTP client: httpx

## Run locally

### Backend

The backend needs Python 3.11 (the version used in production; the pinned dependencies don't install on 3.9).

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Use `python -m uvicorn` instead of plain `uvicorn` so the server runs with the active virtualenv Python.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Notes

- The app accepts `.xlsx` and `.csv` uploads. `/api/preview` parses the file once (every cell as text, so leading zeros and values like "NA" survive) and returns all rows; the browser then sends one JSON chunk of up to 50 registrants per bulk job to `/api/bulk-jobs`. There is no database or server-side persistence.
- Before sending, the browser reads `/api/sessions/{id}/emails` and skips people already registered to the selected session (they are still sent to any extra sessions). Rows without an email are skipped and reported.
- The upload screen offers a template CSV built from the session's registration fields, and after a batch the rows that still failed can be downloaded as a CSV with the reason, to fix and re-upload.
- The session picker uses `/api/sessions` (upcoming and live sessions from 6 hours ago onwards, soonest first, 10 per page; `q` searches event titles or looks up a session ID) and `/api/sessions/{id}`, which also returns the registration form fields used to check column mappings.
- All jobs of a batch are created first (250 ms apart, under Livestorm's 5 req/s limit), then the frontend follows the oldest unfinished one through `/api/job-status`, every 5 seconds while it runs.
- Job polling uses Livestorm's documented endpoints: `GET /v1/jobs/{id}` and `GET /v1/jobs/{id}/tasks`.
- Email is the only mandatory field for Livestorm API registrations. Extra mapped fields are optional prefill data; attendees can complete other required event fields later before joining.
- "Edit this session's registrants" fetches a session's registrants (`GET /v1/sessions/{id}/people`), edits them via `PATCH /v1/sessions/{id}/people/{id}`, and can unregister them via `DELETE /v1/sessions/{id}/people/{id}` (two-step confirm in the UI).
- When Livestorm answers 401 (expired OAuth token), the backend drops the stored token and the frontend logs the user out back to the connect screen with an explanation, instead of showing raw API errors.
- Livestorm's people PATCH endpoint currently applies the update but often never completes the HTTP response. The backend uses a short timeout and then confirms the write by re-reading the contact and comparing field values (`update_session_person` in `livestorm_client.py`).

## Deploy on Render

StormBatch can run as one Docker Web Service. The Docker image builds the Vue app, copies the static files into the runtime image, and serves both the frontend and FastAPI API from one process.

Use the included `render.yaml` Blueprint or create a Render Web Service manually with:

```bash
Dockerfile path: ./Dockerfile
Health check path: /health
```

Render provides the `PORT` environment variable automatically.

Set these environment variables on the service:

- `SESSION_SECRET_KEY`: a long random value (for example `python -c "import secrets; print(secrets.token_urlsafe(48))"`). It signs the session cookie and encrypts the Livestorm token stored in it. In production the app refuses to start without it, and changing it logs everyone out.
- `LIVESTORM_OAUTH_CLIENT_ID`, `LIVESTORM_OAUTH_CLIENT_SECRET`, `LIVESTORM_OAUTH_REDIRECT_URI` (and optionally `LIVESTORM_OAUTH_SCOPES`).

Production mode (HTTPS-only session cookies, no CORS, required secret) turns on when `RENDER=true`, which Render sets on its services, or when `STORMBATCH_ENV=production` on any other host.

Uploads are limited to 10 MB and 20,000 rows (`MAX_UPLOAD_BYTES` and `MAX_ROWS` in `backend/app/services/excel_parser.py`).
