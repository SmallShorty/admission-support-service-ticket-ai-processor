import logging
from fastapi import APIRouter, HTTPException
from src.api.schemas import ClassificationRequest, ClassificationResponse
from src.core.classifier import model_instance

# Specific logger for classification routes
logger = logging.getLogger("api.classification")
router = APIRouter()


@router.post(
    "/classify",
    response_model=ClassificationResponse,
    summary="Classify admission ticket",
    description="Analyzes the input text and maps it to a specific category slug.",
)
async def classify_ticket(request: ClassificationRequest):
    """
    Inbound ticket processing logic.
    """
    try:
        logger.info(f"Processing classification for text length: {len(request.text)}")

        prediction = model_instance.predict(request.text)

        logger.info(f"Task completed. Slug: {prediction['category']}")

        return ClassificationResponse(
            category=prediction["category"], confidence=prediction["confidence"]
        )
    except Exception as e:
        logger.error(f"Inference error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Error occurred during classification."
        )
