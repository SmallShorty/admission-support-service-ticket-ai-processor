import os
import json
import time
import random
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY не найден в .env")

genai.configure(api_key=api_key)

MAX_RETRIES = 3
RETRY_DELAY = 2.0

# Вариации формата подачи — выбирается случайно при каждой генерации
PROMPT_VARIATIONS = [
    "Напиши как вопрос — абитуриент не знает ответа и спрашивает.",
    "Напиши как жалобу — абитуриент недоволен и выражает раздражение.",
    "Напиши как просьбу о помощи — вежливо, с контекстом ситуации.",
    "Напиши как срочное сообщение — дедлайн горит, нужен быстрый ответ.",
    "Напиши как описание проблемы — перечисление фактов без эмоций.",
    "Напиши как повторное обращение — абитуриент уже писал, но не получил ответ.",
    "Напиши с неоднозначной формулировкой — тема затрагивает смежные вопросы, но основная — указанная категория.",
]


class DatasetGenerator:
    def __init__(self, personas_path: str, taxonomy_path: str):
        self.personas = self._load_json(personas_path)
        self.categories = self._load_json(taxonomy_path)

        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={
                "temperature": 0.85,
                "response_mime_type": "application/json",
            },
        )

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
        prompt = f"""
        Ты — эксперт Admission Support Service. Напиши текст обращения.

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
        - Длина: 2-5 предложений.

        ВЕРНИ JSON:
        {{
            "persona_id": "{persona['id']}",
            "category_id": "{category['id']}",
            "ticket_text": "текст"
        }}
        """
        for attempt in range(MAX_RETRIES):
            try:
                response = self.model.generate_content(prompt)
                return json.loads(response.text)
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    print(f"  ✗ [Persona {persona['id']}, Category {category['id']}]: {e}")
        return None

    def create_custom_batch(self, persona_id: str, category_id: str, count: int) -> List[Dict]:
        persona = self.get_persona_by_id(persona_id)
        category = self.get_category_by_id(category_id)

        print(f"Генерация {count} заявок: '{persona['name']}' → '{category['name_ru']}'")
        batch = []
        for i in range(count):
            sample = self._generate_ticket(persona, category)
            if sample:
                batch.append(sample)
                print(f"  {i+1}/{count} ✓")
            else:
                print(f"  {i+1}/{count} ✗")
            time.sleep(0.5)

        self._save(batch, f"custom_{persona_id}_{category_id}")
        return batch

    def generate_full_dataset(self, samples_per_combination: int = 10, max_workers: int = 4) -> List[Dict]:
        """
        Генерация полного датасета параллельно.
        Поддерживает resume — пропускает уже сгенерированные комбинации.
        max_workers — количество одновременных потоков.
        """
        combinations = [
            (persona, category)
            for persona in self.personas
            for category in self.categories
        ]
        total = len(combinations)
        done_keys = self._load_done_keys()
        print(f"Всего комбинаций: {total} ({total * samples_per_combination} образцов)")
        print(f"Уже готово: {len(done_keys)}, осталось: {total - len(done_keys)}")

        all_data: List[Dict] = []

        def generate_combo(persona: Dict, category: Dict) -> List[Dict]:
            key = f"custom_{persona['id']}_{category['id']}"
            if key in done_keys:
                return []
            results = []
            for _ in range(samples_per_combination):
                sample = self._generate_ticket(persona, category)
                if sample:
                    results.append(sample)
                time.sleep(0.3)
            if results:
                self._save(results, key)
            status = f"{len(results)}/{samples_per_combination}"
            print(f"  {'✓' if results else '✗'} {persona['name']} → {category['name_ru']}: {status}")
            return results

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(generate_combo, p, c): (p, c)
                for p, c in combinations
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
        """Возвращает набор уже сгенерированных ключей (для resume)."""
        done = set()
        raw_dir = "data/raw"
        if not os.path.exists(raw_dir):
            return done
        for fname in os.listdir(raw_dir):
            if fname.startswith("batch_") and fname.endswith(".json"):
                # batch_{key}_{timestamp}.json → убираем timestamp
                key = fname[len("batch_"):-len(".json")].rsplit("_", 1)[0]
                done.add(key)
        return done

    def _save(self, data: List[Dict], suffix: str):
        os.makedirs("data/raw", exist_ok=True)
        path = f"data/raw/batch_{suffix}_{int(time.time())}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  Сохранено: {path}")


if __name__ == "__main__":
    generator = DatasetGenerator(
        personas_path="data/config/personas.json",
        taxonomy_path="data/config/taxonomy.json",
    )

    # Полный датасет (все персоны × все категории, параллельно)
    generator.generate_full_dataset(samples_per_combination=10, max_workers=4)

    # Или только конкретная комбинация:
    # generator.create_custom_batch(persona_id="C", category_id="tech_issue", count=5)
