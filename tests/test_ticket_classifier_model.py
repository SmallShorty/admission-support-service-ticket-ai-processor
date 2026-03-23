import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.core.classifier import model_instance
import time


def run_inference_check():
    test_cases = [
        {"text": "Как подать документы на бюджет?", "expected": "docs_submission"},
        {"text": "Где посмотреть расписание занятий?", "expected": "academic_info"},
        {"text": "Ошибка 500 при загрузке фото в ЛК", "expected": "tech_issue"},
    ]

    for case in test_cases:
        start = time.time()
        res = model_instance.predict(case["text"])
        duration = round(time.time() - start, 2)

        status = "✅" if res["category"] == case["expected"] else "❌"

        print(f"{status} Текст: {case['text'][:40]}...")
        print(f"   Результат: {res['category']} (Уверенность: {res['confidence']})")
        print(f"   Время: {duration} сек.\n")


if __name__ == "__main__":
    run_inference_check()
