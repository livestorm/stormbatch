# StormBatch

StormBatch is a simple local MVP for bulk-registering people from a spreadsheet into one or more Livestorm sessions. It can also transfer registrants between sessions and edit contact details of a session's registrants in place.

## Stack

- Frontend: Vue 3 + Vite
- Backend: FastAPI
- Spreadsheet parsing: pandas + openpyxl
- Livestorm HTTP client: httpx

## Run locally

### Backend

```bash
cd backend
python3 -m venv .venv
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

- The app accepts `.xlsx` and `.csv` uploads and re-reads the file when you submit, so there is no database or server-side persistence.
- The frontend polls `/api/job-status` every 2.5 seconds after the jobs are created.
- Job polling uses Livestorm's documented endpoints: `GET /v1/jobs/{id}` and `GET /v1/jobs/{id}/tasks`.
- Email is the only mandatory field for Livestorm API registrations. Extra mapped fields are optional prefill data; attendees can complete other required event fields later before joining.
- The "Update contacts" source mode fetches a session's registrants (`GET /v1/sessions/{id}/people`) and edits them via `PATCH /v1/sessions/{id}/people/{id}`. Email is protected by Livestorm and shown read-only.
- Livestorm's people PATCH endpoint currently applies the update but often never completes the HTTP response. The backend uses a short timeout and then confirms the write by re-reading the contact and comparing field values (`update_session_person` in `livestorm_client.py`).

## Deploy on Render

StormBatch can run as one Docker Web Service. The Docker image builds the Vue app, copies the static files into the runtime image, and serves both the frontend and FastAPI API from one process.

Use the included `render.yaml` Blueprint or create a Render Web Service manually with:

```bash
Dockerfile path: ./Dockerfile
Health check path: /health
```

Render provides the `PORT` environment variable automatically.
