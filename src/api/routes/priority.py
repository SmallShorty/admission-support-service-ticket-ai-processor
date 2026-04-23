import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from src.api.schemas import PriorityRequest, PriorityResponse
from src.core.priority import calculate_priority

logger = logging.getLogger("api.priority")
router = APIRouter()


@router.post(
    "/priority",
    response_model=PriorityResponse,
    summary="Calculate priority for a ticket",
    description="Calculates priority using topic weight, student status bonuses, and wait time.",
)
async def calculate_ticket_priority(request: PriorityRequest):
    try:
        logger.info(
            f"Priority request: category={request.category}, confidence={request.confidence}"
        )

        now = datetime.now(timezone.utc)
        result = calculate_priority(
            category=request.category.value,
            confidence=request.confidence,
            created_at=request.created_at,
            has_bvi=request.student.has_bvi,
            has_special_quota=request.student.has_special_quota,
            has_target_quota=request.student.has_target_quota,
            has_separate_quota=request.student.has_separate_quota,
            has_priority_right=request.student.has_priority_right,
            original_submitted=request.student.original_submitted,
            score=request.student.score,
            now=now,
        )

        logger.info(f"Priority={result['priority']} for category={request.category}")

        return PriorityResponse(
            category=request.category,
            priority=result["priority"],
            breakdown=result["breakdown"],
            recalculated_at=now,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Priority calculation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error occurred during priority calculation.")
