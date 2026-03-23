# app/routers/ocr.py

from fastapi import APIRouter, File, Form, Depends
from ..utils.ocr_extractor import extract_text_from_file
from ..auth.auth_utils import get_current_user

router = APIRouter()

# 👈🏻 FastAPI의 File()과 Form()을 사용하여 multipart/form-data 처리
@router.post("/extract/ocr")
async def extract_ocr(
    file_content: bytes = File(...),
    file_name: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """
    이미지나 PDF 파일에서 텍스트와 좌표를 추출합니다.
    """
    # 👈🏻 ocr_extractor의 함수를 호출하고 file_name 인자를 전달합니다.
    ocr_result = extract_text_from_file(file_content, file_name)

    return ocr_result