import logging
from typing import Optional, Dict, Any
import torch
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
            logger.info(f"Loading model {settings.MODEL_NAME}...")

            device = 0 if torch.cuda.is_available() else -1

            self._classifier = pipeline(
                "zero-shot-classification",
                model=settings.MODEL_NAME,
                device=device,
                torch_dtype=torch.float16 if device == 0 else torch.float32,
                batch_size=8,
            )

            if device == 0:
                logger.info(f"Model loaded on GPU: {torch.cuda.get_device_name(0)}")
        return self._classifier

    def predict(self, text: str) -> Dict[str, Any]:
        """
        Предсказание категории текста.
        Модель загружается только при первом вызове этого метода.
        """
        try:
            # Отправляем текст и список описаний из конфига
            with torch.autocast(
                device_type="cuda" if torch.cuda.is_available() else "cpu",
                enabled=torch.cuda.is_available(),
            ):
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
