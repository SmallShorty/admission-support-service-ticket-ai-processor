import logging
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from src.core.priority import MAX_SCORE


class AdmissionIntentCategory(str, Enum):
    TECHNICAL_ISSUES = "TECHNICAL_ISSUES"
    DEADLINES_TIMELINES = "DEADLINES_TIMELINES"
    DOCUMENT_SUBMISSION = "DOCUMENT_SUBMISSION"
    STATUS_VERIFICATION = "STATUS_VERIFICATION"
    SCORES_COMPETITION = "SCORES_COMPETITION"
    PAYMENTS_CONTRACTS = "PAYMENTS_CONTRACTS"
    ENROLLMENT = "ENROLLMENT"
    DORMITORY_HOUSING = "DORMITORY_HOUSING"
    STUDIES_SCHEDULE = "STUDIES_SCHEDULE"
    EVENTS = "EVENTS"
    GENERAL_INFO = "GENERAL_INFO"
    PROGRAM_CONSULTATION = "PROGRAM_CONSULTATION"


class ClassificationRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=1000)


class ClassificationResponse(BaseModel):
    category: AdmissionIntentCategory
    confidence: float


class StudentStatus(BaseModel):
    has_bvi: bool = False
    has_special_quota: bool = False
    has_target_quota: bool = False
    has_separate_quota: bool = False
    has_priority_right: bool = False
    original_submitted: bool = False
    score: int = Field(0, ge=0)

    @field_validator("score")
    @classmethod
    def clamp_score(cls, v: int) -> int:
        if v > MAX_SCORE:
            logging.warning(f"score {v} exceeds MAX_SCORE {MAX_SCORE}, clamping")
        return v


class PriorityRequest(BaseModel):
    category: AdmissionIntentCategory = Field(..., description="Category from AdmissionIntentCategory enum")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score (0–1)")
    created_at: datetime = Field(..., description="Ticket creation time (UTC)")
    student: StudentStatus = Field(default_factory=StudentStatus)


class PriorityResponse(BaseModel):
    category: AdmissionIntentCategory
    priority: float = Field(..., description="Calculated priority value (0–100)")
    breakdown: dict
    recalculated_at: Optional[datetime] = None
