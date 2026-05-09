from pathlib import Path
from collections import defaultdict
import json

RAW_DIR = Path("data/raw")
TARGET = 10

def main():
    files = sorted(RAW_DIR.glob("batch_*.json"))
    if not files:
        print("Нет файлов в data/raw")
        return

    counts: dict[str, int] = defaultdict(int)
    total_files = 0
    errors = 0

    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                continue
            # batch_deepseek_A_tech_issue_TIMESTAMP.json → ключ deepseek_A_tech_issue
            key = path.stem.removeprefix("batch_").rsplit("_", 1)[0]
            counts[key] += len(data)
            total_files += 1
        except Exception as e:
            print(f"  Ошибка чтения {path.name}: {e}")
            errors += 1

    if not counts:
        print("Нет данных.")
        return

    # Группировка по персоне
    personas: dict[str, dict[str, int]] = defaultdict(dict)
    for key, cnt in sorted(counts.items()):
        parts = key.split("_")  # ['deepseek', 'A', 'tech', 'issue']
        persona_id = parts[1]
        category = "_".join(parts[2:])
        personas[persona_id][category] = cnt

    # Вывод таблицы
    all_categories = sorted({cat for p in personas.values() for cat in p})
    all_personas  = sorted(personas.keys())

    col_w = 22
    header = f"{'Категория':<{col_w}}" + "".join(f"{p:>6}" for p in all_personas) + f"{'ИТОГО':>7}"
    print(header)
    print("-" * len(header))

    grand_total = 0
    category_totals: dict[str, int] = defaultdict(int)

    for cat in all_categories:
        row = f"{cat:<{col_w}}"
        row_total = 0
        for persona in all_personas:
            n = personas[persona].get(cat, 0)
            mark = "!" if 0 < n < TARGET else ""
            row += f"{str(n) + mark:>6}"
            row_total += n
            category_totals[cat] += n
        row += f"{row_total:>7}"
        grand_total += row_total
        print(row)

    print("-" * len(header))
    totals_row = f"{'ИТОГО':<{col_w}}" + "".join(f"{sum(personas[p].values()):>6}" for p in all_personas) + f"{grand_total:>7}"
    print(totals_row)

    # Сводка
    complete   = sum(1 for n in counts.values() if n >= TARGET)
    incomplete = sum(1 for n in counts.values() if 0 < n < TARGET)
    missing    = sum(1 for n in counts.values() if n == 0)
    total_combos = len(all_personas) * len(all_categories)

    print(f"\nФайлов прочитано:  {total_files}" + (f"  (ошибок: {errors})" if errors else ""))
    print(f"Комбинаций всего:  {total_combos}")
    print(f"  Заполнено ≥{TARGET}:   {complete}")
    print(f"  Неполных  <{TARGET}:   {incomplete}  ← ! в таблице")
    print(f"  Отсутствуют:    {total_combos - complete - incomplete}")
    print(f"\nОбразцов итого:    {grand_total}")
    print(f"Цель ({TARGET} × {total_combos}):     {TARGET * total_combos}")
    print(f"Осталось:          {max(0, TARGET * total_combos - grand_total)}")

if __name__ == "__main__":
    main()
