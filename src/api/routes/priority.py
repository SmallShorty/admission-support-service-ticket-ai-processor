import logging
from fastapi import APIRouter, HTTPException
from src.api.schemas import PriorityRequest, PriorityResponse
from src.core.priority import calculate_priority, CATEGORY_WEIGHTS

# Specific logger for priority routes
logger = logging.getLogger("api.priority")
router = APIRouter()


@router.post(
    "/priority",
    response_model=PriorityResponse,
    summary="Calculate priority for a category",
    description="Calculates priority based on category and confidence.",
)
async def calculate_ticket_priority(request: PriorityRequest):
    """
    Calculate priority for a given category.

    - **category**: Category slug (e.g., 'tech_issue', 'finance_contracts')
    - **confidence**: Model confidence score (0-1) - optional
    """
    try:
        logger.info(
            f"Processing priority calculation for category: {request.category}, "
            f"confidence: {request.confidence}"
        )

        # Проверяем существование категории
        if request.category not in CATEGORY_WEIGHTS:
            available_categories = ", ".join(list(CATEGORY_WEIGHTS.keys()))
            raise HTTPException(
                status_code=400,
                detail=f"Unknown category: '{request.category}'. "
                f"Available categories: {available_categories}",
            )

        # Рассчитываем приоритет
        priority = calculate_priority(
            category=request.category,
            confidence=request.confidence,
        )

        logger.info(f"Priority calculated: {priority} for category: {request.category}")

        return PriorityResponse(
            category=request.category,
            priority=priority,
            base_weight=CATEGORY_WEIGHTS[request.category],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Priority calculation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error occurred during priority calculation: {str(e)}",
        )
