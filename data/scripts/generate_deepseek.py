import os
import json
import time
import random
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:8b")

MAX_RETRIES = 3
RETRY_DELAY = 2.0

PROMPT_VARIATIONS = [
    "Укажи конкретную дату или дедлайн в тексте обращения.",
    "Упомяни, что абитуриент уже пробовал решить проблему самостоятельно — безуспешно.",
    "Добавь уточняющий вопрос в конце обращения.",
    "Включи конкретную деталь: номер документа, дату подачи или название программы.",
    "Напиши кратко — только суть проблемы, без лишних деталей.",
    "Добавь контекст: откуда абитуриент и на какую программу поступает.",
    "Упомяни предыдущее взаимодействие с приёмной комиссией (звонок, визит, письмо).",
]


class OllamaDatasetGenerator:
    def __init__(self, personas_path: str, taxonomy_path: str):
        self.personas = self._load_json(personas_path)
        self.categories = self._load_json(taxonomy_path)
        self.api_url = f"{OLLAMA_BASE_URL}/api/chat"

    def _load_json(self, path: str) -> List[Dict]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_persona_by_id(self, persona_id: str) -> Dict:
        persona = next((p for p in self.personas if p["id"] == persona_id), None)
        if not persona:
            raise ValueError(f"Персона с ID {persona_id} не найдена")
        return persona

    def get_category_by_id(self, category_id: str) -> Dict:
        category = next((c for c in self.categories if c["id"] == category_id), None)
        if not category:
            raise ValueError(f"Категория с ID {category_id} не найдена")
        return category

    def _generate_ticket(self, persona: Dict, category: Dict) -> Optional[Dict]:
        variation = random.choice(PROMPT_VARIATIONS)
        prompt = f"""Ты — эксперт Admission Support Service. Напиши текст обращения.

КТО ПИШЕТ: {persona['name']}
ОПИСАНИЕ: {persona['settings']['description']}
СТИЛЬ: {persona['settings']['style']}
ТОН: {persona['settings']['tone']}

ТЕМА: {category['name_ru']} ({category['description']})

ФОРМАТ ПОДАЧИ: {variation}

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
}}"""

        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "Ты эксперт по генерации реалистичных обращений для службы поддержки абитуриентов. Отвечай только валидным JSON без лишнего текста.",
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.9},
            "format": "json",
        }

        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(self.api_url, json=payload, timeout=120)
                response.raise_for_status()
                content = response.json()["message"]["content"].strip()
                return json.loads(content)
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt < MAX_RETRIES - 1:
                    print(f"  Ollama недоступен, повтор через {RETRY_DELAY}с...")
                    time.sleep(RETRY_DELAY)
                else:
                    print(
                        f"  ✗ Ollama недоступен [{persona['id']}/{category['id']}]: {e}"
                    )
                    return None
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"  ✗ Ошибка [{persona['id']}/{category['id']}]: {e}")
                    return None
        return None

    def create_custom_batch(
        self, persona_id: str, category_id: str, count: int
    ) -> List[Dict]:
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
                print(f"  {i+1}/{count} ✓ {sample['ticket_text'][:60]}...")
            else:
                print(f"  {i+1}/{count} ✗")

        self._save(batch, f"deepseek_{persona_id}_{category_id}")
        return batch

    def generate_full_dataset(
        self, samples_per_combination: int = 10, max_workers: int = 2
    ) -> List[Dict]:
        """
        Генерация полного датасета.
        Поддерживает resume — пропускает уже сгенерированные комбинации.
        max_workers — параллельные потоки (не больше 2-4 для локального Ollama).
        """
        combinations = [
            (persona, category)
            for persona in self.personas
            for category in self.categories
        ]
        total = len(combinations)
        done_keys = self._load_done_keys()
        print(f"Модель: {OLLAMA_MODEL} @ {OLLAMA_BASE_URL}")
        print(f"Всего комбинаций: {total} ({total * samples_per_combination} образцов)")
        print(f"Уже готово: {len(done_keys)}, осталось: {total - len(done_keys)}")

        all_data: List[Dict] = []

        def generate_combo(persona: Dict, category: Dict) -> List[Dict]:
            key = f"deepseek_{persona['id']}_{category['id']}"
            if key in done_keys:
                return []
            results = []
            for _ in range(samples_per_combination):
                sample = self._generate_ticket(persona, category)
                if sample:
                    results.append(sample)
            if results:
                self._save(results, key)
            status = f"{len(results)}/{samples_per_combination}"
            print(
                f"  {'✓' if results else '✗'} {persona['name']} → {category['name_ru']}: {status}"
            )
            return results

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(generate_combo, p, c): (p, c) for p, c in combinations
            }
            completed = 0
            for future in as_completed(futures):
                completed += 1
                try:
                    all_data.extend(future.result())
                except Exception as e:
                    p, c = futures[future]
                    print(f"  ✗ Ошибка {p['name']} → {c['name_ru']}: {e}")
                print(f"Прогресс: {completed}/{total}")

        print(f"\nИтого сгенерировано: {len(all_data)} образцов")
        return all_data

    def _load_done_keys(self) -> set:
        done = set()
        raw_dir = "data/raw"
        if not os.path.exists(raw_dir):
            return done
        for fname in os.listdir(raw_dir):
            if fname.startswith("batch_") and fname.endswith(".json"):
                key = fname[len("batch_") : -len(".json")].rsplit("_", 1)[0]
                done.add(key)
        return done

    def _save(self, data: List[Dict], suffix: str):
        os.makedirs("data/raw", exist_ok=True)
        path = f"data/raw/batch_{suffix}_{int(time.time())}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  Сохранено {len(data)} записей → {path}")


if __name__ == "__main__":
    generator = OllamaDatasetGenerator(
        personas_path="data/config/personas.json",
        taxonomy_path="data/config/taxonomy.json",
    )

    # Полный датасет (все персоны × все категории)
    generator.generate_full_dataset(samples_per_combination=10, max_workers=2)

    # Или только конкретная комбинация:
    # generator.create_custom_batch(persona_id="A", category_id="tech_issue", count=5)
