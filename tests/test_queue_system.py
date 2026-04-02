import asyncio
import logging
import sys
import os
from pathlib import Path

from core.queue_manager import QueueManager, QueueType  # Добавить QueueType
from core.queues import ClassificationQueue, SNILSQueue

# Добавляем src в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import settings
from core.queue_manager import QueueManager
from core.queues import ClassificationQueue, SNILSQueue

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_queue")


class MockRedisClient:
    """Мок-клиент Redis для тестирования"""

    def __init__(self):
        self.cache = {}
        self.hits = 0
        self.misses = 0

    async def get_applicant_data(self, snils: str) -> dict:
        """Получение данных заявителя из кэша"""
        if snils in self.cache:
            self.hits += 1
            return self.cache[snils]
        self.misses += 1
        return None

    async def cache_applicant_data(self, snils: str, data: dict):
        """Кэширование данных заявителя"""
        self.cache[snils] = data

    def get_stats(self):
        """Получение статистики"""
        return {"hits": self.hits, "misses": self.misses, "cache_size": len(self.cache)}


class MockNestClient:
    """Мок-клиент Nest.js API для тестирования"""

    def __init__(self):
        self.applicant_data = {
            "123-456-789 01": {
                "has_bvi": True,
                "has_special_quota": False,
                "has_separate_quota": True,
                "has_target_quota": False,
                "has_priority_right": True,
                "original_document_received": True,
                "exam_scores": [85, 90, 78],
            },
            "987-654-321 02": {
                "has_bvi": False,
                "has_special_quota": True,
                "has_separate_quota": False,
                "has_target_quota": True,
                "has_priority_right": False,
                "original_document_received": False,
                "exam_scores": [92, 88, 95],
            },
        }
        self.request_count = 0

    async def batch_get_applicants(self, snils_list: list) -> list:
        """Пакетное получение данных заявителей"""
        self.request_count += 1
        results = []

        for snils in snils_list:
            if snils in self.applicant_data:
                results.append(self.applicant_data[snils])
            else:
                # Данные по умолчанию для неизвестных SNILS
                results.append(
                    {
                        "has_bvi": False,
                        "has_special_quota": False,
                        "has_separate_quota": False,
                        "has_target_quota": False,
                        "has_priority_right": False,
                        "original_document_received": False,
                        "exam_scores": [],
                        "is_default": True,
                    }
                )

        return results

    def get_stats(self):
        """Получение статистики"""
        return {
            "request_count": self.request_count,
            "known_applicants": len(self.applicant_data),
        }


async def test_classification_queue():
    """Тестирование очереди классификации"""
    logger.info("=== Тестирование очереди классификации ===")

    # Создаем очередь с меньшими параметрами для тестирования
    queue = ClassificationQueue(
        batch_size=3,  # Маленький размер батча для тестирования
        max_wait_ms=100,  # 100 мс для быстрого тестирования
        worker_count=1,
    )

    try:
        # Запускаем очередь
        await queue.start()

        # Тестовые тексты
        test_texts = [
            "Как оплатить обучение?",
            "Какие документы нужны для поступления?",
            "Когда начинается прием документов?",
            "Есть ли бюджетные места?",
            "Какой проходной балл?",
            "Нужно ли медицинское заключение?",
            "Можно ли подать документы онлайн?",
            "Какие экзамены нужно сдавать?",
            "Есть ли подготовительные курсы?",
            "Как получить общежитие?",
        ]

        # Запускаем несколько задач параллельно
        tasks = []
        for i, text in enumerate(test_texts):
            task = asyncio.create_task(
                queue.enqueue(text), name=f"classification_task_{i}"
            )
            tasks.append(task)

        # Ждем завершения всех задач
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Анализируем результаты
        successful = 0
        failed = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Задача {i} завершилась с ошибкой: {result}")
                failed += 1
            else:
                logger.info(
                    f"Задача {i}: текст='{test_texts[i][:30]}...', "
                    f"категория={result.get('category')}, "
                    f"уверенность={result.get('confidence')}"
                )
                successful += 1

        logger.info(f"Успешно: {successful}, Ошибок: {failed}")

        # Проверяем метрики
        metrics = queue.get_metrics()
        logger.info(f"Метрики очереди классификации: {metrics}")

        # Проверяем, что батчи обрабатывались
        assert metrics["total_batches"] > 0, "Должен быть обработан хотя бы один батч"
        assert metrics["total_processed"] == len(
            test_texts
        ), "Должны быть обработаны все тексты"

        logger.info("✓ Очередь классификации работает корректно")

    finally:
        # Останавливаем очередь
        await queue.stop()


