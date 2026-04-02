import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class QueueType(Enum):
    """Типы очередей"""

    CLASSIFICATION = "classification"
    SNILS = "snils"


@dataclass
class QueueItem:
    """Элемент очереди"""

    id: str
    data: Any
    future: asyncio.Future
    timestamp: float = field(default_factory=time.time)
    queue_type: QueueType = None


@dataclass
class BatchResult:
    """Результат обработки батча"""

    batch_id: str
    items: List[QueueItem]
    results: Dict[str, Any]
    processing_time: float


class BatchQueue:
    """Базовая очередь с пакетной обработкой"""

    def __init__(
        self,
        queue_type: QueueType,
        batch_size: int,
        max_wait_ms: int,
        worker_count: int = 1,
        name: str = None,
    ):
        self.queue_type = queue_type
        self.batch_size = batch_size
        self.max_wait_ms = max_wait_ms
        self.worker_count = worker_count
        self.name = name or f"{queue_type.value}_queue"

        # Очередь для элементов
        self._queue: asyncio.Queue = asyncio.Queue()
        # Словарь для отслеживания ожидающих элементов
        self._pending_items: Dict[str, QueueItem] = {}
        # Таймер для батча
        self._batch_timer: Optional[asyncio.Task] = None
        # Текущий батч
        self._current_batch: List[QueueItem] = []
        # Воркеры
        self._workers: List[asyncio.Task] = []
        # Флаг работы
        self._running = False

        # Метрики
        self._metrics = {
            "total_processed": 0,
            "total_batches": 0,
            "avg_batch_size": 0,
            "avg_wait_time": 0,
            "errors": 0,
        }

        logger.info(
            f"Создана очередь {self.name} (batch_size={batch_size}, max_wait={max_wait_ms}ms)"
        )

    async def start(self):
        """Запуск очереди и воркеров"""
        if self._running:
            return

        self._running = True
        # Запускаем воркеры
        for i in range(self.worker_count):
            worker = asyncio.create_task(
                self._worker_loop(), name=f"{self.name}_worker_{i}"
            )
            self._workers.append(worker)

        logger.info(f"Очередь {self.name} запущена с {self.worker_count} воркерами")

    async def stop(self):
        """Остановка очереди"""
        self._running = False

        # Отменяем таймер
        if self._batch_timer:
            self._batch_timer.cancel()
            try:
                await self._batch_timer
            except asyncio.CancelledError:
                pass

        # Отменяем воркеры
        for worker in self._workers:
            worker.cancel()

        # Ждем завершения воркеров
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        # Завершаем все ожидающие futures
        for item_id, item in self._pending_items.items():
            if not item.future.done():
                item.future.set_exception(
                    RuntimeError(f"Очередь {self.name} остановлена")
                )

        logger.info(f"Очередь {self.name} остановлена")

    async def enqueue(self, data: Any) -> Any:
        """
        Добавление элемента в очередь и ожидание результата

        Returns:
            Результат обработки элемента
        """
        # Создаем future для результата
        future = asyncio.Future()
        item_id = str(uuid.uuid4())

        # Создаем элемент очереди
        item = QueueItem(
            id=item_id, data=data, future=future, queue_type=self.queue_type
        )

        # Сохраняем в ожидающих
        self._pending_items[item_id] = item

        # Добавляем в очередь
        await self._queue.put(item)

        # Запускаем таймер, если нужно
        self._start_batch_timer()

        # Ждем результат
        try:
            result = await future
            return result
        except Exception as e:
            logger.error(f"Ошибка при обработке элемента {item_id}: {e}")
            self._metrics["errors"] += 1
            raise

    async def _worker_loop(self):
        """Цикл обработки воркера"""
        while self._running:
            try:
                # Получаем элемент из очереди
                item = await self._queue.get()

                # Добавляем в текущий батч
                self._current_batch.append(item)

                # Проверяем, нужно ли обрабатывать батч
                if len(self._current_batch) >= self.batch_size:
                    await self._process_batch()
                elif self._batch_timer is None:
                    # Если таймера нет, запускаем его
                    self._start_batch_timer()

                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в воркере {self.name}: {e}")
                await asyncio.sleep(0.1)

    def _start_batch_timer(self):
        """Запуск таймера для обработки батча"""
        if self._batch_timer is None or self._batch_timer.done():
            self._batch_timer = asyncio.create_task(self._batch_timer_task())

    async def _batch_timer_task(self):
        """Задача таймера для обработки батча по времени"""
        try:
            await asyncio.sleep(self.max_wait_ms / 1000.0)

            # Если есть элементы в батче, обрабатываем
            if self._current_batch:
                await self._process_batch()

        except asyncio.CancelledError:
            pass
        finally:
            self._batch_timer = None

    async def _process_batch(self):
        """Обработка текущего батча"""
        if not self._current_batch:
            return

        # Создаем копию батча и очищаем текущий
        batch_items = self._current_batch.copy()
        self._current_batch.clear()

        # Сбрасываем таймер
        if self._batch_timer:
            self._batch_timer.cancel()
            self._batch_timer = None

        # Обрабатываем батч
        batch_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            # Извлекаем данные из элементов
            batch_data = [item.data for item in batch_items]

            # Обрабатываем батч (этот метод должен быть переопределен)
            results = await self._process_batch_data(batch_data, batch_id)

            # Распределяем результаты по элементам
            for i, item in enumerate(batch_items):
                if i < len(results):
                    item.future.set_result(results[i])
                else:
                    item.future.set_exception(
                        RuntimeError(f"Нет результата для элемента {item.id}")
                    )

                # Удаляем из ожидающих
                self._pending_items.pop(item.id, None)

            # Обновляем метрики
            processing_time = time.time() - start_time
            self._update_metrics(batch_items, processing_time)

            logger.debug(
                f"Обработан батч {batch_id} в очереди {self.name}: "
                f"{len(batch_items)} элементов за {processing_time:.3f}с"
            )

        except Exception as e:
            logger.error(f"Ошибка при обработке батча {batch_id}: {e}")

            # Устанавливаем ошибку для всех элементов батча
            for item in batch_items:
                if not item.future.done():
                    item.future.set_exception(e)
                self._pending_items.pop(item.id, None)

            self._metrics["errors"] += 1

    async def _process_batch_data(
        self, batch_data: List[Any], batch_id: str
    ) -> List[Any]:
        """
        Обработка данных батча

        Этот метод должен быть переопределен в подклассах
        """
        raise NotImplementedError("Метод должен быть реализован в подклассе")

    def _update_metrics(self, batch_items: List[QueueItem], processing_time: float):
        """Обновление метрик"""
        batch_size = len(batch_items)

        # Вычисляем среднее время ожидания
        total_wait = 0
        for item in batch_items:
            total_wait += time.time() - item.timestamp

        avg_wait = total_wait / batch_size if batch_size > 0 else 0

        # Обновляем метрики
        self._metrics["total_processed"] += batch_size
        self._metrics["total_batches"] += 1

        # Вычисляем скользящее среднее
        old_avg_size = self._metrics["avg_batch_size"]
        old_avg_wait = self._metrics["avg_wait_time"]

        self._metrics["avg_batch_size"] = old_avg_size * 0.7 + batch_size * 0.3
        self._metrics["avg_wait_time"] = old_avg_wait * 0.7 + avg_wait * 0.3

    def get_metrics(self) -> Dict[str, Any]:
        """Получение текущих метрик"""
        return {
            **self._metrics,
            "queue_size": self._queue.qsize(),
            "pending_items": len(self._pending_items),
            "current_batch_size": len(self._current_batch),
            "is_running": self._running,
        }


