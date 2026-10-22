from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.routes.helpers import require_token
from app.schemas.preview import PreviewResponse
from app.services.excel_parser import parse_excel_upload


router = APIRouter(tags=["preview"])


@router.post("/preview", response_model=PreviewResponse, dependencies=[Depends(require_token)])
async def preview_excel(file: UploadFile = File(...)) -> PreviewResponse:
    try:
        parsed = await parse_excel_upload(file)
        return PreviewResponse(**parsed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
