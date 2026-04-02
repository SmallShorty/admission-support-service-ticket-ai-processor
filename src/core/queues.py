import asyncio
import logging
from typing import List, Any, Dict
from .queue_manager import BatchQueue, QueueType
from .classifier import model_instance

logger = logging.getLogger(__name__)


class ClassificationQueue(BatchQueue):
    """Очередь для пакетной классификации текста"""

    def __init__(self, batch_size: int, max_wait_ms: int, worker_count: int = 1):
        super().__init__(
            queue_type=QueueType.CLASSIFICATION,
            batch_size=batch_size,
            max_wait_ms=max_wait_ms,
            worker_count=worker_count,
            name="classification_queue",
        )

        # Кэш для результатов классификации (опционально)
        self._classification_cache: Dict[str, Dict[str, Any]] = {}

        logger.info(
            f"Создана очередь классификации (batch_size={batch_size}, max_wait={max_wait_ms}ms)"
        )

    async def _process_batch_data(
        self, batch_data: List[str], batch_id: str
    ) -> List[Dict[str, Any]]:
        """
        Пакетная обработка текстов для классификации

        Args:
            batch_data: Список текстов для классификации
            batch_id: Идентификатор батча

        Returns:
            Список результатов классификации для каждого текста
        """
        if not batch_data:
            return []

        logger.info(
            f"Начата пакетная классификация батча {batch_id}: {len(batch_data)} текстов"
        )

        try:
            # Проверяем кэш для каждого текста
            cached_results = []
            texts_to_process = []
            text_indices = []

            for i, text in enumerate(batch_data):
                # Создаем простой хэш для кэширования
                text_hash = str(hash(text))

                if text_hash in self._classification_cache:
                    cached_results.append((i, self._classification_cache[text_hash]))
                else:
                    texts_to_process.append(text)
                    text_indices.append(i)

            # Обрабатываем только тексты, которых нет в кэше
            batch_results = []
            if texts_to_process:
                # Используем существующий классификатор для пакетной обработки
                # В текущей реализации model_instance.predict обрабатывает по одному тексту
                # В будущем можно оптимизировать для пакетной обработки
                for text in texts_to_process:
                    try:
                        result = model_instance.predict(text)
                        batch_results.append(result)

                        # Кэшируем результат
                        text_hash = str(hash(text))
                        self._classification_cache[text_hash] = result

                    except Exception as e:
                        logger.error(f"Ошибка при классификации текста: {e}")
                        # Возвращаем результат по умолчанию при ошибке
                        batch_results.append(
                            {
                                "category": "general",
                                "confidence": 0.5,
                                "original_description": "General questions about admission",
                            }
                        )

            # Собираем все результаты в правильном порядке
            all_results = [None] * len(batch_data)

            # Добавляем закэшированные результаты
            for idx, result in cached_results:
                all_results[idx] = result

            # Добавляем свежие результаты
            for idx, result in zip(text_indices, batch_results):
                all_results[idx] = result

            logger.info(f"Завершена пакетная классификация батча {batch_id}")
            return all_results

        except Exception as e:
            logger.error(
                f"Критическая ошибка при пакетной классификации батча {batch_id}: {e}"
            )
            # Возвращаем результаты по умолчанию для всего батча
            return [
                {
                    "category": "general",
                    "confidence": 0.5,
                    "original_description": "General questions about admission",
                }
                for _ in batch_data
            ]

    def clear_cache(self):
        """Очистка кэша классификации"""
        self._classification_cache.clear()
        logger.info("Кэш классификации очищен")


