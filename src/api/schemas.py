from pydantic import BaseModel, Field
from typing import Optional


class ClassificationRequest(BaseModel):
    # The text input from the applicant (e.g., a question or a ticket)
    text: str = Field(..., min_length=5, max_length=1000)


class ClassificationResponse(BaseModel):
    # The short ID (slug) of the category mapped from the JSON config
    category: str
    # Confidence score from 0.0 to 1.0 (BART output)
    confidence: float


class PriorityRequest(BaseModel):
    # Category slug (e.g., 'tech_issue', 'finance_contracts')
    category: str = Field(..., description="Category slug from the classification")

    # Model confidence score (optional)
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence score from the classification model (0.0 to 1.0)",
    )


class PriorityResponse(BaseModel):
    # The category slug
    category: str = Field(..., description="Category slug")

    # Calculated priority value (0-100)
    priority: float = Field(..., description="Calculated priority value (0-100)")

    # Base weight of the category from priority configuration
    base_weight: int = Field(..., description="Base priority weight of the category")
