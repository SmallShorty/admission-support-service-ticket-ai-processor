from transformers import pipeline
from .config import settings


class TicketClassifier:
    def __init__(self):
        # При первом запуске скачается ~1.6 ГБ данных
        print(f"Loading model {settings.MODEL_NAME}...")
        self.classifier = pipeline(
            "zero-shot-classification", model=settings.MODEL_NAME
        )
        # Создаем мапу: Описание из JSON -> ID (ключ) из JSON
        self.desc_to_id = {v: k for k, v in settings.CATEGORIES_DATA.items()}
        print("Model loaded successfully!")

    def predict(self, text: str):
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


model_instance = TicketClassifier()
