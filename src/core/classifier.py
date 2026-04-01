# src/core/classifier.py
import logging
from typing import Optional, Dict, Any
from functools import lru_cache
from transformers import pipeline
from .config import settings

logger = logging.getLogger(__name__)


class TicketClassifier:
    """
    Singleton класс для классификатора с ленивой загрузкой модели.
    Модель загружается только при первом использовании, а не при старте приложения.
    """

    _instance: Optional["TicketClassifier"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Предотвращаем повторную инициализацию
        if self._initialized:
            return

        self._initialized = True
        self._classifier = None  # Модель будет загружена лениво
        self.desc_to_id = {v: k for k, v in settings.CATEGORIES_DATA.items()}
        logger.info("TicketClassifier instance created (model not loaded yet)")

    @property
    def classifier(self):
        """Ленивая загрузка модели при первом обращении"""
        if self._classifier is None:
            logger.info(
                f"Loading model {settings.MODEL_NAME} (this may take a while)..."
            )
            self._classifier = pipeline(
                "zero-shot-classification",
                model=settings.MODEL_NAME,
                device=0,  # -1 для CPU, 0 для GPU
            )
            logger.info("Model loaded successfully!")
        return self._classifier

    def predict(self, text: str) -> Dict[str, Any]:
        """
        Предсказание категории текста.
        Модель загружается только при первом вызове этого метода.
        """
        try:
            # Отправляем текст и список описаний из конфига
            result = self.classifier(
                text, candidate_labels=settings.TICKET_LABELS, multi_label=False
            )

            best_desc = result["labels"][0]
            category_id = self.desc_to_id.get(best_desc)

            return {
                "category": category_id,
                "confidence": round(result["scores"][0], 4),
                "original_description": best_desc,
            }
        except Exception as e:
            logger.error(f"Prediction error: {e}", exc_info=True)
            raise

    def is_model_loaded(self) -> bool:
        """Проверка, загружена ли модель"""
        return self._classifier is not None

    def unload_model(self):
        """Выгрузка модели для освобождения памяти (опционально)"""
        if self._classifier is not None:
            logger.info("Unloading model...")
            del self._classifier
            self._classifier = None
            import gc

            gc.collect()
            logger.info("Model unloaded")


# Глобальный экземпляр (синглтон)
model_instance = TicketClassifier()