class QueueManager:
    """Менеджер для управления всеми очередями"""

    def __init__(self, config):
        self.config = config
        self.queues: Dict[QueueType, BatchQueue] = {}
        self._running = False

        logger.info("Инициализация менеджера очередей")

    async def start(self):
        """Запуск всех очередей"""
        if self._running:
            return

        self._running = True

        # Создаем и запускаем очереди
        queues_to_create = [
            (
                QueueType.CLASSIFICATION,
                self.config.CLASSIFY_BATCH_SIZE,
                self.config.CLASSIFY_MAX_WAIT_MS,
                self.config.CLASSIFY_WORKER_COUNT,
                "classification_queue",
            ),
            (
                QueueType.SNILS,
                self.config.SNILS_BATCH_SIZE,
                self.config.SNILS_MAX_WAIT_MS,
                self.config.SNILS_WORKER_COUNT,
                "snils_queue",
            ),
        ]

        for queue_type, batch_size, max_wait, workers, name in queues_to_create:
            queue = BatchQueue(
                queue_type=queue_type,
                batch_size=batch_size,
                max_wait_ms=max_wait,
                worker_count=workers,
                name=name,
            )
            self.queues[queue_type] = queue
            await queue.start()

        logger.info("Менеджер очередей запущен")

    async def stop(self):
        """Остановка всех очередей"""
        if not self._running:
            return

        self._running = False

        # Останавливаем все очереди
        for queue in self.queues.values():
            await queue.stop()

        self.queues.clear()
        logger.info("Менеджер очередей остановлен")

    def get_queue(self, queue_type: QueueType) -> Optional[BatchQueue]:
        """Получение очереди по типу"""
        return self.queues.get(queue_type)

    async def enqueue_classification(self, text: str) -> Dict[str, Any]:
        """Добавление текста в очередь классификации"""
        queue = self.get_queue(QueueType.CLASSIFICATION)
        if not queue:
            raise RuntimeError("Очередь классификации не инициализирована")

        return await queue.enqueue(text)

    async def enqueue_snils(self, snils: str) -> Dict[str, Any]:
        """Добавление SNILS в очередь поиска"""
        queue = self.get_queue(QueueType.SNILS)
        if not queue:
            raise RuntimeError("Очередь SNILS не инициализирована")

        return await queue.enqueue(snils)

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Получение метрик всех очередей"""
        metrics = {}
        for queue_type, queue in self.queues.items():
            metrics[queue_type.value] = queue.get_metrics()

        return metrics

    def is_running(self) -> bool:
        """Проверка, запущен ли менеджер"""
        return self._running
