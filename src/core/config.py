import json
import os
from pathlib import Path
from pydantic_settings import BaseSettings

os.environ["HF_HUB_OFFLINE"] = "1"


class Settings(BaseSettings):
    # Базовые настройки
    MODEL_NAME: str = "facebook/bart-large-mnli"
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "ticket-classifier-model"

    HF_HUB_OFFLINE: bool = True

    # Путь к файлу с категориями (относительно корня проекта)
    CATEGORIES_FILE: Path = Path(__file__).parent / "categories.json"

    @property
    def CATEGORIES_DATA(self) -> dict:
        """Загружает JSON с категориями и описаниями"""
        if not self.CATEGORIES_FILE.exists():
            return {"general": "General questions about admission"}

        with open(self.CATEGORIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    @property
    def TICKET_LABELS(self) -> list:
        """Список описаний"""
        return list(self.CATEGORIES_DATA.values())

    @property
    def TICKET_SLUGS(self) -> list:
        """Список коротких ID для API (ключи из JSON)"""
        return list(self.CATEGORIES_DATA.keys())

    class Config:
        env_file = ".env"


settings = Settings()
