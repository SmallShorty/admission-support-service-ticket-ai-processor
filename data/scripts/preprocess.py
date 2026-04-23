"""
Скрипт предобработки датасета.

Объединяет все сырые файлы из data/raw/, удаляет дубликаты,
кодирует метки и разбивает на train/val/test выборки.

Запуск:
    python data/scripts/preprocess.py
"""

import json
import random
from pathlib import Path
from collections import defaultdict

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
TAXONOMY_PATH = Path("data/config/taxonomy.json")

TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
# TEST_RATIO = 0.15 (остаток)

RANDOM_SEED = 42


def load_raw_samples() -> list[dict]:
    samples = []
    for path in sorted(RAW_DIR.glob("batch_*.json")):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            samples.extend(data)
        elif isinstance(data, dict) and "samples" in data:
            samples.extend(data["samples"])
    return samples


def build_label_map(taxonomy_path: Path) -> dict[str, int]:
    with open(taxonomy_path, "r", encoding="utf-8") as f:
        taxonomy = json.load(f)
    return {item["id"]: idx for idx, item in enumerate(taxonomy)}


def deduplicate(samples: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result = []
    for s in samples:
        text = s.get("ticket_text", "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(s)
    return result


def stratified_split(
    samples: list[dict],
    train_ratio: float,
    val_ratio: float,
    seed: int,
) -> tuple[list, list, list]:
    rng = random.Random(seed)
    by_category: dict[str, list] = defaultdict(list)
    for s in samples:
        by_category[s["category_id"]].append(s)

    train, val, test = [], [], []
    for items in by_category.values():
        rng.shuffle(items)
        n = len(items)
        n_train = max(1, int(n * train_ratio))
        n_val = max(1, int(n * val_ratio))
        train.extend(items[:n_train])
        val.extend(items[n_train : n_train + n_val])
        test.extend(items[n_train + n_val :])

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return train, val, test


def encode_labels(samples: list[dict], label_map: dict[str, int]) -> list[dict]:
    result = []
    for s in samples:
        cat = s.get("category_id", "")
        if cat not in label_map:
            print(f"  Пропущена неизвестная категория: {cat!r}")
            continue
        result.append({
            "text": s["ticket_text"].strip(),
            "label": label_map[cat],
            "category": cat,
        })
    return result


def save_json(data: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("Загрузка сырых данных...")
    raw = load_raw_samples()
    print(f"  Загружено записей: {len(raw)}")

    raw = deduplicate(raw)
    print(f"  После дедупликации: {len(raw)}")

    if not raw:
        print("Нет данных для обработки. Сначала запустите generate_deepseek.py")
        return

    print("Построение карты меток...")
    label_map = build_label_map(TAXONOMY_PATH)
    print(f"  Категорий: {len(label_map)}")

    print("Кодирование меток...")
    encoded = encode_labels(raw, label_map)
    print(f"  Валидных записей: {len(encoded)}")

    print("Разбивка на выборки...")
    train, val, test = stratified_split(encoded, TRAIN_RATIO, VAL_RATIO, RANDOM_SEED)
    print(f"  Train: {len(train)}, Val: {len(val)}, Test: {len(test)}")

    print("Сохранение...")
    save_json(train, PROCESSED_DIR / "train.json")
    save_json(val, PROCESSED_DIR / "val.json")
    save_json(test, PROCESSED_DIR / "test.json")

    # Сохраняем карту меток (slug → index)
    save_json(label_map, PROCESSED_DIR / "label_map.json")

    print("Готово. Файлы сохранены в data/processed/")

    # Статистика по категориям
    from collections import Counter
    counts = Counter(s["category"] for s in encoded)
    print("\nРаспределение по категориям:")
    for cat, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n}")


if __name__ == "__main__":
    main()
