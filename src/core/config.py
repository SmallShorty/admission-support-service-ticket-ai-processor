import json
import os
from pathlib import Path
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MODEL_NAME: str = "facebook/bart-large-mnli"
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "ticket-classifier-model"
    HF_HUB_OFFLINE: str = "0"
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = []
    CATEGORIES_FILE: Path = Path(__file__).parent / "categories.json"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [
                i.strip().replace('"', "").replace("'", "")
                for i in v.strip("[]").split(",")
                if i.strip()
            ]
        return v

    @property
    def CATEGORIES_DATA(self) -> dict:
        if not self.CATEGORIES_FILE.exists():
            return {"general": "General questions about admission"}
        with open(self.CATEGORIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    @property
    def TICKET_LABELS(self) -> list:
        return list(self.CATEGORIES_DATA.values())

    @property
    def TICKET_SLUGS(self) -> list:
        return list(self.CATEGORIES_DATA.keys())

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
