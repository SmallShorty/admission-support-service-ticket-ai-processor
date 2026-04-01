# src/core/priority.py
from typing import Optional, Dict, Any

# Веса категорий на основе Wintent из вашей таблицы
CATEGORY_WEIGHTS = {
    "tech_issue": 60,  # Технические проблемы
    "finance_contracts": 50,  # Оплата и договоры
    "enrollment": 45,  # Зачисление
    "deadlines": 40,  # Сроки и дедлайны
    "docs_submission": 30,  # Подача документов
    "status_check": 25,  # Проверка статуса
    "admission_scores": 20,  # Вопросы по баллам
    "dormitory": 15,  # Общежитие
    "program_consult": 10,  # Консультация по направлениям
    "academic_info": 5,  # Учеба и расписание
    "events": 5,  # Мероприятия
    "general_info": 5,  # Общая информация
}


def calculate_priority(
    category: str,
    confidence: Optional[float] = None,
) -> float:
    """
    Calculate priority based on category weight and optional factors.

    Args:
        category: Category slug/ID (e.g., "tech_issue", "finance_contracts")
        confidence: Model confidence score (0-1), used to adjust priority

    Returns:
        Priority value (float between 0 and 100)
    """

    # Получаем базовый вес категории
    if category not in CATEGORY_WEIGHTS:
        raise ValueError(
            f"Unknown category: {category}. Available: {list(CATEGORY_WEIGHTS.keys())}"
        )

    priority = CATEGORY_WEIGHTS[category]

    # Модифицируем приоритет на основе уверенности модели
    if confidence is not None:
        # Уверенность 0-1, добавляем от -10 до +10
        confidence_modifier = (confidence - 0.5) * 20
        priority += confidence_modifier

    # Ограничиваем от 0 до 100
    priority = max(0, min(100, priority))

    return round(priority, 2)