class SNILSQueue(BatchQueue):
    """Очередь для пакетного поиска данных по SNILS"""

    def __init__(
        self,
        batch_size: int,
        max_wait_ms: int,
        worker_count: int = 1,
        redis_client=None,
        nest_client=None,
    ):
        super().__init__(
            queue_type=QueueType.SNILS,
            batch_size=batch_size,
            max_wait_ms=max_wait_ms,
            worker_count=worker_count,
            name="snils_queue",
        )

        self.redis_client = redis_client
        self.nest_client = nest_client

        logger.info(
            f"Создана очередь SNILS (batch_size={batch_size}, max_wait={max_wait_ms}ms)"
        )

    async def _process_batch_data(
        self, batch_data: List[str], batch_id: str
    ) -> List[Dict[str, Any]]:
        """
        Пакетная обработка SNILS для получения данных заявителей

        Args:
            batch_data: Список SNILS для поиска
            batch_id: Идентификатор батча

        Returns:
            Список данных заявителей для каждого SNILS
        """
        if not batch_data:
            return []

        logger.info(
            f"Начата пакетная обработка SNILS батча {batch_id}: {len(batch_data)} SNILS"
        )

        try:
            # Проверяем Redis кэш для каждого SNILS
            cached_results = []
            snils_to_fetch = []
            snils_indices = []

            for i, snils in enumerate(batch_data):
                if self.redis_client:
                    try:
                        cached_data = await self.redis_client.get_applicant_data(snils)
                        if cached_data:
                            cached_results.append((i, cached_data))
                            continue
                    except Exception as e:
                        logger.warning(
                            f"Ошибка при проверке Redis кэша для SNILS {snils}: {e}"
                        )

                snils_to_fetch.append(snils)
                snils_indices.append(i)

            # Получаем данные только для SNILS, которых нет в кэше
            fetched_results = []
            if snils_to_fetch and self.nest_client:
                try:
                    # Пакетный запрос к Nest.js API
                    fetched_data = await self.nest_client.batch_get_applicants(
                        snils_to_fetch
                    )

                    # Кэшируем полученные данные
                    for snils, data in zip(snils_to_fetch, fetched_data):
                        if self.redis_client and data:
                            try:
                                await self.redis_client.cache_applicant_data(
                                    snils, data
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Ошибка при кэшировании данных для SNILS {snils}: {e}"
                                )

                        fetched_results.append(data)

                except Exception as e:
                    logger.error(f"Ошибка при пакетном запросе к Nest.js API: {e}")
                    # Возвращаем данные по умолчанию для всех SNILS в этом батче
                    fetched_results = [
                        self._get_default_applicant_data() for _ in snils_to_fetch
                    ]
            elif snils_to_fetch:
                # Если нет клиента Nest.js, возвращаем данные по умолчанию
                fetched_results = [
                    self._get_default_applicant_data() for _ in snils_to_fetch
                ]

            # Собираем все результаты в правильном порядке
            all_results = [None] * len(batch_data)

            # Добавляем закэшированные результаты
            for idx, result in cached_results:
                all_results[idx] = result

            # Добавляем свежие результаты
            for idx, result in zip(snils_indices, fetched_results):
                all_results[idx] = result

            # Заполняем оставшиеся None значениями по умолчанию
            for i in range(len(all_results)):
                if all_results[i] is None:
                    all_results[i] = self._get_default_applicant_data()

            logger.info(f"Завершена пакетная обработка SNILS батча {batch_id}")
            return all_results

        except Exception as e:
            logger.error(
                f"Критическая ошибка при пакетной обработке SNILS батча {batch_id}: {e}"
            )
            # Возвращаем данные по умолчанию для всего батча
            return [self._get_default_applicant_data() for _ in batch_data]

    def _get_default_applicant_data(self) -> Dict[str, Any]:
        """Возвращает данные заявителя по умолчанию"""
        return {
            "has_bvi": False,
            "has_special_quota": False,
            "has_separate_quota": False,
            "has_target_quota": False,
            "has_priority_right": False,
            "original_document_received": False,
            "exam_scores": [],
            "is_default": True,  # Флаг, что это данные по умолчанию
        }

    async def set_clients(self, redis_client, nest_client):
        """Установка клиентов Redis и Nest.js"""
        self.redis_client = redis_client
        self.nest_client = nest_client
        logger.info("Клиенты установлены для очереди SNILS")
