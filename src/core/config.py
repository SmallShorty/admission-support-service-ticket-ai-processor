import json
import os
from pathlib import Path
from typing import List, Union, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Основные настройки приложения
    MODEL_NAME: str = "typeform/distilbert-base-uncased-mnli"
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "ticket-classifier-model"
    HF_HUB_OFFLINE: str = "0"
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = []
    CATEGORIES_FILE: Path = Path(__file__).parent / "categories.json"

    # Настройки Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_SSL: bool = False
    REDIS_TTL_SECONDS: int = 86400  # 24 часа

    # Настройки Nest.js API
    NEST_API_BASE_URL: str = "http://localhost:3000"
    NEST_API_TIMEOUT_SECONDS: float = 5.0
    NEST_API_BATCH_ENDPOINT: str = "/api/applicants/batch"

    # Настройки очередей
    # Очередь классификации
    CLASSIFY_BATCH_SIZE: int = 5
    CLASSIFY_MAX_WAIT_MS: int = 50
    CLASSIFY_WORKER_COUNT: int = 1

    # Очередь SNILS
    SNILS_BATCH_SIZE: int = 50
    SNILS_MAX_WAIT_MS: int = 30
    SNILS_WORKER_COUNT: int = 2

    # Настройки производительности
    REQUEST_TIMEOUT_MS: int = 500
    DEFAULT_APPLICANT_DATA_TTL: int = 60 * 1  # 5 минут для данных по умолчанию

    # Настройки дообученной модели
    USE_FINE_TUNED_MODEL: bool = False
    FINE_TUNED_MODEL_PATH: Optional[str] = None  # например, "models/rubert-ticket-classifier"

    # Настройки логирования
    LOG_LEVEL: str = "INFO"
    ENABLE_QUEUE_METRICS: bool = True

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

    @property
    def REDIS_URL(self) -> str:
        """Генерирует URL для подключения к Redis"""
        scheme = "rediss" if self.REDIS_SSL else "redis"
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"{scheme}://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def NEST_API_BATCH_URL(self) -> str:
        """Полный URL для batch endpoint Nest.js"""
        return f"{self.NEST_API_BASE_URL}{self.NEST_API_BATCH_ENDPOINT}"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