async def test_snils_queue():
    """Тестирование очереди SNILS"""
    logger.info("\n=== Тестирование очереди SNILS ===")

    # Создаем мок-клиенты
    redis_client = MockRedisClient()
    nest_client = MockNestClient()

    # Создаем очередь с меньшими параметрами для тестирования
    queue = SNILSQueue(
        batch_size=4,  # Маленький размер батча для тестирования
        max_wait_ms=100,  # 100 мс для быстрого тестирования
        worker_count=1,
        redis_client=redis_client,
        nest_client=nest_client,
    )

    try:
        # Запускаем очередь
        await queue.start()

        # Тестовые SNILS
        test_snils = [
            "123-456-789 01",  # Есть в моке
            "987-654-321 02",  # Есть в моке
            "111-222-333 03",  # Нет в моке (должен вернуть данные по умолчанию)
            "444-555-666 04",  # Нет в моке
            "123-456-789 01",  # Дубликат (должен взять из кэша)
            "777-888-999 05",  # Нет в моке
            "987-654-321 02",  # Дубликат (должен взять из кэша)
            "000-111-222 06",  # Нет в моке
        ]

        # Запускаем несколько задач параллельно
        tasks = []
        for i, snils in enumerate(test_snils):
            task = asyncio.create_task(queue.enqueue(snils), name=f"snils_task_{i}")
            tasks.append(task)

        # Ждем завершения всех задач
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Анализируем результаты
        successful = 0
        failed = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Задача {i} завершилась с ошибкой: {result}")
                failed += 1
            else:
                snils = test_snils[i]
                has_bvi = result.get("has_bvi", False)
                is_default = result.get("is_default", False)

                logger.info(
                    f"Задача {i}: SNILS={snils}, "
                    f"has_bvi={has_bvi}, "
                    f"is_default={is_default}"
                )
                successful += 1

        logger.info(f"Успешно: {successful}, Ошибок: {failed}")

        # Проверяем метрики
        metrics = queue.get_metrics()
        logger.info(f"Метрики очереди SNILS: {metrics}")

        # Проверяем статистику Redis
        redis_stats = redis_client.get_stats()
        logger.info(f"Статистика Redis: {redis_stats}")

        # Проверяем статистику Nest.js
        nest_stats = nest_client.get_stats()
        logger.info(f"Статистика Nest.js: {nest_stats}")

        # Проверяем, что кэширование работает
        assert redis_stats["hits"] > 0, "Должны быть попадания в кэш"
        assert nest_stats["request_count"] > 0, "Должны быть запросы к API"

        # Проверяем, что дубликаты брались из кэша
        # У нас 8 запросов, из них 2 уникальных известных SNILS
        # Должен быть только 1 запрос к API для этих двух SNILS
        assert (
            nest_stats["request_count"] == 2
        ), "Должен быть только один запрос к API для уникальных SNILS"

        logger.info("✓ Очередь SNILS работает корректно")

    finally:
        # Останавливаем очередь
        await queue.stop()


