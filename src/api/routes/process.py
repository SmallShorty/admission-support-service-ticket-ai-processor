import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from src.api.schemas import ProcessRequest, ProcessResponse, ApplicantInfo, AdmissionIntentCategory
from src.core.queues import classification_queue
from src.core.priority import calculate_priority
from src.core.mock_client import get_applicant_by_snils

logger = logging.getLogger("api.process")
router = APIRouter()


@router.post(
    "/process",
    response_model=ProcessResponse,
    summary="Full ticket processing pipeline",
    description="Classify text, fetch applicant data by SNILS, calculate priority — all in one call.",
)
async def process_ticket(request: ProcessRequest):
    try:
        # 1+2. Fetch applicant and classify in parallel
        prediction, applicant_data = await asyncio.gather(
            classification_queue.enqueue(request.text),
            get_applicant_by_snils(request.snils),
        )
        category_value: str = prediction["category"]
        confidence: float = prediction["confidence"]

        # 3. Map applicant fields to priority inputs
        quotas = applicant_data.get("quotas", {})
        docs = applicant_data.get("documents", {})
        scores = applicant_data.get("examScores", [])
        personal = applicant_data.get("personalInfo", {})

        total_score = sum(s.get("score", 0) for s in scores) if scores else 0

        student_kwargs = {
            "has_bvi": quotas.get("hasBvi", False),
            "has_special_quota": quotas.get("hasSpecialQuota", False),
            "has_separate_quota": quotas.get("hasSeparateQuota", False),
            "has_target_quota": quotas.get("hasTargetQuota", False),
            "has_priority_right": quotas.get("hasPriorityRight", False),
            "original_submitted": docs.get("originalDocumentReceived", False),
            "score": total_score,
        }

        applicant_out = ApplicantInfo(
            id=applicant_data.get("id", ""),
            firstName=personal.get("firstName", ""),
            lastName=personal.get("lastName", ""),
            patronymic=personal.get("patronymic"),
            email=personal.get("email"),
            is_fallback=applicant_data.get("_is_fallback", False),
        )

        # 4. Calculate priority
        now = datetime.now(timezone.utc)
        result = calculate_priority(
            category=category_value,
            confidence=confidence,
            created_at=now,
            **student_kwargs,
        )

        return ProcessResponse(
            category=AdmissionIntentCategory(category_value),
            confidence=confidence,
            priority=result["priority"],
            breakdown=result["breakdown"],
            applicant=applicant_out,
        )

    except Exception as e:
        logger.error(f"process_ticket error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
