#!/usr/bin/env python3
"""
Скрипт для запуска тестов системы очередей
"""

import sys
import os
from pathlib import Path

# Добавляем src в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Запускаем тесты
if __name__ == "__main__":
    print("Запуск тестов системы очередей...")

    # Импортируем и запускаем тесты
    from test_queue_system import main
    import asyncio

    try:
        asyncio.run(main())
        print("\n✅ Все тесты успешно пройдены!")
    except Exception as e:
        print(f"\n❌ Ошибка при запуске тестов: {e}")
        sys.exit(1)
