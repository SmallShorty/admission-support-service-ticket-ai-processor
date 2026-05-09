"""
Дополняет датасет до TARGET образцов на каждую комбинацию персона × категория.
Перед стартом показывает таблицу недостающих данных и просит подтверждение.

Запуск:
    python data/scripts/fill_gaps.py
    python data/scripts/fill_gaps.py --target 30   # другой целевой объём
    python data/scripts/fill_gaps.py --dry-run      # только показать таблицу
"""

import argparse
import sys
from pathlib import Path

# Импортируем генератор из соседнего файла
sys.path.insert(0, str(Path(__file__).parent))
from generate_deepseek import OllamaDatasetGenerator, OLLAMA_MODEL, OLLAMA_BASE_URL, log

PERSONAS_PATH  = "data/config/personas.json"
TAXONOMY_PATH  = "data/config/taxonomy.json"
DEFAULT_TARGET = 10


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target",   type=int, default=DEFAULT_TARGET, help="Целевое количество образцов на комбинацию")
    parser.add_argument("--workers",  type=int, default=2,              help="Параллельных воркеров")
    parser.add_argument("--dry-run",  action="store_true",              help="Только показать таблицу, не генерировать")
    args = parser.parse_args()

    gen = OllamaDatasetGenerator(PERSONAS_PATH, TAXONOMY_PATH)

    # Собираем состояние
    rows = []
    for persona in gen.personas:
        for category in gen.categories:
            key  = f"deepseek_{persona['id']}_{category['id']}"
            have = gen._count_existing_samples(key)
            need = max(0, args.target - have)
            rows.append({
                "persona_id":   persona["id"],
                "persona_name": persona["name"],
                "category_id":  category["id"],
                "category_name": category["name_ru"],
                "have": have,
                "need": need,
            })

    gaps = [r for r in rows if r["need"] > 0]
    complete = [r for r in rows if r["need"] == 0]

    # Таблица недостающих
    print(f"\nМодель: {OLLAMA_MODEL} @ {OLLAMA_BASE_URL}")
    print(f"Цель:   {args.target} образцов на комбинацию\n")

    if not gaps:
        print(f"Датасет полный — все {len(rows)} комбинаций имеют >= {args.target} образцов.")
        return

    print(f"{'Персона':<20} {'Категория':<22} {'Есть':>5} {'Нужно':>6}")
    print("-" * 57)
    for r in gaps:
        status = "нет данных" if r["have"] == 0 else f"{r['have']}/{args.target}"
        print(f"{r['persona_name']:<20} {r['category_name']:<22} {r['have']:>5} {r['need']:>6}   {status}")

    total_need = sum(r["need"] for r in gaps)
    print("-" * 57)
    print(f"Комбинаций:  {len(gaps)} неполных, {len(complete)} готовых")
    print(f"Образцов:    {sum(r['have'] for r in rows)} уже есть, {total_need} нужно догенерировать\n")

    if args.dry_run:
        print("--dry-run: генерация не запускается.")
        return

    answer = input("Запустить генерацию? [y/N] ").strip().lower()
    if answer != "y":
        print("Отменено.")
        return

    log.info("Старт генерации: %d образцов в %d комбинациях", total_need, len(gaps))
    gen.generate_full_dataset(samples_per_combination=args.target, max_workers=args.workers)


if __name__ == "__main__":
    main()
