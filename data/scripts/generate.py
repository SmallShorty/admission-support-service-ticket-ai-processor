import os
import json
import random
import time
from typing import List, Dict, Optional
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY не найден в .env")

genai.configure(api_key=api_key)


class DatasetGenerator:
    def __init__(self, personas_path: str, taxonomy_path: str):
        self.personas = self._load_json(personas_path)
        self.categories = self._load_json(taxonomy_path)

        # Настройка модели
        self.model = genai.GenerativeModel(
            model_name="gemini-flash-latest",
            generation_config={
                "temperature": 0.9,
                "response_mime_type": "application/json",
            },
        )

    def _load_json(self, path: str) -> List[Dict]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_persona_by_id(self, persona_id: str) -> Dict:
        """Явный выбор персоны по ID (A, B, C, D, E)"""
        persona = next((p for p in self.personas if p["id"] == persona_id), None)
        if not persona:
            raise ValueError(f"Персона с ID {persona_id} не найдена")
        return persona

    def get_category_by_id(self, category_id: str) -> Dict:
        """Явный выбор категории по ID (из taxonomy.json)"""
        category = next((c for c in self.categories if c["id"] == category_id), None)
        if not category:
            raise ValueError(f"Категория с ID {category_id} не найдена")
        return category

    def _generate_ticket(self, persona: Dict, category: Dict) -> Optional[Dict]:
        """Приватный метод для прямого обращения к LLM"""
        prompt = f"""
        Ты — эксперт Admission Support Service. Напиши текст обращения.
        
        КТО ПИШЕТ: {persona['name']}
        ОПИСАНИЕ: {persona['settings']['description']}
        СТИЛЬ: {persona['settings']['style']}
        ТОН: {persona['settings']['tone']}
        
        ТЕМА: {category['name_ru']} ({category['description']})
        
        ОГРАНИЧЕНИЯ:
        - ЗАПРЕЩЕНО: эмодзи, сокращение "ASS".
        - Язык: Русский.
        - Не называй категорию прямо.
        
        ВЕРНИ JSON:
        {{
            "persona_id": "{persona['id']}",
            "category_id": "{category['id']}",
            "ticket_text": "текст"
        }}
        """
        try:
            response = self.model.generate_content(prompt)
            return json.loads(response.text)
        except Exception as e:
            print(f"Ошибка [Persona {persona['id']}, Category {category['id']}]: {e}")
            return None

    def create_custom_batch(self, persona_id: str, category_id: str, count: int):
        """Генерация конкретного набора данных"""
        persona = self.get_persona_by_id(persona_id)
        category = self.get_category_by_id(category_id)

        batch = []
        print(
            f"Запуск: {count} заявок от '{persona['name']}' по теме '{category['name_ru']}'"
        )

        for i in range(count):
            sample = self._generate_ticket(persona, category)
            if sample:
                batch.append(sample)
            time.sleep(1)  # Пауза для лимитов API

        self._save(batch, f"custom_{persona_id}_{category_id}")

    def _save(self, data: List[Dict], suffix: str):
        os.makedirs("data/raw", exist_ok=True)
        path = f"data/raw/batch_{suffix}_{int(time.time())}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Сохранено в {path}")


# --- ПРИМЕР ИСПОЛЬЗОВАНИЯ В КОДЕ ---
if __name__ == "__main__":
    generator = DatasetGenerator(
        personas_path="data/config/personas.json",
        taxonomy_path="data/config/taxonomy.json",
    )

    # Вариант 1: Генерируем только для Технических Скептиков (ID: C)
    # по теме Технических ошибок (ID: tech_error)
    generator.create_custom_batch(persona_id="C", category_id="tech_issue", count=3)

    # Вариант 2: Генерируем для Родителей (ID: D)
    # по теме Платного обучения (ID: paid_education)
    # generator.create_custom_batch('D', 'paid_education', 5)