async def test_queue_manager():
    """Тестирование менеджера очередей"""
    logger.info("\n=== Тестирование менеджера очередей ===")

    # Создаем мок-клиенты
    redis_client = MockRedisClient()
    nest_client = MockNestClient()

    # Создаем менеджер с тестовыми параметрами
    class TestConfig:
        CLASSIFY_BATCH_SIZE = 3
        CLASSIFY_MAX_WAIT_MS = 100
        CLASSIFY_WORKER_COUNT = 1
        SNILS_BATCH_SIZE = 4
        SNILS_MAX_WAIT_MS = 100
        SNILS_WORKER_COUNT = 1

    config = TestConfig()

    # Создаем менеджер
    manager = QueueManager(config)

    # Устанавливаем клиенты для очереди SNILS
    # (в реальной реализации это будет делаться через dependency injection)

    try:
        # Запускаем менеджер
        await manager.start()

        # Проверяем, что очереди созданы
        assert manager.is_running(), "Менеджер должен быть запущен"
        assert len(manager.queues) == 2, "Должны быть созданы 2 очереди"

        # Получаем метрики
        metrics = manager.get_all_metrics()
        logger.info(f"Метрики всех очередей: {metrics}")

        # Проверяем, что очереди доступны
        classification_queue = manager.get_queue(QueueType.CLASSIFICATION)
        snils_queue = manager.get_queue(QueueType.SNILS)

        assert (
            classification_queue is not None
        ), "Очередь классификации должна быть доступна"
        assert snils_queue is not None, "Очередь SNILS должна быть доступна"

        logger.info("✓ Менеджер очередей работает корректно")

    finally:
        # Останавливаем менеджер
        await manager.stop()


async def test_concurrent_requests():
    """Тестирование конкурентных запросов"""
    logger.info("\n=== Тестирование конкурентных запросов ===")

    # Создаем очередь классификации
    queue = ClassificationQueue(batch_size=5, max_wait_ms=50, worker_count=2)

    try:
        await queue.start()

        # Создаем много конкурентных запросов
        num_requests = 20
        test_text = "Как оплатить обучение?"

        # Запускаем все запросы одновременно
        start_time = asyncio.get_event_loop().time()

        tasks = []
        for i in range(num_requests):
            task = asyncio.create_task(
                queue.enqueue(f"{test_text} #{i}"), name=f"concurrent_task_{i}"
            )
            tasks.append(task)

        # Ждем завершения
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = asyncio.get_event_loop().time()
        total_time = end_time - start_time

        # Анализируем результаты
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = sum(1 for r in results if isinstance(r, Exception))

        logger.info(
            f"Конкурентные запросы: {num_requests} запросов за {total_time:.3f} секунд"
        )
        logger.info(f"Успешно: {successful}, Ошибок: {failed}")
        logger.info(
            f"Среднее время на запрос: {(total_time / num_requests * 1000):.1f} мс"
        )

        # Проверяем метрики
        metrics = queue.get_metrics()
        logger.info(f"Метрики: {metrics}")

        # Проверяем, что батчи обрабатывались
        assert metrics["total_batches"] > 0, "Должны быть обработаны батчи"
        assert (
            metrics["total_processed"] == num_requests
        ), "Должны быть обработаны все запросы"

        # Проверяем, что время обработки разумное
        # (20 запросов с батчем 5 и 50мс таймаутом должны обработаться быстрее чем за 1 секунду)
        assert (
            total_time < 1.0
        ), f"Обработка заняла слишком много времени: {total_time:.3f}с"

        logger.info("✓ Конкурентные запросы обрабатываются корректно")

    finally:
        await queue.stop()


async def main():
    """Основная функция тестирования"""
    logger.info("Начало тестирования системы очередей")

    try:
        # Тестируем отдельные очереди
        await test_classification_queue()
        await test_snils_queue()

        # Тестируем менеджер
        await test_queue_manager()

        # Тестируем конкурентные запросы
        await test_concurrent_requests()

        logger.info("\n✅ Все тесты пройдены успешно!")

    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Запускаем тесты
    asyncio.run(main())
