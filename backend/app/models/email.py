"""
이메일 데이터 모델
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime,timedelta
from app.utils.datetime_utils import get_kst_now

class AttachmentData(BaseModel):
    """첨부파일 데이터 모델"""
    filename: str
    content_type: str
    size: int
    data: str  # Base64 encoded file content


class OriginalEmailData(BaseModel):
    """원본 이메일 데이터 모델"""
    email_id: str = Field(description="고유 이메일 ID")
    from_email: str = Field(description="발신자 이메일")
    to_emails: List[str] = Field(description="수신자 이메일 리스트")
    subject: str = Field(description="이메일 제목")
    original_body: str = Field(description="마스킹 전 원본 본문 (HTML)")
    attachments: List[AttachmentData] = Field(default=[], description="첨부파일 리스트")
    created_at: datetime = Field(default_factory=get_kst_now, description="생성 시간")

    class Config:
        json_schema_extra = {
            "example": {
                "email_id": "email_20250118_123456_abcd1234",
                "from_email": "sender@example.com",
                "to_emails": ["recipient1@example.com", "recipient2@example.com"],
                "subject": "회의 자료 공유",
                "original_body": "<p>안녕하세요. 회의 자료 전달드립니다.</p>",
                "attachments": [
                    {
                        "filename": "document.pdf",
                        "content_type": "application/pdf",
                        "size": 102400,
                        "data": "base64_encoded_string..."
                    }
                ],
                "created_at": "2025-01-18T12:34:56.789Z"
            }
        }


class OriginalEmailResponse(BaseModel):
    """원본 이메일 조회 응답 모델"""
    success: bool
    message: str
    data: Optional[OriginalEmailData] = None


class MaskedEmailData(BaseModel):
    """마스킹된 이메일 데이터 모델"""
    email_id: str = Field(description="원본 이메일 ID와 동일")
    from_email: str = Field(description="발신자 이메일")
    to_emails: List[str] = Field(description="수신자 이메일 리스트")
    subject: str = Field(description="이메일 제목")
    masked_body: str = Field(description="마스킹된 본문")
    masked_attachments: List[AttachmentData] = Field(default=[], description="마스킹된 첨부파일 리스트")
    masking_decisions: dict = Field(default={}, description="마스킹 결정 정보")
    pii_masked_count: int = Field(default=0, description="마스킹된 PII 개수")
    created_at: datetime = Field(default_factory=get_kst_now, description="생성 시간")

    class Config:
        json_schema_extra = {
            "example": {
                "email_id": "email_20250118_123456_abcd1234",
                "from_email": "sender@example.com",
                "to_emails": ["recipient1@example.com"],
                "subject": "회의 자료 공유",
                "masked_body": "<p>안녕하세요. 회의 자료 전달드립니다. 연락처: 010-****-5678</p>",
                "masked_attachments": [
                    {
                        "filename": "masked_document.pdf",
                        "content_type": "application/pdf",
                        "size": 102400,
                        "data": "base64_encoded_string..."
                    }
                ],
                "masking_decisions": {},
                "pii_masked_count": 3,
                "created_at": "2025-01-18T12:35:00.000Z"
            }
        }


class MaskedEmailResponse(BaseModel):
    """마스킹된 이메일 조회 응답 모델"""
    success: bool
    message: str
    data: Optional[MaskedEmailData] = None
