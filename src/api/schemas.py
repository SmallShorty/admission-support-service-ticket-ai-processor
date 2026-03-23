from pydantic import BaseModel, Field


class ClassificationRequest(BaseModel):
    # The text input from the applicant (e.g., a question or a ticket)
    text: str = Field(..., min_length=5, max_length=1000)


class ClassificationResponse(BaseModel):
    # The short ID (slug) of the category mapped from the JSON config
    category: str
    # Confidence score from 0.0 to 1.0 (BART output)
    confidence: float
