# src/core/priority.py
import random
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
    include_random: bool = True,
    random_range: tuple = (0, 100),
) -> float:
    """
    Calculate priority based on category weight and optional factors.

    Args:
        category: Category slug/ID (e.g., "tech_issue", "finance_contracts")
        confidence: Model confidence score (0-1), used to adjust priority
        include_random: Whether to add random weight
        random_range: Min and max random values (default: 0-100)

    Returns:
        Priority value (float between 0 and 100)
    """

    # Получаем базовый вес категории
    if category not in CATEGORY_WEIGHTS:
        raise ValueError(
            f"Unknown category: {category}. Available: {list(CATEGORY_WEIGHTS.keys())}"
        )

    base_priority = CATEGORY_WEIGHTS[category]

    # Модифицируем приоритет на основе уверенности модели
    if confidence is not None:
        # Уверенность 0-1, добавляем от -10 до +10
        confidence_modifier = (confidence - 0.5) * 20
        priority += confidence_modifier

    # Добавляем случайную вариативность
    if include_random:
        random_weight = random.randint(random_range[0], random_range[1])
        # Берем среднее между базовым приоритетом и случайным весом
        priority = (priority + random_weight) / 2
        # Ограничиваем от 0 до 100
        priority = max(0, min(100, priority))

    return round(priority, 2)
