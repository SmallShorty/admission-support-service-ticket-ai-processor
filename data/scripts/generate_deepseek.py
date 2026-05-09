import os
import json
import time
import random
import logging
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:8b")

MAX_RETRIES = 3
RETRY_DELAY = 2.0

# Сохранять промежуточный батч каждые N образцов — защита от падения
SAVE_EVERY = 5

RAW_DIR = Path("data/raw")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("generate")

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

    def _check_ollama_connection(self):
        url = f"{OLLAMA_BASE_URL}/api/tags"
        try:
            resp = requests.get(url, timeout=5, proxies={"http": None, "https": None})
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            if OLLAMA_MODEL in models:
                log.info("Ollama: подключение OK | модель %s доступна", OLLAMA_MODEL)
            else:
                log.warning("Ollama: подключение OK | модель %s НЕ НАЙДЕНА | доступны: %s", OLLAMA_MODEL, ", ".join(models))
        except requests.ConnectionError:
            log.error("Ollama: недоступна по адресу %s — генерация завершится ошибками", OLLAMA_BASE_URL)
        except Exception as e:
            log.error("Ollama: ошибка проверки: %s", e)

    def _count_existing_samples(self, key: str) -> int:
        """Считает суммарное количество образцов во всех файлах для данного ключа."""
        if not RAW_DIR.exists():
            return 0
        count = 0
        for path in RAW_DIR.glob(f"batch_{key}_*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    count += len(data)
            except Exception:
                pass
        return count

    def _generate_ticket(self, persona: Dict, category: Dict) -> Optional[Dict]:
        variation = random.choice(PROMPT_VARIATIONS)
        prompt = f"""Напиши обращение абитуриента в приёмную комиссию.
Персона: {persona['settings']['description']} Стиль: {persona['settings']['style']} Тон: {persona['settings']['tone']}
Тема: {category['name_ru']} — {category['description']}
Требование: {variation}
Правила: 2-5 предложений, без эмодзи, на русском, тему не называй явно.
Верни JSON: {{"persona_id": "{persona['id']}", "category_id": "{category['id']}", "ticket_text": "..."}}"""

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
            "think": False,
            "options": {
                "temperature": 0.9,
                "num_ctx": 1024,
            },
            "format": "json",
        }

        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(self.api_url, json=payload, timeout=120,
                                        proxies={"http": None, "https": None})
                response.raise_for_status()
                content = response.json()["message"]["content"].strip()
                if not content:
                    log.warning("Пустой ответ от модели [%s/%s], повтор...", persona['id'], category['id'])
                    time.sleep(RETRY_DELAY)
                    continue
                return json.loads(content)
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    log.error("Ollama недоступен [%s/%s]: %s", persona['id'], category['id'], e)
                    return None
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    log.error("Ошибка генерации [%s/%s]: %s", persona['id'], category['id'], e)
                    return None
        return None

    def _save(self, data: List[Dict], key: str):
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        path = RAW_DIR / f"batch_{key}_{int(time.time())}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info("Сохранено %d образцов → %s", len(data), path.name)

    def create_custom_batch(self, persona_id: str, category_id: str, count: int) -> List[Dict]:
        persona = self.get_persona_by_id(persona_id)
        category = self.get_category_by_id(category_id)
        key = f"deepseek_{persona_id}_{category_id}"

        existing = self._count_existing_samples(key)
        remaining = count - existing
        if remaining <= 0:
            log.info("Уже есть %d/%d образцов для %s/%s, пропуск.", existing, count, persona_id, category_id)
            return []

        log.info("Запуск: %d новых (уже есть %d) — %s → %s", remaining, existing, persona['name'], category['name_ru'])
        return self._generate_batch(persona, category, key, remaining)

    def generate_full_dataset(self, samples_per_combination: int = 10, max_workers: int = 2) -> List[Dict]:
        """
        Генерация полного датасета с равным числом образцов на каждую комбинацию.

        Count-aware resume: считает уже существующие образцы и догенерирует только до цели.
        Fallback-proof: сохраняет промежуточный результат каждые SAVE_EVERY образцов,
        поэтому внезапная остановка теряет не более SAVE_EVERY-1 образцов.
        """
        combinations = [
            (persona, category)
            for persona in self.personas
            for category in self.categories
        ]
        total = len(combinations)

        counts = {
            f"deepseek_{p['id']}_{c['id']}": self._count_existing_samples(f"deepseek_{p['id']}_{c['id']}")
            for p, c in combinations
        }
        done = sum(1 for v in counts.values() if v >= samples_per_combination)
        total_existing = sum(counts.values())

        log.info("Модель: %s @ %s", OLLAMA_MODEL, OLLAMA_BASE_URL)
        log.info("Цель: %d образцов на комбинацию", samples_per_combination)
        log.info("Комбинаций: %d | Завершено: %d | Уже есть: %d | Осталось: %d",
                 total, done, total_existing, max(0, total * samples_per_combination - total_existing))
        self._check_ollama_connection()

        all_data: List[Dict] = []

        def generate_combo(persona: Dict, category: Dict) -> List[Dict]:
            key = f"deepseek_{persona['id']}_{category['id']}"
            existing = counts[key]
            remaining = samples_per_combination - existing
            if remaining <= 0:
                log.info("Пропуск: %s → %s  (уже %d/%d)", persona['name'], category['name_ru'], existing, samples_per_combination)
                return []
            label = f"{persona['name']} → {category['name_ru']}"
            log.info("Старт: %s  (есть %d, нужно %d)", label, existing, remaining)
            t0 = time.monotonic()
            result = self._generate_batch(persona, category, key, remaining)
            elapsed = time.monotonic() - t0
            total_now = existing + len(result)
            log.info("Готово: %s  %d/%d  (%.1fс)", label, total_now, samples_per_combination, elapsed)
            return result

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
                    log.error("Комбинация %s → %s упала: %s", p['name'], c['name_ru'], e)
                log.info("Прогресс: %d/%d комбинаций", completed, total)

        log.info("Генерация завершена. Новых образцов: %d", len(all_data))
        return all_data

    def _generate_batch(self, persona: Dict, category: Dict, key: str, count: int) -> List[Dict]:
        """
        Генерирует `count` образцов с промежуточным сохранением каждые SAVE_EVERY штук.
        При падении уже сохранённые образцы не теряются.
        """
        results = []
        buffer = []

        for i in range(count):
            sample = self._generate_ticket(persona, category)
            if sample:
                results.append(sample)
                buffer.append(sample)
                log.info("  [%s] %d/%d ✓", key, i + 1, count)
                if len(buffer) >= SAVE_EVERY:
                    self._save(buffer, key)
                    buffer = []
            else:
                log.warning("  [%s] %d/%d ✗ пропущен", key, i + 1, count)

        if buffer:
            self._save(buffer, key)

        return results


if __name__ == "__main__":
    generator = OllamaDatasetGenerator(
        personas_path="data/config/personas.json",
        taxonomy_path="data/config/taxonomy.json",
    )

    # Полный датасет (все персоны × все категории)
    generator.generate_full_dataset(samples_per_combination=10, max_workers=2)

    # Или только конкретная комбинация:
    # generator.create_custom_batch(persona_id="F", category_id="tech_issue", count=10)
