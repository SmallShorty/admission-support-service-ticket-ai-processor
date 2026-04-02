import os
import json
import random
import time
from typing import List, Dict, Optional
from dotenv import load_dotenv
import requests

load_dotenv()
api_key = os.getenv("DEEPSEEK_API_KEY")

if not api_key:
    raise ValueError("DEEPSEEK_API_KEY не найден в .env")


class DeepSeekDatasetGenerator:
    def __init__(self, personas_path: str, taxonomy_path: str):
        self.personas = self._load_json(personas_path)
        self.categories = self._load_json(taxonomy_path)
        
        # DeepSeek API endpoint
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

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
        """Приватный метод для обращения к DeepSeek API"""
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
        - Текст должен быть реалистичным и соответствовать стилю и тону персоны.
        - Длина: 2-5 предложений.
        
        ВЕРНИ ТОЛЬКО JSON ОБЪЕКТ без дополнительного текста:
        {{
            "persona_id": "{persona['id']}",
            "category_id": "{category['id']}",
            "ticket_text": "текст обращения здесь"
        }}
        """
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Ты эксперт по генерации реалистичных обращений для службы поддержки абитуриентов."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.9,
            "max_tokens": 500
        }
        
        try:
            response = requests.post(self.api_url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # Извлекаем JSON из ответа (может быть обернут в markdown)
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            if content.startswith("```"):
                content = content[3:]
                
            return json.loads(content.strip())
        except Exception as e:
            print(f"Ошибка [Persona {persona['id']}, Category {category['id']}]: {e}")
            print(f"Ответ API: {response.text if 'response' in locals() else 'Нет ответа'}")
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
            print(f"Генерация {i+1}/{count}...")
            sample = self._generate_ticket(persona, category)
            if sample:
                batch.append(sample)
                print(f"✓ Сгенерировано: {sample['ticket_text'][:50]}...")
            else:
                print(f"✗ Ошибка генерации")
            time.sleep(1)  # Пауза для лимитов API

        self._save(batch, f"deepseek_{persona_id}_{category_id}")
        return batch

    def generate_full_dataset(self, samples_per_combination: int = 2):
        """Генерация полного датасета для всех комбинаций персон и категорий"""
        all_data = []
        
        for persona in self.personas:
            for category in self.categories:
                print(f"\n{'='*60}")
                print(f"Генерация для: {persona['name']} -> {category['name_ru']}")
                print(f"{'='*60}")
                
                batch = []
                for i in range(samples_per_combination):
                    print(f"  Образец {i+1}/{samples_per_combination}...")
                    sample = self._generate_ticket(persona, category)
                    if sample:
                        batch.append(sample)
                        print(f"  ✓ Успешно")
                    else:
                        print(f"  ✗ Ошибка")
                    time.sleep(1)
                
                all_data.extend(batch)
        
        self._save(all_data, f"full_dataset_{samples_per_combination}_per_combo")
        return all_data

    def _save(self, data: List[Dict], suffix: str):
        os.makedirs("data/raw", exist_ok=True)
        path = f"data/raw/batch_{suffix}_{int(time.time())}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n✓ Сохранено {len(data)} записей в {path}")


# --- ПРИМЕР ИСПОЛЬЗОВАНИЯ В КОДЕ ---
if __name__ == "__main__":
    generator = DeepSeekDatasetGenerator(
        personas_path="data/config/personas.json",
        taxonomy_path="data/config/taxonomy.json",
    )

    # Вариант 1: Генерация одного конкретного набора
    # generator.create_custom_batch(persona_id="C", category_id="tech_issue", count=3)
    
    # Вариант 2: Генерация полного датасета (все персоны × все категории)
    # generator.generate_full_dataset(samples_per_combination=2)
    
    # Вариант 3: Пример для тестирования - один образец
    print("Тестовая генерация одного образца...")
    test_persona = generator.get_persona_by_id("A")
    test_category = generator.get_category_by_id("tech_issue")
    test_sample = generator._generate_ticket(test_persona, test_category)
    
    if test_sample:
        print("\n✓ Тестовый образец сгенерирован:")
        print(f"Персона: {test_persona['name']}")
        print(f"Категория: {test_category['name_ru']}")
        print(f"Текст: {test_sample['ticket_text']}")
    else:
        print("✗ Ошибка тестовой генерации")