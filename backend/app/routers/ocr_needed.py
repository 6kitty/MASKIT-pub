# app/routers/ocr_needed.py

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from ..auth.auth_utils import get_current_user

router = APIRouter()

# 1. 요청 데이터를 위한 Pydantic 모델 정의
class PreflightCheckRequest(BaseModel):
    filename: str

# 2. 응답 데이터를 위한 Pydantic 모델 정의
class PreflightCheckResponse(BaseModel):
    ocr_needed: bool

# 3. OCR이 필요한 파일 확장자 목록
# 실제 프로젝트에서는 더 많은 확장자를 추가할 수 있습니다.
OCR_REQUIRED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".pdf", ".heic"]

# 4. API 엔드포인트 정의
@router.post("/check-ocr", response_model=PreflightCheckResponse)
def check_ocr_needed(request: PreflightCheckRequest, current_user: dict = Depends(get_current_user)):
    """
    파일 이름을 분석하여 OCR이 필요한지 여부를 반환합니다.
    이미지나 PDF 파일은 OCR이 필요합니다.
    """
    
    # 소문자로 변환하여 확장자 비교
    filename = request.filename.lower()
    
    # 확장자가 OCR 필요 목록에 포함되는지 확인
    ocr_needed = any(filename.endswith(ext) for ext in OCR_REQUIRED_EXTENSIONS)
    
    return {"ocr_needed": ocr_needed}